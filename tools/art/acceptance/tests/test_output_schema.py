"""Строгие схемы вывода приёмщика (_output_schema.py) для `codex exec --output-schema` и их приём validate_card.py.

    python -m pytest tools/art/acceptance/tests -q
"""
import copy
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import _output_schema as osch  # noqa: E402
import validate_card as vc  # noqa: E402
from test_validate_card import anim_card, concept_card, model_card  # noqa: E402

FULL = json.loads(vc.SCHEMA_PATH.read_text(encoding="utf-8"))
jsonschema = pytest.importorskip("jsonschema")


def strict_form(card):
    """Карточка так, как её вернёт строгий вывод: все поля схемы вывода, необязательные — null."""
    c = copy.deepcopy(card)
    c.setdefault("clip", None)
    c.setdefault("verdict_reason", None)
    c.setdefault("known_issues", [])
    for g in c["gates"].values():
        g.setdefault("note", None)
        g.setdefault("source_defect", None)
    return c


def out_errors(card, kind):
    v = jsonschema.Draft202012Validator(osch.build(kind))
    return [e.message for e in v.iter_errors(card)]


@pytest.mark.parametrize("kind", osch.KINDS)
def test_files_are_current_and_strict(kind):
    assert osch.path_for(kind).read_text(encoding="utf-8") == osch.dumps(osch.build(kind))
    assert osch.strict_problems(osch.build(kind)) == []
    jsonschema.Draft202012Validator.check_schema(osch.build(kind))


def test_strict_problems_catches_the_full_schema():
    probs = osch.strict_problems(FULL)
    assert any("allOf" in p for p in probs) and any("every property must be required" in p for p in probs)


@pytest.mark.parametrize("make,kind", [(model_card, "model"), (concept_card, "concept"), (anim_card, "anim")])
def test_valid_card_fits_output_schema_and_validator(make, kind):
    card = strict_form(make())
    assert out_errors(card, kind) == []
    errs, allowed, _rules, _score = vc.validate(card, FULL)
    assert errs == [] and card["verdict"] in allowed


def test_rework_card_with_reason_and_gate_extras():
    card = model_card(F=0.5, verdict="rework_blender",
                      rework_fix_list=[{"item": "F", "frame": "wire-front.jpg", "fix": "сгладить шейдинг",
                                        "tool": "retopo.target_tris"},
                                       {"item": "T", "frame": "close-head.jpg", "fix": "поднять тон кожи",
                                        "tool": "lookdev grade.gains"}])
    card["gates"]["G-UV"] = {"status": "PASS", "source": "x/reports/uv-report.json", "note": "uv-report.json#passed = true"}
    c = strict_form(card)
    assert c["verdict_reason"] and c["gates"]["G-UV"]["note"] and c["gates"]["G-TOPO"]["note"] is None
    assert out_errors(c, "model") == []
    errs, allowed, _r, _s = vc.validate(c, FULL)
    assert errs == [] and "rework_blender" in allowed


def test_prop_d_null_fits_model_output():
    card = model_card()
    card["scores"]["D"] = {"value": None, "rationale": "проп без рига", "frames": []}
    card["gates"]["G-RIG"] = {"status": "n/a", "source": "проп: нет рига"}
    card["score"] = vc.compute_score(card["scores"], "model")
    assert out_errors(strict_form(card), "model") == []


def test_output_schema_rejects_what_strict_mode_must_reject():
    c = strict_form(model_card())
    del c["known_issues"]
    assert out_errors(c, "model")  # every field is required
    c = strict_form(model_card())
    c["gates"]["G-EXTRA"] = {"status": "PASS", "source": "x", "note": None, "source_defect": None}
    assert out_errors(c, "model")  # fixed gate set per kind
    c = strict_form(model_card())
    c["clip"] = "Idle"
    assert out_errors(c, "model")  # clip only for anim


def test_nulls_do_not_hide_real_errors():
    c = strict_form(model_card(F=0.5, verdict="rework_blender"))
    c["verdict_reason"] = None  # rework without a reason: the full schema still demands it
    errs, _a, _r, _s = vc.validate(c, FULL)
    assert any("verdict_reason" in e for e in errs)
    a = strict_form(anim_card())
    a["clip"] = None  # anim: clip is required
    errs, _a, _r, _s = vc.validate(a, FULL)
    assert any("clip" in e for e in errs)


def test_strip_output_nulls_keeps_the_file_dict():
    c = strict_form(model_card())
    before = copy.deepcopy(c)
    out = vc.strip_output_nulls(c)
    assert c == before and "clip" not in out and "note" not in out["gates"]["G-TOPO"]
    assert out["known_issues"] == []  # [] is a value, not a null
