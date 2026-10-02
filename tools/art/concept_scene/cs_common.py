"""ENV-MAPS P8 (path 1) concept scene, track A: shared helpers (system Python; numpy / scipy / PIL).

P8 = a REAL LIT 3D island under the painting: the albedo of every mesh comes from the DE-LIT concept plate projected
from the concept camera C0 (tools/art/concept_paste/cp_common.py: pinhole HFOV 35, pitch -55, yaw -90, distance
1.45 x fit), lit only by the engine (docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md).

Frames and units (as the whole ENV-MAPS track): board space in uu, X right / east, Y towards the K1 camera / south,
Z up, map centre = origin, map plane Z 0. Mesh data are kept as numpy arrays in UE numbers (MeshBuilder convention of
tools/art/env_kit/k_blender.py: faces CCW seen from outside in the right-handed math frame of the UE numbers), local to
the mesh pivot (board position = local + pivot, yaw 0, scale 1).

The C0 -> plate mapping is the P7 one, reused (not re-derived): tools/art/concept_paste/cp_bake.py texel grids +
paste_proto.c0_to_plate through the registration homography of the 'extended2x' plate framing
(tools/art/concept_paste/registration.json), so C0 pixel (x, y) maps into the P8 albedo plate
sarpedon-extended-albedo-2x.png (4680 x 2634, concept framing rect [668, 376, 3344, 1882] - same framing as the P7
sarpedon-extended-2x.png, P8.0 manifest C:/tmp/envmaps-research/p8/plates/manifest.json).

Out of git (ENV-U3 / ENV-U7): every image derived from the concept (atlases, the projected plate) ->
scraped-data/derived/concept-scene/sarpedon/ (gitignored); scratch -> C:/tmp/envmaps-research/p8/sceneA/.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CP_DIR = REPO / "tools" / "art" / "concept_paste"
for _p in (str(HERE), str(CP_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import cp_common as C  # noqa: E402
import paste_proto as pp  # noqa: E402

MAP_KEY = "sarpedon"
SCHEMA_MANIFEST = "unmatched.concept-scene/1"
PARAMS_PATH = HERE / "scene-params.sarpedon.json"
MANIFEST_PATH = HERE / "manifest.sarpedon.json"
WORK = Path("C:/tmp/envmaps-research/p8/sceneA")
PLATES = Path("C:/tmp/envmaps-research/p8/plates")
DERIVED = REPO / "scraped-data" / "derived" / "concept-scene" / MAP_KEY
CC0_RAW = C.MAIN / "art" / "material-library" / "cc0-raw"
LAYOUTS = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "EnvLayouts"
SCENE_LAYOUT = LAYOUTS / "sarpedon.scene.layout.json"
UE_DIR = "/Game/EnvMaps/Sarpedon/Scene"
BLENDER = Path("C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
PC = REPO / "art" / "pipeline-candidates"
RUNS = {"island": PC / "ASSET-ENV-S-ISLAND-001" / "20261002-v1",
        "ship": PC / "ASSET-ENV-S-SHIP-001" / "20261002-v1",
        "fort": PC / "ASSET-ENV-S-FORT-001" / "20261002-v1",
        "props": PC / "ASSET-ENV-S-PROPS-001" / "20261002-v1"}

# the P8.0 albedo plate (Codex de-lit + make_albedo.py), same framing as the P7 extended x2 plate
ALBEDO_PLATE = {"file": "sarpedon-extended-albedo-2x.png", "size": [4680, 2634], "conceptRectPx": [668, 376, 3344, 1882],
                "registrationTag": "extended2x"}
RECT_B = (-384.0, -216.0, 2304.0, 1296.0)  # C0 px x0, y0, x1, y1 of the extended canvas (cp_bake PlateB rect)
MAP_FIELD = (C.FRAME_HX - 2.0, C.FRAME_HY - 2.0)  # 467.667 x 310.667: no island face above Z -3 inside (under frame)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def text_sha256_lf(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def rel(path) -> str:
    try:
        return Path(path).resolve().relative_to(REPO).as_posix()
    except ValueError:
        return Path(path).as_posix()


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path: Path, obj, indent=1):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=indent, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def params() -> dict:
    return load_json(PARAMS_PATH)


def spec() -> dict:
    return pp.load_spec(MAP_KEY)


def r3(v) -> float:
    return round(float(v) + 0.0, 3)


# ------------------------------------------------------------------ camera / rays (cp_common C0, paste_proto rays)
def cam0() -> C.Cam:
    return C.concept_cam()


def ray_z(px, py, z, cam=None) -> np.ndarray:
    """World point(s) of C0 pixel(s) on the plane Z = z."""
    cam = cam or cam0()
    return pp.ray_z(cam, np.asarray(px, float), np.asarray(py, float), z)[0]


def project(P, cam=None):
    """World points -> (C0 px (..., 2), view depth)."""
    cam = cam or cam0()
    return cam.project(np.asarray(P, float))


def registration_h() -> np.ndarray:
    """C0 px -> concept-framing px homography of the extended x2 framing (registration.json, P7a register.py)."""
    reg = load_json(CP_DIR / "registration.json")
    return np.asarray(reg["maps"][MAP_KEY][ALBEDO_PLATE["registrationTag"]]["H"], float)


def c0_to_albedo_px(fx, fy, H=None):
    """C0 px -> pixel of the P8 albedo plate (paste_proto.c0_to_plate, the cp_bake code path)."""
    return pp.c0_to_plate(ALBEDO_PLATE, registration_h() if H is None else H, fx, fy)


# ------------------------------------------------------------------ polygons (2D)
def poly_area(P: np.ndarray) -> float:
    P = np.asarray(P, float)
    x, y = P[:, 0], P[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def ccw(P: np.ndarray) -> np.ndarray:
    P = np.asarray(P, float)
    return P if poly_area(P) > 0 else P[::-1].copy()


def densify(P: np.ndarray, step: float, closed: bool = True) -> np.ndarray:
    P = np.asarray(P, float)
    out = []
    n = len(P)
    for i in range(n if closed else n - 1):
        a, b = P[i], P[(i + 1) % n]
        k = max(1, int(math.ceil(np.linalg.norm(b - a) / step)))
        for j in range(k):
            out.append(a + (b - a) * j / k)
    if not closed:
        out.append(P[-1])
    return np.array(out)


def resample_closed(P: np.ndarray, step: float) -> np.ndarray:
    """Uniform arc-length resampling of a closed polygon (vertex count = round(perimeter / step))."""
    P = np.asarray(P, float)
    Q = np.vstack([P, P[:1]])
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    n = max(8, int(round(s[-1] / step)))
    t = np.arange(n) * s[-1] / n
    return np.c_[np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])]


def smooth_closed(P: np.ndarray, iters: int = 2, k: float = 0.5) -> np.ndarray:
    P = np.asarray(P, float).copy()
    for _ in range(iters):
        P = P * (1 - k) + 0.5 * k * (np.roll(P, 1, 0) + np.roll(P, -1, 0))
    return P


def inside(poly: np.ndarray, pts: np.ndarray) -> np.ndarray:
    """Even-odd point-in-polygon (vectorised over the points)."""
    poly = np.asarray(poly, float)
    pts = np.asarray(pts, float)
    x, y = pts[..., 0], pts[..., 1]
    res = np.zeros(x.shape, bool)
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        cond = (y1 > y) != (y2 > y)
        with np.errstate(divide="ignore", invalid="ignore"):
            xc = (x2 - x1) * (y - y1) / (y2 - y1 + 1e-300) + x1
        res ^= cond & (x < xc)
    return res


def vertex_normals_2d(P: np.ndarray) -> np.ndarray:
    """Outward unit normals of a CCW polygon (average of the adjacent edge normals)."""
    P = np.asarray(P, float)
    e0 = P - np.roll(P, 1, 0)
    e1 = np.roll(P, -1, 0) - P
    t = e0 / np.maximum(np.linalg.norm(e0, axis=1, keepdims=True), 1e-9) + \
        e1 / np.maximum(np.linalg.norm(e1, axis=1, keepdims=True), 1e-9)
    t /= np.maximum(np.linalg.norm(t, axis=1, keepdims=True), 1e-9)
    return np.c_[t[:, 1], -t[:, 0]]  # CCW: (ty, -tx) points outward


def seg_dist(pts: np.ndarray, poly: np.ndarray, closed=True) -> np.ndarray:
    """Distance of points (n, 2) to a polyline / polygon outline."""
    pts = np.asarray(pts, float)
    A = np.asarray(poly, float)
    B = np.roll(A, -1, 0) if closed else A[1:]
    A = A if closed else A[:-1]
    d = np.full(len(pts), np.inf)
    for a, b in zip(A, B):
        ab = b - a
        t = np.clip(((pts - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        d = np.minimum(d, np.linalg.norm(pts - (a + t[:, None] * ab), axis=1))
    return d


# ------------------------------------------------------------------ deterministic noise
def _hash01(ix, iy, seed):
    h = (np.asarray(ix, np.int64) * 374761393 + np.asarray(iy, np.int64) * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h = h ^ (h >> 16)
    return (h & 0xFFFFFF).astype(np.float64) / float(0xFFFFFF)


def value_noise(x, y, scale: float, seed: int) -> np.ndarray:
    """Smooth value noise in [-1, 1] (cubic interpolation of a hashed lattice); deterministic, numpy only."""
    x = np.asarray(x, float) / scale
    y = np.asarray(y, float) / scale
    x0, y0 = np.floor(x), np.floor(y)
    fx, fy = x - x0, y - y0
    ux, uy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = _hash01(x0, y0, seed)
    b = _hash01(x0 + 1, y0, seed)
    c = _hash01(x0, y0 + 1, seed)
    d = _hash01(x0 + 1, y0 + 1, seed)
    return (a * (1 - ux) * (1 - uy) + b * ux * (1 - uy) + c * (1 - ux) * uy + d * ux * uy) * 2 - 1


def fbm(x, y, scale: float, seed: int, octaves: int = 4, gain: float = 0.5) -> np.ndarray:
    out = np.zeros(np.broadcast(np.asarray(x), np.asarray(y)).shape)
    amp, tot = 1.0, 0.0
    for o in range(octaves):
        out = out + amp * value_noise(x, y, scale / (2 ** o), seed + 101 * o)
        tot += amp
        amp *= gain
    return out / tot


def smoothstep(e0, e1, x):
    t = np.clip((np.asarray(x, float) - e0) / max(e1 - e0, 1e-12), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ mesh data (NPZ, UE numbers)
class Mesh:
    """Triangle mesh in UE numbers, local to `pivot` (board = local + pivot). F (T, 3) CCW outward; UV (T, 3, 2) per
    corner (Blender convention, v up); MAT (T,) slot index; SMOOTH (T,) bool (smooth shading group);
    slots = material slot names."""

    def __init__(self, name, V, F, UV, MAT=None, SMOOTH=None, slots=("M0",), pivot=(0.0, 0.0, 0.0)):
        self.name = name
        self.V = np.asarray(V, np.float64)
        self.F = np.asarray(F, np.int64).reshape(-1, 3)
        self.UV = np.asarray(UV, np.float64).reshape(-1, 3, 2)
        self.MAT = np.zeros(len(self.F), np.int64) if MAT is None else np.asarray(MAT, np.int64)
        self.SMOOTH = np.ones(len(self.F), bool) if SMOOTH is None else np.asarray(SMOOTH, bool)
        self.slots = list(slots)
        self.pivot = np.asarray(pivot, np.float64)

    @property
    def tris(self) -> int:
        return int(len(self.F))

    def board(self) -> np.ndarray:
        return self.V + self.pivot

    def save(self, path: Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, V=self.V, F=self.F, UV=self.UV, MAT=self.MAT, SMOOTH=self.SMOOTH,
                            slots=np.array(self.slots), pivot=self.pivot, name=np.array(self.name))

    @staticmethod
    def load(path: Path) -> "Mesh":
        d = np.load(path, allow_pickle=False)
        return Mesh(str(d["name"]), d["V"], d["F"], d["UV"], d["MAT"], d["SMOOTH"], [str(s) for s in d["slots"]],
                    d["pivot"])

    def face_normals(self) -> np.ndarray:
        P = self.V[self.F]
        n = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    def digest(self) -> str:
        h = hashlib.sha256()
        for a in (np.round(self.V, 4), self.F, np.round(self.UV, 6), self.MAT, self.SMOOTH):
            h.update(np.ascontiguousarray(a).tobytes())
        h.update(json.dumps([self.slots, np.round(self.pivot, 4).tolist()]).encode())
        return h.hexdigest()


def merge_meshes(name, parts, slots, pivot) -> Mesh:
    V, F, UV, MAT, SM = [], [], [], [], []
    base = 0
    for m in parts:
        V.append(m.V + m.pivot - np.asarray(pivot, float))
        F.append(m.F + base)
        UV.append(m.UV)
        MAT.append(np.array([slots.index(m.slots[i]) for i in m.MAT], np.int64))
        SM.append(m.SMOOTH)
        base += len(m.V)
    return Mesh(name, np.vstack(V), np.vstack(F), np.vstack(UV), np.concatenate(MAT), np.concatenate(SM), slots, pivot)


def uv_overlap_share(UV: np.ndarray, res: int = 1024, mask=None) -> tuple[float, int]:
    """Share of covered texels covered by more than one triangle (UV (T, 3, 2) in 0..1; texel centres inside the
    triangle, edges excluded by a 1e-9 margin) and the count of covered texels."""
    cnt = np.zeros((res, res), np.int32)
    tri = np.asarray(UV, float) * res
    if mask is not None:
        tri = tri[mask]
    for t in tri:
        x0, y0 = np.floor(t.min(0)).astype(int)
        x1, y1 = np.ceil(t.max(0)).astype(int)
        x0, y0 = max(x0, 0), max(y0, 0)
        x1, y1 = min(x1, res), min(y1, res)
        if x1 <= x0 or y1 <= y0:
            continue
        ys, xs = np.mgrid[y0:y1, x0:x1]
        px, py = xs + 0.5, ys + 0.5
        (ax, ay), (bx, by), (cx, cy) = t
        d = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(d) < 1e-12:
            continue
        l0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / d
        l1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / d
        l2 = 1 - l0 - l1
        m = (l0 > 1e-9) & (l1 > 1e-9) & (l2 > 1e-9)
        cnt[y0:y1, x0:x1] += m
    cov = int((cnt > 0).sum())
    return (float((cnt > 1).sum()) / max(cov, 1), cov)


def triangulate_polygon(poly: np.ndarray, step: float, extra: np.ndarray | None = None,
                        holes=(), boundary: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """2D triangulation of a simple polygon: boundary = the given vertices (kept first, in order, so callers can stitch
    to them) or the outline resampled at 0.7 step; interior grid at `step` (offset rows), optional extra points; scipy
    Delaunay, triangles whose centroid lies outside are dropped. Returns (P (n, 2), T (m, 3) CCW); with `boundary`
    the first len(boundary) points of P are the boundary vertices."""
    from scipy.spatial import Delaunay
    poly = ccw(poly)
    B = np.asarray(boundary, float) if boundary is not None else resample_closed(poly, step * 0.7)
    lo, hi = poly.min(0), poly.max(0)
    xs = np.arange(lo[0] + step / 2, hi[0], step)
    ys = np.arange(lo[1] + step / 2, hi[1], step * math.sqrt(3) / 2)
    G = np.array([(x + (step / 2 if j % 2 else 0.0), y) for j, y in enumerate(ys) for x in xs])
    G = G[inside(poly, G)]
    if len(G):
        G = G[seg_dist(G, poly) > step * 0.45]
    pts = [B, G]
    if extra is not None and len(extra):
        E = np.asarray(extra, float)
        E = E[inside(poly, E)]
        if len(E):
            E = E[seg_dist(E, poly) > step * 0.3]
        pts.append(E)
    P = np.vstack(pts)
    # unique (rounded) points keep Delaunay deterministic (first occurrence wins: the boundary stays first)
    _, idx = np.unique(np.round(P, 6), axis=0, return_index=True)
    P = P[np.sort(idx)]
    if boundary is not None and not np.allclose(P[:len(B)], B):
        raise ValueError("triangulate_polygon: duplicate boundary vertices")
    tri = Delaunay(P, qhull_options="Qbb Qc Qz Q12")
    T = tri.simplices.astype(np.int64)
    cen = P[T].mean(1)
    keep = inside(poly, cen)
    for h in holes:
        keep &= ~inside(h, cen)
    T = T[keep]
    # CCW
    a = P[T]
    cr = (a[:, 1, 0] - a[:, 0, 0]) * (a[:, 2, 1] - a[:, 0, 1]) - (a[:, 1, 1] - a[:, 0, 1]) * (a[:, 2, 0] - a[:, 0, 0])
    T[cr < 0] = T[cr < 0][:, ::-1]
    # drop slivers along the boundary
    a = P[T]
    cr = np.abs((a[:, 1, 0] - a[:, 0, 0]) * (a[:, 2, 1] - a[:, 0, 1]) - (a[:, 1, 1] - a[:, 0, 1]) * (a[:, 2, 0] - a[:, 0, 0]))
    T = T[cr > 1e-6]
    if boundary is not None:
        return P, T
    used = np.unique(T)
    remap = -np.ones(len(P), np.int64)
    remap[used] = np.arange(len(used))
    return P[used], remap[T]


# ------------------------------------------------------------------ rasteriser (C0 depth / ids, numpy)
def raster_tris(cam: C.Cam, P: np.ndarray, T: np.ndarray, w: int, h: int, ids=None, cull_back=False, rect=None):
    """Z-buffer of world triangles (P (n, 3), T (m, 3)) in a camera; the raster (w x h) covers the C0-px rectangle
    rect = (x0, y0, x1, y1) (default the camera frame). Returns (depth (h, w) view depth, inf = empty; id (h, w)
    triangle id or -1). Perspective-correct depth via 1/z interpolation."""
    q, z = cam.project(P)
    x0r, y0r, x1r, y1r = rect if rect is not None else (0.0, 0.0, float(cam.w), float(cam.h))
    q = (q - np.array([x0r, y0r])) * np.array([w / (x1r - x0r), h / (y1r - y0r)])
    return raster_screen(q, z, T, w, h, ids, cull_back)


def raster_screen(q: np.ndarray, z: np.ndarray, T: np.ndarray, w: int, h: int, ids=None, cull_back=False):
    """raster_tris on projected vertices (q raster px, z view depth)."""
    ids = np.arange(len(T)) if ids is None else np.asarray(ids)
    depth = np.full(h * w, np.inf)
    tid = np.full(h * w, -1, np.int64)
    qa, qb, qc = q[T[:, 0]], q[T[:, 1]], q[T[:, 2]]
    za, zb, zc = z[T[:, 0]], z[T[:, 1]], z[T[:, 2]]
    ok = (za > 1) & (zb > 1) & (zc > 1)
    area = (qb[:, 0] - qa[:, 0]) * (qc[:, 1] - qa[:, 1]) - (qb[:, 1] - qa[:, 1]) * (qc[:, 0] - qa[:, 0])
    if cull_back:
        ok &= area > 0  # faces CCW-outward in the UE numbers keep their orientation in C0 px (x right, y down)
    ok &= np.abs(area) > 1e-9
    x0 = np.floor(np.minimum(np.minimum(qa[:, 0], qb[:, 0]), qc[:, 0]) - 0.5).astype(np.int64)
    x1 = np.ceil(np.maximum(np.maximum(qa[:, 0], qb[:, 0]), qc[:, 0]) - 0.5).astype(np.int64)
    y0 = np.floor(np.minimum(np.minimum(qa[:, 1], qb[:, 1]), qc[:, 1]) - 0.5).astype(np.int64)
    y1 = np.ceil(np.maximum(np.maximum(qa[:, 1], qb[:, 1]), qc[:, 1]) - 0.5).astype(np.int64)
    ok &= (x1 >= 0) & (y1 >= 0) & (x0 < w) & (y0 < h)
    x0, y0 = np.clip(x0, 0, w - 1), np.clip(y0, 0, h - 1)
    x1, y1 = np.clip(x1, 0, w - 1), np.clip(y1, 0, h - 1)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    sel_all = np.nonzero(ok)[0]
    size = np.maximum(bw, bh)
    frags_p, frags_z, frags_i = [], [], []
    for lo, hi in ((0, 2), (2, 4), (4, 8), (8, 16), (16, 32), (32, 64), (64, 128), (128, 100000)):
        sel = sel_all[(size[sel_all] > lo) & (size[sel_all] <= hi)]
        if not len(sel):
            continue
        S = int(min(hi, size[sel].max()))
        n_per = max(1, int(3_000_000 / (S * S)))
        for g0 in range(0, len(sel), n_per):
            g = sel[g0:g0 + n_per]
            oy, ox = np.mgrid[0:S, 0:S]
            px = x0[g][:, None, None] + ox[None] + 0.5
            py = y0[g][:, None, None] + oy[None] + 0.5
            ax, ay = qa[g, 0][:, None, None], qa[g, 1][:, None, None]
            bx, by = qb[g, 0][:, None, None], qb[g, 1][:, None, None]
            cx, cy = qc[g, 0][:, None, None], qc[g, 1][:, None, None]
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            l0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
            l1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
            l2 = 1 - l0 - l1
            m = (l0 >= -1e-7) & (l1 >= -1e-7) & (l2 >= -1e-7)
            m &= (px - 0.5 <= x1[g][:, None, None]) & (py - 0.5 <= y1[g][:, None, None])
            ti, yy, xx = np.nonzero(m)
            if not len(ti):
                continue
            gi = g[ti]
            iz = l0[ti, yy, xx] / za[gi] + l1[ti, yy, xx] / zb[gi] + l2[ti, yy, xx] / zc[gi]
            frags_p.append((y0[gi] + yy) * w + (x0[gi] + xx))
            frags_z.append(1.0 / iz)
            frags_i.append(ids[gi])
    if frags_p:
        p = np.concatenate(frags_p)
        zz = np.concatenate(frags_z)
        ii = np.concatenate(frags_i)
        o = np.lexsort((zz, p))
        p, zz, ii = p[o], zz[o], ii[o]
        first = np.r_[True, p[1:] != p[:-1]]
        depth[p[first]] = zz[first]
        tid[p[first]] = ii[first]
    return depth.reshape(h, w), tid.reshape(h, w)


def poly_mask(poly_px, w, h, rect=None) -> np.ndarray:
    """C0-px polygon rasterised on a w x h raster covering the C0 rect (x0, y0, x1, y1) (default the C0 frame)."""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = rect if rect is not None else (0.0, 0.0, float(C.W), float(C.H))
    kx, ky = w / (x1 - x0), h / (y1 - y0)
    im = Image.new("L", (w, h), 0)
    ImageDraw.Draw(im).polygon([((x - x0) * kx, (y - y0) * ky) for x, y in poly_px], fill=255)
    return np.asarray(im) > 127


DELIT_EXT = {"file": "sarpedon-extended-delit.png", "size": [2340, 1317], "conceptRectPx": [334, 188, 1672, 941],
             "registrationTag": "extended"}


def plate_c0(rect=RECT_B, w=1344, h=756, plate=None) -> np.ndarray:
    """A plate (default the albedo plate; DELIT_EXT = the de-lit extended plate) resampled bilinearly on a w x h raster
    over a C0 rect through its registration - previews / overlays only (the bake uses the Lanczos path of cp_bake)."""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    plate = plate or ALBEDO_PLATE
    img = np.asarray(Image.open(PLATES / plate["file"]).convert("RGB")).astype(np.float32) / 255.0
    reg = load_json(CP_DIR / "registration.json")["maps"][MAP_KEY][plate["registrationTag"]]
    x0, y0, x1, y1 = rect
    xs = x0 + (np.arange(w) + 0.5) * (x1 - x0) / w
    ys = y0 + (np.arange(h) + 0.5) * (y1 - y0) / h
    FX, FY = np.meshgrid(xs, ys)
    px, py = pp.c0_to_plate(plate, np.asarray(reg["H"], float), FX, FY)
    return C.bilinear(img, px, py)


def overlay_meshes(meshes, out_png, rect=RECT_B, scale=0.5, alpha=0.5, colors=None, crop=None):
    """C0 silhouettes (back faces culled) of several meshes over the de-lit plate (self-check image, out of git).
    crop = optional C0 rect to cut the output to."""
    from PIL import Image
    cam = cam0()
    w, h = int((rect[2] - rect[0]) * scale), int((rect[3] - rect[1]) * scale)
    img = plate_c0(rect, w, h, DELIT_EXT)
    pal = colors or [(1.0, 0.8, 0.1), (0.1, 0.9, 1.0), (1.0, 0.2, 0.2), (0.3, 1.0, 0.3), (1.0, 0.3, 1.0), (1, 1, 1)]
    depth = np.full((h, w), np.inf)
    owner = np.full((h, w), -1)
    for i, m in enumerate(meshes):
        d, _ = raster_tris(cam, m.board(), m.F, w, h, rect=rect, cull_back=True)
        nearer = d < depth
        depth[nearer] = d[nearer]
        owner[nearer] = i
    o = img.copy()
    for i in range(len(meshes)):
        s = owner == i
        o[s] = o[s] * (1 - alpha) + np.array(pal[i % len(pal)]) * alpha
    im = Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8))
    if crop:
        k = w / (rect[2] - rect[0])
        im = im.crop(tuple(int(v) for v in ((crop[0] - rect[0]) * k, (crop[1] - rect[1]) * k,
                                            (crop[2] - rect[0]) * k, (crop[3] - rect[1]) * k)))
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    im.save(out_png, quality=88)
    return {i: int((owner == i).sum()) for i in range(len(meshes))}
