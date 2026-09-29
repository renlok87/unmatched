"""Stage `sheets` (system python, Pillow): side-by-side review sheets of the H2 candidate. Every render panel is
labelled "blender" (EEVEE studio light, not the game light); concept panels are labelled as imagegen concepts.

python sheets.py <profile.json>
Output (preview/): sbs_{front,right,back}.png (concept | blender render [| quality reference on front]),
sbs_k2_{1p6,5x}_{front,3q}.png (H2 | previous candidate, same camera, crops), closeups_sheet.png.
Report: reports/sheets-report.json (inputs and outputs with sha256).
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

BG = (24, 25, 28)
FG = (235, 235, 235)


def label(im, text, sub=None):
    bar = 44 if sub else 26
    out = Image.new("RGB", (im.width, im.height + bar), BG)
    out.paste(im, (0, bar))
    d = ImageDraw.Draw(out)
    d.text((8, 6), text, fill=FG)
    if sub:
        d.text((8, 24), sub, fill=(170, 170, 170))
    return out


def hstack(images, gap=8):
    h = max(i.height for i in images)
    w = sum(i.width for i in images) + gap * (len(images) - 1)
    out = Image.new("RGB", (w, h), BG)
    x = 0
    for i in images:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def fit_h(im, h):
    return im.resize((max(1, round(im.width * h / im.height)), h), Image.LANCZOS)


def save(im, path, outputs):
    im.save(path, format="PNG", optimize=False, compress_level=9)
    outputs[path.name] = {"path": C.rel(path), "sha256": C.sha256(path), "px": list(im.size)}


def main():
    prof = C.Profile(sys.argv[1])
    pv = prof.preview
    outputs, inputs = {}, {}
    rt = C.load_json(prof.reports / "build-report.json")
    tris = rt["measures"]["figure_triangles"]
    concept = prof["concepts"]
    for view, key in (("front", "front"), ("right", "side"), ("back", "back")):
        cpath = C.repo_path(concept[key])
        inputs[key] = {"path": concept[key], "sha256": C.sha256(cpath)}
        c = Image.open(cpath).convert("RGB")
        r = Image.open(pv / ("ortho_%s.png" % view)).convert("RGB")
        h = 1100
        panels = [label(fit_h(c, h), "CONCEPT H2 (imagegen, %s)" % key, "art/imagegen/hero-quality-v1/merlin"),
                  label(fit_h(r, h), "BLENDER render (EEVEE, studio light - not the game light)",
                        "H2 game mesh %d tris (SK) + 4K atlas, exported FBX read back" % tris)]
        if view == "front":
            q = C.repo_path(concept["quality_reference"])
            inputs["quality_reference"] = {"path": concept["quality_reference"], "sha256": C.sha256(q)}
            panels.append(label(fit_h(Image.open(q).convert("RGB"), h), "QUALITY REFERENCE (imagegen)", "medusa-quality-reference.png"))
        save(hstack(panels), pv / ("sbs_%s.png" % view), outputs)
    # K2: crops around the figure (image centre), H2 | previous
    for tag, up in (("1p6", 4), ("5x", 2)):
        for view in ("front", "3q"):
            a = Image.open(pv / ("k2_%s_%s_h2.png" % (tag, view))).convert("RGB")
            b = Image.open(pv / ("k2_%s_%s_prev.png" % (tag, view))).convert("RGB")
            # square crop around the union of both silhouettes (pixels that differ from the corner background)
            boxes = []
            for im in (a, b):
                px = im.load()
                bg = px[2, 2]
                w, h = im.size
                xs, ys = [], []
                for y in range(0, h, 2):
                    for x in range(0, w, 2):
                        p = px[x, y]
                        if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 12:
                            xs.append(x)
                            ys.append(y)
                boxes.append((min(xs), min(ys), max(xs), max(ys)))
            x0, y0 = min(bb[0] for bb in boxes), min(bb[1] for bb in boxes)
            x1, y1 = max(bb[2] for bb in boxes), max(bb[3] for bb in boxes)
            side = max(x1 - x0, y1 - y0) + 24
            cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
            box = (cx - side // 2, cy - side // 2, cx - side // 2 + side, cy - side // 2 + side)
            ca = a.crop(box).resize((side * up, side * up), Image.NEAREST)
            cb = b.crop(box).resize((side * up, side * up), Image.NEAREST)
            zoom = "crop %dx%d px of the 1920x1080 frame, nearest x%d (figure height in frame: %d px)" % (side, side, up, y1 - y0)
            sheet = hstack([label(ca, "BLENDER K2 %s %s - H2 (2K runtime atlas)" % (tag, view), zoom),
                            label(cb, "BLENDER K2 %s %s - previous CLI candidate (2K)" % (tag, view), zoom)])
            save(label(sheet, "game camera K2: horizontal FOV 35, pitch -55, D %s uu; Blender studio light, not the game light" %
                       ("1207" if tag == "1p6" else "386")), pv / ("sbs_k2_%s_%s.png" % (tag, view)), outputs)
    # close-ups
    names = ["face", "right_fist_staff", "left_fist", "crystal", "staff_mid", "feet_base", "back_hood"]
    tiles = [label(Image.open(pv / ("closeup_%s.png" % n)).convert("RGB").resize((600, 600), Image.LANCZOS),
                   "BLENDER close-up: %s (4K master)" % n) for n in names]
    rows = [hstack(tiles[i:i + 4]) for i in range(0, len(tiles), 4)]
    w = max(r.width for r in rows)
    sheet = Image.new("RGB", (w, sum(r.height for r in rows) + 8 * (len(rows) - 1)), BG)
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.height + 8
    save(sheet, pv / "closeups_sheet.png", outputs)
    C.write_json(prof.reports / "sheets-report.json", {"stage": "sheets", "profile": C.rel(prof.path), "inputs": inputs,
                                                       "outputs": outputs, "label": "blender renders vs imagegen concepts"})
    print("H2_STAGE_OK sheets")


if __name__ == "__main__":
    main()
