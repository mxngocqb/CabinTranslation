#!/bin/sh
# Start the offline interpreter server on the board (Linux aarch64, e.g. Arduino VENTUNO Q / QCS8275).
#   sh start.sh [npu|gpu|cpu] [langs]        defaults: npu  vi,en,ko,zh
#   HTTPS=1 sh start.sh npu                  also serve https://<board-ip>:8443/ for a phone/laptop on the LAN
#   HOST=0.0.0.0 sh start.sh npu             bind the HTTP server (port 8080) on all interfaces
# Then open http://127.0.0.1:8080/ in a browser ON THE BOARD (Firefox), or from a laptop through
#   ssh -L 8080:127.0.0.1:8080 <user>@<board>     and open http://127.0.0.1:8080/ on the laptop.
# (Browsers only allow the microphone on localhost/https, so do not open the board's LAN IP directly.)
D=$(cd "$(dirname "$0")" && pwd)
BACKEND=${1:-npu}
LANGS=${2:-vi,en,ko,zh}
cd "$D"
sh "$D/stop.sh" >/dev/null 2>&1
mkdir -p "$D/out"
if [ "$BACKEND" = npu ]; then
  # Gemma on the Hexagon NPU: LiteRT-LM 0.18 NPU runtime + Qualcomm dispatch + QAIRT 2.50 libs in lib_npu/
  BIN=./cabin_edge_npu
  # the Qualcomm libraries look for libcdsprpc.so; Ubuntu ships it as libcdsprpc.so.1
  [ -e "$D/lib_npu/libcdsprpc.so" ] || ln -sf /lib/aarch64-linux-gnu/libcdsprpc.so.1 "$D/lib_npu/libcdsprpc.so"
  if [ ! -f "$D/lib_npu/libQnnHtp.so" ]; then
    echo "QAIRT 2.50 libraries missing in $D/lib_npu (see README_INSTALL.md: python3 fetch_qairt.py lib_npu)"; exit 1
  fi
  export LD_LIBRARY_PATH="$D/lib_npu:$D/lib" ADSP_LIBRARY_PATH="$D/lib_npu"
else
  BIN=./cabin_edge
  export LD_LIBRARY_PATH="$D/lib"
fi
# HOST=0.0.0.0 exposes plain HTTP on the LAN (default 127.0.0.1). Browsers still need https or localhost for the mic.
nohup setsid $BIN --config "config_$BACKEND.json" --serve 8080 --host "${HOST:-127.0.0.1}" --langs "$LANGS" > "$D/out/server.log" 2>&1 &
echo "starting CabinTranslation (LLM on $BACKEND, langs=$LANGS) ..."
i=0
while [ $i -lt 180 ]; do
  grep -q "serving on" "$D/out/server.log" 2>/dev/null && break
  if ! pgrep -f "config_$BACKEND.json --serve" >/dev/null; then echo "server exited:"; tail -20 "$D/out/server.log"; exit 1; fi
  sleep 1; i=$((i+1))
done
grep "loaded:" "$D/out/server.log" | tail -1 | cut -c1-200
echo "READY: open http://127.0.0.1:8080/   (log: $D/out/server.log, stop: sh $D/stop.sh)"
if [ "${HOST:-127.0.0.1}" = 0.0.0.0 ]; then
  for ip in $(hostname -I); do case $ip in 172.17.*) ;; *) echo "LAN:   http://$ip:8080/  (mic needs https or localhost)";; esac; done
fi
if [ "${HTTPS:-0}" = 1 ]; then
  # LAN access with microphone (phone/laptop): https://<board-ip>:8443/ (self-signed certificate, accept once)
  nohup setsid python3 "$D/https_proxy.py" --port 8443 > "$D/out/https.log" 2>&1 &
  sleep 2
  for ip in $(hostname -I); do case $ip in 172.17.*) ;; *) echo "LAN:   https://$ip:8443/";; esac; done
fi
