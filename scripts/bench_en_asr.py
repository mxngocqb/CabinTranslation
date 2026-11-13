"""Compare small English ASR models on the organizer EN sample set (CPU, fixed threads).

python scripts/bench_en_asr.py [--threads 2]
"""
import argparse
import gc
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import jiwer  # noqa: E402
import numpy as np  # noqa: E402
import psutil  # noqa: E402
import sherpa_onnx  # noqa: E402

from cabin.asr import load_audio  # noqa: E402
from cabin.data import load_pair  # noqa: E402
from cabin.normalize import normalize  # noqa: E402

M = ROOT / "models"
C = M / "en_candidates"


def files_mb(paths):
    return round(sum(Path(p).stat().st_size for p in paths) / 1e6, 1)


def build(name, t):
    """returns (recognizer, files, streaming)"""
    if name == "parakeet-0.6b":
        d = M / "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"
        f = [d / "encoder.int8.onnx", d / "decoder.int8.onnx", d / "joiner.int8.onnx", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_transducer(*map(str, f[:3]), tokens=str(f[3]), num_threads=t,
                                                             model_type="nemo_transducer"), f, False
    if name == "parakeet-110m":
        d = M / "sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000"
        f = [d / "encoder.int8.onnx", d / "decoder.onnx", d / "joiner.int8.onnx", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_transducer(*map(str, f[:3]), tokens=str(f[3]), num_threads=t,
                                                             model_type="nemo_transducer"), f, False
    if name == "parakeet-110m-int8dec":
        d = M / "sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000"
        f = [d / "encoder.int8.onnx", d / "decoder.int8.onnx", d / "joiner.int8.onnx", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_transducer(*map(str, f[:3]), tokens=str(f[3]), num_threads=t,
                                                             model_type="nemo_transducer"), f, False
    if name == "parakeet-110m-ctc":
        d = C / "sherpa-onnx-nemo-parakeet_tdt_ctc_110m-en-36000"
        f = [d / "model.int8.onnx", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_nemo_ctc(model=str(f[0]), tokens=str(f[1]), num_threads=t), f, False
    if name == "nemo-ctc-conformer-small":
        d = C / "sherpa-onnx-nemo-ctc-en-conformer-small"
        f = [d / "model.int8.onnx", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_nemo_ctc(model=str(f[0]), tokens=str(f[1]), num_threads=t), f, False
    if name == "canary-180m-flash":
        d = C / "sherpa-onnx-nemo-canary-180m-flash-en-es-de-fr-int8"
        f = [d / "encoder.int8.onnx", d / "decoder.int8.onnx", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_nemo_canary(encoder=str(f[0]), decoder=str(f[1]), tokens=str(f[2]),
                                                              src_lang="en", tgt_lang="en",
                                                              num_threads=t), f, False
    if name.startswith("moonshine-v2"):
        d = C / f"sherpa-onnx-moonshine-{name.split('-')[-1]}-en-quantized-2026-02-27"
        f = [d / "encoder_model.ort", d / "decoder_model_merged.ort", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_moonshine_v2(encoder=str(f[0]), decoder=str(f[1]),
                                                               tokens=str(f[2]), num_threads=t), f, False
    if name == "moonshine-v1-tiny":
        d = C / "sherpa-onnx-moonshine-tiny-en-int8"
        f = [d / "preprocess.onnx", d / "encode.int8.onnx", d / "uncached_decode.int8.onnx",
             d / "cached_decode.int8.onnx", d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_moonshine(
            preprocessor=str(f[0]), encoder=str(f[1]), uncached_decoder=str(f[2]), cached_decoder=str(f[3]),
            tokens=str(f[4]), num_threads=t), f, False
    if name == "whisper-tiny.en":
        d = C / "sherpa-onnx-whisper-tiny.en"
        f = [d / "tiny.en-encoder.int8.onnx", d / "tiny.en-decoder.int8.onnx", d / "tiny.en-tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_whisper(encoder=str(f[0]), decoder=str(f[1]), tokens=str(f[2]),
                                                          language="en", task="transcribe", num_threads=t), f, False
    if name.startswith("zipformer-libriheavy"):
        sub = {"zipformer-libriheavy-small": "sherpa-onnx-zipformer-en-libriheavy-20230926-small",
               "zipformer-libriheavy-small-punct": "sherpa-onnx-zipformer-en-libriheavy-20230830-small-punct-case"}[name]
        d = C / sub
        enc = next(d.glob("encoder-*.int8.onnx"))
        dec = next(p for p in d.glob("decoder-*.onnx") if "int8" not in p.name)
        joi = next(d.glob("joiner-*.int8.onnx"))
        f = [enc, dec, joi, d / "tokens.txt"]
        return sherpa_onnx.OfflineRecognizer.from_transducer(str(enc), str(dec), str(joi), tokens=str(f[3]),
                                                             num_threads=t), f, False
    if name == "zipformer-kroko-streaming":
        d = C / "sherpa-onnx-streaming-zipformer-en-kroko-2025-08-06"
        f = [d / "encoder.onnx", d / "decoder.onnx", d / "joiner.onnx", d / "tokens.txt"]
        return sherpa_onnx.OnlineRecognizer.from_transducer(tokens=str(f[3]), encoder=str(f[0]), decoder=str(f[1]),
                                                            joiner=str(f[2]), num_threads=t), f, True
    if name.startswith("auto:"):
        return build_auto(C / name[5:], t)
    raise ValueError(name)


def _pick(d, stem):
    """Prefer the int8 file for `stem` (encoder/decoder/joiner/model), else fp32."""
    cands = sorted(p for p in d.glob(f"{stem}*.onnx"))
    int8 = [p for p in cands if ".int8." in p.name]
    fp = [p for p in cands if ".int8." not in p.name]
    return (int8 or fp or [None])[0]


def build_auto(d, t):
    """Infer model family from directory name + files (zipformer/nemo, transducer/ctc, offline/streaming)."""
    n = d.name
    tokens = d / "tokens.txt"
    streaming = "streaming" in n
    nemo = "nemo" in n
    enc, dec, joi, mdl = _pick(d, "encoder"), _pick(d, "decoder"), _pick(d, "joiner"), _pick(d, "model")
    if enc and dec and joi:
        f = [enc, dec, joi, tokens]
        kw = dict(tokens=str(tokens), encoder=str(enc), decoder=str(dec), joiner=str(joi), num_threads=t)
        if nemo:
            kw["model_type"] = "nemo_transducer"
        if streaming:
            return sherpa_onnx.OnlineRecognizer.from_transducer(**kw), f, True
        return sherpa_onnx.OfflineRecognizer.from_transducer(**kw), f, False
    if mdl:
        f = [mdl, tokens]
        if nemo and streaming:
            return sherpa_onnx.OnlineRecognizer.from_nemo_ctc(model=str(mdl), tokens=str(tokens), num_threads=t), f, True
        if nemo:
            return sherpa_onnx.OfflineRecognizer.from_nemo_ctc(model=str(mdl), tokens=str(tokens), num_threads=t), f, False
        if streaming:
            return sherpa_onnx.OnlineRecognizer.from_zipformer2_ctc(model=str(mdl), tokens=str(tokens), num_threads=t), f, True
        return sherpa_onnx.OfflineRecognizer.from_zipformer_ctc(model=str(mdl), tokens=str(tokens), num_threads=t), f, False
    raise ValueError(f"cannot infer model type for {d}")


def decode(rec, audio, streaming):
    s = rec.create_stream()
    if streaming:
        s.accept_waveform(16000, audio)
        s.accept_waveform(16000, np.zeros(int(0.66 * 16000), dtype=np.float32))
        s.input_finished()
        while rec.is_ready(s):
            rec.decode_stream(s)
        return rec.get_result(s)
    s.accept_waveform(16000, audio)
    rec.decode_stream(s)
    return s.result.text


NAMES = ["moonshine-v2-tiny", "moonshine-v2-base", "moonshine-v1-tiny", "whisper-tiny.en",
         "zipformer-libriheavy-small", "zipformer-libriheavy-small-punct", "zipformer-kroko-streaming",
         "parakeet-110m", "parakeet-0.6b"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threads", type=int, default=2)
    ap.add_argument("--models", nargs="*", default=NAMES)
    a = ap.parse_args()
    samples = [s for s in load_pair("en-vi") if s.wav]
    audios = [load_audio(s.wav) for s in samples]
    total_audio = sum(len(x) for x in audios) / 16000
    refs = [normalize(s.src, "en", drop_fillers=True) for s in samples]
    proc = psutil.Process()
    table = []
    for name in a.models:
        gc.collect()
        rss0 = proc.memory_info().rss
        t0 = time.time()
        rec, files, streaming = build(name, a.threads)
        load_s = time.time() - t0
        decode(rec, audios[0], streaming)  # warmup
        hyps, lat = [], []
        for x in audios:
            t = time.perf_counter()
            hyps.append(decode(rec, x, streaming))
            lat.append(time.perf_counter() - t)
        rss = (proc.memory_info().rss - rss0) / 1e6
        H = [normalize(h, "en", drop_fillers=True) for h in hyps]
        row = {"model": name, "size_mb": files_mb(files), "wer": round(jiwer.wer(refs, H) * 100, 2),
               "lat_mean_s": round(float(np.mean(lat)), 3), "lat_p95_s": round(float(np.percentile(lat, 95)), 3),
               "rtf": round(sum(lat) / total_audio, 4), "ram_delta_mb": round(rss, 1), "load_s": round(load_s, 2)}
        table.append(row)
        print(json.dumps(row), flush=True)
        (ROOT / f"results/components/asr/asr_en-vi_cand_{name.replace('auto:', '')}.json").write_text(json.dumps(
            {"summary": {"pair": "en-vi", "model": name, **row},
             "rows": [{"id": s.id, "ref": s.src, "hyp": h} for s, h in zip(samples, hyps)]}, ensure_ascii=False, indent=1))
        del rec
    md = ["| model | size MB | WER % | latency mean / p95 (s) | RTF | RAM Δ MB |", "|---|---|---|---|---|---|"]
    for r in sorted(table, key=lambda r: r["wer"]):
        md.append(f"| {r['model']} | {r['size_mb']} | {r['wer']} | {r['lat_mean_s']} / {r['lat_p95_s']} | {r['rtf']} | {r['ram_delta_mb']} |")
    (ROOT / f"results/components/asr/en_asr_candidates_t{a.threads}.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
