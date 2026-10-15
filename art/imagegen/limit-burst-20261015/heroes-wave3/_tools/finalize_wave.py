"""Verify the completed private wave and produce the coordinator handoff."""
from pathlib import Path
import hashlib
import json

WAVE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
KEYS = ["xander", "drusilla", "tara"]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

handoff = {"task_id": "AN-151", "registered_before_generation": True, "calls_total": 6,
           "note": "Private handoff only. Coordinator owns shared ledger. All six calls have exact prompts and preserved original PNGs. No formal pipeline gate advancement.", "packages": []}
failures = []
manifest_files = 0
selected_rows = []
for key in KEYS:
    package = WAVE / key
    provenance = json.loads((package / "provenance.json").read_text(encoding="utf-8"))
    records = json.loads((package / "generation-records.json").read_text(encoding="utf-8"))
    manifest = json.loads((package / "manifest-sha256.json").read_text(encoding="utf-8"))
    verification = json.loads((package / "verification.json").read_text(encoding="utf-8"))
    for rel, record in manifest.items():
        path = package / rel
        manifest_files += 1
        if not path.exists() or sha(path) != record["sha256"] or path.stat().st_size != record["bytes"]:
            failures.append(key + "/" + rel)
    selected = next(r for r in records if r["selected"])
    design = package / "design" / (key + "-front.png")
    assert len(records) == 2 and selected["attempt"] == 2
    assert sha(design) == selected["sha256"], "Selected design copy diverged"
    assert verification["source_unchanged"] and verification["generated_image_byte_preserved"]
    assert all(p["clean_core_only_with_optional_correction"] for p in verification["prompt_validation"])
    checks = json.loads((package / "checks/design-front-g2/checks-report.json").read_text(encoding="utf-8"))
    assert checks["inputs"][0]["sha256"] == selected["sha256"]
    selected_rows.append({"key": key, "sha256": selected["sha256"], "width": selected["width"], "height": selected["height"], "checker": checks["summary"], "top_pct": checks["measurements"]["front"]["mask"]["top_pct"], "bottom_pct": checks["measurements"]["front"]["mask"]["bottom_pct"]})
    handoff["packages"].append({
        "task_id": "AN-151", "proposed_asset_id": provenance["proposed_asset_id"],
        "owner_hero_slug": provenance["owner_hero_slug"], "game_name": provenance["game_name"],
        "service": "Codex", "model": "built-in image_gen", "template": "T-CODEX-HEROVIEWS",
        "units": "package, 2 image_gen calls", "cost": None, "balance_before": None, "balance_after": None,
        "package_path": package.relative_to(ROOT).as_posix(),
        "prompt_files": [r["prompt_file"] for r in records], "result_paths": [r["saved_path"] for r in records],
        "selected_result": selected["saved_path"], "selected_sha256": selected["sha256"],
        "status": "proposed-production-reference-only", "shared_ledger_pending_coordinator": True,
    })

assert not failures, failures
dump(WAVE / "ledger-handoff.json", handoff)
verification = {
    "visual_card_id": "AN-151", "registered_before_generation": True, "packages": KEYS,
    "generated_images": 6, "selected_g2_images": 3, "max_calls_per_asset": 2,
    "manifest_files_checked": manifest_files, "manifest_failures": failures,
    "all_sources_unchanged": True, "all_images_byte_preserved": True,
    "selected_design_copies_match_generation_and_checker_hashes": True,
    "all_sent_prompts_clean": True, "selected_images": selected_rows,
    "independent_acceptance": False, "three_d_pipeline_gates_advanced": False,
    "long_lived_processes_started": [], "all_own_checker_commands_finished": True,
    "frozen_first_wave_written": False, "frozen_second_wave_written": False,
    "total_wave_bytes": sum(p.stat().st_size for p in WAVE.rglob("*") if p.is_file() and p.name != "wave-verification.json"),
}
dump(WAVE / "wave-verification.json", verification)
print(json.dumps(verification, ensure_ascii=False))
