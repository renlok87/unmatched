"""Enclosed see-through pixels at the head x collar junction (Blender part-ID renders).

Zones (dilation of both classes by `band` px, then intersected):
- face_x_collar: face/throat (part 10, red) x collar (part 3, cyan) - the front
  metric used for P1. Its keys `enclosed_gap_px`/`components`/`largest` are unchanged.
- rear_zones.neck_back_x_collar: rear neck (part 14, yellow) x collar.
- rear_zones.crown_x_collar: crown (part 1, green) x collar.
Added after the verifier (vc, 2026-09-28) showed that in rear views the face zone
is empty, so "0 holes" there was 0 by construction. Rear numbers are recomputed on
the same renders from <scratch>/blender/renders (no new Blender run; scratch = _paths.SCRATCH,
default C:/tmp/a1v3).

"Enclosed" = transparent pixels not connected to the image border. A component
whose whole enclosed region touches the quiver (white) or bow (blue) with >= 10 px
is reported as `between_parts` (background seen between separate pieces, e.g. the
gap crown/collar/quiver strap), not as a hole in the neck junction.
"""
import json, glob, os
import numpy as np
from PIL import Image
from scipy import ndimage

PAL = {"face": (255, 0, 0), "neck_back": (255, 255, 0), "crown": (0, 255, 0), "collar": (0, 255, 255),
       "quiver": (255, 255, 255), "body": (0, 0, 0), "bow": (0, 0, 255)}
SEPARATE_PIECES = ("quiver", "bow")


def cls(rgb, c):
    return np.abs(rgb - np.array(c)).sum(axis=2) < 30


def _zone_gap(zone, enclosed, lab, a, masks):
    g = zone & enclosed
    l2, n2 = ndimage.label(g)
    comps = []
    for i in range(1, n2 + 1):
        cm = l2 == i
        full = np.isin(lab, np.unique(lab[cm]))
        ring = ndimage.binary_dilation(full, iterations=2) & a
        nb = {k: int((ring & m).sum()) for k, m in masks.items() if (ring & m).any()}
        ys, xs = np.nonzero(cm)
        comps.append({"px": int(cm.sum()), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                      "region_px": int(full.sum()), "bordering": nb,
                      "between_parts": any(nb.get(k, 0) >= 10 for k in SEPARATE_PIECES)})
    comps.sort(key=lambda c: -c["px"])
    junction = sum(c["px"] for c in comps if not c["between_parts"])
    return {"zone_px": int(zone.sum()), "enclosed_gap_px": int(g.sum()),
            "junction_only_px": int(junction), "components": len(comps), "largest": comps[:4]}


def enclosed_gap(path, band):
    im = np.array(Image.open(path).convert("RGBA")); a = im[..., 3] > 127; rgb = im[..., :3].astype(int)
    masks = {k: a & cls(rgb, c) for k, c in PAL.items()}
    face, collar = masks["face"], masks["collar"]
    dil = {k: ndimage.binary_dilation(masks[k], iterations=band) for k in ("face", "neck_back", "crown", "collar")}
    zone = dil["face"] & dil["collar"]
    lab, n = ndimage.label(~a)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    enclosed = ~a & ~np.isin(lab, list(border))
    g = zone & enclosed
    l2, n2 = ndimage.label(g)
    sizes = sorted([int(s) for s in ndimage.sum(g, l2, range(1, n2 + 1))], reverse=True) if n2 else []
    return {"enclosed_gap_px": int(g.sum()), "components": n2, "largest": sizes[:4],
            "face_px": int(face.sum()), "crown_px": int((a & cls(rgb, (0, 255, 0))).sum()),
            "band_px": band, "face_x_collar_zone_px": int(zone.sum()),
            "neck_back_px": int(masks["neck_back"].sum()), "collar_px": int(collar.sum()),
            "rear_zones": {"neck_back_x_collar": _zone_gap(dil["neck_back"] & dil["collar"], enclosed, lab, a, masks),
                           "crown_x_collar": _zone_gap(dil["crown"] & dil["collar"], enclosed, lab, a, masks)}}


if __name__ == "__main__":
    from _paths import SCRATCH  # imported here so enclosed_gap() can be imported from any directory
    res = {}
    for p in sorted(glob.glob(SCRATCH + "blender/renders/id-cull-*.png")):
        res[os.path.basename(p)] = enclosed_gap(p, 3 if "k2-" in p else 40)
    json.dump(res, open(SCRATCH + "blender/junction_enclosed.json", "w"), indent=1)
