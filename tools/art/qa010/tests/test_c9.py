import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import math
import unittest

import numpy as np

from tests._util import rel_lum, solid
from qa010lib.checks import C9Params, check_c9


def two_layer(game_rgb, decor_rgb, w=100, h=100):
    img = solid(w, h, decor_rgb)
    img[:, : w // 2] = game_rgb
    game = np.zeros((h, w), dtype=bool)
    game[:, : w // 2] = True
    return img, game, ~game


class C9Tests(unittest.TestCase):
    params = C9Params(min_pixels=100)

    def test_known_ev_difference_in_band(self):
        # 2^0.5 in linear light: decode(150)=0.3050, decode(121)=0.1912 -> ~0.674 EV
        g, d = (150, 150, 150), (121, 121, 121)
        img, gm, dm = two_layer(g, d)
        res = check_c9(img, gm, dm, self.params)
        expected = math.log2(rel_lum(g) / rel_lum(d))
        self.assertAlmostEqual(res["delta_ev"]["used"], round(expected, 4), places=4)
        self.assertTrue(0.3 < expected < 0.7)
        self.assertEqual(res["result_normative"], "pass")
        self.assertTrue(res["verdicts"]["ev_range"]["pass"])

    def test_brighter_but_outside_proposed_band(self):
        img, gm, dm = two_layer((200, 200, 200), (60, 60, 60))
        res = check_c9(img, gm, dm, self.params)
        self.assertGreater(res["delta_ev"]["used"], 0.7)
        self.assertEqual(res["result_normative"], "pass")
        self.assertFalse(res["verdicts"]["ev_range"]["pass"])
        self.assertEqual(res["result_proposed"], "fail")

    def test_proxy_mask_gives_no_normative_result(self):
        from qa010lib.layers import proxy_regions
        img, gm, dm = two_layer((200, 200, 200), (60, 60, 60))
        proxies = proxy_regions([("game", "b=trace-cells:all", "trace-cells", False, ""),
                                 ("decor", "decor=trace-ring:0.05,0.35", "trace-ring", True, "ring")])
        self.assertEqual([p["layer"] for p in proxies], ["decor"])
        res = check_c9(img, gm, dm, self.params, proxies=proxies)
        self.assertEqual(res["status"], "measured")                       # numbers are still there
        self.assertEqual((res["result_normative"], res["result_proposed"]), ("proxy", "proxy"))
        self.assertEqual(res["result_on_proxy"]["normative"], "pass")
        self.assertTrue(res["layer_basis"]["proxy"])
        self.assertIn("L3", res["layer_basis"]["reason"])
        plain = check_c9(img, gm, dm, self.params)
        self.assertEqual(plain["result_normative"], "pass")
        self.assertFalse(plain["layer_basis"]["proxy"])
        self.assertNotIn("result_on_proxy", plain)

    def test_darker_game_layer_fails_normative(self):
        img, gm, dm = two_layer((60, 60, 60), (120, 120, 120))
        res = check_c9(img, gm, dm, self.params)
        self.assertLess(res["delta_ev"]["used"], 0)
        self.assertEqual(res["result_normative"], "fail")

    def test_equal_layers_are_not_brighter(self):
        img, gm, dm = two_layer((90, 90, 90), (90, 90, 90))
        res = check_c9(img, gm, dm, self.params)
        self.assertEqual(res["delta_ev"]["used"], 0.0)
        self.assertEqual(res["result_normative"], "fail")

    def test_saturation_verdict(self):
        # brighter but gray game layer vs saturated decor -> "насыщеннее" fails
        img, gm, dm = two_layer((150, 150, 150), (130, 60, 40))
        res = check_c9(img, gm, dm, self.params)
        self.assertEqual(res["result_normative"], "pass")
        self.assertFalse(res["verdicts"]["more_saturated"]["pass"])
        img2, gm2, dm2 = two_layer((200, 120, 60), (110, 110, 118))
        self.assertTrue(check_c9(img2, gm2, dm2, self.params)["verdicts"]["more_saturated"]["pass"])

    def test_decor_cool_info(self):
        img, gm, dm = two_layer((150, 150, 150), (60, 70, 95))
        self.assertTrue(check_c9(img, gm, dm, self.params)["info"]["decor_cool"]["cool"])

    def test_median_statistic_option(self):
        img, gm, dm = two_layer((150, 150, 150), (121, 121, 121))
        img[:5, :50] = 255  # a few bright highlight pixels skew the mean only
        mean = check_c9(img, gm, dm, self.params)["delta_ev"]
        med = check_c9(img, gm, dm, C9Params(min_pixels=100, statistic="median"))
        self.assertGreater(mean["mean"], mean["median"])
        self.assertEqual(med["delta_ev"]["used"], mean["median"])

    def test_overlap_rejected_unless_allowed(self):
        img, gm, dm = two_layer((150, 150, 150), (100, 100, 100))
        dm2 = dm.copy()
        dm2[:, 40:50] = True
        self.assertEqual(check_c9(img, gm, dm2, self.params)["status"], "insufficient_input")
        res = check_c9(img, gm, dm2, C9Params(min_pixels=100, allow_overlap=True))
        self.assertEqual(res["status"], "measured")
        self.assertEqual(res["layers"]["game"]["pixels"], 40 * 100)

    def test_min_pixels(self):
        img, gm, dm = two_layer((150, 150, 150), (100, 100, 100))
        self.assertEqual(check_c9(img, gm, dm, C9Params(min_pixels=10_000))["status"], "insufficient_input")

    def test_exclude_mask_removes_hud(self):
        img, gm, dm = two_layer((150, 150, 150), (100, 100, 100))
        img[:20, 50:] = 255      # bright HUD panel over the decor half
        hud = np.zeros_like(gm)
        hud[:20, 50:] = True
        with_hud = check_c9(img, gm, dm, self.params)
        without = check_c9(img, gm, dm, self.params, exclude=hud)
        self.assertLess(with_hud["delta_ev"]["used"], without["delta_ev"]["used"])
        self.assertAlmostEqual(without["delta_ev"]["used"],
                               round(math.log2(rel_lum((150,) * 3) / rel_lum((100,) * 3)), 4), places=4)

    def test_black_decor_does_not_crash(self):
        img, gm, dm = two_layer((150, 150, 150), (0, 0, 0))
        res = check_c9(img, gm, dm, self.params)
        self.assertEqual(res["result_normative"], "pass")
        self.assertTrue(math.isfinite(res["delta_ev"]["used"]))


if __name__ == "__main__":
    unittest.main()
