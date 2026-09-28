"""Unit tests for the skeletal-candidate profile (T4): atlas -> build -> ue-import.

The atlas stage runs for real (workspace Python + Pillow/numpy) on a small textured
GLB written by the test. Blender is tests/fake_blender.py (headless and --mcp), the
UnrealEditor is tests/fake_unreal_mcp.py, which refuses to import onto an existing
name exactly like the real UE 5.8 MCP import_file.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
"""

import io
import json
import struct
import sys
import unittest
from pathlib import Path

from test_mcp_backend import FAKE_UE, McpBackendTestBase
from test_pipeline import FAKE, sha, tp

try:
    import numpy  # noqa: F401
    from PIL import Image
except ImportError:  # pragma: no cover - the atlas stage needs them too
    Image = None

PARTS = ("tripo_part_0", "tripo_part_1", "tripo_part_2")


def png_bytes(color, size=8):
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="PNG")
    return buf.getvalue()


def make_textured_glb(path: Path):
    """Three mesh parts, each with base/metal-rough/normal PNGs embedded in the BIN chunk."""
    binary, views, images, textures, materials, meshes, nodes, accessors = b"", [], [], [], [], [], [], []
    for i, name in enumerate(PARTS):
        tex = {}
        for key, color in (("base", (200, 100 + i * 40, 50)), ("rm", (0, 128, 30 * i)), ("normal", (128, 128, 255))):
            data = png_bytes(color)
            views.append({"buffer": 0, "byteOffset": len(binary), "byteLength": len(data)})
            binary += data + b"\0" * (-len(data) % 4)
            images.append({"bufferView": len(views) - 1, "mimeType": "image/png"})
            textures.append({"source": len(images) - 1})
            tex[key] = len(textures) - 1
        materials.append({"pbrMetallicRoughness": {"baseColorFactor": [0.800000011920929] * 3 + [1.0],
                                                   "baseColorTexture": {"index": tex["base"]},
                                                   "metallicRoughnessTexture": {"index": tex["rm"]}},
                          "normalTexture": {"index": tex["normal"]}})
        accessors.append({"count": 12 * (i + 1), "componentType": 5125, "type": "SCALAR"})
        accessors.append({"count": 8, "componentType": 5126, "type": "VEC3"})
        meshes.append({"name": name, "primitives": [{"indices": len(accessors) - 2, "material": i,
                                                     "attributes": {"POSITION": len(accessors) - 1}}]})
        nodes.append({"name": name, "mesh": i})
    doc = {"asset": {"version": "2.0", "generator": "Tripo"}, "scene": 0, "scenes": [{"nodes": [0, 1, 2]}],
           "nodes": nodes, "meshes": meshes, "accessors": accessors, "materials": materials, "images": images,
           "textures": textures, "bufferViews": views, "buffers": [{"byteLength": len(binary)}]}
    body = json.dumps(doc).encode("utf-8")
    body += b" " * (-len(body) % 4)
    total = 12 + 8 + len(body) + 8 + len(binary)
    data = (struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<I4s", len(body), b"JSON") + body
            + struct.pack("<I4s", len(binary), b"BIN\0") + binary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def make_profile(path: Path):
    profile = {
        "schema": tp.BUILD_PROFILE_SCHEMA, "profile_id": "test-profile/1", "asset_id": "ASSET-TEST-001",
        "status": "proposed", "source_role": "glb", "expected_part_count": 3,
        "atlas": {"size": 64, "gutter_px": 2, "texture_prefix": "T_Test_Atlas", "base_color_factor_expected": 0.800000011920929,
                  "orm_occlusion_fill": 255, "background": {"BC": [128, 128, 128], "N_OpenGL": [128, 128, 255],
                                                            "ORM": [255, 220, 0]}},
        "scale": {"figure_height_m": 0.55},
        "meshes": {"body": {"object": "SK_Test_Body", "mesh": "Test_Body", "active_part": "tripo_part_0"},
                   "bow": {"object": "SK_Test_Bow", "part": "tripo_part_1", "bone": "weapon"},
                   "base": {"object": "SM_Test_Base", "part": "tripo_part_2", "footprint_m": [0.3, 0.3, 0.06]}},
        "materials": {"atlas": "M_Atlas"},
        "orientation": {"method": "ray-escape", "flip_below_score": -0.5, "expected_inside_out_parts": [],
                        "min_score_after_fix": 0.5},
        "armature": {"object": "SKEL_Test", "max_influences": 2,
                     "bones": [["root", None, [0, 0, 0], [0, 0, 0.1]], ["weapon", "root", [0.1, 0, 0.3], [0.12, 0, 0.3]]]},
        "weights": [{"parts": ["tripo_part_0"], "bone": "root"}],
        "fbx_preset": tp.DEFAULT_FBX_PRESET,
        "axes": {"expected_ue_front": "+X", "expected_ue_front_source": "test: 04 §1 / UM_FBX_v1"},
        "exports": {"skeletal_fbx": "SK_Test_Candidate.fbx", "base_fbx": "SM_Test_Base_Candidate.fbx"},
        "sockets": [{"name": "Weapon", "bone": "weapon", "location_uu": [0, 0, 0]},
                    {"name": "Head", "bone": "root", "location_uu": [0, 0, 4]}],
        "ue": {"skeletal_asset": "SK_Test_Candidate", "base_asset": "SM_Test_Base_Candidate", "material": "M_Test_Atlas",
               "default_instance": "MI_Test_Blue",
               "instances": {"MI_Test_Blue": [0.72, 0.85, 1.0, 1.0], "MI_Test_Red": [1.0, 0.76, 0.7, 1.0]},
               "textures": {"BC": {"asset": "T_Test_BC", "file_key": "BC", "srgb": True, "compression": "TC_Default"},
                            "N": {"asset": "T_Test_N", "file_key": "N", "srgb": False, "compression": "TC_Normalmap",
                                  "flip_green": False},
                            "ORM": {"asset": "T_Test_ORM", "file_key": "ORM", "srgb": False, "compression": "TC_Masks"}}},
        "expectations": {"triangles": {"SK_Test_Body": 4, "SK_Test_Bow": 8, "SM_Test_Base": 12},
                         "bones": 2, "skeletal_material_slots": 2, "base_material_slots": 1},
        "proposed_limits_for_comparison_only": {"hero_triangles": [15000, 25000], "material_slots_max": 3,
                                                "height_uu": [50, 55], "texture_px": 2048},
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=1), encoding="utf-8")
    return profile


@unittest.skipIf(Image is None, "Pillow/numpy not installed (atlas stage needs them)")
class CandidateProfileTests(McpBackendTestBase):
    FOLDER = "/Game/PipelineCandidates/Test/cand1"

    def setUp(self):
        super().setUp()
        make_textured_glb(self.glb)
        self.spec["files"][0]["expected_sha256"] = sha(self.glb)
        self.spec["expectations"] = {"glb": {"glb_mesh_count": 3, "glb_materials": 3, "glb_images": 9}}
        self.write_spec()
        self.profile_rel = "art/pipeline-candidates/ASSET-TEST-001/build-profiles/test.json"
        self.profile = make_profile(self.repo / self.profile_rel)
        self.source_state = (sha(self.glb), self.glb.stat().st_mtime_ns)

    def init_candidate(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "skeletal-candidate",
                 "--build-profile", self.profile_rel)
        self.cli("register-source", "--run-dir", str(self.run_dir), "--spec", str(self.spec_path))

    def ue(self, *extra, expect=0, env=None):
        return self.mcp("ue-import", "--run-dir", str(self.run_dir), "--ue-folder", self.FOLDER, *extra,
                        expect=expect, env=env)

    def expected_assets(self):
        f = self.FOLDER
        return sorted([f + "/Meshes/SK_Test_Candidate", f + "/Meshes/SK_Test_Candidate_Skeleton",
                       f + "/Meshes/SM_Test_Base_Candidate", f + "/Materials/M_Test_Atlas",
                       f + "/Materials/MI_Test_Blue", f + "/Materials/MI_Test_Red",
                       f + "/Textures/T_Test_BC", f + "/Textures/T_Test_N", f + "/Textures/T_Test_ORM"])

    def test_candidate_stages_run_and_second_run_is_noop(self):
        self.init_candidate()
        out = self.cli("run", "--run-dir", str(self.run_dir))
        for stage in ("preflight", "import", "verify", "atlas", "build"):
            self.assertIn("%-9s executed" % stage, out.stdout)
        self.assertNotIn("export    ", out.stdout)
        self.assertEqual(self.blender_calls(), ["import", "build"])
        atlas = json.loads((self.run_dir / "reports/atlas-report.json").read_text(encoding="utf-8"))
        self.assertTrue(atlas["passed"])
        self.assertTrue(atlas["checks"]["normal_directx_is_opengl_with_inverted_green"]["passed"])
        for key in ("BC", "N", "N_OpenGL", "ORM"):
            self.assertTrue((self.run_dir / "textures" / ("T_Test_Atlas_%s.png" % key)).is_file())
        m = self.manifest()
        self.assertEqual(sorted(e["path"] for e in m["exports"]),
                         ["export/SK_Test_Candidate.fbx", "export/SM_Test_Base_Candidate.fbx"])
        first = tp.snapshot(self.run_dir)
        out = self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("build     skipped", out.stdout)
        self.assertIn("atlas     skipped", out.stdout)
        self.assertEqual(tp.snapshot(self.run_dir), first)
        self.assertEqual(self.blender_calls(), ["import", "build"])
        self.assertSourceUntouched()

    def test_passthrough_stage_refused_and_profile_required(self):
        self.cli("init", "--run-dir", str(self.run_dir), "--asset-id", "ASSET-TEST-001", "--primary-source",
                 "tripo-t1", "--primary-role", "glb", "--profile", "skeletal-candidate", expect=tp.EXIT_USAGE)
        self.assertFalse((self.run_dir / "manifest.json").exists())
        self.init_candidate()
        self.cli("run", "--run-dir", str(self.run_dir))
        proc = self.cli("export", "--run-dir", str(self.run_dir), expect=tp.EXIT_USAGE)
        self.assertIn("not part of profile", proc.stderr)

    def test_profile_change_rebuilds_but_identical_fbx_is_not_duplicated(self):
        self.init_candidate()
        self.cli("run", "--run-dir", str(self.run_dir))
        profile_path = self.repo / self.profile_rel
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        data["status_note"] = "wording only"
        profile_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        out = self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("atlas     executed", out.stdout)
        self.assertIn("build     executed", out.stdout)
        m = self.manifest()
        current = [e for e in m["exports"] if not e.get("superseded_by")]
        self.assertEqual(len(current), 2)
        self.assertEqual(len([e for e in m["exports"] if e["path"].endswith("SM_Test_Base_Candidate.fbx")]), 1,
                         "base FBX bytes did not change: no second entry")

    def test_failed_build_check_is_reported_and_resumable(self):
        self.init_candidate()
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1,
                        env=dict(self.env, FAKE_BUILD_FAIL_CHECK="orientation"))
        self.assertIn("build", proc.stderr)
        self.assertEqual(self.manifest()["stages"]["build"]["status"], "failed")
        self.cli("run", "--run-dir", str(self.run_dir))
        self.assertEqual(self.manifest()["stages"]["build"]["status"], "completed")

    def test_ue_candidate_import_forced_reimport_and_probe(self):
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.ue()
        self.assertEqual(sorted(self.ue_assets()), self.expected_assets())
        report = json.loads((self.run_dir / "reports/ue-import-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "technically_imported", json.dumps(
            {k: c for k, c in report["checks"].items() if not c["passed"]}, indent=1))
        self.assertEqual(report["measured"]["skeleton"]["bone0"], "SKEL_Test")
        self.assertEqual(report["checks"]["base_triangles"]["measured"], 11, "12 minus 1 near-degenerate sliver")
        self.assertEqual(report["measured"]["axis_mapping"][0]["blender_front_minus_y_becomes"], "+X")
        self.assertTrue(report["checks"]["front_axis_as_fbx_preset"]["passed"])
        self.assertTrue(report["checks"]["skeletal_bounds_equal_um_fbx_v1_prediction"]["passed"])
        self.assertNotIn("front_axis", report["comparison_with_proposals_not_budgets"])
        cfg = self.manifest()["config"]["ue"]
        self.assertEqual((cfg["import_materials"], cfg["import_textures"]), (False, False),
                         "config.ue records the flags really used by the candidate path")
        first = tp.snapshot(self.run_dir)
        calls = len(self.ue_calls())
        out = self.ue()
        self.assertIn("skipped", out.stdout)
        self.assertNotIn("import_file", self.ue_calls()[calls:])
        self.assertEqual(tp.snapshot(self.run_dir), first)
        self.ue("--force")
        self.assertEqual(sorted(self.ue_assets()), self.expected_assets(), "forced re-import must not duplicate")
        report2 = json.loads((self.run_dir / "reports/ue-import-report.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(report2["previous_assets_deleted"]), self.expected_assets())
        self.assertEqual(report2["checks"], report["checks"])
        state = json.loads(self.ue_state.read_text(encoding="utf-8"))
        sk = state["assets"][self.FOLDER + "/Meshes/SK_Test_Candidate"]
        self.assertEqual([s["name"] for s in sk["sockets"]], ["Weapon", "Head"], "sockets must not duplicate")

    def test_import_over_existing_name_is_refused_by_ue_so_stage_deletes_first(self):
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.ue()
        # Simulate a pipeline that would skip deletion: UE refuses, it does not create *_1.
        proc = self.mcp("ue-import", "--run-dir", str(self.run_dir), "--force", expect=0)
        self.assertIn("executed", proc.stdout)
        self.assertFalse(any(a.endswith("_1") for a in self.ue_assets()))
        # the fake mirrors the real editor: a plain second import_file of the same name fails
        direct = self.mcp_raw_import()
        self.assertIn("already exists", direct)

    def mcp_raw_import(self):
        import subprocess
        args = {"folder_path": self.FOLDER + "/Meshes", "asset_name": "SK_Test_Candidate",
                "source_file": str(self.run_dir / "export/SK_Test_Candidate.fbx")}
        proc = subprocess.run([sys.executable, str(FAKE_UE), "call", tp.UE_TOOLSETS["skeletal"], "import_file",
                               json.dumps(args)], capture_output=True, text=True, env=self.env)
        return proc.stdout

    def test_profile_without_fbx_preset_is_refused(self):
        profile_path = self.repo / self.profile_rel
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        del data["fbx_preset"]
        profile_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        self.init_candidate()
        proc = self.cli("run", "--run-dir", str(self.run_dir), expect=1)
        self.assertIn("fbx_preset_is_um_fbx_v1", proc.stderr)
        preflight = json.loads((self.run_dir / "reports/preflight.json").read_text(encoding="utf-8"))
        self.assertIn("no fbx_preset", preflight["checks"]["fbx_preset_is_um_fbx_v1"]["error"])
        self.assertEqual(self.blender_calls(), [])

    def test_preset_change_rebuilds_candidate(self):
        self.init_candidate()
        self.cli("run", "--run-dir", str(self.run_dir))
        preset = json.loads(self.preset.read_text(encoding="utf-8"))
        preset["status"] = "wording only"
        self.preset.write_text(json.dumps(preset, indent=2), encoding="utf-8")
        out = self.cli("run", "--run-dir", str(self.run_dir))
        self.assertIn("build     executed", out.stdout)
        self.assertIn("atlas     skipped", out.stdout)

    def test_reference_front_is_mapped_onto_candidate_front(self):
        """Production-like reference (front +Y, unrotated) vs the UM_FBX_v1 candidate (front +X)."""
        ref = "/Game/ReferenceTest/SK_Ref"
        profile_path = self.repo / self.profile_rel
        data = json.loads(profile_path.read_text(encoding="utf-8"))
        data["ue"]["reference_skeletal_for_axes"] = {"asset": ref, "ue_front": "+Y"}
        profile_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        build = json.loads((self.run_dir / "reports/build-report.json").read_text(encoding="utf-8"))
        b = build["expected_ue_bounds_uu_at_import_scale_1"]["skeletal_blender_axes"]
        lo, hi = [b["min"][0], -b["max"][1], b["min"][2]], [b["max"][0], -b["min"][1], b["max"][2]]
        self.ue_state.write_text(json.dumps({"assets": {ref: {
            "class": "SkeletalMesh", "slots": ["M"], "bones": [], "parents": {}, "sockets": [],
            "bounds": {"min": dict(zip("xyz", lo)), "max": dict(zip("xyz", hi))}}}}), encoding="utf-8")
        self.ue()
        report = json.loads((self.run_dir / "reports/ue-import-report.json").read_text(encoding="utf-8"))
        check = report["checks"]["reference_front_lands_on_candidate_front"]
        self.assertTrue(check["passed"], check)
        self.assertEqual(report["measured"]["reference"]["reference_front_lands_on"], ["+X"])
        self.assertIn(ref, self.ue_assets(), "the read-only reference must stay")

    def test_foreign_asset_blocks_candidate_import(self):
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        self.ue_state.write_text(json.dumps({"assets": {self.FOLDER + "/Meshes/Other": {"class": "StaticMesh"}}}),
                                 encoding="utf-8")
        proc = self.ue(expect=tp.EXIT_CONFLICT)
        self.assertIn("did not create", proc.stderr)
        self.assertNotIn("delete", self.ue_calls())

    def test_ue_contract_failure_then_clean_retry(self):
        self.init_candidate()
        self.mcp("run", "--run-dir", str(self.run_dir))
        proc = self.ue(expect=1, env=dict(self.env, FAKE_UE_TRIS_DELTA="3"))
        self.assertIn("base_triangles", proc.stderr)
        self.ue()
        self.assertEqual(sorted(self.ue_assets()), self.expected_assets())


if __name__ == "__main__":
    unittest.main()
