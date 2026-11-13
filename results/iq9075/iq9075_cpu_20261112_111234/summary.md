# On-device benchmark 20261112_111234

- Device: QCS9075 / Qualcomm Technologies, Inc. Addons IQ 9075 EVK, Qualcomm Linux 1.9-ver.1.0, kernel 6.6.136-qli-1.9-ver.1.0-06428-g9fbf5270689c-dirty, MemTotal:       34704964 kB, Adreno663v1 (KGSL, Qualcomm OpenCL/Vulkan), CPU Cortex-A78C/ 8 cores
- Network at start: wifi_on=1 airplane=n/a internet=online links=[eth0=UP wlan0=UP]; at end: internet=online
- LLM backend: cpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it.litertlm, sampler=topk1, prefix_cache=False, ctx=1024, threads=8); ASR/TTS: CPU
- Load time (ms): {"asr_en": 5305, "asr_ko": 3195, "asr_vi": 2387, "asr_zh": 5021, "mt": 254, "tts_en": 911, "tts_ko": 597, "tts_vi": 661, "tts_zh": 2161}
- Peak process RSS (VmHWM): 4398 MB; /proc + DRM fdinfo peaks (MB): total_rss=4367, vm_hwm=4398, graphics=0
- Engine network sockets (non-loopback TCP/UDP of the cabin_edge process, sampled every ~1 s, whole run): max = 0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 48.48 | 63.86 | 86.44 | 47.84 | 63.6 | 0.0 | 855.5 | 547.8 | 31.6 | 260.4 | 1134.7 / 1563.3 |
| en-vi | 100 | 8.12 | 42.08 | 59.97 | 83.67 | 40.56 | 192.1 | 0.0 | 1314.8 | 549.1 | 31.2 | 274.9 | 1672.5 / 2588.8 |
| vi-ko | 175 | 4.68 | 35.92 | 28.86 | 87.25 | 35.31 | 51.8 | 0.0 | 859.1 | 570.3 | 30.6 | 432.1 | 1290.3 / 1796.6 |
| ko-vi | 177 | 7.69 | 22.71 | 41.84 | 83.68 | 21.91 | 82.9 | 0.0 | 879.3 | 579.8 | 30.0 | 110.9 | 1042.8 / 1392.7 |
| vi-zh | 176 | 12.33 | 51.94 | 34.7 | 90.55 | 48.55 | 67.9 | 0.0 | 884.8 | 580.8 | 30.3 | 357.2 | 1221.0 / 1967.5 |
| zh-vi | 177 | 3.74 | 46.52 | 63.94 | 93.05 | 45.49 | 114.3 | 0.0 | 979.5 | 552.0 | 31.3 | 157.1 | 1158.0 / 1906.4 |
