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
const QCS = latest("qcs8550", "device_bench_");
// additional devices measured for latency only (optional: skipped if no complete run exists)
const tryLatest = (d, p) => { try { return latest(d, p); } catch (e) { return null; } };
const S25 = tryLatest("s25ultra", "s25ultra_gpu_");
const s25p50 = () => rng(S25, "total_ms_p50");   // evaluated later (rng is defined below)
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
const P = (text, opt = {}) => new Paragraph({ children: runs(text, opt), spacing: { after: opt.after ?? 100 }, alignment: opt.align, keepNext: opt.keep });
const B = (text, lvl = 0, keep = false) => new Paragraph({ children: runs(text), numbering: { reference: "bul", level: lvl }, spacing: { after: 40 }, keepNext: keep });
// small variants used inside table cells: PS = one line/paragraph, BS = bullet (lvl 1 = sub-bullet)
const PS = (text, after = 40) => P(text, { size: 18, after });
const BS = (text, lvl = 0) => new Paragraph({ children: runs(text, { size: 18 }), numbering: { reference: "bul", level: lvl }, spacing: { after: 20 } });
const LOG = (l) => new Paragraph({ spacing: { after: 0 }, keepNext: true, indent: { left: 200 }, children: [new TextRun({ text: l, font: "Consolas", size: 14, color: "1F3864" })] });
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
const qcsGfx = mb((QCS.s.meminfo_peak_kb || {}).graphics || 0);
const qcsPunct = QCS.s.pairs["vi-en"].punct_ms_mean > 0;
const rmeta = (run) => { try { return JSON.parse(fs.readFileSync(path.join(run.dir, "run_meta.json"), "utf8")); } catch (e) { return {}; } };
const npuOffline = !!rmeta(NPU).offline;

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
C.push(P("Every number in this document comes from the run folders named in Section 4 and can be regenerated with `node docs/submission/build_submission_docx.js`.", { italics: true, size: 18, color: "595959" }));

// 1
C.push(H1("1. Prototype summary"));
C.push(table([2300, W - 2300], ["Field", "Team response"], [
  ["Team / individual participant", TEAM],
  ["Project name", [
    PS("**CabinTranslation**"),
    PS("Offline two-way voice-to-voice interpreter for workers in factories, warehouses and construction sites."),
  ]],
  ["Submitted build", [
    PS(`**v1.0**, ${TODAY}. One native engine (\`cabin_edge\`) shipped for three Qualcomm devices:`),
    BS("**VENTUNO Q package** `CabinTranslation-VentunoQ-v1.0` (engine build 085aba7cad5c)"),
    BS("**QCS8550 Android bundle v1.0** `CabinTranslation-QCS8550-v1.0`: app `vn.cabin.translate` v1.0, APK sha256 21471b6e6d79…"),
    BS("**Samsung Galaxy S25 Ultra (SM8750):** the same APK and bundle, unchanged"),
    PS("Source: private GitHub repository (Section 3.1)."),
  ]],
  ["Demo language(s)", [
    PS("Registered pairs **VI↔EN, VI↔KO, VI↔ZH**."),
    BS("All six directions run end to end and were benchmarked (Section 4)."),
    BS("The demo videos show **all three pairs, in both directions, live** on each device."),
    BS("Galaxy S25 Ultra video: one speaker fluent in Vietnamese, English, Korean and Chinese."),
  ]],
  ["Test scenario", [
    PS("\"Shift handover and line fault at an electronics assembly plant\" (~30 min). A Vietnamese line leader talks with:"),
    BS("an English-speaking customer auditor (safety walk, audit findings)"),
    BS("a Korean equipment engineer (reflow-oven alarm)"),
    BS("a Chinese supplier QA (defective connectors)"),
    PS("…then hands over the shift. Script: Appendix A and `docs/submission/demo_scenario.md`."),
  ]],
  ["Test conditions", [
    BS("**Recordings (uncut):** Galaxy S25 Ultra **1:43** · QCS8550 tablet **1:35** · VENTUNO Q **2:08**"),
    BS("**Environment:** indoor office/lab, light background noise (air-conditioning, people talking nearby)"),
    BS("**Capture:** speakers about 30–50 cm from the microphone; push-to-talk"),
    BS("**Network:** all devices run **offline** (confirmed by the team)"),
    BS("S25 Ultra: airplane mode switched on camera at 0:00–0:07", 1),
    BS("QCS8550 tablet: the app header shows ✈ Offline throughout", 1),
  ]],
  ["Actual demo device", [
    PS("**Device A — Arduino VENTUNO Q**"),
    BS("Qualcomm QCS8275: 4× Cortex-A78C + 4× Cortex-A55, Hexagon v75 NPU, Adreno 623"),
    BS(`16 GB RAM (${Math.round(15651776 / 1048576 * 10) / 10} GB visible), ${NPU.s.device["ro.build.version.release"]}`),
    BS("Translation on the **NPU**"),
    BS("UI: browser at http://127.0.0.1:8080 on the board, or https://<board>:8443 from a phone/laptop on the LAN"),
    BS("In the video: the UI is served by the board over the web; the **laptop's microphone and speakers** are the input and output"),
    PS(""),
    PS("**Device B — Qualcomm QCS8550 tablet** (\"Tablet_Meeting\", kalama)"),
    BS(`Android ${QCS.s.device["ro.build.version.release"]}, 16 GB RAM, Adreno 740`),
    BS("Translation on the **GPU**"),
    BS("Built-in microphone and speaker; CabinTranslation Android app (or the browser UI)"),
    PS(""),
    PS("**Device C — Samsung Galaxy S25 Ultra** (SM-S938B)"),
    BS("Snapdragon 8 Elite for Galaxy (**SM8750**): 8-core Oryon CPU, Adreno 830, Hexagon NPU"),
    BS("12 GB RAM (11.4 GB visible), Android 17"),
    BS("Translation on the **GPU**"),
    BS("Built-in microphone and speaker; same CabinTranslation Android app as Device B"),
    ...(S25 ? [BS(`End-to-end p50 ${sec(s25p50()[0])}–${sec(s25p50()[1])} s (Table 4.5)`)] : []),
  ]],
  ["Current capability & progress", [
    PS("**Works end to end on all three devices** (VENTUNO Q, QCS8550 tablet, Galaxy S25 Ultra):"),
    BS("speech → ASR → Gemma 4 E2B translation → TTS, in all six directions"),
    BS("entirely on-device"),
    BS("operated through a touch UI: hold-to-talk per speaker, per-stage timing on screen, replay"),
    PS(""),
    PS("**Delivered in Phase 3:**"),
    BS("A single native process with no Python and no network calls (sherpa-onnx ASR/TTS, LiteRT-LM for Gemma, ViFastTts FFI)."),
    BS(`Gemma 4 E2B on the **Hexagon NPU** of QCS8275: ~${f0(mean(NPU, "mt_decode_tps_mean"))} tokens/s, ${f0(mean(NPU, "mt_ttft_ms_mean"))} ms time-to-first-token, end-to-end p50 ${sec(npuP50[0])}–${sec(npuP50[1])} s.`),
    BS("GPU builds for Adreno 740 (QCS8550) and Adreno 830 (Galaxy S25 Ultra / SM8750), both measured."),
    BS("Device TTS chosen under a 500 ms budget (Piper EN, Supertonic-2 KO)."),
    BS("Single-call Vietnamese input (lower-case + system-prompt constraint) replacing a separate punctuation pass."),
    BS("An offline, relocatable judge package with pre-flight check and self-test."),
    BS("An Android app with VAD capture, tested on the QCS8550 tablet and the Galaxy S25 Ultra."),
    BS("Battery power measured on the S25 Ultra (Table 4.5)."),
    PS(""),
    PS("**Main limitations:**"),
    BS("Push-to-talk per utterance (no streaming)."),
    BS("Dropping the punctuation pass costs VI→EN ~1.8 COMET."),
    BS("Korean and Chinese TTS on CPU are now the slowest stages on the NPU build."),
    PS(""),
    PS("Direction unchanged from the Phase 2 proposal."),
  ]],
], { firstColFill: true, firstColBold: true }));

// 2
C.push(H1("2. Demo video"));
C.push(P("**Video link:** https://drive.google.com/drive/folders/1iWq1RX0CFh7ceKYvsQRPJ3jb_PW2tEPs?usp=sharing", { after: 40 }));
C.push(P("Folder BKMEETING_OneVoiceAIChallenge — three uncut recordings:", { after: 40 }));
C.push(B("`GalaxyS25_SM8750.MOV` — **1:43**"));
C.push(B("`BKMEETING_QCS8550.MOV` — **1:35**"));
C.push(B("`VentunoQ.mov` — **2:08**"));
C.push(P("Key timestamps (times are approximate to ±2 s):", { after: 60, keep: true }));
C.push(table([2300, W - 2300], ["Video", "Timestamps"], [
  [["GalaxyS25_SM8750.MOV (1:43)", "Samsung Galaxy S25 Ultra, app"], [
    BS("Network disconnected (airplane mode in quick settings): **0:00–0:07**"),
    BS("App shows ✈ Offline · Sẵn sàng: **0:08**"),
    BS("First complete voice-to-voice exchange: **≈0:28** (VI→EN; on screen ASR 76 · MT 744 · TTS 217 · total 1040 ms)"),
    BS("VI↔EN **0:08–0:52** · VI↔KO **0:56–1:16** · VI↔ZH **1:16–1:43**"),
    BS("One speaker fluent in all three foreign languages"),
  ]],
  [["BKMEETING_QCS8550.MOV (1:35)", "QCS8550 tablet, app"], [
    BS("✈ Offline · Sẵn sàng visible in the app header: from **0:00**"),
    BS("First complete exchange (VI→EN): **≈0:24**"),
    BS("VI↔EN **0:12–0:48** · VI↔KO **0:52–1:16** · VI↔ZH **1:16–1:35**"),
    BS("Per-stage timings in the footer of every turn"),
  ]],
  [["VentunoQ.mov (2:08)", "Arduino VENTUNO Q, web UI on a laptop"], [
    BS("Board session: **0:00–0:14**; web UI ready: **0:16**"),
    BS("First complete exchange (VI→EN, 1877 ms): **≈0:44**; EN→VI: **≈1:04**"),
    BS("Status line with NPU timing: **≈1:20** (e.g. ASR 298 · MT 605 (Gemma 4 E2B, NPU) · TTS 283 · total 1187 ms)"),
    BS("VI↔KO **1:24–1:40** · VI↔ZH **1:44–2:08**"),
    BS("Laptop microphone and speakers as input/output"),
  ]],
], { firstColFill: true, firstColBold: true, size: 17 }));

// 3
C.push(H1("3. Solution package"));
C.push(H2("3.1 Files and access"));
C.push(table([2300, W - 2300], ["Item", "Details"], [
  ["Offline package — VENTUNO Q", [
    BS("**CabinTranslation-VentunoQ-v1.0.tar** (3.4 GB)"),
    BS("SHA-256 `fb5c3ffdee100fceaa6c0621a0911e3d290cfd8c0b5a616350d7ae5ccbfaf97a`", 1),
    BS("**qairt-2.50-libs.tar** (107 MB): Qualcomm AI Runtime 2.50 runtime libraries, shipped separately under Qualcomm's terms"),
    BS("SHA-256 `7cc90dd40d50a58f0b865ebd69e219798585c3e0d40bab63e0cb307789f5d346`", 1),
    BS("`fetch_qairt.py` re-downloads them from Qualcomm with pinned hashes", 1),
    PS(""),
    PS("**Download:** GitHub release v1.0 — https://github.com/mxngocqb/CabinTranslation/releases/tag/v1.0"),
    PS("Assets: `CabinTranslation-VentunoQ-v1.0.tar.part-*`, `qairt-2.50-libs.tar`, `SHA256SUMS.txt`"),
  ]],
  ["Offline package — Android (QCS8550 tablet, Galaxy S25 Ultra)", [
    PS("Same package for both Android devices: **CabinTranslation-QCS8550-v1.0**"),
    BS("CabinTranslation.apk + models + install.sh"),
    BS("Installs offline over adb"),
    PS(""),
    PS("**Download:** GitHub release v1.0 — https://github.com/mxngocqb/CabinTranslation/releases/tag/v1.0"),
    PS("Assets: `CabinTranslation-QCS8550-v1.0.tar.part-*`, `CabinTranslation.apk`"),
  ]],
  ["Format", [
    BS("**VENTUNO Q (Linux aarch64):** packaged native executables + models + launch scripts"),
    BS("**Android (QCS8550 tablet, Galaxy S25 Ultra):** APK + models installed over adb (USB or wireless debugging), plus the native bundle"),
  ]],
  ["Source repository", [
    PS("Private GitHub repository shared with **saigonaihub**:"),
    PS("https://github.com/mxngocqb/CabinTranslation (tag **v1.0**)"),
    PS("Layout:"),
    BS("`edge/engine` — native engine"),
    BS("`edge/ventunoq-linux`, `edge/qcs8550-android`, `edge/android-app` — per-device builds and the Android app"),
    BS("`edge/tools` — bundle, deploy and on-device benchmark tools"),
    BS("`cabin` — Python core / prompts; `pc` — reference app; `scripts` — evaluations"),
    BS("`results` — all runs and logs; `dashboard`; `docs`"),
  ]],
  ["Package contents (VENTUNO Q)", [
    BS("`cabin_edge`, `cabin_edge_npu` — engine (HTTP server + touch UI, batch mode)"),
    BS("`lib/`, `lib_npu/` — runtime libraries"),
    BS("`models/` — ASR, TTS and the Gemma 4 E2B QCS8275 NPU model (3.25 GB in total)"),
    BS("`config_{npu,gpu,cpu}.json`, `prompts.json` — relative model paths and MT prompts"),
    BS("`start.sh`, `stop.sh` — launch / stop"),
    BS("`check.sh` (pre-flight), `selftest.sh` (offline self-test on `sample_input/`)"),
    BS("`https_proxy.py`, `fetch_qairt.py`"),
    BS("`README_INSTALL.md`, `SHA256SUMS`, `VERSION`"),
  ]],
], { firstColFill: true, firstColBold: true }));

C.push(H2("3.2 Architecture of the demonstrated solution"));
const img = fs.readFileSync(path.join(__dirname, "assets", "architecture.png"));
C.push(new Paragraph({ children: [new ImageRun({ type: "png", data: img, transformation: { width: 640, height: Math.round(640 * img.readUInt32BE(20) / img.readUInt32BE(16)) } })], spacing: { after: 120 } }));
C.push(P("**Implementation notes**", { after: 60 }));
C.push(B("**One process.** All stages run in one native process on the device. No API or cloud call is made during inference."));
C.push(B("The UI (served by the same process) records 16 kHz PCM and posts it to `/api/translate`.", 1));
C.push(B("It receives the transcript, translation, timings and synthesized speech.", 1));
C.push(B("**Precision:**"));
C.push(B("ASR models: int8 (sherpa-onnx)", 1));
C.push(B("Gemma 4 E2B: LiteRT-LM's mixed 2/4/8-bit QAT format; the NPU build is compiled ahead-of-time for QCS8275 with QAIRT 2.50", 1));
C.push(B("TTS: ONNX fp32 (Piper, ViFastTts, Matcha) and int8 (Supertonic-2)", 1));
C.push(B("**Vietnamese input.** The Vietnamese ASR outputs upper case with no punctuation."));
C.push(B("It is lower-cased, a rule-based question mark is added, and it is translated in one Gemma call.", 1));
C.push(B("The system prompt states that the input is an unpunctuated transcript.", 1));
C.push(B("System prompts per direction are generated from the Python core, so PC and devices translate identically.", 1));
C.push(B("**User controls:**"));
C.push(B("partner-language selector (EN / KO / ZH)", 1));
C.push(B("one hold-to-talk (or tap-to-toggle) button per speaker; replay button", 1));
C.push(B("status line with per-stage times", 1));
C.push(B("`start.sh npu|gpu|cpu` selects the accelerator", 1));
C.push(B("**Fallbacks:**"));
C.push(B("if the NPU is unavailable, `start.sh gpu` (Adreno 623, Vulkan) or `start.sh cpu` run the same pipeline", 1));
C.push(B("on Android the browser UI remains available if the app is not installed", 1));
C.push(B("**Development tools** (not part of the runtime): host cross-compilers, benchmark scoring on a PC (COMET)."));
C.push(B("Qualcomm AI Hub was not used. The VENTUNO Q board used for development and measurement was a Qualcomm Device Cloud (QDC) device.", 1));

C.push(H2("3.3 Minimum requirements to run this build"));
C.push(table([2300, W - 2300], ["Component", "Minimum requirement / compatibility"], [
  ["Processor / accelerator", [
    PS("**VENTUNO Q build (tested):**"),
    BS("Qualcomm QCS8275 with Hexagon v75 NPU (FastRPC `/dev/fastrpc-cdsp`)"),
    BS("Adreno 623 for the GPU mode; aarch64 CPU"),
    BS("Other QCS8275 boards: estimated compatible (same SoC and NPU model)"),
    PS(""),
    PS("**Android build (tested):**"),
    BS("QCS8550 (Adreno 740) and Snapdragon 8 Elite / SM8750 (Adreno 830, Galaxy S25 Ultra)"),
    BS("GPU via OpenCL, arm64-v8a"),
    BS("Other Snapdragon 8 Gen 2 / Gen 3 phones: estimated compatible, not tested"),
  ]],
  ["Memory and storage", [
    PS("**Tested peak RAM** (all 4 languages loaded):"),
    BS(`VENTUNO Q NPU: ${npuRSS} MB process RSS`),
    BS(`QCS8550: ${qcsRSS} MB RSS + ${qcsGfx} MB GPU (graphics)`),
    ...(S25 ? [BS(`Galaxy S25 Ultra: ${mb(S25.s.device_summary.peak_rss_kb)} MB RSS + ${mb((S25.s.meminfo_peak_kb || {}).graphics || 0)} MB graphics`)] : []),
    BS("Minimum: 8 GB RAM (estimated)"),
    PS(""),
    PS("**Storage:**"),
    BS("VENTUNO Q: 3.45 GB installed (NPU) + 0.1 GB QAIRT; +4.7 GB for the optional CPU/GPU Gemma files"),
    BS("QCS8550 / Galaxy S25 Ultra: ~2.9 GB in `/sdcard/CabinTranslation/models` for the app (or `/data/local/tmp/cabin` for the adb bundle)"),
    BS("Keep ≥ 1 GB free for logs"),
  ]],
  ["OS and software", [
    PS("**VENTUNO Q:**"),
    BS("Ubuntu 24.04 aarch64 (glibc ≥ 2.39)"),
    BS("Stock FastRPC (`libcdsprpc.so.1`); user in groups `fastrpc` and `render`"),
    BS("Python 3 standard library, only for the optional HTTPS front"),
    BS("Bundled: sherpa-onnx 1.13.8, ONNX Runtime 1.28.2, LiteRT-LM C API 0.19.1 (CPU/GPU), LiteRT-LM 0.18 NPU runtime + LiteRT Qualcomm dispatch"),
    BS("QAIRT 2.50.0.260828 (separate archive)"),
    BS("No root, compiler or package installation required"),
    PS(""),
    PS("**Android:**"),
    BS("Tested: Android 13 (QCS8550) and Android 17 (Galaxy S25 Ultra)"),
    BS("arm64 with the vendor GPU OpenCL driver"),
    BS("\"All files access\" permission for the app (granted by install.sh)"),
    BS("adb on a host (USB or wireless debugging) for installation"),
  ]],
  ["Audio and peripherals", [
    BS("Microphone and speaker/headphones, either on the board (USB/onboard audio with a local monitor and Firefox) or on the client device that opens the UI (laptop/phone browser over https on the LAN)"),
    BS("QCS8550 tablet / Galaxy S25 Ultra: built-in microphone and speaker"),
    BS("A screen for the UI"),
    BS("Optional: Ethernet cable for LAN access while Wi-Fi is off"),
  ]],
], { firstColFill: true, firstColBold: true }));

C.push(H2("3.4 Install and run offline"));
C.push(P("**A** = VENTUNO Q · **B** = QCS8550 tablet · **C** = Galaxy S25 Ultra (B and C use the same Android package).", { size: 18 }));
C.push(table([2300, W - 2300], ["Step", "What to do"], [
  ["Prepare", [
    PS("**A:**"),
    BS("Copy `CabinTranslation-VentunoQ-v1.0.tar` and `qairt-2.50-libs.tar` to the board (USB stick or scp). Nothing else is downloaded."),
    PS("**B / C:**"),
    BS("A host PC with adb: USB, or wireless debugging (`adb pair` once, then `adb connect <phone-ip>:<port>`)"),
    BS("The wireless port changes after reconnects; check with `adb devices -l`", 1),
    BS("Join the release parts and unpack on the host:"),
    BS("`cat CabinTranslation-QCS8550-v1.0.tar.part-* > CabinTranslation-QCS8550-v1.0.tar`", 1),
    BS("`tar -xf CabinTranslation-QCS8550-v1.0.tar`", 1),
  ]],
  ["Install", [
    PS("**A:**"),
    BS("`tar -xf CabinTranslation-VentunoQ-v1.0.tar`"),
    BS("`cd CabinTranslation-VentunoQ-v1.0`"),
    BS("`tar -xf ../qairt-2.50-libs.tar -C lib_npu`"),
    BS("`sh check.sh` → `CHECK PASSED` (verifies SoC, NPU access, libraries, SHA-256 of every file)"),
    PS("**B / C:** inside `CabinTranslation-QCS8550-v1.0/`:"),
    BS("`bash install.sh <adb-serial>` (same package for the tablet and the S25 Ultra)"),
    BS("installs the APK, grants file access, pins landscape", 1),
    BS("pushes `models/` to `/sdcard/CabinTranslation/models` and starts the app", 1),
  ]],
  ["Disconnect and launch", [
    PS("**A:**"),
    BS("Disable networking: `nmcli radio wifi off`, unplug Ethernet"),
    BS("Launch: `sh start.sh npu`"),
    BS("Ready after ~25 s: `READY: open http://127.0.0.1:8080/`"),
    BS("UI status: `Sẵn sàng · models loaded on device: en, ko, vi, zh · LLM npu`"),
    BS("For a phone/laptop on a local cable: `HOST=0.0.0.0 HTTPS=1 sh start.sh npu`, then open https://<board-ip>:8443/"),
    PS("**B / C:**"),
    BS("Enable airplane mode"),
    BS("Tap the **CabinTranslation** app (~20–25 s load)"),
    BS("Header shows **Sẵn sàng** and **Offline**; footer `Gemma 4 E2B trên GPU`"),
    BS("Tablet alternative (browser UI): `adb shell sh /data/local/tmp/cabin/start.sh`"),
  ]],
  ["Run the scenario", [
    BS("Pick the partner language (English / 한국어 / 中文)."),
    BS("The Vietnamese speaker holds **Giữ để nói**, the partner holds **Hold to talk**; release to translate."),
    BS("Expected: the recognized sentence and the translation appear in the log, the translation is spoken, and the status line shows ASR / MT / TTS / total milliseconds."),
  ]],
  ["Reset or troubleshoot", [
    PS("**Restart:**"),
    BS("A: `sh stop.sh && sh start.sh npu`"),
    BS("B / C: close and reopen the app, or `adb shell am force-stop vn.cabin.translate`"),
    PS("**Troubleshooting:**"),
    BS("App says 'Thiếu model' → run `install.sh` again (it skips files already present)"),
    BS("Verify without a microphone: `sh selftest.sh npu` (12 bundled utterances)"),
    BS("`QAIRT 2.50 libraries missing` → untar `qairt-2.50-libs.tar` into `lib_npu`"),
    BS("Microphone silent → open the UI via 127.0.0.1 or https (browsers block the mic on plain-http LAN addresses)"),
    PS("**Logs:** `out/server.log`, `out/selftest.log`; every live utterance is saved to `out/live/`."),
  ]],
], { firstColFill: true, firstColBold: true }));

// 4
C.push(new Paragraph({ children: [new PageBreak()] }));
C.push(H1("4. Self-recorded test results"));
const NUTT = PAIRS.reduce((a, p) => a + NPU.s.pairs[p].n, 0);
C.push(P(`**Test record.** Organizer Round 3 sample set, all six directions, ${NUTT} utterances per run:`, { after: 40 }));
C.push(B(PAIRS.map((p) => `${LBL[p]} ${NPU.s.pairs[p].n}`).join(" · ")));
C.push(B("Each utterance goes speech-in → speech-out on the device in batch mode (same engine and models as the UI)."));
C.push(B("Scoring on a PC."));
C.push(P("**Runs:**", { after: 40, keep: true }));
C.push(B(`Device A (VENTUNO Q), NPU: \`results/ventunoq/${NPU.name}\` — **submitted build**${npuOffline ? ", **measured fully offline**, installed from the judge package" : ""}`));
C.push(B(`Device B (QCS8550, GPU): \`results/qcs8550/${QCS.name}\`${QCS.name.endsWith("_offline") ? " — **measured fully offline**" : ""}${qcsPunct ? " — earlier 2-call Vietnamese build" : ""}`));
if (S25) C.push(B(`Device C (Galaxy S25 Ultra, GPU): \`results/s25ultra/${S25.name}\` (latency) + battery power (Table 4.5)`));

if (npuOffline) {
  const sd = path.join(NPU.dir, "syslog");
  const nl = fs.readFileSync(path.join(sd, "network.log"), "utf8").trim().split("\n");
  const run = nl.filter((l) => / engine_pid=\d/.test(l));
  const socks = run.map((l) => (l.match(/engine_net_sockets=(\d+)/) || [])[1]).filter(Boolean).map(Number);
  const mark = (k) => nl.find((l) => l.includes(k));
  C.push(H2("VENTUNO Q benchmark measured fully offline"));
  C.push(P(`Run folder: \`results/ventunoq/${NPU.name}\` (NPU, v1.0). The board was installed from the judge package (\`CabinTranslation-VentunoQ-v1.0.tar\` + \`qairt-2.50-libs.tar\`, SHA-256 verified, \`check.sh\` → CHECK PASSED; \`install/\`) and had **no internet during the whole ${NUTT}-utterance run**.`, { after: 40 }));
  C.push(B("Wi-Fi (the board's only internet route) was switched off before the engine started and back on after it finished."));
  C.push(B("The run was driven over the local Ethernet cable to the host (`end0`, 192.168.5.0/24, no default route)."));
  C.push(B("Checked on the board: no default route, pings to 8.8.8.8 and 1.1.1.1 failing, Wi-Fi radio disabled."));
  C.push(B(`Every ~15 s during the run: engine non-loopback sockets **max ${socks.length ? Math.max(...socks) : "n/a"}** over ${socks.length} samples, all with no default route.`));
  C.push(P("**Raw evidence in the run folder** (`syslog/`, captured on the board by `edge/tools/board_syslog.sh`):", { after: 40, keep: true }));
  C.push(B("`network.log` — offline markers + network state, engine sockets and memory every 15 s"));
  C.push(B("`journal_during_run.log`, `journal_boot_full.log` — systemd journal (unfiltered)"));
  C.push(B("`dmesg_during_run.log`, `dmesg_full.log` — kernel log"));
  C.push(B("`network_state_end.txt` (ip addr / route / ss), `system_info.txt`"));
  C.push(B("`device_stderr.log` — engine log; `result.jsonl` — raw per-utterance output and timings; `wav/` — spoken outputs"));
  C.push(P("**Raw log lines** (verbatim from `syslog/network.log`):", { size: 18, after: 40, keep: true }));
  [...new Set([mark("OFFLINE-REQUEST"), mark("OFFLINE-CONFIRMED-START"), run[0], run[Math.floor(run.length / 2)], run[run.length - 1], mark("OFFLINE-CHECK-END"), mark("ONLINE-RESTORED")].filter(Boolean))]
    .forEach((l) => C.push(LOG(l)));
  C.push(P("Board clock is UTC (22:44 in Vietnam = 15:44 UTC).", { size: 16, after: 80, italics: true }));
}
const qcsOffline = QCS.name.endsWith("_offline");
if (qcsOffline) {
  const di = JSON.parse(fs.readFileSync(path.join(QCS.dir, "device_info.json"), "utf8"));
  const de = JSON.parse(fs.readFileSync(path.join(QCS.dir, "device_info_end.json"), "utf8"));
  C.push(H2("QCS8550 benchmark measured fully offline"));
  C.push(P(`Run folder: \`results/qcs8550/${QCS.name}\` (v1.0 build). The tablet had **no network during the whole ${NUTT}-utterance run**.`, { after: 40 }));
  C.push(B("Checked **on the device every ~15 s** and written to the raw `network.log`:"));
  C.push(B("no active default network", 1));
  C.push(B("no IPv4 address other than loopback", 1));
  C.push(B("pings to 8.8.8.8 and 1.1.1.1 failing", 1));
  C.push(B(`Start: default_network=${di.default_network}, ping 8.8.8.8 ${di["ping_8.8.8.8"]}, ping 1.1.1.1 ${di["ping_1.1.1.1"]}`));
  C.push(B(`End: default_network=${de.default_network}, ping 8.8.8.8 ${de["ping_8.8.8.8"]}, ping 1.1.1.1 ${de["ping_1.1.1.1"]}`));
  C.push(B(`Samples with any connectivity during the run: **${di.samples_online_during_run}**`));
  C.push(B("Started over **USB adb**; executed entirely on the tablet."));
  C.push(B("The tablet clock is not network-synced while offline; a CLOCK-NOTE line in `network.log` maps device time to wall time."));
  C.push(P("**Raw evidence in the run folder:**", { after: 40, keep: true }));
  C.push(B("`network.log` — network state + engine memory every 15 s"));
  C.push(B("`device_stderr.log` — engine log"));
  C.push(B("`result.jsonl` — raw per-utterance output and timings"));
  C.push(B("`shots/start.png`, `shots/middle.png`, `shots/end.png` — screenshots taken by the tablet itself"));
  C.push(B("`wav/` — spoken outputs"));
  C.push(B("`logcat/` — full, unfiltered Android logcat (every buffer), a full `adb bugreport`, `dumpsys connectivity` and `dumpsys netstats`"));
  const ev = QCS.s.offline_evidence;
  if (ev) {
    C.push(P(`**Raw log lines** (verbatim from \`network.log\`; ${ev.samples_fully_offline} of ${ev.samples} samples fully offline):`, { size: 18, after: 40, keep: true }));
    const lines = fs.readFileSync(path.join(QCS.dir, "network.log"), "utf8").trim().split("\n");
    const smp = lines.filter((l) => l.includes(" wav="));
    [...new Set([ev.start_line, ...smp.slice(0, 2), smp[Math.floor(smp.length / 2)], ...smp.slice(-2), ev.end_line, ev.clock_note].filter(Boolean))]
      .forEach((l) => C.push(LOG(l.replace(/ mem=\[.*\]/, " mem=[…]"))));
    const sl = ev.system_logs;
    if (sl) {
      C.push(P("", { after: 40 }));
      C.push(P(`**Android system log** (logcat, unfiltered, in \`${sl.folder}\`). Key lines:`, { size: 18, after: 40, keep: true }));
      C.push(B("the engine start (the app is force-stopped just before the run)", 1));
      C.push(B("Wi-Fi kept sending DHCPDISCOVER and got no answer", 1));
      C.push(B("Android's own Wi-Fi traffic counters stayed at zero", 1));
      sl.key_lines.forEach((l) => C.push(LOG(l)));
    }
    C.push(P("", { after: 80 }));
  }
}

C.push(P("**Offline operation**", { after: 40, keep: true }));
C.push(B("Confirmed by the team on all three devices: the demo videos were recorded with networking disabled (the S25 Ultra and QCS8550 apps show ✈ Offline). Inference never uses the network."));
if (npuOffline) C.push(B("VENTUNO Q NPU benchmark (submitted build): fully offline, with raw logs (above)."));
if (qcsOffline) C.push(B("QCS8550 benchmark: fully offline, with raw logs (above)."));
const onl = [!npuOffline && "VENTUNO Q", !qcsOffline && "QCS8550", S25 && "Galaxy S25 Ultra"].filter(Boolean);
if (npuOffline && S25) C.push(B("Galaxy S25 Ultra latency/power runs: orchestrated from a host PC over wireless adb with the network connected, so their logs record that control link."));
else if (onl.length) C.push(B(`${onl.join(" and ")} benchmarks: the ${NUTT}-utterance batch runs were orchestrated from a host PC over ssh / adb, so the log fields record that control link.`));
if (!npuOffline) C.push(B(`VENTUNO Q: internet ${net(NPU)}`, 1));
if (!qcsOffline) C.push(B(`QCS8550: ${net(QCS)}`, 1));
if (S25) C.push(B("Galaxy S25 Ultra: Wi-Fi on for wireless debugging; the power run was on battery", 1));
C.push(B(`Evidence that the engine itself makes no network calls: its sockets were sampled every ~1 s during the full VENTUNO Q NPU run — **maximum non-loopback TCP/UDP sockets of the engine process = ${sock(NPU) ?? "n/a"}**.`));

C.push(P("**Evidence folder:** https://github.com/mxngocqb/CabinTranslation/tree/main/results → `results/<device>/<run>/`", { after: 40, keep: true }));
C.push(B("`summary.md`, `summary.json` — scores, latency, memory"));
C.push(B("`result.jsonl` — raw device output, per-utterance timings"));
C.push(B("`rows.jsonl` — per-utterance output with references"));
C.push(B("`device_stderr.log` — engine log"));
C.push(B("`meminfo_samples.json` — memory / GPU / socket samples"));
C.push(B("`stage/` (16 kHz inputs), `wav/` (spoken outputs)"));
C.push(B("Offline runs also contain the raw system logs: QCS8550 — `network.log` (network state logged on the device every 15 s), `shots/` (device screenshots), `logcat/` (Android logcat + bugreport); VENTUNO Q — `syslog/` (network.log, systemd journal, kernel log) and `install/` (package install + check.sh output)"));
C.push(B("Dashboard with audio: `dashboard/index.html`"));

C.push(P("**Metric definitions**", { after: 40, keep: true }));
C.push(B("BLEU and chrF++ (sacreBLEU) on normalized text: lower-case, no punctuation, numbers spelled out. KO/ZH targets use character-level BLEU."));
C.push(B("COMET = Unbabel/wmt22-comet-da."));
C.push(B("ASR error: WER (VI, EN) or CER (KO, ZH)."));
C.push(B("ASR-BLEU = BLEU of the spoken output re-recognized by ASR on the PC."));
C.push(B("Latency = wall time inside the engine from reading the input WAV to finishing the output WAV (ASR + text prep + MT + TTS), excluding one-time model loading. p50 / p95 over all utterances of a direction."));
C.push(P("", { after: 60 }));

C.push(table([1700, W - 1700 - 1800, 1800], ["Area", "Result and method", "Evidence reference"], [
  ["Translation quality", [
    PS("**Mean COMET** over the six directions:"),
    BS(`VENTUNO Q NPU: **${f1(mean(NPU, "comet"))}**`),
    BS(`QCS8550 GPU: ${f1(mean(QCS, "comet"))}${qcsPunct ? " (2-call build)" : ""}`),
    PS("Per-direction BLEU / chrF++ / COMET / ASR-BLEU: Tables 4.1–4.2."),
    PS("Representative outputs and failures: Table 4.4."),
    PS("**Known failures:**"),
    BS(`empty ASR on ${emptyAsr.length} utterance(s) (${emptyAsr.join(", ") || "none"})`),
    BS("KO references in the sample set contain misaligned pairs (e.g. VK-0242), which lowers KO→VI BLEU"),
  ], "`summary.md`, `rows.jsonl` of each run"],
  ["Inference / response time", [
    PS("End-to-end speech-in → speech-out, **p50 / p95** per direction:"),
    BS(`VENTUNO Q NPU: **${sec(npuP50[0])}–${sec(npuP50[1])} s / ${sec(npuP95[0])}–${sec(npuP95[1])} s**`),
    BS(`QCS8550 GPU: ${sec(qcsP50[0])}–${sec(qcsP50[1])} s / ${sec(qcsP95[0])}–${sec(qcsP95[1])} s`),
    ...EXTRA.map((e) => BS(`${e[0].split(" (")[0]} ${e[1].split(" · ")[0]}: p50 ${sec(rng(e[2], "total_ms_p50")[0])}–${sec(rng(e[2], "total_ms_p50")[1])} s (Table 4.5)`)),
    PS(`Gemma on NPU: ${f0(mean(NPU, "mt_ttft_ms_mean"))} ms TTFT, ${f1(mean(NPU, "mt_decode_tps_mean"))} tokens/s decode.`),
    PS(`Component means: Table 4.3. ${NUTT} utterances per run, one run per configuration.`),
  ], "`result.jsonl` (per-utterance asr/mt/tts/total ms)"],
  ["Model size", [
    PS("Model files in the VENTUNO Q package: **3,255 MB**"),
    BS("Gemma 4 E2B QCS8275 NPU: 2,596 MB"),
    BS("ASR 268 MB: Zipformer-30M vi 29, X-ASR zh-en 167, Zipformer-ko 73"),
    BS("TTS 390 MB: ViFastTts 82, Piper 77, Supertonic-2 92, Matcha 88, Vocos 51"),
    PS("Libraries 189 MB (+107 MB QAIRT). Total installation 3.45 GB (+0.1 GB)."),
    PS("QCS8550 and Galaxy S25 Ultra (same Android package): Gemma `-gpu` 2,232 MB + the same ASR/TTS."),
  ], "`SHA256SUMS`; `du` listing in the package README"],
  ["Peak memory", [
    PS("Process peak RSS (VmHWM, all four languages loaded, whole run):"),
    BS(`VENTUNO Q NPU: **${npuRSS} MB**`),
    BS(`QCS8550: ${qcsRSS} MB + ${qcsGfx} MB graphics (dumpsys meminfo)`),
    ...(S25 ? [BS(`Galaxy S25 Ultra: ${mb(S25.s.device_summary.peak_rss_kb)} MB + ${mb((S25.s.meminfo_peak_kb || {}).graphics || 0)} MB graphics`)] : []),
    PS("Measured by the engine (VmHWM) and polled every ~1 s by the host."),
  ], "`summary.json` → device_summary.peak_rss_kb, `meminfo_samples.json`"],
  ["Device operation & UX", [
    PS("**Scenario completed: yes**, on all three devices, offline."),
    BS("Uncut videos: 1:43 (S25 Ultra), 1:35 (QCS8550), 2:08 (VENTUNO Q), covering VI↔EN, VI↔KO and VI↔ZH with no crash or restart. A misrecognized utterance is simply repeated."),
    BS("VENTUNO Q live UI test (2026-11-11): speech from a laptop browser over HTTPS was recognized, translated on the NPU and spoken back (e.g. a 6 s introduction in 2.9 s)."),
    BS("Android app on the QCS8550 tablet (2026-11-13): EN→VI 727 ms (ASR 171 · MT 409 · TTS 144)."),
    BS("Android app on the Galaxy S25 Ultra (2026-11-13): VI→EN 562 ms (ASR 53 · MT 279 · TTS 228)."),
    BS("Startup ~20–25 s. Restart with `stop.sh` / `start.sh` (A) or by reopening the app (B / C)."),
  ], "Section 2 timestamps; `out/server.log`, `out/live/*.wav`"],
], { firstColFill: true, firstColBold: true }));

C.push(H2("Table 4.1 — VENTUNO Q, Gemma on the Hexagon NPU (submitted build)"));
C.push(table([1300, 1700, 1300, 1300, 1300, 3006], ["Direction", "ASR error", "BLEU", "chrF++", "COMET", "ASR-BLEU (spoken output)"], qualityRows(NPU), { zebra: true }));
C.push(H2(`Table 4.2 — QCS8550, Gemma on the Adreno 740 GPU${qcsPunct ? " (earlier 2-call build)" : qcsOffline ? " (measured offline)" : ""}`));
C.push(table([1300, 1700, 1300, 1300, 1300, 3006], ["Direction", "ASR error", "BLEU", "chrF++", "COMET", "ASR-BLEU (spoken output)"], qualityRows(QCS), { zebra: true }));
C.push(H2("Table 4.3 — Latency per stage (mean ms) and end-to-end p50 / p95 (ms)"));
const lw = [1100, 900, 1000, 1000, 1000, 1100, 1000, W - 7100];
C.push(P("**VENTUNO Q NPU**", { after: 40, keep: true }));
C.push(table(lw, ["Dir.", "ASR", "Punct.", "MT", "TTFT", "tok/s", "TTS", "Total p50 / p95"], latencyRows(NPU), { zebra: true, size: 17 }));
C.push(P("", { after: 40 }));
C.push(P(`**QCS8550 GPU**${qcsOffline ? " (measured offline)" : ""}`, { after: 40, keep: true }));
C.push(table(lw, ["Dir.", "ASR", "Punct.", "MT", "TTFT", "tok/s", "TTS", "Total p50 / p95"], latencyRows(QCS), { zebra: true, size: 17 }));
C.push(H2("Table 4.4 — Representative inputs and outputs (VENTUNO Q NPU run)"));
C.push(table([1300, 3500, 3006, 2100], ["ID", "ASR transcript (device)", "Device translation", "Reference / time"],
  EX.map((r) => [[r.id.split("__")[1], LBL[r.pair]], r.mt_in || r.asr, r.hyp, [r.ref, `**${f0(r.total_ms)} ms**`]]), { size: 16 }));

if (EXTRA.length) {
  C.push(H2("Table 4.5 — Same Android build on Samsung Galaxy S25 Ultra (latency only; network connected)"));
  C.push(P(`Same engine, models and prompts; full sample set (${NUTT} utterances). Only timing is reported here, as requested; transcripts and translations are in each run's \`rows.jsonl\`.`, { size: 18 }));
  const ew = [1050, 1000, 1000, 1000, 1000, 1050, 1000, W - 7100];
  EXTRA.forEach(([dev, acc, run]) => {
    const ds = run.s.device_summary || {}, mp = run.s.meminfo_peak_kb || {};
    C.push(P(`**${dev} — Gemma on ${acc}**`, { after: 20, size: 18, keep: true }));
    C.push(B(`Run: \`${run.name}\``, 0, true));
    C.push(B(`Peak RSS ${mb(ds.peak_rss_kb || 0)} MB${mp.graphics ? ` + ${mb(mp.graphics)} MB GPU` : ""}`, 0, true));
    if ("net_conns" in mp) C.push(B(`Engine network sockets: max ${mp.net_conns}`, 0, true));
    C.push(P("", { after: 20, keep: true }));
    C.push(table(ew, ["Dir.", "ASR", "Punct.", "MT", "TTFT", "tok/s", "TTS", "Total p50 / p95"], latencyRows(run), { zebra: true, size: 17 }));
  });
  // battery power measured on the S25 Ultra (edge/tools/power_bench_android.py), if available
  const pdir = path.join(R, "s25ultra");
  const pw = fs.existsSync(pdir) ? fs.readdirSync(pdir).filter((x) => x.startsWith("power_")).sort().reverse()
    .map((x) => path.join(pdir, x, "summary.json")).find((f) => fs.existsSync(f)) : null;
  if (pw) {
    const q = JSON.parse(fs.readFileSync(pw, "utf8"));
    C.push(P("", { after: 40 }));
    C.push(P("**Power consumption — Galaxy S25 Ultra**", { after: 20, size: 18, keep: true }));
    C.push(B(`Run: \`${path.basename(path.dirname(pw))}\``, 0, true));
    C.push(B("On battery, charger unplugged; no root", 0, true));
    C.push(B("`dumpsys battery` current / voltage / charge counter sampled ~1/s", 0, true));
    C.push(P("", { after: 20, keep: true }));
    C.push(table([3300, 1300, 1300, 1300, 1300, W - 8500], ["Phase", "Duration s", "Avg current mA", "Avg power W", "Charge used mAh", "Battery temp °C"], [
      ["Idle baseline (screen on, nothing running)", f0(q.idle.duration_s), f0(q.idle.avg_current_ma), f2(q.idle.avg_power_w), f1(q.idle.charge_used_mah), `${q.idle.temp_c_start_end[0]} → ${q.idle.temp_c_start_end[1]}`],
      [`Pipeline running (${q.utterances} utterances, speech→speech)`, f0(q.load.duration_s), f0(q.load.avg_current_ma), f2(q.load.avg_power_w), f1(q.load.charge_used_mah), `${q.load.temp_c_start_end[0]} → ${q.load.temp_c_start_end[1]}`],
    ], { zebra: true, size: 17 }));
    C.push(P("", { after: 20 }));
    C.push(B(`Pipeline power (load − idle): **${f2(q.pipeline_power_w)} W**`));
    C.push(B(`Energy per translated utterance: **${f1(q.energy_per_utterance_j)} J** for the pipeline alone; ${f1(q.total_energy_per_utterance_j)} J including the screen/OS baseline`));
    C.push(B(`${q.utterances} utterances in ${f0(q.load_wall_s)} s, back-to-back — the worst case. In a real conversation the device idles between turns.`));
  }
}

C.push(H2("Known limitations"));
[
  ["Push-to-talk per utterance; no streaming recognition or barge-in yet.", ["The Android app already segments with Silero VAD."]],
  ["Single-call Vietnamese input trades accuracy for speed.", ["VI→EN loses ~1.8 COMET / ~7 BLEU against the 2-call punctuation pass.", "`--punct-pass` restores it."]],
  ["Vietnamese ASR on the VI–ZH sample voices: WER 12.3% vs 1.7–4.8% on the other sets.", ["ASR errors propagate to translation."]],
  ["One utterance with empty ASR output (EV-2748).", []],
  ["Network evidence differs per device.", npuOffline
    ? ["VENTUNO Q NPU and QCS8550 benchmarks: fully offline, with raw system logs.", "The Galaxy S25 Ultra latency/power runs were orchestrated over wireless adb, so their logs record that control link."]
    : ["QCS8550 benchmark: fully offline (on-device `network.log` 55/55 samples offline, plus logcat).", "VENTUNO Q and Galaxy S25 Ultra batch runs: orchestrated over ssh / wireless adb, so their logs record that control link.", "Engine network sockets on VENTUNO Q = 0."]],
  ["The NPU requires QAIRT 2.50 runtime libraries, distributed separately from the main package.", []],
].forEach(([t, sub]) => { C.push(B(t)); sub.forEach((x) => C.push(B(x, 1))); });
C.push(H2("Next development steps"));
[
  ["**Streaming ASR + VAD auto-segmentation** on both devices.", "Check: end-of-speech-to-audio latency and WER on the sample set, with the same scoring scripts."],
  ["**Move Korean/Chinese TTS off the CPU critical path** (NPU via QNN, or a faster vocoder) to bring VI→KO/ZH p50 below 0.6 s.", "Check: `selftest.sh` and the full-benchmark per-stage TTS times, round-trip CER."],
  ["**Domain adaptation for factory vocabulary**: a glossary in the prompt, then LoRA on spoken-style parallel data.", "Check: COMET/BLEU on the sample set and on a factory term list, with the scenario script as a regression test."],
].forEach(([t, chk]) => { C.push(B(t)); C.push(B(chk, 1)); });

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
const out = process.env.OUT || path.join(__dirname, `${TEAM.replace(/[\[\]]/g, "")}_Prototype Submission_V3.docx`);  // OUT=... if the file is open in Word
Packer.toBuffer(doc).then((b) => { fs.writeFileSync(out, b); console.log("wrote", out, "| runs:", NPU.name, QCS.name); });
