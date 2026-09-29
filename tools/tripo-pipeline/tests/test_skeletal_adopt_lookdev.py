"""LD-merlin-ue: skeletal-adopt of a look-dev run (format h2-lookdev-merlin/1, skeletal_adopt_lookdev.py) and the
UE-inputs converter (tools/art/material_library/lookdev_ue_inputs.py).

The real Merlin look-dev run is used when its files are in the checkout (skipped otherwise): adopt must pass with the
committed profile, and a tampered H2.1 build-report pin, a stale UE-inputs report or a LUT of the wrong size must fail.
"""
import copy
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE.parent
REPO = TOOL.parents[1]
sys.path.insert(0, str(TOOL))
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))

import skeletal_adopt as sa  # noqa: E402
import skeletal_adopt_lookdev as sal  # noqa: E402

PROFILE = REPO / "art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-h2-lookdev-ue-import.json"
PRESET = REPO / "blender/_tools/presets/UM_FBX_v1.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def png_px(p):
    head = Path(p).read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return list(struct.unpack(">II", head[16:24]))


def run_adopt(profile):
    return sa.adopt(profile, lambda rel: REPO / rel, sha, png_px, json.loads(PRESET.read_text(encoding="utf-8")))


@unittest.skipUnless(PROFILE.is_file() and (REPO / "art/pipeline-candidates/ASSET-MERLIN-001/20260929-h2-lookdev/"
                                                   "ue-inputs/ue-inputs-report.json").is_file(),
                     "Merlin look-dev run not in this checkout")
class LookdevAdoptTest(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    def test_format_registered(self):
        self.assertIn("h2-lookdev-merlin/1", sa.REPORT_FORMATS)
        self.assertIs(sa.normaliser(self.profile), sal.lookdev_merlin)

    def test_real_run_adopts(self):
        res = run_adopt(self.profile)
        failed = [k for k, v in res["checks"].items() if not v["passed"]]
        self.assertEqual(failed, [])
        self.assertTrue(all(v["passed"] for v in res["bake"]["normalised"]["checks"].values()))
        self.assertEqual(res["views"]["atlas"]["size"], 2048)
        self.assertIn("texture:MatLUT", res["keys"])

    def test_h21_pin_mismatch_fails(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["h21_build_report"]["sha256"] = "0" * 64
        res = run_adopt(p)
        self.assertFalse(res["checks"]["bake_report_passed"]["passed"])
        self.assertFalse(res["bake"]["normalised"]["checks"]["h21_build_report_pinned"]["passed"])

    def test_lut_without_exception_fails_tier_check(self):
        p = copy.deepcopy(self.profile)
        p["candidate"]["texture_exceptions"] = {}
        res = run_adopt(p)
        self.assertFalse(res["checks"]["textures_are_the_runtime_tier"]["passed"])

    def test_dds_pixels(self):
        lut = REPO / self.profile["candidate"]["dir"] / self.profile["candidate"]["textures"]["MatLUT"]
        self.assertEqual(sa.dds_pixels(lut), [16, 16])
        self.assertEqual(sal.image_px(lut), [16, 16])


class ConverterTest(unittest.TestCase):
    def test_blender_overrides_to_lut(self):
        import lookdev_ue_inputs as li
        out = li.blender_overrides_to_lut({
            "silk": {"baseColor": {"typicalLinear": [0.3, 0.16, 0.07]}, "teamDyeAllowed": False, "note": "x",
                     "cloth": {"sheenColor": {"intensity": 0.5, "tint": 1.0}},
                     "roughness": {"typical": 0.42, "range": [0.32, 0.58], "variation": 0.08, "note": "y"}},
            "bronze": {"heroYmed": 0.178}})
        self.assertEqual(out["silk"], {"bc": [0.3, 0.16, 0.07], "teamDyeAllowed": 0.0, "sheenIntensity": 0.5,
                                       "sheenTint": 1.0, "roughTypical": 0.42, "roughLo": 0.32, "roughHi": 0.58,
                                       "roughVariation": 0.08})
        self.assertEqual(out["bronze"], {"ymedClassHero": 0.178})
        merged = li.merge(out, {"silk": {"specular": 0.35, "why": "doc"}})
        self.assertEqual(merged["silk"]["specular"], 0.35)
        self.assertNotIn("why", merged["silk"])

    def test_zone_palette_distinct(self):
        import lookdev_ue_inputs as li
        import numpy as np
        import build_ue_inputs as B
        pal = li.zone_palette(12, 0.34)
        self.assertEqual(len(pal), 12)
        disp = [B.linear_to_srgb8(np.clip(c * 0.34, 0, 1)).astype(float) for c in pal]
        dmin = min(float(np.linalg.norm(a - b)) for i, a in enumerate(disp) for b in disp[i + 1:])
        self.assertGreater(dmin, 40.0)
        self.assertEqual([list(c) for c in pal], [list(c) for c in li.zone_palette(12, 0.34)])


if __name__ == "__main__":
    unittest.main()
