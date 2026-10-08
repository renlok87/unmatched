"""FX-37 (VS-6, G-COST ВР-25): the -BenchFx variants of tools/art/render/render_bench.py - one system per fx-each run,
the worst set under the NET_UM_Combat cap of 3, the -S08FxLegacy control and the per-board dust cell.

  python -m pytest tools/art/tests/test_render_bench_fx37.py
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))

import render_bench as B  # noqa: E402

MARM = "../../../Unmatched/Config/Bench/S08BenchMarmoreal.json"
SARP = "../../../Unmatched/Config/Bench/S08BenchSarpedon.json"


class Fx37Variants(unittest.TestCase):
    def test_each_stages_one_system(self):
        for name in B.FX37_SYSTEMS:
            args, notes = B.fx37_spec(f"dx12-lumen-high-v2-fx-each-{name}", MARM)
            if name == "grade":
                self.assertEqual(args, ["-BenchResult=board"])
                continue
            self.assertEqual(len(args), 1)
            self.assertTrue(args[0].startswith("-BenchFx="))
            self.assertNotIn(";", args[0])
            self.assertEqual(notes["fx37"]["systems"], [name])

    def test_worst_has_three_combat_systems_and_the_board_cell(self):
        args, notes = B.fx37_spec("dx12-lumen-high-v2-fx-worst", SARP)
        self.assertEqual(notes["fx37"]["combat"], 3)
        self.assertIn("dust,8,2,150", args[0])
        self.assertNotIn("outcome", args[0])
        self.assertNotIn("-S08FxLegacy", args)
        m, _ = B.fx37_spec("dx12-lumen-high-v2-fx-worst", MARM)
        self.assertIn("dust,1,1,150", m[0])

    def test_legacy_control_and_cap(self):
        args, notes = B.fx37_spec("dx12-lumen-high-v2-fx-worst-legacy", MARM)
        self.assertIn("-S08FxLegacy", args)
        self.assertTrue(notes["fx37"]["legacy"])
        with self.assertRaises(SystemExit):
            B.fx37_spec("dx12-lumen-high-v2-fx-worst", MARM, ("star", "heal", "ash", "vortex"))
        with self.assertRaises(SystemExit):
            B.fx37_spec("dx12-lumen-high-v2-fx-each-nope", MARM)
        self.assertIsNone(B.fx37_spec("dx12-lumen-high-v2", MARM))
        g, _ = B.fx37_spec("dx12-lumen-high-v2-fx-each-grade-legacy", MARM)
        self.assertEqual(g, ["-BenchResult=board", "-S08FxLegacy"])
        with self.assertRaises(SystemExit):
            B.fx37_spec("dx12-lumen-high-v2-fx-worst", MARM, ("star", "grade"))

    def test_variant_args_keep_the_v2_look(self):
        with tempfile.TemporaryDirectory() as d:
            args, execs, _ = B.variant_args("dx12-lumen-high-v2-fx-worst", Path(d))
        self.assertIn("-ArtPreviewHeroesV2", args)
        self.assertNotIn("-S08HeroesLegacy", args)
        self.assertEqual(execs, [])


if __name__ == "__main__":
    unittest.main()
