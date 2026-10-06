#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Листы проверок набора VR44 (VS-2 A2, карточки IC-38…IC-61) — пункты acceptance сверх листа приёмки:
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


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, "docs", "game-design", "evidence", "VISUAL"))
