#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Контракт движения значков v3 — единый источник для эталона (Python) и UE.

    python art/imagegen/hud-icons-v3/_tools/motion_contract.py

Пишет:
  docs/unreal/contracts/hud/icon-motion.json      — контракт (схема unmatched.icon-motion/1);
  unreal/Unmatched/Config/S08IconMotion.json      — та же копия для рантайма UE (попадает в pak);
  docs/unreal/contracts/hud/ICON-MOTION.md        — раскадровка, сгенерированная из контракта.

Модель (её же реализует FS08IconMotion в UE):
- значок = холст 32 × 32 u (плашки 64 × 32 u, 1 u = 1/32 стороны) и слои; слой — текстура `src` (весь значок `<id>`,
  слой `<id>_<layer>`, флипбук `<id>_<layer>#NN` с `frames` кадрами), опорная точка `pivot_u`, покой `rest`;
- цель дорожки `all` — корень значка (над всеми слоями), иначе id слоя;
- свойства: scale, scale_x, scale_y (множители), tx, ty (u), rotate (градусы, по часовой), opacity (0..1), frame (индекс);
- ключ [t_ms, value, ease] — ease описывает отрезок от этого ключа к следующему; value null — «текущее значение на
  старте события»; два ключа с одним t — мгновенный скачок (берётся последний ключ с t ≤ t);
- поза слоя = покой, поверх базовая анимация (enter → loop/idle → exit), поверх событие (event) по тем же (цель, свойство);
- экранная поза: точка p слоя → R_all(R_layer(p)), где R(p) = pivot + rot(sx·(p − pivot)) + (tx, ty);
- reduced motion: у анимации своя ветка `reduced` (обычно только opacity ≤ 100 мс или статика).
"""
from __future__ import annotations

import hashlib
import io
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
OUT_JSON = os.path.join(REPO, "docs", "unreal", "contracts", "hud", "icon-motion.json")
OUT_CFG = os.path.join(REPO, "unreal", "Unmatched", "Config", "S08IconMotion.json")
OUT_MD = os.path.join(REPO, "docs", "unreal", "contracts", "hud", "ICON-MOTION.md")

EASES = {
    "linear": "линейно",
    "constant": "держать значение до следующего ключа",
    "ease_in_quad": "x²",
    "ease_out_quad": "1 − (1 − x)²",
    "ease_out_cubic": "1 − (1 − x)³",
    "ease_in_out_cubic": "x < ½: 4x³, иначе 1 − (−2x + 2)³ / 2",
}

# ------------------------------------------------------------------------------------------------ шаблоны
APPEAR = {"kind": "enter", "duration_ms": 180, "beat_ms": None, "tracks": [
    {"target": "all", "prop": "scale", "keys": [[0, 0.80, "ease_out_cubic"], [72, 1.04, "ease_in_out_cubic"], [180, 1.0, "constant"]]},
    {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [120, 1.0, "constant"]]}],
    "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
    "note": "«кладут на стол»: 0,80 → 1,04 → 1,00; кадр 0 не пустой (opacity 0,15)"}
APPEAR_FADE = {"kind": "enter", "duration_ms": 150, "beat_ms": None, "tracks": [
    {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "linear"], [150, 1.0, "constant"]]}],
    "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
    "note": "кроссфейд без масштаба (связь, спиннер)"}
LEAVE = {"kind": "exit", "duration_ms": 120, "beat_ms": None, "tracks": [
    {"target": "all", "prop": "opacity", "keys": [[0, None, "ease_in_quad"], [120, 0.0, "constant"]]},
    {"target": "all", "prop": "scale", "keys": [[0, None, "ease_in_quad"], [120, 0.92, "constant"]]}],
    "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, None, "linear"], [100, 0.0, "constant"]]}]},
    "note": "opacity → 0, scale → 0,92"}
TAP = {"kind": "event", "duration_ms": 150, "beat_ms": 50, "tracks": [
    {"target": "all", "prop": "scale", "keys": [[0, None, "ease_out_quad"], [50, 0.94, "ease_out_cubic"], [150, None, "constant"]]}],
    "reduced": {"duration_ms": 0, "tracks": []},
    "note": "смена числа на значке (цифру рисует игра): от текущего масштаба к 0,94 и обратно к нему же"}


def hold(kind_note, target, prop, to, ms, reduced_to=None, reduced_prop=None):
    """Событие «перейти к значению и держать» (hover, press, spend)."""
    red = {"duration_ms": 0, "tracks": []}
    if reduced_to is not None:
        red = {"duration_ms": 100, "tracks": [{"target": target, "prop": reduced_prop or prop,
                                                "keys": [[0, None, "linear"], [100, reduced_to, "constant"]]}]}
    return {"kind": "event", "hold": True, "duration_ms": ms, "beat_ms": None,
            "tracks": [{"target": target, "prop": prop, "keys": [[0, None, "ease_out_cubic"], [ms, to, "constant"]]}],
            "reduced": red, "note": kind_note}


def static_reduced():
    return {"duration_ms": 0, "tracks": []}


def layer(lid, src, pivot=None, rest=None, frames=None, tint=None):
    d = {"id": lid, "src": src}
    if pivot:
        d["pivot_u"] = list(pivot)
    if rest:
        d["rest"] = rest
    if frames:
        d["frames"] = frames
    if tint:
        d["tint"] = tint
    return d


def steps(period, n, deg):
    keys = [[round(i * period / n, 3), i * deg, "constant"] for i in range(n)]
    keys.append([period, n * deg, "constant"])
    return keys


# ------------------------------------------------------------------------------------------------ значки
ACTION_EVENTS = {
    "hover_in": hold("наведение: 1,06", "all", "scale", 1.06, 150),
    "hover_out": hold("уход курсора: 1,00", "all", "scale", 1.0, 150),
    "press": hold("нажатие: 0,96", "all", "scale", 0.96, 80),
    "release": hold("отпускание: обратно к 1,06", "all", "scale", 1.06, 80),
    "select": {"kind": "event", "duration_ms": 200, "beat_ms": 70, "tracks": [
        {"target": "glyph", "prop": "scale", "keys": [[0, None, "ease_out_quad"], [70, 1.12, "ease_out_cubic"], [200, None, "constant"]]}],
        "reduced": static_reduced(), "note": "действие выбрано: импульс глифа от текущего масштаба и обратно"},
    "spend": hold("действие потрачено: opacity 0,4 (02:895)", "all", "opacity", 0.4, 150, reduced_to=0.4),
    "restore": hold("действие снова доступно", "all", "opacity", 1.0, 150, reduced_to=1.0),
    "tap": TAP,
}


def action(icon):
    return {"canvas_u": [32, 32], "layers": [layer("body", f"{icon}_body"), layer("glyph", f"{icon}_glyph")],
            "anims": dict({"appear": APPEAR, "leave": LEAVE}, **ACTION_EVENTS),
            "demo": [["appear"], ["wait", 300], ["hover_in"], ["wait", 250], ["press"], ["wait", 120], ["release"],
                     ["select"], ["wait", 300], ["hover_out"], ["wait", 200], ["spend"], ["wait", 400], ["restore"],
                     ["wait", 300], ["leave"]]}


SENT_FRAMES = 12
SENT_FRAME_T = [0, 92, 183, 275, 367, 458, 550, 950, 1060, 1170, 1280, 1390]   # шаг ≈ 91 / 110 мс, без застоя на кадре 0

ICONS = {
    "state-boost": {
        "canvas_u": [32, 32], "layers": [layer("icon", "state-boost")],
        "anims": {"appear": APPEAR, "leave": LEAVE, "tap": TAP,
                  "reveal": {"kind": "event", "duration_ms": 240, "beat_ms": 80, "tracks": [
                      {"target": "all", "prop": "scale_x", "keys": [[0, None, "ease_in_quad"], [80, 0.05, "ease_out_cubic"], [160, 1.06, "ease_in_quad"], [240, 1.0, "constant"]]}],
                      "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
                      "note": "BOOST вскрыт: «переворот монеты» по X — схлопнулся ребром (удар 80) и раскрылся с перелётом"}},
        "demo": [["appear"], ["wait", 400], ["reveal"], ["wait", 400], ["tap"], ["wait", 400], ["leave"]]},
    "state-enemy": {
        "canvas_u": [32, 32], "layers": [layer("body", "state-enemy_body"), layer("glyph", "state-enemy_glyph")],
        "anims": {"appear": dict(APPEAR, beat_ms=140, tracks=APPEAR["tracks"] + [
            {"target": "glyph", "prop": "ty", "keys": [[0, -2.0, "ease_in_quad"], [140, 0.0, "constant"]]}],
            note="фигурку ставят на клетку: глиф падает 2 u, «тук» при 140"), "leave": LEAVE, "tap": TAP},
        "demo": [["appear"], ["wait", 800], ["tap"], ["wait", 400], ["leave"]]},
    "state-sent": {
        "canvas_u": [32, 32], "layers": [layer("body", "state-sent_body"),
                                         layer("glyph", "state-sent_glyph#", pivot=(16, 16), frames=SENT_FRAMES)],
        "anims": {"appear": APPEAR, "leave": LEAVE,
                  "cycle": {"kind": "loop", "duration_ms": 1500, "beat_ms": 650, "tracks": [
                      {"target": "glyph", "prop": "frame", "keys": [[t, i, "constant"] for i, t in enumerate(SENT_FRAME_T)] + [[1500, 0, "constant"]]},
                      {"target": "glyph", "prop": "rotate", "keys": [[0, 0, "constant"], [650, 0, "ease_in_out_cubic"], [950, 180, "constant"], [950, 0, "constant"], [1500, 0, "constant"]]}],
                      "reduced": static_reduced(),
                      "note": "песок пересыпается (кадры 0–6, 550 мс), переворот 650–950 (удар 650), песок снова сверху (кадры 7–11)"}},
        "demo": [["appear"], ["cycle", 2], ["leave"]]},
    "state-pending-move": {
        "canvas_u": [32, 32], "layers": [layer("body", "state-pending-move_body"),
                                         layer("glyph", "state-pending-move_glyph", pivot=(16, 16))],
        "anims": {"appear": APPEAR, "leave": LEAVE,
                  "cycle": {"kind": "loop", "duration_ms": 1200, "beat_ms": 520, "tracks": [
                      {"target": "glyph", "prop": "scale", "keys": [[0, 1.0, "constant"], [180, 1.0, "ease_in_quad"], [480, 0.86, "constant"], [520, 0.86, "ease_out_cubic"], [760, 1.0, "constant"], [1200, 1.0, "constant"]]}],
                      "reduced": static_reduced(), "note": "стрелки втягиваются и «щёлкают» наружу (удар 520)"}},
        "demo": [["appear"], ["cycle", 2], ["leave"]]},
    "state-pending-place": {
        "canvas_u": [32, 32], "layers": [layer("body", "state-pending-place_body"), layer("space", "state-pending-place_space"),
                                         layer("arrow", "state-pending-place_arrow")],
        "anims": {"appear": APPEAR, "leave": LEAVE,
                  "cycle": {"kind": "loop", "duration_ms": 1200, "beat_ms": 600, "tracks": [
                      {"target": "arrow", "prop": "ty", "keys": [[0, 0.0, "ease_out_quad"], [300, -2.4, "ease_in_quad"], [600, 0.0, "constant"], [1200, 0.0, "constant"]]}],
                      "reduced": static_reduced(), "note": "стрелка подпрыгивает и опускается на клетку («тук» 600)"}},
        "demo": [["appear"], ["cycle", 2], ["leave"]]},
    "state-hint": {
        "canvas_u": [64, 32], "layers": [layer("body", "state-hint_body"), layer("glyph", "state-hint_glyph", pivot=(16, 16.25))],
        "anims": {"appear": {"kind": "enter", "duration_ms": 260, "beat_ms": 200, "stagger_ms": 60, "tracks": [
            {"target": "all", "prop": "scale_x", "keys": [[0, 0.5, "ease_out_cubic"], [200, 1.0, "constant"]]},
            {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [120, 1.0, "constant"]]},
            {"target": "glyph", "prop": "scale", "keys": [[0, 1.0, "constant"], [200, 1.0, "ease_out_quad"], [230, 1.12, "ease_out_cubic"], [260, 1.0, "constant"]]}],
            "pivot_u": {"all": [1, 16]},
            "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "плашка растёт слева (scaleX 0,5 → 1), лампа «загорается» импульсом; каскад по рангу 0 / 60 / 120 мс (stagger_ms задаёт игра)"},
            "leave": LEAVE, "tap": TAP},
        "demo": [["appear"], ["wait", 600], ["tap"], ["wait", 400], ["leave"]]},
    "state-threat": {
        "canvas_u": [64, 32], "layers": [layer("body", "state-threat_body"), layer("glyph", "state-threat_glyph", pivot=(16, 16))],
        "anims": {"appear": {"kind": "enter", "duration_ms": 200, "beat_ms": None, "tracks": [
            {"target": "all", "prop": "scale_x", "keys": [[0, 0.5, "ease_out_cubic"], [200, 1.0, "constant"]]},
            {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [120, 1.0, "constant"]]}],
            "pivot_u": {"all": [1, 16]},
            "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "плашка растёт слева; глаз не моргает"},
            "leave": LEAVE, "tap": TAP,
            "rise": {"kind": "event", "duration_ms": 220, "beat_ms": 60, "tracks": [
                {"target": "glyph", "prop": "scale", "keys": [[0, 1.0, "ease_out_quad"], [60, 1.18, "ease_out_cubic"], [220, 1.0, "constant"]]},
                {"target": "all", "prop": "scale", "keys": [[0, 1.0, "ease_out_quad"], [60, 1.04, "ease_out_cubic"], [220, 1.0, "constant"]]}],
                "reduced": static_reduced(), "note": "угроз стало больше: глаз «вглядывается»"}},
        "demo": [["appear"], ["wait", 500], ["rise"], ["wait", 500], ["tap"], ["wait", 400], ["leave"]]},
    "state-immobilized": {
        "canvas_u": [32, 32], "layers": [layer("body", "state-immobilized_body"), layer("glyph", "state-immobilized_glyph")],
        "anims": {"appear": {"kind": "enter", "duration_ms": 260, "beat_ms": 160, "tracks": [
            {"target": "all", "prop": "scale", "keys": [[0, 0.9, "ease_out_cubic"], [100, 1.0, "constant"], [160, 1.0, "ease_out_quad"], [200, 0.95, "ease_out_cubic"], [260, 1.0, "constant"]]},
            {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [100, 1.0, "constant"]]},
            {"target": "glyph", "prop": "ty", "keys": [[0, -3.0, "ease_in_quad"], [160, 0.0, "constant"]]}],
            "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "«бросили якорь»: глиф падает 3 u, удар 160, плашка вздрагивает"},
            "leave": LEAVE, "tap": TAP},
        "demo": [["appear"], ["wait", 900], ["leave"]]},
    "action-attack": action("action-attack"),
    "action-defense": action("action-defense"),
    "action-maneuver": action("action-maneuver"),
    "action-scheme": action("action-scheme"),
    "action-attack-token": {
        "canvas_u": [32, 32], "layers": [layer("icon", "action-attack-token")],
        "anims": {"appear": {"kind": "enter", "duration_ms": 220, "beat_ms": 140, "tracks": [
            {"target": "all", "prop": "scale", "keys": [[0, 1.25, "ease_in_quad"], [140, 0.96, "ease_out_cubic"], [220, 1.0, "constant"]]},
            {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [80, 1.0, "constant"]]}],
            "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "жетон цели кладут на бойца сверху: 1,25 → 0,96 → 1,00, удар 140"},
            "leave": LEAVE,
            "cycle": {"kind": "loop", "duration_ms": 1000, "beat_ms": 0, "tracks": [
                {"target": "all", "prop": "scale", "keys": [[0, 1.0, "ease_in_out_cubic"], [500, 1.05, "ease_in_out_cubic"], [1000, 1.0, "constant"]]}],
                "reduced": static_reduced(), "note": "пульс цели 1 Гц (03 §6); reduced motion — без пульса"}},
        "demo": [["appear"], ["cycle", 3], ["leave"]]},
    "marker-status": {
        "canvas_u": [32, 32], "layers": [layer("body", "marker-status_body"), layer("team", "marker-status_team", tint="team")],
        "anims": {"appear": {"kind": "enter", "duration_ms": 220, "beat_ms": None, "tracks": [
            {"target": "all", "prop": "scale_y", "keys": [[0, 0.1, "ease_out_cubic"], [220, 1.0, "constant"]]},
            {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [100, 1.0, "constant"]]}],
            "pivot_u": {"all": [16, 1]},
            "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "лента разворачивается сверху вниз"},
            "leave": LEAVE, "tap": TAP},
        "demo": [["appear"], ["wait", 600], ["tap"], ["wait", 400], ["leave"]]},
    "loader-spinner": {
        "canvas_u": [32, 32], "layers": [layer("icon", "loader-spinner")],
        "anims": {"appear": APPEAR_FADE, "leave": LEAVE,
                  "cycle": {"kind": "loop", "duration_ms": 1000, "beat_ms": 0, "pivot_u": {"all": [16, 16]}, "tracks": [
                      {"target": "all", "prop": "rotate", "keys": steps(1000, 8, 45)}],
                      "reduced": {"duration_ms": 2000, "tracks": [{"target": "all", "prop": "rotate", "keys": steps(2000, 8, 45)}]},
                      "note": "8 ступеней по 45° (125 мс), без промежуточных кадров; reduced — ступени по 250 мс (индикатор прогресса оставлен)"}},
        "demo": [["appear"], ["cycle", 2], ["leave"]]},
    "resource-action-full": {
        "canvas_u": [32, 32], "layers": [layer("under", "resource-action-empty", rest={"opacity": 0.0}),
                                         layer("icon", "resource-action-full", pivot=(16, 16))],
        "anims": {"appear": APPEAR, "leave": LEAVE, "tap": TAP,
                  "spend": {"kind": "event", "hold": True, "duration_ms": 150, "beat_ms": 0, "tracks": [
                      {"target": "under", "prop": "opacity", "keys": [[0, 1.0, "constant"], [150, 1.0, "constant"]]},
                      {"target": "icon", "prop": "scale", "keys": [[0, 1.0, "ease_out_quad"], [150, 0.9, "constant"]]},
                      {"target": "icon", "prop": "opacity", "keys": [[0, 1.0, "ease_in_quad"], [150, 0.0, "constant"]]}],
                      "reduced": {"duration_ms": 100, "tracks": [
                          {"target": "under", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]},
                          {"target": "icon", "prop": "opacity", "keys": [[0, 1.0, "linear"], [100, 0.0, "constant"]]}]},
                      "note": "очко потрачено: светлый ромб гаснет поверх пустого (дальше игра ставит resource-action-empty)"},
                  "gain": {"kind": "event", "duration_ms": 180, "beat_ms": 120, "tracks": [
                      {"target": "under", "prop": "opacity", "keys": [[0, 1.0, "constant"], [180, 0.0, "constant"]]},
                      {"target": "icon", "prop": "scale", "keys": [[0, 0.6, "ease_out_cubic"], [120, 1.08, "ease_in_quad"], [180, 1.0, "constant"]]},
                      {"target": "icon", "prop": "opacity", "keys": [[0, 0.0, "ease_out_quad"], [100, 1.0, "constant"]]}],
                      "reduced": {"duration_ms": 100, "tracks": [{"target": "icon", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
                      "note": "очко вернулось (новый ход)"}},
        "demo": [["appear"], ["wait", 400], ["spend"], ["wait", 500], ["gain"], ["wait", 400], ["leave"]]},
    "resource-action-empty": {
        "canvas_u": [32, 32], "layers": [layer("icon", "resource-action-empty")],
        "anims": {"appear": APPEAR_FADE, "leave": LEAVE},
        "demo": [["appear"], ["wait", 800], ["leave"]]},
    "resource-card": {
        "canvas_u": [32, 32], "layers": [layer("icon", "resource-card")],
        "anims": {"appear": APPEAR, "leave": LEAVE, "tap": TAP,
                  "draw": {"kind": "event", "duration_ms": 180, "beat_ms": 180, "tracks": [
                      {"target": "all", "prop": "ty", "keys": [[0, -3.0, "ease_out_cubic"], [180, 0.0, "constant"]]},
                      {"target": "all", "prop": "scale", "keys": [[0, 1.1, "ease_out_cubic"], [180, 1.0, "constant"]]}],
                      "reduced": static_reduced(), "note": "добор карты: стопка «падает» на место, удар — приземление 180"}},
        "demo": [["appear"], ["wait", 400], ["draw"], ["wait", 400], ["tap"], ["wait", 400], ["leave"]]},
    "resource-connection-online": {
        "canvas_u": [32, 32], "layers": [layer("icon", "resource-connection-online")],
        "anims": {"appear": APPEAR_FADE, "leave": LEAVE},
        "demo": [["appear"], ["wait", 800], ["leave"]]},
    "resource-connection-reconnecting": {
        "canvas_u": [32, 32], "layers": [layer("bars", "resource-connection-reconnecting_bars"),
                                         layer("sign", "resource-connection-reconnecting_sign", pivot=(8.75, 8.75))],
        "anims": {"appear": APPEAR_FADE, "leave": LEAVE,
                  "cycle": {"kind": "loop", "duration_ms": 1200, "beat_ms": 0, "tracks": [
                      {"target": "sign", "prop": "rotate", "keys": [[0, 0.0, "linear"], [1200, 360.0, "constant"]]}],
                      "reduced": static_reduced(), "note": "круговая стрелка вращается, столбики стоят"}},
        "demo": [["appear"], ["cycle", 2], ["leave"]]},
    "resource-connection-lost": {
        "canvas_u": [32, 32], "layers": [layer("from", "resource-connection-online", rest={"opacity": 0.0}),
                                         layer("bars", "resource-connection-lost_bars"),
                                         layer("sign", "resource-connection-lost_sign", pivot=(8.75, 8.75))],
        "anims": {"appear": {"kind": "enter", "duration_ms": 180, "beat_ms": 110, "tracks": [
            {"target": "bars", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [150, 1.0, "constant"]]},
            {"target": "sign", "prop": "scale", "keys": [[0, 0.0, "ease_out_cubic"], [110, 1.08, "ease_in_quad"], [180, 1.0, "constant"]]}],
            "reduced": {"duration_ms": 100, "tracks": [
                {"target": "bars", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]},
                {"target": "sign", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "связи нет с самого начала: приглушённые столбики проявляются, красный X «штампуется» (удар 110)"},
            "appear_from_online": {"kind": "enter", "duration_ms": 180, "beat_ms": 110, "tracks": [
            {"target": "from", "prop": "opacity", "keys": [[0, 1.0, "ease_in_quad"], [150, 0.0, "constant"]]},
            {"target": "from", "prop": "tx", "keys": [[0, 0.0, "ease_out_cubic"], [150, 3.75, "constant"]]},
            {"target": "bars", "prop": "opacity", "keys": [[0, 0.0, "ease_in_quad"], [150, 1.0, "constant"]]},
            {"target": "bars", "prop": "tx", "keys": [[0, -3.75, "ease_out_cubic"], [150, 0.0, "constant"]]},
            {"target": "sign", "prop": "scale", "keys": [[0, 0.0, "ease_out_cubic"], [110, 1.08, "ease_in_quad"], [180, 1.0, "constant"]]}],
            "reduced": {"duration_ms": 100, "tracks": [
                {"target": "from", "prop": "opacity", "keys": [[0, 1.0, "linear"], [50, 0.0, "constant"]]},
                {"target": "bars", "prop": "opacity", "keys": [[0, 0.0, "constant"], [50, 0.0, "linear"], [100, 1.0, "constant"]]},
                {"target": "sign", "prop": "opacity", "keys": [[0, 0.0, "constant"], [50, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "связь пропала во время игры (вместо online): столбики online уезжают вправо (3,75 u) на место приглушённых и гаснут, X «штампуется», без мигания"},
            "leave": LEAVE},
        "demo": [["appear_from_online"], ["wait", 800], ["leave"], ["wait", 300], ["appear"], ["wait", 600], ["leave"]]},
    "resource-hp-full": {
        "canvas_u": [32, 32], "layers": [layer("under", "resource-hp-empty", rest={"opacity": 0.0}),
                                         layer("icon", "resource-hp-full", pivot=(16, 16))],
        "anims": {"appear": APPEAR, "leave": LEAVE, "tap": TAP,
                  "damage": {"kind": "event", "duration_ms": 200, "beat_ms": 60, "tracks": [
                      {"target": "all", "prop": "scale", "keys": [[0, 1.0, "ease_out_quad"], [60, 1.15, "ease_in_quad"], [200, 1.0, "constant"]]},
                      {"target": "all", "prop": "tx", "keys": [[0, 0.0, "linear"], [40, -0.8, "linear"], [80, 0.8, "linear"], [120, -0.5, "linear"], [160, 0.3, "linear"], [200, 0.0, "constant"]]}],
                      "reduced": static_reduced(), "note": "урон: сердце вздрагивает, число меняет игра; reduced — без движения"},
                  "deplete": {"kind": "event", "hold": True, "duration_ms": 200, "beat_ms": 60, "tracks": [
                      {"target": "under", "prop": "opacity", "keys": [[0, 1.0, "constant"], [200, 1.0, "constant"]]},
                      {"target": "icon", "prop": "scale", "keys": [[0, 1.0, "ease_out_quad"], [60, 1.15, "ease_in_quad"], [200, 0.0, "constant"]]},
                      {"target": "icon", "prop": "opacity", "keys": [[0, 1.0, "constant"], [60, 1.0, "ease_in_quad"], [200, 0.0, "constant"]]}],
                      "reduced": {"duration_ms": 100, "tracks": [
                          {"target": "under", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]},
                          {"target": "icon", "prop": "opacity", "keys": [[0, 1.0, "linear"], [100, 0.0, "constant"]]}]},
                      "note": "пип здоровья потерян: полное сердце 1 → 1,15 → 0 поверх пустого (hp_hit)"},
                  "heal": {"kind": "event", "duration_ms": 180, "beat_ms": 120, "tracks": [
                      {"target": "under", "prop": "opacity", "keys": [[0, 1.0, "constant"], [180, 0.0, "constant"]]},
                      {"target": "icon", "prop": "scale", "keys": [[0, 0.0, "ease_out_cubic"], [120, 1.1, "ease_in_quad"], [180, 1.0, "constant"]]},
                      {"target": "icon", "prop": "opacity", "keys": [[0, 0.0, "ease_out_quad"], [80, 1.0, "constant"]]}],
                      "reduced": {"duration_ms": 100, "tracks": [{"target": "icon", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
                      "note": "лечение: сердце наполняется"}},
        "demo": [["appear"], ["wait", 400], ["damage"], ["wait", 400], ["deplete"], ["wait", 500], ["heal"], ["wait", 400], ["leave"]]},
    "resource-hp-empty": {
        "canvas_u": [32, 32], "layers": [layer("icon", "resource-hp-empty")],
        "anims": {"appear": APPEAR_FADE, "leave": LEAVE},
        "demo": [["appear"], ["wait", 800], ["leave"]]},
}
ORDER = ["state-boost", "state-enemy", "state-sent", "state-pending-move", "state-pending-place", "state-hint",
         "state-threat", "state-immobilized", "action-attack", "action-attack-token", "action-defense", "action-maneuver",
         "action-scheme", "marker-status", "loader-spinner", "resource-action-full", "resource-action-empty",
         "resource-card", "resource-connection-online", "resource-connection-reconnecting", "resource-connection-lost",
         "resource-hp-full", "resource-hp-empty"]
VARIANT_OF = {"resource-hp-full-enemy": "resource-hp-full", "marker-status-p1": "marker-status", "marker-status-p2": "marker-status"}


def contract():
    assert list(ICONS) == ORDER or set(ICONS) == set(ORDER), sorted(set(ORDER) ^ set(ICONS))
    return {
        "schema": "unmatched.icon-motion/1",
        "revision": "icon-motion-2026-10-03b",   # b: ART-011 О-2 — знак связи (pivot 8,75; 8,75), сдвиг столбиков 3,75
        "status": "предложено",
        "source": "docs/unreal/contracts/hud/ICON-MOTION-PLAN.md; art/imagegen/hud-icons-v3/STYLE-v3.md §7; генератор art/imagegen/hud-icons-v3/_tools/motion_contract.py",
        "units": {"t": "ms", "canvas": "u (32 u = сторона значка; плашки 64 × 32)", "tx/ty": "u", "rotate": "градусы по часовой",
                  "scale": "множитель", "opacity": "0..1", "frame": "индекс кадра флипбука"},
        "eases": EASES,
        "props": ["scale", "scale_x", "scale_y", "tx", "ty", "rotate", "opacity", "frame"],
        "rules": {
            "keys": "[t_ms, value|null, ease к следующему ключу]; null — значение на старте события; одинаковые t — скачок",
            "compose": "поза слоя = rest ← base (enter → loop/idle → exit) ← event; экран: R_all(R_layer(p)), R(p) = pivot + rot(s·(p − pivot)) + t",
            "reduced": "ветка reduced заменяет tracks и duration; пустые tracks — статичный кадр покоя",
            "hold": "событие с hold держит последнее значение до следующего события того же свойства",
            "budget": "≤ 3 одновременно циклящих значка в кадре; тик только у активных анимаций",
        },
        "variants": VARIANT_OF,
        "order": ORDER,
        "icons": {k: ICONS[k] for k in ORDER},
    }


def storyboard_md(c):
    lines = ["# Движение значков HUD v3: раскадровка", "",
             "Сгенерировано из контракта [`icon-motion.json`](icon-motion.json) скриптом",
             "`art/imagegen/hud-icons-v3/_tools/motion_contract.py` — не править руками. План и фазы —",
             "[ICON-MOTION-PLAN.md](ICON-MOTION-PLAN.md). Ключи и модель позы — в шапке генератора и в `rules` контракта.", "",
             "Удар — момент события в цикле, на него позже вешается звук (±40 мс). Reduced motion — ветка `reduced`.", "",
             "| Значок | Анимация | Вид | мс | Удар | Что двигается | Reduced motion |", "|---|---|---|---|---|---|---|"]
    for icon in c["order"]:
        d = c["icons"][icon]
        for name, a in d["anims"].items():
            moves = "; ".join(sorted({f"{t['target']}.{t['prop']}" for t in a["tracks"]})) or "—"
            red = a.get("reduced", {})
            rtxt = "статично" if not red.get("tracks") else "; ".join(sorted({f"{t['target']}.{t['prop']}" for t in red["tracks"]})) + f" {red.get('duration_ms')} мс"
            beat = a.get("beat_ms")
            note = a.get("note", "")
            lines.append(f"| `{icon}` | {name} | {a['kind']}{' (hold)' if a.get('hold') else ''} | {a['duration_ms']} | "
                         f"{'—' if beat is None else beat} | {moves}{' — ' + note if note else ''} | {rtxt} |")
    lines += ["", "Варианты того же id играют анимации основного значка: " +
              ", ".join(f"`{v}` → `{b}`" for v, b in c["variants"].items()) + ".", ""]
    return "\n".join(lines)


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main():
    c = contract()
    text = dump(c)
    for p in (OUT_JSON, OUT_CFG):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write(storyboard_md(c))
    print(OUT_JSON, hashlib.sha1(text.encode("utf-8")).hexdigest()[:12])
    print(OUT_CFG)
    print(OUT_MD)


if __name__ == "__main__":
    main()
