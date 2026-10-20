"""Профили приёмщиков после 2026-10-20 (side_models.py): Sol отключён, Z-Code GLM-5.3-Flash — второй профиль.

    python -m pytest tools/art/acceptance/tests -q
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import _output_schema as osch  # noqa: E402
import side_models as sm  # noqa: E402
import validate_card as vc  # noqa: E402
from test_validate_card import model_card  # noqa: E402

FULL = json.loads(vc.SCHEMA_PATH.read_text(encoding="utf-8"))


def with_profile(profile, date="2026-10-09", session="workflow:acc-1"):
    card = model_card(date=date)
    card["acceptor"] = {"profile": profile, "session_id": session}
    return card


def test_full_schema_lists_every_profile():
    assert FULL["properties"]["acceptor"]["properties"]["profile"]["enum"] == list(sm.PROFILES)


@pytest.mark.parametrize("kind", osch.KINDS)
def test_output_schemas_drop_the_retired_profile(kind):
    enum = osch.build(kind)["properties"]["acceptor"]["properties"]["profile"]["enum"]
    assert enum == [sm.OPUS, sm.ZCODE_FLASH] and sm.SOL not in enum
    assert "codex exec" not in osch.path_for(kind).read_text(encoding="utf-8")


def test_old_sol_card_stays_valid_and_new_one_fails():
    errs, allowed, _r, _s = vc.validate(with_profile(sm.SOL, "2026-10-14", "codex:thread-1"), FULL)
    assert errs == [] and allowed == {"pass"}
    errs, *_ = vc.validate(with_profile(sm.SOL, "2026-10-20", "codex:thread-2"), FULL)
    assert errs == []  # день отключения ещё в истории
    errs, *_ = vc.validate(with_profile(sm.SOL, "2026-10-21", "codex:thread-3"), FULL)
    assert any("Sol отключён 2026-10-20" in e and "AGENTS.md" in e for e in errs)


def test_zcode_profile_is_accepted():
    errs, allowed, _r, _s = vc.validate(with_profile(sm.ZCODE_FLASH, "2026-10-21", "zcode:task-1"), FULL)
    assert errs == [] and allowed == {"pass"}


def test_pair_opus_and_zcode_is_two_profiles():
    a = with_profile(sm.OPUS, "2026-10-21")
    b = with_profile(sm.ZCODE_FLASH, "2026-10-21", "zcode:task-1")
    assert vc.pair_errors(a, b) == []
    same = with_profile(sm.OPUS, "2026-10-21", "workflow:acc-2")
    assert any("профиль приёмщика тот же" in e for e in vc.pair_errors(a, same))
    assert vc.pair_errors(a, same, same_profile_ok=True) == []


def test_zcode_lane_is_a_clear_stub(capsys):
    with pytest.raises(sm.SideModelUnavailable, match="zcode login zai"):
        sm.zcode_headless("prompt.md", attach=["a.png"])
    assert sm.main(["zcode-probe"]) == 2
    assert "zcode login zai" in capsys.readouterr().err


def test_first_acceptor_workflow_args():
    args = osch.workflow_args("anim", [{"asset": "ASSET-X-001", "evidence": "art/x/acc-anim/20261021-r1/Idle"}],
                              first=True)
    assert args["items"] == [{"asset": "ASSET-X-001", "evidence": "art/x/acc-anim/20261021-r1/Idle",
                              "label": "acceptor-ASSET-X-001-Idle-r1",
                              "prompt": "art/x/acc-anim/20261021-r1/Idle/acceptor-prompt.md"}]
    assert osch.workflow_args("model", [{"asset": "A", "evidence": "e/20261021-r2"}])["items"][0]["label"] == \
        "acceptor2-A-r2"
