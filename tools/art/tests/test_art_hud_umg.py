"""Tests for tools/art/art_hud_umg.py (W4-C hybrid UMG HUD).

  - the `SHOT widget` line format of the client (S08ArtHud::FormatWidgetLine,
    pinned by the C++ test Unmatched.S08.ArtHudUmg.Flag) parses with the
    harness regex;
  - qa010 (tools/art/qa010/qa010lib/trace.py) reads a trace WITH the new lines
    exactly like the same trace without them: no unknown SHOT plate/icon lines,
    the same plate / icon / reachable values (byte-compatible QA-010 formats);
  - the same-frame pairing (UMG shown vs Slate twin) and its 1 px rule.

  python -m unittest discover -s tools/art/tests -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "qa010"))

import art_hud_umg as hud  # noqa: E402
from qa010lib import trace as qtrace  # noqa: E402

# The exact line the C++ test expects from FormatWidgetLine.
CPP_LINE = ("SHOT widget id=plate.name impl=umg state=own fighter=f-0-hero bbox=(981,521,1060,537) geom=painted "
            "visible=1 twin=0 source=/Game/S08/UI/ArtHud/WBP_S08ArtPlate")

BASE = """2026.09.29-04.02.22 BOARD 5x6 cells | control points: (0,0)=(-200,-250,0) (4,5)=(200,250,0) | neighbor pair (dist 100 uu)
2026.09.29-04.02.44 HUD art impl=compare plateViews=umg:/Game/S08/UI/ArtHud/WBP_S08ArtPlate,slate(twin):slate iconViews=umg:/Game/S08/UI/ArtHud/WBP_S08ArtIcon,slate(twin):slate textTable=S08ArtHud entries=13 missingKeys=0
2026.09.29-04.02.53 SHOT ctx viewport=1920x1080 viewTarget=CameraActor_1 cam=(0,171,344) rot=(-55,-90,0)
2026.09.29-04.02.53 SHOT fighter f-0-hero pos=(2,2) world=(0,-50,0) screen=(960,660) projected=1 alive=1
2026.09.29-04.02.53 SHOT reachable fighter=f-0-hero n=2 cells=(1,0)(2,0)
2026.09.29-04.02.53 SHOT plate fighter=f-0-hero bbox=(1139,494,1311,548) overlapReachable=0 placement=right gap=6 anchor=(787,282,1133,788) planned=(1139,494,1311,548) geom=painted stableFrames=54
2026.09.29-04.02.53 SHOT icon fighter=f-1-hero bbox=(936,933,984,981) size=48 src=flag planned=(936,933,984,981) geom=painted
{widgets}2026.09.29-04.02.53 SHOT label fighter=f-0-sk0 mode=compact bbox=(1724,432,1848,446)
2026.09.29-04.02.53 SHOT requested: FScreenshotRequest(bShowUI) -> C:\\tmp\\phase2-board-host-1920x1080.png
{samples}2026.09.29-04.03.40 PERF summary scope=artHud impl=compare elapsed=60.0 frames=938 fps=29.31 frameMs avg=34.11 p50=33.33 p95=34.50 p99=41.00 max=300.00 hitches50=2 gpuMs avg=2.22 p50=2.10 p95=2.65 gameMs avg=3.50 p95=6.29 renderMs avg=5.99 p95=7.94
"""


def widget(pid, impl, bbox, twin, prefix=""):
    return (f"2026.09.29-04.02.53 {prefix}SHOT widget id={pid} impl={impl} state=own fighter=f-0-hero "
            f"bbox=({','.join(map(str, bbox))}) geom=painted visible={0 if twin else 1} twin={1 if twin else 0} "
            f"source={'slate' if impl == 'slate' else '/Game/S08/UI/ArtHud/WBP_S08ArtPlate'}\n")


def make_trace(umg_name=(1145, 499, 1260, 518), slate_name=(1145, 499, 1260, 518)) -> str:
    widgets = (widget("plate", "umg", (1139, 494, 1311, 548), False) + widget("plate.name", "umg", umg_name, False)
               + widget("plate", "slate", (1139, 494, 1311, 548), True)
               + widget("plate.name", "slate", slate_name, True))
    samples = (widget("plate", "umg", (1095, 500, 1267, 554), False, "HUD sample=1 ")
               + widget("plate", "slate", (1095, 500, 1267, 554), True, "HUD sample=1 "))
    return BASE.format(widgets=widgets, samples=samples)


class WidgetLineFormat(unittest.TestCase):
    def test_cpp_line_parses(self):
        m = hud.WIDGET.match(CPP_LINE)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(2), "plate.name")
        self.assertEqual([int(m.group(i)) for i in range(6, 10)], [981, 521, 1060, 537])
        self.assertEqual(m.group(10), "painted")

    def test_sample_prefix(self):
        m = hud.WIDGET.match("HUD sample=7 " + CPP_LINE)
        self.assertEqual(m.group(1), "7")

    def test_not_a_qa010_prefix(self):
        for prefix in ("SHOT reachable", "SHOT plate", "SHOT icon", "PLATE ", "REACHABLE ", "ICON "):
            self.assertFalse(CPP_LINE.startswith(prefix), prefix)


class Qa010ByteCompatible(unittest.TestCase):
    def test_same_parse_with_and_without_widget_lines(self):
        with_lines = qtrace.parse_trace_text(make_trace(), "with")
        without = qtrace.parse_trace_text(BASE.format(widgets="", samples=""), "without")
        self.assertEqual(with_lines.unknown_new_lines, [])
        self.assertEqual(len(with_lines.shots), 1)
        a, b = with_lines.shots[0], without.shots[0]
        self.assertEqual(a.plate.value, b.plate.value)
        self.assertEqual(a.icon.value, b.icon.value)
        self.assertEqual(a.reachable.value, b.reachable.value)
        self.assertEqual(a.plate.value["bbox"], (1139.0, 494.0, 1311.0, 548.0))
        self.assertEqual(a.plate.source, "shot-block")


class SameFramePairing(unittest.TestCase):
    def _parse(self, text):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "phase2-client-host.trace.log"
            p.write_text(text, encoding="utf-8")
            return hud.parse_trace(p)

    def test_equal_boxes_pass(self):
        t = self._parse(make_trace())
        self.assertEqual(t["impl"]["impl"], "compare")
        self.assertEqual(t["impl"]["missingKeys"], 0)
        self.assertEqual(len(t["shots"]), 1)
        self.assertEqual(t["shots"][0]["plate"]["bbox"], [1139, 494, 1311, 548])
        parts = hud.pair_group(t["shots"][0]["widgets"])
        self.assertTrue(all(p["pass"] for p in parts.values()))
        self.assertEqual(sorted(t["samples"]), [1])
        self.assertEqual(t["perfArtHud"]["gameMsP95"], 6.29)

    def test_one_px_passes_two_px_fails(self):
        one = hud.pair_group(self._parse(make_trace(slate_name=(1146, 499, 1260, 518)))["shots"][0]["widgets"])
        self.assertTrue(one["plate.name"]["pass"])
        two = hud.pair_group(self._parse(make_trace(slate_name=(1147, 499, 1260, 518)))["shots"][0]["widgets"])
        self.assertFalse(two["plate.name"]["pass"])
        self.assertEqual(two["plate.name"]["maxEdgeDiffPx"], 2)

    def test_missing_twin_is_an_error(self):
        text = make_trace().replace("impl=slate", "impl=umgx")
        parts = hud.pair_group(self._parse(text)["shots"][0]["widgets"])
        self.assertIn("error", parts["plate"])


if __name__ == "__main__":
    unittest.main()
