#!/usr/bin/env python3
"""Burn language titles and mux narration. One ffmpeg pass per language."""
import json, subprocess, sys
from pathlib import Path

OUT = Path("/workspace/artifacts/documentary")
TXT = OUT / "txt"
TIMELINE = json.loads((OUT / "timeline.json").read_text())
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF_R = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
IVORY = "0xF4EFE6"
GOLD = "0xD4A853"

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
        "end1": "EL BORDE NO ES EL FINAL",
        "end2": "Diez cosas que no sabías",
        "end3": "de los agujeros negros",
        "p3": ("ESTELAR", "SUPERMASIVO"),
        "p4": ("LEJOS", "EN EL BORDE"),
        "p10": ("SUSPENDIDO", "CAÍDA LIBRE"),
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
        "end1": "THE EDGE IS NOT THE END",
        "end2": "Ten things you didn't know",
        "end3": "about black holes",
        "p3": ("STELLAR", "SUPERMASSIVE"),
        "p4": ("FAR AWAY", "AT THE EDGE"),
        "p10": ("HOVERING", "FREE FALL"),
    },
}

def seg(sid):
    return next(s for s in TIMELINE["segments"] if s["id"] == sid)

def write_text(name, text):
    TXT.mkdir(parents=True, exist_ok=True)
    p = TXT / name
    p.write_text(text + "\n", encoding="utf-8")
    return p

def ts(t):
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def line(style, t0, t1, text, x, y, align=5, size=None, fade=(500, 450)):
    tags = f"{{\\an{align}\\pos({x},{y})\\fad({fade[0]},{fade[1]})}}"
    if size:
        tags = f"{{\\an{align}\\pos({x},{y})\\fs{size}\\fad({fade[0]},{fade[1]})}}"
    return f"Dialogue: 0,{ts(t0)},{ts(t1)},{style},,0,0,0,,{tags}{text}\n"

def build_ass(lang):
    c = COPY[lang]
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Ivory,DejaVu Serif,64,&H00E6EFF4,&H000000FF,&H96000000,&H00000000,-1,0,0,0,100,100,1,0,1,2,1,5,20,20,20,1
Style: IvoryReg,DejaVu Serif,32,&H00E6EFF4,&H000000FF,&H96000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,7,20,20,20,1
Style: Gold,DejaVu Sans,28,&H0053A8D4,&H000000FF,&H96000000,&H00000000,-1,0,0,0,100,100,4,0,1,2,1,5,20,20,20,1
Style: GoldSans,DejaVu Sans,32,&H0053A8D4,&H000000FF,&H96000000,&H00000000,-1,0,0,0,100,100,2,0,1,2,0,5,20,20,20,1
Style: Symbol,DejaVu Sans,40,&H00E6EFF4,&H000000FF,&H96000000,&H00000000,0,0,0,0,100,100,0,0,1,2,1,7,20,20,20,1
Style: Dim,DejaVu Sans,24,&H00B2BEC4,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,2,0,1,0,0,9,20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    ev.append(line("Gold", 3.0, 9.2, c["kicker"], 960, 880, fade=(600, 800)))
    title = seg("title")
    a, b = title["start"] + 1.0, title["end"] - 1.1
    ev.append(line("Gold", a, b, c["doc"], 960, 430, size=26, fade=(800, 1000)))
    ev.append(line("Ivory", a + 0.3, b, c["t1"], 960, 530, size=68, fade=(800, 1000)))
    ev.append(line("Ivory", a + 0.55, b, c["t2"], 960, 620, size=58, fade=(800, 1000)))
    for i, name in enumerate(c["chapters"], start=1):
        s = seg(f"{i:02d}")
        big0, big1 = s["start"] + 0.25, s["start"] + s["pre"] + 0.65
        ev.append(line("Gold", big0, big1, f"{i:02d}", 960, 450, size=30, fade=(400, 400)))
        ev.append(line("Ivory", big0 + 0.1, big1, name.upper(), 960, 540, size=56 if len(name) < 28 else 44, fade=(450, 400)))
        low0, low1 = s["start"] + s["pre"] + 0.1, s["end"] - 0.25
        ev.append(line("Gold", low0, low1, f"{i:02d}", 130, 930, align=7, size=36, fade=(350, 300)))
        ev.append(line("IvoryReg", low0, low1, name, 220, 936, align=7, size=34, fade=(350, 300)))
        ev.append(line("Dim", low0, low1, f"{i:02d}  /  10", 1840, 80, align=9, fade=(350, 300)))
    for sid, key, y in (("03", "p3", 160), ("04", "p4", 180), ("10", "p10", 160)):
        s = seg(sid)
        left, right = c[key]
        ev.append(line("GoldSans", s["start"] + 0.8, s["end"] - 0.4, left, 480, y, fade=(400, 400)))
        ev.append(line("GoldSans", s["start"] + 0.8, s["end"] - 0.4, right, 1440, y, fade=(400, 400)))
    s1 = seg("01")
    ev.append(line("Symbol", s1["start"] + s1["pre"] + 12, s1["end"] - 2, "R☉   =   2.95 km", 160, 680, align=7, fade=(400, 400)))
    ev.append(line("Symbol", s1["start"] + s1["pre"] + 16, s1["end"] - 2, "R⊕   =   8.9 mm", 160, 750, align=7, fade=(400, 400)))
    s5 = seg("05")
    ev.append(line("Symbol", s5["start"] + 6, s5["end"] - 4, "10⁶ – 10⁷ K", 160, 170, align=7, fade=(400, 400)))
    s6 = seg("06")
    mid = s6["start"] + (s6["end"] - s6["start"]) * 0.48
    ev.append(line("GoldSans", s6["start"] + 2, mid, "M87*    2019", 960, 88, fade=(350, 250)))
    ev.append(line("GoldSans", mid + 0.25, s6["end"] - 1.2, "Sgr A*    2022", 960, 88, fade=(250, 400)))
    s7 = seg("07")
    ev.append(line("GoldSans", s7["start"] + 3, s7["end"] - 3, "4.3 × 10⁶ M☉", 960, 88, fade=(400, 400)))
    ev.append(line("GoldSans", s7["start"] + 8, s7["end"] - 3, "S2", 1260, 430, fade=(300, 300)))
    s9 = seg("09")
    ev.append(line("Symbol", s9["start"] + 6, s9["end"] - 6, "T   ∝   1 / M", 160, 190, align=7, fade=(400, 400)))
    cl = seg("11_close")
    e0 = cl["start"] + cl["pre"] + cl["vo"] * 0.72
    e1 = cl["end"] - 0.3
    ev.append(line("Gold", e0, e1, c["end1"], 960, 460, size=26, fade=(800, 500)))
    ev.append(line("Ivory", e0 + 0.2, e1, c["end2"], 960, 545, size=52, fade=(800, 500)))
    ev.append(line("Ivory", e0 + 0.4, e1, c["end3"], 960, 620, size=48, fade=(800, 500)))
    path = OUT / f"{lang}.ass"
    path.write_text(header + "".join(ev), encoding="utf-8")
    return path

def encode(lang, ss=None, dur=None, dest=None):
    ass = build_ass(lang)
    base = OUT / "base.mp4"
    mix = OUT / f"mix_{lang}.wav"
    if dest is None:
        dest = {
            "es": Path("/tmp/bh_ES.mp4"),
            "en": Path("/tmp/bh_EN.mp4"),
        }[lang]
    # subtitles filter needs the path escaped for filtergraph
    ass_esc = str(ass).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
    vf = f"scale=1920:1080:flags=lanczos,hqdn3d=1.2:1.2:4:4,subtitles='{ass_esc}'"
    cmd = ["ffmpeg", "-y", "-progress", "pipe:1", "-nostats"]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    cmd += ["-i", str(base)]
    if ss is not None:
        cmd += ["-ss", str(ss)]
    cmd += ["-i", str(mix), "-vf", vf]
    if dur is not None:
        cmd += ["-t", str(dur)]
    cmd += [
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest", str(dest),
    ]
    print("encode", lang, dest, flush=True)
    log = open(f"/tmp/encode_{lang}.log", "w")
    r = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log, text=True)
    last = ""
    for line in r.stdout:
        line = line.strip()
        if line.startswith("out_time=") or line.startswith("progress="):
            last = line
            if line.startswith("out_time="):
                print(lang, line, flush=True)
    code = r.wait()
    log.close()
    if code != 0:
        err = Path(f"/tmp/encode_{lang}.log").read_text()[-2000:]
        raise RuntimeError(err or f"ffmpeg exit {code} last {last}")
    print("done", dest, flush=True)

if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "es"
    if arg == "test":
        encode("es", ss=36, dur=8, dest=OUT / "test_title.mp4")
    else:
        encode(arg)
