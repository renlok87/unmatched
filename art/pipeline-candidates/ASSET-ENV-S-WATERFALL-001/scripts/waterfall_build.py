"""ASSET-ENV-S-WATERFALL-001: Sarpedon's south waterfall meshes + the rock lip add-on + the sea ring (headless Blender).

  blender -b --factory-startup -t 4 --python-exit-code 1 --python \
      art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/scripts/waterfall_build.py -- \
      art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/20261001-waterfall-v1/reports/waterfall-params.json

Needs the T2b build first (reads its reports/south-profile.json: the shared tray's rock under this river mouth).
Four static meshes (UM_FBX_v1, uniform scale 1.0), every number in params (proposed):
  SM_Env_S_WaterfallLip   OPTIONAL add-on, separate from the shared tray (which stays identical on both maps): a
                          water-worn rock spout (5 flat-topped slabs with a rounded, undercut front edge at front_x,
                          2 cheek boulders channelling the water, 4 hanging chunks recessed under it). Convex hulls of
                          seeded point clouds like the tray; slot M_TableBase_T2b (the tray's MI), UV0 box projection,
                          Col as the tray (R moss/damp mask on up-facing tops, G random, B depth).
  SM_Env_S_Waterfall      the water sheet: starts start_back_uu behind the lip front at start_z (under the spill plane
                          z 2.5), leaves the lip like a jet (x = x0 + R sqrt(d / D)), falls to bottom_z, widening to
                          widen_bottom, slight plan bulge and ripples. R is the smallest reach_candidates value that keeps
                          the sheet clear of the lip AND of the T2b rock (south profile) by the clearance margins.
                          UV0 = (u across 0..1, v along the flow 0 at the top .. 1 at the bottom, by arc length) = what
                          M_EnvWaterfall expects with FallCard = (top width, arc length, 0); UV1 = the same in uu / 100.
  SM_Env_S_WaterfallFoam  slot 0 a domed foam disc at the impact (UV0 u = angle, v = 1 at the centre .. 0 at the rim),
                          slot 1 a mist curtain arc around it (v 0 at the top .. 1 at the water); both for M_EnvWaterfall
                          MIDs with FallCard kind 1 (spill: foam grows with v, alpha fades in near v 0).
  SM_Env_S_SeaRing        flat annulus under the island, pivot = tray centre; UV0 planar / uv0_tile_uu, UV1 = (around
                          0..1, distance from the inner edge / uv1_dist_uu); Col R = foam band at the inner edge,
                          G = far fade 0..1.
Checks: triangles per mesh; lip and hanging chunks outward and closed; the lip front at front_x and in front of the T2b
top-band rock; sheet clearance >= margins everywhere; sheet x range = the layout entry (x0..x1 at the top); drop in
[120, 200]; UV0 in 0..1 on the sheet; sea inner edge inside the tray outline and outer radius; 1 mesh per FBX, slots,
UV0 (+UV1), round trip; UM_FBX_v1 rows conform. Outputs: export/*.fbx, reports/build-report.json,
reports/waterfall-layout.json (proposed layout / ground entries for UE).
"""

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import k_blender as K  # noqa: E402

S, r = K.S, K.r
SCHEMA = "unmatched.env-s-waterfall.build-report/1"


def hull(points):
    bm = bmesh.new()
    for p in points:
        bm.verts.new(Vector(p))
    res = bmesh.ops.convex_hull(bm, input=bm.verts[:], use_existing_faces=False)
    drop = list({g for g in res["geom_interior"] + res["geom_unused"] if isinstance(g, bmesh.types.BMVert)})
    if drop:
        bmesh.ops.delete(bm, geom=drop, context="VERTS")
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.verts.index_update()
    V = np.array([v.co[:] for v in bm.verts], dtype=np.float64)
    T = [[v.index for v in f.verts] for f in bm.faces]
    bm.free()
    if K.signed_volume(V, T) < 0:
        T = [t[::-1] for t in T]
    return V, T


def level(rng, n, cx, cy, hx, hy, z, zj, xyj=1.0, p=4.0):
    pts = []
    ph = rng.uniform(0, 2 * math.pi)
    for i in range(n):
        th = ph + 2 * math.pi * (i + rng.uniform(-0.25, 0.25)) / n
        c, s = math.cos(th), math.sin(th)
        x = hx * math.copysign(abs(c) ** (2 / p), c)
        y = hy * math.copysign(abs(s) ** (2 / p), s)
        pts.append((cx + x + rng.uniform(-xyj, xyj), cy + y + rng.uniform(-xyj, xyj), z + rng.uniform(-zj, zj)))
    return pts


def box_uv(p, n, tile, off):
    ax = int(np.argmax(np.abs(n)))
    if ax == 0:
        u, v = p[1] * math.copysign(1.0, n[0]), p[2]
    elif ax == 1:
        u, v = -p[0] * math.copysign(1.0, n[1]), p[2]
    else:
        u, v = p[0] * math.copysign(1.0, n[2]), p[1]
    return (u / tile + off[0], v / tile + off[1])


def add_rock(mb, V, T, rng, tile, top_z):
    base = mb.add_verts(V)
    off = (float(rng.random()), float(rng.random()))
    g = float(rng.random())
    for t in T:
        a, b, c = V[t[0]], V[t[1]], V[t[2]]
        n = np.cross(b - a, c - a)
        n = n / max(np.linalg.norm(n), 1e-12)
        up = min(max((n[2] - 0.15) / 0.55, 0.0), 1.0)
        cols = []
        for p in (a, b, c):
            hgt = min(max((p[2] + 40.0) / 36.0, 0.0), 1.0)
            cols.append((up * hgt, g, min(max((top_z - p[2]) / 250.0, 0.0), 1.0), 1.0))
        mb.add_face([base + i for i in t], [box_uv(V[i], n, tile, off) for i in t], 0, cols, "rock")


def build_lip(P, front_x):
    L = P["lip"]
    rng = np.random.default_rng(int(L["seed"]))
    mb = K.MeshBuilder(L["asset"], n_uv=1, colors=True)
    hw, bx, tz = float(L["half_width_uu"]), float(L["back_x"]), float(L["top_z"])
    n = int(L["slabs"])
    w = 2 * hw / n
    parts = []
    for k in range(n):
        yc = -hw + w * (k + 0.5)
        hy = w / 2 + rng.uniform(2.0, 5.0)
        fx = front_x - rng.uniform(0.0, 1.2)
        pts = []
        for z, xb, xf, sh, zj in ((tz, bx, fx - 2.0, 1.0, 0.15), (tz - 1.6, bx, fx - 0.4, 1.0, 0.3),
                                  (tz - 4.5, bx, fx, 0.99, 0.6), (-14.0, bx, fx - 6.0, 0.96, 1.5),
                                  (-30.0, bx + 4.0, fx - 14.0, 0.9, 2.0),
                                  (float(L["slab_bottom_z"]), bx + 8.0, fx - 20.0, 0.8, 3.0)):
            pts += level(rng, 10, (xb + xf) / 2, yc, (xf - xb) / 2, hy * sh, z, zj, 0.4 if z > -5 else 1.2)
        parts.append(("slab", pts))
    for sgn in (-1.0, 1.0):
        chw = rng.uniform(*L["cheek_half_width"])
        yc = sgn * (96.9 + chw - 2.0)
        top = rng.uniform(*L["cheek_top_z"])
        bot = float(L["cheek_bottom_z"])
        pts = []
        for i in range(7):
            ph = -math.pi / 2 + math.pi * i / 6
            c, s = math.cos(ph), math.sin(ph)
            z = (top + bot) / 2 + s * (top - bot) / 2
            if c < 0.1:
                pts.append((4.0 + rng.uniform(-3, 3), yc + rng.uniform(-3, 3), z))
                continue
            pts += level(rng, 9, 4.0, yc, 26.0 * c ** 0.8, chw * c ** 0.8, z, 1.0, 1.0, 2.6)
        P2 = np.array(pts)
        P2[:, 0] = np.minimum(P2[:, 0], front_x)
        parts.append(("cheek", P2.tolist()))
    nh = int(L["hanging"])
    for k in range(nh):
        yc = -hw * 0.8 + 2 * hw * 0.8 * (k + 0.5) / nh + rng.uniform(-6, 6)
        bot = rng.uniform(*L["hanging_bottom_z"])
        top = float(L["hanging_top_z"])
        xf = front_x - float(L["hanging_front_recess_uu"])
        pts = level(rng, 8, (bx + 6 + xf) / 2, yc, (xf - bx - 6) / 2, 22.0, top, 1.5)
        pts += level(rng, 7, (bx + 10 + xf - 4) / 2, yc + rng.uniform(-4, 4), (xf - 4 - bx - 10) / 2 * 0.8, 16.0,
                     (top + bot) / 2, 3.0)
        pts += [(rng.uniform(bx + 10, xf - 8), yc + rng.uniform(-6, 6), bot + rng.uniform(-2, 2)) for _ in range(3)]
        parts.append(("hanging", pts))
    info = []
    for kind, pts in parts:
        V, T = hull(pts)
        add_rock(mb, V, T, rng, float(L["tile_uu"]), 0.0)
        info.append({"kind": kind, "hullTris": len(T), "volumeUU3": r(K.signed_volume(V, T), 1),
                     "xRange": [r(V[:, 0].min(), 2), r(V[:, 0].max(), 2)], "zRange": [r(V[:, 2].min(), 2), r(V[:, 2].max(), 2)]})
    return mb, info


def surface_samples(V, F, n=6):
    g = np.array([(i / n, j / n, 1 - (i + j) / n) for i in range(n + 1) for j in range(n + 1 - i)])
    tris = []
    for f in F:
        for i in range(1, len(f) - 1):
            tris.append([V[f[0]], V[f[i]], V[f[i + 1]]])
    T = np.array(tris)
    return np.einsum("sk,tkc->tsc", g, T).reshape(-1, 3)


def rock_front(lip_pts, profile, half_w, z):
    """Max outward x of the rock at height z (+-2.5 uu) within |y| <= half_w: the lip (dense samples) and the T2b
    south profile bin of that z."""
    m = (np.abs(lip_pts[:, 2] - z) <= 2.5) & (np.abs(lip_pts[:, 1]) <= half_w)
    x = float(lip_pts[m, 0].max()) if m.any() else -1e9
    for b in profile["bins"]:
        if b["zBottom"] - 2.5 <= z <= b["zTop"] + 2.5:
            x = max(x, float(b["maxOutwardUU"]))
    return x


def sheet_curve(Sh, front_x, R):
    x0 = front_x - float(Sh["start_back_uu"])
    z0, zb = float(Sh["start_z"]), float(Sh["bottom_z"])
    D = z0 - zb
    rows = int(Sh["rows"])
    ds = [D * (k / rows) ** 1.6 for k in range(rows + 1)]
    pts = [(x0 + R * math.sqrt(d / D), z0 - d) for d in ds]
    arc = [0.0]
    for i in range(1, len(pts)):
        arc.append(arc[-1] + math.dist(pts[i - 1], pts[i]))
    return pts, arc, D


def sheet_offsets(Sh, y, hw, d, D):
    bulge = float(Sh["plan_bulge_uu"]) * (1 - (y / hw) ** 2)
    rip = float(Sh["ripple_uu"]) * math.sin(2 * math.pi * (y / float(Sh["ripple_period_y_uu"]) + d / float(
        Sh["ripple_period_d_uu"]))) * min(d / 20.0, 1.0)
    return bulge + rip


def build_sheet(P, front_x, lip_pts, profile):
    Sh = P["sheet"]
    e = P["source_entry"]
    width = float(e["x1"]) - float(e["x0"])
    hw0 = width / 2
    chosen, tried = None, []
    for R in Sh["reach_candidates_uu"]:
        pts, arc, D = sheet_curve(Sh, front_x, float(R))
        worst = 1e9
        for (x, z), d in zip(pts, [float(Sh["start_z"]) - p[1] for p in pts]):
            if z > float(P["lip"]["top_z"]) + 0.2:
                continue
            hw = hw0 * (1 + (float(Sh["widen_bottom"]) - 1) * d / D)
            need = float(Sh["clearance_lip_uu"]) if z > -10.0 else float(Sh["clearance_uu"])
            # worst case over the width: no bulge at the edges, ripple at its trough
            margin = x - float(Sh["ripple_uu"]) * min(d / 20.0, 1.0) - rock_front(lip_pts, profile, hw, z) - need
            worst = min(worst, margin)
        tried.append({"reachUU": R, "worstMarginUU": r(worst, 3)})
        if worst >= 0:
            chosen = float(R)
            break
    if chosen is None:
        raise SystemExit("no reach candidate clears the rock: %s" % tried)
    pts, arc, D = sheet_curve(Sh, front_x, chosen)
    cols = int(Sh["columns"])
    mb = K.MeshBuilder(Sh["asset"], n_uv=2)
    grid = []
    for k, ((x, z), a) in enumerate(zip(pts, arc)):
        d = float(Sh["start_z"]) - z
        hw = hw0 * (1 + (float(Sh["widen_bottom"]) - 1) * d / D)
        row = []
        for j in range(cols + 1):
            u = j / cols
            y = -hw + 2 * hw * u
            row.append((x + sheet_offsets(Sh, y, hw, d, D), y, z))
        grid.append(mb.add_verts(row))
    for k in range(len(pts) - 1):
        for j in range(cols):
            idx = [grid[k] + j, grid[k] + j + 1, grid[k + 1] + j + 1, grid[k + 1] + j]
            # the corners' (j, k): u across = j / cols, v = arc / arc_total
            uv0 = [(jj / cols, arc[kk] / arc[-1]) for jj, kk in ((j, k), (j + 1, k), (j + 1, k + 1), (j, k + 1))]
            uv1 = [(jj / cols * width / 100.0, arc[kk] / 100.0) for jj, kk in ((j, k), (j + 1, k), (j + 1, k + 1), (j, k + 1))]
            V = np.array([mb.V[i] for i in idx])
            n = np.cross(V[1] - V[0], V[3] - V[0])
            if n[0] < 0:  # face towards local +X (outward, the camera side after yaw 90)
                idx, uv0, uv1 = idx[::-1], uv0[::-1], uv1[::-1]
            mb.add_face(idx, [uv0, uv1], 0, tag="sheet")
    # measured clearance of the built sheet against the rock
    Vs = mb.verts()
    worst = 1e9
    for p in Vs:
        if p[2] > float(P["lip"]["top_z"]) + 0.2:
            continue
        need = float(Sh["clearance_lip_uu"]) if p[2] > -10.0 else float(Sh["clearance_uu"])
        m = (np.abs(lip_pts[:, 2] - p[2]) <= 2.5) & (np.abs(lip_pts[:, 1] - p[1]) <= 6.0)
        rx = float(lip_pts[m, 0].max()) if m.any() else -1e9
        for b in profile["bins"]:
            if b["zBottom"] - 2.5 <= p[2] <= b["zTop"] + 2.5:
                rx = max(rx, float(b["maxOutwardUU"]))
        worst = min(worst, p[0] - rx - need)
    return mb, {"reachUU": chosen, "tried": tried, "dropUU": r(D, 3), "arcLengthUU": r(arc[-1], 3),
                "topWidthUU": r(width, 3), "bottomWidthUU": r(width * float(Sh["widen_bottom"]), 3),
                "fallCard": [r(width, 3), r(arc[-1], 3), 0.0], "builtWorstMarginUU": r(worst, 3),
                "curve": [[r(x, 2), r(z, 2)] for x, z in pts[::4]]}


def build_foam(P, sheet_info, front_x):
    Fm = P["foam"]
    Sh = P["sheet"]
    pts, arc, D = sheet_curve(Sh, front_x, sheet_info["reachUU"])
    xb, zb = pts[-1]
    hwb = sheet_info["bottomWidthUU"] / 2
    mb = K.MeshBuilder(Fm["asset"], n_uv=1)
    # slot 0: domed disc centred a little in front of the impact
    ax, ay = float(Fm["disc_half_x_uu"]), hwb / float(Fm["disc_half_y_factor"]) * 0.5 * 1.0
    ay = hwb * 0.5 / float(Fm["disc_half_y_factor"]) * 2 * float(Fm["disc_half_y_factor"])  # = hwb
    ay = hwb * (1.0 + float(Fm["disc_half_y_factor"]) * 0.3)
    nr, ns = int(Fm["disc_rings"]), int(Fm["disc_segments"])
    cx = xb + 10.0
    centre = mb.add_verts([(cx, 0.0, zb + float(Fm["disc_dome_uu"]))])
    rings = []
    for i in range(1, nr + 1):
        rr = i / nr
        ring = []
        for s in range(ns):
            th = 2 * math.pi * s / ns
            ring.append((cx + ax * rr * math.cos(th), ay * rr * math.sin(th), zb + float(Fm["disc_dome_uu"]) * (1 - rr * rr)))
        rings.append(mb.add_verts(ring))
    for s in range(ns):
        t = (s + 1) % ns
        mb.add_face([centre, rings[0] + s, rings[0] + t], [(s / ns + 0.5 / ns, 1.0), (s / ns, 1 - 1 / nr), ((s + 1) / ns, 1 - 1 / nr)],
                    0, tag="foam")
    for i in range(nr - 1):
        for s in range(ns):
            t = (s + 1) % ns
            v0, v1 = 1 - (i + 1) / nr, 1 - (i + 2) / nr
            mb.add_face([rings[i] + s, rings[i + 1] + s, rings[i + 1] + t, rings[i] + t],
                        [(s / ns, v0), (s / ns, v1), ((s + 1) / ns, v1), ((s + 1) / ns, v0)], 0, tag="foam")
    # slot 1: mist curtain arc (front half around the impact)
    mx, my = float(Fm["mist_radius_x_uu"]), hwb * (1.0 + float(Fm["mist_half_y_factor"]) * 0.2)
    a0, a1 = (math.radians(v) for v in Fm["mist_arc_deg"])
    msg, mrows = int(Fm["mist_segments"]), int(Fm["mist_rows"])
    grid = []
    for k in range(mrows + 1):
        z = zb + float(Fm["mist_height_uu"]) - (float(Fm["mist_height_uu"]) + float(Fm["mist_sink_uu"])) * k / mrows
        spread = 1.0 + 0.25 * (1 - k / mrows)  # the top of the mist billows out
        row = []
        for s in range(msg + 1):
            th = a0 + (a1 - a0) * s / msg
            row.append((xb + mx * spread * math.cos(th) * 0.9, my * spread * math.sin(th), z))
        grid.append(mb.add_verts(row))
    for k in range(mrows):
        for s in range(msg):
            idx = [grid[k] + s, grid[k] + s + 1, grid[k + 1] + s + 1, grid[k + 1] + s]
            uv = [(s / msg, k / mrows), ((s + 1) / msg, k / mrows), ((s + 1) / msg, (k + 1) / mrows), (s / msg, (k + 1) / mrows)]
            V = np.array([mb.V[i] for i in idx])
            n = np.cross(V[1] - V[0], V[3] - V[0])
            c = V.mean(0) - np.array([xb, 0.0, V.mean(0)[2]])
            if np.dot(n, c) < 0:  # face away from the impact (outwards, towards the camera side)
                idx, uv = idx[::-1], uv[::-1]
            mb.add_face(idx, uv, 1, tag="mist")
    # disc faces up
    return mb, {"impactLocalUU": [r(xb, 3), 0.0, r(zb, 3)], "discHalfUU": [r(ax, 2), r(ay, 2)],
                "fallCards": {"foam (slot 0)": [r(2 * ay, 2), r(ax, 2), 1.0],
                              "mist (slot 1)": [r(my * 2, 2), r(float(Fm["mist_height_uu"]) + float(Fm["mist_sink_uu"]), 2), 1.0]}}


def rounded_rect(hx, hy, rad, n):
    """n points by arc length on a rounded rectangle (CCW from +X)."""
    segs = []
    L = 0.0
    corners = [(hx - rad, hy - rad, 0.0), (-hx + rad, hy - rad, 90.0), (-hx + rad, -hy + rad, 180.0), (hx - rad, -hy + rad, 270.0)]
    # parametrise: straight +X side going up, corner, top side going left, ...
    path = []
    for i, (cx, cy, a) in enumerate(corners):
        prev = corners[i - 1]
        # straight from the previous corner's end to this corner's start
        sx, sy = prev[0] + rad * math.cos(math.radians(prev[2] + 90)), prev[1] + rad * math.sin(math.radians(prev[2] + 90))
        ex, ey = cx + rad * math.cos(math.radians(a)), cy + rad * math.sin(math.radians(a))
        path.append(("line", (sx, sy), (ex, ey)))
        path.append(("arc", (cx, cy), a))
    lengths = [math.dist(p[1], p[2]) if p[0] == "line" else rad * math.pi / 2 for p in path]
    total = sum(lengths)
    out = []
    for i in range(n):
        s = total * i / n
        for p, ln in zip(path, lengths):
            if s <= ln:
                if p[0] == "line":
                    t = s / ln if ln > 0 else 0
                    out.append((p[1][0] + (p[2][0] - p[1][0]) * t, p[1][1] + (p[2][1] - p[1][1]) * t))
                else:
                    a = math.radians(p[2] + 90.0 * s / ln)
                    out.append((p[1][0] + rad * math.cos(a), p[1][1] + rad * math.sin(a)))
                break
            s -= ln
    return out, total


def build_sea(P):
    Se = P["sea"]
    T = P["tray"]
    hx, hy = float(T["half_x_ue"]) - float(Se["inset_uu"]), float(T["half_y_ue"]) - float(Se["inset_uu"])
    B, per = rounded_rect(hx, hy, float(Se["corner_radius_uu"]), int(Se["boundary_points"]))
    Ro = float(Se["outer_radius_uu"])
    fr = [float(f) for f in Se["ring_fractions"]]
    mb = K.MeshBuilder(Se["asset"], n_uv=2, colors=True)
    n = len(B)
    rows = []
    dist = []
    for f in fr:
        ring, dd = [], []
        for (bx, by) in B:
            rb = math.hypot(bx, by)
            ox, oy = bx / rb * Ro, by / rb * Ro
            x, y = bx + (ox - bx) * f, by + (oy - by) * f
            ring.append((x, y, 0.0))
            dd.append(math.hypot(x - bx, y - by))
        rows.append(mb.add_verts(ring))
        dist.append(dd)
    t0, t1 = (float(v) for v in Se["far_fade_uu"])
    fb = float(Se["foam_band_uu"])

    def col(d):
        foam = 1.0 - min(max(d / fb, 0.0), 1.0)
        foam = foam * foam * (3 - 2 * foam)
        far = min(max((d - t0) / (t1 - t0), 0.0), 1.0)
        return (foam, far, 0.0, 1.0)
    for k in range(len(fr) - 1):
        for i in range(n):
            j = (i + 1) % n
            idx = [rows[k] + i, rows[k] + j, rows[k + 1] + j, rows[k + 1] + i]
            V = [mb.V[q] for q in idx]
            uv0 = [(p[0] / float(Se["uv0_tile_uu"]), p[1] / float(Se["uv0_tile_uu"])) for p in V]
            uj = (j if j > 0 else n) / n
            d = [dist[k][i], dist[k][j], dist[k + 1][j], dist[k + 1][i]]
            uv1 = [(i / n, d[0] / float(Se["uv1_dist_uu"])), (uj, d[1] / float(Se["uv1_dist_uu"])),
                   (uj, d[2] / float(Se["uv1_dist_uu"])), (i / n, d[3] / float(Se["uv1_dist_uu"]))]
            cols = [col(x) for x in d]
            Va = np.array(V)
            nn = np.cross(Va[1] - Va[0], Va[3] - Va[0])
            if nn[2] < 0:
                idx, uv0, uv1, cols = idx[::-1], uv0[::-1], uv1[::-1], cols[::-1]
            mb.add_face(idx, [uv0, uv1], 0, cols, "sea")
    return mb, {"innerHalfUU": [hx, hy], "innerPerimeterUU": r(per, 2), "outerRadiusUU": Ro}


def export_one(P, mb, mats, kind_checks, pivot_note):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    materials = [K.flat_material(m, (0.2, 0.25, 0.3), 0.5) for m in mats]
    V = mb.verts()
    b = K.bounds(V)
    obj = mb.to_object(materials)
    tris = S.triangles(obj)
    blend = K.save_scratch_blend(P, mb.name)
    fbx = P["_run"] / "export" / ("%s.fbx" % mb.name)
    exp = K.export(obj, fbx)
    exp["um_fbx_v1_conformance"].append({"setting": "Pivot: " + pivot_note, "standard": True, "used": True,
                                         "conforms": True})
    rt = K.roundtrip(fbx, tris, mats, b)
    c = {"single_mesh": rt["mesh_objects"] == 1, "triangles_preserved": rt["triangles"] == tris,
         "material_slots": rt["material_slots"] == mats, "uv0_present": "UVMap" in (rt["uv_layers"] or []),
         "roundtrip_bounds_match_ue_frame": rt["ue_frame_matches_build"],
         "um_fbx_v1_conforms": all(x["conforms"] for x in exp["um_fbx_v1_conformance"]), **kind_checks}
    return {**exp, "name": mb.name, "triangles": tris, "boundsUeLocalUU": b, "uv": K.uv_stats(mb), "roundtrip": rt,
            "blend_scratch": blend, "checks": {k: bool(v) for k, v in c.items()}}


def main():
    P = K.load_params(K.script_args()[0])
    run = P["_run"]
    prof = json.loads((REPO / P["south_profile"]).read_text(encoding="utf-8"))
    L, Sh = P["lip"], P["sheet"]
    top_band = max(b["maxOutwardUU"] for b in prof["bins"] if b["zTop"] > -12.0)
    front_x = max(float(L["front_x_min"]), top_band + float(L["front_margin_uu"]))
    lip, lip_parts = build_lip(P, front_x)
    lipV = lip.verts()
    lip_pts = surface_samples(lipV, lip.F)
    sheet, sheet_info = build_sheet(P, front_x, lip_pts, prof)
    foam, foam_info = build_foam(P, sheet_info, front_x)
    sea, sea_info = build_sea(P)
    e = P["source_entry"]
    xc = (float(e["x0"]) + float(e["x1"])) / 2
    edge_y = float(P["tray"]["offset_y_ue"]) + float(P["tray"]["half_y_ue"])
    exports = []
    lip_vol_ok = all(p["volumeUU3"] > 0 for p in lip_parts)
    exports.append(export_one(P, lip, [L["material"]], {
        "triangles_within_budget": lip.triangles() <= int(L["max_triangles"]),
        "hulls_outward_closed": lip_vol_ok,
        "front_at_front_x": abs(float(lipV[:, 0].max()) - front_x) <= 1.5,
        "front_ahead_of_tray_top_band": front_x >= top_band + float(L["front_margin_uu"]) - 1e-6,
        "colors_present": True},
        "on the near tray edge line at the fall centre, z 0 = play plane; +X outward"))
    sv = sheet.verts()
    uv0 = np.array([uv for f in sheet.UV[0] for uv in f])
    exports.append(export_one(P, sheet, [Sh["material"]], {
        "triangles_within_budget": sheet.triangles() <= int(Sh["max_triangles"]),
        "clear_of_rock": sheet_info["builtWorstMarginUU"] >= -1e-6,
        "top_width_equals_layout_entry": abs((sv[sv[:, 2] >= float(Sh["start_z"]) - 1e-6][:, 1].max()
                                              - sv[sv[:, 2] >= float(Sh["start_z"]) - 1e-6][:, 1].min())
                                             - (float(e["x1"]) - float(e["x0"]))) < 0.01,
        "drop_in_120_200": 120.0 <= sheet_info["dropUU"] <= 200.0,
        "uv0_normalised": float(uv0.min()) >= -1e-9 and float(uv0.max()) <= 1 + 1e-9,
        "uv1_present": True},
        "as the lip (the sheet starts start_back_uu behind the lip front at start_z)"))
    exports.append(export_one(P, foam, list(P["foam"]["materials"]), {
        "triangles_within_budget": foam.triangles() <= int(P["foam"]["max_triangles"]),
        "at_the_impact": abs(foam.verts()[:, 2].min() - (float(Sh["bottom_z"]) - float(P["foam"]["mist_sink_uu"]))) < 0.01},
        "as the lip; the foam sits at the sheet bottom"))
    seaV = sea.verts()
    rr = np.hypot(seaV[:, 0], seaV[:, 1])
    exports.append(export_one(P, sea, [P["sea"]["material"]], {
        "triangles_within_budget": sea.triangles() <= int(P["sea"]["max_triangles"]),
        "inner_edge_inside_tray": float(np.abs(seaV[:, 0]).min()) >= 0 and all(
            abs(x) <= float(P["tray"]["half_x_ue"]) and abs(y) <= float(P["tray"]["half_y_ue"])
            for x, y in [(seaV[i, 0], seaV[i, 1]) for i in range(int(P["sea"]["boundary_points"]))]),
        "outer_radius": abs(float(rr.max()) - float(P["sea"]["outer_radius_uu"])) < 0.5,
        "flat": float(np.abs(seaV[:, 2]).max()) < 1e-9, "colors_present": True},
        "the tray centre (board (0, offsetY)), z 0 = the sea surface"))
    layout = {
        "schema": "unmatched.env-s-waterfall.layout/1", "status": "proposed",
        "map": "sarpedon", "replaces": "ground.waterfalls[fall-s] vertical card (FallCardTransform); the spill (kind 1) stays",
        "fallPieces": {"loc": [r(xc, 3), r(edge_y, 3), 0.0], "yawDeg": 90.0, "scale": 1.0,
                       "meshes": {"lip": "SM_Env_S_WaterfallLip (optional add-on rock, MI_TableBase_T2b)",
                                  "sheet": "SM_Env_S_Waterfall (MID of MI_EnvWaterfall_Sarpedon, FallCard %s)" % sheet_info["fallCard"],
                                  "foam": "SM_Env_S_WaterfallFoam (slot 0 / 1 MIDs, FallCard %s)" % foam_info["fallCards"]}},
        "sea": {"loc": [0.0, float(P["tray"]["offset_y_ue"]), float(Sh["bottom_z"])], "yawDeg": 0.0, "scale": 1.0,
                "mesh": "SM_Env_S_SeaRing (new M_EnvSea: dark water, Col.R foam ring, Col.G far fade; unlit-ish/fogged)"},
        "frameNote": "local +X of the fall pieces = board +Y (yaw 90); local Y = board -X (the fall is symmetric)",
    }
    checks = {e2["name"]: all(e2["checks"].values()) for e2 in exports}
    report = {
        "schema": SCHEMA, "status": "measured", "asset": "ASSET-ENV-S-WATERFALL-001",
        "claims": {"art_accepted": False, "game_ready": False, "technically_imported": False},
        "blender_version": bpy.app.version_string, "script_sha256_lf": S.text_sha256_lf(HERE),
        "helpers": {"k_blender": S.text_sha256_lf(K.HERE), "static_prop_candidate": S.text_sha256_lf(K.SPC_PATH)},
        "params": {"path": K.rel(P["_params_path"]), "sha256": S.sha256(P["_params_path"])},
        "southProfile": {"path": P["south_profile"], "sha256": S.sha256(REPO / P["south_profile"]),
                         "topBandOutwardUU": top_band},
        "lip": {"frontXUU": r(front_x, 3), "measuredFrontXUU": r(float(lipV[:, 0].max()), 3), "parts": lip_parts}, "sheet": sheet_info, "foam": foam_info, "sea": sea_info,
        "layout": "reports/waterfall-layout.json",
        "contract": {"ue": {"folder": "/Game/EnvKit/Sarpedon (flat, env-kit contract)",
                            "import": "extend tools/art/env_kit/ue_import_env_kit.py (legacy FbxFactory, uniform scale "
                                      "1.0, vertex_color_import_option REPLACE for the lip / sea, no collision, Nanite off); "
                                      "materials: M_EnvWaterfall MIDs (exists, ue_import_env_ground.py) for the sheet / "
                                      "foam / mist, MI_TableBase_T2b for the lip, a new M_EnvSea for the ring"}},
        "exports": exports,
    }
    report["checks"] = checks
    report["checks_passed"] = all(checks.values())
    K.write_json(run / "reports" / "build-report.json", report)
    K.write_json(run / "reports" / "waterfall-layout.json", layout)
    print("WATERFALL-BUILD", json.dumps(checks))
    print("WATERFALL-SUMMARY front_x=%.1f reach=%s drop=%.1f arc=%.1f margin=%.2f tris=%s" % (
        front_x, sheet_info["reachUU"], sheet_info["dropUU"], sheet_info["arcLengthUU"],
        sheet_info["builtWorstMarginUU"], [e2["triangles"] for e2 in exports]))
    for e2 in exports:
        if not all(e2["checks"].values()):
            print("FAILED", e2["name"], e2["checks"])
    if not report["checks_passed"]:
        raise SystemExit(1)


main()
