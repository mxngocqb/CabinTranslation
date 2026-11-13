# Benchmark 20261111_114843

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 3547.8 MB  {'asr:en-parakeet': 661.3, 'asr:ko-zipformer': 84.7, 'asr:vi-30m': 33.9, 'mt:gemma-4-E2B-it-Q3_K_M.gguf': 2536.8, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 5069.1 MB, peak VRAM: 2025 MB, load time 12.7s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.59 | 50.96 | 65.25 | 87.59 | 50.17 | 0.025 | 0.143 | 0.365 | 0.515 / 0.758 |
| en-vi | 100 | 8.61 | 45.67 | 61.85 | 84.75 | 44.09 | 0.249 | 0.126 | 0.069 | 0.422 / 0.666 |
| ko-vi | 177 | 7.86 | 22.75 | 40.8 | 83.17 | 21.98 | 0.048 | 0.084 | 0.044 | 0.166 / 0.282 |
