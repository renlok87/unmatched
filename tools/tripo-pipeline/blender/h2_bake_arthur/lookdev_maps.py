"""Stage `ld_maps` (system python): look-dev v2 maps of King Arthur from the H2.2 texel state.

    python lookdev_maps.py <lookdev profile.json> <lookdev run dir>

Input: the state cache of ld_state (H2.2 rebuilt byte-exact), work/lookdev/uv1-triangles.npz of ld_export.
1. zones (profile lookdev.zones; soft weights at 4K that sum to 1 on every texel, gutters = nearest covered texel):
   from the class weights of the H2.1/H2.2 material pass (see the profile's rules_note);
2. MatID (G8, value = class index x 16 + 8, no mips) at matid_px: class weights box-filtered from 4K, argmax;
3. TeamAccent (new, docs/art-pipeline/material-library/team-accent.md): the red-cloth strip inside the gold border
   bands of the parts in team_accent.strip.parts (rev. 2: the cloak only, the tabard stays red; 3D distance to a band
   texel whose normal agrees) + the belt; per-part checks that the cloak and the tabard stay red; soft edge
   (normalised Gaussian inside the coverage, atlas fill), multiplied by the dye-allowed zones (never on metal, skin,
   the embroidery, hair or stone); 3D area share measured with the texel area of the POS bake;
4. EdgeMask: convexity of the baked tangent normal (as Merlin, island-aware derivatives);
5. BC / ORM of the look-dev set: the H2.2 maps, except the cloth group (cloak, tabard) whose embroidery is no longer
   metal: BC = the painted colour there (the H2.2 F0-mapped gold is dropped), ORM.B = 0. N and TeamMask = H2.2
   (TeamMask kept for compatibility, DEPRECATED by TeamAccent);
6. per-texel UV1 (metres) rasterised from the export's triangles (affine per triangle = a similarity per island);
7. the base LUT inputs (presets + profile overrides; Ymed of the metal classes measured on the 2K BC), the
   look-dev 4K inputs of the emulation (work/lookdev/ld4k/*.npy) and the zone / accent / tabard ID textures for the frames.
Writes reports/ld-maps-report.json, textures/<prefix>_{N,TeamMask,TeamAccent,EdgeMask,TeamMaskRGBA,MatID}_2K.png (+4K
masters of N/TeamMask/TeamAccent/EdgeMask/TeamMaskRGBA, local), work/lookdev/T_Zone_4K.png, previews.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lookdev_emul as E  # noqa: E402
import lookdev_state as S  # noqa: E402
import materials as M  # noqa: E402
import pure as P  # noqa: E402
import textures as T  # noqa: E402
import uvcheck  # noqa: E402

# zone colours of the ID frames (sRGB 8-bit): steel plate / blade / stone / red cloth are the class colours of the
# H2.2 steelcheck (materials.STEEL_PLATE_RGB, STEEL_OVERRIDE_RGB, stone (55, 55, 55), red cloth (190, 25, 30)), so
# steelcheck.relative_check measures the look-dev frames with the H2.2 masks and references unchanged
ZONE_RGB = {"steel_plate": M.STEEL_PLATE_RGB, "blade": M.STEEL_OVERRIDE_RGB, "gold": (245, 205, 30),
            "embroidery": (255, 130, 0), "cloth": (190, 25, 30), "lining": (110, 0, 70), "belt": (110, 60, 25),
            "face_skin": (235, 185, 150), "hair": (60, 90, 40), "base": (55, 55, 55)}
ACCENT_RGB = (255, 0, 255)
TABARD_RGB = (0, 255, 255)
CLASS_RGB = {0: (20, 20, 20), 1: (80, 110, 170), 2: (200, 240, 235), 4: (245, 205, 30), 8: (110, 60, 25),
             9: (190, 25, 30), 11: (255, 130, 0), 13: (235, 185, 150), 14: (90, 90, 90)}


def check(checks, name, passed, measured, expected, note=""):
    checks[name] = {"passed": bool(passed), "measured": measured, "expected": expected, "note": note}


def save_png(path, arr, mode):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode).save(path, format="PNG", compress_level=6)
    return {"file": P.rel(path), "sha256": P.sha256(path), "bytes": path.stat().st_size,
            "px": [int(arr.shape[1]), int(arr.shape[0])]}


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def boxf(a, k):
    return a.reshape(a.shape[0] // k, k, a.shape[1] // k, k, *a.shape[2:]).mean(axis=(1, 3))


def matid_step(presets):
    n = int(presets["matId"].get("maxClasses", 16))
    return 256 // n


def zone_weights(st, zcfg):
    m, g, r, l_ = st["metal"], st["gold_share"], st["red"], st["leather"]
    grp, over, cov = st["group"], st["steel_override"], st["covered"]
    arm, clo, hed, sto = grp == 1, grp == 2, grp == 3, grp == 4
    z = {k: np.zeros(m.shape, np.float32) for k in zcfg["order"]}
    steel = m * (1 - g)
    z["steel_plate"] = np.where(arm & ~over, steel, 0)
    z["blade"] = np.where(arm & over, steel, 0)
    z["gold"] = np.where(arm, m * g, 0) + np.where(hed, m, 0)
    z["lining"] = np.where(arm, r, 0)
    z["belt"] = np.where(arm, l_ * (1 - r), 0)
    z["embroidery"] = np.where(clo, m, 0)
    z["cloth"] = np.where(clo, 1 - m, 0)
    _h, _s, v = M.hsv(st["bc_paint"])
    lo, hi = zcfg["head_skin_value_ramp"]
    skin = smoothstep((v - lo) / (hi - lo))
    z["face_skin"] = np.where(hed, (1 - m) * skin, 0)
    z["hair"] = np.where(hed, (1 - m) * (1 - skin), 0)
    z["base"] = np.where(sto, 1.0, 0)
    z = {k: T.nearest_fill(np.where(cov, w, 0).astype(np.float32), cov) for k, w in z.items()}
    return z


def edge_mask(n_enc, isl, cov):
    """Convexity of the baked tangent normal (OpenGL: x along +U, y along +V). Arrays row 0 = top (v = 1): d/dv =
    -d/drow. Derivatives only between texels of the same island, two scales, positive part / p99, mean."""
    n = n_enc * 2.0 - 1.0
    okx = np.zeros(cov.shape, bool)
    okx[:, 1:-1] = (isl[:, 2:] == isl[:, :-2]) & (isl[:, 2:] > 0)
    oky = np.zeros(cov.shape, bool)
    oky[1:-1, :] = (isl[2:, :] == isl[:-2, :]) & (isl[2:, :] > 0)
    out = np.zeros(cov.shape, np.float32)
    info = {}
    for sigma in (1.5, 4.0):
        nx = ndimage.gaussian_filter(n[..., 0], sigma, mode="nearest")
        ny = ndimage.gaussian_filter(n[..., 1], sigma, mode="nearest")
        du = np.zeros(cov.shape, np.float32)
        dv = np.zeros(cov.shape, np.float32)
        du[:, 1:-1] = (nx[:, 2:] - nx[:, :-2]) / 2
        dv[1:-1, :] = -(ny[2:, :] - ny[:-2, :]) / 2
        c = np.where(okx, du, 0) + np.where(oky, dv, 0)
        p99 = float(np.percentile(c[cov], 99))
        out += 0.5 * np.clip(c / p99, 0, 1)
        info["sigma_%g_p99" % sigma] = P.r(p99, 5)
    return T.nearest_fill(out, cov), info


def uv1_raster(tri_npz, size, cov):
    """Per-texel UV1 (metres): triangle index raster of UV0 (as uvcheck), affine UV0 -> UV1 per triangle; gutters
    extrapolate the affine map of the nearest covered texel's triangle."""
    z = np.load(tri_npz)
    u0 = np.concatenate([z[k + "_uv0"] for k in ("body", "weapon", "base")])
    u1 = np.concatenate([z[k + "_uv1"] for k in ("body", "weapon", "base")])
    lab = uvcheck.rasterise(u0, np.arange(len(u0)), size)
    ras_cov = lab > 0
    A = np.concatenate([u0, np.ones(u0.shape[:2] + (1,))], -1)            # [T, 3, 3]
    det = np.linalg.det(A)
    ok = np.abs(det) > 1e-14
    coef = np.zeros((len(u0), 3, 2))
    coef[ok] = np.linalg.solve(A[ok], u1[ok])
    _d, (jy, jx) = ndimage.distance_transform_edt(~(ras_cov & ok[np.maximum(lab - 1, 0)]), return_indices=True)
    t = lab[jy, jx] - 1
    rows, cols = np.mgrid[0:size, 0:size]
    uu = (cols + 0.5) / size
    vv = 1.0 - (rows + 0.5) / size
    c = coef.astype(np.float32)[t]
    uv1 = uu[..., None] * c[..., 0, :] + vv[..., None] * c[..., 1, :] + c[..., 2, :]
    info = {"triangles": int(len(u0)), "degenerate_uv0_triangles": int((~ok).sum()),
            "raster_equals_atlas_coverage": bool(np.array_equal(ras_cov, cov)),
            "coverage_mismatch_texels": int((ras_cov != cov).sum()),
            "uv1_abs_max_m_covered": P.r(float(np.abs(uv1[cov]).max()), 4)}
    return uv1.astype(np.float32), info


def team_accent(st, z, zc, tcfg, area, scale):
    names, pid, cov, pos = st["names"], st["pid"], st["covered"], st["pos"]
    sc = tcfg["strip"]
    parts = np.isin(pid, [names.index(p) + 1 for p in sc["parts"]])
    m = st["metal"]
    emb = parts & cov & (m >= 0.5)
    lab, _n = ndimage.label(emb, structure=np.ones((3, 3), bool))
    sizes = np.bincount(lab.ravel())
    sizes[0] = 0
    band = sizes[lab] >= int(sc["band_component_min_texels"])
    _t, _b, nrm = T.pos_frames(pos)
    tree = cKDTree(pos[band])
    bn = nrm[band]
    cand = parts & cov & (z["cloth"] > 0)
    d, j = tree.query(pos[cand], k=1)
    agree = (nrm[cand] * bn[j]).sum(-1) >= float(sc["normal_agree_min"])
    w_t = float(sc["width_m"]) / scale
    f_t = float(sc["feather_m"]) / scale
    strip = np.zeros(pid.shape, np.float32)
    strip[cand] = (smoothstep((w_t - d) / f_t) * agree * st["red"][cand] * z["cloth"][cand]).astype(np.float32)
    belt = z[tcfg["belt"]["zone"]]
    raw = np.maximum(strip, belt) * cov
    sig = float(tcfg["blur_sigma_px"])
    num = ndimage.gaussian_filter(raw.astype(np.float32), sig)
    den = ndimage.gaussian_filter(cov.astype(np.float32), sig)
    soft = np.where(cov, num / np.maximum(den, 1e-6), 0.0).astype(np.float32)
    soft = T.nearest_fill(soft, cov)
    allowed = z["cloth"] + z["belt"]     # the lining (collar, gems) is wool too, but stays out of the accent
    acc = np.clip(soft * allowed, 0, 1).astype(np.float32)
    fig = cov & (pid != names.index("tripo_part_4") + 1)
    fa = float(area[fig].sum())
    info = {"band_texels_4k": int(band.sum()), "band_components": int((np.bincount(lab[band]) > 0).sum()),
            "width_m_final": sc["width_m"], "width_m_tripo": P.r(w_t, 5), "seat_scale": scale,
            "share_3d_total": P.r(float((acc * area)[fig].sum()) / fa, 4),
            "share_3d_strip": P.r(float((np.minimum(acc, strip) * area)[fig].sum()) / fa, 4),
            "share_3d_belt": P.r(float((np.minimum(acc, belt) * area)[fig].sum()) / fa, 4),
            "share_3d_by_part": {n: P.r(float((acc * area)[fig & (pid == i + 1)].sum()) / fa, 4) for i, n in enumerate(names)
                                 if float((acc * area)[fig & (pid == i + 1)].sum()) > 0},
            "texels_4k_ge_0_5": int((acc[cov] >= 0.5).sum()),
            "area_method": "texel area = |dPOS/drow x dPOS/dcol| of the POS bake (Tripo frame; ratio, so the frame "
                           "scale cancels), clipped at 8 x median against island-edge jumps; figure = body + sword, "
                           "without the base part"}
    return acc, strip, belt, info


def main():
    prof, paths, src, src_run, cache = S.lookdev_paths(sys.argv[1], sys.argv[2])
    ld = prof["lookdev"]
    zc = ld["zones"]
    presets = P.load_json(P.repo_path(ld["presets"]))
    cidx = {c["id"]: int(c["index"]) for c in presets["classes"]}
    step = matid_step(presets)
    checks = {}
    st = S.load(cache, S.input_hashes(P.repo_path(ld["source_profile"]), src_run))
    size = st["size"]
    cov = st["covered"]
    scale = float(P.load_json(src_run / "reports" / "rig-report.json")["seat"]["scale"])
    # ---------------------------------------------------------------- zones and MatID
    z = zone_weights(st, zc)
    order = zc["order"]
    total = sum(z.values())
    check(checks, "zone_weights_partition", float(np.abs(total - 1).max()) < 1e-4,
          P.r(float(np.abs(total - 1).max()), 7), "< 1e-4 on every texel of the atlas")
    zone_id = np.argmax(np.stack([z[k] for k in order], 0), 0).astype(np.uint8)
    cls_of = zc["class_of"]
    classes = sorted({cidx[c] for c in cls_of.values()})
    cw = {ci: sum(z[k] for k in order if cidx[cls_of[k]] == ci) for ci in classes}
    mpx = int(ld["matid_px"])
    f = size // mpx
    matid_cls = np.array(classes, np.uint8)[np.argmax(np.stack([boxf(cw[ci], f) for ci in classes], 0), 0)]
    matid8 = (matid_cls.astype(np.int32) * step + step // 2).astype(np.uint8)
    dec = np.floor(matid8.astype(np.float64) * (255.0 / 255.0) / step + 1e-3).astype(np.int32)
    check(checks, "matid_encoding_roundtrip", bool(np.array_equal(dec, matid_cls)),
          {"values": sorted(int(v) for v in np.unique(matid8)), "step": step},
          "value = index x %d + %d; floor(v / %d) = index" % (step, step // 2, step))
    cov2 = boxf(cov.astype(np.float32), f) >= 0.5
    area_cls = {cid: P.r(float(((matid_cls == ci) & cov2).sum()) / cov2.sum(), 5)
                for cid, ci in sorted(cidx.items()) if ci in classes}
    zone_area = {k: P.r(float(((zone_id == i) & cov).sum()) / cov.sum(), 5) for i, k in enumerate(order)}
    check(checks, "every_zone_present", all(v > 0 for v in zone_area.values()), zone_area, "> 0 for every zone")
    # metal classes of MatID vs the H2.2 metallic (ORM.B): the embroidery left the metal on purpose
    met2 = boxf(st["mr"][..., 2], f) >= 0.5
    metal_ids = [cidx[c] for c in ("steel_blued", "steel_polished", "gold_antique")]
    mat_metal = np.isin(matid_cls, metal_ids)
    emb2 = matid_cls == cidx[cls_of["embroidery"]]
    dis = (mat_metal != met2) & ~emb2 & cov2
    check(checks, "matid_metal_equals_h22_metallic_outside_embroidery", int(dis.sum()) <= int(0.02 * max(1, mat_metal.sum())),
          {"metal_class_texels_2k": int(mat_metal.sum()), "h22_metallic_ge_0_5_texels_2k": int(met2.sum()),
           "disagree_outside_embroidery": int(dis.sum()), "embroidery_texels_2k_h22_metallic": int((emb2 & met2).sum())},
          "disagree <= 2 % of the metal texels (2K)")
    # ---------------------------------------------------------------- texel area, TeamAccent
    dr = np.gradient(st["pos"], axis=0)
    dc = np.gradient(st["pos"], axis=1)
    area = np.linalg.norm(np.cross(dr, dc), axis=-1).astype(np.float32)
    area[~cov] = 0
    area = np.minimum(area, float(np.median(area[cov])) * 8)
    tcfg = ld["team_accent"]
    acc, strip, belt, acc_info = team_accent(st, z, zc, tcfg, area, scale)
    lo, hi = tcfg["area_share_range"]
    check(checks, "team_accent_area_share", lo <= acc_info["share_3d_total"] <= hi,
          {k: acc_info[k] for k in ("share_3d_total", "share_3d_strip", "share_3d_belt")}, [lo, hi],
          "share of the figure's 3D surface (body + sword, no base)")
    core = {k: (z[k] >= 0.999) & ndimage.binary_erosion(zone_id == order.index(k), iterations=2) & cov
            for k in order}
    never = ["steel_plate", "blade", "gold", "embroidery", "face_skin", "hair", "base", "lining"]
    acc8 = q = T.q8(acc)
    leak = {k: int(q[core[k]].max()) if core[k].any() else 0 for k in never}
    check(checks, "team_accent_zero_outside_cloth_and_belt", all(v == 0 for v in leak.values()), leak,
          "0 (8-bit) on the core texels of metal, embroidery, skin, hair, stone, lining")
    # per part (rev. 2): a mean over cloak + tabard hid a tabard dyed for the most part (review 2026-09-29)
    rp = tcfg["red_parts"]
    part_core = {}
    for role in ("cloak", "tabard"):
        m = core["cloth"] & (st["pid"] == st["names"].index(rp[role]) + 1)
        share = float((acc[m] >= 0.5).mean()) if m.any() else 0.0
        part_core[role] = share
        check(checks, "team_accent_%s_stays_red" % role, m.any() and share <= float(rp["max_core_share"]),
              {"part": rp[role], "core_texels_4k": int(m.sum()), "accent_ge_0_5_share": P.r(share, 4)},
              "<= %s of the red cloth core texels of the %s carry the accent" % (rp["max_core_share"], role),
              "the %s stays red (the accent is only a strip / the belt)" % role)
    acc_info["red_core_share_by_part"] = {k: P.r(v, 4) for k, v in part_core.items()}
    # ---------------------------------------------------------------- EdgeMask, UV1
    edge, edge_info = edge_mask(st["normal_enc"], st["isl"], cov)
    uv1, uv1_info = uv1_raster(paths["work"] / "lookdev" / "uv1-triangles.npz", size, cov)
    check(checks, "uv1_raster_covers_atlas", uv1_info["coverage_mismatch_texels"] <= int(1e-4 * cov.sum()), uv1_info,
          "the export's triangles cover the texels of the bake atlas (mismatch <= 0.01 %)")
    # ---------------------------------------------------------------- look-dev BC / ORM (4K, linear)
    clo = st["group"] == 2
    clo_f = T.nearest_fill(np.where(cov, clo, False), cov)
    bc_ld = np.where(clo_f[..., None], st["bc_paint"], st["bc"]).astype(np.float32)
    metal_ld = np.where(clo_f, 0.0, st["mr"][..., 2]).astype(np.float32)
    rough_ld = st["mr"][..., 1].astype(np.float32)
    ld4k = paths["work"] / "lookdev" / "ld4k"
    ld4k.mkdir(parents=True, exist_ok=True)
    matid4 = np.repeat(np.repeat(matid_cls, f, 0), f, 1)
    for k, a in (("bc_ld", bc_ld), ("metal_ld", metal_ld), ("rough_ld", rough_ld), ("ao", st["ao"]),
                 ("n_gl", st["normal_enc"]), ("edge", edge), ("uv1", uv1), ("accent", acc), ("cls4k", matid4),
                 ("zone_id", zone_id), ("area", area), ("covered", cov)):
        np.save(ld4k / (k + ".npy"), a)
    np.savez_compressed(ld4k / "zones.npz", **{k: v.astype(np.float16) for k, v in z.items()})
    # ---------------------------------------------------------------- textures (unchanged / new masks)
    tex = paths["textures"]
    px = ld["prefix"]
    # the H2.2 TeamMask was boxed to 2K as one RGBA float array (textures.py): box the same array, so the 2K R / G
    # channels are the H2.2 bytes (a box of the single channel rounds a few texels differently)
    team4 = np.zeros(st["team_r"].shape + (4,), np.float32)
    team4[..., 0] = st["team_r"]
    team4[..., 1] = st["band"]
    team4[..., 3] = 1.0
    team4_2k = T.box2(team4)
    team_rgba = np.stack([st["team_r"], st["band"], acc, edge], -1)
    rgba2 = np.concatenate([team4_2k[..., :2], T.box2(acc)[..., None], T.box2(edge)[..., None]], -1)
    out = {}
    n_gl8 = T.q8(st["normal_enc"])
    n_dx4 = n_gl8.copy()
    n_dx4[..., 1] = 255 - n_dx4[..., 1]
    n2 = T.normals_encode(T.box2(st["normal_enc"]))
    n_dx2 = T.q8(n2)
    n_dx2[..., 1] = 255 - n_dx2[..., 1]
    maps = {"N": (n_dx4, n_dx2, "RGB"),
            "TeamMask": (T.q8(st["team_r"]), T.q8(team4_2k[..., 0]), "L"),
            "TeamAccent": (acc8, T.q8(T.box2(acc)), "L"),
            "EdgeMask": (T.q8(edge), T.q8(T.box2(edge)), "L"),
            "TeamMaskRGBA": (T.q8(team_rgba), T.q8(rgba2), "RGBA")}
    for k, (a4, a2, mode) in maps.items():
        out[k + "_4K"] = save_png(tex / ("%s_%s_4K.png" % (px, k)), a4, mode)
        out[k + "_2K"] = save_png(tex / ("%s_%s_2K.png" % (px, k)), a2, mode)
    out["MatID_2K"] = save_png(tex / ("%s_MatID_2K.png" % px), matid8, "L")
    # N and TeamMask(R) equal the H2.2 runtime 2K pixels
    sp = src["textures"]["prefix"]
    eq = {}
    with Image.open(src_run / "textures" / "runtime_2k" / ("%s_N.png" % sp)) as img:
        eq["N"] = bool(np.array_equal(np.asarray(img), np.asarray(Image.open(tex / ("%s_N_2K.png" % px)))))
    with Image.open(src_run / "textures" / "runtime_2k" / ("%s_TeamMask.png" % sp)) as img:
        ref = np.asarray(img)
        eq["TeamMask_R"] = bool(np.array_equal(ref[..., 0], np.asarray(Image.open(tex / ("%s_TeamMask_2K.png" % px)))))
        eq["TeamMaskRGBA_RG"] = bool(np.array_equal(ref[..., :2], np.asarray(Image.open(tex / ("%s_TeamMaskRGBA_2K.png" % px)))[..., :2]))
    check(checks, "unchanged_maps_equal_h22_2k", all(eq.values()), eq,
          "N, TeamMask (= H2.2 TeamMask.R, deprecated) and TeamMaskRGBA.RG = the H2.2 runtime 2K pixels")
    # ID textures of the frames (2K, zone argmax of the 2 x 2 block; accent >= 0.5 over it in the accent variant)
    zid2 = np.argmax(np.stack([boxf(z[k], f) for k in order], 0), 0)
    zrgb = np.array([ZONE_RGB[k] for k in order], np.uint8)[zid2]
    wk = paths["work"] / "lookdev"
    ids = {"zones": save_png(wk / "id" / "zones.png", zrgb, "RGB")}
    arg = zrgb.copy()
    arg[boxf(acc, f) >= 0.5] = ACCENT_RGB
    ids["accent"] = save_png(wk / "id" / "accent.png", arg, "RGB")
    # tabard ID (rev. 2): the red cloth of the tabard part in TABARD_RGB, the rest as the zone ID; lookdev_report
    # measures the red share of these pixels with and without the team dye
    tab = zrgb.copy()
    tpart = boxf((st["pid"] == st["names"].index(rp["tabard"]) + 1).astype(np.float32), f) >= 0.5
    tab[tpart & (zid2 == order.index("cloth"))] = TABARD_RGB
    ids["tabard"] = save_png(wk / "id" / "tabard.png", tab, "RGB")
    zp = save_png(wk / "T_Zone_4K.png", (zone_id.astype(np.int32) * 16 + 8).astype(np.uint8), "L")
    zone_png = {"path": zp["file"], "sha256": zp["sha256"], "encoding": "zone index (order of zones) x 16 + 8, 4K",
                "note": "local (work/); input of the debug ZoneID of lookdev_ue_inputs.py"}
    # ---------------------------------------------------------------- previews
    prev = paths["preview"]
    crgb = np.zeros(matid_cls.shape + (3,), np.uint8)
    for ci, col in CLASS_RGB.items():
        crgb[matid_cls == ci] = col
    out_prev = {"matid": save_png(prev / "ld_matid_2K.png", crgb, "RGB")}
    zc1 = np.array([ZONE_RGB[k] for k in order], np.float32)[zone_id] * np.where(cov, 1.0, 0.35)[..., None]
    out_prev["zones"] = save_png(prev / "ld_zones_1K.png", T.q8(boxf(zc1 / 255.0, 4)), "RGB")
    out_prev["edge"] = save_png(prev / "ld_edgemask_1K.png", T.q8(boxf(edge, 4)), "L")
    bcs = T.srgb(T.box2(bc_ld))
    a2 = T.box2(acc)[..., None]
    vis = bcs * (1 - a2 * 0.85) + np.array([1.0, 0.0, 1.0]) * a2 * 0.85
    out_prev["accent"] = save_png(prev / "ld_teamaccent_1K.png", T.q8(T.box2(vis)), "RGB")
    # ---------------------------------------------------------------- base LUT inputs
    bc2 = np.asarray(Image.fromarray(T.q8(T.srgb(T.box2(bc_ld))), "RGB"), np.float64) / 255.0
    y2 = E.lin(bc2) @ E.LUM.astype(np.float64)
    ymed = {}
    for cid in ("steel_blued", "steel_polished", "gold_antique"):
        sel = (matid_cls == cidx[cid]) & cov2
        ymed[cid] = P.r(float(np.median(y2[sel])), 5)
    diel = {}
    for cid in ("wool_coarse", "silk", "leather_worn", "skin", "stone_base"):
        sel = (matid_cls == cidx[cid]) & cov2
        diel[cid] = {"Y_p2_p50_p98": P.rv(np.percentile(y2[sel], [2, 50, 98]), 5), "texels_2k": int(sel.sum())}
    report = {"stage": "ld_maps", "profile": P.rel(sys.argv[1]), "profile_id": prof["profile_id"],
              "source_profile": ld["source_profile"], "atlas_px": size, "matid_px": mpx, "zones": order,
              "zone_class": cls_of, "zone_area_share_4k": zone_area, "matid_class_area_share_2k": area_cls,
              "team_accent": acc_info, "edge_mask": dict(edge_info, method="convexity of the baked tangent normal: "
                                                         "d(nx)/du + d(ny)/dv inside UV islands at gaussian sigma 1.5 "
                                                         "and 4 texels (4K), positive part / p99, mean of the two"),
              "uv1_raster": uv1_info, "ymed_bake_2k": ymed, "dielectric_bake_2k": diel,
              "presets_sha256": P.sha256(P.repo_path(ld["presets"])),
              "textures": out, "zone_texture": zone_png, "id_textures": ids, "previews": out_prev,
              "conventions": {
                  "MatID": "G8 linear (UE TC_Grayscale, sRGB off, NoMipmaps, Nearest, never streamed); value = class "
                           "index x 16 + 8; shader: Load(int3(frac(uv0) x size, 0)), id = floor(v x 255 / 16)",
                  "TeamAccent": "L8 linear (UE TC_Grayscale, sRGB off): team-colour accent (team-accent.md); goes into "
                                "the TeamMaskTexture slot of M_UM_Figure_v2",
                  "TeamMask": "L8 linear = H2.2 TeamMask.R (cloak, tabard, collar lining): DEPRECATED, kept for "
                              "compatibility (v1 MIs, W5c import)",
                  "EdgeMask": "L8 linear, 1 = convex edge (EdgeMaskTexture of M_UM_Figure_v2)",
                  "TeamMaskRGBA": "R TeamMask (deprecated), G base side band, B TeamAccent, A EdgeMask; linear",
                  "N": "DirectX (-Y), = H2.2"},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    P.write_json(paths["reports"] / "ld-maps-report.json", report)
    print(P.STAGE_MARKER, "ld_maps passed=%s" % report["passed"], sorted(k for k, c in checks.items() if not c["passed"]))
    print("accent", acc_info["share_3d_total"], acc_info["share_3d_strip"], acc_info["share_3d_belt"], "ymed", ymed)


if __name__ == "__main__":
    main()
