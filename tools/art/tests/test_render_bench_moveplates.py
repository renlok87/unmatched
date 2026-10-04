"""MS-T-08: the move-plates variant of tools/art/render/render_bench.py and the draw-call columns of its CSV summary
(MS-AT-41: GPU and draw calls of dx12-lumen-high-v2-moveplates against dx12-lumen-high-v2 on the same bench scene),
plus the -BenchMoveDraft scene fixtures (tools/s08/fixtures/move-draft, 06 §6.2).

  python -m unittest discover -s tools/art/tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))

import render_bench as B  # noqa: E402

MOVE_DRAFT = REPO / "tools/s08/fixtures/move-draft"
BENCH = REPO / "unreal/Unmatched/Config/Bench"
REAL_BOARDS = {"c121b47f8d6eb28daccb76d05": "marmoreal-original", "c7fa64a26c29a0835f2383e63": "sarpedon-original"}


class MovePlatesVariant(unittest.TestCase):
    def test_variant_listed_with_the_plates_flag_and_the_v2_look(self):
        self.assertIn("dx12-lumen-high-v2-moveplates", B.VARIANTS)
        with tempfile.TemporaryDirectory() as d:
            args, execs, notes = B.variant_args("dx12-lumen-high-v2-moveplates", Path(d))
        self.assertIn("-S08MovePlates", args)
        self.assertIn("-ArtPreviewHeroesV2", args)
        self.assertNotIn("-S08HeroesLegacy", args)  # a -v2 variant keeps the accepted figures
        self.assertEqual(execs, [])
        self.assertTrue(notes["movePlates"])

    def test_csv_summary_reads_the_draw_call_columns(self):
        rows = ["FrameTime,GPUTime,RHI/DrawCalls,RHI/PrimitivesDrawn", "16.0,9.0,120,50000", "16.2,9.1,124,50100",
                "16.1,9.0,122,50050", "[HasHeaderRowAtEnd]"]
        # the profiler's [HasHeaderRowAtEnd] layout: header row before the metadata row, data rows positional
        text = "\n".join([rows[0]] + rows[1:4] + [rows[0], "[HasHeaderRowAtEnd],1"]) + "\n"
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.csv"
            p.write_text(text, encoding="utf-8")
            out = B.parse_csv(p)
        self.assertEqual(out["frames"], 3)
        self.assertEqual(out["rhi"]["RHI/DrawCalls"]["max"], 124.0)
        self.assertEqual(out["rhi"]["RHI/DrawCalls"]["p50"], 122.0)
        self.assertIn("RHI/PrimitivesDrawn", out["rhi"])
        self.assertIn("GPUTime", out["gpu"])

    def test_csv_without_the_column_has_no_rhi_entry(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "x.csv"
            p.write_text("FrameTime,GPUTime\n16.0,9.0\n", encoding="utf-8")
            self.assertEqual(B.parse_csv(p)["rhi"], {})


class MoveDraftFixtures(unittest.TestCase):
    """The scene files reference ids of their bench fixture only (the UE test Unmatched.S08.MoveHL.BenchDraft replays them
    through the real draft; here: schema, real boards, ids)."""

    def test_scene_fixtures_use_real_boards_and_known_ids(self):
        files = sorted(MOVE_DRAFT.glob("*.json"))
        self.assertGreaterEqual(len(files), 4)
        boards = set()
        for f in files:
            with self.subTest(f.name):
                doc = json.loads(f.read_text(encoding="utf-8"))
                self.assertEqual(doc["schema"], "unmatched.move-draft/1")
                bench = json.loads((BENCH / doc["benchFixture"]).read_text(encoding="utf-8"))
                self.assertIn(bench["benchBoardId"], REAL_BOARDS)
                self.assertEqual(REAL_BOARDS[bench["benchBoardId"]], doc["board"])
                boards.add(doc["board"])
                state = json.loads(bench["raw"]["data"]["gameState"]["state"])
                fighters = {x["id"] for x in state["fighters"]}
                hand = {c["id"] for c in state["handZones"][bench["benchViewerId"]]["cards"]}
                spaces = {c["spaceId"] for row in state["boardState"]["cells"] for c in row if c.get("spaceId")}
                ids = [m["fighterId"] for m in doc.get("moves", [])] + [o["fighterId"] for o in doc.get("moveOrder", [])]
                if doc.get("selected"):
                    ids.append(doc["selected"])
                self.assertTrue(set(ids) <= fighters, set(ids) - fighters)
                if doc.get("boostCardId"):
                    self.assertIn(doc["boostCardId"], hand)
                for cell in [m["to"] for m in doc.get("moves", [])] + ([doc["hover"]] if "hover" in doc else []):
                    self.assertIn(cell, spaces)
        self.assertEqual(boards, {"marmoreal-original", "sarpedon-original"})


if __name__ == "__main__":
    unittest.main()
