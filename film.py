#!/usr/bin/env python3
"""Cinematic black-hole documentary picture. Language-free base, 1280x720, 24fps, 10:00."""
import json, math, os, subprocess, sys, time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path("/workspace/documentary")
AUDIO = Path("/workspace/artifacts/documentary/audio")
OUT = Path("/workspace/artifacts/documentary")
W, H = 1280, 720
FPS = 24
TARGET = 600.0

def durations(lang):
    out = {}
    for p in sorted((AUDIO / lang).glob("*.mp3")):
        err = subprocess.run(["ffmpeg", "-i", str(p)], capture_output=True, text=True).stderr
        line = [ln for ln in err.splitlines() if "Duration:" in ln][0]
        hh, mm, ss = line.split("Duration:")[1].split(",")[0].strip().split(":")
        out[p.stem] = int(hh) * 3600 + int(mm) * 60 + float(ss)
    return out

def build_timeline():
    es, en = durations("es"), durations("en")
    order = ["00_open", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11_close"]
    scenes = {
        "00_open": "approach",
        "01": "collapse",
        "02": "horizon",
        "03": "spag",
        "04": "clocks",
        "05": "quasar",
        "06": "eht",
        "07": "galaxy",
        "08": "scales",
        "09": "hawking",
        "10": "myth",
        "11_close": "close",
    }
    vmax = {k: max(es[k], en[k]) for k in order}
    open_pre, open_post = 2.4, 3.4
    title_dur = 16.0
    ch_pre, ch_post = 5.0, 4.4
    close_pre, close_post = 1.6, 11.0
    ch_keys = order[1:-1]

    def total():
        t = open_pre + vmax["00_open"] + open_post + title_dur
        t += close_pre + vmax["11_close"] + close_post
        for k in ch_keys:
            t += ch_pre + vmax[k] + ch_post
        return t

    slack = TARGET - total()
    if slack >= 0:
        title_dur += min(3.5, slack * 0.18)
        slack = TARGET - total()
        close_post += min(7.0, max(0.0, slack * 0.22))
        slack = TARGET - total()
        ch_post += slack / len(ch_keys)
    else:
        # tighten air, never the voice
        need = -slack
        cut = min(ch_post - 2.2, need / len(ch_keys))
        ch_post -= cut
        need -= cut * len(ch_keys)
        if need > 0:
            title_dur = max(9.0, title_dur - need * 0.4)
            close_post = max(6.0, close_post - need * 0.6)
        # final nudge on chapter posts
        slack = TARGET - total()
        ch_post += slack / len(ch_keys)

    segs = []
    t = 0.0

    def add(sid, scene, pre, vo, post, chapter=None):
        nonlocal t
        dur = pre + vo + post
        segs.append({
            "id": sid,
            "scene": scene,
            "start": round(t, 3),
            "end": round(t + dur, 3),
            "pre": round(pre, 3),
            "vo": round(vo, 3),
            "post": round(post, 3),
            "chapter": chapter,
            "es_vo": es.get(sid if sid != "title" else "", es.get(sid, 0)),
            "en_vo": en.get(sid if sid != "title" else "", en.get(sid, 0)),
        })
        t += dur

    add("00_open", "approach", open_pre, vmax["00_open"], open_post, None)
    add("title", "title", title_dur, 0.0, 0.0, None)
    for i, k in enumerate(ch_keys, start=1):
        add(k, scenes[k], ch_pre, vmax[k], ch_post, i)
    add("11_close", "close", close_pre, vmax["11_close"], close_post, None)
    # fix float drift so the last frame lands on TARGET
    drift = TARGET - segs[-1]["end"]
    segs[-1]["end"] = round(segs[-1]["end"] + drift, 3)
    segs[-1]["post"] = round(segs[-1]["post"] + drift, 3)
    meta = {"fps": FPS, "width": W, "height": H, "duration": segs[-1]["end"], "segments": segs,
            "es": es, "en": en}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timeline.json").write_text(json.dumps(meta, indent=2))
    (ROOT / "timeline.json").write_text(json.dumps(meta, indent=2))
    return meta

def smooth(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)

class Film:
    def __init__(self):
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        self.x = (xs - W / 2) / (H * 0.5)
        self.y = (ys - H / 2) / (H * 0.5)
        self.r = np.sqrt(self.x * self.x + self.y * self.y) + 1e-4
        self.ang = np.arctan2(self.y, self.x)
        Hh, Wh = H // 2, W // 2
        yhs, xhs = np.mgrid[0:Hh, 0:Wh].astype(np.float32)
        self.xh = (xhs - Wh / 2) / (Hh * 0.5)
        self.yh = (yhs - Hh / 2) / (Hh * 0.5)
        self.Hh, self.Wh = Hh, Wh
        rng = np.random.default_rng(11)
        self.star = self._stars(rng)
        self._lens_s = None
        self.sy = self.sx = None
        self.set_lens(0.062)
        self.lensed = np.ascontiguousarray(self.star[self.sy, self.sx])
        self.ring = np.exp(-((self.r - 0.215) / 0.012) ** 2).astype(np.float32)
        vig = 1.0 - 0.62 * np.clip((self.x / 1.55) ** 2 + self.y ** 2, 0, 1) ** 1.15
        self.vig = np.clip(vig, 0.28, 1.0).astype(np.float32)
        self.bottom = np.clip((self.y - 0.42) / 0.85, 0, 1).astype(np.float32)
        self.shade = (self.vig * (1.0 - 0.62 * self.bottom)).astype(np.float32)
        self.shade_eht = self.vig.copy()
        self.grains = []
        for i in range(6):
            g = rng.normal(0, 1, (H, W)).astype(np.float32) * 0.011
            self.grains.append(g)
        self._rays = self._build_rays()
        # fixed dust
        self.dust_a = rng.random(48).astype(np.float32) * math.tau
        self.dust_r = 0.15 + rng.random(48).astype(np.float32) * 1.15
        self.dust_z = 0.4 + rng.random(48).astype(np.float32) * 1.4
        self.disk_cache_t = None
        self.disk_cache = None

    def _stars(self, rng):
        img = np.zeros((H, W, 3), np.float32)
        img[:] = (0.010, 0.011, 0.018)
        # milky way
        band_y = self.y - 0.08 * np.sin(self.x * 0.85)
        band = np.exp(-(band_y ** 2) / 0.055) * np.exp(-(self.x ** 2) / 6.5)
        dust = 0.65 + 0.35 * np.sin(self.x * 2.2 + self.y * 3.0)
        img += band[..., None] * np.array([0.055, 0.045, 0.075], np.float32) * dust[..., None]
        # star layers
        for n, sharp, gain in ((900, 2.2, 0.55), (280, 1.4, 1.0), (60, 0.7, 1.8)):
            px = rng.integers(0, W, n)
            py = rng.integers(0, H, n)
            mag = rng.random(n).astype(np.float32) ** sharp
            warm = rng.random(n).astype(np.float32)
            cols = np.stack([
                mag * (0.75 + 0.25 * warm),
                mag * (0.78 + 0.1 * (1 - warm)),
                mag * (0.7 + 0.35 * (1 - warm)),
            ], axis=1) * gain
            for dx, dy, w in ((0, 0, 1), (1, 0, 0.45), (-1, 0, 0.45), (0, 1, 0.45), (0, -1, 0.45),
                              (2, 0, 0.18), (-2, 0, 0.18), (0, 2, 0.18), (0, -2, 0.18)):
                xx = np.clip(px + dx, 0, W - 1)
                yy = np.clip(py + dy, 0, H - 1)
                for c in range(3):
                    np.add.at(img[:, :, c], (yy, xx), cols[:, c] * w)
        # diffraction on a handful
        bright = rng.integers(0, W, 18)
        brighty = rng.integers(0, H, 18)
        for x, y in zip(bright, brighty):
            img[y, max(0, x - 8):min(W, x + 9), :] += 0.25
            img[max(0, y - 8):min(H, y + 9), x, :] += 0.18
        return np.clip(img, 0, 2.2)

    def set_lens(self, s):
        if self._lens_s is not None and abs(self._lens_s - s) < 1e-4:
            return
        self._lens_s = s
        r2 = self.r * self.r + 0.018
        bx = self.x - self.x * s / r2
        by = self.y - self.y * s / r2
        self.sx = np.clip((bx * (H * 0.5) + W / 2).astype(np.int32), 0, W - 1)
        self.sy = np.clip((by * (H * 0.5) + H / 2).astype(np.int32), 0, H - 1)

    def stars_frame(self, t, lens=0.062, scroll=18.0):
        shift = int(t * scroll) % W
        if abs(lens - 0.062) <= 0.012:
            img = np.roll(self.lensed, shift, axis=1).copy()
            img += img * self.ring[..., None] * 0.38
            return img
        self.set_lens(lens)
        src = np.roll(self.star, shift, axis=1)
        img = np.ascontiguousarray(src[self.sy, self.sx])
        img += img * self.ring[..., None] * 0.3
        return img

    def disk(self, t, zoom=1.0, boost=1.0):
        key = (round(t, 2), round(zoom, 3), round(boost, 3))
        if key == self.disk_cache_t:
            return self.disk_cache
        z = max(zoom, 0.05)
        x = self.xh / z
        y = self.yh / z
        ang = np.arctan2(y, x)
        r = np.sqrt(x * x + y * y) + 1e-4
        ye = y * 1.72
        re = np.sqrt(x * x + ye * ye) + 1e-4
        inner, outer = 0.15, 1.05
        edge_in = np.clip((re - 0.145) / 0.025, 0, 1)
        edge_out = np.clip((outer - re) / 0.22, 0, 1)
        band = edge_in * edge_out * np.clip((re - inner) / 0.03 + 0.15, 0, 1)
        # hide the far-side primary under the hole later; keep full ellipse
        temp = (inner / np.maximum(re, inner)) ** 0.78
        dop = np.clip(1.0 / (1.0 - 0.55 * (x / re)), 0.18, 4.2) ** 1.65
        spiral = 0.55 + 0.45 * np.sin(6.2 * np.log(re + 0.18) - ang * 2.15 + t * 0.85)
        turb = 0.82 + 0.18 * np.sin(ang * 7 + re * 18 - t * 1.7)
        inten = temp * dop * spiral * turb * band
        # lensed far-side arcs
        arc = np.exp(-((r - 0.305) / 0.03) ** 2) * np.clip(y * 5.5, 0, 1)
        arc2 = np.exp(-((r - 0.248) / 0.014) ** 2)
        tex = 0.58 + 0.42 * np.sin(ang * 3.0 - t * 0.9 + 2.4 * np.log(r + 0.15))
        sec = (arc * 1.15 + arc2 * 0.85) * tex * np.clip(dop, 0.35, 2.2)
        # chromatic photon ring
        w = 0.0062
        pr = np.exp(-((r - 0.198) / w) ** 2)
        pr_r = np.exp(-((r - 0.206) / w) ** 2)
        pr_b = np.exp(-((r - 0.190) / (w * 1.05)) ** 2)
        hot = 0.45 + 0.55 * np.clip(0.2 - x, 0, 1.6)
        glow = np.exp(-(r ** 2) / 0.09) * 0.22
        jet = np.exp(-((x / (0.018 + 0.045 * np.abs(y))) ** 2)) * np.exp(-np.abs(y) * 0.85)
        jet *= np.clip((np.abs(y) - 0.12) / 0.08, 0, 1) * (0.55 + 0.45 * np.sin(t * 2.2 + y * 6))
        sh = np.clip((r - 0.162) / 0.014, 0, 1)
        base = (inten * 1.25 + sec * 0.62 + glow) * sh + pr * hot * 1.5
        col = np.empty((self.Hh, self.Wh, 3), np.float32)
        c = np.clip(base * boost, 0, 8)
        col[..., 0] = np.clip(c * 1.25 + pr_r * hot * 1.3 + jet * 0.35, 0, 2.4)
        col[..., 1] = np.clip((c - 0.12) * 0.95 + pr * hot * 0.7 + jet * 0.48, 0, 2.0)
        col[..., 2] = np.clip((c - 0.55) * 0.85 + pr_b * hot * 1.15 + jet * 0.85, 0, 1.8)
        # soft horizontal bloom, kept out of the shadow
        lum = np.clip(col[..., 0], 0, 1.5)
        k = 22
        csum = np.cumsum(lum, axis=1, dtype=np.float32)
        blur = csum.copy()
        blur[:, k:] = csum[:, k:] - csum[:, :-k]
        blur /= k
        outside = np.clip((r - 0.175) / 0.03, 0, 1)
        col[..., 0] += blur * 0.10 * outside
        col[..., 1] += blur * 0.045 * outside
        # shadow core
        core = np.clip((0.155 - r) / 0.018, 0, 1)
        col *= (1 - core)[..., None]
        up = np.repeat(np.repeat(col, 2, axis=0), 2, axis=1)
        self.disk_cache_t = key
        self.disk_cache = up
        return up

    def _build_rays(self):
        groups = []
        # escaping
        for b in np.linspace(-0.95, 0.95, 14):
            xs = np.linspace(-1.7, 1.7, 260)
            bend = 0.11 * np.tanh(b * 4) / (xs * xs + 0.12)
            ys = b * 0.15 + b + bend * (1 if abs(b) > 0.22 else 0)
            if abs(b) < 0.2:
                continue
            groups.append(self._raster(xs, ys, capture=False))
        # captured spirals
        for k in range(8):
            phi = np.linspace(0.2, 5.4 + k * 0.15, 280)
            rad = 0.19 + 0.85 * np.exp(-0.55 * phi)
            ang0 = k * math.tau / 8
            xs = rad * np.cos(phi + ang0)
            ys = rad * np.sin(phi + ang0) * 0.92
            groups.append(self._raster(xs, ys, capture=True))
        return groups

    def _raster(self, xs, ys, capture):
        px = np.clip((xs * (H * 0.5) + W / 2).astype(np.int32), 0, W - 1)
        py = np.clip((ys * (H * 0.5) + H / 2).astype(np.int32), 0, H - 1)
        u = np.linspace(0, 1, len(px)).astype(np.float32)
        return px, py, u, capture

    def paint_rays(self, img, t, strength=1.0):
        for px, py, u, capture in self._rays:
            phase = (t * (0.22 if capture else 0.33) + (0.15 if capture else 0.0)) % 1.0
            # two pulses
            d1 = np.minimum(np.abs(u - phase), 1 - np.abs(u - phase))
            pulse = np.exp(-(d1 ** 2) / 0.004)
            base = 0.10 if not capture else 0.06
            inten = (base + pulse) * strength
            if capture:
                np.add.at(img[:, :, 0], (py, px), inten * 0.95)
                np.add.at(img[:, :, 1], (py, px), inten * 0.55)
                np.add.at(img[:, :, 2], (py, px), inten * 0.28)
            else:
                np.add.at(img[:, :, 0], (py, px), inten * 0.75)
                np.add.at(img[:, :, 1], (py, px), inten * 0.82)
                np.add.at(img[:, :, 2], (py, px), inten * 0.9)

    def add_dust(self, img, t):
        a = self.dust_a + t * 0.05 * self.dust_z
        r = self.dust_r
        x = r * np.cos(a)
        y = r * np.sin(a) * 0.6 + 0.05 * np.sin(t * 0.4 + self.dust_a)
        px = np.clip((x * (H * 0.5) + W / 2).astype(np.int32), 1, W - 2)
        py = np.clip((y * (H * 0.5) + H / 2).astype(np.int32), 1, H - 2)
        v = (0.04 + 0.05 * self.dust_z).astype(np.float32)
        np.add.at(img[:, :, 0], (py, px), v)
        np.add.at(img[:, :, 1], (py, px), v * 0.9)
        np.add.at(img[:, :, 2], (py, px), v * 0.7)

    def finish(self, img, t, lift_bottom=True):
        img *= (self.shade if lift_bottom else self.shade_eht)[..., None]
        img += self.grains[int(t * FPS) % len(self.grains)][..., None]
        np.clip(img, 0, 1.15, out=img)
        img *= 0.9
        np.clip(img, 0, 1, out=img)
        return (img * 255.0 + 0.5).astype(np.uint8)

    def splat(self, img, x, y, color, rad=1.5):
        px = int(x * (H * 0.5) + W / 2)
        py = int(y * (H * 0.5) + H / 2)
        r = int(rad) + 2
        x0, x1 = max(0, px - r), min(W, px + r + 1)
        y0, y1 = max(0, py - r), min(H, py + r + 1)
        if x0 >= x1 or y0 >= y1:
            return
        yy, xx = np.ogrid[y0:y1, x0:x1]
        d2 = (xx - px) ** 2 + (yy - py) ** 2
        m = np.exp(-d2 / (2 * rad * rad)).astype(np.float32)
        for c in range(3):
            img[y0:y1, x0:x1, c] += m * color[c]

    # ---------- scenes ----------
    def scene_approach(self, t, local, dur):
        z = 0.06 + 0.98 * smooth(min(1, local / 0.92))
        lens = 0.01 + 0.055 * smooth(local)
        img = self.stars_frame(t, lens=lens, scroll=8 + 22 * local)
        img += self.disk(t, zoom=z, boost=0.35 + 0.9 * smooth(local))
        return img

    def scene_title(self, t, local, dur):
        img = self.stars_frame(t, scroll=10)
        img *= 0.72
        img += self.disk(t, zoom=1.02 + 0.06 * math.sin(local * math.pi), boost=0.85)
        return img

    def scene_collapse(self, t, local, dur):
        img = self.stars_frame(t * 0.4, lens=0.03 + 0.04 * local, scroll=12)
        # progenitor star
        life = np.clip(1.0 - (local - 0.18) / 0.42, 0, 1)
        if life > 0:
            glow = np.exp(-(self.r ** 2) / (0.02 + 0.12 * life)) * life
            img[..., 0] += glow * 1.4
            img[..., 1] += glow * 1.15
            img[..., 2] += glow * 0.7
        # infall
        n = 640
        rng = np.random.default_rng(3)
        a0 = rng.random(n).astype(np.float32) * math.tau
        r0 = 0.18 + rng.random(n).astype(np.float32) ** 0.6 * 1.15
        fall = smooth(np.clip((local - 0.12) / 0.7, 0, 1))
        rad = r0 * (1 - 0.92 * fall)
        ang = a0 + fall * (2.4 + r0)
        xs = rad * np.cos(ang)
        ys = rad * np.sin(ang) * 0.78
        m = rad > 0.045
        px = np.clip((xs[m] * (H * 0.5) + W / 2).astype(np.int32), 0, W - 1)
        py = np.clip((ys[m] * (H * 0.5) + H / 2).astype(np.int32), 0, H - 1)
        heat = (1 - rad[m] / (r0[m] + 1e-3))
        np.add.at(img[:, :, 0], (py, px), 0.35 + heat * 0.8)
        np.add.at(img[:, :, 1], (py, px), 0.22 + heat * 0.35)
        np.add.at(img[:, :, 2], (py, px), 0.12)
        if local > 0.48:
            k = smooth((local - 0.48) / 0.25)
            img += self.disk(t, zoom=0.35 + 0.7 * k, boost=k)
            # flash
            if local < 0.62:
                flash = np.exp(-(self.r ** 2) / 0.08) * (1 - (local - 0.48) / 0.14)
                img += np.clip(flash, 0, 1)[..., None] * np.array([1.2, 0.8, 0.4], np.float32)
        return img

    def scene_horizon(self, t, local, dur):
        img = self.stars_frame(t * 0.5, lens=0.07, scroll=6)
        img *= 0.55
        # event horizon ring
        ring = np.exp(-((self.r - 0.34) / 0.006) ** 2)
        img[..., 0] += ring * 0.9
        img[..., 1] += ring * 0.72
        img[..., 2] += ring * 0.35
        inner = np.clip((0.34 - self.r) / 0.34, 0, 1) ** 1.4
        img *= (1 - 0.72 * inner)[..., None]
        self.paint_rays(img, t, strength=0.65 + 0.35 * math.sin(local * math.pi))
        # subtle disk behind
        img += self.disk(t, zoom=0.72, boost=0.28)
        return img

    def _figure(self, img, cx, cy, stretch, tint):
        pts = np.array([
            [0, -0.20], [0, -0.10], [0, 0.00], [0, 0.10],
            [-0.07, -0.02], [0.07, -0.02],
            [-0.045, 0.22], [0.045, 0.22],
        ], np.float32)
        links = [(0, 1), (1, 2), (2, 3), (1, 4), (1, 5), (3, 6), (3, 7)]
        feet = pts[:, 1].max()
        rel = feet - pts[:, 1]
        pts = pts.copy()
        pts[:, 1] += rel * stretch * 1.6
        pts[:, 0] *= max(0.22, 1.0 - stretch * 0.55)
        pts[:, 0] += cx
        pts[:, 1] += cy
        col = np.array(tint, np.float32)
        for i, j in links:
            a, b = pts[i], pts[j]
            for s in np.linspace(0, 1, 18):
                p = a * (1 - s) + b * s
                self.splat(img, p[0], p[1], col, rad=1.6)
        self.splat(img, pts[0, 0], pts[0, 1], col, rad=3.2)

    def scene_spag(self, t, local, dur):
        img = self.stars_frame(t * 0.3, lens=0.04, scroll=5)
        img *= 0.5
        # divider
        img[:, W // 2 - 1:W // 2 + 1, :] += 0.08
        # left: stellar, violent early
        u = smooth(np.clip(local / 0.85, 0, 1))
        left_s = np.clip((u - 0.25) / 0.45, 0, 1) ** 1.2
        # small BH
        self._mini_hole(img, -0.72, 0.05, 0.16, t)
        self._figure(img, -0.72, -0.18 + u * 0.28, left_s, (1.3, 0.85, 0.45))
        # right: supermassive, calm until late
        right_s = np.clip((u - 0.62) / 0.38, 0, 1) ** 1.3
        self._mini_hole(img, 0.72, 0.08, 0.42, t)
        self._figure(img, 0.72, -0.34 + u * 0.55, right_s * 0.85, (0.8, 0.9, 1.15))
        return img

    def _mini_hole(self, img, cx, cy, rad, t):
        d = np.sqrt((self.x - cx) ** 2 + (self.y - cy) ** 2)
        hole = np.clip((rad - d) / 0.02, 0, 1)
        ring = np.exp(-((d - rad) / 0.008) ** 2)
        hot = 0.6 + 0.4 * np.sin(t + self.ang)
        img[..., 0] += ring * (0.9 * hot)
        img[..., 1] += ring * 0.55
        img[..., 2] += ring * 0.22
        img *= (1 - 0.92 * hole)[..., None]
        # disk hint
        band = np.exp(-((self.y - cy) / 0.03) ** 2) * np.clip((d - rad) / 0.05, 0, 1) * np.exp(-((d - rad) / (rad * 1.8)) ** 2)
        img[..., 0] += band * 0.45
        img[..., 1] += band * 0.22

    def scene_clocks(self, t, local, dur):
        img = self.stars_frame(t * 0.25, lens=0.035, scroll=4)
        img *= 0.38
        # horizon suggestion behind right clock
        d = np.sqrt((self.x - 0.55) ** 2 + (self.y - 0.05) ** 2)
        ring = np.exp(-((d - 0.55) / 0.007) ** 2) * 0.45
        img[..., 0] += ring
        img[..., 1] += ring * 0.7
        # clocks
        near = local  # 0..1 of chapter, asymptotic slowdown
        far_angle = t * 1.4
        # proper clock runs steady; distant view of the near clock slows
        slow = 1 - math.exp(-local * 1.1)
        near_angle = 1.3 * (local * 0.15 + 0.85 * (1 - math.exp(-3 * (1 - local)))) * math.tau
        # actually: the clock AT the horizon (right) slows as local->1
        near_angle = math.tau * (0.05 + 0.55 * (1 - math.exp(-2.4 * local)))
        self._clock(img, -0.62, 0.02, 0.30, far_angle, (0.85, 0.9, 1.0))
        self._clock(img, 0.58, 0.02, 0.30, near_angle, (1.15, 0.82, 0.45))
        return img

    def _clock(self, img, cx, cy, rad, angle, tint):
        d = np.sqrt((self.x - cx) ** 2 + (self.y - cy) ** 2)
        face = np.clip((rad - d) / 0.01, 0, 1) * np.clip((d - rad * 0.15) / 0.02, 0, 1)
        rim = np.exp(-((d - rad) / 0.006) ** 2)
        img[..., 0] += rim * tint[0]
        img[..., 1] += rim * tint[1]
        img[..., 2] += rim * tint[2]
        img[..., :] += (face * 0.05)[..., None]
        # ticks
        for k in range(12):
            a = k / 12 * math.tau
            x = cx + math.cos(a) * rad * 0.82
            y = cy + math.sin(a) * rad * 0.82
            self.splat(img, x, y, tint, rad=1.3)
        # hand
        hx = cx + math.sin(angle) * rad * 0.62
        hy = cy - math.cos(angle) * rad * 0.62
        steps = 24
        for s in np.linspace(0, 1, steps):
            self.splat(img, cx * (1 - s) + hx * s, cy * (1 - s) + hy * s, tint, rad=1.5)
        self.splat(img, cx, cy, (1, 1, 1), rad=2.2)

    def scene_quasar(self, t, local, dur):
        z = 0.82 + 0.28 * smooth(local)
        img = self.stars_frame(t * 0.6, lens=0.05, scroll=14)
        img *= 0.75
        img += self.disk(t, zoom=z, boost=1.15 + 0.25 * math.sin(local * math.pi))
        # extra jet length
        beam = np.exp(-((self.x / (0.02 + 0.08 * np.abs(self.y))) ** 2))
        beam *= np.exp(-np.abs(self.y) * 0.55) * np.clip((np.abs(self.y) - 0.15) / 0.1, 0, 1)
        pulse = 0.65 + 0.35 * math.sin(t * 3.0)
        img[..., 0] += beam * 0.25 * pulse
        img[..., 1] += beam * 0.38 * pulse
        img[..., 2] += beam * 0.7 * pulse
        return img

    def scene_eht(self, t, local, dur):
        img = np.zeros((H, W, 3), np.float32)
        img[:] = (0.012, 0.008, 0.006)
        # which source
        phase = smooth(np.clip((local - 0.42) / 0.12, 0, 1))
        rad = 0.30 * (1 - 0.18 * phase)
        thick = 0.016 * (1 + 0.15 * phase)
        d = self.r
        ring = np.exp(-((d - rad) / thick) ** 2)
        # asymmetric brightness (spin)
        asym = 0.35 + 0.9 * np.clip(0.15 - self.y, 0, 1) ** 1.2
        asym = asym * (1.0 - 0.25 * phase) + phase * (0.4 + 0.8 * np.clip(-self.x, 0, 1))
        noise_seed = 5 if local < 0.5 else 9
        rng = np.random.default_rng(noise_seed)
        # smooth-ish blobs via low res noise upscaled
        nsmall = rng.random((H // 8, W // 8)).astype(np.float32)
        nup = np.repeat(np.repeat(nsmall, 8, 0), 8, 1)[:H, :W]
        focus = smooth(np.clip(local / 0.22, 0, 1)) * (1 - 0.35 * phase) + phase * smooth(np.clip((local - 0.48) / 0.2, 0, 1))
        blur_mix = 1 - 0.75 * np.clip(focus, 0, 1)
        ring_v = ring * asym * (0.65 + 0.55 * nup) 
        img[..., 0] += ring_v * 1.35
        img[..., 1] += ring_v * 0.55
        img[..., 2] += ring_v * 0.12
        # defocus haze
        haze = np.exp(-((d - rad) / (thick * 3.5)) ** 2) * blur_mix
        img[..., 0] += haze * 0.35
        img[..., 1] += haze * 0.12
        # dark shadow
        sh = np.clip((rad * 0.72 - d) / 0.02, 0, 1)
        img *= (1 - 0.95 * sh)[..., None]
        # film of the array: faint ticks, not text
        return img

    def scene_galaxy(self, t, local, dur):
        img = np.zeros((H, W, 3), np.float32)
        img[:] = (0.008, 0.009, 0.016)
        # spiral arms rotate slowly
        rot = t * 0.15
        ang = self.ang + rot
        rr = self.r
        arms = 0.5 + 0.5 * np.sin(2 * ang - np.log(rr + 0.15) * 3.4)
        disk = np.exp(-(rr / 0.95) ** 2) * (0.25 + 0.85 * arms) * np.clip(rr / 0.08, 0, 1)
        core = np.exp(-(rr ** 2) / 0.03)
        img[..., 0] += disk * 0.28 + core * 0.9
        img[..., 1] += disk * 0.30 + core * 0.55
        img[..., 2] += disk * 0.45 + core * 0.25
        # central darkness of the unseen mass, tiny
        hole = np.clip((0.025 - rr) / 0.01, 0, 1)
        img *= (1 - 0.85 * hole)[..., None]
        # orbits, S2 is brighter and faster
        orbits = [
            (0.22, 0.16, 1.15, 0.9, True),
            (0.38, 0.30, 0.55, 0.45, False),
            (0.52, 0.40, 0.32, 0.35, False),
            (0.70, 0.48, 0.22, 0.28, False),
            (0.90, 0.34, 0.16, 0.22, False),
        ]
        for i, (a, b, speed, bright, is_s2) in enumerate(orbits):
            th = t * speed + i
            # ellipse path + trail
            trail = 28 if is_s2 else 8
            for k in range(trail):
                tk = th - k * 0.05
                x = a * math.cos(tk)
                y = b * math.sin(tk)
                fade = (1 - k / trail) * bright
                col = (1.3, 0.95, 0.55) if is_s2 else (0.7, 0.8, 1.0)
                self.splat(img, x, y, np.array(col) * fade, rad=2.4 if (is_s2 and k == 0) else 1.2)
            # faint ellipse
            for s in range(80):
                tk = s / 80 * math.tau
                x = a * math.cos(tk)
                y = b * math.sin(tk)
                self.splat(img, x, y, (0.25, 0.28, 0.35), rad=0.8)
        return img

    def scene_scales(self, t, local, dur):
        img = self.stars_frame(t * 0.2, lens=0.02, scroll=3)
        img *= 0.30
        masses = [10, 4.3e6, 6.5e9, 6e10]
        labels_ready = True
        # log size
        sizes = []
        for m in masses:
            sizes.append(0.05 + 0.22 * math.log10(m) / math.log10(masses[-1]))
        xs = [-1.05, -0.35, 0.40, 1.15]
        appear = [0.05, 0.22, 0.42, 0.62]
        for x, s, a0, m in zip(xs, sizes, appear, masses):
            k = smooth(np.clip((local - a0) / 0.16, 0, 1))
            if k <= 0:
                continue
            d = np.sqrt((self.x - x) ** 2 + (self.y + 0.02) ** 2)
            rad = s * k
            ring = np.exp(-((d - rad) / 0.007) ** 2) * k
            glow = np.exp(-(d ** 2) / (0.02 + rad)) * 0.25 * k
            img[..., 0] += ring * 1.1 + glow * 0.8
            img[..., 1] += ring * 0.7 + glow * 0.35
            img[..., 2] += ring * 0.3 + glow * 0.12
            hole = np.clip((rad * 0.72 - d) / 0.015, 0, 1) * k
            img *= (1 - 0.9 * hole)[..., None]
        # final overwhelm
        if local > 0.78:
            k = smooth((local - 0.78) / 0.2)
            img += self.disk(t, zoom=0.4 + 1.3 * k, boost=0.2 + 0.8 * k) * k
        return img

    def scene_hawking(self, t, local, dur):
        img = self.stars_frame(t * 0.15, lens=0.05, scroll=2)
        img *= 0.42
        d = self.r
        ring = np.exp(-((d - 0.36) / 0.007) ** 2)
        img[..., 0] += ring * 0.85
        img[..., 1] += ring * 0.62
        img[..., 2] += ring * 0.28
        hole = np.clip((0.36 - d) / 0.36, 0, 1)
        img *= (1 - 0.78 * hole ** 1.3)[..., None]
        # quantum shimmer
        shimmer = 0.5 + 0.5 * np.sin(self.ang * 8 + t * 3)
        rim = np.exp(-((d - 0.36) / 0.02) ** 2) * shimmer * 0.12
        img[..., 2] += rim
        img[..., 0] += rim * 0.4
        for i in range(7):
            phase = (local * 1.35 + i / 7.0) % 1.0
            ang = i / 7.0 * math.tau + 0.4
            # pair separates
            spread = phase
            r_out = 0.36 + spread * 0.55
            r_in = 0.36 - spread * 0.30
            if r_in > 0.04:
                self.splat(img, math.cos(ang) * r_in, math.sin(ang) * r_in, (1.2, 0.45, 0.2), rad=2.0)
            if phase < 0.92:
                fade = 1 - phase
                self.splat(img, math.cos(ang) * r_out, math.sin(ang) * r_out, (0.45, 0.75, 1.3) * np.array(fade), rad=2.2)
        return img

    def scene_myth(self, t, local, dur):
        img = self.stars_frame(t * 0.2, lens=0.03, scroll=4)
        img *= 0.33
        # split
        img[:, W // 2 - 1:W // 2 + 1] += 0.07
        # LEFT hover: stars streak faster as local grows
        speed = 4 + (local ** 2) * 70
        rng = np.random.default_rng(21)
        n = 90
        yy = rng.uniform(-0.85, 0.85, n).astype(np.float32)
        xx = rng.uniform(-1.55, -0.15, n).astype(np.float32)
        length = np.clip(0.01 + (local ** 1.6) * 0.35, 0.01, 0.4)
        for i in range(n):
            x0 = float(xx[i])
            y0 = float(yy[i])
            ln = float(length)
            steps = max(2, int(8 + ln * 40))
            bright = 0.15 + 0.5 * min(1, local * 1.4)
            for s in range(steps):
                x = x0 + (s / steps) * ln
                if x > -0.08:
                    break
                self.splat(img, x, y0, (bright, bright * 0.85, bright * 0.55), rad=0.9)
        # hovering clock spinning up
        spin = t * (1.2 + local * 14)
        self._clock(img, -0.72, 0.08, 0.22, spin, (0.95, 0.85, 0.55))
        # RIGHT free fall, calm clock, shrinking sky
        self._clock(img, 0.78, -0.48, 0.16, t * 0.7, (0.8, 0.88, 1.05))
        sky_r = 0.62 * (1 - 0.78 * smooth(local))
        d = np.sqrt((self.x - 0.55) ** 2 + (self.y - 0.08) ** 2)
        sky = np.clip((sky_r - d) / 0.015, 0, 1)
        # only right side
        right = (self.x > 0.08).astype(np.float32)
        img[..., 0] += sky * right * 0.55
        img[..., 1] += sky * right * 0.65
        img[..., 2] += sky * right * 0.95
        rim = np.exp(-((d - sky_r) / 0.008) ** 2) * right
        img[..., 0] += rim * 0.8
        img[..., 1] += rim * 0.9
        img[..., 2] += rim * 1.1
        # singularity beat near the end
        if local > 0.72:
            k = smooth((local - 0.72) / 0.18)
            white = np.exp(-(d ** 2) / (0.04 + 0.2 * (1 - k))) * k * right
            img += white[..., None] * np.array([1.0, 0.96, 0.9], np.float32)
            if local > 0.9:
                fade = smooth((local - 0.9) / 0.1)
                img *= (1 - 0.85 * fade * right)[..., None]
        return img

    def scene_close(self, t, local, dur):
        z = 1.05 - 0.48 * smooth(local)
        img = self.stars_frame(t, lens=0.06 * (0.4 + 0.6 * (1 - local)), scroll=8)
        img += self.disk(t, zoom=max(0.2, z), boost=0.95 * (1 - 0.35 * local))
        # gravitational-wave rings, two pulses
        for center in (0.28, 0.55):
            u = (local - center) / 0.22
            if 0 <= u <= 1:
                rad = 0.18 + u * 1.15
                ring = np.exp(-((self.r - rad) / 0.012) ** 2) * (1 - u) * 0.7
                img[..., 0] += ring * 0.7
                img[..., 1] += ring * 0.8
                img[..., 2] += ring * 1.0
        return img

    def render_at(self, t, seg):
        local = 0 if seg["end"] <= seg["start"] else (t - seg["start"]) / (seg["end"] - seg["start"])
        local = float(np.clip(local, 0, 1))
        dur = seg["end"] - seg["start"]
        fn = {
            "approach": self.scene_approach,
            "title": self.scene_title,
            "collapse": self.scene_collapse,
            "horizon": self.scene_horizon,
            "spag": self.scene_spag,
            "clocks": self.scene_clocks,
            "quasar": self.scene_quasar,
            "eht": self.scene_eht,
            "galaxy": self.scene_galaxy,
            "scales": self.scene_scales,
            "hawking": self.scene_hawking,
            "myth": self.scene_myth,
            "close": self.scene_close,
        }[seg["scene"]]
        img = fn(t, local, dur)
        self.add_dust(img, t)
        # chapter pulse
        if seg["chapter"] and local < 0.035:
            p = 1 - local / 0.035
            shock = np.exp(-((self.r - 0.25 - (1 - p) * 0.4) ** 2) / 0.004) * p * 0.45
            img[..., 0] += shock
            img[..., 1] += shock * 0.8
            img[..., 2] += shock * 0.4
        lift = seg["scene"] != "eht"
        return self.finish(img, t, lift_bottom=lift)

def seg_at(segs, t):
    for s in segs:
        if s["start"] <= t < s["end"]:
            return s
    return segs[-1]

def dump_frames(film, meta):
    picks = []
    for s in meta["segments"]:
        mid = (s["start"] + s["end"]) * 0.5
        picks.append((s["scene"], mid))
        if s["scene"] in ("approach", "collapse", "myth", "eht"):
            picks.append((s["scene"] + "_early", s["start"] + 1.2))
    outdir = ROOT / "frames"
    outdir.mkdir(exist_ok=True)
    for name, t in picks:
        fr = film.render_at(t, seg_at(meta["segments"], t))
        Image.fromarray(fr, "RGB").save(outdir / f"{name}.png")
        print("saved", name, t, flush=True)

def render_base(film, meta, path):
    n = int(round(meta["duration"] * FPS))
    cmd = [
        "ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
        "-r", str(FPS), "-i", "-", "-an", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "16", "-pix_fmt", "yuv420p", str(path),
    ]
    log = open(path.with_suffix(".log"), "w")
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
    t0 = time.time()
    segs = meta["segments"]
    try:
        i = 0
        while i < n:
            t = i / FPS
            fr = film.render_at(t, seg_at(segs, t))
            raw = fr.tobytes()
            proc.stdin.write(raw)
            i += 1
            if i < n:
                proc.stdin.write(raw)
                i += 1
            if i % 96 == 0:
                el = time.time() - t0
                fps = i / max(el, 1e-3)
                eta = (n - i) / max(fps, 1e-3)
                print(f"frame {i}/{n}  {fps:.2f} fps  eta {eta/60:.1f} min", flush=True)
        proc.stdin.close()
    except BrokenPipeError:
        log.flush()
        raise RuntimeError(path.with_suffix(".log").read_text()[-2000:])
    code = proc.wait()
    log.close()
    if code != 0:
        raise RuntimeError(path.with_suffix(".log").read_text()[-2000:])
    print("base done", path, flush=True)

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--frames"
    print("timeline...", flush=True)
    meta = build_timeline()
    print("duration", meta["duration"], "segments", len(meta["segments"]), flush=True)
    for s in meta["segments"]:
        print(f"  {s['id']:10} {s['scene']:10} {s['start']:7.2f}-{s['end']:7.2f} pre {s['pre']:.2f} vo {s['vo']:.2f}", flush=True)
    print("init film...", flush=True)
    film = Film()
    if mode == "--frames":
        dump_frames(film, meta)
    elif mode == "--render":
        render_base(film, meta, OUT / "base.mp4")
    else:
        raise SystemExit("use --frames or --render")

if __name__ == "__main__":
    main()
