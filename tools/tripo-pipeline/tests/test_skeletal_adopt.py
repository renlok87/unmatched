"""Unit tests for the skeletal-adopt profile (tool 0.7.0, W5c): preflight -> adopt -> ue-import of an H2 bake.

The bake folder (SK + base FBX, 2K-style maps, build-report.json in the h2-bake-rig/1 layout, textures-report.json) is
written by the test; the real ones come from tools/tripo-pipeline/blender/h2_bake_*. UnrealEditor is
tests/fake_unreal_mcp.py (it reads the H2 build report next to the imported FBX, runs the CLI's editor-Python FBX import
and the skeletal LOD/triangle measurement) with the UM masters pre-built (test_um_master.fake_masters).

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import json
import sys
import unittest
from pathlib import Path

from test_mcp_backend import McpBackendTestBase
from test_pipeline import sha, tp
from test_static_candidate import png
from test_um_master import fake_masters, um_masters

sys.path.insert(0, str(Path(tp.__file__).resolve().parent))
import skeletal_adopt  # noqa: E402

BAKE = "art/pipeline-candidates/ASSET-TEST-001/h2-bake"
BONES = [["root", None], ["hips", "root"], ["spine", "hips"], ["head", "spine"], ["arm_upper.L", "spine"],
         ["arm_lower.L", "arm_upper.L"], ["hand.L", "arm_lower.L"], ["arm_upper.R", "spine"],
         ["arm_lower.R", "arm_upper.R"], ["hand.R", "arm_lower.R"], ["weapon.R", "hand.R"], ["leg_upper.L", "hips"],
         ["leg_lower.L", "leg_upper.L"], ["foot.L", "leg_lower.L"], ["leg_upper.R", "hips"],
         ["leg_lower.R", "leg_upper.R"], ["foot.R", "leg_lower.R"]]
TEX = {"BC": (60, 70, 140), "N": (128, 128, 255), "ORM": (250, 200, 0), "TeamMask": (255, 255, 255)}


class PointerAndFrameTests(unittest.TestCase):
    def test_json_pointer(self):
        doc = {"a": {"b/c": [10, {"d~e": 5}]}}
        self.assertEqual(skeletal_adopt.pointer(doc, "/a/b~1c/1/d~0e"), 5)
        self.assertIs(skeletal_adopt.pointer(doc, ""), doc)
        with self.assertRaises(skeletal_adopt.AdoptError):
            skeletal_adopt.pointer(doc, "/a/x")

    def test_um_fbx_v1_frames_match_the_measured_ue_map(self):
        # ue(x, y) = (-y_blender, -x_blender) (ART-001, measured on the Medusa candidate; CLI build reports agree)
        f = skeletal_adopt.frames_of({"min": [-10.879, -7.947, 4.797], "max": [11.605, 10.09, 49.741]}, 90.0)
        self.assertEqual(f["ue_predicted"], {"min": [-10.09, -11.605, 4.797], "max": [7.947, 10.879, 49.741]})
        self.assertEqual(f["export_frame"], {"min": [-10.09, -10.879, 4.797], "max": [7.947, 11.605, 49.741]})

    def test_unknown_report_format_is_refused(self):
        with self.assertRaises(skeletal_adopt.AdoptError):
            skeletal_adopt.pointers({"candidate": {"report_format": "h9/1"}})

    def test_embedded_editor_scripts_compile(self):
        # the editor runs these texts verbatim (a real newline inside a string literal broke the first live run)
        for name in ("UE_PY_IMPORT_FBX", "UE_PY_MEASURE_SKELETAL", "UE_PY_LAUNCHER"):
            compile(getattr(tp, name), name, "exec")
        self.assertIn('newline="\\n"', tp.UE_PY_MEASURE_SKELETAL)

    def test_triangle_band_allows_only_the_near_degenerate_slivers(self):
        view = {"meshes_pre_export_m": {"A": {"triangles": 100, "near_degenerate_triangles": 3},
                                        "B": {"triangles": 20, "near_degenerate_triangles": 0},
                                        "SM": {"triangles": 50, "near_degenerate_triangles": 9}},
                "roundtrip": {"skeletal": {"meshes": {"A": {}, "B": {}}}}}
        self.assertEqual(skeletal_adopt.expected_skeletal_triangles(view), {"max": 120, "min": 117, "meshes": ["A", "B"]})


class SkeletalAdoptTests(McpBackendTestBase):
    FOLDER = "/Game/PipelineCandidates/TestHero/H2"

    def setUp(self):
        super().setUp()
        bake = self.repo / BAKE
        for name, data in (("export/SK_Test_H2.fbx", b"Kaydara FBX Binary  \0fake H2 skeletal"),
                           ("export/SM_Test_H2_Base.fbx", b"Kaydara FBX Binary  \0fake H2 base")):
            (bake / name).parent.mkdir(parents=True, exist_ok=True)
            (bake / name).write_bytes(data)
        for key, color in TEX.items():
            png(bake / ("textures/T_Test_H2_%s_2K.png" % key), 8, color)
            png(bake / ("textures/T_Test_H2_%s_4K.png" % key), 16, color)  # local master: never imported
        preset = json.loads(self.preset.read_text(encoding="utf-8"))
        settings = {k: preset[k] for k in skeletal_adopt.PRESET_KEYS}
        settings.update(path_mode="STRIP", bake_anim=False, preset={"name": preset["name"]},
                        deviations_from_preset={"path_mode": "STRIP: textures reach UE from the atlas",
                                                "bake_anim": "no clips"})
        heads = {n: [0.01 * i, 0.0, 0.02 * i] for i, (n, _p) in enumerate(BONES)}
        self.build = {
            "stage": "rig", "profile_id": "test-h2-bake/2", "passed": True, "skeleton": "UM_HUMANOID_17_v2",
            "armature_object": "SKEL_UM_Humanoid",
            "exports": {"skeletal_fbx": {"path": BAKE + "/export/SK_Test_H2.fbx", "sha256": sha(bake / "export/SK_Test_H2.fbx")},
                        "base_fbx": {"path": BAKE + "/export/SM_Test_H2_Base.fbx",
                                     "sha256": sha(bake / "export/SM_Test_H2_Base.fbx")},
                        "settings": settings},
            "roundtrip": {
                "scale_ratio": [1.0, 1.0, 1.0],
                "skeletal": {"armature_objects": ["SKEL_UM_Humanoid"],
                             "bones": {n: {"parent": p, "head_m": heads[n], "tail_m": heads[n]} for n, p in BONES},
                             "meshes": {"SK_Test_H2_Body": {"bounds_m": {"min": [-0.11, -0.08, 0.05], "max": [0.12, 0.1, 0.45]},
                                                            "material_slots": ["M_Test_H2_Atlas"], "triangles": 3000,
                                                            "near_degenerate_triangles": 3, "vertices": 1600},
                                        "SK_Test_H2_Staff": {"bounds_m": {"min": [-0.1, -0.02, 0.07], "max": [-0.06, 0.02, 0.49]},
                                                             "material_slots": ["M_Test_H2_Atlas"], "triangles": 400,
                                                             "near_degenerate_triangles": 0, "vertices": 210}}},
                "base": {"meshes": {"SM_Test_H2_Base": {"bounds_m": {"min": [-0.12, -0.12, 0.0], "max": [0.12, 0.12, 0.05]},
                                                        "material_slots": ["M_Test_H2_Atlas"], "triangles": 224,
                                                        "near_degenerate_triangles": 0}}}},
            "sockets": [{"name": "Weapon", "bone": "weapon.R", "location_uu_for_ue": [0, 0, 0]},
                        {"name": "Head", "bone": "head", "location_uu_for_ue": [-0.1, -1.4, 2.6],
                         "target_ue_component_uu": [2.7, 0.1, 36.7]}],
            "measures": {"hood_top_uu": 44.99},
            "checks": {"export_face_plus_x": {"passed": True}},
        }
        self.write_json(bake / "reports/build-report.json", self.build)
        textures = {}
        for key in TEX:
            for tier, size in (("2K", 8), ("4K", 16)):
                rel = "%s/textures/T_Test_H2_%s_%s.png" % (BAKE, key, tier)
                textures[Path(rel).name] = {"path": rel, "sha256": sha(self.repo / rel), "px": [size, size],
                                            "tier": "runtime_2k" if tier == "2K" else "master_4k"}
        self.textures_report = {"profile_id": "test-h2-bake/2", "textures": textures, "conventions": {
            "BC": "sRGB 8-bit", "N": "DirectX (-Y)", "ORM": "R = AO, G = roughness, B = metallic (linear)",
            "TeamMask": "L 8-bit linear = cloth"}}
        self.write_json(bake / "reports/textures-report.json", self.textures_report)
        self.profile_rel = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/h2-ue.json"
        self.profile = {
            "schema": tp.BUILD_PROFILE_SCHEMA, "profile_id": "test-h2-ue-import/1", "asset_id": "ASSET-TEST-001",
            "kind": "skeletal-adopt", "status": "proposed", "source_role": "glb", "fbx_preset": tp.DEFAULT_FBX_PRESET,
            "candidate": {"dir": BAKE, "report_format": "h2-bake-rig/1", "bake_profile_id": "test-h2-bake/2",
                          "build_report": "reports/build-report.json", "textures_report": "reports/textures-report.json",
                          "fbx": {"skeletal": "export/SK_Test_H2.fbx", "base": "export/SM_Test_H2_Base.fbx"},
                          "textures": {k: "textures/T_Test_H2_%s_2K.png" % k for k in TEX},
                          "texture_px": 8, "texture_tier": "runtime_2k",
                          "conventions_required": {"N": "DirectX", "ORM": "R = AO, G = roughness, B = metallic",
                                                   "TeamMask": "linear"},
                          "top_part": "part_0"},
            "armature": {"object": "SKEL_UM_Humanoid", "skeleton": "UM_HUMANOID_17_v2", "bones": BONES},
            "scale": {"figure_height_m": 0.45},
            "meshes": {"base": {"object": "SM_Test_H2_Base", "footprint_m": [0.24, 0.24, 0.05]}},
            "axes": {"expected_ue_front": "+X"},
            "sockets": [{"name": "Weapon", "bone": "weapon.R", "location_uu": [0, 0, 0]},
                        {"name": "Head", "bone": "head", "location_uu": None}],
            "expectations": {"triangles": {"SK_Test_H2_Body": 3000, "SK_Test_H2_Staff": 400, "SM_Test_H2_Base": 224},
                             "bones": 17, "skeletal_material_slots": 1, "base_material_slots": 1, "skeletal_lods": 1},
            "proposed_limits_for_comparison_only": {"hero_triangles": [3000, 4500], "material_slots_max": 2,
                                                    "height_uu": [40, 48]},
            "ue": {"skeletal_asset": "SK_Test_H2", "base_asset": "SM_Test_H2_Base", "material_route": "um-master",
                   "figure_instance": "MI_Test_H2", "base_instance": "MI_Test_H2_Base",
                   "teams": {"Blue": "#3F6FD8", "Red": "#D0453A"}, "default_team": "Blue",
                   "team_instances": {"figure": "MI_Test_H2_{team}", "base": "MI_Test_H2_Base_{team}"},
                   "team_color_mode": "mask", "figure_parameters": {"TeamDye": 1.0, "TeamDyeGain": 5.5},
                   "base_marker": {"textures": True, "parameters": {"SideBandWeight": 1.0}},
                   "textures": {"BC": {"file_key": "BC", "asset": "T_Test_H2_BC", "srgb": True, "compression": "TC_Default"},
                                "N": {"file_key": "N", "asset": "T_Test_H2_N", "srgb": False,
                                      "compression": "TC_Normalmap", "flip_green": False},
                                "ORM": {"file_key": "ORM", "asset": "T_Test_H2_ORM", "srgb": False,
                                        "compression": "TC_Masks"},
                                "TeamMask": {"file_key": "TeamMask", "asset": "T_Test_H2_TeamMask", "srgb": False,
                                             "compression": "TC_Grayscale"}},
                   "measure_skeletal_triangles": True},
        }
        self.write_json(self.repo / self.profile_rel, self.profile)
        fake_masters(self.ue_state)
        self.env["FAKE_UE_ARMATURE_NODE"] = "SKEL_UM_Humanoid"  # the legacy importer's bone 0 = the armature object
        self.masters_state = self.ue_state.read_text(encoding="utf-8")

    @staticmethod
    def write_json(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def init_run(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "skeletal-adopt", "--build-profile", self.profile_rel)
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))

    def ue(self, *extra, expect=0, env=None):
        return self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER, *extra,
                        expect=expect, env=env)

    def report_json(self, name="ue-import-report.json"):
        return json.loads((self.run_dir / "reports" / name).read_text(encoding="utf-8"))

    def planned(self):
        f = self.FOLDER
        out = [f + "/Meshes/SK_Test_H2", f + "/Meshes/SK_Test_H2_Skeleton", f + "/Meshes/SM_Test_H2_Base",
               f + "/Materials/MI_Test_H2", f + "/Materials/MI_Test_H2_Base"]
        out += [f + "/Materials/MI_Test_H2%s_%s" % (part, team) for part in ("", "_Base") for team in ("Blue", "Red")]
        out += [f + "/Textures/T_Test_H2_%s" % k for k in TEX]
        return sorted(out)

    def test_adopt_import_skip_force_without_numbered_copies(self):
        self.init_run()
        self.cli("preflight", "--run-dir", str(self.run_dir))
        out = self.cli("adopt", "--run-dir", str(self.run_dir))
        self.assertIn("adopt     executed", out.stdout)
        adopt = self.report_json("adopt-report.json")
        self.assertTrue(adopt["passed"], {k: v for k, v in adopt["checks"].items() if not v["passed"]})
        self.assertEqual(adopt["views"]["build"]["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_ue_predicted"],
                         {"min": [-10.0, -12.0, 5.0], "max": [8.0, 11.0, 49.0]})
        self.assertNotIn("4K", json.dumps(adopt["inputs"]), "the local 4K masters are never adopted")
        self.assertEqual(self.blender_calls(), [], "skeletal-adopt never runs Blender stages")
        self.ue()
        report = self.report_json()
        self.assertTrue(report["passed"], {k: v for k, v in report["checks"].items() if not v["passed"]})
        self.assertEqual(report["logic"], tp.UE_SKELETAL_ADOPT_LOGIC_VERSION)
        self.assertEqual(sorted(report["assets"]), self.planned())
        m = report["measured"]
        self.assertEqual(m["skeleton"]["bone0"], "SKEL_UM_Humanoid")
        self.assertIn("weapon_R", m["skeleton"]["bones_in_order"])
        self.assertEqual(m["skeletal_lod0"]["triangles"], 3400)
        self.assertEqual(m["textures"]["N"]["properties"]["bFlipGreenChannel"], False)
        self.assertEqual({k: v["properties"]["SRGB"] for k, v in m["textures"].items()},
                         {"BC": True, "N": False, "ORM": False, "TeamMask": False})
        self.assertEqual(m["um_instances"]["team:figure:Blue"]["read_back"]["vectors"]["TeamColor"],
                         um_masters.hex_to_linear("#3F6FD8"))
        self.assertEqual(m["um_instances"]["figure_instance"]["read_back"]["textures"]["TeamMaskTexture"],
                         self.FOLDER + "/Textures/T_Test_H2_TeamMask")
        # the fake reads the H2 bake's reports next to the imported FBX: the sources are the bake's files
        assets = self.ue_assets()
        self.assertTrue(assets[self.FOLDER + "/Meshes/SK_Test_H2"]["source"].replace("\\", "/")
                        .endswith(BAKE + "/export/SK_Test_H2.fbx"))
        # second import: skipped (fingerprint + editor listing unchanged)
        out = self.ue()
        self.assertIn("skipped", out.stdout)
        # --force: previous assets deleted first, same names again, no Name_1
        self.ue("--force")
        again = self.report_json()
        self.assertTrue(again["passed"])
        self.assertEqual(sorted(again["assets"]), self.planned())
        self.assertEqual(sorted(again["previous_assets_deleted"]), self.planned())
        self.assertFalse([a for a in self.ue_assets() if a.startswith(self.FOLDER) and a[-2:] == "_1"])

    def test_bytes_that_differ_from_the_bake_report_fail_adopt(self):
        self.init_run()
        self.cli("preflight", "--run-dir", str(self.run_dir))
        (self.repo / BAKE / "export/SK_Test_H2.fbx").write_bytes(b"other bytes")
        self.cli("adopt", "--run-dir", str(self.run_dir), expect=1)
        adopt = self.report_json("adopt-report.json")
        self.assertFalse(adopt["checks"]["fbx_bytes_match_bake_report"]["passed"])

    def test_opengl_normal_convention_or_master_tier_fails_adopt(self):
        self.textures_report["conventions"]["N"] = "OpenGL (+Y)"
        self.textures_report["textures"]["T_Test_H2_ORM_2K.png"]["tier"] = "master_4k"
        self.write_json(self.repo / BAKE / "reports/textures-report.json", self.textures_report)
        self.init_run()
        self.cli("preflight", "--run-dir", str(self.run_dir))
        self.cli("adopt", "--run-dir", str(self.run_dir), expect=1)
        checks = self.report_json("adopt-report.json")["checks"]
        self.assertFalse(checks["texture_conventions_as_ue_expects"]["passed"])
        self.assertFalse(checks["textures_are_the_runtime_tier"]["passed"])

    def test_bone_contract_mismatch_fails_adopt(self):
        self.build["roundtrip"]["skeletal"]["bones"]["weapon.R"]["parent"] = "hand.L"
        self.write_json(self.repo / BAKE / "reports/build-report.json", self.build)
        self.init_run()
        self.cli("preflight", "--run-dir", str(self.run_dir))
        self.cli("adopt", "--run-dir", str(self.run_dir), expect=1)
        self.assertFalse(self.report_json("adopt-report.json")["checks"]["skeleton_contract"]["passed"])

    def test_candidate_changed_after_adopt_blocks_ue_import(self):
        self.init_run()
        self.cli("preflight", "--run-dir", str(self.run_dir))
        self.cli("adopt", "--run-dir", str(self.run_dir))
        png(self.repo / BAKE / "textures/T_Test_H2_ORM_2K.png", 8, (1, 2, 3))
        proc = self.ue(expect=1)
        self.assertIn("changed since adopt", proc.stderr)
        self.assertEqual(json.loads(self.ue_state.read_text(encoding="utf-8")), json.loads(self.masters_state),
                         "nothing is imported when an adopted file changed")

    def test_skeletal_triangle_mismatch_fails_the_ue_stage(self):
        self.init_run()
        self.cli("preflight", "--run-dir", str(self.run_dir))
        self.cli("adopt", "--run-dir", str(self.run_dir))
        env = dict(self.env, FAKE_UE_SK_TRIS_DELTA="-10")
        self.ue(expect=1, env=env)
        checks = self.report_json()["checks"]
        self.assertFalse(checks["skeletal_triangles_lod0_as_build"]["passed"])
        self.assertEqual(checks["skeletal_triangles_lod0_as_build"]["expected"]["min"], 3397)

    def test_preflight_refuses_an_unknown_report_format(self):
        self.profile["candidate"]["report_format"] = "h9/1"
        self.write_json(self.repo / self.profile_rel, self.profile)
        self.init_run()
        proc = self.cli("preflight", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("build_profile_valid", proc.stderr)


if __name__ == "__main__":
    unittest.main()
