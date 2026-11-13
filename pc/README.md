# PC reference pipeline (development & quality reference)

The Python pipeline (`cabin/`) with a Gradio UI. It is the **source of truth for prompts and text
normalization**. The device builds generate their `prompts.json` from `cabin/mt.py` and `cabin/normalize.py`.
It is also the reference against which the device builds are compared. It is **not** the submitted device build;
see [`edge/`](../edge/README.md) for that.

```
mic ─► ASR (sherpa-onnx int8, CPU) ─► text prep ─► Gemma 4 E2B (llama.cpp GGUF Q3_K_M, GPU/CPU) ─► TTS (ONNX, CPU) ─► speaker
```

| Stage | Language | Model | Size | Runtime |
|---|---|---|---|---|
| ASR | Vietnamese | hynt Zipformer-30M-RNNT-6000h (int8) | 30 MB | sherpa-onnx, CPU |
| ASR | English + Chinese | X-ASR Zipformer zh-en punct (int8). `lite`: Zipformer GigaSpeech. `quality`: Parakeet-TDT 0.6B v2 | 175 / 74 / 661 MB | sherpa-onnx, CPU |
| ASR | Korean | k2-fsa Zipformer Korean (int8) | 76 MB | sherpa-onnx, CPU |
| MT | all | Gemma 4 E2B-it GGUF Q3_K_M | 2.54 GB | llama.cpp (CUDA or CPU) |
| TTS | Vietnamese | ViFastTts Ngọc Huyền small | 86 MB | ONNX Runtime, CPU |
| TTS | English, Korean | Supertonic-3 int8 | 145 MB | sherpa-onnx, CPU |
| TTS | Chinese | Matcha zh-baker + Vocos 22 kHz | 129 MB | sherpa-onnx, CPU |

## Install

Requires Linux x86-64/aarch64, Python 3.11, and about 6 GB of disk. An NVIDIA GPU (CUDA 12.x) is optional.

```bash
bash pc/install.sh                      # creates ./.venv; builds llama-cpp-python with CUDA if nvcc is found
source .venv/bin/activate
python scripts/download_models.py       # ~3 GB into ./models  (--all for optional models)
bash pc/make_wheelhouse.sh              # optional: ./wheels for an offline install -> bash pc/install.sh --offline
docker build -f pc/Dockerfile -t cabin . && docker run --gpus all -p 7860:7860 -v $PWD/models:/app/models cabin
```

## Run (offline)

```bash
bash pc/run.sh            # VI ⇄ EN UI on http://127.0.0.1:7860   (bash pc/run.sh ko|zh)
CABIN_DEVICE=cpu bash pc/run.sh        # LLM on CPU
CABIN_PROFILE=lite bash pc/run.sh      # English ASR = GigaSpeech zipformer (74 MB)
CABIN_PROFILE=quality bash pc/run.sh   # English ASR = Parakeet 0.6B (661 MB)
CABIN_GGUF=<file.gguf> bash pc/run.sh  # another Gemma quant
```

To use it, press the microphone on your side and speak, then press stop. The translation is shown and spoken.
The partner selector switches between EN, KO and ZH. The status bar shows the latency of each stage.

## Benchmark and evaluations (run from the repo root)

```bash
python scripts/benchmark_e2e.py --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi   # -> results/pc/bench_<ts>/
python scripts/eval_asr.py --pair vi-en --model vi-30m                        # -> results/components/asr/
python scripts/eval_mt.py  --pair vi-en --input asr --asr vi-30m              # -> results/components/mt/
python scripts/eval_tts.py --lang vi                                          # -> results/components/tts/
python scripts/score_all.py                                                   # COMET + results/components/mt/scoreboard.md
python scripts/bench_en_asr.py --threads 2                                    # 26 English ASR candidates
python scripts/prompt_ablation.py                                             # system-prompt variants
```

Latest PC run (`results/pc/bench_20261111_134125`, RTX 4080 SUPER, Wi-Fi on): COMET 83.2–93.2 across the six
directions, latency p50 0.17–0.51 s. Tables are in [`results/README.md`](../results/README.md).

## Design choices measured here

- **Vietnamese ASR uses Zipformer-30M, not 150M.** WER is 1.59% vs 1.23%, but the model is 5× smaller.
- **Gemma uses Q3_K_M, not QAT Q4_0.** Quality is equal within noise, and the file is 24% smaller. Q2 loses about 20 BLEU.
- **ASR text preparation.** VI ASR outputs upper case with no punctuation, which costs BLEU 53.7 → 34.5. Lower-casing
  plus a `?`/`.` heuristic recovers BLEU to 48.6. A Gemma punctuation pass recovers it to 52.7. The device builds use
  the 1-call variant (lower-case + system-prompt note) for speed.
- **English ASR is X-ASR zh-en.** It won the comparison of 26 models (`results/components/asr/en_asr_candidates_t2.md`).
- **No few-shot prompting**, because it gave no gain.
