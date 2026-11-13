# dashboard/ — results dashboard

| File | Purpose |
|---|---|
| `build_report.py` | Reads every run under `results/`, picks the latest complete 6-direction run per device/backend as **official**, writes `index.html` here and `results/README.md` |
| `report_template.html` | Page template (tabs: overview, QCS8550, VENTUNO Q, PC, model studies, per-utterance audio, run history) |
| `index.html` | Generated, self-contained page (data inlined). Audio is linked from `../results/<run>/` |
| `serve.sh` | `bash dashboard/serve.sh [port]` → http://localhost:8000/dashboard/ (serves the repo root so audio plays) |
| `export_dashboard_artifact.py` | Export page + MP3 audio packs for publishing as a claude.ai artifact |

```bash
python dashboard/build_report.py      # after any benchmark
bash dashboard/serve.sh
```

The **per-utterance** tab lists all 905 sample utterances. It shows the source audio, the reference, and side by side the
transcript, translation, latency and spoken output of every official device run (QCS8550 GPU, VENTUNO Q NPU / GPU / CPU).
