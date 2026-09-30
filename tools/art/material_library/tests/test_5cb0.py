"""Tests of the 5c-B0 tools: ue_bc_feedback.py (BC gain through the v2 dielectric clamp, pixel ratio) and
tools/tripo-pipeline/blender/h2_bake_arthur/lookdev_accent_mips.py (TeamAccent through the mip chain).

  python -m unittest discover -s tools/art/material_library/tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(REPO / "tools" / "tripo-pipeline" / "blender" / "h2_bake_arthur"))

import lookdev_accent_mips as AM  # noqa: E402
import ue_bc_feedback as F  # noqa: E402


class AccentMipsTest(unittest.TestCase):
    def test_kaiser_kernel_normalised_and_symmetric(self):
        k = AM.kaiser_kernel()
        self.assertAlmostEqual(float(k.sum()), 1.0, places=9)
        np.testing.assert_allclose(k, k[::-1])

    def test_box_chain_keeps_the_mean(self):
        x = np.random.default_rng(1).random((64, 64))
        for lv in AM.chain(x, 4, "box"):
            self.assertAlmostEqual(float(lv.mean()), float(x.mean()), places=9)

    def test_sample_at_level_0_is_identity(self):
        x = np.random.default_rng(2).random((32, 32))
        np.testing.assert_array_equal(AM.sample_at(x, 32), x)

    def test_gap_keeps_the_border_clean_where_a_touching_strip_paints_it(self):
        """A 64-texel border (class B) with the accent either inside it (rev. 2 style) or as a piping 4 texels away."""
        n = 256
        border = np.zeros((n, n), bool)
        border[:, 96:160] = True
        inside = np.zeros((n, n))
        inside[:, 96:160:2] = 1.0            # red between threads dyed: every second column of the border
        piping = np.zeros((n, n))
        piping[:, 164:180] = 1.0             # 4 texels gap, 16 wide, outside the border
        w = np.ones((n, n))
        a = AM.painted_shares(inside, {"border": border}, w, levels=3, kinds=("box",))["box"]
        b = AM.painted_shares(piping, {"border": border}, w, levels=3, kinds=("box",))["box"]
        self.assertAlmostEqual(a[0]["border"], 0.5, places=3)            # the texels: every second column
        self.assertGreater(min(r["border"] for r in a[1:]), 0.9)         # the mips: the whole border
        self.assertLess(max(r["border"] for r in b[:3]), 0.15)

    def test_visible_mips_of_the_k2_cameras(self):
        v = AM.visible_mips(0.000721, 788.8, 55.0)
        self.assertAlmostEqual(v["mip_facing"], 0.81, places=2)
        self.assertGreater(v["mip_vertical_no_aniso"], v["mip_facing"])


class FeedbackTest(unittest.TestCase):
    def test_effective_keeps_chroma_and_clamps_luminance(self):
        bc = np.array([[0.05, 0.02, 0.01], [0.3, 0.2, 0.1]])
        e = F.effective(bc, 0.08, 0.45, 0.9)
        self.assertAlmostEqual(float(e[0] @ F.LUMA), 0.08, places=6)
        np.testing.assert_allclose(e[0] / e[0].sum(), bc[0] / bc[0].sum(), rtol=1e-9)
        np.testing.assert_allclose(e[1], bc[1])

    def test_solve_gain_reaches_the_ratio_through_the_floor(self):
        rng = np.random.default_rng(3)
        bc = np.stack([rng.uniform(0.05, 0.2, 5000), rng.uniform(0.02, 0.08, 5000), rng.uniform(0.01, 0.05, 5000)], -1)
        r = [0.99, 1.3, 1.8]
        g, got = F.solve_gain(bc, r, 0.08, 0.45, 0.9)
        np.testing.assert_allclose(got, r, rtol=2e-3)
        self.assertTrue(np.all(g >= np.asarray(r) * 0.99))   # the floor makes the gain at least the ratio

    def test_apply_ratio_one_is_identity(self):
        img = (np.random.default_rng(4).random((8, 8, 3)) * 255).astype(np.uint8)
        sel = np.ones((8, 8), bool)
        np.testing.assert_array_equal(F.apply_ratio(img, sel, [1.0, 1.0, 1.0]), img)


if __name__ == "__main__":
    unittest.main()
