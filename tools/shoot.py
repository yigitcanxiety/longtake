#!/usr/bin/env python3
"""shoot.py — clock a composition frame by frame, photograph it, encode, mux sound.

  python3 tools/shoot.py cases/hello-12s/comp.html --out cases/hello-12s/draft.mp4 --sfx cases/hello-12s/sfx.wav
  python3 tools/shoot.py comp.html --out film.mp4 --final --sfx sfx.wav     # 4K60, only after the cut is accepted
  python3 tools/shoot.py comp.html --out raw.mp4 --shutter 0               # no motion blur

Drafts are the default (1920×1080, 30 fps, 180° shutter) because every round before acceptance is
a draft.

Motion blur is real integration: a screenshot is an instant, so a fast move strobes into copies.
For each moving frame the page is clocked several times across the open shutter (centred on the
frame time) and the captures are averaged in linear light. Both ends of the shutter are captured
first; identical ends mean nothing moved, and the frame is written as is. A page that defines
window.__travel(t0, t1) — the farthest anything moves on screen between two times, CSS px — gets as
many captures per frame as keep neighbours --gap px apart, between --samples-min and --samples-max.

A cut stays a cut: when one step between neighbouring captures holds the change (≥ 3× any other
step), only the captures on the frame time's side are averaged.

The page contract: window.__meta.dur, window.__clock(t) → Promise (resolves after images decode),
window.__ready → Promise, optional window.__travel and window.__meta.cuts.

Writes <out>.render.json (fps, shutter, samples, frames, captures, seconds) for judge.py.
"""
import argparse, asyncio, io, json, math, multiprocessing, os, shutil, subprocess, time
from concurrent.futures import ProcessPoolExecutor, wait

import numpy as np
from PIL import Image
from playwright.async_api import async_playwright

_u = np.arange(256) / 255.0
LIN = np.where(_u <= 0.04045, _u / 12.92, ((_u + 0.055) / 1.055) ** 2.4).astype(np.float32)
_q = np.arange(65536) / 65535.0
SRGB = np.clip(np.rint(np.where(_q <= 0.0031308, _q * 12.92, 1.055 * np.power(_q, 1 / 2.4) - 0.055) * 255.0), 0, 255).astype(np.uint8)

GPU = ["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist", "--enable-gpu-rasterization"]


def grey(png):
    return np.asarray(Image.open(io.BytesIO(png)).convert("L").reduce(8), dtype=np.int16)


def side(smalls, at):
    """Captures to integrate: all of them, unless one neighbour step is a discontinuity (a cut,
    not motion). Then the side that holds the frame time."""
    n = len(smalls)
    if n < 4:
        return list(range(n))
    d = np.array([np.abs(smalls[k + 1] - smalls[k]).mean() for k in range(n - 1)])
    j = int(d.argmax())
    if d[j] <= 0 or d[j] < 3 * np.delete(d, j).max():
        return list(range(n))
    mid = at * n
    return list(range(j + 1)) if mid <= j + 0.5 else list(range(j + 1, n))


def integrate(pngs, at):
    keep = side([grey(p) for p in pngs], at)
    acc = None
    for k in keep:
        lin = LIN[np.asarray(Image.open(io.BytesIO(pngs[k])).convert("RGB"))]
        acc = lin if acc is None else acc + lin
    return SRGB[np.clip(np.rint(acc * (65535.0 / len(keep))), 0, 65535).astype(np.uint16)], len(keep) < len(pngs)


def work(job):
    return asyncio.run(_work(job))


async def _work(j):
    fps, dur, fr, sh = j["fps"], j["dur"], j["fr"], j["shutter"]
    st = {"captures": 0, "still": 0, "cuts": 0, "errors": [], "hist": {}, "relaunched": 0}
    async with async_playwright() as p:
        B = {}

        async def launch():
            if B:
                await B["br"].close()
            B["br"] = br = await p.chromium.launch(args=GPU if j.get("gpu") else [])
            ctx = await br.new_context(viewport={"width": j["width"], "height": j["height"]}, device_scale_factor=j["scale"])
            B["pg"] = pg = await ctx.new_page()
            pg.on("pageerror", lambda e: st["errors"].append(str(e)))
            pg.on("console", lambda m: st["errors"].append(m.text) if m.type == "error" else None)
            await pg.goto("file://" + j["comp"])
            await pg.evaluate("window.__ready")

        await launch()
        adapt = sh > 0 and await B["pg"].evaluate("typeof window.__travel === 'function'")
        open_s = (sh / 360.0) / fps
        cuts = j.get("cuts") or []

        async def grab(t):
            await B["pg"].evaluate(f"window.__clock({t})")
            st["captures"] += 1
            return await B["pg"].screenshot(type="png")

        async def frame(t, path, f):
            if sh <= 0:
                open(path, "wb").write(await grab(t))
                return
            S = j["samples"]
            if adapt:
                try:
                    far = await B["pg"].evaluate(f"window.__travel({max(t - open_s / 2, 0.0)}, {min(t + open_s / 2, dur - 1e-6)})")
                    S = min(j["smax"], max(j["smin"], math.ceil(far * j["scale"] / j["gap"])))
                except Exception:
                    if not B["br"].is_connected():
                        raise
            lo, hi = max(t - open_s / 2, 0.0), min(t + open_s / 2, dur - 1e-6)
            for c in cuts:                                    # a declared cut inside the shutter: keep one side
                if lo < c < hi:
                    if c - lo < hi - c:
                        lo, hi = lo, max(lo + 1e-6, c)
                    else:
                        lo, hi = min(hi - 1e-6, c), hi
            span = hi - lo
            times = [lo + span * (k + 0.5) / S for k in range(S)]
            first = await grab(times[0])
            last = await grab(times[-1])
            if first == last:
                open(path, "wb").write(first)
                st["still"] += 1
                return
            pngs = [first] + [await grab(tk) for tk in times[1:-1]] + [last]
            img, cut = integrate(pngs, 0.5)
            st["cuts"] += cut
            Image.fromarray(img).save(path, compress_level=1)
            st["hist"][S] = st["hist"].get(S, 0) + 1

        done = 0
        for f in range(j["k"], j["N"], j["n"]):
            t = f / fps
            path = f"{fr}/{f:05d}.png"
            if j.get("resume") and os.path.exists(path):
                continue
            if done and j.get("recycle") and done % j["recycle"] == 0:
                await launch()
            done += 1
            for attempt in range(4):
                try:
                    await frame(t, path, f)
                    break
                except Exception as e:
                    if "closed" not in str(e) or attempt == 3:
                        raise
                    st["relaunched"] += 1
                    try:
                        await B["br"].close()
                    except Exception:
                        pass
                    B.clear()
                    await launch()
        await B["br"].close()
    return st


async def info(comp, width, height, gpu):
    async with async_playwright() as p:
        br = await p.chromium.launch(args=GPU if gpu else [])
        pg = await (await br.new_context(viewport={"width": width, "height": height})).new_page()
        await pg.goto("file://" + comp)
        await pg.evaluate("window.__ready")
        v = await pg.evaluate("({dur:(window.__meta||{}).dur||null, cuts:(window.__meta||{}).cuts||null, travel:typeof window.__travel==='function'})")
        await br.close()
    return v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("comp"); ap.add_argument("--out", default="draft.mp4")
    ap.add_argument("--fps", type=int, default=30); ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--final", action="store_true", help="3840×2160 at 60 fps")
    ap.add_argument("--shutter", type=float, default=180.0, help="shutter angle; 0 = none")
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--gap", type=float, default=6.0)
    ap.add_argument("--samples-min", type=int, default=4); ap.add_argument("--samples-max", type=int, default=48)
    ap.add_argument("--workers", type=int, default=max(1, min(8, (os.cpu_count() or 3) - 2)))
    ap.add_argument("--width", type=int, default=1920); ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--sfx", default=None); ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--recycle", type=int, default=150, help="relaunch a worker's browser after n frames")
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()
    if a.final:
        a.fps, a.scale = 60, 2
    comp, out = os.path.abspath(a.comp), os.path.abspath(a.out)
    fr = os.path.join(os.path.dirname(out), "_frames")
    if not a.resume:
        shutil.rmtree(fr, ignore_errors=True)
    os.makedirs(fr, exist_ok=True)
    meta = asyncio.run(info(comp, a.width, a.height, a.gpu))
    dur = meta["dur"] or 15
    N = int(round(dur * a.fps))
    nw = max(1, min(a.workers, N))
    adapt = a.shutter > 0 and meta["travel"]
    print(f"{N} frames on {nw} workers · " + ("no shutter" if a.shutter <= 0 else
          f"shutter {a.shutter:g}°, " + (f"captures sized by __travel (gap {a.gap:g} px)" if adapt else f"{a.samples} captures per moving frame")), flush=True)
    job = dict(comp=comp, fr=fr, fps=a.fps, dur=dur, N=N, n=nw, width=a.width, height=a.height, scale=a.scale, shutter=a.shutter,
               samples=max(2, a.samples), gap=a.gap, smin=max(2, a.samples_min), smax=max(2, a.samples_max),
               resume=a.resume, recycle=a.recycle, gpu=a.gpu, cuts=meta["cuts"])
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=nw, mp_context=multiprocessing.get_context("spawn")) as ex:
        futs = [ex.submit(work, dict(job, k=k)) for k in range(nw)]
        while wait(futs, timeout=15).not_done:
            print(f"  {len(os.listdir(fr))}/{N}  {time.time() - t0:.0f}s", flush=True)
        res = [f.result() for f in futs]
    secs = time.time() - t0
    captures, still, cuts = (sum(r[k] for r in res) for k in ("captures", "still", "cuts"))
    errs = [e for r in res for e in r["errors"]]
    rel = sum(r.get("relaunched", 0) for r in res)
    hist = {}
    for r in res:
        for k, v in r["hist"].items():
            hist[k] = hist.get(k, 0) + v
    print(f"{N} frames, {captures} captures ({still} stills skipped, {cuts} kept a cut hard) in {secs:.0f}s; errors: {errs[:3] or 'none'}"
          + (f"; relaunched {rel}×" if rel else ""))
    cmd = ["ffmpeg", "-v", "error", "-y", "-framerate", str(a.fps), "-i", f"{fr}/%05d.png"]
    if a.sfx:
        cmd += ["-i", os.path.abspath(a.sfx)]
    cmd += ["-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p,setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", str(a.crf), "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "5.2", "-movflags", "+faststart"]
    if a.sfx:
        cmd += ["-c:a", "aac", "-b:a", "256k", "-shortest"]
    subprocess.run(cmd + [out], check=True)
    if not a.keep_frames:
        shutil.rmtree(fr, ignore_errors=True)
    json.dump({"comp": comp, "fps": a.fps, "scale": a.scale, "size": [a.width * a.scale, a.height * a.scale],
               "shutter": a.shutter if a.shutter > 0 else 0, "samples": ("adaptive" if adapt else max(2, a.samples)) if a.shutter > 0 else 1,
               "samples_per_moving_frame": {str(k): hist[k] for k in sorted(hist)}, "workers": nw, "frames": N,
               "still_frames": still, "cut_frames": cuts, "captures": captures, "seconds": round(secs, 1), "final": a.final},
              open(os.path.splitext(out)[0] + ".render.json", "w"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
