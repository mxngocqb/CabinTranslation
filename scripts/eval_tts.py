"""TTS intelligibility (round-trip): text -> TTS -> ASR -> WER, plus synthesis RTF.

python scripts/eval_tts.py --lang vi      # uses reference target texts of en-vi
python scripts/eval_tts.py --lang en      # uses reference target texts of vi-en
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import jiwer  # noqa: E402
import librosa  # noqa: E402
import soundfile as sf  # noqa: E402

from cabin.asr import ASR, DEFAULT_ASR  # noqa: E402
from cabin.data import load_pair  # noqa: E402
from cabin.normalize import normalize  # noqa: E402
from cabin.tts import build_tts  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", required=True, choices=["vi", "en"])
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--save", type=int, default=5, help="save first N wavs to results/tts_<lang>/")
    a = ap.parse_args()

    pair = {"vi": "en-vi", "en": "vi-en"}[a.lang]
    texts = [s.ref for s in load_pair(pair)][: a.n]
    tts = build_tts(a.lang)
    asr = ASR(DEFAULT_ASR[a.lang])
    outdir = Path(f"results/components/tts/tts_{a.lang}")
    outdir.mkdir(parents=True, exist_ok=True)
    refs, hyps, syn_s, aud_s, rows = [], [], 0.0, 0.0, []
    for i, t in enumerate(texts):
        t0 = time.time()
        wav, sr = tts.synthesize(t)
        dt = time.time() - t0
        syn_s += dt
        aud_s += len(wav) / sr
        if i < a.save:
            sf.write(outdir / f"{i:03d}.wav", wav, sr)
        hyp = asr.transcribe(librosa.resample(wav, orig_sr=sr, target_sr=16000))
        refs.append(normalize(t, a.lang, drop_fillers=True))
        hyps.append(normalize(hyp, a.lang, drop_fillers=True))
        rows.append({"text": t, "asr": hyp, "syn_s": round(dt, 3)})
    res = {"lang": a.lang, "n": len(texts), "roundtrip_wer": round(jiwer.wer(refs, hyps) * 100, 2),
           "roundtrip_cer": round(jiwer.cer(refs, hyps) * 100, 2), "tts_rtf": round(syn_s / aud_s, 4),
           "avg_syn_s": round(syn_s / len(texts), 3)}
    print(json.dumps(res, ensure_ascii=False))
    Path(f"results/components/tts/tts_{a.lang}.json").write_text(json.dumps({"summary": res, "rows": rows}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
