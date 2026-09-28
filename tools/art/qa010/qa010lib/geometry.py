"""Planar polygon helpers (stdlib only).

Screen coordinates are continuous viewport pixels, origin top-left, +y down;
pixel column i covers [i, i + 1). A bbox (x0, y0, x1, y1) is the rectangle
x0 <= x <= x1, y0 <= y <= y1 in those coordinates.
"""

from __future__ import annotations

from typing import Iterable, Sequence

Point = tuple[float, float]
Rect = tuple[float, float, float, float]


def polygon_area(poly: Sequence[Point]) -> float:
    """Absolute shoelace area; orientation independent."""
    n = len(poly)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def _clip_edge(poly: list[Point], inside, intersect) -> list[Point]:
    out: list[Point] = []
    n = len(poly)
    for i in range(n):
        cur = poly[i]
        prev = poly[i - 1]
        cur_in = inside(cur)
        prev_in = inside(prev)
        if cur_in:
            if not prev_in:
                out.append(intersect(prev, cur))
            out.append(cur)
        elif prev_in:
            out.append(intersect(prev, cur))
    return out


def clip_polygon_to_rect(poly: Iterable[Point], rect: Rect) -> list[Point]:
    """Sutherland-Hodgman clip of a (convex or concave, simple) polygon by an
    axis-aligned rectangle. Returns [] when there is no overlap."""
    x0, y0, x1, y1 = normalize_rect(rect)
    pts = [(float(x), float(y)) for x, y in poly]

    def ix(xc):
        def f(p, q):
            t = (xc - p[0]) / (q[0] - p[0])
            return (xc, p[1] + t * (q[1] - p[1]))
        return f

    def iy(yc):
        def f(p, q):
            t = (yc - p[1]) / (q[1] - p[1])
            return (p[0] + t * (q[0] - p[0]), yc)
        return f

    for inside, inter in (
        (lambda p: p[0] >= x0, ix(x0)),
        (lambda p: p[0] <= x1, ix(x1)),
        (lambda p: p[1] >= y0, iy(y0)),
        (lambda p: p[1] <= y1, iy(y1)),
    ):
        if not pts:
            return []
        pts = _clip_edge(pts, inside, inter)
    return pts


def normalize_rect(rect: Rect) -> Rect:
    x0, y0, x1, y1 = (float(v) for v in rect)
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def rect_area(rect: Rect) -> float:
    x0, y0, x1, y1 = normalize_rect(rect)
    return (x1 - x0) * (y1 - y0)


def rect_polygon(rect: Rect) -> list[Point]:
    x0, y0, x1, y1 = normalize_rect(rect)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def overlap_area(poly: Sequence[Point], rect: Rect) -> float:
    return polygon_area(clip_polygon_to_rect(poly, rect))


def parse_bbox(text: str) -> Rect:
    """'x0,y0,x1,y1' or '(x0,y0,x1,y1)' -> Rect (validated, normalized)."""
    parts = [p.strip() for p in text.strip().strip("()[]").split(",")]
    if len(parts) != 4:
        raise ValueError(f"bbox needs 4 numbers x0,y0,x1,y1: {text!r}")
    vals = tuple(float(p) for p in parts)
    rect = normalize_rect(vals)  # type: ignore[arg-type]
    if rect[2] - rect[0] <= 0 or rect[3] - rect[1] <= 0:
        raise ValueError(f"bbox has zero area: {text!r}")
    return rect


def parse_points(text: str) -> list[Point]:
    """'x,y;x,y;...' -> points."""
    pts = []
    for item in text.replace(" ", "").split(";"):
        if not item:
            continue
        a, b = item.split(",")
        pts.append((float(a), float(b)))
    return pts
