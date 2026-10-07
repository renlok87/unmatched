"""ENV-MAPS P7 track B: plain-Python contract of tools/art/concept_paste/ue_concept_material.py (M_ConceptPaste).

The UE side is unreal/Unmatched/Source/Unmatched/S08/S08ConceptPaste.h (+ Unmatched.S08.ConceptPaste.* automation):
parameter names, the projection mirror, the shipped conceptPaste blocks, the grade / LUT helpers.
"""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "concept_paste"))

import ue_concept_material as m  # noqa: E402


class ConceptMaterialContract(unittest.TestCase):
    def test_check_mode_passes(self):
        report, errors = m.check()
        self.assertEqual(errors, [])
        self.assertIn("FlowRect0", report["params"])

    def test_every_parameter_is_a_custom_pin_and_used_by_the_hlsl(self):
        for name in m.TEXTURES + tuple(m.VECTORS) + tuple(m.SCALARS):
            self.assertIn(name, m.INPUTS)
            self.assertRegex(m.CONCEPT_HLSL, rf"\b{name}\b", name)
        for pin in ("WP", "VUV", "VSZ", "UseAnimS"):
            self.assertIn(pin, m.INPUTS)
            self.assertRegex(m.CONCEPT_HLSL, rf"\b{pin}\b")
        self.assertEqual(len(set(m.INPUTS)), len(m.INPUTS))

    def test_graph4_no_time_node_and_the_static_switch(self):
        """VS-5 EN-06 (ВР-EN.4): the animation time is AnimTime from C++; UseAnim gates the anim channels."""
        self.assertEqual(m.GRAPH_VERSION, "4")
        self.assertNotIn("Time", m.INPUTS)
        self.assertNotRegex(m.CONCEPT_HLSL, r"\bTime\b")
        self.assertIn("V.xy * AnimTime", m.CONCEPT_HLSL)  # the flows read AnimTime too
        self.assertEqual(m.SCALARS["AnimTime"], 0.0)
        self.assertEqual(m.USE_ANIM, "UseAnim")
        anim = m.CONCEPT_HLSL[m.CONCEPT_HLSL.index("if (UseAnimS > 0.5)"):]
        for name in ("AnimMask", "MistNoise", "WindParams", "WindWavePx", "MistColor", "MistParams"):
            self.assertIn(name, anim)
        # every lantern slot is read, unused slots (radius 0) weigh 0, at most 8
        for i in range(m.MAX_ANIM_LANTERNS):
            self.assertIn(f"LanternC0_{i}.z", m.CONCEPT_HLSL)
            self.assertEqual(m.SCALARS[f"LanternFlicker_{i}"], 1.0)
            self.assertEqual(m.VECTORS[f"LanternC0_{i}"], (0.0, 0.0, 0.0, 0.0))
        self.assertNotIn(f"LanternC0_{m.MAX_ANIM_LANTERNS}", m.CONCEPT_HLSL)
        # the wind offset follows the card formula (y = 0.35 x)
        self.assertIn("c += float2(wx, 0.35 * wx);", m.CONCEPT_HLSL)
        self.assertIn("0.4 + 0.6 * Texture2DSample(MistNoise", m.CONCEPT_HLSL)

    def test_noise_is_deterministic_tileable_and_spans_the_range(self):
        a = m.noise_values(64, 7, ((4, 1.0), (8, 0.5)))
        b = m.noise_values(64, 7, ((4, 1.0), (8, 0.5)))
        self.assertEqual(a, b)
        self.assertNotEqual(a, m.noise_values(64, 8, ((4, 1.0), (8, 0.5))))
        self.assertEqual((min(a), max(a)), (0, 255))
        rows = [a[y * 64:(y + 1) * 64] for y in range(64)]
        # wrap: the step across the texture edge is like any neighbour step (no seam)
        inner = max(abs(r[x + 1] - r[x]) for r in rows for x in range(63))
        edge = max(abs(r[0] - r[63]) for r in rows)
        self.assertLessEqual(edge, inner + 1)
        inner_y = max(abs(rows[y + 1][x] - rows[y][x]) for y in range(63) for x in range(64))
        self.assertLessEqual(max(abs(rows[0][x] - rows[63][x]) for x in range(64)), inner_y + 1)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "n.tga"
            m.write_tga_gray(path, a, 64)
            data = path.read_bytes()
            self.assertEqual(len(data), 18 + 64 * 64)
            self.assertEqual(data[2], 3)    # uncompressed grayscale
            self.assertEqual(data[16], 8)   # 8 bit
            self.assertEqual(data[17], 0x20)  # top-left origin

    def test_shipped_marmoreal_anim_block(self):
        """VS-5 E1 (EN-06 + EN-07): the Marmoreal paste block animates the painted surround; Sarpedon has no anim."""
        profiles = json.loads(m.PROFILES.read_text(encoding="utf-8"))
        boards = {b["id"]: b for b in profiles["boards"]}
        mar = boards["marmoreal-original"]["conceptPaste"]
        anim = mar["anim"]
        self.assertEqual(anim["mask"], "/Game/EnvMaps/Marmoreal/ConceptPaste/T_Marmoreal_ConceptAnim")
        light_ids = {lt["id"] for lt in mar["lights"]}
        synced = [sl for sl in anim["lanterns"] if sl.get("light") in light_ids]
        self.assertEqual(len(anim["lanterns"]), 6)
        self.assertEqual(len(synced), 4)
        self.assertLessEqual(float(anim["wind"]["ampPx"]) * (1 + float(anim["wind"]["gustAmp"])), 4.0)
        self.assertNotIn("anim", boards["sarpedon-original"]["conceptPaste"])

    def test_hlsl_avoids_vector_conditions(self):
        # HLSL 2021 (DXC): no vector condition in ?: and no ||/&& on vectors - the shader uses step / lerp instead
        self.assertNotIn("all(", m.CONCEPT_HLSL)
        self.assertNotIn(" ? tc", m.CONCEPT_HLSL)
        self.assertIn("return float4(e, alpha);", m.CONCEPT_HLSL)

    def test_camera_matches_the_k1_mock_rig(self):
        cam = m.Camera()
        self.assertAlmostEqual(cam.pos[1], 1557.046, places=2)
        self.assertAlmostEqual(cam.pos[2], 2223.692, places=2)
        x, y = cam.project((0.0, 0.0, 0.0))
        self.assertAlmostEqual(x, 960.0, places=9)
        self.assertAlmostEqual(y, 540.0, places=9)
        self.assertIsNone(cam.project(tuple(p + 10 * f for p, f in zip(cam.pos, (0.0, 0.5736, 0.8192)))))

    def test_shipped_sarpedon_block_cut_and_flow(self):
        profiles = json.loads(m.PROFILES.read_text(encoding="utf-8"))
        sar = next(b for b in profiles["boards"] if b["id"] == "sarpedon-original")["conceptPaste"]
        fh = (445.6667 + 24, 288.6667 + 24)
        self.assertTrue(m.shader_sample(sar, fh, (0.0, 0.0, 0.0))["cut"])
        self.assertFalse(m.shader_sample(sar, fh, (0.0, 0.0, -300.0), sea=True)["cut"])
        self.assertFalse(m.shader_sample(sar, fh, (470.0, 0.0, -3.0))["cut"])
        # a point of the painted waterfall (C0 px ~ (820, 1090)) is inside the waterfall flow region
        cam = m.Camera(sar)
        sx = (820 / 1920 * 2 - 1) * cam.tan_h
        sy = (1 - 1090 / 1080 * 2) * cam.tan_v
        ray = [f + sx * r + sy * u for f, r, u in zip(cam.fwd, cam.right, cam.up)]
        world = tuple(p + 2700 * v for p, v in zip(cam.pos, ray))
        sample = m.shader_sample(sar, fh, world)
        self.assertGreater(sample["flowWeights"][0], 0.99)
        self.assertEqual(sample["flowWeights"][1], 0.0)

    def test_grade_helpers(self):
        for y in (0.0, 0.05, 0.3, 0.7, 0.97):
            self.assertAlmostEqual(m.aces(m.inverse_aces(y)), y, places=5)
        for s in (0.0, 0.02, 0.5, 1.0):
            self.assertAlmostEqual(m.srgb_encode(m.srgb_decode(s)), s, places=6)
        ch, v = m.calib_cell(0, 0)
        self.assertEqual((ch, v), (0, 0.0))
        ch, v = m.calib_cell(31, 17)
        idx = 17 * 32 + 31
        self.assertEqual(ch, idx % 4)
        self.assertAlmostEqual(v, m.CALIB_MAX * (((idx // 4) % 64) / 63) ** 3)

    def test_lut_from_a_synthetic_tonemapper_and_hdr(self):
        samples = [(ch, e, m.srgb_encode(m.aces(e))) for cy in range(18) for cx in range(32)
                   for ch, e in [m.calib_cell(cx, cy)]]
        lut = m.lut_from_samples(samples)
        self.assertEqual(len(lut), m.LUT_SIZE)
        for k in range(8, 240, 16):
            for c in range(3):
                self.assertAlmostEqual(m.srgb_encode(m.aces(lut[k][c])), k / 255, delta=0.01)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "lut.hdr"
            m.write_hdr(path, lut)
            data = path.read_bytes()
            header = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 256\n"
            self.assertTrue(data.startswith(header))
            self.assertEqual(len(data), len(header) + 4 * 256)
            r, g, b, e = data[len(header) + 4 * 128: len(header) + 4 * 129]
            scale = math.ldexp(1.0, e - 136)
            self.assertAlmostEqual(r * scale, lut[128][0], delta=lut[128][0] * 0.01 + 1e-6)


if __name__ == "__main__":
    unittest.main()
