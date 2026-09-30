"""TeamAccent through the mip chain (5c-B0, 2026-09-30): what a pixel of the board frames reads from the mask.

Look-dev C found in UE that the rev. 2 accent strip (14 mm around the gold borders of the cloak, the red cloth between the
braid threads included) turns the WHOLE border into the team colour once the mask and the BC are mip-filtered: the
threads are 1-2 texels wide, the mips average them with the dyed red between them. This module models the chain the
way UE builds and samples it and measures, per mip, how much of each class a pixel sees as "painted":

- the runtime mask = the 2K PNG (8 bit), mips generated from it as UE does: 2 x 2 box (TMGS_SimpleAverage, the default
  of the texture group) or a Kaiser-windowed sinc (the Sharpen/Kaiser family, as the alternative);
- the value of a 2K texel at mip L = bilinear sample of mip L at the texel's UV (the hardware filter inside a mip);
- painted = value >= threshold (0.25: a quarter of the bright team colour mixed into the dark red cloth or the gold
  braid is visible); shares weighted by the 3D texel area of the POS bake.

Pure numpy / scipy; used by ld_maps (check team_accent_mip_chain) and by the 5c-B0 comparison.
"""

import numpy as np
from scipy import ndimage


def box_down(x):
    return x.reshape(x.shape[0] // 2, 2, x.shape[1] // 2, 2).mean(axis=(1, 3))


def kaiser_kernel(beta=4.0, half=4):
    """2 x decimation taps: output i sits at input 2i + 0.5, taps at the input texel centres d = +-0.5 ... +-(half - 0.5);
    weight = sinc(d / 2) x Kaiser window, normalised."""
    d = np.arange(-half, half) + 0.5
    win = np.kaiser(2 * half + 1, beta)[np.round(d + half).astype(int).clip(0, 2 * half)]
    w = np.sinc(d / 2.0) * win
    return w / w.sum()


def kaiser_down(x, beta=4.0, half=4):
    k = kaiser_kernel(beta, half)

    def along(a, axis):
        a = np.moveaxis(a, axis, 0)
        pad = np.pad(a, ((half, half),) + ((0, 0),) * (a.ndim - 1), mode="edge")
        n = a.shape[0] // 2
        out = np.zeros((n,) + a.shape[1:], np.float64)
        for j, wj in enumerate(k):
            out += wj * pad[j + 1: j + 1 + 2 * n: 2]
        return np.moveaxis(out, 0, axis)

    return np.clip(along(along(x.astype(np.float64), 0), 1), 0.0, 1.0)


def chain(x, levels, kind="box"):
    out = [np.asarray(x, np.float64)]
    down = box_down if kind == "box" else kaiser_down
    for _ in range(levels):
        out.append(down(out[-1]))
    return out


def sample_at(img, size):
    """Bilinear value of a mip at the UV of every texel centre of a size x size grid (separable, clamp at the edge)."""
    s = img.shape[0] / float(size)
    if s == 1.0:
        return img
    c = (np.arange(size) + 0.5) * s - 0.5
    tmp = ndimage.map_coordinates(img, np.meshgrid(c, np.arange(img.shape[1]), indexing="ij"), order=1, mode="nearest")
    return ndimage.map_coordinates(tmp, np.meshgrid(np.arange(size), c, indexing="ij"), order=1, mode="nearest")


def painted_shares(mask2k, classes, weights, levels=4, threshold=0.25, kinds=("box", "kaiser"), core=None):
    """mask2k: runtime mask in [0, 1] (the 8-bit PNG / 255); classes: {name: bool 2K}; weights: 2K texel area.
    -> {kind: [{mip, px, <class>: painted share, core_median}]}"""
    size = mask2k.shape[0]
    out = {}
    for kind in kinds:
        rows = []
        for lv, img in enumerate(chain(mask2k, levels, kind)):
            e = sample_at(img, size)
            row = {"mip": lv, "px": int(img.shape[0])}
            for name, sel in classes.items():
                w = weights[sel]
                row[name] = round(float((w * (e[sel] >= threshold)).sum() / max(float(w.sum()), 1e-12)), 4)
            if core is not None and core.any():
                row["accent_core_median"] = round(float(np.median(e[core])), 3)
            rows.append(row)
        out[kind] = rows
    return out


def visible_mips(texel_m, figure_px_per_m, pitch_deg=55.0, bias=0.0):
    """Mip level a facing / a vertical surface reads on a K2 camera: log2(pixel footprint / texel size); the vertical
    surface seen from pitch_deg (camera looking down) is foreshortened by 1 / cos(pitch) along one axis (the upper bound
    without anisotropic filtering; with it the minor axis = the facing value decides)."""
    fp = 1.0 / figure_px_per_m
    face = float(np.log2(fp / texel_m)) + bias
    vert = float(np.log2(fp / np.cos(np.radians(pitch_deg)) / texel_m)) + bias
    return {"pixel_mm": round(fp * 1e3, 3), "mip_facing": round(face, 2), "mip_vertical_no_aniso": round(vert, 2)}
