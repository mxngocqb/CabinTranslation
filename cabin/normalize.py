"""Text normalization matching the organizer's "normalized" style:
lowercase, no punctuation, numbers spelled out as words."""
from __future__ import annotations

import re
import unicodedata

try:
    from num2words import num2words
except ImportError:  # pragma: no cover
    num2words = None

_PUNCT = re.compile(r"[^\w\s']", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")
_NUM = re.compile(r"\d+(?:[.,]\d+)?")


def _spell_numbers(text: str, lang: str) -> str:
    if num2words is None:
        return text

    def rep(m: re.Match) -> str:
        tok = m.group(0)
        try:
            if lang == "vi":
                # Vietnamese uses '.' as thousands separator, ',' as decimal
                t = tok.replace(".", "")
                if "," in t:
                    a, b = t.split(",", 1)
                    return f"{num2words(int(a), lang='vi')} phẩy {' '.join(num2words(int(c), lang='vi') for c in b)}"
                return num2words(int(t), lang="vi")
            if lang == "en":
                t = tok.replace(",", "")
                return num2words(float(t) if "." in t else int(t), lang="en").replace("-", " ").replace(",", "")
        except Exception:
            return tok
        return tok

    return _NUM.sub(rep, text)


_EN_CONTRACTIONS = [
    (r"\bwon't\b", "will not"), (r"\bcan't\b", "can not"), (r"\bcannot\b", "can not"),
    (r"\bshan't\b", "shall not"), (r"\bain't\b", "is not"), (r"\blet's\b", "let us"),
    (r"\b(\w+)n't\b", r"\1 not"), (r"\b(\w+)'re\b", r"\1 are"), (r"\b(\w+)'ve\b", r"\1 have"),
    (r"\b(\w+)'ll\b", r"\1 will"), (r"\b(\w+)'d\b", r"\1 would"), (r"\bi'm\b", "i am"),
    (r"\b(it|that|there|here|what|where|who|how|he|she)'s\b", r"\1 is"),
    (r"\balright\b", "all right"), (r"\bok\b", "okay"), (r"\bgonna\b", "going to"),
    (r"\bwanna\b", "want to"),
]
_EN_FILLERS = re.compile(r"\b(um+|uh+|erm|er|hmm+|mm+|ah)\b")


def expand_en(text: str) -> str:
    text = text.replace("’", "'")
    for p, r in _EN_CONTRACTIONS:
        text = re.sub(p, r, text)
    return text


def normalize(text: str, lang: str = "vi", drop_fillers: bool = False) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.lower()
    if lang == "en":
        text = expand_en(text)
        if drop_fillers:
            text = _EN_FILLERS.sub(" ", text)
    if lang in ("vi", "en"):
        text = text.replace("%", " phần trăm " if lang == "vi" else " percent ")
        text = _spell_numbers(text, lang)
    if lang in ("zh", "ko", "ja"):
        text = re.sub(r"[^\w\s]", " ", text)
    else:
        text = _PUNCT.sub(" ", text)
        if lang == "vi":
            text = text.replace("'", " ")
    return _SPACES.sub(" ", text).strip()


# ---------------------------------------------------------------------------
# ASR output -> MT input: ASR emits UPPERCASE text without punctuation, which
# hurts the LLM translator badly (BLEU 53 -> 35). Restore casing + '?' cheaply.
_VI_Q_END = ("không", "chưa", "à", "hả", "nhỉ", "nhé chứ", "chứ", "sao", "đâu", "gì", "nào", "ạ không",
             "được không", "phải không", "đúng không", "bao giờ", "bao lâu", "bao nhiêu", "mấy giờ", "ai")
_VI_Q_ANY = ("bao nhiêu", "bao lâu", "bao giờ", "tại sao", "vì sao", "làm sao", "thế nào", "như thế nào",
             "có phải", "ở đâu", "cái gì", "là gì", "mấy", "khi nào", "đi đâu", "có ai")
_EN_Q_START = ("what", "where", "when", "why", "who", "whom", "whose", "which", "how", "is", "are", "am",
               "was", "were", "do", "does", "did", "can", "could", "will", "would", "shall", "should",
               "may", "might", "have", "has", "had")


def prep_asr_text(text: str, lang: str) -> str:
    t = _SPACES.sub(" ", (text or "").strip())
    if not t:
        return t
    if lang in ("vi", "en"):
        if not t.isupper():  # already cased/punctuated (e.g. Parakeet) -> keep
            return t
        t = t.lower()
        if lang == "en":
            t = re.sub(r"\bi\b", "I", t)
            t = re.sub(r"\bi'(m|d|ll|ve)\b", r"I'\1", t)
        if t[-1] not in ".?!":
            q = False
            if lang == "vi":
                q = t.endswith(_VI_Q_END) or any(f" {k} " in f" {t} " for k in _VI_Q_ANY)
            else:
                q = t.split(" ", 1)[0] in _EN_Q_START
            t += "?" if q else "."
        t = t[0].upper() + t[1:]
    return t
