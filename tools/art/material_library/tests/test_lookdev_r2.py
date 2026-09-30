"""Tests of look-dev round 2 (2026-09-30): zone render regions of ue_hero_lookdev.py (figure-relative screen boxes
that mirror the concept boxes), the concept backdrop exclusion of ue_hero_concept_zones.py and the multi-zone forecast
of lookdev_r2.py (the pixels of each edited zone x its ratio, nothing else moves).

  python -m unittest discover -s tools/art/material_library/tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import ue_bc_feedback as F  # noqa: E402
import ue_hero_concept_zones as CZ  # noqa: E402
import ue_hero_lookdev as U  # noqa: E402


def figure(h=100, w=200):
    """class map: -1 background, a 'figure' of class 12 spanning x 20..179, y 10..89."""
    cls = np.full((h, w), -1, np.int16)
    cls[10:90, 20:180] = 12
    return cls


class ZoneRegionTest(unittest.TestCase):
    def test_no_region_is_none(self):
        self.assertIsNone(U.zone_region({}, "dark", "front", figure()))
        self.assertIsNone(U.zone_region({"render_regions": {"orange": {"x_outer": [0, 1]}}}, "dark", "front", figure()))

    def test_view_not_listed_is_empty(self):
        cfg = {"render_regions": {"dark": {"views": ["front", "back"], "x_outer": [0.5, 1.0]}}}
        self.assertFalse(U.zone_region(cfg, "dark", "side", figure()).any())

    def test_outer_x_is_symmetric_about_the_figure_centre(self):
        cfg = {"render_regions": {"dark": {"x_outer": [0.5, 1.0], "y": [0.0, 1.0]}}}
        m = U.zone_region(cfg, "dark", "front", figure())
        cols = np.nonzero(m.any(0))[0]
        # centre 99.5, half-width 79.5: |x - 99.5| >= 39.75 -> x <= 59 or x >= 140, and within the figure x 20..179
        self.assertEqual(int(cols.min()), 20)
        self.assertEqual(int(cols.max()), 179)
        self.assertFalse(m[:, 60:140].any())
        self.assertTrue(m[50, 59] and m[50, 140])

    def test_y_is_relative_to_the_figure_extent(self):
        cfg = {"render_regions": {"z": {"y": [0.0, 0.5]}}}
        m = U.zone_region(cfg, "z", "front", figure())
        rows = np.nonzero(m.any(1))[0]
        self.assertEqual(int(rows.min()), 10)      # (y - 10) / 79 >= 0 -> y >= 10 (figure top)
        self.assertEqual(int(rows.max()), 49)      # (y - 10) / 79 <= 0.5 -> y <= 49


class ConceptExcludeTest(unittest.TestCase):
    def test_backdrop_hue_is_excluded_and_warm_dark_kept(self):
        backdrop = np.array([[[49, 50, 52]]], np.uint8)      # grey-blue studio backdrop (hue ~220)
        feather = np.array([[[46, 39, 37]]], np.uint8)       # dark primary (hue ~13)
        flt = {"hue": [185, 265]}
        self.assertTrue(bool(CZ.filter_mask(backdrop, flt)[0, 0]))
        self.assertFalse(bool(CZ.filter_mask(feather, flt)[0, 0]))


class ForecastTest(unittest.TestCase):
    def test_apply_ratio_on_linear_light(self):
        px = np.array([[[128, 64, 32]]], np.uint8)
        out = F.apply_ratio(px, np.ones((1, 1), bool), [1.0, 1.0, 1.0])
        np.testing.assert_array_equal(out, px)
        out = F.apply_ratio(px, np.ones((1, 1), bool), [0.5, 0.5, 0.5])
        lin_in = U.lin(px.astype(np.float64) / 255.0)
        lin_out = U.lin(out.astype(np.float64) / 255.0)
        np.testing.assert_allclose(lin_out, lin_in * 0.5, rtol=0.03, atol=2e-4)


if __name__ == "__main__":
    unittest.main()
