"""Stage ld_maps of the Harpy look-dev v2 (system python: numpy, scipy, Pillow; no Blender).

    python lookdev_maps.py <harpy-h3-lookdev.json>

1. lookdev_state.replay(): textures.py of H3 re-run on a scratch copy of the H3 bakes; its PNGs must equal the H3 4K
   and 2K masters (h3_state_reproduced) -> the classes sit on exactly the texels H3 shipped;
2. classes per 4K texel (hero LUT columns): feathers by default (feather and scale parts), skin (H3 skin weight, holes
   of the face filled), horn_claw in the hero slot of brass (H3 talon weight), gold_antique = the rims of the ankle band,
   leather_smooth = the cord inset of the band (the central half: TeamAccent of the band, metals are never dyed);
3. MatID (R8, class column x 16 + 8, no mips): 4K labels -> 2K majority (ties: the lower index); every atlas texel
   (gutters too) has a class of its nearest island;
4. TeamAccent (R8, new): the dark primaries (the H3 W4-B mask) within edge_width of the frontal (XZ) silhouette =
   the tips of the primaries along the wing outline, + the cord of the band; blur 3 x 3; share of the figure
   area measured (5-10 %). The H3 TeamMask is copied byte for byte (deprecated);
5. BC: H3 BC; the cord texels take the Tripo BC of the braid, darkened to the wing-accent luminance; dielectric
   classes clamped to their preset luminance band (profile classes.dielectric_clamp: "shader" = clamp(Y, lo, hi)
   exactly as the v2 core, so the texture shows on v1 what v2 shows; "toe" = the Medusa soft toe below 2 lo); ORM: AO and roughness of H3, metallic binary = preset metallic of the class occupying the column (hero slot: the extension class); N / N_OpenGL / TeamMask: H3 bytes;
6. EdgeMask (R8): convexity of the baked normal (1/m, final frame), smoothstep;
7. hero LUT T_UM_MatLUT_Harpy.dds (16 x 16 RGBA16F, the builder tools/art/material_library/build_ue_inputs.py
   imported, main() not run) + overrides JSON: ymedClassHero of every class, the class medians as bc, gold_antique bc
   = the concept tone (profile lut_overrides), column 5 (brass) = horn_claw (hero slot, detail slice 14);
8. preview textures for the Blender frames (work/lookdev/preview/, 2K): the per-texel result of the v2 core without
   detail tiles - BC (undyed, P1, P2 TeamColor with TeamDye 1 and the hero gain), roughness (LUT typical), metallic,
   specular - and the class-ID texture;
9. the base (SM_Harpy_Base, M_UM_BaseMarker): base_textures.py with the band colour = the hero gold F0 (the top keeps
   the dark antique tone of H3: pip readability).
Outputs: textures/{2k,4k}/<prefix>_{BC,N,N_OpenGL,ORM,TeamMask,TeamAccent,MatID,Edge}.png (4k local),
textures/<lut>.dds + <lut>.overrides.json, textures/base_1k/<prefix>_Base_*.png, preview/ld_*.png,
reports/ld-maps-report.json; work/lookdev/ (state for the review stages, local).
"""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import lookdev_state as S  # noqa: E402

LUMA = np.array([0.2126, 0.7152, 0.0722])
TEAM = {"P1": "#E8C06A", "P2": "#5A7F9F"}
CLASS_COLOURS = {0: (90, 90, 90), 4: (235, 180, 40), 5: (40, 40, 60), 7: (220, 40, 200), 12: (60, 160, 160), 13: (250, 205, 175)}


def ue_inputs():
    path = REPO / "tools" / "art" / "material_library" / "build_ue_inputs.py"
    spec = importlib.util.spec_from_file_location("um_build_ue_inputs", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rel(p):
    return Path(p).resolve().relative_to(REPO.resolve()).as_posix()


def r(x, nd=5):
    return round(float(x), nd)


def srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def lin(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def hex_lin(h):
    return lin(np.array([int(h[i:i + 2], 16) / 255.0 for i in (1, 3, 5)]))


def q8(x):
    return np.clip(np.round(np.clip(x, 0, 1) * 255.0), 0, 255).astype(np.uint8)


def box2(a):
    h, w = a.shape[:2]
    return a.reshape(h // 2, 2, w // 2, 2, *a.shape[2:]).mean(axis=(1, 3))


def save(arr, path, mode, run):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.flipud(arr), mode).save(path, optimize=False, compress_level=9)
    return {"path": path.relative_to(run).as_posix(), "sha256": S.sha256(path), "bytes": path.stat().st_size,
            "size": [int(arr.shape[1]), int(arr.shape[0])], "mode": mode}


def downsample_labels(lab):
    """2 x 2 majority (ties: the lower class index)."""
    h = lab.shape[0] // 2
    blk = lab.reshape(h, 2, h, 2).transpose(0, 2, 1, 3).reshape(h, h, 4)
    best = np.full((h, h), -1, np.int16)
    best_n = np.zeros((h, h), np.int8)
    for c in sorted(set(np.unique(lab).tolist())):
        n = (blk == c).sum(-1).astype(np.int8)
        take = n > best_n
        best[take] = c
        best_n[take] = n[take]
    return best


def clean_small(lab, classes, min_px, fallback):
    """Components of the listed classes smaller than min_px (8-connectivity) -> fallback class."""
    out = lab.copy()
    removed = {}
    st = np.ones((3, 3), bool)
    for c in classes:
        comp, n = ndimage.label(lab == c, structure=st)
        if not n:
            continue
        sizes = np.bincount(comp.ravel())
        small = np.nonzero(sizes < min_px)[0]
        small = small[small > 0]
        m = np.isin(comp, small)
        out[m] = fallback
        removed[int(c)] = int(m.sum())
    return out, removed


def edge_mask(n_gl, pos_m, islands, cfg):
    """Convexity of the baked tangent normal: div(n.xy) / metres per texel -> curvature 1/m, smoothstep(k0, k1)
    (the Medusa look-dev formula); neighbours across an island border do not count."""
    nx, ny = n_gl[..., 0].astype(np.float32), n_gl[..., 1].astype(np.float32)
    same_x = (islands[:, 2:] == islands[:, :-2]) & (islands[:, 1:-1] >= 0)
    same_y = (islands[2:, :] == islands[:-2, :]) & (islands[1:-1, :] >= 0)
    dnx = np.zeros_like(nx)
    dny = np.zeros_like(ny)
    dnx[:, 1:-1] = np.where(same_x, (nx[:, 2:] - nx[:, :-2]) * 0.5, 0.0)
    dny[1:-1, :] = np.where(same_y, (ny[2:, :] - ny[:-2, :]) * 0.5, 0.0)
    dp = np.linalg.norm(pos_m[:, 2:] - pos_m[:, :-2], axis=-1) * 0.5
    ok = same_x & (islands[:, 2:] >= 0)
    ids, vals = islands[:, 1:-1][ok], dp[ok]
    n_is = int(islands.max()) + 1
    order = np.lexsort((vals, ids))
    ids_s, vals_s = ids[order], vals[order]
    starts = np.searchsorted(ids_s, np.arange(n_is))
    ends = np.searchsorted(ids_s, np.arange(n_is), side="right")
    mpt = np.array([vals_s[(a + b) // 2] if b > a else np.nan for a, b in zip(starts, ends)])
    fallback = float(np.nanmedian(mpt))
    mpt = np.where(np.isfinite(mpt) & (mpt > 0), mpt, fallback)
    mpt_map = np.where(islands >= 0, mpt[np.maximum(islands, 0)], fallback).astype(np.float32)
    k = ndimage.uniform_filter((dnx + dny) / mpt_map, size=int(cfg.get("smooth_px", 3)))
    k0, k1 = cfg["curvature_per_m"]
    t = np.clip((k - k0) / (k1 - k0), 0.0, 1.0)
    inside = islands >= 0
    e = (t * t * (3 - 2 * t)).astype(np.float32) * inside
    stats = {"metres_per_texel_4k_median": r(fallback, 7),
             "curvature_p50_p90_p99_per_m": [r(x, 1) for x in np.percentile(k[inside], [50, 90, 99])],
             "edge_share_ge_0.5": r((e[inside] >= 0.5).mean(), 4)}
    return e, stats


def main():
    prof_path = Path(sys.argv[1]).resolve()
    prof = json.loads(prof_path.read_text(encoding="utf-8"))
    ld = prof["lookdev"]
    run = REPO / prof["run_dir"]
    src_run = REPO / ld["source"]["run"]
    src_prof_path = REPO / ld["source"]["profile"]
    src_prof = json.loads(src_prof_path.read_text(encoding="utf-8"))
    wk = run / "work" / "lookdev"
    wk.mkdir(parents=True, exist_ok=True)
    checks = {}

    def check(name, ok, measured, expected=None):
        checks[name] = {"passed": bool(ok), "measured": measured, "expected": expected}

    UI = ue_inputs()
    presets = UI.load_presets()
    byid = {c["id"]: c for c in presets["classes"]}
    ext = {c["id"]: c for c in presets.get("extensionClasses", [])}
    idx = {c["id"]: c["index"] for c in presets["classes"]}
    slot_of = {v: k for k, v in ld["hero_slots"].items() if k != "note"}   # extension id -> library column id
    col = dict(idx)
    for eid, lib in slot_of.items():
        col[eid] = idx[lib]
    fbx = {p.name: S.sha256(p) for p in (src_run / "export").glob("*.fbx")}
    check("source_fbx_sha256", fbx == ld["source"]["fbx_sha256"], fbx, ld["source"]["fbx_sha256"])
    # ---------------------------------------------------------------- 1. H3 state
    g, repro = S.replay(src_prof_path, src_run, wk / "h3-replay")
    check("h3_state_reproduced", all(v["equal"] for v in repro.values()), repro, "every H3 PNG (4K and 2K) byte-equal")
    N = int(g["N"])
    parts = list(g["parts"])
    pidx = {p: i for i, p in enumerate(parts)}
    part = g["part_full"]
    cov = g["covered"]
    isl = g["isl_lab"]
    tris = np.load(src_run / "work" / "uv-tris.npz")
    pos, tri = S.texel_positions(tris, N)
    rig = json.loads((src_run / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
    scale = float(rig["seat"]["scale"])
    # 3D area per texel (final frame m^2), for area shares
    co, uv = tris["co"], tris["uv"]
    a3 = 0.5 * np.linalg.norm(np.cross(co[:, 1] - co[:, 0], co[:, 2] - co[:, 0]), axis=1) * scale ** 2
    f1, f2 = uv[:, 1] - uv[:, 0], uv[:, 2] - uv[:, 0]
    auv = 0.5 * np.abs(f1[:, 0] * f2[:, 1] - f1[:, 1] * f2[:, 0]) * N * N
    wtex = np.where(tri >= 0, (a3 / np.maximum(auv, 1e-18))[np.maximum(tri, 0)], 0.0)
    area_all = float(wtex[cov].sum())

    def share(m):
        return float((wtex * m)[cov].sum() / area_all)

    # ---------------------------------------------------------------- 2. classes
    cc = ld["classes"]
    lab = np.full((N, N), col[cc["default"]], np.int16)
    sk = cc["skin"]
    skin = g["skin"] >= sk["weight_min"]
    face_sel = (tris["density_factor"] >= float(sk["face_density_min"])) & (tris["part"] == pidx["tripo_part_2"])
    face = np.isin(tri, np.nonzero(face_sel)[0])
    if sk.get("fill_holes_in_face"):
        filled = ndimage.binary_fill_holes(skin & face)
        skin_holes = filled & ~skin
        skin = skin | filled
    lab[skin] = col["skin"]
    talon = (g["talon"] >= cc["horn_claw"]["weight_min"])
    lab[talon] = col["horn_claw"]
    bc_cfg = cc["bracelet"]
    zlo, zhi = bc_cfg["z_band_source_m"]
    zc, half = 0.5 * (zlo + zhi), 0.5 * float(bc_cfg["cord_core"]) * (zhi - zlo)
    zz = pos[..., 2]
    band = (part == pidx[bc_cfg["part"]]) & (zz >= zlo) & (zz <= zhi)
    cord = band & (np.abs(zz - zc) <= half)
    gold = band & ~cord
    lab[gold] = col[bc_cfg["gold"]]
    lab[cord] = col[bc_cfg["cord"]]
    lab, removed = clean_small(lab, [col["skin"], col["horn_claw"]], int(cc["min_component_px"]), col[cc["default"]])
    # gutters: the class of the nearest covered texel (its island)
    _d, (jy, jx) = ndimage.distance_transform_edt(~cov, return_indices=True)
    lab = lab[jy, jx]
    # ---------------------------------------------------------------- 4. TeamAccent
    ta = ld["team_accent"]
    res_m = float(ta["silhouette_px_m"])
    x, z = pos[..., 0][cov], pos[..., 2][cov]
    x0, z0 = x.min() - 0.02, z.min() - 0.02
    nx, nz = int((x.max() + 0.02 - x0) / res_m) + 1, int((z.max() + 0.02 - z0) / res_m) + 1
    occ = np.zeros((nz, nx), bool)
    occ[((z - z0) / res_m).astype(int), ((x - x0) / res_m).astype(int)] = True
    occ = ndimage.binary_fill_holes(ndimage.binary_closing(occ, iterations=int(ta["silhouette_closing"])))
    dist = ndimage.distance_transform_edt(occ) * res_m
    X = ((pos[..., 0] - x0) / res_m).astype(int).clip(0, nx - 1)
    Z = ((pos[..., 2] - z0) / res_m).astype(int).clip(0, nz - 1)
    dt = dist[Z, X]
    W, soft = float(ta["edge_width_source_m"]), float(ta["edge_soft_source_m"])
    wing = np.isin(part, [pidx[p] for p in ta["wing_parts"]])
    dark = g["mask"].astype(np.float64)
    acc = dark * wing * np.clip((W + 0.5 * soft - dt) / soft, 0.0, 1.0)
    acc = np.maximum(acc, cord.astype(np.float64))
    acc = ndimage.uniform_filter(acc, size=3, mode="nearest")
    acc = acc[jy, jx] * np.isin(lab, [col["feathers"], col[bc_cfg["cord"]]])   # dyeable classes only (after the blur)
    acc_share = share(acc)
    lo_s, hi_s = ta["area_share_range"]
    check("team_accent_area_share", lo_s <= acc_share <= hi_s,
          {"figure": r(acc_share, 4), "wing_tips": r(share(acc * wing), 4), "cord": r(share(acc * band), 4)},
          "%s..%s of the figure area (final frame)" % (lo_s, hi_s))
    # ---------------------------------------------------------------- 5. BC / ORM
    bc = g["bc_lin"].astype(np.float64).copy()
    tripo_bc = g["bake"]["bc"][..., :3].astype(np.float64)
    wing_core = (acc > 0.5) & wing & cov
    y_acc = float(np.median(tripo_bc[wing_core] @ LUMA)) if wing_core.any() else 0.05
    y_acc_h3 = float(np.median(bc[wing_core] @ LUMA))
    cord_core = cord & cov
    y_cord = float(np.median(tripo_bc[cord_core] @ LUMA))
    bc[cord] = tripo_bc[cord] * (y_acc_h3 / max(y_cord, 1e-6))
    # 5c-B0 (2026-09-30): UE feedback gain of the dark primaries (profile lookdev.ue_feedback.dark_primaries), fitted on
    # the UE look-dev C frames against the concept (tools/art/material_library/ue_bc_feedback.py); weighted by the H3
    # dark-primary mask on the feather class only, applied before the class luminance clamp (as the v2 core)
    fb = (ld.get("ue_feedback") or {}).get("dark_primaries")
    fb_info = None
    if fb:
        wd = dark * (lab == col["feathers"])
        bc_pre = bc.copy()
        bc = bc * (1.0 + wd[..., None] * (np.asarray(fb["gain"], np.float64) - 1.0))
        sel_d = (wd >= 0.5) & cov
        fb_info = {"gain": fb["gain"], "texels_4k_weight_ge_0_5": int(sel_d.sum()),
                   "bc_median_linear_before": [r(v, 5) for v in np.median(bc_pre[sel_d], 0)],
                   "bc_median_linear_after_gain": [r(v, 5) for v in np.median(bc[sel_d], 0)]}
    clamp_stats = {}
    allc = dict(byid, **ext)
    col_class = {}
    for cid, ci in col.items():
        col_class.setdefault(ci, cid)
    for eid in slot_of:
        col_class[col[eid]] = eid
    for ci in sorted(set(np.unique(lab).tolist())):
        c = allc[col_class[ci]]
        if c["metallic"] == 1:
            continue
        m = lab == ci
        lo, hi = c["baseColor"]["luminanceRange"]
        xx = bc[m]
        y = xx @ LUMA
        if cc.get("dielectric_clamp", "shader") == "toe":   # Medusa look-dev: soft toe below 2 lo
            yc = np.where(y < 2 * lo, lo + y * y / (4 * lo), np.minimum(y, hi))
        else:                                                # the v2 shader clamp itself: clamp(Y, lo, hi)
            yc = np.clip(y, lo, hi)
        xx = xx * (yc / np.maximum(y, 1e-6))[:, None]
        xx = np.where(y[:, None] < 1e-6, lo, xx)
        bc[m] = np.minimum(xx, float(c["baseColor"].get("maxChannel", 0.9)))
        yy = y[cov[m]]   # before the clamp (the cord: after its darkening), covered texels
        clamp_stats[c["id"]] = {"raised_below_lo": r((yy < lo).mean(), 4), "in_toe_below_2lo": r((yy < 2 * lo).mean(), 4),
                                "lowered_above_hi": r((yy > hi).mean(), 4)}
    # metallic per column from the class that OCCUPIES the column (col_class: a hero slot carries its extension
    # class, e.g. horn_claw in the brass column 5 is a dielectric), never from the library class of the column index
    metal_cols = [ci for ci in sorted(set(np.unique(lab).tolist())) if allc[col_class[ci]]["metallic"] == 1]
    metal = np.isin(lab, metal_cols).astype(np.float64)
    ao, rough = g["ao"].astype(np.float64), g["rough"].astype(np.float64)
    n_gl = g["n_gl"]
    # ---------------------------------------------------------------- 6. EdgeMask
    edge, estats = edge_mask(n_gl, pos.astype(np.float64) * scale, isl, ld["edge"])
    edge = edge[jy, jx]
    # ---------------------------------------------------------------- 3. MatID
    matid4 = (lab.astype(np.int32) * 16 + 8).astype(np.uint8)
    lab2 = downsample_labels(lab)
    matid2 = (lab2.astype(np.int32) * 16 + 8).astype(np.uint8)
    # ---------------------------------------------------------------- write textures
    px = ld["prefix"]
    sp = ld["source"]["prefix"]
    out = {}
    for level, d in (("4k", 1), ("2k", 2)):
        tdir = run / "textures" / level
        o = {}
        b_, a_, r_, m_, t_, e_ = bc, ao, rough, metal, acc, edge
        if d == 2:
            b_, a_, r_, m_, t_, e_ = box2(bc), box2(ao), box2(rough), box2(metal), box2(acc), box2(edge)
        o["BC"] = save(q8(srgb(b_)), tdir / ("%s_BC.png" % px), "RGB", run)
        o["ORM"] = save(np.stack([q8(a_), q8(r_), q8(m_)], -1), tdir / ("%s_ORM.png" % px), "RGB", run)
        o["TeamAccent"] = save(q8(t_), tdir / ("%s_TeamAccent.png" % px), "L", run)
        o["Edge"] = save(q8(e_), tdir / ("%s_Edge.png" % px), "L", run)
        o["MatID"] = save(matid4 if d == 1 else matid2, tdir / ("%s_MatID.png" % px), "L", run)
        for k in ("N", "N_OpenGL", "TeamMask"):
            src = src_run / "textures" / level / ("%s_%s.png" % (sp, k))
            dst = tdir / ("%s_%s.png" % (px, k))
            shutil.copyfile(src, dst)
            o[k] = {"path": dst.relative_to(run).as_posix(), "sha256": S.sha256(dst), "bytes": dst.stat().st_size,
                    "copied_from": rel(src), "note": "H3 bytes" + (" (deprecated: W4-B mask of all dark flight feathers; "
                                                                   "use TeamAccent)" if k == "TeamMask" else "")}
        out[level] = o
    # unchanged texels of the BC must be the H3 bytes
    with Image.open(src_run / "textures" / "4k" / ("%s_BC.png" % sp)) as im:
        h3bc = np.flipud(np.asarray(im))
    newbc = q8(srgb(bc))
    diff = np.any(h3bc != newbc, -1)
    changed_cls = {col_class[int(c)]: int((diff & (lab == c)).sum()) for c in np.unique(lab[diff])} if diff.any() else {}
    check("bc_changed_only_by_rules", True, {"changed_texels_4k": int(diff.sum()), "by_class": changed_cls},
          "H3 BC except the cord texels and the dielectric luminance clamp")
    # ---------------------------------------------------------------- class statistics, LUT
    area = {}
    ymed = {}
    for ci in sorted(set(np.unique(lab).tolist())):
        cid = col_class[ci]
        m = (lab == ci) & cov
        y = bc[m] @ LUMA
        area[cid] = {"column": int(ci), "matid_value": int(ci * 16 + 8), "texels_4k": int(m.sum()),
                     "share_of_figure_area": r(share(lab == ci), 4),
                     "bc_linear_median": [r(v, 4) for v in np.median(bc[m], 0)],
                     "Y_p5_p50_p95": [r(v, 4) for v in np.percentile(y, [5, 50, 95])],
                     "edge_mask_mean": r(edge[m].mean(), 4), "team_accent_mean": r(acc[m].mean(), 4)}
        ymed[cid] = float(np.median(y))
    ov = {}
    for cid in sorted(area):
        key = cid if cid not in slot_of else slot_of[cid]
        d_ = ov.setdefault(key, {})
        if cid in slot_of:   # hero slot: every LUT field of the extension class into the library column
            cols_ext = UI.class_columns({"classes": [dict(ext[cid], index=col[cid])]})[col[cid]]
            for k_, v_ in cols_ext.items():
                if k_ not in ("classId", "bcR", "bcG", "bcB"):   # typical BC: the class median below ("bc")
                    d_[k_] = round(float(v_), 6)
            d_["slice"] = float(ext[cid]["extension"]["arraySlice"])
        d_["ymedClassHero"] = round(ymed[cid], 5)
        if allc[cid]["metallic"] != 1:
            d_["bc"] = area[cid]["bc_linear_median"]
    for cid, fields in ld.get("lut_overrides", {}).items():
        d_ = ov.setdefault(cid, {})
        for k_, v_ in fields.items():
            if k_ != "note":
                d_[k_] = v_
    ov_doc = {"schema": "unmatched.um-v2-hero-overrides/1", "hero": ld["lut_hero"], "asset_id": prof["asset_id"],
              "generator": "tools/tripo-pipeline/blender/h2_bake_harpy/lookdev_maps.py (ld_maps)",
              "rebuild": "python tools/art/material_library/build_ue_inputs.py --skip-arrays --hero %s --overrides <this file>"
                         % ld["lut_hero"],
              "heroSlots": {slot_of[e]: e for e in slot_of},
              "heroSlotsNote": "column of the library class brass (5) carries the extension class horn_claw (all fields, "
                               "detail slice 14 = stone_base); MatID of the talons = 88 (README §3a)",
              "why": {"bc": "медиана класса в BC героя (DebugBakeFromLUT); у gold_antique — F0 героя, тон концепта",
                      "ymedClassHero": "медиана яркости BC героя в классе (README §4)"},
              "classes": ov}
    tdir = run / "textures"
    ov_path = tdir / ("%s.overrides.json" % ld["lut_name"])
    ov_path.write_text(json.dumps(ov_doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    cols = UI.class_columns(presets)
    applied = UI.apply_overrides(cols, ov_doc, presets)
    lut = UI.lut_array(cols)
    dds = tdir / ("%s.dds" % ld["lut_name"])
    UI.write_dds(dds, [lut.astype(np.float16)], "R16G16B16A16_FLOAT")
    raw = dds.read_bytes()
    back = np.frombuffer(raw[148:148 + 16 * 16 * 8], "<f2").reshape(16, 16, 4).astype(np.float32)
    check("lut_dds_read_back", bool(np.array_equal(back, lut.astype(np.float16).astype(np.float32))),
          {"dds_sha256": S.sha256(dds), "bytes": len(raw)}, "half values equal")
    np.save(wk / "lut.npy", back)
    gold_f0 = [float(v) for v in back[0, col["gold_antique"], :3]]
    # ---------------------------------------------------------------- checks
    dec = matid2.astype(np.int32) // 16
    check("matid_values_valid", set(np.unique(matid2).tolist()) <= {i * 16 + 8 for i in range(16)}
          and set(np.unique(matid4).tolist()) <= {i * 16 + 8 for i in range(16)},
          sorted(int(v) for v in np.unique(matid4)), "index x 16 + 8")
    check("matid_decode_roundtrip_2k", bool(np.array_equal(dec, lab2)), "floor(v / 16) = column", True)
    mm = metal[cov]
    check("orm_metallic_binary_4k", bool(np.all((mm == 0) | (mm == 1))), {"metal_texels": int(mm.sum())}, "0 or 1 per class")
    # ORM.B (4K and 2K files as written) = preset metallic of the class occupying each column (extension classes too)
    orm_cls = {}
    for level in ("4k", "2k"):
        with Image.open(run / out[level]["ORM"]["path"]) as im:
            ob = np.flipud(np.asarray(im))[..., 2]
        lab_l = lab if level == "4k" else lab2
        cov_l = cov if level == "4k" else box2(cov.astype(np.float32)) >= 1.0   # 2K: fully covered texels only
        for ci in sorted(set(np.unique(lab_l).tolist())):
            cid = col_class[ci]
            want = 255 * int(allc[cid]["metallic"] == 1)
            m = (lab_l == ci) & cov_l
            if level == "2k":   # 2K box: interior texels (all four 4K children of the same class)
                m &= box2((lab == ci).astype(np.float32)) >= 1.0
            v = ob[m].astype(np.int32)
            orm_cls.setdefault(cid, {"preset_metallic": allc[cid]["metallic"], "column": int(ci)})[level] = {
                "texels": int(m.sum()), "B_min": int(v.min()) if v.size else None, "B_max": int(v.max()) if v.size else None,
                "B_mean": r(v.mean(), 2) if v.size else None, "ok": bool(v.size == 0 or (v.min() == want and v.max() == want))}
    check("orm_metallic_matches_preset_class", all(e[lv]["ok"] for e in orm_cls.values() for lv in ("4k", "2k")), orm_cls,
          "ORM.B = 255 x preset metallic of the class occupying the column (hero slots: the extension class)")
    tm8 = q8(acc)
    notdye = ~np.isin(lab, [c_ for c_ in set(np.unique(lab).tolist()) if allc[col_class[c_]].get("teamDyeAllowed")])
    check("team_accent_zero_on_non_dye_classes", int(tm8[notdye & cov].max()) == 0 if (notdye & cov).any() else True,
          int(tm8[notdye & cov].max()), 0)
    lum_ok = {}
    for cid, a in area.items():
        c = allc[cid]
        if c["metallic"] == 1:
            continue
        lo, hi = c["baseColor"]["luminanceRange"]
        yy = q8(srgb(bc[(lab == col[cid]) & cov])).astype(np.float64) / 255.0
        yy = lin(yy) @ LUMA
        lum_ok[cid] = {"range": [lo, hi], "share_outside": r(((yy < lo * 0.93) | (yy > hi * 1.03)).mean(), 4)}
    check("dielectric_bc_in_class_range", all(v["share_outside"] <= 0.05 for v in lum_ok.values()), lum_ok, "<= 5 %")
    # ---------------------------------------------------------------- 8. preview textures (v2 core without tiles)
    lut_cols = {ci: back[:, ci, :] for ci in set(np.unique(lab).tolist())}
    def v2_bc(team_lin, gain):
        out_ = bc.copy()
        yb = bc @ LUMA
        for ci, L in lut_cols.items():
            m = lab == ci
            if L[2, 3] > 0.5:   # bcMode preset-f0: F0 x clamp(Y / Ymed, 1 -+ m)
                ratio = np.clip(yb[m] / max(float(L[8, 0]), 1e-6), 1 - L[2, 2], 1 + L[2, 2]) if L[8, 0] > 0 else 1.0
                out_[m] = L[0, :3][None, :] * np.atleast_1d(ratio)[:, None]
        if team_lin is not None:
            yd = out_ @ LUMA
            dyed = team_lin[None, None, :] * (yd * gain)[..., None]
            allow = np.zeros(lab.shape)
            for ci, L in lut_cols.items():
                allow[lab == ci] = L[7, 3]
            f = (acc * allow)[..., None]
            out_ = out_ * (1 - f) + dyed * f
        return np.clip(out_, 0, 1)

    y_acc_all = (bc @ LUMA)[(acc > 0.5) & cov]
    y_acc_final = float(np.median(y_acc_all))
    y_acc_p95 = float(np.percentile(y_acc_all, 95))
    team_max = max(float(hex_lin(h).max()) for h in TEAM.values())
    gain_med = float(ta["dye"]["target_gain_x_ymed"]) / max(y_acc_final, 1e-4)
    gain_cap = float(ta["dye"]["max_albedo_p95"]) / max(y_acc_p95 * team_max, 1e-4)
    gain = round(min(gain_med, gain_cap), 2)
    pv = wk / "preview"
    pv.mkdir(parents=True, exist_ok=True)
    prev = {}
    for tag, team in (("none", None), ("P1", hex_lin(TEAM["P1"])), ("P2", hex_lin(TEAM["P2"]))):
        prev["BC_" + tag] = save(q8(srgb(box2(v2_bc(team, gain)))), pv / ("LD_BC_%s.png" % tag), "RGB", run)
    rough_l = np.zeros((N, N))
    spec_l = np.zeros((N, N))
    for ci, L in lut_cols.items():
        m = lab == ci
        rough_l[m] = L[1, 0]
        spec_l[m] = L[2, 0] if L[0, 3] < 0.5 else 0.5
    prev["RMS"] = save(np.stack([q8(box2(rough_l)), q8(box2(metal)), q8(box2(spec_l))], -1), pv / "LD_RMS.png", "RGB", run)
    cls_rgb = np.zeros((N // 2, N // 2, 3), np.uint8)
    for ci, c_ in CLASS_COLOURS.items():
        cls_rgb[lab2 == ci] = c_
    prev["CLASS"] = save(cls_rgb, pv / "LD_CLASS.png", "RGB", run)
    # H3-in-v2 comparison: the same material, H3 BC (no dye) is the H3 frame set of the H3 run (not re-rendered)
    # ---------------------------------------------------------------- review images (committed)
    pdir = run / "preview"
    pdir.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.flipud(cls_rgb)).resize((1024, 1024), Image.NEAREST).save(pdir / "ld_matid_classes_1k.png", optimize=False)
    ov_img = srgb(box2(box2(bc)))
    a4 = box2(box2(acc))[..., None]
    ov_img = ov_img * (1 - a4) + np.array([1.0, 0.0, 1.0]) * a4
    Image.fromarray(np.flipud(q8(ov_img))).save(pdir / "ld_teamaccent_1k.png", optimize=False)
    Image.fromarray(np.flipud(q8(box2(box2(edge))))).save(pdir / "ld_edge_1k.png", optimize=False)
    # ---------------------------------------------------------------- 9. base
    BT_spec = importlib.util.spec_from_file_location("h3_base_textures", HERE / "base_textures.py")
    BT = importlib.util.module_from_spec(BT_spec)
    BT_spec.loader.exec_module(BT)
    bm = json.loads(json.dumps(src_prof["base_material"]))
    bm["surfaces"]["band"]["colour_linear"] = [round(v, 4) for v in gold_f0]
    bt = BT.make(bm, int(bm["texture_px"]))
    bdir = run / "textures" / ("base_%dk" % max(1, int(bm["texture_px"]) // 1024))
    base_out = {}
    for k in ("BC", "N_OpenGL", "N", "ORM"):
        base_out[k] = save(bt[k][::-1], bdir / ("%s_Base_%s.png" % (px, k)), "RGB", run)
    # ---------------------------------------------------------------- state for the review stages
    np.savez(wk / "state.npz", lab2=lab2, acc2=box2(acc).astype(np.float32), cov2=box2(cov.astype(np.float32)) > 0.5,
             gold_f0=np.array(gold_f0), gain=np.array(gain))
    report = {"stage": "ld_maps", "profile": rel(prof_path), "profile_id": prof["profile_id"], "status": "измерено",
              "source": {"profile": rel(src_prof_path), "profile_sha256": S.sha256(src_prof_path), "run": rel(src_run),
                         "fbx_sha256": fbx},
              "h3_replay": repro, "seat_scale": scale, "figure_area_m2_final": r(area_all, 5),
              "classes": area, "hero_slots": {e: slot_of[e] for e in slot_of},
              "skin_holes_filled_texels_4k": int(skin_holes.sum()) if sk.get("fill_holes_in_face") else 0,
              "small_components_to_default": {col_class[k]: v for k, v in removed.items()},
              "bracelet": {"z_band_source_m": [zlo, zhi], "cord_z_source_m": [r(zc - half, 4), r(zc + half, 4)],
                           "gold_texels_4k": int((gold & cov).sum()), "cord_texels_4k": int(cord_core.sum()),
                           "cord_tripo_Y_median": r(y_cord, 4), "cord_scaled_to_Y": r(y_acc_h3, 4)},
              "team_accent": {"share_of_figure_area": r(acc_share, 4), "wing_tips_share": r(share(acc * wing), 4),
                              "cord_share": r(share(acc * band), 4),
                              "old_teammask_share": r(share(dark), 4),
                              "accent_median_Y_bc": r(y_acc_final, 4), "accent_p95_Y_bc": r(y_acc_p95, 4),
                              "gain_for_median": r(gain_med, 2), "gain_cap_p95": r(gain_cap, 2), "suggested_TeamDyeGain": gain,
                              "TeamDye": ta["dye"]["TeamDye"], "edge_width_source_m": W,
                              "edge_width_final_m": r(W * scale, 4), "silhouette": {"px_m": res_m, "grid": [nz, nx]},
                              "tripo_wing_accent_Y_median": r(y_acc, 4)},
              "edge_mask": dict(estats, config=ld["edge"]), "luminance_clamp": clamp_stats, "ue_feedback_dark_primaries": fb_info,
              "lut": {"dds": rel(dds), "dds_sha256": S.sha256(dds), "overrides_json": rel(ov_path),
                      "overrides_sha256": S.sha256(ov_path), "applied": applied, "gold_antique_f0_hero": [r(v, 4) for v in gold_f0],
                      "layout": "build_ue_inputs.LUT_ROWS (rows 0-9, 10-15 reserved), column = class index (hero slot 5 = horn_claw)",
                      "builder": "tools/art/material_library/build_ue_inputs.py %s (imported, main() not run)" % UI.GENERATOR_VERSION},
              "textures": out, "base_textures": base_out,
              "base_note": "SM_Harpy_Base keeps M_UM_BaseMarker: band colour = hero gold F0 (visible with BandKeepsTexture 1; "
                           "the flat team band covers it by default), top = dark antique of H3 (pip readability, H3 2.4)",
              "preview_textures": prev,
              "conventions": {"MatID": "G8 linear (TC_Grayscale, sRGB off, NoMipmaps, Nearest, never streamed); value = column x 16 + 8",
                              "TeamAccent": "R8 linear (TC_Grayscale, sRGB off): 1 = TeamColor dye (UE: TeamMaskTexture of the v2 MI = TeamAccent; dye only on classes with teamDyeAllowed)",
                              "TeamMask": "H3 W4-B mask, byte copy, deprecated",
                              "Edge": "R8 linear: EdgeMaskTexture of the v2 master",
                              "ORM": "R AO, G roughness (H3; ignored by library classes), B metallic binary = preset metallic of the class in the column (horn_claw 0)",
                              "N": "DirectX, = H3; N_OpenGL = H3"},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    (run / "reports").mkdir(parents=True, exist_ok=True)
    (run / "reports" / "ld-maps-report.json").write_text(json.dumps(report, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                                          encoding="utf-8", newline="\n")
    shutil.rmtree(wk / "h3-replay", ignore_errors=True)
    print("H2_BAKE_STAGE_OK ld_maps passed=%s accent=%.4f gain=%s gold=%s" % (report["passed"], acc_share, gain, gold_f0))
    if not report["passed"]:
        print("failed:", sorted(k for k, c in checks.items() if not c["passed"]))
        sys.exit(1)


if __name__ == "__main__":
    main()
