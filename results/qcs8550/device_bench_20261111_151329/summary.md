# On-device benchmark 20261111_151329

- Device: QCS8550 / Tablet Meeting, Android 13, MemTotal:       15626272 kB, GLES: Qualcomm, Adreno (TM) 740, OpenGL ES 3.2 V@0676.69 (GIT@1e9d6bfa18, Ia9449ce5a8, 1741259084) (Date:03/06/25)
- Network at start: wifi_on=1 airplane=0 internet=online; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gpu.litertlm); ASR/TTS: CPU
- Load time (ms): {"asr_en": 4190, "asr_ko": 2619, "asr_vi": 1688, "asr_zh": 4260, "mt": 8014, "tts_en": 770, "tts_ko": 793, "tts_vi": 653, "tts_zh": 1822}
- Peak process RSS (VmHWM): 4377 MB; dumpsys peaks (MB): total_pss=4340, total_rss=4370, graphics=841, native_heap=2361, gl_mtrack=0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 54.62 | 67.99 | 88.63 | 54.11 | 74.3 | 490.4 | 506.9 | 122.7 | 30.9 | 1150.5 | 2079.8 / 3515.0 |
| en-vi | 100 | 7.8 | 42.07 | 60.03 | 84.08 | 40.4 | 192.6 | 0.0 | 968.8 | 149.9 | 30.8 | 388.0 | 1417.0 / 2417.0 |
| vi-ko | 175 | 4.84 | 38.1 | 30.59 | 88.05 | 37.14 | 60.1 | 448.4 | 466.1 | 120.9 | 30.9 | 1014.7 | 1890.2 / 3276.5 |
| ko-vi | 177 | 7.86 | 22.51 | 41.09 | 83.41 | 22.1 | 86.8 | 0.0 | 445.7 | 116.2 | 30.9 | 135.9 | 627.0 / 1049.3 |
| vi-zh | 176 | 12.38 | 55.09 | 39.39 | 91.24 | 51.67 | 78.2 | 610.6 | 497.6 | 132.0 | 30.8 | 315.0 | 1331.5 / 2793.1 |
| zh-vi | 177 | 3.74 | 45.72 | 63.6 | 92.92 | 44.57 | 113.1 | 0.0 | 594.8 | 118.3 | 30.9 | 198.4 | 799.2 / 1683.2 |
