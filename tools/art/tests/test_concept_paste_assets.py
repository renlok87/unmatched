"""ENV-MAPS P7 (ENV-U15) concept paste, track A: registration file, Lanczos bake, proxies / detail meshes, the concept
env-layout overlays and the UE import pre-check.

CPU only, no UE / Blender. The out-of-git textures (scraped-data/derived/concept-paste, ENV-U3 / U7) and the plates are
only checked when present (their sha256 against the committed manifests); every other test runs on committed files or
synthetic images.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
CP = REPO / "tools" / "art" / "concept_paste"
sys.path.insert(0, str(CP))

import cp_bake as B  # noqa: E402
import cp_common as C  # noqa: E402
import cp_layout as LY  # noqa: E402
import cp_proxies as PX  # noqa: E402
import paste_proto as pp  # noqa: E402
import ue_import_concept_paste as UI  # noqa: E402

LAYOUTS = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "EnvLayouts"
PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
MAPS = ("sarpedon", "marmoreal")
# design.json 5_elements.keep_3D_animated (P7a stage contract, out of git): world positions of the 12 details
DESIGN_WORLD = {
    "lantern-bay": [-129.7, -397.7, 196.6], "lantern-left": [-565.9, -46.1, 154.3],
    "lantern-stern": [418.1, -427.3, 144.7], "lantern-rail": [737.0, -221.7, 140.8],
    "lantern-deck-n": [522.4, -157.4, 82.4], "lantern-deck-se": [622.9, 228.1, 104.0],
    "fire-fort": [-492.3, -427.3, -3.0], "fire-brazier": [-555.1, 194.3, 112.1],
    "cannon-1": [587.6, -333.2, 19.0], "cannon-2": [643.2, -214.1, 19.0], "cannon-3": [721.5, -34.7, 19.0],
    "banner-ship": [831.2, -133.3, 49.1]}


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git_show(path: str) -> bytes | None:
    try:
        return subprocess.run(["git", "show", f"HEAD:{path}"], cwd=REPO, capture_output=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


class RegistrationFile(unittest.TestCase):
    def test_schema_and_near_identity(self):
        reg = B.load_registration()
        self.assertEqual(reg["schema"], B.SCHEMA_REG)
        for key, tags in B.REG_TAGS.items():
            for tag in tags:
                e = reg["maps"][key][tag]
                H = np.asarray(e["H"], float)
                self.assertEqual(H.shape, (3, 3))
                # imagegen did not warp the map: corners of the C0 frame move by < 4 px, residual < 0.35 px RMS
                for x, y in ((0, 0), (1920, 0), (0, 1080), (1920, 1080), (960, 540)):
                    q = H @ np.array([x, y, 1.0])
                    self.assertLess(math.hypot(q[0] / q[2] - x, q[1] / q[2] - y), 4.0, (key, tag))
                self.assertLess(e["homographyResidualPx"]["rms"], 0.35, (key, tag))
                self.assertRegex(e["sha256"], r"^[0-9a-f]{64}$")

    def test_colour_plate_registration_matches_spec(self):
        for key in MAPS:
            spec = B.load_spec(key)
            e = B.colour_registration(key, spec)  # raises on a crop / plate mismatch
            self.assertEqual(Path(e["plate"]).name, Path(spec["plates"]["colour"]["file"]).name)


class LanczosSampler(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(7)
        self.img = rng.random((40, 52, 3)).astype(np.float32)
        ys, xs = np.mgrid[0:40, 0:52] + 0.5
        self.xs, self.ys = xs, ys

    def test_identity_at_pixel_centres(self):
        out = B.lanczos_sample(self.img, self.xs, self.ys)
        self.assertLess(float(np.abs(out - self.img).max()), 1e-6)

    def test_constant_stays_constant_when_minifying(self):
        c = np.full((40, 52, 3), 0.37, np.float32)
        out = B.lanczos_sample(c, self.xs * 0.6 + 2.2, self.ys * 1.4 - 3.0, 1.6, 1.3)
        self.assertLess(float(np.abs(out - 0.37).max()), 1e-5)

    def test_linear_ramp_is_reproduced_off_grid(self):
        ramp = np.tile(np.linspace(0, 1, 52, dtype=np.float32), (40, 1))[..., None].repeat(3, 2)
        out = B.lanczos_sample(ramp, self.xs[:, 6:46] + 0.37, self.ys[:, 6:46])
        # Lanczos-3 is not exactly linear-preserving off the half-pixel symmetry; it stays well under 1/2 LSB of 8 bit
        self.assertLess(float(np.abs(out - (ramp[:, 6:46] + 0.37 / 51)).max()), 1e-3)

    def test_edge_clamp_and_range(self):
        out = B.lanczos_sample(self.img, self.xs - 100, self.ys)
        self.assertTrue(np.all(out >= 0) and np.all(out <= 1))
        self.assertLess(float(np.abs(out[:, 0] - self.img[:, 0]).max()), 1e-5)

    def test_reflect(self):
        np.testing.assert_allclose(B.reflect(np.array([-10.0, 5.0, 1925.0, 3850.0]), 1920.0),
                                   [10.0, 5.0, 1915.0, 10.0])


class BakeGeometry(unittest.TestCase):
    def test_texel_grid_covers_the_rect(self):
        FX, FY = B.texel_c0((-384, -216, 2304, 1296), (8, 4))
        self.assertAlmostEqual(float(FX[0, 0]), -384 + 2688 / 16)
        self.assertAlmostEqual(float(FY[-1, 0]), 1296 - 1512 / 8)

    def test_map_centre_is_under_the_frame_and_the_surround_is_not(self):
        spec = B.load_spec("sarpedon")
        cam = C.concept_cam()
        c = cam.project(np.array([[0.0, 0.0, -3.0], [0.0, -C.FRAME_HY - 30, -3.0]]))[0]
        SX, SY, under, moved = B.sample_points(spec, cam, c[:, 0:1], c[:, 1:2])
        self.assertTrue(bool(under[0, 0]))
        self.assertFalse(bool(under[1, 0]))
        self.assertTrue(bool(moved[1, 0]))  # inside the painted-frame band: rubber-stretched outwards
        q = cam.project(np.array([[0.0, -C.FRAME_HY - 30, -3.0]]))[0][0]
        self.assertLess(float(SY[1, 0]), q[1])  # sampled further out (towards the far side = up in C0)

    def test_synthetic_plate_bake(self):
        """A constant plate through the real spec geometry: the colour stays constant, the alpha is 0 under the frame
        and outside the island matte, 1 on the island."""
        spec = json.loads(json.dumps(B.load_spec("sarpedon")))
        tex = {"kind": "paste", "size": [384, 216], "rectC0": [-384, -216, 2304, 1296]}
        sp = spec["plates"]["colour"]
        plate = np.full((sp["size"][1], sp["size"][0], 3), 0.25, np.float32)
        img, st = B.bake_texture("sarpedon", spec, "PlateB", tex, {"colour": plate}, np.eye(3), log=lambda *_: None)
        self.assertEqual(img.shape, (216, 384, 4))
        self.assertLess(float(np.abs(img[..., :3] - 0.25).max()), 1e-5)
        FX, FY = B.texel_c0(tex["rectC0"], tex["size"])
        cam = C.concept_cam()
        m = cam.project(np.array([[0.0, 0.0, 0.0]]))[0][0]
        j = int(np.argmin(np.abs(FY[:, 0] - m[1])))
        i = int(np.argmin(np.abs(FX[0] - m[0])))
        self.assertEqual(float(img[j, i, 3]), 0.0)  # map centre: under the frame
        sky = (FX < 0) & (FY < 0)  # top-left corner: open sky / sea (outside the island matte)
        self.assertLess(float(img[..., 3][sky].max()), 0.5)
        fort = cam.project(np.array([[-500.0, -430.0, -3.0]]))[0][0]  # the fort / campfire area: island
        jj = int(np.argmin(np.abs(FY[:, 0] - fort[1])))
        ii = int(np.argmin(np.abs(FX[0] - fort[0])))
        self.assertGreater(float(img[jj, ii, 3]), 0.99)
        self.assertGreater(st["bandResampledTexels"], 0)


class Manifests(unittest.TestCase):
    def test_manifest_matches_spec_and_code(self):
        for key in MAPS:
            spec = B.load_spec(key)
            man = load(B.derived_path(key))
            self.assertEqual(man["schema"], B.SCHEMA_DERIVED)
            self.assertEqual(set(man["outputs"]), set(spec["bake"]["textures"]))
            self.assertEqual(man["paramsSha256"], B.canon_sha(B.bake_params(spec)), "bake params changed: re-bake")
            self.assertEqual(man["generator"], B.generator_hashes(), "bake code changed: re-bake")
            self.assertEqual(man["materialContract"], B.material_contract(spec))
            reg = B.colour_registration(key, spec)
            self.assertEqual(man["inputs"]["colour"]["sha256"], reg["sha256"])
            for name, o in man["outputs"].items():
                tex = spec["bake"]["textures"][name]
                self.assertEqual(o["size"], tex["size"])
                self.assertEqual(o["rectC0"], tex["rectC0"])
                self.assertEqual(o["file"], B.texture_file(spec, name))
                self.assertEqual(o["channels"], "RGBA" if tex["kind"] == "paste" else "RGB")
            self.assertEqual(man["materialContract"]["homography"], [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]])

    def test_out_of_git_outputs_when_present(self):
        for key in MAPS:
            man = load(B.derived_path(key))
            od = B.OUT_DEFAULT / key
            if not od.is_dir():
                self.skipTest(f"{od} absent (out of git)")
            res = B.check(key, B.OUT_DEFAULT, verbose=False)
            self.assertTrue(res["ok"], res["errors"])
            self.assertEqual(set(res["outputs"]), set(man["outputs"]))

    def test_nothing_derived_from_the_concepts_in_git(self):
        out = subprocess.run(["git", "ls-files", "--others", "--cached", "--exclude-standard", "scraped-data",
                              "tools/art/concept_paste", "art/pipeline-candidates/ASSET-ENV-CONCEPT-PASTE-001"],
                             cwd=REPO, capture_output=True, text=True).stdout.split()
        images = [p for p in out if p.lower().endswith((".png", ".jpg", ".jpeg", ".npy", ".npz", ".hdr", ".exr"))]
        self.assertEqual(images, [], "concept-derived images must stay out of git (ENV-U3 / U7)")


class Proxies(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = PX.load_params()
        cls.report = load(PX.RUN / "reports" / "build-report.json")
        cls.exports = {e["name"]: e for e in cls.report["exports"]}

    def test_report_is_current(self):
        self.assertTrue(self.report["checks_passed"])
        self.assertEqual(self.report["params"]["sha256"], C.sha256(PX.PARAMS))
        lf = lambda p: B.text_sha256_lf(p)  # noqa: E731
        self.assertEqual(self.report["script_sha256_lf"]["tools/art/concept_paste/blender_cp_assets.py"],
                         lf(CP / "blender_cp_assets.py"))
        self.assertEqual(self.report["script_sha256_lf"]["tools/art/concept_paste/cp_proxies.py"], lf(CP / "cp_proxies.py"))
        self.assertTrue(PX.check(verbose=False)["ok"])

    def test_sheets(self):
        for key in MAPS:
            e = self.exports[f"SM_{C.MAPS[key]['name']}_ConceptSheet"]
            self.assertLessEqual(e["triangles"], self.params["proxies"]["maxSheetTriangles"])
            self.assertEqual(e["facingC0Share"], 1.0)
            self.assertLessEqual(e["surfaceErrorUU"]["max"], 1.0)
            self.assertEqual(e["roundtrip"]["mesh_objects"], 1)
            # the sheet surrounds the frame: its bounds reach past the tray on every side, never under the sea level
            b = e["boundsUeLocalUU"]
            self.assertLess(b["min"][0], -C.FRAME_HX - 200)
            self.assertGreater(b["max"][0], C.FRAME_HX + 200)
            self.assertGreaterEqual(b["min"][2], pp.load_spec(key)["geometry"]["seaZ"] - 1e-3)

    def test_sheet_grid_numpy_side(self):
        """The numpy grid (prepare) faces C0 everywhere and drops the cells under the frame."""
        sh = PX.sheet_data("sarpedon")
        spec = sh["spec"]
        tex = spec["bake"]["textures"]
        arr = PX.mesh_arrays(sh, tex["PlateA"]["rectC0"], tex["PlateB"]["rectC0"])
        self.assertEqual(arr["backFacing"], 0)
        self.assertEqual(arr["cellsKept"], self.report["numpy"]["sarpedon"]["sheet"]["cellsKept"])
        c = C.concept_cam().project(np.array([[0.0, 0.0, -3.0]]))[0][0]
        i = int((c[0] - PX.EXT[0]) // sh["step"])
        j = int((c[1] - PX.EXT[1]) // sh["step"])
        self.assertFalse(bool(sh["keep"][j, i]))  # the map field is not part of the sheet

    def test_lantern_head(self):
        e = self.exports["SM_EnvCP_LanternHead"]
        b = e["boundsUeLocalUU"]
        self.assertLess(b["size"][2], 45.0)   # no post (the post is 95 uu)
        self.assertLess(b["size"][1], 25.0)   # no arm (the arm spans ~22 uu across Y)
        self.assertAlmostEqual(b["min"][2], 0.0, places=2)
        g = e["glowOffsetUU"]
        self.assertTrue(b["min"][2] < g[2] < b["max"][2])
        self.assertTrue(all(e["checks"].values()))

    def test_banner_cloth(self):
        # P7c: a procedural cloth hanging along the C0 screen-down (hangLocal), the rail on top
        e = self.exports["SM_EnvCP_BannerCloth"]
        self.assertAlmostEqual(e["clothLengthUU"] / e["clothWidthUU"], self.params["bannerCloth"]["clothAspect"], places=2)
        self.assertTrue(e["source"].get("procedural"))
        self.assertAlmostEqual(e["boundsUeLocalUU"]["max"][2], e["crossbarTopUU"], delta=1.0)
        self.assertEqual(e["hangLocal"], self.params["bannerCloth"]["hangLocal"])
        # the rail is the highest part; the cloth spans hangLocal.z x its length below it
        self.assertAlmostEqual(e["crossbarTopUU"] - e["clothTopUU"], 2 * self.params["bannerCloth"]["rodRadiusUU"]
                               + self.params["bannerCloth"]["rodClearUU"], delta=0.01)
        self.assertGreater(e["clothTopUU"], -e["hangLocal"][2] * e["clothLengthUU"] * 0.8)
        self.assertEqual(e["roundtrip"]["material_slots"], ["MI_EnvCP_Banner"])
        self.assertTrue(all(e["checks"].values()))

    def test_banner_hang_is_the_c0_screen_down(self):
        self.assertEqual(LY.banner_hang_local(pp.load_spec("sarpedon")), self.params["bannerCloth"]["hangLocal"])

    def test_kit_cannon_measured(self):
        m = self.report["kitMeasurements"]["SM_Env_Cannon"]
        self.assertTrue(m["sha256Ok"])
        self.assertTrue(15.0 < m["barrelAxisZUU"] < 26.0)


class Overlays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = load(LY.BUILD_REPORT)

    def test_committed_overlays_are_fresh_and_valid(self):
        for key in MAPS:
            spec = pp.load_spec(key)
            base = load(LAYOUTS / f"{key}.layout.json")
            overlay, _ = LY.build(key, base, spec, self.report)
            path = LAYOUTS / f"{key}.{spec['layout']['variant']}.layout.json"
            self.assertEqual(path.read_text(encoding="utf-8"), LY.text_of(overlay), f"{path.name}: run cp_layout.py")
            self.assertEqual(LY.validate(key, base, overlay), [])
            for fixed in ("lights", "ground", "tray", "apron"):
                self.assertNotIn(fixed, overlay)  # MergeOverlay refuses them

    def test_base_layouts_untouched(self):
        for key in MAPS:
            rel = f"unreal/Unmatched/Config/ArtBoards/EnvLayouts/{key}.layout.json"
            head = git_show(rel)
            if head is None:
                self.skipTest("git unavailable")
            self.assertEqual((REPO / rel).read_bytes().replace(b"\r\n", b"\n"), head.replace(b"\r\n", b"\n"))

    def test_sarpedon_details_land_on_the_design_points(self):
        overlay = load(LAYOUTS / "sarpedon.concept.layout.json")
        merged = LY.merge(load(LAYOUTS / "sarpedon.layout.json"), overlay)
        props = {p["id"]: p for p in merged["props"]}
        fx = {f["id"]: f for f in merged["fx"]}
        self.assertEqual(set(props), {k for k in DESIGN_WORLD if not k.startswith("fire-")})
        lant = LY.export_of(self.report, "SM_EnvCP_LanternHead")
        cannon = self.report["kitMeasurements"]["SM_Env_Cannon"]
        ban = LY.export_of(self.report, "SM_EnvCP_BannerCloth")
        for pid, p in props.items():
            s, yaw, loc = p["scale"], p["yawDeg"], np.array(p["loc"])
            if pid.startswith("lantern"):
                pt = loc + LY.rot_yaw(np.array(lant["glowOffsetUU"]) * s, yaw)
                f = fx["flame-" + pid]
                self.assertEqual(f["anchor"], pid)
                np.testing.assert_allclose(loc + LY.rot_yaw(f["loc"], yaw), DESIGN_WORLD[pid], atol=0.05)
            elif pid.startswith("cannon"):
                pt = loc + LY.rot_yaw([0.0, cannon["barrelAxisYUU"] * s, cannon["barrelAxisZUU"] * s], yaw)
            else:
                # P7c: the rail moved towardC0UU along the C0 ray of the design point (same C0 pixel, scaled)
                rail = np.array([ban["crossbarXUU"], ban["crossbarYUU"], ban["crossbarTopUU"]])
                pt = loc + LY.rot_yaw(rail * s, yaw)
                cam0 = C.concept_cam()
                tow = json.loads((HERE.parent / "concept_paste" / "sarpedon.paste.json").read_text(
                    encoding="utf-8"))["layout"]["banner"]["towardC0UU"]
                ray = np.array(DESIGN_WORLD[pid]) - cam0.pos
                np.testing.assert_allclose(pt, np.array(DESIGN_WORLD[pid]) - ray / np.linalg.norm(ray) * tow,
                                           atol=0.05, err_msg=pid)
                got, _ = cam0.project(pt)
                want, _ = cam0.project(np.array(DESIGN_WORLD[pid]))
                self.assertLess(float(np.hypot(*(got - want))), 0.05, pid)
                continue
            np.testing.assert_allclose(pt, DESIGN_WORLD[pid], atol=0.05, err_msg=pid)
            self.assertFalse(p["castShadow"])
        for fid in ("fire-fort", "fire-brazier"):
            # on the C0 ray through the painted fire (P7 tune: towardC0UU may move the origin along that ray in front
            # of its host flat; fort 0 = the design XY)
            cam0 = C.concept_cam()
            fire = json.loads((HERE.parent / "concept_paste" / "sarpedon.paste.json").read_text(encoding="utf-8"))
            dz = fire["layout"]["fire"]["campfire" if fid == "fire-fort" else "brazier"]["dz"]
            got, _ = cam0.project(np.array(fx[fid]["loc"], float))
            want, _ = cam0.project(np.array(DESIGN_WORLD[fid], float) + np.array([0.0, 0.0, dz]))
            self.assertLess(float(np.hypot(*(got - want))), 0.05, fid)
        self.assertLess(math.dist(fx["fire-fort"]["loc"][:2], DESIGN_WORLD["fire-fort"][:2]), 0.05)
        # every painted prop of the base layout is gone; the fireflies moved over the canopy, the beach ones removed
        self.assertNotIn("fireflies-beach", fx)
        self.assertEqual(fx["fireflies-forest-n"]["loc"], [-707.6, -118.9, 150.0])
        self.assertTrue(all(p["mesh"].startswith("/Game/EnvKit/") for p in merged["props"]))
        # P7c: the dark-iron copy of the kit cannon
        self.assertTrue(all(props[c]["mesh"] == "/Game/EnvKit/ConceptPaste/SM_EnvCP_Cannon"
                            for c in ("cannon-1", "cannon-2", "cannon-3")))

    def test_banner_faces_the_camera_side(self):
        p = next(x for x in load(LAYOUTS / "sarpedon.concept.layout.json")["props"]["add"] if x["id"] == "banner-ship")
        n = LY.rot_yaw([1.0, 0.0, 0.0], p["yawDeg"])
        cam = C.concept_cam().pos
        self.assertGreater(float(np.dot(n, cam - np.array(DESIGN_WORLD["banner-ship"]))), 0)

    def test_marmoreal_comparison_overlay(self):
        base = load(LAYOUTS / "marmoreal.layout.json")
        overlay = load(LAYOUTS / "marmoreal.concept.layout.json")
        merged = LY.merge(base, overlay)
        self.assertEqual(merged["props"], [])
        self.assertEqual({f["id"] for f in merged["fx"]}, {"fireflies-garden-w", "fireflies-garden-e"})
        self.assertEqual(overlay["conceptPaste"]["lights"]["mode"], "base")

    def test_light_reference_matches_the_profile_count(self):
        overlay = load(LAYOUTS / "sarpedon.concept.layout.json")
        ref = overlay["conceptPaste"]["lights"]["reference"]
        self.assertLessEqual(len(ref) + LY.PROFILE_POINTS, LY.MAX_POINT_LIGHTS)
        boards = load(PROFILES).get("boards", [])
        boards = boards.values() if isinstance(boards, dict) else boards
        block = next((b["conceptPaste"] for b in boards if isinstance(b, dict) and isinstance(b.get("conceptPaste"), dict)
                      and "sarpedon" in b["conceptPaste"].get("spec", "")), None)
        if not (block and block.get("lights")):
            self.skipTest("no Sarpedon conceptPaste lights in the profiles yet (track B)")
        # the profile block (track B) carries the lights: same ids, XY at the reference points (Z is the block's choice)
        got = {lt["id"]: lt["loc"] for lt in block["lights"]}
        self.assertEqual(set(got), {lt["id"] for lt in ref})
        for lt in ref:
            self.assertLess(math.dist(got[lt["id"]][:2], lt["loc"][:2]), 1.0, lt["id"])


class ImportPreCheck(unittest.TestCase):
    def test_asset_names(self):
        self.assertEqual(UI.texture_asset("sarpedon", "T_Sarpedon_ConceptPlateA.png"),
                         "/Game/EnvMaps/Sarpedon/ConceptPaste/T_Sarpedon_ConceptPlateA")
        self.assertEqual(UI.mesh_asset("SM_Sarpedon_ConceptSheet"), "/Game/EnvMaps/Sarpedon/ConceptPaste/SM_Sarpedon_ConceptSheet")
        self.assertEqual(UI.mesh_asset("SM_EnvCP_LanternHead"), "/Game/EnvKit/ConceptPaste/SM_EnvCP_LanternHead")
        layout_meshes = {p["mesh"] for p in load(LAYOUTS / "sarpedon.concept.layout.json")["props"]["add"]}
        for name in UI.DETAILS:
            self.assertIn(UI.mesh_asset(name), layout_meshes)

    def test_profile_asset_paths_when_the_block_exists(self):
        """Track B's profile block names the same assets (sheet mesh, plates, manifest)."""
        text = PROFILES.read_text(encoding="utf-8")
        if '"conceptPaste"' not in text:
            self.skipTest("no conceptPaste block in the profiles yet")
        for key in MAPS:
            man = load(B.derived_path(key))
            name = C.MAPS[key]["name"]
            for prof_key, asset in man["materialContract"]["assets"].items():
                if f'"{prof_key}": "' in text and asset.split("/")[-1].startswith(f"T_{name}_"):
                    if f'"{prof_key}": "/Game/EnvMaps/{name}/' in text:
                        self.assertIn(asset, text, f"{key}.{prof_key}")
            self.assertIn(f"/Game/EnvMaps/{name}/ConceptPaste/SM_{name}_ConceptSheet", text)
            self.assertIn(f"tools/art/concept_paste/manifest.{key}.json", text)

    def test_check_mode(self):
        p = UI.plan(list(MAPS), UI.derived_root(None))
        for name, item in p["meshes"].items():
            self.assertTrue(item["verified"], (name, item.get("error")))
        if not (B.OUT_DEFAULT / "sarpedon").is_dir():
            self.skipTest("textures out of git absent")
        self.assertTrue(p["ok"])


if __name__ == "__main__":
    unittest.main()
