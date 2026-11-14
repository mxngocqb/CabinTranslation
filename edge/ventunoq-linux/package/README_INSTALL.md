# CabinTranslation — offline package for Arduino VENTUNO Q (Qualcomm QCS8275)

Two-way voice interpreter: **VI ⇄ EN, VI ⇄ KO, VI ⇄ ZH**. Everything runs on the board, with no network:
speech recognition (CPU) → Gemma 4 E2B translation (**Hexagon NPU**, or GPU / CPU) → speech synthesis (CPU).

## 1. Requirements (tested)

| Item | Requirement |
|---|---|
| Board | Arduino VENTUNO Q, Qualcomm QCS8275 (Hexagon v75 NPU, Adreno 623), 16 GB RAM |
| OS | Ubuntu 24.04 aarch64 (glibc 2.39), the board's stock image with FastRPC (`/dev/fastrpc-cdsp`, `libcdsprpc.so.1`) |
| User | Member of the `fastrpc` group (NPU) and `render` group (GPU). The stock `arduino` user is. |
| Disk | 4 GB free for the default package (NPU). +5 GB with `--all-backends`. |
| UI | Firefox on the board (HDMI monitor + USB/onboard mic and speaker), **or** a laptop through `ssh -L` |
| Extra files | QAIRT 2.50 libraries (Qualcomm), see step 2 |

## 2. Install (before disconnecting the network)

```bash
tar -xf CabinTranslation-VentunoQ-v1.1.tar && cd CabinTranslation-VentunoQ-v1.1
# QAIRT 2.50 runtime libs for the NPU (Qualcomm, not redistributed in the main package). Either:
tar -xf ../qairt-2.50-libs.tar -C lib_npu        # if you received qairt-2.50-libs.tar, or
python3 fetch_qairt.py lib_npu                   # online: range-reads 6 files from Qualcomm's QAIRT 2.50 SDK zip, SHA-256 verified
sh check.sh                                      # board, NPU access, libraries, SHA256SUMS -> "CHECK PASSED"
```

No compiler, Python packages, root access or system changes are needed.

## 3. Disconnect and run

```bash
nmcli radio wifi off; nmcli networking off       # or unplug Ethernet / disable Wi-Fi in the desktop menu
sh start.sh npu                                  # ~25 s: loads 4 ASR + 4 TTS + Gemma, prints "READY"
```

Open **http://127.0.0.1:8080/** in Firefox on the board. From a laptop, run
`ssh -L 8080:127.0.0.1:8080 arduino@<board-ip>` first and open the same address on the laptop.
Browsers only allow the microphone on `localhost` or https, so do not open the board's LAN address.

The ready state shows: `✅ Sẵn sàng · models loaded on device: en, ko, vi, zh · LLM npu`.

## 4. Use

1. Pick the partner language at the top: 🇬🇧 English, 🇰🇷 한국어 or 🇨🇳 中文.
2. Whoever speaks taps their own button once: the Vietnamese speaker **🎤 Nói** (blue, left), the partner
   **🎤 Speak / 말하기 / 说话** (green, right). Talk; recording stops by itself after a ~1 s pause
   (or tap the red button). Holding the button and releasing it also works.
3. The conversation shows what was heard and the translation, and the translation is spoken.
   **🔊 Replay** plays it again; tapping the time under a bubble shows ASR / MT (Gemma, NPU) / TTS.
4. **⇅ Đối diện** turns the screen into two halves for a device lying between two people; **⌨️** lets you type a
   sentence; **⏹ Tự dừng** switches the automatic stop off.

Step-by-step guide for every option: `docs/INSTALL_AND_USE.md` in the repository.

Other backends: `sh start.sh gpu` (Adreno 623 via Vulkan) or `sh start.sh cpu` (4 threads). These need
`--all-backends` packages, which contain the CPU and GPU Gemma files.

## 5. Verify without a microphone

```bash
sh selftest.sh npu        # 12 bundled utterances (2 per direction), full speech->speech, per-stage timings
```

## 6. Reset and troubleshooting

| Symptom | Fix |
|---|---|
| Restart | `sh stop.sh && sh start.sh npu` |
| `QAIRT 2.50 libraries missing` | Do step 2 (`qairt-2.50-libs.tar` or `fetch_qairt.py`) |
| `Qnn System library version 1.13.0 … minimum 1.14.0` | The system QAIRT 2.49 is being used. Run via `start.sh`, which sets `LD_LIBRARY_PATH`/`ADSP_LIBRARY_PATH` to `lib_npu` |
| `Cannot open /dev/fastrpc-cdsp` | Add the user to the `fastrpc` group, or use `sh start.sh gpu` / `cpu` |
| Microphone does nothing | Open the UI via `127.0.0.1` (not the LAN IP) and allow the microphone in Firefox |
| Logs | `out/server.log` (server), `out/selftest.log` (self-test) |

## 7. Contents

| Path | Purpose |
|---|---|
| `cabin_edge`, `cabin_edge_npu` | Native engine (one process: ASR → MT → TTS, HTTP server + batch mode). `_npu` links the LiteRT-LM 0.18 NPU runtime |
| `lib/` | sherpa-onnx 1.13.8 C API, ONNX Runtime 1.28.2, LiteRT-LM C API 0.19.1, ViFastTts FFI |
| `lib_npu/` | LiteRT-LM 0.18 NPU runtime + LiteRT Qualcomm dispatch (+ QAIRT 2.50 after step 2) |
| `config_{npu,gpu,cpu}.json`, `prompts.json` | Model paths (relative), MT system prompts |
| `models/` | ASR: Zipformer-30M (vi), X-ASR zh-en, Zipformer-ko · TTS: ViFastTts (vi), Piper lessac (en), Supertonic-2 (ko), Matcha+Vocos (zh) · MT: Gemma 4 E2B QCS8275 NPU build |
| `web/index.html` | Touch UI served at :8080 |
| `start.sh`, `stop.sh`, `check.sh`, `selftest.sh`, `fetch_qairt.py` | Launch, stop, pre-flight check, offline self-test, QAIRT fetch |
| `sample_input/` | 12 sample utterances from the organizer's sample set |
| `SHA256SUMS`, `VERSION` | Integrity and build ID |

Licenses: hynt Zipformer-30M ASR is CC BY-NC-ND. ViFastTts voice weights are CC BY-NC. Gemma is under the
Gemma Terms of Use. QAIRT is under Qualcomm's terms. Other components are Apache-2.0/MIT.
