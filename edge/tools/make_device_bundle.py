"""Generate the on-device config (prompts.json + config.json) from the Python source of truth and
push models / binaries to the device.

Android (QCS8550 tablet, adb):
  python edge/tools/make_device_bundle.py --serial 10.5.14.32:5555 [--push] [--no-models]
Linux aarch64 (Arduino VENTUNO Q / QCS8275, Ubuntu, ssh; binaries from edge/ventunoq-linux/build.sh):
  python edge/tools/make_device_bundle.py --target linux --ssh "ssh -p 2222 arduino@localhost" [--push] [--no-models]
  -> also writes config_cpu.json / config_gpu.json (LLM backend) next to config.json.
"""
import argparse
import io
import json
import shlex
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cabin import mt, normalize  # noqa: E402

DEV = "/data/local/tmp/cabin"
LINUX_DEV = "/home/arduino/cabin"
DIST_DIR = {"android": "qcs8550-android", "linux": "ventunoq-linux"}   # edge/<dir>/dist
# LiteRT-LM Gemma file per LLM backend. Android GPU uses the -gpu build (as measured on QCS8550).
# On Linux the generic build runs on CPU (XNNPACK) and GPU (ML Drift / WebGPU-Vulkan).
GEMMA = {"android": {"gpu": "gemma-4-E2B-it-gpu.litertlm", "cpu": "gemma-4-E2B-it.litertlm"},
         "linux": {"gpu": "gemma-4-E2B-it-gpu.litertlm", "cpu": "gemma-4-E2B-it.litertlm",
                   "npu": "gemma-4-E2B-it_Qualcomm_QCS8275.litertlm"}}
M = ROOT / "models"
PAIRS = ["vi-en", "en-vi", "vi-ko", "ko-vi", "vi-zh", "zh-vi"]

# local model dir -> files used on device (all int8 where available)
MODEL_FILES = {
    "Zipformer-30M-RNNT-6000h": ["encoder-epoch-20-avg-10.int8.onnx", "decoder-epoch-20-avg-10.int8.onnx",
                                 "joiner-epoch-20-avg-10.int8.onnx", "config.json"],
    "sherpa-onnx-x-asr-zipformer-transducer-zh-en-punct-int8-2026-06-03": [
        "encoder-epoch-99-avg-1.int8.onnx", "decoder-epoch-99-avg-1.onnx", "joiner-epoch-99-avg-1.int8.onnx",
        "tokens.txt"],
    "sherpa-onnx-zipformer-korean-2024-06-24": ["encoder-epoch-99-avg-1.int8.onnx",
                                                "decoder-epoch-99-avg-1.int8.onnx",
                                                "joiner-epoch-99-avg-1.int8.onnx", "tokens.txt"],
    "vifasttts-ngochuyen-small": ["onnx/acoustic.onnx", "onnx/vocoder.onnx"],
    # EN TTS: Piper lessac-medium (233 ms/sentence on QCS8550, round-trip WER 1.1%) — needs sherpa-onnx 1.13.x (espeak)
    "vits-piper-en_US-lessac-medium": ["en_US-lessac-medium.onnx", "tokens.txt", "espeak-ng-data"],
    # KO TTS: Supertonic-2 int8, 5 steps (303 ms/sentence, round-trip CER 6.6%)
    "sherpa-onnx-supertonic-tts-int8-2026-03-06": ["duration_predictor.int8.onnx", "text_encoder.int8.onnx",
                                                   "vector_estimator.int8.onnx", "vocoder.int8.onnx",
                                                   "tts.json", "unicode_indexer.bin", "voice.bin"],
    "sherpa-onnx-supertonic-3-tts-int8-2026-05-11": ["duration_predictor.int8.onnx", "text_encoder.int8.onnx",
                                                     "vector_estimator.int8.onnx", "vocoder.int8.onnx",
                                                     "tts.json", "unicode_indexer.bin", "voice.bin"],
    "matcha-icefall-zh-baker": ["model-steps-3.onnx", "lexicon.txt", "tokens.txt", "phone.fst", "date.fst",
                                "number.fst", "dict"],
    ".": ["vocos-22khz-univ.onnx"],
}


def prompts() -> dict:
    sysmap = {}
    for p in PAIRS:
        s, t = p.split("-")
        sysmap[p] = mt.SYSTEM.format(src=mt.LANG_NAME[s], tgt=mt.LANG_NAME[t]) + mt.STYLE_HINT[t]
    lower = {p: sysmap[p] + mt.LOWERCASE_NOTE.format(tgt=mt.LANG_NAME[p.split("-")[1]]) for p in PAIRS if p.startswith("vi-")}
    return {"system": sysmap, "system_lower": lower, "punct": {"vi": mt.PUNCT_SYSTEM["vi"]},
            "vi_q_end": list(normalize._VI_Q_END), "vi_q_any": list(normalize._VI_Q_ANY),
            "en_q_start": list(normalize._EN_Q_START)}


def config(max_tokens: int, backend: str, dev: str = DEV, gemma: str = "gemma-4-E2B-it-gpu.litertlm",
           mt_threads: int = 0, punct_pass: bool = False) -> dict:
    d = f"{dev}/models"
    vi = f"{d}/Zipformer-30M-RNNT-6000h"
    xa = f"{d}/sherpa-onnx-x-asr-zipformer-transducer-zh-en-punct-int8-2026-06-03"
    ko = f"{d}/sherpa-onnx-zipformer-korean-2024-06-24"
    st = f"{d}/sherpa-onnx-supertonic-tts-int8-2026-03-06"   # Supertonic-2 (KO): 3x faster than v3 on QCS8550
    pp = f"{d}/vits-piper-en_US-lessac-medium"
    mc = f"{d}/matcha-icefall-zh-baker"
    sup = lambda lang: {"kind": "supertonic", "lang": lang, "num_steps": 5, "duration_predictor": f"{st}/duration_predictor.int8.onnx",  # noqa: E731
                        "text_encoder": f"{st}/text_encoder.int8.onnx",
                        "vector_estimator": f"{st}/vector_estimator.int8.onnx", "vocoder": f"{st}/vocoder.int8.onnx",
                        "tts_json": f"{st}/tts.json", "unicode_indexer": f"{st}/unicode_indexer.bin",
                        "voice_style": f"{st}/voice.bin"}
    xasr = {"encoder": f"{xa}/encoder-epoch-99-avg-1.int8.onnx", "decoder": f"{xa}/decoder-epoch-99-avg-1.onnx",
            "joiner": f"{xa}/joiner-epoch-99-avg-1.int8.onnx", "tokens": f"{xa}/tokens.txt"}
    return {
        "prompts": f"{dev}/prompts.json",
        "web_root": f"{dev}/web",
        "live_dir": f"{dev}/out/live",
        # False: VI ASR (all caps) -> lowercase + rule-based '?'/'.' -> ONE Gemma call with system_lower
        # (LOWERCASE_NOTE). True: extra Gemma punctuation pass before MT (2 calls; COMET +0.8, ~0.5 s slower
        # on QCS8550, ~1.5 s on QCS8275).
        "punct_pass": punct_pass,
        "threads": 4, "tts_threads": 2,
        "mt": {"model": f"{d}/{gemma}", "backend": backend, "max_num_tokens": max_tokens,
               "max_output_tokens": 128, "cache_dir": f"{dev}/cache", "num_threads": mt_threads},
        "asr": {
            "vi": {"encoder": f"{vi}/encoder-epoch-20-avg-10.int8.onnx", "decoder": f"{vi}/decoder-epoch-20-avg-10.int8.onnx",
                   "joiner": f"{vi}/joiner-epoch-20-avg-10.int8.onnx", "tokens": f"{vi}/config.json"},
            "en": xasr, "zh": xasr,
            "ko": {"encoder": f"{ko}/encoder-epoch-99-avg-1.int8.onnx", "decoder": f"{ko}/decoder-epoch-99-avg-1.int8.onnx",
                   "joiner": f"{ko}/joiner-epoch-99-avg-1.int8.onnx", "tokens": f"{ko}/tokens.txt"},
        },
        "tts": {
            "vi": {"kind": "vifasttts", "acoustic": f"{d}/vifasttts-ngochuyen-small/onnx/acoustic.onnx",
                   "vocoder": f"{d}/vifasttts-ngochuyen-small/onnx/vocoder.onnx"},
            "en": {"kind": "vits", "model": f"{pp}/en_US-lessac-medium.onnx", "tokens": f"{pp}/tokens.txt",
                   "data_dir": f"{pp}/espeak-ng-data"},
            "ko": sup("ko"),
            "zh": {"kind": "matcha", "acoustic_model": f"{mc}/model-steps-3.onnx", "vocoder": f"{d}/vocos-22khz-univ.onnx",
                   "lexicon": f"{mc}/lexicon.txt", "tokens": f"{mc}/tokens.txt", "dict_dir": f"{mc}/dict",
                   "rule_fsts": f"{mc}/phone.fst,{mc}/date.fst,{mc}/number.fst"},
        },
    }


def adb(serial, *args, check=True):
    return subprocess.run(["adb", "-s", serial, *args], check=check, capture_output=True, text=True)


def ssh_push(ssh: list, items: list, dst: str):
    """items: [(local Path, arcname relative to dst)] -> streamed as one tar over ssh."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for src, arc in items:
            tf.add(str(src), arcname=arc)
    r = subprocess.run([*ssh, f"mkdir -p {dst} && tar -C {dst} -xf -"], input=buf.getvalue(), capture_output=True)
    if r.returncode:
        raise RuntimeError(r.stderr.decode()[-500:])


def push_linux(a, out):
    ssh = shlex.split(a.ssh)
    dev = a.dev_dir
    items = [(out / f, f) for f in ["cabin_edge", "prompts.json", "config.json", "config_cpu.json", "config_gpu.json", "config_npu.json", "cabin_edge_npu", "https_proxy.py",
                                    "start.sh", "stop.sh"] if (out / f).exists()]
    items += [(f, f"lib/{f.name}") for f in (out / "lib").iterdir()]
    if (out / "lib_npu").is_dir():
        items += [(f, f"lib_npu/{f.name}") for f in (out / "lib_npu").iterdir()]
    items += [(ROOT / "edge" / "engine" / "web" / "index.html", "web/index.html")]
    ssh_push(ssh, items, dev)
    subprocess.run([*ssh, f"mkdir -p {dev}/cache {dev}/out && chmod 755 {dev}/cabin_edge* {dev}/*.sh 2>/dev/null; "
                          f"[ -d {dev}/lib_npu ] && ln -sf /lib/aarch64-linux-gnu/libcdsprpc.so.1 {dev}/lib_npu/libcdsprpc.so; true"])
    print("pushed binary/libs/config to", dev)
    if a.no_models:
        return
    for d, files in MODEL_FILES.items():
        items = [(M / d / f, ("" if d == "." else f"{d}/") + f) for f in files]
        ssh_push(ssh, items, f"{dev}/models")
        print("ok ", d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", choices=["android", "linux"], default="android")
    ap.add_argument("--serial", default="10.5.14.32:5555")
    ap.add_argument("--ssh", default="ssh -p 2222 arduino@localhost", help="linux target: ssh command prefix")
    ap.add_argument("--dev-dir", default=None)
    ap.add_argument("--max-tokens", type=int, default=384)
    ap.add_argument("--backend", default="gpu")
    ap.add_argument("--mt-threads", type=int, default=4, help="LiteRT-LM CPU-backend threads (linux)")
    ap.add_argument("--punct-pass", action="store_true", help="re-enable the 2-call VI punctuation pass")
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--no-models", action="store_true")
    ap.add_argument("--models-only", action="store_true", help="android: only push models (e.g. for the APK)")
    ap.add_argument("--models-dir", default=None,
                    help="android: device folder for models (default <dev>/models; the APK uses /sdcard/CabinTranslation/models)")
    ap.add_argument("--gemma", default=str(Path.home() / "edge" / "models" / "gemma-4-E2B-it-gpu.litertlm"),
                    help="android: host path of the Gemma GPU .litertlm pushed with the models")
    a = ap.parse_args()
    a.dev_dir = a.dev_dir or (LINUX_DEV if a.target == "linux" else DEV)
    out = ROOT / "edge" / DIST_DIR[a.target] / "dist"
    out.mkdir(parents=True, exist_ok=True)
    for f in ("start.sh", "stop.sh", "https_proxy.py"):  # launch scripts live next to build.sh; staged into dist/
        if (ROOT / "edge" / DIST_DIR[a.target] / f).exists():
            shutil.copy(ROOT / "edge" / DIST_DIR[a.target] / f, out / f)
    (out / "prompts.json").write_text(json.dumps(prompts(), ensure_ascii=False, indent=1))
    g = GEMMA[a.target]
    # Linux bundles use "./" paths (resolved by cabin_edge against the config's folder) -> relocatable package
    cfg_dir = "." if a.target == "linux" else a.dev_dir
    (out / "config.json").write_text(json.dumps(config(a.max_tokens, a.backend, cfg_dir, g[a.backend], punct_pass=a.punct_pass), indent=1))
    print("wrote", out / "prompts.json", out / "config.json")
    if a.target == "linux":
        for b in ("cpu", "gpu", "npu"):
            c = config(a.max_tokens, b, cfg_dir, g[b], a.mt_threads if b == "cpu" else 0, a.punct_pass)
            if b == "npu":
                # AOT-compiled Hexagon v75 build; run by cabin_edge_npu (LiteRT-LM 0.18 NPU runtime, lib_npu/)
                # measured on QCS8275: conversation_clone fails on NPU ("NPU executor's SetCurrentStep only
                # supports rolling back one token") -> no prefix cache; QNN needs QAIRT 2.50 libs in lib_npu
                # (the model embeds QAIRT 2.50.0.260828; the board's apt QAIRT 2.49 is rejected).
                c["mt"].update({"dispatch_lib_dir": f"{cfg_dir}/lib_npu", "prefix_cache": False})
            if b == "cpu":
                # measured on QCS8275 (LiteRT-LM C API 0.19.1, CPU/XNNPACK):
                # - ctx 384/512 fail (DYNAMIC_UPDATE_SLICE prepare error); 1024 works
                # - conversation_clone (system-prompt prefix cache) carries stale state on CPU -> the
                #   previous answer is repeated; so every request prefills the system prompt
                # - no GREEDY/TOP_K sampler on CPU -> cabin_edge uses TOP_P with k=1 ("topk1")
                c["mt"].update({"max_num_tokens": max(a.max_tokens, 1024), "prefix_cache": False,
                                "sampler": "topk1"})
            (out / f"config_{b}.json").write_text(json.dumps(c, indent=1))
        if a.push:
            push_linux(a, out)
        return
    if not a.push:
        return
    if a.models_only:
        push_android_models(a)
        return
    adb(a.serial, "shell", f"mkdir -p {DEV}/lib {DEV}/models {DEV}/cache {DEV}/out")
    for f in ["cabin_edge", "prompts.json", "config.json", "start.sh", "stop.sh"]:
        adb(a.serial, "push", str(out / f), f"{DEV}/")
    adb(a.serial, "shell", f"mkdir -p {DEV}/web")
    adb(a.serial, "push", str(ROOT / "edge" / "engine" / "web" / "index.html"), f"{DEV}/web/")
    adb(a.serial, "shell", f"chmod 755 {DEV}/start.sh {DEV}/stop.sh")
    for f in (out / "lib").iterdir():
        adb(a.serial, "push", str(f), f"{DEV}/lib/")
    adb(a.serial, "shell", f"chmod 755 {DEV}/cabin_edge")
    if a.no_models:
        return
    push_android_models(a)


def push_android_models(a):
    """Push ASR/TTS models + the Gemma GPU file; skips files already present with the same size."""
    root = a.models_dir or f"{DEV}/models"
    used = {k: v for k, v in MODEL_FILES.items() if "supertonic-3" not in k}   # Supertonic-3 is not used on device
    items = [(M / d / f, (root if d == "." else f"{root}/{d}") + (f"/{Path(f).parent}" if "/" in f else "")) for d, fs in used.items() for f in fs]
    items.append((Path(a.gemma), root))
    for src, target in items:
        size = src.stat().st_size if src.is_file() else None
        dst = f"{target}/{src.name}"
        if size is not None:
            r = adb(a.serial, "shell", f"stat -c %s '{dst}' 2>/dev/null", check=False)
            if r.stdout.strip() == str(size):
                print("skip", dst)
                continue
        adb(a.serial, "shell", f"mkdir -p '{target}'")
        r = adb(a.serial, "push", str(src), f"{target}/", check=False)
        print(("ok  " if r.returncode == 0 else "ERR ") + dst, r.stderr.strip()[-80:] if r.returncode else "")


if __name__ == "__main__":
    main()
