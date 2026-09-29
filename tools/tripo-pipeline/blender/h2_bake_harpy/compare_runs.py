"""Before/after sheets of two H2 bake runs of one hero (system Python, Pillow): the same review frames of an earlier
run (e.g. a copy of the run folder kept before a rebuild) and of the current run side by side, labelled "blender".

    python compare_runs.py <old_run_dir> <new_run_dir> <out_dir> <old_label> <new_label>
        "name=old_rel:new_rel[:crop[:note]]" ...

old_rel / new_rel are paths under each run's preview/ (PNG or the JPEG store_preview.py left); crop = x0,y0,x1,y1 in
pixels applied to both frames and enlarged x2 (nearest), "-" for none; note = text of a second label line on the
sheet (e.g. which figure is which). Writes <out_dir>/before_after_<name>.png.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

old_run, new_run, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
old_label, new_label = sys.argv[4], sys.argv[5]
out.mkdir(parents=True, exist_ok=True)


def frame(run, rel):
    p = run / "preview" / rel
    for cand in (p, Path(str(p) + ".png"), Path(str(p) + ".jpg")):  # names may contain dots (d4.8)
        if cand.exists():
            return Image.open(cand).convert("RGB")
    raise FileNotFoundError(p)


def label(img, text, xy=(10, 8)):
    d = ImageDraw.Draw(img)
    d.rectangle([xy[0] - 4, xy[1] - 3, xy[0] + 7 * len(text) + 6, xy[1] + 14], fill=(0, 0, 0))
    d.text(xy, text, fill=(255, 220, 90))


for spec in sys.argv[6:]:
    name, rest = spec.split("=", 1)
    parts = rest.split(":")
    a, b = frame(old_run, parts[0]), frame(new_run, parts[1])
    if len(parts) > 2 and parts[2] != "-":
        box = tuple(int(v) for v in parts[2].split(","))
        a = a.crop(box).resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.NEAREST)
        b = b.crop(box).resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.NEAREST)
    if a.size != b.size:
        b = b.resize(a.size, Image.LANCZOS)
    sheet = Image.new("RGB", (a.width * 2 + 10, a.height), (0, 0, 0))
    sheet.paste(a, (0, 0))
    sheet.paste(b, (a.width + 10, 0))
    label(sheet, "blender, %s: %s" % (old_label, parts[0]))
    label(sheet, "blender, %s: %s" % (new_label, parts[1]), (a.width + 20, 8))
    if len(parts) > 3:
        label(sheet, parts[3], (10, 30))
    p = out / ("before_after_%s.png" % name)
    sheet.save(p, optimize=True)
    print("BEFORE_AFTER", p.name, sheet.size)
