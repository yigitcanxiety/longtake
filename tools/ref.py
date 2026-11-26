#!/usr/bin/env python3
"""ref.py — read a reference clip in numbers before touching a composition.

  python3 tools/ref.py ref.mp4 --out ana/

Prints the numbers a film has to match, not a description: how much of it is dead still, where it
cuts, how its moves ease (median t80), and whether it was shot with motion blur (smear width).
Writes ana/energy.txt, ana/sheet.png (cut midpoints) and ana/ref.json.

Energy map: rows are vertical bands (top of the frame first), columns are 1/4 s, glyph = mean abs
difference in that cell (`.` still … `#` hard). Read it for when the film moves, not what it shows.
"""
import argparse, json, os, subprocess, sys

import numpy as np
from PIL import Image, ImageDraw

GLYPH = " .:-=+*#%@"


def frames(video, w=320):
    h = int(round(w * 9 / 16))
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"], capture_output=True)
    if p.returncode != 0:
        raise SystemExit(p.stderr.decode()[:400])
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, h, w).astype(np.int16)


def fps(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", video],
                       capture_output=True, text=True).stdout.strip()
    n, _, d = r.partition("/")
    try: return max(1, int(round(float(n) / float(d or 1))))
    except ValueError: return 30


def energy_map(d, f):
    """6 bands × 4 per second, each cell the mean abs diff; printed with a ramp."""
    per = max(1, f // 4)
    H = d.shape[1]
    bands = np.array_split(np.arange(H), 6)
    cols = len(d) // per
    rows = []
    for b in bands:
        cells = [float(d[i:i + per][:, b].mean()) if i + per <= len(d) else 0.0 for i in range(0, cols * per, per)]
        rows.append("".join(GLYPH[min(9, int(v / 4))] for v in cells))
    return "\n".join(rows)


def smear(d, f):
    """Median width (px) of moving blobs in the direction of travel: < .78 reads as blurred."""
    widths = []
    for i in range(1, len(d), max(1, f // 4)):
        x = (d[i] - d[i - 1]).astype(np.float32)
        if x.max() < 8:
            continue
        m = x > x.max() * 0.35
        ys, xs = np.nonzero(m)
        if len(xs) < 20:
            continue
        widths.append(min(40.0, float(xs.std() * 2.4)))
    return round(float(np.median(widths)), 2) if widths else None


def t80_of(d, f):
    """Median t80 of block motion: share of a move spent before 80 % of its travel."""
    per = max(1, f // 2)
    out = []
    for i in range(0, len(d) - per, per):
        x = (d[i] - d[i + per - 1]).astype(np.float32)
        if x.max() < 8:
            continue
        ys, xs = np.nonzero(x > x.max() * 0.3)
        if len(xs) < 10:
            continue
        path = [float(np.abs(d[j + 1] - d[j]).sum()) for j in range(i, i + per - 1)]
        s = np.cumsum(path)
        if s[-1] <= 0:
            continue
        out.append(float(np.searchsorted(s, 0.8 * s[-1]) + 1) / len(path))
    return round(float(np.median(out)), 2) if out else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--out", default="ana/"); ap.add_argument("--sheet", type=int, default=8)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    d = frames(a.video)
    f = fps(a.video)
    diffs = np.abs(np.diff(d, axis=0)).mean(axis=(1, 2))
    cuts = cut_times(diffs, f)
    best = run = 0
    for v in diffs:
        run = run + 1 if v < 1.0 else 0
        best = max(best, run)
    em = energy_map(d, f)
    line = (f"motion: median t80 {t80_of(d, f)} · smear {smear(d, f)}  (t80 low = snaps; smear < .78 = shot with blur)")
    rep = (f"{os.path.basename(a.video)}\n{d.shape[1]}×{d.shape[2]} @ {f} fps, {len(d) / f:.1f} s\n"
           f"still {float((diffs < 0.5).mean()):.1%} · low {float((diffs < 3).mean()):.1%} · longest quiet {best / f:.2f} s\n"
           f"cuts {len(cuts)} at {[round(c, 2) for c in cuts]}\n{line}\n\nenergy map (1/4 s columns)\n{em}\n")
    open(os.path.join(a.out, "energy.txt"), "w").write(rep)
    print(rep)
    # contact sheet at cut midpoints and even gaps
    times = [c + 0.35 for c in cuts][: a.sheet]
    if len(times) < 3:
        times = list(np.linspace(0.1, len(d) / f - 0.1, min(a.sheet, 4)))
    tiles = []
    for t in times:
        i = min(len(d) - 1, int(t * f))
        im = Image.fromarray(d[i].astype(np.uint8)).convert("RGB").resize((480, 270))
        ImageDraw.Draw(im).text((6, 6), f"{t:.2f}s", fill=(230, 0, 0))
        tiles.append(im)
    sheet = Image.new("RGB", (480 * len(tiles), 270))
    for i, im in enumerate(tiles): sheet.paste(im, (480 * i, 0))
    sheet.save(os.path.join(a.out, "sheet.png"))
    json.dump({"duration": len(d) / f, "cuts": [round(c, 2) for c in cuts], "still": round(float((diffs < 0.5).mean()), 3),
               "quiet_s": round(best / f, 2), "t80_median": t80_of(d, f), "smear": smear(d, f)},
              open(os.path.join(a.out, "ref.json"), "w"), indent=1)
    print(f"wrote {a.out}energy.txt, sheet.png, ref.json")


def cut_times(diffs, f):
    """Local maxima above 25 within +-3 frames — one time per cut, not three."""
    out = []
    for i in np.nonzero(diffs > 25)[0]:
        lo, hi = max(0, i - 3), min(len(diffs), i + 4)
        if diffs[i] >= diffs[lo:hi].max():
            if not out or i / f - out[-1] > 0.18:
                out.append(i / f)
    return out


if __name__ == "__main__":
    main()
