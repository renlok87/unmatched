"""AN-31 frames: K2x1.6 / K1 crops of the three harpy bases (head socket + offset), colour + grey, and the digit height
(the cream glyph: R,G,B >= 200 and R-B <= 60, the connected run nearest the base point), per run."""
import sys, re, json
import numpy as np
from PIL import Image, ImageOps, ImageDraw
from scipy import ndimage
VIEWS = ["K1", "K2x1p6", "K2x2p5"]
def heads(run):
    out = {}
    lines = [l for l in open(f"{run}/bench.trace.log", encoding="utf-8", errors="replace") if "SHOT head fighter=f-0-sk" in l]
    lines = lines[-9:]
    for i, l in enumerate(lines):
        m = re.search(r"fighter=(f-0-sk\d) .*? screen=\(([\d.]+),([\d.]+)\).*headPx=([\d.]+)", l)
        out.setdefault(VIEWS[i // 3], []).append((m.group(1), float(m.group(2)), float(m.group(3)), float(m.group(4))))
    return out
def digit(a, cx, cy, r):
    sub = a[int(cy - r):int(cy + r), int(cx - r):int(cx + r)].astype(int)
    navy = (sub.max(-1) <= 70) & (sub[..., 2] >= sub[..., 0])
    lab, n = ndimage.label(ndimage.binary_closing(navy, iterations=2))
    if not n: return None
    sizes = ndimage.sum(navy, lab, range(1, n + 1)); k = int(np.argmax(sizes)) + 1
    disc = ndimage.binary_fill_holes(lab == k)
    ys, xs = np.nonzero(disc)
    cream = (sub.min(-1) >= 140) & ((sub[..., 0] - sub[..., 2]) <= 70) & disc
    gy, gx = np.nonzero(cream)
    if not len(gy): return {"discH": int(np.ptp(ys) + 1), "discW": int(np.ptp(xs) + 1), "digitH": 0}
    return {"discH": int(np.ptp(ys) + 1), "discW": int(np.ptp(xs) + 1), "digitH": int(np.ptp(gy) + 1), "digitW": int(np.ptp(gx) + 1)}
def sheet(out, runs, view, off, half, scale):
    rows = []; meas = {}
    for run in runs:
        a = np.asarray(Image.open(f"{run}/bench-{view}-1920x1080.png").convert("RGB"))
        im = Image.fromarray(a); tiles = []
        for fid, x, y, hp in sorted(heads(run)[view]):
            cx, cy = x, y + off * hp
            tiles.append(im.crop((int(cx - half), int(cy - half), int(cx + half), int(cy + half))).resize((2 * half * scale, 2 * half * scale), Image.NEAREST))
            meas.setdefault(run.split("/")[-1], {})[fid] = digit(a, cx, cy, half)
        rows.append((run.split("/")[-1], tiles))
    t = rows[0][1][0].size[0]
    W = Image.new("RGB", (t * 6 + 12, (t + 16) * len(rows)), (24, 24, 24)); d = ImageDraw.Draw(W)
    for i, (name, tiles) in enumerate(rows):
        for j, tl in enumerate(tiles):
            W.paste(tl, (j * t, i * (t + 16) + 16)); W.paste(ImageOps.grayscale(tl).convert("RGB"), (3 * t + 12 + j * t, i * (t + 16) + 16))
        d.text((4, i * (t + 16) + 2), f"{name} {view}  (colour | grey)  harpies 1, 2, 3", fill=(255, 255, 255))
    W.save(out)
    return meas
if __name__ == "__main__":
    out, view, off, half, scale = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    print(json.dumps(sheet(out, sys.argv[6:], view, off, half, scale)))
