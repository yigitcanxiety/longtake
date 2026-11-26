#!/usr/bin/env node
/* motion_test.js — the library's numbers, asserted. `node tools/motion_test.js` (exit 1 on failure). */
const LT = require("../lib/anim.js");
let bad = 0;
const ok = (name, cond, got) => { if (!cond) { bad++; console.log(`FAIL ${name} ${got === undefined ? "" : got}`); } else console.log(`ok   ${name}`); };
const near = (a, b, e = 1e-6) => Math.abs(a - b) <= e;

// curves: 0 → 1, monotonic, and t80 in the documented band
for (const [name, c, lo, hi] of [["linear", LT.C.linear, 0.79, 0.81], ["snap", LT.C.snap, 0.2, 0.26], ["whip", LT.C.whip, 0.45, 0.6], ["drift", LT.C.drift, 0.6, 0.72]]) {
  ok(`${name} ends`, near(c(0), 0, 1e-9) && near(c(1), 1, 1e-9));
  const t = LT.t80(c);
  ok(`${name} t80`, t >= lo && t <= hi, t.toFixed(3));
  let mono = true;
  for (let i = 1; i <= 200; i++) if (c(i / 200) + 1e-9 < c((i - 1) / 200)) mono = false;
  ok(`${name} monotonic`, mono);
}

// spring: from rest, 0 at 0, ~1 after settle, bounce overshoots
ok("spring start", LT.spring(0) === 0);
ok("spring rest", Math.abs(LT.spring(2, { omega: 20 }) - 1) < 1e-3, LT.spring(2));
ok("spring bounce overshoots", LT.spring(0.18, { bounce: 0.5, omega: 16 }) > 1.05, LT.spring(0.18, { bounce: 0.5, omega: 16 }).toFixed(3));
ok("critical never overshoots", LT.spring(0.1, { bounce: 0, omega: 20 }) < 1.0001);
const st = LT.settle({ omega: 22, eps: 0.02 });
ok("settle has a length", st > 0.15 && st < 2.5, st);

// clamp/mix/prog
ok("clamp", LT.clamp(3) === 1 && LT.clamp(-1) === 0 && LT.clamp(0.5) === 0.5);
ok("prog", LT.prog(5, 0, 10) === 0.5 && LT.prog(-1, 0, 1) === 0);
ok("mix", LT.mix(10, 20, 0.5) === 15);

// spline holds its ends and its knots
const knots = [{ t: 0, x: 0, y: 0 }, { t: 1, x: 100, y: 50 }, { t: 2, x: 200, y: 0 }];
ok("spline start", near(LT.spline(knots, -1)[0], 0));
ok("spline end", near(LT.spline(knots, 9)[0], 200));
ok("spline knot", near(LT.spline(knots, 1)[0], 100, 1e-9) && near(LT.spline(knots, 1)[1], 50, 1e-9));

// rng is fixed for a seed
const r1 = LT.rng(9), r2 = LT.rng(9);
let same = true; for (let i = 0; i < 20; i++) if (r1() !== r2()) same = false;
ok("rng deterministic", same);

// moves: endpoints, and the shapes the comps rely on
ok("rise lands", LT.rise(3, 0).y === 0 && LT.rise(0.001, 0).op < 0.5);
ok("pop lands", Math.abs(LT.pop(3, 0).s - 1) < 0.01);
const fd = LT.drop(3, 0, 2); ok("drop settles", Math.abs(fd.sy - 1) < 0.02 && Math.abs(fd.sx - 1) < 0.02);
ok("typeIn counts", LT.typeIn(2, 0, "abc", { cps: 3 }).shown === "abc" && LT.typeIn(0.5, 0, "abc", { cps: 2 }).shown === "a");
ok("typeIn caret blinks after", LT.typeIn(9, 0, "ab", { cps: 10, blink: 2 }).caret === (Math.floor(9 * 2) % 2 === 0 ? 1 : 0));
ok("checkIn flips", LT.checkIn(0.2, 0.5).on === false && LT.checkIn(0.6, 0.5).on === true);

const A = { x: 0, y: 0, w: 100, h: 100 }, B = { x: 1000, y: 500, w: 500, h: 300 };
const mid = LT.morph(0.5, 0, 1, A, B, { curve: LT.C.linear });
ok("morph halfway", near(mid.x, 500) && near(mid.w, 300));
ok("morph axis y", near(LT.morph(0.5, 0, 1, A, B, { curve: LT.C.linear, axis: "y" }).x, 0));
const dv = LT.dive(1, 0, 1, { x: 460, y: 228, w: 1000, h: 625 });
ok("dive fills", Math.abs(dv.s - 1.92) < 1e-5 && Math.abs(dv.tx - (960 - 1.92 * 960)) < 0.01);
ok("bloom covers", LT.bloom(9, 0, 1, 960, 540).full === true);
ok("fold fans", Math.abs(LT.fold(0.5, 0, 1, 0, 5, { x: 0, y: 0 }, { x: 10, y: 10 }).rot) > 0);
ok("flip picks", LT.flip(1.2, [[0, "a"], [1, "b"]]).text === "b");
ok("reveal clip", LT.reveal(0.5, 0, 1, { curve: LT.C.linear }).clip === "inset(0 50% 0 0)");

// camera: keys, quantisation, parallax
const cam = LT.rig([{ t: 0, x: 0, y: 0, zoom: 1 }, { t: 2, x: 1000, y: 500, zoom: 2 }], { float: 0 });
ok("cam start", near(cam(0).x, 0, 0.07) && near(cam(0).zoom, 1, 1e-3));
ok("cam end", Math.abs(cam(2).x - 1000) < 0.07 && Math.abs(cam(2).zoom - 2) < 1e-3);
const m0 = LT.plane({ x: 960, y: 540, zoom: 1, rot: 0 });
ok("plane identity at centre", near(m0[0], 1) && near(m0[4], 0) && near(m0[5], 0));
ok("parallax moves less", Math.abs(LT.plane({ x: 0, y: 0, zoom: 1, rot: 0 }, { depth: 1 })[4]) < Math.abs(LT.plane({ x: 0, y: 0, zoom: 1, rot: 0 })[4]) - 100);
const box = { x: 100, y: 100, w: 50, h: 50 };
ok("boxTravel grows with zoom", LT.boxTravel(box, { x: 0, y: 0, zoom: 1, rot: 0 }, { x: 0, y: 0, zoom: 2, rot: 0 }) > 30);

// light / rings / cloth / belt
const lf = LT.light(0);
ok("light low", lf.horizon > 800);
ok("rings spread", LT.rings(2, 0, { n: 3 })["done"] === true);
const cl = LT.cloth(0.3, 3, LT.cloth.ramps.slate, { gx: 8, gy: 8 });
ok("cloth RGBA", cl.length === 8 * 8 * 4 && cl[3] === 255);
const belt = LT.belt({ dur: 2, speed: 100 });
ok("belt monotonic", belt.at(1).x > belt.at(0.5).x && belt.at(2).clock > belt.at(1).clock);

console.log(bad ? `\n${bad} failed` : "\nall pass");
process.exit(bad ? 1 : 0);
