#!/usr/bin/env bash
# AOT-compile the Gemma 4 E2B "NPU_Uncompiled" LiteRT-LM bundle for a Qualcomm SoC (x86-64 Linux host).
#   bash edge/tools/compile_npu_model.sh <SOC_MODEL> [input.litertlm] [output.litertlm]     e.g. QCS9075, QCS8275, SM8650
# Toolchain (official PyPI packages, separate venv ~/venvs/litert-aot):
#   python3.12 -m venv ~/venvs/litert-aot && . ~/venvs/litert-aot/bin/activate
#   pip install ai-edge-litert==2.3.0 ai-edge-litert-sdk-qualcomm==2.3.0 litert-lm-builder litert-torch==0.10.0 \
#       "torch<2.15" --extra-index-url https://download.pytorch.org/whl/cpu
#   (the SDK package ships QAIRT 2.50.0.260828 x86 libs; the Qualcomm compiler plugin needs libc++.so.1:
#    apt-get download libc++1-18 libc++abi1-18 libunwind-18 && dpkg-deb -x <deb> ~/edge/aot/libcxx/root)
# Input: https://huggingface.co/litert-community/gemma-4-E2B-it-litert-lm/resolve/main/gemma-4-E2B-it_NPU_Uncompiled.litertlm
# Measured 2026-11-12: QCS9075 compile 2 min 38 s, 13.5 GB peak RAM -> 3.77 GB file; QCS8275 -> 761 MB context.
set -euo pipefail
SOC=${1:?SOC model, e.g. QCS9075}
IN=${2:-$HOME/edge/models/gemma-4-E2B-it_NPU_Uncompiled.litertlm}
OUT=${3:-$HOME/edge/models/gemma-4-E2B-it_Qualcomm_${SOC}.litertlm}
. ~/venvs/litert-aot/bin/activate
SDKLIB=$(python -c "import ai_edge_litert_sdk_qualcomm as q; print(q.path_to_sdk_libs())")
export LD_LIBRARY_PATH=$HOME/edge/aot/libcxx/root/usr/lib/x86_64-linux-gnu:$SDKLIB
python -m litert_torch.generative.export_hf.experimental.litert_lm_npu_compiler.litert_lm_npu_compiler_main \
  --input_litertlm "$IN" --output_litertlm "$OUT" --backend qualcomm --soc_model "$SOC" "${@:4}"
ls -la "$OUT" && sha256sum "$OUT"
