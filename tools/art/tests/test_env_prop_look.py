"""Tests for ENV-MAPS P4 track B: the env kit 'look' (tools/art/env_kit/env_prop_look.py, M_EnvProp parameters in
art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/scripts/env-prop-look.json), its plain-Python side in
tools/art/env_kit/ue_import_env_kit.py, and the P4 layout rules of tools/art/env_kit/layout_check.py (K1 framing of
the Sarpedon hull, the near-half rule, the moved / added props).

CPU only (numpy / PIL, committed textures and layouts). The HLSL compile test runs when the Windows SDK fxc / dxc are
installed and skips otherwise.

  python -m pytest tools/art/tests/test_env_prop_look.py -q
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ENV_KIT = HERE.parents[0] / "env_kit"
sys.path.insert(0, str(ENV_KIT))

import env_prop_look as LOOK  # noqa: E402
import layout_check as LC  # noqa: E402
import ue_import_env_kit as IMP  # noqa: E402

DATA = LOOK.load_look()
LAYOUT_DIR = LC.ROOT / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
TOPO_DIR = LC.ROOT / "backend/prisma/fixtures/boards"
LC.kit_crosscheck(LC.BUILD_REPORTS)


def layout(key: str) -> dict:
    return json.loads((LAYOUT_DIR / f"{key}.layout.json").read_text(encoding="utf-8"))


def spaces(key: str) -> list:
    return LC.load_spaces(json.loads((TOPO_DIR / f"{key}.topology.json").read_text(encoding="utf-8")))


class LookFile(unittest.TestCase):
    def test_schema_and_master(self):
        self.assertEqual(DATA["schema"], LOOK.SCHEMA)
        self.assertEqual(DATA["master"], "/Game/EnvKit/Shared/M_EnvProp")
        self.assertEqual(LOOK.validate_look(DATA), [])
        self.assertIn("предложено", DATA["status"])
        self.assertNotIn("художественно принято", json.dumps(DATA, ensure_ascii=False))

    def test_props_are_kit_props(self):
        self.assertEqual(set(DATA["props"]) - set(IMP.KIT), set())
        # the review gaps this phase covers with the look (no new asset)
        self.assertEqual(set(DATA["props"]), {"Cherry", "Cypress", "Tree", "LanternPlinth", "Campfire", "Portal"})

    def test_validation_rejects_bad_entries(self):
        bad = json.loads(json.dumps(DATA))
        bad["props"]["Cherry"]["region"]["window"]["halfWidthDeg"] = 0
        bad["props"]["LanternPlinth"]["emissive"]["intensity"] = 0
        bad["props"]["Urn"] = {}
        errs = " | ".join(LOOK.validate_look(bad))
        for needle in ("Cherry.region.window out of range", "LanternPlinth.emissive.intensity", "Urn: no region"):
            self.assertIn(needle, errs)
        self.assertTrue(LOOK.validate_look(dict(DATA, master="/Game/UM/Materials/M_UM_Figure")))

    def test_mi_params_complete(self):
        for name in DATA["props"]:
            prm = LOOK.mi_params(DATA, name)
            self.assertEqual(set(prm["vector"]), set(LOOK.VECTOR_DEFAULTS), name)
            self.assertEqual(set(prm["scalar"]), set(LOOK.SCALAR_DEFAULTS), name)
            self.assertTrue(all(len(v) == 4 for v in prm["vector"].values()), name)
            has_em = "emissive" in DATA["props"][name]
            self.assertEqual(prm["scalar"]["EmissiveIntensity"] > 0, has_em, name)
            self.assertEqual(prm["vector"]["EmissiveWindow"][1] > 0, has_em, name)


class Shader(unittest.TestCase):
    def test_hlsl_inputs_used_and_no_vector_ternary(self):
        for kind, code in (("albedo", LOOK.HLSL_ALBEDO), ("emissive", LOOK.HLSL_EMISSIVE)):
            for pin, _ in LOOK.HLSL_INPUTS[kind]:
                self.assertRegex(code, rf"\b{pin}\b", f"{kind}: input {pin} unused")
            self.assertNotIn("?", code)  # vector ?: is deprecated in HLSL 2021 (dxc)
            self.assertIn("return", code)

    def test_neutral_parameters_are_identity(self):
        neutral = {"vector": dict(LOOK.VECTOR_DEFAULTS), "scalar": dict(LOOK.SCALAR_DEFAULTS)}
        for name in ("Cherry", "LanternPlinth", "Hull"):
            bc = LOOK.load_bc(name, size=128)
            out = LOOK.apply_look(bc, neutral)
            self.assertLess(float(np.abs(out["srgb"] - bc).max()), 1.0 / 255.0, name)
            self.assertEqual(float(out["emissive"].max()), 0.0, name)
            self.assertEqual(float(out["w"].max()), 0.0, name)

    def test_hsv_round_trip_and_known_values(self):
        rng = np.random.default_rng(7)
        c = rng.random((4096, 3))
        self.assertLess(float(np.abs(LOOK.hsv_to_rgb(LOOK.rgb_to_hsv(c)) - c).max()), 1e-6)
        hsv = LOOK.rgb_to_hsv(np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [1.0, 0.0, 0.5], [0.5, 0.5, 0.5]]))
        np.testing.assert_allclose(hsv[:, 0] * 360, [0, 120, 330, 0], atol=1e-4)
        np.testing.assert_allclose(hsv[:, 1], [1, 1, 1, 0], atol=1e-6)

    def test_window_wraps_hue(self):
        soft = (8.0, 0.06)
        hsv = np.array([[355 / 360, 0.8, 0.8], [5 / 360, 0.8, 0.8], [40 / 360, 0.8, 0.8], [0.0, 0.1, 0.8]])
        w = LOOK.window_weight(hsv, (0.0, 15.0, 0.3, 0.3), soft)
        np.testing.assert_allclose(w, [1, 1, 0, 0], atol=1e-6)
        self.assertEqual(float(LOOK.window_weight(hsv, (0.0, -1.0, 0.3, 0.3), soft).max()), 0.0)

    @unittest.skipUnless(Path("C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64/fxc.exe").is_file(),
                         "Windows SDK fxc not installed")
    def test_hlsl_compiles_sm5_and_sm6(self):
        src = ["struct FMaterialPixelParameters { float4 SvPosition; };", "cbuffer CB { float4 K[16]; };"]
        calls = []
        for i, (kind, code) in enumerate((("albedo", LOOK.HLSL_ALBEDO), ("emissive", LOOK.HLSL_EMISSIVE))):
            ins = LOOK.HLSL_INPUTS[kind]
            params = ", ".join(["FMaterialPixelParameters Parameters"] + [f"{t} {n}" for n, t in ins])
            src.append(f"float3 CustomExpression{i}({params})\n{{\n{code}\n}}")
            args = ["Parameters"] + [f"({t})K[{k}]" if t != "float" else f"K[{k}].x" for k, (n, t) in enumerate(ins)]
            calls.append(f"  acc.xyz += CustomExpression{i}({', '.join(args)});")
        src.append("float4 main(float4 pos : SV_Position) : SV_Target\n{\n  FMaterialPixelParameters Parameters;\n"
                   "  Parameters.SvPosition = pos;\n  float4 acc = 0;\n" + "\n".join(calls) + "\n  return acc;\n}\n")
        kits = Path("C:/Program Files (x86)/Windows Kits/10/bin/10.0.26100.0/x64")
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "m_envprop.hlsl"
            f.write_text("\n\n".join(src), encoding="utf-8")
            runs = [(kits / "fxc.exe", ["/T", "ps_5_0", "/E", "main", "/nologo"])]
            if (kits / "dxc.exe").is_file():
                runs += [(kits / "dxc.exe", ["-T", "ps_6_0", "-E", "main", "-nologo"]),
                         (kits / "dxc.exe", ["-T", "ps_6_6", "-E", "main", "-nologo", "-HV", "2021"])]
            for exe, args in runs:
                r = subprocess.run([str(exe), *args, str(f)], capture_output=True, text=True,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                self.assertEqual(r.returncode, 0, f"{exe.name} {args[:2]}: {r.stdout[-800:]} {r.stderr[-800:]}")


class Targets(unittest.TestCase):
    """The review's numbers, measured on the committed BC textures (texture space; UE frames are the integrate's)."""

    @classmethod
    def setUpClass(cls):
        cls.res = {name: LOOK.measure(name, DATA) for name in DATA["props"]}

    def test_every_target_met(self):
        for name, res in self.res.items():
            self.assertEqual(LOOK.check_targets(name, DATA, res), [], name)

    def test_cherry_blossom_quick_win(self):  # rank 2: hue 335-345, S ~0.35 IN THE FRAME, V +20 %
        reg = self.res["Cherry"]["region"]
        self.assertTrue(335 <= reg["after"]["hueDeg"] <= 345)
        # P4 tune: the night render raises the blossom saturation (albedo 0.34 -> lit canopy 0.45), so the albedo goes
        # to ~0.25 for a measured K1 canopy S of ~0.39 (target 0.35-0.45)
        self.assertAlmostEqual(reg["after"]["sat"], 0.25, delta=0.04)
        self.assertGreater(reg["valRatio"], 1.12)  # +20 % before the clamp at V = 1
        self.assertGreater(reg["before"]["sat"], 0.55)
        self.assertAlmostEqual(self.res["Cherry"]["rest"]["valRatio"], 1.0, delta=0.005)  # trunk untouched

    def test_cypress_baubles_quiet_and_tree_darker(self):  # ranks 15, 7
        cyp = self.res["Cypress"]
        self.assertLess(cyp["region"]["after"]["sat"], 0.32)
        self.assertLess(cyp["region"]["after"]["val"], 0.4)
        self.assertLess(cyp["rest"]["valRatio"], 0.85)
        tree = self.res["Tree"]["rest"]
        self.assertAlmostEqual(tree["valRatio"], 0.75, delta=0.03)
        self.assertAlmostEqual(tree["satRatio"], 0.80, delta=0.03)

    def test_emissive_accents(self):  # ranks 13, 14: emissive only, lantern brightest
        lum = {n: (self.res[n].get("emissive") or {}).get("meanLuminance", 0.0) for n in DATA["props"]}
        self.assertEqual({n for n, v in lum.items() if v > 0}, {"LanternPlinth", "Campfire", "Portal"})
        self.assertEqual(max(lum, key=lum.get), "LanternPlinth")
        # x ~0.2 (EV100 2.05) the lantern glass sits at 3-5x the map's emissive Lift 1.5 x 0.2 x albedo ~0.5
        self.assertTrue(0.2 * lum["LanternPlinth"] >= 3 * 0.2 * 1.5 * 0.1)


class Importer(unittest.TestCase):
    def _plans(self, names):
        run = IMP.RUN_DEFAULT
        report = IMP.load_build_report(run)
        return run, {n: IMP.plan_prop(n, run, report) for n in names}

    def test_attach_look_selects_the_look_props(self):
        run, plans = self._plans(list(IMP.KIT))
        info, ok = IMP.attach_look(plans, run, Namespace(no_look=False, look=None))
        self.assertTrue(ok and info["used"])
        self.assertEqual({n for n, p in plans.items() if p.get("look")}, set(DATA["props"]))
        self.assertEqual(plans["Cherry"]["look"], LOOK.mi_params(DATA, "Cherry"))
        self.assertNotIn("look", plans["Hull"])

    def test_no_look_and_missing_file(self):
        run, plans = self._plans(["Cherry"])
        info, ok = IMP.attach_look(plans, run, Namespace(no_look=True, look=None))
        self.assertTrue(ok)
        self.assertFalse(info["used"])
        self.assertNotIn("look", plans["Cherry"])
        info, ok = IMP.attach_look(plans, run, Namespace(no_look=False, look=str(run / "nope.json")))
        self.assertFalse(ok)

    def test_check_mode_passes(self):
        self.assertEqual(IMP.main(["--check", "--names", "Cherry,LanternPlinth,Hull"]), 0)

    def test_master_contract(self):
        self.assertEqual(IMP.ENV_MASTER, LOOK.MASTER_PATH)
        self.assertTrue(IMP.ENV_MASTER.startswith(IMP.ROOT + "/"))  # cooked with /Game/EnvKit (DefaultGame.ini)
        self.assertEqual(LOOK.TEX_PARAMS, {"BC": IMP.PARAMS["BC"], "N": IMP.PARAMS["N"], "ORM": IMP.PARAMS["ORM"]})


class Layouts(unittest.TestCase):
    """P4 track B layout edits (concept-review gaps 2, 4, 6, 7): props and lights only."""

    def _errors(self, key):
        lay = layout(key)
        sp = spaces(key)
        err, warn, info = LC.validate(lay, key, sp)
        err = [e for e in err if not e.startswith("ground:")]  # the splat is regenerated by ground_splat.py
        self.assertTrue(info["parsed"])
        return lay, sp, err, warn

    def test_sarpedon_hull_in_the_k1_frame(self):
        lay, sp, err, warn = self._errors("sarpedon")
        self.assertEqual(err, [])
        k_err, k_info = LC.k1_framing(lay, "sarpedon")
        self.assertEqual(k_err, [])
        for pid in ("hull-e1", "hull-e2"):
            self.assertIn(pid, LC.K1_FRAMED["sarpedon"])
            self.assertEqual(k_info[pid]["inFrame"], 1.0)
            self.assertGreaterEqual(k_info[pid]["edgePx"], 0.0)
        hulls = [p for p in lay["props"] if LC.mesh_name(p) == "Hull"]
        ys = sorted(p["loc"][1] for p in hulls)
        self.assertLess(ys[0], 0.0)
        self.assertGreater(ys[1], 0.0)  # centred on Y
        self.assertFalse([w for w in warn if "rocky lip" in w])  # the old hull-e1 20 uu WARN

    def test_sarpedon_west_forest(self):
        lay, _, _, _ = self._errors("sarpedon")
        trees = [p for p in lay["props"] if LC.mesh_name(p) == "Tree"]
        self.assertGreaterEqual(len(trees), 6)
        self.assertTrue(all(p["loc"][0] < -LC.FRAME_HX - 100 for p in trees))  # behind the W palisade
        self.assertGreater(len({p["scale"] for p in trees}), 3)
        self.assertGreater(len({p["yawDeg"] for p in trees}), 3)

    def test_marmoreal_corners(self):
        lay, sp, err, warn = self._errors("marmoreal")
        self.assertEqual(err, [])
        cherries = [p for p in lay["props"] if LC.mesh_name(p) == "Cherry"]
        posts = [p for p in lay["props"] if LC.mesh_name(p) == "PlinthBall"]
        self.assertEqual(len(cherries), 4)
        self.assertEqual(len(posts), 4)
        quads = {(p["loc"][0] > 0, p["loc"][1] > 0) for p in posts}
        self.assertEqual(len(quads), 4)  # one ball-finial post per tray corner

    def test_light_budget_unchanged(self):
        for key in ("marmoreal", "sarpedon"):
            lay = layout(key)
            self.assertEqual(len(lay["lights"]), 5, key)  # + 1 profile point = 6, + the key
            self.assertTrue(all(lt["castShadow"] is False for lt in lay["lights"]))
            self.assertTrue(LC.PROPS_RANGE[0] <= len(lay["props"]) <= LC.PROPS_RANGE[1], key)

    def test_ground_section_untouched_by_track_b(self):
        for key in ("marmoreal", "sarpedon"):
            g = layout(key)["ground"]
            self.assertEqual(g["mode"], "runtime")
            self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", g["splatSha256"]))


if __name__ == "__main__":
    unittest.main()
