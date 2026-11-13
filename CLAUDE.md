# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

CabinTranslation is an **offline voice-to-voice interpreter** built for the OneVoice AI Challenge 2026,
Phase 3 prototype. The submission deadline is 2026-11-13. Organizer brief: `docs/1V_P3_Prototype_Brief.pdf`.

Supported pairs: VI⇄EN, VI⇄KO, VI⇄ZH (all six directions).

**Repo map** (details in `README.md`):
- `edge/engine/`: native engine source shared by all devices.
- `edge/qcs8550-android/`, `edge/ventunoq-linux/`, `edge/android-app/`: per-platform build and launch.
- `edge/tools/`: bundle, deploy and on-device benchmark.
- `cabin/` + `pc/`: Python core and the PC reference app.
- `scripts/`: component evals.
- `results/{qcs8550,ventunoq,pc,components,archive}/`: measured runs.
- `dashboard/`: generator and the generated page.
- `docs/`: brief and submission documents.

Judging weights:
- 45% voice-to-voice translation quality
- 20% on-device performance: model size, latency, peak RAM/VRAM
- 20% UX
- 15% demo package

Hard requirements: all inference on-device, no network calls at demo time, and a UI judges can operate.
**Every model or quantization choice is a quality-vs-size trade-off that was measured.** Rerun the evals before changing a default.

The user mandated these models. Do not swap them out:
- Vietnamese ASR: hynt Zipformer-30M RNNT
- Vietnamese TTS: ViFastTts
- MT: Gemma 4 E2B

Report BLEU, chrF++ **and** COMET. Use the GPU for the LLM when available.

## Environment

- Dev venv: `~/venvs/cabin` (Python 3.11, on the Linux filesystem). Activate it with `source ~/venvs/cabin/bin/activate`. `pc/install.sh` instead creates `./.venv` (PC reference).
- The repo sits on `/mnt/c` (WSL2), so file I/O is slow.
- **Run every script from the repo root.** Scripts read and write relative `results/` paths and import `cabin` via a `sys.path` insert.
- `results/` layout:
  - `qcs8550/` holds QCS8550 device runs (`device_bench_*`, `device_tts_*`).
  - `ventunoq/` holds VENTUNO Q runs (`ventunoq_<backend>_*`).
  - `pc/` holds PC end-to-end runs (`bench_*`).
  - `components/{asr,mt,tts}/` holds component evals. `eval_mt --input asr` reads `components/asr/asr_<pair>_<model>.json`.
  - `archive/` holds smoke-test, crashed and failed runs.
  - `dashboard/build_report.py` marks the latest complete 6-pair run of each device/backend as official.
- torch must come from the cu128 index. The default PyPI torch segfaults on this WSL driver. torch is only needed for COMET and the HF dev backend.
- `llama-cpp-python` 0.3.36 is built with CUDA against a conda CUDA 12.8 toolkit at `~/cuda128`. Rebuild command: `CUDACXX=~/cuda128/bin/nvcc CMAKE_ARGS="-DGGML_CUDA=on -DCMAKE_CUDA_ARCHITECTURES=89" uv pip install --reinstall --no-cache llama-cpp-python`.
- Running prebuilt llama.cpp release binaries is blocked in this environment.
- `models/` and `data/` are git-ignored. Fetch models with `python scripts/download_models.py [--all]`. Data is the organizer's sample set, under `data/Round 3-Bộ dữ liệu mẫu/`.

## Commands

There is no unit-test suite. The eval scripts on the organizer sample set serve as the tests.

```bash
bash pc/run.sh [en|ko|zh]                # PC Gradio UI on 127.0.0.1:7860 (python pc/app.py --partner en)
CABIN_DEVICE=cpu bash pc/run.sh          # force LLM onto CPU
CABIN_PROFILE=lite bash pc/run.sh        # English ASR = Zipformer GigaSpeech (74 MB) instead of X-ASR
CABIN_PROFILE=quality bash pc/run.sh     # English ASR = Parakeet 0.6B
CABIN_GGUF=<path.gguf> bash pc/run.sh    # alternative Gemma quant

python scripts/eval_asr.py --pair vi-en --model vi-30m          # WER/CER, writes results/components/asr/asr_<pair>_<model>.json
python scripts/eval_mt.py --pair vi-en --input gold             # MT from reference transcript
python scripts/eval_mt.py --pair vi-en --input asr --asr vi-30m # cascade; needs the asr_*.json above
python scripts/eval_tts.py --lang vi                            # round-trip TTS->ASR intelligibility
python scripts/score_all.py [results/components/mt/mt_*.json ...]  # adds COMET, rebuilds results/components/mt/scoreboard.md
python scripts/benchmark_e2e.py --pairs vi-en en-vi ko-vi [--n 10] [--no-comet]   # PC wav->wav benchmark -> results/pc/
python dashboard/build_report.py                                # rebuild results/README.md + dashboard/index.html (run after any benchmark)
bash dashboard/serve.sh                                         # http://localhost:8000/dashboard/ (serves repo root; audio playback)
python dashboard/export_dashboard_artifact.py <dir>             # page + MP3 audio packs for the claude.ai artifact https://claude.ai/artifact/NE7xKRac8TShYAtHLr6cu9
python scripts/bench_en_asr.py --threads 2 [--models ...]       # English ASR candidates; `auto:<dir>` infers type for models/en_candidates/<dir>
python scripts/prompt_ablation.py                               # MT system-prompt variants
```

Pair codes are defined in `cabin/data.py` `PAIRS`: `vi-en en-vi vi-zh zh-vi vi-ko ko-vi`. Use `--n` or `--models` for a quick single run.

## Architecture

Pipeline (`cabin/pipeline.py`, class `VoiceTranslator`):
**ASR → `prep_asr_text` (+ `lower_input` prompt for all-caps VI) → Gemma MT (one call) → TTS**, timed per stage.
- ASR and TTS for a language load lazily (`ensure_lang`). One Gemma instance is shared by all directions.
- `pc/app.py` (Gradio) and `scripts/benchmark_e2e.py` both drive this class. Change behaviour there, not in the callers.

- **`cabin/asr.py`**: sherpa-onnx int8 CPU recognizers, keyed by name in `ASR_MODELS`. `DEFAULT_ASR` maps each language to a model.
  - hynt repos ship `tokens.txt` as `config.json`.
  - English default is X-ASR zipformer zh-en (punctuated, Apache-2.0, also the intended ZH model), chosen from 26 benchmarked EN models (`results/components/asr/en_asr_candidates_t2.md`).
  - SenseVoice int8 produces garbage under sherpa-onnx 2.0.1. Korean therefore uses `ko-zipformer`. That model outputs text without word spacing, so score Korean with CER.
  - `ASR.files` / `ASR.size_mb` record exactly which files were loaded. The benchmark reports model size from them, so keep `_first()`/`_p()` wrapping any new paths.
- **`cabin/mt.py`**: two backends.
  - `LlamaTranslator` (llama.cpp GGUF) is the real and default one. It offloads to GPU when `llama_supports_gpu_offload()`, and uses mmap only on CPU.
  - `HFTranslator` (transformers) is dev-only. It emits stray `<h2>` tags under batched left-padding, so don't trust its numbers.
  - Prompting: one system prompt (`SYSTEM` + `STYLE_HINT[tgt]`). Few-shot is off by default because it was measured to give no gain. `clean_output` strips tags, labels and "anh/chị" slash-alternatives.
  - The default GGUF is `models/gemma-4-E2B-it-Q3_K_M/`. It scores the same as the QAT Q4_0 build and is 24% smaller. Q2 loses about 20 BLEU.
- **Vietnamese ASR text prep**: the Vietnamese ASR emits UPPERCASE text without punctuation, which wrecks MT if passed raw (BLEU 53 → 35).
  - Default, chosen by the user: `normalize.prep_asr_text` lowercases, capitalizes and adds `?` by heuristic, then ONE Gemma call with `build_messages(lower_input=True)`, which appends `LOWERCASE_NOTE`. This matches the device `punct_pass: false`.
  - Measured on 451 VI utterances: COMET 88.27 vs 89.08 for the 2-call path, about 0.5 s faster on the QCS8550.
  - `restore_punctuation` (in `mt.py`): the 2-call path, a Gemma pass that only adds punctuation, with output rejected unless the word sequence is unchanged. It is kept but unused by default. Device: `make_device_bundle.py --punct-pass`.
  - It only triggers for all-caps Vietnamese input. An English pass (for the all-caps GigaSpeech model) was measured, gave no gain, and is disabled.
  - Korean spacing restoration was tried, gave no gain, and is disabled in `_needs_restore`.
- **`cabin/tts.py`**: `ViFastTTS` for vi wraps the vendored `vifasttts` runtime and keeps the ONNX sessions resident. `SupertonicTTS` covers en and ko via `GenerationConfig.extra={"lang": ...}`. Supertonic has no zh, so `MatchaZhTTS` (Matcha zh-baker + `models/vocos-22khz-univ.onnx`) covers zh. Piper/VITS in sherpa-onnx 2.x has no espeak frontend, so it is not used.
- **`cabin/normalize.py`**: scoring normalization matching the organizer's "normalized" references: lowercase, no punctuation, numbers spelled out via num2words, English contractions expanded, optional filler removal. Both refs and hyps go through `normalize(..., drop_fillers=True)` before BLEU and WER.
- **`cabin/data.py`**: handles two dataset layouts.
  - VI-EN uses xlsx files with language-named columns plus `wav/<ID>.wav`.
  - VI-KO uses `<Lang>_text/<ID>.txt` plus `<Lang>_voice/<ID>.wav` (`Vie/Kor/Man`).
  - VI-ZH uses the same folder layout with `Man_*` folders.
  - Korean "wav" files are actually MP3. soundfile decodes them, but Gradio would need ffmpeg, which is why `pc/app.py` uses `type="filepath"`.
  - Some VI-KO reference pairs are misaligned in the organizer data.
- **`scripts/score_all.py`** monkeypatches COMET 2.2.7's `XLMREncoder.forward` for transformers 5. Its `comet()` helper is reused by other scripts.
- **`vendor/ViFastTts`**: pinned upstream source (see `UPSTREAM_COMMIT.txt`), installed with `pip install --no-deps ./vendor/ViFastTts`.

## Submission artifacts

- **Benchmark logs:** official runs must have the **network disconnected**. Never disconnect it from inside this session. The user forbade turning off the VENTUNO Q Wi-Fi: its runs are online, and they log the engine's non-loopback sockets (`net_conns`) as evidence instead.
- **Offline packages:** VENTUNO Q uses `edge/ventunoq-linux/package.sh` (run on the board). The PC uses `pc/make_wheelhouse.sh` + `pc/install.sh --offline` or `pc/Dockerfile`. Submission docs go in `docs/submission/`, and built packages go in `../CabinTranslation_submission/` (outside the repo).
- **Secrets:** `qdc_id_*.pem` in the repo root is a private key. It is git-ignored and must never go into a package.
- **Licenses (non-commercial):** hynt ASR is CC BY-NC-ND. The ViFastTts voice weights are CC BY-NC.

## On-device (Qualcomm QCS8550, Android) — `edge/qcs8550-android/`

- `edge/engine/cabin_edge.cc` is one native binary covering the whole pipeline:
  - LiteRT-LM C API (Gemma 4 E2B `gpu.litertlm`, GPU, context 384, cached system-prompt prefill)
  - sherpa-onnx **v1.13.8** C API for ASR/TTS on CPU. Do not upgrade to 2.x: it dropped the espeak frontend that Piper needs.
  - ViFastTts Rust FFI
- Build and deploy: `bash edge/qcs8550-android/build.sh`, then `python edge/tools/make_device_bundle.py --push`.
  - Device config and prompts are generated from `cabin/mt.py` and `cabin/normalize.py`.
  - Device: adb `10.5.14.32:5555`, path `/data/local/tmp/cabin`.
- Benchmarks: `python edge/tools/run_device_bench.py --pairs …` (end to end → `results/qcs8550/`) and `python edge/tools/bench_device_tts.py` (TTS candidates). `edge/qcs8550-android/README.md` has the device results and the measured choices.
- Device TTS choices (quota about 500 ms): EN uses Piper lessac-medium, KO uses Supertonic-2 with 5 steps. The PC (`cabin/tts.py`) still uses Supertonic-3 for EN/KO.
- Build gotchas: `liblitert-lm.so` needs `patchelf --set-soname`. ViFastTts's ORT adapter is built with `api-28` so it shares sherpa's ORT 1.28.2.

## Android app — `edge/android-app/`

- Native app `vn.cabin.translate` ("CabinTranslation"). Capture follows the official sherpa-onnx `vad-asr` sample: `AudioRecord` at 16 kHz plus Silero VAD, using the unchanged `Vad.kt` and `libsherpa-onnx-jni.so` v1.13.8.
- The app runs `cabin_edge` as a child process (`jniLibs/libcabin_edge.so`, serve mode on 127.0.0.1:18181).
- Build: `prepare.sh`, then Gradle 8.10.2 + JDK 17 (`~/jdk17`, `~/android-sdk`; build from a Linux-FS copy, e.g. `~/build/android-app`).
- Install: `install.sh` → `dist/CabinTranslation.apk`.
- Models must be in `/sdcard/CabinTranslation/models` with MANAGE_EXTERNAL_STORAGE granted (`appops`). Files that the shell creates under `Android/data/<pkg>` are owned by uid 2000 and are unreadable by the app.
- The browser UI (`edge/engine/web`) is kept as a fallback. Its capture uses an AudioWorklet (ScriptProcessor dropped samples) with pre-roll and post-roll.

## On-device (Arduino VENTUNO Q, QCS8275, Ubuntu 24.04 aarch64) — `edge/ventunoq-linux/`

- Same `cabin_edge.cc`, cross-compiled for glibc: `bash edge/ventunoq-linux/build.sh` → `cabin_edge` (LiteRT-LM 1.0 C API, CPU/GPU) and `cabin_edge_npu` (NPU runtime LiteRT-LM 0.18 via the `litert_lm_compat_018.cc` ABI shim).
- Deploy/bench over ssh: `python edge/tools/make_device_bundle.py --target linux --ssh "ssh -p 2222 arduino@localhost" --push`, then `python edge/tools/run_device_bench.py --target linux --ssh ... --backend cpu|gpu|npu`. Results go to `results/ventunoq/`.
- Launch: `sh ~/cabin/start.sh npu`. `HOST=0.0.0.0` exposes :8080 on the LAN. `HTTPS=1` adds `https_proxy.py` on :8443 (self-signed), because the microphone needs https or localhost.
- The board is a QDC device. SSH arrives over `end0` (192.168.5.2), and Wi-Fi (SSID QDC) is its only internet route.
- Configs use `./` paths, which the engine resolves against the config folder, so packages are relocatable.
- Do not `pkill -f <name>` over ssh with the name inside the same command line: it kills your own shell.
- Measured gotchas (details in `edge/ventunoq-linux/README.md`):
  - GPU (Vulkan/Turnip, Adreno 623) needs `-gpu.litertlm`. CPU needs the generic `.litertlm`, ctx ≥ 1024, sampler `topk1` (TOP_P with k=1; GREEDY/TOP_K are unimplemented on CPU), and `prefix_cache: false` (clone is broken).
  - NPU needs the QAIRT 2.50 libs in `~/cabin/lib_npu` (apt 2.49 is rejected) and `prefix_cache: false`.
- Vietnamese ASR input now uses a single Gemma call on all device configs (`punct_pass: false` + `LOWERCASE_NOTE`). `--punct-pass` restores the 2-call path.

## On-device (Qualcomm IQ-9075 EVK, QCS9075, Qualcomm Linux 1.9) — same `edge/ventunoq-linux` build

- The binaries are unchanged. Deploy with `--ssh "ssh -p 2222 root@localhost" --dev-dir /root/cabin`. Benchmark with `--device-tag iq9075`, which writes `results/iq9075/`.
- GPU: KGSL + Qualcomm Vulkan, Adreno 663, about 15.7 tok/s.
- CPU: 8 big cores, so use `--mt-threads 8` (about 32 tok/s, the fastest MT here).
- NPU is blocked. A self-compiled QCS9075 build exists (`edge/tools/compile_npu_model.sh`, `~/edge/models/gemma-4-E2B-it_Qualcomm_QCS9075.litertlm`): it loads, but its 1.66 GB weight buffer cannot be FastRPC-mapped. On v73 the int4 weights are expanded (761 MB on v75).
- The image is minimal: no `ss`, `ldd` or Python `statistics`. Device scripts must use only basic Python and coreutils.

