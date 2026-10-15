"""Finalize only Wiglaf's corrective 1a run, preserving all prior stage records."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
from PIL import Image

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[4]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def rel(path):
    return path.relative_to(ROOT).as_posix()

context = read(PACKAGE / "fix1-context.json")
history = ROOT / context["history"]
snapshot = history / "preexisting-package"
inventory = read(history / "snapshot-inventory.json")
review = read(PACKAGE / "fix1-review.json")
calls = read(PACKAGE / "fix1-calls.json")
old_records = read(snapshot / "generation-records.json")
old_prompts = read(snapshot / "prompts/concept-prompts.json")
old_verification = read(snapshot / "verification.json")
sources = read(PACKAGE / "source-hashes-before.json")
base = old_prompts["1a/design-front/g1"]
correction = (ROOT / "docs/game-design/visual/06-tasks/prompts/ASSET-WIGLAF-001-concept.fix1.codex.md").read_text(encoding="utf-8").split("```text\n", 1)[1].split("```", 1)[0].rstrip("\n")
assert len(calls) <= 2
assert [c["attempt"] for c in calls] == list(range(3, 3 + len(calls)))
new_records = []
prompts = dict(old_prompts)
checks = []
raw_checks = []
now = datetime.now(timezone.utc).isoformat()
for call in calls:
    attempt = call["attempt"]
    image = PACKAGE / ("concepts/wiglaf-design-front-g" + str(attempt) + ".png")
    original = Path(call["original_path"])
    prompt_file = PACKAGE / ("prompts/design-front-g" + str(attempt) + ".txt")
    prompt = prompt_file.read_text(encoding="utf-8")
    assert prompt == base + "\n" + correction, "The exact base CORE or approved CORRECTION changed"
    assert sha(image) == sha(original)
    with Image.open(image) as im:
        width, height = im.size
    prompt_key = "1a/design-front/g" + str(attempt)
    assert prompt_key not in prompts
    prompts[prompt_key] = prompt
    new_records.append({
        "id": "ASSET-WIGLAF-001-1a-design-front-g" + str(attempt),
        "card_id": "ASSET-WIGLAF-001", "stage": "1a", "view": "design-front", "side_view": None,
        "attempt": attempt, "tool": "image_gen.imagegen", "mode": "generate",
        "references": [{"path": p, "sha256": sha(ROOT / p)} for p in context["call_inputs"]],
        "prompt_key": prompt_key, "prompt_file": rel(prompt_file), "prompt_sha256": sha(prompt_file),
        "correction": correction.splitlines()[1:], "original_path": original.as_posix(),
        "saved_path": rel(image), "sha256": sha(image), "width": width, "height": height,
        "date": now, "selected": False,
        "best_failed_attempt": attempt == review["best_attempt"],
        "selection_scope": "unaccepted corrective attempts only; canonical accepted g2 remains selected",
        "status": "unaccepted corrective attempt; limit exhausted; requested S correction not achieved",
    })
    raw_checks.append({"original_path": original.as_posix(), "saved_path": rel(image), "sha256": sha(image), "byte_identical": True})
    report = PACKAGE / ("checks/design-front-g" + str(attempt) + "/checks-report.json")
    result = read(report)
    assert result["inputs"][0]["sha256"] == sha(image)
    checks.append({"view": "design-front", "generation": "g" + str(attempt), "exit_code": call["checker_exit_code"], "report": rel(report), "summary": result["summary"]})

best_failed = next(r for r in new_records if r["best_failed_attempt"])
canonical = next(r for r in old_records if r["stage"] == "1a" and r["attempt"] == 2)
assert sha(PACKAGE / "design/wiglaf-front.png") == canonical["sha256"]
assert sha(PACKAGE / "design/checks-report.json") == sha(snapshot / "design/checks-report.json")
final_report = PACKAGE / "checks/design-front-g3/final-attempt-report.json"
assert read(final_report)["inputs"][0]["sha256"] == best_failed["sha256"]
checks.append({"view": "design-front", "generation": "best failed g" + str(review["best_attempt"]), "exit_code": review["final_checker_exit_code"], "report": rel(final_report), "summary": read(final_report)["summary"], "note": "This temporary candidate check was saved before restoring canonical g2 and its original design/checks-report.json byte-for-byte."})

source_checks = []
for source in sources[context["source_block_index"]]["inputs"]:
    actual = sha(ROOT / source["path"])
    source_checks.append({**source, "after_sha256": actual, "unchanged": source["sha256"] == actual})
assert all(s["unchanged"] for s in source_checks)
allowed_mutations = {"README.md", "prompts.md", "source-hashes-before.json", "generation-records.json", "verification.json", "manifest-sha256.json", "prompts/concept-prompts.json"}
preserved = []
for old in inventory["files"]:
    if "snapshot_path" in old:
        assert sha(PACKAGE / old["snapshot_path"]) == old["sha256"], "History snapshot changed"
    if old["path"] not in allowed_mutations:
        assert sha(PACKAGE / old["path"]) == old["sha256"], "Immutable prior artifact changed: " + old["path"]
        preserved.append(old)
dump(PACKAGE / "generation-records.json", old_records + new_records)
dump(PACKAGE / "prompts/concept-prompts.json", prompts)
appendix = "\n\n---\n\n# Corrective design-front 1a fix1 — 2026-10-15\n\nBuilt-in image_gen. Previous exact prompts above remain unchanged. Base CORE is identical to 1a/design-front/g1; each call appends exactly the root-authored fix1 block.\n\n"
for record in new_records:
    appendix += "## " + record["prompt_key"] + "\n\nreferences, in call order:\n\n" + "\n".join("- `" + r["path"] + "`, SHA256 `" + r["sha256"] + "`" for r in record["references"]) + "\n\n```text\n" + prompts[record["prompt_key"]] + "\n```\n\n"
appendix += "## Проверка и ограничения\n\n" + review["summary_ru"] + "\n\n" + "\n".join("- " + s for s in review["limitations"]) + "\n"
(PACKAGE / "prompts.md").write_text((snapshot / "prompts.md").read_text(encoding="utf-8") + appendix, encoding="utf-8")
verification = {
    "card_id": "ASSET-WIGLAF-001", "stage": "1a corrective attempts", "status": "correction exhausted; canonical accepted g2 retained; sheet-r1 rejected; asset requires coordinator escalation", "date": now,
    "source_unchanged": True, "source_checks": source_checks, "outside_folder": [],
    "outside_folder_note": "Built-in image_gen automatic originals in CODEX_HOME are preserved at their original absolute paths.",
    "checks": checks, "checklist": review["checklist"], "generations_per_view": {"design-front": 2 + len(calls)},
    "generation_limit_this_run": 2, "generation_limit_package_per_view": {"design-front": 4},
    "generations_this_run": len(calls), "counter_reset": False,
    "selected_per_view": {"design-front": "g2, previous accepted canonical design retained"},
    "selected_sha256": canonical["sha256"],
    "best_failed_candidate": {"attempt": review["best_attempt"], "path": best_failed["saved_path"], "sha256": best_failed["sha256"], "selected": False},
    "historical_selection_note": "Previous 1a and 1c generation records retain their original historical selected flags. Both new attempts are unselected and cannot be used as a new draft source.",
    "limit_reached": review["limit_reached"], "raw_copy_checks": raw_checks, "selected_copy_byte_identical": True,
    "limitations": review["limitations"], "candidate_visual_failures": review["candidate_visual_failures"],
    "history_archive": context["history"], "prior_metadata_preserved": True,
    "preexisting_immutable_files": preserved, "base_core_unchanged": True, "exact_root_correction": True,
    "prior_1c_status": "rejected sheet-r1; root views, sheet, reports and all originals remain unchanged historical artifacts of g2",
    "corrective_goal_achieved": False, "canonical_accepted_design_retained": True,
    "asset_only_escalation": True, "new_draft_authorized": False,
    "next_required_gates": ["coordinator handoff/stop for this asset: 1a attempt limit reached without requested S fix", "no new 1b or 1c using these unaccepted correction attempts"],
    "previous_runs": [old_verification],
    "execution": {"mode": "built-in image_gen", "retouch_resize_crop_reencode": False, "git_ledger_registry_tripo_unreal_services_used": False, "background_processes_started": []},
}
dump(PACKAGE / "verification.json", verification)
dump(PACKAGE / "provenance.json", {
    "asset_id": "ASSET-WIGLAF-001", "stage": "1a", "status": verification["status"],
    "fix_task": "docs/game-design/visual/06-tasks/prompts/ASSET-WIGLAF-001-concept.fix1.codex.md",
    "source_rejection": "art/pipeline-candidates/ASSET-WIGLAF-001/evidence/acceptance-concept/20261015-sheet-r1/card.json",
    "source_rejection_score": 7.5, "source_rejection_S": 1.5, "source_rejection_C": 0.5,
    "history_archive": context["history"], "current_selected_design": rel(PACKAGE / "design/wiglaf-front.png"),
    "current_selected_sha256": canonical["sha256"], "current_generation": 2,
    "best_failed_candidate": verification["best_failed_candidate"],
    "prior_design_g2_sha256": sources[context["source_block_index"]]["prior_design"]["sha256"],
    "prior_records_retained_unchanged": True, "prior_1c_views_retained_unchanged": True,
    "new_attempts_not_source_of_old_or_new_1b_or_1c": True, "image_inputs": context["call_inputs"],
    "approved_previous_design_read_only_context": True, "limits": verification["limitations"],
})
heading = "# Wiglaf — корректирующие попытки design-front 1a fix1\n\nСтатус: **коррекция S не достигнута, лимит исчерпан; прежний принятый 1a g2 сохранён; sheet-r1 отклонён**. ASSET-WIGLAF-001, 2026-10-15.\n\n"
heading += review["summary_ru"] + "\n\n"
heading += "Canonical `design/wiglaf-front.png` восстановлен побайтно как прежний принятый **g2**, SHA256 `" + canonical["sha256"] + "`; его `design/checks-report.json` также восстановлен побайтно. Новых вызовов: **" + str(len(calls)) + "/2**, всего design-front: **" + str(2 + len(calls)) + "/4**, без сброса счётчика. Лучший среди не прошедших кандидатов — g" + str(review["best_attempt"]) + " (`" + best_failed["saved_path"].split("concept-wiglaf-codex/", 1)[1] + "`), **selected=false**; g4 также selected=false. Ни один не заменяет canonical и не является источником нового draft.\n\n"
heading += "До изменений сохранена побайтная упаковка в `" + context["history"].split("concept-wiglaf-codex/", 1)[1] + "/preexisting-package/`; исходные записи 1a/1c, prompts и старые selected flags остаются в истории и generation-records. Текущий выбор определяется `verification.json#selected_per_view`. Все старые PNG 1a/1c и root-виды, sheet и reports оставлены побайтно.\n\n"
heading += "Приёмка sheet-r1 вернула 7.5 (S=1.5, C=0.5). Здесь предпринималась только коррекция S design-front, но требуемые зазоры не получены. Старый root-набор front/side/back/sheet ниже — **отклонённая историческая упаковка 1c принятого g2**. Противоречие росписи внутренней поверхности щита в side не исправлялось. Лимит 1a исчерпан: требуется handoff/стоп только этого ассета координатором; новый 1b/1c по g3/g4 не запускается.\n\n"
heading += "CORE не менялся; добавлен точный root-authored CORRECTION fix1. Единственный image input — Medusa craftsmanship reference. Прежний Wiglaf design и sheet просмотрены для самопроверки, но не подавались дополнительными image inputs. Все новые сырые PNG сохранены без ретуши/ресайза/обрезки/перекодирования.\n\nОграничения:\n\n" + "\n".join("- " + s for s in review["limitations"]) + "\n\nОбщие реестры, ledger, git, Tripo, Unreal и службы не использовались. Ни 1a, ни 1c самим исполнителем не приняты. Ниже неизменённый исторический README, который описывает прошлые этапы.\n\n---\n\n"
(PACKAGE / "README.md").write_text(heading + (snapshot / "README.md").read_text(encoding="utf-8"), encoding="utf-8")
manifest = {"files": [{"path": rel(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(PACKAGE.rglob("*")) if p.is_file() and p != PACKAGE / "manifest-sha256.json"]}
dump(PACKAGE / "manifest-sha256.json", manifest)
assert read(PACKAGE / "generation-records.json")[:len(old_records)] == old_records
for key, prompt in old_prompts.items():
    assert read(PACKAGE / "prompts/concept-prompts.json")[key] == prompt
for entry in manifest["files"]:
    assert sha(ROOT / entry["path"]) == entry["sha256"]
print(json.dumps({"canonical_generation": 2, "best_failed_attempt": review["best_attempt"], "new_calls": len(calls), "total_design_generations": 2 + len(calls), "canonical_sha256": canonical["sha256"], "best_failed_candidate_sha256": best_failed["sha256"], "manifest_files": len(manifest["files"]), "prior_immutable_files_verified": len(preserved), "sources_unchanged": True, "all_prior_records_retained": True, "corrective_goal_achieved": False}, ensure_ascii=False))
