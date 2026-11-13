# Submission checklist — deadline 2026-11-13 23:59

Brief requirement → artifact → status. "Team" = needs a person (recording, uploading, filling names/links).

| # | Requirement (Brief §7–8) | Artifact | Status |
|---|---|---|---|
| 1 | Submission document `.docx`/`.pdf`, named `[TeamName]_Prototype Submission_V3` | `node docs/submission/build_submission_docx.js "<TeamName>"` → `docs/submission/<TeamName>_Prototype Submission_V3.docx` | Generated from results. **Team:** fill the yellow fields, then export to PDF |
| 2 | Demo video, uncut, network disabled on camera, screen/logs readable | Script: `docs/submission/demo_scenario.md` (~30 min, VI⇄EN/KO/ZH) | **Team:** record on VENTUNO Q (and QCS8550 if possible), upload, put link + timestamps in §2 |
| 3 | Offline installation package (models + configs + dependencies + launch files) | `CabinTranslation_submission/ventunoq/CabinTranslation-VentunoQ-v1.0.tar` (3.4 GB) + `qairt-2.50-libs.tar` (107 MB) + `SHA256SUMS.txt` | ✅ VENTUNO Q built, installed fresh on the board, `check.sh` PASSED, `selftest.sh` 12/12 OK. QCS8550 bundle + APK: 2026-11-12 |
| 4 | Private GitHub repository shared with `saigonaihub` | this repo (`.gitignore` excludes models/data/wavs/keys) | **Team:** create a private repo, push, invite `saigonaihub`, put the URL in §3.1. Do not commit `qdc_id_*.pem` (git-ignored) |
| 5 | Measured benchmark results with raw logs/screenshots, network disconnected | `results/ventunoq/*`, `results/qcs8550/*` (summary.md, result.jsonl, logs, wavs) | VENTUNO Q: measured with Wi-Fi **on** (the user forbade turning it off on the QDC board), with an engine-socket log (`net_conns`). QCS8550: re-run the 1-call build **offline** (airplane mode, adb over USB): `python edge/tools/run_device_bench.py --pairs vi-en en-vi vi-ko ko-vi vi-zh zh-vi` |
| 6 | Reproduction guide | `README.md`, `edge/*/README.md`, `edge/ventunoq-linux/package/README_INSTALL.md` | ✅ |
| 7 | Minimal UI judges can operate | Web UI (`start.sh`), HTTPS for LAN mic, Android app | ✅ VENTUNO Q tested live over HTTPS on 2026-11-11 |
| 8 | Licenses / third-party terms | README §Licenses; QAIRT shipped separately | **Team:** confirm whether to bundle `qairt-2.50-libs.tar` (Qualcomm terms) or keep it as a separate download |

## After the QCS8550 offline run (2026-11-12)

```bash
python dashboard/build_report.py                                   # refresh results/README.md + dashboard
node docs/submission/build_submission_docx.js "<TeamName>"         # refresh every table in the document
```

`node` is the VS Code server binary, run with `NODE_PATH=../CabinTranslation_submission/.tools/node_modules`.
The `docx` npm package is installed there.
