"""Unit tests for the P1.7 control scene review fixes (stage 3, T3.1 review, 2026-09-29): decor stands on the surface
under it (no hard-coded z), the decor support check and the base see-through count of the board-hidden frames.

No editor and no Blender: review/control_scene.py is imported for its scene spec only (nothing connects at import),
review/control_scene_analyze.py for its pure helpers.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

REVIEW = Path(__file__).resolve().parents[1] / "review"


def load(name):
    sys.path.insert(0, str(REVIEW))
    try:
        spec = importlib.util.spec_from_file_location(name, REVIEW / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(REVIEW))


cs = load("control_scene")
an = load("control_scene_analyze")


class SceneSpecTest(unittest.TestCase):
    def test_decor_is_placed_on_the_surface_not_at_a_fixed_z(self):
        spec = cs.scene_spec(cs.BARREL)
        decor = [a for a in spec["actors"] if a["label"] == "P17 barrel"]
        self.assertEqual(len(decor), 1)
        self.assertIsNone(decor[0]["location"][2], "decor z must come from the surface under it (rim top 5 uu)")
        self.assertEqual(decor[0]["place_on_surface"]["exclude_label_prefixes"], ["P17 "])

    def test_figures_stand_on_board_cells(self):
        spec = cs.scene_spec(cs.BARREL)
        for a in spec["actors"]:
            if a["label"] == "P17 barrel":
                continue
            self.assertEqual(a["location"][2], 0.0, a["label"])
            self.assertNotIn("place_on_surface", a)

    def test_every_figure_gets_base_see_through_masks(self):
        self.assertEqual(sorted(cs.FIGURES), sorted(k for k in cs.SUBJECTS if k != "barrel"))
        self.assertEqual(cs.BOARD_PREFIX, "ART005")


class DecorSupportTest(unittest.TestCase):
    @staticmethod
    def build(bottom_z, support=5.0, spread=0.0):
        return {"actors": {"P17 barrel": {"location": [264.0, -200.0, bottom_z], "world_bounds": {
                    "min": [253.3, -210.7, bottom_z], "max": [274.7, -189.3, bottom_z + 26.0]}}},
                "decor_support": {"P17 barrel": {"support_z_max_uu": support, "support_z_min_uu": support - spread,
                                                 "spread_uu": spread, "samples": 256,
                                                 "supports": [{"label": "ART005 Decorative Board - NoCollision"}]}}}

    def test_barrel_on_the_rim_top_passes(self):
        d = an.decor_support(self.build(5.0))["barrel"]
        self.assertTrue(d["on_surface"])
        self.assertEqual(d["sunk_into_support_uu"], 0.0)

    def test_barrel_at_z0_inside_the_rim_fails(self):
        d = an.decor_support(self.build(0.0))["barrel"]
        self.assertFalse(d["on_surface"])
        self.assertEqual(d["sunk_into_support_uu"], 5.0)

    def test_uneven_support_fails(self):
        self.assertFalse(an.decor_support(self.build(5.0, spread=2.0))["barrel"]["on_surface"])

    def test_no_decor(self):
        self.assertEqual(an.decor_support({"actors": {}}), {})


class VoidHolesTest(unittest.TestCase):
    def test_holes_counted_and_figure_cover_removed(self):
        h, w = 40, 60
        disc = np.zeros((h, w), bool)
        disc[10:30, 10:50] = True                      # 800 px
        empty = np.zeros((h, w, 3))
        base = np.full((h, w, 3), 90.0)
        base[12:16, 12:22] = 0.0                       # hole A: 40 px
        base[20:25, 30:40] = 0.0                       # hole B: 50 px
        figure = base.copy()
        figure[12:16, 12:22] = 120.0                   # the figure covers hole A
        out = an.void_holes(disc, 100.0, empty, base, figure)
        self.assertTrue(out["void_empty_ok"])
        self.assertEqual(out["base_only"]["void_px"], 90)
        self.assertEqual(out["with_figure"]["void_px"], 50)
        self.assertAlmostEqual(out["base_only"]["area_uu2_est"], 100.0 * 90 / 800, places=2)

    def test_black_figure_pixels_outside_holes_do_not_count(self):
        disc = np.ones((10, 10), bool)
        base = np.full((10, 10, 3), 80.0)
        figure = base.copy()
        figure[0:5, 0:5] = 0.0                         # shadowed figure without bounce light renders black
        out = an.void_holes(disc, 1.0, np.zeros((10, 10, 3)), base, figure)
        self.assertEqual(out["base_only"]["void_px"], 0)
        self.assertEqual(out["with_figure"]["void_px"], 0)

    def test_something_visible_in_the_empty_frame_is_flagged(self):
        disc = np.ones((10, 10), bool)
        empty = np.zeros((10, 10, 3))
        empty[0, 0] = 200.0
        out = an.void_holes(disc, 1.0, empty, empty, empty)
        self.assertFalse(out["void_empty_ok"])


if __name__ == "__main__":
    unittest.main()
