#!/usr/bin/env bash
# Cross-compile cabin_edge for Android arm64 and stage it with its shared libs in edge/qcs8550-android/dist/.
#   NDK=~/edge/android-ndk-r27c  LITERT_LM=~/edge/dl/litert_lm_c_api  SHERPA=~/edge/dl/sherpa-android
#   ORT=~/edge/dl/ort-android  VIFASTTTS=~/src/ViFastTts/rust  THIRD=~/edge/third_party  bash build.sh
set -euo pipefail
cd "$(dirname "$0")"
NDK=${NDK:-$HOME/edge/android-ndk-r27c}
LITERT_LM=${LITERT_LM:-$HOME/edge/dl/litert_lm_c_api}
# sherpa-onnx v1.13.8: last release with the built-in espeak-ng frontend (2.x dropped it -> Piper/Kitten need it)
SHERPA=${SHERPA:-$HOME/edge/dl/sherpa-1138}
SHERPA_INC=${SHERPA_INC:-$HOME/edge/third_party/sherpa1138}
ORT=${ORT:-$HOME/edge/dl/ort-android}
VIFASTTTS=${VIFASTTTS:-$HOME/src/ViFastTts/rust}
THIRD=${THIRD:-$HOME/edge/third_party}
TC=$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin
API=33

# 1) ViFastTts C ABI (Rust). sherpa-onnx's Android ORT is 1.28.2 and its symbols are versioned
#    (OrtGetApiBase@VERS_1.28.2), so both must share that one libonnxruntime.so: build the
#    load-dynamic ORT adapter against API 28 instead of 31.
sed -i 's/"load-dynamic", "api-31"/"load-dynamic", "api-28"/' "$VIFASTTTS/crates/adapters/outbound/ort/Cargo.toml"
( cd "$VIFASTTTS" && \
  CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=$TC/aarch64-linux-android$API-clang \
  CC_aarch64_linux_android=$TC/aarch64-linux-android$API-clang \
  AR_aarch64_linux_android=$TC/llvm-ar \
  ~/.cargo/bin/cargo build --release -p vifasttts-ffi --target aarch64-linux-android )

mkdir -p dist/lib
cp "$LITERT_LM/lib/android_arm64/liblitert-lm.so" dist/lib/
cp "$SHERPA/jniLibs/arm64-v8a/libsherpa-onnx-c-api.so" dist/lib/
cp "$SHERPA/jniLibs/arm64-v8a/libonnxruntime.so" dist/lib/   # ORT 1.28.2, shared by sherpa + ViFastTts
chmod u+w dist/lib/liblitert-lm.so
patchelf --set-soname liblitert-lm.so dist/lib/liblitert-lm.so  # prebuilt lib has no SONAME -> bionic verneed fails
cp "$VIFASTTTS/target/aarch64-linux-android/release/libvifasttts_ffi.so" dist/lib/

# 2) cabin_edge
$TC/aarch64-linux-android$API-clang++ -O2 -std=c++17 -fPIE -pie \
  -I"$LITERT_LM/include" -I"$SHERPA_INC" -I"$THIRD" -I"$VIFASTTTS/crates/adapters/inbound/ffi/include" \
  ../engine/cabin_edge.cc -o dist/cabin_edge \
  -Ldist/lib -llitert-lm -lsherpa-onnx-c-api -lvifasttts_ffi -llog \
  -static-libstdc++ -Wl,-rpath,'$ORIGIN/lib'
$TC/llvm-strip dist/cabin_edge
ls -la dist dist/lib
