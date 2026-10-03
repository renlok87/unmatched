#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Лист «было → стало»: значки v2 (art/imagegen/hud-icons-v2) и v3 (этот набор) по всем 23 id.

    python art/imagegen/hud-icons-v3/_tools/compare_v2_v3.py

Колонки: v2 128 | v2 24 | v3 128 | v3 32 | v3 24 | v3 24 серый — на панели tag.background.
v2 уменьшается из мастера (так он и экспортировался), v3 берётся из sizes/ (рендер из вектора).
Выход: sheets/compare-v2-v3.png.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import draw_icons as D  # noqa: E402

V3 = D.ROOT
V2 = os.path.join(os.path.dirname(V3), "hud-icons-v2")
COLS = ("v2 128", "v2 24", "v3 128", "v3 32", "v3 24", "v3 24 серый")


def cell(im, w, h, bg):
    c = Image.new("RGBA", (w, h), bg)
    c.alpha_composite(im, ((w - im.width) // 2, (h - im.height) // 2))
    return c


def fit(im, h):
    return im.resize((round(im.width * h / im.height), h), Image.LANCZOS)


def main():
    names = D.ORDER23
    lab_w, gap, row_h = 260, 14, 140
    widths = [256, 64, 256, 80, 64, 110]
    W = lab_w + sum(widths) + gap * len(widths)
    H = 40 + len(names) * (row_h + 6)
    sheet = Image.new("RGBA", (W, H), D.SHEET_BG)
    x = lab_w
    for title, w in zip(COLS, widths):
        sheet.alpha_composite(D.label(w, 30, title, size=15), (x, 4))
        x += w + gap
    y = 40
    for nm in names:
        sheet.alpha_composite(D.label(lab_w - 10, 30, nm, size=14), (6, y + row_h // 2 - 15))
        wide = D.is_wide(nm)
        v2 = Image.open(os.path.join(V2, nm + ".png")).convert("RGBA")
        v3m = Image.open(os.path.join(V3, "masters", nm + ".png")).convert("RGBA")
        s24 = Image.open(os.path.join(V3, "sizes", nm + "-24.png")).convert("RGBA")
        s32 = Image.open(os.path.join(V3, "sizes", nm + "-32.png")).convert("RGBA")
        k = 2 if wide else 1
        cells = [
            fit(v2, 128),
            v2.resize((24 * k, 24), Image.LANCZOS),
            fit(v3m, 128),
            s32,
            s24,
            D.grey(s24) if hasattr(D, "grey") else s24.convert("LA").convert("RGBA"),
        ]
        x = lab_w
        for im, w in zip(cells, widths):
            sheet.alpha_composite(cell(im, w, row_h, D.PANEL), (x, y))
            x += w + gap
        y += row_h + 6
    out = os.path.join(V3, "sheets", "compare-v2-v3.png")
    sheet.convert("RGB").save(out, optimize=True)
    print(out, sheet.size)


if __name__ == "__main__":
    main()
