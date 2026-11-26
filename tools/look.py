#!/usr/bin/env python3
"""look.py — a look as eight colour tokens and three faces, applied to a composition as CSS variables.

  python3 tools/look.py list
  python3 tools/look.py sheet --out gallery/looks.png
  python3 tools/look.py apply slate cases/hello-12s/comp.html
  python3 tools/look.py from-shot shots/home.png --name mine --out looks/mine.json
  python3 tools/look.py apply looks/mine.json comp.html

Tokens: ground deep card line mute ink accent accent2. A look is picked by name in the concept round,
never silently defaulted. `apply` writes look.js beside the comp — variables plus the three faces
subset to the glyphs the comp actually sets and inlined — and links it before the comp's own script.
Comp code writes against var(--ink), var(--display), var(--text), var(--mono).

`apply` names every character a face cannot set (add a fallback face with --cjk, or change copy).
"""
import argparse, base64, json, os, subprocess, sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS = os.path.join(HERE, "looks", "looks.json")
FONTS = os.path.join(HERE, "looks", "fonts")
SLOTS = ("display", "text", "mono")
ROLES = ("ground", "deep", "card", "line", "mute", "ink", "accent", "accent2")


def load(path=PRESETS):
    return json.load(open(path))


def pick(name):
    lib = load()
    if name in lib["looks"]:
        return name, lib["looks"][name]
    if os.path.exists(name):
        d = json.load(open(name))
        return d.get("name", os.path.basename(name)), d
    raise SystemExit(f"no look {name}; try: {', '.join(lib['looks'])}")


def subset(face_file, text, weight):
    """Woff2 bytes for `text` only, or the whole face if fonttools is missing."""
    path = os.path.join(FONTS, face_file)
    try:
        from fontTools import subset as sub
        from fontTools.ttLib import TTFont
        opts = sub.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga", "calt", "ss01", "cv11"]
        opts.drop_tables += ["DSIG"]
        font = TTFont(path)
        sub.Subsetter(options=opts).subset(font)
        tmp = path + ".woff2"
        font.flavor = "woff2"
        font.save(tmp)
        data = open(tmp, "rb").read()
        os.unlink(tmp)
        return data
    except Exception:
        return open(path, "rb").read()


def missing(face_file, text):
    try:
        from fontTools.ttLib import TTFont
        cmap = TTFont(os.path.join(FONTS, face_file)).getBestCmap()
        return sorted({c for c in text if ord(c) > 32 and ord(c) not in cmap})
    except Exception:
        return []


def sheet(out):
    lib = load()
    cols, cell, top = len(lib["looks"]), 300, 96
    im = Image.new("RGB", (cols * cell, top + 236), "#ffffff")
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(os.path.join(FONTS, "Inter.ttf"), 17)
        small = ImageFont.truetype(os.path.join(FONTS, "Inter.ttf"), 13)
    except Exception:
        font = small = ImageFont.load_default()
    for i, (name, look) in enumerate(lib["looks"].items()):
        c = look["color"]
        x = i * cell
        d.rectangle([x, 0, x + cell - 1, top + 235], fill=c["ground"])
        d.text((x + 16, 14), name, font=font, fill=c["ink"])
        d.text((x + 16, 40), look["mood"], font=small, fill=c["mute"])
        d.rounded_rectangle([x + 16, 84, x + cell - 16, 176], 12, fill=c["card"], outline=c["line"])
        d.text((x + 30, 100), "Aa", font=ImageFont.truetype(os.path.join(FONTS, look["type"]["display"]["file"]), 48), fill=c["ink"])
        d.rectangle([x + 16, 190, x + cell - 16, 202], fill=c["line"])
        d.rectangle([x + 16, 190, x + 80, 202], fill=c["accent"])
        for j, k in enumerate(ROLES):
            d.rectangle([x + 16 + j * 33, 214, x + 16 + j * 33 + 28, 232], fill=c[k])
    im.save(out)
    print("wrote", out)


def apply(name, comp, cjk=None):
    look_name, look = pick(name)
    text = open(comp, encoding="utf-8").read()
    glyphs = "".join(sorted({c for c in text if ord(c) > 32})) + " !\"'()[]{}.,:;-_/\\@#%&*+=0123456789"
    warn, css, meta = [], [], {}
    for slot in SLOTS:
        spec = look["type"][slot]
        files = [spec["file"]] + ([cjk + ".ttf"] if cjk else [])
        family = f"LT-{slot}"
        meta[slot] = {"family": family, "weight": str(spec.get("weight", "400"))}
        for f in files:
            if not os.path.exists(os.path.join(FONTS, f)):
                sys.exit(f"missing face {f} in looks/fonts")
            miss = missing(f, glyphs)
            if miss:
                warn.append(f"{slot} face {f} lacks {' '.join(miss[:24])}")
            b64 = base64.b64encode(subset(f, glyphs, spec.get("weight", "400"))).decode()
            css.append("@font-face{font-family:'%s';font-weight:%s;font-display:block;src:url(data:font/woff2;base64,%s)}"
                       % (family, spec.get("weight", "400"), b64))
    props = "".join(f"--{k}:{look['color'][k]};" for k in ROLES)
    fallback = {"display": look["type"]["display"].get("fallback", "Georgia, serif"),
                "text": look["type"]["text"].get("fallback", "system-ui, sans-serif"),
                "mono": look["type"]["mono"].get("fallback", "ui-monospace, Menlo, monospace")}
    js = ["/* longtake look: %s — generated by tools/look.py */" % look_name, "(function(){"]
    js.append("const c=%s;const s=document.documentElement.style;for(const k in c)s.setProperty('--'+k,c[k]);" % json.dumps(look["color"]))
    for slot in SLOTS:
        js.append("s.setProperty('--%s',%s);" % (slot, json.dumps(meta[slot]["family"] + ", " + fallback[slot])))
    js.append("const F=(f,a,w)=>{try{document.fonts.add(new FontFace(f,'url(data:font/woff2;base64,'+a+')',{weight:w}))}catch(e){}};")
    for slot, rule in zip(SLOTS, css):
        b64 = rule.split("base64,")[1].rstrip("}")
        js.append("F('%s',%s,'%s');" % (meta[slot]["family"], json.dumps(b64), meta[slot]["weight"]))
    js.append("window.LOOK={name:%s,color:c,ready:document.fonts.ready,fallback:%s,"
              "family:s=>({%s})[s],weight:s=>({%s})[s],"
              "font:(s,size,w)=>`${w||(%s)[s]} ${size}px ${({%s})[s]}`};"
              % (json.dumps(look_name), json.dumps(fallback),
                 ",".join(f"{k}:'{meta[k]['family']}'" for k in SLOTS),
                 ",".join(f"{k}:'{meta[k]['weight']}'" for k in SLOTS),
                 json.dumps({k: meta[k]["weight"] for k in SLOTS}),
                 ",".join(f"{k}:'{meta[k]['family']}'" for k in SLOTS)))
    js.append("})();")
    out = os.path.join(os.path.dirname(os.path.abspath(comp)), "look.js")
    open(out, "w").write("\n".join(js) + "\n")
    if 'id="lt-look"' not in text:
        text = text.replace("<head>", f'<head>\n<style id="lt-look">:root{{{props}}}</style>\n', 1)
        text = text.replace("<script", '<script src="look.js"></script>\n<script', 1)
        open(comp, "w", encoding="utf-8").write(text)
    print(f"applied {look_name} → {out}")
    if warn:
        print("glyph warnings:\n  " + "\n  ".join(warn))


def from_shot(path, name, out):
    im = Image.open(path).convert("RGB")
    im.thumbnail((160, 160))
    px = list(im.getdata())
    import random
    random.Random(3).shuffle(px)
    centers = px[:8]
    for _ in range(24):
        buckets = [[] for _ in centers]
        for p in px[:: max(1, len(px) // 4000)]:
            k = min(range(len(centers)), key=lambda i: sum((p[j] - centers[i][j]) ** 2 for j in range(3)))
            buckets[k].append(p)
        centers = [tuple(int(sum(c[j] for c in b) / len(b)) for j in range(3)) if b else centers[i] for i, b in enumerate(buckets)]
    centers.sort(key=lambda c: sum(c))
    hexd = lambda c: "#%02x%02x%02x" % c
    lum = [sum(c) / 3 for c in centers]
    look = {"name": name, "mood": "picked from " + os.path.basename(path), "color": {
        "ground": hexd(centers[7]), "deep": hexd(centers[0]), "card": hexd(centers[6]), "line": hexd(centers[5]),
        "mute": hexd(centers[4]), "ink": hexd(centers[1]), "accent": hexd(centers[2]), "accent2": hexd(centers[3])},
        "type": {"display": {"face": "Fraunces", "weight": 400}, "text": {"face": "Inter", "weight": 500}, "mono": {"face": "Geist Mono", "weight": 400}}}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    json.dump(look, open(out, "w"), indent=1)
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["list", "sheet", "apply", "from-shot", "check"])
    ap.add_argument("arg", nargs="?"); ap.add_argument("comp", nargs="?")
    ap.add_argument("--out", default="gallery/looks.png"); ap.add_argument("--name"); ap.add_argument("--cjk")
    a = ap.parse_args()
    if a.cmd == "list":
        for k, v in load()["looks"].items():
            print(f"{k:10} {v['mood']}")
    elif a.cmd == "sheet":
        sheet(a.out)
    elif a.cmd == "apply":
        if not a.arg or not a.comp: sys.exit("apply <look> <comp.html>")
        apply(a.arg, a.comp, a.cjk)
    elif a.cmd == "from-shot":
        from_shot(a.arg, a.name or "from-shot", a.out)
    elif a.cmd == "check":
        for k in load()["looks"]:
            print(f"{k:10} ok")


if __name__ == "__main__":
    main()
