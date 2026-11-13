"""Benchmark TTS candidates ON the device (speed) + intelligibility on the host (round-trip ASR).

python edge/tools/bench_device_tts.py [--n 60] [--only name1 name2]
Each candidate runs in its own cabin_edge process (load time excluded), synthesizing the
organizer reference sentences; wavs are pulled back and re-recognized with the host ASR.
Writes results/qcs8550/device_tts_<ts>/summary.md (+ json).
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import jiwer  # noqa: E402
import librosa  # noqa: E402
import numpy as np  # noqa: E402
import soundfile as sf  # noqa: E402

from cabin.asr import ASR, DEFAULT_ASR  # noqa: E402
from cabin.data import load_pair  # noqa: E402
from cabin.normalize import normalize  # noqa: E402

DEV = "/data/local/tmp/cabin"
C = f"{DEV}/tts_cand"
ST3 = f"{DEV}/models/sherpa-onnx-supertonic-3-tts-int8-2026-05-11"
ST2 = f"{C}/sherpa-onnx-supertonic-tts-int8-2026-03-06"


def supertonic(d, lang, steps):
    return {"kind": "supertonic", "lang": lang, "num_steps": steps,
            "duration_predictor": f"{d}/duration_predictor.int8.onnx", "text_encoder": f"{d}/text_encoder.int8.onnx",
            "vector_estimator": f"{d}/vector_estimator.int8.onnx", "vocoder": f"{d}/vocoder.int8.onnx",
            "tts_json": f"{d}/tts.json", "unicode_indexer": f"{d}/unicode_indexer.bin", "voice_style": f"{d}/voice.bin"}


def piper(name, onnx, **kw):
    d = f"{C}/{name}"
    return {"kind": "vits", "model": f"{d}/{onnx}", "tokens": f"{d}/tokens.txt", "data_dir": f"{d}/espeak-ng-data", **kw}


def kitten(name, onnx):
    d = f"{C}/{name}"
    return {"kind": "kitten", "model": f"{d}/{onnx}", "voices": f"{d}/voices.bin", "tokens": f"{d}/tokens.txt",
            "data_dir": f"{d}/espeak-ng-data"}


CANDIDATES = {
    "en": {
        "supertonic3-s5 (current)": supertonic(ST3, "en", 5),
        "supertonic3-s4": supertonic(ST3, "en", 4),
        "supertonic2-s5": supertonic(ST2, "en", 5),
        "supertonic2-s3": supertonic(ST2, "en", 3),
        "piper-lessac-medium": piper("vits-piper-en_US-lessac-medium", "en_US-lessac-medium.onnx"),
        "piper-lessac-high-int8": piper("vits-piper-en_US-lessac-high-int8", "en_US-lessac-high.onnx"),
        "piper-kristin-medium-int8": piper("vits-piper-en_US-kristin-medium-int8", "en_US-kristin-medium.onnx"),
        "piper-amy-low-int8": piper("vits-piper-en_US-amy-low-int8", "en_US-amy-low.onnx"),
        "kitten-nano-int8": kitten("kitten-nano-en-v0_8-int8", "model.int8.onnx"),
        "kitten-micro": kitten("kitten-micro-en-v0_8", "model.onnx"),
    },
    "ko": {
        "supertonic3-s5 (current)": supertonic(ST3, "ko", 5),
        "supertonic3-s4": supertonic(ST3, "ko", 4),
        "supertonic2-s5": supertonic(ST2, "ko", 5),
        "supertonic2-s3": supertonic(ST2, "ko", 3),
        "mimic3-kss-low": piper("vits-mimic3-ko_KO-kss_low", "ko_KO-kss_low.onnx"),
    },
}


def adb(serial, *args, check=True):
    return subprocess.run(["adb", "-s", serial, *args], capture_output=True, text=True, check=check)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="10.5.14.32:5555")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    out = ROOT / "results" / "qcs8550" / f"device_tts_{dt.datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True)
    base = json.loads(adb(a.serial, "shell", f"cat {DEV}/config.json").stdout)
    texts = {"en": [s.ref for s in load_pair("vi-en")][: a.n], "ko": [s.ref for s in load_pair("vi-ko")][: a.n]}
    asr = {"en": ASR(DEFAULT_ASR["en"]), "ko": ASR(DEFAULT_ASR["ko"])}
    rows = []
    for lang, cands in CANDIDATES.items():
        man = "\n".join(json.dumps({"id": f"{lang}{i:03d}", "task": "tts", "tgt": lang, "text": t}, ensure_ascii=False)
                        for i, t in enumerate(texts[lang])) + "\n"
        (out / f"man_{lang}.jsonl").write_text(man)
        adb(a.serial, "push", str(out / f"man_{lang}.jsonl"), f"{DEV}/out/tts_man.jsonl")
        for name, tcfg in cands.items():
            if a.only and not any(o in name for o in a.only):
                continue
            cfg = dict(base)
            cfg["tts"] = dict(base["tts"])
            cfg["tts"][lang] = tcfg
            cfg["tts_threads"] = a.threads
            (out / "cfg.json").write_text(json.dumps(cfg))
            adb(a.serial, "push", str(out / "cfg.json"), f"{DEV}/out/tts_cfg.json")
            adb(a.serial, "shell", f"rm -rf {DEV}/out/ttsw; mkdir -p {DEV}/out/ttsw")
            r = adb(a.serial, "shell", f"cd {DEV} && LD_LIBRARY_PATH=lib ./cabin_edge --config out/tts_cfg.json "
                    f"--manifest out/tts_man.jsonl --out out/tts_res.jsonl --wav-dir out/ttsw", check=False)
            res = adb(a.serial, "shell", f"cat {DEV}/out/tts_res.jsonl", check=False).stdout.splitlines()
            items = [json.loads(l) for l in res if l.startswith("{") and '"summary"' not in l]
            summ = next((json.loads(l)["summary"] for l in res if '"summary"' in l), {})
            if not items or "tts_ms" not in items[0]:
                print(f"{lang} {name}: FAILED\n{r.stderr[-400:]}")
                rows.append({"lang": lang, "model": name, "error": r.stderr[-300:]})
                continue
            wd = out / "wav" / lang / name.split(" ")[0]
            wd.parent.mkdir(parents=True, exist_ok=True)
            adb(a.serial, "pull", f"{DEV}/out/ttsw", str(wd))
            refs, hyps = [], []
            for it, t in zip(items, texts[lang]):
                w = wd / f"{it['id']}.wav"
                if w.exists() and w.stat().st_size > 100:
                    y, sr = sf.read(str(w), dtype="float32", always_2d=True)
                    h = asr[lang].transcribe(librosa.resample(y.mean(axis=1), orig_sr=sr, target_sr=16000))
                else:
                    h = ""
                if lang == "ko":
                    refs.append("".join(c for c in t if c.isalnum()))
                    hyps.append("".join(c for c in h if c.isalnum()))
                else:
                    refs.append(normalize(t, "en"))
                    hyps.append(normalize(h, "en"))
            err = jiwer.cer(refs, hyps) if lang == "ko" else jiwer.wer(refs, hyps)
            ms = [it["tts_ms"] for it in items]
            aud = sum(it["tts_audio_s"] for it in items)
            row = {"lang": lang, "model": name, "n": len(items), "tts_ms_mean": round(float(np.mean(ms))),
                   "tts_ms_p50": round(float(np.percentile(ms, 50))), "tts_ms_p95": round(float(np.percentile(ms, 95))),
                   "rtf": round(sum(ms) / 1000 / aud, 3), ("roundtrip_cer" if lang == "ko" else "roundtrip_wer"): round(err * 100, 2),
                   "load_ms": round(summ.get("load_ms", {}).get(f"tts_{lang}", 0)),
                   "peak_rss_mb": round(summ.get("peak_rss_kb", 0) / 1024)}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    (out / "summary.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    md = ["| lang | model | mean ms | p50 | p95 | RTF | round-trip err % | load ms | peak RSS MB |",
          "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        if "error" in r:
            md.append(f"| {r['lang']} | {r['model']} | FAILED | | | | | | |")
        else:
            md.append(f"| {r['lang']} | {r['model']} | {r['tts_ms_mean']} | {r['tts_ms_p50']} | {r['tts_ms_p95']} | {r['rtf']} | "
                      f"{r.get('roundtrip_wer', r.get('roundtrip_cer'))} | {r['load_ms']} | {r['peak_rss_mb']} |")
    (out / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print("written", out)


if __name__ == "__main__":
    main()
