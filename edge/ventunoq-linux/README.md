# CabinTranslation on Arduino VENTUNO Q (Qualcomm QCS8275, Ubuntu 24.04 aarch64)

Same native pipeline as the QCS8550 tablet ([`../engine/cabin_edge.cc`](../engine/cabin_edge.cc), one process, no Python, no network calls),
cross-compiled for glibc. The LLM runs on **CPU**, **GPU** or **NPU**, chosen per run (`config_{cpu,gpu,npu}.json`).
ASR and TTS always run on the CPU with the same models as on QCS8550.

Device: QCS8275 (`Monaco`), 4× Cortex-A78C (cpu0–3, 2.1/2.36 GHz) + 4× Cortex-A55 (cpu4–7, 1.96 GHz), 15 GB RAM,
Adreno 623 (msm DRM + Mesa 25.2 Turnip Vulkan, no Qualcomm OpenCL/KGSL), Hexagon v75 NPU (QAIRT 2.49 installed).

| Stage | Runtime | Model |
|---|---|---|
| ASR vi / en+zh / ko | sherpa-onnx 1.13.8 linux-aarch64, CPU | as on QCS8550 |
| MT, GPU run | LiteRT-LM C API 0.19.1, ML Drift over WebGPU (Dawn) → Vulkan (Turnip) | `gemma-4-E2B-it-gpu.litertlm` (2.34 GB), ctx 384, prefix cache, greedy |
| MT, CPU run | LiteRT-LM C API 0.19.1, XNNPACK, 4 threads | `gemma-4-E2B-it.litertlm` (2.59 GB), ctx 1024, no prefix cache, top-p sampler with k=1 (argmax) |
| MT, NPU run | LiteRT-LM 0.18 NPU runtime + Qualcomm dispatch + QAIRT 2.50 (Hexagon v75), via `cabin_edge_npu` | `gemma-4-E2B-it_Qualcomm_QCS8275.litertlm` (2.72 GB), no prefix cache, greedy |
| TTS vi / en / ko / zh | ViFastTts FFI / Piper / Supertonic-2 / Matcha, CPU | as on QCS8550 |

## Folder

| File | Purpose |
|---|---|
| `build.sh` | Cross-compile `cabin_edge` (CPU/GPU, LiteRT-LM 1.0 C API) and `cabin_edge_npu` (LiteRT-LM 0.18 NPU runtime via [`../engine/litert_lm_compat_018.cc`](../engine/litert_lm_compat_018.cc)) → `dist/` |
| `start.sh`, `stop.sh` | Launch / stop on the board: `sh start.sh [npu\|gpu\|cpu]`, `HOST=0.0.0.0`, `HTTPS=1` |
| `https_proxy.py` | HTTPS front (self-signed) on :8443 so a phone/laptop on the LAN can use the microphone |
| `package.sh`, `package/` | Build the offline judge package on the board (`check.sh`, `selftest.sh`, `fetch_qairt.py`, `README_INSTALL.md`) |
| `dist/` | Staged build: binaries, `config_{cpu,gpu,npu}.json` (relative `./` paths), `prompts.json`, `lib/`, `lib_npu/` |

## Build, deploy, run

```bash
bash edge/ventunoq-linux/build.sh     # host: aarch64-linux-gnu-g++ (glibc 2.39), rust target aarch64-unknown-linux-gnu
python edge/tools/make_device_bundle.py --target linux --ssh "ssh -p 2222 arduino@localhost" --push   # -> ~/cabin
#   Gemma files are fetched on the board (2.3–2.7 GB each), e.g.
#   cd ~/cabin/models && curl -LO https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it_Qualcomm_QCS8275.litertlm
#   QAIRT 2.50 libs for the NPU: python3 package/fetch_qairt.py ~/cabin/lib_npu   (SHA-256 pinned)

# on the board
sh ~/cabin/start.sh npu                      # UI on http://127.0.0.1:8080/  (Firefox on the board)
HOST=0.0.0.0 HTTPS=1 sh ~/cabin/start.sh npu # + LAN: https://<board-ip>:8443/ (mic works), http://<board-ip>:8080/
sh ~/cabin/stop.sh

# benchmark (host orchestrates over ssh; the device runs everything)
python edge/tools/run_device_bench.py --target linux --ssh "ssh -p 2222 arduino@localhost" --backend npu --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi
# -> results/ventunoq/ventunoq_<backend>_<ts>/  (summary.md, summary.json, result.jsonl, rows.jsonl, wav/, meminfo_samples.json)
```

## Also runs on Qualcomm IQ-9075 EVK (QCS9075, Qualcomm Linux 1.9)

The same `dist/` binaries run on the IQ-9075 EVK without recompiling: aarch64, glibc 2.39, and libstdc++ is present.
Measured differences:

| | VENTUNO Q (QCS8275) | IQ-9075 (QCS9075) |
|---|---|---|
| OS | Ubuntu 24.04 | Qualcomm Linux 1.9 (Yocto, Wayland), root user, minimal Python 3, no `ss`/`ldd` |
| CPU / RAM | 4× A78C + 4× A55, 16 GB | 8× A78C, 32 GB |
| GPU driver | Mesa Turnip (Vulkan), Adreno 623 | Qualcomm KGSL + `libvulkan_adreno`, Adreno 663 |
| Gemma GPU (20-sentence smoke) | 7 tok/s, MT 1.4–6.3 s | **15.7 tok/s**, MT 1.28 s mean |
| Gemma CPU | 4 threads: 15 tok/s | **8 threads: 32 tok/s**, MT 0.97 s mean (4 thr: 23.6, 6 thr: 28.8) |
| Gemma NPU | QCS8275 AOT build, ~40 tok/s | **blocked**: the QCS8275 build is rejected (`Request feature arch with value 75 unsupported`, Hexagon v73); a self-compiled QCS9075 build loads but its 1.66 GB weight buffer cannot be mapped by FastRPC (`compute-cb: failed to map buffer`) |

```bash
python edge/tools/make_device_bundle.py --target linux --ssh "ssh -p 2222 root@localhost" --dev-dir /root/cabin --push
python edge/tools/make_device_bundle.py --target linux --mt-threads 8      # CPU config with 8 threads for the 8 big cores
python edge/tools/run_device_bench.py --target linux --ssh "ssh -p 2222 root@localhost" --dev-dir /root/cabin \
    --device-tag iq9075 --backend gpu --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi      # -> results/iq9075/
```

**NPU on QCS9075: what was tried.**

1. The Google QCS8275 build fails because it is an AOT context for Hexagon v75, and QCS9075 is v73.
2. A self-compiled build was made with [`../tools/compile_npu_model.sh`](../tools/compile_npu_model.sh) `QCS9075`. It uses the official PyPI
   `litert-torch` 0.10.0 `litert_lm_npu_compiler` with `ai-edge-litert` 2.3.0 and QAIRT 2.50. The compile takes 2 min 38 s,
   peaks at 13.5 GB RAM and writes a 3.77 GB file.
3. On the board that build gets past the architecture check: QNN 2.50 with the V73 skel loads it, and the cDSP is active.
   It then fails to map its 1.66 GB weight buffer through FastRPC.
4. The same toolchain gives a 761 MB context for QCS8275 (v75) and 1,859 MB for QCS9075 (v73). On v73 the int4 weights
   are expanded, and the resulting buffer exceeds what FastRPC can map on this Qualcomm Linux kernel.
5. `--disable_weight_sharing` makes it larger (2,125 MB).

On this board, use CPU (8 threads) or GPU.

GPU memory on KGSL is read from `/sys/class/kgsl/kgsl/proc/<pid>/kernel`. Engine network sockets are counted by
[`../tools/net_socks.py`](../tools/net_socks.py), which reads `/proc` and so needs no `ss`.

## Offline package for the judges

```bash
# on the board, from the deployed ~/cabin
bash package.sh ~/cabin ~/pkg v1.0           # -> CabinTranslation-VentunoQ-v1.0.tar (3.4 GB, NPU) + qairt-2.50-libs.tar (107 MB)
```

The package runs in place from any folder: `tar -xf` → `tar -xf qairt-2.50-libs.tar -C lib_npu` → `sh check.sh` →
`sh start.sh npu`. Its `README_INSTALL.md` is [package/README_INSTALL.md](package/README_INSTALL.md).
Verified on 2026-11-11 by installing into a fresh folder on the board:
- `check.sh`: PASSED.
- `selftest.sh`: 12/12 utterances, 0.41–1.58 s each.
- HTTP API: all six directions.

Memory on Linux is read from `/proc/<pid>/status` (VmRSS/VmHWM) and GPU buffers from the DRM fdinfo
(`drm-resident-memory`, summed over the process's render fds).

## What had to change vs. Android (all measured on the board)

- **GPU model file.** The generic `gemma-4-E2B-it.litertlm` loads on the Vulkan GPU path but produces garbage
  (128 tokens of nothing) and is slower (4.9 tok/s, 15.7 s load). `-gpu.litertlm` (also used on QCS8550) is correct.
  On CPU the opposite holds: `-gpu.litertlm` fails to create the engine (NOT_FOUND).
- **CPU sampler.** The CPU executor implements neither `GREEDY` nor `TOP_K` (`UNIMPLEMENTED: Sampler type: N not
  implemented yet`), and the model's default sampler is stochastic. `cabin_edge` uses `TOP_P` with k=1, which is argmax
  (`mt.sampler = "topk1"`, the default when `backend == "cpu"`).
- **CPU context.** `max_num_tokens` 384 and 512 fail with a `DYNAMIC_UPDATE_SLICE` prepare error; 1024 works.
- **CPU prefix cache is broken.** A cloned conversation keeps stale state, so each answer repeats the previous one.
  The CPU config therefore uses `prefix_cache: false` and prefills the ~190-token system prompt on every request
  (TTFT ≈ 1.2 s instead of ≈ 0.6 s).
- **CPU threads.** 4 threads under the default scheduler: 14.7 tok/s decode. 4 threads pinned to the A78C cores: 16.2.
  8 threads: 11.9 (the A55 cores slow the rest down). Pinned to the A55 cores: 3.6. Speculative decoding: no gain
  (15.1 tok/s pinned, 12.0 unpinned).
- `cabin_edge` now logs LiteRT-LM errors from `send_message` (they were silently empty before).

## NPU (Hexagon v75) — `cabin_edge_npu`

- Model: `gemma-4-E2B-it_Qualcomm_QCS8275.litertlm` (2.72 GB, sha256 `794339…0f06`), AOT-compiled, embeds
  **QAIRT 2.50.0.260828**. The 3.29 GB `…_qualcomm_qcs8275` (QAIRT 2.44) build used by Qualcomm's dragonwingdocs
  tutorial is no longer on Hugging Face (404).
- Runtime: the NPU-enabled LiteRT-LM 0.18 Linux build (`libLiteRtLm.so` + `libLiteRtDispatch_Qualcomm.so`,
  flutter_edge_ai `native-v0.18.0-e`, sha256 `29c2306f…3214`, HTP burst mode on). It has the **pre-1.0 C ABI**
  (functions return objects, no status codes), so `cabin_edge_npu` is linked with
  [`litert_lm_compat_018.cc`](litert_lm_compat_018.cc), which implements the 1.0 API on a dlopen'ed `libLiteRtLm.so`.
  No Bazel build needed.
- QNN: the board's apt QAIRT 2.49 is rejected (`Qnn System library version 1.13.0 … minimum supported version is
  1.14.0`). Six QAIRT 2.50 libs (`libQnnHtp`, `libQnnSystem`, `libQnnHtpV75Stub`, `libQnnHtpV75Skel`,
  `libQnnHtpPrepare`, `libQnnTFLiteDelegate`; ~110 MB, SHA-256 pinned) are range-read from Qualcomm's QAIRT
  Community SDK zip into `~/cabin/lib_npu` (`ADSP_LIBRARY_PATH` points there too). System libraries are untouched.
- **No prefix cache on NPU**: `conversation_clone` fails (`NPU executor's SetCurrentStep only supports rolling back
  one token at the end of decode`). `config_npu.json` sets `prefix_cache: false`.
- Smoke (20 sentences, text MT): decode **42–43 tok/s**, MT 0.2–0.75 s per sentence (GPU: 7 tok/s, 1.0–6.3 s);
  translations match GPU; `libQnnHtp` mapped and 1806 cDSP interrupts during the run.

```bash
python edge/tools/run_device_bench.py --target linux --ssh "ssh -p 2222 arduino@localhost" --backend npu --pairs ...
```

## Vietnamese input: one Gemma call (default since 2026-11-11)

`punct_pass: false` in every device config. The all-caps VI ASR output is lowercased, gets a rule-based `?`/`.`
(`prep_asr_text`), and goes to a single MT call whose system prompt adds `LOWERCASE_NOTE` (input is a lowercase,
unpunctuated transcript: infer sentence boundaries, questions and names). Previously a separate Gemma punctuation
pass ran first (2 calls). Earlier measurement: COMET 88.27 (1 call) vs 89.08 (2 calls) on 451 VI utterances. On QCS8275 GPU the
punctuation pass cost 1.4–1.8 s per VI utterance (VI→EN p50 3.70 s → 1.95 s on a 3-utterance smoke).
`make_device_bundle.py --punct-pass` restores the 2-call path.

## Results (full sample set, 905 utterances, VI input = 1 Gemma call, 2026-11-11)

Runs: `results/ventunoq/ventunoq_{gpu_20261111_202616, cpu_20261111_212707, npu_20261111_221351}`.
ASR/TTS are identical across runs (CPU), so the columns differ only by the LLM backend. BLEU for KO/ZH targets is
character-level. Wi-Fi was on during these runs. The owner does not allow disabling Wi-Fi on this remotely hosted
(QDC) board.

**Final NPU run of the packaged build:** `results/ventunoq/ventunoq_npu_20261113_224456`: installed from the judge package (`install/`), measured **fully offline** (`--offline`: Wi-Fi off, ssh over the local `end0` cable), with raw board logs in `syslog/` (journal, kernel log, 15 s network/socket samples). The earlier online run is in `results/archive/`.
- Translations are identical to the table below, because decoding is deterministic.
- p50 is 0.54–1.21 s and p95 0.88–2.03 s. That is about 5% slower than `221351`, because a 3.4 GB package transfer shared the board's link during the run.
- Peak RSS is 3,885 MB.
- **Engine network sockets: the maximum count of non-loopback TCP/UDP sockets is 0**, sampled every ~1 s over all 905 utterances.

| pair | ASR err | BLEU cpu / gpu / npu | COMET cpu / gpu / npu | MT ms cpu / gpu / npu | total p50 cpu / gpu / **npu** |
|---|---|---|---|---|---|
| VI→EN | WER 1.72 | 48.48 / 47.44 / 47.72 | 86.44 / 86.82 / 86.82 | 2062 / 1889 / 324 | 2.33 / 2.17 / **0.69 s** |
| EN→VI | WER 7.96 | 42.04 / 42.73 / 40.75 | 83.68 / 83.90 / 83.93 | 3497 / 4316 / 676 | 3.76 / 4.48 / **1.14 s** |
| VI→KO | WER 4.76 | 35.89 / 38.19 / 34.58 | 87.22 / 87.72 / 87.20 | 1986 / 1735 / 300 | 2.43 / 2.21 / **0.83 s** |
| KO→VI | CER 7.69 | 22.71 / 21.97 / 22.32 | 83.68 / 83.15 / 83.47 | 1916 / 1785 / 302 | 2.09 / 1.98 / **0.51 s** |
| VI→ZH | WER 12.33 | 51.94 / 51.62 / 51.72 | 90.55 / 90.66 / 90.60 | 1932 / 1878 / 310 | 2.28 / 2.10 / **0.74 s** |
| ZH→VI | CER 3.74 | 46.52 / 46.98 / 45.85 | 93.05 / 92.97 / 92.81 | 2257 / 2442 / 407 | 2.46 / 2.51 / **0.66 s** |

| | CPU (XNNPACK, 4 thr) | GPU (Adreno 623, Vulkan) | NPU (Hexagon v75) |
|---|---|---|---|
| Gemma file | 2.59 GB | 2.34 GB | 2.72 GB |
| decode tok/s | 12–15 | 6.8–7.3 | **40–41** |
| TTFT | 1.27–1.36 s (no prefix cache) | 0.52–0.80 s (prefix cache) | **0.07 s** (no prefix cache) |
| LLM load | 0.3 s | 3.4 s | 0.7 s |
| peak RSS (4 langs loaded) | 4.3 GB | 3.4 GB + 1.2 GB GPU | 4.2 GB |

- p95 total on NPU: 0.87–1.91 s. For comparison, QCS8550 (Adreno 740 GPU, 2-call VI): p50 0.63–1.44 s, p95 1.09–2.87 s.
- Quality is the same on all three backends: COMET is within ±0.5 per pair. The VI→ source pairs are below QCS8550
  (VI→EN −1.8 COMET / −7 BLEU) because these runs use the 1-call VI input; the non-VI pairs match QCS8550.
- Single failures (identical on all backends' ASR): EN-VI EV-2748 gives an empty ASR result. VI-KO VK-0300 is
  returned untranslated (Vietnamese) on CPU and GPU, but translated on NPU.
