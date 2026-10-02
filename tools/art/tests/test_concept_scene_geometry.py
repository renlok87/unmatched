"""ENV-MAPS P8.1 (track A) concept scene: geometry contracts, recomputed from the params (pure Python, no Blender).

  python -m pytest tools/art/tests/test_concept_scene_geometry.py -q

* determinism: the island / fort / palisade / piles / banner builders give the same mesh twice and the digest recorded
  in their committed build reports (code + params == the exported geometry);
* the island: no vertex above the plateau inside the map field (|X| <= 467.67, |Y| <= 310.67), the frame-002 foot
  ring stands on the top (no gap), <= 40k triangles, a non-overlapping UV atlas inside 0..1, the near cliffs face the
  K1 camera, the waterfall tongue reaches under SM_Env_S_WaterfallLip, the cliffs reach the sea plane;
* the props: triangle budgets (<= 12k), closed logs, posts standing on the island.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools/art/concept_scene"))

import cs_common as CS  # noqa: E402
import cs_geom as G  # noqa: E402
import island_build as IB  # noqa: E402
import fort_build as FB  # noqa: E402
import palisade_build as PB  # noqa: E402
import banner_build as BB  # noqa: E402


def report(run, name):
    return json.loads((CS.RUNS[run] / "reports" / name).read_text(encoding="utf-8"))


class IslandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allp = CS.params()
        cls.P = allp["island"]
        cls.sea = float(allp["seaZ"])
        cls.mesh, cls.rimd, cls.info, cls.hf = IB.build(cls.P, cls.sea)

    def test_deterministic_and_matches_the_report(self):
        again, _, _, _ = IB.build(self.P, self.sea)
        self.assertEqual(self.mesh.digest(), again.digest())
        self.assertEqual(self.mesh.digest(), report("island", "island-build.json")["meshDigest"],
                         "island-build.json is stale: run island_build.py (run_scene.py)")

    def test_no_face_above_the_map_field(self):
        B = self.mesh.board()
        hx, hy = CS.MAP_FIELD
        inside = (np.abs(B[:, 0]) <= hx) & (np.abs(B[:, 1]) <= hy)
        self.assertGreater(int(inside.sum()), 100)
        self.assertLessEqual(float(B[inside, 2].max()), self.P["plateauZ"] + 1e-6)
        # every triangle with a vertex in the field stays at or below the plateau
        tri_in = inside[self.mesh.F].any(1)
        self.assertLessEqual(float(B[self.mesh.F[tri_in]][..., 2].max()), self.P["plateauZ"] + 1e-6)

    def test_frame_foot_stands_on_a_solid_plate(self):
        chk = IB.checks(self.mesh, self.P)
        self.assertEqual(chk["frameFootRingCovered"], 1.0)
        self.assertEqual(chk["verticesAboveMapField"], 0)

    def test_triangle_budget_and_atlas(self):
        self.assertLessEqual(self.mesh.tris, 40000)
        UV = self.mesh.UV
        self.assertTrue((UV >= 0).all() and (UV <= 1).all())
        ov, cov = CS.uv_overlap_share(UV, 1024)
        self.assertEqual(ov, 0.0)
        self.assertGreater(cov, 300000)

    def test_cliffs_reach_the_sea_and_face_out(self):
        B = self.mesh.board()
        self.assertLessEqual(float(B[:, 2].min()), self.sea)
        cliff = ~self.mesh.SMOOTH
        n = self.mesh.face_normals()[cliff]
        c = B[self.mesh.F[cliff]].mean(1)
        near = c[:, 1] > CS.C.FRAME_HY + 40  # the near (south) cliffs below the front rim
        self.assertGreater(float(n[near, 1].mean()), 0.3, "near cliffs must face the K1 camera (+Y)")
        top = self.mesh.face_normals()[self.mesh.SMOOTH]
        self.assertGreater(float(top[:, 2].min()), 0.0, "top faces point up")

    def test_waterfall_tongue_under_the_lip(self):
        # SM_Env_S_WaterfallLip: loc (-144.1, 425, 0), yaw 90, slabs from local x -26 (back) -> board Y >= 399
        R = self.rimd["R"]
        sel = np.abs(R[:, 0] + 144.1) < 80
        self.assertGreater(float(R[sel, 1].max()), 399.0 + 20.0, "the tongue must reach under the lip's back")
        h = self.hf(np.array([[-144.1, 410.0]]))[0]
        self.assertLess(h, 0.8, "the tongue stays below the lip top (Z 0.8)")


class PropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allp = CS.params()
        island, _, _, _ = IB.build(allp["island"], float(allp["seaZ"]))
        cls.ground = G.Ground([island])
        cls.allp = allp

    def test_fort(self):
        m, info = FB.build(self.allp["fort"], self.ground)
        m2, _ = FB.build(self.allp["fort"], self.ground)
        self.assertEqual(m.digest(), m2.digest())
        self.assertEqual(m.digest(), report("fort", "fort-build.json")["meshDigest"])
        self.assertLessEqual(m.tris, 12000)
        self.assertGreater(info["blocks"], 20)
        # the painted ruin is 150-280 uu tall at C0 (task text 110-150 = the P7 guess): measured, reported
        self.assertGreater(info["heightMaxUU"], 110.0)

    def test_palisade_and_piles(self):
        for key, name, rep in (("palisade", "SM_Env_S_Palisade", "palisade-build.json"),
                               ("piles", "SM_Env_S_Piles", "piles-build.json")):
            slot = "MI_Env_S_" + name.rsplit("_", 1)[-1]
            m, info = PB.build_posts(self.allp[key], self.ground, name, slot)
            m2, _ = PB.build_posts(self.allp[key], self.ground, name, slot)
            self.assertEqual(m.digest(), m2.digest(), key)
            self.assertEqual(m.digest(), report("props", rep)["meshDigest"], key)
            self.assertLessEqual(m.tris, 12000, key)
            for g in info["groups"]:
                for f in g["feet"]:
                    gz = self.ground.height_at(f[0], f[1])
                    self.assertLess(abs(gz - f[2]), 60.0, f"{key} {g['id']}: foot off the island")

    def test_log_is_closed_and_outward(self):
        V, F = G.log([0, 0, 0], [0, 0, 100], 10, point=1.5)
        c = G.closed_check(V, F)
        self.assertEqual(c["boundaryEdges"], 0)
        self.assertEqual(c["nonManifoldEdges"], 0)
        self.assertGreater(c["volume"], 0)
        V, F = G.chamfer_box([0, 0, 0], [40, 30, 20], bevel=2)
        c = G.closed_check(V, F)
        self.assertEqual((c["boundaryEdges"], c["nonManifoldEdges"]), (0, 0))
        self.assertAlmostEqual(c["volume"], 24000, delta=200)

    def test_banner_hangs_vertically(self):
        m, info = BB.build(self.allp["banner"])
        self.assertEqual(m.digest(), report("props", "banner-build.json")["meshDigest"])
        cloth = m.V[:, 2] < -5.0
        # straight down: the cloth's X spread is only the folds (no shear along the hang)
        self.assertLess(float(np.ptp(m.V[cloth, 0])), 12.0)
        self.assertEqual(info["hang"], [0.0, 0.0, -1.0])


if __name__ == "__main__":
    unittest.main()
