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
        t = copy.deepcopy(TABLE); row(t, "CUE-011")["sfx"]["status"] = "present"; cases.append((t, "present без пути"))
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

    def test_instant_hide_and_screen_without_hero_death(self):
        # фигура без клипа и MIC (серая доска): исчезает в кадр падения, без строки dissolve
        lines, gone = self.death(70, "f-1-hero", 9000, hero=True, staged=False, settle=0, still=0, dissolve=0)
        self.assertEqual(gone, 9000)
        screen = "RESULT screen seq=70 t=10000 due=10000 gameOver=9000 heroGone=9000 wait=1000"
        self.assertEqual(cc.check_trace(lines + [screen], TABLE)[0], [])
        # GAME_OVER без смерти героя (например, после реконнекта): экран сразу
        self.assertEqual(cc.check_trace(["RESULT screen seq=3 t=500 due=500 gameOver=500 heroGone=- wait=0"], TABLE)[0], [])


if __name__ == "__main__":
    unittest.main()
