#!/usr/bin/env bash
# Serve the results dashboard locally (audio playback works in every browser this way).
#   bash dashboard/serve.sh [port]   ->  http://localhost:8000/dashboard/
# Serves the repo root so the page can reach ../results/<run>/wav/*.wav
cd "$(dirname "$0")/.."
PORT=${1:-8000}
echo "Dashboard: http://localhost:$PORT/dashboard/"
exec python3 -m http.server "$PORT" --bind 127.0.0.1
