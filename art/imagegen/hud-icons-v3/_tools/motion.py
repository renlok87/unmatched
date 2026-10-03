#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Движение значков v3: каждый кадр — чистая функция времени t (мс), без случайности.

    python motion.py            # sheets/motion/: frames-<id>.png (12 кадров: 2 появления, 9 цикла, 1 уход; строка
                                # reduced motion под обычной), <id>.gif, frames-transitions.png

Константы — токены motion.icon.* (STYLE-v3.md §7); «удар» каждого цикла — одна константа (на неё вешаются звук и
хаптика): щелчок стрелок 520 мс, переворот часов 650 мс, проход головы спиннера через 12 ч, «тук» метки 300 мс.
"""
from __future__ import annotations

import math
import os

from PIL import Image

import draw_icons as D

OUT = os.path.join(D.ROOT, "sheets", "motion")

APPEAR_MS, LEAVE_MS = 180, 120
REDUCED_MS = 100
SPINNER_STEP_MS = 125
PERIOD = {"loader-spinner": 8 * SPINNER_STEP_MS, "state-pending-move": 1200, "state-pending-place": 1200,
          "state-sent": 1500, "resource-connection-reconnecting": 1200}
HIT_MS = {"state-pending-move": 520, "state-sent": 650, "state-pending-place": 300, "loader-spinner": 0,
          "resource-connection-reconnecting": 0}


def clamp01(x):
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def ease_out_cubic(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 3


def ease_in_quad(x):
    x = clamp01(x)
    return x * x


def ease_out_quad(x):
    x = clamp01(x)
    return 1 - (1 - x) ** 2


def ease_in_out_cubic(x):
    x = clamp01(x)
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def ease_out_back(x, s=0.75):
    x = clamp01(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def lerp(a, b, k):
    return a + (b - a) * k


# ------------------------------------------------------------------ параметры циклов
def spinner_params(t, reduced=False):
    step = SPINNER_STEP_MS * (2 if reduced else 1)
    return {"step": int(t // step) % 8}


def pending_move_params(t, reduced=False):
    if reduced:
        return {"ext": 1.0}
    t = t % PERIOD["state-pending-move"]
    if t < 180:
        ext = 1.0
    elif t < 480:
        ext = lerp(1.0, 0.86, ease_in_quad((t - 180) / 300))
    elif t < 520:
        ext = 0.86
    elif t < 760:
        ext = lerp(0.86, 1.0, ease_out_cubic((t - 520) / 240))
    else:
        ext = 1.0
    return {"ext": ext}


def pending_place_params(t, reduced=False):
    if reduced:
        return {"dy": 0.0}
    t = t % PERIOD["state-pending-place"]
    if t < 300:
        dy = -2.4 * ease_out_quad(t / 300)
    elif t < 600:
        dy = -2.4 * (1 - ease_in_quad((t - 300) / 300))
    else:
        dy = 0.0
    return {"dy": dy}


def sent_params(t, reduced=False):
    if reduced:
        return {"top": 0.55, "bottom": 0.45, "angle": 0.0, "stream": False}
    t = t % PERIOD["state-sent"]
    if t < 550:
        k = t / 550
        return {"top": 0.55 * (1 - k), "bottom": 0.45 + 0.55 * k, "angle": 0.0, "stream": True}
    if t < 650:
        return {"top": 0.0, "bottom": 1.0, "angle": 0.0, "stream": False}
    if t < 950:
        return {"top": 0.0, "bottom": 1.0, "angle": math.pi * ease_in_out_cubic((t - 650) / 300), "stream": False}
    if t < 1400:
        k = (t - 950) / 450
        return {"top": 1.0 - 0.45 * k, "bottom": 0.45 * k, "angle": 0.0, "stream": True}
    return {"top": 0.55, "bottom": 0.45, "angle": 0.0, "stream": False}


def reconnect_params(t, reduced=False):
    if reduced:
        return {"angle": 0.0}
    return {"angle": 2 * math.pi * ((t % PERIOD["resource-connection-reconnecting"]) / PERIOD["resource-connection-reconnecting"])}


CYCLES = {
    "loader-spinner": spinner_params, "state-pending-move": pending_move_params,
    "state-pending-place": pending_place_params, "state-sent": sent_params,
    "resource-connection-reconnecting": reconnect_params,
}


# ------------------------------------------------------------------ огибающая появления / ухода
def envelope(t, total, reduced=False):
    """(scale, opacity) всего значка: appear 180 мс (0,80 → 1,04 на 40 % → 1,00, ease-out-back; opacity за 120),
    leave 120 мс (opacity → 0, scale → 0,92 ease-in-quad). reduced: только opacity ≤ 100 мс."""
    if reduced:
        if t < REDUCED_MS:
            return 1.0, clamp01(t / REDUCED_MS)
        if t > total - REDUCED_MS:
            return 1.0, clamp01((total - t) / REDUCED_MS)
        return 1.0, 1.0
    if t < APPEAR_MS:
        return lerp(0.80, 1.0, ease_out_back(t / APPEAR_MS)), 0.15 + 0.85 * clamp01(t / 120)   # кадр 0 не пустой
    if t > total - LEAVE_MS:
        x = (t - (total - LEAVE_MS)) / LEAVE_MS
        return 1.0 - 0.08 * ease_in_quad(x), 1.0 - ease_in_quad(x)
    return 1.0, 1.0


def frame(icon, size, t, total, reduced=False):
    """Кадр в момент t: цикл начинается после появления (t − 180), уход — последние 120 мс."""
    params = CYCLES[icon](max(0.0, t - APPEAR_MS), reduced) if icon in CYCLES else {}
    base = D.render(icon, size, **params)
    sc, op = envelope(t, total, reduced)
    w, h = base.size
    if abs(sc - 1.0) > 1e-3:
        im = base.resize((max(1, round(w * sc)), max(1, round(h * sc))), Image.LANCZOS)
        base = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        base.paste(im, ((w - im.width) // 2, (h - im.height) // 2), im)
    if op < 1.0:
        base.putalpha(base.getchannel("A").point(lambda v: int(v * op)))
    return base


# ------------------------------------------------------------------ листы
def frame_sheet(icon):
    period = PERIOD[icon]
    total = APPEAR_MS + period + LEAVE_MS
    ts = [40, 120] + [APPEAR_MS + period * i / 9 for i in range(9)] + [total - 50]
    big, small = 96, 32
    wide = D.is_wide(icon)
    cw = (2 * big if wide else big) + 24 + (2 * small if wide else small) * 3 + 16
    ch = big + 8
    W = 20 + 12 * cw
    H = 60 + 2 * (ch + 36)
    sheet = Image.new("RGBA", (W, H), D.SHEET_BG)
    D.paste(sheet, D.label(W, 36, f"{icon}: 12 кадров = 2 появления (180 мс) + 9 цикла ({period} мс) + 1 ухода (120 мс); 96 px и 32 px ×3; верх — обычный, низ — reduced motion; удар цикла при {HIT_MS[icon]} мс", 15), 0, 8)
    for row, red in ((0, False), (1, True)):
        y = 60 + row * (ch + 36)
        for i, t in enumerate(ts):
            x = 20 + i * cw
            panel = Image.new("RGBA", (cw - 8, ch), D.PANEL)
            D.paste(panel, frame(icon, big, t, total, red), 4, 4)
            s = frame(icon, small, t, total, red)
            D.paste(panel, D.xN(s, 3), (2 * big if wide else big) + 16, (ch - small * 3) // 2)
            D.paste(sheet, panel, x, y)
            D.paste(sheet, D.label(cw - 8, 20, f"t = {int(t)} мс" + ("  reduced" if red else ""), 12), x, y + ch + 6)
    p = os.path.join(OUT, f"frames-{icon}.png")
    sheet.convert("RGB").save(p)
    return p


def gif(icon):
    """GIF: длительности в единицах 10 мс → кадры по 20 мс; спиннер — 8 кадров 120/130 мс."""
    period = PERIOD[icon]
    sizes = (128, 48, 32, 24)
    gap = 16
    W = sum(2 * s if D.is_wide(icon) else s for s in sizes) + gap * (len(sizes) + 1)
    H = 128 + 2 * gap
    if icon == "loader-spinner":
        times = [APPEAR_MS + i * SPINNER_STEP_MS for i in range(8)]
        durations = [120, 130] * 4
    else:
        n = period // 20
        times = [APPEAR_MS + i * 20 for i in range(n)]
        durations = [20] * n
    frames = []
    total = APPEAR_MS + period + LEAVE_MS + 10 ** 6   # без ухода в зацикленном GIF
    for t in times:
        bg = Image.new("RGBA", (W, H), D.PANEL)
        x = gap
        for s in sizes:
            im = frame(icon, s, t, total)
            D.paste(bg, im, x, gap + (128 - s) // 2)
            x += im.width + gap
        frames.append(bg.convert("RGB").quantize(colors=64, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE))
    p = os.path.join(OUT, f"{icon}.gif")
    frames[0].save(p, save_all=True, append_images=frames[1:], duration=durations, loop=0, disposal=1)
    return p


def transitions_sheet(icons=("state-enemy", "action-attack", "marker-status-p1", "resource-hp-full")):
    """Появление (180 мс, 7 кадров) и уход (120 мс, 5 кадров): первый кадр не пустой, последний появления = мастер."""
    n_a, n_l, big = 7, 5, 96
    rows = []
    for icon in icons:
        cells = []
        total = APPEAR_MS + 1000 + LEAVE_MS
        for i in range(n_a):
            cells.append((f"+{int(i * APPEAR_MS / (n_a - 1))}", frame(icon, big, i * APPEAR_MS / (n_a - 1), total)))
        for i in range(n_l):
            t = total - LEAVE_MS + i * LEAVE_MS / (n_l - 1)
            cells.append((f"−{int(LEAVE_MS - i * LEAVE_MS / (n_l - 1))}", frame(icon, big, t, total)))
        rows.append((icon, cells))
    cw = 2 * big + 16
    W = 20 + (n_a + n_l) * cw
    H = 50 + len(rows) * (big + 50)
    sheet = Image.new("RGBA", (W, H), D.SHEET_BG)
    D.paste(sheet, D.label(W, 36, "переходы: появление 180 мс (scale 0,80 → 1,04 → 1,00 ease-out-back, opacity за 120) и уход 120 мс (opacity → 0, scale → 0,92); reduced motion — только opacity ≤ 100 мс", 15), 0, 8)
    for r, (icon, cells) in enumerate(rows):
        y = 50 + r * (big + 50)
        for i, (lab, im) in enumerate(cells):
            x = 20 + i * cw
            panel = Image.new("RGBA", (cw - 8, big + 8), D.PANEL)
            D.paste(panel, im, (panel.width - im.width) // 2, 4)
            D.paste(sheet, panel, x, y)
            D.paste(sheet, D.label(cw - 8, 20, f"{icon} {lab} мс", 11), x, y + big + 10)
    p = os.path.join(OUT, "frames-transitions.png")
    sheet.convert("RGB").save(p)
    return p


def build():
    os.makedirs(OUT, exist_ok=True)
    for icon in CYCLES:
        print(frame_sheet(icon))
        print(gif(icon))
    print(transitions_sheet())


if __name__ == "__main__":
    build()
