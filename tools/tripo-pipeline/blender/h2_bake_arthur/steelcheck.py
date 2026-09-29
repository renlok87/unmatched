"""Stage steelcheck (H2.2, system python: numpy, scipy, Pillow): luminance of the steel plate in the studio frames
against the concept, and of the steel in the Cobble-light frames (does the dark steel turn white from the sky?).

    python steelcheck.py <profile.json> <run_dir> [--renders DIR] [--classes DIR] [--cobble DIR] [--sets h2,h21,h22]
        [--check h22] [--no-write]

Metric: mean relative luminance Y (Rec.709) of the sRGB-decoded pixels (linear display values), per view and pooled
over the three views (all pixels of the three masks together); the check passes when the pooled mean of the checked
set is within +-tolerance of the pooled concept mean (profile review_h22.steel_check.tolerance).

Masks (profile review_h22.steel_check):
  concept  the steel zones drawn in concept pixels (polygons / rectangles inside the armour silhouette: plate, arms,
           gauntlets, legs, sabatons; no blade, head, cloak or base) AND the colour gate of the pixel (sRGB HSV:
           saturation <= s_max drops the gold trims, the red cloth and the brown leather; value >= v_min drops the
           black gaps). The concept and the model do not line up pixel for pixel (other proportions), so the concept
           mask is its own and is shown in preview/h22/steel_masks.jpg
  render   the plate-steel class of the material pass (class raster rendered flat on the mesh by stage compare with
           the same camera: colour materials.STEEL_PLATE_RGB +- class_tolerance, eroded by erode_px to drop the
           anti-aliased edges; the blade has its own class colour and stays out) AND the same colour gate
Writes textures-report.json -> steel_luminance_check (unless --no-write) and preview/h22/steel_masks.jpg.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parent))
import materials as M  # noqa: E402
import pure as P  # noqa: E402

LUM = np.array([0.2126, 0.7152, 0.0722])


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0


def lin(a):
    return np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)


def gate(img, g):
    mx = img.max(axis=2)
    s = np.where(mx > 1e-6, (mx - img.min(axis=2)) / np.maximum(mx, 1e-6), 0.0)
    return (s <= float(g["s_max"])) & (mx >= float(g["v_min"]))


def zone_mask(shape, zones):
    im = Image.new("L", (shape[1], shape[0]), 0)
    d = ImageDraw.Draw(im)
    for z in zones:
        if "rect" in z:
            x0, y0, x1, y1 = z["rect"]
            d.rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
        else:
            d.polygon([tuple(p) for p in z["poly"]], fill=255)
    return np.array(im) > 127


def class_mask(cls_img, tol, erode):
    rgb = np.array(M.STEEL_PLATE_RGB, dtype=np.float64) / 255.0
    m = np.abs(cls_img - rgb).sum(axis=2) * 255.0 <= tol
    return ndimage.binary_erosion(m, iterations=int(erode)) if erode else m


def stats(img, mask, white=None):
    li = lin(img[mask])
    y = li @ LUM
    if not len(y):
        return {"pixels": 0}
    mean_rgb = li.mean(axis=0)
    e = {"pixels": int(mask.sum()), "Y_mean": P.r(y.mean(), 5),
         "Y_p10_p50_p90": [P.r(v, 5) for v in np.percentile(y, (10, 50, 90))],
         "chroma_mean_rgb_over_Y": [P.r(v, 4) for v in mean_rgb / max(float(mean_rgb @ LUM), 1e-9)]}
    if white is not None:
        e["share_display_max_channel_ge_%.2f" % white] = P.r((img[mask].max(axis=1) >= white).mean(), 5)
    return e


def pooled(parts):
    n = sum(p["_n"] for p in parts)
    return float(sum(p["_sum"] for p in parts) / max(n, 1)), n


def hsv_img(img):
    """sRGB display HSV of an image (H in degrees)."""
    mx = img.max(axis=2)
    mn = img.min(axis=2)
    d = mx - mn
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    h = np.zeros_like(mx)
    m = d > 1e-6
    rm = m & (mx == r)
    gm = m & (mx == g) & ~rm
    bm = m & ~rm & ~gm
    h[rm] = ((g[rm] - b[rm]) / d[rm]) % 6
    h[gm] = (b[gm] - r[gm]) / d[gm] + 2
    h[bm] = (r[bm] - g[bm]) / d[bm] + 4
    return h * 60.0, np.where(mx > 1e-6, d / np.maximum(mx, 1e-6), 0.0), mx


def colour_gate(img, g):
    """hue window [lo, hi] (degrees, wraps when lo > hi), saturation >= s_min, value >= v_min (sRGB display HSV)."""
    h, s, v = hsv_img(img)
    lo, hi = g["hue_deg"]
    hue = (h >= lo) & (h <= hi) if lo <= hi else (h >= lo) | (h <= hi)
    return hue & (s >= float(g["s_min"])) & (v >= float(g["v_min"]))


def ref_mask_concept(cimg, view, ref):
    if "concept_rects" in ref:
        return zone_mask(cimg.shape, [{"rect": ref["concept_rects"][view]}])
    return colour_gate(cimg, ref["gate"])


def ref_mask_render(cls, img, ref):
    m = np.abs(cls * 255.0 - np.array(ref["render_class_rgb"])).sum(axis=2) <= 12
    m = ndimage.binary_erosion(m, iterations=int(ref.get("erode_px", 0))) if ref.get("erode_px") else m
    return m & colour_gate(img, ref["gate"]) if "gate" in ref else m


def ylin(img, mask):
    return lin(img[mask]) @ LUM


def relative_check(profile, sc, renders, classes, sets, g):
    """Gate of H2.2 (rev. 2): the steel luminance RELATIVE to reference materials of the same frame, concept vs render.
    For every reference r (stone of the base, red cloth, gold; unchanged by the steel pass) and set:
        ratio_r = (Y_steel / Y_r)_render / (Y_steel / Y_r)_concept
    i.e. the steel ratio after bringing the render to the concept's exposure measured on r. The references disagree
    (their painted Tripo colour and their response to the light are not the concept's), so the gate is the geometric
    mean over the references; each reference is reported. Pooled = sums of Y over the three views (front, side, back).
    Zones (front view): the same ratio per armour zone (chest, faulds, greaves, gauntlets, ...) with the front
    references, concept zone polygons vs render zone rectangles (render pixels) x the plate-steel class x colour gate."""
    rl = sc["relative"]
    refs = rl["references"]
    acc = {s: {"steel_c": [0.0, 0], "steel_r": [0.0, 0]} | {r: {"c": [0.0, 0], "r": [0.0, 0]} for r in refs}
           for s in sets}
    views = {}
    front = None
    for view, rview in sc["views"].items():
        cimg = load(P.repo_path(profile["sources"]["concepts"][view]))
        cm = zone_mask(cimg.shape, sc["concept_zones"][view]) & gate(cimg, g)
        cls = load(classes / (rview + ".png"))
        base = class_mask(cls, float(sc["class_tolerance"]), int(sc["erode_px"]))
        ys_c = ylin(cimg, cm)
        cref = {r: ylin(cimg, ref_mask_concept(cimg, view, ref)) for r, ref in refs.items()}
        ve = {"concept": {"steel_Y_mean": P.r(ys_c.mean(), 5)} | {r + "_Y_mean": P.r(y.mean(), 5) for r, y in cref.items()}
              | {r + "_pixels": int(len(y)) for r, y in cref.items()}}
        for s in sets:
            f = renders / s / (rview + ".png")
            if not f.exists():
                continue
            img = load(f)
            ys_r = ylin(img, base & gate(img, g))
            e = {"steel_Y_mean": P.r(ys_r.mean(), 5), "ratio": {}}
            a = acc[s]
            a["steel_c"][0] += ys_c.sum(); a["steel_c"][1] += len(ys_c)
            a["steel_r"][0] += ys_r.sum(); a["steel_r"][1] += len(ys_r)
            logs = []
            for r, ref in refs.items():
                yr = ylin(img, ref_mask_render(cls, img, ref))
                e[r + "_Y_mean"] = P.r(yr.mean(), 5)
                e[r + "_pixels"] = int(len(yr))
                a[r]["c"][0] += cref[r].sum(); a[r]["c"][1] += len(cref[r])
                a[r]["r"][0] += yr.sum(); a[r]["r"][1] += len(yr)
                q = (ys_r.mean() / yr.mean()) / (ys_c.mean() / cref[r].mean())
                e["ratio"][r] = P.r(q, 4)
                logs.append(np.log(q))
            e["ratio_geomean"] = P.r(float(np.exp(np.mean(logs))), 4)
            ve[s] = e
            if view == "front":
                front = (cimg, cls, cref)
        views[view] = ve
    pooled = {}
    for s in sets:
        a = acc[s]
        if not a["steel_r"][1]:
            continue
        m = lambda x: x[0] / max(x[1], 1)  # noqa: E731
        e = {"ratio": {}}
        logs = []
        for r in refs:
            q = (m(a["steel_r"]) / m(a[r]["r"])) / (m(a["steel_c"]) / m(a[r]["c"]))
            e["ratio"][r] = P.r(q, 4)
            logs.append(np.log(q))
        e["ratio_geomean"] = P.r(float(np.exp(np.mean(logs))), 4)
        e["ratio_min_max"] = [P.r(min(e["ratio"].values()), 4), P.r(max(e["ratio"].values()), 4)]
        pooled[s] = e
    zones = {}
    if front and rl.get("zones_front"):
        cimg, cls, cref = front
        base = class_mask(cls, float(sc["class_tolerance"]), int(sc["erode_px"]))
        czones = {z["name"]: z for z in sc["concept_zones"]["front"]}
        for zname, zc in rl["zones_front"].items():
            cmask = zone_mask(cimg.shape, [czones[n] for n in zc["concept"]]) & gate(cimg, g)
            ys_c = ylin(cimg, cmask)
            ze = {"concept_zones": zc["concept"], "render_rects": zc["render_rects"], "concept_pixels": int(len(ys_c)),
                  "concept_steel_Y_mean": P.r(ys_c.mean(), 5)}
            for s in sets:
                f = renders / s / "ortho_front.png"
                if not f.exists():
                    continue
                img = load(f)
                rmask = zone_mask(img.shape, [{"rect": q} for q in zc["render_rects"]]) & base & gate(img, g)
                ys_r = ylin(img, rmask)
                logs = []
                for r, ref in refs.items():
                    yr = ylin(img, ref_mask_render(cls, img, ref))
                    logs.append(np.log((ys_r.mean() / yr.mean()) / (ys_c.mean() / cref[r].mean())))
                ze[s] = {"pixels": int(len(ys_r)), "steel_Y_mean": P.r(ys_r.mean(), 5),
                         "ratio_geomean": P.r(float(np.exp(np.mean(logs))), 4)}
            zones[zname] = ze
    return {"what": rl["note"], "references": {r: {k: v for k, v in ref.items()} for r, ref in refs.items()},
            "tolerance": rl["tolerance"], "views": views, "pooled": pooled, "zones_front": zones}


CLASS_RGB = {"steel_plate": M.STEEL_PLATE_RGB, "steel_blade": M.STEEL_OVERRIDE_RGB, "gold": (245, 205, 30),
             "red_cloth": (190, 25, 30), "leather": (110, 60, 25), "head_non_metal": (235, 185, 150),
             "stone": (55, 55, 55), "other_non_metal": (120, 120, 120)}


def change_vs_baseline(profile, paths, base_dir):
    """Texels of the runtime 2K BC / ORM that differ from the H2.1 baseline, per material class of the 2K class raster
    (work/materials-classes-2k.png: a texel belongs to a class when its colour is within 6 of the class colour,
    otherwise it is 'mixed' - a soft boundary between classes; the raster is filled into the gutters like BC, so the
    counts are atlas texels). Only the plate steel should change."""
    prefix = profile["textures"]["prefix"]
    cls = np.asarray(Image.open(paths["work"] / "materials-classes-2k.png").convert("RGB")).astype(np.int32)
    lab = np.full(cls.shape[:2], -1, dtype=np.int32)
    names = list(CLASS_RGB)
    for i, n in enumerate(names):
        lab[np.abs(cls - np.array(CLASS_RGB[n])).sum(axis=2) <= 6] = i
    pid_cov = cls.sum(axis=2) > 0
    bl = profile["review_h22"]["baseline_h21"]
    rt = P.rel(paths["textures"] / "runtime_2k")
    out = {"baseline": {"commit": bl["commit"],
                        "files": {k: "%s:%s/%s_%s.png" % (bl["commit"], rt, prefix, k) for k in ("BC", "ORM")},
                        "sha256": {k: bl["runtime_2k_sha256"][k] for k in ("BC", "ORM")},
                        "local_copy": P.rel(base_dir) + " (not committed: run.py baseline_dir extracts the files with "
                                      "git show <commit>:<path> and checks the sha256)"},
           "class_raster": "work/materials-classes-2k.png (not committed; stage textures writes it)", "maps": {}}
    for key in ("BC", "ORM"):
        if P.sha256(base_dir / ("%s_%s.png" % (prefix, key))) != bl["runtime_2k_sha256"][key]:
            raise SystemExit("baseline %s: local copy differs from %s" % (key, bl["commit"]))
        a = np.asarray(Image.open(base_dir / ("%s_%s.png" % (prefix, key))).convert("RGB")).astype(np.int32)
        b = np.asarray(Image.open(paths["textures"] / "runtime_2k" / ("%s_%s.png" % (prefix, key))).convert("RGB")).astype(np.int32)
        d = np.abs(a - b).max(axis=2)
        e = {}
        for i, n in list(enumerate(names)) + [(-1, "mixed")]:
            m = (lab == i) & pid_cov
            if m.any():
                e[n] = {"texels": int(m.sum()), "changed": int((d[m] > 0).sum()),
                        "changed_gt_8_levels": int((d[m] > 8).sum()), "max_abs_diff": int(d[m].max())}
        out["maps"][key] = e
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("run_dir")
    ap.add_argument("--renders", default="")
    ap.add_argument("--classes", default="")
    ap.add_argument("--cobble", default="")
    ap.add_argument("--sets", default="h2,h21,h22")
    ap.add_argument("--check", default="h22")
    ap.add_argument("--no-write", action="store_true")
    a = ap.parse_args()
    profile = P.load_json(a.profile)
    paths = P.run_paths(a.run_dir)
    sc = profile["review_h22"]["steel_check"]
    raw = paths["work"] / "h22_png"
    renders = Path(a.renders) if a.renders else raw / "studio_env"
    classes = Path(a.classes) if a.classes else raw / "classes" / "classes"
    cobble = Path(a.cobble) if a.cobble else raw / "cobble"
    sets = [s for s in a.sets.split(",") if s]
    g = sc["gate"]
    rep = {"schema": "unmatched.h2-bake.steel-check/1", "metric": sc["metric"], "light": sc["light"],
           "gate": g, "tolerance": sc["tolerance"], "checked_set": a.check, "views": {}, "pooled": {}}
    acc = {"concept": []} | {s: [] for s in sets}
    sheet = []
    for view, rview in sc["views"].items():
        cimg = load(P.repo_path(profile["sources"]["concepts"][view]))
        cm = zone_mask(cimg.shape, sc["concept_zones"][view]) & gate(cimg, g)
        cls = load(classes / (rview + ".png"))
        base = class_mask(cls, float(sc["class_tolerance"]), int(sc["erode_px"]))
        ve = {"render_view": rview, "concept": stats(cimg, cm)}
        yc = lin(cimg[cm]) @ LUM
        acc["concept"].append({"_n": len(yc), "_sum": yc.sum()})
        for s in sets:
            f = renders / s / (rview + ".png")
            if not f.exists():
                continue
            img = load(f)
            rm = base & gate(img, g)
            ve[s] = stats(img, rm) | {"class_mask_pixels": int(base.sum()),
                                      "raw_png_sha256": P.sha256(f)}
            yr = lin(img[rm]) @ LUM
            acc[s].append({"_n": len(yr), "_sum": yr.sum()})
            ve[s]["ratio_to_concept"] = P.r(ve[s]["Y_mean"] / ve["concept"]["Y_mean"], 4)
        rep["views"][view] = ve
        # inspection: concept with its mask | checked-set render with its mask
        tint = np.array([0.0, 0.55, 1.0])
        c_vis = np.where(cm[..., None], cimg * 0.35 + tint * 0.65, cimg * 0.45)
        panels = [c_vis]
        f = renders / a.check / (rview + ".png")
        if f.exists():
            img = load(f)
            rm = base & gate(img, g)
            panels.append(np.where(rm[..., None], img * 0.35 + tint * 0.65, img * 0.45))
        sheet.append(panels)
    yc, nc = pooled(acc["concept"])
    rep["pooled"]["concept"] = {"Y_mean": P.r(yc, 5), "pixels": nc}
    for s in sets:
        if acc[s]:
            y, n = pooled(acc[s])
            rep["pooled"][s] = {"Y_mean": P.r(y, 5), "pixels": n, "ratio_to_concept": P.r(y / yc, 4)}
    er = sc.get("exposure_reference")
    if er:
        # informative: the unchanged stone of the base, concept vs render (how much brighter studio_env is)
        cimg = load(P.repo_path(profile["sources"]["concepts"][er["view"]]))
        x0, y0, x1, y1 = er["concept_rect"]
        yc_ref = float((lin(cimg[y0:y1, x0:x1].reshape(-1, 3)) @ LUM).mean())
        rview = sc["views"][er["view"]]
        cls = load(classes / (rview + ".png"))
        m = ndimage.binary_erosion(np.abs(cls * 255.0 - np.array(er["render_class_rgb"])).sum(axis=2) <= 12,
                                   iterations=int(er["render_erode_px"]))
        ex = {"note": er["note"], "concept_stone_Y_mean": P.r(yc_ref, 5), "render_stone_pixels": int(m.sum())}
        for s in sets:
            f = renders / s / (rview + ".png")
            if f.exists() and s in rep["pooled"]:
                yr_ref = float((lin(load(f)[m]) @ LUM).mean())
                k = yc_ref / yr_ref
                ex[s] = {"render_stone_Y_mean": P.r(yr_ref, 5), "concept_over_render": P.r(k, 4),
                         "steel_ratio_at_concept_exposure": P.r(rep["pooled"][s]["ratio_to_concept"] * k, 4)}
        rep["exposure_reference"] = ex
    chk = rep["pooled"].get(a.check)
    # H2.2 rev. 1 gated on this absolute ratio; studio_env lights the unchanged stone x2.1 brighter than the concept's
    # light, so an absolute match made the steel ~2x too dark next to the other materials (rejected). Informative now.
    rep["absolute_informative"] = {
        "ratio_to_concept": chk["ratio_to_concept"] if chk else None,
        "within_tolerance": bool(chk and abs(chk["ratio_to_concept"] - 1.0) <= float(sc["tolerance"])),
        "note": "absolute mean Y of the steel masks, render / concept; NOT the gate since H2.2 rev. 2: studio_env is "
                "brighter than the concept's light (see exposure_reference), the gate is 'relative'"}
    if sc.get("relative"):
        rep["relative"] = relative_check(profile, sc, renders, classes, sets, g)
    # Cobble-light frames: steel of the plate (class mask of the same camera) per set
    cb = {}
    for v in sc.get("cobble_views", []):
        cf = classes / (v + ".png")
        if not cf.exists():
            continue
        base = class_mask(load(cf), float(sc["class_tolerance"]), int(sc["erode_px"]))
        cb[v] = {"class_mask_pixels": int(base.sum())}
        for s in sets:
            f = cobble / s / (v + ".png")
            if f.exists():
                im = load(f)
                board = float(np.median(lin(im[:im.shape[0] // 10].reshape(-1, 3)) @ LUM))
                e = stats(im, base, white=float(sc["white_display_threshold"]))
                cb[v][s] = e | {"board_Y_median_top_rows": P.r(board, 5),
                                "steel_Y_mean_over_board": P.r(e["Y_mean"] / board, 4),
                                "steel_Y_p90_over_board": P.r(e["Y_p10_p50_p90"][2] / board, 4),
                                "raw_png_sha256": P.sha256(f)}
    if cb:
        rep["cobble"] = cb
        lo, hi = sc["cobble_steel_over_board_range"]
        vals = [cb[v][a.check]["steel_Y_mean_over_board"] for v in cb if a.check in cb[v]]
        rep["cobble_check"] = {"range": [lo, hi], "set": a.check, "steel_Y_mean_over_board": vals,
                               "passed": bool(vals) and all(lo <= x <= hi for x in vals),
                               "note": "the plate steel on the Cobble-light K2 frames neither white (> hi, H2.1 "
                                       "1.27-1.51) nor black (< lo, H2.2 rev. 1 0.17-0.20); H2 0.48-0.53"}
        rep["cobble_note"] = ("plate-steel pixels of the Cobble-light K2 frames (class mask of the same camera, no colour "
                              "gate); share_display_max_channel_ge = share of the steel pixels whose brightest display "
                              "channel reaches the threshold; steel_Y_*_over_board = steel luminance over the median "
                              "luminance of the board (top 10 % rows of the frame, only board): > 1 = the steel is "
                              "lighter than the grey stone board, i.e. reads light / white on the board")
    rel_ok = None
    if "relative" in rep and a.check in rep["relative"]["pooled"]:
        q = rep["relative"]["pooled"][a.check]["ratio_geomean"]
        rel_ok = abs(q - 1.0) <= float(sc["relative"]["tolerance"])
        rep["relative"]["passed"] = rel_ok
    rep["passed"] = bool(rel_ok) and rep.get("cobble_check", {}).get("passed", True)
    rep["pass_rule"] = ("relative.pooled[%s].ratio_geomean within +-%s of 1 AND cobble_check (steel / board in %s)"
                   % (a.check, sc["relative"]["tolerance"] if sc.get("relative") else "-",
                      sc.get("cobble_steel_over_board_range")))
    bdir = paths["work"] / "h21-baseline-runtime-2k"
    if bdir.exists() and (paths["work"] / "materials-classes-2k.png").exists():
        rep["change_vs_h21"] = change_vs_baseline(profile, paths, bdir)
    if a.no_write:
        import json
        print(json.dumps(rep, indent=1, ensure_ascii=False))
        return
    trep = paths["reports"] / "textures-report.json"
    tr = P.load_json(trep)
    tr["steel_luminance_check"] = rep
    P.write_json(trep, tr)
    out = paths["preview"] / "h22"
    out.mkdir(parents=True, exist_ok=True)
    from sheets import hstack, label, save_jpg, vstack  # noqa: E402
    rows = []
    for (view, rview), panels in zip(sc["views"].items(), sheet):
        cells = [label(Image.fromarray((panels[0] * 255 + 0.5).astype(np.uint8)),
                       "концепт · %s · маска стали (зоны + цветовой гейт)" % view, 16)]
        if len(panels) > 1:
            cells.append(label(Image.fromarray((panels[1] * 255 + 0.5).astype(np.uint8)),
                               "blender · EEVEE · %s · %s · маска: класс «сталь лат» + гейт" % ({"h22": "H2.2 ред. 2", "h21": "H2.1"}.get(a.check, a.check), rview), 16))
        rows.append(hstack([c.resize((c.width * 2 // 3, c.height * 2 // 3), Image.LANCZOS) for c in cells]))
    save_jpg(label(vstack(rows, gap=8), "маски проверки яркости стали (голубое — учитывается)", 18),
             out / "steel_masks.jpg")
    print(P.STAGE_MARKER, "steelcheck", rep.get("relative", {}).get("pooled"), rep.get("cobble_check"), "passed", rep["passed"])


if __name__ == "__main__":
    main()
