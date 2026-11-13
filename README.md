# CabinTranslation — offline voice-to-voice interpreter on Qualcomm edge devices

Two-way speech-to-speech interpreter for workers in factories, warehouses and construction sites.
**Vietnamese ⇄ English, Vietnamese ⇄ Korean and Vietnamese ⇄ Chinese** (all six directions).
Recognition, translation and speech synthesis **all run on the device**, and inference makes no cloud or API calls.
OneVoice AI Challenge 2026, Phase 3 prototype.

```
 mic ─► ASR (sherpa-onnx, CPU) ─► text prep ─► Gemma 4 E2B translation (GPU / NPU / CPU) ─► TTS (ONNX, CPU) ─► speaker
        └──────────── one native process on the device (cabin_edge): HTTP server + touch web UI ─────────────┘
```

| Device build | LLM runs on | End-to-end latency p50 (speech in → speech out) | COMET (6-direction mean) |
|---|---|---|---|
| **Qualcomm QCS8550 tablet** (Android 13) | Adreno 740 GPU | 0.63–1.44 s | 88.1 ¹ |
| **Arduino VENTUNO Q** (QCS8275, Ubuntu 24.04) | **Hexagon v75 NPU** | **0.54–1.21 s** | 87.5 |
| Arduino VENTUNO Q | Adreno 623 GPU / CPU | 1.98–4.48 s / 2.09–3.76 s | 87.5 / 87.4 |

¹ Earlier 2-call Vietnamese build. Sample set: organizer Round 3 sample (905 utterances).
All runs above were measured with the network connected. During the VENTUNO Q NPU run the engine opened
**no** non-loopback network socket (sampled every second over the 905 utterances). See [results/README.md](results/README.md).

## Repository map

```
CabinTranslation/
├── edge/                       ── SUBMITTED DEVICE BUILDS ─────────────────────────────────────────
│   ├── engine/                 native engine shared by every device: cabin_edge.cc, LiteRT-LM 0.18 ABI shim, web UI
│   ├── qcs8550-android/        build + launch for the QCS8550 tablet (Android, Gemma on GPU)
│   ├── ventunoq-linux/         build + launch + offline package for Arduino VENTUNO Q (Linux, Gemma on NPU/GPU/CPU)
│   ├── android-app/            installable Android app (APK) wrapping the same engine, with Silero VAD
│   └── tools/                  generate configs/prompts, deploy (adb/ssh), on-device benchmarks
├── cabin/                      Python core: prompts (source of truth for the devices), normalization, data loaders, PC pipeline
├── pc/                         PC reference app (Gradio): install, run, Dockerfile
├── scripts/                    component evaluations: ASR / MT / TTS, COMET scoring, PC end-to-end benchmark
├── results/                    measured results, one folder per scenario
│   ├── qcs8550/                on-device runs on the QCS8550 tablet
│   ├── ventunoq/               on-device runs on VENTUNO Q (cpu / gpu / npu)
│   ├── pc/                     PC reference runs
│   ├── components/             model comparisons (26 English ASR models, Gemma quants, prompts, TTS)
│   └── archive/                smoke tests, aborted or failed runs (kept for traceability)
├── dashboard/                  results dashboard: generator, template, generated index.html
├── docs/                       organizer brief, submission documents, demo scenario
├── vendor/ViFastTts/           pinned Vietnamese TTS runtime (Python, PC only)
└── models/, data/              downloaded weights and the organizer sample set (not in git)
```

## Which folder do I need?

| I want to… | Go to |
|---|---|
| Run the interpreter on the QCS8550 tablet | [edge/qcs8550-android/README.md](edge/qcs8550-android/README.md) |
| Run it on Arduino VENTUNO Q (NPU), or install the judges' offline package | [edge/ventunoq-linux/README.md](edge/ventunoq-linux/README.md) and [package/README_INSTALL.md](edge/ventunoq-linux/package/README_INSTALL.md) |
| Install the Android app (APK) | [edge/android-app/README.md](edge/android-app/README.md) |
| Understand the native engine or the deploy/benchmark tools | [edge/README.md](edge/README.md) |
| Run the PC reference or the component evaluations | [pc/README.md](pc/README.md) |
| See every measured number, the logs and the audio | [results/README.md](results/README.md) · `bash dashboard/serve.sh` → http://localhost:8000/dashboard/ |

## Quick start

**VENTUNO Q (Hexagon NPU)**, using the offline package:
```bash
tar -xf CabinTranslation-VentunoQ-v1.0.tar && cd CabinTranslation-VentunoQ-v1.0
tar -xf ../qairt-2.50-libs.tar -C lib_npu && sh check.sh     # -> CHECK PASSED
sh start.sh npu                                               # open http://127.0.0.1:8080/ (Firefox on the board)
```

**QCS8550 tablet (Android)**, from a host with adb:
```bash
bash edge/qcs8550-android/build.sh && python edge/tools/make_device_bundle.py --push
adb shell sh /data/local/tmp/cabin/start.sh                    # opens the UI in the tablet browser
```

**Use:** pick the partner language (EN / KO / ZH). Each speaker holds their 🎤 button and speaks.
The translation is shown, spoken aloud, and timed per stage (ASR / MT / TTS).

## Models (device builds)

| Stage | Language | Model | Runtime |
|---|---|---|---|
| ASR | Vietnamese | hynt Zipformer-30M-RNNT-6000h, int8 (29 MB) | sherpa-onnx 1.13.8, CPU |
| ASR | English, Chinese | X-ASR Zipformer zh-en punct, int8 (167 MB) | sherpa-onnx, CPU |
| ASR | Korean | k2-fsa Zipformer Korean, int8 (73 MB) | sherpa-onnx, CPU |
| MT | all | Google Gemma 4 E2B-it, LiteRT-LM builds: `-gpu` (2.34 GB), `QCS8275` NPU (2.72 GB), generic CPU (2.59 GB) | LiteRT-LM (GPU: ML Drift; NPU: QNN/QAIRT 2.50; CPU: XNNPACK) |
| TTS | Vietnamese | ViFastTts Ngọc Huyền small (82 MB) | ViFastTts Rust FFI + ONNX Runtime 1.28.2, CPU |
| TTS | English | Piper VITS en_US-lessac-medium (79 MB) | sherpa-onnx (espeak-ng), CPU |
| TTS | Korean | Supertonic-2 int8, 5 steps (92 MB) | sherpa-onnx, CPU |
| TTS | Chinese | Matcha zh-baker + Vocos 22 kHz (139 MB) | sherpa-onnx, CPU |

Vietnamese ASR output (upper case, unpunctuated) is lower-cased, given a rule-based `?`/`.`, and translated in
**one** Gemma call whose system prompt says the input is an unpunctuated transcript. Every choice above was measured
on the organizer sample set. The reasons are in each platform README and in [pc/README.md](pc/README.md).

## Reproduce the measurements

```bash
python edge/tools/run_device_bench.py --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi                       # QCS8550 (adb)
python edge/tools/run_device_bench.py --target linux --ssh "ssh -p 2222 arduino@<host>" --backend npu --pairs ...  # VENTUNO Q
python scripts/benchmark_e2e.py --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi                              # PC
python dashboard/build_report.py                                                                         # results/README.md + dashboard
```

Each run folder contains:
- `summary.md` and `summary.json`
- the raw device output (`result.jsonl`)
- per-utterance rows with references (`rows.jsonl`)
- the device stderr log and memory samples
- the 16 kHz inputs (`stage/`) and the spoken outputs (`wav/`)

Metrics:
- BLEU, chrF++ and COMET (wmt22-comet-da) on normalized text.
- WER/CER of the ASR.
- ASR-BLEU, which re-recognizes the spoken output.
- Per-stage and end-to-end latency, peak RSS and GPU memory.
- On VENTUNO Q, the engine's non-loopback network sockets (evidence that inference makes no network calls).

## Limitations and roadmap

- Vietnamese → X directions lose about 1.8 COMET (VI→EN) when the punctuation pass is dropped for speed. `--punct-pass` restores it.
- Push-to-talk per utterance. Streaming ASR with VAD segmentation is next (the Android app already uses Silero VAD).
- Korean and Chinese TTS (CPU) are now the slowest stages on the NPU build. Moving them to the NPU or optimizing them is next.
- A factory/warehouse glossary in the prompt, and LoRA domain adaptation of Gemma 4 E2B.

## Licenses

- Gemma 4: Gemma Terms of Use.
- hynt Zipformer ASR: CC BY-NC-ND 4.0.
- ViFastTts voice weights: CC BY-NC 4.0.
- X-ASR, sherpa-onnx, LiteRT-LM and ONNX Runtime: Apache-2.0 / MIT.
- Piper lessac voice: see its model card. Supertonic: see its LICENSE.
- QAIRT (Qualcomm AI Runtime): Qualcomm's terms. It is not redistributed in the main package.

Use in this competition is non-commercial.
