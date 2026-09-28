import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # qa010 dir, any discovery root

import unittest

import numpy as np

from tests._util import rel_lum
from qa010lib import color


class SrgbTransferTests(unittest.TestCase):
    def test_roundtrip_all_8bit_levels(self):
        levels = np.arange(256, dtype=np.uint8)
        back = color.quantize_u8(color.linear_to_srgb(color.srgb_to_linear(levels / 255.0)))
        np.testing.assert_array_equal(back, levels)

    def test_known_decode_values(self):
        self.assertAlmostEqual(float(color.srgb_to_linear(0.5)), 0.214041, places=6)
        self.assertEqual(float(color.srgb_to_linear(0.0)), 0.0)
        self.assertAlmostEqual(float(color.srgb_to_linear(1.0)), 1.0, places=12)

    def test_flinearcolor_trap(self):
        # ue-pipeline-traps #9: FLinearColor(1,.25,.25) is linear -> (255,137,137) on screen
        self.assertEqual(color.expected_srgb_bytes_from_linear(1.0, 0.25, 0.25), (255, 137, 137))
        # FLinearColor(FColor(255,64,64)) decodes sRGB first -> the same bytes come back
        lin = color.srgb_to_linear(np.array([255, 64, 64]) / 255.0)
        self.assertEqual(color.expected_srgb_bytes_from_linear(*lin), (255, 64, 64))
        self.assertNotEqual(color.expected_srgb_bytes_from_linear(1.0, 64 / 255, 64 / 255), (255, 64, 64))


class LumaAndGrayTests(unittest.TestCase):
    def test_rec709_luma_primaries(self):
        px = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255], [255, 255, 255]], dtype=np.uint8)
        np.testing.assert_allclose(color.luma_u8(px), [54.213, 182.376, 18.411, 255.0], atol=1e-9)

    def test_grayscale_values(self):
        px = np.array([[[255, 0, 0], [0, 255, 0], [0, 0, 255]]], dtype=np.uint8)
        g = color.grayscale(px)
        np.testing.assert_array_equal(g[0, :, 0], [54, 182, 18])
        np.testing.assert_array_equal(g[..., 0], g[..., 1])
        np.testing.assert_array_equal(g[..., 1], g[..., 2])

    def test_grayscale_preserves_every_gray_level(self):
        levels = np.repeat(np.arange(256, dtype=np.uint8)[:, None], 3, axis=1)[None]
        np.testing.assert_array_equal(color.grayscale(levels), levels)

    def test_relative_luminance_matches_independent_formula(self):
        for rgb in [(119, 119, 119), (217, 72, 63), (63, 166, 92), (232, 192, 106)]:
            got = float(color.relative_luminance(np.array(rgb, dtype=np.uint8)))
            self.assertAlmostEqual(got, rel_lum(rgb), places=9)


class DeuteranopiaTests(unittest.TestCase):
    def sim(self, rgb):
        return tuple(int(v) for v in color.deuteranopia(np.array([[rgb]], dtype=np.uint8))[0, 0])

    def test_matrix_is_machado_2009_severity_1(self):
        m = color.MACHADO_DEUTERANOPIA_1_0
        self.assertEqual(m[0, 0], 0.367322)
        self.assertEqual(m[2, 2], 0.968881)
        np.testing.assert_allclose(m.sum(axis=1), 1.0, atol=2e-6)
        # dichromat projection: rank 2
        self.assertLess(np.linalg.svd(m)[1][-1], 1e-5)

    def test_known_outputs_in_linear_space(self):
        # expected values computed with scalar decode -> matrix -> encode
        self.assertEqual(self.sim((255, 0, 0)), (163, 144, 0))
        self.assertEqual(self.sim((0, 255, 0)), (239, 214, 58))
        self.assertEqual(self.sim((0, 0, 255)), (0, 61, 251))

    def test_not_applied_in_gamma_space(self):
        # applying the matrix to encoded values would give (94, 71, 0) for red
        self.assertNotEqual(self.sim((255, 0, 0)), (94, 71, 0))

    def test_neutrals_are_unchanged(self):
        levels = np.repeat(np.arange(256, dtype=np.uint8)[:, None], 3, axis=1)[None]
        np.testing.assert_array_equal(color.deuteranopia(levels), levels)

    def test_confusion_pair_collapses(self):
        m = color.MACHADO_DEUTERANOPIA_1_0
        null = np.linalg.svd(m)[2][-1]
        base = np.array([0.4, 0.4, 0.4])
        a, b = base - 0.15 * null, base + 0.15 * null
        enc = lambda lin: color.quantize_u8(color.linear_to_srgb(lin))  # noqa: E731
        ia, ib = enc(a), enc(b)
        self.assertGreater(int(np.abs(ia.astype(int) - ib.astype(int)).max()), 30)  # distinct to normal vision
        oa = color.deuteranopia(ia[None, None])[0, 0].astype(int)
        ob = color.deuteranopia(ib[None, None])[0, 0].astype(int)
        self.assertLessEqual(int(np.abs(oa - ob).max()), 2)  # nearly identical to a deuteranope

    def test_c7_red_green_zones_converge_but_blue_yellow_do_not(self):
        red, green = self.sim((0xD9, 0x48, 0x3F)), self.sim((0x3F, 0xA6, 0x5C))
        blue, yellow = self.sim((0x3D, 0x7B, 0xDB)), self.sim((0xE0, 0xB2, 0x3C))
        d = lambda p, q: max(abs(x - y) for x, y in zip(p, q))  # noqa: E731
        self.assertEqual(red, (149, 134, 58))
        self.assertEqual(green, (154, 143, 97))
        self.assertGreater(d(blue, yellow), 3 * d(red[:2], green[:2]))

    def test_only_severity_one(self):
        with self.assertRaises(ValueError):
            color.simulate_deuteranopia_linear(np.zeros((1, 3)), severity=0.5)


class ContrastAndChromaTests(unittest.TestCase):
    def test_wcag_extremes_and_symmetry(self):
        self.assertAlmostEqual(float(color.wcag_contrast_ratio(1.0, 0.0)), 21.0)
        self.assertAlmostEqual(float(color.wcag_contrast_ratio(0.0, 1.0)), 21.0)
        self.assertAlmostEqual(float(color.wcag_contrast_ratio(0.3, 0.3)), 1.0)

    def test_wcag_known_pair(self):
        l = float(color.relative_luminance(np.array([119, 119, 119], dtype=np.uint8)))
        self.assertAlmostEqual(float(color.wcag_contrast_ratio(1.0, l)), 4.478, places=3)

    def test_lab_chroma(self):
        c, b = color.lab_chroma(np.array([[128, 128, 128], [255, 0, 0], [60, 90, 160]], dtype=np.uint8))
        self.assertLess(float(c[0]), 0.05)
        self.assertGreater(float(c[1]), 100.0)
        self.assertLess(float(b[2]), -20.0)  # blue-ish = cool (b* < 0)


if __name__ == "__main__":
    unittest.main()
