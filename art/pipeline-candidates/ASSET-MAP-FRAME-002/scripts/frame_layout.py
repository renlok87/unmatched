"""ASSET-MAP-FRAME-002: geometry and placement of the heavy modular map frame (pure Python + numpy).

Importable in system Python (tools/art/tests/test_k_env_assets.py) and inside Blender (frame_build.py).

Frames (UE numbers, right-handed math on them = UE yaw convention: yaw t maps local (1,0) -> (cos t, sin t)):
  profile   (w, z): w = outward distance from the inner edge (the map edge), z relative to the play plane.
  segment   local X along the inner edge 0..segment_uu, local +Y = outward (w), Z = z. Placed with its origin on the
            inner edge; yaw 0 on the near side (outward +Y), 180 far (-Y), -90 east (+X), 90 west (-X).
  corner    local origin = the inner map corner; leg A along local -X (x in [-leg, w]) with outward +Y, leg B along
            local -Y (y in [-leg, w]) with outward +X, mitred on the diagonal x = y (profile point w -> (w, w)).
            yaw 0 = the near-east corner (+X, +Y), 90 near-west, 180 far-west, -90 far-east.
Placement (board-actor space, map centre at the origin, the frame mesh at z 0): see placements(). The map size of both
shipped maps gives an exact fit (stretch 1.0); another size gets the nearest segment count and reports the stretch a
UE placement would need (scale X of the segments only) - the caller decides.
"""
from __future__ import annotations

import math

import numpy as np


def map_half(P: dict) -> tuple[float, float]:
    m = P["map"]
    return m["src_px"][0] * m["uu_per_px"] * 0.5, m["src_px"][1] * m["uu_per_px"] * 0.5


def frame_half(P: dict) -> tuple[float, float]:
    hx, hy = map_half(P)
    f = float(P["map"]["frame_uu"])
    return hx + f, hy + f


def fit_side(fill: float, seg: float) -> dict:
    n = max(1, int(round(fill / seg)))
    return {"fillUU": fill, "segments": n, "stretch": fill / (n * seg)}


def placements(P: dict) -> dict:
    """Module instances (board-actor space). Middle segment of each side = 'Mid' (bracket) when the count is odd;
    the rest alternate A / B."""
    hx, hy = map_half(P)
    seg = float(P["modules"]["segment_uu"])
    lc = float(P["modules"]["corner_leg_uu"])
    out, sides = [], {}
    corners = (("near-east", (hx, hy), 0.0), ("near-west", (-hx, hy), 90.0),
               ("far-west", (-hx, -hy), 180.0), ("far-east", (hx, -hy), -90.0))
    for name, (x, y), yaw in corners:
        out.append({"id": "corner-" + name, "module": "Corner", "loc": [round(x, 4), round(y, 4), 0.0], "yawDeg": yaw,
                    "scaleX": 1.0})
    # (side, start point of the fill on the inner edge, direction of local +X, yaw)
    for side, start, d, yaw, length in (("near", (-hx + lc, hy), (1.0, 0.0), 0.0, 2 * hx),
                                        ("far", (hx - lc, -hy), (-1.0, 0.0), 180.0, 2 * hx),
                                        ("east", (hx, hy - lc), (0.0, -1.0), -90.0, 2 * hy),
                                        ("west", (-hx, -hy + lc), (0.0, 1.0), 90.0, 2 * hy)):
        f = fit_side(length - 2 * lc, seg)
        sides[side] = f
        L = seg * f["stretch"]
        mid = f["segments"] // 2 if f["segments"] % 2 == 1 else None
        for i in range(f["segments"]):
            mod = "Mid" if i == mid else ("A" if (i + (0 if side in ("near", "far") else 1)) % 2 == 0 else "B")
            x, y = start[0] + d[0] * L * i, start[1] + d[1] * L * i
            out.append({"id": "%s-%d" % (side, i), "module": mod, "loc": [round(x, 4), round(y, 4), 0.0],
                        "yawDeg": yaw, "scaleX": round(f["stretch"], 9)})
    return {"mapHalfUU": [hx, hy], "frameHalfUU": list(frame_half(P)), "instances": out, "sides": sides,
            "exactFit": all(abs(s["stretch"] - 1.0) < 1e-5 for s in sides.values())}


def yaw_matrix(yaw_deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(yaw_deg)), math.sin(math.radians(yaw_deg))
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def profile_area(points) -> float:
    p = np.asarray(points, dtype=np.float64)
    return 0.5 * float(np.sum(p[:, 0] * np.roll(p[:, 1], -1) - np.roll(p[:, 0], -1) * p[:, 1]))


def point_in_polygon(pt, poly) -> bool:
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def thicken_polyline(line, profile, t):
    """Closed polygon of a strap: the open polyline on the wood surface + its offset by t away from the wood."""
    L = np.asarray(line, dtype=np.float64)
    normals = []
    for i in range(len(L) - 1):
        d = L[i + 1] - L[i]
        d = d / np.linalg.norm(d)
        n = np.array([d[1], -d[0]])
        mid = (L[i] + L[i + 1]) / 2
        if point_in_polygon(mid + 0.01 * n, profile):
            n = -n
        normals.append(n)
    off = []
    for i in range(len(L)):
        if i == 0:
            n = normals[0]
        elif i == len(L) - 1:
            n = normals[-1]
        else:
            a, b = normals[i - 1], normals[i]
            m = a + b
            m = m / np.linalg.norm(m)
            n = m / max(float(np.dot(m, a)), 0.3)
        off.append(L[i] + n * t)
    return [tuple(p) for p in L] + [tuple(p) for p in reversed(off)]


def all_points_bounds(P: dict) -> dict:
    """Plan extent of the wood profile (w range) and of the iron (w range incl. thickness)."""
    prof = P["profile"]["points"]
    ws = [p[0] for p in prof]
    iron = []
    for key in ("corner_polyline", "mid_polyline"):
        iron += thicken_polyline(P["iron"][key], prof, float(P["iron"]["thickness_uu"]))
    return {"woodW": [min(ws), max(ws)], "woodZ": [min(p[1] for p in prof), max(p[1] for p in prof)],
            "ironW": [min(p[0] for p in iron), max(p[0] for p in iron)],
            "ironZ": [min(p[1] for p in iron), max(p[1] for p in iron)]}
