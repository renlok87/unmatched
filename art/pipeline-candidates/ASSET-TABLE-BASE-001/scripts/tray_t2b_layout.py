"""ASSET-TABLE-BASE-001 T2b: the modular layout of the chunky shared rocky tray SM_TableBase_T2b (pure Python + numpy).

T2b = T2 (tray_t2_layout.py) with the review gap 3 changes (p2-frames-2026-10-01/concept-review.json, rank 3): bigger,
readable boulders, a cliff 150..250 uu deep with a jagged bottom, a slight overhang of the upper lip. Same top outline
(half_x_ue 780 / half_y_ue 470, offset -45 applied by the board actor), same three levels and the same rules:
  1. chunk library   params kit.library {kind: count}, kinds cap / boulder / block / spike (convex point clouds; the
                     hull is built by Blender). Local frame as T2: x along the edge, y outward, z up; origin = centre of
                     the top outer edge, the body at y < 0 and z < 0. Sizes come from params shapes.<kind>.
                       cap      the upper lip: top tilted down inward (only the outer band can rise above the tray top),
                                outer face battered inward going down;
                       boulder  rounded blocks bulging out under the lip (jittered superellipsoid, more points = rounder);
                       block    the columnar cliff wall behind the boulders;
                       spike    the hanging bottom row (blunt broken blocks and tapered points: the jagged silhouette).
  2. modules         side modules (one per kit.side_module_lengths_uu) and corner modules (kit.corner_variants) of
                     chunk instances (variant, uniform scale, yaw, position), rows from params kit.rows (a LIST, top to
                     bottom; each row names its library kind). Corner = one diagonal chunk per row + the two legs.
  3. perimeter       tray_t2_layout.perimeter (unchanged): corners at the side ends, side modules with an equal joint
                     overlap, rigid transforms + uniform scale only - never stretched.
Deterministic: one numpy Generator per shape / module (seeded from kit.seed).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tray_t2_layout as T2  # noqa: E402

KINDS = ("cap", "boulder", "block", "spike")
ring = T2.ring
instance_matrix = T2.instance_matrix
uniform_scale = T2.uniform_scale


def _u(rng, pair):
    return float(rng.uniform(float(pair[0]), float(pair[1])))


def make_shape(kind: str, rng, cfg: dict) -> dict:
    """One library chunk: point cloud (uu, local frame) + nominal sizes; cfg = params shapes.<kind>."""
    w, t, h = _u(rng, cfg["w"]), _u(rng, cfg["t"]), _u(rng, cfg["h"])
    if kind == "cap":
        k = _u(rng, cfg.get("top_slope", (0.28, 0.42)))
        a = _u(rng, cfg.get("flat_band", (6.0, 12.0)))
        b = _u(rng, cfg.get("batter", (0.15, 0.3))) * t
        top = ring(rng, 9, w / 2, t / 2, -t / 2, 0.0, 0.8, zfun=lambda x, y: k * min(y + a, 0.0))
        upper = ring(rng, 9, w / 2 * 1.03, t / 2 * 1.02, -t / 2 - 0.02 * t, -0.16 * h, 1.8)
        mid = ring(rng, 8, w / 2 * 0.92, t / 2 * 0.86, -t / 2 - 0.5 * b, -0.55 * h, 3.5)
        bot = ring(rng, 7, w / 2 * 0.7, t / 2 * 0.62, -t / 2 - b, -h, 0.12 * h)
        pts = top + upper + mid + bot
        extra = {"topSlope": k, "flatBand": a, "batter": b}
    elif kind == "boulder":
        # rounded block: rings of a superellipsoid (p 2.6 across, 2.2 vertical), slight lean, outermost point at y ~ 0
        n_rings = int(cfg.get("rings", 6))
        lean = _u(rng, (-0.12, 0.12))
        pts = []
        for i in range(n_rings + 1):
            ph = -math.pi / 2 + math.pi * i / n_rings      # -90 (bottom) .. +90 (top)
            c = math.copysign(abs(math.cos(ph)) ** (2.0 / 2.2), math.cos(ph))
            s = math.copysign(abs(math.sin(ph)) ** (2.0 / 2.2), math.sin(ph))
            z = -h / 2 + s * h / 2
            if abs(c) < 0.08:
                pts.append((lean * (z + h / 2) + _u(rng, (-3, 3)), -t / 2 + _u(rng, (-3, 3)), z))
                continue
            pts += ring(rng, int(cfg.get("ring_points", 9)), w / 2 * c, t / 2 * c, -t / 2, z, 0.04 * h, p=2.6,
                        rjit=(0.9, 1.05), cx=lean * (z + h / 2))
        pts = [(x, y, min(z, 0.0)) for x, y, z in pts]
        P = np.array(pts)
        P[:, 1] -= P[:, 1].max()  # outermost point on y = 0
        pts = P.tolist()
        extra = {"lean": lean}
    elif kind == "block":
        sx, sy = _u(rng, (-0.15, 0.15)), _u(rng, (-0.3, -0.1))
        lx, ly = _u(rng, (-5, 5)), _u(rng, (-5, 2))
        top = ring(rng, 8, w / 2, t / 2, -t / 2, 0.0, 1.2, zfun=lambda x, y: sx * x + sy * (y + t / 2))
        upper = ring(rng, 8, w / 2 * 1.02, t / 2, -t / 2, -0.2 * h, 2.5, cx=lx * 0.3)
        mid = ring(rng, 8, w / 2 * 0.96, t / 2 * 0.92, -t / 2 + ly * 0.5, -0.55 * h, 3.5, cx=lx * 0.6)
        bot = ring(rng, 7, w / 2 * 0.84, t / 2 * 0.8, -t / 2 + ly, -h, 0.1 * h, cx=lx)
        pts = top + upper + mid + bot
        extra = {"lean": [lx, ly]}
    elif kind == "spike":
        tx, ty = _u(rng, (-0.25, 0.25)) * w, _u(rng, (-0.2, 0.2)) * t
        blunt = bool(rng.random() < float(cfg.get("blunt_fraction", 0.55)))
        top = ring(rng, 8, w / 2, t / 2, -t / 2, 0.0, 1.5)
        r2 = ring(rng, 8, w / 2 * 0.9, t / 2 * 0.88, -t / 2 + ty * 0.3, -0.33 * h, 3.0, cx=tx * 0.3)
        if blunt:
            f = _u(rng, (0.35, 0.6))
            r3 = ring(rng, 7, w / 2 * (f + 0.2), t / 2 * (f + 0.2), -t / 2 + ty * 0.7, -0.7 * h, 3.5, cx=tx * 0.7)
            tip = ring(rng, 6, w / 2 * f, t / 2 * f, -t / 2 + ty, -h, 0.1 * h, cx=tx)
        else:
            r3 = ring(rng, 6, w / 2 * 0.5, t / 2 * 0.5, -t / 2 + ty * 0.7, -0.68 * h, 3.0, cx=tx * 0.7)
            tip = [(tx + rng.uniform(-3, 3), -t / 2 + ty + rng.uniform(-3, 3), -h + rng.uniform(-3, 0))
                   for _ in range(int(rng.integers(2, 4)))]
        pts = top + r2 + r3 + tip
        extra = {"tip": [tx, ty], "blunt": 1.0 if blunt else 0.0}
    else:
        raise KeyError(kind)
    P = np.array(pts, dtype=np.float64)
    return {"kind": kind, "points": P, "w": float(w), "t": float(t), "h": float(h),
            "extent_x": float(P[:, 0].max() - P[:, 0].min()),
            "extra": {k: (np.round(v, 3).tolist() if isinstance(v, list) else round(float(v), 3)) for k, v in extra.items()}}


def make_library(kit: dict, shapes: dict) -> dict:
    lib = {}
    for ki, kind in enumerate(KINDS):
        n = int(kit["library"].get(kind, 0))
        lib[kind] = [make_shape(kind, np.random.default_rng([kit["seed"], 1, ki, v]), shapes[kind]) for v in range(n)]
    return lib


def _row(rng, lib, row, scale_rng, start, stop, frame):
    """Chunks of one row from cursor 'start' to 'stop' along a straight leg (T2 rule). frame(u) -> (x, y, yaw0, n)."""
    kind = row["kind"]
    scale_rng = row.get("scale") or scale_rng  # optional per-row uniform scale range
    out = []
    u = start
    first = True
    while u < stop:
        v = int(rng.integers(len(lib[kind])))
        s = float(rng.uniform(*scale_rng))
        w = lib[kind][v]["extent_x"] * s
        if row.get("overlap_uu") and not first:
            u -= rng.uniform(*row["overlap_uu"])
        centre = u + w / 2.0
        x, y, yaw0, (nx, ny) = frame(centre)
        o = float(rng.uniform(*row["out_uu"]))
        out.append({"row": row["name"], "kind": kind, "variant": v, "scale": s,
                    "pos": [x + nx * o, y + ny * o, float(rng.uniform(*row["top_z"]))],
                    "yaw": yaw0 + float(rng.uniform(-row["yaw_jitter_deg"], row["yaw_jitter_deg"]))})
        u += w
        if row.get("gap_uu"):
            u += rng.uniform(*row["gap_uu"])
        first = False
    return out


def side_module(kit, lib, index, length):
    rng = np.random.default_rng([kit["seed"], 2, index])
    chunks = []
    for row in kit["rows"]:
        start = -float(rng.uniform(4, 14))
        chunks += _row(rng, lib, row, kit["instance_scale"], start, length - 6.0, lambda u: (u, 0.0, 0.0, (0.0, 1.0)))
    return {"type": "side", "index": index, "length": float(length), "chunks": chunks}


def corner_module(kit, lib, index):
    rng = np.random.default_rng([kit["seed"], 3, index])
    lc = float(kit["corner_leg_uu"])
    diag = (math.sqrt(0.5), math.sqrt(0.5))
    chunks = []
    for row in kit["rows"]:
        kind = row["kind"]
        target = float(row.get("corner_width_uu", 60.0))
        v = int(min(range(len(lib[kind])), key=lambda i: abs(lib[kind][i]["extent_x"] - target)))
        s = float(rng.uniform(0.96, 1.04))
        wd = lib[kind][v]["extent_x"] * s
        lo_o, hi_o = row["out_uu"]
        o = float(rng.uniform(hi_o - 6.0, hi_o) if row.get("corner_push_out") else rng.uniform(lo_o, min(hi_o, lo_o + 6.0)))
        chunks.append({"row": row["name"], "kind": kind, "variant": v, "scale": s,
                       "pos": [diag[0] * o, diag[1] * o, float(rng.uniform(*row["top_z"]))],
                       "yaw": -45.0 + float(rng.uniform(-row["yaw_jitter_deg"], row["yaw_jitter_deg"]) * 0.5)})
        chunks += _row(rng, lib, row, kit["instance_scale"], -lc - float(rng.uniform(4, 14)), -0.45 * wd,
                       lambda u: (u, 0.0, 0.0, (0.0, 1.0)))
        chunks += _row(rng, lib, row, kit["instance_scale"], 0.45 * wd, lc + float(rng.uniform(4, 14)),
                       lambda u: (0.0, -u, -90.0, (1.0, 0.0)))
    return {"type": "corner", "index": index, "legUU": lc, "chunks": chunks}


def build(params: dict) -> dict:
    """Everything the Blender build needs: library, modules, flattened chunk instances (blend frame, uu)."""
    kit, tray = params["kit"], params["tray"]
    half_bx, half_by = float(tray["half_y_ue"]), float(tray["half_x_ue"])  # blend x = UE Y, blend y = UE X
    lib = make_library(kit, params["shapes"])
    sides_mod = [side_module(kit, lib, i, L) for i, L in enumerate(kit["side_module_lengths_uu"])]
    corners_mod = [corner_module(kit, lib, i) for i in range(int(kit["corner_variants"]))]
    per = T2.perimeter(kit, half_bx, half_by)
    instances = []
    for pi, pl in enumerate(per["placements"]):
        mod = sides_mod[pl["module"][1]] if pl["module"][0] == "side" else corners_mod[pl["module"][1]]
        Mp = instance_matrix([pl["origin"][0], pl["origin"][1], 0.0], pl["rot"], 1.0)
        for ci, c in enumerate(mod["chunks"]):
            M = Mp @ instance_matrix(c["pos"], c["yaw"], c["scale"])
            instances.append({"placement": pi, "module": pl["module"], "chunk": ci, "row": c["row"], "kind": c["kind"],
                              "variant": c["variant"], "scale": c["scale"], "matrix": M})
    return {"library": lib, "sides": sides_mod, "corners": corners_mod, "perimeter": per, "instances": instances,
            "half_bx": half_bx, "half_by": half_by}


def world_points(b: dict) -> np.ndarray:
    """All library points through every instance matrix (the hull vertices are a subset: exact bounds)."""
    pts = []
    for inst in b["instances"]:
        P = b["library"][inst["kind"]][inst["variant"]]["points"]
        pts.append((np.c_[P, np.ones(len(P))] @ inst["matrix"].T)[:, :3])
    return np.vstack(pts)


def module_points(lib, mod) -> np.ndarray:
    pts = []
    for c in mod["chunks"]:
        P = lib[c["kind"]][c["variant"]]["points"]
        M = instance_matrix(c["pos"], c["yaw"], c["scale"])
        pts.append((np.c_[P, np.ones(len(P))] @ M.T)[:, :3])
    return np.vstack(pts)
