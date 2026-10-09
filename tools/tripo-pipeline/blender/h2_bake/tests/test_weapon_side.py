"""D-1: weapon side and presence of the shared h2_bake stages come from the profile and the rig contract.

Plain Python (no Blender): profile.py helpers used by st_rig / st_seams / st_preview / st_lookdev / st_team.
Run: python -m pytest tools/tripo-pipeline/blender/h2_bake/tests -q"""

import copy
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
sys.path.insert(0, str(HERE.parents[1]))

from h2_bake import profile as PR  # noqa: E402

MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"


@pytest.fixture(scope="module")
def contract():
    c = PR.load_contract(REPO)
    assert c is not None, "docs/art-pipeline/rig/rig-contract.json is missing"
    return c


@pytest.fixture()
def medusa():
    return json.loads(MEDUSA.read_text(encoding="utf-8"))


def weapon_part(p):
    return next(n for n, cfg in p["parts"].items() if cfg["mesh"] == "weapon")


def right_handed(p, character="Arthur"):
    """Medusa layout with the weapon bone on the right hand (as Arthur / Merlin in the contract)."""
    q = copy.deepcopy(p)
    q["rig"]["character"] = character
    for b in q["rig"]["bones"]:
        if b[0] == "weapon.L":
            b[0], b[1] = "weapon.R", "hand.R"
            b[2][0], b[3][0] = -b[2][0], -b[3][0]
    q["rig"]["weights"][weapon_part(q)] = {"kind": "rigid", "bone": "weapon.R"}
    for s in q.get("sockets", []):
        if s.get("bone") == "weapon.L":
            s["bone"] = "weapon.R"
    return q


def unarmed(p, character="Harpy"):
    """Medusa layout without a weapon: the bow part becomes a body part on hand.L, no weapon bone, no weapon mesh."""
    q = copy.deepcopy(p)
    q["rig"]["character"] = character
    wp = weapon_part(q)
    q["parts"][wp]["mesh"] = "body"
    q["rig"]["bones"] = [b for b in q["rig"]["bones"] if b[0] not in PR.WEAPON_BONES]
    q["rig"]["weights"][wp] = {"kind": "rigid", "bone": "hand.L"}
    del q["meshes"]["weapon"]
    return q


# ------------------------------------------------------------------ Medusa: old behaviour, byte-for-byte inputs
def test_medusa_resolves_to_previous_layout(medusa, contract):
    assert PR.validate(medusa) == []
    assert PR.weapon_bone(medusa, contract) == "weapon.L"
    assert PR.weapon_bone(medusa) == "weapon.L"  # without the contract: from rig.bones
    assert PR.has_weapon(medusa)
    assert PR.figure_roles(medusa) == ("body", "weapon", "base")
    assert PR.skinned_roles(medusa) == ("body", "weapon")
    assert PR.figure_mesh_names(medusa) == ("SK_Medusa_H2_Body", "SK_Medusa_H2_Bow", "SM_Medusa_H2_Base")
    assert PR.weapon_hand("weapon.L") == "hand.L"
    assert PR.weapon_side_sign("weapon.L") == 1.0
    assert PR.content_key(medusa) == "medusa"  # probe labels medusa-h2-blend / medusa-h2-fbx


def test_medusa_rig_checks_keep_names_and_values():
    bones = {"hand.L": "arm_lower.L", "weapon.L": "hand.L", "hand.R": "arm_lower.R"}
    assert PR.weapon_bone_verdict(bones, "weapon.L") == (True, "hand.L", "hand.L")
    assert PR.weapon_side_check("weapon.L") == ("export_frame_bow_on_rotated_left", "bow on +Y of the export frame (UE -Y)")
    # the old check failed on the v1 name and on a wrong parent: still so
    assert PR.weapon_bone_verdict(dict(bones, weapon="hand.L"), "weapon.L")[0] is False
    assert PR.weapon_bone_verdict(dict(bones, **{"weapon.L": "hand.R"}), "weapon.L")[0] is False
    assert PR.weapon_bone_verdict({"hand.L": "arm_lower.L"}, "weapon.L") == (False, None, "hand.L")


# ------------------------------------------------------------------ right-handed (weapon.R)
def test_right_handed_profile(medusa, contract):
    q = right_handed(medusa)
    assert PR.validate(q) == []
    assert PR.weapon_bone(q, contract) == "weapon.R"
    assert PR.weapon_bone(q) == "weapon.R"
    assert PR.weapon_hand("weapon.R") == "hand.R"
    assert PR.weapon_side_sign("weapon.R") == -1.0
    assert PR.figure_roles(q) == ("body", "weapon", "base")
    name, expected = PR.weapon_side_check("weapon.R")
    assert name == "export_frame_bow_on_rotated_right" and "-Y" in expected


def test_right_handed_bone_verdict():
    good = {"hand.R": "arm_lower.R", "weapon.R": "hand.R"}
    assert PR.weapon_bone_verdict(good, "weapon.R") == (True, "hand.R", "hand.R")
    assert PR.weapon_bone_verdict(dict(good, **{"weapon.L": "hand.L"}), "weapon.R")[0] is False  # both sides
    assert PR.weapon_bone_verdict({"weapon.L": "hand.L"}, "weapon.R")[0] is False  # Medusa's bone on Arthur
    assert PR.weapon_bone_verdict({"weapon.R": "hand.L"}, "weapon.R")[0] is False  # wrong parent


def test_contract_beats_profile_bones(medusa, contract):
    """Arthur (contract weapon.R) with Medusa's weapon.L bone: the resolved bone is weapon.R, so the read-back check
    of the rig stage fails on the profile's weapon.L."""
    q = copy.deepcopy(medusa)
    q["rig"]["character"] = "Arthur"
    assert PR.weapon_bone(q, contract) == "weapon.R"
    assert PR.weapon_bone_verdict({"weapon.L": "hand.L"}, PR.weapon_bone(q, contract))[0] is False


def test_explicit_weapon_bone(medusa, contract):
    q = copy.deepcopy(medusa)
    q["rig"]["weapon_bone"] = "weapon.L"
    assert PR.validate(q) == []
    assert PR.weapon_bone(q, contract) == "weapon.L"
    q["rig"]["weapon_bone"] = "weapon.R"  # contradicts the contract (Medusa -> weapon.L) and rig.bones
    with pytest.raises(ValueError):
        PR.weapon_bone(q, contract)
    assert any("not in rig.bones" in m for m in PR.validate(q))
    q["rig"]["weapon_bone"] = "weapon"
    assert any("weapon.L, weapon.R or null" in m for m in PR.validate(q))
    with pytest.raises(ValueError):
        PR.weapon_bone(q)


def test_character_missing_from_contract_uses_rig_bones(medusa, contract):
    q = right_handed(medusa, character="NewHero")
    assert PR.weapon_bone(q, contract) == "weapon.R"
    r = unarmed(medusa, character="NewHero")
    assert PR.weapon_bone(r, contract) is None


# ------------------------------------------------------------------ no weapon (null)
def test_unarmed_profile(medusa, contract):
    q = unarmed(medusa)
    assert PR.validate(q) == []
    assert PR.weapon_bone(q, contract) is None
    assert PR.weapon_bone(q) is None
    assert not PR.has_weapon(q)
    assert PR.figure_roles(q) == ("body", "base")
    assert PR.skinned_roles(q) == ("body",)
    assert PR.figure_mesh_names(q) == ("SK_Medusa_H2_Body", "SM_Medusa_H2_Base")
    assert PR.weapon_side_check(None) is None
    assert PR.weapon_side_sign(None) is None and PR.weapon_hand(None) is None


def test_unarmed_bone_verdict():
    assert PR.weapon_bone_verdict({"hand.L": "arm_lower.L"}, None) == (True, [], "no weapon bone (character without a weapon)")
    assert PR.weapon_bone_verdict({"weapon.L": "hand.L"}, None) == (False, ["weapon.L"], "no weapon bone (character without a weapon)")
    assert PR.weapon_bone_verdict({"weapon": "hand.R"}, None)[0] is False


def test_unarmed_explicit_null(medusa, contract):
    q = unarmed(medusa)
    q["rig"]["weapon_bone"] = None
    assert PR.validate(q) == []
    assert PR.weapon_bone(q, contract) is None
    q["rig"]["character"] = "Medusa"  # contract says weapon.L: an explicit null contradicts it
    with pytest.raises(ValueError):
        PR.weapon_bone(q, contract)


# ------------------------------------------------------------------ validation of the weapon layout
def test_validation_problems(medusa):
    two = copy.deepcopy(medusa)
    extra = next(n for n, cfg in two["parts"].items() if cfg["mesh"] == "body")
    two["parts"][extra]["mesh"] = "weapon"
    assert any("at most one weapon part" in m for m in PR.validate(two))
    no_mesh = copy.deepcopy(medusa)
    del no_mesh["meshes"]["weapon"]
    assert any("meshes.weapon missing" in m for m in PR.validate(no_mesh))
    both = copy.deepcopy(medusa)
    both["rig"]["bones"].append(["weapon.R", "hand.R", [-0.1, 0.0, 0.3], [-0.12, 0.0, 0.3]])
    assert any("at most one weapon bone" in m for m in PR.validate(both))
    with pytest.raises(ValueError):
        PR.weapon_bone(both)


def test_content_key():
    assert PR.content_key({"asset_id": "ASSET-MEDUSA-001"}) == "medusa"
    assert PR.content_key({"asset_id": "ASSET-KING-ARTHUR-001"}) == "king-arthur"
    assert PR.content_key({"asset_id": "ASSET-HARPY-001"}) == "harpy"
