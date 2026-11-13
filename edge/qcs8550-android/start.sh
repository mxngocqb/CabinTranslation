#!/system/bin/sh
# Start the on-device interpreter server and open the UI in the tablet's browser.
#   adb shell sh /data/local/tmp/cabin/start.sh [langs]     (default: vi,en,ko,zh)
D=/data/local/tmp/cabin
LANGS=${1:-vi,en,ko,zh}
cd $D
sh $D/stop.sh >/dev/null 2>&1
LD_LIBRARY_PATH=$D/lib nohup setsid ./cabin_edge --config config.json --serve 8080 --langs $LANGS > $D/out/server.log 2>&1 &
echo "starting cabin_edge (langs=$LANGS)…"
i=0
while [ $i -lt 120 ]; do
  grep -q "serving on" $D/out/server.log 2>/dev/null && break
  grep -qiE "failed|error" $D/out/server.log 2>/dev/null && { cat $D/out/server.log; exit 1; }
  sleep 1; i=$((i+1))
done
grep "loaded:" $D/out/server.log | tail -1
am start -a android.intent.action.VIEW -d http://127.0.0.1:8080/ >/dev/null 2>&1
echo "UI: http://127.0.0.1:8080/  (log: $D/out/server.log)"
