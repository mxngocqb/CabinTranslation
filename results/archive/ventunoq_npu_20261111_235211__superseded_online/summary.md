# On-device benchmark 20261111_235211

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651776 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[end0=UP wlp3s0=UP]; at end: internet=online
- LLM backend: npu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it_Qualcomm_QCS8275.litertlm, sampler=greedy, prefix_cache=False, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_en": 6388, "asr_ko": 3992, "asr_vi": 2946, "asr_zh": 6356, "mt": 757, "tts_en": 1067, "tts_ko": 738, "tts_vi": 759, "tts_zh": 2645}
- Peak process RSS (VmHWM): 3885 MB; /proc + DRM fdinfo peaks (MB): total_rss=3859, vm_hwm=3885, graphics=0
- Engine network sockets (non-loopback TCP/UDP of the cabin_edge process, sampled every ~1 s, whole run): max = 0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 47.72 | 63.9 | 86.82 | 47.47 | 100.0 | 0.0 | 345.6 | 74.3 | 37.9 | 298.5 | 712.5 / 1159.4 |
| en-vi | 100 | 7.96 | 40.75 | 59.35 | 83.93 | 39.42 | 270.2 | 0.0 | 723.3 | 76.4 | 38.1 | 307.6 | 1213.2 / 2031.0 |
| vi-ko | 175 | 4.76 | 34.58 | 27.79 | 87.2 | 34.06 | 78.1 | 0.0 | 318.3 | 72.9 | 37.5 | 491.0 | 863.6 / 1367.6 |
| ko-vi | 177 | 7.69 | 22.32 | 41.55 | 83.47 | 21.86 | 120.8 | 0.0 | 322.5 | 72.6 | 37.6 | 125.3 | 538.0 / 880.2 |
| vi-zh | 176 | 12.33 | 51.72 | 35.75 | 90.6 | 48.59 | 97.6 | 0.0 | 328.5 | 72.2 | 37.8 | 404.1 | 755.1 / 1512.3 |
| zh-vi | 177 | 3.74 | 45.85 | 63.68 | 92.81 | 45.15 | 162.7 | 0.0 | 432.4 | 72.1 | 38.1 | 175.6 | 696.1 / 1400.5 |
