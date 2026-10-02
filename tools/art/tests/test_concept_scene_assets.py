"""ENV-MAPS P8.1 (track A) concept scene: FBX contracts (UM_FBX_v1 via k_blender), manifest and sha256.

  python -m pytest tools/art/tests/test_concept_scene_assets.py -q

Pure Python on the committed reports / manifest (+ the out-of-git textures when they are present):
* every exported FBX: sha256 of the file == build report == manifest, <= 15 MB, one mesh with the expected
  triangles, the slot names, UV0 'UVMap', the read-back bounds in the UE frame == the build bounds, every UM_FBX_v1
  conformance row true, the atlas without overlap (texel centres at 1k);
* the manifest: schema / fields of the interface (meshes, projected, layout), UE names /Game/EnvMaps/Sarpedon/Scene/,
  textures in the gitignored scraped-data/derived/concept-scene/sarpedon/ with their sha256, the projected plate
  power-of-two over the P7 PlateB rect, the looks named by the layout, params / generator hashes current;
* the ship (P9: procedural on the painted pixels, no Poly Haven hull): the C0 fit (visible silhouette IoU, rail /
  foot pixel residuals) and its three gun ports;
* P9 material route: the frame band / cascade meshes name track B's material-route MIs per slot, the manifest's
  "materials" carries the cascade's FallCard.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools/art/concept_scene"))

import cs_common as CS  # noqa: E402
import run_scene as RS  # noqa: E402

MAN = CS.load_json(CS.MANIFEST_PATH)


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


class FbxContracts(unittest.TestCase):
    def test_exports(self):
        seen = set()
        for key, (run, stem, slot, unwrap, sharp, smooth, atlas, ao) in RS.MESHES.items():
            rep = CS.load_json(CS.RUNS[run] / "reports" / "build-report.json")
            e = next(x for x in rep["exports"] if x["name"] == stem)
            fbx = REPO / e["fbx"]
            self.assertTrue(fbx.is_file(), stem)
            self.assertEqual(sha(fbx), e["sha256"], f"{stem}: FBX changed since the build report")
            self.assertLessEqual(fbx.stat().st_size, 15 * 1024 * 1024, stem)
            rb = e["readback"]
            self.assertEqual(rb["mesh_objects"], 1, stem)
            self.assertEqual(rb["triangles"], e["triangles"], stem)
            self.assertEqual(rb["material_slots"], RS.slots_of(slot), stem)
            self.assertEqual(rb["uv_layers"], ["UVMap"], stem)
            self.assertTrue(rb["ue_frame_matches_build"], stem)
            self.assertTrue(all(c["conforms"] for c in e["um_fbx_v1_conformance"]), stem)
            if atlas:
                self.assertLessEqual(e["uv0"]["overlapShare1k"], 1e-4, f"{stem}: overlapping UV atlas")
                self.assertGreaterEqual(e["uv0"]["min"][0], 0.0)
                self.assertLessEqual(e["uv0"]["max"][1], 1.0)
            budget = 40000 if key in ("Island", "Ship") else 12000
            self.assertLessEqual(e["triangles"], budget, stem)
            seen.add(stem)
        self.assertEqual(len(seen), len(RS.MESHES))


class Manifest(unittest.TestCase):
    def test_schema_and_interface(self):
        self.assertEqual(MAN["schema"], "unmatched.concept-scene/1")
        self.assertEqual(MAN["map"], "sarpedon")
        self.assertEqual(MAN["layout"], "unreal/Unmatched/Config/ArtBoards/EnvLayouts/sarpedon.scene.layout.json")
        names = [m["name"] for m in MAN["meshes"] + MAN["meshesExistingMaterial"]]
        self.assertEqual(sorted(names), sorted(RS.MESHES))
        self.assertTrue(all(m["textures"] for m in MAN["meshes"]), "baked meshes carry BC / N / ORM")
        for m in MAN["meshesExistingMaterial"]:
            self.assertEqual(m["textures"], {})
            self.assertTrue(m["slots"])
        for m in MAN["meshes"] + MAN["meshesExistingMaterial"]:
            self.assertRegex(m["ue"], r"^/Game/EnvMaps/Sarpedon/Scene/SM_Env_S_[A-Za-z]+$")
            for k in ("fbx", "tris", "castShadow", "lumenGI", "textures", "sha256"):
                self.assertIn(k, m, m["name"])
            fbx = REPO / m["fbx"]
            self.assertEqual(m["sha256"][m["fbx"]], sha(fbx), m["name"])
            if m["textures"]:
                self.assertEqual(sorted(m["textures"]), ["BC", "N", "ORM"])
                for k, rel in m["textures"].items():
                    self.assertTrue(rel.startswith("scraped-data/derived/concept-scene/sarpedon/T_Env_S_"), rel)
                    self.assertRegex(Path(rel).stem, rf"^T_Env_S_{m['name']}_{k}$")
                    self.assertIn(rel, m["sha256"])
                    self.assertRegex(m["sha256"][rel] or "", r"^[0-9a-f]{64}$", rel)
                self.assertEqual(m["mi"], f"/Game/EnvMaps/Sarpedon/Scene/MI_Env_S_{m['name']}")
        p = MAN["projected"]
        self.assertEqual(p["ue"], "/Game/EnvMaps/Sarpedon/Scene/T_Env_S_AlbedoC0")
        self.assertEqual(p["rectC0Px"], [-384.0, -216.0, 2688.0, 1512.0])
        w, h = p["size"]
        self.assertTrue(w & (w - 1) == 0 and h & (h - 1) == 0, "projected plate must be power of two")
        self.assertRegex(p["sha256"] or "", r"^[0-9a-f]{64}$")

    def test_out_of_git_textures(self):
        rels = [p for m in MAN["meshes"] for p in m["textures"].values()] + [MAN["projected"]["albedo"]]
        r = subprocess.run(["git", "check-ignore", *rels], cwd=str(REPO), capture_output=True, text=True)
        self.assertEqual(sorted(r.stdout.split()), sorted(rels), "concept-derived images must be gitignored (ENV-U3)")
        r = subprocess.run(["git", "ls-files", "scraped-data/derived/concept-scene"], cwd=str(REPO),
                           capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), "")

    def test_textures_match_when_present(self):
        present = 0
        for m in MAN["meshes"]:
            for rel in m["textures"].values():
                f = REPO / rel
                if f.is_file():
                    present += 1
                    self.assertEqual(sha(f), m["sha256"][rel], rel)
        a = REPO / MAN["projected"]["albedo"]
        if a.is_file():
            self.assertEqual(sha(a), MAN["projected"]["sha256"])
        if not present:
            self.skipTest("textures not baked in this checkout (out of git): run bake_albedo.py")

    def test_params_and_generator_current(self):
        self.assertEqual(MAN["params"]["sha256"], CS.text_sha256_lf(CS.PARAMS_PATH),
                         "scene-params changed since the bake: re-run run_scene.py")
        for rel, h in MAN["generator"].items():
            self.assertEqual(CS.text_sha256_lf(REPO / rel), h, f"{rel} changed since the bake")

    def test_looks_are_the_layout_materials(self):
        lay = CS.load_json(CS.SCENE_LAYOUT)
        used = {p["material"] for p in lay["props"]["add"] if "material" in p}
        # P8.3: the lanterns' lit3d glass (a child of the P7c lantern MI, ue_scene_material.mi_plan "lanternHead")
        used.discard("/Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_LanternHead")
        listed = {v["mi"] for v in MAN["looks"]}
        for v in MAN["looks"]:
            self.assertEqual(v["mi"], f"/Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_Proj_{v['name']}")
            self.assertEqual(len(v["vectors"]["FallbackTint"]), 4)
        self.assertTrue(used <= listed, used - listed)
        for mi in listed:
            self.assertRegex(mi, r"^/Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_Proj_[A-Za-z]+$")


class ShipBuild(unittest.TestCase):
    def test_c0_fit(self):
        rep = CS.load_json(CS.RUNS["ship"] / "reports" / "ship-build.json")
        fit = rep["c0Fit"]
        self.assertGreaterEqual(fit["iouC0"], 0.7, "visible C0 silhouette IoU vs the painted ship (P8: 0.65)")
        self.assertGreaterEqual(fit["targetCoveredC0"], 0.8)
        self.assertLessEqual(fit["railRmsPx"], 3.0, "the rail cap on the painted rail pixels")
        self.assertLessEqual(fit["footRmsPx"], 10.0)
        self.assertLessEqual(rep["info"]["triangles"], 40000)
        self.assertNotIn("source", CS.params()["ship"], "P9: no Poly Haven hull any more")

    def test_ports(self):
        rep = CS.load_json(CS.RUNS["ship"] / "reports" / "ship-build.json")
        ports = rep["info"]["ports"]
        self.assertEqual(sorted(p["cannon"] for p in ports), ["cannon-1", "cannon-2", "cannon-3"])
        cam = CS.cam0()
        for p in ports:
            q = cam.project(np.array([p["muzzle"]], float))[0][0]
            self.assertLess(float(np.hypot(*(q - np.array(p["muzzlePx"])))), 1.0, p["cannon"])
            self.assertGreater(p["protrusionUU"], 0.0)


class MaterialRoute(unittest.TestCase):
    def test_slots_and_materials(self):
        ex = {m["name"]: m for m in MAN["meshesExistingMaterial"]}
        ue = "/Game/EnvMaps/Sarpedon/Scene/MI_EnvScene_"
        self.assertEqual(ex["FrameBand"]["slots"], [ue + "FrameWood", ue + "FrameIron"])
        self.assertEqual(ex["Cascade"]["slots"], [ue + "FallsSheet"])
        self.assertEqual(ex["CascadeFoam"]["slots"], [ue + "FallsFoam"])
        rep = CS.load_json(CS.RUNS["props"] / "reports" / "cascade-build.json")
        card = MAN["materials"]["FallsSheet"]["vectors"]["FallCard"]
        self.assertEqual(card[:2], rep["info"]["fallCard"])
        self.assertEqual(card[3], 1.0, "lane K v convention: FallCard.w = 1")


if __name__ == "__main__":
    unittest.main()
