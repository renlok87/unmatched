"""Record CP-31 source portraits and the actual failed call without runtime claims."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
from PIL import Image

WAVE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
KEYS = ["spike", "willow", "geralt-of-rivia", "philippa"]
REVIEWS = {
    "spike": {
        "identity": "Slicked platinum hair, pale angular adult face, half-smile, black leather lapels and red-over-black shirt preserve the broad project miniature cues. Facial planes and jacket details are generated interpretation, not an identical face.",
        "native80": "Platinum hair, brow/face planes, dark lapels and red shirt remain distinct; individual skin and leather marks do not resolve.",
        "native40": "Light hair/head silhouette and red shirt between dark lapels remain readable. Fine eyes, expression and leather stitching collapse into a few pixels.",
        "headroom": "About 6% above the hair, visibly less than the requested 18%; full head remains inside the full100 circle.",
        "detail_limit": "Fine skin/hair and leather detail disappears at 40 px; the portrait does not prove exact facial identity to an unfamiliar viewer.",
    },
    "willow": {
        "identity": "Long copper-red sculpted hair, green embroidered knit, purple top and simple necklace follow the current owner-design cues. Everyday form is shown without hands, spells or Dark Willow features.",
        "native80": "Red hair framing the face and green/purple costume remain readable; necklace and embroidery become small accents.",
        "native40": "Red hair, light central face, green shoulders and purple top remain distinct; pendant, individual eyes and floral embroidery are not reliably readable.",
        "headroom": "About 6% above the hair instead of the requested 18%; whole head and main hair tips remain inside the full100 circle.",
        "detail_limit": "The referenced figure is formally unaccepted (r2 score6.3) with no adjacent user override. Root specifically authorized this independent source-only portrait; this is not acceptance of that figure.",
    },
    "philippa": {
        "identity": "Short dark sculpted curls, high black-and-violet collar, dark gown and one pale-metal owl brooch preserve the broad project design. Hair/collar silhouette is clear, with generated differences in face and ornament.",
        "native80": "Dark curls, pale face, high violet collar and a pale brooch accent are distinct. Owl silhouette is small; individual feathers do not resolve.",
        "native40": "Dark hair and large violet collar framing the pale face remain readable. Brooch becomes a pale mark, not a reliable owl; fine eye and curl details are lost.",
        "headroom": "About 8% above the hair instead of the requested 18%; full hair and high collar fit inside the full100 circle.",
        "detail_limit": "Formal paired result remains return_to_stage_1 at7.5 despite a recorded user override to proceed. Portrait source generation does not change either record or authorize runtime import.",
    },
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def rel(path):
    return path.relative_to(ROOT).as_posix()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

now = datetime.now(timezone.utc).isoformat()
handoff = {"task_id": "CP-31", "template": "T-CODEX-PORTRAITSOURCE", "tool_calls_total": 4, "successful_images": 3, "failed_calls": 1, "correction_calls": 0, "note": "Coordinator owns shared ledger. Null prices/balances are unknown, not free. Geralt output moderation produced no PNG; no bypass/fallback used.", "packages": []}
package_results = []
for key in KEYS:
    package = WAVE / key
    preflight = read(package / "preflight.json")
    attempts = read(package / "attempts.json")
    assert len(attempts) == 1
    attempt = attempts[0]
    source_checks = []
    for record in read(package / "source-hashes-before.json"):
        after = sha(ROOT / record["path"])
        source_checks.append({**record, "after_sha256": after, "unchanged": after == record["sha256"]})
    assert all(r["unchanged"] for r in source_checks)
    prompt = package / attempt["prompt_file"]
    text = prompt.read_text(encoding="utf-8")
    assert text.startswith("Use case: stylized-concept\n") and "CHECKLIST" not in text and "wiglaf" not in text.lower()
    record = {"task_id": "CP-31", "template": "T-CODEX-PORTRAITSOURCE", "owner_slug": key, "game_name": preflight["game_name"], "date_recorded_utc": now,
        "tool": "image_gen.imagegen", "mode": "built-in", "stage": "portrait-source-only", "attempt": 1,
        "prompt_file": rel(prompt), "prompt_sha256": sha(prompt),
        "references": [{"path": preflight["reference"]["path"], "sha256": preflight["reference"]["sha256"], "role": "current project miniature design, broad identity/costume and craftsmanship cues only"}],
        "reference_status": preflight["reference_status"], "formal_card": preflight["formal_card"],
        "runtime_key_requested": "portrait:" + key, "runtime_imported": False, "runtime_accepted": False,
    }
    blocked = key == "geralt-of-rivia"
    if blocked:
        assert not (package / "portrait-source-candidate.png").exists()
        record.update({"status": "blocked by image generation service; no image produced", "selected": False, "error": attempt["error"], "original_path": None, "saved_path": None, "sha256": None, "dimensions": None})
        review = {"task_id": "CP-31", "status": record["status"], "reviewer": "producing Codex agent", "generated_image_inspected": False, "reference_inspected": True,
            "source_reference_limit": preflight["source_limit"], "native40_80_crop_review": "not applicable; no generated image exists", "generation_calls": 1, "correction_calls": 0,
            "limitations": ["HTTP400 moderation_blocked at output, category other; exact error and request ID in tool-error-g1.json.", "No generated image, source candidate, dimensions or crop proof can be supplied for this call.", "Current source uses a user override; formal card score6.3/return_to_stage_1 is unchanged.", "No prompt workaround, alternate generator or paid fallback was attempted."], "runtime_accepted": False}
        dims = None
        summary_ru = "Портрет Geralt of Rivia не создан: встроенный image_gen вернул HTTP400 moderation_blocked на этапе output (category other). Сохранены точный промпт, reference SHA, preflight, фактическая ошибка и request ID. PNG отсутствует; неуспешный вызов учитывается как один вызов, не как готовый ассет."
    else:
        image = package / attempt["image"]
        original = Path(attempt["original_path"])
        selected = package / "portrait-source-candidate.png"
        assert sha(original) == sha(image) == sha(selected)
        with Image.open(selected) as im:
            dims = list(im.size)
            mode = im.mode
        assert dims[0] == dims[1]
        for size in [40, 80, 160]:
            with Image.open(package / ("review/circle-full100-" + str(size) + ".png")) as im:
                assert im.size == (size, size)
        assert read(package / "review/crop-contract.json")["source_sha256"] == sha(selected)
        record.update({"status": "source-candidate-only", "selected": True, "original_path": original.as_posix(), "saved_path": rel(image), "selected_path": rel(selected), "sha256": sha(selected), "dimensions": dims, "colour_mode": mode, "byte_identical_to_original": True})
        details = REVIEWS[key]
        review = {"task_id": "CP-31", "status": "source-candidate-only", "reviewer": "producing Codex agent self-review, not independent acceptance", "reviewed_at_utc": now,
            "generated_image_inspected": True, "source_dimensions": dims, "source_sha256": sha(selected), "generation_calls": 1, "correction_calls": 0,
            "observations": {"identity": details["identity"], "style": "Sculpted coherent hair/costume masses and detailed matte painted surfaces. Facial skin rendering is highly realistic; physical resin provenance and a pixel-identical original face are not claimed.", "source_framing": details["headroom"], "full100_circle": "Whole head/hair and high collar where present remain inside the circle of diameter100% of the square. Outer shoulders and lower chest corners are removed as expected. No tighter zoom/crop was tested.", "native80": details["native80"], "native40": details["native40"], "grayscale80_160": "Hair, face planes and collar remain visible in grayscale previews; colour-only costume distinctions and fine ornament are reduced.", "background": "Plain charcoal studio backdrop with slight tonal variation; no UI, text, frame, watermark or scenery observed. Exact flatness is not claimed."},
            "checklist": [{"item": "one adult head-and-shoulders portrait; no hands, pedestal or text/UI", "passed": True}, {"item": "whole head/hair/high collar safe in full100 circle", "passed": True}, {"item": "requested about18% upper breathing room", "passed": False, "note": details["headroom"]}, {"item": "broad identity and costume cues readable at native80/40", "passed": True, "note": "Fine identity details are limited; source review is not runtime acceptance."}],
            "limitations": [details["headroom"], details["detail_limit"], "Outer shoulder/chest corners are cut by the circular mask; keep full100 without tighter zoom.", "No runtime widget, DPI, interaction state, UE import or independent acceptance tested by this producing agent."],
            "actual_head_or_identity_failure_requiring_correction_observed": False, "runtime_accepted": False, "independent_review_pending": True}
        summary_ru = "Оригинальный портретный исходник " + preflight["game_name"] + " создан одним вызовом встроенного image_gen по собственному current design-front. Голова/волосы и ворот помещаются в full100 circle; цветной и серый обзор 80/160 и native40/80 осмотрены. Дополнительный вызов не использован: обрезки головы или потери основных признаков не обнаружено."
    dump(package / "generation-record.json", record)
    dump(package / "self-review.json", review)
    verification = {"task_id": "CP-31", "owner_slug": key, "status": record["status"], "reference_status": preflight["reference_status"], "source_unchanged": True, "source_checks": source_checks,
        "source_candidate_exists": not blocked, "generated_image_byte_preserved": not blocked, "byte_preservation_note": "not applicable: no generated image" if blocked else "Original, raw copy and selected source have identical SHA256.",
        "all_sent_prompts_clean": True, "native_crop_review_completed": not blocked, "crop_contract": "full100; entire square downsampled, no crop or zoom", "runtime_imported": False, "runtime_accepted": False, "three_d_or_pipeline_gates_advanced": False,
        "independent_acceptance": False, "shared_registry_ledger_git_or_source_files_modified": False, "long_lived_processes_started": [], "limitations": review["limitations"]}
    dump(package / "verification.json", verification)
    (package / "README.md").write_text("# " + preflight["game_name"] + " — CP-31 portrait source\n\nСтатус: **" + record["status"] + "**.\n\n" + summary_ru + "\n\nReference status: **" + preflight["reference_status"] + "**. Формальная карточка остаётся `" + preflight["formal_card"]["verdict"] + "`, score " + str(preflight["formal_card"]["score"]) + "; пользовательский override не превращён в formal pass.\n\n" + ("Размер: " + str(dims[0]) + "×" + str(dims[1]) + ". `original-g1.png` и `portrait-source-candidate.png` — точные побайтные копии автоматического оригинала, без ретуши/ресайза/обрезки/пересохранения. Только review/ содержит отдельно обозначенные производные для проверки.\n\n" if dims else "Готового изображения и review-растра нет. `attempts.json`/`tool-error-g1.json` содержат фактический отказ; промпт для обхода отказа не менялся.\n\n") + "Ограничения:\n\n" + "\n".join("- " + s for s in review["limitations"]) + "\n\nПодтверждены live owner и raw slug; проверено отсутствие исходного портретного key. Это только предложение исходника: runtime, Unreal, канонический design-front, formal acceptance, общие registry/ledger/git не менялись. Источники и SHA — в preflight/source-hashes-before/verification; точный запрос — prompt-g1.txt.\n", encoding="utf-8")
    item = {"task_id": "CP-31", "owner_slug": key, "game_name": preflight["game_name"], "service": "Codex", "model": "built-in image_gen", "template": "T-CODEX-PORTRAITSOURCE", "units": "1 image_gen call", "calls": 1, "successful_images": 0 if blocked else 1,
        "cost": None, "balance_before": None, "balance_after": None, "status": record["status"], "prompt_file": rel(prompt), "result_path": record.get("selected_path"), "sha256": record["sha256"], "dimensions": dims, "shared_ledger_pending_coordinator": True}
    handoff["packages"].append(item)
    dump(package / "coordinator-handoff.json", item)
    manifest = {"files": [{"path": rel(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in sorted(package.rglob("*")) if p.is_file() and p.name != "manifest-sha256.json"]}
    dump(package / "manifest-sha256.json", manifest)
    for f in manifest["files"]:
        assert sha(ROOT / f["path"]) == f["sha256"]
    package_results.append({"key": key, "status": record["status"], "generated": not blocked, "dimensions": dims, "sha256": record["sha256"], "manifest_files_checked": len(manifest["files"]), "sources_unchanged": True})
dump(WAVE / "ledger-handoff.json", handoff)
dump(WAVE / "wave-verification.json", {"task_id": "CP-31", "tool_calls": 4, "successful_images": 3, "failed_tool_calls": 1, "correction_calls": 0, "packages": package_results, "manifest_failures": [], "all_available_images_byte_preserved": True, "all_sources_unchanged": True, "shared_files_modified": False, "runtime_accepted": False, "long_lived_processes_started": []})
print(json.dumps(package_results, ensure_ascii=False))
