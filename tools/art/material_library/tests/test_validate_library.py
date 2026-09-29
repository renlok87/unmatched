"""Tests for tools/art/material_library/validate_library.py (and the pure helpers of build_library.py).

The repository library must pass; every mutation below must fail exactly the check that guards it. Mutations run on
a temporary copy of the library (JSON copied, PNG tiles hard-linked, replaced only when a test rewrites one).

  python -m unittest discover -s tools/art/material_library/tests -v
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build_library as bl  # noqa: E402
import validate_library as vl  # noqa: E402

REPO = vl.REPO
HAVE_LIBRARY = all((REPO / p).is_file() for p in (vl.PRESETS, vl.SOURCES, vl.REPORT, vl.MANIFEST))


def failed(results):
    return sorted({r["check"] for r in results if not r["ok"]})


class PureHelpers(unittest.TestCase):
    def test_seam_ratio_periodic_vs_cut(self):
        rng = np.random.default_rng(0)
        noise = bl.periodic_gauss(rng.standard_normal((256, 256)), 2.0)
        self.assertLessEqual(max(vl.seam_ratio(noise)), vl.SEAM_MAX)
        cut = np.asarray(Image.fromarray(((noise - noise.min()) / np.ptp(noise) * 255).astype(np.uint8))
                         .crop((0, 0, 190, 256)).resize((256, 256)), dtype=np.float64)
        self.assertGreater(vl.seam_ratio(cut)[0], vl.SEAM_MAX)

    def test_seam_ratio_periodic_pattern_on_edge(self):
        # a periodic stripe pattern whose wrap falls on a stripe edge is still seamless
        x = np.arange(256)
        stripes = np.tile(((x // 8) % 2).astype(np.float64), (256, 1))
        self.assertLessEqual(max(vl.seam_ratio(stripes)), vl.SEAM_MAX)

    def test_normal_from_height_is_directx(self):
        yy, xx = np.meshgrid(np.arange(128), np.arange(128), indexing="ij")
        h = np.sin(2 * np.pi * xx / 32) * np.cos(2 * np.pi * yy / 64)
        n = bl.encode_normal(bl.normal_dx_from_height(h * 5))
        h01 = (h - h.min()) / np.ptp(h)
        k = vl.normal_convention(n, h01)
        self.assertTrue(vl.dx_sign_ok(k["corr_x"], k["corr_y"]), k)
        gl = n.copy()
        gl[..., 1] = 255 - gl[..., 1]
        k2 = vl.normal_convention(gl, h01)
        self.assertFalse(vl.dx_sign_ok(k2["corr_x"], k2["corr_y"]), k2)

    def test_box_down_keeps_wrap(self):
        rng = np.random.default_rng(1)
        a = bl.periodic_gauss(rng.standard_normal((512, 512)), 3.0)
        self.assertLessEqual(max(vl.seam_ratio(bl.box_down(a, 256))), vl.SEAM_MAX)

    def test_procedural_tiles_periodic_and_deterministic(self):
        for fn, size in ((bl.proc_satin, 128), (bl.proc_skin, 128), (bl.proc_feathers, 256)):
            n1, rmh1, _ = fn(size, 5)
            n2, rmh2, _ = fn(size, 5)
            self.assertTrue(np.array_equal(bl.encode_normal(n1), bl.encode_normal(n2)), fn.__name__)
            self.assertTrue(np.array_equal(rmh1, rmh2), fn.__name__)
            for arr in (n1[..., :2], rmh1[..., 2].astype(np.float64)):
                self.assertLessEqual(max(vl.seam_ratio(arr)), vl.SEAM_MAX, fn.__name__)

    def test_rough_deviation_floor(self):
        flat = 0.1 + 0.001 * np.random.default_rng(2).standard_normal((64, 64))
        dev, med, amp = bl.rough_deviation(flat)
        self.assertEqual(amp, bl.ROUGH_AMP_FLOOR)
        self.assertLess(float(np.abs(dev - 0.5).max()), 0.1)


@unittest.skipUnless(HAVE_LIBRARY, "material library v1 not built")
class RepositoryLibrary(unittest.TestCase):
    def test_repository_library_passes(self):
        res = vl.validate(REPO)
        self.assertEqual(failed(res), [], res)


@unittest.skipUnless(HAVE_LIBRARY, "material library v1 not built")
class Mutations(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="umlib-"))
        for rel in (vl.PRESETS, vl.SOURCES, vl.README, vl.REPORT, vl.MANIFEST):
            dst = self.tmp / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / rel, dst)
        for c in self.load(vl.REPORT)["classes"]:
            for o in c["outputs"]:
                dst = self.tmp / o["path"]
                dst.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(REPO / o["path"], dst)
                except OSError:
                    shutil.copy2(REPO / o["path"], dst)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def load(self, rel):
        return json.loads((self.tmp / rel).read_text(encoding="utf-8"))

    def save(self, rel, obj):
        (self.tmp / rel).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")

    def preset(self, data, cid):
        return next(c for c in data["classes"] if c.get("id") == cid)

    def rewrite_tile(self, cls, kind, fn):
        rep = self.load(vl.REPORT)
        c = next(c for c in rep["classes"] if c["class"] == cls)
        o = next(o for o in c["outputs"] if o["map"] == kind)
        p = self.tmp / o["path"]
        a = np.asarray(Image.open(p)).copy()
        p.unlink()                                  # break the hard link: never touch the repository file
        Image.fromarray(fn(a), "RGB").save(p)
        o["sha256"], o["bytes"] = vl.sha256_file(p), p.stat().st_size
        self.save(vl.REPORT, rep)

    def assertOnlyFails(self, check):
        self.assertEqual(failed(vl.validate(self.tmp)), [check])

    def test_copy_passes(self):
        self.assertEqual(failed(vl.validate(self.tmp)), [])

    def test_metallic_half(self):
        d = self.load(vl.PRESETS)
        self.preset(d, "bronze")["metallic"] = 0.5
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def test_dielectric_too_bright(self):
        d = self.load(vl.PRESETS)
        c = self.preset(d, "linen")
        c["baseColor"]["luminanceRange"] = [0.02, 0.97]
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def test_gold_not_f0(self):
        d = self.load(vl.PRESETS)
        self.preset(d, "gold_antique")["baseColor"]["typicalLinear"] = [0.55, 0.40, 0.15]
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def test_blued_steel_as_bright_iron_needs_no_oxide_flag(self):
        d = self.load(vl.PRESETS)
        bc = self.preset(d, "steel_blued")["baseColor"]
        bc["typicalLinear"] = [0.56, 0.57, 0.58]        # the H2.1 "chrome" look with the oxide band kept
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def test_cloth_without_sheen(self):
        d = self.load(vl.PRESETS)
        del self.preset(d, "wool_coarse")["cloth"]
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def test_measured_roughness_drift(self):
        d = self.load(vl.PRESETS)
        self.preset(d, "wood")["roughness"]["variation"] = 0.3
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def ext(self, data, cid):
        return next(c for c in data["extensionClasses"] if c.get("id") == cid)

    def test_horn_claw_present_and_extension(self):
        d = self.load(vl.PRESETS)
        c = self.ext(d, "horn_claw")
        self.assertEqual((c["metallic"], c["extension"]["globalMatId"], c["detail"]["tileFrom"]), (0, False, "stone_base"))
        self.assertNotIn("horn_claw", [x["id"] for x in d["classes"]])     # the global 0..15 layout is untouched

    def test_horn_claw_metallic_half(self):
        d = self.load(vl.PRESETS)
        self.ext(d, "horn_claw")["metallic"] = 0.5
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def test_horn_claw_f0_not_keratin_band(self):
        d = self.load(vl.PRESETS)
        self.ext(d, "horn_claw")["specular"].update(value=1.0, f0=0.08)
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("preset_physics")

    def test_horn_claw_global_matid_rejected(self):
        d = self.load(vl.PRESETS)
        self.ext(d, "horn_claw")["extension"]["globalMatId"] = True
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("presets_tiles")

    def test_horn_claw_tiles_must_be_tile_from(self):
        d = self.load(vl.PRESETS)
        self.ext(d, "horn_claw")["detail"]["DetailN"] = "art/material-library/v1/tiles/wood/wood_DetailN.png"
        self.save(vl.PRESETS, d)
        self.assertOnlyFails("presets_tiles")

    def test_non_cc0_license(self):
        m = self.load(vl.MANIFEST)
        m["assets"][0]["license"] = "CC BY 4.0"
        self.save(vl.MANIFEST, m)
        self.assertOnlyFails("licenses")

    def test_sources_missing_a_set(self):
        s = self.load(vl.SOURCES)
        s["sets"] = [x for x in s["sets"] if x["id"] != "Rock058"]
        self.save(vl.SOURCES, s)
        self.assertOnlyFails("licenses")

    def test_unused_set_without_reason(self):
        s = self.load(vl.SOURCES)
        next(x for x in s["sets"] if x["id"] == "Wood066")["reason"] = ""
        self.save(vl.SOURCES, s)
        self.assertOnlyFails("source_mapping")

    def test_tile_sha_mismatch(self):
        rep = self.load(vl.REPORT)
        rep["classes"][0]["outputs"][0]["sha256"] = "0" * 64
        self.save(vl.REPORT, rep)
        self.assertOnlyFails("tile_files")

    def test_opengl_normal_detected(self):
        def flip_g(a):
            a[..., 1] = 255 - a[..., 1]
            return a
        self.rewrite_tile("wood", "DetailN", flip_g)
        self.assertOnlyFails("normal_dx")

    def test_cut_tile_detected(self):
        def cut(a):
            n = a.shape[0]
            return np.asarray(Image.fromarray(a).crop((0, 0, int(n * 0.7), n)).resize((n, n), Image.BILINEAR))
        self.rewrite_tile("leather_worn", "DetailRMH", cut)
        self.assertIn("seamless", failed(vl.validate(self.tmp)))


if __name__ == "__main__":
    unittest.main()
