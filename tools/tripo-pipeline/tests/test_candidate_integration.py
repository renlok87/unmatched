"""Integration: the real skeletal candidates (Medusa and the heroes) with the real Blender 5.2 (headless only).

1. `--backend headless` runs preflight -> import -> verify -> atlas -> build on the paid
   Tripo source that is already in the repository (read only), into a temporary run dir
   outside the repository; the second run changes no file.
2. The build stage script runs in "live" isolation inside a Blender session with user
   data, exactly like blender-mcp's execute_code (tests/blender_live_harness.py): the
   session is left unchanged and the FBX bytes equal the headless ones.
3. If the committed T4 run exists, its FBX hashes are reproduced.
4. Heroes (tool 0.5.0, flow seated-parts): King Arthur, Merlin and Harpy are built end to end by the CLI
   (no per-hero script) into temporary run dirs: build completed in the manifest, FBX and atlas bytes equal
   the committed candidates of the 2026-09-28 per-hero builders, the second run is a no-op, and ue-import
   (tests/fake_unreal_mcp.py fed by the real build report) accepts the run (height by profile, Head socket
   from the build's UE bone-space prediction).

Nothing is written into the repository. Skipped when Blender or the sources are missing
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
                  "base_fbx_out": str(out / "SM_Medusa_Base_Candidate.fbx"), "report_out": str(out / "build-report.json"),
                  "lib_dir": str(tp.BLENDER_SCRIPTS["build"].parent)}
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


FAKE_UE = Path(__file__).resolve().parent / "fake_unreal_mcp.py"
HEROES = {
    # asset: (committed run, build profile, primary source, source specs)
    "ASSET-KING-ARTHUR-001": ("20260928-blender-um-fbx-v1", "king-arthur-segmented-skeletal-um-fbx-v1-cli.json",
                              "tripo-75e27ee8", ("tripo-5cb29330.json", "tripo-75e27ee8.json")),
    "ASSET-MERLIN-001": ("20260928-blender-um-fbx-v1", "merlin-segmented-skeletal-um-fbx-v1-cli.json",
                         "tripo-d9ff4260", ("tripo-22cb43f2.json", "tripo-d9ff4260.json")),
    "ASSET-HARPY-001": ("20260928-blender-um-fbx-v1", "harpy-segmented-skeletal-um-fbx-v1-cli.json",
                        "tripo-d500fc84", ("tripo-c756522c.json", "tripo-d500fc84.json")),
}


def hero_sources_present(asset):
    base = REPO / "art/pipeline-candidates" / asset
    try:
        for spec in HEROES[asset][3]:
            data = json.loads((base / "source-specs" / spec).read_text(encoding="utf-8"))
            if not all((REPO / f["path"]).is_file() for f in data["files"]):
                return False
    except (OSError, ValueError, KeyError):
        return False
    return (base / HEROES[asset][0] / "manifest.json").is_file()


class RealHeroCandidateBase:
    """The CLI builds a hero end to end (flow seated-parts, no per-hero script) into a temporary run dir: build is
    completed in the manifest, the FBX and atlas bytes equal the committed candidate of the per-hero builder, the
    second run is a no-op, and ue-import (fake UnrealEditor fed by the real build report) accepts the run.
    A mixin (not a TestCase itself): the concrete classes below set ASSET."""

    ASSET = None

    @classmethod
    def setUpClass(cls):
        committed, profile, primary, specs = HEROES[cls.ASSET]
        cls.base = REPO / "art/pipeline-candidates" / cls.ASSET
        cls.committed = cls.base / committed
        cls.profile_rel = "art/pipeline-candidates/%s/build-profiles/%s" % (cls.ASSET, profile)
        cls.tmp = Path(tempfile.mkdtemp(prefix="tripo-pipeline-%s-" % cls.ASSET.lower()))
        cls.run_dir = cls.tmp / "run"
        cls.env = {k: v for k, v in os.environ.items() if not k.startswith("TRIPO_PIPELINE_") and not k.startswith("FAKE_")}
        cls.env["TRIPO_PIPELINE_BLENDER"] = BLENDER
        cls.cli("init", "--run-dir", str(cls.run_dir), "--asset-id", cls.ASSET, "--primary-source", primary,
                "--primary-role", "segmented-retopo-glb", "--profile", "skeletal-candidate", "--build-profile", cls.profile_rel)
        for spec in specs:
            cls.cli("register-source", "--run-dir", str(cls.run_dir), "--spec", str(cls.base / "source-specs" / spec))
        cls.first = cls.cli("run", "--run-dir", str(cls.run_dir))
        cls.snap1 = tp.snapshot(cls.run_dir)
        cls.second = cls.cli("run", "--run-dir", str(cls.run_dir))
        cls.snap2 = tp.snapshot(cls.run_dir)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def cli(cls, *args, env=None):
        proc = subprocess.run([sys.executable, str(TOOL), "--repo-root", str(REPO), *args], capture_output=True,
                              text=True, env=env or cls.env, timeout=1800)
        if proc.returncode != 0:
            raise AssertionError("pipeline %s failed:\n%s\n%s" % (args, proc.stdout, proc.stderr))
        return proc.stdout

    def manifest(self):
        return json.loads((self.run_dir / "manifest.json").read_text(encoding="utf-8"))

    def test_build_completed_through_the_cli_and_second_run_is_noop(self):
        self.assertIn("build     executed", self.first)
        self.assertIn("build     skipped", self.second)
        self.assertEqual(self.snap1, self.snap2)
        m = self.manifest()
        for stage in ("preflight", "import", "verify", "atlas", "build"):
            self.assertEqual(m["stages"][stage]["status"], "completed", stage)
        report = json.loads((self.run_dir / "reports/build-report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["passed"], [k for k, c in report["checks"].items() if not c["passed"]])
        self.assertEqual(report["flow"], "seated-parts")
        self.assertEqual(report["builder"]["script"], "tools/tripo-pipeline/blender/build_candidate.py")
        self.assertEqual(report["anatomy"]["disagreements"], {}, "profile anatomy = detected anatomy")

    def test_fbx_and_atlas_bytes_equal_the_committed_candidate(self):
        for rel in sorted(self.manifest()["stages"]["build"]["outputs"]):
            if rel.startswith("export/"):
                self.assertEqual(sha(self.run_dir / rel), sha(self.committed / rel), rel)
        for rel in sorted(self.manifest()["stages"]["atlas"]["outputs"]):
            if rel.startswith("textures/"):
                self.assertEqual(sha(self.run_dir / rel), sha(self.committed / rel), rel)

    def test_ue_import_accepts_the_run(self):
        state = self.tmp / "ue-state.json"
        env = dict(self.env, TRIPO_PIPELINE_UNREAL_MCP_CMD=json.dumps([sys.executable, str(FAKE_UE)]),
                   FAKE_UE_STATE=str(state), FAKE_UE_ARMATURE_NODE="SKEL_UM_Humanoid")
        folder = "/Game/PipelineCandidates/Test/%s" % self.ASSET.replace("-", "_")
        self.cli("--backend", "mcp", "ue-import", "--run-dir", str(self.run_dir), "--ue-folder", folder, env=env)
        ue = json.loads((self.run_dir / "reports/ue-import-report.json").read_text(encoding="utf-8"))
        failed = {k: c for k, c in ue["checks"].items() if not c["passed"]}
        self.assertEqual(ue["status"], "technically_imported", json.dumps(failed, indent=1)[:3000])
        build = json.loads((self.run_dir / "reports/build-report.json").read_text(encoding="utf-8"))
        self.assertAlmostEqual(ue["measured"]["height"]["build_figure_top_uu"],
                               json.loads((REPO / self.profile_rel).read_text(encoding="utf-8"))["scale"]["figure_height_m"] * 100)
        self.assertAlmostEqual(ue["measured"]["height"]["build_skeletal_top_uu"], build["figure"]["skeletal_top_m"] * 100,
                               places=2)
        head = next(s for s in ue["measured"]["sockets_plan"] if s["name"] == "Head")
        self.assertEqual(head["source"], "build prediction")


@unittest.skipIf(SKIP or not hero_sources_present("ASSET-KING-ARTHUR-001"), "Blender or King Arthur sources missing")
class RealKingArthurCandidateTests(RealHeroCandidateBase, unittest.TestCase):
    ASSET = "ASSET-KING-ARTHUR-001"


@unittest.skipIf(SKIP or not hero_sources_present("ASSET-MERLIN-001"), "Blender or Merlin sources missing")
class RealMerlinCandidateTests(RealHeroCandidateBase, unittest.TestCase):
    ASSET = "ASSET-MERLIN-001"

    def test_live_seated_build_leaves_session_untouched_and_matches_headless_bytes(self):
        """The seated flow in "live" isolation (blender-mcp execute_code, tests/blender_live_harness.py)."""
        m = self.manifest()
        cfg = m["config"]
        primary = next(f for f in m["sources"][cfg["primary_source"]]["files"] if f["role"] == cfg["primary_role"])
        profile = json.loads((REPO / self.profile_rel).read_text(encoding="utf-8"))
        out = self.tmp / "live"
        out.mkdir()
        params = {"source": str(REPO / primary["path"]), "profile": str(REPO / self.profile_rel),
                  "fbx_preset": str(REPO / tp.DEFAULT_FBX_PRESET),
                  "atlas_report": str(self.run_dir / "reports/atlas-report.json"),
                  "textures_dir": str(self.run_dir / "textures"), "repo_root": str(REPO),
                  "blend_out": str(out / "work.blend"), "sk_fbx_out": str(out / profile["exports"]["skeletal_fbx"]),
                  "base_fbx_out": str(out / profile["exports"]["base_fbx"]), "report_out": str(out / "build-report.json"),
                  "lib_dir": str(tp.BLENDER_SCRIPTS["build"].parent)}
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
        for name in (profile["exports"]["skeletal_fbx"], profile["exports"]["base_fbx"]):
            self.assertEqual(sha(out / name), sha(self.run_dir / "export" / name), name)


@unittest.skipIf(SKIP or not hero_sources_present("ASSET-HARPY-001"), "Blender or Harpy sources missing")
class RealHarpyCandidateTests(RealHeroCandidateBase, unittest.TestCase):
    ASSET = "ASSET-HARPY-001"


if __name__ == "__main__":
    unittest.main()
