"""Integration tests with the real Blender 5.2 (headless only; the live GUI is never touched).

1. The pipeline's headless backend runs import -> verify -> export on a small GLB
   twice: the second run changes no file (idempotency with real Blender output).
2. The same stage scripts run in "live" isolation mode inside a Blender session
   that already holds user data, exactly the way blender-mcp's execute_code runs
   them (tests/blender_live_harness.py). The session must be left unchanged and
   the outputs must equal the headless outputs (FBX byte-identical when no object
   names collide).

Skipped when Blender is not installed or TRIPO_PIPELINE_SKIP_BLENDER=1.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_pipeline import TESTS, TOOL, install_preset, tp

BLENDER = os.environ.get("TRIPO_PIPELINE_BLENDER", tp.DEFAULT_BLENDER)
HARNESS = TESTS / "blender_live_harness.py"
SKIP = os.environ.get("TRIPO_PIPELINE_SKIP_BLENDER") == "1" or not Path(BLENDER).is_file()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def blender(job_path):
    proc = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(HARNESS),
                           "--", str(job_path)], capture_output=True, timeout=600,
                          creationflags=0x08000000 if os.name == "nt" else 0)
    out = proc.stdout.decode("utf-8", "replace")
    if proc.returncode != 0 or "HARNESS_OK" not in out:
        raise AssertionError("blender harness failed (%s):\n%s\n%s" % (proc.returncode, out[-3000:],
                                                                      proc.stderr.decode("utf-8", "replace")[-2000:]))
    return out


@unittest.skipIf(SKIP, "Blender not available")
class RealBlenderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="tripo-pipeline-blender-"))
        cls.repo = cls.tmp / "repo"
        (cls.repo / ".git").mkdir(parents=True)
        cls.preset = install_preset(cls.repo)
        cls.glb = cls.repo / "tripo-source/t1/model.glb"
        cls.glb.parent.mkdir(parents=True)
        job = cls.tmp / "make.json"
        job.write_text(json.dumps({"mode": "make-glb", "glb": str(cls.glb)}), encoding="utf-8")
        blender(job)
        info = tp.inspect_glb(cls.glb)
        spec = {"schema": tp.SPEC_SCHEMA, "source_id": "tripo-t1", "asset_id": "ASSET-TEST-001",
                "service": "tripo-studio", "task_id": "local-test-no-tripo", "generation": None,
                "operations": [{"op": "generate"}],
                "files": [{"role": "glb", "path": "tripo-source/t1/model.glb", "expected_sha256": sha(cls.glb)}],
                "expectations": {"glb": {"glb_mesh_count": info["mesh_count"], "glb_triangles": info["triangles"]}}}
        cls.spec = cls.tmp / "spec.json"
        cls.spec.write_text(json.dumps(spec), encoding="utf-8")
        cls.run_dir = cls.repo / "art/pipeline-candidates/ASSET-TEST-001/run1"
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith("TRIPO_PIPELINE_")}
        cls.cli("init", "--run-dir", str(cls.run_dir), "--asset-id", "ASSET-TEST-001",
                "--primary-source", "tripo-t1", "--primary-role", "glb")
        cls.cli("register-source", "--run-dir", str(cls.run_dir), "--spec", str(cls.spec))
        cls.first = cls.cli("run", "--run-dir", str(cls.run_dir))
        cls.snap1 = tp.snapshot(cls.run_dir)
        cls.second = cls.cli("run", "--run-dir", str(cls.run_dir))
        cls.snap2 = tp.snapshot(cls.run_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def cli(cls, *args):
        proc = subprocess.run([sys.executable, str(TOOL), "--repo-root", str(cls.repo), *args], capture_output=True,
                              text=True, env=cls.env, timeout=900)
        if proc.returncode != 0:
            raise AssertionError("pipeline %s failed:\n%s\n%s" % (args, proc.stdout, proc.stderr))
        return proc.stdout

    def live(self, name, collide):
        out = self.tmp / name
        out.mkdir()
        stages = []
        for stage, params in (
                ("import", {"source": str(self.glb), "blend_out": str(out / "work.blend"),
                            "report_out": str(out / "import-report.json")}),
                ("export", {"blend": str(out / "work.blend"), "fbx_out": str(out / "ASSET-TEST-001_glb.fbx"),
                            "report_out": str(out / "export-report.json"), "fbx_preset": str(self.preset)})):
            path = out / ("%s-params.json" % stage)
            path.write_text(json.dumps(params), encoding="utf-8")
            stages.append({"stage": stage, "script": str(tp.BLENDER_SCRIPTS[stage]), "params": str(path)})
        job = out / "job.json"
        job.write_text(json.dumps({"mode": "live", "result": str(out / "result.json"), "collide": collide,
                                   "stages": stages}), encoding="utf-8")
        blender(job)
        return out, json.loads((out / "result.json").read_text(encoding="utf-8"))

    def test_headless_second_run_rewrites_nothing(self):
        self.assertIn("import    executed", self.first)
        self.assertIn("export    executed", self.first)
        self.assertIn("import    skipped", self.second)
        self.assertIn("export    skipped", self.second)
        self.assertEqual(self.snap1, self.snap2)
        m = json.loads((self.run_dir / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(len(m["exports"]), 1)
        report = json.loads((self.run_dir / "reports/export-report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["passed"], report["checks"])

    def test_export_follows_um_fbx_v1(self):
        """Passthrough FBX: rotated +90 deg about Z (front -Y -> +X), triangulated, cm numbers, USF 1.0."""
        report = json.loads((self.run_dir / "reports/export-report.json").read_text(encoding="utf-8"))
        settings = report["fbx"]["settings"]
        self.assertEqual(settings["preset"]["name"], "UM_FBX_v1")
        self.assertEqual(settings["export_space_rotation_z_degrees"], 90.0)
        self.assertTrue(settings["use_triangles"])
        self.assertTrue(report["checks"]["export_frame_rotated_as_preset"])
        before = report["scene_before_export"]["bounds_dimensions"]
        raw = report["roundtrip_export_frame"]["bounds_dimensions"]
        self.assertGreater(abs(before[0] - before[1]), 0.1, "test GLB must have a non-square footprint")
        self.assertAlmostEqual(raw[0], before[1], places=4)
        self.assertAlmostEqual(raw[1], before[0], places=4)
        self.assertEqual(report["roundtrip_reimport"]["bounds_dimensions"], before, "authored frame after undo")
        self.assertEqual(report["expected_ue_dimensions_uu_at_import_scale_1"],
                         [round(v * 100, 6) for v in raw])

    def test_live_mode_leaves_session_untouched_and_matches_headless_bytes(self):
        out, result = self.live("live-clean", collide=False)
        for run in result["runs"]:
            self.assertIsNone(run["error"], run["error"])
            self.assertIn("isolation=live", run["stdout"])
        before, after = dict(result["before"]), dict(result["after"])
        before.pop("_is_dirty"), after.pop("_is_dirty")
        self.assertEqual(after, before, "live stage scripts changed the user's session")
        self.assertEqual(sha(out / "ASSET-TEST-001_glb.fbx"), sha(self.run_dir / "export/ASSET-TEST-001_glb.fbx"),
                         "live FBX must be byte-identical to the headless FBX")
        self.assertEqual((out / "import-report.json").read_bytes(),
                         (self.run_dir / "reports/import-report.json").read_bytes())

    def test_live_mode_with_name_collision_reports_canonical_names(self):
        out, result = self.live("live-collide", collide=True)
        for run in result["runs"]:
            self.assertIsNone(run["error"], run["error"])
        before, after = dict(result["before"]), dict(result["after"])
        before.pop("_is_dirty"), after.pop("_is_dirty")
        self.assertEqual(after, before)
        live_report = json.loads((out / "import-report.json").read_text(encoding="utf-8"))
        headless_report = json.loads((self.run_dir / "reports/import-report.json").read_text(encoding="utf-8"))
        self.assertEqual(live_report.pop("live_name_collisions"),
                         {"materials": ["MatA.001"], "objects": ["part_body.001"]})
        self.assertEqual(live_report, headless_report)
        export_report = json.loads((out / "export-report.json").read_text(encoding="utf-8"))
        self.assertTrue(export_report["passed"])
        self.assertEqual(export_report["live_name_collisions"],
                         {"materials": ["MatA.001"], "objects": ["part_body.001"]})


if __name__ == "__main__":
    unittest.main()
