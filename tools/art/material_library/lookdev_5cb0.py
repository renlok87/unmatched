"""5c-B0 (2026-09-30): the material leftovers of look-dev C fixed on the Blender stage - measurements and comparison
sheets "concept | before | after" (no editor, no Blender).

    python tools/art/material_library/lookdev_5cb0.py feedback --hero arthur|merlin|harpy
        UE zone medians before (the look-dev C frames) and AFTER (prediction: ue_bc_feedback.predict = the same frames
        with the linear pixels of the edited zone x the fitted ratio, measured by ue_hero_lookdev.cmd_measure), both
        exposures, every zone -> <look-dev run>/reports/ld-5cb0-ue-feedback.json + preview/ld_5cb0_<zone>_sheet.png

    python tools/art/material_library/lookdev_5cb0.py accent --before <dir with the rev. 2 2K PNGs + renders>
        Arthur TeamAccent rev. 2 vs rev. 3 through the mip chain (lookdev_accent_mips) + the sheet
        -> <Arthur look-dev run>/reports/ld-5cb0-teamaccent.json + preview/ld_5cb0_teamaccent_sheet.png
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_bc_feedback as F  # noqa: E402
import ue_hero_lookdev as U  # noqa: E402

REPO = U.REPO
PC = REPO / "art" / "pipeline-candidates"

HEROES = {
    "arthur": {"asset": "ASSET-KING-ARTHUR-001", "run": "20260929-h2-lookdev", "ue": "20260929-h2ld-ue",
               "frames": "review/i2", "tag": "i2", "zone": "belt", "select": "class", "sat_max": None,
               "fit": {"weights": "reading=1,neutral=0.5", "keep_luma": False, "scale": 1.0},
               "concept": "art/imagegen/hero-quality-v1/king-arthur/king-arthur-%s.png",
               "label": "пояс (leather_worn)"},
    "merlin": {"asset": "ASSET-MERLIN-001", "run": "20260929-h2-lookdev", "ue": "20260930-h2ld-ldc-ue",
               "frames": "review/c3", "tag": "c3", "zone": "leather_worn", "select": "class", "sat_max": None,
               "fit": {"weights": "reading=1,neutral=0.5", "keep_luma": False, "scale": 1.0},
               "concept": "art/imagegen/hero-quality-v1/merlin/merlin-%s.png",
               "label": "потёртая кожа: пояс, сапоги, обмотка бороды (leather_worn)"},
    "harpy": {"asset": "ASSET-HARPY-001", "run": "20260929-h3-lookdev", "ue": "20260929-h3ld-ue",
              "frames": "review/i3", "tag": "i3", "zone": "dark", "select": "gate_lowsat", "sat_max": 0.38,
              "fit": {"weights": "reading=1,neutral=0.5", "keep_luma": True, "scale": 0.9},
              "concept": "art/imagegen/hero-quality-v1/harpy/harpy-%s.png",
              "label": "тёмные маховые перья (feathers, ворота v <= 0.45)"},
}


def now():
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def font(size):
    return U.font(size)


def label(img: Image.Image, text: str, size=22) -> Image.Image:
    out = Image.new("RGB", (img.width, img.height + size + 12), (24, 24, 24))
    out.paste(img, (0, size + 12))
    ImageDraw.Draw(out).text((6, 4), text, fill=(235, 235, 235), font=font(size))
    return out


def hstack(imgs, pad=6, bg=(24, 24, 24)):
    h = max(i.height for i in imgs)
    out = Image.new("RGB", (sum(i.width for i in imgs) + pad * (len(imgs) - 1), h), bg)
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width + pad
    return out


def vstack(imgs, pad=6, bg=(24, 24, 24)):
    w = max(i.width for i in imgs)
    out = Image.new("RGB", (w, sum(i.height for i in imgs) + pad * (len(imgs) - 1)), bg)
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + pad
    return out


def fit_h(img: Image.Image, h: int) -> Image.Image:
    return img.resize((max(1, round(img.width * h / img.height)), h), Image.LANCZOS)


def bbox(mask, margin=0.08, pct=0.5):
    ys, xs = np.nonzero(mask)
    # robust extent (stray decoded pixels on the board / plate noise do not stretch the crop)
    y0, y1 = (int(v) for v in np.percentile(ys, [pct, 100 - pct]))
    x0, x1 = (int(v) for v in np.percentile(xs, [pct, 100 - pct]))
    my, mx = int((y1 - y0) * margin) + 8, int((x1 - x0) * margin) + 8
    return max(0, x0 - mx), max(0, y0 - my), min(mask.shape[1], x1 + mx), min(mask.shape[0], y1 + my)


# ------------------------------------------------------------------ BC feedback (b)
def cmd_feedback(a):
    h = HEROES[a.hero]
    ue = PC / h["asset"] / h["ue"]
    run = PC / h["asset"] / h["run"]
    cfg = json.loads((ue / "review-config.json").read_text(encoding="utf-8"))
    frames = ue / h["frames"]
    tag = h["tag"]
    fit = json.loads(Path(a.fit).read_text(encoding="utf-8"))
    r = np.asarray(fit["ratio_effective_albedo_linear"]) * float(h["fit"]["scale"])
    masks, cls_of = F.load_masks(cfg, frames, tag)
    sel = F.select_pixels(cfg, frames, tag, masks, cls_of, h["zone"], h["select"], h["sat_max"] or 0.38)
    before = json.loads((frames / ("measure-%s.json" % tag)).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as td:
        pred = F.predict(cfg, frames, tag, sel, r, Path(td))
        # sheet frames (modified) read before the scratch dir goes
        mod = {}
        for view in U.ORTHO:
            for var in ("neutral", "reading"):
                p = Path(td) / "frames" / ("%s-%s-%s-%s.png" % (cfg["hero"].lower(), tag, view, var))
                if p.is_file():
                    mod[(view, var)] = Image.open(p).convert("RGB")
                    mod[(view, var)].load()
    gain_doc = json.loads(Path(a.gain).read_text(encoding="utf-8")) if a.gain else None
    table = {}
    for var in ("reading", "neutral"):
        eb, ea = before["exposure"][var], pred["exposure"][var]
        table[var] = {"k_before": eb["k_concept_over_ue_geomean_key_zones"], "k_after": ea["k_concept_over_ue_geomean_key_zones"],
                      "zones": {z: {"before": {k: eb["deltas"][z][k] for k in ("Y_ratio_exposure_normalised", "dHue_deg", "dSat", "all_within")},
                                    "after_predicted": {k: ea["deltas"][z][k] for k in ("Y_ratio_exposure_normalised", "dHue_deg", "dSat", "all_within")},
                                    "median_srgb_before": before["zones"][z][var]["median_srgb"],
                                    "median_srgb_after_predicted": pred["zones"][z][var]["median_srgb"]}
                                for z in eb["deltas"] if z in ea["deltas"]}}
    concept = {z: before["zones"][z].get("concept") for z in before["zones"]}
    # sheet: per view, concept | UE before | UE after (prediction) on the board exposure and -1 EV + zone zoom
    rows = []
    H = 460
    for view in U.ORTHO:
        if view not in masks or (view, "neutral") not in mod:
            continue
        cpath = REPO / (h["concept"] % view)
        cimg = fit_h(Image.open(cpath).convert("RGB"), H)
        fig = masks[view] >= 1
        x0, y0, x1, y1 = bbox(fig, 0.04)
        zm = sel[view]
        tiles = [label(cimg, "концепт %s" % view)]
        for var, vlab in (("neutral", "EV100 1.3"), ("reading", "−1 EV")):
            b = Image.fromarray(U.load_frame(frames, cfg["hero"], tag, "%s-%s" % (view, var)))
            tiles.append(label(fit_h(b.crop((x0, y0, x1, y1)), H), "UE %s до · %s" % (tag, vlab)))
            tiles.append(label(fit_h(mod[(view, var)].crop((x0, y0, x1, y1)), H), "после (прогноз) · %s" % vlab))
        if zm.any():
            zx0, zy0, zx1, zy1 = bbox(U.erode(zm, 1) if U.erode(zm, 1).sum() > 200 else zm, 0.15, 3.0)
            b = Image.fromarray(U.load_frame(frames, cfg["hero"], tag, "%s-reading" % view))
            zb = b.crop((zx0, zy0, zx1, zy1))
            za = mod[(view, "reading")].crop((zx0, zy0, zx1, zy1))
            hh = H // 2 - 20
            tiles.append(vstack([label(fit_h(zb, hh), "зона до −1 EV", 18), label(fit_h(za, hh), "зона после −1 EV", 18)]))
        rows.append(hstack(tiles))
    # swatches: concept median / before / after (reading) of the zone
    z = h["zone"]
    sw = []
    for txt, rgb in (("концепт", concept[z]["median_srgb"]),
                     ("UE до −1 EV", before["zones"][z]["reading"]["median_srgb"]),
                     ("после −1 EV (прогноз)", pred["zones"][z]["reading"]["median_srgb"]),
                     ("UE до EV100 1.3", before["zones"][z]["neutral"]["median_srgb"]),
                     ("после EV100 1.3 (прогноз)", pred["zones"][z]["neutral"]["median_srgb"])):
        t = Image.new("RGB", (260, 90), tuple(int(round(c)) for c in rgb))
        sw.append(label(t, "%s %s" % (txt, [int(round(c)) for c in rgb]), 16))
    title = Image.new("RGB", (max(r_.width for r_ in rows), 70), (24, 24, 24))
    rr, nn = table["reading"]["zones"][z], table["neutral"]["zones"][z]
    ImageDraw.Draw(title).text((8, 6), "%s — %s.\n−1 EV: Y %.2f→%.2f, нас. %+.3f→%+.3f; EV100 1.3: Y %.2f→%.2f, нас. %+.3f→%+.3f "
                                       "(после = прогноз по кадрам UE %s, не съёмка)" % (
        cfg["hero"], h["label"], rr["before"]["Y_ratio_exposure_normalised"], rr["after_predicted"]["Y_ratio_exposure_normalised"],
        rr["before"]["dSat"], rr["after_predicted"]["dSat"], nn["before"]["Y_ratio_exposure_normalised"],
        nn["after_predicted"]["Y_ratio_exposure_normalised"], nn["before"]["dSat"], nn["after_predicted"]["dSat"], tag),
        fill=(235, 235, 235), font=font(20))
    sheet = vstack([title] + rows + [hstack(sw)])
    prev = run / "preview"
    prev.mkdir(parents=True, exist_ok=True)
    sp = prev / ("ld_5cb0_%s_sheet.png" % z.replace("_", "-"))
    sheet.save(sp, optimize=True)
    rep_path = run / "reports" / "ld-5cb0-ue-feedback.json"
    doc = {"schema": "unmatched.lookdev-5cb0-ue-feedback/1", "hero": cfg["hero"], "created": now(), "status": "измерено (прогноз)",
           "zone": z, "zone_label": h["label"], "ue_frames": U.rel(frames), "tag": tag,
           "fit": {"file_note": "ue_bc_feedback.py fit output (copied)", "select": h["select"], "sat_max": h["sat_max"],
                   "weights": h["fit"]["weights"], "keep_luma": h["fit"]["keep_luma"], "scale_applied": h["fit"]["scale"],
                   "ratio_fit": fit["ratio_effective_albedo_linear"], "ratio_used": [round(float(x), 4) for x in r],
                   "changed_pixels_by_view": {v: int(m.sum()) for v, m in sel.items()}},
           "bc_gain": gain_doc, "concept": concept[z], "table": table,
           "sheet": {"path": U.rel(sp), "sha256": U.sha(sp)},
           "model": fit["model"],
           "limits": ["prediction from the look-dev C editor frames (editor-mcp-viewport), not a UE re-shoot; the orchestrator re-imports the BC and re-shoots",
                      "specular / sheen are not separated from the diffuse: the change of saturation is an upper bound",
                      "the exposure k of the measure is the geometric mean of the key zones: an edited key zone moves k and the ratios of the other zones"]}
    U.write_json(rep_path, doc)
    print(json.dumps({v: {"k": (table[v]["k_before"], table[v]["k_after"]),
                          "zones": {zz: (t["before"]["Y_ratio_exposure_normalised"], t["before"]["dSat"], t["before"]["all_within"], "->",
                                         t["after_predicted"]["Y_ratio_exposure_normalised"], t["after_predicted"]["dSat"],
                                         t["after_predicted"]["all_within"]) for zz, t in table[v]["zones"].items()}}
                      for v in table}, indent=1, ensure_ascii=False))
    print("sheet", sp)
    return doc


# ------------------------------------------------------------------ TeamAccent (a)
def dyed_bc(bc_lin, mask, team, gain):
    y = bc_lin @ F.LUMA
    teamed = team[None, None, :] * y[..., None] * gain
    return bc_lin + (teamed - bc_lin) * mask[..., None]


def cmd_accent(a):
    sys.path.insert(0, str(REPO / "tools" / "tripo-pipeline" / "blender" / "h2_bake_arthur"))
    import lookdev_accent_mips as AM  # noqa: E402
    h = HEROES["arthur"]
    run = PC / h["asset"] / h["run"]
    before = Path(a.before)
    rep_maps = json.loads((run / "reports" / "ld-maps-report.json").read_text(encoding="utf-8"))
    mc_after = rep_maps["team_accent"]["mip_chain"]
    crit = json.loads(Path(a.criteria).read_text(encoding="utf-8"))
    # rev. 2 through the same classes (the ld_maps classes of rev. 3 are the same texels: envelope, field, tabard, other)
    cls_png = json.loads(Path(a.classes).read_text(encoding="utf-8")) if a.classes else None
    doc = {"schema": "unmatched.lookdev-5cb0-teamaccent/1", "hero": "KingArthur", "created": now(), "status": "измерено",
           "criteria_fixed_before_edit": crit, "rev3_ld_maps": mc_after,
           "rev2": json.loads(Path(a.rev2_metrics).read_text(encoding="utf-8")) if a.rev2_metrics else None,
           "classes_note": cls_png}
    # sheet: Blender renders before / after (Cobble, P1 / P2, cloak back and K2), concept crop, atlas mip strip
    concept = Image.open(REPO / (h["concept"] % "back")).convert("RGB")
    ccrop = concept.crop((280, 240, 900, 1080))
    rows = []
    for view in ("close_cloak_back_az180", "k2_5x_az180", "k2_5x_az0"):
        tiles = [label(fit_h(ccrop, 560), "концепт (back)")]
        for team in ("ld_p1", "ld_p2"):
            for tagl, root in (("до (ред. 2)", before / "render_final"), ("после (ред. 3)", run / "work" / "lookdev" / "render_final")):
                p = root / "cobble" / team / ("%s.png" % view)
                im = Image.open(p).convert("RGB")
                if view.startswith("k2"):
                    w, hh = im.size
                    im = im.crop((int(w * 0.38), int(hh * 0.22), int(w * 0.62), int(hh * 0.78))).resize((int(w * 0.24 * 2), int(hh * 0.56 * 2)), Image.NEAREST)
                tiles.append(label(fit_h(im, 560), "%s %s · %s" % (tagl, team.replace("ld_", "").upper(), view)))
        rows.append(hstack(tiles))
    # UE frame of the finding (rev. 2, i2 back P2)
    uep = PC / h["asset"] / h["ue"] / "review" / "i2" / "frames" / "kingarthur-i2-back-p2.png"
    ue_im = Image.open(uep).convert("RGB").crop((700, 230, 1220, 900))
    # atlas: what a pixel reads at mips 0-3 (P2, box mips), border region
    bc2 = F.lin(np.asarray(Image.open(run / "textures" / "T_KingArthur_H2LD_BC_2K.png").convert("RGB"), np.float64) / 255.0)
    bc2_old = F.lin(np.asarray(Image.open(before / "textures" / "T_KingArthur_H2LD_BC_2K.png").convert("RGB"), np.float64) / 255.0)
    m_new = np.asarray(Image.open(run / "textures" / "T_KingArthur_H2LD_TeamAccent_2K.png"), np.float64) / 255.0
    m_old = np.asarray(Image.open(before / "textures" / "T_KingArthur_H2LD_TeamAccent_2K.png"), np.float64) / 255.0
    team = np.array([0.1022, 0.2122, 0.3467])   # P2 #5A7F9F linear
    gain = float(a.gain_p2)
    y0, y1, x0, x1 = 1590, 1790, 20, 220      # 2K atlas window on a vertical cloak border (rows from the top)
    strips = []
    for tagl, bc, mk in (("до (ред. 2)", bc2_old, m_old), ("после (ред. 3)", bc2, m_new)):
        tiles = []
        mips_b = [AM.chain(bc[..., c], 3, "box") for c in range(3)]
        mips_m = AM.chain(mk, 3, "box")
        for lv in range(4):
            f = 2 ** lv
            bcl = np.stack([mips_b[c][lv] for c in range(3)], -1)
            ml = mips_m[lv]
            d = dyed_bc(bcl, ml, team, gain)
            win = d[y0 // f:y1 // f, x0 // f:x1 // f]
            im = Image.fromarray((F.srgb(win) * 255).round().astype(np.uint8)).resize((200, 200), Image.NEAREST)
            tiles.append(label(im, "%s мип %d (%d px)" % (tagl, lv, 2048 // f), 14))
        strips.append(hstack(tiles))
    atlas = vstack(strips)
    rows.append(hstack([label(fit_h(ue_im, 470), "UE i2 back P2 (находка look-dev C, ред. 2)", 18), atlas]))
    title = Image.new("RGB", (max(r_.width for r_ in rows), 70), (24, 24, 24))
    ta = mc_after["criteria_result"]["worst"]
    ImageDraw.Draw(title).text((8, 6), "King Arthur TeamAccent ред. 2 → ред. 3 (5c-B0): кайма плаща закрашена на мипах 0–3 — до %s, после ≤ %.1f %%;\n"
                                       "поле плаща ≤ %.1f %%. Кадры Blender (EEVEE, свет ≈ Cobble), не UE" % (
        a.rev2_border or "54–97 %", ta["border"] * 100, ta["field"] * 100), fill=(235, 235, 235), font=font(20))
    sheet = vstack([title] + rows)
    sp = run / "preview" / "ld_5cb0_teamaccent_sheet.png"
    sheet.save(sp, optimize=True)
    doc["sheet"] = {"path": U.rel(sp), "sha256": U.sha(sp)}
    U.write_json(run / "reports" / "ld-5cb0-teamaccent.json", doc)
    print("sheet", sp)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["feedback", "accent"])
    ap.add_argument("--hero")
    ap.add_argument("--fit")
    ap.add_argument("--gain")
    ap.add_argument("--before")
    ap.add_argument("--criteria")
    ap.add_argument("--classes")
    ap.add_argument("--rev2-metrics")
    ap.add_argument("--rev2-border")
    ap.add_argument("--gain-p2", default="19.8955")
    a = ap.parse_args()
    {"feedback": cmd_feedback, "accent": cmd_accent}[a.command](a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
