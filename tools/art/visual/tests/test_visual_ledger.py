"""ledger.py: rows per 07 4.2 under a lock with an atomic replace; check verifies totals and the ВР-04/ВР-PL10 limits.

  python -B -m pytest -q tools/art/visual/tests
"""
import csv
import json
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import ledger  # noqa: E402
from visual_common import LEDGER_REL, repo_root  # noqa: E402

FIELDS = ["id", "title", "tool", "prompt", "deliverable", "references", "status"]


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
        "T-SYNTX-UPSCALE T-SYNTX-IMG-BANANA T-CODEX-2D\n", encoding="utf-8")
    (r / "docs/game-design/visual/06-tasks/prompts/EN-03.syntx.txt").write_text("x", encoding="utf-8")
    # the real ledger as the starting point: real limits, empty rows
    shutil.copyfile(repo_root() / LEDGER_REL, r / LEDGER_REL)
    return r


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
    assert d["totals"] == {"syntx_spent": 12, "tripo_spent": 0, "codex_packages": 0}
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


def test_codex_row_keeps_nulls(root):
    assert run(root, "add", "--task", "IC-36", "--template", "T-CODEX-2D", "--service", "codex", "--model",
               "Codex app", "--image-gen", "8", "--result", "art/imagegen/hud-icons-vr44-codex/") == 0
    e = data(root)["entries"][0]
    assert e["service"] == "Codex" and e["units"] == "пакет, 8 генераций image_gen"
    assert e["cost"] is None and e["balance_before"] is None and e["quoted"] is None
    assert data(root)["totals"]["codex_packages"] == 1
    assert run(root, "add", "--task", "IC-36", "--template", "T-CODEX-2D", "--service", "Codex", "--model", "x",
               "--units", "пакет", "--before", "10") == 2


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
