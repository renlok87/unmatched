"""Base geometry and team-band helpers of the opt-in W2-c options (plain numpy, no bpy; skill pilot F83, F104, F143,
F150). The Blender stages call them on arrays they read from bpy (st_prepare: base.flatten_bottom, st_retopo:
base.rim_smooth, st_uv: textures.team_mask.base_band.height_m); the tests call them on synthetic arrays.

Frame of every coordinate: the final frame of the profile (metres, -Y front, +X the figure's left, +Z up, base bottom at
z = 0, base top at scale.base_height_m). Profiles without the keys never reach this module (byte-identical runs)."""

import numpy as np

# base.flatten_bottom: floor = area-weighted quantile of the centroid z of the downward faces (n_z < down_normal_z) of
# the base part. Every vertex of a downward face at most band_m above the floor (a lifted rim or a raised patch of the
# underside) goes down to it, and the vertices above it follow with a linear falloff over falloff_m (the lift at their xy
# from the nearest underside vertices): the rim chamfer keeps its shape and texture, no stretched strip (falloff_m 0 =
# snap the underside only). Every base vertex still below the floor goes up to it (hanging bumps). Then z is rescaled
# linearly so that the floor is z = 0 and the top keeps its height.
FLATTEN_DEFAULTS = {"floor_quantile": 0.5, "band_m": 0.008, "falloff_m": 0.012, "down_normal_z": -0.5}
FLATTEN_MAX_BAND_M = 0.015
# base.rim_smooth: z of every boundary loop of the listed parts that lies inside z_band_m is smoothed along the loop
# (circular Gaussian over the arc length, sigma = window_m / 2), the shift clamped to max_shift_m; the vertices one edge
# away from the loop follow with ring_weight x the mean shift of their loop neighbours.
RIM_DEFAULTS = {"window_m": 0.006, "max_shift_m": 0.002, "min_perimeter_cm": 1.0, "ring_weight": 0.5}
RIM_MAX_SHIFT_M = 0.004
RIM_MAX_WINDOW_M = 0.03
# textures.team_mask.base_band.height_m: a base face is in the team band when its centroid z lies in [z0, z1] and it
# does not face down (n_z >= DOWN_NORMAL_Z: the underside never shows)
DOWN_NORMAL_Z = -0.5
MASK_ATTRIBUTE = "UM_Mask"  # the base vertex mask of M_UM_BaseMarker (candidate_build.base, Harpy): R band, G/B pips


def weighted_quantile(values, weights, q):
    values = np.asarray(values, np.float64)
    weights = np.asarray(weights, np.float64)
    if values.size == 0:
        raise ValueError("weighted_quantile of an empty set")
    order = np.argsort(values, kind="stable")
    v, w = values[order], weights[order]
    cum = np.cumsum(w)
    target = float(q) * cum[-1]
    i = int(np.searchsorted(cum, target, side="left"))
    return float(v[min(i, len(v) - 1)])


def flatten_cfg(cfg):
    out = dict(FLATTEN_DEFAULTS)
    out.update({k: v for k, v in (cfg or {}).items() if k in FLATTEN_DEFAULTS})
    return out


def floor_level(face_z, face_nz, face_area, cfg):
    """Floor height of the base underside (metres): area-weighted floor_quantile of the centroid z of the faces whose
    normal z is below down_normal_z (the downward faces)."""
    c = flatten_cfg(cfg)
    down = np.asarray(face_nz) < c["down_normal_z"]
    if not down.any():
        raise ValueError("base.flatten_bottom: the base has no downward faces (n_z < %s)" % c["down_normal_z"])
    return weighted_quantile(np.asarray(face_z)[down], np.asarray(face_area)[down], c["floor_quantile"])


def nearest_numpy(src_xy, query_xy, k):
    """(distances, indices) of the k nearest src points per query (brute force in chunks: tests and small meshes; the
    prepare stage passes a mathutils KDTree)."""
    src_xy, query_xy = np.asarray(src_xy, np.float64), np.asarray(query_xy, np.float64)
    k = min(k, len(src_xy))
    d_out, i_out = [], []
    for s in range(0, len(query_xy), 2048):
        q = query_xy[s:s + 2048]
        d2 = ((q[:, None, :] - src_xy[None, :, :]) ** 2).sum(-1)
        idx = np.argsort(d2, axis=1, kind="stable")[:, :k]
        d_out.append(np.sqrt(np.take_along_axis(d2, idx, 1)))
        i_out.append(idx)
    return np.concatenate(d_out), np.concatenate(i_out)


def flatten_z(co, bottom_vertex, z_floor, band_m, falloff_m=0.0, nearest=nearest_numpy, k=4):
    """-> (new z, stats). co: base vertex positions [N, 3]; bottom_vertex: True for a vertex of a downward face.
    Lift L = z - floor of the bottom vertices with floor < z <= floor + band_m (0 for the other bottom vertices up to
    floor + band_m). falloff_m 0: those vertices snap to the floor. falloff_m > 0: they go to the floor and every other
    base vertex below floor + band_m + falloff_m moves down by L(xy) x clip(1 - (z - floor - L(xy)) / falloff_m, 0, 1),
    L(xy) = inverse-distance mean over the k nearest underside vertices in xy (`nearest(src_xy, query_xy, k)`). Then every
    vertex below the floor goes up to it and z' = (z - floor) x top / (top - floor)."""
    co = np.asarray(co, np.float64)
    z = co[:, 2]
    bottom_vertex = np.asarray(bottom_vertex, bool)
    top = float(z.max())
    if not top > z_floor:
        raise ValueError("base.flatten_bottom: floor %.5f m is not below the top %.5f m" % (z_floor, top))
    src = bottom_vertex & (z <= z_floor + band_m)
    lift = np.where(src, np.maximum(z - z_floor, 0.0), 0.0)
    lifted = src & (lift > 0)
    dz = -lift
    followers = 0
    if falloff_m > 0 and lifted.any():
        cand = ~src & (z < z_floor + band_m + falloff_m)
        if cand.any():
            d, idx = nearest(co[src, :2], co[cand, :2], k)
            d, idx = np.asarray(d).reshape(cand.sum(), -1), np.asarray(idx).reshape(cand.sum(), -1)
            w = 1.0 / (d + 1e-5)
            lq = (w * lift[src][idx]).sum(1) / w.sum(1)
            wt = np.clip(1.0 - (z[cand] - z_floor - lq) / falloff_m, 0.0, 1.0)
            dz[cand] = -lq * wt
            followers = int(((lq * wt) > 0).sum())
    zw = z + dz
    up = zw < z_floor
    zc = np.where(up, z_floor, zw)
    scale = top / (top - z_floor)
    out = (zc - z_floor) * scale
    out[z == top] = top  # the top keeps its exact height (the feet contact of the frame map)
    shift = out - z
    stats = {"floor_m": round(float(z_floor), 6), "band_m": float(band_m), "falloff_m": float(falloff_m),
             "z_scale": round(scale, 6), "vertices": int(z.size), "raised_to_floor": int((up & (z < z_floor)).sum()),
             "lowered_to_floor": int(lifted.sum()), "followers_lowered": followers,
             "max_raise_mm": round(float(np.where(z < z_floor, z_floor - z, 0.0).max(initial=0.0) * 1000), 3),
             "max_lower_mm": round(float(lift.max(initial=0.0) * 1000), 3),
             "max_abs_shift_mm": round(float(np.abs(shift).max() * 1000), 3)}
    return out, stats


def bottom_profile(co, tris, axis, step_m=0.001, inner_share=0.9):
    """Lowest z of the mesh per column of width step_m along `axis` (0: x, seen from the front; 1: y, seen from the
    side): the lower envelope of the projected triangle edges. Columns within inner_share of the half-width (the
    chamfered outer edge excluded). -> {"columns", "share_gt_1mm", "share_gt_2mm", "p95_mm", "max_mm"}."""
    co = np.asarray(co, np.float64)
    tris = np.asarray(tris, np.int64)
    e = np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    e = np.unique(np.sort(e, 1), axis=0)
    a, b = co[e[:, 0]], co[e[:, 1]]
    ua, ub = a[:, axis], b[:, axis]
    lo_u, hi_u = np.minimum(ua, ub), np.maximum(ua, ub)
    c0 = np.ceil(lo_u / step_m - 0.5).astype(np.int64)
    c1 = np.floor(hi_u / step_m - 0.5).astype(np.int64)
    n = np.maximum(c1 - c0 + 1, 0)
    idx = np.repeat(np.arange(len(e)), n)
    col = c0[idx] + (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n))
    u = (col + 0.5) * step_m
    du = ub[idx] - ua[idx]
    t = np.where(np.abs(du) > 1e-12, (u - ua[idx]) / np.where(np.abs(du) > 1e-12, du, 1.0), 0.0)
    zz = a[idx, 2] + t * (b[idx, 2] - a[idx, 2])
    # vertices themselves (columns their x falls in)
    vc = np.floor(co[:, axis] / step_m).astype(np.int64)
    cols = np.concatenate([col, vc])
    zs = np.concatenate([zz, co[:, 2]])
    order = np.lexsort((zs, cols))
    cols, zs = cols[order], zs[order]
    first = np.ones(len(cols), bool)
    first[1:] = cols[1:] != cols[:-1]
    ucol, low = cols[first], zs[first]
    half = max(abs(co[:, axis].min()), abs(co[:, axis].max()))
    keep = np.abs((ucol + 0.5) * step_m) <= inner_share * half
    low = low[keep]
    if not low.size:
        return {"columns": 0}
    return {"columns": int(low.size), "share_gt_1mm": round(float((low > 0.001).mean()), 4),
            "share_gt_2mm": round(float((low > 0.002).mean()), 4),
            "p95_mm": round(float(np.percentile(low, 95) * 1000), 3), "max_mm": round(float(low.max() * 1000), 3)}


def rim_cfg(cfg):
    out = dict(RIM_DEFAULTS)
    out.update({k: v for k, v in (cfg or {}).items() if k in RIM_DEFAULTS})
    return out


def loop_arclength(pts):
    pts = np.asarray(pts, np.float64)
    seg = np.linalg.norm(np.roll(pts, -1, 0) - pts, axis=1)
    return np.concatenate([[0.0], np.cumsum(seg)[:-1]]), float(seg.sum())


def gaussian_loop(values, s, perimeter, sigma):
    d = np.abs(s[:, None] - s[None, :])
    d = np.minimum(d, perimeter - d)
    w = np.exp(-0.5 * (d / sigma) ** 2)
    return (w @ values) / w.sum(1)


def tooth_mm(z, s, perimeter, sigma):
    """Height of the rim teeth: |z - Gaussian(z, sigma)| along the loop, p95 and max in millimetres."""
    dev = np.abs(np.asarray(z) - gaussian_loop(np.asarray(z, np.float64), s, perimeter, sigma))
    return round(float(np.percentile(dev, 95) * 1000), 3), round(float(dev.max() * 1000), 3)


def smooth_loop_z(pts, window_m, max_shift_m):
    """New z of an ordered closed loop: circular Gaussian of z over the arc length (sigma = window_m / 2), the shift of
    every vertex clamped to +-max_shift_m. -> (z_new, stats)."""
    pts = np.asarray(pts, np.float64)
    s, per = loop_arclength(pts)
    z = pts[:, 2]
    zs = gaussian_loop(z, s, per, window_m / 2.0)
    shift = np.clip(zs - z, -max_shift_m, max_shift_m)
    z_new = z + shift
    before, after = tooth_mm(z, s, per, window_m / 2.0), tooth_mm(z_new, s, per, window_m / 2.0)
    return z_new, {"vertices": int(len(z)), "perimeter_cm": round(per * 100, 2),
                   "z_mm": [round(float(z.min() * 1000), 2), round(float(z.max() * 1000), 2)],
                   "max_shift_mm": round(float(np.abs(shift).max() * 1000), 3),
                   "clamped_vertices": int((np.abs(zs - z) > max_shift_m).sum()),
                   "tooth_mm_p95_max_before": list(before), "tooth_mm_p95_max_after": list(after)}


def loop_in_band(pts, z_band):
    z = np.asarray(pts)[:, 2]
    return bool(z.min() >= z_band[0] and z.max() <= z_band[1])


def height_band_faces(face_z, face_nz, height_m):
    """Faces of the base in the team band: centroid z inside height_m = [z0, z1] and not facing down."""
    z = np.asarray(face_z)
    return (z >= height_m[0]) & (z <= height_m[1]) & (np.asarray(face_nz) >= DOWN_NORMAL_Z)


def mask_corner_colours(face_in_band, loop_totals):
    """RGBA per face corner (CORNER domain, faces in mesh order): (1, 0, 0, 1) in the band, (0, 0, 0, 1) elsewhere."""
    per_face = np.where(np.asarray(face_in_band, bool)[:, None], [1.0, 0.0, 0.0, 1.0], [0.0, 0.0, 0.0, 1.0])
    return np.repeat(per_face, np.asarray(loop_totals, np.int64), axis=0).astype(np.float32)
