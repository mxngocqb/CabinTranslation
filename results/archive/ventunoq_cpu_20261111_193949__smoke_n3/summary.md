# On-device benchmark 20261111_193949

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651776 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[end0=UP wlp3s0=UP]; at end: internet=online
- LLM backend: cpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it.litertlm, sampler=topk1, prefix_cache=False, ctx=1024, threads=4); ASR/TTS: CPU
- Load time (ms): {"asr_vi": 2982, "asr_zh": 6288, "mt": 297, "tts_en": 1025, "tts_vi": 768}
- Peak process RSS (VmHWM): 2111 MB; /proc + DRM fdinfo peaks (MB): total_rss=2108, vm_hwm=2108, graphics=0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 3 | 0.0 | 61.32 | 74.47 | - | 61.32 | 91.9 | 1389.1 | 1665.2 | 1131.4 | 15.7 | 250.7 | 3393.7 / 3636.5 |
| zh-vi | 3 | 0.0 | 28.91 | 51.94 | - | 28.91 | 181.7 | 0.0 | 2270.4 | 1260.3 | 14.4 | 203.1 | 2497.1 / 3402.1 |
