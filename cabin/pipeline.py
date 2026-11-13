"""End-to-end voice-to-voice pipeline: ASR -> (text prep) -> Gemma MT -> TTS. Fully offline."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from cabin.asr import ASR, DEFAULT_ASR
from cabin.mt import LlamaTranslator
from cabin.normalize import prep_asr_text
from cabin.tts import build_tts


@dataclass
class Turn:
    src_lang: str
    tgt_lang: str
    asr_text: str
    mt_input: str
    translation: str
    audio: np.ndarray
    sample_rate: int
    timings: dict = field(default_factory=dict)


class VoiceTranslator:
    def __init__(self, langs=("vi", "en"), asr_override: dict | None = None, mt: LlamaTranslator | None = None):
        self.langs = tuple(langs)
        self.asr_names = {**DEFAULT_ASR, **(asr_override or {})}
        self.asr, self.tts = {}, {}
        for lang in self.langs:
            self.ensure_lang(lang, warm=False)
        self.mt = mt or LlamaTranslator()
        self.warmup()

    def ensure_lang(self, lang: str, warm: bool = True):
        """Load ASR/TTS for a language on first use (keeps RAM low when only one pair is active)."""
        if lang in self.asr:
            return
        name = self.asr_names[lang]
        # share one recognizer instance between languages that use the same model
        self.asr[lang] = next((a for a in self.asr.values() if a.name == name), None) or ASR(name)
        self.tts[lang] = build_tts(lang)
        if warm:
            self._warm(lang)

    def _warm(self, lang):
        self.asr[lang].transcribe(np.zeros(16000, dtype=np.float32))
        self.tts[lang].synthesize({"vi": "xin chào", "ko": "안녕하세요", "zh": "你好"}.get(lang, "hello"))

    def warmup(self):
        for lang in self.asr:
            self._warm(lang)
        self.mt.translate("xin chào", "vi", self.langs[1] if self.langs[0] == "vi" else self.langs[0])

    def recognize(self, audio: np.ndarray, lang: str) -> str:
        return self.asr[lang].transcribe(audio)

    def translate_text(self, text: str, src: str, tgt: str, lower_input: bool = False) -> str:
        return self.mt.translate(text, src, tgt, lower_input=lower_input)

    def __call__(self, audio: np.ndarray, src: str, tgt: str, sr: int = 16000, speak: bool = True) -> Turn:
        self.ensure_lang(src)
        self.ensure_lang(tgt)
        if sr != 16000:
            import librosa
            audio = librosa.resample(audio, orig_sr=sr, target_sr=16000)
        t = {"audio_s": round(len(audio) / 16000, 2)}
        t0 = time.perf_counter()
        asr_text = self.recognize(audio, src)
        t["asr_s"] = round(time.perf_counter() - t0, 3)
        t1 = time.perf_counter()
        # no Gemma punctuation pass (matches the device default punct_pass: false): all-caps Vietnamese ASR ->
        # lowercase + rule casing/"?", translated in ONE call whose system prompt says the input is unpunctuated
        lower = src == "vi" and asr_text.isupper()
        mt_in = prep_asr_text(asr_text, src)
        tr = self.translate_text(mt_in, src, tgt, lower_input=lower) if mt_in else ""
        t["mt_s"] = round(time.perf_counter() - t1, 3)
        wav, out_sr = np.zeros(0, dtype=np.float32), 16000
        if speak and tr:
            t2 = time.perf_counter()
            wav, out_sr = self.tts[tgt].synthesize(tr)
            t["tts_s"] = round(time.perf_counter() - t2, 3)
        t["total_s"] = round(time.perf_counter() - t0, 3)
        return Turn(src, tgt, asr_text, mt_in, tr, wav, out_sr, t)
