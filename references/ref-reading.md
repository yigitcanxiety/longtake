# Reading a reference

`tools/ref.py ref.mp4 --out ana/` gives numbers, not a description. Read them before writing a beat.

## The energy map

Rows are six horizontal bands, top of the frame first; columns are ¼ s; the glyph is mean absolute frame difference in that cell (`.` still … `#` hard). Read it for three things:

1. **Where the rests are.** Empty columns are holds. Their length is the film's rest budget — match it, don't shorten it to "keep it moving".
2. **Where the columns fill in bursts.** Consecutive `#` columns are hits. Count them; a burst is 3+ inside 1.5 s.
3. **Which bands move.** Motion only in the middle band means small subjects on a big ground. Motion across all bands means full-bleed or a camera move.

## The numbers

```
still 34.0% · low 61.2% · longest quiet 1.10 s
cuts 7 at [1.98, 2.11, 2.2, 5.44, 5.51, 5.6, 8.02]
motion: median t80 0.34 · smear 0.71
```

- **still / low** — rest budget. Under 25 % still is a busy film; over 55 % is a slow one. Copy the neighbourhood of the reference, not the extreme.
- **longest quiet** — the longest stretch with no motion at all. Your film needs at least one as long.
- **cuts** — when the reference cuts at all, and whether they come in bursts. If it has none, yours needs none.
- **median t80** — how its moves ease. ~.25–.35 is snappy, ~.7 is soft. Pick curves near it.
- **smear** — the width of moving blobs. Under .78 the reference was shot with a shutter; use `shoot.py`'s default. Over .78 means sharp stills and your blur may look wrong for that feel (compare before deciding).

## Contact sheet

`ana/sheet.png` is cut midpoints. Look for what the reference does *at* a cut: whip, dissolve, an object crossing, a colour swap. That is its carry grammar — copy the grammar, not the subject.

## Scale

Reference resolution does not matter (analysis runs at 320 px wide); framing does. Note how much of the frame the subject fills — if it is 6 %, a full-bleed remake will read as a different genre.

## After measuring

Write the numbers at the top of the beat sheet. They are the only defence against building from memory, which is how a film comes out on a uniform cadence — twice, in the case that produced this file.
