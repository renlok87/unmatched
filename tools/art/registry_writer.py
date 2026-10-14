#!/usr/bin/env python3
"""Один писатель реестров ассета по таблице статусов (references/new-character-registration.md §10, RA-26; C59).

Этап 7b писал запись docs/art-pipeline/asset-registry.json (файл форматирован вручную: компактные строки путей) и строки
docs/game-design/visual/03-asset-registry.csv (CRLF) самодельными скриптами в $W (находка C59 фигуры-проверки Beowulf
2026-10-14). Здесь — одна запись за раз, остальные строки файла не меняются ни на байт:

  entry  запись asset-registry.json из JSON-файла (--entry): заменяет запись с тем же id на её месте или добавляет в
         конец "assets"; пишется в стиле файла (ключи записи — по строке, словари и скаляры в одну строку, слои
         развёрнуты, каждый путь / evidence — одной строкой). Статус и стадия — по фазе таблицы §10 (--phase):
           0          «предложено», planned            (этап 0, references/intake-and-evidence.md §1)
           7b-frames  «технически импортировано», ue-editor-frames   (7b до упаковки: импорт и UE-кадры 7a — факт)
           7b-probe   «технически импортировано», live-packaged-probe (шаг 7.8, после осмотра кадров -Bench)
         Этапы 1–7a реестр не трогают; «художественно принято» исполнитель не пишет (нужен акт
         docs/game-design/evidence/(ART|GD)-NNN/…, HANDBOOK §0 п.3) — отказ. Нет status/stage в записи — берутся из
         таблицы, другие — отказ. Путь с "sha256": "auto" получает sha256 файла (/Game/… — .uasset в Content).
  rows   строки 03-asset-registry.csv из JSON-списка (--rows): строка с тем же id заменяется на месте, новая — в конец;
         колонки — ровно заголовок файла (13), окончания строк и BOM файла сохраняются. Фаза:
           7b-tech    status «технически импортировано», acceptance по умолчанию «нет»
           7b-art     status «художественно принято», acceptance обязан содержать «по делегированию» (ВР-17, после
                      осмотра листа K1/K2) или акт (ART|GD)-NNN
         Нет status в строке — из таблицы, другой — отказ.

    python tools/art/registry_writer.py entry --entry $W/registry-entry.json --phase 7b-frames [--dry-run]
    python tools/art/registry_writer.py rows --rows $W/csv-rows.json --phase 7b-art [--dry-run]

После записи: python tools/tripo-pipeline/validate_registry.py — новых ERROR против базовой линии нет (§5.1).
Код выхода: 0 — записано (или --dry-run), 2 — ошибка входа или отказ по таблице статусов.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = "docs/art-pipeline/asset-registry.json"
CSV_03 = "docs/game-design/visual/03-asset-registry.csv"
CONTENT = "unreal/Unmatched/Content"
TECH, ART, PROPOSED = "технически импортировано", "художественно принято", "предложено"
# §10 new-character-registration.md: фаза → (status, stage) записи asset-registry.json
ENTRY_PHASES = {"0": (PROPOSED, "planned"), "7b-frames": (TECH, "ue-editor-frames"),
                "7b-probe": (TECH, "live-packaged-probe")}
ROW_PHASES = {"7b-tech": TECH, "7b-art": ART}
ACT_RE = re.compile(r"\b(ART|GD)-\d{3}\b")
LIST_KEYS = ("evidence", "plannedPaths", "acceptanceEvidence")


class WriterError(Exception):
    pass


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


# ------------------------------------------------------------------------------------------------ asset-registry.json
def _line(o) -> str:
    return json.dumps(o, ensure_ascii=False)


def render_entry(obj: dict) -> str:
    """Запись в стиле asset-registry.json: отступ записи 4, ключи 6; слои развёрнуты (ключи слоя 10, пути 12 —
    по строке); evidence / plannedPaths / acceptanceEvidence — по строке на объект; остальное — в одну строку."""
    out = ["    {"]
    keys = list(obj)
    for i, k in enumerate(keys):
        v, comma = obj[k], "," if i < len(keys) - 1 else ""
        if k == "layers" and v:
            out.append('      "layers": [')
            for j, layer in enumerate(v):
                out.append("        {")
                lk = list(layer)
                for m, kk in enumerate(lk):
                    c2 = "," if m < len(lk) - 1 else ""
                    if kk == "paths" and layer[kk]:
                        out.append('          "paths": [')
                        out += ["            " + _line(x) + ("," if n < len(layer[kk]) - 1 else "")
                                for n, x in enumerate(layer[kk])]
                        out.append("          ]" + c2)
                    else:
                        out.append(f"          {_line(kk)}: {_line(layer[kk])}{c2}")
                out.append("        }" + ("," if j < len(v) - 1 else ""))
            out.append("      ]" + comma)
        elif k in LIST_KEYS and v:
            out.append(f"      {_line(k)}: [")
            out += ["        " + _line(x) + ("," if n < len(v) - 1 else "") for n, x in enumerate(v)]
            out.append("      ]" + comma)
        else:
            out.append(f"      {_line(k)}: {_line(v)}{comma}")
    out.append("    }")
    return "\n".join(out)


def entry_span(lines: list, asset_id: str) -> tuple[int, int] | None:
    """(первая, последняя) строка записи с этим id: «    {» … «    }» / «    },»."""
    want = f'      "id": {_line(asset_id)},'
    hits = [i for i, ln in enumerate(lines) if ln == want]
    if not hits:
        return None
    if len(hits) > 1:
        raise WriterError(f"{asset_id}: {len(hits)} записей с этим id")
    start = hits[0] - 1
    if lines[start] != "    {":
        raise WriterError(f"{asset_id}: запись не в стиле файла (нет «    {{» перед id) — правка руками")
    end = start + 1
    while end < len(lines) and lines[end] not in ("    },", "    }"):
        end += 1
    if end >= len(lines):
        raise WriterError(f"{asset_id}: не найден конец записи")
    return start, end


def sha_of(path: str, repo: Path) -> str:
    p = repo / CONTENT / (path[len("/Game/"):] + ".uasset") if path.startswith("/Game/") else repo / path
    if not p.is_file():
        raise WriterError(f'"sha256": "auto": нет файла {p}')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fill_auto_sha(entry: dict, repo: Path) -> int:
    n = 0
    refs = [r for layer in entry.get("layers") or [] for r in layer.get("paths") or []]
    refs += [r for k in LIST_KEYS for r in entry.get(k) or []]
    for r in refs:
        if isinstance(r, dict) and r.get("sha256") == "auto":
            r["sha256"] = sha_of(r["path"], repo)
            n += 1
    return n


def check_entry_phase(entry: dict, phase: str) -> None:
    if phase not in ENTRY_PHASES:
        raise WriterError(f"--phase {phase!r}: запись реестра пишется только на фазах {', '.join(ENTRY_PHASES)} "
                          "(§10: этапы 1–7a реестр не трогают)")
    status, stage = ENTRY_PHASES[phase]
    if entry.get("status") == ART or any((x or {}).get("status") == ART for x in entry.get("layers") or []):
        raise WriterError(f"«{ART}» исполнитель не пишет: нужен акт docs/game-design/evidence/(ART|GD)-NNN/… "
                          "(HANDBOOK §0 п.3); пометка «по делегированию» — только в 03 и карточках приёмки")
    for k, want in (("status", status), ("stage", stage)):
        if entry.get(k) is not None and entry[k] != want:
            raise WriterError(f"{k} {entry[k]!r} не по таблице §10 для фазы {phase}: {want!r}")
    if entry.get("status") is None or entry.get("stage") is None:
        # на место соседних записей: … "instances", "status", "stage", "ownership" …
        items = [(k, v) for k, v in entry.items() if k not in ("status", "stage")]
        keys = [k for k, _ in items]
        at = next((keys.index(k) + 1 for k in ("instances", "parent", "category", "name", "id") if k in keys), 0)
        items[at:at] = [("status", status), ("stage", stage)]
        entry.clear()
        entry.update(items)


def write_entry(repo: Path, entry: dict, phase: str, registry: Path | None = None, dry_run: bool = False) -> dict:
    aid = entry.get("id")
    if not isinstance(aid, str) or not re.fullmatch(r"ASSET-[A-Z0-9-]+-\d{3}", aid):
        raise WriterError(f"id записи {aid!r}: нужен ASSET-<…>-NNN")
    check_entry_phase(entry, phase)
    filled = fill_auto_sha(entry, repo)
    path = registry or repo / REGISTRY
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    lines = text.replace("\r\n", "\n").split("\n")
    old = json.loads(text)
    span = entry_span(lines, aid)
    block = render_entry(entry).split("\n")
    if span:
        start, end = span
        if lines[end].endswith(","):
            block[-1] += ","
        lines[start:end + 1] = block
        action = "replaced"
    else:
        try:
            head = lines.index('  "assets": [')
            close = next(i for i in range(head + 1, len(lines)) if lines[i] == "  ]")
        except (ValueError, StopIteration) as exc:
            raise WriterError(f"{path}: не найден массив \"assets\" в стиле файла") from exc
        if lines[close - 1] == "    }":
            lines[close - 1] = "    },"
        lines[close:close] = block
        action = "appended"
    new_text = "\n".join(lines)
    new = json.loads(new_text)
    got = next(a for a in new["assets"] if a.get("id") == aid)
    if got != entry:
        raise WriterError("запись после записи не совпадает с входом (стиль файла?)")
    others_old = [a for a in old["assets"] if a.get("id") != aid]
    others_new = [a for a in new["assets"] if a.get("id") != aid]
    if others_old != others_new or {k: v for k, v in old.items() if k != "assets"} != \
            {k: v for k, v in new.items() if k != "assets"}:
        raise WriterError("другие записи изменились бы — отказ")
    if not dry_run:
        path.write_bytes((b"\xef\xbb\xbf" if raw.startswith(b"\xef\xbb\xbf") else b"") +
                         new_text.replace("\n", nl).encode("utf-8"))
    return {"file": path.as_posix(), "id": aid, "action": action, "status": entry["status"], "stage": entry["stage"],
            "sha256_filled": filled, "dry_run": dry_run}


# ---------------------------------------------------------------------------------------- 03-asset-registry.csv
def csv_line(row: dict, fields: list, nl: str) -> str:
    buf = io.StringIO()
    csv.DictWriter(buf, fields, lineterminator=nl).writerow(row)
    return buf.getvalue()


def check_row_phase(row: dict, phase: str) -> None:
    if phase not in ROW_PHASES:
        raise WriterError(f"--phase {phase!r}: строки 03 пишутся на фазах {', '.join(ROW_PHASES)} (§10: шаг 7.8)")
    want = ROW_PHASES[phase]
    if not row.get("status"):
        row["status"] = want
    elif row["status"] != want:
        raise WriterError(f"{row.get('id')}: status {row['status']!r} не по таблице §10 для фазы {phase}: {want!r}")
    acc = row.get("acceptance") or ""
    if phase == "7b-tech" and not acc:
        row["acceptance"] = "нет"
    if phase == "7b-art" and "по делегированию" not in acc and not ACT_RE.search(acc):
        raise WriterError(f"{row.get('id')}: «{ART}» в 03 — только «по делегированию <дата> (ВР-17)» после осмотра "
                          "листа K1/K2 или с актом (ART|GD)-NNN в acceptance")


def write_rows(repo: Path, rows: list, phase: str, csv_path: Path | None = None, dry_run: bool = False) -> dict:
    path = csv_path or repo / CSV_03
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    nl = "\r\n" if "\r\n" in text else "\n"
    fields = next(csv.reader(io.StringIO(text)))
    lines = text.split(nl)
    trailing = lines[-1] == ""
    if trailing:
        lines = lines[:-1]
    if len(list(csv.reader(io.StringIO(text)))) != len(lines):
        raise WriterError(f"{path}: значение с переводом строки внутри — построчная запись невозможна, правка руками")
    ids = {}
    for i, ln in enumerate(lines[1:], 1):
        rec = next(csv.reader(io.StringIO(ln)), None)
        if rec:
            ids.setdefault(rec[0], []).append(i)
    actions = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("id"):
            raise WriterError(f"строка без id: {row!r}"[:120])
        extra, missing = sorted(set(row) - set(fields)), [f for f in fields if f not in row and f not in
                                                          ("status", "acceptance")]
        if extra or missing:
            raise WriterError(f"{row['id']}: колонки не как в заголовке 03 (лишние {extra}, нет {missing})")
        check_row_phase(row, phase)
        new_line = csv_line(row, fields, nl)[:-len(nl)]
        if "\n" in new_line.replace(nl, ""):
            raise WriterError(f"{row['id']}: перевод строки внутри значения")
        hit = ids.get(row["id"])
        if hit and len(hit) > 1:
            raise WriterError(f"{row['id']}: {len(hit)} строк с этим id в 03")
        if hit:
            lines[hit[0]] = new_line
            actions.append({"id": row["id"], "action": "replaced", "line": hit[0] + 1})
        else:
            lines.append(new_line)
            ids[row["id"]] = [len(lines) - 1]
            actions.append({"id": row["id"], "action": "appended", "line": len(lines)})
    out = nl.join(lines) + (nl if trailing else "")
    parsed = list(csv.DictReader(io.StringIO(out)))
    if {len(r) for r in parsed} != {len(fields)}:
        raise WriterError("после записи не у всех строк по %d колонок" % len(fields))
    if not dry_run:
        path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + out.encode("utf-8"))
    return {"file": path.as_posix(), "rows": actions, "columns": len(fields), "dry_run": dry_run}


def main(argv=None) -> int:
    _utf8_streams()
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("entry", help="запись asset-registry.json")
    e.add_argument("--entry", required=True, help="JSON записи (поля как у соседних записей реестра)")
    e.add_argument("--phase", required=True, choices=sorted(ENTRY_PHASES))
    e.add_argument("--registry", default=None, help=f"файл реестра (по умолчанию {REGISTRY})")
    r = sub.add_parser("rows", help="строки 03-asset-registry.csv")
    r.add_argument("--rows", required=True, help="JSON-список строк (ключи = заголовок 03)")
    r.add_argument("--phase", required=True, choices=sorted(ROW_PHASES))
    r.add_argument("--csv", default=None, help=f"файл 03 (по умолчанию {CSV_03})")
    for p in (e, r):
        p.add_argument("--repo", default=str(REPO))
        p.add_argument("--dry-run", action="store_true", help="проверить и показать, файл не писать")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    repo = Path(a.repo)
    try:
        if a.cmd == "entry":
            res = write_entry(repo, load_json(Path(a.entry)), a.phase, Path(a.registry) if a.registry else None,
                              a.dry_run)
        else:
            data = load_json(Path(a.rows))
            rows = data.get("rows") if isinstance(data, dict) else data
            if not isinstance(rows, list):
                raise WriterError("--rows: нужен JSON-список строк (или {\"rows\": [...]})")
            res = write_rows(repo, rows, a.phase, Path(a.csv) if a.csv else None, a.dry_run)
    except (WriterError, OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(res, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
