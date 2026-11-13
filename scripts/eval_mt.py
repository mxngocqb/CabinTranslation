"""Evaluate MT (Gemma 4 E2B) on the organizer sample set.

python scripts/eval_mt.py --pair vi-en --input gold          # text MT from reference transcript
python scripts/eval_mt.py --pair vi-en --input asr --asr vi-30m  # cascade: ASR hyp -> MT
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import sacrebleu  # noqa: E402

from cabin.data import PAIRS, load_pair  # noqa: E402
from cabin.normalize import normalize, prep_asr_text  # noqa: E402


def score(hyps, refs, tgt):
    H = [normalize(h, tgt, drop_fillers=True) for h in hyps]
    R = [normalize(r, tgt, drop_fillers=True) for r in refs]
    tok = {"zh": "zh", "ko": "char", "ja": "ja-mecab"}.get(tgt, "13a")
    if tgt == "ko":
        H = [h.replace(" ", "") for h in H]
        R = [r.replace(" ", "") for r in R]
        tok = "char"
    bleu = sacrebleu.corpus_bleu(H, [R], tokenize=tok if tok != "ja-mecab" else "char")
    chrf = sacrebleu.corpus_chrf(H, [R], word_order=2)
    return {"bleu": round(bleu.score, 2), "chrf++": round(chrf.score, 2)}


def comet_score(srcs, hyps, refs, model="Unbabel/wmt22-comet-da"):
    try:
        from comet import download_model, load_from_checkpoint
    except ImportError:
        return None
    m = load_from_checkpoint(download_model(model))
    data = [{"src": s, "mt": h, "ref": r} for s, h, r in zip(srcs, hyps, refs)]
    out = m.predict(data, batch_size=32, gpus=1, progress_bar=False)
    return round(out.system_score * 100, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pair", required=True, choices=PAIRS)
    ap.add_argument("--input", default="gold", choices=["gold", "asr"])
    ap.add_argument("--asr", default=None, help="ASR model name (reads results/components/asr/asr_<pair>_<asr>.json)")
    ap.add_argument("--backend", default="llama", choices=["hf", "llama"])
    ap.add_argument("--gguf", default=None)
    ap.add_argument("--fewshot", action="store_true")
    ap.add_argument("--raw-asr", action="store_true")
    ap.add_argument("--no-punct", action="store_true", help="rule-based casing only (no Gemma punctuation pass)")
    ap.add_argument("--bs", type=int, default=16)
    ap.add_argument("--comet", action="store_true")
    ap.add_argument("--tag", default="")
    a = ap.parse_args()

    src, tgt, _ = PAIRS[a.pair]
    samples = load_pair(a.pair)
    if a.input == "asr":
        asr = json.loads(Path(f"results/components/asr/asr_{a.pair}_{a.asr}.json").read_text())
        hyp_by_id = {r["id"]: r["hyp"] for r in asr["rows"]}
        samples = [s for s in samples if s.id in hyp_by_id]
    if a.backend == "hf":
        from cabin.mt import HFTranslator
        mt = HFTranslator()
    else:
        from cabin.mt import LlamaTranslator
        mt = LlamaTranslator(a.gguf)

    if a.input == "asr":
        from cabin.mt import restore_punctuation
        inputs = [hyp_by_id[s.id] if a.raw_asr else
                  (prep_asr_text(hyp_by_id[s.id], src) if a.no_punct else restore_punctuation(mt, hyp_by_id[s.id], src))
                  for s in samples]
    else:
        inputs = [s.src for s in samples]

    t0 = time.time()
    hyps = []
    for i in range(0, len(inputs), a.bs):
        hyps += mt.translate_batch(inputs[i:i + a.bs], src, tgt, fewshot=a.fewshot)
    dt = time.time() - t0

    refs = [s.ref for s in samples]
    res = {"pair": a.pair, "input": a.input, "asr": a.asr, "backend": a.backend, "n": len(hyps),
           **score(hyps, refs, tgt), "sec_per_sent": round(dt / len(hyps), 3)}
    if a.comet:
        res["comet"] = comet_score([s.src for s in samples], hyps, refs)
    print(json.dumps(res, ensure_ascii=False))
    name = f"results/components/mt/mt_{a.pair}_{a.input}{'_' + a.asr if a.asr else ''}_{a.backend}{a.tag}.json"
    rows = [{"id": s.id, "src": x, "ref": s.ref, "hyp": h} for s, x, h in zip(samples, inputs, hyps)]
    Path(name).write_text(json.dumps({"summary": res, "rows": rows}, ensure_ascii=False, indent=1))
    for r in rows[:6]:
        print(r)


if __name__ == "__main__":
    main()
