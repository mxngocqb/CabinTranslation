# System logs of the QCS8550 tablet for the offline run

Collected over USB adb right after the run (device clock 04-22 19:19; it is not network-synced while offline —
see CLOCK-NOTE in ../network.log: device 18:51:35 = 2026-11-13 21:38:30 +07:00). Nothing is filtered or edited.

| File | Content |
|---|---|
| `logcat_all_buffers.txt` | Full `logcat -b all` dump (all buffers merged, 29,308 lines) |
| `logcat_main.txt`, `logcat_system.txt`, `logcat_events.txt`, `logcat_kernel.txt`, `logcat_radio.txt`, `logcat_crash.txt` | Each buffer separately (`logcat -d -v threadtime -b <buffer>`) |
| `logcat_run_window_18-45_to_19-05.txt` | All buffers, only the lines between 04-22 18:45 and 19:05 (the run was 18:49:27–19:03:38) |
| `bugreport_qcs8550_after_offline_run.zip` | Full `adb bugreport` (all logs, all dumpsys, system state) |
| `dumpsys_connectivity.txt`, `dumpsys_netstats.txt`, `collect_time_state.txt` | Connectivity state and per-interface traffic statistics at collection time |

Key system lines during the run (verbatim):

```
04-22 18:49:25.597  1944  4311 I ActivityManager: Force stopping vn.cabin.translate appid=10136 user=0: from pid 7035
04-22 18:48:44.924  2761  3341 D DhcpClient: Broadcasting DHCPDISCOVER
04-22 18:56:58.582  2761  3341 D DhcpClient: Broadcasting DHCPDISCOVER
04-22 18:58:05.065  1944  2596 I netstats_wifi_sample: [0,0,0,0,0,0,0,0,0,0,0,0,1776859085065]
```

- `Force stopping vn.cabin.translate` (18:49:25): the app was closed right before the benchmark started (18:49:27).
- `DhcpClient: Broadcasting DHCPDISCOVER` (18:48:44, 18:56:58): Wi-Fi kept asking for an address and got no answer — no network.
- `netstats_wifi_sample: [0,0,0,...]` (18:58:05): Android's own Wi-Fi traffic counters were zero during the run.
- `dumpsys_connectivity.txt`: `Active default network: none`.
