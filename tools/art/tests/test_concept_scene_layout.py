"""ENV-MAPS P8.1 (track A) concept scene: the scene layout overlay (EnvLayouts/sarpedon.scene.layout.json).

  python -m pytest tools/art/tests/test_concept_scene_layout.py -q

* the overlay merges on sarpedon.layout.json (MergeOverlay twin) and passes the scene validation (roots, NoAI,
  material paths, Fab scale ranges, pivots off the map, fx anchors);
* layout_check rule 12 (check_scene): no prop of the merged layout covers a circle at any camera pose and no
  castShadow prop throws its key-light shadow on a circle, on the committed geometry proxies;
* rule 12 still fires where it must (synthetic cases: a tall post in the near band, a tree beside the frame with a
  shadow, a scene mesh turned off its authored placement) - the cell rules are not weakened;
* the contents asked by the task: island / ship / fort / palisade / piles, 12-18 trees, 20-60 rocks, 6 lanterns on
  their hosts, 2 fires, 3 cannons, the banner hanging vertically 300-325 uu, pack props with a projected look;
* P9: the frame band and the cascade placed, the cannons in the ship's ports (muzzle out of the hull side), the dock
  props clear of the frame band and the hull side, the banner flat against the hull, track B's fx plan merged
  (fires on the brazier / fort-pit anchors, mist on the cascade tiers; an unknown tier dropped, an unknown anchor an
  error), rule 12 still catches scene geometry over frame-002.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools/art/concept_scene"))
sys.path.insert(0, str(REPO / "tools/art/env_kit"))

import cs_common as CS  # noqa: E402
import frame_band_build as FBB  # noqa: E402
import layout_check as LC  # noqa: E402
import scene_layout as SL  # noqa: E402
import ship_build as SB  # noqa: E402

import numpy as np  # noqa: E402

LAY = CS.load_json(CS.SCENE_LAYOUT)
BASE = CS.load_json(CS.LAYOUTS / "sarpedon.layout.json")
PROX = LC.load_scene_proxies()


class SceneLayout(unittest.TestCase):
    def test_schema_and_validation(self):
        self.assertEqual(LAY["schema"], "unmatched.env-layout-overlay/1")
        self.assertEqual(LAY["variant"], "scene")
        self.assertEqual(LAY["boardId"], BASE["boardId"])
        for fixed in ("lights", "ground", "tray", "apron"):
            self.assertNotIn(fixed, LAY)
        self.assertEqual(SL.validate(BASE, LAY), [])

    def test_rule12_occlusion_and_shadows(self):
        res = LC.check_scene("sarpedon", overlay=LAY, proxies=PROX)
        self.assertEqual(res["errors"], [])
        self.assertGreater(res["cameras"], 500)

    def test_contents(self):
        add = {p["id"]: p for p in LAY["props"]["add"]}
        for n in ("island", "ship", "fort", "palisade", "piles", "frameband", "cascade", "cascadefoam"):
            p = add[f"scene-{n}"]
            self.assertEqual((p["yawDeg"], p["scale"]), (0.0, 1.0))
        self.assertTrue(add["scene-frameband"]["castShadow"])
        self.assertFalse(add["scene-cascade"]["castShadow"] or add["scene-cascadefoam"]["castShadow"])
        trees = [p for p in add.values() if p["id"].startswith("tree-")]
        rocks = [p for p in add.values() if p["id"].startswith("rock-")]
        self.assertTrue(12 <= len(trees) <= 18, len(trees))
        self.assertTrue(20 <= len(rocks) <= 60, len(rocks))
        lanterns = [p for p in add.values() if p["mesh"].endswith("SM_EnvCP_LanternHead")]
        self.assertEqual(len(lanterns), 6)
        self.assertEqual(len([p for p in add.values() if p["mesh"].endswith("SM_EnvCP_Cannon")]), 3)
        fires = [f for f in LAY["fx"]["add"] if f["system"].endswith("NS_Env_ConceptFire")]
        if SL.FX_PLAN.is_file():  # P9: track B's layered fires replace the P8 sprite fires
            plan = CS.load_json(SL.FX_PLAN)
            ids = {f["id"] for f in LAY["fx"]["add"]}
            self.assertEqual(fires, [])
            for f in plan["fires"] + plan.get("waterfall", []):
                self.assertIn(f["id"], ids)
        else:
            self.assertEqual(sorted(f["id"] for f in fires), ["fire-brazier", "fire-fort"])
        ban = add["banner-ship"]
        self.assertTrue(ban["mesh"].endswith("SM_Env_S_Banner"))
        length = float(ban["scale"]) * CS.params()["banner"]["lengthUU"]
        self.assertTrue(300.0 <= length <= 325.0, length)
        for p in trees + rocks + [x for x in add.values() if x["id"].startswith(("barrel-", "crate-", "coil-", "bush-"))]:
            self.assertRegex(p.get("material", ""), r"^/Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_Proj_[A-Za-z]+$", p["id"])
        for p in trees:
            if LC.frame_dist(*p["loc"][:2]) < 60.0:
                self.assertFalse(p["castShadow"], p["id"])

    def test_no_noai_and_lights_untouched(self):
        txt = CS.SCENE_LAYOUT.read_text(encoding="utf-8")
        for n in LC.NOAI_ROOTS:
            self.assertNotIn(n, txt)
        merged = LC.merge_overlay(BASE, LAY)
        self.assertEqual(merged["lights"], BASE["lights"])
        self.assertEqual(merged["ground"], BASE["ground"])


class P9Placements(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.allp = CS.params()
        cls.add = {p["id"]: p for p in LAY["props"]["add"]}
        cls.wall = SB.Wall(cls.allp["ship"])
        cls.ship = CS.load_json(CS.RUNS["ship"] / "reports" / "ship-build.json")

    def test_cannons_in_the_ports(self):
        ports = {p["cannon"]: p for p in self.ship["info"]["ports"]}
        km = SB.kit_metrics()
        for cid, pt in ports.items():
            p = self.add[cid]
            self.assertAlmostEqual(p["yawDeg"], pt["yawDeg"], places=2)
            self.assertAlmostEqual(p["scale"], pt["scale"], places=3)
            a = np.radians(p["yawDeg"])
            R = np.array([[np.cos(a), -np.sin(a), 0.0], [np.sin(a), np.cos(a), 0.0], [0.0, 0.0, 1.0]])
            axis = R @ (np.array(km["axis"]) * p["scale"]) + np.array(p["loc"])
            self.assertLess(float(np.linalg.norm(axis - np.array(pt["axisPoint"]))), 0.05, cid)
            muzzle = axis + R @ np.array([km["muzzleX"] * p["scale"], 0.0, 0.0])
            d = self.wall.sdz(muzzle)[1]
            self.assertAlmostEqual(d, -pt["protrusionUU"], delta=0.05, msg=f"{cid}: only the bare barrel leaves the hull")
            s, _, z = self.wall.sdz(muzzle)
            self.assertLess(abs(s - pt["s"]) + abs(z - pt["z"]), 0.1, f"{cid}: through the port centre")

    def test_dock_props_clear_of_band_and_hull(self):
        ext = FBB.outer_extents(self.allp["frameBand"])
        rect = np.array([[ext["westX"], ext["farY"]], [ext["eastX"], ext["farY"]], [ext["eastX"], ext["nearY"]],
                         [ext["westX"], ext["nearY"]]])
        C = self.allp["layout"]["propClearance"]
        for p in self.allp["layout"]["props"]:
            fp = LC.footprint(self.add[p["id"]])
            self.assertGreaterEqual(LC.poly_clearance(fp, rect), C["bandUU"] - 1e-6, p["id"])
            d = (fp - self.wall.F0) @ self.wall.in2
            s = (fp - self.wall.F0) @ self.wall.u2
            along = (s > self.ship["info"]["sNorth"] - C["hullUU"]) & (s < self.ship["info"]["sSouth"])
            if along.any():
                self.assertLessEqual(float(d[along].max()), -C["hullUU"] + 1e-6, p["id"])

    def test_banner_flat_against_the_hull(self):
        b = self.add["banner-ship"]
        self.assertAlmostEqual(b["yawDeg"], self.wall.out_yaw_deg(), places=2)
        d = self.wall.sdz(np.array(b["loc"], float))[1]
        self.assertAlmostEqual(d, -self.allp["layout"]["details"]["bannerOutUU"], delta=0.05)

    def test_fx_plan_merge(self):
        import tempfile
        anchors = LAY["conceptScene"]["fxAnchors"]
        plan = {"schema": SL.FX_PLAN_SCHEMA, "fires": [{"id": "f1", "system": "/Game/EnvKit/FX/NS_X", "anchor": "brazier",
                                                         "offsetUU": [0, 0, 10], "scale": 2.0}],
                "waterfall": [{"id": "m1", "system": "/Game/EnvKit/FX/NS_Y", "tier": 2, "scale": 0.5},
                              {"id": "m9", "system": "/Game/EnvKit/FX/NS_Y", "tier": 9}]}
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "plan.json"
            f.write_text(json.dumps(plan), encoding="utf-8")
            out, info = SL.fx_plan(anchors, f)
            self.assertEqual([e["id"] for e in out], ["f1", "m1"])
            self.assertEqual(info["droppedTiers"], ["m9"])
            b = anchors["brazier"]["loc"]
            self.assertEqual(out[0]["loc"], [round(b[0], 2), round(b[1], 2), round(b[2] + 10, 2)])
            self.assertEqual(out[1]["loc"], [round(v, 2) for v in anchors["falls-tier-2"]["loc"]])
            plan["fires"][0]["anchor"] = "nowhere"
            f.write_text(json.dumps(plan), encoding="utf-8")
            with self.assertRaises(SystemExit):
                SL.fx_plan(anchors, f)
            out, info = SL.fx_plan(anchors, Path(td) / "absent.json")
            self.assertIsNone(out)
            self.assertFalse(info["present"])


class Rule12StillFires(unittest.TestCase):
    """Synthetic overlays on the committed proxies: the scene rules are real checks, not waivers."""

    def overlay(self, add):
        o = copy.deepcopy(LAY)
        o["props"]["add"] = copy.deepcopy(o["props"]["add"]) + add
        return o

    def test_tall_post_in_the_near_band_covers_spaces(self):
        o = self.overlay([{"id": "t-post", "mesh": "/Game/EnvKit/Sarpedon/SM_Env_LanternPost", "loc": [0.0, 340.0, -3.0],
                           "yawDeg": 90.0, "scale": 2.0, "castShadow": False}])
        res = LC.check_scene("sarpedon", overlay=o, proxies=PROX)
        self.assertTrue(any("t-post" in e and "covers" in e for e in res["errors"]), res["errors"])

    def test_tree_beside_the_frame_must_not_cast_shadow(self):
        o = self.overlay([{"id": "t-tree", "mesh": "/Game/EnvKit/Fab/Sarpedon/SM_EnvFab_ForestSmall",
                           "loc": [-500.0, 0.0, -3.0], "yawDeg": 0.0, "scale": 0.1, "castShadow": True}])
        res = LC.check_scene("sarpedon", overlay=o, proxies=PROX)
        self.assertTrue(any("t-tree" in e and "R5" in e for e in res["errors"]), res["errors"])

    def test_scene_mesh_placement_is_fixed(self):
        o = copy.deepcopy(LAY)
        for p in o["props"]["add"]:
            if p["id"] == "scene-fort":
                p["yawDeg"] = 15.0
        res = LC.check_scene("sarpedon", overlay=o, proxies=PROX)
        self.assertTrue(any("scene-fort" in e and "board space" in e for e in res["errors"]), res["errors"])

    def test_scene_geometry_over_frame002_is_caught(self):
        prox = copy.deepcopy(PROX)
        piv = prox["FrameBand"]["pivot"]
        # a synthetic cluster on frame-002's top (local to the band's pivot)
        prox["FrameBand"]["clusters"].append([[460.0 - piv[0], 0.0 - piv[1], 5.0], [465.0 - piv[0], 0.0 - piv[1], 5.0],
                                              [462.0 - piv[0], 5.0 - piv[1], 5.0], [462.0 - piv[0], 2.0 - piv[1], 9.0]])
        res = LC.check_scene("sarpedon", overlay=LAY, proxies=prox)
        self.assertTrue(any("scene-frameband" in e and "frame-002" in e for e in res["errors"]), res["errors"])

    def test_below_plane_geometry_cannot_cover(self):
        box = [[0.0, 300.0, -200.0], [10.0, 300.0, -200.0], [0.0, 310.0, -200.0], [0.0, 300.0, -150.0]]
        import numpy as np
        self.assertEqual(len(LC.clip_above_plane(np.array(box))), 0)


if __name__ == "__main__":
    unittest.main()
