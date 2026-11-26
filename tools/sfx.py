#!/usr/bin/env python3
"""sfx.py — one room, a handful of materials, placed from the film's own events.

  python3 tools/sfx.py --demo room.wav
  python3 tools/sfx.py --comp comp.html --out sfx.wav --dur 15
  python3 tools/sfx.py --score score.json --events events.json --out sfx.wav

Events come from window.__events() → [{t, kind, gain?, pan?}] (or the JSON form). Kinds: air, tick,
wood, glass, sub, bubble, riser. Fewer events than beats: a tone per event is the audio version of a
slideshow.

All synthesis, no recorded sources: nothing to license. One synthetic room (decaying noise with early
reflections) is shared by every event, so they belong to the same place. Mastered to ~-16 LUFS with
the ceiling at -4 dBTP so the AAC render stays under -3 dBFS.
"""
import argparse, json, subprocess, wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 48000
RNG = np.random.default_rng(7)


def env(n, attack=0.004, decay=0.12, shape=2.0):
    t = np.arange(n) / SR
    a = np.clip(t / attack, 0, 1)
    return a * np.exp(-t / decay) ** (1 / shape)


def noise(n=SR):
    return RNG.standard_normal(n)


def band(x, lo, hi, order=3):
    sos = butter(order, [lo / (SR / 2), hi / (SR / 2)], btype="band", output="sos")
    return sosfilt(sos, x)


def material(kind, dur=1.2):
    n = int(dur * SR)
    if kind == "air":
        x = band(noise(n), 300, 2600) * env(n, 0.05, 0.7, 1.4)
    elif kind == "tick":
        x = band(noise(n), 1800, 9000) * env(n, 0.0008, 0.02, 1.2)
    elif kind == "wood":
        x = band(noise(n), 120, 900) * env(n, 0.001, 0.07, 1.5)
        x += 0.5 * np.sin(2 * np.pi * 180 * np.arange(n) / SR) * env(n, 0.001, 0.05, 2)
    elif kind == "glass":
        t = np.arange(n) / SR
        x = sum(np.sin(2 * np.pi * f * t) * amp for f, amp in ((2140, 1), (3290, 0.6), (4870, 0.35)))
        x *= env(n, 0.001, 0.35, 1.6)
    elif kind == "sub":
        t = np.arange(n) / SR
        f = 90 * np.exp(-t * 2.4) + 32
        x = np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.004, 0.45, 1.8)
    elif kind == "bubble":
        t = np.arange(n) / SR
        x = np.sin(2 * np.pi * (320 * np.exp(t * 6)) * t) * env(n, 0.006, 0.16, 2)
    elif kind == "riser":
        t = np.arange(n) / SR
        x = band(noise(n), 500, 5000) * np.linspace(0, 1, n) ** 2 * np.exp(-np.clip(t - dur * 0.75, 0, None) * 8)
    else:
        raise SystemExit(f"unknown kind {kind}")
    return x / (np.abs(x).max() + 1e-9)


def room(sec=2.2):
    """One room: sparse early reflections, then a decaying diffuse tail."""
    n = int(sec * SR)
    ir = np.zeros(n)
    for d, g in ((0.011, 0.5), (0.023, 0.38), (0.037, 0.3), (0.053, 0.22), (0.079, 0.16)):
        ir[int(d * SR)] = g
    tail = noise(n) * np.exp(-np.arange(n) / SR * 5.2)
    ir += 0.35 * band(tail, 180, 5200)
    ir[: int(0.008 * SR)] = 0
    return ir / np.abs(ir).max()


def events_of(comp):
    import asyncio, os
    from playwright.async_api import async_playwright

    async def go():
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={"width": 1920, "height": 1080})
            await pg.goto("file://" + os.path.abspath(comp))
            await pg.evaluate("window.__ready")
            ev = await pg.evaluate("window.__events ? window.__events() : []")
            await b.close()
            return ev or []
    return asyncio.run(go())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default=None); ap.add_argument("--comp", default=None); ap.add_argument("--score", default=None)
    ap.add_argument("--events", default=None); ap.add_argument("--out", default="sfx.wav"); ap.add_argument("--dur", type=float, default=15.0)
    ap.add_argument("--music", default=None, help="optional royalty-free bed, ducked under the hits")
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    global RNG
    RNG = np.random.default_rng(a.seed)

    ev = []
    if a.comp:
        ev = events_of(a.comp)
    if a.events:
        ev += json.load(open(a.events))
    if a.score:
        sc = json.load(open(a.score))
        a.dur = float(sc.get("dur", a.dur))
        ev += sc.get("events", [])

    if a.demo:
        kinds = ["air", "tick", "wood", "glass", "sub", "bubble", "riser"]
        ev = [{"t": 0.4 + i * 0.55, "kind": k, "gain": 0.8} for i, k in enumerate(kinds)]
        a.dur, a.out = 0.4 + len(kinds) * 0.55 + 1.2, a.demo

    n = int(a.dur * SR)
    L = np.zeros(n + 3 * SR); R = np.zeros(n + 3 * SR)
    cache = {}
    for e in ev:
        k = e.get("kind", "tick")
        if k not in cache: cache[k] = material(k)
        s = cache[k]
        i = int(float(e["t"]) * SR)
        if i >= n: continue
        seg = s[: len(L) - i]
        g = float(e.get("gain", 1.0))
        if "pan" in e:                                 # constant-power pan
            p = (float(e["pan"]) + 1) / 2
            gl, gr = np.cos(p * np.pi / 2), np.sin(p * np.pi / 2)
        else:
            gl = gr = 0.7071
        L[i:i + len(seg)] += seg * g * gl
        R[i:i + len(seg)] += seg * g * gr
    L, R = L[:n], R[:n]
    wet = np.stack([fftconvolve(L, room(), mode="full")[:n], fftconvolve(R, room(), mode="full")[:n]], 1)
    mix = 0.55 * np.stack([L, R], 1) + 0.8 * wet
    if a.music:
        r = subprocess.run(["ffmpeg", "-v", "error", "-i", a.music, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
        if r.returncode == 0:
            bed = np.frombuffer(r.stdout, np.float32)[:n]
            if len(bed) < n: bed = np.pad(bed, (0, n - len(bed)))
            bed /= np.abs(bed).max() + 1e-9
            # duck the bed under each hit
            duck = np.ones(n)
            for e in ev:
                i = int(float(e["t"]) * SR)
                if i < n: duck[i:i + int(0.35 * SR)] *= 0.45
            mix = mix + 0.28 * np.stack([bed * np.convolve(duck, np.ones(2400) / 2400, "same")] * 2, 1)
    rms = np.sqrt((mix ** 2).mean() + 1e-12)
    mix *= 10 ** ((-16 + 23) / 20) / (rms + 1e-12)             # ~ -16 LUFS
    peak = np.abs(mix).max() + 1e-12
    mix *= min(1.0, 10 ** ((-4) / 20) / peak)
    st = np.tanh(mix * 1.02) * 0.999
    with wave.open(a.out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(st, -1, 1) * 32767).astype(np.int16).tobytes())
    print(f"wrote {a.out} · {len(ev)} events in one room, {a.dur:.1f} s")


if __name__ == "__main__":
    main()
