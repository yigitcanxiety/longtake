#!/usr/bin/env python3
"""probe.py — read a composition's motion in numbers: what carries each boundary, how moves curve,
what leaves the frame.

  python3 tools/probe.py comp.html
  python3 tools/probe.py comp.html --out probe/          # + tracks.json, curves.png

The page contract is window.__clock(t) plus window.__frames(t) → [{id, key, x, y, w, h, op}]
(lib/paint.js provides it). Without __frames a DOM scan is used; canvas internals are then one
layer per canvas.

Declared beats. window.__beats = [{t, carry, hard?, note?}] names, for every boundary, the id that
survives it and visibly becomes the next beat. A boundary with a declared carry that did not move —
checked on the layer AND on the pixels inside its box — is bare. `hard: true` exempts a boundary
(the end card, a burst of hits). Without __beats, boundaries are inferred from replacement windows.

continuity  A boundary is CARRIED when a declared or surviving layer moves ≥ 2 % of the diagonal or
            scales ≥ 10 % across it; ANCHORED when only a large unchanged layer survives (a frame whose
            content swaps); BARE when nothing survives. Exempt: hard beats, bursts (≥ 3 cuts in 1.5 s),
            the last 1.2 s, __meta.cuts. score = (carried + anchored/2) / considered.
curves      Each layer's track is cut into moves: path, t80 (share of the move spent before 80 % of
            the path), peak px/frame (normalised to 1920), overshoot. Soft travel share and median
            t80 are printed, not judged.
framing     window.__meta.mustStay = {id: [t0, t1] | [t0, t1, 'whole']} — sampled times an id was
            entirely off frame, or (whole) not wholly inside.
"""
import argparse, asyncio, io, json, math, os, sys
import numpy as np
from playwright.async_api import async_playwright

AUTO_JS = r"""
(() => {
  if (window.__ltScan) return;
  const fold = s => { s = String(s || ''); const q = s.indexOf('?'); if (q >= 0) s = s.slice(0, q);
    return s.split('/').slice(-2).join('/').replace(/\d{2,}(?=\.[a-z0-9]+$)/i, '#'); };
  const pathOf = el => {
    const parts = [];
    for (let e = el; e && e.nodeType === 1 && e !== document.body; e = e.parentElement) {
      let p = e.tagName.toLowerCase();
      if (e.dataset.lt) { parts.unshift('lt:' + e.dataset.lt); break; }
      if (e.parentElement) { const sib = [...e.parentElement.children].filter(x => x.tagName === e.tagName); if (sib.length > 1) p += ':' + sib.indexOf(e); }
      parts.unshift(p);
    }
    return parts.join('>');
  };
  window.__ltScan = () => {
    const VW = innerWidth, VH = innerHeight, out = [], memo = new Map();
    const op = el => { if (!el || el.nodeType !== 1) return 1; if (memo.has(el)) return memo.get(el);
      const cs = getComputedStyle(el); let o = (cs.display === 'none' || cs.visibility === 'hidden') ? 0 : parseFloat(cs.opacity);
      if (o > 0) o *= op(el.parentElement); memo.set(el, o); return o; };
    const add = (id, key, r, o, kind) => {
      const x0 = Math.max(0, r.left), y0 = Math.max(0, r.top), x1 = Math.min(VW, r.right), y1 = Math.min(VH, r.bottom);
      if (x1 - x0 < 2 || y1 - y0 < 2 || o < 0.05) return;
      if ((kind === 'box' || kind === 'canvas') && r.width * r.height >= 0.85 * VW * VH) return;
      out.push({ id: kind + ':' + id, key, x: (r.left + r.right) / 2, y: (r.top + r.bottom) / 2, w: r.width, h: r.height, op: o, vis: (x1 - x0) * (y1 - y0) });
    };
    for (const el of document.body.querySelectorAll('*')) {
      const tag = el.tagName.toLowerCase();
      if (tag === 'script' || tag === 'style' || tag === 'link' || (tag !== 'svg' && el.closest('svg'))) continue;
      let kind = null, key = '';
      if (tag === 'img' || tag === 'video') { kind = 'img'; key = fold(el.currentSrc || el.src); }
      else if (tag === 'canvas') kind = 'canvas';
      else if (tag === 'svg') kind = 'svg';
      else {
        let own = ''; for (const n of el.childNodes) if (n.nodeType === 3) own += n.textContent;
        if (own.trim()) { kind = 'text'; key = own.trim().slice(0, 40); }
        else { const cs = getComputedStyle(el), bg = cs.backgroundColor;
          if ((bg && bg !== 'rgba(0, 0, 0, 0)') || cs.backgroundImage !== 'none' || parseFloat(cs.borderTopWidth) > 0) kind = 'box'; }
      }
      if (!kind) continue;
      add(pathOf(el), key, el.getBoundingClientRect(), op(el), kind);
    }
    return out;
  };
})();
"""

SAMPLE_OWN = "async (t) => { await window.__clock(t); return window.__frames(t) || []; }"
SAMPLE_AUTO = "async (t) => { await window.__clock(t); return window.__ltScan(); }"

SHORT = lambda i: (i.split(':', 1)[0] + ':' + i.split('>')[-1][:34])


def url(comp):
    return comp if comp.startswith(("file://", "http://", "https://")) else "file://" + os.path.abspath(comp)


async def collect_page(pg, comp, fps=30, t0=0.0, t1=None, query=""):
    await pg.goto(url(comp) + query)
    await pg.evaluate("window.__ready")
    meta = await pg.evaluate("({m: window.__meta || {}, beats: window.__beats || null, own: typeof window.__frames === 'function'})")
    dur = float(t1 if t1 is not None else meta["m"].get("dur", 15))
    n = max(1, int(round((dur - t0) * fps)))
    fn = SAMPLE_OWN if meta["own"] else SAMPLE_AUTO
    samples, failed = [], []
    for i in range(n + 1):
        t = round(t0 + i / fps, 6)
        try:
            items = await pg.evaluate(fn, t)
            samples.append((t, [{**it, "vis": it.get("vis") or it["w"] * it["h"]} for it in items]))
        except Exception as e:
            failed.append((t, str(e).splitlines()[0][:120]))
            samples.append((t, [] if meta["own"] else await pg.evaluate("window.__ltScan()")))
    return {"comp": comp, "meta": meta["m"], "beats": meta["beats"], "fps": fps, "dur": dur,
            "own": meta["own"], "samples": samples, "failed": failed}


async def collect(comp, fps=30, t0=0.0, t1=None, width=1920, height=1080):
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={"width": width, "height": height})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.add_init_script(AUTO_JS)
        res = await collect_page(pg, comp, fps, t0, t1)
        res.update(W=width, H=height, errors=errs)
        await b.close()
    return res


# ── continuity ─────────────────────────────────────────────────────────────
def weight(it, area):
    return (it.get("vis") or it["w"] * it["h"]) * it["op"] / area


def jaccard(A, B, area):
    inter = union = 0.0
    for k in set(A) | set(B):
        wa = weight(A[k], area) if k in A else 0.0
        wb = weight(B[k], area) if k in B else 0.0
        if k in A and k in B and A[k]["key"] == B[k]["key"]:
            inter += min(wa, wb); union += max(wa, wb)
        else:
            union += wa + wb
    return inter / union if union > 0 else 1.0


def continuity(res, dt=0.4, j_max=0.2, cut_j=0.3, min_content=0.004, imgs=None):
    W, H, fps, dur = res["W"], res["H"], res["fps"], res["dur"]
    area, diag = float(W * H), math.hypot(W, H)
    S = [{it["id"]: it for it in items} for _, items in res["samples"]]
    content = [sum(weight(it, area) for it in s.values()) for s in S]
    lag, bridge, n = max(1, int(round(dt * fps))), int(1.5 * fps), len(S)

    cuts = [i for i in range(n - 1) if content[i] >= min_content and content[i + 1] >= min_content and jaccard(S[i], S[i + 1], area) < cut_j]
    bursts, group = [], []
    for i in cuts:
        if group and (i - group[-1]) / fps > 0.6:
            if len(group) >= 3: bursts.append((group[0] / fps - 0.25, group[-1] / fps + 0.25))
            group = []
        group.append(i)
    if len(group) >= 3: bursts.append((group[0] / fps - 0.25, group[-1] / fps + 0.25))

    # boundaries: declared beats when the page has them, replacement windows otherwise
    beats = res.get("beats")
    events = []
    if beats:
        for b in beats:
            events.append({"t": float(b["t"]), "carry": b.get("carry"), "hard": bool(b.get("hard")), "note": b.get("note", ""), "J": None})
    else:
        for i in range(n - lag):
            if content[i] < min_content: continue
            j = i + lag
            while j < n - 1 and content[j] < min_content and j - i < bridge: j += 1
            if content[j] < min_content: continue
            J = jaccard(S[i], S[j], area)
            if J >= j_max: continue
            if events and i <= events[-1]["_j"]:
                ev = events[-1]; ev["_j"] = j
                if J < ev["J"]: ev.update(_i=i, J=J)
            else:
                events.append({"_i": i, "_j": j, "J": J, "carry": None, "hard": False, "note": ""})
    for ev in events:
        if "_i" in ev: ev["t"] = round((ev["_i"] + ev["_j"]) / 2 / fps, 2)

    declared = [float(c) for c in (res["meta"].get("cuts") or [])]
    for ev in events:
        i = max(0, min(n - 1, int(round((ev["t"] - dt / 2) * fps))))
        j = max(0, min(n - 1, int(round((ev["t"] + dt / 2) * fps))))
        A, B = S[i], S[j]
        if ev["J"] is None: ev["J"] = round(jaccard(A, B, area), 3)
        strong, weak = [], []
        for k in set(A) & set(B):
            a, b = A[k], B[k]
            if min(a["op"], b["op"]) < 0.15: continue
            move = math.hypot(b["x"] - a["x"], b["y"] - a["y"]) / diag
            scale = abs(math.log(math.sqrt(max(b["w"] * b["h"], 1)) / math.sqrt(max(a["w"] * a["h"], 1))))
            big = min(a["vis"], b["vis"]) / area
            if move >= 0.02 or scale >= 0.1: strong.append((max(move, scale), k))
            elif big >= 0.03 and a["key"] == b["key"]: weak.append((big, k))
        ev["carriers"] = [SHORT(k) for _, k in sorted(strong, reverse=True)[:3]]
        ev["anchors"] = [SHORT(k) for _, k in sorted(weak, reverse=True)[:2]]
        ev["_i"], ev["_j"] = i, j
        # a declared carry must itself be one of the movers, and its pixels must change
        ok, px = True, None
        if ev["carry"]:
            ids = {k for _, k in strong}
            named = [k for k in ids if ev["carry"] in k]
            ok = bool(named)
            if ok and imgs and ev["t"] in imgs:
                box_a, box_b = A.get(named[0]), B.get(named[0])
                a_img, b_img = imgs[ev["t"]]
                if box_a and box_b:
                    x0 = max(0, int(min(box_a["x"] - box_a["w"] / 2, box_b["x"] - box_b["w"] / 2)))
                    y0 = max(0, int(min(box_a["y"] - box_a["h"] / 2, box_b["y"] - box_b["h"] / 2)))
                    x1 = min(W, int(max(box_a["x"] + box_a["w"] / 2, box_b["x"] + box_b["w"] / 2)))
                    y1 = min(H, int(max(box_a["y"] + box_a["h"] / 2, box_b["y"] + box_b["h"] / 2)))
                    if x1 - x0 >= 4 and y1 - y0 >= 4:
                        ok = float(np.abs(a_img[y0:y1, x0:x1].astype(np.int16) - b_img[y0:y1, x0:x1].astype(np.int16)).mean()) > 2.5
                        px = "changed" if ok else "identical"
        if px: ev["pixels"] = px
        ev["kind"] = "carried" if (strong and ok) else "anchored" if weak else "bare"
        tb = ev["t"]
        ev["exempt"] = ("hard" if ev["hard"] else "burst" if any(a0 <= tb <= a1 for a0, a1 in bursts)
                        else "end" if tb >= dur - 1.2 else "declared" if any(abs(tb - c) <= 0.25 for c in declared) else "")
        top = lambda s: [SHORT(k) for k, _ in sorted(s.items(), key=lambda kv: -weight(kv[1], area))[:2]]
        ev["before"], ev["after"] = top(A), top(B)
        if ev["carry"] and not ok: ev["note"] = (ev["note"] + " carry did not move").strip()
    considered = [e for e in events if not e["exempt"]]
    score = 1.0 if not considered else sum(1.0 if e["kind"] == "carried" else 0.5 if e["kind"] == "anchored" else 0.0 for e in considered) / len(considered)
    return {"score": round(score, 2), "events": events, "considered": len(considered), "bare": sum(e["kind"] == "bare" for e in considered),
            "cuts": len(cuts), "bursts": [(round(a, 2), round(b, 2)) for a, b in bursts]}


# ── curves ─────────────────────────────────────────────────────────────────
def moves_of(track, fps, W, vmin=0.8, min_path=30.0, min_steps=4, gap=2):
    runs, cur = [], []
    for i in sorted(track):
        if track[i]["op"] < 0.15 or (cur and i != cur[-1] + 1):
            if cur: runs.append(cur)
            cur = [] if track[i]["op"] < 0.15 else [i]
            continue
        cur.append(i)
    if cur: runs.append(cur)
    norm, out = 1920.0 / W, []
    for run in runs:
        if len(run) < min_steps + 1: continue
        xs = np.array([track[i]["x"] for i in run], float)
        ys = np.array([track[i]["y"] for i in run], float)
        ds = np.array([math.sqrt(max(track[i]["w"] * track[i]["h"], 1.0)) for i in run], float)
        step = (np.hypot(np.diff(xs), np.diff(ys)) + 0.5 * np.abs(np.diff(ds))) * norm
        for k in range(len(step)):
            prev = step[k - 1] if k > 0 else 0.0
            nxt = step[k + 1] if k + 1 < len(step) else 0.0
            if step[k] > 60 and prev < 0.1 * step[k] and nxt < 0.1 * step[k]: step[k] = 0.0
        active = step >= vmin
        k = 0
        while k < len(step):
            if not active[k]: k += 1; continue
            a = b = k
            while b < len(step):
                if active[b]: b += 1; continue
                nxt = b
                while nxt < len(step) and not active[nxt] and nxt - b < gap: nxt += 1
                if nxt < len(step) and active[nxt]: b = nxt; continue
                break
            k = b
            path = step[a:b]; L = float(path.sum())
            if b - a < min_steps or L < min_path: continue
            k80 = int(np.searchsorted(np.cumsum(path), 0.8 * L)) + 1
            net = np.array([xs[b] - xs[a], ys[b] - ys[a]]); nl = float(np.hypot(*net)); over = 0.0
            if nl > 20:
                u = net / nl
                proj = (xs[a:b + 1] - xs[a]) * u[0] + (ys[a:b + 1] - ys[a]) * u[1]
                over = max(0.0, float(proj.max() - proj[-1]) / nl)
            out.append({"t0": round(run[a] / fps, 3), "t1": round(run[b] / fps, 3), "path": round(L, 1), "t80": round(k80 / (b - a), 3),
                        "peak": round(float(path.max()), 1), "overshoot": round(over, 3)})
    return out


def curves(res, soft_t80=0.55):
    tracks = {}
    for i, (_, items) in enumerate(res["samples"]):
        for it in items: tracks.setdefault(it["id"], {})[i] = it
    moves = []
    for k, tr in tracks.items():
        for m in moves_of(tr, res["fps"], res["W"]):
            m["id"] = k; moves.append(m)
    moves.sort(key=lambda m: -m["path"])
    total = sum(m["path"] for m in moves)
    soft = sum(m["path"] for m in moves if m["t80"] >= soft_t80) / total if total else 0.0
    order = sorted(moves, key=lambda m: m["t80"])
    acc, med = 0.0, None
    for m in order:
        acc += m["path"]
        if med is None and acc >= total / 2: med = m["t80"]
    top = max(moves, key=lambda m: m["peak"]) if moves else None
    return {"moves": moves, "tracks": tracks, "peak": top["peak"] if top else 0.0,
            "peak_at": (SHORT(top["id"]), top["t0"]) if top else None, "soft_share": round(soft, 2), "t80_median": med, "count": len(moves)}


def framing(res):
    spec = (res.get("meta") or {}).get("mustStay") or {}
    W, H, out = res.get("W", 1920), res.get("H", 1080), {}
    for name, win in spec.items():
        t0, t1, whole = float(win[0]), float(win[1]), len(win) > 2 and win[2] == "whole"
        bad, seen = [], 0
        for t, items in res["samples"]:
            if not t0 <= t <= t1: continue
            b = next((it for it in items if name in it["id"] and it.get("op", 1) > 0), None)
            if b is None: continue
            seen += 1
            x0, y0, x1, y1 = b["x"] - b["w"] / 2, b["y"] - b["h"] / 2, b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
            off = (x0 < -0.5 or y0 < -0.5 or x1 > W + 0.5 or y1 > H + 0.5) if whole else (x1 < 0 or y1 < 0 or x0 > W or y0 > H)
            if off: bad.append(round(t, 3))
        out[name] = {"whole": whole, "window": [t0, t1], "samples": seen, "bad": bad}
    return out


def plot_speeds(res, cv, path, title="", top=8, size=(19.2, 3.2)):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fps, norm = res["fps"], 1920.0 / res["W"]
    ranked, seen = [], set()
    for m in cv["moves"]:
        if m["id"] not in seen:
            seen.add(m["id"]); ranked.append(m["id"])
        if len(ranked) >= top: break
    fig, ax = plt.subplots(figsize=size, dpi=100)
    fig.patch.set_facecolor("#f7f7f5"); ax.set_facecolor("#f7f7f5")
    for k in ranked:
        tr = cv["tracks"][k]; ii = sorted(tr); ts, vs = [], []
        for a, b in zip(ii, ii[1:]):
            if b != a + 1 or min(tr[a]["op"], tr[b]["op"]) < 0.15: ts.append(np.nan); vs.append(np.nan); continue
            d = math.hypot(tr[b]["x"] - tr[a]["x"], tr[b]["y"] - tr[a]["y"]) + 0.5 * abs(math.sqrt(max(tr[b]["w"] * tr[b]["h"], 1)) - math.sqrt(max(tr[a]["w"] * tr[a]["h"], 1)))
            ts.append(b / fps); vs.append(d * norm)
        ax.plot(ts, vs, lw=1.6, label=SHORT(k))
    for m in cv["moves"][:6]:
        ax.annotate(f"t80 {m['t80']:.2f}", (m["t0"], m["peak"]), fontsize=8, color="#555", xytext=(2, 2), textcoords="offset points")
    ax.set_xlim(0, res["dur"]); ax.set_ylabel(f"px / frame @{fps}"); ax.set_xlabel("s")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
    if title: ax.set_title(title, loc="left", fontsize=10)
    fig.tight_layout(); fig.savefig(path, facecolor=fig.get_facecolor()); plt.close(fig)


def report(res, ct, cv):
    print(f"\n{os.path.basename(res['comp'])} — {len(res['samples'])} samples at {res['fps']} fps, {len(cv['tracks'])} layers"
          f" ({'__frames' if res['own'] else 'DOM scan'})" + (f"; page errors: {'; '.join(res['errors'][:2])}" if res.get("errors") else ""))
    if res.get("failed"):
        print(f"  !! __clock threw at {len(res['failed'])} samples, first t={res['failed'][0][0]}: {res['failed'][0][1]}")
    kinds = [e["kind"] for e in ct["events"] if not e["exempt"]]
    print(f"continuity  score {ct['score']:.2f} — {ct['considered']} boundaries: {kinds.count('carried')} carried, "
          f"{kinds.count('anchored')} anchored, {kinds.count('bare')} bare; {len(ct['events']) - ct['considered']} exempt; cuts {ct['cuts']}, bursts {ct['bursts']}")
    for e in ct["events"]:
        via = ", ".join(e["carriers"] or e["anchors"]) or "—"
        flag = f" [{e['pixels']}]" if e.get("pixels") else ""
        print(f"  t={e['t']:6.2f}  J {e['J']:.2f}  {(e['exempt'] or e['kind']):9} via {via:44.44}{flag}  before {', '.join(e['before'])} | after {', '.join(e['after'])}"
              + (f"  · {e['note']}" if e.get("note") else ""))
    if cv["peak_at"]:
        print(f"curves      peak {cv['peak']:.0f} px/frame ({cv['peak_at'][0]} at {cv['peak_at'][1]:.2f} s) · soft travel {cv['soft_share'] * 100:.0f} % · median t80 {cv['t80_median']:.2f} · {cv['count']} moves")
        for m in cv["moves"][:8]:
            print(f"  {SHORT(m['id']):36.36} {m['t0']:6.2f}–{m['t1']:5.2f} s  path {m['path']:6.0f}  t80 {m['t80']:.2f}  peak {m['peak']:5.0f}  over {m['overshoot']:.2f}")
    else:
        print("curves      nothing moved")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("comp"); ap.add_argument("--fps", type=int, default=30); ap.add_argument("--out", default=None)
    ap.add_argument("--from", dest="t0", type=float, default=0.0); ap.add_argument("--to", dest="t1", type=float, default=None)
    ap.add_argument("--width", type=int, default=1920); ap.add_argument("--height", type=int, default=1080)
    a = ap.parse_args()
    res = await collect(a.comp, a.fps, a.t0, a.t1, a.width, a.height)

    # boundary screenshots, only for declared carries: a layer that reports a new box must also
    # change its pixels, or it is a label that teleported
    imgs = {}
    if res.get("beats"):
        from PIL import Image
        async with async_playwright() as p:
            b = await p.chromium.launch()
            pg = await b.new_page(viewport={"width": res["W"], "height": res["H"]})
            await pg.goto(url(a.comp) + "?hud=1")
            await pg.evaluate("window.__ready")
            for ev in res["beats"]:
                pair = []
                for s in (-0.2, 0.2):
                    await pg.evaluate(f"window.__clock({round(float(ev['t']) + s, 3)})")
                    pair.append(np.asarray(Image.open(io.BytesIO(await pg.screenshot())).convert("L")))
                imgs[float(ev["t"])] = pair
            await b.close()

    ct = continuity(res, imgs=imgs)
    cv = curves(res)
    report(res, ct, cv)
    for k, v in framing(res).items():
        print(f"framing  {k}: {'wholly ' if v['whole'] else ''}in frame {v['window'][0]:g}–{v['window'][1]:g} s — off at {len(v['bad'])} of {v['samples']} samples{' ' + str(v['bad'][:8]) if v['bad'] else ''}")
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        slim = {k: [[i / res["fps"], round(v["x"], 1), round(v["y"], 1), round(v["w"], 1), round(v["h"], 1), round(v["op"], 3)] for i, v in sorted(tr.items())] for k, tr in cv["tracks"].items()}
        json.dump({"fps": res["fps"], "dur": res["dur"], "continuity": ct, "moves": cv["moves"], "tracks": slim}, open(os.path.join(a.out, "tracks.json"), "w"))
        plot_speeds(res, cv, os.path.join(a.out, "curves.png"), title=os.path.basename(a.comp))
        print(f"\nwrote {a.out}/tracks.json and {a.out}/curves.png")


if __name__ == "__main__":
    asyncio.run(main())
