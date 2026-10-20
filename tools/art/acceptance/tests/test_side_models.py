"""Профили приёмщиков (side_models.py): Sol отключён 2026-10-20; Z-Code GLM-5.3-Flash снят с приёмки 2026-10-21
(калибровка не пройдена); второй приёмщик «другим профилем» — «Opus high» (решение пользователя 2026-10-21: «Хорошо,
использую Opus High вместо Z-код для приемщика.»).

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


def with_profile(profile, date="2026-10-09", session="workflow:acc-1", **scores):
    card = model_card(date=date, **scores)
    card["acceptor"] = {"profile": profile, "session_id": session}
    return card


def test_full_schema_lists_every_profile():
    assert FULL["properties"]["acceptor"]["properties"]["profile"]["enum"] == list(sm.PROFILES)
    assert sm.FIRST == sm.OPUS == "Opus xhigh" and sm.SECOND == sm.OPUS_HIGH == "Opus high"
    assert sm.effort_of(sm.FIRST) == "xhigh" and sm.effort_of(sm.SECOND) == "high"
    with pytest.raises(ValueError):
        sm.effort_of(sm.ZCODE_FLASH)


@pytest.mark.parametrize("kind", osch.KINDS)
def test_output_schemas_drop_the_retired_profiles(kind):
    enum = osch.build(kind)["properties"]["acceptor"]["properties"]["profile"]["enum"]
    assert enum == [sm.OPUS, sm.OPUS_HIGH] and sm.SOL not in enum and sm.ZCODE_FLASH not in enum
    text = osch.path_for(kind).read_text(encoding="utf-8")
    assert "codex exec" not in text and sm.ZCODE_FLASH not in text and '"Opus high"' in text


def test_old_sol_card_stays_valid_and_new_one_fails():
    errs, allowed, _r, _s = vc.validate(with_profile(sm.SOL, "2026-10-14", "codex:thread-1"), FULL)
    assert errs == [] and allowed == {"pass"}
    errs, *_ = vc.validate(with_profile(sm.SOL, "2026-10-20", "codex:thread-2"), FULL)
    assert errs == []  # день отключения ещё в истории
    errs, *_ = vc.validate(with_profile(sm.SOL, "2026-10-21", "codex:thread-3"), FULL)
    assert any("Sol отключён 2026-10-20" in e and "AGENTS.md" in e and "«Opus high»" in e for e in errs)


def test_zcode_card_after_2026_10_21_is_rejected():
    """Калибровка 2026-10-21 (zcode-calibration/RESULT.md) — история; карточка Z-Code позже — ошибка."""
    errs, allowed, _r, _s = vc.validate(with_profile(sm.ZCODE_FLASH, "2026-10-21", "zcode:task-1"), FULL)
    assert errs == [] and allowed == {"pass"}
    errs, *_ = vc.validate(with_profile(sm.ZCODE_FLASH, "2026-10-22", "zcode:task-2"), FULL)
    assert any("«Z-Code GLM-5.3-Flash» на карточке от 2026-10-22" in e and "снят с приёмки 2026-10-21" in e
               and "zcode-calibration/RESULT.md" in e and "«Opus high»" in e for e in errs), errs
    assert sm.retired_profile_error(sm.ZCODE_FLASH, "2026-11-01T10:00:00+05:00")
    assert sm.retired_profile_error(sm.OPUS_HIGH, "2026-11-01") is None


def test_opus_high_card_is_valid():
    errs, allowed, _r, _s = vc.validate(with_profile(sm.OPUS_HIGH, "2026-10-21", "workflow:acceptor2-A-r1"), FULL)
    assert errs == [] and allowed == {"pass"}


def test_pair_opus_xhigh_and_opus_high_is_two_profiles():
    a = with_profile(sm.OPUS, "2026-10-21")
    b = with_profile(sm.OPUS_HIGH, "2026-10-21", "workflow:acc-2")
    assert vc.pair_errors(a, b) == []
    same = with_profile(sm.OPUS, "2026-10-21", "workflow:acc-2")  # старая пара 2026-10-20 — 2026-10-21
    assert any("профиль приёмщика тот же" in e for e in vc.pair_errors(a, same))
    assert vc.pair_errors(a, same, same_profile_ok=True) == []


def write(tmp_path, name, card):
    p = tmp_path / name
    p.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
    return p


def test_validate_card_second_xhigh_high_pair_without_same_profile_ok(tmp_path, capsys):
    """validate_card.py --second: «Opus xhigh» + «Opus high» проходит без --same-profile-ok; старая пара одного профиля —
    как раньше (код 1 без флага, с флагом — same_profile_fallback)."""
    unstable = dict(S=2, F=1.5, T=1.5, D=1.5)  # 8,1 — полоса второго приёмщика
    a = write(tmp_path, "card.json", with_profile(sm.OPUS, "2026-10-21", "workflow:acceptor-A-r1", **unstable))
    assert vc.main([str(a)]) == vc.EXIT_NEEDS_SECOND
    b = write(tmp_path, "card-2.json", with_profile(sm.OPUS_HIGH, "2026-10-21", "workflow:acceptor2-A-r1", **unstable))
    fin = tmp_path / "final.json"
    assert vc.main([str(a), "--second", str(b), "--final-json", str(fin), "--print-verdict"]) == 0
    out = json.loads(fin.read_text(encoding="utf-8"))
    assert out["same_profile_fallback"] is False and out["verdict"] == "pass" and out["score"] == 8.1
    assert [c["profile"] for c in out["cards"]] == ["Opus xhigh", "Opus high"]
    old = write(tmp_path, "card-2-old.json", with_profile(sm.OPUS, "2026-10-21", "workflow:acceptor2-A-r1", **unstable))
    capsys.readouterr()
    assert vc.main([str(a), "--second", str(old)]) == 1
    assert "профиль приёмщика тот же" in capsys.readouterr().err
    assert vc.main([str(a), "--second", str(old), "--same-profile-ok", "--final-json", str(fin)]) == 0
    assert json.loads(fin.read_text(encoding="utf-8"))["same_profile_fallback"] is True


def test_zcode_lane_is_a_clear_stub(capsys):
    with pytest.raises(sm.SideModelUnavailable, match="zcode login zai"):
        sm.zcode_headless("prompt.md", attach=["a.png"])
    assert sm.main(["zcode-probe"]) == 2
    assert "zcode login zai" in capsys.readouterr().err


def test_first_and_second_acceptor_workflow_args():
    first = osch.workflow_args("anim", [{"asset": "ASSET-X-001", "evidence": "art/x/acc-anim/20261021-r1/Idle"}],
                               first=True)
    assert first["items"] == [{"asset": "ASSET-X-001", "evidence": "art/x/acc-anim/20261021-r1/Idle",
                               "label": "acceptor-ASSET-X-001-Idle-r1",
                               "prompt": "art/x/acc-anim/20261021-r1/Idle/acceptor-prompt.md"}]
    assert first["profile"] == "Opus xhigh" and first["effort"] == "xhigh"
    second = osch.workflow_args("model", [{"asset": "A", "evidence": "e/20261021-r2"}])
    assert second["items"][0]["label"] == "acceptor2-A-r2" and second["items"][0]["prompt"] == \
        "e/20261021-r2/acceptor-prompt-2.md"
    assert second["profile"] == "Opus high" and second["effort"] == "high"


def test_workflow_args_cli_second_is_effort_high(capsys):
    assert osch.main(["--workflow-args", "concept", "--item", "ASSET-X-001=art/x/acc/20261021-sheet-r1"]) == 0
    raw = capsys.readouterr().out
    assert raw.isascii()
    wa = json.loads(raw)
    assert wa["effort"] == "high" and wa["profile"] == "Opus high"
    assert wa["items"][0]["label"] == "acceptor2-ASSET-X-001-r1"
    assert osch.main(["--workflow-args", "concept", "--first", "--item", "ASSET-X-001=art/x/acc/20261021-sheet-r1"]) == 0
    wa = json.loads(capsys.readouterr().out)
    assert wa["effort"] == "xhigh" and wa["profile"] == "Opus xhigh"
