# On-device benchmark 20261111_145722

- Device: QCS8550 / Tablet Meeting, Android 13, MemTotal:       15626272 kB, GLES: Qualcomm, Adreno (TM) 740, OpenGL ES 3.2 V@0676.69 (GIT@1e9d6bfa18, Ia9449ce5a8, 1741259084) (Date:03/06/25)
- Network at start: wifi_on=1 airplane=0 internet=online; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gpu.litertlm); ASR/TTS: CPU
- Load time (ms): {"asr_en": 4118, "asr_vi": 1785, "mt": 7652, "tts_en": 785, "tts_vi": 656}
- Peak process RSS (VmHWM): 2425 MB; dumpsys peaks (MB): total_pss=2369, total_rss=2405, graphics=840, native_heap=881

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 5 | 2.86 | 49.96 | 64.35 | - | 49.96 | 74.2 | 497.2 | 552.2 | 281.6 | 30.5 | 892.0 | 2099.7 / 2216.5 |
| en-vi | 5 | 6.17 | 44.56 | 60.27 | - | 44.04 | 208.4 | 0.0 | 1055.3 | 273.7 | 30.3 | 354.6 | 1702.9 / 1813.3 |
