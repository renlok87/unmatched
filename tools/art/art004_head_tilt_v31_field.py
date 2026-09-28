"""Medusa head-tilt v3.1 deformation field (numpy only; shared by export and measurement).

One source of truth for tools/art/art004_face_skeletal_export.py (ART004_HEAD_TILT_V31=<preset>)
and tools/art/art004_head_tilt_v3_measure.py (--v31 mode). Coordinates are the authoring frame
of blender/ASSET-MEDUSA-001/medusa.blend: metres, Z up, face towards -Y. Parts are the atlas
cells (atlas-report.json), labelled per polygon exactly like the v3 scripts. Parts are separate
shells (no shared vertices, no coincident seams), so a per-part field cannot tear a mesh.

Field (rest position p -> p'), per part:
- head field: tripo_part_10 (face/throat), tripo_part_14 (rear neck) and, with crown_mode
  "field", tripo_part_1 (crown) rotate about the X axis through `pivot_m` by
      theta(z) = face_deg * smoothstep((z - z0) / (z1 - z0)),  [z0, z1] = ramp_z_m
  so the throat root (z0 = 0.385 m, start of the `head` bone) stays in place and the angle reaches
  the full value at z1 (0.42 m). Optional top_deg / top_ramp_z_m ease the angle towards top_deg
  over the upper crown, so the crown top keeps its height (a rigid -15 deg drops the 55 uu top
  by 0.6 uu):
      theta(z) += (top_deg - face_deg) * smoothstep((z - t0) / (t1 - t0))
  crown_mode "rigid" rotates the crown by crown_deg instead (the A1 ramp probe).
- collar, tripo_part_3 (100 % `head`-weighted shoulder/collar piece): partial rotation of its
  upper band only, about collar_pivot_m (default pivot_m):
      theta = face_deg * collar_factor * [w(y) * smoothstep((z - f0) / (f1 - f0))
                                         + (1 - w(y)) * smoothstep((z - c0) / (c1 - c0))]
  [c0, c1] = collar_ramp_z_m (back/default); [f0, f1] = collar_front_ramp_z_m (optional, front
  band under the throat plate); w(y) = 1 - smoothstep((y - ya) / (yb - ya)), [ya, yb] =
  collar_front_y_m. Without collar_front_ramp_z_m, w = 0. The shoulders below the ramps stay put.
- quiver, tripo_part_7: rigid rotation (degrees about X, then about Y) about `quiver_pivot_m`,
  so the fletching leans away from the crown; quiver_offset_m is added afterwards.
Everything else (body, arms, hands, bow, base) is not touched.

Corner normals follow the Jacobian J of the field at the corner's vertex: n' = normalize(J^-T n)
(per-vertex split normals). For a rigid rotation J = R, i.e. the normal is rotated; in the
smoothstep bands J = R + (dR/dtheta (p - P)) grad(theta)^T also carries the bend. J is analytic
(checked against central differences in the export report).
"""

import math

import numpy as np

PART_FACE, PART_NECK, PART_CROWN, PART_COLLAR, PART_QUIVER = (
    "tripo_part_10", "tripo_part_14", "tripo_part_1", "tripo_part_3", "tripo_part_7")

# Variant presets (degrees, metres), chosen from a headless sweep (2026-09-28, three rounds) on
# the thresholds of the A1 act. Each export JSON records the full parameter set; the measure script
# recomputes the field from the JSON and compares it with the saved FBX. Common to all three:
# face/rear-neck/crown ramp 0.385 -> 0.42 m (A1 spec), crown in the same field eased to -10 deg at
# the top (0.47 -> 0.55 m), collar front band blended by y, quiver leaned about the centroid of its
# lower end (z < 0.355 m) by -6 deg about X (top backwards) and -4/-5 deg about Y (top outwards).
# crown_deg is used only with crown_mode "rigid".
_QUIVER_PIVOT_M = [-0.0418, 0.0426, 0.339]
PRESETS = {
    # a: pivot = start of the `head` bone (0, 0, 0.385) as in v3; -16 deg; collar front band
    #    0.38 -> 0.405 m (y < -1 cm), back band 0.385 -> 0.43 m (y > 1.5 cm), same pivot.
    "a": {"face_deg": -16, "pivot_m": [0, 0, 0.385], "ramp_z_m": [0.385, 0.42],
          "crown_mode": "field", "crown_deg": -15, "top_deg": -10, "top_ramp_z_m": [0.47, 0.55],
          "collar_factor": 1.0, "collar_ramp_z_m": [0.385, 0.43], "collar_pivot_m": None,
          "collar_front_ramp_z_m": [0.38, 0.405], "collar_front_y_m": [-0.01, 0.015],
          "quiver_rot_deg": [-6, -4], "quiver_pivot_m": _QUIVER_PIVOT_M, "quiver_offset_m": [0, 0, 0]},
    # b: pivot 5 mm forward and 5 mm up; -15.5 deg; collar about its own pivot (0, -0.01, 0.38),
    #    front band 0.375 -> 0.405 m, back band 0.39 -> 0.42 m.
    "b": {"face_deg": -15.5, "pivot_m": [0, -0.005, 0.39], "ramp_z_m": [0.385, 0.42],
          "crown_mode": "field", "crown_deg": -15, "top_deg": -10, "top_ramp_z_m": [0.47, 0.55],
          "collar_factor": 1.0, "collar_ramp_z_m": [0.39, 0.42], "collar_pivot_m": [0, -0.01, 0.38],
          "collar_front_ramp_z_m": [0.375, 0.405], "collar_front_y_m": [-0.015, 0.01],
          "quiver_rot_deg": [-6, -5], "quiver_pivot_m": _QUIVER_PIVOT_M, "quiver_offset_m": [0, 0, 0]},
    # c: pivot 5 mm forward and 5 mm up; -16 deg; collar factor 0.95 about (0, -0.01, 0.385),
    #    front band 0.385 -> 0.41 m, back band 0.385 -> 0.43 m.
    "c": {"face_deg": -16, "pivot_m": [0, -0.005, 0.39], "ramp_z_m": [0.385, 0.42],
          "crown_mode": "field", "crown_deg": -15, "top_deg": -10, "top_ramp_z_m": [0.47, 0.55],
          "collar_factor": 0.95, "collar_ramp_z_m": [0.385, 0.43], "collar_pivot_m": [0, -0.01, 0.385],
          "collar_front_ramp_z_m": [0.385, 0.41], "collar_front_y_m": [-0.015, 0.01],
          "quiver_rot_deg": [-6, -4], "quiver_pivot_m": _QUIVER_PIVOT_M, "quiver_offset_m": [0, 0, 0]},
}

REQUIRED = ("face_deg", "pivot_m", "ramp_z_m", "crown_mode", "crown_deg", "collar_factor",
            "collar_ramp_z_m", "quiver_rot_deg", "quiver_pivot_m", "quiver_offset_m")
OPTIONAL = {"top_deg": None, "top_ramp_z_m": None, "collar_pivot_m": None,
            "collar_front_ramp_z_m": None, "collar_front_y_m": None}


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def dsmoothstep(t):
    inside = (t > 0.0) & (t < 1.0)
    return np.where(inside, 6.0 * t * (1.0 - t), 0.0)


def rot_x(theta):
    """Rotation matrices about X for an array of angles (radians): shape (n, 3, 3)."""
    c, s = np.cos(theta), np.sin(theta)
    r = np.zeros((len(theta), 3, 3))
    r[:, 0, 0] = 1.0
    r[:, 1, 1], r[:, 1, 2] = c, -s
    r[:, 2, 1], r[:, 2, 2] = s, c
    return r


def drot_x(theta):
    c, s = np.cos(theta), np.sin(theta)
    r = np.zeros((len(theta), 3, 3))
    r[:, 1, 1], r[:, 1, 2] = -s, -c
    r[:, 2, 1], r[:, 2, 2] = c, -s
    return r


def euler_xy(deg_x, deg_y):
    ax, ay = math.radians(deg_x), math.radians(deg_y)
    rx = np.array([[1, 0, 0], [0, math.cos(ax), -math.sin(ax)], [0, math.sin(ax), math.cos(ax)]])
    ry = np.array([[math.cos(ay), 0, math.sin(ay)], [0, 1, 0], [-math.sin(ay), 0, math.cos(ay)]])
    return ry @ rx  # X first, then Y


def normalized(params):
    """Validated copy with every optional key present (None = off)."""
    missing = [k for k in REQUIRED if k not in params]
    if missing:
        raise ValueError("v3.1 field params lack %s" % missing)
    unknown = sorted(set(params) - set(REQUIRED) - set(OPTIONAL))
    if unknown:
        raise ValueError("unknown v3.1 field params %s" % unknown)
    p = dict(OPTIONAL)
    p.update(params)
    if not -25 <= p["face_deg"] <= 0:
        raise ValueError("face_deg must be within -25..0")
    if p["crown_mode"] not in ("field", "rigid"):
        raise ValueError("crown_mode must be field or rigid")
    if not 0 <= p["collar_factor"] <= 1:
        raise ValueError("collar_factor must be within 0..1")
    ramps = [p["ramp_z_m"], p["collar_ramp_z_m"]]
    if p["top_deg"] is not None:
        if not -25 <= p["top_deg"] <= 0:
            raise ValueError("top_deg must be within -25..0")
        ramps.append(p["top_ramp_z_m"])
    if p["collar_front_ramp_z_m"] is not None:
        ramps += [p["collar_front_ramp_z_m"], p["collar_front_y_m"]]
    if any(b <= a for a, b in ramps):
        raise ValueError("every ramp must increase")
    return p


def _ramp(x, lo_hi):
    lo, hi = lo_hi
    t = (x - lo) / (hi - lo)
    return smoothstep(t), dsmoothstep(t) / (hi - lo)


def angles(p, part_of_vertex, co):
    """theta (radians) of the X rotation and grad(theta) (n, 3) for every vertex."""
    y, z = co[:, 1], co[:, 2]
    a = math.radians(p["face_deg"])
    theta = np.zeros(len(co))
    grad = np.zeros((len(co), 3))
    head = np.isin(part_of_vertex, [PART_FACE, PART_NECK] + ([PART_CROWN] if p["crown_mode"] == "field" else []))
    s, ds = _ramp(z[head], p["ramp_z_m"])
    theta[head] = a * s
    grad[head, 2] = a * ds
    if p["top_deg"] is not None:
        extra = math.radians(p["top_deg"]) - a
        s, ds = _ramp(z[head], p["top_ramp_z_m"])
        theta[head] += extra * s
        grad[head, 2] += extra * ds
    if p["crown_mode"] == "rigid":
        theta[part_of_vertex == PART_CROWN] = math.radians(p["crown_deg"])
    collar = part_of_vertex == PART_COLLAR
    k = a * p["collar_factor"]
    s_c, ds_c = _ramp(z[collar], p["collar_ramp_z_m"])
    if p["collar_front_ramp_z_m"] is None:
        theta[collar] = k * s_c
        grad[collar, 2] = k * ds_c
    else:
        s_f, ds_f = _ramp(z[collar], p["collar_front_ramp_z_m"])
        sw, dsw = _ramp(y[collar], p["collar_front_y_m"])
        w, dw = 1.0 - sw, -dsw
        theta[collar] = k * (w * s_f + (1.0 - w) * s_c)
        grad[collar, 2] = k * (w * ds_f + (1.0 - w) * ds_c)
        grad[collar, 1] = k * (s_f - s_c) * dw
    return theta, grad


def _rotate(co, idx, theta, grad, pivot, out, jac):
    rel = co[idx] - pivot
    r = rot_x(theta[idx])
    out[idx] = pivot + np.einsum("nij,nj->ni", r, rel)
    dr_rel = np.einsum("nij,nj->ni", drot_x(theta[idx]), rel)
    jac[idx] = r + dr_rel[:, :, None] * grad[idx][:, None, :]


def apply(params, co, part_of_vertex):
    """co: (n, 3) rest positions in metres. Returns (new positions, J (n, 3, 3), moved mask)."""
    p = normalized(params)
    co = np.asarray(co, dtype=float)
    part_of_vertex = np.asarray(part_of_vertex, dtype=object)
    out = co.copy()
    jac = np.repeat(np.eye(3)[None], len(co), axis=0)
    theta, grad = angles(p, part_of_vertex, co)
    active = (theta != 0.0) | np.any(grad != 0.0, axis=1)
    collar = part_of_vertex == PART_COLLAR
    pivot = np.array(p["pivot_m"], dtype=float)
    collar_pivot = np.array(p["collar_pivot_m"] if p["collar_pivot_m"] is not None else p["pivot_m"], dtype=float)
    idx = np.flatnonzero(active & ~collar)
    if len(idx):
        _rotate(co, idx, theta, grad, pivot, out, jac)
    idx = np.flatnonzero(active & collar)
    if len(idx):
        _rotate(co, idx, theta, grad, collar_pivot, out, jac)
    quiver = np.flatnonzero(part_of_vertex == PART_QUIVER)
    qx, qy = p["quiver_rot_deg"][:2]
    offset = np.array(p["quiver_offset_m"], dtype=float)
    if len(quiver) and (qx or qy or offset.any()):
        rq = euler_xy(qx, qy)
        qp = np.array(p["quiver_pivot_m"], dtype=float)
        out[quiver] = qp + (co[quiver] - qp) @ rq.T + offset
        jac[quiver] = rq
    moved = np.linalg.norm(out - co, axis=1) > 1e-9
    return out, jac, moved


def jacobian_check(params, co, part_of_vertex, step=1e-6, every=37):
    """Max abs difference between the analytic J and central differences (sampled moved vertices)."""
    new, jac, moved = apply(params, co, part_of_vertex)
    idx = np.flatnonzero(moved)[::every]
    err = 0.0
    for k in range(3):
        dp = np.zeros(3)
        dp[k] = step
        a, _j, _m = apply(params, co[idx] + dp, part_of_vertex[idx])
        b, _j, _m = apply(params, co[idx] - dp, part_of_vertex[idx])
        err = max(err, float(np.abs((a - b) / (2 * step) - jac[idx][:, :, k]).max()))
    return err, int(len(idx))


def transform_normals(jac_of_corner, normals):
    """n' = normalize(J^-T n) per corner."""
    inv_t = np.transpose(np.linalg.inv(jac_of_corner), (0, 2, 1))
    n = np.einsum("nij,nj->ni", inv_t, normals)
    length = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.where(length > 0, length, 1.0)
