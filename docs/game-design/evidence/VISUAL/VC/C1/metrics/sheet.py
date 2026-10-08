"""sheet.py <out.jpg> <label=run>... : Medusa head crops K2x1.6 (x6) and K2x2.5 (x5), colour | grey, one row per run."""
import sys, re
from PIL import Image, ImageOps, ImageDraw
out = sys.argv[1]; items = [a.split("=", 1) for a in sys.argv[2:]]
def head(run, view_idx):
    ls = [l for l in open(f"{run}/bench.trace.log", encoding="utf-8", errors="replace") if "SHOT head fighter=f-0-hero" in l][-3:]
    m = re.search(r"screen=\(([\d.]+),([\d.]+)\)", ls[view_idx]); return float(m.group(1)), float(m.group(2))
tiles = []
for label, run in items:
    row = []
    for vi, view, half, sc in ((1, "K2x1p6", 18, 8), (2, "K2x2p5", 28, 5)):
        x, y = head(run, vi); y += half * 0.25
        im = Image.open(f"{run}/bench-{view}-1920x1080.png").convert("RGB").crop((int(x - half), int(y - half), int(x + half), int(y + half)))
        im = im.resize((2 * half * sc, 2 * half * sc), Image.LANCZOS)
        row += [im, ImageOps.grayscale(im).convert("RGB")]
    tiles.append((label, row))
w = sum(t.size[0] for t in tiles[0][1]) + 8 * 3; h = tiles[0][1][0].size[1]
W = Image.new("RGB", (w, (h + 18) * len(tiles)), (24, 24, 24)); d = ImageDraw.Draw(W)
for i, (label, row) in enumerate(tiles):
    x = 0
    for t in row: W.paste(t, (x, i * (h + 18) + 18)); x += t.size[0] + 8
    d.text((4, i * (h + 18) + 3), f"{label}   K2x1.6 colour | grey      K2x2.5 colour | grey", fill=(255, 255, 255))
W.save(out, quality=88); print(out, W.size)
