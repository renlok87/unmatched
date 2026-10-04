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

    def test_cue007_caps(self):
        """MS-T-15: CUE-007 несёт потолки 04 §6.3 и описание params; схема и семантика их стерегут."""
        r = row(TABLE, "CUE-007")
        self.assertEqual(cc.move_params(r), {"duration_per_step_ms": 280, "cap_subject_ms": 1400, "cap_seq_ms": 2400,
                                             "min_step_ms": 90, "overlap": 0.3, "place_ms": 240})
        self.assertTrue({"path", "order_in_seq"} <= set(r["params"]))
        for key in ("cap_seq_ms", "params"):
            t = copy.deepcopy(TABLE); del row(t, "CUE-007")[key]
            self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)), key)
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["cap_seq_ms"] = 2400  # потолок без шаговой длительности
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        t = copy.deepcopy(TABLE); row(t, "CUE-007")["overlap"] = 1.0
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        cases = (("cap_seq_ms", 1000, "cap_seq_ms"), ("cap_subject_ms", 200, "cap_subject_ms"),
                 ("min_step_ms", 300, "min_step_ms"), ("place_ms", 60, "place_ms"))
        for key, value, needle in cases:
            t = copy.deepcopy(TABLE); row(t, "CUE-007")[key] = value
            errs = cc.validate_table(t)
            self.assertTrue(any(needle in e and not e.startswith("schema") for e in errs), (key, errs))
        t = copy.deepcopy(TABLE); del row(t, "CUE-007")["params"]["order_in_seq"]
        self.assertTrue(any("params.order_in_seq" in e for e in cc.validate_table(t)))


P = cc.move_params(row(TABLE, "CUE-007"))


def moves(count, steps, kind="move"):
    return [{"kind": kind, "steps": steps} for _ in range(count)]


def end(e):
    return e["start"] + e["ms"]


class MoveScheduleTests(unittest.TestCase):
    """Контрольные значения 04 §6.3 / MS-AT-24 на потолках из таблицы (те же проверяет C++ CueTrace)."""

    def test_single_moves(self):
        self.assertAlmostEqual(cc.move_schedule(moves(1, 1), P)[0]["ms"], 280, delta=1)
        nine = cc.move_schedule(moves(1, 9), P)[0]
        self.assertAlmostEqual(nine["ms"], 1400, delta=1)
        self.assertAlmostEqual(nine["step"], 155.6, delta=0.1)
        self.assertAlmostEqual(cc.move_schedule(moves(1, 5, "place"), P)[0]["ms"], 240, delta=1)
        self.assertAlmostEqual(cc.move_schedule(moves(1, 1, "place"), P, mul=0.5)[0]["ms"], 120, delta=1)

    def test_four_by_seven(self):
        normal = cc.move_schedule(moves(4, 7), P)
        self.assertAlmostEqual(end(normal[3]), 2400, delta=1)
        self.assertAlmostEqual(normal[0]["step"], 110.6, delta=0.1)
        self.assertEqual([round(e["start"]) for e in normal], [0, 542, 1084, 1626])
        slow = cc.move_schedule(moves(4, 7), P, mul=1.5)
        self.assertAlmostEqual(end(slow[3]), 3600, delta=1)
        self.assertAlmostEqual(slow[0]["step"], 165.9, delta=0.1)

    def test_nine_by_nine_snaps(self):
        normal = cc.move_schedule(moves(9, 9), P)
        self.assertEqual([round(end(e)) for e in normal[:3]], [810, 1377, 1944])
        self.assertEqual([e["snapped"] for e in normal], [False] * 3 + [True] * 6)
        self.assertTrue(all(round(e["start"]) == 1944 and e["ms"] == 0 for e in normal[3:]))
        fast = cc.move_schedule(moves(9, 9), P, mul=0.5)
        self.assertEqual([e["snapped"] for e in fast], [False] + [True] * 8)
        self.assertAlmostEqual(end(fast[0]), 810, delta=1)  # min_step_ms не масштабируется
        self.assertTrue(all(round(e["start"]) == 810 for e in fast[1:]))

    def test_reduced_and_none(self):
        for sched in (cc.move_schedule(moves(3, 4), P, reduced=True), cc.move_schedule(moves(3, 4), P, mul=None)):
            self.assertTrue(all(e["snapped"] and e["ms"] == 0 and e["start"] == 0 for e in sched))

    def test_dispatcher_duration_uses_schedule(self):
        d = cc.ReferenceDispatcher(TABLE)
        r = row(TABLE, "CUE-007")
        self.assertEqual(d._duration(r, {"steps": 4}), (1120, False))
        self.assertEqual(d._duration(r, {"steps": 9}), (1400, False))  # было 2520 без потолка
        self.assertEqual(d._duration(r, {"steps": 3, "move_kind": "place"}), (240, False))
        self.assertEqual(d._duration(r, {"steps": 9, "order": 4, "seq_moves": moves(9, 9)}), (0, False))


def ms_line(seq, fighter, order, of, kind, steps, source, start, ms, snapped, path=None, extra=""):
    line = ("2026.10.04-00.16.55 MS-CUE move seq=%d fighter=%s order=%d of=%d kind=%s steps=%d source=%s start=%d ms=%d "
            "snapped=%d" % (seq, fighter, order, of, kind, steps, source, start, ms, snapped))
    if path:
        line += " path=" + path
    return line + extra


GOOD = [
    ms_line(11, "s1", 0, 2, "place", 1, "trail", 0, 240, 0, "(4,0)>(4,2)"),
    ms_line(11, "h1", 1, 2, "move", 3, "trail", 168, 840, 0, "(0,0)>(1,0)>(1,1)>(2,1)"),
    "2026.10.04-00.16.55 CUE move h1 (0,0)->(2,1) seq=11",
    ms_line(12, "m1", 0, 1, "move", 1, "straight", 0, 280, 0, "(0,1)>(4,1)"),
    ms_line(13, "m1", 0, 1, "move", 3, "canonical", 0, 840, 0, "M07>M08>M09>M15", " trail=mismatch"),
]


class MsCueGateTests(unittest.TestCase):
    def codes(self, lines):
        return sorted({c for c, _ in cc.check_trace(lines, TABLE)[0]})

    def test_good_trace(self):
        errs, summary = cc.check_trace(GOOD, TABLE)
        self.assertEqual(errs, [])
        self.assertEqual((summary["ms_cue"], summary["ms_cue_sets"]), (4, 3))
        self.assertEqual(summary["ms_cue_sources"], {"trail": 2, "canonical": 1, "straight": 1})

    def test_overflowing_seq_and_speed(self):
        sched = cc.move_schedule(moves(9, 9), P)
        lines = [ms_line(5, "f%d" % i, i, 9, "move", 9, "trail", round(e["start"]), round(e["ms"]), int(e["snapped"]))
                 for i, e in enumerate(sched)]
        self.assertEqual(self.codes(lines), [])
        slow = cc.move_schedule(moves(1, 2), P, mul=1.5)[0]
        self.assertEqual(self.codes([ms_line(6, "a", 0, 1, "move", 2, "trail", 0, round(slow["ms"]), 0, extra=" speed=slow")]), [])
        self.assertEqual(self.codes([ms_line(7, "a", 0, 1, "move", 2, "trail", 0, 0, 1, extra=" reduced=1")]), [])

    def test_format_errors(self):
        self.assertEqual(self.codes([GOOD[0].replace(" steps=1", ""), GOOD[1]]), ["M1", "M2"])
        self.assertEqual(self.codes([GOOD[3].replace("source=straight", "source=guess")]), ["M1"])
        self.assertEqual(self.codes([GOOD[3] + " speed=turbo"]), ["M1"])

    def test_set_errors(self):
        self.assertEqual(self.codes(GOOD[:1]), ["M2"])                    # набор не завершён
        self.assertEqual(self.codes([GOOD[0], GOOD[3]]), ["M2"])          # прерван другим seq
        self.assertEqual(self.codes([GOOD[0], GOOD[1].replace("order=1", "order=0")]), ["M2"])
        self.assertEqual(self.codes([GOOD[0], GOOD[1].replace("fighter=h1", "fighter=s1")]), ["M2"])
        # один и тот же полный набор дважды (два прогона в одном логе) — не ошибка гейта
        self.assertEqual(self.codes(GOOD[:2] + GOOD[:2]), [])

    def test_steps_and_path_errors(self):
        self.assertEqual(self.codes([GOOD[0].replace("steps=1", "steps=2"), GOOD[1]]), ["M3"])
        self.assertEqual(self.codes([GOOD[3].replace("steps=1", "steps=4")]), ["M3"])
        self.assertEqual(self.codes([GOOD[4].replace("M07>", "")]), ["M3"])

    def test_timing_errors(self):
        self.assertEqual(self.codes([GOOD[0], GOOD[1].replace("ms=840", "ms=900")]), ["M4"])
        self.assertEqual(self.codes([GOOD[0], GOOD[1].replace("start=168", "start=0")]), ["M4"])
        self.assertEqual(self.codes([GOOD[4].replace("snapped=0", "snapped=1")]), ["M4"])
        self.assertEqual(self.codes([GOOD[0], GOOD[1].replace("ms=840", "ms=841")]), [])  # ±1 мс

    def test_cli_min_ms_cue(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "trace.txt"
            log.write_text("\n".join(GOOD) + "\n", encoding="utf-8")
            self.assertEqual(cc.main(["check-trace", str(log), "--min-ms-cue", "4"]), 0)
            self.assertEqual(cc.main(["check-trace", str(log), "--min-ms-cue", "5"]), 1)


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
