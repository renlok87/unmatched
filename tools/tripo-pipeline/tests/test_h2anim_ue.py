"""Tests of anim/h2anim_ue.py without an editor (wave 2 of the 3d-model-pipeline skill rework, W2-b):
F145 preview mesh (carrier) currency and refresh, F96 default base, F136 camera from the figure height, F153 warm-up.

  python -m pytest tools/tripo-pipeline/tests/test_h2anim_ue.py -q
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "anim"))

import h2anim_ue as H  # noqa: E402


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="h2anim-ue-test-"))
        self.repo0 = H.REPO
        H.REPO = self.tmp

    def tearDown(self):
        H.REPO = self.repo0
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fbx(self, rel, data=b"fbx-v1"):
        p = self.tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p

    def spec(self, fbx_rel="bake/export/SK_Hero_H2.fbx", pin=True, ue_extra=None):
        f = self.tmp / fbx_rel
        spec = {"hero": "Hero", "ue_hero": "Hero", "run_dir": "run",
                "target": {"sk_fbx": fbx_rel, "sha256": sha(f) if pin else None},
                "ue": dict({"skeleton": "/Game/PipelineCandidates/Hero/Rig/SK_Hero_Skeleton",
                            "mesh_for_preview": "/Game/PipelineCandidates/Hero/Rig/SK_Hero",
                            "clips_folder": "/Game/PipelineCandidates/Hero/H2Anim"}, **(ue_extra or {})),
                "clips": {"Idle": {"frames": 4, "key_frames": [0, 2]}}}
        p = self.tmp / "spec.json"
        p.write_text(json.dumps(spec), encoding="utf-8")
        return p


class PreviewDecisionTest(TempRepo):
    def test_missing_mesh_needs_a_refresh(self):
        f = self.fbx("a/SK.fbx")
        d = H.preview_decision({"exists": False, "mesh": "/Game/x"}, f, sha(f))
        self.assertIs(d["current"], False)
        self.assertTrue(d["refresh"])

    def test_sha_stamp_decides(self):
        f = self.fbx("a/SK.fbx")
        st = {"exists": True, "sha_stamp": sha(f), "source_files": ["C:/elsewhere/SK.fbx"]}
        self.assertEqual((H.preview_decision(st, f, sha(f))["current"], H.preview_decision(st, f, sha(f))["refresh"]),
                         (True, False))
        d = H.preview_decision(dict(st, sha_stamp="0" * 64), f, sha(f))
        self.assertEqual((d["current"], d["refresh"]), (False, True))

    def test_same_path_without_stamp_is_assumed_current_and_forced_on_request(self):
        f = self.fbx("a/SK.fbx")
        st = {"exists": True, "sha_stamp": None, "source_files": [f.as_posix().upper()]}
        d = H.preview_decision(st, f, sha(f))
        self.assertIsNone(d["current"])
        self.assertFalse(d["refresh"])
        self.assertTrue(H.preview_decision(st, f, sha(f), force=True)["refresh"])

    def test_reworked_model_in_a_new_run_dir_is_detected_by_the_old_source_sha(self):
        old = self.fbx("bake-r2/SK.fbx", b"old geometry")
        new = self.fbx("bake-r3/SK.fbx", b"new geometry")
        st = {"exists": True, "source_files": [old.as_posix()]}
        d = H.preview_decision(st, new, sha(new))
        self.assertEqual((d["current"], d["refresh"]), (False, True))
        same = self.fbx("bake-copy/SK.fbx", b"new geometry")
        d2 = H.preview_decision({"exists": True, "source_files": [same.as_posix()]}, new, sha(new))
        self.assertEqual((d2["current"], d2["refresh"]), (True, False))

    def test_gone_source_cannot_be_proven(self):
        f = self.fbx("a/SK.fbx")
        d = H.preview_decision({"exists": True, "source_files": ["C:/tmp/wt-gone/SK.fbx"]}, f, sha(f))
        self.assertEqual((d["current"], d["refresh"]), (False, True))

    def test_spec_target_refuses_an_unpinned_change(self):
        self.fbx("bake/export/SK_Hero_H2.fbx")
        spec = H.load_spec(self.spec())
        (self.tmp / "bake/export/SK_Hero_H2.fbx").write_bytes(b"reworked")
        with self.assertRaises(SystemExit) as cm:
            H.spec_target(spec)
        self.assertIn("target.sha256", str(cm.exception))


class FakeUe:
    """run_task / py_file of ue_live.Ue for the skeleton command: a carrier with a recorded state."""

    def __init__(self, carrier_state):
        self.state = carrier_state
        self.tasks = []

    def py_file(self, script, out_json, timeout=600, args=""):
        return {"dirty_content": []}

    def run_task(self, script, out_json, timeout=600, **kw):
        name = Path(script).name
        self.tasks.append((name, kw))
        if name == "canonical_skeleton.py":
            return {"skeleton": "/Game/PipelineCandidates/Hero/Rig/SK_Hero_Skeleton", "created": False,
                    "bones_in_order": ["SKEL", "root"], "bone0": "SKEL"}
        if name == "preview_mesh.py" and kw["op"] == "state":  # the task's shape: the state is its "before" block
            return {"op": "state", "mesh": kw["mesh"], "dirty_before": [], "before": dict(self.state, mesh=kw["mesh"])}
        if name == "preview_mesh.py" and kw["op"] == "refresh":
            self.state = dict(self.state, exists=True, sha_stamp=kw["fbx_sha256"], source_files=[kw["fbx"]])
            return {"after": dict(self.state), "imported": [kw["mesh"]], "ref_pose_equal": True, "saved": True}
        raise AssertionError("unexpected task %s %s" % (name, kw))


class SkeletonCommandTest(TempRepo):
    def run_skeleton(self, state, refresh_preview=False):
        fake = FakeUe(state)
        orig = H.Ue
        H.Ue = lambda: fake
        try:
            H.cmd_skeleton(SimpleNamespace(spec=str(self.spec()), refresh_preview=refresh_preview))
        finally:
            H.Ue = orig
        rep = json.loads((self.tmp / "run/reports/ue-canonical-skeleton.json").read_text(encoding="utf-8"))
        return fake, rep

    def test_stale_carrier_is_reimported_onto_the_existing_skeleton_and_stamped(self):
        old = self.fbx("bake-r2/export/SK_Hero_H2.fbx", b"old")
        new = self.fbx("bake/export/SK_Hero_H2.fbx", b"new")
        fake, rep = self.run_skeleton({"exists": True, "source_files": [old.as_posix()], "top_z": 60.0})
        refresh = [kw for n, kw in fake.tasks if n == "preview_mesh.py" and kw["op"] == "refresh"]
        self.assertEqual(len(refresh), 1)
        self.assertEqual(refresh[0]["skeleton"], "/Game/PipelineCandidates/Hero/Rig/SK_Hero_Skeleton")
        self.assertEqual(refresh[0]["fbx_sha256"], sha(new))
        self.assertTrue(rep["preview_mesh"]["current"])
        self.assertEqual(rep["preview_mesh"]["fbx_sha256"], sha(new))
        self.assertEqual(rep["target_fbx_sha256_now"], sha(new))
        # canonical_skeleton.py gets the sha too (a NEW carrier is stamped at creation)
        self.assertEqual([kw for n, kw in fake.tasks if n == "canonical_skeleton.py"][0]["fbx_sha256"], sha(new))

    def test_current_carrier_is_kept_unless_forced(self):
        new = self.fbx("bake/export/SK_Hero_H2.fbx", b"new")
        fake, rep = self.run_skeleton({"exists": True, "sha_stamp": sha(new), "source_files": [new.as_posix()]})
        self.assertFalse([1 for n, kw in fake.tasks if kw.get("op") == "refresh"])
        self.assertIsNone(rep["preview_mesh"]["refresh"])
        fake2, rep2 = self.run_skeleton({"exists": True, "sha_stamp": sha(new), "source_files": [new.as_posix()]},
                                        refresh_preview=True)
        self.assertEqual(len([1 for n, kw in fake2.tasks if kw.get("op") == "refresh"]), 1)
        self.assertTrue(rep2["preview_mesh"]["decision"]["reason"].startswith("--refresh-preview"))


class PreviewCheckTest(TempRepo):
    def test_frames_refuse_a_stale_carrier_and_accept_a_current_one(self):
        old = self.fbx("bake-r2/export/SK_Hero_H2.fbx", b"old")
        new = self.fbx("bake/export/SK_Hero_H2.fbx", b"new")
        spec = H.load_spec(self.spec())
        with self.assertRaises(SystemExit) as cm:
            H.preview_check(FakeUe({"exists": True, "source_files": [old.as_posix()]}), spec, self.tmp / "t.json")
        self.assertIn("h2anim_ue.py skeleton", str(cm.exception))
        ok = H.preview_check(FakeUe({"exists": True, "sha_stamp": sha(new)}), spec, self.tmp / "t.json")
        self.assertEqual(ok["fbx_sha256_of_frames"], sha(new))

    def test_a_non_carrier_preview_mesh_is_recorded_not_enforced(self):
        self.fbx("bake/export/SK_Hero_H2.fbx", b"new")
        spec = H.load_spec(self.spec(ue_extra={"mesh_for_preview": "/Game/PipelineCandidates/Hero/H2/Meshes/SK_Hero_H2"}))
        res = H.preview_check(FakeUe({"exists": True, "source_files": ["C:/gone.fbx"]}), spec, self.tmp / "t.json")
        self.assertFalse(res["enforced"])
        self.assertIsNone(res["fbx_sha256_of_frames"])


class BaseDefaultTest(TempRepo):
    def test_order_flag_spec_convention(self):
        self.fbx("bake/export/SK_Hero_H2.fbx")
        spec = H.load_spec(self.spec())
        self.assertEqual(H.resolve_base(spec, no_base=True), (None, "none (--no-base)"))
        self.assertEqual(H.resolve_base(spec, base="/Game/X/SM_B")[0], "/Game/X/SM_B")
        self.assertEqual(H.resolve_base(spec, exists=lambda p: True)[0],
                         "/Game/PipelineCandidates/Hero/H2LD/Meshes/SM_Hero_H2LD_Base")
        spec["ue"]["base"] = "/Game/PipelineCandidates/Hero/H2LD/Meshes/SM_Other"
        self.assertEqual(H.resolve_base(spec, exists=lambda p: True), (spec["ue"]["base"], "spec ue.base"))

    def test_missing_base_is_refused_with_the_way_out(self):
        self.fbx("bake/export/SK_Hero_H2.fbx")
        spec = H.load_spec(self.spec())
        with self.assertRaises(SystemExit) as cm:
            H.resolve_base(spec, exists=lambda p: False)
        self.assertIn("--no-base", str(cm.exception))
        self.assertIn("--base", str(cm.exception))

    def test_cli_base_and_no_base_are_exclusive(self):
        argv0 = sys.argv
        sys.argv = ["h2anim_ue.py", "frames", "spec.json", "--base", "/Game/X", "--no-base"]
        try:
            with self.assertRaises(SystemExit) as cm:
                H.main()
            self.assertEqual(cm.exception.code, 2)
        finally:
            sys.argv = argv0


class CameraTest(unittest.TestCase):
    T = H.half_tan_v(2033, 1216)  # the agent editor's viewport (-ResX=2033 -ResY=1216)

    def test_viewport_crop_angle(self):
        self.assertAlmostEqual(self.T, 0.1779, places=3)
        self.assertAlmostEqual(H.half_tan_v(2560, 1080), H.half_tan_v(2560, 1080, 35.1), places=6)
        self.assertLess(H.half_tan_v(2560, 1080), self.T)  # wider than 16:9: the crop takes the height

    def test_figures_that_fit_keep_the_mvp_eye(self):
        for top in (55.0, 55.909, 60.0):  # Angel 55.9 (sword tip), Arthur / Merlin ~55-60
            cam = H.frame_camera(top, 5.6, self.T)
            self.assertEqual((cam["mode"], cam["eye_dist_uu"], cam["eye_z_uu"]), ("mvp", 200.0, 31.0), top)

    def test_tall_figure_backs_off_and_is_fully_framed(self):
        cam = H.frame_camera(73.56, 5.6, self.T)  # Ancient Leshen antler tips (F136)
        self.assertEqual(cam["mode"], "fit")
        self.assertGreater(cam["eye_dist_uu"], 200.0)
        lo, hi = cam["eye_z_uu"] - cam["eye_dist_uu"] * self.T, cam["eye_z_uu"] + cam["eye_dist_uu"] * self.T
        self.assertLessEqual(lo, 0.0)
        self.assertGreaterEqual(hi, 73.56 + 0.05 * 73.56)

    def test_no_bounds_is_mvp(self):
        self.assertEqual(H.frame_camera(None, None, self.T)["mode"], "mvp")


class WarmUpTest(unittest.TestCase):
    @staticmethod
    def grabs(levels):
        it = iter(levels)
        return lambda: Image.new("RGB", (8, 8), (next(it),) * 3)

    def test_converges_after_the_minimum(self):
        levels = [0, 50, 100, 101, 102, 102, 102, 102]
        diffs, ok = H.warm_up(self.grabs(levels), min_diffs=4, max_diffs=7, sleep=lambda s: None)
        self.assertTrue(ok)
        self.assertEqual(len(diffs), 5)  # 50, 50, 1, 1, 0 -> last three <= 1 at the 5th difference

    def test_never_converging_viewport_is_reported(self):
        levels = [(i % 2) * 3 for i in range(10)]
        diffs, ok = H.warm_up(self.grabs(levels), min_diffs=2, max_diffs=6, sleep=lambda s: None)
        self.assertFalse(ok)
        self.assertEqual(len(diffs), 6)


class SheetPreviewTest(TempRepo):
    def test_frames_of_an_older_carrier_are_stale(self):
        new = self.fbx("bake/export/SK_Hero_H2.fbx", b"new")
        spec = H.load_spec(self.spec())
        run = self.tmp / "run"
        (run / "preview/ue").mkdir(parents=True)
        frames = {}
        for f in (0, 2):
            for v in ("front", "q34"):
                name = "Hero-Idle-f%02d-%s-ue-editor.jpg" % (f, v)
                Image.new("RGB", (1920, 1080), (40, 40, 40)).save(run / "preview/ue" / name)
                frames[name] = {"sha256": sha(run / "preview/ue" / name), "imported_fbx_sha256": None,
                                "preview_fbx_sha256": sha(new)}
        self.assertIsNotNone(H.build_sheet(spec, run, frames))
        frames["Hero-Idle-f02-q34-ue-editor.jpg"]["preview_fbx_sha256"] = "0" * 64
        self.assertIsNone(H.build_sheet(spec, run, frames))


if __name__ == "__main__":
    unittest.main()
