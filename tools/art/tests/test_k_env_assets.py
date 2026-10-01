"""Tests for the ENV-MAPS lane K Blender-made environment assets (no Tripo):

  ASSET-TABLE-BASE-001 T2b      art/pipeline-candidates/ASSET-TABLE-BASE-001/20261001-tray-t2b (chunky shared tray)
  ASSET-MAP-FRAME-002           art/pipeline-candidates/ASSET-MAP-FRAME-002/20261001-frame-v1 (heavy modular frame)
  ASSET-ENV-M-BACKWALL-001      art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/20261001-backwall-v1 (Marmoreal wall)
  ASSET-ENV-S-WATERFALL-001     art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/20261001-waterfall-v1 (Sarpedon fall)

Pure Python + numpy (system Python). Layout / geometry rules are recomputed from the params with the pure-Python layout
modules; the committed build reports and the independent FBX read-backs (tools/tripo-pipeline/blender/
check_static_prop_fbx.py, run by tools/art/env_kit/run_k_assets.py) are checked for dimensions vs targets, triangle
budgets (<= 12k per prop module, <= 40k per tray module), UVs, slots and the export files' sha256.

  python -m pytest tools/art/tests/test_k_env_assets.py -q
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PC = REPO / "art/pipeline-candidates"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
sys.path.insert(0, str(PC / "ASSET-TABLE-BASE-001/scripts"))
sys.path.insert(0, str(PC / "ASSET-MAP-FRAME-002/scripts"))
sys.path.insert(0, str(REPO / "tools/art/env_kit"))

import frame_layout as FL  # noqa: E402
import tray_t2b_layout as T2B  # noqa: E402

RUNS = {
    "tray-t2b": PC / "ASSET-TABLE-BASE-001/20261001-tray-t2b",
    "frame": PC / "ASSET-MAP-FRAME-002/20261001-frame-v1",
    "backwall": PC / "ASSET-ENV-M-BACKWALL-001/20261001-backwall-v1",
    "waterfall": PC / "ASSET-ENV-S-WATERFALL-001/20261001-waterfall-v1",
}
PARAMS = {"tray-t2b": "tray-t2b-params.json", "frame": "frame-params.json", "backwall": "backwall-params.json",
          "waterfall": "waterfall-params.json"}
BUDGET = {"tray-t2b": 40000, "frame": 12000, "backwall": 12000, "waterfall": 12000}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def params(key):
    return load(RUNS[key] / "reports" / PARAMS[key])


def report(key):
    p = RUNS[key] / "reports/build-report.json"
    return load(p) if p.is_file() else None


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def png_size(p: Path):
    data = p.read_bytes()[:24]
    assert data[:8] == b"\x89PNG\r\n\x1a\n", p
    return struct.unpack(">II", data[16:24])


# ----------------------------------------------------------------------------- shared rules for every run
class AllRuns(unittest.TestCase):
    def test_reports_pass_and_exports_match_files(self):
        for key in RUNS:
            r = report(key)
            if r is None:
                self.skipTest(f"{key}: no build report yet (run tools/art/env_kit/run_k_assets.py)")
            with self.subTest(run=key):
                self.assertTrue(r["checks_passed"], {k: v for k, v in r["checks"].items() if not v})
                self.assertEqual(r["status"], "measured")
                self.assertFalse(r["claims"]["art_accepted"])
                for ex in r["exports"]:
                    fbx = REPO / ex["fbx"]
                    self.assertTrue(fbx.is_file(), fbx)
                    self.assertEqual(sha(fbx), ex["sha256"], fbx.name)
                    self.assertLessEqual(ex["triangles"], BUDGET[key], fbx.name)
                    self.assertTrue(all(c["conforms"] for c in ex["um_fbx_v1_conformance"]), fbx.name)

    def test_independent_readback(self):
        for key in RUNS:
            r = report(key)
            if r is None:
                self.skipTest("no build report yet")
            for ex in r["exports"]:
                fbx = REPO / ex["fbx"]
                rb_path = RUNS[key] / "reports/fbx-readback" / (fbx.stem + ".json")
                with self.subTest(fbx=fbx.name):
                    self.assertTrue(rb_path.is_file(), rb_path)
                    rb = load(rb_path)
                    self.assertEqual(len(rb["mesh_objects"]), 1)
                    self.assertEqual(rb["armatures"], 0)
                    self.assertEqual(rb["triangles"], ex["triangles"])
                    self.assertIn("UVMap", rb["uv_layers"])
                    self.assertEqual(rb["object_scale"], [0.01, 0.01, 0.01])  # UnitScaleFactor 1.0 (cm numbers)
                    b = ex.get("boundsUeLocalUU") or r.get("geometry", {}).get("boundsUeUU")
                    # read-back frame = UE with Y negated
                    self.assertAlmostEqual(rb["bounds_min_uu"][0], b["min"][0], delta=0.05)
                    self.assertAlmostEqual(rb["bounds_max_uu"][0], b["max"][0], delta=0.05)
                    self.assertAlmostEqual(rb["bounds_min_uu"][1], -b["max"][1], delta=0.05)
                    self.assertAlmostEqual(rb["bounds_max_uu"][1], -b["min"][1], delta=0.05)
                    self.assertAlmostEqual(rb["bounds_min_uu"][2], b["min"][2], delta=0.05)
                    self.assertAlmostEqual(rb["bounds_max_uu"][2], b["max"][2], delta=0.05)

    def test_textures_png_at_most_2k_and_previews_exist(self):
        for key, run in RUNS.items():
            with self.subTest(run=key):
                pngs = sorted((run / "export").glob("*.png"))
                for p in pngs:
                    w, h = png_size(p)
                    self.assertLessEqual(max(w, h), 2048, p.name)
                    self.assertEqual(w, h, p.name)
                pv = run / "preview/preview.json"
                if not pv.is_file():
                    self.skipTest("no previews yet")
                for shot in load(pv)["shots"]:
                    self.assertTrue((run / "preview" / shot["file"]).is_file(), shot["file"])


# ----------------------------------------------------------------------------- T2b
class TrayT2b(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = params("tray-t2b")
        cls.b = T2B.build(cls.P)

    def test_same_top_outline_as_t2_and_layouts(self):
        import layout_check as LC
        t = self.P["tray"]
        self.assertEqual({"halfX": t["half_x_ue"], "halfY": t["half_y_ue"], "offsetY": t["offset_y_ue"]}, LC.TRAY_T2)
        self.assertEqual(t["top_z"], LC.TRAY_TOP_Z)
        self.assertEqual(t["rim_uu"], LC.RIM_UU)
        t2 = load(PC / "ASSET-TABLE-BASE-001/20261001-tray-t2/reports/tray-t2-params.json")["tray"]
        for k in ("half_x_ue", "half_y_ue", "offset_y_ue", "top_z"):
            self.assertEqual(t[k], t2[k], k)
        for key in ("marmoreal", "sarpedon"):
            self.assertEqual(load(LAYOUTS / f"{key}.layout.json")["tray"],
                             {"halfX": t["half_x_ue"], "halfY": t["half_y_ue"], "offsetY": t["offset_y_ue"]})

    def test_modular_uniform_instances(self):
        for inst in self.b["instances"]:
            s, an = T2B.uniform_scale(inst["matrix"])
            self.assertAlmostEqual(an, 1.0, places=9)
            R = inst["matrix"][:3, :3] / s
            self.assertGreater(np.linalg.det(R), 0.0)
            self.assertAlmostEqual(R[2, 2], 1.0, places=9)
        for side in self.b["perimeter"]["sides"]:
            self.assertGreaterEqual(side["sumUU"], side["fillUU"])
            self.assertGreaterEqual(side["overlapUU"], 0.0)

    def test_depth_overhang_and_boulders_on_points(self):
        t = self.P["tray"]
        A = T2B.world_points(self.b)
        depth = t["top_z"] - float(A[:, 2].min())
        self.assertGreaterEqual(depth, t["depth_min_uu"])
        self.assertLessEqual(depth, t["depth_max_uu"])
        hx, hy = self.b["half_bx"], self.b["half_by"]
        ox, oy = np.abs(A[:, 0]) - hx, np.abs(A[:, 1]) - hy
        sides = max(float(ox[np.abs(A[:, 1]) < hy - 60].max()), float(oy[np.abs(A[:, 0]) < hx - 60].max()))
        self.assertGreater(sides, 10.0)  # a real (slight) overhang of the lip
        self.assertLessEqual(sides, t["overhang_max_uu"])
        kinds = {i["kind"] for i in self.b["instances"]}
        self.assertEqual(kinds, {"cap", "boulder", "block", "spike"})
        widths = [s["w"] for s in self.b["library"]["boulder"]]
        self.assertGreaterEqual(min(widths), 70.0)  # readable boulders (T2 chunks were 36..72 wide)

    def test_report_geometry_and_vertex_colours(self):
        r = report("tray-t2b")
        if r is None:
            self.skipTest("no build report")
        g = r["geometry"]
        self.assertEqual(g["flatTop"]["rectUeUU"], {"halfX": 780.0, "halfY": 470.0})
        self.assertEqual(g["flatTop"]["zUU"], [-3.0])
        self.assertLessEqual(g["triangles"], 40000)
        self.assertTrue(all(m["triangles"] <= 40000 for m in r["kit"]["modules"]))
        self.assertEqual(r["seeThrough"]["missedTotal"], 0)
        self.assertEqual(r["roundtrip"]["color_attributes"], ["Col"])
        self.assertGreater(r["vertexColorStats"]["R_moss"]["meanAboveZ-20"], 0.4)
        self.assertLess(r["vertexColorStats"]["R_moss"]["meanBelowZ-80"], 0.05)
        sp = load(RUNS["tray-t2b"] / "reports/south-profile.json")
        self.assertEqual(sp["edgeBoardUeY"], 425.0)
        self.assertEqual(sp["xRangeUeUU"], self.P["south_profile"]["x_ue"])


# ----------------------------------------------------------------------------- frame
class MapFrame002(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.P = params("frame")
        cls.lay = FL.placements(cls.P)

    def test_same_frame_half_as_the_board_profiles(self):
        prof = load(PROFILES)
        for b in prof["boards"]:
            m = b.get("mapImage") if isinstance(b, dict) else None
            if not m:
                continue
            with self.subTest(board=b.get("id")):
                self.assertEqual(m["srcSize"], self.P["map"]["src_px"])
                self.assertAlmostEqual(m["uuPerPx"], self.P["map"]["uu_per_px"], places=7)
                self.assertEqual(m.get("frameUU", 24), self.P["map"]["frame_uu"])
        hx, hy = FL.map_half(self.P)
        self.assertAlmostEqual(hx, 445.6667, places=3)
        self.assertAlmostEqual(hy, 288.6667, places=3)
        fx, fy = FL.frame_half(self.P)
        self.assertAlmostEqual(fx, 469.6667, places=3)
        self.assertAlmostEqual(fy, 312.6667, places=3)

    def test_exact_modular_fit_no_stretch(self):
        self.assertTrue(self.lay["exactFit"])
        self.assertEqual(self.lay["sides"]["near"]["segments"], 5)
        self.assertEqual(self.lay["sides"]["east"]["segments"], 3)
        mods = [i["module"] for i in self.lay["instances"]]
        self.assertEqual(mods.count("Corner"), 4)
        self.assertEqual(mods.count("Mid"), 4)
        for i in self.lay["instances"]:
            self.assertAlmostEqual(i["scaleX"], 1.0, places=5)
        # every mid bracket sits on its side's midpoint (x = 0 on near/far, y = 0 on east/west)
        seg = self.P["modules"]["segment_uu"]
        for i in self.lay["instances"]:
            if i["module"] != "Mid":
                continue
            c, s = math.cos(math.radians(i["yawDeg"])), math.sin(math.radians(i["yawDeg"]))
            mid = (i["loc"][0] + c * seg / 2, i["loc"][1] + s * seg / 2)
            self.assertAlmostEqual(mid[0] if i["id"].startswith(("near", "far")) else mid[1], 0.0, places=3)

    def test_profile_is_1p6x_taller_and_inside_frame_half(self):
        pb = FL.all_points_bounds(self.P)
        self.assertEqual(pb["woodW"], [0.0, 24.0])
        self.assertAlmostEqual((pb["woodZ"][1] - pb["woodZ"][0]) / 14.0, 1.6, places=3)
        self.assertGreaterEqual(pb["ironW"][0], 0.0)  # no iron over the map opening
        self.assertGreater(abs(FL.profile_area(self.P["profile"]["points"])), 24.0 * 14.0)

    def test_report(self):
        r = report("frame")
        if r is None:
            self.skipTest("no build report")
        self.assertEqual(len(r["exports"]), 4)
        for ex in r["exports"]:
            self.assertEqual(ex["roundtrip"]["material_slots"], ["M_MapFrame002_Wood", "M_MapFrame002_Iron"])
            self.assertEqual(ex["openingPenetrationUU"], 0.0)
        a = r["assembled"]
        self.assertEqual(a["verticesInsideMapOpening"], 0)
        self.assertLess(a["ironBeyondFrameHalfUU"], 2.5)  # strap 0.9 + rivet 1.1 on the outer face
        for o in r["mapOcclusionUU"].values():
            self.assertLessEqual(o["newFrameUU"], o["currentFrameUU"])
        lay = load(RUNS["frame"] / "reports/frame-layout.json")
        self.assertEqual(len(lay["instances"]), 20)


# ----------------------------------------------------------------------------- back wall
class BackWall(unittest.TestCase):
    def test_modules_match_the_arcade_row(self):
        P = params("backwall")
        lay = load(LAYOUTS / "marmoreal.layout.json")
        arc = sorted(p["loc"][0] for p in lay["props"] if p["mesh"].endswith("SM_Env_ArcadeBay"))
        self.assertEqual(arc, P["layout_source"]["arcade_x"])
        self.assertAlmostEqual(arc[1] - arc[0], P["modules"]["Bay_Door"]["width"], places=6)
        self.assertAlmostEqual(arc[1] - arc[0], P["modules"]["Bay_Windows"]["width"], places=6)
        scale = {p["loc"][0]: p["scale"] for p in lay["props"] if p["mesh"].endswith("SM_Env_ArcadeBay")}
        self.assertTrue(all(s == P["layout_source"]["arcade_scale"] for s in scale.values()))
        portal = next(p for p in lay["props"] if p["mesh"].endswith("SM_Env_Portal"))
        self.assertAlmostEqual(P["modules"]["Centre"]["width"], 128.278 * portal["scale"], delta=0.1)

    def test_report(self):
        r = report("backwall")
        if r is None:
            self.skipTest("no build report")
        P = params("backwall")
        self.assertEqual(len(r["exports"]), 3)
        for ex in r["exports"]:
            b = ex["boundsUeLocalUU"]
            M = P["modules"][ex["module"]]
            self.assertAlmostEqual(b["size"][1], M["width"], places=2)
            self.assertAlmostEqual(b["max"][2], M["height"], places=2)
            self.assertEqual(ex["roundtrip"]["material_slots"], ["M_Env_BackWall"])
            self.assertGreaterEqual(ex["uvRange"][0], 0.0)
            self.assertLessEqual(ex["uvRange"][1], 1.0)
        ew = r["emissiveWindow"]
        self.assertGreaterEqual(ew["glowInsideFraction"], 0.99)
        self.assertLessEqual(ew["otherInsideFraction"], 0.001)
        for name in ("BC", "N", "ORM", "E"):
            p = REPO / r["textures"][name]["path"]
            self.assertEqual(sha(p), r["textures"][name]["sha256"])
        lay = load(RUNS["backwall"] / "reports/backwall-layout.json")
        self.assertEqual(len(lay["props"]), 5)
        for p in lay["props"]:
            self.assertEqual(p["loc"][2], -3.0)  # props stand on the tray top (layout_check rule)
            self.assertEqual(p["yawDeg"], 90.0)


# ----------------------------------------------------------------------------- waterfall
class Waterfall(unittest.TestCase):
    def test_entry_matches_the_sarpedon_layout(self):
        P = params("waterfall")
        g = load(LAYOUTS / "sarpedon.layout.json")["ground"]
        fall = next(f for f in g["waterfalls"] if f["id"] == P["source_entry"]["id"])
        for k in ("x0", "x1", "y", "topZ", "spillUU"):
            self.assertEqual(fall[k], P["source_entry"][k], k)

    def test_report(self):
        r = report("waterfall")
        if r is None:
            self.skipTest("no build report")
        P = params("waterfall")
        sp = REPO / P["south_profile"]
        self.assertEqual(sha(sp), r["southProfile"]["sha256"])  # built against the current T2b
        sh = r["sheet"]
        self.assertTrue(120.0 <= sh["dropUU"] <= 200.0)
        self.assertGreaterEqual(sh["builtWorstMarginUU"], 0.0)
        self.assertAlmostEqual(sh["topWidthUU"], P["source_entry"]["x1"] - P["source_entry"]["x0"], places=3)
        names = {e["name"]: e for e in r["exports"]}
        self.assertEqual(set(names), {"SM_Env_S_WaterfallLip", "SM_Env_S_Waterfall", "SM_Env_S_WaterfallFoam",
                                      "SM_Env_S_SeaRing"})
        self.assertEqual(names["SM_Env_S_Waterfall"]["uv"]["UVMap"]["min"], [0.0, 0.0])
        self.assertEqual(names["SM_Env_S_Waterfall"]["uv"]["UVMap"]["max"], [1.0, 1.0])
        self.assertIn("UV1", names["SM_Env_S_Waterfall"]["roundtrip"]["uv_layers"])
        self.assertEqual(names["SM_Env_S_WaterfallFoam"]["roundtrip"]["material_slots"],
                         ["M_EnvWaterfall_Foam", "M_EnvWaterfall_Mist"])
        self.assertEqual(names["SM_Env_S_SeaRing"]["roundtrip"]["color_attributes"], ["Col"])
        self.assertEqual(names["SM_Env_S_WaterfallLip"]["roundtrip"]["material_slots"], ["M_TableBase_T2b"])
        lip_front = r["lip"]["frontXUU"]
        self.assertGreaterEqual(lip_front, r["southProfile"]["topBandOutwardUU"])
        lay = load(RUNS["waterfall"] / "reports/waterfall-layout.json")
        xc = (P["source_entry"]["x0"] + P["source_entry"]["x1"]) / 2
        self.assertAlmostEqual(lay["fallPieces"]["loc"][0], xc, places=3)
        self.assertEqual(lay["fallPieces"]["loc"][1], 425.0)


if __name__ == "__main__":
    unittest.main()
