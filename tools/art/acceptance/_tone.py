"""Тон классов H2LD против концепта для измерения T приёмки (этап 4 скилла 3d-model-pipeline).

Кадры приёмки (EEVEE, AgX, свет key/fill/rim, фон 72) заметно светлее живописи концепта, поэтому тон класса на
глаз против листа не оценивается. Источник тона — отчёт стадии look-dev `ld_measure`
(`tools/tripo-pipeline/blender/h2_bake/lookdev.py:run_measure` → `$LD/reports/measure-report.json`): медианы классов по
проходу ID в орто-кадрах, выровненных по концептам, экспозиция нормирована (`exposure_k_concept_over_ld`, якорный класс
или взвешенное среднее). Поле на класс: `zones.<class>.delta_ld_vs_concept` = {`Y_ratio_exposure_normalised`
(1 = как в концепте), `dHue_deg`, `dSat`}.

Классы, поднятые к физическому полу альбедо (`$LD/reports/ld-maps-report.json#grade.median_floor_applied`: концепт
темнее пола 0,02 — остаток это свет, а не альбедо, `lookdev.py` «Dark classes»), T не снижают: они идут в
known_issues карточки.

Рамка: `measure.framing` есть — орто-кадры look-dev выровнены по концепту (look-dev профиль `frame`, h2-bake 0.6.1,
`tools/tripo-pipeline/blender/h2_bake/framing.py`), поле `framing: concept`; нет — канон Medusa 1021 × 1540
(`framing: default`): для Medusa верно, у нового персонажа это дефект этапа 3 (съёмка пишет предупреждение).

Яркость якорного класса (решение скилла по калибровке 2026-10-09, раунд 3). При `exposure.mode = anchor_class`
экспозиция нормирована по одному классу (Medusa — `linen`, платье), и его `Y_ratio_exposure_normalised` = 1 по
построению: яркость самого крупного класса иначе не проверялась бы никогда. Абсолютная экспозиция для этого не годится:
у живописи концепта свой свет, и отношение Y(концепт)/Y(кадр) содержит экспозицию целиком. Корректная проверка —
**leave-one-out**: экспозиция по всем ОСТАЛЬНЫМ классам (без проверяемого, без классов `floor` и без `legacy_bake`,
который `ld_measure` сам исключает из экспозиции как смешанный) — взвешенное по `pixels_ld` геометрическое среднее
k_c = Y(концепт)/Y(H2LD), и `y_ratio_loo = k_loo / k_класса`: во сколько раз класс светлее (> 1) или темнее (< 1)
концепта ОТНОСИТЕЛЬНО ОСТАЛЬНОЙ ФИГУРЫ. Считается для каждого основного класса; если у остальных классов вместе
меньше 10 % пикселей, опоры нет: `y_ratio_loo = null` и предупреждение `loo_unavailable`.

Семейство тона (граница S и T, решение скилла): медиана хроматическая, если насыщенность ≥ 0,15, иначе нейтральная.
`family: changed`, если обе хроматические и |dHue| > 30°, или одна нейтральная, другая хроматическая и |dSat| ≥ 0,20;
иначе `same`. Смена семейства у основного класса — признак S (раскладка цветов); светлота и насыщенность внутри
семейства — T (потолок `t_cap`).

Допуски (решение скилла; калибровка — Medusa H2LD 20260929-h2-lookdev: все классы вне пола в пределах 0,965–1,203,
|dHue| ≤ 3,8°, якорь `linen` по leave-one-out 1,01):
  основной класс  — доля пикселей рендера (pixels_ld) ≥ 10 % суммы классов;
  вне допуска     — Y_ratio < 0,80 или > 1,25 (≈ ±0,3 EV) или |dHue| > 15° (только у хроматических медиан, ниже);
                    у основного класса ещё y_ratio_loo вне
                    0,80–1,25 (у якорного класса это единственная проверка яркости);
  потолок T       — 1,0, если вне допуска хоть один основной класс; 1,5 — если только второстепенные; иначе 2,0.

Оттенок — только у хроматических медиан (решение скилла по пилоту 2026-10-13, RB-06). Критерий |dHue| > 15°
применяется, только когда обе медианы класса (концепт и H2LD) хроматические — насыщенность ≥ 0,15, тот же порог
`CHROMA_SAT`, что у семейства тона. Оттенок почти серого цвета — шум: сталь меча Angel (sat 0,020 / 0,043) давала
dHue −114° и выносила класс за допуск без дефекта тона; основной нейтральный класс (сталь, чёрная кожа, белый лён) так
получил бы `t_cap` 1,0. Переход нейтральный ↔ хроматический ловит семейство (`family`, |dSat| ≥ 0,20 — признак S).
Нет насыщенностей в отчёте (`concept.sat`/`ld.sat`) — оттенок проверяется, как раньше. Поле строки `hue_checked`.

CLI (выход этапа 3, HANDBOOK §4.4 «Сдача этапа 3»; тот же код, что `frames/tone.json` съёмки):

    python tools/art/acceptance/_tone.py <measure-report.json | run look-dev> [<ld-maps-report.json>] [--json]

Без второго аргумента берётся `ld-maps-report.json` рядом с measure-report (как в `capture_acceptance_set.py`), если он
есть. Печатает `t_cap`, классы `out` и `floor`, смену семейства основного класса, предупреждения и строки классов;
`--json` — всю таблицу. Код выхода: 0 — `t_cap` 2.0 (тон сдаётся); 2 — `t_cap` ниже 2.0 (ещё итерация grade); 1 — вход
не читается.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

MAIN_SHARE = 0.10
Y_LO, Y_HI = 0.80, 1.25
HUE_MAX_DEG = 15.0
LOO_MIN_SHARE = 0.10      # опора leave-one-out: у остальных классов вместе не меньше 10 % пикселей
CHROMA_SAT = 0.15         # насыщенность медианы, с которой цвет хроматический
FAMILY_HUE_DEG = 30.0     # другое семейство у двух хроматических цветов
FAMILY_SAT = 0.20         # нейтральный <-> хроматический: изменение насыщенности
EXCLUDED_FROM_EXPOSURE = {"legacy_bake"}  # ld_measure не берёт его в экспозицию (смешанный класс)


def _k(zone):
    """k_c = Y(концепт) / Y(H2LD) класса или None."""
    try:
        yc, yl = float(zone["concept"]["luma_Y_linear"]), float(zone["ld"]["luma_Y_linear"])
    except (KeyError, TypeError, ValueError):
        return None
    return yc / max(yl, 1e-5) if yc > 0 else None


def _sats(zone):
    """(sat концепта, sat H2LD) медиан класса или None."""
    try:
        return float(zone["concept"]["sat"]), float(zone["ld"]["sat"])
    except (KeyError, TypeError, ValueError):
        return None


def hue_applies(zone):
    """Проверять ли |dHue| класса: обе медианы хроматические (sat ≥ CHROMA_SAT). Нет насыщенностей — да (как раньше)."""
    s = _sats(zone)
    return s is None or (s[0] >= CHROMA_SAT and s[1] >= CHROMA_SAT)


def family(zone, d_hue):
    """same | changed | None (нет медиан): граница S (семейство цвета) и T (светлота, насыщенность)."""
    s = _sats(zone)
    if s is None:
        return None
    sc, sl = s
    cc, cl = sc >= CHROMA_SAT, sl >= CHROMA_SAT
    if cc and cl:
        return "changed" if abs(d_hue) > FAMILY_HUE_DEG else "same"
    if cc != cl:
        return "changed" if abs(sl - sc) >= FAMILY_SAT else "same"
    return "same"


def loo_ratio(cid, zones, floor, total):
    """y_ratio_loo класса cid: экспозиция по остальным классам (без floor и legacy_bake); None — опоры нет."""
    k_c = _k(zones.get(cid) or {})
    if k_c is None:
        return None
    num = den = 0.0
    for other, z in zones.items():
        if other == cid or other in floor or other in EXCLUDED_FROM_EXPOSURE:
            continue
        k_o = _k(z)
        w = float(z.get("pixels_ld") or 0)
        if k_o is None or w <= 0:
            continue
        num += w * math.log(k_o)
        den += w
    if den <= 0 or den / max(total, 1) < LOO_MIN_SHARE:
        return None
    return math.exp(num / den) / k_c


def tone_table(measure: dict, maps: dict | None = None) -> dict:
    """measure — measure-report.json, maps — ld-maps-report.json (или None). Возвращает tone.json (без путей)."""
    zones = measure.get("zones") or {}
    floor = set(((maps or {}).get("grade") or {}).get("median_floor_applied") or {})
    exposure = measure.get("exposure") or {}
    anchor = exposure.get("class") if exposure.get("mode") == "anchor_class" else None
    rows = []
    for cid, z in sorted(zones.items()):
        d = z.get("delta_ld_vs_concept")
        if not isinstance(d, dict) or "Y_ratio_exposure_normalised" not in d:
            continue
        rows.append({"class": cid, "pixels_ld": int(z.get("pixels_ld") or 0),
                     "y_ratio": float(d["Y_ratio_exposure_normalised"]), "d_hue_deg": float(d.get("dHue_deg", 0.0)),
                     "d_sat": float(d.get("dSat", 0.0))})
    if not rows:
        raise ValueError("measure-report: нет zones.*.delta_ld_vs_concept")
    total = sum(r["pixels_ld"] for r in rows) or 1
    cap = 2.0
    warnings = []
    for r in rows:
        r["share"] = round(r["pixels_ld"] / total, 4)
        r["role"] = "main" if r["share"] >= MAIN_SHARE else "secondary"
        r["anchor"] = r["class"] == anchor
        r["family"] = family(zones[r["class"]], r["d_hue_deg"])
        r["hue_checked"] = hue_applies(zones[r["class"]])
        loo = loo_ratio(r["class"], zones, floor, total) if r["role"] == "main" else None
        r["y_ratio_loo"] = round(loo, 3) if loo is not None else None
        if r["role"] == "main" and loo is None and r["class"] not in floor:
            warnings.append("loo_unavailable: %s — у остальных классов вне пола меньше %d %% пикселей, яркость "
                            "класса относительно фигуры не проверена" % (r["class"], int(LOO_MIN_SHARE * 100)))
        out_y = r["y_ratio"] < Y_LO or r["y_ratio"] > Y_HI
        out_loo = r["y_ratio_loo"] is not None and not (Y_LO <= r["y_ratio_loo"] <= Y_HI)
        out_hue = r["hue_checked"] and abs(r["d_hue_deg"]) > HUE_MAX_DEG
        out = out_y or out_loo or out_hue
        if r["class"] in floor:
            r["status"] = "floor"  # концепт темнее пола альбедо: остаток — свет, T не снижает
        elif out:
            r["status"] = "out"
            cap = min(cap, 1.0 if r["role"] == "main" else 1.5)
        else:
            r["status"] = "ok"
    return {
        "schema": "unmatched.acceptance-tone/1",
        "rule": {"main_share_min": MAIN_SHARE, "y_ratio_ok": [Y_LO, Y_HI], "hue_abs_max_deg": HUE_MAX_DEG,
                 "hue_checked": "|dHue| проверяется, только когда обе медианы хроматические (sat >= %.2f); оттенок "
                                "почти серого цвета — шум (RB-06)" % CHROMA_SAT,
                 "y_ratio_loo": "основной класс: экспозиция по остальным классам (без проверяемого, floor и "
                                "legacy_bake), k_loo / k_класса; у якорного класса нормировки y_ratio = 1 по "
                                "построению, его яркость проверяет только y_ratio_loo",
                 "family": "same | changed: обе медианы хроматические (sat >= %.2f) и |dHue| > %d deg, либо переход "
                           "нейтральный <-> хроматический с |dSat| >= %.2f — смена семейства (S); светлота и "
                           "насыщенность внутри семейства — тон (T)" % (CHROMA_SAT, FAMILY_HUE_DEG, FAMILY_SAT),
                 "cap": "1.0 — основной класс вне допуска; 1.5 — только второстепенные; 2.0 — все в допуске; "
                        "status floor (ld-maps-report grade.median_floor_applied) T не снижает"},
        "framing": "concept" if measure.get("framing") else "default",
        "exposure_k_concept_over_ld": measure.get("exposure_k_concept_over_ld"),
        "exposure": measure.get("exposure"),
        "anchor_class": anchor,
        "classes": rows,
        "t_cap": cap,
        "out_of_tolerance": [r["class"] for r in rows if r["status"] == "out"],
        "floor_limited": [r["class"] for r in rows if r["status"] == "floor"],
        "family_changed_main": [r["class"] for r in rows
                                if r["role"] == "main" and r["family"] == "changed" and r["class"] not in floor],
        "warnings": warnings,
    }


def _fmt(v, nd=3):
    return "—" if v is None else ("%.*f" % (nd, v) if isinstance(v, float) else str(v))


def format_table(t: dict, measure_path: str = "", maps_path: str | None = None) -> str:
    """Человекочитаемая сводка tone_table для CLI (выход этапа 3)."""
    lines = ["measure-report: %s" % measure_path,
             "ld-maps-report: %s" % (maps_path or "нет (пол альбедо не учтён: классы floor считаются как обычные)"),
             "t_cap: %s" % t["t_cap"],
             "out: %s" % (", ".join(t["out_of_tolerance"]) or "—"),
             "floor: %s" % (", ".join(t["floor_limited"]) or "—"),
             "family_changed_main: %s" % (", ".join(t["family_changed_main"]) or "—"),
             "anchor: %s; framing: %s" % (t["anchor_class"] or "—", t["framing"])]
    lines += ["warning: %s" % w for w in t["warnings"]]
    lines.append("%-16s %6s %-10s %7s %7s %8s %-5s %-7s %s" % ("class", "share", "role", "y_ratio", "y_loo", "dHue",
                                                             "hue?", "family", "status"))
    for r in t["classes"]:
        lines.append("%-16s %6.3f %-10s %7s %7s %8.1f %-5s %-7s %s" % (
            r["class"], r["share"], r["role"] + ("*" if r["anchor"] else ""), _fmt(r["y_ratio"]),
            _fmt(r["y_ratio_loo"]), r["d_hue_deg"], "yes" if r["hue_checked"] else "no", r["family"] or "—",
            r["status"]))
    return "\n".join(lines)


def main(argv=None) -> int:
    import argparse  # noqa: PLC0415
    for stream in (sys.stdout, sys.stderr):  # русские сообщения читаемы в Git Bash/агентах (консоль cp1251)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Таблица тона H2LD против концепта (t_cap приёмки, выход этапа 3)")
    ap.add_argument("measure", help="measure-report.json look-dev или каталог run look-dev (<run>/reports/...)")
    ap.add_argument("maps", nargs="?", help="ld-maps-report.json (по умолчанию — рядом с measure-report, если есть)")
    ap.add_argument("--json", action="store_true", help="напечатать всю таблицу tone.json")
    a = ap.parse_args(argv)
    mp = Path(a.measure)
    if mp.is_dir():
        mp = mp / "reports" / "measure-report.json"
    maps_p = Path(a.maps) if a.maps else mp.with_name("ld-maps-report.json")
    try:
        measure = json.loads(mp.read_text(encoding="utf-8"))
        maps = json.loads(maps_p.read_text(encoding="utf-8")) if (a.maps or maps_p.is_file()) else None
        t = tone_table(measure, maps)
    except (OSError, ValueError) as e:
        print("FAIL: %s" % e, file=sys.stderr)
        return 1
    if a.json:
        print(json.dumps(t, ensure_ascii=False, indent=2))
    else:
        print(format_table(t, mp.as_posix(), maps_p.as_posix() if maps is not None else None))
    return 0 if t["t_cap"] >= 2.0 else 2


if __name__ == "__main__":
    sys.exit(main())
