#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Вычислитель движения значков по контракту icon-motion.json — эталон для FS08IconMotion (UE).

Чистые функции времени: поза = f(контракт, история команд, t). Случайности нет.
Модель описана в шапке motion_contract.py и в `rules` контракта; C++-порт обязан совпадать с этим файлом
(автотест Unmatched.S08.IconMotion.Golden сравнивает с icon-motion-golden.json, который пишет golden()).

    python icon_motion.py --golden     # пишет docs/unreal/contracts/hud/icon-motion-golden.json
"""
from __future__ import annotations

import io
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
CONTRACT = os.path.join(REPO, "docs", "unreal", "contracts", "hud", "icon-motion.json")
GOLDEN = os.path.join(REPO, "docs", "unreal", "contracts", "hud", "icon-motion-golden.json")

PROPS = ("scale", "scale_x", "scale_y", "tx", "ty", "rotate", "opacity", "frame")
REST = {"scale": 1.0, "scale_x": 1.0, "scale_y": 1.0, "tx": 0.0, "ty": 0.0, "rotate": 0.0, "opacity": 1.0, "frame": 0.0}
GOLDEN_STEP_MS = 25


def load_contract(path=CONTRACT):
    with io.open(path, encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------------------------------------ кривые и ключи
def ease(name, x):
    x = 0.0 if x < 0.0 else 1.0 if x > 1.0 else x
    if name == "linear":
        return x
    if name == "constant":
        return 0.0
    if name == "ease_in_quad":
        return x * x
    if name == "ease_out_quad":
        return 1.0 - (1.0 - x) * (1.0 - x)
    if name == "ease_out_cubic":
        return 1.0 - (1.0 - x) ** 3
    if name == "ease_in_out_cubic":
        return 4.0 * x ** 3 if x < 0.5 else 1.0 - (-2.0 * x + 2.0) ** 3 / 2.0
    raise ValueError(name)


def eval_keys(keys, t, start):
    """keys: [[t, v|None, ease], ...] по возрастанию t (равные t — скачок). None → start."""
    def val(k):
        return start if k[1] is None else float(k[1])

    if t <= keys[0][0]:
        return val(keys[0])
    i = 0
    for j in range(len(keys)):
        if keys[j][0] <= t:
            i = j
        else:
            break
    if i == len(keys) - 1:
        return val(keys[i])
    k0, k1 = keys[i], keys[i + 1]
    if k0[2] == "constant" or k1[0] <= k0[0]:
        return val(k0)
    x = (t - k0[0]) / (k1[0] - k0[0])
    a, b = val(k0), val(k1)
    return a + (b - a) * ease(k0[2], x)


# ------------------------------------------------------------------------------------------------ аниматор
class Play:
    __slots__ = ("name", "t0", "dur", "kind", "hold", "tracks", "pivot", "start", "seq")

    def __init__(self, name, t0, anim, reduced, seq=0):
        branch = anim.get("reduced") if reduced else None
        self.name = name
        self.t0 = float(t0)
        self.kind = anim["kind"]
        self.hold = bool(anim.get("hold"))
        self.dur = float((branch or anim)["duration_ms"])
        self.tracks = (branch or anim)["tracks"]
        self.pivot = anim.get("pivot_u", {})
        self.start = {}
        self.seq = seq


class Animator:
    """Состояние одного значка. Команды: play(name, t). Поза: pose(t) → {target: {prop: value}}, visible."""

    def __init__(self, contract, icon, reduced=False):
        base_icon = contract.get("variants", {}).get(icon, icon)
        self.d = contract["icons"][base_icon]
        self.icon = icon
        self.reduced = reduced
        self.targets = ["all"] + [l["id"] for l in self.d["layers"]]
        self.rest = {"all": dict(REST)}
        for l in self.d["layers"]:
            r = dict(REST)
            r.update(l.get("rest", {}))
            self.rest[l["id"]] = r
        self.base = None          # Play (enter / loop / exit)
        self.events = []          # Play (event), по времени старта
        self.hidden_from = None   # после exit
        self.shown = False
        self.seq = 0              # порядок команд: при равном t0 побеждает сыгранная позже

    # -------------------------------------------------------------------- команды
    def play(self, name, t):
        anim = self.d["anims"][name]
        self.seq += 1
        p = Play(name, t, anim, self.reduced, self.seq)
        needs = {(tr["target"], tr["prop"]) for tr in p.tracks if any(k[1] is None for k in tr["keys"])}
        if needs:
            cur, _ = self.pose(t)
            p.start = {tn: cur["pose"][tn[0]][tn[1]] for tn in needs}
        if p.kind == "event":
            covered = {(tr["target"], tr["prop"]) for tr in p.tracks}
            keep = []
            for e in self.events:
                done = t - e.t0 >= e.dur
                mine = {(tr["target"], tr["prop"]) for tr in e.tracks}
                # закончившееся событие больше не нужно, если новое перекрывает все его дорожки; удержанное (hold)
                # снимает только новое удержанное — короткое (tap) пройдёт поверх и вернёт его значение
                if done and mine <= covered and (not e.hold or p.hold):
                    continue
                keep.append(e)
            self.events = keep + [p]
        else:
            self.base = p
            if p.kind == "enter":
                self.shown = True
                self.hidden_from = None
                self.events = []
            if p.kind == "exit":
                # уход владеет всем: удержанные события (hover, spend) больше не перекрывают затухание; их значения
                # уже попали в start ключей None
                self.hidden_from = t + p.dur
                self.events = []

    def has(self, name):
        return name in self.d["anims"]

    # -------------------------------------------------------------------- поза
    def _base_at(self, t):
        """(Play, локальное t) действующей базовой анимации или (None, 0)."""
        b = self.base
        if b is None:
            return None, 0.0
        lt = t - b.t0
        if b.kind == "enter" and lt >= b.dur:
            if "cycle" in self.d["anims"]:
                cyc = Play("cycle", b.t0 + b.dur, self.d["anims"]["cycle"], self.reduced)
                if cyc.dur <= 0 or not cyc.tracks:
                    return None, 0.0
                return cyc, (t - cyc.t0) % cyc.dur
            return None, 0.0
        if b.kind == "loop":
            if b.dur <= 0 or not b.tracks:
                return None, 0.0
            return b, lt % b.dur
        return b, min(lt, b.dur)

    def pose(self, t):
        pose = {k: dict(v) for k, v in self.rest.items()}
        pivots = {}
        visible = self.shown and (self.hidden_from is None or t < self.hidden_from)
        if self.base is not None and self.base.kind == "enter" and t < self.base.t0:
            visible = False       # появление, назначенное на будущее (каскад stagger_ms), ещё не началось
        b, lt = self._base_at(t)
        if b:
            for tr in b.tracks:
                start = b.start.get((tr["target"], tr["prop"]), pose[tr["target"]][tr["prop"]])
                pose[tr["target"]][tr["prop"]] = eval_keys(tr["keys"], lt, start)
            pivots.update(b.pivot)
        # Действующее событие (идёт или hold) владеет своими (цель, свойство), пока его не перекроет более позднее
        # действующее событие с той же дорожкой; закончившееся без hold ничем не владеет — под ним снова видны более
        # ранний hold (hover 1,06 после tap) или база/покой. Порядок: (t0, seq) — при равном t0 побеждает сыгранное позже.
        claimed = set()
        for e in sorted((e for e in self.events if t >= e.t0), key=lambda e: (e.t0, e.seq), reverse=True):
            local = t - e.t0
            if not (local < e.dur or e.hold):
                continue
            for tr in e.tracks:
                key = (tr["target"], tr["prop"])
                if key in claimed:
                    continue
                claimed.add(key)
                start = e.start.get(key, pose[key[0]][key[1]])
                pose[key[0]][key[1]] = eval_keys(tr["keys"], min(local, e.dur), start)
            for tgt, pv in e.pivot.items():
                pivots.setdefault(tgt, pv)
        return {"pose": pose, "pivot": pivots}, visible

    def pivot_of(self, target, pivots):
        if target in pivots:
            return pivots[target]
        if target != "all":
            for l in self.d["layers"]:
                if l["id"] == target and "pivot_u" in l:
                    return l["pivot_u"]
        cw, ch = self.d["canvas_u"]
        return [cw / 2.0, ch / 2.0]


# ------------------------------------------------------------------------------------------------ демо-сценарий
def demo_schedule(contract, icon, reduced=False):
    """Сценарий галереи: [(t_ms, команда)], длительность. Одинаков для эталона и UE (S08IconGallery)."""
    base_icon = contract.get("variants", {}).get(icon, icon)
    d = contract["icons"][base_icon]

    def dur(name):
        a = d["anims"][name]
        br = a.get("reduced") if reduced else None
        return float((br or a)["duration_ms"])

    t = 0.0
    out = []
    for step in d["demo"]:
        op = step[0]
        if op == "wait":
            t += step[1]
        elif op == "cycle":
            a = d["anims"]["cycle"]
            out_period = float(a["duration_ms"])
            br = a.get("reduced") if reduced else None
            if br is not None and br.get("tracks"):
                out_period = float(br["duration_ms"])
            t += out_period * step[1]
        else:
            out.append((t, op))
            if op in ("appear", "leave"):
                t += dur(op)
    return out, t


def run_demo(contract, icon, reduced, times):
    sched, total = demo_schedule(contract, icon, reduced)
    a = Animator(contract, icon, reduced)
    res = []
    si = 0
    for t in times:
        while si < len(sched) and sched[si][0] <= t:
            a.play(sched[si][1], sched[si][0])
            si += 1
        res.append((t, a.pose(t), a))
    return res, total


# ------------------------------------------------------------------------------------------------ эталонные позы
def golden(contract=None, step=GOLDEN_STEP_MS):
    c = contract or load_contract()
    out = {"schema": "unmatched.icon-motion-golden/1", "contract_revision": c["revision"], "step_ms": step,
           "props": list(PROPS), "icons": {}}
    for icon in c["order"]:
        entry = {}
        for reduced in (False, True):
            _, total = demo_schedule(c, icon, reduced)
            times = [i * step for i in range(int(total // step) + 2)]
            rows, _ = run_demo(c, icon, reduced, times)
            samples = []
            for t, (pp, visible), anim in rows:
                pose = pp["pose"]
                row = {"t": t, "v": 1 if visible else 0, "pose": {}}
                for tgt in anim.targets:
                    row["pose"][tgt] = [round(pose[tgt][p], 5) for p in PROPS]
                    pv = anim.pivot_of(tgt, pp["pivot"])
                    row["pose"][tgt] += [round(pv[0], 4), round(pv[1], 4)]
                samples.append(row)
            entry["reduced" if reduced else "normal"] = {"total_ms": total, "samples": samples}
        out["icons"][icon] = entry
    return out


if __name__ == "__main__":
    if "--golden" in sys.argv:
        g = golden()
        with io.open(GOLDEN, "w", encoding="utf-8", newline="\n") as f:
            json.dump(g, f, ensure_ascii=False, separators=(",", ":"))
            f.write("\n")
        n = sum(len(v[k]["samples"]) for v in g["icons"].values() for k in v)
        print(GOLDEN, n, "samples")
