"""ENV-MAPS P9 track B: plain-Python tests of the six-fix material / fx / profile side of the Sarpedon lit3d scene -
F6 foliage wind (ue_scene_material.py SceneWind + FOLIAGE_WIND), F2 frame band MIs (dark wood + iron), F4 cascade MIs
(children of the P5c waterfall MI) and the P5c falls hidden in lit3d, F5 the layered fire + cascade mist
(ue_import_fab_fx.py FX_SPECS, fx-plan.sarpedon.json, the merge check of ue_import_concept_scene.py) and the brazier
flicker of the lit3d block.

  python -B -m pytest -q tools/art/tests/test_ue_concept_scene_p9.py
"""
from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "concept_scene"))
sys.path.insert(0, str(REPO / "tools" / "art" / "concept_paste"))
sys.path.insert(0, str(REPO / "tools" / "art" / "env_kit"))
import ue_import_concept_scene as IMP  # noqa: E402
import ue_import_fab_fx as FX  # noqa: E402
import ue_scene_material as SM  # noqa: E402

PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
CONTENT = REPO / "unreal/Unmatched/Content"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def plan_by_name(manifest, tune=None):
    return {m["name"]: m for m in SM.mi_plan(manifest, tune={} if tune is None else tune)}


class FoliageWind(unittest.TestCase):
    """F6: P8 measured 0.16 % live foliage motion (WindAmp 2 x (h / 300)^1.5 on 50-300 uu trees: sub-pixel)."""

    def test_wind_is_raised_over_the_manifest(self):
        manifest = SM.load_manifest()
        fol = plan_by_name(manifest)["MI_EnvScene_Proj_Foliage"]["scalars"]
        self.assertEqual((fol["WindAmp"], fol["WindHeight"]), (8.0, 120.0))
        self.assertGreater(fol["WindFlutter"], 0.0)
        # the manifest's own measured look values (tint, projection) survive
        look = next(x for x in (manifest or {}).get("looks", SM.DEFAULT_LOOKS) if x["name"] == "Foliage")
        vec = plan_by_name(manifest)["MI_EnvScene_Proj_Foliage"]["vectors"]["FallbackTint"]
        self.assertEqual(tuple(round(v, 4) for v in vec), tuple(round(float(v), 4) for v in look["vectors"]["FallbackTint"]))

    def test_tune_still_wins(self):
        tuned = plan_by_name(SM.load_manifest(), {"looks": {"Foliage": {"scalars": {"WindAmp": 5.0}}}})
        self.assertEqual(tuned["MI_EnvScene_Proj_Foliage"]["scalars"]["WindAmp"], 5.0)

    def test_default_looks_without_manifest(self):
        fol = plan_by_name(None)["MI_EnvScene_Proj_Foliage"]["scalars"]
        self.assertEqual((fol["WindAmp"], fol["WindHeight"], fol["WindFlutter"]), (8.0, 120.0, 1.5))

    def test_sway_reads_in_pixels_and_is_still_when_frozen(self):
        # a 100 uu tree top: h = 100 / 120 -> 8 x h^1.5 = ~6 uu (~6 px at C0 / K1, ~0.9 uu per px)
        h = min(1.0, 100.0 / 120.0)
        self.assertGreater(8.0 * h ** 1.5, 5.0)
        code = SM.HLSL_WIND
        self.assertIn("float live = saturate(Live);", code)
        self.assertIn("return (sway + flutter) * live;", code)  # Live = 0 (-Bench, MPC default) -> no WPO at all
        self.assertEqual(SM.MPC_DEFAULTS[SM.MPC_LIVE], 0.0)
        pins = [p for p, _t in SM.NODES["SceneWind"][1]]
        self.assertIn("WindFlutter", pins)
        self.assertIn("WindFlutterHz", pins)
        self.assertEqual(SM.GRAPH_VERSION, "2")  # the masters are rebuilt with the new wind

    def test_profile_keeps_the_wind_targets(self):
        lit = SM.sarpedon_block(load(PROFILES))["lit3d"]
        for pattern in ("tree*", "bush*"):
            self.assertIn(pattern, lit["winds"])


class MaterialRoute(unittest.TestCase):
    """F2 frame band (dark wood + iron) and F4 cascade water MIs."""

    def setUp(self):
        self.plan = plan_by_name(SM.load_manifest())

    def test_planned_with_and_without_manifest(self):
        for plan in (self.plan, plan_by_name(None)):
            for name in SM.MATERIAL_NAMES:
                item = plan[f"MI_EnvScene_{name}"]
                self.assertEqual(item["path"], SM.material_mi_path(name))
                self.assertTrue(item["path"].startswith(SM.MAP_ROOT + "/"))

    def test_frame_wood_is_dark_planks(self):
        wood = self.plan["MI_EnvScene_FrameWood"]
        self.assertEqual(wood["parent"], SM.MATERIAL_PATH)
        self.assertEqual(wood["scalars"]["Projected"], 0.0)  # never the pale projected plate
        self.assertEqual(set(wood["textures"]), {"BC", "N", "ORM"})
        self.assertTrue(all("Planks023A" in v for v in wood["textures"].values()))
        tint = wood["vectors"]["BakedTint"]
        # Planks023A mean linear (0.102, 0.079, 0.062) x tint -> a dark brown albedo (< 0.04 linear, ~ sRGB 50 / 39 / 30)
        albedo = [m * t for m, t in zip((0.1016, 0.0794, 0.0618), tint[:3])]
        self.assertTrue(all(a < 0.04 for a in albedo), albedo)
        self.assertGreater(albedo[0], albedo[2])  # warm wood, not grey

    def test_frame_iron_uses_the_frame002_iron(self):
        iron = self.plan["MI_EnvScene_FrameIron"]
        self.assertEqual(iron["parent"], SM.MATERIAL_PATH)
        self.assertTrue(all(v.startswith("/Game/EnvMaps/Frame/T_MapFrame002_Iron_") for v in iron["textures"].values()))

    def test_textures_exist_when_content_is_present(self):
        for name in ("FrameWood", "FrameIron"):
            for path in self.plan[f"MI_EnvScene_{name}"]["textures"].values():
                f = CONTENT / (path[len("/Game/"):] + ".uasset")
                if (CONTENT / "EnvKit").is_dir():
                    self.assertTrue(f.is_file(), path)

    def test_falls_children_of_the_p5c_waterfall(self):
        for name in ("MI_EnvScene_FallsSheet", "MI_EnvScene_FallsFoam"):
            item = self.plan[name]
            self.assertEqual(item["route"], "falls")
            self.assertEqual(item["parent"], SM.FALLS_PARENT)
            card = item["vectors"]["FallCard"]
            self.assertEqual(card[3], 1.0)  # v authored top -> bottom in Blender (the FBX import flips V)
            # P9 tune: a wide sheet, or (manifest uvPerStream) one stream of the 4-stream ~ 300 uu cascade
            # VS-8 E1 EN-19: one of the three painted streams (mean 58.3 uu)
            self.assertGreaterEqual(card[0], 50.0)
            for k in item["vectors"]:
                self.assertIn(k, SM.FALL_PARAMS["vectors"])
            self.assertEqual(item["vectors"]["FallLook"][3], 1.0)  # the Water Materials streaks
        foam, sheet = self.plan["MI_EnvScene_FallsFoam"], self.plan["MI_EnvScene_FallsSheet"]
        # VS-8 E1 EN-19 (ВР-VS8-46): the stream body carries the white now (0.75 in the middle of a stream, fading to
        # its edges); the foam pads stay at the P10 0.5 (torn, never the opaque strips of P9) - below the body
        self.assertGreaterEqual(foam["vectors"]["FallLook"][0], 0.5)
        self.assertLessEqual(sheet["vectors"]["FallLook"][0], 0.8)
        if (CONTENT / "EnvKit/Ground").is_dir():
            self.assertTrue((CONTENT / "EnvKit/Ground/MI_EnvWaterfall_Sarpedon.uasset").is_file())

    def test_manifest_overrides_and_look_alias(self):
        manifest = copy.deepcopy(SM.load_manifest() or {"meshes": [], "looks": []})
        manifest["materials"] = {"FrameWood": {"vectors": {"BakedTint": [0.2, 0.15, 0.12, 1.0]}}}
        manifest.setdefault("looks", []).append({"name": "FrameIron", "scalars": {"NormalStrength": 2.0}})
        plan = plan_by_name(manifest)
        self.assertEqual(plan["MI_EnvScene_FrameWood"]["vectors"]["BakedTint"], (0.2, 0.15, 0.12, 1.0))
        self.assertEqual(plan["MI_EnvScene_FrameIron"]["scalars"]["NormalStrength"], 2.0)
        self.assertNotIn("MI_EnvScene_Proj_FrameIron", plan)  # a look of a material name makes no projected MI

    def test_mesh_with_a_material_mi_gets_no_baked_mi(self):
        manifest = copy.deepcopy(SM.load_manifest() or {"meshes": []})
        manifest["meshes"].append({"name": "FrameBand", "mi": SM.material_mi_path("FrameWood")})
        plan = SM.mi_plan(manifest, tune={})
        self.assertEqual(len([m for m in plan if m["path"] == SM.material_mi_path("FrameWood")]), 1)

    def test_check_names_and_params(self):
        report, errors = SM.check()
        self.assertEqual(errors, [])
        self.assertEqual(set(report["materialMis"]), {f"MI_EnvScene_{n}" for n in SM.MATERIAL_NAMES})
        self.assertGreaterEqual(report["foliageWind"]["WindAmp"], 6.0)


class ImporterExistingMaterial(unittest.TestCase):
    def _manifest(self, entry):
        m = copy.deepcopy(SM.load_manifest())
        if m is None:
            self.skipTest("track A manifest absent")
        existing = [e for e in m.get("meshesExistingMaterial", []) if e.get("name") != entry["name"]]
        m["meshesExistingMaterial"] = existing + [entry]  # replace the real entry of the same name (track A has FrameBand)
        return m

    def test_per_slot_material_mis_validate(self):
        entry = {"name": "FrameBand", "ue": f"{SM.MAP_ROOT}/SM_Env_S_FrameBand",
                 "fbx": "art/pipeline-candidates/ASSET-ENV-S-FRAMEBAND-001/x/SM_Env_S_FrameBand.fbx",
                 "slots": ["MI_EnvScene_FrameWood", "MI_EnvScene_FrameIron"], "castShadow": True, "lumenGI": True,
                 "tris": 4000}
        report, errors = IMP.validate(self._manifest(entry), check_files=False, check_git=False)
        self.assertEqual([e for e in errors if "FrameBand" in e and "sha256" not in e], [])
        self.assertEqual(report["meshes"]["FrameBand"]["mis"],
                         [SM.material_mi_path("FrameWood"), SM.material_mi_path("FrameIron")])

    def test_unplanned_scene_mi_is_an_error(self):
        entry = {"name": "FrameBand", "ue": f"{SM.MAP_ROOT}/SM_Env_S_FrameBand", "fbx": "a/b.fbx",
                 "slots": ["MI_EnvScene_NoSuch"]}
        _report, errors = IMP.validate(self._manifest(entry), check_files=False, check_git=False)
        self.assertTrue(any("MI_EnvScene_NoSuch" in e and "not planned" in e for e in errors), errors)

    def test_full_mi(self):
        self.assertEqual(IMP._full_mi("MI_EnvScene_FrameWood"), SM.material_mi_path("FrameWood"))
        self.assertEqual(IMP._full_mi("/Game/EnvKit/ConceptPaste/MI_EnvCP_Banner"), "/Game/EnvKit/ConceptPaste/MI_EnvCP_Banner")
        self.assertIsNone(IMP._full_mi(None))


class FirePlan(unittest.TestCase):
    """F5 (and the F4 mist): the layered fire systems and fx-plan.sarpedon.json."""

    def setUp(self):
        self.plan = load(IMP.FX_PLAN)

    def test_specs_valid_and_lightless(self):
        err, _warn = FX.validate(FX.FX_SPECS, content=None)
        self.assertEqual(err, [])
        for names in FX.FX_PLAN_SYSTEMS.values():
            for n in names:
                s = FX.spec_by_name(n)
                self.assertIsNotNone(s, n)
                t = s["tune"]
                self.assertTrue(t["disableLightRenderers"] and t["disableComponentRenderers"], n)
                self.assertEqual(t["simTarget"], "cpu", n)
                self.assertTrue(s["system"]["determinism"], n)
                self.assertLessEqual(FX.estimate_particles(n), FX.FX_PARTICLE_BUDGET, n)
                self.assertIn(s["pack"], ("Stylish_Fire_VFX", "FreeParticle_SoftTofu"), n)

    def test_layers_differ(self):
        core = FX.spec_by_name("NS_Env_FireCore")["tune"]["constants"]
        smoke = FX.spec_by_name("NS_Env_FireSmoke")["tune"]["constants"]
        colour = lambda rules: next(r["set"] for r in rules if r["match"] == "*.Color.Scale Color" and "set" in r)  # noqa: E731
        self.assertGreater(colour(core)[0], colour(core)[2])  # yellow core: R > B
        self.assertLess(max(colour(smoke)), 0.1)  # dark smoke
        self.assertTrue(any(r["match"] == "*.GravityForce.Gravity" and r.get("mul") == 0.15 for r in smoke))
        sizes = {n: next(r["mul"] for r in FX.spec_by_name(n)["tune"]["constants"]
                         if r["match"] == "*.InitializeParticle.Uniform Sprite Size*")
                 for n in ("NS_Env_FireCore", "NS_Env_FireTongues", "NS_Env_FireSmoke")}
        concept = next(r["mul"] for r in FX.spec_by_name("NS_Env_ConceptFire")["tune"]["constants"]
                       if r["match"] == "*.InitializeParticle.Uniform Sprite Size*")
        self.assertTrue(all(k < concept for k in sizes.values()), (sizes, concept))  # smaller than the P8 blob

    def test_plan_valid(self):
        report, errors = IMP.validate_fx_plan(self.plan)
        self.assertEqual(errors, [])
        self.assertEqual(report["fires"], 8)
        self.assertGreaterEqual(report["waterfall"], 2)
        self.assertLessEqual(report["particlesEstimate"], FX.BOARD_PARTICLE_BUDGET / 2)
        self.assertEqual(set(self.plan["replaces"]), {"fire-fort", "fire-brazier"})
        for f in self.plan["fires"]:
            self.assertIn(f["anchor"], IMP.FX_ANCHORS)
            self.assertTrue(f["id"].startswith("fire-brazier-" if f["anchor"] == "brazier" else "fire-fort-"))

    def test_plan_broken(self):
        for mutate, needle in (
                (lambda p: p["fires"][0].update(system="/Game/EnvKit/FX/NS_Env_ConceptFire"), "system"),
                (lambda p: p["fires"][0].update(anchor="mast"), "anchor"),
                (lambda p: p["fires"][1].update(id=p["fires"][0]["id"]), "duplicate"),
                (lambda p: p["waterfall"][0].update(tier=0), "tier"),
                (lambda p: p["fires"][0].update(offsetUU=[0, 0]), "offsetUU"),
                (lambda p: p.update(schema="x"), "schema"),
                (lambda p: p.update(fires=[f for f in p["fires"] if not f["id"].endswith("-smoke")]), "layers")):
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            _r, errors = IMP.validate_fx_plan(plan)
            self.assertTrue(any(needle in e for e in errors), (needle, errors))

    def test_merge_states(self):
        ids = [f["id"] for f in self.plan["fires"] + self.plan["waterfall"]]
        none = {"fx": {"add": [{"id": "fire-fort", "system": "/Game/EnvKit/FX/NS_Env_ConceptFire"}]}}
        report, errors = IMP.validate_fx_plan(self.plan, none)
        self.assertEqual((report["merged"], errors), ("none", []))
        merged = {"fx": {"add": [{"id": i, "system": "/Game/EnvKit/FX/x"} for i in ids]}}
        report, errors = IMP.validate_fx_plan(self.plan, merged)
        self.assertEqual((report["merged"], errors), ("all", []))
        no_tier3 = {"fx": {"add": [{"id": i, "system": "/Game/EnvKit/FX/x"} for i in ids if i != "falls-mist-3"]}}
        report, errors = IMP.validate_fx_plan(self.plan, no_tier3)
        self.assertEqual((report["merged"], errors), ("partial", []))  # a missing cascade tier is dropped, not an error
        no_fire = {"fx": {"add": [{"id": i, "system": "/Game/EnvKit/FX/x"} for i in ids if i != "fire-fort-smoke"]}}
        _r, errors = IMP.validate_fx_plan(self.plan, no_fire)
        self.assertTrue(any("fire-fort-smoke" in e for e in errors), errors)
        both = {"fx": {"add": merged["fx"]["add"] + none["fx"]["add"]}}
        _r, errors = IMP.validate_fx_plan(self.plan, both)
        self.assertTrue(any("NS_Env_ConceptFire" in e for e in errors), errors)


class Lit3dProfile(unittest.TestCase):
    def setUp(self):
        prof = load(PROFILES)
        self.prof = prof
        self.board = next(b for b in prof["boards"] if b["id"] == "sarpedon-original")
        self.lit = self.board["conceptPaste"]["lit3d"]

    def test_brazier_flicker_reads(self):
        brazier = next(lt for lt in self.lit["lights"] if lt["id"] == "fire-brazier")
        self.assertEqual(brazier["radius"], 180)
        # VS-8 E1 EN-22: 0.25 -> 0.5 (the G7 std of the pool over 20 live K1 frames 3.7 levels, card 2..8)
        self.assertEqual(brazier["flicker"]["amp"], 0.5)
        # VC C2 (ВР-VC-06): 1.6 -> 1.37 Hz - the G7 live series (a K1 frame every ~6.3 s) aliased both flicker terms of
        # 1.6 Hz to nearly the same phase (10.08 / 23.9 cycles); 1.37 Hz keeps the rhythm and decorrelates them
        self.assertEqual(brazier["flicker"]["hz"], 1.37)
        # the pool must stay off the map cells: the brazier stands > radius from the painted map field
        half = (891.3333 / 2, 577.3333 / 2)
        x, y, z = brazier["loc"]
        dx, dy = max(0.0, abs(x) - half[0]), max(0.0, abs(y) - half[1])
        self.assertGreater(math.sqrt(dx * dx + dy * dy + z * z), 0.95 * brazier["radius"])

    def test_p5c_falls_hidden_sea_kept_budget(self):
        self.assertIn("waterfalls", self.lit["hide"])
        self.assertNotIn("sea", self.lit["hide"])
        points = len(self.prof["lightProfiles"][self.board["light"]]["points"])
        self.assertLessEqual(points + len(self.lit["lights"]), 6)

    def test_paste_lights_untouched(self):
        paste = {lt["id"]: lt for lt in self.board["conceptPaste"]["lights"]}
        self.assertEqual((paste["fire-brazier"]["radius"], paste["fire-brazier"]["flicker"]["amp"]), (420, 0.06))


if __name__ == "__main__":
    unittest.main()
