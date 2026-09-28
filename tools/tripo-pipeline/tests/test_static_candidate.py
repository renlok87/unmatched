"""Unit tests for the static-candidate profile (stage 3 T2.1): preflight -> adopt -> ue-import.

The candidate FBX/BC/N/ORM and its candidate/read-back reports are written by the test (the real ones
come from blender/static_prop_candidate.py and check_static_prop_fbx.py). UnrealEditor is
tests/fake_unreal_mcp.py: import_file returns only the mesh (like UE 5.8 MCP) and a static import
adds one convex collision element (like Interchange), which the stage must remove.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import json
import struct
import unittest
import zlib

from test_mcp_backend import McpBackendTestBase
from test_pipeline import sha, tp

CAND = "art/pipeline-candidates/ASSET-TEST-001/cand"
MASTER = "/Game/S05/M_TestMaster"


def png(path, size, color):
    raw = b"".join(b"\0" + bytes(color) * size for _ in range(size))
    chunks = [(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)), (b"IDAT", zlib.compress(raw)),
              (b"IEND", b"")]
    data = b"\x89PNG\r\n\x1a\n" + b"".join(struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
                                           for t, d in chunks)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


class StaticCandidateTests(McpBackendTestBase):
    FOLDER = "/Game/PipelineCandidates/TestProp/run1/Candidate"

    def setUp(self):
        super().setUp()
        cand = self.repo / CAND
        fbx = cand / "export/SM_Test_Prop.fbx"
        fbx.parent.mkdir(parents=True)
        fbx.write_bytes(b"Kaydara FBX Binary  \0fake static prop")
        for key, color in (("BC", (200, 120, 60)), ("N", (128, 128, 255)), ("ORM", (255, 230, 30))):
            png(cand / ("export/T_Test_Prop_%s.png" % key), 8, color)
        preset = json.loads(self.preset.read_text(encoding="utf-8"))
        settings = {k: preset[k] for k in tp.ADOPT_PRESET_KEYS}
        self.report = {
            "schema": "unmatched.tripo-pipeline.static-prop-candidate/1", "status": "measured",
            "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
            "source": {"path": "tripo-source/t1/model.glb", "sha256": sha(self.glb)},
            "params": {"texture_size": 8},
            "export": {"fbx": fbx.name, "sha256": sha(fbx), "settings": settings,
                       "um_fbx_v1_conformance": [{"setting": "axes", "conforms": True}]},
            "textures": {"outputs": {k: {"path": "T_Test_Prop_%s.png" % k,
                                         "sha256": sha(cand / ("export/T_Test_Prop_%s.png" % k))}
                                     for k in ("BC", "N", "ORM")}},
            "roundtrip": {"triangles": 120, "expected_ue_dimensions_uu_at_import_scale_1": [2.0, 1.8, 3.0]},
            "material_slots": 1, "checks": {"single_mesh": True, "um_fbx_v1_conforms": True}, "checks_passed": True,
        }
        self.write_json(cand / "reports/candidate-report.json", self.report)
        self.write_json(cand / "reports/fbx-readback.json", {
            "fbx": CAND + "/export/SM_Test_Prop.fbx", "mesh_objects": ["SM_Test_Prop"], "armatures": 0,
            "triangles": 120, "material_slots": ["M_Test_Prop"],
            "topology_welded_1um": {"open_edges": 0, "non_manifold_edges": 0, "faces_with_inconsistent_winding": 0},
            "bounds_min_uu": [-1.0, -0.9, 0.0], "bounds_max_uu": [1.0, 0.9, 3.0],
            "protrusion_axis_blender": "+X", "protrusion_direction_deg_from_plus_x_ccw": 3.0})
        self.profile_rel = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/static.json"
        self.profile = {
            "schema": tp.BUILD_PROFILE_SCHEMA, "profile_id": "test-static/1", "asset_id": "ASSET-TEST-001",
            "kind": "static-candidate", "status": "proposed", "source_role": "glb", "fbx_preset": tp.DEFAULT_FBX_PRESET,
            "candidate": {"dir": CAND, "fbx": "export/SM_Test_Prop.fbx", "report": "reports/candidate-report.json",
                          "readback": "reports/fbx-readback.json",
                          "report_schema": "unmatched.tripo-pipeline.static-prop-candidate/1",
                          "textures": {k: "export/T_Test_Prop_%s.png" % k for k in ("BC", "N", "ORM")}},
            "ue": {"static_asset": "SM_Test_Prop", "material": "M_Test_Prop_Candidate",
                   "instance": "MI_Test_Prop_Candidate", "team_color": [1, 1, 1, 1], "collision": "none",
                   "two_sided": False,
                   "shared_master": {"asset": MASTER, "texture_parameters": {"BC": "BaseColorTexture",
                                                                            "N": "NormalTexture", "ORM": "ORMTexture"}},
                   "textures": {"BC": {"asset": "T_Test_Prop_BC", "srgb": True, "compression": "TC_Default"},
                                "N": {"asset": "T_Test_Prop_N", "srgb": False, "compression": "TC_Normalmap",
                                      "flip_green": False},
                                "ORM": {"asset": "T_Test_Prop_ORM", "srgb": False, "compression": "TC_Masks"}}},
            "axes": {"expected_ue_front": "+X", "protrusion_axis_ue": "+X"},
            "expectations": {"pivot_tolerance_uu": 0.05},
        }
        self.write_json(self.repo / self.profile_rel, self.profile)

    @staticmethod
    def write_json(path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    def init_static(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "static-candidate",
                 "--build-profile", self.profile_rel)
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))

    def ue(self, *extra, expect=0, env=None):
        return self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER, *extra,
                        expect=expect, env=env)

    def report_json(self, name="ue-import-report.json"):
        return json.loads((self.run_dir / "reports" / name).read_text(encoding="utf-8"))

    def planned(self, own_material=True):
        f = self.FOLDER
        out = [f + "/Meshes/SM_Test_Prop", f + "/Materials/MI_Test_Prop_Candidate",
               f + "/Textures/T_Test_Prop_BC", f + "/Textures/T_Test_Prop_N", f + "/Textures/T_Test_Prop_ORM"]
        if own_material:
            out.append(f + "/Materials/M_Test_Prop_Candidate")
        return sorted(out)

    def seed_master(self, parameters):
        state = {"assets": {MASTER: {"class": "Material", "parameters": parameters}},
                 "props": {MASTER: {"TwoSided": False, "BlendMode": "BLEND_Opaque"}}, "log": []}
        self.ue_state.write_text(json.dumps(state), encoding="utf-8")

    def test_adopt_then_ue_import_is_idempotent_and_force_makes_no_numbered_copy(self):
        self.init_static()
        out = self.mcp("run", "--run-dir", str(self.run_dir))
        self.assertIn("adopt     executed", out.stdout)
        adopt = self.report_json("adopt-report.json")
        self.assertTrue(adopt["passed"], adopt["checks"])
        self.assertEqual(adopt["expectations_for_ue"]["ue_bounds_uu_predicted"],
                         {"min": [-1.0, -0.9, 0.0], "max": [1.0, 0.9, 3.0]})
        self.assertEqual(self.blender_calls(), [], "static-candidate never runs Blender stages")
        self.ue()
        report = self.report_json()
        self.assertTrue(report["passed"], {k: v for k, v in report["checks"].items() if not v["passed"]})
        self.assertEqual(report["status"], "technically_imported")
        self.assertEqual(sorted(self.ue_assets()), self.planned())
        self.assertEqual(report["measured"]["collision_after_import"]["simple_elements"], 1)
        self.assertEqual(report["measured"]["collision_after_stage"]["simple_elements"], 0)
        self.assertEqual(report["measured"]["material_route"]["used"], "own_material")
        self.assertIn("is absent", report["deviations"][0])
        self.assertEqual(report["checks"]["protrusion_axis_by_bounds"]["measured"]["longer_horizontal_axis"], "X")
        calls_after_first = len(self.ue_calls())
        again = self.ue()
        self.assertIn("ue-import skipped", again.stdout)
        self.assertEqual([c for c in self.ue_calls()[calls_after_first:] if c == "import_file"], [])
        run_again = self.mcp("run", "--run-dir", str(self.run_dir))
        self.assertIn("adopt     skipped", run_again.stdout)
        self.assertIn("ue-import skipped", run_again.stdout)
        forced = self.ue("--force")
        self.assertIn("ue-import executed", forced.stdout)
        self.assertEqual(sorted(self.ue_assets()), self.planned(), "no *_1 after --force")
        report = self.report_json()
        self.assertTrue(report["passed"])
        self.assertEqual(sorted(report["previous_assets_deleted"]), self.planned())

    def test_shared_master_with_texture_parameters_is_used(self):
        self.init_static()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.seed_master([{"type": "Texture", "name": n} for n in ("BaseColorTexture", "NormalTexture", "ORMTexture")]
                         + [{"type": "Vector", "name": "TeamColor"}])
        self.ue()
        report = self.report_json()
        self.assertTrue(report["passed"], {k: v for k, v in report["checks"].items() if not v["passed"]})
        self.assertEqual(report["measured"]["material_route"]["used"], "shared_master")
        self.assertEqual(report["deviations"], [])
        self.assertEqual(sorted(a for a in self.ue_assets() if a != MASTER), self.planned(own_material=False))

    def test_shared_master_without_texture_parameters_is_a_recorded_deviation(self):
        self.init_static()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.seed_master([{"type": "Vector", "name": "BaseColor"}, {"type": "Vector", "name": "TeamColor"}])
        self.ue()
        report = self.report_json()
        self.assertTrue(report["passed"])
        route = report["measured"]["material_route"]
        self.assertEqual(route["used"], "own_material")
        self.assertEqual(route["missing_texture_parameters"], ["BaseColorTexture", "NormalTexture", "ORMTexture"])
        self.assertIn("has no texture parameters", report["deviations"][0])

    def test_adopt_refuses_bytes_that_differ_from_the_candidate_report(self):
        self.init_static()
        (self.repo / CAND / "export/T_Test_Prop_N.png").write_bytes(b"\x89PNG\r\n\x1a\nchanged")
        proc = self.mcp("run", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("texture_bytes_match_candidate_report", proc.stderr)
        self.assertEqual(self.ue_calls(), [])

    def test_candidate_changed_after_adopt_blocks_ue_import(self):
        self.init_static()
        self.mcp("run", "--run-dir", str(self.run_dir))
        with open(self.repo / CAND / "export/SM_Test_Prop.fbx", "ab") as handle:
            handle.write(b"x")
        proc = self.ue(expect=1)
        self.assertIn("changed since adopt", proc.stderr)
        self.assertNotIn("import_file", self.ue_calls())

    def test_ue_contract_failures_are_reported(self):
        self.init_static()
        self.mcp("run", "--run-dir", str(self.run_dir))
        env = dict(self.env, FAKE_UE_TRIS_DELTA="-2")
        proc = self.ue(expect=1, env=env)
        self.assertIn("triangles_lod0_equal_candidate", proc.stderr)
        self.assertEqual(self.report_json()["status"], "failed")

    def test_foreign_asset_in_folder_is_a_conflict(self):
        self.init_static()
        self.mcp("run", "--run-dir", str(self.run_dir))
        foreign = self.FOLDER + "/Meshes/SM_Someone_Else"
        self.ue_state.write_text(json.dumps({"assets": {foreign: {"class": "StaticMesh"}}, "props": {}, "log": []}),
                                 encoding="utf-8")
        proc = self.ue(expect=tp.EXIT_CONFLICT)
        self.assertIn("did not create", proc.stderr)
        self.assertEqual(sorted(self.ue_assets()), [foreign])

    def test_build_profile_is_required_and_only_for_profiles_that_read_it(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "static-candidate", expect=tp.EXIT_USAGE)
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--build-profile", self.profile_rel, expect=tp.EXIT_USAGE)


if __name__ == "__main__":
    unittest.main()
