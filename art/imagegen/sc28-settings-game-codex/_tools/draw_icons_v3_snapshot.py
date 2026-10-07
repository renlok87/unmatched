#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""HUD icons v3 «Жетон-эмблема» на основе Unmatched: Digital Edition — один векторный движок (pycairo).

    python draw_icons.py                 # пересобирает всё: masters/, sizes/, layers/, sheets/, manifest.json, audit.json
    python draw_icons.py --review DIR    # дополнительно листы со сканами карт и кадрами DE в DIR (вне репозитория)
    python draw_icons.py --only state-boost,action-attack   # подмножество (для отладки)
    python draw_icons.py --sheet accept state-boost,action-attack DIR   # IC-33: лист приёмки (цвет / серый Rec.709 /
                                         # дейтеранопия на card.navy, card.cream, #808080; мастер и 18/24/32/48 ×4)

Единицы: холст 32 u × 32 u (плашки 64 × 32 u), мастер 1024 px → 1 u = 32 px. Каждый размер рендерится из вектора:
толщины слоёв (keyline K, кромка E, штрих W, кольцо) снэпятся к целым пикселям, прямые границы тел ложатся на пиксель,
размеры SIZES — набор экспортов под масштаб UI и DPI (18 / 36 / 72 — IC-33), без mip и без даунскейла мастера,
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
# IC-33 (ВР-62, ВР-IC14; 02 §3.2, §5.3): набор экспортов под масштаб вместо mip — 18 и 36 = значок 24 su при DPI 0,75
# (720p) и при 150 %, 72 = значок 48 su при 150 %. Прежние размеры и их PNG побайтно те же, новые — только новые файлы.
SIZES = (16, 18, 21, 24, 32, 36, 48, 64, 72, 96)
# Размеры сверх SIZES у отдельных id (ВР-78): чип команды в HUD — 24 su, экспорты 9 и 12 px только для листа проверки.
EXTRA_SIZES = {"team-chip-p1": (9, 12), "team-chip-p2": (9, 12)}
SHEET_SIZES = (48, 32, 24, 16)
# Лист приёмки --sheet accept (02 §13.2): рабочие размеры, ×4 nearest; бейджи слоя L6 (clamp 16…32 px, HUD-AND-ICONS
# §1.7) ещё 16 и 21.
ACCEPT_SIZES = (18, 24, 32, 48)
ACCEPT_L6_SIZES = (16, 21)
L6_BADGES = ("state-boost", "state-enemy", "state-hint", "state-threat", "marker-status", "marker-status-p1",
             "marker-status-p2", "badge-order", "badge-order-p2", "badge-refuse", "badge-conflict")
# VS-2 A2: свои размеры листа приёмки — чипы команд ещё 9 и 12 (EXTRA_SIZES, ВР-78), курсоры — 24 / 32 / 48 / 64
ACCEPT_OWN = {"team-chip-p1": (9, 12, 18, 24, 32, 48), "team-chip-p2": (9, 12, 18, 24, 32, 48),
              "cursor-default": (24, 32, 48, 64), "cursor-unavailable": (24, 32, 48, 64), "cursor-busy": (24, 32, 48, 64),
              "cursor-pointer": (24, 32, 48, 64)}

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
    # набор DE-012 (STYLE-v3.md §11, принят пользователем 2026-10-05): тёплые тона вспышки кольца хода
    "turn.flash.yellow": "#F2C14E", "turn.flash.orange": "#E8812C",
    # IC-33 для строк VR44 (значения — hud-style-tokens.json, 02 §2.4 ВР-66 и §2.6 ВР-67; сверку держит pytest
    # test_draw_icons_new_roles_match_style_tokens): state.warning — алиас turn.flash.orange
    "state.warning": "#E8812C", "fx.heal": "#8CE69A",
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
    # набор DE-012 (STYLE-v3.md §11)
    "ring.yellow": "turn.flash.yellow",   # вспышка кольца хода: жёлтый → оранжевый → красный (01 F-07)
    "ring.orange": "turn.flash.orange",   # тлеющее кольцо хода; кольцо текущего слота трекера (вариант DE)
    "ring.red": "card.type.attack",       # конец вспышки — красный игры, не state.error (правило ДНК 7)
    "hp.glow": "card.type.attack",        # ореол сердца при уроне: плоская полоса за keyline, без градиента
    # IC-33 (ВР-IC03): роли значков VR44
    "warning": "state.warning",           # знак «!» предупреждения (ВР-66: алиас turn.flash.orange)
    "heal": "fx.heal",                    # «+» лечения (ВР-67)
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


HEART_C = (16.0, 16.9)   # центр ядра сердца resource-hp-* (heart_path: доли (±5,5; −3,5), остриё +10)


def draw_resource_hp(ctx, sp: Spec, mode="light", text=None, layer=None):
    """Здоровье: своё — светлое сердце (DE), чужое — тёмное, потрачено — пустой контур text.secondary.
    layer glow — DE-012 (AB-6, принят 2026-10-05): ореол урона под сердцем (слой glow в icon-motion.json, покой 0)."""
    if layer == "glow":
        heart_glow(ctx, sp, *HEART_C)
        return
    heart_token(ctx, sp, *HEART_C, mode=mode, scale=1.0)
    if text:
        text_path(ctx, text, 9.0 if len(text) <= 1 else 8.0, 16.0, 15.6, tracking=-0.2)
        fill(ctx, C["body"] if mode == "light" else C["glyph"])


# ------------------------------------------------------------------------------------------------ набор DE-012
# W-15 арт (DE-012; ICON-MOTION.md, раздел DE; STYLE-v3.md §11). Арт-приёмка пользователя 2026-10-05 (01-decisions,
# «Лист A/B DE-028 — ответ пользователя»: AB-5 тёплое кольцо, AB-7 трекер DE, AB-8 да, форма Codex): кольцо хода — форма
# v3 как есть; павшее сердце, штамп и слот DE — формы Codex (art/imagegen/hud-icons-de012-codex/, draw_icons_codex.py).
# Кандидатом остаётся только кольцо цвета команды (AB-5 выбрал тёплое): галерея -S08IconGallery и лист sheets/de012/.
RING_BAND = 2.5           # полоса тлеющего обода; окно портрета ⌀ 21 u в поле 32 u (мастер: 15 − 1 − 2,5 − 1)
RING_FLASH_GROW = 0.75    # вспышка шире тлеющего обода внутрь на 0,75 u — «обод целиком вспыхнул»
RING_FLASH_FRAMES = 7     # флипбук вспышки: жёлтый (f00) → оранжевый (f03) → красный (f06) за 1000 мс


def ring_flash_colour(frame, frames=RING_FLASH_FRAMES):
    """Цвет кадра вспышки: линейно в sRGB жёлтый → оранжевый (первая половина), оранжевый → красный (вторая)."""
    k = frame / max(frames - 1, 1)
    a, b, f = (C["ring.yellow"], C["ring.orange"], k * 2) if k <= 0.5 else (C["ring.orange"], C["ring.red"], k * 2 - 1)
    return tuple(a[i] + (b[i] - a[i]) * f for i in range(3))


def _annulus(ctx, sp: Spec, r_out, r_in, col):
    """Обод-высечка: keyline снаружи и внутри, полоса цвета между ними, окно прозрачное (одна заливка + вырез)."""
    circle(ctx, U / 2, U / 2, r_out)
    fill(ctx, C["keyline"])
    circle(ctx, U / 2, U / 2, r_out - sp.K)
    fill(ctx, col)
    circle(ctx, U / 2, U / 2, r_in + sp.K)
    fill(ctx, C["keyline"])
    circle(ctx, U / 2, U / 2, r_in)
    clear(ctx)


def draw_marker_turn_ring(ctx, sp: Spec, layer=None, frame=0, team=False):
    """Кольцо хода у портрета (SD-34, 01 F-07): обод целиком. rim — тлеющий обод (оранжевый; у варианта team — белый,
    игра умножает на цвет команды С-11), flash — тот же обод шире внутрь, кадр флипбука жёлтый → красный.
    Без layer — поза покоя: только rim (вспышка в покое opacity 0)."""
    R = U / 2 - sp.M
    band = sp.pxu(RING_BAND)              # полоса в целых пикселях: при 16 px окно не съедает цвет
    if layer in (None, "rim"):
        _annulus(ctx, sp, R, R - 2 * sp.K - band, C["white"] if team else C["ring.orange"])
    if layer == "flash":
        grow = sp.pxu(RING_FLASH_GROW)
        _annulus(ctx, sp, R, R - 2 * sp.K - band - grow, C["white"] if team else ring_flash_colour(frame))


def heart_glow(ctx, sp: Spec, cx, cy):
    """Ореол урона: плоская полоса hp.glow 1,5 u за keyline сердца (правило ДНК 1 — без градиента; пульс даёт
    opacity слоя). Внутри ореола — та же заливка: слой лежит под сердцем и закрыт им."""
    rim = sp.pxu(1.6)

    def core():
        heart_path(ctx, cx, cy, 5.5, 5.5, -3.5, 10.0)

    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    ctx.set_miter_limit(4)
    inset_fill(ctx, core, -(rim + sp.K + sp.pxu(1.5)), C["hp.glow"])


FALLEN_X = (16.0, 16.4)   # центр креста на сердце (оптический центр ядра; pivot слоя cross в контракте)


def draw_resource_hp_fallen(ctx, sp: Spec, layer=None):
    """Павший (SD-38), форма Codex (принята 2026-10-05, AB-8): почерневшее сердце — внешний контур пустого сердца
    resource-hp-empty (keyline + полоса text.secondary), середина залита card.navy (сердце «почернело» до штампа), —
    и уменьшенный крест state.error: полуразмах 4 u, штрих 2,5 u (было 5,75 / 3) — доли и нижний кончик сердца видны
    (правило ДНК 7: красный — только X). Слои heart и cross в контракте: сердце стоит, крест «штампуется»."""
    if layer in (None, "heart"):
        def core():
            heart_path(ctx, *HEART_C)
        inset_fill(ctx, core, -(sp.E + sp.K), C["keyline"])
        inset_fill(ctx, core, -sp.E, C["dim"])
        inset_fill(ctx, core, sp.pxu(1.0), C["body"])
    if layer in (None, "cross"):
        glyph(ctx, sp, *FALLEN_X, lambda: g_x(ctx, sp, half=4.0, w=sp.pxu(2.5), col=C["error"]))


def draw_marker_x_stamp(ctx, sp: Spec):
    """Крест-штамп (SD-37), форма Codex (принята 2026-10-05, AB-8): «нет защиты» / «отменено» — тот же знак X
    state.error, что у resource-connection-lost, компактный (полуразмах 9 u, было 10,5; штрих 3,5 u, прямые окончания)
    с keyline: на 16 px остаётся 1 px поля до края холста. Тела нет — штамп ложится на слот или карту."""
    glyph(ctx, sp, 16.0, 16.0, lambda: g_x(ctx, sp, half=9.0, w=sp.pxu(3.5), col=C["error"]))


def draw_marker_action_slot_de(ctx, sp: Spec, layer=None):
    """Слот трекера DE (01 F-12), форма Codex (принята 2026-10-05, AB-7): один оранжевый обод ring.orange 1,5 u с
    keyline, внутри тело card.navy и серый диск-призрак text.secondary с opacity 0,35 (⌀ 13 u) — отличает трекер от
    кольца портрета без второго серого контура. Пульсирует, пока выбирается действие; заполнение — слои body/glyph
    принятых action-* поверх (в контракте)."""
    r = U / 2 - sp.M
    if layer in (None, "ring"):
        circle(ctx, U / 2, U / 2, r)
        fill(ctx, C["keyline"])
        circle(ctx, U / 2, U / 2, r - sp.K)
        fill(ctx, C["ring.orange"])
        circle(ctx, U / 2, U / 2, r - sp.K - sp.pxu(1.5))
        fill(ctx, C["keyline"])
        circle(ctx, U / 2, U / 2, r - 2 * sp.K - sp.pxu(1.5))
        fill(ctx, C["body"])
        circle(ctx, U / 2, U / 2, sp.pxu(6.5))
        fill(ctx, C["dim"], 0.35)


# ------------------------------------------------------------------------------------------------ набор VR44 (VS-2 A2)
# Строки IC-38…IC-61 (06-tasks/icons.csv; 02 §5.5 ВР-44), по делегированию. Финал рисует этот движок по числам карточек
# (Codex форм не рисовал); где числа карточки не сходятся с геометрией, записано решение ВР-VS2-NN (README набора v3,
# раздел VR44). Принятые 27 значков и их файлы не меняются (sha1 в manifest.json).
BADGE_W = 24.0            # лента бейджа порядка у клетки (IC-38): 24 × 30 u, x 4…28, y 1…31, вырез 0,28 w = 6,72 u
BADGE_BLOCK = 0.32        # блок команды — 0,32 высоты тела от кромки до апекса выреза (ВР-VS2-13)
BADGE_CAP = (10.5, 9.5)   # runtime-цифра font.card cap: один / два знака (ВР-VS2-13: 13 / 11 из карточки поле не вмещает)
BADGE_DIGIT_DY = 0.25     # центр цифры — середина поля + 0,25 u: при 24 px зазор до блока ≥ 0,5 px, низ выше апекса
BANG_BADGE = (2.75, 5.75, 1.5, 2.75)   # «!» конфликта: планка w × h, зазор, точка (ВР-VS2-14: 9,5 / 1,75 поле не вмещает)
BANG_WARNING = (2.75, 9.0, 1.75, 2.75)  # «!» предупреждения (IC-47): планка y 11…20, точка y 21,75…24,5
WARNING_TRI = ((16.0, 3.5), (29.0, 27.5), (3.0, 27.5))   # треугольник state-warning (ВР-66, ВР-IC16)
CHIP_BODY_R = 13.0        # чип P1: круг тела r 13 u, keyline снаружи до 14 (ВР-78)
CHIP_HEX_R = 14.0         # чип P2: описанный радиус тела (площадь −4 % к кругу P1), вершины на 0°, 60° … 300°
CHIP_HEX_CORNER = 0.5
STEP_TRI = ((16.0, 11.0), (22.0, 18.5), (10.0, 18.5))    # ▲ ui-step: основание 12, высота 7,5, центр масс (16; 16)
# Курсоры (IC-58…IC-61, ВР-IC11): u = px при 32; keyline 2 u снаружи, стык miter с лимитом 2 (остриё срезается).
CURSOR_ARROW = ((3.0, 3.0), (3.0, 24.0), (8.0, 19.0), (11.75, 27.5), (15.25, 26.0), (11.5, 17.5), (18.5, 17.5))
CURSOR_KEYLINE = 2.0
CURSOR_SIZES = (24, 32, 48, 64)   # экспорты курсоров для UE (HB-12): DPI 0,75 / ×1 / 150 % / ×2
CURSOR_BUSY_FRAMES = ((0, 0.0), (2, 0.0), (4, 0.0), (6, 0.0), (6, 90.0), (7, 0.0), (9, 0.0), (11, 0.0))  # (_sent_frames, °)
CURSOR_BUSY_SCALE = 1.2   # песочные часы state-sent ×1,2 (высота 21 u)


def ribbon_sil_px(sp: Spec, w, notch=0.28):
    """Лента VR44 (бейдж порядка, ленты слота): силуэт ribbon_sil, но вертикальные бока на пиксельных колонках
    (симметрично относительно центра холста) — при 16–21 px бока не мылятся; вырез — от номинальной ширины."""
    x0 = sp.snap(U / 2 - w / 2)
    x1 = U - x0
    y0, y1 = sp.M, U - sp.M
    return Poly([(x0, y0), (x1, y0), (x1, y1), (U / 2, y1 - notch * w), (x0, y1)], [0.75, 0.75, 0.4, 0.0, 0.4])


def badge_geom(sp: Spec):
    """Лента бейджа: силуэт, верх тела (u), апекс внутреннего тела (офсет полигона), низ блока (снэп), центр поля."""
    sil = ribbon_sil_px(sp, BADGE_W)
    top_in = sp.M + sp.KE
    apex_in = _offset_poly(sil.pts, sp.KE)[3][1]
    block_bot = sp.snap(top_in + BADGE_BLOCK * (apex_in - top_in))
    return sil, top_in, apex_in, block_bot, (block_bot + apex_in) / 2


def draw_badge_order(ctx, sp: Spec, team=None, text=None, layer=None):
    """Бейдж порядка хода у клетки (IC-38, ВР-IC04/06): лента 24 × 30 u как marker-status (верх r 0,75, хвосты r 0,4,
    вырез 0,28 w, апекс внутренних слоёв — офсет полигона), блок команды 0,32 тела с плоским низом (в мастере цвет
    команды, слой team — белая маска, UMG красит), тело navy. Поле цифры — от блока до апекса тела; цифра cap 10,5 u
    (9,5 u при двух знаках) с центром на середине поля + 0,25 u (ВР-VS2-13)."""
    sil, top_in, apex_in, block_bot, fc = badge_geom(sp)
    fc += BADGE_DIGIT_DY
    if layer in (None, "body"):
        token(ctx, sil, sp)
    if layer in (None, "team"):
        ctx.save()
        sil.path(ctx, sp.KE)
        ctx.clip()
        ctx.rectangle(0, 0, U, block_bot)
        fill(ctx, C["white"] if layer == "team" else (team or C["white"]))
        ctx.restore()
    if text:
        cap = BADGE_CAP[0] if len(text) == 1 else BADGE_CAP[1]
        text_path(ctx, text, cap, U / 2, fc, tracking=-0.15 if len(text) > 1 else 0)
        fill(ctx, C["glyph"])


def g_bang(ctx, sp: Spec, bang, col, keyline=True):
    """«!»: планка w × h с прямыми концами, зазор, точка-квадрат; всё со снэпом (detail 0: планка и точка ≥ 2 px,
    зазор ≥ 1 px); keyline K вокруг каждой части (при detail 0 нет — поле узкое)."""
    w, h, gap, dot = bang
    mn = 2 if sp.detail == 0 else 1
    bw, bh, g, d = sp.pxu(w, mn), sp.pxu(h, mn), sp.pxu(gap), sp.pxu(dot, mn)
    y0 = sp.sy(-(bh + g + d) / 2)
    parts = [(sp.sx(-bw / 2), y0, bw, bh), (sp.sx(-d / 2), y0 + bh + g, d, d)]
    if keyline and sp.detail >= 1:
        for x, y, pw, ph in parts:
            ctx.rectangle(x - sp.K, y - sp.K, pw + 2 * sp.K, ph + 2 * sp.K)
            fill(ctx, C["keyline"])
    for x, y, pw, ph in parts:
        ctx.rectangle(x, y, pw, ph)
        fill(ctx, col)


def draw_badge_conflict(ctx, sp: Spec, team=None, layer=None):
    """Конфликт хода V-09 (IC-41, ВР-IC05): геометрия и блок команды badge-order, в поле цифры — «!» state.error;
    keyline у «!» нет (ВР-VS2-14: на теле navy он не виден, 1,1 : 1, а при 48 px наезжал на блок команды); слои body /
    team общие с badge-order, свой слой glyph. Лента не красная (И-3)."""
    if layer in (None, "body", "team"):
        draw_badge_order(ctx, sp, team=team, layer=layer)
    if layer in (None, "glyph"):
        fc = badge_geom(sp)[4]
        glyph(ctx, sp, U / 2, fc, lambda: g_bang(ctx, sp, BANG_BADGE, C["error"], keyline=False))


def draw_badge_refuse(ctx, sp: Spec, layer=None):
    """Отказ V-08 (IC-40): плашка shape.state_badge (тело navy) и X state.error в боксе глифа — полуразмах 6,75 u,
    штрих 3 u (detail 0 ≥ 2 px), прямые концы, keyline офсетом (при detail 0 нет). Плашка не красная (И-3)."""
    if layer in (None, "body"):
        token(ctx, sq_sil(sp), sp)
    if layer in (None, "glyph"):
        w = sp.pxu(3.0, mn=2 if sp.detail == 0 else 1)
        # detail 0 (16, 18 px): без keyline — тело 10–12 px, keyline X выходил на кремовую кромку (на navy он не виден)
        glyph(ctx, sp, 16.0, 16.0, lambda: g_x(ctx, sp, half=6.75, w=w, col=C["error"], keyline=sp.detail >= 1))


def g_chevrons(ctx, sp: Spec, n=2, w=2.25, arm=5.5, depth=4.75, step=4.75):
    """Двойной шеврон «»» вправо: осевые линии (x, ∓arm) → (x + depth, 0), между остриём первого и спинкой второго —
    шаг step (бокс осевых линий 2 depth + step = 14,25 × 11 u, как в карточке IC-42: две отдельные «галочки»), штрих w,
    стык miter, концы плоские; бокс по факту штриха — по центру. detail 0 — один шеврон штрихом ≥ 2 px."""
    lw = sp.pxu(w, mn=2 if sp.detail == 0 else 1)
    n = 1 if sp.detail == 0 else n

    def path(dx):
        ctx.new_path()
        for i in range(n):
            x = dx + i * (depth + step)
            ctx.move_to(x, -arm)
            ctx.line_to(x + depth, 0.0)
            ctx.line_to(x, arm)

    ctx.set_line_width(lw)
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    ctx.set_miter_limit(10)
    ctx.set_line_cap(cairo.LINE_CAP_BUTT)
    path(0.0)
    x0, _, x1, _ = ctx.stroke_extents()
    path(-(x0 + x1) / 2)
    ctx.stroke()


def draw_badge_ally(ctx, sp: Spec, layer=None):
    """Союзник проходим V-06 (IC-42): плашка shape.state_badge (тело navy), глиф — двойной шеврон «сквозь» card.glyph."""
    _state(ctx, sp, g_chevrons, layer=layer)


def draw_badge_attack_from(ctx, sp: Spec, text=None, layer=None):
    """«Отсюда можно атаковать: N» (IC-43): плашка shape.title_plate как state-hint (слот, линейка, поле числа), в слоте
    — звезда-взрыв g_burst action-attack R 7,75 card.glyph; число — runtime font.card cap 14 u."""
    _plate(ctx, sp, g_burst, text=text, layer=layer, R=7.75)


def draw_team_chip(ctx, sp: Spec, slot=0, tint=None):
    """Чип команды (IC-44 / IC-45, ВР-78): голый жетон — круг тела r 13 u (P1) или шестигранник с описанным радиусом
    14 u, вершинами на 0°, 60° … 300° от +X, углами r 0,5 u (P2), keyline 1 u снаружи; тело белое (UMG умножает на цвет
    команды, И-5), в мастере-превью — цвет команды. При мелких размерах оба жетона уменьшаются одним множителем, чтобы
    keyline 1 px и поле 1 px вошли в холст; плоские грани шестигранника — на пиксельных рядах."""
    ext = CHIP_HEX_R - CHIP_HEX_CORNER / math.sin(math.pi / 3) + CHIP_HEX_CORNER    # крайняя точка тела P2
    s = min(1.0, (U / 2 - sp.M - sp.K) / ext)
    body = tint or C["white"]
    if slot == 0:
        r = CHIP_BODY_R * s
        circle(ctx, U / 2, U / 2, r + sp.K)
        fill(ctx, C["keyline"])
        circle(ctx, U / 2, U / 2, r)
        fill(ctx, body)
        return
    apothem = U / 2 - sp.snap(U / 2 - CHIP_HEX_R * s * math.sin(math.pi / 3))
    R = apothem / math.sin(math.pi / 3)
    pts = [(U / 2 + R * math.cos(math.radians(a)), U / 2 + R * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    sil = Poly(pts, [CHIP_HEX_CORNER] * 6)
    sil.path(ctx, -sp.K)
    fill(ctx, C["keyline"])
    sil.path(ctx, 0)
    fill(ctx, body)


def draw_state_warning(ctx, sp: Spec):
    """Предупреждение (IC-47, ВР-66, ВР-IC16): треугольник вершиной вверх (16; 3,5), (29; 27,5), (3; 27,5), скругление
    1 u; keyline 1 u снаружи, кромка card.cream 1,25 u внутрь, тело state.warning; «!» card.navy по оси x = 16.
    Основание снэпнуто к пиксельному ряду (keyline снизу — целый ряд)."""
    (ax, ay), (bx, by), (cx_, _) = WARNING_TRI
    base = sp.snap(by + sp.K) - sp.K
    sil = Poly([(ax, ay), (bx, base), (cx_, base)], [1.0, 1.0, 1.0])
    sil.path(ctx, -sp.K)
    fill(ctx, C["keyline"])
    sil.path(ctx, 0)
    fill(ctx, C["edge"])
    sil.path(ctx, sp.E)
    fill(ctx, C["warning"])
    w, h, gap, dot = BANG_WARNING
    glyph(ctx, sp, 16.0, 11.0 + (h + gap + dot) / 2, lambda: g_bang(ctx, sp, BANG_WARNING, C["body"], keyline=False))


def draw_marker_slot(ctx, sp: Spec, kind="scheme"):
    """Лента слота карты-источника (IC-50 / IC-51 / IC-52, ВР-IC12): геометрия marker-status (20,6 × 30 u, вырез
    0,28 w) без блока команды; scheme — тело card.type.scheme, молния action-scheme ×0,8 card.navy; boost — тело navy,
    белое кольцо card.glyph r 3,5…5,25 u (язык диска BOOST); discard — тело text.secondary, глиф card-drop ×0,8
    card.navy. Центр глифа — центр поля (кромка…апекс) −0,3 u."""
    w = 20.6
    body = {"scheme": C["scheme"], "discard": C["dim"]}.get(kind, C["body"])
    token(ctx, ribbon_sil_px(sp, w), sp, body=body)
    cy = ((sp.M + sp.KE) + (U - sp.M - 0.28 * w)) / 2 - 0.3
    if kind == "scheme":
        glyph(ctx, sp, U / 2, cy, lambda: g_bolt(ctx, sp, s=0.8), col=C["body"])
        return
    if kind == "discard":
        glyph(ctx, sp, U / 2, cy, lambda: g_card_drop_slot(ctx, sp, C["body"]), col=C["body"])
        return

    def ring():
        r = 5.25
        circle(ctx, 0, 0, r)
        ctx.fill()
        circle(ctx, 0, 0, r - sp.ring)
        clear(ctx)

    glyph(ctx, sp, U / 2, cy, ring)


def g_menu(ctx, sp: Spec):
    """«≡»: три прямые планки 16 × 2,25 u, зазоры 3,5 u, плоские концы, keyline K вокруг каждой; detail 0 — планки и
    зазоры ≥ 2 px. Белая маска (UMG красит)."""
    mn = 2 if sp.detail == 0 else 1
    h, g = sp.pxu(2.25, mn), sp.pxu(3.5, mn)
    y0 = sp.sy(-(3 * h + 2 * g) / 2)
    x0, x1 = sp.sx(-8.0), sp.sx(8.0)
    bars = [(x0, y0 + i * (h + g), x1 - x0, h) for i in range(3)]
    for x, y, bw, bh in bars:
        ctx.rectangle(x - sp.K, y - sp.K, bw + 2 * sp.K, bh + 2 * sp.K)
        fill(ctx, C["keyline"])
    for x, y, bw, bh in bars:
        ctx.rectangle(x, y, bw, bh)
        fill(ctx, C["white"])


def draw_ui_menu(ctx, sp: Spec):
    glyph(ctx, sp, 16.0, 16.0, lambda: g_menu(ctx, sp))


def draw_ui_close(ctx, sp: Spec):
    """«×» закрыть (IC-54): две планки W крестом под 45°, полуразмах 6 u, плоские концы, keyline офсетом; белая маска,
    никогда не красный и без плашки (И-3, И-10)."""
    glyph(ctx, sp, 16.0, 16.0, lambda: g_x(ctx, sp, half=6.0, w=sp.W, col=C["white"]))


def draw_ui_step(ctx, sp: Spec):
    """«▲» выбора числа (IC-56): треугольник вершиной вверх, основание 12 u, высота 7,5 u, центр масс (16; 16),
    скругление 0,75 u, keyline 1 u снаружи; белая маска; «▼» — поворот 180° в UMG. Основание без снэпа (ВР-VS2-17):
    центр масс тела на (16; 16) при любом размере, поворот на 180° его не сдвигает."""
    sil = Poly(STEP_TRI, [0.75, 0.75, 0.75])
    sil.path(ctx, -sp.K)
    fill(ctx, C["keyline"])
    sil.path(ctx, 0)
    fill(ctx, C["white"])


def _cursor_outline(ctx, sp: Spec, pts):
    """Курсор: тело card.glyph и keyline mark.keyline CURSOR_KEYLINE u снаружи — заливка + штрих 2 K одной фигурой
    (стык miter, лимит 2: острое остриё срезается и не выходит за поле)."""
    k2 = sp.pxu(CURSOR_KEYLINE)
    ctx.set_line_join(cairo.LINE_JOIN_MITER)
    ctx.set_miter_limit(2.0)
    poly(ctx, pts)
    rgb(ctx, C["keyline"])
    ctx.set_line_width(2 * k2)
    ctx.stroke_preserve()
    ctx.fill()
    poly(ctx, pts)
    fill(ctx, C["glyph"])


def draw_cursor_default(ctx, sp: Spec):
    """Обычный курсор (IC-58, ВР-IC11, ВР-46): стрелка CURSOR_ARROW, тело card.glyph, keyline 2 u, без тени."""
    _cursor_outline(ctx, sp, CURSOR_ARROW)


def draw_cursor_unavailable(ctx, sp: Spec):
    """Недоступно (IC-60): cursor-default и малый X state.error — центр (23; 23) u, полуразмах 4,25 u, штрих 2,5 u,
    keyline 2 u; X в нижнем правом поле, остриё стрелки свободно; красный только у знака (И-3)."""
    _cursor_outline(ctx, sp, CURSOR_ARROW)
    k2 = sp.pxu(CURSOR_KEYLINE)
    w = sp.pxu(2.5)
    L = 4.25 * math.sqrt(2)
    ctx.save()
    ctx.translate(23.0, 23.0)
    for pass_, col in ((0, C["keyline"]), (1, C["error"])):
        g = k2 if pass_ == 0 else 0.0
        for s_ in (1, -1):
            ctx.save()
            ctx.rotate(s_ * math.pi / 4)
            ctx.rectangle(-L - g, -w / 2 - g, 2 * L + 2 * g, w + 2 * g)
            fill(ctx, col)
            ctx.restore()
    ctx.restore()


def _hourglass_shell(ctx, sp: Spec, angle=0.0):
    """Силуэт песочных часов g_hourglass (планки + колба без вырезов) — подложка keyline курсора «занято»."""
    ctx.save()
    ctx.rotate(angle)
    snap = sp.sy if abs(angle) < 1e-6 else (lambda y: y)
    bw, ch = 6.5, 0.5
    y_out = snap(8.75)
    y_in = y_out - sp.pxu(1.5)
    for sgn in (-1, 1):
        a, b = (y_in, y_out) if sgn > 0 else (-y_out, -y_in)
        poly(ctx, [(-bw + ch, a), (bw - ch, a), (bw, a + ch), (bw, b - ch), (bw - ch, b), (-bw + ch, b),
                   (-bw, b - ch), (-bw, a + ch)])
    hw0, wst = 6.0, 2.3
    if sp.detail == 0:
        wst = max(wst, 1.0 / sp.k)
    poly(ctx, [(-hw0, -y_in - 0.3), (hw0, -y_in - 0.3), (wst, 0), (hw0, y_in + 0.3), (-hw0, y_in + 0.3), (-wst, 0)])
    ctx.restore()


def draw_cursor_busy(ctx, sp: Spec, frame=0):
    """Занято (IC-61): песочные часы state-sent без плашки ×1,2 (высота 21 u) по центру (16; 16), keyline 2 u; кадр
    frame из CURSOR_BUSY_FRAMES (кадры _sent_frames(), f04 — повёрнутый на 90°, середина переворота). Глиф рисуется
    в своей сетке Spec(size × 1,2): толщины и горизонтальные кромки ложатся на пиксели холста; «воздух» колбы —
    keyline (тёмный)."""
    idx, deg = CURSOR_BUSY_FRAMES[frame]
    kw = _sent_frames()[idx]
    s = CURSOR_BUSY_SCALE
    g = Spec(sp.size * s)
    g.detail = sp.detail
    g.ox = g.oy = (U / 2) / s
    top, bottom, stream = kw["top"], kw["bottom"], kw["stream"]
    if sp.detail == 0:
        top, bottom, stream = 1.0, 1.0, False
    angle = math.radians(deg)
    k2 = sp.pxu(CURSOR_KEYLINE) / s
    ctx.save()
    ctx.translate(U / 2, U / 2)
    ctx.scale(s, s)
    ctx.set_line_join(cairo.LINE_JOIN_ROUND)   # силуэт из нескольких фигур: miter давал «уши» на фасках планок
    _hourglass_shell(ctx, g, angle)
    rgb(ctx, C["keyline"])
    ctx.set_line_width(2 * k2)
    ctx.stroke_preserve()
    ctx.fill()
    ctx.push_group()
    rgb(ctx, C["glyph"])
    g_hourglass(ctx, g, top=top, bottom=bottom, angle=angle, stream=stream)
    ctx.pop_group_to_source()
    ctx.paint()
    ctx.restore()


def cursor_hotspot(name, size):
    """Горячая точка курсора в px размера size (начало сверху слева): у стрелок — середина среза острия внешней кромки
    (keyline снаружи, лимит miter 2), сдвинутая внутрь до первого пикселя с α ≥ 128; у «занято» — центр холста."""
    if name == "cursor-busy":
        return [size // 2, size // 2]
    if name == "cursor-pointer":
        return pointer_hotspot(size)
    sp = Spec(size)
    k2 = sp.pxu(CURSOR_KEYLINE)
    (tx, ty), (_, by), (sx_, sy_) = CURSOR_ARROW[0], CURSOR_ARROW[1], CURSOR_ARROW[-1]
    # внешние нормали двух рёбер у острия: левое (вертикаль) — (−1, 0); ребро к (18,5; 17,5) — наружу вверх-вправо
    dx, dy = sx_ - tx, sy_ - ty
    L = math.hypot(dx, dy)
    n2 = (dy / L, -dx / L)
    p1, p2 = (tx - k2, ty), (tx + k2 * n2[0], ty + k2 * n2[1])
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    im = np.asarray(render(name, size))[..., 3]
    bis = ((0 + dx / L) / 2, (1 + dy / L) / 2)        # биссектриса внутрь от острия
    for t in np.arange(0.0, 4.0, 0.05):
        x, y = int(math.floor((mx + bis[0] * t) * sp.k)), int(math.floor((my + bis[1] * t) * sp.k))
        if 0 <= x < size and 0 <= y < size and im[y, x] >= 128:
            return [x, y]
    raise RuntimeError(f"{name}-{size}: hotspot not found")


# ------------------------------------------------------------------------------------------------ VR44, VS-2 шаг A3
# Строки IC-46, IC-48, IC-55, IC-59 — формы Codex IC-36, вектор A (art/imagegen/hud-icons-vr44-codex/README.md, принят
# по делегированию: end-turn и card-drop — ревью VS-1, log и pointer — доработка fix1, ВР-VS2-01, ВР-VS2-02). Числа
# перенесены один в один из _tools/draw_candidates.py пакета; альфа экспорта совпадает побайтно с vector/<px>/<name>.png
# (pytest test_vr44_forms_match_codex_proposal). Этап «точной палитры» Codex не переносится (ВР-VS2-23): внутренние
# AA-стыки — как у остальных значков v3 (диск конца хода стоит в ряду ACTIONS рядом с action-*). IC-52 — лента слота
# с глифом card-drop ×0,8.
END_TURN_SHAFT = (-8.0, -1.25)          # древко x от … до (u, локально от центра (16; 16)); ширина W
END_TURN_HEAD = ((-1.25, -3.5), (3.25, 0.0), (-1.25, 3.5))   # наконечник: основание 7 u, длина 4,5 u
END_TURN_BAR = (4.75, -6.0, 2.25, 12.0)  # стоп-черта x, y, w, h (зазор острие–черта 1,5 u до снэпа)
CARD_DROP_ARROW = (-9.5, -4.5, 3.5, -0.5)   # древко: верх, основание наконечника, полуширина основания, остриё (y)
CARD_DROP_SLABS = (1.5, 15.0, 3.0, 3.5, 1.0)  # стопка: y первой плашки, ширина, высота, скос, зазор (две плашки)
LOG_ROWS = (8.375, 2.75, 1.5, 11.0, 4.5)  # журнал: x маркера, сторона маркера, зазор, длина строки, шаг строк (u)
POINTER_HAND = ((7, 2), (15, 2), (15, 11), (20, 11), (20, 13), (24, 13), (24, 15), (28, 15), (28, 27), (25, 30),
                (11, 30), (8, 27), (8, 25), (5, 22), (3, 22), (3, 17), (7, 17))   # абсолютные u, радиусы 0 (fix1)
POINTER_HOTSPOT_U = (11, 2)             # середина верхнего торца пальца (ВР-VS2-02)
SLOT_DISCARD_SCALE = 0.8                # глиф card-drop в ленте слота (IC-52, ВР-IC12)


def _cx_poly(ctx, sp: Spec, pts, col=None):
    """Многоугольник глифа: вершины снэпнуты к пикселям в абсолютных u (sp.sx / sp.sy), как polygon() пакета Codex."""
    poly(ctx, [(sp.sx(x), sp.sy(y)) for x, y in pts])
    fill(ctx, col or C["glyph"])


def g_end_turn(ctx, sp: Spec, col=None):
    """«→|» конца хода (IC-46, вектор A IC-36): древко и наконечник — один замкнутый полигон (без шва), стоп-черта
    2,25 × 12 u; бокс 15 × 12 u."""
    top = sp.sy(-sp.W / 2)
    bot = top + sp.W
    (x0, x1), ((hx0, hy0), (tx, ty), (_, hy1)) = END_TURN_SHAFT, END_TURN_HEAD
    _cx_poly(ctx, sp, [(x0, top), (x1, top), (hx0, hy0), (tx, ty), (hx0, hy1), (x1, bot), (x0, bot)], col)
    bx, by, bw, bh = END_TURN_BAR
    ctx.rectangle(sp.sx(bx), sp.sy(by), sp.pxu(bw), sp.pxu(bh))
    fill(ctx, col or C["glyph"])


def draw_action_end_turn(ctx, sp: Spec, layer=None):
    """Диск «Конец хода» (IC-46, ВР-IC09): семейство shape.action_disc — keyline, кремовое кольцо, тело navy (не жёлтое
    и не красное: жёлтое — тело главной кнопки); глиф «→|» card.glyph. Слои body / glyph для UMG и движения."""
    _action(ctx, sp, lambda c, s: g_end_turn(c, s), C["body"], layer=layer)


def g_card_drop(ctx, sp: Spec, col=None):
    """«В сброс» (IC-48, вектор A IC-36): стрелка вниз (древко W, наконечник 7 × 4 u) над стопкой из двух скошенных
    плашек 15 × 3 u (скос 3,5 u, зазор 1 px, язык resource-card); без лотка и коробки; detail 0 — плашки по 1 px."""
    top, base, hw, tip = CARD_DROP_ARROW
    left = sp.sx(-sp.W / 2)
    right = left + sp.W
    _cx_poly(ctx, sp, [(left, top), (right, top), (right, base), (hw, base), (0, tip), (-hw, base), (left, base)], col)
    y0, w, h_u, skew, gap_u = CARD_DROP_SLABS
    h = sp.pxu(h_u) if sp.detail else 1 / sp.k
    gap = sp.pxu(gap_u)
    y = sp.sy(y0)
    for i in range(2):
        yi = y + i * (h + gap)
        _cx_poly(ctx, sp, [(-w / 2 + skew, yi), (w / 2, yi), (w / 2 - skew, yi + h), (-w / 2, yi + h)], col)


def draw_card_drop(ctx, sp: Spec, layer=None):
    """Карта уйдёт в сброс (IC-48, ВР-IC13): плашка shape.state_badge (тело navy) — слой body, глиф card-drop — слой
    glyph."""
    _state(ctx, sp, g_card_drop, layer=layer)


def _log_rects(sp: Spec):
    """Строки журнала в абсолютных u: целочисленный шаг рядов (fix1 Codex: независимый снэп слеплял маркеры при 21 px);
    detail 0 — две строки с центрами px(13), px(19)."""
    mx, msz, gap, lw, pitch = LOG_ROWS
    xpx, bpx, gpx, c, p = sp.px(mx), sp.px(msz), sp.px(gap), sp.px(16), sp.px(pitch)
    centers = [sp.px(13), sp.px(19)] if sp.detail == 0 else [c - p, c, c + p]
    for cy in centers:
        yield xpx / sp.k, (cy - bpx // 2) / sp.k, bpx / sp.k, bpx / sp.k
        yield (xpx + bpx + gpx) / sp.k, (cy - sp.px(2.25) // 2) / sp.k, sp.pxu(lw), sp.W


def draw_ui_log(ctx, sp: Spec):
    """Глиф «Журнал» (IC-55, ВР-IC10 + ВР-VS2-01): диск-пипс как у конца хода (keyline r 14–15 u, крем r 12,75–14 u,
    navy), белая печать — три строки 11 × 2,25 u с квадратными маркерами 2,75 u, без своего keyline (границу несёт диск).
    Не «≡» (ui-menu) и не стопка (resource-card)."""
    token(ctx, disc_sil(sp), sp)

    def rows():
        for x, y, w, h in _log_rects(sp):
            ctx.rectangle(x - 16, y - 16, w, h)
        fill(ctx, C["glyph"])

    glyph(ctx, sp, 16, 16, rows)


def draw_cursor_pointer(ctx, sp: Spec):
    """Указатель (IC-59, ВР-IC11 + ВР-VS2-02): плоская рука, указательный палец вертикально вверх слева (торец 8 u),
    три ступени согнутых пальцев справа, большой палец слева, плоское запястье; keyline mark.keyline 2 u — офсет внутрь
    того же силуэта (тело card.glyph), радиусы 0, без кольца и тени. Горячая точка — середина торца (11; 2) u."""
    pts = [(sp.snap(x), sp.snap(y)) for x, y in POINTER_HAND]
    sil = Poly(pts, [0] * len(pts))
    sil.path(ctx)
    fill(ctx, C["keyline"])
    sil.path(ctx, sp.pxu(CURSOR_KEYLINE))
    fill(ctx, C["glyph"])


def pointer_hotspot(size):
    """Горячая точка указателя (как verification.json пакета IC-36): первый ряд торца пальца, где есть α = 255; x —
    середина непрозрачного отрезка этого ряда floor((xmin + xmax + 1) / 2). 24 → (8, 2), 32 → (11, 2), 48 → (17, 3),
    64 → (22, 4)."""
    a = np.asarray(render("cursor-pointer", size))[..., 3]
    for y in range(size):
        xs = np.where(a[y] == 255)[0]
        if len(xs):
            return [int((xs.min() + xs.max() + 1) // 2), int(y)]
    raise RuntimeError(f"cursor-pointer-{size}: hotspot not found")


def g_card_drop_slot(ctx, sp: Spec, col):
    """Глиф card-drop ×0,8 для ленты слота: своя сетка Spec(size × 0,8) (как глиф cursor-busy), чтобы толщины, зазор
    стопки и горизонтальные кромки ложились на пиксели холста."""
    s = SLOT_DISCARD_SCALE
    g = Spec(sp.size * s)
    g.detail = sp.detail
    g.ox, g.oy = sp.ox / s, sp.oy / s
    ctx.save()
    ctx.scale(s, s)
    g_card_drop(ctx, g, col=col)
    ctx.restore()


# ------------------------------------------------------------------------------------------------ VR44, VS-4 шаг V3
# Строки IC-62…IC-69 (ВР-IC07) — значки зон у клетки: формы принятого предложения Codex IC-37 (вариант A каждого ключа,
# art/imagegen/zone-icons-codex/README.md, ревью VS-1 по делегированию), числа перенесены один в один (абсолютные u,
# снэп каждой координаты; вырезы листа и пламени — только при detail 2). Плашка shape.state_badge (30 u, r 1,5 u, keyline
# 1 u, кромка card.cream 1,25 u, тело card.navy), диск r 11 u с ободком card.cream 0,5 u (r 11…11,5), глиф в боксе 13 u.
# Слои: _body — плашка с ободком и прозрачным окном диска; _disc — белая маска диска (тон даёт UMG из профиля доски,
# boards[].zoneIconSrgb); _glyph — белая маска глифа с keyline mark.keyline ровно 1 px наружу (расширение маски 3 × 3,
# как в пакете). Отличия от пакета (ВР-VS4-50, -51): сглаживание движка (ANTIALIAS_BEST, как у остальных значков v3;
# пакет рисовал без сглаживания ради «точной палитры» — тот этап не переносится, как ВР-VS2-23), и диск слоя _disc
# заходит под кремовый ободок (r 11 + 0,5 u), чтобы сглаженный край окна не просвечивал (в цельном значке ободок его
# закрывает, вид тот же). Цвет диска мастера и размеров — замер кадров I Marmoreal (02 §7.4), варианты -sarpedon —
# Sarpedon; глиф — card.navy или card.glyph, у кого контраст к диску выше (02 §7.4, ВР-68).
ZONE_KEYS = ("gray", "green", "blue", "violet", "purple", "red", "brown", "yellow")
ZONE_DISC = {
    "marmoreal": dict(zip(ZONE_KEYS, ("#DEDEE0", "#5EA66F", "#4E84A1", "#9187A9", "#904A80", "#D39BA5", "#9A6D5D",
                                      "#D5BD8A"))),
    "sarpedon": {"green": "#2F8564", "blue": "#90AABB", "yellow": "#DCC88E", "red": "#A43839", "purple": "#B182A2",
                 "brown": "#8C6034"},
}
ZONE_DISC_R = 11.0        # диск у клетки, u (ободок card.cream 0,5 u снаружи)
ZONE_PLATE_R = 1.5        # радиус плашки, u


def _lum(hexv):
    c = np.array([int(hexv[i:i + 2], 16) for i in (1, 3, 5)], float) / 255
    c = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return float(c @ [0.2126, 0.7152, 0.0722])


def zone_contrast(a, b):
    x, y = sorted((_lum(a), _lum(b)))
    return (y + 0.05) / (x + 0.05)


def zone_ink(disc_hex):
    """Цвет глифа на диске: card.navy или card.glyph — у кого контраст к диску выше (рантайм — то же правило)."""
    return max((TOKENS["card.navy"], TOKENS["card.glyph"]), key=lambda c: zone_contrast(c, disc_hex))


def _zpath(ctx, sp: Spec, cmds):
    """Путь пакета IC-37: каждая координата снэпается в абсолютных u."""
    for cmd, pts in cmds:
        pts = [sp.snap(n) for n in pts]
        {"M": ctx.move_to, "L": ctx.line_to, "C": ctx.curve_to}[cmd](*pts)
    ctx.close_path()


def _zrect(ctx, sp: Spec, x, y, w, h):
    x0, y0, x1, y1 = map(sp.snap, (x, y, x + w, y + h))
    ctx.rectangle(x0, y0, x1 - x0, y1 - y0)


def zg_gray(ctx, sp: Spec):
    _zrect(ctx, sp, 11.75, 11.75, 8.5, 8.5)
    fill(ctx, C["white"])


def zg_green(ctx, sp: Spec):
    _zpath(ctx, sp, [("M", [11.5, 20.5]), ("C", [11.5, 14.5, 14.5, 11.5, 20.5, 11.5]), ("C", [20.5, 17.5, 17.5, 20.5, 11.5, 20.5])])
    fill(ctx, C["white"])
    if sp.detail > 1:
        ctx.move_to(sp.snap(13), sp.snap(19))
        ctx.line_to(sp.snap(19), sp.snap(13))
        ctx.save()
        ctx.set_line_width(sp.pxu(1.5))
        ctx.set_line_cap(cairo.LINE_CAP_BUTT)
        ctx.set_operator(cairo.OPERATOR_CLEAR)
        ctx.stroke()
        ctx.restore()


def zg_blue(ctx, sp: Spec):
    w = sp.W
    for cy in (12, 20):
        _zpath(ctx, sp, [("M", [10.5, cy - w / 2]), ("C", [12.3, cy - w / 2 - .75, 14.2, cy - w / 2 - .75, 16, cy - w / 2]),
                         ("C", [17.8, cy - w / 2 + .75, 19.7, cy - w / 2 + .75, 21.5, cy - w / 2]), ("L", [21.5, cy + w / 2]),
                         ("C", [19.7, cy + w / 2 + .75, 17.8, cy + w / 2 + .75, 16, cy + w / 2]),
                         ("C", [14.2, cy + w / 2 - .75, 12.3, cy + w / 2 - .75, 10.5, cy + w / 2])])
        fill(ctx, C["white"])


def zg_violet(ctx, sp: Spec):
    circle(ctx, sp.snap(17.25), sp.snap(16), sp.snap(5.25))
    fill(ctx, C["white"])
    circle(ctx, sp.snap(19.75), sp.snap(16), sp.snap(4.5))
    clear(ctx)


def zg_purple(ctx, sp: Spec):
    _zpath(ctx, sp, [("M", [11, 21]), ("L", [11, 16]), ("C", [11, 9.333333, 21, 9.333333, 21, 16]), ("L", [21, 21])])
    fill(ctx, C["white"])
    _zrect(ctx, sp, 13.75, 15.25, 4.5, 7)
    clear(ctx)


def zg_red(ctx, sp: Spec):
    _zpath(ctx, sp, [("M", [16.8, 9.5]), ("C", [16.4, 12.15, 14.1, 12.55, 13.3, 14.45]), ("C", [10.9, 17.85, 13.2, 20, 16, 20]),
                     ("C", [19.5, 20, 21.1, 17.45, 18.7, 14.15]), ("C", [18.9, 16.05, 17.1, 16.35, 17.2, 14.35]),
                     ("C", [17.3, 12.65, 16.7, 10.95, 16.8, 9.5])])
    fill(ctx, C["white"])
    if sp.detail > 1:
        _zpath(ctx, sp, [("M", [16.2, 15.35]), ("C", [16.1, 16.35, 14.8, 16.85, 14.8, 17.75]),
                         ("C", [14.8, 19.55, 17.5, 19.55, 17.5, 17.75]), ("C", [17.5, 17.05, 16.8, 16.15, 16.2, 15.35])])
        clear(ctx)


def zg_brown(ctx, sp: Spec):
    p = [(10, 19.5), (13.25, 12.5), (18.75, 12.5), (22, 19.5)]
    Poly([(sp.snap(x), sp.snap(y)) for x, y in p], [0, sp.pxu(1), sp.pxu(1), 0]).path(ctx)
    fill(ctx, C["white"])


def zg_yellow(ctx, sp: Spec):
    for x, y in [(16, 12.5), (12.5, 18.562178), (19.5, 18.562178)]:
        circle(ctx, sp.snap(x), sp.snap(y), sp.pxu(1.5))
    fill(ctx, C["white"])


ZONE_GLYPHS = dict(zip(ZONE_KEYS, (zg_gray, zg_green, zg_blue, zg_violet, zg_purple, zg_red, zg_brown, zg_yellow)))


def zone_glyph_alpha(key, size):
    """Альфа белой маски глифа ключа на холсте size × size (сглаживание движка), uint8."""
    sp = Spec(size)
    surf, c2 = surface(size, size)
    c2.scale(sp.k, sp.k)
    ZONE_GLYPHS[key](c2, sp)
    surf.flush()
    stride = surf.get_stride()
    buf = np.frombuffer(surf.get_data(), dtype=np.uint8).reshape(size, stride)[:, : size * 4].reshape(size, size, 4)
    return buf[..., 3].copy()


def _paint_alpha(ctx, alpha, col):
    """Заливка цветом col по маске alpha в пикселях холста (без масштаба контекста)."""
    h, w = alpha.shape
    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_A8, w)
    buf = np.zeros((h, stride), np.uint8)
    buf[:, :w] = alpha
    ms = cairo.ImageSurface.create_for_data(memoryview(buf), cairo.FORMAT_A8, w, h, stride)
    ctx.save()
    ctx.identity_matrix()
    rgb(ctx, col)
    ctx.mask_surface(ms, 0, 0)
    ctx.restore()
    ms.finish()


def draw_zone(ctx, sp: Spec, key="gray", layer=None, disc=None):
    """Значок зоны у клетки (IC-62…IC-69): диск цвета зоны в окне плашки, глиф ключа с keyline 1 px. layer: body / disc /
    glyph — слои UMG (диск и глиф — белые маски, тон даёт игра); None — цельный значок (диск цветом кадра Marmoreal или
    disc, глиф — цвет правила контраста)."""
    disc_hex = disc or ZONE_DISC["marmoreal"][key]
    ring_r = sp.snap(ZONE_DISC_R) + sp.rim
    if layer in (None, "disc"):
        circle(ctx, U / 2, U / 2, ring_r)  # под ободок: сглаженный край окна плашки не просвечивает (ВР-VS4-51)
        fill(ctx, C["white"] if layer == "disc" else hx(disc_hex))
    if layer in (None, "body"):
        ctx.push_group()
        token(ctx, rect_sil(sp.M, sp.M, U - 2 * sp.M, U - 2 * sp.M, sp.pxu(ZONE_PLATE_R)), sp)
        circle(ctx, U / 2, U / 2, ring_r)
        fill(ctx, C["edge"])
        circle(ctx, U / 2, U / 2, sp.snap(ZONE_DISC_R))
        clear(ctx)
        ctx.pop_group_to_source()
        ctx.paint()
    if layer in (None, "glyph"):
        from scipy import ndimage
        a = zone_glyph_alpha(key, sp.size)
        _paint_alpha(ctx, ndimage.grey_dilation(a, size=(3, 3)), C["keyline"])   # keyline ровно 1 px наружу
        _paint_alpha(ctx, a, C["white"] if layer == "glyph" else hx(zone_ink(disc_hex)))


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
# набор DE-012, принятый пользователем 2026-10-05 (AB-5, AB-7, AB-8): новые id после 23 значков v3 — на листах
# принятого набора (ORDER_ACCEPTED) и на своём листе sheets/de012/. В контракте движения — список `accepted_de012`.
DE_ACCEPTED = {
    "marker-turn-ring": (draw_marker_turn_ring, {}, False),
    "resource-hp-fallen": (draw_resource_hp_fallen, {}, False),
    "marker-x-stamp": (draw_marker_x_stamp, {}, False),
    "marker-action-slot-de": (draw_marker_action_slot_de, {}, False),
}
# кандидаты DE-012 до арт-приёмки: в мастерах, размерах и слоях, но не на листах принятого набора; лист sheets/de012/.
# В контракте движения — список `candidates`. AB-5 выбрал тёплое кольцо: вариант цвета команды остаётся галереей.
CANDIDATES = {
    "marker-turn-ring-team": (draw_marker_turn_ring, {"team": True}, False),
}
# IC-33 (ВР-IC14, по делегированию): набор VR44 (02 §5.5) — строки IC-34, IC-38…IC-69 добавляют id сюда.
# До ревью строки id — в CANDIDATES_VR44: мастер, размеры, слои и свой лист sheets/vr44/, но не листы принятого набора.
# После ревью id переходит в ACCEPTED_VR44 и встаёт в ORDER_ACCEPTED после DE_ACCEPTED (листы принятого набора); в
# контракте движения — список `accepted_vr44`. Курсоры (IC-58…IC-61) рисуются здесь же, но в UE их импортирует HB-12.
CANDIDATES_VR44: dict = {}
# VS-2 A2 (IC-38…IC-61): строки приняты по делегированию после поштучного ревью листов (ВР-42, ВР-60; README набора,
# раздел VR44). Курсоры — в наборе движка и на листах, но не в контракте движения и не в IconsV3 (HB-12).
ACCEPTED_VR44: dict = {
    "badge-order": (draw_badge_order, {"team": C["team1"]}, False),
    "badge-refuse": (draw_badge_refuse, {}, False),
    "badge-conflict": (draw_badge_conflict, {"team": C["team1"]}, False),
    "badge-ally": (draw_badge_ally, {}, False),
    "badge-attack-from": (draw_badge_attack_from, {}, True),
    "team-chip-p1": (draw_team_chip, {"slot": 0}, False),
    "team-chip-p2": (draw_team_chip, {"slot": 1}, False),
    "state-warning": (draw_state_warning, {}, False),
    "marker-slot-scheme": (draw_marker_slot, {"kind": "scheme"}, False),
    "marker-slot-boost": (draw_marker_slot, {"kind": "boost"}, False),
    "ui-menu": (draw_ui_menu, {}, False),
    "ui-close": (draw_ui_close, {}, False),
    "ui-step": (draw_ui_step, {}, False),
    "cursor-default": (draw_cursor_default, {}, False),
    "cursor-unavailable": (draw_cursor_unavailable, {}, False),
    "cursor-busy": (draw_cursor_busy, {}, False),
    # VS-2 A3: формы Codex IC-36 (вектор A) — IC-46, IC-48, IC-55, IC-59; IC-52 — лента слота «в сброс»
    "action-end-turn": (draw_action_end_turn, {}, False),
    "card-drop": (draw_card_drop, {}, False),
    "ui-log": (draw_ui_log, {}, False),
    "cursor-pointer": (draw_cursor_pointer, {}, False),
    "marker-slot-discard": (draw_marker_slot, {"kind": "discard"}, False),
    # VS-4 V3: значки зон у клетки IC-62…IC-69 (формы Codex IC-37, вариант A; ВР-VS4-50, -51)
    **{f"zone-{k}": (draw_zone, {"key": k}, False) for k in ZONE_KEYS},
}
# варианты id набора VR44 (как marker-status-p2): та же геометрия, для листов, галереи и запасного вида без тона
VARIANTS_VR44 = {
    "badge-order-p2": (draw_badge_order, {"team": C["team2"]}, False),
    # VS-4 V3: диски зон цветом кадров Sarpedon (у Sarpedon нет ключей gray и violet)
    **{f"zone-{k}-sarpedon": (draw_zone, {"key": k, "disc": ZONE_DISC["sarpedon"][k]}, False) for k in ZONE_KEYS
       if k in ZONE_DISC["sarpedon"]},
}
CURSORS = tuple(n for n in ACCEPTED_VR44 if n.startswith("cursor-"))
# мастер-превью отличается от текстуры размеров (И-5): тело чипа в текстуре белое, в мастере — цвет команды
MASTER_KW = {"team-chip-p1": {"tint": C["team1"]}, "team-chip-p2": {"tint": C["team2"]}}
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
    # набор DE-012 (glow, кольцо, павший, слот — приняты 2026-10-05; кольцо team — кандидат)
    "resource-hp-full": ("glow",),
    "marker-turn-ring": ("rim", "flash"),
    "marker-turn-ring-team": ("rim", "flash"),
    "resource-hp-fallen": ("heart", "cross"),
    "marker-action-slot-de": ("ring",),
    # набор VR44 (VS-2 A2): слои для UMG (тело, блок команды — белая маска, глиф); у конфликта тело и блок — слои
    # badge-order (контракт: src badge-order_body / _team)
    "badge-order": ("body", "team"),
    "badge-conflict": ("glyph",),
    "badge-refuse": ("body", "glyph"),
    "badge-ally": ("body", "glyph"),
    "badge-attack-from": ("body", "glyph"),
    # VS-2 A3: диск конца хода и плашка «в сброс» — слои для UUmButton / UUmCardWidget и движения (select, appear)
    "action-end-turn": ("body", "glyph"),
    "card-drop": ("body", "glyph"),
    # VS-4 V3: значки зон — плашка и диск общие (слои zone-gray), глиф у каждого ключа свой
    "zone-gray": ("body", "disc", "glyph"),
    **{f"zone-{k}": ("glyph",) for k in ZONE_KEYS if k != "gray"},
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


FLIPBOOKS = {("state-sent", "glyph"): _sent_frames(),
             ("marker-turn-ring", "flash"): [{"frame": i} for i in range(RING_FLASH_FRAMES)]}
ALL = (list(ICONS) + list(VARIANTS) + list(DE_ACCEPTED) + list(CANDIDATES) + list(ACCEPTED_VR44) + list(VARIANTS_VR44)
       + list(CANDIDATES_VR44))
ORDER23 = [k for k in ICONS if k != "action-attack-token-glyphmask"]
# 27 принятых: 23 v3 (2026-10-03) + 4 DE-012 (2026-10-05); затем принятые VR44 (IC-33)
ORDER_ACCEPTED = ORDER23 + list(DE_ACCEPTED) + list(ACCEPTED_VR44)
EXAMPLE = {"state-boost": {"text": "+2"}, "state-hint": {"text": "1"}, "state-threat": {"text": "3"},
           "marker-status": {"text": "1", "team": C["team1"]}, "marker-status-p1": {"text": "1"},
           "marker-status-p2": {"text": "2"}, "resource-hp-full": {"text": "17"}, "resource-hp-full-enemy": {"text": "16"},
           # VR44: образцы runtime-текста и превью тона (в текстуре тело чипа белое)
           "badge-order": {"text": "1"}, "badge-order-p2": {"text": "2"}, "badge-attack-from": {"text": "2"},
           "team-chip-p1": {"tint": C["team1"]}, "team-chip-p2": {"tint": C["team2"]}}
# цифр нет ниже этого размера (STYLE §3.2; бейдж порядка — < 24 px только лента и блок, IC-38)
TEXT_MIN_PX = {"badge-order": 24, "badge-order-p2": 24, "badge-attack-from": 24}


def _entry(name):
    for table in (ICONS, VARIANTS, DE_ACCEPTED, CANDIDATES, ACCEPTED_VR44, VARIANTS_VR44, CANDIDATES_VR44):
        if name in table:
            return table[name]
    raise KeyError(name)


def sizes_of(name):
    """Экспортные размеры id: SIZES и его EXTRA_SIZES (по возрастанию)."""
    return tuple(sorted(set(SIZES) | set(EXTRA_SIZES.get(name, ()))))


def is_wide(name):
    return _entry(name)[2]


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
    fn, base_kw, wide = _entry(name)
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
    if Spec(size).detail == 0 or size < TEXT_MIN_PX.get(name, 0):
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


def _tinted(im, col):
    a = np.asarray(im).astype(np.float32)
    a[..., :3] *= np.array(col, dtype=np.float32)
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


def _over(*ims):
    out = ims[0].copy()
    for im in ims[1:]:
        out.alpha_composite(im)
    return out


def de012_items():
    """Лист набора DE-012 (принят 2026-10-05): (подпись, f(size) → RGBA). Мастер 1024 и 48/32/24/16; слои — как их
    видит игра; последние строки — кандидат team и ореол."""
    tf = RING_FLASH_FRAMES - 1
    return [
        ("marker-turn-ring · rim (тлеющее, в игре opacity 0,35)", lambda s: render("marker-turn-ring", s)),
        ("marker-turn-ring · flash f00 (жёлтый, 0–143 мс)", lambda s: render("marker-turn-ring", s, layer="flash", frame=0)),
        (f"marker-turn-ring · flash f{tf // 2:02d} (оранжевый)", lambda s: render("marker-turn-ring", s, layer="flash", frame=tf // 2)),
        (f"marker-turn-ring · flash f{tf:02d} (красный, к 1000 мс)", lambda s: render("marker-turn-ring", s, layer="flash", frame=tf)),
        ("resource-hp-fallen · heart (почернело, до штампа)", lambda s: render("resource-hp-fallen", s, layer="heart")),
        ("resource-hp-fallen (сердце + малый X)", lambda s: render("resource-hp-fallen", s)),
        ("marker-x-stamp (нет защиты / отменено)", lambda s: render("marker-x-stamp", s)),
        ("marker-action-slot-de · ring (обод + призрак)", lambda s: render("marker-action-slot-de", s)),
    ] + [(f"marker-action-slot-de · заполнен {a}",
          (lambda a: lambda s: _over(render("marker-action-slot-de", s), render(f"action-{a}", s)))(a))
         for a in ("attack", "defense", "maneuver", "scheme")] + [
        ("resource-hp-full · glow (пик пульса урона)",
         lambda s: _over(render("resource-hp-full", s, layer="glow"), render("resource-hp-full", s))),
        ("КАНДИДАТ marker-turn-ring-team · rim × team.p1", lambda s: _tinted(render("marker-turn-ring-team", s), C["team1"])),
        ("КАНДИДАТ marker-turn-ring-team · rim × team.p2", lambda s: _tinted(render("marker-turn-ring-team", s), C["team2"])),
    ]


def sheet_de012(path):
    """Мастер 1024 при 256 px | 48/32/24/16 цвет | серый | ×4 nearest 32/24/16 — на панели tag.background."""
    items = de012_items()
    name_w, mcell = 300, 256
    row_h = mcell + 24
    sizes_w = sum(s + 18 for s in SHEET_SIZES) + 20
    x4_w = sum(4 * (s + 4) + 12 for s in (32, 24, 16)) + 20
    W = name_w + mcell + 30 + 2 * sizes_w + x4_w + 20
    H = 60 + len(items) * row_h
    sheet = Image.new("RGBA", (W, H), SHEET_BG)
    paste(sheet, label(W, 40, "DE-012 — принято пользователем 2026-10-05 (формы Codex; кольцо — v3), внизу кандидат team: мастер 1024 (×0,25) | 48 / 32 / 24 / 16 px цвет | серый | ×4 nearest 32 / 24 / 16 — на панели tag.background", 17), 0, 8)
    for r, (title, fn) in enumerate(items):
        y = 60 + r * row_h
        paste(sheet, label(name_w, 44, title, 12), 0, y + 8)
        m = fn(MASTER).resize((mcell, mcell), Image.LANCZOS)
        paste(sheet, on_bg(m, PANEL, 0), name_w, y)
        x = name_w + mcell + 30
        for mode in ("colour", "grey"):
            for s in SHEET_SIZES:
                im = on_bg(fn(s), PANEL, 4)
                paste(sheet, grey(im) if mode == "grey" else im, x, y + 8)
                x += im.width + 10
            x += 20
        for s in (32, 24, 16):
            big = xN(on_bg(fn(s), PANEL, 2), 4)
            paste(sheet, big, x, y + 8)
            x += big.width + 12
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.convert("RGB").save(path)
    return path


def vr44_items():
    """Лист набора VR44 (VS-2 A2): (подпись, f(size) → RGBA, широкий?) — принятые VR44, варианты, кадр f04 курсора
    «занято» и кандидаты; образцы цифр и тон чипов — как на остальных листах (render_example)."""
    items = []
    for n in list(ACCEPTED_VR44) + list(VARIANTS_VR44):
        items.append((n, (lambda n: lambda s: render_example(n, s))(n), is_wide(n)))
        if n == "badge-order":
            items.append(("badge-order · слой team × team.p2 (UMG)",
                          lambda s: _over(render("badge-order", s, layer="body"),
                                          _tinted(render("badge-order", s, layer="team"), C["team2"])), False))
        if n == "cursor-busy":
            items.append(("cursor-busy · f04 (переворот 90°)", lambda s: render("cursor-busy", s, frame=4), False))
    for n in CANDIDATES_VR44:
        items.append((f"КАНДИДАТ {n}", (lambda n: lambda s: render_example(n, s))(n), is_wide(n)))
    return items


VR44_SHEET_SIZES = (48, 32, 24, 18, 16)


def sheet_vr44(path):
    """Мастер 1024 (×0,25) | 48 / 32 / 24 / 18 / 16 цвет | серый | ×4 nearest 32 / 24 / 18 — на панели tag.background."""
    items = vr44_items()
    name_w, mcell = 300, 256
    row_h = mcell + 24
    sizes_w = sum(2 * s + 18 for s in VR44_SHEET_SIZES) + 20
    x4_w = sum(4 * (2 * s + 4) + 12 for s in (32, 24, 18)) + 20
    W = name_w + 2 * mcell + 30 + 2 * sizes_w + x4_w + 20
    H = 60 + len(items) * row_h
    sheet = Image.new("RGBA", (W, H), SHEET_BG)
    paste(sheet, label(W, 40, "VR44 (VS-2 A2, A3) — принято по делегированию 2026-10-06 (A3: формы Codex IC-36 и лента «сброс»): мастер 1024 (×0,25) | 48 / 32 / 24 / 18 / 16 px цвет | серый | ×4 nearest 32 / 24 / 18 — на панели tag.background; цифры — образец runtime-текста", 17), 0, 8)
    for r, (title, fn, wide) in enumerate(items):
        y = 60 + r * row_h
        paste(sheet, label(name_w, 44, title, 12), 0, y + 8)
        m = fn(MASTER)
        m = m.resize(((2 if wide else 1) * mcell, mcell), Image.LANCZOS)
        paste(sheet, on_bg(m, PANEL, 0), name_w, y)
        x = name_w + 2 * mcell + 30
        for mode in ("colour", "grey"):
            for sz in VR44_SHEET_SIZES:
                im = on_bg(fn(sz), PANEL, 4)
                paste(sheet, grey(im) if mode == "grey" else im, x, y + 8)
                x += 2 * sz + 18
            x += 20
        for sz in (32, 24, 18):
            big = xN(on_bg(fn(sz), PANEL, 2), 4)
            paste(sheet, big, x, y + 8)
            x += 4 * (2 * sz + 4) + 12
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sheet.convert("RGB").save(path)
    return path


def cursor_frames_and_hotspots(names, dirs):
    """Курсоры (IC-58…IC-61): кадры «занято» layers/cursor-busy_fNN-<px>.png (CURSOR_SIZES) и cursor-hotspots.json —
    горячая точка каждого размера sizes_of(id) в px (начало сверху слева)."""
    cur = [n for n in CURSORS if n in names]
    if not cur:
        return
    if "cursor-busy" in cur:
        for fi in range(len(CURSOR_BUSY_FRAMES)):
            for sz in CURSOR_SIZES:
                render("cursor-busy", sz, frame=fi).save(os.path.join(dirs["layers"], f"cursor-busy_f{fi:02d}-{sz}.png"))
    path = os.path.join(ROOT, "cursor-hotspots.json")
    data = {"tool": "art/imagegen/hud-icons-v3/_tools/draw_icons.py", "origin": "top-left, px of each size",
            "ue_sizes": list(CURSOR_SIZES),
            "rule": "стрелки — середина среза острия внешней кромки (keyline 2 u, miter 2), первый пиксель α ≥ 128; "
                    "cursor-busy — центр (16; 16) u; cursor-pointer — середина верхнего торца пальца (11; 2) u: первый "
                    "ряд с α = 255, x = floor((xmin + xmax + 1) / 2) (IC-36 fix1, ВР-VS2-02)", "cursors": {}}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data["cursors"] = json.load(f).get("cursors", {})
    for n in cur:
        data["cursors"][n] = {str(sz): cursor_hotspot(n, sz) for sz in sizes_of(n)}
        if n == "cursor-busy":
            data["cursors"][n]["frames"] = [{"index": i, "angle": a} for i, a in CURSOR_BUSY_FRAMES]
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


# ------------------------------------------------------------------------------------------------ лист приёмки (IC-33)
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(ROOT)))
ACCEPT_BGS = (("card.navy", TOKENS["card.navy"]), ("card.cream", TOKENS["card.cream"]), ("board grey", "#808080"))


def _visual_sheet():
    """Цветовые преобразования листов цикла (tools/art/visual/sheet.py): серый Rec.709 и дейтеранопия Machado 2009
    (severity 1,0, линейный sRGB) — один источник для всех листов приёмки."""
    import importlib.util
    path = os.path.join(REPO_ROOT, "tools", "art", "visual", "sheet.py")
    spec = importlib.util.spec_from_file_location("visual_sheet", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def accept_sizes(name):
    """Рабочие размеры листа приёмки: 18/24/32/48, у бейджей L6 ещё 16 и 21."""
    if name in ACCEPT_OWN:
        return ACCEPT_OWN[name]
    extra = ACCEPT_L6_SIZES if name in L6_BADGES else ()
    return tuple(sorted(set(ACCEPT_SIZES) | set(extra)))


def sheet_accept(name, path, vs=None):
    """Лист приёмки одного id (02 §13.2): мастер 1024 (×0,25 на листе) и рабочие размеры из вектора ×4 nearest; строки —
    цвет | серый Rec.709 | дейтеранопия на каждом из фонов card.navy, card.cream, #808080."""
    vs = vs or _visual_sheet()
    wide = is_wide(name)
    sizes = accept_sizes(name)
    master = render_example(name, MASTER)  # образцы цифр — только на листах (числа в текстуры не печатаются)
    mview = master.resize((256 * (2 if wide else 1), 256), Image.LANCZOS)
    smalls = [(s, xN(render_example(name, s), 4)) for s in sizes]
    name_w, pad, row_h = 300, 16, 256 + 16
    W = name_w + mview.width + pad + sum(im.width + pad for _, im in smalls) + pad
    W = max(W, 1100)
    H = 84 + 24 + len(vs.MODES) * len(ACCEPT_BGS) * (row_h + 8)
    sheet = Image.new("RGBA", (W, H), SHEET_BG)
    paste(sheet, label(W, 30, f"{name} — лист приёмки (IC-33, 02 §13.2): мастер 1024 (×0,25) | " +
                       " / ".join(f"{s}" for s in sizes) + " px из вектора ×4 nearest", 15), 0, 6)
    paste(sheet, label(W, 26, "цвет | серый Rec.709 | дейтеранопия (Machado 2009, severity 1,0) на card.navy, card.cream, "
                       "#808080; числа — образец runtime-текста, при ≤ 20 px не рисуются", 13), 0, 38)
    x = name_w + mview.width + pad
    for s, im in smalls:
        paste(sheet, label(im.width, 20, f"{s} px", 12, align="center"), x, 80)
        x += im.width + pad
    y = 108
    for mode in vs.MODES:
        for bg_name, bg_hex in ACCEPT_BGS:
            bg = tuple(int(bg_hex[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
            row = Image.new("RGBA", (W - name_w, row_h), bg)
            paste(row, mview, 0, (row_h - mview.height) // 2)
            x = mview.width + pad
            for _, im in smalls:
                paste(row, im, x, (row_h - im.height) // 2)
                x += im.width + pad
            row = vs.apply_mode(row, mode).convert("RGBA")
            paste(sheet, label(name_w, 44, f"{mode} · {bg_name}", 13), 0, y + row_h // 2 - 22)
            paste(sheet, row, name_w, y)
            y += row_h + 8
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    sheet.convert("RGB").save(path)
    return {"id": name, "file": os.path.basename(path), "sizes": list(sizes), "modes": list(vs.MODES),
            "backgrounds": [f"{n} {h}" for n, h in ACCEPT_BGS], "wide": wide}


def sheets_accept(names, out_dir):
    """--sheet accept: accept-<id>.png на каждый id и accept.json (что на листах)."""
    vs = _visual_sheet()
    out = []
    for n in names:
        _entry(n)  # неизвестный id — KeyError до записи файлов
    for n in names:
        out.append(sheet_accept(n, os.path.join(out_dir, f"accept-{n}.png"), vs))
        print("sheet", out[-1]["file"], out[-1]["sizes"])
    with open(os.path.join(out_dir, "accept.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"tool": "art/imagegen/hud-icons-v3/_tools/draw_icons.py --sheet accept", "gray": "Rec.709 luma",
                   "deuteranopia": "Machado, Oliveira, Fernandes 2009, severity 1.0, linear RGB", "sheets": out},
                  f, ensure_ascii=False, indent=1)
    return out


# ------------------------------------------------------------------------------------------------ сборка
def build(names=None, review_dir=None):
    names = names or ALL
    dirs = {d: os.path.join(ROOT, d) for d in ("masters", "sizes", "layers", "sheets")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    manifest = {"revision": "hud-icons-v3", "unit_px": MASTER // U, "sizes": list(SIZES), "files": {}}
    extra = {n: list(EXTRA_SIZES[n]) for n in names if n in EXTRA_SIZES}
    if extra:
        manifest["extra_sizes"] = extra
    audits = {}
    for n in names:
        im = render(n, MASTER, **MASTER_KW.get(n, {}))
        p = os.path.join(dirs["masters"], f"{n}.png")
        im.save(p)
        audits[n] = audit(n, im)
        for s in sizes_of(n):
            render(n, s).save(os.path.join(dirs["sizes"], f"{n}-{s}.png"))
        for layer in LAYERS.get(n, ()):
            render(n, MASTER, layer=layer).save(os.path.join(dirs["layers"], f"{n}_{layer}.png"))
            for s in sizes_of(n):
                render(n, s, layer=layer).save(os.path.join(dirs["layers"], f"{n}_{layer}-{s}.png"))
            for fi, kw in enumerate(FLIPBOOKS.get((n, layer), ())):
                render(n, MASTER, layer=layer, **kw).save(os.path.join(dirs["layers"], f"{n}_{layer}_f{fi:02d}.png"))
                for s in sizes_of(n):
                    render(n, s, layer=layer, **kw).save(os.path.join(dirs["layers"], f"{n}_{layer}_f{fi:02d}-{s}.png"))
        print("ok", n, im.size, audits[n].get("margin_px"), "body%", audits[n].get("glyph_area_pct_of_body"), "seam", audits[n].get("seam_px"))
    show = [n for n in ORDER_ACCEPTED if n in names] + [n for n in ("action-attack-token-glyphmask",) + tuple(VARIANTS)
                                                         + tuple(VARIANTS_VR44) if n in names]
    sheet_masters(show, os.path.join(dirs["sheets"], "sheet-masters.png"))
    sheet_sizes(show, os.path.join(dirs["sheets"], "sheet-sizes.png"))
    sheet_context_panel([n for n in ORDER_ACCEPTED if n in names] + [v for v in ("resource-hp-full-enemy",) if v in names],
                        os.path.join(dirs["sheets"], "sheet-context-panel.png"))
    if all(n in names for n in list(DE_ACCEPTED) + list(CANDIDATES)):
        sheet_de012(os.path.join(dirs["sheets"], "de012", "sheet-de012.png"))
    vr44 = [n for n in CANDIDATES_VR44 if n in names]
    if vr44:  # IC-33: кандидаты VR44 — свой лист приёмки, не листы принятого набора
        sheets_accept(vr44, os.path.join(dirs["sheets"], "vr44"))
    cursor_frames_and_hotspots(names, dirs)
    if all(n in names for n in list(ACCEPTED_VR44) + list(VARIANTS_VR44) + list(CANDIDATES_VR44)):
        sheet_vr44(os.path.join(dirs["sheets"], "vr44", "sheet-vr44.png"))  # VS-2 A2: строка каждой карточки
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
    if "--sheet" in args:
        # IC-33: python draw_icons.py --sheet accept <id>[,<id>...] <dir>  — только листы, ничего в репозитории не пишет
        i = args.index("--sheet")
        if len(args) < i + 4 or args[i + 1] != "accept":
            sys.exit("usage: draw_icons.py --sheet accept <id>[,<id>...] <dir>")
        os.makedirs(args[i + 3], exist_ok=True)
        sheets_accept([x for x in args[i + 2].split(",") if x], args[i + 3])
        sys.exit(0)
    only = None
    review = None
    if "--only" in args:
        only = args[args.index("--only") + 1].split(",")
    if "--review" in args:
        review = args[args.index("--review") + 1]
    build(only, review)
