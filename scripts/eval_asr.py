"""Evaluate ASR WER/CER on the organizer sample set.

python scripts/eval_asr.py --pair vi-en --model vi-30m
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jiwer  # noqa: E402

from cabin.asr import ASR, load_audio  # noqa: E402
from cabin.data import PAIRS, load_pair  # noqa: E402
from cabin.normalize import normalize  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True, choices=PAIRS)
    ap.add_argument("--model", required=True)
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--decoding", default="greedy_search")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    src_lang = PAIRS[a.pair][0]
    samples = [s for s in load_pair(a.pair) if s.wav]
    kw = {"num_threads": a.threads}
    if a.model.startswith("vi-"):
        kw["decoding"] = a.decoding
    t0 = time.time()
    asr = ASR(a.model, **kw)
    load_t = time.time() - t0

    rows, refs, hyps, audio_s, proc_s = [], [], [], 0.0, 0.0
    for s in samples:
        audio = load_audio(s.wav)
        t = time.time()
        hyp = asr.transcribe(audio)
        dt = time.time() - t
        audio_s += len(audio) / 16000
        proc_s += dt
        r, h = normalize(s.src, src_lang, drop_fillers=True), normalize(hyp, src_lang, drop_fillers=True)
        refs.append(r)
        hyps.append(h)
        rows.append({"id": s.id, "ref": s.src, "hyp": hyp, "sec": round(dt, 3)})

    if src_lang in ("zh", "ko"):
        # character error rate for CJK
        cer = jiwer.cer([r.replace(" ", "") for r in refs], [h.replace(" ", "") for h in hyps])
        wer = jiwer.wer(refs, hyps)
    else:
        wer = jiwer.wer(refs, hyps)
        cer = jiwer.cer(refs, hyps)
    summary = {"pair": a.pair, "model": a.model, "n": len(rows), "wer": round(wer * 100, 2),
               "cer": round(cer * 100, 2), "rtf": round(proc_s / audio_s, 4),
               "avg_latency_s": round(proc_s / len(rows), 3), "load_s": round(load_t, 2)}
    print(json.dumps(summary, ensure_ascii=False))
    out = Path(a.out or f"results/components/asr/asr_{a.pair}_{a.model}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1))
    for r in rows[:5]:
        print(r)


if __name__ == "__main__":
    main()
