#!/usr/bin/env bash
# Stage native libs + assets into the Android app (run after edge/qcs8550-android/build.sh and edge/tools/make_device_bundle.py).
set -euo pipefail
cd "$(dirname "$0")"
D=../qcs8550-android/dist
J=app/src/main/jniLibs/arm64-v8a
mkdir -p $J app/src/main/assets
cp $D/cabin_edge                 $J/libcabin_edge.so     # the engine, executed as a child process
cp $D/lib/liblitert-lm.so        $J/
cp $D/lib/libsherpa-onnx-c-api.so $J/
cp $D/lib/libonnxruntime.so      $J/                    # ORT 1.28.2: engine + sherpa JNI (VAD)
cp $D/lib/libvifasttts_ffi.so    $J/
cp ${SHERPA:-$HOME/edge/dl/sherpa-1138}/jniLibs/arm64-v8a/libsherpa-onnx-jni.so $J/   # Silero VAD (Kotlin API)
cp $D/config.json app/src/main/assets/config.template.json
cp $D/prompts.json app/src/main/assets/prompts.json
ls -la $J app/src/main/assets
