"""Stage `ld_report` (system python): measurements of the final look-dev frames, sheets, reports of King Arthur.

    python lookdev_report.py <lookdev profile.json> <lookdev run dir>

Reads work/lookdev/render_final (ld_render_final: studio_env ortho + close-ups, Cobble K2 + close-ups, zone / accent ID
frames) and the reports of the earlier stages. Measures:
  steel    the H2.2 relative check on the final frames (h22, h2, ld) and steel / board on the Cobble K2 5x frames
  zones    per zone and view: luminance ratio render / concept at the stone exposure, hue and saturation difference
           (before = h22, after = ld)
  accent   screen share of the TeamAccent on the Cobble K2 frames (accent ID pixels / figure pixels), CIELAB contrast of
           the accent against the red cloth next to it (<= 6 px) and between the P1 and P2 frames
  tabard   red share of the tabard's red cloth pixels (tabard ID frame) with P1 / P2 against no dye (rev. 2)
Writes preview/ld_*.jpg (sheets, every frame labelled "blender"), preview/ld_concept_zones_*.png,
reports/ld-metrics.json, reports/textures-report.json, reports/ld-report.json (all checks), reports/manifest-ld.json.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lookdev_emul as E  # noqa: E402
import lookdev_maps as LM  # noqa: E402
import lookdev_state as S  # noqa: E402
import lookdev_tone as LT  # noqa: E402
import pure as P  # noqa: E402
import steelcheck as SC  # noqa: E402
from sheets import hstack, label, save_jpg, vstack  # noqa: E402

LUM = np.array([0.2126, 0.7152, 0.0722])
SET_LABEL = {"h22": "прежний: H2.2 ред. 2 (8a788343)", "h2": "H2 (9a2a5184)", "ld": "look-dev v2 (эмуляция M_UM_Figure_v2), без красителя",
             "ld_p1": "look-dev v2 · TeamAccent P1 #E8C06A", "ld_p2": "look-dev v2 · TeamAccent P2 #5A7F9F"}


def lab(rgb):
    li = E.lin(rgb)
    M = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = li @ M.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def colour_mask(img, rgb, tol=3):
    return np.abs(img * 255.0 - np.array(rgb)).sum(axis=2) <= tol


def accent_metrics(rdir, views):
    out = {}
    for v in views:
        a = LT.load_img(rdir / "id" / "accent" / (v + ".png"))
        z = LT.load_img(rdir / "id" / "zones" / (v + ".png"))
        acc = colour_mask(a, LM.ACCENT_RGB)
        fig = np.zeros(acc.shape, bool)
        for rgb in LM.ZONE_RGB.values():
            fig |= colour_mask(z, rgb)
        body = fig & ~colour_mask(z, LM.ZONE_RGB["base"])
        cloth = colour_mask(z, LM.ZONE_RGB["cloth"])
        near = ndimage.binary_dilation(acc, iterations=6) & cloth & ~acc
        acc_e = ndimage.binary_erosion(acc, iterations=1)
        e = {"accent_px": int(acc.sum()), "figure_px_without_base": int(body.sum()),
             "screen_share_of_figure": P.r(float(acc.sum()) / max(int(body.sum()), 1), 4)}
        labs = {}
        for s in ("ld", "ld_p1", "ld_p2"):
            im = LT.load_img(rdir / "cobble" / s / (v + ".png"))
            L = lab(im)
            ma, mn = L[acc_e].mean(0), L[near].mean(0)
            labs[s] = ma
            e[s] = {"accent_lab": P.rv(ma, 1), "cloth_next_to_it_lab": P.rv(mn, 1),
                    "delta_e_accent_vs_cloth": P.r(float(np.linalg.norm(ma - mn)), 1)}
        e["delta_e_p1_vs_p2"] = P.r(float(np.linalg.norm(labs["ld_p1"] - labs["ld_p2"])), 1)
        out[v] = e
    return out


TABARD_VIEWS = ["k2_5x_az0", "k2_5x_az-40", "k2_1p6_az0", "k2_1p6_az-40", "close_torso_az0"]
RED_HUE_DEG = 20.0      # red: display hue within +-20 deg of 0 and saturation >= RED_SAT_MIN (the painted cloth: hue
RED_SAT_MIN = 0.35      # 355-5 deg, s 0.6-0.8; P1 #E8C06A dyed = hue ~40, P2 #5A7F9F = hue ~210)


def red_share(im, mask):
    h, s, _v = SC.hsv_img(im)
    red = ((h <= RED_HUE_DEG) | (h >= 360 - RED_HUE_DEG)) & (s >= RED_SAT_MIN)
    return float(red[mask].mean())


def tabard_red_metrics(rdir, cobble_dir, views=TABARD_VIEWS, min_px=200):
    """Red share of the tabard's red cloth pixels (tabard ID frame, eroded 1 px) on the Cobble frames without dye and
    with P1 / P2; ratio = dyed / no dye (rev. 2 check: the tabard stays red)."""
    out = {}
    for v in views:
        t = LT.load_img(rdir / "id" / "tabard" / (v + ".png"))
        m = ndimage.binary_erosion(colour_mask(t, LM.TABARD_RGB), iterations=1)
        if int(m.sum()) < min_px:
            continue
        e = {"tabard_px": int(m.sum())}
        for s in ("ld", "ld_p1", "ld_p2"):
            e[s] = P.r(red_share(LT.load_img(Path(cobble_dir) / s / (v + ".png")), m), 4)
        for s in ("ld_p1", "ld_p2"):
            e["ratio_" + s] = P.r(e[s] / max(e["ld"], 1e-6), 4)
        out[v] = e
    return out


def hue_sat(rgb_lin):
    s = E.srgb(np.asarray(rgb_lin, np.float64)[None, None, :])
    h, sat, _v = SC.hsv_img(s)
    return float(h[0, 0]), float(sat[0, 0])


def zone_metrics(concept, per, zones):
    out = {}
    for z in zones:
        e = {}
        for s in ("h22", "ld"):
            rows = []
            for view, ce in concept.items():
                c = ce.get("zone:" + z)
                r = per[s]["views"].get(view, {}).get("zone:" + z)
                if c is None or r is None or c["n"] < 150 or r["n"] < 150:
                    continue
                k = ce["stone"]["Y_mean"] / per[s]["views"][view]["stone"]["Y_mean"]
                cm, rm = c["median_rgb"], r["median_rgb"] * k
                hc, sc_ = hue_sat(cm)
                hr, sr = hue_sat(rm)
                dh = ((hr - hc + 180) % 360) - 180
                rows.append({"view": view, "luma_ratio": P.r(float(rm @ LUM) / float(cm @ LUM), 3), "d_hue_deg": P.r(dh, 1),
                             "d_sat": P.r(sr - sc_, 3)})
            if rows:
                e[s] = {"views": rows, "median": {k: P.r(float(np.median([r_[k] for r_ in rows])), 3)
                                                  for k in ("luma_ratio", "d_hue_deg", "d_sat")}}
        out[z] = e
    return out


def concept_overlays(prof, src, paths):
    cz = prof["lookdev"]["concept_zones"]
    sc = src["review_h22"]["steel_check"]
    cols = {"cloth": (255, 40, 40), "embroidery": (255, 140, 0), "gold": (255, 230, 0), "belt": (140, 80, 30),
            "face_skin": (255, 190, 160), "hair": (80, 200, 80), "base": (80, 160, 255), "steel": (0, 200, 255)}
    out = {}
    for view in ("front", "side", "back"):
        cimg = LT.load_img(P.repo_path(src["sources"]["concepts"][view]))
        vis = (cimg * 0.4 * 255).astype(np.uint8)
        steel = SC.zone_mask(cimg.shape, sc["concept_zones"][view]) & SC.gate(cimg, sc["gate"])
        vis[steel] = np.array(cols["steel"], np.uint8)
        for zone in {e["zone"] for e in cz[view]}:
            m = LT.concept_zone_mask(cimg, cz[view], cz["filters"], zone)
            vis[m] = np.array(cols[zone], np.uint8)
        im = Image.fromarray(vis)
        d = ImageDraw.Draw(im)
        for e in cz[view]:
            d.rectangle(e["box"], outline=cols[e["zone"]], width=2)
        p = paths["preview"] / ("ld_concept_zones_%s.png" % view)
        im.save(p, format="PNG", compress_level=6)
        out[view] = {"file": P.rel(p), "sha256": P.sha256(p)}
    return out


def img(path, h=None, crop=None):
    im = Image.open(path).convert("RGB")
    if crop:
        im = im.crop(crop)
    if h:
        im = im.resize((round(im.width * h / im.height), h), Image.LANCZOS)
    return im


def sheets(prof, src, paths, rdir):
    out = {}
    pv = paths["preview"]
    for view, rview in LT.VIEW_OF.items():
        cells = [label(img(P.repo_path(src["sources"]["concepts"][view]), 900), "концепт H2 · %s" % view, 16)]
        for s in ("h22", "h2", "ld"):
            cells.append(label(img(rdir / "studio_env" / s / (rview + ".png"), 900),
                               "blender · EEVEE · studio_env · %s · %s" % (SET_LABEL[s], rview), 14))
        out["sheet_" + view] = save_jpg(hstack(cells), pv / ("ld_sbs_%s.jpg" % view))
    def fig_box(v, margin=0.18):
        z = LT.load_img(rdir / "id" / "zones" / (v + ".png"))
        fig = np.zeros(z.shape[:2], bool)
        for rgb in LM.ZONE_RGB.values():
            fig |= colour_mask(z, rgb)
        ys, xs = np.nonzero(fig)
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        mx, my = (x1 - x0) * margin, (y1 - y0) * margin
        return (int(max(x0 - mx, 0)), int(max(y0 - my, 0)), int(min(x1 + mx, z.shape[1])), int(min(y1 + my, z.shape[0])))

    for tag, views in (("k2_5x", ("k2_5x_az0", "k2_5x_az-40", "k2_5x_az180")), ("k2_1p6", ("k2_1p6_az0", "k2_1p6_az-40"))):
        rows = []
        for v in views:
            box = fig_box(v)
            cells = []
            for s in ("h22", "ld", "ld_p1", "ld_p2"):
                im = img(rdir / "cobble" / s / (v + ".png"), crop=box)
                scale = 560 / im.height
                im = im.resize((round(im.width * scale), 560), Image.LANCZOS if tag == "k2_5x" else Image.NEAREST)
                cells.append(label(im, "%s · %s" % (SET_LABEL[s], v), 12))
            rows.append(hstack(cells))
        note = ("blender · K2 %s · свет ≈ Cobble, экспозиция откалибрована по якорю W4-A (K1 доска p50 131) · кроп по фигуре, "
                "увеличение ×%s · это НЕ UE" % ("5×" if tag == "k2_5x" else "1,6×", "~1,5" if tag == "k2_5x" else "~4 (nearest)"))
        out[tag] = save_jpg(label(vstack(rows), note, 15), pv / ("ld_%s_cobble.jpg" % tag))
    crop = fig_box("k2_5x_az0")
    cells = []
    for s in ("h22", "ld"):
        for v in ("close_torso_az0", "close_legs_az0", "close_head_az0"):
            cells.append(label(img(rdir / "studio_env" / s / (v + ".png"), 600), "blender · studio_env · %s · %s" % (SET_LABEL[s], v), 12))
    row1 = hstack(cells[:3])
    row2 = hstack(cells[3:])
    cells = [label(img(rdir / "cobble" / s / "close_torso_az0.png", 600), "blender · Cobble · %s" % SET_LABEL[s], 12)
             for s in ("ld", "ld_p1", "ld_p2")]
    cells.append(label(img(rdir / "cobble" / "ld_p2" / "close_cloak_back_az180.png", 600), "blender · Cobble · P2 · плащ сзади", 12))
    out["closeups"] = save_jpg(vstack([row1, row2, hstack(cells)]), pv / "ld_closeups.jpg")
    cells = [label(img(rdir / "id" / lab_ / "ortho_front.png", 700), "ID: %s" % lab_, 14) for lab_ in ("zones", "accent")]
    cells.append(label(img(rdir / "id" / "accent" / "k2_5x_az0.png", 700, crop=crop), "ID accent · K2 5× az 0", 14))
    cells.append(label(img(rdir / "id" / "tabard" / "k2_5x_az0.png", 700, crop=crop), "ID табард (замер красного) · K2 5× az 0", 14))
    out["id"] = save_jpg(hstack(cells), pv / "ld_id_masks.jpg")
    return out


def main():
    prof, paths, src, src_run, _cache = S.lookdev_paths(sys.argv[1], sys.argv[2])
    ld = prof["lookdev"]
    rdir = paths["work"] / "lookdev" / "render_final"
    checks = {}

    def check(name, passed, measured, expected, note=""):
        checks[name] = {"passed": bool(passed), "measured": measured, "expected": expected, "note": note}

    sets = ["h22", "h2", "ld"]
    rel, concept, per = LT.measure(prof, src, rdir / "studio_env", rdir / "id" / "zones", sets)
    tol = float(src["review_h22"]["steel_check"]["relative"]["tolerance"])
    q = rel["pooled"]["ld"]["ratio_geomean"]
    check("steel_relative_within_h22_tolerance", abs(q - 1) <= tol, rel["pooled"], "|ld - 1| <= %s" % tol,
          "the H2.2 gate (steelcheck.relative_check) on the final look-dev frames")
    cob = LT.cobble_steel(rdir / "cobble", rdir / "id" / "zones", ["k2_5x_az0", "k2_5x_az-40"], ["h22", "h2", "ld", "ld_p1", "ld_p2"],
                          LM.ZONE_RGB["steel_plate"])
    lo, hi = ld["tone"]["steel"]["cobble_range"]
    mean_ld = float(np.mean([cob[v]["ld"]["steel_over_board"] for v in cob]))
    check("steel_cobble_mean_in_range", lo - 0.02 <= mean_ld <= hi, {"mean": P.r(mean_ld, 4), "per_view": {v: cob[v]["ld"]["steel_over_board"] for v in cob}},
          [lo, hi], "mean steel / board over K2 5x az 0 / -40 (the fit rule; 0.02 = measurement noise of the refit)")
    white = max(cob[v]["ld"]["share_display_max_channel_ge_0.85"] for v in cob)
    check("steel_not_white_on_board", white <= 0.01, white, "<= 1 % of the steel pixels with a display channel >= 0.85")
    tone = P.load_json(paths["reports"] / "ld-tone-report.json")
    lut = P.load_json(paths["reports"] / "ld-lut.json")
    f0 = np.array(tone["steel"]["f0"])
    check("steel_f0_in_oxide_band", 0.10 <= float(f0 @ LUM) <= 0.26, P.r(float(f0 @ LUM), 4), [0.10, 0.26],
          "preset steel_blued luminanceRange (validator oxide film band 0.05-0.35)")
    gf0 = np.array(tone["gold"]["f0"])
    check("gold_f0_metal_rule", float(gf0 @ LUM) >= 0.45 and gf0.max() <= 1.0, {"Y": P.r(float(gf0 @ LUM), 4), "max": P.r(float(gf0.max()), 4)},
          "Y >= 0.45, channels <= 1 (LDD-7)")
    cols = lut["columns_v2"]
    used = {"1": "steel_blued", "2": "steel_polished", "4": "gold_antique", "8": "leather_worn", "9": "wool_coarse",
            "11": "silk", "13": "skin", "14": "stone_base"}
    dye = {cid: cols[i]["teamDyeAllowed"] for i, cid in used.items()}
    check("lut_dye_only_wool_and_leather", {k for k, v in dye.items() if v > 0.5} == {"wool_coarse", "leather_worn"}, dye,
          "teamDyeAllowed = 1 only on the classes the TeamAccent covers (wool_coarse, leather_worn)")
    check("lut_metallic_binary", all(cols[i]["metallic"] in (0.0, 1.0) for i in cols), {i: cols[i]["metallic"] for i in used}, "0 or 1")
    check("lut_exr_readback", lut["file"]["readback_equal"], lut["file"]["readback_equal"], True)
    acc = accent_metrics(rdir, ["k2_5x_az0", "k2_5x_az-40", "k2_5x_az180", "k2_1p6_az0", "k2_1p6_az-40"])
    min_de = min(acc[v][s]["delta_e_accent_vs_cloth"] for v in acc for s in ("ld_p1", "ld_p2"))
    min_pp = min(acc[v]["delta_e_p1_vs_p2"] for v in acc)
    check("team_accent_reads_at_k2", min_de >= 15 and min_pp >= 20,
          {"min_delta_e_accent_vs_cloth": min_de, "min_delta_e_p1_vs_p2": min_pp},
          "CIELAB dE >= 15 against the red cloth next to it, >= 20 between P1 and P2 (K2 5x and 1.6x, Cobble)")
    tab = tabard_red_metrics(rdir, rdir / "cobble")
    rmin = float(ld["team_accent"]["red_parts"]["render_red_share_min_ratio"])
    min_ratio = min(min(e["ratio_ld_p1"], e["ratio_ld_p2"]) for e in tab.values()) if tab else 0.0
    check("team_accent_tabard_red_in_render", bool(tab) and min_ratio >= rmin,
          {"min_ratio": P.r(min_ratio, 4), "per_view": tab},
          ">= %s x the no-dye red share of the tabard pixels with P1 and with P2 (Cobble, %s)" % (rmin, ", ".join(TABARD_VIEWS)),
          "rev. 2: the front panel stays red; red = display hue within +-%g deg of 0, saturation >= %g"
          % (RED_HUE_DEG, RED_SAT_MIN))
    zm = zone_metrics(concept, per, ["cloth", "embroidery", "gold", "belt", "face_skin", "hair", "base"])
    maps = P.load_json(paths["reports"] / "ld-maps-report.json")
    exp = P.load_json(paths["reports"] / "ld-export-report.json")
    st = P.load_json(paths["reports"] / "ld-state-report.json")
    for name, rep in (("ld_state", st), ("ld_export", exp), ("ld_maps", maps)):
        check(name + "_passed", rep["passed"], sorted(k for k, c in rep["checks"].items() if not c["passed"]), [])
    ov = concept_overlays(prof, src, paths)
    sh = sheets(prof, src, paths, rdir)
    metrics = {"stage": "ld_report", "steel_relative": rel["pooled"], "steel_relative_zones_front": rel["zones_front"],
               "steel_cobble": cob, "team_accent_screen": acc, "team_accent_3d": maps["team_accent"],
               "team_accent_tabard_red_render": tab,
               "zones_vs_concept": zm, "note": "all frames Blender (EEVEE / Workbench), emulated v2 material; not UE"}
    P.write_json(paths["reports"] / "ld-metrics.json", metrics)
    # textures report
    tex = {}
    for f in sorted(paths["textures"].glob("*")):
        e = {"file": P.rel(f), "sha256": P.sha256(f), "bytes": f.stat().st_size,
             "committed": not f.name.endswith("_4K.png")}
        if f.suffix == ".png":
            with Image.open(f) as im:
                e["px"] = list(im.size)
                e["mode"] = im.mode
        tex[f.name] = e
    P.write_json(paths["reports"] / "textures-report.json",
                 {"stage": "ld_report", "prefix": ld["prefix"], "textures": tex, "conventions": maps["conventions"],
                  "lut": {"file": lut["file"], "format": lut["format"]},
                  "note": "the 4K masters are local (reproducible from the chain, sha256 here); the 2K runtime set, MatID, "
                          "TeamAccent, EdgeMask and the LUT are committed"})
    report = {"stage": "ld_report", "profile": P.rel(sys.argv[1]), "profile_id": prof["profile_id"], "status": "измерено",
              "sheets": sh, "concept_zone_overlays": ov, "checks": checks,
              "passed": all(c["passed"] for c in checks.values())}
    P.write_json(paths["reports"] / "ld-report.json", report)
    files = []
    for sub in ("export", "textures", "reports", "preview", "ue-inputs"):
        d = paths["run"] / sub
        if d.exists():
            for f in sorted(d.rglob("*")):
                if f.is_file() and not f.name.endswith("_4K.png") and f.name != "manifest-ld.json":
                    files.append({"file": P.rel(f), "sha256": P.sha256(f), "bytes": f.stat().st_size})
    P.write_json(paths["reports"] / "manifest-ld.json", {"profile": P.rel(sys.argv[1]), "profile_sha256": P.sha256(sys.argv[1]),
                                                        "files": files})
    print(P.STAGE_MARKER, "ld_report passed=%s" % report["passed"], sorted(k for k, c in checks.items() if not c["passed"]))


if __name__ == "__main__":
    main()
