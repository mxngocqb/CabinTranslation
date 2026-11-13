# Benchmark 20261111_113437

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 3464.7 MB  {'asr:en-parakeet': 661.3, 'asr:vi-30m': 35.5, 'mt:gemma-4-E2B-it-Q3_K_M.gguf': 2536.8, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 4324.1 MB, peak VRAM: 2023 MB, load time 15.74s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.59 | 50.96 | 65.25 | 87.59 | 50.53 | 0.026 | 0.14 | 0.373 | 0.522 / 0.788 |
| en-vi | 100 | 8.61 | 45.67 | 61.85 | 84.75 | 44.09 | 0.246 | 0.127 | 0.069 | 0.411 / 0.683 |
