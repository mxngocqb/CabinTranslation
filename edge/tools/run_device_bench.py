"""Run the end-to-end benchmark ON the device (cabin_edge) and score it on the host.

Android (QCS8550 tablet, adb):
  python edge/tools/run_device_bench.py --pairs vi-en en-vi [--n 20] [--serial 10.5.14.32:5555] [--no-comet]
Linux aarch64 (Arduino VENTUNO Q / QCS8275, ssh), LLM on cpu or gpu:
  python edge/tools/run_device_bench.py --target linux --ssh "ssh -p 2222 arduino@localhost" --backend gpu --pairs ...

Steps: convert sample wavs to 16 kHz PCM16 -> push -> run cabin_edge on device while polling memory
(Android: `dumpsys meminfo <pid>` PSS / Graphics; Linux: /proc/<pid>/status VmRSS + DRM fdinfo
drm-resident-memory for the GPU) -> pull jsonl + output wavs -> score (WER/CER, BLEU, chrF++,
COMET, ASR-BLEU of the spoken output re-recognized on the host).
Writes results/qcs8550/device_bench_<ts>/ (Android) or results/ventunoq/ventunoq_<backend>_<ts>/
(Linux) with device logs, raw jsonl, summary.json and summary.md.
"""
import argparse
import datetime as dt
import json
import io
import re
import shlex
import subprocess
import tarfile
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import jiwer  # noqa: E402
import librosa  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from cabin.data import PAIRS, load_pair  # noqa: E402
from cabin.normalize import normalize  # noqa: E402

DEV = "/data/local/tmp/cabin"
LINUX_DEV = "/home/arduino/cabin"


def sh(serial, cmd, check=False, timeout=None):
    return subprocess.run(["adb", "-s", serial, "shell", cmd], capture_output=True, text=True, check=check,
                          timeout=timeout)


class AdbDevice:
    def __init__(self, serial, dev=DEV):
        self.serial, self.dev, self.kind = serial, dev, "android"

    def sh(self, cmd, check=False, timeout=None):
        return sh(self.serial, cmd, check, timeout)

    def push(self, local, remote):
        subprocess.run(["adb", "-s", self.serial, "push", str(local), remote], check=True, capture_output=True)

    def pull(self, remote, local):
        subprocess.run(["adb", "-s", self.serial, "pull", remote, str(local)], check=True, capture_output=True)

    def info(self):
        return device_info(self.serial)

    def mem_sample(self, pid):
        out = self.sh(f"dumpsys meminfo {pid}", timeout=15).stdout
        vals = {}
        for key, pat in {"total_pss": r"TOTAL PSS:\s+(\d+)", "total_rss": r"TOTAL RSS:\s+(\d+)",
                         "graphics": r"Graphics:\s+(\d+)", "native_heap": r"Native Heap:\s+(\d+)",
                         "gl_mtrack": r"GL mtrack\s+(\d+)", "egl_mtrack": r"EGL mtrack\s+(\d+)"}.items():
            m = re.search(pat, out)
            if m:
                vals[key] = int(m.group(1))
        return vals, "No process found" in out


class SshDevice:
    """Linux aarch64 board over ssh (e.g. VENTUNO Q). `ssh` is a command prefix, e.g. "ssh -p 2222 user@host"."""

    def __init__(self, ssh, dev=LINUX_DEV):
        self.ssh, self.dev, self.kind = shlex.split(ssh), dev, "linux"

    def sh(self, cmd, check=False, timeout=None):
        return subprocess.run([*self.ssh, cmd], capture_output=True, text=True, check=check, timeout=timeout)

    def push(self, local, remote):
        """local file or dir -> placed inside remote dir `remote` (adb-push-to-dir semantics)."""
        local = Path(local)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            tf.add(str(local), arcname=local.name)
        dst = remote if remote.endswith("/") or local.is_dir() else str(Path(remote).parent)
        r = subprocess.run([*self.ssh, f"mkdir -p {dst} && tar -C {dst} -xf -"], input=buf.getvalue(),
                           capture_output=True)
        if r.returncode:
            raise RuntimeError(r.stderr.decode()[-400:])
        if not local.is_dir() and not remote.endswith("/") and Path(remote).name != local.name:
            self.sh(f"mv {dst}/{local.name} {remote}", check=True)

    def pull(self, remote, local):
        local = Path(local)
        rp = Path(remote)
        r = subprocess.run([*self.ssh, f"tar -C {rp.parent} -cf - {rp.name}"], capture_output=True, check=True)
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
            if local.is_dir():          # pull dir into local dir
                tf.extractall(local, filter="data")
            else:                       # single file -> exact local path
                m = tf.getmembers()[0]
                local.write_bytes(tf.extractfile(m).read())

    def info(self):
        q = lambda c: self.sh(c).stdout.strip()  # noqa: E731
        props = {
            "ro.soc.model": q("cat /sys/devices/soc0/machine 2>/dev/null"),
            "ro.product.model": q("tr -d '\\0' < /proc/device-tree/model"),
            "ro.build.version.release": q(". /etc/os-release; echo $PRETTY_NAME") + ", kernel " + q("uname -r"),
            "ro.board.platform": q("hostname"),
            "mem_total": q("grep MemTotal /proc/meminfo"),
            "cpus": q("lscpu | awk -F: '/Model name/{gsub(/^ +/,\"\",$2); printf \"%s \", $2}'") + "/ "
                    + q("nproc") + " cores",
            "gpu": self._gpu(q),
        }
        links = q("ip -br link | awk '$1!=\"lo\" && $1!~/^docker/ {print $1\"=\"$2}' | tr '\\n' ' '")
        props.update({"links": links, "wifi_on": "1" if re.search(r"wl\S*=UP", links) else "0",
                      "airplane_mode_on": "n/a",
                      "internet": q("ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1 && echo online || echo offline")})
        return props

    @staticmethod
    def _gpu(q):
        kgsl = q("cat /sys/class/kgsl/kgsl-3d0/gpu_model 2>/dev/null")
        if kgsl:   # Qualcomm proprietary driver (KGSL + Adreno OpenCL/Vulkan), e.g. Qualcomm Linux on IQ-9075
            return f"{kgsl} (KGSL, Qualcomm OpenCL/Vulkan)"
        g = re.search(r"a(\d{3})_gmu", q("(dmesg 2>/dev/null || sudo -n dmesg 2>/dev/null) | grep -m1 -o 'a[0-9]*_gmu'") or "")
        mesa = q("dpkg-query -W -f='${Version}' mesa-vulkan-drivers 2>/dev/null")
        return f"Adreno {g.group(1) if g else '?'} (msm DRM" + (f", Mesa {mesa} Vulkan)" if mesa else ")")

    def mem_sample(self, pid):
        # also count the engine's sockets connected to anything but loopback (evidence of no network use)
        out = self.sh(f"grep -E 'VmRSS|VmHWM' /proc/{pid}/status 2>/dev/null; "
                      f"cat /proc/{pid}/fdinfo/* 2>/dev/null | grep -E '^drm-(resident|total)-memory'; "
                      f"echo KGSL $(cat /sys/class/kgsl/kgsl/proc/{pid}/kernel 2>/dev/null || echo 0); "
                      f"echo NET $(python3 {self.dev}/out/net_socks.py {pid} 2>/dev/null || echo -1)",
                      timeout=15).stdout
        if not out.strip():
            return {}, True
        vals = {}
        for key, pat in {"total_rss": r"VmRSS:\s+(\d+)", "vm_hwm": r"VmHWM:\s+(\d+)"}.items():
            m = re.search(pat, out)
            if m:
                vals[key] = int(m.group(1))
        gpu = sum(int(x) for x in re.findall(r"drm-resident-memory:\s+(\d+)", out))
        k = re.search(r"KGSL (\d+)", out)
        if not gpu and k:
            gpu = int(k.group(1)) // 1024   # KGSL driver: bytes allocated by this process
        vals["graphics"] = gpu  # KiB resident in GPU (DRM or KGSL) buffers
        m = re.search(r"NET (-?\d+)", out)
        if m:
            vals["net_conns"] = int(m.group(1))  # non-loopback TCP/UDP sockets of the engine process
        return vals, False


def device_info(serial):
    props = {k: sh(serial, f"getprop {k}").stdout.strip() for k in
             ["ro.soc.model", "ro.product.model", "ro.build.version.release", "ro.board.platform"]}
    props["mem_total"] = sh(serial, "grep MemTotal /proc/meminfo").stdout.strip()
    props["gpu"] = re.sub(r"\s+", " ", sh(serial, "dumpsys SurfaceFlinger | grep -m1 GLES").stdout.strip())
    wifi = sh(serial, "settings get global wifi_on").stdout.strip()
    airplane = sh(serial, "settings get global airplane_mode_on").stdout.strip()
    ping = sh(serial, "ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1 && echo online || echo offline").stdout.strip()
    props.update({"wifi_on": wifi, "airplane_mode_on": airplane, "internet": ping})
    return props


class MemPoller:
    """Polls memory of the cabin_edge process on the device; keeps peaks (KB)."""

    def __init__(self, device):
        self.d, self.stop, self.peak = device, threading.Event(), {}
        self.samples = []

    def run(self):
        pid = None
        while not self.stop.is_set():
            if pid is None:
                pid = self.d.sh("pidof cabin_edge cabin_edge_npu").stdout.strip().split(" ")[0] or None
                if pid is None:
                    time.sleep(0.3)
                    continue
            vals, gone = self.d.mem_sample(pid)
            if not vals and gone:
                break
            if vals:
                self.samples.append({"t": time.time(), **vals})
                for k, v in vals.items():
                    self.peak[k] = max(self.peak.get(k, 0), v)
            time.sleep(1.0)


def to_pcm16(src: Path, dst: Path):
    x, sr = sf.read(str(src), dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    if sr != 16000:
        x = librosa.resample(x, orig_sr=sr, target_sr=16000)
    sf.write(str(dst), x, 16000, subtype="PCM_16")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["android", "linux"], default="android")
    ap.add_argument("--serial", default="10.5.14.32:5555")
    ap.add_argument("--ssh", default="ssh -p 2222 arduino@localhost", help="linux target: ssh command prefix")
    ap.add_argument("--backend", default="gpu", help="linux target: LLM backend -> config_<backend>.json")
    ap.add_argument("--device-tag", default=None,
                    help="results/<tag>/<tag>_<backend>_<ts> (e.g. iq9075, s25ultra); default: ventunoq (linux), qcs8550 (android)")
    ap.add_argument("--dev-dir", default=None, help="linux target: deployed folder on the device (default /home/arduino/cabin)")
    ap.add_argument("--pairs", nargs="+", default=["vi-en", "en-vi"])
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--no-comet", action="store_true")
    ap.add_argument("--config", default=None)
    ap.add_argument("--adsp-path", default=f"{LINUX_DEV}/lib_npu",
                    help="linux npu: where the Hexagon-side QNN skel (QAIRT 2.50 libQnnHtpV75Skel.so) is")
    ap.add_argument("--offline", action="store_true",
                    help="linux: switch the board's Wi-Fi off (nmcli) for the run, confirm no route/ping, switch it back on "
                         "afterwards (a watchdog on the board re-enables it after 50 min). ssh must come over a local link.")
    ap.add_argument("--rescore", default=None, metavar="RUN_DIR",
                    help="only (re)score an existing run dir (result.jsonl + wav/ already pulled); no device run")
    a = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    if a.target == "linux":
        d = SshDevice(a.ssh, a.dev_dir or LINUX_DEV)
        a.config = a.config or f"{d.dev}/config_{a.backend}.json"
        tag = a.device_tag or "ventunoq"
        out = ROOT / "results" / tag / f"{tag}_{a.backend}_{stamp}"
        d.push(Path(__file__).with_name("net_socks.py"), f"{d.dev}/out/net_socks.py")
        d.push(Path(__file__).with_name("board_syslog.sh"), f"{d.dev}/out/board_syslog.sh")
    else:
        d = AdbDevice(a.serial)
        a.config = a.config or f"{DEV}/config.json"
        out = (ROOT / "results" / a.device_tag / f"{a.device_tag}_gpu_{stamp}" if a.device_tag
               else ROOT / "results" / "qcs8550" / f"device_bench_{stamp}")
    DEVD = d.dev
    if a.rescore:
        rescore(a, d, Path(a.rescore))
        return
    stage = out / "stage"
    stage.mkdir(parents=True)
    info = d.info()
    (out / "device_info.json").write_text(json.dumps(info, ensure_ascii=False))
    print("device:", json.dumps(info, ensure_ascii=False))

    # 1) stage + push audio, build manifest
    manifest, refs = [], {}
    for pair in a.pairs:
        src, tgt, _ = PAIRS[pair]
        samples = [s for s in load_pair(pair) if s.wav]
        if a.n:
            samples = samples[: a.n]
        pd = stage / pair
        pd.mkdir()
        for s in samples:
            to_pcm16(s.wav, pd / f"{s.id}.wav")
            uid = f"{pair}__{s.id}"
            manifest.append({"id": uid, "task": "e2e", "src": src, "tgt": tgt, "wav": f"{DEVD}/data/{pair}/{s.id}.wav"})
            refs[uid] = {"pair": pair, "src_ref": s.src, "ref": s.ref}
        d.sh(f"rm -rf {DEVD}/data/{pair}; mkdir -p {DEVD}/data")
        d.push(pd, f"{DEVD}/data/")
    (stage / "manifest.jsonl").write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in manifest) + "\n")
    d.push(stage / "manifest.jsonl", f"{DEVD}/out/manifest.jsonl")
    d.sh(f"rm -rf {DEVD}/out/wav; mkdir -p {DEVD}/out/wav")

    # 2) run on device with memory polling (+ raw system logs on Linux boards: journal, kernel log, 15 s samples)
    if d.kind == "linux":
        d.sh(f"sh {DEVD}/out/board_syslog.sh start {DEVD}/out/syslog", check=True)
    if a.offline:
        go_offline(d, DEVD)
        info = d.info()   # network state at the start of the run, i.e. after going offline
        (out / "device_info.json").write_text(json.dumps(info, ensure_ascii=False))
        print("device (offline):", json.dumps(info, ensure_ascii=False))
    poller = MemPoller(d)
    th = threading.Thread(target=poller.run, daemon=True)
    th.start()
    t0 = time.time()
    run = "LD_LIBRARY_PATH=lib ./cabin_edge"
    if a.target == "linux" and a.backend == "npu":   # LiteRT-LM 0.18 NPU runtime + QNN (system QAIRT, ADSP path)
        run = ("{ [ -e lib_npu/libcdsprpc.so ] || ln -sf /lib/aarch64-linux-gnu/libcdsprpc.so.1 lib_npu/libcdsprpc.so; } && "  # as start.sh
               f"LD_LIBRARY_PATH=lib_npu:lib ADSP_LIBRARY_PATH={a.adsp_path} ./cabin_edge_npu")
    cmd = (f"cd {DEVD} && {run} --config {a.config} --manifest out/manifest.jsonl "
           f"--out out/result.jsonl --wav-dir out/wav")
    r = d.sh(cmd)
    wall = time.time() - t0
    poller.stop.set()
    th.join(timeout=20)
    (out / "device_stderr.log").write_text(r.stderr + r.stdout)
    if a.offline:
        info_end = d.info()   # still offline: taken before Wi-Fi is switched back on
        (out / "device_info_end.json").write_text(json.dumps(info_end, ensure_ascii=False))
        back_online(d, DEVD)
    if d.kind == "linux":
        d.sh(f"sh {DEVD}/out/board_syslog.sh stop {DEVD}/out/syslog")
        d.pull(f"{DEVD}/out/syslog", out)
    d.pull(f"{DEVD}/out/result.jsonl", out / "result.jsonl")
    d.pull(f"{DEVD}/out/wav", out)
    (out / "meminfo_samples.json").write_text(json.dumps(poller.samples))
    if not a.offline:
        info_end = d.info()
        (out / "device_info_end.json").write_text(json.dumps(info_end, ensure_ascii=False))
    (out / "run_meta.json").write_text(json.dumps({"target": d.kind, "backend": a.backend, "config": a.config,
                                                   "pairs": a.pairs, "wall_s": round(wall, 1), "offline": a.offline}))
    score_run(a, d, out, refs, info, info_end, poller.peak, wall, stamp)
    if (out / "syslog").is_dir():
        syslog_section(out)


NETSTATE = r"""echo "$(date '+%F %T') $1 default_route=[$(ip route show default | tr '\n' ';')] ipv4=[$(ip -o -4 addr | awk '$2!="lo"{print $2"="$4}' | tr '\n' ' ')] wifi_radio=$(nmcli radio wifi) ping8888=$(ping -c1 -W1 8.8.8.8 >/dev/null 2>&1 && echo online || echo offline) ping1111=$(ping -c1 -W1 1.1.1.1 >/dev/null 2>&1 && echo online || echo offline)" """


def go_offline(d, devd):
    """Linux board: Wi-Fi off, wait until there is no default route and both pings fail; log it in syslog/network.log."""
    log = f"{devd}/out/syslog/network.log"
    d.sh(f"echo \"$(date '+%F %T') OFFLINE-REQUEST: sudo nmcli radio wifi off (ssh stays on the local link $SSH_CONNECTION)\" >> {log}; "
         f"nohup sh -c 'sleep 3000; sudo -n nmcli radio wifi on' >/dev/null 2>&1 & echo $! > {devd}/out/.wifi_watchdog; "
         "sudo -n nmcli radio wifi off", check=True)
    for _ in range(60):
        r = d.sh("ip route show default | grep -q . && echo route; ping -c1 -W1 8.8.8.8 >/dev/null 2>&1 && echo ping8; "
                 "ping -c1 -W1 1.1.1.1 >/dev/null 2>&1 && echo ping1").stdout.strip()
        if not r:
            break
        time.sleep(2)
    else:
        raise SystemExit("board did not go offline")
    d.sh(f"sh -c {shlex.quote(NETSTATE)} x OFFLINE-CONFIRMED-START >> {log}", check=True)
    print(d.sh(f"tail -1 {log}").stdout.strip())


def back_online(d, devd):
    log = f"{devd}/out/syslog/network.log"
    d.sh(f"sh -c {shlex.quote(NETSTATE)} x OFFLINE-CHECK-END >> {log}")
    d.sh(f"kill $(cat {devd}/out/.wifi_watchdog) 2>/dev/null; sudo -n nmcli radio wifi on; "
         f"echo \"$(date '+%F %T') ONLINE-RESTORED: sudo nmcli radio wifi on\" >> {log}")
    print(d.sh(f"grep -E 'OFFLINE-CHECK-END|ONLINE-RESTORED' {log}").stdout.strip())


def syslog_section(out: Path):
    """Append verbatim lines of the raw board logs (syslog/) to summary.md and an index to summary.json."""
    sd = out / "syslog"
    net = (sd / "network.log").read_text().splitlines() if (sd / "network.log").exists() else []
    run = [ln for ln in net if "engine_pid=none" not in ln]
    socks = [int(m.group(1)) for ln in run for m in [re.search(r"engine_net_sockets=(\d+)", ln)] if m]
    files = sorted(f.name for f in sd.iterdir() if f.is_file())
    sizes = {f: (sd / f).stat().st_size for f in files}
    pick = list(dict.fromkeys(run[:2] + run[len(run) // 2:len(run) // 2 + 1] + run[-2:]))
    jr = [ln for ln in (sd / "journal_during_run.log").read_text(errors="replace").splitlines()] if (sd / "journal_during_run.log").exists() else []
    md = ["", "## Raw system logs (board, unfiltered) — `syslog/`", "",
          "Captured on the board by `edge/tools/board_syslog.sh` while the engine ran:", ""]
    md += [f"- `{f}` ({sizes[f]:,} bytes)" for f in files]
    md += ["", f"- 15 s samples while the engine was running: **{len(run)}**; engine non-loopback sockets: "
           f"**max {max(socks) if socks else 'n/a'}** over {len(socks)} samples", "",
           "Verbatim `network.log` lines (first, middle, last):", "", "```"] + pick + ["```", ""]
    if jr:
        md += [f"`journal_during_run.log`: {len(jr)} lines (first and last 5):", "", "```"] + jr[:5] + (["…"] + jr[-5:] if len(jr) > 10 else jr[5:]) + ["```", ""]
    with open(out / "summary.md", "a") as f:
        f.write("\n".join(md) + "\n")
    sj = json.loads((out / "summary.json").read_text())
    sj["system_logs"] = {"folder": "syslog/", "files": sizes, "samples_engine_running": len(run),
                         "engine_net_sockets_max": max(socks) if socks else None, "network_log_excerpt": pick}
    (out / "summary.json").write_text(json.dumps(sj, ensure_ascii=False, indent=1))
    print("\n".join(md))


def rescore(a, d, out: Path):
    """Score a run whose device part finished (e.g. host scoring crashed). Device info comes from the saved
    json files; runs made before those were saved fall back to querying the device now (marked as such)."""
    def jl(name):
        f = out / name
        return json.loads(f.read_text()) if f.exists() else None
    meta = jl("run_meta.json") or {}
    ids = [json.loads(line)["id"] for line in (out / "result.jsonl").read_text().splitlines()
           if '"summary"' not in line[:12]]
    pairs = list(dict.fromkeys(i.split("__")[0] for i in ids))
    a.pairs, a.config = pairs, meta.get("config", a.config)
    refs = {}
    for pair in pairs:
        for s in load_pair(pair):
            refs[f"{pair}__{s.id}"] = {"pair": pair, "src_ref": s.src, "ref": s.ref}
    info = jl("device_info.json")
    info_end = jl("device_info_end.json")
    if info is None:
        info = d.info()
        info["queried_at_rescore"] = True
    if info_end is None:
        info_end = dict(info)
    peak = {}
    for smp in jl("meminfo_samples.json") or []:
        for k, v in smp.items():
            if k != "t":
                peak[k] = max(peak.get(k, 0), v)
    stamp = out.name.split("_", 2)[-1]
    score_run(a, d, out, refs, info, info_end, peak, meta.get("wall_s", 0.0), stamp)
    if (out / "syslog").is_dir():
        syslog_section(out)


def score_run(a, d, out, refs, info, info_end, peak, wall, stamp):
    rows, dev_summary = [], {}
    for line in (out / "result.jsonl").read_text().splitlines():
        j = json.loads(line)
        if "summary" in j:
            dev_summary = j["summary"]
        else:
            rows.append({**j, **refs[j["id"]]})

    # 3) score
    from cabin.asr import ASR, DEFAULT_ASR
    from eval_mt import score
    back = {}
    summary = {"target": d.kind, "config": a.config, "device": info, "device_end": info_end, "device_summary": dev_summary, "meminfo_peak_kb": peak,
               "wall_s": round(wall, 1), "pairs": {}}
    for pair in a.pairs:
        src, tgt, _ = PAIRS[pair]
        pr = [x for x in rows if x["pair"] == pair]
        if tgt not in back:
            back[tgt] = ASR(DEFAULT_ASR[tgt])
        for x in pr:
            w = out / "wav" / f"{x['id']}.wav"
            x["back_asr"] = ""
            if w.exists():
                y, sr = sf.read(str(w), dtype="float32", always_2d=True)
                if len(y) >= sr // 10:   # empty translation -> near-empty wav; the encoder rejects < ~0.1 s
                    try:
                        x["back_asr"] = back[tgt].transcribe(
                            librosa.resample(y.mean(axis=1), orig_sr=sr, target_sr=16000))
                    except RuntimeError as e:
                        print("back-ASR failed", x["id"], str(e)[:80])
        cjk = src in ("zh", "ko")
        R = [normalize(x["src_ref"], src, drop_fillers=True) for x in pr]
        H = [normalize(x.get("asr", ""), src, drop_fillers=True) for x in pr]
        asr_err = (jiwer.cer([s.replace(" ", "") for s in R], [h.replace(" ", "") for h in H]) if cjk
                   else jiwer.wer(R, H))
        m = score([x.get("hyp", "") for x in pr], [x["ref"] for x in pr], tgt)
        mb = score([x["back_asr"] for x in pr], [x["ref"] for x in pr], tgt)
        p = {"n": len(pr), ("asr_cer" if cjk else "asr_wer"): round(asr_err * 100, 2), **m,
             "asr_bleu_speech_out": mb["bleu"]}
        for k in ("asr_ms", "punct_ms", "mt_ms", "tts_ms", "total_ms"):
            xs = [x.get(k, 0.0) for x in pr]
            p[f"{k}_mean"] = round(float(np.mean(xs)), 1)
            p[f"{k}_p50"] = round(float(np.percentile(xs, 50)), 1)
            p[f"{k}_p95"] = round(float(np.percentile(xs, 95)), 1)
        for k in ("ttft_ms", "prefill_tps", "decode_tps", "prefill_tok", "decode_tok"):
            xs = [x["mt_stats"][k] for x in pr if k in x.get("mt_stats", {})]
            if xs:
                p[f"mt_{k}_mean"] = round(float(np.mean(xs)), 1)
        p["audio_s_mean"] = round(float(np.mean([x.get("audio_s", 0) for x in pr])), 2)
        if not a.no_comet:
            try:
                from score_all import comet
                p["comet"], _ = comet([x["src_ref"] for x in pr], [x.get("hyp", "") for x in pr], [x["ref"] for x in pr])
            except Exception as e:
                print("COMET skipped:", e)
        summary["pairs"][pair] = p
        print(pair, json.dumps(p, ensure_ascii=False))
    (out / "rows.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in rows) + "\n")
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))

    lm = dev_summary.get("load_ms", {})
    os_name = (f"Android {info['ro.build.version.release']}" if d.kind == "android"
               else info["ro.build.version.release"])
    net = (f"wifi_on={info['wifi_on']} airplane={info['airplane_mode_on']} internet={info['internet']}"
           + (f" links=[{info.get('links', '').strip()}]" if d.kind == "linux" else ""))
    md = [f"# On-device benchmark {stamp}", "",
          f"- Device: {info['ro.soc.model']} / {info['ro.product.model']}, {os_name}, "
          f"{info['mem_total']}, {info['gpu']}" + (f", CPU {info['cpus']}" if "cpus" in info else ""),
          f"- Network at start: {net}; at end: internet={info_end['internet']}",
          f"- LLM backend: {dev_summary.get('mt_backend')} (LiteRT-LM, Gemma 4 E2B "
          f"{Path(dev_summary.get('mt_model', 'gpu.litertlm')).name}, sampler={dev_summary.get('mt_sampler', 'greedy')}, "
          f"prefix_cache={dev_summary.get('mt_prefix_cache')}, ctx={dev_summary.get('mt_max_num_tokens')}"
          + (f", threads={dev_summary.get('mt_num_threads')}" if dev_summary.get("mt_backend") == "cpu" else "")
          + "); ASR/TTS: CPU",
          f"- Load time (ms): {json.dumps({k: round(v) for k, v in lm.items()})}",
          f"- Peak process RSS (VmHWM): {round(dev_summary.get('peak_rss_kb', 0) / 1024)} MB; "
          f"{'dumpsys' if d.kind == 'android' else '/proc + DRM fdinfo'} peaks (MB): "
          + ", ".join(f"{k}={round(v / 1024)}" for k, v in peak.items() if k != "net_conns"),
          *( [f"- Engine network sockets (non-loopback TCP/UDP of the cabin_edge process, sampled every ~1 s, "
              f"whole run): max = {peak['net_conns']}"] if "net_conns" in peak else []), "",
          "| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pair, p in summary["pairs"].items():
        md.append(f"| {pair} | {p['n']} | {p.get('asr_wer', p.get('asr_cer'))} | {p['bleu']} | {p['chrf++']} | "
                  f"{p.get('comet', '-')} | {p['asr_bleu_speech_out']} | {p['asr_ms_mean']} | {p['punct_ms_mean']} | "
                  f"{p['mt_ms_mean']} | {p.get('mt_ttft_ms_mean', '-')} | {p.get('mt_decode_tps_mean', '-')} | "
                  f"{p['tts_ms_mean']} | {p['total_ms_p50']} / {p['total_ms_p95']} |")
    (out / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print("written", out)


if __name__ == "__main__":
    main()
