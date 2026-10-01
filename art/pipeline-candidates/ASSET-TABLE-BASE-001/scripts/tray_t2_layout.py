"""ASSET-TABLE-BASE-001 T2: the modular layout of the shared rocky tray SM_TableBase_T2 (pure Python + numpy).

Used by tray_t2_build.py inside headless Blender (bmesh builds the convex hulls) and importable in system Python
(tools/art/tests/test_tray_t2_layout.py). Deterministic: one numpy Generator per library shape / module, seeded from
params kit.seed.

Three levels, rigid transforms + uniform scale only (NO non-uniform stretch anywhere):
  1. chunk library   kit.library {cap, block, spike} point clouds (the hull is built by Blender). Local frame:
                     x along the tray edge (width), y outward (+y = out of the tray), z up; origin = centre of the
                     top outer edge: the body lies at y < 0 (inward) and z < 0 (down).
                       cap    the top lip row: top tilted down inward (slope 0.28..0.40) so only its outer part can
                              rise above the tray top; the outer face slants inward going down (wider at the top);
                       block  the columnar cliff row under the caps;
                       spike  the hanging row at the bottom (tapered to a blunt point): the jagged silhouette.
  2. modules         side modules (kit.side_module_lengths_uu, one variant per length) and corner modules
                     (kit.corner_variants) = chunk instances (variant, uniform scale, yaw, position) in module space:
                     side = x along the edge 0..L, y outward (edge line y = 0); corner = the incoming side's frame
                     with the corner at the origin (leg A along +x up to the corner, leg B along -y after it, outward
                     +y resp. +x, one diagonal chunk per row).
  3. perimeter       .blend axes (UM_FBX_v1: UE X = -blend y, UE Y = -blend x): the tray rectangle is
                     |x| <= half_y_ue, |y| <= half_x_ue. Sides clockwise from the top-left corner (d x n = +z, so every
                     placement is a proper rotation): the corner module sits at the END of each side; side modules
                     fill [corner_leg, S - corner_leg] of every side, each joint overlapping by the same e >= 0 (the
                     sum of the module lengths minus the fill, spread over the n + 1 joints) - never stretched.
"""
from __future__ import annotations

import math

import numpy as np

KINDS = ("cap", "block", "spike")
# blend-frame sides, clockwise from the top-left corner: (name, UE side, start corner sign (sx, sy), rotation deg)
SIDES = (("top", "west (UE -X)", (-1, 1), 0.0), ("right", "far/north (UE -Y)", (1, 1), -90.0),
         ("bottom", "east (UE +X)", (1, -1), 180.0), ("left", "near/south (UE +Y)", (-1, -1), 90.0))


def rot2(deg: float) -> np.ndarray:
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.array([[c, -s], [s, c]])


def ring(rng, n, half_w, half_t, cy, z, zjit, p=3.2, rjit=(0.9, 1.04), cx=0.0, zfun=None):
    """n points on a jittered superellipse (half sizes half_w along x, half_t along y) centred at (cx, cy)."""
    phase = rng.uniform(0.0, 2.0 * math.pi)
    pts = []
    for i in range(n):
        th = phase + 2.0 * math.pi * (i + rng.uniform(-0.3, 0.3)) / n
        c, s = math.cos(th), math.sin(th)
        x = half_w * math.copysign(abs(c) ** (2.0 / p), c)
        y = half_t * math.copysign(abs(s) ** (2.0 / p), s)
        r = rng.uniform(*rjit)
        px, py = cx + x * r, cy + y * r
        pz = (zfun(px, py) if zfun else z) + rng.uniform(-zjit, zjit)
        pts.append((px, py, pz))
    return pts


def make_shape(kind: str, rng) -> dict:
    """One library chunk: point cloud (uu, local frame) + nominal sizes."""
    if kind == "cap":
        w, t, h = rng.uniform(44, 72), rng.uniform(30, 44), rng.uniform(38, 62)
        k = rng.uniform(0.30, 0.45)          # top slope down inward, after a flat outer band
        a = rng.uniform(5.0, 11.0)           # flat outer band of the top (the visible rock rim)
        b = rng.uniform(0.18, 0.35) * t      # outer face batter (inward shift at the bottom)
        top = ring(rng, 8, w / 2, t / 2, -t / 2, 0.0, 0.6, zfun=lambda x, y: k * min(y + a, 0.0))
        upper = ring(rng, 8, w / 2 * 1.02, t / 2, -t / 2 - 0.02 * t, -0.18 * h, 1.5)
        mid = ring(rng, 7, w / 2 * 0.9, t / 2 * 0.85, -t / 2 - 0.5 * b, -0.55 * h, 3.0)
        bot = ring(rng, 6, w / 2 * 0.7, t / 2 * 0.6, -t / 2 - b, -h, 0.12 * h)
        pts = top + upper + mid + bot
        extra = {"topSlope": k, "flatBand": a, "batter": b}
    elif kind == "block":
        w, t, h = rng.uniform(36, 64), rng.uniform(28, 44), rng.uniform(52, 88)
        sx, sy = rng.uniform(-0.15, 0.15), rng.uniform(-0.3, -0.1)
        lx, ly = rng.uniform(-4, 4), rng.uniform(-4, 2)
        top = ring(rng, 7, w / 2, t / 2, -t / 2, 0.0, 1.0, zfun=lambda x, y: sx * x + sy * (y + t / 2))
        upper = ring(rng, 7, w / 2 * 1.01, t / 2, -t / 2, -0.2 * h, 2.0, cx=lx * 0.3)
        mid = ring(rng, 7, w / 2 * 0.95, t / 2 * 0.92, -t / 2 + ly * 0.5, -0.55 * h, 3.0, cx=lx * 0.6)
        bot = ring(rng, 6, w / 2 * 0.82, t / 2 * 0.8, -t / 2 + ly, -h, 0.1 * h, cx=lx)
        pts = top + upper + mid + bot
        extra = {"lean": [lx, ly]}
    elif kind == "spike":
        # the hanging row: most are blunt hanging blocks (a broken, flat-ish bottom), some taper to a point - the
        # concept's ragged cliff foot, not a row of teeth
        w, t, h = rng.uniform(30, 54), rng.uniform(24, 40), rng.uniform(36, 84)
        tx, ty = rng.uniform(-0.25, 0.25) * w, rng.uniform(-0.2, 0.2) * t
        blunt = bool(rng.random() < 0.6)
        top = ring(rng, 7, w / 2, t / 2, -t / 2, 0.0, 1.5)
        r2 = ring(rng, 7, w / 2 * 0.88, t / 2 * 0.88, -t / 2 + ty * 0.3, -0.35 * h, 3.0, cx=tx * 0.3)
        if blunt:
            f = rng.uniform(0.35, 0.6)
            r3 = ring(rng, 6, w / 2 * (f + 0.2), t / 2 * (f + 0.2), -t / 2 + ty * 0.7, -0.72 * h, 3.0, cx=tx * 0.7)
            tip = ring(rng, 5, w / 2 * f, t / 2 * f, -t / 2 + ty, -h, 0.12 * h, cx=tx)
        else:
            r3 = ring(rng, 5, w / 2 * 0.5, t / 2 * 0.5, -t / 2 + ty * 0.7, -0.7 * h, 3.0, cx=tx * 0.7)
            tip = [(tx + rng.uniform(-3, 3), -t / 2 + ty + rng.uniform(-3, 3), -h + rng.uniform(-3, 0))
                   for _ in range(int(rng.integers(2, 4)))]
        pts = top + r2 + r3 + tip
        extra = {"tip": [tx, ty], "blunt": 1.0 if blunt else 0.0}
    else:
        raise KeyError(kind)
    P = np.array(pts, dtype=np.float64)
    return {"kind": kind, "points": P, "w": float(w), "t": float(t), "h": float(h),
            "extent_x": float(P[:, 0].max() - P[:, 0].min()), "extra": {k: (np.round(v, 3).tolist()
                                                                          if isinstance(v, list) else round(float(v), 3))
                                                                      for k, v in extra.items()}}


def make_library(kit: dict) -> dict:
    lib = {}
    for ki, kind in enumerate(KINDS):
        lib[kind] = [make_shape(kind, np.random.default_rng([kit["seed"], 1, ki, v]))
                     for v in range(int(kit["library"][kind]))]
    return lib


def _row(rng, lib, kind, cfg, scale_rng, start, stop, frame):
    """Chunks of one row from cursor 'start' to 'stop' along a straight leg. frame(u) -> (x, y, yaw_base, out_dir)
    gives the edge point and the direction for the along-edge coordinate u."""
    out = []
    u = start
    first = True
    while u < stop:
        v = int(rng.integers(len(lib[kind])))
        s = float(rng.uniform(*scale_rng))
        w = lib[kind][v]["extent_x"] * s
        if cfg.get("overlap_uu") and not first:
            u -= rng.uniform(*cfg["overlap_uu"])
        centre = u + w / 2.0
        x, y, yaw0, (nx, ny) = frame(centre)
        o = float(rng.uniform(*cfg["out_uu"]))
        out.append({"kind": kind, "variant": v, "scale": s,
                    "pos": [x + nx * o, y + ny * o, float(rng.uniform(*cfg["top_z"]))],
                    "yaw": yaw0 + float(rng.uniform(-cfg["yaw_jitter_deg"], cfg["yaw_jitter_deg"]))})
        u += w
        if cfg.get("gap_uu"):
            u += rng.uniform(*cfg["gap_uu"])
        first = False
    return out


def side_module(kit, lib, index, length):
    rng = np.random.default_rng([kit["seed"], 2, index])
    chunks = []
    for kind in KINDS:
        cfg = kit["rows"][kind]
        start = -float(rng.uniform(4, 12))
        chunks += _row(rng, lib, kind, cfg, kit["instance_scale"], start, length - 6.0,
                       lambda u: (u, 0.0, 0.0, (0.0, 1.0)))
    return {"type": "side", "index": index, "length": float(length), "chunks": chunks}


def corner_module(kit, lib, index):
    rng = np.random.default_rng([kit["seed"], 3, index])
    lc = float(kit["corner_leg_uu"])
    diag = (math.sqrt(0.5), math.sqrt(0.5))
    chunks = []
    for kind in KINDS:
        cfg = kit["rows"][kind]
        # the diagonal chunk first: the variant whose width is closest to 50 uu, scale ~1, pushed out only a little
        # (its outer face chamfers the corner; its wings would otherwise stick out along both sides)
        v = int(min(range(len(lib[kind])), key=lambda i: abs(lib[kind][i]["extent_x"] - 50.0)))
        s = float(rng.uniform(0.95, 1.05))
        wd = lib[kind][v]["extent_x"] * s
        lo_o, hi_o = cfg["out_uu"]
        # the cliff block is pushed OUT (upper 6 uu of its range) so the rectangle corner stays filled below the lip
        o = float(rng.uniform(hi_o - 6.0, hi_o) if kind == "block" else rng.uniform(lo_o, min(hi_o, lo_o + 6.0)))
        chunks.append({"kind": kind, "variant": v, "scale": s, "pos": [diag[0] * o, diag[1] * o,
                                                                         float(rng.uniform(*cfg["top_z"]))],
                       "yaw": -45.0 + float(rng.uniform(-cfg["yaw_jitter_deg"], cfg["yaw_jitter_deg"]) * 0.5)})
        # leg A: along +x on the edge y = 0 (outward +y), from -lc - start to just before the corner chunk
        chunks += _row(rng, lib, kind, cfg, kit["instance_scale"], -lc - float(rng.uniform(4, 12)), -0.45 * wd,
                       lambda u: (u, 0.0, 0.0, (0.0, 1.0)))
        # leg B: along -y on the edge x = 0 (outward +x), from just after the corner chunk to lc + end
        chunks += _row(rng, lib, kind, cfg, kit["instance_scale"], 0.45 * wd, lc + float(rng.uniform(4, 12)),
                       lambda u: (0.0, -u, -90.0, (1.0, 0.0)))
    return {"type": "corner", "index": index, "legUU": lc, "chunks": chunks}


def fill_side(kit, fill: float, side_index: int, lengths: list) -> dict:
    """A module sequence for one side: n modules whose summed length covers 'fill', no variant twice in a row,
    joint overlap e = (sum - fill) / (n + 1) closest to 8 uu (seeded search, deterministic)."""
    rng = np.random.default_rng([kit["seed"], 4, side_index])
    best = None
    lmin, lmax = min(lengths), max(lengths)
    for _ in range(4000):
        n = int(rng.integers(math.ceil(fill / lmax), math.ceil(fill / lmin) + 1))
        seq = []
        for _ in range(n):
            choices = [i for i in range(len(lengths)) if not seq or i != seq[-1]]
            seq.append(int(rng.choice(choices)))
        total = sum(lengths[i] for i in seq)
        if total < fill:
            continue
        e = (total - fill) / (n + 1)
        uses = np.bincount(seq, minlength=len(lengths))
        score = abs(e - 8.0) + 0.5 * float(uses.max() - uses.min())
        if best is None or score < best[0]:
            best = (score, seq, e)
    _, seq, e = best
    return {"sequence": seq, "overlapUU": float(e), "fillUU": float(fill),
            "sumUU": float(sum(lengths[i] for i in seq))}


def perimeter(kit: dict, half_bx: float, half_by: float) -> dict:
    """Module instances in .blend space: [{module: ('side', i) | ('corner', i), rot, origin}] + the side table."""
    lc = float(kit["corner_leg_uu"])
    lengths = [float(v) for v in kit["side_module_lengths_uu"]]
    placements, sides = [], []
    for k, (name, ue, (sx, sy), rot) in enumerate(SIDES):
        start = np.array([sx * half_bx, sy * half_by])
        R = rot2(rot)
        d = R @ np.array([1.0, 0.0])
        n = R @ np.array([0.0, 1.0])
        assert abs(d[0] * n[1] - d[1] * n[0] - 1.0) < 1e-9  # proper rotation, n = outward
        length = 2.0 * (half_bx if abs(d[0]) > 0.5 else half_by)
        fill = fill_side(kit, length - 2.0 * lc, k, lengths)
        u = lc - fill["overlapUU"]
        for vi in fill["sequence"]:
            placements.append({"module": ["side", vi], "rot": rot, "origin": (start + d * u).tolist(), "side": name,
                               "u": u})
            u += lengths[vi] - fill["overlapUU"]
        end = start + d * length
        placements.append({"module": ["corner", k % int(kit["corner_variants"])], "rot": rot,
                           "origin": end.tolist(), "side": name, "u": length})
        sides.append({"name": name, "ue": ue, "start": start.tolist(), "rotDeg": rot, "lengthUU": length,
                      "outward": [round(float(v), 6) for v in n], **fill})
    return {"placements": placements, "sides": sides}


def instance_matrix(pos, yaw_deg, scale) -> np.ndarray:
    """4x4: T(pos) * Rz(yaw) * S(uniform)."""
    M = np.eye(4)
    M[:2, :2] = rot2(yaw_deg) * scale
    M[2, 2] = scale
    M[:3, 3] = pos
    return M


def build(params: dict) -> dict:
    """Everything the Blender build needs: library, modules, flattened chunk instances (blend frame, uu)."""
    kit, tray = params["kit"], params["tray"]
    half_bx, half_by = float(tray["half_y_ue"]), float(tray["half_x_ue"])  # blend x = UE Y, blend y = UE X
    lib = make_library(kit)
    sides_mod = [side_module(kit, lib, i, L) for i, L in enumerate(kit["side_module_lengths_uu"])]
    corners_mod = [corner_module(kit, lib, i) for i in range(int(kit["corner_variants"]))]
    per = perimeter(kit, half_bx, half_by)
    instances = []
    for pi, pl in enumerate(per["placements"]):
        mod = sides_mod[pl["module"][1]] if pl["module"][0] == "side" else corners_mod[pl["module"][1]]
        Mp = instance_matrix([pl["origin"][0], pl["origin"][1], 0.0], pl["rot"], 1.0)
        for ci, c in enumerate(mod["chunks"]):
            M = Mp @ instance_matrix(c["pos"], c["yaw"], c["scale"])
            instances.append({"placement": pi, "module": pl["module"], "chunk": ci, "kind": c["kind"],
                              "variant": c["variant"], "scale": c["scale"], "matrix": M})
    return {"library": lib, "sides": sides_mod, "corners": corners_mod, "perimeter": per, "instances": instances,
            "half_bx": half_bx, "half_by": half_by}


def uniform_scale(M: np.ndarray) -> tuple[float, float]:
    """(scale, anisotropy) of the linear part: column lengths; 1.0 = uniform."""
    cols = np.linalg.norm(M[:3, :3], axis=0)
    return float(cols.mean()), float(cols.max() / cols.min())
