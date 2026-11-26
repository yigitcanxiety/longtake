/* longtake · lib/ui.js — a product interface rebuilt on a plane. MIT.
 *
 * For demos: screenshot the product as reference, rebuild the interface in HTML in its own
 * pixel frame, and put that frame on a plane the camera can fly into at any zoom. Every string
 * lives in a table, every state is written by one set(state), so a second language is ?lang=
 * on the same comp instead of a second comp.
 *
 *   const U = UIK.plane(stage, {w: 1440, h: 900, at: {x: 240, y: 90}, scale: 0.62});
 *   const r = UIK.rect(screenEl, U);      // screen-space box for __frames / highlights
 *
 * Narrated demos: UIK.warp() maps a narration's word times onto the authored timeline and
 * UIK.subs() renders chunked subtitles from the same table.
 */
(function (root) {
  'use strict';

  const UIK = {
    // A plane: design px × scale, anchored at `at` in the scene. Returns the element and its frame.
    plane(stage, { w, h, at = { x: 0, y: 0 }, scale = 1, depth = 0 } = {}) {
      const el = document.createElement('div');
      el.style.cssText = `position:absolute;left:${at.x}px;top:${at.y}px;width:${w}px;height:${h}px;` +
        `transform-origin:0 0;transform:scale(${scale});background:#fff`;
      el.dataset.plane = depth;
      stage.appendChild(el);
      return { el, w, h, scale, at, depth };
    },

    // Screen-space rect of an element on a plane (the plane's own transform included).
    rect(el, plane) {
      const a = el.getBoundingClientRect();
      return { x: a.left, y: a.top, w: a.width, h: a.height, k: plane.scale };
    },

    // Screen px per design px at the current camera zoom — is this text still legible?
    legible(plane, zoom = 1) { return plane.scale * zoom; },

    // The zoom at which a design size reaches minPx on screen.
    zoomFor(plane, designPx, minPx = 11) { return minPx / (designPx * plane.scale); },

    // A ring that hugs its content plus padding, in design px.
    ring(el, pad = 8) { const r = el.getBoundingClientRect(); return { x: r.left - pad, y: r.top - pad, w: r.width + pad * 2, h: r.height + pad * 2, r: (r.height + pad * 2) / 2 }; },

    // A screenshot as a reference backing, sized to the plane.
    shot(plane, src) {
      const img = document.createElement('img');
      img.src = src; img.alt = '';
      img.style.cssText = `position:absolute;inset:0;width:100%;height:100%;object-fit:cover`;
      plane.el.appendChild(img);
      return img;
    },

    // Strings by language, with a missing key falling back to the source language.
    strings(table, lang = 'en', fallback = 'en') { return k => (table[lang] && table[lang][k]) ?? table[fallback][k]; },

    // Map a narration time (word times, seconds) onto the authored timeline.
    warp(knots) {
      const ks = knots.slice().sort((a, b) => a[0] - b[0]);
      return t => {
        if (t <= ks[0][0]) return ks[0][1] + (t - ks[0][0]);
        for (let i = 1; i < ks.length; i++) if (t <= ks[i][0]) {
          const k = (t - ks[i - 1][0]) / (ks[i][0] - ks[i - 1][0]);
          return ks[i - 1][1] + (ks[i][1] - ks[i - 1][1]) * k;
        }
        return ks[ks.length - 1][1] + (t - ks[ks.length - 1][0]);
      };
    },

    // Subtitles from [[t0, t1, text], …] in the authored timeline; the active one is shown.
    subs(stage, chunks, { size = 30, bottom = 54 } = {}) {
      const el = document.createElement('div');
      el.style.cssText = `position:absolute;left:0;right:0;bottom:${bottom}px;text-align:center;font:500 ${size}px system-ui;color:#fff;text-shadow:0 2px 12px rgba(0,0,0,.6);pointer-events:none`;
      stage.appendChild(el);
      return t => { const c = chunks.find(([a, b]) => t >= a && t < b); el.textContent = c ? c[2] : ''; el.style.opacity = c ? 1 : 0; };
    },

    // A font face for a language, loaded once; returns a promise the comp can await.
    async font(family, url) {
      const f = new FontFace(family, `url(${url})`);
      await f.load(); document.fonts.add(f);
      return family;
    },
  };

  root.UIK = UIK;
})(typeof window !== 'undefined' ? window : globalThis);
