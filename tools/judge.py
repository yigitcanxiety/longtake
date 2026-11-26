#!/usr/bin/env python3
"""judge.py — does the cut have a rhythm, and does it carry? Fails a slideshow before a human sits down.

  python3 tools/judge.py film.mp4 --comp comp.html --shots 0,1.4,3.1,4.2,6.8,9.4,11.6

Legs (a number and PASS / WARN / FAIL; only FAIL fails the verdict):
  cadence     shot lengths vary: CV >= 0.25. Equal shots are slides.
  rest        >= 25 % of frames dead-still (<0.5 mean abs diff at 320 px) and one quiet stretch >= 1 s.
  burst       a 1.5 s window with >= 3 big changes (> 8). FAIL only when --ref has one; else WARN.
  audio       peak <= -3 dBFS, 0 clipped, >= 15 % of 1/12 s frames quiet.
  continuity  probe.py's carry score over declared beats: FAIL < 0.5, WARN < 0.7.
  curves      FAIL when something travels > 80 px per frame (normalised to 1920) without shutter blur.
  framing     FAIL when a declared mustStay id is off frame inside its window.
  reference   (--ref) both energy maps side by side; no verdict.

Exit 1 on any FAIL.
"""
import argparse, json, os, subprocess, sys, tempfile, wave

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import probe


def frames_of(video, w=320):
    h = int(round(w * 9 / 16))
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h},format=gray", "-f", "rawvideo", "-"],
                       capture_output=True)
    if p.returncode != 0:
        raise SystemExit(p.stderr.decode()[:400])
    return np.frombuffer(p.stdout, np.uint8).reshape(-1, h, w).astype(np.int16)


def energy_stats(video):
    f = frames_of(video)
    d = np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))
    still = float((d < 0.5).mean())
    quiet_run = best = 0
    for v in d:
        quiet_run = quiet_run + 1 if v < 1.0 else 0
        best = max(best, quiet_run)
    fps = film_fps(video)
    wins = [d[i:i + int(1.5 * fps)] for i in range(0, max(1, len(d) - 1))]
    hot = [i / fps for i, w in enumerate(wins) if (w > 4).sum() >= 3]
    bursts = []
    for t in hot:
        if not bursts or t - bursts[-1] > 0.6:
            bursts.append(t)
    return {"still": round(still, 3), "quiet_s": round(best / fps, 2), "bursts": bursts, "fps": fps,
            "longest": len(d) / fps}


def film_fps(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", video],
                       capture_output=True, text=True).stdout.strip()
    n, _, d = r.partition("/")
    try:
        return max(1, int(round(float(n) / float(d or 1))))
    except ValueError:
        return 30


def audio_stats(video):
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "a.wav")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "2", "-ar", "48000", wav], capture_output=True)
    if r.returncode != 0 or not os.path.exists(wav):
        return None
    w = wave.open(wav)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).reshape(-1, 2) / 32767
    w.close()
    n = 4000
    rms = np.array([np.sqrt((x[i:i + n] ** 2).mean()) for i in range(0, max(1, len(x) - n), n)])
    return {"peak": round(20 * np.log10(np.abs(x).max() + 1e-9), 1), "clipped": int((np.abs(x) >= 0.999).sum()),
            "quiet": round(float((20 * np.log10(rms + 1e-9) < -40).mean()), 3)}


def leg(name, state, detail):
    print(f"  {state:4}  {name:10} {detail}")
    return state != "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--comp", default=None); ap.add_argument("--shots", default=None); ap.add_argument("--ref", default=None)
    a = ap.parse_args()
    es = energy_stats(a.video)
    fps = es["fps"]
    print(f"\n{os.path.basename(a.video)} — {es['longest']:.2f} s at {fps} fps · still {es['still']:.0%} · bursts {len(es['bursts'])}\n")
    oks = []
    shots = a.shots
    if not shots and a.comp:
        try:
            import asyncio
            r = asyncio.run(probe.collect(a.comp, fps=1))
            beats = [float(b["t"]) for b in (r.get("beats") or [])]
            if beats: shots = ",".join(str(x) for x in [0] + beats + [r["dur"]])
        except Exception:
            pass
    if shots:
        ts = sorted(float(x) for x in shots.split(","))
        L = np.diff(ts)
        L = L[L > 0.02]
        cv = float(L.std() / L.mean()) if len(L) > 1 else 0.0
        oks.append(leg("cadence", "PASS" if cv >= 0.25 else "FAIL", f"shot lengths {np.round(L, 2).tolist()} CV {cv:.2f} (need >= .25)"))
    else:
        print("  skip  cadence    (pass --shots or --comp with __beats)")
    oks.append(leg("rest", "PASS" if es["still"] >= 0.25 and es["quiet_s"] >= 1.0 else "FAIL",
                   f"still {es['still']:.0%}  longest quiet {es['quiet_s']} s"))
    ref_es = None
    if a.ref:
        ref_es = energy_stats(a.ref)
    if es["bursts"]:
        oks.append(leg("burst", "PASS", f"{len(es['bursts'])} burst windows"))
    elif ref_es and ref_es["bursts"]:
        oks.append(leg("burst", "FAIL", f"none; the reference has {len(ref_es['bursts'])}"))
    else:
        oks.append(leg("burst", "WARN", "none — fine without hits; --ref holds it to a reference"))
    au = audio_stats(a.video)
    if au:
        oks.append(leg("audio", "PASS" if au["peak"] <= -3 and au["clipped"] == 0 and au["quiet"] >= 0.15 else "FAIL",
                       f"peak {au['peak']} dBFS  clipped {au['clipped']}  quiet {au['quiet']}"))
    else:
        print("  skip  audio      (no track)")
    info = None
    p = os.path.splitext(a.video)[0] + ".render.json"
    if os.path.exists(p):
        info = json.load(open(p))
    if a.comp:
        import asyncio
        vfps = fps
        res = asyncio.run(probe.collect(a.comp, fps=vfps))
        ct = probe.continuity(res)
        cv = probe.curves(res)
        bare = [e["t"] for e in ct["events"] if not e["exempt"] and e["kind"] == "bare"]
        state = "FAIL" if ct["score"] < 0.5 else "WARN" if ct["score"] < 0.7 else "PASS"
        oks.append(leg("continuity", state, f"carry {ct['score']:.2f} over {ct['considered']} boundaries; bare at {bare or '—'}"))
        blurred = bool(info and info.get("shutter", 0) > 0)
        state = "FAIL" if cv["peak"] > 80 and not blurred else "PASS"
        where = f" ({cv['peak_at'][0]} at {cv['peak_at'][1]:.2f} s)" if cv["peak_at"] else ""
        oks.append(leg("curves", state, f"peak {cv['peak']:.0f} px/frame @{vfps}{where}, " + ("shutter blur" if blurred else "no blur recorded")))
        fr = probe.framing(res)
        off = {k: v["bad"] for k, v in fr.items() if v["bad"]}
        if fr:
            oks.append(leg("framing", "FAIL" if off else "PASS", "; ".join(f"{k} off at {b[:4]}" for k, b in off.items()) or f"{len(fr)} ids stayed in frame"))
        else:
            print("  skip  framing    (declare window.__meta.mustStay)")
        if res.get("failed"):
            print(f"  !!    __clock threw at {len(res['failed'])} samples (first t={res['failed'][0][0]})")
    if ref_es:
        print(f"\n  reference: still {ref_es['still']:.0%} · quiet {ref_es['quiet_s']} s · bursts {len(ref_es['bursts'])}")
    print("\nVERDICT:", "PASS" if all(oks) else "FAIL")
    sys.exit(0 if all(oks) else 1)


if __name__ == "__main__":
    main()
