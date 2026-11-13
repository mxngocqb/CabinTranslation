"""Re-score every results/components/mt/mt_*.json with BLEU, chrF++ and COMET (wmt22-comet-da).

python scripts/score_all.py [results/components/mt/mt_*.json ...]
Writes results/scoreboard.md and updates each json's summary.
"""
import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cabin.data import PAIRS, load_pair  # noqa: E402
from eval_mt import score  # noqa: E402

_comet = None


def _patch_comet_for_transformers5():
    """COMET 2.2.x unpacks a 3-tuple from XLM-R; transformers>=5 returns a ModelOutput."""
    from comet.encoders.xlmr import XLMREncoder

    def forward(self, input_ids, attention_mask, **kwargs):
        out = self.model(input_ids=input_ids, attention_mask=attention_mask,
                         output_hidden_states=True, return_dict=True)
        h = out.last_hidden_state
        return {"sentemb": h[:, 0, :], "wordemb": h, "all_layers": out.hidden_states,
                "attention_mask": attention_mask}

    XLMREncoder.forward = forward


def comet(srcs, hyps, refs):
    global _comet
    from comet import download_model, load_from_checkpoint
    if _comet is None:
        _patch_comet_for_transformers5()
        _comet = load_from_checkpoint(download_model("Unbabel/wmt22-comet-da"))
    data = [{"src": s, "mt": h, "ref": r} for s, h, r in zip(srcs, hyps, refs)]
    out = _comet.predict(data, batch_size=64, gpus=1, progress_bar=False)
    return round(out.system_score * 100, 2), [round(x * 100, 1) for x in out.scores]


def main():
    files = sys.argv[1:] or sorted(glob.glob("results/components/mt/mt_*.json"))
    rows_md = []
    for f in files:
        d = json.loads(Path(f).read_text())
        s = d["summary"]
        tgt = PAIRS[s["pair"]][1]
        gold_src = {x.id: x.src for x in load_pair(s["pair"])}
        rows = d["rows"]
        hyps, refs = [r["hyp"] for r in rows], [r["ref"] for r in rows]
        srcs = [gold_src.get(r["id"], r["src"]) for r in rows]  # COMET always sees the true source
        s.update(score(hyps, refs, tgt))
        s["comet"], per = comet(srcs, hyps, refs)
        for r, c in zip(rows, per):
            r["comet"] = c
        Path(f).write_text(json.dumps(d, ensure_ascii=False, indent=1))
        name = Path(f).stem.removeprefix("mt_")
        rows_md.append(f"| {name} | {s['pair']} | {s['input']}{'/' + s['asr'] if s.get('asr') else ''} | "
                       f"{s['bleu']} | {s['chrf++']} | {s['comet']} | {s.get('sec_per_sent', '')} |")
        print(rows_md[-1], flush=True)
    rows_md = []
    for f in sorted(glob.glob("results/components/mt/mt_*.json")):
        s = json.loads(Path(f).read_text())["summary"]
        if "comet" not in s:
            continue
        rows_md.append(f"| {Path(f).stem.removeprefix('mt_')} | {s['pair']} | {s['input']}"
                       f"{'/' + s['asr'] if s.get('asr') else ''} | {s['bleu']} | {s['chrf++']} | "
                       f"{s['comet']} | {s.get('sec_per_sent', '')} |")
    md = ["| run | pair | input | BLEU | chrF++ | COMET | s/sent |", "|---|---|---|---|---|---|---|"] + rows_md
    Path("results/components/mt/scoreboard.md").write_text("\n".join(md) + "\n")


if __name__ == "__main__":
    main()
