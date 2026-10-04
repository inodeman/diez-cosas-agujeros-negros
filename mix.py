#!/usr/bin/env python3
"""Score, whooshes and narration mix for both languages. Timeline-locked to 10:00."""
import json, subprocess
from pathlib import Path

import numpy as np

AUDIO = Path("/workspace/artifacts/documentary/audio")
OUT = Path("/workspace/artifacts/documentary")
SR = 48000
TIMELINE = json.loads((OUT / "timeline.json").read_text())
DUR = float(TIMELINE["duration"])
N = int(round(DUR * SR))

def decode(path):
    raw = subprocess.check_output([
        "ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"
    ])
    return np.frombuffer(raw, dtype=np.float32).copy()

def norm_peak(x, peak=0.92):
    m = np.max(np.abs(x)) + 1e-8
    return x * (peak / m)

def envelope(vo, win=int(0.18 * SR)):
    a = np.abs(vo)
    c = np.cumsum(a, dtype=np.float64)
    out = c.copy()
    out[win:] = c[win:] - c[:-win]
    out[:win] = c[:win]
    out /= win
    # attack/release smoothing via a second pass
    k = int(0.25 * SR)
    c2 = np.cumsum(out, dtype=np.float64)
    sm = c2.copy()
    sm[k:] = c2[k:] - c2[:-k]
    sm /= k
    sm = sm / (np.max(sm) + 1e-8)
    return sm.astype(np.float32)

def whoosh(rng, dur=0.62, amp=0.22):
    m = int(dur * SR)
    noise = rng.normal(0, 1, m).astype(np.float32)
    # one-pole with rising cutoff approximation: integrate then high-emphasis
    y = np.empty(m, np.float32)
    acc = 0.0
    for i in range(m):
        cut = 0.02 + 0.45 * (i / m) ** 1.4
        acc += cut * (noise[i] - acc)
        y[i] = noise[i] - acc
    env = np.linspace(0, 1, m, dtype=np.float32) ** 0.4
    env *= np.linspace(1, 0, m, dtype=np.float32) ** 1.6
    return y * env * amp

def bell(freq, dur, amp):
    m = int(dur * SR)
    tt = np.arange(m, dtype=np.float32) / SR
    env = np.exp(-tt * 1.6)
    y = np.sin(2 * np.pi * freq * tt) * env
    y += 0.35 * np.sin(2 * np.pi * freq * 2.01 * tt) * np.exp(-tt * 2.4)
    return y * amp

def build_music():
    rng = np.random.default_rng(8)
    t = np.arange(N, dtype=np.float32) / SR
    segs = TIMELINE["segments"]

    def seg_gain(scene_set, width=1.4):
        g = np.zeros(N, np.float32)
        for s in segs:
            if s["scene"] not in scene_set and s["id"] not in scene_set:
                continue
            a = int(s["start"] * SR)
            b = int(s["end"] * SR)
            g[a:b] = 1
        # smooth edges
        k = int(width * SR)
        if k < 2:
            return g
        c = np.cumsum(g, dtype=np.float64)
        sm = c.copy()
        sm[k:] = (c[k:] - c[:-k]) / k
        sm[:k] = c[:k] / k
        return np.clip(sm, 0, 1).astype(np.float32)

    # harmonic beds in D dorian / open fifths. Original, slow, non-melodic.
    layers = [
        (55.00, 0.16),
        (82.41, 0.07),
        (110.00, 0.05),
        (164.81, 0.035),
        (220.00, 0.02),
    ]
    bed = np.zeros(N, np.float32)
    for i, (f, a) in enumerate(layers):
        lfo = 0.82 + 0.18 * np.sin(2 * np.pi * (0.03 + 0.01 * i) * t + i)
        bed += np.sin(2 * np.pi * f * t + 0.2 * i) * a * lfo
    # beating pair for the clock chapter
    beat = np.sin(2 * np.pi * 55.0 * t) * np.sin(2 * np.pi * 0.35 * t)
    clocks = seg_gain({"clocks"})
    bed += beat * 0.06 * clocks
    # air / high shimmer, very quiet
    shimmer = np.sin(2 * np.pi * 440 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t))
    shimmer += np.sin(2 * np.pi * 554.37 * t) * (0.5 + 0.5 * np.sin(2 * np.pi * 0.05 * t + 1))
    hawking = seg_gain({"hawking", "myth"})
    bed += shimmer * 0.012 * (0.35 + hawking)
    # title swell
    title = seg_gain({"title"}, width=0.6)
    swell = np.sin(2 * np.pi * 130.81 * t) * 0.07 + np.sin(2 * np.pi * 196.0 * t) * 0.04
    bed += swell * title
    # quasar wider
    quasar = seg_gain({"quasar", "approach"})
    bed += np.sin(2 * np.pi * 73.42 * t) * 0.05 * quasar
    # myth almost dry
    myth = seg_gain({"myth"})
    bed *= (1 - 0.55 * myth)
    # soft pulse, heartbeat of spacetime, rests in myth
    pulse = np.zeros(N, np.float32)
    period = int(2.6 * SR)
    for i in range(0, N, period):
        m = min(int(0.18 * SR), N - i)
        env = np.linspace(1, 0, m, dtype=np.float32) ** 2
        pulse[i:i + m] += env
    sub = np.sin(2 * np.pi * 46.0 * t) * pulse * 0.12 * (1 - myth)
    bed += sub
    # stereo decorrelation
    delay = int(0.013 * SR)
    left = bed + sub * 0.2
    right = np.zeros_like(left)
    right[delay:] = left[:-delay] * 0.92
    right += np.sin(2 * np.pi * 164.81 * t + 0.6) * 0.02
    # whooshes at chapter starts
    for s in segs:
        if s["id"] in ("00_open",):
            continue
        w = whoosh(rng, dur=0.7, amp=0.16 if s["id"] != "title" else 0.28)
        a = int(s["start"] * SR)
        b = min(N, a + len(w))
        left[a:b] += w[:b - a]
        right[a:b] += w[:b - a] * 0.85
    # bells during close (gravitational-wave rings)
    close = next(s for s in segs if s["id"] == "11_close")
    span = close["end"] - close["start"]
    for frac, freq in ((0.28, 196.0), (0.55, 146.83)):
        a = int((close["start"] + span * frac) * SR)
        y = bell(freq, 3.4, 0.11)
        b = min(N, a + len(y))
        left[a:b] += y[:b - a]
        right[a:b] += y[:b - a]
    # title sub impact
    title_s = next(s for s in segs if s["id"] == "title")
    a = int(title_s["start"] * SR)
    m = int(0.8 * SR)
    env = np.exp(-np.linspace(0, 6, m, dtype=np.float32))
    impact = np.sin(2 * np.pi * 40 * np.arange(m) / SR) * env * 0.35
    left[a:a + m] += impact
    right[a:a + m] += impact
    stereo = np.stack([left, right], axis=1)
    return stereo

def place_voice(lang):
    vo = np.zeros(N, np.float32)
    mapping = {
        "00_open": "00_open.mp3",
        "01": "01.mp3", "02": "02.mp3", "03": "03.mp3", "04": "04.mp3",
        "05": "05.mp3", "06": "06.mp3", "07": "07.mp3", "08": "08.mp3",
        "09": "09.mp3", "10": "10.mp3", "11_close": "11_close.mp3",
    }
    for s in TIMELINE["segments"]:
        fn = mapping.get(s["id"])
        if not fn:
            continue
        x = norm_peak(decode(AUDIO / lang / fn), 0.9)
        a = int((s["start"] + s["pre"]) * SR)
        b = min(N, a + len(x))
        vo[a:b] += x[:b - a]
    return vo

def mix(lang):
    print("music +", lang, flush=True)
    music = build_music()
    vo = place_voice(lang)
    env = envelope(vo)
    # duck: bed sits under the voice, opens in the pauses
    gain = (0.34 - 0.22 * np.clip(env * 1.4, 0, 1)).astype(np.float32)
    stereo = music * gain[:, None]
    stereo[:, 0] += vo
    stereo[:, 1] += vo
    peak = np.max(np.abs(stereo)) + 1e-8
    if peak > 0.98:
        stereo *= 0.98 / peak
    path = OUT / f"mix_{lang}.wav"
    cmd = [
        "ffmpeg", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
        "-c:a", "pcm_s16le", str(path),
    ]
    p = subprocess.run(cmd, input=stereo.astype(np.float32).tobytes(), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[-1500:])
    print("wrote", path, flush=True)

if __name__ == "__main__":
    mix("es")
    mix("en")
