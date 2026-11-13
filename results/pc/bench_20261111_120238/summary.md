# Benchmark 20261111_120238

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 3411.7 MB  {'asr:en-parakeet-110m': 609.9, 'asr:vi-30m': 33.9, 'mt:gemma-4-E2B-it-Q3_K_M.gguf': 2536.8, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 3661.0 MB, peak VRAM: 2252 MB, load time 9.85s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.59 | 50.96 | 65.25 | 87.59 | 50.21 | 0.029 | 0.145 | 0.355 | 0.491 / 0.743 |
| en-vi | 100 | 9.58 | 42.5 | 59.55 | 83.64 | 41.32 | 0.097 | 0.131 | 0.081 | 0.301 / 0.442 |
