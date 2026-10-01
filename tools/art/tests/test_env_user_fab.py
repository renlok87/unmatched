"""ENV-MAPS P5c UserVariant: the NoAI derivatives spec (ue_import_user_fab.py --check logic, the Nanite-assembly T3D parse
of the Yoshino bake) and the user's layout variant overlays (p5c_user_overlays.py: merge twin of S08EnvLayout
MergeOverlay, idempotent, layout_check clean, main layouts free of NoAI / UserFab paths).

CPU only, no UE, no images: the committed spec (measured bounds from the UE import report) and overlay files.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRIPTS = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


UF = _load("_test_ue_import_user_fab", REPO / "tools/art/env_kit/ue_import_user_fab.py")
OV = _load("_test_p5c_user_overlays", SCRIPTS / "p5c_user_overlays.py")

T3D = ('NaniteAssemblyData=(Parts=((MeshObjectPath="/Game/Megaplant_Library/T/Instances/SKM_Twig_A.SKM_Twig_A",'
       'MaterialRemap=(0,1)),(MeshObjectPath="/Game/Megaplant_Library/T/Instances/SKM_Twig_B.SKM_Twig_B",'
       'MaterialRemap=(0,1))),Nodes=((PartIndex=0,Transform=(Rotation=(X=0.1,Y=0.2,Z=0.3,W=0.927362),'
       'Translation=(X=1.5,Y=-2.0,Z=198.7),Scale3D=(X=0.86,Y=0.86,Z=0.86)),BoneInfluences=((BoneIndex=18))),'
       '(PartIndex=1,TransformSpace=BoneRelative,Transform=(Rotation=(X=0.0,Y=0.0,Z=0.0,W=1.0),'
       'Translation=(X=-3.2e-01,Y=4.0,Z=5.0),Scale3D=(X=1.0,Y=1.0,Z=1.0)),BoneInfluences=((BoneIndex=2)))))')


def spec() -> dict:
    return UF.load_spec()


class UserFabSpecTest(unittest.TestCase):
    def test_committed_spec_valid_and_measured(self):
        data = spec()
        self.assertEqual(UF.validate_spec(data), [])
        for name, e in data["meshes"].items():
            self.assertTrue(e.get("measured"), f"{name}: no measured block")
            self.assertTrue(e["dest"].startswith(UF.ROOT))
            self.assertIn(UF.pack_of(e["source"]), UF.NOAI_ROOTS)
        bakes = {n: e for n, e in data["meshes"].items() if e["kind"] == "bake"}
        self.assertEqual(set(bakes), {"YoshinoC", "YoshinoD"})
        for n, e in bakes.items():
            self.assertLessEqual(e["measured"]["tris"], e["maxTris"], n)
            self.assertIsNotNone(e["measured"]["base"], n)

    def test_rejections(self):
        base = spec()
        cases = []
        d = copy.deepcopy(base)
        d["meshes"]["StoneCluster1"]["source"] = "/Game/Fantasy_Forest/Statick_Meshes/SM_rock_01"
        cases.append((d, "not in a NoAI pack"))
        d = copy.deepcopy(base)
        d["meshes"]["YoshinoD"]["dest"] = "/Game/EnvKit/Fab/Marmoreal/SM_UserFab_YoshinoD"
        cases.append((d, "is not /Game/EnvKit/UserFab/"))
        d = copy.deepcopy(base)
        d["materials"]["MI_UserFab_YoshinoBark"]["scalar"]["Glow"] = 1.0
        cases.append((d, "is not on the master"))
        d = copy.deepcopy(base)
        d["materials"]["MI_UserFab_StoneCluster1Wet"]["switch"]["Use Color Tint?"] = 1
        cases.append((d, "is not a bool"))
        d = copy.deepcopy(base)
        d["meshes"]["YoshinoC"]["slots"][0] = {"slot": "Bark", "material": "MI_UserFab_YoshinoBark"}
        cases.append((d, "bake slots are by material index"))
        d = copy.deepcopy(base)
        d["meshes"]["YoshinoC"]["maxTris"] = 5000000
        cases.append((d, "maxTris"))
        d = copy.deepcopy(base)
        d["noAiPacks"] = ["Megaplant_Library"]
        cases.append((d, "noAiPacks"))
        for data, needle in cases:
            errs = UF.validate_spec(data)
            self.assertTrue(any(needle in e for e in errs), f"{needle!r} not in {errs}")

    def test_spec_sha_ignores_measured(self):
        e = copy.deepcopy(spec()["meshes"]["YoshinoD"])
        a = UF.spec_sha(e)
        e["measured"]["tris"] += 1
        self.assertEqual(a, UF.spec_sha(e))
        e["maxTris"] += 1
        self.assertNotEqual(a, UF.spec_sha(e))

    def test_assembly_t3d_parse(self):
        parts, nodes = UF.parse_assembly_t3d(T3D)
        self.assertEqual([p["remap"] for p in parts], [[0, 1], [0, 1]])
        self.assertEqual(len(nodes), T3D.count("PartIndex="))
        self.assertEqual(nodes[0]["part"], 0)
        self.assertEqual(nodes[0]["space"], "Local")
        self.assertAlmostEqual(nodes[0]["loc"][2], 198.7)
        self.assertEqual(nodes[1]["space"], "BoneRelative")
        self.assertAlmostEqual(nodes[1]["loc"][0], -0.32)
        self.assertEqual(UF.static_twin(parts[0]["path"]), "/Game/Megaplant_Library/T/Instances/Twig_A")

    def test_check_passes_and_layouts_clean(self):
        self.assertEqual(UF.main(["--check"]), 0)
        errs, used = UF.check_layouts(spec(), LAYOUTS)
        self.assertEqual(errs, [])
        self.assertEqual(sorted(used), ["marmoreal", "sarpedon"])
        for key in ("marmoreal", "sarpedon"):
            text = (LAYOUTS / f"{key}.layout.json").read_text(encoding="utf-8")
            for marker in UF.NOAI_ROOTS + (UF.ROOT, "Yoshino", "StyleHex", "Megaplant"):
                self.assertNotIn(marker, text, f"{key}.layout.json")

    def test_check_layouts_rejects_raw_noai_path(self, tmp=None):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            for f in LAYOUTS.glob("*.layout.json"):
                (Path(td) / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            o = json.loads((Path(td) / "sarpedon.user.layout.json").read_text(encoding="utf-8"))
            o["props"]["replace"][0]["mesh"] = "/Game/StyleHex_Studio/Free_Packs/FREE_Stylized_Rocks_and_Stones/Meshes/SM_Stone_Cluster_1"
            (Path(td) / "sarpedon.user.layout.json").write_text(json.dumps(o), encoding="utf-8")
            errs, _ = UF.check_layouts(spec(), Path(td))
            self.assertTrue(any("raw NoAI pack path" in e for e in errs), errs)


class UserOverlayTest(unittest.TestCase):
    def test_merge_twin(self):
        base = {"props": [{"id": "a", "mesh": "/Game/EnvKit/X/SM_Env_A", "loc": [0, 0, 0], "yawDeg": 0, "scale": 1,
                           "castShadow": True}, {"id": "b", "mesh": "m", "loc": [1, 1, 0], "yawDeg": 0, "scale": 1,
                                                 "castShadow": True}],
                "fx": [{"id": "fa", "anchor": "a", "loc": [0, 0, 1]}, {"id": "fb", "anchor": "b", "loc": [0, 0, 1]}],
                "lights": []}
        m = OV.merge(base, {"props": {"remove": ["a"], "replace": [{"id": "b", "scale": 2}]},
                            "fx": {"replace": [{"id": "fb", "loc": [0, 0, 9]}]}})
        self.assertEqual([p["id"] for p in m["props"]], ["b"])
        self.assertEqual(m["props"][0]["scale"], 2)
        self.assertEqual([f["id"] for f in m["fx"]], ["fb"])
        self.assertEqual(m["fx"][0]["loc"], [0, 0, 9])
        self.assertEqual(base["props"][1]["scale"], 1)  # the base is not mutated
        for bad in ({"lights": []}, {"props": {"replace": [{"id": "b", "colour": 1}]}},
                    {"props": {"replace": [{"id": "nosuch", "scale": 1}]}}, {"props": {"add": [{"id": "b"}]}}):
            with self.assertRaises(ValueError):
                OV.merge(base, bad)

    def test_overlays_match_generator_and_pass_layout_check(self):
        self.assertEqual(OV.main(["--check"]), 0)

    def test_overlay_contents(self):
        data = spec()
        for key, plan in OV.PLAN.items():
            o = json.loads((LAYOUTS / f"{key}.{OV.VARIANT}.layout.json").read_text(encoding="utf-8"))
            self.assertEqual((o["schema"], o["map"], o["variant"]), (OV.OVERLAY_SCHEMA, key, "user"))
            for fixed in ("lights", "ground", "tray", "apron"):
                self.assertNotIn(fixed, o)
            reps = {r["id"]: r for r in o["props"]["replace"]}
            self.assertEqual(set(reps), set(plan))
            for pid, (name, _) in plan.items():
                self.assertEqual(reps[pid]["mesh"], data["meshes"][name]["dest"])
                lo, hi = data["meshes"][name]["scaleRange"]
                self.assertTrue(lo <= reps[pid]["scale"] <= hi)
        o = json.loads((LAYOUTS / "marmoreal.user.layout.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(f["id"] for f in o["fx"]["replace"]),
                         sorted(f"petals-{p}" for p in OV.PLAN["marmoreal"]))


if __name__ == "__main__":
    unittest.main()
