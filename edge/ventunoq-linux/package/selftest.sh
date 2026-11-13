#!/bin/sh
# Offline self-test: runs the full speech->speech pipeline on the bundled sample utterances (2 per direction)
# in batch mode and prints per-stage timings. Output wavs go to out/selftest_wav/.
#   sh selftest.sh [npu|gpu|cpu]
D=$(cd "$(dirname "$0")" && pwd); B=${1:-npu}; cd "$D"; mkdir -p out/selftest_wav
python3 - "$D" > out/selftest.jsonl <<'PY'
import json, os, sys
d = sys.argv[1]
for f in sorted(os.listdir(f"{d}/sample_input")):
    pair = f.split("__")[0]; s, t = pair.split("-")
    print(json.dumps({"id": f[:-4], "task": "e2e", "src": s, "tgt": t, "wav": f"{d}/sample_input/{f}"}))
PY
if [ "$B" = npu ]; then
  [ -e lib_npu/libcdsprpc.so ] || ln -sf /lib/aarch64-linux-gnu/libcdsprpc.so.1 lib_npu/libcdsprpc.so
  export LD_LIBRARY_PATH="$D/lib_npu:$D/lib" ADSP_LIBRARY_PATH="$D/lib_npu"; BIN=./cabin_edge_npu
else export LD_LIBRARY_PATH="$D/lib"; BIN=./cabin_edge; fi
$BIN --config "config_$B.json" --manifest out/selftest.jsonl --out out/selftest_result.jsonl --wav-dir out/selftest_wav > out/selftest.log 2>&1
python3 - <<'PY'
import json
for l in open("out/selftest_result.jsonl"):
    j = json.loads(l)
    if "summary" in j:
        s = j["summary"]; print(f"LLM {s.get('mt_backend')} | load {json.dumps({k: round(v) for k, v in s.get('load_ms', {}).items()})} | peak RSS {s.get('peak_rss_kb', 0)//1024} MB"); continue
    print(f"{j['id']:22s} {j.get('total_ms',0):6.0f} ms (ASR {j.get('asr_ms',0):.0f} / MT {j.get('mt_ms',0):.0f} / TTS {j.get('tts_ms',0):.0f})  {j.get('asr','')[:30]!r} -> {j.get('hyp','')[:40]!r}")
PY
echo "wavs: $D/out/selftest_wav/   log: $D/out/selftest.log"
