#!/usr/bin/env bash
# Install CabinTranslation into ./.venv
#   online : bash pc/install.sh
#   offline: bash pc/install.sh --offline     (uses ./wheels built by pc/make_wheelhouse.sh)
# GPU: if nvcc (CUDA >= 12) is found, llama-cpp-python is built with CUDA; otherwise CPU build.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3.11}
OFFLINE=0; [[ "${1:-}" == "--offline" ]] && OFFLINE=1

$PY -m venv .venv
source .venv/bin/activate
PIP_OPTS=""
[[ $OFFLINE == 1 ]] && PIP_OPTS="--no-index --find-links wheels"
pip install $PIP_OPTS -U pip wheel setuptools

if [[ $OFFLINE == 1 && -n "$(ls wheels/llama_cpp_python-*.whl 2>/dev/null)" ]]; then
  pip install $PIP_OPTS wheels/llama_cpp_python-*.whl
else
  NVCC=${CUDACXX:-$(command -v nvcc || true)}
  if [[ -n "$NVCC" ]]; then
    echo ">> building llama-cpp-python with CUDA ($NVCC)"
    CUDACXX=$NVCC CMAKE_ARGS="-DGGML_CUDA=on" pip install $PIP_OPTS --no-cache-dir llama-cpp-python==0.3.36
  else
    echo ">> building llama-cpp-python for CPU"
    CMAKE_ARGS="-DGGML_NATIVE=ON" pip install $PIP_OPTS --no-cache-dir llama-cpp-python==0.3.36
  fi
fi
pip install $PIP_OPTS -r pc/requirements.txt
pip install $PIP_OPTS --no-deps ./vendor/ViFastTts
echo ">> done. Models: python scripts/download_models.py (online, once).  Run: bash pc/run.sh"
