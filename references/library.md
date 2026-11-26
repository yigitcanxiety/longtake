# Library

Every function is a pure function of time returning numbers. Nothing touches the DOM; `LTX.set` applies. Read the curve table before picking an ease: `t80` is the share of the move spent before 80 % of the distance — under .35 snaps and lands, .55–.7 is a soft S, and using one soft S everywhere is the "hand-rolled transition" look.

`node tools/motion_test.js` asserts these numbers.

## Curves

| curve | t80 | use |
| --- | --- | --- |
| `C.linear` | .80 | belts, a constant sweep |
| `C.swell` | .70 | sine in-out; a camera leg that starts at rest |
| `C.soft` | .71 | smoothstep, the fallback when nothing else fits |
| `C.drift` | .67 | long travels that should feel unhurried |
| `C.glide` | .63 | camera legs; leaves and lands at rest |
| `C.deep` | .58 | heavy objects, a big panel |
| `C.land` | .55 | a fall that decelerates |
| `C.fall` | .42 | gravity-accented drop |
| `C.drop` | .33 | gravity, without overshoot |
| `C.snap` | .23 | the standard landing: fast out, settles |
| `C.suck` | .97 | leaves slowly then accelerates |
| `C.whip` | .57 | camera whip, in-out with a fast middle |
| `C.circle` | .40 | a quick reveal |
| `C.overshoot` | .23 | a move that passes its target once |

`LT.bez(x1,y1,x2,y2)` builds a curve from a spec; `LT.t80(curve)` measures one.

## Scalars

`clamp(v,lo,hi)` · `mix(a,b,k)` · `prog(t,t0,t1)` · `sstep(a,b,x)` · `s5(a,b,x)` · `LT.spring(tau,{bounce,omega})` (0 = critical, .35 bouncy) · `LT.springVel` · `LT.pulse(tau,{decay,freq})` · `LT.settle` · `LT.spline(knots,t)` · `LT.rng(seed)` · `LT.track(want,{...})` — a spring chasing a target function, sampled.

## Entrances

| function | returns | notes |
| --- | --- | --- |
| `rise(t,t0,{dist,s0,ds,lead})` | `{k,op,y,s}` | a word landing; opacity leads the spring |
| `drop(t,t0,i,{stagger,dist,squash})` | `{k,sq,op,y,sx,sy}` | wordmark letter i; squash comes from velocity |
| `pop(t,t0,{from,s0})` | `{k,op,s,y}` | cards |
| `maskUp(t,t0,i,{h})` | `{k,y,on}` | line rise behind a clip; `y` is a fraction of the line height |
| `typeIn(t,t0,text,{cps})` | `{shown,caret,done}` | caret blinks after the last character |
| `checkIn(t,tl,{bounce})` | `{on,k,s}` | a tick |
| `flyBy(t,t0,hold,{...})` | `{live,x,ry,s,blur,op}` | panel through the frame, tilted; blur on entry and exit |
| `peel(t,t1,{dist,blur})` | `{k,op,y,blur,s}` | the exit; pair with the entrance |

A landing needs a `hit` on whatever it lands on, or it reads as a fade-in.

## Carries

| function | returns | boundary |
| --- | --- | --- |
| `morph(t,t0,t1,A,B,{curve,axis})` | `{k,x,y,w,h,r,cx,cy}` | become — rect A is rect B |
| `bloom(t,t0,t1,cx,cy,{r0})` | `{k,cx,cy,r,full}` | open — a stage from the subject |
| `dive(t,t0,t1,box,{fit})` | `{k,s,tx,ty,matrix}` | enter — camera into a surface |
| `arc(t,t0,t1,from,to,{height})` | `{k,x,y}` | ride — the subject hops |
| `fold(t,t0,t1,i,n,from,to,{stagger,lift})` | `{k,x,y,rot}` | gather |
| `shuffle(t,times,{amp,dur,lag})` | `{shift,at,wobble,rot,sx,sy,drag}` | an elastic rail |
| `stamp(t,t0,t1,{r,turns})` | `{k,r,rot}` | the lockup seal |
| `flip(t,list)` | `{text,i}` | staccato hits on hard cuts |
| `reveal(t,t0,t1,{from})` | `{k,clip}` | wipe; feed `clip` to `clip-path` |

`morph` with `axis:'y'` changes only y and height (a bar thickening); `axis:'x'` only x and width.

## Contact

| function | returns | use |
| --- | --- | --- |
| `hit(t,th,{sx,sy})` | `{r,sx,sy}` | the ring of a landing; squash the lander, shake the camera |
| `cleave(t,th,x,cx,{spread,bounce})` | `{dx,dy,rot}` | a headline split by an impact at `cx` |
| `push(t,tc,{depth,flash})` | `{s,sq,down,active}` | a press; `active` is the colour flash |
| `pointer(t,path,clicks,{down})` | `{x,y,s}` | the hand, from a spline and its clicks |
| `stretch(vx,vy,{k})` | `{speed,ang,sx,sy}` | stretch along travel, thin across it |
| `sims.pull / chase / wobble / rope` | `{st,at(t)}` | pre-simulated mechanisms inside a card; `at` samples |

Sims run once at 240 Hz from `card.t` to `card.out + .3`; they take the same `hand` function the pointer is drawn from, so cause and effect agree.

## Camera

`rig(keys,{curve,float,hits,W,H})` → `t → {x,y,zoom,rot}`. Keys `{t,x,y,zoom,rot,curve}`; `x,y` is the world point at frame centre; zoom interpolates in log space; a duplicate key holds and drops the float. `hits` = `[[t, amp, decay]]` for impact tremor.

`plane(cam,{depth})` → matrix for a depth wrapper (0 = focus; > 0 farther). `bokeh(depth,focus)` → blur px. `whip(t,t0,dur,dist)` → a camera move. `tremor(t,th,{amp})` → an independent shake. `grid(cam,{depth,spacing})` → a far lattice (a camera needs something farther back to slide against). `project / unproject / boxTravel / camTravel`.

## Fluid

`light(level)` → ellipse for a ground of light. `rings(t,t0,{n})` → a draining flood. `cloth(tau,seed,ramp)` → RGBA for a tiny canvas, drawn up blurred; `cloth.ramps` = `slate`, `ember`, `moss`. `belt({dur,speed,stop})` → `at(t) → {x,clock}`, a belt that slows its own contents.

## Painting

`LTX.mount(stage)` · `.add(id, el, {key, depth, w, h})` · `.set(id, pose)` · `.cam(cam)` · `.frames()` · `.travel(a,b,seek)` · `.hide(id)`.

Pose fields: `x y w h s sx sy rot op blur ox oy clip display`. `w/h` are layout, the rest compose as translate → rotate → scale about `ox,oy` (default top-left). `op ≤ .002` also sets `display:none`.
