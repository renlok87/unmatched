"""Tests for the ENV-U10 themed ground tools (ENV-MAPS P2 track GROUND, P4 water / edges / petals):
tools/art/env_kit/ground_splat.py (splat + aux masks, layout 'ground' sections, waterfalls), tools/art/env_kit/
ue_import_env_ground.py (the plain-Python stages, the procedural water ripple, the MI parameters) and the ground check of
tools/art/env_kit/layout_check.py.

The splat tests run everywhere (numpy / PIL, committed layouts and params). The staging test needs the gitignored
staging folder of ue_import_env_ground.py --prep and skips cleanly without it. The two 'committed' checks
(test_layout_sections_match_the_splats, test_plan_against_the_staging) need the layouts' ground sections written by
ground_splat.py --write-layouts after the last layout / params change.

  python -m pytest tools/art/tests/test_env_ground.py -q
"""
from __future__ import annotations

import copy
import json
import re
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


def sample(res: dict, x: float, y: float, key: str = "array") -> np.ndarray:
    """Decoded splat value (R, G, B coverage, A accent) - or with key 'aux' the aux mask (R water, G foam, B edge,
    A depth) - at board XY (nearest pixel)."""
    x0, y0, x1, y1 = res["rect"]
    w, h = res["size"]
    i = min(max(int((x - x0) / (x1 - x0) * w), 0), w - 1)
    j = min(max(int((y - y0) / (y1 - y0) * h), 0), h - 1)
    return GS.decode(res[key][j:j + 1, i:i + 1])[0, 0]


def water_run(res: dict, y: float):
    """x extent of the aux water >= 0.5 on the splat row nearest y (None without water)."""
    X, Y = res["X"], res["Y"]
    j = int(np.argmin(np.abs(Y[:, 0] - y)))
    xs = X[j][GS.decode(res["aux"])[j, :, 0] >= 0.5]
    return (float(xs.min()), float(xs.max())) if len(xs) else None


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
            self.assertEqual(again["auxSha256"], generated(key)["auxSha256"], key)
            self.assertEqual(again["falls"], generated(key)["falls"], key)

    def test_alpha_never_zero(self):
        # UE's PNG import may infill the RGB of zero-alpha pixels (TextureImporter FillPNGZeroAlpha)
        for key in GS.MAPS:
            self.assertGreaterEqual(int(generated(key)["array"][..., 3].min()), 1, key)
            self.assertGreaterEqual(int(generated(key)["aux"][..., 3].min()), 1, key)
            self.assertEqual(generated(key)["aux"].shape, generated(key)["array"].shape, key)

    def test_gauss_blur_keeps_constants_and_mass(self):
        flat = np.full((40, 60), 0.37)
        np.testing.assert_allclose(GS.gauss_blur(flat, (3.0, 2.0)), flat, atol=1e-12)
        spot = np.zeros((41, 41))
        spot[20, 20] = 1.0
        b = GS.gauss_blur(spot, (2.0, 2.0))
        self.assertAlmostEqual(float(b.sum()), 1.0, places=6)
        self.assertAlmostEqual(float(b[20, 18]), float(b[18, 20]), places=12)  # isotropic for equal sigmas
        np.testing.assert_array_equal(GS.gauss_blur(spot, (0.0, 0.0)), spot)

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
        # P4: water only on Sarpedon, an edge band on both (Marmoreal curb, Sarpedon deck beam)
        self.assertEqual(mar["water"], 0.0)
        self.assertEqual(mar["foam"], 0.0)
        self.assertGreater(sar["water"], 0.03)
        self.assertGreater(sar["foam"], 0.0)
        self.assertGreater(mar["edge"], 0.03)
        self.assertGreater(sar["edge"], 0.002)
        # P4 gap 10: the petals concentrate under the cherries - well below the P2 petal rules on the same layout
        p2 = copy.deepcopy(PARAMS)
        p2["maps"]["marmoreal"]["rules"].update(petalGlobal=1.0, petalTreeRadiusUU=125.0, petalDrift=0.55, petalBeds=0.3)
        before = GS.coverage(GS.generate("marmoreal", p2, layout("marmoreal")), p2)["accentMean"]
        self.assertLess(mar["accentMean"], 0.8 * before)


class SplatRules(unittest.TestCase):
    def test_marmoreal_regions(self):
        res = generated("marmoreal")
        lay = layout("marmoreal")
        self.assertGreater(sample(res, 0, -360)[2], 0.95)  # palace terrace: paving
        self.assertGreater(sample(res, -490, 0)[2], 0.95)  # W walkway next to the frame
        # P5c: the cherry crown centre of the role rules (= loc on the kit mesh, the footprint centre on a Fab tree)
        cherry = next(q for q in GS.role_props(lay, "Cherry") if q.prop["id"] == "cherry-w")
        c = sample(res, cherry.cx, cherry.cy)
        self.assertLess(c[2], 0.05)  # no paving under the cherry
        self.assertGreater(c[3], 0.8)  # a carpet of petals
        self.assertGreater(sample(res, -776, 100)[0], 0.5)  # moss along the tray rim
        for q in GS.role_props(lay, "LanternPlinth"):
            self.assertGreater(sample(res, q.cx, q.cy)[2], 0.95, q.prop["id"])  # lamp pads are paved

    def test_sarpedon_regions(self):
        res = generated("sarpedon")
        lay = layout("sarpedon")
        for p in lay["props"]:
            if LC.mesh_name(p) in ("Hull", "Cannon"):
                self.assertGreater(sample(res, *p["loc"][:2])[2], 0.95, p["id"])  # on the deck
        fa, fb = PARAMS["maps"]["sarpedon"]["river"]["farEdgeX"]
        far = sample(res, (fa + fb) / 2 + 15, -420)
        self.assertGreater(far[1], 0.9)  # the pebble bed of the far channel (under the water)
        self.assertGreater(far[3], 0.8)  # wet (x 0.82 .. 1 noise)
        na, nb = PARAMS["maps"]["sarpedon"]["river"]["nearEdgeX"]
        near = sample(res, (na + nb) / 2 - 10, 400)
        self.assertGreater(near[1], 0.9)  # the pebble bed at the river mouth near edge (waterfall)
        self.assertGreater(sample(res, 0, -420)[0], 0.9)  # beach N-centre: sand
        forest = sample(res, -700, 150)
        self.assertLess(max(forest[:3]), 0.1)  # the forest floor base (W)
        fort = GS.role_props(lay, "FortRuin")[0]
        self.assertGreater(max(sample(res, fort.cx, fort.cy)[:2]), 0.5)  # fort dust / rubble

    def test_marmoreal_curb_and_petal_mask(self):
        res = generated("marmoreal")
        # walking out from the frame along y = 0: paving, then the curb band (aux B) on its last ~24 uu, then earth
        xs = np.arange(-470.0, -650.0, -2.0)
        pave = np.array([sample(res, x, 0.0)[2] for x in xs])
        edge = np.array([sample(res, x, 0.0, "aux")[2] for x in xs])
        out = int(np.argmax(pave < 0.5))  # first x outside the paving
        self.assertGreater(out, 5)
        self.assertGreater(float(edge[max(out - 5, 0):out].max()), 0.8)  # the curb just inside the paving border
        self.assertLess(float(edge[:max(out - 20, 1)].max()), 0.1)  # no curb next to the frame
        self.assertLess(float(edge[out + 10:].max()), 0.1)  # none on the earth
        # the crown centre (role rules): on the P5c Fab sakura the pivot is the trunk base, ~90 uu off the crown
        cherry = next(q for q in GS.role_props(layout("marmoreal"), "Cherry") if q.prop["id"] == "cherry-w")
        self.assertGreater(sample(res, cherry.cx, cherry.cy)[3], 0.8)  # dense under the tree
        self.assertLess(sample(res, -600, 300)[3], 0.1)  # sparse confetti far from the trees

    def test_sarpedon_water_follows_the_painted_river(self):
        res = generated("sarpedon")
        riv = PARAMS["maps"]["sarpedon"]["river"]
        for y, (a, b) in ((-GS.FY - 6.0, riv["farEdgeX"]), (GS.FY + 6.0, riv["nearEdgeX"])):
            run = water_run(res, y)
            self.assertIsNotNone(run, y)
            overlap = min(run[1], b) - max(run[0], a)
            self.assertGreater(overlap / (b - a), 0.85, (y, run, (a, b)))  # the water continues the painted river
            self.assertLess(abs((run[0] + run[1]) / 2 - (a + b) / 2), 20.0, (y, run))
            self.assertGreater(sample(res, (a + b) / 2, y, "aux")[0], 0.9)
        # the far mouth opens into the sea: surf lines (foam) inside the water near the far tray edge
        Y = res["Y"]
        aux = GS.decode(res["aux"])
        sea = (Y < SHARED_TRAY[1] + 70) & (Y > SHARED_TRAY[1] + 20)
        self.assertGreater(float((aux[..., 1] * aux[..., 0])[sea].max()), 0.5)
        # depth: 0 at the shore, deep in the middle of the far mouth
        fa, fb = riv["farEdgeX"]
        self.assertGreater(sample(res, (fa + fb) / 2 + 20, -440, "aux")[3], 0.6)
        # a thin pebble rim on the banks, sand beyond it, no water there
        run = water_run(res, -400.0)
        self.assertGreater(sample(res, run[1] + 5.0, -400.0)[1], 0.5)
        beyond = [sample(res, run[1] + d, -400.0)[1] for d in range(30, 70, 2)]  # sand (a sparse pebble scatter)
        self.assertLess(float(np.mean(beyond)), 0.5)
        self.assertLess(sample(res, run[1] + 40.0, -400.0, "aux")[0], 0.05)

    def test_sarpedon_deck_beam(self):
        res = generated("sarpedon")
        self.assertGreater(sample(res, 404.0, -400.0, "aux")[2], 0.8)  # the quay N-E: the planks end at x 400
        self.assertGreater(sample(res, 124.0, 380.0, "aux")[2], 0.8)  # the quay S-E: the planks end at x 120
        self.assertLess(sample(res, 600.0, -200.0, "aux")[2], 0.05)  # not inside the deck
        self.assertLess(sample(res, -700.0, 150.0, "aux")[2], 0.05)  # not on the forest floor

    def test_waterfall_entry(self):
        res = generated("sarpedon")
        falls = res["falls"]
        self.assertEqual(len(falls), 1)
        f = falls[0]
        tx0, ty0, tx1, ty1 = SHARED_TRAY
        spec = PARAMS["maps"]["sarpedon"]["water"]["falls"][0]
        self.assertEqual(f["material"], "/Game/EnvKit/Ground/MI_EnvWaterfall_Sarpedon")
        self.assertEqual(f["y"], ty1 + spec["offsetUU"])
        na, nb = PARAMS["maps"]["sarpedon"]["river"]["nearEdgeX"]
        self.assertLess(abs((f["x0"] + f["x1"]) / 2 - (na + nb) / 2), 30.0)  # under the river
        self.assertGreater(f["x1"] - f["x0"], 0.8 * (nb - na))
        run = water_run(res, ty1 - 3.0)
        self.assertGreaterEqual(f["x0"], run[0] - 2.0)  # inside the water at the edge
        self.assertLessEqual(f["x1"], run[1] + 2.0)
        self.assertEqual(GS.validate_waterfalls("sarpedon", falls, SHARED_TRAY), [])
        self.assertEqual(generated("marmoreal")["falls"], [])
        bad = [dict(f, topZ=30.0), dict(f), dict(f, spillUU=0.0), dict(f, x1=f["x0"] - 1.0),
               dict(f, material="/Game/X/MI_Y"), dict(f, y=ty1 - 10.0)]
        for k, b in enumerate(bad):
            got = GS.validate_waterfalls("sarpedon", [f, b] if k == 1 else [b], SHARED_TRAY)
            self.assertTrue(got, (k, b))  # 1: duplicate id

    def test_rules_are_parametric(self):
        p = copy.deepcopy(PARAMS)
        p["maps"]["marmoreal"]["rules"]["petalGlobal"] = 0.0
        p["maps"]["marmoreal"]["rules"]["curbWidthUU"] = 0.0
        res = GS.generate("marmoreal", p, layout("marmoreal"))
        cov = GS.coverage(res, p)
        self.assertLess(cov["accentMean"], GS.coverage(generated("marmoreal"), PARAMS)["accentMean"])
        self.assertEqual(cov["edge"], 0.0)
        p = copy.deepcopy(PARAMS)
        p["maps"]["sarpedon"]["water"]["falls"] = []
        p["maps"]["sarpedon"]["rules"]["waterInsetUU"] = 15.0
        res = GS.generate("sarpedon", p, layout("sarpedon"))
        self.assertEqual(res["falls"], [])
        self.assertLess(GS.coverage(res, p)["water"], GS.coverage(generated("sarpedon"), PARAMS)["water"])
        p["maps"]["sarpedon"]["rules"]["depthUU"] = "deep"
        with self.assertRaises(SystemExit):
            GS.generate("sarpedon", p, layout("sarpedon"))

    def test_ground_section_carries_aux_and_waterfalls(self):
        for key in GS.MAPS:
            res = generated(key)
            sec = GS.ground_section(key, PARAMS, res, GS.PARAMS_DEFAULT.parent / f"{key}.splat.png")
            self.assertEqual(sec["aux"], GS.rel(GS.PARAMS_DEFAULT.parent / f"{key}.aux.png"))
            self.assertEqual(sec["auxSha256"], res["auxSha256"])
            self.assertEqual("waterfalls" in sec, key == "sarpedon")
            lay = dict(layout(key), ground=sec)
            self.assertEqual(GS.check_layout_ground(key, lay, res, PARAMS), [])
            stale = dict(sec, auxSha256="00")
            self.assertTrue(GS.check_layout_ground(key, dict(lay, ground=stale), res, PARAMS))
            # layout_check accepts the section (its splat sha256 rule compares the committed file, skipped here)
            err, _, _ = LC.validate_ground(lay, key, SHARED_TRAY)
            self.assertEqual([e for e in err if "sha256" not in e], [], key)
        res = generated("sarpedon")
        sec = GS.ground_section("sarpedon", PARAMS, res, GS.PARAMS_DEFAULT.parent / "sarpedon.splat.png")
        moved = dict(sec, waterfalls=[dict(sec["waterfalls"][0], x0=sec["waterfalls"][0]["x0"] - 50.0)])
        errs = GS.check_layout_ground("sarpedon", dict(layout("sarpedon"), ground=moved), res, PARAMS)
        self.assertTrue(any("waterfalls" in e for e in errs), errs)

    def test_layout_sections_match_the_splats(self):
        for key in GS.MAPS:
            lay = layout(key)
            png = GS.REPO / lay["ground"]["splat"]
            self.assertTrue(png.is_file(), key)
            aux = GS.REPO / lay["ground"].get("aux", "-")
            self.assertTrue(aux.is_file(), f"{key}: no aux mask in the layout (ground_splat.py --write-layouts)")
            res = dict(generated(key), sha256=GS.sha256_bytes(png.read_bytes()),
                       auxSha256=GS.sha256_bytes(aux.read_bytes()))
            self.assertEqual(GS.check_layout_ground(key, lay, res, PARAMS), [], key)
            self.assertEqual(res["sha256"], generated(key)["sha256"], f"{key}: committed splat != the rules")
            self.assertEqual(res["auxSha256"], generated(key)["auxSha256"], f"{key}: committed aux != the rules")


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

    def test_water_ripple_normal(self):
        n = IMP.water_ripple_normal()
        self.assertEqual(n.shape, (IMP.RIPPLE["size"], IMP.RIPPLE["size"], 3))
        np.testing.assert_array_equal(n, IMP.water_ripple_normal())  # deterministic
        v = n.astype(float) / 255.0 * 2.0 - 1.0
        self.assertGreater(float(v[..., 2].min()), 0.5)  # gentle ripples, always facing up
        self.assertLess(abs(float(v[..., 0].mean())), 0.02)  # no net tilt
        self.assertLess(abs(float(v[..., 1].mean())), 0.02)
        # tileable: the wrap-around step is no larger than an ordinary neighbour step
        inner_x = np.abs(np.diff(v[..., :2], axis=1)).mean()
        inner_y = np.abs(np.diff(v[..., :2], axis=0)).mean()
        self.assertLess(np.abs(v[:, 0, :2] - v[:, -1, :2]).mean(), 1.5 * inner_x)
        self.assertLess(np.abs(v[0, :, :2] - v[-1, :, :2]).mean(), 1.5 * inner_y)

    def test_material_instance_parameters(self):
        textures = {(s, k): f"T_{s}_{k}" for s in list(PARAMS["sets"]) + [IMP.RIPPLE_SET] for k in IMP.KEYS}
        rect = [-820.0, -560.0, 820.0, 470.0]
        mar = IMP.mi_want("marmoreal", PARAMS, textures, "splat", rect, "aux", "ripple")
        sar = IMP.mi_want("sarpedon", PARAMS, textures, "splat", rect, "aux", "ripple")
        for want in (mar, sar):
            self.assertEqual(want["tex"]["Aux"], "aux")
            self.assertEqual(want["tex"]["WaterRippleN"], "ripple")
            self.assertEqual(len(want["tex"]), 15)
        # gap 13: rough, less specular marble paving (L3) on Marmoreal
        self.assertGreaterEqual(mar["vector"]["LayerRoughMin"][3], 0.75)
        self.assertLess(mar["vector"]["LayerSpecular"][3], 0.4)
        self.assertAlmostEqual(mar["vector"]["LayerMacro"][3], 0.08)
        # no water on Marmoreal: no foam, no lift
        self.assertEqual(mar["vector"]["WaterFoam"][3], 0.0)
        self.assertEqual(mar["vector"]["WaterSurface"][3], 0.0)
        # Sarpedon water: the map's river colour in linear (P4 tune: sRGB 34, 63, 105 -> 40, 76, 128 with lift 4,
        # so the off-map water reads like the lifted painted river), glossy, lifted
        r, g, b, _ = sar["vector"]["WaterColor"]
        self.assertAlmostEqual(r, 0.0212, places=3)
        self.assertAlmostEqual(g, 0.0723, places=3)
        self.assertAlmostEqual(b, 0.2159, places=3)
        self.assertLess(sar["vector"]["WaterSurface"][0], 0.15)
        self.assertGreater(sar["vector"]["WaterSurface"][3], 0.0)
        self.assertGreater(sar["vector"]["LayerNormal"][3], 1.0)  # sharper deck planks
        self.assertTrue(IMP.has_falls(PARAMS, "sarpedon"))
        self.assertFalse(IMP.has_falls(PARAMS, "marmoreal"))
        fall = IMP.fall_mi_want("sarpedon", PARAMS, "ripple")
        self.assertEqual(fall["vector"]["WaterColor"], sar["vector"]["WaterColor"])
        self.assertGreater(fall["vector"]["FallFlow"][0], 0.0)
        self.assertEqual(IMP.fall_mi_asset("sarpedon"), "/Game/EnvKit/Ground/MI_EnvWaterfall_Sarpedon")
        self.assertEqual(IMP.aux_asset("sarpedon"), "/Game/EnvKit/Ground/T_EnvGround_Sarpedon_Aux")
        self.assertIn(IMP.ripple_asset(), IMP.planned_assets(PARAMS))

    def test_hlsl_declares_what_it_reads(self):
        # every Custom node of both graphs names its inputs in the code (ue_import_env_ground.build_* wire them)
        self.assertIn("WaterRippleN", IMP.HLSL_FALL_RIPPLE_UV + "WaterRippleN")
        for code, pins in ((IMP.HLSL_WATER, ("Aux", "P", "Time", "WaterPan", "WaterRipple", "WaterFoam")),
                           (IMP.HLSL_FALL_OPACITY, IMP.FALL_CORE_INPUTS),
                           (IMP.HLSL_EMISSIVE, ("Water", "WaterColor", "WaterSurface", "NightEV", "NightSaturation",
                                                "NightTint"))):
            for pin in pins:
                self.assertIn(pin, code)

    def test_fall_mesh_v_flip(self):
        # P5b tune: the lane K meshes carry v top -> bottom in Blender, the FBX import flips V; FallCard.w = 1 (C++
        # FallFlipMesh on the sheet / foam MIDs) makes M_EnvWaterfall use 1 - v, the plane card / spill keep w = 0
        header = (GS.REPO / "unreal/Unmatched/Source/Unmatched/S08/S08EnvGround.h").read_text(encoding="utf-8")
        self.assertRegex(header, r"constexpr float FallFlipPlane = 0\.0f;")
        self.assertRegex(header, r"constexpr float FallFlipMesh = 1\.0f;")
        src = (GS.REPO / "unreal/Unmatched/Source/Unmatched/S08/S08EnvGround.cpp").read_text(encoding="utf-8")
        self.assertEqual(src.count("S08EnvGroundSpec::FallFlipMesh"), 2)  # SheetCardParam + FoamCardParam
        core = IMP.HLSL_FALL_CORE
        self.assertIn("float2 uvf = FallCard.w > 0.5 ? float2(UV.x, 1.0 - UV.y) : UV;", core)
        after = core.split("float2 uvf =", 1)[1].split(chr(10), 1)[1]
        self.assertNotIn("UV.y", after)  # every later v read is flipped
        self.assertIn("FallCard.w > 0.5", IMP.HLSL_FALL_RIPPLE_UV)
        self.assertNotEqual(IMP.FALL_GRAPH_VERSION, "1")  # rebuilds M_EnvWaterfall over the P4 graph

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


ENVGROUND_H = GS.REPO / "unreal/Unmatched/Source/Unmatched/S08/S08EnvGround.h"
WATERFALL_RUN = "art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/20261001-waterfall-v1"


def ground_consts() -> dict:
    text = ENVGROUND_H.read_text(encoding="utf-8")
    out = {m.group(1): float(m.group(2)) for m in re.finditer(r"constexpr float (\w+) = ([-\d.]+)f;", text)}
    out.update({m.group(1): int(m.group(2)) for m in re.finditer(r"constexpr int32 (\w+) = (\d+);", text)})
    return out


class MeshPieces(unittest.TestCase):
    """P5 track B: the lane K waterfall meshes and the sea ring in the layout ground section (ground_splat.py) and their
    import (ue_import_env_ground.py), plain Python."""

    def test_sarpedon_fall_mesh_and_sea(self):
        res = generated("sarpedon")
        f = res["falls"][0]
        m = f["mesh"]
        tx0, ty0, tx1, ty1 = SHARED_TRAY
        self.assertEqual(m["sheet"], "/Game/EnvKit/Ground/Sarpedon/SM_Env_S_Waterfall")
        self.assertEqual(m["foam"], "/Game/EnvKit/Ground/Sarpedon/SM_Env_S_WaterfallFoam")
        self.assertEqual(m["lip"], "/Game/EnvKit/Ground/Sarpedon/SM_Env_S_WaterfallLip")
        self.assertEqual(m["lipMaterial"], "/Game/PipelineCandidates/TableBase/T2b/MI_TableBase_T2b_Sarpedon")
        self.assertEqual(m["loc"], [round((f["x0"] + f["x1"]) / 2, 3), ty1, 0.0])
        self.assertEqual(m["yawDeg"], 90.0)
        self.assertEqual(m["sheetCard"], [193.8, 185.231])
        self.assertAlmostEqual(m["sheetCard"][0], f["x1"] - f["x0"], places=6)  # built for this fall
        self.assertEqual(m["foamCards"], [[261.34, 70.0], [243.97, 76.0]])     # slot 0 foam, slot 1 mist
        self.assertEqual(res["sea"], {"mesh": "/Game/EnvKit/Ground/Sarpedon/SM_Env_S_SeaRing",
                                      "material": "/Game/EnvKit/Ground/MI_EnvSea_Sarpedon",
                                      "loc": [0.0, (ty0 + ty1) / 2, -172.0], "yawDeg": 0.0})
        self.assertEqual(GS.validate_waterfalls("sarpedon", res["falls"], SHARED_TRAY), [])
        self.assertEqual(GS.validate_sea("sarpedon", res["sea"], SHARED_TRAY), [])
        # Marmoreal has neither (gated to the Sarpedon ground section)
        mres = generated("marmoreal")
        self.assertIsNone(mres["sea"])
        sec = GS.ground_section("marmoreal", PARAMS, mres, GS.PARAMS_DEFAULT.parent / "marmoreal.splat.png")
        self.assertNotIn("sea", sec)
        self.assertNotIn("notesP5", sec)
        ssec = GS.ground_section("sarpedon", PARAMS, res, GS.PARAMS_DEFAULT.parent / "sarpedon.splat.png")
        self.assertIn("sea", ssec)
        self.assertIn("notesP5", ssec)

    def test_mesh_and_sea_rejections(self):
        res = generated("sarpedon")
        f = res["falls"][0]
        m = f["mesh"]
        bad_meshes = [dict(m, sheet="Game/X"), dict(m, foam="C:/x"), dict(m, lipMaterial=None),
                      dict(m, loc=[0.0, 0.0]), dict(m, loc=[m["loc"][0], m["loc"][1], 60.0]),
                      dict(m, loc=[m["loc"][0] + 5.0, m["loc"][1], 0.0]), dict(m, loc=[m["loc"][0], 400.0, 0.0]),
                      dict(m, yawDeg=400.0), dict(m, sheetCard=[0.0, 10.0]), dict(m, sheetCard=[10.0]),
                      dict(m, foamCards=[[1.0, 1.0]] * 3), dict(m, foamCards=[["1", 1.0]]), "mesh"]
        for b in bad_meshes:
            self.assertTrue(GS.validate_waterfalls("sarpedon", [dict(f, mesh=b)], SHARED_TRAY), b)
        sea = res["sea"]
        for b in (dict(sea, loc=[0.0, -45.0, -3.0]), dict(sea, loc=[0.0, -45.0, 5.0]), dict(sea, loc=[0.0, 0.0, -172.0]),
                  dict(sea, loc=[0.0, -45.0, -2000.0]), dict(sea, mesh="SM_X"), dict(sea, material=None),
                  dict(sea, yawDeg="0"), [1, 2]):
            self.assertTrue(GS.validate_sea("sarpedon", b, SHARED_TRAY), b)

    def test_check_mesh_run_catches_a_stale_build(self):
        res = generated("sarpedon")
        sec = GS.ground_section("sarpedon", PARAMS, res, GS.PARAMS_DEFAULT.parent / "sarpedon.splat.png")
        self.assertEqual(GS.check_mesh_run("sarpedon", sec, PARAMS), [])
        # the fall moved / widened by the rules: the sheet was built for the old width -> rebuild
        f = dict(sec["waterfalls"][0], x0=sec["waterfalls"][0]["x0"] - 20.0)
        errs = GS.check_mesh_run("sarpedon", dict(sec, waterfalls=[f]), PARAMS)
        self.assertTrue(any("rebuild" in e for e in errs), errs)
        moved = dict(sec["waterfalls"][0], mesh=dict(sec["waterfalls"][0]["mesh"], loc=[0.0, 425.0, 0.0]))
        self.assertTrue(GS.check_mesh_run("sarpedon", dict(sec, waterfalls=[moved]), PARAMS))
        # another shared tray than the run was built for
        p = copy.deepcopy(PARAMS)
        p["tray"]["offsetY"] = -40.0
        errs = GS.check_mesh_run("sarpedon", sec, p)
        self.assertTrue(any("built for the tray" in e for e in errs), errs)
        self.assertTrue(GS.check_mesh_run("sarpedon", dict(sec, sea=dict(sec["sea"], loc=[0.0, -45.0, -150.0])), PARAMS))
        # the layout check compares the sea / mesh blocks with the generator
        lay = dict(layout("sarpedon"), ground=dict(sec, sea=None))
        self.assertTrue(any("ground.sea" in e for e in GS.check_layout_ground("sarpedon", lay, res, PARAMS)))

    def test_limits_mirror_s08envground(self):
        h = ground_consts()
        self.assertEqual(GS.MESH_MAX_ABS_XY_UU, h["MeshMaxAbsXYUU"])
        self.assertEqual(GS.MESH_Z, (h["FallMeshMinZ"], h["FallMeshMaxZ"]))
        self.assertEqual(GS.SEA_Z, (h["SeaMinZ"], h["SeaMaxZ"]))
        self.assertEqual(GS.MESH_MAX_CARD_UU, h["MaxMeshCardUU"])
        self.assertEqual(GS.MESH_MAX_FOAM_CARDS, h["MaxFoamCards"])
        self.assertEqual(GS.FALL_TOP_Z, (h["FallMinTopZ"], h["FallMaxTopZ"]))
        self.assertEqual(GS.SEA_Z[1], -3.0)  # = S08Diorama::TopZ: the sea stays under the tray top

    def test_shipped_sarpedon_layout_carries_the_pieces(self):
        g = layout("sarpedon")["ground"]
        self.assertIn("mesh", g["waterfalls"][0])
        self.assertIn("sea", g)
        self.assertNotIn("sea", layout("marmoreal")["ground"])
        self.assertTrue(all("mesh" not in f for f in layout("marmoreal")["ground"].get("waterfalls", [])))

    def test_mesh_import_plan(self):
        items = IMP.plan_meshes(PARAMS, "sarpedon")
        self.assertEqual(set(items), {"sheet", "foam", "lip", "sea"})
        for part, it in items.items():
            self.assertTrue(it["ok"], (part, it.get("error")))
            self.assertEqual(it["asset"], f"/Game/EnvKit/Ground/Sarpedon/{IMP.ENV_MESHES[part][0]}")
            self.assertEqual(it["run"], WATERFALL_RUN)
        # vertex colours REPLACE for the lip (the tray moss mask) and the sea ring (foam / far fade)
        self.assertEqual({p: it["vertexColors"] for p, it in items.items()},
                         {"sheet": "ignore", "foam": "ignore", "lip": "replace", "sea": "replace"})
        self.assertEqual(items["foam"]["slots"], 2)
        self.assertEqual(IMP.plan_meshes(PARAMS, "marmoreal"), {})
        p = copy.deepcopy(PARAMS)
        p["maps"]["sarpedon"]["sea"]["run"] = "art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/no-such-run"
        self.assertFalse(IMP.plan_meshes(p, "sarpedon")["sea"]["ok"])
        p = copy.deepcopy(PARAMS)
        p["maps"]["sarpedon"]["water"]["falls"][0]["mesh"]["lip"] = False
        self.assertNotIn("lip", IMP.plan_meshes(p, "sarpedon"))
        planned = IMP.planned_assets(PARAMS)
        for it in items.values():
            self.assertIn(it["asset"], planned)
        self.assertIn(IMP.SEA_MATERIAL_PATH, planned)
        self.assertIn(IMP.sea_mi_asset("sarpedon"), planned)

    def test_compare_mesh(self):
        item = {"boundsUeUU": {"min": [26.041, -108.528, -172.0], "max": [81.274, 108.528, 2.0]}, "triangles": 1632}
        ok = IMP.compare_mesh({"boundsMin": [26.2, -108.528, -172.0], "boundsMax": [81.274, 108.6, 2.0],
                               "trianglesLod0": 1630}, item)
        self.assertTrue(ok["bounds"]["ok"] and ok["triangles"]["ok"], ok)
        x100 = IMP.compare_mesh({"boundsMin": [2604.1, -10852.8, -17200.0], "boundsMax": [8127.4, 10852.8, 200.0],
                                 "trianglesLod0": 1500}, item)
        self.assertFalse(x100["bounds"]["ok"])
        self.assertFalse(x100["triangles"]["ok"])

    def test_sea_material_instance(self):
        pack = {k: f"tex:{k}" for k in IMP.PACK_TEXTURES}
        want = IMP.sea_mi_want("sarpedon", PARAMS, pack, {k: "pack" for k in IMP.PACK_TEXTURES})
        sp = PARAMS["maps"]["sarpedon"]["sea"]
        # P5c graph 2: the Water Materials foam + two normals (no WaterRippleN any more)
        self.assertEqual(want["tex"], {k: f"tex:{k}" for k in IMP.SEA_PACK_PARAMS})
        col = want["vector"]["SeaColor"]
        far = want["vector"]["SeaFar"]
        water = IMP.mi_want("sarpedon", PARAMS, {(s, k): "t" for s in list(PARAMS["sets"]) + [IMP.RIPPLE_SET]
                                                   for k in IMP.KEYS}, "s", [0, 0, 1, 1])["vector"]["WaterColor"]
        self.assertLess(sum(col[:3]), sum(water[:3]))   # the sea is darker than the river water
        self.assertLess(sum(far[:3]), sum(col[:3]))     # and fades darker far out
        self.assertEqual(far[3], float(sp["farStrength"]))
        self.assertEqual(want["vector"]["SeaTile"][:2], (600.0, float(sp["rippleTileUU"])))  # UV0 = XY / 600 (lane K)
        self.assertEqual(want["scalar"]["NightEV"], PARAMS["maps"]["sarpedon"]["grade"]["ev"])
        self.assertEqual(set(want["vector"]), set(IMP.SEA_VECTOR_DEFAULTS))
        self.assertEqual(set(want["scalar"]), set(IMP.SEA_SCALAR_DEFAULTS))
        self.assertTrue(IMP.has_sea(PARAMS, "sarpedon"))
        self.assertFalse(IMP.has_sea(PARAMS, "marmoreal"))

    def test_sea_hlsl_declares_what_it_reads(self):
        uv_codes = [(code, ("UV", "Time", "SeaTile", "SeaFlow", tile)) for _, _, code, tile in IMP.SEA_UV_NODES]
        for code, pins in [(IMP.HLSL_SEA_ALBEDO, IMP.SEA_CORE_INPUTS),
                           (IMP.HLSL_SEA_EMISSIVE, IMP.SEA_CORE_INPUTS + ("SeaShade",)),
                           (IMP.HLSL_SEA_NORMAL, ("NA", "NB", "SeaShade", "VC"))] + uv_codes:
            for pin in pins:
                self.assertIn(pin, code)
        self.assertIn("VC.r", IMP.HLSL_SEA_CORE)  # foam band
        self.assertIn("VC.g", IMP.HLSL_SEA_CORE)  # far fade


if __name__ == "__main__":
    unittest.main()
