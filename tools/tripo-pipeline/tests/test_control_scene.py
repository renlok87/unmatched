"""Unit tests for the P1.7 control scene review fixes (stage 3, T3.1 review, 2026-09-29): decor stands on the surface
under it (no hard-coded z), the decor support check and the base see-through count of the board-hidden frames.

No editor and no Blender: review/control_scene.py is imported for its scene spec only (nothing connects at import),
review/control_scene_analyze.py for its pure helpers.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import importlib.util
import json
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


class TeamContrastTest(unittest.TestCase):
    """W4-B review fix: figure / base split of the team comparison, noise pair, inputs export and recompute."""

    @staticmethod
    def write_run(root, tag, figure_team_rgb, base_team_rgb, noise=0):
        from PIL import Image
        run = root / tag
        run.mkdir(parents=True)
        h, w = 120, 160
        board = np.full((h, w, 3), 60, np.uint8)
        fig = np.zeros((h, w), bool)
        fig[20:80, 70:90] = True                          # figure
        base = np.zeros((h, w), bool)
        base[80:95, 55:105] = True                        # base below it

        def frame(fig_rgb, base_rgb, show_fig=True, show_base=True):
            a = board.copy()
            if show_base:
                a[base] = base_rgb
            if show_fig:
                a[fig] = fig_rgb
            if noise:
                a[5, 5] = (a[5, 5].astype(int) + noise) % 255
            return a

        save = lambda name, a: Image.fromarray(a).save(run / ("p17-%s-ue-editor.png" % name))  # noqa: E731
        save("mask-k2-1p6-merlin", frame((200, 200, 200), (120, 120, 120)))
        save("mask-k2-1p6-empty-merlin", board)
        save("mask-k2-1p6-base-merlin", frame((0, 0, 0), (120, 120, 120), show_fig=False))
        save("k2-1p6-merlin", frame((90, 80, 40), (200, 160, 60)))                    # Gold
        save("team-alt-k2-1p6-merlin", frame(figure_team_rgb, base_team_rgb))         # Silver
        (run / "control-scene-report.json").write_text(json.dumps({"tag": tag, "asset_set": "w4b"}), encoding="utf-8")
        return run

    def test_regions_noise_and_inputs_round_trip(self):
        import tempfile
        tc = load("team_contrast")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trim_only = self.write_run(root, "trim", (90, 80, 40), (100, 150, 190))   # only the base changes team
            robe = self.write_run(root, "robe", (40, 70, 110), (100, 150, 190))
            robe2 = self.write_run(root, "robe2", (40, 70, 110), (100, 150, 190), noise=3)
            runs = [tc.load_run(p) for p in (trim_only, robe, robe2)]
            res = {r["meta"]["tag"]: tc.analyse(r) for r in runs}
            trim = res["trim"]["subjects"]["merlin"]["c11_pair"]
            self.assertEqual(trim["regions"]["figure"]["grey"]["mean_abs_dY"], 0.0, "unchanged figure")
            self.assertGreater(trim["grey"]["mean_abs_dY"], 0.0, "the silhouette mean hides it")
            self.assertEqual(trim["base_share_of_sum"]["deuteranopia_dE76"], 1.0)
            robe_fig = res["robe"]["subjects"]["merlin"]["c11_pair"]["regions"]["figure"]
            self.assertGreater(robe_fig["deuteranopia"]["mean_dE76"], 5.0)
            self.assertEqual(res["robe"]["subjects"]["merlin"]["split_source"], "own base-only frame")
            noise = tc.noise_floor(runs[1], runs[2])["subjects"]["merlin"]["main"]
            self.assertEqual(noise["grey"]["mean_abs_dY"], 0.0, "pixel (5,5) is outside the silhouette")
            inputs = root / "inputs"
            tc.write_inputs(inputs, runs, ["robe", "robe2"])
            again, noise_tags = tc.load_inputs(inputs)
            self.assertEqual(noise_tags, ["robe", "robe2"])
            for before, after in zip(runs, again):
                a, b = tc.analyse(before), tc.analyse(after)
                for e in (a, b):
                    e.pop("run", None), e.pop("inputs", None)
                    for s in e["subjects"].values():
                        s.pop("crop_box_px", None)
                self.assertEqual(a, b, "numbers from the committed crops = numbers from the full frames")


if __name__ == "__main__":
    unittest.main()
