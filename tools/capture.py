#!/usr/bin/env python3
"""capture.py — drive a real page in real time and record it as frames, with the action frame marked.

  python3 tools/capture.py footage.json --out footage/

Config:
  {"page": "http://localhost:5173", "w": 1280, "h": 800, "fps": 30,
   "clips": [{"name": "hero", "start": 0.6, "dur": 2.6, "mark": 0.5,
              "actions": [{"at": 0.0, "kind": "move", "x": 640, "y": 300, "ms": 300},
                          {"at": 0.5, "kind": "click"},
                          {"at": 0.9, "kind": "wheel", "dy": 400},
                          {"at": 1.4, "kind": "type", "text": "hello"}]}]}

One clip at a time: navigate, settle, then play actions on the wall clock while a CDP screencast is
recorded. A magenta 6×6 patch is injected top-left the instant the first input starts, so the frame
the page began reacting to is findable afterwards (info.json → mark). The pointer path is written too
(path.json) — the composition draws the hand back in, because the viewer has to see the cause.

Frames are 30 fps JPEG at the size shown; recording is wall-clock, not scripted-per-frame.
"""
import argparse, asyncio, base64, json, os, time
from playwright.async_api import async_playwright

MARK_JS = """() => { if (document.getElementById('__ltmark')) return;
  const d = document.createElement('div'); d.id='__ltmark';
  d.style.cssText='position:fixed;left:0;top:0;width:6px;height:6px;background:#ff00ff;z-index:2147483647';
  document.documentElement.appendChild(d); }"""
PATH_JS = """() => { window.__ltpath=[]; addEventListener('mousemove', e => window.__ltpath.push([performance.now(), e.clientX, e.clientY]), {passive:true}); }"""


def find_mark(frames):
    """Index of the first frame whose top-left patch is the magenta marker."""
    import io
    import numpy as np
    from PIL import Image
    for i, f in enumerate(frames):
        a = np.asarray(Image.open(io.BytesIO(f)).convert("RGB").crop((0, 0, 8, 8)), dtype=np.int16).reshape(-1, 3).mean(0)
        if a[0] > 190 and a[1] < 80 and a[2] > 190:
            return i
    return 0


async def run_clip(pg, cdp, clip, out, fps):
    d = os.path.join(out, clip["name"])
    os.makedirs(d, exist_ok=True)
    frames = []
    stopped = False

    def on_frame(p):
        if not stopped:
            frames.append((base64.b64decode(p["data"]), p.get("metadata", {}).get("timestamp", time.time())))

    cdp.on("Page.screencastFrame", lambda p: (on_frame(p), asyncio.ensure_future(cdp.send("Page.screencastFrameAck", {"sessionId": p["sessionId"]}))))
    await pg.wait_for_timeout(int(clip.get("start", 0.5) * 1000))
    await cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 88, "everyNthFrame": 1})
    t0 = time.time()
    mark_t, mx, my = None, 0, 0
    await pg.evaluate(PATH_JS)

    async def act(a):
        nonlocal mark_t
        if mark_t is None:
            await pg.evaluate(MARK_JS)
            mark_t = time.time()
        kind = a["kind"]
        nonlocal mx, my
        if kind == "move":
            mx, my = a["x"], a["y"]
            await pg.mouse.move(mx, my, steps=max(2, int(a.get("ms", 200) / 16)))
        elif kind == "click":
            if "x" in a: mx, my = a["x"], a["y"]
            await pg.mouse.click(mx, my)
        elif kind == "wheel":
            await pg.mouse.wheel(0, a.get("dy", 300))
        elif kind == "type":
            await pg.keyboard.type(a["text"], delay=a.get("delay", 45))
        elif kind == "wait":
            await pg.wait_for_timeout(a.get("ms", 200))

    acts = sorted(clip.get("actions", []), key=lambda a: a["at"])
    for a in acts:
        await pg.wait_for_timeout(max(0, int((a["at"] - (time.time() - t0)) * 1000)))
        await act(a)
    await pg.wait_for_timeout(max(0, int((clip["dur"] - (time.time() - t0)) * 1000)))
    stopped = True
    await cdp.send("Page.stopScreencast")

    # resample wall-clock frames onto a fixed fps grid, nearest earlier frame
    if not frames:
        raise SystemExit(f"clip {clip['name']}: no frames")
    start_ts = frames[0][1]
    want = int(clip["dur"] * fps)
    out_frames, k = [], 0
    for i in range(want):
        t = start_ts + i / fps
        while k + 1 < len(frames) and frames[k + 1][1] <= t:
            k += 1
        out_frames.append(frames[k][0])
    for i, data in enumerate(out_frames):
        open(os.path.join(d, f"{i + 1:04d}.jpg"), "wb").write(data)
    path = await pg.evaluate("window.__ltpath || []")
    base = path[0][0] if path else 0
    rel = [[round((p[0] - base) / 1000, 3), p[1], p[2]] for p in path]
    json.dump(rel, open(os.path.join(d, "path.json"), "w"))
    mark = find_mark(out_frames)
    json.dump({"n": len(out_frames), "fps": fps, "mark": mark, "w": clip.get("w"), "h": clip.get("h")}, open(os.path.join(d, "info.json"), "w"))
    print(f"  {clip['name']}: {len(out_frames)} frames, action at {mark / fps:.2f} s")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config"); ap.add_argument("--out", default="footage/")
    a = ap.parse_args()
    cfg = json.load(open(a.config))
    os.makedirs(a.out, exist_ok=True)
    w, h, fps = cfg.get("w", 1280), cfg.get("h", 800), cfg.get("fps", 30)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg = await ctx.new_page()
        cdp = await ctx.new_cdp_session(pg)
        await cdp.send("Page.enable")
        for clip in cfg["clips"]:
            await pg.goto(cfg["page"])
            await pg.wait_for_timeout(clip.get("settle", 400))
            await run_clip(pg, cdp, dict(clip, w=w, h=h), a.out, fps)
        await b.close()
    print("done")


if __name__ == "__main__":
    asyncio.run(main())
