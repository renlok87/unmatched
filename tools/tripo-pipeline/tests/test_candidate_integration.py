"""Integration: the real Medusa skeletal candidate with the real Blender 5.2 (headless only).

1. `--backend headless` runs preflight -> import -> verify -> atlas -> build on the paid
   Tripo source that is already in the repository (read only), into a temporary run dir
   outside the repository; the second run changes no file.
2. The build stage script runs in "live" isolation inside a Blender session with user
   data, exactly like blender-mcp's execute_code (tests/blender_live_harness.py): the
   session is left unchanged and the FBX bytes equal the headless ones.
3. If the committed T4 run exists, its FBX hashes are reproduced.

Nothing is written into the repository. Skipped when Blender or the Medusa source is missing
or TRIPO_PIPELINE_SKIP_BLENDER=1.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_blender_integration import BLENDER, SKIP, blender, sha
from test_pipeline import TOOL, tp

REPO = TOOL.parents[2]
MEDUSA = REPO / "art/pipeline-candidates/ASSET-MEDUSA-001"
PROFILE = "art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-segmented-skeletal-um-fbx-v1.json"
SOURCE = REPO / "blender/ASSET-MEDUSA-001/tripo-source/b6253e58/medusa-segmented-retopo.glb"
COMMITTED_RUN = MEDUSA / "20260928-t4-um-fbx-v1"


@unittest.skipIf(SKIP or not SOURCE.is_file() or not (REPO / PROFILE).is_file(), "Blender or Medusa source missing")
class RealMedusaCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tripo-pipeline-medusa-"))
        cls.run_dir = cls.tmp / "run"
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith("TRIPO_PIPELINE_")}
        cls.env["TRIPO_PIPELINE_BLENDER"] = BLENDER
        cls.cli("init", "--run-dir", str(cls.run_dir), "--asset-id", "ASSET-MEDUSA-001", "--primary-source",
                "tripo-b6253e58", "--primary-role", "segmented-retopo-glb", "--profile", "skeletal-candidate",
                "--build-profile", PROFILE)
        for spec in ("tripo-d562f057.json", "tripo-b6253e58.json"):
            cls.cli("register-source", "--run-dir", str(cls.run_dir), "--spec", str(MEDUSA / "source-specs" / spec))
        cls.first = cls.cli("run", "--run-dir", str(cls.run_dir))
        cls.snap1 = tp.snapshot(cls.run_dir)
        cls.second = cls.cli("run", "--run-dir", str(cls.run_dir))
        cls.snap2 = tp.snapshot(cls.run_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def cli(cls, *args):
        proc = subprocess.run([sys.executable, str(TOOL), "--repo-root", str(REPO), *args], capture_output=True,
                              text=True, env=cls.env, timeout=1800)
        if proc.returncode != 0:
            raise AssertionError("pipeline %s failed:\n%s\n%s" % (args, proc.stdout, proc.stderr))
        return proc.stdout

    def report(self):
        return json.loads((self.run_dir / "reports/build-report.json").read_text(encoding="utf-8"))

    def test_build_contracts_pass_and_second_run_is_noop(self):
        self.assertIn("build     executed", self.first)
        self.assertIn("build     skipped", self.second)
        self.assertEqual(self.snap1, self.snap2)
        report = self.report()
        self.assertTrue(report["passed"], [k for k, c in report["checks"].items() if not c["passed"]])
        self.assertEqual(report["orientation"]["flipped_parts"],
                         ["tripo_part_10", "tripo_part_13", "tripo_part_14", "tripo_part_8"])
        self.assertEqual(report["checks"]["reference_v2_same_geometry_uv_material"]["passed"], True)

    def test_export_follows_um_fbx_v1_face_plus_x(self):
        report = self.report()
        settings = report["exports"]["settings"]
        self.assertEqual(settings["preset"]["name"], "UM_FBX_v1")
        self.assertEqual(settings["export_space_rotation_z_degrees"], 90.0)
        self.assertTrue(settings["use_triangles"])
        self.assertEqual(report["axes"]["export_frame"]["front_axis"], "+X")
        for name in ("export_frame_face_points_along_rotated_front", "export_frame_bow_on_rotated_side",
                     "triangulate_changes_no_geometry", "reference_corner_normals_rotated_consistently",
                     "roundtrip_bone_hierarchy_and_rest_positions", "roundtrip_scale_ratio_1"):
            self.assertTrue(report["checks"][name]["passed"], (name, report["checks"][name]))
        face = report["axes"]["export_frame"]["face_mean_normal"]
        self.assertGreater(face[0], 0.3)
        pred = report["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_ue_predicted"]
        authored = report["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_blender_axes"]
        # UE (x, y) = (-authored y, -authored x)
        self.assertAlmostEqual(pred["min"][0], -authored["max"][1], places=2)
        self.assertAlmostEqual(pred["min"][1], -authored["max"][0], places=2)

    def test_committed_candidate_is_reproduced(self):
        manifest = COMMITTED_RUN / "manifest.json"
        if not manifest.is_file():
            self.skipTest("committed T4 run not present")
        committed = {e["path"]: e["sha256"] for e in json.loads(manifest.read_text(encoding="utf-8"))["exports"]
                     if not e.get("superseded_by")}
        for rel, digest in committed.items():
            self.assertEqual(sha(self.run_dir / rel), digest, rel)

    def test_live_build_leaves_session_untouched_and_matches_headless_bytes(self):
        out = self.tmp / "live"
        out.mkdir()
        params = {"source": str(SOURCE), "profile": str(REPO / PROFILE), "fbx_preset": str(REPO / tp.DEFAULT_FBX_PRESET),
                  "atlas_report": str(self.run_dir / "reports/atlas-report.json"),
                  "textures_dir": str(self.run_dir / "textures"), "repo_root": str(REPO),
                  "blend_out": str(out / "work.blend"), "sk_fbx_out": str(out / "SK_Medusa_Candidate.fbx"),
                  "base_fbx_out": str(out / "SM_Medusa_Base_Candidate.fbx"), "report_out": str(out / "build-report.json")}
        (out / "params.json").write_text(json.dumps(params), encoding="utf-8")
        job = out / "job.json"
        job.write_text(json.dumps({"mode": "live", "result": str(out / "result.json"), "collide": False,
                                   "stages": [{"stage": "build", "script": str(tp.BLENDER_SCRIPTS["build"]),
                                               "params": str(out / "params.json")}]}), encoding="utf-8")
        blender(job)
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
        self.assertIsNone(result["runs"][0]["error"], result["runs"][0]["error"])
        self.assertIn("isolation=live", result["runs"][0]["stdout"])
        before, after = dict(result["before"]), dict(result["after"])
        before.pop("_is_dirty"), after.pop("_is_dirty")
        self.assertEqual(after, before, "live build changed the user's session")
        for name in ("SK_Medusa_Candidate.fbx", "SM_Medusa_Base_Candidate.fbx"):
            self.assertEqual(sha(out / name), sha(self.run_dir / "export" / name), name)
        live, headless = self.report(), json.loads((out / "build-report.json").read_text(encoding="utf-8"))
        live, headless = dict(live), dict(headless)
        self.assertNotEqual(live.pop("isolation_note"), headless.pop("isolation_note"))
        self.assertEqual(live, headless, "reports differ beyond the isolation note")


if __name__ == "__main__":
    unittest.main()
