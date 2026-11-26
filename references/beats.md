# Beats: rhythm and carry

Two numbers decide a beat sheet. Rhythm is how long a shot lasts; carry is what survives it. A cut with perfect rhythm and no carry is still a slideshow.

## Rhythm

- Shot lengths vary by **≥ 4×**: a .25 s word next to a 2.5 s hold. `judge.py --shots` fails a cadence CV under .25.
- **≥ 25 % of the film dead still** and one stretch ≥ 1 s of dead picture and quiet sound.
- One story, the concept's. Three cards about three features are a catalogue.
- **Small elements, big ground.** A 70 % empty frame is the genre. Full-bleed is a single calm hold.
- Bursts are 3+ hits inside 1.5 s, on hard cuts. They only land because the film was still before them.

Holds are written as duplicate camera keys and identical poses. If a hold still shows motion, it is not a hold and the burst after it has nothing to land against.

## Carry

At every section boundary:

| grammar | what it looks like | tool |
| --- | --- | --- |
| **become** | the shape is the next shape: caret → rule, chip → card, card → page | `LT.morph`, `LT.stretchTo` |
| **open** | a stage grows out of the subject until it is the frame | `LT.bloom` |
| **enter** | the camera pushes into a surface and its inside is the next scene | `LT.dive` |
| **ride** | the subject travels along the thing that survives | `LT.arc`, `LT.fold`, `LT.shuffle` |
| **gather** | the cast folds into the lockup | `LT.fold` → `LT.stamp` |
| **fall through** | the same glyph or object drops into the next layout | `LT.drop`, `LT.maskUp` |

A boundary without one of these is a cut. Cuts are legal in a burst and at the end card, and nowhere else — `hard: true` in `__beats` is the only way to say so.

## Declaring

```js
window.__beats = [
  { t: 1.32, carry: 'rule', note: 'the caret stretches into the rule' },
  { t: 8.18, carry: 'rule', hard: true, note: 'second hit' },
];
```

`carry` is a **layer id substring**, not a description. The probe looks for a surviving layer matching it, checks it moved ≥ 2 % of the diagonal or scaled ≥ 10 %, and compares the pixels in its box across the boundary. A declaration that does not move is `bare`, however good the note reads.

Put the boundary in the **middle** of the motion, not at its start, and not on the frame a layer appears (the probe ignores anything under 15 % opacity on either side): a ±0.2 s window around a move that only begins at `t` sees nothing move and fails. If a beat's motion is shorter than 0.3 s, either lengthen it or move the boundary to a beat that can carry.

## Failure signatures

| symptom | cause | fix |
| --- | --- | --- |
| probe: several `bare` at regular intervals | beats were written as scenes | give each boundary one surviving layer and a visible motion |
| cards slide in from off frame, one per feature | cards are the unit, not the frame | let one card become the next thing instead of the next card |
| judge: cadence CV < .25 | every beat is ~1 s | cut one beat, hold another 2.5 s, make one .25 s |
| judge: rest < 25 % | the camera floats through everything | duplicate keys, freeze the subject, re-time the burst |
| every move is soft | one smootherstep everywhere | pick curves by t80; snaps land |
| peak > 80 px/frame and strobing | no shutter | `shoot.py` default 180°, tighten `--gap` |

## End card

Legal cut, one clean hold, the mark and at most one line. It is the only place a full sentence may sit still.
