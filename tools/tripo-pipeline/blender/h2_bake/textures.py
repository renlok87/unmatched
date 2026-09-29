"""Stage textures (plain Python: numpy + Pillow; no bpy): composites of the bake stage -> final PNG maps.

Inputs  work/bake/{NORMAL,AO,BC,RM,HIT}.npy (+ _alpha), work/uv/{island_ids,part_ids,base_band}.npy
Outputs textures/<prefix>_{BC,N,N_OpenGL,ORM,TeamMask}.png (4K master) and <prefix>_2K_{...}.png (runtime),
        reports/textures-report.json

Fill: texels inside the UV islands that got no bake hit and the whole background are filled from the baked
texels: `edge_px` steps of 8-neighbour dilation (edge extension: mips/bilinear never read black) and then a
pull-push pyramid for the remaining background. Normals are filled in vector space and renormalised.
Runtime 2K = exact 2x2 box average of the 8-bit 4K maps (the first mip), normals renormalised.
Contact footprints first (work/uv/footprints.npz): BC, RM and AO of the faces hidden at rest under a covering part
are repainted from the visible surface around them (their normals stay baked). Then caps (work/uv/caps.npz,
cap_ids.npy; close stage): their texels are not taken from the bake (no high-poly surface behind a cap). BC, RM and
AO of every cap vertex = its rim samples (bilinear, from the composites without the cap texels, 4-step dilation for
cage-miss specks) combined with the uv-stage weights, interpolated over the cap triangles (barycentric); the
tangent-space normal of a cap is flat (0.5, 0.5, 1). The composites are then filled with the cap texels as valid.
H2.1 (profile textures.materials, module materials.py): AO of the listed parts from work/bake/AO_EX.npy (stage aux)
before the footprints/caps read their rim; rim filters of named contacts (keep only the rim samples of the surface
that continues under the contact); after the caps, the metal mask and the BC/ORM remap (metal, cloth roughness).
Without textures.materials the stage is the H2 stage unchanged.
PNG writing: Pillow, compress_level 6, no metadata -> identical bytes for identical pixels."""

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

SHIFTS = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def sha256(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def shift(a, dy, dx):
    out = np.zeros_like(a)
    h, w = a.shape[:2]
    ys, yd = slice(max(dy, 0), h + min(dy, 0)), slice(max(-dy, 0), h + min(-dy, 0))
    xs, xd = slice(max(dx, 0), w + min(dx, 0)), slice(max(-dx, 0), w + min(-dx, 0))
    out[yd, xd] = a[ys, xs]
    return out


def dilate(values, valid, steps):
    """Edge extension: each step, an invalid texel with valid 8-neighbours takes their mean."""
    v = values.copy()
    ok = valid.copy()
    for _ in range(steps):
        acc = np.zeros_like(v)
        cnt = np.zeros(ok.shape, np.float32)
        for dy, dx in SHIFTS:
            m = shift(ok, dy, dx)
            acc += shift(v, dy, dx) * m[..., None]
            cnt += m
        grow = (~ok) & (cnt > 0)
        if not grow.any():
            break
        v[grow] = acc[grow] / cnt[grow][:, None]
        ok = ok | grow
    return v, ok


def pull_push(values, valid):
    """Fill every invalid texel from a coverage-weighted image pyramid (deterministic, smooth)."""
    levels = [(values * valid[..., None], valid.astype(np.float32))]
    while levels[-1][1].shape[0] > 1:
        v, w = levels[-1]
        h2 = v.shape[0] // 2
        v2 = v.reshape(h2, 2, h2, 2, -1).sum((1, 3))
        w2 = w.reshape(h2, 2, h2, 2).sum((1, 3))
        levels.append((v2, w2))
    v, w = levels[-1]
    filled = v / np.maximum(w, 1e-12)[..., None]
    for v, w in reversed(levels[:-1]):
        up = np.repeat(np.repeat(filled, 2, 0), 2, 1)
        own = v / np.maximum(w, 1e-12)[..., None]
        filled = np.where((w > 0)[..., None], own, up)
    out = values.copy()
    out[~valid] = filled[~valid]
    return out


def fill(values, valid, edge_px):
    v, ok = dilate(values, valid, edge_px)
    return pull_push(v, ok)


def bilinear(img, px):
    """img [H, W, C] (row 0 = v 0), px [S, 2] atlas pixel coordinates (x = u * size, y = v * size)."""
    h, w = img.shape[:2]
    x = np.clip(px[:, 0] - 0.5, 0.0, w - 1.0)
    y = np.clip(px[:, 1] - 0.5, 0.0, h - 1.0)
    x0 = np.floor(x).astype(np.int64)
    y0 = np.floor(y).astype(np.int64)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return ((img[y0, x0] * (1 - fx) + img[y0, x1] * fx) * (1 - fy) + (img[y1, x0] * (1 - fx) + img[y1, x1] * fx) * fy)


def raster_bary(tri_px, size):
    """Pixel centres inside each triangle (inclusive edges, the rule of bl_util.raster_triangles):
    (ys, xs, triangle index, barycentrics [N, 3])."""
    out_y, out_x, out_t, out_b = [], [], [], []
    for t in range(len(tri_px)):
        a, b, c = tri_px[t]
        x0 = max(int(np.floor(min(a[0], b[0], c[0]))), 0)
        x1 = min(int(np.ceil(max(a[0], b[0], c[0]))), size - 1)
        y0 = max(int(np.floor(min(a[1], b[1], c[1]))), 0)
        y1 = min(int(np.ceil(max(a[1], b[1], c[1]))), size - 1)
        if x1 < x0 or y1 < y0:
            continue
        X, Y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / d
        l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / d
        l3 = 1.0 - l1 - l2
        inside = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not inside.any():
            continue
        out_y.append((Y[inside] - 0.5).astype(np.int64))
        out_x.append((X[inside] - 0.5).astype(np.int64))
        out_t.append(np.full(int(inside.sum()), t, np.int64))
        out_b.append(np.stack([l1[inside], l2[inside], l3[inside]], 1))
    if not out_y:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros((0, 3))
    return np.concatenate(out_y), np.concatenate(out_x), np.concatenate(out_t), np.concatenate(out_b)


def region_paint(maps, alpha, region, exclude, keys=("BC", "RM", "AO")):
    """Paints the texels of the region triangles (in place) from their rim samples; returns (painted mask, stats)."""
    size = exclude.shape[0]
    ys, xs, ts, bary = raster_bary(region["tri_px"], size)
    last = {}
    for k, (y, x) in enumerate(zip(ys.tolist(), xs.tolist())):
        last[(y, x)] = k
    keep = np.array(sorted(last.values()), np.int64)
    ys, xs, ts, bary = ys[keep], xs[keep], ts[keep], bary[keep]
    painted = np.zeros((size, size), bool)
    painted[ys, xs] = True
    nv = int(region["n_vertices"])
    for key in keys:
        pre, _ok = dilate(maps[key], alpha[key] & ~exclude, 4)
        samples = bilinear(pre, region["samp_px"])
        vert = np.zeros((nv, samples.shape[1]))
        np.add.at(vert, region["w_rows"], region["w_vals"][:, None] * samples[region["w_cols"]])
        maps[key][ys, xs] = (vert[region["tri_v"][ts]] * bary[..., None]).sum(1)
    return painted, {"painted_texels": int(painted.sum()), "vertices": nv, "rim_samples": int(len(region["samp_px"])),
                     "triangles": int(len(region["tri_px"]))}


def cap_fill(maps, alpha, caps, cap_mask, edge_px):
    """Overwrites the cap texels of maps (in place) from their rim; returns (valid masks, stats)."""
    ys, xs, ts, bary = raster_bary(caps["tri_px"], cap_mask.shape[0])
    last = {}
    for k, (y, x) in enumerate(zip(ys.tolist(), xs.tolist())):
        last[(y, x)] = k  # a pixel centre on a shared edge: the later triangle wins (as in raster_triangles)
    keep = np.array(sorted(last.values()), np.int64)
    ys, xs, ts, bary = ys[keep], xs[keep], ts[keep], bary[keep]
    painted = np.zeros(cap_mask.shape, bool)
    painted[ys, xs] = True
    nv = int(caps["n_vertices"])
    valid = {}
    for key in ("BC", "RM", "AO"):
        base_valid = alpha[key] & ~cap_mask
        pre, _ok = dilate(maps[key], base_valid, 4)  # rim samples lie inside baked rim faces: close cage-miss specks only
        samples = bilinear(pre, caps["samp_px"])
        vert = np.zeros((nv, samples.shape[1]))
        np.add.at(vert, caps["w_rows"], caps["w_vals"][:, None] * samples[caps["w_cols"]])
        tv = caps["tri_v"][ts]
        maps[key][ys, xs] = (vert[tv] * bary[..., None]).sum(1)
        valid[key] = base_valid | painted
    maps["NORMAL"][ys, xs] = np.array([0.5, 0.5, 1.0], np.float32)
    valid["NORMAL"] = (alpha["NORMAL"] & ~cap_mask) | painted
    return valid, {"cap_texels": int(cap_mask.sum()), "painted_texels": int(painted.sum()),
                   "cap_texels_not_painted": int((cap_mask & ~painted).sum()),
                   "painted_outside_cap_raster": int((painted & ~cap_mask).sum()),
                   "cap_vertices": nv, "rim_samples": int(len(caps["samp_px"])), "cap_triangles": int(len(caps["tri_px"]))}


def box2(a):
    h = a.shape[0] // 2
    return a.reshape(h, 2, h, 2, *a.shape[2:]).mean((1, 3))


def renorm_encoded(n_enc):
    n = n_enc * 2.0 - 1.0
    n[..., 2] = np.maximum(n[..., 2], 1e-4)
    n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-8)
    return n * 0.5 + 0.5


def to8(a):
    return np.clip(np.floor(np.clip(a, 0.0, 1.0) * 255.0 + 0.5), 0, 255).astype(np.uint8)


def save_png(arr8, path, mode):
    img = Image.fromarray(arr8[::-1], mode)  # row 0 of the arrays = v 0 (bottom): flip to image order
    img.save(path, format="PNG", compress_level=6)
    return {"sha256": sha256(path), "bytes": path.stat().st_size, "px": [arr8.shape[1], arr8.shape[0]], "mode": mode}


def rgb_to_hsv(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-8), 0.0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    dd = np.maximum(d, 1e-9)
    h = np.where(mx == r, ((g - b) / dd) % 6, np.where(mx == g, (b - r) / dd + 2, (r - g) / dd + 4)) * 60.0
    h = np.where(d > 1e-9, h, 0.0)
    return h, s, mx


def smooth_le(x, edge, ramp):
    t = np.clip((edge + ramp - x) / (2 * ramp), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def blur3(a, n):
    for _ in range(n):
        acc = a.copy()
        for dy, dx in SHIFTS:
            acc += shift(a, dy, dx)
        a = acc / 9.0
    return a


def load_sibling(name):
    spec = importlib.util.spec_from_file_location("h2_" + name, Path(__file__).resolve().parent / (name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def contact_labels(run_dir, part_names, names):
    """Labels (part index * 1000 + cap index, the uv-stage encoding) of named contact caps (close-report.json)."""
    close = json.loads((Path(run_dir) / "reports" / "close-report.json").read_text(encoding="utf-8"))
    out = []
    for n in names:
        rec = next(c for c in close["caps"] if c["name"] == n)
        out.append(part_names.index(rec["part"]) * 1000 + int(rec["cap_index"]))
    return out


def run(run_dir, profile):
    run_dir = Path(run_dir)
    w = run_dir / "work"
    tcfg = profile["textures"]
    prefix = tcfg["prefix"]
    edge_px = int(tcfg.get("edge_extend_px", 16))
    part_names = sorted(profile["parts"], key=lambda n: int(n.split("_")[-1]))
    part_ids = np.load(w / "uv" / "part_ids.npy")
    base_band = np.load(w / "uv" / "base_band.npy").astype(bool)
    uv_cov = part_ids >= 0
    maps = {k: np.load(w / "bake" / ("%s.npy" % k)).astype(np.float32) for k in ("NORMAL", "AO", "BC", "RM")}
    alpha = {k: np.load(w / "bake" / ("%s_alpha.npy" % k)).astype(bool) for k in ("NORMAL", "AO", "BC", "RM", "HIT")}
    size = part_ids.shape[0]
    stats = {"size": size, "uv_texels": int(uv_cov.sum()),
             "baked_texels": {k: int(v.sum()) for k, v in alpha.items()},
             "in_island_unbaked_texels": {k: int((uv_cov & ~alpha[k]).sum()) for k in alpha}}
    cap_path = w / "uv" / "caps.npz"
    cap_mask = np.load(w / "uv" / "cap_ids.npy") > 0 if (w / "uv" / "cap_ids.npy").exists() else np.zeros_like(uv_cov)
    cap_stats = None
    mcfg = tcfg.get("materials")
    mat = load_sibling("materials") if mcfg else None
    tx = SimpleNamespace(rgb_to_hsv=rgb_to_hsv, bilinear=bilinear, dilate=dilate, blur3=blur3)
    mstats = {}
    if mcfg and mcfg.get("ao_exclusions"):
        mstats["ao_exclusions"] = mat.ao_exclusions(maps, alpha, part_ids, part_names, run_dir, mcfg["ao_exclusions"])
    rim_filters = (mcfg or {}).get("rim_filters", [])
    fp_path = w / "uv" / "footprints.npz"
    fp_stats = None
    if fp_path.exists():
        fp = dict(np.load(fp_path))
        if len(fp["tri_px"]):
            if rim_filters:
                fp, mstats["rim_filters_footprints"] = mat.filter_rim(
                    fp, maps, alpha, cap_mask, contact_labels(run_dir, part_names, [f["contact"] for f in rim_filters]),
                    [f["keep_hsv"] for f in rim_filters], tx)
            _painted, fp_stats = region_paint(maps, alpha, fp, cap_mask)
    stats["footprints"] = fp_stats
    valid_maps = {k: alpha[k] for k in ("NORMAL", "AO", "BC", "RM")}
    if cap_path.exists() and cap_mask.any():
        caps = dict(np.load(cap_path))
        if rim_filters:
            caps, mstats["rim_filters_caps"] = mat.filter_rim(
                caps, maps, alpha, cap_mask, contact_labels(run_dir, part_names, [f["contact"] for f in rim_filters]),
                [f["keep_hsv"] for f in rim_filters], tx)
        valid_maps, cap_stats = cap_fill(maps, alpha, caps, cap_mask, edge_px)
    stats["caps"] = cap_stats
    metal_m = None
    if mcfg and mcfg.get("metal"):
        pos = np.load(w / "uv" / "position.npy")
        vb = valid_maps["BC"] & uv_cov
        metal_m, mstats["metal_mask"] = mat.metal_mask(maps["BC"], vb, part_ids, part_names, pos, mcfg["metal"], tx)
        del pos
        cloth_w = mat.cloth_weight(maps["BC"], part_ids, part_names, tcfg["team_mask"], tx) * (1.0 - metal_m)
        mstats["remap"] = mat.remap(maps, vb & valid_maps["RM"], metal_m, cloth_w, mcfg)
    filled = {}
    for k in ("NORMAL", "AO", "BC", "RM"):
        filled[k] = fill(maps[k], valid_maps[k], edge_px)
    filled["NORMAL"] = renorm_encoded(filled["NORMAL"])
    # ---- TeamMask (R clothing, G base band) from the filled BC
    tm = tcfg["team_mask"]
    cloth_idx = [part_names.index(p) for p in tm["cloth_parts"]]
    in_cloth = np.isin(part_ids, cloth_idx)
    h, s, v = rgb_to_hsv(filled["BC"])
    hsv = tm["cloth_hsv"]
    r = smooth_le(v, hsv["v_max"], hsv["ramp"]) * smooth_le(s, hsv["s_max"], hsv["ramp"])
    r = np.where(in_cloth, r, 0.0).astype(np.float32)
    r = blur3(r, int(tm.get("blur", 0))) * in_cloth
    g = base_band.astype(np.float32)
    team = np.stack([r, g, np.zeros_like(r)], -1)
    team_valid = uv_cov
    team = fill(team, team_valid, edge_px)
    filled["TeamMask"] = team
    cloth_share = float(r[in_cloth].mean()) if in_cloth.any() else 0.0
    # ---- 8-bit maps (4K) and runtime 2K
    tex_dir = run_dir / "textures"
    tex_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}

    def write(name, arr8, mode):
        path = tex_dir / ("%s_%s.png" % (prefix, name))
        outputs[path.name] = save_png(arr8, path, mode)
        return path

    def maps8(f):
        n_gl = to8(f["NORMAL"])
        n_dx = n_gl.copy()
        n_dx[..., 1] = 255 - n_gl[..., 1]
        orm = np.stack([to8(f["AO"][..., 0]), to8(f["RM"][..., 1]), to8(f["RM"][..., 2])], -1)
        tmk = np.concatenate([to8(f["TeamMask"][..., :3]), np.full(f["TeamMask"].shape[:2] + (1,), 255, np.uint8)], -1)
        return {"BC": to8(f["BC"]), "N": n_dx, "N_OpenGL": n_gl, "ORM": orm, "TeamMask": tmk}

    m4 = maps8(filled)
    for name, arr in m4.items():
        write(name, arr, "RGBA" if name == "TeamMask" else "RGB")
    # runtime 2K from the 8-bit 4K maps (not from the float composites): identical 4K bytes give identical 2K bytes
    # (the float normal bake carries ~2e-7 noise between runs; a float box filter flipped 1 value of 12.6 M, measured)
    q = lambda a: a.astype(np.float32) / 255.0
    half = {"BC": box2(q(m4["BC"])), "AO": box2(q(m4["ORM"][..., :1])), "RM": box2(q(m4["ORM"])),
            "TeamMask": box2(q(m4["TeamMask"][..., :3])), "NORMAL": renorm_encoded(box2(q(m4["N_OpenGL"])))}
    half["RM"] = np.stack([np.zeros_like(half["RM"][..., 0]), half["RM"][..., 1], half["RM"][..., 2]], -1)
    m2 = maps8(half)
    for name, arr in m2.items():
        write("2K_" + name, arr, "RGBA" if name == "TeamMask" else "RGB")
    # ---- checks
    checks = {}
    for tag, m in (("4k", m4), ("2k", m2)):
        checks["dx_equals_opengl_g_inverted_%s" % tag] = {
            "passed": bool(np.array_equal(m["N"][..., 1], 255 - m["N_OpenGL"][..., 1])
                           and np.array_equal(m["N"][..., ::2], m["N_OpenGL"][..., ::2])), "measured": "exact"}
        dec = m["N_OpenGL"].astype(np.float32) / 127.5 - 1.0
        ln = np.linalg.norm(dec, axis=-1)
        checks["normal_length_%s" % tag] = {"passed": bool(np.percentile(np.abs(ln - 1), 99.9) < 0.02),
                                             "measured": {"p50": round(float(np.median(ln)), 4),
                                                          "p99.9_abs_dev": round(float(np.percentile(np.abs(ln - 1), 99.9)), 4)},
                                             "expected": "|len - 1| p99.9 < 0.02"}
    gate = tcfg["ao_gate"]
    ao_in = m4["ORM"][..., 0][uv_cov]
    p1, p99 = np.percentile(ao_in, 1), np.percentile(ao_in, 99)
    occl = float((ao_in < gate["occluded_below"]).mean())
    checks["orm_occlusion_baked_not_constant"] = {
        "passed": bool(p99 - p1 >= gate["min_range_p1_p99"] and occl >= gate["min_occluded_fraction"]),
        "measured": {"p1": float(p1), "p99": float(p99), "occluded_fraction": round(occl, 4)},
        "expected": {"p99_minus_p1_min": gate["min_range_p1_p99"], "occluded_fraction_min": gate["min_occluded_fraction"]}}
    real = uv_cov & ~cap_mask
    missing = {k: int((real & ~alpha[k]).sum()) for k in ("NORMAL", "AO", "BC", "RM")}
    checks["in_island_unbaked_share"] = {"passed": all(v <= 0.01 * real.sum() for v in missing.values()),
                                         "measured": {k: round(v / real.sum(), 6) for k, v in missing.items()},
                                         "expected": "<= 1 % of the non-cap island texels (filled by dilation from baked "
                                                     "neighbours; cap texels are filled from their rim)"}
    if cap_stats is not None:
        checks["cap_texels_filled_from_rim"] = {
            "passed": cap_stats["cap_texels_not_painted"] == 0 and cap_stats["painted_outside_cap_raster"] == 0,
            "measured": cap_stats, "expected": "every cap texel of the uv raster painted, none outside"}
    checks["team_mask_cloth_share"] = {"passed": 0.5 <= cloth_share <= 0.98, "measured": round(cloth_share, 4),
                                       "expected": "0.5..0.98 of the cloth part's texels (gold trim, belt, strap stay out)"}
    if metal_m is not None:  # H2.1: measured on the written 8-bit 4K maps
        ck = mcfg.get("checks", {})
        core = (metal_m >= 0.99) & uv_cov
        other = (metal_m <= 0) & uv_cov & valid_maps["RM"]  # no metal influence (the 3x3 edge blur excluded)
        met8 = m4["ORM"][..., 2]
        rough8 = m4["ORM"][..., 1].astype(np.float32) / 255.0
        bc_lin_max = mat.lin(m4["BC"][core].astype(np.float32) / 255.0).max(-1)
        lo_r, hi_r = ck.get("metal_core_roughness", [0.3, 0.46])
        checks["h21_metal_core_metallic"] = {
            "passed": bool(np.percentile(met8[core], 1) / 255.0 >= ck.get("metal_core_metallic_min", 0.89)),
            "measured": {"texels": int(core.sum()), "p1": round(float(np.percentile(met8[core], 1)) / 255.0, 4),
                         "median": round(float(np.median(met8[core])) / 255.0, 4)},
            "expected": "metal core (mask >= 0.99): metallic p1 >= %s" % ck.get("metal_core_metallic_min", 0.89)}
        checks["h21_metal_core_roughness"] = {
            "passed": bool(np.percentile(rough8[core], 1) >= lo_r and np.percentile(rough8[core], 99) <= hi_r),
            "measured": {"p1": round(float(np.percentile(rough8[core], 1)), 4), "p50": round(float(np.median(rough8[core])), 4),
                         "p99": round(float(np.percentile(rough8[core], 99)), 4)},
            "expected": "metal core roughness p1..p99 within %s..%s (varied, not a constant)" % (lo_r, hi_r)}
        checks["h21_non_metal_metallic_zero"] = {
            "passed": bool(met8[other].max() <= ck.get("non_metal_metallic_max_8bit", 1)),
            "measured": {"texels": int(other.sum()), "max_8bit": int(met8[other].max())},
            "expected": "cloth, skin, leather, wood, snakes, base (mask 0): metallic <= %d/255" % ck.get("non_metal_metallic_max_8bit", 1)}
        checks["h21_metal_basecolor_plausible"] = {
            "passed": bool(np.median(bc_lin_max) >= ck.get("metal_core_bc_linear_max_channel_p50_min", 0.5)),
            "measured": {"linear_max_channel_p5_p50_p95": [round(float(x), 4) for x in np.percentile(bc_lin_max, [5, 50, 95])],
                         "srgb_mean": [round(float(x), 1) for x in m4["BC"][core].mean(0)]},
            "expected": "metal BaseColor = reflectance: linear max channel median >= %s (cavities darker by the Tripo detail)"
                        % ck.get("metal_core_bc_linear_max_channel_p50_min", 0.5)}
        rf = mstats.get("rim_filters_caps", []) + mstats.get("rim_filters_footprints", [])
        checks["h21_rim_filters_applied"] = {
            "passed": all(r["vertices"] > 0 and r["rim_samples_kept"] > 0 for r in mstats.get("rim_filters_caps", [])),
            "measured": [{k: r[k] for k in ("label", "vertices", "rim_samples", "rim_samples_kept", "vertices_without_kept_sample")
                          if k in r} for r in rf],
            "expected": "every filtered contact cap found, with kept rim samples"}
    for tag, m, sz in (("4k", m4, size), ("2k", m2, size // 2)):
        checks["sizes_%s" % tag] = {"passed": all(a.shape[0] == a.shape[1] == sz for a in m.values()), "measured": sz}
    bc_in = m4["BC"][uv_cov].astype(np.float64)
    report = {"stage": "textures", "prefix": prefix, "edge_extend_px": edge_px,
              "fill": "8-neighbour dilation %d px, then pull-push pyramid" % edge_px, "stats": stats,
              "bc_mean_srgb_in_islands": [round(x, 2) for x in bc_in.mean(0)],
              "team_mask": {"format": "RGBA: R = clothing (TeamColor), G = base side band, B = 0, A = 255",
                            "cloth_parts": tm["cloth_parts"], "hsv": hsv, "cloth_share_of_cloth_texels": round(cloth_share, 4),
                            "base_band_texels": int(base_band.sum())},
              "outputs": outputs, "checks": checks, "passed": all(c["passed"] for c in checks.values()), "status": "измерено"}
    if mcfg:
        report["materials"] = {"config": mcfg, "stats": mstats,
                               "note": "H2.1: маска металла и перенастройка BC/ORM (materials.py); статус — измерено, "
                                       "художественно не принято"}
    if metal_m is not None:
        np.save(w / "uv" / "metal_mask.npy", metal_m.astype(np.float32))
    out = run_dir / "reports" / "textures-report.json"
    out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("textures checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
    return report


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--profile", required=True)
    a = ap.parse_args()
    run(a.run_dir, json.loads(Path(a.profile).read_text(encoding="utf-8")))
    print("H2_TEXTURES_OK")
