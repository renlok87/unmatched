"""Look-dev v2 (2026-09-29): the H2.1 texel state of Merlin rebuilt from the source run (system python).

The lookdev stages do not rebake and do not touch the H2.1 run: they read its work/uv/*.npz and work/bake/*.npy and
repeat the steps of maps.py that give the per-texel inputs of the material classes (UV raster -> part / island /
triangle maps, gutter fill of the Cycles bakes, team masks, per-texel source-frame position, H2.1 classes of
maps.materials_h21). maps.py is imported, not changed: its H2 behaviour stays byte-identical.

build(src) returns the state at atlas_px (4K). check_against_h21(state, src) compares the 8-bit BC / ORM / TeamMask /
TeamMaskRGBA written from this state with the H2.1 4K masters on disk (sha256 pinned in the H2.1 textures-report): the
lookdev classes are computed on exactly the texels H2.1 shipped.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import maps as M  # noqa: E402
from raster import raster  # noqa: E402

OBJECTS = M.OBJECTS


def build(src):
    """src: C.Profile of the H2.1 bake run. Arrays: row 0 = v 0 (bottom), as maps.py."""
    size = int(src["uv"]["atlas_px"])
    mcfg = src["maps"]
    part_map = np.full((size, size), -1, np.int16)
    island_map = np.full((size, size), -1, np.int32)
    obj_map = np.full((size, size), -1, np.int8)
    nz_map = np.zeros((size, size), np.float32)
    cap_map = np.zeros((size, size), np.int8)
    tri_map = np.full((size, size), -1, np.int32)
    count = np.zeros((size, size), np.uint16)
    isl_off = tri_off = 0
    uv_all, pos_all = [], []
    for oi, key in enumerate(OBJECTS):
        z = np.load(src.work / "uv" / (key + ".npz"))
        uv, part, isl, nrm = z["uv"], z["part"], z["island"], z["normal"]
        count += raster(uv, size, [(part.astype(np.int16), part_map), ((isl + isl_off).astype(np.int32), island_map),
                                   (np.full(len(uv), oi, np.int8), obj_map), (np.abs(nrm[:, 2]).astype(np.float32), nz_map),
                                   (z["cap"].astype(np.int8), cap_map), ((np.arange(len(uv)) + tri_off).astype(np.int32), tri_map)])
        isl_off += int(isl.max()) + 1
        tri_off += len(uv)
        uv_all.append(uv)
        pos_all.append(z["pos"])
    covered = count > 0
    bake = {}
    for mp in ("normal", "ao", "basecolor", "roughness", "metallic"):
        a = np.load(src.work / "bake" / (mp + ".npy")).astype(np.float32)
        written = a[..., 3] > 0.5
        _d, (jy, jx) = ndimage.distance_transform_edt(~written, return_indices=True)
        bake[mp] = a[jy, jx, :3]
    n_gl = bake["normal"] * 2.0 - 1.0
    n_gl /= np.maximum(np.linalg.norm(n_gl, axis=-1, keepdims=True), 1e-8)
    bc_lin = np.clip(bake["basecolor"], 0, 1)
    ao = np.clip(bake["ao"][..., 0], 0, 1)
    rough = np.clip(bake["roughness"][..., 0], 0, 1)
    metal = np.clip(bake["metallic"][..., 0], 0, 1)
    bc_srgb = M.srgb_encode(bc_lin)
    _d, (ky, kx) = ndimage.distance_transform_edt(part_map < 0, return_indices=True)
    part_full = part_map[ky, kx]
    island_full = island_map[ky, kx]
    obj_full = obj_map[ky, kx]
    nz_full = nz_map[ky, kx]
    h, sat, val = M.rgb_to_hsv(bc_srgb)
    tm = mcfg["team_mask"]
    team_of = {C.part_index(n): p.get("team") for n, p in src["parts"].items()}
    cloth_parts = np.isin(part_full, [k for k, v in team_of.items() if v == "cloth"])
    base_parts = np.isin(part_full, [k for k, v in team_of.items() if v == "base"])
    cc = tm["cloth"]
    hr = 10.0
    cloth = (M.ramp(h, cc["hue_deg"][0] - hr, hr) * M.ramp(-h, -cc["hue_deg"][1] - hr, hr)
             * M.ramp(sat, cc["s_min"] - cc["soft"], cc["soft"]) * M.ramp(-val, -cc["v_max"] - cc["soft"], cc["soft"]))
    cloth = np.where(cloth_parts, cloth, 0.0)
    trc = tm["trim"]
    trim = (M.ramp(h, trc["hue_deg"][0] - hr, hr) * M.ramp(-h, -trc["hue_deg"][1] - hr, hr)
            * M.ramp(sat, trc["s_min"] - trc["soft"], trc["soft"]) * M.ramp(val, trc["v_min"] - trc["soft"], trc["soft"]))
    trim = np.where(cloth_parts, trim, 0.0)
    band = (base_parts & (nz_full < tm["base_band"]["normal_z_abs_max"])).astype(np.float64)
    cloth = ndimage.uniform_filter(cloth, 3, mode="nearest")
    trim = ndimage.uniform_filter(trim, 3, mode="nearest")
    pos = M.texel_positions(np.concatenate(uv_all), np.concatenate(pos_all).astype(np.float64), tri_map)
    pos = pos[ky, kx]
    bc_new, r_new, m_new, emb, cls, _rep = M.materials_h21(mcfg["materials"], pos, part_full, covered, bc_lin, rough, metal,
                                                          trim, cloth)
    return {"size": size, "covered": covered, "part": part_full, "island": island_full, "island_raw": island_map,
            "object": obj_full, "cap": cap_map, "pos": pos, "n_gl": n_gl, "ao": ao, "rough_tripo": rough,
            "bc_lin": bc_new, "rough": r_new, "metal": m_new, "cloth": cloth, "band": band, "emb": emb, "cls": cls,
            "cloth_parts": cloth_parts, "hsv": M.rgb_to_hsv(M.srgb_encode(bc_new))}


def maps8(state):
    """The 8-bit 4K maps exactly as maps.py writes them (arrays, row 0 = bottom)."""
    s = state
    n_dx = s["n_gl"].copy()
    n_dx[..., 1] *= -1.0
    return {"BC": M.to8(M.srgb_encode(s["bc_lin"])), "N": M.to8(n_dx * 0.5 + 0.5),
            "ORM": M.to8(np.stack([s["ao"], s["rough"], s["metal"]], -1)), "TeamMask": M.to8(s["cloth"]),
            "TeamMaskRGBA": M.to8(np.stack([s["cloth"], s["band"], s["emb"], np.ones_like(s["cloth"])], -1))}


def check_against_h21(state, src):
    """Per map: sha256 of the H2.1 4K master on disk = its textures-report entry, and the 8-bit map rebuilt here
    equals its pixels. Returns {map: {...}}."""
    rep = C.load_json(src.reports / "textures-report.json")["textures"]
    prefix = src["maps"]["prefix"]
    out = {}
    for key, arr in maps8(state).items():
        name = "%s_%s_4K.png" % (prefix, key)
        path = src.textures / name
        disk_sha = C.sha256(path)
        with Image.open(path) as img:
            ref = np.flipud(np.asarray(img))
        same = ref.shape == arr.shape and bool(np.array_equal(ref, arr))
        out[key] = {"file": C.rel(path), "sha256_matches_h21_report": disk_sha == rep[name]["sha256"],
                    "pixels_equal_rebuilt": same,
                    "max_abs_lsb": None if ref.shape != arr.shape else int(np.abs(ref.astype(np.int16) - arr.astype(np.int16)).max())}
    return out
