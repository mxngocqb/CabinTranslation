# On-device benchmark 20261111_202421

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651776 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[end0=UP wlp3s0=UP]; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it-gpu.litertlm, sampler=greedy, prefix_cache=True, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_vi": 2979, "mt": 3294, "tts_en": 1096}
- Peak process RSS (VmHWM): 689 MB; /proc + DRM fdinfo peaks (MB): total_rss=688, vm_hwm=688, graphics=1192

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 3 | 0.0 | 74.66 | 76.32 | - | 74.66 | 95.0 | 0.0 | 1688.5 | 538.1 | 7.3 | 278.9 | 1954.6 / 2296.5 |
