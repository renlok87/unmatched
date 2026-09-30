"""Stages `ld_tone_prep` and `ld_tone` (system python): the hero tone of King Arthur measured on the concept.

    python lookdev_tone.py prep <lookdev profile.json> <lookdev run dir>
    python lookdev_tone.py fit  <lookdev profile.json> <lookdev run dir>

prep  restores the previous texture sets (h22 = the H2.2 rev. 2 runtime 2K of the source run, h2 = git show of
      9a2a5184; sha256 checked) and writes emulated v2 sets (lookdev_emul) for the F0 candidates of steel_blued and
      gold_antique (profile lookdev.tone.*.candidates_y; chromaticity of the preset), then work/lookdev/job-tone.json
      for ld_render_tone (studio_env ortho views, Cobble K2 frames, zone ID frames).
fit   measures the concept and the candidate frames:
  steel   the H2.2 relative check (steelcheck.relative_check: (Y_steel / Y_ref)_render / (Y_steel / Y_ref)_concept,
          references = the base stone and the red cloth, geometric mean pooled over front/side/back; the H2.2 concept
          masks and gate), log-log fit over the candidates -> F0 luminance for lookdev.tone.steel.target_relative
          (corrected for the luminance gain of the red cloth, if the cloth tone changes it); chromaticity = the concept
          steel white-balanced on the stone of each frame (concept steel / concept stone x render stone);
  gold    the same relative formula on the gold trims (concept boxes x gold filter vs the gold zone), F0 luminance
          clamped to Y >= 0.45; chromaticity white-balanced as the steel;
  dielectric zones (as Merlin's ld_tone): per zone and view the median linear colour of the concept pixels (boxes x
          HSV filter) and of the render zone (ID frame, eroded); exposure brought to the concept by the stone of the
          same view; gain = chroma (clamped, luminance-preserving) x luma (clamped), median over the views; applied in
          linear light to the zone's BC texels (zone weights blurred 3 x 3 at 4K) unless |gain - 1| < dead_band.
  Then: the look-dev BC / ORM textures (4K master + 2K), Ymed of the metal classes on the final 2K BC, the hero LUT
  (EXR 16 x 8 + reports/ld-lut.json in the format of lookdev_ue_inputs.py), the final emulated sets (no dye, P1, P2
  of the C-11 palette with the TeamAccent mask) and work/lookdev/job-final.json for ld_render_final.
"""

import copy
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lookdev_emul as E  # noqa: E402
import lookdev_lut as LL  # noqa: E402
import lookdev_state as S  # noqa: E402
import pure as P  # noqa: E402
import steelcheck as SC  # noqa: E402
import textures as T  # noqa: E402

LUM = np.array([0.2126, 0.7152, 0.0722])
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
VIEW_OF = {"front": "ortho_front", "side": "ortho_left", "back": "ortho_back"}


def hex_lin(h):
    h = h.lstrip("#")
    return [P.r(float(E.lin(int(h[i:i + 2], 16) / 255.0)), 6) for i in (0, 2, 4)]


def load_ld4k(paths):
    d = paths["work"] / "lookdev" / "ld4k"
    keys = ("bc_ld", "metal_ld", "rough_ld", "ao", "n_gl", "edge", "uv1", "accent", "cls4k", "zone_id", "covered")
    out = {k: np.load(d / (k + ".npy")) for k in keys}
    out["zones"] = {k: v.astype(np.float32) for k, v in np.load(d / "zones.npz").items()}
    return out


def emul_input(l4, bc=None):
    return {"bc": l4["bc_ld"] if bc is None else bc, "ao": l4["ao"], "rough": l4["rough_ld"], "metal": l4["metal_ld"],
            "n_gl": l4["n_gl"], "edge": l4["edge"], "uv1": l4["uv1"], "cls": l4["cls4k"].astype(np.int32)}


def with_f0(cols, cidx, cid, rgb):
    c = copy.deepcopy(cols)
    i = cidx[cid]
    c[i]["bcR"], c[i]["bcG"], c[i]["bcB"] = (float(x) for x in rgb)
    return c


def preset_chroma(presets, cid):
    c = next(x for x in presets["classes"] if x["id"] == cid)
    rgb = np.array(c["baseColor"]["typicalLinear"], np.float64)
    return rgb / float(rgb @ LUM)


def prev_sets(prof, paths, src, src_run):
    """h22 (source run runtime 2K) and h2 (git show <commit>) -> work/prev/<label>/{BC,ORM,N_OpenGL}.png."""
    out = {}
    prefix = src["textures"]["prefix"]
    for label, cfg in prof["lookdev"]["previous_sets"].items():
        if not isinstance(cfg, dict):
            continue
        d = paths["work"] / "prev" / label
        d.mkdir(parents=True, exist_ok=True)
        for key, sha in cfg["runtime_2k_sha256"].items():
            f = d / (key + ".png")
            srcf = src_run / "textures" / "runtime_2k" / ("%s_%s.png" % (prefix, key))
            if not f.exists() or P.sha256(f) != sha:
                if P.sha256(srcf) == sha:
                    f.write_bytes(srcf.read_bytes())
                else:
                    spec = "%s:%s" % (cfg["commit"], P.rel(srcf))
                    f.write_bytes(subprocess.run(["git", "-C", str(P.REPO), "-c", "core.longpaths=true", "show", spec],
                                                 capture_output=True, check=True, creationflags=NO_WINDOW).stdout)
            if P.sha256(f) != sha:
                raise SystemExit("previous set %s %s: sha256 %s != %s" % (label, key, P.sha256(f), sha))
        out[label] = str(d)
    return out


def base_columns(prof, paths, presets, ymed=None):
    ld = prof["lookdev"]
    rep = P.load_json(paths["reports"] / "ld-maps-report.json")
    ymed = ymed or rep["ymed_bake_2k"]
    return E.columns(presets, ld["lut_overrides"], ld["ue_lut_fields"], ymed)


def prep(prof_path, run):
    prof, paths, src, src_run, _cache = S.lookdev_paths(prof_path, run)
    ld = prof["lookdev"]
    presets = P.load_json(P.repo_path(ld["presets"]))
    cidx = {c["id"]: int(c["index"]) for c in presets["classes"]}
    prev = prev_sets(prof, paths, src, src_run)
    cols, _merged, _applied = base_columns(prof, paths, presets)
    l4 = load_ld4k(paths)
    slices = E.Slices(presets, paths["work"] / "lookdev" / "slices")
    inp = emul_input(l4)
    tc = ld["tone"]
    sy, gy = tc["steel"]["candidates_y"], tc["gold"]["candidates_y"]
    sch, gch = preset_chroma(presets, "steel_blued"), preset_chroma(presets, "gold_antique")
    sets = dict(prev)
    cands = {}
    for i, ys in enumerate(sy):
        yg = gy[min(i, len(gy) - 1)]
        c = with_f0(with_f0(cols, cidx, "steel_blued", sch * ys), cidx, "gold_antique", gch * yg)
        em, stats = E.emulate(inp, c, slices)
        label = "cand%d" % i
        files = E.write_set(em, paths["work"] / "lookdev" / "sets" / label)
        cands[label] = {"steel_Y": ys, "gold_Y": yg, "steel_f0": P.rv(sch * ys, 5), "gold_f0": P.rv(gch * yg, 5),
                        "files": files, "class_stats": stats}
        sets[label] = str(paths["work"] / "lookdev" / "sets" / label)
        print("candidate", label, ys, yg, flush=True)
    rc = ld["render"]
    job = {"out": str(paths["work"] / "lookdev" / "render_tone"), "sets": sets,
           "lights": {"studio_env": rc["tone_views"], "cobble": rc["tone_cobble_views"]},
           "id_sets": {"zones": str(paths["work"] / "lookdev" / "id" / "zones.png")},
           "id_views": rc["tone_views"] + rc["tone_cobble_views"], "calibrate": True}
    P.write_json(paths["work"] / "lookdev" / "job-tone.json", job)
    P.write_json(paths["reports"] / "ld-tone-prep-report.json",
                 {"stage": "ld_tone_prep", "previous_sets": {k: P.rel(v) for k, v in prev.items()},
                  "candidates": cands, "job": P.rel(paths["work"] / "lookdev" / "job-tone.json")})
    print(P.STAGE_MARKER, "ld_tone_prep", sorted(sets))


# ------------------------------------------------------------------ measurement helpers
def load_img(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0


def hsv_filter(img, f):
    h, s, v = SC.hsv_img(img)
    m = np.ones(h.shape, bool)
    if "hue" in f:
        lo, hi = f["hue"]
        m &= (h >= lo) & (h <= hi) if lo <= hi else (h >= lo) | (h <= hi)
    for k, arr, op in (("s_min", s, np.greater_equal), ("s_max", s, np.less_equal), ("v_min", v, np.greater_equal),
                       ("v_max", v, np.less_equal)):
        if k in f:
            m &= op(arr, float(f[k]))
    return m


def concept_zone_mask(img, entries, filters, zone):
    m = np.zeros(img.shape[:2], bool)
    for e in entries:
        if e["zone"] != zone:
            continue
        x0, y0, x1, y1 = e["box"]
        b = np.zeros(img.shape[:2], bool)
        b[y0:y1, x0:x1] = True
        m |= b & hsv_filter(img, filters[e["filter"]])
    return m


def zone_render_mask(idimg, rgb, erode):
    m = np.abs(idimg * 255.0 - np.array(rgb)).sum(axis=2) <= 3
    return ndimage.binary_erosion(m, iterations=int(erode)) if erode else m


def lin_stats(img, mask):
    li = E.lin(img[mask])
    if not len(li):
        return None
    return {"n": int(mask.sum()), "mean_rgb": li.mean(0), "median_rgb": np.median(li, 0), "Y_mean": float((li @ LUM).mean())}


def chroma(rgb):
    rgb = np.asarray(rgb, np.float64)
    return rgb / max(float(rgb @ LUM), 1e-9)


def fit_loglog(xs, ys, target):
    """least squares log(y) = a + b log(x); returns x with y = target and (a, b)."""
    lx, ly = np.log(np.asarray(xs)), np.log(np.asarray(ys))
    b, a = np.polyfit(lx, ly, 1)
    return float(np.exp((np.log(target) - a) / b)), (float(a), float(b))


def interp_loglog(xs, ys, x):
    lx, ly = np.log(np.asarray(xs)), np.log(np.asarray(ys))
    b, a = np.polyfit(lx, ly, 1)
    return float(np.exp(a + b * np.log(x)))


def cobble_steel(render_dir, id_dir, views, sets, rgb):
    """steel (zone mask, no gate) mean Y / board median Y (top 10 % rows), as steelcheck's cobble check."""
    out = {}
    for v in views:
        idimg = load_img(id_dir / (v + ".png"))
        m = zone_render_mask(idimg, rgb, 2)
        e = {}
        for s in sets:
            f = render_dir / s / (v + ".png")
            if not f.exists():
                continue
            im = load_img(f)
            board = float(np.median(E.lin(im[:im.shape[0] // 10].reshape(-1, 3)) @ LUM))
            y = E.lin(im[m]) @ LUM
            e[s] = {"steel_Y_mean": P.r(y.mean(), 5), "board_Y_median_top_rows": P.r(board, 5),
                    "steel_over_board": P.r(float(y.mean()) / board, 4), "pixels": int(m.sum()),
                    "share_display_max_channel_ge_0.85": P.r(float((im[m].max(axis=1) >= 0.85).mean()), 5)}
        out[v] = e
    return out


def measure(prof, src, render_dir, id_dir, sets):
    """Concept vs render (studio_env ortho frames): steel relative check (H2.2), gold relative, colours per zone,
    stone white balance. Returns a dict per set."""
    ld = prof["lookdev"]
    sc = src["review_h22"]["steel_check"]
    g = sc["gate"]
    rel = SC.relative_check(src, sc, render_dir, id_dir, sets, g)
    cz = ld["concept_zones"]
    filters = cz["filters"]
    zrgb = __import__("lookdev_maps").ZONE_RGB
    erode = int(ld["render"]["id_erode_px"])
    per = {s: {"views": {}} for s in sets}
    concept = {}
    for view, rview in VIEW_OF.items():
        cimg = load_img(P.repo_path(src["sources"]["concepts"][view]))
        stone_c = SC.zone_mask(cimg.shape, [{"rect": sc["relative"]["references"]["stone"]["concept_rects"][view]}])
        red_c = SC.colour_gate(cimg, sc["relative"]["references"]["red_cloth"]["gate"])
        steel_c = SC.zone_mask(cimg.shape, sc["concept_zones"][view]) & SC.gate(cimg, g)
        ce = {"stone": lin_stats(cimg, stone_c), "red_ref": lin_stats(cimg, red_c), "steel": lin_stats(cimg, steel_c)}
        for zone in {e["zone"] for e in cz[view]}:
            ce["zone:" + zone] = lin_stats(cimg, concept_zone_mask(cimg, cz[view], filters, zone))
        concept[view] = ce
        idimg = load_img(id_dir / (rview + ".png"))
        masks = {z: zone_render_mask(idimg, rgb, erode) for z, rgb in zrgb.items()}
        masks["stone"] = zone_render_mask(idimg, zrgb["base"], 3)
        for s in sets:
            f = render_dir / s / (rview + ".png")
            if not f.exists():
                continue
            img = load_img(f)
            re_ = {"stone": lin_stats(img, masks["stone"]),
                   "red_ref": lin_stats(img, masks["cloth"] & SC.colour_gate(img, sc["relative"]["references"]["red_cloth"]["gate"])),
                   "steel": lin_stats(img, masks["steel_plate"] & SC.gate(img, g))}
            for z in zrgb:
                re_["zone:" + z] = lin_stats(img, masks[z])
            per[s]["views"][view] = re_
    return rel, concept, per


def rel_ratio(concept, per_set, key_c, key_r, refs=("stone", "red_ref")):
    """(Y_zone / Y_ref)_render / (Y_zone / Y_ref)_concept, pooled over the views (sums of Y), geometric mean over refs."""
    acc = {k: [0.0, 0, 0.0, 0] for k in ("z",) + refs}
    for view, ce in concept.items():
        re_ = per_set["views"].get(view)
        if not re_ or ce.get(key_c) is None or re_.get(key_r) is None:
            continue
        acc["z"][0] += ce[key_c]["Y_mean"] * ce[key_c]["n"]; acc["z"][1] += ce[key_c]["n"]
        acc["z"][2] += re_[key_r]["Y_mean"] * re_[key_r]["n"]; acc["z"][3] += re_[key_r]["n"]
        for r in refs:
            acc[r][0] += ce[r]["Y_mean"] * ce[r]["n"]; acc[r][1] += ce[r]["n"]
            acc[r][2] += re_[r]["Y_mean"] * re_[r]["n"]; acc[r][3] += re_[r]["n"]
    m = {k: (v[0] / max(v[1], 1), v[2] / max(v[3], 1)) for k, v in acc.items()}
    ratios = {r: (m["z"][1] / m[r][1]) / (m["z"][0] / m[r][0]) for r in refs}
    return float(np.exp(np.mean(np.log(list(ratios.values()))))), ratios


def wb_chroma(concept, per_set, key_c, key_r):
    """target render chromaticity of a zone: concept chroma / concept stone chroma x render stone chroma (per view,
    pixel-weighted mean of the chromaticities), and the rendered chroma of the zone."""
    tgt, got, w = np.zeros(3), np.zeros(3), 0.0
    for view, ce in concept.items():
        re_ = per_set["views"].get(view)
        if not re_ or ce.get(key_c) is None or re_.get(key_r) is None:
            continue
        n = min(ce[key_c]["n"], re_[key_r]["n"])
        t = chroma(ce[key_c]["mean_rgb"]) / chroma(ce["stone"]["mean_rgb"]) * chroma(re_["stone"]["mean_rgb"])
        tgt += chroma(t) * n
        got += chroma(re_[key_r]["mean_rgb"]) * n
        w += n
    return chroma(tgt / w), chroma(got / w)


def dielectric_gains(prof, concept, per_set):
    tc = prof["lookdev"]["tone"]["dielectric"]
    out = {}
    for z in tc["zones"]:
        gs, views = [], {}
        for view, ce in concept.items():
            c = ce.get("zone:" + z)
            r = per_set["views"].get(view, {}).get("zone:" + z)
            if c is None or r is None or c["n"] < tc["min_view_pixels"] or r["n"] < tc["min_view_pixels"]:
                continue
            k = ce["stone"]["Y_mean"] / per_set["views"][view]["stone"]["Y_mean"]   # render -> concept exposure
            cm, rm = c["median_rgb"], r["median_rgb"] * k
            ch = np.clip(chroma(cm) / chroma(rm), *tc["chroma_clamp"])
            ch = ch / float((chroma(rm) * ch) @ LUM)      # the chroma part keeps the zone's luminance
            lu = float(np.clip((cm @ LUM) / (rm @ LUM), *tc["luma_clamp"]))
            gv = ch * lu
            gs.append(gv)
            views[view] = {"concept_median_linear": P.rv(cm, 5), "render_median_linear_x_k": P.rv(rm, 5),
                           "k_stone": P.r(k, 4), "gain": P.rv(gv, 4), "pixels_concept": c["n"], "pixels_render": r["n"]}
        if not gs:
            out[z] = {"views": views, "gain": [1.0, 1.0, 1.0], "applied": False, "why": "no view with enough pixels"}
            continue
        gain = np.median(np.array(gs), 0)
        gain = np.round(gain / 0.01) * 0.01
        applied = bool(np.abs(gain - 1).max() >= tc["dead_band"])
        out[z] = {"views": views, "gain": P.rv(gain, 3), "applied": applied}
    return out


def zone_hsv_summary(rgb_lin):
    s = E.srgb(np.asarray(rgb_lin, np.float64)[None, None, :])
    h, sat, v = SC.hsv_img(s)
    return {"Y": P.r(float(np.asarray(rgb_lin) @ LUM), 5), "hue_deg": P.r(float(h[0, 0]), 1), "sat": P.r(float(sat[0, 0]), 3)}


def fit(prof_path, run):
    prof, paths, src, src_run, _cache = S.lookdev_paths(prof_path, run)
    ld = prof["lookdev"]
    tc = ld["tone"]
    presets = P.load_json(P.repo_path(ld["presets"]))
    cidx = {c["id"]: int(c["index"]) for c in presets["classes"]}
    prep_rep = P.load_json(paths["reports"] / "ld-tone-prep-report.json")
    cands = prep_rep["candidates"]
    rdir = paths["work"] / "lookdev" / "render_tone"
    render_dir, id_dir = rdir / "studio_env", rdir / "id" / "zones"
    sets = ["h22", "h2"] + sorted(cands)
    rel, concept, per = measure(prof, src, render_dir, id_dir, sets)
    rep = {"stage": "ld_tone", "profile": P.rel(prof_path), "sets": sets, "steel_relative_h22_method": rel["pooled"],
           "concept": {v: {k: (None if e is None else {"n": e["n"], "Y_mean": P.r(e["Y_mean"], 5),
                                                       "chroma": P.rv(chroma(e["mean_rgb"]), 4)})
                           for k, e in ce.items()} for v, ce in concept.items()}}
    # ---------------------------------------------------------------- dielectric zones (on a candidate: dielectrics equal)
    base_set = sorted(cands)[0]
    gains = dielectric_gains(prof, concept, per[base_set])
    rep["dielectric"] = gains
    g_cloth = np.array(gains.get("cloth", {}).get("gain", [1, 1, 1])) if gains.get("cloth", {}).get("applied") else np.ones(3)
    # red reference of the render scales with the cloth luminance gain (diffuse)
    gY_cloth = 1.0
    if gains.get("cloth", {}).get("applied"):
        rr = [per[base_set]["views"][v]["red_ref"]["median_rgb"] for v in concept if per[base_set]["views"].get(v)]
        base_c = np.mean([chroma(x) for x in rr], 0)
        gY_cloth = float((base_c * g_cloth) @ LUM / (base_c @ LUM))
    # ---------------------------------------------------------------- steel
    st_cfg = tc["steel"]
    ys = [cands[c]["steel_Y"] for c in sorted(cands)]
    rels, rels_raw = [], {}
    for c in sorted(cands):
        gm, rr = rel_ratio(concept, per[c], "steel", "steel")
        rr_adj = dict(rr, red_ref=rr["red_ref"] / gY_cloth)
        rels.append(float(np.exp(np.mean(np.log(list(rr_adj.values()))))))
        rels_raw[c] = {"geomean": P.r(gm, 4), "by_reference": {k: P.r(v, 4) for k, v in rr.items()},
                       "geomean_after_cloth_gain": P.r(rels[-1], 4),
                       "h22_method_pooled": rel["pooled"].get(c)}
    y_rel, ab = fit_loglog(ys, rels, float(st_cfg["target_relative"]))
    cob = cobble_steel(rdir / "cobble", id_dir, ld["render"]["tone_cobble_views"], sets, __import__("lookdev_maps").ZONE_RGB["steel_plate"])
    # the darkest steel that is not black on the board: the mean steel / board of the Cobble K2 frames at the lower
    # end of cobble_range, unless the relative target already gives more; never above the relative tolerance
    cob_mean = [float(np.mean([cob[v][c]["steel_over_board"] for v in cob])) for c in sorted(cands)]
    y_cob, ab_cob = fit_loglog(ys, cob_mean, float(st_cfg["cobble_range"][0]))
    rel_hi = 1.0 + float(src["review_h22"]["steel_check"]["relative"]["tolerance"])
    y_relhi, _ = fit_loglog(ys, rels, rel_hi)
    y_star = float(np.clip(min(max(y_rel, y_cob), y_relhi), *st_cfg["y_clamp"]))
    rule = ("Y_cobble_floor" if y_cob > y_rel else "Y_relative_target") if y_star < y_relhi else "Y_relative_upper_bound"
    cob_pred = {v: P.r(interp_loglog(ys, [cob[v][c]["steel_over_board"] for c in sorted(cands)], y_star), 4) for v in cob}
    cob_pred["mean"] = P.r(interp_loglog(ys, cob_mean, y_star), 4)
    rel_pred = interp_loglog(ys, rels, y_star)
    near = sorted(cands)[int(np.argmin([abs(np.log(y / y_star)) for y in ys]))]
    tgt_c, got_c = wb_chroma(concept, per[near], "steel", "steel")
    f0_cand = np.array(cands[near]["steel_f0"])
    f0_ch = chroma(chroma(f0_cand) * tgt_c / got_c)
    # quantised to 0.001: the fit reads EEVEE frames (ray-traced noise moves it by ~2e-5 run to run), the LUT must not
    steel_f0 = np.round(f0_ch * y_star, 3)
    rep["steel"] = {"candidates": {c: {"Y": cands[c]["steel_Y"], "f0": cands[c]["steel_f0"]} | rels_raw[c]
                                   | {"cobble": {v: cob[v][c]["steel_over_board"] for v in cob}} for c in sorted(cands)},
                    "previous": {s: {"relative_h22_method": rel["pooled"].get(s),
                                     "cobble": {v: cob[v].get(s, {}).get("steel_over_board") for v in cob}} for s in ("h22", "h2")},
                    "cloth_luminance_gain_on_red_reference": P.r(gY_cloth, 4),
                    "fit_loglog_a_b": P.rv(ab, 4), "target_relative": st_cfg["target_relative"],
                    "Y_at_target_relative": P.r(y_rel, 5), "Y_at_cobble_floor": P.r(y_cob, 5),
                    "Y_at_relative_upper_bound": P.r(y_relhi, 5), "rule_applied": rule, "Y_fit": P.r(y_star, 5),
                    "relative_predicted_at_fit": P.r(rel_pred, 4),
                    "cobble_predicted_at_fit": cob_pred, "chroma_target_wb": P.rv(tgt_c, 4),
                    "chroma_rendered_at": {"set": near, "chroma": P.rv(got_c, 4)},
                    "f0": P.rv(steel_f0, 5), "f0_hsv": zone_hsv_summary(steel_f0),
                    "preset_f0": P.rv(np.array(next(c for c in presets["classes"] if c["id"] == "steel_blued")["baseColor"]["typicalLinear"]), 5)}
    # ---------------------------------------------------------------- gold
    gc = tc["gold"]
    gys = sorted({cands[c]["gold_Y"] for c in cands})
    g_rel = {}
    for c in sorted(cands):
        gm, rr = rel_ratio(concept, per[c], "zone:gold", "zone:gold")
        g_rel[cands[c]["gold_Y"]] = float(np.exp(np.mean(np.log([rr["stone"], rr["red_ref"] / gY_cloth]))))
    gy_star, gab = fit_loglog(gys, [g_rel[y] for y in gys], 1.0) if len(gys) > 1 else (gys[0], (0, 1))
    gy_star = float(max(gy_star, float(gc["y_min"])))
    near_g = next(c for c in sorted(cands) if abs(cands[c]["gold_Y"] - gys[-1]) < 1e-9)
    gt, gg = wb_chroma(concept, per[near_g], "zone:gold", "zone:gold")
    gold_f0 = chroma(chroma(np.array(cands[near_g]["gold_f0"])) * gt / gg) * gy_star
    if gold_f0.max() > 1.0:
        gold_f0 = gold_f0 / gold_f0.max()
    gold_f0 = np.round(gold_f0, 3)
    rep["gold"] = {"relative_by_Y": {str(k): P.r(v, 4) for k, v in g_rel.items()}, "fit_loglog_a_b": P.rv(gab, 4),
                   "Y_fit_clamped": P.r(gy_star, 5), "chroma_target_wb": P.rv(gt, 4), "chroma_rendered": P.rv(gg, 4),
                   "f0": P.rv(gold_f0, 5), "f0_Y": P.r(float(gold_f0 @ LUM), 4), "f0_hsv": zone_hsv_summary(gold_f0),
                   "preset_f0_hsv": zone_hsv_summary(np.array([1.0, 0.766, 0.336]))}
    # ---------------------------------------------------------------- final BC / ORM (4K + 2K)
    l4 = load_ld4k(paths)
    bc = l4["bc_ld"].astype(np.float32).copy()
    mult = np.ones(bc.shape, np.float32)
    for z, e in gains.items():
        if not e["applied"]:
            continue
        w = ndimage.uniform_filter(l4["zones"][z], 3, mode="nearest")[..., None]
        mult += w * (np.array(e["gain"], np.float32) - 1.0)
    # 5c-B0 (2026-09-30): UE feedback gains per zone (profile lookdev.tone.ue_feedback), fitted on the UE look-dev
    # frames against the concept (tools/art/material_library/ue_bc_feedback.py), multiplied onto the concept-tone
    # BC of the zone with the same blurred zone weights
    fb = {z: v for z, v in (tc.get("ue_feedback") or {}).items() if isinstance(v, dict) and "gain" in v}
    for z, e in fb.items():
        w = ndimage.uniform_filter(l4["zones"][z], 3, mode="nearest")[..., None]
        mult *= 1.0 + w * (np.array(e["gain"], np.float32) - 1.0)
    rep["ue_feedback"] = {z: {"gain": e["gain"], "source": e.get("source")} for z, e in fb.items()}
    bc = np.clip(bc * mult, 0, 1)
    tex = paths["textures"]
    px = ld["prefix"]
    orm4 = np.stack([l4["ao"], l4["rough_ld"], l4["metal_ld"]], -1)
    outs = {}
    for key, a4, mode in (("BC", T.q8(T.srgb(bc)), "RGB"), ("ORM", T.q8(orm4), "RGB")):
        outs[key + "_4K"] = T.save_png(a4, tex / ("%s_%s_4K.png" % (px, key)), mode)
    outs["BC_2K"] = T.save_png(T.q8(T.srgb(T.box2(bc))), tex / ("%s_BC_2K.png" % px), "RGB")
    outs["ORM_2K"] = T.save_png(T.q8(np.stack([T.box2(l4["ao"]), T.box2(l4["rough_ld"]), T.box2(l4["metal_ld"])], -1)),
                                tex / ("%s_ORM_2K.png" % px), "RGB")
    np.save(paths["work"] / "lookdev" / "ld4k" / "bc_final.npy", bc)
    # ---------------------------------------------------------------- Ymed + LUT
    bc2 = E.lin(np.asarray(Image.open(tex / ("%s_BC_2K.png" % px)), np.float64) / 255.0) @ LUM
    matid = np.asarray(Image.open(tex / ("%s_MatID_2K.png" % px))).astype(np.int32) // 16
    cov2 = T.box2(l4["covered"].astype(np.float32)) >= 0.5
    ymed, diel = {}, {}
    for cid in ("steel_blued", "steel_polished", "gold_antique"):
        ymed[cid] = P.r(float(np.median(bc2[(matid == cidx[cid]) & cov2])), 5)
    bc2rgb = E.lin(np.asarray(Image.open(tex / ("%s_BC_2K.png" % px)), np.float64) / 255.0)
    ue_fields = copy.deepcopy(ld["ue_lut_fields"])
    blender_ov = copy.deepcopy(ld["lut_overrides"])
    floors = {}
    for cid in ("wool_coarse", "silk", "leather_worn", "skin", "stone_base"):
        sel = (matid == cidx[cid]) & cov2
        y = bc2[sel]
        med = np.median(bc2rgb[sel], 0)
        diel[cid] = {"Y_p2_p50_p98": P.rv(np.percentile(y, [2, 50, 98]), 5), "median_linear": P.rv(med, 5)}
        blender_ov.setdefault(cid, {})["baseColor"] = {"typicalLinear": P.rv(med, 5)}
        pc = next(c for c in presets["classes"] if c["id"] == cid)
        lo = float(pc["baseColor"]["luminanceRange"][0])
        p2 = float(np.percentile(y, 2))
        if p2 < lo:
            floors[cid] = float(np.floor(p2 * 1000) / 1000)
            ue_fields.setdefault(cid, {})["luminanceMin"] = floors[cid]
            ue_fields[cid]["why"] = "bake p2 Y %.4f below the preset floor %.3f (UE-0 of Merlin)" % (p2, lo)
    for cid, f0 in (("steel_blued", steel_f0), ("gold_antique", gold_f0)):
        blender_ov.setdefault(cid, {})["baseColor"] = {"typicalLinear": P.rv(f0, 5)}
    for cid, y in ymed.items():
        blender_ov.setdefault(cid, {})["heroYmed"] = y
    cols, merged, applied = E.columns(presets, {k: {kk: vv for kk, vv in v.items() if kk != "heroYmed"} for k, v in blender_ov.items()},
                                      ue_fields, ymed)
    import build_ue_inputs as B
    lut16 = B.lut_array(cols)
    exr = LL.exr_rows(lut16, {cidx[c]: y for c, y in ymed.items()})
    exr_path = tex / ("%s_MatLUT.exr" % px)
    LL.write_exr(exr_path, exr)
    back = LL.read_exr(exr_path).astype(np.float32)
    exr_ok = bool(np.array_equal(back, exr.astype(np.float16).astype(np.float32)))
    lut_doc = {"stage": "ld_tone", "hero": ld["hero"], "presets": ld["presets"], "presets_sha256": P.sha256(P.repo_path(ld["presets"])),
               "file": {"path": P.rel(exr_path), "sha256": P.sha256(exr_path), "bytes": exr_path.stat().st_size,
                        "readback_equal": exr_ok},
               "format": "OpenEXR scanline, uncompressed, HALF RGBA, 16 x 8; row 0 = top = EXR y 0 = Load(int3(id, row, 0)); "
                         "rows 0-7 = README section 4; ymedClassHero of the metal columns also in row 7.R (LDM-7); "
                         "the UE LUT 16 x 16 is rebuilt from 'overrides' + 'ue_lut_fields' by lookdev_ue_inputs.py",
               "overrides": blender_ov, "ue_lut_fields": ue_fields, "luminance_floors_added": floors,
               "measured_sources": {"steel_blued.baseColor": "reports/ld-tone-report.json#steel",
                                    "gold_antique.baseColor": "reports/ld-tone-report.json#gold",
                                    "heroYmed": "median Y of the final 2K BC inside the MatID class",
                                    "dielectric baseColor.typicalLinear": "median linear BC of the class (reference only: bake-clamped path)"},
               "columns_v2": {str(i): {k: (round(v, 6) if isinstance(v, float) else v) for k, v in sorted(f.items())}
                              for i, f in sorted(cols.items())},
               "applied": applied, "rows_exr": [list(B.LUT_ROWS[r]) for r in range(8)],
               "half_values_rows_top_to_bottom": [[P.rv(exr.astype(np.float16)[r, i].astype(np.float64), 5) for i in range(16)]
                                                  for r in range(8)]}
    P.write_json(paths["reports"] / "ld-lut.json", lut_doc)
    np.save(paths["work"] / "lookdev" / "lut16.npy", lut16)
    # ---------------------------------------------------------------- TeamDyeGain of the MI (team-accent.md rule)
    ta = ld["team_accent"]
    acc_sel = (l4["accent"] >= 0.5) & l4["covered"]
    ya = np.clip(bc[acc_sel] @ LUM.astype(np.float32), 0.02, 0.8)
    ymed_a, yp95_a = float(np.median(ya)), float(np.percentile(ya, 95))
    tmax = max(max(hex_lin(h)) for h in (ta["palette"]["P1"], ta["palette"]["P2"]))
    gr = ta["team_dye_gain_rule"]
    g_med = float(gr["median_target"]) / ymed_a
    g_p95 = float(gr["p95_max_albedo"]) / (tmax * yp95_a)
    dye_gain = float(np.floor(min(g_med, g_p95) / gr["round_to"]) * gr["round_to"])
    rep["team_dye_gain"] = {"accent_Y_p50_p95": [P.r(ymed_a, 5), P.r(yp95_a, 5)], "gain_for_median": P.r(g_med, 3),
                            "gain_for_p95": P.r(g_p95, 3), "palette_max_channel_linear": P.r(tmax, 4), "TeamDyeGain": dye_gain,
                            "dyed_accent_albedo_median_over_team": P.r(ymed_a * dye_gain, 4),
                            "dyed_accent_albedo_p95_max_channel": P.r(yp95_a * dye_gain * tmax, 4), "rule": gr["note"]}
    lut_doc["mi_parameters"] = {"TeamDye": ta["team_dye"], "TeamDyeGain": dye_gain,
                                "TeamMaskTexture": "T_%s_TeamAccent (textures/%s_TeamAccent_2K.png)" % (px[2:], px),
                                "note": "M_UM_Figure_v2 MI parameters of the proposal (import profile figure_parameters); "
                                        "TeamDyeGain from the team-accent.md rule, see reports/ld-tone-report.json#team_dye_gain"}
    P.write_json(paths["reports"] / "ld-lut.json", lut_doc)
    # ---------------------------------------------------------------- final emulated sets
    slices = E.Slices(presets, paths["work"] / "lookdev" / "slices")
    inp = emul_input(l4, bc=bc)
    finals, fstats = {}, {}
    for label, team in (("ld", None), ("ld_p1", hex_lin(ta["palette"]["P1"])), ("ld_p2", hex_lin(ta["palette"]["P2"]))):
        em, stats = E.emulate(inp, cols, slices, team=team, dye=ta["team_dye"], dye_gain=dye_gain,
                              mask=l4["accent"])
        d = paths["work"] / "lookdev" / "sets" / label
        fstats[label] = {"team_linear": team, "files": E.write_set(em, d), "class_stats": stats}
        finals[label] = str(d)
        if label == "ld":
            # the neutral emulation as a 1K preview of the look-dev material (atlas)
            prev = T.q8(T.srgb(T.box2(T.box2(em["bc"]))))
            T.save_png(prev, paths["preview"] / "ld_emulated_bc_1K.png", "RGB")
        print("final set", label, flush=True)
    rep["final_sets"] = fstats
    rep["ymed_final_2k"] = ymed
    rep["dielectric_final_2k"] = diel
    rep["textures"] = outs
    prev = {k: v for k, v in prev_sets(prof, paths, src, src_run).items()}
    rc = ld["render"]
    job = {"out": str(paths["work"] / "lookdev" / "render_final"),
           "sets": {"h22": prev["h22"], "h2": prev["h2"], **finals},
           "lights": {"studio_env": rc["final_views_studio"], "cobble": rc["final_views_cobble"]},
           "id_sets": {"zones": str(paths["work"] / "lookdev" / "id" / "zones.png"),
                       "accent": str(paths["work"] / "lookdev" / "id" / "accent.png"),
                       "tabard": str(paths["work"] / "lookdev" / "id" / "tabard.png")},
           "id_views": sorted(set(rc["final_views_studio"] + rc["final_views_cobble"])), "calibrate": False}
    P.write_json(paths["work"] / "lookdev" / "job-final.json", job)
    P.write_json(paths["reports"] / "ld-tone-report.json", rep)
    print(P.STAGE_MARKER, "ld_tone steel Y %.4f f0 %s gold f0 %s cloth gain %s" % (y_star, P.rv(steel_f0, 4), P.rv(gold_f0, 4),
                                                                                   gains.get("cloth", {}).get("gain")))


if __name__ == "__main__":
    {"prep": prep, "fit": fit}[sys.argv[1]](sys.argv[2], sys.argv[3])
