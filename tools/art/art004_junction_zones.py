"""Numpy-only port of the A1 junction metric (see-through pixels at the head x collar junction).

Same definitions as tools/art/art004_head_tilt_v3_mcp_review/junction_enclosed.py (scipy): part-ID
classes by colour, 4-connected labelling (scipy.ndimage.label default structure), dilation with the
4-neighbour cross (scipy.ndimage.binary_dilation default structure, border value 0), zones
face x collar, neck_back x collar and crown x collar. Blender 5.2 ships numpy but not scipy/PIL, so
art004_head_tilt_v3_measure.py (v31 mode) uses this module inside the Blender run. Equality with the
scipy version on the A1 live renders is checked by self_check() (system Python with scipy + Pillow):

  python tools/art/art004_junction_zones.py docs/game-design/evidence/ART-004/head-tilt-v3-probe-2026-09-28/blender-mcp-live

Input of enclosed_gap(): uint8 RGBA array (H, W, 4) in image row order (row 0 = top).
"""

import json
import sys

import numpy as np

PAL = {"face": (255, 0, 0), "neck_back": (255, 255, 0), "crown": (0, 255, 0), "collar": (0, 255, 255),
       "quiver": (255, 255, 255), "body": (0, 0, 0), "bow": (0, 0, 255)}
SEPARATE_PIECES = ("quiver", "bow")


def cls(rgb, c):
    return np.abs(rgb - np.array(c)).sum(axis=2) < 30


def dilate(mask, iterations):
    """scipy.ndimage.binary_dilation(mask, iterations=n) with the default cross structure."""
    out = mask.copy()
    for _ in range(iterations):
        grown = out.copy()
        grown[1:, :] |= out[:-1, :]
        grown[:-1, :] |= out[1:, :]
        grown[:, 1:] |= out[:, :-1]
        grown[:, :-1] |= out[:, 1:]
        if np.array_equal(grown, out):
            break
        out = grown
    return out


def label(mask):
    """4-connected components; labels 1..n in raster order of each component's first pixel
    (the numbering scipy.ndimage.label produces). Returns (labels int32, n)."""
    h, w = mask.shape
    runs = []  # (row, start, end_exclusive)
    row_runs = []
    for y in range(h):
        row = mask[y]
        if not row.any():
            row_runs.append((len(runs), len(runs)))
            continue
        padded = np.concatenate(([False], row, [False]))
        edges = np.flatnonzero(padded[1:] != padded[:-1])
        first = len(runs)
        for s, e in zip(edges[::2], edges[1::2]):
            runs.append((y, int(s), int(e)))
        row_runs.append((first, len(runs)))
    parent = list(range(len(runs)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for y in range(1, h):
        a0, a1 = row_runs[y - 1]
        b0, b1 = row_runs[y]
        i, j = a0, b0
        while i < a1 and j < b1:
            _, sa, ea = runs[i]
            _, sb, eb = runs[j]
            if sa < eb and sb < ea:  # 4-connectivity: column ranges overlap
                ra, rb = find(i), find(j)
                if ra != rb:
                    if ra < rb:
                        parent[rb] = ra
                    else:
                        parent[ra] = rb
            if ea < eb:
                i += 1
            else:
                j += 1
    lab = np.zeros((h, w), dtype=np.int32)
    ids = {}
    for k, (y, s, e) in enumerate(runs):  # runs are in raster order -> first-seen root order
        root = find(k)
        if root not in ids:
            ids[root] = len(ids) + 1
        lab[y, s:e] = ids[root]
    return lab, len(ids)


def _zone_gap(zone, enclosed, lab, a, masks):
    g = zone & enclosed
    l2, n2 = label(g)
    comps = []
    for i in range(1, n2 + 1):
        cm = l2 == i
        full = np.isin(lab, np.unique(lab[cm]))
        ring = dilate(full, 2) & a
        nb = {k: int((ring & m).sum()) for k, m in masks.items() if (ring & m).any()}
        ys, xs = np.nonzero(cm)
        comps.append({"px": int(cm.sum()), "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                      "region_px": int(full.sum()), "bordering": nb,
                      "between_parts": any(nb.get(k, 0) >= 10 for k in SEPARATE_PIECES)})
    comps.sort(key=lambda c: -c["px"])
    junction = sum(c["px"] for c in comps if not c["between_parts"])
    return {"zone_px": int(zone.sum()), "enclosed_gap_px": int(g.sum()),
            "junction_only_px": int(junction), "components": len(comps), "largest": comps[:4]}


def enclosed_gap(im, band):
    """im: uint8 RGBA (H, W, 4). Same keys and values as junction_enclosed.enclosed_gap(path, band)."""
    a = im[..., 3] > 127
    rgb = im[..., :3].astype(int)
    masks = {k: a & cls(rgb, c) for k, c in PAL.items()}
    face, collar = masks["face"], masks["collar"]
    dil = {k: dilate(masks[k], band) for k in ("face", "neck_back", "crown", "collar")}
    zone = dil["face"] & dil["collar"]
    lab, _n = label(~a)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    enclosed = ~a & ~np.isin(lab, list(border))
    g = zone & enclosed
    l2, n2 = label(g)
    sizes = sorted([int((l2 == i).sum()) for i in range(1, n2 + 1)], reverse=True) if n2 else []
    return {"enclosed_gap_px": int(g.sum()), "components": n2, "largest": sizes[:4],
            "face_px": int(face.sum()), "crown_px": int((a & cls(rgb, (0, 255, 0))).sum()),
            "band_px": band, "face_x_collar_zone_px": int(zone.sum()),
            "neck_back_px": int(masks["neck_back"].sum()), "collar_px": int(collar.sum()),
            "rear_zones": {"neck_back_x_collar": _zone_gap(dil["neck_back"] & dil["collar"], enclosed, lab, a, masks),
                           "crown_x_collar": _zone_gap(dil["crown"] & dil["collar"], enclosed, lab, a, masks)}}


def self_check(directory):
    """Compare with the scipy original on every id-cull-*.png in `directory` (system Python)."""
    import glob
    import os
    from PIL import Image
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(here, "art004_head_tilt_v3_mcp_review"))
    import junction_enclosed as ref  # scipy
    result = {}
    for path in sorted(glob.glob(os.path.join(directory, "id-cull-*.png"))):
        band = 3 if "k2-" in os.path.basename(path) else 40
        mine = enclosed_gap(np.array(Image.open(path).convert("RGBA")), band)
        theirs = ref.enclosed_gap(path, band)
        result[os.path.basename(path)] = json.dumps(mine, sort_keys=True) == json.dumps(theirs, sort_keys=True)
    return result


if __name__ == "__main__":
    res = self_check(sys.argv[1])
    print(json.dumps(res, indent=1))
    print("ART004_JUNCTION_ZONES_SELF_CHECK", "PASS" if res and all(res.values()) else "FAIL", len(res))
