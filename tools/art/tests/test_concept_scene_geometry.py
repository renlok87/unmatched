"""ENV-MAPS P8.1 (track A) concept scene: geometry contracts, recomputed from the params (pure Python, no Blender).

  python -m pytest tools/art/tests/test_concept_scene_geometry.py -q

* determinism: the island / fort / palisade / piles / banner builders give the same mesh twice and the digest recorded
  in their committed build reports (code + params == the exported geometry);
* the island: no vertex above the plateau inside the map field (|X| <= 467.67, |Y| <= 310.67), the frame-002 foot
  ring stands on the top (no gap), <= 40k triangles, a non-overlapping UV atlas inside 0..1, the near cliffs face the
  K1 camera, the cliffs reach the sea plane; P9: the front lip tucks under the frame band's near beam (ring 1 on the
  beam face plane, below its bottom edge; deeper in the cascade outlet), the P5c waterfall tongue is gone;
* the props: triangle budgets (<= 12k), closed logs, posts standing on the island;
* P9: the frame band (wraps frame-002, never over it, below its top, covers the painted frame at C0, two slots), the
  cascade (4 streams, 4 tiers, clear of the rock towards every game camera, flow UVs) and the procedural ship (rail on
  the painted pixels, ports at the painted muzzles, the mast on the deck, clear of the frame band).
"""
from __future__ import annotations

import json
import math
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
import frame_band_build as FBB  # noqa: E402
import cascade_build as CB  # noqa: E402
import ship_build as SB  # noqa: E402


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

    def test_front_lip_tucks_under_the_beam(self):
        # P9 F3: on the front rim under the near beam the first profile ring lies on the beam's face plane, below its
        # bottom edge (no grazing lip strip in front of the frame); deeper in the cascade outlet
        L = self.P["nearLip"]
        fb = CS.params()["frameBand"]
        R, rings = self.rimd["R"], self.rimd["rings"]
        sel = (R[:, 1] > CS.C.FRAME_HY) & (np.abs(R[:, 0]) < L["xHalfUU"] - 5)
        self.assertGreater(int(sel.sum()), 40)
        r1 = rings[1, sel]
        self.assertLess(float(np.abs(r1[:, 1] - L["faceYUU"]).max()), 1.5)
        self.assertTrue((r1[:, 2] <= fb["faceBottomZ"]).all(), "ring 1 below the beam's bottom edge")
        x0, x1 = L["outletXUU"]
        out = sel & (R[:, 0] > x0) & (R[:, 0] < x1)
        self.assertLess(float(rings[1, out, 2].max()), fb["faceBottomZ"] - 20.0, "the cascade outlet under the beam")
        self.assertLess(float(R[sel, 1].max()), fb["faceYUU"], "the rim stays behind the beam face")

    def test_waterfall_tongue_is_gone(self):
        R = self.rimd["R"]
        sel = np.abs(R[:, 0] + 144.1) < 120
        self.assertLess(float(R[sel, 1].max()), 360.0)


class FrameBandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = CS.params()["frameBand"]
        cls.mesh, cls.info = FBB.build(cls.P)

    def test_deterministic_and_matches_the_report(self):
        again, _ = FBB.build(self.P)
        self.assertEqual(self.mesh.digest(), again.digest())
        self.assertEqual(self.mesh.digest(), report("props", "frameband-build.json")["meshDigest"])

    def test_wraps_frame002_never_over_it(self):
        chk = FBB.checks(self.mesh, self.P)
        self.assertEqual(chk["verticesOverFrame002OrMap"], 0)
        self.assertTrue(chk["belowFrameTop"])
        self.assertLessEqual(self.mesh.tris, 12000)
        B = self.mesh.board()
        self.assertLess(float(np.abs(B[:, 0]).min()), 1.0, "the far / near beams run across the whole width")
        self.assertLess(float(np.min(np.abs(B[:, 0]) - CS.C.FRAME_HX, initial=1e9, where=np.abs(B[:, 1]) < CS.C.FRAME_HY)), 1.0)

    def test_covers_the_painted_frame_at_c0(self):
        rep = report("props", "frameband-build.json")
        self.assertGreaterEqual(rep["c0Coverage"]["covered"], 0.9)
        self.assertLessEqual(rep["c0Coverage"]["spillShareOfPainted"], 0.2)

    def test_two_slots_and_tiling_uvs(self):
        self.assertEqual(self.mesh.slots, ["MI_EnvScene_FrameWood", "MI_EnvScene_FrameIron"])
        n_iron = int((self.mesh.MAT == 1).sum())
        self.assertGreater(n_iron, 500, "iron brackets / straps / rivets")
        self.assertGreater(int((self.mesh.MAT == 0).sum()), 500)
        self.assertTrue(np.isfinite(self.mesh.UV).all())
        # tiling: a beam spans several UV units along its grain
        self.assertGreater(float(np.ptp(self.mesh.UV[self.mesh.MAT == 0][..., 0])), 5.0)


class CascadeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allp = CS.params()
        cls.allp = allp
        island, rimd, _, _ = IB.build(allp["island"], float(allp["seaZ"]))
        cls.island, cls.rimd = island, rimd
        cls.sheet, cls.foam, cls.info = CB.build(allp["cascade"], rimd, float(allp["seaZ"]), CB.beam_of(allp))

    def test_deterministic_and_matches_the_report(self):
        s2, f2, _ = CB.build(self.allp["cascade"], self.rimd, float(self.allp["seaZ"]), CB.beam_of(self.allp))
        self.assertEqual((self.sheet.digest(), self.foam.digest()), (s2.digest(), f2.digest()))
        rep = report("props", "cascade-build.json")
        self.assertEqual(rep["meshDigest"], {CB.NAME: self.sheet.digest(), CB.FOAM: self.foam.digest()})

    def test_streams_tiers_and_uvs(self):
        # VS-8 E1 EN-19: the three painted streams (P9 / P10: four overlapping ones)
        self.assertEqual(len(self.info["streams"]), len(self.allp["cascade"]["streams"]))
        self.assertGreaterEqual(len(self.info["streams"]), 3)
        xs = self.allp["cascade"]["streams"]
        self.assertTrue(all(b[0] - a[1] >= 10.0 for a, b in zip(xs, xs[1:])), "rock gaps >= 10 uu between streams")
        self.assertEqual([t["tier"] for t in self.info["tiers"]], [1, 2, 3, 4])
        self.assertTrue(self.info["tiers"][-1]["sea"])
        zs = [t["landing"][2] for t in self.info["tiers"]]
        self.assertEqual(zs, sorted(zs, reverse=True), "tiers step down")
        B = self.sheet.board()
        self.assertGreaterEqual(float(B[:, 2].min()), float(self.allp["seaZ"]) - 1e-6)
        self.assertLessEqual(float(B[:, 2].max()), self.allp["frameBand"]["faceBottomZ"], "starts under the beam")
        self.assertTrue((self.sheet.UV >= -1e-9).all() and (self.sheet.UV <= 1 + 1e-9).all())
        rep = report("props", "cascade-build.json")
        # VS-8 E1 EN-19: the painted rocks between the three painted streams stay dry (their light columns cover
        # 201 of the 360 px of the painted rect = 0.56); P9 / P10 covered the whole width (>= 0.8)
        self.assertGreaterEqual(rep["c0Coverage"]["c0Frame"]["widthCoverage"], 0.55, "painted width coverage at C0")

    def test_clear_of_the_rock_towards_the_cameras(self):
        cam = CS.cam0()
        ground = G.Ground([self.island])
        c = ground.P[ground.F].mean(1)
        sel = (c[:, 0] > -330) & (c[:, 0] < 100) & (c[:, 1] > 300)
        F = ground.F[sel]
        for name, pos in (("C0", cam.pos), ("K1", CS.C.Cam(CS.C.D_K1).pos)):
            blocked = 0
            for v in self.sheet.board()[::4]:
                d = pos - v
                d = d / np.linalg.norm(d)
                blocked += int(np.isfinite(G.ray_mesh(v + d * 0.5, d, ground.P, F)))
            self.assertEqual(blocked, 0, name)


class ShipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        allp = CS.params()
        cls.P = allp["ship"]
        cls.east = FBB.outer_extents(allp["frameBand"])["eastX"]
        cls.mesh, cls.info, cls.W = SB.build(cls.P, cls.east)

    def test_deterministic_and_matches_the_report(self):
        again, _, _ = SB.build(self.P, self.east)
        self.assertEqual(self.mesh.digest(), again.digest())
        self.assertEqual(self.mesh.digest(), report("ship", "ship-build.json")["meshDigest"])
        self.assertLessEqual(self.mesh.tris, 40000)

    def test_rail_on_the_painted_pixels(self):
        self.assertLess(max(abs(v) for v in self.W.rail_res), 5.0, "the painted rail is level on the wall plane")
        cam = CS.cam0()
        for x, y in self.P["railPx"]:
            A = self.W.on_plane(x, y, 0.0)
            s = self.W.sdz(A)[0]
            q = cam.project(self.W.P(s, 0.0, float(self.W.rail_z(s)))[None])[0][0]
            self.assertLess(float(np.hypot(q[0] - x, q[1] - y)), 4.0)

    def test_mast_on_deck_and_clear_of_the_band(self):
        H = self.P["hull"]
        for m in self.info["rig"]["masts"]:
            self.assertTrue(H["wallThickUU"] < m["dInUU"] < H["beamUU"] - H["wallThickUU"], m["id"])
        B = self.mesh.board()
        ext = FBB.outer_extents(CS.params()["frameBand"])
        inside = (B[:, 0] > ext["westX"]) & (B[:, 0] < ext["eastX"]) & (B[:, 1] > ext["farY"]) & (B[:, 1] < ext["nearY"])
        self.assertEqual(int((inside & (B[:, 2] < 60.0)).sum()), 0, "the hull side must not cut the frame band")


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
        # VS-8 E1 EN-20: the hang turned hangTiltDeg in the cloth plane (towards local -Y), never out of it (X)
        t = math.radians(float(self.allp["banner"].get("hangTiltDeg", 0.0)))
        self.assertEqual(info["hang"], [0.0, round(-math.sin(t), 4), round(-math.cos(t), 4)])


if __name__ == "__main__":
    unittest.main()
