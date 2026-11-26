# Sound

One room, a handful of materials, fewer events than beats.

## Events

The comp owns the cues:

```js
window.__events = () => [
  { t: 1.15, kind: 'wood', gain: 0.9 },
  { t: 2.1, kind: 'tick', gain: 0.3, pan: -0.4 },
];
```

`sfx.py` places them. `kind` ∈ `air tick wood glass sub bubble riser`. `pan` −1…1 (constant power). `gain` 0–1.

Rules that keep it from sounding cheap:

- **Fewer events than beats.** A sound per element is the audio slideshow. One landing sound per beat, plus texture.
- **One material set per film.** A film of wood is wood, not wood then glass then bubble.
- **Silence is an event.** Leave the quiet stretch quiet; do not fill it.
- **Sub for weight, not for every hit.** One or two in a burst; the rest thin.
- **Texture under, not on top.** `air` at .3–.5 gain for movement, risers only into a hit.

## Room

Every event goes through the same synthetic impulse: sparse early reflections (5 taps inside 80 ms), then a 2.2 s decaying tail, band-limited. `sfx.py` does this already; a second room (extra reverb, delay) breaks the single space.

## Levels

- Master ≈ **−16 LUFS**, ceiling **−4 dBTP**, so the AAC mux stays under the judge's −3 dBFS peak.
- Events peak around −10, texture −20.
- The `judge.py` audio leg needs: peak ≤ −3, zero clipped samples, ≥ 15 % of 1/12 s windows below −40 dBFS.

## Music

Royalty-free by default (Pixabay Music, the YouTube Audio Library, Free Music Archive under a CC licence), with the source and licence kept next to the score. `sfx.py --music track.mp3` ducks the bed to 45 % under every hit. A commercial track only when the user supplies it and says so.

## What sounded cheap

- a raw sine pop on every event;
- the same tick at the same gain for every landing;
- reverb on the bed as well as the effects (two rooms);
- a riser longer than the thing it rises into;
- no silence anywhere, so the burst has nothing to break.
