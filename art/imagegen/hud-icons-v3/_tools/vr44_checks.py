#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Листы проверок набора VR44 (VS-2 A2, карточки IC-38…IC-61; шаг A3 — IC-46, IC-48, IC-52, IC-55, IC-59, флаг --a3) — пункты acceptance сверх листа приёмки:
соседи в сером, цифры, зоны досок, ×8 чипов, «▼» = «▲» на 180°, курсоры на светлом и тёмном, кадры «занято».

    python art/imagegen/hud-icons-v3/_tools/vr44_checks.py [docs/game-design/evidence/VISUAL]

Пишет в <root>/<IC-NN>/: check-*.png и checks.json (замеры). Всё рисует движок draw_icons.py из вектора (как экспорты
sizes/ и layers/); цифры — образец runtime-текста font.card. Цвета зон — backend/prisma/fixtures/boards/
{marmoreal,sarpedon}.topology.json; #A43839, #D39BA5, #DEDEE0 — из строк карточек (палуба Sarpedon, розовая зона и
светлое пространство Marmoreal).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import draw_icons as D  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CARDS = {"IC-38": "badge-order", "IC-39": "badge-order-p2", "IC-40": "badge-refuse", "IC-41": "badge-conflict",
         "IC-42": "badge-ally", "IC-43": "badge-attack-from", "IC-44": "team-chip-p1", "IC-45": "team-chip-p2",
         "IC-47": "state-warning", "IC-50": "marker-slot-scheme", "IC-51": "marker-slot-boost", "IC-53": "ui-menu",
         "IC-54": "ui-close", "IC-56": "ui-step", "IC-58": "cursor-default", "IC-60": "cursor-unavailable",
         "IC-61": "cursor-busy"}
NAVY, CREAM, GREY = "#061623", "#F9EBDB", "#808080"
ZONES = {"Marmoreal yellow": "#E6CDB2", "Marmoreal blue": "#C4CDD4", "Sarpedon yellow": "#FEFFB9",
         "Sarpedon blue": "#BFCFD9"}
RED_ZONES = {"Sarpedon red deck": "#A43839", "Marmoreal pink zone": "#D39BA5"}
CURSOR_BGS = {"Marmoreal light space": "#DEDEE0", "Sarpedon red deck": "#A43839", "panel.bg": NAVY}


def rgba(hexv):
    return tuple(int(hexv[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def grey(im):
    """Серый Rec.709 по закодированным sRGB (как sheet.py и лист приёмки)."""
    a = np.asarray(im.convert("RGBA")).astype(np.float64)
    y = np.clip(np.rint(a[..., :3] @ np.array([0.2126, 0.7152, 0.0722])), 0, 255)
    out = np.dstack([y, y, y, a[..., 3]]).astype(np.uint8)
    return Image.fromarray(out, "RGBA")


def cell(im, bg, zoom, pad=2):
    base = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), rgba(bg))
    base.alpha_composite(im, (pad, pad))
    return D.xN(base, zoom)


def compose(title, rows, path):
    """rows: [(подпись, [картинка, …])] — подписи слева, картинки в ряд; без масштабирования."""
    gap, name_w = 12, 260
    W = max(name_w + sum(im.width + gap for im in ims) for _, ims in rows) + gap
    H = 44 + sum(max(im.height for im in ims) + gap for _, ims in rows)
    sheet = Image.new("RGBA", (max(W, 900), H), D.SHEET_BG)
    sheet.alpha_composite(D.label(sheet.width, 34, title, 14), (0, 4))
    y = 44
    for name, ims in rows:
        h = max(im.height for im in ims)
        sheet.alpha_composite(D.label(name_w, 40, name, 12), (0, y + max(0, (h - 40) // 2)))
        x = name_w
        for im in ims:
            sheet.alpha_composite(im, (x, y))
            x += im.width + gap
        y += h + gap
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.convert("RGB").save(path)
    return os.path.basename(path)


def ex(name, size, **kw):
    """Образец, как на листах: render_example (цифры с 24 px у бейджей, тон чипов) с правками kw."""
    args = dict(D.EXAMPLE.get(name, {}))
    if D.Spec(size).detail == 0 or size < D.TEXT_MIN_PX.get(name, 0):
        args.pop("text", None)
    args.update(kw)
    return D.render(name, size, **args)


def neighbours(names, sizes, bgs=(NAVY, CREAM, GREY), zoom=4, colour=True):
    rows = []
    for bg in bgs:
        for mode in (("colour", "grey") if colour else ("grey",)):
            ims = []
            for s in sizes:
                for n in names:
                    im = cell(ex(n, s), bg, zoom)
                    ims.append(grey(im) if mode == "grey" else im)
            rows.append((f"{mode} · {bg} · {' | '.join(names)} @ {'/'.join(map(str, sizes))}", ims))
    return rows


def on_zones(name, sizes, zones, zoom=4):
    rows = []
    for zname, hexv in zones.items():
        for mode in ("colour", "grey"):
            ims = [cell(ex(name, s), hexv, zoom) for s in sizes]
            rows.append((f"{zname} {hexv} · {mode}", [grey(i) for i in ims] if mode == "grey" else ims))
    return rows


def mean_grey(im):
    a = np.asarray(grey(im))
    m = a[..., 3] > 128
    return round(float(a[..., 0][m].mean()), 1) if m.any() else None


def checks_badge_order(cid, name, out):
    team = "P1" if name == "badge-order" else "P2"
    files, meas = [], {}
    rows = []
    for s in (24, 32):
        ims = [cell(ex(name, s, text=str(d)), NAVY, 4) for d in list(range(1, 10)) + [10]]
        rows.append((f"{team} · цифры 1…9, 10 @ {s} px ×4 (font.card cap 10,5 / 9,5 u)", ims))
        rows.append((f"{team} · серый @ {s} px", [grey(i) for i in ims]))
    files.append(compose(f"{cid} {name}: цифры runtime-текстом (образец) при 24 и 32 px; < 24 px цифры нет", rows,
                         os.path.join(out, "check-digits.png")))
    files.append(compose(f"{cid} {name}: на жёлтой и синей зонах обеих карт (keyline держит границу), 16 / 21 / 24 / 32 px ×4",
                         on_zones(name, (16, 21, 24, 32), ZONES), os.path.join(out, "check-zones.png")))
    files.append(compose(f"{cid}: P1 и P2 рядом — цвет и серый (блок P1 / P2), 16 / 21 / 24 / 32 px ×4",
                         neighbours(["badge-order", "badge-order-p2"], (16, 21, 24, 32)),
                         os.path.join(out, "check-p1-p2.png")))
    sp = D.Spec(1024)
    _, top_in, apex_in, block_bot, fc = D.badge_geom(sp)
    meas["field_u"] = {"top_in": round(top_in, 3), "block_bottom": round(block_bot, 3), "apex_in": round(apex_in, 3),
                       "digit_centre": round(fc, 3), "cap_u": list(D.BADGE_CAP), "digit_centre_shift_u": D.BADGE_DIGIT_DY}
    blk = {}
    for s in (16, 24, 32):
        im = np.asarray(D.render("badge-order", s, layer="team"))
        blk[str(s)] = int((im[..., 3] > 128).any(1).sum())
    meas["block_rows_px"] = blk
    meas["block_grey"] = {"P1": round(float(np.array([0.2126, 0.7152, 0.0722]) @ np.array(rgba(D.TOKENS["team.p1.screen"])[:3])), 1),
                          "P2": round(float(np.array([0.2126, 0.7152, 0.0722]) @ np.array(rgba(D.TOKENS["team.p2.screen"])[:3])), 1)}
    return files, meas


def checks_refuse(cid, name, out):
    files = [compose(f"{cid} {name}: на красной палубе Sarpedon и розовой зоне Marmoreal — границу держит плашка, 16 / 21 / 24 / 32 px ×4",
                     on_zones(name, (16, 21, 24, 32), RED_ZONES), os.path.join(out, "check-red-zones.png")),
             compose(f"{cid}: в сером рядом с badge-conflict (лента) и state-pending-move (тело 91), 16 / 24 / 32 px ×4",
                     neighbours([name, "badge-conflict", "state-pending-move"], (16, 24, 32)),
                     os.path.join(out, "check-neighbours.png"))]
    meas = {"x_stroke_px": {str(s): D.Spec(s).px(3.0, 2 if D.Spec(s).detail == 0 else 1) for s in (16, 18, 21, 24, 32)},
            "body_grey": {n: mean_grey(D.render(n, 32, layer="body")) for n in (name, "state-pending-move")}}
    return files, meas


def checks_conflict(cid, name, out):
    files = [compose(f"{cid} {name}: рядом с badge-order и badge-refuse — цвет и серый, 16 / 21 / 24 / 32 px ×4",
                     neighbours([name, "badge-order", "badge-refuse"], (16, 21, 24, 32)),
                     os.path.join(out, "check-neighbours.png")),
             compose(f"{cid} {name}: на жёлтой и синей зонах обеих карт, 16 / 21 / 24 / 32 px ×4",
                     on_zones(name, (16, 21, 24, 32), ZONES), os.path.join(out, "check-zones.png"))]
    meas = {}
    for s in (16, 24, 32):
        g = np.asarray(D.render(name, s, layer="glyph"))
        ys = np.where((g[..., 3] > 128).any(1))[0]
        meas[f"bang_rows_{s}px"] = [int(ys.min()), int(ys.max())] if len(ys) else None
    return files, meas


def checks_simple(cid, name, out, others, sizes, title, bgs=(NAVY, CREAM, GREY)):
    return [compose(f"{cid} {name}: {title}", neighbours([name] + others, sizes, bgs),
                    os.path.join(out, "check-neighbours.png"))], {}


def checks_chip(cid, name, out):
    rows = []
    for s in (9, 12):
        for bg in (NAVY, CREAM, GREY):
            ims = [cell(ex(n, s), bg, 8) for n in ("team-chip-p1", "team-chip-p2")]
            rows.append((f"{s} px ×8 · {bg} · цвет | серый", ims + [grey(i) for i in ims]))
    files = [compose(f"{cid}: чипы 9 и 12 px ×8 nearest (лист проверки, в UE не импортируются) — круг не квадрат, шестигранник гранями",
                     rows, os.path.join(out, "check-chips-x8.png")),
             compose(f"{cid}: P1 и P2 формой в сером, 18 / 24 / 32 / 48 px ×4 (24 su при 720p / 100 % / 1440p / 150 %)",
                     neighbours(["team-chip-p1", "team-chip-p2"], (18, 24, 32, 48)),
                     os.path.join(out, "check-p1-p2.png"))]
    meas = {}
    for s in (9, 12, 18, 24, 32):
        a = np.asarray(D.render(name, s))[..., 3] > 128
        ys, xs = np.where(a)
        meas[f"opaque_bbox_{s}px"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        meas[f"opaque_px_{s}"] = int(a.sum())
    return files, meas


def checks_slot(cid, name, out):
    return [compose(f"{cid}: две ленты слота рядом (IC-52 «сброс» — после пакета CX-04), цвет и серый, 18 / 24 / 32 / 48 px ×4",
                    neighbours(["marker-slot-scheme", "marker-slot-boost"], (18, 24, 32, 48)),
                    os.path.join(out, "check-neighbours.png"))], {
        "body_grey": {n: mean_grey(D.render(n, 32)) for n in ("marker-slot-scheme", "marker-slot-boost")}}


def checks_menu(cid, name, out):
    files = [compose(f"{cid}: ui-menu рядом с resource-card при 18 и 24 px (×4), цвет и серый",
                     neighbours([name, "resource-card"], (18, 24)), os.path.join(out, "check-neighbours.png"))]
    rows = []
    for s in (18, 24, 32):
        im = D._tinted(D.render(name, s), D.C["body"])
        rows.append((f"главная кнопка: маска × card.navy @ {s} px ×4 на card.cream", [cell(im, CREAM, 4), grey(cell(im, CREAM, 4))]))
    files.append(compose(f"{cid}: белая маска, UMG красит card.navy на главной кнопке", rows,
                         os.path.join(out, "check-tint.png")))
    return files, {}


def centroid(im, mask=None):
    a = np.asarray(im).astype(np.float64)
    w = a[..., 3] / 255.0
    if mask is not None:
        w = w * mask(a)
    ys, xs = np.mgrid[0:a.shape[0], 0:a.shape[1]]
    return float((w * (xs + 0.5)).sum() / w.sum()), float((w * (ys + 0.5)).sum() / w.sum())


def checks_step(cid, name, out):
    rows, meas = [], {}
    for bg in (NAVY, CREAM, GREY):
        ims = []
        for s in (18, 24, 32, 48):
            up = D.render(name, s)
            ims += [cell(up, bg, 4), cell(up.rotate(180), bg, 4)]
        rows.append((f"вверх | вниз (RenderTransform 180°) · {bg} · 18 / 24 / 32 / 48 px ×4", ims))
        rows.append(("серый", [grey(i) for i in ims]))
    files = [compose(f"{cid} {name}: вверх и вниз — тот же значок, повёрнутый на 180° вокруг центра холста", rows,
                     os.path.join(out, "check-up-down.png"))]
    white = lambda a: (a[..., :3].min(-1) > 200).astype(np.float64)   # белое тело (маска)
    for s in (16, 18, 21, 24, 32, 36, 48, 64, 1024):
        up = D.render(name, s)
        cx, cy = centroid(up, white)
        ax, ay = centroid(up)
        meas[str(s)] = {"body_centroid_px": [round(cx, 3), round(cy, 3)], "alpha_centroid_px": [round(ax, 3), round(ay, 3)],
                        "rotation_shift_body_px": round(abs(2 * (cy - s / 2)), 3),
                        "rotation_shift_alpha_px": round(abs(2 * (ay - s / 2)), 3)}
    return files, meas


def checks_cursor(cid, name, out):
    hs = json.load(open(os.path.join(D.ROOT, "cursor-hotspots.json"), encoding="utf-8"))["cursors"][name]
    rows = []
    for bname, hexv in CURSOR_BGS.items():
        ims = [cell(D.render(name, s), hexv, 4) for s in D.CURSOR_SIZES]
        rows.append((f"{bname} {hexv} · цвет", ims))
        rows.append((f"{bname} · серый", [grey(i) for i in ims]))
    marked = []
    for s in D.CURSOR_SIZES:
        im = D.render(name, s).copy()
        x, y = hs[str(s)][:2] if isinstance(hs[str(s)], list) else hs[str(s)]
        base = Image.new("RGBA", im.size, rgba("#DEDEE0"))
        base.alpha_composite(im)
        base.putpixel((x, y), (255, 0, 255, 255))
        marked.append(D.xN(base, 6))
    rows.append(("горячая точка (пиксель #FF00FF) ×6, 24 / 32 / 48 / 64", marked))
    files = [compose(f"{cid} {name}: на светлом пространстве Marmoreal, красной палубе Sarpedon и panel.bg, 24 / 32 / 48 / 64 px ×4",
                     rows, os.path.join(out, "check-cursor.png"))]
    meas = {"hotspot_px": {k: v for k, v in hs.items() if k != "frames"}}
    if name == "cursor-busy":
        frows = []
        for s in (24, 32):
            for bg in (NAVY, "#DEDEE0"):
                ims = [cell(D.render(name, s, frame=f), bg, 4) for f in range(len(D.CURSOR_BUSY_FRAMES))]
                frows.append((f"f00…f07 @ {s} px ×4 · {bg}", ims))
                frows.append(("серый", [grey(i) for i in ims]))
        files.append(compose(f"{cid}: 8 кадров цикла 1500 мс (f00–f03 песок течёт, f04 — переворот 90° на 800 мс, f05–f07 после)",
                             frows, os.path.join(out, "check-frames.png")))
        meas["frames"] = [{"frame": f"f{i:02d}", "sent_index": idx, "angle": a, "t_ms": t}
                          for i, ((idx, a), t) in enumerate(zip(D.CURSOR_BUSY_FRAMES, (0, 183, 367, 550, 800, 950, 1170, 1390)))]
    return files, meas


# VS-2 A3: формы Codex IC-36 (вектор A) и лента слота «сброс»
CARDS_A3 = {"IC-46": "action-end-turn", "IC-48": "card-drop", "IC-52": "marker-slot-discard", "IC-55": "ui-log",
            "IC-59": "cursor-pointer"}
YELLOW = "#F2C14E"   # turn.flash.yellow — тело главной кнопки (02 §4.3)
SCANS = os.path.join(REPO, "scraped-data", "derived", "ue-media-v1", "cards")   # вне git (CP-01)
OFFGIT = os.path.join(REPO, "scraped-data", "derived", "visual-evidence")     # листы со сканами — вне git (ВР-CP12)


def _lin(c):
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def contrast(a, b):
    """Отношение контраста WCAG двух sRGB-цветов (hex)."""
    la, lb = [float(_lin(rgba(x)[:3]) @ np.array([0.2126, 0.7152, 0.0722])) for x in (a, b)]
    hi, lo = max(la, lb), min(la, lb)
    return round((hi + 0.05) / (lo + 0.05), 2)


def scale_about(im, k, opacity=1.0):
    """Состояние кнопки на листе: масштаб k вокруг центра (билинейно, как UMG RenderTransform) и прозрачность."""
    w = max(1, round(im.width * k))
    sc = im.resize((w, w), Image.BILINEAR)
    if w <= im.width:
        out = Image.new("RGBA", im.size, (0, 0, 0, 0))
        out.alpha_composite(sc, ((im.width - w) // 2, (im.height - w) // 2))
    else:
        o = (w - im.width) // 2
        out = sc.crop((o, o, o + im.width, o + im.height))
    if opacity < 1.0:
        a = np.asarray(out).copy()
        a[..., 3] = (a[..., 3] * opacity).astype(np.uint8)
        out = Image.fromarray(a, "RGBA")
    return out


def _padded(im, pad):
    c = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), (0, 0, 0, 0))
    c.alpha_composite(im, (pad, pad))
    return c


def checks_end_turn(cid, name, out):
    from PIL import ImageDraw
    rows = []
    for bg, bname in ((YELLOW, "тело главной кнопки turn.flash.yellow"), (NAVY, "panel.bg")):
        ims = [cell(ex(name, s), bg, 4) for s in (24, 32, 36, 48)]
        rows.append((f"{bname} {bg} · цвет", ims))
        rows.append(("серый", [grey(i) for i in ims]))
    files = [compose(f"{cid} {name}: диск на теле главной кнопки и на panel.bg, 24 / 32 / 36 / 48 px ×4",
                     rows, os.path.join(out, "check-button.png"))]
    srows = []
    for s in (32, 48):
        pad = max(4, s // 6)
        base = D.render(name, s)
        sel = D._over(D.render(name, s, layer="body"), scale_about(D.render(name, s, layer="glyph"), 1.12))
        states = [("normal", _padded(base, pad)), ("hover 1,06", _padded(scale_about(base, 1.06), pad)),
                  ("pressed 0,96", _padded(scale_about(base, 0.96), pad)),
                  ("disabled 0,4", _padded(scale_about(base, 1.0, 0.4), pad)),
                  ("selected: глиф 1,12 (пик импульса)", _padded(sel, pad))]
        foc = _padded(base, pad)
        ring = Image.new("RGBA", foc.size, (0, 0, 0, 0))
        su = s / 48.0                       # диск 48 su
        wr = max(1, round(2 * su))
        r2 = s / 2 + 2 * su + wr / 2
        c0 = pad + s / 2
        ImageDraw.Draw(ring).ellipse((c0 - r2, c0 - r2, c0 + r2, c0 + r2), outline=rgba("#FAF8F2"), width=wr)
        ring.alpha_composite(foc)
        states.append(("focus: кольцо card.glyph 2 su, зазор 2 su", ring))
        for bg in (YELLOW, NAVY):
            ims = [D.xN(Image.alpha_composite(Image.new("RGBA", im.size, rgba(bg)), im), 3) for _, im in states]
            srows.append((f"{s} px ×3 · {bg}", ims))
            srows.append(("серый", [grey(i) for i in ims]))
    files.append(compose(f"{cid}: строка состояний 02 §4.3 — normal | hover 1,06 | pressed 0,96 | disabled 0,4 | selected | focus",
                         srows, os.path.join(out, "check-states.png")))
    files.append(compose(f"{cid}: в сером рядом с state-boost и пипсами action-* (тела 94–200), 24 / 32 / 48 px ×4",
                         neighbours([name, "state-boost", "action-attack", "action-defense", "action-maneuver",
                                     "action-scheme"], (24, 32, 48), colour=False),
                         os.path.join(out, "check-neighbours.png")))
    meas = {"contrast": {"glyph_on_navy": contrast("#FAF8F2", NAVY), "navy_disc_on_yellow": contrast(NAVY, YELLOW),
                         "keyline_on_yellow": contrast("#111317", YELLOW),
                         "cream_ring_on_panel_bg": contrast("#F9EBDB", NAVY)},
            "body_grey": {n: mean_grey(D.render(n, 32, layer="body")) for n in
                          (name, "action-attack", "action-defense", "action-maneuver", "action-scheme")},
            "state_boost_grey": mean_grey(D.render("state-boost", 32))}
    return files, meas


def _scan(hero, card, lang="en"):
    p = os.path.join(SCANS, hero, f"{card}.{lang}.png")
    return Image.open(p).convert("RGBA") if os.path.exists(p) else None


def _on_card(scan, icon, card_px, pos):
    """Скан карты, вписанный в card_px, со значком в точке pos (доли ширины / высоты, центр значка)."""
    w, h = card_px
    c = scan.resize((w, h), Image.LANCZOS)
    x, y = round(pos[0] * w - icon.width / 2), round(pos[1] * h - icon.height / 2)
    c.alpha_composite(icon, (max(0, min(w - icon.width, x)), max(0, min(h - icon.height, y))))
    return c


SCAN_CARDS = (("medusa", "gaze-of-stone"), ("medusa", "dash"), ("king-arthur", "excalibur"), ("king-arthur", "feint"))
SCAN_POS = (("справа сверху", (0.88, 0.09)), ("справа снизу", (0.88, 0.92)), ("центр", (0.5, 0.5)))


def scan_rows(name, sizes):
    """Значок 24 su на скане карты руки 150 × 208 su (px/su = size / 24) в трёх точках; яркость скана под значком."""
    rows, meas = [], {}
    for hero, card in SCAN_CARDS:
        scan = _scan(hero, card)
        if scan is None:
            continue
        for s in sizes:
            k = s / 24.0
            card_px = (round(150 * k), round(208 * k))
            small = np.asarray(scan.resize(card_px, Image.LANCZOS)).astype(np.float64)
            ims = []
            for pname, pos in SCAN_POS:
                ims.append(D.xN(_on_card(scan, D.render(name, s), card_px, pos), 2))
                cx, cy = round(pos[0] * card_px[0]), round(pos[1] * card_px[1])
                r = s // 2 + 2
                patch = small[max(0, cy - r):cy + r, max(0, cx - r):cx + r, :3]
                meas.setdefault(f"{hero}:{card}", {})[f"{pname}@{s}"] = round(float(
                    (patch @ np.array([0.2126, 0.7152, 0.0722])).mean()), 1)
            rows.append((f"{hero} / {card} @ {s} px ×2 · " + " | ".join(p for p, _ in SCAN_POS), ims))
            rows.append(("серый", [grey(i) for i in ims]))
    return rows, meas


def _offgit_rel(off, offfiles):
    return [os.path.relpath(os.path.join(off, f), REPO).replace(os.sep, "/") for f in offfiles]


def checks_card_drop(cid, name, out):
    files = [compose(f"{cid} {name}: рядом с state-pending-place (тело 91, эллипс) и resource-card (стопка), 18 / 24 / 32 px ×4",
                     neighbours([name, "state-pending-place", "resource-card"], (18, 24, 32)),
                     os.path.join(out, "check-neighbours.png"))]
    rows, scan_luma = scan_rows(name, (18, 24, 36))
    off = os.path.join(OFFGIT, cid)
    offfiles = [compose(f"{cid} {name}: на светлых и тёмных сканах руки Medusa и King Arthur (вне git), 18 / 24 / 36 px",
                        rows, os.path.join(off, "check-scans.png"))] if rows else []
    meas = {"body_grey": {n: mean_grey(D.render(n, 32, layer="body")) for n in (name, "state-pending-place")},
            "scan_patch_luma": scan_luma, "keyline_vs_cream_edge": contrast("#111317", "#F9EBDB"),
            "offgit_files": _offgit_rel(off, offfiles)}
    return files, meas


def checks_slot_a3(cid, name, out):
    files = [compose(f"{cid}: три ленты слота рядом (схема, BOOST, сброс), цвет и серый, 18 / 24 / 32 / 48 px ×4",
                     neighbours(["marker-slot-scheme", "marker-slot-boost", name], (18, 24, 32, 48)),
                     os.path.join(out, "check-neighbours.png"))]
    rows = []
    for hero, card in SCAN_CARDS:
        scan = _scan(hero, card)
        if scan is None:
            continue
        for s in (24, 32):
            k = s / 32.0                  # лента 32 su на рамке карты 150 × 208 su
            card_px = (round(150 * k), round(208 * k))
            ims = [D.xN(_on_card(scan, D.render(n, s), card_px, (0.86, 0.11)), 2)
                   for n in ("marker-slot-scheme", "marker-slot-boost", name)]
            rows.append((f"{hero} / {card} @ {s} px ×2 · справа сверху · схема | BOOST | сброс", ims))
    off = os.path.join(OFFGIT, cid)
    offfiles = [compose(f"{cid}: ленты слота справа сверху на рамке карты (вне git)", rows,
                        os.path.join(off, "check-scans.png"))] if rows else []
    meas = {"body_grey": {n: mean_grey(D.render(n, 32)) for n in ("marker-slot-scheme", "marker-slot-boost", name)},
            "contrast": {"navy_glyph_on_text_secondary": contrast(NAVY, "#B9B2A6")},
            "offgit_files": _offgit_rel(off, offfiles)}
    return files, meas


def checks_log(cid, name, out):
    files = [compose(f"{cid}: ui-log рядом с ui-menu и resource-card при 18 и 24 px (×4), цвет и серый",
                     neighbours([name, "ui-menu", "resource-card"], (18, 24)), os.path.join(out, "check-neighbours.png")),
             compose(f"{cid}: ui-log рядом с action-end-turn и state-boost (общий диск), 24 / 32 / 48 px ×4, серый",
                     neighbours([name, "action-end-turn", "state-boost"], (24, 32, 48), colour=False),
                     os.path.join(out, "check-discs.png"))]
    meas = {f"rows_{s}px": len(list(D._log_rects(D.Spec(s)))) // 2 for s in (16, 18, 21, 24, 32, 48)}
    return files, meas


def checks_pointer(cid, name, out):
    files, meas = checks_cursor(cid, name, out)
    files.append(compose(f"{cid}: указатель рядом с cursor-default и cursor-unavailable, серый, 24 / 32 / 48 px ×4",
                         neighbours([name, "cursor-default", "cursor-unavailable"], (24, 32, 48),
                                    bgs=("#DEDEE0", NAVY, GREY), colour=False),
                         os.path.join(out, "check-neighbours.png")))
    return files, meas


def run_a3(root, only=None):
    report = {}
    for cid, name in CARDS_A3.items():
        if only and cid not in only:
            continue
        out = os.path.join(root, cid)
        fn = {"action-end-turn": checks_end_turn, "card-drop": checks_card_drop, "marker-slot-discard": checks_slot_a3,
              "ui-log": checks_log, "cursor-pointer": checks_pointer}[name]
        files, meas = fn(cid, name, out)
        audit = json.load(open(os.path.join(D.ROOT, "sheets", "audit.json"), encoding="utf-8")).get(name, {})
        data = {"id": name, "card": cid, "tool": "art/imagegen/hud-icons-v3/_tools/vr44_checks.py --a3", "files": files,
                "audit_master": {k: audit.get(k) for k in ("margin_px", "seam_px", "glyph_area_pct_of_body",
                                                         "alpha_centroid_u", "lr_symmetry_mean_abs")},
                "measures": meas}
        with open(os.path.join(out, "checks.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        report[cid] = files
        print(cid, name, files)
    return report


def run(root):
    report = {}
    for cid, name in CARDS.items():
        out = os.path.join(root, cid)
        if name in ("badge-order", "badge-order-p2"):
            files, meas = checks_badge_order(cid, name, out)
        elif name == "badge-refuse":
            files, meas = checks_refuse(cid, name, out)
        elif name == "badge-conflict":
            files, meas = checks_conflict(cid, name, out)
        elif name == "badge-ally":
            files, meas = checks_simple(cid, name, out, ["state-pending-move", "action-maneuver"], (18, 24, 32, 48),
                                        "в сером рядом с state-pending-move (IC-04) и action-maneuver; IC-46 — после CX-04; ×4")
        elif name == "badge-attack-from":
            files, meas = checks_simple(cid, name, out, ["state-hint", "state-threat"], (18, 24, 32),
                                        "звезда в слоте против лампы state-hint и глаза state-threat, ×4")
            rows = [(f"число 1…4 @ {s} px ×4", [cell(ex(name, s, text=str(d)), NAVY, 4) for d in range(1, 5)])
                    for s in (24, 32)]
            files.append(compose(f"{cid}: число runtime-текстом font.card cap 14 u (образец)", rows,
                                 os.path.join(out, "check-digits.png")))
        elif name.startswith("team-chip"):
            files, meas = checks_chip(cid, name, out)
        elif name == "state-warning":
            files, meas = checks_simple(cid, name, out, ["ui-step", "action-scheme"], (18, 24, 32),
                                        "треугольник «!» против ui-step (без «!» и кромки) и диска action-scheme, ×4")
        elif name.startswith("marker-slot"):
            files, meas = checks_slot(cid, name, out)
        elif name == "ui-menu":
            files, meas = checks_menu(cid, name, out)
        elif name == "ui-close":
            files, meas = checks_simple(cid, name, out, ["badge-refuse", "marker-x-stamp"], (18, 24, 32),
                                        "белый тонкий × без плашки против badge-refuse и marker-x-stamp, ×4")
        elif name == "ui-step":
            files, meas = checks_step(cid, name, out)
        else:
            files, meas = checks_cursor(cid, name, out)
        audit = json.load(open(os.path.join(D.ROOT, "sheets", "audit.json"), encoding="utf-8")).get(name, {})
        data = {"id": name, "card": cid, "tool": "art/imagegen/hud-icons-v3/_tools/vr44_checks.py", "files": files,
                "audit_master": {k: audit.get(k) for k in ("margin_px", "seam_px", "glyph_area_pct_of_body",
                                                         "alpha_centroid_u", "lr_symmetry_mean_abs")},
                "measures": meas}
        with open(os.path.join(out, "checks.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        report[cid] = files
        print(cid, name, files)
    return report


# ------------------------------------------------------------------------------------------------ VS-4 V3: значки зон
# IC-62…IC-69: лист 8 ключей рядом (24 и 32 px ×4, цвет и серый — пункт acceptance «попарно различимы»), лист каждого
# ключа на фонах кадров (светлое пространство Marmoreal, красная палуба Sarpedon, panel.bg), ×8 при 24 px, замеры:
# контраст глифа к диску и диска к плашке по профилю доски, попарные расстояния глифов в сером.
CARDS_ZONES = {f"IC-{62 + i}": k for i, k in enumerate(D.ZONE_KEYS)}
ZONE_BGS = {"light space": "#DEDEE0", "red deck": "#A43839", "panel.bg": NAVY}  # светлое пространство Marmoreal, палуба Sarpedon


def zone_variants(key):
    """[(доска, id, диск)]: мастер — цвет кадра Marmoreal, вариант -sarpedon — если ключ есть на Sarpedon."""
    out = [("Marmoreal", f"zone-{key}", D.ZONE_DISC["marmoreal"][key])]
    if key in D.ZONE_DISC["sarpedon"]:
        out.append(("Sarpedon", f"zone-{key}-sarpedon", D.ZONE_DISC["sarpedon"][key]))
    return out


def zone_pairs(size):
    """Попарные расстояния 8 глифов при size px: пиксели, где бинарные маски (альфа ≥ 128) различаются, и доля от
    объединения; и средняя |Δ серого| цельных значков (диск Marmoreal) по окну диска."""
    masks = {k: D.zone_glyph_alpha(k, size) >= 128 for k in D.ZONE_KEYS}
    greys = {k: np.asarray(grey(D.render(f"zone-{k}", size)))[..., 0].astype(float) for k in D.ZONE_KEYS}
    yy, xx = np.mgrid[:size, :size]
    win = (xx + 0.5 - size / 2) ** 2 + (yy + 0.5 - size / 2) ** 2 <= (size * 11.0 / 32) ** 2
    pairs = []
    keys = list(D.ZONE_KEYS)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            diff = int((masks[a] ^ masks[b]).sum())
            union = int((masks[a] | masks[b]).sum())
            pairs.append({"a": a, "b": b, "glyph_px_diff": diff, "glyph_diff_of_union": round(diff / max(union, 1), 3),
                          "grey_mean_abs_diff": round(float(np.abs(greys[a] - greys[b])[win].mean()), 1)})
    return pairs


def checks_zone_keys(out):
    """Лист 8 ключей рядом: цвет диска кадра и серый Rec.709, 24 и 32 px ×4; второй блок — варианты Sarpedon."""
    rows = []
    for s in (24, 32):
        ims = [cell(D.render(f"zone-{k}", s), NAVY, 4) for k in D.ZONE_KEYS]
        rows.append((f"Marmoreal · colour @ {s} px ×4", ims))
        rows.append((f"Marmoreal · grey @ {s} px ×4", [grey(i) for i in ims]))
    sk = [k for k in D.ZONE_KEYS if k in D.ZONE_DISC["sarpedon"]]
    for s in (24, 32):
        ims = [cell(D.render(f"zone-{k}-sarpedon", s), NAVY, 4) for k in sk]
        rows.append((f"Sarpedon · colour @ {s} px ×4", ims))
        rows.append((f"Sarpedon · grey @ {s} px ×4", [grey(i) for i in ims]))
    title = "IC-62…IC-69: 8 ключей рядом — " + ", ".join(D.ZONE_KEYS) + " (Sarpedon: " + ", ".join(sk) + ")"
    return compose(title, rows, os.path.join(out, "check-zone-keys.png"))


def checks_zone(cid, key, out):
    files, meas = [], {"key": key, "boards": {}}
    rows = []
    for board, name, disc in zone_variants(key):
        ink = D.zone_ink(disc)
        meas["boards"][board] = {"id": name, "disc": disc, "ink": ink,
                                 "ink_to_disc": contrast(ink, disc), "disc_to_navy_plate": contrast(disc, NAVY),
                                 "other_ink_to_disc": contrast(
                                     D.TOKENS["card.glyph"] if ink == D.TOKENS["card.navy"] else D.TOKENS["card.navy"],
                                     disc)}
        for bname, bg in ZONE_BGS.items():
            ims = [cell(D.render(name, s), bg, 4) for s in (24, 32, 48)]
            rows.append((f"{board} {disc} · {bname} · colour", ims))
            rows.append((f"{board} · {bname} · grey", [grey(i) for i in ims]))
    files.append(compose(f"{cid} zone-{key}: на фонах кадров (светлое пространство Marmoreal #DEDEE0, палуба Sarpedon "
                         f"#A43839, panel.bg), 24 / 32 / 48 px ×4, цвет и серый", rows,
                         os.path.join(out, "check-zone-context.png")))
    rows = []
    for board, name, disc in zone_variants(key):
        im = cell(D.render(name, 24), NAVY, 8, pad=1)
        rows.append((f"{board} @ 24 px ×8 · colour | grey", [im, grey(im)]))
    gl = D.zone_glyph_alpha(key, 24)
    g = Image.fromarray(np.dstack([np.full_like(gl, 255)] * 3 + [gl]), "RGBA")
    rows.append(("glyph mask @ 24 px ×8", [cell(g, NAVY, 8, pad=1)]))
    files.append(compose(f"{cid} zone-{key}: 24 px ×8 — форма глифа на рабочем размере", rows,
                         os.path.join(out, "check-zone-24x8.png")))
    alpha24 = D.zone_glyph_alpha(key, 24)
    meas["glyph_px_24"] = int((alpha24 >= 128).sum())
    meas["glyph_px_32"] = int((D.zone_glyph_alpha(key, 32) >= 128).sum())
    return files, meas


def run_zones(root):
    report = {}
    shared = checks_zone_keys(os.path.join(root, "IC-62"))
    pairs = {s: zone_pairs(s) for s in (24, 32)}
    for cid, key in CARDS_ZONES.items():
        out = os.path.join(root, cid)
        files, meas = checks_zone(cid, key, out)
        meas["pairs"] = {str(s): [p for p in ps if key in (p["a"], p["b"])] for s, ps in pairs.items()}
        meas["pairs_min"] = {str(s): min((p for p in ps if key in (p["a"], p["b"])), key=lambda p: p["glyph_px_diff"])
                             for s, ps in pairs.items()}
        meas["shared_sheet"] = f"IC-62/{shared}"
        audit = {}
        for _, name, _ in zone_variants(key):
            a = json.load(open(os.path.join(D.ROOT, "sheets", "audit.json"), encoding="utf-8")).get(name, {})
            audit[name] = {k: a.get(k) for k in ("margin_px", "seam_px", "glyph_area_pct_of_body", "alpha_centroid_u",
                                                  "lr_symmetry_mean_abs")}
        data = {"id": f"zone-{key}", "card": cid, "tool": "art/imagegen/hud-icons-v3/_tools/vr44_checks.py --v3zones",
                "files": files + ([shared] if cid == "IC-62" else []), "audit_master": audit, "measures": meas}
        with open(os.path.join(out, "checks.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
        report[cid] = files
        print(cid, key, files, meas["boards"], meas["pairs_min"])
    allmin = {s: min(ps, key=lambda p: p["glyph_px_diff"]) for s, ps in pairs.items()}
    print("pairs min", allmin)
    return report


if __name__ == "__main__":
    # --a3 [IC-NN,…]: листы шага A3 (IC-46, IC-48, IC-52, IC-55, IC-59); --v3zones: листы IC-62…IC-69 (VS-4 V3);
    # без флага — листы шага A2
    argv = sys.argv[1:]
    root = os.path.join(REPO, "docs", "game-design", "evidence", "VISUAL")
    if "--v3zones" in argv:
        run_zones(root)
    elif "--a3" in argv:
        i = argv.index("--a3")
        only = argv[i + 1].split(",") if len(argv) > i + 1 and argv[i + 1].startswith("IC-") else None
        run_a3(root, only)
    else:
        run(argv[0] if argv else root)
