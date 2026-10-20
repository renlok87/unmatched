#!/usr/bin/env python3
"""Валидация карточки приёмки и детерминированный вердикт (этапы 1, 4, 6 скилла 3d-model-pipeline).

    python tools/art/acceptance/validate_card.py <card.json> [--print-verdict] [--check-files]
        [--second <card-2.json> [--final-json <final.json>]]

Что делает:
0. Карточка из строгого вывода приёмщика (структурный вывод Workflow по `asset-acceptance-2.output-<kind>.schema.json`,
   `_output_schema.py`; до 2026-10-20 — `codex exec --output-schema`) несёт null в необязательных полях (clip,
   verdict_reason, known_issues, gates.*.note, gates.*.source_defect): null = поля нет (`strip_output_nulls`, файл
   не меняется).
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
   status_note содержит «по делегированию». Профиль приёмщика (side_models.py): «Opus xhigh», «Z-Code GLM-5.3-Flash»
   или «Sol 6.1 xhigh» — последний отключён 2026-10-20, его карточки с датой позже — ошибка, старые валидны.
5. `--check-files`: файлы accepted_object существуют и sha256 совпадает; frames.dir/<files>, reports и пути-источники
   гейтов существуют (пути от корня репо). У модели frames.dir/frames.json и tone.json читаются всегда, а не только
   когда приёмщик перечислил их в frames.files (пилот 2026-10-13, RB-16): frames.json обязателен, frames.files =
   frames.json#files, frames.json#inputs.fbx.sha256 есть в accepted_object, sheet.png = frames.json#sheet.sha256; T не
   выше t_cap из tone.json; tone.json, названный в frames.json (#tone, #files), обязан быть, его t_cap =
   frames.json#tone.t_cap. Машинные гейты модели (G-TOPO, G-UV, G-TEX, G-RIG, G-NAMES) пересчитываются по отчётам
   карточки и заявке asset-card.yaml (`--asset-card`, по умолчанию art/pipeline-candidates/<ASSET_ID>/asset-card.yaml):
   статус карточки, расходящийся с пересчётом, — ошибка (RB-05; рост G-NAMES — верх тела без оружия, F41/F78).
   WARN (код не меняют): лист другого ассета (frames.json#sheet.key_match = false); t_cap tone.json ≠ пересчёту текущим
   _tone.py; гейты не пересчитаны (проп, нет ld-fbx-report — форк) или пересчитаны не целиком (нет заявки).
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
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import side_models  # noqa: E402
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
    retired = side_models.retired_profile_error(card["acceptor"]["profile"], card.get("date"))
    if retired:
        errs.append(retired)
    if card["verdict"] == "pass" and "delegated" in card["decided_by"] and "по делегированию" not in card["status_note"]:
        errs.append("status_note: при pass по делегированию нужна пометка «по делегированию» "
                    "(docs/game-design/decisions/2026-10-06-visual-delegated-decisions.md)")
    return errs


def _read_json(p):
    """JSON-файл, {"_unreadable": True} — не читается, None — нет файла."""
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"_unreadable": True}
    return data if isinstance(data, dict) else {"_unreadable": True}


def _frames_manifest(card, repo):
    """frames.json набора кадров модели (capture_acceptance_set.py) или None (не модель или файла нет). Читается всегда,
    а не только когда приёмщик перечислил его в frames.files (пилот 2026-10-13, RB-16)."""
    if card["kind"] != "model":
        return None
    return _read_json(repo / card["frames"]["dir"] / "frames.json")


def frames_manifest_errors(card, repo):
    """Вход приёмки = принимаемый объект (калибровка 2026-10-09, раунд 3): frames.files = frames.json#files, кадры
    сняты с FBX из accepted_object, sheet.png — тот лист, что записан в frames.json#sheet. У модели frames.json
    обязателен: съёмка пишет его всегда, без него сверка входа и t_cap обходятся (RB-16)."""
    if card["kind"] != "model":
        return []
    man = _frames_manifest(card, repo)
    if man is None:
        return ["frames/frames.json: нет манифеста кадров (capture_acceptance_set.py пишет его всегда; без него сверка "
                "входа не проверяется)"]
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


def file_warnings(card, repo, asset_card=None):
    """Предупреждения --check-files (код не меняют): лист другого ассета (не тот лист или негативный контроль), t_cap
    tone.json против пересчёта, гейты, которые не пересчитаны по отчётам или пересчитаны не целиком."""
    out = []
    man = _frames_manifest(card, repo)
    sheet = (man or {}).get("sheet") or {}
    if man and not man.get("_unreadable") and sheet.get("key_match") is False:
        out.append("frames.json#sheet: лист %s (ключ %s) не совпадает с ключом ассета — не тот лист (стоп, сверить "
                   "вход) или негативный контроль калибровки" % (sheet.get("source"), sheet.get("content_key")))
    out += tone_warnings(card, repo)
    out += recompute_gates(card, repo, asset_card)[1]
    return out


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
    errs += tone_errors(card, repo)
    return errs


def _tone_cap(card, repo):
    """(t_cap из frames.dir/tone.json | None, ошибка | None). tone.json модели читается всегда (RB-16)."""
    tone_p = repo / card["frames"]["dir"] / "tone.json"
    if not tone_p.is_file():
        return None, None
    try:
        return float(json.loads(tone_p.read_text(encoding="utf-8"))["t_cap"]), None
    except (OSError, ValueError, KeyError, TypeError) as e:
        return None, "frames/tone.json: не читается t_cap (%s)" % e


def tone_errors(card, repo):
    """Потолок T из tone.json (§5.3): T модели не выше t_cap. tone.json и frames.json читаются всегда, а не только когда
    приёмщик перечислил их в frames.files (пилот 2026-10-13, RB-16): съёмка, создавшая tone.json, записывает его в
    frames.json#tone; tone.json нет, а frames.json его называет — ошибка; t_cap в tone.json и frames.json#tone
    расходятся — tone.json подменён после съёмки."""
    if card["kind"] != "model":
        return []
    errs = []
    man = _frames_manifest(card, repo)
    man = man if man and not man.get("_unreadable") else {}
    man_tone = man.get("tone") if isinstance(man.get("tone"), dict) else None
    cap, err = _tone_cap(card, repo)
    if err:
        return [err]
    if cap is None:
        named = man_tone is not None or "tone.json" in (man.get("files") or [])
        if named and "tone.json" not in card["frames"]["files"]:  # перечисленный файл ловит проверка frames.files
            errs.append("frames/tone.json: нет файла, а frames.json его называет (#tone/#files): потолок T не проверить")
        return errs
    if man_tone is not None and man_tone.get("t_cap") is not None and float(man_tone["t_cap"]) != cap:
        errs.append("frames/tone.json#t_cap %s ≠ frames.json#tone.t_cap %s: tone.json заменён после съёмки"
                    % (cap, man_tone["t_cap"]))
    t = card["scores"]["T"]["value"]
    if t is not None and t > cap:
        errs.append("scores.T.value %s > t_cap %s из tone.json (тон класса вне допуска)" % (t, cap))
    return errs


def tone_warnings(card, repo):
    """WARN: t_cap tone.json расходится с пересчётом текущим _tone.py по его же sources (правило тона изменилось после
    съёмки — RB-06, или отчёт заменён). Карточку проверяет t_cap из tone.json: его видел приёмщик."""
    if card["kind"] != "model":
        return []
    tone = _read_json(repo / card["frames"]["dir"] / "tone.json")
    if not tone or tone.get("_unreadable"):
        if tone is None and card["gates"].get("G-RIG", {}).get("status") != "n/a":
            man = _frames_manifest(card, repo)
            if man and not man.get("_unreadable") and "tone" in man and man["tone"] is None:
                return ["frames.json#tone = null: героя сняли без measure-report (--allow-no-tone), тон T потолком не "
                        "ограничен"]
        return []
    src = tone.get("sources") or {}
    mp = src.get("measure_report")
    if not mp or not (repo / mp).is_file():
        return []
    try:
        from _tone import tone_table  # noqa: PLC0415
        maps_p = src.get("maps_report")
        maps = json.loads((repo / maps_p).read_text(encoding="utf-8")) if maps_p and (repo / maps_p).is_file() else None
        now = tone_table(json.loads((repo / mp).read_text(encoding="utf-8")), maps)
    except (OSError, ValueError, ImportError) as e:
        return ["tone.json: пересчёт по %s не удался (%s)" % (mp, e)]
    if tone.get("t_cap") is not None and float(now["t_cap"]) != float(tone["t_cap"]):
        return ["tone.json#t_cap %s, пересчёт текущим _tone.py по %s = %s (правило тона изменилось после съёмки или "
                "отчёт заменён; карточку проверяет t_cap из tone.json)" % (tone["t_cap"], mp, now["t_cap"])]
    return []


# --------------------------------------------------------------------------------------------- гейты из отчётов (RB-05)
#
# Машинные гейты модели (рубрика §4, H2-герой генерического h2_bake) валидатор пересчитывает сам по отчётам карточки
# (`reports` и `gates.*.source`, поиск по имени файла) и заявке `art/pipeline-candidates/<ASSET_ID>/asset-card.yaml`
# (`POLY_BUDGET`, `UE_NAMES`, `FIGURE_HEIGHT_M`, `FIGURE_BOUNDS_TOP_M`); расхождение со статусом в карточке — ошибка.
# Пилот 2026-10-13: гейты ставил приёмщик-LLM, разнобой G-NAMES (F78) и разброс приёмщиков (F141, F151).
# Не пересчитываются (WARN): проп (G-RIG n/a: candidate-report, свои ключи §4 «Проп»), ассет без ld-fbx-report.json
# (форк старше скилла — таблица соответствия §12.2). Без заявки — POLY_BUDGET по умолчанию (GD-058), а пункт (1)
# G-NAMES (UE_NAMES) и рост не сверяются (WARN); такой пересчёт неполный: PASS по отчётам не опровергает FAIL карточки.

POLY_BUDGET_DEFAULT = {"figure_tris_max": 45000, "base_tris_max": 2500}  # GD-058 final, SKILL.md §7.2
NEAR_DEGENERATE_MAX = 0.001   # §4 G-TOPO: почти вырожденных не больше 0,1 % треугольников каждого меша
HEIGHT_TOL = 0.01             # §4 G-NAMES (5): бюджет роли HANDBOOK §2.10 ± 1 %
ARMATURE_OBJECT = "SKEL_UM_Humanoid"
FBX_PRESET = "UM_FBX_v1"
PX_2K = [2048, 2048]


def _dig(d, *keys):
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def load_asset_card(card, repo, path=None):
    """(заявка asset-card.yaml | None, предупреждение | None). По умолчанию <repo>/art/pipeline-candidates/<ASSET_ID>/."""
    p = Path(path) if path else repo / "art" / "pipeline-candidates" / str(card.get("asset_id")) / "asset-card.yaml"
    if not p.is_file():
        return None, "нет заявки %s" % (p.as_posix() if path else "art/pipeline-candidates/%s/asset-card.yaml"
                                         % card.get("asset_id"))
    try:
        import yaml  # noqa: PLC0415
    except ImportError:
        return None, "нет пакета PyYAML: заявка %s не прочитана" % p.as_posix()
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as e:
        return None, "заявка %s не читается (%s)" % (p.as_posix(), e)
    if not isinstance(data, dict):
        return None, "заявка %s — не словарь YAML" % p.as_posix()
    return data, None


class _Reports:
    """Отчёты карточки по имени файла: `reports` и `gates.*.source` (первое вхождение имени)."""

    def __init__(self, card, repo):
        self.repo, self.rel, self._cache = repo, {}, {}
        srcs = [v.get("source", "") for v in card["gates"].values() if isinstance(v, dict)]
        for rel in list(card.get("reports") or []) + srcs:
            if isinstance(rel, str) and rel.endswith(".json") and " " not in rel and "#" not in rel:
                self.rel.setdefault(Path(rel).name, rel)

    def path(self, name):
        rel = self.rel.get(name)
        return self.repo / rel if rel else None

    def get(self, name):
        """dict отчёта или None (нет в карточке, нет файла, не читается)."""
        if name not in self._cache:
            p = self.path(name)
            data = _read_json(p) if p else None
            self._cache[name] = data if data and not data.get("_unreadable") else None
        return self._cache[name]


def _need(R, name, fails):
    rep = R.get(name)
    if rep is None:
        fails.append("%s: нет в reports карточки или не читается (нет отчёта = FAIL, §4)" % name)
    return rep


def _need_passed(rep, name, keys, fails):
    """Каждый ключ `a.b` должен иметь `passed: true` (`passed` — верхний уровень отчёта)."""
    for key in keys:
        if key == "passed":
            if rep.get("passed") is not True:
                fails.append("%s#passed ≠ true" % name)
        elif _dig(rep, *key.split("."), "passed") is not True:
            fails.append("%s#%s.passed ≠ true" % (name, key))


def _accepted_shas(card):
    return {o.get("sha256") for o in card["accepted_object"]}


def _gate_topo(card, R, ctx):
    fails = []
    L = ctx["ld"]
    meas = _dig(L, "checks", "triangles_as_h21", "measured")
    budget = ctx["poly_budget"]
    if not isinstance(meas, dict):
        fails.append("ld-fbx-report.json#checks.triangles_as_h21.measured: нет ключа")
    else:
        skel, base = _dig(L, "roundtrip", "ld", "skeletal", "meshes"), _dig(L, "roundtrip", "ld", "base", "meshes")
        fig_names = list(skel) if isinstance(skel, dict) else [m for m in meas if m.startswith("SK_")]
        base_names = list(base) if isinstance(base, dict) else [m for m in meas if m.startswith("SM_")]
        fig = sum(int(meas.get(m) or 0) for m in fig_names)
        bas = sum(int(meas.get(m) or 0) for m in base_names)
        if fig > budget["figure_tris_max"]:
            fails.append("ld-fbx-report.json#checks.triangles_as_h21: фигура %s = %d > POLY_BUDGET.figure_tris_max %d"
                         % (" + ".join(fig_names), fig, budget["figure_tris_max"]))
        if budget.get("base_tris_max") is not None and bas > budget["base_tris_max"]:
            fails.append("ld-fbx-report.json#checks.triangles_as_h21: подставка %d > POLY_BUDGET.base_tris_max %d"
                         % (bas, budget["base_tris_max"]))
    _need_passed(L, "ld-fbx-report.json", ["checks.triangles_as_h21", "passed"], fails)
    pre = L.get("meshes_pre_export")
    if not isinstance(pre, dict) or not pre:
        fails.append("ld-fbx-report.json#meshes_pre_export: нет ключа")
    else:
        for m, v in sorted(pre.items()):
            nd, tris = _dig(v, "near_degenerate_triangles"), _dig(v, "triangles")
            if not isinstance(nd, (int, float)) or not isinstance(tris, (int, float)) or tris <= 0:
                fails.append("ld-fbx-report.json#meshes_pre_export.%s.near_degenerate_triangles/.triangles: нет ключа"
                             % m)
            elif nd / tris > NEAR_DEGENERATE_MAX:
                fails.append("ld-fbx-report.json#meshes_pre_export.%s.near_degenerate_triangles = %d из %d (> 0,1 %%)"
                             % (m, nd, tris))
    for name in ("seams-report.json", "close-report.json"):
        rep = _need(R, name, fails)
        if rep is not None:
            _need_passed(rep, name, ["passed"], fails)
    return fails, []


def _gate_uv(card, R, ctx):
    fails = []
    U = _need(R, "uv-report.json", fails)
    if U is not None:
        _need_passed(U, "uv-report.json", ["checks.raster_overlap_px", "checks.island_gap_px_at_4k",
                                           "checks.no_folded_uv_triangles"], fails)
    return fails, []


def _gate_tex(card, R, ctx):
    fails = []
    shas = _accepted_shas(card)
    M = _need(R, "ld-maps-report.json", fails)
    T = _need(R, "textures-report.json", fails)
    TA = _need(R, "ld-team-accent-report.json", fails)
    prefix = None
    if M is not None:
        _need_passed(M, "ld-maps-report.json", ["passed", "checks.matid_values_valid", "checks.matid_decodes_to_labels_4k",
                                                "checks.orm_metallic_binary_per_class_4k"], fails)
        outs = M.get("outputs") if isinstance(M.get("outputs"), dict) else {}
        prefix = next((m.group(1) for m in (re.fullmatch(r"(T_.+_H2LD)_2K_BC\.png", k) for k in outs) if m), None)
        if prefix is None:
            fails.append("ld-maps-report.json#outputs: нет T_<Key>_H2LD_2K_BC.png")
        else:
            for x in ("BC", "ORM", "MatID", "Edge"):
                name = "%s_2K_%s.png" % (prefix, x)
                if x == "Edge" and name not in outs and "%s_2K_EdgeMask.png" % prefix in outs:
                    name = "%s_2K_EdgeMask.png" % prefix
                o = outs.get(name)
                if not isinstance(o, dict):
                    fails.append("ld-maps-report.json#outputs.%s: нет ключа" % name)
                    continue
                if o.get("px") != PX_2K:
                    fails.append("ld-maps-report.json#outputs.%s.px = %s ≠ [2048, 2048]" % (name, o.get("px")))
                if o.get("sha256") not in shas:
                    fails.append("ld-maps-report.json#outputs.%s.sha256 нет в accepted_object" % name)
            n_name = "%s_2K_N.png" % prefix
            n_sha = _dig(outs, n_name, "sha256")
            pin = _dig(M, "pins", "2K_N", "sha256")
            if n_sha is None:
                fails.append("ld-maps-report.json#outputs.%s.sha256: нет ключа" % n_name)
            else:
                if n_sha != pin:
                    fails.append("мост N: ld-maps-report.json#outputs.%s.sha256 ≠ #pins.2K_N.sha256" % n_name)
                if n_sha not in shas:
                    fails.append("ld-maps-report.json#outputs.%s.sha256 нет в accepted_object" % n_name)
                if T is not None:
                    touts = T.get("outputs") if isinstance(T.get("outputs"), dict) else {}
                    bake_n = next((v for k, v in touts.items() if isinstance(v, dict) and v.get("sha256") == n_sha
                                   and "OpenGL" not in k), None)
                    if bake_n is None:
                        fails.append("textures-report.json#outputs: нет карты N с sha256 моста (pins.2K_N)")
                    elif bake_n.get("px") != PX_2K:
                        fails.append("textures-report.json#outputs.<N>.px = %s ≠ [2048, 2048]" % bake_n.get("px"))
    if T is not None:
        _need_passed(T, "textures-report.json", ["checks.sizes_2k", "checks.dx_equals_opengl_g_inverted_2k",
                                                 "checks.normal_length_2k", "checks.orm_occlusion_baked_not_constant"],
                     fails)
    if TA is not None:
        _need_passed(TA, "ld-team-accent-report.json", ["passed"], fails)
        if prefix is not None:
            name = "%s_TeamAccent_2K.png" % prefix
            o = _dig(TA, "outputs", name)
            if not isinstance(o, dict):
                fails.append("ld-team-accent-report.json#outputs.%s: нет ключа" % name)
            else:
                if o.get("px") != PX_2K:
                    fails.append("ld-team-accent-report.json#outputs.%s.px = %s ≠ [2048, 2048]" % (name, o.get("px")))
                if o.get("sha256") not in shas:
                    fails.append("ld-team-accent-report.json#outputs.%s.sha256 нет в accepted_object" % name)
    return fails, []


def _gate_rig(card, R, ctx):
    fails = []
    rig = _need(R, "rig-report.json", fails)
    if rig is not None:
        _need_passed(rig, "rig-report.json", ["passed", "checks.bones_and_parents_as_profile", "checks.max_influences",
                                              "checks.no_unweighted_vertices"], fails)
    pr = _need(R, "probes-report.json", fails)
    if pr is not None:
        _need_passed(pr, "probes-report.json", ["passed"], fails)
        pl = pr.get("plausible") if isinstance(pr.get("plausible"), dict) else {}
        # N из probes-report.json#total (прежние 7 + расширенные пробы рига без skipped, RB-08); отчёт без total
        # (прогон до расширенных проб) — прежние 7/7
        tot = pr.get("total") if isinstance(pr.get("total"), dict) else {}
        for kind in ("blend", "fbx"):
            keys = [k for k in pl if k.endswith("-" + kind)]
            if not keys:
                fails.append("probes-report.json#plausible: нет ключа <content_key>-h2-%s" % kind)
            elif any(pl[k] != tot.get(k, 7) for k in keys):
                fails.append("probes-report.json#plausible.*-%s = %s ≠ %s" % (
                    kind, [pl[k] for k in keys], "/".join(str(tot.get(k, 7)) for k in keys)))
        if _dig(pr, "validate_clip_v2", "result") != "pass":
            fails.append("probes-report.json#validate_clip_v2.result = %s ≠ pass" % _dig(pr, "validate_clip_v2", "result"))
    vs = _need(R, "validate-skeletal-mesh-v2.json", fails)
    if vs is not None and vs.get("result") != "pass":
        fails.append("validate-skeletal-mesh-v2.json#result = %s ≠ pass" % vs.get("result"))
    _need_passed(ctx["ld"], "ld-fbx-report.json", ["checks.bones_and_parents_as_h21", "checks.bone_heads_tails_as_h21",
                                                   "checks.positions_and_uv0_per_loop_as_h21"], fails)
    return fails, []


def _texture_candidates(ue_name):
    """Имя UE текстуры → варианты файлов look-dev: T_<Key>_H2LD_<X> → T_<Key>_H2LD_2K_<X>.png (генерический) или
    T_<Key>_H2LD_<X>_2K.png (TeamAccent, раскладка форка); остальное (T_UM_MatLUT_<C>) — <имя>.dds / .png."""
    if "_H2LD_" in ue_name or "_H3LD_" in ue_name:
        stage = "_H2LD_" if "_H2LD_" in ue_name else "_H3LD_"
        return [ue_name.replace(stage, stage[:-1] + "_2K_", 1) + ".png", ue_name + "_2K.png"]
    return [ue_name + ".dds", ue_name + ".png"]


def _ue_texture_groups(entries):
    """UE_NAMES.textures заявки → группы альтернатив: «{A,B}» раскрывается, «X (или _Y)» — X или X с последним
    сегментом _Y (T_<Key>_H2LD_Edge (или _EdgeMask))."""
    groups = []
    for e in entries or []:
        if not isinstance(e, str):
            continue
        m = re.fullmatch(r"\s*(\S+)\s*(?:\((?:или|or)\s+(_\w+)\)\s*)?", e)
        if not m:
            continue
        base, alt = m.group(1), m.group(2)
        b = re.fullmatch(r"(.*)\{([^}]*)\}(.*)", base)
        names = [b.group(1) + x.strip() + b.group(3) for x in b.group(2).split(",")] if b else [base]
        for n in names:
            alts = [n] + ([re.sub(r"_[A-Za-z0-9]+$", alt, n)] if alt else [])
            groups.append(alts)
    return groups


def _gate_names(card, R, ctx):
    fails, skipped = [], []
    L, ac, prof = ctx["ld"], ctx["asset_card"], ctx["profile"]
    # (1) имена файлов = UE_NAMES заявки
    ue = (ac or {}).get("UE_NAMES") if isinstance((ac or {}).get("UE_NAMES"), dict) else None
    if ue is None:
        skipped.append("(1) UE_NAMES: %s" % (ctx["asset_card_warn"] or "в заявке нет UE_NAMES"))
    else:
        for field, rkey in (("skeletal_mesh", "skeletal_fbx"), ("base", "base_fbx")):
            want = ue.get(field)
            got = _dig(L, "exports", rkey, "path")
            if want and (not isinstance(got, str) or Path(got).name != want + ".fbx"):
                fails.append("(1) ld-fbx-report.json#exports.%s.path = %s ≠ UE_NAMES.%s %s.fbx"
                             % (rkey, got and Path(got).name, field, want))
        files = set(Path(o["path"]).name for o in card["accepted_object"])
        for name in ("ld-maps-report.json", "ld-team-accent-report.json", "ld-fbx-report.json"):
            p = R.path(name)
            tdir = p.parent.parent / "textures" if p else None
            if tdir is not None and tdir.is_dir():
                files |= {f.name for f in tdir.iterdir()}
        for alts in _ue_texture_groups(ue.get("textures")):
            if not any(c in files for a in alts for c in _texture_candidates(a)):
                fails.append("(1) UE_NAMES.textures %s: нет файла %s в textures/ look-dev"
                             % (" | ".join(alts), " | ".join(c for a in alts for c in _texture_candidates(a))))
    # (2) меши внутри FBX = блок meshes bake-профиля; (4) один слот = materials.atlas
    pre = L.get("meshes_pre_export") if isinstance(L.get("meshes_pre_export"), dict) else {}
    meshes = (prof or {}).get("meshes") if isinstance((prof or {}).get("meshes"), dict) else None
    atlas = _dig(prof, "materials", "atlas")
    if prof is None:
        skipped.append("(2), (4) bake-профиль: %s" % ctx["profile_warn"])
    else:
        if meshes is None:
            fails.append("(2) bake-профиль %s#meshes: нет ключа" % ctx["profile_rel"])
        elif set(pre) != set(meshes.values()):
            fails.append("(2) ld-fbx-report.json#meshes_pre_export = %s ≠ профиль #meshes %s"
                         % (sorted(pre), sorted(meshes.values())))
        if not atlas:
            fails.append("(4) bake-профиль %s#materials.atlas: нет ключа" % ctx["profile_rel"])
        else:
            for m, v in sorted(pre.items()):
                if _dig(v, "material_slots") != [atlas]:
                    fails.append("(4) ld-fbx-report.json#meshes_pre_export.%s.material_slots = %s ≠ [%s]"
                                 % (m, _dig(v, "material_slots"), atlas))
    rig = R.get("rig-report.json")
    if rig is None:
        fails.append("(4), (5) rig-report.json: нет в reports карточки (нет отчёта = FAIL, §4)")
    else:
        _need_passed(rig, "rig-report.json", ["checks.material_slots", "checks.unit_scale_1_and_height"], fails)
    # (3) объект арматуры
    arm = _dig(L, "roundtrip", "ld", "skeletal", "armature_objects")
    if arm != [ARMATURE_OBJECT]:
        fails.append("(3) ld-fbx-report.json#roundtrip.ld.skeletal.armature_objects = %s ≠ [%s]" % (arm, ARMATURE_OBJECT))
    # (5) пресет, масштаб, фронт
    if _dig(L, "exports", "settings", "preset", "name") != FBX_PRESET:
        fails.append("(5) ld-fbx-report.json#exports.settings.preset.name = %s ≠ %s"
                     % (_dig(L, "exports", "settings", "preset", "name"), FBX_PRESET))
    usf = _dig(L, "exports", "settings", "unit_scale_factor_after_patch")
    if not isinstance(usf, (int, float)) or abs(usf - 1.0) > 1e-9:
        fails.append("(5) ld-fbx-report.json#exports.settings.unit_scale_factor_after_patch = %s ≠ 1" % usf)
    _need_passed(L, "ld-fbx-report.json", ["checks.export_frame_face_points_along_rotated_front_ue_plus_x"], fails)
    # (5) рост — верх тела без оружия (F41, F78): FIGURE_HEIGHT_M ± 1 %; деталь тела выше головы (рога) — по
    # FIGURE_BOUNDS_TOP_M заявки ± 1 %, если он выше бюджета
    h = (ac or {}).get("FIGURE_HEIGHT_M")
    if not isinstance(h, (int, float)) or h <= 0:
        skipped.append("(5) рост: %s" % (ctx["asset_card_warn"] or "в заявке нет FIGURE_HEIGHT_M"))
    else:
        skel = _dig(L, "roundtrip", "ld", "skeletal", "meshes") or {}
        body = (meshes or {}).get("body") or next((m for m in skel if m.endswith("_Body")), None)
        top = _dig(skel, body, "bounds_m", "max") if body else None
        top = top[2] if isinstance(top, list) and len(top) == 3 else None
        b = (ac or {}).get("FIGURE_BOUNDS_TOP_M")
        if top is None:
            fails.append("(5) ld-fbx-report.json#roundtrip.ld.skeletal.meshes.%s.bounds_m.max: нет ключа" % body)
        elif abs(top / h - 1) > HEIGHT_TOL and not (isinstance(b, (int, float)) and b > h * (1 + HEIGHT_TOL)
                                                     and abs(top / b - 1) <= HEIGHT_TOL):
            fails.append("(5) рост: верх тела без оружия %s = %.4f м ≠ FIGURE_HEIGHT_M %.4f ± 1 %%%s"
                         % (body, top, h, "" if b is None else " (и ≠ FIGURE_BOUNDS_TOP_M %s ± 1 %%)" % b))
    return fails, skipped


GATE_RECOMPUTE = {"G-TOPO": _gate_topo, "G-UV": _gate_uv, "G-TEX": _gate_tex, "G-RIG": _gate_rig,
                  "G-NAMES": _gate_names}


def recompute_gates(card, repo, asset_card=None):
    """Пересчёт машинных гейтов модели по отчётам (RB-05). Возвращает ({гейт: {status, why, partial}}, предупреждения).
    Пусто — пересчёт неприменим (не модель, проп, нет ld-fbx-report.json): причина в предупреждениях."""
    if card.get("kind") != "model":
        return {}, []
    if card["gates"].get("G-RIG", {}).get("status") == "n/a":
        return {}, ["гейты пропа (candidate-report, §4 «Проп») по отчётам не пересчитываются — статусы карточки"]
    R = _Reports(card, repo)
    ld = R.get("ld-fbx-report.json")
    if ld is None:
        return {}, ["нет ld-fbx-report.json в reports: гейты не пересчитаны (ассет вне генерического H2 — форк, "
                    "таблица соответствия §12.2)"]
    ac, ac_warn = (asset_card, None) if isinstance(asset_card, dict) else load_asset_card(card, repo, asset_card)
    budget = dict(POLY_BUDGET_DEFAULT)
    pb = (ac or {}).get("POLY_BUDGET")
    if isinstance(pb, dict):
        budget.update({k: pb[k] for k in ("figure_tris_max", "base_tris_max") if k in pb})
    prof, prof_rel, prof_warn = None, None, None
    man = _read_json(R.path("ld-fbx-report.json").parent / "run-manifest.json")
    prof_rel = _dig(man, "source_profile", "path") if man else None
    if not prof_rel:
        prof_warn = "нет <LD>/reports/run-manifest.json#source_profile.path"
    else:
        prof = _read_json(repo / prof_rel)
        if prof is None or prof.get("_unreadable"):
            prof, prof_warn = None, "профиль %s не найден или не читается" % prof_rel
    ctx = {"ld": ld, "asset_card": ac, "asset_card_warn": ac_warn, "poly_budget": budget, "profile": prof,
           "profile_rel": prof_rel, "profile_warn": prof_warn}
    out, warns = {}, []
    if ac_warn:
        warns.append("гейты: %s — POLY_BUDGET по умолчанию %s, UE_NAMES и рост G-NAMES не сверены"
                     % (ac_warn, POLY_BUDGET_DEFAULT))
    for g, fn in GATE_RECOMPUTE.items():
        fails, skipped = fn(card, R, ctx)
        out[g] = {"status": "FAIL" if fails else "PASS", "why": fails, "partial": bool(skipped)}
        if skipped:
            warns.append("%s пересчитан не целиком: %s" % (g, "; ".join(skipped)))
    return out, warns


def gate_errors(card, repo, asset_card=None):
    """Статус машинного гейта в карточке против пересчёта по отчётам: FAIL отчётов при PASS карточки — ошибка; PASS
    полного пересчёта при FAIL карточки — тоже (гейт ставится по отчёту, а не по впечатлению, §4)."""
    errs = []
    res, _ = recompute_gates(card, repo, asset_card)
    for g, r in res.items():
        st = (card["gates"].get(g) or {}).get("status")
        if st == "PASS" and r["status"] == "FAIL":
            errs.append("gates.%s: в карточке PASS, пересчёт по отчётам — FAIL: %s" % (g, "; ".join(r["why"])))
        elif st == "FAIL" and r["status"] == "PASS" and not r["partial"]:
            errs.append("gates.%s: в карточке FAIL, пересчёт по отчётам — PASS (решающие ключи §4 в норме): статус "
                        "гейта ставится по отчёту" % g)
    return errs


OUTPUT_NULLABLE = ("clip", "verdict_reason", "known_issues")  # строгий вывод приёмщика (_output_schema.py)
OUTPUT_NULLABLE_GATE = ("note", "source_defect")


def strip_output_nulls(card):
    """Карточка из строгого вывода приёмщика (_output_schema.py) заполняет необязательные поля
    значением null: null = поля нет. Возвращает копию без них (файл карточки не меняется)."""
    if not isinstance(card, dict):
        return card
    out = {k: v for k, v in card.items() if not (k in OUTPUT_NULLABLE and v is None)}
    if isinstance(out.get("gates"), dict):
        out["gates"] = {g: ({k: x for k, x in v.items() if not (k in OUTPUT_NULLABLE_GATE and x is None)}
                            if isinstance(v, dict) else v) for g, v in out["gates"].items()}
    return out


def validate(card, schema, check_files=False, repo=REPO, use_jsonschema=True, asset_card=None):
    """Возвращает (ошибки, допустимые вердикты | None, правила, score | None). asset_card — путь к asset-card.yaml или
    его словарь (по умолчанию art/pipeline-candidates/<ASSET_ID>/asset-card.yaml) для пересчёта гейтов."""
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
        errs += gate_errors(card, repo, asset_card)
    return errs, allowed, rules, score


def needs_second(card, allowed, score):
    """Любой kind (модель, концепт, клип): pass со score в [8,0; 8,5) неустойчив — нужен второй приёмщик другим
    профилем (решение скилла по калибровке 2026-10-09, раунд 3: правило распространено на concept и anim)."""
    return (card.get("kind") in DIMS and allowed == {"pass"} and score is not None
            and THRESHOLD <= score < STABLE_PASS)


def pair_errors(a, b, same_profile_ok=False):
    """Сверка двух карточек одной приёмки (первый и второй приёмщик). same_profile_ok — запасной путь, когда второй
    профиль не запустился после пробы или его полосы нет (Z-Code GLM-5.3-Flash до `zcode login zai`, side_models.py):
    второй приёмщик того же профиля, но в новом контексте."""
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
                    help="проверить файлы (sha256 accepted_object, кадры, frames.json, tone.json; пути от корня репо) "
                         "и пересчитать машинные гейты модели по отчётам")
    ap.add_argument("--repo-root", default=str(REPO), help=argparse.SUPPRESS)
    ap.add_argument("--no-jsonschema", action="store_true", help="принудительно встроенная проверка схемы")
    ap.add_argument("--second", help="card-2.json второго приёмщика (другой профиль, те же кадры): итог по минимуму")
    ap.add_argument("--same-profile-ok", action="store_true",
                    help="с --second: второй приёмщик того же профиля (другой профиль не запустился после пробы)")
    ap.add_argument("--final-json", help="с --second: записать итог пары (unmatched.acceptance-final/1)")
    ap.add_argument("--asset-card", help="с --check-files: asset-card.yaml для пересчёта гейтов (по умолчанию "
                                         "art/pipeline-candidates/<ASSET_ID>/asset-card.yaml)")
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
    results = [validate(c, schema, a.check_files, Path(a.repo_root), not a.no_jsonschema, a.asset_card) for c in cards]
    if a.check_files:
        for pth, c in zip(paths, cards):
            try:
                for w in file_warnings(strip_output_nulls(c), Path(a.repo_root), a.asset_card):
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
