# Method

The order is the method. Skipping a step is how a cut ends up a slideshow with good craft.

## 1 · Reference first

`tools/ref.py` turns a clip into an energy map, a cut list, a stillness ratio, a median t80 and a smear width. The energy map says *when* motion happens; `motion:` says *how* it eases and whether it was shot with a shutter. Both get written on the beat sheet. `references/ref-reading.md`.

## 2 · Concepts, then look

Three concepts that differ in their central idea, each with a hook frame, its carry, what it rules out, and a named look. The user picks. A concept without a look gets one picked there, not left to the comp's defaults.

## 3 · Beat sheet

Every row is `t · beat · what moves · what is still · what carries`. Written to the case README, and mirrored into `window.__beats` so the probe can hold the comp to it. `references/beats.md`.

## 4 · The comp

One HTML file, 1920×1080 authored, every frame a pure function of `t`.

### Contract

| name | type | meaning |
| --- | --- | --- |
| `window.__meta` | object | `{dur, fps, w, h, cuts?, mustStay?}`; `cuts` are declared hard cuts (exempt from continuity) |
| `window.__clock(t)` | `async t →` | draws frame t; resolves only after that frame's images are decoded |
| `window.__frames()` | `→ [{id,key,x,y,w,h,op}]` | visible registered layers, **screen space, x/y are centres** — `LTX.frames()` |
| `window.__beats` | `[{t, carry, hard?, note?}]` | the carry list from §3 |
| `window.__travel(a,b)` | `async → px` | farthest anything travels between two times; sizes the shutter |
| `window.__events()` | `→ [{t,kind,gain?,pan?}]` | sound cues |
| `window.__ready` | `Promise` | fonts, measurement, first frame |

`LTX.mount(stage)` gives `add`, `set`, `cam`, `frames`, `travel`. **Only `set` writes transforms.** A layer painted outside `set` is invisible to the probe and will lie about continuity.

### Determinism

`__clock(t)` twice must give the same picture: the shutter depends on it. No `Math.random()` on the clock path — `LT.rng(seed)` at setup, sims precomputed once (`LT.sims.*` return a sampler). Camera output is quantised below what shows, so a settled hold repeats its frame and the shutter is skipped.

### Camera

`LT.rig(keys)` → `t → cam`. Duplicate keys hold; the hand float drops to zero inside a hold. Depth wrappers (`LTX.add(..., {depth})`) give parallax; the focus plane is depth 0. Declare `__meta.mustStay = {id: [t0, t1, 'whole']}` for anything that must not leave the frame — the judge fails it if it does.

### Content

- Real product UI: rebuild it in HTML from screenshots on a `UIK.plane`, then move the camera — never screen-record a page for a film (`references/method.md` §replica).
- Footage is the exception: `tools/capture.py` records a real page in real time with an action marker, and the comp draws the pointer back from the path file, because the viewer must see the cause.

## 5 · The replica (feature demos)

When the film walks through features, or has a voice, the UI is rebuilt, not recorded:

1. Screenshot or record reference takes at the size you will show.
2. Rebuild each screen in HTML inside its own pixel frame on a `UIK.plane(stage, {w, h, at, scale})`; the plane is a depth wrapper so the camera can fly into it at any zoom.
3. Every string lives in one table; `UIK.strings(table, lang)` reads `?lang=`. A second language never forks the comp.
4. Every state is written by one `set(state)`, so a frame is a function of t alone.
5. Highlights come from the DOM (`UIK.rect`), not from magic numbers.
6. Narration: word times warp onto the authored timeline with `UIK.warp(knots)`; subtitles via `UIK.subs`. Check the source language renders identically after adding a translation.

Legibility: `UIK.legible(plane, zoom)` is screen px per design px. Below ~11 px a label is decoration, not information — either the camera closes in or the label goes.

## 6 · Exit criteria

Probe: no considered boundary `bare`, peaks where you meant them, `mustStay` clean. Judge: PASS. Then the user watches. 4K60 only after that.
