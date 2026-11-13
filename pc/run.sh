#!/usr/bin/env bash
# Start the PC reference UI (Gradio):  bash pc/run.sh [en|ko|zh] [--port 7860]
# Force CPU for the LLM:              CABIN_DEVICE=cpu bash pc/run.sh
# Use the QAT Q4_0 model instead:     CABIN_GGUF=models/gemma-4-E2B-it-qat-q4_0/gemma-4-E2B_q4_0-it.gguf bash pc/run.sh
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root: models/ and .venv live there
[[ -d .venv ]] && source .venv/bin/activate
export HF_HUB_OFFLINE=1 GRADIO_ANALYTICS_ENABLED=False
PARTNER="${1:-en}"; [[ $# -gt 0 ]] && shift

exec python pc/app.py --partner "$PARTNER" "$@"
