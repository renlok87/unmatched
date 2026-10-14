"""render_bench.parse_trace: the face ROI head is the focus fighter's (C58, skill check figure Beowulf 7b).

The client traces one `SHOT head` line per figure; the bench took the last one (Merlin f-1-sk0), so `faceRoiSkipped`
named SK_Merlin_H2LD although K2x5 is shot on the -BenchFocusFighter hero.

  python -m pytest tools/art/tests/test_render_bench_focus_head.py -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))

import render_bench as B  # noqa: E402

HEAD = ("2026.10.14-12.29.55 SHOT head fighter={f} socket=Head mesh={m} world=(0.0,0.0,40.0) screen=(960.0,517.7) "
        "top=(960.0,489.1) bottom=(960.0,545.6) headPx={px} projected=1")
FIGHTERS = [("f-0-hero", "SK_Medusa_H2LD"), ("f-1-hero", "SK_Beowulf_H2LD"), ("f-1-sk0", "SK_Merlin_H2LD")]


def trace(tmp_path: Path, focus_line: bool = True, view_focus: str | None = "f-1-hero", scene_hero="f-1-hero") -> Path:
    lines = []
    if focus_line:
        lines.append("2026.10.14-12.28.54 BENCH focus fighter=f-1-hero (Beowulf)")
    lines.append(f"2026.10.14-12.28.54 BENCH scene fixture=x.json board=7x6 fighters=6 hero={scene_hero} art=1")
    lines.append("2026.10.14-12.29.24 BENCH view=K1 overview target=2340.2 fit=1872.2")
    lines += [HEAD.format(f=f, m=m, px="9.0") for f, m in FIGHTERS]
    lines.append("2026.10.14-12.29.55 BENCH view=K2x5" + (f" focus hero={view_focus}" if view_focus else "")
                 + " zoom=5.00 target=468.0 clamp=0")
    lines += [HEAD.format(f=f, m=m, px="56.4") for f, m in FIGHTERS]
    p = tmp_path / "bench.trace.log"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_focus_fighter_head_not_the_last_line(tmp_path):
    t = B.parse_trace(trace(tmp_path))
    assert t["focus"] == "f-1-hero"
    assert t["heads"]["K2x5"]["mesh"] == "SK_Beowulf_H2LD"
    assert t["headFocus"]["K2x5"] == {"fighter": "f-1-hero", "source": "view focus"}
    assert t["heads"]["K1"]["mesh"] == "SK_Beowulf_H2LD"                       # K1 has no view focus
    assert t["headFocus"]["K1"]["source"] == "BenchFocusFighter"
    assert set(t["headsAll"]["K2x5"]) == {f for f, _ in FIGHTERS}
    luma_why = B.face_boxes(t["heads"]["K2x5"])[1]
    assert "SK_Beowulf_H2LD" in luma_why and "Merlin" not in luma_why


def test_scene_hero_then_last_line_fallbacks(tmp_path):
    t = B.parse_trace(trace(tmp_path, focus_line=False, view_focus=None, scene_hero="f-0-hero"))
    assert t["heads"]["K2x5"]["mesh"] == "SK_Medusa_H2LD" and t["headFocus"]["K2x5"]["source"] == "scene hero"
    t = B.parse_trace(trace(tmp_path, focus_line=False, view_focus=None, scene_hero="f-9-none"))
    assert t["heads"]["K2x5"]["mesh"] == "SK_Merlin_H2LD"                      # old traces: the last line, as before
    assert t["headFocus"]["K2x5"]["source"].startswith("last SHOT head line")


def test_committed_beowulf_bench_trace():
    p = REPO / "docs/art-pipeline/evidence/beowulf-20261014/bench/beowulf-stage7/r1/bench.trace.txt"
    if not p.is_file():
        pytest.skip("Beowulf 7b bench trace not in this checkout")
    t = B.parse_trace(p)
    assert {v: h["mesh"] for v, h in t["heads"].items()} == {"K1": "SK_Beowulf_H2LD", "K2x5": "SK_Beowulf_H2LD"}
