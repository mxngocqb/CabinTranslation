#!/bin/bash
# Build the offline VENTUNO Q package from a deployed board folder (run ON the board).
#   bash package.sh [SRC=~/cabin] [OUT_DIR=~] [VERSION=v1.1]  [--all-backends] [--with-qairt]
#   -> OUT_DIR/CabinTranslation-VentunoQ-<VERSION>/ (+ .tar) ; qairt-2.50-libs.tar is built separately.
# Default contents: NPU Gemma only. --all-backends also adds the CPU and GPU Gemma files (+4.9 GB).
# QAIRT 2.50 libs (Qualcomm) are NOT put into the main package unless --with-qairt.
set -euo pipefail
SRC=${1:-$HOME/cabin}; OUTD=${2:-$HOME}; VER=${3:-v1.1}; ALL=0; QAIRT=0
for x in "$@"; do [ "$x" = --all-backends ] && ALL=1; [ "$x" = --with-qairt ] && QAIRT=1; done
P=$OUTD/CabinTranslation-VentunoQ-$VER
HERE=$(cd "$(dirname "$0")" && pwd)
rm -rf "$P"; mkdir -p "$P"/{lib,lib_npu,models,web,sample_input,cache,out}
cp "$SRC"/cabin_edge "$SRC"/cabin_edge_npu "$SRC"/start.sh "$SRC"/stop.sh "$SRC"/https_proxy.py "$SRC"/prompts.json "$SRC"/config_{cpu,gpu,npu}.json "$P"/
cp "$SRC"/web/index.html "$P"/web/
cp "$SRC"/lib/*.so "$P"/lib/
cp "$SRC"/lib_npu/{libLiteRtLm.so,libLiteRt.so,libGemmaModelConstraintProvider.so,libLiteRtDispatch_Qualcomm.so} "$P"/lib_npu/
QLIBS="libQnnHtp.so libQnnSystem.so libQnnHtpV75Stub.so libQnnHtpV75Skel.so libQnnHtpPrepare.so libQnnTFLiteDelegate.so"
[ $QAIRT = 1 ] && for f in $QLIBS; do cp "$SRC/lib_npu/$f" "$P/lib_npu/"; done
cp "$HERE"/package/{check.sh,selftest.sh,fetch_qairt.py,README_INSTALL.md} "$P"/
[ -f "$HERE/../../docs/INSTALL_AND_USE.md" ] && cp "$HERE/../../docs/INSTALL_AND_USE.md" "$P"/   # full guide (when run from a repo checkout)
# models referenced by the configs
python3 - "$SRC" "$P" "$ALL" <<'PY'
import json, os, shutil, sys
src, dst, allb = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
need = set()
def walk(j):
    if isinstance(j, str) and j.startswith("./models/"):
        for part in j.split(","): need.add(part[2:])
    elif isinstance(j, dict): [walk(v) for v in j.values()]
    elif isinstance(j, list): [walk(v) for v in j]
for b in (("cpu", "gpu", "npu") if allb else ("npu",)):
    walk(json.load(open(f"{src}/config_{b}.json")))
gemma_other = set()
if not allb:   # keep the ASR/TTS of all configs but only the NPU Gemma
    for b in ("cpu", "gpu"):
        c = json.load(open(f"{src}/config_{b}.json")); gemma_other.add(c["mt"]["model"][2:])
        walk({k: v for k, v in c.items() if k != "mt"})
for rel in sorted(need - gemma_other):
    s, d = os.path.join(src, rel), os.path.join(dst, rel)
    os.makedirs(os.path.dirname(d), exist_ok=True)
    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)
print("models:", len(need - gemma_other), "paths")
PY
# 2 sample utterances per direction (organizer sample set, 16 kHz PCM16)
for p in vi-en en-vi vi-ko ko-vi vi-zh zh-vi; do
  for w in $(ls "$SRC"/data/$p/*.wav | head -2); do cp "$w" "$P/sample_input/${p}__$(basename "$w")"; done
done
echo "$VER $(date -u +%Y-%m-%dT%H:%MZ) $(sha256sum "$P"/cabin_edge | cut -c1-12)" > "$P"/VERSION
chmod +x "$P"/*.sh "$P"/cabin_edge "$P"/cabin_edge_npu
( cd "$P" && find . -type f ! -name SHA256SUMS ! -path './out/*' ! -path './cache/*' -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS )
( cd "$OUTD" && tar -cf "CabinTranslation-VentunoQ-$VER.tar" "CabinTranslation-VentunoQ-$VER" )
( cd "$SRC/lib_npu" && tar -cf "$OUTD/qairt-2.50-libs.tar" $QLIBS )
du -sh "$P" "$OUTD/CabinTranslation-VentunoQ-$VER.tar" "$OUTD/qairt-2.50-libs.tar"
