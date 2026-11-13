# On-device benchmark 20261111_193548

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651776 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[end0=UP wlp3s0=UP]; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it-gpu.litertlm, sampler=greedy, prefix_cache=True, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_ko": 3922, "asr_vi": 2960, "mt": 3263, "tts_en": 1034, "tts_vi": 761}
- Peak process RSS (VmHWM): 1041 MB; /proc + DRM fdinfo peaks (MB): total_rss=1039, vm_hwm=1039, graphics=1194

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 3 | 0.0 | 75.52 | 77.07 | - | 75.52 | 124.0 | 1780.2 | 1732.6 | 633.9 | 7.4 | 259.1 | 3698.4 / 4266.3 |
| ko-vi | 3 | 0.0 | 11.16 | 36.52 | - | 11.16 | 108.1 | 0.0 | 1677.8 | 523.3 | 7.3 | 131.6 | 1992.9 / 2186.3 |
