"""H2.1 comparison sheets (system Python, Pillow + numpy): concept | H2 | H2.1 and H2 | H2.1 game frames.

    python compose_h21.py <profile.json> <run_dir>

Reads <run>/work/h21-frames/{h2,h21}_*.png (review_h21.py) and the H2 concepts; writes <run>/preview/h21/*.jpg (JPEG
q90 4:4:4) and adds the sha256 of every raw frame to <run>/preview/h21/frames-storage-h21.json. Every panel is
labelled; nothing here is an UE frame.
"""

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

profile_path, run = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
P = json.loads(profile_path.read_text(encoding="utf-8"))
REPO = Path(__file__).resolve().parents[4]
RIG = json.loads((run / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
RAW = run / "work" / "h21-frames"
OUT = run / "preview" / "h21"
OUT.mkdir(parents=True, exist_ok=True)
BG = (46, 47, 51)
K2 = P["review"].get("k2_live", {}).get("distances_m", {"5x": 3.86, "1.6x": 12.07})
GC = P["review"]["game_camera"]
written = []


def label(img, text, xy=(10, 8)):
    d = ImageDraw.Draw(img)
    d.rectangle([xy[0] - 4, xy[1] - 3, xy[0] + 7 * len(text) + 6, xy[1] + 14], fill=(0, 0, 0))
    d.text(xy, text, fill=(255, 220, 90))


def raw(who, name):
    return Image.open(RAW / ("%s_%s.png" % (who, name)))


def on_bg(im):
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, BG + (255,))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def row(panels, gap=8):
    h = max(p.height for p in panels)
    w = sum(p.width for p in panels) + gap * (len(panels) - 1)
    s = Image.new("RGB", (w, h), (0, 0, 0))
    x = 0
    for p in panels:
        s.paste(p, (x, 0))
        x += p.width + gap
    return s


def col(rows_, gap=8):
    w = max(r.width for r in rows_)
    h = sum(r.height for r in rows_) + gap * (len(rows_) - 1)
    s = Image.new("RGB", (w, h), (0, 0, 0))
    y = 0
    for r in rows_:
        s.paste(r, (0, y))
        y += r.height + gap
    return s


def save(img, name):
    p = OUT / name
    img.save(p, quality=90, subsampling=0)
    written.append(p.name)


TRIS = {"h2": "H2 (harpy-h2-bake/2, 28.5k tris)", "h21": "H2.1 (harpy-h2-bake/3, %.1fk tris)" % (
    RIG["measure"]["triangles_body"] / 1000.0)}

# 1. concept | H2 | H2.1
for view, rel in P["review"]["concepts"].items():
    c = Image.open(REPO / rel).convert("RGB")
    panels = [c]
    label(c, "concept H2 (imagegen) - %s" % view)
    for who in ("h2", "h21"):
        r = on_bg(raw(who, "concept_%s" % view)).resize(c.size, Image.LANCZOS)
        label(r, "blender: %s, baked 4K, EEVEE preview light" % TRIS[who])
        panels.append(r)
    s = row(panels)
    s = s.resize((s.width * 2 // 3, s.height * 2 // 3), Image.LANCZOS)
    save(s, "cmp_h21_concept_%s.jpg" % view)


# 2. K2 game frames (crop around the projected figure)
def project(pt, az, dist, w=1920, h=1080):
    el = math.radians(-GC["pitch_deg"])
    a_ = math.radians(az)
    d = np.array([math.sin(a_) * math.cos(el), -math.cos(a_) * math.cos(el), math.sin(el)])
    t = np.array([0.0, 0.0, 0.12])
    cam = t + d * dist
    f = -d
    right = np.cross(f, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, f)
    v = np.array(pt) - cam
    x, y, z = v @ right, v @ up, v @ f
    fx = (w / 2) / math.tan(math.radians(GC["horizontal_fov_deg"]) / 2)
    return w / 2 + fx * x / z, h / 2 - fx * y / z


for zoom, dist in sorted(K2.items()):
    tagz = zoom.replace(".", "p")
    scale = 1 if zoom == "5x" else 3
    half = (430, 300) if zoom == "5x" else (140, 95)
    rows_ = []
    for who in ("h2", "h21"):
        panels = []
        for az in (0, 40, 140, 180):
            im = raw(who, "k2_%s_az%03d" % (tagz, az)).convert("RGB")
            cxy = project((0, 0, 0.2), az, dist)
            box = (int(cxy[0] - half[0]), int(cxy[1] - half[1]), int(cxy[0] + half[0]), int(cxy[1] + half[1]))
            cr = im.crop(box)
            if scale > 1:
                cr = cr.resize((cr.width * scale, cr.height * scale), Image.NEAREST)
            label(cr, "%s | K2 %s (%.2f m) az %d%s" % (who.upper().replace("H21", "H2.1"), zoom, dist, az,
                                                       "" if scale == 1 else ", crop x%d nearest" % scale))
            panels.append(cr)
        rows_.append(row(panels))
    save(col(rows_), "cmp_h21_k2_%s.jpg" % tagz)

# 3. nape, face, talons/base close-ups: H2 | H2.1
for name, title in (("nape_game_az140", "nape, game pitch -55, az 140"), ("nape_game_az180", "nape, game pitch -55, az 180"),
                    ("nape_game_az220", "nape, game pitch -55, az 220"), ("talons_3q", "talons / bands, 3/4"),
                    ("base_band", "base, band and top")):
    panels = []
    for who in ("h2", "h21"):
        im = raw(who, name).convert("RGB")
        label(im, "blender: %s - %s" % (TRIS[who], title))
        panels.append(im)
    save(row(panels), "cmp_h21_%s.jpg" % name)

# 4. face: concept face | H2 | H2.1 close-up at the game pitch, and the K2 5x face crops (x4 nearest)
c = Image.open(REPO / P["review"]["concepts"]["front"]).convert("RGB")
cw, ch = c.size
cf = c.crop((int(cw * 0.40), int(ch * 0.20), int(cw * 0.60), int(ch * 0.47))).resize((600, 810), Image.LANCZOS)
label(cf, "concept face")
panels = [cf]
for who in ("h2", "h21"):
    im = raw(who, "face_game_az000").convert("RGB").resize((810, 810), Image.LANCZOS)
    label(im, "blender %s: face, game pitch" % who.upper().replace("H21", "H2.1"))
    panels.append(im)
top = row(panels)
fc = RIG["measure"]["face_centroid_m"]
kp = []
for who in ("h2", "h21"):
    im = raw(who, "k2_5x_az000").convert("RGB")
    x, y = project(fc, 0, K2["5x"])
    cr = im.crop((int(x - 50), int(y - 50), int(x + 50), int(y + 50))).resize((400, 400), Image.NEAREST)
    label(cr, "%s K2 5x face x4" % who.upper().replace("H21", "H2.1"))
    kp.append(cr)
    im = raw(who, "k2_1p6x_az000").convert("RGB")
    x, y = project(fc, 0, K2["1.6x"])
    cr = im.crop((int(x - 20), int(y - 20), int(x + 20), int(y + 20))).resize((400, 400), Image.NEAREST)
    label(cr, "%s K2 1.6x face x10" % who.upper().replace("H21", "H2.1"))
    kp.append(cr)
save(col([top, row(kp)]), "cmp_h21_face.jpg")

# 5. team band Gold / Silver (H2.1)
panels = []
for team in ("gold", "silver"):
    im = raw("h21", "team_%s_k2_5x" % team).convert("RGB")
    x, y = project((0, 0, 0.05), 40, K2["5x"])
    cr = im.crop((int(x - 330), int(y - 330), int(x + 330), int(y + 170)))
    label(cr, "H2.1 K2 5x az 40, team %s (base band = TeamColor, metal)" % team)
    panels.append(cr)
save(row(panels), "cmp_h21_teamcolor.jpg")

# 5b. head pitch pose probe (H2.1, K2 5x az 0, face crops x4)
hp = [RAW / ("h21_headpitch%02d_k2_5x_az000.png" % d) for d in (0, 12)]
if all(f.exists() for f in hp):
    panels = []
    for d, f in zip((0, 12), hp):
        im = Image.open(f).convert("RGB")
        x, y = project(fc, 0, K2["5x"])
        cr = im.crop((int(x - 60), int(y - 70), int(x + 60), int(y + 50))).resize((480, 480), Image.NEAREST)
        label(cr, "H2.1 K2 5x face x4, head pitch +%d deg (pose probe)" % d)
        panels.append(cr)
    save(row(panels), "cmp_h21_face_headpitch_probe.jpg")

# 6. nape visibility masks (nape_visibility.py frames: red = neck cap, green = nape fill / old patch, blue = seal core)
nf = {"h2": run / "work" / "nape-frames-h2", "h21": run / "work" / "nape-frames"}
if all(d.exists() for d in nf.values()):
    rows_ = []
    for who in ("h2", "h21"):
        for dist in ("3.86", "12.07"):
            panels = []
            for az in (0, 120, 180, 240):
                f = nf[who] / ("nape_%s_az%03d_d%s.png" % (who, az, dist))
                if not f.exists():
                    continue
                im = Image.open(f).convert("RGB")
                k = 420.0 / im.height
                im = im.resize((max(1, int(im.width * k)), 420), Image.NEAREST)
                label(im, "%s %s m az %d: red = cap" % (who.upper().replace("H21", "H2.1"), dist, az))
                panels.append(im)
            if panels:
                rows_.append(row(panels))
    if rows_:
        save(col(rows_), "cmp_h21_nape_visibility_masks.jpg")

store = {}
for f in sorted(RAW.glob("*.png")):
    store[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
(OUT / "frames-storage-h21.json").write_text(json.dumps({"raw_frames_dir": "work/h21-frames (not committed)",
                                                         "sha256": store, "sheets": written}, indent=1, sort_keys=True),
                                            encoding="utf-8")
print("COMPOSE_H21_OK", written)
