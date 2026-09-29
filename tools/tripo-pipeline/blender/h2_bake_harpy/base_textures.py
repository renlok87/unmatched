"""Procedural metal textures of the H2.1 Harpy base (system Python: numpy/scipy; deterministic, seeded).

    make(cfg, size) -> {"BC": uint8 HxWx3 (sRGB), "N_OpenGL": uint8, "N": uint8 (DirectX), "ORM": uint8, "stats": {...}}

Layout = base_gold.uv_layout (profile base_material.uv_layout): a band strip over the full width (v in band_v, tileable
in u because the noise is sampled on the circle), a top disc (top_centre_uv, top_radius_uv), the rest filled with the
top material. Materials (profile base_material.surfaces; proposal): "top" - antique gold/bronze, "band" - bright gold
(visible where BandKeepsTexture = 1; with the default flat team band only its ORM matters). Every surface: metallic 1,
roughness in [roughness_min, roughness_max] driven by a mottling field (brighter = more polished), a soft
hammered-leaf height field -> tangent normal (normal_strength), AO 1. Rows are written top row first like every PNG of
the pipeline (row 0 of the arrays here = v = 1).
"""

import numpy as np
from scipy import ndimage


def _srgb(lin):
    lin = np.clip(lin, 0.0, 1.0)
    return np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(lin, 1 / 2.4) - 0.055)


def _q8(x):
    return np.clip(np.round(np.clip(x, 0, 1) * 255.0), 0, 255).astype(np.uint8)


def _fbm_plane(rng, n, scales, weights):
    out = np.zeros((n, n))
    for s, w in zip(scales, weights):
        f = ndimage.gaussian_filter(rng.standard_normal((n, n)), s, mode="wrap")
        out += w * f / (f.std() + 1e-12)
    return out / (np.abs(out).max() + 1e-12)


def make(cfg, size):
    L = cfg["uv_layout"]
    S = cfg["surfaces"]
    rng = np.random.default_rng(int(cfg.get("seed", 0)))
    n = int(size)
    # texel centres in UV (v up), row 0 = v near 1
    u = (np.arange(n) + 0.5) / n
    v = 1.0 - (np.arange(n) + 0.5) / n
    U, V = np.meshgrid(u, v)
    band = (V >= L["band_v"][0] - 2.0 / n) & (V <= L["band_v"][1] + 2.0 / n)
    # mottling + hammer fields: generated tileable (wrap) so the band strip tiles in u
    mott = _fbm_plane(rng, n, (n / 64.0, n / 24.0, n / 8.0), (1.0, 0.6, 0.35))
    fine = _fbm_plane(rng, n, (1.5, 3.0), (0.6, 0.4))
    # hammered leaf: sparse soft dents
    dents = np.zeros((n, n))
    k = int(cfg.get("dents", 900) * (n / 1024.0) ** 2)
    ys, xs = rng.integers(0, n, k), rng.integers(0, n, k)
    np.add.at(dents, (ys, xs), rng.uniform(0.5, 1.0, k))
    dents = ndimage.gaussian_filter(dents, n / 160.0, mode="wrap")
    dents /= dents.max() + 1e-12
    height = -0.7 * dents + 0.25 * mott + 0.05 * fine
    bc = np.zeros((n, n, 3))
    rough = np.zeros((n, n))
    stats = {}
    for name, mask in (("top", ~band), ("band", band)):
        s = S[name]
        base = np.array(s["colour_linear"], np.float64)
        var = float(s.get("value_variation", 0.12))
        patina = np.array(s.get("patina_linear", s["colour_linear"]), np.float64)
        m = 0.5 + 0.5 * mott
        col = base[None, None, :] * (1.0 + var * mott[..., None]) * (1.0 + 0.04 * fine[..., None])
        pat = np.clip(-mott, 0, 1)[..., None] * float(s.get("patina_amount", 0.3))
        col = col * (1 - pat) + patina[None, None, :] * pat
        r = float(s["roughness_max"]) - (float(s["roughness_max"]) - float(s["roughness_min"])) * np.clip(m, 0, 1)
        r = r + 0.03 * fine
        r = np.clip(r, float(s["roughness_min"]), float(s["roughness_max"]))
        bc[mask] = col[mask]
        rough[mask] = r[mask]
        stats[name] = {"bc_linear_mean": [round(float(c), 4) for c in col[mask].mean(0)],
                       "roughness_mean": round(float(r[mask].mean()), 4),
                       "roughness_p1_p99": [round(float(np.percentile(r[mask], 1)), 4),
                                            round(float(np.percentile(r[mask], 99)), 4)],
                       "metallic": 1.0}
    # tangent normal (OpenGL: +X right = +u, +Y up = +v); height in texels scaled by normal_strength
    st = float(cfg.get("normal_strength", 1.5))
    gx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) * 0.5  # wrap: the band strip tiles in u
    gy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) * 0.5
    nx, ny = -gx * st, gy * st  # row index grows downward = -v, so d/dv = -d/drow
    nz = np.ones_like(nx)
    ln = np.sqrt(nx * nx + ny * ny + nz * nz)
    ngl = np.stack([nx / ln, ny / ln, nz / ln], -1)
    n8 = _q8(ngl * 0.5 + 0.5)
    ndx = n8.copy()
    ndx[..., 1] = 255 - ndx[..., 1]
    orm = np.stack([np.ones((n, n)), rough, np.ones((n, n))], -1)
    stats["normal_tilt_p99_deg"] = round(float(np.degrees(np.arccos(np.percentile(ngl[..., 2], 1)))), 2)
    return {"BC": _q8(_srgb(bc)), "N_OpenGL": n8, "N": ndx, "ORM": _q8(orm), "stats": stats}
