# CabinTranslation — Android app (Qualcomm QCS8550 tested)

A native Android app. Audio is captured the same way as the official sherpa-onnx Android sample (`vad-asr`):

- **Capture**: `AudioRecord` (VOICE_RECOGNITION source, 16 kHz mono PCM16) feeding a **Silero VAD**. The VAD class is the official `com/k2fsa/sherpa/onnx/Vad.kt` with `libsherpa-onnx-jni.so` from v1.13.8, unchanged.
- **Turn-taking**:
  1. The speaker taps their button and talks.
  2. The VAD ends the utterance after 0.6 s of silence; tapping again ends it early.
  3. 0.3 s of audio before the VAD onset is kept, so the first syllable is never clipped.
- **Engine**: `libcabin_edge.so` is the same `cabin_edge` binary benchmarked in [`../qcs8550-android/README.md`](../qcs8550-android/README.md), started as a child process from the app's native-lib dir. It covers:
  - ASR with sherpa-onnx
  - Gemma 4 E2B on the GPU via LiteRT-LM
  - TTS with ViFastTts, Piper, Supertonic and Matcha

  The app talks to it over loopback (127.0.0.1:18181). Inference makes no network calls.
- **Models** (2.9 GB) live in `/sdcard/CabinTranslation/models`, so the app needs "All files access". The `install.sh` script grants it.

## Install

```bash
bash edge/android-app/install.sh 10.5.14.32:5555     # installs dist/CabinTranslation.apk, grants access, copies models, starts app
```

The script copies models from `/data/local/tmp/cabin/models` on the device if present (`edge/tools/make_device_bundle.py --push`), or from a host folder given as the 2nd argument.

## Build

```bash
bash edge/qcs8550-android/build.sh && python edge/tools/make_device_bundle.py   # engine + libs + config
bash edge/android-app/prepare.sh                                   # stage jniLibs/assets
cd edge/android-app && gradle assembleRelease                      # JDK 17, Android SDK 35 (AGP 8.7.3, Kotlin 2.0.21)
```

## Use

1. Open **CabinTranslation**. It loads in about 25 s and shows "✅ Sẵn sàng · Gemma 4 E2B trên GPU".
2. Pick the partner language (English / 한국어 / 中文).
3. Tap the button of whoever is speaking and talk. The translation is shown and spoken.

Every live utterance is saved as a WAV inside the app's private files for diagnosis (`files/live/`).
