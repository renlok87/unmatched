"""Unit tests for tripo_pipeline: idempotency, hash dedupe, interrupt + resume.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
Blender is replaced by tests/fake_blender.py; no network and no real Tripo files.
"""

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
TOOL = TESTS.parent / "tripo_pipeline.py"
FAKE = TESTS / "fake_blender.py"
REAL_PRESET = TOOL.parents[2] / "blender/_tools/presets/UM_FBX_v1.json"
sys.path.insert(0, str(TESTS.parent))
import tripo_pipeline as tp  # noqa: E402


def make_glb(path: Path, meshes, materials=2, images=3):
    accessors, gltf_meshes = [], []
    for name, tris in meshes:
        accessors.append({"count": tris * 3, "componentType": 5125, "type": "SCALAR"})
        accessors.append({"count": tris * 3, "componentType": 5126, "type": "VEC3"})
        gltf_meshes.append({"name": name, "primitives": [{"indices": len(accessors) - 2,
                                                          "attributes": {"POSITION": len(accessors) - 1}}]})
    doc = {"asset": {"version": "2.0", "generator": "Tripo"}, "meshes": gltf_meshes, "accessors": accessors,
           "materials": [{} for _ in range(materials)], "images": [{} for _ in range(images)]}
    body = json.dumps(doc).encode("utf-8")
    body += b" " * (-len(body) % 4)
    data = struct.pack("<4sII", b"glTF", 2, 12 + 8 + len(body)) + struct.pack("<I4s", len(body), b"JSON") + body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install_preset(repo: Path) -> Path:
    """Every FBX of the tool follows UM_FBX_v1; test repos carry a copy of the real preset."""
    target = repo / tp.DEFAULT_FBX_PRESET
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(REAL_PRESET, target)
    return target


class PipelineTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="tripo-pipeline-test-"))
        self.repo = self.tmp / "repo"
        (self.repo / ".git").mkdir(parents=True)
        self.preset = install_preset(self.repo)
        self.glb = self.repo / "tripo-source/t1/model.glb"
        make_glb(self.glb, [("part_a", 10), ("part_b", 5)])
        self.png = self.repo / "inputs/front.png"
        self.png.parent.mkdir(parents=True)
        self.png.write_bytes(b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
                             + struct.pack(">IIBBBBB", 1024, 1024, 8, 2, 0, 0, 0) + b"\0" * 4)
        self.png2 = self.repo / "inputs/back.png"
        shutil.copyfile(self.png, self.png2)
        with open(self.png2, "ab") as handle:
            handle.write(b"x")
        self.spec = {
            "schema": tp.SPEC_SCHEMA, "source_id": "tripo-t1", "asset_id": "ASSET-TEST-001",
            "service": "tripo-studio", "task_id": "t1-task",
            "model_version": {"ui_label": "H3.1"},
            "generation": {"mode": "multi-view", "views": {
                "front": {"path": "inputs/front.png", "sha256": sha(self.png)},
                "back": {"path": "inputs/back.png", "sha256": sha(self.png2)}, "right": None}},
            "operations": [{"op": "generate", "credits": {"unit": "studio-credits", "observed_debit": 55}},
                           {"op": "retopology", "credits": {"unit": "studio-credits", "observed_debit": 40}}],
            "files": [{"role": "glb", "path": "tripo-source/t1/model.glb", "expected_sha256": sha(self.glb)}],
            "expectations": {"glb": {"glb_mesh_count": 2, "glb_triangles": 15, "glb_materials": 2}},
        }
        self.spec_path = self.tmp / "spec.json"
        self.write_spec()
        self.run_dir = self.repo / "art/pipeline-candidates/ASSET-TEST-001/run1"
        self.calls = self.tmp / "blender-calls.log"
        self.env = dict(os.environ, TRIPO_PIPELINE_BLENDER_CMD=json.dumps([sys.executable, str(FAKE)]),
                        FAKE_BLENDER_LOG=str(self.calls))
        self.env.pop("FAKE_BLENDER_FAIL", None)
        self.env.pop("FAKE_BLENDER_SLEEP", None)
        self.source_state = (sha(self.glb), self.glb.stat().st_mtime_ns)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_spec(self):
        self.spec_path.write_text(json.dumps(self.spec), encoding="utf-8")

    def cli(self, *args, expect=0, env=None):
        cmd = [sys.executable, str(TOOL), "--repo-root", str(self.repo)] + list(args)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=env or self.env, timeout=120)
        if expect is not None:
            self.assertEqual(proc.returncode, expect, "cmd %s\nstdout:%s\nstderr:%s" % (args, proc.stdout, proc.stderr))
        return proc

    def init_and_register(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001",
                 "--primary-source", "tripo-t1", "--primary-role", "glb")
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))

    def manifest(self):
        return json.loads((self.run_dir / "manifest.json").read_text(encoding="utf-8"))

    def journal(self):
        return [json.loads(line) for line in (self.run_dir / "journal.jsonl").read_text(encoding="utf-8").splitlines()]

    def blender_calls(self):
        return self.calls.read_text(encoding="utf-8").split() if self.calls.exists() else []

    def assertSourceUntouched(self):
        self.assertEqual((sha(self.glb), self.glb.stat().st_mtime_ns), self.source_state)


class RegisterSourceTests(PipelineTestBase):
    def test_register_twice_is_noop(self):
        self.init_and_register()
        before = (self.run_dir / "manifest.json").read_bytes()
        out = self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))
        self.assertIn("already registered", out.stdout)
        self.assertEqual((self.run_dir / "manifest.json").read_bytes(), before)
        self.assertEqual(list(self.manifest()["sources"]), ["tripo-t1"])
        self.assertEqual(self.manifest()["sources"]["tripo-t1"]["historical_credits_observed"], {"studio-credits": 95})

    def test_changed_spec_conflicts_and_keeps_manifest(self):
        self.init_and_register()
        before = (self.run_dir / "manifest.json").read_bytes()
        self.spec["operations"][0]["credits"]["observed_debit"] = 56
        self.write_spec()
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path), expect=tp.EXIT_CONFLICT)
        self.assertEqual((self.run_dir / "manifest.json").read_bytes(), before)

    def test_hash_mismatch_against_evidence_is_rejected(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001",
                 "--primary-source", "tripo-t1", "--primary-role", "glb")
        self.spec["files"][0]["expected_sha256"] = "0" * 64
        self.write_spec()
        proc = self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path), expect=1)
        self.assertIn("hash mismatch", proc.stderr)

    def test_studio_and_api_credits_are_not_mixed(self):
        self.spec["operations"][0]["credits"]["unit"] = "api-credits"
        with self.assertRaises(tp.PipelineError):
            tp.validate_spec(self.spec)

    def test_batch_is_not_a_single_source(self):
        self.spec["generation"]["mode"] = "batch"
        with self.assertRaises(tp.PipelineError):
            tp.validate_spec(self.spec)

    def test_multiview_needs_two_views(self):
        self.spec["generation"]["views"] = {"front": self.spec["generation"]["views"]["front"]}
        with self.assertRaises(tp.PipelineError):
            tp.validate_spec(self.spec)

    def test_originals_inside_run_dir_are_rejected(self):
        inside = self.run_dir / "copy.glb"
        inside.parent.mkdir(parents=True)
        shutil.copyfile(self.glb, inside)
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001",
                 "--primary-source", "tripo-t1", "--primary-role", "glb")
        self.spec["files"][0]["path"] = "art/pipeline-candidates/ASSET-TEST-001/run1/copy.glb"
        self.write_spec()
        proc = self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path), expect=1)
        self.assertIn("outside the run directory", proc.stderr)


class IdempotencyTests(PipelineTestBase):
    def test_second_run_changes_nothing(self):
        self.init_and_register()
        self.cli("run", "--run-dir", str(self.run_dir))
        self.assertEqual(self.blender_calls(), ["import", "export"])
        first = tp.snapshot(self.run_dir)
        out = self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("import    skipped", out.stdout)
        self.assertIn("export    skipped", out.stdout)
        self.assertIn("preflight revalidated", out.stdout)
        self.assertEqual(tp.snapshot(self.run_dir), first, "any file rewritten on a no-op run")
        self.assertEqual(self.blender_calls(), ["import", "export"], "Blender re-invoked on a no-op run")
        m = self.manifest()
        self.assertEqual(len(m["exports"]), 1)
        self.assertEqual(m["network"], {"tripo_calls": 0, "paid_tasks_created": 0,
                                        "policy": m["network"]["policy"]})
        self.assertSourceUntouched()
        self.assertFalse((self.run_dir / "run.lock").exists())
        self.assertFalse((self.run_dir / ".staging").exists())

    def test_forced_export_with_identical_bytes_is_not_duplicated(self):
        self.init_and_register()
        self.cli("run", "--run-dir", str(self.run_dir))
        fbx = self.run_dir / "export/ASSET-TEST-001_glb.fbx"
        mtime = fbx.stat().st_mtime_ns
        time.sleep(0.05)
        self.cli("export", "--run-dir", str(self.run_dir), "--force")
        self.assertEqual(self.blender_calls(), ["import", "export", "export"])
        self.assertEqual(fbx.stat().st_mtime_ns, mtime, "identical export was rewritten")
        self.assertEqual(len(self.manifest()["exports"]), 1)
        done = [e for e in self.journal() if e["event"] == "stage_completed" and e["stage"] == "export"]
        self.assertEqual(done[-1]["outputs"]["export/ASSET-TEST-001_glb.fbx"], "unchanged")
        self.assertEqual(done[-1]["exports_added"], [])

    def test_lost_work_file_reruns_import_but_export_dedupes(self):
        self.init_and_register()
        self.cli("run", "--run-dir", str(self.run_dir))
        (self.run_dir / "work/ASSET-TEST-001_glb.blend").unlink()
        self.cli("run", "--run-dir", str(self.run_dir))
        # .blend bytes differ (nonce) so export re-executes, but its FBX is identical.
        self.assertEqual(self.blender_calls(), ["import", "export", "import", "export"])
        self.assertEqual(len(self.manifest()["exports"]), 1)
        self.assertEqual(self.manifest()["stages"]["import"]["attempts"], 2)

    def test_changed_source_blocks_run(self):
        self.init_and_register()
        self.cli("run", "--run-dir", str(self.run_dir))
        make_glb(self.glb, [("part_a", 11)])
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("preflight failed", proc.stderr)
        self.assertEqual(self.blender_calls(), ["import", "export"])

    def test_verify_fails_on_evidence_mismatch(self):
        self.spec["expectations"]["glb"]["glb_triangles"] = 16
        self.write_spec()
        self.init_and_register()
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("evidence_glb_triangles", proc.stderr)
        self.assertEqual(self.manifest()["stages"]["verify"]["status"], "failed")
        self.assertNotIn("export", self.manifest()["stages"])


class ResumeTests(PipelineTestBase):
    def test_interrupt_then_resume_continues_from_unfinished_stage(self):
        self.init_and_register()
        self.cli("run", "--run-dir", str(self.run_dir), "--interrupt-at", "verify", expect=tp.EXIT_INTERRUPTED)
        m = self.manifest()
        self.assertEqual(m["stages"]["import"]["status"], "completed")
        self.assertEqual(m["stages"]["verify"]["status"], "running")
        self.assertTrue((self.run_dir / "run.lock").exists(), "a crash leaves the lock behind")
        self.assertEqual(self.blender_calls(), ["import"])
        # A plain run must refuse to paper over the interruption.
        self.cli("run", "--run-dir", str(self.run_dir), expect=tp.EXIT_NEEDS_RESUME)
        out = self.cli("resume", "--run-dir", str(self.run_dir))
        self.assertIn("first unfinished stage = verify", out.stdout)
        self.assertIn("import    skipped", out.stdout)
        self.assertIn("verify    executed", out.stdout)
        self.assertEqual(self.blender_calls(), ["import", "export"], "import must not be redone on resume")
        m = self.manifest()
        self.assertTrue(all(m["stages"][s]["status"] == "completed" for s in tp.STAGES))
        self.assertEqual(len(m["stages"]["verify"]["interruptions"]), 1)
        self.assertEqual(len(m["exports"]), 1)
        events = [e["event"] for e in self.journal()]
        self.assertIn("simulated_interrupt", events)
        self.assertIn("stale_lock_recovered", events)
        snap = tp.snapshot(self.run_dir)
        self.cli("run", "--run-dir", str(self.run_dir))
        self.assertEqual(tp.snapshot(self.run_dir), snap)
        self.assertSourceUntouched()

    def test_interrupt_during_export_does_not_duplicate(self):
        self.init_and_register()
        self.cli("run", "--run-dir", str(self.run_dir), "--interrupt-at", "export", expect=tp.EXIT_INTERRUPTED)
        self.assertFalse((self.run_dir / "export").exists(), "uncommitted export leaked out of staging")
        self.cli("resume", "--run-dir", str(self.run_dir))
        self.assertEqual(self.blender_calls(), ["import", "export", "export"])
        self.assertEqual(len(self.manifest()["exports"]), 1)
        self.assertFalse((self.run_dir / ".staging").exists())

    def test_killed_process_is_resumable(self):
        self.init_and_register()
        env = dict(self.env, FAKE_BLENDER_SLEEP="30")
        cmd = [sys.executable, str(TOOL), "--repo-root", str(self.repo), "run", "--run-dir", str(self.run_dir)]
        proc = subprocess.Popen(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 30
        while time.time() < deadline and self.blender_calls() != ["import"]:
            time.sleep(0.1)
        self.assertEqual(self.blender_calls(), ["import"])
        # Kill the whole tree we started (pipeline + fake Blender child), by our own PID only.
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        else:
            proc.kill()
        proc.wait(timeout=30)
        self.assertEqual(self.manifest()["stages"]["import"]["status"], "running")
        self.cli("run", "--run-dir", str(self.run_dir), expect=tp.EXIT_NEEDS_RESUME)
        self.cli("resume", "--run-dir", str(self.run_dir))
        m = self.manifest()
        self.assertTrue(all(m["stages"][s]["status"] == "completed" for s in tp.STAGES))
        self.assertEqual(m["stages"]["import"]["attempts"], 2)
        self.assertEqual(len(m["exports"]), 1)

    def test_live_lock_blocks_second_process(self):
        self.init_and_register()
        (self.run_dir / "run.lock").write_text(json.dumps({"pid": os.getpid(), "command": "test"}), encoding="utf-8")
        self.cli("run", "--run-dir", str(self.run_dir), expect=tp.EXIT_LOCKED)
        (self.run_dir / "run.lock").unlink()

    def test_failed_blender_stage_is_retried_by_resume(self):
        self.init_and_register()
        env = dict(self.env, FAKE_BLENDER_FAIL="import")
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1, env=env)
        self.assertIn("Blender stage import failed", proc.stderr)
        self.assertEqual(self.manifest()["stages"]["import"]["status"], "failed")
        self.assertTrue((self.run_dir / "logs/import.failed.log").exists())
        self.cli("resume", "--run-dir", str(self.run_dir))
        self.assertEqual(self.manifest()["stages"]["export"]["status"], "completed")


class GenerationRequestTests(PipelineTestBase):
    def views(self):
        return ["--view", "front=inputs/front.png", "--view", "back=inputs/back.png"]

    def test_submission_without_dry_run_is_refused(self):
        self.init_and_register()
        self.cli("prepare-generation", "--run-dir", str(self.run_dir), "--service", "tripo-studio",
                 "--mode", "multi-view", "--model-label", "H3.2", *self.views(), expect=tp.EXIT_USAGE)

    def prepare(self, label, *extra, expect=0, views=None):
        return self.cli("prepare-generation", "--run-dir", str(self.run_dir), "--dry-run", "--service", "tripo-studio",
                        "--mode", "multi-view", "--model-label", label, *(views or self.views()), *extra,
                        expect=expect)

    def test_duplicate_of_registered_task_is_refused(self):
        self.init_and_register()
        proc = self.prepare("H3.1", expect=tp.EXIT_CONFLICT)
        self.assertIn("t1-task", proc.stderr)
        self.assertFalse((self.run_dir / "generation-requests").exists())

    def test_duplicate_is_refused_whatever_the_model_label_says(self):
        """Same input hashes + mode + service = duplicate, even when the free-text label differs (vb, P0)."""
        self.init_and_register()
        for label in ("H3.1 - Макс.кач. Ожидание дольше", "h3.1", "H3.2", "anything"):
            proc = self.prepare(label, expect=tp.EXIT_CONFLICT)
            self.assertIn("t1-task", proc.stderr)
            self.assertIn("model label is not compared", proc.stderr)
        self.assertFalse((self.run_dir / "generation-requests").exists())
        self.assertEqual(self.manifest()["generation_requests"], [])
        refused = [e for e in self.journal() if e["event"] == "generation_request_refused_duplicate"]
        self.assertEqual(len(refused), 4)

    def test_other_inputs_or_mode_or_service_are_not_duplicates(self):
        self.init_and_register()
        other = self.repo / "inputs/front-v2.png"
        other.write_bytes(self.png.read_bytes() + b"v2")
        self.prepare("H3.1", views=["--view", "front=inputs/front-v2.png", "--view", "back=inputs/back.png"])
        self.cli("prepare-generation", "--run-dir", str(self.run_dir), "--dry-run", "--service", "tripo-api",
                 "--mode", "multi-view", "--model-label", "H3.1", *self.views())
        self.assertEqual(len(self.manifest()["generation_requests"]), 2)

    def test_allow_duplicate_needs_a_reason_and_records_it(self):
        self.init_and_register()
        proc = self.prepare("H3.2", "--allow-duplicate", expect=tp.EXIT_USAGE)
        self.assertIn("--duplicate-reason", proc.stderr)
        proc = self.prepare("H3.2", "--duplicate-reason", "why", expect=tp.EXIT_USAGE)
        self.assertIn("only used together with --allow-duplicate", proc.stderr)
        self.prepare("H3.2", "--allow-duplicate", "--duplicate-reason", "new model version test")
        m = self.manifest()
        request = json.loads((self.run_dir / m["generation_requests"][0]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(request["duplicate_allowed"], {"reason": "new model version test",
                                                        "duplicate_of": ["t1-task"]})

    def test_dry_run_package_is_idempotent(self):
        self.init_and_register()
        args = ("H3.2", "--allow-duplicate", "--duplicate-reason", "idempotency test")
        self.prepare(*args)
        first = tp.snapshot(self.run_dir)
        out = self.prepare(*args)
        self.assertIn("already exists", out.stdout)
        self.assertEqual(tp.snapshot(self.run_dir), first)
        m = self.manifest()
        self.assertEqual(len(m["generation_requests"]), 1)
        request = json.loads((self.run_dir / m["generation_requests"][0]["path"]).read_text(encoding="utf-8"))
        self.assertTrue(request["dry_run"])
        self.assertFalse(request["submitted"])
        self.assertEqual(request["paid_tasks_created"], 0)
        self.assertEqual(request["same_inputs_as_registered"][0]["same_model_label"], False)


class StaticSafetyTests(unittest.TestCase):
    def test_no_network_modules(self):
        source = TOOL.read_text(encoding="utf-8")
        for module in ("urllib", "http.client", "socket", "requests", "ssl"):
            self.assertNotRegex(source, r"(?m)^\s*(import|from)\s+%s\b" % module.replace(".", r"\."))

    def test_glb_inspector_counts_triangles(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a.glb"
            make_glb(path, [("a", 7), ("b", 3)], materials=1, images=0)
            info = tp.inspect_glb(path)
            self.assertEqual((info["mesh_count"], info["triangles"], info["materials"]), (2, 10, 1))


if __name__ == "__main__":
    unittest.main()
