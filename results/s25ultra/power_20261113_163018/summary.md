# Power measurement 20261113_163018 — SM-S938B (SM8750)

- Method: `dumpsys battery` sampled ~1/s (current now, voltage, charge counter); on battery (charging at start/end: False/False); screen state unchanged; no root.
- Load: `cabin_edge` batch run, 905 utterances speech→speech (6 directions), 778 s wall, engine rc=0.

| phase | duration s | avg current mA | avg voltage V | avg power W | charge used mAh | temp °C start→end |
|---|---|---|---|---|---|---|
| idle (baseline) | 197.0 | 337.0 | 3.99 | 1.344 | 34.5 | 40.3 → 38.0 |
| load (pipeline running) | 776.9 | 1103.5 | 3.928 | 4.33 | 251.2 | 38.0 → 39.7 |

- **Pipeline power (load − idle): 2.986 W**
- **Energy per utterance (pipeline only): 2.57 J**; including baseline (screen/OS): 3.72 J
