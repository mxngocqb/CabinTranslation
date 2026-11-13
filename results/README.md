# Results — CabinTranslation

_Generated 2026-11-13 21:53 by `python dashboard/build_report.py`. Open the dashboard with `bash dashboard/serve.sh` (http://localhost:8000/dashboard/) for charts, per-utterance browsing and audio._

## Layout

```
results/
  README.md              this index (generated)
  (dashboard: ../dashboard/index.html, generated)
  qcs8550/               on-device runs, QCS8550 tablet (Android, Gemma on GPU): device_bench_* (end-to-end), device_tts_* (TTS candidates)
  ventunoq/              on-device runs, Arduino VENTUNO Q / QCS8275 (Linux, Gemma on CPU/GPU/NPU): ventunoq_<backend>_*
  iq9075/                on-device runs, Qualcomm IQ-9075 EVK / QCS9075 (Qualcomm Linux, Gemma on CPU/GPU): iq9075_<backend>_*
  s25ultra/              on-device runs, Samsung Galaxy S25 Ultra / SM8750 (Android, Gemma on GPU): s25ultra_gpu_*
  pc/                    PC reference runs (RTX 4080): bench_* (end-to-end)
  components/asr|mt|tts/ component evaluations and model comparisons
  archive/               smoke tests, crashed or failed runs (kept for traceability)
```

## Official on-device results — Qualcomm QCS8550 (`qcs8550/device_bench_20261113_215053_offline`)

- Device: QCS8550 / Tablet Meeting, Android 13, Adreno 740.
- Runtime: Gemma 4 E2B on the GPU via LiteRT-LM (context 384); ASR and TTS on the CPU.
- Peak RSS: 4231 MB (all 4 languages loaded). GPU (Graphics): 840 MB.
- Network: offline at start, offline at end. **Re-run offline for the submission.**

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTS ms | total p50 / p95 ms |
|---|---|---|---|---|---|---|---|---|---|---|---|
| VI→EN | 100 | WER 1.72 | 48.3 | 63.95 | 86.45 | 47.93 | 76 | 0 | 500 | 209 | 736 / 1204 |
| EN→VI | 100 | WER 7.8 | 42.07 | 60.03 | 84.08 | 40.4 | 186 | 0 | 950 | 389 | 1434 / 2400 |
| VI→KO | 175 | WER 4.84 | 34.93 | 28.05 | 87.46 | 34.36 | 62 | 0 | 434 | 332 | 794 / 1310 |
| KO→VI | 177 | CER 7.86 | 22.51 | 41.09 | 83.41 | 22.1 | 87 | 0 | 428 | 137 | 619 / 1046 |
| VI→ZH | 176 | WER 12.38 | 52.24 | 35.06 | 90.17 | 49.1 | 81 | 0 | 451 | 301 | 757 / 1488 |
| ZH→VI | 177 | CER 3.74 | 45.72 | 63.6 | 92.92 | 44.57 | 113 | 0 | 569 | 200 | 796 / 1663 |

BLEU for KO/ZH targets is character-level. ASR-BLEU is BLEU of the spoken output after re-recognition.

## Arduino VENTUNO Q — QCS8275, Ubuntu 24.04 (`ventunoq/`)

Same native pipeline; only the Gemma backend differs (ASR/TTS on CPU). VI input = 1 Gemma call. Runs: CPU `ventunoq_cpu_20261111_212707`, GPU `ventunoq_gpu_20261111_202616`, NPU `ventunoq_npu_20261111_235211`. Details: `edge/ventunoq-linux/README.md`.

| pair | COMET cpu | COMET gpu | COMET npu | BLEU cpu | BLEU gpu | BLEU npu | p50 cpu ms | p50 gpu ms | p50 npu ms |
|---|---|---|---|---|---|---|---|---|---|
| VI→EN | 86.44 | 86.82 | 86.82 | 48.48 | 47.44 | 47.72 | 2328 | 2174 | 712 |
| EN→VI | 83.68 | 83.9 | 83.93 | 42.04 | 42.73 | 40.75 | 3762 | 4484 | 1213 |
| VI→KO | 87.22 | 87.72 | 87.2 | 35.89 | 38.19 | 34.58 | 2426 | 2214 | 864 |
| KO→VI | 83.68 | 83.15 | 83.47 | 22.71 | 21.97 | 22.32 | 2094 | 1982 | 538 |
| VI→ZH | 90.55 | 90.66 | 90.6 | 51.94 | 51.62 | 51.72 | 2284 | 2095 | 755 |
| ZH→VI | 93.05 | 92.97 | 92.81 | 46.52 | 46.98 | 45.85 | 2456 | 2506 | 696 |

| backend | Gemma file | decode tok/s | TTFT ms | peak RSS MB | GPU MB | engine net sockets (max) |
|---|---|---|---|---|---|---|
| CPU | gemma-4-E2B-it.litertlm (2468 MB) | 13.8 | 1305 | 4315 | 0 | n/a |
| GPU | gemma-4-E2B-it-gpu.litertlm (2232 MB) | 7.2 | 589 | 3404 | 1212 | n/a |
| NPU | gemma-4-E2B-it_Qualcomm_QCS8275.litertlm (2596 MB) | 37.8 | 73 | 3885 | 0 | 0 |

Network during these runs: online.

## Qualcomm IQ-9075 EVK — QCS9075, Qualcomm Linux 1.9 (`iq9075/`)

Same native pipeline; only the Gemma backend differs (ASR/TTS on CPU). VI input = 1 Gemma call. Runs: CPU `iq9075_cpu_20261112_111234`, GPU `iq9075_gpu_20261112_104813`. Details: `edge/ventunoq-linux/README.md (same Linux build)`.

| pair | COMET cpu | COMET gpu | BLEU cpu | BLEU gpu | p50 cpu ms | p50 gpu ms |
|---|---|---|---|---|---|---|
| VI→EN | 86.44 | 86.77 | 48.48 | 47.67 | 1135 | 1170 |
| EN→VI | 83.67 | 83.9 | 42.08 | 42.72 | 1672 | 2227 |
| VI→KO | 87.25 | 87.45 | 35.92 | 36.15 | 1290 | 1199 |
| KO→VI | 83.68 | 83.76 | 22.71 | 22.23 | 1043 | 973 |
| VI→ZH | 90.55 | 90.71 | 51.94 | 52.39 | 1221 | 1140 |
| ZH→VI | 93.05 | 92.83 | 46.52 | 45.5 | 1158 | 1271 |

| backend | Gemma file | decode tok/s | TTFT ms | peak RSS MB | GPU MB | engine net sockets (max) |
|---|---|---|---|---|---|---|
| CPU | gemma-4-E2B-it.litertlm (2468 MB) | 30.8 | 563 | 4398 | 0 | 0 |
| GPU | gemma-4-E2B-it-gpu.litertlm (2232 MB) | 15.8 | 296 | 3432 | 1380 | 0 |

Network during these runs: online.

## Samsung Galaxy S25 Ultra — SM8750, Android 17 (latency run, COMET not computed) (`s25ultra/`)

Same native pipeline; only the Gemma backend differs (ASR/TTS on CPU). VI input = 1 Gemma call. Runs: GPU `s25ultra_gpu_20261113_161738`. Details: `edge/qcs8550-android/README.md (same Android build)`.

| pair | COMET gpu | BLEU gpu | p50 gpu ms |
|---|---|---|---|
| VI→EN | None | 50.22 | 509 |
| EN→VI | None | 42.91 | 1159 |
| VI→KO | None | 35.97 | 625 |
| KO→VI | None | 21.11 | 574 |
| VI→ZH | None | 52.88 | 574 |
| ZH→VI | None | 45.62 | 738 |

| backend | Gemma file | decode tok/s | TTFT ms | peak RSS MB | GPU MB | engine net sockets (max) |
|---|---|---|---|---|---|---|
| GPU | gemma-4-E2B-it-gpu.litertlm (2232 MB) | 40.6 | 103 | 2906 | 1953 | n/a |

Network during these runs: online.

## PC reference — RTX 4080 (`pc/bench_20261111_134125`)

| pair | ASR err | BLEU | chrF++ | COMET | total p50 / p95 ms |
|---|---|---|---|---|---|
| VI→EN | 1.59 | 50.96 | 65.25 | 87.59 | 507 / 768 |
| EN→VI | 7.85 | 43.72 | 60.56 | 84.38 | 319 / 458 |
| VI→KO | 5.08 | 39.45 | 32.29 | 88.14 | 454 / 679 |
| KO→VI | 7.86 | 22.75 | 40.8 | 83.17 | 167 / 266 |
| VI→ZH | 12.38 | 52.5 | 35.85 | 91.59 | 290 / 501 |
| ZH→VI | 3.74 | 46.62 | 63.55 | 93.16 | 213 / 350 |

## Runs

| time | run | kind | status | pairs | note |
|---|---|---|---|---|---|
| 2026-11-13 21:50 | [device_bench_20261113_215053_offline](qcs8550/device_bench_20261113_215053_offline/summary.md) | qcs8550 | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-13 16:30 | [power_20261113_163018](s25ultra/power_20261113_163018/summary.md) | pc | superseded |  |  |
| 2026-11-13 16:17 | [s25ultra_gpu_20261113_161738](s25ultra/s25ultra_gpu_20261113_161738/summary.md) | s25ultra-gpu | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-12 11:12 | [iq9075_cpu_20261112_111234](iq9075/iq9075_cpu_20261112_111234/summary.md) | iq9075-cpu | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-12 10:48 | [iq9075_gpu_20261112_104813](iq9075/iq9075_gpu_20261112_104813/summary.md) | iq9075-gpu | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-11 23:52 | [ventunoq_npu_20261111_235211](ventunoq/ventunoq_npu_20261111_235211/summary.md) | ventunoq-npu | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-11 23:10 | device_bench_20261111_231045__aborted_stopped_by_user | qcs8550 | archived |  | aborted stopped by user |
| 2026-11-11 22:13 | [ventunoq_npu_20261111_221351](ventunoq/ventunoq_npu_20261111_221351/summary.md) | ventunoq-npu | superseded | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-11 21:27 | [ventunoq_cpu_20261111_212707](ventunoq/ventunoq_cpu_20261111_212707/summary.md) | ventunoq-cpu | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-11 20:26 | [ventunoq_gpu_20261111_202616](ventunoq/ventunoq_gpu_20261111_202616/summary.md) | ventunoq-gpu | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-11 20:24 | [ventunoq_gpu_20261111_202421__smoke_single_call](archive/ventunoq_gpu_20261111_202421__smoke_single_call/summary.md) | ventunoq-gpu | archived | vi-en | smoke single call |
| 2026-11-11 19:42 | ventunoq_gpu_20261111_194227__aborted_old_punct_pipeline | ventunoq-gpu | archived |  | aborted old punct pipeline |
| 2026-11-11 19:39 | [ventunoq_cpu_20261111_193949__smoke_n3](archive/ventunoq_cpu_20261111_193949__smoke_n3/summary.md) | ventunoq-cpu | archived | vi-en, zh-vi | smoke n3 |
| 2026-11-11 19:35 | [ventunoq_gpu_20261111_193548__smoke_n3](archive/ventunoq_gpu_20261111_193548__smoke_n3/summary.md) | ventunoq-gpu | archived | vi-en, ko-vi | smoke n3 |
| 2026-11-11 16:16 | [device_bench_20261111_161624__superseded_online_2call](archive/device_bench_20261111_161624__superseded_online_2call/summary.md) | qcs8550 | archived | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi | superseded online 2call |
| 2026-11-11 16:02 | [device_tts_20261111_160254](qcs8550/device_tts_20261111_160254/summary.md) | qcs8550-tts | official | en, ko |  |
| 2026-11-11 15:58 | device_tts_20261111_155803__piper_failed_sherpa2 | qcs8550-tts | archived |  | piper failed sherpa2 |
| 2026-11-11 15:13 | [device_bench_20261111_151329__superseded_online_2call](archive/device_bench_20261111_151329__superseded_online_2call/summary.md) | qcs8550 | archived | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi | superseded online 2call |
| 2026-11-11 15:05 | device_bench_20261111_150546__crashed_empty_asr | qcs8550 | archived |  | crashed empty asr |
| 2026-11-11 14:57 | [device_bench_20261111_145722__smoke_n5](archive/device_bench_20261111_145722__smoke_n5/summary.md) | qcs8550 | archived | vi-en, en-vi | smoke n5 |
| 2026-11-11 13:41 | [bench_20261111_134125](pc/bench_20261111_134125/summary.md) | pc | official | vi-en, en-vi, vi-ko, ko-vi, vi-zh, zh-vi |  |
| 2026-11-11 12:29 | [bench_20261111_122950](pc/bench_20261111_122950/summary.md) | pc | superseded | en-vi |  |
| 2026-11-11 12:27 | [bench_20261111_122736](pc/bench_20261111_122736/summary.md) | pc | superseded | vi-en, en-vi |  |
| 2026-11-11 12:02 | [bench_20261111_120238](pc/bench_20261111_120238/summary.md) | pc | superseded | vi-en, en-vi |  |
| 2026-11-11 11:48 | [bench_20261111_114843](pc/bench_20261111_114843/summary.md) | pc | superseded | vi-en, en-vi, ko-vi |  |
| 2026-11-11 11:44 | [bench_20261111_114401](pc/bench_20261111_114401/summary.md) | pc | superseded | ko-vi |  |
| 2026-11-11 11:34 | [bench_20261111_113437](pc/bench_20261111_113437/summary.md) | pc | superseded | vi-en, en-vi |  |
| 2026-11-11 11:11 | [bench_20261111_111107](pc/bench_20261111_111107/summary.md) | pc | superseded | vi-en, en-vi |  |

## Component studies

- `components/asr/en_asr_candidates_t2.md`: 26 English ASR models compared on WER, size and latency.
- `components/mt/scoreboard.md`: every MT run with BLEU, chrF++ and COMET (Gemma quants, prompts, ASR inputs).
- `components/mt/prompt_ablation.json`: system-prompt variants.
- `components/tts/`: round-trip intelligibility on PC.
- `qcs8550/device_tts_20261111_160254/summary.md`: on-device TTS candidates against the 500 ms quota.
