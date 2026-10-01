"""Tests for the ENV-U10 themed ground tools (ENV-MAPS P2 track GROUND):
tools/art/env_kit/ground_splat.py (splat masks + layout 'ground' sections), tools/art/env_kit/ue_import_env_ground.py
(the plain-Python stages) and the ground check of tools/art/env_kit/layout_check.py.

The splat tests run everywhere (numpy / PIL, committed layouts and params). The staging test needs the gitignored
staging folder of ue_import_env_ground.py --prep and skips cleanly without it.

  python -m pytest tools/art/tests/test_env_ground.py -q
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ENV_KIT = HERE.parents[0] / "env_kit"
sys.path.insert(0, str(ENV_KIT))

import ground_splat as GS  # noqa: E402
import layout_check as LC  # noqa: E402
import ue_import_env_ground as IMP  # noqa: E402

PARAMS = GS.load_params(GS.PARAMS_DEFAULT)
SHARED_TRAY = GS.tray_rect(PARAMS["tray"])  # (-780, -515, 780, 425)


def layout(key: str) -> dict:
    return json.loads((GS.LAYOUT_DIR / f"{key}.layout.json").read_text(encoding="utf-8"))


_CACHE: dict = {}


def generated(key: str) -> dict:
    if key not in _CACHE:
        _CACHE[key] = GS.generate(key, PARAMS, layout(key))
    return _CACHE[key]


def sample(res: dict, x: float, y: float) -> np.ndarray:
    """Decoded splat value (R, G, B coverage, A accent) at board XY (nearest pixel)."""
    x0, y0, x1, y1 = res["rect"]
    w, h = res["size"]
    i = min(max(int((x - x0) / (x1 - x0) * w), 0), w - 1)
    j = min(max(int((y - y0) / (y1 - y0) * h), 0), h - 1)
    return GS.decode(res["array"][j:j + 1, i:i + 1])[0, 0]


class SplatGeometry(unittest.TestCase):
    def test_rect_covers_the_shared_tray_with_margin(self):
        for key in GS.MAPS:
            x0, y0, x1, y1 = generated(key)["rect"]
            tx0, ty0, tx1, ty1 = SHARED_TRAY
            m = PARAMS["splat"]["marginUU"]
            self.assertTrue(x0 <= tx0 - m and y0 <= ty0 - m and x1 >= tx1 + m and y1 >= ty1 + m, key)
            self.assertEqual(generated(key)["size"], tuple(PARAMS["splat"]["size"]))

    def test_deterministic_bytes(self):
        for key in GS.MAPS:
            again = GS.generate(key, PARAMS, layout(key))
            self.assertEqual(again["sha256"], generated(key)["sha256"], key)

    def test_alpha_never_zero(self):
        # UE's PNG import may infill the RGB of zero-alpha pixels (TextureImporter FillPNGZeroAlpha)
        for key in GS.MAPS:
            self.assertGreaterEqual(int(generated(key)["array"][..., 3].min()), 1, key)

    def test_stacked_weights_sum_to_one(self):
        rng = np.random.default_rng(3)
        r, g, b = rng.random((3, 64))
        h = tuple(rng.random((3, 64)))
        w = GS.stacked_weights(r, g, b, h, 0.25)
        np.testing.assert_allclose(sum(w), 1.0, atol=1e-12)
        full = GS.stacked_weights(np.ones(1), np.zeros(1), np.ones(1), contrast=0.25)
        self.assertAlmostEqual(float(full[3][0]), 1.0)  # L3 on top of everything

    def test_coverage_is_themed(self):
        mar, sar = GS.coverage(generated("marmoreal"), PARAMS), GS.coverage(generated("sarpedon"), PARAMS)
        self.assertGreater(mar["L3"], 0.3)  # marble paving round the frame and the palace terrace
        self.assertGreater(mar["L0"], 0.15)  # dark earth (the cherry beds)
        self.assertGreater(mar["accentMean"], 0.1)  # petals
        self.assertGreater(sar["L3"], 0.3)  # deck planks E
        self.assertGreater(sar["L1"], 0.1)  # sand
        self.assertGreater(sar["L2"], 0.05)  # pebbles in the river channels
        self.assertGreater(sar["L0"], 0.2)  # forest floor W


class SplatRules(unittest.TestCase):
    def test_marmoreal_regions(self):
        res = generated("marmoreal")
        lay = layout("marmoreal")
        self.assertGreater(sample(res, 0, -360)[2], 0.95)  # palace terrace: paving
        self.assertGreater(sample(res, -505, 0)[2], 0.95)  # W walkway next to the frame
        cherry = next(p for p in lay["props"] if p["id"] == "cherry-w")
        c = sample(res, *cherry["loc"][:2])
        self.assertLess(c[2], 0.05)  # no paving under the cherry
        self.assertGreater(c[3], 0.8)  # a carpet of petals
        self.assertGreater(sample(res, -776, 100)[0], 0.5)  # moss along the tray rim
        for p in lay["props"]:
            if LC.mesh_name(p) == "LanternPlinth":
                self.assertGreater(sample(res, *p["loc"][:2])[2], 0.95, p["id"])  # lamp pads are paved

    def test_sarpedon_regions(self):
        res = generated("sarpedon")
        lay = layout("sarpedon")
        for p in lay["props"]:
            if LC.mesh_name(p) in ("Hull", "Cannon"):
                self.assertGreater(sample(res, *p["loc"][:2])[2], 0.95, p["id"])  # on the deck
        fa, fb = PARAMS["maps"]["sarpedon"]["river"]["farEdgeX"]
        far = sample(res, (fa + fb) / 2 + 15, -420)
        self.assertGreater(far[1], 0.9)  # pebbles in the far channel
        self.assertGreater(far[3], 0.8)  # wet (x 0.82 .. 1 noise)
        na, nb = PARAMS["maps"]["sarpedon"]["river"]["nearEdgeX"]
        near = sample(res, (na + nb) / 2 - 10, 400)
        self.assertGreater(near[1], 0.9)  # pebbles at the river mouth near edge (waterfall)
        self.assertGreater(sample(res, 0, -420)[0], 0.9)  # beach N-centre: sand
        forest = sample(res, -700, 150)
        self.assertLess(max(forest[:3]), 0.1)  # the forest floor base (W)
        fort = next(p for p in lay["props"] if LC.mesh_name(p) == "FortRuin")
        self.assertGreater(max(sample(res, *fort["loc"][:2])[:2]), 0.5)  # fort dust / rubble

    def test_layout_sections_match_the_splats(self):
        for key in GS.MAPS:
            lay = layout(key)
            png = GS.REPO / lay["ground"]["splat"]
            self.assertTrue(png.is_file(), key)
            res = dict(generated(key), sha256=GS.sha256_bytes(png.read_bytes()))
            self.assertEqual(GS.check_layout_ground(key, lay, res, PARAMS), [], key)
            self.assertEqual(res["sha256"], generated(key)["sha256"], f"{key}: committed splat != the rules")


class GroundCheck(unittest.TestCase):
    def test_strips_mirror_s08envground(self):
        hole = (-LC.FRAME_HX + 2, -LC.FRAME_HY + 2, LC.FRAME_HX - 2, LC.FRAME_HY - 2)
        strips = LC.ground_strips(SHARED_TRAY, hole)
        self.assertEqual(len(strips), 4)
        area = sum((r[2] - r[0]) * (r[3] - r[1]) for r in strips)
        tray_area = (SHARED_TRAY[2] - SHARED_TRAY[0]) * (SHARED_TRAY[3] - SHARED_TRAY[1])
        hole_area = (hole[2] - hole[0]) * (hole[3] - hole[1])
        self.assertAlmostEqual(area, tray_area - hole_area, places=6)
        self.assertEqual(LC.ground_strips(SHARED_TRAY, (-1e4, -1e4, 1e4, 1e4)), [])
        self.assertEqual(LC.ground_strips(SHARED_TRAY, (2000, 2000, 2100, 2100)), [SHARED_TRAY])

    def test_shipped_layout_ground_is_valid(self):
        for key in GS.MAPS:
            err, warn, info = LC.validate_ground(layout(key), key, SHARED_TRAY)
            self.assertEqual(err, [], key)
            self.assertEqual(info["strips"], 4, key)


class ImportStages(unittest.TestCase):
    def test_rot90_dx_normal_matches_the_rotated_height(self):
        # a height field, its DirectX normal map (x right, y down), then both rotated: the rotated normal map must be
        # the normal map of the rotated height field
        n = 64
        yy, xx = np.mgrid[0:n, 0:n].astype(float)
        h = np.sin(xx / 5.0) * 3.0 + np.cos(yy / 7.0) * 2.0 + 0.05 * xx * yy / n

        def dx_normal(height):
            gy, gx = np.gradient(height)
            v = np.stack([-gx, -gy, np.ones_like(gx)], axis=-1)
            v /= np.linalg.norm(v, axis=-1, keepdims=True)
            return np.clip(np.rint((v * 0.5 + 0.5) * 255), 0, 255).astype(np.uint8)
        rotated = IMP.rot90_dx_normal(dx_normal(h))
        expected = dx_normal(np.rot90(h, 1))
        diff = np.abs(rotated.astype(int) - expected.astype(int))[2:-2, 2:-2, :2]
        self.assertLessEqual(int(diff.max()), 2)

    def test_used_sets_and_asset_names(self):
        self.assertEqual(sorted(IMP.used_sets(PARAMS, ["marmoreal", "sarpedon"])),
                         sorted(["Ground076", "Moss002", "Grass005", "Tiles143", "Ground055S", "Gravel021",
                                 "Planks023A"]))
        self.assertEqual(IMP.mi_asset("marmoreal"), "/Game/EnvKit/Ground/MI_EnvGround_Marmoreal")
        self.assertEqual(IMP.texture_asset("Planks023A", "ORMH"), "/Game/EnvKit/Ground/Sets/T_Ground_Planks023A_ORMH")
        for key in GS.MAPS:
            self.assertEqual(layout(key)["ground"]["material"], IMP.mi_asset(key))

    def test_plan_against_the_staging(self):
        staging = IMP.STAGING_DEFAULT
        if not (staging / "ground-sources.json").is_file():
            self.skipTest(f"no staging at {staging} (ue_import_env_ground.py --prep)")
        pl = IMP.plan(PARAMS, ["marmoreal", "sarpedon"], staging, GS.PARAMS_DEFAULT)
        bad = {s: {k: t.get("error") for k, t in it["textures"].items() if not t["ok"]} for s, it in pl["sets"].items()}
        self.assertTrue(pl["ok"], json.dumps({"sets": bad, "maps": {k: m.get("error") for k, m in pl["maps"].items()}}))


if __name__ == "__main__":
    unittest.main()
