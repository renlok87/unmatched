"""ENV-MAPS P9b: tools/art/render/hero_light_metrics.py (gates D1-D6 + H2 of docs/art-pipeline/ENV-HERO-LIGHT.md,
«Ревизия после ревью 2026-10-02») - the synthetic self-test, the thresholds against the doc, the masks / bands helpers and
the committed D6 reference config (zone rectangles inside the reference renders of the detailed Tripo models).

  python -B -m pytest -q tools/art/tests/test_hero_light_metrics.py
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "render"))
import hero_light_metrics as H  # noqa: E402

DOC = REPO / "docs/art-pipeline/ENV-HERO-LIGHT.md"
EVIDENCE = REPO / "docs/game-design/evidence/ENV-MAPS/p9b-hero-light-detail-2026-10-02"


class SelfCheck(unittest.TestCase):
    def test_synthetic_gates(self):
        # an accent passes D1-D4 / H2 / D5 / D6, a flat flood (the P9 failure) fails D1-D4, spill fails H2, x1.35 fails D5
        self.assertEqual(H.self_check(), [])

    def test_cli_check(self):
        self.assertEqual(H.main(["--check"]), 0)


class Thresholds(unittest.TestCase):
    def test_doc_quotes_the_thresholds(self):
        T = H.THRESHOLDS
        self.assertEqual((T["D1"], T["D2"], T["D3pct"], T["D3level"]), (1.0, 0.97, 0.5, 245))
        self.assertEqual((T["D4gain"], T["D4edge"], T["D4band"]), ((0.15, 0.35), 1.15, (2.0, 4.0)))
        self.assertEqual((T["D5"], T["H2out"], T["H2signed"]), ((1.08, 1.2), 0.5, 1.0))
        doc = DOC.read_text(encoding="utf-8")
        for needle in ("≥ 1,0", "≥ 0,97", "≤ 0,5 %", "+15…+35 %", "≥ 1,15", "1,08…1,2", "dABnorm", "-NoHeroLight"):
            self.assertIn(needle, doc, needle)


class Helpers(unittest.TestCase):
    def test_bands(self):
        yy, xx = np.mgrid[0:101, 0:101]
        disc = (xx - 50) ** 2 + (yy - 50) ** 2 <= 30 ** 2
        inner, outer = H.band_inside(disc, 2, 4), H.band_outside(disc, 2, 4)
        r_in = np.hypot(xx[inner] - 50, yy[inner] - 50)
        r_out = np.hypot(xx[outer] - 50, yy[outer] - 50)
        self.assertTrue(25.5 <= r_in.min() and r_in.max() <= 29.0)
        self.assertTrue(31.0 <= r_out.min() and r_out.max() <= 34.5)

    def test_green_mask_ignores_fire(self):
        off = np.full((60, 60, 3), 60.0)
        lit = off.copy()
        lit[10:30, 10:30] += [0, 40, 0]   # a figure under the green mask light
        lit[35:55, 35:55] += [50, 30, 5]  # Niagara fire flicker between runs
        m = H.green_mask(lit, off)
        self.assertTrue(m[12:28, 12:28].all())
        self.assertFalse(m[35:55, 35:55].any())

    def test_lab(self):
        self.assertAlmostEqual(float(H.srgb_to_lab(np.array([255.0, 255, 255]))[0]), 100.0, places=1)
        lab = H.srgb_to_lab(np.array([128.0, 128, 128]))
        self.assertAlmostEqual(float(lab[0]), 53.59, places=1)
        self.assertLess(abs(float(lab[1])) + abs(float(lab[2])), 0.05)


class D6Config(unittest.TestCase):
    def test_reference_config(self):
        cfg_path = EVIDENCE / "d6-config.json"
        if not cfg_path.exists():
            self.skipTest("the P9b evidence is not written yet")
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        from PIL import Image
        for hero, ref in cfg["references"].items():
            img = REPO / ref["image"]
            self.assertTrue(img.exists(), img)
            w, h = Image.open(img).size
            self.assertIn("pedestal", ref["zones"], hero)
            self.assertGreaterEqual(len(ref["zones"]), 3, hero)
            for zone, rects in ref["zones"].items():
                for x0, y0, x1, y1 in rects:
                    self.assertTrue(0 <= x0 < x1 <= w and 0 <= y0 < y1 <= h, (hero, zone))
        for board, views in cfg["figures"].items():
            for view, figs in views.items():
                self.assertEqual(view, "K2x2p5")
                for f in figs:
                    self.assertIn(f["hero"], cfg["references"], (board, f))


if __name__ == "__main__":
    unittest.main()
