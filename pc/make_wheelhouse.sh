#!/usr/bin/env bash
# Build ./wheels so the judges can install with NO network: bash pc/install.sh --offline
# Run on a machine with the same OS/Python/CUDA as the target device, inside an activated venv
# where llama-cpp-python was already built (the built wheel is copied from the uv/pip cache).
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p wheels
pip download -d wheels pip wheel setuptools hatchling
grep -v '^llama-cpp-python' pc/requirements.txt | pip download -d wheels -r /dev/stdin
pip wheel --no-deps -w wheels ./vendor/ViFastTts
CUDACXX=${CUDACXX:-$(command -v nvcc || true)}
if [[ -n "$CUDACXX" ]]; then
  CUDACXX=$CUDACXX CMAKE_ARGS="-DGGML_CUDA=on" pip wheel --no-deps -w wheels llama-cpp-python==0.3.36
else
  CMAKE_ARGS="-DGGML_NATIVE=OFF" pip wheel --no-deps -w wheels llama-cpp-python==0.3.36
fi
du -sh wheels
