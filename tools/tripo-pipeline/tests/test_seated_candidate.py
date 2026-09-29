"""Unit tests for the profile-driven build (tool 0.5.0): flow seated-parts profiles, profile validation, anatomy
detection, the atlas options (exclude_parts, normal_renormalise, team_color.mask) and the ue-import rules for heroes
(height by profile, sockets from the build, optional TeamMask, TeamColor modes, parametric-base material).

Blender is tests/fake_blender.py, UnrealEditor is tests/fake_unreal_mcp.py; the atlas stage runs for real.
The real Blender builds of the four assets are in test_candidate_integration.py.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import copy
import importlib.util
import json
import unittest

from test_candidate import Image, make_textured_glb
from test_mcp_backend import McpBackendTestBase
from test_pipeline import TOOL, sha, tp

REPO = TOOL.parents[2]
LIB = TOOL.parent / "blender" / "candidate_build"
REAL_PROFILES = {
    "ASSET-MEDUSA-001": ("art/pipeline-candidates/ASSET-MEDUSA-001/build-profiles/medusa-segmented-skeletal-um-fbx-v1.json",
                         "whole-figure"),
    "ASSET-KING-ARTHUR-001": ("art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/"
                              "king-arthur-segmented-skeletal-um-fbx-v1-cli.json", "seated-parts"),
    "ASSET-MERLIN-001": ("art/pipeline-candidates/ASSET-MERLIN-001/build-profiles/merlin-segmented-skeletal-um-fbx-v1-cli.json",
                         "seated-parts"),
    "ASSET-HARPY-001": ("art/pipeline-candidates/ASSET-HARPY-001/build-profiles/harpy-segmented-skeletal-um-fbx-v1-cli.json",
                        "seated-parts"),
}


def load_module(name):
    spec = importlib.util.spec_from_file_location("test_lib_" + name, LIB / ("%s.py" % name))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


schema = load_module("profile_schema")
anatomy = load_module("anatomy")


def seated_profile(weapon=False, team_mode="mask", base_mode="parametric"):
    """A hero-like profile for the 3-part test GLB: body tripo_part_0, head tripo_part_1, Tripo base tripo_part_2."""
    bones = [["root", None, [0, 0, 0], [0, 0, 0.04]], ["spine", "root", [0, 0, 0.2], [0, 0, 0.3], "source"],
             ["head", "spine", [0, 0, 0.3], [0, 0, 0.4], "source"], ["weapon", "spine", [0.1, 0, 0.3], [0.1, 0, 0.5]]]
    profile = {
        "schema": tp.BUILD_PROFILE_SCHEMA, "profile_id": "test-seated/2", "asset_id": "ASSET-TEST-001",
        "status": "proposed", "build": {"flow": "seated-parts"}, "source_role": "glb", "expected_part_count": 3,
        "fbx_preset": tp.DEFAULT_FBX_PRESET,
        "atlas": {"size": 64, "gutter_px": 2, "texture_prefix": "T_Test_Atlas", "base_color_factor_expected": 0.800000011920929,
                  "orm_occlusion_fill": 255, "background": {"BC": [128, 128, 128], "N_OpenGL": [128, 128, 255],
                                                            "ORM": [255, 220, 0]}},
        "scale": {"figure_height_m": 0.42, "top_part": "tripo_part_1"},
        "materials": {"atlas": "M_Test_Atlas"},
        "meshes": {"body": {"object": "SK_Test_Body", "mesh": "Test_Body", "active_part": "tripo_part_0"},
                   "weapon": None,
                   "base": {"object": "SM_Test_Base", "mesh": "Test_Base", "mode": base_mode, "part": "tripo_part_2",
                            "footprint_m": [0.22, 0.22, 0.05]},
                   "drop_parts": {}},
        "weld": {"distance_m": 1e-06},
        "orientation": {"method": "ray-escape", "flip_below_score": -0.5, "expected_inside_out_parts": [],
                        "min_score_after_fix": 0.5, "corner_normal_opposed_max_fraction": 0.02},
        "armature": {"object": "SKEL_Test", "max_influences": 4, "bones": bones},
        "weights": {"clean_below": 0.01, "coordinates_frame": "source",
                    "groups": [{"parts": ["tripo_part_0"], "heat": ["root", "spine"]},
                               {"parts": ["tripo_part_1"], "rigid": "head"}]},
        "anatomy": {"feet": {"L": "tripo_part_0", "R": "tripo_part_0"}},
        "axes": {"expected_ue_front": "+X", "expected_ue_front_source": "test: 04 §1 / UM_FBX_v1"},
        "exports": {"skeletal_fbx": "SK_Test_Candidate.fbx", "base_fbx": "SM_Test_Base_Candidate.fbx"},
        "sockets": [{"name": "Head", "bone": "head", "target": {"kind": "part_bbox_centre"}, "location_uu": None}],
        "ue": {"skeletal_asset": "SK_Test_Candidate", "base_asset": "SM_Test_Base_Candidate", "material": "M_Test_Atlas",
               "default_instance": "MI_Test_Gold",
               "instances": {"MI_Test_Gold": [0.807, 0.527, 0.144, 1.0], "MI_Test_Silver": [0.347, 0.539, 0.686, 1.0]},
               "team_color_mode": team_mode,
               "textures": {"BC": {"asset": "T_Test_BC", "file_key": "BC", "srgb": True, "compression": "TC_Default"},
                            "N": {"asset": "T_Test_N", "file_key": "N", "srgb": False, "compression": "TC_Normalmap",
                                  "flip_green": False},
                            "ORM": {"asset": "T_Test_ORM", "file_key": "ORM", "srgb": False, "compression": "TC_Masks"},
                            "TeamMask": {"asset": "T_Test_TeamMask", "file_key": "TeamMask", "srgb": False,
                                         "compression": "TC_Grayscale", "optional": True}}},
        "team_color": {"mask": {"method": "hsv-smooth-box", "texture": "T_Test_Atlas_TeamMask.png", "hue_deg": [18.0, 55.0],
                                "hue_ramp_deg": 4.0, "s_min": 0.3, "v_min": 0.22, "ramp": 0.05,
                                "cells": ["tripo_part_0"]}},
        "expectations": {"triangles": {"SK_Test_Body": 4, "SM_Test_Base": 12}, "bones": 4,
                         "skeletal_material_slots": 1, "base_material_slots": 1},
        "proposed_limits_for_comparison_only": {"sidekick_triangles": [8000, 15000], "height_uu": [35, 42]},
    }
    if base_mode == "parametric":
        profile["meshes"]["base"] = {"object": "SM_Test_Base", "mesh": "Test_Base", "mode": "parametric",
                                     "source_part": "tripo_part_2", "footprint_m": [0.22, 0.22, 0.05]}
        profile["meshes"]["drop_parts"] = {"tripo_part_2": "Tripo base replaced by the parametric base"}
        profile["atlas"]["exclude_parts"] = {"tripo_part_2": "replaced by the parametric base"}
        profile["atlas"]["normal_renormalise"] = True
        profile["base_parametric"] = {"radius_bottom_m": 0.11, "side_top_z_m": 0.046, "radius_top_m": 0.106,
                                      "height_m": 0.05, "segments": 16,
                                      "pips": {"ring_radius_m": 0.0955, "pip_radius_m": 0.009, "pip_sides": 8,
                                               "arc_spacing_m": 0.03, "sector_azimuths_deg": [-90], "raise_m": 0.0004,
                                               "skirt_m": 0.0006, "slots_per_sector": ["outer_a", "centre", "outer_b"]},
                                      "mask": {"attribute": "UM_Mask"}, "material": "M_Test_Base",
                                      "preview_colours_linear": {"base": [0.03, 0.026, 0.023], "pip": [0.78, 0.74, 0.64],
                                                                 "team_gold": [0.807, 0.527, 0.144]}}
        profile["ue"].update({"base_material": "M_Test_Base_Candidate", "base_material_mode": "vertex-mask",
                              "base_material_parameters": {"BaseColor": [0.03, 0.026, 0.023],
                                                           "PipColor": [0.78, 0.74, 0.64], "PipEmissive": 0.35}})
    if weapon:
        profile["meshes"]["weapon"] = {"object": "SK_Test_Weapon", "mesh": "Test_Weapon", "mode": "part",
                                       "part": "tripo_part_1", "bone": "weapon"}
        profile["expectations"]["triangles"]["SK_Test_Weapon"] = 8
        profile["armature"]["weapon_axis_tolerance_m"] = 0.003
        profile["axes"]["blender_weapon_side"] = "-X"
        profile["sockets"].insert(0, {"name": "Weapon", "bone": "weapon", "location_uu": [0, 0, 0]})
    return profile


class ProfileSchemaTests(unittest.TestCase):
    def test_real_profiles_are_valid_and_name_their_flow(self):
        for asset, (rel, flow) in sorted(REAL_PROFILES.items()):
            profile = json.loads((REPO / rel).read_text(encoding="utf-8"))
            self.assertEqual(profile["asset_id"], asset)
            self.assertEqual(schema.flow_of(profile), flow, rel)
            self.assertEqual(schema.validate(profile), [], rel)
            self.assertNotIn("builder", profile, "the CLI builds from the profile, no external builder: %s" % rel)

    def test_legacy_hero_profiles_with_an_external_builder_are_refused(self):
        """The /1 hero profiles (records of the 2026-09-28 runs built by per-hero scripts) stay unchanged; the CLI
        refuses them with a message that points at the build description (their /2 successors are *-cli.json)."""
        for asset, (rel, _flow) in sorted(REAL_PROFILES.items()):
            if not rel.endswith("-cli.json"):
                continue
            legacy = REPO / rel.replace("-cli.json", ".json")
            profile = json.loads(legacy.read_text(encoding="utf-8"))
            self.assertTrue(profile.get("builder"), legacy)
            self.assertTrue(any(p.startswith("builder:") for p in schema.validate(profile)), legacy)

    def test_external_builder_profile_is_refused(self):
        profile = seated_profile()
        profile["builder"] = "art/pipeline-candidates/ASSET-TEST-001/scripts/build_test_candidate.py"
        self.assertTrue(any(p.startswith("builder:") for p in schema.validate(profile)))

    def test_seated_profile_rules(self):
        self.assertEqual(schema.validate(seated_profile()), [])
        self.assertEqual(schema.validate(seated_profile(weapon=True, base_mode="normalise-part")), [])
        bad = seated_profile()
        bad["meshes"]["drop_parts"] = {}
        self.assertIn("meshes.base.source_part must be listed in meshes.drop_parts (replaced by the parametric base)",
                      schema.validate(bad))
        bad = seated_profile(weapon=True)
        bad["meshes"]["weapon"]["mode"] = "split-from-part"
        problems = schema.validate(bad)
        self.assertTrue(any("split_from" in p for p in problems), problems)
        self.assertTrue(any("weapon_split" in p for p in problems), problems)
        bad = seated_profile()
        bad["armature"]["bones"][1][4] = "world"
        bad["weights"]["coordinates_frame"] = "gltf"
        bad["sockets"][0]["bone"] = "neck"
        bad["weights"]["groups"][0]["rigid"] = "root"
        problems = schema.validate(bad)
        for fragment in ("frame must be one of", "weights.coordinates_frame", "bone neck is not in armature.bones",
                         "exactly one of"):
            self.assertTrue(any(fragment in p for p in problems), (fragment, problems))
        bad = seated_profile()
        del bad["ue"]["textures"]["TeamMask"]["file_key"]
        self.assertIn("ue.textures.TeamMask: file_key (atlas output key) is required", schema.validate(bad))

    def test_whole_figure_needs_the_face_and_neck_parts(self):
        profile = json.loads((REPO / REAL_PROFILES["ASSET-MEDUSA-001"][0]).read_text(encoding="utf-8"))
        broken = copy.deepcopy(profile)
        del broken["anatomy"]["neck"]
        self.assertIn("expectations.neck_polygons needs anatomy.neck (the neck part)", schema.validate(broken))
        broken = copy.deepcopy(profile)
        del broken["anatomy"]["face"]
        del broken["materials"]["face_slot"]
        self.assertTrue(any("face part" in p for p in schema.validate(broken)))


def box(lo, hi):
    return {"min": list(lo), "max": list(hi), "centroid": [(a + b) / 2 for a, b in zip(lo, hi)], "polygons": 10}


class AnatomyTests(unittest.TestCase):
    PARTS = {
        "tripo_part_0": box((-0.10, -0.08, 0.06), (0.10, 0.08, 0.40)),   # cloak, spans both sides
        "tripo_part_1": box((0.01, -0.05, 0.06), (0.08, 0.03, 0.26)),    # left leg (+X)
        "tripo_part_2": box((-0.08, -0.05, 0.06), (-0.01, 0.03, 0.26)),  # right leg
        "tripo_part_3": box((-0.04, -0.05, 0.45), (0.04, 0.04, 0.55)),   # head (top)
        "tripo_part_4": box((-0.02, -0.02, 0.43), (0.02, 0.02, 0.47)),   # neck ring inside the head's footprint
        "tripo_part_5": box((-0.12, -0.10, 0.30), (-0.06, -0.04, 0.38)),  # right fist
    }

    def test_detection(self):
        found = anatomy.detect(self.PARTS, weapon_bone_head=[-0.09, -0.07, 0.34])
        self.assertEqual(found["head"], "tripo_part_3")
        self.assertEqual(found["feet"], {"L": "tripo_part_1", "R": "tripo_part_2"}, "the cloak spans both sides")
        self.assertEqual(found["weapon_hand"], "tripo_part_5")
        self.assertEqual(found["neck"], "tripo_part_4")

    def test_profile_wins_and_disagreements_are_listed(self):
        resolved = anatomy.resolve({"feet": {"L": "tripo_part_2", "R": "tripo_part_1"}}, self.PARTS, "tripo_part_3")
        self.assertEqual(resolved["used"]["feet"], {"L": "tripo_part_2", "R": "tripo_part_1"})
        self.assertEqual(resolved["source"]["feet"], "profile")
        self.assertEqual(resolved["source"]["neck"], "auto")
        self.assertIn("feet", resolved["disagreements"])
        self.assertEqual(resolved["used"]["face"], "tripo_part_3", "face defaults to the head part")


@unittest.skipIf(Image is None, "Pillow/numpy not installed (atlas stage needs them)")
class SeatedCandidateTests(McpBackendTestBase):
    FOLDER = "/Game/PipelineCandidates/Test/seated1"

    def setUp(self):
        super().setUp()
        make_textured_glb(self.glb)
        self.spec["files"][0]["expected_sha256"] = sha(self.glb)
        self.spec["expectations"] = {"glb": {"glb_mesh_count": 3, "glb_materials": 3, "glb_images": 9}}
        self.write_spec()
        self.profile_rel = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/seated.json"

    def write_profile(self, profile):
        path = self.repo / self.profile_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(profile, indent=1), encoding="utf-8")

    def init_candidate(self, profile):
        self.write_profile(profile)
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "skeletal-candidate", "--build-profile", self.profile_rel)
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))

    def report(self, rel):
        return json.loads((self.run_dir / rel).read_text(encoding="utf-8"))

    def test_parametric_base_team_mask_and_predicted_socket_reach_ue(self):
        self.init_candidate(seated_profile())
        out = self.mcp("run", "--run-dir", str(self.run_dir))
        self.assertIn("build     executed", out.stdout)
        m = self.manifest()
        self.assertEqual(m["stages"]["build"]["status"], "completed")
        self.assertEqual(m["tool"]["version"], tp.TOOL_VERSION)
        atlas = self.report("reports/atlas-report.json")
        self.assertEqual(sorted(atlas["cells"]), ["tripo_part_0", "tripo_part_1"], "the Tripo base is left out")
        self.assertEqual(sorted(atlas["excluded_parts"]), ["tripo_part_2"])
        self.assertIn("normal_renormalised_texels", atlas["checks"])
        self.assertTrue(atlas["checks"]["normal_vectors_unit_length_in_cells"]["passed"])
        self.assertEqual(atlas["files"]["TeamMask"]["file"], "T_Test_Atlas_TeamMask.png")
        self.assertIn("textures/T_Test_Atlas_TeamMask.png", m["stages"]["atlas"]["outputs"])
        with Image.open(self.run_dir / "textures/T_Test_Atlas_TeamMask.png") as mask:
            self.assertEqual((mask.mode, mask.size), ("L", (64, 64)))
        coverage = atlas["team_mask"]["coverage_by_cell_inner_rect_ge_0_5"]
        self.assertEqual(coverage["tripo_part_1"], 0.0, "only the listed cell carries the mask")
        build = self.report("reports/build-report.json")
        self.assertEqual(build["fake_params_seen"]["lib_dir"], "blender", "the build gets the library directory")
        preflight = self.report("reports/preflight.json")
        self.assertTrue(preflight["checks"]["build_profile_schema"]["passed"])
        self.assertEqual(preflight["checks"]["build_profile_schema"]["measured"]["flow"], "seated-parts")
        self.assertTrue(preflight["checks"]["build_library_present"]["passed"])

        self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER)
        ue = self.report("reports/ue-import-report.json")
        failed = {k: c for k, c in ue["checks"].items() if not c["passed"]}
        self.assertEqual(ue["status"], "technically_imported", json.dumps(failed, indent=1))
        f = self.FOLDER
        self.assertIn(f + "/Textures/T_Test_TeamMask", ue["assets"])
        self.assertIn(f + "/Materials/M_Test_Base_Candidate", ue["assets"])
        self.assertEqual(ue["measured"]["material"]["team_color_mode"], "mask")
        self.assertIn("TeamMask", ue["measured"]["material"]["samplers"])
        self.assertTrue(ue["checks"]["base_material_graph_vertex_mask"]["passed"])
        self.assertTrue(ue["checks"]["base_vertex_colors_imported"]["passed"])
        self.assertEqual(ue["measured"]["base_vertex_colors"]["asset_import_option"], "Replace")
        self.assertIn("editor Python", ue["measured"]["base_vertex_colors"]["import"])
        self.assertEqual(ue["checks"]["team_color_instances"]["expected"]["parent"], f + "/Materials/M_Test_Base_Candidate")
        self.assertEqual(ue["checks"]["skeletal_material_slots"]["expected"]["material"], f + "/Materials/M_Test_Atlas",
                         "team instances belong to the base: the figure shows the atlas material")
        plan = ue["measured"]["sockets_plan"]
        self.assertEqual([(s["name"], s["source"], s["location_uu"]) for s in plan],
                         [("Head", "build prediction", build["sockets"][0]["location_uu_for_ue"])])
        self.assertTrue(ue["checks"]["figure_height_as_profile"]["passed"])
        self.assertTrue(ue["checks"]["skeletal_top_as_build"]["passed"])
        self.assertEqual(ue["comparison_with_proposals_not_budgets"]["hero_triangles"]["proposed_key"], "sidekick_triangles")

    def test_weapon_above_the_figure_top_passes_the_height_checks(self):
        self.init_candidate(seated_profile(weapon=True, team_mode="multiply", base_mode="normalise-part"))
        self.mcp("run", "--run-dir", str(self.run_dir))
        build = self.report("reports/build-report.json")
        self.assertAlmostEqual(build["figure"]["skeletal_top_m"] - build["figure"]["figure_top_m"], 0.05)
        self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER)
        ue = self.report("reports/ue-import-report.json")
        failed = {k: c for k, c in ue["checks"].items() if not c["passed"]}
        self.assertEqual(ue["status"], "technically_imported", json.dumps(failed, indent=1))
        self.assertEqual(ue["measured"]["height"]["build_skeletal_top_uu"], 47.0)
        self.assertEqual(ue["measured"]["height"]["build_figure_top_uu"], 42.0)
        self.assertEqual(ue["measured"]["material"]["team_color_mode"], "multiply")
        self.assertEqual([(s["name"], s["source"]) for s in ue["measured"]["sockets_plan"]],
                         [("Weapon", "profile"), ("Head", "build prediction")])
        self.assertNotIn(self.FOLDER + "/Materials/M_Test_Base_Candidate", ue["assets"])

    def test_vertex_mask_base_without_vertex_colours_fails(self):
        """If the base arrives without vertex colours (VertexColorImportOption Ignore), the vertex-mask base renders
        fully lit (measured live on Harpy, T3.1): the stage must fail."""
        self.init_candidate(seated_profile())
        self.mcp("run", "--run-dir", str(self.run_dir))
        env = dict(self.env, FAKE_UE_EDITOR_PY_DROPS_VC="1")
        proc = self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER, expect=1, env=env)
        self.assertIn("base_vertex_colors_imported", proc.stdout + proc.stderr)

    def test_socket_on_a_dotted_bone_gets_the_ue_bone_name(self):
        """Harpy's Weapon socket sits on foot.R; the FBX import names that bone foot_R, and UE refuses add_socket on
        "foot.R" (measured live 2026-09-28). The plan keeps the profile name and attaches to the UE name."""
        profile = seated_profile()
        profile["armature"]["bones"].append(["foot.R", "root", [-0.05, 0, 0.0], [-0.05, -0.04, 0.0]])
        profile["sockets"].append({"name": "Weapon", "bone": "foot.R", "target": {"kind": "foot_tip", "side": "R"},
                                   "location_uu": None})
        self.init_candidate(profile)
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER)
        ue = self.report("reports/ue-import-report.json")
        failed = {k: c for k, c in ue["checks"].items() if not c["passed"]}
        self.assertEqual(ue["status"], "technically_imported", json.dumps(failed, indent=1))
        weapon = [s for s in ue["measured"]["sockets_plan"] if s["name"] == "Weapon"]
        self.assertEqual([(s["bone"], s["ue_bone"]) for s in weapon], [("foot.R", "foot_R")])
        self.assertEqual(ue["checks"]["sockets_weapon_head"]["measured"]["Weapon"]["bone"], "foot_R")

    def test_invalid_profile_stops_at_preflight_before_any_blender_work(self):
        profile = seated_profile()
        profile["builder"] = "art/pipeline-candidates/ASSET-TEST-001/scripts/build_test_candidate.py"
        self.init_candidate(profile)
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("build_profile_schema", proc.stderr)
        preflight = self.report("reports/preflight.json")
        self.assertTrue(any("external builders" in p for p in preflight["checks"]["build_profile_schema"]["measured"]["problems"]))
        self.assertEqual(self.blender_calls(), [])

    def test_per_face_reference_source_is_resolved_and_passed_to_the_build(self):
        profile = seated_profile()
        profile["orientation"]["per_face_reference"] = {
            "parts": ["tripo_part_1"], "source_id": "tripo-t1", "role": "reference-glb", "max_reference_distance_m": 0.012,
            "smoothing_lambda": 1.0, "smoothing_max_sweeps": 30, "max_inconsistent_after": 12}
        self.init_candidate(profile)
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("build_reference_source_registered", proc.stderr)
        # register the reference high-poly as a second file of the source and rebuild
        ref = self.repo / "tripo-source/t1/reference.glb"
        ref.write_bytes(self.glb.read_bytes())
        spec = json.loads(self.spec_path.read_text(encoding="utf-8"))
        spec["source_id"] = "tripo-t1-ref"
        spec["files"] = [{"role": "reference-glb", "path": "tripo-source/t1/reference.glb"}]
        self.spec_path.write_text(json.dumps(spec), encoding="utf-8")
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))
        profile["orientation"]["per_face_reference"]["source_id"] = "tripo-t1-ref"
        self.write_profile(profile)
        self.cli("run", "--run-dir", str(self.run_dir))
        build = self.report("reports/build-report.json")
        self.assertEqual(build["fake_params_seen"]["reference_glb"], "reference.glb")
        fp_before = self.manifest()["stages"]["build"]["fingerprint"]
        ref.write_bytes(self.glb.read_bytes() + b"\0\0\0\0")
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("source_files_unchanged_since_registration", proc.stderr)
        self.assertEqual(self.manifest()["stages"]["build"]["fingerprint"], fp_before)

    def manifest(self):
        return json.loads((self.run_dir / "manifest.json").read_text(encoding="utf-8"))

    def blender_calls(self):
        return self.calls.read_text(encoding="utf-8").split() if self.calls.exists() else []


if __name__ == "__main__":
    unittest.main()
