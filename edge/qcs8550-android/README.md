# CabinTranslation on Qualcomm QCS8550 (Android) — on-device deployment

> Source: [`../engine/`](../engine) (shared with the VENTUNO Q build). Build: [`build.sh`](build.sh). Launch scripts:
> [`start.sh`](start.sh) / [`stop.sh`](stop.sh). Deploy/benchmark tools: [`../tools/`](../tools). Results: [`results/qcs8550/`](../../results/qcs8550).
> The installable Android app (APK) wrapping this engine is in [`../android-app/`](../android-app).
> **Vietnamese input uses one Gemma call** (`punct_pass: false`, lower-case + system-prompt note) since 2026-11-11.
> The results table below is from the earlier 2-call build and will be re-measured offline.

Everything runs on the device in one native process, `cabin_edge`. It needs no Python, no root and no network.

| Stage | Runtime on device | Model | Size |
|---|---|---|---|
| ASR vi | sherpa-onnx C API, CPU | hynt Zipformer-30M RNNT int8 | 29 MB |
| ASR en + zh | sherpa-onnx C API, CPU | X-ASR Zipformer zh-en punct int8 | 167 MB |
| ASR ko | sherpa-onnx C API, CPU | k2-fsa Zipformer Korean int8 | 73 MB |
| MT | **LiteRT-LM C API, GPU (Adreno 740)** | Gemma 4 E2B-it `gemma-4-E2B-it-gpu.litertlm`, context 384 tokens | 2.18 GB |
| TTS vi | ViFastTts Rust FFI (`libvifasttts_ffi.so`) + ONNX Runtime, CPU | Ngọc Huyền small | 82 MB |
| TTS en | sherpa-onnx 1.13.8 (built-in espeak-ng), CPU | Piper VITS en_US-lessac-medium | 79 MB |
| TTS ko | sherpa-onnx, CPU | Supertonic-2 int8 (5 flow steps) | 92 MB |
| TTS zh | sherpa-onnx, CPU | Matcha zh-baker + Vocos 22 kHz | 139 MB |

Device used: Tablet_Meeting, QCS8550 (`kalama`), Android 13, 16 GB RAM, 6 CPU cores online
(3×2.0 + 2×2.8 + 1×3.2 GHz), Adreno 740.

## Layout on the device (`/data/local/tmp/cabin`)

```
cabin_edge  config.json  prompts.json  start.sh  stop.sh
lib/   liblitert-lm.so  libsherpa-onnx-c-api.so (v1.13.8)  libonnxruntime.so (1.28.2)  libvifasttts_ffi.so
models/ …            web/index.html            out/ (logs, results)
```

## Build (host: Linux/WSL)

Prerequisites:
- Android NDK r27c
- Rust 1.99.1 with the `aarch64-linux-android` target
- `patchelf`
- Prebuilt packages:
  - LiteRT-LM C API v0.19.1 (`litert_lm_c_api-1.0.0.zip`)
  - sherpa-onnx **v1.13.8** `sherpa-onnx-v1.13.8-android.tar.bz2` plus its `c-api.h`. v2.x removed the built-in espeak-ng frontend, so Piper/Kitten would need an external phonemizer.
  - The ViFastTts repository (Rust workspace)

```bash
bash edge/qcs8550-android/build.sh               # -> edge/qcs8550-android/dist/{cabin_edge, lib/*.so}
python edge/tools/make_device_bundle.py --push   # writes config/prompts from cabin/*.py, pushes binary, libs, models, web UI
```

Non-obvious build fixes (both handled by `build.sh`):
- **Missing SONAME.** The prebuilt `liblitert-lm.so` has no SONAME, so bionic rejects its versioned symbols. `patchelf --set-soname` fixes it.
- **One ONNX Runtime for both libraries.** sherpa-onnx's Android ORT is 1.28.2 and its symbols are versioned (`OrtGetApiBase@VERS_1.28.2`). ViFastTts's `load-dynamic` ORT adapter is therefore built against `api-28` instead of `api-31`, so both share that single `libonnxruntime.so`.

## Run

```bash
# Interactive UI on the tablet (offline): starts the server and opens the browser at 127.0.0.1:8080
adb shell sh /data/local/tmp/cabin/start.sh            # optional arg: langs, default vi,en,ko,zh
adb shell sh /data/local/tmp/cabin/stop.sh

# Benchmark (host orchestrates; device runs everything). Disconnect Wi-Fi on the tablet first,
# and keep adb over USB.
python edge/tools/run_device_bench.py --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi
# -> results/qcs8550/device_bench_<ts>/{summary.md, summary.json, result.jsonl (raw device output),
#    device_stderr.log, meminfo_samples.json, wav/}
```

`cabin_edge` modes:
- `--manifest in.jsonl --out out.jsonl [--wav-dir d]`: batch mode. Tasks are `e2e`, `asr`, `mt` and `tts`. Per-item timings are in ms, and Gemma also reports TTFT, prefill and decode tokens/s.
- `--serve 8080 --langs vi,en`: HTTP server plus web UI. `POST /api/translate?src=vi&tgt=en` takes a PCM16 WAV body. `POST /api/text` takes JSON. `GET /api/health` reports status.

## Latency optimizations that were measured

- **System-prompt prefix cache.** One prefilled conversation is kept per prompt and cloned for each request. Cloning takes 1–3 ms. Gemma TTFT drops from about 280 ms to about 130 ms.
- **Context length 384 tokens.** The longest prompt is about 220 tokens and output is capped at 128.
- **No effect, so left off:**
  - Speculative decoding: this `.litertlm` has no drafter.
  - `gpu_decode_steps_per_sync`: only applies to the Artisan GPU backend.
  - Context 512 vs 384: RAM and speed unchanged.
- **Decode speed on Adreno 740 is about 30 tokens/s**, which makes it the dominant cost.
- **TTS quota of 500 ms for EN and KO** (`edge/tools/bench_device_tts.py`, 60 organizer sentences each, round-trip intelligibility via host ASR):

  | lang | model | mean / p95 ms | round-trip err |
  |---|---|---|---|
  | en | Supertonic-3, 5 steps (old) | 1153 / 1776 | WER 1.49% |
  | en | **Piper lessac-medium fp32 (chosen)** | **233 / 410** | **WER 1.12%** |
  | en | Piper amy-low int8 | 345 / 601 | WER 0.56% (16 kHz voice, less natural) |
  | en | Kitten micro / nano | 758 / 797 | WER 0.37 / 0.93% |
  | en | Supertonic-2, 5 steps | 390 / 589 | WER 6.53% |
  | ko | Supertonic-3, 5 steps (old) | 888 / 1315 | CER 4.35% |
  | ko | **Supertonic-2, 5 steps (chosen)** | **303 / 434** | CER 6.61% |
  | ko | Supertonic-3, 4 steps | 748 / 1133 | CER 9.57% |
  | ko | Mimic3 kss-low | 237 / 378 | CER 22.6% (rejected) |

  Piper int8 models are slower than fp32 on this CPU, because dynamic quantization is slow on ARM.
- **TTS stays at 2 CPU threads.**
  - 4 or 6 threads are slower because the little cores slow the others down.
  - The NNAPI EP falls back to CPU, and the XNNPACK EP is not in this ORT build.
  - Fewer Supertonic steps hurt intelligibility (EN with 3 steps: WER 6.0%), so we keep 5 steps.

## Results (full sample set, 905 utterances, `results/qcs8550/device_bench_20261111_161624`)

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR | punct | MT | TTS | total p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| VI→EN | 100 | WER 1.72 | 54.62 | 67.99 | 88.63 | 53.88 | 76 | 490 | 509 | 226 | 1.22 s / 2.00 s |
| EN→VI | 100 | WER 7.80 | 42.07 | 60.03 | 84.08 | 40.40 | 189 | – | 969 | 395 | 1.44 s / 2.46 s |
| VI→KO | 175 | WER 4.84 | 38.10 | 30.59 | 88.05 | 37.05 | 60 | 449 | 467 | 343 | 1.25 s / 2.06 s |
| KO→VI | 177 | CER 7.86 | 22.51 | 41.09 | 83.41 | 22.10 | 87 | – | 448 | 136 | 0.63 s / 1.09 s |
| VI→ZH | 176 | WER 12.38 | 55.09 | 39.39 | 91.24 | 51.52 | 79 | 612 | 497 | 318 | 1.33 s / 2.87 s |
| ZH→VI | 177 | CER 3.74 | 45.72 | 63.60 | 92.92 | 44.57 | 113 | – | 595 | 199 | 0.80 s / 1.70 s |

- Stage times are mean ms. BLEU for KO/ZH targets is character-level.
- Peak RSS is 4.25 GB with all 4 languages loaded; GPU (Graphics) is 841 MB.
- Gemma: TTFT about 120–150 ms, decode about 30.8 tokens/s.
- Measured with Wi-Fi on. Re-run with the network off for the official submission.
