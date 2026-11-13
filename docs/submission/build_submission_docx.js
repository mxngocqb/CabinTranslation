// Build the Phase 3 submission document (.docx) from the measured results in results/.
//   node docs/submission/build_submission_docx.js [TEAM_NAME]
// -> docs/submission/<TEAM_NAME>_Prototype Submission_V3.docx
// Numbers are read from the latest complete 6-direction summary.json of each device/backend, so re-running after a
// new (offline) benchmark refreshes every table. Yellow-highlighted text = fields the team must fill in.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
  HeadingLevel, LevelFormat, ImageRun, PageBreak, BorderStyle, Footer, PageNumber, ExternalHyperlink,
} = require("docx");

const ROOT = path.resolve(__dirname, "..", "..");
const R = path.join(ROOT, "results");
const TEAM = process.argv[2] || "[TeamName]";
const TODAY = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);  // local date
const PAIRS = ["vi-en", "en-vi", "vi-ko", "ko-vi", "vi-zh", "zh-vi"];
const LBL = { "vi-en": "VI→EN", "en-vi": "EN→VI", "vi-ko": "VI→KO", "ko-vi": "KO→VI", "vi-zh": "VI→ZH", "zh-vi": "ZH→VI" };

function latest(dir, prefix) {
  const d = path.join(R, dir);
  const runs = fs.readdirSync(d).filter((x) => x.startsWith(prefix)).sort();
  for (let i = runs.length - 1; i >= 0; i--) {
    const f = path.join(d, runs[i], "summary.json");
    if (!fs.existsSync(f)) continue;
    const s = JSON.parse(fs.readFileSync(f, "utf8"));
    if (PAIRS.every((p) => s.pairs && s.pairs[p])) return { name: runs[i], dir: path.join(d, runs[i]), s };
  }
  throw new Error("no complete run for " + dir + "/" + prefix);
}
const NPU = latest("ventunoq", "ventunoq_npu_");
const GPU = latest("ventunoq", "ventunoq_gpu_");
const CPU = latest("ventunoq", "ventunoq_cpu_");
const QCS = latest("qcs8550", "device_bench_");
// additional devices measured for latency only (optional: skipped if no complete run exists)
const tryLatest = (d, p) => { try { return latest(d, p); } catch (e) { return null; } };
const EXTRA = [
  ["Samsung Galaxy S25 Ultra (SM8750, Android 17)", "GPU · Adreno 830", tryLatest("s25ultra", "s25ultra_gpu_")],
].filter((e) => e[2]);
const f1 = (v) => (v == null ? "–" : Number(v).toFixed(1));
const f2 = (v) => (v == null ? "–" : Number(v).toFixed(2));
const f0 = (v) => (v == null ? "–" : Math.round(v).toString());
const sec = (ms) => (ms / 1000).toFixed(2);
const mean = (run, k) => PAIRS.reduce((a, p) => a + (run.s.pairs[p][k] || 0), 0) / PAIRS.length;
const rng = (run, k) => { const v = PAIRS.map((p) => run.s.pairs[p][k]); return [Math.min(...v), Math.max(...v)]; };
const mb = (kb) => Math.round(kb / 1024);
const net = (run) => `${run.s.device.internet || "?"} at start / ${(run.s.device_end || {}).internet || "?"} at end`;
const sock = (run) => (run.s.meminfo_peak_kb && "net_conns" in run.s.meminfo_peak_kb ? run.s.meminfo_peak_kb.net_conns : null);

// examples from the NPU run
const rows = fs.readFileSync(path.join(NPU.dir, "rows.jsonl"), "utf8").trim().split("\n").map((l) => JSON.parse(l));
const pick = (id) => rows.find((r) => r.id === id);
const EX = ["vi-en__VE-0046", "en-vi__EV-0228", "vi-ko__VK-0242", "ko-vi__VK-0170", "vi-zh__VM-0223", "zh-vi__VM-0237"].map(pick).filter(Boolean);
const emptyAsr = rows.filter((r) => !(r.asr || "").trim()).map((r) => r.id.split("__")[1]);

// ---------- styling helpers
const FONT = "Arial";
const W = 9906; // A4 content width in DXA with 1000-DXA margins
const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function runs(text, opt = {}) {
  // [[...]] = highlighted placeholder, **...** = bold
  const out = [];
  String(text).split(/(\[\[.*?\]\]|\*\*.*?\*\*|`[^`]+`)/).filter(Boolean).forEach((t) => {
    if (t.startsWith("`")) out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: (opt.size || 20) - 2, color: "1F3864" }));
    else if (t.startsWith("[[")) out.push(new TextRun({ text: t.slice(2, -2), highlight: "yellow", font: FONT, size: opt.size || 20 }));
    else if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, font: FONT, size: opt.size || 20 }));
    else out.push(new TextRun({ text: t, font: FONT, size: opt.size || 20, bold: opt.bold, italics: opt.italics, color: opt.color }));
  });
  return out;
}
const P = (text, opt = {}) => new Paragraph({ children: runs(text, opt), spacing: { after: opt.after ?? 100 }, alignment: opt.align });
const B = (text, lvl = 0) => new Paragraph({ children: runs(text), numbering: { reference: "bul", level: lvl }, spacing: { after: 40 } });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text: t, font: FONT })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text: t, font: FONT })] });
function cell(content, width, opt = {}) {
  const paras = (Array.isArray(content) ? content : [content]).map((c) =>
    c instanceof Paragraph ? c : new Paragraph({ children: runs(c, { size: opt.size || 18, bold: opt.bold }), spacing: { after: 40 } }));
  return new TableCell({
    children: paras, width: { size: width, type: WidthType.DXA }, borders,
    shading: opt.fill ? { fill: opt.fill, type: ShadingType.CLEAR, color: "auto" } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
  });
}
function table(widths, header, body, opt = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  const tr = [];
  if (header) tr.push(new TableRow({ tableHeader: true, children: header.map((h, i) => cell(h, widths[i], { bold: true, fill: "D9E2F3", size: opt.size })) }));
  body.forEach((r, k) => tr.push(new TableRow({ cantSplit: true, children: r.map((c, i) => cell(c, widths[i], { size: opt.size, fill: opt.firstColFill && i === 0 ? "EAF1FB" : (opt.zebra && k % 2 ? "F5F7FA" : undefined), bold: opt.firstColBold && i === 0 })) })));
  return new Table({ width: { size: total, type: WidthType.DXA }, columnWidths: widths, rows: tr });
}

// ---------- numbers used in the text
const npuP50 = rng(NPU, "total_ms_p50"), npuP95 = rng(NPU, "total_ms_p95");
const qcsP50 = rng(QCS, "total_ms_p50"), qcsP95 = rng(QCS, "total_ms_p95");
const npuRSS = mb(NPU.s.device_summary.peak_rss_kb), qcsRSS = mb(QCS.s.device_summary.peak_rss_kb);
const qcsGfx = mb((QCS.s.meminfo_peak_kb || {}).graphics || 0), gpuGfx = mb((GPU.s.meminfo_peak_kb || {}).graphics || 0);
const qcsPunct = QCS.s.pairs["vi-en"].punct_ms_mean > 0;

function qualityRows(run) {
  return PAIRS.map((p) => {
    const e = run.s.pairs[p];
    return [LBL[p], `${"asr_cer" in e ? "CER" : "WER"} ${f2(e.asr_cer ?? e.asr_wer)}%`, f2(e.bleu), f2(e["chrf++"]), f2(e.comet), f2(e.asr_bleu_speech_out)];
  });
}
function latencyRows(run) {
  return PAIRS.map((p) => {
    const e = run.s.pairs[p];
    return [LBL[p], f0(e.asr_ms_mean), f0(e.punct_ms_mean), f0(e.mt_ms_mean), f0(e.mt_ttft_ms_mean), f1(e.mt_decode_tps_mean), f0(e.tts_ms_mean), `${f0(e.total_ms_p50)} / ${f0(e.total_ms_p95)}`];
  });
}

// ---------- document
const C = [];
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "PROTOTYPE SUBMISSION", font: FONT, size: 36, bold: true, color: "1F3864" })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: "OneVoice AI Challenge 2026 · Phase 3", font: FONT, size: 24, color: "404040" })] }));
C.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 }, children: runs(`${TEAM === "[TeamName]" ? "[[" + TEAM + "]]" : TEAM} — CabinTranslation · build v1.0 · ${TODAY}`, { size: 22 }) }));
C.push(P("Fields highlighted in [[yellow]] must be completed by the team (names, links, video timestamps). Every number in this document comes from the run folders named in Section 4 and can be regenerated with `node docs/submission/build_submission_docx.js`.", { italics: true, size: 18, color: "595959" }));

// 1
C.push(H1("1. Prototype summary"));
C.push(table([2300, W - 2300], ["Field", "Team response"], [
  ["Team / individual participant", TEAM],
  ["Project name", "**CabinTranslation** — offline two-way voice-to-voice interpreter for workers in factories, warehouses and construction sites."],
  ["Submitted build", `**v1.0**, ${TODAY}. One native engine (\`cabin_edge\`) shipped for two Qualcomm devices: **VENTUNO Q package** \`CabinTranslation-VentunoQ-v1.0\` (engine build 085aba7cad5c) and **QCS8550 Android bundle v1.0** (app \`vn.cabin.translate\` v1.0, APK sha256 21471b6e6d79…, \`CabinTranslation-QCS8550-v1.0\`). Source: private GitHub repository (Section 3.1).`],
  ["Demo language(s)", "Registered pairs **VI⇄EN, VI⇄KO, VI⇄ZH**. All six directions run end to end and were benchmarked (Section 4). The demo video covers all three pairs in one factory scenario: [[confirm the directions actually shown in the video]]."],
  ["Test scenario", "\"Shift handover and line fault at an electronics assembly plant\" (~30 min). A Vietnamese line leader talks with an English-speaking customer auditor (safety walk, audit findings), a Korean equipment engineer (reflow-oven alarm), and a Chinese supplier QA (defective connectors), then hands over the shift. Script: Appendix A and `docs/submission/demo_scenario.md`."],
  ["Test conditions", "[[Actual duration mm:ss]]; [[indoor, light background noise (fans/conveyor audio) — describe]]; speakers 40–60 cm from the microphone; push-to-talk; network disabled before the first exchange ([[how: Wi-Fi off / cable unplugged]])."],
  ["Actual demo device", [
    P(`**Device A — Arduino VENTUNO Q:** Qualcomm QCS8275 (4× Cortex-A78C + 4× Cortex-A55, Hexagon v75 NPU, Adreno 623), 16 GB RAM (${Math.round(15651776 / 1048576 * 10) / 10} GB visible), ${NPU.s.device["ro.build.version.release"]}. Translation on the **NPU**. UI: browser at http://127.0.0.1:8080 on the board, or https://<board>:8443 from a phone/laptop on the LAN. [[Microphone/speaker used in the video: e.g. laptop/USB headset]].`, { size: 18 }),
    P(`**Device B — Qualcomm QCS8550 tablet** ("Tablet_Meeting", kalama): Android ${QCS.s.device["ro.build.version.release"]}, 16 GB RAM, Adreno 740. Translation on the **GPU**. Built-in microphone and speaker; browser UI or the CabinTranslation Android app.`, { size: 18 }),
  ]],
  ["Current capability & progress", [
    P("**Works end to end on both devices:** speech → ASR → Gemma 4 E2B translation → TTS, in all six directions, entirely on-device, operated through a touch UI (hold-to-talk per speaker, per-stage timing on screen, replay).", { size: 18 }),
    P(`**Delivered in Phase 3:** (1) a single native process with no Python and no network calls (sherpa-onnx ASR/TTS, LiteRT-LM for Gemma, ViFastTts FFI); (2) Gemma 4 E2B on the **Hexagon NPU** of QCS8275 at ~${f0(mean(NPU, "mt_decode_tps_mean"))} tokens/s with ${f0(mean(NPU, "mt_ttft_ms_mean"))} ms time-to-first-token, end-to-end p50 ${sec(npuP50[0])}–${sec(npuP50[1])} s; GPU builds for Adreno 740 and Adreno 623 and a CPU build, all measured; (3) device TTS chosen under a 500 ms budget (Piper EN, Supertonic-2 KO); (4) single-call Vietnamese input (lower-case + system-prompt constraint) replacing a separate punctuation pass; (5) an offline, relocatable judge package with pre-flight check and self-test; (6) an Android app with VAD capture.`, { size: 18 }),
    P("**Main limitation:** push-to-talk per utterance (no streaming). Dropping the punctuation pass costs VI→EN ~1.8 COMET. Korean and Chinese TTS on CPU are now the slowest stages on the NPU build. [[Confirm: direction unchanged from the Phase 2 proposal]].", { size: 18 }),
  ]],
], { firstColFill: true, firstColBold: true }));

// 2
C.push(H1("2. Demo video"));
C.push(P("Video link: [[accessible URL]]   Duration: [[mm:ss]]"));
C.push(P("Key timestamps: network disconnected — [[mm:ss]]; first complete voice-to-voice exchange — [[mm:ss]]; VI⇄KO scene — [[mm:ss]]; VI⇄ZH scene — [[mm:ss]]; on-screen per-stage timings / server log — [[mm:ss]]."));
C.push(P("Recording plan (VENTUNO Q): show `ip -br addr` / `nmcli radio` and disable Wi-Fi (`nmcli radio wifi off`) on camera, then `sh start.sh npu`; the UI status line shows `ASR … ms · MT … ms (Gemma 4 E2B, NPU) · TTS … ms · Tổng … ms` for every turn. On the QCS8550 tablet: enable airplane mode on camera, then start the app/UI.", { size: 18, color: "404040" }));

// 3
C.push(H1("3. Solution package"));
C.push(H2("3.1 Files and access"));
C.push(table([2300, W - 2300], ["Item", "Details"], [
  ["Offline package — VENTUNO Q", [
    P("**CabinTranslation-VentunoQ-v1.0.tar** (3.4 GB; SHA-256 fb5c3ffdee100fceaa6c0621a0911e3d290cfd8c0b5a616350d7ae5ccbfaf97a) + **qairt-2.50-libs.tar** (107 MB; SHA-256 7cc90dd40d50a58f0b865ebd69e219798585c3e0d40bab63e0cb307789f5d346; Qualcomm AI Runtime 2.50 runtime libraries, shipped separately under Qualcomm's terms; `fetch_qairt.py` re-downloads them from Qualcomm with pinned hashes).", { size: 18 }),
    P("Download: GitHub release v1.0 — https://github.com/mxngocqb/CabinTranslation/releases/tag/v1.0 (assets `CabinTranslation-VentunoQ-v1.0.tar.part-*`, `qairt-2.50-libs.tar`, `SHA256SUMS.txt`)", { size: 18 }),
  ]],
  ["Offline package — QCS8550", "`CabinTranslation-QCS8550-v1.0` (CabinTranslation.apk + models + install.sh, offline over adb) — GitHub release v1.0: https://github.com/mxngocqb/CabinTranslation/releases/tag/v1.0 (assets `CabinTranslation-QCS8550-v1.0.tar.part-*`, `CabinTranslation.apk`)"],
  ["Format", "Packaged native executables + models + launch scripts (VENTUNO Q, Linux aarch64); Android: native bundle installed over adb, and an APK."],
  ["Source repository", "Private GitHub repository shared with **saigonaihub**: https://github.com/mxngocqb/CabinTranslation (tag **v1.0**). Layout: `edge/engine` (native engine), `edge/ventunoq-linux`, `edge/qcs8550-android`, `edge/android-app`, `edge/tools`, `cabin` (Python core / prompts), `pc` (reference app), `scripts` (evaluations), `results` (all runs and logs), `dashboard`, `docs`."],
  ["Package contents (VENTUNO Q)", [
    B("`cabin_edge`, `cabin_edge_npu` — engine (HTTP server + touch UI, batch mode); `lib/`, `lib_npu/` — runtime libraries"),
    B("`models/` — ASR, TTS and the Gemma 4 E2B QCS8275 NPU model (3.25 GB in total)"),
    B("`config_{npu,gpu,cpu}.json`, `prompts.json` — relative model paths and MT prompts"),
    B("`start.sh`, `stop.sh`, `check.sh` (pre-flight), `selftest.sh` (offline self-test on `sample_input/`), `https_proxy.py`, `fetch_qairt.py`"),
    B("`README_INSTALL.md`, `SHA256SUMS`, `VERSION`"),
  ]],
], { firstColFill: true, firstColBold: true }));

C.push(H2("3.2 Architecture of the demonstrated solution"));
const img = fs.readFileSync(path.join(__dirname, "assets", "architecture.png"));
C.push(new Paragraph({ children: [new ImageRun({ type: "png", data: img, transformation: { width: 640, height: Math.round(640 * 866 / 3216) } })], spacing: { after: 120 } }));
C.push(P("**Implementation notes**", { after: 60 }));
[
  "All stages run in one native process on the device. The UI (served by the same process) records 16 kHz PCM, posts it to `/api/translate`, and receives the transcript, translation, timings and synthesized speech. No API or cloud call is made during inference.",
  `Precision: ASR models int8 (sherpa-onnx); Gemma 4 E2B in LiteRT-LM's mixed 2/4/8-bit QAT format (NPU build compiled ahead-of-time for QCS8275 with QAIRT 2.50); TTS ONNX fp32 (Piper, ViFastTts, Matcha) and int8 (Supertonic-2).`,
  "Vietnamese ASR output (upper case, no punctuation) is lower-cased with a rule-based question mark and translated in one Gemma call whose system prompt states that the input is an unpunctuated transcript. System prompts per direction are generated from the Python core so PC and devices translate identically.",
  "User controls: partner-language selector (EN/KO/ZH), one hold-to-talk (or tap-to-toggle) button per speaker, replay button; status line with per-stage times; `start.sh npu|gpu|cpu` selects the accelerator.",
  "Fallbacks: if the NPU is unavailable, `start.sh gpu` (Adreno 623, Vulkan) or `start.sh cpu` run the same pipeline; on Android the browser UI remains available if the app is not installed.",
  "Development tools (not part of the runtime): host cross-compilers, benchmark scoring on a PC (COMET). Qualcomm AI Hub was not used; the VENTUNO Q board used for development and measurement was a Qualcomm Device Cloud (QDC) device.",
].forEach((t) => C.push(B(t)));

C.push(H2("3.3 Minimum requirements to run this build"));
C.push(table([2300, W - 2300], ["Component", "Minimum requirement / compatibility"], [
  ["Processor / accelerator", [
    P("**VENTUNO Q build (tested):** Qualcomm QCS8275 with Hexagon v75 NPU (FastRPC `/dev/fastrpc-cdsp`), Adreno 623 for the GPU mode, aarch64 CPU. Other QCS8275 boards: estimated compatible (same SoC and NPU model).", { size: 18 }),
    P("**Android build (tested on QCS8550):** Snapdragon/QCS8550-class SoC with Adreno 740 GPU (OpenCL). Snapdragon 8 Gen 2 / Gen 3 phones: estimated, not tested.", { size: 18 }),
  ]],
  ["Memory and storage", [
    P(`**Tested peak RAM** (all 4 languages loaded): VENTUNO Q NPU ${npuRSS} MB process RSS; QCS8550 ${qcsRSS} MB RSS + ${qcsGfx} MB GPU (graphics). Minimum: 8 GB RAM (estimated).`, { size: 18 }),
    P("**Storage:** VENTUNO Q package 3.45 GB installed (NPU) + 0.1 GB QAIRT; +4.7 GB for the optional CPU/GPU Gemma files. QCS8550: ~2.9 GB in `/data/local/tmp/cabin` (or `/sdcard/CabinTranslation` for the app). Keep ≥ 1 GB free for logs.", { size: 18 }),
  ]],
  ["OS and software", [
    P("**VENTUNO Q:** Ubuntu 24.04 aarch64 (glibc ≥ 2.39), stock FastRPC (`libcdsprpc.so.1`), user in groups `fastrpc` and `render`; Python 3 standard library for the optional HTTPS front. Bundled: sherpa-onnx 1.13.8, ONNX Runtime 1.28.2, LiteRT-LM C API 0.19.1 (CPU/GPU), LiteRT-LM 0.18 NPU runtime + LiteRT Qualcomm dispatch, QAIRT 2.50.0.260828 (separate archive). No root, compiler or package installation required.", { size: 18 }),
    P("**Android:** Android 13 arm64 with GPU OpenCL driver; adb on a host for installation (bundle) or APK sideloading.", { size: 18 }),
  ]],
  ["Audio and peripherals", "Microphone and speaker/headphones: on the board (USB/onboard audio with a local monitor and Firefox) or on the client device that opens the UI (laptop/phone browser over https on the LAN, or the tablet's built-in mic/speaker). Screen for the UI. Optional: Ethernet cable for LAN access while Wi-Fi is off."],
], { firstColFill: true, firstColBold: true }));

C.push(H2("3.4 Install and run offline"));
C.push(table([2300, W - 2300], ["Step", "VENTUNO Q (Device A)  ·  QCS8550 tablet (Device B)"], [
  ["Prepare", [
    P("**A:** copy `CabinTranslation-VentunoQ-v1.0.tar` and `qairt-2.50-libs.tar` to the board (USB stick or scp). Nothing else is downloaded.", { size: 18 }),
    P("**B:** host PC with adb; copy the QCS8550 bundle `CabinTranslation-QCS8550-v1.0` (join the release parts: `cat CabinTranslation-QCS8550-v1.0.tar.part-* > CabinTranslation-QCS8550-v1.0.tar`, then `tar -xf`) to the host.", { size: 18 }),
  ]],
  ["Install", [
    P("**A:** `tar -xf CabinTranslation-VentunoQ-v1.0.tar && cd CabinTranslation-VentunoQ-v1.0 && tar -xf ../qairt-2.50-libs.tar -C lib_npu && sh check.sh` → `CHECK PASSED` (verifies SoC, NPU access, libraries, SHA-256 of every file).", { size: 18 }),
    P("**B:** inside `CabinTranslation-QCS8550-v1.0/`: `bash install.sh <adb-serial>` — installs the APK, grants file access, pins landscape, pushes `models/` to `/sdcard/CabinTranslation/models` and starts the app.", { size: 18 }),
  ]],
  ["Disconnect and launch", [
    P("**A:** disable networking (`nmcli radio wifi off`, unplug Ethernet), then `sh start.sh npu`. Ready after ~25 s: `READY: open http://127.0.0.1:8080/`; the UI status shows `Sẵn sàng · models loaded on device: en, ko, vi, zh · LLM npu`. For a phone/laptop on a local cable: `HOST=0.0.0.0 HTTPS=1 sh start.sh npu` and open https://<board-ip>:8443/.", { size: 18 }),
    P("**B:** enable airplane mode, then `adb shell sh /data/local/tmp/cabin/start.sh` (opens the browser UI) or tap the CabinTranslation app (~25 s load).", { size: 18 }),
  ]],
  ["Run the scenario", "Pick the partner language (English / 한국어 / 中文). The Vietnamese speaker holds **Giữ để nói**, the partner holds **Hold to talk**; release to translate. Expected: the recognized sentence and translation appear in the log, the translation is spoken, and the status line shows ASR / MT / TTS / total milliseconds."],
  ["Reset or troubleshoot", [
    P("Restart: `sh stop.sh && sh start.sh npu` (A) / `adb shell sh /data/local/tmp/cabin/stop.sh` then start again (B). Verify without a microphone: `sh selftest.sh npu` (12 bundled utterances).", { size: 18 }),
    P("`QAIRT 2.50 libraries missing` → untar `qairt-2.50-libs.tar` into `lib_npu`. Microphone silent → open the UI via 127.0.0.1 or https (browsers block the mic on plain http LAN addresses). Logs: `out/server.log`, `out/selftest.log`; every live utterance is saved to `out/live/`.", { size: 18 }),
  ]],
], { firstColFill: true, firstColBold: true }));

// 4
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(H1("4. Self-recorded test results"));
C.push(P(`**Test record.** Organizer Round 3 sample set, all six directions, ${NPU.s.pairs["vi-en"].n + NPU.s.pairs["en-vi"].n + NPU.s.pairs["vi-ko"].n + NPU.s.pairs["ko-vi"].n + NPU.s.pairs["vi-zh"].n + NPU.s.pairs["zh-vi"].n} utterances per run (VI→EN 100, EN→VI 100, VI→KO 175, KO→VI 177, VI→ZH 176, ZH→VI 177). Each utterance goes speech-in → speech-out on the device in batch mode (same engine and models as the UI); scoring on a PC.`));
C.push(P(`**Runs.** Device A (VENTUNO Q): NPU \`results/ventunoq/${NPU.name}\` (submitted build), GPU \`${GPU.name}\`, CPU \`${CPU.name}\`. Device B (QCS8550, GPU): \`results/qcs8550/${QCS.name}\`${qcsPunct ? " — **earlier 2-call Vietnamese build**; the 1-call v1.0 build will be re-measured offline: [[update after the QCS8550 offline run]]" : ""}.`));
C.push(P(`**Network condition (stated honestly).** VENTUNO Q runs: the board's Wi-Fi stayed connected (internet ${net(NPU)}) because the board is a remotely hosted device whose session would drop; instead, the engine's network sockets were sampled every ~1 s during the run: **maximum non-loopback TCP/UDP sockets of the engine process = ${sock(NPU) ?? "n/a"}**. QCS8550 run: Wi-Fi on (adb over Wi-Fi), internet ${net(QCS)}. [[Offline re-runs: add here]].`));
C.push(P("**Evidence folder:** https://github.com/mxngocqb/CabinTranslation/tree/main/results → `results/<device>/<run>/`: `summary.md`, `summary.json`, `result.jsonl` (raw device output, per-utterance timings), `rows.jsonl` (with references), `device_stderr.log`, `meminfo_samples.json` (memory / GPU / socket samples), `stage/` (16 kHz inputs), `wav/` (spoken outputs). Dashboard with audio: `dashboard/index.html`."));
C.push(P("**Metric definitions.** BLEU and chrF++ (sacreBLEU) on normalized text (lower-case, no punctuation, numbers spelled out); KO/ZH targets character-level BLEU. COMET = Unbabel/wmt22-comet-da. ASR error: WER (VI, EN) or CER (KO, ZH). ASR-BLEU = BLEU of the spoken output re-recognized by ASR on the PC. Latency = wall time inside the engine from reading the input WAV to finishing the output WAV (ASR + text prep + MT + TTS), excluding one-time model loading; p50/p95 over all utterances of a direction.", { size: 18 }));

C.push(table([1700, W - 1700 - 1800, 1800], ["Area", "Result and method", "Evidence reference"], [
  ["Translation quality", [
    P(`Mean COMET over the six directions: **${f1(mean(NPU, "comet"))}** (VENTUNO Q NPU), ${f1(mean(GPU, "comet"))} (GPU), ${f1(mean(CPU, "comet"))} (CPU), ${f1(mean(QCS, "comet"))} (QCS8550${qcsPunct ? ", 2-call build" : ""}). Per-direction BLEU / chrF++ / COMET / ASR-BLEU in Tables 4.1–4.2.`, { size: 18 }),
    P(`Representative outputs and failures in Table 4.4. Known failures: empty ASR on ${emptyAsr.length} utterance(s) (${emptyAsr.join(", ") || "none"}); KO references in the sample set contain misaligned pairs (e.g. VK-0242), which lowers KO→VI BLEU.`, { size: 18 }),
  ], "`summary.md`, `rows.jsonl` of each run"],
  ["Inference / response time", `End-to-end speech-in → speech-out, p50 / p95 per direction: **VENTUNO Q NPU ${sec(npuP50[0])}–${sec(npuP50[1])} s / ${sec(npuP95[0])}–${sec(npuP95[1])} s**; QCS8550 GPU ${sec(qcsP50[0])}–${sec(qcsP50[1])} s / ${sec(qcsP95[0])}–${sec(qcsP95[1])} s. Gemma on NPU: ${f0(mean(NPU, "mt_ttft_ms_mean"))} ms TTFT, ${f1(mean(NPU, "mt_decode_tps_mean"))} tokens/s decode. Component means in Table 4.3. 905 utterances per run, one run per configuration.${EXTRA.length ? " Same engine on additional devices (Table 4.5): " + EXTRA.map((e) => `${e[0].split(" (")[0]} ${e[1].split(" · ")[0]} p50 ${sec(rng(e[2], "total_ms_p50")[0])}–${sec(rng(e[2], "total_ms_p50")[1])} s`).join("; ") + "." : ""}`, "`result.jsonl` (per-utterance asr/mt/tts/total ms)"],
  ["Model size", "Model files in the VENTUNO Q package: **3,255 MB** = Gemma 4 E2B QCS8275 NPU 2,596 MB + ASR 268 MB (Zipformer-30M vi 29, X-ASR zh-en 167, Zipformer-ko 73) + TTS 390 MB (ViFastTts 82, Piper 77, Supertonic-2 92, Matcha 88, Vocos 51). Libraries 189 MB (+107 MB QAIRT). Total installation 3.45 GB (+0.1 GB). QCS8550: Gemma `-gpu` 2,232 MB + same ASR/TTS.", "`SHA256SUMS`; `du` listing in the package README"],
  ["Peak memory", `Process peak RSS (VmHWM, all four languages loaded, whole run): VENTUNO Q NPU **${npuRSS} MB**, GPU ${mb(GPU.s.device_summary.peak_rss_kb)} MB + ${gpuGfx} MB GPU buffers (DRM fdinfo), CPU ${mb(CPU.s.device_summary.peak_rss_kb)} MB; QCS8550 ${qcsRSS} MB + ${qcsGfx} MB graphics (dumpsys meminfo). Measured by the engine (VmHWM) and polled every ~1 s by the host.`, "`summary.json` → device_summary.peak_rss_kb, `meminfo_samples.json`"],
  ["Device operation & UX", "[[Scenario completed: yes/no; actual duration; interruptions/recoveries]]. Live UI test on VENTUNO Q (2026-11-11): utterances spoken through a laptop browser over HTTPS were recognized, translated on the NPU and spoken back (e.g. a 6 s introduction in 2.9 s). Startup ~25 s; restart with `stop.sh/start.sh`.", "[[Video timestamps]]; `out/server.log`, `out/live/*.wav`"],
], { firstColFill: true, firstColBold: true }));

C.push(H2("Table 4.1 — VENTUNO Q, Gemma on the Hexagon NPU (submitted build)"));
C.push(table([1300, 1700, 1300, 1300, 1300, 3006 - 300 + 300], ["Direction", "ASR error", "BLEU", "chrF++", "COMET", "ASR-BLEU (spoken output)"], qualityRows(NPU), { zebra: true }));
C.push(H2(`Table 4.2 — QCS8550, Gemma on the Adreno 740 GPU${qcsPunct ? " (earlier 2-call build)" : ""}`));
C.push(table([1300, 1700, 1300, 1300, 1300, 3006], ["Direction", "ASR error", "BLEU", "chrF++", "COMET", "ASR-BLEU (spoken output)"], qualityRows(QCS), { zebra: true }));
C.push(H2("Table 4.3 — Latency per stage (mean ms) and end-to-end p50 / p95 (ms)"));
const lw = [1100, 900, 1000, 1000, 1000, 1100, 1000, W - 7100];
C.push(P("**VENTUNO Q NPU**", { after: 40 }));
C.push(table(lw, ["Dir.", "ASR", "Punct.", "MT", "TTFT", "tok/s", "TTS", "Total p50 / p95"], latencyRows(NPU), { zebra: true, size: 17 }));
C.push(P("**VENTUNO Q GPU (Adreno 623) / CPU** — total p50 / p95 ms: " + PAIRS.map((p) => `${LBL[p]} ${f0(GPU.s.pairs[p].total_ms_p50)}/${f0(GPU.s.pairs[p].total_ms_p95)} · ${f0(CPU.s.pairs[p].total_ms_p50)}/${f0(CPU.s.pairs[p].total_ms_p95)}`).join("; ") + `. Mean COMET GPU ${f1(mean(GPU, "comet"))}, CPU ${f1(mean(CPU, "comet"))}.`, { size: 18 }));
C.push(P("**QCS8550 GPU**", { after: 40 }));
C.push(table(lw, ["Dir.", "ASR", "Punct.", "MT", "TTFT", "tok/s", "TTS", "Total p50 / p95"], latencyRows(QCS), { zebra: true, size: 17 }));
C.push(H2("Table 4.4 — Representative inputs and outputs (VENTUNO Q NPU run)"));
C.push(table([1300, 3500, 3606 - 600, 1500 + 600], ["ID", "ASR transcript (device)", "Device translation", "Reference / time"],
  EX.map((r) => [`${r.id.split("__")[1]} ${LBL[r.pair]}`, r.mt_in || r.asr, r.hyp, `${r.ref} · ${f0(r.total_ms)} ms`]), { size: 16 }));

if (EXTRA.length) {
  C.push(H2("Table 4.5 — Same Android build on Samsung Galaxy S25 Ultra (latency only; network connected)"));
  C.push(P("Same engine, models and prompts; full sample set (905 utterances). Only timing is reported here, as requested; transcripts and translations are in each run's `rows.jsonl`.", { size: 18 }));
  const ew = [1050, 1000, 1000, 1000, 1000, 1050, 1000, W - 7100];
  EXTRA.forEach(([dev, acc, run]) => {
    const ds = run.s.device_summary || {}, mp = run.s.meminfo_peak_kb || {};
    C.push(P(`**${dev} — Gemma on ${acc}** · \`${run.name}\` · peak RSS ${mb(ds.peak_rss_kb || 0)} MB${mp.graphics ? ` + ${mb(mp.graphics)} MB GPU` : ""}${"net_conns" in mp ? ` · engine network sockets max ${mp.net_conns}` : ""}`, { after: 40, size: 18 }));
    C.push(table(ew, ["Dir.", "ASR", "Punct.", "MT", "TTFT", "tok/s", "TTS", "Total p50 / p95"], latencyRows(run), { zebra: true, size: 17 }));
  });
  // battery power measured on the S25 Ultra (edge/tools/power_bench_android.py), if available
  const pdir = path.join(R, "s25ultra");
  const pw = fs.existsSync(pdir) ? fs.readdirSync(pdir).filter((x) => x.startsWith("power_")).sort().reverse()
    .map((x) => path.join(pdir, x, "summary.json")).find((f) => fs.existsSync(f)) : null;
  if (pw) {
    const q = JSON.parse(fs.readFileSync(pw, "utf8"));
    C.push(P(`**Power consumption — Galaxy S25 Ultra** (\`${path.basename(path.dirname(pw))}\`; on battery, charger unplugged; \`dumpsys battery\` current/voltage/charge counter sampled ~1/s; no root).`, { after: 40, size: 18 }));
    C.push(table([3300, 1300, 1300, 1300, 1300, W - 8500], ["Phase", "Duration s", "Avg current mA", "Avg power W", "Charge used mAh", "Battery temp °C"], [
      ["Idle baseline (screen on, nothing running)", f0(q.idle.duration_s), f0(q.idle.avg_current_ma), f2(q.idle.avg_power_w), f1(q.idle.charge_used_mah), `${q.idle.temp_c_start_end[0]} → ${q.idle.temp_c_start_end[1]}`],
      [`Pipeline running (${q.utterances} utterances, speech→speech)`, f0(q.load.duration_s), f0(q.load.avg_current_ma), f2(q.load.avg_power_w), f1(q.load.charge_used_mah), `${q.load.temp_c_start_end[0]} → ${q.load.temp_c_start_end[1]}`],
    ], { zebra: true, size: 17 }));
    C.push(P(`Pipeline power (load − idle): **${f2(q.pipeline_power_w)} W**. Energy per translated utterance: **${f1(q.energy_per_utterance_j)} J** for the pipeline alone, ${f1(q.total_energy_per_utterance_j)} J including the screen/OS baseline (${q.utterances} utterances in ${f0(q.load_wall_s)} s; back-to-back, i.e. the worst case — in a real conversation the device idles between turns).`, { size: 18 }));
  }
}

C.push(H2("Known limitations"));
[
  "Push-to-talk per utterance; no streaming recognition or barge-in yet (the Android app already segments with Silero VAD).",
  "Single-call Vietnamese input trades accuracy for speed: VI→EN loses ~1.8 COMET / ~7 BLEU against the 2-call punctuation pass (`--punct-pass` restores it).",
  "Vietnamese ASR on the VI–ZH sample voices: WER 12.3% vs 1.7–4.8% on the other sets; ASR errors propagate to translation.",
  "One utterance with empty ASR output (EV-2748); occasional untranslated short sentences on CPU/GPU builds (VK-0300).",
  "VENTUNO Q benchmarks were run with Wi-Fi connected (socket evidence provided); the QCS8550 table is from the earlier 2-call build pending an offline re-run.",
  "The NPU requires QAIRT 2.50 runtime libraries, distributed separately from the main package.",
].forEach((t) => C.push(B(t)));
C.push(H2("Next development steps"));
[
  "**Streaming ASR + VAD auto-segmentation** on both devices; check: end-of-speech-to-audio latency and WER on the sample set with the same scoring scripts.",
  "**Move Korean/Chinese TTS off the CPU critical path** (NPU via QNN or faster vocoder) to bring VI→KO/ZH p50 below 0.6 s; check: `selftest.sh` and the full benchmark per-stage TTS times, round-trip CER.",
  "**Domain adaptation for factory vocabulary** (glossary in the prompt, then LoRA on spoken-style parallel data); check: COMET/BLEU on the sample set and on a factory term list, with the scenario script as a regression test.",
].forEach((t) => C.push(B(t)));

// Appendix
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(H1("Appendix A — Demo scenario script (summary)"));
const sc = fs.readFileSync(path.join(__dirname, "demo_scenario.md"), "utf8");
const scenes = [...sc.matchAll(/^\| (\d) \| ([^|]+) \| ([^|]+) \| ([^|]+) \|$/gm)].map((m) => [m[1], m[2].trim(), m[3].trim(), m[4].trim()]);
C.push(table([700, 1900, 1700, W - 4300], ["#", "Time", "Pair", "Scene"], scenes, { zebra: true }));
C.push(P("Full utterance list (≈60 turns, Vietnamese / English / Korean / Chinese): `docs/submission/demo_scenario.md` in the repository and package.", { size: 18 }));

const doc = new Document({
  creator: TEAM, title: `${TEAM}_Prototype Submission_V3`,
  styles: {
    default: { document: { run: { font: FONT, size: 20 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 28, bold: true, color: "1F3864" }, paragraph: { spacing: { before: 280, after: 120 }, keepNext: true, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: FONT, size: 22, bold: true, color: "2F5496" }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } },
    ],
  },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 400, hanging: 240 } } } }, { level: 1, format: LevelFormat.BULLET, text: "◦", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 800, hanging: 240 } } } }] }] },
  sections: [{
    properties: { page: { margin: { top: 900, bottom: 900, left: 1000, right: 1000 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [new TextRun({ text: `${TEAM} · CabinTranslation · Prototype Submission V3 · page `, font: FONT, size: 16, color: "808080" }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16, color: "808080" })] })] }) },
    children: C,
  }],
});
const out = path.join(__dirname, `${TEAM.replace(/[\[\]]/g, "")}_Prototype Submission_V3.docx`);
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(out, b); console.log("wrote", out, "| runs:", NPU.name, GPU.name, CPU.name, QCS.name); });
