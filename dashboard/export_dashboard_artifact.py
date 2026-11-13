"""Export the results dashboard as a claude.ai Artifact bundle (page + audio packs).

python dashboard/export_dashboard_artifact.py OUT_DIR
-> OUT_DIR/index.html (page content without doctype/html/head/body, per the Artifact page contract)
   OUT_DIR/audio/<pair>.json  {utterance id: {"src": b64 mp3, <run key>: b64 mp3, ...}}  (16 kHz mono VBR MP3)
   run keys come from data["sample_runs"] (qcs8550, vq_npu, vq_gpu, vq_cpu).
"""
import base64
import io
import json
import re
import sys
from pathlib import Path

import librosa
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"


def mp3_b64(path: Path) -> str | None:
    if not path.exists():
        return None
    y, sr = sf.read(str(path), dtype="float32", always_2d=True)
    y = y.mean(axis=1)
    if sr != 16000:
        y = librosa.resample(y, orig_sr=sr, target_sr=16000)
    b = io.BytesIO()
    sf.write(b, y, 16000, format="MP3", subtype="MPEG_LAYER_III", compression_level=0.6, bitrate_mode="VARIABLE")
    return base64.b64encode(b.getvalue()).decode()


def main():
    out = Path(sys.argv[1])
    (out / "audio").mkdir(parents=True, exist_ok=True)
    data = json.loads((ROOT / "dashboard" / "data.json").read_text())
    data["audio_bundle"] = True
    packs = {}
    for s in data["samples"]:
        e = {"src": mp3_b64((ROOT / "dashboard" / s["src_wav"]).resolve()) if s.get("src_wav") else None}
        for key, o in s["outs"].items():
            e[key] = mp3_b64((ROOT / "dashboard" / o["wav"]).resolve()) if o.get("wav") else None
            o["wav"] = None  # local paths are meaningless once published
        packs.setdefault(s["pair"], {})[s["id"]] = e
        s["src_wav"] = None
    total = 0
    for pair, pk in packs.items():
        f = out / "audio" / f"{pair}.json"
        f.write_text(json.dumps(pk))
        total += f.stat().st_size
        print(f"{pair}: {len(pk)} utterances, {f.stat().st_size / 1e6:.1f} MB")
    tpl = (ROOT / "dashboard" / "report_template.html").read_text()
    page = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False))
    # Artifact page contract: no doctype/html/head/body/meta charset/viewport of our own
    page = re.sub(r"<!doctype html>\s*|</?html[^>]*>\s*|</?head>\s*|</?body>\s*|<meta charset[^>]*>\s*|<meta name=\"viewport\"[^>]*>\s*",
                  "", page, flags=re.I)
    (out / "index.html").write_text(page)
    print(f"page {(out / 'index.html').stat().st_size / 1e6:.2f} MB, audio total {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
