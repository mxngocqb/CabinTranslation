# On-device benchmark 20261111_161624

- Device: QCS8550 / Tablet Meeting, Android 13, MemTotal:       15626272 kB, GLES: Qualcomm, Adreno (TM) 740, OpenGL ES 3.2 V@0676.69 (GIT@1e9d6bfa18, Ia9449ce5a8, 1741259084) (Date:03/06/25)
- Network at start: wifi_on=1 airplane=0 internet=online; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gpu.litertlm); ASR/TTS: CPU
- Load time (ms): {"asr_en": 4257, "asr_ko": 2651, "asr_vi": 1678, "asr_zh": 4227, "mt": 8007, "tts_en": 630, "tts_ko": 619, "tts_vi": 661, "tts_zh": 1794}
- Peak process RSS (VmHWM): 4254 MB; dumpsys peaks (MB): total_pss=4216, total_rss=4246, graphics=841, native_heap=2237, gl_mtrack=0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 54.62 | 67.99 | 88.63 | 53.88 | 75.8 | 490.1 | 509.0 | 122.1 | 30.8 | 225.8 | 1220.7 / 1996.6 |
| en-vi | 100 | 7.8 | 42.07 | 60.03 | 84.08 | 40.4 | 188.9 | 0.0 | 968.6 | 149.3 | 30.7 | 394.6 | 1441.8 / 2463.8 |
| vi-ko | 175 | 4.84 | 38.1 | 30.59 | 88.05 | 37.05 | 60.4 | 448.6 | 467.1 | 120.8 | 30.7 | 342.9 | 1254.4 / 2060.3 |
| ko-vi | 177 | 7.86 | 22.51 | 41.09 | 83.41 | 22.1 | 86.6 | 0.0 | 448.2 | 116.7 | 30.8 | 136.1 | 629.2 / 1089.8 |
| vi-zh | 176 | 12.38 | 55.09 | 39.39 | 91.24 | 51.52 | 79.4 | 612.2 | 496.7 | 131.8 | 30.7 | 317.8 | 1328.4 / 2867.2 |
| zh-vi | 177 | 3.74 | 45.72 | 63.6 | 92.92 | 44.57 | 112.6 | 0.0 | 595.3 | 118.1 | 30.8 | 199.4 | 800.6 / 1698.7 |
