#!/usr/bin/env bash
# Build the offline QCS8550 (Android) package: APK + models + adb install script.
#   bash edge/android-app/package.sh [OUT_DIR=../CabinTranslation_submission/qcs8550] [VERSION=v1.1]
# -> OUT_DIR/CabinTranslation-QCS8550-<VERSION>/ and .tar + SHA256SUMS.txt
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
OUTD=${1:-$ROOT/../CabinTranslation_submission/qcs8550}; VER=${2:-v1.1}
M=$ROOT/models; GEMMA=${GEMMA:-$HOME/edge/models/gemma-4-E2B-it-gpu.litertlm}
P=$OUTD/CabinTranslation-QCS8550-$VER
rm -rf "$P"; mkdir -p "$P/models"
cp "$HERE/dist/CabinTranslation.apk" "$P/"
cp "$ROOT/docs/INSTALL_AND_USE.md" "$P/"
cp "$GEMMA" "$P/models/"
# exactly the files the device config references (edge/tools/make_device_bundle.py MODEL_FILES, minus unused Supertonic-3)
cp_rel() { mkdir -p "$P/models/$1/$(dirname "$2")"; cp -r "$M/$1/$2" "$P/models/$1/$(dirname "$2")/"; }
for f in encoder-epoch-20-avg-10.int8.onnx decoder-epoch-20-avg-10.int8.onnx joiner-epoch-20-avg-10.int8.onnx config.json; do cp_rel Zipformer-30M-RNNT-6000h $f; done
for f in encoder-epoch-99-avg-1.int8.onnx decoder-epoch-99-avg-1.onnx joiner-epoch-99-avg-1.int8.onnx tokens.txt; do cp_rel sherpa-onnx-x-asr-zipformer-transducer-zh-en-punct-int8-2026-06-03 $f; done
for f in encoder-epoch-99-avg-1.int8.onnx decoder-epoch-99-avg-1.int8.onnx joiner-epoch-99-avg-1.int8.onnx tokens.txt; do cp_rel sherpa-onnx-zipformer-korean-2024-06-24 $f; done
for f in onnx/acoustic.onnx onnx/vocoder.onnx; do cp_rel vifasttts-ngochuyen-small $f; done
for f in en_US-lessac-medium.onnx tokens.txt espeak-ng-data; do cp_rel vits-piper-en_US-lessac-medium $f; done
for f in duration_predictor.int8.onnx text_encoder.int8.onnx vector_estimator.int8.onnx vocoder.int8.onnx tts.json unicode_indexer.bin voice.bin; do cp_rel sherpa-onnx-supertonic-tts-int8-2026-03-06 $f; done
for f in model-steps-3.onnx lexicon.txt tokens.txt phone.fst date.fst number.fst dict; do cp_rel matcha-icefall-zh-baker $f; done
cp "$M/vocos-22khz-univ.onnx" "$P/models/"

cat > "$P/install.sh" <<'INS'
#!/usr/bin/env bash
# Offline install on a Qualcomm QCS8550 Android tablet (tested: Android 13, Adreno 740). Needs only adb (USB is fine).
#   bash install.sh [adb-serial]
set -euo pipefail
cd "$(dirname "$0")"
A="adb"; [ -n "${1:-}" ] && A="adb -s $1"
echo "[1/5] installing CabinTranslation.apk"
$A install -r -g CabinTranslation.apk
echo "[2/5] granting file access (models live in shared storage)"
$A shell appops set vn.cabin.translate MANAGE_EXTERNAL_STORAGE allow
echo "[3/5] pinning landscape (meeting-tablet stands report a wrong orientation)"
$A shell settings put system accelerometer_rotation 0
$A shell settings put system user_rotation 0
echo "[4/5] copying models to /sdcard/CabinTranslation/models (~2.8 GB, a few minutes over USB)"
$A shell mkdir -p /sdcard/CabinTranslation/models
$A push models/. /sdcard/CabinTranslation/models/
echo "[5/5] starting the app (first start loads the models, ~25 s)"
$A shell am start -n vn.cabin.translate/.MainActivity
echo "Done. Turn on airplane mode: everything runs on the device."
INS
chmod +x "$P/install.sh"

cat > "$P/README_INSTALL.md" <<'RD'
# CabinTranslation for Qualcomm QCS8550 (Android) — offline install

Team **BKMEETING** · OneVoice AI Challenge 2026 · Phase 3 prototype

## What is inside

| Path | What it is |
|---|---|
| `CabinTranslation.apk` | Android app `vn.cabin.translate`. It contains the native engine `libcabin_edge.so` and the Silero VAD. |
| `models/` | All model files, about 2.8 GB. It holds Gemma 4 E2B `gemma-4-E2B-it-gpu.litertlm` and the sherpa-onnx ASR/TTS models. |
| `install.sh` | One-command install over adb. |
| `INSTALL_AND_USE.md` | Full step-by-step guide (also for installing without adb), conversation how-to, troubleshooting. |

## Requirements

- An Android tablet or phone with a Qualcomm Snapdragon chip and Adreno GPU, Android 10 or later, at least 8 GB RAM and 4 GB free storage.
  Tested: QCS8550 meeting tablet (Android 13, Adreno 740) and Samsung Galaxy S25 Ultra (SM8750, Android 17, Adreno 830).
- A PC with `adb`. Connect over USB with USB debugging enabled. No network is needed.

## Install (offline)

```bash
bash install.sh                 # or: bash install.sh <adb-serial>
```

Manual equivalent:
1. `adb install -r -g CabinTranslation.apk`
2. `adb shell appops set vn.cabin.translate MANAGE_EXTERNAL_STORAGE allow`
3. `adb push models/. /sdcard/CabinTranslation/models/`

**Updating from v1.0:** the models are unchanged. Only run `adb install -r -g CabinTranslation.apk`.

## Use

1. Turn on **airplane mode**. Nothing needs the network.
2. Open **CabinTranslation**. It shows "Sẵn sàng · Gemma 4 E2B trên GPU" after about 25 s.
3. Pick the partner language at the top: English / 한국어 / 中文.
4. Whoever speaks taps their own button (blue **Nói tiếng Việt** on the left, green **Speak …** on the right) and talks.
   The button turns red while listening; when the speaker pauses, the turn ends by itself (or tap the red button).
5. The button shows "Đang dịch… / Translating…". Then the sentence and its translation appear in the conversation
   (Vietnamese bubbles left, partner right) and the translation is read aloud.
6. Each card shows the translation for that person in large type, and "Bạn vừa nói / You said: …" so the speaker can
   check what was heard. 🔊 on a card, or a tap on any bubble, replays a translation. **⟲ Lật** turns the partner card
   upside down when the tablet lies between two people. Errors appear on the speaker's card, in the speaker's language.

The pipeline runs fully on the device:
- **ASR**: sherpa-onnx with Zipformer VI / X-ASR EN+ZH / Zipformer KO, on the CPU.
- **Translation**: Gemma 4 E2B via LiteRT-LM on the **GPU**.
- **TTS**: ViFastTts VI / Piper EN / Supertonic-2 KO / Matcha ZH, on the CPU.

## Check without speaking (optional)

```bash
adb push some_16k_pcm16.wav /sdcard/Download/t.wav
adb shell am start -f 0x20000000 -n vn.cabin.translate/.MainActivity --es wav /sdcard/Download/t.wav --es src vi --es tgt en
```

## Licenses of bundled models

| Model | License |
|---|---|
| Gemma 4 | Gemma Terms of Use |
| hynt Zipformer VI | CC BY-NC-ND 4.0 |
| ViFastTts voice | CC BY-NC 4.0 |
| X-ASR | Apache-2.0 |
| Piper lessac | MIT voice |
| Supertonic | see upstream |
| Matcha / Vocos | Apache-2.0 / MIT |

The package is for non-commercial evaluation only.
RD
cd "$OUTD"
tar -cf "CabinTranslation-QCS8550-$VER.tar" "CabinTranslation-QCS8550-$VER"
sha256sum "CabinTranslation-QCS8550-$VER.tar" > SHA256SUMS.txt
cp "$P/README_INSTALL.md" "$OUTD/"
du -sh "$P" "CabinTranslation-QCS8550-$VER.tar"; cat SHA256SUMS.txt
