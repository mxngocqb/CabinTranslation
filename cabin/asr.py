"""On-device ASR wrappers (sherpa-onnx, CPU, int8).

Vietnamese : hynt Zipformer-30M / 150M RNNT (6000h)
English    : NeMo Parakeet-TDT 0.6B v2 int8
Chinese/Ko : SenseVoice int8 (zh/en/ja/ko/yue)
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import sherpa_onnx
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
MODELS = Path(os.environ.get("CABIN_MODELS", ROOT / "models"))


_LOADED: list[str] = []  # files touched by the last build_recognizer() call (for size reporting)


def _first(d: Path, pattern: str) -> str:
    hits = sorted(d.glob(pattern))
    if not hits:
        raise FileNotFoundError(f"{pattern} not found in {d}")
    _LOADED.append(str(hits[0]))
    return str(hits[0])


def _p(path: Path) -> str:
    _LOADED.append(str(path))
    return str(path)


ASR_MODELS = {
    "vi-30m": "Zipformer-30M-RNNT-6000h",
    "vi-150m": "ZipFormer-150M-CR-CTC-RNNT-6000h",
    "en-parakeet": "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8",
    "en-parakeet-110m": "sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000",
    "sensevoice": "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09",  # broken with sherpa-onnx 2.0.1
    "ko-zipformer": "sherpa-onnx-zipformer-korean-2024-06-24",
    "xasr-zh-en": "sherpa-onnx-x-asr-zipformer-transducer-zh-en-punct-int8-2026-06-03",
    "en-gigaspeech": "sherpa-onnx-zipformer-gigaspeech-2023-12-12",
}

# English: 26 small models benchmarked on the organizer EN set (scripts/bench_en_asr.py, 2 CPU threads).
#   default  X-ASR zipformer zh-en punct int8 : 175 MB, WER 7.85%, 0.075 s, MT COMET 84.5 (Apache-2.0, ~1M h data)
#   lite     Zipformer GigaSpeech int8        :  74 MB, WER 9.53%, 0.051 s, MT COMET 83.9
#   quality  Parakeet-TDT 0.6B v2 int8        : 661 MB, WER 8.61%, 0.31 s,  MT COMET 84.6
DEFAULT_ASR = {"vi": "vi-30m", "en": "xasr-zh-en", "zh": "xasr-zh-en", "ko": "ko-zipformer"}
_PROFILE = os.environ.get("CABIN_PROFILE", "").lower()
if _PROFILE == "lite":
    DEFAULT_ASR["en"] = "en-gigaspeech"
elif _PROFILE == "quality":
    DEFAULT_ASR["en"] = "en-parakeet"


def build_recognizer(name: str, num_threads: int = 4, decoding: str = "greedy_search",
                     provider: str = "cpu") -> sherpa_onnx.OfflineRecognizer:
    d = MODELS / ASR_MODELS[name]
    _LOADED.clear()
    if name in ("ko-zipformer", "xasr-zh-en", "en-gigaspeech"):
        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=_first(d, "encoder-*.int8.onnx"),
            decoder=_first(d, "decoder-*[0-9].onnx"),
            joiner=_first(d, "joiner-*.int8.onnx"),
            tokens=_p(d / "tokens.txt"),
            num_threads=num_threads, sample_rate=16000, feature_dim=80,
            decoding_method="greedy_search", provider=provider,
        )
    if name.startswith("vi-"):
        # hynt repos ship tokens as config.json
        tokens = d / "tokens.txt"
        if not tokens.exists():
            tokens = d / "config.json"
        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=_first(d, "encoder-*.int8.onnx"),
            decoder=_first(d, "decoder-*[0-9].onnx"),
            joiner=_first(d, "joiner-*.int8.onnx"),
            tokens=_p(tokens),
            num_threads=num_threads,
            sample_rate=16000,
            feature_dim=80,
            decoding_method=decoding,
            max_active_paths=4,
            provider=provider,
        )
    if name.startswith("en-parakeet"):
        dec = d / "decoder.int8.onnx"
        return sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=_p(d / "encoder.int8.onnx"),
            decoder=_p(dec if dec.exists() else d / "decoder.onnx"),
            joiner=_p(d / "joiner.int8.onnx"),
            tokens=_p(d / "tokens.txt"),
            num_threads=num_threads,
            model_type="nemo_transducer",
            decoding_method="greedy_search",
            provider=provider,
        )
    if name == "sensevoice":
        return sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=_p(d / "model.int8.onnx"),
            tokens=_p(d / "tokens.txt"),
            num_threads=num_threads,
            use_itn=True,  # punctuation + casing helps the LLM translator
            language="auto",
            provider=provider,
        )
    raise ValueError(name)


def load_audio(path: str | os.PathLike, target_sr: int = 16000) -> np.ndarray:
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    audio = audio.mean(axis=1)
    if sr != target_sr:
        import librosa
        audio = librosa.resample(audio, orig_sr=sr, target_sr=target_sr)
    return np.ascontiguousarray(audio, dtype=np.float32)


class ASR:
    def __init__(self, name: str, **kw):
        self.name = name
        self.rec = build_recognizer(name, **kw)
        self.files = list(_LOADED)
        self.size_mb = round(sum(Path(f).stat().st_size for f in self.files) / 1e6, 1)

    def transcribe(self, audio: np.ndarray, sr: int = 16000) -> str:
        s = self.rec.create_stream()
        s.accept_waveform(sr, audio)
        self.rec.decode_stream(s)
        return s.result.text.strip()

    def transcribe_batch(self, audios: list[np.ndarray], sr: int = 16000) -> list[str]:
        streams = []
        for a in audios:
            s = self.rec.create_stream()
            s.accept_waveform(sr, a)
            streams.append(s)
        self.rec.decode_streams(streams)
        return [s.result.text.strip() for s in streams]
