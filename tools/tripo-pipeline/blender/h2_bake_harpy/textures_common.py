"""Helpers of the H2 texture post-process (system Python, numpy/scipy/Pillow). Raster arrays use the Blender image
order (row 0 = v = 0 = bottom); PNGs are written top row first (np.flipud)."""

import hashlib
import json
from pathlib import Path

import numpy as np

PART_RGB = [(230, 77, 64), (64, 153, 230), (242, 204, 51), (102, 204, 102), (204, 102, 230), (242, 140, 38),
            (77, 230, 217), (153, 153, 153), (230, 115, 166), (128, 89, 51), (51, 89, 191), (191, 230, 77),
            (242, 242, 242), (89, 51, 128)]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def rasterise(uv, label, n, first=None):
    """Pixel-centre rasteriser: returns (label map int32, -1 empty; cover count uint8). uv: (T, 3, 2) in 0..1.
    first: optional int32 (n, n) array filled with the FIRST label written to each texel (overlap diagnostics)."""
    lab = np.full((n, n), -1, np.int32)
    cover = np.zeros((n, n), np.uint8)
    pts = uv * n
    for t in range(len(pts)):
        (x0, y0), (x1, y1), (x2, y2) = pts[t]
        xmin = max(int(np.floor(min(x0, x1, x2) - 0.5)), 0)
        xmax = min(int(np.ceil(max(x0, x1, x2) - 0.5)), n - 1)
        ymin = max(int(np.floor(min(y0, y1, y2) - 0.5)), 0)
        ymax = min(int(np.ceil(max(y0, y1, y2) - 0.5)), n - 1)
        if xmax < xmin or ymax < ymin:
            continue
        xs = np.arange(xmin, xmax + 1) + 0.5
        ys = np.arange(ymin, ymax + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if abs(area) < 1e-12:
            continue
        w0 = (x1 - gx) * (y2 - gy) - (x2 - gx) * (y1 - gy)
        w1 = (x2 - gx) * (y0 - gy) - (x0 - gx) * (y2 - gy)
        w2 = (x0 - gx) * (y1 - gy) - (x1 - gx) * (y0 - gy)
        if area < 0:
            w0, w1, w2 = -w0, -w1, -w2
        eps = -1e-9 * abs(area)
        inside = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not inside.any():
            continue
        iy, ix = np.nonzero(inside)
        iy += ymin
        ix += xmin
        if first is not None:
            fresh = lab[iy, ix] < 0
            first[iy[fresh], ix[fresh]] = label[t]
        lab[iy, ix] = label[t]
        cover[iy, ix] = np.minimum(cover[iy, ix].astype(np.int32) + 1, 255).astype(np.uint8)
    return lab, cover
