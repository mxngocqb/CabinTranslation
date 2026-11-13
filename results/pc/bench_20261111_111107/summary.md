# Benchmark 20261111_111107

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 4277.4 MB  {'asr:en-parakeet': 661.3, 'asr:vi-30m': 35.5, 'mt:gemma-4-E2B-it-qat-q4_0': 3349.5, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 4921.7 MB, peak VRAM: 0 MB, load time 15.54s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.59 | 46.62 | 62.56 | 86.77 | 45.86 | 0.026 | 0.094 | 0.366 | 0.46 / 0.726 |
| en-vi | 100 | 8.61 | 41.19 | 58.64 | 84.21 | 39.53 | 0.253 | 0.12 | 0.066 | 0.43 / 0.637 |
