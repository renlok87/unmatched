"""Unit tests for the --backend mcp path: live Blender stages and the UE import stage.

Blender and UnrealEditor are replaced by tests/fake_blender.py --mcp and
tests/fake_unreal_mcp.py (same CLI/JSON contract as the real clients in
C:/Users/ren/.claude/mcp-servers/clients). No live application is touched.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import json
import sys
import unittest

from test_pipeline import FAKE, TESTS, PipelineTestBase, tp

FAKE_UE = TESTS / "fake_unreal_mcp.py"


class McpBackendTestBase(PipelineTestBase):
    def setUp(self):
        super().setUp()
        self.ue_state = self.tmp / "ue-state.json"
        self.ue_log = self.tmp / "ue-calls.log"
        self.env.update(TRIPO_PIPELINE_BLENDER_MCP_CMD=json.dumps([sys.executable, str(FAKE), "--mcp"]),
                        TRIPO_PIPELINE_UNREAL_MCP_CMD=json.dumps([sys.executable, str(FAKE_UE)]),
                        FAKE_UE_STATE=str(self.ue_state), FAKE_UE_LOG=str(self.ue_log))
        for key in ("FAKE_UE_QUALIFIED", "FAKE_UE_TRIS_DELTA", "FAKE_UE_FAIL_TOOL", "FAKE_BLENDER_MCP_DOWN",
                    "TRIPO_PIPELINE_BACKEND"):
            self.env.pop(key, None)

    def mcp(self, *args, expect=0, env=None):
        return self.cli("--backend", "mcp", *args, expect=expect, env=env)

    def ue_assets(self):
        return json.loads(self.ue_state.read_text(encoding="utf-8"))["assets"] if self.ue_state.exists() else {}

    def ue_calls(self):
        return self.ue_log.read_text(encoding="utf-8").split() if self.ue_log.exists() else []


class McpBlenderBackendTests(McpBackendTestBase):
    def test_stages_run_in_live_blender_and_second_run_is_noop(self):
        self.init_and_register()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.assertEqual(self.blender_calls(), ["mcp:import", "mcp:export"])
        self.assertIn("isolation=live", (self.run_dir / "logs/import.log").read_text(encoding="utf-8"))
        first = tp.snapshot(self.run_dir)
        out = self.mcp("run", "--run-dir", str(self.run_dir))
        self.assertIn("export    skipped", out.stdout)
        self.assertEqual(tp.snapshot(self.run_dir), first)
        self.assertEqual(self.blender_calls(), ["mcp:import", "mcp:export"])
        preflight = json.loads((self.run_dir / "reports/preflight.json").read_text(encoding="utf-8"))
        self.assertEqual(preflight["backend"], "mcp")
        self.assertEqual(preflight["checks"]["blender_runnable"]["measured"], "9.9.9 LTS")

    def test_switching_backend_reexecutes_blender_stages_but_dedupes_identical_fbx(self):
        self.init_and_register()
        self.cli("run", "--run-dir", str(self.run_dir))
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.assertEqual(self.blender_calls(), ["import", "export", "mcp:import", "mcp:export"])
        self.assertEqual(len(self.manifest()["exports"]), 1,
                         "identical FBX bytes from the other backend must not create a second export entry")
        done = [e for e in self.journal() if e["event"] == "stage_completed" and e["stage"] == "export"]
        self.assertEqual(done[-1]["outputs"]["export/ASSET-TEST-001_glb.fbx"], "unchanged")

    def test_unreachable_live_blender_fails_preflight_without_side_effects(self):
        self.init_and_register()
        env = dict(self.env, FAKE_BLENDER_MCP_DOWN="1")
        proc = self.mcp("run", "--run-dir", str(self.run_dir), expect=1, env=env)
        self.assertIn("blender_runnable", proc.stderr)
        self.assertEqual(self.blender_calls(), [])
        self.assertFalse((self.run_dir / "work").exists())

    def test_live_stage_error_is_reported_and_resumable(self):
        self.init_and_register()
        env = dict(self.env, FAKE_BLENDER_FAIL="export")
        proc = self.mcp("run", "--run-dir", str(self.run_dir), expect=1, env=env)
        self.assertIn("mcp backend", proc.stderr)
        self.assertTrue((self.run_dir / "logs/export.failed.log").exists())
        self.mcp("resume", "--run-dir", str(self.run_dir))
        self.assertEqual(self.blender_calls(), ["mcp:import", "mcp:export", "mcp:export"])
        self.assertEqual(len(self.manifest()["exports"]), 1)


class UeImportTests(McpBackendTestBase):
    FOLDER = "/Game/PipelineCandidates/Test/run1"
    MESH = FOLDER + "/SM_ASSET_TEST_001_glb"
    ALL = [FOLDER + "/M_0", FOLDER + "/M_1", MESH]

    def prepared(self):
        self.init_and_register()
        self.mcp("run", "--run-dir", str(self.run_dir))

    def ue_import(self, *extra, expect=0, env=None):
        return self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER, *extra,
                        expect=expect, env=env)

    def report(self):
        return json.loads((self.run_dir / "reports/ue-import-report.json").read_text(encoding="utf-8"))

    def test_headless_backend_refuses_ue_stage_without_touching_manifest(self):
        self.prepared()
        before = (self.run_dir / "manifest.json").read_bytes()
        proc = self.cli("ue-import", "--run-dir", str(self.run_dir), expect=tp.EXIT_USAGE)
        self.assertIn("--backend mcp", proc.stderr)
        self.assertEqual((self.run_dir / "manifest.json").read_bytes(), before)
        self.assertEqual(self.ue_calls(), [])

    def test_folder_outside_pipeline_candidates_is_refused(self):
        self.prepared()
        for folder in ("/Game/ART004/Medusa", "/Game/ArtPreview/Medusa", "/Game/PipelineCandidates/../ART004"):
            self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", folder, expect=tp.EXIT_USAGE)
        self.assertNotIn("ue", self.manifest()["config"])
        self.assertEqual(self.ue_calls(), [])

    def test_import_twice_creates_no_duplicates(self):
        self.prepared()
        self.ue_import()
        assets = self.ue_assets()
        self.assertEqual(sorted(assets), self.ALL)
        report = self.report()
        self.assertEqual(report["status"], "technically_imported")
        self.assertTrue(report["checks"]["dimensions_match_blender_at_import_scale_1"]["passed"])
        self.assertTrue(report["checks"]["folder_contains_only_this_import"]["passed"])
        calls = len(self.ue_calls())
        first = tp.snapshot(self.run_dir)
        out = self.ue_import()
        self.assertIn("skipped", out.stdout)
        self.assertEqual(self.ue_assets(), assets)
        self.assertNotIn("import_file", self.ue_calls()[calls:], "no-op run must not import again")
        self.assertEqual(tp.snapshot(self.run_dir), first)

    def test_forced_reimport_replaces_instead_of_numbering(self):
        self.prepared()
        self.ue_import()
        self.ue_import("--force")
        self.assertEqual(sorted(self.ue_assets()), self.ALL)
        self.assertEqual(self.ue_calls().count("delete"), 3)
        self.assertEqual(self.ue_calls().count("import_file"), 2)
        self.assertEqual(sorted(self.report()["previous_assets_deleted"]), self.ALL)

    def test_foreign_assets_in_folder_block_import(self):
        self.prepared()
        self.ue_state.write_text(json.dumps({"assets": {self.FOLDER + "/SomeoneElse": {"class": "StaticMesh"}}}),
                                 encoding="utf-8")
        proc = self.ue_import(expect=tp.EXIT_CONFLICT)
        self.assertIn("did not create", proc.stderr)
        self.assertEqual(list(self.ue_assets()), [self.FOLDER + "/SomeoneElse"])
        self.assertNotIn("delete", self.ue_calls())
        self.assertNotIn("import_file", self.ue_calls())

    def test_interrupted_ue_import_resumes_without_duplicates(self):
        self.prepared()
        self.ue_import("--interrupt-at", "ue-import", expect=tp.EXIT_INTERRUPTED)
        m = self.manifest()
        self.assertEqual(m["stages"]["ue-import"]["status"], "running")
        self.assertEqual(sorted(m["stages"]["ue-import"]["ue_owned_assets"]), self.ALL)
        self.ue_import(expect=tp.EXIT_NEEDS_RESUME)
        out = self.mcp("resume", "--run-dir", str(self.run_dir))
        self.assertIn("first unfinished stage = ue-import", out.stdout)
        self.assertEqual(sorted(self.ue_assets()), self.ALL)
        m = self.manifest()
        self.assertEqual(m["stages"]["ue-import"]["status"], "completed")
        self.assertEqual(len(m["stages"]["ue-import"]["interruptions"]), 1)
        self.assertEqual(self.ue_calls().count("import_file"), 2)
        self.assertEqual(self.blender_calls(), ["mcp:import", "mcp:export"], "Blender stages must not rerun")

    def test_asset_deleted_in_editor_is_reimported(self):
        self.prepared()
        self.ue_import()
        state = json.loads(self.ue_state.read_text(encoding="utf-8"))
        del state["assets"][self.MESH]
        self.ue_state.write_text(json.dumps(state), encoding="utf-8")
        out = self.ue_import()
        self.assertIn("executed", out.stdout)
        self.assertEqual(sorted(self.ue_assets()), self.ALL)

    def test_contract_failure_then_clean_retry(self):
        self.prepared()
        proc = self.ue_import(expect=1, env=dict(self.env, FAKE_UE_TRIS_DELTA="50"))
        self.assertIn("triangles_equal_blender_roundtrip", proc.stderr)
        self.assertEqual(self.manifest()["stages"]["ue-import"]["status"], "failed")
        self.assertEqual(self.report()["status"], "failed")
        self.ue_import()
        self.assertEqual(sorted(self.ue_assets()), self.ALL)
        self.assertEqual(self.report()["status"], "technically_imported")

    def test_qualified_tool_names_are_detected(self):
        self.prepared()
        self.ue_import(env=dict(self.env, FAKE_UE_QUALIFIED="1"))
        self.assertEqual(self.report()["tool_name_style"], "qualified")

    def test_changed_target_is_a_conflict(self):
        self.prepared()
        self.ue_import()
        self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER + "_other",
                 expect=tp.EXIT_CONFLICT)

    def test_run_includes_ue_stage_only_for_mcp(self):
        self.prepared()
        self.ue_import()
        out = self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("not-run (needs --backend mcp)", out.stdout)
        out = self.mcp("run", "--run-dir", str(self.run_dir))
        self.assertIn("ue-import skipped", out.stdout)


if __name__ == "__main__":
    unittest.main()
