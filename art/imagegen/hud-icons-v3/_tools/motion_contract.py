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
    "spend": hold("действие потрачено: opacity 0,4 (02 §8 UI-ICON-ACTION)", "all", "opacity", 0.4, 150, reduced_to=0.4),
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
                                         layer("glow", "resource-hp-full_glow", rest={"opacity": 0.0}),
                                         layer("icon", "resource-hp-full", pivot=(16, 16))],
        "anims": {"appear": APPEAR, "leave": LEAVE, "tap": TAP,
                  "damage": {"kind": "event", "duration_ms": 1000, "beat_ms": 60, "tracks": [
                      {"target": "all", "prop": "scale", "keys": [[0, 1.0, "ease_out_quad"], [60, 1.15, "ease_in_quad"], [200, 1.0, "constant"]]},
                      {"target": "all", "prop": "tx", "keys": [[0, 0.0, "linear"], [40, -0.8, "linear"], [80, 0.8, "linear"], [120, -0.5, "linear"], [160, 0.3, "linear"], [200, 0.0, "constant"]]},
                      {"target": "glow", "prop": "opacity", "keys": [[0, 0.0, "constant"], [200, 0.0, "ease_out_quad"], [320, 1.0, "ease_in_out_cubic"], [560, 0.45, "ease_in_out_cubic"], [760, 0.85, "ease_in_quad"], [1000, 0.0, "constant"]]}],
                      "reduced": static_reduced(),
                      "note": "урон (SD-35, DE-012): 0–200 сердце вздрагивает (удар 60), 200–1000 вспышка и один пульс ореола glow (принят 2026-10-05, AB-6); число меняет игра на +80 от контакта; reduced — без движения"},
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
        "demo": [["appear"], ["wait", 400], ["damage"], ["wait", 1200], ["deplete"], ["wait", 500], ["heal"], ["wait", 400], ["leave"]]},
    "resource-hp-empty": {
        "canvas_u": [32, 32], "layers": [layer("icon", "resource-hp-empty")],
        "anims": {"appear": APPEAR_FADE, "leave": LEAVE},
        "demo": [["appear"], ["wait", 800], ["leave"]]},
}
# ------------------------------------------------------------------------------------------------ набор DE-012
# W-15 арт (ICON-MOTION.md, раздел DE; 01 F-07, F-09, F-12; 02 SD-34…SD-38). Числа — из 01. Арт-приёмка пользователя
# 2026-10-05 (01-decisions, «Лист A/B DE-028 — ответ пользователя»): тёплое кольцо, павшее сердце, штамп и трекер DE —
# принятый набор (`accepted_de012`, формы Codex у сердца, штампа и слота); кольцо цвета команды остаётся кандидатом —
# только галерея -S08IconGallery, HUD его не использует (pytest test_candidates_are_gallery_only).
RING_FLASH_FRAMES = 7     # = draw_icons.RING_FLASH_FRAMES: жёлтый (f00) → оранжевый (f03) → красный (f06)
RING_REST_OPACITY = 0.35  # тлеющее кольцо весь ход (01 F-07, «Резолюция» п. 6)


def turn_ring(icon, flash_frames):
    """Кольцо хода: rim — тлеющий обод (покой 0,35), flash — вспышка 1000 мс (флипбук цвета или цвет команды)."""
    team = None if flash_frames else "team"
    tracks = [
        {"target": "flash", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [120, 1.0, "ease_in_quad"], [1000, 0.0, "constant"]]},
        {"target": "rim", "prop": "opacity", "keys": [[0, 0.0, "linear"], [1000, RING_REST_OPACITY, "constant"]]}]
    if flash_frames:
        tracks.append({"target": "flash", "prop": "frame",
                       "keys": [[round(i * 1000 / flash_frames, 3), i, "constant"] for i in range(flash_frames)]
                       + [[1000, flash_frames - 1, "constant"]]})
    return {
        "canvas_u": [32, 32],
        "layers": [layer("rim", f"{icon}_rim", rest={"opacity": RING_REST_OPACITY}, tint=team),
                   layer("flash", f"{icon}_flash#" if flash_frames else f"{icon}_flash", rest={"opacity": 0.0},
                         frames=flash_frames or None, tint=team)],
        "anims": {
            "appear": {"kind": "enter", "duration_ms": 1000, "beat_ms": 0, "tracks": tracks,
                       "reduced": {"duration_ms": 100, "tracks": [
                           {"target": "rim", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, RING_REST_OPACITY, "constant"]]}]},
                       "note": "старт хода стороны (CUE-015, 01 F-07): обод целиком вспыхивает "
                               + ("жёлтый → оранжевый → красный" if flash_frames else "цветом команды С-11")
                               + " за 1000 мс и гаснет в тлеющее кольцо 0,35 до конца хода; ввод не блокирует; reduced — статичное кольцо 0,35"},
            "leave": {"kind": "exit", "duration_ms": 120, "beat_ms": None, "tracks": [
                {"target": "all", "prop": "opacity", "keys": [[0, None, "ease_in_quad"], [120, 0.0, "constant"]]}],
                "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, None, "linear"], [100, 0.0, "constant"]]}]},
                "note": "ход перешёл к другой стороне: opacity → 0 без масштаба"}},
        "demo": [["appear"], ["wait", 1500], ["leave"]]}


CANDIDATE_ICONS = {
    "marker-turn-ring": turn_ring("marker-turn-ring", RING_FLASH_FRAMES),
    "marker-turn-ring-team": turn_ring("marker-turn-ring-team", 0),
    "resource-hp-fallen": {
        "canvas_u": [32, 32], "layers": [layer("heart", "resource-hp-fallen_heart"),
                                         layer("cross", "resource-hp-fallen_cross", pivot=(16, 16.4))],
        "anims": {"appear": {"kind": "enter", "duration_ms": 200, "beat_ms": 120, "tracks": [
            {"target": "cross", "prop": "scale", "keys": [[0, 0.0, "ease_out_cubic"], [120, 1.08, "ease_in_quad"], [200, 1.0, "constant"]]}],
            "reduced": {"duration_ms": 100, "tracks": [{"target": "cross", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "павший (SD-38, форма Codex): малый крест «штампуется» на почерневшее сердце, сердце неподвижно; игра запускает на +1100 от кадра контакта (01 F-09)"},
            "leave": LEAVE},
        "demo": [["appear"], ["wait", 900], ["leave"]]},
    "marker-x-stamp": {
        "canvas_u": [32, 32], "layers": [layer("sign", "marker-x-stamp", pivot=(16, 16))],
        "anims": {"appear": {"kind": "enter", "duration_ms": 200, "beat_ms": 120, "tracks": [
            {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [150, 1.0, "constant"]]},
            {"target": "sign", "prop": "scale", "keys": [[0, 0.0, "ease_out_cubic"], [120, 1.08, "ease_in_quad"], [200, 1.0, "constant"]]}],
            "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "крест-штамп (SD-37): «нет защиты» (CUE-009) / «отменено»; удар скоростью анимации не масштабируется"},
            "leave": LEAVE},
        "demo": [["appear"], ["wait", 800], ["leave"]]},
    "marker-action-slot-de": {
        "canvas_u": [32, 32], "layers": [layer("ring", "marker-action-slot-de_ring", pivot=(16, 16), rest={"opacity": 0.6}),
                                         layer("body", "action-attack_body", rest={"opacity": 0.0}),
                                         layer("glyph", "action-attack_glyph", pivot=(16, 16), rest={"opacity": 0.0})],
        "anims": {"appear": APPEAR, "leave": LEAVE,
                  "slot_pulse": {"kind": "loop", "duration_ms": 770, "beat_ms": 0, "tracks": [
                      {"target": "ring", "prop": "scale", "keys": [[0, 1.0, "ease_in_out_cubic"], [385, 1.06, "ease_in_out_cubic"], [770, 1.0, "constant"]]},
                      {"target": "ring", "prop": "opacity", "keys": [[0, 0.6, "ease_in_out_cubic"], [385, 1.0, "ease_in_out_cubic"], [770, 0.6, "constant"]]}],
                      "reduced": static_reduced(),
                      "note": "трекер DE (01 F-12, принят 2026-10-05, AB-7): пульс текущего слота, пока выбирается действие; reduced — обод без пульса"},
                  "fill": {"kind": "event", "hold": True, "duration_ms": 300, "beat_ms": 200, "tracks": [
                      {"target": "body", "prop": "opacity", "keys": [[0, 0.4, "ease_out_quad"], [300, 1.0, "constant"]]},
                      {"target": "glyph", "prop": "opacity", "keys": [[0, 0.4, "ease_out_quad"], [300, 1.0, "constant"]]},
                      {"target": "glyph", "prop": "scale", "keys": [[0, 0.8, "ease_out_cubic"], [200, 1.04, "ease_in_quad"], [300, 1.0, "constant"]]},
                      {"target": "ring", "prop": "opacity", "keys": [[0, None, "ease_out_quad"], [150, 0.0, "constant"]]}],
                      "reduced": {"duration_ms": 100, "tracks": [
                          {"target": "body", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]},
                          {"target": "glyph", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]},
                          {"target": "ring", "prop": "opacity", "keys": [[0, None, "linear"], [100, 0.0, "constant"]]}]},
                      "note": "трекер DE: «потрачено = заполнено значком типа» 0,4 → 1 за 300 мс в момент выбора (слои принятых action-<тип>; в галерее атака)"},
                  "unfill": {"kind": "event", "hold": True, "duration_ms": 150, "beat_ms": None, "tracks": [
                      {"target": "body", "prop": "opacity", "keys": [[0, None, "ease_in_quad"], [150, 0.0, "constant"]]},
                      {"target": "glyph", "prop": "opacity", "keys": [[0, None, "ease_in_quad"], [150, 0.0, "constant"]]},
                      {"target": "ring", "prop": "opacity", "keys": [[0, None, "ease_out_quad"], [150, 0.6, "constant"]]}],
                      "reduced": {"duration_ms": 100, "tracks": [
                          {"target": "body", "prop": "opacity", "keys": [[0, None, "linear"], [100, 0.0, "constant"]]},
                          {"target": "glyph", "prop": "opacity", "keys": [[0, None, "linear"], [100, 0.0, "constant"]]},
                          {"target": "ring", "prop": "opacity", "keys": [[0, None, "linear"], [100, 0.6, "constant"]]}]},
                      "note": "трекер DE: Undo — слот снова пуст (01 F-12)"}},
        "demo": [["appear"], ["slot_pulse"], ["wait", 1540], ["fill"], ["wait", 800], ["unfill"], ["wait", 500], ["leave"]]},
}
ICONS.update(CANDIDATE_ICONS)
# порядок записей в `order` прежний (23 v3, затем пять записей DE-012); принятые и кандидаты — отдельными списками
CANDIDATES = ["marker-turn-ring-team"]
ACCEPTED_DE012 = [k for k in CANDIDATE_ICONS if k not in CANDIDATES]

# IC-33 (ВР-IC14): принятые значки набора VR44 (02 §5.5) — строки IC-34, IC-38…IC-69 после ревью добавляют сюда записи
# (порядок `order`: после DE-012); кандидаты VR44 до ревью в контракт не входят — только мастера, размеры и лист
# sheets/vr44/ движка draw_icons.py.
# VS-2 A2 (IC-38…IC-56, приняты по делегированию 2026-10-06): движение — из колонок keyframes карточек. Курсоры
# (IC-58…IC-61) в контракт не входят (HB-12); вариант badge-order-p2 — в VARIANT_OF.
RIBBON_APPEAR = {"kind": "enter", "duration_ms": 220, "beat_ms": None, "tracks": [
    {"target": "all", "prop": "scale_y", "keys": [[0, 0.1, "ease_out_cubic"], [220, 1.0, "constant"]]},
    {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [100, 1.0, "constant"]]}],
    "pivot_u": {"all": [16, 1]},
    "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
    "note": "как marker-status: лента разворачивается сверху вниз"}
PLATE_APPEAR = {"kind": "enter", "duration_ms": 200, "beat_ms": None, "tracks": [
    {"target": "all", "prop": "scale_x", "keys": [[0, 0.5, "ease_out_cubic"], [200, 1.0, "constant"]]},
    {"target": "all", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [120, 1.0, "constant"]]}],
    "pivot_u": {"all": [1, 16]},
    "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
    "note": "как state-threat: плашка растёт слева"}


def static_icon(icon, note):
    """Статичный значок (чип, глиф кнопки, предупреждение): стандартные appear 180 / leave 120 — для импорта и галереи."""
    return {"canvas_u": [32, 32], "layers": [layer("icon", icon, pivot=(16, 16))],
            "anims": {"appear": dict(APPEAR, note=APPEAR["note"] + "; " + note), "leave": LEAVE},
            "demo": [["appear"], ["wait", 800], ["leave"]]}


ACCEPTED_VR44_ICONS: dict = {
    "badge-order": {
        "canvas_u": [32, 32], "layers": [layer("body", "badge-order_body"), layer("team", "badge-order_team", tint="team")],
        "anims": {"appear": dict(RIBBON_APPEAR, note="бейдж порядка у клетки (IC-38, V-04): лента разворачивается сверху вниз"),
                  "leave": LEAVE, "tap": dict(TAP, note="смена номера (цифру рисует игра, font.card cap 10,5 u, 9,5 u при двух знаках; центр — середина поля + 0,25 u)")},
        "demo": [["appear"], ["wait", 600], ["tap"], ["wait", 400], ["leave"]]},
    "badge-refuse": {
        "canvas_u": [32, 32], "layers": [layer("body", "badge-refuse_body"), layer("glyph", "badge-refuse_glyph", pivot=(16, 16))],
        "anims": {"appear": {"kind": "enter", "duration_ms": 200, "beat_ms": 120, "tracks": [
            {"target": "body", "prop": "opacity", "keys": [[0, 0.0, "linear"], [120, 1.0, "constant"]]},
            {"target": "glyph", "prop": "opacity", "keys": [[0, 0.15, "ease_out_quad"], [150, 1.0, "constant"]]},
            {"target": "glyph", "prop": "scale", "keys": [[0, 0.0, "ease_out_cubic"], [120, 1.08, "ease_in_quad"], [200, 1.0, "constant"]]}],
            "reduced": {"duration_ms": 100, "tracks": [{"target": "all", "prop": "opacity", "keys": [[0, 0.0, "linear"], [100, 1.0, "constant"]]}]},
            "note": "отказ V-08 (IC-40, CUE-004): плашка проявляется за 120, X «штампуется» как marker-x-stamp (удар 120); игра ставит leave через 230 мс от старта — всего 350 = motion.refuse.ms; без тряски"},
            "leave": LEAVE},
        "demo": [["appear"], ["wait", 30], ["leave"]]},
    "badge-conflict": {
        "canvas_u": [32, 32], "layers": [layer("body", "badge-order_body"), layer("team", "badge-order_team", tint="team"),
                                         layer("glyph", "badge-conflict_glyph")],
        "anims": {"appear": dict(RIBBON_APPEAR, note="конфликт хода V-09 (IC-41): лента с «!» разворачивается сверху вниз; держится, пока статус Conflict; без мигания"),
                  "leave": LEAVE},
        "demo": [["appear"], ["wait", 900], ["leave"]]},
    "badge-ally": {
        "canvas_u": [32, 32], "layers": [layer("body", "badge-ally_body"), layer("glyph", "badge-ally_glyph")],
        "anims": {"appear": dict(APPEAR, note="союзник проходим V-06 (IC-42): при наведении «кладут на стол»"), "leave": LEAVE},
        "demo": [["appear"], ["wait", 800], ["leave"]]},
    "badge-attack-from": {
        "canvas_u": [64, 32], "layers": [layer("body", "badge-attack-from_body"),
                                         layer("glyph", "badge-attack-from_glyph", pivot=(16, 16))],
        "anims": {"appear": dict(PLATE_APPEAR, note="«отсюда можно атаковать: N» (IC-43): плашка растёт слева"),
                  "leave": LEAVE, "tap": dict(TAP, note="смена числа (число рисует игра, font.card cap 14 u)")},
        "demo": [["appear"], ["wait", 600], ["tap"], ["wait", 400], ["leave"]]},
    "team-chip-p1": static_icon("team-chip-p1", "чип команды P1 (IC-44): статичен; тело — белая маска, тон даёт UMG (И-5)"),
    "team-chip-p2": static_icon("team-chip-p2", "чип команды P2 (IC-45): статичен; тело — белая маска, тон даёт UMG (И-5)"),
    "state-warning": static_icon("state-warning", "предупреждение (IC-47): без цикла и мигания"),
    "marker-slot-scheme": {
        "canvas_u": [32, 32], "layers": [layer("icon", "marker-slot-scheme")],
        "anims": {"appear": dict(RIBBON_APPEAR, note="лента слота «схема» (IC-50): появляется с картой, держится до её ухода"),
                  "leave": LEAVE},
        "demo": [["appear"], ["wait", 900], ["leave"]]},
    "marker-slot-boost": {
        "canvas_u": [32, 32], "layers": [layer("icon", "marker-slot-boost")],
        "anims": {"appear": dict(RIBBON_APPEAR, note="лента слота BOOST (IC-51): держится ≥ 1000 мс (SD-54)"),
                  "leave": LEAVE},
        "demo": [["appear"], ["wait", 1000], ["leave"]]},
    "ui-menu": static_icon("ui-menu", "глиф кнопки меню (IC-53): состояния даёт UUmButton"),
    "ui-close": static_icon("ui-close", "глиф «×» закрыть (IC-54): состояния даёт UUmButton"),
    "ui-step": static_icon("ui-step", "глиф «▲» (IC-56; «▼» — RenderTransform 180° в UMG): состояния даёт UUmButton"),
}
ICONS.update(ACCEPTED_VR44_ICONS)
ACCEPTED_VR44 = list(ACCEPTED_VR44_ICONS)
# IC-33 (02 §3.2 ВР-62, §5.3): экранные размеры текстур записи в UE — набор экспортов под DPI и масштаб UI вместо mip:
# 18 = 24 su при DPI 0,75 (720p), 36 = 24 su при 150 %; 24 / 32 / 48 / 64 — как раньше. Размер текстуры по экранным px
# выбирает виджет (S08IconMotion::TextureObjectPath(Src, Frame, SizePx)); импорт — tools/art/icons_v3_import.py.
UE_SIZES_DEFAULT = (18, 24, 32, 36, 48, 64)
# VS-2 A2: бейджи L6 у клетки (clamp 16…32 px, HUD-AND-ICONS §1.7) — ещё 16 и 21 (IC-38, IC-40, IC-41); чипы команд —
# набор по умолчанию (24 su при DPI 0,75…2,0 и галерея 64 px; 9 и 12 px — только лист проверки, ВР-78, ВР-VS2-15).
L6_UE_SIZES = (16, 18, 21, 24, 32, 36, 48, 64)
UE_SIZES = {"badge-order": L6_UE_SIZES, "badge-refuse": L6_UE_SIZES, "badge-conflict": L6_UE_SIZES}

ORDER = ["state-boost", "state-enemy", "state-sent", "state-pending-move", "state-pending-place", "state-hint",
         "state-threat", "state-immobilized", "action-attack", "action-attack-token", "action-defense", "action-maneuver",
         "action-scheme", "marker-status", "loader-spinner", "resource-action-full", "resource-action-empty",
         "resource-card", "resource-connection-online", "resource-connection-reconnecting", "resource-connection-lost",
         "resource-hp-full", "resource-hp-empty"] + list(CANDIDATE_ICONS) + ACCEPTED_VR44
VARIANT_OF = {"resource-hp-full-enemy": "resource-hp-full", "marker-status-p1": "marker-status", "marker-status-p2": "marker-status",
              "badge-order-p2": "badge-order"}


def contract():
    assert list(ICONS) == ORDER or set(ICONS) == set(ORDER), sorted(set(ORDER) ^ set(ICONS))
    return {
        "schema": "unmatched.icon-motion/1",
        # 2026-10-04: DE-012 — кандидаты набора DE (`candidates`), damage сердца 1000 мс с ореолом glow
        # 2026-10-05: арт-приёмка DE-012 — четыре записи в `accepted_de012`, сердце павшего на слое fallen_heart
        # 2026-10-06: IC-33 — `ue_sizes` у каждой записи (экспорты 18 / 36 под DPI и масштаб UI), список `accepted_vr44`
        # 2026-10-06 (VS-2 A2): 13 записей `accepted_vr44` (IC-38…IC-56), вариант badge-order-p2, бейджи L6 с 16 / 21
        "revision": "icon-motion-2026-10-06-vr44",
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
        "accepted_de012": ACCEPTED_DE012,
        "accepted_de012_note": "набор DE-012, принят пользователем 2026-10-05 (AB-5 тёплое кольцо, AB-7 трекер DE, AB-8 сердце павшего и штамп в форме Codex): принятый арт — по умолчанию, флаги только откатывают (AGENTS.md)",
        "candidates": CANDIDATES,
        "candidates_note": "кандидаты DE-012 до арт-приёмки пользователя (кольцо цвета команды — AB-5 выбрал тёплое): только галерея -S08IconGallery, HUD их не использует",
        "accepted_vr44": ACCEPTED_VR44,
        "accepted_vr44_note": "IC-33 (ВР-IC14): принятые после ревью строки значки набора VR44 (02 §5.5); кандидаты VR44 в контракт не входят; VS-2 A2 (2026-10-06): IC-38…IC-56 приняты по делегированию (листы docs/game-design/evidence/VISUAL/IC-NN/), курсоры IC-58…IC-61 — вне контракта (HB-12)",
        "ue_sizes_note": "IC-33 (02 §3.2 ВР-62, §5.3): экранные размеры текстур записи в UE (T_IV3_<id>_<px>, без mip); 18 и 36 — значок 24 su при DPI 0,75 и при 150 %; варианты берут набор основного значка",
        "order": ORDER,
        "icons": {k: dict(ICONS[k], ue_sizes=list(UE_SIZES.get(k, UE_SIZES_DEFAULT))) for k in ORDER},
    }


def storyboard_md(c):
    lines = ["# Движение значков HUD v3: раскадровка", "",
             "Сгенерировано из контракта [`icon-motion.json`](icon-motion.json) скриптом",
             "`art/imagegen/hud-icons-v3/_tools/motion_contract.py` — не править руками. План и фазы —",
             "[ICON-MOTION-PLAN.md](ICON-MOTION-PLAN.md). Ключи и модель позы — в шапке генератора и в `rules` контракта.",
             "Исключение — ручной раздел в конце файла (ниже маркера `MANUAL_MARKER`): генератор переносит его без изменений.", "",
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


# Всё ниже этой строки в ICON-MOTION.md пишется руками (запланированные записи до переноса в контракт, DE-007)
# и при перегенерации сохраняется как есть.
MANUAL_MARKER = "<!-- ручной раздел: motion_contract.py сохраняет всё ниже этой строки -->"


def manual_tail(path):
    """Ручной раздел существующей раскадровки (с маркером) или пустая строка."""
    if not os.path.exists(path):
        return ""
    with io.open(path, encoding="utf-8") as f:
        old = f.read()
    i = old.find(MANUAL_MARKER)
    return "" if i < 0 else "\n" + old[i:]


def dump(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"


def main():
    c = contract()
    text = dump(c)
    for p in (OUT_JSON, OUT_CFG):
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    tail = manual_tail(OUT_MD)
    with io.open(OUT_MD, "w", encoding="utf-8", newline="\n") as f:
        f.write(storyboard_md(c) + tail)
    print(OUT_JSON, hashlib.sha1(text.encode("utf-8")).hexdigest()[:12])
    print(OUT_CFG)
    print(OUT_MD)


if __name__ == "__main__":
    main()
