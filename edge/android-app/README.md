# CabinTranslation — Android app (APK)

A native Android app that wraps the same on-device engine (`cabin_edge`) as the QCS8550 build. Everything runs on
the phone or tablet: speech recognition, Gemma 4 E2B translation on the GPU, and speech synthesis. **Inference makes
no network calls.**

| Tested device | SoC / GPU | Android | Result |
|---|---|---|---|
| QCS8550 meeting tablet ("Tablet_Meeting") | QCS8550 / Adreno 740 | 13 | Works. Benchmark: [`results/qcs8550/`](../../results/qcs8550) |
| **Samsung Galaxy S25 Ultra** (SM-S938B) | Snapdragon 8 Elite (SM8750) / Adreno 830 | 17 | **Works.** End-to-end p50 0.51–1.16 s. Benchmark and power: [`results/s25ultra/`](../../results/s25ultra) |

## How it works

- **Capture**: `AudioRecord` (VOICE_RECOGNITION source, 16 kHz mono PCM16) feeds a **Silero VAD**. The VAD class is
  the official sherpa-onnx `Vad.kt`, used unchanged, with `libsherpa-onnx-jni.so` v1.13.8.
- **Turn-taking**:
  1. The speaker taps their button and talks.
  2. The VAD ends the utterance after 0.6 s of silence. Tapping again ends it early.
  3. The 0.3 s of audio before the VAD onset is kept, so the first syllable is never clipped.
- **Engine**: `libcabin_edge.so` is the `cabin_edge` binary from [`../qcs8550-android/`](../qcs8550-android).
  - The app starts it as a child process from its native-lib folder.
  - The app talks to it over loopback (`127.0.0.1:18181`).
  - It runs ASR (sherpa-onnx, CPU), Gemma 4 E2B (LiteRT-LM, GPU) and TTS (ViFastTts, Piper, Supertonic-2, Matcha; CPU).
- **Configuration**: `assets/config.template.json` and `assets/prompts.json` are generated from `cabin/` by
  `edge/tools/make_device_bundle.py`. Vietnamese input uses **one Gemma call**. At start-up the app rewrites the
  model paths to `/sdcard/CabinTranslation/models`.
- **Models** (2.8 GB) live in **`/sdcard/CabinTranslation/models`**, so the app needs "All files access"
  (MANAGE_EXTERNAL_STORAGE). `install.sh` grants it.

## 1. Connect the device (adb)

Use USB, or **Wireless debugging** if the phone must stay unplugged (for example, to measure power on battery).

```bash
adb pair <phone-ip>:<pairing-port> <pairing-code>     # once: Settings > Developer options > Wireless debugging > Pair device
adb connect <phone-ip>:<port>                         # e.g. adb connect 10.5.10.143:33041
adb devices -l                                        # shows the serial to use
```

The wireless-debugging **port changes** every time it is toggled or the phone reconnects. If a command reports
`device '...' not found`, run `adb devices -l` again and use the new serial.

## 2. Install

```bash
bash edge/android-app/install.sh                  # uses the only connected adb device
bash edge/android-app/install.sh <adb-serial>     # or a specific one
```

The script does the following:
1. Installs `dist/CabinTranslation.apk`.
2. Grants "All files access".
3. Puts the models in `/sdcard/CabinTranslation/models`:
   - If the device already has `/data/local/tmp/cabin/models` (from `make_device_bundle.py --push`), it copies them on the device, which is fast.
   - Otherwise it pushes them from the host: the repo's `models/` plus `~/edge/models/gemma-4-E2B-it-gpu.litertlm`, about 2.8 GB. Over Wi-Fi this takes about 15 min.
4. Restarts the app.

To push the models only:

```bash
python edge/tools/make_device_bundle.py --target android --serial <adb-serial> --push --models-only \
    --models-dir /sdcard/CabinTranslation/models
```

## 3. Use

1. Open **CabinTranslation**. It loads in about 20–25 s, then the header shows **"Sẵn sàng"** and the footer shows
   `Gemma 4 E2B trên GPU · nạp 20s · RAM … MB`.
2. Pick the partner language: English, 한국어 or 中文.
3. Tap the button of whoever is speaking (**Nói tiếng Việt** or **Speak English/Korean/Chinese**) and talk.
   The button turns red; when the speaker pauses, the VAD ends the turn (or tap the red button).
4. The button shows "Đang dịch… / Translating…". Then the sentence and its translation appear in the conversation
   (Vietnamese bubbles on the left, the partner's on the right), the translation is spoken, and the footer shows
   `ASR … ms · dịch … ms · TTS … ms · tổng … ms`.
5. Each card shows the translation for that person in large type and "Bạn vừa nói / You said: …" so the speaker
   can check what was heard. 🔊 on a card, or a tap on any bubble, replays a translation. **⟲ Lật** turns the
   partner card upside down for face-to-face use. Errors appear on the speaker's card in the speaker's language.

Step-by-step guide for non-developers (including install without adb): [docs/INSTALL_AND_USE.md](../../docs/INSTALL_AND_USE.md).

The header shows **Online / Offline**. For the offline demo, enable **airplane mode** first. The app keeps working.

**Test without a microphone.** Send a 16 kHz PCM16 WAV to the running app:

```bash
adb -s <serial> push sample_vi.wav /sdcard/Download/cabin_test_vi.wav
adb -s <serial> shell am start -f 0x20000000 -n vn.cabin.translate/.MainActivity \
    --es wav /sdcard/Download/cabin_test_vi.wav --es src vi --es tgt en
```

On the S25 Ultra: "Anh đang ở phòng nào để tôi kiểm tra." → "Which room are you in so I can check?", ASR 53 · MT 279 · TTS 228 · **total 562 ms**.

## 4. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "⚠️ Thiếu model" | `/sdcard/CabinTranslation/models` is empty or incomplete. Run `install.sh` again: it skips files that are already present |
| "⚠️ Cần quyền tệp" | `adb shell appops set vn.cabin.translate MANAGE_EXTERNAL_STORAGE allow`, then restart the app |
| `adb: device '...' not found` | The wireless-debugging port changed. Use the serial from `adb devices -l` |
| App stuck on loading | Check that `gemma-4-E2B-it-gpu.litertlm` is complete (2,340,870,772 bytes). Logs: `adb logcat \| grep -i cabin` |
| Files pushed into `Android/data/<pkg>` are unreadable | Shell-created files there are owned by uid 2000. Keep the models in `/sdcard/CabinTranslation/models` |

Every live utterance is saved as a WAV inside the app's private files (`files/live/`) for diagnosis.

## 5. Build the APK

```bash
bash edge/qcs8550-android/build.sh                          # engine + libs (NDK r27c)
python edge/tools/make_device_bundle.py --target android    # config.json / prompts.json from cabin/*.py
bash edge/android-app/prepare.sh                            # stage jniLibs/ + assets/ into the app
# build from a Linux-filesystem copy (Gradle is slow on /mnt/c)
B=~/build/android-app; rm -rf $B/app/src && cp -r edge/android-app/app/src $B/app/ && \
  cp edge/android-app/app/build.gradle.kts $B/app/ && cp edge/android-app/{build.gradle.kts,settings.gradle.kts,gradle.properties} $B/
(cd $B && JAVA_HOME=~/jdk17 ANDROID_HOME=~/android-sdk ~/gradle-8.10.2/bin/gradle assembleRelease)
cp $B/app/build/outputs/apk/release/app-release.apk edge/android-app/dist/CabinTranslation.apk
```

Toolchain: JDK 17, Android SDK 35, AGP 8.7.3, Kotlin 2.0.21, Gradle 8.10.2. Check the result:
`unzip -p dist/CabinTranslation.apk assets/config.template.json | grep punct_pass` should show `false`.

## 6. Benchmark and power on a phone

The app shares its engine with the adb build. Benchmarks therefore run the engine directly from `/data/local/tmp/cabin`
(close the app first: `adb shell am force-stop vn.cabin.translate`).

```bash
python edge/tools/make_device_bundle.py --target android --serial <serial> --push --no-models
adb -s <serial> shell 'mkdir -p /data/local/tmp/cabin/models && cp -r /sdcard/CabinTranslation/models/. /data/local/tmp/cabin/models/'
python edge/tools/run_device_bench.py --target android --serial <serial> --device-tag s25ultra --no-comet \
    --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi              # -> results/s25ultra/s25ultra_gpu_<ts>/
python edge/tools/power_bench_android.py --serial <serial> --tag s25ultra    # on battery -> results/s25ultra/power_<ts>/
```

`power_bench_android.py` needs **no root**:
- It samples `dumpsys battery` (`current now`, voltage, `Charge counter`) about once a second.
- It measures an idle baseline, then the full 905-utterance run.
- It reports the average power, the pipeline power (load − idle), and the energy per utterance.
- The charger must be unplugged; adb over Wi-Fi is fine.
