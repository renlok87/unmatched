"""Stage `ld_maps` (system python): look-dev v2 maps of Merlin from the H2.1 texel state.

python lookdev_maps.py <lookdev profile.json>

1. lookdev_state.build(): the H2.1 state rebuilt from the source run; its 8-bit maps must equal the H2.1 4K masters
   (check h21_state_reproduced) -> the classes below sit on exactly the texels H2.1 shipped;
2. zones (profile lookdev.zones, soft weights at 4K): wool / embroidery / belt / buckle from the H2.1 classes on the
   cloth parts; boots, wood, crystal, hands, base by part; part 9 split into face skin, beard (low saturation) and
   the leather beard wrap (saturated, below source z wrap_z_max_m);
3. MatID (G8, value = class index x 16 + 8, no mips) at matid_px: class weights (sum of zone weights) box-filtered
   from 4K, argmax. Every texel of the atlas (gutters included) has a class: the zones are defined on the gutter-filled
   part / colour maps, so a Load near an island edge never reads an undefined id;
4. EdgeMask (convexity of the baked tangent normal map, two scales, positive part / p99, island-aware derivatives)
   -> TeamMaskRGBA.A (A was a constant 255 in H2.1); R G B unchanged;
5. ORM: G of the beard (MatID 0) remapped to a matte hair range (profile beard_roughness); everything else = H2.1;
6. N, TeamMask: the H2.1 pixels (rewritten under the lookdev prefix, pixel equality checked);
   BC: written by ld_tone (concept tone match); here the H2.1 BC is kept in work/lookdev/ as the "before" state.
Outputs: textures/<prefix>_{N,ORM,TeamMask,TeamMaskRGBA,MatID}_2K.png (+ 4K masters, local),
work/lookdev/state.npz (zone ids, BC linear, class weights for ld_tone), work/lookdev/T_Zone_4K.png (zone id pass
texture), preview/ld_matid_2K.png, preview/ld_zones_1K.png, reports/ld-maps-report.json.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import lookdev_lut as L  # noqa: E402
import lookdev_state as S  # noqa: E402
import maps as M  # noqa: E402

ZONE_COLOURS = {"wool": (0.15, 0.2, 0.75), "embroidery": (1.0, 0.85, 0.1), "belt": (0.1, 0.85, 0.2), "buckle": (1.0, 0.1, 0.1),
                "boots": (0.2, 0.55, 0.2), "beard_wrap": (0.6, 1.0, 0.3), "wood": (0.45, 0.28, 0.12), "crystal": (0.1, 0.9, 1.0),
                "face_skin": (1.0, 0.6, 0.45), "hands_skin": (0.85, 0.45, 0.35), "beard": (0.95, 0.95, 0.95), "base": (0.35, 0.35, 0.38)}
CLASS_COLOURS = L.CLASS_COLOURS


def lookdev_profiles(path):
    prof = C.Profile(path)
    src = C.Profile(C.repo_path(prof["lookdev"]["source_profile"]))
    return prof, src


def class_index(presets):
    return {c["id"]: int(c["index"]) for c in presets["classes"]}


def zone_weights(st, ld, src):
    """Soft zone weights at 4K (sum 1 on every texel)."""
    z = ld["zones"]
    part = st["part"]

    def on(key):
        return np.isin(part, [C.part_index(p) for p in z["parts"][key]]).astype(np.float64)

    cls = st["cls"]
    cloth = on("cloth")
    w = {}
    # the H2.1 soft classes can sum above 1 on their soft edges (metal + leather x (1 - metal) + trim x ...): take them
    # in priority buckle > belt > embroidery, each limited to what the previous ones left
    w["buckle"] = cls["metal_buckle"] * cloth
    w["belt"] = np.minimum(cls["leather_belt"] * cloth, cloth - w["buckle"])
    w["embroidery"] = np.clip(np.minimum(cls["embroidery"] * cloth, cloth - w["buckle"] - w["belt"]), 0, 1)
    w["wool"] = np.clip(cloth - w["buckle"] - w["belt"] - w["embroidery"], 0, 1)
    fb = z["face_beard"]
    face = on("face_beard")
    _h, s, _v = st["hsv"]
    sat = np.clip((s - fb["skin_s_min"]) / fb["s_soft"] + 0.5, 0, 1)
    low = np.clip((fb["wrap_z_max_m"] - st["pos"][..., 2]) / fb["z_soft_m"] + 0.5, 0, 1)
    w["beard"] = face * (1 - sat)
    w["beard_wrap"] = face * sat * low
    w["face_skin"] = face * sat * (1 - low)
    w["hands_skin"] = on("hands")
    w["boots"] = on("boots")
    w["wood"] = on("wood")
    w["crystal"] = on("crystal")
    w["base"] = on("base")
    total = sum(w.values())
    return {k: w[k] for k in z["order"]}, total


def edge_mask(st):
    """Convexity of the baked tangent normal (OpenGL: x along +U, y along +V; arrays row 0 = v 0). Derivatives only
    between texels of the same UV island (gutter texels take the nearest island), two scales, positive part / p99."""
    n = st["n_gl"]
    isl = st["island_raw"]
    cov = st["covered"]
    okx = np.zeros(cov.shape, bool)
    okx[:, 1:-1] = (isl[:, 2:] == isl[:, :-2]) & (isl[:, 2:] >= 0)
    oky = np.zeros(cov.shape, bool)
    oky[1:-1, :] = (isl[2:, :] == isl[:-2, :]) & (isl[2:, :] >= 0)
    out = np.zeros(cov.shape)
    info = {}
    for sigma in (1.5, 4.0):
        nx = ndimage.gaussian_filter(n[..., 0], sigma, mode="nearest")
        ny = ndimage.gaussian_filter(n[..., 1], sigma, mode="nearest")
        du = np.zeros(cov.shape)
        dv = np.zeros(cov.shape)
        du[:, 1:-1] = (nx[:, 2:] - nx[:, :-2]) / 2
        dv[1:-1, :] = (ny[2:, :] - ny[:-2, :]) / 2
        c = np.where(okx, du, 0) + np.where(oky, dv, 0)
        p99 = float(np.percentile(c[cov], 99))
        out += 0.5 * np.clip(c / p99, 0, 1)
        info["sigma_%g_p99" % sigma] = C.r(p99, 5)
    # gutters: nearest covered texel (the same fill as the other maps)
    _d, (jy, jx) = ndimage.distance_transform_edt(~cov, return_indices=True)
    return out[jy, jx], info


def main():
    prof, src = lookdev_profiles(sys.argv[1])
    ld = prof["lookdev"]
    presets = C.load_json(C.repo_path(ld["presets"]))
    cidx = class_index(presets)
    checks = {}
    st = S.build(src)
    repro = S.check_against_h21(st, src)
    C.check(checks, "h21_state_reproduced", all(v["sha256_matches_h21_report"] and v["pixels_equal_rebuilt"] for v in repro.values()),
            repro, "every 4K master: sha256 = H2.1 textures-report, rebuilt 8-bit pixels equal")
    size = st["size"]
    cov = st["covered"]
    zw, total = zone_weights(st, ld, src)
    C.check(checks, "zone_weights_partition", float(np.abs(total - 1).max()) < 1e-6, C.r(float(np.abs(total - 1).max()), 8), "< 1e-6",
            "sum of the soft zone weights on every texel of the atlas")
    order = ld["zones"]["order"]
    zstack = np.stack([zw[k] for k in order], 0)
    zone_id = np.argmax(zstack, 0).astype(np.uint8)  # index into order
    # class weights + MatID
    cls_of = ld["zones"]["class_of"]
    classes = sorted({cidx[c] for c in cls_of.values()})
    cw = {ci: sum(zw[k] for k in order if cidx[cls_of[k]] == ci) for ci in classes}
    mpx = int(ld["matid_px"])
    f = size // mpx

    def boxf(a, k):
        return a.reshape(a.shape[0] // k, k, a.shape[1] // k, k).mean((1, 3))

    cstack = np.stack([boxf(cw[ci], f) for ci in classes], 0)
    matid_cls = np.array(classes, np.uint8)[np.argmax(cstack, 0)]
    matid8 = (matid_cls.astype(np.uint16) * 16 + 8).astype(np.uint8)
    # the 1K alternative (README §3), measured only: share of the 2K embroidery texels that keep their class at 1K
    c1k = np.array(classes, np.uint8)[np.argmax(np.stack([boxf(cw[ci], size // 1024) for ci in classes], 0), 0)]
    emb_ci = cidx[cls_of["embroidery"]]
    emb2 = matid_cls == emb_ci
    emb_up = np.repeat(np.repeat(c1k == emb_ci, 2, 0), 2, 1)
    keep_1k = float((emb2 & emb_up).sum() / max(1, emb2.sum()))
    decoded = matid8.astype(np.int32) // 16
    C.check(checks, "matid_encoding_roundtrip", bool(np.array_equal(decoded, matid_cls)) and set(np.unique(matid8 % 16).tolist()) == {8},
            {"values": sorted(int(v) for v in np.unique(matid8))}, "value = index x 16 + 8; floor(v / 16) = index")
    cov2 = boxf(cov.astype(np.float64), f) >= 0.5
    area = {}
    for ci in classes:
        m = matid_cls == ci
        area[str(ci)] = {"class": next(c["id"] for c in presets["classes"] if c["index"] == ci),
                         "share_of_covered": C.r((m & cov2).sum() / cov2.sum(), 5), "texels_all": int(m.sum())}
    # zone -> class sanity on the committed rules (measured on covered 4K texels, hard zone ids)
    zone_area = {k: C.r(float(((zone_id == i) & cov).sum()) / cov.sum(), 5) for i, k in enumerate(order)}
    C.check(checks, "every_zone_present", all(v > 0 for v in zone_area.values()), zone_area, "> 0 for every zone")
    C.check(checks, "no_team_dye_class_on_embroidery",
            ld["lut_overrides"].get(cls_of["embroidery"], {}).get("teamDyeAllowed") is False,
            {"class": cls_of["embroidery"], "override_teamDyeAllowed": ld["lut_overrides"].get(cls_of["embroidery"], {}).get("teamDyeAllowed")}, False)
    tm8 = M.to8(st["cloth"])
    emb4 = (zone_id == order.index("embroidery")) & cov
    C.check(checks, "team_mask_zero_on_embroidery_core", int(tm8[emb4 & (zw["embroidery"] >= 0.999)].max()) == 0,
            int(tm8[emb4 & (zw["embroidery"] >= 0.999)].max()), 0, "TeamMask (cloth) on texels fully in the embroidery zone")
    metal_ci = cidx[cls_of["buckle"]]
    orm8_h21 = S.maps8(st)["ORM"]
    metal2 = boxf(orm8_h21[..., 2].astype(np.float64), f) >= 128
    C.check(checks, "matid_metal_equals_orm_metallic", int(((matid_cls == metal_ci) != metal2).sum()) <= int(0.02 * max(1, metal2.sum())) and metal2.any(),
            {"matid_bronze_texels": int((matid_cls == metal_ci).sum()), "orm_metallic_ge_0_5_texels": int(metal2.sum()),
             "disagree": int(((matid_cls == metal_ci) != metal2).sum())}, "disagree <= 2 % of the metal texels (2K)")
    # EdgeMask
    edge, edge_info = edge_mask(st)
    # ORM: beard roughness
    br = ld["beard_roughness"]
    rough = st["rough"].copy()
    wb = zw["beard"]
    core_b = cov & (wb >= 0.999)
    p50_t = float(np.median(st["rough"][core_b]))
    r_b = np.clip(br["target_p50"] + br["scale"] * (st["rough"] - p50_t), br["range"][0], br["range"][1])
    rough = rough * (1 - wb) + r_b * wb
    before_b = C.rv(np.percentile(st["rough"][core_b], [5, 50, 95]), 4)
    after_b = C.rv(np.percentile(rough[core_b], [5, 50, 95]), 4)
    C.check(checks, "beard_roughness_matte", after_b[1] >= 0.72, {"before_p5_p50_p95": before_b, "after_p5_p50_p95": after_b},
            ">= 0.72 p50 (hair of a painted miniature: matte)")
    # textures
    tex = prof.textures
    px = ld["prefix"]
    out = {}
    n_dx = st["n_gl"].copy()
    n_dx[..., 1] *= -1
    n2 = M.box2(st["n_gl"])
    n2 /= np.maximum(np.linalg.norm(n2, axis=-1, keepdims=True), 1e-8)
    n2[..., 1] *= -1
    orm4 = np.stack([st["ao"], rough, st["metal"]], -1)
    rgba4 = np.stack([st["cloth"], st["band"], st["emb"], edge], -1)
    # 2K: box of every source array in its own dtype, stacked afterwards, as maps.py (the team masks are float32: a box
    # after stacking with a float64 channel rounds 65 texels of TeamMaskRGBA.R differently)
    def box_each(*arrs):
        return np.stack([M.box2(a) for a in arrs], -1)

    maps = {"N": (M.to8(n_dx * 0.5 + 0.5), M.to8(n2 * 0.5 + 0.5), "RGB"),
            "ORM": (M.to8(orm4), M.to8(box_each(st["ao"], rough, st["metal"])), "RGB"),
            "TeamMask": (M.to8(st["cloth"]), M.to8(M.box2(st["cloth"])), "L"),
            "TeamMaskRGBA": (M.to8(rgba4), M.to8(box_each(st["cloth"], st["band"], st["emb"], edge)), "RGBA")}
    for k, (a4, a2, mode) in maps.items():
        out[k + "_4K"] = M.save_png(tex / ("%s_%s_4K.png" % (px, k)), a4, mode)
        out[k + "_2K"] = M.save_png(tex / ("%s_%s_2K.png" % (px, k)), a2, mode)
    out["MatID_2K"] = M.save_png(tex / ("%s_MatID_%dK.png" % (px, mpx // 1024)), matid8, "L")
    # equality with the H2.1 runtime set where nothing changed
    h21 = {}
    sp = src["maps"]["prefix"]
    for k, chans in (("N", None), ("TeamMask", None), ("ORM", [0, 2]), ("TeamMaskRGBA", [0, 1, 2])):
        with Image.open(src.textures / ("%s_%s_2K.png" % (sp, k))) as img:
            ref = np.asarray(img)
        with Image.open(tex / ("%s_%s_2K.png" % (px, k))) as img:
            new = np.asarray(img)
        if chans is None:
            h21[k] = bool(np.array_equal(ref, new))
        else:
            h21[k] = bool(np.array_equal(ref[..., chans], new[..., chans]))
    C.check(checks, "unchanged_channels_equal_h21_2k", all(h21.values()), h21, "N, TeamMask, ORM.R/B, TeamMaskRGBA.RGB = H2.1 2K pixels")
    with Image.open(src.textures / ("%s_ORM_2K.png" % sp)) as img:
        ref_g = np.flipud(np.asarray(img)[..., 1])
    new_g = maps["ORM"][1][..., 1]
    beard2 = boxf(wb, 2) > 0
    C.check(checks, "orm_g_changed_only_on_beard", int(((ref_g != new_g) & ~beard2).sum()) == 0,
            {"changed_texels": int((ref_g != new_g).sum()), "outside_beard": int(((ref_g != new_g) & ~beard2).sum())}, {"outside_beard": 0})
    e2 = M.box2(edge)
    C.check(checks, "edge_mask_range", float(np.percentile(e2[boxf(cov.astype(float), 2) >= 0.5], 99)) > 0.5,
            dict(edge_info, p50_p95_p99_2k=C.rv(np.percentile(e2[boxf(cov.astype(float), 2) >= 0.5], [50, 95, 99]), 4)), "p99 > 0.5")
    # work state for ld_tone
    wk = prof.work / "lookdev"
    wk.mkdir(parents=True, exist_ok=True)
    np.savez(wk / "state.npz", zone_id=zone_id, bc_lin=st["bc_lin"].astype(np.float32), covered=cov,
             part=st["part"].astype(np.int16), hsv_s=st["hsv"][1].astype(np.float32))
    zone_png = M.save_png(wk / "T_Zone_4K.png", (zone_id.astype(np.uint16) * 16 + 8).astype(np.uint8), "L")
    # review images
    zc = np.array([ZONE_COLOURS[k] for k in order])[zone_id] * np.where(cov, 1.0, 0.35)[..., None]
    out_prev = {"zones": M.save_png(prof.preview / "ld_zones_1K.png", M.to8(M.box2(M.box2(zc))), "RGB")}
    mc = np.zeros(matid_cls.shape + (3,))
    for ci, col in CLASS_COLOURS.items():
        mc[matid_cls == ci] = col
    out_prev["matid"] = M.save_png(prof.preview / "ld_matid_2K.png", M.to8(mc), "RGB")
    out_prev["edge"] = M.save_png(prof.preview / "ld_edgemask_1K.png", M.to8(M.box2(e2)), "L")
    report = {"stage": "ld_maps", "profile": C.rel(prof.path), "profile_id": prof["profile_id"],
              "source_profile": C.rel(src.path), "atlas_px": size, "matid_px": mpx, "zones": order,
              "zone_class": cls_of, "zone_area_share_4k": zone_area, "matid_class_area_2k": area,
              "matid_1k_alternative": {"embroidery_texels_2k_kept_at_1k": C.r(keep_1k, 4),
                                       "note": "share of the 2K embroidery MatID texels whose 1K MatID is also embroidery"},
              "beard_roughness": {"tripo_p50": C.r(p50_t, 4), "before_p5_p50_p95": before_b, "after_p5_p50_p95": after_b},
              "edge_mask": dict(edge_info, channel="TeamMaskRGBA.A (linear)", method="convexity of the baked tangent normal: d(nx)/du + d(ny)/dv inside UV islands at gaussian sigma 1.5 and 4 texels (4K), positive part / p99 of each, mean of the two"),
              "textures": out, "zone_texture": zone_png, "previews": out_prev,
              "conventions": {"MatID": "G8 linear (UE TC_Grayscale, sRGB off, NoMipmaps, Nearest, never streamed); value = class index x 16 + 8; shader: Load(int3(frac(uv0) x size, 0)), id = floor(v x 255 / 16)",
                              "TeamMaskRGBA": "R cloth (team dye), G base side band, B gold embroidery, A EdgeMask (look-dev v2; A was 255 in H2.1); linear, sRGB off",
                              "ORM": "R AO, G roughness (beard remapped), B metallic; linear", "N": "DirectX (-Y), = H2.1", "TeamMask": "L = cloth, = H2.1"},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    C.write_json(prof.reports / "ld-maps-report.json", report)
    print("H2_STAGE_OK ld_maps passed=%s" % report["passed"])
    if not report["passed"]:
        print("failed:", sorted(k for k, c in checks.items() if not c["passed"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
