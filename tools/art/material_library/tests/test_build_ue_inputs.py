"""Tests for tools/art/material_library/build_ue_inputs.py (M_UM_Figure v2 inputs: LUT, arrays, test textures).

  python -m unittest discover -s tools/art/material_library/tests -v
"""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build_ue_inputs as bu  # noqa: E402

HAVE_PRESETS = bu.PRESETS.is_file()


def read_dds(path: Path):
    raw = path.read_bytes()
    assert raw[:4] == b"DDS "
    h, w = struct.unpack_from("<II", raw, 12)
    fourcc = raw[84:88]
    dxgi, dim, _, arr, _ = struct.unpack_from("<IIIII", raw, 128)
    return {"h": h, "w": w, "fourcc": fourcc, "dxgi": dxgi, "dim": dim, "array": arr, "data": raw[148:]}


@unittest.skipUnless(HAVE_PRESETS, "presets missing")
class Lut(unittest.TestCase):
    def setUp(self):
        self.presets = bu.load_presets()
        self.cols = bu.class_columns(self.presets)
        self.lut = bu.lut_array(self.cols)

    def test_layout(self):
        self.assertEqual(self.lut.shape, (bu.LUT_H, bu.LUT_W, 4))
        self.assertTrue(np.all(self.lut[10:] == 0.0), "rows 10-15 are reserved (0)")

    def test_metallic_binary_and_bc_mode(self):
        for i, f in self.cols.items():
            self.assertIn(f["metallic"], (0.0, 1.0), f["classId"])
            if i:
                self.assertEqual(f["bcMode"], f["metallic"], "metals take the preset F0, dielectrics the bake")

    def test_slice_is_index_and_512_tiles_halved(self):
        for c in self.presets["classes"][1:]:
            f = self.cols[c["index"]]
            self.assertEqual(f["slice"], float(c["index"]))
            exp = c["detail"]["tilesPerMeter"] * c["detail"]["tileSizePx"] / bu.SLICE
            self.assertAlmostEqual(f["tilesPerMeter"], exp, places=6)

    def test_dye_only_where_presets_allow(self):
        allowed = {c["index"] for c in self.presets["classes"] if c.get("teamDyeAllowed")}
        for i, f in self.cols.items():
            self.assertEqual(f["teamDyeAllowed"] == 1.0, i in allowed or i == 0, f["classId"])
        for metal in ("steel_blued", "gold_antique", "bronze", "brass"):
            i = next(c["index"] for c in self.presets["classes"] if c["id"] == metal)
            self.assertEqual(self.cols[i]["teamDyeAllowed"], 0.0, metal)

    def test_cloth_rows(self):
        for c in self.presets["classes"][1:]:
            f = self.cols[c["index"]]
            self.assertEqual(f["shadingModel"] == 1.0, c["shadingModel"] == "Cloth", c["id"])
            if c["shadingModel"] == "Cloth":
                self.assertGreater(f["sheenIntensity"], 0.0)
                self.assertGreater(f["clothAmount"], 0.0)

    def test_half_precision_is_enough(self):
        q = self.lut.astype(np.float16).astype(np.float32)
        self.assertLess(float(np.abs(q - self.lut).max()), 0.01)

    def test_overrides(self):
        cols = json.loads(json.dumps(self.cols))
        cols = {int(k): v for k, v in cols.items()}
        applied = bu.apply_overrides(cols, {"classes": {"steel_blued": {"bc": [0.1, 0.11, 0.13], "ymedClassHero": 0.2}}},
                                     self.presets)
        self.assertEqual(len(applied), 2)
        self.assertAlmostEqual(cols[1]["bcB"], 0.13)
        self.assertAlmostEqual(cols[1]["ymedClassHero"], 0.2)
        with self.assertRaises(SystemExit):
            bu.apply_overrides(cols, {"classes": {"steel_blued": {"nope": 1}}}, self.presets)


class Dds(unittest.TestCase):
    def test_array_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.dds"
            s = [np.full((4, 8, 4), i, np.uint8) for i in range(3)]
            bu.write_dds(p, s, "R8G8B8A8_UNORM")
            d = read_dds(p)
            self.assertEqual((d["h"], d["w"], d["fourcc"], d["dxgi"], d["dim"], d["array"]), (4, 8, b"DX10", 28, 3, 3))
            self.assertEqual(len(d["data"]), 3 * 4 * 8 * 4)
            self.assertEqual(d["data"][4 * 8 * 4], 1)

    def test_matid_encoding_decodes(self):
        # value = index * 16 + 8 -> floor(v / 255 * 255 / 16) = index (the shader decode)
        for i in range(16):
            v = (i * 16 + 8) / 255.0
            self.assertEqual(int(np.floor(v * (255.0 / 16.0) + 1e-3)), i)


if __name__ == "__main__":
    unittest.main()
