# On-device benchmark 20261113_224456

- Device: QCS8275 / Qualcomm Technologies, Inc. Monaco Monza addons, Ubuntu 24.04.4 LTS, kernel 6.8.0-1080-qcom, MemTotal:       15651800 kB, Adreno 623 (msm DRM, Mesa 25.2.8-0ubuntu0.24.04.2 Vulkan), CPU Cortex-A55 Cortex-A78C/ 8 cores
- Network at start: wifi_on=0 airplane=n/a internet=offline links=[end0=UP wlp3s0=DOWN]; at end: internet=offline
- LLM backend: npu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it_Qualcomm_QCS8275.litertlm, sampler=greedy, prefix_cache=False, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_en": 6349, "asr_ko": 4011, "asr_vi": 2942, "asr_zh": 6352, "mt": 659, "tts_en": 1032, "tts_ko": 709, "tts_vi": 739, "tts_zh": 2653}
- Peak process RSS (VmHWM): 4151 MB; /proc + DRM fdinfo peaks (MB): total_rss=4138, vm_hwm=4151, graphics=0
- Engine network sockets (non-loopback TCP/UDP of the cabin_edge process, sampled every ~1 s, whole run): max = 0

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 47.72 | 63.9 | 86.82 | 46.64 | 98.0 | 0.0 | 310.1 | 67.8 | 42.8 | 297.8 | 673.2 / 1064.3 |
| en-vi | 100 | 7.96 | 40.75 | 59.35 | 83.93 | 39.42 | 270.1 | 0.0 | 638.6 | 69.8 | 43.3 | 305.3 | 1125.2 / 1902.3 |
| vi-ko | 175 | 4.76 | 34.58 | 27.79 | 87.2 | 33.59 | 79.0 | 0.0 | 287.4 | 68.2 | 42.3 | 487.7 | 828.1 / 1287.2 |
| ko-vi | 177 | 7.69 | 22.32 | 41.55 | 83.47 | 21.86 | 121.1 | 0.0 | 290.1 | 67.6 | 42.4 | 124.6 | 513.6 / 822.6 |
| vi-zh | 176 | 12.33 | 51.72 | 35.75 | 90.6 | 48.51 | 96.6 | 0.0 | 296.2 | 67.3 | 42.5 | 402.3 | 719.5 / 1409.5 |
| zh-vi | 177 | 3.74 | 45.85 | 63.68 | 92.81 | 45.15 | 162.0 | 0.0 | 388.5 | 67.5 | 42.8 | 174.5 | 653.0 / 1315.7 |

## Raw system logs (board, unfiltered) — `syslog/`

Captured on the board by `edge/tools/board_syslog.sh` while the engine ran:

- `capture.txt` (141 bytes)
- `dmesg_during_run.log` (143,156 bytes)
- `dmesg_full.log` (143,156 bytes)
- `engine_processes_after_stop.txt` (0 bytes)
- `journal_boot_full.log` (1,873,123 bytes)
- `journal_during_run.log` (283,925 bytes)
- `network.log` (11,207 bytes)
- `network_state_end.txt` (5,766 bytes)
- `system_info.txt` (4,733 bytes)

- 15 s samples while the engine was running: **52**; engine non-loopback sockets: **max 0** over 48 samples

Verbatim `network.log` lines (first, middle, last):

```
2026-11-13 15:46:04 OFFLINE-REQUEST: sudo nmcli radio wifi off (ssh stays on the local link 192.168.5.2 60253 192.168.5.1 22)
2026-11-13 15:46:05 OFFLINE-CONFIRMED-START default_route=[] ipv4=[end0=192.168.5.1/24 docker0=172.17.0.1/16 ] wifi_radio=disabled ping8888=offline ping1111=offline
2026-11-13 15:52:24 engine_pid=32998 engine_net_sockets=0 engine_rss_kb=3576688 default_route=[] ipv4=[end0=192.168.5.1/24 docker0=172.17.0.1/16 ] ping8888=offline load=[3.57 2.40 1.37] mem_available_kb=11856336
2026-11-13 15:58:34 OFFLINE-CHECK-END default_route=[] ipv4=[end0=192.168.5.1/24 docker0=172.17.0.1/16 ] wifi_radio=disabled ping8888=offline ping1111=offline
2026-11-13 15:58:35 ONLINE-RESTORED: sudo nmcli radio wifi on
```

`journal_during_run.log`: 1819 lines (first and last 5):

```
2026-11-13T15:46:03.611888+00:00 ventunoq sudo[32833]:  arduino : PWD=/home/arduino ; USER=root ; COMMAND=/usr/bin/dmesg
2026-11-13T15:46:03.612572+00:00 ventunoq sudo[32833]: pam_unix(sudo:session): session opened for user root(uid=0) by arduino(uid=1000)
2026-11-13T15:46:03.624177+00:00 ventunoq sudo[32833]: pam_unix(sudo:session): session closed for user root
2026-11-13T15:46:03.691797+00:00 ventunoq sudo[32837]:  arduino : PWD=/home/arduino ; USER=root ; COMMAND=/usr/bin/journalctl -n 1
2026-11-13T15:46:03.692911+00:00 ventunoq sudo[32837]: pam_unix(sudo:session): session opened for user root(uid=0) by arduino(uid=1000)
…
2026-11-13T15:58:35.153898+00:00 ventunoq NetworkManager[1848]: <info>  [1794585515.1538] manager: rfkill: Wi-Fi now enabled by radio killswitch
2026-11-13T15:58:35.161278+00:00 ventunoq sudo[43360]: pam_unix(sudo:session): session closed for user root
2026-11-13T15:58:35.186738+00:00 ventunoq wpa_supplicant[1869]: dbus: fill_dict_with_properties dbus_interface=fi.w1.wpa_supplicant1.Interface.P2PDevice dbus_property=P2PDeviceConfig getter failed
2026-11-13T15:58:35.192313+00:00 ventunoq NetworkManager[1848]: <info>  [1794585515.1921] device (wlp3s0): supplicant interface state: internal-starting -> disconnected
2026-11-13T15:58:35.192663+00:00 ventunoq NetworkManager[1848]: <info>  [1794585515.1925] device (wlp3s0): state change: unavailable -> disconnected (reason 'supplicant-available', sys-iface-state: 'managed')
```

