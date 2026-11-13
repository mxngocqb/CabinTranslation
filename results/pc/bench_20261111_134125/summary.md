# Benchmark 20261111_134125

- Device: x86_64 (16 threads), RAM 50.5 GB, GPU NVIDIA GeForce RTX 4080 SUPER
- Network online at start/end: True / True
- Models on disk: 3049.3 MB  {'asr:xasr-zh-en': 175.0, 'asr:ko-zipformer': 76.3, 'asr:vi-30m': 30.1, 'mt:gemma-4-E2B-it-Q3_K_M.gguf': 2536.8, 'tts:vifasttts-ngochuyen-small': 85.8, 'tts:supertonic-3-int8': 145.3}
- Peak RAM (process RSS): 4800.5 MB, peak VRAM: 2041 MB, load time 15.93s

| pair | n | ASR WER/CER | BLEU | chrF++ | COMET | ASR-BLEU (speech out) | ASR s | MT s | TTS s | total s (p50/p95) |
|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.59 | 50.96 | 65.25 | 87.59 | 50.57 | 0.029 | 0.146 | 0.351 | 0.507 / 0.768 |
| en-vi | 100 | 7.85 | 43.72 | 60.56 | 84.38 | 42.03 | 0.092 | 0.136 | 0.09 | 0.319 / 0.458 |
| vi-ko | 175 | 5.08 | 39.45 | 32.29 | 88.14 | 38.28 | 0.023 | 0.13 | 0.312 | 0.454 / 0.679 |
| ko-vi | 177 | 7.86 | 22.75 | 40.8 | 83.17 | 21.98 | 0.047 | 0.082 | 0.046 | 0.167 / 0.266 |
| vi-zh | 176 | 12.38 | 52.5 | 35.85 | 91.59 | 49.54 | 0.035 | 0.159 | 0.112 | 0.29 / 0.501 |
| zh-vi | 177 | 3.74 | 46.62 | 63.55 | 93.16 | 46.01 | 0.065 | 0.094 | 0.061 | 0.213 / 0.35 |
