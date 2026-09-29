"""Stage `ld_accent` (system python + one headless Blender run): TeamAccent mask of Merlin (look-dev v2, 2026-09-30).

python lookdev_accent.py <lookdev profile.json> [--no-render]

User decision 2026-09-29 ("Accents + ring"): the hero keeps the concept colours (Merlin's robe stays BLUE); the team
colour goes to the ring / base and to the accents of the clothing. The W4-B TeamMask of H2.1 (all the blue wool,
~70 % of the figure) is DEPRECATED: it stays byte-identical in textures/ for the v1 MIs only.
Rules (profile lookdev.team_accent; positions and widths in the SOURCE frame of the H2.1 texel state, Tripo metres,
x 0.504853 = game metres), on the 4K state of lookdev_accent_state.py:
  belt        zone `belt` of ld_maps (leather waist band + hanging end); the bronze buckle (zone buckle) stays out
  hood_lining wool of the robe part above z_min (front of y_max) within width_m of the face / beard part (3D) and on
              the face side of the gold hood band (closer to the face than the nearest band texel by margin_m):
              the narrow lining round the face opening; the gold band itself and the outer hood stay out
  sleeve_hem  wool of the sleeve parts within width_m (3D) of the gold cuff band (8-connected embroidery components of
              >= band_component_min_texels 4K texels on that sleeve), both faces of the cuff shell (narrow outer
              strip + inner lining); the band itself and the rest of the sleeve stay blue. Rev 2 (review 2026-09-30):
              15 mm source instead of 35 mm, each sleeve <= 20 % of its wool core (Arthur rule, team-accent.md)
  robe_hem    rev 2: the edge of the robe hem - wool of the robe part below the gold hem band (lower than the nearest
              band texel by margin_m, band = embroidery components >= band_component_min_texels below band_z_max_m),
              within width_m (3D) of it, outer face only (normal . band normal >= normal_min): the strip between the
              hem band and the lower edge; the hem band itself and the robe above it stay blue
  soft edge   smoothstep over feather_m inside the width, normalised Gaussian (sigma blur_sigma_px 4K texels) inside
              the coverage, gutters = nearest covered texel, then x the dye-allowed zone weights (wool + belt): 0 on
              the embroidery, buckle, boots, beard wrap, skin, beard, wood, crystal and the base
TeamDyeGain: team-accent.md rule on the 2K look-dev BC. Frames: the dye of M_UM_Figure_v2
(dyed = lerp(BC x Team, Team x Y(BC) x TeamDyeGain, TeamDye); BC = lerp(BC, dyed, mask)) applied to the committed 2K
BC with P1 / P2 of the active C-11 palette; Blender EEVEE, light ~ Cobble calibrated to the W4-A anchor (board p50
131), K2 5x / 1.6x and close-ups (lookdev_accent_render.py); ID frames for the screen measurements.
Outputs: textures/T_Merlin_H2LD_TeamAccent_2K.png (+ _4K local), preview/ld_teamaccent_1K.png,
preview/ld_accent_*.jpg (sheets), reports/ld-accent-report.json, reports/ld-team-accent-ue.json (UE data of the next
wave), reports/ld-accent-cobble-calibration.json; raw frames in work/lookdev/accent/ (local).
"""

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import lookdev_accent_state as AS  # noqa: E402
import maps as M  # noqa: E402

LUM = np.array([0.2126, 0.7152, 0.0722])
ZONE_RGB = {"wool": (40, 60, 190), "embroidery": (250, 210, 40), "belt": (40, 200, 60), "buckle": (255, 30, 30),
            "boots": (30, 120, 30), "beard_wrap": (150, 250, 70), "face_skin": (255, 150, 110),
            "hands_skin": (210, 110, 90), "beard": (240, 240, 240), "wood": (110, 70, 30), "crystal": (20, 230, 255),
            "base": (90, 90, 95)}
ACCENT_RGB = (255, 0, 255)
NEVER = ("embroidery", "buckle", "boots", "beard_wrap", "face_skin", "hands_skin", "beard", "wood", "crystal", "base")
SETS = ("ld", "ld_p1", "ld_p2")
SET_LABEL = {"ld": "look-dev v2 без красителя", "ld_p1": "TeamAccent P1 #E8C06A", "ld_p2": "TeamAccent P2 #5A7F9F"}
FONT = "C:/Windows/Fonts/arial.ttf"


def smoothstep(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


def hex_lin(h):
    s = np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float64) / 255.0
    return M.srgb_decode(s)


def part_ids(names):
    return [C.part_index(n) for n in names]


# ------------------------------------------------------------------------------------------------ accent rules
def hood_lining(d, cfg):
    cov, part, pos, wool, emb = d["covered"], d["part"], d["pos"], d["zone_wool"], d["zone_embroidery"]
    reg = (cov & (part == C.part_index(cfg["part"])) & (pos[..., 2] > cfg["z_min_m"]) & (pos[..., 1] < cfg["y_max_m"]))
    face = cov & np.isin(part, part_ids(cfg["face_parts"]))
    tf = cKDTree(pos[face].astype(np.float64))
    band = reg & (emb >= float(cfg["band_emb_min"]))
    bd, _ = tf.query(pos[band].astype(np.float64), k=1)
    tb = cKDTree(pos[band].astype(np.float64))
    cand = reg & (wool > 0.5)
    df, _ = tf.query(pos[cand].astype(np.float64), k=1)
    _, jb = tb.query(pos[cand].astype(np.float64), k=1)
    face_side = bd[jb] >= df + float(cfg["margin_m"])
    w = smoothstep((float(cfg["width_m"]) - df) / float(cfg["feather_m"])) * face_side
    out = np.zeros(cov.shape, np.float32)
    out[cand] = w
    # clean-up (measured 2026-09-30, run 2): the face-side test flickers between the gold motifs of the band, which
    # left specks of accent in the band field and a ragged edge at the forehead. Components of the hard mask below
    # min_component_texels are dropped, holes are closed (close_px, only on wool of the region), soft edge kept.
    hard = out >= 0.5
    lab, _n = ndimage.label(hard, structure=np.ones((3, 3), bool))
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    keep = sz[lab] >= int(cfg["min_component_texels"])
    dropped = int((hard & ~keep).sum())
    grow = ndimage.binary_dilation(keep, iterations=int(cfg["close_px"]) + 1)
    closed = ndimage.binary_closing(keep, structure=np.ones((3, 3), bool), iterations=int(cfg["close_px"])) & cand
    out = np.where(closed & ~keep, 1.0, np.where(grow, out, 0.0)).astype(np.float32)
    info = {"band_texels_4k": int(band.sum()), "candidate_texels_4k": int(cand.sum()), "face_texels_4k": int(face.sum()),
            "components_kept": int(len(np.unique(lab[keep]))), "texels_dropped_small_components": dropped,
            "texels_filled_by_closing": int((closed & ~keep).sum())}
    return out, info


def sleeve_hem(d, cfg):
    cov, part, pos, wool, emb = d["covered"], d["part"], d["pos"], d["zone_wool"], d["zone_embroidery"]
    out = np.zeros(cov.shape, np.float32)
    info = {}
    for pn in cfg["parts"]:
        p = C.part_index(pn)
        e = cov & (part == p) & (emb >= float(cfg["band_emb_min"]))
        lab, _n = ndimage.label(e, structure=np.ones((3, 3), bool))
        sz = np.bincount(lab.ravel())
        sz[0] = 0
        band = sz[lab] >= int(cfg["band_component_min_texels"])
        tb = cKDTree(pos[band].astype(np.float64))
        cand = cov & (part == p) & (wool > 0.5)
        dd, _ = tb.query(pos[cand].astype(np.float64), k=1)
        out[cand] = smoothstep((float(cfg["width_m"]) - dd) / float(cfg["feather_m"]))
        comps = np.unique(lab[band])
        info[pn] = {"band_components": int(len(comps)), "band_texels_4k": int(band.sum()),
                    "component_texels": sorted((int(sz[c]) for c in comps), reverse=True)}
    return out, info


def robe_hem(d, cfg):
    cov, part, pos, nrm, wool, emb = d["covered"], d["part"], d["pos"], d["nrm"], d["zone_wool"], d["zone_embroidery"]
    reg = cov & (part == C.part_index(cfg["part"]))
    zmax = float(cfg["band_z_max_m"])
    e = reg & (emb >= float(cfg["band_emb_min"])) & (pos[..., 2] < zmax)
    lab, _n = ndimage.label(e, structure=np.ones((3, 3), bool))
    sz = np.bincount(lab.ravel())
    sz[0] = 0
    band = sz[lab] >= int(cfg["band_component_min_texels"])
    bp = pos[band].astype(np.float64)
    bn = d["nrm"][band].astype(np.float64)
    tb = cKDTree(bp)
    cand = reg & (wool > 0.5) & (pos[..., 2] < zmax + float(cfg["width_m"]))
    q = pos[cand].astype(np.float64)
    dd, j = tb.query(q, k=1)
    below = q[:, 2] < bp[j, 2] - float(cfg["margin_m"])
    agree = (nrm[cand].astype(np.float64) * bn[j]).sum(1) >= float(cfg["normal_min"])
    out = np.zeros(cov.shape, np.float32)
    out[cand] = smoothstep((float(cfg["width_m"]) - dd) / float(cfg["feather_m"])) * (below & agree)
    info = {"band_components": int(len(np.unique(lab[band]))), "band_texels_4k": int(band.sum()),
            "candidate_texels_4k": int(cand.sum()), "texels_below_and_outer_within_width": int((below & agree & (dd < float(cfg["width_m"]))).sum())}
    return out, info


def team_accent(d, tcfg):
    cov, part, area = d["covered"], d["part"], d["area"]
    belt = d["zone_" + tcfg["belt"]["zone"]].astype(np.float32)
    hood, hood_info = hood_lining(d, tcfg["hood_lining"])
    sleeve, sleeve_info = sleeve_hem(d, tcfg["sleeve_hem"])
    hem, hem_info = robe_hem(d, tcfg["robe_hem"])
    wool = d["zone_wool"]
    raw = np.maximum(belt, np.maximum(np.maximum(hood, sleeve), hem) * wool) * cov
    sig = float(tcfg["blur_sigma_px"])
    num = ndimage.gaussian_filter(raw.astype(np.float32), sig)
    den = ndimage.gaussian_filter(cov.astype(np.float32), sig)
    soft = np.where(cov, num / np.maximum(den, 1e-6), 0.0).astype(np.float32)
    _d, (jy, jx) = ndimage.distance_transform_edt(~cov, return_indices=True)
    soft = soft[jy, jx]
    allowed = np.clip(wool + belt, 0, 1)
    acc = np.clip(soft * allowed, 0, 1).astype(np.float32)
    base_p = C.part_index(tcfg["figure_excludes_part"])
    fig = cov & (part != base_p)
    fa = float(area[fig].sum())

    def share(w, m=None):
        m = fig if m is None else (fig & m)
        return C.r(float((w * area)[m].sum()) / fa, 4)

    comp = {"belt": np.minimum(acc, belt), "hood_lining": np.minimum(acc, hood), "sleeve_hem": np.minimum(acc, sleeve),
            "robe_hem": np.minimum(acc, hem)}
    info = {"share_3d_total": share(acc), "share_3d": {k: share(v) for k, v in comp.items()},
            "share_3d_by_part": {}, "hood_lining": hood_info, "sleeve_hem": sleeve_info, "robe_hem": hem_info,
            "texels_4k_ge_0_5": int((acc[cov] >= 0.5).sum()),
            "area_method": "texel area = 3D area of its UV triangle / the triangle's UV area in 4K texels (work/uv/*.npz "
                           "area3d_m2, source frame; a ratio, so the frame scale cancels); figure = body + staff, "
                           "without the base part"}
    for p in sorted(set(np.unique(part[fig]).tolist())):
        s = share(acc, part == p)
        if s > 0:
            info["share_3d_by_part"]["tripo_part_%d" % p] = s
    return acc, comp, info


def dye_gain(bc2_lin, acc2, tcfg, palette):
    """team-accent.md rule, evaluated per team (the MI of each team carries its own TeamDyeGain): gain_t =
    min(median_target / Y_p50, p95_max_albedo / (max channel of TeamColor_t x Y_p95)) over the accent texels
    (weight >= 0.5) of the 2K BC, Y clamped to y_clamp, rounded down to round_to."""
    rule = tcfg["team_dye_gain_rule"]
    y = np.clip(bc2_lin @ LUM, *rule["y_clamp"])
    sel = acc2 >= 0.5
    p50, p95 = float(np.percentile(y[sel], 50)), float(np.percentile(y[sel], 95))
    step = float(rule["round_to"])
    gains, by_team = {}, {}
    for k, v in palette.items():
        maxch = float(v.max())
        g = min(float(rule["median_target"]) / p50, float(rule["p95_max_albedo"]) / (maxch * p95))
        gains[k] = float(np.floor(g / step) * step)
        by_team[k] = {"team_max_channel_linear": C.r(maxch, 4), "gain_unrounded": C.r(g, 3), "team_dye_gain": gains[k],
                      "median_dyed_albedo_over_team": C.r(gains[k] * p50, 3),
                      "p95_dyed_max_channel": C.r(gains[k] * p95 * maxch, 3),
                      "bound_by": "median" if float(rule["median_target"]) / p50 <= float(rule["p95_max_albedo"]) / (maxch * p95) else "p95"}
    common = min(gains.values())
    return gains, {"accent_texels_2k_ge_0_5": int(sel.sum()), "Y_p50": C.r(p50, 4), "Y_p95": C.r(p95, 4),
                   "by_team": by_team, "one_gain_for_both_teams_would_be": common,
                   "note": "per team: the p95 condition is on the dyed albedo = TeamColor x Y x gain, so it depends on the "
                           "team colour; one gain for both (the brightest channel of the palette, P1) would leave the P2 "
                           "accent at %.2f x TeamColor (median) - measured 2026-09-30: dE P2 accent vs the blue wool "
                           "6-13 at K2" % (common * p50)}


def dye(bc_lin, mask, team, gain, dye_amount):
    y = bc_lin @ LUM
    teamed = (1 - dye_amount) * (bc_lin * team) + dye_amount * (team[None, None, :] * y[..., None] * gain)
    return bc_lin + (teamed - bc_lin) * mask[..., None]


# ------------------------------------------------------------------------------------------------ frame metrics
def load_img(path):
    return np.asarray(Image.open(path).convert("RGB"), np.float64) / 255.0


def lab(rgb):
    li = M.srgb_decode(rgb)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = li @ m.T / np.array([0.9505, 1.0, 1.089])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def cmask(img, rgb, tol=3):
    return np.abs(img * 255.0 - np.array(rgb)).sum(axis=2) <= tol


def blue_share(img, mask, hue=(200.0, 265.0), s_min=0.2):
    h, s, _v = M.rgb_to_hsv(img)
    b = (h >= hue[0]) & (h <= hue[1]) & (s >= s_min)
    return float(b[mask].mean())


def frame_metrics(rdir, views):
    out = {}
    for v in views:
        a = load_img(rdir / "id" / "accent" / (v + ".png"))
        z = load_img(rdir / "id" / "zones" / (v + ".png"))
        acc = cmask(a, ACCENT_RGB)
        fig = np.zeros(acc.shape, bool)
        for k, rgb in ZONE_RGB.items():
            if k != "base":
                fig |= cmask(z, rgb)
        wool = cmask(z, ZONE_RGB["wool"])
        emb = ndimage.binary_erosion(cmask(z, ZONE_RGB["embroidery"]), iterations=1)
        near = ndimage.binary_dilation(acc, iterations=6) & wool & ~acc
        acc_e = ndimage.binary_erosion(acc, iterations=1)
        wool_e = ndimage.binary_erosion(wool, iterations=1)
        e = {"accent_px": int(acc.sum()), "figure_px_without_base": int(fig.sum()),
             "screen_share_of_figure": C.r(float(acc.sum()) / max(int(fig.sum()), 1), 4),
             "wool_px": int(wool_e.sum()), "embroidery_px": int(emb.sum())}
        imgs = {s: load_img(rdir / "cobble" / s / (v + ".png")) for s in SETS}
        labs = {s: lab(im) for s, im in imgs.items()}
        mean_acc = {}
        for s in SETS:
            L = labs[s]
            ent = {"blue_share_of_wool_px": C.r(blue_share(imgs[s], wool_e), 4)}
            if acc_e.sum() >= 20 and near.sum() >= 20:
                ma, mn = L[acc_e].mean(0), L[near].mean(0)
                mean_acc[s] = ma
                ent.update({"accent_lab": C.rv(ma, 1), "wool_next_to_it_lab": C.rv(mn, 1),
                            "delta_e_accent_vs_wool": C.r(float(np.linalg.norm(ma - mn)), 1)})
            if s != "ld":
                de = np.linalg.norm(L - labs["ld"], axis=-1)
                ent["embroidery_delta_e_vs_no_dye_p50_p95"] = C.rv(np.percentile(de[emb], [50, 95]), 2) if emb.any() else None
                ent["wool_outside_accent_delta_e_vs_no_dye_p50_p95"] = C.rv(
                    np.percentile(de[wool_e & ~ndimage.binary_dilation(acc, iterations=2)], [50, 95]), 2)
                ent["blue_share_ratio_vs_no_dye"] = C.r(blue_share(imgs[s], wool_e) / max(blue_share(imgs["ld"], wool_e), 1e-6), 4)
            e[s] = ent
        if "ld_p1" in mean_acc and "ld_p2" in mean_acc:
            e["delta_e_p1_vs_p2"] = C.r(float(np.linalg.norm(mean_acc["ld_p1"] - mean_acc["ld_p2"])), 1)
        # pixels the dye changes (any channel > 8 levels), share of the figure
        for s in ("ld_p1", "ld_p2"):
            ch = (np.abs(imgs[s] - imgs["ld"]).max(-1) * 255 > 8) & fig
            e[s]["changed_px_share_of_figure"] = C.r(float(ch.sum()) / max(int(fig.sum()), 1), 4)
        out[v] = e
    return out


# ------------------------------------------------------------------------------------------------ sheets
def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def label(im, text, size=14):
    bar = size + 12
    out = Image.new("RGB", (im.width, im.height + bar), (18, 18, 20))
    out.paste(im, (0, bar))
    ImageDraw.Draw(out).text((8, 5), text, fill=(235, 220, 120), font=font(size))
    return out


def hstack(imgs, gap=6):
    h = max(i.height for i in imgs)
    out = Image.new("RGB", (sum(i.width for i in imgs) + gap * (len(imgs) - 1), h), (18, 18, 20))
    x = 0
    for i in imgs:
        out.paste(i, (x, 0))
        x += i.width + gap
    return out


def vstack(imgs, gap=6):
    w = max(i.width for i in imgs)
    out = Image.new("RGB", (w, sum(i.height for i in imgs) + gap * (len(imgs) - 1)), (18, 18, 20))
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + gap
    return out


def save_jpg(img, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.convert("RGB").save(path, "JPEG", quality=90, optimize=False, subsampling=0)
    return {"file": C.rel(path), "sha256": C.sha256(path), "bytes": path.stat().st_size}


def fig_box(rdir, v, margin=0.12):
    z = load_img(rdir / "id" / "zones" / (v + ".png"))
    fig = np.zeros(z.shape[:2], bool)
    for rgb in ZONE_RGB.values():
        fig |= cmask(z, rgb)
    ys, xs = np.nonzero(fig)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    mx, my = (x1 - x0) * margin, (y1 - y0) * margin
    return (int(max(x0 - mx, 0)), int(max(y0 - my, 0)), int(min(x1 + mx, z.shape[1])), int(min(y1 + my, z.shape[0])))


def fit(im, h, nearest=False):
    return im.resize((round(im.width * h / im.height), h), Image.NEAREST if nearest else Image.LANCZOS)


def sheets(prof, src, rdir, gain):
    out = {}
    pv = prof.preview
    rows = []
    for v, cview in (("k2_5x_az0", "front"), ("k2_5x_az180", "back")):
        box = fig_box(rdir, v)
        cells = [label(fit(Image.open(C.repo_path(src["concepts"][cview])).convert("RGB"), 620), "концепт H2 · %s" % cview)]
        for s in SETS:
            cells.append(label(fit(Image.open(rdir / "cobble" / s / (v + ".png")).convert("RGB").crop(box), 620),
                               "blender · Cobble · %s · %s" % (SET_LABEL[s], v)))
        rows.append(hstack(cells))
    note = ("blender EEVEE (НЕ UE) · K2 5× (386 uu, FOV 35, pitch −55) · свет ≈ Cobble, экспозиция по якорю W4-A "
            "(K1 доска p50 131) · кроп по фигуре · краситель v2: TeamDye 1, TeamDyeGain P1 %s / P2 %s" % (gain["P1"], gain["P2"]))
    out["k2_5x"] = save_jpg(label(vstack(rows), note, 16), pv / "ld_accent_k2_5x_cobble.jpg")
    rows = []
    for v in ("k2_5x_az-40", "k2_1p6_az0", "k2_1p6_az180"):
        box = fig_box(rdir, v)
        nearest = v.startswith("k2_1p6")
        rows.append(hstack([label(fit(Image.open(rdir / "cobble" / s / (v + ".png")).convert("RGB").crop(box), 520, nearest),
                                  "blender · Cobble · %s · %s" % (SET_LABEL[s], v)) for s in SETS]))
    out["k2_more"] = save_jpg(label(vstack(rows), "blender (НЕ UE) · K2 5× азимут −40 и K2 1,6× (увеличение nearest ×~4)", 16),
                              pv / "ld_accent_k2_more_cobble.jpg")
    rows = []
    for v in ("close_hood_az0", "close_torso_az0", "close_back_az180"):
        rows.append(hstack([label(fit(Image.open(rdir / "cobble" / s / (v + ".png")).convert("RGB"), 520),
                                  "blender · Cobble · %s · %s" % (SET_LABEL[s], v)) for s in SETS]))
    out["closeups"] = save_jpg(label(vstack(rows), "blender (НЕ UE) · крупные планы, орто, свет ≈ Cobble", 16),
                               pv / "ld_accent_closeups_cobble.jpg")
    cells = []
    for v in ("k2_5x_az0", "k2_5x_az180", "close_hood_az0", "close_torso_az0", "close_back_az180"):
        box = fig_box(rdir, v) if v.startswith("k2") else None
        for lab_ in ("zones", "accent"):
            im = Image.open(rdir / "id" / lab_ / (v + ".png")).convert("RGB")
            if box:
                im = im.crop(box)
            cells.append(label(fit(im, 440, nearest=True), "ID %s · %s" % (lab_, v), 12))
    out["id"] = save_jpg(vstack([hstack(cells[:4]), hstack(cells[4:])]), pv / "ld_accent_id.jpg")
    return out


# ------------------------------------------------------------------------------------------------ main
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    no_render = "--no-render" in sys.argv
    prof = C.Profile(args[0])
    src = C.Profile(C.repo_path(prof["lookdev"]["source_profile"]))
    ld = prof["lookdev"]
    tcfg = ld["team_accent"]
    px = ld["prefix"]
    checks = {}
    d, cache_info = AS.load(prof, src)
    C.check(checks, "h21_state_reproduced", bool(d["h21_reproduced"]), {"state_key": cache_info["key"]},
            True, "the 4K state = the H2.1 4K masters (lookdev_state.check_against_h21), as ld_maps")
    # the zone weights of the state are those of ld_maps: hard zone ids equal work/lookdev/state.npz of ld_maps
    zs = np.load(prof.work / "lookdev" / "state.npz")
    order = ld["zones"]["order"]
    zid = np.argmax(np.stack([d["zone_" + k] for k in order], 0), 0).astype(np.uint8)
    C.check(checks, "zones_equal_ld_maps", bool(np.array_equal(zid, zs["zone_id"])),
            int((zid != zs["zone_id"]).sum()), 0, "hard zone ids of this stage vs work/lookdev/state.npz of ld_maps")
    cov, part = d["covered"], d["part"]
    acc, comp, info = team_accent(d, tcfg)
    lo, hi = tcfg["area_share_range"]
    C.check(checks, "team_accent_area_share", lo <= info["share_3d_total"] <= hi,
            {"total": info["share_3d_total"], **info["share_3d"]}, [lo, hi],
            "share of the figure's 3D surface (body + staff, no base)")
    er = {k: (d["zone_" + k] >= 0.999) & ndimage.binary_erosion(zid == order.index(k), iterations=2) & cov for k in order}
    acc8_4k = M.to8(acc)
    leak = {k: int(acc8_4k[er[k]].max()) if er[k].any() else 0 for k in NEVER}
    C.check(checks, "team_accent_zero_outside_wool_and_belt", all(v == 0 for v in leak.values()), leak,
            "0 (8-bit, 4K) on the core texels of the embroidery, buckle, boots, beard wrap, skin, beard, wood, crystal, base")
    # the robe stays blue, per part (a mean over parts hides a part dyed for the most part: Arthur review 2026-09-29)
    per_part = {}
    for pn, lim in tcfg["blue_parts_max_core_share"].items():
        m = er["wool"] & (part == C.part_index(pn))
        share = float((acc[m] >= 0.5).mean())
        per_part[pn] = {"wool_core_texels_4k": int(m.sum()), "accent_ge_0_5_share": C.r(share, 4), "max": lim}
    C.check(checks, "robe_stays_blue_per_part", all(v["accent_ge_0_5_share"] <= v["max"] for v in per_part.values()),
            per_part, "<= max per part", "share of the wool core texels of each cloth part that carry the accent (>= 0.5)")
    info["wool_core_share_by_part"] = per_part
    # textures
    tex = prof.textures
    a2 = M.box2(acc)
    out = {"TeamAccent_4K": M.save_png(tex / ("%s_TeamAccent_4K.png" % px), acc8_4k, "L"),
           "TeamAccent_2K": M.save_png(tex / ("%s_TeamAccent_2K.png" % px), M.to8(a2), "L")}
    lm = C.load_json(prof.reports / "ld-maps-report.json")["textures"]
    tm_ok = {k: C.sha256(tex / ("%s_%s.png" % (px, k))) == lm[k]["sha256"] for k in ("TeamMask_2K", "TeamMaskRGBA_2K", "MatID_2K")}
    C.check(checks, "deprecated_team_mask_unchanged", all(tm_ok.values()), tm_ok, True,
            "TeamMask / TeamMaskRGBA / MatID 2K = the ld_maps outputs (sha256): the deprecated mask is kept for the v1 MIs")
    # read-only: geometry, rig, UV (the FBX pair of ld_export) and the other look-dev maps are those of the run
    ex = C.load_json(prof.reports / "ld-export-report.json")["exports"]
    tr = C.load_json(prof.reports / "textures-report.json")["textures"]
    ro = {"SK_fbx": C.sha256(prof.export / ld["exports"]["skeletal_fbx"]) == ex["skeletal_fbx"]["sha256"],
          "SM_fbx": C.sha256(prof.export / ld["exports"]["base_fbx"]) == ex["base_fbx"]["sha256"]}
    for k in ("BC_2K", "N_2K", "ORM_2K", "MatID_2K", "TeamMask_2K", "TeamMaskRGBA_2K"):
        ro[k] = C.sha256(tex / ("%s_%s.png" % (px, k))) == tr["%s_%s.png" % (px, k)]["sha256"]
    ro["atlas_coverage_equals_h21_raster"] = bool(np.array_equal(cov, d["tri"] >= 0))
    C.check(checks, "geometry_rig_uv_and_maps_read_only", all(ro.values()), ro, True,
            "export FBX (geometry, rig UM_HUMANOID_17_v2, UV0 + UV1) = ld-export-report sha256; BC/N/ORM/MatID/TeamMask* 2K = "
            "textures-report sha256; the accent lives on UV0 texels of the H2.1 atlas raster")
    # dye gain on the committed 2K BC (the texture the MI samples)
    with Image.open(tex / ("%s_BC_2K.png" % px)) as im:
        bc2_8 = np.flipud(np.asarray(im)).copy()
    bc2 = M.srgb_decode(bc2_8.astype(np.float64) / 255.0)
    a2q = M.to8(a2).astype(np.float64) / 255.0
    masters = C.load_json(C.repo_path(tcfg["palette"]["masters"]))["team_palette"]
    pal_src = masters[masters["active"]]
    palette = {"P1": hex_lin(pal_src["Gold"]), "P2": hex_lin(pal_src["Silver"])}
    C.check(checks, "palette_is_c11_active", pal_src["Gold"].upper() == tcfg["palette"]["P1"] and pal_src["Silver"].upper() == tcfg["palette"]["P2"],
            {"active": masters["active"], "P1": pal_src["Gold"], "P2": pal_src["Silver"]}, [tcfg["palette"]["P1"], tcfg["palette"]["P2"]])
    gain, gain_info = dye_gain(bc2, a2q, tcfg, palette)
    # frame sets (2K, image row 0 = top as the PNG)
    wk = prof.work / "lookdev" / "accent"
    sets = {"ld": {k: str(tex / ("%s_%s_2K.png" % (px, k))) for k in ("BC", "ORM", "N")}}
    for key, tk in (("ld_p1", "P1"), ("ld_p2", "P2")):
        bc = dye(bc2, a2q, palette[tk], gain[tk], float(tcfg["team_dye"]))
        bc8 = M.to8(M.srgb_encode(bc))
        bc8[a2q == 0] = bc2_8[a2q == 0]  # no accent: the committed BC bytes exactly
        p = wk / "sets" / key / "BC.png"
        M.save_png(p, bc8, "RGB")
        sets[key] = dict(sets["ld"], BC=str(p))
    zid2 = np.argmax(np.stack([M.box2(d["zone_" + k]) for k in order], 0), 0)
    zrgb = np.array([ZONE_RGB[k] for k in order], np.uint8)[zid2]
    arg = zrgb.copy()
    arg[a2 >= 0.5] = ACCENT_RGB
    ids = {"zones": wk / "id" / "zones.png", "accent": wk / "id" / "accent.png"}
    M.save_png(ids["zones"], zrgb, "RGB")
    M.save_png(ids["accent"], arg, "RGB")
    # atlas preview
    bcs = M.srgb_encode(M.box2(bc2))
    av = M.box2(a2)[..., None] * 0.85
    prev = {"accent_atlas": M.save_png(prof.preview / "ld_teamaccent_1K.png", M.to8(bcs * (1 - av) + np.array([1.0, 0.0, 1.0]) * av), "RGB")}
    fcfg = tcfg["frames"]
    views = ["k2_%s_az%d" % (t, a) for t in fcfg["k2_distance_uu"] for a in fcfg["k2_azimuths"]] + list(fcfg["closeups"])
    rdir = wk / "render"
    job = {"out": str(rdir), "sets": sets, "views": views, "id_sets": {k: str(v) for k, v in ids.items()},
           "id_views": views, "calibrate": not (prof.reports / "ld-accent-cobble-calibration.json").exists()}
    C.write_json(wk / "render-job.json", job)
    frames = sheet_out = None
    if not no_render:
        log = prof.run_dir / "logs" / "ld_accent_render.log"
        with open(log, "wb") as fh:
            rc = subprocess.run([prof["blender"], "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                                 str(Path(__file__).resolve().parent / "lookdev_accent_render.py"), "--", str(prof.path),
                                 str(wk / "render-job.json")], stdout=fh, stderr=subprocess.STDOUT,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).returncode
        if rc:
            raise SystemExit("lookdev_accent_render.py failed, see %s" % log)
        cal = C.load_json(prof.reports / "ld-accent-cobble-calibration.json")
        C.check(checks, "cobble_exposure_calibrated", bool(cal["passed"]),
                {"k1_board_p50": cal["k1_board_p50_final"], "exposure_offset_stops": cal["exposure_offset_stops"]},
                "|p50 - 131.2| <= 0.75")
        frames = frame_metrics(rdir, [v for v in views if v.startswith("k2")] + ["close_hood_az0", "close_torso_az0", "close_back_az180"])
        rd = fcfg["readability"]
        k2 = [v for v in rd["views"] if "delta_e_accent_vs_wool" in frames[v]["ld_p1"]]
        min_de = min(frames[v][s]["delta_e_accent_vs_wool"] for v in k2 for s in ("ld_p1", "ld_p2"))
        min_pp = min(frames[v]["delta_e_p1_vs_p2"] for v in k2)
        min_sh = min(frames[v]["screen_share_of_figure"] for v in rd["views"])
        C.check(checks, "team_accent_reads_at_k2", min_de >= rd["min_delta_e_accent_vs_wool"] and min_pp >= rd["min_delta_e_p1_vs_p2"]
                and min_sh >= rd["min_screen_share"],
                {"views": rd["views"], "min_delta_e_accent_vs_wool": min_de, "min_delta_e_p1_vs_p2": min_pp,
                 "min_screen_share_of_figure": min_sh},
                {"delta_e_accent_vs_wool": ">= %s" % rd["min_delta_e_accent_vs_wool"], "delta_e_p1_vs_p2": ">= %s" % rd["min_delta_e_p1_vs_p2"],
                 "screen_share": ">= %s" % rd["min_screen_share"]}, "CIELAB of the Cobble frames; accent / wool pixels from the ID frames")
        ratios = {v: [frames[v][s]["blue_share_ratio_vs_no_dye"] for s in ("ld_p1", "ld_p2")] for v in rd["views"]}
        C.check(checks, "robe_stays_blue_in_render", all(min(r) >= rd["blue_share_min_ratio"] for r in ratios.values()), ratios,
                ">= %s" % rd["blue_share_min_ratio"], "blue share of all wool-ID pixels (accent included) with P1 / P2 vs without dye")
        emb = {v: [frames[v][s]["embroidery_delta_e_vs_no_dye_p50_p95"][0] for s in ("ld_p1", "ld_p2")] for v in rd["views"]}
        C.check(checks, "embroidery_not_dyed_in_render", all(max(e) <= rd["embroidery_max_median_delta_e"] for e in emb.values()), emb,
                "median <= %s" % rd["embroidery_max_median_delta_e"], "ΔE of the gold embroidery pixels (ID, eroded 1 px) dyed vs no dye")
        sheet_out = sheets(prof, src, rdir, gain)
    ue = ue_data(prof, tcfg, out, gain, gain_info, palette)
    C.write_json(prof.reports / "ld-team-accent-ue.json", ue)
    report = {"stage": "ld_accent", "profile": C.rel(prof.path), "profile_id": prof["profile_id"],
              "rules": {k: tcfg[k] for k in ("belt", "hood_lining", "sleeve_hem", "robe_hem", "blur_sigma_px")},
              "team_accent": info, "dye": {"team_dye": tcfg["team_dye"], "team_dye_gain": gain, "gain_rule": gain_info,
                                           "palette_active": masters["active"],
                                           "palette_linear": {k: C.rv(v, 4) for k, v in palette.items()}},
              "textures": out, "previews": prev, "sheets": sheet_out, "frames": frames,
              "frames_note": "raw frames in work/lookdev/accent/render (local); the dye is the v2 formula applied to the "
                             "2K BC; Principled BSDF, not the M_UM_Figure_v2 core; Blender EEVEE, not UE",
              "conventions": {"TeamAccent": "L8 linear (UE TC_Grayscale, sRGB off, mips on): 0 = concept colour, 1 = "
                                            "full team dye; goes into the TeamMaskTexture slot of the v2 MI",
                              "TeamMask": "L8 = H2.1 cloth (all the blue wool): DEPRECATED, kept byte-identical for the v1 MIs",
                              "TeamMaskRGBA": "R = TeamMask (deprecated), G base band, B embroidery, A EdgeMask: unchanged"},
              "checks": checks, "passed": all(c["passed"] for c in checks.values())}
    C.write_json(prof.reports / "ld-accent-report.json", report)
    print("H2_STAGE_OK ld_accent passed=%s share=%s gain=%s" % (report["passed"], info["share_3d_total"], gain))  # noqa
    if not report["passed"]:
        print("failed:", sorted(k for k, c in checks.items() if not c["passed"]))
        sys.exit(1)


def ue_data(prof, tcfg, out, gain, gain_info, palette):
    px = prof["lookdev"]["prefix"]
    return {
        "schema": "unmatched.merlin-lookdev.team-accent-ue/1", "status": "proposed (data of the next UE wave; UE not touched)",
        "texture": {"file": out["TeamAccent_2K"]["path"], "sha256": out["TeamAccent_2K"]["sha256"],
                    "ue_asset": "/Game/PipelineCandidates/Merlin/H2LD/%s_TeamAccent" % px,
                    "settings": {"CompressionSettings": "TC_Grayscale", "SRGB": False, "MipGenSettings": "FromTextureGroup",
                                 "Filter": "Default"}},
        "mi_parameters": {"TeamMaskTexture": "%s_TeamAccent" % px, "TeamDye": float(tcfg["team_dye"]), "TeamDyeGain": gain,
                          "TeamDyeGain_note": "per team MI: P1 (gold) and P2 (steel blue) differ, both by the same rule",
                          "TeamColor": {k: C.rv(v, 4) for k, v in palette.items()},
                          "team_dye_gain_rule": gain_info,
                          "note": "the MIs of the H2LD import (Neutral / Blue / Red; P1 / P2 of the active palette): the "
                                  "TeamMaskTexture slot takes TeamAccent instead of the deprecated TeamMask; TeamDyeGain by the "
                                  "team-accent.md rule"},
        "master_change": {
            "file": "tools/art/material_library/ue/um_v2_core.hlsl (M_UM_Figure_v2), next UE wave",
            "now": "class >= 1: bc = lerp(bc, dyed, TeamMask * L7.a)  (L7.a = teamDyeAllowed of the class); class 0: lerp(bc, teamed, TeamMask)",
            "proposed": "bc = lerp(bc, dyed, TeamAccent) for every class: the dye is decided by the TeamAccent texture alone (static switch "
                        "UseTeamAccent, default on for the v2 heroes; off = the current TeamMask x teamDyeAllowed path for the v1 MIs). "
                        "teamDyeAllowed stays in the LUT as a data rule of the mask authoring (the accent is 0 on metal, skin, "
                        "embroidery - checked in ld-accent-report), not as a shader gate",
            "why": "with TeamMask x teamDyeAllowed a class decides the dye: Merlin's wool_coarse is teamDyeAllowed = 1, so the W4-B "
                   "TeamMask dyed the whole robe; and the belt (leather_worn, teamDyeAllowed = 0 in the Merlin LUT) could never "
                   "carry the accent. TeamAccent carries exactly the accent texels"},
        "lut_if_master_unchanged": {
            "leather_worn": {"teamDyeAllowed": True,
                             "why": "only if the master keeps the class gate: the belt (leather_worn) must be allowed; the boots and the "
                                    "beard wrap are leather_worn too but TeamAccent is 0 there (check team_accent_zero_outside_wool_and_belt)"},
            "wool_coarse": {"teamDyeAllowed": True, "why": "unchanged (1): the robe stays blue because TeamAccent is 0 outside the accents"},
            "silk": {"teamDyeAllowed": False, "why": "unchanged: the gold embroidery is never dyed"},
            "note": "not written into build-profiles/merlin-h2-lookdev-ue-lut.json or ld-lut.json (UE wave input, not touched here)"},
        "deprecated": {"TeamMask": "%s_TeamMask_2K.png (all the blue wool, 65.7 %% of the figure, 3D): v1 MIs only" % px,
                       "TeamMaskRGBA.R": "same as TeamMask"}}


if __name__ == "__main__":
    main()
