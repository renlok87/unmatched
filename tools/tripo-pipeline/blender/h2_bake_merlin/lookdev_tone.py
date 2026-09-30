"""Stage `ld_tone` (system python): concept-matched BC tone per zone + the hero LUT of Merlin.

python lookdev_tone.py <lookdev profile.json>

1. Concept: per view (front / side = right / back) and zone, the pixels inside the profile boxes that pass the zone's
   HSV filter (concept_zones); median colour in linear light. Overlays preview/ld_concept_zones_<view>.png.
2. Model: the H2.1 textures rendered by ld_render_before in the same Blender studio light and the concept framing;
   zone pixels from the zone-ID pass of the same camera (eroded id_erode_px, alpha 1); median in linear light.
3. ratio_zone = concept / model per linear channel, per view, median over the views with >= min_views_pixels on both
   sides; k = median over zones of the luminance ratio (the concept's exposure and light are unknown, so only the
   zones' colours relative to each other are matched). gain = chroma x luma: chroma = the ratio normalised to keep the
   luminance of the zone's model median (hue / saturation of the concept, clamp chroma_clamp); luma = zone luminance
   ratio / k clamped to luma_clamp (a luminance ratio also carries the concept's light: face 0.84-1.18 vs hands
   1.71-1.78 on the same skin); dead band, quantised.
4. BC: gains applied in linear light at 4K on the zone map (3 x 3 box so zone edges blend), 2K = exact 2 x 2 box
   (linear) as maps.py -> textures/<prefix>_BC_{4K,2K}.png.
5. LUT: presets v1 + profile lut_overrides + measured hero values: row 0 (BC typical) of every dielectric class
   present = median linear BC after the tone match inside the class (concept-matched tone); metal (bronze): row 7.R
   Ymed_class_hero = median luminance of the baked BC in the class (README §4) -> textures/<prefix>_MatLUT.exr
   (16 x 8 RGBA16F), reports/ld-lut.json (every value, float16 rows, per-class source).
Report: reports/ld-tone-report.json (per zone and view: pixel counts, concept / model medians, luma, hue, saturation).
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import lookdev_lut as L  # noqa: E402
import lookdev_maps as LM  # noqa: E402
import maps as M  # noqa: E402

VIEWS = {"front": "front", "side": "right", "back": "back"}  # concept view -> render view
LUM = np.array([0.2126, 0.7152, 0.0722])


def hsv_of_linear(rgb):
    s = M.srgb_encode(np.clip(np.asarray(rgb, np.float64), 0, 1))[None, :]
    h, sat, v = M.rgb_to_hsv(s)
    return float(h[0]), float(sat[0]), float(v[0])


def describe(rgb):
    h, s, v = hsv_of_linear(rgb)
    return {"linear": C.rv(rgb, 5), "luma_Y": C.r(float(np.dot(rgb, LUM)), 5), "hue_deg": C.r(h, 1), "sat": C.r(s, 4), "value": C.r(v, 4)}


def filt_mask(img_srgb, f):
    h, s, v = M.rgb_to_hsv(img_srgb)
    m = np.ones(h.shape, bool)
    if "hue" in f:
        m &= (h >= f["hue"][0]) & (h <= f["hue"][1])
    for key, arr, op in (("s_min", s, np.greater_equal), ("v_min", v, np.greater_equal), ("s_max", s, np.less_equal), ("v_max", v, np.less_equal)):
        if key in f:
            m &= op(arr, f[key])
    return m


def concept_zones(prof, ld):
    cz = ld["concept_zones"]
    res = {}
    overlays = {}
    for view in VIEWS:
        path = C.repo_path(prof_concept(prof, ld, view))
        with Image.open(path) as im:
            srgb = np.asarray(im.convert("RGB")).astype(np.float64) / 255.0
        lin = M.srgb_decode(srgb)
        masks = {}
        for z in cz[view]:
            x0, y0, x1, y1 = z["box"]
            m = np.zeros(srgb.shape[:2], bool)
            m[y0:y1, x0:x1] = True
            m &= filt_mask(srgb, cz["filters"][z["filter"]])
            masks[z["zone"]] = masks.get(z["zone"], np.zeros_like(m)) | m
        res[view] = {k: {"pixels": int(m.sum()), "median": np.median(lin[m], 0) if m.any() else None} for k, m in masks.items()}
        ov = (srgb * 0.35)
        for k, m in masks.items():
            ov[m] = LM.ZONE_COLOURS[k]
        img = Image.fromarray(M.to8(ov), "RGB")
        d = ImageDraw.Draw(img)
        for z in cz[view]:
            d.rectangle(z["box"], outline=tuple(int(c * 255) for c in LM.ZONE_COLOURS[z["zone"]]))
        out = prof.preview / ("ld_concept_zones_%s.png" % view)
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, format="PNG", optimize=False, compress_level=9)
        overlays[view] = {"path": C.rel(out), "sha256": C.sha256(out)}
    return res, overlays


def prof_concept(prof, ld, view):
    src = C.Profile(C.repo_path(ld["source_profile"]))
    return src["concepts"][view]


def model_zones(prof, ld, order):
    rdir = prof.work / "lookdev" / "render"
    er = int(ld["render"]["id_erode_px"])
    res = {}
    for cview, rview in VIEWS.items():
        with Image.open(rdir / ("%s_zone.png" % rview)) as im:
            zp = np.asarray(im.convert("RGBA")).astype(np.int32)
        with Image.open(rdir / ("%s_lit_before.png" % rview)) as im:
            lin = M.srgb_decode(np.asarray(im.convert("RGB")).astype(np.float64) / 255.0)
        solid = zp[..., 3] == 255
        val = zp[..., 0]
        ok = solid & (np.abs(val % 16 - 8) <= 2)
        zid = np.where(ok, val // 16, -1)
        out = {}
        for i, k in enumerate(order):
            m = ndimage.binary_erosion(zid == i, iterations=er) if er else (zid == i)
            out[k] = {"pixels": int(m.sum()), "median": np.median(lin[m], 0) if m.any() else None}
        out["_id_pixels_valid_share"] = C.r(ok.sum() / max(1, solid.sum()), 5)
        res[cview] = out
    return res


def main():
    prof, src = LM.lookdev_profiles(sys.argv[1])
    ld = prof["lookdev"]
    tone = ld["tone"]
    order = ld["zones"]["order"]
    checks = {}
    conc, overlays = concept_zones(prof, ld)
    model = model_zones(prof, ld, order)
    C.check(checks, "zone_id_pass_clean", all(model[v]["_id_pixels_valid_share"] >= 0.999 for v in model),
            {v: model[v]["_id_pixels_valid_share"] for v in model}, ">= 0.999 of the opaque pixels decode to a zone id")
    nmin = int(tone["min_views_pixels"])
    per_zone = {}
    for z in order:
        views = {}
        ratios = []
        lratios = []
        mmeds = []
        for v in VIEWS:
            c = conc[v].get(z)
            m = model[v].get(z)
            entry = {"concept_pixels": c["pixels"] if c else 0, "model_pixels": m["pixels"] if m else 0}
            if c and c["median"] is not None:
                entry["concept"] = describe(c["median"])
            if m and m["median"] is not None:
                entry["model_before"] = describe(m["median"])
            use = bool(c and m and c["pixels"] >= nmin and m["pixels"] >= nmin)
            entry["used"] = use
            if use:
                cm, mm = np.asarray(c["median"]), np.maximum(np.asarray(m["median"]), 1e-6)
                ratios.append(cm / mm)
                lratios.append(float(np.dot(cm, LUM) / np.dot(mm, LUM)))
                mmeds.append(mm)
            views[v] = entry
        rz = np.median(np.stack(ratios), 0) if ratios else None
        lz = float(np.median(lratios)) if lratios else None
        per_zone[z] = {"views": views, "ratio_rgb": C.rv(rz, 4) if rz is not None else None,
                       "luma_ratio_views": [C.r(x, 4) for x in lratios], "luma_ratio": C.r(lz, 4) if lz is not None else None,
                       "_r": rz, "_l": lz, "_m": np.median(np.stack(mmeds), 0) if mmeds else None}
    lum_ratios = [per_zone[z]["_l"] for z in order if per_zone[z]["_l"] is not None and z not in tone["skip_zones"]]
    k = float(np.median(lum_ratios))
    lo, hi = tone["chroma_clamp"]
    llo, lhi = tone["luma_clamp"]
    q = float(tone["quantize"])
    gains = {}
    for z in order:
        r = per_zone[z].pop("_r")
        lz = per_zone[z].pop("_l")
        mz = per_zone[z].pop("_m")
        if r is None or z in tone["skip_zones"]:
            gains[z] = [1.0, 1.0, 1.0]
            per_zone[z]["gain"] = None
            per_zone[z]["gain_note"] = "skipped (%s)" % ("metal: preset F0" if z in tone["skip_zones"] else "no view with enough pixels")
            continue
        # chroma: the colour ratio normalised so the luminance of the zone's median model colour is kept; luma: the
        # zone's luminance ratio over the exposure k, clamped tighter (it carries the light differences of the concept)
        chroma = np.clip(r / (np.dot(r * mz, LUM) / np.dot(mz, LUM)), lo, hi)
        luma = float(np.clip(lz / k, llo, lhi))
        g = chroma * luma
        per_zone[z]["chroma_gain"] = C.rv(chroma, 4)
        per_zone[z]["luma_gain"] = C.r(luma, 4)
        per_zone[z]["luma_gain_unclamped"] = C.r(lz / k, 4)
        g = np.round(g / q) * q
        if np.all(np.abs(g - 1) < tone["dead_band"]):
            g = np.ones(3)
            per_zone[z]["gain_note"] = "inside the dead band: H2.1 BC kept"
        gains[z] = [float(x) for x in g]
        per_zone[z]["gain"] = C.rv(g, 3)
    C.check(checks, "exposure_k_from_zones", len(lum_ratios) >= 6, {"k": C.r(k, 4), "zones": len(lum_ratios)}, ">= 6 zones")
    # 5c-B0 (2026-09-30): UE feedback gains (profile lookdev.tone.ue_feedback), fitted on the UE look-dev C frames
    # against the concept (tools/art/material_library/ue_bc_feedback.py): multiplied onto the concept-tone gain
    fb = tone.get("ue_feedback") or {}
    fb_gain = fb.get("gain")
    for z in fb.get("zones", []) if fb_gain else []:
        g = np.asarray(gains[z], np.float64) * np.asarray(fb_gain, np.float64)
        gains[z] = [round(float(x), 4) for x in g]
        per_zone[z]["gain_before_ue_feedback"] = per_zone[z].get("gain")
        per_zone[z]["gain"] = C.rv(g, 4)
        per_zone[z]["ue_feedback_gain"] = C.rv(np.asarray(fb_gain), 4)
    # look-dev round 2 (2026-09-30, after 5c-B1): a second UE feedback (profile lookdev.tone.ue_feedback_r2), fitted on
    # the CONVERGED UE frames b1 (tools/art/material_library/lookdev_r2.py fit), multiplied onto the gain above
    fb2 = tone.get("ue_feedback_r2") or {}
    for z in fb2.get("zones", []) if fb2.get("gain") else []:
        g = np.asarray(gains[z], np.float64) * np.asarray(fb2["gain"], np.float64)
        gains[z] = [round(float(x), 4) for x in g]
        per_zone[z]["gain_before_ue_feedback_r2"] = per_zone[z].get("gain")
        per_zone[z]["gain"] = C.rv(g, 4)
        per_zone[z]["ue_feedback_r2_gain"] = C.rv(np.asarray(fb2["gain"]), 4)
    # ---------------------------------------------------------------- BC
    stt = np.load(prof.work / "lookdev" / "state.npz")
    zone_id = stt["zone_id"]
    bc = stt["bc_lin"].astype(np.float64)
    cov = stt["covered"]
    gtab = np.array([gains[z] for z in order])
    G = gtab[zone_id]
    G = np.stack([ndimage.uniform_filter(G[..., i], 3, mode="nearest") for i in range(3)], -1)
    bc_new = np.clip(bc * G, 0, 1)
    px = ld["prefix"]
    out = {"BC_4K": M.save_png(prof.textures / ("%s_BC_4K.png" % px), M.to8(M.srgb_encode(bc_new)), "RGB"),
           "BC_2K": M.save_png(prof.textures / ("%s_BC_2K.png" % px), M.to8(M.srgb_encode(M.box2(bc_new))), "RGB")}
    albedo = {}
    for i, z in enumerate(order):
        m = cov & (zone_id == i)
        albedo[z] = {"before": describe(np.median(bc[m], 0)), "after": describe(np.median(bc_new[m], 0)), "texels_4k": int(m.sum())}
    unchanged = [z for z in order if gains[z] == [1.0, 1.0, 1.0]]
    moved = [i for i, z in enumerate(order) if z in unchanged]
    far = ndimage.binary_erosion(np.isin(zone_id, moved), iterations=2)
    C.check(checks, "unmatched_zones_keep_h21_bc", bool(np.array_equal(M.to8(M.srgb_encode(bc_new))[far], M.to8(M.srgb_encode(bc))[far])),
            {"zones_kept": unchanged}, "8-bit BC equal on texels 2+ px inside kept zones")
    # ---------------------------------------------------------------- LUT
    presets = C.load_json(C.repo_path(ld["presets"]))
    cidx = LM.class_index(presets)
    overrides = {k: dict(v) for k, v in ld["lut_overrides"].items()}
    cls_of = ld["zones"]["class_of"]
    lut_src = {}
    for cid in sorted(set(cls_of.values())):
        if cid == "legacy_bake":
            continue
        zs = [i for i, z in enumerate(order) if cls_of[z] == cid]
        m = cov & np.isin(zone_id, zs)
        pre = next(c for c in presets["classes"] if c["id"] == cid)
        o = overrides.setdefault(cid, {})
        if int(pre["metallic"]) == 1:
            ymed = float(np.median(bc[m] @ LUM))
            o["heroYmed"] = round(ymed, 5)
            lut_src[cid] = {"row0": "preset F0 (metal)", "row7.R Ymed_class_hero": C.r(ymed, 5), "texels_4k": int(m.sum())}
        else:
            med = np.median(bc_new[m], 0)
            o.setdefault("baseColor", {})["typicalLinear"] = [round(float(x), 5) for x in med]
            lut_src[cid] = {"row0": "median BC after the concept tone match, zones %s" % [order[i] for i in zs],
                            "value": describe(med), "texels_4k": int(m.sum())}
    lut, merged = L.build(presets, overrides)
    half = L.to_half(lut)
    exr = prof.textures / ("%s_MatLUT.exr" % px)
    L.write_exr(exr, half)
    back = L.read_exr(exr)
    C.check(checks, "lut_exr_roundtrip_python", bool(np.array_equal(back.view(np.uint16), half.view(np.uint16))),
            {"shape": list(back.shape)}, "bit-exact float16")
    present = sorted({cidx[c] for c in cls_of.values()})
    C.check(checks, "lut_metallic_binary", set(np.unique(lut[0, :, 3]).tolist()) <= {0.0, 1.0}, sorted(set(lut[0, :, 3].tolist())), [0, 1])
    C.check(checks, "lut_team_dye_only_wool", [int(i) for i in present if lut[7, i, 3] > 0.5] == [cidx["wool_coarse"]],
            {str(i): float(lut[7, i, 3]) for i in present}, "teamDyeAllowed = 1 only on wool_coarse among Merlin's classes")
    C.check(checks, "lut_cloth_classes", {int(i) for i in present if lut[3, i, 3] > 0.5} == {cidx["wool_coarse"], cidx["silk"]},
            sorted(int(i) for i in present if lut[3, i, 3] > 0.5), sorted([cidx["wool_coarse"], cidx["silk"]]))
    rows_desc = ["BC typical r g b | metallic", "roughness typ | lo | hi | variation", "specular | clothAmount | bakeLuminanceModulation | bcMode",
                 "sheen intensity | sheen tint | sheenRoughness | shadingModel", "tilesPerMeter (512 tiles / 2) | normalStrength | array slice | cavityDarken",
                 "wear strength | wornRoughness (-1 none) | wornRoughnessDelta | wornBCScale", "worn BC r g b | wornBCMode",
                 "luminance min (metals: Ymed_class_hero) | luminance max | maxChannel | teamDyeAllowed"]
    C.write_json(prof.reports / "ld-lut.json", {
        "stage": "ld_tone", "hero": "Merlin", "file": {"path": C.rel(exr), "sha256": C.sha256(exr), "bytes": exr.stat().st_size},
        "format": "OpenEXR scanline, uncompressed, HALF RGBA, 16 x 8; row 0 = top = EXR y 0 = Load(int3(id, row, 0)); UE: TC_HDR (RGBA16F), Nearest, NoMipmaps, never stream, sRGB off",
        "rows": rows_desc, "presets": ld["presets"], "overrides": overrides, "measured_sources": lut_src,
        "classes": {str(c["index"]): c["id"] for c in presets["classes"]},
        "columns": {merged[cid]["id"]: {"index": int(merged[cid]["index"]),
                                         "rows": [C.rv(lut[r, int(merged[cid]["index"])], 5) for r in range(8)]}
                    for cid in merged},
        "half_values_rows_top_to_bottom": [[[float(x) for x in half[r, c]] for c in range(16)] for r in range(8)]})
    rep = {"stage": "ld_tone", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "method": tone["method"],
           "exposure_k": C.r(k, 4), "zones": per_zone, "gains": {z: C.rv(g, 3) for z, g in gains.items()}, "albedo_4k": albedo,
           "concept_overlays": overlays, "textures": out, "lut": {"path": C.rel(exr), "sha256": C.sha256(exr)},
           "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    C.write_json(prof.reports / "ld-tone-report.json", rep)
    print("H2_STAGE_OK ld_tone passed=%s k=%.3f gains=%s" % (rep["passed"], k, {z: g for z, g in gains.items() if g != [1.0, 1.0, 1.0]}))
    if not rep["passed"]:
        print("failed:", sorted(k2 for k2, c in checks.items() if not c["passed"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
