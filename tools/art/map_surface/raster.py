"""Rasterise the vector game layer into N x N texture space (same UV as the BC).

Texel (row i, col j) centre = UV ((j + 0.5) / N, (i + 0.5) / N) = source px (u * 1337, v * 866).
All distances are Euclidean in SOURCE pixels (isotropic on the board: 1 px = 2/3 uu), not in
texels, so the SDF is correct although the texture stretches the 1337 x 866 image to a square.
"""
from __future__ import annotations

import math

import numpy as np


class Grid:
    def __init__(self, n: int, src_w: int, src_h: int, clamp_px: float):
        self.n, self.sw, self.sh, self.clamp = n, src_w, src_h, clamp_px
        self.xs = ((np.arange(n) + 0.5) * src_w / n).astype(np.float64)
        self.ys = ((np.arange(n) + 0.5) * src_h / n).astype(np.float64)

    def block(self, x0: float, x1: float, y0: float, y1: float):
        """Texel index slices covering source bbox [x0, x1] x [y0, y1] (+ clamp margin)."""
        m = self.clamp
        j0 = max(0, int(math.floor((x0 - m) * self.n / self.sw - 0.5)))
        j1 = min(self.n, int(math.ceil((x1 + m) * self.n / self.sw - 0.5)) + 1)
        i0 = max(0, int(math.floor((y0 - m) * self.n / self.sh - 0.5)))
        i1 = min(self.n, int(math.ceil((y1 + m) * self.n / self.sh - 0.5)) + 1)
        return slice(i0, i1), slice(j0, j1)

    def coords(self, rs: slice, cs: slice):
        return self.xs[cs][None, :], self.ys[rs][:, None]

    def full(self, value: float) -> np.ndarray:
        return np.full((self.n, self.n), value, np.float32)


def discs_sdf(g: Grid, centres, r: float) -> np.ndarray:
    """Signed distance to the union of discs of radius r (negative inside)."""
    out = g.full(g.clamp)
    for cx, cy in centres:
        rs, cs = g.block(cx - r, cx + r, cy - r, cy + r)
        X, Y = g.coords(rs, cs)
        d = (np.hypot(X - cx, Y - cy) - r).astype(np.float32)
        np.minimum(out[rs, cs], d, out=out[rs, cs])
    return out


def segments_dist(g: Grid, segments, out: np.ndarray | None = None) -> np.ndarray:
    """Unsigned distance to the nearest segment ((x0, y0), (x1, y1))."""
    if out is None:
        out = g.full(g.clamp)
    for (ax, ay), (bx, by) in segments:
        rs, cs = g.block(min(ax, bx), max(ax, bx), min(ay, by), max(ay, by))
        X, Y = g.coords(rs, cs)
        vx, vy = bx - ax, by - ay
        L2 = vx * vx + vy * vy
        t = np.clip(((X - ax) * vx + (Y - ay) * vy) / max(L2, 1e-12), 0.0, 1.0)
        d = np.hypot(X - (ax + t * vx), Y - (ay + t * vy)).astype(np.float32)
        np.minimum(out[rs, cs], d, out=out[rs, cs])
    return out


def arcs_dist(g: Grid, arcs, out: np.ndarray) -> np.ndarray:
    """Unsigned distance to circular arcs (cx, cy, R, start_rad, sweep_rad)."""
    for cx, cy, R, a0, sw in arcs:
        angs = a0 + sw * np.linspace(0, 1, 64)
        px, py = cx + R * np.cos(angs), cy + R * np.sin(angs)
        rs, cs = g.block(px.min(), px.max(), py.min(), py.max())
        X, Y = g.coords(rs, cs)
        ang = np.arctan2(Y - cy, X - cx)
        # position along the sweep in [0, 1] if inside the angular span
        rel = (ang - a0) * math.copysign(1.0, sw)
        rel = np.mod(rel, 2 * math.pi) / abs(sw)
        on = rel <= 1.0
        d_arc = np.abs(np.hypot(X - cx, Y - cy) - R)
        e0 = np.hypot(X - px[0], Y - py[0])
        e1 = np.hypot(X - px[-1], Y - py[-1])
        d = np.where(on, d_arc, np.minimum(e0, e1)).astype(np.float32)
        np.minimum(out[rs, cs], d, out=out[rs, cs])
    return out


def diamonds_sdf(g: Grid, diamonds, out: np.ndarray) -> np.ndarray:
    """Signed distance (approx. at the vertices) to L1 diamonds (cx, cy, half_diagonal)."""
    for cx, cy, h in diamonds:
        rs, cs = g.block(cx - h, cx + h, cy - h, cy + h)
        X, Y = g.coords(rs, cs)
        # square rotated 45 deg: axis-aligned box in (u, v) = ((x+y)/sqrt2, (x-y)/sqrt2)
        u = np.abs((X - cx) + (Y - cy)) / math.sqrt(2)
        v = np.abs((X - cx) - (Y - cy)) / math.sqrt(2)
        b = h / math.sqrt(2)
        qx, qy = u - b, v - b
        d = (np.hypot(np.maximum(qx, 0), np.maximum(qy, 0)) + np.minimum(np.maximum(qx, qy), 0)).astype(np.float32)
        np.minimum(out[rs, cs], d, out=out[rs, cs])
    return out


def id_map(g: Grid, centres, r: float) -> np.ndarray:
    out = np.zeros((g.n, g.n), np.uint16)
    for k, (cx, cy) in enumerate(centres, start=1):
        rs, cs = g.block(cx - r, cx + r, cy - r, cy + r)
        X, Y = g.coords(rs, cs)
        inside = (X - cx) ** 2 + (Y - cy) ** 2 <= r * r
        blk = out[rs, cs]
        if (blk[inside] != 0).any():
            raise ValueError("space discs overlap in the ID map")
        blk[inside] = k
    return out


def encode_sdf16(d: np.ndarray, scale: float) -> np.ndarray:
    return np.clip(np.round(32768.0 + d.astype(np.float64) * scale), 0, 65535).astype(np.uint16)
