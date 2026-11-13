# On-device benchmark 20261111_202616

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651776 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[end0=UP wlp3s0=UP]; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it-gpu.litertlm, sampler=greedy, prefix_cache=True, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_en": 6268, "asr_ko": 4009, "asr_vi": 2923, "asr_zh": 6390, "mt": 3397, "tts_en": 1105, "tts_ko": 754, "tts_vi": 744, "tts_zh": 2608}
- Peak process RSS (VmHWM): 3404 MB; /proc + DRM fdinfo peaks (MB): total_rss=3404, vm_hwm=3404, graphics=1212

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 47.44 | 63.53 | 86.82 | 46.81 | 99.2 | 0.0 | 1889.4 | 539.5 | 7.2 | 302.5 | 2174.1 / 3300.0 |
| en-vi | 100 | 7.96 | 42.73 | 60.46 | 83.9 | 41.27 | 274.2 | 0.0 | 4316.4 | 799.6 | 6.8 | 307.2 | 4484.4 / 7919.5 |
| vi-ko | 175 | 4.76 | 38.19 | 31.16 | 87.72 | 37.06 | 78.9 | 0.0 | 1735.3 | 522.9 | 7.3 | 505.1 | 2214.0 / 3463.3 |
| ko-vi | 177 | 7.69 | 21.97 | 40.95 | 83.15 | 21.5 | 123.8 | 0.0 | 1785.2 | 521.3 | 7.3 | 127.2 | 1981.7 / 3383.3 |
| vi-zh | 176 | 12.33 | 51.62 | 34.8 | 90.66 | 48.28 | 99.4 | 0.0 | 1877.8 | 607.6 | 7.3 | 403.2 | 2095.3 / 4639.0 |
| zh-vi | 177 | 3.74 | 46.98 | 63.88 | 92.97 | 46.06 | 165.4 | 0.0 | 2441.6 | 540.7 | 7.1 | 177.4 | 2506.3 / 5229.4 |
