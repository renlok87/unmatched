"""Register an existing design, without generating or modifying image bytes.

One-shot audit script for the explicitly scoped 2026-10-13 corrective run.
All writes are confined to this package. Run from the repository root with -B.
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys

PACKAGE = Path("art/imagegen/concept-winter-soldier-codex")
EXPECTED = "742d0d500316a0a2bea57583d55590d3a8a232b57973269084d379da4c65444a"
DESIGN = PACKAGE / "design/winter-soldier-front.png"
MUTABLE = (
    "generation-records.json", "prompts/concept-prompts.json", "prompts.md",
    "verification.json", "manifest-sha256.json", "README.md",
    "source-hashes-before.json", "design/checks-report.json",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_path(path):
    path.resolve().relative_to(PACKAGE.resolve())
    return path


def write_text(path, text):
    safe_path(path).parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, data):
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def byte_copy(source, target):
    safe_path(source)
    safe_path(target)
    assert not target.exists(), f"Refusing to overwrite: {target}"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    assert target.read_bytes() == source.read_bytes(), f"Copy differs: {target}"


def main():
    assert DESIGN.is_file() and digest(DESIGN) == EXPECTED
    records = read_json(PACKAGE / "generation-records.json")
    old_records = copy.deepcopy(records)
    assert isinstance(records, list) and len(records) < 4
    selected = [r for r in records if r.get("selected") and r.get("view") == "design-front"]
    assert len(selected) == 1
    source_record = selected[0]
    assert source_record["tool"].startswith("unstability.ai")
    old_verification = read_json(PACKAGE / "verification.json")
    historical_post = old_verification["design_source"]["post"]
    assert "rebg.py" in historical_post
    attempt = max(r["attempt"] for r in records if r["view"] == "design-front") + 1
    candidate = PACKAGE / f"concepts/winter-soldier-design-front-g{attempt}.png"
    assert not candidate.exists()
    now = dt.datetime.now(dt.timezone.utc)
    stamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    date = now.isoformat(timespec="seconds")
    archive = PACKAGE / "archive" / f"metadata-only-{stamp}"
    assert not archive.exists()
    run_dir = PACKAGE / "repair" / stamp
    run_dir.mkdir(parents=True, exist_ok=False)

    # Record the original inputs before touching any mutable metadata.
    png_before = {p.as_posix(): {"sha256": digest(p), "bytes": p.stat().st_size}
                  for p in sorted(PACKAGE.rglob("*.png"))}
    inputs = []
    metadata_before = {}
    absent = []
    for name in MUTABLE:
        source = PACKAGE / name
        if not source.is_file():
            absent.append(source.as_posix())
            continue
        entry = {"path": source.as_posix(), "sha256": digest(source),
                 "bytes": source.stat().st_size, "kind": "mutable_metadata",
                 "archive_path": (archive / name).as_posix()}
        metadata_before[name] = entry
        inputs.append(entry)
    for path, value in png_before.items():
        inputs.append({"path": path, **value, "kind": "existing_png"})
    palette = PACKAGE / "palette.json"
    inputs.append({"path": palette.as_posix(), "sha256": digest(palette),
                   "bytes": palette.stat().st_size, "kind": "unchanged_palette"})
    block = {"run_id": stamp, "date": date, "mode": "metadata-only registration",
             "generations_allowed": 0, "image_gen_calls_this_run": 0,
             "inputs": inputs, "absent_optional_metadata": absent,
             "outside_folder": [], "other_packages_opened": False,
             "reference_image_used": False}
    write_json(run_dir / "inputs-before.json", block)
    for name in metadata_before:
        byte_copy(PACKAGE / name, archive / name)
    write_json(archive / "snapshot-index.json", {
        "run_id": stamp, "date": date, "files": list(metadata_before.values())})
    source_hashes_path = PACKAGE / "source-hashes-before.json"
    if source_hashes_path.exists():
        source_hashes = read_json(source_hashes_path)
        if isinstance(source_hashes, list):
            source_hashes.append(block)
        else:
            source_hashes.setdefault("corrective_runs", []).append(block)
    else:
        source_hashes = {"schema": "unmatched.concept-source-hashes/1",
                         "corrective_runs": [block]}
    write_json(source_hashes_path, source_hashes)

    byte_copy(DESIGN, candidate)
    data = candidate.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", data[16:24])
    prompt_path = PACKAGE / "prompts/concept-prompts.json"
    prompts = read_json(prompt_path) if prompt_path.exists() else {}
    exact_prompt = source_record.get("prompt") or prompts[source_record["prompt_key"]]
    assert isinstance(exact_prompt, str) and exact_prompt
    for r in old_records:
        if "prompt" in r:
            if r["prompt_key"] in prompts:
                assert prompts[r["prompt_key"]] == r["prompt"]
            else:
                prompts[r["prompt_key"]] = r["prompt"]
    new_prompt_key = f"1a/design-front/g{attempt}"
    assert new_prompt_key not in prompts
    prompts[new_prompt_key] = exact_prompt
    new_record = {
        "id": f"ASSET-WINTER-SOLDIER-001-1a-design-front-g{attempt}",
        "card_id": "ASSET-WINTER-SOLDIER-001", "stage": "1a", "view": "design-front",
        "side_view": None, "attempt": attempt,
        "tool": "unstability.ai source; Claude rebg.py historical postprocess; metadata-only registration",
        "mode": "metadata-only registration of unstability.ai source after historical Claude rebg.py postprocess; zero generation calls",
        "references": [{"path": DESIGN.as_posix(), "sha256": EXPECTED}],
        "prompt_key": new_prompt_key, "correction": None,
        "original_path": DESIGN.resolve().as_posix(), "saved_path": candidate.as_posix(),
        "sha256": EXPECTED, "width": width, "height": height, "date": date, "selected": True,
        "checks": (PACKAGE / f"checks/design-front-g{attempt}/checks-report.json").as_posix(),
        "registration_only": True, "image_generations_this_run": 0,
        "image_gen_calls_this_run": 0, "prompt_historical_not_executed": True,
        "references_role": "byte-copy provenance only; no image generation references used in this run",
        "historical_provenance": {
            "source_service": "unstability.ai", "source_record_id": source_record["id"],
            "source_candidate": source_record["saved_path"], "source_candidate_sha256": source_record["sha256"],
            "postprocessor": "Claude: C:/tmp/concept-wave/rebg.py (historical, not executed now)",
            "post": historical_post,
            "documentation": (archive / "verification.json").as_posix() + "#design_source.post",
            "raw_frame": (PACKAGE / "design/winter-soldier-front-raw.png").as_posix(),
            "raw_frame_sha256": digest(PACKAGE / "design/winter-soldier-front-raw.png"),
            "lineage_note": "Historical candidate and raw frame have different hashes; their exact conversion chain is not reconstructed. The normalized design is registered from the current authoritative file.",
        },
    }
    for r in records:
        if r["view"] == "design-front":
            r["selected"] = False
    records.append(new_record)
    write_json(PACKAGE / "generation-records.json", records)
    write_json(prompt_path, prompts)

    runs = []
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")

    def run_checker(record, final=False):
        source = DESIGN if final else Path(record["saved_path"])
        out = PACKAGE / f"checks/design-front-g{record['attempt']}"
        temp_set = run_dir / f"temporary-design-front-g{record['attempt']}"
        temp_image = temp_set / "winter-soldier-front.png"
        if final:
            set_dir = DESIGN.parent
        else:
            assert not (out / "checks-report.json").exists()
            byte_copy(source, temp_image)
            set_dir = temp_set
        command = [sys.executable, "-B", "tools/art/concept/check_concept_views.py",
                   "--set", set_dir.as_posix(), "--key", "winter-soldier",
                   "--views", "front", "--role", "hero", "--min-top-pct", "4"]
        if not final:
            command += ["--out", out.as_posix()]
        result = subprocess.run(command, env=env, capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        report_path = (DESIGN.parent if final else out) / "checks-report.json"
        row = {"view": "design-front", "generation": f"g{record['attempt']}",
               "record_id": record["id"], "exit_code": result.returncode,
               "report": report_path.as_posix(), "final": final,
               "source_path": source.as_posix(), "source_sha256": digest(source),
               "command": command, "stdout": result.stdout, "stderr": result.stderr,
               "historical_candidate": not final and record is not new_record}
        if report_path.exists():
            report = read_json(report_path)
            assert report["inputs"][0]["sha256"] == digest(source)
            row["failed_items"] = [c["id"] for c in report["checks"] if c["result"] == "FAIL"]
            row["warnings"] = [c["id"] for c in report["checks"] if c["result"] == "WARN"]
        if not final:
            # Only this invocation's newly created byte copy is removed.
            assert digest(temp_image) == digest(source)
            safe_path(temp_image).unlink()
            safe_path(temp_set).rmdir()
            row["temporary_input_deleted_after_check"] = True
        runs.append(row)
        write_json(run_dir / "checker-runs.json", runs)
        print(json.dumps({"generation": row["generation"], "final": final,
                          "exit_code": result.returncode, "report": row["report"],
                          "stdout": result.stdout, "stderr": result.stderr}, ensure_ascii=False), flush=True)
        return result.returncode

    blocker = None
    # Check each registered historical concepts candidate, then the registration.
    for record in records:
        code = run_checker(record)
        if code not in (0, 1):
            blocker = f"Checker input/tool error for {record['id']}: {code}"
            break
    final_code = None
    if blocker is None:
        final_code = run_checker(new_record, final=True)  # Last checker invocation; no --out.
        if final_code not in (0, 1):
            blocker = f"Final checker input/tool error: {final_code}"

    png_after = []
    for path, before in png_before.items():
        p = Path(path)
        after = {"sha256": digest(p), "bytes": p.stat().st_size}
        assert before == after, f"Existing PNG changed: {p}"
        png_after.append({"path": path, "before": before, "after": after, "unchanged": True})
    assert DESIGN.read_bytes() == candidate.read_bytes()
    metadata_preserved = []
    for name, entry in metadata_before.items():
        archived = archive / name
        assert digest(archived) == entry["sha256"]
        metadata_preserved.append({**entry, "archived_byte_identical": True,
                                   "updated_in_place": digest(PACKAGE / name) != entry["sha256"]})
    assert digest(palette) == next(i["sha256"] for i in inputs if i["kind"] == "unchanged_palette")
    for old, current in zip(old_records, records):
        permitted = copy.deepcopy(old)
        permitted["selected"] = current["selected"]
        assert permitted == current, "Historical record changed beyond selected flag"

    checklist_items = [
        "one subject, one pedestal, no collage, no second view, no text, letters, logo or watermark",
        "strict front orthographic view, camera exactly level, no perspective or three-quarter turn; pedestal edge-on, no visible top",
        "whole subject and pedestal visible, nothing cropped; plain flat dark gray background",
        "rifle in figure's RIGHT hand (viewer LEFT); arms apart from torso, not T-pose or A-pose",
        "identity anchors: rifle in RIGHT hand, silver LEFT arm with red star, black tactical gear, lower-face mask",
        "palette main colours and accent; no team colour, coloured base ring or band",
    ]
    checklist = [{"view": "design-front", "item": item, "passed": None,
                  "status": "not_reassessed", "note": "В этой правке изображения разрешены только для хеширования и checker. Визуальная оценка не выполнялась; null не означает PASS или FAIL. Историческая заметка Claude сохранена в design_source.checklist_note."}
                 for item in checklist_items]
    verification = copy.deepcopy(old_verification)
    verification.update({
        "status": "proposed", "status_ru": "предложено", "source_unchanged": True,
        "source_unchanged_scope": "All pre-existing package PNGs and palette unchanged; original mutable metadata archived byte-for-byte.",
        "outside_folder": [], "image_gen_calls_this_run": 0, "image_generations_this_run": 0,
        "generations_allowed": 0, "generations": {"design-front": 0},
        "record_count": len(records), "generation_history": {"historical_external_generation_records": len(old_records),
            "metadata_registration_records_added_this_run": 1},
        "selected": {"view": "design-front", "record_id": new_record["id"], "candidate": candidate.as_posix(),
                     "sha256": EXPECTED, "original_path": DESIGN.resolve().as_posix()},
        "checks": runs, "final_checker_exit_code": final_code,
        "historical_checks": old_verification.get("checks", []),
        "historical_verification": (archive / "verification.json").as_posix(),
        "checklist": checklist, "checklist_completed": False, "limit_reached": [],
        "png_hash_preservation": png_after, "all_previous_pngs_unchanged": True,
        "registered_candidate_byte_identical_to_design": True,
        "mutable_metadata_archive": {"path": archive.as_posix(), "files": metadata_preserved},
        "prompt_provenance": {"key": new_prompt_key, "copied_from_record": source_record["id"],
                              "exact_historical_external_prompt": True, "executed_this_run": False},
        "limitations": [
            "Визуальная приёмка и новая визуальная проверка CHECKLIST не выполнялись; все passed=null обозначают непроверенные пункты.",
            "Исторические FAIL сохранены, повторная генерация запрещена. Технический PASS checker не является художественной приёмкой.",
            "Фактический размер 1280×1600 (4:5); исторически сервис был указан как 3:4. В этой правке размер не изменялся.",
            "Исторические кандидат u1 и raw имеют разные хеши; точная цепочка их преобразования не установлена. rebg.py не запускался.",
            "Референс качества из другого пакета не открывался, не хешировался и не использовался.",
        ], "blocker": blocker,
    })
    if final_code in (0, 1):
        final_report = read_json(DESIGN.parent / "checks-report.json")
        verification["selected_checker_summary"] = final_report["summary"]
        verification["selected_checker_warnings"] = [c for c in final_report["checks"] if c["result"] == "WARN"]
        verification["selected_framing_measurements"] = final_report["measurements"]["front"]["mask"]
    write_json(PACKAGE / "verification.json", verification)

    prompt_lines = ["# Промпты ASSET-WINTER-SOLDIER-001 — этап 1a", "",
                    f"Дата корректирующей регистрации: {date}.", "",
                    "В этой правке выполнена только регистрация метаданных. Генераций изображений и вызовов image_gen: **0**.",
                    "Все тексты ниже — точные исторические промпты внешнего источника; сейчас они не выполнялись.", ""]
    for r in records:
        registration = r.get("registration_only", False)
        prompt_lines += [f"## {r['prompt_key']}", "", f"Файл: `{r['saved_path']}`.",
                         f"Дата записи: {r['date']}. Инструмент: {r['tool']}.",
                         f"Режим: {r['mode']}.",
                         "referenced_image_paths для генерации: `[]`; в этой правке вызова генерации не было." if registration
                         else "Исторические referenced_image_paths (в порядке вызова): `[]` (text-to-image).",
                         "Вход регистрации — существующий нормализованный дизайн; references новой записи обозначают происхождение байтов." if registration
                         else "Историческая генерация unstability.ai; промпт взят из прежней записи без изменений.",
                         "", "```text", prompts[r["prompt_key"]], "```", ""]
    prompt_lines += ["## Проверка и ограничения", "",
                    "Зарегистрирован только front. Сравнение разных видов не проводилось.",
                    "Новый ключ g2 повторяет исторический внешний промпт u1 дословно; выполнения промпта сейчас не было.",
                    "Claude исторически нормализовал фон через rebg.py; это не операция данного запуска.",
                    "Текущий дизайн и прежние PNG сохранены байт-в-байт. Checker проверял временные копии кандидатов внутри пакета.",
                    "Визуальная приёмка и визуальная переоценка CHECKLIST не выполнены. Статус — предложено.", ""]
    write_text(PACKAGE / "prompts.md", "\n".join(prompt_lines))
    failures = [f"g{r['generation'][1:]}: код {r['exit_code']}, FAIL {', '.join(r.get('failed_items', [])) or 'нет'}"
                for r in runs if not r["final"]]
    readme = ["# Концепт-пакет ASSET-WINTER-SOLDIER-001", "",
              "Статус: **предложено** (proposed), этап 1a. Художественная приёмка не выполнялась.", "",
              "## Корректирующая регистрация существующего дизайна", "",
              f"Дата: {date}. Генераций изображений: **0**; вызовов image_gen: **0**.",
              f"Выбран `{candidate.relative_to(PACKAGE).as_posix()}` (запись g{attempt}, попытка {attempt}).",
              "Это новая неизменяемая байтовая копия уже существующего `design/winter-soldier-front.png`, а не новый результат генератора.",
              f"SHA256 обоих файлов: `{EXPECTED}`.",
              "Причина выбора: текущий нормализованный дизайн назначен пользователем авторитетным изображением этой волны.", "",
              "## Происхождение и сохранённая история", "",
              "Источник изображения — историческая генерация unstability.ai, UltraReal Fine-Tune v4 (Flux.1 D).",
              f"Историческая нормализация Claude: `{historical_post}`.",
              "rebg.py сейчас не запускался. Ранее нормализованный дизайн отличается по хешу от кандидата u1.",
              "Кандидат u1 и raw также различаются; точная цепочка между ними не восстановлена и не выдумывается.",
              "Старые записи сохранены полностью; изменены только флаги selected. Новая запись ссылается на существующий дизайн абсолютным original_path.",
              "Точный исторический внешний промпт скопирован в новый ключ; он не выполнялся в этой правке.",
              f"Исходные версии изменяемых метаданных сохранены байт-в-байт в `{archive.relative_to(PACKAGE).as_posix()}/`.",
              "palette.json, текущий дизайн, raw и все прежние PNG остались без изменений; before/after приведены в verification.json.", "",
              "## Технические проверки и ограничения", "",
              *[f"- {line}." for line in failures],
              f"- Финальный checker текущего design запущен последним без --out; код {final_code}.",
              "- Каждый кандидат проверен в собственном checks/design-front-gN. Временные наборы внутри пакета содержали байтовые копии winter-soldier-front.png и удалены после проверки; SHA256 в отчётах связывает их с кандидатами.",
              "- Исторические FAIL остаются историей; генерации и исправления PNG не выполнялись.",
              "- view.frame_top — WARN: верх 2,875% вместо минимум 4%. Измеренный низ подставки 98,312%, центр x51,836%; ядро задаёт y93% и x50%.",
              "- Фактический размер 1280×1600 (4:5), несмотря на историческое указание сервиса 3:4. Изменение размера запрещено.",
              "- CHECKLIST визуально не переоценивался: passed=null означает непроверенный пункт, а не положительный вердикт. Историческая заметка Claude сохранена отдельно.",
              "- Референс качества из другого пакета не открывался и не использовался. Отчёт checker не означает художественную приёмку.",
              f"- Блокер: {blocker or 'нет'}. outside_folder=[].", ""]
    write_text(PACKAGE / "README.md", "\n".join(readme))

    # Final preservation assertions, then the manifest is the last file written.
    for path, value in png_before.items():
        assert digest(Path(path)) == value["sha256"]
    assert DESIGN.read_bytes() == candidate.read_bytes()
    assert len(records) <= 4 and prompts[new_prompt_key] == exact_prompt
    for name, entry in metadata_before.items():
        assert digest(archive / name) == entry["sha256"]
    # Refresh final metadata-change flags after README/verification writes.
    for entry in verification["mutable_metadata_archive"]["files"]:
        entry["updated_in_place"] = (entry["path"].endswith("/manifest-sha256.json")
                                     or digest(Path(entry["path"])) != entry["sha256"])
    write_json(PACKAGE / "verification.json", verification)
    manifest_path = PACKAGE / "manifest-sha256.json"
    files = [{"path": p.relative_to(PACKAGE).as_posix(), "sha256": digest(p), "bytes": p.stat().st_size}
             for p in sorted(PACKAGE.rglob("*")) if p.is_file() and p != manifest_path]
    manifest = {"schema": "unmatched.concept-manifest/1", "generated_at": date,
                "path_base": PACKAGE.as_posix(), "files": files}
    write_json(manifest_path, manifest)
    assert {r["path"] for r in files} == {
        p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob("*") if p.is_file() and p != manifest_path}
    for row in files:
        path = PACKAGE / row["path"]
        assert digest(path) == row["sha256"] and path.stat().st_size == row["bytes"]
    print(json.dumps({"selected": candidate.as_posix(), "image_generations": 0,
                      "previous_pngs_preserved": len(png_before), "final_checker_exit_code": final_code,
                      "record_count": len(records), "manifest_verified_files": len(files),
                      "status": "proposed", "blocker": blocker}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
