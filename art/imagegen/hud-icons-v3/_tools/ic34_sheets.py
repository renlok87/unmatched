#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""IC-34 (VS-2 A3): лист приёмки набора v3 и DE-012 (строки IC-01…IC-32) на новой основе панелей (panel.bg = card.navy,
ВР-61), на card.cream и #808080, в цвете, сером (Rec.709) и при дейтеранопии; размеры 18 / 24 / 32 / 48 px ×4 nearest.

    python art/imagegen/hud-icons-v3/_tools/ic34_sheets.py [docs/game-design/evidence/VISUAL/IC-34] [--per-id C:/tmp/visual/IC-34]

Пишет в <out>: sheet-accept-colour.png, sheet-accept-grey.png, sheet-accept-deutan.png (все 32 строки на трёх фонах),
check-groups.png (соседи строк в сером при 18 и 24 px), check-resources-18.png (ресурсы 24 su при 720p = 18 px),
check-motion.png (кадры флипбуков и фаз), check-ring-rest.png (тлеющий обод 0,35 / 0,55, ВР-43),
sheet-live-context.jpg (кропы живых кадров прогона I, обе карты; штамп Marmoreal — кадр соперника), ic34.json
(замеры по строкам). --per-id: листы accept-<id>.png движка (мастер + размеры, 9 строк) — для поштучного осмотра,
вне git (бюджет листов в git ≤ 10 МБ). Всё рисует draw_icons.py из вектора; цифры — образец runtime-текста.
"""
from __future__ import annotations

import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import draw_icons as D  # noqa: E402
import vr44_checks as V  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CARDS = {
    "IC-01": "state-boost", "IC-02": "state-enemy", "IC-03": "state-sent", "IC-04": "state-pending-move",
    "IC-05": "state-pending-place", "IC-06": "state-hint", "IC-07": "state-threat", "IC-08": "state-immobilized",
    "IC-09": "action-attack", "IC-10": "action-attack-token", "IC-11": "action-attack-token-glyphmask",
    "IC-12": "action-defense", "IC-13": "action-maneuver", "IC-14": "action-scheme", "IC-15": "marker-status",
    "IC-16": "loader-spinner", "IC-17": "resource-action-full", "IC-18": "resource-action-empty",
    "IC-19": "resource-card", "IC-20": "resource-connection-online", "IC-21": "resource-connection-reconnecting",
    "IC-22": "resource-connection-lost", "IC-23": "resource-hp-full", "IC-24": "resource-hp-empty",
    "IC-25": "resource-hp-full-enemy", "IC-26": "marker-status-p1", "IC-27": "marker-status-p2",
    "IC-28": "marker-turn-ring", "IC-29": "resource-hp-fallen", "IC-30": "marker-x-stamp",
    "IC-31": "marker-action-slot-de", "IC-32": "marker-turn-ring-team",
}
SIZES = (18, 24, 32, 48)
ZOOM = 4
BGS = (("card.navy (panel.bg)", D.TOKENS["card.navy"]), ("card.cream", D.TOKENS["card.cream"]), ("#808080", "#808080"))
NAVY, CREAM = D.TOKENS["card.navy"], D.TOKENS["card.cream"]
RUN_I = os.path.join(REPO, "docs", "game-design", "evidence", "DE-FOOTAGE", "2026-10-05", "I")
LIVE = (("Marmoreal", "marmoreal/combat-20261005-235827/host"), ("Sarpedon", "sarpedon/combat-20261005-235948/host"))
LIVE_FRAMES = ("s09-turn-banner.jpg", "s09-damage-combat.jpg", "s09-no-defense-stamp.jpg")
# 1080p кадры прогона I: колонка портретов (кольцо, сердце, трекер) и правый край боя (штамп «нет защиты»)
LIVE_CROPS = (("портреты: кольцо, сердце, трекер", (20, 862, 280, 1062)), ("край боя: штамп", (1600, 470, 1910, 612)))
# У хоста Marmoreal в кадре штампа открыта панель колоды соперника и закрывает правый край (README прогона I):
# штамп Marmoreal берётся из кадра соперника (joiner) того же момента; сердце павшего — s09-result-board хоста.
LIVE_EXTRA = (("Marmoreal", "marmoreal/combat-20261005-235827/joiner", "s09-no-defense-stamp.jpg",
               ("край боя: штамп (joiner)", (1600, 470, 1910, 612))),
              ("Marmoreal", "marmoreal/combat-20261005-235827/host", "s09-result-board.jpg",
               ("портреты: сердце павшего", (20, 862, 280, 1062))),
              ("Sarpedon", "sarpedon/combat-20261005-235948/host", "s09-result-board.jpg",
               ("портреты: сердце павшего", (20, 862, 280, 1062))))
TEAM_DISCS = (("team.p1.screen", "#DAC576"), ("team.p2.screen", "#5786A8"))
# Кольцо хода: окно 64 su сейчас (US08TurnPortraitWidget, ВР-VS2-35) и 104 su в PANEL-LOC (04 §2.2), круг 42 / 80 su
RING_WINDOWS = ((64, 42 / 64), (104, 80 / 104))


def rgba(hexv):
    return tuple(int(hexv[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def luma(c):
    return float(np.array([0.2126, 0.7152, 0.0722]) @ np.array(c[:3], dtype=float))


def lin(c):
    c = np.asarray(c[:3], dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def contrast(a, b):
    la, lb = [float(lin(rgba(x) if isinstance(x, str) else x) @ np.array([0.2126, 0.7152, 0.0722])) for x in (a, b)]
    return round((max(la, lb) + 0.05) / (min(la, lb) + 0.05), 2)


# ------------------------------------------------------------------------------------------------ листы
def row_image(name, bg_hex):
    """18 / 24 / 32 / 48 ×4 nearest на одном фоне (широкие — 2 : 1)."""
    wide = D.is_wide(name)
    ims = [D.xN(D.render_example(name, s), ZOOM) for s in SIZES]
    pad = 12
    W = sum(im.width for im in ims) + pad * (len(ims) + 1)
    H = max(im.height for im in ims) + 2 * pad
    row = Image.new("RGBA", (W, H), rgba(bg_hex))
    x = pad
    for im in ims:
        row.alpha_composite(im, (x, (H - im.height) // 2))
        x += im.width + pad
    return row


def sheets(out):
    vs = D._visual_sheet()
    files = {}
    blocks = {cid: [row_image(n, h) for _, h in BGS] for cid, n in CARDS.items()}
    name_w, gap = 300, 10
    W = name_w + max(sum(b.width for b in bl) + gap * len(bl) for bl in blocks.values()) + gap
    for mode, fname in zip(vs.MODES, ("sheet-accept-colour.png", "sheet-accept-grey.png", "sheet-accept-deutan.png")):
        H = 70 + sum(max(b.height for b in bl) + gap for bl in blocks.values())
        sheet = Image.new("RGBA", (W, H), D.SHEET_BG)
        sheet.alpha_composite(D.label(W, 30, f"IC-34 — набор v3 и DE-012 (IC-01…IC-32), {mode}: 18 / 24 / 32 / 48 px из вектора ×4 nearest "
                                      "на card.navy (panel.bg, ВР-61) | card.cream | #808080; числа — образец runtime-текста", 15), (0, 6))
        sheet.alpha_composite(D.label(W, 24, "IC-11 — маска (игроку не видна), IC-32 — отклонённый кандидат (только галерея); "
                                      "мастера — sheets/sheet-masters.png", 12), (0, 38))
        y = 70
        for cid, bl in blocks.items():
            h = max(b.height for b in bl)
            sheet.alpha_composite(D.label(name_w, 40, f"{cid} {CARDS[cid]}", 13), (0, y + h // 2 - 20))
            x = name_w
            for b in bl:
                sheet.alpha_composite(vs.apply_mode(b, mode).convert("RGBA"), (x, y))
                x += b.width + gap
            y += h + gap
        p = os.path.join(out, fname)
        sheet.convert("RGB").save(p, optimize=True)
        files[mode] = fname
    return files


def per_id(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    vs = D._visual_sheet()
    return [D.sheet_accept(n, os.path.join(out_dir, f"accept-{cid}-{n}.png"), vs)["file"] for cid, n in CARDS.items()]


GROUPS = (
    ("IC-01 BOOST против спиннера, жетона цели и пипсов", ["state-boost", "loader-spinner", "action-attack-token", "action-attack",
                                                          "action-defense", "action-maneuver", "action-scheme"]),
    ("IC-02 / IC-08 пешка, якорь, часы, крест стрелок", ["state-enemy", "state-immobilized", "state-sent", "state-pending-move"]),
    ("IC-04 крест стрелок против X отказа (IC-40)", ["state-pending-move", "badge-refuse"]),
    ("IC-05 место PLACE против card-drop (IC-48)", ["state-pending-place", "card-drop"]),
    ("IC-06 / IC-07 лампа против глаза", ["state-hint", "state-threat"]),
    ("IC-09 / IC-12 / IC-13 звезда, щит, ботинки", ["action-attack", "action-defense", "action-maneuver"]),
    ("IC-14 молния против state-warning (IC-47)", ["action-scheme", "state-warning"]),
    ("IC-15 / IC-26 / IC-27 лента P1 / P2", ["marker-status-p1", "marker-status-p2"]),
    ("IC-17 / IC-18 полный и пустой ромб", ["resource-action-full", "resource-action-empty"]),
    ("IC-19 стопка против ui-menu (IC-53)", ["resource-card", "ui-menu"]),
    ("IC-20…IC-22 связь: online, reconnecting, lost", ["resource-connection-online", "resource-connection-reconnecting",
                                                      "resource-connection-lost"]),
    ("IC-23…IC-25 / IC-29 сердца: своё, пустое, чужое, павший", ["resource-hp-full", "resource-hp-empty", "resource-hp-full-enemy",
                                                                 "resource-hp-fallen"]),
    ("IC-30 штамп против badge-refuse и ui-close", ["marker-x-stamp", "badge-refuse", "ui-close"]),
)


def groups(out):
    rows = []
    for title, names in GROUPS:
        for s in (18, 24):
            ims = [V.grey(V.cell(V.ex(n, s), NAVY, 4)) for n in names]
            rows.append((f"{title} @ {s} px, серый, card.navy", ims))
    return V.compose("IC-34: соседи строк в сером на card.navy (panel.bg) при 18 и 24 px ×4", rows,
                     os.path.join(out, "check-groups.png"))


def resources18(out):
    """Ресурсы 24 su при 720p = 18 px (detail 0) рядом с ui-menu: сердце, стопка, связь; тёмное чужое сердце на navy."""
    names = ["resource-hp-full", "resource-hp-full-enemy", "resource-hp-empty", "resource-hp-fallen", "resource-card", "ui-menu",
             "resource-connection-online", "resource-connection-reconnecting", "resource-connection-lost"]
    rows = []
    for bg in (NAVY, CREAM):
        for zoom in (1, 6):
            ims = [V.cell(D.render(n, 18), bg, zoom) for n in names]
            rows.append((f"18 px ×{zoom} · {bg} · цвет", ims))
            rows.append(("серый", [V.grey(i) for i in ims]))
    return V.compose("IC-34: ресурсы 24 su при 720p (DPI 0,75) = 18 px, detail 0: " + " | ".join(names), rows,
                     os.path.join(out, "check-resources-18.png"))


def motion_frames(out):
    """IC-03 флипбук часов (24 / 32, 12 кадров); IC-21 знак ↻ — поворот 0…330° (24, 18); IC-28 тона вспышки f00…f06."""
    rows = []
    frames = D._sent_frames()
    for s in (24, 32):
        ims = [V.cell(Image.alpha_composite(D.render("state-sent", s, layer="body"),
                                            D.render("state-sent", s, layer="glyph", **kw)), NAVY, 4) for kw in frames]
        rows.append((f"IC-03 state-sent f00…f11 @ {s} px ×4", ims))
    for s in (18, 24):
        ims = []
        for ang in range(0, 360, 30):
            bars = D.render("resource-connection-reconnecting", s, layer="bars")
            sign = D.render("resource-connection-reconnecting", s, layer="sign", angle=math.radians(ang))
            ims.append(V.cell(Image.alpha_composite(bars, sign), NAVY, 4))
        rows.append((f"IC-21 ↻ 0…330° @ {s} px ×4", ims))
    ims = [V.cell(D.render("marker-turn-ring", 48, layer="flash", frame=f), NAVY, 2) for f in range(D.RING_FLASH_FRAMES)]
    rows.append(("IC-28 вспышка f00…f06 @ 48 ×2 · цвет", ims))
    rows.append(("серый", [V.grey(i) for i in ims]))
    return V.compose("IC-34: кадры движения (флипбуки и фазы поворота) — эталон движка", rows, os.path.join(out, "check-motion.png"))


def live_context(out):
    tiles = []
    jobs = [(board, rel, f, crop) for board, rel in LIVE for f in LIVE_FRAMES for crop in LIVE_CROPS]
    jobs += [(board, rel, f, crop) for board, rel, f, crop in LIVE_EXTRA]
    for board, rel, f, (title, box) in jobs:
        p = os.path.join(RUN_I, rel, f)
        if not os.path.exists(p):
            continue
        c = Image.open(p).convert("RGB").crop(box)
        c = c.resize((c.width * 2, c.height * 2), Image.NEAREST)
        side = rel.rsplit("/", 1)[-1]
        tiles.append((f"{board} · {side}/{f} · {title}", c))
    pad, lab = 10, 26
    cols = 2
    cw = max(t.width for _, t in tiles) + pad
    ch = max(t.height for _, t in tiles) + lab + pad
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * cw + pad, 40 + rows * ch), D.SHEET_BG[:3])
    sheet.paste(D.label(sheet.width, 30, "IC-34: живой контекст — кропы кадров прогона I (1080p, packaged), ×2 nearest: "
                        "кольцо хода, сердце, трекер DE, штамп; Marmoreal original и Sarpedon original", 15).convert("RGB"), (0, 6))
    for i, (title, t) in enumerate(tiles):
        x, y = pad + (i % cols) * cw, 40 + (i // cols) * ch
        sheet.paste(D.label(cw, lab, title, 12).convert("RGB"), (x, y))
        sheet.paste(t, (x, y + lab))
    p = os.path.join(out, "sheet-live-context.jpg")
    sheet.save(p, quality=88)
    return os.path.basename(p), len(tiles)


def _with_opacity(im, k):
    a = np.asarray(im).copy()
    a[..., 3] = np.rint(a[..., 3] * k).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


def ring_rest(out):
    """IC-28 / ВР-43: тлеющий обод кольца хода 0,35 против 0,55 на panel.bg вокруг круга аватара, 1080p (DPI 1) и 720p
    (DPI 0,75), окно 64 su (виджет хода сейчас) и 104 su (PANEL-LOC 04 §2.2); живой кадр Marmoreal (обод в покое у
    King Arthur, ход соперника) ×1 и уменьшенный ×0,75 билинейно как образ 720p."""
    rows = []
    for su, k in RING_WINDOWS:
        for dpi in (1.0, 0.75):
            px = round(su * dpi)
            ims = []
            for op in (0.35, 0.55):
                for _, disc in TEAM_DISCS:
                    base = Image.new("RGBA", (px, px), (0, 0, 0, 0))
                    d = px * k
                    ImageDraw.Draw(base).ellipse(((px - d) / 2, (px - d) / 2, (px + d) / 2 - 1, (px + d) / 2 - 1), fill=rgba(disc))
                    base.alpha_composite(_with_opacity(D.render("marker-turn-ring", px, layer="rim"), op))
                    ims.append(V.cell(base, NAVY, 3 if px <= 64 else 2))
            rows.append((f"окно {su} su · DPI {dpi} = {px} px · обод 0,35 | 0,35 | 0,55 | 0,55 · цвет", ims))
            rows.append(("серый", [V.grey(i) for i in ims]))
    p = os.path.join(RUN_I, "marmoreal/combat-20261005-235827/host/s09-damage-combat.jpg")
    if os.path.exists(p):
        c = Image.open(p).convert("RGBA").crop((20, 862, 280, 962))
        small = c.resize((round(c.width * 0.75), round(c.height * 0.75)), Image.BILINEAR)
        rows.append(("живой кадр 1080p ×2 | образ 720p (×0,75 билинейно) ×2",
                     [D.xN(c, 2), D.xN(small, 2)]))
        rows.append(("серый", [V.grey(D.xN(c, 2)), V.grey(D.xN(small, 2))]))
    return V.compose("IC-34 / ВР-43: тлеющий обод кольца хода на panel.bg — 0,35 против 0,55, 1080p и 720p", rows,
                     os.path.join(out, "check-ring-rest.png"))


# ------------------------------------------------------------------------------------------------ замеры
def _over(fg_hex, bg_hex, k):
    """Цвет fg с непрозрачностью k поверх bg (sRGB, как UMG без гамма-смешения в 8 бит)."""
    f, b = np.array(rgba(fg_hex)[:3], float), np.array(rgba(bg_hex)[:3], float)
    return tuple(int(v) for v in np.rint(f * k + b * (1 - k))) + (255,)


def mean_grey_on(name, size, bg=NAVY, layer=None, **kw):
    im = D.render(name, size, layer=layer, **kw) if layer else V.ex(name, size)
    base = Image.new("RGBA", im.size, rgba(bg))
    base.alpha_composite(im)
    a = np.asarray(im)[..., 3] > 128
    g = np.asarray(V.grey(base))[..., 0].astype(float)
    return round(float(g[a].mean()), 1) if a.any() else None


def grey_diff(a, b, size, bg=NAVY):
    """Средняя |Δ серого| двух значков на одном фоне по объединению их непрозрачных пикселей (0…255)."""
    def comp(n):
        im = V.ex(n, size)
        base = Image.new("RGBA", im.size, rgba(bg))
        base.alpha_composite(im)
        return np.asarray(V.grey(base))[..., 0].astype(float), np.asarray(im)[..., 3] > 32
    ga, ma = comp(a)
    gb, mb = comp(b)
    if ga.shape != gb.shape:
        return None
    m = ma | mb
    return round(float(np.abs(ga - gb)[m].mean()), 1)


def min_gap_sign_bars(size):
    """IC-21: минимальный зазор (px) между знаком ↻ и столбиками по всем фазам поворота 0…345° (шаг 15°)."""
    from scipy import ndimage
    bars = np.asarray(D.render("resource-connection-reconnecting", size, layer="bars"))[..., 3] > 64
    dist = ndimage.distance_transform_edt(~bars)
    out = []
    for ang in range(0, 360, 15):
        sign = np.asarray(D.render("resource-connection-reconnecting", size, layer="sign", angle=math.radians(ang)))[..., 3] > 64
        out.append(float(dist[sign].min()) if sign.any() else None)
    vals = [v for v in out if v is not None]
    return round(min(vals) - 1.0, 2) if vals else None   # пиксельные центры: 1,0 = соседние пиксели, зазор 0


def boost_text_fits(size=32):
    """IC-01: «+2» cap 11 u внутри внутреннего круга кольца при 32 px (пиксели цифр не выходят за кольцо)."""
    sp = D.Spec(size)
    R = D.U / 2 - sp.M
    r_in = (R - sp.K - sp.pxu(1.0) - sp.ring) * sp.k
    im = np.asarray(D.render("state-boost", size, text="+2")).astype(int)
    base = np.asarray(D.render("state-boost", size)).astype(int)
    diff = np.abs(im - base).sum(-1) > 30
    ys, xs = np.where(diff)
    c = size / 2 - 0.5
    rmax = float(np.max(np.hypot(xs - c, ys - c))) if len(xs) else 0.0
    return {"text_px_max_radius": round(rmax, 2), "ring_inner_radius_px": round(r_in, 2), "fits": rmax <= r_in}


def measures():
    c = json.load(open(os.path.join(REPO, "docs", "unreal", "contracts", "hud", "icon-motion.json"), encoding="utf-8"))
    icons = c["icons"]
    m = {}
    m["IC-01"] = {"boost_text_32": boost_text_fits(32),
                  "grey_diff_24": {n: grey_diff("state-boost", n, 24) for n in ("loader-spinner", "action-attack-token",
                                                                                 "action-attack", "action-defense")}}
    m["IC-02"] = {"grey_diff_24": {n: grey_diff("state-enemy", n, 24) for n in ("state-immobilized", "state-sent",
                                                                                "state-pending-move")}}
    m["IC-04"] = {"grey_diff_24_vs_badge_refuse": grey_diff("state-pending-move", "badge-refuse", 24),
                  "body_on_marmoreal_blue": {"keyline_vs_#4E84A1": contrast(D.TOKENS["mark.keyline"], "#4E84A1"),
                                             "glyph_vs_body": contrast(D.TOKENS["card.glyph"], D.TOKENS["state.pending"])}}
    m["IC-05"] = {"body_grey": {"state-pending-place": mean_grey_on("state-pending-place", 32, layer="body"),
                                "card-drop": mean_grey_on("card-drop", 32, layer="body")}}
    m["IC-06"] = {"grey_diff_24_vs_threat": grey_diff("state-hint", "state-threat", 24)}
    m["IC-09"] = {"grey_diff_24": {n: grey_diff("action-attack", n, 24) for n in ("action-defense", "action-maneuver")}}
    m["IC-10"] = {"reduced_pulse": {k: v.get("reduced", {}).get("tracks") for k, v in icons["action-attack-token"]["anims"].items()
                                    if v.get("kind") == "loop"},
                  "rim_vs_marmoreal_white_#DEDEE0": contrast(D.TOKENS["icon.token.rim"], "#DEDEE0"),
                  "body_vs_marmoreal_white_#DEDEE0": contrast(D.TOKENS["icon.token.body"], "#DEDEE0"),
                  "rim_vs_red_deck_#A43839": contrast(D.TOKENS["icon.token.rim"], "#A43839")}
    t = np.asarray(D.render("action-attack-token", 64))[..., 3]
    g = np.asarray(D.render("action-attack-token-glyphmask", 64))[..., 3]
    m["IC-11"] = {"mask_inside_token_64": bool(((g > 0) & (t == 0)).sum() == 0), "mask_px_64": int((g > 128).sum())}
    m["IC-14"] = {"grey_diff_24_vs_warning": grey_diff("action-scheme", "state-warning", 24)}
    m["IC-15"] = {"team_block_grey": {"P1": round(luma(rgba(D.TOKENS["team.p1.screen"])), 1),
                                      "P2": round(luma(rgba(D.TOKENS["team.p2.screen"])), 1)}}
    sp = icons["loader-spinner"]["anims"]
    loop = [v for v in sp.values() if v.get("kind") == "loop"]
    m["IC-16"] = {"loop_ms": loop[0]["duration_ms"] if loop else None,
                  "reduced_ms": loop[0].get("reduced", {}).get("duration_ms") if loop else None}
    spend = icons["resource-action-full"]["anims"]["spend"]
    m["IC-17"] = {"spend_ms": spend["duration_ms"],
                  "spend_tracks": [f"{t['target']}.{t['prop']} {t['keys'][0][1]}->{t['keys'][-1][1]}" for t in spend["tracks"]],
                  "full_vs_empty_grey_diff_24_on_navy": grey_diff("resource-action-full", "resource-action-empty", 24)}
    m["IC-18"] = {"grey_diff_24_full_vs_empty": grey_diff("resource-action-full", "resource-action-empty", 24)}
    m["IC-19"] = {"grey_diff_18_vs_ui_menu": grey_diff("resource-card", "ui-menu", 18)}
    m["IC-20"] = {"text_secondary_on_panel_bg": contrast(D.TOKENS["text.secondary"], NAVY),
                  "grey_diff_18": {n: grey_diff("resource-connection-online", n, 18) for n in
                                   ("resource-connection-reconnecting", "resource-connection-lost")}}
    m["IC-21"] = {"min_gap_sign_bars_px": {str(s): min_gap_sign_bars(s) for s in (18, 24, 32, 48)}}
    m["IC-22"] = {"grey_diff_18_reconnecting_vs_lost": grey_diff("resource-connection-reconnecting", "resource-connection-lost", 18),
                  "lost_sign_loops": [k for k, v in icons["resource-connection-lost"]["anims"].items() if v.get("kind") == "loop"]}
    m["IC-23"] = {"grey_diff_18": {n: grey_diff("resource-hp-full", n, 18) for n in ("resource-hp-full-enemy", "resource-hp-empty")},
                  "glow_vs_panel_bg": contrast(D.TOKENS["card.type.attack"], NAVY)}
    m["IC-24"] = {"grey_diff_24": {n: grey_diff("resource-hp-empty", n, 24) for n in ("resource-hp-full-enemy", "resource-hp-fallen")}}
    m["IC-25"] = {"red_rim_vs_panel_bg": contrast(D.TOKENS["card.type.attack"], NAVY),
                  "dark_body_vs_panel_bg": contrast(D.TOKENS["card.navy"], NAVY)}
    for cid, var, team in (("IC-26", "marker-status-p1", "team1"), ("IC-27", "marker-status-p2", "team2")):
        body = D.render("marker-status", 64, layer="body")
        tm = D._tinted(D.render("marker-status", 64, layer="team"), D.C[team])
        comp = Image.alpha_composite(body, tm)
        a = np.asarray(comp).astype(int)
        b = np.asarray(D.render(var, 64)).astype(int)
        pa, pb = a[..., :3] * a[..., 3:] // 255, b[..., :3] * b[..., 3:] // 255
        m[cid] = {"max_abs_premult_vs_status_x_team_64": int(np.abs(pa - pb).max()), "alpha_max_diff": int(np.abs(a[..., 3] - b[..., 3]).max())}
    flash = [rgba(D.TOKENS[t]) for t in ("turn.flash.yellow", "turn.flash.orange", "card.type.attack")]
    m["IC-28"] = {"flash_luma": {"yellow": round(luma(flash[0]), 1), "orange": round(luma(flash[1]), 1), "red": round(luma(flash[2]), 1)},
                  "rim_rest_opacity": [l.get("rest", {}).get("opacity") for l in icons["marker-turn-ring"]["layers"] if l["id"] == "rim"][0],
                  "rest_rim_vs_panel_bg": {str(op): contrast(_over(D.TOKENS["turn.flash.orange"], NAVY, op), NAVY)
                                           for op in (0.35, 0.55)}}
    m["IC-29"] = {"grey_diff_24_vs_empty": grey_diff("resource-hp-fallen", "resource-hp-empty", 24)}
    m["IC-30"] = {"grey_diff_24": {n: grey_diff("marker-x-stamp", n, 24) for n in ("badge-refuse", "ui-close")}}
    ring = mean_grey_on("marker-action-slot-de", 32, layer="ring")
    m["IC-31"] = {"ring_grey_on_navy": ring, "fill_ms": icons["marker-action-slot-de"]["anims"]["fill"]["duration_ms"]}
    m["IC-32"] = {"contract_list": "candidates" if "marker-turn-ring-team" in c.get("candidates", []) else None}
    return m


def main():
    args = sys.argv[1:]
    out = args[0] if args and not args[0].startswith("--") else os.path.join(REPO, "docs", "game-design", "evidence", "VISUAL", "IC-34")
    os.makedirs(out, exist_ok=True)
    data = {"tool": "art/imagegen/hud-icons-v3/_tools/ic34_sheets.py", "cards": CARDS, "sizes": list(SIZES), "zoom": ZOOM,
            "backgrounds": [f"{n} {h}" for n, h in BGS]}
    data["sheets"] = sheets(out)
    data["checks"] = [groups(out), resources18(out), motion_frames(out), ring_rest(out)]
    data["live"], data["live_tiles"] = live_context(out)
    data["measures"] = measures()
    if "--per-id" in args:
        data["per_id_dir"] = args[args.index("--per-id") + 1]
        data["per_id"] = per_id(data["per_id_dir"])
    with open(os.path.join(out, "ic34.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(json.dumps({k: data[k] for k in ("sheets", "checks", "live", "live_tiles")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
