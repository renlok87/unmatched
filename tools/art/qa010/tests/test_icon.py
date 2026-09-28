import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import unittest

import numpy as np

from tests._util import rel_lum, solid
from qa010lib.checks import IconParams, check_icon, otsu_threshold


def plus_icon(fg, bg, size=96, stroke=24, frame=(200, 200), at=(50, 50)):
    img = solid(frame[0], frame[1], bg)
    x, y = at
    c = size // 2
    img[y + c - stroke // 2: y + c + stroke // 2, x: x + size] = fg
    img[y: y + size, x + c - stroke // 2: x + c + stroke // 2] = fg
    return img, (x, y, x + size, y + size)


class IconContrastTests(unittest.TestCase):
    def test_white_on_black_is_21_to_1_at_all_sizes(self):
        img, bb = plus_icon((255, 255, 255), (0, 0, 0))
        res = check_icon(img, bb, IconParams())
        self.assertEqual(res["result"], "pass")
        self.assertEqual([s["size_px"] for s in res["sizes"]], [24, 32, 48])
        for s in res["sizes"]:
            self.assertAlmostEqual(s["contrast_ratio"], 21.0, places=2)
            self.assertAlmostEqual(s["luma_delta"], 255.0, places=1)
            self.assertFalse(s["upscaled"])
        self.assertEqual(res["foreground"]["foreground"], "bright")

    def test_known_mid_contrast(self):
        fg, bg = (200, 200, 200), (60, 60, 60)
        img, bb = plus_icon(fg, bg)
        expected = (rel_lum(fg) + 0.05) / (rel_lum(bg) + 0.05)
        res = check_icon(img, bb, IconParams())
        for s in res["sizes"]:
            self.assertAlmostEqual(s["contrast_ratio"], expected, places=2)

    def test_low_contrast_fails(self):
        img, bb = plus_icon((120, 120, 120), (110, 110, 110))
        res = check_icon(img, bb, IconParams())
        self.assertEqual(res["result"], "fail")
        self.assertLess(res["sizes"][0]["contrast_ratio"], 1.3)
        self.assertIn("contrast", res["sizes"][0]["reason"])

    def test_red_on_green_isoluminant_fails_despite_hue(self):
        # colour difference alone is not contrast (WCAG luminance based)
        img, bb = plus_icon((200, 60, 60), (60, 105, 60))
        res = check_icon(img, bb, IconParams())
        self.assertEqual(res["result"], "fail")

    def test_thin_strokes_collapse_at_24px(self):
        img, bb = plus_icon((255, 255, 255), (0, 0, 0), size=96, stroke=2)
        res = check_icon(img, bb, IconParams())
        s24 = res["sizes"][0]
        self.assertEqual(s24["size_px"], 24)
        self.assertFalse(s24["pass"])
        self.assertEqual(s24["fg_pixels"], 0)
        self.assertIn("collapses", s24["reason"])
        self.assertEqual(res["result"], "fail")

    def test_dark_icon_on_light_background(self):
        img, bb = plus_icon((20, 20, 20), (230, 230, 230))
        res = check_icon(img, bb, IconParams())
        self.assertEqual(res["foreground"]["foreground"], "dark")
        self.assertEqual(res["result"], "pass")
        self.assertLess(res["sizes"][0]["luma_delta"], 0)

    def test_explicit_mask_matches_auto_on_clean_icon(self):
        img, bb = plus_icon((230, 230, 230), (40, 40, 40))
        mask = np.all(img == (230, 230, 230), axis=-1)
        a = check_icon(img, bb, IconParams())
        m = check_icon(img, bb, IconParams(), fg_mask=mask)
        self.assertEqual(m["foreground"]["method"], "mask")
        for sa, sm in zip(a["sizes"], m["sizes"]):
            self.assertAlmostEqual(sa["contrast_ratio"], sm["contrast_ratio"], places=3)
            self.assertEqual(sa["fg_pixels"], sm["fg_pixels"])
        # bbox-sized mask is accepted too
        x0, y0, x1, y1 = bb
        mb = check_icon(img, bb, IconParams(), fg_mask=mask[y0:y1, x0:x1])
        self.assertEqual(mb["sizes"][0]["fg_pixels"], m["sizes"][0]["fg_pixels"])

    def test_bad_mask_shape(self):
        img, bb = plus_icon((230, 230, 230), (40, 40, 40))
        self.assertEqual(check_icon(img, bb, IconParams(), fg_mask=np.ones((3, 3), bool))["status"],
                         "insufficient_input")

    def test_small_icon_is_flagged_upscaled(self):
        img, bb = plus_icon((255, 255, 255), (0, 0, 0), size=36, stroke=8)
        res = check_icon(img, bb, IconParams())
        flags = {s["size_px"]: s["upscaled"] for s in res["sizes"]}
        self.assertEqual(flags, {24: False, 32: False, 48: True})

    def test_uniform_bbox_has_no_icon(self):
        img = solid(100, 100, (80, 80, 80))
        res = check_icon(img, (30, 30, 70, 70), IconParams())
        self.assertEqual(res["result"], "fail")
        self.assertIsNone(res["foreground"]["threshold"])

    def test_min_luma_delta_gate(self):
        img, bb = plus_icon((200, 200, 200), (60, 60, 60))
        self.assertEqual(check_icon(img, bb, IconParams(min_luma_delta=200))["result"], "fail")
        self.assertEqual(check_icon(img, bb, IconParams(min_luma_delta=50))["result"], "pass")

    def test_reversed_bbox_is_normalized(self):
        img, (x0, y0, x1, y1) = plus_icon((255, 255, 255), (0, 0, 0))
        a = check_icon(img, (x0, y0, x1, y1), IconParams())
        b = check_icon(img, (x1, y1, x0, y0), IconParams())
        self.assertEqual(a["bbox"], b["bbox"])
        self.assertEqual(b["result"], "pass")

    def test_empty_bbox(self):
        img = solid(50, 50, (0, 0, 0))
        self.assertEqual(check_icon(img, (60, 60, 80, 80), IconParams())["status"], "insufficient_input")

    def test_otsu(self):
        vals = np.array([10] * 50 + [200] * 50, dtype=float)
        t = otsu_threshold(vals)
        self.assertTrue(10 <= t < 200)
        self.assertIsNone(otsu_threshold(np.full(10, 7.0)))

    def test_otsu_float_luma_of_gray_levels(self):
        # regression: float luma of gray 20 is 19.999...; histogram and split must agree
        from qa010lib import color
        px = np.array([[20, 20, 20]] * 30 + [[230, 230, 230]] * 70, dtype=np.uint8)
        y = color.luma_u8(px)
        t = otsu_threshold(y)
        from qa010lib.checks import luma_levels
        lv = luma_levels(y)
        self.assertEqual(int((lv <= t).sum()), 30)
        self.assertEqual(int((lv > t).sum()), 70)


if __name__ == "__main__":
    unittest.main()
