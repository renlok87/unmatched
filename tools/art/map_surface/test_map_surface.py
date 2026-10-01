"""Unit tests for tools/art/map_surface (pure functions, synthetic data; no map images needed).

  python -B -m unittest tools/art/map_surface/test_map_surface.py -v
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import k1_mock  # noqa: E402
import png16  # noqa: E402
import raster  # noqa: E402
import vector_layer as vl  # noqa: E402


class Png16(unittest.TestCase):
    def test_roundtrip_rgba16_and_gray16(self):
        rng = np.random.default_rng(0)
        a = rng.integers(0, 65536, size=(37, 53, 4), dtype=np.uint16)
        g = rng.integers(0, 65536, size=(19, 7), dtype=np.uint16)
        self.assertTrue(np.array_equal(png16.decode_png(png16.encode_png(a)), a))
        self.assertTrue(np.array_equal(png16.decode_png(png16.encode_png(g)), g))


class Raster(unittest.TestCase):
    def setUp(self):
        self.g = raster.Grid(256, 128, 64, clamp_px=16.0)

    def test_texel_centres(self):
        self.assertAlmostEqual(self.g.xs[0], 0.5 * 128 / 256)
        self.assertAlmostEqual(self.g.ys[-1], (255.5) * 64 / 256)

    def test_disc_sdf_sign_and_value(self):
        R = raster.discs_sdf(self.g, [(64.0, 32.0)], 10.0)
        i, j = int(32 / 64 * 256), int(64 / 128 * 256)
        x, y = self.g.xs[j], self.g.ys[i]
        self.assertAlmostEqual(float(R[i, j]), math.hypot(x - 64, y - 32) - 10.0, places=4)
        self.assertLess(float(R[i, j]), 0)
        self.assertEqual(float(R[0, 0]), 16.0)  # clamped far away

    def test_arc_distance_matches_polyline(self):
        arc = (64.0, 64.0, 30.0, math.radians(200), math.radians(140))
        B = raster.arcs_dist(self.g, [arc], self.g.full(16.0))
        angs = arc[3] + arc[4] * np.linspace(0, 1, 2000)
        pts = np.c_[arc[0] + arc[2] * np.cos(angs), arc[1] + arc[2] * np.sin(angs)]
        segs = list(zip(map(tuple, pts[:-1]), map(tuple, pts[1:])))
        S = raster.segments_dist(self.g, segs)
        self.assertLess(float(np.abs(B - S).max()), 0.01)

    def test_id_map(self):
        ids = raster.id_map(self.g, [(20.0, 20.0), (80.0, 40.0)], 8.0)
        self.assertEqual(int(ids[int(20 / 64 * 256), int(20 / 128 * 256)]), 1)
        self.assertEqual(int(ids[int(40 / 64 * 256), int(80 / 128 * 256)]), 2)
        self.assertEqual(int(ids[0, 0]), 0)


class Camera(unittest.TestCase):
    def test_s08_fit_distance(self):
        # state.md 2.5: Cobble 5x6 -> 1931 uu, whole map at 2/3 uu per px (891x577) -> ~1872 uu
        self.assertAlmostEqual(k1_mock.s08_fit_distance(250.0, 300.0), 1931.0, delta=1.0)
        self.assertAlmostEqual(k1_mock.s08_fit_distance(891.333 / 2, 577.333 / 2), 1872.0, delta=1.0)

    def test_overview_distance_env_u9(self):
        # ENV-U9: the two map-image profiles carry k1DistanceMul 1.25 -> K1 2340 uu; Cobble keeps its fit (1931)
        self.assertEqual(k1_mock.k1_distance_mul("c121b47f8d6eb28daccb76d05"), 1.25)  # Marmoreal
        self.assertEqual(k1_mock.k1_distance_mul("c7fa64a26c29a0835f2383e63"), 1.25)  # Sarpedon
        self.assertEqual(k1_mock.k1_distance_mul("cmuhgs4b2001mwik4f2b2xtf8"), 1.0)   # Cobble City 5x6
        with self.assertRaises(ValueError):
            k1_mock.k1_distance_mul("no-such-board")
        self.assertAlmostEqual(k1_mock.s08_overview_distance(891.333 / 2, 577.333 / 2, 1.25), 2340.2, delta=0.5)
        self.assertEqual(k1_mock.s08_overview_distance(250.0, 300.0), k1_mock.s08_fit_distance(250.0, 300.0))

    def test_projection_centre_and_orientation(self):
        cam = k1_mock.Camera(1872.0, 1920, 1080)
        c = cam.project([[0.0, 0.0, 0.0]])[0]
        self.assertAlmostEqual(c[0], 960.0, places=6)
        self.assertAlmostEqual(c[1], 540.0, places=6)
        east = cam.project([[100.0, 0.0, 0.0]])[0]
        north = cam.project([[0.0, -100.0, 0.0]])[0]
        self.assertGreater(east[0], c[0])  # +X is screen right
        self.assertLess(north[1], c[1])    # -Y (image top) is screen up / far


class Fits(unittest.TestCase):
    def test_circle_fit(self):
        a = np.linspace(0.3, 1.2, 50)
        pts = np.c_[10 + 200 * np.cos(a), -5 + 200 * np.sin(a)]
        cx, cy, r = vl._circle_fit(pts)
        self.assertAlmostEqual(cx, 10, places=5)
        self.assertAlmostEqual(cy, -5, places=5)
        self.assertAlmostEqual(r, 200, places=5)

    def _short_gap(self):
        # two rings 140 px apart (gap outside r 65: 10 px), a 7 px stroke 5 px beside the chord
        dk = np.zeros((100, 220))
        ys = np.arange(100) + 0.5
        dk[(ys >= 51.5) & (ys <= 58.5), :] = 1.0
        return dk, np.array([40.0, 50.0]), np.array([180.0, 50.0])

    def test_chord_samples_find_a_stroke_beside_the_chord(self):
        dk, A, B = self._short_gap()
        Q, peak = vl._chord_centreline_samples(dk, A, B)
        self.assertEqual(len(Q), 21)  # r 65 .. 75 every 0.5 px
        self.assertLess(float(np.abs(Q[:, 1] - 55.0).max()), 0.05)
        self.assertTrue(np.all(Q[:, 0] >= A[0] + 65 - 1e-9) and np.all(Q[:, 0] <= B[0] - 65 + 1e-9))

    def test_stroke_offset_check(self):
        dk, A, B = self._short_gap()
        on = np.array([[102.0, 55.0], [118.0, 55.0]])
        self.assertLess(abs(vl._stroke_offset(dk, on)), 0.05)
        self.assertAlmostEqual(vl._stroke_offset(dk, on - [0.0, 1.3]), 1.3, delta=0.05)
        self.assertAlmostEqual(vl._stroke_offset(dk, on - [0.0, 5.0]), 5.0, delta=0.05)
        self.assertIsNone(vl._stroke_offset(np.zeros_like(dk), on))


class CommittedVectorLayers(unittest.TestCase):
    def test_required_arcs_and_counts(self):
        want = {"marmoreal": ({"M06-M12", "M20-M27", "M21-M25", "M23-M26"}, 31, 42),
                "sarpedon": ({"S11-S21", "S20-S21", "S21-S31", "S30-S31"}, 38, 61)}
        for key, (arcs, n_sp, n_e) in want.items():
            p = HERE / f"{key}.vector-layer.json"
            if not p.exists():
                self.skipTest(f"{p.name} not built")
            v = json.loads(p.read_text(encoding="utf-8"))
            self.assertEqual(len(v["spaces"]), n_sp)
            self.assertEqual(len(v["connections"]), n_e)
            self.assertTrue(arcs <= set(v["connection_summary"]["arcs"]), key)
            self.assertEqual(sorted(d["start"] for d in v["start_diamonds"]), [1, 2, 3, 4])
            for c in v["connections"].values():
                self.assertGreaterEqual(len(c["polyline_px"]), 2)

    def test_polylines_sit_on_the_painted_stroke(self):
        for key in ("marmoreal", "sarpedon"):
            p = HERE / f"{key}.vector-layer.json"
            if not p.exists():
                self.skipTest(f"{p.name} not built")
            v = json.loads(p.read_text(encoding="utf-8"))
            limit = v["params"]["vector_layer"]["max_stroke_offset_px"]
            self.assertLessEqual(limit, 0.5)
            for e, c in v["connections"].items():
                if c["method"] == "geodesic-fit":
                    self.assertLessEqual(abs(c["stroke_offset_px"]), limit, f"{key} {e}")
        s = json.loads((HERE / "sarpedon.vector-layer.json").read_text(encoding="utf-8"))["connections"]["S09-S10"]
        self.assertEqual(s["centreline_source"], "chord-profile")


class CommittedManifests(unittest.TestCase):
    """The manifests must verify on any checkout: LF-normalised input hashes, LF vector layers,
    no machine-local output paths."""

    def manifests(self):
        for key in ("marmoreal", "sarpedon"):
            p = HERE / f"manifest.{key}.json"
            if not p.exists():
                self.skipTest(f"{p.name} not built")
            yield key, json.loads(p.read_text(encoding="utf-8"))

    def test_topology_hash_is_of_the_lf_text(self):
        repo = HERE.parents[2]
        for key, m in self.manifests():
            t = m["inputs"]["topology"]
            data = (repo / t["path"]).read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(t["sha256"], hashlib.sha256(data).hexdigest(), key)

    def test_vector_layer_hash_matches_the_file(self):
        for key, m in self.manifests():
            data = (HERE.parents[2] / m["vector_layer"]["path"]).read_bytes()
            self.assertNotIn(b"\r\n", data, key)
            self.assertEqual(m["vector_layer"]["sha256"], hashlib.sha256(data).hexdigest(), key)

    def test_output_paths_are_canonical(self):
        for key, m in self.manifests():
            paths = [o["path"] for o in m["outputs"].values()]
            self.assertTrue(all(p.startswith(f"scraped-data/derived/maps/{key}/") for p in paths), paths)
            mocks = [o["path"] for o in m["k1"]["mocks"].values()]
            mocks += m["checks"]["overlays"] + [m["logo_paint_out"]["before_after"]]
            self.assertTrue(all(p.startswith("<mocks>/") for p in mocks), mocks)
            self.assertEqual(set(m["roots"]), {"scraped-data/derived/maps", "<mocks>"})

    def test_k1_grade_is_the_profile_map_grade(self):
        # ENV-MAPS P4: the mocks b / c and the MI are graded with the ENGINE grade (the light profile's mapGrade).
        for key, m in self.manifests():
            g = m["k1"]["grade_b_c"]
            p = k1_mock.profile_map_grade(key)
            for k in ("ev", "saturation", "lift", "mask_saturation", "lift_saturation"):
                self.assertAlmostEqual(g[k], p[k], places=6, msg=f"{key} {k}")
            self.assertEqual(g["tint_lin"], p["tint_lin"], key)
            self.assertEqual(g["tint_lin_luma_normalised"], p["tint_lin"], key)
            self.assertEqual(g["mask_inverse_tint_lin"], p["mask_inverse_tint_lin"], key)
            self.assertIn("S08ArtBoardProfiles.json", g["source"])


class EngineGrade(unittest.TestCase):
    """ENV-MAPS P4: k1_mock._night = M_MapBoard graph v2 (ue_import_map_surface.py), profile grade reader."""

    def setUp(self):
        rng = np.random.default_rng(4)
        self.c = rng.uniform(0.02, 0.9, size=(500, 3)).astype(np.float32)
        self.g1 = {"ev": -0.35, "saturation": 0.75, "lift": 1.5, "tint_lin": [0.97, 1.0, 1.05]}

    def test_profile_map_grade(self):
        for key in ("marmoreal", "sarpedon"):
            g = k1_mock.profile_map_grade(key)
            self.assertGreater(g["mask_saturation"], 1.0, key)
            self.assertGreaterEqual(g["lift_saturation"], 1.0, key)
            self.assertEqual(len(g["mask_inverse_tint_lin"]), 3, key)
            self.assertIn(f"{key}-original", g["source"])
        with self.assertRaises(ValueError):
            k1_mock.profile_map_grade("no-such-map")

    def test_identity_terms_are_graph_v1(self):
        # without the graph-v2 terms (or at identity) the grade is the pre-P4 formula exactly
        light = (2.0 ** self.g1["ev"]) * np.asarray(self.g1["tint_lin"], np.float32)
        lit = self.c * light
        v1_inside = lit + self.g1["lift"] * self.c
        got = k1_mock._night(self.c, np.ones(len(self.c), np.float32), self.g1)
        np.testing.assert_allclose(got, v1_inside, rtol=1e-6, atol=1e-7)
        ident = dict(self.g1, mask_saturation=1.0, lift_saturation=1.0, mask_inverse_tint_lin=[1.0, 1.0, 1.0])
        np.testing.assert_allclose(k1_mock._night(self.c, np.ones(len(self.c), np.float32), ident), v1_inside,
                                   rtol=1e-6, atol=1e-7)

    def test_mask_terms_raise_chroma_inside_only(self):
        g2 = dict(self.g1, mask_saturation=1.5, lift_saturation=1.6, mask_inverse_tint_lin=[1.0, 1.0, 1.0])
        luma = k1_mock.LUMA
        inside1 = k1_mock._night(self.c, np.ones(len(self.c), np.float32), self.g1)
        inside2 = k1_mock._night(self.c, np.ones(len(self.c), np.float32), g2)
        outside1 = k1_mock._night(self.c, np.zeros(len(self.c), np.float32), self.g1)
        outside2 = k1_mock._night(self.c, np.zeros(len(self.c), np.float32), g2)
        np.testing.assert_array_equal(outside1, outside2)  # outside the game mask nothing changes

        def spread(x):
            return np.abs(x - (x @ luma)[:, None]).sum(axis=1)
        lit = self.c * (2.0 ** g2["ev"]) * np.asarray(g2["tint_lin"], np.float32)

        def raw_sat(x, s):
            y = (x @ luma)[:, None]
            return y + (x - y) * s
        # rows where neither saturated term clips at 0 (max(..., 0) is what keeps the colour valid)
        unclipped = (raw_sat(lit, 1.5) > 0).all(axis=1) & (raw_sat(self.c, 1.6) > 0).all(axis=1)
        self.assertGreater(int(unclipped.sum()), 100)
        self.assertTrue((spread(inside2)[unclipped] >= spread(inside1)[unclipped] - 1e-6).all())
        # luma is kept by the saturation (exactly where nothing clips at 0)
        np.testing.assert_allclose((inside2 @ luma)[unclipped], (inside1 @ luma)[unclipped], rtol=1e-5, atol=1e-6)

    def test_import_mi_params_follow_the_grade(self):
        import ue_import_map_surface as imp
        for key in ("marmoreal", "sarpedon"):
            p = imp.mi_params(imp.load_manifest(key)["k1"]["grade_b_c"])
            g = k1_mock.profile_map_grade(key)
            self.assertEqual(p["scalar"], {"NightEV": g["ev"], "NightSaturation": g["saturation"], "Lift": g["lift"],
                                           "MaskSaturation": g["mask_saturation"],
                                           "LiftSaturation": g["lift_saturation"]})
            self.assertEqual(p["vector"], {"NightTint": g["tint_lin"], "MaskInverseTint": g["mask_inverse_tint_lin"]})
        # a pre-P4 grade (no graph-v2 keys) keeps the identity terms
        p = imp.mi_params({"ev": -0.7, "saturation": 0.7, "lift": 0.35})
        self.assertEqual((p["scalar"]["MaskSaturation"], p["scalar"]["LiftSaturation"], p["vector"]["MaskInverseTint"]),
                         (1.0, 1.0, [1.0, 1.0, 1.0]))
        self.assertEqual(imp.GRAPH_VERSION, "2")
        for hlsl, names in ((imp.BASE_HLSL, ("MaskSaturation", "MaskInverseTint", "NightSaturation")),
                            (imp.LIFT_HLSL, ("LiftSaturation", "Lift")),
                            (imp.FRAME_WOOD_HLSL, ("FrameValueScale", "FrameSaturation")),
                            (imp.CONTACT_SHADOW_HLSL, ("Strength", "Softness"))):
            for name in names:
                self.assertIn(name, hlsl)


class ZoneSeparation(unittest.TestCase):
    """ENV-MAPS P4: the pure parts of zone_separation.py (trace parsing, colour, pairs, camera)."""

    def test_lab(self):
        import zone_separation as zs
        np.testing.assert_allclose(zs.lab(np.array([[255.0, 255.0, 255.0]]))[0], [100.0, 0.0, 0.0], atol=0.05)
        np.testing.assert_allclose(zs.lab(np.array([[0.0, 0.0, 0.0]]))[0], [0.0, 0.0, 0.0], atol=1e-6)
        x = np.linspace(0.0, 2.0, 50)
        np.testing.assert_allclose(zs.aces_inv(zs.aces(x))[zs.aces(x) < 0.99], x[zs.aces(x) < 0.99], rtol=1e-6, atol=1e-6)

    def test_trace_parsing(self):
        import tempfile
        import zone_separation as zs
        v1 = ("2026.10.01-01.38.11 ARTPREVIEW map grade profile=marmoreal-night source=profile nightEV=-0.35 "
              "nightSaturation=0.75 lift=1.50 nightTint=(0.9700,1.0000,1.0500)")
        v2 = ("2026.10.02-01.00.00 ARTPREVIEW map grade profile=marmoreal-night source=profile nightEV=-0.35 "
              "nightSaturation=0.75 lift=1.65 nightTint=(0.9700,1.0000,1.0500) maskSaturation=1.50 liftSaturation=1.60 "
              "maskInverseTint=(0.9830,1.0100,0.9470) graph=v2 maskTerms=1")
        ctx = ("2026.10.01-01.39.26 SHOT ctx viewport=1920x1080 viewTarget=CameraActor_0 cam=(0,1342,1917) rot=(-55,-90,-0)\n"
               "2026.10.01-01.39.27 SHOT captured file=bench-K1-1920x1080.png frame=767\n")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.log"
            p.write_text(v1 + "\n" + ctx, encoding="utf-8")
            g = zs.trace_grade(p)
            self.assertEqual((g["lift"], g["mask_saturation"], g["mask_inverse_tint_lin"]), (1.5, 1.0, [1.0, 1.0, 1.0]))
            self.assertEqual(zs.shot_camera(p, "bench-K1-1920x1080.png"), ([0.0, 1342.0, 1917.0], -55.0, -90.0))
            p.write_text(v1 + "\n" + v2 + "\n", encoding="utf-8")
            g = zs.trace_grade(p)  # the last line wins
            self.assertEqual((g["lift"], g["mask_saturation"], g["lift_saturation"]), (1.65, 1.5, 1.6))
            self.assertEqual(g["mask_inverse_tint_lin"], [0.983, 1.01, 0.947])
            v2_on_v1 = v2.replace("graph=v2", "graph=v1")  # a graph-v1 material ignores the terms
            p.write_text(v2_on_v1 + "\n", encoding="utf-8")
            self.assertEqual(zs.trace_grade(p)["mask_saturation"], 1.0)

    def test_pairs_and_camera(self):
        import zone_separation as zs
        zones = {"a": np.array([50.0, 0, 0]), "b": np.array([50.0, 3, 4]), "c": np.array([80.0, 0, 0])}
        t = zs.pair_table(zones, [("a", "b")])
        self.assertEqual(t["adjacent"], {"a-b": 5.0})
        self.assertEqual(t["minAll"], ["a-b", 5.0])
        self.assertEqual(t["all"]["a-c"], 30.0)
        cam = zs.Cam([0.0, 1342.0, 1917.0], -55.0, -90.0)
        xy = cam.project([[0.0, 0.0, 0.0]])[0]
        self.assertAlmostEqual(xy[0], 960.0, delta=0.5)  # the board centre is on the optical axis (K1)
        self.assertAlmostEqual(xy[1], 540.0, delta=1.0)
        right = cam.project([[100.0, 0.0, 0.0]])[0]
        self.assertGreater(right[0], xy[0])  # +X (east) is screen right



class Backdrop(unittest.TestCase):
    """ENV-MAPS P5 track C (gap 8): backdrop.py mirrors S08BoardArt.cpp / S08MapBackdrop.cpp / the material HLSL."""

    HALF = (1337 * 0.6666667 / 2, 866 * 0.6666667 / 2)

    @staticmethod
    def header() -> str:
        return (HERE.parents[2] / "unreal/Unmatched/Source/Unmatched/S08/S08BoardArt.h").read_text(encoding="utf-8")

    def test_constants_match_the_cpp_header(self):
        import backdrop as bd
        import ue_import_map_surface as ms
        h = self.header()
        for name, value in (("BackdropMaxZ", bd.MAX_Z), ("BackdropMinZ", bd.MIN_Z),
                            ("BackdropMinLayerGapUU", bd.MIN_LAYER_GAP), ("BackdropFarViewRatio", bd.FAR_VIEW_RATIO)):
            m = re.search(r"constexpr float %s = (-?[0-9.]+)f;" % name, h)
            self.assertIsNotNone(m, name)
            self.assertAlmostEqual(float(m.group(1)), value, msg=name)
        self.assertIn("constexpr int32 BackdropMaxMist = %d;" % bd.MAX_MIST, h)
        for path in (ms.BACKDROP_MIST_PATH, ms.BACKDROP_MOON_PATH):
            leaf = path.rsplit("/", 1)[1]
            self.assertIn('TEXT("%s.%s")' % (path, leaf), h)
        params = set(re.findall(r'ParamBackdrop\w+ = TEXT\("(\w+)"\)', h))
        used = (set(bd.MIST_PARAMS["vector"]) | set(bd.MIST_PARAMS["scalar"]) | set(bd.MOON_PARAMS["vector"])
                | set(bd.MOON_PARAMS["scalar"]))
        self.assertEqual(used, params)
        for pin in bd.MIST_INPUTS:
            self.assertIn(pin, bd.MIST_HLSL)
        for pin in bd.MOON_INPUTS:
            self.assertIn(pin, bd.MOON_HLSL)

    def test_camera_matches_zone_separation_cam(self):
        import backdrop as bd
        import zone_separation as zs
        d = bd.k1_fit_distance(self.HALF) * 1.25
        self.assertAlmostEqual(d, 2340.195, delta=0.5)
        self.assertAlmostEqual(bd.far_view_distance(self.HALF), 2880.24, delta=0.5)
        view = bd.BoardView(d)
        cam = zs.Cam(list(view.loc), -55.0, -90.0)
        for p in ((0.0, 0.0, 0.0), (300.0, -200.0, -50.0), (-700.0, 300.0, -3.0)):
            ndc = view.project(p)
            px = cam.project([list(p)])[0]
            self.assertAlmostEqual((ndc[0] + 1) * 960.0, px[0], delta=0.5)
            self.assertAlmostEqual((1 - ndc[1]) * 540.0, px[1], delta=0.5)
        for anchor in ((-0.9, 0.82), (0.3, -0.4)):
            ray = view.ray(anchor)
            back = view.project(tuple(view.loc[i] + ray[i] * 3000.0 for i in range(3)))
            self.assertAlmostEqual(back[0], anchor[0], places=9)
            self.assertAlmostEqual(back[1], anchor[1], places=9)

    def test_shipped_blocks_valid_and_below_the_board(self):
        import backdrop as bd
        blocks = bd.shipped_blocks()
        # P5b tune: Sarpedon has no backdrop (Track B's opaque sea ring under the island hid the moon card)
        self.assertEqual(sorted(blocks), ["marmoreal-original"])
        for bid, board in blocks.items():
            half = bd.map_half(board)
            self.assertEqual(bd.validate_block(board["backdrop"], half, bid), [])
            rep = bd.report(board["backdrop"], half)
            moon = rep["moon"]
            self.assertLessEqual(moon["topZ"], bd.MAX_Z)
            self.assertEqual(moon["ndcFar"], [-0.9, 0.82])  # upper-left of the far zoom (K1 x 0.65) view
            for m in board["backdrop"].get("mist", []):
                self.assertLessEqual(m["zUU"], bd.MAX_Z)
        self.assertEqual(len(blocks["marmoreal-original"]["backdrop"]["mist"]), 2)

    def test_validate_block_rules(self):
        import backdrop as bd
        ok = {"mist": [{"zUU": -400}, {"zUU": -900}], "moon": {}}
        self.assertEqual(bd.validate_block(ok, self.HALF), [])
        for bad, part in (({"mist": [{"zUU": -100}]}, "mist[0]"), ({"mist": [{"zUU": -400}, {"zUU": -450}]}, "closer"),
                          ({"mist": [{"zUU": -400}] * 3}, "at most"), ({"mist": [{"halfUU": [1, 1]}]}, "mist[0]"),
                          ({"moon": {"depthUU": 1500}}, "moon card"), ({}, "at least one"),
                          ({"moon": {"intensity": 0}}, "moon")):
            errs = bd.validate_block(bad, self.HALF)
            self.assertTrue(any(part in e for e in errs), (bad, errs))

    def test_mist_density_mirror(self):
        import backdrop as bd
        p = bd.mist_params({"zUU": -400})
        n = 129
        g = np.linspace(0.0, 1.0, n)
        uv = np.stack(np.meshgrid(g, g), -1)
        d = bd.mist_density(uv, 0.0, p)
        self.assertTrue(np.all((d >= 0) & (d <= 1)))
        self.assertEqual(float(d[0, 0]), 0.0)          # corners outside the ellipse
        self.assertEqual(float(np.abs(d[0, :]).max()), 0.0)  # the plane edge fully faded (no hard rectangle)
        centre = d[n // 4: 3 * n // 4, n // 4: 3 * n // 4]
        self.assertGreater(float(centre.std()), 0.1)    # visible cloud structure inside
        lo = bd.mist_density(uv, 0.0, dict(p, Coverage=0.2)).mean()
        hi = bd.mist_density(uv, 0.0, dict(p, Coverage=0.8)).mean()
        self.assertLess(lo, hi)                          # coverage is monotonic
        moved = bd.mist_density(uv, 60.0, p)             # a minute of pan moves the clouds
        self.assertGreater(float(np.abs(moved - d)[n // 4: 3 * n // 4, n // 4: 3 * n // 4].mean()), 0.01)

    def test_moon_glow_mirror(self):
        import backdrop as bd
        p = bd.moon_params({})
        n = 101
        g = np.linspace(0.0, 1.0, n)
        uv = np.stack(np.meshgrid(g, g), -1)
        e = bd.moon_glow(uv, p)
        lum = e @ np.array([0.2126, 0.7152, 0.0722])
        self.assertEqual(int(np.argmax(lum)), (n // 2) * n + n // 2)  # peak at the centre
        self.assertEqual(float(lum[0, 0]), 0.0)                      # nothing at the card corners
        self.assertEqual(float(lum[n // 2, 0]), 0.0)                 # nor on the card edge (r = 1)
        self.assertTrue(np.all(np.diff(lum[n // 2, n // 2:]) <= 1e-12))  # monotonic falloff
        no_disc = bd.moon_glow(uv, dict(p, DiscRadius=0.0))
        self.assertLess(float(no_disc.max()), float(e.max()))

    def test_mock_view_runs(self):
        import backdrop as bd
        board = bd.shipped_blocks()["marmoreal-original"]
        img = bd.mock_far_view(board["backdrop"], bd.map_half(board), size=(96, 54))
        self.assertEqual(img.shape, (54, 96, 3))
        self.assertTrue(np.isfinite(img).all())


if __name__ == "__main__":
    unittest.main()
