/* longtake · lib/paint.js — the DOM half. MIT.
 *
 * anim.js answers "where is it at t"; paint.js is the only place that writes a transform.
 * A composition mounts one stage, registers layers by id and paints them with pose objects.
 * Registered layers are what the probe reads, so a comp never has to be annotated twice.
 *
 *   const P = LTX.mount(document.getElementById('stage'));
 *   P.add('line', el, {key:'line', w:900, h:2});
 *   P.set('line', {x:510, y:540, op:1});
 *   P.cam(cam(t));                       // one world plane, optional depth wrappers
 *   window.__frames = () => P.frames();
 *
 * Poses: {x, y, w, h, s, sx, sy, rot, op, blur, ox, oy, clip, display}. Origin defaults to the
 * layer's top-left (0 0), so positions are predictable. Pass ox/oy for anything that must scale
 * about its own centre.
 */
(function (root) {
  'use strict';

  const LTX = {
    mount(stage, { W = 1920, H = 1080 } = {}) {
      stage.style.position = 'absolute';
      stage.style.inset = '0';
      stage.style.overflow = 'hidden';
      stage.style.transformOrigin = '0 0';
      const world = document.createElement('div');
      world.style.cssText = `position:absolute;left:0;top:0;width:${W}px;height:${H}px;transform-origin:0 0;will-change:transform`;
      stage.appendChild(world);
      const depths = new Map([[0, world]]), reg = new Map(), poses = new Map();
      const depthEl = d => {
        if (depths.has(d)) return depths.get(d);
        const wrap = document.createElement('div');
        wrap.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;transform-origin:0 0;will-change:transform';
        world.appendChild(wrap); depths.set(d, wrap);
        return wrap;
      };
      const P = {
        stage, world, W, H, reg, poses,

        add(id, el, { key = '', depth = 0, w = 0, h = 0, ox = 0, oy = 0 } = {}) {
          const lay = { id, el, key, depth, ox, oy };
          el.style.position = 'absolute';
          el.style.left = '0'; el.style.top = '0';
          el.style.transformOrigin = '0 0';
          el.style.willChange = 'transform,opacity,filter';
          el.dataset.lt = id;
          if (key) el.dataset.ltKey = key;
          depthEl(depth).appendChild(el);
          reg.set(id, lay);
          poses.set(id, { x: 0, y: 0, w, h, op: 1 });
          return el;
        },

        // Pose application. w/h set layout size; every other key is a transform field.
        set(id, p = {}) {
          const L = reg.get(id); if (!L) return;
          const cur = poses.get(id) || {};
          const q = Object.assign({ x: 0, y: 0, op: 1 }, cur, p);
          poses.set(id, q);
          const el = L.el;
          if (q.w != null && q.w !== '') el.style.width = typeof q.w === 'number' ? q.w + 'px' : q.w;
          if (q.h != null && q.h !== '') el.style.height = typeof q.h === 'number' ? q.h + 'px' : q.h;
          el.style.display = q.display || (q.op > 0.002 ? '' : 'none');
          el.style.opacity = Math.max(0, Math.min(1, q.op)).toFixed(3);
          el.style.filter = q.blur > 0.2 ? `blur(${q.blur.toFixed(2)}px)` : '';
          el.style.clipPath = q.clip || '';
          const s = q.s == null ? 1 : q.s, sx = (q.sx == null ? 1 : q.sx) * s, sy = (q.sy == null ? 1 : q.sy) * s;
          el.style.transform = `translate(${(q.x || 0).toFixed(2)}px,${(q.y || 0).toFixed(2)}px)` +
            (q.rot ? ` rotate(${q.rot.toFixed(5)}rad)` : '') +
            (sx !== 1 || sy !== 1 ? ` scale(${sx.toFixed(5)},${sy.toFixed(5)})` : '');
          el.style.transformOrigin = `${L.ox}px ${L.oy}px`;
        },

        hide(id) { const L = reg.get(id); if (L) L.el.style.display = 'none'; },

        // Camera: one matrix on the world and one per depth wrapper (parallax).
        cam(cam) {
          for (const [d, el] of depths) {
            const m = LT.plane(cam, { W: this.W, H: this.H, depth: d });
            el.style.transform = `matrix(${m.map(v => v.toFixed(5)).join(',')})`;
          }
        },

        // What is on screen, for the probe: rects already carry every ancestor transform.
        frames() {
          const out = [];
          for (const { id, el, key } of reg.values()) {
            if (!el.isConnected) continue;
            let op = 1;
            for (let e = el; e; e = e.parentElement) {
              const cs = getComputedStyle(e);
              if (cs.display === 'none' || cs.visibility === 'hidden') { op = 0; break; }
              op *= parseFloat(cs.opacity);
            }
            if (op < 0.04) continue;
            const r = el.getBoundingClientRect();
            if (r.width < 1 || r.height < 1) continue;
            out.push({ id, key: key || id, x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height, op });
          }
          return out;
        },

        // Farthest anything on screen travels between two times — what the shutter sizes itself by.
        // Measures local boxes on each depth plane and the plane matrices, so it is camera-inclusive.
        async travel(a, b, seek) {
          const snap = () => {
            const ms = new Map(), boxes = [];
            for (const [d, el] of depths) ms.set(d, new DOMMatrix(getComputedStyle(el).transform === 'none' ? '' : getComputedStyle(el).transform));
            for (const [id, L] of reg) {
              const q = poses.get(id); if (!q || q.op <= 0.04) continue;
              boxes.push({ id, d: L.depth, x: q.x || 0, y: q.y || 0, w: q.w || 0, h: q.h || 0, sx: q.sx || 1, sy: q.sy || 1, s: q.s || 1, rot: q.rot || 0 });
            }
            return { ms, boxes };
          };
          const A = (await seek(a), snap()); const B = (await seek(b), snap());
          const byId = new Map(B.boxes.map(x => [x.id, x]));
          const pts = (x) => {
            const cs = [[0, 0], [x.w, 0], [0, x.h], [x.w, x.h]];
            const c = Math.cos(x.rot), s = Math.sin(x.rot), kx = x.sx * x.s, ky = x.sy * x.s;
            return cs.map(([px, py]) => [x.x + (px * c - py * s) * kx, x.y + (px * s + py * c) * ky]);
          };
          let far = 0;
          for (const p of A.boxes) {
            const q = byId.get(p.id); if (!q) continue;
            const pa = pts(p), pb = pts(q), Ma = A.ms.get(p.d), Mb = B.ms.get(q.d);
            for (let i = 0; i < 4; i++) {
              const a0 = Ma.transformPoint(new DOMPoint(pa[i][0], pa[i][1])), b0 = Mb.transformPoint(new DOMPoint(pb[i][0], pb[i][1]));
              far = Math.max(far, Math.hypot(a0.x - b0.x, a0.y - b0.y));
            }
          }
          for (const [sx, sy] of [[0, 0], [this.W, 0], [0, this.H], [this.W, this.H]]) {
            const a0 = A.ms.get(0).inverse().transformPoint(new DOMPoint(sx, sy)), b0 = B.ms.get(0).inverse().transformPoint(new DOMPoint(sx, sy));
            far = Math.max(far, Math.hypot(a0.x - b0.x, a0.y - b0.y));
          }
          return far;
        },
      };
      return P;
    },

    // The pointer, painted from a path and its clicks; the cause is on screen, not implied.
    hand(el, t, LT, path, clicks, { down = 0.84, hold = 0.14 } = {}) {
      const p = LT.pointer(t, path, clicks, { down, hold });
      el.style.transform = `translate(${(p.x - 4).toFixed(1)}px,${(p.y - 3).toFixed(1)}px) scale(${p.s.toFixed(3)})`;
      return p;
    },
  };

  root.LTX = LTX;
})(typeof window !== 'undefined' ? window : globalThis);
