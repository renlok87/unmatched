"""H2.1 material pass of the textures stage (plain Python: numpy + scipy.ndimage; no bpy).

Why: the Tripo PBR step gives the gold of the H2 model metallic ~0.095 and roughness ~0.75 — gold reads as peach clay.
Driven by profile textures.materials (absent -> the stage is byte-for-byte the H2 textures stage). Steps, in order:

  ao_exclusions  AO of a part re-baked without the high-poly occluders that move away in the animation (stage aux,
                 work/bake/AO_EX.npy): replaces the part's AO before the footprints/caps take their rim samples.
  rim_filters    contact caps / footprints whose rim carries the neighbour's colour (the Tripo texture at a contact line
                 is the covering part projected: skin and belt gold on the dress under the fist): rim samples outside a
                 keep class (HSV of the BC composite; optional ao_min: not in a crease) get weight 0, every cap vertex
                 is renormalised to its kept samples (a vertex without any: the mean of the region's kept samples).
  metal          metal mask m in [0, 1] from data that exists: BC hue/saturation/value per texel and its local mean
                 (coverage-normalised box of radius local_radius_px inside the part: cavities of a gold piece stay
                 gold, lighter specks of leather stay leather), membership in the Tripo parts (per-part thresholds) and
                 optional 3D gates from the rest-position map of stage aux (boxes: the diadem and earrings of the head
                 part, half-spaces: the quiver without its arrows). Then a binary closing (close_px) and a 3x3 blur.
  remap          metal texels: BaseColor -> the target metal colour (linear) x a compressed luminance detail of the
                 Tripo BC (cavities stay darker), metallic 0.9..1.0, roughness min..max from the detail and the Tripo
                 roughness rank (raised bright metal smoother); everything outside the mask: metallic 0 (cloth, skin,
                 leather, wood, snakes, base). Cloth (TeamMask rule of the cloth part, minus metal): roughness remapped
                 into cloth_roughness [lo, hi] by its Tripo rank (no sheen in M_UM_Figure: a fully rough dielectric
                 spreads its 4 % specular over the whole dark cloth as a grey veil).
All numbers go to textures-report.json -> materials. Deterministic: no randomness, fixed filter order.

band_repaint (textures.band_repaint, W2-c, pilot F107; runs with or without textures.materials, before the footprints
and caps read their rim): a visible band of a part at a contact line whose Tripo texture carries the neighbour's colour
(Achilles: olive-beige smears of the neck and curls on the red collar) is repainted from the same part just outside the
band. Texels of `part` (UV raster, rest position of stage aux, caps excluded) whose 3D distance to the nearest texel of
the `near` parts is <= band_m form the band (union of include_boxes_m when given, minus exclude_boxes_m); texels at
band_m .. band_m + ring_m that pass keep_hsv form the source ring. Every band texel takes the inverse-distance mean of
its k nearest ring texels (3D) for each map of `keys` (default BC), times an optional luminance detail of its own BC
(own / local mean of the band, clipped to `detail`); the last feather_m of the band blends into the original.

color_repaint (textures.color_repaint, F12 of the 2026-10-20 batch: Bruce Lee model acceptance r1, T 0.5; runs right
after band_repaint, before the footprints and caps read their rim): a Tripo colour defect inside one part, not at a
contact line, which band_repaint cannot select (its band needs another part within 5 cm) — navy streaks on the edges of
the black stripes of a jumpsuit, a dark smear on the inner thighs. Texels of `parts` (UV raster, rest position of stage
aux, caps excluded; inside include_boxes_m when given, outside exclude_boxes_m) whose BaseColor passes match_hsv
(hue_deg [lo, hi], lo > hi wraps through 0; s_min / s_max / v_min / v_max; every given bound must hold) take the
inverse-distance mean of their k nearest source texels (3D) for each map of `keys` (default BC): source = a baked texel of
the same parts (anywhere in them, boxes do not limit the sources) that does NOT pass match_hsv and passes keep_hsv
(default: every non-matching texel), no farther than radius_m (<= 0.03 m). A matched texel without a source in reach
keeps its value (counted as without_source). Optional `detail` = the luminance detail of band_repaint (own / local mean
of the matched texels, clipped). Report rows: matched, repainted, without_source, distances, mean change.
Optional `majority` {radius_m <= 0.012, min_source_fraction in (0.5, 1]} (Bruce Lee model acceptance r2, T 0.5: stripes
with yellow inserts, ragged edges and specks): a matched texel is repainted only when, among the baked texels of the same
parts within majority.radius_m of it (3D, rest position, caps excluded), the share of source texels (keep_hsv and not
match_hsv) is >= min_source_fraction — a majority / closing filter: holes and a yellow middle inside a dark stripe fill,
dark specks and a ragged rim outside it go, and the stripe does not widen (at its edge the share is about one half).
Report row block majority: passed / held texels.

roughness_remap (textures.roughness_remap, F12; runs after the caps and after the H2.1 metal remap, with or without
textures.materials.metal — the cloth_roughness of materials.remap runs only inside the metal pass, so a metal-free hero
had no way to make its cloth matte): ORM roughness (RM.G) of the valid texels of `parts` (optional `hsv` gate on the
BaseColor, same keys as match_hsv) goes into [lo, hi] by its rank in those texels (rank01: 5th..95th percentile, the
cloth_roughness rule). Metal texels (mask >= 0.5 of the metal pass) are left out. Without the key nothing runs and the
cloth_roughness result of heroes with metal is unchanged."""

import numpy as np
from scipy import ndimage


def lin(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def hex_srgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)], np.float64)


def smooth_ge(x, edge, ramp):
    t = np.clip((x - (edge - ramp)) / (2 * ramp), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def smooth_le(x, edge, ramp):
    return smooth_ge(-x, -edge, ramp)


def hue_band(h, lo, hi, ramp):
    return smooth_ge(h, lo, ramp) * smooth_le(h, hi, ramp)


def luminance(rgb_lin):
    return rgb_lin[..., 0] * 0.2126 + rgb_lin[..., 1] * 0.7152 + rgb_lin[..., 2] * 0.0722


def hsv_keep(rgb, rule, tx):
    h, s, v = tx.rgb_to_hsv(rgb)
    ok = np.ones(h.shape, bool)
    if "v_max" in rule:
        ok &= v <= rule["v_max"]
    if "v_min" in rule:
        ok &= v >= rule["v_min"]
    if "s_max" in rule:
        ok &= s <= rule["s_max"]
    if "s_min" in rule:
        ok &= s >= rule["s_min"]
    return ok


# ---------------------------------------------------------------- AO exclusions
def ao_exclusions(maps, alpha, part_ids, part_names, run_dir, cfg):
    """Replaces the AO of the listed parts by work/bake/AO_EX.npy (stage aux); returns stats."""
    ex = np.load(run_dir / "work" / "bake" / "AO_EX.npy")
    ex_a = np.load(run_dir / "work" / "bake" / "AO_EX_alpha.npy").astype(bool)
    rows = []
    for part in cfg:
        pi = part_names.index(part)
        m = (part_ids == pi) & ex_a & alpha["AO"]
        d = ex[..., 0][m] - maps["AO"][..., 0][m]
        maps["AO"][m] = ex[m]
        rows.append({"part": part, "texels": int(m.sum()), "delta_mean": round(float(d.mean()), 5),
                     "delta_p99": round(float(np.percentile(d, 99)), 4), "delta_max": round(float(d.max()), 4),
                     "texels_lighter_gt_16_255": int((d > 16 / 255).sum())})
    return rows


# ---------------------------------------------------------------- rim filters
def filter_rim(region, maps, alpha, exclude, labels, rules, tx):
    """Zero the weights of rim samples outside the keep class for the regions (caps / footprints) with the given labels;
    renormalise each vertex row. region: dict of the uv stage (tri_v, tri_cap, samp_px, w_rows, w_cols, w_vals).
    tx: helpers of the textures stage (rgb_to_hsv, bilinear, dilate, blur3)."""
    out = dict(region)
    vals = region["w_vals"].copy()
    pre, _ok = tx.dilate(maps["BC"], alpha["BC"] & ~exclude, 4)  # the same rim read as region_paint / cap_fill
    colours = tx.bilinear(pre, region["samp_px"])
    pre_ao, _ok = tx.dilate(maps["AO"], alpha["AO"] & ~exclude, 4)
    ao = tx.bilinear(pre_ao, region["samp_px"])[:, 0]
    stats = []
    for label, rule in zip(labels, rules):
        verts = np.unique(region["tri_v"][region["tri_cap"] == label])
        if not len(verts):
            stats.append({"label": int(label), "vertices": 0})
            continue
        in_rows = np.isin(region["w_rows"], verts)
        keep = hsv_keep(colours[region["w_cols"]], rule, tx)
        if "ao_min" in rule:  # a crease right at the contact line (belt overhang) is not the surface under the contact
            keep &= ao[region["w_cols"]] >= float(rule["ao_min"])
        samples = np.unique(region["w_cols"][in_rows])
        kept_samples = np.unique(region["w_cols"][in_rows & keep])
        new = np.where(in_rows & ~keep, 0.0, vals)
        tot_new = np.bincount(region["w_rows"], new, minlength=int(region["n_vertices"]))
        tot_old = np.bincount(region["w_rows"], vals, minlength=int(region["n_vertices"]))
        fallback = np.zeros(int(region["n_vertices"]), bool)
        fallback[verts] = tot_new[verts] <= 1e-9
        use_new = in_rows & ~fallback[region["w_rows"]]
        vals = np.where(use_new, new / np.maximum(tot_new[region["w_rows"]], 1e-12) * tot_old[region["w_rows"]], vals)
        extra = None
        if fallback[verts].any() and len(kept_samples):
            # a vertex whose rim samples are all outside the keep class takes the mean of the region's kept samples
            fb = np.nonzero(fallback)[0]
            drop = np.isin(region["w_rows"], fb)
            vals = np.where(drop, 0.0, vals)
            extra = (np.repeat(fb, len(kept_samples)), np.tile(kept_samples, len(fb)),
                     np.repeat(tot_old[fb], len(kept_samples)) / len(kept_samples))
        if extra is not None:
            region = dict(region, w_rows=np.concatenate([region["w_rows"], extra[0]]),
                          w_cols=np.concatenate([region["w_cols"], extra[1]]))
            vals = np.concatenate([vals, extra[2]])
            out["w_rows"], out["w_cols"] = region["w_rows"], region["w_cols"]
        stats.append({"label": int(label), "vertices": int(len(verts)), "rim_samples": int(len(samples)),
                      "rim_samples_kept": int(len(kept_samples)), "vertices_without_kept_sample": int(fallback[verts].sum()),
                      "fallback": "mean of the region's kept samples",
                      "keep": rule})
    out["w_vals"] = vals
    return out, stats


# ---------------------------------------------------------------- band repaint (W2-c)
def boxes_mask(pts, boxes):
    inside = np.zeros(len(pts), bool)
    for b in boxes:
        inside |= np.all((pts >= np.array(b["min_m"])) & (pts <= np.array(b["max_m"])), axis=1)
    return inside


def band_repaint(maps, alpha, part_ids, part_names, pos, pos_ok, exclude, cfgs, tx):
    """Repaints the bands of textures.band_repaint in place (module docstring); returns the report rows."""
    from scipy.spatial import cKDTree

    rows = []
    for cfg in cfgs:
        band_m = float(cfg["band_m"])
        ring_m = float(cfg.get("ring_m", 0.006))
        feather = float(cfg.get("feather_m", 0.002))
        keys = list(cfg.get("keys", ["BC"]))
        k = int(cfg.get("k", 8))
        pi = part_names.index(cfg["part"])
        mine = (part_ids == pi) & pos_ok & ~exclude
        near = np.isin(part_ids, [part_names.index(n) for n in cfg["near"]]) & pos_ok
        ya, xa = np.nonzero(mine)
        pa = pos[ya, xa].astype(np.float64)
        pn = pos[near].astype(np.float64)
        row = {"name": cfg["name"], "part": cfg["part"], "near": list(cfg["near"]), "band_m": band_m, "ring_m": ring_m,
               "part_texels": int(len(pa))}
        if not len(pa) or not len(pn):
            rows.append(dict(row, band_texels=0, note="no texels of the part or of the near parts"))
            continue
        d, _i = cKDTree(pn).query(pa, distance_upper_bound=band_m + ring_m + 1e-6)
        ok = np.ones(len(pa), bool)
        if cfg.get("include_boxes_m"):
            ok &= boxes_mask(pa, cfg["include_boxes_m"])
        if cfg.get("exclude_boxes_m"):
            ok &= ~boxes_mask(pa, cfg["exclude_boxes_m"])
        band = ok & (d <= band_m)
        ring = ok & (d > band_m) & (d <= band_m + ring_m) & alpha["BC"][ya, xa]
        ring_all = int(ring.sum())
        if cfg.get("keep_hsv"):
            ring &= hsv_keep(maps["BC"][ya, xa], cfg["keep_hsv"], tx)
        row.update(band_texels=int(band.sum()), ring_texels=ring_all, ring_texels_kept=int(ring.sum()))
        if not band.any() or ring.sum() < k:
            rows.append(dict(row, note="nothing repainted (empty band or fewer kept ring texels than k)"))
            continue
        bi, ri = np.nonzero(band)[0], np.nonzero(ring)[0]
        dd, ii = cKDTree(pa[ri]).query(pa[bi], k=k)
        dd, ii = dd.reshape(len(bi), -1), ii.reshape(len(bi), -1)
        w = 1.0 / (dd + 1e-4)
        w /= w.sum(1, keepdims=True)
        f = np.clip((band_m - d[bi]) / feather, 0.0, 1.0) if feather > 0 else np.ones(len(bi))
        f = f * f * (3 - 2 * f)
        by, bx = ya[bi], xa[bi]
        before_keep = hsv_keep(maps["BC"][by, bx], cfg["keep_hsv"], tx) if cfg.get("keep_hsv") else None
        stats = {}
        for key in keys:
            src = maps[key][ya[ri], xa[ri]].astype(np.float64)
            new = (w[..., None] * src[ii]).sum(1)
            if key == "BC" and cfg.get("detail"):
                lo, hi = cfg["detail"]
                own = luminance(lin(maps["BC"][by, bx].astype(np.float64)))
                # own luminance over its local mean among the 4k nearest band texels (3D): the fold / weave detail stays,
                # the smear's colour does not
                _dn, inb = cKDTree(pa[bi]).query(pa[bi], k=min(4 * k, len(bi)))
                inb = inb.reshape(len(bi), -1)
                ratio = np.clip(own / np.maximum(own[inb].mean(1), 1e-6), lo, hi)
                new = srgb(np.clip(lin(new) * ratio[:, None], 0.0, 1.0))
            old = maps[key][by, bx].astype(np.float64)
            out = old * (1 - f[:, None]) + new * f[:, None]
            stats[key] = {"mean_abs_change": round(float(np.abs(out - old).mean()), 4),
                          "p95_abs_change": round(float(np.percentile(np.abs(out - old).max(1), 95)), 4)}
            maps[key][by, bx] = out.astype(maps[key].dtype)
        row.update(maps=stats, feathered_texels=int((f < 1).sum()), k=k,
                   distance_mm_p50_max=[round(float(np.median(d[bi]) * 1000), 2), round(float(d[bi].max() * 1000), 2)])
        if before_keep is not None:
            after_keep = hsv_keep(maps["BC"][by, bx], cfg["keep_hsv"], tx)
            row["band_share_outside_keep_hsv"] = {"before": round(float((~before_keep).mean()), 4),
                                                  "after": round(float((~after_keep).mean()), 4),
                                                  "ring_reference": round(float(1 - ring.sum() / max(ring_all, 1)), 4)}
        rows.append(row)
    return rows


# ---------------------------------------------------------------- colour repaint and roughness remap (F12, 2026-10-20 batch)
COLOR_REPAINT_KEYS = ("name", "parts", "match_hsv", "keep_hsv", "include_boxes_m", "exclude_boxes_m", "radius_m", "k",
                      "keys", "detail", "majority", "note")
MAJORITY_KEYS = ("radius_m", "min_source_fraction")
COLOR_REPAINT_MAJORITY_RADIUS_MAX_M = 0.012
ROUGHNESS_REMAP_KEYS = ("name", "parts", "lo", "hi", "hsv", "note")
HSV_SELECT_KEYS = ("hue_deg", "s_min", "s_max", "v_min", "v_max")
REPAINT_MAPS = ("BC", "RM", "AO")
COLOR_REPAINT_RADIUS_MAX_M = 0.03


def _is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x)


def hsv_select(rgb, rule, tx):
    """Boolean mask of the texels whose HSV passes every bound of `rule` (hue_deg [lo, hi] in degrees, lo > hi wraps
    through 0; s_min, s_max, v_min, v_max in [0, 1]); an empty rule selects everything."""
    h, s, v = tx.rgb_to_hsv(rgb)
    ok = np.ones(h.shape, bool)
    if "hue_deg" in rule:
        lo, hi = rule["hue_deg"]
        ok &= ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))
    for key, cmp in (("s_min", np.greater_equal), ("s_max", np.less_equal), ("v_min", np.greater_equal),
                     ("v_max", np.less_equal)):
        if key in rule:
            ok &= cmp(s if key[0] == "s" else v, rule[key])
    return ok


def _hsv_rule_problems(where, rule, allow_empty):
    if not isinstance(rule, dict) or (not rule and not allow_empty):
        return ["%s must be a non-empty object of %s (got %r)" % (where, ", ".join(HSV_SELECT_KEYS), rule)]
    problems = ["%s: unknown key %s" % (where, k) for k in rule if k not in HSV_SELECT_KEYS]
    for k, v in rule.items():
        if k == "hue_deg":
            if not (isinstance(v, list) and len(v) == 2 and all(_is_num(x) and 0.0 <= x <= 360.0 for x in v)):
                problems.append("%s.hue_deg must be [lo, hi] in 0..360 degrees (got %r)" % (where, v))
        elif k in HSV_SELECT_KEYS and not (_is_num(v) and 0.0 <= v <= 1.0):
            problems.append("%s.%s must be in [0, 1] (got %r)" % (where, k, v))
    return problems


def _boxes_problems(where, boxes):
    if not isinstance(boxes, list) or not boxes:
        return ["%s must be a non-empty list of {min_m: [x, y, z], max_m: [x, y, z]}" % where]
    for i, b in enumerate(boxes):
        if not (isinstance(b, dict) and all(isinstance(b.get(k), list) and len(b[k]) == 3 and all(_is_num(v) for v in b[k])
                                            for k in ("min_m", "max_m"))
                and all(lo < hi for lo, hi in zip(b["min_m"], b["max_m"]))):
            return ["%s[%d] must be {min_m: [x, y, z], max_m: [x, y, z]} with min < max" % (where, i)]
    return []


def _parts_problems(where, parts, part_names):
    if not isinstance(parts, list) or not parts or len(set(parts)) != len(parts):
        return ["%s must be a non-empty list of distinct parts (got %r)" % (where, parts)]
    return ["%s: unknown part %r" % (where, p) for p in parts if p not in part_names]


def color_repaint_problems(cfgs, part_names):
    """Validation of textures.color_repaint (the stage raises ValueError with these problems)."""
    if not isinstance(cfgs, list) or not cfgs:
        return ["textures.color_repaint must be a non-empty list of repaints"]
    problems, seen = [], set()
    for i, c in enumerate(cfgs):
        w = "textures.color_repaint[%d]" % i
        if not isinstance(c, dict):
            problems.append("%s must be an object" % w)
            continue
        problems += ["%s: unknown key %s" % (w, k) for k in c if k not in COLOR_REPAINT_KEYS]
        if not isinstance(c.get("name"), str) or not c["name"] or c["name"] in seen:
            problems.append("%s.name must be a unique non-empty string" % w)
        seen.add(c.get("name"))
        problems += _parts_problems(w + ".parts", c.get("parts"), part_names)
        problems += _hsv_rule_problems(w + ".match_hsv", c.get("match_hsv"), allow_empty=False)
        if "keep_hsv" in c:
            problems += _hsv_rule_problems(w + ".keep_hsv", c["keep_hsv"], allow_empty=True)
        r = c.get("radius_m", 0.01)
        if not (_is_num(r) and 0.0 < r <= COLOR_REPAINT_RADIUS_MAX_M):
            problems.append("%s.radius_m must be in (0, %s] m (got %r)" % (w, COLOR_REPAINT_RADIUS_MAX_M, r))
        k = c.get("k", 8)
        if not (isinstance(k, int) and not isinstance(k, bool) and 1 <= k <= 64):
            problems.append("%s.k must be an integer in [1, 64] (got %r)" % (w, k))
        keys = c.get("keys", ["BC"])
        if not (isinstance(keys, list) and keys and all(x in REPAINT_MAPS for x in keys) and len(set(keys)) == len(keys)):
            problems.append("%s.keys must be a non-empty subset of %s (got %r)" % (w, list(REPAINT_MAPS), keys))
        det = c.get("detail")
        if det is not None and not (isinstance(det, list) and len(det) == 2 and all(_is_num(x) for x in det)
                                    and 0.0 < det[0] <= 1.0 <= det[1]):
            problems.append("%s.detail must be [lo, hi] with 0 < lo <= 1 <= hi (got %r)" % (w, det))
        for key in ("include_boxes_m", "exclude_boxes_m"):
            if key in c:
                problems += _boxes_problems("%s.%s" % (w, key), c[key])
        if "majority" in c:
            problems += _majority_problems(w + ".majority", c["majority"])
    return problems


def _majority_problems(where, mj):
    if not isinstance(mj, dict):
        return ["%s must be {radius_m, min_source_fraction} (got %r)" % (where, mj)]
    problems = ["%s: unknown key %s" % (where, k) for k in mj if k not in MAJORITY_KEYS]
    r, f = mj.get("radius_m"), mj.get("min_source_fraction")
    if not (_is_num(r) and 0.0 < r <= COLOR_REPAINT_MAJORITY_RADIUS_MAX_M):
        problems.append("%s.radius_m must be in (0, %s] m (got %r)" % (where, COLOR_REPAINT_MAJORITY_RADIUS_MAX_M, r))
    if not (_is_num(f) and 0.5 < f <= 1.0):
        problems.append("%s.min_source_fraction must be in (0.5, 1] (got %r)" % (where, f))
    return problems


def majority_fraction(pts, counted, source, query, radius):
    """Share of `source` points among the `counted` points within `radius` (3D ball, boundary included) of every `query`
    point (boolean masks over pts; source must be a subset of counted). Exact counts: cKDTree.query_ball_point with
    return_length."""
    from scipy.spatial import cKDTree

    q = pts[query]
    if not len(q):
        return np.zeros(0)
    n_all = cKDTree(pts[counted]).query_ball_point(q, radius, return_length=True, workers=-1)
    n_src = (cKDTree(pts[source]).query_ball_point(q, radius, return_length=True, workers=-1) if source.any()
             else np.zeros(len(q), np.int64))
    return np.asarray(n_src, np.float64) / np.maximum(np.asarray(n_all, np.float64), 1.0)


def roughness_remap_problems(cfgs, part_names):
    """Validation of textures.roughness_remap (the stage raises ValueError with these problems)."""
    if not isinstance(cfgs, list) or not cfgs:
        return ["textures.roughness_remap must be a non-empty list of remaps"]
    problems, seen = [], set()
    for i, c in enumerate(cfgs):
        w = "textures.roughness_remap[%d]" % i
        if not isinstance(c, dict):
            problems.append("%s must be an object" % w)
            continue
        problems += ["%s: unknown key %s" % (w, k) for k in c if k not in ROUGHNESS_REMAP_KEYS]
        if not isinstance(c.get("name"), str) or not c["name"] or c["name"] in seen:
            problems.append("%s.name must be a unique non-empty string" % w)
        seen.add(c.get("name"))
        problems += _parts_problems(w + ".parts", c.get("parts"), part_names)
        lo, hi = c.get("lo"), c.get("hi")
        if not (_is_num(lo) and 0.0 <= lo <= 1.0):
            problems.append("%s.lo must be in [0, 1] (got %r)" % (w, lo))
        if not (_is_num(hi) and 0.0 <= hi <= 1.0):
            problems.append("%s.hi must be in [0, 1] (got %r)" % (w, hi))
        if _is_num(lo) and _is_num(hi) and not lo < hi:
            problems.append("%s: lo must be below hi (got %r, %r)" % (w, lo, hi))
        if "hsv" in c:
            problems += _hsv_rule_problems(w + ".hsv", c["hsv"], allow_empty=True)
    return problems


def color_repaint(maps, alpha, part_ids, part_names, pos, pos_ok, exclude, cfgs, tx):
    """Repaints the matched texels of textures.color_repaint in place (module docstring); returns the report rows."""
    from scipy.spatial import cKDTree

    rows = []
    for cfg in cfgs:
        radius = float(cfg.get("radius_m", 0.01))
        k = int(cfg.get("k", 8))
        keys = list(cfg.get("keys", ["BC"]))
        idx = [part_names.index(p) for p in cfg["parts"]]
        mine = np.isin(part_ids, idx) & pos_ok & ~exclude
        ya, xa = np.nonzero(mine)
        pa = pos[ya, xa].astype(np.float64)
        rgb = maps["BC"][ya, xa]
        matched_colour = hsv_select(rgb, cfg["match_hsv"], tx)
        in_box = np.ones(len(pa), bool)
        if cfg.get("include_boxes_m"):
            in_box &= boxes_mask(pa, cfg["include_boxes_m"])
        if cfg.get("exclude_boxes_m"):
            in_box &= ~boxes_mask(pa, cfg["exclude_boxes_m"])
        match = matched_colour & in_box
        source = ~matched_colour & alpha["BC"][ya, xa] & hsv_select(rgb, cfg.get("keep_hsv", {}), tx)
        row = {"name": cfg["name"], "parts": list(cfg["parts"]), "radius_m": radius, "k": k,
               "part_texels": int(len(pa)), "matched_texels": int(match.sum()), "source_texels": int(source.sum())}
        mj = cfg.get("majority")
        if mj:  # majority / closing filter: repaint only where the sources hold the majority of the ball
            frac = majority_fraction(pa, alpha["BC"][ya, xa], source, match, float(mj["radius_m"]))
            passed = frac >= float(mj["min_source_fraction"])
            row["majority"] = {"radius_m": float(mj["radius_m"]), "min_source_fraction": float(mj["min_source_fraction"]),
                               "passed_texels": int(passed.sum()), "held_texels": int((~passed).sum())}
            match = match.copy()
            match[np.nonzero(match)[0][~passed]] = False
        mi, si = np.nonzero(match)[0], np.nonzero(source)[0]
        if not len(mi) or not len(si):
            rows.append(dict(row, repainted_texels=0, without_source=int(len(mi)),
                             note="nothing repainted (no matched texel or no source texel)"))
            continue
        kk = min(k, len(si))
        dd, ii = cKDTree(pa[si]).query(pa[mi], k=kk, distance_upper_bound=radius)
        dd, ii = dd.reshape(len(mi), -1), ii.reshape(len(mi), -1)
        found = np.isfinite(dd)
        has = found.any(1)
        w = np.where(found, 1.0 / (np.where(found, dd, 1.0) + 1e-4), 0.0)
        w = w / np.maximum(w.sum(1, keepdims=True), 1e-12)
        ii = np.where(found, ii, 0)
        mi_ok, w, ii = mi[has], w[has], ii[has]
        by, bx = ya[mi_ok], xa[mi_ok]
        stats = {}
        for key in keys:
            src = maps[key][ya[si], xa[si]].astype(np.float64)
            new = (w[..., None] * src[ii]).sum(1)
            if key == "BC" and cfg.get("detail") and len(mi_ok):
                lo, hi = cfg["detail"]
                own = luminance(lin(maps["BC"][by, bx].astype(np.float64)))
                _dn, inb = cKDTree(pa[mi_ok]).query(pa[mi_ok], k=min(4 * k, len(mi_ok)))
                inb = inb.reshape(len(mi_ok), -1)
                ratio = np.clip(own / np.maximum(own[inb].mean(1), 1e-6), lo, hi)
                new = srgb(np.clip(lin(new) * ratio[:, None], 0.0, 1.0))
            old = maps[key][by, bx].astype(np.float64)
            stats[key] = {"mean_abs_change": round(float(np.abs(new - old).mean()), 4) if len(mi_ok) else 0.0}
            maps[key][by, bx] = new.astype(maps[key].dtype)
        dist = dd[has][found[has]]
        row.update(repainted_texels=int(len(mi_ok)), without_source=int((~has).sum()), maps=stats,
                   distance_mm_p50_max=[round(float(np.median(dist) * 1000), 2), round(float(dist.max() * 1000), 2)]
                   if len(dist) else None)
        rows.append(row)
    return rows


def roughness_remap(maps, valid, part_ids, part_names, metal_m, cfgs, tx):
    """ORM roughness (RM.G) of the listed parts into [lo, hi] by rank, in place (module docstring); returns the rows."""
    rows = []
    for cfg in cfgs:
        idx = [part_names.index(p) for p in cfg["parts"]]
        sel = np.isin(part_ids, idx) & valid
        if cfg.get("hsv"):
            sel &= hsv_select(maps["BC"], cfg["hsv"], tx)
        metal_out = 0
        if metal_m is not None:
            metal_out = int((sel & (metal_m >= 0.5)).sum())
            sel &= metal_m < 0.5
        row = {"name": cfg["name"], "parts": list(cfg["parts"]), "lo": cfg["lo"], "hi": cfg["hi"],
               "texels": int(sel.sum()), "metal_excluded_texels": metal_out}
        if not sel.any():
            rows.append(dict(row, note="no texel selected"))
            continue
        rough = maps["RM"][..., 1]
        before = rough[sel].astype(np.float64)
        rank, q = rank01(rough, sel)
        rough[sel] = (cfg["lo"] + (cfg["hi"] - cfg["lo"]) * rank[sel]).astype(rough.dtype)
        after = rough[sel].astype(np.float64)
        row.update(tripo_roughness_q5_q95=q,
                   roughness_before_p5_p50_p95=[round(float(x), 4) for x in np.percentile(before, [5, 50, 95])],
                   roughness_after_p5_p50_p95=[round(float(x), 4) for x in np.percentile(after, [5, 50, 95])])
        rows.append(row)
    return rows


# ---------------------------------------------------------------- metal mask
def local_mean(rgb, weight, radius):
    size = 2 * int(radius) + 1
    den = ndimage.uniform_filter(weight, size=size, mode="constant")
    out = np.empty_like(rgb)
    for c in range(rgb.shape[-1]):
        out[..., c] = ndimage.uniform_filter(rgb[..., c] * weight, size=size, mode="constant") / np.maximum(den, 1e-6)
    return out


def gate_3d(pos, gate):
    """1.0 where a position passes the part's 3D gates (union of boxes, intersection of half-spaces)."""
    ok = np.ones(pos.shape[0], bool)
    if gate.get("boxes"):
        inside = np.zeros(pos.shape[0], bool)
        for b in gate["boxes"]:
            lo, hi = np.array(b["min_m"]), np.array(b["max_m"])
            inside |= np.all((pos >= lo) & (pos <= hi), axis=1)
        ok &= inside
    for hs in gate.get("half_spaces", []):
        n = np.array(hs["normal"], np.float64)
        n /= np.linalg.norm(n)
        ok &= (pos - np.array(hs["point_m"])) @ n >= float(hs["min_m"])
    return ok


def part_terms(pc, cfg):
    """Mask terms of a part: explicit `terms` or the short form `local` / `texel` with the global defaults."""
    if "terms" in pc:
        return pc["terms"]
    terms = []
    hue = [cfg["hue_deg"][0], float(pc.get("hue_max", cfg["hue_deg"][1]))]
    if "local" in pc:
        terms.append(dict(pc["local"], kind="local", radius_px=int(cfg.get("local_radius_px", 6)), hue_deg=hue))
    if "texel" in pc:
        terms.append(dict(pc["texel"], kind="texel", hue_deg=hue))
    return terms


def metal_mask(bc, valid, part_ids, part_names, pos, cfg, tx):
    """Binary metal decision per texel (union of the part's terms, closing, 3D gates, small-component removal),
    then a 3x3 blur for the edge. A term: kind local (BC averaged over a (2r+1)^2 box of the part's valid texels) or
    texel; hue_deg band (ramp hue_ramp_deg), s_min, v_min (ramp `ramp`); a term passes at >= 0.5."""
    rgb_to_hsv, blur3 = tx.rgb_to_hsv, tx.blur3
    ramp = float(cfg.get("ramp", 0.04))
    hue_ramp = float(cfg.get("hue_ramp_deg", 4.0))
    h, s, v = rgb_to_hsv(bc)
    m = np.zeros(part_ids.shape, np.float32)
    per_part = {}
    for part, pc in sorted(cfg["parts"].items(), key=lambda kv: part_names.index(kv[0])):
        pi = part_names.index(part)
        mine = part_ids == pi
        terms = part_terms(pc, cfg)
        radius = max([int(t.get("radius_px", 0)) for t in terms] + [0])
        ys, xs = np.nonzero(mine)
        pad = radius + 2
        y0, x0 = max(ys.min() - pad, 0), max(xs.min() - pad, 0)
        y1, x1 = min(ys.max() + 1 + pad, bc.shape[0]), min(xs.max() + 1 + pad, bc.shape[1])
        sl = (slice(y0, y1), slice(x0, x1))
        w = (mine[sl] & valid[sl]).astype(np.float32)
        b = np.zeros(w.shape, bool)
        term_px = []
        for t in terms:
            hr = float(t.get("hue_ramp_deg", hue_ramp))
            if t["kind"] == "local":
                hh, ss, vv = rgb_to_hsv(local_mean(bc[sl], w, int(t["radius_px"])))
            else:
                hh, ss, vv = h[sl], s[sl], v[sl]
            val = hue_band(hh, t["hue_deg"][0], t["hue_deg"][1], hr) * smooth_ge(ss, t["s_min"], ramp) * smooth_ge(vv, t["v_min"], ramp)
            if "s_max" in t:
                val = val * smooth_le(ss, t["s_max"], ramp)
            bt = (val >= 0.5) & mine[sl]
            term_px.append(int(bt.sum()))
            b |= bt
        if "texel_floor" in pc:  # a metal piece keeps its cavities, but not the black gaps / soles
            b &= v[sl] >= pc["texel_floor"]["v_min"]
        close = int(cfg.get("close_px", 0))
        if close:  # fills cavities / specks narrower than 2 * close_px inside a metal piece (islands are >= 8 px apart)
            st = ndimage.generate_binary_structure(2, 1)
            b = ndimage.binary_closing(b, structure=st, iterations=close) & mine[sl]
        gate = None
        if pc.get("boxes") or pc.get("half_spaces"):
            gy, gx = np.nonzero(b)
            keep = gate_3d(pos[sl][gy, gx], pc)
            gate = {"texels_tested": int(len(gy)), "texels_kept": int(keep.sum())}
            b[gy[~keep], gx[~keep]] = False
        removed = 0
        min_px = int(pc.get("min_component_px", cfg.get("min_component_px", 0)))
        if min_px:
            lab, n = ndimage.label(b, structure=np.ones((3, 3), int))
            if n:
                sizes = np.bincount(lab.ravel())
                small = sizes < min_px
                small[0] = False
                drop = small[lab]
                removed = int(drop.sum())
                b &= ~drop
        m[sl] = np.where(b, 1.0, m[sl])
        per_part[part] = {"gate": gate, "term_texels": term_px, "small_component_texels_removed": removed}
    m = blur3(m, int(cfg.get("blur", 1))) * (part_ids >= 0)
    for part in per_part:
        mine = (part_ids == part_names.index(part)) & valid
        per_part[part]["metal_share"] = round(float((m[mine] >= 0.5).mean()), 4)
        per_part[part]["mask_mean"] = round(float(m[mine].mean()), 4)
    return m.astype(np.float32), per_part


# ---------------------------------------------------------------- remap
def rank01(x, sel, lo_q=5, hi_q=95):
    lo, hi = np.percentile(x[sel], [lo_q, hi_q])
    return np.clip((x - lo) / max(hi - lo, 1e-6), 0.0, 1.0), [round(float(lo), 4), round(float(hi), 4)]


def remap(maps, valid, m, cloth_w, cfg):
    bc = maps["BC"]
    rm = maps["RM"]
    before = {"metal": {}, "cloth": {}}
    sel = (m >= 0.5) & valid
    csel = (cloth_w >= 0.5) & valid
    for tag, s_ in (("metal", sel), ("cloth", csel)):
        if not s_.any():  # no cloth texels (team_mask.cloth_parts empty): nothing to measure
            before[tag] = {"texels": 0}
            continue
        before[tag] = {"texels": int(s_.sum()),
                       "bc_srgb_mean": [round(float(x) * 255, 1) for x in bc[s_].mean(0)],
                       "roughness_mean": round(float(rm[..., 1][s_].mean()), 4),
                       "metallic_mean": round(float(rm[..., 2][s_].mean()), 4)}
    mc = cfg["metal"]["basecolor"]
    bc_lin = lin(bc)
    L = luminance(bc_lin)
    l_ref = float(np.median(L[sel]))
    lo, hi = mc["detail_clip"]
    detail = np.clip(L / max(l_ref, 1e-6), lo, hi) ** float(mc["detail_gamma"])
    d01 = (detail - lo ** mc["detail_gamma"]) / (hi ** mc["detail_gamma"] - lo ** mc["detail_gamma"])
    target = lin(hex_srgb(mc["target_srgb"]))
    metal_lin = np.clip(target[None, None, :] * detail[..., None], 0.0, 1.0)
    mw = m[..., None]
    new_bc = srgb(bc_lin * (1 - mw) + metal_lin * mw)
    rc = cfg["metal"]["roughness"]
    r_rank, r_q = rank01(rm[..., 1], sel)
    wd = float(rc.get("detail_weight", 0.5))
    r_metal = rc["min"] + (rc["max"] - rc["min"]) * np.clip(wd * (1 - d01) + (1 - wd) * r_rank, 0.0, 1.0)
    mt = cfg["metal"]["metallic"]
    metal_val = mt["min"] + (mt["max"] - mt["min"]) * d01
    rough = rm[..., 1].copy()
    c_q = None
    cr = cfg.get("cloth_roughness")
    if cr and cr.get("apply", True) and csel.any():  # H2.1 measured: 0.80-0.90 made the cloth lighter and greyer -> off in the profile
        c_rank, c_q = rank01(rm[..., 1], csel)
        r_cloth = cr["lo"] + (cr["hi"] - cr["lo"]) * c_rank
        rough = rough * (1 - cloth_w) + r_cloth * cloth_w
    rough = rough * (1 - m) + r_metal * m
    metallic = metal_val * m
    maps["BC"] = new_bc.astype(np.float32)
    rm_new = rm.copy()
    rm_new[..., 1] = rough
    rm_new[..., 2] = metallic
    maps["RM"] = rm_new.astype(np.float32)
    after = {}
    core = (m >= 0.99) & valid
    for tag, s_ in (("metal", sel), ("metal_core_m_ge_0.99", core), ("cloth", csel)):
        if not s_.any():
            after[tag] = {"texels": 0}
            continue
        after[tag] = {"texels": int(s_.sum()),
                      "bc_srgb_mean": [round(float(x) * 255, 1) for x in maps["BC"][s_].mean(0)],
                      "roughness_mean": round(float(rough[s_].mean()), 4),
                      "roughness_p5_p95": [round(float(x), 4) for x in np.percentile(rough[s_], [5, 95])],
                      "metallic_mean": round(float(metallic[s_].mean()), 4),
                      "metallic_p5_p95": [round(float(x), 4) for x in np.percentile(metallic[s_], [5, 95])]}
    other = valid & (m < 0.01)
    after["non_metal_metallic_max"] = round(float(metallic[other].max()), 6) if other.any() else None
    bc_m = maps["BC"][sel]
    return {"luminance_reference_linear": round(l_ref, 5), "target_srgb": mc["target_srgb"],
            "target_linear": [round(float(x), 4) for x in target], "tripo_roughness_rank_q5_q95": {"metal": r_q, "cloth": c_q},
            "metal_bc_linear_max_channel_p5_p50_p95": [round(float(x), 4) for x in
                                                       np.percentile(lin(bc_m).max(-1), [5, 50, 95])],
            "before": before, "after": after}


def cloth_weight(bc, part_ids, part_names, team_cfg, tx):
    if not team_cfg["cloth_parts"]:  # a hero without cloth (team_mask.cloth_parts empty): no cloth roughness remap
        return np.zeros(part_ids.shape, np.float32)
    h, s, v = tx.rgb_to_hsv(bc)
    hsv = team_cfg["cloth_hsv"]
    idx = [part_names.index(p) for p in team_cfg["cloth_parts"]]
    w = smooth_le(v, hsv["v_max"], hsv["ramp"]) * smooth_le(s, hsv["s_max"], hsv["ramp"])
    return np.where(np.isin(part_ids, idx), w, 0.0).astype(np.float32)

