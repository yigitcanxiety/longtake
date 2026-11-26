# hello-12s · one line is enough

A 12 s launch film for a fictional tool. The whole film is one rule.

**Concept.** The caret is the line, the line is the shelf, the shelf is the baseline, the baseline is the underline. One element walks the picture; nothing else is ever the subject. The look is `slate` — night instrument panel, bone type, one acid-lime signal — picked for the film, not carried from another.

**Why it is not a slideshow.** Every boundary is the rule moving: stretching, thickening, rising, snapping, dropping. The three cards exist only to be ridden by the shelf and then folded into ticks on the rule. The wordmark is written by letters falling onto the rule as it becomes its underline.

## Beat sheet

| t | beat | what moves | what is still | carry |
| --- | --- | --- | --- | --- |
| 0.00–0.38 | empty ground, far lattice | nothing | everything | — |
| 0.38 | caret draws | caret height spring | ground | — |
| 0.38–1.10 | types "one line is enough" | characters at 34 cps, caret | caret line | — |
| **1.32** | caret stretches into the rule | caret → 1420 px rule, y 470 → 588 | caption | **rule** |
| **1.90** | rule thickens into a shelf | h 3 → 5, y → 640 | ground | **rule** |
| **2.02** | three cards drop onto the shelf | cards, 0.17 s stagger, squash on contact | rule | **card0** |
| 2.30–4.30 | hold; shelf leans | cards ±0.02 rad, camera drift 1.05 → 1.075 | everything else | — |
| 4.40 | shelf rises to the baseline | x 300 → 250, ticks land on it | caption | — |
| **4.86** | cards fold into ticks | 300×190 → 26×6, staggered | line type | **card0** |
| 4.75–5.90 | "every beat is carried." rises word by word | four words, 0.26 s apart | rule, ticks | — |
| **6.72** | rule becomes the underline, letters drop | rule y 640 → 806, letters 0.045 s stagger | tagline | **rule** |
| 7.15 | tagline rises | one line | mark, rule | — |
| **8.00 / .18 / .36 / .54** | burst: no cuts / no fades / no slides / one take | hard cuts, camera tremor, underline snaps to each word's width | ground | **rule** (first), `hard` ×3 |
| 9.02 | back to the wordmark | underline snaps to the mark's width | letters | — |
| 9.25–10.45 | dead still | nothing | everything | — |
| 9.45 | credit rises | one line | mark | — |
| **10.95** | closing stroke | rule drops to 210 px at y 940 | mark, tagline, credit | **rule** |
| 11.35–12.00 | hold | nothing | everything | — |

## Numbers

```
probe   continuity 1.00 over 6 boundaries — 6 carried, 0 anchored, 0 bare; 5 exempt
curves  peak 202 px/frame @30 (hit, 8.03 s), soft travel 59 %, median t80 .71
judge   cadence PASS (CV .81) · rest PASS (65 %, 2.33 s) · burst PASS · audio PASS
        (−4.9 dBFS, 0 clipped, 28.7 % quiet) · continuity PASS · curves PASS · framing PASS
VERDICT PASS
```

## What failed first

v1 scored **0.43** with four bare boundaries and failed framing. `ruleBox()` composed its morphs with a helper that ignored its second argument, so the rule never actually thickened or rose: the beats were declared where nothing moved. The pixels check in the probe reported `identical` on every declared carry — the declaration was fine, the picture was not.

v2 moved the boundaries to the **middle** of each motion instead of its start (a ±0.2 s probe window around a move that begins at `t` sees nothing), fixed the composition, and dropped the type beats that had no survivor of their own: a word appearing mid-shot is not a boundary.

## Files

`comp.html` · `look.js` · `sfx.wav` (40 events, one room) · `hello.mp4` (1920×1080, 30 fps, 180° shutter) · `stills.png`
