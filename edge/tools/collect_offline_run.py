"""Collect an offline on-device benchmark (edge/tools/offline_bench_android.sh) and score it on the host.

python edge/tools/collect_offline_run.py --serial <adb-serial> --tag s25ultra|qcs8550 [--no-comet]

Run this after the device finished (out/offline/DONE exists) and airplane mode was turned off again.
It pulls /data/local/tmp/cabin/out/offline (result.jsonl, wav/, device_stderr.log, network.log, shots/),
builds a normal run folder (results/s25ultra/s25ultra_gpu_<ts>_offline/ or results/qcs8550/device_bench_<ts>_offline/),
takes the network state from the log written ON the device during the run, and scores it with
run_device_bench.py --rescore (WER/CER, BLEU, chrF++, COMET, ASR-BLEU, latency, memory).
"""
import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = "/data/local/tmp/cabin"


def adb(serial, *args, **kw):
    return subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True)
    ap.add_argument("--tag", required=True, help="s25ultra or qcs8550")
    ap.add_argument("--no-comet", action="store_true")
    ap.add_argument("--from-dir", default=None, help="re-score an already pulled run folder (skip adb pull)")
    a = ap.parse_args()
    if a.from_dir:
        out = Path(a.from_dir)
    elif adb(a.serial, "shell", f"test -f {DEV}/out/offline/DONE && echo yes").stdout.strip() != "yes":
        raise SystemExit("the device run has not finished (no out/offline/DONE)")
    if not a.from_dir:
        out = pull(a)
    finish(a, out)


def pull(a):
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"device_bench_{stamp}_offline" if a.tag == "qcs8550" else f"{a.tag}_gpu_{stamp}_offline"
    out = ROOT / "results" / a.tag / name
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / (name + ".pull")
    tmp.mkdir()
    r = adb(a.serial, "pull", f"{DEV}/out/offline", str(tmp))
    if r.returncode:
        raise SystemExit(r.stderr)
    shutil.move(str(tmp / "offline"), str(out))
    tmp.rmdir()
    adb(a.serial, "pull", f"{DEV}/out/manifest.jsonl", str(out / "manifest.jsonl"))
    return out


def finish(a, out):

    log = (out / "network.log").read_text().splitlines()
    first = next(l for l in log if "OFFLINE-CONFIRMED-START" in l)
    last = next(l for l in reversed(log) if "OFFLINE-CHECK-END" in l)
    online_samples = [l for l in log if ("ping8888=online" in l or "ping1111=online" in l or "default_network=none" not in l)
                      and ("wav=" in l or "OFFLINE" in l)]
    model, soc, release = (out / "device.txt").read_text().split("\n")[:3]

    def state(line):
        g = lambda k: (lambda m: m.group(1) if m else None)(re.search(k + r"=(\[[^\]]*\]|\S+)", line))  # noqa: E731
        return {"airplane_mode_on": g("airplane"), "wifi_on": g("wifi_setting"), "default_network": g("default_network"),
                "external_ipv4": g("external_ipv4"), "ping_8.8.8.8": g("ping8888"), "ping_1.1.1.1": g("ping1111"),
                "internet": "offline" if g("ping8888") == "offline" and g("ping1111") == "offline" and g("default_network") == "none" else "online",
                "logged_at": line[:19]}
    gpu = adb(a.serial, "shell", "dumpsys SurfaceFlinger | grep -m1 GLES").stdout.strip()
    base = {"ro.soc.model": soc.strip(), "ro.product.model": model.strip(), "ro.build.version.release": release.strip(),
            "mem_total": adb(a.serial, "shell", "grep MemTotal /proc/meminfo").stdout.strip(), "gpu": re.sub(r"\s+", " ", gpu),
            "network_source": "network.log written on the device during the run (airplane flag + ping 8.8.8.8 every ~15 s)",
            "samples_online_during_run": len(online_samples)}
    (out / "device_info.json").write_text(json.dumps({**base, **state(first)}, ensure_ascii=False, indent=1))
    (out / "device_info_end.json").write_text(json.dumps({**base, **state(last)}, ensure_ascii=False, indent=1))
    mem = []
    for l in log:
        m = re.search(r"TOTAL PSS: (\d+).*?(?:Graphics: (\d+))?", l)
        g = re.search(r"Graphics: (\d+)", l)
        if m:
            mem.append({"t": l[:19], "total_pss": int(m.group(1)), **({"graphics": int(g.group(1))} if g else {})})
    (out / "meminfo_samples.json").write_text(json.dumps(mem))
    t0 = dt.datetime.strptime(first[:19], "%Y-%m-%d %H:%M:%S")
    t1 = dt.datetime.strptime(last[:19], "%Y-%m-%d %H:%M:%S")
    (out / "run_meta.json").write_text(json.dumps({"target": "android", "config": f"{DEV}/config.json", "offline": True,
                                                   "wall_s": (t1 - t0).total_seconds(),
                                                   "wall_source": "network.log OFFLINE-CONFIRMED-START -> OFFLINE-CHECK-END (device clock)"}))
    print(f"pulled {out}  wav={len(list((out / 'wav').glob('*.wav')))}  start: {first[:120]}  end: {last[:120]}"
          f"  online samples during run: {len(online_samples)}")
    cmd = [sys.executable, str(ROOT / "edge" / "tools" / "run_device_bench.py"), "--target", "android", "--serial", a.serial,
           "--rescore", str(out)] + (["--no-comet"] if a.no_comet else [])
    subprocess.run(cmd, check=True)

    # ---- offline evidence: verbatim lines from the raw network.log written on the device
    samples = [l for l in log if " wav=" in l]
    all_off = [l for l in samples if "default_network=none" in l and "external_ipv4=[]" in l
               and "ping8888=offline" in l and "ping1111=offline" in l]
    pick = list(dict.fromkeys([first] + samples[:3] + samples[len(samples) // 2:len(samples) // 2 + 2] + samples[-3:] + [last]))
    clock = [l for l in log if "CLOCK-NOTE" in l]
    ev = ["", "## Offline evidence (raw `network.log`, written on the device during the run)", "",
          f"- Checks every ~15 s: active default network, IPv4 addresses other than loopback, ping 8.8.8.8, ping 1.1.1.1 "
          f"(plus the airplane-mode and Wi-Fi settings for reference). adb was connected over **USB** only.",
          f"- **{len(all_off)} of {len(samples)} samples during the run were fully offline**"
          f" (no default network, no external IPv4, both pings failed).",
          "- The device clock is not network-synced while offline: " + (clock[0][20:] if clock else "see CLOCK-NOTE"),
          f"- Screenshots taken by the device itself: `shots/start.png`, `shots/middle.png`, `shots/end.png`.",
          "", "Verbatim log lines (start, first samples, middle, last samples, end):", "", "```"] + pick + ["```"]
    with open(out / "summary.md", "a") as f:
        f.write("\n".join(ev) + "\n")
    sj = json.loads((out / "summary.json").read_text())
    sj["offline_evidence"] = {"samples": len(samples), "samples_fully_offline": len(all_off),
                              "start_line": first, "end_line": last, "clock_note": clock[0] if clock else None,
                              "raw_log": "network.log", "screenshots": ["shots/start.png", "shots/middle.png", "shots/end.png"]}
    (out / "summary.json").write_text(json.dumps(sj, ensure_ascii=False, indent=1))
    print("\n".join(ev))


if __name__ == "__main__":
    main()
