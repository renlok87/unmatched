"""ENV-MAPS P8.1 (track A): albedo bake of the concept scene (system Python; numpy / scipy / PIL; CPU only).

  python -B tools/art/concept_scene/bake_albedo.py [--only Island,Ship] [--force]   # bake + manifest
  python -B tools/art/concept_scene/bake_albedo.py --manifest-only                  # manifest from the files on disk
  python -B tools/art/concept_scene/bake_albedo.py --check                          # sha256 of the outputs vs manifest

Route 1 - BAKED (the custom meshes: island, ship, fort, palisade, piles): every texel of a mesh's UV0 atlas
(<work>/SM_Env_S_<Name>.npz = the exported FBX's UVs) gets its board-space position / face normal by UV rasterisation;
  * C0 visibility: a C0 depth buffer of all scene meshes (back faces culled, 1.5 px per C0 px over the extended canvas);
    a texel is projectable when its C0 depth is within tol of the buffer (3x3 max), it faces C0 (n.v, weight
    smoothstep(facingLo, facingHi)), lies inside the extended canvas and - on the island top - outside the painted
    frame band (the painted frame is ~2-3.6x wider than frame-002: cut.paintedFrameOuterUU of sarpedon.paste.json; that
    band is painted with ground albedo, not stretched - task diagnosis #2);
  * projected albedo: the P8 albedo plate (sarpedon-extended-albedo-2x.png, de-lit low + x2 detail) sampled at the
    texel's C0 pixel through the registration homography with the classic Lanczos-3 of cp_bake (the P7 code path);
  * fallback (texels hidden from C0, grazing, the frame band, under the map): the CC0 material of the surface
    (Rock058 cliffs / fort, Ground055S sand, Moss002 forest floor, Planks023A wood; ambientCG, ENV-U5 set) sampled
    triplanar in world space, colour-matched to the neighbouring projected albedo: a world-space voxel field of the
    projected colours (normalised convolution, pull-push until filled) gives the local mean, fallback = local mean x
    CC0 / CC0 mean;
  * ORM: R = Cycles CPU ambient occlusion (cs_blender.py 'ao', upsampled), G = roughness (rock 0.88, ground 0.92, wood
    0.86, forest 0.9; wet rocks near the sea 0.35, the bay water 0.3), B = metal 0; N = DirectX tangent normal from the
    albedo luma (gaussian sigma 1.5 px, strength <= 0.3); BC = sRGB albedo; everything dilated over the atlas gaps.
Route 2 - PROJECTED (pack meshes; M_EnvScene 'projected' mode of track B): T_Env_S_AlbedoC0.png = the albedo plate
  rectified (registration baked in, identity homography) over the extended canvas C0 [-384, -216] .. [2304, 1296]
  (rectC0Px [-384, -216, 2688, 1512], the P7 PlateB rect) at 4096 x 2048 (power of two), the painted-frame band of the
  ground plane filled by pull-push from the surrounding ground (no stretch).

Outputs OUT of git (ENV-U3 / ENV-U7): scraped-data/derived/concept-scene/sarpedon/ (gitignored); git: the manifest
tools/art/concept_scene/manifest.sarpedon.json (schema unmatched.concept-scene/1, sha256 of every file, the track A /
B interface) and the per-mesh bake statistics in it. Self-check previews (C0 re-projection of the baked albedo, out of
git) -> <work>/overlays/bake-*.jpg.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cs_common as CS  # noqa: E402
import cp_bake as CB  # noqa: E402  (tools/art/concept_paste: Lanczos sampler, texel grids)
import run_scene as RS  # noqa: E402

Image.MAX_IMAGE_PIXELS = None
LUMA = np.array([0.2126, 0.7152, 0.0722], np.float32)
# track A's generators (track B owns ue_import_concept_scene.py / ue_scene_material.py in the same folder)
TRACK_A_SCRIPTS = ("cs_common.py", "cs_geom.py", "cs_blender.py", "ship_build.py", "island_build.py", "fort_build.py",
                   "palisade_build.py", "piles_build.py", "banner_build.py", "frame_band_build.py", "cascade_build.py",
                   "scene_layout.py", "bake_albedo.py", "run_scene.py")


# ------------------------------------------------------------------ helpers
def save_png(path: Path, img01: np.ndarray):
    path.parent.mkdir(parents=True, exist_ok=True)
    a = np.clip(np.round(np.asarray(img01, np.float32) * 255.0), 0, 255).astype(np.uint8)
    Image.fromarray(a, "RGB" if a.ndim == 3 else "L").save(path, format="PNG", compress_level=6)


def load_plate() -> np.ndarray:
    p = CS.PLATES / CS.ALBEDO_PLATE["file"]
    man = CS.load_json(CS.PLATES / "manifest.json")
    want = man["files"][CS.ALBEDO_PLATE["file"]]["sha256"]
    got = CS.sha256(p)
    if got != want:
        raise SystemExit(f"{p}: sha256 {got} != the P8.0 manifest {want}")
    return np.asarray(Image.open(p).convert("RGB")).astype(np.float32) / 255.0


def cc0(name: str, px: int = 1024) -> np.ndarray:
    """The CC0 colour map (ambientCG 2K JPG) resampled to `px` (= the tile size in atlas texels: no aliasing)."""
    p = CS.CC0_RAW / name / f"{name}_2K-JPG_Color.jpg"
    im = Image.open(p).convert("RGB").resize((int(px), int(px)), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def wrap_bilinear(img: np.ndarray, u: np.ndarray, v: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    x = (u % 1.0) * w - 0.5
    y = (v % 1.0) * h - 0.5
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    ax, ay = (x - x0)[..., None], (y - y0)[..., None]
    x0 %= w
    y0 %= h
    x1, y1 = (x0 + 1) % w, (y0 + 1) % h
    return (img[y0, x0] * (1 - ax) * (1 - ay) + img[y0, x1] * ax * (1 - ay) + img[y1, x0] * (1 - ax) * ay +
            img[y1, x1] * ax * ay)


def triplanar(img: np.ndarray, P: np.ndarray, N: np.ndarray, tile: float) -> np.ndarray:
    w = np.abs(N) ** 4
    w /= np.maximum(w.sum(1, keepdims=True), 1e-9)
    a = wrap_bilinear(img, P[:, 1] / tile, P[:, 2] / tile)
    b = wrap_bilinear(img, P[:, 0] / tile, P[:, 2] / tile)
    c = wrap_bilinear(img, P[:, 0] / tile, P[:, 1] / tile)
    return a * w[:, :1] + b * w[:, 1:2] + c * w[:, 2:3]


def uv_raster(mesh: CS.Mesh, W: int, H: int):
    """Per texel: triangle id (-1 = empty) and barycentrics, from the UV0 triangles (texel centres)."""
    T = len(mesh.F)
    q = np.stack([mesh.UV[..., 0] * W, (1.0 - mesh.UV[..., 1]) * H], -1).reshape(-1, 2)
    z = np.full(len(q), 2.0)
    F = np.arange(T * 3).reshape(T, 3)
    _, tid = CS.raster_screen(q, z, F, W, H)
    ys, xs = np.nonzero(tid >= 0)
    t = tid[ys, xs]
    a, b, c = q[F[t, 0]], q[F[t, 1]], q[F[t, 2]]
    px, py = xs + 0.5, ys + 0.5
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    l0 = ((b[:, 1] - c[:, 1]) * (px - c[:, 0]) + (c[:, 0] - b[:, 0]) * (py - c[:, 1])) / den
    l1 = ((c[:, 1] - a[:, 1]) * (px - c[:, 0]) + (a[:, 0] - c[:, 0]) * (py - c[:, 1])) / den
    L = np.stack([l0, l1, 1 - l0 - l1], -1).astype(np.float32)
    return tid, ys, xs, t, np.clip(L, -0.05, 1.05)


def frame_band(P: np.ndarray, spec: dict, beams: dict | None = None) -> np.ndarray:
    """1 where a ground point lies in the painted-frame band (outside frame-002 minus 2 uu, inside the painted frame's
    outer edge + 6 uu per side; corners: the painted corner size). P9: with `beams` (frame_band_build.outer_extents)
    the band is the frame band mesh's own footprint (+ beamPadUU): the island top there lies under the heavy frame;
    the sliver between the beam and the painted outer edge on the ground (hidden at C0, seen from the K views) takes
    the ground of its side like the rest of the top."""
    if beams is not None:
        X, Y = P[:, 0], P[:, 1]
        pad = float(beams.get("padUU", 0.0))
        inside_outer = (X >= beams["westX"] - pad) & (X <= beams["eastX"] + pad) & (Y >= beams["farY"] - pad) &             (Y <= beams["nearY"] + pad)
        under_frame = (np.abs(X) <= C.FRAME_HX - 2.0) & (np.abs(Y) <= C.FRAME_HY - 2.0)
        return inside_outer & ~under_frame
    cut = spec["cut"]
    pw = cut["paintedFrameOuterUU"]
    X, Y = P[:, 0], P[:, 1]
    ex = np.abs(X) - C.MAP_HX
    ey = np.abs(Y) - C.MAP_HY
    lim_x = np.where(X < 0, pw["west"], pw["east"]) + 6.0
    lim_y = np.where(Y < 0, pw["far"], pw["near"]) + 6.0
    corner = (ex > 0) & (ey > 0)
    lim_x = np.where(corner, np.maximum(lim_x, cut["paintedCornerUU"] + 6.0), lim_x)
    lim_y = np.where(corner, np.maximum(lim_y, cut["paintedCornerUU"] + 6.0), lim_y)
    inside_outer = (ex <= lim_x) & (ey <= lim_y)
    under_frame = (ex <= C.FRAME_UU - 2.0) & (ey <= C.FRAME_UU - 2.0)
    return inside_outer & ~under_frame


C = CS.C


class VoxelField:
    """World-space colour field of the projected albedo (normalised convolution, pull-push fill)."""

    def __init__(self, lo, hi, cell):
        self.lo = np.asarray(lo, float)
        self.cell = float(cell)
        self.n = np.maximum(np.ceil((np.asarray(hi, float) - self.lo) / cell).astype(int) + 1, 1)
        self.acc = np.zeros((*self.n, 3), np.float64)
        self.w = np.zeros(tuple(self.n), np.float64)

    def idx(self, P):
        i = np.clip(((P - self.lo) / self.cell).astype(int), 0, self.n - 1)
        return i[:, 0], i[:, 1], i[:, 2]

    def add(self, P, rgb, w):
        i, j, k = self.idx(P)
        np.add.at(self.acc, (i, j, k), rgb * w[:, None])
        np.add.at(self.w, (i, j, k), w)

    def fill(self):
        acc, w = self.acc.copy(), self.w.copy()
        out = np.zeros_like(acc)
        have = np.zeros(w.shape, bool)
        for sig in (0.8, 1.6, 3.2, 6.4, 12.8, 25.6, 51.2):
            a = np.stack([ndimage.gaussian_filter(acc[..., c], sig, mode="nearest") for c in range(3)], -1)
            ww = ndimage.gaussian_filter(w, sig, mode="nearest")
            ok = (ww > 1e-6) & ~have
            out[ok] = a[ok] / ww[ok][:, None]
            have |= ok
            if have.all():
                break
        if not have.all():
            out[~have] = (acc.sum((0, 1, 2)) / max(w.sum(), 1e-9))
        self.mean = out

    def lookup(self, P):
        """Trilinear (voxel centres) - no blocky steps in the fallback colour."""
        g = ((P - self.lo) / self.cell - 0.5).T
        return np.stack([ndimage.map_coordinates(self.mean[..., c], g, order=1, mode="nearest") for c in range(3)], -1)


# ------------------------------------------------------------------ the C0 depth buffer of the scene
def scene_zbuf(meshes: dict, layout: dict | None, scale: float):
    cam = CS.cam0()
    rect = CS.RECT_B
    w, h = int((rect[2] - rect[0]) * scale), int((rect[3] - rect[1]) * scale)
    Ps, Fs, base, owner = [], [], 0, []
    for k, (name, m) in enumerate(meshes.items()):
        Ps.append(m.board())
        Fs.append(m.F + base)
        owner += [k] * len(m.F)
        base += len(m.V)
    P = np.vstack(Ps)
    F = np.vstack(Fs)
    depth, tid = CS.raster_tris(cam, P, F, w, h, rect=rect, cull_back=True)
    own = np.where(tid >= 0, np.asarray(owner)[np.maximum(tid, 0)], -1)
    zmax3 = ndimage.maximum_filter(np.where(np.isfinite(depth), depth, -np.inf), size=3)
    return {"depth": depth, "zmax3": zmax3, "owner": own, "names": list(meshes), "w": w, "h": h, "scale": scale,
            "rect": rect}


# ------------------------------------------------------------------ bake one mesh
def bake_mesh(key: str, mesh: CS.Mesh, size: int, zb: dict, plate: np.ndarray, H: np.ndarray, P: dict,
              ao_path: Path, out_dir: Path, log=print) -> dict:
    t0 = time.time()
    cam = CS.cam0()
    spec = CS.spec()
    W = Hh = int(size)
    tid, ys, xs, t, L = uv_raster(mesh, W, Hh)
    Vb = mesh.board()
    Fn = mesh.face_normals()
    n_tex = len(t)
    Pw = (Vb[mesh.F[t, 0]] * L[:, :1] + Vb[mesh.F[t, 1]] * L[:, 1:2] + Vb[mesh.F[t, 2]] * L[:, 2:3]).astype(np.float64)
    Nw = Fn[t]
    smooth = mesh.SMOOTH[t]
    q, depth = cam.project(Pw)
    rect = zb["rect"]
    zx = np.clip(((q[:, 0] - rect[0]) * zb["scale"]).astype(int), 0, zb["w"] - 1)
    zy = np.clip(((q[:, 1] - rect[1]) * zb["scale"]).astype(int), 0, zb["h"] - 1)
    zref = zb["zmax3"][zy, zx]
    tol = P["depthTolUU"] + P["depthTolRel"] * depth
    vis = depth <= zref + tol
    vdir = cam.pos[None, :] - Pw
    vdir /= np.linalg.norm(vdir, axis=1, keepdims=True)
    facing = np.einsum("ij,ij->i", Nw, vdir)
    m = P["canvasMarginPx"]
    inside = (q[:, 0] > rect[0] + m) & (q[:, 0] < rect[2] - m) & (q[:, 1] > rect[1] + m) & (q[:, 1] < rect[3] - m)
    wgt = vis * CS.smoothstep(P["facing"][0], P["facing"][1], facing) * inside
    band = np.zeros(n_tex, bool)
    if key == "Island":
        import frame_band_build as FBB  # P9 F2: the band is real geometry now
        beams = dict(FBB.outer_extents(CS.params()["frameBand"]), padUU=float(P["frameBand"].get("beamPadUU", 0.0)))
        band = smooth & frame_band(Pw, spec, beams)
        wgt = wgt * (~band)
        under = (np.abs(Pw[:, 0]) < C.FRAME_HX - 2) & (np.abs(Pw[:, 1]) < C.FRAME_HY - 2)
        wgt = wgt * (~under)
    wgt = wgt.astype(np.float32)
    # projected albedo (Lanczos-3 of cp_bake through the registration H) where it is used
    proj = np.zeros((n_tex, 3), np.float32)
    use = wgt > 0.0
    idx = np.nonzero(use)[0]
    sp = CS.ALBEDO_PLATE
    src_per_c0 = sp["conceptRectPx"][2] / C.W
    # texel footprint in C0 px (median over the projected texels) -> minification factor of the kernel
    for c0 in range(0, len(idx), 400000):
        sel = idx[c0:c0 + 400000]
        px, py = CS.pp.c0_to_plate(sp, H, q[sel, 0], q[sel, 1])
        proj[sel] = CB.lanczos_sample(plate, px, py, 1.0, 1.0, 3)
    # world colour field of the projected albedo -> the local mean for the fallback
    lo, hi = Pw.min(0) - 1, Pw.max(0) + 1
    vf = VoxelField(lo, hi, P["voxelUU"])
    good = wgt > 0.5
    vf.add(Pw[good], proj[good].astype(np.float64), np.ones(int(good.sum())))
    vf.fill()
    local = vf.lookup(Pw).astype(np.float32)
    # CC0 fallback per surface class
    mats = P["fallback"][key]
    fb = np.zeros((n_tex, 3), np.float32)
    rough = np.zeros(n_tex, np.float32)
    cls = np.zeros(n_tex, np.int8)
    if key == "Island":
        forest = CS.inside(island_forest_poly(), Pw[:, :2])
        # 0 cliff rock, 1 sand / ground, 2 moss (forest floor), 3 deck planks; the painted-frame band takes the
        # ground of its side in the painting: far = the beach sand, west = the forest floor, east = the dock planks,
        # near = the mossy rim of the cliffs
        cls = np.where(~smooth, 0, np.where(forest, 2, 1)).astype(np.int8)
        ex, ey = np.abs(Pw[:, 0]) - C.MAP_HX, np.abs(Pw[:, 1]) - C.MAP_HY
        side = np.where(ex > ey, np.where(Pw[:, 0] < 0, 2, 3), np.where(Pw[:, 1] < 0, 1, 2)).astype(np.int8)
        cls = np.where(band, side, cls).astype(np.int8)
        fbc = P.get("frameBand") or {}
        if fbc.get("mode") == "plateMeanPlanks" and band.any():
            # P8.3: the painted-frame band = the CC0 planks on the low-passed colour of the painted frame itself (the
            # plate at the band's C0 pixels, a world voxel field of cellUU: no painted bolts / brackets, no stretch) -
            # the frame-002 stands on a dark wooden platform as wide as the painted frame (G4: the band was grey ground)
            bsel = np.nonzero(band & vis & inside)[0]
            if len(bsel):
                px_, py_ = CS.pp.c0_to_plate(sp, H, q[bsel, 0], q[bsel, 1])
                pb = CB.lanczos_sample(plate, px_, py_, 1.0, 1.0, 3).astype(np.float64)
                blo, bhi = Pw[band].min(0) - 1, Pw[band].max(0) + 1
                bf = VoxelField(blo, bhi, float(fbc["cellUU"]))
                bf.add(Pw[bsel], pb, np.ones(len(bsel)))
                bf.fill()
                local = local.copy()
                local[band] = (bf.lookup(Pw[band]) * float(fbc.get("gain", 1.0))).astype(np.float32)
                cls = np.where(band, int(fbc["class"]), cls).astype(np.int8)
    area = float(np.linalg.norm(np.cross(Vb[mesh.F[:, 1]] - Vb[mesh.F[:, 0]], Vb[mesh.F[:, 2]] - Vb[mesh.F[:, 0]]),
                                axis=1).sum() / 2)
    rho = math.sqrt(n_tex / max(area, 1.0))  # atlas texels per uu
    for ci, mat in enumerate(mats):
        sel = cls == ci
        if not sel.any():
            continue
        img = cc0(mat["cc0"], max(64, min(2048, int(round(mat["tileUU"] * rho)))))
        mean = img.reshape(-1, 3).mean(0)
        tex = triplanar(img, Pw[sel], Nw[sel], mat["tileUU"])
        lt = tex @ LUMA
        # brightness detail of the CC0 (luma ratio: no hue noise) on the local colour; a little of the CC0 hue mixed in
        # at the local brightness
        ll = local[sel] @ LUMA
        hue = tex / np.maximum(lt, 1e-4)[:, None] * ll[:, None]
        base = local[sel] * (1 - P["fallbackHueMix"]) + hue * P["fallbackHueMix"]
        fb[sel] = base * (1.0 + P["fallbackDetailGain"] * (lt / float(mean @ LUMA) - 1.0))[:, None]
        rough[sel] = mat["roughness"]
    if key == "Island":
        wet = (~smooth) & (Pw[:, 2] < P["wetBelowZ"][0])
        rough = np.where(wet, np.interp(Pw[:, 2], [P["wetBelowZ"][1], P["wetBelowZ"][0]], [P["wetRoughness"], rough.mean()]),
                         rough)
        bay = smooth & (Pw[:, 2] < P["bayBelowZ"])
        rough = np.where(bay, P["bayRoughness"], rough)
    alb = np.clip(wgt[:, None] * proj + (1 - wgt[:, None]) * fb, 0, 1)
    # atlas images
    BC = np.zeros((Hh, W, 3), np.float32)
    BC[ys, xs] = alb
    covered = np.zeros((Hh, W), bool)
    covered[ys, xs] = True
    RO = np.zeros((Hh, W), np.float32)
    RO[ys, xs] = rough
    # dilation over the gaps (nearest covered texel)
    idx_near = ndimage.distance_transform_edt(~covered, return_distances=False, return_indices=True)
    BC = BC[idx_near[0], idx_near[1]]
    RO = RO[idx_near[0], idx_near[1]]
    # AO (Cycles CPU, half / full res) -> atlas size
    ao = np.asarray(Image.open(ao_path).convert("L").resize((W, Hh), Image.BILINEAR)).astype(np.float32) / 255.0
    ao = np.clip(ao * P["aoGain"] + (1 - P["aoGain"]), 0, 1)
    # detail normal from the albedo luma (DirectX: green = -dh/dy_image)
    hgt = ndimage.gaussian_filter(BC @ LUMA, P["normalSigmaPx"])
    gy, gx = np.gradient(hgt)
    k = P["normalStrength"] * P["normalGain"]
    N = np.stack([-gx * k, -gy * k, np.ones_like(gx)], -1)
    N /= np.linalg.norm(N, axis=-1, keepdims=True)
    tilt = np.degrees(np.arccos(np.clip(N[..., 2][covered], -1, 1)))
    ORM = np.stack([ao, RO, np.zeros_like(RO)], -1)
    name = f"T_Env_S_{key}"
    files = {"BC": out_dir / f"{name}_BC.png", "N": out_dir / f"{name}_N.png", "ORM": out_dir / f"{name}_ORM.png"}
    save_png(files["BC"], BC)
    save_png(files["N"], N * 0.5 + 0.5)
    save_png(files["ORM"], ORM)
    # C0 coverage of this mesh
    own = zb["owner"] == zb["names"].index(key)
    stats = {"atlasPx": [W, Hh], "coveredTexels": int(n_tex), "coveredShare": round(n_tex / (W * Hh), 4),
             "projectedShare": round(float((wgt > 0.5).mean()), 4),
             "projectedWeightMean": round(float(wgt.mean()), 4),
             "frameBandTexels": int(band.sum()), "texelsPerUU": round(rho, 3),
             "c0Pixels": int(own.sum()), "c0PixelsAt": f"{zb['scale']:g} px per C0 px over the extended canvas",
             "texelsPerC0PxVisible": round(float((wgt > 0.5).sum() / max(own.sum() / zb['scale'] ** 2, 1)), 3),
             "normalTiltDeg": {"mean": round(float(tilt.mean()), 2), "p95": round(float(np.percentile(tilt, 95)), 2)},
             "aoMean": round(float(ao[covered].mean()), 3),
             "bcMeanSrgb": [round(float(v), 4) for v in BC[covered].mean(0)],
             "seconds": round(time.time() - t0, 1)}
    log(f"  {key}: {W}x{Hh} projected {stats['projectedShare']:.1%} of {n_tex} texels, C0 px {stats['c0Pixels']}, "
        f"{stats['seconds']} s")
    return {"files": files, "stats": stats, "preview": (mesh, BC)}


def island_forest_poly() -> np.ndarray:
    hz = CS.spec()["geometry"]["heightZones"][0]
    return np.array([CS.ray_z(x, y, -3.0)[:2] for x, y in hz["poly"]])


# ------------------------------------------------------------------ route 2: the projected plate
def projected_plate(plate: np.ndarray, H: np.ndarray, P: dict, out: Path) -> dict:
    w, h = P["projected"]["size"]
    x0, y0, x1, y1 = CS.RECT_B
    rect = (x0, y0, x1, y1)
    sp = CS.ALBEDO_PLATE
    sx = (sp["conceptRectPx"][2] / C.W) * (x1 - x0) / w
    sy = (sp["conceptRectPx"][3] / C.H) * (y1 - y0) / h
    img = np.zeros((h, w, 3), np.float32)
    for r0 in range(0, h, 64):
        rows = slice(r0, min(h, r0 + 64))
        FX, FY = CB.texel_c0(rect, (w, h), rows)
        px, py = CS.pp.c0_to_plate(sp, H, FX, FY)
        img[rows] = CB.lanczos_sample(plate, px, py, sx, sy, 3)
    # the painted-frame band of the ground plane: pull-push fill from the surrounding ground
    FX, FY = CB.texel_c0(rect, (w, h))
    G = CS.pp.ground_xy(CS.cam0(), FX, FY, -3.0)
    Pg = np.stack([G[0].ravel(), G[1].ravel(), np.zeros(G[0].size)], -1)
    band = frame_band(Pg, CS.spec()).reshape(h, w)
    under = ((np.abs(G[0]) < C.FRAME_HX - 2) & (np.abs(G[1]) < C.FRAME_HY - 2))
    hole = band | under
    filled = img.copy()
    wmap = (~hole).astype(np.float32)
    have = ~hole
    for sig in (2, 4, 8, 16, 32, 64):
        a = np.stack([ndimage.gaussian_filter(img[..., c] * wmap, sig) for c in range(3)], -1)
        ww = ndimage.gaussian_filter(wmap, sig)
        ok = (ww > 0.05) & ~have & band
        filled[ok] = a[ok] / ww[ok][:, None]
        have |= ok
    save_png(out, filled)
    return {"size": [w, h], "rectC0Px": [x0, y0, x1 - x0, y1 - y0], "bandTexels": int(band.sum()),
            "kernelPxPerTexel": [round(sx, 4), round(sy, 4)]}


# ------------------------------------------------------------------ previews (self-check, out of git)
def reproject_preview(meshes: dict, baked: dict, cam, path: Path, rect=(0.0, 0.0, 1920.0, 1080.0), scale=0.5,
                      unbaked_rgb=(0.15, 0.15, 0.18)):
    w, h = int((rect[2] - rect[0]) * scale), int((rect[3] - rect[1]) * scale)
    Ps, Fs, UVs, owner, base = [], [], [], [], 0
    names = list(meshes)
    for k, n in enumerate(names):
        m = meshes[n]
        Ps.append(m.board())
        Fs.append(m.F + base)
        UVs.append(m.UV)
        owner += [k] * len(m.F)
        base += len(m.V)
    P = np.vstack(Ps)
    F = np.vstack(Fs)
    UV = np.vstack(UVs)
    owner = np.asarray(owner)
    depth, tid = CS.raster_tris(cam, P, F, w, h, rect=rect, cull_back=True)
    q, z = cam.project(P)
    q = (q - np.array(rect[:2])) * scale
    out = np.zeros((h, w, 3), np.float32)
    ys, xs = np.nonzero(tid >= 0)
    t = tid[ys, xs]
    a, b, c = q[F[t, 0]], q[F[t, 1]], q[F[t, 2]]
    px, py = xs + 0.5, ys + 0.5
    den = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    l0 = ((b[:, 1] - c[:, 1]) * (px - c[:, 0]) + (c[:, 0] - b[:, 0]) * (py - c[:, 1])) / den
    l1 = ((c[:, 1] - a[:, 1]) * (px - c[:, 0]) + (a[:, 0] - c[:, 0]) * (py - c[:, 1])) / den
    l2 = 1 - l0 - l1
    za, zb_, zc = z[F[t, 0]], z[F[t, 1]], z[F[t, 2]]
    ws = l0 / za + l1 / zb_ + l2 / zc
    l0, l1, l2 = l0 / za / ws, l1 / zb_ / ws, l2 / zc / ws
    uv = UV[t, 0] * l0[:, None] + UV[t, 1] * l1[:, None] + UV[t, 2] * l2[:, None]
    for k, n in enumerate(names):
        sel = owner[t] == k
        if n in baked:
            BC = baked[n]
            Hh, W = BC.shape[:2]
            out[ys[sel], xs[sel]] = C.bilinear(BC, uv[sel, 0] * W, (1 - uv[sel, 1]) * Hh)
        else:
            out[ys[sel], xs[sel]] = unbaked_rgb
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(out * 255, 0, 255).astype(np.uint8)).save(path, quality=88)
    return out, tid >= 0


# ------------------------------------------------------------------ manifest
def mesh_entries(baked_stats: dict) -> tuple[list, list]:
    """(baked meshes, untextured scene meshes that keep an existing material)."""
    out, extra = [], []
    exp = CS.load_json(CS.WORK / "export-report.json")["exports"]
    by = {e["name"]: e for e in exp}
    lay = CS.load_json(CS.SCENE_LAYOUT)
    shadow = {p["mesh"]: p.get("castShadow", False) for p in lay["props"]["add"]}
    for key, (run, stem, slot, unwrap, sharp, smooth, atlas, ao) in RS.MESHES.items():
        e = by[stem]
        fbx = CS.REPO / e["fbx"]
        ue = f"{CS.UE_DIR}/{stem}"
        ent = {"name": key, "fbx": e["fbx"], "ue": ue, "tris": e["triangles"],
               "castShadow": bool(shadow.get(ue, False)), "lumenGI": key != "Banner",
               "pivotBoard": e["pivotBoard"], "slots": e["slots"],
               "sha256": {e["fbx"]: CS.sha256(fbx)}}
        if atlas:
            tex = {}
            for k in ("BC", "N", "ORM"):
                f = CS.DERIVED / f"T_Env_S_{key}_{k}.png"
                r = CS.rel(f)
                tex[k] = r
                ent["sha256"][r] = CS.sha256(f) if f.is_file() else None
            ent["textures"] = tex
            ent["textureAssets"] = {k: f"{CS.UE_DIR}/T_Env_S_{key}_{k}" for k in ("BC", "N", "ORM")}
            ent["textureSettings"] = {"BC": "sRGB, default", "N": "Normalmap, DirectX (green down), no flip",
                                      "ORM": "linear masks (sRGB off): R AO, G roughness, B metal"}
            ent["mi"] = f"{CS.UE_DIR}/MI_Env_S_{key}"
            ent["atlasPx"] = [atlas, atlas]
            ent["bake"] = baked_stats.get(key)
            out.append(ent)
        else:
            ent["textures"] = {}
            ent.update(EXISTING_MATERIAL[key](ent))
            extra.append(ent)
    return out, extra


def _banner_entry(ent: dict) -> dict:
    return {"slots": ["/Game/EnvKit/ConceptPaste/MI_EnvCP_Banner"],
            "note": ("vertical banner cloth, the P7c M_EnvCP_Banner UV contract (u across, v rail..hem, rod at "
                     "Blender V 1.04..1.06): slot -> MI_EnvCP_Banner (WPO wind, sigil), not baked")}


def _material_route_entry(names: list[str], note: str):
    """P9: meshes whose slots take track B's material-route MIs (ue_scene_material.MATERIAL_LOOKS: MAP_ROOT/
    MI_EnvScene_<Name>), one MI per slot in slot order; not baked."""
    def f(ent: dict) -> dict:
        slots = [f"{CS.UE_DIR}/MI_EnvScene_{n}" for n in names]
        return {"slots": slots, "mi": slots[0], "note": note}
    return f


EXISTING_MATERIAL = {
    "Banner": _banner_entry,
    "FrameBand": _material_route_entry(["FrameWood", "FrameIron"], (
        "P9 F2 the heavy dark frame band around frame-002: slot 0 the bevelled beams (FrameWood: Planks023A dark), slot 1 "
        "the iron corner brackets / mid straps / rivets (FrameIron: the frame-002 iron); box-mapped tiling UV0 (1 UV = "
        "frameBand.uvTileUU uu), castShadow true, Lumen GI on")),
    "Cascade": _material_route_entry(["FallsSheet"], (
        "P9 F4 the cascade sheets (4 streams x 4 tiers down the front cliff): UV0 u across the whole cascade 0..1, v "
        "along the flow 0..1 per tier (a UV island per tier: lip foam + landing fade each), authored lane K style "
        "(Blender v = s / L, flipped by the FBX import: FallCard.w = 1); castShadow false, translucent; not in the "
        "bake's depth buffer")),
    "CascadeFoam": _material_route_entry(["FallsFoam"], (
        "P9 F4 the foam pads on the 3 ledges + the sea foot: UV0 u across the cascade 0..1, v from the landing edge 0 "
        "to the outer edge 1 (Blender v; FallCard.w = 1: foam at the landing, fade outwards); castShadow false")),
}


def materials_block() -> dict:
    """Top-level manifest 'materials': this build's values for track B's material-route MIs (FallCard = the
    cascade's measured stream size; the pads' depth)."""
    rep = CS.load_json(CS.RUNS["props"] / "reports" / "cascade-build.json")
    card = rep["info"]["fallCard"]
    depth = CS.params()["cascade"]["foamDepthUU"]
    return {"FallsSheet": {"vectors": {"FallCard": [card[0], card[1], 0.0, 1.0]},
                           "note": "FallCard.xy = the cascade width x the mean tier length (uu) of reports/cascade-build.json"},
            "FallsFoam": {"vectors": {"FallCard": [card[0], round((depth["ledge"] + depth["sea"]) / 2, 1), 0.0, 1.0]},
                          "note": "FallCard.xy = the cascade width x the mean pad depth (uu)"}}


def look_entries(cfg: dict) -> list:
    """Track B's look list (ue_scene_material.mi_plan: name, masked, bc, scalars, vectors); FallbackTint measured on
    the albedo plate around the C0 projections of the layout props using the look."""
    lay = CS.load_json(CS.SCENE_LAYOUT)
    cam = CS.cam0()
    rect = CS.RECT_B
    w, h = 1344, 756
    img = CS.plate_c0(rect, w, h)
    lin = np.where(img <= 0.04045, img / 12.92, ((img + 0.055) / 1.055) ** 2.4)
    out = []
    for name, c in cfg.items():
        mi = f"{CS.UE_DIR}/MI_EnvScene_Proj_{name}"
        acc, n = np.zeros(3), 0
        for p in lay["props"]["add"]:
            if p.get("material") != mi:
                continue
            q = cam.project(np.asarray(p["loc"], float) + np.array([0.0, 0.0, 20.0]))[0]
            x = int((q[0] - rect[0]) / (rect[2] - rect[0]) * w)
            y = int((q[1] - rect[1]) / (rect[3] - rect[1]) * h)
            if 4 <= x < w - 4 and 4 <= y < h - 4:
                acc += lin[y - 4:y + 5, x - 4:x + 5].reshape(-1, 3).mean(0)
                n += 1
        tint = (acc / max(n, 1)).round(4).tolist() + [1.0]
        out.append({"name": name, "mi": mi, "masked": bool(c.get("masked", False)), "bc": None,
                    "scalars": {"Roughness": c["roughness"], "ProjStrength": c["strength"], "FacingPower": c["facingPower"],
                                **({"WindAmp": c["windAmp"], "WindHz": c["windHz"], "WindHeight": c["windHeight"],
                                    "UseOpacity": 1.0} if c.get("masked") else {})},
                    "vectors": {"FallbackTint": tint}, "measuredOnProps": n, "for": c["for"]})
    return out


def write_manifest(baked_stats: dict, proj_stats: dict | None):
    P = CS.params()
    old = CS.load_json(CS.MANIFEST_PATH) if CS.MANIFEST_PATH.is_file() else {}
    if not baked_stats:
        baked_stats = {m["name"]: m.get("bake") for m in old.get("meshes", []) if m.get("bake")}
    if proj_stats is None:
        proj_stats = (old.get("projected") or {}).get("stats")
    alb = CS.DERIVED / "T_Env_S_AlbedoC0.png"
    looks = look_entries(P["bake"]["looks"])
    meshes, extra = mesh_entries(baked_stats)
    man = {
        "schema": CS.SCHEMA_MANIFEST, "map": "sarpedon",
        "status": "технически экспортировано / измерено (CREATE stage, headless; no UE import yet); художественно "
                  "не принято",
        "meshes": meshes,
        "meshesExistingMaterial": extra,
        "meshesExistingMaterialNote": "scene meshes without a baked atlas (the banner keeps the P7c MI_EnvCP_Banner: "
                                      "wind + sigil): import like 'meshes' (Nanite off, no collision), slots = 'slots'",
        "projected": {"albedo": CS.rel(alb), "ue": f"{CS.UE_DIR}/T_Env_S_AlbedoC0",
                      "rectC0Px": [CS.RECT_B[0], CS.RECT_B[1], CS.RECT_B[2] - CS.RECT_B[0], CS.RECT_B[3] - CS.RECT_B[1]],
                      "sha256": CS.sha256(alb) if alb.is_file() else None,
                      "size": P["bake"]["projected"]["size"], "colorSpace": "sRGB",
                      "uvContract": "u = (c0x - rectC0Px[0]) / rectC0Px[2], v = (c0y - rectC0Px[1]) / rectC0Px[3]; c0 = the "
                                    "C0 pixel (1920 x 1080, y down) of the world position (CONCEPT_HLSL camera of "
                                    "tools/art/concept_paste/ue_concept_material.py); identity homography (registration "
                                    "baked into the texels), outside the rect: clamp",
                      "stats": proj_stats},
        "looks": looks,
        "materials": materials_block(),
        "materialsNote": "P9: value overrides of track B's material-route MIs (ue_scene_material.MATERIAL_LOOKS) named by "
                         "the meshesExistingMaterial slots (frame band, cascade)",
        "looksNote": "projected-albedo MIs MI_EnvScene_Proj_<name> of M_EnvScene (track B, ue_scene_material.mi_plan) "
                     "named by the layout's optional prop field 'material' (all slots of the prop); FallbackTint = the "
                     "measured mean of the albedo plate over the C0 projections of the props using the look (linear "
                     "RGB), the back-face / off-plate colour",
        "layout": CS.rel(CS.SCENE_LAYOUT),
        "proxies": "tools/art/concept_scene/scene-proxies.sarpedon.json",
        "camera": CS.cam0().to_json(),
        "inputs": {"albedoPlate": {"file": (CS.PLATES / CS.ALBEDO_PLATE["file"]).as_posix(),
                                   "sha256": CS.load_json(CS.PLATES / "manifest.json")["files"][CS.ALBEDO_PLATE["file"]]["sha256"],
                                   "conceptRectPx": CS.ALBEDO_PLATE["conceptRectPx"],
                                   "registration": "tools/art/concept_paste/registration.json maps.sarpedon.extended2x"},
                   "cc0": CS.CC0_RAW.as_posix()},
        "params": {"file": CS.rel(CS.PARAMS_PATH), "sha256": CS.text_sha256_lf(CS.PARAMS_PATH)},
        "generator": {CS.rel(HERE / f): CS.text_sha256_lf(HERE / f) for f in TRACK_A_SCRIPTS},
        "seaZ": P["seaZ"],
        "notes": ["textures OUT of git (ENV-U3 / ENV-U7): scraped-data/derived/concept-scene/sarpedon/ (gitignored); the "
                  "FBX in git (each <= 15 MB)",
                  "every mesh is authored in board space: layout loc = pivotBoard, yaw 0, scale 1 (the banner: loc / yaw / "
                  "scale from the layout)",
                  "castShadow / lumenGI per mesh = the scene layout's props (layout_check rule 12)"]}
    CS.dump_json(CS.MANIFEST_PATH, man)
    return man


def check() -> int:
    man = CS.load_json(CS.MANIFEST_PATH)
    bad = []
    for m in man["meshes"] + man.get("meshesExistingMaterial", []):
        for f, h in m["sha256"].items():
            p = CS.REPO / f
            got = CS.sha256(p) if p.is_file() else None
            if got != h:
                bad.append(f"{f}: {'missing' if got is None else 'sha256 differs'}")
    a = CS.REPO / man["projected"]["albedo"]
    if not a.is_file() or CS.sha256(a) != man["projected"]["sha256"]:
        bad.append(f"{man['projected']['albedo']}: missing or sha256 differs")
    print("CONCEPT-SCENE-CHECK", "ok" if not bad else "FAILED", "; ".join(bad))
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--only", default="")
    ap.add_argument("--manifest-only", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--no-projected", action="store_true")
    a = ap.parse_args(argv)
    if a.check:
        return check()
    if a.manifest_only:
        write_manifest({}, None)
        print("manifest", CS.rel(CS.MANIFEST_PATH))
        return 0
    P = CS.params()["bake"]
    t0 = time.time()
    plate = load_plate()
    H = CS.registration_h()
    meshes = {k: CS.Mesh.load(CS.WORK / f"{v[1]}.npz") for k, v in RS.MESHES.items()}
    # the banner occludes with its layout placement
    lay = CS.load_json(CS.SCENE_LAYOUT)
    bp = next(p for p in lay["props"]["add"] if p["id"] == "banner-ship")
    bm = meshes["Banner"]
    a_ = math.radians(bp["yawDeg"])
    R = np.array([[math.cos(a_), -math.sin(a_), 0], [math.sin(a_), math.cos(a_), 0], [0, 0, 1]])
    meshes["Banner"] = CS.Mesh("SM_Env_S_Banner", bm.V * bp["scale"] @ R.T, bm.F, bm.UV, bm.MAT, bm.SMOOTH, bm.slots,
                               bp["loc"])
    # the translucent cascade water does not hide the cliff behind it from C0 (the painted water lands on the rock)
    zb = scene_zbuf({k: m for k, m in meshes.items() if k not in RS.WATER}, lay, P["zbufPxPerC0"])
    print(f"BAKE zbuf {zb['w']}x{zb['h']} in {time.time() - t0:.1f} s")
    only = [s for s in a.only.split(",") if s]
    old = CS.load_json(CS.MANIFEST_PATH) if CS.MANIFEST_PATH.is_file() else {}
    stats = {m["name"]: m.get("bake") for m in old.get("meshes", []) if m.get("bake")}
    baked = {}
    for key, (run, stem, slot, unwrap, sharp, smooth, atlas, ao) in RS.MESHES.items():
        if not atlas or (only and key not in only):
            continue
        r = bake_mesh(key, meshes[key], atlas, zb, plate, H, P, CS.WORK / "ao" / f"{stem}_AO.png", CS.DERIVED)
        stats[key] = r["stats"]
        baked[key] = r["preview"][1]
    proj = None
    if not a.no_projected and not only:
        proj = projected_plate(plate, H, P, CS.DERIVED / "T_Env_S_AlbedoC0.png")
        print(f"BAKE projected plate {proj['size']}")
    if baked:
        cam = CS.cam0()
        _, cov = reproject_preview(meshes, baked, cam, CS.WORK / "overlays" / "bake-c0.jpg")
        for label, c in (("K1", CS.C.Cam(CS.C.D_K1)), ("K2x1.6c", CS.C.Cam(CS.C.D_K2)),
                         ("K2x1.6hero", CS.C.Cam(CS.C.D_K2, CS.C.K2_HERO_FOCUS["sarpedon"]))):
            reproject_preview(meshes, baked, c, CS.WORK / "overlays" / f"bake-{label}.jpg")
    write_manifest(stats, proj)
    print(f"BAKE done in {time.time() - t0:.1f} s -> {CS.rel(CS.DERIVED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
