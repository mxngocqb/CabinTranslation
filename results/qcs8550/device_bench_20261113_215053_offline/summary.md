# On-device benchmark 20261113_215053_offline

- Device: QCS8550 / Tablet Meeting, Android 13, MemTotal:       15626272 kB, GLES: Qualcomm, Adreno (TM) 740, OpenGL ES 3.2 V@0676.69 (GIT@1e9d6bfa18, Ia9449ce5a8, 1741259084) (Date:03/06/25)
- Network at start: wifi_on=1 airplane=0 internet=offline; at end: internet=offline
- LLM backend: gpu (LiteRT-LM, Gemma 4 E2B gemma-4-E2B-it-gpu.litertlm, sampler=greedy, prefix_cache=True, ctx=384); ASR/TTS: CPU
- Load time (ms): {"asr_en": 4410, "asr_ko": 2710, "asr_vi": 1868, "asr_zh": 4210, "mt": 8669, "tts_en": 753, "tts_ko": 802, "tts_vi": 834, "tts_zh": 2005}
- Peak process RSS (VmHWM): 4231 MB; dumpsys peaks (MB): total_pss=4197, graphics=840

| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTFT ms | decode tok/s | TTS ms | total ms p50 / p95 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| vi-en | 100 | 1.72 | 48.3 | 63.95 | 86.45 | 47.93 | 76.3 | 0.0 | 500.5 | 153.1 | 32.2 | 208.8 | 735.9 / 1203.7 |
| en-vi | 100 | 7.8 | 42.07 | 60.03 | 84.08 | 40.4 | 186.5 | 0.0 | 949.9 | 151.0 | 31.6 | 389.4 | 1434.5 / 2399.8 |
| vi-ko | 175 | 4.84 | 34.93 | 28.05 | 87.46 | 34.36 | 62.0 | 0.0 | 434.4 | 114.7 | 32.2 | 331.6 | 794.2 / 1309.9 |
| ko-vi | 177 | 7.86 | 22.51 | 41.09 | 83.41 | 22.1 | 86.8 | 0.0 | 427.8 | 112.7 | 32.5 | 137.0 | 618.6 / 1045.8 |
| vi-zh | 176 | 12.38 | 52.24 | 35.06 | 90.17 | 49.1 | 81.1 | 0.0 | 451.0 | 125.6 | 32.4 | 300.9 | 757.0 / 1488.1 |
| zh-vi | 177 | 3.74 | 45.72 | 63.6 | 92.92 | 44.57 | 113.0 | 0.0 | 569.0 | 114.8 | 32.5 | 199.6 | 795.8 / 1663.2 |

## Offline evidence (raw `network.log`, written on the device during the run)

- Checks every ~15 s: active default network, IPv4 addresses other than loopback, ping 8.8.8.8, ping 1.1.1.1 (plus the airplane-mode and Wi-Fi settings for reference). adb was connected over **USB** only.
- **55 of 55 samples during the run were fully offline** (no default network, no external IPv4, both pings failed).
- The device clock is not network-synced while offline: CLOCK-NOTE device clock is not network-synced while offline; host (wall) time at this line = 2026-11-13 21:38:30 +0700
- Screenshots taken by the device itself: `shots/start.png`, `shots/middle.png`, `shots/end.png`.

Verbatim log lines (start, first samples, middle, last samples, end):

```
2026-04-22 18:49:27 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 OFFLINE-CONFIRMED-START
2026-04-22 18:49:29 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 wav=0 mem=[ Graphics: 0 0 TOTAL PSS: 6456 TOTAL RSS: 21404 TOTAL SWAP (KB): 0 ]
2026-04-22 18:49:45 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 wav=0 mem=[ Graphics: 0 0 TOTAL PSS: 1109463 TOTAL RSS: 1137028 TOTAL SWAP (KB): 0 ]
2026-04-22 18:50:00 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 wav=0 mem=[ Graphics: 860596 860600 TOTAL PSS: 2364503 TOTAL RSS: 2395460 TOTAL SWAP (KB): 0 ]
2026-04-22 18:56:34 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 wav=394 mem=[ Graphics: 860640 860644 TOTAL PSS: 3646829 TOTAL RSS: 3678156 TOTAL SWAP (KB): 0 ]
2026-04-22 18:56:49 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 wav=416 mem=[ Graphics: 860640 860644 TOTAL PSS: 3655057 TOTAL RSS: 3686384 TOTAL SWAP (KB): 0 ]
2026-04-22 19:03:07 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 wav=885 mem=[ Graphics: 860640 860644 TOTAL PSS: 4297217 TOTAL RSS: 4328544 TOTAL SWAP (KB): 0 ]
2026-04-22 19:03:23 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 wav=904 mem=[ Graphics: 860640 860644 TOTAL PSS: 4287821 TOTAL RSS: 4319148 TOTAL SWAP (KB): 0 ]
2026-04-22 19:03:38 default_network=none external_ipv4=[] ping8888=offline ping1111=offline airplane=0 wifi_setting=1 OFFLINE-CHECK-END rc=0 wav=904
```

## System logs (Android logcat + bugreport, unfiltered) — `logcat/`

Full logcat of every buffer and a full `adb bugreport` were collected from the tablet after the run (see `logcat/README.md`).

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

