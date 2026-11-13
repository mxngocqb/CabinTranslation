#!/bin/sh
# Raw system logs on a Linux board around a benchmark run (pushed and driven by run_device_bench.py --target linux).
#   sh /abs/path/board_syslog.sh start <dir>   start background capture (journal + kernel log follow, 15 s state samples)
#   sh /abs/path/board_syslog.sh stop  <dir>   stop it and dump the full journal / dmesg / system and network state
# Only coreutils, iproute2, journalctl and python3 (net_socks.py next to this script) are used.
D=$2
HERE=$(cd "$(dirname "$0")" && pwd)
# journal/dmesg may need privileges: use them directly if readable, else passwordless sudo, else whatever is visible
if dmesg >/dev/null 2>&1; then DM=dmesg; elif sudo -n dmesg >/dev/null 2>&1; then DM="sudo -n dmesg"; else DM=dmesg; fi
if sudo -n journalctl -n 1 >/dev/null 2>&1; then JC="sudo -n journalctl"; else JC=journalctl; fi
case $1 in
start)
  rm -rf "$D"; mkdir -p "$D"
  echo "$(date '+%F %T %z') capture started (journal: $JC, kernel log: $DM)" > "$D/capture.txt"
  nohup $JC -f -n 0 -o short-iso-precise --no-pager > "$D/journal_during_run.log" 2>&1 &
  echo $! > "$D/.pid_journal"
  nohup $DM -w -T > "$D/dmesg_during_run.log" 2>&1 &
  echo $! > "$D/.pid_dmesg"
  nohup sh "$HERE/board_syslog.sh" sample "$D" > /dev/null 2>&1 &
  echo $! > "$D/.pid_sample"
  ;;
sample)
  while :; do
    P=$(pidof cabin_edge_npu cabin_edge 2>/dev/null | cut -d' ' -f1)
    if [ -n "$P" ]; then
      S=$(python3 "$HERE/net_socks.py" "$P" 2>/dev/null || echo n/a)
      R=$(awk '/VmRSS/{print $2}' /proc/$P/status 2>/dev/null)
    else S=n/a; R=n/a; fi
    echo "$(date '+%F %T') engine_pid=${P:-none} engine_net_sockets=$S engine_rss_kb=$R" \
         "default_route=[$(ip route show default 2>/dev/null | tr '\n' ';')]" \
         "ipv4=[$(ip -o -4 addr 2>/dev/null | awk '$2!="lo"{print $2"="$4}' | tr '\n' ' ')]" \
         "ping8888=$(ping -c 1 -W 1 8.8.8.8 >/dev/null 2>&1 && echo online || echo offline)" \
         "load=[$(cut -d' ' -f1-3 /proc/loadavg)] mem_available_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)" \
         >> "$D/network.log"
    sleep 15
  done ;;
stop)
  for f in "$D"/.pid_*; do [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null; rm -f "$f"; done
  echo "$(date '+%F %T %z') capture stopped" >> "$D/capture.txt"
  $JC -b --no-pager -o short-iso-precise > "$D/journal_boot_full.log" 2>&1
  $DM -T > "$D/dmesg_full.log" 2>&1
  { echo "## date"; date '+%F %T %z'; echo "## uname"; uname -a; echo "## os-release"; cat /etc/os-release
    echo "## model"; tr -d '\0' < /proc/device-tree/model; echo; echo "## soc"; cat /sys/devices/soc0/machine 2>/dev/null
    echo "## lscpu"; lscpu; echo "## free -k"; free -k; echo "## df -h"; df -h; echo "## uptime"; uptime
    echo "## fastrpc / dri devices"; ls -l /dev/fastrpc* /dev/dri 2>/dev/null; echo "## id"; id; } > "$D/system_info.txt" 2>&1
  { echo "## ip addr"; ip addr; echo "## ip route"; ip route; echo "## ip -s link"; ip -s link
    echo "## nmcli device"; nmcli device status 2>/dev/null; echo "## ss -tunap"; ss -tunap 2>/dev/null; } > "$D/network_state_end.txt" 2>&1
  pgrep -af "[c]abin_edge" > "$D/engine_processes_after_stop.txt" 2>&1
  ;;
esac
