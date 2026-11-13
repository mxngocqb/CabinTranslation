"""Measure battery power/energy of the on-device pipeline on an Android phone (no root needed).

python edge/tools/power_bench_android.py --serial <adb-serial> [--idle-s 180] [--tag s25ultra]

The device must run on battery (charger unplugged; adb over Wi-Fi). `dumpsys battery` is sampled about once a second:
`current now` (µA, negative = discharge), `Charge counter` (µAh, coulomb counter), and the voltage.
Phases (screen state unchanged, nothing else started):
  1. idle — nothing running: the baseline (screen, radios, OS);
  2. load — cabin_edge batch run over the benchmark manifest already on the device (speech in → speech out, all 6 directions).
Reports the average current, voltage and power per phase, the charge used (counter delta), and the
**energy per utterance attributable to the pipeline** = (P_load − P_idle) × T_load / N.
Writes results/<tag>/power_<ts>/{samples.json, summary.json, summary.md}.
"""
import argparse
import datetime as dt
import json
import re
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = "/data/local/tmp/cabin"


def sh(serial, cmd, timeout=60):
    return subprocess.run(["adb", "-s", serial, "shell", cmd], capture_output=True, text=True, timeout=timeout).stdout


def battery(serial):
    out = sh(serial, "dumpsys battery", timeout=20)
    g = lambda pat: (lambda m: int(m.group(1)) if m else None)(re.search(pat, out))  # noqa: E731
    return {"t": time.time(), "current_ua": g(r"current now:\s*(-?\d+)"), "charge_uah": g(r"Charge counter:\s*(\d+)"),
            "voltage_mv": g(r"\n\s*voltage:\s*(\d+)"), "temp_dc": g(r"\n\s*temperature:\s*(\d+)"), "level": g(r"\n\s*level:\s*(\d+)"),
            "powered": bool(re.search(r"(AC|USB|Wireless|Dock) powered: true", out))}


class Sampler:
    def __init__(self, serial, phase):
        self.serial, self.phase, self.stop, self.samples = serial, phase, threading.Event(), []

    def run(self):
        while not self.stop.is_set():
            try:
                s = battery(self.serial)
                s["phase"] = self.phase[0]
                self.samples.append(s)
            except Exception:  # noqa: BLE001 - keep sampling through transient adb hiccups
                pass
            time.sleep(0.8)


def stats(samples, phase):
    xs = [s for s in samples if s["phase"] == phase and s["current_ua"] is not None and s["voltage_mv"]]
    if len(xs) < 2:
        return {}
    t = xs[-1]["t"] - xs[0]["t"]
    i_ma = sum(-s["current_ua"] for s in xs) / len(xs) / 1000
    v = sum(s["voltage_mv"] for s in xs) / len(xs) / 1000
    p = sum(-s["current_ua"] / 1e6 * s["voltage_mv"] / 1000 for s in xs) / len(xs)
    dq = (xs[0]["charge_uah"] - xs[-1]["charge_uah"]) / 1000 if xs[0]["charge_uah"] and xs[-1]["charge_uah"] else None
    return {"duration_s": round(t, 1), "samples": len(xs), "avg_current_ma": round(i_ma, 1), "avg_voltage_v": round(v, 3),
            "avg_power_w": round(p, 3), "charge_used_mah": round(dq, 1) if dq is not None else None,
            "energy_from_counter_j": round(dq * 3.6 * v, 1) if dq is not None else None,
            "temp_c_start_end": [xs[0]["temp_dc"] / 10 if xs[0]["temp_dc"] else None, xs[-1]["temp_dc"] / 10 if xs[-1]["temp_dc"] else None],
            "level_start_end": [xs[0]["level"], xs[-1]["level"]]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", required=True)
    ap.add_argument("--idle-s", type=int, default=180)
    ap.add_argument("--tag", default="s25ultra")
    ap.add_argument("--manifest", default=f"{DEV}/out/manifest.jsonl")
    a = ap.parse_args()
    b0 = battery(a.serial)
    if b0["powered"]:
        raise SystemExit("device is charging: unplug the charger (keep adb over Wi-Fi) and retry")
    n = int(sh(a.serial, f"wc -l < {a.manifest}").strip() or 0)
    model = sh(a.serial, "getprop ro.product.model").strip()
    soc = sh(a.serial, "getprop ro.soc.model").strip()
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "results" / a.tag / f"power_{stamp}"
    out.mkdir(parents=True)
    phase = ["idle"]
    smp = Sampler(a.serial, phase)
    th = threading.Thread(target=smp.run, daemon=True)
    th.start()
    print(f"[{model} / {soc}] idle baseline {a.idle_s} s ...", flush=True)
    time.sleep(a.idle_s)
    phase[0] = "load"
    print(f"load: cabin_edge over {n} utterances ...", flush=True)
    t0 = time.time()
    r = subprocess.run(["adb", "-s", a.serial, "shell",
                        f"cd {DEV} && rm -rf out/power_wav && mkdir -p out/power_wav && LD_LIBRARY_PATH=lib ./cabin_edge "
                        f"--config config.json --manifest {a.manifest} --out out/power_result.jsonl --wav-dir out/power_wav"],
                       capture_output=True, text=True)
    t_load = time.time() - t0
    phase[0] = "after"
    time.sleep(2)
    smp.stop.set()
    th.join(timeout=10)
    b1 = battery(a.serial)
    idle, load = stats(smp.samples, "idle"), stats(smp.samples, "load")
    res = {"device": model, "soc": soc, "utterances": n, "load_wall_s": round(t_load, 1), "idle": idle, "load": load,
           "charging_at_start": b0["powered"], "charging_at_end": b1["powered"], "engine_rc": r.returncode}
    if idle and load:
        dp = load["avg_power_w"] - idle["avg_power_w"]
        res["pipeline_power_w"] = round(dp, 3)
        res["energy_per_utterance_j"] = round(dp * t_load / max(n, 1), 2)
        res["total_energy_per_utterance_j"] = round(load["avg_power_w"] * t_load / max(n, 1), 2)
        res["utterances_per_1pct_battery"] = round(max(n, 1) / max(load["level_start_end"][0] - load["level_start_end"][1], 1), 0) \
            if load["level_start_end"][0] != load["level_start_end"][1] else None
    (out / "samples.json").write_text(json.dumps(smp.samples))
    (out / "summary.json").write_text(json.dumps(res, indent=1))
    md = [f"# Power measurement {stamp} — {model} ({soc})", "",
          f"- Method: `dumpsys battery` sampled ~1/s (current now, voltage, charge counter); on battery "
          f"(charging at start/end: {b0['powered']}/{b1['powered']}); screen state unchanged; no root.",
          f"- Load: `cabin_edge` batch run, {n} utterances speech→speech (6 directions), {t_load:.0f} s wall, engine rc={r.returncode}.", "",
          "| phase | duration s | avg current mA | avg voltage V | avg power W | charge used mAh | temp °C start→end |",
          "|---|---|---|---|---|---|---|"]
    for name, s in (("idle (baseline)", idle), ("load (pipeline running)", load)):
        if s:
            md.append(f"| {name} | {s['duration_s']} | {s['avg_current_ma']} | {s['avg_voltage_v']} | {s['avg_power_w']} | "
                      f"{s['charge_used_mah']} | {s['temp_c_start_end'][0]} → {s['temp_c_start_end'][1]} |")
    if "pipeline_power_w" in res:
        md += ["", f"- **Pipeline power (load − idle): {res['pipeline_power_w']} W**",
               f"- **Energy per utterance (pipeline only): {res['energy_per_utterance_j']} J**; including baseline "
               f"(screen/OS): {res['total_energy_per_utterance_j']} J"]
    (out / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print("written", out)


if __name__ == "__main__":
    main()
