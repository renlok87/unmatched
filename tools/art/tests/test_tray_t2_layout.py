"""Tests for the shared rocky tray T2 (ASSET-TABLE-BASE-001 / 20261001-tray-t2, ENV-U10 'единая каменная подложка').

Pure Python + numpy (the convex hulls are built by Blender in tray_t2_build.py; the hull vertices are a subset of the
library point clouds, so bounds and overhangs measured on the points are exact). Ties together the build params, the
modular layout (art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/tray_t2_layout.py), the shared tray constant of
tools/art/env_kit/layout_check.py and both shipped env layouts; the committed build report is checked when present.

  python -m pytest tools/art/tests/test_tray_t2_layout.py -q
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
SCRIPTS = REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts"
RUN = REPO / "art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2"
PARAMS = RUN / "reports/tray-t2-params.json"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO / "tools/art/env_kit"))

import tray_t2_layout as LAY  # noqa: E402


def params() -> dict:
    return json.loads(PARAMS.read_text(encoding="utf-8"))


def world_points(b: dict) -> np.ndarray:
    pts = []
    for inst in b["instances"]:
        P = b["library"][inst["kind"]][inst["variant"]]["points"]
        pts.append(np.c_[P, np.ones(len(P))] @ inst["matrix"].T)
    return np.vstack(pts)[:, :3]


class TrayT2Layout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = params()
        cls.b = LAY.build(cls.P)

    def test_deterministic(self):
        again = LAY.build(params())
        self.assertEqual(len(again["instances"]), len(self.b["instances"]))
        for a, c in zip(again["instances"], self.b["instances"]):
            np.testing.assert_array_equal(a["matrix"], c["matrix"])

    def test_rigid_uniform_instances_only(self):
        lo, hi = self.P["kit"]["instance_scale"]
        for inst in self.b["instances"]:
            s, an = LAY.uniform_scale(inst["matrix"])
            self.assertAlmostEqual(an, 1.0, places=9)  # no non-uniform stretch anywhere
            self.assertGreaterEqual(s, min(lo, 0.95) - 1e-9)
            self.assertLessEqual(s, max(hi, 1.05) + 1e-9)
            R = inst["matrix"][:3, :3] / s
            np.testing.assert_allclose(R @ R.T, np.eye(3), atol=1e-9)
            self.assertGreater(np.linalg.det(R), 0.0)  # proper rotation (no mirror)
            self.assertAlmostEqual(R[2, 2], 1.0, places=9)  # yaw only

    def test_sides_cover_the_perimeter_without_stretch(self):
        per = self.b["perimeter"]
        lc = self.P["kit"]["corner_leg_uu"]
        lengths = self.P["kit"]["side_module_lengths_uu"]
        for side in per["sides"]:
            self.assertGreaterEqual(side["sumUU"], side["fillUU"])
            self.assertGreaterEqual(side["overlapUU"], 0.0)
            self.assertLess(side["overlapUU"], 25.0)
            self.assertTrue(all(a != b for a, b in zip(side["sequence"], side["sequence"][1:])))
            n = len(side["sequence"])
            self.assertAlmostEqual(side["sumUU"] - side["fillUU"], (n + 1) * side["overlapUU"], places=6)
            self.assertAlmostEqual(side["fillUU"], side["lengthUU"] - 2 * lc, places=6)
            self.assertEqual(sum(lengths[i] for i in side["sequence"]), side["sumUU"])
        corners = [p for p in per["placements"] if p["module"][0] == "corner"]
        self.assertEqual(len(corners), 4)
        hx, hy = self.b["half_bx"], self.b["half_by"]
        self.assertEqual(sorted((round(abs(c["origin"][0]), 6), round(abs(c["origin"][1]), 6)) for c in corners),
                         [(hx, hy)] * 4)

    def test_extents_match_params_and_layout_check(self):
        import layout_check as LC  # noqa: E402  (tools/art/env_kit)
        t = self.P["tray"]
        self.assertEqual({"halfX": t["half_x_ue"], "halfY": t["half_y_ue"], "offsetY": t["offset_y_ue"]}, LC.TRAY_T2)
        self.assertEqual(t["rim_uu"], LC.RIM_UU)
        self.assertEqual(t["top_z"], LC.TRAY_TOP_Z)
        self.assertEqual((self.b["half_bx"], self.b["half_by"]), (t["half_y_ue"], t["half_x_ue"]))

    def test_shipped_layouts_use_the_one_shared_tray(self):
        t = self.P["tray"]
        for key in ("marmoreal", "sarpedon"):
            lay = json.loads((LAYOUTS / f"{key}.layout.json").read_text(encoding="utf-8"))
            self.assertEqual(lay["tray"], {"halfX": t["half_x_ue"], "halfY": t["half_y_ue"], "offsetY": t["offset_y_ue"]},
                             key)

    def test_overhang_depth_and_lip_envelope_on_points(self):
        t = self.P["tray"]
        A = world_points(self.b)
        hx, hy = self.b["half_bx"], self.b["half_by"]
        ox, oy = np.abs(A[:, 0]) - hx, np.abs(A[:, 1]) - hy
        sides = max(float(ox[np.abs(A[:, 1]) < hy - 60].max()), float(oy[np.abs(A[:, 0]) < hx - 60].max()))
        self.assertLessEqual(sides, t["overhang_max_uu"])
        self.assertLessEqual(float(np.maximum(ox, oy).max()), t["overhang_corner_max_uu"])
        depth = t["top_z"] - float(A[:, 2].min())
        self.assertGreaterEqual(depth, t["depth_min_uu"])
        self.assertLessEqual(depth, t["depth_max_uu"])
        self.assertLessEqual(float(A[:, 2].max()), t["lip_top_z_max"])
        # only the cap row rises towards the top; the cliff and hanging rows stay well below it
        for inst in self.b["instances"]:
            if inst["kind"] != "cap":
                self.assertLess(inst["matrix"][2, 3], t["top_z"] - 10.0)


class TrayT2BuildReport(unittest.TestCase):
    """The committed build report of the run (skipped before the first build)."""

    def setUp(self):
        path = RUN / "reports/build-report.json"
        if not path.is_file():
            self.skipTest("no build report yet (run tray_t2_run.py)")
        self.r = json.loads(path.read_text(encoding="utf-8"))

    def test_checks_passed_and_contract(self):
        self.assertTrue(self.r["checks_passed"], {k: v for k, v in self.r["checks"].items() if not v})
        self.assertEqual(self.r["contract"]["ue"]["folder"], "/Game/PipelineCandidates/TableBase/T2")
        self.assertEqual(self.r["contract"]["ue"]["mesh"], "SM_TableBase_T2")
        g = self.r["geometry"]
        self.assertEqual(g["flatTop"]["rectUeUU"], {"halfX": 780.0, "halfY": 470.0})
        self.assertEqual(g["flatTop"]["zUU"], [-3.0])
        self.assertLessEqual(g["triangles"], 30000)
        self.assertEqual(self.r["seeThrough"]["missedTotal"], 0)

    def test_export_matches_files(self):
        import hashlib
        fbx = REPO / self.r["export"]["fbx"]
        if not fbx.is_file():
            self.skipTest("FBX not present")
        self.assertEqual(hashlib.sha256(fbx.read_bytes()).hexdigest(), self.r["export"]["sha256"])


class TrayT2UeImportPlan(unittest.TestCase):
    """tools/art/env_kit/ue_import_tray_t2.py without UE: source verification and the post-import comparison."""

    def test_check_mode_verifies_the_run(self):
        import ue_import_tray_t2 as U  # noqa: E402  (tools/art/env_kit; `unreal` is absent here)
        if not (RUN / "reports/build-report.json").is_file():
            self.skipTest("no build report yet")
        plan = U.plan(RUN)
        self.assertTrue(plan["ok"], plan)
        self.assertEqual({v["status"] for v in plan["sources"].values()}, {"verified"})
        self.assertEqual(U.ASSETS["mesh"], "/Game/PipelineCandidates/TableBase/T2/SM_TableBase_T2")
        self.assertEqual(U.ASSETS["mi"], "/Game/PipelineCandidates/TableBase/T2/MI_TableBase_T2")

    def test_compare_bounds_and_triangles(self):
        import ue_import_tray_t2 as U  # noqa: E402
        exp = {"boundsUeUU": {"min": [-802.0, -485.0, -179.5], "max": [802.0, 485.0, 1.5]}, "triangles": 18344}
        ok = U.compare({"boundsMin": [-802.2, -485.0, -179.5], "boundsMax": [802.0, 485.3, 1.5],
                        "trianglesLod0": 18300}, exp)
        self.assertTrue(ok["bounds"]["ok"] and ok["triangles"]["ok"], ok)
        x100 = U.compare({"boundsMin": [-80200.0, -48500.0, -17950.0], "boundsMax": [80200.0, 48500.0, 150.0],
                          "trianglesLod0": 15000}, exp)
        self.assertFalse(x100["bounds"]["ok"])
        self.assertFalse(x100["triangles"]["ok"])


if __name__ == "__main__":
    unittest.main()
