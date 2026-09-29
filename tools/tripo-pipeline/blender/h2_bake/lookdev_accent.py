"""TeamAccent of the H2 look-dev (plain Python: numpy + scipy + Pillow; no bpy). Mode `--mode teamaccent` of
run_h2_bake.py, profile schema unmatched.h2-lookdev-teamaccent-profile/1.

Why: the look-dev run (lookdev.py, ld_maps) kept the W4-B TeamMask.R = the whole dress. With the v2 master
(bc = lerp(bc, dyed, TeamMask x teamDyeAllowed)) and linen teamDyeAllowed = 1 the team colour covers the whole dress,
against the user decision 2026-09-29 «Акценты + кольцо»: the hero stays in the concept colours, the team colour goes
to the ring / base and to ACCENTS of the clothes (hem border, belt / sash, lining, ribbon) — layout and rules in
docs/art-pipeline/material-library/team-accent.md.

The mode reads a FINISHED look-dev run (profile lookdev_run; every input pinned by sha256, nothing of it is rewritten:
the look-dev profile, ld-maps-report and run-manifest are pinned by the UE import, skeletal_adopt_formats.h2_lookdev)
and writes new files next to it (or into another --run-dir for the determinism check):

  ta_maps    (this module) TeamAccent L8 linear: 4K master + 2K runtime (box of the 4K float mask);
             accent = hem strip (dress cloth within width_m of the gold border bands of the skirt, 3D distance, normal
             agreement) + ribbon (the leather baldric across the chest and back, isolated by UV opening + 3D components),
             soft edge (normalised Gaussian inside the coverage), multiplied by the allowed zones (dress cloth + the
             baldric), atlas gutter = nearest covered texel. Area share of the figure (3D, texel area of the position
             bake), per-part check that the dress keeps its colour, 0 on gold / skin / snakes / stone / wood (8 bit).
             TeamDyeGain of the MI by the team-accent.md rule. Emulated render sets (the dye of um_v2_core.hlsl on
             the look-dev BC: dyed = lerp(bc, Team x Y(bc) x gain, TeamAccent x teamDyeAllowed(class))) for P1 / P2
             and an ID texture (R MatID, G accent, B 255) for the measurements of the frames.
  ta_render  (st_team.py, Blender) Cobble light of the board, exposure calibrated to the W4-A anchor (K1 board ROI
             p50 = 131.2), K2 5x front / back (+ 1.6x), sets ld | ld_p1 | ld_p2 + ID pass.
  ta_report  (this module) screen share of the accent, CIELAB contrast accent / dress next to it and P1 / P2, the dress
             and the gold unchanged by the dye outside the accent; sheets concept | ld | P1 | P2.
  ta_manifest  inputs / outputs / modules with sha256 (reports/ld-team-manifest.json).
Deterministic: no randomness, Pillow PNG without metadata; the frames are Blender (EEVEE) editor frames, not UE."""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
LUM = np.array([0.2126, 0.7152, 0.0722], np.float64)
ACCENT_ID_G = 255


def sha256(path):
    d = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            d.update(chunk)
    return d.hexdigest()


def r(x, nd=4):
    return round(float(x), nd)


def lin(c):
    c = np.clip(np.asarray(c, np.float64), 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def srgb(x):
    x = np.clip(np.asarray(x, np.float64), 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1.0 / 2.4) - 0.055)


def to8(a):
    return np.clip(np.floor(np.clip(a, 0.0, 1.0) * 255.0 + 0.5), 0, 255).astype(np.uint8)


def box2(a):
    h = a.shape[0] // 2
    return a.reshape(h, 2, h, 2, *a.shape[2:]).mean((1, 3))


def hex_lin(h):
    h = h.lstrip("#")
    return [float(lin(int(h[i:i + 2], 16) / 255.0)) for i in (0, 2, 4)]


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def read_png(path):
    """8-bit PNG -> array, row 0 = v 0 (the textures-stage convention of h2_bake)."""
    return np.asarray(Image.open(path))[::-1].copy()


def save_png(arr8, path, mode):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr8[::-1], mode).save(path, format="PNG", compress_level=6)
    return {"sha256": sha256(path), "bytes": path.stat().st_size, "px": [int(arr8.shape[1]), int(arr8.shape[0])], "mode": mode}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def check(checks, name, passed, measured, expected, note=""):
    checks[name] = {"passed": bool(passed), "measured": measured, "expected": expected, "note": note}


# ------------------------------------------------------------------ inputs
def inputs(ta, repo):
    """Pinned inputs: the look-dev profile, files of the look-dev run and of its H2.1 source run (sha256 of the profile)."""
    repo = Path(repo)
    ld_path = repo / ta["lookdev_profile"]["path"]
    got = sha256(ld_path)
    if got != ta["lookdev_profile"]["sha256"]:
        raise RuntimeError("ta: look-dev profile %s sha256 %s != pinned %s" % (ld_path, got, ta["lookdev_profile"]["sha256"]))
    ld = load_json(ld_path)
    pins = {"lookdev_profile": {"path": ta["lookdev_profile"]["path"], "sha256": got}}
    ld_run = repo / ta["lookdev_run"]["path"]
    files = {}
    for key, rel in ta["lookdev_run"]["files"].items():
        p = ld_run / rel
        s = sha256(p)
        want = ta["lookdev_run"]["sha256"][key]
        if s != want:
            raise RuntimeError("ta: %s sha256 %s != pinned %s (look-dev run changed)" % (rel, s, want))
        files[key] = p
        pins["lookdev_run:" + key] = {"path": (Path(ta["lookdev_run"]["path"]) / rel).as_posix(), "sha256": s}
    src_run = repo / ld["source"]["run"]
    for key in ta["source_run_files"]:
        rel = ld["source"]["files"][key]
        p = src_run / rel
        s = sha256(p)
        if s != ld["source"]["sha256"][key]:
            raise RuntimeError("ta: source %s sha256 %s != pinned %s" % (rel, s, ld["source"]["sha256"][key]))
        files[key] = p
        pins["source_run:" + key] = {"path": (Path(ld["source"]["run"]) / rel).as_posix(), "sha256": s}
    return ld, files, pins


def presets(repo):
    return load_json(Path(repo) / "docs" / "art-pipeline" / "material-library" / "um-material-presets-v1.json")


# ------------------------------------------------------------------ geometry per texel
def texel_geometry(pos, cov):
    """Texel area (|dP/drow x dP/dcol|, clipped at 8 x median against island-edge jumps) and the unit normal of the
    position bake (sign convention irrelevant: only agreements between texels are used)."""
    dr = np.gradient(pos, axis=0)
    dc = np.gradient(pos, axis=1)
    n = np.cross(dr, dc)
    a = np.linalg.norm(n, axis=-1)
    nrm = n / np.maximum(a[..., None], 1e-20)
    a = np.where(cov, a, 0.0)
    a = np.minimum(a, float(np.median(a[cov])) * 8.0)
    return a.astype(np.float64), nrm


def in_boxes(pos, boxes):
    m = np.zeros(pos.shape[:2], bool)
    for b in boxes:
        lo, hi = np.array(b["min_m"]), np.array(b["max_m"])
        m |= np.all((pos >= lo) & (pos <= hi), axis=-1)
    return m


def ribbon_mask(lab, pid, pos, cfg, cidx):
    """The leather baldric: leather texels of the part above z_min, UV opening with a disk (drops the thin leather
    recesses of the gold belt and the rims of the gold bands), 3D components of the opened texels (voxel grid,
    26-connected), components >= min_component_opened_texels kept, then grown back inside the leather by
    reconstruct_px (geodesic dilation, 8-connected)."""
    leather = (lab == cidx[cfg["class"]]) & np.isin(pid, cfg["parts"])
    cand = leather & (pos[..., 2] >= float(cfg["z_min_m"]))
    rr = int(cfg["open_radius_px"])
    yy, xx = np.mgrid[-rr:rr + 1, -rr:rr + 1]
    disk = np.hypot(yy, xx) <= rr
    opened = ndimage.binary_opening(cand, structure=disk)
    ys, xs = np.nonzero(opened)
    p = pos[ys, xs].astype(np.float64)
    vox = float(cfg["voxel_m"])
    q = np.floor((p - p.min(0)) / vox).astype(np.int64)
    grid = np.zeros(tuple(q.max(0) + 1), bool)
    grid[tuple(q.T)] = True
    comp, n = ndimage.label(grid, structure=np.ones((3, 3, 3), bool))
    lt = comp[tuple(q.T)]
    sizes = np.bincount(lt, minlength=n + 1)
    keep_ids = [int(k) for k in np.nonzero(sizes >= int(cfg["min_component_opened_texels"]))[0] if k > 0]
    seed = np.zeros(lab.shape, bool)
    keep = np.isin(lt, keep_ids)
    seed[ys[keep], xs[keep]] = True
    out = seed.copy()
    st = np.ones((3, 3), bool)
    for _ in range(int(cfg["reconstruct_px"])):
        out = ndimage.binary_dilation(out, structure=st) & leather
    comps = []
    for k in keep_ids:
        pp = p[lt == k]
        comps.append({"opened_texels": int((lt == k).sum()), "min_m": [r(x, 4) for x in pp.min(0)],
                      "max_m": [r(x, 4) for x in pp.max(0)]})
    info = {"candidate_texels_4k": int(cand.sum()), "opened_texels_4k": int(opened.sum()), "components_3d": int(n),
            "kept_components": comps, "ribbon_texels_4k": int(out.sum()),
            "dropped_leather_above_z_texels_4k": int((cand & ~out).sum())}
    return out, info


def hem_strip(lab, pid, pos, nrm, cfg, cidx):
    """Dress cloth texels within width_m (3D) of a gold band texel of the skirt whose normal agrees
    (dot >= normal_agree_min; the other face of the cloth does not count); soft edge smoothstep over feather_m."""
    parts = np.isin(pid, cfg["parts"])
    gold = parts & (lab == cidx[cfg["band_class"]])
    band = gold & (pos[..., 2] < float(cfg["band_z_max_m"])) & ~in_boxes(pos, cfg.get("band_exclude_boxes", []))
    cloth = parts & (lab == cidx[cfg["cloth_class"]])
    tree = cKDTree(pos[band].astype(np.float64))
    bn = nrm[band]
    d, j = tree.query(pos[cloth].astype(np.float64), k=1, distance_upper_bound=float(cfg["search_max_m"]))
    ok = np.isfinite(d)
    jj = np.where(ok, j, 0)
    agree = ok & ((nrm[cloth] * bn[jj]).sum(-1) >= float(cfg["normal_agree_min"]))
    dist = np.full(lab.shape, np.inf)
    dist[cloth] = np.where(agree, d, np.inf)
    w, f = float(cfg["width_m"]), float(cfg["feather_m"])
    strip = np.where(cloth, smoothstep((w - dist) / f), 0.0)
    info = {"band_texels_4k": int(band.sum()), "gold_texels_of_parts_4k": int(gold.sum()),
            "band_excluded_texels_4k (belt, sash panel)": int((gold & ~band).sum()),
            "cloth_texels_4k": int(cloth.sum()), "cloth_with_agreeing_band_within_search": int(agree.sum()),
            "width_m": w, "feather_m": f}
    return strip, band, info


def team_accent(lab, pid, pos, cov, area, nrm, tcfg, cidx):
    strip, band, strip_info = hem_strip(lab, pid, pos, nrm, tcfg["hem"], cidx)
    ribbon, ribbon_info = ribbon_mask(lab, pid, pos, tcfg["ribbon"], cidx)
    raw = np.maximum(strip, ribbon.astype(np.float64)) * cov
    sig = float(tcfg["blur_sigma_px"])
    num = ndimage.gaussian_filter(raw, sig)
    den = ndimage.gaussian_filter(cov.astype(np.float64), sig)
    soft = np.where(cov, num / np.maximum(den, 1e-9), 0.0)
    allowed = (np.isin(pid, tcfg["hem"]["parts"]) & (lab == cidx[tcfg["hem"]["cloth_class"]])) | ribbon
    acc = np.clip(soft * allowed, 0.0, 1.0)
    _d, (iy, ix) = ndimage.distance_transform_edt(~cov, return_indices=True)
    acc = acc[iy, ix]  # atlas gutter: value of the nearest covered texel
    fig = cov & ~np.isin(pid, tcfg["figure_exclude_parts"])
    fa = float(area[fig].sum())
    info = {"hem": strip_info, "ribbon": ribbon_info,
            "share_3d_total": r(float((acc * area)[fig].sum()) / fa),
            "share_3d_hem": r(float((np.minimum(acc, strip) * area)[fig].sum()) / fa),
            "share_3d_ribbon": r(float((np.minimum(acc, ribbon) * area)[fig].sum()) / fa),
            "texels_4k_ge_0_5": int((acc[cov] >= 0.5).sum()),
            "figure_area_m2": r(fa, 6),
            "area_method": "texel area = |dPOS/drow x dPOS/dcol| of the H2.1 position bake (authored frame, metres), "
                           "clipped at 8 x median against island-edge jumps; figure = all parts but %s (the base)"
                           % tcfg["figure_exclude_parts"]}
    return acc, strip, ribbon, band, info


# ------------------------------------------------------------------ stage ta_maps
def run_maps(run_dir, ta, repo):
    run_dir, repo = Path(run_dir), Path(repo)
    ld, files, pins = inputs(ta, repo)
    pr = presets(repo)
    cidx = {c["id"]: int(c["index"]) for c in pr["classes"]}
    byidx = {int(c["index"]): c for c in pr["classes"]}
    tcfg = ta["team_accent"]
    checks = {}
    pid = np.load(files["part_ids"])
    pos = np.load(files["position"]).astype(np.float64)
    cov = pid >= 0
    matid4 = read_png(files["MatID"])
    lab = (matid4.astype(np.int32) // 16).astype(np.int16)
    labels_in_cov = sorted(int(x) for x in np.unique(lab[cov]))
    area, nrm = texel_geometry(pos, cov)
    acc, strip, ribbon, band, info = team_accent(lab, pid, pos, cov, area, nrm, tcfg, cidx)
    lo, hi = tcfg["area_share_range"]
    check(checks, "team_accent_area_share", lo <= info["share_3d_total"] <= hi,
          {k: info[k] for k in ("share_3d_total", "share_3d_hem", "share_3d_ribbon")}, [lo, hi],
          "share of the figure's 3D surface (all parts but the base)")
    # ---- zero outside the dyeable accent zones (core texels = class interior, eroded 2 px), 8 bit
    acc8 = to8(acc)
    never = tcfg["never_classes"]
    leak = {}
    for cid in never:
        m = cov & ndimage.binary_erosion(lab == cidx[cid], iterations=2)
        leak[cid] = int(acc8[m].max()) if m.any() else 0
    check(checks, "team_accent_zero_on_never_classes_4k", all(v == 0 for v in leak.values()), leak,
          "0 (8 bit) on the core texels of %s" % never)
    # the same at 2K (runtime): 2K class = the 2K MatID of the run (2 x 2 majority)
    acc2f = box2(acc)
    acc2 = to8(acc2f)
    lab2 = (read_png(files["2K_MatID"]).astype(np.int32) // 16).astype(np.int16)
    cov2 = box2(cov.astype(np.float64)) >= 0.5
    leak2 = {}
    for cid in never:
        m = cov2 & ndimage.binary_erosion(lab2 == cidx[cid], iterations=2)
        leak2[cid] = int(acc2[m].max()) if m.any() else 0
    check(checks, "team_accent_zero_on_never_classes_2k", all(v == 0 for v in leak2.values()), leak2,
          "0 (8 bit) on the 2K core texels (class interior eroded 2 px of the 2K MatID)")
    # ---- teamDyeAllowed: the accent lives only on classes the v2 master may dye (then TeamMaskTexture = TeamAccent
    #      dyes exactly the accent; no class of the hero with teamDyeAllowed gets dye outside it)
    dye_ok = [i for i, c in byidx.items() if i and c.get("teamDyeAllowed")]
    off = cov & (acc > 0) & ~np.isin(lab, dye_ok)
    check(checks, "team_accent_only_on_dye_allowed_classes", int(off.sum()) == 0,
          {"texels_4k_with_accent_on_classes_without_teamDyeAllowed": int(off.sum()),
           "accent_classes": sorted({byidx[int(x)]["id"] for x in np.unique(lab[cov & (acc > 0)])})},
          "0: the accent only on classes with teamDyeAllowed (linen, leather_smooth)")
    # ---- the dress keeps the concept colour: share of the dress cloth core texels with accent >= 0.5, per part
    dress = tcfg["dress_parts"]
    per = {}
    for name, part in dress.items():
        m = (pid == int(part)) & (lab == cidx[tcfg["hem"]["cloth_class"]]) & ndimage.binary_erosion(
            lab == cidx[tcfg["hem"]["cloth_class"]], iterations=2)
        per[name] = {"part": int(part), "core_texels_4k": int(m.sum()),
                     "accent_ge_0_5_share": r(float((acc[m] >= 0.5).mean()) if m.any() else 1.0),
                     "accent_ge_0_5_share_3d": r(float((area * (acc >= 0.5))[m].sum() / max(area[m].sum(), 1e-12)))}
    mx = float(tcfg["dress_core_share_max"])
    check(checks, "dress_keeps_concept_colour_per_part", all(v["accent_ge_0_5_share_3d"] <= mx for v in per.values()),
          per, "<= %s of the dress cloth (3D area of the core texels) carries the accent >= 0.5" % mx,
          "the dress stays plum-charcoal as in the concept; the accent is a hem strip")
    # ---- the old TeamMask is untouched (deprecated, kept for compatibility)
    tm_same = {k: sha256(files[k]) == ta["lookdev_run"]["sha256"][k] for k in ("TeamMask", "2K_TeamMask")}
    check(checks, "old_teammask_unchanged", all(tm_same.values()), tm_same,
          "T_Medusa_H2LD_{,2K_}TeamMask.png of the look-dev run byte-identical (deprecated, not rewritten)")
    # ---- geometry, rig and UV are not touched: the look-dev FBX pair on disk = the bytes ld_fbx read back (its report:
    #      positions / UV0 per loop, bones = H2.1); the mask lives in UV0 of the same atlas (size = MatID)
    ld_run = Path(repo) / ta["lookdev_run"]["path"]
    fbx_rep = load_json(ld_run / "reports" / "ld-fbx-report.json")
    fbx = {}
    for key in ("skeletal_fbx", "base_fbx"):
        e = fbx_rep["exports"][key]
        p = ld_run / "export" / Path(e["path"]).name
        fbx[key] = {"file": Path(e["path"]).name, "sha256_equals_ld_fbx_readback": sha256(p) == e["sha256"]}
    geo_ok = all(v["sha256_equals_ld_fbx_readback"] for v in fbx.values()) and fbx_rep.get("passed") is True
    check(checks, "geometry_rig_uv_unchanged", geo_ok and acc.shape == matid4.shape,
          {"fbx": fbx, "ld_fbx_passed": fbx_rep.get("passed"),
           "ld_fbx_checks": sorted(k for k, c in fbx_rep["checks"].items() if c.get("passed")),
           "mask_px_4k": list(acc.shape), "matid_px_4k": list(matid4.shape)},
          "the FBX pair = the ld_fbx read-back bytes (positions / UV0 per loop and bones = H2.1); mask on UV0 of the atlas")
    # ---- TeamDyeGain of the MI (team-accent.md rule) on the look-dev BC (4K, linear)
    bc = lin(read_png(files["BC"]).astype(np.float64) / 255.0)
    y = bc @ LUM
    sel = cov & (acc >= 0.5)
    ya = np.clip(y[sel], 0.02, 0.8)
    ymed_a, yp95_a = float(np.median(ya)), float(np.percentile(ya, 95))
    pal = tcfg["palette"]
    tmax = max(max(hex_lin(pal[k])) for k in ("P1", "P2"))
    gr = tcfg["team_dye_gain_rule"]
    g_med = float(gr["median_target"]) / ymed_a
    g_p95 = float(gr["p95_max_albedo"]) / (tmax * yp95_a)
    gain = float(np.floor(min(g_med, g_p95) / gr["round_to"]) * gr["round_to"])
    zone_y = {}
    for zname, zm in (("hem", sel & (strip >= 0.5)), ("ribbon", sel & ribbon)):
        if zm.any():
            zone_y[zname] = [r(np.median(y[zm]), 5), r(np.percentile(y[zm], 95), 5)]
    dye_gain = {"accent_Y_p50_p95": [r(ymed_a, 5), r(yp95_a, 5)], "accent_Y_p50_p95_by_zone": zone_y,
                "gain_for_median": r(g_med, 3), "gain_for_p95": r(g_p95, 3), "palette_max_channel_linear": r(tmax, 4),
                "TeamDyeGain": gain, "dyed_accent_albedo_median_over_team": r(ymed_a * gain),
                "dyed_accent_albedo_p95_max_channel": r(yp95_a * gain * tmax), "rule": gr["note"],
                "previous_MI_value": tcfg.get("previous_team_dye_gain")}
    # ---- emulated render sets: the dye of um_v2_core.hlsl (after the class clamp, which the look-dev BC already has)
    allowed_cls = np.zeros(16, np.float64)
    for i, c in byidx.items():
        if i < 16:
            allowed_cls[i] = 1.0 if (i == 0 or c.get("teamDyeAllowed")) else 0.0
    wdye = acc * allowed_cls[np.clip(lab, 0, 15)] * float(tcfg["team_dye"])
    work = run_dir / "work" / "ta"
    sets = {}
    for key in ("P1", "P2"):
        team = np.array(hex_lin(pal[key]))
        dyed = team[None, None, :] * y[..., None] * gain
        dyed = (1 - float(tcfg["team_dye"])) * bc * team + float(tcfg["team_dye"]) * dyed
        out = bc * (1 - wdye[..., None]) + dyed * wdye[..., None]
        p = work / "sets" / ("ld_%s" % key.lower()) / "BC.png"
        sets["ld_%s" % key.lower()] = dict(save_png(to8(srgb(out)), p, "RGB"), file=p.relative_to(run_dir).as_posix())
    # ID texture of the frames: R = MatID, G = accent >= 0.5, B = 255 (figure)
    idt = np.zeros(lab.shape + (3,), np.uint8)
    idt[..., 0] = matid4
    idt[..., 1] = np.where(acc >= 0.5, ACCENT_ID_G, 0).astype(np.uint8)
    idt[..., 2] = 255
    p = work / "id" / "id_accent.png"
    sets["id"] = dict(save_png(idt, p, "RGB"), file=p.relative_to(run_dir).as_posix())
    np.save(work / "accent_4k.npy", acc.astype(np.float32))
    # the hero LUT for the Blender material (st_lookdev.lut_material reads EXR): the pinned DDS of the look-dev run
    import importlib.util
    spec = importlib.util.spec_from_file_location("h2ld_lookdev", HERE / "lookdev.py")
    LDM = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(LDM)
    lut = LDM.read_dds_rgba16f(files["LUT_dds"])
    LDM.write_exr(work / ("%s.exr" % ld["lut_name"]), lut)
    sets["lut_exr"] = {"file": (work / ("%s.exr" % ld["lut_name"])).relative_to(run_dir).as_posix(),
                       "from": "the pinned DDS of the look-dev run (lookdev.write_exr, HALF)"}
    # ---- textures
    tex = run_dir / "textures"
    px = ta["prefix"]
    outputs = {}
    outputs["%s_TeamAccent_4K.png" % px] = save_png(acc8, tex / ("%s_TeamAccent_4K.png" % px), "L")
    outputs["%s_TeamAccent_2K.png" % px] = save_png(acc2, tex / ("%s_TeamAccent_2K.png" % px), "L")
    back = read_png(tex / ("%s_TeamAccent_2K.png" % px))
    check(checks, "team_accent_2k_readback", bool(np.array_equal(back, acc2)) and back.dtype == np.uint8 and back.ndim == 2,
          {"mode": "L", "px": list(back.shape)}, "L8 2048 x 2048, bytes = the box of the 4K float mask")
    # ---- previews
    prev = run_dir / "preview"
    bc2 = srgb(box2(box2(bc)))
    a1 = box2(acc2f)[..., None]
    vis = bc2 * (1 - a1 * 0.85) + np.array([1.0, 0.0, 1.0]) * a1 * 0.85
    outputs["preview/ld_teamaccent_1K.png"] = save_png(to8(vis), prev / "ld_teamaccent_1K.png", "RGB")
    report = {"stage": "ta_maps", "profile_id": ta["profile_id"], "pins": pins, "labels_in_coverage": labels_in_cov,
              "team_accent": info, "dress_core_by_part": per, "team_dye_gain": dye_gain,
              "mi_parameters": {"TeamDye": float(tcfg["team_dye"]), "TeamDyeGain": gain,
                                "TeamMaskTexture": "T_%s_TeamAccent (textures/%s_TeamAccent_2K.png)" % (px[2:], px),
                                "note": "M_UM_Figure_v2 без изменения графа: слот TeamMaskTexture MI героя = TeamAccent "
                                        "(вместо T_Medusa_H2LD_2K_TeamMask, W4-B, deprecated). Маска ненулевая только на "
                                        "классах с teamDyeAllowed (проверка team_accent_only_on_dye_allowed_classes), "
                                        "поэтому TeamAccent x teamDyeAllowed = TeamAccent: красится ровно акцент."},
              "conventions": {
                  "TeamAccent": "L8 linear (UE TC_Grayscale, sRGB off, mips normal): 0 = concept colour, 1 = full team dye; "
                                "UV0 of the atlas; gutter = nearest covered texel; team-accent.md",
                  "TeamMask": "T_Medusa_H2LD_{,2K_}TeamMask.png (R = the whole dress cloth, G base band): DEPRECATED, kept "
                              "byte-identical for compatibility (v1 MIs, the LD-medusa-ue import of 2026-09-29)"},
              "render_sets": sets, "outputs": outputs, "checks": checks,
              "passed": all(c["passed"] for c in checks.values()), "status": "измерено"}
    write_json(run_dir / "reports" / "ld-team-accent-report.json", report)
    print("ta_maps passed=%s" % report["passed"], [k for k, c in checks.items() if not c["passed"]],
          "share", info["share_3d_total"], info["share_3d_hem"], info["share_3d_ribbon"], "gain", gain, flush=True)
    if not report["passed"]:
        raise RuntimeError("ta_maps checks failed: %s" % [k for k, c in checks.items() if not c["passed"]])
    return report


# ------------------------------------------------------------------ stage ta_report
def lab_of(rgb8):
    li = lin(np.asarray(rgb8, np.float64) / 255.0)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = li @ M.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def decode_id(path):
    """ID frame (Cycles emission of the ID texture, Raw, 1 sample): class, accent, figure masks."""
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    fig = (a[..., 3] >= 250) & (a[..., 2] >= 250)
    cls = np.clip(np.floor(a[..., 0] / 16.0), 0, 15).astype(np.int16)
    cls[~fig] = -1
    acc = fig & (a[..., 1] >= 128)
    return cls, acc, fig


def img8(path):
    return np.asarray(Image.open(path).convert("RGB"))


def view_metrics(rdir, view, cidx, near_px):
    cls, acc, fig = decode_id(rdir / "id" / (view + ".png"))
    body = fig & (cls != cidx["stone_base"])
    linen = (cls == cidx["linen"]) & ~acc
    gold = cls == cidx["gold_antique"]
    acc_e = ndimage.binary_erosion(acc, iterations=1)
    if acc_e.sum() < 20:  # K2 1.6x: the strip is 1-2 px wide, erosion leaves nothing -> the accent pixels themselves
        acc_e = acc
    near = ndimage.binary_dilation(acc, iterations=near_px) & ndimage.binary_erosion(linen, iterations=1)
    frames = {s: img8(rdir / "cobble" / s / (view + ".png")) for s in ("ld", "ld_p1", "ld_p2")}
    L = {s: lab_of(v) for s, v in frames.items()}
    e = {"accent_px": int(acc.sum()), "figure_px_without_base": int(body.sum()),
         "screen_share_of_figure": r(acc.sum() / max(int(body.sum()), 1)),
         "dress_px_without_accent": int(ndimage.binary_erosion(linen, iterations=1).sum())}
    lin_e = ndimage.binary_erosion(linen, iterations=1)
    for s in ("ld", "ld_p1", "ld_p2"):
        if acc_e.sum() < 20 or near.sum() < 20:
            continue
        ma, mn = L[s][acc_e].mean(0), L[s][near].mean(0)
        gnear = ndimage.binary_dilation(acc, iterations=near_px) & ndimage.binary_erosion(gold, iterations=1)
        mg = L[s][gnear].mean(0) if gnear.sum() >= 20 else None
        e[s] = {"accent_lab": [r(x, 1) for x in ma], "dress_next_to_it_lab": [r(x, 1) for x in mn],
                "delta_e_accent_vs_dress": r(np.linalg.norm(ma - mn), 1),
                "delta_e_accent_vs_gold_trim_next_to_it": r(np.linalg.norm(ma - mg), 1) if mg is not None else None,
                "accent_median_srgb": [int(x) for x in np.median(frames[s][acc_e], 0)]}
    if acc_e.sum() >= 20:
        e["delta_e_p1_vs_p2_accent"] = r(np.linalg.norm(L["ld_p1"][acc_e].mean(0) - L["ld_p2"][acc_e].mean(0)), 1)
    for s in ("ld_p1", "ld_p2"):
        dd = np.linalg.norm(L[s] - L["ld"], axis=-1)
        e["dress_unchanged_" + s] = {"median_delta_e": r(np.median(dd[lin_e]), 2) if lin_e.any() else None,
                                     "share_delta_e_lt_3": r((dd[lin_e] < 3).mean()) if lin_e.any() else None}
        ge = ndimage.binary_erosion(gold, iterations=1)
        e["gold_unchanged_" + s] = {"median_delta_e": r(np.median(dd[ge]), 2) if ge.any() else None,
                                    "share_delta_e_lt_3": r((dd[ge] < 3).mean()) if ge.any() else None}
        e["accent_changed_" + s] = {"median_delta_e_vs_no_dye": r(np.median(dd[acc_e]), 1) if acc_e.any() else None}
    return e


def font(size):
    from PIL import ImageFont
    for f in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def labelled(im, text, size=15):
    lines = text.split("\n")
    hh = (size + 6) * len(lines) + 6
    out = Image.new("RGB", (im.width, im.height + hh), (20, 20, 22))
    out.paste(im, (0, hh))
    d = ImageDraw.Draw(out)
    for i, t in enumerate(lines):
        d.text((6, 4 + i * (size + 6)), t, fill=(240, 240, 240), font=font(size))
    return out


def hstack(ims, bg=(20, 20, 22)):
    h = max(i.height for i in ims)
    out = Image.new("RGB", (sum(i.width for i in ims), h), bg)
    x = 0
    for i in ims:
        out.paste(i, (x, 0))
        x += i.width
    return out


def vstack(ims, bg=(20, 20, 22)):
    w = max(i.width for i in ims)
    out = Image.new("RGB", (w, sum(i.height for i in ims)), bg)
    y = 0
    for i in ims:
        out.paste(i, (0, y))
        y += i.height
    return out


def fig_box(rdir, view, margin=0.12):
    _c, _a, fig = decode_id(rdir / "id" / (view + ".png"))
    ys, xs = np.nonzero(fig)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    return (int(max(x0 - mx, 0)), int(max(y0 - my, 0)), int(min(x1 + mx, fig.shape[1])), int(min(y1 + my, fig.shape[0])))


def concept_tile(path, h):
    im = Image.open(path).convert("RGB")
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


SET_LABEL = {"ld": "look-dev v2 без красителя", "ld_p1": "TeamAccent P1 #E8C06A", "ld_p2": "TeamAccent P2 #5A7F9F"}


def sheets(ta, repo, run_dir, rdir, gain):
    prev = run_dir / "preview"
    out = {}
    note = ("blender · EEVEE · свет ≈ Cobble, экспозиция откалибрована по якорю W4-A (K1 доска p50 131,2) · кроп по фигуре\n"
            "краситель = эмуляция um_v2_core.hlsl на BC look-dev (TeamDye 1, TeamDyeGain %s, маска TeamAccent) · это НЕ UE" % gain)
    for tag, views, h in (("k2_5x", ta["render"]["sheet_views"]["k2_5x"], 620), ("k2_1p6", ta["render"]["sheet_views"]["k2_1p6"], 420)):
        rows = []
        for view, concept_key in views:
            box = fig_box(rdir, view)
            cells = [labelled(concept_tile(Path(repo) / ta["concepts"][concept_key], h), "концепт · %s" % concept_key)]
            for s in ("ld", "ld_p1", "ld_p2"):
                im = Image.open(rdir / "cobble" / s / (view + ".png")).convert("RGB").crop(box)
                sc = h / im.height
                im = im.resize((round(im.width * sc), h), Image.LANCZOS if tag == "k2_5x" else Image.NEAREST)
                cells.append(labelled(im, "%s · %s" % (SET_LABEL[s], view)))
            rows.append(hstack(cells))
        sheet = labelled(vstack(rows), note, 16)
        p = prev / ("ld_team_%s_cobble.jpg" % tag)
        sheet.save(p, format="JPEG", quality=92)
        out[p.name] = sha256(p)
    # ID of the accent on the K2 5x frames (magenta = accent, grey = figure, dark = base)
    cells = []
    for view, _c in ta["render"]["sheet_views"]["k2_5x"]:
        cls, acc, fig = decode_id(rdir / "id" / (view + ".png"))
        vis = np.zeros(cls.shape + (3,), np.uint8)
        vis[fig] = (110, 110, 110)
        vis[cls == 4] = (200, 170, 40)
        vis[cls == 14] = (50, 60, 50)
        vis[acc] = (255, 0, 255)
        box = fig_box(rdir, view)
        im = Image.fromarray(vis).crop(box)
        im = im.resize((round(im.width * 620 / im.height), 620), Image.NEAREST)
        cells.append(labelled(im, "ID: акцент (пурпур), золото, подставка · %s" % view))
    p = prev / "ld_team_id_k2.jpg"
    hstack(cells).save(p, format="JPEG", quality=92)
    out[p.name] = sha256(p)
    return out


def run_report(run_dir, ta, repo):
    run_dir, repo = Path(run_dir), Path(repo)
    pr = presets(repo)
    cidx = {c["id"]: int(c["index"]) for c in pr["classes"]}
    rdir = run_dir / "work" / "ta" / "render"
    maps = load_json(run_dir / "reports" / "ld-team-accent-report.json")
    rend = load_json(rdir / "render-report.json")
    gain = maps["team_dye_gain"]["TeamDyeGain"]
    checks = {}
    views = ta["render"]["views"]
    per = {v: view_metrics(rdir, v, cidx, int(ta["render"]["near_px"])) for v in views}
    rd = ta["render"]["readability"]
    k2 = [v for v in views if v.startswith("k2_5x")]
    de_min = min(per[v][s]["delta_e_accent_vs_dress"] for v in views for s in ("ld_p1", "ld_p2") if s in per[v])
    pp_min = min(per[v]["delta_e_p1_vs_p2_accent"] for v in views if "delta_e_p1_vs_p2_accent" in per[v])
    check(checks, "team_accent_reads_at_k2", de_min >= rd["delta_e_accent_vs_dress_min"] and pp_min >= rd["delta_e_p1_vs_p2_min"],
          {"min_delta_e_accent_vs_dress": de_min, "min_delta_e_p1_vs_p2": pp_min},
          "CIELAB dE >= %s against the dress next to it, >= %s between P1 and P2 (Cobble, %s)"
          % (rd["delta_e_accent_vs_dress_min"], rd["delta_e_p1_vs_p2_min"], ", ".join(views)))
    sh = {v: per[v]["screen_share_of_figure"] for v in k2}
    check(checks, "team_accent_visible_k2_5x_front_and_back", all(x >= rd["screen_share_min"] for x in sh.values()), sh,
          ">= %s of the figure pixels (without the base) on K2 5x front and back" % rd["screen_share_min"])
    dr_ = {v: {s: per[v]["dress_unchanged_" + s]["share_delta_e_lt_3"] for s in ("ld_p1", "ld_p2")} for v in views}
    check(checks, "dress_outside_accent_unchanged_by_dye",
          all(x is not None and x >= rd["dress_unchanged_share_min"] for d in dr_.values() for x in d.values()), dr_,
          ">= %s of the dress pixels outside the accent change by dE < 3 with P1 / P2" % rd["dress_unchanged_share_min"],
          "the dress stays in the concept colour; the rest is the anti-aliased rim of the accent and the dyed bounce light")
    gd = {v: {s: per[v]["gold_unchanged_" + s]["median_delta_e"] for s in ("ld_p1", "ld_p2")} for v in views}
    check(checks, "gold_unchanged_by_dye", all(x is not None and x <= rd["gold_median_delta_e_max"] for d in gd.values() for x in d.values()),
          gd, "median dE of the gold pixels (meander, belt) with P1 / P2 against no dye <= %s" % rd["gold_median_delta_e_max"])
    check(checks, "ta_maps_passed", maps["passed"], [k for k, c in maps["checks"].items() if not c["passed"]], [])
    cal = rend["lights"]["cobble"]
    check(checks, "cobble_exposure_calibrated_to_w4a", abs(cal["k1_board_p50"] - ta["cobble"]["exposure_calibration"]["target_board_p50_luma"])
          <= ta["cobble"]["exposure_calibration"]["tolerance_luma"], cal["k1_board_p50"],
          "K1 board ROI p50 = %s +- %s" % (ta["cobble"]["exposure_calibration"]["target_board_p50_luma"],
                                           ta["cobble"]["exposure_calibration"]["tolerance_luma"]))
    sh_ = sheets(ta, repo, run_dir, rdir, gain)
    rep = {"stage": "ta_report", "profile_id": ta["profile_id"], "per_view": per, "sheets": sh_,
           "render": {"lights": rend["lights"], "frames": rend["frames"], "views": rend.get("views")},
           "label": "blender (EEVEE) кадры, эмуляция красителя v2 на BC look-dev; не UE, не художественная приёмка",
           "checks": checks, "passed": all(c["passed"] for c in checks.values()), "status": "измерено"}
    write_json(run_dir / "reports" / "ld-team-report.json", rep)
    print("ta_report passed=%s" % rep["passed"], [k for k, c in checks.items() if not c["passed"]], flush=True)
    return rep


def run_manifest(run_dir, ta, ta_path, repo, blender_version):
    run_dir, repo = Path(run_dir), Path(repo)
    maps = load_json(run_dir / "reports" / "ld-team-accent-report.json")
    outs = {}
    for rel in ("reports/ld-team-accent-report.json", "reports/ld-team-report.json", "reports/ld-team-cobble-calibration.json",
                "reports/ld-team-determinism.json"):
        p = run_dir / rel
        if p.is_file():
            outs[rel] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    for name in sorted(maps["outputs"]):
        p = run_dir / (name if name.startswith("preview/") else "textures/" + name)
        outs[p.relative_to(run_dir).as_posix()] = {"sha256": sha256(p), "bytes": p.stat().st_size,
                                                   "committed": not name.endswith("_4K.png")}
    for p in sorted((run_dir / "preview").glob("ld_team_*.jpg")):
        outs[p.relative_to(run_dir).as_posix()] = {"sha256": sha256(p), "bytes": p.stat().st_size}
    mods = {p.name: sha256(p) for p in (HERE / "lookdev_accent.py", HERE / "st_team.py", HERE / "st_lookdev.py",
                                        HERE / "run_h2_bake.py", HERE / "blender_entry.py")}
    man = {"schema": "unmatched.h2-lookdev-teamaccent-run/1", "asset_id": ta["asset_id"],
           "profile": {"path": Path(ta_path).resolve().relative_to(repo).as_posix(), "sha256": sha256(ta_path),
                       "profile_id": ta["profile_id"]},
           "pins": maps["pins"], "modules": mods, "blender": blender_version, "outputs": outs,
           "untouched": "look-dev profile, ld-maps-report.json, run-manifest.json and every texture of ld_maps (pinned by "
                        "the LD-medusa-ue import) are only read",
           "network": {"tripo_calls": 0, "paid_tasks_created": 0},
           "claims": {"art_accepted": False, "game_ready": False, "ue_checked": False}, "status": "измерено"}
    write_json(run_dir / "reports" / "ld-team-manifest.json", man)
    return man
