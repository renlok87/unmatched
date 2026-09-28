import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tests._util import FIXTURE_TRACE, run_cli, save_png, solid, topdown_cell_rect, topdown_trace
from qa010lib.imageio import load_rgb


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class DeriveCliTests(unittest.TestCase):
    def test_batch_derive_is_read_only_and_deterministic(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "evidence"
            a = save_png(src / "host" / "k1.png", solid(8, 4, (255, 0, 0)))
            b = save_png(src / "joiner" / "k1.png", solid(8, 4, (0, 0, 255)))
            before = {p: sha(p) for p in (a, b)}
            out = Path(d) / "out"
            code, man, err = run_cli("derive", src, "--out", out)
            self.assertEqual(code, 0, err)
            self.assertEqual({p: sha(p) for p in (a, b)}, before)          # inputs untouched
            self.assertEqual(len(man["entries"]), 2)                       # same basename, no collision
            gray = load_rgb(out / "host" / "k1.gray.png")
            deut = load_rgb(out / "host" / "k1.deuteranopia.png")
            self.assertEqual(tuple(gray[0, 0]), (54, 54, 54))
            self.assertEqual(tuple(deut[0, 0]), (163, 144, 0))
            for e in man["entries"]:
                self.assertEqual(e["gray"]["sha256"], sha(Path(e["gray"]["path"])))
            first = {e["deuteranopia"]["sha256"] for e in man["entries"]}
            code, man2, _ = run_cli("derive", src, "--out", out)
            self.assertEqual({e["deuteranopia"]["sha256"] for e in man2["entries"]}, first)
            self.assertTrue((out / "qa010-derive-manifest.json").exists())

    def test_same_basename_from_different_runs_does_not_collide(self):
        with tempfile.TemporaryDirectory() as d:
            ev = Path(d) / "evidence"
            a = save_png(ev / "run-1" / "phase2-board-host.png", solid(4, 4, (255, 0, 0)))
            b = save_png(ev / "run-2" / "phase2-board-host.png", solid(4, 4, (0, 0, 255)))
            c = save_png(ev / "run-3" / "joiner" / "shot.png", solid(4, 4, (0, 255, 0)))
            out = Path(d) / "out"
            code, man, err = run_cli("derive", a, b, a, "--out", out)
            self.assertEqual(code, 0, err)
            self.assertEqual(len(man["entries"]), 2)            # duplicate input dropped
            outs = {e["gray"]["path"] for e in man["entries"]}
            self.assertEqual(len(outs), 2)
            self.assertEqual(tuple(load_rgb(out / "run-1" / "phase2-board-host.gray.png")[0, 0]), (54, 54, 54))
            self.assertEqual(tuple(load_rgb(out / "run-2" / "phase2-board-host.gray.png")[0, 0]), (18, 18, 18))
            # directory scan keeps its relative layout; a colliding file input gets its run dir
            save_png(ev / "run-4" / "joiner" / "shot.png", solid(4, 4, (9, 9, 9)))
            code, man, err = run_cli("derive", ev / "run-3", ev / "run-4", "--out", out / "dirs")
            self.assertEqual(code, 0, err)
            names = sorted(Path(e["gray"]["path"]).relative_to(out / "dirs").as_posix() for e in man["entries"])
            self.assertEqual(names, ["run-3/joiner/shot.gray.png", "run-4/joiner/shot.gray.png"])
            self.assertTrue(c.exists())

    def test_derived_files_are_skipped_when_rescanning(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            save_png(src / "k.png", solid(4, 4, (10, 20, 30)))
            save_png(src / "k.gray.png", solid(4, 4, (1, 1, 1)))
            code, man, _ = run_cli("derive", src, "--out", src / "out")
            self.assertEqual([Path(e["input"]).name for e in man["entries"]], ["k.png"])

    def test_missing_input(self):
        code, _, err = run_cli("derive", "C:/definitely/missing.png", "--out", tempfile.gettempdir())
        self.assertEqual(code, 2)


class LumaC9CliTests(unittest.TestCase):
    def test_luma_regions(self):
        with tempfile.TemporaryDirectory() as d:
            img = solid(100, 50, (0, 0, 0))
            img[:, 50:] = 200
            f = save_png(Path(d) / "f.png", img)
            code, res, err = run_cli("luma", f, "--region", "right=bbox:50,0,100,50", "--json", Path(d) / "l.json")
            self.assertEqual(code, 0, err)
            fr = res["frames"][0]
            self.assertEqual(fr["stats"]["luma_p90"], 200.0)
            self.assertEqual(fr["regions"]["right"]["stats"]["luma_p50"], 200.0)
            self.assertEqual(json.loads((Path(d) / "l.json").read_text(encoding="utf-8")), res)

    def test_c9_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            img = solid(100, 100, (100, 100, 100))
            img[:, :50] = (150, 150, 150)
            f = save_png(Path(d) / "f.png", img)
            ok = run_cli("c9", f, "--game", "g=bbox:0,0,50,100", "--decor", "d=bbox:50,0,100,100")
            self.assertEqual(ok[0], 0)
            self.assertEqual(ok[1]["result_normative"], "pass")
            gated = run_cli("c9", f, "--game", "g=bbox:0,0,50,100", "--decor", "d=bbox:50,0,100,100",
                            "--gate-proposed", "--ev-range", "0.9,1.2")
            self.assertEqual(gated[0], 1)
            bad = run_cli("c9", f, "--game", "g=bbox:50,0,100,100", "--decor", "d=bbox:0,0,50,100")
            self.assertEqual(bad[0], 1)
            few = run_cli("c9", f, "--game", "g=bbox:0,0,5,5", "--decor", "d=bbox:50,0,100,100")
            self.assertEqual(few[0], 3)

    def test_c9_trace_regions(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "t.trace.txt"
            t.write_text(topdown_trace(name="f.png", cam_z=2000), encoding="utf-8")
            img = solid(1920, 1080, (30, 30, 30))
            # board area (fully inside the frame at 2000 uu) brighter than surroundings
            bx0, by0, _, _ = topdown_cell_rect(3, 0, cam_z=2000)
            _, _, bx1, by1 = topdown_cell_rect(0, 2, cam_z=2000)
            self.assertTrue(0 < by0 < by1 < 1080 and 0 < bx0 < bx1 < 1920)
            img[int(by0) + 1:int(by1), int(bx0) + 1:int(bx1)] = (120, 120, 120)
            f = save_png(Path(d) / "f.png", img)
            # trace-ring = tray ring (L4), not decor L3: measured, but never a normative result
            for name in ("ring", "decor"):   # a neutral region name must not hide the proxy
                code, res, err = run_cli("c9", f, "--trace", t, "--game", "b=trace-cells:all",
                                         "--decor", f"{name}=trace-ring:0.1,0.5")
                self.assertEqual(code, 3, err)
                self.assertIn("proxy", err)
                self.assertEqual(res["status"], "measured")
                self.assertEqual((res["result_normative"], res["result_proposed"]), ("proxy", "proxy"))
                self.assertEqual(res["result_on_proxy"]["normative"], "pass")
                self.assertTrue(res["layer_basis"]["proxy"])
                self.assertFalse(res["layer_basis"]["normative"])
                self.assertTrue(res["decor_region"]["proxy"])
                self.assertEqual(res["decor_region"]["kinds"], ["trace-ring"])
                self.assertFalse(res["proxy_accepted_by_flag"])
            self.assertEqual(res["trace"]["shot"], "f.png")
            self.assertTrue(res["trace"]["shot_matches_frame"])
            self.assertGreater(res["delta_ev"]["used"], 1.0)
            # --accept-proxy: exit code from the proxy measurement, JSON still not normative
            code, res, err = run_cli("c9", f, "--trace", t, "--game", "b=trace-cells:all",
                                     "--decor", "decor=trace-ring:0.1,0.5", "--accept-proxy")
            self.assertEqual(code, 0, err)
            self.assertEqual(res["result_normative"], "proxy")
            self.assertTrue(res["proxy_accepted_by_flag"])
            # board cells as "decor" are the game plane L2; the tray ring is not the game layer
            code, res, _ = run_cli("c9", f, "--trace", t, "--game", "b=trace-cells:0,0",
                                   "--decor", "d=trace-cells:3,2")
            self.assertEqual((code, res["result_normative"]), (3, "proxy"))
            self.assertEqual(res["layer_basis"]["proxy_regions"][0]["layer"], "decor")
            code, res, _ = run_cli("c9", f, "--trace", t, "--game", "g=trace-ring:0.1,0.5",
                                   "--decor", "d=bbox:0,0,200,200")
            self.assertEqual((code, res["result_normative"]), (3, "proxy"))
            self.assertEqual([x["layer"] for x in res["layer_basis"]["proxy_regions"]], ["game"])
            # a caller mask (bbox/poly/mask) for decor is not a proxy: normative result
            code, res, err = run_cli("c9", f, "--trace", t, "--game", "b=trace-cells:all",
                                     "--decor", "d=bbox:0,0,200,200")
            self.assertEqual(code, 0, err)
            self.assertEqual(res["result_normative"], "pass")
            self.assertFalse(res["layer_basis"]["proxy"])
            self.assertNotIn("result_on_proxy", res)


class PlateIconProjectCliTests(unittest.TestCase):
    def test_plate_exit_codes_on_fixture(self):
        expected = {"k2-plate-clear.png": 0, "k2-plate-overlap.png": 1,
                    "k2-plate-client-mismatch.png": 1, "k2-plate-missing.png": 3,
                    "k2-plate-camera-uninitialised.png": 3,
                    # nothing checked is never a pass (empty selection, plate off-screen,
                    # zero-size UMG geometry, every selected cell off-screen)
                    "k2-plate-reachable-empty.png": 3, "k2-plate-offscreen-bbox.png": 3,
                    "k2-plate-zero-bbox.png": 3, "k2-plate-cells-offscreen.png": 3}
        for shot, want in expected.items():
            code, res, err = run_cli("plate", "--trace", FIXTURE_TRACE, "--shot", shot)
            self.assertEqual(code, want, f"{shot}: {err} {res and res.get('reason')}")

    def test_plate_requires_trace(self):
        with self.assertRaises(SystemExit):
            run_cli("plate")

    def test_plate_overlay(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d) / "t.trace.txt"
            x0, y0, x1, y1 = topdown_cell_rect(1, 1)
            t.write_text(topdown_trace(plate=(x0, y0, x1, y1), reachable=[(2, 2)], name="f.png"), encoding="utf-8")
            f = save_png(Path(d) / "f.png", solid(1920, 1080, (50, 50, 50)))
            ov = Path(d) / "ov.png"
            code, res, err = run_cli("plate", "--trace", t, "--frame", f, "--overlay", ov)
            self.assertEqual(code, 0, err)
            self.assertTrue(ov.exists())
            self.assertNotEqual(sha(ov), sha(f))
            self.assertEqual(res["frame"]["sha256"], sha(f))       # binds the result to the frame
            self.assertTrue(res["frame"]["matches_shot"])

    def test_icon_from_trace_line(self):
        with tempfile.TemporaryDirectory() as d:
            img = solid(1920, 1080, (20, 20, 20))
            img[700:740, 955:965] = 240
            img[715:725, 940:980] = 240
            f = save_png(Path(d) / "k2-plate-clear.png", img)
            code, res, err = run_cli("icon", f, "--trace", FIXTURE_TRACE)
            self.assertEqual(code, 0, err)
            self.assertTrue(res["bbox_source"].startswith("trace:shot-block"))
            self.assertEqual(res["bbox"], [940, 700, 980, 740])
            code, res, _ = run_cli("icon", f, "--trace", FIXTURE_TRACE, "--shot", "k2-plate-overlap.png")
            self.assertEqual(code, 3)
            self.assertEqual(res["status"], "requires_new_trace")

    def test_icon_needs_bbox_or_trace(self):
        with tempfile.TemporaryDirectory() as d:
            f = save_png(Path(d) / "f.png", solid(10, 10, (0, 0, 0)))
            self.assertEqual(run_cli("icon", f)[0], 2)

    def test_project(self):
        code, res, err = run_cli("project", "--trace", FIXTURE_TRACE, "--shot", "#0")
        self.assertEqual(code, 0, err)
        s = res["shots"][0]
        self.assertTrue(s["projection"]["ok"])
        self.assertEqual(s["cells_in_frame"]["total"], 30)
        self.assertEqual(len(s["cells"]), 30)
        self.assertEqual(s["zoom_source"]["zoom"], 1.6)   # E4: zoom came from the test flag
        code, res, _ = run_cli("project", "--trace", FIXTURE_TRACE, "--all")
        self.assertEqual(code, 0)   # survey passes: every camera-valid block validates
        self.assertEqual(len(res["shots"]), 9)
        self.assertNotIn("frame", res)
        bad = [s for s in res["shots"] if not s["projection"]["ok"]]
        self.assertEqual([s["shot"] for s in bad], ["k2-plate-camera-uninitialised.png"])  # reported, not hidden


if __name__ == "__main__":
    unittest.main()
