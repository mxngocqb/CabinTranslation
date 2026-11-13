#!/usr/bin/env bash
# Cross-compile cabin_edge for Linux aarch64 (glibc; e.g. Arduino VENTUNO Q / QCS8275, Ubuntu 24.04)
# and stage it with its shared libs in edge/ventunoq-linux/dist/. Same source as the Android build.
#   LITERT_LM=~/edge/dl/litert_lm_c_api  SHERPA=~/edge/dl/sherpa-1138-linux-aarch64/...-shared-cpu-lib
#   VIFASTTTS=~/src/ViFastTts/rust  THIRD=~/edge/third_party  bash edge/ventunoq-linux/build.sh
# Host needs: g++-aarch64-linux-gnu (glibc 2.39 cross = Ubuntu 24.04 target), rustup target
# aarch64-unknown-linux-gnu, patchelf.
set -euo pipefail
cd "$(dirname "$0")"
LITERT_LM=${LITERT_LM:-$HOME/edge/dl/litert_lm_c_api}
SHERPA=${SHERPA:-$HOME/edge/dl/sherpa-1138-linux-aarch64/sherpa-onnx-v1.13.8-linux-aarch64-shared-cpu-lib}
SHERPA_INC=${SHERPA_INC:-$HOME/edge/third_party/sherpa1138}
VIFASTTTS=${VIFASTTTS:-$HOME/src/ViFastTts/rust}
THIRD=${THIRD:-$HOME/edge/third_party}
CXX=${CXX:-aarch64-linux-gnu-g++}
export PATH="$PATH:$HOME/venvs/cabin/bin"   # patchelf comes from pip in the dev venv

# 1) ViFastTts C ABI. sherpa-onnx 1.13.8 linux-aarch64 ships ORT 1.28.2 (versioned symbols), so the
#    load-dynamic adapter is built against api-28, as on Android.
sed -i 's/"load-dynamic", "api-31"/"load-dynamic", "api-28"/' "$VIFASTTTS/crates/adapters/outbound/ort/Cargo.toml"
( cd "$VIFASTTTS" && \
  CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc \
  CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc \
  AR_aarch64_unknown_linux_gnu=aarch64-linux-gnu-ar \
  ~/.cargo/bin/cargo build --release -p vifasttts-ffi --target aarch64-unknown-linux-gnu )

mkdir -p dist/lib
cp "$LITERT_LM/lib/linux_arm64/liblitert-lm.so" dist/lib/
cp "$SHERPA/lib/libsherpa-onnx-c-api.so" "$SHERPA/lib/libonnxruntime.so" dist/lib/
chmod u+w dist/lib/*.so
patchelf --set-soname liblitert-lm.so dist/lib/liblitert-lm.so   # prebuilt lib has no SONAME
cp "$VIFASTTTS/target/aarch64-unknown-linux-gnu/release/libvifasttts_ffi.so" dist/lib/

# 2) cabin_edge (no -llog on glibc)
$CXX -O2 -std=c++17 -fPIE -pie \
  -I"$LITERT_LM/include" -I"$SHERPA_INC" -I"$THIRD" -I"$VIFASTTTS/crates/adapters/inbound/ffi/include" \
  ../engine/cabin_edge.cc -o dist/cabin_edge \
  -Ldist/lib -llitert-lm -lsherpa-onnx-c-api -lvifasttts_ffi -lpthread \
  -static-libstdc++ -static-libgcc -Wl,-rpath,'$ORIGIN/lib'
aarch64-linux-gnu-strip dist/cabin_edge
ls -la dist dist/lib

# 3) cabin_edge_npu: same source linked against the NPU-enabled LiteRT-LM 0.18 runtime (libLiteRtLm.so +
#    LiteRT's Qualcomm dispatch lib) from flutter_edge_ai native-v0.18.0-e (litertlm-linux_arm64.tar.gz,
#    sha256 29c2306f…3214) — the runtime used by the Google x Qualcomm VENTUNO Q hackathon example.
#    That runtime has the pre-1.0 C ABI (returns objects, no status codes), so cabin_edge is linked with
#    litert_lm_compat_018.cc, which implements the 1.0 API used here on top of a dlopen'ed libLiteRtLm.so.
#    It also lacks the speculative-decoding API -> CABIN_NO_SPECULATIVE.
NPU_RT=${NPU_RT:-$HOME/edge/dl/litertlm-npu-0.18.0e}
if [ -f "$NPU_RT/libLiteRtLm.so" ]; then
  mkdir -p dist/lib_npu
  cp "$NPU_RT"/{libLiteRtLm.so,libLiteRt.so,libGemmaModelConstraintProvider.so,libLiteRtDispatch_Qualcomm.so} dist/lib_npu/
  $CXX -O2 -std=c++17 -fPIE -pie -DCABIN_NO_SPECULATIVE \
    -I"$LITERT_LM/include" -I"$SHERPA_INC" -I"$THIRD" -I"$VIFASTTTS/crates/adapters/inbound/ffi/include" \
    ../engine/cabin_edge.cc ../engine/litert_lm_compat_018.cc -o dist/cabin_edge_npu \
    -Ldist/lib -lsherpa-onnx-c-api -lvifasttts_ffi -lpthread -ldl \
    -static-libstdc++ -static-libgcc -Wl,-rpath,'$ORIGIN/lib_npu:$ORIGIN/lib'
  aarch64-linux-gnu-strip dist/cabin_edge_npu
  ls -la dist/cabin_edge_npu dist/lib_npu
fi
