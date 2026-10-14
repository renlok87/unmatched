#!/usr/bin/env python3
"""Зазор «наездника»: жёсткая деталь, сидящая на другой части фигуры (ворона на плече или предплечье, щит на руке,
фонарь на поясе), против своей опоры — в покое и по кадрам клипов h2anim (пилот 3d-model-pipeline 2026-10-14: F137 —
ворона Ancient Leshen висела в 2,9 см от предплечья ещё в rest; F133 — в клипе жёсткая деталь отрывается от
деформируемой руки; ни h2_bake, ни clip_contact_check этого не меряли).

    python tools/tripo-pipeline/review/rider_gap.py --run <h2-bake run> --out <json> \
        [--fbx <SK_*.fbx того же rest, например H2LD>] [--parts <lp_uv.blend>] [--profile <bake profile>]
    python tools/tripo-pipeline/review/rider_gap.py --spec <ASSET>/build-profiles/<key>-h2anim.json --out <json> \
        [--clips Idle,HitReact] [--clip-fbx <Name>=<AM_*.fbx>]...
    общие: [--pair [NAME=]RIDER[:PERCH]]... [--designed-gap NAME=MM]... [--no-profile-pairs] [--no-scan]
           [--float-ok PART]... [--no-bone-groups] [--gap-max-mm 2.0] [--pen-max-mm 1.0] [--blender <exe>]

Части. Скелетный меш h2_bake — склейка низкополигональных частей Tripo; принадлежность вершины части берётся из рабочего
файла прогона `<run>/work/lp_uv.blend` (объекты `LP_tripo_part_N`, авторская рамка: м, −Y лицо) по положению
(KD-дерево, рамка FBX UM_FBX_v1: (x, y, z) → (−y, x, z); выбирается та рамка, где совпадение лучше; худшее совпадение — в
отчёте, пилот Leshen 2e-7 м). Клип h2anim несёт тот же меш: вершины клипа относятся к частям по их bind-координатам.
Подставка (`parts.<p>.mesh = base` профиля, иначе часть без вершин в FBX) не участвует.

Пары «деталь → опора»:
- `--pair crow_R=tripo_part_8:tripo_part_6+tripo_part_12` (номер без префикса тоже: `8:6+12`); опора `auto` (по
  умолчанию) — части (не деталь, не подставка), ближайшие к детали в rest: ближайшая и все, что не дальше её
  + 1 см (AUTO_MARGIN_M);
- из bake-профиля (`--profile`, по умолчанию `<run>/reports/run-manifest.json#profile.path`): каждая часть
  `prepare.part_offsets_m` (её и сажали на опору; F137) с опорой auto; `--no-profile-pairs` — без них. Пара CLI с той же
  деталью заменяет пару профиля.
- «Задуманный зазор» (C47, 2026-10-14): `--designed-gap NAME=5.6` — у пары NAME зазор не обязан быть ≤ порога, он
  должен держаться у задуманного: |gap − задуманный| ≤ порога зазора в rest и в каждом кадре (щит Beowulf над
  предплечьем — 5,6 мм постоянно; без этого такая пара могла только FAIL). Проникновение — как у всех пар.
Жёсткие части на одной кости (C47; профиль `rig.weights.<p>` kind rigid с одной `bone`: щит и умбон на arm_lower.L,
клинок и навершие на weapon.R) двигаются как одно тело: зазор между ними ничего не говорит о посадке. Поэтому скан
берёт их одной группой («tripo_part_2+tripo_part_18») против остальной фигуры, а опора auto (пары и скана) не берёт
части той же кости; группа, часть которой названа деталью пары, в скан не идёт. `--no-bone-groups` — прежнее
поведение (каждая жёсткая часть отдельно, соседи по кости в опоре), для повтора старых отчётов.
Скан (`--no-scan` — без него): каждая жёсткая часть профиля (`rig.weights.<p>.kind = rigid`, не подставка), не
названная парой, против всей остальной фигуры в rest: висит в воздухе (зазор > порога и не утоплена внутрь) — FAIL
(F137: деталь, которой никто не назначил опору, Tripo тоже мог сгенерировать с зазором). В клипах — зазор до её опоры
rest (опора auto) в каждом кадре, без проникновения (копьё в кулаке, рог в черепе утоплены по построению): отрыв > порога
— FAIL (F133 у детали без пары). Нарочно парящая деталь — `--float-ok tripo_part_N`.

Замер (рамка FBX, м). Состояние = rest SK или кадр клипа (скиненный меш, все вершины):
- gap_m — минимальное расстояние между поверхностями детали и опоры: вершины детали → ближайшая точка поверхности опоры
  и вершины опоры в окне детали (её рамка ± 3 см) → поверхность детали; 0, если есть проникновение;
- pen_m — глубина проникновения: вершина детали внутри опоры или вершина опоры внутри детали. «Внутри» части = нормаль
  её ближайшей грани смотрит от точки, точка ближе 2 см (PEN_EVAL_M) к её поверхности И обобщённое число оборотов
  этой части |w| ≥ 0,5 (winding_numbers). Чётность лучей не годится: части h2_bake — с открытыми петлями стыков (ворона
  плеча Leshen — 74 открытых ребра, рука — 327), и чётность давала ложные 3,02 мм в одиночных кадрах;
- others_pen_m — то же против остальных частей фигуры (когти, ствол): справка и WARN, не гейт (это столкновение клипа,
  а не посадка детали);
- в rest ещё: кости опоры у детали (доминирующая группа вершин опоры не дальше gap + 5 мм), кости детали (жёсткая —
  одна кость), таблица кандидатов опоры.

Пороги (калибровка на пилоте 2026-10-14, отчёт пишет их и основание): gap ≤ 2 мм и pen ≤ 2 мм в rest и в каждом
кадре каждого клипа. Leshen bake r3 (после part_offsets_m): ворона правого предплечья 1,60 мм, левого предплечья
1,52 мм, левого плеча — касание с утоплением лап 0,88 мм, во всех кадрах четырёх клипов те же числа; bake r2: ворона
правого предплечья 29,0 мм в rest и 18,4–29,6 мм в клипах — FAIL. Achilles bake r3: рукоять щита в кулаке — утопление
1,52 мм во всех кадрах (модель и клипы приняты), поэтому pen ≤ 2 мм, а не 1 мм.

Выход: JSON (schema unmatched.rider-gap/1) — входы с sha256, пороги, сопоставление частей, пары (rest, клипы по кадрам,
сводка, вердикт и причины), скан, предупреждения, общий вердикт.
Код выхода: 0 — PASS; 2 — FAIL (зазор или проникновение выше порога, висящая жёсткая часть); 1 — ошибка входа или
Blender. Blender — headless (`-b --factory-startup`), один процесс; ничего не сохраняется в .blend.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BLENDER_SCRIPT = HERE / "_rider_gap_blender.py"
DEFAULT_BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
SCHEMA = "unmatched.rider-gap/1"
GAP_MAX_M = 0.002   # деталь касается опоры: зазор ≤ 2 мм (Leshen r3: 1,60 / 1,52 мм — сидит; r2: 29 мм — висит)
PEN_MAX_M = 0.002   # утопление ≤ 2 мм (Leshen r3: лапы вороны плеча 0,88 мм; Achilles r3: рукоять щита в кулаке 1,52 мм)
AUTO_MARGIN_M = 0.01  # опора auto: ближайшая часть и все не дальше её + 1 см
WINDOW_M = 0.03     # вершины опоры/остальных против детали — только в рамке детали ± 3 см
PEN_EVAL_M = 0.02    # «внутри» проверяется числом оборотов только у точек ближе 2 см к поверхности части
MATCH_WARN_M = 0.001  # вершина FBX дальше 1 мм от точки своей части lp_uv.blend — WARN (меш изменён после UV?)
PART_RE = re.compile(r"^(?:tripo_part_)?(\d+)$")
CALIBRATION = ("пилот 2026-10-14. ASSET-ANCIENT-LESHEN-001 bake r3 (prepare.part_offsets_m tripo_part_8): вороны "
               "сидят — правое предплечье зазор 1,60 мм, левое предплечье 1,52 мм, левое плечо касание с утоплением "
               "лап 0,88 мм, во всех кадрах четырёх клипов h2anim-r3 те же числа; bake r2: ворона правого предплечья "
               "29,0 мм в rest и 18,4–29,6 мм в клипах h2anim (вето D приёмки клипа HitReact r1) — FAIL. "
               "ASSET-ACHILLES-001 bake r3: щит (жёстко arm_lower.L) — рукоять в кулаке, утопление 1,52 мм в rest и "
               "во всех кадрах h2anim-r3, модель и клипы приняты — поэтому порог проникновения 2 мм, а не 1 мм")


class InputError(Exception):
    pass


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def repo_rel(p) -> str:
    p = Path(p).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def part_name(token: str) -> str:
    """`8` | `tripo_part_8` → `tripo_part_8`; иное имя части — как есть (непустое, без пробелов)."""
    t = token.strip()
    m = PART_RE.match(t)
    if m:
        return "tripo_part_%d" % int(m.group(1))
    if not t or re.search(r"[\s:=+,]", t):
        raise ValueError("часть %r: нужен номер или tripo_part_N" % token)
    return t


def parse_pair(text: str) -> dict:
    """`[NAME=]RIDER[+RIDER…][:PERCH[+PERCH…]|:auto]` → {name, rider[], perch[] | None (auto), source: cli}."""
    s = text.strip()
    name = None
    if "=" in s:
        name, s = s.split("=", 1)
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.\-]+", name or ""):
            raise ValueError("пара %r: имя — буквы, цифры, _ . -" % text)
    rider_s, _, perch_s = s.partition(":")
    rider = [part_name(t) for t in rider_s.split("+") if t.strip()]
    if not rider:
        raise ValueError("пара %r: нет детали" % text)
    perch = None
    if perch_s.strip() and perch_s.strip().lower() != "auto":
        perch = [part_name(t) for t in perch_s.split("+") if t.strip()]
        if set(perch) & set(rider):
            raise ValueError("пара %r: часть и деталь, и опора" % text)
    return {"name": name or "+".join(rider), "rider": rider, "perch": perch, "source": "cli"}


def profile_pairs(profile: dict | None) -> list:
    """Пары из bake-профиля: каждая часть prepare.part_offsets_m — деталь с опорой auto (её и сажали на опору)."""
    prep = (profile or {}).get("prepare")
    offs = prep.get("part_offsets_m") if isinstance(prep, dict) else None
    if not isinstance(offs, dict):
        return []
    return [{"name": n, "rider": [n], "perch": None, "source": "profile prepare.part_offsets_m"}
            for n in sorted(offs, key=part_sort_key)]


def merge_pairs(cli: list, prof: list) -> list:
    """Пары CLI + пары профиля; пара профиля с деталью, уже названной в CLI, отбрасывается. Имена уникальны."""
    named = {p for pr in cli for p in pr["rider"]}
    out = list(cli) + [pr for pr in prof if not set(pr["rider"]) & named]
    seen = set()
    for pr in out:
        if pr["name"] in seen:
            raise ValueError("пара %s названа дважды" % pr["name"])
        seen.add(pr["name"])
    return out


def part_sort_key(name: str):
    m = re.search(r"(\d+)$", name)
    return (0, int(m.group(1)), name) if m else (1, 0, name)


def base_parts(profile: dict | None) -> list:
    parts = (profile or {}).get("parts") or {}
    return sorted((n for n, v in parts.items() if isinstance(v, dict) and v.get("mesh") == "base"), key=part_sort_key)


def rigid_parts(profile: dict | None) -> dict:
    """{часть: кость} жёстких частей rig.weights (kind rigid), кроме подставки."""
    weights = ((profile or {}).get("rig") or {}).get("weights") or {}
    base = set(base_parts(profile))
    return {n: v.get("bone") for n, v in sorted(weights.items(), key=lambda kv: part_sort_key(kv[0]))
            if isinstance(v, dict) and v.get("kind") == "rigid" and n not in base}


def bone_groups(rigid: dict) -> dict:
    """{часть: [все жёсткие части той же кости, по порядку]} (C47): щит и умбон на arm_lower.L — одно тело."""
    by_bone = {}
    for p, b in rigid.items():
        if b:
            by_bone.setdefault(b, []).append(p)
    return {p: sorted(by_bone.get(b, [p]), key=part_sort_key) if b else [p] for p, b in rigid.items()}


def scan_units(rigid: dict, pairs: list, grouped: bool = True) -> list:
    """Единицы скана: [{name, parts, bone}]. grouped — жёсткие части одной кости одной группой (C47), группа с деталью
    какой-либо пары не сканируется; иначе (--no-bone-groups) — по части, как раньше (части пар выпадают поштучно)."""
    named = {p for pr in pairs for p in pr["rider"]}
    if not grouped:
        return [{"name": p, "parts": [p], "bone": b} for p, b in rigid.items() if p not in named]
    groups, seen, out = bone_groups(rigid), set(), []
    for p, b in rigid.items():
        g = groups[p]
        if p in seen:
            continue
        seen.update(g)
        if set(g) & named:
            continue
        out.append({"name": "+".join(g), "parts": g, "bone": b})
    return out


def parse_designed(items, pairs: list) -> dict:
    """`--designed-gap NAME=MM` → {имя пары: зазор, м}. Пара должна быть среди пар (CLI или профиля), зазор ≥ 0."""
    names = {pr["name"] for pr in pairs}
    out = {}
    for it in items or []:
        if "=" not in it:
            raise ValueError("--designed-gap %r: нужно ИМЯ=мм" % it)
        n, v = (x.strip() for x in it.split("=", 1))
        if n not in names:
            raise ValueError("--designed-gap %s: нет такой пары (есть %s)" % (n, ", ".join(sorted(names)) or "нет"))
        mm = float(v)
        if mm < 0:
            raise ValueError("--designed-gap %s: зазор ≥ 0 мм" % n)
        out[n] = mm / 1e3
    return out


def part_roles(profile: dict | None) -> dict:
    return {n: v.get("role") for n, v in ((profile or {}).get("parts") or {}).items()
            if isinstance(v, dict) and v.get("role")}


def auto_perch(dist_by_part: dict, margin: float = AUTO_MARGIN_M) -> list:
    """Опора auto: части с расстоянием до детали ≤ ближайшее + margin (по возрастанию расстояния)."""
    known = {p: d for p, d in dist_by_part.items() if d is not None}
    if not known:
        return []
    lim = min(known.values()) + margin
    return [p for p, d in sorted(known.items(), key=lambda kv: (kv[1], part_sort_key(kv[0]))) if d <= lim]


def fan_triangles(polys) -> list:
    """Полигоны (кортежи индексов вершин) → треугольники веером [(a, b, c), …]."""
    return [(f[0], f[k], f[k + 1]) for f in polys for k in range(1, len(f) - 1)]


def winding_number(point, tris) -> float:
    """Обобщённое число оборотов (Jacobson 2013) точки относительно треугольников tris (k×3×3): сумма телесных углов
    / 4π (формула Van Oosterom–Strackee). Внутри замкнутой поверхности ±1, снаружи 0; у незамкнутой части (открытые
    петли стыков h2_bake) — плавно, ~0,5 у самой дыры: устойчивее чётности лучей, которая на открытой части
    ошибается целиком (пилот Leshen: ворона плеча, 74 открытых ребра — ложные 3,02 мм в одиночных кадрах)."""
    import numpy as np

    return float(winding_numbers([point], tris)[0])


def winding_numbers(points, tris, chunk_elems: int = 2_000_000):
    """winding_number для многих точек сразу (numpy, кусками по ≤ chunk_elems пар точка × треугольник)."""
    import numpy as np

    pts = np.asarray(points, dtype=float).reshape(-1, 3)
    t = np.asarray(tris, dtype=float).reshape(-1, 3, 3)
    out = np.zeros(len(pts))
    if not len(t) or not len(pts):
        return out
    step = max(1, chunk_elems // len(t))
    for s in range(0, len(pts), step):
        q = t[None, :, :, :] - pts[s:s + step, None, None, :]          # Q × T × 3 × 3
        a, b, c = q[:, :, 0], q[:, :, 1], q[:, :, 2]
        la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
        det = np.einsum("qtj,qtj->qt", a, np.cross(b, c))
        den = (la * lb * lc + np.einsum("qtj,qtj->qt", a, b) * lc + np.einsum("qtj,qtj->qt", b, c) * la
               + np.einsum("qtj,qtj->qt", c, a) * lb)
        out[s:s + step] = np.arctan2(det, den).sum(axis=1) * 2.0 / (4.0 * np.pi)
    return out


def state_flags(meas: dict, gap_max: float, pen_max: float, designed: float | None = None) -> list:
    """Нарушения одного состояния (rest или кадр): ['gap 2.900 mm > 2.0', 'pen …']. designed — задуманный зазор пары
    (C47): тогда нарушение — отход зазора от задуманного больше порога зазора в любую сторону."""
    out = []
    if meas.get("gap_m") is None:
        out.append("нет замера (пустая деталь или опора)")
        return out
    if designed is not None:
        if abs(meas["gap_m"] - designed) > gap_max + 1e-9:
            out.append("зазор %.2f мм вне задуманного %.2f ± %.1f" % (meas["gap_m"] * 1e3, designed * 1e3,
                                                                     gap_max * 1e3))
    elif meas["gap_m"] > gap_max + 1e-9:
        out.append("зазор %.2f мм > %.1f" % (meas["gap_m"] * 1e3, gap_max * 1e3))
    if (meas.get("pen_m") or 0.0) > pen_max + 1e-9:
        out.append("проникновение %.2f мм > %.1f" % (meas["pen_m"] * 1e3, pen_max * 1e3))
    return out


def clip_summary(rows: list) -> dict:
    """Сводка кадров клипа: наибольший зазор и проникновение (с кадром), наименьший зазор, наибольшее
    проникновение остальных частей; lift_m — рост зазора против кадра 0."""
    good = [r for r in rows if r.get("gap_m") is not None]
    if not good:
        return {"frames": len(rows), "measured": 0}
    g = max(good, key=lambda r: r["gap_m"])
    p = max(good, key=lambda r: r.get("pen_m") or 0.0)
    o = max(good, key=lambda r: r.get("others_pen_m") or 0.0)
    return {"frames": len(rows), "measured": len(good),
            "gap_max_m": g["gap_m"], "gap_max_frame": g["f"],
            "gap_min_m": min(r["gap_m"] for r in good),
            "lift_m": round(g["gap_m"] - good[0]["gap_m"], 6),
            "pen_max_m": p.get("pen_m") or 0.0, "pen_max_frame": p["f"],
            "others_pen_max_m": o.get("others_pen_m") or 0.0, "others_pen_max_frame": o["f"]}


def pair_verdict(pair: dict, gap_max: float, pen_max: float) -> tuple[str, list, list]:
    """(PASS|FAIL, причины, предупреждения) пары: rest и каждый кадр каждого клипа по gap/pen; проникновение остальных
    частей — предупреждение."""
    reasons, warns = [], []
    rest = pair.get("rest") or {}
    dg = pair.get("designed_gap_m")  # задуманный зазор пары (C47) или None
    reasons += ["rest: %s" % f for f in state_flags(rest, gap_max, pen_max, dg)]
    if (rest.get("others_pen_m") or 0.0) > pen_max:
        warns.append("rest: остальные части входят в деталь на %.2f мм" % (rest["others_pen_m"] * 1e3))
    for clip, c in (pair.get("clips") or {}).items():
        bad = [(r["f"], state_flags(r, gap_max, pen_max, dg)) for r in c.get("rows") or []]
        bad = [(f, fl) for f, fl in bad if fl]
        if bad:
            frames = [f for f, _ in bad]
            worst = max((r for r in c.get("rows") or [] if r["f"] in frames),
                        key=lambda r: max((abs((r.get("gap_m") or 0.0) - dg) if dg is not None
                                           else (r.get("gap_m") or 0.0)) - gap_max,
                                          (r.get("pen_m") or 0.0) - pen_max))
            reasons.append("%s: %d кадров из %d (к. %s), худший к. %d: %s"
                           % (clip, len(bad), len(c.get("rows") or []), compact_frames(frames), worst["f"],
                              "; ".join(state_flags(worst, gap_max, pen_max, dg))))
        s = c.get("summary") or {}
        if (s.get("others_pen_max_m") or 0.0) > pen_max:
            warns.append("%s: остальные части входят в деталь на %.2f мм (к. %s)"
                         % (clip, s["others_pen_max_m"] * 1e3, s.get("others_pen_max_frame")))
    return ("FAIL" if reasons else "PASS"), reasons, warns


def scan_verdict(item: dict, gap_max: float, float_ok: set) -> str:
    """Скан жёсткой части: PASS (касается в rest и в каждом кадре клипов), EMBEDDED (утоплена внутрь других частей —
    не висит), FLOAT_OK (разрешено --float-ok), FAIL (висит в rest или отрывается от опоры в клипе)."""
    if item.get("gap_m") is None:
        return "PASS"
    if item["gap_m"] > gap_max + 1e-9 and item.get("embedded"):
        return "EMBEDDED"
    clip_bad = any((s.get("gap_max_m") or 0.0) > gap_max + 1e-9 for s in (item.get("clips") or {}).values())
    if item["gap_m"] <= gap_max + 1e-9 and not clip_bad:
        return "PASS"
    parts = item.get("parts") or [item["part"]]  # группа частей одной кости (C47): разрешена, если названа любая
    return "FLOAT_OK" if item["part"] in float_ok or set(parts) & set(float_ok) else "FAIL"


def compact_frames(frames: list) -> str:
    """[0,1,2,5,7,8] → '0–2, 5, 7–8'."""
    out, start, prev = [], None, None
    for f in sorted(frames):
        if start is None:
            start = prev = f
        elif f == prev + 1:
            prev = f
        else:
            out.append(str(start) if start == prev else "%d–%d" % (start, prev))
            start = prev = f
    if start is not None:
        out.append(str(start) if start == prev else "%d–%d" % (start, prev))
    return ", ".join(out)


def build_report(raw: dict, inputs: dict, pairs: list, roles: dict, gap_max: float, pen_max: float,
                 float_ok: set) -> dict:
    """Итоговый отчёт из сырого замера Blender (raw) и входов: вердикты пар и скана, предупреждения."""
    warnings = list(raw.get("warnings") or [])
    out_pairs, failures = [], []
    for pr in pairs:
        name = pr["name"]
        rest = (raw.get("rest") or {}).get("pairs", {}).get(name)
        rec = {"name": name, "source": pr["source"], "rider": pr["rider"],
               "rider_roles": {p: roles.get(p) for p in pr["rider"]},
               "perch": (raw.get("perch") or {}).get(name, pr["perch"]),
               "perch_source": "cli" if pr["perch"] else "auto",
               "perch_roles": {p: roles.get(p) for p in ((raw.get("perch") or {}).get(name) or pr["perch"] or [])},
               "rest": rest, "clips": {}}
        if pr.get("designed_gap_m") is not None:  # только у пар с --designed-gap (C47)
            rec["designed_gap_m"] = pr["designed_gap_m"]
        for clip, c in (raw.get("clips") or {}).items():
            rows = (c.get("rows") or {}).get(name) or []
            rec["clips"][clip] = {"frames": len(rows), "summary": clip_summary(rows), "rows": rows}
        verdict, reasons, warns = pair_verdict(rec, gap_max, pen_max)
        rec.update({"verdict": verdict, "reasons": reasons})
        warnings += ["%s: %s" % (name, w) for w in warns]
        failures += ["%s: %s" % (name, r) for r in reasons]
        out_pairs.append(rec)
    scan = []
    for item in (raw.get("rest") or {}).get("scan") or []:
        parts = item.get("parts") or [item["part"]]
        role = roles.get(item["part"]) if len(parts) == 1 else \
            ("; ".join("%s: %s" % (p, roles[p]) for p in parts if roles.get(p)) or None)
        item = dict(item, role=role)
        clips = {}
        for clip, c in (raw.get("clips") or {}).items():
            rows = [r for r in ((c.get("scan_rows") or {}).get(item["part"]) or []) if r.get("gap_m") is not None]
            if rows:
                worst = max(rows, key=lambda r: r["gap_m"])
                clips[clip] = {"frames": len(rows), "gap_max_m": worst["gap_m"], "gap_max_frame": worst["f"],
                               "bad_frames": compact_frames([r["f"] for r in rows if r["gap_m"] > gap_max + 1e-9]),
                               "rows": rows}
        if clips:
            item["clips"] = clips
        v = scan_verdict(item, gap_max, float_ok)
        item["verdict"] = v
        scan.append(item)
        what = "%s (%s)" % (item["part"], role or "без роли")
        if v == "FAIL" and item["gap_m"] > gap_max + 1e-9:
            failures.append("скан: %s висит: зазор %.2f мм до %s > %.1f мм — опора и prepare.part_offsets_m "
                            "(HANDBOOK 4.2) или --pair" % (what, item["gap_m"] * 1e3, item.get("nearest_part"),
                                                         gap_max * 1e3))
        elif v == "FAIL":
            failures += ["скан: %s отрывается от %s в %s: до %.2f мм (к. %s) > %.1f мм"
                         % (what, "+".join(item.get("perch") or []), clip, s["gap_max_m"] * 1e3, s["bad_frames"],
                            gap_max * 1e3)
                         for clip, s in clips.items() if s["gap_max_m"] > gap_max + 1e-9]
        elif v == "EMBEDDED":
            warnings.append("скан: %s утоплена в %s (зазор поверхностей %.2f мм, вершины внутри) — не висит"
                            % (item["part"], item.get("nearest_part"), item["gap_m"] * 1e3))
    return {
        "schema": SCHEMA,
        "tool": "tools/tripo-pipeline/review/rider_gap.py",
        "inputs": inputs,
        "blender": raw.get("blender"),
        "frame": "мировая рамка импорта FBX UM_FBX_v1, м: +X лицо фигуры, +Y её левый бок, +Z вверх",
        "thresholds": {"gap_max_m": gap_max, "pen_max_m": pen_max, "auto_perch_margin_m": AUTO_MARGIN_M,
                       "window_m": WINDOW_M, "calibration": CALIBRATION,
                       "rule": "PASS пары: gap ≤ gap_max и pen ≤ pen_max в rest и в каждом кадре каждого клипа; "
                               "скан: жёсткая часть касается остальной фигуры в rest (gap ≤ gap_max) или утоплена в "
                               "неё, и в каждом кадре клипов зазор до её опоры rest ≤ gap_max (без проникновения)"},
        "mapping": raw.get("mapping"),
        "parts_open_edges": raw.get("parts_open_edges"),
        "pairs": out_pairs,
        "scan": scan,
        "warnings": warnings,
        "failures": failures,
        "verdict": "FAIL" if failures else "PASS",
    }


def read_json(p: Path, what: str) -> dict:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise InputError("%s %s: %s" % (what, p, e))


def resolve(a) -> dict:
    """Пути прогона: rest FBX, lp_uv.blend, bake-профиль, клипы (из спеки и --clip-fbx)."""
    spec, spec_p = None, None
    if a.spec:
        spec_p = Path(a.spec).resolve()
        spec = read_json(spec_p, "спека")
        try:
            sk = REPO / spec["target"]["sk_fbx"]
        except (KeyError, TypeError):
            raise InputError("спека %s: нет target.sk_fbx" % spec_p)
        run = Path(a.run).resolve() if a.run else sk.parent.parent
    elif a.run:
        run = Path(a.run).resolve()
        sks = sorted(p for p in (run / "export").glob("SK_*.fbx")) if (run / "export").is_dir() else []
        if a.fbx is None and len(sks) != 1:
            raise InputError("%s/export: нужен ровно один SK_*.fbx (есть %s) — укажите --fbx" % (run, [p.name for p in sks]))
        sk = sks[0] if sks else None
    else:
        raise InputError("нужен --run <h2-bake run> или --spec <h2anim spec>")
    rest = Path(a.fbx).resolve() if a.fbx else sk
    if rest is None or not rest.is_file():
        raise InputError("нет rest FBX %s" % rest)
    if a.parts:
        parts = Path(a.parts).resolve()
    else:
        cands = [run / "work" / n for n in ("lp_uv.blend", "lp_closed.blend")]
        parts = next((p for p in cands if p.is_file()), cands[0])
    if not parts.is_file():
        raise InputError("нет файла частей %s (work/ прогона удалён?) — укажите --parts <lp_uv.blend>" % parts)
    profile_p = None
    if a.profile:
        profile_p = Path(a.profile).resolve()
    else:
        man = run / "reports" / "run-manifest.json"
        if man.is_file():
            path = (read_json(man, "run-manifest").get("profile") or {}).get("path")
            if path:
                profile_p = (REPO / path).resolve()
    profile = read_json(profile_p, "bake-профиль") if profile_p is not None and profile_p.is_file() else None
    if profile_p is not None and profile is None:
        raise InputError("нет bake-профиля %s" % profile_p)
    clips = {}
    if spec is not None:
        names = list(spec.get("clips") or {})
        if a.clips:
            want = [c.strip() for c in a.clips.split(",") if c.strip()]
            bad = [c for c in want if c not in names]
            if bad:
                raise InputError("--clips %s: нет в спеке (%s)" % (bad, ", ".join(names)))
            names = want
        clip_dir = REPO / spec["run_dir"] / "export"
        for c in names:
            clips[c] = clip_dir / ("AM_%s_%s.fbx" % (spec["ue_hero"], c))
    for item in a.clip_fbx or []:
        if "=" not in item:
            raise InputError("--clip-fbx %r: нужно Имя=путь.fbx" % item)
        n, p = item.split("=", 1)
        clips[n.strip()] = Path(p).resolve()
    for n, p in clips.items():
        if not p.is_file():
            raise InputError("клип %s: нет %s" % (n, p))
    return {"run": run, "rest": rest, "parts": parts, "profile_path": profile_p, "profile": profile,
            "spec_path": spec_p, "clips": clips}


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # кириллица в Git Bash/агентах (консоль cp1251)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", help="каталог прогона h2_bake (export/SK_*.fbx, work/lp_uv.blend, reports/run-manifest.json)")
    ap.add_argument("--spec", help="спека h2anim: rest = target.sk_fbx (прогон — его каталог), клипы <run_dir>/export")
    ap.add_argument("--fbx", help="rest FBX вместо export/SK_*.fbx прогона (например H2LD того же меша)")
    ap.add_argument("--parts", help="blend с объектами LP_<часть> (по умолчанию <run>/work/lp_uv.blend)")
    ap.add_argument("--profile", help="bake-профиль (по умолчанию из <run>/reports/run-manifest.json#profile.path)")
    ap.add_argument("--clips", help="клипы спеки через запятую (по умолчанию все)")
    ap.add_argument("--clip-fbx", action="append", help="Имя=AM_*.fbx — клип вне спеки (дымовой прогон); можно много")
    ap.add_argument("--pair", action="append", help="[NAME=]RIDER[:PERCH|:auto], части через +; можно много")
    ap.add_argument("--designed-gap", action="append", default=[],
                    help="NAME=мм — задуманный зазор пары: |gap − мм| ≤ порога зазора (C47); можно много")
    ap.add_argument("--no-bone-groups", action="store_true",
                    help="прежнее поведение: жёсткие части одной кости сканируются по одной и входят в опору auto")
    ap.add_argument("--no-profile-pairs", action="store_true", help="не брать детали prepare.part_offsets_m профиля")
    ap.add_argument("--no-scan", action="store_true", help="без скана жёстких частей профиля")
    ap.add_argument("--float-ok", action="append", default=[], help="жёсткая часть, которой можно висеть (скан)")
    ap.add_argument("--gap-max-mm", type=float, default=GAP_MAX_M * 1e3)
    ap.add_argument("--pen-max-mm", type=float, default=PEN_MAX_M * 1e3)
    ap.add_argument("--out", required=True, help="JSON отчёта")
    ap.add_argument("--blender", default=DEFAULT_BLENDER)
    a = ap.parse_args(argv)
    try:
        inp = resolve(a)
        cli = [parse_pair(t) for t in a.pair or []]
        prof = [] if a.no_profile_pairs else profile_pairs(inp["profile"])
        pairs = merge_pairs(cli, prof)
        designed = parse_designed(a.designed_gap, pairs)
        for pr in pairs:
            if pr["name"] in designed:
                pr["designed_gap_m"] = designed[pr["name"]]
        float_ok = {part_name(t) for t in a.float_ok}
    except (InputError, ValueError) as e:
        print("FAIL: %s" % e, file=sys.stderr)
        return 1
    if not Path(a.blender).is_file():
        print("FAIL: нет Blender %s (--blender или env BLENDER)" % a.blender, file=sys.stderr)
        return 1
    grouped = not a.no_bone_groups
    rigid = rigid_parts(inp["profile"])
    scan = [] if a.no_scan else scan_units(rigid, pairs, grouped)
    # соседи по кости (C47): в опору auto пар и скана не идут — двигаются с деталью как одно тело
    same_bone = {p: [q for q in g if q != p] for p, g in bone_groups(rigid).items() if len(g) > 1} if grouped else {}
    if not pairs and not scan:
        print("FAIL: нечего мерить: нет пар (--pair, prepare.part_offsets_m профиля) и жёстких частей для скана",
              file=sys.stderr)
        return 1
    gap_max, pen_max = a.gap_max_mm / 1e3, a.pen_max_mm / 1e3
    out = Path(a.out).resolve()
    with tempfile.TemporaryDirectory(prefix="rider-gap-") as tmp:
        cfg = {"parts_blend": str(inp["parts"]), "rest_fbx": str(inp["rest"]),
               "clips": {k: str(v) for k, v in inp["clips"].items()},
               "pairs": [{"name": p["name"], "rider": p["rider"], "perch": p["perch"]} for p in pairs],
               "scan": scan, "same_bone": same_bone,
               "base_parts": base_parts(inp["profile"]), "auto_margin_m": AUTO_MARGIN_M,
               "window_m": WINDOW_M, "match_warn_m": MATCH_WARN_M, "pen_eval_m": PEN_EVAL_M, "raw_out": str(Path(tmp) / "raw.json")}
        (Path(tmp) / "cfg.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
        cmd = [a.blender, "-b", "--factory-startup", "--python-exit-code", "1",
               "--python", str(BLENDER_SCRIPT), "--", str(Path(tmp) / "cfg.json")]
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if r.returncode != 0 or "RIDER_GAP_RAW_OK" not in r.stdout:
            tail = "\n".join((r.stdout + r.stderr).splitlines()[-25:])
            print("FAIL: Blender завершился с кодом %s\n%s" % (r.returncode, tail), file=sys.stderr)
            return 1
        raw = json.loads((Path(tmp) / "raw.json").read_text(encoding="utf-8"))
    inputs = {
        "run": repo_rel(inp["run"]),
        "rest_fbx": {"path": repo_rel(inp["rest"]), "sha256": sha256(inp["rest"])},
        "parts_blend": {"path": repo_rel(inp["parts"]), "sha256": sha256(inp["parts"])},
        "profile": ({"path": repo_rel(inp["profile_path"]), "sha256": sha256(inp["profile_path"])}
                    if inp["profile"] is not None else None),
        "spec": {"path": repo_rel(inp["spec_path"]), "sha256": sha256(inp["spec_path"])} if inp["spec_path"] else None,
        "clips": {k: {"path": repo_rel(v), "sha256": sha256(v)} for k, v in inp["clips"].items()},
        "float_ok": sorted(float_ok, key=part_sort_key),
    }
    if grouped and same_bone:  # только если группы что-то меняют (C47); --no-bone-groups — прежний отчёт
        groups = bone_groups(rigid)
        inputs["bone_groups"] = {"+".join(groups[p]): rigid[p] for p in same_bone}
    rep = build_report(raw, inputs, pairs, part_roles(inp["profile"]), gap_max, pen_max, float_ok)
    if designed:
        rep["thresholds"]["designed_gap_rule"] = ("пара с --designed-gap: |gap − задуманный| ≤ gap_max в rest и в каждом "
                                                  "кадре, pen ≤ pen_max (C47: постоянный зазор щита к предплечью)")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    for w in rep["warnings"]:
        print("WARN: %s" % w, file=sys.stderr)
    for pr in rep["pairs"]:
        rest = pr["rest"] or {}
        clips = "; ".join("%s gap≤%.2f pen≤%.2f мм" % (c, (v["summary"].get("gap_max_m") or 0) * 1e3,
                                                    (v["summary"].get("pen_max_m") or 0) * 1e3)
                          for c, v in pr["clips"].items())
        print("PAIR %s %s → %s: rest gap %.2f мм pen %.2f мм%s%s — %s" % (
            pr["name"], "+".join(pr["rider"]), "+".join(pr["perch"] or []), (rest.get("gap_m") or 0) * 1e3,
            (rest.get("pen_m") or 0) * 1e3,
            (" (задуманный %.2f мм)" % (pr["designed_gap_m"] * 1e3)) if pr.get("designed_gap_m") is not None else "",
            ("; " + clips) if clips else "", pr["verdict"]))
    for s in rep["scan"]:
        clips = "; ".join("%s ≤%.2f" % (c, v["gap_max_m"] * 1e3) for c, v in (s.get("clips") or {}).items())
        print("SCAN %s (%s) gap %.2f мм до %s%s — %s" % (s["part"], s.get("bone"), (s.get("gap_m") or 0) * 1e3,
                                                       s.get("nearest_part"), (" | клипы: " + clips) if clips else "",
                                                       s["verdict"]))
    for f in rep["failures"]:
        print("FAIL: %s" % f, file=sys.stderr)
    print("RIDER_GAP %s -> %s" % (rep["verdict"], out))
    return 2 if rep["failures"] else 0


if __name__ == "__main__":
    sys.exit(main())
