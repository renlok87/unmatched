"""Comparison sheets for the Medusa head-tilt v3.1 probe (system Python + Pillow, deterministic).

  python tools/art/art004_head_tilt_v31_review/composites.py [LIVE_DIR]

Reads docs/game-design/evidence/ART-004/head-tilt-v31-probe-2026-09-28/ (written by
art004_head_tilt_v3_measure.py -- --v31) and writes into the same folder:
  compare-id-gate-views.png   part-ID renders, backface culling, magenta = see-through background;
                              gate views (front, 3/4 right, along D-10) + 3/4 left, v2 | v3 | v3.1 a/b/c
  compare-id-rear-views.png   rear, rear 3/4 right, side right
  compare-id-k2-face.png      K2 front D-10 300 uu, crop around the head (red = facial features z >= 42 uu,
                              magenta = throat z < 42 uu)
  compare-tex-closeups.jpg    Workbench textured close-ups (A5: hands and bow arm front/back)
With LIVE_DIR (run_live_review.py output) it also writes blender-mcp-live/*.jpg (900 px, q88) and
compare-live-blender.jpg. Live viewport frames are not byte-reproducible; the rest is.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[3]
PROBE = REPO / "docs/game-design/evidence/ART-004/head-tilt-v31-probe-2026-09-28"
TAGS = ("v2", "v3", "v31a", "v31b", "v31c")
BG = (255, 0, 255)


def on_magenta(path, colour=BG):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, colour + (255,))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def sheet(rows, cell, title):
    """rows: list of (row label, [(caption, image)])."""
    cols = max(len(r[1]) for r in rows)
    w, h = cols * (cell[0] + 6) + 6, 24 + len(rows) * (cell[1] + 22)
    out = Image.new("RGB", (w, h), (24, 24, 24))
    d = ImageDraw.Draw(out)
    d.text((6, 6), title, fill=(255, 255, 255))
    y = 24
    for _label, items in rows:
        for k, (cap, im) in enumerate(items):
            x = 6 + k * (cell[0] + 6)
            out.paste(im.resize(cell), (x, y + 18))
            d.text((x + 2, y + 3), cap, fill=(255, 230, 0))
        y += cell[1] + 22
    return out


def main():
    m = json.loads((PROBE / "blender-measurements.json").read_text(encoding="utf-8"))
    views = m["part_id_views"]

    def id_rows(names, metric):
        rows = []
        for v in names:
            items = []
            for t in TAGS:
                val = views[t][v][metric]["enclosed_gap_px" if metric == "face_x_collar" else "junction_only_px"]
                items.append((f"{v} {t}: {val}", on_magenta(PROBE / f"id-cull-{v}-{t}.png")))
            rows.append((v, items))
        return rows
    sheet(id_rows(("neck-front", "neck-front34R", "neck-top55", "neck-front34L"), "face_x_collar"), (256, 256),
          "Medusa v2 | v3 | v3.1a | v3.1b | v3.1c - part-ID, backface culling, magenta = see-through; "
          "caption = enclosed px in the face x collar zone (ortho 16 cm, 1 px = 0.024 mm2)"
          ).save(PROBE / "compare-id-gate-views.png", optimize=True)
    rear = []
    for v in ("neck-rear", "neck-rear34R", "neck-sideR"):
        items = []
        for t in TAGS:
            nb = views[t][v]["neck_back_x_collar"]["junction_only_px"]
            cr = views[t][v]["crown_x_collar"]["junction_only_px"]
            items.append((f"{v} {t}: nb {nb} / cr {cr}", on_magenta(PROBE / f"id-cull-{v}-{t}.png")))
        rear.append((v, items))
    sheet(rear, (256, 256), "Rear junction zones (junction-only px): nb = neck_back x collar, cr = crown x collar"
          ).save(PROBE / "compare-id-rear-views.png", optimize=True)
    k2 = []
    for t in TAGS:
        im = on_magenta(PROBE / f"idsplit-k2-front-d300-{t}.png", (48, 48, 48)).crop((840, 330, 1040, 510))
        feat = views[t]["idsplit-k2-front-d300"]["facial_features_z_ge_42_px"]
        k2.append((f"{t}: features {feat} px", im))
    sheet([("k2", k2)], (300, 270), "K2 front D-10 300 uu, 1920x1080 crop x1.5: red = facial features (z >= 42 uu), "
          "magenta = throat, green = crown, grey = background").save(PROBE / "compare-id-k2-face.png", optimize=True)
    tex_rows = []
    for v in m["textured_closeups"]["views"]:
        items = [(f"{v} {t}", Image.open(PROBE / f"{v}-{t}.jpg").convert("RGB"))
                 for t in ("v2", "v31a", "v31b", "v31c")]
        tex_rows.append((v, items))
    sheet(tex_rows, (300, 300), "Workbench textured close-ups (atlas BaseColor, studio light, backface culling): "
          "v2 | v3.1a | v3.1b | v3.1c").save(PROBE / "compare-tex-closeups.jpg", quality=88)
    if len(sys.argv) > 1:
        live = Path(sys.argv[1])
        out = PROBE / "blender-mcp-live"
        out.mkdir(exist_ok=True)
        record = (live / "live-review.json").read_text(encoding="utf-8")
        (out / "live-review.json").write_text(record, encoding="utf-8")
        shots = json.loads(record)["shots"]
        for name, file in shots.items():
            im = Image.open(live / file).convert("RGB")
            im.thumbnail((900, 900))
            im.save(out / f"{name}-blender-live.jpg", quality=88)
        pairs = [("neck34R-v2", "neck34R-v31a"), ("rear34L-v2", "rear34L-v31a"), ("bowarm-rear-v2", "bowarm-rear-v31a")]
        rows = []
        for a, b in pairs:
            items = []
            for n in (a, b):
                im = Image.open(live / shots[n]).convert("RGB")
                w, h = im.size
                items.append((n, im.crop((0, (h - w) // 2, w, (h - w) // 2 + w))))
            rows.append((a, items))
        sheet(rows, (400, 400), "Live Blender 5.2.2 viewport (isolated scene, textured, backface culling): v2 | v3.1a"
              ).save(PROBE / "compare-live-blender.jpg", quality=88)
    print("ART004_V31_COMPOSITES_OK", PROBE)


if __name__ == "__main__":
    main()
