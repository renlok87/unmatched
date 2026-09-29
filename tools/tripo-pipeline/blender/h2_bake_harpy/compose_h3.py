"""H3 comparison sheets (system Python, Pillow + numpy): CONCEPT | H2.1 | H3.

    python compose_h3.py <profile.json> <run_dir> [--rev1 <dir of rev 1 cobble raw frames>]

Reads <run>/work/h3-frames/{h21,h3}_*.png (review_h3.py) and the concepts; writes <run>/preview/h3/*.jpg (JPEG q90
4:4:4) and <run>/preview/h3/frames-storage-h3.json (sha256 of every raw frame). The concept is the first panel of every
sheet that has a concept counterpart (the reference is always the concept, not the previous iteration). Every panel is
labelled; nothing here is an UE frame.

Cobble measurement (<run>/preview/h3/cobble-measure-h3.json): the exposure calibration (reports/cobble-calibration.json),
the K2 5x board luma of the board-only frame against the UE Cobble editor frame of the Arthur H2.1 import, and colour
statistics (HSV of the 8-bit sRGB pixels) of the BODY (alpha of cobble_mask_body_*, base excluded) at K2 5x az 0 / 40
in the preview light, the calibrated Cobble light and the warm variant, next to the concept front (figure pixels = max
|RGB - background (46, 48, 50)| > 15 above row 860, the gold base excluded) and the face centre ROI of the close-ups.
--rev1 adds the same statistics for the uncalibrated rev 1 Cobble frames (backup of work/h3-frames, sha256 recorded).
Band: fixed box (660, 270)-(820, 350) of the 1000 px talons_3q close-ups (inside the left-leg band of both runs), concept
box (770, 740)-(830, 772) of harpy-front.png. View-transform probe (cobvt_* frames, each calibrated to the same board
anchor): cmp_h3_cobble_vt_probe.jpg and the band / face statistics per view transform.
The concept is a lit imagegen render with its own light: its numbers are a direction, not a target value.
"""

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

profile_path, run = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
REV1 = Path(sys.argv[sys.argv.index("--rev1") + 1]).resolve() if "--rev1" in sys.argv else None
P = json.loads(profile_path.read_text(encoding="utf-8"))
REPO = Path(__file__).resolve().parents[4]
RIG = json.loads((run / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
BASE = REPO / P["review"]["h3"]["baseline_run"]
RIG_B = json.loads((BASE / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
RAW = run / "work" / "h3-frames"
OUT = run / "preview" / "h3"
OUT.mkdir(parents=True, exist_ok=True)
BG = (46, 47, 51)
K2 = P["review"].get("k2_live", {}).get("distances_m", {"5x": 3.86, "1.6x": 12.07})
GC = P["review"]["game_camera"]
written = []
NAME = {"h21": "H2.1 (%.1fk tris)" % (RIG_B["measure"]["triangles_body"] / 1000.0),
        "h3": "H3 (%.1fk tris)" % (RIG["measure"]["triangles_body"] / 1000.0)}
RIGS = {"h21": RIG_B, "h3": RIG}
CON = {k: Image.open(REPO / v).convert("RGB") for k, v in P["review"]["concepts"].items()}
CAL = json.loads((run / "reports" / "cobble-calibration.json").read_text(encoding="utf-8"))
COB = "Cobble approx (key 4.5 lux, sky 11.2, EV100 1.3 %+.2f EV: board K1 p50 %.0f = W4-A 131)" % (
    CAL["exposure_offset_stops"], CAL["k1_board_p50_final"])


def label(img, text, xy=(10, 8)):
    d = ImageDraw.Draw(img)
    d.rectangle([xy[0] - 4, xy[1] - 3, xy[0] + 7 * len(text) + 6, xy[1] + 14], fill=(0, 0, 0))
    d.text(xy, text, fill=(255, 220, 90))


def raw(who, name):
    return Image.open(RAW / ("%s_%s.png" % (who, name)))


def on_bg(im):
    im = im.convert("RGBA")
    bg = Image.new("RGBA", im.size, BG + (255,))
    bg.alpha_composite(im)
    return bg.convert("RGB")


def row(panels, gap=8):
    h = max(p.height for p in panels)
    w = sum(p.width for p in panels) + gap * (len(panels) - 1)
    s = Image.new("RGB", (w, h), (0, 0, 0))
    x = 0
    for p in panels:
        s.paste(p, (x, 0))
        x += p.width + gap
    return s


def col(rows_, gap=8):
    w = max(r.width for r in rows_)
    h = sum(r.height for r in rows_) + gap * (len(rows_) - 1)
    s = Image.new("RGB", (w, h), (0, 0, 0))
    y = 0
    for r in rows_:
        s.paste(r, (0, y))
        y += r.height + gap
    return s


def save(img, name):
    p = OUT / name
    img.save(p, quality=90, subsampling=0)
    written.append(p.name)


def concept_crop(view, box, size):
    c = CON[view]
    w, h = c.size
    cr = c.crop((int(w * box[0]), int(h * box[1]), int(w * box[2]), int(h * box[3])))
    k = min(size[0] / cr.width, size[1] / cr.height)
    cr = cr.resize((int(cr.width * k), int(cr.height * k)), Image.LANCZOS)
    label(cr, "CONCEPT (imagegen) %s" % view)
    return cr


def project(pt, az, dist, w=1920, h=1080):
    el = math.radians(-GC["pitch_deg"])
    a_ = math.radians(az)
    d = np.array([math.sin(a_) * math.cos(el), -math.cos(a_) * math.cos(el), math.sin(el)])
    t = np.array([0.0, 0.0, 0.12])
    cam = t + d * dist
    f = -d
    right = np.cross(f, [0, 0, 1.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, f)
    v = np.array(pt) - cam
    x, y, z = v @ right, v @ up, v @ f
    fx = (w / 2) / math.tan(math.radians(GC["horizontal_fov_deg"]) / 2)
    return w / 2 + fx * x / z, h / 2 - fx * y / z


# 1. concept | H2.1 | H3 (ortho, framed like the concept)
for view in ("front", "side", "back"):
    c = CON[view].copy()
    label(c, "CONCEPT (imagegen, hero-quality-v1) - %s = reference" % view)
    panels = [c]
    for who in ("h21", "h3"):
        r = on_bg(raw(who, "concept_%s" % view)).resize(c.size, Image.LANCZOS)
        label(r, "blender: %s, baked 4K, EEVEE preview light" % NAME[who])
        panels.append(r)
    s = row(panels)
    s = s.resize((s.width * 2 // 3, s.height * 2 // 3), Image.LANCZOS)
    save(s, "cmp_h3_concept_%s.jpg" % view)

# 2. K2 5x / 1.6x, concept front as the first panel of each row block
for zoom, dist in sorted(K2.items()):
    tagz = zoom.replace(".", "p")
    scale = 1 if zoom == "5x" else 3
    half = (430, 300) if zoom == "5x" else (140, 95)
    rows_ = []
    for who in ("h21", "h3"):
        panels = [concept_crop("front" if who == "h21" else "back", (0.02, 0.05, 0.98, 0.95), (860, 600))]
        # row 1 opens with the front concept (azimuths 0/40), row 2 with the back concept (azimuths 140/180)
        for az in (0, 40, 140, 180):
            im = raw(who, "k2_%s_az%03d" % (tagz, az)).convert("RGB")
            cxy = project((0, 0, 0.2), az, dist)
            cr = im.crop((int(cxy[0] - half[0]), int(cxy[1] - half[1]), int(cxy[0] + half[0]), int(cxy[1] + half[1])))
            if scale > 1:
                cr = cr.resize((cr.width * scale, cr.height * scale), Image.NEAREST)
            label(cr, "%s | K2 %s (%.2f m) az %d%s" % (NAME[who], zoom, dist, az, "" if scale == 1 else ", crop x%d nearest" % scale))
            panels.append(cr)
        rows_.append(row(panels))
    save(col(rows_), "cmp_h3_k2_%s.jpg" % tagz)

# 3. close-ups: concept crop | H2.1 | H3
CROPS = {"face_front": ("front", (0.40, 0.20, 0.60, 0.47)), "face_game": ("front", (0.40, 0.20, 0.60, 0.47)),
         "nape_back": ("back", (0.38, 0.06, 0.62, 0.45)), "nape_game": ("back", (0.38, 0.06, 0.62, 0.45)),
         "talons_3q": ("front", (0.33, 0.62, 0.67, 0.86)), "talons_front": ("front", (0.33, 0.62, 0.67, 0.86)),
         "base_band": ("front", (0.33, 0.62, 0.67, 0.92))}
TITLE = {"face_front": "face, front ortho", "face_game": "face at the game pitch -55 (what K2 sees, magnified)",
         "nape_back": "back of the head, ortho from behind", "nape_game": "nape at the game pitch, az 180",
         "talons_3q": "talons / band 3/4", "talons_front": "talons front", "base_band": "base, band and top"}
for name, (view, box) in CROPS.items():
    panels = [concept_crop(view, box, (1000, 1000))]
    for who in ("h21", "h3"):
        im = raw(who, "close_" + name).convert("RGB")
        label(im, "blender: %s - %s" % (NAME[who], TITLE[name]))
        panels.append(im)
    save(row(panels), "cmp_h3_close_%s.jpg" % name)

# 4. face at K2: concept face | K2 5x face crops x4 | K2 1.6x x10 for both
cf = concept_crop("front", (0.40, 0.20, 0.60, 0.47), (400, 400))
kp = [cf]
for who in ("h21", "h3"):
    fc = RIGS[who]["measure"]["face_centroid_m"]
    im = raw(who, "k2_5x_az000").convert("RGB")
    x, y = project(fc, 0, K2["5x"])
    cr = im.crop((int(x - 50), int(y - 50), int(x + 50), int(y + 50))).resize((400, 400), Image.NEAREST)
    label(cr, "%s K2 5x face x4" % NAME[who])
    kp.append(cr)
    im = raw(who, "k2_1p6x_az000").convert("RGB")
    x, y = project(fc, 0, K2["1.6x"])
    cr = im.crop((int(x - 20), int(y - 20), int(x + 20), int(y + 20))).resize((400, 400), Image.NEAREST)
    label(cr, "%s K2 1.6x face x10" % NAME[who])
    kp.append(cr)
save(row(kp), "cmp_h3_face_k2.jpg")

# 5. game-light approximation (Cobble): concept | H2.1 | H3 at K2 5x az 0 / 40 / 180, 1.6x az 40; close-ups
rows_ = []
for who in ("h21", "h3"):
    panels = [concept_crop("front", (0.02, 0.05, 0.98, 0.95), (860, 600))]
    for name, az, zoom in (("k2_5x_az000", 0, "5x"), ("k2_5x_az040", 40, "5x"), ("k2_5x_az180", 180, "5x"),
                           ("k2_1p6x_az040", 40, "1.6x")):
        im = raw(who, "cobble_" + name).convert("RGB")
        cxy = project((0, 0, 0.2), az, K2[zoom])
        half = (430, 300) if zoom == "5x" else (140, 95)
        cr = im.crop((int(cxy[0] - half[0]), int(cxy[1] - half[1]), int(cxy[0] + half[0]), int(cxy[1] + half[1])))
        if zoom != "5x":
            cr = cr.resize((cr.width * 3, cr.height * 3), Image.NEAREST)
        label(cr, "%s | %s, white key, K2 %s az %d" % (NAME[who], COB, zoom, az))
        panels.append(cr)
    rows_.append(row(panels))
save(col(rows_), "cmp_h3_cobble_k2.jpg")
rows_ = []
for who in ("h21", "h3"):
    panels = []
    for name in ("k2_5x_az000", "k2_5x_az040"):
        im = raw(who, "cobwarm_" + name).convert("RGB")
        az = int(name[-3:])
        cxy = project((0, 0, 0.2), az, K2["5x"])
        cr = im.crop((int(cxy[0] - 430), int(cxy[1] - 300), int(cxy[0] + 430), int(cxy[1] + 300)))
        label(cr, "%s | %s, WARM key (brief assumption) K2 5x az %d" % (NAME[who], COB, az))
        panels.append(cr)
    rows_.append(row(panels))
save(col(rows_), "cmp_h3_cobble_warm_k2.jpg")
for name, (view, box) in (("face_game", CROPS["face_game"]), ("nape_game", CROPS["nape_game"]),
                          ("talons_3q", CROPS["talons_3q"])):
    panels = [concept_crop(view, box, (1000, 1000))]
    for who in ("h21", "h3"):
        im = raw(who, "cobble_close_" + name).convert("RGB")
        label(im, "blender: %s - %s, %s" % (NAME[who], TITLE[name], COB))
        panels.append(im)
    save(row(panels), "cmp_h3_cobble_close_%s.jpg" % name)

# 6. team band Gold / Silver (H3)
panels = []
for team in ("gold", "silver"):
    im = raw("h3", "team_%s_k2_5x" % team).convert("RGB")
    x, y = project((0, 0, 0.05), 40, K2["5x"])
    cr = im.crop((int(x - 330), int(y - 330), int(x + 330), int(y + 170)))
    label(cr, "H3 K2 5x az 40, team %s (base band = TeamColor, metal)" % team)
    panels.append(cr)
save(row(panels), "cmp_h3_teamcolor.jpg")



# 7. Cobble measurement (see module doc)
def luma(a):
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def hsv_stats(px):
    """px: (n, 3) uint8 sRGB -> HSV statistics (S, V in 0-1, hue in degrees)."""
    f = px.astype(np.float64) / 255.0
    mx, mn = f.max(1), f.min(1)
    v = mx
    s_ = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    r, g, b = f[:, 0], f[:, 1], f[:, 2]
    d = np.maximum(mx - mn, 1e-9)
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    chrom = s_ > 0.3
    orange = chrom & (h >= 15) & (h <= 45) & (v > 0.35)
    return {"pixels": int(len(px)), "luma_p50": round(float(np.median(luma(px.astype(np.float64)))), 1),
            "S_p50": round(float(np.median(s_)), 3), "V_p50": round(float(np.median(v)), 3),
            "V_p90": round(float(np.percentile(v, 90)), 3),
            "bleached_frac": round(float(np.mean((s_ < 0.25) & (v > 0.75))), 4),
            "dark_frac_V_lt_0p25": round(float(np.mean(v < 0.25)), 4),
            "hue_p50_of_S_gt_0p3": round(float(np.median(h[chrom])), 1) if chrom.any() else None,
            "orange_frac": round(float(np.mean(orange)), 4),
            "orange_S_p50": round(float(np.median(s_[orange])), 3) if orange.any() else None,
            "orange_V_p50": round(float(np.median(v[orange])), 3) if orange.any() else None,
            "mean_rgb": [round(float(x), 1) for x in px.mean(0)]}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


meas = {"schema": "unmatched.h3-cobble-measure/1",
        "label": "measurement of Blender frames (EEVEE) and the concept image; not an UE frame",
        "calibration": {k: CAL[k] for k in ("anchor", "target_board_p50_luma", "exposure_offset_stops",
                                             "blender_exposure", "k1_board_p50_final", "board_albedo_linear")},
        "stats_def": "HSV of 8-bit sRGB; bleached = S < 0.25 and V > 0.75; orange = S > 0.3, hue 15-45 deg, V > 0.35",
        "body": {}, "face_centre_roi": {}}
bo = np.asarray(raw("h3", "cobble_board_k2_5x_az000").convert("RGB")).astype(np.float64)
Lb = luma(bo)
ue = REPO / "docs/art-pipeline/evidence/w5c-arthur-h2-ue-2026-09-29/arthur-h2-k2-5x-az0-blue-ue-editor.jpg"
Lu = luma(np.asarray(Image.open(ue).convert("RGB")).astype(np.float64))
corners = lambda L_: [round(float(np.median(L_[y:y + 150, x:x + 300])), 1) for y, x in ((0, 0), (0, 1620), (930, 0), (930, 1620))]
meas["k2_5x_board"] = {"blender_board_only_az000": {"frame_p50": round(float(np.median(Lb)), 1), "corners_p50": corners(Lb)},
                       "ue_cobble_editor_arthur_h21_k2_5x_az0": {"file": str(ue.relative_to(REPO)).replace("\\", "/"),
                                                                "sha256": sha(ue), "frame_p50": round(float(np.median(Lu)), 1),
                                                                "corners_p50": corners(Lu)},
                       "note": "UE frame: textured cobblestones, figure and UI in frame; Blender: flat board of the mean albedo"}
c = np.asarray(CON["front"]).astype(np.int16)
cm = (np.abs(c - np.array([46, 48, 50])).max(-1) > 15)
cm[860:] = False
meas["body"]["concept_front"] = {"file": P["review"]["concepts"]["front"], **hsv_stats(c[cm].astype(np.uint8))}
sources = {"preview": "k2_5x_%s", "cobble_rev2": "cobble_k2_5x_%s", "cobwarm_rev2": "cobwarm_k2_5x_%s"}
for who in ("h21", "h3"):
    for az in ("az000", "az040"):
        m = np.asarray(raw(who, "cobble_mask_body_k2_5x_" + az).convert("RGBA"))[..., 3] > 250
        for key, pat in sources.items():
            im = np.asarray(raw(who, pat % az).convert("RGB"))
            meas["body"]["%s_%s_%s" % (who, key, az)] = hsv_stats(im[m])
        if REV1 is not None:
            for key, pat in (("cobble_rev1", "cobble_k2_5x_%s"), ("cobwarm_rev1", "cobwarm_k2_5x_%s")):
                f = REV1 / ("%s_%s.png" % (who, pat % az))
                if f.exists():
                    im = np.asarray(Image.open(f).convert("RGB"))
                    meas["body"]["%s_%s_%s" % (who, key, az)] = {"sha256": sha(f), **hsv_stats(im[m])}
# face centre ROI: centre 300 x 300 px of the 1000 px face close-ups; concept: centre 30 % of the face crop
w_, h_ = CON["front"].size
fx0, fy0, fx1, fy1 = CROPS["face_game"][1]
cx, cy, hw, hh = (fx0 + fx1) / 2 * w_, (fy0 + fy1) / 2 * h_, 0.15 * (fx1 - fx0) * w_, 0.15 * (fy1 - fy0) * h_
cf_px = np.asarray(CON["front"])[int(cy - hh):int(cy + hh), int(cx - hw):int(cx + hw)].reshape(-1, 3)
meas["face_centre_roi"]["concept_front"] = hsv_stats(cf_px)
for who in ("h21", "h3"):
    for key, name in (("preview", "close_face_game"), ("cobble_rev2", "cobble_close_face_game")):
        im = np.asarray(raw(who, name).convert("RGB"))[350:650, 350:650].reshape(-1, 3)
        meas["face_centre_roi"]["%s_%s" % (who, key)] = hsv_stats(im)
    if REV1 is not None and (REV1 / ("%s_cobble_close_face_game.png" % who)).exists():
        f = REV1 / ("%s_cobble_close_face_game.png" % who)
        im = np.asarray(Image.open(f).convert("RGB"))[350:650, 350:650].reshape(-1, 3)
        meas["face_centre_roi"]["%s_cobble_rev1" % who] = {"sha256": sha(f), **hsv_stats(im)}
# band (see module doc)
BAND_BOX, CON_BAND_BOX = (660, 270, 820, 350), (770, 740, 830, 772)
meas["band"] = {"box_px": list(BAND_BOX), "concept_box_px": list(CON_BAND_BOX),
                "concept_front": hsv_stats(np.asarray(CON["front"].crop(CON_BAND_BOX)).reshape(-1, 3))}
VT = [("agx", "cobble_close_%s")] + [(v.lower().replace(" ", "_"), "cobvt_" + v.lower().replace(" ", "_") + "_close_%s")
                                     for v in P["review"]["h3"]["cobble"].get("view_transform_probe", [])]
for who in ("h21", "h3"):
    meas["band"]["%s_preview" % who] = hsv_stats(np.asarray(raw(who, "close_talons_3q").convert("RGB").crop(BAND_BOX)).reshape(-1, 3))
    for slug, pat in VT:
        f = RAW / ("%s_%s.png" % (who, pat % "talons_3q"))
        if f.exists():
            meas["band"]["%s_cobble_%s" % (who, slug)] = hsv_stats(
                np.asarray(Image.open(f).convert("RGB").crop(BAND_BOX)).reshape(-1, 3))
        f = RAW / ("%s_%s.png" % (who, pat % "face_game"))
        if f.exists() and slug != "agx":
            im = np.asarray(Image.open(f).convert("RGB"))[350:650, 350:650].reshape(-1, 3)
            meas["face_centre_roi"]["%s_cobble_%s" % (who, slug)] = hsv_stats(im)
    if REV1 is not None and (REV1 / ("%s_cobble_close_talons_3q.png" % who)).exists():
        f = REV1 / ("%s_cobble_close_talons_3q.png" % who)
        meas["band"]["%s_cobble_rev1" % who] = {"sha256": sha(f), **hsv_stats(
            np.asarray(Image.open(f).convert("RGB").crop(BAND_BOX)).reshape(-1, 3))}
# skin-like pixels (S 0.08-0.38, V > 0.5, hue 15-55): face close-ups rows 450-850, cols 250-750 (below the crest at
# the game pitch); concept: rows 0.30-0.44, cols 0.44-0.56 of harpy-front.png (mouth, chin, throat)


def skin_stats(a):
    px = a.reshape(-1, 3)
    f = px.astype(np.float64) / 255.0
    mx, mn = f.max(1), f.min(1)
    s_ = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0.0)
    d = np.maximum(mx - mn, 1e-9)
    r, g, b = f[:, 0], f[:, 1], f[:, 2]
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60.0
    m = (s_ > 0.08) & (s_ < 0.38) & (mx > 0.5) & (h > 15) & (h < 55)
    return {"pixels": int(m.sum()), **{k: v for k, v in hsv_stats(px[m]).items()
                                       if k in ("luma_p50", "S_p50", "V_p50", "mean_rgb", "bleached_frac")}}


cw, ch = CON["front"].size
meas["face_skin"] = {"def": "S 0.08-0.38, V > 0.5, hue 15-55 deg; close-ups rows 450-850 cols 250-750; concept rows "
                            "0.30-0.44 cols 0.44-0.56 of harpy-front.png",
                     "concept_front": skin_stats(np.asarray(CON["front"])[int(0.30 * ch):int(0.44 * ch),
                                                                          int(0.44 * cw):int(0.56 * cw)])}
for who in ("h21", "h3"):
    for key, name in [("preview", "close_face_game")] + [("cobble_" + slug, pat % "face_game") for slug, pat in VT]:
        f = RAW / ("%s_%s.png" % (who, name))
        if f.exists():
            meas["face_skin"]["%s_%s" % (who, key)] = skin_stats(np.asarray(Image.open(f).convert("RGB"))[450:850, 250:750])
    if REV1 is not None and (REV1 / ("%s_cobble_close_face_game.png" % who)).exists():
        f = REV1 / ("%s_cobble_close_face_game.png" % who)
        meas["face_skin"]["%s_cobble_rev1" % who] = {"sha256": sha(f), **skin_stats(
            np.asarray(Image.open(f).convert("RGB"))[450:850, 250:750])}
cal_probe = CAL.get("view_transform_probe", {})
meas["view_transform_probe"] = {"agx": {"exposure_offset_stops": CAL["exposure_offset_stops"],
                                        "k1_board_p50_final": CAL["k1_board_p50_final"]},
                                **{k: {x: v.get(x) for x in ("available", "exposure_offset_stops", "k1_board_p50_final")}
                                   for k, v in cal_probe.items()}}
# probe sheet: per view transform: concept talons | H2.1 talons | H3 talons | H3 face at the game pitch
rows_ = []
for slug, pat in VT:
    if not (RAW / ("h3_%s.png" % (pat % "talons_3q"))).exists():
        continue
    name = "AgX (main)" if slug == "agx" else next(v for v in cal_probe if v.lower().replace(" ", "_") == slug)
    off = CAL["exposure_offset_stops"] if slug == "agx" else cal_probe[name]["exposure_offset_stops"]
    panels = [concept_crop("front", CROPS["talons_3q"][1], (500, 500))]
    for who, what in (("h21", "talons_3q"), ("h3", "talons_3q"), ("h3", "face_game")):
        im = Image.open(RAW / ("%s_%s.png" % (who, pat % what))).convert("RGB").resize((500, 500), Image.LANCZOS)
        label(im, "%s %s | %s %+.2f EV" % (NAME[who], what, name, off))
        panels.append(im)
    rows_.append(row(panels))
if rows_:
    save(col(rows_), "cmp_h3_cobble_vt_probe.jpg")
(OUT / "cobble-measure-h3.json").write_text(json.dumps(meas, indent=1, ensure_ascii=False), encoding="utf-8")

store = {}
for f in sorted(RAW.glob("*.png")):
    store[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
(OUT / "frames-storage-h3.json").write_text(json.dumps({"raw_frames_dir": "work/h3-frames (not committed)",
                                                        "sha256": store, "sheets": written}, indent=1, sort_keys=True),
                                           encoding="utf-8")
print("COMPOSE_H3_OK", written)
