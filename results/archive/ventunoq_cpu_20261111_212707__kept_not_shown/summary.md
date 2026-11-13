# On-device benchmark 20261111_212707

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651776 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[end0=UP wlp3s0=UP]; at end: internet=online
- LLM backend: cpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it.litertlm, sampler=topk1, prefix_cache=False, ctx=1024, threads=4); ASR/TTS: CPU
- Load time (ms): {"asr_en": 6351, "asr_ko": 4037, "asr_vi": 2945, "asr_zh": 6381, "mt": 306, "tts_en": 1065, "tts_ko": 734, "tts_vi": 762, "tts_zh": 2614}
- Peak process RSS (VmHWM): 4315 MB; /proc + DRM fdinfo peaks (MB): total_rss=3097, vm_hwm=3110, graphics=0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 48.48 | 63.86 | 86.44 | 47.8 | 96.9 | 0.0 | 2062.3 | 1345.8 | 14.1 | 296.5 | 2328.3 / 3450.7 |
| en-vi | 100 | 7.96 | 42.04 | 59.99 | 83.68 | 40.56 | 278.0 | 0.0 | 3497.3 | 1359.2 | 12.3 | 303.7 | 3762.0 / 7181.3 |
| vi-ko | 175 | 4.76 | 35.89 | 28.85 | 87.22 | 35.06 | 77.1 | 0.0 | 1986.1 | 1279.4 | 13.3 | 498.3 | 2425.7 / 3719.7 |
| ko-vi | 177 | 7.69 | 22.71 | 41.84 | 83.68 | 21.9 | 121.3 | 0.0 | 1915.5 | 1286.0 | 14.6 | 122.1 | 2094.1 / 2786.1 |
| vi-zh | 176 | 12.33 | 51.94 | 34.7 | 90.55 | 48.52 | 97.2 | 0.0 | 1932.0 | 1270.9 | 14.2 | 397.7 | 2283.9 / 3557.7 |
| zh-vi | 177 | 3.74 | 46.52 | 63.94 | 93.05 | 45.45 | 164.2 | 0.0 | 2257.2 | 1291.5 | 14.2 | 172.4 | 2456.2 / 3770.7 |
