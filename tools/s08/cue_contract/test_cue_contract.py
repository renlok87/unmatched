"""Тесты контракта FS08CueDispatcher без движка.

Run from the repo root:  python -m unittest discover -s tools/s08/cue_contract -v
Проверяются: таблица (схема, семантика, сверка с 07), эталонная модель на фикстурах, гейт трассы
на позитивных и негативных трассах. Реальные файлы только читаются.
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cue_contract as cc  # noqa: E402

TABLE = cc.load_json(cc.TABLE)


def row(table, cid):
    return next(c for c in table["cues"] if c["id"] == cid)


class TableTests(unittest.TestCase):
    def test_table_valid(self):
        self.assertEqual(cc.validate_table(TABLE), [])
        self.assertEqual(len(TABLE["cues"]), 18)

    def test_missing_report_lists_every_absent_asset(self):
        miss = cc.missing_report(TABLE)
        expected = sum(1 for c in TABLE["cues"] for ch in ("vfx", "sfx", "clip")
                       if c.get(ch) and c[ch]["status"] == "missing")
        self.assertEqual(len(miss), expected)
        self.assertIn(("CUE-011", "clip", row(TABLE, "CUE-011")["clip"]["missing_reason"]), miss)

    def test_semantic_errors_detected(self):
        cases = []
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["duration_ms"] = 800; cases.append((t, "duration_ms"))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["vfx"]["socket"] = "Tail"; cases.append((t, "сокет"))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["sfx"]["status"] = "present"; cases.append((t, "present без пути"))
        t = copy.deepcopy(TABLE); row(t, "CUE-008")["interrupted_by"] = ["CUE-099"]; cases.append((t, "interrupted_by"))
        t = copy.deepcopy(TABLE); r = row(t, "CUE-013"); r["duration_ms"] = 1200; cases.append((t, "P3"))
        t = copy.deepcopy(TABLE); t["cues"] = t["cues"][:-1]; cases.append((t, "07"))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["clip"]["status"] = "missing"; row(t, "CUE-011")["clip"]["sequence"] = "/Game/A/B.B"
        cases.append((t, "путь задан"))
        for bad, needle in cases:
            errs = cc.validate_table(bad)
            self.assertTrue(any(needle in e for e in errs), (needle, errs))

    def test_schema_errors_detected(self):
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["vfx"]["sim"] = "gpu"
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["reduced_motion"] = {"mode": "shorten", "max_ms": 250}
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["on_reconnect"] = "replay"
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))


class ModelAndGateTests(unittest.TestCase):
    def test_all_fixtures(self):
        res = cc.run_fixtures(TABLE)
        self.assertGreaterEqual(len(res), 12)
        bad = [r for r in res if not r["ok"]]
        self.assertEqual(bad, [])

    def test_model_rejects_bad_input(self):
        d = cc.ReferenceDispatcher(TABLE)
        d.feed({"t": 10, "kind": "advance"})
        with self.assertRaises(ValueError):
            d.feed({"t": 5, "kind": "advance"})
        with self.assertRaises(ValueError):
            cc.ReferenceDispatcher(TABLE).feed({"t": 0, "kind": "cue", "id": "CUE-011", "subject": "x"})

    def test_parse_line_with_log_prefix_and_foreign_lines(self):
        k, f = cc.parse_line("[2026.09.29-10.00.00:000][  0]LogUnmatched: CUE fx done id=CUE-011 subject=a seq=1 t=900 ms=900 cut=0")
        self.assertEqual((k, f["cut"]), ("CUE fx done", "0"))
        self.assertIsNone(cc.parse_line("LogUnmatched: CUE damage medusa -2 seq=7"))
        self.assertIsNone(cc.parse_line("CUE move medusa (1,1)->(1,2) seq=8"))

    def test_gate_ignores_existing_cue_lines(self):
        errs, summary = cc.check_trace(["CUE damage medusa -2 seq=7", "CUE move medusa (1,1)->(1,2) seq=8"], TABLE)
        self.assertEqual((errs, summary["presented"]), ([], 0))

    def test_gate_counts_unique_triples(self):
        fx = cc.load_json(cc.FIXTURES / "dedupe-http-ws.json")
        errs, summary = cc.check_trace(fx["expect_trace"], TABLE)
        self.assertEqual(errs, [])
        self.assertEqual((summary["presented"], summary["unique_triples"], summary["duplicate"]), (1, 1, 1))

    def test_every_presented_line_has_all_fields(self):
        fx = cc.load_json(cc.FIXTURES / "reconnect-no-replay.json")
        broken = [l.replace(" socket=Head", "") if "result=spawned" in l else l for l in fx["expect_trace"]]
        codes = {c for c, _ in cc.check_trace(broken, TABLE)[0]}
        self.assertIn("G1", codes)


if __name__ == "__main__":
    unittest.main()
