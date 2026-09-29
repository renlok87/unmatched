"""Side-by-side sheets of the H2 review (system Python, Pillow). Labels every panel ("concept H2 (imagegen)",
"blender: game mesh + baked 4K", "blender: Tripo high-poly") so no frame can be mistaken for an UE frame.

    python compose_review.py <profile.json> <run_dir>

Writes <run>/preview/cmp_concept_{front,side,back}.png (concept | render composited on the concept's charcoal),
<run>/preview/cmp_closeup_<name>.png (Tripo high-poly | game mesh), and sheet JPEGs for quick reading.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

profile_path, run = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
P = json.loads(profile_path.read_text(encoding="utf-8"))
REPO = Path(__file__).resolve().parents[4]
concepts = P["review"]["concepts"]
rv = run / "preview" / "review"
out = run / "preview"
BG = (46, 47, 51)
written = []
RIG = json.loads((run / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
TRIS = "%.1fk" % (RIG["measure"]["triangles_body"] / 1000.0)


def frame(path):
    """PNG as rendered, or the JPEG that store_preview.py left in its place."""
    return path if path.exists() else path.with_suffix(".jpg")


def label(img, text, xy=(12, 10)):
    d = ImageDraw.Draw(img)
    d.rectangle([xy[0] - 4, xy[1] - 3, xy[0] + 8 * len(text) + 4, xy[1] + 14], fill=(0, 0, 0))
    d.text(xy, text, fill=(255, 220, 90))


for view, rel in concepts.items():
    c = Image.open(REPO / rel).convert("RGB")
    r = Image.open(frame(rv / ("concept_frame_%s.png" % view))).convert("RGBA")
    bg = Image.new("RGBA", r.size, BG + (255,))
    bg.alpha_composite(r)
    r = bg.convert("RGB").resize(c.size, Image.LANCZOS)
    s = Image.new("RGB", (c.width * 2 + 10, c.height), (0, 0, 0))
    s.paste(c, (0, 0))
    s.paste(r, (c.width + 10, 0))
    label(s, "concept H2 (imagegen, hero-quality-v1) - %s" % view)
    label(s, "blender: game mesh %s tris + baked 4K BC/N/ORM, EEVEE preview light" % TRIS, (c.width + 22, 10))
    p = out / ("cmp_concept_%s.png" % view)
    s.save(p, optimize=True)
    written.append(p.name)

for f in sorted(list(rv.glob("closeup_*_highpoly.png")) + list(rv.glob("closeup_*_highpoly.jpg"))):
    name = f.stem[len("closeup_"):-len("_highpoly")]
    hp = Image.open(f).convert("RGB")
    lp = Image.open(frame(rv / ("closeup_%s.png" % name))).convert("RGB")
    s = Image.new("RGB", (hp.width * 2 + 10, hp.height), (0, 0, 0))
    s.paste(hp, (0, 0))
    s.paste(lp, (hp.width + 10, 0))
    label(s, "blender: Tripo high-poly 1.96M tris, Tripo 8K textures - %s" % name)
    label(s, "blender: game mesh + baked 4K atlas - %s" % name, (hp.width + 22, 10))
    p = out / ("cmp_closeup_%s.png" % name)
    s.save(p, optimize=True)
    written.append(p.name)
# K2 crops: the pixels of the game-camera frames around both figures, enlarged (nearest) for reading; the left/right
# labels come from the projected figure centres recorded by review_h2.py (review-frames-k2.json left_to_right), so a
# frame from behind (where the order flips) is labelled correctly
k2 = run / "preview" / "k2"
k2rec = json.loads((k2 / "review-frames-k2.json").read_text(encoding="utf-8"))["frames"] if (k2 / "review-frames-k2.json").exists() else {}
names = {"previous": "previous candidate 13.1k", "H2": "H2 %s" % TRIS}
for old_crop in out.glob("crop_k2*.png"):
    old_crop.unlink()
for name, rec in sorted(k2rec.items()):
    if name.startswith("_") or name.startswith("k1_") or "left_to_right" not in rec:
        continue
    f = frame(k2 / ("%s.png" % name))
    if not f.exists():
        continue
    box = (560, 380, 1360, 660) if name.startswith("k2_") else (380, 260, 1540, 700)
    im = Image.open(f).convert("RGB")
    fac = 3 if name.startswith("k2_") else 2
    c = im.crop(box).resize(((box[2] - box[0]) * fac, (box[3] - box[1]) * fac), Image.NEAREST)
    left, right = rec["left_to_right"]
    label(c, "blender, game camera az %s %.1f m, crop x%d (nearest): left = %s, right = %s"
          % (rec.get("azimuth_deg"), rec.get("distance_m", 0.0), fac, names[left], names[right]))
    p = out / ("crop_%s.png" % name)
    c.save(p, optimize=True)
    written.append(p.name)
# shape sheets: high-poly | game mesh (Workbench) from preview_lowpoly.py; the single frames are removed afterwards
# (their silhouette IoU is in preview/shape/preview-lowpoly.json)
shape = run / "preview" / "shape"
for f in sorted(shape.glob("*_hp.png")):
    tag = f.stem[:-3]
    g = shape / ("%s_lp.png" % tag)
    if not g.exists():
        continue
    a, b = Image.open(f).convert("RGB"), Image.open(g).convert("RGB")
    sh = Image.new("RGB", (a.width * 2 + 10, a.height), (0, 0, 0))
    sh.paste(a, (0, 0))
    sh.paste(b, (a.width + 10, 0))
    label(sh, "blender Workbench: Tripo high-poly - %s" % tag)
    label(sh, "blender Workbench: game mesh %s - %s" % (TRIS, tag), (a.width + 22, 10))
    p = shape / ("shape_%s.png" % tag)
    sh.save(p, optimize=True)
    f.unlink()
    g.unlink()
    written.append("shape/" + p.name)
print("COMPOSE_OK", written)
