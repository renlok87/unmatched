"""TeamAccent of Merlin (look-dev v2, 2026-09-30): per-texel inputs at 4K, cached in work/ (system python).

The state is the H2.1 texel state rebuilt by lookdev_state.build() (checked against the H2.1 4K masters, as ld_maps)
plus what the accent rules need and ld_maps does not keep:
  tri      triangle index per covered texel (UV raster of work/uv/*.npz, all objects concatenated)
  nrm      3D face normal of that triangle (source frame, Tripo metres, Z up, face -Y), nearest covered texel in gutters
  area     3D area of a texel = triangle 3D area / its UV area in texels (source frame, m^2); 0 in gutters
  zones    soft zone weights of ld_maps (lookdev_maps.zone_weights), float32
The cache (work/lookdev/accent/state.npz, git-ignored) is keyed by the sha256 of the H2.1 textures-report and of the
look-dev ld-maps-report: a cache hit gives exactly the arrays of a fresh build (they are deterministic functions of
the same inputs). Row 0 of every array = v 0 (bottom), as maps.py.
"""

import hashlib
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import lookdev_maps as LM  # noqa: E402
import lookdev_state as S  # noqa: E402
from raster import raster  # noqa: E402

CACHE_VERSION = "merlin-accent-state/1"
KEEP_ZONES = ("wool", "embroidery", "belt", "buckle", "boots", "beard_wrap", "face_skin", "hands_skin", "beard",
              "wood", "crystal", "base")


def cache_key(prof, src):
    h = hashlib.sha256(CACHE_VERSION.encode())
    for p in (src.reports / "textures-report.json", prof.reports / "ld-maps-report.json"):
        h.update(C.sha256(p).encode())
    return h.hexdigest()


def _triangles(src, size):
    tri_map = np.full((size, size), -1, np.int32)
    nrm_all, area_all, uv_all = [], [], []
    off = 0
    for key in S.OBJECTS:
        z = np.load(src.work / "uv" / (key + ".npz"))
        uv = z["uv"]
        raster(uv, size, [((np.arange(len(uv)) + off).astype(np.int32), tri_map)])
        off += len(uv)
        nrm_all.append(z["normal"])
        area_all.append(z["area3d_m2"])
        uv_all.append(uv)
    uv = np.concatenate(uv_all)
    nrm = np.concatenate(nrm_all)
    area3d = np.concatenate(area_all)
    uv_px = 0.5 * np.abs((uv[:, 1, 0] - uv[:, 0, 0]) * (uv[:, 2, 1] - uv[:, 0, 1])
                         - (uv[:, 2, 0] - uv[:, 0, 0]) * (uv[:, 1, 1] - uv[:, 0, 1])) * size * size
    per_texel = np.where(uv_px > 0, area3d / np.maximum(uv_px, 1e-12), 0.0)
    return tri_map, nrm, per_texel


def build(prof, src):
    st = S.build(src)
    repro = S.check_against_h21(st, src)
    ok = all(v["sha256_matches_h21_report"] and v["pixels_equal_rebuilt"] for v in repro.values())
    if not ok:
        raise RuntimeError("H2.1 state not reproduced: %s" % repro)
    size = st["size"]
    cov = st["covered"]
    zw, _total = LM.zone_weights(st, prof["lookdev"], src)
    tri_map, nrm_t, area_t = _triangles(src, size)
    from scipy import ndimage
    _d, (jy, jx) = ndimage.distance_transform_edt(tri_map < 0, return_indices=True)
    tri_full = tri_map[jy, jx]
    nrm = nrm_t[tri_full].astype(np.float32)
    area = np.where(tri_map >= 0, area_t[np.maximum(tri_map, 0)], 0.0).astype(np.float32)
    h, s, v = st["hsv"]
    out = {"size": np.int32(size), "covered": cov, "part": st["part"].astype(np.int16),
           "island": st["island_raw"].astype(np.int32), "pos": st["pos"].astype(np.float32), "nrm": nrm,
           "area": area, "tri": tri_map, "bc_lin": st["bc_lin"].astype(np.float32),
           "hsv": np.stack([h, s, v], -1).astype(np.float32), "emb": st["emb"].astype(np.float32),
           "cloth": st["cloth"].astype(np.float32),
           "cls_leather_belt": st["cls"]["leather_belt"].astype(np.float32),
           "cls_metal_buckle": st["cls"]["metal_buckle"].astype(np.float32),
           "h21_reproduced": np.bool_(ok)}
    for k in KEEP_ZONES:
        out["zone_" + k] = zw[k].astype(np.float32)
    return out


def load(prof, src):
    """Returns (dict of arrays, {"cache": hit|built, "key": ...})."""
    cache = prof.work / "lookdev" / "accent" / "state.npz"
    key = cache_key(prof, src)
    if cache.exists():
        z = np.load(cache)
        if str(z["key"]) == key:
            return {k: z[k] for k in z.files if k != "key"}, {"cache": "hit", "key": key}
    data = build(prof, src)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, key=np.array(key), **data)
    return data, {"cache": "built", "key": key}
