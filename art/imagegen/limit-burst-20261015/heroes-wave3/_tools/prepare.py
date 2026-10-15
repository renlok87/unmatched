from pathlib import Path
import json
import hashlib
import re
import shutil

ROOT = Path(__file__).resolve().parents[5]
WAVE = Path(__file__).resolve().parents[1]
SPECS = {
    "xander": {
        "asset": "ASSET-XANDER-001", "owner": "buffy", "name": "Xander", "health": 6, "move": 3, "attack": "melee", "hand": "right",
        "subject": "An original adult male practical companion and everyday vampire-hunting helper, human proportions, mid-twenties, short dark-brown hair and a friendly determined clean-shaven original face with no likeness to any actor. He wears a muted-blue checked overshirt with rolled sleeves over a plain charcoal T-shirt, tan work trousers and scuffed brown work boots. The checks are broad simple low-contrast blocks, not tiny texture. He holds ONE short substantial carved wooden stake low in his own RIGHT hand, angled down and outward with a visible background gap from his thigh. His LEFT hand is empty and relaxed. No eye patch, no injury, no armour, no jacket, no extra weapons, no holster, no logos or printed shirt text.",
        "anchors": "short dark-brown hair; blue checked open overshirt; charcoal T-shirt; tan work trousers; one wooden stake low in own RIGHT hand; empty left hand",
        "main": [{"name": "overshirt muted blue", "hex": "#4A657A"}, {"name": "trousers tan", "hex": "#927654"}, {"name": "T-shirt charcoal", "hex": "#3F4145"}],
        "accent": {"name": "stake wood", "hex": "#98734B"},
        "design_note": "Original adult everyday-helper interpretation of Xander's reliable companion role. Source confirms name, owner and mechanics, not exact age, face, costume or stake. No actor portrait target.",
    },
    "drusilla": {
        "asset": "ASSET-DRUSILLA-001", "owner": "spike", "name": "Drusilla", "health": 7, "move": 2, "attack": "melee", "hand": "none",
        "subject": "An original adult female vampire companion with natural human proportions, pale skin, very long near-black hair parted centrally and falling behind her shoulders, an original serene unsettling face with no likeness to any actor. She wears a modest high-neck antique ivory gown with a fitted bodice, narrow three-quarter sleeves and a simple ankle-length skirt, a narrow deep-burgundy waist sash and plain dark ankle boots. A small muted antique-brass sash buckle is the only jewellery. Both hands are empty, fingers naturally relaxed, arms held slightly apart so a charcoal-background gap is visible at both elbows. Keep her hair behind the upper arms so it does not fill the arm gaps. No weapon, no held object, no blood, no gore, no doll, no crown, no veil, no cape and no magical effects.",
        "anchors": "very long dark centrally-parted hair; pale adult face; high-neck ivory gown with narrow sleeves; burgundy sash; empty hands",
        "main": [{"name": "gown ivory", "hex": "#DED8CC"}, {"name": "sash wine", "hex": "#6D283A"}, {"name": "hair near-black", "hex": "#231E25"}],
        "accent": {"name": "sash buckle brass", "hex": "#9A8464"},
        "design_note": "Original adult vampire-companion interpretation. Source confirms Drusilla under Spike and mechanics, not this gown or face. No actor likeness, portrait, scan or photographic reference supplied.",
    },
    "tara": {
        "asset": "ASSET-TARA-001", "owner": "willow", "name": "Tara", "health": 6, "move": 2, "attack": "range", "hand": "none",
        "subject": "An original adult female gentle scholarly spellcaster companion with natural human proportions, long honey-blonde hair loosely half tied back, and a calm focused original face with no likeness to any actor. She wears a muted indigo hip-length knitted cardigan over a plain cream blouse, a simple warm-brown ankle-length skirt and practical brown lace-up boots. A small plain round silver pendant hangs at the collar, without any symbol or lettering. Both hands are empty and slightly open, relaxed beside her body with bent elbows and clear charcoal-background gaps; this is a neutral modelling pose, not casting an active spell. Keep hair behind the shoulders and arms. No staff, book, weapon, held object, magical sphere, flame, glow, floating effect, robe, cape, crown or actor likeness.",
        "anchors": "long honey-blonde half-tied hair; indigo cardigan; cream blouse; plain brown ankle skirt; small unmarked round silver pendant; empty hands",
        "main": [{"name": "cardigan indigo", "hex": "#4B4F75"}, {"name": "blouse cream", "hex": "#DCD5C7"}, {"name": "skirt warm brown", "hex": "#6F5144"}],
        "accent": {"name": "pendant silver", "hex": "#A8B0B6"},
        "design_note": "Original adult caster-companion interpretation of Tara under Willow. Source confirms name, owner and ranged mechanics, not exact costume or hairstyle. Empty-handed caster design is delegated; no active FX are baked into the reference.",
    },
}

(WAVE / "_tools").mkdir(parents=True, exist_ok=True)
shutil.copyfile(ROOT / "art/imagegen/limit-burst-20261015/heroes-wave2/_tools/finalize.py", WAVE / "_tools/finalize.py")
clean = (ROOT / "art/imagegen/limit-burst-20261015/heroes/faith/prompts/future-core-clean.txt").read_text(encoding="utf-8")
for key, spec in SPECS.items():
    out = WAVE / key
    (out / "prompts").mkdir(parents=True, exist_ok=True)
    colours = ", ".join(x["name"] + " " + x["hex"] for x in spec["main"]) + ", accent " + spec["accent"]["name"] + " " + spec["accent"]["hex"]
    prompt = clean
    for prefix, value in [("SUBJECT: ", spec["subject"]), ("IDENTITY ANCHORS, each clearly visible: ", spec["anchors"] + "."), ("PALETTE: ", colours + ". These are the main colours plus one accent; no other strong colours.")]:
        prompt = re.sub("^" + re.escape(prefix) + ".*$", prefix + value, prompt, flags=re.M)
    if spec["hand"] == "none":
        prompt = prompt.replace("The weapon is held in the figure's own RIGHT hand, which appears on the viewer's LEFT in the front view.", "No weapon or held object. Both hands are empty.")
    assert prompt.startswith("Use case:") and "CHECKLIST" not in prompt and "wiglaf" not in prompt.lower()
    (out / "prompts/design-front-g1.txt").write_text(prompt, encoding="utf-8")
    inputs = [ROOT / ("scraped-data/api/heroes/" + spec["owner"] + ".json"), ROOT / "art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png",
              ROOT / ("art/imagegen/concept-" + spec["owner"] + "-codex/design/" + spec["owner"] + "-front.png"),
              WAVE / "live-roster-evidence.json", WAVE / "roster-coverage-audit.json", ROOT / "backend/src/games/services/game-initialization.service.ts"]
    hashes = [{"path": p.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size} for p in inputs]
    (out / "source-hashes-before.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")
    palette = {"asset_id": spec["asset"], "main": spec["main"], "accent": spec["accent"]}
    (out / "palette.json").write_text(json.dumps(palette, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {"proposed_asset_id": spec["asset"], "visual_card_id": "AN-151", "registered_before_generation": True,
                  "task_map": "art/imagegen/limit-burst-20261015/task-map-wave3.json", "task_registration": "docs/game-design/visual/06-tasks/anim.csv AN-151",
                  "game_name": spec["name"], "owner_hero_slug": spec["owner"], "count": 1, "health": spec["health"], "movement": spec["move"], "attack": spec["attack"],
                  "source": "scraped-data/api/heroes/" + spec["owner"] + ".json nodes[2].data sidekicks", "live_roster": "art/imagegen/limit-burst-20261015/heroes-wave3/live-roster-evidence.json",
                  "runtime_source": "backend/src/games/services/game-initialization.service.ts:151-191,720-732", "visual_design": spec["design_note"],
                  "absence_check": "Full 84-Hero live roster compared against current concepts, root asset cards, prior waves and existing aliases before production. Selected helpers have no exact concept/card; known aliases and contaminated cross-owner rows excluded.",
                  "image_inputs": ["art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png"], "context_images_read_only": [hashes[2]["path"]], "stage": "production-reference-only; no formal gates advanced"}
    (out / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    proposal = {"ASSET_ID": spec["asset"], "VISUAL_CARD_ID": "AN-151", "CONTENT_KEY": key, "GAME_NAME": spec["name"], "ROLE": "hero", "GAME_ROLE": "sidekick", "ANATOMY": "humanoid", "OWNER_HERO_SLUG": spec["owner"], "WEAPON_HAND": spec["hand"], "SIDE_VIEW": "left", "DESCRIPTION_EN": spec["subject"], "ANCHORS_EN": spec["anchors"], "PALETTE": palette, "STATUS": "unregistered asset proposal; registered visual task AN-151; production reference only", "NOTES": spec["design_note"] + " No model/rig/game-readiness claim."}
    (out / "asset-card.proposal.json").write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"key": key, "prompt": prompt}, ensure_ascii=False))
