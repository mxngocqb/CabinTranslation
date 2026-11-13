# On-device benchmark 20261113_161738

- Device: SM8750 / SM-S938B, Android 17, MemTotal:       11379712 kB, ------------RE GLES (Ganesh)------------
- Network at start: wifi_on=1 airplane=0 internet=online; at end: internet=online
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it-gpu.litertlm, sampler=greedy, prefix_cache=True, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_en": 2277, "asr_ko": 1395, "asr_vi": 1036, "asr_zh": 2253, "mt": 8123, "tts_en": 393, "tts_ko": 347, "tts_vi": 400, "tts_zh": 961}
- Peak process RSS (VmHWM): 2906 MB; dumpsys peaks (MB): total_pss=4583, total_rss=3925, graphics=1953, native_heap=1513, gl_mtrack=1106

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 50.22 | 65.35 | - | 49.49 | 54.6 | 0.0 | 285.5 | 72.5 | 52.3 | 189.6 | 508.8 / 784.3 |
| en-vi | 100 | 7.85 | 42.91 | 60.47 | - | 41.41 | 145.2 | 0.0 | 854.9 | 139.1 | 37.0 | 241.2 | 1158.9 / 2057.8 |
| vi-ko | 175 | 4.84 | 35.97 | 29.35 | - | 35.28 | 44.0 | 0.0 | 330.8 | 85.0 | 43.7 | 281.9 | 624.8 / 1038.8 |
| ko-vi | 177 | 7.8 | 21.11 | 40.79 | - | 21.0 | 84.8 | 0.0 | 397.6 | 104.2 | 37.0 | 130.0 | 574.0 / 1006.7 |
| vi-zh | 176 | 12.38 | 52.88 | 35.7 | - | 49.42 | 54.1 | 0.0 | 359.8 | 103.2 | 39.4 | 233.9 | 573.8 / 1137.0 |
| zh-vi | 177 | 3.74 | 45.62 | 63.19 | - | 44.58 | 102.9 | 0.0 | 539.6 | 113.3 | 34.3 | 159.6 | 738.1 / 1509.0 |
