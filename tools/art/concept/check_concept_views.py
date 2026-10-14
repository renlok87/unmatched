#!/usr/bin/env python3
"""Автопроверки и лист-сетка концепт-набора (этап 1 скилла 3d-model-pipeline).

Читает сырые виды `<set>/<key>-<view>.png` (не меняет их), меряет фон, маску фигуры и размещение подставки в % кадра,
сравнивает виды между собой и пишет `checks-report.json` (schema `unmatched.concept-checks/1`) и, с `--sheet`,
лист приёмки `sheet-<key>.png` (направляющие #00C8FF через все виды, линейка в % высоты кадра, свотчи палитры).

    python tools/art/concept/check_concept_views.py --set <dir> --key <content-key> --views front,side,back \
        [--role hero|creature|prop] [--palette <dir>/palette.json] [--sheet] [--out <dir>] [--min-top-pct 4]

--min-top-pct N — рамка ядра (шаг 1a: «верхняя точка не выше y 4 %»): верх маски выше y N % → WARN `view.frame_top`
(не FAIL и не повод для ретрая; видят приёмщик и запускающий агент). Без флага проверки нет.
--side-ortho <ortho_<SIDE_VIEW>.png> — ракурс бокового вида (F8, шаг 1c): силуэт вида `--side-view` (по умолчанию
side), растянутый на кадр ортопроекции черновика 1b, сравнивается по IoU с силуэтом орто и с его зеркалом. Зеркало
лучше на `facing_margin` → FAIL `view.facing` (вид нарисован с другой стороны); разница меньше порога или оба IoU
ниже `facing_iou_warn` → WARN. Без флага проверки нет. Пилот 2026-10-14: прямо 0,96–0,97, зеркало 0,56–0,67.
Код выхода: 0 = 0 FAIL, 1 = есть FAIL, 2 = ошибка входа. Допуски и их калибровка — tools/art/concept/README.md.
Зависимости: numpy, Pillow, scipy (как у остальных инструментов арт-пайплайна).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage as ndi

SCHEMA = "unmatched.concept-checks/1"
TOOL = "tools/art/concept/check_concept_views.py"
GUIDE_RGB = (0, 200, 255)  # #00C8FF — цвет направляющих листа (DECISIONS Р-5.5)
ROLES = ("hero", "creature", "prop")

# Допуски (решение скилла, DECISIONS Р-9). Двухступенчатые там, где калибровка на art/imagegen/hero-quality-v1
# показала, что принятый канон выходит за число Р-9: *_warn = исходное число Р-9 (WARN, видно на листе и приёмщику),
# *_fail = наблюдаемый максимум четырёх наборов + запас (FAIL). Таблица калибровки — tools/art/concept/README.md.
TOLERANCES = {
    "size_rel_pct": 0.5,               # размеры видов: |Δ| по каждой стороне ≤ 0,5 % (канон: 1 px = 0,09 %)
    "border_band_pct": 2.0,            # ширина рамки, по которой судим о фоне, % короткой стороны
    "border_share_min": 0.99,          # доля пикселей рамки в допуске тона
    "border_tone_warn": 12,            # Р-9: ±12 от медианы рамки (канон: Merlin back 0,921 → WARN)
    "border_tone_fail": 20,            # калибровка: 99-й перцентиль отклонения рамки ≤ 16 (Merlin back) + 4
    "bg_neutral_max": 6,               # |R−G|, |G−B| медианы рамки (канон ≤ 4)
    "bg_between_views_max": 12,        # медианы фона разных видов (один фон на набор; канон ≤ 4)
    "bg_dark_luma_warn": 96,           # тёмно-серый фон: яркость медианы > 96 → WARN (канон 24–49)
    "top_min_pct": 1.0,                # верх маски не ближе 1 % высоты к верхнему краю (канон ≥ 1,88)
    "bottom_max_pct": 99.0,            # низ подставки не ниже 99 % высоты (канон ≤ 97,01)
    "side_min_pct": 1.0,               # маска не ближе 1 % ширины к боковым краям (канон ≥ 2,99)
    "base_bottom_spread_warn_pct": 1.5,   # Р-9; разброс низа подставки между видами, % высоты кадра
    "base_bottom_spread_fail_pct": 3.5,   # калибровка: Merlin 2,87
    "base_center_spread_warn_pct": 2.0,   # Р-9; разброс центра подставки, % ширины кадра
    "base_center_spread_fail_pct": 6.5,   # калибровка: Medusa 5,61
    "height_spread_warn_pct": 3.0,        # Р-9; разброс роста (низ подставки − верх маски), % от наибольшего
    "height_spread_fail_pct": 5.0,        # калибровка: Medusa 4,10
    "extra_component_warn_pct": 0.5,   # прочие связные компоненты ≥ 0,5 % площади кадра → WARN (канон ≤ 0,19)
    "mask_area_min_pct": 2.0,          # маска меньше → фигура не найдена (FAIL)
    "mask_area_max_pct": 90.0,         # маска больше → фон не отделился (FAIL)
    "segment_tone": 14,                # порог отделения фигуры от модели фона (уровни 0–255, макс. по каналам)
    "segment_min_component_pct": 0.02,  # компоненты меньше — шум, в маску фигуры не входят
    "facing_margin": 0.05,             # --side-ortho: IoU зеркала больше прямого на столько → FAIL view.facing
    "facing_iou_warn": 0.5,            # --side-ortho: оба IoU ниже → WARN (силуэт не совпал с орто ни так, ни так)
}

HEX_RE = re.compile(r"^#?([0-9A-Fa-f]{6})$")


class InputError(Exception):
    """Ошибка входа → код выхода 2."""


# --------------------------------------------------------------------------------------------- измерения одного вида
def _poly_features(h: int, w: int) -> np.ndarray:
    yy, xx = np.mgrid[0:h, 0:w]
    x = xx / max(w - 1, 1) * 2.0 - 1.0
    y = yy / max(h - 1, 1) * 2.0 - 1.0
    return np.stack([np.ones_like(x), x, y, x * x, y * y, x * y], -1).reshape(-1, 6)


def background_mask(rgb: np.ndarray, band: int, tone: float, iters: int = 3):
    """Модель фона = квадратичная поверхность по каналам (ловит виньетку и мягкий градиент), подгоняется сначала по
    рамке, затем по всему фону, связанному с краем. Возвращает (bg_connected bool[H,W], model float[H,W,3])."""
    h, w, _ = rgb.shape
    feats = _poly_features(h, w)
    flat = rgb.reshape(-1, 3)
    sel = np.zeros((h, w), bool)
    sel[:band] = sel[-band:] = True
    sel[:, :band] = sel[:, -band:] = True
    model = None
    bgc = sel
    for _ in range(iters):
        idx = np.flatnonzero(sel.ravel())
        if idx.size < 16:
            break
        if idx.size > 200_000:
            idx = idx[np.linspace(0, idx.size - 1, 200_000).astype(np.int64)]
        coef, *_ = np.linalg.lstsq(feats[idx], flat[idx], rcond=None)
        model = (feats @ coef).reshape(h, w, 3)
        elig = np.abs(rgb - model).max(2) < tone
        seed = np.zeros_like(elig)
        seed[[0, -1], :] = elig[[0, -1], :]
        seed[:, [0, -1]] = elig[:, [0, -1]]
        bgc = ndi.binary_propagation(seed, mask=elig)
        sel = bgc
    if model is None:
        model = np.broadcast_to(np.median(flat, axis=0), rgb.shape).astype(float)
    return bgc, model


def measure_view(img: Image.Image, tol: dict) -> dict:
    """Все измерения одного вида. Проценты — от высоты (y) или ширины (x) кадра, 0 = верх/лево."""
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    alpha_min = 255
    if has_alpha:
        alpha_min = int(np.asarray(img.convert("RGBA"))[..., 3].min())
    rgb = np.asarray(img.convert("RGB")).astype(np.float64)
    h, w, _ = rgb.shape
    band = max(2, int(round(tol["border_band_pct"] / 100.0 * min(h, w))))
    ring = np.zeros((h, w), bool)
    ring[:band] = ring[-band:] = True
    ring[:, :band] = ring[:, -band:] = True
    border = rgb[ring]
    med = np.median(border, axis=0)
    dev = np.abs(border - med).max(1)
    share_warn = float(np.mean(dev <= tol["border_tone_warn"]))
    share_fail = float(np.mean(dev <= tol["border_tone_fail"]))
    neutral = float(max(abs(med[0] - med[1]), abs(med[1] - med[2])))
    luma = float(0.2126 * med[0] + 0.7152 * med[1] + 0.0722 * med[2])

    bgc, model = background_mask(rgb, band, tol["segment_tone"])
    resid = (rgb - model)[bgc]
    fg = ~bgc
    labels, n = ndi.label(fg)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    area = float(h * w)
    min_comp = max(24.0, tol["segment_min_component_pct"] / 100.0 * area)
    keep = sizes >= min_comp
    keep[0] = False
    out = {
        "size": [w, h],
        "mode": img.mode,
        "alpha": {"present": bool(has_alpha), "min": alpha_min},
        "border": {"band_px": band, "median_rgb": [round(float(c), 1) for c in med],
                   "share_within_tone_warn": round(share_warn, 4), "share_within_tone_fail": round(share_fail, 4),
                   "p99_deviation": round(float(np.percentile(dev, 99)), 1), "neutral_delta": round(neutral, 1),
                   "luma": round(luma, 1)},
        "background_model": {"fit": "quadratic per channel", "residual_std": [round(float(s), 2) for s in resid.std(0)]
                             if resid.size else None, "segment_tone": tol["segment_tone"]},
    }
    if not keep.any():
        out["mask"] = None
        return out
    mask = keep[labels]
    order = np.argsort(sizes)[::-1]
    comps = [int(i) for i in order if sizes[i] > 0]
    main = comps[0]
    others = [round(float(sizes[i]) / area * 100.0, 3) for i in comps[1:] if sizes[i] >= 24][:10]
    filled = ndi.binary_fill_holes(mask)
    ys, xs = np.nonzero(mask)
    top, bottom = int(ys.min()), int(ys.max()) + 1
    left, right = int(xs.min()), int(xs.max()) + 1
    fig_h = bottom - top
    # Подставка: нижняя полоса 6 % роста фигуры; самая широкая строка (медиана центров строк ≥ 95 % этой ширины).
    band_rows = range(max(top, bottom - max(3, int(round(0.06 * fig_h)))), bottom)
    rows = []
    for y in band_rows:
        xx = np.flatnonzero(mask[y])
        if xx.size:
            rows.append((int(xx[-1] - xx[0] + 1), (xx[-1] + xx[0] + 1) / 2.0, y))
    base_w = max(r[0] for r in rows)
    base_cx = float(np.median([r[1] for r in rows if r[0] >= 0.95 * base_w]))
    widest_y = min(r[2] for r in rows if r[0] >= 0.95 * base_w)
    # Верх подставки: от самой широкой строки вверх, пока ширина ≥ 85 % ширины подставки (оценка, не проверка;
    # низ подставки — эллипс, поэтому начинать с самого низа нельзя).
    base_top = widest_y
    for y in range(widest_y, top - 1, -1):
        xx = np.flatnonzero(mask[y])
        if xx.size == 0 or (xx[-1] - xx[0] + 1) < 0.85 * base_w:
            break
        base_top = y
    out["mask"] = {
        "area_pct": round(float(mask.sum()) / area * 100.0, 3),
        "filled_area_pct": round(float(filled.sum()) / area * 100.0, 3),
        "components_kept": int(keep.sum()),
        "main_component_pct": round(float(sizes[main]) / area * 100.0, 3),
        "other_components_pct": others,
        "bbox_px": [left, top, right, bottom],
        "top_pct": round(top / h * 100.0, 3),
        "bottom_pct": round(bottom / h * 100.0, 3),
        "left_pct": round(left / w * 100.0, 3),
        "right_pct": round(right / w * 100.0, 3),
        "height_pct": round(fig_h / h * 100.0, 3),
        "base_center_x_pct": round(base_cx / w * 100.0, 3),
        "base_width_pct": round(base_w / w * 100.0, 3),
        "base_top_pct_est": round(base_top / h * 100.0, 3),
    }
    out["_mask"] = mask  # для палитры; в отчёт не попадает
    out["_rgb"] = rgb
    return out


# ------------------------------------------------------------------------------------------------ ракурс (F8)
def _iou(a: np.ndarray, b: np.ndarray) -> float:
    return float((a & b).sum()) / max(1.0, float((a | b).sum()))


def facing_check(side_mask: np.ndarray | None, ortho: Image.Image, tol: dict) -> dict:
    """Боковой вид против ортопроекции черновика 1b: силуэты (маска инструмента, дыры залиты), вид растянут на кадр
    орто; IoU прямо и с зеркалом орто. verdict OK | MIRRORED | UNCLEAR | NO_MASK."""
    om = measure_view(ortho, tol)
    if side_mask is None or om.get("mask") is None:
        return {"verdict": "NO_MASK", "iou_direct": None, "iou_mirror": None}
    o = ndi.binary_fill_holes(om["_mask"])
    h, w = o.shape
    s = ndi.binary_fill_holes(side_mask).astype(np.uint8) * 255
    s = np.asarray(Image.fromarray(s).resize((w, h), Image.Resampling.NEAREST)) > 127
    direct, mirror = _iou(s, o), _iou(s, o[:, ::-1])
    m = tol["facing_margin"]
    verdict = "MIRRORED" if mirror > direct + m else ("OK" if direct > mirror + m else "UNCLEAR")
    return {"verdict": verdict, "iou_direct": round(direct, 4), "iou_mirror": round(mirror, 4),
            "ortho_size": [w, h], "margin": m}


def facing_row(facing: dict, scope: str, tol: dict, ortho_path: str) -> dict:
    v = facing["verdict"]
    low = v != "NO_MASK" and max(facing["iou_direct"], facing["iou_mirror"]) < tol["facing_iou_warn"]
    res = "FAIL" if v == "MIRRORED" else ("WARN" if v in ("UNCLEAR", "NO_MASK") or low else "PASS")
    return {"id": "view.facing", "scope": scope, "result": res,
            "value": {"verdict": v, "iou_direct": facing["iou_direct"], "iou_mirror": facing["iou_mirror"],
                      "ortho": ortho_path},
            "limit": f"IoU прямо > зеркало + {tol['facing_margin']} (WARN: оба < {tol['facing_iou_warn']})",
            "message": "боковой вид смотрит в ту же сторону, что ортопроекция SIDE_VIEW черновика (F8)"}


# ------------------------------------------------------------------------------------------------------- палитра
def load_palette(path: Path) -> list:
    """Поддерживаемые формы palette.json: {"main":[{name,hex}], "accent":{name,hex}} (образец Robin Hood),
    {"colors":[...]}/{"palette":[...]}, список [{name,hex}|"#hex"], словарь {зона: "#hex"}."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise InputError(f"palette: не читается {path}: {exc}") from exc

    def item(x, role, idx):
        if isinstance(x, str):
            name, hx = f"{role}{idx + 1}", x
        elif isinstance(x, dict) and "hex" in x:
            name, hx = str(x.get("name") or x.get("zone") or f"{role}{idx + 1}"), x["hex"]
        else:
            raise InputError(f"palette: элемент без hex: {x!r}")
        m = HEX_RE.match(str(hx).strip())
        if not m:
            raise InputError(f"palette: неверный hex {hx!r}")
        return {"name": name, "hex": "#" + m.group(1).upper(), "role": role}

    out = []
    if isinstance(data, dict) and ("main" in data or "accent" in data):
        for i, x in enumerate(data.get("main") or []):
            out.append(item(x, "main", i))
        acc = data.get("accent")
        for i, x in enumerate(acc if isinstance(acc, list) else ([acc] if acc else [])):
            out.append(item(x, "accent", i))
    elif isinstance(data, dict) and isinstance(data.get("colors") or data.get("palette"), list):
        for i, x in enumerate(data.get("colors") or data.get("palette")):
            out.append(item(x, "color", i))
    elif isinstance(data, list):
        for i, x in enumerate(data):
            out.append(item(x, "color", i))
    elif isinstance(data, dict):
        for i, (k, v) in enumerate((k, v) for k, v in data.items() if isinstance(v, str) and HEX_RE.match(v.strip())):
            out.append({"name": k, "hex": "#" + HEX_RE.match(v.strip()).group(1).upper(), "role": "color"})
    if not out:
        raise InputError(f"palette: в {path} нет цветов")
    return out


def palette_asset_id(path: Path) -> str | None:
    """`asset_id` palette.json (форма concept-sheet.md §4.5, пишет make_tasks.py); нет поля или другая форма — None."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    aid = data.get("asset_id") if isinstance(data, dict) else None
    return aid if isinstance(aid, str) and aid else None


def palette_presence(palette: list, views: dict) -> None:
    """Справочно: доля пикселей фигуры (все виды) в RGB-расстоянии ≤ 40 от свотча. Не проверка."""
    px = [m["_rgb"][m["_mask"]] for m in views.values() if m.get("_mask") is not None]
    if not px:
        return
    allpx = np.concatenate(px)
    if allpx.shape[0] > 400_000:
        allpx = allpx[np.linspace(0, allpx.shape[0] - 1, 400_000).astype(np.int64)]
    for sw in palette:
        c = np.array([int(sw["hex"][i:i + 2], 16) for i in (1, 3, 5)], float)
        d = np.sqrt(((allpx - c) ** 2).sum(1))
        sw["figure_share_within_40_pct"] = round(float(np.mean(d <= 40.0)) * 100.0, 2)


# ---------------------------------------------------------------------------------------------------------- проверки
def run_checks(views: dict, tol: dict, min_top_pct: float | None = None) -> list:
    rows = []

    def add(cid, scope, ok, value, limit, msg, warn=False):
        res = "PASS" if ok else ("WARN" if warn else "FAIL")
        rows.append({"id": cid, "scope": scope, "result": res, "value": value, "limit": limit, "message": msg})

    def tiered(cid, scope, ok_fail, ok_warn, value, limit, msg):
        res = "FAIL" if not ok_fail else ("WARN" if not ok_warn else "PASS")
        rows.append({"id": cid, "scope": scope, "result": res, "value": value, "limit": limit, "message": msg})

    def spread(cid, value, key, unit, msg):
        w, f = tol[key + "_warn_pct"], tol[key + "_fail_pct"]
        tiered(cid, "set", value <= f, value <= w, round(value, 3), f"<= {f} {unit} (WARN > {w})", msg)

    names = list(views)
    sizes = {v: views[v]["size"] for v in names}
    ref = sizes[names[0]]
    worst = 0.0
    for v in names:
        for k in (0, 1):
            worst = max(worst, abs(sizes[v][k] - ref[k]) / ref[k] * 100.0)
    add("set.size", "set", worst <= tol["size_rel_pct"], {"sizes": sizes, "max_delta_pct": round(worst, 3)},
        f"<= {tol['size_rel_pct']} %", "все виды одного размера и аспекта")
    exact = all(sizes[v] == ref for v in names)
    add("set.size_exact", "set", exact, sizes, "равны до пикселя",
        "размеры отличаются на пиксели: сравнение идёт в % кадра", warn=True)

    meds = {}
    for v in names:
        m = views[v]
        b = m["border"]
        meds[v] = np.array(b["median_rgb"])
        add("view.alpha", v, not (m["alpha"]["present"] and m["alpha"]["min"] < 255), m["alpha"], "без прозрачности",
            "альфа-канал с прозрачностью: Tripo и image_gen ждут RGB", warn=True)
        tiered("view.border_uniform", v, b["share_within_tone_fail"] >= tol["border_share_min"],
               b["share_within_tone_warn"] >= tol["border_share_min"],
               {"share_warn_tone": b["share_within_tone_warn"], "share_fail_tone": b["share_within_tone_fail"],
                "p99_deviation": b["p99_deviation"]},
               f">= {tol['border_share_min']} при ±{tol['border_tone_fail']} (WARN при ±{tol['border_tone_warn']})",
               "рамка 2 % кадра — ровный фон без объектов")
        add("view.bg_neutral", v, b["neutral_delta"] <= tol["bg_neutral_max"], b["median_rgb"],
            f"|R-G|,|G-B| <= {tol['bg_neutral_max']}", "фон нейтрально-серый")
        add("view.bg_dark", v, b["luma"] <= tol["bg_dark_luma_warn"], b["luma"], f"<= {tol['bg_dark_luma_warn']}",
            "фон тёмно-серый (норма hero-quality-v1)", warn=True)
        mk = m.get("mask")
        if mk is None:
            add("view.mask", v, False, None, "фигура найдена", "фигура не отделяется от фона")
            continue
        add("view.mask", v, tol["mask_area_min_pct"] <= mk["area_pct"] <= tol["mask_area_max_pct"], mk["area_pct"],
            f"{tol['mask_area_min_pct']}..{tol['mask_area_max_pct']} %", "маска фигуры правдоподобна")
        add("view.top_margin", v, mk["top_pct"] >= tol["top_min_pct"], mk["top_pct"], f">= {tol['top_min_pct']} %",
            "верх фигуры не касается края")
        if min_top_pct is not None:
            add("view.frame_top", v, mk["top_pct"] >= min_top_pct, mk["top_pct"], f">= {min_top_pct} %",
                "верхняя точка не выше рамки ядра (1a: y >= 4 %)", warn=True)
        add("view.bottom_margin", v, mk["bottom_pct"] <= tol["bottom_max_pct"], mk["bottom_pct"],
            f"<= {tol['bottom_max_pct']} %", "низ подставки в кадре")
        side = min(mk["left_pct"], 100.0 - mk["right_pct"])
        add("view.side_margin", v, side >= tol["side_min_pct"], round(side, 3), f">= {tol['side_min_pct']} %",
            "фигура не обрезана по бокам")
        biggest_other = max(mk["other_components_pct"], default=0.0)
        add("view.single_component", v, biggest_other < tol["extra_component_warn_pct"], mk["other_components_pct"],
            f"прочие < {tol['extra_component_warn_pct']} %", "одна крупная связная фигура", warn=True)

    bg_spread = max(float(np.abs(meds[a] - meds[b]).max()) for a in names for b in names)
    add("set.bg_same", "set", bg_spread <= tol["bg_between_views_max"], round(bg_spread, 1),
        f"<= {tol['bg_between_views_max']}", "один фон на набор")

    mks = {v: views[v]["mask"] for v in names if views[v].get("mask")}
    if len(mks) == len(names) and len(names) > 1:
        bots = [m["bottom_pct"] for m in mks.values()]
        cxs = [m["base_center_x_pct"] for m in mks.values()]
        hs = [m["height_pct"] for m in mks.values()]
        spread("set.base_bottom", max(bots) - min(bots), "base_bottom_spread", "% высоты",
            "низ подставки на одной линии земли")
        spread("set.base_center", max(cxs) - min(cxs), "base_center_spread", "% ширины",
            "центр подставки на одной вертикали")
        hsp = (max(hs) - min(hs)) / max(hs) * 100.0
        spread("set.height", hsp, "height_spread", "% от наибольшего", "рост фигуры одинаков во всех видах")
    return rows


# ---------------------------------------------------------------------------------------------------------- лист
def _font(size: int):
    for cand in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def _dashed_h(d, x0, x1, y, fill, width=2, dash=14, gap=8):
    x = x0
    while x < x1:
        d.line([(x, y), (min(x + dash, x1), y)], fill=fill, width=width)
        x += dash + gap


def _dashed_v(d, x, y0, y1, fill, width=2, dash=14, gap=8):
    y = y0
    while y < y1:
        d.line([(x, y), (x, min(y + dash, y1))], fill=fill, width=width)
        y += dash + gap


SWATCH_W, SWATCH_PITCH_MIN, SWATCH_LABEL_GAP = 110, 150, 12


def fit_text(text: str, font, max_w: float) -> str:
    """Текст, укороченный с «…» до ширины max_w px этим шрифтом (целиком, если влезает)."""
    if font.getlength(text) <= max_w:
        return text
    while text and font.getlength(text.rstrip() + "…") > max_w:
        text = text[:-1]
    return text.rstrip() + "…"


def swatch_layout(palette: list, font, avail_w: float) -> tuple[int, list]:
    """Шаг свотчей и подписи (hex, имя) в две строки (C13: длинные имена в одну строку с hex налезали на соседний
    свотч). Шаг — по самой широкой подписи, но все свотчи в ряду avail_w; имя укорачивается до шага − зазор."""
    n = max(1, len(palette))
    widest = max([font.getlength(sw["hex"]) for sw in palette] + [font.getlength(sw["name"]) for sw in palette] + [0])
    pitch = int(max(SWATCH_PITCH_MIN, widest + SWATCH_LABEL_GAP))
    pitch = max(SWATCH_W + SWATCH_LABEL_GAP, min(pitch, int(avail_w // n)))
    labels = [(sw["hex"], fit_text(sw["name"], font, pitch - SWATCH_LABEL_GAP)) for sw in palette]
    return pitch, labels


def draw_sheet(key: str, role: str, images: dict, views: dict, checks: list, palette: list, verdict: str,
               out_path: Path, cell_h: int = 900) -> None:
    names = list(images)
    pad, gutter, ruler_w, head_h = 24, 36, 96, 86
    f_big, f_mid, f_small = _font(30), _font(22), _font(17)
    scaled = []
    for v in names:
        im = images[v].convert("RGB")
        cw = int(round(im.width * cell_h / im.height))
        scaled.append(im.resize((cw, cell_h), Image.Resampling.LANCZOS))
    cells_w = sum(s.width for s in scaled) + gutter * (len(scaled) - 1)
    info_h = 3 * 24 + 16
    pal_h = 0 if not palette else 130
    W = pad + ruler_w + cells_w + pad
    H = head_h + 40 + cell_h + info_h + pal_h + pad
    sheet = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    n_fail = sum(c["result"] == "FAIL" for c in checks)
    n_warn = sum(c["result"] == "WARN" for c in checks)
    vcol = (90, 210, 120) if verdict == "PASS" else (240, 80, 70)
    d.text((pad, 18), f"{key}  |  {SCHEMA}  |  role {role}", font=f_big, fill=(235, 235, 235))
    d.text((pad, 54), f"{verdict}  FAIL {n_fail}  WARN {n_warn}   guides #00C8FF: ground / top / base centre; "
                      f"ruler = % of frame height", font=f_small, fill=vcol)
    y0 = head_h + 40
    x0 = pad + ruler_w
    # ячейки
    xs = []
    x = x0
    for v, s in zip(names, scaled):
        sheet.paste(s, (x, y0))
        xs.append(x)
        vres = "FAIL" if any(c["scope"] == v and c["result"] == "FAIL" for c in checks) else "ok"
        d.text((x, y0 - 32), f"{v}  {s.width}x{cell_h} (src {images[v].width}x{images[v].height})  {vres}",
               font=f_small, fill=(240, 80, 70) if vres == "FAIL" else (220, 220, 220))
        x += s.width + gutter
    x_end = x - gutter
    # сетка 10 % и линейка
    faint = (0, 200, 255)
    for pct in range(0, 101, 5):
        y = y0 + int(round(pct / 100.0 * cell_h))
        tick = 18 if pct % 10 == 0 else 9
        d.line([(x0 - tick, y), (x0, y)], fill=(200, 200, 200), width=2)
        if pct % 10 == 0:
            d.text((pad, y - 10), f"{pct}%", font=f_small, fill=(200, 200, 200))
            for xi, s in zip(xs, scaled):
                _dashed_h(d, xi, xi + s.width, y, fill=tuple(int(c * 0.45) for c in faint), width=1, dash=6, gap=10)
    mks = [views[v].get("mask") for v in names]
    if all(mks):
        ground = float(np.median([m["bottom_pct"] for m in mks]))
        topm = float(np.median([m["top_pct"] for m in mks]))
        cx_med = float(np.median([m["base_center_x_pct"] for m in mks]))
        for pct, label in ((ground, "ground"), (topm, "top")):
            y = y0 + int(round(pct / 100.0 * cell_h))
            d.line([(x0 - 4, y), (x_end, y)], fill=GUIDE_RGB, width=2)
            d.text((x_end - 120, y + (4 if label == "ground" else -24)), f"{label} {pct:.1f}%", font=f_small,
                   fill=GUIDE_RGB)
        for xi, s, m in zip(xs, scaled, mks):
            cx = xi + int(round(cx_med / 100.0 * s.width))
            _dashed_v(d, cx, y0, y0 + cell_h, fill=GUIDE_RGB, width=2)
            own_cx = xi + int(round(m["base_center_x_pct"] / 100.0 * s.width))
            own_b = y0 + int(round(m["bottom_pct"] / 100.0 * cell_h))
            own_t = y0 + int(round(m["top_pct"] / 100.0 * cell_h))
            for yy in (own_b, own_t):
                d.line([(xi, yy), (xi + 28, yy)], fill=(255, 255, 255), width=3)
                d.line([(xi + s.width - 28, yy), (xi + s.width, yy)], fill=(255, 255, 255), width=3)
            d.line([(own_cx, own_b - 22), (own_cx, own_b + 6)], fill=(255, 255, 255), width=3)
        # подписи измерений
        for xi, m in zip(xs, mks):
            ty = y0 + cell_h + 10
            for line in (f"top {m['top_pct']:.1f}%  ground {m['bottom_pct']:.1f}%  height {m['height_pct']:.1f}%",
                         f"base x {m['base_center_x_pct']:.1f}%  w {m['base_width_pct']:.1f}%  "
                         f"base top ~{m['base_top_pct_est']:.1f}%",
                         f"side margin {min(m['left_pct'], 100 - m['right_pct']):.1f}%  "
                         f"area {m['area_pct']:.1f}%"):
                d.text((xi, ty), line, font=f_small, fill=(210, 210, 210))
                ty += 24
    if palette:
        py = y0 + cell_h + info_h + 10
        px = x0
        pitch, labels = swatch_layout(palette, f_small, W - pad - x0)
        for sw, (hx, name) in zip(palette, labels):
            if px + SWATCH_W > W - pad:
                break
            rgb = tuple(int(sw["hex"][i:i + 2], 16) for i in (1, 3, 5))
            d.rectangle([px, py, px + SWATCH_W, py + 70], fill=rgb, outline=(230, 230, 230), width=2)
            d.text((px, py + 74), hx, font=f_small, fill=(220, 220, 220))
            d.text((px, py + 96), name, font=f_small, fill=(220, 220, 220))
            px += pitch
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path, format="PNG", optimize=True)


# ---------------------------------------------------------------------------------------------------------- CLI
def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, dest="set_dir", help="каталог набора с <key>-<view>.png")
    ap.add_argument("--key", required=True, help="content-key (kebab), префикс файлов видов")
    ap.add_argument("--views", default="front,side,back", help="виды через запятую (по умолчанию front,side,back)")
    ap.add_argument("--role", default="hero", choices=ROLES, help="роль из карточки (в отчёт и на лист; допуски общие)")
    ap.add_argument("--palette", default=None, help="palette.json (по умолчанию <set>/palette.json, если есть)")
    ap.add_argument("--sheet", action="store_true", help="нарисовать лист приёмки sheet-<key>.png")
    ap.add_argument("--out", default=None, help="куда писать отчёт и лист (по умолчанию --set)")
    ap.add_argument("--min-top-pct", type=float, default=None,
                    help="рамка ядра: верх маски выше y N %% кадра → WARN view.frame_top (шаг 1a: 4)")
    ap.add_argument("--side-ortho", default=None,
                    help="ortho_<SIDE_VIEW>.png черновика 1b: проверка ракурса бокового вида view.facing (F8)")
    ap.add_argument("--side-view", default="side", help="имя бокового вида в --views для --side-ortho (по умолчанию side)")
    return ap.parse_args(argv)


def _utf8_streams() -> None:
    """Консоль/пайп cp1251 (Codex через PowerShell, Git Bash агента) не должен ронять печать «→» (код 1 = FAIL!)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv=None) -> int:
    _utf8_streams()
    try:
        args = parse_args(argv)
    except SystemExit as exc:  # argparse: --help → 0, ошибка аргументов → 2
        return int(exc.code or 0)
    try:
        return _run(args)
    except InputError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — сбой инструмента не должен выглядеть как «есть FAIL» (код 1)
        print(f"ERROR: внутренний сбой {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2


def _run(args) -> int:
    set_dir = Path(args.set_dir)
    if not set_dir.is_dir():
        raise InputError(f"нет каталога набора {set_dir}")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", args.key):
        raise InputError(f"--key должен быть kebab-case: {args.key!r}")
    names = [v.strip() for v in args.views.split(",") if v.strip()]
    if not names or len(set(names)) != len(names):
        raise InputError(f"--views пуст или с повторами: {args.views!r}")
    out_dir = Path(args.out) if args.out else set_dir
    tol = dict(TOLERANCES)
    if args.min_top_pct is not None and not 0.0 <= args.min_top_pct < 50.0:
        raise InputError(f"--min-top-pct вне 0..50: {args.min_top_pct}")

    palette, pal_path = [], None
    if args.palette:
        pal_path = Path(args.palette)
        if not pal_path.is_file():
            raise InputError(f"нет файла палитры {pal_path}")
    elif (set_dir / "palette.json").is_file():
        pal_path = set_dir / "palette.json"
    if pal_path:
        palette = load_palette(pal_path)
    ortho = None
    if args.side_ortho:
        if args.side_view not in names:
            raise InputError(f"--side-ortho: вида {args.side_view!r} нет в --views {args.views!r}")
        try:
            ortho = Image.open(args.side_ortho)
            ortho.load()
        except OSError as exc:
            raise InputError(f"--side-ortho: не читается {args.side_ortho}: {exc}") from exc

    images, inputs, views = {}, [], {}
    for v in names:
        p = set_dir / f"{args.key}-{v}.png"
        if not p.is_file():
            raise InputError(f"нет файла вида {p}")
        try:
            im = Image.open(p)
            im.load()
        except OSError as exc:
            raise InputError(f"не читается {p}: {exc}") from exc
        images[v] = im
        inputs.append({"view": v, "path": p.as_posix(), "sha256": sha256(p), "format": im.format,
                       "mode": im.mode, "size": [im.width, im.height]})
        views[v] = measure_view(im, tol)

    checks = run_checks(views, tol, args.min_top_pct)
    facing = None
    if ortho is not None:
        sv = views[args.side_view]
        facing = facing_check(sv.get("_mask"), ortho, tol)
        facing.update({"view": args.side_view, "ortho": Path(args.side_ortho).as_posix(),
                       "ortho_sha256": sha256(Path(args.side_ortho))})
        checks.append(facing_row(facing, args.side_view, tol, facing["ortho"]))
    if palette:
        palette_presence(palette, views)
    summary = {r: sum(c["result"] == r for c in checks) for r in ("PASS", "WARN", "FAIL")}
    verdict = "PASS" if summary["FAIL"] == 0 else "FAIL"
    sheet_path = out_dir / f"sheet-{args.key}.png"
    if args.sheet:
        draw_sheet(args.key, args.role, images, views, checks, palette, verdict, sheet_path)
    for m in views.values():
        m.pop("_mask", None)
        m.pop("_rgb", None)
    report = {
        "schema": SCHEMA,
        "tool": TOOL,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "set": set_dir.as_posix(),
        "key": args.key,
        "role": args.role,
        "views": names,
        "inputs": inputs,
        "raw_files_modified": False,
        "tolerances": tol,
        "tolerances_note": "решение скилла (DECISIONS Р-9), калибровка на art/imagegen/hero-quality-v1 — "
                           "tools/art/concept/README.md",
        "frame": {"min_top_pct": args.min_top_pct},
        **({"facing": facing} if facing is not None else {}),
        "measurements": views,
        "checks": checks,
        "summary": summary,
        "verdict": verdict,
        "palette": {"path": pal_path.as_posix() if pal_path else None,
                    "asset_id": palette_asset_id(pal_path) if pal_path else None, "swatches": palette},
        "sheet": sheet_path.as_posix() if args.sheet else None,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "checks-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                                                encoding="utf-8")
    for c in checks:
        if c["result"] != "PASS":
            print(f"{c['result']:4} {c['id']:22} {c['scope']:8} value={json.dumps(c['value'], ensure_ascii=False)} "
                  f"limit={c['limit']}  # {c['message']}")
    print(f"{verdict}: PASS {summary['PASS']} WARN {summary['WARN']} FAIL {summary['FAIL']} → "
          f"{(out_dir / 'checks-report.json').as_posix()}" + (f", {sheet_path.as_posix()}" if args.sheet else ""))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
