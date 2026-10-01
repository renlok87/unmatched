"""Unit tests for tools/art/map_surface (pure functions, synthetic data; no map images needed).

  python -B -m unittest tools/art/map_surface/test_map_surface.py -v
"""
from __future__ import annotations

import hashlib
import json
import math
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


if __name__ == "__main__":
    unittest.main()
