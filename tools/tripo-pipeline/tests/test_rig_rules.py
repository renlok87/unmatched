"""Тесты правил контракта рига v2 (anim/rig_rules.py) и самосогласованности rig-contract.json.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
Без Blender: проверяются чистые функции, которые validate_clip.py вызывает на измеренных числах,
и данные контракта / профилей героев /4. Прогон validate_clip.py на файлах —
tools/tripo-pipeline/anim/run_rig_v2_validation.py (headless Blender).
"""
import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
PIPE = TESTS.parent
REPO = PIPE.parent.parent
sys.path.insert(0, str(PIPE / "anim"))
sys.path.insert(0, str(PIPE / "blender" / "candidate_build"))
import rig_rules as rr  # noqa: E402
import profile_schema  # noqa: E402

CONTRACT = json.loads((REPO / "docs/art-pipeline/rig/rig-contract.json").read_text(encoding="utf-8"))
V2 = CONTRACT["skeletons"]["UM_HUMANOID_17_v2"]
V1 = CONTRACT["skeletons"]["UM_HUMANOID_17_v1"]
PROFILES_RIG_V2 = {
    "Arthur": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-segmented-skeletal-um-fbx-v1-rig-v2-cli.json",
    "Merlin": "art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-segmented-skeletal-um-fbx-v1-rig-v2-cli.json",
}


def v2_bones(side_bone=None, **override):
    bones = {b["name"]: b["parent"] for b in V2["bones"] if b["name"] not in V2["weapon_bones"]}
    if side_bone:
        bones[side_bone] = V2["weapon_bones"][side_bone]["parent"]
    bones.update(override)
    return bones


# authored frame: face -Y, .L = +X (shoulders and hips of Medusa, metres)
AUTHORED_L = [(0.045, 0.0, 0.355), (0.03, 0.0, 0.19)]
AUTHORED_R = [(-0.045, 0.0, 0.355), (-0.03, 0.0, 0.19)]


def rot_z90(p):  # UM_FBX_v1 export space: x' = -y, y' = x
    return (-p[1], p[0], p[2])


class ContractTests(unittest.TestCase):
    def test_default_skeleton_is_v2(self):
        key, skel = rr.skeleton_entry(CONTRACT)
        self.assertEqual(key, "UM_HUMANOID_17_v2")
        self.assertEqual(skel["armature_object"]["name"], "SKEL_UM_Humanoid")
        self.assertEqual(skel["armature_object"]["legacy_policy"], "fail")
        with self.assertRaises(KeyError):
            rr.skeleton_entry(CONTRACT, "NOPE")

    def test_v1_kept_but_closed(self):
        self.assertTrue(V1["closed_for_new_clips"])
        self.assertEqual(V1["superseded_by"], "UM_HUMANOID_17_v2")
        # v1 bones unchanged: single weapon under hand.L with per-character parents (mannequin/readback still read them)
        weapon = next(b for b in V1["bones"] if b["name"] == "weapon")
        self.assertEqual(weapon["parent"], "hand.L")
        self.assertEqual(len(V1["bones"]), 17)

    def test_grandfathered_files_exist_and_match(self):
        for e in V1["grandfathered_files"]:
            p = REPO / e["path"]
            self.assertTrue(p.exists(), e["path"])
            self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), e["sha256"], e["path"])

    def test_weapon_bones_match_bone_list(self):
        listed = {b["name"]: b for b in V2["bones"]}
        for name, wb in V2["weapon_bones"].items():
            self.assertIn(name, listed)
            self.assertTrue(listed[name].get("optional"))
            self.assertEqual(listed[name]["parent"], wb["parent"])
            side = name.rsplit(".", 1)[1]
            self.assertTrue(wb["parent"].endswith("." + side), "weapon side must match hand side")
            self.assertEqual(wb["ue_name"], name.replace(".", "_"))
        self.assertNotIn("weapon", listed)

    def test_characters(self):
        chars = V2["characters"]
        self.assertEqual(chars["Medusa"]["weapon_bone"], "weapon.L")
        self.assertEqual(chars["Arthur"]["weapon_bone"], "weapon.R")
        self.assertEqual(chars["Merlin"]["weapon_bone"], "weapon.R")
        self.assertIsNone(chars["Harpy"]["weapon_bone"])
        for c in chars.values():
            self.assertTrue(c["weapon_bone"] is None or c["weapon_bone"] in V2["weapon_bones"])

    def test_ik_chains_consistent(self):
        self.assertEqual(rr.ik_chain_problems(V2), [])
        names = [c["name"] for c in V2["ik_chains"]["chains"]]
        for want in ("Root", "Spine", "Head", "LeftArm", "RightArm", "LeftLeg", "RightLeg"):
            self.assertIn(want, names)

    def test_ik_chain_problems_detects_errors(self):
        bad = copy.deepcopy(V2)
        bad["ik_chains"]["chains"].append({"name": "Broken", "start": "hand.L", "end": "spine"})
        bad["ik_chains"]["chains"].append({"name": "Ghost", "start": "tail", "end": "tail"})
        bad["ik_chains"]["chains"].append({"name": "LeftArm", "start": "arm_upper.L", "end": "hand.L", "goal": "arm_lower.L"})
        probs = rr.ik_chain_problems(bad)
        self.assertTrue(any("Broken" in p and "не предок" in p for p in probs))
        self.assertTrue(any("Ghost" in p for p in probs))
        self.assertTrue(any("повтор" in p for p in probs))
        self.assertTrue(any("цель" in p for p in probs))
        self.assertEqual(rr.ik_chain_problems({"bones": []}), ["нет ik_chains"])

    def test_ref_pose_and_boundaries_present(self):
        self.assertEqual(V2["ref_pose"]["expected_facing_yaw_deg"], 0)
        self.assertEqual(V2["ref_pose"]["export_space_rotation_z_degrees"], 90)
        self.assertEqual(set(V2["clip_boundaries"]["roles"]), set(rr.ROLES))
        preset = json.loads((REPO / V2["ref_pose"]["export_preset"]).read_text(encoding="utf-8"))
        self.assertEqual(preset["export_space_rotation_z_degrees"], V2["ref_pose"]["export_space_rotation_z_degrees"])


class VerdictTests(unittest.TestCase):
    def test_expected_bones_by_character(self):
        req, opt = rr.expected_bones(V2, "Arthur")
        self.assertEqual(req["weapon.R"], "hand.R")
        self.assertNotIn("weapon.L", req)
        self.assertNotIn("weapon.L", opt)
        req, opt = rr.expected_bones(V2)
        self.assertEqual(set(opt), {"weapon.L", "weapon.R"})
        req, opt = rr.expected_bones(V2, "Harpy")
        self.assertEqual(opt, {})
        self.assertEqual(len(req), 16)
        with self.assertRaises(KeyError):
            rr.expected_bones(V2, "Nobody")

    def test_skeleton_contract_verdict(self):
        req, opt = rr.expected_bones(V2, "Medusa")
        self.assertEqual(rr.skeleton_contract_verdict(v2_bones("weapon.L"), req, opt)[0], "pass")
        st, d = rr.skeleton_contract_verdict(v2_bones(), req, opt)
        self.assertEqual((st, d["missing"]), ("fail", ["weapon.L"]))
        st, d = rr.skeleton_contract_verdict(v2_bones("weapon.L", extra_leaf="head"), req, opt)
        self.assertEqual((st, d["extra"]), ("warn", ["extra_leaf"]))
        st, d = rr.skeleton_contract_verdict(v2_bones("weapon.L", head="hips"), req, opt)
        self.assertEqual((st, d["parent_mismatch"]), ("fail", ["head"]))

    def test_weapon_verdict(self):
        self.assertEqual(rr.weapon_verdict(v2_bones("weapon.L"), V2, "Medusa")[0], "pass")
        self.assertEqual(rr.weapon_verdict(v2_bones("weapon.R"), V2, "Arthur")[0], "pass")
        self.assertEqual(rr.weapon_verdict(v2_bones(), V2, "Harpy")[0], "pass")
        self.assertEqual(rr.weapon_verdict(v2_bones("weapon.R"), V2)[0], "pass")
        cases = [
            (v2_bones("weapon.L"), "Arthur"),                        # wrong side for the hero
            (v2_bones(weapon="hand.R"), "Arthur"),                   # legacy single name
            (v2_bones("weapon.L", **{"weapon.R": "hand.R"}), None),  # two weapon bones
            (v2_bones(**{"weapon.L": "hand.R"}), None),              # weapon.L under the right hand
            (v2_bones("weapon.R"), "Harpy"),                         # Harpy has no weapon
            (v2_bones(), "Merlin"),                                  # Merlin needs weapon.R
        ]
        for bones, ch in cases:
            st, d = rr.weapon_verdict(bones, V2, ch)
            self.assertEqual(st, "fail", (bones.get("weapon"), ch, d))
            self.assertTrue(d["problems"])
        self.assertEqual(rr.weapon_verdict({"weapon": "hand.L"}, V1)[0], "info")

    def test_armature_name_verdict(self):
        rule2, rule1 = V2["armature_object"], V1["armature_object"]
        self.assertEqual(rr.armature_name_verdict("SKEL_UM_Humanoid", rule2)[0], "pass")
        self.assertEqual(rr.armature_name_verdict("SKEL_Medusa", rule2)[0], "fail")
        self.assertEqual(rr.armature_name_verdict("SKEL_Medusa", rule1)[0], "warn")
        self.assertEqual(rr.armature_name_verdict("Armature", rule2)[0], "fail")
        self.assertEqual(rr.armature_name_verdict("Armature", rule2, external=True)[0], "info")

    def test_skeleton_version_verdict(self):
        draft = V1["grandfathered_files"][0]["sha256"]
        self.assertEqual(rr.skeleton_version_verdict("UM_HUMANOID_17_v1", V1, draft)[0], "warn")
        self.assertEqual(rr.skeleton_version_verdict("UM_HUMANOID_17_v1", V1, "0" * 64)[0], "fail")
        self.assertEqual(rr.skeleton_version_verdict("UM_HUMANOID_17_v2", V2, "0" * 64)[0], "pass")

    def test_facing(self):
        authored = rr.facing_yaw_deg(AUTHORED_L, AUTHORED_R)
        self.assertAlmostEqual(authored, -90.0, places=6)
        exported = rr.facing_yaw_deg([rot_z90(p) for p in AUTHORED_L], [rot_z90(p) for p in AUTHORED_R])
        self.assertAlmostEqual(exported, 0.0, places=6)
        self.assertEqual(rr.facing_verdict(exported, V2["ref_pose"])[0], "pass")
        st, d = rr.facing_verdict(authored, V2["ref_pose"])
        self.assertEqual((st, d["delta_deg"]), ("fail", -90.0))
        self.assertEqual(rr.facing_verdict(authored, V2["ref_pose"], external=True)[0], "info")
        self.assertEqual(rr.facing_verdict(7.5, V2["ref_pose"])[0], "pass")   # asymmetric miniature pose
        self.assertEqual(rr.facing_verdict(12.0, V2["ref_pose"])[0], "fail")
        with self.assertRaises(ValueError):
            rr.facing_yaw_deg([(0, 0, 1)], [(0, 0, 0)])

    def test_yaw_delta_wraps(self):
        self.assertAlmostEqual(rr.yaw_delta_deg(179.0, -179.0), -2.0)
        self.assertAlmostEqual(rr.yaw_delta_deg(-179.0, 179.0), 2.0)
        self.assertAlmostEqual(rr.yaw_delta_deg(90.0, -90.0), 180.0)

    def test_root_axis(self):
        self.assertEqual(rr.root_axis_verdict((0.0, 1.0, 0.0), V2["ref_pose"])[0], "pass")
        self.assertEqual(rr.root_axis_verdict((1.0, 0.0, 0.0), V2["ref_pose"])[0], "warn")
        self.assertEqual(rr.root_axis_verdict((0.0, 0.0, 1.0), V2["ref_pose"])[0], "info")

    def test_boundaries(self):
        rules = V2["clip_boundaries"]
        self.assertEqual(rr.boundary_verdict("oneshot", 0.0, 0.0, rules)[0], "pass")
        st, d = rr.boundary_verdict("oneshot", 0.0, 0.512, rules)
        self.assertEqual((st, d["not_rest"]), ("fail", ["last"]))
        self.assertEqual(rr.boundary_verdict("terminal", 0.0, 0.512, rules)[0], "pass")
        self.assertEqual(rr.boundary_verdict("terminal", 0.02, 0.512, rules)[0], "fail")
        self.assertEqual(rr.boundary_verdict("idle", 0.004, 0.0049, rules)[0], "pass")
        self.assertEqual(rr.boundary_verdict("idle", 0.0, 0.3, rules, external=True)[0], "info")

    def test_default_role(self):
        self.assertEqual(rr.default_role(True), "idle")
        self.assertEqual(rr.default_role(False), "oneshot")
        self.assertEqual(rr.default_role(False, "Terminal"), "terminal")
        with self.assertRaises(ValueError):
            rr.default_role(False, "death")

    def test_ue_clip_import(self):
        ok = {"force_root_lock": True, "enable_root_motion": False, "factory": "FbxFactory"}
        self.assertEqual(rr.ue_clip_import_problems(ok, CONTRACT), [])
        self.assertTrue(rr.ue_clip_import_problems({**ok, "force_root_lock": False}, CONTRACT))
        self.assertTrue(rr.ue_clip_import_problems({**ok, "factory": "InterchangeFbxTranslator"}, CONTRACT))
        self.assertTrue(rr.ue_clip_import_problems({"factory": "FbxFactory"}, CONTRACT))
        rm = {"force_root_lock": False, "enable_root_motion": True, "factory": "FbxFactory"}
        self.assertEqual(rr.ue_clip_import_problems(rm, CONTRACT, "root_motion"), [])
        self.assertTrue(rr.ue_clip_import_problems(ok, CONTRACT, "sideways"))


class HeroProfileRigV2Tests(unittest.TestCase):
    def test_profiles_follow_v2(self):
        base = {b["name"] for b in V2["bones"] if b["name"] not in V2["weapon_bones"]}
        for char, rel in PROFILES_RIG_V2.items():
            prof = json.loads((REPO / rel).read_text(encoding="utf-8"))
            self.assertEqual(profile_schema.validate(prof), [], rel)
            want = V2["characters"][char]["weapon_bone"]
            bones = {b[0]: b[1] for b in prof["armature"]["bones"]}
            self.assertEqual(set(bones), base | {want}, rel)
            self.assertEqual(bones[want], V2["weapon_bones"][want]["parent"])
            self.assertEqual(prof["armature"]["object"], V2["armature_object"]["name"])
            self.assertEqual(prof["meshes"]["weapon"]["bone"], want)
            weapon_socket = next(s for s in prof["sockets"] if s["name"] == "Weapon")
            self.assertEqual(weapon_socket["bone"], want)
            self.assertTrue(prof["profile_id"].endswith("/4"), prof["profile_id"])
            self.assertIn("UM_FBX_v1.json", prof["fbx_preset"])

    def test_profile_ids_unique(self):
        # профили W4-D сначала получили /3, а W4-B независимо выдала /3 своим *-um-master.json;
        # один profile_id на два разных файла ломает ссылки run -> профиль (build-report profile.id)
        seen = {}
        for path in sorted(REPO.glob("art/pipeline-candidates/*/build-profiles/*.json")):
            pid = json.loads(path.read_text(encoding="utf-8")).get("profile_id")
            if pid is None:
                continue
            rel = path.relative_to(REPO).as_posix()
            self.assertNotIn(pid, seen, "profile_id %s: %s and %s" % (pid, seen.get(pid), rel))
            seen[pid] = rel
        for rel in PROFILES_RIG_V2.values():
            self.assertIn(rel, seen.values())


if __name__ == "__main__":
    unittest.main()
