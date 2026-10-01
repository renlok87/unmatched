"""Tests for the T2b import of the shared rocky tray (P5 track B; ASSET-TABLE-BASE-001 / 20261001-tray-t2b, lane K).

Plain Python (no UE): tools/art/env_kit/ue_import_tray_t2.py --variant t2b - the source verification against the run's
reports, the S08Diorama.h T2b envelope, the per-map looks of M_TableBase_T2b (ground-params.json 'trayLook'), the CPU
mirror of the moss / albedo HLSL and the C++ constants the importer mirrors.

  python -m pytest tools/art/tests/test_tray_t2b_import.py -q
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
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools/art/env_kit"))

import ue_import_tray_t2 as U  # noqa: E402  (`unreal` is absent here)

DIORAMA_H = REPO / "unreal/Unmatched/Source/Unmatched/S08/S08Diorama.h"
GROUND_PARAMS = json.loads(U.GROUND_PARAMS_DEFAULT.read_text(encoding="utf-8"))


def header_consts() -> dict:
    """name -> value of the 'inline const TCHAR* const X = TEXT("...")' / 'constexpr float X = N' lines."""
    text = DIORAMA_H.read_text(encoding="utf-8")
    out = {m.group(1): m.group(2) for m in re.finditer(r'const TCHAR\* const (\w+)\s*=\s*TEXT\("([^"]*)"\)', text)}
    out.update({m.group(1): float(m.group(2)) for m in re.finditer(r"constexpr float (\w+) = ([-\d.]+)f;", text)})
    return out


class T2bPlan(unittest.TestCase):
    def test_check_mode_verifies_the_run_and_the_rock_set(self):
        p = U.plan_t2b(U.RUN_T2B_DEFAULT, U.RUN_DEFAULT, U.GROUND_PARAMS_DEFAULT)
        self.assertTrue(p["ok"], {k: p.get(k) for k in ("error", "envelope", "sources")})
        self.assertEqual({v["status"] for v in p["sources"].values()}, {"verified"})
        self.assertEqual(set(p["sources"]), {"fbx", "Moss_BC", "Moss_N"})
        self.assertEqual({v["status"] for v in p["rock"]["sources"].values()}, {"verified"})  # T2 rock set reused
        self.assertTrue(p["envelope"]["ok"], p["envelope"])
        self.assertEqual(p["expected"]["triangles"], 19278)
        self.assertEqual(set(p["looks"]), {"mi", "mi:marmoreal", "mi:sarpedon"})

    def test_main_check_defaults_to_t2b_and_keeps_t2(self):
        self.assertEqual(U.main(["--check"]), 0)
        self.assertEqual(U.main(["--check", "--variant", "t2"]), 0)

    def test_a_tampered_source_is_never_imported(self):
        import shutil
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / "20261001-tray-t2b"
            shutil.copytree(U.RUN_T2B_DEFAULT / "reports", run / "reports")
            (run / "export").mkdir()
            for f in (U.RUN_T2B_DEFAULT / "export").iterdir():
                shutil.copy(f, run / "export" / f.name)
            moss = run / "export" / "T_TableBase_T2b_Moss_N.png"
            moss.write_bytes(moss.read_bytes() + b"\0")
            p = U.plan_t2b(run, U.RUN_DEFAULT, U.GROUND_PARAMS_DEFAULT)
            self.assertFalse(p["ok"])
            self.assertEqual(p["sources"]["Moss_N"]["status"], "mismatch")

    def test_assets_match_the_s08diorama_constants(self):
        h = header_consts()
        self.assertEqual(U.T2B_ASSETS["mesh"], h["T2bMeshPath"])
        self.assertEqual(U.T2B_ASSETS["mi"], h["T2bMaterialPath"])
        self.assertEqual(U.T2B_ASSETS["master"], h["T2bMasterPath"])
        for key, name in U.T2B_MAPS.items():
            self.assertEqual(U.T2B_ASSETS[f"mi:{key}"], h["T2bMapMaterialPrefix"] + name)
        self.assertEqual(U.T2B_ENVELOPE["maxOverhangUU"], h["T2bMaxOverhangUU"])
        self.assertEqual(U.T2B_ENVELOPE["depthUU"], (h["T2bMinDepthUU"], h["T2bMaxDepthUU"]))
        self.assertEqual(U.T2B_ENVELOPE["lipTopZMax"], h["T2LipTopZMax"])
        self.assertEqual(U.T2B_ENVELOPE["topHalf"], (h["T2TopHalfX"], h["T2TopHalfY"]))
        self.assertEqual(U.T2B_ENVELOPE["topZ"], h["TopZ"])
        # the T2 import is untouched
        self.assertEqual(U.ASSETS["mesh"], h["T2MeshPath"])
        self.assertEqual(U.ASSETS["mi"], h["T2MaterialPath"])

    def test_envelope_check(self):
        build = json.loads((U.RUN_T2B_DEFAULT / "reports/build-report.json").read_text(encoding="utf-8"))
        b = build["geometry"]["boundsUeUU"]
        ok = U.envelope_check(b["min"], b["max"])
        self.assertTrue(ok["ok"], ok)
        self.assertAlmostEqual(ok["overhangUU"], 35.719, places=3)
        self.assertAlmostEqual(ok["depthUU"], 212.746, places=3)
        self.assertFalse(U.envelope_check([v * 100 for v in b["min"]], [v * 100 for v in b["max"]])["ok"])  # x100 import
        deep = list(b["min"])
        deep[2] = -260.0
        self.assertFalse(U.envelope_check(deep, b["max"])["ok"])
        wide = list(b["max"])
        wide[0] = 830.0
        self.assertFalse(U.envelope_check(b["min"], wide)["ok"])
        # T2 (the fallback) is inside the T2b envelope's top / lip but too shallow for its depth range
        t2 = json.loads((U.RUN_DEFAULT / "reports/build-report.json").read_text(encoding="utf-8"))["geometry"]["boundsUeUU"]
        self.assertFalse(U.envelope_check(t2["min"], t2["max"])["ok"])


class T2bLooks(unittest.TestCase):
    def test_looks_resolve_defaults_and_map_overrides(self):
        shared = U.tray_look(GROUND_PARAMS, None)
        marm = U.tray_look(GROUND_PARAMS, "marmoreal")
        sarp = U.tray_look(GROUND_PARAMS, "sarpedon")
        for look in (shared, marm, sarp):
            self.assertEqual(set(look), set(U.TRAY_LOOK_NEUTRAL))
            for name in U.TRAY_LOOK_VECTORS:
                self.assertEqual(len(look[name]), 4, name)
        self.assertGreater(marm["PetalColor"][3], 0.0)    # petals in the Marmoreal moss
        self.assertEqual(sarp["PetalColor"][3], 0.0)      # none on Sarpedon
        self.assertTrue(all(c < 1.0 for c in sarp["RockTint"][:3]))  # damp dark rock
        self.assertLess(sarp["RockRoughScale"], 1.0)
        self.assertEqual(marm["RockTint"], (1.0, 1.0, 1.0, 1.0))  # Marmoreal keeps the T2 rock colour
        self.assertEqual(shared["ChunkVariation"], marm["ChunkVariation"])  # inherited default

    def test_bad_looks_are_refused(self):
        for bad in ({"MossAmount": "lots"}, {"MossTint": [1, 1]}, {"Glow": 1.0}, {"RockTint": [1, "x", 1]},
                    {"MossAmount": True}):
            p = copy.deepcopy(GROUND_PARAMS)
            p["maps"]["sarpedon"]["trayLook"] = bad
            with self.assertRaises(ValueError, msg=bad):
                U.tray_look(p, "sarpedon")
        p = copy.deepcopy(GROUND_PARAMS)
        p["maps"]["sarpedon"]["trayLook"] = {"Glow": 1}
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / "ground-params.json"
            tmp.write_text(json.dumps(p), encoding="utf-8")
            plan = U.plan_t2b(U.RUN_T2B_DEFAULT, U.RUN_DEFAULT, tmp)
            self.assertFalse(plan["ok"])
            self.assertIn("error", plan["looks"])

    def test_neutral_look_is_the_t2_rock(self):
        rng = np.random.default_rng(7)
        rock, moss, vc = rng.random((500, 3)), rng.random((500, 3)), rng.random((500, 3))
        out = U.tray_albedo_cpu(rock, moss, vc, U.TRAY_LOOK_NEUTRAL)
        np.testing.assert_allclose(out, rock, atol=1e-12)
        self.assertEqual(float(U.tray_moss_cpu(vc[:, 0], 0.5, U.TRAY_LOOK_NEUTRAL).max()), 0.0)

    def test_moss_follows_vertex_colour_r(self):
        look = U.tray_look(GROUND_PARAMS, "marmoreal")
        m = U.tray_moss_cpu(np.array([0.0, 0.2, 0.5, 1.0]), 0.36, look)
        self.assertEqual(m[0], 0.0)                       # no mask, no moss
        self.assertTrue(np.all(np.diff(m) >= 0.0), m)     # monotone in R
        self.assertGreater(m[3], 0.9)                     # full mask: moss
        zero = dict(look, MossAmount=0.0)
        self.assertEqual(float(U.tray_moss_cpu(np.ones(4), 0.9, zero).max()), 0.0)

    def test_sarpedon_rock_is_darker_and_deep_rock_darkens(self):
        rock, moss = np.full((1, 3), 0.3), np.full((1, 3), 0.2)
        top, deep = np.array([[0.0, 0.5, 0.0]]), np.array([[0.0, 0.5, 0.8]])
        marm, sarp = U.tray_look(GROUND_PARAMS, "marmoreal"), U.tray_look(GROUND_PARAMS, "sarpedon")
        self.assertLess(U.tray_albedo_cpu(rock, moss, top, sarp).mean(), U.tray_albedo_cpu(rock, moss, top, marm).mean())
        for look in (marm, sarp):
            self.assertLess(U.tray_albedo_cpu(rock, moss, deep, look).mean(), U.tray_albedo_cpu(rock, moss, top, look).mean())

    def test_hlsl_declares_what_it_reads(self):
        params = set(U.TRAY_LOOK_SCALARS) | set(U.TRAY_LOOK_VECTORS)
        for desc, (code, pins) in U.TRAY_HLSL_INPUTS.items():
            words = set(re.findall(r"\b[A-Z][A-Za-z]+\b", code))
            used = {w for w in words if w in params | {"VC", "UV", "Rock", "Moss", "MossBC", "M", "RockN", "MossN",
                                                       "ORM"}}
            self.assertTrue(used <= set(pins), (desc, used - set(pins)))
            self.assertTrue(set(pins) <= used | {"M"}, (desc, set(pins) - used))
        # the CPU mirror uses the same constants
        self.assertIn("(luma - 0.35)", U.HLSL_TRAY_MOSS)
        self.assertIn("raw * 4.0", U.HLSL_TRAY_MOSS)
        self.assertEqual(set(U.TEX_PARAMS_T2B.values()),
                         {"BaseColorTexture", "NormalTexture", "ORMTexture", "MossBaseColorTexture",
                          "MossNormalTexture"})


if __name__ == "__main__":
    unittest.main()
