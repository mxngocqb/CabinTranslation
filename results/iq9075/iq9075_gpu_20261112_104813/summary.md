# On-device benchmark 20261112_104813

- Device: QCS9075 / Qualcomm Technologies, Inc. Addons IQ 9075 EVK, Qualcomm Linux 1.9-ver.1.0, kernel 6.6.136-qli-1.9-ver.1.0-06428-g9fbf5270689c-dirty, MemTotal:       34704964 kB, Adreno663v1 (KGSL, Qualcomm OpenCL/Vulkan), CPU Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[eth0=UP wlan0=UP]; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it-gpu.litertlm, sampler=greedy, prefix_cache=True, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_en": 4949, "asr_ko": 3051, "asr_vi": 2201, "asr_zh": 4937, "mt": 1462, "tts_en": 893, "tts_ko": 580, "tts_vi": 653, "tts_zh": 2159}
- Peak process RSS (VmHWM): 3432 MB; /proc + DRM fdinfo peaks (MB): total_rss=3406, vm_hwm=3432, graphics=1380
- Engine network sockets (non-loopback TCP/UDP of the cabin_edge process, sampled every ~1 s, whole run): max = 0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 47.67 | 63.54 | 86.77 | 46.99 | 64.6 | 0.0 | 888.9 | 262.0 | 15.8 | 265.9 | 1170.3 / 1780.2 |
| en-vi | 100 | 8.12 | 42.72 | 60.23 | 83.9 | 41.37 | 196.3 | 0.0 | 2016.0 | 438.6 | 15.2 | 278.1 | 2227.1 / 4103.5 |
| vi-ko | 175 | 4.68 | 36.15 | 28.78 | 87.45 | 34.34 | 51.4 | 0.0 | 799.7 | 249.8 | 16.2 | 434.2 | 1199.2 / 2018.9 |
| ko-vi | 177 | 7.69 | 22.23 | 41.58 | 83.76 | 21.8 | 80.7 | 0.0 | 825.8 | 252.2 | 16.0 | 116.7 | 972.9 / 1667.7 |
| vi-zh | 176 | 12.33 | 52.39 | 36.05 | 90.71 | 48.94 | 66.3 | 0.0 | 902.7 | 306.5 | 15.9 | 365.7 | 1139.7 / 2813.0 |
| zh-vi | 177 | 3.74 | 45.5 | 63.0 | 92.83 | 44.32 | 117.2 | 0.0 | 1139.8 | 264.9 | 15.5 | 162.4 | 1270.8 / 2636.9 |
