"""On-device TTS.

Vietnamese : ViFastTts (N0 Ngoc Huyen small, ONNX, 24 kHz)
English    : sherpa-onnx VITS / Piper (en_US)
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
MODELS = Path(os.environ.get("CABIN_MODELS", ROOT / "models"))


class ViFastTTS:
    """Keeps acoustic + vocoder sessions resident (the upstream helper reloads per call)."""

    def __init__(self, model_dir: Path | None = None, provider: str = "cpu", dialect: str = "north"):
        from vifasttts.frontend.normalizer import NormalizerOptions
        from vifasttts.runtime.onnx_engine import OnnxAcousticModel, OnnxVocoder

        d = Path(model_dir or MODELS / "vifasttts-ngochuyen-small") / "onnx"
        self.acoustic = OnnxAcousticModel(d / "acoustic.onnx", provider)
        self.vocoder = OnnxVocoder(d / "vocoder.onnx", provider=provider)
        self.sample_rate = int(self.vocoder.sample_rate or self.acoustic.metadata.get("sample_rate", 24000))
        self.dialect = dialect
        self.options = NormalizerOptions(dialect=dialect)
        self.is_v2 = self.acoustic.metadata.get("arch") == "v2_slot5"

    def iter_synthesize(self, text: str, speed: float = 1.0):
        from vifasttts.frontend.chunking import chunk_text, pause_seconds

        chunks = chunk_text(text, max_chars=400)
        for i, chunk in enumerate(chunks):
            feats = self.acoustic.features_from_text(chunk, dialect=self.dialect, options=self.options)
            out = self.acoustic.run(feats, speed=speed, gate_threshold=0.5) if self.is_v2 else self.acoustic.run(feats)
            yield self.vocoder.waveform(np.asarray(out["mel"])).astype(np.float32)
            if i < len(chunks) - 1:
                n = int(self.sample_rate * pause_seconds(chunk))
                if n:
                    yield np.zeros(n, dtype=np.float32)

    def synthesize(self, text: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        from vifasttts.runtime.postprocess import postprocess

        pieces = list(self.iter_synthesize(text, speed))
        if not pieces:
            return np.zeros(0, dtype=np.float32), self.sample_rate
        return postprocess(np.concatenate(pieces), self.sample_rate), self.sample_rate


class SherpaTTS:
    """Generic sherpa-onnx offline TTS (VITS/Piper, Kokoro, Matcha)."""

    def __init__(self, model_dir: Path, kind: str = "vits", num_threads: int = 2, sid: int = 0,
                 provider: str = "cpu"):
        import sherpa_onnx

        d = Path(model_dir)
        onnx = next(p for p in sorted(d.glob("*.onnx")))
        if kind == "vits":
            model = sherpa_onnx.OfflineTtsModelConfig(
                vits=sherpa_onnx.OfflineTtsVitsModelConfig(
                    model=str(onnx), tokens=str(d / "tokens.txt"),
                    data_dir=str(d / "espeak-ng-data") if (d / "espeak-ng-data").exists() else "",
                    lexicon=str(d / "lexicon.txt") if (d / "lexicon.txt").exists() else "",
                ),
                num_threads=num_threads, provider=provider,
            )
        elif kind == "kokoro":
            model = sherpa_onnx.OfflineTtsModelConfig(
                kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                    model=str(onnx), voices=str(d / "voices.bin"), tokens=str(d / "tokens.txt"),
                    data_dir=str(d / "espeak-ng-data"),
                    lexicon=",".join(str(p) for p in sorted(d.glob("lexicon*.txt"))),
                    dict_dir=str(d / "dict") if (d / "dict").exists() else "",
                ),
                num_threads=num_threads, provider=provider,
            )
        else:
            raise ValueError(kind)
        self.tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=model, max_num_sentences=2))
        self.sid = sid
        self.sample_rate = self.tts.sample_rate

    def synthesize(self, text: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        a = self.tts.generate(text, sid=self.sid, speed=speed)
        return np.asarray(a.samples, dtype=np.float32), a.sample_rate


class SupertonicTTS:
    """Supertonic-3 (31 languages incl. en/ko/ja), int8 ONNX, unicode frontend (no espeak)."""

    def __init__(self, lang: str, model_dir: Path | None = None, sid: int = 0, num_steps: int = 5,
                 num_threads: int = 2, provider: str = "cpu"):
        import sherpa_onnx

        d = Path(model_dir or MODELS / "sherpa-onnx-supertonic-3-tts-int8-2026-05-11")
        cfg = sherpa_onnx.OfflineTtsModelConfig(
            supertonic=sherpa_onnx.OfflineTtsSupertonicModelConfig(
                duration_predictor=str(d / "duration_predictor.int8.onnx"),
                text_encoder=str(d / "text_encoder.int8.onnx"),
                vector_estimator=str(d / "vector_estimator.int8.onnx"),
                vocoder=str(d / "vocoder.int8.onnx"),
                tts_json=str(d / "tts.json"),
                unicode_indexer=str(d / "unicode_indexer.bin"),
                voice_style=str(d / "voice.bin"),
            ),
            num_threads=num_threads, provider=provider,
        )
        self.tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=cfg))
        self.lang, self.sid, self.num_steps = lang, sid, num_steps
        self.sample_rate = self.tts.sample_rate

    def synthesize(self, text: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        import sherpa_onnx

        g = sherpa_onnx.GenerationConfig()
        g.sid, g.speed, g.num_steps = self.sid, speed, self.num_steps
        g.extra = {"lang": self.lang}
        a = self.tts.generate(text, g)
        return np.asarray(a.samples, dtype=np.float32), a.sample_rate


class MatchaZhTTS:
    """Chinese TTS: icefall Matcha zh-baker (lexicon + jieba, no espeak) + Vocos 22 kHz vocoder.
    Round-trip CER 3.75%, ~0.1 s/sentence on 2 CPU threads (Kokoro multi-lang: CER 4.8%, 3 s)."""

    def __init__(self, num_threads: int = 2, provider: str = "cpu"):
        import sherpa_onnx

        d = MODELS / "matcha-icefall-zh-baker"
        cfg = sherpa_onnx.OfflineTtsModelConfig(
            matcha=sherpa_onnx.OfflineTtsMatchaModelConfig(
                acoustic_model=str(d / "model-steps-3.onnx"), vocoder=str(MODELS / "vocos-22khz-univ.onnx"),
                lexicon=str(d / "lexicon.txt"), tokens=str(d / "tokens.txt"), dict_dir=str(d / "dict"),
            ),
            num_threads=num_threads, provider=provider,
        )
        fsts = ",".join(str(d / f) for f in ("phone.fst", "date.fst", "number.fst"))
        self.tts = sherpa_onnx.OfflineTts(sherpa_onnx.OfflineTtsConfig(model=cfg, rule_fsts=fsts, max_num_sentences=2))
        self.sample_rate = self.tts.sample_rate

    def synthesize(self, text: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        a = self.tts.generate(text, sid=0, speed=speed)
        return np.asarray(a.samples, dtype=np.float32), a.sample_rate


def build_tts(lang: str, provider: str = "cpu"):
    if lang == "vi":
        return ViFastTTS(provider=provider)
    if lang == "zh":
        return MatchaZhTTS(provider=provider)
    return SupertonicTTS(lang, provider=provider)
