/* longtake · lib/anim.js — moves as pure functions of time. MIT.
 *
 * Every function takes a time in seconds and returns a plain pose object:
 *   { x, y, w, h, s, sx, sy, rot, op, blur, persp, ox, oy }
 * lib/paint.js applies it. Nothing here touches the DOM, so one call drives an element
 * or a ctx.setTransform alike. No state, no Math.random on the render path: the same
 * arguments always give the same numbers, which is what __clock(t) needs.
 *
 * Load as a classic script (<script src="lib/anim.js"> → window.LT) or require() it.
 * Catalogue and which carry belongs to which boundary: references/library.md.
 *
 *   curve    C · bez · t80 · spring · springVel · pulse · settle
 *   support  prog · mix · clamp · spline · rng · track
 *   enter    rise · drop · pop · maskUp · typeIn · checkIn · flyBy · peel
 *   carry    morph · bloom · dive · arc · fold · shuffle · stamp · flip · reveal
 *   contact  hit · cleave · push · pointer · stretch · sims
 *   camera   rig · plane · bokeh · whip · tremor · grid · project · unproject · boxTravel · camTravel
 *   fluid    light · rings · cloth · belt
 */
(function (root) {
  'use strict';

  // ── scalars ────────────────────────────────────────────────────────────────
  const clamp = (v, lo = 0, hi = 1) => (v < lo ? lo : v > hi ? hi : v);
  const mix = (a, b, k) => a + (b - a) * k;
  const prog = (t, t0, t1) => (t1 === t0 ? (t >= t1 ? 1 : 0) : clamp((t - t0) / (t1 - t0)));
  const sstep = (a, b, x) => { const k = clamp((x - a) / (b - a)); return k * k * (3 - 2 * k); };
  const s5 = (a, b, x) => { const k = clamp((x - a) / (b - a)); return k * k * k * (k * (k * 6 - 15) + 10); };

  // ── curves ────────────────────────────────────────────────────────────────
  // t80 = the share of a move's duration spent before 80 % of the distance is covered.
  // Under .35 snaps and settles (launch-clip feel); around .7 is a soft S-curve.
  const powOut = n => u => 1 - Math.pow(1 - u, n);
  const powInOut = n => u => (u < 0.5 ? Math.pow(2 * u, n) / 2 : 1 - Math.pow(2 - 2 * u, n) / 2);
  const EXPO = 1 - Math.pow(2, -10);
  const C = {
    linear: u => u,                                            // t80 .80
    swell: u => (1 - Math.cos(Math.PI * u)) / 2,                // t80 .70
    soft: u => u * u * (3 - 2 * u),                             // t80 .71
    drift: u => u * u * u * (u * (u * 6 - 15) + 10),            // t80 .67
    glide: powInOut(3),                                         // t80 .50, leaves and lands at rest
    deep: powInOut(5),
    land: powOut(2),                                            // t80 .55
    fall: powOut(3),                                            // t80 .42
    drop: powOut(4),                                            // t80 .33
    snap: u => (u <= 0 ? 0 : u >= 1 ? 1 : (1 - Math.pow(2, -10 * u)) / EXPO),   // t80 .23
    suck: u => (u <= 0 ? 0 : u >= 1 ? 1 : (Math.pow(2, 10 * u) - 1) / 1023),
    whip: u => (u <= 0 ? 0 : u >= 1 ? 1 : u < 0.5 ? Math.pow(2, 20 * u - 10) / 2 : 1 - Math.pow(2, 10 - 20 * u) / 2),
    circle: u => Math.sqrt(1 - Math.pow(1 - clamp(u), 2)),
    overshoot: u => { const k = 1.9; return 1 + (k + 1) * Math.pow(u - 1, 3) + k * Math.pow(u - 1, 2); },
  };

  // A CSS cubic-bezier as a function of u — for a curve lifted from a spec or a reference.
  function bez(x1, y1, x2, y2) {
    const ax = 3 * x1, bx = 3 * (x2 - x1) - ax, cx = 1 - ax - bx;
    const ay = 3 * y1, by = 3 * (y2 - y1) - ay, cy = 1 - ay - by;
    const X = s => ((ax * s + bx) * s + cx) * s, Y = s => ((ay * s + by) * s + cy) * s, dX = s => (3 * ax * s + 2 * bx) * s + cx;
    const solve = x => {
      let s = x;
      for (let i = 0; i < 8; i++) { const e = X(s) - x; if (Math.abs(e) < 1e-7) return s; const d = dX(s); if (Math.abs(d) < 1e-6) break; s -= e / d; if (s < 0 || s > 1) break; }
      let lo = 0, hi = 1; s = x;
      for (let i = 0; i < 60; i++) { const v = X(s); if (Math.abs(v - x) < 1e-7) return s; if (x > v) lo = s; else hi = s; s = (lo + hi) / 2; }
      return s;
    };
    return u => (u <= 0 ? 0 : u >= 1 ? 1 : Y(solve(u)));
  }

  function t80(curve, frac = 0.8, steps = 4000) {
    for (let i = 0; i <= steps; i++) { const u = i / steps; if (curve(u) >= frac) return u; }
    return 1;
  }

  // ── support ───────────────────────────────────────────────────────────────
  // Damped step response 0 → 1 from rest. bounce 0 is critical, .35 bouncy, .55 sloppy.
  function spring(tau, { bounce = 0, omega = 20 } = {}) {
    if (tau <= 0) return 0;
    const z = Math.max(0.02, 1 - bounce);
    if (z < 1) { const wd = omega * Math.sqrt(1 - z * z); return 1 - Math.exp(-z * omega * tau) * (Math.cos(wd * tau) + (z * omega / wd) * Math.sin(wd * tau)); }
    if (z === 1) return 1 - Math.exp(-omega * tau) * (1 + omega * tau);
    const q = omega * Math.sqrt(z * z - 1), r1 = -z * omega + q, r2 = -z * omega - q;
    return 1 - (r2 * Math.exp(r1 * tau) - r1 * Math.exp(r2 * tau)) / (r2 - r1);
  }

  // d/dt of spring() — progress per second. Feed squash so a landing squashes by its speed.
  function springVel(tau, { bounce = 0, omega = 20 } = {}) {
    if (tau <= 0) return 0;
    const z = Math.max(0.02, 1 - bounce);
    if (z < 1) { const wd = omega * Math.sqrt(1 - z * z); return (omega / wd) * Math.exp(-z * omega * tau) * Math.sin(wd * tau); }
    if (z === 1) return omega * omega * tau * Math.exp(-omega * tau);
    const q = omega * Math.sqrt(z * z - 1), r1 = -z * omega + q, r2 = -z * omega - q;
    return omega * omega * (Math.exp(r1 * tau) - Math.exp(r2 * tau)) / (r1 - r2);
  }

  // Decaying ring around 0 — a click, a landing, a wobble that dies out.
  const pulse = (tau, { decay = 9, freq = 26 } = {}) => (tau <= 0 ? 0 : Math.exp(-decay * tau) * Math.sin(freq * tau));

  // Seconds until spring() stays within eps of 1 — how long a beat must hold.
  function settle({ bounce = 0, omega = 20, eps = 0.02 } = {}) {
    let last = 0;
    for (let i = 1; i <= 20000; i++) { const t = i / 1000; if (Math.abs(1 - spring(t, { bounce, omega })) > eps) last = t; }
    return last;
  }

  // Hermite through {t, x, y} knots — the pointer's path.
  function spline(knots, t) {
    const L = knots.length;
    if (t <= knots[0].t) return [knots[0].x, knots[0].y];
    if (t >= knots[L - 1].t) return [knots[L - 1].x, knots[L - 1].y];
    let i = 0; while (knots[i + 1].t < t) i++;
    const k0 = knots[i], k1 = knots[i + 1], h = k1.t - k0.t, u = (t - k0.t) / h;
    const km = knots[Math.max(0, i - 1)], kp = knots[Math.min(L - 1, i + 2)];
    const m0x = (k1.x - km.x) / (k1.t - km.t) * h, m0y = (k1.y - km.y) / (k1.t - km.t) * h;
    const m1x = (kp.x - k0.x) / (kp.t - k0.t) * h, m1y = (kp.y - k0.y) / (kp.t - k0.t) * h;
    const h00 = 2 * u ** 3 - 3 * u ** 2 + 1, h10 = u ** 3 - 2 * u ** 2 + u, h01 = -2 * u ** 3 + 3 * u ** 2, h11 = u ** 3 - u ** 2;
    return [h00 * k0.x + h10 * m0x + h01 * k1.x + h11 * m1x, h00 * k0.y + h10 * m0y + h01 * k1.y + h11 * m1y];
  }

  // xorshift32 — layout decisions made once at setup, never on the render path.
  function rng(seed = 1) {
    let s = (seed >>> 0) || 1;
    return () => { s ^= s << 13; s ^= s >>> 17; s ^= s << 5; return (s >>> 0) / 4294967296; };
  }

  // A spring that chases want(t) → [x, y], integrated once at hz and sampled; the motion of an operator's hand.
  function track(want, { from = [0, 0], omega = 12, bounce = 0.1, hz = 240, dur = 30 } = {}) {
    const n = Math.ceil(dur * hz) + 1, X = new Float64Array(n), Y = new Float64Array(n);
    let x = from[0], y = from[1], vx = 0, vy = 0;
    for (let i = 0; i < n; i++) {
      const w = want(i / hz);
      vx += ((w[0] - x) * omega * omega - 2 * Math.max(0.02, 1 - bounce) * omega * vx) / hz;
      vy += ((w[1] - y) * omega * omega - 2 * Math.max(0.02, 1 - bounce) * omega * vy) / hz;
      x += vx / hz; y += vy / hz; X[i] = x; Y[i] = y;
    }
    return t => { const f = clamp(t * hz, 0, n - 1); return [mix(X[Math.floor(f)], X[Math.min(n - 1, Math.floor(f) + 1)], f - Math.floor(f)), mix(Y[Math.floor(f)], Y[Math.min(n - 1, Math.floor(f) + 1)], f - Math.floor(f))]; };
  }

  // ── enter ─────────────────────────────────────────────────────────────────
  // A word lands: spring rise and a touch of scale; opacity leads the spring so it never reads as a fade.
  function rise(t, t0, { bounce = 0.35, omega = 22, dist = 26, s0 = 0.94, ds = 0.06, lead = 1.6 } = {}) {
    const k = spring(t - t0, { bounce, omega });
    return { k, op: clamp(k * lead), y: (1 - k) * dist, s: s0 + ds * k };
  }

  // Letter i of a wordmark drops in; speed flattens it and widens it, recovering as it settles.
  function drop(t, t0, i, { stagger = 0.055, bounce = 0.45, omega = 26, dist = 46, squash = 0.0075, cap = 0.22, widen = 0.6, lead = 1.6, h = 0.012 } = {}) {
    const tau = t - t0 - i * stagger;
    const k = spring(tau, { bounce, omega });
    const v = (spring(tau, { bounce, omega }) - spring(tau - h, { bounce, omega })) / h;
    const sq = clamp(Math.abs(v) * squash, 0, cap);
    return { k, sq, op: clamp(k * lead), y: (1 - k) * dist, sx: 1 + sq * widen, sy: 1 - sq };
  }

  // A card enters: spring rise with scale.
  function pop(t, t0, { bounce = 0.3, omega = 18, from = 36, s0 = 0.94, ds = 0.06, lead = 1.6 } = {}) {
    const k = spring(t - t0, { bounce, omega });
    return { k, op: clamp(k * lead), s: s0 + ds * k, y: (1 - k) * from };
  }

  // A line rises into place from behind a clip mask; y is a fraction of the line height (pass it).
  function maskUp(t, t0, i = 0, { stagger = 0.13, bounce = 0.5, omega = 17, h = 1 } = {}) {
    const k = spring(t - t0 - i * stagger, { bounce, omega });
    return { k, y: (1 - k) * h, on: k > 0 };
  }

  // Typing: characters at cps, caret solid while typing, blinking after.
  function typeIn(t, t0, text, { cps = 38, blink = 2.4 } = {}) {
    const n = clamp(Math.floor((t - t0) * cps), 0, text.length);
    return { n, shown: text.slice(0, n), done: n >= text.length, caret: n < text.length || Math.floor(t * blink) % 2 === 0 ? 1 : 0 };
  }

  // A checkbox tick at tl: pops from .8 with a spring ring.
  function checkIn(t, tl, { bounce = 0.5, omega = 28 } = {}) {
    const on = t >= tl, k = spring(t - tl, { bounce, omega });
    return { on, k, s: on ? 0.8 + 0.25 * (1 - k) + 0.2 * k : 1 };
  }

  // A panel flies in tilted from the right, holds, flies out left.
  // Compose: translate(x) perspective(2200px) rotateY(r) rotateX(rx) scale(s), filter blur.
  function flyBy(t, t0, hold, { from = 1500, at = 0, out = -1700, bounce = 0.18, omega = 14, exit = 0.28,
    blurIn = 10, blurOut = 12, ry0 = -18, ry1 = -9, ryOut = 10, rx = 4, s0 = 0.92, pre = 0.02, post = 0.35 } = {}) {
    const t1 = t0 + hold, live = t >= t0 - pre && t < t1 + post;
    const kin = spring(t - t0, { bounce, omega }), kout = s5(t1, t1 + exit, t), kc = Math.min(1, kin);
    return {
      live, kin, kout, x: mix(from, at, kin) + kout * out, blur: Math.max((1 - kc) * blurIn, kout * blurOut),
      ry: mix(ry0, ry1, kc) + kout * ryOut, rx, s: mix(s0, 1, kc), op: 1 - kout,
    };
  }

  // Exit: lifts, grows a touch and blurs away over dur.
  function peel(t, t1, { dur = 0.22, dir = -1, dist = 90, blur = 10, grow = 0.03 } = {}) {
    const k = s5(t1, t1 + dur, t);
    return { k, op: 1 - k, y: dir * k * dist, blur: k * blur, s: 1 + grow * k };
  }

  // ── carry — the next beat grows out of this one ───────────────────────────
  // Rect A becomes rect B: a card into a page, a chip into a bar. axis limits the change.
  function morph(t, t0, t1, A, B, { curve = C.snap, axis = 'both', radius = true } = {}) {
    const k = curve(prog(t, t0, t1));
    const kx = axis === 'y' ? 0 : k, ky = axis === 'x' ? 0 : k;
    const x = mix(A.x, B.x, kx), y = mix(A.y, B.y, ky), w = mix(A.w, B.w, kx), h = mix(A.h, B.h, ky);
    return { k, x, y, w, h, r: radius ? mix(A.r || 0, B.r || 0, k) : (B.r || 0), cx: x + w / 2, cy: y + h / 2 };
  }

  // A stage opens from the subject at (cx, cy) until it covers the frame.
  function bloom(t, t0, t1, cx, cy, { W = 1920, H = 1080, curve = C.snap, r0 = 0 } = {}) {
    const k = curve(prog(t, t0, t1));
    const far = Math.max(Math.hypot(cx, cy), Math.hypot(W - cx, cy), Math.hypot(cx, H - cy), Math.hypot(W - cx, H - cy)) + 2;
    return { k, cx, cy, r: mix(r0, far, k), full: k >= 1 };
  }

  // The camera pushes into box until it fills the frame; its inside becomes the next scene.
  // matrix = [s,0,0,s,tx,ty] (screen = world·s + t).
  function dive(t, t0, t1, box, { W = 1920, H = 1080, curve = C.whip, fit = 'cover' } = {}) {
    const k = curve(prog(t, t0, t1));
    const sEnd = fit === 'contain' ? Math.min(W / box.w, H / box.h) : Math.max(W / box.w, H / box.h);
    const s = Math.exp(Math.log(sEnd) * k);                     // log space: one speed, whatever the distance
    const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
    const px = mix(cx, W / 2, k), py = mix(cy, H / 2, k);
    return { k, s, tx: px - s * cx, ty: py - s * cy, matrix: [s, 0, 0, s, px - s * cx, py - s * cy] };
  }

  // The subject travels from → to on an arc.
  function arc(t, t0, t1, from, to, { height = 200, curve = C.drift } = {}) {
    const k = curve(prog(t, t0, t1));
    return { k, x: mix(from.x, to.x, k), y: mix(from.y, to.y, k) - Math.sin(k * Math.PI) * height };
  }

  // Item i of n fans into its new place, staggered.
  function fold(t, t0, t1, i, n, from, to, { stagger = 0.08, lift = 120, spin = 0.4, curve = C.drift } = {}) {
    const k = curve(prog(t, t0 + i * stagger, t1 + i * stagger)), o = i - (n - 1) / 2, b = Math.sin(k * Math.PI);
    return { k, x: mix(from.x, to.x, k), y: mix(from.y, to.y, k) - b * lift, rot: b * o * spin };
  }

  // A rail of panels: each switch advances shift by one with a ring; the text lags behind.
  function shuffle(t, times, { dur = 0.35, amp = 55, decay = 7, freq = 22, tilt = 0.08, sx = 0.24, sy = 0.15, lag = 1.8, curve = C.drift } = {}) {
    let shift = 0, r = 0;
    for (const ts of times) { shift += curve(prog(t, ts, ts + dur)); r += pulse(t - ts, { decay, freq }); }
    const s = Math.abs(r);
    return { shift, at: Math.round(shift), wobble: r * amp, rot: r * tilt, sx: 1 + s * sx, sy: 1 - s * sy, drag: -r * amp * lag };
  }

  // The cast folds into a seal: a disc grows and turns.
  function stamp(t, t0, t1, { r = 235, turns = 1, curve = C.drift } = {}) {
    const k = curve(prog(t, t0, t1));
    return { k, r: r * k, rot: k * turns * Math.PI * 2 };
  }

  // Staccato hits: the word whose time has come. list = [[t, word], …]. Hard cuts, in a burst.
  function flip(t, list) {
    let text = '', i = -1;
    for (let j = 0; j < list.length; j++) if (t >= list[j][0]) { text = list[j][1]; i = j; }
    return { text, i };
  }

  // A wipe that uncovers B from A's edge: pass progress to a clip-path inset.
  function reveal(t, t0, t1, { from = 'left', curve = C.snap } = {}) {
    const k = curve(prog(t, t0, t1)), v = 100 * (1 - k);
    const clip = from === 'left' ? `inset(0 ${v}% 0 0)` : from === 'right' ? `inset(0 0 0 ${v}%)`
      : from === 'up' ? `inset(0 0 ${v}% 0)` : `inset(${v}% 0 0 0)`;
    return { k, clip };
  }

  // ── contact — one thing causes another ────────────────────────────────────
  // The ring of a landing; sx/sy squash the lander, r feeds whatever it lands on.
  function hit(t, th, { decay = 7, freq = 22, sx = 0.13, sy = 0.16 } = {}) {
    const r = pulse(t - th, { decay, freq });
    return { r, sx: 1 + r * sx, sy: 1 - r * sy };
  }

  // A landing at cx splits a line of glyphs at x: pushed apart, bouncing by distance, rejoining.
  function cleave(t, th, x, cx, { w = 600, spread = 65, bounce = 65, rot = 0.18, falloff = 3,
    open = [-0.01, 0.48], close = [0.63, 0.98], decay = 7, freq = 22, curve = C.drift } = {}) {
    const d = (x - cx) / w, r = pulse(t - th, { decay, freq });
    const apart = curve(prog(t, th + open[0], th + open[1])) * (1 - curve(prog(t, th + close[0], th + close[1])));
    return { dx: Math.sign(d) * apart * spread, dy: r * bounce * Math.exp(-d * d * falloff), rot: r * d * rot };
  }

  // A button pressed at tc: rings in scale; active for the colour flash.
  function push(t, tc, { depth = 0.16, decay = 10, freq = 30, flash = 0.4 } = {}) {
    const cl = t - tc, sq = cl > 0 ? pulse(cl, { decay, freq }) * depth : 0;
    return { s: 1 + sq, sq, down: cl > 0, active: cl > 0 && cl < flash };
  }

  // The pointer: spline through knots, dipping to down for hold s at each click.
  function pointer(t, knots, clicks = [], { down = 0.84, hold = 0.14 } = {}) {
    const p = spline(knots, t);
    let s = 1;
    for (const c of clicks) { const d = t - c; if (d >= 0 && d < hold) s = down; }
    return { x: p[0], y: p[1], s };
  }

  // Stretch along the direction of travel, thin across it (velocity in px/s).
  function stretch(vx, vy, { k = 0.0012, cap = 0.45, ky = 0.0008, capY = 0.3 } = {}) {
    const sp = Math.hypot(vx, vy);
    return { speed: sp, ang: Math.atan2(vy, vx), sx: 1 + clamp(sp * k, 0, cap), sy: 1 - clamp(sp * ky, 0, capY) };
  }

  // Live mechanisms inside a card, driven by the pointer. card = {t, out, x, y}; the sim runs
  // card.t … out + .3 once and at(t) samples it. The composition draws.
  const SDT = 1 / 240;
  const sample = (st, t0, per) => t => st[clamp(Math.floor((t - t0) / per), 0, st.length - 1)];
  const sims = {
    SDT,
    // a dot pulled toward the pointer inside R and springing back
    pull(card, hand, { B = { x: 230, y: 158 }, R = 150, pull = 0.36, K = 120, damp = 0.85 } = {}) {
      const D = Math.pow(damp, SDT * 60); let x = 0, y = 0, vx = 0, vy = 0; const st = [];
      for (let t = card.t; t <= card.out + 0.3; t += SDT) {
        const h = hand(t), dx = h[0] - (card.x + B.x), dy = h[1] - (card.y + B.y), d = Math.hypot(dx, dy); let tx = 0, ty = 0;
        if (d < R) { const f = pull * (1 - (d / R) ** 2); tx = dx * f; ty = dy * f; }
        vx += (tx - x) * K * SDT; vy += (ty - y) * K * SDT; vx *= D; vy *= D; x += vx * SDT; y += vy * SDT; st.push([x, y]);
      }
      return { st, per: SDT, B, at: sample(st, card.t, SDT) };
    },
    // a follower that lags the pointer and returns home when it leaves the card
    chase(card, hand, { K = 70, damp = 0.88, home = [230, 140], box = [30, 430, 50, 240], reach = [40, 500, 40, 310] } = {}) {
      const D = Math.pow(damp, SDT * 60); let x = home[0], y = home[1], vx = 0, vy = 0; const st = [];
      for (let t = card.t; t <= card.out + 0.3; t += SDT) {
        const h = hand(t);
        let tx = clamp(h[0] - card.x, box[0], box[1]), ty = clamp(h[1] - card.y, box[2], box[3]);
        const near = h[0] > card.x - reach[0] && h[0] < card.x + reach[1] && h[1] > card.y - reach[2] && h[1] < card.y + reach[3];
        if (!near) { tx = home[0]; ty = home[1]; }
        vx += (tx - x) * K * SDT; vy += (ty - y) * K * SDT; vx *= D; vy *= D; x += vx * SDT; y += vy * SDT; st.push([x, y, vx, vy]);
      }
      return { st, per: SDT, at: sample(st, card.t, SDT) };
    },
    // a ring of radial springs with neighbour coupling, dented where the pointer touches
    wobble(card, hand, { N = 48, C: c = { x: 230, y: 150 }, R0 = 78, K = 42, CP = 1800, damp = 0.962, reach = 60, dent = 14 } = {}) {
      const D = Math.pow(damp, SDT * 60), r = new Float32Array(N), v = new Float32Array(N), st = []; let step = 0;
      for (let t = card.t; t <= card.out + 0.3; t += SDT, step++) {
        const h = hand(t), hx = h[0] - (card.x + c.x), hy = h[1] - (card.y + c.y);
        for (let i = 0; i < N; i++) {
          const th = i / N * Math.PI * 2, px = Math.cos(th) * R0 * (1 + r[i]), py = Math.sin(th) * R0 * (1 + r[i]), d = Math.hypot(hx - px, hy - py);
          let push = 0; if (d < reach) push = -(1 - d / reach) * dent;
          const lap = r[(i + N - 1) % N] + r[(i + 1) % N] - 2 * r[i];
          v[i] += (-r[i] * K + lap * CP + push) * SDT; v[i] *= D;
        }
        for (let i = 0; i < N; i++) r[i] += v[i] * SDT;
        if (step % 4 === 0) st.push(Float32Array.from(r));
      }
      return { st, per: SDT * 4, N, C: c, R0, at: sample(st, card.t, SDT * 4) };
    },
    // N nodes hanging from (ax, ay), pushed aside by the pointer; samples are [x0, y0, x1, y1, …]
    rope(card, hand, { N = 16, L = 13, ax = 230, ay = 40, damp = 0.985, gravity = 1400, reach = 34, push = 2.2, iters = 3 } = {}) {
      const px = new Float32Array(N), py = new Float32Array(N), ox = new Float32Array(N), oy = new Float32Array(N);
      for (let i = 0; i < N; i++) { px[i] = ox[i] = ax; py[i] = oy[i] = ay + i * L; }
      const st = []; let step = 0;
      for (let t = card.t; t <= card.out + 0.3; t += SDT, step++) {
        const h = hand(t), hx = h[0] - card.x, hy = h[1] - card.y;
        for (let i = 1; i < N; i++) {
          const vx = (px[i] - ox[i]) * damp, vy = (py[i] - oy[i]) * damp;
          ox[i] = px[i]; oy[i] = py[i]; px[i] += vx; py[i] += vy + gravity * SDT * SDT;
          const dx = px[i] - hx, dy = py[i] - hy, d = Math.hypot(dx, dy);
          if (d < reach && d > 0.01) { const f = (reach - d) / reach * push; px[i] += dx / d * f; py[i] += dy / d * f; }
        }
        for (let it = 0; it < iters; it++) {
          px[0] = ax; py[0] = ay;
          for (let i = 0; i < N - 1; i++) {
            const dx = px[i + 1] - px[i], dy = py[i + 1] - py[i], d = Math.hypot(dx, dy) || 1e-6, c = (d - L) / d * 0.5;
            if (i === 0) { px[1] -= dx * c * 2; py[1] -= dy * c * 2; } else { px[i] += dx * c; py[i] += dy * c; px[i + 1] -= dx * c; py[i + 1] -= dy * c; }
          }
        }
        if (step % 4 === 0) { const s = new Float32Array(N * 2); for (let i = 0; i < N; i++) { s[i * 2] = px[i]; s[i * 2 + 1] = py[i]; } st.push(s); }
      }
      return { st, per: SDT * 4, N, at: sample(st, card.t, SDT * 4) };
    },
  };

  // ── camera ────────────────────────────────────────────────────────────────
  // Keys {t, x, y, zoom, rot, curve}; (x, y) is the world point held at frame centre. Zoom moves in log
  // space. A hand (two slow sines, zero in a hold) and tremor on hits make it an operator, not keyframes.
  function rig(keys, { W = 1920, H = 1080, curve = C.glide, float = 0.6, shake = 0, hits = [] } = {}) {
    const at = k => ({ x: k.x ?? W / 2, y: k.y ?? H / 2, zoom: k.zoom ?? 1, rot: k.rot ?? 0 });
    return t => {
      let cam;
      if (!keys.length) cam = { x: W / 2, y: H / 2, zoom: 1, rot: 0 };
      else if (t <= keys[0].t) cam = at(keys[0]);
      else if (t >= keys[keys.length - 1].t) cam = at(keys[keys.length - 1]);
      else {
        let i = 0; while (keys[i + 1].t < t) i++;
        const A = at(keys[i]), B = at(keys[i + 1]), k = (keys[i + 1].curve || curve)(prog(t, keys[i].t, keys[i + 1].t));
        cam = { x: mix(A.x, B.x, k), y: mix(A.y, B.y, k), zoom: Math.exp(mix(Math.log(A.zoom), Math.log(B.zoom), k)), rot: mix(A.rot, B.rot, k) };
      }
      if (float) {
        const held = keys.some((k, i) => i && t >= keys[i - 1].t && t <= k.t && Math.abs(k.x - keys[i - 1].x) < 1e-6 && Math.abs(k.zoom - keys[i - 1].zoom) < 1e-9);
        const w = held ? 0 : float;
        cam.x += w * Math.sin(t * 0.37) * Math.cos(t * 0.13);
        cam.y += w * 0.7 * Math.sin(t * 0.29 + 1.7);
        cam.rot += 0.0004 * w * Math.sin(t * 0.23);
      }
      for (const [th, amp, decay] of hits) {
        const tau = t - th; if (tau <= 0) continue;
        const e = amp * Math.exp(-decay * tau), w2 = 2 * Math.PI * tau;
        cam.x += e * Math.sin(w2 * 19); cam.y += 0.7 * e * Math.sin(w2 * 24.9); cam.rot += 0.0015 * e * Math.sin(w2 * 14.6);
      }
      // below what shows: a settled camera repeats its frame and the shutter is skipped
      return { x: Math.round(cam.x * 16) / 16, y: Math.round(cam.y * 16) / 16, zoom: Math.round(cam.zoom * 2000) / 2000, rot: Math.round(cam.rot * 20000) / 20000 };
    };
  }

  // Matrix [a,b,c,d,e,f] for a depth layer seen through cam. depth 0 = focus plane; >0 farther (moves less), <0 nearer.
  function plane(cam, { W = 1920, H = 1080, depth = 0 } = {}) {
    const f = 1 / (1 + Math.max(-0.9, depth));
    const cx = W / 2 + (cam.x - W / 2) * f, cy = H / 2 + (cam.y - H / 2) * f;
    const z = Math.exp(Math.log(cam.zoom) * f), c = Math.cos(cam.rot * f) * z, s = Math.sin(cam.rot * f) * z;
    return [c, s, -s, c, W / 2 - (c * cx - s * cy), H / 2 - (s * cx + c * cy)];
  }

  // Depth-of-field blur in px for a layer at depth when the camera focuses at focus.
  const bokeh = (depth, focus = 0, { k = 10, max = 14 } = {}) => Math.min(max, Math.abs(depth - focus) * k);

  // A whip: all of dist in dur on a whip curve. Only reads with the shutter on.
  const whip = (t, t0, dur, dist, { curve = C.whip } = {}) => { const k = curve(prog(t, t0, t0 + dur)); return { k, d: dist * k }; };

  // Camera tremor after a hit: decaying, deterministic, from zero.
  function tremor(t, th, { amp = 12, decay = 9, freq = 19, seed = 1 } = {}) {
    const tau = t - th; if (tau <= 0) return { x: 0, y: 0, rot: 0 };
    const r = rng(seed), w = 2 * Math.PI * tau, e = amp * Math.exp(-decay * tau);
    return { x: e * Math.sin(w * freq * (1 + 0.1 * r())), y: 0.7 * e * Math.sin(w * freq * (1.31 + 0.1 * r())), rot: 0.0015 * e * Math.sin(w * freq * 0.77) };
  }

  // A far lattice through cam: dot positions and a radius that stays px on screen. A camera needs
  // something farther back to slide against or an empty ground doesn't read.
  function grid(cam, { depth = 1.2, spacing = 48, px = 1.4, W = 1920, H = 1080 } = {}) {
    const M = plane(cam, { W, H, depth }), c = [[0, 0], [W, 0], [0, H], [W, H]].map(p => unproject(M, p[0], p[1]));
    const xs = c.map(p => p[0]), ys = c.map(p => p[1]);
    return { matrix: M, spacing, r: px / Math.hypot(M[0], M[1]),
      x0: Math.floor(Math.min(...xs) / spacing) * spacing, x1: Math.max(...xs), y0: Math.floor(Math.min(...ys) / spacing) * spacing, y1: Math.max(...ys) };
  }

  // Through a plane matrix: world → screen, screen → world, a box's screen bounds, corner travel.
  const project = (M, x, y) => [M[0] * x + M[2] * y + M[4], M[1] * x + M[3] * y + M[5]];
  const unproject = (M, x, y) => { const d = M[0] * M[3] - M[1] * M[2], u = x - M[4], v = y - M[5]; return [(M[3] * u - M[2] * v) / d, (M[0] * v - M[1] * u) / d]; };
  function boxTravel(box, c0, c1, { W = 1920, H = 1080, depth = 0 } = {}) {
    const M0 = plane(c0, { W, H, depth }), M1 = plane(c1, { W, H, depth });
    let d = 0;
    for (const [x, y] of [[box.x, box.y], [box.x + box.w, box.y], [box.x, box.y + box.h], [box.x + box.w, box.y + box.h]]) {
      const a = project(M0, x, y), b = project(M1, x, y);
      d = Math.max(d, Math.hypot(a[0] - b[0], a[1] - b[1]));
    }
    return d;
  }
  // How far the frame's corners slide between two cameras — the camera's share of __travel.
  function camTravel(c0, c1, cMid, { W = 1920, H = 1080, depth = 0 } = {}) {
    const M0 = plane(c0, { W, H, depth }), M1 = plane(c1, { W, H, depth }), Mm = plane(cMid, { W, H, depth });
    let d = 0;
    for (const [sx, sy] of [[0, 0], [W, 0], [0, H], [W, H]]) {
      const [wx, wy] = unproject(Mm, sx, sy), a = project(M0, wx, wy), b = project(M1, wx, wy);
      d = Math.max(d, Math.hypot(a[0] - b[0], a[1] - b[1]));
    }
    return d;
  }

  // ── fluid ─────────────────────────────────────────────────────────────────
  // A ground of light: level 0 is a low glow, 1 is the frame flooded. Fill the ellipse with a
  // radial gradient; `core` is where the light is bright enough to turn type white.
  function light(level, { W = 1920, H = 1080, rest = 0.84, top = -300, r0 = 660, r1 = 1500, tilt = 0.012 } = {}) {
    const ry = r0 + r1 * level, horizon = mix(H * rest, top, level);
    return { cx: W / 2, cy: horizon + 0.62 * ry, rx: ry * 2.3, ry, tilt, horizon, core: 0.5, stops: [0, 0.36, 0.6, 0.8, 1] };
  }

  // A flood that drains in rings: n radii leave a point, staggered, each crossing the frame in dur.
  function rings(t, t0, { n = 3, stagger = 0.16, dur = 1.25, rMax = 1160, curve = C.drift } = {}) {
    const r = []; for (let k = 0; k < n; k++) r.push(rMax * curve(prog(t, t0 + k * stagger, t0 + k * stagger + dur)));
    return { r, done: t >= t0 + (n - 1) * stagger + dur };
  }

  // Cloth: domain-warped value noise, two octaves, on a tiny grid, contrast-stretched and ramped.
  // Returns RGBA for gx × gy; putImageData it into a gx × gy canvas and draw it up blurred.
  const hash = (x, y, s) => { let h = (x * 374761393 + y * 668265263 + s * 1442695041) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); return ((h ^ (h >>> 16)) >>> 0) / 4294967296; };
  function noise(x, y, s) {
    const xi = Math.floor(x), yi = Math.floor(y), xf = x - xi, yf = y - yi, u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf);
    const a = hash(xi, yi, s), b = hash(xi + 1, yi, s), c = hash(xi, yi + 1, s), d = hash(xi + 1, yi + 1, s);
    return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
  }
  const fbm = (x, y, s) => 0.5 * noise(x, y, s) + 0.25 * noise(x * 2.02, y * 2.02, s);
  function rampAt(stops, k) {
    k = clamp(k);
    for (let i = 1; i < stops.length; i++) if (k <= stops[i][0]) {
      const [a, A] = stops[i - 1], [b, B] = stops[i], u = (k - a) / (b - a);
      return A.map((v, j) => v + (B[j] - v) * u);
    }
    return stops[stops.length - 1][1];
  }
  const RAMPS = {
    slate: [[0, [36, 42, 54]], [0.24, [58, 68, 88]], [0.44, [22, 26, 34]], [0.58, [44, 52, 68]], [0.8, [96, 112, 140]], [1, [198, 214, 236]]],
    ember: [[0, [200, 120, 24]], [0.22, [236, 170, 34]], [0.42, [122, 96, 26]], [0.54, [160, 94, 32]], [0.74, [240, 74, 92]], [1, [252, 210, 198]]],
    moss: [[0, [26, 62, 44]], [0.24, [58, 110, 74]], [0.44, [20, 44, 32]], [0.58, [46, 92, 62]], [0.8, [126, 168, 122]], [1, [226, 240, 214]]],
  };
  function cloth(tau, seed = 3, stops = RAMPS.slate, { gx = 16, gy = 20, contrast = 3.4, out = null } = {}) {
    const d = out || new Uint8ClampedArray(gx * gy * 4);
    for (let j = 0; j < gy; j++) for (let i = 0; i < gx; i++) {
      const u = i / gx * 1.1, v = j / gy * 1.4;
      const qx = fbm(u + 0.11 * tau, v - 0.07 * tau, seed), qy = fbm(u + 5.2 - 0.09 * tau, v + 1.3 + 0.05 * tau, seed);
      const k = 0.5 + (fbm(u + 1.8 * qx + 0.04 * tau, v + 1.8 * qy, seed) - 0.375) * contrast;
      const c = rampAt(stops, k), n = (i + j * gx) * 4;
      d[n] = c[0]; d[n + 1] = c[1]; d[n + 2] = c[2]; d[n + 3] = 255;
    }
    return d;
  }
  cloth.ramps = RAMPS; cloth.ramp = rampAt;

  // A belt: travels at speed until told to stop. at(t) → {x, clock}; drive every card's loop with clock
  // so contents slow with the belt. Integrated once, so start and stop stay pure functions of t.
  function belt({ dur, start = 0, speed = 204, rampDur = 1.0, stop = null, hz = 240 } = {}) {
    const n = Math.ceil(dur * hz) + 1, X = new Float64Array(n), T = new Float64Array(n);
    let x = 0, tau = 0;
    for (let i = 0; i < n; i++) {
      const t = i / hz, k = stop ? 1 - C.soft(prog(t, stop[0], stop[1])) : 1;
      x += speed * spring(t - start, { bounce: 0, omega: 2 * Math.PI / rampDur }) * k / hz;
      tau += k / hz; X[i] = x; T[i] = tau;
    }
    return { at(t) { const f = clamp(t * hz, 0, n - 1), i = Math.floor(f), j = Math.min(n - 1, i + 1), u = f - i; return { x: mix(X[i], X[j], u), clock: mix(T[i], T[j], u) }; } };
  }

  const LT = {
    version: '0.1.0',
    clamp, mix, prog, sstep, s5, C, bez, t80, spring, springVel, pulse, settle, spline, rng, track,
    rise, drop, pop, maskUp, typeIn, checkIn, flyBy, peel,
    morph, bloom, dive, arc, fold, shuffle, stamp, flip, reveal,
    hit, cleave, push, pointer, stretch, sims,
    rig, plane, bokeh, whip, tremor, grid, project, unproject, boxTravel, camTravel,
    light, rings, cloth, belt,
  };
  root.LT = LT;
  if (typeof module === 'object' && module.exports) module.exports = LT;
})(typeof window !== 'undefined' ? window : globalThis);
