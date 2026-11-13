#!/system/bin/sh
# Offline benchmark that runs entirely ON an Android device (no host connection needed while it runs).
# Started over adb with:  adb shell "nohup setsid sh /data/local/tmp/cabin/offline_bench_android.sh >/dev/null 2>&1 &"
# 1. waits until the device is OFFLINE: no active default network, pings to 8.8.8.8 and 1.1.1.1 fail, and no IPv4
#    address except loopback (the person disables Wi-Fi/data or turns on airplane mode; adb may stay on USB);
# 2. runs cabin_edge over out/manifest.jsonl (the 905 staged utterances, speech in -> speech out);
# 3. every ~15 s logs network state (airplane flag, Wi-Fi flag, ping, IPv4 interfaces) and the engine's memory;
#    takes screenshots (status bar with the airplane icon) at start / middle / end;
# 4. writes out/offline/DONE. Then turn airplane mode off and collect with edge/tools/collect_offline_run.py.
D=/data/local/tmp/cabin
O=$D/out/offline
cd $D
rm -rf $O && mkdir -p $O/wav $O/shots
L=$O/network.log
defnet() { dumpsys connectivity 2>/dev/null | grep -m1 "Active default network" | sed 's/.*: *//'; }
ext_ip() { ip -o -4 addr 2>/dev/null | awk '$2!="lo"{print $2"="$4}' | tr '\n' ' '; }
is_offline() {
  [ "$(defnet)" = none ] && [ -z "$(ext_ip)" ] && \
  ! ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1 && ! ping -c 1 -W 1 1.1.1.1 >/dev/null 2>&1
}
net() {
  echo "$(date '+%F %T') default_network=$(defnet) external_ipv4=[$(ext_ip)]" \
       "ping8888=$(ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1 && echo online || echo offline)" \
       "ping1111=$(ping -c 1 -W 1 1.1.1.1 >/dev/null 2>&1 && echo online || echo offline)" \
       "airplane=$(settings get global airplane_mode_on) wifi_setting=$(settings get global wifi_on)" $1
}
shot() { input keyevent KEYCODE_WAKEUP >/dev/null 2>&1; sleep 1; screencap -p "$O/shots/$1.png"; }
getprop ro.product.model > $O/device.txt; getprop ro.soc.model >> $O/device.txt; getprop ro.build.version.release >> $O/device.txt
echo "$(date '+%F %T') WAITING until the device is offline (disable Wi-Fi/data or enable airplane mode)" >> $L
i=0
until is_offline; do
  sleep 2; i=$((i+1)); [ $i -gt 900 ] && { echo "$(date '+%F %T') TIMEOUT waiting for offline state" >> $L; exit 1; }
done
net "OFFLINE-CONFIRMED-START" >> $L
shot start
LD_LIBRARY_PATH=lib ./cabin_edge --config config.json --manifest out/manifest.jsonl --out $O/result.jsonl \
    --wav-dir $O/wav > $O/device_stderr.log 2>&1 &
PID=$!
echo "$(date '+%F %T') engine pid=$PID" >> $L
k=0
while kill -0 $PID 2>/dev/null; do
  m=$(dumpsys meminfo $PID 2>/dev/null | grep -E "TOTAL PSS|Graphics:" | tr -s ' ' | tr '\n' ' ')
  n=$(ls $O/wav | wc -l)
  net "wav=$n mem=[$m]" >> $L
  k=$((k+1)); [ $k = 20 ] && shot middle
  sleep 15
done
wait $PID; RC=$?
net "OFFLINE-CHECK-END rc=$RC wav=$(ls $O/wav | wc -l)" >> $L
shot end
date '+%F %T' > $O/DONE
