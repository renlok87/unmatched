"""H2.1 material pass (system python, numpy/scipy): metal mask and PBR values by material class, from the painted BC
(Tripo texture + phantom repaint), the Tripo part of every texel and its Tripo-frame position (POS bake).

Why: Tripo's metallicRoughness map gave the armour almost no metal (metallic mean 0.074 over the atlas, > 0.5 on
0.27 % of the texels): the plate, the crown, the sword and the gold trims rendered as paint. The concept reads them
as steel and gold.

Classes (profile textures.materials; soft weights 0..1, sRGB HSV of the painted BC, smoothstep ramps, no hard edges):
  red       hue window around red, saturation ramp: cloak/tabard cloth, the red collar lining, red gems
  gold      hue window yellow-orange, saturation and value ramps
  leather   brown (hue window, saturation ramp, dark value) inside configured Tripo-frame regions (the belt)
  metal     per part group:
              armour  metal by default: 1 - red - leather (steel where not gold, gold where gold)
              cloth   non-metal by default: metal = gold (the gold embroidery and borders on the red cloth)
              head    non-metal (skin, hair, beard): metal = strict gold inside the crown / neck-ring regions
              stone   never metal (the base)
Metal values (PBR: a metal's base colour is its specular reflectance F0):
  steel BC  neutral grey L * ((1 - k) + k * chroma): L = target * (lum / ref)^gamma, clamped; ref = median luminance of
            the steel core texels of the group (measured, in the report); the painted luminance detail (engraving,
            mail, wear) survives as a compressed contrast
  gold BC   L * chroma, chroma = the texel's chromaticity mixed toward a reference gold chromaticity (luminance 1)
  roughness steel / gold ranges; inside a range, cavities (darker than ref) rougher, raised/bright texels smoother
Non-metal: base colour unchanged (the painted colour), metallic 0, roughness = Tripo roughness clamped to the class
range (cloth / leather / head / stone). Deterministic (numpy only).
"""

import numpy as np
from scipy import ndimage

import pure as P

LUM = np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
STEEL_PLATE_RGB = (150, 175, 210)       # class raster colours (steelcheck.py reads the plate colour)
STEEL_OVERRIDE_RGB = (200, 240, 235)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, 12.92 * x, 1.055 * np.power(x, 1 / 2.4) - 0.055)


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ramp(x, a, b):
    return smoothstep((x - a) / (b - a)).astype(np.float32)


def hsv(bc_lin):
    rgb = srgb(bc_lin).astype(np.float32)
    mx = rgb.max(axis=-1)
    mn = rgb.min(axis=-1)
    d = mx - mn
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    h = np.zeros_like(mx)
    m = d > 1e-6
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    h *= 60.0
    s = np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0).astype(np.float32)
    return h, s, mx


def hue_window(h, lo, hi, soft):
    """1 inside the hue interval [lo, hi] (degrees, wraps when lo > hi), smoothstep to 0 over `soft` degrees."""
    width = (hi - lo) % 360.0
    centre = (lo + width / 2.0) % 360.0
    dist = np.abs(((h - centre + 180.0) % 360.0) - 180.0) - width / 2.0
    return (1.0 - smoothstep(dist / soft)).astype(np.float32)


def colour_weight(h, s, v, rule):
    w = hue_window(h, rule["hue_deg"][0], rule["hue_deg"][1], rule.get("hue_soft_deg", 6.0))
    if "s_ramp" in rule:
        w = w * ramp(s, *rule["s_ramp"])
    if "v_ramp" in rule:
        w = w * ramp(v, *rule["v_ramp"])
    if "v_max_ramp" in rule:
        w = w * (1.0 - ramp(v, *rule["v_max_ramp"]))
    return w


def region_weight(pos, reg):
    """Soft Tripo-frame region: optional box (min_m/max_m) and z limits, smoothstep over feather_m outside."""
    f = float(reg.get("feather_m", 0.003))
    w = np.ones(pos.shape[:-1], dtype=np.float32)
    if "min_m" in reg:
        lo, hi = np.array(reg["min_m"]), np.array(reg["max_m"])
        out = np.linalg.norm(np.maximum(np.maximum(lo - pos, pos - hi), 0.0), axis=-1)
        w = w * (1.0 - smoothstep(out / f))
    if "z_min_m" in reg:
        w = w * ramp(pos[..., 2], float(reg["z_min_m"]) - f, float(reg["z_min_m"]))
    if "z_max_m" in reg:
        w = w * (1.0 - ramp(pos[..., 2], float(reg["z_max_m"]), float(reg["z_max_m"]) + f))
    return w.astype(np.float32)


def steel_params(st, overrides, pid, names):
    """Per-texel steel parameters: the plate values of metal.steel, replaced on the texels of the parts listed in
    metal.steel_part_overrides (every key the override omits falls back to the plate value). float32 arrays (H, W),
    tint (H, W, 3) luminance-normalised, tinted = texels with a tint other than neutral."""
    def one(c):
        tint = np.array(c.get("tint_linear", [1.0, 1.0, 1.0]), dtype=np.float32)
        return {"target": float(c["bc_target_linear"]), "gamma": float(c["gamma"]), "lo": float(c["bc_clamp"][0]),
                "hi": float(c["bc_clamp"][1]), "chroma_keep": float(c.get("chroma_keep", 0.0)),
                "r_lo": float(c["roughness"][0]), "r_hi": float(c["roughness"][1]),
                "dr_lo": float(c["roughness_detail_ratio"][0]), "dr_hi": float(c["roughness_detail_ratio"][1]),
                "tint": tint / float(tint @ LUM), "tinted": bool(np.any(tint != tint[0]))}
    base = one(st)
    # dtypes as the H2.1 scalar arithmetic: the detail ratio in float64, the roughness span computed in double
    f64 = ("dr_lo", "dr_hi")
    base["r_span"] = base["r_hi"] - base["r_lo"]
    out = {k: np.full(pid.shape, v, dtype=np.float64 if k in f64 else np.float32)
           for k, v in base.items() if k not in ("tint", "tinted")}
    out["tint"] = np.broadcast_to(base["tint"], pid.shape + (3,)).copy()
    out["tinted"] = np.full(pid.shape, base["tinted"], dtype=bool)
    for part, ov in sorted(overrides.items()):
        if part not in names:
            continue
        m = pid == names.index(part) + 1
        o = one({**st, **ov})
        o["r_span"] = o["r_hi"] - o["r_lo"]
        for k in out:
            out[k][m] = o[k]
    return out


def pct(x, qs=(10, 50, 90), nd=4):
    if len(x) == 0:
        return None
    return [P.r(v, nd) for v in np.percentile(x, qs)]


def apply_materials(bc, mr, pid, names, pos, covered, cfg):
    """bc: painted linear BC (H, W, 3); mr: Tripo MR bake (G roughness, B metallic). Returns (bc, mr, report,
    classes) - new arrays; classes: dict of float32 class weights for the inspection raster."""
    h, s, v = hsv(bc)
    lum = (bc @ LUM).astype(np.float32)
    rules = cfg["colour_rules"]
    red = colour_weight(h, s, v, rules["red"])
    gold = colour_weight(h, s, v, rules["gold"])
    gold_strict = colour_weight(h, s, v, rules["gold_strict"])
    leather = np.zeros(pid.shape, dtype=np.float32)
    for reg in cfg.get("leather_regions", []):
        pm = pid == names.index(reg["part"]) + 1
        w = colour_weight(h, s, v, rules["leather"]) * region_weight(pos, reg)
        leather = np.where(pm, np.maximum(leather, w), leather)
    group_of = np.zeros(pid.shape, dtype=np.int8)       # 0 none, 1 armour, 2 cloth, 3 head, 4 stone
    gids = {"armour": 1, "cloth": 2, "head": 3, "stone": 4}
    for g, parts in cfg["groups"].items():
        for p in parts:
            if p in names:
                group_of[pid == names.index(p) + 1] = gids[g]
    unassigned = sorted({names[i - 1] for i in np.unique(pid[covered & (group_of == 0)])})
    if unassigned:
        raise RuntimeError("material groups miss parts %s" % unassigned)
    head_reg = np.zeros(pid.shape, dtype=np.float32)
    for reg in cfg.get("head_metal_regions", []):
        head_reg = np.maximum(head_reg, region_weight(pos, reg))
    metal = np.zeros(pid.shape, dtype=np.float32)
    gshare = np.zeros(pid.shape, dtype=np.float32)
    arm, clo, hed = group_of == 1, group_of == 2, group_of == 3
    metal[arm] = ((1.0 - red) * (1.0 - leather))[arm]
    gshare[arm] = gold[arm]
    metal[clo] = (gold * (1.0 - red))[clo]
    gshare[clo] = 1.0
    metal[hed] = (gold_strict * head_reg * (1.0 - red))[hed]
    gshare[hed] = 1.0
    metal[~covered] = 0.0

    # ------------------------------------------------ metal base colour and roughness
    mc = cfg["metal"]
    st, gd = mc["steel"], mc["gold"]
    core_steel = covered & (metal >= 0.95) & (gshare <= 0.05)
    core_gold = covered & (metal >= 0.95) & (gshare >= 0.95)
    rep = {"schema": "unmatched.h2-bake.materials/1", "refs": {}}
    # reference luminance per reference group (parts with their own reference, e.g. the polished blade)
    ref_steel = np.ones(pid.shape, dtype=np.float32)
    ref_gold = np.ones(pid.shape, dtype=np.float32)
    own = st.get("own_reference_parts", [])
    rest = covered & ~np.isin(pid, [names.index(p) + 1 for p in own if p in names])
    for tag, sel in [("default", rest)] + [(p, pid == names.index(p) + 1) for p in own if p in names]:
        rs = float(np.median(lum[core_steel & sel & arm])) if (core_steel & sel & arm).any() else 0.05
        rg = float(np.median(lum[core_gold & sel & arm])) if (core_gold & sel & arm).any() else 0.15
        ref_steel[sel] = rs
        ref_gold[sel] = rg
        rep["refs"][tag] = {"steel_core_lum_median": P.r(rs, 5), "gold_core_lum_median": P.r(rg, 5),
                            "steel_core_texels": int((core_steel & sel & arm).sum()),
                            "gold_core_texels": int((core_gold & sel & arm).sum())}
    lum_safe = np.maximum(lum, 1e-5)
    ratio_s = lum_safe / ref_steel
    ratio_g = lum_safe / ref_gold
    # steel parameters per texel: the plate values (metal.steel) with per-part overrides (metal.steel_part_overrides,
    # H2.2: the polished blade keeps the H2.1 light steel while the plate is dark blued steel)
    sp = steel_params(st, mc.get("steel_part_overrides", {}), pid, names)
    Ls = np.clip(sp["target"] * ratio_s ** sp["gamma"], sp["lo"], sp["hi"])
    chroma = bc / lum_safe[..., None]
    chroma = chroma / np.maximum(chroma @ LUM, 1e-6)[..., None]
    k = sp["chroma_keep"][..., None]
    bc_steel = Ls[..., None] * ((1.0 - k) + k * np.clip(chroma, 0.0, 3.0))
    if sp["tinted"].any():
        # tint (linear, luminance-normalised; measured on the concept): colour only, the luminance stays Ls
        tinted = bc_steel * sp["tint"]
        tinted = tinted * (Ls / np.maximum(tinted @ LUM, 1e-9))[..., None]
        bc_steel = np.where(sp["tinted"][..., None], tinted, bc_steel)
    ref_rgb = np.array(gd["reference_linear"], dtype=np.float32)
    ref_chroma = ref_rgb / float(ref_rgb @ LUM)
    ch_g = np.clip(chroma, 0.0, 4.0)
    ch_g = ch_g / np.maximum(ch_g @ LUM, 1e-6)[..., None]
    mix = float(gd["chroma_to_reference"])
    ch_g = (1.0 - mix) * ch_g + mix * ref_chroma
    ch_g = ch_g / np.maximum(ch_g @ LUM, 1e-6)[..., None]
    Lg = np.clip(float(gd["bc_target_linear_lum"]) * ratio_g ** float(gd["gamma"]), *gd["bc_lum_clamp"])
    bc_gold = np.clip(Lg[..., None] * ch_g, 0.0, float(gd.get("channel_max", 0.95)))
    bc_metal = bc_steel * (1.0 - gshare[..., None]) + bc_gold * gshare[..., None]

    def detail(ratio, lo, hi):
        return np.clip((np.log(ratio) - np.log(lo)) / (np.log(hi) - np.log(lo)), 0.0, 1.0).astype(np.float32)
    ts = np.clip((np.log(ratio_s) - np.log(sp["dr_lo"])) / (np.log(sp["dr_hi"]) - np.log(sp["dr_lo"])),
                 0.0, 1.0).astype(np.float32)
    tg = detail(ratio_g, *gd["roughness_detail_ratio"])
    r_steel = sp["r_hi"] - sp["r_span"] * ts
    gr = np.where(clo[..., None], np.array(gd["roughness_on_cloth"], dtype=np.float32),
                  np.array(gd["roughness"], dtype=np.float32))
    r_gold = gr[..., 1] - (gr[..., 1] - gr[..., 0]) * tg
    r_metal = r_steel * (1.0 - gshare) + r_gold * gshare

    # ------------------------------------------------ non-metal roughness (Tripo roughness clamped per class)
    nm = cfg["non_metal_roughness"]
    tr = mr[..., 1]
    r_non = np.clip(tr, *nm["head"])
    r_non = np.where(group_of == 4, np.clip(tr, *nm["stone"]), r_non)
    cloth_like = (group_of == 2) | (group_of == 1)
    r_non = np.where(cloth_like, np.clip(tr, *nm["cloth"]), r_non)
    lw = leather
    r_non = r_non * (1.0 - lw) + np.clip(tr, *nm["leather"]) * lw

    bc_out = bc * (1.0 - metal[..., None]) + bc_metal * metal[..., None]
    mr_out = mr.copy()
    mr_out[..., 1] = r_non * (1.0 - metal) + r_metal * metal
    mr_out[..., 2] = metal
    bc_out = bc_out.astype(np.float32)
    mr_out = mr_out.astype(np.float32)

    # ------------------------------------------------ measurements
    cov = covered
    lum_out = bc_out @ LUM
    # the steel with its own reference and parameters (the polished blade: st.own_reference_parts) is its own class;
    # the plate parts with overridden values (H2.2 rev. 2: legs, pauldrons) stay plate steel
    steel_over = np.isin(pid, [names.index(p) + 1 for p in st.get("own_reference_parts", [])
                               if p in names and p in mc.get("steel_part_overrides", {})])
    classes_hard = {
        "steel": cov & (metal >= 0.5) & (gshare < 0.5),
        # H2.2: the plate steel and the steel with its own reference and parameters (the blade) separately
        "steel_plate": cov & (metal >= 0.5) & (gshare < 0.5) & ~steel_over,
        "steel_own_params": cov & (metal >= 0.5) & (gshare < 0.5) & steel_over,
        "gold": cov & (metal >= 0.5) & (gshare >= 0.5),
        "gold_on_cloth": cov & clo & (metal >= 0.5),
        "red_cloth": cov & (red >= 0.5) & (metal < 0.5),
        "leather": cov & (leather >= 0.5),
        "head_non_metal": cov & hed & (metal < 0.5),
        "stone": cov & (group_of == 4),
    }
    cls = {}
    for name, sel in classes_hard.items():
        n = int(sel.sum())
        e = {"texels": n}
        if n:
            e |= {"metallic_mean": P.r(mr_out[..., 2][sel].mean(), 4),
                  "roughness_p10_p50_p90": pct(mr_out[..., 1][sel], nd=3),
                  "bc_lum_linear_p10_p50_p90": pct(lum_out[sel]),
                  # the same texels before this pass: painted BC, Tripo metallicRoughness (= H2)
                  "before": {"metallic_mean": P.r(mr[..., 2][sel].mean(), 4),
                             "roughness_p10_p50_p90": pct(mr[..., 1][sel], nd=3),
                             "bc_lum_linear_p10_p50_p90": pct(lum[sel])}}
            if name.startswith("steel"):
                e["bc_channel_spread_p50_p95"] = pct(bc_out[sel].max(axis=1) - bc_out[sel].min(axis=1), (50, 95))
                e["bc_mean_linear_rgb"] = [P.r(x, 4) for x in bc_out[sel].mean(axis=0)]
            if name.startswith("gold"):
                e["bc_mean_linear_rgb"] = [P.r(x, 4) for x in bc_out[sel].mean(axis=0)]
        cls[name] = e
    rep["classes"] = cls
    per_part = {}
    for i, n in enumerate(names):
        m = cov & (pid == i + 1)
        if m.any():
            per_part[n] = {"metallic_mean_before": P.r(mr[..., 2][m].mean(), 4),
                           "metallic_mean": P.r(mr_out[..., 2][m].mean(), 4),
                           "metal_share": P.r((metal[m] >= 0.5).mean(), 4),
                           "gold_share_of_metal": P.r((gshare[m & (metal >= 0.5)] >= 0.5).mean(), 4) if (m & (metal >= 0.5)).any() else 0.0,
                           "roughness_mean": P.r(mr_out[..., 1][m].mean(), 4)}
    rep["per_part"] = per_part
    rep["separation"] = {
        "red_texels_ge_0.9_with_metallic_gt_0.1": int((cov & (red >= 0.9) & (mr_out[..., 2] > 0.1)).sum()),
        "red_texels_ge_0.9": int((cov & (red >= 0.9)).sum()),
        "red_texels_ge_0.5_with_metallic_gt_0.1": int((cov & (red >= 0.5) & (mr_out[..., 2] > 0.1)).sum()),
        "cloth_part_gold_texels_metallic_lt_0.5": int((cov & clo & (gold >= 0.5) & (red < 0.5) & (metal < 0.5)).sum()),
        "cloth_part_gold_texels": int((cov & clo & (gold >= 0.5) & (red < 0.5)).sum()),
        "soft_boundary_texels_0.1_0.9": int((cov & (metal > 0.1) & (metal < 0.9)).sum()),
    }
    rep["atlas"] = {"metallic_mean_covered": P.r(mr_out[..., 2][cov].mean(), 4),
                    "metallic_share_above_0.5": P.r((mr_out[..., 2][cov] > 0.5).mean(), 4),
                    "roughness_mean_covered": P.r(mr_out[..., 1][cov].mean(), 4),
                    "before": {"metallic_mean_covered": P.r(mr[..., 2][cov].mean(), 4),
                               "metallic_share_above_0.5": P.r((mr[..., 2][cov] > 0.5).mean(), 4),
                               "roughness_mean_covered": P.r(mr[..., 1][cov].mean(), 4)}}
    classes = {"metal": metal, "gold_share": gshare, "red": red, "leather": leather, "group": group_of,
               "steel_override": steel_over}
    return bc_out, mr_out, rep, classes


def class_raster(classes, covered):
    """Inspection colours (sRGB 8-bit): steel light blue-grey (the plate; the steel of the parts with their own steel
    parameters, i.e. the blade, pale cyan - H2.2, the steel luminance check separates the two), gold yellow, red
    cloth red, leather brown, head non-metal skin, stone dark grey, other non-metal mid grey; blended by the soft
    weights."""
    metal, gs, red, lea, grp = (classes[k] for k in ("metal", "gold_share", "red", "leather", "group"))
    over = classes.get("steel_override", np.zeros(metal.shape, dtype=bool))
    c_steel = np.where(over[..., None], np.array(STEEL_OVERRIDE_RGB, dtype=np.float32),
                       np.array(STEEL_PLATE_RGB, dtype=np.float32))
    c_gold = np.array([245, 205, 30], dtype=np.float32)
    c_red = np.array([190, 25, 30], dtype=np.float32)
    c_lea = np.array([110, 60, 25], dtype=np.float32)
    c_skin = np.array([235, 185, 150], dtype=np.float32)
    c_stone = np.array([55, 55, 55], dtype=np.float32)
    c_other = np.array([120, 120, 120], dtype=np.float32)
    nonm = np.where((grp == 3)[..., None], c_skin, np.where((grp == 4)[..., None], c_stone, c_other))
    nonm = nonm * (1 - red[..., None]) + c_red * red[..., None]
    nonm = nonm * (1 - lea[..., None]) + c_lea * lea[..., None]
    met = c_steel * (1 - gs[..., None]) + c_gold * gs[..., None]
    out = nonm * (1 - metal[..., None]) + met * metal[..., None]
    out[~covered] = 0
    return np.clip(out + 0.5, 0, 255).astype(np.uint8)
