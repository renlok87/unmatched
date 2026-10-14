"""registration_check.py на синтетическом чекауте (без живых данных репозитория, RB-03): полный набор — PASS, каждая
выпавшая строка регистрации — FAIL своего пункта, разбор C++/INI/Python без импорта.

    python -m pytest tools/art/tests/test_registration_check.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import registration_check as R  # noqa: E402

KEY, FIGHTER, CHAR, AID, PRE = "Testo", "Test Hero", "Testo", "ASSET-TESTO-001", "TST"
SPEC_REL = f"{AID}/build-profiles/testo-h2anim.json"

SPECS_CPP = """
const TArray<FHeroSpec>& Specs() {
  // comment {TEXT("Ghost"), TEXT("Ghost"), TEXT("H2LD"), true, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 1.0f, 7},
  static const TArray<FHeroSpec> Table = {
      {TEXT("King Arthur"), TEXT("KingArthur"), TEXT("H2LD"), true, 55.0f, 52.0f, 56.0f, 55.0f, 60.06f, 2.5f, 7},
      {TEXT("Test Hero"), TEXT("Testo"), TEXT("H2LD"), true, 55.0f, 50.0f, 55.0f, 55.003f, 73.56f,
       56.0f / 24.0f, 8},
  };
  return Table;
}
"""

AUDIO_CPP = """
FString S08AudioBank::CharacterKey(const FString& Name) {
  if (Name.Contains(TEXT("arthur"), ESearchCase::IgnoreCase)) return TEXT("ARTHUR");
  if (Name.Contains(TEXT("test"), ESearchCase::IgnoreCase)) return TEXT("TESTO");
  return FString();
}

FString S08AudioBank::HitType(const FString& Key) {
  if (Key == TEXT("ARTHUR")) return TEXT("BLADE");
  if (Key == TEXT("TESTO")) return TEXT("MAGIC");
  return TEXT("BLUNT");
}
"""

BANKS = "\n".join(f'S08_AUDIO_BANK(TEXT("{b}"), TEXT("/Game/Audio/x"))' for b in (
    "CMB-HIT-BLADE", "CMB-HIT-BLUNT", "CMB-HIT-MAGIC", "CMB-LUNGE-BLADE", "CMB-LUNGE-MAGIC"))

CLIP_MANIFEST_PY = '''
CHARS = {"Arthur": ("ARTH", "ASSET-KING-ARTHUR-001")}
H2ANIM = {"Arthur": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json"}
CHARS["Testo"] = ("TST", "ASSET-TESTO-001")
H2ANIM["Testo"] = "art/pipeline-candidates/ASSET-TESTO-001/build-profiles/testo-h2anim.json"
H2ANIM_CLIP = {}
'''

SHEET_PY = '''
from typing import NamedTuple
class Hero(NamedTuple):
    character: str
    prefix: str
    idle_s: float
    cards: tuple
HEROES = {
    "KingArthur": Hero("Arthur", "ARTH", 2.5, ("AN-01", "AN-02", "AN-03", "AN-04")),
    "Testo": Hero("Testo", "TST", 56.0 / 24.0, ("AN-141", "AN-142", "AN-143", "AN-144")),
}
'''


def _w(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


def _wj(root: Path, rel: str, obj) -> Path:
    return _w(root, rel, json.dumps(obj, ensure_ascii=False, indent=1))


def _hero_files(root: Path, key: str, aid: str, spec_rel: str, contact: int, character: str):
    run = f"art/pipeline-candidates/{aid}/run-h2anim"
    _wj(root, "art/pipeline-candidates/" + spec_rel, {
        "character": character, "ue_hero": key, "asset_id": aid, "fps": 24, "run_dir": run,
        "ue": {"clips_folder": f"/Game/PipelineCandidates/{key}/H2Anim"},
        "clips": {c: ({"frames": 14, "key_frames": [0, 4, contact, 14]} if c == "LungeAttack" else {"frames": 10})
                  for c in R.CLIPS}})
    for c in R.CLIPS:
        _w(root, f"{run}/export/AM_{key}_{c}.fbx", "fbx")
    for c in ("HitReact", "DeathSettle"):
        _w(root, f"unreal/Unmatched/Content/PipelineCandidates/{key}/H2Anim/AM_{key}_{c}.uasset", "u")


def fixture_name(name: str) -> str:
    return json.dumps({"state": json.dumps({"fighters": [{"name": name}]})})


def make_repo(root: Path) -> Path:
    P = R.PATHS
    _w(root, P["specs"], SPECS_CPP)
    _w(root, P["audio"], AUDIO_CPP)
    _w(root, P["audio_data"], BANKS)
    seq = {k: {c: f"/Game/PipelineCandidates/{k}/H2Anim/AM_{k}_{c}.AM_{k}_{c}" for c in ("HitReact", "DeathSettle")}
           for k in ("KingArthur", KEY)}
    _wj(root, P["cue"], {"cues": [
        {"id": "CUE-011", "clip": {"sequence_by_fighter": {k: v["HitReact"] for k, v in seq.items()}}},
        {"id": "CUE-013", "clip": {"sequence_by_fighter": {k: v["DeathSettle"] for k, v in seq.items()}}}]})
    cook = "".join(f'+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/{k}/{s}")\n'
                   for k in ("KingArthur", KEY) for s in ("H2LD", "Rig", "H2Anim"))
    _w(root, P["ini"], "[/Script/UnrealEd.ProjectPackagingSettings]\n" + cook)
    _wj(root, P["names"], {"heroes": {
        "king-arthur": {"hero": {"en": "King Arthur", "ru": "Король Артур"}},
        "test-hero": {"hero": {"en": "Test Hero", "ru": "Тестовый герой"}}}})
    _w(root, P["de010"], 'HEROES = [("KingArthur", "H2LD", "ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json", 7),\n'
       f'          ("{KEY}", "H2LD", "{SPEC_REL}", 8)]\n')
    _w(root, P["de011"], 'CAPTURE_LOOKS = {"KingArthur": "P1"}\nCAPTURE_LOOKS["Testo"] = "P2"\n')
    _w(root, P["manifest_py"], CLIP_MANIFEST_PY)
    _wj(root, P["manifest_schema"], {"$defs": {"clip": {"properties": {"character": {"enum": ["Arthur", CHAR]}}}}})
    _wj(root, P["manifest_json"], {"clips": [{"id": f"{p}-{c}", "role": "production"}
                                             for p in ("ARTH", PRE) for c in R.CLIPS]})
    _w(root, P["sheet"], SHEET_PY)
    _w(root, P["anim_csv"], "id,area\n" + "".join(f"AN-{n:02d},anim\n" for n in (1, 2, 3, 4, 141, 142, 143, 144)))
    _wj(root, P["rig"], {"skeletons": {"UM_HUMANOID_17_v2": {
        "applies_to": ["ASSET-KING-ARTHUR-001", f"{AID} (без оружия)"],
        "characters": {"Arthur": {"asset_id": "ASSET-KING-ARTHUR-001", "weapon_bone": "weapon.R",
                                  "ue_weapon_bone": "weapon_R"},
                       CHAR: {"asset_id": AID, "weapon_bone": None}}}},
        "ue_import": {"sockets_v2": [{"name": "Weapon", "bone_by_character": {"Arthur": "weapon_R", CHAR: "профиль"}}]}})
    boards = {"Marmoreal": "board-m", "Sarpedon": "board-s"}
    for m, b in boards.items():
        _w(root, f"{P['bench']}/S08Bench{m}.json",
           json.dumps({"benchBoardId": b, "raw": {"data": fixture_name("King Arthur")}}))
        _w(root, f"{P['bench']}/S08Bench{m}-{KEY}.json", json.dumps({
            "benchBoardId": b, "benchVariant": {"key": KEY, "heroName": FIGHTER, "heroSlug": "test-hero"},
            "raw": {"data": fixture_name(FIGHTER)}}))
    _wj(root, P["registry"], {"assets": [
        {"id": "ASSET-KING-ARTHUR-001", "status": "технически импортировано", "stage": "ue-editor-frames"},
        {"id": AID, "status": "технически импортировано", "stage": "live-packaged-probe"}]})
    _w(root, f"art/pipeline-candidates/{AID}/asset-card.yaml",
       f"ASSET_ID: {AID}\nKEY: {KEY}\nGAME_ROLE: hero\nCHARACTER: \"{CHAR}\"   # comment\n"
       f"FIGHTER_NAME: \"{FIGHTER}\"\nHERO_SLUG: \"test-hero\"\nOWNER_HERO_SLUG: null\nHIT_TYPE: \"MAGIC\"\n"
       f"AUDIO_KEY: \"TESTO\"\ndelegated:\n  CHARACTER: \"not this one\"\n" + STAGE7A)
    for d in ("20261014-h2ld-ue-import", "20261014-h2ld-ldc-ue", "evidence/stage7a-20261014"):
        _w(root, f"art/pipeline-candidates/{AID}/{d}/README.md", "x")
    _hero_files(root, "KingArthur", "ASSET-KING-ARTHUR-001", "ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2anim.json",
                7, "Arthur")
    _hero_files(root, KEY, AID, SPEC_REL, 8, CHAR)
    return root


STAGE7A = (f"STAGE7A:\n  editor: \"свой редактор, закрыт при 0 dirty\"\n"
           f"  import_run: \"art/pipeline-candidates/{AID}/20261014-h2ld-ue-import\"   # technically_imported\n"
           f"  import_profile: \"build-profiles/testo-h2ld-lookdev-ue-import.json\"\n"
           f"  review: \"art/pipeline-candidates/{AID}/20261014-h2ld-ldc-ue\"\n"
           f"  evidence: \"art/pipeline-candidates/{AID}/evidence/stage7a-20261014\"\n"
           f"  clip_acceptance: \"r1: 4 pass\"\n")


@pytest.fixture
def repo(tmp_path):
    return make_repo(tmp_path / "repo")


def status(report, key=KEY):
    return {i: c["status"] for i, c in report["heroes"][key]["checks"].items()}


def edit(root: Path, key: str, old: str, new: str):
    p = root / R.PATHS.get(key, key)
    t = p.read_text(encoding="utf-8")
    assert old in t, old
    p.write_text(t.replace(old, new), encoding="utf-8")


def test_complete_registration_passes(repo, capsys):
    rep = R.check_all(repo)
    assert rep["verdict"] == "PASS", json.dumps(rep, ensure_ascii=False, indent=1)
    assert status(rep, "KingArthur")["bench"] == "SKIP"  # canonical fighter
    assert status(rep)["bench"] == "PASS"
    ident = rep["heroes"][KEY]["identity"]
    assert (ident["character"], ident["asset_id"], ident["audio_key"]) == (CHAR, AID, "TESTO")
    assert R.main(["--repo", str(repo)]) == 0
    out = capsys.readouterr().out
    assert "PASS: героев 2" in out


def test_parse_specs_skips_comments_and_evaluates_fractions():
    rows = R.parse_specs(SPECS_CPP)
    assert [r["key"] for r in rows] == ["KingArthur", KEY]
    assert rows[1]["idle_s"] == pytest.approx(56 / 24) and rows[1]["contact_frame"] == 8


def test_module_constants_without_import():
    c = R.module_constants(CLIP_MANIFEST_PY + "\nH2ANIM_CLIP[\"Testo\", \"Idle\"] = \"x.json\"\n",
                           {"CHARS", "H2ANIM", "H2ANIM_CLIP"})
    assert c["CHARS"]["Testo"] == ("TST", AID)
    assert c["H2ANIM_CLIP"] == {("Testo", "Idle"): "x.json"}
    h = R.module_constants(SHEET_PY, {"HEROES"})["HEROES"]
    assert h["Testo"][0] == "Testo" and h["Testo"][2] == pytest.approx(56 / 24)


def test_hit_type_default_blunt_fails_audio(repo):
    edit(repo, "audio", '  if (Key == TEXT("TESTO")) return TEXT("MAGIC");\n', "")
    rep = R.check_all(repo, [KEY])
    assert status(rep)["audio"] == "FAIL"
    msgs = " ".join(rep["heroes"][KEY]["checks"]["audio"]["messages"])
    assert "BLUNT" in msgs and "CMB-LUNGE-BLUNT" in msgs


def test_character_key_shadowed_by_earlier_substring(repo):
    edit(repo, "audio", 'TEXT("arthur")', 'TEXT("hero")')
    rep = R.check_all(repo, [KEY])
    assert status(rep)["audio"] == "FAIL"
    assert "ARTHUR" in rep["heroes"][KEY]["checks"]["audio"]["messages"][0]


def test_missing_cue_key_and_cook_dir(repo):
    edit(repo, "cue", f'"{KEY}": "/Game/PipelineCandidates/{KEY}/H2Anim/AM_{KEY}_HitReact', '"Other": "x')
    edit(repo, "ini", f'+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates/{KEY}/Rig")', "; removed")
    s = status(R.check_all(repo, [KEY]))
    assert s["cue"] == "FAIL" and s["cook"] == "FAIL"


def test_parent_cook_dir_covers_subfolders(repo):
    p = repo / R.PATHS["ini"]
    p.write_text('+DirectoriesToAlwaysCook=(Path="/Game/PipelineCandidates")\n', encoding="utf-8")
    assert status(R.check_all(repo, [KEY]))["cook"] == "PASS"


def test_names_missing_fails_and_sidekick_only_skips(repo):
    edit(repo, "names", '"en": "Test Hero"', '"en": "Someone"')
    assert status(R.check_all(repo, [KEY]))["names"] == "FAIL"
    edit(repo, f"art/pipeline-candidates/{AID}/asset-card.yaml", "OWNER_HERO_SLUG: null", "OWNER_HERO_SLUG: king-arthur")
    assert status(R.check_all(repo, [KEY]))["names"] == "SKIP"


def test_de010_contact_mismatch_and_de011_missing(repo):
    edit(repo, "de010", f'"{SPEC_REL}", 8)', f'"{SPEC_REL}", 7)')
    edit(repo, "de011", 'CAPTURE_LOOKS["Testo"] = "P2"\n', "")
    s = status(R.check_all(repo, [KEY]))
    assert s["de010"] == "FAIL" and s["de011"] == "FAIL"


def test_manifest_missing_fbx_and_clip_override(repo):
    (repo / f"art/pipeline-candidates/{AID}/run-h2anim/export/AM_{KEY}_HitReact.fbx").unlink()
    rep = R.check_all(repo, [KEY])
    assert status(rep)["manifest"] == "FAIL"
    assert "HitReact" in rep["heroes"][KEY]["checks"]["manifest"]["messages"][0]


def test_de010_and_manifest_disagree_on_lunge_spec(repo):
    other = f"{AID}/build-profiles/testo-h2anim-r2.json"
    (repo / "art/pipeline-candidates" / other).write_bytes((repo / "art/pipeline-candidates" / SPEC_REL).read_bytes())
    edit(repo, "manifest_py", "H2ANIM_CLIP = {}", f'H2ANIM_CLIP = {{("Testo", "LungeAttack"): "art/pipeline-candidates/{other}"}}')
    rep = R.check_all(repo, [KEY])
    assert status(rep)["de010"] == "FAIL" and status(rep)["manifest"] == "PASS"


def test_sheet_idle_mismatch_and_rig_applies_to(repo):
    edit(repo, "sheet", '"Testo": Hero("Testo", "TST", 56.0 / 24.0', '"Testo": Hero("Testo", "TST", 2.5')
    edit(repo, "rig", f'"{AID} (без оружия)"', '"ASSET-OTHER-001"')
    s = status(R.check_all(repo, [KEY]))
    assert s["sheet"] == "FAIL" and s["rig"] == "FAIL"


def test_bench_variant_missing_and_registry_planned(repo):
    (repo / R.PATHS["bench"] / f"S08BenchSarpedon-{KEY}.json").unlink()
    edit(repo, "registry", '"live-packaged-probe"', '"planned"')
    s = status(R.check_all(repo, [KEY]))
    assert s["bench"] == "FAIL" and s["registry"] == "FAIL"


def test_unknown_hero_fails_specs_and_exit_codes(repo, capsys):
    rep = R.check_all(repo, ["Nobody"])
    assert status(rep, "Nobody")["specs"] == "FAIL"
    assert R.main(["--repo", str(repo), "--heroes", "Nobody", "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["verdict"] == "FAIL"
    assert R.main(["--repo", str(repo / "missing")]) == 2


# ---- C57: блоки этапов заявки -----------------------------------------------------------------------------------------
def card_path(root: Path) -> Path:
    return root / f"art/pipeline-candidates/{AID}/asset-card.yaml"


def test_card_blocks_parse():
    text = ("KEY: X\nSTAGE3:\n  bake_run: \"a/b\"   # c\n  executor: {mechanism: \"subagent\"}\n"
            "STAGE5: []\nSTAGE6_SLOTS: {death: \"DTH\"}\n                  # comment\n"
            "STAGE7A:\n  import_run_live: \"r (26/26)\"\n  note: null\n    deeper: x\ndecided_by:\n  \"k\": \"v\"\n")
    b = R.card_blocks(text)
    assert set(b) == {"STAGE3", "STAGE5", "STAGE7A"}                       # STAGE6_SLOTS — не блок этапа
    assert b["STAGE3"] == {"bake_run": "a/b", "executor": "{mechanism: \"subagent\"}"}
    assert b["STAGE5"] == {} and b["STAGE7A"] == {"import_run_live": "r (26/26)", "note": None}


def test_card_stage7a_required_and_mvp_skips(repo):
    rep = R.check_all(repo)
    assert status(rep)["card"] == "PASS" and status(rep, "KingArthur")["card"] == "SKIP"
    assert "заявка пилота" in rep["heroes"][KEY]["checks"]["card"]["messages"][-1]
    edit(repo, card_path(repo).relative_to(repo).as_posix(), "STAGE7A:", "STAGE7X:")
    r = R.check_all(repo, [KEY])["heroes"][KEY]["checks"]["card"]
    assert r["status"] == "FAIL" and "нет блока STAGE7A" in r["messages"][0]


def test_card_keys_paths_and_placeholders(repo):
    rel = card_path(repo).relative_to(repo).as_posix()
    edit(repo, rel, "  review: ", "  reviewed: ")
    edit(repo, rel, "evidence/stage7a-20261014", "evidence/stage7a-missing")
    edit(repo, rel, '"r1: 4 pass"', '"<цикл → вердикты и баллы 4 клипов>"')
    msgs = R.check_all(repo, [KEY])["heroes"][KEY]["checks"]["card"]["messages"]
    assert any("STAGE7A: нет ключа review" in m for m in msgs)
    assert any("STAGE7A.evidence: нет пути" in m for m in msgs)
    assert any("STAGE7A.clip_acceptance: шаблон не заполнен" in m for m in msgs)


def test_card_pilot_names_and_stage3_needs_stage6(repo):
    rel = card_path(repo).relative_to(repo).as_posix()
    for old, new in (("  import_run: ", "  import_run_live: "), ("  import_profile: ", "  import_profiles: "),
                     ("  evidence: ", "  evidence_7a: "), ("  clip_acceptance: ", "  clip_acceptance_r1: ")):
        edit(repo, rel, old, new)
    assert status(R.check_all(repo, [KEY]))["card"] == "PASS"                # имена пилота
    p = card_path(repo)
    p.write_text(p.read_text(encoding="utf-8") + (
        f"STAGE3:\n  bake_run: \"art/pipeline-candidates/{AID}/20261014-h2ld-ue-import\"\n"
        f"  lookdev_run: \"art/pipeline-candidates/{AID}/20261014-h2ld-ldc-ue\"\n  profiles: [\"a.json\"]\n"
        "  executor: {mechanism: \"subagent\"}\n"), encoding="utf-8")
    r = R.check_all(repo, [KEY])["heroes"][KEY]["checks"]["card"]
    assert r["status"] == "FAIL" and "есть STAGE3, нет STAGE6" in r["messages"][0]
