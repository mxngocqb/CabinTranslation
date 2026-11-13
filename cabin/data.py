"""Loader for the organizer's sample dataset (xlsx + wav/<ID>.wav)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("CABIN_DATA", ROOT / "data" / "Round 3-Bộ dữ liệu mẫu"))

LANG_KEYS = {
    "vi": ["tiếng việt", "vietnamese"],
    "en": ["tiếng anh", "english"],
    "zh": ["tiếng trung", "chinese", "mandarin", "tiếng hoa"],
    "ko": ["tiếng hàn", "korean"],
}

# pair code -> (src, tgt, xlsx glob)
PAIRS = {
    "vi-en": ("vi", "en", "**/Vie-Eng/*.xlsx"),
    "en-vi": ("en", "vi", "**/Eng-Vie/*.xlsx"),
    "vi-zh": ("vi", "zh", "**/*V_to_M*.xlsx"),
    "zh-vi": ("zh", "vi", "**/*M_to_V*.xlsx"),
    "vi-ko": ("vi", "ko", "**/*V_to_K*.xlsx"),
    "ko-vi": ("ko", "vi", "**/*K_to_V*.xlsx"),
}


@dataclass
class Sample:
    id: str
    src: str
    ref: str
    wav: Path | None


def _find_col(cols, lang):
    for c in cols:
        lc = str(c).lower()
        if any(k in lc for k in LANG_KEYS[lang]):
            return c
    raise KeyError(f"no column for {lang} in {cols}")


FOLDER_NAMES = {"vi": "Vie", "en": "Eng", "ko": "Kor", "zh": "Man"}


def _load_folder_pair(pair: str, data_dir: Path) -> list[Sample] | None:
    """Layout used by the Vie-Kor set: <Lang>_text/<ID>.txt + <Lang>_voice/<ID>.wav."""
    src, tgt, _ = PAIRS[pair]
    s_name, t_name = FOLDER_NAMES[src], FOLDER_NAMES[tgt]
    for d in sorted(data_dir.glob("*/")):
        st, tt, sv = d / f"{s_name}_text", d / f"{t_name}_text", d / f"{s_name}_voice"
        if st.is_dir() and tt.is_dir() and sv.is_dir():
            out = []
            for f in sorted(sv.glob("*.wav")):
                a, b = st / f"{f.stem}.txt", tt / f"{f.stem}.txt"
                if a.exists() and b.exists():
                    out.append(Sample(f.stem, a.read_text(encoding="utf-8-sig").strip(),
                                      b.read_text(encoding="utf-8-sig").strip(), f))
            return out
    return None


def load_pair(pair: str, data_dir: Path = DATA) -> list[Sample]:
    src, tgt, pat = PAIRS[pair]
    folder = _load_folder_pair(pair, data_dir)
    if folder:
        return folder
    files = sorted(data_dir.glob(pat))
    if not files:
        raise FileNotFoundError(f"{pat} under {data_dir}")
    xlsx = files[0]
    df = pd.read_excel(xlsx)
    cs, ct = _find_col(df.columns, src), _find_col(df.columns, tgt)
    wavdir = xlsx.parent / "wav"
    out = []
    for _, r in df.iterrows():
        if pd.isna(r["ID"]):
            continue
        sid = str(r["ID"]).strip()
        w = wavdir / f"{sid}.wav"
        out.append(Sample(sid, str(r[cs]).strip(), str(r[ct]).strip(), w if w.exists() else None))
    return out
