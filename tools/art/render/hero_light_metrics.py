#!/usr/bin/env python3
"""ENV-MAPS P9b hero light gates D1-D6 + H2 (docs/art-pipeline/ENV-HERO-LIGHT.md, «Ревизия после ревью 2026-10-02»).

The P9 hero light was tuned on gate H1 (brightness) and over-lit the figures (ACES shoulder: beige harpies, cream
pedestals, flat relief). These gates measure readability instead: the light may only ADD an accent, never flatten the
form, wash the colours or clip.

Frames: editor / packaged -game -Bench SHOTs (bench-<view>-1920x1080.png) of the same board / views rendered
  off      -NoHeroLight (the reference without the hero light)
  on       the light under test (P9, P9b, ...)
  maskbody a measurement override (-ArtBoardProfiles=...) with a GREEN coaxial key + green rim, litPedestal false
  maskfig  the same with the pedestal lit (P9 code: the pedestal was always on channel 1)
  idle     (optional, K2 views) the light under test with activeMul 1 (the control for D5)
Masks: the green light changes almost only G, so mask = dG > 20 and dG > 2 max(dR, dB) (Niagara fire / water noise between
runs changes R >= G and stays out; 20, not 8: the 50 lux green mask light blooms a few px onto the board - the UE5 bloom has
no threshold - and a threshold of 8 took that halo in); components < 80 px dropped, closed, holes filled; near-white label / HP text pixels of
the off frame (min channel >= 200, chroma <= 30, dilated 1 px) removed. body = maskbody, figure = maskfig (body +
pedestal), pedestal = figure minus the dilated body. The masks never depend on the light under test.

Gates (luma Y = Rec.709 weights on the sRGB 0..255 values, as in the review):
  D1 detail      mean |Laplacian(Y)| / mean Y over the body interior (body eroded 1 px): on / off >= 1.0 (no flattening)
  D2 colour      mean HSV saturation over the body: on / off >= 0.97
  D3 clipping    share of figure pixels (body + pedestal) the light clips: max(R, G, B) >= 245 with it and < 245
                 without (labels / a Niagara fire in front of a figure are clipped in both frames) <= 0.5 %
  D4 accent      K1 only: mean Y gain over the body +15..+35 %, and the silhouette edge contrast (mean Y of the band
                 2..4 px inside the body / mean Y of the band 2..4 px outside it) on / off >= 1.15
  D5 active      K2 views (the bench selects the viewer's hero = the body component nearest the frame centre):
                 hero-light luma gain of the active hero / the same hero's gain in the idle control run (activeMul 1)
                 within 1.08..1.2
  D6 fidelity    K2x2.5, per named figure (--d6 config: reference studio renders of the detailed Tripo models, zone
                 rectangles, the figures' frame positions): body pixels are classified into the reference zones from
                 the off frame (grey-world balanced to the reference), pedestal = geometry. Per zone the median colour
                 of each frame, exposure-normalised (the figure's linear luminance scaled to the reference's: brightness
                 may differ) -> Lab. Gate (the coordinator's rule: hue / chroma + the relative value ORDER): mean
                 dABnorm (a*b* distance to the reference zone) of the light < that of the baseline (P9), and the zone L
                 order / chroma order agreement with the reference (pairs > 8 apart) not lower than the baseline's.
                 Reported too: dE76 raw (the night frame vs the studio render) and dEnorm (with the relative L).
  H2 spill       outside the figure masks dilated 12 px: mean |dY| (on - off) <= 0.5 and mean signed dY within +-1

  python tools/art/render/hero_light_metrics.py measure --off <run> --on <run> --mask-body <run> --mask-fig <run>
      [--idle <run>] [--baseline <P9 run> --d6 <config.json> --board <name>] [--json <out>] [--label <text>]
  python tools/art/render/hero_light_metrics.py --check        (self-test on synthetic images, no frames needed)
Status: «измерено» numbers only; «художественно принято» is the user's decision.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

W709 = np.array([0.2126, 0.7152, 0.0722])
VIEWS = ("K1", "K2x1p6", "K2x2p5")
THRESHOLDS = {
    "maskDiff": 20.0, "maskMinArea": 80, "D1": 1.0, "D2": 0.97, "D3pct": 0.5, "D3level": 245,
    "D4gain": (0.15, 0.35), "D4edge": 1.15, "D4band": (2.0, 4.0), "D5": (1.08, 1.2), "H2out": 0.5, "H2signed": 1.0,
    "H2dilate": 12,
}


# ---------------------------------------------------------------- images / colour

def load(path) -> np.ndarray:
    from PIL import Image
    return np.asarray(Image.open(path).convert("RGB")).astype(np.float64)


def luma(img: np.ndarray) -> np.ndarray:
    return img @ W709


def saturation(img: np.ndarray) -> np.ndarray:
    mx, mn = img.max(-1), img.min(-1)
    return np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0.0)


def srgb_to_linear(c: np.ndarray) -> np.ndarray:
    c = np.clip(c / 255.0, 0.0, 1.0)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def linear_to_lab(lin: np.ndarray) -> np.ndarray:
    m = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > (6 / 29) ** 3, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def srgb_to_lab(c: np.ndarray) -> np.ndarray:
    return linear_to_lab(srgb_to_linear(np.asarray(c, dtype=np.float64)))


# ---------------------------------------------------------------- masks

def green_mask(lit: np.ndarray, off: np.ndarray, diff: float = THRESHOLDS["maskDiff"],
               min_area: int = THRESHOLDS["maskMinArea"]) -> np.ndarray:
    """Pixels a green (channel-1-only) light changed: dG > diff and dG > 2 max(dR, dB, 0)."""
    d = lit - off
    dr, dg, db = d[..., 0], d[..., 1], d[..., 2]
    m = (dg > diff) & (dg > 2.0 * np.maximum(dr, 0.0)) & (dg > 2.0 * np.maximum(db, 0.0))
    m = ndimage.binary_closing(m, iterations=1)
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        keep = np.zeros(n + 1, bool)
        keep[1:] = sizes >= min_area
        m = keep[lab]
    return ndimage.binary_fill_holes(m)


def label_pixels(off: np.ndarray) -> np.ndarray:
    """Near-white name / HP text of the off frame (the hero light never reaches the labels: channel 0)."""
    t = (off.min(-1) >= 200) & ((off.max(-1) - off.min(-1)) <= 30)
    return ndimage.binary_dilation(t, iterations=1)


def build_masks(off: np.ndarray, maskbody: np.ndarray, maskfig: np.ndarray | None) -> dict:
    labels = label_pixels(off)
    body = green_mask(maskbody, off) & ~labels
    fig = (green_mask(maskfig, off) & ~labels) | body if maskfig is not None else body.copy()
    ped = fig & ~ndimage.binary_dilation(body, iterations=1)
    ped = ndimage.binary_opening(ped, iterations=1)
    return {"body": body, "fig": fig, "ped": ped, "labels": labels}


def band_inside(mask: np.ndarray, lo: float, hi: float) -> np.ndarray:
    d = ndimage.distance_transform_edt(mask)
    return mask & (d >= lo) & (d <= hi)


def band_outside(mask: np.ndarray, lo: float, hi: float) -> np.ndarray:
    d = ndimage.distance_transform_edt(~mask)
    return ~mask & (d >= lo) & (d <= hi)


def components(mask: np.ndarray, min_area: int = 400) -> list[np.ndarray]:
    lab, n = ndimage.label(mask)
    out = []
    for i in range(1, n + 1):
        c = lab == i
        if c.sum() >= min_area:
            out.append(c)
    return out


def component_at(mask: np.ndarray, xy, min_area: int = 200, max_dist: float = 120.0):
    """The body component containing / nearest the point (x, y) (None when farther than max_dist)."""
    best, best_d = None, max_dist
    for c in components(mask, min_area):
        if c[int(xy[1]), int(xy[0])]:
            return c
        ys, xs = np.nonzero(c)
        d = float(np.min(np.hypot(xs - xy[0], ys - xy[1])))
        if d < best_d:
            best, best_d = c, d
    return best


# ---------------------------------------------------------------- per-view metrics

def detail(y: np.ndarray, region: np.ndarray) -> float:
    lap = np.abs(ndimage.laplace(y))
    return float(lap[region].mean() / max(y[region].mean(), 1e-6))


def view_metrics(off: np.ndarray, on: np.ndarray, masks: dict, view: str, idle: np.ndarray | None = None) -> dict:
    T = THRESHOLDS
    body, fig = masks["body"], masks["fig"]
    yo, yn = luma(off), luma(on)
    interior = ndimage.binary_erosion(body, iterations=1)
    r = {"bodyPx": int(body.sum()), "figPx": int(fig.sum()), "pedestalPx": int(masks["ped"].sum()),
         "labelPxExcluded": int((masks["labels"] & ndimage.binary_dilation(fig, iterations=3)).sum())}
    if r["bodyPx"] < 50:
        r["error"] = "no figure pixels"
        return r
    r["lumaOff"], r["lumaOn"] = round(float(yo[body].mean()), 2), round(float(yn[body].mean()), 2)
    r["gain"] = round(r["lumaOn"] / max(r["lumaOff"], 1e-6) - 1.0, 4)
    r["D1detailOff"], r["D1detailOn"] = round(detail(yo, interior), 4), round(detail(yn, interior), 4)
    r["D1"] = round(r["D1detailOn"] / max(r["D1detailOff"], 1e-9), 4)
    so, sn = saturation(off), saturation(on)
    r["D2satOff"], r["D2satOn"] = round(float(so[body].mean()), 4), round(float(sn[body].mean()), 4)
    r["D2"] = round(r["D2satOn"] / max(r["D2satOff"], 1e-9), 4)
    lvl = T["D3level"]
    # D3 counts the clipping the light adds: >= 245 with the light, < 245 without (labels, a Niagara fire in front of a
    # figure, a moon highlight are clipped in both frames and are not the hero light's doing; reported as raw shares)
    hot_on, hot_off = on.max(-1) >= lvl, off.max(-1) >= lvl
    r["D3clipOffPct"] = round(float(hot_off[fig].mean() * 100), 3)
    r["D3clipRawOnPct"] = round(float(hot_on[fig].mean() * 100), 3)
    r["D3clipOnPct"] = round(float((hot_on & ~hot_off)[fig].mean() * 100), 3)
    r["D3clipBodyOnPct"] = round(float((hot_on & ~hot_off)[body].mean() * 100), 3)
    if masks["ped"].sum() > 20:
        r["pedestalLumaOff"] = round(float(yo[masks["ped"]].mean()), 2)
        r["pedestalLumaOn"] = round(float(yn[masks["ped"]].mean()), 2)
    lo, hi = T["D4band"]
    inner, outer = band_inside(body, lo, hi), band_outside(body | fig, lo, hi)
    outer &= ~ndimage.binary_dilation(masks["labels"], iterations=1)
    if inner.sum() > 10 and outer.sum() > 10:
        c_off = float(yo[inner].mean() / max(yo[outer].mean(), 1e-6))
        c_on = float(yn[inner].mean() / max(yn[outer].mean(), 1e-6))
        r["D4edgeOff"], r["D4edgeOn"] = round(c_off, 4), round(c_on, 4)
        r["D4edge"] = round(c_on / max(c_off, 1e-9), 4)
        r["edgeAbsDeltaOff"] = round(float(abs(yo[inner].mean() - yo[outer].mean())), 2)
        r["edgeAbsDeltaOn"] = round(float(abs(yn[inner].mean() - yn[outer].mean())), 2)
    far = ~ndimage.binary_dilation(fig | body, iterations=T["H2dilate"])
    dy = yn - yo
    r["H2outsideMeanAbs"] = round(float(np.abs(dy[far]).mean()), 3)
    r["H2outsideMeanSigned"] = round(float(dy[far].mean()), 3)
    if view.startswith("K2"):
        h, w = body.shape
        hero = component_at(body, (w / 2.0, h / 2.0), max_dist=200.0)
        if hero is not None:
            others = [c for c in components(body) if not (c & hero).any()]
            g_hero = float((yn - yo)[hero].mean())
            r["D5heroPx"] = int(hero.sum())
            r["D5heroGain"] = round(g_hero, 3)
            if others:
                g_oth = float(np.mean([(yn - yo)[c].mean() for c in others]))
                r["D5gainVsOthers"] = round(g_hero / max(g_oth, 1e-6), 3)  # the P9 "2.77x" reading (different figures)
                r["D5lumaVsOthers"] = round(float(yn[hero].mean() / np.mean([yn[c].mean() for c in others])), 3)
            if idle is not None:
                yi = luma(idle)
                g_idle = float((yi - yo)[hero].mean())
                r["D5idleGain"] = round(g_idle, 3)
                r["D5"] = round(g_hero / max(g_idle, 1e-6), 4)
                r["D5lumaActiveVsIdle"] = round(float(yn[hero].mean() / max(yi[hero].mean(), 1e-6)), 4)
    return r


def gates(r: dict, view: str) -> dict:
    T = THRESHOLDS
    g = {}
    if "D1" not in r:
        return {"error": r.get("error", "no metrics")}
    g["D1"] = r["D1"] >= T["D1"]
    g["D2"] = r["D2"] >= T["D2"]
    g["D3"] = r["D3clipOnPct"] <= T["D3pct"]
    if view == "K1":
        g["D4gain"] = T["D4gain"][0] <= r["gain"] <= T["D4gain"][1]
        if "D4edge" in r:
            g["D4edge"] = r["D4edge"] >= T["D4edge"]
    if view.startswith("K2") and "D5" in r:
        g["D5"] = T["D5"][0] <= r["D5"] <= T["D5"][1]
    g["H2"] = r["H2outsideMeanAbs"] <= T["H2out"] and abs(r["H2outsideMeanSigned"]) <= T["H2signed"]
    return {k: ("PASS" if v else "FAIL") for k, v in g.items()}


# ---------------------------------------------------------------- D6 colour fidelity

def reference_zones(cfg_ref: dict, repo: Path) -> dict:
    """Median sRGB / Lab of every zone rectangle of a reference studio render."""
    img = load(repo / cfg_ref["image"])
    out = {}
    for zone, rects in cfg_ref["zones"].items():
        px = np.concatenate([img[y0:y1, x0:x1].reshape(-1, 3) for x0, y0, x1, y1 in rects])
        srgb = np.median(px, axis=0)
        out[zone] = {"srgb": [round(float(v), 1) for v in srgb], "lab": [round(float(v), 2) for v in srgb_to_lab(srgb)],
                     "px": int(len(px))}
    return out


def chroma(lab) -> float:
    return float(math.hypot(lab[1], lab[2]))


def order_agreement(zl: dict, ref: dict, key: str, min_gap: float = 8.0) -> float | None:
    """Share of zone pairs whose L (key='L') or chroma (key='C') order matches the reference (pairs with a gap > min_gap)."""
    def val(lab):
        return lab[0] if key == "L" else chroma(lab)
    names = [z for z in ref if z in zl]
    ok = total = 0
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            gr = val(ref[a]["lab"]) - val(ref[b]["lab"])
            if abs(gr) <= min_gap:
                continue
            total += 1
            ok += int(np.sign(val(zl[a]) - val(zl[b])) == np.sign(gr))
    return round(ok / total, 3) if total else None


def classify_zones(off: np.ndarray, body: np.ndarray, ref: dict) -> dict:
    """Body pixels -> nearest reference body zone, after a grey-world balance of the off frame to the reference."""
    zones = [z for z in ref if z != "pedestal"]
    lin = srgb_to_linear(off[body])
    ref_lin = np.mean([srgb_to_linear(np.array(ref[z]["srgb"])) for z in zones], axis=0)
    lin_bal = lin * (ref_lin / np.maximum(lin.mean(0), 1e-6))
    lab = linear_to_lab(np.clip(lin_bal, 0, 1))
    centres = np.array([ref[z]["lab"] for z in zones])
    wts = np.array([0.5, 1.0, 1.0])
    d = (((lab[:, None, :] - centres[None]) * wts) ** 2).sum(-1)
    idx = d.argmin(1)
    ys, xs = np.nonzero(body)
    out = {}
    for i, z in enumerate(zones):
        m = np.zeros(body.shape, bool)
        sel = idx == i
        m[ys[sel], xs[sel]] = True
        out[z] = m
    return out


def zone_labs(img: np.ndarray, zone_masks: dict, body_zones: list[str], ref: dict) -> tuple[dict, float]:
    """Median colour per zone, exposure-normalised: the figure's linear luminance (the mean over its body zone medians)
    scaled to the reference's, so a darker night frame is compared by hue, chroma and relative value, not by exposure."""
    med = {z: srgb_to_linear(np.median(img[m], axis=0)) for z, m in zone_masks.items() if m.sum() >= 12}
    yb = [float(med[z] @ W709) for z in body_zones if z in med]
    yr = [float(srgb_to_linear(np.array(ref[z]["srgb"])) @ W709) for z in body_zones if z in med]
    k = float(np.mean(yr) / max(np.mean(yb), 1e-6)) if yb else 1.0
    return {z: [float(v) for v in linear_to_lab(np.clip(lin * k, 0, 1))] for z, lin in med.items()}, k


def d6_figure(frames: dict, masks: dict, xy, ref: dict) -> dict:
    """frames: name -> image (must include 'off'); the figure = the body component at xy; pedestal pixels around it."""
    body = component_at(masks["body"], xy)
    if body is None:
        return {"error": f"no body component near {xy}"}
    near = ndimage.binary_dilation(body, iterations=30)
    ped = masks["ped"] & near
    zm = classify_zones(frames["off"], body, ref)
    body_zones = list(zm)
    if "pedestal" in ref and ped.sum() >= 12:
        zm["pedestal"] = ped
    res = {"bodyPx": int(body.sum()), "pedestalPx": int(ped.sum()),
           "zonePx": {z: int(m.sum()) for z, m in zm.items()}, "frames": {}}
    for name, img in frames.items():
        labs, k = zone_labs(img, zm, body_zones, ref)
        raw = {z: [float(v) for v in srgb_to_lab(np.median(img[m], axis=0))] for z, m in zm.items() if m.sum() >= 12}
        per = {}
        for z, lab in labs.items():
            rl = ref[z]["lab"]
            per[z] = {"labNorm": [round(v, 2) for v in lab], "labRaw": [round(v, 2) for v in raw[z]],
                      "dEnorm": round(math.dist(lab, rl), 2), "dE76raw": round(math.dist(raw[z], rl), 2),
                      "dABnorm": round(math.hypot(lab[1] - rl[1], lab[2] - rl[2]), 2)}
        res["frames"][name] = {
            "zones": per, "exposureK": round(k, 3),
            "meanDEnorm": round(float(np.mean([p["dEnorm"] for p in per.values()])), 2) if per else None,
            "meanDE76raw": round(float(np.mean([p["dE76raw"] for p in per.values()])), 2) if per else None,
            "meanDABnorm": round(float(np.mean([p["dABnorm"] for p in per.values()])), 2) if per else None,
            "orderL": order_agreement(labs, ref, "L"), "orderC": order_agreement(labs, ref, "C")}
    return res


def d6_gate(res: dict, on: str = "on", base: str = "baseline") -> str:
    f = res.get("frames", {})
    if on not in f or base not in f or f[on]["meanDABnorm"] is None:
        return "n/a"
    better = f[on]["meanDABnorm"] < f[base]["meanDABnorm"]
    orders = all((f[on][k] or 0) >= (f[base][k] or 0) for k in ("orderL", "orderC"))
    return "PASS" if better and orders else "FAIL"


# ---------------------------------------------------------------- runs

def shot(run: Path, view: str) -> Path | None:
    p = Path(run) / f"bench-{view}-1920x1080.png"
    return p if p.exists() else None


def measure(args) -> dict:
    out = {"label": args.label, "off": str(args.off), "on": str(args.on), "maskBody": str(args.mask_body),
           "maskFig": str(args.mask_fig), "idle": str(args.idle) if args.idle else None, "thresholds": THRESHOLDS,
           "views": {}}
    cfg = json.loads(Path(args.d6).read_text(encoding="utf-8")) if args.d6 else None
    repo = Path(__file__).resolve().parents[3]
    refs = {k: reference_zones(v, repo) for k, v in cfg["references"].items()} if cfg else {}
    if refs:
        out["d6References"] = refs
    for view in VIEWS:
        po, pn, pb = shot(args.off, view), shot(args.on, view), shot(args.mask_body, view)
        if not (po and pn and pb):
            continue
        off, on = load(po), load(pn)
        pf = shot(args.mask_fig, view) if args.mask_fig else None
        masks = build_masks(off, load(pb), load(pf) if pf else None)
        pi = shot(args.idle, view) if args.idle else None
        r = view_metrics(off, on, masks, view, load(pi) if pi else None)
        r["gates"] = gates(r, view)
        if cfg and args.board and view == "K2x2p5":
            figs = cfg.get("figures", {}).get(args.board, {}).get(view, [])
            frames = {"off": off, "on": on}
            pbase = shot(args.baseline, view) if args.baseline else None
            if pbase:
                frames["baseline"] = load(pbase)
            r["D6"] = {}
            for f in figs:
                res = d6_figure(frames, masks, f["at"], refs[f["hero"]])
                res["hero"] = f["hero"]
                res["gate"] = d6_gate(res)
                r["D6"][f["name"]] = res
                r["gates"][f"D6:{f['name']}"] = res["gate"]
        out["views"][view] = r
    return out


# ---------------------------------------------------------------- self-test

def _synthetic(seed: int = 7):
    """A textured disc 'figure' with a darker pedestal ring on a mid-grey board; returns (albedo, body, ped, shading)."""
    rng = np.random.default_rng(seed)
    h, w = 240, 320
    yy, xx = np.mgrid[0:h, 0:w]
    body = (xx - 160) ** 2 / 50 ** 2 + (yy - 110) ** 2 / 70 ** 2 <= 1.0
    ped = ((xx - 160) ** 2 / 70 ** 2 + (yy - 175) ** 2 / 25 ** 2 <= 1.0) & ~body
    tex = ndimage.gaussian_filter(rng.random((h, w)), 1.2)
    tex = (tex - tex.min()) / (tex.max() - tex.min())
    albedo = np.zeros((h, w, 3)) + np.array([0.18, 0.2, 0.22])
    albedo[body] = np.array([0.55, 0.32, 0.16]) * (0.55 + 0.9 * tex[body])[:, None]
    albedo[ped] = np.array([0.08, 0.07, 0.065])
    shade = np.ones((h, w))
    shade[body] = 0.35 + 0.65 * np.clip((xx[body] - 110) / 100.0, 0, 1)  # side key: form shading left -> right
    return albedo, body, ped, shade


def _render(albedo, light, flat=0.0, exposure=1.0):
    """Linear radiance -> a filmic-ish shoulder -> sRGB 0..255."""
    rad = albedo * (light[..., None] if light.ndim == 2 else light) + flat
    x = rad * exposure
    tone = x * (2.51 * x + 0.03) / (x * (2.43 * x + 0.59) + 0.14)  # ACES fit
    tone = np.clip(tone, 0, 1)
    srgb = np.where(tone <= 0.0031308, 12.92 * tone, 1.055 * tone ** (1 / 2.4) - 0.055)
    return np.clip(srgb * 255.0, 0, 255).round()


def self_check() -> list[str]:
    errs = []
    albedo, body, ped, shade = _synthetic()
    base = 0.22 * shade  # a night level: the figure at sRGB luma ~70-90 like the real -NoHeroLight frames
    off = _render(albedo, base)
    # mask runs: a green light on the body (maskbody) and on body + pedestal (maskfig)
    g = np.zeros(albedo.shape)
    g[body] = [0, 2.0, 0]
    gm = _render(albedo, np.repeat(base[..., None], 3, -1) + g)
    g2 = g.copy()
    g2[ped] = [0, 6.0, 0]
    gf = _render(albedo, np.repeat(base[..., None], 3, -1) + g2)
    masks = build_masks(off, gm, gf)
    iou = (masks["body"] & body).sum() / max((masks["body"] | body).sum(), 1)
    if iou < 0.9:
        errs.append(f"body mask IoU {iou:.3f} < 0.9")
    if masks["ped"].sum() < 0.5 * ped.sum():
        errs.append(f"pedestal mask {masks['ped'].sum()} px of {ped.sum()}")
    # fire-like noise outside the figure (R >= G) must stay out of the mask
    noisy = gm.copy()
    noisy[10:40, 10:60] += np.array([40.0, 25.0, 5.0])
    if (build_masks(off, noisy, gf)["body"][10:40, 10:60]).any():
        errs.append("fire-like noise entered the mask")
    # (a) an accent: a warm side key that agrees with the scene key - it adds form shading and, at a raking angle, the
    #     relief of the normal map (N.L varies with the bump) -> D1..D4 pass. A flat light would lose relative detail and
    #     saturation through the tonemapper toe -> shoulder (see (b)); this is why the gates ask for a directional accent.
    rng = np.random.default_rng(11)
    bump = ndimage.gaussian_filter(rng.random(body.shape), 1.0)
    bump = (bump - bump.mean()) / (bump.std() + 1e-9)
    nl = np.clip(0.75 + 0.35 * bump, 0.05, 1.6) * np.clip(shade - 0.3, 0, 1)
    acc = np.repeat(base[..., None], 3, -1)
    acc[body] += 0.2 * nl[body][:, None] * np.array([1.0, 0.86, 0.72])
    on_a = _render(albedo, acc)
    ra = view_metrics(off, on_a, masks, "K1")
    ga = gates(ra, "K1")
    for k in ("D1", "D2", "D3", "D4gain", "D4edge", "H2"):
        if ga.get(k) != "PASS":
            errs.append(f"accent: {k} {ga.get(k)} ({ra})")
    # (b) the P9 failure: a strong flat frontal flood on the figure -> flattened (D1), washed (D2), clipped (D3), too bright (D4)
    on_b = _render(albedo, base + np.where(body | ped, 3.0, 0.0))
    rb = view_metrics(off, on_b, masks, "K1")
    gb = gates(rb, "K1")
    for k in ("D1", "D2", "D3", "D4gain"):
        if gb.get(k) != "FAIL":
            errs.append(f"flood: {k} {gb.get(k)} expected FAIL ({rb})")
    # (c) spill on the board -> H2 fails
    on_c = on_a.copy()
    on_c[~body & ~ped] = np.clip(on_c[~body & ~ped] + 3.0, 0, 255)
    if gates(view_metrics(off, on_c, masks, "K1"), "K1")["H2"] != "FAIL":
        errs.append("spill: H2 should fail")
    # (d) D5: the hero at the centre with x1.15 of the idle light vs x1.35
    alb2, body2, ped2, shade2 = _synthetic(seed=3)
    h, w = body2.shape
    sh = np.roll(np.roll(body2, h // 2 - 110, 0), w // 2 - 160, 1)  # centre the figure
    alb2 = np.roll(np.roll(alb2, h // 2 - 110, 0), w // 2 - 160, 1)
    base2 = 0.6 * np.ones((h, w))
    off2 = _render(alb2, base2)
    gm2 = off2.copy()
    gm2[sh] = np.clip(gm2[sh] + np.array([0, 60.0, 0]), 0, 255)
    masks2 = build_masks(off2, gm2, gm2)

    def lit(mul):
        L = base2.copy()
        L[sh] += 0.25 * mul
        return _render(alb2, L)
    idle = lit(1.0)
    r15 = view_metrics(off2, lit(1.15), masks2, "K2x2p5", idle)
    r35 = view_metrics(off2, lit(1.35), masks2, "K2x2p5", idle)
    if gates(r15, "K2x2p5").get("D5") != "PASS":
        errs.append(f"D5 x1.15 should pass ({r15.get('D5')})")
    if gates(r35, "K2x2p5").get("D5") != "FAIL":
        errs.append(f"D5 x1.35 should fail ({r35.get('D5')})")
    # (e) D6: a washed frame is farther from the reference than an accent frame
    ref = {"skin": {"srgb": [200, 170, 150]}, "cloth": {"srgb": [90, 60, 120]}, "pedestal": {"srgb": [40, 38, 36]}}
    for z in ref.values():
        z["lab"] = [float(v) for v in srgb_to_lab(np.array(z["srgb"], float))]
    alb3 = np.zeros((h, w, 3)) + 0.2
    yy, xx = np.mgrid[0:h, 0:w]
    fig3 = (xx - 160) ** 2 + (yy - 110) ** 2 <= 45 ** 2
    left = fig3 & (xx < 160)
    alb3[left] = srgb_to_linear(np.array(ref["skin"]["srgb"], float))
    alb3[fig3 & ~left] = srgb_to_linear(np.array(ref["cloth"]["srgb"], float))
    ped3 = ((xx - 160) ** 2 + (yy - 110) ** 2 <= 60 ** 2) & ~fig3
    alb3[ped3] = srgb_to_linear(np.array(ref["pedestal"]["srgb"], float))
    moon = np.array([0.55, 0.62, 0.8])
    off3 = _render(alb3, np.ones((h, w, 3)) * moon * 0.8)
    m3 = {"body": fig3, "ped": ped3, "fig": fig3 | ped3, "labels": np.zeros((h, w), bool)}
    accent = np.ones((h, w, 3)) * moon * 0.8
    accent[fig3] += np.array([0.45, 0.4, 0.33])
    flood = np.ones((h, w, 3)) * moon * 0.8
    flood[fig3 | ped3] += 7.0
    res = d6_figure({"off": off3, "on": _render(alb3, accent), "baseline": _render(alb3, flood)}, m3, (160, 110), ref)
    if d6_gate(res) != "PASS":
        errs.append(f"D6 accent vs flood should pass ({json.dumps(res['frames'])[:400]})")
    res2 = d6_figure({"off": off3, "on": _render(alb3, flood), "baseline": _render(alb3, accent)}, m3, (160, 110), ref)
    if d6_gate(res2) != "FAIL":
        errs.append("D6 flood vs accent should fail")
    return errs


def main(argv=None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "--check":
        errs = self_check()
        print("hero_light_metrics --check:", "ok" if not errs else "FAILED")
        for e in errs:
            print("  -", e)
        return 1 if errs else 0
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("measure")
    m.add_argument("--off", required=True, type=Path)
    m.add_argument("--on", required=True, type=Path)
    m.add_argument("--mask-body", required=True, type=Path)
    m.add_argument("--mask-fig", type=Path)
    m.add_argument("--idle", type=Path)
    m.add_argument("--baseline", type=Path, help="the P9 run (D6 compares against it)")
    m.add_argument("--d6", type=Path, help="D6 config: references + figure positions")
    m.add_argument("--board")
    m.add_argument("--label", default="")
    m.add_argument("--json", type=Path)
    a = ap.parse_args(argv)
    res = measure(a)
    txt = json.dumps(res, indent=1, ensure_ascii=False)
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(txt + "\n", encoding="utf-8")
    for view, r in res["views"].items():
        keys = ("gain", "D1", "D2", "D3clipOnPct", "D4edge", "D5", "H2outsideMeanAbs", "H2outsideMeanSigned")
        print(a.label, view, {k: r.get(k) for k in keys}, r.get("gates"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
