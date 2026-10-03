#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HUD icons v3 «Жетон-эмблема» на основе Unmatched: Digital Edition — один векторный движок (pycairo).

    python draw_icons.py                 # пересобирает всё: masters/, sizes/, layers/, sheets/, manifest.json, audit.json
    python draw_icons.py --review DIR    # дополнительно листы со сканами карт и кадрами DE в DIR (вне репозитория)
    python draw_icons.py --only state-boost,action-attack   # подмножество (для отладки)

Единицы: холст 32 u × 32 u (плашки 64 × 32 u), мастер 1024 px → 1 u = 32 px. Каждый размер рендерится из вектора:
толщины слоёв (keyline K, кромка E, штрих W, кольцо) снэпятся к целым пикселям, прямые границы тел ложатся на пиксель,
уровень детализации глифа зависит от размера (Spec.detail); глифы не масштабируются контекстом — их горизонтальные
кромки снэпятся в абсолютных координатах (Spec.sx/sy), составные фигуры собираются заливкой + вырезом без клипа.
Цифры в текстуры не печатаются — только на листах.
Все цвета — токены docs/unreal/contracts/hud/hud-style-tokens.json плюс новые из STYLE-v3.md §2.1.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from functools import lru_cache

import cairo
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                       # art/imagegen/hud-icons-v3
FONT_BC = "C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/Roboto-BoldCondensed.ttf"
FONT_RG = "C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/Roboto-Regular.ttf"

U = 32            # единиц на сторону
MASTER = 1024     # px мастера
SIZES = (16, 21, 24, 32, 48, 64, 96)
SHEET_SIZES = (48, 32, 24, 16)

# ------------------------------------------------------------------------------------------------ палитра по ролям
TOKENS = {
    # hud-style-tokens.json
    "card.navy": "#061623", "card.cream": "#F9EBDB", "card.glyph": "#FAF8F2", "mark.keyline": "#111317",
    "state.error": "#D9483F", "zone.purple": "#8A56C6", "text.secondary": "#B9B2A6",
    "team.p1.screen": "#DAC576", "team.p2.screen": "#5786A8",
    "icon.token.body": "#161A28", "icon.token.rim": "#F2ECDE", "tag.background": "#161A28",
    "card.type.attack": "#DC2F33", "card.type.defense": "#2976AE", "card.type.versatile": "#6B4E8F",
    "card.type.scheme": "#FDBE72",
    # новые (STYLE-v3.md §2.1)
    "state.pending": "#0D7A89",
}
ROLE = {
    "body": "card.navy",            # тело жетонов состояния, плашек, ленты, тёмных ресурсов
    "edge": "card.cream",           # кремовый торец высечки
    "glyph": "card.glyph",          # плоская белая печать
    "keyline": "mark.keyline",      # тень высечки — несущая граница на доске
    "light": "card.glyph",          # тело светлых ресурсов («есть»): сердце своё, ромб
    "dim": "text.secondary",        # приглушённый глиф (хвост спиннера, связь при сбое)
    "error": "state.error",         # только знак X
    "pending": "state.pending",     # тело плашек выбора цели (DE: «можно выбрать»)
    "attack": "card.type.attack", "defense": "card.type.defense",
    "maneuver": "card.type.versatile", "scheme": "card.type.scheme",
    "team1": "team.p1.screen", "team2": "team.p2.screen",
    "token.body": "icon.token.body", "token.rim": "icon.token.rim",
    "hp.rim": "card.type.attack",   # кромка сердца здоровья (приём DE): красный игры, не state.error
    "panel": "tag.background",
}


def hx(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


C = {k: hx(TOKENS[v]) for k, v in ROLE.items()}
C["white"] = (1.0, 1.0, 1.0)


# ------------------------------------------------------------------------------------------------ спецификация размера
class Spec:
    """Толщины в u, снэпнутые к целым px данного размера: px = max(1, floor(u·k + 0.5))."""

    def __init__(self, size: int):
        self.size = size
        self.k = size / U
        self.detail = 0 if size <= 20 else 1 if size <= 40 else 2
        self.M = self.pxu(1.0)        # поле холста
        self.K = self.pxu(1.0)        # keyline
        self.E = self.pxu(1.25)       # кромка
        self.W = self.pxu(2.25)       # штрих глифа
        self.W2 = self.pxu(1.6)       # тонкий штрих (контур колбы, круговая стрелка)
        self.ring = self.pxu(1.75)    # кольцо BOOST
        self.rule = self.pxu(0.5)     # линейка плашки
        self.rim = self.pxu(0.5)      # ободок жетона цели (D-5)

    def px(self, u, mn=1):
        return max(mn, math.floor(u * self.k + 0.5))

    def pxu(self, u, mn=1):
        return self.px(u, mn) / self.k

    def snap(self, u):
        """координата в u → ближайший пиксель (в u)."""
        return math.floor(u * self.k + 0.5) / self.k

    ox = 0.0   # начало текущего глифа в абсолютных u (ставит glyph())
    oy = 0.0

    def sx(self, x):
        """локальная x глифа → снэп к пикселю в абсолютных координатах (и на мастере 1024)."""
        return self.snap(self.ox + x) - self.ox

    def sy(self, y):
        return self.snap(self.oy + y) - self.oy

    @property
    def KE(self):
        return self.K + self.E

    @property
    def body_in(self):
        return self.M + self.K + self.E


# ------------------------------------------------------------------------------------------------ геометрия
def _offset_poly(pts, d):
    """Смещение простого многоугольника внутрь на d (d < 0 — наружу)."""
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n)) / 2
    sgn = 1.0 if area > 0 else -1.0
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        dx, dy = x1 - x0, y1 - y0
        L = math.hypot(dx, dy)
        nx, ny = sgn * (-dy / L), sgn * (dx / L)
        lines.append(((x0 + nx * d, y0 + ny * d), (x1 + nx * d, y1 + ny * d)))
    out = []
    for i in range(n):
        (ax, ay), (bx, by) = lines[i - 1]
        (cx, cy), (dx_, dy_) = lines[i]
        r1x, r1y = bx - ax, by - ay
        r2x, r2y = dx_ - cx, dy_ - cy
        den = r1x * r2y - r1y * r2x
        if abs(den) < 1e-9:
            out.append((bx, by))
            continue
        t = ((cx - ax) * r2y - (cy - ay) * r2x) / den
        out.append((ax + r1x * t, ay + r1y * t))
    return out


def _is_convex(pts, i):
    n = len(pts)
    area = sum(pts[j][0] * pts[(j + 1) % n][1] - pts[(j + 1) % n][0] * pts[j][1] for j in range(n))
    (px, py), (vx, vy), (nx, ny) = pts[i - 1], pts[i], pts[(i + 1) % n]
    cross = (vx - px) * (ny - vy) - (vy - py) * (nx - vx)
    return (cross > 0) == (area > 0)


def rounded_polygon(ctx, pts, radii):
    n = len(pts)
    first = True
    for i in range(n):
        (px, py), (vx, vy), (nx, ny) = pts[i - 1], pts[i], pts[(i + 1) % n]
        r = radii[i]
        if r <= 0.01:
            (ctx.move_to if first else ctx.line_to)(vx, vy)
            first = False
            continue
        ax, ay = px - vx, py - vy
        bx, by = nx - vx, ny - vy
        la, lb = math.hypot(ax, ay), math.hypot(bx, by)
        ax, ay, bx, by = ax / la, ay / la, bx / lb, by / lb
        cosang = max(-1.0, min(1.0, ax * bx + ay * by))
        theta = math.acos(cosang)
        if theta < 1e-6 or abs(theta - math.pi) < 1e-6:
            (ctx.move_to if first else ctx.line_to)(vx, vy)
            first = False
            continue
        t = r / math.tan(theta / 2)
        t = min(t, la * 0.5, lb * 0.5)
        r = t * math.tan(theta / 2)
        t1 = (vx + ax * t, vy + ay * t)
        t2 = (vx + bx * t, vy + by * t)
        mx, my = ax + bx, ay + by
        lm = math.hypot(mx, my)
        cdist = r / math.sin(theta / 2)
        cx_, cy_ = vx + mx / lm * cdist, vy + my / lm * cdist
        a1 = math.atan2(t1[1] - cy_, t1[0] - cx_)
        a2 = math.atan2(t2[1] - cy_, t2[0] - cx_)
        (ctx.move_to if first else ctx.line_to)(*t1)
        first = False
        da = (a2 - a1) % (2 * math.pi)
        if da <= math.pi:
            ctx.arc(cx_, cy_, r, a1, a2)
        else:
            ctx.arc_negative(cx_, cy_, r, a1, a2)
    ctx.close_path()


class Poly:
    """Многоугольный силуэт с радиусами вершин; path(d) — контур, смещённый внутрь на d (полосы постоянной ширины)."""

    def __init__(self, pts, radii):
        self.pts, self.radii = list(pts), list(radii)

    def path(self, ctx, d=0.0):
        pts = _offset_poly(self.pts, d) if d else self.pts
        radii = [max(r - d, 0.0) if _is_convex(self.pts, i) else max(r + d, 0.0) for i, r in enumerate(self.radii)]
        rounded_polygon(ctx, pts, radii)


class Disc:
    def __init__(self, cx, cy, r):
        self.cx, self.cy, self.r = cx, cy, r

    def path(self, ctx, d=0.0):
        ctx.new_sub_path()
        ctx.arc(self.cx, self.cy, max(self.r - d, 0.05), 0, 2 * math.pi)
        ctx.close_path()


def rect_sil(x, y, w, h, r):
    return Poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], [r, r, r, r])


# ------------------------------------------------------------------------------------------------ cairo helpers
def rgb(ctx, c, a=1.0):
    ctx.set_source_rgba(c[0], c[1], c[2], a)


def fill(ctx, c, a=1.0):
    rgb(ctx, c, a)
    ctx.fill()


def clear(ctx):
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_CLEAR)
    ctx.fill()
    ctx.restore()


def circle(ctx, cx, cy, r):
    ctx.new_sub_path()
    ctx.arc(cx, cy, r, 0, 2 * math.pi)
    ctx.close_path()


def poly(ctx, pts):
    ctx.move_to(*pts[0])
    for p in pts[1:]:
        ctx.line_to(*p)
    ctx.close_path()


def grow_rect(x, y, w, h, g):
    return x - g, y - g, w + 2 * g, h + 2 * g


def token(ctx, sil, sp: Spec, body=None, edge=None, keyline=True):
    """Жетон-высечка: keyline (d = 0) → кромка (d = K) → тело (d = K + E). Три тона, без вкладок."""
    body = body or C["body"]
    edge = edge or C["edge"]
    if keyline:
        sil.path(ctx, 0)
        fill(ctx, C["keyline"])
    sil.path(ctx, sp.K if keyline else 0)
    fill(ctx, edge)
    sil.path(ctx, (sp.K if keyline else 0) + sp.E)
    fill(ctx, body)


def hollow_token(ctx, sil, sp: Spec, edge=None):
    """Пустой жетон: keyline → кремовый штрих W → keyline → прозрачно."""
    edge = edge or C["edge"]
    sil.path(ctx, 0)
    fill(ctx, C["keyline"])
    sil.path(ctx, sp.K)
    fill(ctx, edge)
    sil.path(ctx, sp.K + sp.W)
    fill(ctx, C["keyline"])
    sil.path(ctx, sp.K + sp.W + sp.K)
    clear(ctx)


# ------------------------------------------------------------------------------------------------ текст (только листы)
@lru_cache(maxsize=4)
def _font(path):
    from fontTools.ttLib import TTFont
    f = TTFont(path)
    cap = getattr(f["OS/2"], "sCapHeight", 0) or int(f["head"].unitsPerEm * 0.711)
    return f, f.getGlyphSet(), f.getBestCmap(), f["hmtx"], cap


def _gname(cmap, hmtx, ch):
    """имя глифа для символа; нет в шрифте → дефис, нет и его → пробел."""
    for c in (ch, "-", " "):
        n = cmap.get(ord(c))
        if n is not None and n in hmtx.metrics:
            return n
    return next(iter(hmtx.metrics))


def text_width(text, cap_h, font=FONT_BC, tracking=0.0):
    f, gs, cmap, hmtx, cap = _font(font)
    s = cap_h / cap
    return sum(hmtx[_gname(cmap, hmtx, ch)][0] for ch in text) * s + tracking * (len(text) - 1)


def text_path(ctx, text, cap_h, cx, cy, font=FONT_BC, align="center", tracking=0.0):
    """Текст как путь cairo: высота заглавной/цифры = cap_h, центр по кап-высоте в (cx, cy)."""
    from fontTools.pens.basePen import BasePen

    f, gs, cmap, hmtx, cap = _font(font)
    s = cap_h / cap

    class Pen(BasePen):
        def __init__(self, glyph_set, ox, oy):
            super().__init__(glyph_set)
            self.ox, self.oy = ox, oy

        def _moveTo(self, p):
            ctx.move_to(self.ox + p[0] * s, self.oy - p[1] * s)

        def _lineTo(self, p):
            ctx.line_to(self.ox + p[0] * s, self.oy - p[1] * s)

        def _curveToOne(self, p1, p2, p3):
            ctx.curve_to(self.ox + p1[0] * s, self.oy - p1[1] * s, self.ox + p2[0] * s, self.oy - p2[1] * s,
                         self.ox + p3[0] * s, self.oy - p3[1] * s)

        def _qCurveToOne(self, p1, p2):
            x0, y0 = ctx.get_current_point()
            c1 = (x0 + 2 / 3 * (self.ox + p1[0] * s - x0), y0 + 2 / 3 * (self.oy - p1[1] * s - y0))
            x2, y2 = self.ox + p2[0] * s, self.oy - p2[1] * s
            c2 = (x2 + 2 / 3 * (self.ox + p1[0] * s - x2), y2 + 2 / 3 * (self.oy - p1[1] * s - y2))
            ctx.curve_to(c1[0], c1[1], c2[0], c2[1], x2, y2)

        def _closePath(self):
            ctx.close_path()

    w = text_width(text, cap_h, font, tracking)
    x = cx - w / 2 if align == "center" else cx if align == "left" else cx - w
    y = cy + cap_h / 2
    for ch in text:
        name = _gname(cmap, hmtx, ch)
        gs[name].draw(Pen(gs, x, y))
        x += hmtx[name][0] * s + tracking


# ------------------------------------------------------------------------------------------------ глифы
# Все глифы рисуются в боксе с началом в центре бокса, x вправо, y вниз, в u, БЕЗ масштабирования контекста: размер
# задаётся числами, горизонтальные кромки снэпятся к пиксельным рядам через sp.sy() в абсолютных координатах (работает и
# на мастере 1024 — ревью G6). Глиф = один push_group; вырезы — OPERATOR_CLEAR внутри группы (тело не пробивается).
# Правило ДНК 5 в редакции ревью (G2): любая деталь (зазор, отверстие, основание луча) ≥ 1 u со снэпом; при detail ≤ 1
# детали убираются, а не утончаются. Составные фигуры — одним путём или заливка + вырез, без клипа (G5).

def g_burst(ctx, sp: Spec, R=9.0):
    """Звезда-взрыв как блок атаки на карте и пипс атаки DE: колючий взрыв из острых лучей, длинные и короткие
    чередуются, длины чуть неровные (рисованный взрыв, не правильная звезда), ядро малое — лучи читаются как вспышка.
    detail 2: 14 лучей, ядро 0,44 R (основание луча ≈ 1,9 u ≥ 1 u); detail 1: 10 лучей, ядро 0,5 R;
    detail 0: 8 лучей × (1,0 / 0,8), ядро 0,6 R (основание ≥ 2 px при 16 px)."""
    if sp.detail == 0:
        n, core = 8, 0.60
        tips = [1.0, 0.80] * 4
        jit_t = [0.0] * n
        jit_v = [0.0] * n
    elif sp.detail == 1:
        # нечётное число лучей: при 10 чередование длинный/короткий даёт пятиконечную звезду (= «избранное», не атака)
        n, core = 11, 0.52
        tips = [1.0, 0.84, 0.95, 0.80, 1.0, 0.86, 0.92, 0.82, 0.98, 0.85, 0.90]
        jit_t = [0, 2, -2, 1, -1, 2, -2, 1, 1, -1, 0]
        jit_v = [0] * n
    else:
        n, core = 14, 0.44
        tips = [1.0, 0.68, 0.93, 0.72, 0.98, 0.64, 0.90, 0.70, 1.0, 0.66, 0.94, 0.73, 0.96, 0.67]
        jit_t = [0, 2, -2, 3, -1, 2, -3, 1, -2, 2, 1, -2, 3, -1]   # угол острия, °
        jit_v = [1, -1, 1, -1, 0, 1, -1, 1, 0, -1, 1, 0, -1, 1]    # угол впадины, °
    pts = []
    for i in range(n):
        a = math.radians(-90 + i * 360 / n + jit_t[i])
        pts.append((R * tips[i] * math.cos(a), R * tips[i] * math.sin(a)))
        b = math.radians(-90 + (i + 0.5) * 360 / n + jit_v[i])
        pts.append((R * core * math.cos(b), R * core * math.sin(b)))
    poly(ctx, pts)
    ctx.fill()


def g_shield(ctx, sp: Spec, w=11.0, h=13.0):
    """Щит с карты: прямой верх, верхние углы r 0,8, прямые плечи, две дуги к острию."""
    hw, top, tip = w / 2, -h / 2, h / 2
    side_end = top + 0.385 * h
    r = 0.8
    ctx.new_sub_path()
    ctx.move_to(-hw + r, top)
    ctx.line_to(hw - r, top)
    ctx.arc(hw - r, top + r, r, -math.pi / 2, 0)
    ctx.line_to(hw, side_end)
    ctx.curve_to(hw, side_end + 0.42 * h, 0.55 * hw, tip - 0.16 * h, 0, tip)
    ctx.curve_to(-0.55 * hw, tip - 0.16 * h, -hw, side_end + 0.42 * h, -hw, side_end)
    ctx.line_to(-hw, top + r)
    ctx.arc(-hw + r, top + r, r, math.pi, 1.5 * math.pi)
    ctx.close_path()
    ctx.fill()


def g_bolt(ctx, sp: Spec, s=1.0):
    """Молния с карты: 7 вершин, горизонтальные срезы, ширина 8 u."""
    pts = [(-2, -8), (3.5, -8), (0.5, -1.5), (4, -1.5), (-3.5, 8), (-0.5, 0.5), (-4, 0.5)]
    poly(ctx, [(x * s, y * s) for x, y in pts])
    ctx.fill()


# Отпечаток левой ноги (внутренняя сторона +x, носок вверх), в долях w × h: широкий скруглённый носок с большим пальцем
# ближе к внутренней стороне, свод — вогнутость по внутренней стороне, наружный край почти прямой, каблук уже подошвы.
# Приёмка ART-011 О-1: симметричная капсула + прямоугольный каблук читались парой «!!» — так рисовать нельзя.
BOOT_FOOT = ((-0.47, -0.28), (-0.34, -0.44), (-0.10, -0.51), (0.16, -0.49), (0.38, -0.40), (0.50, -0.21),
             (0.44, -0.02), (0.22, 0.16), (0.27, 0.32), (0.17, 0.47), (-0.04, 0.50), (-0.24, 0.46),
             (-0.35, 0.32), (-0.42, 0.12), (-0.50, -0.10))
BOOT_CUT = ((0.30, 0.15), (-0.50, 0.26))   # ось зазора подошва / каблук: по своду, внутренний конец выше (как в DE)


def _smooth_closed(ctx, pts, tension=0.5):
    """Замкнутый сплайн Catmull-Rom через точки (кубические Безье, касательные непрерывны)."""
    n = len(pts)
    ctx.move_to(*pts[0])
    for i in range(n):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[(i + 1) % n], pts[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) * tension / 3, p1[1] + (p2[1] - p0[1]) * tension / 3)
        c2 = (p2[0] - (p3[0] - p1[0]) * tension / 3, p2[1] - (p3[1] - p1[1]) * tension / 3)
        ctx.curve_to(*c1, *c2, *p2)
    ctx.close_path()


def _boot(ctx, sp: Spec, w, h, rot=0.0, mirror=1, solid=False):
    """Отпечаток ботинка как в DE: подошва со сводом и каблук, разделённые диагональным зазором ≥ 1 px по своду
    (внутренний конец выше); solid — без зазора (16 px). Начало — центр отпечатка, носок вверх; mirror −1 — правая
    нога. Обе части — одна фигура BOOT_FOOT под клипом полуплоскости (вырез CLEAR задел бы соседний отпечаток)."""
    g = 0.0 if solid else sp.pxu(1.0)
    pts = [(x * w, y * h) for x, y in BOOT_FOOT]
    (ax, ay), (bx, by) = [(x * w, y * h) for x, y in BOOT_CUT]
    dx, dy = bx - ax, by - ay
    L = math.hypot(dx, dy)
    nx, ny = -dy / L, dx / L
    if ny < 0:                                  # нормаль к каблуку (вниз)
        nx, ny = -nx, -ny
    ex, ey = dx / L * 3 * h, dy / L * 3 * h
    ctx.save()
    ctx.scale(mirror, 1)
    ctx.rotate(math.radians(rot))
    for side in ((0,) if solid else (-1, 1)):
        ctx.save()
        if side:
            off, far = side * g / 2, side * 3 * h
            p0 = (ax + nx * off - ex, ay + ny * off - ey)
            p1 = (ax + nx * off + ex, ay + ny * off + ey)
            poly(ctx, [p0, p1, (p1[0] + nx * far, p1[1] + ny * far), (p0[0] + nx * far, p0[1] + ny * far)])
            ctx.clip()
        _smooth_closed(ctx, pts)
        ctx.fill()
        ctx.restore()
    ctx.restore()


def g_boots(ctx, sp: Spec):
    """Манёвр: два отпечатка ботинка как в DE (левый выше правого, носки врозь на 12°); detail 0 — без зазора."""
    solid = sp.detail == 0
    for dx, dy, m, rot in ((-3.6, -2.0, 1, -12.0), (3.6, 2.0, -1, -12.0)):
        ctx.save()
        ctx.translate(dx, dy)
        _boot(ctx, sp, 6.4, 13.4, rot=rot, mirror=m, solid=solid)
        ctx.restore()


def g_anchor(ctx, sp: Spec):
    """«Обездвижен» = «на якоре»: кольцо (вырез r 1,2 при detail ≥ 1), шток W, поперечина, дуга-рога W с лапами-
    наконечниками. Перечёркнутые следы отвергнуты: полоса крошит подошвы и каблуки на осколки, а одиночный след = «!».
    Бокс ≈ 18 × 18 u, силуэт не повторяет ни один значок набора."""
    w = sp.W if sp.detail >= 1 else max(sp.W, 1.0 / sp.k)
    # кольцо
    ry_ = -7.0
    circle(ctx, 0, ry_, 2.7)
    ctx.fill()
    if sp.detail >= 1 and 1.2 * sp.k >= 1.0:
        circle(ctx, 0, ry_, 1.2)
        clear(ctx)
    # поперечина
    y0 = sp.sy(-4.35)
    ctx.rectangle(-5.0, y0, 10.0, sp.pxu(2.0))
    ctx.fill()
    # шток
    ctx.rectangle(sp.sx(-w / 2), ry_ + 2.0, w, 15.0)
    ctx.fill()
    # рога: дуга вниз
    R, cy = 7.2, 0.4
    a0, a1 = math.radians(22), math.radians(158)
    ctx.new_sub_path()
    ctx.arc(0, cy, R, a0, a1)
    ctx.set_line_width(w)
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    ctx.stroke()
    # лапы: наконечники по касательной на концах дуги, остриём вверх-наружу
    for a, sgn in ((a0, 1), (a1, -1)):
        ex, ey = R * math.cos(a), cy + R * math.sin(a)
        dx, dy = sgn * math.sin(a), -sgn * math.cos(a)    # касательная от низа дуги к её концу (вверх-наружу)
        nx, ny = -dy, dx
        L, hb = 3.2, 2.3
        bx, by = ex - dx * 0.6, ey - dy * 0.6
        poly(ctx, [(bx + nx * hb, by + ny * hb), (ex + dx * L, ey + dy * L), (bx - nx * hb, by - ny * hb)])
        ctx.fill()


def g_pawn(ctx, sp: Spec):
    """Шахматная пешка (фигурка противника на клетке), 10,8 × 19,2 u: шар r 3,25, воротник 8 × 1,6, корпус-трапеция
    полуширина 2,3 → 4,3, плинт 10,8 × 3 с фасками 1 u сверху. Зазоры = 1 px со снэпом: два при detail 2
    (шар/воротник, воротник/корпус), один при detail 1 (шар/воротник), ни одного при detail 0 (сплошной силуэт)."""
    H, r = 19.2, 3.25
    g = sp.pxu(1.0)
    y_top = -H / 2
    cy_ball = y_top + r
    circle(ctx, 0, cy_ball, r)
    ctx.fill()
    g1 = g if sp.detail >= 1 else -0.4
    g2 = g if sp.detail >= 2 else 0.0
    c0 = sp.sy(cy_ball + r + g1)
    c1 = sp.sy(c0 + 1.6)
    ctx.rectangle(-4.0, c0, 8.0, c1 - c0)
    ctx.fill()
    b0 = c1 + g2
    p0 = sp.sy(H / 2 - 3.0)
    p1 = sp.sy(H / 2)
    poly(ctx, [(-2.3, b0), (2.3, b0), (4.3, p0 + 0.3), (-4.3, p0 + 0.3)])
    ctx.fill()
    poly(ctx, [(-4.4, p0), (4.4, p0), (5.4, p0 + 1.0), (5.4, p1), (-5.4, p1), (-5.4, p0 + 1.0)])
    ctx.fill()


def g_hourglass(ctx, sp: Spec, top=0.55, bottom=0.45, angle=0.0, stream=False):
    """Песочные часы 13 × 17,5 u: планки 13 × 1,5 (снэп), колба 12 u у планок / 4,6 u в талии — сплошной силуэт, «воздух» — два вырезанных трапеция
    (заливка + CLEAR, без клипа и штриха → без швов), песок = остаток белого; detail 0 — сплошной силуэт с талией."""
    ctx.save()
    ctx.rotate(angle)
    snap = sp.sy if abs(angle) < 1e-6 else (lambda y: y)
    bw, ch = 6.5, 0.5
    bh = sp.pxu(1.5)
    y_out = snap(8.75)
    y_in = y_out - bh
    for sgn in (-1, 1):
        a, b = (y_in, y_out) if sgn > 0 else (-y_out, -y_in)
        poly(ctx, [(-bw + ch, a), (bw - ch, a), (bw, a + ch), (bw, b - ch), (bw - ch, b), (-bw + ch, b),
                   (-bw, b - ch), (-bw, a + ch)])
        ctx.fill()
    hw0, wst = 6.0, 2.3                                   # колба: полуширина у планки и в талии
    if sp.detail == 0:
        wst = max(wst, 1.0 / sp.k)
    poly(ctx, [(-hw0, -y_in - 0.3), (hw0, -y_in - 0.3), (wst, 0), (hw0, y_in + 0.3), (-hw0, y_in + 0.3), (-wst, 0)])
    ctx.fill()
    if sp.detail == 0:
        ctx.restore()
        return
    lw = sp.W2                                            # контур колбы и перемычка в талии
    slope = (hw0 - wst) / y_in
    hw_top = hw0 - lw * math.sqrt(1 + slope * slope)      # внутренняя полуширина у планки
    h_c = y_in - lw                                       # высота камеры
    hw_bot = hw_top - slope * h_c                         # внутренняя полуширина у перемычки

    def hw_at(dy):                                        # dy — от широкого конца камеры
        return hw_top - slope * dy

    # верхняя камера: воздух — от планки вниз на (1 − top) высоты
    ya = snap(-y_in + h_c * (1 - top))
    if ya > -y_in + 1e-6:
        d = ya + y_in
        poly(ctx, [(-hw_top, -y_in), (hw_top, -y_in), (hw_at(d), ya), (-hw_at(d), ya)])
        clear(ctx)
    # нижняя камера: воздух — от перемычки вниз до уровня песка
    yb = snap(y_in - h_c * bottom)
    if yb > lw + 1e-6:
        d = y_in - yb
        poly(ctx, [(-hw_bot, lw), (hw_bot, lw), (hw_at(d), yb), (-hw_at(d), yb)])
        clear(ctx)
        if stream and sp.detail >= 2 and bottom < 0.99:
            sw = sp.pxu(0.75)
            ctx.rectangle(-sw / 2, lw - 0.1, sw, yb - lw + 0.2)
            ctx.fill()
    ctx.restore()


def g_move_arrows(ctx, sp: Spec, ext=1.0):
    """Четыре гранёные стрелки от центра, бокс 18,5 u: древки W до ±5,25, наконечники 7 × 4, остриё на ±9,25;
    ступица-ромб 2 u при detail 2; detail 0 — крест ≥ 1 px с головками 3 u."""
    if sp.detail == 0:
        shaft, hb, hh, tip = max(sp.W, 1.0 / sp.k), 3.0, 3.0, 8.0
    else:
        shaft, hb, hh, tip = sp.W, 3.5, 4.0, 9.25
    for i in range(4):
        ctx.save()
        ctx.rotate(i * math.pi / 2)
        y_tip = -tip * ext
        y_base = y_tip + hh
        poly(ctx, [(-shaft / 2, 0.3), (-shaft / 2, y_base), (-hb, y_base), (0, y_tip), (hb, y_base), (shaft / 2, y_base),
                   (shaft / 2, 0.3)])
        ctx.fill()
        ctx.restore()
    if sp.detail >= 2:
        h = 2.0
        poly(ctx, [(0, -h), (h, 0), (0, h), (-h, 0)])
        ctx.fill()
    elif sp.detail == 0:
        ctx.rectangle(-shaft, -shaft, 2 * shaft, 2 * shaft)
        ctx.fill()


def ellipse(ctx, cx, cy, rx, ry):
    ctx.save()
    ctx.translate(cx, cy)
    ctx.scale(1.0, ry / rx)
    ctx.new_sub_path()
    ctx.arc(0, 0, rx, 0, 2 * math.pi)
    ctx.close_path()
    ctx.restore()


def g_place(ctx, sp: Spec, dy=0.0, part=None):
    """Выбор места: стрелка вниз на клетку поля — плоский эллипс (диск пространства в перспективе, как клетки DE на
    доске) с ободком-вырезом; зазор остриё/клетка 1,25 u. detail 0 — стрелка над сплошным эллипсом."""
    rx, ry, cyd = 7.0, 3.6, 5.6
    hw, hb, hh = (sp.W / 2, 3.75, 4.0) if sp.detail >= 1 else (max(sp.W, 1.0 / sp.k) / 2, 3.0, 3.0)
    gap = 1.25 if sp.detail >= 1 else 0.6
    tip = cyd - ry - gap
    if part in (None, "arrow"):
        ctx.save()
        ctx.translate(0, dy)
        poly(ctx, [(-hw, -9.6), (hw, -9.6), (hw, tip - hh), (hb, tip - hh), (0, tip), (-hb, tip - hh), (-hw, tip - hh)])
        ctx.fill()
        ctx.restore()
    if part == "arrow":
        return
    ellipse(ctx, 0, cyd, rx, ry)
    ctx.fill()
    ring = sp.pxu(1.0)
    rim = sp.pxu(1.25)
    if sp.detail >= 1 and (ry - rim - ring) * sp.k >= 1.2:
        ellipse(ctx, 0, cyd, rx - rim, ry - rim)
        clear(ctx)
        ellipse(ctx, 0, cyd, rx - rim - ring, ry - rim - ring)
        ctx.fill()


def g_bulb(ctx, sp: Spec):
    """Лампа подсказки 10,5 × 16,6 u одним путём (купол r 5,25 + прямые к горловине 5,5 u); цоколь — две планки
    5 × 1,4 с зазорами 1 px (detail 2), одна планка 1,75 (detail 1), слитый (detail 0). Кромки снэпнуты."""
    r, cy = 5.25, -3.25
    neck_hw = 2.75
    neck_y = sp.sy(3.25)
    g = sp.pxu(1.0)
    ctx.new_sub_path()
    ctx.arc(0, cy, r, math.radians(160), math.radians(380))
    ctx.line_to(neck_hw, neck_y)
    ctx.line_to(-neck_hw, neck_y)
    ctx.close_path()
    ctx.fill()
    if sp.detail >= 2:
        h = sp.pxu(1.4)
        y1 = sp.sy(neck_y + g)
        y2 = sp.sy(y1 + h + g)
        for y0 in (y1, y2):
            ctx.rectangle(-2.5, y0, 5.0, h)
            ctx.fill()
    elif sp.detail == 1:
        h = sp.pxu(1.75)
        ctx.rectangle(-2.5, sp.sy(neck_y + g), 5.0, h)
        ctx.fill()
    else:
        ctx.rectangle(-2.5, neck_y - 0.3, 5.0, 2.6)
        ctx.fill()


def g_eye(ctx, sp: Spec):
    """Глаз угрозы 16,5 × 9,5 u: миндалина = пересечение двух окружностей (острые уголки), зрачок — вырез r 2,5
    (detail ≥ 1 и ≥ 2,4 px)."""
    a, b = 8.25, 4.75
    R = (a * a + b * b) / (2 * b)
    o = R - b
    x = math.sqrt(R * R - o * o)
    ang = math.atan2(o, x)
    ctx.new_sub_path()
    ctx.arc(0, o, R, -math.pi + ang, -ang)          # верхняя дуга (центр ниже)
    ctx.arc(0, -o, R, ang, math.pi - ang)           # нижняя дуга (центр выше)
    ctx.close_path()
    ctx.fill()
    if sp.detail >= 1 and 2.5 * sp.k >= 1.2:
        circle(ctx, 0, 0, 2.5)
        clear(ctx)


def g_ticks(ctx, sp: Spec, step=0, keyline=True):
    """Спиннер: 8 радиальных брусков r 8..14, 6 печатных + 2 хвостовых приглушённых; keyline вокруг каждого."""
    n = 8
    if sp.detail == 0:
        for i in range(n):
            a = math.radians(-90 + i * 45)
            on = ((i - step) % n) < 6
            ctx.save()
            ctx.translate(11 * math.cos(a), 11 * math.sin(a))
            s = 1.0 / sp.k
            if keyline:
                ctx.rectangle(-s - sp.K, -s - sp.K, 2 * s + 2 * sp.K, 2 * s + 2 * sp.K)
                fill(ctx, C["keyline"])
            ctx.rectangle(-s, -s, 2 * s, 2 * s)
            fill(ctx, C["glyph"] if on else C["dim"])
            ctx.restore()
        return
    hw, r0, r1, c = sp.W / 2, 8.0, 14.0, 0.5
    for pass_ in ((0, 1) if keyline else (1,)):
        for i in range(n):
            on = ((i - step) % n) < 6
            ctx.save()
            ctx.rotate(math.radians(i * 45))
            pts = [(-hw, -r0), (hw, -r0), (hw, -r1 + c), (hw - c, -r1), (-hw + c, -r1), (-hw, -r1 + c)]
            if pass_ == 0:
                poly(ctx, _offset_poly(pts, -sp.K))
                fill(ctx, C["keyline"])
            else:
                poly(ctx, pts)
                fill(ctx, C["glyph"] if on else C["dim"])
            ctx.restore()


def g_card_stack(ctx, sp: Spec, keyline=True):
    """Стопка карт как в DE: три скошенные плашки 15 × 3 u (скос 3,5 u) с зазорами 1 px; keyline вокруг каждой держит
    зазоры на любом фоне; detail 0 — две плашки по 1 px."""
    n = 2 if sp.detail == 0 else 3
    h = sp.pxu(3.0) if sp.detail >= 1 else 1.0 / sp.k
    g = sp.pxu(1.0)
    w, skew = 15.0, 3.5
    total = n * h + (n - 1) * g
    y = sp.sy(-total / 2)
    slabs = []
    for i in range(n):
        y0 = y + i * (h + g)
        slabs.append([(-w / 2 + skew, y0), (w / 2, y0), (w / 2 - skew, y0 + h), (-w / 2, y0 + h)])
    if keyline:
        for s in slabs:
            poly(ctx, _offset_poly(s, -sp.K))
            fill(ctx, C["keyline"])
    for s in slabs:
        poly(ctx, s)
        fill(ctx, C["glyph"])


def _signal_bars(sp: Spec, shift=0.0):
    """Три столбика сигнала растущей высоты (6 / 11 / 16 u), ширина 3,5 u, зазор 1,75 u — всё со снэпом; низ на y = 8.
    shift — сдвиг вправо, когда слева сверху стоит знак (переподключение, потеря): знак не налезает на столбики."""
    bw, g = sp.pxu(3.5), sp.pxu(1.75)
    total = 3 * bw + 2 * g
    x0 = sp.sx(-total / 2 + shift)
    base = sp.sy(8.0)
    bars = []
    for i, hgt in enumerate((6.0, 11.0, 16.0)):
        top = sp.sy(base - hgt)
        bars.append((x0 + i * (bw + g), top, bw, base - top))
    return bars


SIGNAL_SIGN = (-7.25, -7.25)   # центр знака связи (= pivot слоя sign в icon-motion.json: 16 + x, 16 + y)
SIGNAL_BARS_SHIFT = 3.75      # сдвиг столбиков вправо при знаке (= tx «appear_from_online» в icon-motion.json)


def _arrow_arc_path(ctx, ra, lw, a0, a1, head_len=0.0, head_hw=0.0):
    """Круговая стрелка одним замкнутым контуром: полоса дуги ra ± lw/2 от a0 до a1 (рост угла) и наконечник —
    основание по нормали к дуге в конце (центр — конец дуги), остриё на касательной; без наконечника — срез по
    нормали. Один контур → keyline обводкой без ступенек на стыке (приёмка ART-011 О-2)."""
    ro, ri = ra + lw / 2, ra - lw / 2
    c1, s1 = math.cos(a1), math.sin(a1)
    ctx.new_sub_path()
    ctx.arc(0, 0, ro, a0, a1)
    if head_len > 0:
        tx, ty = -s1, c1                       # касательная по ходу дуги
        ctx.line_to((ra + head_hw) * c1, (ra + head_hw) * s1)
        ctx.line_to(ra * c1 + head_len * tx, ra * s1 + head_len * ty)
        ctx.line_to((ra - head_hw) * c1, (ra - head_hw) * s1)
    ctx.line_to(ri * c1, ri * s1)
    ctx.arc_negative(0, 0, ri, a1, a0)
    ctx.close_path()


def g_signal(ctx, sp: Spec, state="online", angle=0.0, keyline=True, part=None):
    """Связь: три столбика сигнала (online — card.glyph; reconnecting / lost — text.secondary) + знак слева сверху
    (центр SIGNAL_SIGN): круговая стрелка r 3,8 штрихом W2 с наконечником 3,6 × 3,8 u (reconnecting; при ≤ 24 px — дуга
    270° без головки) или красный X (lost). Keyline вокруг каждого штриха. Знак (с ореолом) отстоит от ореола
    столбиков (сдвиг SIGNAL_BARS_SHIFT) ≥ 1 u в мастере и ≥ 1 px при 24 px при любом угле поворота «cycle»."""
    bars = _signal_bars(sp, shift=0.0 if state == "online" else SIGNAL_BARS_SHIFT)
    col = C["glyph"] if state == "online" else C["dim"]
    if part == "sign":
        bars = []
    if keyline:
        for x, y, w, h in bars:
            ctx.rectangle(x - sp.K, y - sp.K, w + 2 * sp.K, h + 2 * sp.K)
            fill(ctx, C["keyline"])
    for x, y, w, h in bars:
        ctx.rectangle(x, y, w, h)
        fill(ctx, col)
    if state == "online" or part == "bars":
        return
    sx_, sy_ = SIGNAL_SIGN
    if state == "lost":
        ctx.save()
        ctx.translate(sx_, sy_)
        g_x(ctx, sp, half=3.25, w=sp.W, col=C["error"], keyline=keyline)
        ctx.restore()
        return
    ra = 3.8
    lw = sp.W2 if sp.detail >= 1 else max(sp.W2, 1.0 / sp.k)    # тонкий штрих: наконечник шире штриха вдвое
    ctx.save()
    ctx.translate(sx_, sy_)
    ctx.rotate(angle)
    # поза покоя «↻»: щель справа вверху, головка сверху смотрит вправо, в щель (вращение «cycle» — от этой позы).
    # Головка — только от 32 px: при ≤ 24 px знак ~7 px и головка читается крючком (приёмка ART-011 О-2) — дуга.
    if sp.size > 24:
        a0, a1, head = math.radians(-30), math.radians(255), (3.6, 1.9)
    else:
        a0, a1, head = math.radians(-15), math.radians(255), (0.0, 0.0)
    _arrow_arc_path(ctx, ra, lw, a0, a1, *head)
    if keyline:
        ctx.set_line_width(2 * sp.K)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        rgb(ctx, C["keyline"])
        ctx.stroke_preserve()
        ctx.fill_preserve()
    rgb(ctx, C["glyph"])
    ctx.fill()
    ctx.restore()


def g_x(ctx, sp: Spec, half=3.0, w=None, col=None, keyline=True):
    """X: два повёрнутых прямоугольника; keyline — те же прямоугольники, выращенные на K."""
    w = w or sp.W
    col = col or C["glyph"]
    L = half * math.sqrt(2)
    for pass_ in ((0, 1) if keyline else (1,)):
        g = sp.K if pass_ == 0 else 0
        for s in (1, -1):
            ctx.save()
            ctx.rotate(s * math.pi / 4)
            ctx.rectangle(-L - g, -w / 2 - g, 2 * L + 2 * g, w + 2 * g)
            fill(ctx, C["keyline"] if pass_ == 0 else col)
            ctx.restore()


def heart_path(ctx, cx, cy, r=5.5, lx=5.5, ly=-3.5, tip=10.0):
    """Сердце: доли — окружности r с центрами (±lx, ly), бока — касательные к острию (0, tip)."""
    px, py = 0.0, tip
    dx, dy = lx - px, ly - py
    d = math.hypot(dx, dy)
    a = math.atan2(dy, dx)
    b = math.asin(r / d)
    ang = a + b
    L = math.sqrt(d * d - r * r)
    tx, ty = px + L * math.cos(ang), py + L * math.sin(ang)
    a_t = math.atan2(ty - ly, tx - lx)
    valley_y = ly - math.sqrt(max(r * r - lx * lx, 0.0)) if lx < r else ly
    a_v = math.atan2(valley_y - ly, 0 - lx)
    ctx.new_sub_path()
    ctx.move_to(cx + 0, cy + tip)
    ctx.line_to(cx + tx, cy + ty)
    ctx.arc_negative(cx + lx, cy + ly, r, a_t, a_v)
    ctx.arc_negative(cx - lx, cy + ly, r, math.pi - a_v, math.pi - a_t)
    ctx.close_path()


def shrunk_mask(ctx, path_fn, d):
    """Маска: область внутри контура, сжатая на d — заливка контура минус штрих 2d в CLEAR (одна AA-кромка, без клипа)."""
    ctx.push_group()
    path_fn()
    ctx.set_source_rgba(0, 0, 0, 1)
    ctx.fill()
    if d > 0:
        path_fn()
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.set_line_width(2 * d)
        ctx.stroke()
        ctx.set_operator(cairo.OPERATOR_OVER)
    return ctx.pop_group()


def inset_fill(ctx, path_fn, d, col):
    """Заливка области контура, смещённой на d внутрь (d < 0 — наружу: заливка + штрих 2|d|, одной фигурой)."""
    if d <= 0:
        path_fn()
        rgb(ctx, col)
        if d < 0:
            ctx.set_line_width(-2 * d)
            ctx.stroke_preserve()
        ctx.fill()
    else:
        pat = shrunk_mask(ctx, path_fn, d)
        rgb(ctx, col)
        ctx.mask(pat)


def inset_clear(ctx, path_fn, d):
    ctx.save()
    ctx.set_operator(cairo.OPERATOR_CLEAR)
    if d > 0:
        ctx.mask(shrunk_mask(ctx, path_fn, d))
    else:
        path_fn()
        ctx.fill()
    ctx.restore()


def heart_token(ctx, sp: Spec, cx, cy, mode="light", scale=1.0):
    """Сердце-жетон от одного ядра: слои наружу (keyline, кромка) — заливка + штрих одной фигурой, слои внутрь — маска
    сжатого контура (без клипа → без шва по осевой, ревью G5). mode: light (своё) / dark (чужое) / hollow (пусто —
    контур text.secondary W (≥ 2 px) с keyline по обе стороны, И-10 в редакции ревью G3)."""
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    ctx.set_miter_limit(4)

    def core():
        heart_path(ctx, cx, cy, 5.5 * scale, 5.5 * scale, -3.5 * scale, 10.0 * scale)

    if mode == "hollow":
        wh = sp.pxu(2.25, mn=2)                  # полоса пустого сердца W, но ≥ 2 px: при 16 px иначе = чужое сердце (G3)
        inset_fill(ctx, core, -(sp.E + sp.K), C["keyline"])
        inset_fill(ctx, core, -sp.E, C["dim"])
        inner = max(wh - sp.E, 0.0)              # штрих заходит внутрь ядра на W − E
        inset_fill(ctx, core, inner, C["keyline"])
        inset_clear(ctx, core, inner + sp.K)
        return
    body = C["light"] if mode == "light" else C["body"]
    rim = sp.pxu(1.6)                         # красная кромка сердца как в DE (своё и чужое), шире обычной кромки
    inset_fill(ctx, core, -(rim + sp.K), C["keyline"])
    inset_fill(ctx, core, -rim, C["hp.rim"])
    inset_fill(ctx, core, 0, body)


# ------------------------------------------------------------------------------------------------ силуэты
def sq_sil(sp: Spec):
    return rect_sil(sp.M, sp.M, U - 2 * sp.M, U - 2 * sp.M, 1.5)


def disc_sil(sp: Spec):
    return Disc(U / 2, U / 2, U / 2 - sp.M)


def plate_sil(sp: Spec):
    return rect_sil(sp.M, sp.M, 2 * U - 2 * sp.M, U - 2 * sp.M, 2.25)


def ribbon_sil(sp: Spec, w=20.6, notch=0.28):
    x0, x1 = U / 2 - w / 2, U / 2 + w / 2
    y0, y1 = sp.M, U - sp.M
    return Poly([(x0, y0), (x1, y0), (x1, y1), (U / 2, y1 - notch * w), (x0, y1)], [0.75, 0.75, 0.4, 0.0, 0.4])


def rhombus_sil(sp: Spec, h=10.0):
    c = U / 2
    return Poly([(c, c - h), (c + h, c), (c, c + h), (c - h, c)], [0.5, 0.5, 0.5, 0.5])


def glyph(ctx, sp: Spec, cx, cy, fn, col=None):
    """Глиф в группе: цвет печати, перенос в центр бокса (без масштаба); sp.ox/oy — начало для снэпа в абсолютных u;
    вырезы внутри группы не пробивают тело."""
    sp.ox, sp.oy = cx, cy
    ctx.push_group()
    ctx.save()
    ctx.translate(cx, cy)
    rgb(ctx, col or C["glyph"])
    fn()
    ctx.restore()
    ctx.pop_group_to_source()
    ctx.paint()


# ------------------------------------------------------------------------------------------------ значки
def draw_state_boost(ctx, sp: Spec, text=None):
    """Диск BOOST как на карте: navy, тонкое белое кольцо у края, без крема; keyline снаружи."""
    R = U / 2 - sp.M
    circle(ctx, U / 2, U / 2, R)
    fill(ctx, C["keyline"])
    circle(ctx, U / 2, U / 2, R - sp.K)
    fill(ctx, C["body"])
    gap = sp.pxu(1.0)
    circle(ctx, U / 2, U / 2, R - sp.K - gap)
    fill(ctx, C["glyph"])
    circle(ctx, U / 2, U / 2, R - sp.K - gap - sp.ring)
    fill(ctx, C["body"])
    if text:
        text_path(ctx, text, 11.0 if len(text) <= 2 else 9.0, U / 2, U / 2, tracking=-0.2)
        fill(ctx, C["glyph"])


def _state(ctx, sp: Spec, fn, body=None, cy=16.0, layer=None, **kw):
    """Плашка состояния: бокс глифа 18–19 u по центру (ревью G1), без масштабирования контекста."""
    if layer in (None, "body"):
        token(ctx, sq_sil(sp), sp, body=body)
    if layer in (None, "glyph"):
        glyph(ctx, sp, 16.0, cy, lambda: fn(ctx, sp, **kw))


def draw_state_enemy(ctx, sp: Spec, layer=None):
    _state(ctx, sp, g_pawn, layer=layer)


def draw_state_sent(ctx, sp: Spec, top=0.55, bottom=0.45, angle=0.0, stream=False, layer=None):
    if sp.detail == 0:
        top, bottom, stream = 1.0, 1.0, False
    _state(ctx, sp, g_hourglass, layer=layer, top=top, bottom=bottom, angle=angle, stream=stream)


def draw_state_pending_move(ctx, sp: Spec, ext=1.0, layer=None):
    _state(ctx, sp, g_move_arrows, body=C["pending"], layer=layer, ext=ext)


def draw_state_pending_place(ctx, sp: Spec, dy=0.0, layer=None):
    if layer in ("space", "arrow"):
        glyph(ctx, sp, 16.0, 16.0, lambda: g_place(ctx, sp, dy=dy, part=layer))
        return
    _state(ctx, sp, g_place, body=C["pending"], layer=layer, dy=dy)


def draw_state_immobilized(ctx, sp: Spec, layer=None):
    _state(ctx, sp, g_anchor, layer=layer)


def _plate(ctx, sp: Spec, fn, text=None, layer=None, cy=16.0, **kw):
    """Плашка 2 : 1: слот глифа слева (квадрат во всю внутреннюю высоту), линейка, поле числа справа."""
    bi = sp.body_in
    inner = U - 2 * bi
    if layer in (None, "body"):
        token(ctx, plate_sil(sp), sp)
        rx = sp.snap(bi + inner + 1.5)
        rh = sp.snap(0.54 * inner)
        ctx.rectangle(rx, U / 2 - rh / 2, sp.rule, rh)
        fill(ctx, C["edge"])
    if layer in (None, "glyph"):
        glyph(ctx, sp, bi + inner / 2, cy, lambda: fn(ctx, sp, **kw))
    if text:
        x0 = bi + inner + 1.5 + sp.rule + 1.25
        x1 = 2 * U - bi
        text_path(ctx, text, 0.55 * inner, (x0 + x1) / 2, U / 2)
        fill(ctx, C["glyph"])


def draw_state_hint(ctx, sp: Spec, text=None, layer=None):
    _plate(ctx, sp, g_bulb, text=text, layer=layer, cy=16.25)


def draw_state_threat(ctx, sp: Spec, text=None, layer=None):
    _plate(ctx, sp, g_eye, text=text, layer=layer)


def _action(ctx, sp: Spec, fn, body, col=None, cy=16.0, layer=None, **kw):
    """Пипс действия как в DE: цветной диск, кремовое кольцо, keyline; глиф белый (хитрость — navy).
    layer: body — диск с кольцом; glyph — только глиф (для движения по частям)."""
    if layer in (None, "body"):
        token(ctx, disc_sil(sp), sp, body=body)
    if layer in (None, "glyph"):
        glyph(ctx, sp, 16.0, cy, lambda: fn(ctx, sp, **kw), col=col)


def draw_action_attack(ctx, sp: Spec, layer=None):
    _action(ctx, sp, g_burst, C["attack"], layer=layer, R=9.0)


def draw_action_defense(ctx, sp: Spec, layer=None):
    _action(ctx, sp, g_shield, C["defense"], cy=16.0, layer=layer, w=11.0, h=13.0)


def draw_action_maneuver(ctx, sp: Spec, layer=None):
    _action(ctx, sp, g_boots, C["maneuver"], layer=layer)


def draw_action_scheme(ctx, sp: Spec, layer=None):
    _action(ctx, sp, g_bolt, C["scheme"], col=C["body"], cy=15.75, layer=layer, s=1.0)


def draw_action_attack_token(ctx, sp: Spec, mask=False):
    """Жетон цели D-5: тело icon.token.body, ободок icon.token.rim 0,5 u, без keyline; звезда R 9."""
    R = U / 2 - sp.M
    if not mask:
        circle(ctx, U / 2, U / 2, R)
        fill(ctx, C["token.rim"])
        circle(ctx, U / 2, U / 2, R - sp.rim)
        fill(ctx, C["token.body"])
    glyph(ctx, sp, 16.0, 16.0, lambda: g_burst(ctx, sp, R=9.0), col=C["white"] if mask else None)


def draw_marker_status(ctx, sp: Spec, team=None, text=None, layer=None):
    """Лента порядка хода: верхний блок 0,42 w (в мастере белый — игра красит), тело navy, вырез снизу."""
    sil = ribbon_sil(sp)
    w = 20.6
    block_h = 0.42 * w
    if layer in (None, "body"):
        token(ctx, sil, sp)
    if layer in (None, "team"):
        ctx.save()
        sil.path(ctx, sp.KE)
        ctx.clip()
        ctx.rectangle(0, 0, U, sp.M + sp.KE + block_h)
        fill(ctx, C["white"] if layer == "team" else (team or C["white"]))
        ctx.restore()
    if text:
        y_top = sp.M + sp.KE + block_h
        y_bot = (U - sp.M) - 0.28 * w
        cap = 9.0 if len(text) == 1 else 8.0
        text_path(ctx, text, cap, U / 2, (y_top + y_bot) / 2 - 0.3, tracking=-0.15 if len(text) > 1 else 0)
        fill(ctx, C["glyph"])


def draw_loader_spinner(ctx, sp: Spec, step=0):
    glyph(ctx, sp, 16.0, 16.0, lambda: g_ticks(ctx, sp, step=step))


def draw_resource_action(ctx, sp: Spec, full=True):
    """Очко действия: ромб. Есть — светлый жетон (тело card.glyph, кромка navy); потрачено — пустой контур
    text.secondary (одно правило «пусто» с сердцем)."""
    sil = rhombus_sil(sp)
    if full:
        token(ctx, sil, sp, body=C["light"], edge=C["body"])
    else:
        hollow_token(ctx, sil, sp, edge=C["dim"])


def draw_resource_card(ctx, sp: Spec):
    glyph(ctx, sp, 16.0, 16.0, lambda: g_card_stack(ctx, sp))


def draw_resource_connection(ctx, sp: Spec, state="online", angle=0.0, layer=None):
    glyph(ctx, sp, 16.0, 16.0, lambda: g_signal(ctx, sp, state=state, angle=angle, part=layer))


def draw_resource_hp(ctx, sp: Spec, mode="light", text=None):
    """Здоровье: своё — светлое сердце (DE), чужое — тёмное, потрачено — пустой контур text.secondary."""
    heart_token(ctx, sp, 16.0, 16.9, mode=mode, scale=1.0)
    if text:
        text_path(ctx, text, 9.0 if len(text) <= 1 else 8.0, 16.0, 15.6, tracking=-0.2)
        fill(ctx, C["body"] if mode == "light" else C["glyph"])


# id → (функция, kwargs, широкий?)
ICONS = {
    "state-boost": (draw_state_boost, {}, False),
    "state-enemy": (draw_state_enemy, {}, False),
    "state-sent": (draw_state_sent, {}, False),
    "state-pending-move": (draw_state_pending_move, {}, False),
    "state-pending-place": (draw_state_pending_place, {}, False),
    "state-hint": (draw_state_hint, {}, True),
    "state-threat": (draw_state_threat, {}, True),
    "state-immobilized": (draw_state_immobilized, {}, False),
    "action-attack": (draw_action_attack, {}, False),
    "action-attack-token": (draw_action_attack_token, {}, False),
    "action-attack-token-glyphmask": (draw_action_attack_token, {"mask": True}, False),
    "action-defense": (draw_action_defense, {}, False),
    "action-maneuver": (draw_action_maneuver, {}, False),
    "action-scheme": (draw_action_scheme, {}, False),
    "marker-status": (draw_marker_status, {}, False),
    "loader-spinner": (draw_loader_spinner, {}, False),
    "resource-action-full": (draw_resource_action, {"full": True}, False),
    "resource-action-empty": (draw_resource_action, {"full": False}, False),
    "resource-card": (draw_resource_card, {}, False),
    "resource-connection-online": (draw_resource_connection, {"state": "online"}, False),
    "resource-connection-reconnecting": (draw_resource_connection, {"state": "reconnecting"}, False),
    "resource-connection-lost": (draw_resource_connection, {"state": "lost"}, False),
    "resource-hp-full": (draw_resource_hp, {"mode": "light"}, False),
    "resource-hp-empty": (draw_resource_hp, {"mode": "hollow"}, False),
}
# варианты того же id (суффикс), новых id нет
VARIANTS = {
    "resource-hp-full-enemy": (draw_resource_hp, {"mode": "dark"}, False),
    "marker-status-p1": (draw_marker_status, {"team": C["team1"]}, False),
    "marker-status-p2": (draw_marker_status, {"team": C["team2"]}, False),
}
LAYERS = {
    "action-attack": ("body", "glyph"),
    "action-defense": ("body", "glyph"),
    "action-maneuver": ("body", "glyph"),
    "action-scheme": ("body", "glyph"),
    "resource-connection-reconnecting": ("bars", "sign"),
    "resource-connection-lost": ("bars", "sign"),
    "marker-status": ("body", "team"),
    "state-sent": ("body", "glyph"),
    "state-pending-move": ("body", "glyph"),
    "state-pending-place": ("body", "space", "arrow"),
    "state-enemy": ("body", "glyph"),
    "state-immobilized": ("body", "glyph"),
    "state-hint": ("body", "glyph"),
    "state-threat": ("body", "glyph"),
}
# Флипбуки слоёв для движения (контракт icon-motion.json: src «<id>_<layer>#» → файлы <id>_<layer>_fNN):
# песок часов state-sent — 12 кадров цикла 1500 мс (кадры 0–6 пересыпание за 550 мс, 7–11 после переворота).
def _sent_frames():
    out = []
    for i in range(7):                                   # 0, 92, … 550 мс: верх 0,55 → 0, низ 0,45 → 1
        k = i / 6
        out.append({"top": 0.55 * (1 - k), "bottom": 0.45 + 0.55 * k, "stream": 0 < i < 6})
    for j in range(5):                                   # 950, 1040, … 1310 мс: верх 1 → 0,55+, низ 0 → 0,45−
        k = j / 5
        out.append({"top": 1.0 - 0.45 * k, "bottom": 0.45 * k, "stream": True})
    return out


FLIPBOOKS = {("state-sent", "glyph"): _sent_frames()}
ALL = list(ICONS) + list(VARIANTS)
ORDER23 = [k for k in ICONS if k != "action-attack-token-glyphmask"]
EXAMPLE = {"state-boost": {"text": "+2"}, "state-hint": {"text": "1"}, "state-threat": {"text": "3"},
           "marker-status": {"text": "1", "team": C["team1"]}, "marker-status-p1": {"text": "1"},
           "marker-status-p2": {"text": "2"}, "resource-hp-full": {"text": "17"}, "resource-hp-full-enemy": {"text": "16"}}


def is_wide(name):
    return (ICONS.get(name) or VARIANTS.get(name))[2]


# ------------------------------------------------------------------------------------------------ рендер
def surface(w, h):
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    ctx = cairo.Context(surf)
    ctx.set_antialias(cairo.ANTIALIAS_BEST)
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    return surf, ctx


def to_pil(surf) -> Image.Image:
    """ARGB32 premultiplied → прямой RGBA (делим RGB на α — иначе тёмный ореол)."""
    surf.flush()
    w, h, stride = surf.get_width(), surf.get_height(), surf.get_stride()
    buf = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(h, stride)[:, : w * 4].reshape(h, w, 4)
    b, g, r, a = [buf[..., i].astype(np.float32) for i in range(4)]
    af = np.where(a > 0, a, 1.0)
    out = np.stack([np.clip(r * 255 / af + 0.5, 0, 255), np.clip(g * 255 / af + 0.5, 0, 255),
                    np.clip(b * 255 / af + 0.5, 0, 255), a], axis=-1)
    # Alpha bleed: прозрачные пиксели получают цвет ближайшего непрозрачного (альфа не меняется). Текстура UE с прямой
    # альфой при билинейной выборке (анимация: поворот, масштаб, субпиксельный сдвиг) иначе тянет чёрный в край
    # белого глифа — тёмный ореол.
    empty = a == 0
    if empty.any() and (~empty).any():
        from scipy import ndimage
        _, (iy, ix) = ndimage.distance_transform_edt(empty, return_indices=True)
        out[..., :3] = out[iy, ix, :3]
    return Image.fromarray(out.astype(np.uint8), "RGBA")


def render(name: str, size: int, **kw) -> Image.Image:
    fn, base_kw, wide = ICONS.get(name) or VARIANTS[name]
    sp = Spec(size)
    surf, ctx = surface(2 * size if wide else size, size)
    ctx.scale(sp.k, sp.k)
    args = dict(base_kw)
    args.update(kw)
    fn(ctx, sp, **args)
    return to_pil(surf)


def render_example(name, size):
    """Образец для листов; при detail 0 (≤ 20 px) число не рисуется (STYLE-v3 §3.2) — и на листе тоже (ART-011 Д-4)."""
    kw = dict(EXAMPLE.get(name, {}))
    if Spec(size).detail == 0:
        kw.pop("text", None)
    return render(name, size, **kw)


# ------------------------------------------------------------------------------------------------ самопроверка
def _rgb255(hexv):
    return np.array([int(hexv[i:i + 2], 16) for i in (1, 3, 5)])


GLYPH_RGB = _rgb255(TOKENS["card.glyph"])
KEYLINE_RGB = _rgb255(TOKENS["mark.keyline"])
EDGE_RGB = _rgb255(TOKENS["card.cream"])
PALETTE = np.array([_rgb255(v) for v in TOKENS.values()] + [[255, 255, 255]])


def audit(name, im: Image.Image, size=MASTER):
    a = np.asarray(im)
    alpha = a[..., 3]
    h, w = alpha.shape
    ys, xs = np.where(alpha > 0)
    res = {"size": [w, h]}
    if len(xs) == 0:
        res["error"] = "empty"
        return res
    res["margin_px"] = [int(xs.min()), int(ys.min()), int(w - 1 - xs.max()), int(h - 1 - ys.max())]
    aw = alpha.astype(np.float64)
    res["alpha_centroid_u"] = [round((aw.sum(0) * np.arange(w)).sum() / aw.sum() / size * U, 2),
                               round((aw.sum(1) * np.arange(h)).sum() / aw.sum() / size * U, 2)]
    frame = np.zeros_like(alpha, dtype=bool)
    frame[:2, :] = frame[-2:, :] = frame[:, :2] = frame[:, -2:] = True
    res["dust_alpha_1_6_on_frame"] = int(((alpha >= 1) & (alpha <= 6) & frame).sum())
    res["alpha_1_6_total"] = int(((alpha >= 1) & (alpha <= 6)).sum())
    # симметрия лево/право (альфа и RGB)
    flipped = a[:, ::-1, :]
    res["lr_symmetry_mean_abs"] = float(np.abs(a.astype(int) - flipped.astype(int)).mean())
    # масса глифа: пиксели цвета card.glyph (или белые) среди непрозрачных; и от внутреннего тела (без keyline/кромки)
    rgbv = a[..., :3].astype(int)
    opaque = alpha > 128
    glyph = opaque & (np.abs(rgbv - GLYPH_RGB).sum(-1) < 24)
    rim = opaque & ((np.abs(rgbv - KEYLINE_RGB).sum(-1) < 24) | (np.abs(rgbv - EDGE_RGB).sum(-1) < 24))
    if glyph.sum():
        gy, gx = np.where(glyph)
        res["glyph_area_pct_of_opaque"] = round(100.0 * glyph.sum() / max(opaque.sum(), 1), 1)
        res["glyph_area_pct_of_body"] = round(100.0 * glyph.sum() / max((opaque & ~rim).sum(), 1), 1)
        res["glyph_centroid_u"] = [round(gx.mean() / size * U, 2), round(gy.mean() / size * U, 2)]
        res["glyph_bbox_u"] = [round(gx.min() / size * U, 2), round(gy.min() / size * U, 2),
                               round((gx.max() + 1) / size * U, 2), round((gy.max() + 1) / size * U, 2)]
    # швы (ревью G5): непрозрачный пиксель-смесь (не цвет палитры), у которого оба соседа по вертикали или по
    # горизонтали — один и тот же цвет палитры; на кромках AA таких нет, внутри заливки — это шов
    full = alpha >= 250
    d = np.abs(rgbv[..., None, :] - PALETTE[None, None, :, :]).max(-1)       # h, w, n
    idx = d.argmin(-1)
    blend = full & (d.min(-1) > 12)
    plain = full & ~blend
    sv = blend[1:-1, :] & plain[:-2, :] & plain[2:, :] & (idx[:-2, :] == idx[2:, :])
    sh = blend[:, 1:-1] & plain[:, :-2] & plain[:, 2:] & (idx[:, :-2] == idx[:, 2:])
    res["seam_px"] = int(sv.sum() + sh.sum())
    return res


def sha1(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


# ------------------------------------------------------------------------------------------------ листы
PANEL = tuple(int(c * 255) for c in C["panel"]) + (255,)
CREAM = tuple(int(c * 255) for c in C["edge"]) + (255,)
SHEET_BG = (30, 32, 40, 255)


def label(w, h, text, size=14, bg=SHEET_BG, fg=(0.92, 0.90, 0.86), align="left"):
    surf, ctx = surface(w, h)
    rgb(ctx, tuple(c / 255 for c in bg[:3]))
    ctx.paint()
    text_path(ctx, text, size * 0.71, 6 if align == "left" else w / 2, h / 2, font=FONT_RG, align=align)
    fill(ctx, fg)
    return to_pil(surf)


def grey(im):
    g = im.convert("L")
    return Image.merge("RGBA", (g, g, g, im.getchannel("A")))


def xN(im, n):
    return im.resize((im.width * n, im.height * n), Image.NEAREST)


def paste(bg, im, x, y):
    bg.alpha_composite(im, (int(x), int(y)))


def on_bg(im, bg, pad=4):
    base = Image.new("RGBA", (im.width + 2 * pad, im.height + 2 * pad), bg)
    paste(base, im, pad, pad)
    return base


def sheet_masters(names, path):
    cell, pad = 232, 20
    cols = 6
    rows = (len(names) + cols - 1) // cols
    W = cols * (2 * cell + pad) + pad
    H = 56 + rows * (cell + 40 + pad)
    sheet = Image.new("RGBA", (W, H), SHEET_BG)
    paste(sheet, label(W, 40, "v3 «Жетон-эмблема» на основе Digital Edition — мастера 1024 (плашки 2048×1024) при 232 px на панели tag.background; цифры — пример runtime-текста", 17), 0, 8)
    for i, n in enumerate(names):
        im = render_example(n, 1024)
        im = im.resize((int(im.width * cell / im.height), cell), Image.LANCZOS)
        x = pad + (i % cols) * (2 * cell + pad)
        y = 56 + (i // cols) * (cell + 40 + pad)
        panel = Image.new("RGBA", (2 * cell, cell + 8), PANEL)
        paste(panel, im, 4, 4)
        paste(sheet, panel, x, y)
        paste(sheet, label(2 * cell, 26, n, 14), x, y + cell + 10)
    sheet.convert("RGB").save(path)
    return path


def sheet_sizes(names, path):
    """48/32/24/16 цвет | серый | ×8 для 24 и 16 (цвет, серый)."""
    row_h = 24 * 8 + 24
    name_w = 230
    sizes_w = sum((2 * s if True else s) + 10 for s in SHEET_SIZES) + 30
    x8_w = 24 * 2 * 8 + 16 * 2 * 8 + 40
    W = name_w + 2 * sizes_w + 2 * x8_w + 80
    H = 60 + len(names) * row_h
    sheet = Image.new("RGBA", (W, H), SHEET_BG)
    paste(sheet, label(W, 40, "размеры 48 / 32 / 24 / 16 px из вектора: цвет | серый | ×8 nearest 24 и 16 цвет | ×8 серый — на панели tag.background", 17), 0, 8)
    for r, n in enumerate(names):
        y = 60 + r * row_h
        paste(sheet, label(name_w, 26, n, 14), 0, y + 8)
        x = name_w
        for mode in ("colour", "grey"):
            for s in SHEET_SIZES:
                im = on_bg(render_example(n, s), PANEL, 4)
                if mode == "grey":
                    im = grey(im)
                paste(sheet, im, x, y + 8)
                x += im.width + 10
            x += 30
        for mode in ("colour", "grey"):
            for s in (24, 16):
                im = on_bg(render_example(n, s), PANEL, 2)
                big = xN(grey(im) if mode == "grey" else im, 8)
                paste(sheet, big, x, y + 8)
                x += big.width + 10
            x += 20
    sheet.convert("RGB").save(path)
    return path


def strip(names, size, bg_img, gap=12):
    x = gap
    for n in names:
        im = render_example(n, size)
        paste(bg_img, im, x, (bg_img.height - im.height) // 2)
        x += im.width + gap
    return bg_img


def strip_width(names, size, gap=12):
    return sum((2 * size if is_wide(n) else size) + gap for n in names) + gap


def sheet_context_panel(names, path):
    """Контекст: HUD-панель tag.background и кремовый фон при 32 и 24 px, цвет и серый."""
    rows = []
    for size in (32, 24):
        w = strip_width(names, size)
        for title, col in (("HUD-панель tag.background", PANEL), ("кремовый фон card.cream", CREAM)):
            s = strip(names, size, Image.new("RGBA", (w, size + 24), col))
            rows.append((f"{size} px · {title}", s))
            rows.append((f"{size} px · {title} · серый", grey(s)))
    W = max(r[1].width for r in rows) + 20
    H = 50 + sum(r[1].height + 26 for r in rows)
    sheet = Image.new("RGBA", (W, H), SHEET_BG)
    paste(sheet, label(W, 40, "контекст: панель и крем (ресурсные жетоны «есть/пусто» — только для тёмных панелей)", 17), 0, 6)
    y = 50
    for title, s in rows:
        paste(sheet, label(W, 22, title, 13), 0, y)
        paste(sheet, s, 10, y + 22)
        y += s.height + 26
    sheet.convert("RGB").save(path)
    return path


# ------------------------------------------------------------------------------------------------ сборка
def build(names=None, review_dir=None):
    names = names or ALL
    dirs = {d: os.path.join(ROOT, d) for d in ("masters", "sizes", "layers", "sheets")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    manifest = {"revision": "hud-icons-v3", "unit_px": MASTER // U, "sizes": list(SIZES), "files": {}}
    audits = {}
    for n in names:
        im = render(n, MASTER)
        p = os.path.join(dirs["masters"], f"{n}.png")
        im.save(p)
        audits[n] = audit(n, im)
        for s in SIZES:
            render(n, s).save(os.path.join(dirs["sizes"], f"{n}-{s}.png"))
        for layer in LAYERS.get(n, ()):
            render(n, MASTER, layer=layer).save(os.path.join(dirs["layers"], f"{n}_{layer}.png"))
            for s in SIZES:
                render(n, s, layer=layer).save(os.path.join(dirs["layers"], f"{n}_{layer}-{s}.png"))
            for fi, kw in enumerate(FLIPBOOKS.get((n, layer), ())):
                render(n, MASTER, layer=layer, **kw).save(os.path.join(dirs["layers"], f"{n}_{layer}_f{fi:02d}.png"))
                for s in SIZES:
                    render(n, s, layer=layer, **kw).save(os.path.join(dirs["layers"], f"{n}_{layer}_f{fi:02d}-{s}.png"))
        print("ok", n, im.size, audits[n].get("margin_px"), "body%", audits[n].get("glyph_area_pct_of_body"), "seam", audits[n].get("seam_px"))
    show = [n for n in ORDER23 if n in names] + [n for n in ("action-attack-token-glyphmask",) + tuple(VARIANTS) if n in names]
    sheet_masters(show, os.path.join(dirs["sheets"], "sheet-masters.png"))
    sheet_sizes(show, os.path.join(dirs["sheets"], "sheet-sizes.png"))
    sheet_context_panel([n for n in ORDER23 if n in names] + [v for v in ("resource-hp-full-enemy",) if v in names],
                        os.path.join(dirs["sheets"], "sheet-context-panel.png"))
    with open(os.path.join(dirs["sheets"], "audit.json"), "w", encoding="utf-8") as f:
        json.dump(audits, f, ensure_ascii=False, indent=1)
    for d in ("masters", "sizes", "layers"):
        for fn in sorted(os.listdir(dirs[d])):
            if fn.endswith(".png"):
                manifest["files"][f"{d}/{fn}"] = sha1(os.path.join(dirs[d], fn))
    with open(os.path.join(ROOT, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    if review_dir:
        import review_sheets
        review_sheets.build(review_dir, [n for n in ORDER23 if n in names])
    print("built", len(names), "icons ->", ROOT)


if __name__ == "__main__":
    args = sys.argv[1:]
    only = None
    review = None
    if "--only" in args:
        only = args[args.index("--only") + 1].split(",")
    if "--review" in args:
        review = args[args.index("--review") + 1]
    build(only, review)
