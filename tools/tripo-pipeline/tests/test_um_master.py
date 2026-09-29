"""Unit tests of wave 4, W4-B (tool 0.6.0): UM master materials, the um-master route of ue-import, the AO bake of the
atlas stage, the hsv-band-cells TeamMask, the explicit-FbxFactory mesh import and the console retype.

The UnrealEditor is tests/fake_unreal_mcp.py (it records material graphs, links, parameters, MIs and the FBX import
options of the editor-Python import), Blender is tests/fake_blender.py (its bake_ao.py double writes a ramp per part).

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_candidate import Image, make_profile, make_textured_glb
from test_mcp_backend import FAKE_UE, McpBackendTestBase
from test_pipeline import sha, tp

UM = Path(tp.__file__).resolve().parent / "um_masters.py"
sys.path.insert(0, str(UM.parent))
import um_masters  # noqa: E402

SPEC, _ = um_masters.load_spec()


class ColourRuleTests(unittest.TestCase):
    def test_hex_to_linear_equals_the_engine_srgb_table(self):
        # FLinearColor::sRGBToLinearTable (Engine/Source/Runtime/Core/Public/Math/Color.h, UE 5.8)
        table = {0: 0.0, 1: 0.000303526983548838, 11: 0.00334653564113713, 106: 0.144128469755705,
                 128: 0.215860498718652, 192: 0.527115123357109, 232: 0.806952254658248, 255: 1.0}
        for value, want in table.items():
            self.assertAlmostEqual(um_masters.srgb_u8_to_linear(value), want, places=6, msg=value)
        self.assertEqual(um_masters.hex_to_linear("#E8C06A"), [0.806952, 0.527115, 0.144128, 1.0])

    def test_hex_over_255_is_not_the_rule(self):
        gold = um_masters.hex_to_linear("#E8C06A")
        self.assertNotAlmostEqual(gold[0], 0xE8 / 255.0, places=2, msg="hex/255 must not be used as linear")

    def test_bad_colour_is_refused(self):
        for bad in ("E8C06A", "#E8C06", "#GGGGGG", [1, 1, 1]):
            with self.assertRaises(ValueError):
                um_masters.colour_value(bad)
        self.assertEqual(um_masters.colour_value({"linear": [0.03, 0.026, 0.023]}), [0.03, 0.026, 0.023, 1.0])

    def test_c11_palette_is_nearly_isoluminant_and_the_proposal_is_not(self):
        pal = SPEC["team_palette"]
        lum = {k: um_masters.luminance(um_masters.hex_to_linear(v)[:3])
               for k, v in pal["c11"].items() if k.startswith(("Gold", "Silver"))}
        self.assertLess(lum["Gold"] / lum["Silver"], 1.15, "С-11: gold vs silver-blue differ by < 0.2 EV")
        prop = um_masters.luminance(um_masters.hex_to_linear(pal["c11_value_split_proposal"]["Silver"])[:3])
        self.assertGreater(lum["Gold"] / prop, 2.0, "value-split proposal: > 1 EV between the teams")


class GraphTests(unittest.TestCase):
    def test_custom_primitive_data_layout_of_the_memo(self):
        cpd = SPEC["custom_primitive_data"]
        self.assertEqual({k: v["index"] for k, v in cpd.items() if isinstance(v, dict)},
                         {"TeamColor": 0, "InstanceIndex": 4, "FxFlash": 5, "RimIntensity": 9, "RimWidth": 10,
                          "Fade": 11})
        for role in SPEC["masters"]:
            g = um_masters.GRAPHS[role](SPEC)
            for n in g.nodes.values():
                if n["props"].get("bUseCustomPrimitiveData"):
                    default = n["props"]["DefaultValue"]
                    values = default.values() if isinstance(default, dict) else [default]
                    self.assertTrue(all(v == 0 for v in values), "a primitive without CPD reads 0: 0 is neutral")

    def test_no_wpo_no_masked_and_opaque(self):
        for role in SPEC["masters"]:
            g = um_masters.GRAPHS[role](SPEC)
            self.assertFalse({"MP_WorldPositionOffset", "MP_OpacityMask", "MP_Opacity"} & set(g.outputs), role)
            self.assertEqual(um_masters.settings_of(SPEC, role)["BlendMode"], "BLEND_Opaque")
            self.assertFalse(um_masters.settings_of(SPEC, role)["TwoSided"])

    def test_figure_repeats_the_candidates_graph_with_neutral_knobs(self):
        g = um_masters.figure_graph(SPEC)
        links = set(g.links)
        # lerp(BC, BC x TeamColor, TeamMask.R) of the own-material route, with TeamDye 0 choosing BC x TeamColor
        self.assertIn(("t_bc", "RGB", "dyed", "A"), links)
        self.assertIn(("teamed", "", "dyed", "B"), links)
        self.assertIn(("t_mask", "R", "dyed", "Alpha"), links)
        self.assertIn(("bc_team", "", "teamed", "A"), links)
        self.assertEqual(g.outputs["MP_AmbientOcclusion"], ("t_orm", "R"))
        self.assertEqual(g.outputs["MP_Metallic"], ("t_orm", "B"))
        defaults = {n["props"]["ParameterName"]: n["props"]["DefaultValue"] for n in g.nodes.values()
                    if n["class"] == "MaterialExpressionScalarParameter" and not n["props"].get("bUseCustomPrimitiveData")}
        self.assertEqual(defaults["TeamDye"], 0.0)
        self.assertEqual((defaults["RoughnessMin"], defaults["RoughnessMax"]), (0.0, 1.0))
        self.assertEqual((defaults["NormalStrength"], defaults["AOToBaseColor"], defaults["Saturation"],
                          defaults["ValueLift"]), (1.0, 0.0, 1.0, 0.0))

    def test_every_node_has_its_own_editor_position(self):
        for role in SPEC["masters"]:
            g = um_masters.GRAPHS[role](SPEC)
            slots = [(n["class"], n["x"], n["y"]) for n in g.nodes.values()]
            self.assertEqual(len(slots), len(set(slots)), role)

    def test_read_back_quirk_is_modelled(self):
        g = um_masters.Graph("t")
        g.add("v", "MaterialExpressionVectorParameter", {})
        g.add("l", "MaterialExpressionLinearInterpolate", {})
        g.link("v", "RGB", "l", "B")
        g.link("v", "A", "l", "Alpha")
        self.assertEqual(um_masters.reported_links(g), {("v", "RGB", "l", "B"), ("v", "RGB", "l", "Alpha")})


class MasterBuildOnFakeEditorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="um-masters-test-"))
        self.state = self.tmp / "ue.json"
        self.env = dict(os.environ, TRIPO_PIPELINE_UNREAL_MCP_CMD=json.dumps([sys.executable, str(FAKE_UE)]),
                        FAKE_UE_STATE=str(self.state))

    def um(self, *args, expect=0, repo=None):
        cmd = [sys.executable, str(UM), "--backend", "mcp"] + (["--repo-root", str(repo)] if repo else []) + list(args)
        proc = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=600)
        self.assertEqual(proc.returncode, expect, "%s\n%s\n%s" % (args, proc.stdout, proc.stderr))
        return proc

    def test_build_verify_skip_and_in_place_rebuild(self):
        report = self.tmp / "report.json"
        self.um("build", "--role", "game_layer", "--report", str(report))
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(data["passed"], json.dumps(data, indent=1)[:3000])
        self.assertEqual(data["masters"]["game_layer"]["action"], "created")
        self.assertTrue(all(t["action"] == "imported" for t in data["default_textures"].values()))
        state = json.loads(self.state.read_text(encoding="utf-8"))
        path = "/Game/UM/Materials/M_UM_GameLayer"
        self.assertEqual(state["assets"][path]["class"], "Material")
        # an MI that points at the master (as a candidate's MI would)
        state["assets"]["/Game/PipelineCandidates/X/MI_X"] = {"class": "MaterialInstanceConstant", "vectors": {}}
        state["props"]["/Game/PipelineCandidates/X/MI_X"] = {"Parent": {"refPath": path + ".M_UM_GameLayer"}}
        self.state.write_text(json.dumps(state), encoding="utf-8")
        out = self.um("build", "--role", "game_layer", "--report", str(report))
        self.assertIn("skipped", out.stdout)
        # a changed spec (another neutral default) is refused without --force, rebuilt in place with it
        repo = self.tmp / "repo"
        spec = json.loads((Path(um_masters.REPO) / um_masters.SPEC_REL).read_text(encoding="utf-8"))
        spec["parameters"]["ExposureCompensationAlpha"]["default"] = 0.5
        (repo / um_masters.SPEC_REL).parent.mkdir(parents=True)
        (repo / um_masters.SPEC_REL).write_text(json.dumps(spec), encoding="utf-8")
        for t in spec["default_textures"].values():
            (repo / t["file"]).parent.mkdir(parents=True, exist_ok=True)
            (repo / t["file"]).write_bytes((Path(um_masters.REPO) / t["file"]).read_bytes())
        proc = self.um("build", "--role", "game_layer", "--report", str(report), expect=tp.EXIT_CONFLICT, repo=repo)
        self.assertIn("--force", proc.stderr)
        self.um("build", "--role", "game_layer", "--report", str(report), "--force", repo=repo)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertEqual(data["masters"]["game_layer"]["action"], "rebuilt in place")
        self.assertTrue(data["passed"])
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertIn(path, state["assets"], "the master keeps its asset (no delete + create)")
        self.assertEqual(state["props"]["/Game/PipelineCandidates/X/MI_X"]["Parent"]["refPath"],
                         path + ".M_UM_GameLayer")
        self.um("verify", "--role", "game_layer", "--report", str(self.tmp / "verify.json"), repo=repo)

    def test_verify_fails_on_a_missing_link(self):
        report = self.tmp / "report.json"
        self.um("build", "--role", "game_layer", "--report", str(report))
        state = json.loads(self.state.read_text(encoding="utf-8"))
        mat = state["assets"]["/Game/UM/Materials/M_UM_GameLayer"]
        victim = next(d for d in mat["links"] if "EyeAdaptationInverse" in d)
        mat["links"][victim].pop("AlphaInput")
        self.state.write_text(json.dumps(state), encoding="utf-8")
        self.um("verify", "--role", "game_layer", "--report", str(report), expect=tp.EXIT_FAILED)
        data = json.loads(report.read_text(encoding="utf-8"))
        self.assertFalse(data["masters"]["game_layer"]["verify"]["checks"]["links_match_plan"]["passed"])


def fake_masters(state_path: Path):
    """Pre-built UM masters in the fake editor (parameters as list_parameters returns them)."""
    kinds = {"scalar": "Scalar", "vector": "Vector", "texture": "Texture"}
    state = {"assets": {}, "props": {}, "log": []}
    for role in ("figure", "base_marker"):
        path = um_masters.master_path(SPEC, role)
        state["assets"][path] = {"class": "Material", "outputs": {}, "expressions": 0, "dirty": False,
                                 "parameters": [{"name": n, "type": kinds[k]}
                                                for n, k in sorted(um_masters.expected_parameters(SPEC, role).items())]}
        state["props"][path] = {"BlendMode": "BLEND_Opaque", "TwoSided": False, "ShadingModel": "MSM_DefaultLit"}
    for key in ("TeamMask", "TeamMaskNone"):
        state["assets"][um_masters.texture_path(SPEC, key)] = {"class": "Texture2D", "size": [8, 8]}
    state_path.write_text(json.dumps(state), encoding="utf-8")


@unittest.skipIf(Image is None, "Pillow/numpy not installed (atlas stage needs them)")
class UmMasterRouteTests(McpBackendTestBase):
    FOLDER = "/Game/PipelineCandidates/Test/um1"

    def setUp(self):
        super().setUp()
        make_textured_glb(self.glb)
        self.spec["files"][0]["expected_sha256"] = sha(self.glb)
        self.spec["expectations"] = {"glb": {"glb_mesh_count": 3, "glb_materials": 3, "glb_images": 9}}
        self.write_spec()
        self.profile_rel = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/test-um.json"
        self.profile = make_profile(self.repo / self.profile_rel)
        p = self.profile
        p["atlas"]["ao_bake"] = {"samples": 16, "distance_rel": 0.08, "margin_px": 2, "seed": 0,
                                 "gate": {"min_range_p1_p99": 32, "min_occluded_fraction": 0.02}}
        p["team_color"] = {"mask": {"method": "hsv-band-cells", "texture": "T_Test_Atlas_TeamMask.png",
                                    "cells": ["tripo_part_0"], "v_min": 0.5, "ramp": 0.05}}
        u = p["ue"]
        for key in ("material", "default_instance", "instances"):
            u.pop(key)
        u.update({"material_route": "um-master", "figure_instance": "MI_Test", "base_instance": "MI_Test_Base",
                  "teams": {"Gold": "#E8C06A", "Silver": "#9FC2D8"}, "default_team": "Gold",
                  "team_instances": {"figure": "MI_Test_{team}", "base": "MI_Test_Base_{team}"},
                  "team_color_mode": "mask", "figure_parameters": {"TeamDye": 1.0, "TeamDyeGain": 6.0},
                  "base_marker": {"textures": True, "parameters": {"SideBandWeight": 1.0}}})
        u["textures"]["TeamMask"] = {"asset": "T_Test_TeamMask", "file_key": "TeamMask", "srgb": False,
                                     "compression": "TC_Grayscale"}
        (self.repo / self.profile_rel).write_text(json.dumps(p, indent=1), encoding="utf-8")
        fake_masters(self.ue_state)

    def init_candidate(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "skeletal-candidate",
                 "--build-profile", self.profile_rel)
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))

    def ue(self, *extra, expect=0, env=None):
        return self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER, *extra,
                        expect=expect, env=env)

    def report(self):
        return json.loads((self.run_dir / "reports/ue-import-report.json").read_text(encoding="utf-8"))

    def test_atlas_bakes_ao_into_orm_r_and_builds_the_band_mask(self):
        self.init_candidate()
        self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("ao_bake", self.blender_calls())
        atlas = json.loads((self.run_dir / "reports/atlas-report.json").read_text(encoding="utf-8"))
        gate = atlas["checks"]["orm_occlusion_baked_not_constant"]
        self.assertTrue(gate["passed"], gate)
        self.assertNotIn("orm_occlusion_channel_filled", atlas["checks"])
        self.assertTrue((self.run_dir / "reports/ao-bake-report.json").is_file())
        orm = Image.open(self.run_dir / "textures/T_Test_Atlas_ORM.png")
        import numpy as np
        self.assertGreater(len(np.unique(np.asarray(orm)[..., 0])), 8, "ORM.R is not a constant fill any more")
        cover = atlas["team_mask"]["coverage_by_cell_inner_rect_ge_0_5"]
        self.assertGreater(cover["tripo_part_0"], 0.5, "8 px test cells: the 3x3 blur softens the rim")
        self.assertEqual(cover["tripo_part_1"], 0.0)
        out = self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("atlas     skipped", out.stdout)
        self.assertEqual(self.blender_calls().count("ao_bake"), 1, "second run does not bake again")

    def test_constant_bake_fails_the_gate(self):
        self.init_candidate()
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1, env=dict(self.env, FAKE_AO_CONSTANT="1"))
        self.assertIn("atlas", proc.stderr)
        self.assertEqual(self.manifest()["stages"]["atlas"]["status"], "failed")

    def test_part_baked_with_inward_faces_fails_the_orientation_gate(self):
        # W4-B review: Harpy's head was baked with 40 % of its area facing inward and still passed the range gate
        self.init_candidate()
        self.cli("run", "--run-dir", str(self.run_dir), expect=1,
                 env=dict(self.env, FAKE_AO_INWARD="tripo_part_0:0.4"))
        self.assertEqual(self.manifest()["stages"]["atlas"]["status"], "failed")
        log = (self.run_dir / "logs/atlas.failed.log").read_text(encoding="utf-8")
        self.assertIn("ao_bake_parts_face_outward", log)
        self.cli("run", "--run-dir", str(self.run_dir))
        report = json.loads((self.run_dir / "reports/atlas-report.json").read_text(encoding="utf-8"))
        gate = report["checks"]["ao_bake_parts_face_outward"]
        self.assertTrue(gate["passed"], gate)
        self.assertEqual(sorted(gate["measured"]["inward_area_fraction"]),
                         ["tripo_part_0", "tripo_part_1", "tripo_part_2"], "every baked atlas cell is checked")

    def test_um_master_import_parents_values_and_import_contract(self):
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.ue()
        r = self.report()
        self.assertEqual(r["status"], "technically_imported",
                         json.dumps({k: c for k, c in r["checks"].items() if not c["passed"]}, indent=1)[:4000])
        f = self.FOLDER + "/Materials/"
        assets = self.ue_assets()
        self.assertNotIn(f + "M_Test_Atlas", assets, "no own material on the um-master route")
        for mi in ("MI_Test", "MI_Test_Base", "MI_Test_Gold", "MI_Test_Silver", "MI_Test_Base_Gold",
                   "MI_Test_Base_Silver"):
            self.assertEqual(assets[f + mi]["class"], "MaterialInstanceConstant", mi)
        inst = r["measured"]["um_instances"]
        self.assertEqual(inst["figure_instance"]["read_back"]["parent"], "/Game/UM/Materials/M_UM_Figure")
        self.assertEqual(inst["base_instance"]["read_back"]["parent"], "/Game/UM/Materials/M_UM_BaseMarker")
        self.assertEqual(inst["team:figure:Silver"]["read_back"]["parent"], f + "MI_Test")
        self.assertEqual(inst["team:figure:Silver"]["read_back"]["vectors"]["TeamColor"],
                         um_masters.hex_to_linear("#9FC2D8"))
        self.assertEqual(inst["figure_instance"]["read_back"]["textures"]["TeamMaskTexture"],
                         self.FOLDER + "/Textures/T_Test_TeamMask")
        for name in ("import_legacy_fbx_factory", "normal_import_method", "nanite_disabled", "um_masters_current",
                     "um_instances_parent_textures_values"):
            self.assertTrue(r["checks"][name]["passed"], name)
        sk = assets[self.FOLDER + "/Meshes/SK_Test_Candidate"]
        self.assertEqual(sorted(set(sk["materials"].values())), [f + "MI_Test_Gold"])
        self.assertEqual(assets[self.FOLDER + "/Meshes/SM_Test_Base_Candidate"]["materials"], {"M_Atlas": f + "MI_Test_Base_Gold"})
        self.ue("--force")
        self.assertEqual(self.report()["checks"], r["checks"])

    def test_wrong_normal_method_fails_the_contract(self):
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        proc = self.ue(expect=1, env=dict(self.env, FAKE_UE_NORMAL_METHOD="FBXNIM_COMPUTE_NORMALS"))
        self.assertIn("normal_import_method", proc.stderr)

    def test_missing_master_stops_before_any_mi(self):
        self.ue_state.write_text(json.dumps({"assets": {}, "props": {}, "log": []}), encoding="utf-8")
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        proc = self.ue(expect=1)
        self.assertIn("um_masters.py", proc.stderr)
        self.assertFalse(any(a.startswith(self.FOLDER + "/Materials/") for a in self.ue_assets()))

    def test_lost_console_command_is_typed_again(self):
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.ue(env=dict(self.env, FAKE_UE_TYPE_LOSES_FIRST="1", TRIPO_PIPELINE_CONSOLE_GRACE_S="1"))
        self.assertEqual(self.report()["status"], "technically_imported")
        types = [c for c in self.ue_calls() if c == "Type"]
        self.assertEqual(len(types), 3, "two meshes + one retype after the lost command")


class AoBakeOrientationTests(unittest.TestCase):
    """W4-B review fix: the AO bake repeats the build's orientation fixes (per-face reference, whole-part flips)."""
    HARPY = Path(um_masters.REPO) / "art/pipeline-candidates/ASSET-HARPY-001/build-profiles/" \
                                    "harpy-segmented-skeletal-um-fbx-v1-um-master.json"

    def load(self, path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def test_harpy_bake_gets_the_builds_per_face_fix_seat_and_weld(self):
        p = self.load(self.HARPY)
        params = tp.ao_bake_params(p)
        ref = p["orientation"]["per_face_reference"]
        self.assertEqual(params["flip_parts"], ["tripo_part_6"])
        self.assertEqual(params["occluders_excluded"], ["tripo_part_4"])
        self.assertEqual(params["per_face_reference"], {
            "parts": ["tripo_part_2"], "max_reference_distance_m": ref["max_reference_distance_m"],
            "smoothing_lambda": ref["smoothing_lambda"], "smoothing_max_sweeps": ref["smoothing_max_sweeps"],
            "weld_distance_m": p["weld"]["distance_m"],
            "seat": {"base_part": "tripo_part_4", "top_part": "tripo_part_2", "figure_height_m": 0.42,
                     "base_height_m": 0.05}})

    def test_heroes_without_mixed_winding_bake_as_before(self):
        base = Path(um_masters.REPO) / "art/pipeline-candidates"
        for rel in ("ASSET-MEDUSA-001/build-profiles/medusa-segmented-skeletal-um-fbx-v1-um-master.json",
                    "ASSET-KING-ARTHUR-001/build-profiles/king-arthur-segmented-skeletal-um-fbx-v1-um-master.json",
                    "ASSET-MERLIN-001/build-profiles/merlin-segmented-skeletal-um-fbx-v1-um-master.json"):
            self.assertIsNone(tp.ao_bake_params(self.load(base / rel))["per_face_reference"], rel)

    def test_per_face_reference_outside_the_seated_flow_is_refused(self):
        p = self.load(self.HARPY)
        p["build"]["flow"] = "whole-figure"
        with self.assertRaises(tp.PipelineError):
            tp.ao_bake_params(p)

    def test_bake_script_uses_the_build_library_code(self):
        text = (Path(tp.__file__).resolve().parent / "blender" / "bake_ao.py").read_text(encoding="utf-8")
        for needle in ("orientation.reference_votes", "orientation.smooth_orientation", "mesh_ops.weld_part",
                       "core.flip_polygons", "measure.orientation_scores", "orientation_after_flips"):
            self.assertIn(needle, text)
        self.assertEqual(set(tp.AO_BAKE_LIBRARY) - set(tp.build_library_hashes()), set(),
                         "every library module of the bake is part of the atlas fingerprint")


@unittest.skipIf(Image is None, "Pillow/numpy not installed (atlas stage needs them)")
class AoBakePerFaceReferenceRunTests(McpBackendTestBase):
    """The registered reference GLB reaches the bake; the atlas report lists the per-face flips."""

    def test_reference_glb_reaches_the_bake_and_its_change_reruns_the_atlas(self):
        from test_seated_candidate import seated_profile
        make_textured_glb(self.glb)
        self.spec["files"][0]["expected_sha256"] = sha(self.glb)
        self.spec["expectations"] = {"glb": {"glb_mesh_count": 3, "glb_materials": 3, "glb_images": 9}}
        self.write_spec()
        profile = seated_profile()
        profile["atlas"]["ao_bake"] = {"samples": 16, "distance_rel": 0.08, "margin_px": 2, "seed": 0,
                                       "gate": {"min_range_p1_p99": 32, "min_occluded_fraction": 0.02}}
        profile["orientation"]["per_face_reference"] = {
            "parts": ["tripo_part_1"], "source_id": "tripo-t1-ref", "role": "reference-glb",
            "max_reference_distance_m": 0.012, "smoothing_lambda": 1.0, "smoothing_max_sweeps": 30,
            "max_inconsistent_after": 12}
        rel = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/seated-ao.json"
        (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (self.repo / rel).write_text(json.dumps(profile, indent=1), encoding="utf-8")
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "skeletal-candidate", "--build-profile", rel)
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))
        ref = self.repo / "tripo-source/t1/reference.glb"
        ref.write_bytes(self.glb.read_bytes())
        spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        spec["source_id"] = "tripo-t1-ref"
        spec["files"] = [{"role": "reference-glb", "path": "tripo-source/t1/reference.glb"}]
        self.spec_path.write_text(json.dumps(spec), encoding="utf-8")
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))
        self.cli("run", "--run-dir", str(self.run_dir))
        bake = json.loads((self.run_dir / "reports/ao-bake-report.json").read_text(encoding="utf-8"))
        fix = bake["per_face_reference_fix"]
        self.assertEqual(fix["reference_glb"]["file"], "reference.glb")
        self.assertEqual(fix["seat"], {"base_part": "tripo_part_2", "top_part": "tripo_part_1", "figure_height_m": 0.42,
                                       "base_height_m": 0.05})
        atlas = json.loads((self.run_dir / "reports/atlas-report.json").read_text(encoding="utf-8"))
        self.assertEqual(atlas["ao_bake"]["per_face_reference_flipped"], {"tripo_part_1": 1})
        self.assertTrue(atlas["checks"]["ao_bake_parts_face_outward"]["passed"])
        fp = self.manifest()["stages"]["atlas"]["fingerprint"]
        out = self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("atlas     skipped", out.stdout)
        self.assertEqual(self.manifest()["stages"]["atlas"]["fingerprint"], fp)


class RepoProfilesTests(unittest.TestCase):
    """The /3 profiles of W4-B change nothing the build reads: same FBX bytes as the /2 runs (measured), valid schema."""
    PAIRS = {
        "ASSET-MEDUSA-001": ("medusa-segmented-skeletal-um-fbx-v1.json", "medusa-segmented-skeletal-um-fbx-v1-um-master.json"),
        "ASSET-KING-ARTHUR-001": ("king-arthur-segmented-skeletal-um-fbx-v1-cli.json",
                                  "king-arthur-segmented-skeletal-um-fbx-v1-um-master.json"),
        "ASSET-MERLIN-001": ("merlin-segmented-skeletal-um-fbx-v1-cli.json", "merlin-segmented-skeletal-um-fbx-v1-um-master.json"),
        "ASSET-HARPY-001": ("harpy-segmented-skeletal-um-fbx-v1-cli.json", "harpy-segmented-skeletal-um-fbx-v1-um-master.json"),
    }
    W4B_KEYS = ("profile_id", "status", "status_note", "history", "supersedes", "team_color", "ue")

    def test_um_master_profiles_add_only_atlas_team_and_ue_keys(self):
        sys.path.insert(0, str(UM.parent / "blender" / "candidate_build"))
        import profile_schema
        for asset, (old_name, new_name) in self.PAIRS.items():
            base = Path(um_masters.REPO) / "art/pipeline-candidates" / asset / "build-profiles"
            old = json.loads((base / old_name).read_text(encoding="utf-8"))
            new = json.loads((base / new_name).read_text(encoding="utf-8"))
            self.assertEqual(profile_schema.validate(new), [], new_name)
            strip = lambda p: {k: v for k, v in p.items() if k not in self.W4B_KEYS}  # noqa: E731
            o, n = strip(old), strip(new)
            self.assertEqual({k: v for k, v in n["atlas"].items() if k != "ao_bake"}, o["atlas"], new_name)
            o.pop("atlas"), n.pop("atlas")
            self.assertEqual(n, o, "%s: build keys must equal %s" % (new_name, old_name))
            self.assertEqual(new["ue"]["material_route"], "um-master")
            self.assertEqual(new["ue"]["teams"], dict((k, v) for k, v in SPEC["team_palette"]["c11"].items()
                                                      if k in ("Gold", "Silver")))
            self.assertEqual(new["ue"]["team_color_mode"], "mask")
            self.assertIn("ao_bake", new["atlas"])


class StaticOnUmFigureTests(unittest.TestCase):
    """The static-candidate route onto M_UM_Figure (barrel profile /2): parent, parameters, import contract."""

    def setUp(self):
        from test_static_candidate import StaticCandidateTests
        self.case = StaticCandidateTests("test_adopt_then_ue_import_is_idempotent_and_force_makes_no_numbered_copy")
        self.case.setUp()
        self.addCleanup(self.case.tearDown)
        master = um_masters.master_path(SPEC, "figure")
        self.case.profile["ue"]["shared_master"]["asset"] = master
        self.case.write_json(self.case.repo / self.case.profile_rel, self.case.profile)
        fake_masters(self.case.ue_state)

    def test_barrel_like_prop_uses_the_figure_master(self):
        c = self.case
        c.init_static()
        c.mcp("run", "--run-dir", str(c.run_dir))
        c.ue()
        r = c.report_json()
        self.assertEqual(r["status"], "technically_imported",
                         json.dumps({k: v for k, v in r["checks"].items() if not v["passed"]}, indent=1)[:3000])
        self.assertEqual(r["measured"]["material_route"]["used"], "shared_master")
        self.assertEqual(r["measured"]["instance"]["parent"], "/Game/UM/Materials/M_UM_Figure.M_UM_Figure")
        for name in ("nanite_disabled", "normal_import_method_read_back", "shared_master_parameters_current"):
            self.assertTrue(r["checks"][name]["passed"], name)
        self.assertEqual(r["deviations"], [])


if __name__ == "__main__":
    unittest.main()
