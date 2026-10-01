"""ENV-MAPS P5c track W tests (plain Python): the role-based region rules of tools/art/env_kit/ground_splat.py (a Fab mesh
swap keeps petals / pads / fire clearings; unchanged layouts give byte-identical splats), M_EnvSea graph 2 (Water
Materials textures, surf, waves, sky lift; CPU mirror) and M_EnvWaterfall graph 3 (translucent, pack streaks) of
tools/art/env_kit/ue_import_env_ground.py, the Custom-node HLSL compiled with DXC (tools/art/env_kit/hlsl_check.py; skips
without the Windows SDK) and the Sarpedon tray moss of ground-params.json (tools/art/env_kit/ue_import_tray_t2.py).

  python -m pytest tools/art/tests/test_env_ground_p5c.py -q
"""
from __future__ import annotations

import copy
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ENV_KIT = HERE.parents[0] / "env_kit"
sys.path.insert(0, str(ENV_KIT))

import ground_splat as GS  # noqa: E402
import hlsl_check as HC  # noqa: E402
import layout_check as LC  # noqa: E402
import ue_import_env_ground as IMP  # noqa: E402
import ue_import_tray_t2 as T2  # noqa: E402

PARAMS = GS.load_params(GS.PARAMS_DEFAULT)
FAB_PINK = "/Game/EnvKit/Fab/Marmoreal/SM_Env_Tree_Large_Twisted_Pink"
P5B_TRAY_LOOK = {  # the P5b values the P5c moss change must leave alone on Marmoreal
    "marmoreal": {"MossTint": [0.62, 0.72, 0.45], "MossAmount": 1.1, "DepthTint": [0.5, 0.5, 0.56, 0.6],
                  "PetalColor": [0.87, 0.4, 0.51, 0.35]}}


def layout(key: str) -> dict:
    return json.loads((GS.LAYOUT_DIR / f"{key}.layout.json").read_text(encoding="utf-8"))


def sample(res: dict, x: float, y: float) -> np.ndarray:
    x0, y0, x1, y1 = res["rect"]
    w, h = res["size"]
    i = min(max(int((x - x0) / (x1 - x0) * w), 0), w - 1)
    j = min(max(int((y - y0) / (y1 - y0) * h), 0), h - 1)
    return GS.decode(res["array"][j:j + 1, i:i + 1])[0, 0]


# ------------------------------------------------------------------------------------------------ role rules
class RoleRules(unittest.TestCase):
    def test_kit_meshes_keep_the_old_numbers(self):
        # a prop on its role's kit mesh: centre = loc, scale = scale (the P2..P5b rule), whatever its id
        for key in GS.MAPS:
            lay = layout(key)
            for role in GS.ROLES:
                for q in GS.role_props(lay, role):
                    if LC.mesh_name(q.prop) == role:
                        self.assertEqual((q.cx, q.cy, q.s), (q.prop["loc"][0], q.prop["loc"][1], q.prop["scale"]))
                        self.assertIsNone(q.poly)
            kit = [p for p in lay["props"] if LC.mesh_name(p) in GS.ROLES]
            for p in kit:  # every kit-mesh role prop is matched to its own role
                self.assertEqual(GS.prop_role(p)[0], LC.mesh_name(p), p["id"])

    def test_unchanged_inputs_give_identical_splats(self):
        # the role rules reproduce the committed P5b splats byte for byte while the layout props are the ones the
        # splats were made from (Track F's prop swap changes the hash: then ground_splat.py --write-layouts reruns)
        for key in GS.MAPS:
            meta = json.loads((GS.PARAMS_DEFAULT.parent / f"{key}.splat.json").read_text(encoding="utf-8"))
            lay = layout(key)
            if GS.props_hash(lay) != meta["layout"]["propsSha256"]:
                self.skipTest(f"{key}: layout props changed after the splat (re-run ground_splat.py)")
            res = GS.generate(key, PARAMS, lay)
            self.assertEqual(res["sha256"], meta["png"]["sha256"], key)
            self.assertEqual(res["auxSha256"], meta["aux"]["sha256"], key)
            # role notes only where a role prop has left its kit mesh (P5c: the Marmoreal cherries on the Fab sakura)
            self.assertEqual(res["roleNotes"], meta.get("roles", []), key)

    def test_role_field_and_id_prefix(self):
        self.assertEqual(GS.prop_role({"id": "sakura-1", "role": "Cherry", "mesh": FAB_PINK})[0], "Cherry")
        self.assertEqual(GS.prop_role({"id": "x", "role": "cherry", "mesh": FAB_PINK}), ("Cherry", "role"))
        self.assertEqual(GS.prop_role({"id": "cherry-w", "mesh": FAB_PINK}), ("Cherry", "id"))
        self.assertEqual(GS.prop_role({"id": "lamp-ne", "mesh": "/Game/EnvKit/Fab/Marmoreal/SM_Foo"}),
                         ("LanternPlinth", "id"))
        # decor next to a role prop, other props and an explicit non-role keep no rules role
        for p in ({"id": "fort-nw-vine", "mesh": "/Game/EnvKit/Fab/Sarpedon/Sm_Lines_14"},
                  {"id": "tree-w", "mesh": "/Game/EnvKit/Sarpedon/SM_Env_Tree"},
                  {"id": "cherry-w", "role": "vine", "mesh": FAB_PINK}):
            self.assertEqual(GS.prop_role(p)[0], "", p)
        # the kit mesh wins over the id (P2..P5b)
        self.assertEqual(GS.prop_role({"id": "odd-1", "mesh": "/Game/EnvKit/Marmoreal/SM_Env_Cherry"}),
                         ("Cherry", "mesh"))

    def _fab_cherry(self, lay: dict, pid: str, mesh: str = FAB_PINK, scale: float = 0.17, yaw: float = 270.0):
        """Track F's swap (Scout picks): the Forest tree at the old cherry point - pivot shifted so the crown (bounds
        centre ~ +0.45 x 1134 uu x scale along the yawed +X) sits where the old crown was."""
        p = next(q for q in lay["props"] if q["id"] == pid)
        old = (p["loc"][0], p["loc"][1])
        b = GS.FAB_BOUNDS["SM_Env_Tree_Large_Twisted_Pink"]
        cx_l, cy_l = (b[0][0] + b[1][0]) / 2 * scale, (b[0][1] + b[1][1]) / 2 * scale
        a = math.radians(yaw)
        off = (cx_l * math.cos(a) - cy_l * math.sin(a), cx_l * math.sin(a) + cy_l * math.cos(a))
        p.update(mesh=mesh, scale=scale, yawDeg=yaw, loc=[old[0] - off[0], old[1] - off[1], p["loc"][2]])
        return old

    def test_fab_cherry_keeps_the_petals(self):
        lay = layout("marmoreal")
        if not any(LC.mesh_name(p) == "Cherry" for p in lay["props"]):
            self.skipTest("the shipped Marmoreal layout has no kit cherries any more (Track F swapped them)")
        base = GS.generate("marmoreal", PARAMS, lay)
        fab = copy.deepcopy(lay)
        old = self._fab_cherry(fab, "cherry-w")
        res = GS.generate("marmoreal", PARAMS, fab)
        q = next(q for q in GS.role_props(fab, "Cherry") if q.prop["id"] == "cherry-w")
        self.assertEqual(q.how, "id")
        self.assertLess(math.hypot(q.cx - old[0], q.cy - old[1]), 1.0)  # the crown centre, not the trunk pivot
        self.assertGreater(q.s, 0.5)  # normalised to SM_Env_Cherry, not the raw 0.17
        self.assertLess(q.s, 1.4)
        a_old, a_new = sample(base, *old)[3], sample(res, *old)[3]
        self.assertGreater(a_new, 0.8)  # still a carpet of petals under the crown
        self.assertGreater(a_new, 0.85 * a_old)
        self.assertLess(sample(res, *old)[2], 0.05)  # no paving under it
        self.assertTrue(any("cherry-w" in n for n in res["roleNotes"]))
        # with the pivot alone (the old rule) the petals would sit ~87 uu off the crown
        self.assertGreater(math.hypot(q.prop["loc"][0] - old[0], q.prop["loc"][1] - old[1]), 60.0)

    def test_track_f_duplicate_names(self):
        # Track F's duplicates /Game/EnvKit/Fab/<Kit>/SM_EnvFab_<Name>: the same crown centre from layout_check (when it
        # knows the pick) or from FAB_BOUNDS
        lay = layout("marmoreal")
        if not any(p["id"] == "cherry-w" for p in lay["props"]):
            self.skipTest("no cherry-w in the shipped layout")
        for mesh in ("/Game/EnvKit/Fab/Marmoreal/SM_EnvFab_SakuraTwisted", FAB_PINK):
            fab = copy.deepcopy(lay)
            p = next(q for q in fab["props"] if q["id"] == "cherry-w")
            if LC.mesh_name(p) != "Cherry":
                self.skipTest("cherry-w is not on the kit mesh any more")
            old = self._fab_cherry(fab, "cherry-w", mesh=mesh)
            q = next(q for q in GS.role_props(fab, "Cherry") if q.prop["id"] == "cherry-w")
            self.assertLess(math.hypot(q.cx - old[0], q.cy - old[1]), 1.0, mesh)
            self.assertIsNotNone(q.poly, mesh)

    def test_unknown_mesh_falls_back_with_a_note(self):
        lay = layout("marmoreal")
        fab = copy.deepcopy(lay)
        p = next(q for q in fab["props"] if q["id"] == "cherry-e")
        p.update(mesh="/Game/EnvKit/Fab/Marmoreal/SM_Unknown_Tree", scale=0.2)
        notes: list[str] = []
        q = next(q for q in GS.role_props(fab, "Cherry", notes) if q.prop["id"] == "cherry-e")
        self.assertEqual((q.cx, q.cy, q.s), (p["loc"][0], p["loc"][1], 1.0))
        self.assertTrue(any("unknown mesh footprint" in n for n in notes))
        p["groundScale"] = 1.3
        p["groundCentre"] = [500.0, 10.0]
        q = next(q for q in GS.role_props(fab, "Cherry") if q.prop["id"] == "cherry-e")
        self.assertEqual((q.cx, q.cy, q.s), (500.0, 10.0, 1.3))
        # a polygon role on an unknown mesh: the kit mesh stands in at the prop
        u = copy.deepcopy(lay)
        urn = next(q for q in u["props"] if q["id"] == "urn-w")
        urn["mesh"] = "/Game/EnvKit/Fab/Marmoreal/Sm_Flower_021"
        rq = next(q for q in GS.role_props(u, "Urn") if q.prop["id"] == "urn-w")
        poly = GS.role_poly(rq, "Urn")
        self.assertEqual(poly.shape, (4, 2))
        self.assertLess(np.abs(poly.mean(axis=0) - np.array(urn["loc"][:2])).max(), 1e-6)


# ------------------------------------------------------------------------------------------------ sea graph 2
def sea_profile():
    """A radial strip of the ring at the near cliffs: d = distance from the inner ring edge (lane K col())."""
    xs = np.linspace(-600, 600, 601)
    ds = np.linspace(0, 3500, 876)
    X, D = np.meshgrid(xs, ds)
    PY = 385.0 + D
    f = np.clip(1 - D / 120.0, 0, 1)
    return xs, ds, X, D, PY, f * f * (3 - 2 * f), np.clip((D - 200.0) / 3300.0, 0, 1)


class SeaGraph2(unittest.TestCase):
    def setUp(self):
        self.xs, self.ds, self.X, self.D, self.PY, self.VCR, self.VCG = sea_profile()
        self.want = IMP.sea_mi_want("sarpedon", PARAMS)
        self.lace = IMP._np_sstep(0.3, 0.7, IMP._np_value_noise(self.X / 18.0, self.PY / 18.0))

    def band(self, a, d0, d1):
        return a[(self.ds >= d0) & (self.ds < d1)]

    def test_material_defaults_keep_the_graph1_look(self):
        p = copy.deepcopy(PARAMS)
        p["maps"]["sarpedon"]["sea"] = {"colorSrgb": [20, 44, 74], "lift": 3.0}  # no P5c keys
        want = IMP.sea_mi_want("sarpedon", p)
        self.assertEqual(want["vector"]["SeaPack"][0], 0.0)
        self.assertEqual(want["vector"]["SeaSurfLook"][3], 3.0)  # the foam lift follows the water lift
        g1 = IMP.sea_graph1_cpu(want, self.X, self.PY, self.VCR, self.VCG, t=1.5)
        g2 = IMP.sea_cpu(want, self.X, self.PY, self.D, self.VCR, self.VCG, t=1.5)
        np.testing.assert_allclose(g2["foam"], g1["foam"], atol=1e-12)
        np.testing.assert_allclose(g2["emissive"], g1["emissive"], atol=1e-12)
        np.testing.assert_allclose(g2["albedo"], g1["albedo"], atol=1e-12)
        # and the material defaults themselves: no surf / whitecaps / wave shade / sky
        d = IMP.SEA_VECTOR_DEFAULTS
        self.assertEqual((d["SeaSurfLook"][1], d["SeaWave"][0], d["SeaWave"][1], d["SeaSky"][3]), (0.0, 0.0, 0.0, 0.0))
        self.assertEqual(d["SeaPack"][2:], (2.0, 0.3))

    def test_sarpedon_shore_foam_is_sharper_and_whiter(self):
        # (the P5b MI: graph 1 with the P5b foam colour / opacity)
        p5b = dict(self.want, vector=dict(self.want["vector"], SeaFoam=(0.62, 0.66, 0.7, 0.7)))
        old = IMP.sea_graph1_cpu(p5b, self.X, self.PY, self.VCR, self.VCG, t=2.0)
        new = IMP.sea_cpu(self.want, self.X, self.PY, self.D, self.VCR, self.VCG, t=2.0, lace_tex=self.lace)
        fo, fn = self.band(old["foam"], 40, 80), self.band(new["foam"], 40, 80)
        grey_old = float(((fo > 0.2) & (fo < 0.8)).mean())
        grey_new = float(((fn > 0.2) & (fn < 0.8)).mean())
        self.assertGreater(grey_old, 0.5)          # the P5b band: mostly half-transparent grey
        self.assertLess(grey_new, 0.75 * grey_old)  # sharper
        self.assertGreater(float((fn > 0.8).mean()), 0.3)  # solid white lace at the cliff foot
        c = self.want["vector"]["SeaFoam"]
        self.assertGreater(min(c[:3]), 0.8)  # whiter foam colour (P5b 0.62..0.7)
        self.assertGreaterEqual(c[3], 0.9)

    def test_surf_runs_in_towards_the_cliffs(self):
        d = np.arange(0.0, 220.0, 0.5)[:, None]  # one radial line, 0.5 uu steps
        f = np.clip(1 - d / 120.0, 0, 1)
        args = (np.zeros_like(d), 385.0 + d, d, f * f * (3 - 2 * f), np.zeros_like(d))
        spacing, reach = self.want["vector"]["SeaSurf"][0], self.want["vector"]["SeaSurf"][2]

        def crests(t):
            s = IMP.sea_cpu(self.want, *args, t=t, lace_tex=np.ones_like(d))["surf"][:, 0]
            return [float(d[i, 0]) for i in range(1, len(s) - 1) if s[i] > s[i - 1] and s[i] >= s[i + 1] and s[i] > 0.2]
        a, b = crests(2.0), crests(4.0)
        self.assertGreaterEqual(len([c for c in a if c > 60]), 2)  # >= 2 crest lines beyond the cliff foot
        self.assertLessEqual(max(a), reach)  # within the reach
        # every crest moves shorewards (smaller d) by cycles/s x spacing x 2 s
        step = self.want["vector"]["SeaSurf"][1] * spacing * 2.0
        for c in a[1:]:
            self.assertTrue(any(abs((c - x) - step) < 1.5 for x in b), (c, a, b, step))

    def test_sky_lift_and_texture_stay_bounded(self):
        old_want = IMP.sea_mi_want("sarpedon", PARAMS)
        old_want["vector"]["SeaShade"] = old_want["vector"]["SeaShade"][:3] + (3.0,)
        old = IMP.sea_graph1_cpu(old_want, self.X, self.PY, self.VCR, self.VCG, t=2.0)
        gx = IMP._np_value_noise(self.X / 60.0 + 1.1, self.PY / 60.0) - 0.5
        gy = IMP._np_value_noise(self.X / 60.0 + 7.7, self.PY / 60.0 + 3.3) - 0.5
        new = IMP.sea_cpu(self.want, self.X, self.PY, self.D, self.VCR, self.VCG, t=2.0, lace_tex=self.lace,
                          slope=(0.6 * gx, 0.6 * gy))
        lum = np.array([0.2126, 0.7152, 0.0722])
        eo, en = old["emissive"] @ lum, new["emissive"] @ lum
        r = float(self.band(en, 200, 600).mean() / self.band(eo, 200, 600).mean())
        # the background band round the tray (0.65x: open sea 200..600 uu out): lifted, but not past the P4 level
        # (P5b 12.3 -> P4 25.5 luma would be ~5x in linear light)
        self.assertGreater(r, 1.8)
        self.assertLess(r, 4.0)
        self.assertGreater(float(self.band(en, 200, 600).std()), 5 * float(self.band(eo, 200, 600).std()))  # texture
        self.assertGreater(float(self.band(en, 2000, 3500).mean()), 2 * float(self.band(eo, 2000, 3500).mean()))

    def test_pack_weight(self):
        sp = PARAMS["maps"]["sarpedon"]["sea"]
        self.assertTrue(sp["pack"])
        ok = {k: "pack" for k in IMP.PACK_TEXTURES}
        self.assertEqual(IMP.sea_mi_want("sarpedon", PARAMS, None, ok)["vector"]["SeaPack"][0], 1.0)
        fb = dict(ok, SeaNormalB="fallback")
        self.assertEqual(IMP.sea_mi_want("sarpedon", PARAMS, None, fb)["vector"]["SeaPack"][0], 0.0)
        p = copy.deepcopy(PARAMS)
        p["maps"]["sarpedon"]["sea"]["pack"] = False
        self.assertEqual(IMP.sea_mi_want("sarpedon", p, None, ok)["vector"]["SeaPack"][0], 0.0)
        plan = IMP.pack_plan()
        self.assertEqual(set(plan), set(IMP.PACK_TEXTURES))
        for param, it in plan.items():
            self.assertTrue(it["asset"].startswith("/Game/WaterMaterials/Textures/"), param)
        if not IMP.PACK_CONTENT_DIR.is_dir():
            self.skipTest("Water Materials pack not in this checkout's Content (gitignored)")
        self.assertTrue(all(it["present"] for it in plan.values()), plan)

    def test_surf_distance_matches_the_lane_k_ring(self):
        # UV1.y = distance from the inner ring edge / uv1_dist_uu (waterfall_build.build_sea), V flipped by the FBX
        # import -> SeaSurf.w = 1 and d = (1 - UV1.y) * 1000 in the HLSL
        wp = json.loads((GS.REPO / "art/pipeline-candidates/ASSET-ENV-S-WATERFALL-001/20261001-waterfall-v1/reports/"
                                   "waterfall-params.json").read_text(encoding="utf-8"))
        self.assertEqual(float(wp["sea"]["uv1_dist_uu"]), 1000.0)
        self.assertIn("(SeaSurf.w > 0.5 ? 1.0 - UV1.y : UV1.y) * 1000.0", IMP.HLSL_SEA_CORE)
        self.assertEqual(self.want["vector"]["SeaSurf"][3], 1.0)
        self.assertEqual(float(wp["sea"]["foam_band_uu"]), 120.0)  # the VC.r band the shore foam reads

    def test_sea_graph_is_opaque_and_versioned(self):
        self.assertEqual(IMP.SEA_GRAPH_VERSION, "2")
        self.assertIn("BLEND_OPAQUE", Path(IMP.__file__).read_text(encoding="utf-8").split("def build_sea_material")[1]
                      .split("def ")[0])
        for name in ("SeaFoamTex", "SeaNormalA", "SeaNormalB"):
            self.assertIn(name, [param for _, param, _, _ in IMP.SEA_UV_NODES])


# ------------------------------------------------------------------------------------------------ waterfall graph 3
class FallGraph3(unittest.TestCase):
    def test_fall_look(self):
        want = IMP.fall_mi_want("sarpedon", PARAMS)
        look = PARAMS["maps"]["sarpedon"]["water"]["falls"][0]["look"]
        self.assertEqual(want["blend"], "translucent")
        fl = want["vector"]["FallLook"]
        self.assertEqual(fl, (look["bodyOpacity"], look["foamOpacity"], look["edgeWobble"], 1.0))
        self.assertLess(fl[0], fl[1])  # a clear-ish body, opaque foam
        self.assertEqual(want["vector"]["FallTex"][:2], tuple(look["packTileUU"]))
        self.assertEqual(IMP.fall_mi_want("sarpedon", PARAMS, "r", "s", "fallback")["vector"]["FallLook"][3], 0.0)
        self.assertEqual(IMP.fall_mi_want("sarpedon", PARAMS, "r", "s", "pack")["tex"],
                         {"WaterRippleN": "r", "FallStreakTex": "s"})
        p = copy.deepcopy(PARAMS)
        p["maps"]["sarpedon"]["water"]["falls"][0]["look"]["blend"] = "masked"
        self.assertEqual(IMP.fall_mi_want("sarpedon", p)["blend"], "masked")
        p["maps"]["sarpedon"]["water"]["falls"][0]["look"]["blend"] = "additive"
        with self.assertRaises(ValueError):
            IMP.fall_mi_want("sarpedon", p)
        self.assertEqual(IMP.fall_mi_want("marmoreal", PARAMS)["vector"]["FallLook"][3], 0.0)  # no falls there

    def test_fall_hlsl(self):
        self.assertEqual(IMP.FALL_GRAPH_VERSION, "3")
        self.assertTrue(IMP.HLSL_FALL_OPACITY.rstrip().endswith("return alphaT;"))
        self.assertIn("alphaM + (ign - 0.5) * FallSpill.y", IMP.HLSL_FALL_OPACITY_MASK)  # the graph 2 masked look
        for code in (IMP.HLSL_FALL_STREAK_UV1, IMP.HLSL_FALL_STREAK_UV2, IMP.HLSL_FALL_RIPPLE_UV):
            self.assertIn("FallCard.w > 0.5 ? float2(UV.x, 1.0 - UV.y) : UV", code)  # the lane K v flip everywhere
        after = IMP.HLSL_FALL_CORE.split("float2 uvf =", 1)[1].split("\n", 1)[1]
        self.assertNotIn("UV.y", after)
        self.assertIn("FallLook.z", IMP.HLSL_FALL_CORE)  # the wobbling side fades
        self.assertEqual(PARAMS["maps"]["sarpedon"]["water"]["falls"][0]["look"]["blend"], "translucent")


class HlslCompile(unittest.TestCase):
    def test_custom_nodes_compile_with_dxc(self):
        dxc = HC.find_dxc()
        if not dxc:
            self.skipTest("no dxc (Windows SDK) on this machine")
        for label, nodes in (("M_EnvSea", HC.sea_nodes()), ("M_EnvWaterfall", HC.fall_nodes()),
                             ("M_MapBackdropMoon", HC.moon_nodes())):
            r = HC.compile_nodes(nodes, dxc)
            self.assertEqual(r["status"], "ok", f"{label}: {r.get('log')}")
        broken = HC.sea_nodes()
        name, dim, pins, code = broken[0]
        broken[0] = (name, dim, pins, code.replace("nearW", "nearWW", 1))
        self.assertEqual(HC.compile_nodes(broken, dxc)["status"], "failed")  # the harness does catch errors


# ------------------------------------------------------------------------------------------------ tray moss
class TrayMoss(unittest.TestCase):
    def test_sarpedon_moss_patches_marmoreal_unchanged(self):
        for name, value in P5B_TRAY_LOOK["marmoreal"].items():
            self.assertEqual(PARAMS["maps"]["marmoreal"]["trayLook"][name], value, name)
        marm, sarp = T2.tray_look(PARAMS, "marmoreal"), T2.tray_look(PARAMS, "sarpedon")
        self.assertLessEqual(sarp["MossAmount"], 0.45)
        self.assertGreaterEqual(sarp["MossAmount"], 0.25)
        luma = lambda c: 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]  # noqa: E731
        self.assertLess(luma(sarp["MossTint"]), 0.6 * luma(marm["MossTint"]))  # darker
        self.assertLess(sarp["MossTint"][1] / sarp["MossTint"][2], 1.45)  # less yellow-green
        l_ = np.linspace(0.15, 0.55, 41)
        m_s = T2.tray_moss_cpu(np.ones_like(l_), l_, sarp)
        m_m = T2.tray_moss_cpu(np.ones_like(l_), l_, marm)
        self.assertLess(float(m_s.mean()), 0.35)   # patches, no continuous line on the lip (P5b: 1.0)
        self.assertGreater(float(m_s.max()), 0.3)  # but still some moss
        self.assertGreater(float(m_m.mean()), 0.95)  # Marmoreal keeps its full moss lip


if __name__ == "__main__":
    unittest.main()
