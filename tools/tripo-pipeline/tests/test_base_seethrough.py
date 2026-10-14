"""Regression tests for review/base_seethrough.py (F149, 2026-10-14): only real holes in the base top count.

The old rule aimed every ray at one plane, z = the highest vertex of the base. On a domed or sloped top a -55 ray
aimed at a point in the air above the far rim passed beyond the base and was counted as a hole (Achilles r3 0.98 uu^2,
Ancient Leshen r3 2.81 uu^2: rim rays that hit no face at all). The rule now aims at the actual top surface.

1. fill_holes (pure Python, no Blender): hole cells take the height of the top around them.
2. Real Blender 5.2 headless: synthetic two-tier bases are built and exported to FBX, then the tool runs on them
   exactly as on a candidate (host CLI -> blender -b):
   a) domed top, no hole              -> 0 uu^2 with --aim surface, alone and with a figure; the old --aim plane
                                         reports the rim false positive (> 0.1 uu^2);
   b) the same domed top with a hole  -> > 0.1 uu^2 in every direction;
   c) flat top with a hole            -> --aim surface and --aim plane give identical numbers.
   Skipped when Blender is not installed or TRIPO_PIPELINE_SKIP_BLENDER=1.

Run from the repo root:  python -m unittest tools/tripo-pipeline/tests/test_base_seethrough.py -v
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REVIEW = Path(__file__).resolve().parents[1] / "review"
TOOL = REVIEW / "base_seethrough.py"


def load(name):
    spec = importlib.util.spec_from_file_location(name, REVIEW / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


bs = load("base_seethrough")
BLENDER = os.environ.get("TRIPO_PIPELINE_BLENDER") or bs.DEFAULT_BLENDER
SKIP = os.environ.get("TRIPO_PIPELINE_SKIP_BLENDER") == "1" or not Path(BLENDER).is_file()
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# Builds the synthetic bases in Blender (metres = uu / 100) and exports each to FBX. Two tiers like the H2 bases:
# lower tier r 15 uu, z 0..3.4; upper tier r 14.1 uu, top at z(r) = 6 - drop * (r / 14.1)^2. The sampled disc is
# 0.93 x 15 = 13.95 uu, so with drop 0.45 the top falls ~0.44 uu below the plane z = 6 at the sampled rim (Achilles
# r3: 0.17-0.24, Leshen r3: up to 0.48). 127 segments (odd: no grid point sits on a fan diagonal through the centre).
GENERATOR = r'''
import json, math, sys
import bmesh, bpy

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
S = 0.01
SEG, RINGS = 127, 28
R_TOP, R_LOW, Z_LOW, Z_TOP = 14.1, 15.0, 3.4, 6.0


def ring(bm, r, z):
    return [bm.verts.new((r * math.cos(2 * math.pi * k / SEG) * S, r * math.sin(2 * math.pi * k / SEG) * S, z * S))
            for k in range(SEG)]


def band(bm, a, b):
    for k in range(SEG):
        bm.faces.new((a[k], a[(k + 1) % SEG], b[(k + 1) % SEG], b[k]))


def base(drop, hole):
    bm = bmesh.new()
    top_c = bm.verts.new((0.0, 0.0, Z_TOP * S))
    rings = [ring(bm, R_TOP * i / RINGS, Z_TOP - drop * (i / RINGS) ** 2) for i in range(1, RINGS + 1)]
    for k in range(SEG):
        bm.faces.new((top_c, rings[0][k], rings[0][(k + 1) % SEG]))
    for a, b in zip(rings, rings[1:]):
        band(bm, a, b)
    step = ring(bm, R_TOP, Z_LOW)
    band(bm, rings[-1], step)
    low_top = ring(bm, R_LOW, Z_LOW)
    band(bm, step, low_top)
    low_bot = ring(bm, R_LOW, 0.0)
    band(bm, low_top, low_bot)
    bot_c = bm.verts.new((0.0, 0.0, 0.0))
    for k in range(SEG):
        bm.faces.new((bot_c, low_bot[(k + 1) % SEG], low_bot[k]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])  # closed: all outward
    if hole:
        hx, hy, hr = hole
        dead = [f for f in bm.faces if f.calc_center_median().z > (Z_LOW + 0.5) * S
                and math.hypot(f.calc_center_median().x / S - hx, f.calc_center_median().y / S - hy) < hr]
        bmesh.ops.delete(bm, geom=dead, context="FACES")
    return bm


def box(x0, y0, x1, y1, z0, z1):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co.x = (x0 if v.co.x < 0 else x1) * S
        v.co.y = (y0 if v.co.y < 0 else y1) * S
        v.co.z = (z0 if v.co.z < 0 else z1) * S
    return bm


for name, spec in job["meshes"].items():
    bpy.ops.wm.read_homefile(use_empty=True)
    bm = box(*spec["box"]) if "box" in spec else base(spec["drop"], spec.get("hole"))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.select_set(True)
    bpy.ops.export_scene.fbx(filepath=spec["out"], use_selection=True, object_types={"MESH"})
print("GENERATOR_OK")
'''


class FillHolesTest(unittest.TestCase):
    def test_hole_takes_the_mean_height_of_the_surrounding_top(self):
        cells = [(i, j) for i in range(-2, 3) for j in range(-2, 3)]
        heights = [None if (i, j) == (0, 0) else 5.0 + 0.1 * i for i, j in cells]
        filled = dict(zip(cells, bs.fill_holes(cells, heights, 9.0)))
        self.assertAlmostEqual(filled[(0, 0)], 5.0)  # mean of 4.9, 5.1, 5.0, 5.0
        self.assertAlmostEqual(filled[(1, 0)], 5.1)  # probed cells keep their height

    def test_hole_fills_layer_by_layer_from_its_rim(self):
        cells = [(i, 0) for i in range(5)]
        filled = bs.fill_holes(cells, [4.0, None, None, None, 6.0], 9.0)
        self.assertEqual(filled, [4.0, 4.0, 5.0, 6.0, 6.0])

    def test_unreachable_cells_and_no_probed_cell_get_the_fallback(self):
        self.assertEqual(bs.fill_holes([(0, 0), (5, 5)], [3.0, None], 9.0), [3.0, 9.0])
        self.assertEqual(bs.fill_holes([(0, 0), (0, 1)], [None, None], 9.0), [9.0, 9.0])


@unittest.skipIf(SKIP, "Blender not available")
class SyntheticBaseTest(unittest.TestCase):
    """The tool end to end (host CLI -> headless Blender) on synthetic FBX bases."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="base-seethrough-"))
        meshes = {"domed": {"drop": 0.45},
                  "domed_hole": {"drop": 0.45, "hole": [4.0, -3.0, 2.0]},
                  "flat_hole": {"drop": 0.0, "hole": [4.0, -3.0, 2.0]},
                  # a standing "figure" in the middle of the top, clear of the rim
                  "figure": {"box": [-2.0, -2.0, 2.0, 2.0, 5.0, 25.0]}}
        for name, spec in meshes.items():
            spec["out"] = str(cls.tmp / (name + ".fbx")).replace("\\", "/")
        job = cls.tmp / "job.json"
        job.write_text(json.dumps({"meshes": meshes}), encoding="utf-8")
        gen = cls.tmp / "generator.py"
        gen.write_text(GENERATOR, encoding="utf-8")
        proc = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(gen),
                               "--", str(job)], capture_output=True, timeout=600, creationflags=NO_WINDOW)
        out = proc.stdout.decode("utf-8", "replace")
        if proc.returncode != 0 or "GENERATOR_OK" not in out:
            raise AssertionError("generator failed (%s):\n%s\n%s" % (
                proc.returncode, out[-3000:], proc.stderr.decode("utf-8", "replace")[-2000:]))
        fbx = {name: spec["out"] for name, spec in meshes.items()}
        items = ["domed=%s" % fbx["domed"], "domed_fig=%s,%s" % (fbx["domed"], fbx["figure"]),
                 "domed_hole=%s" % fbx["domed_hole"], "flat_hole=%s" % fbx["flat_hole"]]
        cls.res = {aim: cls.run_tool(aim, items) for aim in bs.AIMS}

    @classmethod
    def run_tool(cls, aim, items):
        out = cls.tmp / ("result-%s.json" % aim)
        env = dict(os.environ, TRIPO_PIPELINE_BLENDER=BLENDER)
        proc = subprocess.run([sys.executable, str(TOOL), "--aim", aim, "--out", str(out)] + items,
                              capture_output=True, timeout=900, env=env, creationflags=NO_WINDOW)
        if proc.returncode != 0:
            raise AssertionError("base_seethrough.py --aim %s failed:\n%s\n%s" % (
                aim, proc.stdout.decode("utf-8", "replace")[-3000:], proc.stderr.decode("utf-8", "replace")[-3000:]))
        return json.loads(out.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def areas(self, aim, label, mode="base_only"):
        return {name: d["see_through_area_uu2"] for name, d in self.res[aim]["items"][label][mode]["directions"].items()}

    def test_synthetic_base_has_the_intended_size_and_dome(self):
        item = self.res["surface"]["items"]["domed"]
        self.assertEqual(self.res["surface"]["schema"], "unmatched.base-seethrough/2")
        self.assertAlmostEqual(item["disc"]["radius_uu"], 15.0, delta=0.05)
        self.assertAlmostEqual(item["disc"]["plane_z_uu"], 6.0, delta=0.01)
        top = item["disc"]["top_surface_uu"]
        self.assertEqual(top["holes"], 0)
        self.assertGreater(top["max_drop_below_plane_uu"], 0.4)  # the top falls well below the plane at the rim

    def test_domed_top_without_holes_is_not_see_through(self):
        for label, mode in (("domed", "base_only"), ("domed_fig", "base_only"), ("domed_fig", "with_figure")):
            self.assertEqual(set(self.areas("surface", label, mode).values()), {0.0}, (label, mode))
        self.assertTrue(self.res["surface"]["items"]["domed"]["pass"])
        fig = self.res["surface"]["items"]["domed_fig"]
        self.assertEqual(fig["judged_on"], "with_figure")
        self.assertTrue(fig["pass"])

    def test_old_plane_aim_reports_the_rim_false_positive(self):
        # the defect this fix removes: rays aimed above the far rim pass beyond the base (F149)
        plane = self.areas("plane", "domed")
        self.assertEqual(plane["top_down"], 0.0)
        self.assertGreater(max(plane.values()), bs.THRESHOLD_UU2)
        self.assertFalse(self.res["plane"]["items"]["domed"]["pass"])
        self.assertFalse(self.res["plane"]["items"]["domed_fig"]["pass"])

    def test_a_real_hole_is_see_through_in_every_direction(self):
        item = self.res["surface"]["items"]["domed_hole"]
        self.assertGreater(item["disc"]["top_surface_uu"]["hole_area_uu2"], 5.0)
        for name, area in self.areas("surface", "domed_hole").items():
            self.assertGreater(area, bs.THRESHOLD_UU2, name)
        self.assertFalse(item["pass"])
        # top-down the see-through area is the hole the probe found
        self.assertAlmostEqual(self.areas("surface", "domed_hole")["top_down"],
                               item["disc"]["top_surface_uu"]["hole_area_uu2"], delta=0.05)

    def test_flat_top_gives_the_same_numbers_with_both_aims(self):
        flat = self.res["surface"]["items"]["flat_hole"]
        self.assertEqual(flat["disc"]["top_surface_uu"]["max_drop_below_plane_uu"], 0.0)
        self.assertGreater(min(self.areas("surface", "flat_hole").values()), bs.THRESHOLD_UU2)
        self.assertEqual(self.areas("surface", "flat_hole"), self.areas("plane", "flat_hole"))


if __name__ == "__main__":
    unittest.main()
