"""Tests for tools/art/env_kit/ue_import_map_frame.py (ENV-MAPS P5 track C, concept review gap 9 full).

Plain Python (no UE): the source verification of the committed lane-K run ASSET-MAP-FRAME-002/20261001-frame-v1, the
committed frame-layout.json against frame_layout.py (the C++ S08MapFrame002Layout is checked against the same file by
the automation test Unmatched.S08.BoardArt.MapFrameLayout), the slot plan by name, the bounds / triangle comparison, the
UE naming contract shared with S08BoardArt.h, and the iron look (frame-iron-look.json) separating the iron from the
darker P4 frame wood in texture space.

  python -m pytest tools/art/tests/test_map_frame_import.py -q
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
sys.path.insert(0, str(REPO / "art" / "pipeline-candidates" / "ASSET-MAP-FRAME-002" / "scripts"))

import ue_import_map_frame as MF  # noqa: E402

HEADER = REPO / "unreal" / "Unmatched" / "Source" / "Unmatched" / "S08" / "S08BoardArt.h"


class Sources(unittest.TestCase):
    def test_committed_run_verifies(self):
        p = MF.plan(MF.RUN_DEFAULT, MF.LOOK_DEFAULT)
        self.assertTrue(p["ok"], json.dumps({k: v for k, v in p.items() if k != "sources"}, default=str)[:2000])
        self.assertEqual(sorted(p["sources"]), sorted([f"fbx:{m}" for m in MF.MODULES] + [f"tex:{k}" for k in MF.TEXTURE_KEYS]))
        self.assertTrue(all(s["status"] == "verified" for s in p["sources"].values()))
        for m in MF.MODULES:
            e = p["expected"][m]
            self.assertTrue(e["boundsUeUU"] and e["triangles"], m)
            self.assertEqual(e["slots"], [MF.WOOD_SLOT, MF.IRON_SLOT], m)
        self.assertEqual({m: p["expected"][m]["iron"] for m in MF.MODULES},
                         {"Corner": True, "SegA": False, "SegB": False, "SegMid": True})
        self.assertTrue(p["layout"]["ok"])
        params = p["look"]["params"]
        import env_prop_look as L
        self.assertEqual(set(params["vector"]), set(L.VECTOR_DEFAULTS))
        self.assertEqual(set(params["scalar"]), set(L.SCALAR_DEFAULTS))

    def test_tampered_texture_is_never_imported(self):
        with tempfile.TemporaryDirectory() as d:
            run = Path(d) / "run"
            shutil.copytree(MF.RUN_DEFAULT / "reports", run / "reports")
            shutil.copytree(MF.RUN_DEFAULT / "export", run / "export")
            bc = run / "export" / f"{MF.TEX}_BC.png"
            bc.write_bytes(bc.read_bytes() + b"x")
            p = MF.plan(run, run / "reports" / MF.LOOK_DEFAULT.name)
            self.assertFalse(p["ok"])
            self.assertEqual(p["sources"]["tex:BC"]["status"], "mismatch")
            (run / "export" / f"{MF.MESH['Corner']}.fbx").unlink()
            self.assertEqual(MF.plan(run, run / "reports" / MF.LOOK_DEFAULT.name)["sources"]["fbx:Corner"]["status"],
                             "missing")


class Layout(unittest.TestCase):
    def test_committed_layout_equals_frame_layout_py(self):
        import frame_layout
        params = json.loads((MF.RUN_DEFAULT / "reports" / "frame-params.json").read_text(encoding="utf-8"))
        fresh = frame_layout.placements(params)
        committed = json.loads((MF.RUN_DEFAULT / "reports" / "frame-layout.json").read_text(encoding="utf-8"))
        self.assertEqual([i["id"] for i in fresh["instances"]], [i["id"] for i in committed["instances"]])
        for a, b in zip(fresh["instances"], committed["instances"]):
            self.assertEqual(a["module"], b["module"], a["id"])
            self.assertEqual(a["yawDeg"], b["yawDeg"], a["id"])
            for x, y in zip(a["loc"], b["loc"]):
                self.assertAlmostEqual(x, y, places=3)
        self.assertTrue(committed["exactFit"])
        s = MF.layout_summary(committed)
        self.assertTrue(s["ok"], s)
        self.assertEqual(s["modules"], {"Corner": 4, "A": 4, "B": 8, "Mid": 4})

    def test_layout_summary_rejects_a_broken_layout(self):
        committed = json.loads((MF.RUN_DEFAULT / "reports" / "frame-layout.json").read_text(encoding="utf-8"))
        broken = json.loads(json.dumps(committed))
        broken["instances"] = broken["instances"][:-1]
        self.assertFalse(MF.layout_summary(broken)["ok"])
        stretched = json.loads(json.dumps(committed))
        stretched["instances"][5]["scaleX"] = 1.05
        self.assertFalse(MF.layout_summary(stretched)["ok"])


class UeSideWorldFree(unittest.TestCase):
    def test_slot_plan_by_name(self):
        self.assertEqual(MF.slot_plan([MF.WOOD_SLOT, MF.IRON_SLOT]), {"slots": {0: "wood", 1: "iron"}, "fallback": False})
        self.assertEqual(MF.slot_plan([MF.IRON_SLOT, MF.WOOD_SLOT]), {"slots": {0: "iron", 1: "wood"}, "fallback": False})
        self.assertEqual(MF.slot_plan([MF.WOOD_SLOT]), {"slots": {0: "wood"}, "fallback": False})  # SegA / SegB
        self.assertEqual(MF.slot_plan([MF.WOOD_SLOT + "_Skin"]), {"slots": {0: "wood"}, "fallback": False})
        self.assertEqual(MF.slot_plan(["Material", "Material_1"]), {"slots": {0: "wood", 1: "iron"}, "fallback": True})
        self.assertEqual(MF.slot_plan([]), {"slots": {}, "fallback": True})

    def test_compare_bounds_and_triangles(self):
        exp = {"boundsUeUU": {"min": [0.0, 0.0, -10.0], "max": [157.0, 24.0, 12.742]}, "triangles": 584}
        good = {"boundsMin": [0.0, 0.0, -10.0], "boundsMax": [157.2, 24.0, 12.74], "trianglesLod0": 582}
        r = MF.compare(good, exp)
        self.assertTrue(r["bounds"]["ok"] and r["triangles"]["ok"])
        scaled = {"boundsMin": [0.0, 0.0, -1000.0], "boundsMax": [15700.0, 2400.0, 1274.2], "trianglesLod0": 584}
        self.assertFalse(MF.compare(scaled, exp)["bounds"]["ok"])  # a x100 import is caught
        self.assertFalse(MF.compare(dict(good, trianglesLod0=500), exp)["triangles"]["ok"])

    def test_naming_contract_matches_the_cpp_header(self):
        h = HEADER.read_text(encoding="utf-8")
        for m in MF.MODULES:
            asset = MF.ASSETS[f"mesh:{m}"]
            self.assertIn('TEXT("%s.%s")' % (asset, asset.rsplit("/", 1)[1]), h, m)
        mi = MF.ASSETS["mi"]
        self.assertIn('Frame002IronMaterialPath = TEXT("%s.%s")' % (mi, mi.rsplit("/", 1)[1]), h)
        self.assertIn('Frame002WoodSlot = TEXT("%s")' % MF.WOOD_SLOT, h)
        self.assertIn('Frame002IronSlot = TEXT("%s")' % MF.IRON_SLOT, h)
        seg = float(re.search(r"Frame002SegmentUU = ([0-9.]+);", h).group(1))
        leg = float(re.search(r"Frame002CornerLegUU = ([0-9.]+);", h).group(1))
        params = json.loads((MF.RUN_DEFAULT / "reports" / "frame-params.json").read_text(encoding="utf-8"))
        self.assertEqual(seg, params["modules"]["segment_uu"])
        self.assertAlmostEqual(leg, params["modules"]["corner_leg_uu"], places=6)
        self.assertEqual(float(re.search(r"Frame002FrameUU = ([0-9.]+)f;", h).group(1)), params["map"]["frame_uu"])
        wood = REPO / "tools" / "art" / "map_surface" / "ue_import_map_surface.py"
        self.assertIn(f'FRAME_WOOD_NAME = "{MF.WOOD_MATERIAL.rsplit("/", 1)[1]}"', wood.read_text(encoding="utf-8"))


class IronLook(unittest.TestCase):
    def test_look_file_valid(self):
        look = MF.load_look(MF.LOOK_DEFAULT)
        self.assertEqual(look["master"], MF.ENV_MASTER)
        p = MF.iron_params(look)
        self.assertLessEqual(p["scalar"]["RoughnessMax"], 0.8)
        self.assertEqual(p["scalar"]["EmissiveIntensity"], 0.0)  # the frame is not a light source

    def test_iron_separates_from_the_frame_wood(self):
        look = MF.load_look(MF.LOOK_DEFAULT)
        tuned = MF.iron_separation(look)
        neutral = MF.iron_separation(None)
        self.assertTrue(tuned["ok"], tuned)
        self.assertFalse(neutral["ok"], neutral)  # the p5k open issue: the Blender preview look does not separate
        self.assertGreater(tuned["lumaRatio"], 2.0 * neutral["lumaRatio"])
        self.assertLess(tuned["ironRoughnessMean"], neutral["ironRoughnessMean"] - 0.15)
        self.assertLess(tuned["ironSaturation"], tuned["woodSaturation"] / 2)  # cool steel against warm wood


if __name__ == "__main__":
    unittest.main()
