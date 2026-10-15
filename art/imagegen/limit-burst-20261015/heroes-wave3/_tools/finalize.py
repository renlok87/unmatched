"""Record byte-preserved generated images; no retouching or shared registry writes."""
from pathlib import Path
import hashlib
import json
import sys
from datetime import datetime, timezone
from PIL import Image

ROOT = Path(__file__).resolve().parents[5]
PACKAGES = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def generation_record(key, package, review, candidate):
    original = Path(candidate["original_path"])
    saved = package / candidate["image"]
    prompt_path = package / candidate["prompt_file"]
    with Image.open(saved) as im:
        width, height = im.size
        mode = im.mode
    ref = "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
    return {
        "id": key + "-limit-burst-20261015-g" + str(candidate.get("attempt", 1)),
        "card_id": "AN-151", "proposed_asset_id": review["asset_id"],
        "registered_before_generation": True, "stage": review["stage"], "view": review["view"],
        "attempt": candidate.get("attempt", 1), "tool": "image_gen.imagegen", "mode": "built-in",
        "references": [{"path": ref, "sha256": sha(ROOT / ref), "role": "craftsmanship only"}],
        "prompt_file": prompt_path.relative_to(ROOT).as_posix(), "prompt_sha256": sha(prompt_path),
        "original_path": original.as_posix(), "saved_path": saved.relative_to(ROOT).as_posix(),
        "sha256": sha(saved), "bytes": saved.stat().st_size, "width": width, "height": height,
        "colour_mode": mode, "byte_identical_to_original": sha(original) == sha(saved),
        "selected": candidate.get("selected", review["selected"]), "status": review["status"],
        "date_recorded_utc": datetime.now(timezone.utc).isoformat(),
        "ledger": "Coordinator owns shared visual ledger; this is one built-in image generation, null price/balances.",
    }


def finalize(key):
    package = PACKAGES / key
    review = json.loads((package / "review.json").read_text(encoding="utf-8"))
    before = json.loads((package / "source-hashes-before.json").read_text(encoding="utf-8"))
    sources = []
    for record in before:
        after = sha(ROOT / record["path"])
        sources.append({**record, "after_sha256": after, "unchanged": record["sha256"] == after})
    candidates = review.get("generations", [review])
    generations = [generation_record(key, package, review, candidate) for candidate in candidates]
    prompt_validation = []
    for record in generations:
        sent_prompt = (ROOT / record["prompt_file"]).read_text(encoding="utf-8")
        clean = sent_prompt.startswith("Use case:") and "CHECKLIST" not in sent_prompt and "wiglaf" not in sent_prompt.lower() and "Return:" not in sent_prompt
        prompt_validation.append({"prompt_file": record["prompt_file"], "clean_core_only_with_optional_correction": clean})
        assert clean, "Foreign task instructions found in sent prompt"
    generation = next((record for record in generations if record["selected"]), generations[-1])
    width, height = generation["width"], generation["height"]
    relative = generation["saved_path"]
    dump(package / "generation-records.json", generations)
    verification = {
        "asset_id": review["asset_id"],
        "status": review["status"],
        "source_unchanged": all(record["unchanged"] for record in sources),
        "source_checks": sources,
        "package_writes_only": True,
        "outside_folder": [],
        "generated_image_byte_preserved": all(record["byte_identical_to_original"] for record in generations),
        "image_inspected": True,
        "image_inspected_by": "producing Codex agent (self-review, not independent pipeline acceptance)",
        "checklist": review["checklist"],
        "limitations": review["limitations"],
        "pipeline_acceptance": False,
        "prompt_validation": prompt_validation,
        "three_d_game_or_rig_ready": False,
        "shared_registry_ledger_or_source_files_modified": False,
        "background_processes_started": [],
    }
    verification["automated_checks"] = []
    for record in generations:
        check_path = package / ("checks/design-front-g" + str(record["attempt"]) + "/checks-report.json")
        if check_path.exists():
            verification["automated_checks"].append({"report": check_path.relative_to(ROOT).as_posix(), "result": json.loads(check_path.read_text(encoding="utf-8-sig"))})
    dump(package / "verification.json", verification)
    (package / "prompts.md").write_text(
        "# Exact generation prompts\n\nBuilt-in `image_gen.imagegen`; one call per image.\n\n"
        + "Image input, craftsmanship only: `art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png`.\n\n"
        + "\n\n".join("## g" + str(record["attempt"]) + "\n\n```text\n" + (ROOT / record["prompt_file"]).read_text(encoding="utf-8") + "\n```" for record in generations) + "\n\n"
        + "No card scans, avatars or commercial game frames were image inputs.\n",
        encoding="utf-8",
    )
    (package / "README.md").write_text(
        "# " + review["title"] + "\n\n" + review["summary_ru"] + "\n\n"
        + "Статус: **" + review["status"] + "**. Вызовов встроенного image_gen: " + str(len(generations)) + "; выбранный/сохраняемый PNG: "
        + str(width) + "×" + str(height) + ". Оригинал скопирован побайтно без ретуши, обрезки и ресайза.\n\n"
        + "Самопроверка 2026-10-15: PNG открыт исполнителем. Это не независимая приёмка пайплайна.\n\n"
        + "Ограничения:\n\n" + "\n".join("- " + item for item in review["limitations"]) + "\n\n"
        + "Ни моделью, ни игровым ассетом, ни принятым rig-compatible результатом пакет не объявляется. "
        + "Общие реестры, карточки существующих ассетов, ledger, Unreal и git не изменялись. "
        + "Источники и точный промпт записаны рядом; хэши в `manifest-sha256.json`.\n",
        encoding="utf-8",
    )
    manifest = {}
    for path in sorted(package.rglob("*")):
        if path.is_file() and path.name != "manifest-sha256.json":
            manifest[path.relative_to(package).as_posix()] = {"sha256": sha(path), "bytes": path.stat().st_size}
    dump(package / "manifest-sha256.json", manifest)
    assert verification["source_unchanged"], "An input changed during this generation"
    assert verification["generated_image_byte_preserved"], "Generated image was not preserved"
    print(json.dumps({"key": key, "image": relative, "width": width, "height": height, "source_unchanged": True, "manifest_files": len(manifest)}, ensure_ascii=False))


if __name__ == "__main__":
    for package_key in sys.argv[1:]:
        finalize(package_key)
