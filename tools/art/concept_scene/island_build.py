"""ENV-MAPS P8.1 island (ASSET-ENV-S-ISLAND-001): the real 3D island under the Sarpedon painting.

  python -B tools/art/concept_scene/island_build.py [--overlay]     # geometry -> <work>/SM_Env_S_Island.pre.npz

Pure Python (numpy / scipy), deterministic; the FBX export (k_blender.MeshBuilder, UM_FBX_v1) is cs_blender.py
'export' (run_scene.py drives the whole chain). Geometry (UE numbers = board space minus the pivot):

  * rim: the plateau outline from the params' outline entries, each a board point "xy", a C0 pixel "px" cast to its
    ray at "z" (the painted rim / canopy silhouette of sarpedon.paste.json geometry.islandMatte) or a C0 pixel
    "footPx" cast to the sea plane (the painted cliff foot of the near / west cliffs) and moved inwards by its run;
    the near rim follows the front-cliff top (Y ~345-352; P9: straight across, the P5c waterfall tongue is gone - the
    cascade of cascade_build.py runs down this cliff), the east rim follows the painted dock edge (the procedural
    hull side of ship_build.py stands a little further east over the sea gap); resampled every rimStepUU, smoothed,
    organic noise away from the frame;
  * top: a Delaunay surface on the rim (the rim vertices are its boundary) with a coarse lattice under the map, the
    normal lattice and a fine lattice in the ring around the frame (K2 close-ups); height = plateau -3, flat and
    exactly -3 inside the map field + frameFlatUU (no face above the map, the frame-002 foot stands on a solid plate:
    no gap), low noise bumps away from the frame, a forest mound (heightZones forest-canopy), the bay ramp down to
    -60 (heightZones bay-water) and a rounded rim;
  * cliffs: rings from the rim down to the sea plane - bottomExtraUU with three ledges (profile breakpoints; P9 F3:
    on the front rim under the frame band's near beam the first ring sits on the beam's face plane below its bottom
    edge - params nearLip - so no grazing lip strip shows in front of the frame, deeper in the cascade outlet),
    per-vertex run (horizontal reach of the cliff foot), jitter of the ledge heights, rock displacement along the
    outward normal and a ragged bottom ring; flat shading (faceted rock), the top is smooth;
  * UV0: one non-overlapping atlas (atlasPx): the top as a planar XY projection (north up), the cliff strips (u =
    rim arc length, v = profile arc length) cut into rows under it; the texel density is the largest that fits.

Outputs: <work>/SM_Env_S_Island.pre.npz (mesh), <work>/island_rim.npz (rim, heights - the layout reads them),
reports/island-build.json (git: triangles, densities, checks, C0 silhouette vs the island matte).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.spatial import Delaunay

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cs_common as CS  # noqa: E402

NAME = "SM_Env_S_Island"


# ------------------------------------------------------------------ outline
def control_outline(P: dict, sea_z: float):
    cen = np.asarray(P["inwardCentre"], float)
    pts, runs = [], []
    for e in P["outline"]:
        if "xy" in e:
            q = np.asarray(e["xy"], float)
        elif "px" in e:
            q = CS.ray_z(e["px"][0], e["px"][1], e["z"])[:2]
        elif "footPx" in e:
            f = CS.ray_z(e["footPx"][0], e["footPx"][1], sea_z)[:2]
            d = cen - f
            q = f + d / np.linalg.norm(d) * e["run"]
        else:
            raise ValueError(f"outline entry {e}")
        pts.append(q)
        runs.append(float(e.get("run", P["defaultRunUU"])))
    pts, runs = np.array(pts), np.array(runs)
    if CS.poly_area(pts) < 0:
        pts, runs = pts[::-1].copy(), runs[::-1].copy()
    return pts, runs


def resample_with(pts, vals, step):
    Q = np.vstack([pts, pts[:1]])
    vv = np.r_[vals, vals[:1]]
    seg = np.linalg.norm(np.diff(Q, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    n = max(16, int(round(s[-1] / step)))
    t = np.arange(n) * s[-1] / n
    return np.c_[np.interp(t, s, Q[:, 0]), np.interp(t, s, Q[:, 1])], np.interp(t, s, vv), s[-1]


def rect_dist(X, Y, hx, hy):
    """Signed distance to the axis-aligned rectangle |X| <= hx, |Y| <= hy (> 0 outside)."""
    dx = np.abs(X) - hx
    dy = np.abs(Y) - hy
    out = np.hypot(np.maximum(dx, 0), np.maximum(dy, 0))
    ins = np.minimum(np.maximum(dx, dy), 0)
    return out + ins


def rim(P: dict, sea_z: float):
    ctrl, cruns = control_outline(P, sea_z)
    R, runs, perim = resample_with(ctrl, cruns, P["rimStepUU"])
    R = CS.smooth_closed(R, P["rimSmoothIters"], 0.5)
    runs = ndimage.gaussian_filter1d(runs, P["runSmoothVerts"], mode="wrap")
    n = CS.vertex_normals_2d(R)
    # organic rim away from the frame (low-frequency push along the normal)
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([R, R[:1]]), axis=0), axis=1))][:-1]
    away = CS.smoothstep(P["rimNoiseFromFrameUU"][0], P["rimNoiseFromFrameUU"][1],
                         rect_dist(R[:, 0], R[:, 1], CS.C.FRAME_HX, CS.C.FRAME_HY))
    R = R + n * (P["rimNoiseUU"] * CS.fbm(arc, np.zeros_like(arc), P["rimNoiseScaleUU"], P["seed"], 3))[:, None] * away[:, None]
    return R, runs, perim, ctrl


# ------------------------------------------------------------------ height field of the top
class Height:
    def __init__(self, P: dict, R: np.ndarray):
        self.P = P
        self.R = R
        g = CS.spec()["geometry"]
        hz = {z["id"]: z for z in g["heightZones"]}
        self.forest = np.array([CS.ray_z(x, y, P["forest"]["rayZ"])[:2] for x, y in hz["forest-canopy"]["poly"]])
        self.bay = np.array([CS.ray_z(x, y, P["bay"]["rayZ"])[:2] for x, y in hz["bay-water"]["poly"]])

    def signed_in(self, poly, pts):
        d = CS.seg_dist(pts, poly)
        return np.where(CS.inside(poly, pts), d, -d)

    def __call__(self, pts: np.ndarray) -> np.ndarray:
        P = self.P
        X, Y = pts[:, 0], pts[:, 1]
        z0 = float(P["plateauZ"])
        dfr = rect_dist(X, Y, CS.MAP_FIELD[0], CS.MAP_FIELD[1])
        flat = CS.smoothstep(P["frameFlatUU"], P["frameFlatUU"] + P["bumpRampUU"], dfr)
        h = z0 + P["bumpUU"] * CS.fbm(X, Y, P["bumpScaleUU"], P["seed"] + 7, 4) * flat
        fm = CS.smoothstep(-P["forest"]["featherUU"], P["forest"]["featherUU"], self.signed_in(self.forest, pts))
        h = h + P["forest"]["moundUU"] * fm * flat
        bf = CS.smoothstep(0.0, P["bay"]["featherUU"], self.signed_in(self.bay, pts))
        h = h * (1 - bf) + P["bay"]["z"] * bf
        # rounded rim
        drim = CS.seg_dist(pts, self.R)
        h = h - P["rimRollUU"] * (1 - CS.smoothstep(0.0, P["rimRollWidthUU"], drim)) * flat
        # no face above the map field (+ the frame foot band): exactly the plateau there
        return np.where(dfr <= P["frameFlatUU"], z0, h)


# ------------------------------------------------------------------ build
def lattice(lo, hi, step, offset=0.0):
    xs = np.arange(lo[0] + offset, hi[0], step)
    ys = np.arange(lo[1] + offset, hi[1], step * math.sqrt(3) / 2)
    return np.array([(x + (step / 2 if j % 2 else 0.0), y) for j, y in enumerate(ys) for x in xs])


def top_surface(P, R, hf):
    lo, hi = R.min(0) - 1, R.max(0) + 1
    hx, hy = CS.MAP_FIELD
    dpts = []
    coarse = lattice(lo, hi, P["topStepUnderMapUU"])
    coarse = coarse[(np.abs(coarse[:, 0]) < hx - P["underMapInsetUU"]) & (np.abs(coarse[:, 1]) < hy - P["underMapInsetUU"])]
    dpts.append(coarse)
    normal = lattice(lo, hi, P["topStepUU"], 3.0)
    dn = rect_dist(normal[:, 0], normal[:, 1], hx, hy)
    normal = normal[(dn > P["fineBandUU"][1]) | (dn < -P["underMapInsetUU"] - P["topStepUU"])]
    normal = normal[~((np.abs(normal[:, 0]) < hx - P["underMapInsetUU"]) & (np.abs(normal[:, 1]) < hy - P["underMapInsetUU"]))]
    dpts.append(normal)
    fine = lattice(lo, hi, P["topStepFineUU"], 1.5)
    df = rect_dist(fine[:, 0], fine[:, 1], hx, hy)
    fine = fine[(df <= P["fineBandUU"][1]) & (df >= P["fineBandUU"][0])]
    dpts.append(fine)
    I = np.vstack(dpts)
    I = I[CS.inside(R, I)]
    I = I[CS.seg_dist(I, R) > P["rimStepUU"] * 0.6]
    pts = np.vstack([R, I])
    tri = Delaunay(pts, qhull_options="Qbb Qc Qz Q12")
    T = tri.simplices.astype(np.int64)
    cen = pts[T].mean(1)
    T = T[CS.inside(R, cen)]
    a = pts[T]
    cr = (a[:, 1, 0] - a[:, 0, 0]) * (a[:, 2, 1] - a[:, 0, 1]) - (a[:, 1, 1] - a[:, 0, 1]) * (a[:, 2, 0] - a[:, 0, 0])
    T[cr < 0] = T[cr < 0][:, ::-1]
    a = pts[T]
    cr = np.abs((a[:, 1, 0] - a[:, 0, 0]) * (a[:, 2, 1] - a[:, 0, 1]) - (a[:, 1, 1] - a[:, 0, 1]) * (a[:, 2, 0] - a[:, 0, 0]))
    T = T[cr > 1e-6]
    Z = hf(pts)
    return np.c_[pts, Z], T


def near_lip_weights(P, R, nrm):
    """P9 (F3 / F4): per rim vertex, the weight of the near-lip override (1 on the front rim under the frame band's
    near beam, ramped off past its ends) and the cascade outlet window (1 inside the cascade X range)."""
    L = P.get("nearLip")
    n = len(R)
    if not L:
        return np.zeros(n), np.zeros(n)
    X, Y = R[:, 0], R[:, 1]
    w = (1.0 - CS.smoothstep(L["xHalfUU"], L["xHalfUU"] + L["rampUU"], np.abs(X)))
    w = w * (nrm[:, 1] > L["minNormalY"]) * (Y > CS.C.FRAME_HY)
    x0, x1 = L["outletXUU"]
    r = L["outletRampUU"]
    win = CS.smoothstep(x0 - r, x0, X) * (1.0 - CS.smoothstep(x1, x1 + r, X))
    return w, win


def cliffs(P, R, runs, z_rim, sea_z):
    n = len(R)
    nrm = CS.vertex_normals_2d(R)
    # smoother normals for the cliff (fewer crossings at concave corners)
    nrm = ndimage.uniform_filter1d(nrm, P["cliffNormalSmoothVerts"], axis=0, mode="wrap")
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(np.vstack([R, R[:1]]), axis=0), axis=1))]
    s_br = np.array([b[0] for b in P["profile"]], float)
    t_br = np.array([b[1] for b in P["profile"]], float)
    K = len(s_br)
    seed = P["seed"]
    bottom = sea_z - P["bottomExtraUU"]
    rings = np.zeros((K, n, 3))
    drop = z_rim - bottom
    # profile (run fraction s, drop fraction t) per ring and rim vertex
    S = np.zeros((K, n))
    T = np.zeros((K, n))
    for k in range(K):
        s = np.full(n, s_br[k])
        t = np.full(n, t_br[k])
        if 0 < k < K - 1:
            s = s + P["ledgeJitterS"] * CS.fbm(arc[:-1], np.full(n, 11.0 * k), P["ledgeNoiseScaleUU"], seed + 31 * k, 3)
            t = t + P["ledgeJitterT"] * CS.fbm(arc[:-1], np.full(n, 7.0 * k), P["ledgeNoiseScaleUU"], seed + 53 * k, 3)
        S[k], T[k] = s, t
    # P9 F3 / F4: under the frame band's near beam the lip drops steeply (the cliff top tucks under the beam's front
    # face: no grazing lip strip in front of the frame), deeper in the cascade outlet (the water leaves from under
    # the beam); later rings stay monotonic
    L = P.get("nearLip")
    w = np.zeros(n)
    if L:
        w, win = near_lip_weights(P, R, nrm)
        lip_drop = L["dropUU"] + (L["outletDropUU"] - L["dropUU"]) * win
        # ring 1 lands on the plane Y = faceYUU (just in front of the beam's front face, below its bottom edge)
        out = np.clip((L["faceYUU"] - R[:, 1]) / np.maximum(nrm[:, 1], 0.6), L["minOutUU"], None)
        S[1] = S[1] * (1 - w) + (out / np.maximum(runs, 1.0)) * w
        T[1] = T[1] * (1 - w) + (lip_drop / np.maximum(drop, 1.0)) * w
        for k in range(2, K):
            S[k] = np.maximum(S[k], S[k - 1] + 0.01 * w)
            T[k] = np.maximum(T[k], T[k - 1] + 0.01 * w)
    for k in range(K):
        s, t = S[k], T[k]
        z = z_rim - drop * np.clip(t, 0, 1)
        if k == K - 1:
            z = bottom + P["raggedBottomUU"] * CS.fbm(arc[:-1], np.zeros(n), 70.0, seed + 99, 3)
        disp = np.zeros(n)
        if k > 0:
            disp = P["rockDispUU"] * CS.fbm(arc[:-1], z, P["rockScaleUU"], seed + 17, 4)
            if k == 1:
                disp = disp * (1 - w)  # the tucked lip stays on the face plane (no rock pushed out over the beam)
        xy = R + nrm * (runs * np.clip(s, 0, 1.2) + disp)[:, None]
        rings[k] = np.c_[xy, z]
    rings[0, :, 2] = z_rim
    rings[0, :, :2] = R
    return rings, arc


def profile_len(rings):
    d = np.linalg.norm(np.diff(rings, axis=0), axis=2)  # (K-1, n)
    return np.vstack([np.zeros((1, rings.shape[1])), np.cumsum(d, axis=0)])


def atlas(P, top_xy, rings, arc):
    """Texel density rho (texels per uu) of the top and rho * cliffDensityRatio of the cliffs, the largest that fits."""
    A = P["atlasPx"]
    pad = P["atlasPadPx"]
    lo, hi = top_xy.min(0), top_xy.max(0)
    W, H = hi - lo
    L = arc[-1]
    plen = profile_len(rings).max()
    ratio = P["cliffDensityRatio"]
    rho = (A - 2 * pad) / max(W, H)
    while rho > 0.1:
        tw, th = W * rho, H * rho
        rc = rho * ratio
        row_h = plen * rc
        per_row = A - 2 * pad
        rows = int(math.ceil(L * rc / per_row))
        need = th + pad + rows * (row_h + pad) + pad
        if tw <= A - 2 * pad and need <= A:
            return rho, rc, rows, row_h, lo
        rho *= 0.99
    raise RuntimeError("atlas: nothing fits")


def build(P: dict, sea_z: float):
    R, runs, perim, ctrl = rim(P, sea_z)
    hf = Height(P, R)
    top, T = top_surface(P, R, hf)
    z_rim = top[:len(R), 2].copy()
    rings, arc = cliffs(P, R, runs, z_rim, sea_z)
    rho, rc, rows, row_h, lo = atlas(P, top[:, :2], rings, arc)
    A = float(P["atlasPx"])
    pad = P["atlasPadPx"]
    # ---- top UVs (Blender v up: image row r -> v = 1 - r / A)
    col = pad + (top[:, 0] - lo[0]) * rho
    row = pad + (top[:, 1] - lo[1]) * rho
    uv_top = np.c_[col / A, 1 - row / A]
    top_h = pad + (top[:, 1].max() - lo[1]) * rho
    V = [top]
    F = [T]
    UV = [uv_top[T]]
    SMOOTH = [np.ones(len(T), bool)]
    # ---- cliff strips in rows (chunks of the ring, columns duplicated at the cuts)
    K, n = rings.shape[:2]
    plen = profile_len(rings)
    per_row = (A - 2 * pad) / rc  # uu of rim per row
    base = len(top)
    cuts = [0]
    while cuts[-1] < n:
        a0 = arc[cuts[-1]]
        j = cuts[-1]
        while j < n and arc[j + 1] - a0 <= per_row:
            j += 1
        cuts.append(max(j, cuts[-1] + 1))
    chunks = list(zip(cuts[:-1], cuts[1:]))
    if len(chunks) > rows:
        raise RuntimeError(f"atlas: {len(chunks)} cliff rows > {rows}")
    for r_i, (c0, c1) in enumerate(chunks):
        cols = list(range(c0, c1 + 1))  # c1 may equal n -> wraps to vertex 0
        idx = [c % n for c in cols]
        Vc = rings[:, idx, :].reshape(-1, 3)
        u = (pad + (arc[cols] - arc[c0]) * rc) / A
        v_rows = top_h + pad + r_i * (row_h + pad) + plen[:, idx] * rc
        uv = np.stack([np.broadcast_to(u, (K, len(cols))), 1 - v_rows / A], -1).reshape(-1, 2)
        m = len(cols)
        Fc = []
        for k in range(K - 1):
            for j in range(m - 1):
                a, b = k * m + j, k * m + j + 1
                c, d = (k + 1) * m + j + 1, (k + 1) * m + j
                Fc += [[a, d, c], [a, c, b]]
        Fc = np.array(Fc, np.int64)
        # orientation: outward = away from the island (rim normal); fix by the first face normal
        Pc = Vc[Fc]
        nn = np.cross(Pc[:, 1] - Pc[:, 0], Pc[:, 2] - Pc[:, 0])
        cen = Pc.mean(1)
        out_dir = cen[:, :2] - R[np.array(idx)[np.clip((Fc[:, 0] % m), 0, m - 1)]]
        if np.median(np.einsum("ij,ij->i", nn[:, :2], out_dir)) < 0:
            Fc = Fc[:, ::-1]
        V.append(Vc)
        F.append(Fc + base)
        UV.append(uv[Fc])
        SMOOTH.append(np.zeros(len(Fc), bool))
        base += len(Vc)
    Vall = np.vstack(V)
    Fall = np.vstack(F)
    UVall = np.vstack(UV)
    SMall = np.concatenate(SMOOTH)
    pivot = np.array(P["pivot"], float)
    mesh = CS.Mesh(NAME, Vall - pivot, Fall, UVall, np.zeros(len(Fall), int), SMall, ["MI_Env_S_Island"], pivot)
    info = {"rimVerts": int(n), "perimeterUU": round(float(arc[-1]), 1), "topTris": int(len(T)),
            "cliffTris": int(len(Fall) - len(T)), "triangles": int(len(Fall)),
            "texelsPerUU": {"top": round(rho, 4), "cliffs": round(rc, 4)}, "cliffRows": len(chunks),
            "atlasPx": P["atlasPx"],
            "topBoundsBoard": {"min": [round(float(v), 1) for v in top.min(0)], "max": [round(float(v), 1) for v in top.max(0)]},
            "zRange": [round(float(Vall[:, 2].min()), 1), round(float(Vall[:, 2].max()), 1)]}
    return mesh, {"R": R, "runs": runs, "zRim": z_rim, "ctrl": ctrl, "rings": rings}, info, hf


# ------------------------------------------------------------------ checks
def checks(mesh: CS.Mesh, P: dict) -> dict:
    B = mesh.board()
    hx, hy = CS.MAP_FIELD
    inside = (np.abs(B[:, 0]) <= hx) & (np.abs(B[:, 1]) <= hy)
    above = int((B[inside, 2] > P["plateauZ"] + 1e-6).sum())
    # every triangle touching the map field lies at the plateau or below
    tri_in = inside[mesh.F].any(1)
    ov, cov = CS.uv_overlap_share(mesh.UV, 1024)
    uv_in = bool((mesh.UV >= 0).all() and (mesh.UV <= 1).all())
    # under-frame plate: the frame foot ring is covered by the top (sampled)
    ang = np.linspace(0, 2 * math.pi, 400, endpoint=False)
    ring = []
    for d in (-6.0, 0.0, 6.0):
        hxx, hyy = CS.C.FRAME_HX + d, CS.C.FRAME_HY + d
        t = np.linspace(-1, 1, 100)
        ring += [np.c_[t * hxx, np.full(100, -hyy)], np.c_[t * hxx, np.full(100, hyy)],
                 np.c_[np.full(100, -hxx), t * hyy], np.c_[np.full(100, hxx), t * hyy]]
    ring = np.vstack(ring)
    R2 = B[:, :2]
    topF = mesh.F[mesh.SMOOTH]
    covered = np.zeros(len(ring), bool)
    a, b, c = R2[topF[:, 0]], R2[topF[:, 1]], R2[topF[:, 2]]
    for i in range(0, len(ring), 200):
        p = ring[i:i + 200][:, None, :]
        d = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
        l0 = ((b[:, 1] - c[:, 1]) * (p[..., 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (p[..., 1] - c[:, 1])) / d
        l1 = ((c[:, 1] - a[:, 1]) * (p[..., 0] - c[:, 0]) + (a[:, 0] - c[:, 0]) * (p[..., 1] - c[:, 1])) / d
        covered[i:i + 200] = ((l0 >= -1e-6) & (l1 >= -1e-6) & (1 - l0 - l1 >= -1e-6)).any(1)
    return {"verticesAboveMapField": above, "trianglesTouchingMapField": int(tri_in.sum()),
            "uvOverlapShare": round(ov, 6), "uvCoveredTexels1k": cov, "uvInside01": uv_in,
            "frameFootRingCovered": round(float(covered.mean()), 4),
            "maxTriangles": P["maxTris"], "trianglesOk": mesh.tris <= P["maxTris"]}


def silhouette(mesh: CS.Mesh, ship: CS.Mesh | None, out_png: Path | None, scale=0.5) -> dict:
    """C0 silhouette of island (+ ship) vs the island matte of sarpedon.paste.json (over the extended canvas)."""
    from PIL import Image, ImageDraw
    cam = CS.cam0()
    rect = CS.RECT_B
    w, h = int((rect[2] - rect[0]) * scale), int((rect[3] - rect[1]) * scale)
    Pm, Fm = mesh.board(), mesh.F
    d_isl, _ = CS.raster_tris(cam, Pm, Fm, w, h, rect=rect, cull_back=True)
    isl = np.isfinite(d_isl)
    ship_m = np.zeros_like(isl)
    if ship is not None:
        d_sh, _ = CS.raster_tris(cam, ship.board(), ship.F, w, h, rect=rect, cull_back=True)
        ship_m = np.isfinite(d_sh)
    matte = CS.poly_mask(CS.spec()["geometry"]["islandMatte"]["poly"], w, h, rect)
    both = isl | ship_m
    res = {"iouIslandShipVsMatte": round(float((both & matte).sum() / max((both | matte).sum(), 1)), 4),
           "matteCovered": round(float((both & matte).sum() / max(matte.sum(), 1)), 4),
           "outsideMatteShareOfMatte": round(float((isl & ~matte & ~ship_m).sum() / max(matte.sum(), 1)), 4)}
    if out_png:
        img = CS.plate_c0(rect, w, h, CS.DELIT_EXT)
        o = img.copy()
        o[isl] = o[isl] * 0.55 + np.array([1.0, 0.8, 0.1]) * 0.45
        o[ship_m & ~isl] = o[ship_m & ~isl] * 0.55 + np.array([0.1, 0.9, 1.0]) * 0.45
        im = Image.fromarray(np.clip(o * 255, 0, 255).astype(np.uint8))
        dr = ImageDraw.Draw(im)
        k = w / (rect[2] - rect[0])
        mp = [((x - rect[0]) * k, (y - rect[1]) * k) for x, y in CS.spec()["geometry"]["islandMatte"]["poly"]]
        dr.line(mp + mp[:1], fill=(255, 0, 255), width=2)
        fr = [((x - rect[0]) * k, (y - rect[1]) * k) for x, y in ((0, 0), (1920, 0), (1920, 1080), (0, 1080), (0, 0))]
        dr.line(fr, fill=(255, 255, 255), width=1)
        Path(out_png).parent.mkdir(parents=True, exist_ok=True)
        im.save(out_png)
    return res


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--overlay", action="store_true", help="also write the C0 silhouette overlay (out of git)")
    a = ap.parse_args(argv)
    allp = CS.params()
    P = allp["island"]
    sea_z = float(allp["seaZ"])
    mesh, rimd, info, _ = build(P, sea_z)
    work = CS.WORK
    mesh.save(work / f"{NAME}.pre.npz")
    np.savez_compressed(work / "island_rim.npz", **{k: np.asarray(v) for k, v in rimd.items()})
    chk = checks(mesh, P)
    rep = {"schema": "unmatched.env-s-island.build/1",
           "status": "предложено (geometry, CREATE stage; measured on the de-lit plate at C0)",
           "mesh": NAME, "pivotBoard": [round(float(v), 3) for v in mesh.pivot], "info": info, "checks": chk,
           "meshDigest": mesh.digest()}
    if a.overlay:
        ship_p = work / "SM_Env_S_Ship.pre.npz"
        ship = CS.Mesh.load(ship_p) if ship_p.is_file() else None
        rep["silhouetteC0"] = silhouette(mesh, ship, work / "overlays" / "island-silhouette-c0.png")
        rep["silhouetteOverlay"] = (work / "overlays" / "island-silhouette-c0.png").as_posix()
    CS.dump_json(CS.RUNS["island"] / "reports" / "island-build.json", rep)
    print("ISLAND", json.dumps(info), json.dumps(chk), json.dumps(rep.get("silhouetteC0")))
    bad = chk["verticesAboveMapField"] or not chk["trianglesOk"] or chk["uvOverlapShare"] > 1e-4 or not chk["uvInside01"]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
