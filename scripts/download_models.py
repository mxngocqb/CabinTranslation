"""Download every model used by CabinTranslation into ./models (run ONCE while online).

python scripts/download_models.py [--all]   # --all also fetches optional/alternative models
"""
import argparse
import tarfile
import urllib.request
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download

M = Path(__file__).resolve().parent.parent / "models"

HF = {
    # ASR
    "Zipformer-30M-RNNT-6000h": ("hynt/Zipformer-30M-RNNT-6000h",
                                 ["*.int8.onnx", "decoder-*[0-9].onnx", "bpe.model", "config.json", "README.md"]),
    # English ASR (default): fp32 export, quantized to int8 below
    "sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000": (
        "csukuangfj/sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000", ["*.onnx", "tokens.txt"]),
    "sherpa-onnx-zipformer-korean-2024-06-24": ("k2-fsa/sherpa-onnx-zipformer-korean-2024-06-24",
                                                ["*.int8.onnx", "decoder-*[0-9].onnx", "tokens.txt", "README.md"]),
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09": (
        "csukuangfj/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09", ["*.onnx", "tokens.txt", "README.md"]),
    # TTS
    "vifasttts-ngochuyen-small": ("dvchd/vifasttts-ngochuyen-small", ["onnx/*", "config.yaml", "README.md"]),
}
HF_OPTIONAL = {
    "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8": ("csukuangfj/sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8",
                                                   ["*.onnx", "tokens.txt", "README.md"]),  # CABIN_PROFILE=quality
    "ZipFormer-150M-CR-CTC-RNNT-6000h": ("hynt/ZipFormer-150M-CR-CTC-RNNT-6000h",
                                         ["*.int8.onnx", "decoder-*[0-9].onnx", "bpe.model", "config.json"]),
}
GGUF = {
    "gemma-4-E2B-it-Q3_K_M": ("unsloth/gemma-4-E2B-it-GGUF", "gemma-4-E2B-it-Q3_K_M.gguf"),
}
GGUF_OPTIONAL = {
    "gemma-4-E2B-it-qat-q4_0": ("google/gemma-4-E2B-it-qat-q4_0-gguf", "gemma-4-E2B_q4_0-it.gguf"),
}
TARBALLS = {
    # Chinese TTS (Matcha zh-baker) + its Vocos vocoder
    "matcha-icefall-zh-baker":
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/matcha-icefall-zh-baker.tar.bz2",
    # English (+Chinese) ASR default: X-ASR zipformer zh-en with punctuation/casing (Apache-2.0)
    "sherpa-onnx-x-asr-zipformer-transducer-zh-en-punct-int8-2026-06-03":
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-x-asr-zipformer-transducer-zh-en-punct-int8-2026-06-03.tar.bz2",
    # English ASR, CABIN_PROFILE=lite
    "sherpa-onnx-zipformer-gigaspeech-2023-12-12":
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-zipformer-gigaspeech-2023-12-12.tar.bz2",
    "sherpa-onnx-supertonic-3-tts-int8-2026-05-11":
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
        "sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    M.mkdir(exist_ok=True)
    hf = {**HF, **(HF_OPTIONAL if a.all else {})}
    for name, (repo, pats) in hf.items():
        print("->", repo)
        snapshot_download(repo, local_dir=M / name, allow_patterns=pats)
    for name, (repo, fn) in {**GGUF, **(GGUF_OPTIONAL if a.all else {})}.items():
        print("->", repo, fn)
        hf_hub_download(repo, fn, local_dir=M / name)
    for name, url in TARBALLS.items():
        if (M / name).exists():
            continue
        print("->", url)
        tmp = M / (name + ".tar.bz2")
        urllib.request.urlretrieve(url, tmp)
        with tarfile.open(tmp) as t:
            t.extractall(M, filter="data")
        tmp.unlink()
    voc = M / "vocos-22khz-univ.onnx"
    if not voc.exists():
        print("-> vocos-22khz-univ.onnx")
        urllib.request.urlretrieve("https://github.com/k2-fsa/sherpa-onnx/releases/download/vocoder-models/"
                                   "vocos-22khz-univ.onnx", voc)
    # int8-quantize Parakeet 110M (dynamic QUInt8: WER 9.58% vs fp32 9.42%); only *.int8.onnx are loaded at runtime
    from onnxruntime.quantization import QuantType, quantize_dynamic
    d = M / "sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000"
    for n in ("encoder", "decoder", "joiner"):
        if not (d / f"{n}.int8.onnx").exists():
            print("-> quantize", n)
            quantize_dynamic(str(d / f"{n}.onnx"), str(d / f"{n}.int8.onnx"), weight_type=QuantType.QUInt8)
    print("All models in", M)


if __name__ == "__main__":
    main()
