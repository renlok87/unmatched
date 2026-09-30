"""Tests of the wave 5c-B1 tools: the UE 5.8 Filmic model (ue_filmic), the ring shape classifier rev 2 and the ring
tile reference rev 3 (t53_readability, proposal registered before the 5c-B re-shoot) and the exposure simulation
helpers (t5cb1_exposure_sim).

  python -m pytest tools/art/tests/test_t5cb1.py -v
"""
from __future__ import annotations

import json
import math
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "qa010"))

import t53_readability as T53  # noqa: E402
import t53_team_ring as RING  # noqa: E402
import ue_filmic as F  # noqa: E402
from qa010lib.projection import Camera  # noqa: E402

REPO = T53.REPO
EVID = REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29"


class UeFilmic(unittest.TestCase):
    def test_mid_grey_is_pinned(self):
        """FilmToneMap maps 0.18 to 0.18 (InMatch = OutMatch); the sRGB encode of 0.18 is 117.6."""
        d = F.scene_to_display(np.array([[0.18, 0.18, 0.18]]))[0] * 255.0
        self.assertTrue(np.allclose(d, 117.65, atol=0.05), d)

    def test_monotonic_grey(self):
        x = np.logspace(-4, 1.5, 400)
        d = F.scene_to_display(np.stack([x, x, x], -1))[:, 1]
        self.assertTrue(np.all(np.diff(d) >= -1e-12))
        self.assertLess(d[0] * 255, 1.0)
        self.assertGreater(d[-1] * 255, 254.0)

    def test_inverse_round_trip_on_reachable_colours(self):
        r = np.random.RandomState(7)
        x0 = np.exp(r.uniform(math.log(1e-3), math.log(4.0), (3000, 3)))
        y = F.scene_to_display(x0)
        e = np.abs(F.scene_to_display(F.display_to_scene(y)) - y) * 255.0
        self.assertLess(float(np.percentile(e, 99)), 0.5)

    def test_game_layer_calibration_bytes(self):
        """The unlit game layer (FromSRGBColor x EyeAdaptationInverse -> tone curve) against the 15 screen bytes the
        W5b-R diagnostic measured in the live editor: max 9 levels (green), mean of the per-colour max <= 4."""
        cal = json.loads((EVID / "t53-thresholds.json").read_text(encoding="utf-8"))["calibration"]["bytes"]
        errs = [int(np.abs(np.array(F.game_layer_screen_u8(v["hex"])) - np.array(v["screen"])).max()) for v in cal.values()]
        self.assertLessEqual(max(errs), 9)
        self.assertLessEqual(float(np.mean(errs)), 4.0)

    def test_exposure_shift_of_grey(self):
        g = F.scene_to_display(np.array([[0.18, 0.18, 0.18]]))
        half = F.scene_to_display(np.array([[0.09, 0.09, 0.09]]))
        lut = F.shift_lut(-1.0, 33)
        self.assertTrue(np.allclose(F.apply_lut(g, lut), half, atol=1.0 / 255.0))

    def test_shift_frame_zero_and_mask(self):
        img = (np.random.RandomState(3).rand(8, 8, 3) * 255).astype(np.uint8)
        self.assertTrue(np.array_equal(F.shift_display_u8(img, 0.0), img))
        m = np.zeros((8, 8), bool)
        m[:4] = True
        out = F.shift_display_u8(img, -1.0, m, n=17)
        self.assertTrue(np.array_equal(out[4:], img[4:]))
        self.assertLess(float(out[:4].astype(float).mean()), float(img[:4].astype(float).mean()))


class ShapeClassifierV2(unittest.TestCase):
    """Synthetic top-down frames like test_t53_readability.ShapeClassifier, with the keylines drawn as well."""

    def frame(self, look: str, fs: float = 1.0, px_per_uu: float = 2.0, rot_deg: float = 0.0, occluders=(),
              tile_noise: float = 0.0):
        w = h = 220
        hfov = 60.0
        focal = (w * 0.5) / math.tan(math.radians(hfov) * 0.5)
        cam = Camera(pos=(0.0, 0.0, focal / px_per_uu + 1.2), rot=(-90.0, 0.0, 0.0), hfov_deg=hfov, viewport=(w, h))
        ys, xs = np.mgrid[0:h, 0:w]
        wx = -(ys + 0.5 - h * 0.5) / px_per_uu
        wy = (xs + 0.5 - w * 0.5) / px_per_uu
        c, s = math.cos(math.radians(-rot_deg)), math.sin(math.radians(-rot_deg))
        lx, ly = (wx * c - wy * s) / fs, (wx * s + wy * c) / fs  # into the ring's local frame
        spec = RING.RING_SPEC["p1" if look == "P1" else "p2"]
        masks = {}
        for band, (a0, a1) in spec["bands"].items():
            quads = (RING.circle_band_quads(a0, a1, 96) if look == "P1" else RING.hex_band_quads(a0, a1, spec["cornerGapUU"]))
            m = np.zeros((h, w), bool)
            for q in quads:
                inside = np.ones((h, w), bool)
                ccw = sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4)) > 0
                for i in range(4):
                    (x0, y0), (x1, y1) = q[i], q[(i + 1) % 4]
                    cr = (x1 - x0) * (ly - y0) - (y1 - y0) * (lx - x0)
                    inside &= cr >= -1e-9 if ccw else cr <= 1e-9
                m |= inside
            masks[band] = m
        team = masks["fill"].copy()
        key = masks["keylineIn"] | masks["keylineOut"]
        if tile_noise:
            noise = np.random.RandomState(11).rand(h, w) < tile_noise
            team |= noise & ~key & ~masks["fill"]
        for x0, x1 in occluders:
            team[:, x0:x1] = False
            key[:, x0:x1] = False
        shot = SimpleNamespace(proj=SimpleNamespace(camera=cam), w=w, h=h,
                               fighters={"f": SimpleNamespace(world=(0.0, 0.0, 0.0))})
        return shot, team, key

    def test_circle(self):
        shot, t, k = self.frame("P1")
        self.assertEqual(T53.classify_shape_v2(shot, "f", t, k, 1.0, 1.2)["shape"], "circle")

    def test_hexagon_and_corner_gaps(self):
        shot, t, k = self.frame("P2")
        res = T53.classify_shape_v2(shot, "f", t, k, 1.0, 1.2)
        self.assertEqual(res["shape"], "hexagon", res)
        self.assertGreaterEqual(res["cornerGaps"], 3)
        self.assertAlmostEqual(res["hexTheta0Deg"] % 60.0, 0.0, delta=2.0)

    def test_thin_occluders_do_not_break_a_circle(self):
        """The rev 1 limitation (a 1-3 sample occluder = a break) is gone: occluded rays are just left out."""
        shot, t, k = self.frame("P1", occluders=((108, 111), (60, 62), (150, 153)))
        self.assertEqual(T53.classify_shape_v2(shot, "f", t, k, 1.0, 1.2)["shape"], "circle")
        self.assertNotEqual(T53.classify_shape(shot, "f", t, 1.0, 1.2)["shape"], "circle")

    def test_sidekick_hexagon_at_low_resolution(self):
        """Merlin-like case: FS 0.78 at 1.6 px/uu (corner gap 1.56 uu = 2.5 px) - missed by 72 samples in rev 1."""
        shot, t, k = self.frame("P2", fs=0.78, px_per_uu=1.6)
        self.assertEqual(T53.classify_shape_v2(shot, "f", t, k, 0.78, 1.2)["shape"], "hexagon")

    def test_rotated_hexagon(self):
        shot, t, k = self.frame("P2", rot_deg=17.0)
        res = T53.classify_shape_v2(shot, "f", t, k, 1.0, 1.2)
        self.assertEqual(res["shape"], "hexagon", res)
        self.assertAlmostEqual(res["hexTheta0Deg"], 17.0, delta=2.0)

    def test_tile_of_the_fill_colour_is_not_the_ring(self):
        """Grey variant on light tiles: tile pixels that match the fill are not keyline-bounded."""
        shot, t, k = self.frame("P1", tile_noise=0.3)
        self.assertEqual(T53.classify_shape_v2(shot, "f", t, k, 1.0, 1.2)["shape"], "circle")

    def test_heavily_occluded_is_unclassified(self):
        shot, t, k = self.frame("P2", occluders=((0, 150),))
        self.assertEqual(T53.classify_shape_v2(shot, "f", t, k, 1.0, 1.2)["shape"], "unclassified")

    def test_ray_centerline_needs_both_keylines(self):
        rh = [18.0 + 0.25 * i for i in range(40)]
        lab = ["O"] * 40
        for i in range(18, 30):
            lab[i] = "T"
        self.assertIsNone(T53.ray_centerline(lab, rh, 1.5, 25.0))
        lab[16], lab[31] = "K", "K"
        self.assertAlmostEqual(T53.ray_centerline(lab, rh, 1.5, 25.0), sum(rh[18:30]) / 12, places=6)


class TwoToneRingAA(unittest.TestCase):
    """B1-3 two-tone ring (keyline + light rim #F2ECDE) rendered with anti-aliasing at the K1 scale (1.45 px/uu,
    foreshortened ~0.78 by a -52 deg camera; sidekick FS 0.78) and read by the classifier B1-0 registers. The first
    proposal ('b1-thin': outer keyline 1.0 / 0.75 uu) lost the keyline to AA against the rim; the revised 'b1' keeps the
    r3 outer keyline and the rim bound of teamShape rev 2 reads both."""

    @classmethod
    def setUpClass(cls):
        import t5cb1_ring_sim as R
        cls.R = R
        cal = json.loads((EVID / "t53-thresholds.json").read_text(encoding="utf-8"))["calibration"]["bytes"]
        cls.calib = cal
        cls.colours = {"fill": {"P1": cal["team.p1.fill"]["screen"], "P2": cal["team.p2.fill"]["screen"]},
                       "keyline": cal["mark.keyline"]["screen"], "rim": R.rim_screen()}

    def shot(self, look: str, fs: float, tile, ppu: float = 1.45):
        from qa010lib import color as C
        w, h, hfov, pitch = 240, 200, 35.0, -52.0
        focal = (w * 0.5) / math.tan(math.radians(hfov) * 0.5)
        dist = focal / ppu
        fwd = (0.0, -math.cos(math.radians(pitch)), math.sin(math.radians(pitch)))  # yaw -90: looks along -Y
        cam = Camera(pos=(-dist * fwd[0], -dist * fwd[1], 1.2 - dist * fwd[2]), rot=(pitch, -90.0, 0.0), hfov_deg=hfov,
                     viewport=(w, h))
        fid = "p-hero" if fs == 1.0 else "p-sidekick"
        rgb = np.zeros((h, w, 3), np.uint8)
        rgb[:] = tile
        s = SimpleNamespace(proj=SimpleNamespace(camera=cam), w=w, h=h, rgb=rgb, np=np,
                            fighters={fid: SimpleNamespace(world=(0.0, 0.0, 0.0))},
                            rings={fid: {"look": look, "shown": True}})
        s.lab = C.linear_to_lab(C.u8_to_linear(rgb))
        return s, fid

    def classify(self, geo_name: str, look: str, fs: float, tile, blur: float, rim_bound: bool = True,
                 ppu: float = 1.45) -> dict:
        from qa010lib import color as C
        s, fid = self.shot(look, fs, tile, ppu)
        rgb = self.R.paint_rings(s, self.R.GEOMETRIES[geo_name], self.colours, blur=blur, keep_occluders=False)
        s.rgb = rgb
        s.variants = {"color": rgb, "gray": C.grayscale(rgb), "deuteranopia": C.deuteranopia(rgb)}
        s.lab = C.linear_to_lab(C.u8_to_linear(rgb))
        masks = T53.variant_masks(s, look, self.calib, 15.0)
        rims = T53.variant_mask(s, self.colours["rim"], 15.0)
        out = {}
        for vn, (tm, km) in masks.items():
            res = T53.classify_shape_v2(s, fid, tm, km, fs, 1.2, rim_mask=rims[vn] if rim_bound else None)
            out[vn] = (res["shape"], res.get("filled", 0), int((km & ~tm).sum()), int(rims[vn].sum()))
        return out

    def test_geometry_rules(self):
        self.assertFalse(any(v["problems"] for v in self.R.check_geometry(self.R.GEOMETRIES["b1"]).values()))
        self.assertFalse(any(v["problems"] for v in self.R.check_geometry(self.R.GEOMETRIES["r3"]).values()))
        thin = self.R.check_geometry(self.R.GEOMETRIES["b1-thin"])
        self.assertTrue(all(any("outer keyline" in p for p in v["problems"]) for v in thin.values()))
        for look, v in self.R.check_geometry(self.R.GEOMETRIES["b1"]).items():
            self.assertGreaterEqual(v["clearanceUU"], 1.0, look)

    def test_b1_classified_at_k1_scale(self):
        """Every look x scale x tile (dark Cobble at the proposed light, light fixture) x AA (4x4 box; box + Gaussian
        0.35 px) x variant at 1.45 px/uu (r3 K1 rings: Cobble 1.52-1.61, fixtures 1.77-1.90 tangential): the expected
        shape, >= 25 % of the 360 rays, >= 10 keyline and rim pixels."""
        for look, want in (("P1", "circle"), ("P2", "hexagon")):
            for fs in (1.0, 0.78):
                for tile in ((92, 88, 84), (170, 166, 158)):
                    for blur in (0.0, 0.35):
                        for vn, (shape, filled, key_px, rim_px) in self.classify("b1", look, fs, tile, blur).items():
                            tag = (look, fs, tile, blur, vn, filled)
                            self.assertEqual(shape, want, tag)
                            self.assertGreaterEqual(filled, 90, tag)
                            self.assertGreaterEqual(key_px, 10, tag)
                            self.assertGreaterEqual(rim_px, 10, tag)

    def test_rim_bound_is_needed_next_to_a_light_rim(self):
        """P2 helper on the dark tile: the rejected 'b1-thin' (outer keyline 0.75 uu) is unreadable without the rim
        bound, and even the r3-wide 1.0 uu keyline next to the light rim bounds too few rays - hence both the r3 width
        and the rim bound of teamShape rev 2."""
        for geo in ("b1-thin", "b1"):
            res = self.classify(geo, "P2", 0.78, (92, 88, 84), 0.0, rim_bound=False)
            self.assertTrue(all(shape != "hexagon" for shape, *_ in res.values()), (geo, res))
        thin = self.classify("b1-thin", "P2", 0.78, (92, 88, 84), 0.0, rim_bound=False)
        wide = self.classify("b1", "P2", 0.78, (92, 88, 84), 0.0, rim_bound=False)
        self.assertLess(max(f for _, f, *_ in thin.values()), min(f for _, f, *_ in wide.values()))

    def test_ray_centerline_rim_bounds_only_outside(self):
        rh = [18.0 + 0.25 * i for i in range(40)]
        lab = ["O"] * 40
        for i in range(18, 30):
            lab[i] = "T"
        lab[16], lab[31] = "K", "R"
        self.assertIsNone(T53.ray_centerline(lab, rh, 1.5, 25.0))  # default: keyline only
        self.assertIsNotNone(T53.ray_centerline(lab, rh, 1.5, 25.0, outer=("K", "R")))
        lab[16], lab[31] = "R", "K"
        self.assertIsNone(T53.ray_centerline(lab, rh, 1.5, 25.0, outer=("K", "R")))  # no rim inside

    def test_rim_bound_window_spans_the_outer_keyline(self):
        """Revision 1 of the 5c-B1 thresholds: fill run, the outer keyline anti-aliased away (O), then the rim - bound
        only with the rim window boundUU + keyline width; a keyline sample keeps the 1.5-uu window."""
        rh = [18.0 + 0.25 * i for i in range(64)]
        lab = ["O"] * 64
        lab[14] = "K"                     # inner keyline at 21.5
        for i in range(16, 29):           # fill 22.0..25.0
            lab[i] = "T"
        for i in range(36, 40):           # rim 27.0..27.75: first rim sample 2.0 uu after the run
            lab[i] = "R"
        self.assertIsNone(T53.ray_centerline(lab, rh, 1.5, 25.0, outer=("K", "R")))
        self.assertIsNotNone(T53.ray_centerline(lab, rh, 1.5, 25.0, outer=("K", "R"), rim_bound_uu=2.5))
        lab2 = list(lab)
        for i in range(36, 40):
            lab2[i] = "K"                 # a keyline sample 2.0 uu after the run: still outside the 1.5-uu window
        self.assertIsNone(T53.ray_centerline(lab2, rh, 1.5, 25.0, outer=("K", "R"), rim_bound_uu=2.5))

    def test_rim_bound_follows_the_ring_spec(self):
        self.assertEqual(T53.rim_bound_uu("P1"), 3.0)
        self.assertEqual(T53.rim_bound_uu("P2"), 2.5)
        with RING.using_bands(RING.RING_BANDS_R3):
            self.assertIsNone(T53.rim_bound_uu("P1"))  # one-tone r3 ring

    def test_rim_of(self):
        self.assertIsNone(T53.rim_of("P1", self.calib, None))  # r3 thresholds: no 'team.rim' bytes
        rim = {"screen": [1, 2, 3], "bands": {"P1": [(27.5, 28.5)], "P2": [(26.25, 27.25)]}}
        self.assertEqual(T53.rim_of("P2", self.calib, rim)["bands"], [(26.25, 27.25)])
        cal = dict(self.calib, **{"team.rim": {"screen": [217, 215, 210]}})
        before = json.dumps(RING.RING_SPEC, sort_keys=True)
        with self.R.ring_spec(self.R.GEOMETRIES["b1"]):
            self.assertEqual(T53.rim_of("P1", cal, None), {"screen": [217, 215, 210], "bands": [(27.5, 28.5)]})
            self.assertIsNone(T53.rim_of("P1", self.calib, None))  # no calibrated rim bytes
        with self.R.ring_spec(self.R.GEOMETRIES["r3"]):
            self.assertIsNone(T53.rim_of("P1", cal, None))  # one-tone ring
        self.assertEqual(json.dumps(RING.RING_SPEC, sort_keys=True), before)  # restored


class R3Evidence(unittest.TestCase):
    """The W5b-R r3 Cobble K1 joiner frame (in git): rev 1 left the helpers 'unclassified' and the ring keyline below
    3:1 against a reference that dropped the light stones; rev 2 / rev 3 read them. Measured with the r3 ring bands the
    frame was shot with (RING_SPEC holds the 5c-B1 two-tone geometry since B1-3)."""

    def setUp(self):
        self.spec_bands = {s: RING.RING_SPEC[s]["bands"] for s in ("p1", "p2")}  # the generator's (5c-B1) bands
        self._bands = RING.using_bands(RING.RING_BANDS_R3)
        self._bands.__enter__()
        self.addCleanup(self._bands.__exit__, None, None, None)

    def test_evidence_bands_follow_the_thresholds(self):
        th = json.loads((EVID / "t53-thresholds.json").read_text(encoding="utf-8"))
        self.assertEqual(T53.evidence_ring_bands(th), RING.RING_BANDS_R3)
        import t5cb1_ring_sim as R
        want = {s: {k: list(v) for k, v in R.GEOMETRIES[R.PROPOSAL][lk].items()} for s, lk in (("p1", "P1"), ("p2", "P2"))}
        b1 = T53.REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r3-2026-09-30/t5cb-thresholds.json"
        if b1.is_file():  # the 5c-B1 registration carries the geometry the 5c-B1 frames are shot with
            self.assertEqual(T53.evidence_ring_bands(json.loads(b1.read_text(encoding="utf-8"))), want)
        self.assertEqual(self.spec_bands, want)  # B1-3: the generator (and the C++ spec) = the checked proposal

    @classmethod
    def setUpClass(cls):
        run = EVID / "k1/cobble-5x6/run-20260929-192438"
        cls.shot = T53.Shot(run / "phase2-board-joiner-1920x1080.png", run / "phase2-client-joiner.trace.log")
        th = json.loads((EVID / "t53-thresholds.json").read_text(encoding="utf-8"))
        cls.calib = th["calibration"]["bytes"]
        cls.cells = T53.T52.board_cells(T53.T52_EVIDENCE, "cobble-5x6")
        cls.ids = {T53.FIGHTER_NAMES.get(f, f): f for f in cls.shot.fighters}

    def test_helpers_classified(self):
        for name, want in (("Harpies 1", "circle"), ("Merlin", "hexagon")):
            fid = self.ids[name]
            look = self.shot.rings[fid]["look"]
            team, key = T53.variant_masks(self.shot, look, self.calib, 15.0)["color"]
            z = self.shot.fighters[fid].world[2] + RING.RING_SPEC["zMax"]
            fs = T53.fighter_scale(fid)
            self.assertEqual(T53.classify_shape_v2(self.shot, fid, team, key, fs, z)["shape"], want, name)
            self.assertEqual(T53.classify_shape(self.shot, fid, team, fs, z)["shape"], "unclassified", name)

    def test_tile_reference_rev3_keeps_the_light_stones(self):
        fid = self.ids["Harpies 3"]
        ref = T53.ring_tile_reference_rev3(self.shot, fid, self.calib, self.cells)
        self.assertGreaterEqual(ref["tilePx"], 500)
        self.assertGreater(ref["color"]["keylineVsTile"], 3.5)
        rev2 = next(r for r in T53.rings_rev2(self.shot, json.loads((EVID / "t53-thresholds.json").read_text(
            encoding="utf-8")), self.calib, self.cells)["fighters"] if r["fighter"] == fid)
        self.assertLess(rev2["variants"]["color"]["keylineVsTile"], 3.0)


class ExposureSimHelpers(unittest.TestCase):
    def test_key_fix_gain_is_small_and_positive(self):
        import t5cb1_exposure_sim as S
        for b in S.KEY_FIX:
            ev = S.key_fix_ev(b)
            self.assertGreater(ev, 0.0)
            self.assertLess(ev, 0.35)

    def test_sky_series_is_linear_through_the_curve(self):
        import t5cb1_exposure_sim as S
        for name, v in S.validate_sky().items():
            self.assertLess(v["lumaResidualMax"], 0.3, name)
            self.assertGreater(v["lumaResidualMaxGamma22"], v["lumaResidualMax"], name)


class SnapshotRebaseline(unittest.TestCase):
    def test_new_file_under_a_production_dir(self):
        import copy
        import tempfile
        import snapshot_rebaseline as SR
        doc = json.loads(SR.BASELINE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            d = root / "unreal/Unmatched/Content/ArtPreview/Medusa/Materials"
            d.mkdir(parents=True)
            (d / "MI_New.uasset").write_bytes(b"abc")
            doc2 = copy.deepcopy(doc)
            ch = SR.rebaseline(doc2, {"repo": root}, [("repo", "unreal/Unmatched/Content/ArtPreview/Medusa/Materials/MI_New.uasset")],
                               "test", "report.md", "2026-09-30")
            self.assertEqual(ch[0]["change"], "added")
            holder = next(x for x in doc2["productionDirs"] if x["root"] == "repo" and x["dir"].endswith("ArtPreview/Medusa"))
            row = next(f for f in holder["files"] if f["path"].endswith("MI_New.uasset"))
            self.assertEqual(row["sha256"], "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
            self.assertEqual(holder["fileCount"], len(holder["files"]))
            self.assertEqual(doc2["revisions"][-1]["task"], "test")
            ch2 = SR.rebaseline(doc2, {"repo": root}, [("repo", "unreal/Unmatched/Content/ArtPreview/Medusa/Materials/MI_New.uasset")],
                                "test", "report.md", "2026-09-30")
            self.assertEqual(ch2[0]["change"], "unchanged")
            with self.assertRaises(FileNotFoundError):
                SR.rebaseline(doc2, {"repo": root}, [("repo", "unreal/Unmatched/Content/ArtPreview/Medusa/none.uasset")],
                              "t", "r", "d")


class B1Thresholds(unittest.TestCase):
    """The 5c-B1 registration (B1-0) and its revision 1: the base sha256 is the registration copy, and the registered ring
    geometry / rim colour are what the generator, the C++ spec and the HUD tokens carry."""
    B1 = REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r3-2026-09-30"

    def setUp(self):
        if not (self.B1 / "t5cb-thresholds.json").is_file():
            self.skipTest("5c-B1 thresholds not registered")
        self.th = json.loads((self.B1 / "t5cb-thresholds.json").read_text(encoding="utf-8"))

    def test_revision_base_is_the_registration(self):
        import hashlib
        # Hash the committed (LF) bytes: a core.autocrlf=true checkout rewrites the file with CRLF.
        reg = (self.B1 / "t5cb-thresholds.registration-b1-0.json").read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(hashlib.sha256(reg).hexdigest(), self.th["revisions"][0]["base"]["sha256"])
        self.assertEqual(json.loads(reg.decode("utf-8"))["revisions"], [])
        self.assertLess(json.loads(reg.decode("utf-8"))["registeredLocal"], self.th["revisions"][0]["registeredLocal"])

    def test_rim_colour_is_one_value_everywhere(self):
        import re
        tok = json.loads((REPO / "docs/unreal/contracts/hud/hud-style-tokens.json").read_text(encoding="utf-8"))["colors"]
        h = (REPO / "unreal/Unmatched/Source/Unmatched/S08/S08Team.h").read_text(encoding="utf-8")
        cpp = re.search(r'RimHex = TEXT\("(#[0-9A-Fa-f]{6})"\)', h).group(1).upper()
        self.assertEqual({self.th["rings"]["rim"]["hex"].upper(), self.th["calibration"]["bytes"]["team.rim"]["hex"].upper(),
                          tok["team.rim"]["hex"].upper(), RING.team_hex()["rim"].upper(), cpp}, {"#FFFFFF"})
        self.assertIsInstance(self.th["calibration"]["bytes"]["team.rim"]["screen"], list)
        for k in ("zone.red", "zone.gray"):
            self.assertIsInstance(self.th["calibration"]["bytes"][k]["screen"], list)

    def test_zone_colours_match_the_profiles(self):
        prof = json.loads((REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json").read_text(encoding="utf-8"))
        for key in ("red", "gray"):
            self.assertEqual(prof["zoneStyles"][key]["color"].upper(), self.th["zones"]["colors"][key].upper())
            self.assertEqual(self.th["calibration"]["bytes"]["zone." + key]["hex"].upper(), self.th["zones"]["colors"][key].upper())
        for lp in prof["lightProfiles"].values():
            self.assertEqual(lp["directional"]["rotation"], self.th["light"]["rotation"])
            self.assertEqual(lp["exposure"]["minBrightness"], self.th["light"]["exposure"]["minBrightness"])
            self.assertAlmostEqual(2 ** lp["exposure"]["ev100"], lp["exposure"]["minBrightness"], places=4)


if __name__ == "__main__":
    unittest.main()
