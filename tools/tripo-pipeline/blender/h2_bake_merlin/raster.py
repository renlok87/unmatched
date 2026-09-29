"""numpy-only UV triangle rasteriser (pixel centres, strict inside test) shared by the Blender UV stage and maps.py.

Row 0 of the arrays is v = 0 (bottom), as Blender stores images; x = u * size. A texel whose centre lies exactly on a
shared edge belongs to no triangle, so two triangles that only share an edge never both cover a texel: a texel
covered twice is a real overlap.
"""

import math

import numpy as np


def raster(uv_tris, size, values_list=(), on_overlap=None):
    """uv_tris [T,3,2]. values_list: (per-triangle values, out array [size,size]) written where a triangle covers.
    on_overlap(t, previous_values_of_first_list_at_the_overlap) is called for triangles hitting covered texels.
    Returns the coverage count [size,size] (uint16)."""
    count = np.zeros((size, size), np.uint16)
    P = np.asarray(uv_tris, np.float64) * size
    for t in range(len(P)):
        (x0, y0), (x1, y1), (x2, y2) = P[t]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if area == 0:
            continue
        if area < 0:
            x1, y1, x2, y2 = x2, y2, x1, y1
        xa, xb = int(math.floor(min(x0, x1, x2) - 0.5)), int(math.ceil(max(x0, x1, x2) - 0.5))
        ya, yb = int(math.floor(min(y0, y1, y2) - 0.5)), int(math.ceil(max(y0, y1, y2) - 0.5))
        xa, ya = max(xa, 0), max(ya, 0)
        xb, yb = min(xb, size - 1), min(yb, size - 1)
        if xb < xa or yb < ya:
            continue
        X, Y = np.meshgrid(np.arange(xa, xb + 1) + 0.5, np.arange(ya, yb + 1) + 0.5)
        w0 = (x1 - X) * (y2 - Y) - (x2 - X) * (y1 - Y)
        w1 = (x2 - X) * (y0 - Y) - (x0 - X) * (y2 - Y)
        w2 = (x0 - X) * (y1 - Y) - (x1 - X) * (y0 - Y)
        inside = (w0 > 0) & (w1 > 0) & (w2 > 0)
        if not inside.any():
            continue
        sub = (slice(ya, yb + 1), slice(xa, xb + 1))
        if on_overlap is not None:
            hit = count[sub][inside] > 0
            if hit.any():
                prev = values_list[0][1][sub][inside][hit] if values_list else None
                on_overlap(t, prev)
        count[sub] += inside
        for vals, out in values_list:
            region = out[sub]
            region[inside] = vals[t]
    return count
