# Camera

The camera is operated, not keyframed. Keys say where each beat needs to be framed; the feel comes from how they are placed and from the hand layered on top.

## Keys

```js
const cam = LT.rig([
  { t: 0.0, x: 960, y: 540, zoom: 1.06 },
  { t: 1.2, x: 940, y: 520, zoom: 1.03, curve: LT.C.glide },
  { t: 3.2, x: 900, y: 500, zoom: 1.05 },
  { t: 3.2, x: 900, y: 500, zoom: 1.05 },   // duplicate: a hold, float off
], { W, H, float: 0.6, hits: [[4.4, 10, 9]] });
```

- `x,y` is the **world point held at the frame centre**. To frame a subject at `(800, 300)`, key `x:800, y:300`.
- Place the key **on the landing point before a snap**, on the curve of the move. A camera that starts chasing after the snap loses the subject — `mustStay` catches it.
- Default curve `glide` (.63). Use `whip` for a deliberate whip between two framings, `swell` inside slow travels.
- Zoom moves in log space, so 1× → 4× reads as one speed whatever the distance.
- `float` is a slow two-sine hand (default .6 px). It is zeroed automatically inside a hold — a held frame must repeat itself or the shutter never skips.
- `hits` shake the camera from the impact time: amplitude in px, decay per second. Small: 8–13 px with decay 8–10.

## Depth

Layers live in depth wrappers: `LTX.add(id, el, {depth: 0.9})`. Depth 0 is the focus plane; positive is farther (moves less), negative nearer (moves more). Depth-of-field blur via `LT.bokeh(depth, focus)` only where the subject is clearly nearer or farther.

An empty ground gives a camera nothing to read against. Draw `LT.grid(cam, {depth: 1.2})` — dots that stay 1–2 px on screen — or a parallax layer behind.

## One camera, no cuts

`__meta.cuts` may declare hard cuts; the camera does not have to cut with them, and better when it does not. The whip through a cut is one of the strongest moves available: `LT.whip` on the camera plus a `dive` into the next surface.

## `mustStay`

```js
window.__meta.mustStay = { 'rule': [1.05, 10.4, 'whole'], 'mark': [6.5, 12, 'whole'] };
```

The judge fails a frame inside the window where that layer is entirely off frame (`whole`: not wholly inside). Ids are layer ids. Declare the subject of the film for the range it must be visible — especially through snaps.

## Travel and the shutter

`LTX.travel(a, b, seek)` measures how far registered layers and the frame corners slide between two times. `shoot.py` sizes captures per frame to keep neighbours ~6 px apart, so a whip smears instead of stepping. A comp without `__travel` falls back to a fixed count, which strobes.

## Ground

The camera's stage is a surface: a colour field, a light, cloth, a lattice. Change it at a boundary the concept owns (the flood, the material flip) — never per beat, or the ground becomes a slideshow of its own.
