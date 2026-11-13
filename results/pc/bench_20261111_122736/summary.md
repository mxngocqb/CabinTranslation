# Benchmark 20261111_122736

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 2973.0 MB  {'asr:xasr-zh-en': 175.0, 'asr:vi-30m': 30.1, 'mt:gemma-4-E2B-it-Q3_K_M.gguf': 2536.8, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 3735.5 MB, peak VRAM: 1964 MB, load time 10.1s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.59 | 50.96 | 65.25 | 87.59 | 50.65 | 0.029 | 0.14 | 0.357 | 0.495 / 0.759 |
| en-vi | 100 | 7.85 | 43.72 | 60.56 | 84.38 | 42.03 | 0.094 | 0.136 | 0.092 | 0.308 / 0.454 |
