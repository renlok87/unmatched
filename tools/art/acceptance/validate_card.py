#!/usr/bin/env python3
"""Валидация карточки приёмки и детерминированный вердикт (этапы 1, 4, 6 скилла 3d-model-pipeline).

    python tools/art/acceptance/validate_card.py <card.json> [--print-verdict] [--check-files]
        [--second <card-2.json> [--final-json <final.json>]]

Что делает:
0. Карточка из строгого вывода приёмщика (`codex exec --output-schema asset-acceptance-2.output-<kind>.schema.json`,
   `_output_schema.py`) несёт null в необязательных полях (clip, verdict_reason, known_issues, gates.*.note,
   gates.*.source_defect): null = поля нет (`strip_output_nulls`, файл не меняется).
1. Проверяет карточку по JSON Schema `tools/art/acceptance/asset-acceptance-2.schema.json` (kind: concept|model|anim).
   Есть пакет `jsonschema` — проверка им (Draft 2020-12); нет — встроенной проверкой того же подмножества ключевых
   слов, которое использует схема.
2. Пересчитывает `score = round(sum / (2 x n_applicable) x 10, 1)` по измерениям с числовым баллом (null у D пропа не
   считается) и сверяет с полем `score`.
3. Применяет правила вердикта (DECISIONS Р-6.4, Р-6.6, Р-7.2) и сверяет с `verdict`:
   model:   S = 0 (другой персонаж) → return_to_stage_1 (концепт не тот); S 0,5–1,0 → return_to_stage_1 (дефект есть
            на листе) | return_to_stage_2 (лист верен, Tripo отклонился), выбор — в verdict_reason; независимо от суммы,
            rework_fix_list при этом пуст (F/T/D — в known_issues);
            иначе гейт FAIL → rework_blender, или return_to_stage_2, если у FAIL-гейта source_defect=true
            (дефект исходника Tripo: нет части, фантом);
            иначе любое измерение < 1,0 (вето) или score < 8,0 → rework_blender; иначе pass.
   concept: гейт G-CHECKS FAIL, вето < 1,0 или score < 8,0 → return_to_stage_1 (новый цикл листа); иначе pass.
   anim:    гейт FAIL, вето < 1,0 или score < 8,0 → rework_blender (доработка клипа); иначе pass.
   Последний цикл без pass (model/anim — r3: два цикла доработки после r1; concept — r4: три цикла после первой
   приёмки, Р-5.8) → escalate_user.
   Сравнение с порогом — `score >= 8.0` по пересчитанному score.
4. Сверки между полями: D=null ⇔ G-RIG n/a (проп); у модели фиксированные кадры (close-hands, close-torso, pose-01..04 и
   pose-03b — при риге) и лист концепта (sheet.png или sheet-<key>.png); кадры-основания баллов и known_issues есть в
   frames.files; rework_fix_list ссылается только на измерения < 2 и FAIL-гейты (S у модели — никогда: в Blender не
   правится); при rework_blender список покрывает каждый FAIL-гейт, каждое вето-измерение, а у модели при score < 8,0 —
   каждое из F/T/D ниже 2,0; previous_card у r2+; сессии приёмщика и исполнителя различаются; при pass по делегированию
   status_note содержит «по делегированию».
5. `--check-files`: файлы accepted_object существуют и sha256 совпадает; frames.dir/<files>, reports и пути-источники
   гейтов существуют (пути от корня репо); если в frames.files есть tone.json — T модели не выше его t_cap; у модели с
   frames.json: frames.files = frames.json#files, frames.json#inputs.fbx.sha256 есть в accepted_object, sheet.png =
   frames.json#sheet.sha256; лист другого ассета (frames.json#sheet.key_match = false) — WARN.
6. Устойчивый pass (любой kind, решение скилла — защита от разброса приёмщиков ±0,5): pass со score 8,0–8,4 одной
   карточкой не окончателен — код 3 и вердикт `needs_second_acceptor`. Второй приёмщик другим профилем на тех же кадрах
   даёт card-2.json; `--second` проверяет обе карточки и пару (asset_id, cycle, accepted_object, frames, гейты равны;
   профили и сессии разные) и печатает итог: score = минимум двух, вердикт — карточки с меньшим score (при равенстве —
   более строгий), а если у другой карточки маршрут строже (возврат, гейт, вето) — он. `--final-json` пишет итог.

`--print-verdict` печатает в stdout вычисленный вердикт одной строкой (`pass`, `rework_blender`,
`return_to_stage_1|return_to_stage_2` — если правило оставляет выбор, `needs_second_acceptor` — п.6), даже если
карточка невалидна, но вычислима.
Код выхода: 0 — карточка (пара) валидна и вердикт согласован с правилами; 1 — нет (ошибки — в stderr); 3 — карточка
валидна, но pass неустойчив: нужен второй приёмщик (`--second`).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCHEMA_PATH = HERE / "asset-acceptance-2.schema.json"

THRESHOLD = 8.0          # Р-6.3/Р-6.4: один порог, сравнение score >= 8.0
STABLE_PASS = 8.5        # модель: pass со score < 8,5 требует второго приёмщика (решение скилла)
EXIT_NEEDS_SECOND = 3
VETO = 1.0               # любое измерение < 1,0 — не pass
SILHOUETTE_RETURN = 1.5  # model: S < 1,5 — возврат на этап 1/2
OTHER_CHARACTER = 0.0    # model: S = 0 (другой персонаж) — только этап 1 (концепт не тот)
DIMS = {"model": ["S", "F", "T", "D"], "concept": ["S", "C", "Q", "P"], "anim": ["R", "C", "D", "L"]}
GATES = {
    "model": ["G-TOPO", "G-UV", "G-TEX", "G-RIG", "G-NAMES"],
    "concept": ["G-CHECKS"],
    "anim": ["G-VALIDATE", "G-CONTACT", "G-MANIFEST"],
}
NA_ALLOWED = {"model": {"G-RIG"}, "concept": set(), "anim": set()}
LAST_CYCLE = {"model": 3, "anim": 3, "concept": 4}
MODEL_FRAMES = ([f"turn-{a:03d}.jpg" for a in range(0, 360, 45)]
                + ["close-head.jpg", "close-weapon.jpg", "close-base.jpg", "wire-front.jpg", "wire-34.jpg",
                   "wire-back.jpg", "uv-layout.png"])
POSE_FRAMES = ([f"close-{z}.jpg" for z in ("hands", "torso", "head-back", "torso-back", "legs", "legs-back")]
               + [f"pose-{i:02d}.jpg" for i in range(1, 5)] + ["pose-03b.jpg"])  # только у ассета с ригом
SHEET_RE = re.compile(r"sheet(-[a-z0-9-]+)?\.png")
SEVERITY = {"pass": 0, "rework_blender": 1, "return_to_stage_2": 2, "return_to_stage_1": 2, "escalate_user": 3}


# --------------------------------------------------------------------------------------------- schema

def _is_type(value, t):
    if t == "object":
        return isinstance(value, dict)
    if t == "array":
        return isinstance(value, list)
    if t == "string":
        return isinstance(value, str)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    if t == "null":
        return value is None
    raise ValueError("unsupported type %r" % t)


def _resolve(root, ref):
    if not ref.startswith("#/"):
        raise ValueError("only local $ref supported: %r" % ref)
    node = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def builtin_validate(value, schema, root=None, path="$"):
    """Встроенная проверка подмножества JSON Schema 2020-12, которое использует схема карточки.
    Возвращает список строк-ошибок."""
    root = schema if root is None else root
    errs = []
    if "$ref" in schema:
        errs += builtin_validate(value, _resolve(root, schema["$ref"]), root, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_is_type(value, t) for t in types):
            return errs + ["%s: ожидался тип %s" % (path, "|".join(types))]
    if "const" in schema and value != schema["const"]:
        errs.append("%s: должно быть %r" % (path, schema["const"]))
    if "enum" in schema and value not in schema["enum"]:
        errs.append("%s: %r не из %r" % (path, value, schema["enum"]))
    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errs.append("%s: короче %d символов" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append("%s: %r не соответствует шаблону" % (path, value))
    if _is_type(value, "number"):
        if "minimum" in schema and value < schema["minimum"]:
            errs.append("%s: %r < %r" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errs.append("%s: %r > %r" % (path, value, schema["maximum"]))
        if "multipleOf" in schema:
            q = value / schema["multipleOf"]
            if abs(q - round(q)) > 1e-9:
                errs.append("%s: %r не кратно %r" % (path, value, schema["multipleOf"]))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errs.append("%s: элементов меньше %d" % (path, schema["minItems"]))
        if schema.get("uniqueItems"):
            seen = [json.dumps(v, sort_keys=True) for v in value]
            if len(seen) != len(set(seen)):
                errs.append("%s: элементы повторяются" % path)
        if "items" in schema:
            for i, v in enumerate(value):
                errs += builtin_validate(v, schema["items"], root, "%s[%d]" % (path, i))
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                errs.append("%s: нет обязательного поля %r" % (path, k))
        if len(value) < schema.get("minProperties", 0):
            errs.append("%s: полей меньше %d" % (path, schema["minProperties"]))
        props = schema.get("properties", {})
        for k, v in value.items():
            if "propertyNames" in schema:
                errs += builtin_validate(k, schema["propertyNames"], root, "%s.<ключ %s>" % (path, k))
            if k in props:
                errs += builtin_validate(v, props[k], root, "%s.%s" % (path, k))
            elif "additionalProperties" in schema:
                ap = schema["additionalProperties"]
                if ap is False:
                    errs.append("%s: лишнее поле %r" % (path, k))
                elif isinstance(ap, dict):
                    errs += builtin_validate(v, ap, root, "%s.%s" % (path, k))
    for sub in schema.get("allOf", []):
        errs += builtin_validate(value, sub, root, path)
    if "anyOf" in schema:
        if all(builtin_validate(value, sub, root, path) for sub in schema["anyOf"]):
            errs.append("%s: не подходит ни один вариант anyOf" % path)
    if "if" in schema:
        if not builtin_validate(value, schema["if"], root, path):
            if "then" in schema:
                errs += builtin_validate(value, schema["then"], root, path)
        elif "else" in schema:
            errs += builtin_validate(value, schema["else"], root, path)
    return errs


def schema_errors(card, schema, use_jsonschema=True):
    if use_jsonschema:
        try:
            import jsonschema  # noqa: PLC0415
        except ImportError:
            use_jsonschema = False
    if use_jsonschema:
        v = jsonschema.Draft202012Validator(schema)
        out = []
        for e in sorted(v.iter_errors(card), key=lambda e: list(e.absolute_path)):
            loc = "$" + "".join("[%d]" % p if isinstance(p, int) else ".%s" % p for p in e.absolute_path)
            out.append("%s: %s" % (loc, e.message))
        return out
    return builtin_validate(card, schema)


# --------------------------------------------------------------------------------------------- rules

def compute_score(scores, kind):
    """score = round(sum / (2 x n) x 10, 1), n — измерения с числовым баллом. Округление half-up (Decimal)."""
    vals = [scores[d]["value"] for d in DIMS[kind] if isinstance(scores.get(d), dict)
            and isinstance(scores[d].get("value"), (int, float)) and not isinstance(scores[d].get("value"), bool)]
    if not vals:
        return None
    raw = Decimal(str(sum(vals))) / (Decimal(2) * len(vals)) * 10
    return float(raw.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def cycle_number(card):
    m = re.fullmatch(r"r([1-9])", str(card.get("cycle", "")))
    return int(m.group(1)) if m else None


def compute_verdict(card):
    """Возвращает (множество допустимых вердиктов, список применённых правил, score)."""
    kind = card["kind"]
    scores = card["scores"]
    gates = card.get("gates", {})
    score = compute_score(scores, kind)
    values = {d: scores[d]["value"] for d in DIMS[kind] if d in scores}
    failed = [g for g, v in gates.items() if isinstance(v, dict) and v.get("status") == "FAIL"]
    vetoed = [d for d, v in values.items() if v is not None and v < VETO]
    rules = []
    if kind == "model":
        s = values.get("S")
        if s is not None and s <= OTHER_CHARACTER:
            allowed = {"return_to_stage_1"}
            rules.append("S=0: другой персонаж (нет половины и больше якорей листа) — концепт не тот → этап 1 "
                         "(сначала запускающий сверяет вход: frames.json#inputs против accepted_object, лист заявки)")
        elif s is not None and s < SILHOUETTE_RETURN:
            allowed = {"return_to_stage_1", "return_to_stage_2"}
            rules.append("S=%s < %s: силуэт/пропорции/палитра в Blender не правятся → этап 1 (дефект есть на листе) "
                         "или 2 (лист верен, Tripo отклонился)" % (s, SILHOUETTE_RETURN))
        elif failed:
            src = [g for g in failed if gates[g].get("source_defect") is True]
            allowed = {"return_to_stage_2"} if src else {"rework_blender"}
            rules.append("гейт FAIL: %s%s" % (", ".join(failed),
                                              " (дефект исходника Tripo: %s)" % ", ".join(src) if src else ""))
        elif vetoed or score is None or score < THRESHOLD:
            allowed = {"rework_blender"}
            rules.append("вето < 1,0: %s; score %s %s 8,0" % (vetoed or "нет", score, ">=" if (score or 0) >= THRESHOLD else "<"))
        else:
            allowed = {"pass"}
            rules.append("гейты PASS, все измерения >= 1,0, S >= 1,5, score %s >= 8,0" % score)
    else:
        fail_route = "return_to_stage_1" if kind == "concept" else "rework_blender"
        if failed or vetoed or score is None or score < THRESHOLD:
            allowed = {fail_route}
            rules.append("гейт FAIL: %s; вето < 1,0: %s; score %s" % (failed or "нет", vetoed or "нет", score))
        else:
            allowed = {"pass"}
            rules.append("гейты PASS, все измерения >= 1,0, score %s >= 8,0" % score)
    n = cycle_number(card)
    if allowed != {"pass"} and n is not None and n >= LAST_CYCLE[kind]:
        rules.append("цикл r%d — последний для kind=%s, без pass → escalate_user" % (n, kind))
        allowed = {"escalate_user"}
    return allowed, rules, score


def consistency_errors(card):
    errs = []
    kind = card["kind"]
    scores, gates = card["scores"], card["gates"]
    files = set(card["frames"]["files"])
    # n/a только где разрешено
    for g, v in gates.items():
        if v.get("status") == "n/a" and g not in NA_ALLOWED[kind]:
            errs.append("gates.%s: n/a не допускается для kind=%s" % (g, kind))
        if v.get("source_defect") is not None and (kind != "model" or v.get("status") != "FAIL"):
            errs.append("gates.%s: source_defect допустим только у FAIL-гейта модели" % g)
    # D=null ⇔ G-RIG n/a
    if kind == "model":
        d_null = scores["D"]["value"] is None
        rig_na = gates["G-RIG"]["status"] == "n/a"
        if d_null != rig_na:
            errs.append("scores.D.value=null и gates.G-RIG=n/a допустимы только вместе (проп без рига)")
        need = list(MODEL_FRAMES) + ([] if rig_na else POSE_FRAMES)
        missing = [f for f in need if f not in files]
        if not any(SHEET_RE.fullmatch(f) for f in files):
            missing.append("sheet.png (лист концепта)")
        if missing:
            errs.append("frames.files: нет обязательных кадров Р-6.1: %s" % ", ".join(missing))
    # кадры-основания
    for d in DIMS[kind]:
        dim = scores[d]
        if dim["value"] is not None:
            bad = [f for f in dim["frames"] if f not in files]
            if bad:
                errs.append("scores.%s.frames: нет в frames.files: %s" % (d, ", ".join(bad)))
    # known_issues: необязательные замечания (при любом вердикте), машиночитаемые
    for i, ki in enumerate(card.get("known_issues") or []):
        if ki["item"] not in DIMS[kind] and ki["item"] not in gates:
            errs.append("known_issues[%d]: %r — не измерение и не гейт kind=%s" % (i, ki["item"], kind))
        if ki["frame"] not in files:
            errs.append("known_issues[%d].frame: %r нет в frames.files" % (i, ki["frame"]))
    # rework_fix_list
    below2 = {d for d in DIMS[kind] if scores[d]["value"] is not None and scores[d]["value"] < 2}
    failed = {g for g, v in gates.items() if v["status"] == "FAIL"}
    items = [it["item"] for it in card["rework_fix_list"]]
    for it in items:
        if kind == "model" and it == "S":
            errs.append("rework_fix_list: 'S' — силуэт в Blender не правится (S < 1,5 — возврат на этап 1/2)")
        elif it not in below2 and it not in failed:
            errs.append("rework_fix_list: %r — не измерение < 2 и не FAIL-гейт" % it)
    s_val = scores.get("S", {}).get("value") if kind == "model" else None
    if s_val is not None and s_val < SILHOUETTE_RETURN and items:
        errs.append("rework_fix_list: при S < 1,5 (возврат на этап 1/2) список пуст — модель перегенерируют; F, T, D "
                    "ниже 2 записываются в known_issues")
    if card["verdict"] == "rework_blender":
        vetoed = {d for d in below2 if scores[d]["value"] < VETO}
        need = failed | vetoed
        score = compute_score(scores, kind)
        if kind == "model" and score is not None and score < THRESHOLD:
            need |= below2 - {"S"}  # score < 8: поднимать можно только F/T/D — каждый ниже 2 в списке
        missed = sorted(need - set(items))
        if missed:
            errs.append("rework_fix_list: при rework_blender нет пунктов для %s" % ", ".join(missed))
    # циклы
    n = cycle_number(card)
    if n is not None and n > 1 and not card.get("previous_card"):
        errs.append("previous_card обязателен для цикла r%d" % n)
    if n == 1 and card.get("previous_card"):
        errs.append("previous_card у r1 должен быть null")
    # независимость приёмщика (Р-4)
    if card["acceptor"]["session_id"] == card["executor_session_id"]:
        errs.append("acceptor.session_id совпадает с executor_session_id: приёмщик не принимает свою работу")
    if card["verdict"] == "pass" and "delegated" in card["decided_by"] and "по делегированию" not in card["status_note"]:
        errs.append("status_note: при pass по делегированию нужна пометка «по делегированию» "
                    "(docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)")
    return errs


def _frames_manifest(card, repo):
    """frames.json набора кадров модели (capture_acceptance_set.py) или None."""
    fj = repo / card["frames"]["dir"] / "frames.json"
    if card["kind"] != "model" or "frames.json" not in card["frames"]["files"] or not fj.is_file():
        return None
    try:
        return json.loads(fj.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"_unreadable": True}


def frames_manifest_errors(card, repo):
    """Вход приёмки = принимаемый объект (калибровка 2026-10-09, раунд 3): frames.files = frames.json#files, кадры
    сняты с FBX из accepted_object, sheet.png — тот лист, что записан в frames.json#sheet."""
    man = _frames_manifest(card, repo)
    if man is None:
        return []
    if man.get("_unreadable"):
        return ["frames/frames.json: не читается"]
    errs = []
    mf = man.get("files")
    if isinstance(mf, list) and sorted(mf) != sorted(card["frames"]["files"]):
        extra = sorted(set(card["frames"]["files"]) - set(mf))
        miss = sorted(set(mf) - set(card["frames"]["files"]))
        errs.append("frames.files ≠ frames.json#files (лишние: %s; нет: %s)" % (extra or "—", miss or "—"))
    fsha = ((man.get("inputs") or {}).get("fbx") or {}).get("sha256")
    shas = {o["sha256"] for o in card["accepted_object"]}
    if fsha and fsha not in shas:
        errs.append("frames.json#inputs.fbx.sha256 %s нет в accepted_object: кадры сняты не с принимаемого FBX" % fsha)
    sheet = man.get("sheet") or {}
    sp = repo / card["frames"]["dir"] / "sheet.png"
    if sheet.get("sha256") and sp.is_file() and hashlib.sha256(sp.read_bytes()).hexdigest() != sheet["sha256"]:
        errs.append("frames/sheet.png не совпадает с frames.json#sheet.sha256: лист подменён после съёмки")
    return errs


def file_warnings(card, repo):
    """Предупреждения --check-files (код не меняют): лист другого ассета (не тот лист или негативный контроль)."""
    man = _frames_manifest(card, repo)
    if not man or man.get("_unreadable"):
        return []
    sheet = man.get("sheet") or {}
    if sheet.get("key_match") is False:
        return ["frames.json#sheet: лист %s (ключ %s) не совпадает с ключом ассета — не тот лист (стоп, сверить вход) "
                "или негативный контроль калибровки" % (sheet.get("source"), sheet.get("content_key"))]
    return []


def file_errors(card, repo):
    errs = []

    def exists(rel, what):
        p = repo / rel
        if not p.exists():
            errs.append("%s: нет файла %s" % (what, rel))
            return None
        return p

    for i, obj in enumerate(card["accepted_object"]):
        p = exists(obj["path"], "accepted_object[%d]" % i)
        if p is not None and p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()
            if h != obj["sha256"]:
                errs.append("accepted_object[%d]: sha256 %s != %s (%s)" % (i, h, obj["sha256"], obj["path"]))
    fdir = card["frames"]["dir"]
    for f in card["frames"]["files"]:
        exists("%s/%s" % (fdir.rstrip("/"), f), "frames")
    errs += frames_manifest_errors(card, repo)
    for r in card["reports"]:
        exists(r, "reports")
    for g, v in card["gates"].items():
        src = v["source"]
        if "/" in src and " " not in src and not src.startswith("python"):
            exists(src, "gates.%s.source" % g)
    if card.get("previous_card"):
        exists(card["previous_card"], "previous_card")
    tone_p = repo / fdir / "tone.json"
    if card["kind"] == "model" and "tone.json" in card["frames"]["files"] and tone_p.is_file():
        try:
            cap = float(json.loads(tone_p.read_text(encoding="utf-8"))["t_cap"])
        except (OSError, ValueError, KeyError, TypeError) as e:
            errs.append("frames/tone.json: не читается t_cap (%s)" % e)
        else:
            t = card["scores"]["T"]["value"]
            if t is not None and t > cap:
                errs.append("scores.T.value %s > t_cap %s из tone.json (тон класса вне допуска)" % (t, cap))
    return errs


OUTPUT_NULLABLE = ("clip", "verdict_reason", "known_issues")  # строгий вывод приёмщика (_output_schema.py)
OUTPUT_NULLABLE_GATE = ("note", "source_defect")


def strip_output_nulls(card):
    """Карточка из строгого вывода `codex exec --output-schema` (_output_schema.py) заполняет необязательные поля
    значением null: null = поля нет. Возвращает копию без них (файл карточки не меняется)."""
    if not isinstance(card, dict):
        return card
    out = {k: v for k, v in card.items() if not (k in OUTPUT_NULLABLE and v is None)}
    if isinstance(out.get("gates"), dict):
        out["gates"] = {g: ({k: x for k, x in v.items() if not (k in OUTPUT_NULLABLE_GATE and x is None)}
                            if isinstance(v, dict) else v) for g, v in out["gates"].items()}
    return out


def validate(card, schema, check_files=False, repo=REPO, use_jsonschema=True):
    """Возвращает (ошибки, допустимые вердикты | None, правила, score | None)."""
    card = strip_output_nulls(card)
    errs = schema_errors(card, schema, use_jsonschema)
    allowed, rules, score = None, [], None
    if errs:
        # вердикт вычисляем, если хватает данных
        try:
            allowed, rules, score = compute_verdict(card)
        except Exception:  # noqa: BLE001 — карточка слишком сломана для вычисления
            pass
        return errs, allowed, rules, score
    errs += consistency_errors(card)
    allowed, rules, score = compute_verdict(card)
    if abs(card["score"] - score) > 1e-9:
        errs.append("score: в карточке %s, пересчёт round(sum/(2*n)*10, 1) = %s" % (card["score"], score))
    if card["verdict"] not in allowed:
        errs.append("verdict: в карточке %r, по правилам %s (%s)"
                    % (card["verdict"], "|".join(sorted(allowed)), "; ".join(rules)))
    if check_files:
        errs += file_errors(card, repo)
    return errs, allowed, rules, score


def needs_second(card, allowed, score):
    """Любой kind (модель, концепт, клип): pass со score в [8,0; 8,5) неустойчив — нужен второй приёмщик другим
    профилем (решение скилла по калибровке 2026-10-09, раунд 3: правило распространено на concept и anim)."""
    return (card.get("kind") in DIMS and allowed == {"pass"} and score is not None
            and THRESHOLD <= score < STABLE_PASS)


def pair_errors(a, b, same_profile_ok=False):
    """Сверка двух карточек одной приёмки (первый и второй приёмщик). same_profile_ok — запасной путь, когда второй
    профиль не запустился после пробы: второй приёмщик того же профиля, но в новом контексте."""
    errs = []
    for k in ("schema", "kind", "asset_id", "cycle", "previous_card", "accepted_object", "frames",
              "executor_session_id"):
        if a.get(k) != b.get(k):
            errs.append("--second: поле %s различается — второй приёмщик смотрит тот же набор" % k)
    if a["acceptor"]["profile"] == b["acceptor"]["profile"] and not same_profile_ok:
        errs.append("--second: профиль приёмщика тот же (%s), нужен другой" % a["acceptor"]["profile"])
    if a["acceptor"]["session_id"] == b["acceptor"]["session_id"]:
        errs.append("--second: session_id приёмщиков совпадает")
    ga = {g: v["status"] for g, v in a["gates"].items()}
    gb = {g: v["status"] for g, v in b["gates"].items()}
    if ga != gb:
        errs.append("--second: статусы гейтов различаются %s / %s — сверить отчёты (§8.1 п.6)" % (ga, gb))
    return errs


def final_of_pair(paths, cards, scores):
    """Итог двух приёмщиков: score = минимум; вердикт — карточки с меньшим score (равенство — строже), но если у
    другой маршрут строже (возврат, FAIL-гейт, вето), побеждает строгий. Возвращает (индекс, score, вердикт)."""
    order = sorted(range(2), key=lambda i: (scores[i], -SEVERITY[cards[i]["verdict"]]))
    low = order[0]
    pick = low
    if SEVERITY[cards[order[1]]["verdict"]] > SEVERITY[cards[low]["verdict"]]:
        pick = order[1]
    return pick, min(scores), cards[pick]["verdict"]


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # русские сообщения читаемы в Git Bash/агентах (консоль cp1251)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("card", help="путь к card.json")
    ap.add_argument("--print-verdict", action="store_true", help="напечатать вычисленный вердикт в stdout")
    ap.add_argument("--check-files", action="store_true",
                    help="проверить существование файлов и sha256 accepted_object (пути от корня репо)")
    ap.add_argument("--repo-root", default=str(REPO), help=argparse.SUPPRESS)
    ap.add_argument("--no-jsonschema", action="store_true", help="принудительно встроенная проверка схемы")
    ap.add_argument("--second", help="card-2.json второго приёмщика (другой профиль, те же кадры): итог по минимуму")
    ap.add_argument("--same-profile-ok", action="store_true",
                    help="с --second: второй приёмщик того же профиля (другой профиль не запустился после пробы)")
    ap.add_argument("--final-json", help="с --second: записать итог пары (unmatched.acceptance-final/1)")
    a = ap.parse_args(argv)
    paths = [a.card] + ([a.second] if a.second else [])
    cards = []
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        for pth in paths:
            cards.append(json.loads(Path(pth).read_text(encoding="utf-8")))
    except (OSError, ValueError) as e:
        print("FAIL: не читается %s: %s" % (paths[len(cards)], e), file=sys.stderr)
        return 1
    if not all(isinstance(c, dict) for c in cards):
        print("FAIL: карточка должна быть JSON-объектом", file=sys.stderr)
        return 1
    results = [validate(c, schema, a.check_files, Path(a.repo_root), not a.no_jsonschema) for c in cards]
    if a.check_files:
        for pth, c in zip(paths, cards):
            try:
                for w in file_warnings(strip_output_nulls(c), Path(a.repo_root)):
                    print("WARN: %s%s" % ("[%s] " % pth if a.second else "", w), file=sys.stderr)
            except (KeyError, TypeError, AttributeError):
                pass  # невалидная карточка: ошибки уже в results
    bad = False
    for pth, (errs, allowed, rules, score) in zip(paths, results):
        for r in rules:
            print("rule: %s%s" % ("[%s] " % pth if a.second else "", r), file=sys.stderr)
        for e in errs:
            print("FAIL: %s%s" % ("[%s] " % pth if a.second else "", e), file=sys.stderr)
        bad = bad or bool(errs)
    if not a.second:
        card = cards[0]
        errs, allowed, rules, score = results[0]
        unstable = not errs and needs_second(card, allowed, score)
        if a.print_verdict and allowed:
            print("needs_second_acceptor" if unstable else "|".join(sorted(allowed)))
        if errs:
            return 1
        if unstable:
            print("NEED-SECOND: score %s в полосе 8,0–8,4 — pass неустойчив; второй приёмщик другим профилем на тех же "
                  "кадрах → card-2.json, затем --second" % score, file=sys.stderr)
            return EXIT_NEEDS_SECOND
        print("OK: %s kind=%s cycle=%s score=%s verdict=%s" % (a.card, card["kind"], card["cycle"], score,
                                                              card["verdict"]), file=sys.stderr)
        return 0
    if bad:
        return 1
    perr = pair_errors(cards[0], cards[1], a.same_profile_ok)
    for e in perr:
        print("FAIL: %s" % e, file=sys.stderr)
    if perr:
        return 1
    scores = [r[3] for r in results]
    pick, smin, verdict = final_of_pair(paths, cards, scores)
    print("rule: итог пары — score min(%s, %s) = %s, вердикт %s по %s" % (scores[0], scores[1], smin, verdict,
                                                                         paths[pick]), file=sys.stderr)
    if a.print_verdict:
        print(verdict)
    if a.final_json:
        out = {"schema": "unmatched.acceptance-final/1", "asset_id": cards[0]["asset_id"], "cycle": cards[0]["cycle"],
               "cards": [{"path": Path(pth).as_posix(), "profile": c["acceptor"]["profile"],
                          "session_id": c["acceptor"]["session_id"], "score": sc, "verdict": c["verdict"]}
                         for pth, c, sc in zip(paths, cards, scores)],
               "score": smin, "verdict": verdict, "source_card": Path(paths[pick]).as_posix(),
               "same_profile_fallback": bool(a.same_profile_ok
                                             and cards[0]["acceptor"]["profile"] == cards[1]["acceptor"]["profile"]),
               "rule": "score = минимум двух; вердикт — карточки с меньшим score, строже — если у другой маршрут строже"}
        Path(a.final_json).write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("OK: пара %s + %s: score=%s verdict=%s" % (paths[0], paths[1], smin, verdict), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
