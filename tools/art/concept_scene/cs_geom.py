"""ENV-MAPS P8.1 concept scene: procedural prop geometry for the baked meshes (logs, ropes, chamfered blocks) and the
C0-pixel placement on the island (system Python, numpy).

Every painted element is placed by C0 pixels read on the de-lit plate: the foot = the first hit of the C0 ray of the
painted foot pixel on the island mesh (SM_Env_S_Island.pre.npz), the top = the height on the vertical through the
foot whose projection lands on the painted top row (so the element stands vertical in 3D and covers its painted
pixels at C0), the radius = half the painted width at the foot's C0 depth.
Faces are CCW outward in the UE numbers' math frame (cs_common.Mesh), UVs are left empty (the Smart UV atlas of
cs_blender.py 'export' replaces them).
"""
from __future__ import annotations

import math

import numpy as np

import cs_common as CS


def ray_mesh(o, d, P, F) -> float:
    a, b, c = P[F[:, 0]], P[F[:, 1]], P[F[:, 2]]
    e1, e2 = b - a, c - a
    pv = np.cross(d, e2)
    det = np.einsum("ij,ij->i", e1, pv)
    ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    tv = o - a
    u = np.einsum("ij,ij->i", tv, pv) * inv
    qv = np.cross(tv, e1)
    v = (qv @ d) * inv
    t = np.einsum("ij,ij->i", e2, qv) * inv
    hit = ok & (u >= -1e-9) & (v >= -1e-9) & (u + v <= 1 + 1e-9) & (t > 1)
    return float(t[hit].min()) if hit.any() else math.inf


class Ground:
    """The island mesh as the ground for C0-pixel placement (+ the ship hull when given)."""

    def __init__(self, meshes):
        Ps, Fs, base = [], [], 0
        for m in meshes:
            Ps.append(m.board())
            Fs.append(m.F + base)
            base += len(m.V)
        self.P = np.vstack(Ps)
        self.F = np.vstack(Fs)
        self.cam = CS.cam0()

    def hit_px(self, px, py) -> np.ndarray:
        d = self.cam.rays(np.array(float(px)), np.array(float(py)))
        d = d / np.linalg.norm(d)
        t = ray_mesh(self.cam.pos, d, self.P, self.F)
        if not math.isfinite(t):
            raise ValueError(f"C0 px ({px}, {py}) misses the ground")
        return self.cam.pos + t * d

    def height_at(self, x, y) -> float:
        """Z of the topmost ground face above (x, y) (vertical ray from above)."""
        t = ray_mesh(np.array([x, y, 2000.0]), np.array([0.0, 0.0, -1.0]), self.P, self.F)
        if not math.isfinite(t):
            raise ValueError(f"({x}, {y}) is off the ground")
        return 2000.0 - t


def vertical_top(foot, top_py, cam=None, lo=5.0, hi=3000.0) -> float:
    """Height above `foot` whose C0 projection lands on row top_py (bisection; the row is above the foot's)."""
    cam = cam or CS.cam0()
    for _ in range(60):
        mid = (lo + hi) / 2
        if cam.project(foot + np.array([0.0, 0.0, mid]))[0][1] > top_py:
            lo = mid
        else:
            hi = mid
    return lo


def px_radius(foot, width_px, cam=None) -> float:
    cam = cam or CS.cam0()
    return width_px / 2 * float((foot - cam.pos) @ cam.fwd) / cam.f_px


def _orient_out(V, F, centre_fn):
    """Flip faces whose normal points towards centre_fn(face centre) (convex-ish parts)."""
    P = V[F]
    n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
    c = P.mean(1)
    inward = np.einsum("ij,ij->i", n, c - centre_fn(c)) < 0
    F = F.copy()
    F[inward] = F[inward][:, ::-1]
    return F


def log(foot, top, radius, seg=10, rings=4, point=0.0, rng=None, taper=0.85, wobble=0.06):
    """A log / post: tapered cylinder from foot to top, `rings` intermediate rings with a small wobble, top either flat
    (point 0) or sharpened to a point `point` x radius above the last ring. Closed (bottom cap)."""
    rng = rng or np.random.default_rng(0)
    foot, top = np.asarray(foot, float), np.asarray(top, float)
    ax = top - foot
    L = np.linalg.norm(ax)
    ax /= L
    ref = np.array([1.0, 0.0, 0.0]) if abs(ax[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(ax, ref)
    u /= np.linalg.norm(u)
    v = np.cross(ax, u)
    ang = np.arange(seg) * 2 * math.pi / seg + rng.uniform(0, 2 * math.pi)
    V = []
    for k in range(rings + 1):
        t = k / rings
        r = radius * (1 - (1 - taper) * t) * (1 + wobble * rng.uniform(-1, 1))
        c = foot + ax * L * t
        V += list(c + r * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * v))
    tip = top + ax * radius * point if point > 0 else top
    V.append(tip)
    V.append(foot)
    V = np.array(V)
    F = []
    for k in range(rings):
        for i in range(seg):
            j = (i + 1) % seg
            a, b = k * seg + i, k * seg + j
            F += [[a, b, b + seg], [a, b + seg, a + seg]]
    top_i, bot_i = len(V) - 2, len(V) - 1
    for i in range(seg):
        j = (i + 1) % seg
        F.append([rings * seg + i, rings * seg + j, top_i])
        F.append([i, bot_i, j])
    F = np.array(F, np.int64)

    def centre(c):
        t = np.clip((c - foot) @ ax, 0, L)
        return foot + t[:, None] * ax[None]
    F = _orient_out(V, F, centre)
    return V, F


def rope(a, b, sag, radius, seg=6, n=12):
    """A catenary-like rope tube from a to b sagging `sag` uu at the middle (parabola), open ends."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = np.linspace(0, 1, n + 1)
    C = a[None] + (b - a)[None] * t[:, None] - np.array([0.0, 0.0, 1.0])[None] * (4 * sag * t * (1 - t))[:, None]
    T = np.gradient(C, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True)
    V = []
    for i in range(n + 1):
        ref = np.array([0.0, 0.0, 1.0]) if abs(T[i][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        u = np.cross(T[i], ref)
        u /= np.linalg.norm(u)
        w = np.cross(T[i], u)
        ang = np.arange(seg) * 2 * math.pi / seg
        V += list(C[i] + radius * (np.cos(ang)[:, None] * u + np.sin(ang)[:, None] * w))
    V = np.array(V)
    F = []
    for i in range(n):
        for k in range(seg):
            j = (k + 1) % seg
            p, q = i * seg + k, i * seg + j
            F += [[p, q, q + seg], [p, q + seg, p + seg]]
    F = np.array(F, np.int64)

    def centre(c):
        # nearest point of the centre line
        d = np.linalg.norm(c[:, None, :] - C[None], axis=2)
        return C[np.argmin(d, axis=1)]
    return V, _orient_out(V, F, centre)


def band(centre, radius, z, tube, seg=8, n=16):
    """A rope band (torus) around a log group: centre (x, y), ring radius, height z."""
    ang = np.arange(n) * 2 * math.pi / n
    C = np.c_[centre[0] + radius * np.cos(ang), centre[1] + radius * np.sin(ang), np.full(n, z)]
    V = []
    for i in range(n):
        T = C[(i + 1) % n] - C[i - 1]
        T /= np.linalg.norm(T)
        u = np.array([C[i][0] - centre[0], C[i][1] - centre[1], 0.0])
        u /= np.linalg.norm(u)
        w = np.cross(T, u)
        a2 = np.arange(seg) * 2 * math.pi / seg
        V += list(C[i] + tube * (np.cos(a2)[:, None] * u + np.sin(a2)[:, None] * w))
    V = np.array(V)
    F = []
    for i in range(n):
        i2 = (i + 1) % n
        for k in range(seg):
            j = (k + 1) % seg
            F += [[i * seg + k, i * seg + j, i2 * seg + j], [i * seg + k, i2 * seg + j, i2 * seg + k]]
    F = np.array(F, np.int64)

    def ctr(c):
        d = np.linalg.norm(c[:, None, :] - C[None], axis=2)
        return C[np.argmin(d, axis=1)]
    return V, _orient_out(V, F, ctr)


def chamfer_box(centre, size, yaw_deg=0.0, bevel=1.5, tilt=(0.0, 0.0)):
    """A box with chamfered edges (bevel uu): the convex hull of the 8 corners each split into 3 points moved inwards
    along one axis (24 points; 6 octagon faces, 12 edge strips, 8 corner triangles). size = (sx, sy, sz) full
    extents, yaw about Z, small tilts (deg about X, Y)."""
    from scipy.spatial import ConvexHull
    sx, sy, sz = (float(v) / 2 for v in size)
    b = min(float(bevel), sx * 0.45, sy * 0.45, sz * 0.45)
    V = []
    for cx in (-1, 1):
        for cy in (-1, 1):
            for cz in (-1, 1):
                base = np.array([cx * sx, cy * sy, cz * sz])
                for axis in range(3):
                    p = base.copy()
                    p[axis] -= np.sign(p[axis]) * b
                    V.append(p)
    V = np.array(V)
    F = ConvexHull(V).simplices.astype(np.int64)
    F = _orient_out(V, F, lambda c: np.zeros_like(c))
    tx, ty = (math.radians(t) for t in tilt)
    Rx = np.array([[1, 0, 0], [0, math.cos(tx), -math.sin(tx)], [0, math.sin(tx), math.cos(tx)]])
    Ry = np.array([[math.cos(ty), 0, math.sin(ty)], [0, 1, 0], [-math.sin(ty), 0, math.cos(ty)]])
    a = math.radians(yaw_deg)
    Rz = np.array([[math.cos(a), -math.sin(a), 0], [math.sin(a), math.cos(a), 0], [0, 0, 1]])
    V = V @ (Rz @ Ry @ Rx).T + np.asarray(centre, float)
    return V, F


class Parts:
    """Accumulates (V, F) parts into one mesh."""

    def __init__(self):
        self.V, self.F, self.n = [], [], 0
        self.tags = []

    def add(self, V, F, tag=""):
        self.V.append(np.asarray(V, float))
        self.F.append(np.asarray(F, np.int64) + self.n)
        self.n += len(V)
        self.tags += [tag] * len(F)

    def mesh(self, name, slot, pivot) -> CS.Mesh:
        V = np.vstack(self.V)
        F = np.vstack(self.F)
        return CS.Mesh(name, V - np.asarray(pivot, float), F, np.zeros((len(F), 3, 2)), np.zeros(len(F), int),
                       np.ones(len(F), bool), [slot], pivot)


def closed_check(V, F) -> dict:
    """Edges used once (open boundary) / more than twice, and the signed volume (> 0 = outward)."""
    e = np.sort(np.vstack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    _, cnt = np.unique(e, axis=0, return_counts=True)
    vol = float(np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6)
    return {"boundaryEdges": int((cnt == 1).sum()), "nonManifoldEdges": int((cnt > 2).sum()), "volume": vol}
