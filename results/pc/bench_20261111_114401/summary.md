# Benchmark 20261111_114401

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 3162.5 MB  {'asr:ko-zipformer': 359.1, 'asr:vi-30m': 35.5, 'mt:gemma-4-E2B-it-Q3_K_M.gguf': 2536.8, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 3618.0 MB, peak VRAM: 2305 MB, load time 9.54s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| ko-vi | 177 | 7.86 | 23.24 | 40.82 | 83.21 | 22.38 | 0.049 | 0.084 | 0.047 | 0.172 / 0.282 |
