"""ENV-MAPS P8 track B (docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md section 4 P8.2): plain-Python tests of
tools/art/concept_scene/ue_scene_material.py (M_EnvScene contract, the C0 projection mirror, the MI plan, DXC) and
tools/art/concept_scene/ue_import_concept_scene.py (--check: the manifest schema of the track interface, sources and
sha256, the scene layout vs the profile's lit3d block), plus the shipped lit3d profile block.

  python -B -m pytest -q tools/art/tests/test_ue_concept_scene.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "concept_scene"))
sys.path.insert(0, str(REPO / "tools" / "art" / "concept_paste"))
import ue_concept_material as CPM  # noqa: E402
import ue_import_concept_scene as IMP  # noqa: E402
import ue_scene_material as SM  # noqa: E402

PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class MaterialContract(unittest.TestCase):
    def test_check_passes(self):
        report, errors = SM.check()
        self.assertEqual(errors, [])
        self.assertIn(report["hlsl"]["status"], ("ok", "skipped"))
        self.assertEqual(report["mirrorMaxUvErr"], 0.0)

    def test_header_names(self):
        hc = SM.header_constants()
        self.assertEqual(hc["SceneMaterialPath"], SM.MATERIAL_PATH)
        self.assertEqual(hc["SceneCollectionPath"], SM.MPC_PATH)
        self.assertEqual((hc["SceneLiveParamName"], hc["SceneEmissiveParamName"]), (SM.MPC_LIVE, SM.MPC_EMISSIVE))
        self.assertEqual(hc["LightsOffFlagName"], "ArtPreviewLightsOff")

    def test_every_pin_has_a_source_and_is_used(self):
        params = set(SM.TEXTURES) | set(SM.SCALARS) | set(SM.VECTORS) | {"WP", "VN", "UV", "OP", "Time", "Live", "Emissive"}
        for node, (dim, pins, code) in SM.NODES.items():
            self.assertIn(dim, (1, 3), node)
            for pin, typ in pins:
                self.assertIn(pin, params, (node, pin))
                self.assertIn(pin, code, (node, pin))
                if pin in SM.TEXTURES:
                    self.assertEqual(typ, "Texture2D")
                    self.assertIn(f"{pin}Sampler", code)

    def test_projection_mirror_equals_the_paste(self):
        block = SM.sarpedon_block()
        vec = dict(SM.camera_vectors(block), AlbedoRect=tuple(block["rectB"]))
        fh = (445.6667 + 24, 288.6667 + 24)
        rnd = random.Random(8)
        for _ in range(200):
            w = (rnd.uniform(-1600, 1600), rnd.uniform(-1200, 900), rnd.uniform(-300, 300))
            a = SM.scene_sample(vec, {"Projected": 1.0}, w, (0.0, 0.0, 1.0))
            b = CPM.shader_sample(block, fh, w)
            if not b["inFront"]:
                continue
            self.assertAlmostEqual(a["uv"][0], b["uvB"][0], places=9)
            self.assertAlmostEqual(a["uv"][1], b["uvB"][1], places=9)
            self.assertEqual(bool(a["inside"]), b["insideB"])

    def test_facing_and_routes(self):
        vec = dict(SM.camera_vectors(SM.sarpedon_block()), AlbedoRect=SM.ALBEDO_DEFAULT_RECT)
        p = (-700.0, 350.0, -3.0)
        cam = CPM.Camera(SM.sarpedon_block())
        to_cam = [c - x for c, x in zip(cam.pos, p)]
        n = math.sqrt(sum(v * v for v in to_cam))
        facing_cam = tuple(v / n for v in to_cam)
        self.assertAlmostEqual(SM.scene_sample(vec, {"Projected": 1.0}, p, facing_cam)["weight"], 1.0, places=9)
        self.assertEqual(SM.scene_sample(vec, {"Projected": 1.0}, p, tuple(-v for v in facing_cam))["weight"], 0.0)
        self.assertEqual(SM.scene_sample(vec, {"Projected": 0.0}, p, facing_cam)["weight"], 0.0)
        self.assertAlmostEqual(SM.scene_sample(vec, {"Projected": 1.0, "ProjStrength": 0.25}, p, facing_cam)["weight"], 0.25)
        # far outside the plate: own colour
        self.assertEqual(SM.scene_sample(vec, {"Projected": 1.0}, (9000.0, 0.0, 0.0), (0.0, 0.0, 1.0))["inside"], 0.0)

    def test_compile_detects_errors(self):
        if SM.compile_check()["status"] == "skipped":
            self.skipTest("no DXC")
        dim, pins, code = SM.NODES["SceneWind"]
        saved = SM.NODES["SceneWind"]
        try:
            SM.NODES["SceneWind"] = (dim, pins, code.replace("pow(h, 1.5)", "pow(h)"))
            self.assertEqual(SM.compile_check()["status"], "failed")
        finally:
            SM.NODES["SceneWind"] = saved


def synthetic_manifest() -> dict:
    d = IMP.DERIVED_REL
    return {"schema": IMP.SCHEMA, "map": "sarpedon",
            "meshes": [{"name": "Island", "fbx": "art/pipeline-candidates/ASSET-ENV-S-ISLAND-001/20261002-v1/export/SM_Env_S_Island.fbx",
                        "ue": f"{IMP.UE_DIR}/SM_Env_S_Island", "tris": 38000, "castShadow": True, "lumenGI": True,
                        "textures": {"BC": f"{d}/T_Env_S_Island_BC.png", "N": f"{d}/T_Env_S_Island_N.png",
                                     "ORM": f"{d}/T_Env_S_Island_ORM.png"}, "sha256": {}},
                       {"name": "Ship", "fbx": "art/pipeline-candidates/ASSET-ENV-S-SHIP-001/20261002-v1/export/SM_Env_S_Ship.fbx",
                        "ue": f"{IMP.UE_DIR}/SM_Env_S_Ship", "tris": 39000, "castShadow": True, "lumenGI": False,
                        "textures": {"BC": f"{d}/T_Env_S_Ship_BC.png"}, "sha256": {},
                        "material": {"scalars": {"Roughness": 0.85}}}],
            "projected": {"albedo": f"{d}/T_Env_S_AlbedoC0.png", "ue": f"{IMP.UE_DIR}/T_Env_S_AlbedoC0",
                          "rectC0Px": [-384, -216, 2688, 1512], "sha256": ""},
            "layout": IMP.LAYOUT_REL}


def scene_overlay(ship_cast=True) -> dict:
    return {"schema": IMP.OVERLAY_SCHEMA, "map": "sarpedon", "variant": "scene",
            "props": {"add": [
                {"id": "island", "mesh": f"{IMP.UE_DIR}/SM_Env_S_Island", "loc": [0, 0, -3]},
                {"id": "ship-hull", "mesh": f"{IMP.UE_DIR}/SM_Env_S_Ship", "loc": [900, 0, -3], "castShadow": ship_cast},
                {"id": "tree-1", "mesh": "/Game/StylizedForest/Meshes/SM_Tree_01", "loc": [-700, 0, -3],
                 "material": f"{IMP.UE_DIR}/MI_EnvScene_Proj_Foliage"}]}}


class ImportCheck(unittest.TestCase):
    """validate() on a synthetic worktree (no git): the sources, their sha256, the layout, the profile's lit3d."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self.man = synthetic_manifest()
        for m in self.man["meshes"]:
            for rel in [m["fbx"]] + list(m["textures"].values()):
                data = f"fake {rel}".encode()
                (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
                (self.repo / rel).write_bytes(data)
                m["sha256"][rel] = sha(data)
        alb = self.man["projected"]["albedo"]
        (self.repo / alb).write_bytes(b"fake albedo")
        self.man["projected"]["sha256"] = sha(b"fake albedo")
        self.lit3d = {"casters": ["island*", "ship*"], "giOff": ["ship*"],
                      "required": [SM.MATERIAL_PATH, f"{IMP.UE_DIR}/SM_Env_S_Island"]}
        self.write_layout(scene_overlay())

    def tearDown(self):
        self.tmp.cleanup()

    def write_layout(self, doc):
        p = self.repo / IMP.LAYOUT_REL
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc), encoding="utf-8")

    def run_validate(self, man=None, lit3d=None):
        return IMP.validate(man or self.man, self.repo, check_git=False, lit3d=lit3d if lit3d is not None else self.lit3d)

    def test_valid(self):
        report, errors = self.run_validate()
        self.assertEqual(errors, [])
        self.assertEqual(report["layout"]["placed"], {"Island": 1, "Ship": 1})
        self.assertEqual(report["layout"]["instancedManifestTris"], 77000)
        self.assertEqual(report["layout"]["otherMeshes"], ["/Game/StylizedForest/Meshes/SM_Tree_01"])
        self.assertTrue(all(f["sha256Ok"] for f in report["files"].values()))

    def expect(self, mutate, fragment, lit3d=None):
        man = copy.deepcopy(self.man)
        mutate(man)
        _report, errors = self.run_validate(man, lit3d)
        self.assertTrue(any(fragment in e for e in errors), (fragment, errors))

    def test_rejections(self):
        d = IMP.DERIVED_REL
        self.expect(lambda m: m.update(schema="x"), "schema")
        self.expect(lambda m: m["meshes"][0].update(ue="/Game/EnvMaps/Sarpedon/Scene/SM_Island"), "ue '/Game/EnvMaps/Sarpedon/Scene/SM_Island'")
        self.expect(lambda m: m["meshes"][0].update(name="island"), "name must be")
        self.expect(lambda m: m["meshes"][0].update(tris=41000), "tris 41000")
        self.expect(lambda m: m["meshes"][0].update(castShadow="yes"), "castShadow must be a bool")
        self.expect(lambda m: m["meshes"][0]["textures"].update(BC="art/T_Env_S_Island_BC.png"), "textures.BC")
        self.expect(lambda m: m["meshes"][0]["textures"].update(AO=f"{d}/T_Env_S_Island_AO.png"), "texture key AO")
        self.expect(lambda m: m["meshes"][1].update(textures={}), "textures needs at least BC")
        self.expect(lambda m: m["meshes"][0]["sha256"].pop(m["meshes"][0]["fbx"]), "no sha256")
        self.expect(lambda m: m["meshes"][0]["sha256"].update({m["meshes"][0]["fbx"]: "0" * 64}), "differs from the manifest")
        self.expect(lambda m: m["projected"].update(rectC0Px=[0, 0, 0, 10]), "rectC0Px")
        self.expect(lambda m: m["projected"].update(ue="/Game/EnvMaps/T_Albedo"), "projected.ue")
        self.expect(lambda m: m.update(layout="x.json"), "layout 'x.json'")
        self.expect(lambda m: m["meshes"].append(copy.deepcopy(m["meshes"][0])), "duplicate name")
        self.expect(lambda m: None, "neither M_EnvScene nor a manifest mesh",
                    lit3d=dict(self.lit3d, required=[f"{IMP.UE_DIR}/SM_Env_S_Fort"]))

    def test_missing_source(self):
        (self.repo / self.man["meshes"][0]["textures"]["N"]).unlink()
        _r, errors = self.run_validate()
        self.assertTrue(any("source missing" in e for e in errors), errors)
        _r, errors = IMP.validate(self.man, self.repo, check_files=False, check_git=False, lit3d=self.lit3d)
        self.assertEqual(errors, [])

    def test_layout_against_the_profile(self):
        # a manifest caster placed with castShadow false needs a lit3d caster pattern
        self.write_layout(scene_overlay(ship_cast=False))
        _r, errors = self.run_validate(lit3d=dict(self.lit3d, casters=["island*"]))
        self.assertTrue(any("castShadow false" in e for e in errors), errors)
        _r, errors = self.run_validate()
        self.assertEqual(errors, [])
        # lumenGI false (Ship) needs a giOff pattern
        _r, errors = self.run_validate(lit3d=dict(self.lit3d, giOff=[]))
        self.assertTrue(any("needs a lit3d giOff pattern" in e for e in errors), errors)
        # a material override must be a planned MI
        doc = scene_overlay()
        doc["props"]["add"][2]["material"] = f"{IMP.UE_DIR}/MI_EnvScene_Proj_Nope"
        self.write_layout(doc)
        _r, errors = self.run_validate()
        self.assertTrue(any("not an MI of ue_scene_material.mi_plan" in e for e in errors), errors)
        # an overlay cannot change the light budget / ground
        doc = scene_overlay()
        doc["lights"] = []
        self.write_layout(doc)
        _r, errors = self.run_validate()
        self.assertTrue(any("cannot change 'lights'" in e for e in errors), errors)

    def test_triangle_budget(self):
        doc = scene_overlay()
        doc["props"]["add"] += [{"id": f"ship-{i}", "mesh": f"{IMP.UE_DIR}/SM_Env_S_Ship", "loc": [900, 50 * i, -3]}
                                for i in range(11)]
        self.write_layout(doc)
        _r, errors = self.run_validate()
        self.assertTrue(any("> 450000 (G8)" in e for e in errors), errors)

    def test_cli(self):
        path = Path(self.tmp.name) / "m.json"
        path.write_text(json.dumps({"schema": "x"}), encoding="utf-8")
        self.assertEqual(IMP.main(["--check", "--manifest", str(path), "--no-git", "--report", str(Path(self.tmp.name) / "r.json")]), 1)
        self.assertEqual(IMP.main(["--check", "--manifest", str(Path(self.tmp.name) / "none.json"), "--no-git",
                                   "--report", str(Path(self.tmp.name) / "r2.json")]), 1)
        rep = load(Path(self.tmp.name) / "r2.json")
        self.assertIn("missing", rep["errors"][0])

    def test_mi_plan_from_the_manifest(self):
        plan = {m["name"]: m for m in SM.mi_plan(self.man)}
        island = plan["MI_Env_S_Island"]
        self.assertEqual(island["route"], "baked")
        self.assertEqual(island["textures"]["BC"], f"{IMP.UE_DIR}/T_Env_S_Island_BC")
        self.assertEqual((island["scalars"]["Projected"], island["scalars"]["UseORM"], island["scalars"]["UseNormal"]), (0.0, 1.0, 1.0))
        ship = plan["MI_Env_S_Ship"]
        self.assertEqual((ship["scalars"]["UseORM"], ship["scalars"]["UseNormal"], ship["scalars"]["Roughness"]), (0.0, 0.0, 0.85))
        foliage = plan["MI_EnvScene_Proj_Foliage"]
        self.assertEqual(foliage["parent"], SM.MASKED_PATH)
        self.assertEqual(foliage["textures"]["Albedo"], f"{IMP.UE_DIR}/T_Env_S_AlbedoC0")
        self.assertEqual(foliage["vectors"]["AlbedoRect"], (-384.0, -216.0, 2688.0, 1512.0))
        self.assertGreater(foliage["scalars"]["WindAmp"], 0.0)
        self.assertIn(SM.LANTERN_GLASS, plan)
        self.assertGreater(plan[SM.LANTERN_GLASS]["scalars"]["EmissiveStrength"], 0.0)
        # manifest looks replace the defaults
        man = dict(self.man, looks=[{"name": "Bark", "masked": False, "bc": "/Game/X/T_Bark", "scalars": {}, "vectors": {}}])
        names = [m["name"] for m in SM.mi_plan(man)]
        self.assertIn("MI_EnvScene_Proj_Bark", names)
        self.assertNotIn("MI_EnvScene_Proj_Rock", names)

    def test_mi_plan_tune(self):
        """P8.3: scene-tune.sarpedon.json is merged last ("*" then the name; vectorsMul scales a planned rgb)."""
        man = dict(self.man, looks=[{"name": "Rock", "masked": False, "bc": None, "scalars": {},
                                     "vectors": {"FallbackTint": [0.2, 0.4, 0.6, 1.0]}}])
        tune = {"baked": {"*": {"vectors": {"BakedTint": [0.5, 0.5, 0.5, 1.0]}, "scalars": {"NormalStrength": 2.0}},
                          "Island": {"vectors": {"BakedTint": [0.6, 0.5, 0.4, 1.0]}}},
                "looks": {"*": {"vectors": {"AlbedoGain": [0.4, 0.4, 0.4, 1.0]}, "vectorsMul": {"FallbackTint": [0.5, 0.5, 0.5]}}},
                "lanternHead": {"parent": "/Game/EnvKit/ConceptPaste/MI_EnvCP_LanternHead", "scalars": {"EmissiveIntensity": 60.0}}}
        plan = {m["name"]: m for m in SM.mi_plan(man, tune=tune)}
        self.assertEqual(plan["MI_Env_S_Island"]["vectors"]["BakedTint"], (0.6, 0.5, 0.4, 1.0))
        self.assertEqual(plan["MI_Env_S_Ship"]["vectors"]["BakedTint"], (0.5, 0.5, 0.5, 1.0))
        self.assertEqual(plan["MI_Env_S_Ship"]["scalars"]["NormalStrength"], 2.0)
        rock = plan["MI_EnvScene_Proj_Rock"]
        self.assertEqual(rock["vectors"]["AlbedoGain"], (0.4, 0.4, 0.4, 1.0))
        self.assertEqual(rock["vectors"]["FallbackTint"], (0.1, 0.2, 0.3, 1.0))
        head = plan[SM.LANTERN_HEAD]
        self.assertEqual((head["route"], head["parent"], head["scalars"]), ("child", "/Game/EnvKit/ConceptPaste/MI_EnvCP_LanternHead",
                                                                             {"EmissiveIntensity": 60.0}))
        self.assertNotIn(SM.LANTERN_HEAD, {m["name"] for m in SM.mi_plan(man, tune={})})
        # the shipped tune file parses and names only planned MIs
        shipped = SM.load_tune()
        self.assertEqual(shipped.get("schema"), "unmatched.concept-scene-tune/1")


class ShippedProfile(unittest.TestCase):
    def setUp(self):
        prof = load(PROFILES)
        self.board = next(b for b in prof["boards"] if b["id"] == "sarpedon-original")
        self.block = self.board["conceptPaste"]
        self.lit = self.block["lit3d"]
        self.prof = prof

    def test_lit3d_default_and_paste_kept(self):
        self.assertEqual((self.block["default"], self.block["mode"]), ("on", "lit3d"))
        self.assertEqual((self.block["variant"], self.block["offVariant"], self.lit["variant"]), ("concept", "p5c", "scene"))
        for key in ("sheetMesh", "plateB", "lights", "hide", "sea"):  # -ConceptPaste=paste: the P7 look
            self.assertIn(key, self.block)

    def test_lights_match_the_paste_and_the_budget(self):
        paste = {lt["id"]: lt["loc"] for lt in self.block["lights"]}
        # P8.3 tune: lantern-deck-n's point moved to lantern-bay - at its design.json detail XY (the paste has no light there)
        paste["lantern-bay"] = [-129.7, -397.7, 196.6]
        for lt in self.lit["lights"]:
            self.assertIn(lt["id"], paste)
            self.assertLess(math.dist(lt["loc"][:2], paste[lt["id"]][:2]), 0.01, lt["id"])
            self.assertGreater(lt["flicker"]["amp"], 0.0)
        points = len(self.prof["lightProfiles"][self.board["light"]]["points"])
        self.assertLessEqual(points + len(self.lit["lights"]), 6)
        self.assertIn("layoutLights", self.lit["hide"])

    def test_hide_brings_sea_and_falls_back(self):
        self.assertNotIn("sea", self.lit["hide"])
        self.assertNotIn("waterfalls", self.lit["hide"])
        self.assertEqual(self.lit["seaZUU"], -300)
        self.assertLessEqual(self.lit["seaZUU"], -3)

    def test_patterns(self):
        for pattern in self.lit["casters"] + self.lit["giOff"] + self.lit["winds"]:
            stem = pattern[:-1] if pattern.endswith("*") else pattern
            self.assertRegex(stem, r"^[A-Za-z0-9_-]{1,64}$")
        self.assertTrue(IMP.match_patterns(["ship*"], "ship-hull"))
        self.assertFalse(IMP.match_patterns(["ship"], "ship-hull"))

    def test_marmoreal_untouched(self):
        marm = next(b for b in self.prof["boards"] if b["id"] == "marmoreal-original")["conceptPaste"]
        self.assertEqual(marm["default"], "off")
        self.assertNotIn("lit3d", marm)
        self.assertNotIn("mode", marm)

    def test_real_manifest_when_present(self):
        """Track A's manifest (once written): the interface contract without file / git checks (those run in P8.3)."""
        if not IMP.MANIFEST.is_file():
            self.skipTest("tools/art/concept_scene/manifest.sarpedon.json not written yet (track A)")
        _report, errors = IMP.validate(load(IMP.MANIFEST), check_files=False, check_git=False)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
