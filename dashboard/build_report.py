"""Build the results index: results/README.md + dashboard/index.html (offline, self-contained).

python dashboard/build_report.py
Picks the latest complete (6-direction) on-device run and PC run as "official"; every other run is
listed as superseded or archived (results/archive/). Re-run after any new benchmark.
"""
import datetime as dt
import glob
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
R = ROOT / "results"
DASH = ROOT / "dashboard"
PAIRS = ["vi-en", "en-vi", "vi-ko", "ko-vi", "vi-zh", "zh-vi"]
VQ_MODEL_MB = {"gemma-4-E2B-it.litertlm": 2468, "gemma-4-E2B-it-gpu.litertlm": 2232,
               "gemma-4-E2B-it_Qualcomm_QCS8275.litertlm": 2596}   # MiB on disk
LABEL = {"vi-en": "VI→EN", "en-vi": "EN→VI", "vi-ko": "VI→KO", "ko-vi": "KO→VI", "vi-zh": "VI→ZH", "zh-vi": "ZH→VI"}


def jload(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None


def run_time(name):
    m = re.search(r"(\d{8})_(\d{6})", name)
    return dt.datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S") if m else None


def latest_complete(pattern):
    best = None
    for d in sorted(glob.glob(str(R / pattern))):
        s = jload(Path(d) / "summary.json")
        if s and all(p in s.get("pairs", {}) for p in PAIRS):
            best = Path(d)
    return best


def load_linux(tag):
    """Latest complete run per LLM backend under results/<tag>/<tag>_<backend>_*."""
    out = {"backends": {}, "rows": []}
    for b in ("cpu", "gpu", "npu"):
        dd = latest_complete(f"{tag}/{tag}_{b}_*")
        if not dd:
            continue
        sm = jload(dd / "summary.json")
        ds_ = sm.get("device_summary", {})
        mp = sm.get("meminfo_peak_kb", {})
        out["backends"][b] = {
            "run": dd.name, "model": Path(ds_.get("mt_model", "")).name, "model_mb": VQ_MODEL_MB.get(Path(ds_.get("mt_model", "")).name),
            "peak_rss_mb": round(ds_.get("peak_rss_kb", 0) / 1024), "gpu_mb": round(mp.get("graphics", 0) / 1024),
            "net_conns": mp.get("net_conns"), "threads": ds_.get("mt_num_threads"),
            "load_mt_ms": round(ds_.get("load_ms", {}).get("mt", 0)), "prefix_cache": ds_.get("mt_prefix_cache"),
            "ctx": ds_.get("mt_max_num_tokens"), "sampler": ds_.get("mt_sampler"),
            "network_start": sm["device"].get("internet"), "network_end": sm.get("device_end", {}).get("internet"),
            "device": sm["device"]}
        for p in PAIRS:
            e = sm["pairs"][p]
            out["rows"].append({"backend": b, "pair": p, "label": LABEL[p], "n": e["n"],
                                "asr_kind": "CER" if "asr_cer" in e else "WER", "asr_err": e.get("asr_cer", e.get("asr_wer")),
                                "bleu": e["bleu"], "chrf": e["chrf++"], "comet": e.get("comet"), "asr_bleu": e["asr_bleu_speech_out"],
                                "asr_ms": e["asr_ms_mean"], "punct_ms": e["punct_ms_mean"], "mt_ms": e["mt_ms_mean"],
                                "tts_ms": e["tts_ms_mean"], "p50": e["total_ms_p50"], "p95": e["total_ms_p95"],
                                "ttft": e.get("mt_ttft_ms_mean"), "dec_tps": e.get("mt_decode_tps_mean")})
    return out


def main():
    edge_dir = latest_complete("qcs8550/device_bench_*")
    pc_dir = latest_complete("pc/bench_*")
    edge = jload(edge_dir / "summary.json")
    pc = jload(pc_dir / "summary.json")
    edge_prev_dir = max((Path(d) for d in glob.glob(str(R / "qcs8550/device_bench_*")) if Path(d) != edge_dir
                         and jload(Path(d) / "summary.json")), key=lambda p: p.name, default=None)
    edge_prev = jload(edge_prev_dir / "summary.json") if edge_prev_dir else None

    # ---------------- official tables
    edge_rows, pc_rows = [], []
    for p in PAIRS:
        e, c = edge["pairs"][p], pc["pairs"][p]
        cjk = "asr_cer" in e
        edge_rows.append({
            "pair": p, "label": LABEL[p], "n": e["n"], "asr_kind": "CER" if cjk else "WER",
            "asr_err": e.get("asr_cer", e.get("asr_wer")), "bleu": e["bleu"], "chrf": e["chrf++"], "comet": e.get("comet"),
            "asr_bleu": e["asr_bleu_speech_out"], "asr_ms": e["asr_ms_mean"], "punct_ms": e["punct_ms_mean"],
            "mt_ms": e["mt_ms_mean"], "tts_ms": e["tts_ms_mean"], "p50": e["total_ms_p50"], "p95": e["total_ms_p95"],
            "ttft": e.get("mt_ttft_ms_mean"), "dec_tps": e.get("mt_decode_tps_mean"), "audio_s": e.get("audio_s_mean"),
            "prev_p50": (edge_prev or {}).get("pairs", {}).get(p, {}).get("total_ms_p50"),
            "prev_tts": (edge_prev or {}).get("pairs", {}).get(p, {}).get("tts_ms_mean")})
        pc_rows.append({"pair": p, "label": LABEL[p], "n": c["n"], "asr_err": c.get("asr_cer", c.get("asr_wer")),
                        "bleu": c["bleu"], "chrf": c["chrf++"], "comet": c.get("comet"), "asr_bleu": c["asr_bleu_speech_out"],
                        "p50": round(c["total_s_p50"] * 1000), "p95": round(c["total_s_p95"] * 1000),
                        "asr_ms": round(c["asr_s_mean"] * 1000), "mt_ms": round(c["mt_s_mean"] * 1000),
                        "tts_ms": round(c["tts_s_mean"] * 1000)})
    ds = edge.get("device_summary", {})
    resources = {
        "device": edge["device"], "network_start": edge["device"].get("internet"),
        "network_end": edge.get("device_end", {}).get("internet"),
        "peak_rss_mb": round(ds.get("peak_rss_kb", 0) / 1024), "graphics_mb": round(edge.get("meminfo_peak_kb", {}).get("graphics", 0) / 1024),
        "load_ms": {k: round(v) for k, v in ds.get("load_ms", {}).items()}, "mt_max_tokens": ds.get("mt_max_num_tokens"),
        "pc_models_mb": pc.get("model_sizes_mb"), "pc_env": pc.get("env"), "pc_peak_ram_mb": pc.get("peak_ram_mb"),
        "pc_peak_vram_mb": pc.get("peak_vram_mb")}

    # ---------------- Linux boards (same engine): VENTUNO Q (QCS8275) and IQ-9075 (QCS9075); ASR+TTS on CPU
    vq = load_linux("ventunoq")
    iq = load_linux("iq9075")
    s25 = load_linux("s25ultra")   # Galaxy S25 Ultra (SM8750, Android), Gemma on the Adreno 830 GPU

    # ---------------- component studies
    asr_c = []
    for f in glob.glob(str(R / "components/asr/asr_en-vi_*.json")):
        s = (jload(f) or {}).get("summary", {})
        if "size_mb" in s:
            asr_c.append({"model": s["model"].replace("auto:", "").replace("sherpa-onnx-", ""), "size_mb": s["size_mb"],
                          "wer": s["wer"], "lat": s["lat_mean_s"] * 1000})
    downstream = {}
    for key, f in {"x-asr-zipformer-transducer-zh-en-punct-int8-2026-06-03": "mt_en-vi_asr_xasr_llama",
                   "zipformer-gigaspeech-2023-12-12": "mt_en-vi_asr_gigaspeech_llama",
                   "nemo-parakeet_tdt_transducer_110m-en-36000-int8": "mt_en-vi_asr_p110_llama",
                   "parakeet-0.6b": "mt_en-vi_asr_en-parakeet_llama"}.items():
        s = (jload(R / f"components/mt/{f}.json") or {}).get("summary", {})
        if "comet" in s:
            downstream[key] = s["comet"]
    for a in asr_c:
        a["mt_comet"] = downstream.get(a["model"])
    asr_c.sort(key=lambda a: a["wer"])

    quant = []
    for tag, name in [("q4gpu", "Gemma QAT Q4_0 (3.35 GB)"), ("Q3_K_M", "Gemma Q3_K_M (2.54 GB)"),
                      ("qat-UD-Q2_K_XL", "Gemma QAT-mobile Q2_K_XL (2.19 GB)")]:
        for p in ["vi-en", "en-vi"]:
            for inp, asr in [("gold", None), ("asr", {"vi-en": "vi-30m", "en-vi": "en-parakeet"}[p])]:
                f = R / f"components/mt/mt_{p}_{inp}{'_' + asr if asr else ''}_llama_{tag}.json"
                s = (jload(f) or {}).get("summary", {})
                if s:
                    quant.append({"model": name, "pair": LABEL[p], "input": "transcript" if inp == "gold" else "ASR",
                                  "bleu": s.get("bleu"), "comet": s.get("comet")})
    ablation = jload(R / "components/mt/prompt_ablation.json") or []
    tts_dir = max(glob.glob(str(R / "qcs8550/device_tts_*")), default=None)
    tts_c = jload(Path(tts_dir) / "summary.json") if tts_dir else []
    pc_asr = []
    for f, label in [("asr_vi-en_vi-30m", "VI Zipformer-30M"), ("asr_vi-en_vi-150m", "VI Zipformer-150M"),
                     ("asr_ko-vi_ko-zipformer", "KO Zipformer"), ("asr_zh-vi_xasr-zh-en", "ZH X-ASR"),
                     ("asr_ko-vi_sensevoice", "KO SenseVoice (broken in sherpa 2.0.1)")]:
        s = (jload(R / f"components/asr/{f}.json") or {}).get("summary", {})
        if s:
            cjk = label.startswith(("KO", "ZH"))  # KO/ZH outputs have no word spacing -> WER is meaningless, use CER
            pc_asr.append({"model": label, "wer": None if cjk else s.get("wer"), "cer": s.get("cer"), "rtf": s.get("rtf")})

    # ---------------- samples: one row per utterance, outputs of every official device run side by side
    sample_runs = [("qcs8550", "QCS8550 GPU", edge_dir)] + [
        (f"vq_{b}", f"VentunoQ {b.upper()}", R / "ventunoq" / vq["backends"][b]["run"])
        for b in ("npu", "gpu", "cpu") if b in vq["backends"]] + [
        (f"iq_{b}", f"IQ-9075 {b.upper()}", R / "iq9075" / iq["backends"][b]["run"])
        for b in ("npu", "gpu", "cpu") if b in iq["backends"]] + [
        (f"s25_{b}", f"S25 Ultra {b.upper()}", R / "s25ultra" / s25["backends"][b]["run"])
        for b in ("gpu",) if b in s25["backends"]]
    by_id = {}
    for key, label, rd in sample_runs:
        rel_run = rd.relative_to(R)
        for line in (rd / "rows.jsonl").read_text().splitlines():
            r = json.loads(line)
            sid = r["id"].split("__")[1]
            row = by_id.get(r["id"])
            if row is None:
                src_wav = rd / "stage" / r["pair"] / f"{sid}.wav"   # the exact 16 kHz input pushed to the device
                row = by_id[r["id"]] = {"id": r["id"], "pair": r["pair"], "src_ref": r.get("src_ref"), "ref": r.get("ref"),
                                        "src_wav": f"../results/{rel_run}/stage/{r['pair']}/{sid}.wav" if src_wav.exists() else None,
                                        "outs": {}}
            row["outs"][key] = ({k: r.get(k) for k in ["asr", "mt_in", "hyp", "back_asr"]} |
                                {k: round(r.get(k, 0) or 0) for k in ["asr_ms", "punct_ms", "mt_ms", "tts_ms", "total_ms"]} |
                                {"wav": f"../results/{rel_run}/wav/{r['id']}.wav" if (rd / "wav" / f"{r['id']}.wav").exists() else None})
    samples = list(by_id.values())

    # ---------------- run history
    history = []
    for d in sorted(glob.glob(str(R / "qcs8550/*")) + glob.glob(str(R / "ventunoq/*")) + glob.glob(str(R / "iq9075/*")) + glob.glob(str(R / "s25ultra/*")) + glob.glob(str(R / "pc/*")) + glob.glob(str(R / "archive/*"))):
        d = Path(d)
        s = jload(d / "summary.json")
        kind = ("ventunoq-" + d.name.split("_")[1] if d.name.startswith("ventunoq_") else
                "iq9075-" + d.name.split("_")[1] if d.name.startswith("iq9075_") else
                "s25ultra-" + d.name.split("_")[1] if d.name.startswith("s25ultra_") else
                "qcs8550" if d.name.startswith("device_bench") else "qcs8550-tts" if d.name.startswith("device_tts") else "pc")
        vq_runs = {v["run"] for v in vq["backends"].values()} | {v["run"] for v in iq["backends"].values()} | {v["run"] for v in s25["backends"].values()}
        status = ("official" if d in (edge_dir, pc_dir) or (tts_dir and d == Path(tts_dir)) or
                  (d.parent.name in ("ventunoq", "iq9075", "s25ultra") and d.name in vq_runs)
                  else "archived" if d.parent.name == "archive" else "superseded")
        pairs = list((s or {}).get("pairs", {}).keys()) if isinstance(s, dict) else []
        note = d.name.split("__")[1].replace("_", " ") if "__" in d.name else ""
        if d.name.startswith("device_tts"):
            pairs = ["en", "ko"] if s else []
        history.append({"run": d.name, "path": str(d.relative_to(R)), "kind": kind, "status": status,
                        "time": (run_time(d.name) or dt.datetime.min).strftime("%Y-%m-%d %H:%M"), "pairs": pairs,
                        "has_summary": (d / "summary.md").exists(), "note": note})
    history.sort(key=lambda h: h["time"], reverse=True)

    data = {"generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "edge_run": edge_dir.name, "pc_run": pc_dir.name,
            "edge_prev_run": edge_prev_dir.name if edge_prev_dir else None,
            "edge": edge_rows, "pc": pc_rows, "resources": resources, "asr_candidates": asr_c, "quant": quant,
            "ablation": ablation, "tts_candidates": tts_c, "pc_asr": pc_asr, "samples": samples,
            "sample_runs": [{"key": k, "label": lb, "run": rd.name} for k, lb, rd in sample_runs], "history": history,
            "ventunoq": vq, "iq9075": iq, "s25ultra": s25}
    DASH.mkdir(exist_ok=True)
    tpl = (DASH / "report_template.html").read_text()
    (DASH / "index.html").write_text(tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False)))
    (DASH / "data.json").write_text(json.dumps(data, ensure_ascii=False))  # used by export_dashboard_artifact.py
    write_readme(data)
    print("wrote dashboard/index.html and results/README.md  (edge:", edge_dir.name, " pc:", pc_dir.name, ")")


def write_readme(d):
    e, p, res = d["edge"], d["pc"], d["resources"]
    L = ["# Results — CabinTranslation", "",
         f"_Generated {d['generated']} by `python dashboard/build_report.py`. "
         "Open the dashboard with `bash dashboard/serve.sh` (http://localhost:8000/dashboard/) for charts, per-utterance browsing and audio._", "",
         "## Layout", "", "```",
         "results/",
         "  README.md              this index (generated)",
         "  (dashboard: ../dashboard/index.html, generated)",
         "  qcs8550/               on-device runs, QCS8550 tablet (Android, Gemma on GPU): device_bench_* (end-to-end), device_tts_* (TTS candidates)",
         "  ventunoq/              on-device runs, Arduino VENTUNO Q / QCS8275 (Linux, Gemma on CPU/GPU/NPU): ventunoq_<backend>_*",
         "  iq9075/                on-device runs, Qualcomm IQ-9075 EVK / QCS9075 (Qualcomm Linux, Gemma on CPU/GPU): iq9075_<backend>_*",
         "  s25ultra/              on-device runs, Samsung Galaxy S25 Ultra / SM8750 (Android, Gemma on GPU): s25ultra_gpu_*",
         "  pc/                    PC reference runs (RTX 4080): bench_* (end-to-end)",
         "  components/asr|mt|tts/ component evaluations and model comparisons",
         "  archive/               smoke tests, crashed or failed runs (kept for traceability)", "```", "",
         f"## Official on-device results — Qualcomm QCS8550 (`qcs8550/{d['edge_run']}`)", "",
         f"- Device: {res['device'].get('ro.soc.model')} / {res['device'].get('ro.product.model')}, Android "
         f"{res['device'].get('ro.build.version.release')}, Adreno 740.",
         f"- Runtime: Gemma 4 E2B on the GPU via LiteRT-LM (context {res['mt_max_tokens']}); ASR and TTS on the CPU.",
         f"- Peak RSS: {res['peak_rss_mb']} MB (all 4 languages loaded). GPU (Graphics): {res['graphics_mb']} MB.",
         f"- Network: {res['network_start']} at start, {res['network_end']} at end. "
         "**Re-run offline for the submission.**", "",
         "| pair | n | ASR err | BLEU | chrF++ | COMET | ASR-BLEU | ASR ms | punct ms | MT ms | TTS ms | total p50 / p95 ms |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in e:
        L.append(f"| {r['label']} | {r['n']} | {r['asr_kind']} {r['asr_err']} | {r['bleu']} | {r['chrf']} | {r['comet']} | "
                 f"{r['asr_bleu']} | {r['asr_ms']:.0f} | {r['punct_ms']:.0f} | {r['mt_ms']:.0f} | {r['tts_ms']:.0f} | "
                 f"{r['p50']:.0f} / {r['p95']:.0f} |")
    L += ["", "BLEU for KO/ZH targets is character-level. ASR-BLEU is BLEU of the spoken output after re-recognition.", ""]
    for key, title, det in [("ventunoq", "Arduino VENTUNO Q — QCS8275, Ubuntu 24.04", "edge/ventunoq-linux/README.md"),
                            ("iq9075", "Qualcomm IQ-9075 EVK — QCS9075, Qualcomm Linux 1.9", "edge/ventunoq-linux/README.md (same Linux build)"),
                            ("s25ultra", "Samsung Galaxy S25 Ultra — SM8750, Android 17 (latency run, COMET not computed)", "edge/qcs8550-android/README.md (same Android build)")]:
        vq = d.get(key, {})
        if not vq.get("rows"):
            continue
        B = [b for b in ("cpu", "gpu", "npu") if b in vq["backends"]]
        by = {(r["backend"], r["pair"]): r for r in vq["rows"]}
        L += [f"## {title} (`{key}/`)", "",
              "Same native pipeline; only the Gemma backend differs (ASR/TTS on CPU). VI input = 1 Gemma call. "
              "Runs: " + ", ".join(f"{b.upper()} `{vq['backends'][b]['run']}`" for b in B) + f". Details: `{det}`.", "",
              "| pair | " + " | ".join(f"COMET {b}" for b in B) + " | " + " | ".join(f"BLEU {b}" for b in B) + " | "
              + " | ".join(f"p50 {b} ms" for b in B) + " |", "|---" * (1 + 3 * len(B)) + "|"]
        for pr in PAIRS:
            L.append(f"| {LABEL[pr]} | " + " | ".join(str(by[(b, pr)]["comet"]) for b in B) + " | "
                     + " | ".join(str(by[(b, pr)]["bleu"]) for b in B) + " | "
                     + " | ".join(f"{by[(b, pr)]['p50']:.0f}" for b in B) + " |")
        L += ["", "| backend | Gemma file | decode tok/s | TTFT ms | peak RSS MB | GPU MB | engine net sockets (max) |", "|---|---|---|---|---|---|---|"]
        for b in B:
            v = vq["backends"][b]
            rs = [r for r in vq["rows"] if r["backend"] == b]
            L.append(f"| {b.upper()} | {v['model']} ({v['model_mb']} MB) | {sum(r['dec_tps'] for r in rs) / len(rs):.1f} | "
                     f"{sum(r['ttft'] for r in rs) / len(rs):.0f} | {v['peak_rss_mb']} | {v['gpu_mb']} | "
                     f"{'n/a' if v.get('net_conns') is None else v['net_conns']} |")
        L += ["", f"Network during these runs: {vq['backends'][B[0]]['network_start']}.", ""]
    L += [
          f"## PC reference — RTX 4080 (`pc/{d['pc_run']}`)", "",
          "| pair | ASR err | BLEU | chrF++ | COMET | total p50 / p95 ms |", "|---|---|---|---|---|---|"]
    for r in p:
        L.append(f"| {r['label']} | {r['asr_err']} | {r['bleu']} | {r['chrf']} | {r['comet']} | {r['p50']} / {r['p95']} |")
    L += ["", "## Runs", "", "| time | run | kind | status | pairs | note |", "|---|---|---|---|---|---|"]
    for h in d["history"]:
        link = f"[{h['run']}]({h['path']}/summary.md)" if h["has_summary"] else h["run"]
        L.append(f"| {h['time']} | {link} | {h['kind']} | {h['status']} | {', '.join(h['pairs'])} | {h['note']} |")
    L += ["", "## Component studies", "",
          "- `components/asr/en_asr_candidates_t2.md`: 26 English ASR models compared on WER, size and latency.",
          "- `components/mt/scoreboard.md`: every MT run with BLEU, chrF++ and COMET (Gemma quants, prompts, ASR inputs).",
          "- `components/mt/prompt_ablation.json`: system-prompt variants.",
          "- `components/tts/`: round-trip intelligibility on PC.",
          f"- `qcs8550/{Path(max(glob.glob(str(R / 'qcs8550/device_tts_*')))).name}/summary.md`: "
          "on-device TTS candidates against the 500 ms quota."]
    (R / "README.md").write_text("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
