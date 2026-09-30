"""Unit tests of look-dev C (group B, 2026-09-30): profile skeletal-adopt on the King Arthur look-dev run (report format
h2-lookdev-arthur/1, normaliser skeletal_adopt_lookdev.lookdev_arthur) and on the Harpy look-dev run (h3-lookdev-harpy/1,
lookdev_harpy).

They run adopt on the real look-dev runs of the repo, then break single inputs in a temporary copy of the profile and
check that adopt fails for the right reason. No Blender, no UE, no network.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

from test_pipeline import TESTS, tp

sys.path.insert(0, str(TESTS.parent))
import skeletal_adopt  # noqa: E402

REPO = Path(tp.__file__).resolve().parents[2]
ARTHUR = REPO / "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2ld-lookdev-ue-import.json"
HARPY = REPO / "art/pipeline-candidates/ASSET-HARPY-001/build-profiles/harpy-h3ld-lookdev-ue-import.json"
# ue-inputs-report.json of Arthur hashes the local zone map of the look-dev work folder (not committed)
ARTHUR_LOCAL = REPO / "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-lookdev/work/lookdev/T_Zone_4K.png"


def run_adopt(profile, repo_path=lambda rel: REPO / rel):
    preset = json.loads((REPO / profile["fbx_preset"]).read_text(encoding="utf-8"))
    return skeletal_adopt.adopt(profile, repo_path, lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
                                lambda p: tp.inspect_png(p).get("pixels"), preset)


def failed(res):
    return json.dumps({k: v for k, v in res["checks"].items() if not v["passed"]}, indent=1)[:3000]


@unittest.skipUnless(ARTHUR.is_file() and ARTHUR_LOCAL.is_file(), "Arthur look-dev run (with its local work/) not here")
class ArthurLookdevAdoptTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(ARTHUR.read_text(encoding="utf-8"))

    def test_real_lookdev_run_adopts(self):
        res = run_adopt(self.profile)
        self.assertTrue(res["passed"], failed(res))
        norm = res["bake"]["normalised"]
        self.assertEqual(norm["format"], "h2-lookdev-arthur/1")
        self.assertTrue(all(c["passed"] for c in norm["checks"].values()))
        # bones and sockets are the H2 bake's (17 bones with weapon.R), FBX bytes the look-dev export's
        self.assertEqual(res["checks"]["skeleton_contract"]["measured"]["bones"], 17)
        self.assertIn("texture:TeamAccent", res["keys"])
        self.assertIn("texture:LUT", res["keys"])

    def test_h2_profile_other_than_pinned_fails(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["h2_adopt_profile"]["sha256"] = "0" * 64
        res = run_adopt(p)
        self.assertFalse(res["bake"]["normalised"]["checks"]["h2_adopt_profile_pinned"]["passed"])
        self.assertFalse(res["passed"])

    def test_texture_outside_the_lookdev_manifest_fails(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["textures"]["BC"] = "../20260929-h2-bake/textures/runtime_2k/T_KingArthur_H2_BC.png"
        res = run_adopt(p)
        self.assertFalse(res["bake"]["normalised"]["checks"]["lookdev_manifest_lists_the_adopted_bytes"]["passed"])
        self.assertFalse(res["passed"])


@unittest.skipUnless(HARPY.is_file(), "Harpy look-dev run not in this checkout")
class HarpyLookdevAdoptTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(HARPY.read_text(encoding="utf-8"))

    def test_real_lookdev_run_adopts(self):
        res = run_adopt(self.profile)
        self.assertTrue(res["passed"], failed(res))
        norm = res["bake"]["normalised"]
        self.assertEqual(norm["format"], "h3-lookdev-harpy/1")
        self.assertTrue(all(c["passed"] for c in norm["checks"].values()))
        # 16 bones, no weapon bone (contract characters.Harpy.weapon_bone = null)
        self.assertEqual(res["checks"]["skeleton_contract"]["measured"]["bones"], 16)
        exp = res["views"]["build"]["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_ue_predicted"]
        # H3 rig report measure.ue_predicted_bounds_uu (same geometry, read back by ld_fbx)
        self.assertEqual([round(v, 3) for v in exp["min"]], [-18.976, -32.022, 4.795])
        self.assertEqual([round(v, 3) for v in exp["max"]], [12.61, 31.936, 42.0])

    def test_opengl_normal_is_not_accepted(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["textures"]["N"] = "textures/2k/T_Harpy_H3LD_N_OpenGL.png"
        res = run_adopt(p)
        self.assertFalse(res["bake"]["normalised"]["checks"]["normal_is_the_h3_directx_map"]["passed"])
        self.assertFalse(res["passed"])

    def test_weapon_bone_in_profile_breaks_the_skeleton_contract(self):
        p = copy.deepcopy(self.profile)
        p["armature"]["bones"].append(["weapon.R", "hand.R"])
        res = run_adopt(p)
        self.assertFalse(res["checks"]["skeleton_contract"]["passed"])
        self.assertFalse(res["passed"])


if __name__ == "__main__":
    unittest.main()
