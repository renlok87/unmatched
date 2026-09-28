import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import unittest

from tests._util import FIXTURE_TRACE, topdown_cell_rect, topdown_trace
from qa010lib.plate import PlateParams, check_plate
from qa010lib.projection import build_projection
from qa010lib.trace import parse_trace, parse_trace_text


def run(shot, **kw):
    proj = build_projection(shot, 35.0, 2.0, "auto")
    return check_plate(shot, proj, kw.pop("params", PlateParams()), **kw)


class TopDownPlateTests(unittest.TestCase):
    """Camera straight down: cells are axis-aligned rectangles with exactly
    known screen coordinates, so overlap areas are hand-computable."""

    def test_half_cell_overlap_exact(self):
        x0, y0, x1, y1 = topdown_cell_rect(1, 1)
        plate = (x0, y0, (x0 + x1) / 2, y1)            # left half of cell (1,1)
        s = parse_trace_text(topdown_trace(plate=plate, reachable=[(1, 1), (2, 2)])).shots[0]
        res = run(s)
        self.assertEqual(res["status"], "measured")
        self.assertEqual(res["result"], "fail")
        v = res["violations"][0]
        self.assertEqual(v["cell"], [1, 1])
        self.assertAlmostEqual(v["overlap_fraction"], 0.5, places=3)
        self.assertAlmostEqual(v["overlap_px2"], (x1 - x0) / 2 * (y1 - y0), places=1)

    def test_plate_on_non_selection_cell_passes(self):
        x0, y0, x1, y1 = topdown_cell_rect(0, 1)
        plate = (x0 + 5, y0 + 5, x1 - 5, y1 - 5)
        s = parse_trace_text(topdown_trace(plate=plate, reachable=[(1, 1), (2, 2)])).shots[0]
        res = run(s)
        self.assertEqual(res["result"], "pass")
        self.assertEqual(res["overlapped_non_selection_cells"], [[0, 1]])

    def test_edge_touch_is_not_overlap(self):
        x0, y0, x1, y1 = topdown_cell_rect(0, 1)
        plate = (x0, y0, x1, y1)                      # exactly cell (0,1); (1,1) shares an edge
        s = parse_trace_text(topdown_trace(plate=plate, reachable=[(1, 1)])).shots[0]
        self.assertEqual(run(s)["result"], "pass")

    def test_tolerance_parameter(self):
        x0, y0, x1, y1 = topdown_cell_rect(1, 1)
        plate = (x0, y0, x0 + (x1 - x0) * 0.1, y1)   # 10 % of the cell
        s = parse_trace_text(topdown_trace(plate=plate, reachable=[(1, 1)])).shots[0]
        self.assertEqual(run(s)["result"], "fail")
        self.assertEqual(run(s, params=PlateParams(max_overlap_fraction=0.15))["result"], "pass")

    def test_all_cells_mode_is_stricter(self):
        x0, y0, x1, y1 = topdown_cell_rect(0, 1)
        plate = (x0 + 5, y0 + 5, x1 - 5, y1 - 5)
        s = parse_trace_text(topdown_trace(plate=plate, reachable=[(1, 1)])).shots[0]
        self.assertEqual(run(s, params=PlateParams(cells="all"))["result"], "fail")

    def test_cli_overrides(self):
        s = parse_trace_text(topdown_trace()).shots[0]   # no new lines at all
        self.assertEqual(run(s)["status"], "requires_new_trace")
        x0, y0, x1, y1 = topdown_cell_rect(2, 2)
        res = run(s, plate_bbox=(x0, y0, x1, y1), reachable=[(2, 2)])
        self.assertEqual(res["result"], "fail")
        self.assertEqual(res["plate"]["source"], "cli")


    def test_nothing_checked_is_insufficient(self):
        x0, y0, x1, y1 = topdown_cell_rect(1, 1)
        s = parse_trace_text(topdown_trace(plate=(x0, y0, x1, y1), reachable=[(2, 2)])).shots[0]
        self.assertEqual(run(s)["status"], "measured")
        empty = run(s, reachable=[])                                  # empty selection
        self.assertEqual(empty["status"], "insufficient_input")
        self.assertNotIn("result", empty)
        self.assertIn("empty reachable", empty["reason"])
        off = run(s, plate_bbox=(3000, 3000, 3100, 3050))             # plate off-screen
        self.assertEqual(off["status"], "insufficient_input")
        self.assertEqual(off["plate"]["visible_area_px2"], 0.0)
        self.assertIn("outside", off["reason"])
        zero = run(s, plate_bbox=(0, 0, 0, 0))                        # collapsed UMG widget
        self.assertEqual(zero["status"], "insufficient_input")
        self.assertIn("zero area", zero["reason"])
        both = run(s, plate_bbox=(0, 0, 0, 0), reachable=[])          # every reason is reported
        self.assertIn("empty reachable", both["reason"])
        self.assertIn("zero area", both["reason"])

    def test_all_checked_cells_offscreen_is_insufficient(self):
        # camera 200 uu above the board: a cell is ~1522 px, corner cells leave the viewport
        s = parse_trace_text(topdown_trace(plate=(900, 500, 1000, 560), reachable=[(0, 0)], cam_z=200.0)).shots[0]
        res = run(s)
        self.assertEqual(res["status"], "insufficient_input", res.get("reason"))
        self.assertEqual(res["checked_cells"]["visible"], 0)
        self.assertEqual(res["checked_cells"]["offscreen"], [[0, 0]])
        # one visible cell is enough to measure; the off-screen one is reported, not hidden
        res = run(s, reachable=[(0, 0), (1, 1)])
        self.assertEqual(res["status"], "measured")
        self.assertEqual(res["checked_cells"]["offscreen"], [[0, 0]])
        self.assertTrue(any("not checked" in i for i in res["issues"]))

    def test_partly_offscreen_plate_is_noted(self):
        s = parse_trace_text(topdown_trace(plate=(-50, -50, 10, 10), reachable=[(2, 2)])).shots[0]
        res = run(s)
        self.assertEqual(res["status"], "measured")
        self.assertEqual(res["plate"]["visible_area_px2"], 100.0)
        self.assertTrue(any("partly outside" in i for i in res["issues"]))


class FixturePlateTests(unittest.TestCase):
    def setUp(self):
        self.t = parse_trace(FIXTURE_TRACE)

    def test_clear(self):
        res = run(self.t.find_shot("k2-plate-clear.png"))
        self.assertEqual((res["status"], res["result"]), ("measured", "pass"))
        self.assertEqual(res["overlapped_non_selection_cells"], [[2, 1]])  # own helper's cell: allowed
        self.assertTrue(res["client_cross_check"]["agree"])
        self.assertEqual(res["checked_cells"]["count"], 14)

    def test_overlap(self):
        res = run(self.t.find_shot("k2-plate-overlap.png"))
        self.assertEqual(res["result"], "fail")
        self.assertEqual([v["cell"] for v in res["violations"]], [[3, 1]])
        # slanted left edge of cell (3,1): hand integration gives ~5623.8 px^2
        self.assertAlmostEqual(res["violations"][0]["overlap_px2"], 5623.8, delta=1.0)
        self.assertTrue(res["client_cross_check"]["agree"])

    def test_client_mismatch_fails(self):
        res = run(self.t.find_shot("k2-plate-client-mismatch.png"))
        self.assertEqual(res["result"], "fail")
        self.assertFalse(res["client_cross_check"]["agree"])

    def test_missing_lines_require_new_trace(self):
        res = run(self.t.find_shot("k2-plate-missing.png"))
        self.assertEqual(res["status"], "requires_new_trace")
        self.assertIn("plate", res["required_lines"])
        self.assertIn("reachable", res["required_lines"])
        self.assertEqual(res["existing_hint"]["existing_selection_line"]["reachable_count"], 14)

    def test_uninitialised_camera_is_insufficient(self):
        res = run(self.t.find_shot("k2-plate-camera-uninitialised.png"))
        self.assertEqual(res["status"], "insufficient_input")

    def test_nothing_checked_cases_never_pass(self):
        cases = {"k2-plate-reachable-empty.png": "empty reachable",
                 "k2-plate-offscreen-bbox.png": "outside the 1920x1080 viewport",
                 "k2-plate-zero-bbox.png": "zero area",
                 "k2-plate-cells-offscreen.png": "all 3 checked cells"}
        for shot, why in cases.items():
            res = run(self.t.find_shot(shot))
            self.assertEqual(res["status"], "insufficient_input", shot)
            self.assertNotIn("result", res, shot)
            self.assertIn(why, res["reason"], shot)
            self.assertIn("не pass", res["reason"], shot)
        # the zero-size widget case: the client's own count agrees (0), so only the guard catches it
        zero = self.t.find_shot("k2-plate-zero-bbox.png")
        self.assertEqual(zero.plate.value["overlap_reachable"], 0)

    def test_reachable_outside_board(self):
        res = run(self.t.find_shot("k2-plate-clear.png"), reachable=[(9, 9)])
        self.assertEqual(res["status"], "insufficient_input")


if __name__ == "__main__":
    unittest.main()
