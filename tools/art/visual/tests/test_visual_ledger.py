"""ledger.py: rows per 07 4.2 under a lock with an atomic replace; check verifies totals and the ВР-04/ВР-PL10 limits.

The fixture ledger is synthetic (RB-03): fixed limits written here, not a copy of the live
docs/game-design/visual/credits-ledger.json, whose limits are user decisions and change (the Tripo cap 3000 was lifted
on 2026-10-13). Only test_real_ledger_passes_check reads the live ledger, and it asserts no particular limit.

  python -B -m pytest -q tools/art/visual/tests
"""
import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ledger  # noqa: E402
from visual_common import LEDGER_REL  # noqa: E402

FIELDS = ["id", "title", "tool", "prompt", "deliverable", "references", "status"]

# the limits every test below expects; tests that need other values rewrite them with set_limits()
LIMITS = {
    "syntx": {"tokens": 300, "until": "2026-10-28", "source": "ВР-04", "stopBalance": 20,
              "perRun": {"image": 8, "video": 10, "upscale": 12, "source": "ВР-PR04"}, "visualCap": 54},
    "tripo": {"credits": 3000, "until": "2026-10-28", "source": "ВР-04"},
    "codex": {"unit": "пакет"},
}


def synthetic_ledger():
    return {"schema": ledger.SCHEMA, "title": "Журнал трат визуального чата (тестовый)", "created": "2026-10-06",
            "status": "пустой: трат ещё нет", "limits": json.loads(json.dumps(LIMITS)), "providerTerms": [],
            "entries": [], "totals": ledger.compute_totals([])}


@pytest.fixture()
def root(tmp_path):
    r = tmp_path / "repo"
    (r / "docs/game-design/visual/06-tasks/prompts").mkdir(parents=True)
    with (r / "docs/game-design/visual/06-tasks/env.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerow({"id": "EN-03", "title": "Плита ×2", "tool": "SYNTX"})
        w.writerow({"id": "IC-36", "title": "Эскизы", "tool": "Codex"})
    (r / "docs/game-design/visual/07-prompt-templates.md").write_text(
        "T-SYNTX-UPSCALE T-SYNTX-IMG-BANANA T-CODEX-2D T-GEMINI-IMG T-STIVA-AUDIO\n", encoding="utf-8")
    (r / "docs/game-design/visual/06-tasks/prompts/EN-03.syntx.txt").write_text("x", encoding="utf-8")
    (r / LEDGER_REL).write_text(json.dumps(synthetic_ledger(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return r


def set_limits(root, service, **values):
    """Rewrite limits.<service> of the fixture ledger; a value of ... deletes the key (DEFAULT_LIMITS applies)."""
    d = data(root)
    for k, v in values.items():
        if v is ...:
            d["limits"][service].pop(k, None)
        else:
            d["limits"][service][k] = v
    (root / LEDGER_REL).write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(root, *args):
    return ledger.main(["--root", str(root), "--lock-timeout", "0.3", *args])


def data(root):
    return json.loads((root / LEDGER_REL).read_text(encoding="utf-8"))


TERMS = ["terms", "--service", "SYNTX", "--model", "Magnific Precision v2", "--url", "https://example.invalid/terms",
         "--checked", "2026-10-06"]
SYNTX_ADD = ["add", "--task", "EN-03", "--template", "T-SYNTX-UPSCALE", "--service", "SYNTX",
             "--model", "magnific/precision_v2 2x", "--units", "1 upscale 2x", "--quoted", "12",
             "--before", "173.771", "--after", "161.771", "--service-task-id", "gen-1",
             "--prompt-file", "docs/game-design/visual/06-tasks/prompts/EN-03.syntx.txt",
             "--result", "scraped-data/derived/env-u16-marmoreal-codex/marmoreal-extended-2x.png",
             "--date", "2026-10-07T14:05:00+05:00"]


def test_real_ledger_passes_check():
    assert ledger.main(["check"]) == 0


def test_add_syntx_row_and_totals(root, capsys):
    assert run(root, *TERMS) == 0
    assert run(root, *SYNTX_ADD) == 0
    d = data(root)
    e = d["entries"][0]
    assert list(e) == list(ledger.ENTRY_KEYS)
    assert e["cost"] == 12 and e["quoted"] == 12 and e["balance_before"] == 173.771 and e["seed"] is None
    assert e["status"] == "ok" and e["note"] == ""
    assert d["totals"] == {"syntx_spent": 12, "tripo_spent": 0, "codex_packages": 0, "gemini_generations": 0,
                           "stiva_generations": 0}
    assert d["status"].startswith("ведётся")
    raw = (root / LEDGER_REL).read_text(encoding="utf-8")
    assert "Журнал трат" in raw and "\\u" not in raw          # ensure_ascii False
    assert raw.startswith('{\n  "schema"')                     # indent 2
    assert not list((root / LEDGER_REL).parent.glob("*.tmp")) and not Path(str(root / LEDGER_REL) + ".lock").exists()
    assert run(root, "check") == 0
    assert "check OK" in capsys.readouterr().out


def test_cost_vs_quoted_goes_to_note(root):
    run(root, *TERMS)
    args = list(SYNTX_ADD)
    args[args.index("--after") + 1] = "160.771"   # cost 13 vs quoted 12
    assert run(root, *args) == 0
    e = data(root)["entries"][0]
    assert e["cost"] == 13 and "differs from quoted 12" in e["note"]


def codex_row(date="2026-10-15T12:27:20+05:00", **over):
    """An old Codex package row as the ledger holds it (written before Codex was switched off on 2026-10-20)."""
    row = {"date": date, "service": "Codex", "model": "Codex app", "template": "T-CODEX-2D", "task_id": "IC-36",
           "units": "пакет, 8 генераций image_gen", "quoted": None, "cost": None, "balance_before": None,
           "balance_after": None, "service_task_id": None, "seed": None, "prompt_file": "",
           "result_path": "art/imagegen/hud-icons-vr44-codex/", "status": "ok", "note": ""}
    row.update(over)
    return row


def put_rows(root, *rows):
    d = data(root)
    d["entries"] += list(rows)
    d["totals"] = ledger.compute_totals(d["entries"])
    (root / LEDGER_REL).write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


GEMINI_TERMS = ["terms", "--service", "gemini", "--model", "Gemini app image generation", "--url",
                "https://example.invalid/gemini-terms", "--checked", "2026-10-20"]
GEMINI_ADD = ["add", "--task", "IC-36", "--template", "T-GEMINI-IMG", "--service", "Gemini", "--model",
              "Gemini app image generation", "--generations", "4", "--result", "art/imagegen/hud-icons-vr44-codex/",
              "--date", "2026-10-21T10:00:00+05:00"]
STIVA_TERMS = ["terms", "--service", "stiva", "--model", "ElevenLabs SFX (stiva.ai)", "--url",
               "https://example.invalid/stiva-terms", "--checked", "2026-10-20"]
STIVA_ADD = ["add", "--task", "EN-03", "--template", "T-STIVA-AUDIO", "--service", "stiva.ai", "--model",
             "ElevenLabs SFX (stiva.ai)", "--generations", "3", "--result", "C:/tmp/audio-src/en-03/",
             "--date", "2026-10-21T11:00:00+05:00"]


def test_codex_add_is_refused_and_old_rows_stay_valid(root, capsys):
    assert run(root, "add", "--task", "IC-36", "--template", "T-CODEX-2D", "--service", "codex", "--model",
               "Codex app", "--units", "пакет, 8 генераций image_gen") == 2
    err = capsys.readouterr().err
    assert "Codex was switched off on 2026-10-20" in err and "AI tools and side models" in err
    assert run(root, "terms", "--service", "Codex", "--model", "x", "--url", "https://example.invalid") == 2
    assert data(root)["entries"] == [] and data(root)["providerTerms"] == []
    put_rows(root, codex_row(), codex_row(date="2026-10-20T23:00:00+05:00"))
    assert run(root, "check") == 0                     # old Codex rows: subscription nulls, no terms needed
    out = capsys.readouterr().out
    assert "codex_packages=2 (switched off 2026-10-20)" in out and "check OK" in out
    put_rows(root, codex_row(date="2026-10-21T09:00:00+05:00"))
    assert run(root, "check") == 1
    assert "Codex was switched off on 2026-10-20" in capsys.readouterr().out


def test_codex_row_keeps_nulls_in_check(root, capsys):
    put_rows(root, codex_row(cost=3))
    assert run(root, "check") == 1
    assert "Codex rows keep cost null" in capsys.readouterr().out


def test_gemini_and_stiva_rows_count_generations(root, capsys):
    assert run(root, *GEMINI_TERMS) == 0 and run(root, *STIVA_TERMS) == 0
    assert [t["service"] for t in data(root)["providerTerms"]] == ["Gemini", "stiva.ai"]
    assert run(root, *GEMINI_ADD) == 0
    assert run(root, *STIVA_ADD) == 0
    second = list(GEMINI_ADD)
    second[second.index("--generations") + 1] = "2"
    assert run(root, *second) == 0
    d = data(root)
    g, s = d["entries"][0], d["entries"][1]
    assert g["service"] == "Gemini" and g["units"] == "4 генераций" and list(g) == list(ledger.ENTRY_KEYS)
    assert s["service"] == "stiva.ai" and s["units"] == "3 генераций"
    for e in (g, s):
        assert e["quoted"] is None and e["cost"] is None and e["balance_before"] is None and e["balance_after"] is None
    assert d["totals"] == {"syntx_spent": 0, "tripo_spent": 0, "codex_packages": 0, "gemini_generations": 6,
                           "stiva_generations": 3}
    capsys.readouterr()
    assert run(root, "check") == 0
    assert "gemini_generations=6; stiva_generations=3" in capsys.readouterr().out


def test_subscription_rows_need_generations_no_balances_and_terms(root, capsys):
    no_count = [a for a in GEMINI_ADD]
    i = no_count.index("--generations")
    del no_count[i:i + 2]
    assert run(root, *no_count) == 2
    assert run(root, *no_count, "--units", "пакет") == 2
    assert run(root, *GEMINI_ADD, "--units", "4 генераций") == 2          # both
    assert run(root, *GEMINI_ADD, "--before", "10") == 2
    err = capsys.readouterr().err
    assert "needs --generations N" in err and "not both" in err and "keep quoted, cost and balances null" in err
    assert data(root)["entries"] == []
    assert run(root, *GEMINI_ADD) == 0                                     # the use is recorded anyway ...
    assert "no providerTerms row for Gemini" in capsys.readouterr().err
    assert run(root, "check") == 1                                         # ... and check wants the terms row
    assert "ВР-05: before the first use" in capsys.readouterr().out
    run(root, *GEMINI_TERMS)
    assert run(root, "check") == 0


def test_totals_written_before_the_new_services_still_check(root):
    run(root, *TERMS)
    run(root, *SYNTX_ADD)
    d = data(root)
    for k in ("gemini_generations", "stiva_generations"):
        del d["totals"][k]                             # a ledger written before 2026-10-20
    (root / LEDGER_REL).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    assert run(root, "check") == 0


def test_refuses_spend_without_card_or_balances(root, capsys):
    assert run(root, *[a if a != "EN-03" else "XX-99" for a in SYNTX_ADD]) == 2
    assert "not a card" in capsys.readouterr().err
    args = [a for a in SYNTX_ADD]
    i = args.index("--after")
    del args[i:i + 2]
    assert run(root, *args) == 2
    assert data(root)["entries"] == []


def test_duplicate_service_task_id_refused(root):
    run(root, *TERMS)
    assert run(root, *SYNTX_ADD) == 0
    assert run(root, *SYNTX_ADD) == 2
    assert len(data(root)["entries"]) == 1


def test_lock_busy_times_out(root, capsys):
    lock = Path(str(root / LEDGER_REL) + ".lock")
    lock.write_text("held", encoding="utf-8")
    assert run(root, *SYNTX_ADD) == 2
    assert "lock is busy" in capsys.readouterr().err
    assert data(root)["entries"] == [] and lock.exists()


def test_check_catches_tampered_totals(root, capsys):
    run(root, *TERMS)
    run(root, *SYNTX_ADD)
    d = data(root)
    d["totals"]["syntx_spent"] = 0
    (root / LEDGER_REL).write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    assert run(root, "check") == 1
    assert "totals.syntx_spent" in capsys.readouterr().out


def test_check_visual_cap_and_stop_balance(root, capsys):
    run(root, *TERMS)
    before = 200.0
    for n in range(5):  # 5 x 12 = 60 > visual cap 54 (ВР-PL10)
        args = list(SYNTX_ADD)
        args[args.index("--before") + 1] = f"{before}"
        args[args.index("--after") + 1] = f"{before - 12}"
        args[args.index("--service-task-id") + 1] = f"gen-{n}"
        assert run(root, *args) == 0
        before -= 12
    args = list(SYNTX_ADD)
    args[args.index("--before") + 1] = "19"
    args[args.index("--after") + 1] = "7"
    args[args.index("--service-task-id") + 1] = "gen-low"
    assert run(root, *args) == 0                       # a spend is always recorded ...
    assert run(root, "check") == 1                     # ... and check fails loudly
    out = capsys.readouterr().out
    assert "visual cap 54" in out and "stop balance 20" in out


def test_check_requires_provider_terms(root, capsys):
    assert run(root, *SYNTX_ADD) == 0
    assert run(root, "check") == 1
    assert "providerTerms" in capsys.readouterr().out


def test_preflight(root, capsys):
    assert run(root, "check", "--balance", "173.771", "--next-cost", "12", "--next-kind", "upscale",
               "--today", "2026-10-07") == 0
    assert run(root, "check", "--balance", "19", "--next-cost", "3", "--next-kind", "image") == 1
    assert run(root, "check", "--balance", "100", "--next-cost", "14", "--next-kind", "upscale") == 1
    assert run(root, "check", "--balance", "100", "--next-cost", "55") == 1          # visual cap 54
    assert run(root, "check", "--balance", "100", "--next-cost", "3", "--today", "2026-10-29") == 1
    out = capsys.readouterr().out
    assert "stop balance" in out and "cap 12" in out and "visual cap 54" in out and "window closed" in out


TRIPO_TERMS = ["terms", "--service", "Tripo", "--model", "Tripo Studio H3.1", "--url",
               "https://example.invalid/tripo-terms", "--checked", "2026-10-09"]


def tripo_add(spent_before, cost, sid):
    """A Tripo spend row on the fixture card EN-03 (check needs only an existing card and a template id)."""
    return ["add", "--task", "EN-03", "--template", "T-SYNTX-UPSCALE", "--service", "Tripo",
            "--model", "Tripo Studio H3.1", "--units", "1 multiview", "--quoted", str(cost),
            "--before", str(spent_before), "--after", str(spent_before - cost), "--service-task-id", sid,
            "--date", "2026-10-09T10:00:00+05:00"]


def test_tripo_preflight_ok_and_ignores_syntx_limits(root, capsys):
    run(root, *TRIPO_TERMS)
    # 95 > the SYNTX visual cap 54 and the SYNTX per-run caps: a Tripo pre-flight must not apply them
    assert run(root, "check", "--service", "tripo", "--next-cost", "95", "--today", "2026-10-09") == 0
    out = capsys.readouterr().out
    assert "ERROR" not in out and "WARN" not in out and "pre-flight: spent" not in out
    assert "remainder 3000 of 3000 until 2026-10-28, after the run 2905" in out
    # with a fresh balance that covers the price, and a model covered by the terms row
    assert run(root, "check", "--service", "Tripo", "--next-cost", "95", "--balance", "4000",
               "--model", "Tripo Studio H3.1", "--today", "2026-10-09") == 0
    capsys.readouterr()
    # a fresh balance below the ВР-04 remainder but above the price: allowed, with a warning
    assert run(root, "check", "--service", "tripo", "--next-cost", "95", "--balance", "100",
               "--today", "2026-10-09") == 0
    assert "the balance is the real bound" in capsys.readouterr().out


def test_tripo_preflight_limit_balance_window_terms(root, capsys):
    assert run(root, "check", "--service", "tripo", "--next-cost", "10", "--today", "2026-10-09") == 1
    assert "no providerTerms row for Tripo" in capsys.readouterr().out          # ВР-05 before the first spend
    run(root, *TRIPO_TERMS)
    assert run(root, "check", "--service", "tripo", "--next-cost", "3001", "--today", "2026-10-09") == 1
    assert "> 3000 credits" in capsys.readouterr().out                           # ВР-04 limit
    assert run(root, "check", "--service", "tripo", "--next-cost", "95", "--balance", "50",
               "--today", "2026-10-09") == 1
    assert "balance 50 < price 95" in capsys.readouterr().out                    # no purchases
    assert run(root, "check", "--service", "tripo", "--next-cost", "95", "--today", "2026-10-29") == 1
    assert "window closed" in capsys.readouterr().out
    assert run(root, "check", "--service", "tripo", "--next-cost", "95", "--model", "Other 3D",
               "--today", "2026-10-09") == 1
    assert "Tripo 'Other 3D'" in capsys.readouterr().out


def test_tripo_preflight_counts_recorded_tripo_spend(root, capsys):
    run(root, *TRIPO_TERMS)
    assert run(root, *tripo_add(5000, 2950, "tripo-1")) == 0
    capsys.readouterr()
    assert run(root, "check", "--service", "tripo", "--next-cost", "50", "--today", "2026-10-09") == 0
    assert "remainder 50 of 3000 until 2026-10-28, after the run 0" in capsys.readouterr().out
    assert run(root, "check", "--service", "tripo", "--next-cost", "51", "--today", "2026-10-09") == 1
    assert "spent 2950 + 51 > 3000" in capsys.readouterr().out
    # the SYNTX pre-flight is unaffected by the Tripo spend
    assert run(root, "check", "--balance", "173.771", "--next-cost", "12", "--next-kind", "upscale",
               "--today", "2026-10-07") == 0


def test_check_service_argument_errors(root, capsys):
    assert run(root, "check", "--service", "tripo") == 2                        # needs --next-cost
    assert run(root, "check", "--service", "tripo", "--next-cost", "5", "--next-kind", "image") == 2
    assert run(root, "check", "--service", "codex", "--next-cost", "5") == 2
    assert run(root, "check", "--model", "Tripo Studio H3.1", "--balance", "100", "--next-cost", "3") == 2
    assert run(root, "check", "--service", "syntx", "--next-cost", "3") == 2    # SYNTX still needs both
    err = capsys.readouterr().err
    assert "needs --next-cost" in err and "--next-kind is a SYNTX" in err and "Codex are subscriptions" in err
    assert "only by the Tripo pre-flight" in err and "both --balance and --next-cost" in err
    # explicit --service syntx is the old default
    assert run(root, "check", "--service", "SYNTX", "--balance", "100", "--next-cost", "55") == 1
    assert "visual cap 54 (ВР-PL10)" in capsys.readouterr().out


# ---- RB-01: until: null is an open window (no TypeError); a missing key keeps the DEFAULT_LIMITS date

def test_limits_of_until_null_and_missing_key():
    lim = ledger.limits_of({"limits": {"syntx": {"until": None}, "tripo": {"until": None}}})
    assert lim["syntx_until"] is None and lim["tripo_until"] is None
    lim = ledger.limits_of({"limits": {"syntx": {}, "tripo": {}}})
    assert lim["syntx_until"] == lim["tripo_until"] == ledger.DEFAULT_LIMITS["syntx_until"] == "2026-10-28"
    assert ledger._after("2026-10-29", "2026-10-28") and not ledger._after("2026-10-28", "2026-10-28")
    assert not ledger._after("2099-01-01", None)


def test_tripo_until_null_keeps_window_open(root, capsys):
    set_limits(root, "tripo", until=None)
    run(root, *TRIPO_TERMS)
    assert run(root, "check", "--service", "tripo", "--next-cost", "95", "--today", "2026-10-29") == 0
    out = capsys.readouterr().out
    assert "window closed" not in out and "None" not in out and "ERROR" not in out
    assert "remainder 3000 of 3000 with an open window (until: null), after the run 2905" in out
    # the SYNTX window keeps its own date
    assert run(root, "check", "--balance", "100", "--next-cost", "3", "--today", "2026-10-29") == 1
    assert "today 2026-10-29 is after 2026-10-28 (ВР-04 window closed)" in capsys.readouterr().out


def test_syntx_until_null_keeps_window_open_and_counts_every_row(root, capsys):
    set_limits(root, "syntx", until=None, tokens=20)
    run(root, *TERMS)
    args = list(SYNTX_ADD)
    args[args.index("--date") + 1] = "2026-11-05T10:00:00+05:00"     # after the old window end 2026-10-28
    assert run(root, *args) == 0
    assert run(root, "check") == 0                                   # no "needs a new decision" for the row
    out = capsys.readouterr().out
    assert "needs a new decision" not in out and "None" not in out
    assert "20 with an open window (until: null) (ВР-04)" in out
    assert run(root, "check", "--balance", "100", "--next-cost", "3", "--today", "2099-01-01") == 0
    assert "window closed" not in capsys.readouterr().out
    # the row of 2026-11-05 counts towards the token limit of an open window: 12 + 12 > 20
    assert run(root, "check", "--balance", "100", "--next-cost", "12", "--next-kind", "upscale",
               "--today", "2099-01-01") == 1
    assert "pre-flight: spent 12.0 + 12 > 20 (ВР-04)" in capsys.readouterr().out


def test_missing_until_key_falls_back_to_default_date(root, capsys):
    set_limits(root, "tripo", until=...)
    run(root, *TRIPO_TERMS)
    assert run(root, "check", "--service", "tripo", "--next-cost", "95", "--today", "2026-10-29") == 1
    assert "today 2026-10-29 is after 2026-10-28 (ВР-04 window closed)" in capsys.readouterr().out
