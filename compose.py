#!/usr/bin/env python3
"""1080p title pass + narration mux for ES and EN."""
import json, subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path("/workspace/artifacts/documentary")
CARD = OUT / "cards"
TIMELINE = json.loads((OUT / "timeline.json").read_text())
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF_R = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
IVORY = (244, 239, 230, 255)
GOLD = (212, 168, 83, 255)
DIM = (196, 190, 178, 230)

def font(path, size):
    return ImageFont.truetype(path, size)

def text_width(draw, text, fnt, tracking):
    w = 0
    for ch in text:
        w += draw.textlength(ch, font=fnt) + tracking
    return w - tracking

def draw_tracked(draw, text, xy, fnt, fill, tracking=0, anchor="mm"):
    x, y = xy
    w = text_width(draw, text, fnt, tracking)
    if anchor[0] == "m":
        x = x - w / 2
    elif anchor[0] == "r":
        x = x - w
    # vertical: use font metrics roughly via anchor on first draw bbox
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill, anchor="lt")
        x += draw.textlength(ch, font=fnt) + tracking

def measure_h(fnt):
    return fnt.getbbox("Ay")[3] - fnt.getbbox("Ay")[1]

def new():
    return Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))

def rule(draw, cx, y, w, color=GOLD):
    draw.rectangle([cx - w / 2, y, cx + w / 2, y + 2], fill=color)

def save(im, name):
    CARD.mkdir(parents=True, exist_ok=True)
    path = CARD / name
    im.save(path)
    return path

def card_kicker(text):
    im = new()
    d = ImageDraw.Draw(im)
    f = font(SANS_B, 28)
    draw_tracked(d, text, (960, 860), f, GOLD, tracking=8)
    return im

def card_title(kicker, line1, line2):
    im = new()
    d = ImageDraw.Draw(im)
    draw_tracked(d, kicker, (960, 400), font(SANS_B, 26), GOLD, tracking=10)
    rule(d, 960, 448, 180)
    draw_tracked(d, line1, (960, 500), font(SERIF, 72), IVORY, tracking=2)
    draw_tracked(d, line2, (960, 590), font(SERIF, 64), IVORY, tracking=3)
    return im

def card_chapter(num, title):
    im = new()
    d = ImageDraw.Draw(im)
    draw_tracked(d, f"{num:02d}", (960, 430), font(SANS_B, 28), GOLD, tracking=8)
    rule(d, 960, 478, 120)
    # wrap long titles
    f = font(SERIF, 68 if len(title) < 28 else 54)
    draw_tracked(d, title.upper(), (960, 520), f, IVORY, tracking=1)
    return im

def card_lower(num, title, total=10):
    im = new()
    d = ImageDraw.Draw(im)
    d.rectangle([90, 900, 94, 990], fill=GOLD)
    draw_tracked(d, f"{num:02d}", (120, 910), font(SERIF, 36), GOLD, tracking=0, anchor="lt")
    draw_tracked(d, title, (200, 918), font(SERIF_R, 32), IVORY, tracking=0, anchor="lt")
    draw_tracked(d, f"{num:02d}  /  {total:02d}", (1740, 80), font(SANS, 24), DIM, tracking=2, anchor="rt")
    return im

def card_label(text, x, y, size=32):
    im = new()
    d = ImageDraw.Draw(im)
    draw_tracked(d, text, (x, y), font(SANS_B, size), GOLD, tracking=3, anchor="mt")
    return im

def card_note(text, x, y, size=34):
    im = new()
    d = ImageDraw.Draw(im)
    draw_tracked(d, text, (x, y), font(SERIF, size), IVORY, tracking=0, anchor="lt")
    return im

def card_end(line1, line2, line3):
    im = new()
    d = ImageDraw.Draw(im)
    draw_tracked(d, line1, (960, 430), font(SANS_B, 26), GOLD, tracking=8)
    rule(d, 960, 478, 160)
    draw_tracked(d, line2, (960, 530), font(SERIF, 52), IVORY, tracking=1)
    draw_tracked(d, line3, (960, 600), font(SERIF, 48), IVORY, tracking=1)
    return im

COPY = {
    "es": {
        "kicker": "AHORA MISMO, EN ALGÚN LUGAR",
        "doc": "UN DOCUMENTAL",
        "t1": "DIEZ COSAS QUE NO SABÍAS",
        "t2": "DE LOS AGUJEROS NEGROS",
        "chapters": [
            "No son agujeros",
            "El horizonte no se siente",
            "El estiramiento depende del tamaño",
            "Dos relojes, dos verdades",
            "Brillan más que una galaxia",
            "Ya los fotografiamos",
            "Uno en el centro de tu cielo",
            "Nacieron de todas las formas",
            "Se evaporan",
            "La película se equivocaba",
        ],
        "end": ("EL BORDE NO ES EL FINAL", "Diez cosas que no sabías", "de los agujeros negros"),
        "panels": {
            "03": (("ESTELAR", 480, 150), ("SUPERMASIVO", 1440, 150)),
            "04": (("LEJOS", 520, 180), ("EN EL BORDE", 1420, 180)),
            "10": (("SUSPENDIDO", 480, 150), ("CAÍDA LIBRE", 1440, 150)),
        },
    },
    "en": {
        "kicker": "SOMEWHERE, RIGHT NOW",
        "doc": "A DOCUMENTARY",
        "t1": "TEN THINGS YOU DIDN'T KNOW",
        "t2": "ABOUT BLACK HOLES",
        "chapters": [
            "They are not holes",
            "You would not feel the horizon",
            "Stretching depends on size",
            "Two clocks, two truths",
            "They can outshine a galaxy",
            "We have photographed them",
            "One at the center of your sky",
            "Born in every way",
            "They evaporate",
            "The movie got it wrong",
        ],
        "end": ("THE EDGE IS NOT THE END", "Ten things you didn't know", "about black holes"),
        "panels": {
            "03": (("STELLAR", 480, 150), ("SUPERMASSIVE", 1440, 150)),
            "04": (("FAR AWAY", 520, 180), ("AT THE EDGE", 1420, 180)),
            "10": (("HOVERING", 480, 150), ("FREE FALL", 1440, 150)),
        },
    },
}

SHARED_NOTES = [
    # id, text, x, y, size, start_frac of the segment after pre, end before post
]

def seg(sid):
    return next(s for s in TIMELINE["segments"] if s["id"] == sid)

def build_cards(lang):
    c = COPY[lang]
    paths = []  # (path, t0, t1, fadein, fadeout)
    k = save(card_kicker(c["kicker"]), f"{lang}_kicker.png")
    paths.append((k, 3.0, 9.2, 0.6, 0.9))
    title = seg("title")
    tcard = save(card_title(c["doc"], c["t1"], c["t2"]), f"{lang}_title.png")
    paths.append((tcard, title["start"] + 1.2, title["end"] - 1.3, 1.1, 1.2))
    for i, name in enumerate(c["chapters"], start=1):
        s = seg(f"{i:02d}")
        big = save(card_chapter(i, name), f"{lang}_ch{i:02d}.png")
        paths.append((big, s["start"] + 0.35, s["start"] + s["pre"] + 0.8, 0.45, 0.55))
        low = save(card_lower(i, name), f"{lang}_low{i:02d}.png")
        paths.append((low, s["start"] + s["pre"] + 0.2, s["end"] - 0.35, 0.4, 0.35))
    for sid, pair in c["panels"].items():
        s = seg(sid)
        for j, (text, x, y) in enumerate(pair):
            p = save(card_label(text, x, y), f"{lang}_{sid}_{j}.png")
            paths.append((p, s["start"] + 1.0, s["end"] - 0.6, 0.4, 0.4))
    # shared science labels
    s1 = seg("01")
    p = save(card_note("R☉   =   2.95 km", 140, 640, 40), f"{lang}_r_sun.png")
    paths.append((p, s1["start"] + s1["pre"] + 12, s1["end"] - s1["post"], 0.4, 0.4))
    p = save(card_note("R⊕   =   8.9 mm", 140, 710, 40), f"{lang}_r_earth.png")
    paths.append((p, s1["start"] + s1["pre"] + 16, s1["end"] - s1["post"], 0.4, 0.4))
    s5 = seg("05")
    p = save(card_note("10⁶  –  10⁷ K", 140, 160, 36), f"{lang}_temp.png")
    paths.append((p, s5["start"] + 6, s5["end"] - 4, 0.4, 0.4))
    s6 = seg("06")
    mid = s6["start"] + (s6["end"] - s6["start"]) * 0.48
    p = save(card_label("M87*     2019", 960, 150, 36), f"{lang}_m87.png")
    paths.append((p, s6["start"] + 2.0, mid, 0.4, 0.3))
    p = save(card_label("Sgr A*     2022", 960, 150, 36), f"{lang}_sgr.png")
    paths.append((p, mid + 0.4, s6["end"] - 1.5, 0.3, 0.4))
    s7 = seg("07")
    p = save(card_label("4.3 × 10⁶ M☉", 960, 120, 34), f"{lang}_mass.png")
    paths.append((p, s7["start"] + 3, s7["end"] - 3, 0.4, 0.4))
    p = save(card_label("S2", 1280, 430, 28), f"{lang}_s2.png")
    paths.append((p, s7["start"] + 8, s7["end"] - 3, 0.3, 0.3))
    s9 = seg("09")
    p = save(card_note("T   ∝   1 / M", 140, 180, 40), f"{lang}_hawking.png")
    paths.append((p, s9["start"] + 6, s9["end"] - 6, 0.4, 0.4))
    end = c["end"]
    ec = save(card_end(*end), f"{lang}_end.png")
    cl = seg("11_close")
    paths.append((ec, cl["start"] + cl["pre"] + cl["vo"] * 0.72, cl["end"] - 0.4, 1.0, 0.6))
    return paths

def run(lang):
    import numpy as np
    cards_meta = build_cards(lang)
    cards = []
    for path, t0, t1, fi, fo in cards_meta:
        arr = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32) / 255.0
        cards.append((arr, t0, t1, fi, fo))
    base = OUT / "base.mp4"
    mix = OUT / f"mix_{lang}.wav"
    text = OUT / f"text_{lang}.mov"
    final = {
        "es": OUT / "Diez_cosas_que_no_sabias_de_los_agujeros_negros_ES.mp4",
        "en": OUT / "Ten_Things_You_Didnt_Know_About_Black_Holes_EN.mp4",
    }[lang]
    n = int(round(TIMELINE["duration"] * 24))
    enc = subprocess.Popen([
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgba", "-s", "1920x1080",
        "-r", "24", "-i", "-", "-an", "-c:v", "qtrle", str(text),
    ], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("text track", lang, flush=True)
    for i in range(0, n, 2):
        t = i / 24.0
        rgb = np.zeros((1080, 1920, 3), np.float32)
        a = np.zeros((1080, 1920, 1), np.float32)
        for arr, t0, t1, fi, fo in cards:
            if t < t0 or t > t1:
                continue
            g = 1.0
            if t < t0 + fi:
                g = (t - t0) / max(fi, 1e-3)
            elif t > t1 - fo:
                g = (t1 - t) / max(fo, 1e-3)
            if g <= 0:
                continue
            sa = arr[:, :, 3:4] * g
            rgb = arr[:, :, :3] * sa + rgb * (1 - sa)
            a = sa + a * (1 - sa)
        frame = np.clip(np.concatenate([rgb, a], axis=2) * 255.0, 0, 255).astype(np.uint8)
        raw = frame.tobytes()
        enc.stdin.write(raw)
        if i + 1 < n:
            enc.stdin.write(raw)
        if i % 480 == 0:
            print(f"  text {lang} {i}/{n}", flush=True)
    enc.stdin.close()
    if enc.wait() != 0:
        raise RuntimeError("text encode failed")
    print("mux", lang, flush=True)
    r = subprocess.run([
        "ffmpeg", "-y", "-i", str(base), "-i", str(text), "-i", str(mix),
        "-filter_complex",
        "[0:v]scale=1920:1080:flags=lanczos[b];[b][1:v]overlay=0:0:format=auto,format=yuv420p[v];[2:a]loudnorm=I=-16:TP=-1.5:LRA=11[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", str(final),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2500:])
    print("done", final, flush=True)

if __name__ == "__main__":
    import sys
    langs = sys.argv[1:] or ["es", "en"]
    for lang in langs:
        run(lang)
