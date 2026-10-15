"""Prepare reference-only proposals for two independently verified missing helpers."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[5]
PACKAGES = Path(__file__).resolve().parents[1]
REFERENCE = "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"
SPECS = {
    "giles": {
        "asset_id": "ASSET-GILES-001", "owner": "buffy", "name": "Giles", "health": 6, "movement": 3,
        "subject": "An original mature male scholar and occult-research mentor, middle-aged human with short neat greying brown hair, a thoughtful original face with no likeness to any actor, and round thin-rimmed reading spectacles. He wears an open brown tweed blazer over a muted olive knitted waistcoat, cream collared shirt, small burgundy tie, charcoal trousers and plain dark leather shoes. Both hands are empty, naturally relaxed and held apart from the torso. A practical academic companion, not a wizard: no robe, cape, magic, armour or weapon.",
        "anchors": "round reading spectacles; neat greying short hair; brown tweed blazer; olive knitted waistcoat and cream shirt; burgundy tie; empty hands",
        "main": [{"name": "tweed brown", "hex": "#6D5947"}, {"name": "vest olive", "hex": "#657052"}, {"name": "shirt cream", "hex": "#E1D9C9"}],
        "accent": {"name": "tie burgundy", "hex": "#6F2D37"}, "weapon_hand": "none",
        "design_note": "Original academic-mentor interpretation of the insightful Giles role in Buffy text. Appearance and clothes are delegated design, not verified source costume or actor likeness.",
    },
    "daisy": {
        "asset_id": "ASSET-DAISY-001", "owner": "dr-jill-trent", "name": "Daisy", "health": 6, "movement": 2,
        "subject": "An original adult woman laboratory field assistant and practical mechanic for a 1940s science-adventure team. Human proportions, short chestnut bobbed hair held back with a simple ivory headband, friendly determined original face. She wears a rolled-sleeve ivory work blouse under deep navy bib overalls with broad shoulder straps and plain brown lace-up work boots. A single substantial steel open-ended wrench is held low in her RIGHT hand, fully clear of the thigh, while her LEFT hand is empty and relaxed. No lab coat, no dress, no ray gun, no extra tools, no tool belt and no actor likeness.",
        "anchors": "single steel wrench held low in the RIGHT hand; navy bib overalls; rolled ivory blouse sleeves; short chestnut bob and simple ivory headband; work boots",
        "main": [{"name": "overalls navy", "hex": "#344659"}, {"name": "blouse ivory", "hex": "#E2D9C7"}, {"name": "hair chestnut", "hex": "#5C3828"}],
        "accent": {"name": "brass fittings", "hex": "#B48D51"}, "weapon_hand": "right",
        "design_note": "Original technician interpretation of Daisy's companion role with Jill Trent's gadgetology. The source confirms identity and mechanics, not this costume or wrench. Distinct from Jill's existing coat/dress/raygun design.",
    },
}


for key, spec in SPECS.items():
    out = PACKAGES / key
    (out / "prompts").mkdir(parents=True, exist_ok=True)
    core = (PACKAGES / "faith/prompts/future-core-clean.txt").read_text(encoding="utf-8")
    palette = ", ".join(entry["name"] + " " + entry["hex"] for entry in spec["main"]) + ", accent " + spec["accent"]["name"] + " " + spec["accent"]["hex"]
    for prefix, value in [("SUBJECT: ", spec["subject"]), ("IDENTITY ANCHORS, each clearly visible: ", spec["anchors"] + "."), ("PALETTE: ", palette + ". These are the main colours plus one accent; no other strong colours.")]:
        core = re.sub("^" + re.escape(prefix) + ".*$", prefix + value, core, flags=re.M)
    if spec["weapon_hand"] == "none":
        core = core.replace("The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.", "No weapon or held object. Both hands are empty.")
    assert core.startswith("Use case:") and "wiglaf" not in core.lower() and "CHECKLIST" not in core
    (out / "prompts/design-front-g1.txt").write_text(core, encoding="utf-8")
    inputs = [ROOT / ("scraped-data/api/heroes/" + spec["owner"] + ".json"), ROOT / REFERENCE,
              ROOT / ("art/pipeline-candidates/ASSET-" + spec["owner"].upper() + "-001/asset-card.yaml"),
              ROOT / ("art/imagegen/concept-" + spec["owner"] + "-codex/design/" + spec["owner"] + "-front.png")]
    hashes = [{"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in inputs]
    (out / "source-hashes-before.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")
    palette_obj = {"asset_id": spec["asset_id"], "main": spec["main"], "accent": spec["accent"]}
    (out / "palette.json").write_text(json.dumps(palette_obj, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {"proposed_asset_id": spec["asset_id"], "game_name": spec["name"], "owner_hero_slug": spec["owner"], "count": 1,
                  "attack": "melee", "health": spec["health"], "movement": spec["movement"],
                  "source": "scraped-data/api/heroes/" + spec["owner"] + ".json nodes[2].data sidekicks",
                  "live_roster_confirmation": "2026-10-15 auditor queried Hero.sidekicks and cross-checked scraped owner file",
                  "visual_design": spec["design_note"], "stage": "Original concept reference candidate, formal pipeline not started",
                  "image_inputs": [REFERENCE], "context_images_inspected_but_not_sent": [hashes[-1]["path"]]}
    (out / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    proposal = {"ASSET_ID": spec["asset_id"], "CONTENT_KEY": key, "KEY": spec["name"], "ROLE": "hero", "GAME_ROLE": "sidekick", "ANATOMY": "humanoid",
                "OWNER_HERO_SLUG": spec["owner"], "WEAPON_HAND": spec["weapon_hand"], "SIDE_VIEW": "left", "DESCRIPTION_EN": spec["subject"],
                "ANCHORS_EN": spec["anchors"], "PALETTE": palette_obj, "QUALITY_REFERENCE": [REFERENCE], "STATUS": "unregistered reference proposal",
                "NOTES": spec["design_note"] + " No rig/model/game-readiness claim; future stage-0 registration and independent design acceptance required."}
    (out / "asset-card.proposal.json").write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"key": key, "prompt": core}, ensure_ascii=False))
