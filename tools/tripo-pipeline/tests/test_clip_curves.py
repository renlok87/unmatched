"""Unit tests for anim/clip_curves.py (авторский слой клипов H2Anim, волна 5c): чистый Python, без Blender.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "anim"))
import clip_curves as cc  # noqa: E402


class ChannelTests(unittest.TestCase):
    def test_keys_are_hit_exactly(self):
        keys = [(0, 0.0), (4, 10.0), (8, -5.0), (14, 0.0)]
        for f, v in keys:
            self.assertAlmostEqual(cc.eval_channel(keys, f), v)

    def test_no_overshoot_at_a_local_extremum(self):
        # auto-clamp: the peak key has a zero tangent, the curve never exceeds it between keys
        keys = [(0, 0.0), (5, 10.0), (10, 0.0)]
        vals = [cc.eval_channel(keys, f / 10.0) for f in range(0, 101)]
        self.assertLessEqual(max(vals), 10.0 + 1e-9)
        self.assertGreaterEqual(min(vals), -1e-9)

    def test_monotone_segment_between_monotone_keys(self):
        keys = [(0, 0.0), (4, 2.0), (8, 10.0), (12, 11.0)]
        vals = [cc.eval_channel(keys, f / 4.0) for f in range(0, 49)]
        self.assertEqual(vals, sorted(vals))

    def test_open_clip_holds_outside_the_keys(self):
        keys = [(2, 3.0), (6, 7.0)]
        self.assertEqual(cc.eval_channel(keys, 0), 3.0)
        self.assertEqual(cc.eval_channel(keys, 9), 7.0)
        self.assertEqual(cc.eval_channel([], 3), 0.0)

    def test_loop_is_periodic_and_smooth_across_the_seam(self):
        keys = [(0, 0.0), (14, 4.0), (42, -4.0), (56, 0.0)]
        n = 56
        self.assertAlmostEqual(cc.eval_channel(keys, 0, True, n), cc.eval_channel(keys, n, True, n))
        v_end = cc.eval_channel(keys, n, True, n) - cc.eval_channel(keys, n - 0.01, True, n)
        v_start = cc.eval_channel(keys, 0.01, True, n) - cc.eval_channel(keys, 0, True, n)
        self.assertAlmostEqual(v_end, v_start, places=4)

    def test_loop_needs_a_period(self):
        with self.assertRaises(ValueError):
            cc.eval_channel([(0, 1.0)], 3, loop=True)


class WaveAndBoundaryTests(unittest.TestCase):
    def test_waves_are_zero_at_the_clip_boundaries(self):
        for shape in cc.SHAPES:
            for cycles in (1, 2, 3):
                self.assertAlmostEqual(cc.wave(0, 48, 5.0, cycles, 0.0, shape), 0.0)
                self.assertAlmostEqual(cc.wave(48, 48, 5.0, cycles, 0.0, shape), 0.0)

    def test_raised_cosine_peaks_mid_period(self):
        self.assertAlmostEqual(cc.wave(24, 48, 3.0, 1, 0.0, "raised_cos"), 3.0)

    def test_unknown_wave_shape_is_refused(self):
        with self.assertRaises(ValueError):
            cc.wave(1, 10, 1.0, shape="square")

    def test_boundary_keys_by_role(self):
        axes = [[(5, 1.0)], [(5, 2.0)], [(5, 3.0)]]
        idle = cc.with_boundary(axes, 10, "idle")
        term = cc.with_boundary(axes, 10, "terminal")
        self.assertEqual(idle[0], [(0, 0.0), (5, 1.0), (10, 0.0)])
        self.assertEqual(term[0], [(0, 0.0), (5, 1.0)])  # terminal ends on its final pose
        explicit = cc.with_boundary([[(0, 2.0), (10, 5.0)]], 10, "oneshot")
        self.assertEqual(explicit[0], [(0, 2.0), (10, 5.0)], "explicit boundary keys are kept")

    def test_channels_from_keys(self):
        ch = cc.channels_from_keys([{"f": 3, "bones": {"spine": [1, 2, 3]}}, {"f": 6, "bones": {"spine": [4, 5, 6]}}])
        self.assertEqual(ch["spine"], [[(3, 1.0), (6, 4.0)], [(3, 2.0), (6, 5.0)], [(3, 3.0), (6, 6.0)]])

    def test_weight_curve_smoothstep_and_hold(self):
        keys = [[0, 1.0], [4, 1.0], [6, 0.0], [10, 0.0], [13, 1.0]]
        self.assertEqual(cc.weight_curve(keys, 2), 1.0)
        self.assertAlmostEqual(cc.weight_curve(keys, 5), 0.5)
        self.assertEqual(cc.weight_curve(keys, 8), 0.0)
        self.assertEqual(cc.weight_curve(keys, 20), 1.0)
        self.assertEqual(cc.weight_curve(None, 3), 1.0)


if __name__ == "__main__":
    unittest.main()
