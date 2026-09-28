import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import unittest

from tests._util import EVIDENCE, FIXTURE_TRACE, topdown_cell_rect, topdown_trace
from qa010lib.geometry import clip_polygon_to_rect, overlap_area, parse_bbox, polygon_area
from qa010lib.projection import build_projection, project_cell
from qa010lib.trace import TraceError, parse_trace, parse_trace_text


class GeometryTests(unittest.TestCase):
    def test_polygon_area(self):
        self.assertEqual(polygon_area([(0, 0), (10, 0), (10, 10), (0, 10)]), 100.0)
        self.assertEqual(polygon_area([(0, 10), (10, 10), (10, 0), (0, 0)]), 100.0)  # CW
        self.assertEqual(polygon_area([(0, 0), (4, 0), (0, 3)]), 6.0)
        self.assertEqual(polygon_area([(0, 0), (1, 1)]), 0.0)

    def test_clip_known_areas(self):
        sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
        self.assertEqual(overlap_area(sq, (5, 5, 20, 20)), 25.0)
        self.assertEqual(overlap_area(sq, (-5, -5, 20, 20)), 100.0)
        self.assertEqual(overlap_area(sq, (2, 2, 4, 4)), 4.0)
        self.assertEqual(overlap_area(sq, (11, 0, 20, 10)), 0.0)
        self.assertEqual(clip_polygon_to_rect(sq, (20, 20, 30, 30)), [])
        # right triangle cut by x <= 2: trapezoid area = 6 - 0.5*2*1.5
        self.assertAlmostEqual(overlap_area([(0, 0), (4, 0), (0, 3)], (0, 0, 2, 10)), 4.5)

    def test_parse_bbox(self):
        self.assertEqual(parse_bbox("(10,20,5,40)"), (5.0, 20.0, 10.0, 40.0))
        with self.assertRaises(ValueError):
            parse_bbox("1,2,3")
        with self.assertRaises(ValueError):
            parse_bbox("1,1,1,5")


class TraceParserTests(unittest.TestCase):
    def setUp(self):
        self.trace = parse_trace(FIXTURE_TRACE)

    def test_blocks_and_board(self):
        t = self.trace
        self.assertEqual((t.board.width, t.board.height), (5, 6))
        self.assertEqual(t.board.consistency_errors(), [])
        self.assertEqual(t.board.cell_center(0, 0), (-200.0, -250.0, 0.0))
        self.assertEqual(t.board.cell_center(4, 5), (200.0, 250.0, 0.0))
        self.assertEqual([s.name for s in t.shots], [
            "k2-plate-clear.png", "k2-plate-overlap.png", "k2-plate-client-mismatch.png",
            "k2-plate-missing.png", "k2-plate-camera-uninitialised.png",
            "k2-plate-reachable-empty.png", "k2-plate-offscreen-bbox.png", "k2-plate-zero-bbox.png",
            "k2-plate-cells-offscreen.png"])
        empty = t.find_shot("k2-plate-reachable-empty.png").reachable.value
        self.assertEqual((empty["n"], empty["cells"]), (0, []))
        self.assertEqual(t.find_shot("k2-plate-zero-bbox.png").plate.value["bbox"], (0.0, 0.0, 0.0, 0.0))

    def test_new_lines(self):
        s = self.trace.find_shot("k2-plate-clear.png")
        self.assertEqual(s.reachable.source, "shot-block")
        self.assertEqual(s.reachable.value["n"], 14)
        self.assertIn((3, 1), s.reachable.value["cells"])
        self.assertEqual(s.plate.value["bbox"], (880.0, 400.0, 1040.0, 470.0))
        self.assertEqual(s.plate.value["overlap_reachable"], 0)
        self.assertEqual(s.icon.value["fighter"], "f-1-hero")
        self.assertEqual(s.selection["reachable_count"], 14)
        self.assertEqual(s.focus["zoom"], 1.6)
        self.assertIsNone(self.trace.find_shot("k2-plate-missing.png").plate)

    def test_shot_selection(self):
        self.assertEqual(self.trace.find_shot("#1").name, "k2-plate-overlap.png")
        self.assertEqual(self.trace.find_shot(None, "C:/x/k2-plate-overlap.png").index, 1)
        with self.assertRaises(TraceError):
            self.trace.find_shot("nope.png")
        with self.assertRaises(TraceError):
            self.trace.find_shot(None)  # several camera-valid blocks, no hint

    def test_reachable_count_mismatch_is_an_error(self):
        text = ("2026.09.28-00.00.00 SHOT ctx viewport=1920x1080 viewTarget=C cam=(0,1,2) rot=(-55,-90,0)\n"
                "2026.09.28-00.00.00 SHOT reachable fighter=f n=3 cells=(1,1)(2,2)\n")
        with self.assertRaises(TraceError):
            parse_trace_text(text)

    def test_standalone_lines_apply_to_next_shot(self):
        text = ("2026.09.28-00.00.00 PLATE fighter=f bbox=(1,2,3,4) overlapReachable=0\n"
                "2026.09.28-00.00.00 REACHABLE fighter=f n=1 cells=(0,0)\n"
                "2026.09.28-00.00.01 SHOT ctx viewport=1920x1080 viewTarget=C cam=(0,1,2) rot=(-55,-90,0)\n"
                "2026.09.28-00.00.01 SHOT requested: FScreenshotRequest(bShowUI) -> C:\\a\\b.png\n")
        s = parse_trace_text(text).shots[0]
        self.assertEqual(s.plate.source, "standalone-latest")
        self.assertEqual(s.reachable.value["cells"], [(0, 0)])
        self.assertEqual(s.name, "b.png")


class ProjectionTests(unittest.TestCase):
    def test_fixture_camera_reproduces_client_projection(self):
        s = parse_trace(FIXTURE_TRACE).find_shot("k2-plate-clear.png")
        rep = build_projection(s, 35.0, 2.0, "trace")
        self.assertTrue(rep.ok, rep.reason)
        self.assertLess(rep.residual_max_used, 2.0)

    def test_uninitialised_camera_rejected(self):
        s = parse_trace(FIXTURE_TRACE).find_shot("k2-plate-camera-uninitialised.png")
        rep = build_projection(s, 35.0, 2.0)
        self.assertFalse(rep.ok)
        self.assertIn("not initialised", rep.reason)

    def test_wrong_fov_is_detected(self):
        s = parse_trace(FIXTURE_TRACE).find_shot("k2-plate-clear.png")
        rep = build_projection(s, 20.0, 2.0, "trace")
        self.assertFalse(rep.ok)

    def test_fit_recovers_rounded_camera_at_k2_zoom(self):
        # real 5x K2 block (ART-004/live-k2-label-probe-5x): cam printed rounded to whole uu
        text = "\n".join([
            "2026.09.28-01.39.13 BOARD 5x6 cells | control points: (0,0)=(-200,-250,0) (4,5)=(200,250,0) | neighbor pair (dist 100 uu)",
            "2026.09.28-01.39.25 SHOT ctx viewport=1920x1080 viewTarget=CameraActor_2147482372 cam=(0,171,344) rot=(-55,-90,0)",
            "2026.09.28-01.39.25 SHOT fighter f-0-hero pos=(2,2) world=(0,-50,0) screen=(960,660) projected=1 alive=1",
            "2026.09.28-01.39.25 SHOT fighter f-0-sk0 pos=(3,2) world=(100,-50,0) screen=(1704,660) projected=1 alive=1",
            "2026.09.28-01.39.25 SHOT fighter f-0-sk1 pos=(2,1) world=(0,-150,0) screen=(960,110) projected=1 alive=1",
            "2026.09.28-01.39.25 SHOT fighter f-0-sk2 pos=(1,2) world=(-100,-50,0) screen=(216,660) projected=1 alive=1",
            "2026.09.28-01.39.25 SHOT fighter f-1-hero pos=(2,3) world=(0,50,0) screen=(960,1388) projected=1 alive=1",
            "2026.09.28-01.39.25 SHOT fighter f-1-sk0 pos=(3,3) world=(100,50,0) screen=(1826,1388) projected=1 alive=1",
            "2026.09.28-01.39.25 SHOT requested: FScreenshotRequest(bShowUI) -> C:\\x\\k2.png"])
        s = parse_trace_text(text).shots[0]
        trace_only = build_projection(s, 35.0, 2.0, "trace")
        auto = build_projection(s, 35.0, 2.0, "auto")
        self.assertFalse(trace_only.ok)            # ~3.4 px from rounding alone
        self.assertTrue(auto.ok)
        self.assertEqual(auto.mode, "fit")
        self.assertLess(auto.residual_max_used, 1.0)

    def test_topdown_cells_are_exact_rectangles(self):
        s = parse_trace_text(topdown_trace()).shots[0]
        rep = build_projection(s, 35.0, 0.05, "trace")
        self.assertTrue(rep.ok, rep.reason)
        pc = project_cell(rep.camera, s.board, 2, 1)
        xs = sorted(p[0] for p in pc["quad"])
        ys = sorted(p[1] for p in pc["quad"])
        ex = topdown_cell_rect(2, 1)
        self.assertAlmostEqual(xs[0], ex[0], places=6)
        self.assertAlmostEqual(xs[-1], ex[2], places=6)
        self.assertAlmostEqual(ys[0], ex[1], places=6)
        self.assertAlmostEqual(ys[-1], ex[3], places=6)


@unittest.skipUnless(EVIDENCE.exists(), "evidence tree not present")
class RealTraceSurveyTests(unittest.TestCase):
    """Every camera-valid SHOT block with >= 2 projected fighters in the real
    S08/S09/ART traces must be reproduced within the default tolerance."""

    def test_all_real_shot_blocks(self):
        checked = 0
        for p in EVIDENCE.rglob("*.trace.log"):
            for s in parse_trace(p).shots:
                if not s.camera_valid() or sum(f.projected for f in s.fighters) < 2:
                    continue
                rep = build_projection(s, 35.0, 2.0, "auto")
                self.assertTrue(rep.ok, f"{p}:{s.line_no}: {rep.reason}")
                checked += 1
        if checked == 0:
            self.skipTest("no SHOT blocks found")


if __name__ == "__main__":
    unittest.main()
