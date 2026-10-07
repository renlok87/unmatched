"""VS-1 HB-05: tests of the HUD string tables builder (keys of 04, duplicates, RU/EN, plural, ВР-H09 delta, PO).

  python -m pytest tools/s08/hud_contract/test_hud_strings_build.py -q
"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hud_strings_build as hs  # noqa: E402

ROWS = hs.all_rows()


class RepoTests(unittest.TestCase):
    def test_check_passes_zero_missing_zero_duplicates(self):
        errors, stats = hs.check()
        self.assertEqual(errors, [])
        self.assertEqual(stats["missing04"], 0)
        self.assertEqual(stats["dup"], 0)
        self.assertEqual(stats["clarify"], 0)
        self.assertLessEqual(stats["bytes"], hs.BUDGET_BYTES)

    def test_tables_and_namespaces(self):
        self.assertEqual({n: t["namespace"] for n, t in hs.TABLES.items()},
                         {"ST_Hud": "hud", "ST_Screens": "screens", "ST_Ms": "ms", "ST_Why": "why"})
        self.assertEqual(len(ROWS["ST_Why"]), 49)  # 40 + 8 screen reasons of 04 §6.1 + why.defense.pick (VS-3 HB-30)
        for key in ("why.login.fields", "why.code.length", "why.room.started", "why.room.full", "why.hero.taken",
                    "why.room.not.ready", "why.room.no.hero", "why.room.board.locked"):
            self.assertIn(key, {r["Key"] for r in ROWS["ST_Why"]})

    def test_acceptance_strings(self):
        hud = {r["Key"]: r for r in ROWS["ST_Hud"]}
        self.assertEqual((hud["hud.hand.count"]["SourceString"], hud["hud.hand.count"]["ru"]), ("Hand {n}/{max}", "Рука {n}/{max}"))
        deck = {r["Key"]: r for r in ROWS["ST_Screens"]}["screens.room.deck.count"]["ru"]
        self.assertIn("{n}|plural(one=карта,few=карты,many=карт,other=карты)", deck)

    def test_st_ms_is_03_with_the_vr_h09_delta(self):
        self.assertEqual([(r["Key"], r["SourceString"], r["ru"]) for r in ROWS["ST_Ms"]],
                         [(r["Key"], r["SourceString"], r["ru"]) for r in hs.expected_ms_rows()])
        ms = {r["Key"]: r for r in ROWS["ST_Ms"]}
        self.assertEqual(ms["ms.status.action"]["ru"], "Выберите действие: манёвр, атака или схема")  # 04 §2.5 example
        self.assertEqual(ms["ms.status.space"]["SourceString"], "Choose a space for {fighterName}")
        self.assertEqual(ms["ms.btn.begin"]["ru"], "Начать манёвр (M)")  # only ms.status.* lose the key (04 §6.1)
        self.assertNotIn("бойц(а/ов)", ms["ms.btn.confirm"]["ru"])


class ParserTests(unittest.TestCase):
    def test_keys_from_04_shorthand_alternation_wildcards(self):
        text = ("- **Строки:** `screens.login.title`, `.email`, `.error.credentials`.\n"
                "- **Строки:** `hud.inspect.close`, `.type.attack|defense`, `settings.*`, `hud.key.<действие>`.\n"
                "| x | `ms.status.attacker`, `.target`, `.attack.card` | `. ` |\n")
        exact, wild = hs.keys_from_04(text)
        self.assertEqual(set(exact), {"screens.login.title", "screens.login.email", "screens.login.error.credentials",
                                      "hud.inspect.close", "hud.inspect.type.attack", "hud.inspect.type.defense",
                                      "ms.status.attacker", "ms.status.target", "ms.status.attack.card"})
        self.assertEqual(set(wild), {"settings.", "hud.key."})

    def test_ms_delta(self):
        self.assertEqual(hs.ms_delta("ms.status.defend", "Вас атакуют: выберите карту защиты или «Без защиты» (N)", "ru"),
                         "Вас атакуют: выберите карту защиты или «Без защиты»")
        self.assertEqual(hs.ms_delta("ms.status.space", "Выберите клетку для {fighterName}; Enter — подтвердить манёвр", "ru"),
                         "Выберите клетку для {fighterName}")
        self.assertEqual(hs.ms_delta("ms.btn.undo", "Отменить шаг (Backspace)", "ru"), "Отменить шаг (Backspace)")
        self.assertEqual(hs.ms_delta("ms.btn.confirm.noboost", "Confirm: {n} fighter(s) (Enter)", "en"),
                         "Confirm: {n} {n}|plural(one=fighter,other=fighters) (Enter)")


class CheckErrorTests(unittest.TestCase):
    def errors_with(self, mutate):
        rows = copy.deepcopy(ROWS)
        mutate(rows)
        return hs.check(rows)[0]

    def test_duplicate_key(self):
        errs = self.errors_with(lambda r: r["ST_Hud"].append(dict(r["ST_Hud"][0])))
        self.assertTrue(any("дубль" in e for e in errs))

    def test_missing_04_key(self):
        errs = self.errors_with(lambda r: r.__setitem__("ST_Hud", [x for x in r["ST_Hud"] if x["Key"] != "hud.top.turn"]))
        self.assertTrue(any("hud.top.turn" in e and "04" in e for e in errs))

    def test_empty_ru_is_an_error_and_clarify_is_counted(self):
        def empty(r):
            r["ST_Hud"][0]["ru"] = ""
        self.assertTrue(any("пустой RU" in e for e in self.errors_with(empty)))
        rows = copy.deepcopy(ROWS)
        rows["ST_Hud"][0]["ru"] = hs.CLARIFY
        errors, stats = hs.check(rows)
        self.assertEqual((errors, stats["clarify"]), ([], 1))

    def test_args_and_plural_forms(self):
        def bad_args(r):
            row = next(x for x in r["ST_Hud"] if x["Key"] == "hud.hand.count")
            row["ru"] = "Рука {n}"
        self.assertTrue(any("аргументы" in e for e in self.errors_with(bad_args)))

        def bad_plural(r):
            row = next(x for x in r["ST_Screens"] if x["Key"] == "screens.room.deck.count")
            row["ru"] = "Колода: {n} {n}|plural(one=карта,other=карт)"
        self.assertTrue(any("plural" in e for e in self.errors_with(bad_plural)))

    def test_wrong_namespace(self):
        def move(r):
            r["ST_Screens"].append({"Key": "hud.extra.key", "SourceString": "x", "ru": "х", "ref": ""})
        self.assertTrue(any("не своего пространства" in e for e in self.errors_with(move)))


class PoTests(unittest.TestCase):
    def test_unreal_po_format(self):
        po = hs.render_po({"ST_Hud": [{"Key": "hud.hand.count", "SourceString": 'Hand {n}/{max} "x"', "ru": "Рука {n}/{max}"}]})
        self.assertIn('msgctxt "hud,hud.hand.count"', po)
        self.assertIn('msgid "Hand {n}/{max} \\"x\\""', po)
        self.assertIn('msgstr "Рука {n}/{max}"', po)
        self.assertIn('"Language: ru\\n"', po)

    def test_ue_csv(self):
        text = hs.ue_csv([{"Key": "hud.a", "SourceString": "A, b"}])
        self.assertEqual(text, '"Key","SourceString"\n"hud.a","A, b"\n')


if __name__ == "__main__":
    unittest.main()
