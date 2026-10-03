"""ENV-MAPS live tune: tools/art/render/live_tune.py (the driver of the -ArtLiveTune file protocol, S08LiveTune.h) against a
fake client - no UE, no GPU lock of the machine (every lock / session file lives in a temp folder).

  python -B -m pytest -q tools/art/tests/test_live_tune.py
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "render"))
import live_tune as LT  # noqa: E402


class SelfCheck(unittest.TestCase):
    def test_self_check(self):
        self.assertEqual(LT.self_check(), [])

    def test_cli_check(self):
        self.assertEqual(LT.main(["--check"]), 0)


class Protocol(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_seq_follows_cmd_and_done_files(self):
        d = self.root / "s"
        d.mkdir()
        self.assertEqual(LT.next_seq(d), 1)
        (d / "cmd-4.json").write_text("{}", encoding="utf-8")
        (d / "done-2.json").write_text("{}", encoding="utf-8")
        (d / "cmd-9.json.tmp").write_text("{}", encoding="utf-8")
        self.assertEqual(LT.next_seq(d), 5)

    def test_atomic_write_leaves_no_tmp(self):
        p = self.root / "cmd-1.json"
        LT.write_atomic(p, '{"action":"state"}')
        self.assertEqual(json.loads(p.read_text(encoding="utf-8"))["action"], "state")
        self.assertFalse((self.root / "cmd-1.json.tmp").exists())

    def test_shot_command_fields(self):
        ns = argparse.Namespace(views="K1+K2x2.5", out=str(self.root / "o"), tag="t", settle=6.0, measure=None, post=None,
                                shot_warmup=None, clock="free", live=True, append=False, no_fresh=True, bench_gap=0.5,
                                bench_gap_later=None)
        cmd = LT.shot_cmd(ns)
        self.assertEqual(cmd["action"], "shot")
        self.assertTrue(Path(cmd["out"]).is_absolute())
        self.assertEqual((cmd["settle"], cmd["clock"], cmd["live"], cmd["fresh"]), (6.0, "free", True, False))
        self.assertEqual(cmd["bench"], {"gap": 0.5})
        self.assertNotIn("measure", cmd)
        self.assertGreater(LT.shot_timeout(cmd), 60.0)

    def test_reload_command_defaults_to_the_session_paths(self):
        s = {"reloadProfiles": str(self.root / "p.json"), "reloadEnvDir": None}
        cmd = LT.reload_cmd(s, None, None)
        self.assertEqual(cmd["action"], "reload")
        self.assertTrue(cmd["profiles"].endswith("/p.json"))
        self.assertNotIn("envDir", cmd)
        self.assertNotIn("profiles", LT.reload_cmd({}, None, None))

    def test_missing_done_times_out_with_code_3(self):
        d = self.root / "s"
        d.mkdir()
        with self.assertRaises(LT.LiveTuneError) as e:
            LT.send({"pid": 1, "dir": str(d), "fake": True}, {"action": "state"}, 0.2)
        self.assertEqual(e.exception.code, 3)

    def test_no_session_is_usage_error(self):
        with self.assertRaises(LT.LiveTuneError) as e:
            LT.load_session(self.root)
        self.assertEqual(e.exception.code, 2)


class Locks(unittest.TestCase):
    def test_acquire_release_only_own(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "gpu.lock"
            LT.lock_acquire(lock, "test", timeout=2)
            self.assertTrue(lock.read_text().startswith("owner=LIVE-TUNE pid="))
            # a second acquire waits, then times out (exit code 3)
            with self.assertRaises(LT.LiveTuneError) as e:
                LT.lock_acquire(lock, "again", timeout=0.3, poll=0.1)
            self.assertEqual(e.exception.code, 3)
            LT.lock_rewrite(lock, "owner=LIVE-TUNE pid=777 map=marmoreal session=x live-tune")
            self.assertFalse(LT.lock_release(lock, pid=778), "another session's pid")
            self.assertTrue(LT.lock_release(lock, pid=777))
            self.assertFalse(lock.exists())
            lock.write_text("owner=ENV-MAPS-P9B pid=1 bench\n")
            self.assertFalse(LT.lock_release(lock), "a foreign lock stays")
            LT.lock_rewrite(lock, "owner=LIVE-TUNE pid=2 hijack")
            self.assertTrue(lock.read_text().startswith("owner=ENV-MAPS-P9B"), "a foreign lock is never rewritten")


class ClientArgs(unittest.TestCase):
    def test_editor_and_packaged(self):
        ed = LT.client_args("editor", "marmoreal", Path("C:/tmp/lt/m"), 30, LT.BENCH["editor"], "C:/p.json", "C:/env", [])
        self.assertIn("-game", ed)
        self.assertTrue(any(a.startswith("-ArtLiveTune=") for a in ed))
        self.assertIn("-ArtBoardProfiles=C:/p.json", ed)
        self.assertIn("-ArtEnvLayouts=C:/env", ed)
        self.assertTrue(any("S08BenchMarmoreal.json" in a for a in ed))
        pk = LT.client_args("packaged", "sarpedon", Path("C:/tmp/lt/s"), 60, LT.BENCH["packaged"], None, None, [])
        self.assertNotIn("-game", pk)
        self.assertIn("-BenchMeasure=3", pk)
        bn = LT.bench_args("editor", "sarpedon", Path("C:/tmp/lt/b"), "K1+K2x2.5", LT.BENCH["editor"], ["-NoHeroLight"])
        self.assertFalse(any(a.startswith(("-ArtLiveTune", "-ArtLiveTuneWarmup")) for a in bn))
        self.assertIn("-BenchViews=K1+K2x2.5", bn)
        self.assertIn("-NoHeroLight", bn)

    def test_kill_needs_the_session_marker(self):
        # a pid whose command line does not carry -ArtLiveTune=<dir> is never killed (here: this python process)
        import os
        self.assertFalse(LT.kill_own(os.getpid(), "-ArtLiveTune=C:/tmp/live-tune/none"))


class Compare(unittest.TestCase):
    def test_gate_and_noise_mask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rng = np.random.default_rng(1)
            base = rng.integers(40, 200, size=(1080, 1920, 3), dtype=np.uint8)
            runs = {}
            for name in ("a", "noise", "same", "changed"):
                img = base.copy()
                if name in ("noise", "same", "changed"):
                    img[100:140, 100:140] = 255 - img[100:140, 100:140]  # a "fire" that differs between fresh runs
                if name == "changed":
                    img[500:600, 900:1000] = np.clip(img[500:600, 900:1000].astype(int) + 60, 0, 255)
                d = root / name
                d.mkdir()
                Image.fromarray(img).save(d / "bench-K1-1920x1080.png")
                runs[name] = d
            same = LT.compare_runs(runs["a"], runs["same"], noise=runs["noise"])
            v = same["views"]["bench-K1-1920x1080.png"]
            self.assertFalse(v["pass"], "raw: the fire area alone is 0.08 % of the frame")
            self.assertTrue(same["passOutsideNoise"], "outside the bench-noise mask: identical")
            self.assertEqual(v["outsideBenchNoise"]["pxOver24"], 0)
            changed = LT.compare_runs(runs["a"], runs["changed"], noise=runs["noise"])
            self.assertFalse(changed["passOutsideNoise"], "a real change is outside the noise mask")
            self.assertEqual(LT.compare_runs(runs["a"], runs["a"])["pass"], True)


if __name__ == "__main__":
    unittest.main()
