"""Look-dev v2 of King Arthur: numpy emulation of the M_UM_Figure_v2 core (um_v2_core.hlsl) for the Blender frames.

Blender cannot run the UE material, so the frames of this stage render "emulated" textures: per atlas texel the v2
core is evaluated in numpy with the same LUT columns the UE import will use (tools/art/material_library/
build_ue_inputs.py class_columns + apply_overrides, i.e. presets + hero overrides) and the same detail slices
(build_ue_inputs.build_slices: the v1 tiles with the fixes of the UE arrays), sampled at the per-texel UV1 in metres
(UE convention: the FBX importer flips V, the DirectX tile is read at (u1, 1 - v1) x tilesPerMeter).
Per texel (class = the MatID at 2K, nearest, as the shader's Load):
  class 0     v1 path: BC (dyed by the mask), roughness = ORM.G, metallic = ORM.B, hero normal
  metal       BC = F0 x clamp(Y(bake) / ymedClassHero, 1 +- m) x lerp(1, RMH.g, cavityDarken)
  dielectric  BC = bake clamped to [luminanceMin, luminanceMax], channel ceiling, x lerp(1, RMH.g, 0.35), skin cavity tint
  all         roughness = clamp(rTyp + (RMH.r - 0.5) x 2 x variation, lo, hi); dye lerp(bc, Team x Y x gain, mask x
              teamDyeAllowed); edge wear with the EdgeMask; detail normal RNM-blended onto the hero normal (UV1 is a
              similarity of UV0 per island, so the detail tangent frame is the hero's)
Not emulated (stated in the report): the Cloth shading model and the Fuzz (sheen) lobe, the Specular of the
dielectric classes (Blender Principled keeps 0.5), the mip/SampleGrad filtering of the tiles (bilinear at the texel).
The results are box-filtered to 2K and written as BC (sRGB), ORM (R AO, G roughness, B metallic) and N_OpenGL.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pure as P  # noqa: E402

MATLIB = P.REPO / "tools" / "art" / "material_library"
if str(MATLIB) not in sys.path:
    sys.path.insert(0, str(MATLIB))
import build_ue_inputs as B  # noqa: E402
import lookdev_ue_inputs as LUI  # noqa: E402

LUM = np.array([0.2126, 0.7152, 0.0722], np.float32)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def lin(x):
    x = np.asarray(x, np.float64)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def q8(x):
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def box2(x):
    h, w = x.shape[:2]
    return x.reshape(h // 2, 2, w // 2, 2, *x.shape[2:]).mean(axis=(1, 3))


def presets16(presets):
    """The presets restricted to the 16 MatID slots of the v2 master (index < 16), sorted by index."""
    out = dict(presets)
    out["classes"] = sorted([c for c in presets["classes"] if int(c["index"]) < 16], key=lambda c: int(c["index"]))
    if [int(c["index"]) for c in out["classes"]] != list(range(16)):
        raise RuntimeError("presets: the 16 MatID slots 0-15 are not all defined")
    return out


def columns(presets, blender_overrides, ue_fields, ymed):
    """LUT columns {index: {field: value}} exactly as the UE import builds the hero LUT (lookdev_ue_inputs.py):
    presets -> Blender-stage overrides (preset-shaped, converted by blender_overrides_to_lut) -> LUT fields."""
    p16 = presets16(presets)
    cols = B.class_columns(p16)
    bl = LUI.blender_overrides_to_lut({k: {kk: vv for kk, vv in v.items() if kk != "note"}
                                       for k, v in blender_overrides.items()})
    for cid, y in ymed.items():
        bl.setdefault(cid, {})["ymedClassHero"] = float(y)
    ue = {k: {kk: vv for kk, vv in v.items() if kk != "why"} for k, v in ue_fields.items() if isinstance(v, dict)}
    merged = LUI.merge(bl, ue)
    applied = B.apply_overrides(cols, {"classes": merged}, p16)
    return cols, merged, applied


class Slices:
    """Detail slices of the UE arrays (float, N as DirectX xy in [-1, 1], RMH in [0, 1]), cached as npy."""

    def __init__(self, presets, cache):
        cache = Path(cache)
        fn, fr = cache / "detail_n.npy", cache / "detail_rmh.npy"
        if fn.exists() and fr.exists():
            self.n = np.load(fn, mmap_mode="r")
            self.rmh = np.load(fr, mmap_mode="r")
        else:
            ns, rs, _info = B.build_slices(presets16(presets))
            self.n = np.stack(ns, 0)[..., :2].astype(np.uint8)
            self.rmh = np.stack(rs, 0)[..., :3].astype(np.uint8)
            cache.mkdir(parents=True, exist_ok=True)
            np.save(fn, self.n)
            np.save(fr, self.rmh)

    def sample(self, sl, u, v):
        """Bilinear, wrapped sample of slice `sl` at tile coordinates (u, v) (1 = one tile; v down the rows).
        Returns (n_xy DirectX [-1, 1], rmh [0, 1])."""
        size = self.n.shape[1]
        x = np.mod(u, 1.0) * size - 0.5
        y = np.mod(v, 1.0) * size - 0.5
        n_img = np.asarray(self.n[sl], np.float32) / 255.0
        r_img = np.asarray(self.rmh[sl], np.float32) / 255.0
        n = np.stack([ndimage.map_coordinates(n_img[..., c], [y, x], order=1, mode="grid-wrap") for c in range(2)], -1)
        r = np.stack([ndimage.map_coordinates(r_img[..., c], [y, x], order=1, mode="grid-wrap") for c in range(3)], -1)
        return n * 2.0 - 1.0, r


def emulate(inp, cols, slices, team=None, dye=1.0, dye_gain=5.5, mask=None, detail_strength=1.0, wear_strength=1.0):
    """inp: 4K arrays - bc (linear), ao, rough, metal (ORM of the hero), n_gl (encoded [0, 1], OpenGL), edge,
    uv1 (metres), cls (class index per 4K texel). team: linear RGB or None (= no dye: TeamColor white x TeamDye 0).
    mask: the dye mask (TeamAccent in the TeamMaskTexture slot). Returns 4K float arrays bc, rough, metal, ao, n_gl."""
    bc_h = inp["bc"]
    cls = inp["cls"]
    out_bc = bc_h.copy()
    rough = inp["rough"].copy()
    metal = inp["metal"].copy()
    ao = inp["ao"].copy()
    n_h = inp["n_gl"] * 2.0 - 1.0
    n_h /= np.maximum(np.linalg.norm(n_h, axis=-1, keepdims=True), 1e-8)
    n_out = n_h.copy()
    team_v = np.ones(3, np.float32) if team is None else np.asarray(team, np.float32)
    dye_v = 0.0 if team is None else float(dye)
    m_all = np.zeros(cls.shape, np.float32) if mask is None else mask
    stats = {}
    for ci in np.unique(cls):
        sel = cls == ci
        f = cols[int(ci)]
        bc = bc_h[sel]
        msk = m_all[sel][:, None]
        if int(ci) == 0:
            yl = bc @ LUM
            teamed = (1 - dye_v) * (bc * team_v) + dye_v * (team_v[None, :] * yl[:, None] * dye_gain)
            out_bc[sel] = bc * (1 - msk) + teamed * msk
            stats[int(ci)] = {"texels": int(sel.sum()), "path": "legacy (v1)"}
            continue
        uv1 = inp["uv1"][sel]
        tpm = float(f["tilesPerMeter"])
        dn, rmh = slices.sample(int(f["slice"]), uv1[:, 0] * tpm, (1.0 - uv1[:, 1]) * tpm)
        ns = float(f["normalStrength"]) * detail_strength
        # detail in the hero tangent frame (OpenGL: y along +v Blender = -v UE)
        d = np.stack([dn[:, 0] * ns, -dn[:, 1] * ns, np.ones(len(dn), np.float32)], -1)
        d /= np.linalg.norm(d, axis=-1, keepdims=True)
        nh = n_h[sel]
        t = nh + np.array([0, 0, 1.0], np.float32)
        uu = d * np.array([-1, -1, 1.0], np.float32)
        nb = t * ((t * uu).sum(-1) / t[:, 2])[:, None] - uu
        nb /= np.linalg.norm(nb, axis=-1, keepdims=True)
        n_out[sel] = nb
        r = np.clip(f["roughTypical"] + (rmh[:, 0] - 0.5) * 2 * f["roughVariation"] * detail_strength, f["roughLo"], f["roughHi"])
        a = inp["ao"][sel] * (1 + (rmh[:, 1] - 1) * 0.5)
        Y = bc @ LUM
        if f["bcMode"] > 0.5:
            m = f["bakeLuminanceModulation"]
            ratio = np.clip(Y / f["ymedClassHero"], 1 - m, 1 + m) if f["ymedClassHero"] > 0 else np.ones_like(Y)
            f0 = np.array([f["bcR"], f["bcG"], f["bcB"]], np.float32)
            b = f0[None, :] * ratio[:, None] * (1 + (rmh[:, 1:2] - 1) * f["cavityDarken"])
        else:
            y = np.maximum(Y, 1e-5)
            yc = np.clip(y, f["luminanceMin"], f["luminanceMax"])
            b = np.where((Y > 1e-5)[:, None], bc * (yc / y)[:, None], yc[:, None])
            b = np.minimum(b, f["maxChannel"])
            b = b * (1 + (rmh[:, 1:2] - 1) * 0.35)
            if f["cavityTintStrength"] > 0:
                tint = np.array([f["cavityTintR"], f["cavityTintG"], f["cavityTintB"]], np.float32)
                aoc = tint[None, :] + (1 - tint[None, :]) * np.clip(a, 0, 1)[:, None]
                b = b * (1 + (aoc - 1) * f["cavityTintStrength"])
        yd = b @ LUM
        dyed = (1 - dye_v) * (b * team_v) + dye_v * (team_v[None, :] * yd[:, None] * dye_gain)
        b = b + (dyed - b) * (msk * f["teamDyeAllowed"])
        wear_mean = 0.0
        if f["wearStrength"] > 0:
            wear = np.clip(inp["edge"][sel] * f["wearStrength"] * 2 - (1 - rmh[:, 2]), 0, 1) * wear_strength
            s = np.clip((inp["ao"][sel] - 0.3) / 0.5, 0, 1)
            wear = wear * s * s * (3 - 2 * s)
            if f["wornBCMode"] > 0.5:
                wbc = np.broadcast_to(np.array([f["wornBCR"], f["wornBCG"], f["wornBCB"]], np.float32), b.shape)
            else:
                wbc = np.minimum(b * f["wornBCScale"], f["maxChannel"])
            wr = f["wornRoughness"] if f["wornRoughness"] >= 0 else np.clip(r + f["wornRoughnessDelta"], 0, 1)
            b = b + (wbc - b) * wear[:, None]
            r = r + (wr - r) * wear
            wear_mean = float(wear.mean())
        out_bc[sel] = b
        rough[sel] = r
        metal[sel] = f["metallic"]
        ao[sel] = a
        stats[int(ci)] = {"texels": int(sel.sum()), "path": "metal" if f["bcMode"] > 0.5 else "dielectric",
                          "bc_Y_p10_p50_p90": P.rv(np.percentile(out_bc[sel] @ LUM, [10, 50, 90]), 4),
                          "roughness_p10_p50_p90": P.rv(np.percentile(r, [10, 50, 90]), 3), "wear_mean": P.r(wear_mean, 4)}
    return {"bc": out_bc, "rough": rough, "metal": metal, "ao": ao, "n_gl": n_out}, stats


def write_set(em, folder, flip_rows=False):
    """2K PNG set for the Blender frames: BC.png (sRGB), ORM.png (linear), N_OpenGL.png (linear, OpenGL).
    Arrays are row 0 = top of the atlas image (textures.py convention)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    bc = box2(em["bc"])
    orm = np.stack([box2(em["ao"]), box2(em["rough"]), box2(em["metal"])], -1)
    n = box2(em["n_gl"])
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-8)
    files = {}
    for name, arr, mode in (("BC", q8(srgb(bc)), "RGB"), ("ORM", q8(orm), "RGB"), ("N_OpenGL", q8(n * 0.5 + 0.5), "RGB")):
        p = folder / (name + ".png")
        Image.fromarray(arr, mode).save(p, format="PNG", compress_level=6)
        files[name] = {"file": P.rel(p), "sha256": P.sha256(p)}
    return files
