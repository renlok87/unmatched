#!/usr/bin/env python3
"""Строгие схемы вывода приёмщика для `codex exec --output-schema` (профиль «Sol 6.1 xhigh», этапы 1, 4, 6).

`codex exec --output-schema` передаёт схему модели как strict json_schema. Строгий режим требует: у каждого объекта
`additionalProperties: false` и все свойства в `required` (необязательное поле — тип с `null`); нет `allOf`/`if`/`then`,
`propertyNames`, `minProperties`, `uniqueItems`, `minLength`, `minItems`, `minimum`/`maximum`/`multipleOf` и
просмотров вперёд в `pattern`. Полная схема карточки `asset-acceptance-2.schema.json` всё это использует, поэтому
приёмщику даётся производная схема своего вида карточки (kind фиксирован: гейты и измерения — фиксированные свойства):

    tools/art/acceptance/asset-acceptance-2.output-model.schema.json     этап 4 (модель)
    tools/art/acceptance/asset-acceptance-2.output-concept.schema.json   этап 1 (концепт-лист)
    tools/art/acceptance/asset-acceptance-2.output-anim.schema.json      этап 6 (клип)

Судья — по-прежнему `validate_card.py` по полной схеме и правилам вердикта. Он принимает null у полей, которые строгий
вывод обязан заполнить (clip у модели и концепта, verdict_reason при pass, known_issues, gates.*.note,
gates.*.source_defect): null = поля нет (`validate_card.strip_output_nulls`). Ответ приёмщика пишется в card.json
без изменений.

    python tools/art/acceptance/_output_schema.py --write    # пересобрать три файла из полной схемы
    python tools/art/acceptance/_output_schema.py --check    # код 1, если файлы устарели
    python tools/art/acceptance/_output_schema.py --workflow-args <model|concept|anim> \
        [--item <ASSET_ID>=<каталог приёмки>[=<label>]]… [--out <args.json>]

--workflow-args — аргументы workflow `second-acceptor` (acceptance-and-blender.md §8.3) одним ASCII-JSON:
{"kind", "items": [{asset, evidence, label, prompt}], "schema"}; схема — та же строгая выходная схема вида, но без
`description`/`title` (кириллица описаний ломалась при печати через cp1251, C34 проверочного прогона 2026-10-14;
модели они не нужны — поля и enum те же). label по умолчанию — acceptor2-<ASSET_ID>-r<N> (клип —
acceptor2-<ASSET_ID>-<Clip>-r<N>) по имени каталога; prompt — <каталог>/acceptor-prompt-2.md. Без --out — в stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FULL = HERE / "asset-acceptance-2.schema.json"
KINDS = ("model", "concept", "anim")
SCHEMA_ID = {"model": "unmatched.asset-acceptance/2", "concept": "unmatched.concept-acceptance/1",
             "anim": "unmatched.anim-acceptance/1"}
CYCLES = {"model": ["r1", "r2", "r3", "r4"], "concept": ["r1", "r2", "r3", "r4"], "anim": ["r1", "r2", "r3"]}
GATES = {"model": ["G-TOPO", "G-UV", "G-TEX", "G-RIG", "G-NAMES"], "concept": ["G-CHECKS"],
         "anim": ["G-VALIDATE", "G-CONTACT", "G-MANIFEST"]}
DIMS = {"model": ["S", "F", "T", "D"], "concept": ["S", "C", "Q", "P"], "anim": ["R", "C", "D", "L"]}
FORBIDDEN = {"allOf", "if", "then", "else", "not", "propertyNames", "minProperties", "maxProperties", "uniqueItems",
             "minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum", "multipleOf",
             "patternProperties", "dependentRequired", "$schema", "$id"}


def path_for(kind: str) -> Path:
    return HERE / ("asset-acceptance-2.output-%s.schema.json" % kind)


def obj(props: dict, desc: str | None = None) -> dict:
    o = {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
    if desc:
        o["description"] = desc
    return o


def s(pattern: str | None = None, nullable: bool = False, desc: str | None = None) -> dict:
    o = {"type": ["string", "null"] if nullable else "string"}
    if pattern:
        o["pattern"] = pattern
    if desc:
        o["description"] = desc
    return o


def arr(items: dict, desc: str | None = None) -> dict:
    o = {"type": "array", "items": items}
    if desc:
        o["description"] = desc
    return o


def build(kind: str, full: dict | None = None) -> dict:
    """Строгая схема вывода приёмщика для kind. Шаблоны (pattern) и enum берутся из полной схемы, кроме repo_path
    (в нём просмотры вперёд — его проверяет validate_card.py)."""
    if kind not in KINDS:
        raise ValueError("kind must be one of %s" % (KINDS,))
    full = full or json.loads(FULL.read_text(encoding="utf-8"))
    P = full["properties"]
    item_pat = P["rework_fix_list"]["items"]["properties"]["item"]["pattern"]
    gate = obj({
        "status": {"type": "string", "enum": list(full["$defs"]["gate"]["properties"]["status"]["enum"])},
        "source": s(desc="отчёт (путь от корня) или команда, давшая статус"),
        "note": s(nullable=True, desc="файл#ключ = значение; null — без заметки"),
        "source_defect": {"type": ["boolean", "null"],
                          "description": "только FAIL у модели: true — дефект исходника Tripo; иначе null"},
    })

    def dim(nullable=False):
        return obj({"value": {"type": ["number", "null"] if nullable else "number",
                              "description": "0 | 0.5 | 1 | 1.5 | 2" + (" | null (проп без рига)" if nullable else "")},
                    "rationale": s(), "frames": arr(s())})

    props = {
        "schema": {"type": "string", "enum": [SCHEMA_ID[kind]]},
        "kind": {"type": "string", "enum": [kind]},
        "asset_id": s(P["asset_id"]["pattern"]),
        "clip": (s(P["clip"]["pattern"], desc=P["clip"]["description"]) if kind == "anim"
                 else {"type": "null", "description": "только kind=anim; здесь null"}),
        "cycle": {"type": "string", "enum": list(CYCLES[kind])},
        "date": s(P["date"]["pattern"]),
        "previous_card": s(nullable=True, desc="card.json предыдущего цикла (путь от корня репо); null у r1"),
        "accepted_object": arr(obj({"path": s(), "sha256": s(P["accepted_object"]["items"]["properties"]["sha256"]["pattern"])})),
        "frames": obj({"dir": s(), "files": arr(s(P["frames"]["properties"]["files"]["items"]["pattern"]))}),
        "reports": arr(s()),
        "gates": obj({g: gate for g in GATES[kind]}),
        "scores": obj({d: dim(nullable=(kind == "model" and d == "D")) for d in DIMS[kind]}),
        "score": {"type": "number"},
        "verdict": {"type": "string", "enum": list(P["verdict"]["enum"])},
        "verdict_reason": s(nullable=True, desc="обязательно (не null) при verdict != pass"),
        "rework_fix_list": arr(obj({"item": s(item_pat), "frame": s(), "fix": s(), "tool": s()})),
        "known_issues": arr(obj({"item": s(item_pat), "frame": s(), "note": s()})),
        "acceptor": obj({"profile": {"type": "string",
                                     "enum": list(P["acceptor"]["properties"]["profile"]["enum"])},
                         "session_id": s()}),
        "executor_session_id": s(),
        "decided_by": s(),
        "status_note": s(),
    }
    missing = set(P) - set(props)
    if missing:  # the full schema grew a field: the output schema must follow it
        raise ValueError("output schema misses fields of the full schema: %s" % sorted(missing))
    out = obj(props, "Строгая схема вывода приёмщика (kind=%s) для codex exec --output-schema; производная от "
                     "tools/art/acceptance/asset-acceptance-2.schema.json (_output_schema.py). Судья — "
                     "validate_card.py." % kind)
    out["title"] = "asset-acceptance-2 output (%s)" % kind
    return out


def strict_problems(schema: dict, path: str = "$") -> list:
    """Нарушения правил строгого режима (для тестов и --check)."""
    out = []
    if isinstance(schema, dict):
        for k in schema:
            if k in FORBIDDEN:
                out.append("%s: keyword %s" % (path, k))
        if "pattern" in schema and "(?" in schema["pattern"]:
            out.append("%s: lookaround in pattern" % path)
        t = schema.get("type")
        if t == "object" or (isinstance(t, list) and "object" in t):
            if schema.get("additionalProperties") is not False:
                out.append("%s: additionalProperties must be false" % path)
            if sorted(schema.get("required", [])) != sorted(schema.get("properties", {})):
                out.append("%s: every property must be required" % path)
        for k, v in schema.items():
            if k == "properties":
                for name, sub in v.items():
                    out += strict_problems(sub, "%s.%s" % (path, name))
            elif isinstance(v, dict):
                out += strict_problems(v, "%s/%s" % (path, k))
            elif isinstance(v, list):
                for i, sub in enumerate(v):
                    if isinstance(sub, dict):
                        out += strict_problems(sub, "%s/%s[%d]" % (path, k, i))
    return out


def dumps(schema: dict) -> str:
    return json.dumps(schema, ensure_ascii=False, indent=2) + "\n"


STRIP_KEYWORDS = ("description", "title")


def ascii_schema(schema):
    """Схема без ключевых слов description/title (имена свойств не трогаются); остальное — как есть."""
    if isinstance(schema, list):
        return [ascii_schema(x) for x in schema]
    if not isinstance(schema, dict):
        return schema
    out = {}
    for k, v in schema.items():
        if k in STRIP_KEYWORDS:
            continue
        if k == "properties" and isinstance(v, dict):
            out[k] = {name: ascii_schema(sub) for name, sub in v.items()}
        else:
            out[k] = ascii_schema(v)
    return out


def default_label(asset: str, evidence: str) -> str:
    """acceptor2-<ASSET_ID>-r<N> по каталогу приёмки …/<YYYYMMDD>[-sheet|-front]-r<N>[/<Clip>] (§8.3)."""
    parts = [p for p in str(evidence).replace("\\", "/").split("/") if p]
    for i in range(len(parts) - 1, -1, -1):
        m = re.search(r"-(r\d+)$", parts[i])
        if m:
            clip = parts[i + 1] if i + 1 < len(parts) else None
            return "acceptor2-%s-%s%s" % (asset, clip + "-" if clip else "", m.group(1))
    return "acceptor2-%s" % asset


def workflow_args(kind: str, items: list | None = None) -> dict:
    """{"kind", "items", "schema"} для workflow second-acceptor; ASCII-безопасно (json.dumps(ensure_ascii=True))."""
    items = [dict(it) for it in (items or [])]
    for it in items:
        if not it.get("asset") or not it.get("evidence"):
            raise ValueError("item needs asset and evidence: %r" % (it,))
        it["evidence"] = str(it["evidence"]).replace("\\", "/").rstrip("/")
        it.setdefault("label", default_label(it["asset"], it["evidence"]))
        it.setdefault("prompt", it["evidence"] + "/acceptor-prompt-2.md")
    return {"kind": kind, "items": items, "schema": ascii_schema(build(kind))}


def parse_item(text: str) -> dict:
    parts = text.split("=")
    if len(parts) not in (2, 3) or not all(parts):
        raise ValueError("--item expects <ASSET_ID>=<evidence dir>[=<label>], got %r" % text)
    item = {"asset": parts[0], "evidence": parts[1]}
    if len(parts) == 3:
        item["label"] = parts[2]
    return item


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--workflow-args", choices=KINDS, metavar="KIND",
                   help="ASCII-аргументы workflow second-acceptor для вида карточки (model, concept, anim)")
    ap.add_argument("--item", action="append", default=[], help="<ASSET_ID>=<каталог приёмки>[=<label>] (повторяется)")
    ap.add_argument("--out", default=None, help="файл аргументов (по умолчанию stdout)")
    a = ap.parse_args(argv)
    if a.workflow_args:
        try:
            text = json.dumps(workflow_args(a.workflow_args, [parse_item(x) for x in a.item]), ensure_ascii=True,
                              indent=2) + "\n"
        except ValueError as exc:
            print("ERROR: %s" % exc, file=sys.stderr)
            return 2
        if a.out:
            Path(a.out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.out).write_text(text, encoding="ascii", newline="\n")
            print("wrote", Path(a.out).as_posix())
        else:
            sys.stdout.write(text)
        return 0
    bad = 0
    for kind in KINDS:
        text = dumps(build(kind))
        p = path_for(kind)
        if a.write:
            p.write_text(text, encoding="utf-8", newline="\n")
            print("wrote", p.as_posix())
        elif not p.is_file() or p.read_text(encoding="utf-8") != text:
            print("STALE", p.as_posix(), "- run _output_schema.py --write", file=sys.stderr)
            bad = 1
    return bad


if __name__ == "__main__":
    sys.exit(main())
