"""CabinTranslation — offline two-way voice interpreter (Gradio UI).

python pc/app.py [--partner en] [--port 7860]   (run from the repo root, or bash pc/run.sh)
Open http://127.0.0.1:7860 . Everything runs locally; no network needed.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)  # models/ and data/ are addressed relative to the repo root

import os

os.environ.setdefault("GRADIO_ANALYTICS_ENABLED", "False")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import argparse  # noqa: E402
import socket  # noqa: E402

import gradio as gr  # noqa: E402
import numpy as np  # noqa: E402

from cabin.pipeline import VoiceTranslator  # noqa: E402

FLAG = {"vi": "🇻🇳 Tiếng Việt", "en": "🇬🇧 English", "zh": "🇨🇳 中文", "ko": "🇰🇷 한국어"}
PARTNERS = {"🇬🇧 English": "en", "🇰🇷 한국어": "ko", "🇨🇳 中文": "zh"}
SPEAK = {"en": "Press the mic and speak English", "ko": "마이크를 누르고 한국어로 말하세요", "zh": "按下麦克风说中文"}
GO = {"en": "Translate to Vietnamese ▶", "ko": "베트남어로 번역 ▶", "zh": "翻译成越南语 ▶"}


def online() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1).close()
        return True
    except OSError:
        return False


def to_mono_f32(audio):
    if isinstance(audio, str):  # filepath: decode with libsndfile (wav/mp3/flac/ogg, no ffmpeg needed)
        import soundfile as sf
        x, sr = sf.read(audio, dtype="float32", always_2d=True)
        return sr, x.mean(axis=1)
    sr, x = audio
    x = np.asarray(x)
    if x.dtype.kind == "i":
        x = x.astype(np.float32) / np.iinfo(x.dtype).max
    x = x.astype(np.float32)
    if x.ndim == 2:
        x = x.mean(axis=1)
    return sr, x


CSS = """
.bigbtn button, button.bigbtn {font-size: 1.25rem !important; min-height: 60px}
.turn-vi {background: #e8f1ff; color: #10243e; border-radius: 12px; padding: 8px 12px; margin: 6px 0}
.turn-xx {background: #e9f9ee; color: #10301a; border-radius: 12px; padding: 8px 12px; margin: 6px 0}
footer {display: none !important}
"""


def build_ui(vt: VoiceTranslator, partner0: str):
    def render(history):
        rows = []
        for h in reversed(history[-30:]):
            cls = "turn-vi" if h["src"] == "vi" else "turn-xx"
            rows.append(f"<div class='{cls}'><b>{FLAG[h['src']]}</b>: {h['asr'] or '…'}<br>"
                        f"➜ <b>{FLAG[h['tgt']]}</b>: <span style='font-size:1.15em'>{h['tr']}</span>"
                        f"<br><small>⏱ {h['t']['total_s']}s</small></div>")
        return "".join(rows) or "<i>Chưa có hội thoại — bấm micro và nói. / Press the mic and speak.</i>"

    def run(audio, src, tgt, history):
        if audio is None:
            return gr.update(), history, render(history), "⚠️ Chưa có âm thanh / No audio"
        sr, x = to_mono_f32(audio)
        if len(x) < sr * 0.3:
            return gr.update(), history, render(history), "⚠️ Đoạn ghi quá ngắn / Too short"
        turn = vt(x, src, tgt, sr=sr)
        t = turn.timings
        history = history + [{"src": src, "tgt": tgt, "asr": turn.mt_input or turn.asr_text, "tr": turn.translation, "t": t}]
        stat = (f"⏱ ASR {t['asr_s']}s · Dịch/MT {t['mt_s']}s · TTS {t.get('tts_s', 0)}s · "
                f"**Tổng {t['total_s']}s** (audio {t['audio_s']}s) · LLM: {vt.mt.device.upper()} · "
                f"{'🌐 ONLINE' if online() else '✈️ OFFLINE'}")
        out_audio = (turn.sample_rate, turn.audio) if turn.audio.size else None
        return out_audio, history, render(history), stat

    def text_translate(text, direction, partner_label):
        p = PARTNERS[partner_label]
        src, tgt = ("vi", p) if direction == "vi→" else (p, "vi")
        if not text.strip():
            return "", None
        vt.ensure_lang(tgt)
        tr = vt.translate_text(text, src, tgt)
        wav, sr = vt.tts[tgt].synthesize(tr)
        return tr, (sr, wav)

    def switch_partner(label):
        p = PARTNERS[label]
        vt.ensure_lang(p)
        return (gr.update(label=SPEAK[p]), gr.update(value=GO[p]), f"### {label}",
                gr.update(value=f"Dịch sang {label} ▶"))

    theme = gr.themes.Soft(font=["system-ui", "sans-serif"], font_mono=["monospace"])
    with gr.Blocks(title="CabinTranslation — Offline Interpreter") as demo:
        gr.Markdown("## 🎧 CabinTranslation · Phiên dịch giọng nói 2 chiều **offline**\n"
                    "Bấm micro → nói → bấm dừng: bản dịch được đọc to tự động. Toàn bộ xử lý chạy trên thiết bị "
                    "(ASR → Gemma 4 E2B → TTS), không cần Internet.")
        history = gr.State([])
        partner = gr.Radio(list(PARTNERS), value=[k for k, v in PARTNERS.items() if v == partner0][0],
                           label="Ngôn ngữ đối tác / Partner language")
        with gr.Row():
            with gr.Column():
                gr.Markdown(f"### {FLAG['vi']}")
                mic_vi = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Bấm micro và nói tiếng Việt")
                btn_vi = gr.Button(f"Dịch sang {FLAG[partner0]} ▶", variant="primary", elem_classes="bigbtn")
            with gr.Column():
                title_x = gr.Markdown(f"### {FLAG[partner0]}")
                mic_x = gr.Audio(sources=["microphone", "upload"], type="filepath", label=SPEAK[partner0])
                btn_x = gr.Button(GO[partner0], variant="primary", elem_classes="bigbtn")
        out_audio = gr.Audio(label="🔊 Bản dịch / Translation", autoplay=True, interactive=False)
        status = gr.Markdown("")
        convo = gr.HTML(render([]))
        clear = gr.Button("🗑 Xoá hội thoại / Clear")
        with gr.Accordion("⌨️ Dịch văn bản / Text mode", open=False):
            direction = gr.Radio([("Tiếng Việt → đối tác", "vi→"), ("Đối tác → Tiếng Việt", "→vi")], value="vi→",
                                 label="Chiều dịch")
            txt = gr.Textbox(label="Nhập câu", lines=2)
            txt_out = gr.Textbox(label="Bản dịch", lines=2)
            txt_audio = gr.Audio(autoplay=True, interactive=False, label="🔊")
            gr.Button("Dịch").click(text_translate, [txt, direction, partner], [txt_out, txt_audio])

        outs = [out_audio, history, convo, status]
        go_vi = lambda au, p, h: run(au, "vi", PARTNERS[p], h)  # noqa: E731
        go_x = lambda au, p, h: run(au, PARTNERS[p], "vi", h)  # noqa: E731
        btn_vi.click(go_vi, [mic_vi, partner, history], outs)
        btn_x.click(go_x, [mic_x, partner, history], outs)
        mic_vi.stop_recording(go_vi, [mic_vi, partner, history], outs)  # hands-free: translate on stop
        mic_x.stop_recording(go_x, [mic_x, partner, history], outs)
        partner.change(switch_partner, partner, [mic_x, btn_x, title_x, btn_vi])
        clear.click(lambda: ([], render([]), ""), None, [history, convo, status])
    return demo, theme


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--partner", default="en", choices=sorted(set(PARTNERS.values())))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args()
    print("Loading models (offline)…", flush=True)
    vt = VoiceTranslator(langs=("vi", a.partner))
    print(f"Ready. LLM device: {vt.mt.device}", flush=True)
    demo, theme = build_ui(vt, a.partner)
    demo.queue(default_concurrency_limit=1).launch(server_name=a.host, server_port=a.port, share=False,
                                                   css=CSS, theme=theme)


if __name__ == "__main__":
    main()
