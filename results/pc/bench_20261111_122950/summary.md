# Benchmark 20261111_122950

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 2871.7 MB  {'asr:en-gigaspeech': 73.7, 'asr:vi-30m': 30.1, 'mt:gemma-4-E2B-it-Q3_K_M.gguf': 2536.8, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 3513.8 MB, peak VRAM: 2038 MB, load time 9.77s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| en-vi | 100 | 9.53 | 43.07 | 59.65 | 84.06 | 41.71 | 0.066 | 0.137 | 0.078 | 0.27 / 0.416 |
