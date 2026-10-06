"""VS-2 CP-08 tests (plain Python, no UE): M_UmPortraitDisc's builder against the C++ parameter names (UmPortrait.h),
the token defaults, and the build report once it exists.

  python -m pytest tools/art/cards/test_portrait_disc_material.py -q
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ue_portrait_disc_material as M  # noqa: E402


def test_parameters_match_the_header():
    info, errors = M.check()
    assert errors == []
    assert set(info["parameters"]) == set(info["header"])


def test_token_defaults():
    # panel.edge = card.cream at alpha 0.45 (02 §2.2), mark.keyline, card.navy - linear like FLinearColor::FromSRGBColor
    edge = M.token_linear("panel.edge")
    assert edge[3] == 0.45 and abs(edge[0] - 0.947307) < 1e-5
    assert M.token_linear("card.navy")[3] == 1.0


def test_build_report_when_present():
    if not M.REPORT.exists():
        return
    rep = json.loads(M.REPORT.read_text(encoding="utf-8"))
    assert rep["ok"] and rep["build"]["action"] in ("created", "rebuilt", "unchanged")
    if "params" in rep["build"]:
        assert rep["build"]["params"]["texture"] == ["Avatar"]
