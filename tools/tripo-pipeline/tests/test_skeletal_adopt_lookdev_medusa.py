"""Unit tests of LD-medusa-ue: profile skeletal-adopt on the Medusa look-dev run (report format h2-lookdev/1,
normaliser skeletal_adopt_formats.h2_lookdev) and candidate.library_inputs (the hero MatLUT pinned by the profile).

They run adopt on the real look-dev run of the repo (art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev and
the H2.1 bake it derives from), then break single inputs in a temporary copy of the profile and check that adopt fails
for the right reason. No Blender, no UE, no network.

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
PROFILE = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2ld-lookdev-ue-import.json"


def run_adopt(profile, repo_path=lambda rel: REPO / rel):
    preset = json.loads((REPO / profile["fbx_preset"]).read_text(encoding="utf-8"))
    return skeletal_adopt.adopt(profile, repo_path, lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
                                lambda p: tp.inspect_png(p).get("pixels"), preset)


@unittest.skipUnless(PROFILE.is_file() and (REPO / "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-lookdev/reports/"
                                            "ld-fbx-report.json").is_file(), "Medusa look-dev run not in this checkout")
class MedusaLookdevAdoptTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    def test_real_lookdev_run_adopts(self):
        res = run_adopt(self.profile)
        self.assertTrue(res["passed"], json.dumps({k: v for k, v in res["checks"].items() if not v["passed"]}, indent=1))
        self.assertIn("library_inputs_pinned_by_profile", res["checks"])
        norm = res["bake"]["normalised"]
        self.assertEqual(norm["format"], "h2-lookdev/1")
        self.assertTrue(all(c["passed"] for c in norm["checks"].values()))
        exp = res["views"]["build"]["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_ue_predicted"]
        # H2.1 rig report expected_ue_bounds_uu_at_import_scale_1.skeletal (same geometry, read back by ld_fbx)
        self.assertEqual([round(v, 3) for v in exp["min"]], [-9.29, -16.358, 5.752])
        self.assertEqual([round(v, 3) for v in exp["max"]], [9.933, 10.742, 55.009])
        self.assertIn("texture:LUT", res["keys"])

    def test_lut_other_than_pinned_fails_adopt(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["library_inputs"]["LUT"]["sha256"] = "0" * 64
        res = run_adopt(p)
        self.assertFalse(res["checks"]["library_inputs_pinned_by_profile"]["passed"])
        self.assertFalse(res["passed"])

    def test_opengl_normal_is_not_accepted(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["textures"]["N"] = "textures/T_Medusa_H2LD_2K_N_OpenGL.png"
        res = run_adopt(p)
        self.assertFalse(res["bake"]["normalised"]["checks"]["normal_is_the_h21_directx_map"]["passed"])
        self.assertFalse(res["passed"])

    def test_wrong_lookdev_profile_fails_the_manifest_check(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["bake_profile"] = "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-h2-bake-h2.json"
        res = run_adopt(p)
        self.assertFalse(res["bake"]["normalised"]["checks"]["run_manifest_lists_the_adopted_bytes"]["passed"])
        self.assertFalse(res["passed"])


if __name__ == "__main__":
    unittest.main()
