"""Image checks: C-9 layer contrast and combat-icon contrast at 24/32/48 px.

Statuses follow the stage-3 rule: a check only reports "measured" values and
pass/fail against *named* thresholds whose status (НОРМАТИВ / ПРЕДЛОЖЕНИЕ) is
carried in the output. Nothing here declares artistic acceptance.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
from PIL import Image

from . import color

EPS_LUMINANCE = 1e-6


# --------------------------------------------------------------------- C-9 --

@dataclass
class C9Params:
    ev_min_normative: float = 0.0        # "ярче" (QA-010 Then / 17 AD-AC-33): dEV > 0
    ev_range_proposed: tuple[float, float] = (0.3, 0.7)   # 03 C-9, ПРЕДЛОЖЕНИЕ
    chroma_min_delta_proposed: float = 0.0  # "насыщеннее" (03 C-9), ПРЕДЛОЖЕНИЕ
    statistic: str = "mean"              # mean | median (of linear luminance)
    min_pixels: int = 2000
    allow_overlap: bool = False


def check_c9(rgb_u8: np.ndarray, game: np.ndarray, decor: np.ndarray,
             params: C9Params, exclude: Optional[np.ndarray] = None,
             proxies: Optional[list[dict]] = None) -> dict:
    """proxies: layers.proxy_regions(...) for the masks. Any proxy turns
    result_normative / result_proposed into "proxy" (no normative verdict);
    the would-be verdicts stay in result_on_proxy for diagnostics."""
    game = game.copy()
    decor = decor.copy()
    overlap = game & decor
    n_overlap = int(overlap.sum())
    issues = []
    if n_overlap and not params.allow_overlap:
        return {"status": "insufficient_input",
                "reason": f"game and decor masks overlap on {n_overlap} px (use --allow-overlap to drop them)"}
    if n_overlap:
        game &= ~overlap
        decor &= ~overlap
        issues.append(f"{n_overlap} overlapping px excluded from both layers")
    if exclude is not None:
        game &= ~exclude
        decor &= ~exclude
    ng, nd = int(game.sum()), int(decor.sum())
    if ng < params.min_pixels or nd < params.min_pixels:
        return {"status": "insufficient_input",
                "reason": f"layer pixels game={ng} decor={nd} < min_pixels={params.min_pixels}"}
    pg, pd = rgb_u8[game], rgb_u8[decor]
    yg, yd = color.relative_luminance(pg), color.relative_luminance(pd)
    cg, bg_ = color.lab_chroma(pg)
    cd, bd = color.lab_chroma(pd)
    stat = np.mean if params.statistic == "mean" else np.median
    lg, ld = float(stat(yg)), float(stat(yd))
    dev = math.log2(max(lg, EPS_LUMINANCE) / max(ld, EPS_LUMINANCE))
    dev_median = math.log2(max(float(np.median(yg)), EPS_LUMINANCE) / max(float(np.median(yd)), EPS_LUMINANCE))
    dev_mean = math.log2(max(float(yg.mean()), EPS_LUMINANCE) / max(float(yd.mean()), EPS_LUMINANCE))
    dchroma = float(cg.mean() - cd.mean())
    lo, hi = params.ev_range_proposed
    verdicts = {
        "brighter": {
            "rule": f"dEV({params.statistic}) > {params.ev_min_normative}",
            "value": round(dev, 4), "pass": dev > params.ev_min_normative,
            "threshold_status": "НОРМАТИВ (качественное «ярче»): 10 QA-010 стр. 132; 17 AD-AC-33",
        },
        "ev_range": {
            "rule": f"{lo} <= dEV({params.statistic}) <= {hi}",
            "value": round(dev, 4), "pass": lo <= dev <= hi,
            "threshold_status": "ПРЕДЛОЖЕНИЕ: 03 С-9 (+0.3..+0.7 EV); 17 AD-AC-33, AD-OPEN-11",
        },
        "more_saturated": {
            "rule": f"mean C*ab(game) - mean C*ab(decor) > {params.chroma_min_delta_proposed}",
            "value": round(dchroma, 3), "pass": dchroma > params.chroma_min_delta_proposed,
            "threshold_status": "ПРЕДЛОЖЕНИЕ: 03 С-9 «ярче и насыщеннее»; метрика C*ab выбрана инструментом",
        },
    }
    res_norm = "pass" if verdicts["brighter"]["pass"] else "fail"
    res_prop = "pass" if all(v["pass"] for v in verdicts.values()) else "fail"
    proxies = list(proxies or [])
    if proxies:
        layer_basis = {
            "proxy": True, "normative": False, "proxy_regions": proxies,
            "reason": ("С-9 сравнивает игровой слой с декором L3 (фасады, фонарь, ящики; 03 §4.1, 17 §11.10). "
                       "Маска-прокси не даёт нормативного результата: нужна stencil- или ручная маска L3 "
                       "(и маска игрового слоя L1/L2)."),
        }
        head = {"result_normative": "proxy", "result_proposed": "proxy",
                "result_on_proxy": {"normative": res_norm, "proposed": res_prop,
                                    "note": "измерено на прокси-маске, не норматив"}}
    else:
        layer_basis = {"proxy": False, "normative": True,
                       "note": "маски mask:/bbox:/poly:/trace-cells — вход вызывающего; принадлежность слою "
                               "(L1/L2 против L3) утверждает вызывающий, инструмент её не проверяет"}
        head = {"result_normative": res_norm, "result_proposed": res_prop}
    return {
        "status": "measured",
        **head,
        "layer_basis": layer_basis,
        "verdicts": verdicts,
        "layers": {
            "game": {"pixels": ng, "rel_luminance_mean": round(float(yg.mean()), 6),
                     "rel_luminance_median": round(float(np.median(yg)), 6),
                     "chroma_mean": round(float(cg.mean()), 3), "b_star_mean": round(float(bg_.mean()), 3)},
            "decor": {"pixels": nd, "rel_luminance_mean": round(float(yd.mean()), 6),
                      "rel_luminance_median": round(float(np.median(yd)), 6),
                      "chroma_mean": round(float(cd.mean()), 3), "b_star_mean": round(float(bd.mean()), 3)},
        },
        "delta_ev": {"used": round(dev, 4), "mean": round(dev_mean, 4), "median": round(dev_median, 4)},
        "info": {
            "decor_cool": {"rule": "mean b*(decor) < 0 (холодные тона, 03 С-9) — информативно, не gate",
                           "value": round(float(bd.mean()), 3), "cool": bool(bd.mean() < 0)},
        },
        "issues": issues,
        "params": {"statistic": params.statistic, "ev_min_normative": params.ev_min_normative,
                   "ev_range_proposed": list(params.ev_range_proposed),
                   "chroma_min_delta_proposed": params.chroma_min_delta_proposed,
                   "min_pixels": params.min_pixels, "allow_overlap": params.allow_overlap},
    }


# -------------------------------------------------------------------- icon --

@dataclass
class IconParams:
    sizes: tuple[int, ...] = (24, 32, 48)
    min_contrast_ratio: float = 3.0            # 02 стр. 864 «иконки ≥ 3:1», ПРЕДЛОЖЕНИЕ
    min_luma_delta: Optional[float] = None     # no norm: informational unless set
    fg_coverage: float = 0.75
    bg_coverage: float = 0.25
    ring_frac: float = 0.25
    ring_min_px: int = 2
    min_fg_fraction: float = 0.02
    background: str = "bbox"                   # bbox | ring


def luma_levels(values: np.ndarray) -> np.ndarray:
    """Integer 0..255 levels (round half up). Otsu histogram *and* the class
    split must use the same levels: float luma of a gray 20 is 19.999..., which
    a floor-binned histogram puts in bin 19 while `y > 19` still counts it high."""
    return np.clip(np.floor(np.asarray(values, dtype=np.float64) + 0.5), 0, 255).astype(np.int64)


def otsu_threshold(values: np.ndarray) -> Optional[int]:
    """Otsu threshold level t on 0..255 values (class split: level <= t vs > t);
    None when the histogram has a single populated level."""
    hist = np.bincount(luma_levels(values).ravel(), minlength=256)
    total = hist.sum()
    if total == 0:
        return None
    levels = np.arange(256, dtype=np.float64)
    w0 = np.cumsum(hist)
    w1 = total - w0
    s0 = np.cumsum(hist * levels)
    with np.errstate(divide="ignore", invalid="ignore"):
        mu0 = s0 / w0
        mu1 = (s0[-1] - s0) / w1
        between = w0 * w1 * (mu0 - mu1) ** 2
    between = np.nan_to_num(between, nan=0.0, posinf=0.0)
    if between.max() <= 0:
        return None
    return int(np.argmax(between))


def auto_icon_mask(crop_u8: np.ndarray, inbox: np.ndarray) -> tuple[np.ndarray, dict]:
    """Heuristic foreground: Otsu split of luma inside the bbox; the class
    whose mean is farther from the surrounding ring's median luma is the icon
    (minority class if there is no ring)."""
    y = luma_levels(color.luma_u8(crop_u8))
    t = otsu_threshold(y[inbox])
    if t is None:
        return np.zeros_like(inbox), {"method": "auto-otsu", "threshold": None,
                                      "note": "uniform bbox: no foreground"}
    hi = inbox & (y > t)
    lo = inbox & (y <= t)
    ring = ~inbox
    if ring.any():
        ref = float(np.median(y[ring]))
        pick_hi = abs(float(y[hi].mean()) - ref) >= abs(float(y[lo].mean()) - ref) if hi.any() and lo.any() else hi.any()
        basis = f"farther from ring median luma {ref:.1f}"
    else:
        pick_hi = hi.sum() <= lo.sum()
        basis = "minority class (no ring)"
    return (hi if pick_hi else lo), {"method": "auto-otsu", "threshold": t,
                                     "foreground": "bright" if pick_hi else "dark", "basis": basis}


def _resize_float(arr2d: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    im = Image.fromarray(np.ascontiguousarray(arr2d, dtype=np.float32))
    return np.asarray(im.resize(size, Image.Resampling.BOX), dtype=np.float64)


def check_icon(rgb_u8: np.ndarray, bbox: tuple[int, int, int, int], params: IconParams,
               fg_mask: Optional[np.ndarray] = None) -> dict:
    """bbox: integer half-open (x0, y0, x1, y1) in frame pixels. fg_mask:
    boolean mask of the icon, either frame-sized or bbox-sized; None = auto."""
    h, w = rgb_u8.shape[:2]
    x0, x1 = sorted((int(bbox[0]), int(bbox[2])))
    y0, y1 = sorted((int(bbox[1]), int(bbox[3])))
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    bw, bh = x1 - x0, y1 - y0
    if bw < 2 or bh < 2:
        return {"status": "insufficient_input", "reason": f"bbox {bbox} empty or outside the frame"}
    ring = max(params.ring_min_px, int(round(params.ring_frac * max(bw, bh))))
    cx0, cy0 = max(0, x0 - ring), max(0, y0 - ring)
    cx1, cy1 = min(w, x1 + ring), min(h, y1 + ring)
    crop = rgb_u8[cy0:cy1, cx0:cx1]
    ch, cw = crop.shape[:2]
    inbox = np.zeros((ch, cw), dtype=bool)
    inbox[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0] = True
    if fg_mask is not None:
        if fg_mask.shape == (h, w):
            fg = fg_mask[cy0:cy1, cx0:cx1] & inbox
        elif fg_mask.shape == (bh, bw):
            fg = np.zeros((ch, cw), dtype=bool)
            fg[y0 - cy0:y1 - cy0, x0 - cx0:x1 - cx0] = fg_mask
        else:
            return {"status": "insufficient_input",
                    "reason": f"icon mask shape {fg_mask.shape} matches neither frame {(h, w)} nor bbox {(bh, bw)}"}
        mask_info = {"method": "mask"}
    else:
        fg, mask_info = auto_icon_mask(crop, inbox)
    native_fg = int(fg.sum())
    lin = color.u8_to_linear(crop)
    results = []
    for size in params.sizes:
        s = size / max(bw, bh)
        nw, nh = max(1, int(round(cw * s))), max(1, int(round(ch * s)))
        lin_s = np.stack([_resize_float(lin[..., k], (nw, nh)) for k in range(3)], axis=-1)
        cover = _resize_float(fg.astype(np.float32), (nw, nh))
        # pixel centres of the resized grid mapped back to crop coordinates
        xs = (np.arange(nw) + 0.5) * (cw / nw)
        ys = (np.arange(nh) + 0.5) * (ch / nh)
        in_x = (xs >= x0 - cx0) & (xs < x1 - cx0)
        in_y = (ys >= y0 - cy0) & (ys < y1 - cy0)
        inb = in_y[:, None] & in_x[None, :]
        fg_s = inb & (cover >= params.fg_coverage)
        bg_in = inb & (cover <= params.bg_coverage)
        bg_ring = (~inb) & (cover <= params.bg_coverage)
        bg = bg_in if params.background == "bbox" else bg_ring
        bg_source = params.background
        if not bg.any():
            bg, bg_source = (bg_ring if params.background == "bbox" else bg_in), "fallback"
        lum = color.relative_luminance_linear(lin_s)
        u8 = color.quantize_u8(color.linear_to_srgb(lin_s))
        luma = color.luma_u8(u8)
        deut = color.relative_luminance_linear(color.simulate_deuteranopia_linear(lin_s))
        n_fg, n_box = int(fg_s.sum()), int(inb.sum())
        entry = {"size_px": size, "scale": round(s, 4), "upscaled": s > 1.0,
                 "fg_pixels": n_fg, "bbox_pixels": n_box,
                 "fg_fraction": round(n_fg / n_box, 4) if n_box else 0.0,
                 "bg_pixels": int(bg.sum()), "bg_source": bg_source}
        if n_fg == 0 or not bg.any():
            entry.update({"contrast_ratio": None, "luma_delta": None, "pass": False,
                          "reason": "icon collapses: no pixel reaches fg coverage" if n_fg == 0 else "no background pixels"})
            results.append(entry)
            continue
        lf, lb = float(np.median(lum[fg_s])), float(np.median(lum[bg]))
        cr = float(color.wcag_contrast_ratio(lf, lb))
        dl = float(np.median(luma[fg_s]) - np.median(luma[bg]))
        ring_cr = None
        if bg_ring.any():
            ring_cr = round(float(color.wcag_contrast_ratio(lf, float(np.median(lum[bg_ring])))), 3)
        dcr = float(color.wcag_contrast_ratio(float(np.median(deut[fg_s])), float(np.median(deut[bg]))))
        reasons = []
        if entry["fg_fraction"] < params.min_fg_fraction:
            reasons.append(f"fg fraction {entry['fg_fraction']} < {params.min_fg_fraction}")
        if cr < params.min_contrast_ratio:
            reasons.append(f"contrast {cr:.2f} < {params.min_contrast_ratio}")
        if params.min_luma_delta is not None and abs(dl) < params.min_luma_delta:
            reasons.append(f"|luma delta| {abs(dl):.1f} < {params.min_luma_delta}")
        entry.update({"fg_rel_luminance": round(lf, 6), "bg_rel_luminance": round(lb, 6),
                      "contrast_ratio": round(cr, 3), "luma_delta": round(dl, 2),
                      "contrast_ratio_vs_ring": ring_cr, "contrast_ratio_deuteranopia": round(dcr, 3),
                      "pass": not reasons, "reason": "; ".join(reasons) or "ok"})
        results.append(entry)
    return {
        "status": "measured",
        "result": "pass" if all(r["pass"] for r in results) else "fail",
        "bbox": [x0, y0, x1, y1], "native_size_px": [bw, bh], "ring_px": ring,
        "native_fg_pixels": native_fg, "foreground": mask_info,
        "sizes": results,
        "params": {"min_contrast_ratio": params.min_contrast_ratio,
                   "min_contrast_status": "ПРЕДЛОЖЕНИЕ: 02 стр. 864 «иконки ≥ 3:1»; 17 стр. 1200",
                   "min_luma_delta": params.min_luma_delta,
                   "min_luma_delta_status": "не задан нормативами; информативно, если не указан",
                   "fg_coverage": params.fg_coverage, "bg_coverage": params.bg_coverage,
                   "min_fg_fraction": params.min_fg_fraction,
                   "min_fg_fraction_status": "ПРЕДЛОЖЕНИЕ инструмента (нормы нет)",
                   "background": params.background, "sizes_status": "02 стр. 894 UI-ICON-ACTION 24/32/48; «проверка в 24 px обязательна»"},
    }


# ---------------------------------------------------------------- icon rev 3 (W5b-R, decision D-5)

def _outer_ring(shape: np.ndarray) -> np.ndarray:
    """Pixels of `shape` with a 4-neighbour outside it (or on the image border): the 1 px rim."""
    pad = np.pad(shape, 1, constant_values=False)
    inner = pad[1:-1, 1:-1] & pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
    return shape & ~inner


def check_icon_token(rgb_u8: np.ndarray, bbox: tuple[int, int, int, int], glyph_alpha: np.ndarray,
                     token_rgba: np.ndarray, mask_alpha: float = 0.5, min_contrast: float = 3.0,
                     surround_px: int = 8, guard_min_ncc: float = 0.9, guard_min_iou: float = 0.6,
                     guard_max_drgb: int = 16) -> dict:
    """Icon rev 3 (t53-thresholds.json icon): the opaque target TOKEN measured at its NATIVE size with masks taken
    from the texture that is drawn - glyph = glyph-mask alpha >= mask_alpha, token shape = token alpha >= 0.5,
    rim = the outer 1 px of the shape, body = shape - glyph - rim. Glyph vs body (colour, gray, deuteranopia), the
    two-tone edge max(rim vs surround, body vs surround) and a presence guard (NCC of the crop against the token
    RGB over the shape, IoU of the matching pixels with the shape). No resampling: the bbox must be N x N."""
    h, w = rgb_u8.shape[:2]
    x0, y0, x1, y1 = (int(round(v)) for v in bbox)
    n = token_rgba.shape[0]
    if token_rgba.shape[:2] != (n, n) or glyph_alpha.shape != (n, n):
        return {"status": "insufficient_input", "reason": f"texture {token_rgba.shape} / mask {glyph_alpha.shape} not N x N"}
    if (x1 - x0, y1 - y0) != (n, n):
        return {"status": "insufficient_input",
                "reason": f"painted bbox {x1 - x0}x{y1 - y0} != texture {n}x{n} (native size only, no resampling)"}
    if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
        return {"status": "insufficient_input", "reason": f"bbox {bbox} outside the frame"}
    crop = rgb_u8[y0:y1, x0:x1]
    glyph = glyph_alpha >= mask_alpha
    shape = token_rgba[..., 3] >= 128
    rim = _outer_ring(shape)
    body = shape & ~glyph & ~rim
    sx0, sy0, sx1, sy1 = max(0, x0 - surround_px), max(0, y0 - surround_px), min(w, x1 + surround_px), min(h, y1 + surround_px)
    sur = np.ones((sy1 - sy0, sx1 - sx0), dtype=bool)
    sur[y0 - sy0:y1 - sy0, x0 - sx0:x1 - sx0] = False
    variants = {"color": crop, "gray": color.grayscale(crop), "deuteranopia": color.deuteranopia(crop)}
    surround_img = rgb_u8[sy0:sy1, sx0:sx1]
    sur_variants = {"color": surround_img, "gray": color.grayscale(surround_img),
                    "deuteranopia": color.deuteranopia(surround_img)}
    out_v = {}
    ok = True
    for vn, img in variants.items():
        lum = color.relative_luminance(img)
        slum = color.relative_luminance(sur_variants[vn])
        lg, lb, lr = float(np.median(lum[glyph])), float(np.median(lum[body])), float(np.median(lum[rim]))
        ls = float(np.median(slum[sur])) if sur.any() else None
        cr = float(color.wcag_contrast_ratio(lg, lb))
        p10 = float(color.wcag_contrast_ratio(float(np.percentile(lum[glyph], 10)), lb))
        edge_rim = float(color.wcag_contrast_ratio(lr, ls)) if ls is not None else None
        edge_body = float(color.wcag_contrast_ratio(lb, ls)) if ls is not None else None
        edge = max(x for x in (edge_rim, edge_body) if x is not None) if ls is not None else None
        passed = cr >= min_contrast and edge is not None and edge >= min_contrast
        ok &= passed
        out_v[vn] = {"glyph_vs_body": round(cr, 3), "glyph_p10_vs_body": round(p10, 3),
                     "edge_rim_vs_surround": round(edge_rim, 3) if edge_rim is not None else None,
                     "edge_body_vs_surround": round(edge_body, 3) if edge_body is not None else None,
                     "edge": round(edge, 3) if edge is not None else None,
                     "glyph_rel_luminance": round(lg, 5), "body_rel_luminance": round(lb, 5),
                     "rim_rel_luminance": round(lr, 5), "surround_rel_luminance": round(ls, 5) if ls is not None else None,
                     "pass": passed}
    # presence guard: the crop IS the opaque token (no scene behind the shape)
    a = crop[shape].astype(np.float64).ravel()
    b = token_rgba[..., :3][shape].astype(np.float64).ravel()
    a0, b0 = a - a.mean(), b - b.mean()
    den = float(np.sqrt((a0 * a0).sum() * (b0 * b0).sum()))
    ncc = float((a0 * b0).sum() / den) if den > 0 else 0.0
    match = shape & (np.abs(crop.astype(int) - token_rgba[..., :3].astype(int)).max(axis=-1) <= guard_max_drgb)
    union = int((match | shape).sum())
    iou = float((match & shape).sum()) / union if union else 0.0
    guard = {"ncc": round(ncc, 4), "iou": round(iou, 4), "min_ncc": guard_min_ncc, "min_iou": guard_min_iou,
             "max_drgb": guard_max_drgb, "present": ncc >= guard_min_ncc and iou >= guard_min_iou}
    status = "measured" if guard["present"] else "no_data"
    return {"status": status,
            "result": ("pass" if ok else "fail") if guard["present"] else "no data (icon not confirmed in the pixels)",
            "bbox": [x0, y0, x1, y1], "size_px": n, "upscaled": False,
            "pixels": {"glyph": int(glyph.sum()), "body": int(body.sum()), "rim": int(rim.sum()),
                       "surround": int(sur.sum())},
            "mask_alpha": mask_alpha, "min_contrast": min_contrast, "variants": out_v, "guard": guard,
            "sizes": [{"size_px": n, "upscaled": False, "contrast_ratio": out_v["color"]["glyph_vs_body"],
                       "contrast_ratio_gray": out_v["gray"]["glyph_vs_body"],
                       "contrast_ratio_deuteranopia": out_v["deuteranopia"]["glyph_vs_body"],
                       "edge": out_v["color"]["edge"], "pass": ok and guard["present"]}]}
