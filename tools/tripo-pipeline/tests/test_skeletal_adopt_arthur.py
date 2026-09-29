"""Unit tests of W5c-A (tool 0.7.0): profile skeletal-adopt on an h2_bake_arthur bake (report format h2-bake-arthur/1).

The bake reports (rig-report schema unmatched.h2-bake.rig/1, textures-report schema unmatched.h2-bake.textures/2,
manifest-h2, validate-skeletal-mesh-v2) are written by the test in the shape h2_bake_arthur writes them; the normaliser
skeletal_adopt_formats.arthur_h2 turns them into the h2-bake-rig/1 layout skeletal_adopt.adopt() reads. UnrealEditor is
tests/fake_unreal_mcp.py: for such a bake it maps the FBX read-back (export frame) to UE on its own, so the adopt views
must agree with an independent mapping. The last class runs adopt on the real King Arthur H2.1 bake of the repo.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

from test_mcp_backend import McpBackendTestBase
from test_pipeline import TESTS, sha, tp
from test_static_candidate import png
from test_um_master import fake_masters

sys.path.insert(0, str(TESTS.parent))
import skeletal_adopt  # noqa: E402
import skeletal_adopt_formats as formats  # noqa: E402

BAKE = "art/pipeline-candidates/ASSET-TEST-001/h2bake"
BAKE_PROFILE = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/test-h2-bake.json"
PROFILE = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/test-h2-ue-import.json"
FOLDER = "/Game/PipelineCandidates/Test/H2"
BONES = [["root", None], ["hips", "root"], ["head", "hips"], ["weapon.R", "hips"]]
MAPS = {"BC": "sRGB 8-bit", "N": "linear, DirectX for UE (green inverted), UE: TC_Normalmap, flip_green false",
        "N_OpenGL": "linear, OpenGL/Blender (+Y)", "ORM": "linear: R AO, G roughness, B metallic; UE: sRGB off, TC_Masks",
        "TeamMask": "linear: R cloth, G base band, B 0, A 255; UE: sRGB off (M_UM_Figure reads R)"}


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1), encoding="utf-8")


def make_arthur_bake(repo: Path, preset: dict) -> dict:
    """A small h2_bake_arthur-shaped bake: FBX pair, runtime_2k maps (8 px), the four reports. Returns the rig report."""
    base = repo / BAKE
    for name, body in (("SK_Test_H2.fbx", b"Kaydara FBX Binary  \0sk"), ("SM_Test_H2_Base.fbx", b"Kaydara FBX Binary  \0base")):
        (base / "export").mkdir(parents=True, exist_ok=True)
        (base / "export" / name).write_bytes(body)
    colours = {"BC": (180, 40, 40), "N": (128, 128, 255), "N_OpenGL": (128, 127, 255), "ORM": (255, 140, 200),
               "TeamMask": (255, 0, 0)}
    for key, colour in colours.items():
        png(base / ("textures/runtime_2k/T_Test_H2_%s.png" % key), 8, colour)
    write_json(repo / BAKE_PROFILE, {"schema": "unmatched.h2-bake.profile/1", "profile_id": "test-h2-bake/1",
                                     "asset_id": "ASSET-TEST-001", "status": "proposed"})
    sk_rel, base_rel = BAKE + "/export/SK_Test_H2.fbx", BAKE + "/export/SM_Test_H2_Base.fbx"
    settings = {k: preset[k] for k in skeletal_adopt.PRESET_KEYS}
    settings.update(path_mode="STRIP", bake_anim=False, preset={"name": preset["name"]},
                    deviations_from_preset={"path_mode": "STRIP: textures from the atlas", "bake_anim": "no clips"})

    def mesh(lo, hi, tris):
        return {"bounds_m_fbx_frame": {"min": lo, "max": hi}, "material_slots": ["M_Test_H2"], "triangles": tris,
                "polygons": tris, "vertices": tris, "near_degenerate_triangles": 0,
                "near_degenerate_area_cm2_below": 0.0001, "uv_layers": ["UVMap"], "uv0_in_unit_square": True}

    rig = {
        "schema": "unmatched.h2-bake.rig/1", "profile": BAKE_PROFILE, "failed": [],
        "armature": {"object": "SKEL_UM_Humanoid", "skeleton": "UM_HUMANOID_17_v2 (test contract)",
                     "bones_final_m": {b[0]: [[0, 0, i * 0.1], [0, 0, i * 0.1 + 0.05]] for i, b in enumerate(BONES)}},
        "checks": {"readback_face_plus_x": {"passed": True, "measured": -2.1, "expected": "0 +- 10 deg"},
                   "single_material_slot": {"passed": True}},
        "exports": {"skeletal_fbx": {"file": sk_rel, "sha256": sha(repo / sk_rel), "bytes": 22},
                    "base_fbx": {"file": base_rel, "sha256": sha(repo / base_rel), "bytes": 24}, "settings": settings},
        # body in the authored frame (front -Y): x -0.14..0.16, y -0.12..0.08 -> export frame (rot 90): x = -y, y = x
        "geometry": {"bounds_body_m": {"min": [-0.14, -0.12, 0.058], "max": [0.16, 0.08, 0.55]},
                     "figure_height_m": 0.55, "sword_tip_m": 0.60, "triangles_total": 150},
        "readback": {
            "skeletal": {"armatures": ["SKEL_UM_Humanoid.001"],
                         "bones": {b[0]: {"parent": b[1]} for b in BONES},
                         "meshes": {"SK_Test_H2_Body.001": mesh([-0.08, -0.14, 0.058], [0.12, 0.16, 0.55], 100),
                                    "SK_Test_H2_Sword.001": mesh([0.05, -0.11, 0.32], [0.08, -0.04, 0.60], 20)}},
            "base": {"armatures": [], "meshes": {"SM_Test_H2_Base.001": mesh([-0.15, -0.15, 0.0], [0.15, 0.15, 0.06], 30)}}},
        "sockets": [
            {"name": "Weapon", "bone": "weapon.R", "location_uu_for_ue": [0.0, 0.0, 0.0], "target_ue_component_uu": [6, 7, 37]},
            {"name": "Head", "bone": "head", "location_uu_for_ue": [0.0, -4.388, -0.603],
             "target_ue_component_uu": [-0.3, 0.0, 50.0], "offset_blender_bone_local_uu": [0.0, 4.388, -0.603]}],
    }
    write_json(base / "reports/rig-report.json", rig)
    outputs = {}
    for key in colours:
        rel = BAKE + "/textures/runtime_2k/T_Test_H2_%s.png" % key
        outputs[key] = {"file": rel, "sha256": sha(repo / rel), "px": [8, 8], "colour": MAPS[key], "bytes": 1}
    write_json(base / "reports/textures-report.json", {"schema": "unmatched.h2-bake.textures/2", "atlas_px": 16,
                                                         "outputs": {"runtime_2k": outputs}})
    files = [{"file": sk_rel, "sha256": sha(repo / sk_rel)}, {"file": base_rel, "sha256": sha(repo / base_rel)}]
    files += [{"file": v["file"], "sha256": v["sha256"]} for v in outputs.values()]
    write_json(base / "reports/manifest-h2.json", {"schema": "unmatched.h2-bake.manifest/1", "profile": BAKE_PROFILE,
                                                    "profile_sha256": sha(repo / BAKE_PROFILE), "files": files})
    write_json(base / "reports/validate-skeletal-mesh-v2.json", {
        "schema": "unmatched.clip-validation/2", "clip": sk_rel, "clip_sha256": sha(repo / sk_rel),
        "skeleton": "UM_HUMANOID_17_v2", "kind": "skeletal-mesh", "result": "pass", "fails": [], "warnings": []})
    return rig


def import_profile() -> dict:
    return {
        "schema": tp.BUILD_PROFILE_SCHEMA, "kind": "skeletal-adopt", "profile_id": "test-h2-ue-import/1",
        "asset_id": "ASSET-TEST-001", "status": "proposed", "source_role": "glb", "fbx_preset": tp.DEFAULT_FBX_PRESET,
        "candidate": {"report_format": "h2-bake-arthur/1", "dir": BAKE, "bake_profile": BAKE_PROFILE,
                      "bake_profile_id": "test-h2-bake/1", "build_report": "reports/rig-report.json",
                      "textures_report": "reports/textures-report.json",
                      "extra_reports": {"manifest": "reports/manifest-h2.json",
                                        "validate_report": "reports/validate-skeletal-mesh-v2.json"},
                      "fbx": {"skeletal": "export/SK_Test_H2.fbx", "base": "export/SM_Test_H2_Base.fbx"},
                      "body_object": "SK_Test_H2_Body", "top_part": "tripo_part_6", "texture_tier": "runtime_2k",
                      "texture_px": 8,
                      "textures": {k: "textures/runtime_2k/T_Test_H2_%s.png" % k for k in ("BC", "N", "ORM", "TeamMask")},
                      "conventions_required": {"BC": "sRGB", "N": "DirectX", "ORM": "R AO, G roughness, B metallic",
                                               "TeamMask": "linear: R cloth"}},
        "armature": {"skeleton": "UM_HUMANOID_17_v2", "object": "SKEL_UM_Humanoid", "bones": BONES},
        "scale": {"figure_height_m": 0.55},
        "meshes": {"base": {"object": "SM_Test_H2_Base", "footprint_m": [0.3, 0.3, 0.06]}},
        "axes": {"expected_ue_front": "+X"},
        "sockets": [{"name": "Weapon", "bone": "weapon.R", "location_uu": [0, 0, 0]},
                    {"name": "Head", "bone": "head", "location_uu": None}],
        "ue": {"skeletal_asset": "SK_Test_H2", "base_asset": "SM_Test_H2_Base", "material_route": "um-master",
               "figure_instance": "MI_Test_H2", "base_instance": "MI_Test_H2_Base",
               "teams": {"Blue": "#3F6FD8", "Red": "#D0453A"}, "default_team": "Blue",
               "team_instances": {"figure": "MI_Test_H2_{team}", "base": "MI_Test_H2_Base_{team}"},
               "team_color_mode": "mask", "figure_parameters": {"TeamDye": 1.0, "TeamDyeGain": 5.65},
               "base_marker": {"textures": True, "parameters": {"SideBandWeight": 1.0, "VertexMaskWeight": 0.0}},
               "textures": {"BC": {"file_key": "BC", "srgb": True, "compression": "TC_Default", "asset": "T_Test_H2_BC"},
                            "N": {"file_key": "N", "srgb": False, "compression": "TC_Normalmap", "flip_green": False,
                                  "asset": "T_Test_H2_N"},
                            "ORM": {"file_key": "ORM", "srgb": False, "compression": "TC_Masks", "asset": "T_Test_H2_ORM"},
                            "TeamMask": {"file_key": "TeamMask", "srgb": False, "compression": "TC_Grayscale",
                                         "asset": "T_Test_H2_TeamMask"}}},
        "expectations": {"triangles": {"SK_Test_H2_Body": 100, "SK_Test_H2_Sword": 20, "SM_Test_H2_Base": 30},
                         "skeletal_material_slots": 1, "base_material_slots": 1},
        "proposed_limits_for_comparison_only": {"hero_triangles": [100, 200], "material_slots_max": 2,
                                                "height_uu": [52, 56]},
    }


class ArthurNormaliserTests(McpBackendTestBase):
    """skeletal_adopt.adopt() with the h2-bake-arthur/1 normaliser (no CLI, no UE)."""

    def setUp(self):
        super().setUp()
        self.preset_data = json.loads(self.preset.read_text(encoding="utf-8"))
        self.rig = make_arthur_bake(self.repo, self.preset_data)
        self.profile = import_profile()

    def adopt(self, profile=None):
        return skeletal_adopt.adopt(profile or self.profile, lambda rel: self.repo / rel, sha,
                                    lambda p: tp.inspect_png(p).get("pixels"), self.preset_data)

    def test_arthur_bake_adopts_with_every_check_passing(self):
        res = self.adopt()
        self.assertTrue(res["passed"], json.dumps({k: v for k, v in res["checks"].items() if not v["passed"]}, indent=1))
        norm = res["bake"]["normalised"]
        self.assertEqual(norm["format"], "h2-bake-arthur/1")
        self.assertTrue(all(c["passed"] for c in norm["checks"].values()))
        self.assertEqual(norm["renamed_readback_objects"]["SKEL_UM_Humanoid.001"], "SKEL_UM_Humanoid")
        # the extra reports and the bake profile are pinned inputs too
        for rel in (BAKE + "/reports/manifest-h2.json", BAKE + "/reports/validate-skeletal-mesh-v2.json", BAKE_PROFILE):
            self.assertIn(rel, res["inputs"])

    def test_views_agree_with_the_export_frame_read_back(self):
        view = self.adopt()["views"]["build"]
        exp = view["expected_ue_bounds_uu_at_import_scale_1"]
        # read-back (export frame, m) of body + sword: x -0.08..0.12, y -0.14..0.16, z 0.058..0.60 -> UE (x, -y, z) cm
        self.assertEqual(exp["skeletal_ue_predicted"], {"min": [-8.0, -16.0, 5.8], "max": [12.0, 14.0, 60.0]})
        self.assertEqual(exp["base_ue_predicted"], {"min": [-15.0, -15.0, 0.0], "max": [15.0, 15.0, 6.0]})
        self.assertEqual(view["figure"]["figure_top_m"], 0.55)
        self.assertEqual(sorted(view["roundtrip"]["skeletal"]["meshes"]), ["SK_Test_H2_Body", "SK_Test_H2_Sword"])

    def test_normalised_scale_ratio_is_measured_from_the_body(self):
        rig = copy.deepcopy(self.rig)
        rig["geometry"]["bounds_body_m"]["max"][2] = 0.60  # pre-export body taller than the read-back
        build, _tex, _info = formats.arthur_h2(rig, json.loads((self.repo / BAKE / "reports/textures-report.json")
                                                                .read_text(encoding="utf-8")),
                                               self.profile, lambda rel: self.repo / rel, sha)
        self.assertNotEqual(build["roundtrip"]["scale_ratio"], [1.0, 1.0, 1.0])

    def test_manifest_that_does_not_list_the_bytes_fails_adopt(self):
        path = self.repo / BAKE / "reports/manifest-h2.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["files"][2]["sha256"] = "0" * 64
        write_json(path, data)
        res = self.adopt()
        self.assertFalse(res["checks"]["bake_report_passed"]["passed"])
        self.assertFalse(res["bake"]["normalised"]["checks"]["bake_manifest_lists_the_adopted_bytes"]["passed"])

    def test_failed_rig_contract_validation_fails_adopt(self):
        path = self.repo / BAKE / "reports/validate-skeletal-mesh-v2.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data.update(result="fail", fails=["weapon bone missing"])
        write_json(path, data)
        res = self.adopt()
        self.assertFalse(res["passed"])
        self.assertFalse(res["bake"]["normalised"]["checks"]["rig_contract_validation_pass"]["passed"])

    def test_opengl_normal_is_not_accepted_as_n(self):
        profile = copy.deepcopy(self.profile)
        profile["candidate"]["textures"]["N"] = "textures/runtime_2k/T_Test_H2_N_OpenGL.png"
        res = self.adopt(profile)
        conv = res["checks"]["texture_conventions_as_ue_expects"]
        self.assertFalse(conv["passed"])
        self.assertIn("OpenGL", conv["measured"]["N"])
        self.assertFalse(res["passed"])

    def test_wrong_report_schema_is_an_adopt_error(self):
        path = self.repo / BAKE / "reports/rig-report.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema"] = "unmatched.h2-bake.rig/0"
        write_json(path, data)
        with self.assertRaises(skeletal_adopt.AdoptError):
            self.adopt()


class ArthurSkeletalAdoptCliTests(McpBackendTestBase):
    """init -> register-source -> run (preflight, adopt) -> ue-import (fake editor), twice, and --force."""

    def setUp(self):
        super().setUp()
        make_arthur_bake(self.repo, json.loads(self.preset.read_text(encoding="utf-8")))
        write_json(self.repo / PROFILE, import_profile())
        fake_masters(self.ue_state)
        self.env["FAKE_UE_ARMATURE_NODE"] = "SKEL_UM_Humanoid"

    def prepared(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "skeletal-adopt", "--build-profile", PROFILE)
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))
        self.cli("run", "--run-dir", str(self.run_dir))

    def ue(self, *extra, expect=0):
        return self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", FOLDER, *extra, expect=expect)

    def report(self):
        return json.loads((self.run_dir / "reports/ue-import-report.json").read_text(encoding="utf-8"))

    def test_import_twice_then_force_keeps_one_asset_set(self):
        self.prepared()
        adopt = json.loads((self.run_dir / "reports/adopt-report.json").read_text(encoding="utf-8"))
        self.assertTrue(adopt["passed"])
        self.assertEqual(adopt["bake"]["normalised"]["format"], "h2-bake-arthur/1")
        self.ue()
        rep = self.report()
        self.assertTrue(rep["passed"], json.dumps({k: v for k, v in rep["checks"].items() if not v["passed"]},
                                                  indent=1)[:4000])
        for name in ("bone0_is_armature_object_node", "front_axis_as_fbx_preset", "skeletal_bounds_equal_um_fbx_v1_prediction",
                     "figure_height_as_profile", "base_footprint_pivot", "sockets_weapon_head",
                     "textures_size_colour_space_compression", "um_instances_parent_textures_values"):
            self.assertTrue(rep["checks"][name]["passed"], name)
        tex = rep["measured"]["textures"]
        self.assertEqual(tex["TeamMask"]["properties"]["CompressionSettings"], "TC_Grayscale")
        self.assertIs(tex["ORM"]["properties"]["SRGB"], False)
        first = sorted(a for a in self.ue_assets() if a.startswith(FOLDER + "/"))
        self.assertEqual(len(first), 13)  # SK, skeleton, base, 4 textures, 2 MIs, 2 x 2 team MIs
        out = self.ue()
        self.assertIn("skipped", out.stdout)
        self.assertEqual(sorted(a for a in self.ue_assets() if a.startswith(FOLDER + "/")), first)
        self.ue("--force")
        again = sorted(a for a in self.ue_assets() if a.startswith(FOLDER + "/"))
        self.assertEqual(again, first)
        self.assertFalse([a for a in again if a.endswith("_1")])
        self.assertTrue(self.report()["passed"])

    def test_texture_changed_after_adopt_blocks_the_ue_stage(self):
        self.prepared()
        png(self.repo / BAKE / "textures/runtime_2k/T_Test_H2_ORM.png", 8, (255, 10, 10))
        proc = self.ue(expect=1)
        self.assertIn("changed since adopt", proc.stderr)
        self.assertEqual([a for a in self.ue_assets() if a.startswith(FOLDER + "/")], [],
                         "nothing is imported from a candidate that changed after adopt")


REPO = Path(tp.__file__).resolve().parents[2]
REAL_PROFILE = REPO / "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-h2-ue-import.json"


@unittest.skipUnless(REAL_PROFILE.is_file() and
                     (REPO / "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-bake/reports/rig-report.json").is_file(),
                     "King Arthur H2.1 bake not in this checkout")
class RealArthurBakeTests(unittest.TestCase):
    def test_real_arthur_h21_bake_adopts(self):
        profile = json.loads(REAL_PROFILE.read_text(encoding="utf-8"))
        preset = json.loads((REPO / profile["fbx_preset"]).read_text(encoding="utf-8"))
        res = skeletal_adopt.adopt(profile, lambda rel: REPO / rel,
                                   lambda p: hashlib.sha256(p.read_bytes()).hexdigest(),
                                   lambda p: tp.inspect_png(p).get("pixels"), preset)
        self.assertTrue(res["passed"], json.dumps({k: v for k, v in res["checks"].items() if not v["passed"]}, indent=1))
        exp = res["views"]["build"]["expected_ue_bounds_uu_at_import_scale_1"]
        # rig-report readback.skeletal.ue_predicted_bounds_uu of the bake (rounded to 0.01 uu there)
        self.assertEqual([round(v, 2) for v in exp["skeletal_ue_predicted"]["min"]], [-8.02, -16.02, 5.81])
        self.assertEqual([round(v, 2) for v in exp["skeletal_ue_predicted"]["max"]], [12.68, 14.43, 60.06])
        self.assertEqual(res["views"]["build"]["figure"]["figure_top_m"], 0.55)


if __name__ == "__main__":
    unittest.main()
