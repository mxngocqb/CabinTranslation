#!/bin/sh
# Pre-flight check for the VENTUNO Q package: board, NPU access, libraries, file integrity.
#   sh check.sh            (run from the package folder)
cd "$(dirname "$0")"
ok=1
say() { printf '%-44s %s\n' "$1" "$2"; }
soc=$(cat /sys/devices/soc0/machine 2>/dev/null); say "SoC (expect QCS8275)" "${soc:-unknown}"
[ "$(uname -m)" = aarch64 ] && say "arch" "aarch64 OK" || { say "arch" "$(uname -m) (need aarch64)"; ok=0; }
g=$(ldd --version 2>/dev/null | head -1 | grep -oE '[0-9]+\.[0-9]+$'); say "glibc (need >= 2.39)" "$g"
if [ -r /dev/fastrpc-cdsp ] && [ -w /dev/fastrpc-cdsp ]; then say "NPU device /dev/fastrpc-cdsp" "accessible"; else say "NPU device /dev/fastrpc-cdsp" "NOT accessible (add user to group fastrpc) - NPU mode unavailable"; fi
[ -e /lib/aarch64-linux-gnu/libcdsprpc.so.1 ] && say "FastRPC libcdsprpc.so.1" "found" || { say "FastRPC libcdsprpc.so.1" "missing - NPU mode unavailable"; }
[ -f lib_npu/libQnnHtp.so ] && say "QAIRT 2.50 libs (lib_npu)" "present" || say "QAIRT 2.50 libs (lib_npu)" "missing -> python3 fetch_qairt.py lib_npu (online) or untar qairt-2.50-libs.tar"
ls /dev/dri/renderD128 >/dev/null 2>&1 && say "GPU render node" "present" || say "GPU render node" "missing - GPU mode unavailable"
free -m | awk '/Mem:/{printf "%-44s %s MB\n", "RAM total", $2}'
df -m . | awk 'NR==2{printf "%-44s %s MB\n", "free disk here", $4}'
echo "verifying SHA256SUMS ..."
if sha256sum -c --quiet SHA256SUMS; then say "file integrity" "OK"; else say "file integrity" "FAILED"; ok=0; fi
[ $ok = 1 ] && echo "CHECK PASSED" || { echo "CHECK FAILED"; exit 1; }
