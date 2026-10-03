#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Листы просмотра со сканами карт и кадрами Digital Edition — только вне репозитория (ENV-U3).

    python draw_icons.py --review DIR      # или: python review_sheets.py DIR

Выход: DIR/sheet-context-maps.png (Marmoreal/Sarpedon при 24 и 32 px, цвет и серый),
       DIR/sheet-vs-de.png (наши значки рядом с кадрами DE того же смысла).
"""
from __future__ import annotations

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import draw_icons as D  # noqa: E402

MAPS = "C:/Users/ren/WebstormProjects/unmached/unmached/scraped-data/images/maps"
SHOTS = ("C:/Users/ren/AppData/Local/Temp/claude/C--Users-ren-WebstormProjects-unmached-unmached/"
         "671fbf8e-b9b7-4285-83ec-c748575d9f59/scratchpad/rework/de-research/shots")


def map_crop(name, box, scale):
    im = Image.open(os.path.join(MAPS, name)).convert("RGBA").crop(box)
    return im.resize((int(im.width * scale), int(im.height * scale)), Image.LANCZOS)


def sheet_context_maps(names, path):
    strip_h = 60
    rows = []
    for size in (32, 24):
        w = D.strip_width(names, size)
        bgs = [
            (f"{size} px · Marmoreal ×1.6 (бейджи L6 при зуме K1)",
             map_crop("marmoreal.png", (330, 300, 330 + int(w / 1.6), 300 + int(strip_h / 1.6)), 1.6)),
            (f"{size} px · Sarpedon ×1.6",
             map_crop("sarpedon.png", (380, 330, 380 + int(w / 1.6), 330 + int(strip_h / 1.6)), 1.6)),
            (f"{size} px · Marmoreal ×1.0 (минимальный зум)",
             map_crop("marmoreal.png", (300, 250, 300 + w, 250 + strip_h), 1.0)),
            (f"{size} px · Sarpedon ×1.0", map_crop("sarpedon.png", (200, 420, 200 + w, 420 + strip_h), 1.0)),
        ]
        for title, bg in bgs:
            bg = bg.resize((w, strip_h), Image.LANCZOS)
            s = D.strip(names, size, bg)
            rows.append((title, s))
            rows.append((title + " · серый", D.grey(s)))
    W = max(r[1].width for r in rows) + 20
    H = 50 + sum(r[1].height + 26 for r in rows)
    sheet = Image.new("RGBA", (W, H), D.SHEET_BG)
    D.paste(sheet, D.label(W, 40, "контекст на доске: фрагменты реальных карт (только просмотр, ENV-U3) — границу держит keyline mark.keyline", 17), 0, 6)
    y = 50
    for title, s in rows:
        D.paste(sheet, D.label(W, 22, title, 13), 0, y)
        D.paste(sheet, s, 10, y + 22)
        y += s.height + 26
    sheet.convert("RGB").save(path)
    return path


# (кадр DE, кроп, подпись, наши значки того же смысла)
DE_ROWS = [
    ("02-own-hud-panel-arthur.jpg", (80, 265, 180, 345), "DE: своё сердце — белое, тёмная цифра", ["resource-hp-full"]),
    ("03-opponent-hud-medusa-hexbuttons.jpg", (245, 325, 345, 410), "DE: чужое сердце — тёмное, белая цифра", ["resource-hp-full-enemy", "resource-hp-empty"]),
    ("02-own-hud-panel-arthur.jpg", (265, 235, 470, 282), "DE: стопка (колода) и следы (движение)", ["resource-card", "action-maneuver"]),
    ("07-own-hud-medusa-action-pips.jpg", (425, 372, 595, 435), "DE: пипсы действий — фиолетовый манёвр, красная атака с кремовым кольцом", ["action-maneuver", "action-attack", "action-defense", "action-scheme"]),
    ("09-stat-icons-melee-heart-footprints.jpg", (70, 50, 250, 400), "DE: статы героя — белые жирные глифы на чёрной кляксе", ["resource-hp-full", "action-maneuver", "resource-card"]),
    ("01-duel-sarpedon-combat-full.jpg", (640, 210, 735, 300), "DE: отмена — красный крест кистью (у нас: чистый X с keyline, без кисти)", ["resource-connection-lost", "resource-connection-online", "resource-connection-reconnecting"]),
    ("16-world-hearts-base-rings.jpg", (90, 225, 310, 375), "DE: голубое кольцо — допустимая цель/защитник (у нас: бирюзовое тело pending)", ["state-pending-move", "state-pending-place"]),
    ("03-opponent-hud-medusa-hexbuttons.jpg", (570, 20, 780, 100), "DE: системные кнопки — шестиугольник, белая кромка, белый глиф", ["state-enemy", "state-sent", "state-immobilized"]),
    ("08-select-hero-arthur.jpg", (470, 285, 545, 345), "DE: ромб способности с кремовой кромкой (у нас ромб = очко действия)", ["resource-action-full", "resource-action-empty"]),
    ("18-trailer-9s-combat-vs-banner.jpg", (300, 35, 510, 95), "DE: баннер «2 vs 4» мазком кисти — язык крупных элементов, не значков", ["state-hint", "state-threat"]),
    ("05-world-tags-heart-name-sidekick-token.jpg", (60, 40, 360, 120), "DE: тег над бойцом — сердце + полоса имени цвета героя", ["marker-status-p1", "marker-status-p2", "state-boost"]),
    ("05-world-tags-heart-name-sidekick-token.jpg", (150, 130, 330, 260), "DE: жетон сайдкика на клетке — диск с ободком цвета героя", ["action-attack-token", "loader-spinner"]),
]


def sheet_vs_de(path):
    h_de = 150
    rows = []
    for shot, box, title, ours in DE_ROWS:
        de = Image.open(os.path.join(SHOTS, shot)).convert("RGBA").crop(box)
        de = de.resize((int(de.width * h_de / de.height), h_de), Image.LANCZOS)
        ours_w = sum((2 * 64 if D.is_wide(n) else 64) + 12 + (2 * 32 if D.is_wide(n) else 32) + 24 for n in ours)
        row = Image.new("RGBA", (de.width + 40 + ours_w + 20, h_de + 8), D.PANEL)
        D.paste(row, de, 4, 4)
        x = de.width + 24
        for n in ours:
            a = D.render_example(n, 64)
            b = D.render_example(n, 32)
            D.paste(row, a, x, (row.height - a.height) // 2)
            x += a.width + 12
            D.paste(row, b, x, (row.height - b.height) // 2)
            x += b.width + 24
        rows.append((title + "   ->   " + ", ".join(ours), row))
    W = max(r[1].width for r in rows) + 20
    H = 50 + sum(r[1].height + 30 for r in rows)
    sheet = Image.new("RGBA", (W, H), D.SHEET_BG)
    D.paste(sheet, D.label(W, 40, "рядом с Digital Edition: слева кроп кадра DE (только просмотр), справа наши значки 64 и 32 px — сравнение манеры, не пикселей", 17), 0, 6)
    y = 50
    for title, row in rows:
        D.paste(sheet, D.label(W, 24, title, 13), 0, y)
        D.paste(sheet, row, 10, y + 24)
        y += row.height + 30
    sheet.convert("RGB").save(path)
    return path


def build(out_dir, names=None):
    os.makedirs(out_dir, exist_ok=True)
    names = names or D.ORDER23
    print(sheet_context_maps(names, os.path.join(out_dir, "sheet-context-maps.png")))
    print(sheet_vs_de(os.path.join(out_dir, "sheet-vs-de.png")))


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(D.ROOT), "v3-review"))
