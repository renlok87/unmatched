"""ENV-MAPS P7 concept paste: prototype of the camera-projected concept surround (offline, numpy).

  python paste_proto.py <map> build    -> paste plate (RGBA: frame band mirror-filled, alpha = island matte minus the
                                          area under the 3D frame), sea plate, depth sheet (vertex grid of world
                                          points), all OUT of git under C:/tmp/envmaps-research/p7/proto/<map>/
  python paste_proto.py <map> render [--proxy relief|terrain|plane] [--views ...]
                                       -> mock frames of the composited scene (real map + frame + heroes + detail
                                          stand-ins over the projected surround) and metrics.json

Technique (design.json): the registered clean plate is projected from the concept camera C0 onto a 'depth sheet' = a
grid mesh whose vertices lie on C0 rays at the depth of simple proxies (ground Z -3, raised forest canopy, low bay,
60-degree front cliff, vertical flats for the fort / posts / ship); everything outside the island matte is the sea
layer (sea plane + sky cylinder) projected the same way. The map field and frame-002 stay real.
"""
from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

import cp_common as C
import k1_mock

Image.MAX_IMAGE_PIXELS = None
HERE = Path(__file__).resolve().parent
OUT = Path("C:/tmp/envmaps-research/p7/proto")
EXT = (-384.0, -216.0, 2304.0, 1296.0)  # C0 px range of the extended canvas (rounded outwards)


# ------------------------------------------------------------------ spec / registration
def load_spec(map_key: str) -> dict:
    return json.loads((HERE / f"{map_key}.paste.json").read_text(encoding="utf-8"))


def load_h(map_key: str, out: Path) -> np.ndarray:
    rep = json.loads((out / map_key / "registration.json").read_text(encoding="utf-8"))
    return np.asarray(rep["homography_base_to_concept"], float)


def apply_h(Hm, x, y):
    w = Hm[2, 0] * x + Hm[2, 1] * y + Hm[2, 2]
    return (Hm[0, 0] * x + Hm[0, 1] * y + Hm[0, 2]) / w, (Hm[1, 0] * x + Hm[1, 1] * y + Hm[1, 2]) / w


# ------------------------------------------------------------------ geometry helpers
def poly_mask_grid(poly, xs: np.ndarray, ys: np.ndarray, supersample: int = 1) -> np.ndarray:
    """Polygon (C0 px) rasterised on the grid of sample positions xs (cols) x ys (rows) (uniform steps)."""
    sx, sy = xs[1] - xs[0], ys[1] - ys[0]
    w, h = len(xs), len(ys)
    im = Image.new("L", (w * supersample, h * supersample), 0)
    pts = [((x - xs[0]) / sx * supersample + supersample / 2 - 0.5, (y - ys[0]) / sy * supersample
            + supersample / 2 - 0.5) for x, y in poly]
    ImageDraw.Draw(im).polygon(pts, fill=255)
    a = np.asarray(im).astype(np.float32) / 255.0
    if supersample > 1:
        a = a.reshape(h, supersample, w, supersample).mean(axis=(1, 3))
    return a


def ray_plane(cam: C.Cam, fx, fy, P0, n):
    d = cam.rays(fx, fy)
    den = d @ n
    t = ((np.asarray(P0, float) - cam.pos) @ n) / np.where(np.abs(den) < 1e-9, 1e-9, den)
    return cam.pos + t[..., None] * d, t


def ray_z(cam: C.Cam, fx, fy, z):
    d = cam.rays(fx, fy)
    t = (np.asarray(z, float) - cam.pos[2]) / d[..., 2]
    return cam.pos + t[..., None] * d, t


def zone_plane(cam: C.Cam, zone: dict, ground_z: float):
    """(P0, n) of a plane zone."""
    if zone["type"] == "vplane":
        (ax, ay), (bx, by) = zone["basePx"]
        A = ray_z(cam, np.array(float(ax)), np.array(float(ay)), ground_z)[0]
        B = ray_z(cam, np.array(float(bx)), np.array(float(by)), ground_z)[0]
        n = np.cross(B - A, [0.0, 0.0, 1.0])
        n /= np.linalg.norm(n)
        if n @ (cam.pos - A) < 0:
            n = -n
        return A, n
    if zone["type"] == "slope":
        l0, l1 = zone["line0"], zone["line1"]
        P0 = np.array([0.0, l0["Y"], l0["z"]])
        n = np.array([0.0, l1["z"] - l0["z"], -(l1["Y"] - l0["Y"])])
        n /= np.linalg.norm(n)
        if n @ (cam.pos - P0) < 0:
            n = -n
        return P0, n
    raise ValueError(zone["type"])


def sheet_points(spec: dict, cam: C.Cam, xs: np.ndarray, ys: np.ndarray, proxy: str = "relief") -> np.ndarray:
    """World points (len(ys), len(xs), 3) of the depth sheet at C0 px sample positions.
    proxy: 'plane' = everything on the ground plane; 'terrain' = ground + height zones + the front cliff;
    'relief' = terrain + every vertical flat (the recommended design)."""
    g = spec["geometry"]
    gz = g["groundZ"]
    FX, FY = np.meshgrid(xs, ys)
    step = xs[1] - xs[0]
    hz = np.full(FX.shape, gz, np.float64)
    if proxy != "plane":
        for z in g["heightZones"]:
            m = poly_mask_grid(z["poly"], xs, ys, 2)
            m = ndimage.gaussian_filter(m, max(z.get("smoothPx", 0) / step, 1e-3))
            hz = hz + (z["z"] - gz) * m
    P, _ = ray_z(cam, FX, FY, hz)
    if proxy != "plane":
        for z in g["planeZones"]:
            if proxy == "terrain" and z["type"] != "slope":
                continue
            m = poly_mask_grid(z["poly"], xs, ys, 1) > 0.5
            P0, n = zone_plane(cam, z, gz)
            Q, t = ray_plane(cam, FX[m], FY[m], P0, n)
            ok = t > 0
            Pm = P[m]
            Pm[ok] = Q[ok]
            P[m] = Pm
    # nothing of the island goes below the sea level: the sheet continues on the sea plane there
    low = P[..., 2] < g["seaZ"]
    if low.any():
        P[low] = ray_z(cam, FX[low], FY[low], g["seaZ"])[0]
    return P


def ground_xy(cam: C.Cam, fx, fy, z=-3.0):
    P, _ = ray_z(cam, fx, fy, z)
    return P[..., 0], P[..., 1]


# ------------------------------------------------------------------ build: paste plate + sea plate
def plate_grid(spec_plate: dict):
    """Per plate pixel C0-px coordinates (concept framing rect -> 1920 x 1080)."""
    w, h = spec_plate["size"]
    x0, y0, rw, rh = spec_plate["conceptRectPx"]
    fx = (np.arange(w) + 0.5 - x0) / rw * C.W
    fy = (np.arange(h) + 0.5 - y0) / rh * C.H
    return fx, fy


def c0_to_plate(spec_plate: dict, Hm, fx, fy):
    """True C0 px -> plate pixel coordinates (registration homography C0 -> concept px, then the plate rect)."""
    cx, cy = apply_h(Hm, fx, fy)
    x0, y0, rw, rh = spec_plate["conceptRectPx"]
    return x0 + cx / C.W * rw, y0 + cy / C.H * rh


def frame_band(spec: dict, X, Y):
    """(under_frame, band, sample X, sample Y) for ground points.
    under = inside the 3D frame's outer foot minus underFrameUU (alpha 0: the frame covers the seam);
    band = outside that but inside the painted frame's outer edge (per side, wider in the corners): the painted frame
    of the concept is ~2x wider than frame-002, so the ground ring [frame foot .. painted edge + L] is resampled from
    [painted edge .. painted edge + L] (a 1D rubber stretch per side, faded out past the corners), i.e. the ground just
    outside the painted frame is pulled in to meet frame-002. A mirror fill was tried first: it makes kaleidoscope
    patterns on the near cliff / waterfall."""
    cut = spec["cut"]
    u = cut["underFrameUU"]
    under = (np.abs(X) < C.FRAME_HX - u) & (np.abs(Y) < C.FRAME_HY - u)
    pw = cut["paintedFrameOuterUU"]
    pad = cut.get("edgePadUU", 4.0)
    ring = cut.get("stretchRingUU", {"far": 80.0, "east": 80.0, "west": 80.0, "near": 120.0})
    e_f = C.FRAME_UU - u
    corner_x = np.abs(Y) > C.MAP_HY
    corner_y = np.abs(X) > C.MAP_HX
    sx, sy = X.copy(), Y.copy()
    band = np.zeros(X.shape, bool)
    for side, axis, sign, half, lat, lat_half in (("west", 0, -1, C.MAP_HX, Y, C.MAP_HY), ("east", 0, 1, C.MAP_HX, Y, C.MAP_HY),
                                                 ("far", 1, -1, C.MAP_HY, X, C.MAP_HX), ("near", 1, 1, C.MAP_HY, X, C.MAP_HX)):
        coord = X if axis == 0 else Y
        e = sign * coord - half                       # outward distance from the map edge on this side
        e_o = pw[side] + pad
        e_o = np.where(corner_x if axis == 0 else corner_y, np.maximum(e_o, cut["paintedCornerUU"] + pad), e_o)
        L = ring[side]
        sel = (e >= e_f) & (e <= e_o + L)
        e2 = np.where(sel, e_o + (e - e_f) * L / (e_o + L - e_f), e)
        # lateral fade: full shift along the side, fading to 0 over L past the frame corner
        over = np.abs(lat) - (lat_half + C.FRAME_UU)
        wlat = np.clip(1 - over / L, 0, 1)
        de = (e2 - e) * wlat
        if axis == 0:
            sx = sx + sign * de
        else:
            sy = sy + sign * de
        band |= sel & (e < e_o) & (wlat > 0.5)
    band &= ~under
    return under, band, sx, sy


def build(map_key: str, out: Path) -> dict:
    t0 = time.time()
    spec = load_spec(map_key)
    od = out / map_key
    Hm = load_h(map_key, out)
    Hinv = np.linalg.inv(Hm)
    cam = C.concept_cam()
    sp = spec["plates"]["colour"]
    pdir = Path(spec["plates"]["dir"])
    plate = np.asarray(Image.open(pdir / sp["file"]).convert("RGB")).astype(np.float32) / 255.0
    ph, pw_ = plate.shape[:2]
    fx1, fy1 = plate_grid(sp)
    # concept px of each plate pixel -> true C0 px via H^-1
    CX, CY = np.meshgrid(fx1, fy1)
    TX, TY = apply_h(Hinv, CX, CY)
    del CX, CY
    X, Y = ground_xy(cam, TX, TY, spec["geometry"]["groundZ"])
    under, band, MX, MY = frame_band(spec, X, Y)
    # rubber fill of the painted-frame band: every ground pixel whose sample point moved is resampled
    moved = ((np.abs(MX - X) > 1e-3) | (np.abs(MY - Y) > 1e-3)) & ~under
    bi = np.nonzero(moved)
    mfx, mfy = cam.project(np.stack([MX[bi], MY[bi], np.full(len(bi[0]), spec["geometry"]["groundZ"])], -1))[0].T
    px_, py_ = c0_to_plate(sp, Hm, mfx, mfy)
    filled = plate.copy()
    filled[bi] = C.bilinear(plate, px_, py_)
    # island matte (+ feather) and the cut under the frame
    xs = fx1  # plate grid in C0 px (uniform)
    island = poly_mask_grid(spec["geometry"]["islandMatte"]["poly"], fx1, fy1, 1)
    fpx = spec["geometry"]["islandMatte"]["featherPx"] * (len(fx1) / (fx1[-1] - fx1[0]))
    island = ndimage.gaussian_filter(island, fpx / 2)
    alpha = island * (~under)
    rgba = np.dstack([filled, alpha]).astype(np.float32)
    Image.fromarray(np.round(rgba * 255).astype(np.uint8), "RGBA").save(od / "paste-plate-rgba.png")
    # UE-ready resample (Lanczos, POT): centre plate 4096 x 2048 and the band check crop
    Image.fromarray(np.round(rgba * 255).astype(np.uint8), "RGBA").resize((4096, 2048), Image.LANCZOS).save(
        od / "paste-plate-rgba-4096x2048.png")
    # sea plate: the extended plate where it is sea; inside the island the sea-sky plate matched to it
    ss = spec["plates"].get("seaSky")
    seam = island < 0.5
    mu_r = sd_r = mu_s = sd_s = np.zeros(3)
    if not ss:  # no sea / sky plate (Marmoreal flag variant): the background is the colour plate itself
        sea_tex = plate
    else:
        sea_src = np.asarray(Image.open(pdir / ss["file"]).convert("RGB").resize((C.W, C.H), Image.LANCZOS)).astype(
            np.float32) / 255.0
        ref = plate[seam & (TY > 0) & (TY < C.H) & (TX > 0) & (TX < C.W)]
        # match mean / std per channel (sRGB; enough for the stand-in, the UE stage grades it with the same numbers)
        mu_r, sd_r = ref.mean(0), ref.std(0)
        mu_s, sd_s = sea_src.reshape(-1, 3).mean(0), sea_src.reshape(-1, 3).std(0)
        sea_m = np.clip((sea_src - mu_s) / sd_s * sd_r + mu_r, 0, 1)
        sea_in = C.bilinear(sea_m, TX, TY, fill=np.nan)
        sea_tex = np.where(seam[..., None], plate, sea_in)
        # outside the C0 frame inside the island: nearest fill + blur from the sea pixels
        holes = np.isnan(sea_tex[..., 0])
        if holes.any():
            idx = ndimage.distance_transform_edt(holes, return_distances=False, return_indices=True)
            sea_tex = sea_tex[idx[0], idx[1]]
            sea_tex = np.where(holes[..., None], ndimage.gaussian_filter(sea_tex, (6, 6, 0)), sea_tex)
    C.save_rgb(od / "sea-plate.png", sea_tex)
    # depth sheet (relief) vertex grid for the UE mesh: world XYZ + UV (plate px / size)
    step = spec["geometry"]["vertexStepPx"]
    gx = np.arange(EXT[0], EXT[2] + step, step)
    gy = np.arange(EXT[1], EXT[3] + step, step)
    sheets = {}
    for proxy in ("relief", "terrain", "plane"):
        P = sheet_points(spec, cam, gx, gy, proxy)
        np.save(od / f"sheet-{proxy}.npy", P.astype(np.float32))
        sheets[proxy] = {"verts": [int(len(gy)), int(len(gx))], "zRange": [round(float(P[..., 2].min()), 1),
                                                                            round(float(P[..., 2].max()), 1)]}
    info = {"plate": sp["file"], "plateSha256": C.sha256(pdir / sp["file"]), "plateSize": [pw_, ph],
            "bandPixels": int(band.sum()), "resampledPixels": int(moved.sum()), "underFramePixels": int(under.sum()),
            "seaMatch": {"refMean": mu_r.round(4).tolist(), "refStd": sd_r.round(4).tolist(),
                         "seaSkyMean": mu_s.round(4).tolist(), "seaSkyStd": sd_s.round(4).tolist()},
            "sheetGrid": {"stepPx": step, "x": [float(gx[0]), float(gx[-1])], "y": [float(gy[0]), float(gy[-1])]},
            "sheets": sheets, "seconds": round(time.time() - t0, 1)}
    C.dump_json(od / "build.json", info)
    # band check crops (C0 frame)
    reg = C.bilinear(rgba[..., :3] * rgba[..., 3:4] + (1 - rgba[..., 3:4]) * np.array([1, 0, 1], np.float32),
                     *c0_to_plate(sp, Hm, *np.meshgrid(np.arange(C.W) + 0.5, np.arange(C.H) + 0.5)))
    C.save_rgb(od / "check-paste-plate-c0.jpg", reg)
    return info


# ------------------------------------------------------------------ rasteriser (depth sheet)
def raster(cam: C.Cam, P: np.ndarray, A: np.ndarray):
    """Rasterise the grid mesh P (ny, nx, 3) with per-vertex attributes A (ny, nx, k) (perspective-correct) into the
    camera: returns depth (H, W) (inf = empty) and attributes (H, W, k)."""
    ny, nx = P.shape[:2]
    q, z = cam.project(P.reshape(-1, 3))
    q = q.reshape(ny, nx, 2)
    z = z.reshape(ny, nx)
    k = A.shape[-1]
    tris = []
    for (a, b, c) in (((0, 0), (0, 1), (1, 0)), ((0, 1), (1, 1), (1, 0))):
        ia = (slice(a[0], ny - 1 + a[0]), slice(a[1], nx - 1 + a[1]))
        ib = (slice(b[0], ny - 1 + b[0]), slice(b[1], nx - 1 + b[1]))
        ic = (slice(c[0], ny - 1 + c[0]), slice(c[1], nx - 1 + c[1]))
        tris.append((q[ia].reshape(-1, 2), q[ib].reshape(-1, 2), q[ic].reshape(-1, 2),
                     z[ia].ravel(), z[ib].ravel(), z[ic].ravel(),
                     A[ia].reshape(-1, k), A[ib].reshape(-1, k), A[ic].reshape(-1, k)))
    qa = np.concatenate([t[0] for t in tris]); qb = np.concatenate([t[1] for t in tris])
    qc = np.concatenate([t[2] for t in tris])
    za = np.concatenate([t[3] for t in tris]); zb = np.concatenate([t[4] for t in tris])
    zc = np.concatenate([t[5] for t in tris])
    Aa = np.concatenate([t[6] for t in tris]); Ab = np.concatenate([t[7] for t in tris])
    Ac = np.concatenate([t[8] for t in tris])
    ok = (za > 1) & (zb > 1) & (zc > 1) & np.isfinite(qa).all(1) & np.isfinite(qb).all(1) & np.isfinite(qc).all(1)
    x0 = np.floor(np.minimum(np.minimum(qa[:, 0], qb[:, 0]), qc[:, 0]) - 0.5).astype(np.int64)
    x1 = np.ceil(np.maximum(np.maximum(qa[:, 0], qb[:, 0]), qc[:, 0]) - 0.5).astype(np.int64)
    y0 = np.floor(np.minimum(np.minimum(qa[:, 1], qb[:, 1]), qc[:, 1]) - 0.5).astype(np.int64)
    y1 = np.ceil(np.maximum(np.maximum(qa[:, 1], qb[:, 1]), qc[:, 1]) - 0.5).astype(np.int64)
    ok &= (x1 >= 0) & (y1 >= 0) & (x0 < cam.w) & (y0 < cam.h)
    x0, y0 = np.clip(x0, 0, cam.w - 1), np.clip(y0, 0, cam.h - 1)
    x1, y1 = np.clip(x1, 0, cam.w - 1), np.clip(y1, 0, cam.h - 1)
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    idx_all = np.nonzero(ok)[0]
    frag_pix, frag_z, frag_a = [], [], []
    for lo, hi in ((0, 4), (4, 8), (8, 16), (16, 32), (32, 64), (64, 128), (128, 4096)):
        sel = idx_all[(np.maximum(bw[idx_all], bh[idx_all]) > lo) & (np.maximum(bw[idx_all], bh[idx_all]) <= hi)]
        if not len(sel):
            continue
        if hi > 128:
            groups = [np.array([i]) for i in sel]
        else:
            n_per = max(1, int(4_000_000 / (hi * hi)))
            groups = [sel[i:i + n_per] for i in range(0, len(sel), n_per)]
        for gsel in groups:
            S = int(max(bw[gsel].max(), bh[gsel].max()))
            oy, ox = np.mgrid[0:S, 0:S]
            px = x0[gsel][:, None, None] + ox[None] + 0.5
            py = y0[gsel][:, None, None] + oy[None] + 0.5
            ax, ay = qa[gsel, 0][:, None, None], qa[gsel, 1][:, None, None]
            bx, by = qb[gsel, 0][:, None, None], qb[gsel, 1][:, None, None]
            cx, cy = qc[gsel, 0][:, None, None], qc[gsel, 1][:, None, None]
            den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
            den = np.where(np.abs(den) < 1e-12, 1e-12, den)
            l0 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / den
            l1 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / den
            l2 = 1 - l0 - l1
            inside = (l0 >= -1e-6) & (l1 >= -1e-6) & (l2 >= -1e-6)
            inside &= (px - 0.5 <= x1[gsel][:, None, None]) & (py - 0.5 <= y1[gsel][:, None, None])
            ti, yy, xx = np.nonzero(inside)
            if not len(ti):
                continue
            g = gsel[ti]
            w0 = l0[ti, yy, xx] / za[g]
            w1 = l1[ti, yy, xx] / zb[g]
            w2 = l2[ti, yy, xx] / zc[g]
            ws = w0 + w1 + w2
            zz = 1.0 / ws
            aa = (Aa[g] * w0[:, None] + Ab[g] * w1[:, None] + Ac[g] * w2[:, None]) / ws[:, None]
            pix = (y0[g] + yy) * cam.w + (x0[g] + xx)
            frag_pix.append(pix); frag_z.append(zz); frag_a.append(aa.astype(np.float32))
    depth = np.full(cam.h * cam.w, np.inf)
    attr = np.zeros((cam.h * cam.w, k), np.float32)
    if frag_pix:
        pix = np.concatenate(frag_pix); zz = np.concatenate(frag_z); aa = np.concatenate(frag_a)
        o = np.lexsort((zz, pix))
        pix, zz, aa = pix[o], zz[o], aa[o]
        first = np.r_[True, pix[1:] != pix[:-1]]
        depth[pix[first]] = zz[first]
        attr[pix[first]] = aa[first]
    return depth.reshape(cam.h, cam.w), attr.reshape(cam.h, cam.w, k), (q, z)


# ------------------------------------------------------------------ real layer (map + frame-002 + heroes)
class RealLayer:
    def __init__(self, map_key: str):
        name = C.MAPS[map_key]["name"]
        bc = np.asarray(Image.open(C.DERIVED_MAPS / map_key / f"T_{name}_Map_BC_4K.png").convert("RGB"))
        mask = np.asarray(Image.open(C.DERIVED_MAPS / map_key / f"T_{name}_Map_GameMask_4K.png").convert("L"))
        self.mips = k1_mock.build_mips(k1_mock.srgb_to_lin(bc.astype(np.float32) / 255.0))
        self.mask_mips = k1_mock.build_mips(mask.astype(np.float32) / 255.0)
        self.grade = k1_mock.profile_map_grade(map_key)
        import build_map_textures as bmt
        vec = json.loads((C.REPO / f"tools/art/map_surface/{map_key}.vector-layer.json").read_text(encoding="utf-8"))
        topo = json.loads((C.EV_RESEARCH / f"{map_key}.topology.json").read_text(encoding="utf-8"))
        self.layout = bmt.k1_layout(vec, topo, {**self.grade})
        self.gain = 1.0

    def render(self, cam: C.Cam):
        """sRGB-linear colour (H, W, 3) and view depth (inf = no hit) of the map plane, frame boxes and heroes."""
        ys, xs = np.mgrid[0:cam.h, 0:cam.w]
        d = cam.rays(xs + 0.5, ys + 0.5)
        col = np.zeros((cam.h, cam.w, 3), np.float32)
        depth = np.full((cam.h, cam.w), np.inf)
        # map plane z = 0
        t0 = -cam.pos[2] / d[..., 2]
        X = cam.pos[0] + t0 * d[..., 0]
        Y = cam.pos[1] + t0 * d[..., 1]
        on = (np.abs(X) <= C.MAP_HX) & (np.abs(Y) <= C.MAP_HY) & (t0 > 0)
        u = (X + C.MAP_HX) / (2 * C.MAP_HX)
        v = (Y + C.MAP_HY) / (2 * C.MAP_HY)
        n0 = self.mips[0].shape[0]
        lx = np.hypot(np.gradient(u * n0, axis=1), np.gradient(v * n0, axis=1))
        ly = np.hypot(np.gradient(u * n0, axis=0), np.gradient(v * n0, axis=0))
        lod = np.log2(np.maximum(np.sqrt(lx * ly), 1e-6))
        alb = k1_mock.trilinear(self.mips, u[on], v[on], lod[on])
        m = k1_mock.trilinear(self.mask_mips, u[on], v[on], lod[on])
        c = k1_mock._night(alb, m, self.layout["grade"]) * self.gain
        Xm, Ym = X[on], Y[on]
        for hr in self.layout["heroes"]:
            dd = np.hypot(Xm - hr["x"] - 4.0, Ym - hr["y"] - 3.0)
            c = c * (1 - 0.45 * np.exp(-(dd / 20.0) ** 2))[:, None]
        for rg in self.layout["rings"]:
            dd = np.hypot(Xm - rg["x"], Ym - rg["y"])
            band = k1_mock._aa_band(dd, rg["r_in"], rg["r_out"], 0.6)
            rcol = k1_mock.srgb_to_lin(rg["srgb"]) * rg["intensity"]
            c = c * (1 - band)[:, None] + rcol * band[:, None]
        col[on] = c
        depth[on] = (t0[on, None] * d[on]) @ cam.fwd
        # frame-002 as 4 wood boxes (top Z 12.4, foot Z -10)
        boxes = [(-C.FRAME_HX, C.FRAME_HX, -C.FRAME_HY, -C.MAP_HY), (-C.FRAME_HX, C.FRAME_HX, C.MAP_HY, C.FRAME_HY),
                 (-C.FRAME_HX, -C.MAP_HX, -C.MAP_HY, C.MAP_HY), (C.MAP_HX, C.FRAME_HX, -C.MAP_HY, C.MAP_HY)]
        wood = k1_mock.srgb_to_lin(np.array([0.24, 0.16, 0.10], np.float32))
        L = k1_mock._light_dir(k1_mock.KEY_LIGHT_ROT)
        for (bx0, bx1, by0, by1) in boxes:
            lo = np.array([bx0, by0, -10.0]); hi = np.array([bx1, by1, C.FRAME_TOP_Z])
            inv = 1.0 / np.where(np.abs(d) < 1e-12, 1e-12, d)
            ta = (lo - cam.pos) * inv
            tb = (hi - cam.pos) * inv
            tmin = np.minimum(ta, tb).max(-1)
            tmax = np.maximum(ta, tb).min(-1)
            hit = (tmax >= tmin) & (tmin > 0)
            if not hit.any():
                continue
            ax = np.minimum(ta, tb).argmax(-1)
            dep = (tmin[..., None] * d) @ cam.fwd
            nrm = np.zeros(d.shape, np.float32)
            for k_ in range(3):
                nrm[..., k_] = np.where(ax == k_, -np.sign(d[..., k_]), 0)
            ndl = np.clip(nrm @ (-L), 0, 1)
            P = cam.pos + tmin[..., None] * d
            grain = 1 + 0.18 * np.sin(P[..., 0] * 0.9 + np.sin(P[..., 1] * 0.13) * 3) * np.sin(P[..., 1] * 0.7)
            sh = (0.30 + 0.70 * ndl) * grain
            cc = wood[None, :] * sh[hit][:, None]
            cc = k1_mock._night(cc, None, self.layout["grade"]) * self.gain * 1.6
            upd = hit & (dep < depth)
            col[upd] = cc[upd[hit]]
            depth[upd] = dep[upd]
        # heroes (k1_mock SDF placeholder)
        for hr in self.layout["heroes"]:
            hcol = col.copy()
            k1_mock._trace_hero(hcol, cam, d, t0, hr, L, self.layout["grade"], "c")
            ch = np.any(hcol != col, axis=-1)
            col[ch] = hcol[ch]
            dep = np.hypot(np.hypot(*(cam.pos[:2] - np.array([hr["x"], hr["y"]]))), cam.pos[2] - 25.0)
            depth[ch] = np.minimum(depth[ch], dep * 0.98)
        return col, depth


# ------------------------------------------------------------------ 3D detail stand-ins
def detail_positions(spec: dict, cam0: C.Cam, proxy: str = "relief") -> list[dict]:
    """World position of every 3D detail: the C0 ray through its painted pixel, hitting the proxy surface it is
    mounted on (flats / ground at +heightUU), so it stays registered to the painted host in every view."""
    g = spec["geometry"]
    zones = {z["id"]: z for z in g["planeZones"]}
    out = []
    for dtl in spec["details"]:
        fx, fy = np.array(float(dtl["px"][0])), np.array(float(dtl["px"][1]))
        on = dtl["on"]
        if on in zones and (proxy == "relief" or zones[on]["type"] == "slope"):
            P0, n = zone_plane(cam0, zones[on], g["groundZ"])
            P = ray_plane(cam0, fx, fy, P0, n)[0]
        else:
            P = ray_z(cam0, fx, fy, g["groundZ"] + dtl.get("heightUU", 0.0))[0]
        # size from the painted extent at that depth
        depth = float((P - cam0.pos) @ cam0.fwd)
        uu_per_px = depth / cam0.f_px
        out.append({**dtl, "world": [round(float(v), 1) for v in P], "c0DepthUU": round(depth, 1),
                    "sizeUU": [round(s * uu_per_px, 1) for s in dtl.get("sizePx", [0, 0])]})
    return out


def true_positions(spec: dict, cam0: C.Cam) -> dict:
    """Reference 'true' positions for the alignment metric: the relief-proxy positions (flats = physical hosts)."""
    return {d["id"]: np.array(d["world"]) for d in detail_positions(spec, cam0, "relief")}


def render_details(cam: C.Cam, details: list[dict], col, depth):
    """Emissive / dark spheres as stand-ins (lantern 8 uu warm, fire 12 uu orange, cannon 3 dark spheres, banner a
    red quad)."""
    ys, xs = np.mgrid[0:cam.h, 0:cam.w]
    d = cam.rays(xs + 0.5, ys + 0.5)
    dn = d / np.linalg.norm(d, axis=-1, keepdims=True)
    cosf = dn @ cam.fwd

    def sphere(c, r, colr):
        oc = cam.pos - c
        b = dn @ oc
        disc = b * b - (oc @ oc - r * r)
        hit = disc > 0
        t = -b - np.sqrt(np.maximum(disc, 0))
        dep = t * cosf
        upd = hit & (t > 0) & (dep < depth)
        col[upd] = colr
        depth[upd] = dep[upd]

    for dt in details:
        P = np.array(dt["world"])
        if dt["kind"] == "lantern":
            sphere(P, 9.0, np.array([3.2, 1.6, 0.45], np.float32))
        elif dt["kind"] in ("campfire", "brazier"):
            sphere(P + [0, 0, 6], 13.0, np.array([4.0, 1.4, 0.25], np.float32))
        elif dt["kind"] == "cannon":
            dirv = np.array([-0.7, 0.7, 0.0])
            for s in (-18, 0, 18):
                sphere(P + dirv * s, 8.0, np.array([0.02, 0.02, 0.025], np.float32))
        elif dt["kind"] == "banner":
            for s in range(0, 160, 10):
                sphere(P + [0, 0, -s], 9.0, np.array([0.35, 0.03, 0.02], np.float32))
    return col, depth


# ------------------------------------------------------------------ sea layer (backward mapping)
def render_sea(cam: C.Cam, spec: dict, sea_tex: np.ndarray, Hm, sp: dict, c0: C.Cam):
    g = spec["geometry"]
    ys, xs = np.mgrid[0:cam.h, 0:cam.w]
    d = cam.rays(xs + 0.5, ys + 0.5)
    t = (g["seaZ"] - cam.pos[2]) / d[..., 2]
    P = cam.pos + t[..., None] * d
    cyl = g["skyCylinder"]
    cxy = np.array(cyl["centre"])
    R = cyl["radius"]
    far = (np.hypot(P[..., 0] - cxy[0], P[..., 1] - cxy[1]) > R) | (t <= 0)
    # ray / vertical cylinder (from inside)
    ox, oy = cam.pos[0] - cxy[0], cam.pos[1] - cxy[1]
    a = d[..., 0] ** 2 + d[..., 1] ** 2
    b = 2 * (ox * d[..., 0] + oy * d[..., 1])
    cc = ox * ox + oy * oy - R * R
    tc = (-b + np.sqrt(np.maximum(b * b - 4 * a * cc, 0))) / (2 * a)
    Pc = cam.pos + tc[..., None] * d
    P = np.where(far[..., None], Pc, P)
    q, _ = c0.project(P)
    px_, py_ = c0_to_plate(sp, Hm, q[..., 0], q[..., 1])
    # clamp to the plate (edge extension) and count what lies outside the extended canvas
    h, w = sea_tex.shape[:2]
    outside = (px_ < 0) | (py_ < 0) | (px_ > w) | (py_ > h)
    colr = C.bilinear(sea_tex, np.clip(px_, 0.5, w - 0.5), np.clip(py_, 0.5, h - 0.5))
    return colr, outside


# ------------------------------------------------------------------ render a view
def render_view(map_key: str, cam: C.Cam, spec: dict, ctx: dict, proxy: str, with_details=True):
    real_col, real_depth = ctx["real"].render(cam)
    sp = ctx["sp"]
    P = ctx["sheets"][proxy]
    q0, _ = ctx["c0"].project(P.reshape(-1, 3))
    # vertex UV = the C0 px of the vertex itself (the grid), mapped into the plate
    gx, gy = ctx["grid"]
    FX, FY = np.meshgrid(gx, gy)
    upx, upy = c0_to_plate(sp, ctx["H"], FX, FY)
    A = np.dstack([upx, upy, FX, FY]).astype(np.float32)
    sdepth, sattr, _ = raster(cam, P, A)
    has = np.isfinite(sdepth)
    rgba = ctx["paste"]
    h, w = rgba.shape[:2]
    pc = C.bilinear(rgba, np.clip(sattr[..., 0], 0.5, w - 0.5), np.clip(sattr[..., 1], 0.5, h - 0.5))
    alpha = np.where(has, pc[..., 3], 0.0)
    out_ext = has & ((sattr[..., 0] < 0) | (sattr[..., 1] < 0) | (sattr[..., 0] > w) | (sattr[..., 1] > h))
    paint = k1_mock.srgb_to_lin(pc[..., :3]) * ctx["paintGain"]
    sea, sea_out = render_sea(cam, spec, ctx["sea"], ctx["H"], sp, ctx["c0"])
    sea = k1_mock.srgb_to_lin(sea) * ctx["paintGain"]
    # composite: sea, then the sheet (alpha over sea), then the real layer / details by depth
    col = sea * (1 - alpha[..., None]) + paint * alpha[..., None]
    sheet_depth = np.where(alpha > 0.5, sdepth, np.inf)
    use_real = real_depth < sheet_depth
    col = np.where(use_real[..., None], real_col, col)
    depth = np.minimum(real_depth, sheet_depth)
    if with_details:
        col, depth = render_details(cam, ctx["details"], col, depth)
    srgb = k1_mock.lin_to_srgb(col).astype(np.float32)
    layers = {"real": use_real, "sheet": (~use_real) & (alpha > 0.5), "sea": (~use_real) & (alpha <= 0.5),
              "outsideExtended": (~use_real) & ((out_ext & (alpha > 0.5)) | (sea_out & (alpha <= 0.5)))}
    return srgb, layers, sattr, has


def concept_c0_ctx(map_key: str, out: Path, proxy_list=("relief",)) -> dict:
    spec = load_spec(map_key)
    od = out / map_key
    sp = spec["plates"]["colour"]
    ctx = {"spec": spec, "sp": sp, "H": load_h(map_key, out), "c0": C.concept_cam(),
           "real": RealLayer(map_key)}
    rgba = np.asarray(Image.open(od / "paste-plate-rgba.png")).astype(np.float32) / 255.0
    ctx["paste"] = rgba
    ctx["sea"] = np.asarray(Image.open(od / "sea-plate.png").convert("RGB")).astype(np.float32) / 255.0
    step = spec["geometry"]["vertexStepPx"]
    ctx["grid"] = (np.arange(EXT[0], EXT[2] + step, step), np.arange(EXT[1], EXT[3] + step, step))
    ctx["sheets"] = {p: np.load(od / f"sheet-{p}.npy").astype(np.float64) for p in proxy_list}
    ctx["details"] = detail_positions(spec, ctx["c0"], "relief")
    ctx["paintGain"] = 1.0
    return ctx
