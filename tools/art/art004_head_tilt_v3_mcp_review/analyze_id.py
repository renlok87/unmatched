import json, sys, glob, os
import numpy as np
from PIL import Image
from scipy import ndimage
PAL = {"face": (255, 0, 0), "neck_back": (255, 255, 0), "crown": (0, 255, 0), "collar": (0, 255, 255),
       "quiver": (255, 255, 255), "body": (0, 0, 0), "bow": (0, 0, 255)}
def analyze(path):
    im = np.array(Image.open(path).convert("RGBA"))
    a = im[..., 3] > 127
    rgb = im[..., :3].astype(int)
    out = {"figure_px": int(a.sum())}
    for k, c in PAL.items():
        out[k + "_px"] = int((a & (np.abs(rgb - np.array(c)).sum(axis=2) < 30)).sum())
    bg = ~a
    lab, n = ndimage.label(bg)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    holes = [(i, int((lab == i).sum())) for i in range(1, n + 1) if i not in border]
    holes = [(i, s) for i, s in holes if s >= 1]
    out["enclosed_holes"] = len(holes)
    out["enclosed_hole_px"] = int(sum(s for _, s in holes))
    big = sorted(holes, key=lambda t: -t[1])[:6]
    out["largest_holes"] = []
    for i, s in big:
        ys, xs = np.nonzero(lab == i)
        # which classes border the hole
        ring = ndimage.binary_dilation(lab == i, iterations=2) & a
        nb = {k: int((ring & (np.abs(rgb - np.array(c)).sum(axis=2) < 30)).sum()) for k, c in PAL.items()}
        out["largest_holes"].append({"px": s, "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                                     "bordering": {k: v for k, v in nb.items() if v}})
    return out
if __name__ == "__main__":
    res = {}
    for p in sorted(glob.glob(sys.argv[1])):
        res[os.path.basename(p)] = analyze(p)
    json.dump(res, open(sys.argv[2], "w"), indent=1)
    for k, v in res.items():
        print(k, {x: v[x] for x in ("figure_px", "face_px", "neck_back_px", "crown_px", "collar_px", "quiver_px", "enclosed_holes", "enclosed_hole_px")})
