# edge/ — on-device builds

One native engine, three ways to ship it. Everything here runs **on the device** in a single process with no
Python and no network calls during inference.

```
edge/
├── engine/                  shared source
│   ├── cabin_edge.cc        ASR → text prep → Gemma MT → TTS; batch mode (--manifest) and HTTP server (--serve)
│   ├── litert_lm_compat_018.cc   LiteRT-LM 1.0 C API on top of the 0.18 NPU runtime (dlopen), used by cabin_edge_npu
│   └── web/index.html       touch UI served by the engine (hold-to-talk, per-stage timing, replay)
├── qcs8550-android/         Android arm64 (NDK r27c): build.sh, start.sh, stop.sh, dist/      → QCS8550 tablet, Gemma on GPU
├── ventunoq-linux/          Linux aarch64 glibc: build.sh, start.sh, stop.sh, https_proxy.py, package.sh, dist/
│                                                                                              → VENTUNO Q, Gemma on NPU / GPU / CPU
├── android-app/             Kotlin app (APK) that runs the engine as a child process + Silero VAD capture
│                                                                    → tested on QCS8550 tablet and Galaxy S25 Ultra
└── tools/
    ├── make_device_bundle.py   generate config_*.json + prompts.json from cabin/mt.py & cabin/normalize.py; push (adb or ssh)
    ├── run_device_bench.py     full-sample-set benchmark on the device, scored on the host → results/<device>/
    ├── bench_device_tts.py     on-device TTS candidate comparison (QCS8550)
    ├── power_bench_android.py  battery power/energy per utterance on an Android phone (dumpsys battery, no root)
    ├── net_socks.py            counts the engine's non-loopback sockets on Linux boards (evidence of no network use)
    └── compile_npu_model.sh    AOT-compile the Gemma NPU_Uncompiled bundle for a Qualcomm SoC (x86 host)
```

## Runtime per stage

| Stage | QCS8550 (Android) | VENTUNO Q (Linux) |
|---|---|---|
| ASR (vi / en+zh / ko) | sherpa-onnx 1.13.8 C API, CPU, 4 threads | same (linux-aarch64 build) |
| MT, Gemma 4 E2B | LiteRT-LM C API 0.19.1, **GPU** (Adreno 740, OpenCL), `-gpu.litertlm`, ctx 384, prefix cache | **NPU**: LiteRT-LM 0.18 + Qualcomm dispatch + QAIRT 2.50 (`_Qualcomm_QCS8275.litertlm`) · GPU: Vulkan/Turnip · CPU: XNNPACK |
| TTS (vi / en / ko / zh) | ViFastTts FFI / Piper / Supertonic-2 / Matcha, CPU, 2 threads | same |

## Common workflow

```bash
bash edge/<platform>/build.sh                                         # cross-compile on the host → edge/<platform>/dist/
python edge/tools/make_device_bundle.py [--target linux --ssh "..."] --push [--no-models]
python edge/tools/run_device_bench.py   [--target linux --ssh "..." --backend npu] [--device-tag <name>] --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi
python dashboard/build_report.py                                      # refresh results/README.md + dashboard
```

- **Prompts come from the PC code.** `config_*.json` and `prompts.json` are generated from `cabin/mt.py` (system
  prompts, `LOWERCASE_NOTE`) and `cabin/normalize.py` (question heuristics), so the PC and device builds translate identically.
- **Relocatable configs.** On Linux, config paths starting with `./` are resolved by the engine against the config file's
  folder, so the VENTUNO Q package runs from any directory.
- **Vietnamese input** uses one Gemma call by default (`punct_pass: false`). `make_device_bundle.py --punct-pass` adds the
  separate Gemma punctuation pass (2 calls, +0.8 COMET on average, slower).

Platform details and every measured choice: [qcs8550-android/README.md](qcs8550-android/README.md),
[ventunoq-linux/README.md](ventunoq-linux/README.md), [android-app/README.md](android-app/README.md).
