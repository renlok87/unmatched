"""Stage ld_compose of the Harpy look-dev v2 (system python): sheets and measurements of the ld_review frames.

    python lookdev_compose.py <harpy-h3-lookdev.json>

Reference of every sheet = the CONCEPT (first panel); H3 = the frame of the same name from the H3 run
(work/h3-frames/h3_<name>.png, review_h3.py rev 2, same cameras and lights).

Measurements (reports/ld-measure-report.json):
  gold_tone   concept framing, preview light, Standard view (sRGB OETF -> linear): per zone of the profile
              (concept_zones) the median linear colour of the concept pixels (box x HSV filter) and of the LD render
              pixels (box x class of the ID pass x alpha); the feather zones (BC unchanged from H3 = concept colours)
              give the light/exposure ratio k = median Y(concept) / Y(render); the gold F0 that would match the concept
              = F0 x (concept / (k x render)) per channel (a rough metal reflects in proportion to F0 per channel)
  k2_cobble   Cobble K2 5x az 0 (AgX, calibrated): body pixels (alpha of the body-only frame): luma p50, S p50, share
              V < 0.25, as the H3 report 3.1, for H3 and LD; TeamAccent visibility = share of body pixels whose
              colour changes by > 12 levels between the undyed and the P1 / P2 frames
  bracelet    the band pixels of the talons close-up (fixed box) in the Cobble light: luma / S / hue for H3,
              H3 with ORM connected, LD
Sheets: preview/ld_sheet_*.jpg.
"""

import colorsys
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LUMA = np.array([0.2126, 0.7152, 0.0722])
BG = (45, 45, 48)


def lin(c):
    c = np.clip(c, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rgba(path):
    return np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)


def flat(path, bg=BG):
    im = Image.open(path).convert("RGBA")
    b = Image.new("RGBA", im.size, bg + (255,))
    b.alpha_composite(im)
    return b.convert("RGB")


def hsv_arr(rgb8):
    x = rgb8 / 255.0
    mx, mn = x.max(-1), x.min(-1)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    h = np.degrees(np.arctan2(np.sqrt(3) * (g - b), 2 * r - g - b)) % 360
    return h, s, mx


def filt(rgb8, f):
    h, s, v = hsv_arr(rgb8)
    m = np.ones(h.shape, bool)
    if "hue" in f:
        m &= (h >= f["hue"][0]) & (h <= f["hue"][1])
    for k, arr, op in (("s_min", s, np.greater_equal), ("s_max", s, np.less_equal), ("v_min", v, np.greater_equal),
                       ("v_max", v, np.less_equal)):
        if k in f:
            m &= op(arr, f[k])
    return m


def stats8(px):
    """px: N x 3 uint8-ish sRGB -> luma p50 (0-255), S p50, hue of the median colour."""
    if not len(px):
        return None
    lum = px @ LUMA
    _h, s, _v = hsv_arr(px)
    med = np.median(px, 0) / 255.0
    hh = colorsys.rgb_to_hsv(*med)[0] * 360
    return {"n": int(len(px)), "luma_p50": round(float(np.median(lum)), 1), "s_p50": round(float(np.median(s)), 3),
            "hue_of_median_deg": round(hh, 1), "srgb8_median": [round(float(v), 1) for v in np.median(px, 0)]}


def label(im, text, h=34):
    out = Image.new("RGB", (im.width, im.height + h), (20, 20, 22))
    out.paste(im, (0, h))
    ImageDraw.Draw(out).text((8, 8), text, fill=(235, 235, 235))
    return out


def row(images, texts, height):
    ims = [label(i.resize((int(i.width * height / i.height), height)), t) for i, t in zip(images, texts)]
    W = sum(i.width for i in ims)
    out = Image.new("RGB", (W, ims[0].height), (20, 20, 22))
    x = 0
    for i in ims:
        out.paste(i, (x, 0))
        x += i.width
    return out


def stack(rows):
    W = max(r.width for r in rows)
    out = Image.new("RGB", (W, sum(r.height for r in rows)), (20, 20, 22))
    y = 0
    for r in rows:
        out.paste(r, (0, y))
        y += r.height
    return out


def main():
    prof_path = Path(sys.argv[1]).resolve()
    prof = json.loads(prof_path.read_text(encoding="utf-8"))
    ld = prof["lookdev"]
    run = REPO / prof["run_dir"]
    fr = run / "work" / "ld-frames"
    h3 = REPO / ld["review"]["baseline_frames"]
    concept = {v: REPO / ("art/imagegen/hero-quality-v1/harpy/harpy-%s.png" % v) for v in ("front", "side", "back")}
    maps = json.loads((run / "reports" / "ld-maps-report.json").read_text(encoding="utf-8"))
    class_rgb = {"gold_antique": (235, 180, 40), "horn_claw": (40, 40, 60), "leather_smooth": (220, 40, 200),
                 "feathers": (60, 160, 160), "skin": (250, 205, 175)}
    cz = ld["concept_zones"]
    rep = {"stage": "ld_compose", "profile": prof_path.relative_to(REPO).as_posix(), "status": "измерено",
           "label": ld["review"]["label"]}
    # ---------------------------------------------------------------- gold tone (concept framing)
    zones = {}
    for view in ("front", "back"):
        c8 = np.asarray(Image.open(concept[view]).convert("RGB")).astype(np.float64)
        ld_ = rgba(fr / ("concept_%s.png" % view))
        h3_ = rgba(h3 / ("h3_concept_%s.png" % view))
        idp = rgba(fr / ("id_concept_%s.png" % view))
        for z in cz[view]:
            x0, y0, x1, y1 = z["box"]
            box = np.zeros(c8.shape[:2], bool)
            box[y0:y1, x0:x1] = True
            mc = box & filt(c8, cz["filters"][z["filter"]])
            cls = np.array(class_rgb[z["class"]], np.float64)
            mr = box & (np.abs(idp[..., :3] - cls).max(-1) <= 3) & (idp[..., 3] > 250) & (ld_[..., 3] > 250)
            e = zones.setdefault(z["zone"], {"concept": [], "ld": [], "h3": []})
            e["concept"].append(c8[mc])
            e["ld"].append(ld_[..., :3][mr])
            e["h3"].append(h3_[..., :3][mr & (h3_[..., 3] > 250)])
    zrep = {}
    for zn, e in zones.items():
        zrep[zn] = {}
        for who in ("concept", "ld", "h3"):
            px = np.concatenate(e[who], 0) if e[who] else np.zeros((0, 3))
            st = stats8(px)
            if st:
                st["linear_median"] = [round(float(v), 4) for v in np.median(lin(px / 255.0), 0)]
            zrep[zn][who] = st
    refs = cz["reference_zones"]
    k_ld = [(np.array(zrep[z]["concept"]["linear_median"]) @ LUMA) / (np.array(zrep[z]["ld"]["linear_median"]) @ LUMA)
            for z in refs if zrep[z]["ld"] and zrep[z]["concept"]]
    k = float(np.median(k_ld))
    f0 = np.array(maps["lut"]["gold_antique_f0_hero"], np.float64)

    def lm(z, who):
        return np.array(zrep[z][who]["linear_median"])

    def chroma(z):   # per-channel ratio concept / LD render, luminance-normalised
        ratio = lm(z, "concept") / lm(z, "ld")
        return ratio / ((lm(z, "concept") @ LUMA) / (lm(z, "ld") @ LUMA))

    chroma_ref = np.exp(np.mean([np.log(chroma(z)) for z in refs], 0))
    chroma_gold = chroma("gold") / chroma_ref
    luma_gold = ((lm("gold", "concept") @ LUMA) / (lm("gold", "ld") @ LUMA)) / k
    sug = f0 * chroma_gold * luma_gold
    over = float(sug.max())
    sug_c = sug / over if over > 1.0 else sug
    y_floor = float(ld["concept_zones"].get("gold_f0_min_Y", 0.45))
    if float(sug_c @ LUMA) < y_floor:
        sug_c = sug_c * min(y_floor / float(sug_c @ LUMA), 1.0 / float(sug_c.max()))
    rep["gold_tone"] = {"zones": zrep, "reference_zones": refs, "k_per_reference": [round(float(x), 4) for x in k_ld],
                        "k_light_ratio": round(k, 4), "f0_current": [round(float(v), 4) for v in f0],
                        "reference_chroma_ratio": [round(float(v), 4) for v in chroma_ref],
                        "gold_chroma_ratio_corrected": [round(float(v), 4) for v in chroma_gold],
                        "gold_luma_ratio_over_k": round(float(luma_gold), 4),
                        "f0_suggested_raw": [round(float(v), 4) for v in sug],
                        "f0_suggested": [round(float(v), 4) for v in sug_c],
                        "f0_suggested_Y": round(float(sug_c @ LUMA), 4),
                        "residual_per_channel": [round(float(v), 4) for v in chroma_gold * luma_gold],
                        "method": "F0_new = F0 x chroma x luma. chroma = per-channel ratio concept / LD render of the gold "
                                  "zone (luminance-normalised) divided by the same ratio of the feather reference zones "
                                  "(geometric mean): the concept's colour grading - it saturates the orange feathers too, "
                                  "whose BC is the concept colour - is cancelled; luma = Y ratio of the gold zone / k, k = "
                                  "median Y ratio of the reference zones (light and exposure of the two images). A rough "
                                  "metal reflects in proportion to F0 per channel. Max channel <= 1; Y >= %.2f (bare metal "
                                  "rule of the library)" % y_floor}
    # ---------------------------------------------------------------- K2 Cobble statistics
    def body_stats(frame, mask):
        im = rgba(frame)[..., :3]
        a = rgba(mask)[..., 3] > 250
        px = im[a]
        _h, s, v = hsv_arr(px)
        return {"pixels": int(a.sum()), "luma_p50": round(float(np.median(px @ LUMA)), 1),
                "s_p50": round(float(np.median(s)), 3), "dark_share_v_lt_0.25": round(float((v < 0.25).mean()), 4)}

    mask_ld = fr / "cobble_mask_body_k2_5x_az000.png"
    k2 = {"h3": body_stats(h3 / "h3_cobble_k2_5x_az000.png", h3 / "h3_cobble_mask_body_k2_5x_az000.png"),
          "ld_none": body_stats(fr / "cobble_k2_5x_az000_none.png", mask_ld),
          "h3_orm_connected": body_stats(fr / "h3orm_cobble_k2_5x_az000.png", mask_ld)}
    a = rgba(mask_ld)[..., 3] > 250
    vis = {}
    for az in ("000", "040"):
        n0 = rgba(fr / ("cobble_k2_5x_az%s_none.png" % az))[..., :3]
        for t in ("P1", "P2"):
            changed = np.abs(rgba(fr / ("cobble_k2_5x_az%s_%s.png" % (az, t)))[..., :3] - n0).max(-1) > 12
            vis["az%s_%s" % (az, t)] = {"changed_pixels": int(changed.sum())}
            if az == "000":
                vis["az%s_%s" % (az, t)]["share_of_body_pixels"] = round(float((changed & a).sum() / a.sum()), 4)
    k2["team_accent_visibility"] = vis
    k2["note"] = "az 040 has no body-only frame: changed pixels only; share of body pixels for az 000"
    rep["k2_cobble"] = k2
    # ---------------------------------------------------------------- bracelet in the Cobble light (talons close-up)
    brac_box = ld["review"].get("bracelet_box_close_talons_3q", [590, 220, 860, 380])
    x0, y0, x1, y1 = brac_box
    cb = {}
    for who, p in (("h3", h3 / "h3_cobble_close_talons_3q.png"), ("h3_orm_connected", fr / "h3orm_cobble_close_talons_3q.png"),
                   ("ld_none", fr / "cobble_close_talons_3q_none.png")):
        im = rgba(p)[y0:y1, x0:x1, :3]
        m = filt(im, {"hue": [25, 65], "s_min": 0.2, "v_min": 0.35})
        cb[who] = stats8(im[m])
    rep["bracelet_cobble_close"] = {"box_px": brac_box, "filter": "hue 25-65, S >= 0.2, V >= 0.35 (gold pixels of the band)",
                                    "stats": cb}
    # ---------------------------------------------------------------- sheets
    pv = run / "preview"
    pv.mkdir(parents=True, exist_ok=True)
    sheets = {}
    for view in ("front", "side", "back"):
        s = row([Image.open(concept[view]).convert("RGB"), flat(h3 / ("h3_concept_%s.png" % view)), flat(fr / ("concept_%s.png" % view))],
                ["CONCEPT harpy-%s" % view, "H3 (blender, preview light)", "LOOKDEV v2 (blender, preview light, no dye)"], 535)
        p = pv / ("ld_sheet_concept_%s.jpg" % view)
        s.save(p, quality=90)
        sheets[view] = p.name

    def crop_fig(path, box=(560, 180, 1360, 720)):
        return Image.open(path).convert("RGB").crop(box)

    rows = []
    for az in ("000", "040"):
        rows.append(row([crop_fig(h3 / ("h3_cobble_k2_5x_az%s.png" % az))] +
                        [crop_fig(fr / ("cobble_k2_5x_az%s_%s.png" % (az, t))) for t in ("none", "P1", "P2")],
                        ["H3 Cobble K2 5x az%s" % az, "LD no dye", "LD TeamAccent P1 #E8C06A", "LD TeamAccent P2 #5A7F9F"], 480))
    rows.append(row([crop_fig(h3 / "h3_cobble_k2_5x_az180.png")] + [crop_fig(fr / ("cobble_k2_5x_az180_%s.png" % t)) for t in ("none", "P1")],
                    ["H3 Cobble K2 5x az180", "LD no dye", "LD P1"], 480))
    p = pv / "ld_sheet_k2_cobble.jpg"
    stack(rows).save(p, quality=90)
    sheets["k2_cobble"] = p.name
    s = stack([row([crop_fig(h3 / ("h3_k2_5x_az%03d.png" % az)), crop_fig(fr / ("k2_5x_az%03d.png" % az))],
                   ["H3 K2 5x az%03d preview light" % az, "LD K2 5x az%03d" % az], 480) for az in (0, 40, 180)])
    p = pv / "ld_sheet_k2_preview.jpg"
    s.save(p, quality=90)
    sheets["k2_preview"] = p.name
    cbr = Image.open(concept["front"]).convert("RGB").crop((690, 690, 890, 890))
    s = row([cbr, Image.open(h3 / "h3_cobble_close_talons_3q.png").convert("RGB"), Image.open(fr / "h3orm_cobble_close_talons_3q.png").convert("RGB")]
            + [Image.open(fr / ("cobble_close_talons_3q_%s.png" % t)).convert("RGB") for t in ("none", "P1", "P2")],
            ["CONCEPT (front crop)", "H3 Cobble", "H3 maps, LD material (control)", "LD no dye", "LD P1", "LD P2"], 500)
    p = pv / "ld_sheet_talons_cobble.jpg"
    s.save(p, quality=90)
    sheets["talons"] = p.name
    s = row([Image.open(concept["front"]).convert("RGB").crop((560, 600, 940, 900)),
             flat(h3 / "h3_concept_front.png").crop((560, 600, 940, 900)),
             flat(fr / "h3orm_concept_front.png").crop((560, 600, 940, 900)),
             flat(fr / "concept_front.png").crop((560, 600, 940, 900))],
            ["CONCEPT", "H3 frame (review_h3)", "H3 maps, LD material (control)", "LOOKDEV v2"], 450)
    p = pv / "ld_sheet_bracelet_front.jpg"
    s.save(p, quality=90)
    sheets["bracelet_front"] = p.name
    rep["sheets"] = sheets
    (run / "reports").mkdir(parents=True, exist_ok=True)
    (run / "reports" / "ld-measure-report.json").write_text(json.dumps(rep, indent=1, sort_keys=True, ensure_ascii=False) + "\n",
                                                             encoding="utf-8", newline="\n")
    print("LD_COMPOSE_OK k=%.3f f0_suggested=%s" % (k, rep["gold_tone"]["f0_suggested"]))


if __name__ == "__main__":
    main()
