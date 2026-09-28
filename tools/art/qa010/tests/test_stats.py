import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import tempfile
import unittest
from pathlib import Path

import numpy as np

from tests._util import EVIDENCE, save_png, solid
from qa010lib.imageio import load_mask, load_rgb
from qa010lib.regions import RegionError, luma_stats, nearest_rank, parse_region


class PercentileTests(unittest.TestCase):
    def test_nearest_rank_floor_rule(self):
        vals = np.arange(100, dtype=np.float64)
        self.assertEqual(nearest_rank(vals, 0.5), 50.0)
        self.assertEqual(nearest_rank(vals, 0.9), 90.0)
        self.assertEqual(nearest_rank(np.array([7.0]), 0.9), 7.0)
        self.assertEqual(nearest_rank(np.arange(10, dtype=float), 1.0), 9.0)

    def test_gray_ramp_stats(self):
        ramp = np.repeat(np.arange(100, dtype=np.uint8)[None, :, None], 3, axis=2)
        st = luma_stats(ramp)
        self.assertEqual(st["pixels"], 100)
        self.assertEqual(st["luma_p50"], 50.0)
        self.assertEqual(st["luma_p90"], 90.0)
        self.assertAlmostEqual(st["luma_mean"], 49.5)
        self.assertEqual(st["dark_under_30_pct"], 30.0)

    def test_stride_samples_grid(self):
        img = np.zeros((8, 8, 3), dtype=np.uint8)
        img[::4, ::4] = 200
        self.assertEqual(luma_stats(img, stride=4)["luma_p50"], 200.0)
        self.assertEqual(luma_stats(img, stride=1)["luma_p50"], 0.0)


class RegionTests(unittest.TestCase):
    def setUp(self):
        self.img = solid(100, 50, (0, 0, 0))
        self.img[:, 50:] = (200, 200, 200)

    def test_bbox_is_half_open(self):
        r = parse_region("right=bbox:50,0,100,50", (100, 50))
        self.assertEqual(int(r.mask.sum()), 50 * 50)
        st = luma_stats(self.img, r.mask)
        self.assertEqual((st["luma_p50"], st["luma_p90"]), (200.0, 200.0))
        left = parse_region("left=bbox:0,0,50,50", (100, 50))
        self.assertEqual(luma_stats(self.img, left.mask)["luma_max"], 0.0)

    def test_bbox_straddling_boundary(self):
        r = parse_region("mid=bbox:40,0,60,10", (100, 50))
        st = luma_stats(self.img, r.mask)
        self.assertEqual(st["pixels"], 200)
        self.assertEqual(st["luma_p50"], 200.0)   # sorted[100] of 100 zeros + 100 x 200
        self.assertEqual(st["luma_mean"], 100.0)

    def test_poly_region(self):
        r = parse_region("tri=poly:0,0;99,0;0,49", (100, 50))
        self.assertTrue(r.mask[0, 0] and not r.mask[49, 99])

    def test_mask_png_gray_and_alpha(self):
        with tempfile.TemporaryDirectory() as d:
            m = np.zeros((50, 100), dtype=np.uint8)
            m[:, 50:] = 255
            p = save_png(Path(d) / "m.png", m)
            r = parse_region(f"m=mask:{p}", (100, 50))
            self.assertEqual(luma_stats(self.img, r.mask)["luma_min"], 200.0)
            rgba = np.zeros((50, 100, 4), dtype=np.uint8)
            rgba[..., :3] = 255          # colour ignored when alpha is informative
            rgba[:, :50, 3] = 255
            pa = save_png(Path(d) / "a.png", rgba)
            mask = load_mask(pa, (100, 50))
            self.assertEqual(int(mask.sum()), 50 * 50)
            self.assertTrue(mask[0, 0] and not mask[0, 99])

    def test_mask_size_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = save_png(Path(d) / "m.png", np.zeros((10, 10), dtype=np.uint8))
            with self.assertRaises(ValueError):
                parse_region(f"m=mask:{p}", (100, 50))

    def test_bad_specs(self):
        for spec in ("nokind", "x=bbox:1,2,3", "x=bbox:200,0,300,10", "x=unknown:1", "x=trace-cells:all"):
            with self.assertRaises((RegionError, ValueError)):
                parse_region(spec, (100, 50))

    def test_alpha_is_ignored_on_load(self):
        with tempfile.TemporaryDirectory() as d:
            rgba = np.zeros((4, 4, 4), dtype=np.uint8)
            rgba[..., :3] = (10, 20, 30)
            rgba[..., 3] = 0   # UE screenshots may carry alpha=0 on opaque pixels
            p = save_png(Path(d) / "f.png", rgba)
            self.assertEqual(tuple(load_rgb(p)[0, 0]), (10, 20, 30))


S05_FRAMES = EVIDENCE / "S05" / "art-references" / "frames"


@unittest.skipUnless((S05_FRAMES / "frame-K1-overview.png").exists(), "S05 evidence frames not present")
class S05RegressionTests(unittest.TestCase):
    """Real-data regression: reproduce tools/s05/s05_frame_measure.ps1 numbers
    published in frame-measurements.json (stride 4 grid, Rec.709 luma)."""

    EXPECTED = {
        "frame-K1-overview.png": (101.9, 61.0, 204.1, 3.61, 30.81),
        "frame-K2-closeup.png": (136.0, 167.7, 180.3, 7.38, 65.93),
        "frame-K3-combat.png": (105.1, 79.5, 204.7, 3.61, 30.23),
    }

    def test_reproduces_s05_measurements(self):
        for name, (mean, p50, p90, dark, bright) in self.EXPECTED.items():
            st = luma_stats(load_rgb(S05_FRAMES / name), stride=4)
            self.assertEqual(round(st["luma_mean"], 1), mean, name)
            self.assertEqual(round(st["luma_p50"], 1), p50, name)
            self.assertEqual(round(st["luma_p90"], 1), p90, name)
            self.assertEqual(round(st["dark_under_30_pct"], 2), dark, name)
            self.assertEqual(round(st["bright_over_150_pct"], 2), bright, name)


if __name__ == "__main__":
    unittest.main()
