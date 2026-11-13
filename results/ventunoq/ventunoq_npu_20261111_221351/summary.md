# On-device benchmark 20261111_221351

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651776 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[end0=UP wlp3s0=UP]; at end: internet=online
- LLM backend: npu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it_Qualcomm_QCS8275.litertlm, sampler=greedy, prefix_cache=False, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_en": 6376, "asr_ko": 4003, "asr_vi": 2948, "asr_zh": 6389, "mt": 668, "tts_en": 1078, "tts_ko": 756, "tts_vi": 753, "tts_zh": 2619}
- Peak process RSS (VmHWM): 4174 MB; /proc + DRM fdinfo peaks (MB): total_rss=4152, vm_hwm=4174, graphics=0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 47.72 | 63.9 | 86.82 | 47.3 | 99.1 | 0.0 | 323.5 | 69.1 | 40.6 | 298.0 | 686.8 / 1104.1 |
| en-vi | 100 | 7.96 | 40.75 | 59.35 | 83.93 | 39.42 | 273.9 | 0.0 | 676.0 | 73.6 | 40.8 | 305.5 | 1143.6 / 1907.4 |
| vi-ko | 175 | 4.76 | 34.58 | 27.79 | 87.2 | 33.17 | 77.3 | 0.0 | 299.6 | 69.8 | 40.3 | 491.6 | 833.8 / 1311.5 |
| ko-vi | 177 | 7.69 | 22.32 | 41.55 | 83.47 | 21.86 | 118.6 | 0.0 | 302.4 | 69.1 | 40.4 | 125.1 | 508.8 / 865.3 |
| vi-zh | 176 | 12.33 | 51.72 | 35.75 | 90.6 | 48.47 | 98.5 | 0.0 | 309.8 | 69.3 | 40.3 | 402.9 | 735.7 / 1446.1 |
| zh-vi | 177 | 3.74 | 45.85 | 63.68 | 92.81 | 45.15 | 162.2 | 0.0 | 406.6 | 69.2 | 40.7 | 173.9 | 660.6 / 1354.3 |
