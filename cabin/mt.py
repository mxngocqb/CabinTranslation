"""Machine translation with Gemma 4 E2B-it.

Backends:
  - "hf"    : transformers (GPU, used for fast offline evaluation / prompt tuning)
  - "llama" : llama.cpp GGUF via llama-cpp-python (on-device deployment, CPU/GPU)
"""
from __future__ import annotations

import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODELS = Path(os.environ.get("CABIN_MODELS", ROOT / "models"))

LANG_NAME = {"vi": "Vietnamese", "en": "English", "zh": "Simplified Chinese", "ko": "Korean"}

SYSTEM = (
    "You are a professional real-time interpreter in a voice translation device used by workers "
    "in factories, construction sites, warehouses, offices, clinics and customer-service calls. "
    "The input is a transcript of spoken {src}; it may lack punctuation, contain fillers "
    "(um, uh, ờ, à) or small recognition errors. Translate it into natural, fluent spoken {tgt} "
    "that a native speaker would say in the same situation. Rules:\n"
    "- Preserve the full meaning; do not add, explain, or omit information.\n"
    "- Keep names, brands, street names and product codes as they are.\n"
    "- Drop meaningless fillers and repetitions.\n"
    "- Keep the speaker's register (polite / casual) and the question/statement form.\n"
    "- Output ONLY the {tgt} translation, nothing else."
)

# Single-call alternative to the punctuation pass (config "punct_pass": false): measured on 451 VI utterances,
# COMET 88.27 vs 89.08 for the 2-call punctuation pass, but ~0.5 s faster on the QCS8550.
LOWERCASE_NOTE = ("\n- The input is an automatic transcript in lowercase with NO punctuation: infer sentence boundaries, "
                  "questions and proper names yourself, and write the {tgt} translation with normal capitalization and punctuation.")

STYLE_HINT = {
    "vi": " Use natural Vietnamese pronouns that fit the context (anh/chị/tôi/bạn).",
    "en": "",
    "zh": " Use Simplified Chinese characters.",
    "ko": " Use polite Korean (해요체/합니다체) unless the source is clearly casual.",
}

# few-shot examples (spoken style, not from the test set)
FEWSHOT = {
    ("vi", "en"): [
        ("máy số ba lại bị kẹt rồi anh qua xem giúp em với", "Machine number three is jammed again, can you come take a look?"),
        ("ờ hôm nay ca chiều có tăng ca không chị", "Is there overtime for the afternoon shift today?"),
    ],
    ("en", "vi"): [
        ("um could you move those pallets to bay four before lunch", "anh có thể chuyển mấy cái pallet đó sang khu bốn trước giờ ăn trưa được không"),
        ("your order has been shipped is there anything else i can help you with", "đơn hàng của anh đã được gửi đi anh còn cần tôi giúp gì nữa không"),
    ],
    ("vi", "zh"): [
        ("máy số ba lại bị kẹt rồi anh qua xem giúp em với", "三号机又卡住了，你过来帮我看一下吧。"),
    ],
    ("zh", "vi"): [
        ("请把这些箱子搬到二号仓库", "làm ơn chuyển những thùng này sang kho số hai"),
    ],
    ("vi", "ko"): [
        ("máy số ba lại bị kẹt rồi anh qua xem giúp em với", "3번 기계가 또 걸렸어요. 와서 좀 봐 주시겠어요?"),
    ],
    ("ko", "vi"): [
        ("이 상자들을 2번 창고로 옮겨 주세요", "làm ơn chuyển những thùng này sang kho số hai"),
    ],
}


def build_messages(text: str, src: str, tgt: str, fewshot: bool = False, lower_input: bool = False) -> list[dict]:
    sys_prompt = SYSTEM.format(src=LANG_NAME[src], tgt=LANG_NAME[tgt]) + STYLE_HINT[tgt]
    if lower_input:   # same prompt as the device builds' "system_lower" (punct_pass: false)
        sys_prompt += LOWERCASE_NOTE.format(tgt=LANG_NAME[tgt])
    msgs = [{"role": "system", "content": sys_prompt}]
    if fewshot:
        for s, t in FEWSHOT.get((src, tgt), []):
            msgs.append({"role": "user", "content": s})
            msgs.append({"role": "assistant", "content": t})
    msgs.append({"role": "user", "content": text})
    return msgs


def clean_output(out: str) -> str:
    out = re.sub(r"</?[a-zA-Z][a-zA-Z0-9]*>", "", out).strip()
    out = re.sub(r"^(translation|bản dịch|译文|번역)\s*[:：]\s*", "", out, flags=re.I)
    out = out.split("\n")[0].strip() if out.count("\n") and len(out.split("\n")[0]) > 3 else out
    out = re.sub(r"\b(anh|chị|ông|bà|bạn|em)\s*/\s*(anh|chị|ông|bà|bạn|em)\b", r"\1", out, flags=re.I)
    return out.strip().strip('"“”').strip()


class HFTranslator:
    def __init__(self, model_id: str = "google/gemma-4-E2B-it", device: str = "cuda", dtype: str = "bfloat16"):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.torch = torch
        self.tok = AutoTokenizer.from_pretrained(model_id)
        self.tok.padding_side = "left"
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id, dtype=getattr(torch, dtype), device_map=device
        ).eval()

    def _prompt(self, msgs):
        return self.tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
                                            enable_thinking=False)

    def translate_batch(self, texts: list[str], src: str, tgt: str, max_new_tokens: int = 160,
                        fewshot: bool = False) -> list[str]:
        idx = [i for i, t in enumerate(texts) if t.strip()]
        res = [""] * len(texts)
        if idx:
            for i, o in zip(idx, self._translate_batch([texts[i] for i in idx], src, tgt, max_new_tokens, fewshot)):
                res[i] = o
        return res

    def _translate_batch(self, texts, src, tgt, max_new_tokens, fewshot):
        prompts = [self._prompt(build_messages(t, src, tgt, fewshot)) for t in texts]
        enc = self.tok(prompts, return_tensors="pt", padding=True, add_special_tokens=False).to(self.model.device)
        with self.torch.inference_mode():
            out = self.model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False)
        gen = out[:, enc["input_ids"].shape[1]:]
        return [clean_output(self.tok.decode(g, skip_special_tokens=True)) for g in gen]

    def translate(self, text: str, src: str, tgt: str, **kw) -> str:
        return self.translate_batch([text], src, tgt, **kw)[0]

    def chat(self, messages, max_new_tokens: int = 160) -> str:
        prompt = self._prompt(messages)
        enc = self.tok(prompt, return_tensors="pt", add_special_tokens=False).to(self.model.device)
        with self.torch.inference_mode():
            out = self.model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=False)
        return self.tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)


class LlamaTranslator:
    def __init__(self, gguf: str | None = None, n_ctx: int = 2048, n_threads: int | None = None,
                 n_gpu_layers: int | None = None):
        from llama_cpp import Llama, llama_supports_gpu_offload

        # default: Q3_K_M (2.5 GB) — same quality as the 3.3 GB QAT Q4_0 on our dev set
        gguf = gguf or os.environ.get("CABIN_GGUF") or str(next((MODELS / "gemma-4-E2B-it-Q3_K_M").glob("*.gguf")))
        self.gguf = gguf
        if n_gpu_layers is None:  # GPU by default when available; CABIN_DEVICE=cpu forces CPU
            use_gpu = os.environ.get("CABIN_DEVICE", "auto") != "cpu" and llama_supports_gpu_offload()
            n_gpu_layers = -1 if use_gpu else 0
        self.device = "gpu" if n_gpu_layers else "cpu"
        self.llm = Llama(model_path=gguf, n_ctx=n_ctx, n_threads=n_threads or max(1, os.cpu_count() // 2),
                         n_gpu_layers=n_gpu_layers, flash_attn=True, use_mmap=n_gpu_layers == 0,
                         verbose=False)

    def translate(self, text: str, src: str, tgt: str, max_new_tokens: int = 160, fewshot: bool = False,
                  lower_input: bool = False) -> str:
        if not text.strip():
            return ""
        r = self.llm.create_chat_completion(messages=build_messages(text, src, tgt, fewshot, lower_input),
                                            max_tokens=max_new_tokens, temperature=0.0)
        return clean_output(r["choices"][0]["message"]["content"])

    def translate_batch(self, texts, src, tgt, **kw):
        return [self.translate(t, src, tgt, **kw) for t in texts]

    def chat(self, messages, max_new_tokens: int = 160) -> str:
        r = self.llm.create_chat_completion(messages=messages, max_tokens=max_new_tokens, temperature=0.0)
        return r["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# Punctuation restoration for unpunctuated ASR output (Vietnamese zipformer emits
# UPPERCASE without punctuation). Missing commas/sentence ends cost ~4 BLEU / 1.6 COMET;
# a cheap Gemma pass (~0.06 s on GPU) recovers most of it. Words are never allowed to change.
PUNCT_SYSTEM = {
    "vi": ("Bạn là công cụ thêm dấu câu cho bản ghi lời nói tiếng Việt. Chỉ thêm dấu câu (, . ? !) và viết hoa "
           "đúng chỗ; KHÔNG thay đổi, thêm hay bớt bất kỳ từ nào. Chỉ trả về câu đã thêm dấu."),
    "en": ("You restore punctuation and casing in English speech transcripts. Only add punctuation (, . ? !) and "
           "capitalization; do NOT change, add or remove any word. Output only the punctuated sentence."),
    # Korean zipformer drops word spacing (띄어쓰기); restore spacing + punctuation
    "ko": ("당신은 한국어 음성 인식 결과의 띄어쓰기와 문장 부호를 교정하는 도구입니다. 올바른 띄어쓰기와 문장 부호(, . ?)만 "
           "추가하고 글자는 절대 바꾸거나 추가·삭제하지 마세요. 교정된 문장만 출력하세요."),
}


def _needs_restore(text: str, lang: str) -> bool:
    # English (GigaSpeech zipformer is all-caps) was measured: no COMET gain (83.82 vs 83.93) -> rule-based only
    if lang == "vi":
        return text.isupper()
    # Korean spacing restoration was measured: no gain (COMET 82.9 -> 82.4), so it is disabled.
    return False


def _same_content(a: str, b: str, lang: str) -> bool:
    if lang == "ko":
        k = lambda s: re.sub(r"[^\w]", "", s)
        return k(a) == k(b)
    return _words(a) == _words(b)


def _words(s: str) -> list[str]:
    return re.sub(r"[^\w\s]", " ", s.lower()).split()


def restore_punctuation(translator, text: str, lang: str) -> str:
    from cabin.normalize import prep_asr_text

    text = (text or "").strip()
    if not text or lang not in PUNCT_SYSTEM or not _needs_restore(text, lang):
        return prep_asr_text(text, lang)
    low = text.lower()
    msgs = [{"role": "system", "content": PUNCT_SYSTEM[lang]}, {"role": "user", "content": low}]
    try:
        out = clean_output(translator.chat(msgs, max_new_tokens=len(low) * 2 + 16))
    except Exception:
        out = ""
    if out and _same_content(out, low, lang):
        return out[0].upper() + out[1:]
    return prep_asr_text(text, lang)  # fall back to the rule-based casing + '?' heuristic
