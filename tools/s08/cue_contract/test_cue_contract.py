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
        self.assertIn(("CUE-011", "vfx", row(TABLE, "CUE-011")["vfx"]["missing_reason"]), miss)
        # DE-003: клипы H2Anim есть у всех v2-фигур, в missing-report их нет; у объявления атаки клипа нет (F-03)
        self.assertFalse([m for m in miss if m[1] == "clip"])
        self.assertIsNone(row(TABLE, "CUE-008")["clip"])

    def test_semantic_errors_detected(self):
        cases = []
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["duration_ms"] = 800; cases.append((t, "duration_ms"))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["vfx"]["socket"] = "Tail"; cases.append((t, "сокет"))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["sfx"]["sound"] = None; cases.append((t, "present без пути"))
        t = copy.deepcopy(TABLE); row(t, "CUE-008")["interrupted_by"] = ["CUE-099"]; cases.append((t, "interrupted_by"))
        t = copy.deepcopy(TABLE); r = row(t, "CUE-013"); r["duration_ms"] = 1200; cases.append((t, "P3"))
        t = copy.deepcopy(TABLE); t["cues"] = t["cues"][:-1]; cases.append((t, "07"))
        t = copy.deepcopy(TABLE); clip = row(t, "CUE-011")["clip"]
        clip.update(status="missing", missing_reason="нет", sequence="/Game/A/B.B"); del clip["sequence_by_fighter"]
        cases.append((t, "путь задан"))
        t = copy.deepcopy(TABLE); clip = row(t, "CUE-013")["clip"]
        clip.update(status="missing", missing_reason="нет"); cases.append((t, "путь задан"))  # путь в sequence_by_fighter
        t = copy.deepcopy(TABLE); del row(t, "CUE-011")["clip"]["sequence_by_fighter"]; cases.append((t, "present без пути"))
        if cc.CONTENT_DIR.is_dir():
            t = copy.deepcopy(TABLE); row(t, "CUE-011")["clip"]["sequence_by_fighter"]["Merlin"] = "/Game/Nope/AM_X.AM_X"
            cases.append((t, "нет ассета"))
        for bad, needle in cases:
            errs = cc.validate_table(bad)
            self.assertTrue(any(needle in e for e in errs), (needle, errs))

    def test_clip_by_fighter(self):
        """DE-003: клип своей роли у каждого скелета (FHeroSpec.Key); субъект трассы находит свой клип."""
        d = cc.ReferenceDispatcher(TABLE)
        self.assertEqual(d._asset("CUE-011", "clip", "merlin"), "AM_Merlin_HitReact")
        self.assertEqual(d._asset("CUE-011", "clip", "arthur"), "AM_KingArthur_HitReact")
        self.assertEqual(d._asset("CUE-013", "clip", "harpy2"), "AM_Harpy_DeathSettle")
        self.assertEqual(d._asset("CUE-011", "clip", "dummy"), "missing")
        self.assertEqual(d._asset("CUE-008", "clip", "arthur"), "none")
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["clip"]["sequence_by_fighter"]["bad key"] = "/Game/A/B.B"
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))

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

    def test_cue007_pose(self):
        """DE-021 (01 F-02, D-DE-02): поза хода в таблице — без подскока, наклон 10° за 60 мс, разворот 50, доворот 120,
        возврат в Idle 150, ease выкл; схема и семантика её стерегут (C++ CueTrace сверяет FS08MoveAnimParams с ней)."""
        r = row(TABLE, "CUE-007")
        self.assertEqual(cc.move_pose(r), {"hop_height_rel": 0, "travel_lean_deg": 10, "lean_in_ms": 60, "start_turn_ms": 50,
                                           "turn_ms": 120, "settle_ms": 150, "ease_ends": False})
        t = copy.deepcopy(TABLE); del row(t, "CUE-007")["pose"]
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        t = copy.deepcopy(TABLE); del row(t, "CUE-007")["pose"]["settle_ms"]
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["pose"] = copy.deepcopy(r["pose"])  # поза без шаговой длительности
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        t = copy.deepcopy(TABLE); row(t, "CUE-007")["pose"]["hop_height_rel"] = 0.9
        self.assertTrue(any(e.startswith("schema") for e in cc.validate_table(t)))
        for key in ("lean_in_ms", "start_turn_ms", "turn_ms"):
            t = copy.deepcopy(TABLE); row(t, "CUE-007")["pose"][key] = 400
            errs = cc.validate_table(t)
            self.assertTrue(any("pose." + key in e and not e.startswith("schema") for e in errs), (key, errs))


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



class CombatStagingTests(unittest.TestCase):
    """DE-018: постановка боя `CUE combat …` и удержание внутри CUE-010 (CUE-DISPATCHER.md §3.1, §4 D12, §6)."""

    def fixture(self, name):
        return cc.load_json(cc.FIXTURES / (name + ".json"))

    def test_fight_scale_with_text_is_about_3_9_s(self):
        # 01 F-01 «Резолюция» п. 1: атака без защиты, текст эффекта на карте, 0 сработавших строк — ≈3,9 с ±10 %
        errs, summary = cc.check_trace(self.fixture("combat-staging-text")["expect_trace"], TABLE)
        self.assertEqual(errs, [])
        self.assertEqual(summary["combat_sets"], 1)
        total = summary["combat_totals"][0]
        self.assertTrue(3900 * 0.9 <= total <= 3900 * 1.1, total)
        self.assertEqual(total, 600 + 800 + 1000 + 300 + 292 + 900)

    def test_dropped_read_hold_is_caught_and_skip_is_counted(self):
        lines = [l.replace("text=1", "text=0") for l in self.fixture("combat-staging-text")["expect_trace"]
                 if " stage=read " not in l]
        errs, _ = cc.check_trace(lines, TABLE)
        self.assertIn("C4", {c for c, _ in errs})  # чтение убрано, но слэм/hold остались от текста — гейт видит
        errs, summary = cc.check_trace(self.fixture("combat-staging-lethal-skip")["expect_trace"], TABLE)
        self.assertEqual(errs, [])
        self.assertEqual(summary["combat_skipped"], 1)

    def test_hold_does_not_count_as_input_block(self):
        trace = self.fixture("combat-staging-text")["expect_trace"]
        done10 = next(l for l in trace if "done id=CUE-010" in l)
        self.assertIn("ms=1800", done10)
        self.assertIn("hold=1000", done10)
        # без hold те же 1800 мс — блокирующий CUE длиннее 1 с (G5)
        bad = [l.replace(" hold=1000", "") if l is done10 else l for l in trace]
        self.assertIn("G5", {c for c, _ in cc.check_trace(bad, TABLE)[0]})

    def test_hp_before_contact_and_repeat_seq_are_rejected(self):
        fx = self.fixture("neg-combat-staging")
        codes = sorted({c for c, _ in cc.check_trace(fx["trace"], TABLE)[0]})
        self.assertEqual(codes, sorted(fx["expect_error_codes"]))
        self.assertIn("C2", codes)
        self.assertIn("C5", codes)

    def test_defense_holds_has_no_hit(self):
        trace = self.fixture("combat-staging-defense-holds")["expect_trace"]
        self.assertFalse([l for l in trace if "id=CUE-011" in l or " stage=hit " in l or " stage=minus " in l])
        self.assertTrue(any("outcome=hold" in l for l in trace))
        forged = trace[:-1] + ["CUE combat seq=52 stage=minus t=4532 amount=1 life=900", trace[-1]]
        self.assertIn("C5", {c for c, _ in cc.check_trace(forged, TABLE)[0]})

    def test_lunge_rate_and_minus_life_follow_speed(self):
        # DE-025 (SD-49): play rate выпада = 1 / скорость, «−N» = 900 × скорость; заливка от скорости не зависит
        trace = self.fixture("combat-staging-text")["expect_trace"]
        self.assertTrue(any(" stage=lunge " in l and " rate=1.00" in l for l in trace))
        fast_rate = [l.replace(" rate=1.00", " rate=2.00") if " stage=lunge " in l else l for l in trace]
        self.assertIn("C4", {c for c, _ in cc.check_trace(fast_rate, TABLE)[0]})
        long_minus = [l.replace(" life=900", " life=1350") if " stage=minus " in l else l for l in trace]
        self.assertIn("C5", {c for c, _ in cc.check_trace(long_minus, TABLE)[0]})
        no_rate = [l.replace(" rate=1.00", "") for l in trace]  # трасса до DE-025 без поля rate=
        self.assertEqual(cc.check_trace(no_rate, TABLE)[0], [])

    def test_cut_staging_checks_order_only(self):
        lines = ["CUE combat seq=9 stage=start t=0 attacker=a target=b text=0 lines=0 damage=1 lethal=0 shown=0 "
                 "speed=1.00 flip=620 contact=292 src=default a=3 d=2 outcome=win",
                 "CUE combat seq=9 stage=end t=100 total=700 skipped=0 cut=replace"]
        errs, summary = cc.check_trace(lines, TABLE)
        self.assertEqual(errs, [])
        self.assertEqual((summary["combat_sets"], summary["combat_cut"]), (1, 1))

    def test_reference_model_writes_combat_lines_and_hold(self):
        d = cc.ReferenceDispatcher(TABLE)
        d.feed({"t": 0, "kind": "combat", "seq": 3, "stage": "start", "fields": {"attacker": "a", "target": "b"}})
        d.feed({"t": 0, "kind": "cue", "id": "CUE-010", "subject": "scene", "seq": 3, "hold_ms": 250})
        lines = d.finish()
        self.assertEqual(lines[0], "CUE combat seq=3 stage=start t=0 attacker=a target=b")
        self.assertEqual(lines[-1], "CUE fx done id=CUE-010 subject=scene seq=3 t=1050 ms=1050 cut=0 hold=250")


class CombatEffectLogTests(unittest.TestCase):
    """R-02: строки эффекта боя из журнала сервера `metadata.lastCombat` — `COMBAT-LOG` и гейт C8/C9
    (CUE-DISPATCHER.md §3.1, §5, §6)."""

    def trace(self):
        return list(cc.load_json(cc.FIXTURES / "combat-staging-effect-lines.json")["expect_trace"])

    def with_log(self, lines=2, src="log"):
        log = ("[2026.10.05-12.00.00:000][  0]LogS08: COMBAT-LOG seq=61 log=61 n=4 entries=3 lines=%d src=%s "
               "outcomes=APPLIED:2,NO_TARGETS:1" % (lines, src))
        trace = self.trace()
        i = next(k for k, l in enumerate(trace) if " stage=start " in l)
        return trace[:i] + [log] + trace[i:]

    def test_two_lines_from_the_log_pass_and_are_counted(self):
        # F-01: 600 на строку; пропуск кликом во второй строке режет её, удержание CUE-010 = чтение + строки
        trace = self.trace()
        effects = [l for l in trace if " stage=effect " in l]
        self.assertEqual(len(effects), 2)
        self.assertIn(" i=1 ms=600 skipped=0", effects[0])
        self.assertIn(" i=2 ms=280 skipped=1", effects[1])
        errs, summary = cc.check_trace(self.with_log(), TABLE)
        self.assertEqual(errs, [])
        self.assertEqual((summary["combat_logs"], summary["combat_logs_own"], summary["combat_effect_lines"]), (1, 1, 2))
        self.assertEqual(summary["combat_totals"], [4480])

    def test_lines_must_equal_the_log(self):
        errs, _ = cc.check_trace(self.with_log(lines=1), TABLE)
        self.assertIn("C8", {c for c, _ in errs})

    def test_lines_without_an_own_record_are_rejected(self):
        errs, _ = cc.check_trace(self.with_log(src="other"), TABLE)
        self.assertIn("C8", {c for c, _ in errs})
        errs, _ = cc.check_trace(self.with_log(lines=0, src="none")
                                 + ["COMBAT-LOG seq=70 log=- n=- entries=0 lines=0 src=bogus outcomes=-"], TABLE)
        self.assertIn("C8", {c for c, _ in errs})

    def test_effect_lines_need_the_read_hold(self):
        # lines>0 при text=0: клиент обязан включить чтение, раз эффект карты сработал
        trace = [l.replace(" text=1 ", " text=0 ") for l in self.with_log()]
        msgs = [m for c, m in cc.check_trace(trace, TABLE)[0] if c == "C8"]
        self.assertTrue(any("text=0" in m for m in msgs), msgs)

    def test_r02_client_writes_a_log_before_every_staging(self):
        other = cc.load_json(cc.FIXTURES / "combat-staging-text.json")["expect_trace"]
        errs, _ = cc.check_trace(self.with_log() + list(other), TABLE)
        self.assertIn("C8", {c for c, _ in errs})  # постановка seq 31 без COMBAT-LOG при клиенте R-02
        # трасса до R-02 (нет ни одной строки COMBAT-LOG) — C8 не требует журнала
        self.assertEqual(cc.check_trace(self.trace(), TABLE)[0], [])

    def test_cli_min_effect_lines(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "trace.txt"
            log.write_text("\n".join(self.with_log()) + "\n", encoding="utf-8")
            self.assertEqual(cc.main(["check-trace", str(log), "--min-combat", "1", "--min-effect-lines", "2"]), 0)
            self.assertEqual(cc.main(["check-trace", str(log), "--min-effect-lines", "3"]), 1)


class CatchupTests(unittest.TestCase):
    """R-03: постановка боя, отстающая от применённого состояния, догоняет его — строки `CATCHUP` и гейт C10
    (CUE-DISPATCHER.md §3.1, §5, §6)."""

    CONFIG = "CATCHUP config queued=3 lagMs=1500"

    def hurried(self, reason="combat", lag=280, applied="1"):
        # летальный удар DE-018 с пропуском в паузе: тот же пропуск, но от политики догоняния (src=catchup)
        trace = [l.replace("src=space", "src=catchup")
                 for l in cc.load_json(cc.FIXTURES / "combat-staging-lethal-skip.json")["expect_trace"]]
        return [self.CONFIG] + trace + [
            "CATCHUP seq=41 latest=42 queued=1 lag=%d t=1900 action=hurry reason=%s applied=%s" % (lag, reason, applied)]

    def cut(self, queued=4, latest=24, end_cut="catchup"):
        return [self.CONFIG,
                "CUE combat seq=20 stage=start t=1000 attacker=a target=b text=1 lines=2 damage=2 lethal=0 shown=0 "
                "speed=1.00 flip=620 contact=292 src=notify a=4 d=0 outcome=win",
                "CUE combat seq=20 stage=end t=1400 total=1000 skipped=0 cut=%s" % end_cut,
                "CATCHUP seq=20 latest=%d queued=%d lag=300 t=1400 action=cut reason=queue applied=1" % (latest, queued)]

    def codes(self, lines):
        return {c for c, _ in cc.check_trace(lines, TABLE)[0]}

    def test_short_version_and_cut_pass_and_are_counted(self):
        errs, summary = cc.check_trace(self.hurried(), TABLE)
        self.assertEqual(errs, [])  # C4 видит обычный пропуск: удержания короче только со skipped=1
        self.assertEqual((summary["catchup_hurry"], summary["catchup_cut"], summary["combat_skipped"]), (1, 0, 1))
        errs, summary = cc.check_trace(self.cut(), TABLE)
        self.assertEqual(errs, [])  # cut≠0: C4–C6 не проверяются, как у replace
        self.assertEqual((summary["catchup_cut"], summary["combat_cut"]), (1, 1))

    def test_lag_reason_needs_lag_over_t(self):
        self.assertNotIn("C10", self.codes(self.hurried(reason="lag", lag=1501)))
        self.assertIn("C10", self.codes(self.hurried(reason="lag", lag=1200)))

    def test_queue_reason_needs_more_than_k(self):
        self.assertIn("C10", self.codes(self.cut(queued=3, latest=23)))
        self.assertIn("C10", self.codes(self.cut(queued=2, latest=24)))  # queued ≠ latest − seq

    def test_skip_and_cut_need_their_catchup_line_and_back(self):
        hurried = self.hurried()
        self.assertIn("C10", self.codes(hurried[:-1]))  # skip src=catchup без строки CATCHUP
        self.assertIn("C10", self.codes([l for l in hurried if " stage=skip " not in l]))  # CATCHUP без skip
        self.assertIn("C10", self.codes(self.cut(end_cut="replace")))  # cut без end cut=catchup
        self.assertIn("C10", self.codes(self.cut()[:-1]))  # end cut=catchup без строки CATCHUP
        # applied=0: удержания уже кончились, постановка не менялась — skip не нужен
        self.assertNotIn("C10", self.codes([l.replace("src=catchup", "src=space") for l in self.hurried(applied="0")]))

    def test_format_reason_and_once_per_seq(self):
        self.assertIn("C10", self.codes([self.CONFIG, "CATCHUP seq=5 latest=6 queued=1 t=10 action=hurry reason=lag applied=1"]))
        self.assertIn("C10", self.codes(self.hurried()[:-1] + [
            "CATCHUP seq=41 latest=42 queued=1 lag=280 t=1900 action=cut reason=combat applied=0"]))
        self.assertIn("C10", self.codes(self.hurried() + [
            "CATCHUP seq=41 latest=43 queued=2 lag=380 t=2000 action=hurry reason=combat applied=0"]))
        self.assertIn("C10", self.codes(["CATCHUP config queued=x lagMs=1500"]))


class DeathStageTests(unittest.TestCase):
    """DE-019: смерть по этапам `CUE death …` и экран результата `RESULT screen …` (01 F-09, CUE-DISPATCHER.md §6)."""

    def staged(self):
        # летальный удар Medusa по Merlin (контакт 2233, этап fall 2683) из фикстуры DE-018
        return list(cc.load_json(cc.FIXTURES / "combat-staging-lethal-skip.json")["expect_trace"])

    @staticmethod
    def death(seq, fighter, fall, hero, staged, settle=875, still=None, dissolve=None, style="fade"):
        still = (300 if hero else 0) if still is None else still
        dissolve = (500 if hero else 400) if dissolve is None else dissolve
        style = "none" if dissolve == 0 else style
        gone = fall + settle + still + dissolve
        lines = ["CUE death seq=%d stage=fall t=%d fighter=%s hero=%d staged=%d settle=%d still=%d dissolve=%d style=%s gone=%d"
                 % (seq, fall, fighter, int(hero), int(staged), settle, still, dissolve, style, gone),
                 "CUE death seq=%d stage=mark t=%d fighter=%s heart=dark" % (seq, fall + 650, fighter)]
        if dissolve:
            lines.append("CUE death seq=%d stage=dissolve t=%d fighter=%s ms=%d style=%s"
                         % (seq, fall + settle + still, fighter, dissolve, style))
        lines.append("CUE death seq=%d stage=gone t=%d fighter=%s" % (seq, gone, fighter))
        lines.sort(key=lambda l: int(l.split(" t=")[1].split()[0]))
        return lines, gone

    def test_sidekick_death_from_the_staged_fall(self):
        lines, gone = self.death(41, "merlin", 2683 + 17, hero=False, staged=True)
        errs, summary = cc.check_trace(self.staged() + lines, TABLE)
        self.assertEqual(errs, [])
        self.assertEqual((summary["death_sets"], summary["death_heroes"]), (1, 0))
        self.assertEqual(gone - 2233, 1725 + 17)  # помощник ≈1725 мс от контакта (+ кадр запуска)

    def test_hero_death_and_result_screen_3_1_s(self):
        trace = [l.replace("target=merlin", "target=arthur").replace("subject=merlin", "subject=arthur")
                 for l in self.staged()]
        lines, gone = self.death(41, "arthur", 2683, hero=True, staged=True)
        self.assertEqual(gone - 2233, 2125)
        screen = "RESULT screen seq=41 t=%d due=%d gameOver=1000 heroGone=%d wait=%d" % (
            gone + 1000 + 16, gone + 1000, gone, gone + 1016 - 1000)
        errs, summary = cc.check_trace(trace + lines + [screen], TABLE)
        self.assertEqual(errs, [])
        self.assertEqual(summary["result_screens"], 1)
        self.assertEqual(summary["hit_to_screen"], [3125 + 16])

    def test_old_hold_early_screen_and_unstaged_fall_are_caught(self):
        # старое удержание 2,0 с вместо 300 мс — DS3
        lines, _ = self.death(41, "merlin", 2683, hero=False, staged=True, still=2000)
        self.assertIn("DS3", {c for c, _ in cc.check_trace(self.staged() + lines, TABLE)[0]})
        # экран раньше исчезновения героя + 1000 — DS5
        lines, gone = self.death(52, "arthur", 5000, hero=True, staged=False)
        early = "RESULT screen seq=52 t=%d due=%d gameOver=4900 heroGone=%d wait=%d" % (gone + 200, gone + 200, gone,
                                                                                        gone + 200 - 4900)
        self.assertIn("DS5", {c for c, _ in cc.check_trace(lines + [early], TABLE)[0]})
        # staged=1 без этапа fall постановки — DS4; второе падение того же бойца — DS2
        lines, _ = self.death(60, "harpy1", 7000, hero=False, staged=True)
        self.assertIn("DS4", {c for c, _ in cc.check_trace(lines, TABLE)[0]})
        self.assertIn("DS2", {c for c, _ in cc.check_trace(lines + lines[:1], TABLE)[0]})

    def test_snapshot_death_waits_for_the_staging_still_playing(self):
        # ревью IMPL 2026-10-05 (хвост DE-019): смерть staged=0 при ещё играющей постановке предыдущего seq —
        # экран ждёт её конца, клиент пишет staging=<ms>; экран t = staging — PASS
        lines, gone = self.death(52, "arthur", 5000, hero=True, staged=False)
        staging = gone + 1000 + 233
        held = "RESULT screen seq=52 t=%d due=%d gameOver=4900 heroGone=%d wait=%d staging=%d" % (
            staging, staging, gone, staging - 4900, staging)
        self.assertEqual(cc.check_trace(lines + [held], TABLE)[0], [])
        # экран раньше конца постановки при staging — DS5
        early = "RESULT screen seq=52 t=%d due=%d gameOver=4900 heroGone=%d wait=%d staging=%d" % (
            gone + 1000, gone + 1000, gone, gone + 1000 - 4900, staging)
        self.assertIn("DS5", {c for c, _ in cc.check_trace(lines + [early], TABLE)[0]})
        # токен staging не позже обычного due — лишний, DS5
        idle = "RESULT screen seq=52 t=%d due=%d gameOver=4900 heroGone=%d wait=%d staging=%d" % (
            gone + 1000, gone + 1000, gone, gone + 1000 - 4900, gone + 500)
        self.assertIn("DS5", {c for c, _ in cc.check_trace(lines + [idle], TABLE)[0]})

    def test_instant_hide_and_screen_without_hero_death(self):
        # фигура без клипа и MIC (серая доска): исчезает в кадр падения, без строки dissolve
        lines, gone = self.death(70, "f-1-hero", 9000, hero=True, staged=False, settle=0, still=0, dissolve=0)
        self.assertEqual(gone, 9000)
        screen = "RESULT screen seq=70 t=10000 due=10000 gameOver=9000 heroGone=9000 wait=1000"
        self.assertEqual(cc.check_trace(lines + [screen], TABLE)[0], [])
        # GAME_OVER без смерти героя (например, после реконнекта): экран сразу
        self.assertEqual(cc.check_trace(["RESULT screen seq=3 t=500 due=500 gameOver=500 heroGone=- wait=0"], TABLE)[0], [])


def snd(cid, point, t, seq="-", subject="-", cls=None, sound="missing", gain="1.00", result="fallback", ev=None,
        extra=""):
    """Строка `CUE sound …` в формате FS08CueSound::Play (S08CueSoundTests.cpp пишет те же строки)."""
    cls = cls or row(TABLE, cid)["sfx"]["sound_class"]
    ev = t if ev is None else ev
    line = ("LogS08: CUE sound id=%s point=%s subject=%s seq=%s t=%d event_t=%d dt=%d class=%s sound=%s gain=%s "
            "result=%s" % (cid, point, subject, seq, t, ev, t - ev, cls, sound, gain, result))
    return line + (" " + extra if extra else "")


AUDIO_START = ("CUE audio master=100 master_mute=0 ambience=60 ambience_mute=0 gain_master=1.00 gain_ambience=0.60 "
               "t=0 applied=start")


class SoundGateTests(unittest.TestCase):
    """DE-032: звук точек синхронизации (CUE-DISPATCHER.md §3.2, гейт AU1–AU10)."""

    def good(self):
        return [
            AUDIO_START,
            snd("CUE-003", "ui", 1000, seq="12", subject="hud.endturn"),
            snd("CUE-004", "ui", 1100, seq="12"),
            snd("CUE-004", "ui", 1250, seq="12", sound="none", result="throttled"),
            snd("CUE-004", "ui", 1400, seq="12"),
            snd("CUE-007", "step", 1500, seq="20", subject="arthur", extra="edge=1/3 due=1500"),
            snd("CUE-007", "step", 1790, seq="20", subject="arthur", extra="edge=2/3 due=1780"),
            snd("CUE-007", "step", 2070, seq="20", subject="arthur", extra="edge=3/3 due=2060"),
            snd("CUE-007", "step", 2100, seq="21", subject="medusa", extra="edge=snap due=2100"),
            "HUD-TURN seq=30 turn=opp initial=0 ring=none flash=0 banner=0 reduced=0",
            snd("CUE-015", "turn", 3000, seq="30", sound="none", result="silent", extra="turn=opp reason=opponent"),
            "HUD-TURN seq=34 turn=own initial=0 ring=none flash=0 banner=600 reduced=0",
            snd("CUE-015", "turn", 3500, seq="34", extra="turn=own"),
            "CUE audio master=50 master_mute=0 ambience=60 ambience_mute=1 gain_master=0.50 gain_ambience=0.00 "
            "t=4000 applied=change",
            snd("CUE-011", "hit", 5000, seq="41", subject="medusa", gain="0.50"),
            "RESULT screen seq=50 t=9000 due=9000 gameOver=9000 heroGone=- wait=0",
            snd("CUE-016", "result", 9000, seq="50", gain="0.50"),
        ]

    def codes(self, lines):
        return {c for c, _ in cc.check_sound(lines, TABLE)[0]}

    def test_good_trace_passes_the_whole_gate(self):
        errs, summary = cc.check_trace(self.good(), TABLE)
        self.assertEqual(errs, [])
        self.assertEqual(summary["sounds"], 12)
        self.assertEqual(summary["sound_points"], {"ui": 4, "hit": 1, "step": 4, "turn": 2, "result": 1, "cue": 0})
        self.assertEqual((summary["sound_fallback"], summary["sound_silent"], summary["sound_throttled"]), (10, 1, 1))
        self.assertEqual(summary["audio_lines"], 2)
        self.assertEqual(summary["sound_dt_max"], 0)

    def test_bus_gains_cue_point_and_grouped_hits(self):
        """AU-S4: gain = master x bus of the class; the cue point; one sound per frame of hits, the rest grouped."""
        audio = ("CUE audio master=100 master_mute=0 ambience=60 ambience_mute=0 gain_master=1.00 gain_ambience=0.60 "
                 "music=60 sfx=80 ui=80 vo=80 subtitles=1 t=0 applied=start")
        good = [audio,
                snd("CUE-003", "ui", 1000, gain="0.80"),
                snd("CUE-008", "cue", 1100, seq="40", subject="arthur", sound="SW_CMB_ATTACK_DECLARE_01", gain="0.80",
                    result="played"),
                "CUE combat seq=41 stage=contact t=2000 offset=292 window=900 src=notify",
                snd("CUE-011", "hit", 2000, seq="41", subject="medusa", sound="SW_CMB_HIT_MULTI_01", gain="0.80",
                    result="played", extra="bank=CMB-HIT-MULTI due=2000"),
                snd("CUE-011", "hit", 2000, seq="41", subject="harpy1", sound="none", gain="0.80", result="silent",
                    extra="bank=CMB-HIT-MULTI due=2000 reason=grouped"),
                "RESULT screen seq=50 t=9000 due=9000 gameOver=9000 heroGone=- wait=0",
                snd("CUE-016", "result", 9000, seq="50", sound="SW_STG_WIN_ARTHUR", gain="0.60", result="played",
                    extra="bank=STG-WIN-ARTHUR")]
        self.assertEqual(self.codes(good), set())
        # the old gain (master only) is wrong now for a UI sound at 80 %
        self.assertIn("AU8", self.codes([audio, snd("CUE-003", "ui", 1000, gain="1.00")]))
        # a grouped reason outside a hit
        self.assertIn("AU4", self.codes([audio, snd("CUE-003", "ui", 1000, sound="none", gain="0.80", result="silent",
                                                    extra="reason=grouped")]))
        # a trace without the bus fields keeps the old rule (100 %)
        self.assertEqual(self.codes([AUDIO_START, snd("CUE-003", "ui", 1000, gain="1.00")]), set())

    def test_sound_off_the_event_frame(self):
        self.assertIn("AU2", self.codes([AUDIO_START, snd("CUE-003", "ui", 1033, ev=1000)]))
        self.assertEqual(self.codes([AUDIO_START, snd("CUE-003", "ui", 1016, ev=1000)]), set())

    def test_opponent_turn_must_be_silent_and_match_hud_turn(self):
        self.assertIn("AU3", self.codes([AUDIO_START, snd("CUE-015", "turn", 3000, seq="30", extra="turn=opp")]))
        no_chime = ["HUD-TURN seq=34 turn=own initial=0 ring=none flash=0 banner=600 reduced=0", AUDIO_START]
        self.assertIn("AU3", self.codes(no_chime))
        # initial (вход посреди хода): без баннера и без перезвона
        self.assertEqual(self.codes(["HUD-TURN seq=2 turn=own initial=1 ring=none flash=0 banner=0 reduced=0"]), set())

    def test_sound_token_and_result_agree(self):
        self.assertIn("AU4", self.codes([AUDIO_START, snd("CUE-003", "ui", 10, sound="SW_Click")]))
        self.assertEqual(self.codes([AUDIO_START, snd("CUE-003", "ui", 10, sound="SW_Click", result="played")]), set())

    def test_hit_on_the_contact_frame(self):
        contact = "CUE combat seq=24 stage=contact t=2000 offset=292 window=900 src=notify"
        ok = snd("CUE-011", "hit", 2016, seq="24", subject="medusa", extra="due=2000")
        self.assertEqual(self.codes([AUDIO_START, contact, ok]), set())
        # при применении снапшота (до контакта) — AU5; второй удар той же цели — AU5
        early = snd("CUE-011", "hit", 1500, seq="24", subject="medusa", extra="due=1500")
        self.assertIn("AU5", self.codes([AUDIO_START, contact, early]))
        self.assertIn("AU5", self.codes([AUDIO_START, contact, ok, ok]))
        wrong_due = snd("CUE-011", "hit", 2016, seq="24", subject="medusa", extra="due=1990")
        self.assertIn("AU5", self.codes([AUDIO_START, contact, wrong_due]))
        # удар без постановки (каскад после перемещения) того же seq — в свой кадр, без due
        cascade = snd("CUE-011", "hit", 2500, seq="24", subject="harpy1")
        self.assertEqual(self.codes([AUDIO_START, contact, ok, cascade]), set())

    def test_one_step_per_edge_unless_dropped(self):
        lines = [AUDIO_START, snd("CUE-007", "step", 1500, seq="20", subject="arthur", extra="edge=1/3 due=1500")]
        self.assertIn("AU6", self.codes(lines))
        dropped = lines + ["CUE sound drop point=step seq=20 fighter=* t=1600 count=2 reason=skip"]
        self.assertEqual(self.codes(dropped), set())
        twice = lines + [lines[1]]
        self.assertIn("AU6", self.codes(twice + ["CUE sound drop point=step seq=20 fighter=arthur t=1600 count=1 "
                                                 "reason=replace"]))
        late = [AUDIO_START, snd("CUE-007", "step", 1700, seq="22", subject="arthur", extra="edge=snap due=1500")]
        self.assertIn("AU6", self.codes(late))

    def test_late_frame_after_evidence_shot_is_counted_not_failed(self):
        # G-LIVE прогона G: снимок доказательств остановил кадр на ~250 мс, первое ребро второй фигуры
        # прозвучало в первом кадре после снимка (t − due = 154) — счётчик sound_late_shot, не AU6
        shot = "SHOT captured file=s09-opponent-move.png frame=704 px=1920x1080 sha256=x order=BGRA saved=1"
        prev = snd("CUE-007", "step", 24588, seq="7", subject="hero", extra="edge=1/1 due=24568")
        stalled = snd("CUE-007", "step", 24834, seq="7", subject="sk0", extra="edge=1/1 due=24680")
        errs, summary = cc.check_sound([AUDIO_START, prev, shot, stalled], TABLE)
        self.assertEqual(errs, [])
        self.assertEqual(summary["sound_late_shot"], 1)
        # без снимка — AU6; снимок задолго до due или звук позже первого кадра после снимка — тоже AU6
        self.assertIn("AU6", self.codes([AUDIO_START, prev, stalled]))
        early_shot = [AUDIO_START, snd("CUE-007", "step", 20000, seq="6", subject="hero", extra="edge=1/1 due=20000"),
                      shot, snd("CUE-007", "step", 20040, seq="6", subject="sk0", extra="edge=1/1 due=20040"), stalled]
        self.assertIn("AU6", self.codes(early_shot))
        much_later = snd("CUE-007", "step", 24990, seq="7", subject="sk1", extra="edge=1/1 due=24680")
        self.assertIn("AU6", self.codes([AUDIO_START, prev, shot, stalled, much_later]))
        # удар постановки в первом кадре после снимка — так же
        contact = "CUE combat seq=24 stage=contact t=2000 offset=292 window=900 src=notify"
        hit = snd("CUE-011", "hit", 2180, seq="24", subject="medusa", extra="due=2000")
        self.assertEqual(self.codes([AUDIO_START, contact, shot, hit]), set())
        self.assertIn("AU5", self.codes([AUDIO_START, contact, hit]))
        # AU-S6: the late-shot queue of run I - lines of the shot's own frame follow the capture (same t), the
        # stall shows in the next frame; `SHOT late end` closes a capture the same way
        same_frame = snd("CUE-010", "cue", 24588, seq="7", subject="card.attack")
        errs, summary = cc.check_sound([AUDIO_START, prev, shot, same_frame, stalled], TABLE)
        self.assertEqual(errs, [])
        self.assertEqual(summary["sound_late_shot"], 1)
        late_end = "SHOT late end file=s09-no-defense-stamp.png frame=1585"
        errs, summary = cc.check_sound([AUDIO_START, prev, late_end, same_frame, stalled], TABLE)
        self.assertEqual(errs, [])
        self.assertEqual(summary["sound_late_shot"], 1)
        # still AU6 without a shot, or with the sound later than the first frame after it
        self.assertIn("AU6", self.codes([AUDIO_START, prev, same_frame, stalled]))
        self.assertIn("AU6", self.codes([AUDIO_START, prev, late_end, same_frame, stalled, much_later]))

    def test_result_sting_with_the_screen(self):
        screen = "RESULT screen seq=50 t=9000 due=9000 gameOver=9000 heroGone=- wait=0"
        self.assertIn("AU7", self.codes([AUDIO_START, screen]))
        self.assertIn("AU7", self.codes([AUDIO_START, snd("CUE-016", "result", 9000, seq="50")]))

    def test_volumes_apply_to_the_next_sound(self):
        self.assertIn("AU8", self.codes([snd("CUE-003", "ui", 10)]))  # звук до CUE audio
        change = ("CUE audio master=50 master_mute=0 ambience=60 ambience_mute=0 gain_master=0.50 gain_ambience=0.30 "
                  "t=100 applied=change")
        self.assertEqual(self.codes([AUDIO_START, change, snd("CUE-003", "ui", 200, gain="0.50")]), set())
        self.assertIn("AU8", self.codes([AUDIO_START, change, snd("CUE-003", "ui", 200, gain="1.00")]))
        bad_formula = change.replace("gain_ambience=0.30", "gain_ambience=0.60")
        self.assertIn("AU8", self.codes([AUDIO_START, bad_formula]))
        muted = AUDIO_START.replace("master_mute=0", "master_mute=1").replace("gain_master=1.00", "gain_master=0.00") \
            .replace("gain_ambience=0.60", "gain_ambience=0.00")
        self.assertEqual(self.codes([muted, snd("CUE-016", "result", 10, sound="none", gain="0.00", result="silent",
                                                extra="reason=muted")]
                                    + ["RESULT screen seq=1 t=10 due=10 gameOver=10 heroGone=- wait=0"]), set())
        self.assertIn("AU8", self.codes([muted, snd("CUE-003", "ui", 10, gain="0.00")]))

    def test_retrigger(self):
        self.assertIn("AU9", self.codes([AUDIO_START, snd("CUE-004", "ui", 100), snd("CUE-004", "ui", 200)]))
        self.assertIn("AU9", self.codes([AUDIO_START, snd("CUE-004", "ui", 100),
                                         snd("CUE-004", "ui", 500, sound="none", result="throttled")]))

    def test_cli_min_sound(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "trace.log"
            log.write_text("\n".join(self.good()) + "\n", encoding="utf-8")
            self.assertEqual(cc.main(["check-trace", str(log), "--min-sound", "12"]), 0)
            self.assertEqual(cc.main(["check-trace", str(log), "--min-sound", "13"]), 1)


if __name__ == "__main__":
    unittest.main()
