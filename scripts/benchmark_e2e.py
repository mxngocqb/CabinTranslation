"""End-to-end voice-to-voice benchmark (Section 7.3 of the brief).

Measures, per utterance: ASR / MT / TTS / total latency.
Reports: ASR WER, MT BLEU / chrF++ / COMET, ASR-BLEU of the spoken output,
model size on disk, peak process RAM and peak GPU VRAM, network state.

python scripts/benchmark_e2e.py --pairs vi-en en-vi [--n 100] [--no-comet]
Writes results/pc/bench_<timestamp>/{log.txt, rows_<pair>.jsonl, summary.json, summary.md}
"""
import argparse
import datetime as dt
import json
import os
import platform
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import jiwer  # noqa: E402
import librosa  # noqa: E402
import numpy as np  # noqa: E402
import psutil  # noqa: E402
import soundfile as sf  # noqa: E402

from cabin.asr import ASR_MODELS, DEFAULT_ASR, MODELS, load_audio  # noqa: E402
from cabin.data import PAIRS, load_pair  # noqa: E402
from cabin.normalize import normalize  # noqa: E402


def network_online(timeout=1.5) -> bool:
    for host in [("8.8.8.8", 53), ("1.1.1.1", 53)]:
        try:
            socket.create_connection(host, timeout=timeout).close()
            return True
        except OSError:
            pass
    return False


def dir_size_mb(p: Path, patterns=("*.onnx", "*.gguf", "*.bin", "*.txt", "*.json", "*.model")) -> float:
    """Size of the files actually loaded (skip fp32 encoder/joiner when an int8 twin exists, test wavs, caches)."""
    import re as _re
    files = {f for pat in patterns for f in p.rglob(pat)
             if ".cache" not in f.parts and "test_wavs" not in f.parts and f.name not in ("README.md",)}
    names = {f.name for f in files}
    def unused(f):
        n = f.name
        if _re.match(r"(encoder|joiner).*[0-9]\.onnx$", n) and n.replace(".onnx", ".int8.onnx") in names:
            return True
        if _re.match(r"decoder.*\.int8\.onnx$", n) and n.replace(".int8", "") in names:
            return True  # we load the fp32 decoder (tiny) for accuracy
        return n in ("bpe.model",) and any(x.name in ("tokens.txt", "config.json") for x in files)
    files = {f for f in files if not unused(f)}
    return round(sum(f.stat().st_size for f in files) / 1e6, 1)


class PeakMonitor:
    """Samples process RSS and this process' GPU memory (nvidia-smi) in a background thread."""

    def __init__(self, interval=0.05):
        self.proc = psutil.Process()
        self.interval = interval
        self.peak_rss = 0
        self.peak_vram = 0
        self._stop = threading.Event()
        self._gpu_t = 0.0
        self.baseline_vram = gpu_used_total_mb()[0]

    def _vram_mb(self):
        # WSL2 hides per-process GPU usage, so measure total used VRAM minus the pre-load baseline
        return max(0, gpu_used_total_mb()[0] - self.baseline_vram)

    def _run(self):
        while not self._stop.is_set():
            self.peak_rss = max(self.peak_rss, self.proc.memory_info().rss)
            if time.time() - self._gpu_t > 0.5:
                self.peak_vram = max(self.peak_vram, self._vram_mb())
                self._gpu_t = time.time()
            time.sleep(self.interval)

    def __enter__(self):
        self.t = threading.Thread(target=self._run, daemon=True)
        self.t.start()
        return self

    def __exit__(self, *a):
        self._stop.set()
        self.t.join()


def gpu_used_total_mb():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,name", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=3).stdout.strip().split(",")
        return int(out[0]), out[1].strip()
    except Exception:
        return 0, "n/a"


def pct(xs, q):
    return round(float(np.percentile(xs, q)), 3) if xs else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", nargs="+", default=["vi-en", "en-vi"])
    ap.add_argument("--n", type=int, default=0, help="limit samples per pair (0 = all)")
    ap.add_argument("--no-comet", action="store_true")
    ap.add_argument("--save-audio", type=int, default=10)
    a = ap.parse_args()

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "results" / "pc" / f"bench_{stamp}"
    out.mkdir(parents=True, exist_ok=True)
    logf = open(out / "log.txt", "w", encoding="utf-8")

    def log(*x):
        line = f"[{dt.datetime.now().isoformat(timespec='milliseconds')}] " + " ".join(str(i) for i in x)
        print(line, flush=True)
        logf.write(line + "\n")
        logf.flush()

    gpu_before, gpu_name = gpu_used_total_mb()
    env = {"host": platform.node(), "os": platform.platform(), "python": platform.python_version(),
           "cpu": platform.processor() or platform.machine(), "cpu_count": os.cpu_count(),
           "ram_gb": round(psutil.virtual_memory().total / 1e9, 1), "gpu": gpu_name,
           "network_online_at_start": network_online()}
    log("ENV", json.dumps(env, ensure_ascii=False))
    if env["network_online_at_start"]:
        log("WARNING: network is ONLINE. For the official benchmark disconnect Wi-Fi/Ethernet first.")

    langs = sorted({l for p in a.pairs for l in PAIRS[p][:2]})
    from cabin.pipeline import VoiceTranslator

    with PeakMonitor() as mon:
        t0 = time.time()
        vt = VoiceTranslator(langs=tuple(langs))
        load_s = round(time.time() - t0, 2)
        log(f"models loaded in {load_s}s; MT device={vt.mt.device}")

        sizes = {f"asr:{vt.asr[l].name}": vt.asr[l].size_mb for l in langs}
        sizes[f"mt:{Path(vt.mt.gguf).name}"] = round(Path(vt.mt.gguf).stat().st_size / 1e6, 1)
        if "vi" in langs:
            sizes["tts:vifasttts-ngochuyen-small"] = dir_size_mb(MODELS / "vifasttts-ngochuyen-small" / "onnx")
        if "zh" in langs:
            sizes["tts:matcha-zh-baker+vocos"] = round(
                ((MODELS / "matcha-icefall-zh-baker" / "model-steps-3.onnx").stat().st_size
                 + (MODELS / "vocos-22khz-univ.onnx").stat().st_size) / 1e6, 1)
        if any(l in ("en", "ko") for l in langs):
            sizes["tts:supertonic-3-int8"] = dir_size_mb(MODELS / "sherpa-onnx-supertonic-3-tts-int8-2026-05-11")
        log("MODEL_SIZES_MB", json.dumps(sizes))

        results = {}
        for pair in a.pairs:
            src, tgt, _ = PAIRS[pair]
            samples = [s for s in load_pair(pair) if s.wav]
            if a.n:
                samples = samples[: a.n]
            rows = []
            back_asr = vt.asr[tgt]
            adir = out / f"audio_{pair}"
            adir.mkdir(exist_ok=True)
            with open(out / f"rows_{pair}.jsonl", "w", encoding="utf-8") as rf:
                for i, s in enumerate(samples):
                    audio = load_audio(s.wav)
                    turn = vt(audio, src, tgt)
                    # ASR-BLEU: re-recognize the synthesized speech with the target-language ASR
                    back = back_asr.transcribe(librosa.resample(turn.audio, orig_sr=turn.sample_rate,
                                                                target_sr=16000)) if turn.audio.size else ""
                    if i < a.save_audio and turn.audio.size:
                        sf.write(adir / f"{s.id}.wav", turn.audio, turn.sample_rate)
                    row = {"id": s.id, "src_ref": s.src, "asr": turn.asr_text, "mt_in": turn.mt_input,
                           "hyp": turn.translation, "ref": s.ref, "back_asr": back, **turn.timings}
                    rows.append(row)
                    rf.write(json.dumps(row, ensure_ascii=False) + "\n")
                    log(f"{pair} {s.id} asr={turn.timings['asr_s']}s mt={turn.timings['mt_s']}s "
                        f"tts={turn.timings.get('tts_s', 0)}s total={turn.timings['total_s']}s | {turn.translation}")
            results[pair] = rows
        peak_rss_mb = round(mon.peak_rss / 1e6, 1)
        peak_vram_mb = mon.peak_vram

    # ---- quality metrics
    from eval_mt import score
    summary = {"env": env, "load_s": load_s, "model_sizes_mb": sizes,
               "total_model_mb": round(sum(sizes.values()), 1),
               "peak_ram_mb": peak_rss_mb, "peak_vram_mb": peak_vram_mb,
               "gpu_used_before_mb": gpu_before, "pairs": {}}
    comet_model = None
    for pair, rows in results.items():
        src, tgt, _ = PAIRS[pair]
        cjk = src in ("zh", "ko")
        R = [normalize(r["src_ref"], src, drop_fillers=True) for r in rows]
        H = [normalize(r["asr"], src, drop_fillers=True) for r in rows]
        asr_err = jiwer.cer([x.replace(" ", "") for x in R], [x.replace(" ", "") for x in H]) if cjk else jiwer.wer(R, H)
        m = score([r["hyp"] for r in rows], [r["ref"] for r in rows], tgt)
        mb = score([r["back_asr"] for r in rows], [r["ref"] for r in rows], tgt)
        p = {"n": len(rows), ("asr_cer" if cjk else "asr_wer"): round(asr_err * 100, 2),
             "bleu": m["bleu"], "chrf++": m["chrf++"], "asr_bleu_speech_out": mb["bleu"],
             "asr_chrf_speech_out": mb["chrf++"]}
        for k in ("asr_s", "mt_s", "tts_s", "total_s"):
            xs = [r.get(k, 0) for r in rows]
            p[f"{k}_mean"] = round(float(np.mean(xs)), 3)
            p[f"{k}_p50"] = pct(xs, 50)
            p[f"{k}_p95"] = pct(xs, 95)
        p["audio_s_mean"] = round(float(np.mean([r["audio_s"] for r in rows])), 2)
        if not a.no_comet:
            try:
                from score_all import comet
                p["comet"], _ = comet([r["src_ref"] for r in rows], [r["hyp"] for r in rows], [r["ref"] for r in rows])
            except Exception as e:  # COMET is an optional dev-only metric
                log("COMET skipped:", e)
        summary["pairs"][pair] = p
        log("SUMMARY", pair, json.dumps(p, ensure_ascii=False))
    summary["network_online_at_end"] = network_online()
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1))

    md = [f"# Benchmark {stamp}", "", f"- Device: {env['cpu']} ({env['cpu_count']} threads), RAM {env['ram_gb']} GB, GPU {env['gpu']}",
          f"- Network online at start/end: {env['network_online_at_start']} / {summary['network_online_at_end']}",
          f"- Models on disk: {summary['total_model_mb']} MB  {sizes}",
          f"- Peak RAM (process RSS): {peak_rss_mb} MB, peak VRAM: {peak_vram_mb} MB, load time {load_s}s", "",
          "| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for pair, p in summary["pairs"].items():
        md.append(f"| {pair} | {p['n']} | {p.get('asr_wer', p.get('asr_cer'))} | {p['bleu']} | {p['chrf++']} | "
                  f"{p.get('comet', '-')} | {p['asr_bleu_speech_out']} | {p['asr_s_mean']} | {p['mt_s_mean']} | "
                  f"{p['tts_s_mean']} | {p['total_s_p50']} / {p['total_s_p95']} |")
    (out / "summary.md").write_text("\n".join(md) + "\n")
    log("written", out)
    print("\n".join(md))


if __name__ == "__main__":
    main()
