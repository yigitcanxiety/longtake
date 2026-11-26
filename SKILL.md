---
name: longtake
description: Launch films, teasers and feature demos that never cut to the next slide — every beat is carried into the next, one operated camera, continuity measured by an oracle before a human watches. Use for a launch clip, a product teaser, a feature demo rebuilt from screenshots, or "my motion video reads like a slideshow".
---

# longtake

A film is a **seam**, not a stack of shots. This skill exists so the seam gets designed: at every boundary something on screen survives and visibly becomes the next beat, one camera holds the whole take, and an oracle scores the carry before anyone watches.

Three cases built it. One had perfect rhythm and was still rejected as a slideshow: every beat replaced the last. The fix was not faster cuts, it was **carry** — the character lands on the headline, the page grows out of its card, a stage opens from the character. Another had carry but a **still camera**, and was rejected for it: a camera that chases what each beat frames was accepted. The third was rejected as "nice artwork, no idea" until the idea was moved **into the art** instead of labelled beside it.

Everything below is ordered. Do not skip a step because the film looks simple.

## When

- Launch film, teaser, intro for an app, a page, a feature, a skill — yes.
- Narrated feature demo, 30–60 s, possibly in two languages — yes; rebuild the UI instead of recording it (`references/method.md`).
- A reference clip whose *feel* is wanted — yes, measure it first (§1).
- Long-form, talking heads, cutting existing footage — no.

## 1 · Measure the reference, if there is one

```bash
python3 tools/ref.py ref.mp4 --out ana/
```

Read `ana/energy.txt`: when it moves, where it cuts, how much is dead still, its median t80, its smear. A film built from memory comes out on a uniform cadence; a film built from the numbers does not. Keep the numbers where you can see them while writing the beat sheet.

## 2 · Three concepts, differing in their central idea

A concept is one sentence about the **picture**, not the product. Three that differ in that idea, not three stories in the same cards:

- one element transforms through every beat (a caret → rule → shelf → baseline → underline);
- one camera move through scale (inside a pixel → the whole page → back);
- a before/after split that breaks (slideshow left, carried right, until the right eats the left);
- a chain reaction (every beat is the collision that starts the next);
- a single surface that changes material (wet, frost, print, glow) under one continuous light;
- a typographic system where the layout itself is the actor.

For each: the hook frame, what survives every boundary, what the concept rules out, and **its look** — a preset from `tools/look.py list` (sheet: `python3 tools/look.py sheet`), a look from the product (`look.py from-shot`), or one written for this film. Show the three; the user picks. Never default to the skeleton's own story.

## 3 · Beat sheet: rhythm **and** carry

Write `t · beat · what moves · what is still · what carries into the next beat`. Commit it to the case `README.md` before composing.

**Rhythm.** Shot lengths vary by ≥ 4× (a 0.25 s word beside a 2.5 s hold). At least one stretch of dead picture and quiet sound ≥ 1 s. One story, not a catalogue. Small elements, big ground — this genre's frame is mostly empty.

**Carry.** Every section boundary names the layer that survives it and the motion it makes. A level change is not a carry. `window.__beats` carries the same list into the comp so the probe can check it:

```js
window.__beats = [{ t: 1.32, carry: 'rule', note: 'caret stretches into the rule' }];
```

Set `hard: true` only for a burst of hits and the end card. Those are the two legal cuts.

## 4 · Look, then compose

```bash
python3 tools/look.py apply <look> cases/<film>/comp.html
```

`look.js` writes `--ground --deep --card --line --mute --ink --accent --accent2` and the three faces. Write against the tokens and `var(--display)`, never a hex. It names any glyph a face lacks — fix the copy or pass `--cjk`.

Copy `templates/comp.html` next to the film and replace its beats. Keep its contract:

```
window.__meta = {dur, fps, w, h, cuts?, mustStay?}
window.__clock(t) → Promise      draw frame t; resolve after images decode
window.__frames() → [{id,key,x,y,w,h,op}]   registered layers, screen space, centres
window.__beats                    the carry list
window.__travel(a,b)              farthest screen travel between two times
window.__events() → [{t,kind,gain?,pan?}]
window.__ready
```

Register every visible layer through `LTX.add`; paint it through `LTX.set` — one place writes transforms, so the probe and the picture cannot disagree. Moves come from `lib/anim.js` by name (`LT.morph`, `LT.dive`, `LT.hit`); look up the curve's `t80` in `references/library.md` instead of inventing an ease.

Camera from `LT.rig(keys)`. Duplicate keys make a hold and silence the hand float. Declare `__meta.mustStay` for anything that must never leave the frame.

## 5 · Stills before motion, motion before polish

```bash
python3 tools/peek.py cases/<film>/comp.html --times 0.6,1.4,2.9,4.6,7.1 --out stills.png
python3 tools/probe.py cases/<film>/comp.html
```

Read every row of the probe. `bare` means the declared thing did not move — fix the beat or the move, not the declaration. Iterate until no considered boundary is bare and the peaks are on the moves you meant.

## 6 · Render, sound, verdict

```bash
python3 tools/sfx.py --comp comp.html --out sfx.wav            # fewer events than beats
python3 tools/shoot.py comp.html --out draft.mp4 --sfx sfx.wav # 1080p30, shutter on
python3 tools/judge.py draft.mp4 --comp comp.html
```

Tell the user the time estimate before a long render (~2 min for 12 s at 1080p30 on eight workers; 4K60 is ~10×). Only after a PASS and the user's acceptance:

```bash
python3 tools/shoot.py comp.html --out film.mp4 --final --sfx sfx.wav
```

## Hard rules

- **Never default to the skeleton's story.** Three concepts, user picks (§2).
- **Never carry the last film's look.** Palette, stage, camera grammar, transitions chosen in §2 by name.
- **Never replace a beat — carry it.** A boundary with nothing surviving is a slide, however good the rhythm. Exceptions: the hit burst, the end card.
- **Never cut on a metronome.** Equal shot lengths are slides.
- **Never let the frame be always in motion.** Rests are what make the bursts land; a third of a measured reference is dead still.
- **Small elements, big ground.** Full-bleed is one calm hold, not the default.
- **The cause must be visible.** The hand, or the concept's own subject. A page reacting to nothing is a screensaver.
- **Curves by t80, from the library.** One hand-rolled smoothstep everywhere flattens every move into the same soft S.
- **Fast moves need the shutter.** Over 80 px/frame without blur strobes into copies; `shoot.py` defaults to 180°.
- **A camera that chases, and never loses the subject.** Key the landing point before a snap; declare `mustStay`.
- **Drafts at 1080p30.** No 4K60 of a rejected cut.
- **No particles, no confetti.** The type lands with squash, not dust.
- **One material set, one room, fewer events than beats.** A synth tone per event is the audio slideshow.
- **Everything deterministic.** Two clocks of the same t give the same frame; sims are precomputed from a seed.
- **Edit the comp, not the frame.** If a shot only works at one scale, the layout is wrong.
- **Music royalty-free by default**, sourced and licensed next to the score; a commercial track only when the user supplies it.

## Files

`references/method.md` (order, contracts, replica technique) · `references/beats.md` (rhythm and carry numbers) · `references/library.md` (every move) · `references/camera.md` (operator grammar) · `references/sound.md` (palette, room, levels) · `references/ref-reading.md` (reading a reference) · `cases/hello-12s/` (a finished film and its numbers).
