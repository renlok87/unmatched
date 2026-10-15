"""Read-only roster/reference preflight and exact portrait prompts for CP-31."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import subprocess

WAVE = Path(__file__).resolve().parents[1]
ROOT = Path(__file__).resolve().parents[5]
SPECS = {
    "spike": {"name": "Spike", "cycle": "20261013-front-r1", "reference_status": "formal 1a pass", "score": 8.8,
        "subject": "One original adult male punk vampire miniature bust: slicked-back platinum-blond sculpted hair, pale angular original face and a restrained knowing half-smile, black leather duster lapels, muted red open shirt over a plain black T-shirt. No fangs, blood, cigarettes or props. Use the project design's broad hair, collar and colour cues while retaining an original non-photographic adult face; do not depict an actor.",
        "palette": "black coat #1C1A1C, platinum hair #E8E0C8, muted red shirt #9B2E26, natural pale skin"},
    "willow": {"name": "Willow", "cycle": "20261013-front-r2", "reference_status": "unaccepted / return_to_stage_1; specifically authorized as portrait source only", "score": 6.3,
        "subject": "One original adult female scholarly witch miniature bust: long copper-red sculpted hair parted near the centre, calm attentive original face, moss-green knitted cardigan with broad restrained floral embroidery over a muted purple top, small simple necklace. No hands, spell, glow or props. Preserve the project design's warm hair silhouette and green/purple costume relationship; this is the everyday owner form, not Dark Willow. Do not depict an actress.",
        "palette": "copper-red hair #A8321E, green cardigan #5E8A4A, muted purple top #6A4A8A, natural warm fair skin"},
    "geralt-of-rivia": {"name": "Geralt of Rivia", "cycle": "20261013-front-r2", "reference_status": "user override to proceed; formal card remains return_to_stage_1", "score": 6.3,
        "subject": "One original mature adult male monster-hunter miniature bust: long white sculpted hair brushed back from the forehead and falling to the shoulders, rugged original angular face, restrained vertical facial scar, small natural amber-yellow eyes without glow, dark layered leather armour and crossing straps, a single small silver wolf-like medallion at the upper chest. No hands or weapons in this portrait. Use only the intact head/hair/upper-armour cues of the project design. The source has eroded black artifacts on its lower body: do not reproduce those artifacts, broken edges or surface holes. Do not depict any actor or copy a commercial game portrait.",
        "palette": "dark leather #24211F, white hair #E2E0DA, steel #9AA1A7, small silver medallion #C0C6CC, weathered natural skin"},
    "philippa": {"name": "Philippa", "cycle": "20261013-front-r2", "reference_status": "user override applied; formal paired result remains return_to_stage_1", "score": 7.5,
        "subject": "One original adult female sorceress miniature bust: short dark sculpted curled hair swept back, composed intelligent original face, high black-and-violet standing collar framing the neck, tailored dark gown with broad violet decorative panels, one small pale-metal owl brooch visible low on the upper chest. Collar and hair are fully contained in the composition. No hands, spell, magic glow or props. Preserve the project design's short hair, tall collar and owl identity cues. Do not depict an actress or copy a commercial game portrait.",
        "palette": "gown black #1C1A20, violet panels #5B2A7E, dark hair #2A2224, restrained pale-metal owl and natural fair skin"},
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def dump(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def decode_hero(path):
    flat = json.loads(path.read_text(encoding="utf-8"))["nodes"][2]["data"]
    def get(index):
        if index < 0:
            return None
        value = flat[index]
        if isinstance(value, dict):
            return {k: get(v) for k, v in value.items()}
        if isinstance(value, list):
            return [get(v) for v in value]
        return value
    root = flat[0]
    data = get(root["fetchedHero"])
    return {k: data[k] for k in ["id", "name", "key", "attack", "startHealth", "move"]}

now = datetime.now(timezone.utc).isoformat()
live = json.loads((WAVE / "live-roster-evidence.json").read_text(encoding="utf-8"))
live["queried_at_utc"] = now
for row in live["rows"]:
    row["sidekicks"] = [{k: v for k, v in s.items() if k != "avatarUrl"} for s in row["sidekicks"]]
dump(WAVE / "live-roster-evidence.json", live)
assert len(live["rows"]) == 4 and live["rows_total"] == 84
registration_file = ROOT / "docs/game-design/visual/06-tasks/cards-portraits.csv"
registration = next(line for line in registration_file.read_text(encoding="utf-8-sig").splitlines() if line.startswith("CP-31,"))
dump(WAVE / "task-registration.json", {"task_id": "CP-31", "registered_before_generation": True, "source": registration_file.relative_to(ROOT).as_posix(), "line_text": registration, "line_sha256": hashlib.sha256(registration.encode()).hexdigest()})
runtime = ROOT / "unreal/Unmatched/Config/Cards/S08CardMedia.json"
runtime_text = runtime.read_text(encoding="utf-8")
files = subprocess.run(["rg", "--files", "art/imagegen", "art/cards-v1", "unreal/Unmatched/Content"], cwd=ROOT, encoding="utf-8", capture_output=True)
listed = files.stdout.splitlines()
for key, spec in SPECS.items():
    out = WAVE / key
    out.mkdir(exist_ok=False)
    ref = ROOT / ("art/imagegen/concept-" + key + "-codex/design/" + key + "-front.png")
    raw = ROOT / ("scraped-data/api/heroes/" + key + ".json")
    palette = ref.parent.parent / "palette.json"
    card_root = ROOT / ("art/pipeline-candidates/ASSET-" + key.upper() + "-001/evidence/acceptance-concept/" + spec["cycle"])
    card = card_root / "card.json"
    acceptance = json.loads(card.read_text(encoding="utf-8"))
    assert any(o["sha256"] == sha(ref) for o in acceptance["accepted_object"])
    raw_owner = decode_hero(raw)
    assert raw_owner["key"] == key and raw_owner["name"] == spec["name"]
    live_row = next(row for row in live["rows"] if row["name"] == spec["name"])
    matches = [f for f in listed if ("portrait" in f.lower() or "avatar" in f.lower()) and key in f.lower()]
    assert not matches, matches
    runtime_key = "portrait:" + key
    assert '"' + runtime_key + '"' not in runtime_text
    extra_files = []
    if (card_root / "user-decision.json").exists():
        extra_files.append(card_root / "user-decision.json")
    if (card_root / "final.json").exists():
        extra_files.append(card_root / "final.json")
    preflight = {
        "task_id": "CP-31", "checked_at_utc": now, "status": "source-candidate-only", "owner_slug": key,
        "game_name": spec["name"], "raw_owner": {"path": raw.relative_to(ROOT).as_posix(), "sha256": sha(raw), **raw_owner},
        "live_roster": {"snapshot": (WAVE / "live-roster-evidence.json").relative_to(ROOT).as_posix(), "row": live_row},
        "reference": {"path": ref.relative_to(ROOT).as_posix(), "sha256": sha(ref), "opened_with_view_image": True},
        "reference_status": spec["reference_status"], "formal_card": {"path": card.relative_to(ROOT).as_posix(), "verdict": acceptance["verdict"], "score": acceptance["score"], "hash_matches_current_ref": True},
        "effective_recorded_score": spec["score"], "user_override_present_next_to_card": (card_root / "user-decision.json").exists(),
        "absence_check": {"named_source_matches": matches, "runtime_key": runtime_key, "runtime_key_absent": True, "roots": ["art/imagegen", "art/cards-v1", "unreal/Unmatched/Content"], "rg_exit_code": files.returncode, "rg_stderr": files.stderr, "scope": "Focused portrait/avatar path and exact runtime key lookup. Raw avatar images were not opened or used."},
        "crop_contract": "full100: centered circle diameter equals entire square side, no zoom or tighter source crop",
        "source_limit": "Canonical lower body has eroded black artifacts; intact head cues only, canonical not edited." if key == "geralt-of-rivia" else None,
        "willow_authorization": "Coordinator explicitly authorizes a source-only portrait proposal from this current unaccepted owner design; score6.3/currentr2, no adjacent override; no import or pipeline advancement." if key == "willow" else None,
    }
    dump(out / "preflight.json", preflight)
    sources = [ref, raw, palette, card, WAVE / "live-roster-evidence.json", WAVE / "task-registration.json", ROOT / "art/imagegen/limit-burst-20261015/task-map-owner-wave5.json"] + extra_files
    dump(out / "source-hashes-before.json", [{"path": f.relative_to(ROOT).as_posix(), "sha256": sha(f), "bytes": f.stat().st_size} for f in sources])
    prompt = (
        "Use case: stylized-concept\n"
        "Asset type: original square head-and-shoulders portrait SOURCE CANDIDATE for the project's " + spec["name"] + " roster owner.\n"
        "Input image 1: the project's own current miniature design, used ONLY for broad identity cues, upper-costume palette and sculpted miniature character. Create a NEW original portrait, do not crop or reprint the input. Its pipeline acceptance state is separate from this source-only portrait request.\n"
        "Subject: " + spec["subject"] + "\n"
        "Style/medium: premium hand-painted collectible tabletop MINIATURE bust illustration/render. Sculpted resin-like hair masses, coherent painted facial planes, matte worn cloth/leather, restrained fine brush detail. Original adult character interpretation, no photographic human avatar or actor likeness.\n"
        "Composition/framing: square canvas. One centered head, shoulders and upper chest, nearly frontal. Full100 composition: the ENTIRE square is the intended future circular crop, with no zoom. Generous charcoal breathing room: highest hair/headgear point about y18%, eyes about y43%, chin about y62%; keep all hair, ears, headgear and high collar inside the central 64% width, comfortably inside an imaginary centered circle whose diameter equals 100% of the square side. Hair tips and the small chest identity detail stay above y82%. Shoulders taper into the lower corners. Whole head and all hair are visible, never clipped. No hands, pedestal, weapons, spell effects or props beside the face.\n"
        "Background/light: plain empty neutral dark charcoal gray, soft even studio lighting with gentle fill, clear facial light/dark planes and readable eyes, no floor, scenery, haze or strong rim light.\n"
        "Palette: " + spec["palette"] + ".\n"
        "Constraints: one adult character only. No text, letters, logos, watermark, frame, badge, circular mask, UI, cards, collage, scans, commercial game frames or photographic skin/actor portrait. Preserve the broad source identity while making original facial details. Output one single square image."
    )
    (out / "prompt-g1.txt").write_text(prompt, encoding="utf-8")
    dump(out / "tool-arguments-g1.json", {"prompt_file": (out / "prompt-g1.txt").relative_to(ROOT).as_posix(), "referenced_image_paths": [ref.as_posix()], "transparent_background": False})
    print(json.dumps({"key": key, "reference_sha256": sha(ref), "reference_status": spec["reference_status"], "runtime_key_absent": True}, ensure_ascii=False))
