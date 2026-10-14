"""G-RIG: пробы рига сравниваются с N из probes-report.json#total (прежние 7 + расширенные пробы RB-08, skipped вне N;
интеграция W1-e в h2_bake), отчёт без total (прогоны до расширенных проб) — с прежними 7/7.

    python -m pytest tools/art/acceptance/tests -q
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from test_rules_pilot import edit, gate_repo, statuses  # noqa: E402


def with_total(n_blend, n_fbx, total=14):
    def fn(d):
        d["plausible"] = {"test-h2-blend": n_blend, "test-h2-fbx": n_fbx}
        d["total"] = {"test-h2-blend": total, "test-h2-fbx": total}
    return fn


def test_extended_probes_all_plausible_pass(tmp_path):
    card = gate_repo(tmp_path)
    edit(tmp_path, "probes-report.json", with_total(14, 14))
    st, _res, _ = statuses(card, tmp_path)
    assert st["G-RIG"] == "PASS"


def test_extended_probe_failed_is_fail(tmp_path):
    card = gate_repo(tmp_path)
    edit(tmp_path, "probes-report.json", with_total(14, 13))
    st, res, _ = statuses(card, tmp_path)
    assert st["G-RIG"] == "FAIL" and "plausible.*-fbx = [13] ≠ 14" in res["G-RIG"]["why"][0]


def test_skipped_probes_lower_n(tmp_path):
    """Ancient Leshen: rig.probe_skip выводит голени и стопы из N (14 - 4 = 10)."""
    card = gate_repo(tmp_path)
    edit(tmp_path, "probes-report.json", with_total(10, 10, total=10))
    st, _res, _ = statuses(card, tmp_path)
    assert st["G-RIG"] == "PASS"


def test_report_without_total_keeps_seven(tmp_path):
    card = gate_repo(tmp_path)
    st, _res, _ = statuses(card, tmp_path)
    assert st["G-RIG"] == "PASS"  # фикстура: plausible 7/7 без total
    edit(tmp_path, "probes-report.json", lambda d: d["plausible"].update({"test-h2-blend": 14}))
    st, res, _ = statuses(card, tmp_path)
    assert st["G-RIG"] == "FAIL" and "≠ 7" in res["G-RIG"]["why"][0]
