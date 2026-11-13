"""Quick prompt ablation for Gemma MT (GPU). Scores BLEU/chrF++/COMET on gold + ASR input.

python scripts/prompt_ablation.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import cabin.mt as mt  # noqa: E402
from cabin.data import PAIRS, load_pair  # noqa: E402
from cabin.normalize import prep_asr_text  # noqa: E402
from eval_mt import score  # noqa: E402
from score_all import comet  # noqa: E402

BASE = mt.SYSTEM
VARIANTS = {
    "base": BASE,
    "short": ("Translate the following spoken {src} into natural spoken {tgt}. "
              "Keep the full meaning, names and numbers. Output only the {tgt} translation."),
    "faithful": BASE.replace(
        "Translate it into natural, fluent spoken {tgt} that a native speaker would say in the same situation.",
        "Translate it faithfully and completely into natural spoken {tgt}, staying close to the original wording "
        "and sentence structure while sounding natural."),
    "interp_vi": BASE + ("\n- When translating into Vietnamese, keep discourse words (ừ, vâng, được rồi, à) "
                         "when the source has them (yeah, okay, well, so) and translate every clause."),
}
ASR_OF = {"vi-en": "vi-30m", "en-vi": "en-parakeet"}


def main():
    tr = mt.LlamaTranslator()
    table = []
    for pair in ["en-vi", "vi-en"]:
        src, tgt, _ = PAIRS[pair]
        samples = load_pair(pair)
        asr = {r["id"]: r["hyp"] for r in json.loads((ROOT / f"results/components/asr/asr_{pair}_{ASR_OF[pair]}.json").read_text())["rows"]}
        for name, sysp in VARIANTS.items():
            mt.SYSTEM = sysp
            for inp in ["gold", "asr"]:
                xs = [s.src if inp == "gold" else prep_asr_text(asr[s.id], src) for s in samples]
                hyps = [tr.translate(x, src, tgt) for x in xs]
                refs = [s.ref for s in samples]
                sc = score(hyps, refs, tgt)
                sc["comet"], _ = comet([s.src for s in samples], hyps, refs)
                row = {"pair": pair, "variant": name, "input": inp, **sc}
                table.append(row)
                print(json.dumps(row), flush=True)
    (ROOT / "results/components/mt/prompt_ablation.json").write_text(json.dumps(table, indent=1))


if __name__ == "__main__":
    main()
