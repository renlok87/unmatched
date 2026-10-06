"""Тесты правил HUD без движка.  Run from the repo root:  python -m unittest discover -s tools/s08/hud_contract -v"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hud_contract as hc  # noqa: E402

SPEC02 = hc.SPEC02.read_text(encoding="utf-8")
TOKENS = hc.load(hc.TOKENS)
WHY = hc.load(hc.WHY)


class HudContractTests(unittest.TestCase):
    def test_tokens_and_why_valid(self):
        self.assertEqual(hc.validate_tokens(TOKENS), [])
        self.assertEqual(hc.validate_why(WHY, SPEC02), [])

    def test_why_keys_follow_02(self):
        self.assertEqual({r["key"] for r in WHY["reasons"]}, set(hc.WHY_02_RE.findall(SPEC02)))
        bad = copy.deepcopy(WHY)
        bad["reasons"][3]["ru"] = "Только для героя"  # потерян аргумент {bannerName}
        self.assertTrue(any("аргументы" in e for e in hc.validate_why(bad, SPEC02)))
        bad = copy.deepcopy(WHY)
        bad["reasons"].pop()
        self.assertTrue(any("02 §4.2" in e for e in hc.validate_why(bad, SPEC02)))

    def test_token_errors(self):
        bad = copy.deepcopy(TOKENS)
        bad["colors"]["team.p1"]["hex"] = "E8C06A"
        bad["spacing"]["space.s"]["px"] = 0
        errs = hc.validate_tokens(bad)
        self.assertTrue(any("team.p1" in e for e in errs) and any("space.s" in e for e in errs))

    def test_srgb_to_linear_reference_for_ad_open_39(self):
        # 17 AD-OPEN-39 сравнивает #3D7BDB/255 = 0.24/0.48/0.86 с измеренным MI_S05_ZoneBlue (0.18, 0.36, 0.70),
        # tools/s05/s05_import_scene.py:417. Тест проверяет только справку: кривая sRGB даёт 0.047/0.198/0.708,
        # ни одно из двух значений S05 с ней не совпадает. Текст 17 этим тестом не опровергается.
        r, g, b = hc.hex_to_linear("#3D7BDB")
        self.assertAlmostEqual(r, 0.0467, places=3)
        self.assertAlmostEqual(g, 0.1981, places=3)
        self.assertAlmostEqual(b, 0.7083, places=3)
        self.assertEqual(hc.hex_to_linear("#FFFFFF"), (1.0, 1.0, 1.0))

    def test_widget_trace_gate(self):
        ids = hc.ui_ids_from_02(SPEC02)
        self.assertIn("UI-HUD-HAND", ids)
        good = ["LogUnmatched: SHOT widget id=UI-HUD-HAND state=maneuver bbox=560,860,800,200 geom=painted visible=1"]
        self.assertEqual(hc.check_widget_trace(good, ids), ([], 1))
        bad = ["SHOT widget id=UI-HUD-NOPE state=x bbox=1900,1000,100,100 geom=unpainted visible=1",
               "SHOT widget id=UI-HUD-HAND bbox=1,1,1,1 geom=painted"]
        errs, seen = hc.check_widget_trace(bad, ids)
        self.assertEqual(seen, 2)
        self.assertTrue(any("неизвестный" in e for e in errs))
        self.assertTrue(any("geom=unpainted" in e for e in errs))
        self.assertTrue(any("вне кадра" in e for e in errs))
        self.assertTrue(any("state" in e for e in errs))

    def test_layout_trace_gate(self):
        # VS-2 HB-06: HUD-LAYOUT once per shot frame; overlapField of the persistent blocks must be 0
        ids = hc.ui_ids_from_02(SPEC02)
        good = ["2026.10.06 HUD-LAYOUT class=L canvas=1920x1080 scale=1.000 field=(466,258,995,599) overlapField=0 "
                "window=1920x1080 hand=376..1540 handVisible=193 crossing=-"]
        self.assertEqual(hc.check_widget_trace(good, ids), ([], 0))
        bad = ["HUD-LAYOUT class=S canvas=1138x640 scale=1.125 field=(223,153,690,361) overlapField=796 crossing=opphand",
               "HUD-LAYOUT class=X canvas=1x1 scale=1 overlapField=0"]
        errs, _ = hc.check_widget_trace(bad, ids)
        self.assertTrue(any("overlapField=796" in e and "opphand" in e for e in errs))
        self.assertTrue(any("class=X" in e for e in errs))
        self.assertTrue(any("без поля field" in e for e in errs))


if __name__ == "__main__":
    unittest.main()


def test_check_trace_portrait_cp08():
    """VS-2 CP-08 (ВР-CP10): PORTRAIT lines - scale <= 1.6, no monogram for a key the registry has."""
    reg = hc.registry_portrait_keys()
    assert {"king-arthur", "medusa", "king-arthur/merlin", "medusa/harpies"} <= reg
    ok = ["PORTRAIT id=king-arthur tex=/Game/S08/UI/Portraits/T_Portrait_king_arthur.T_Portrait_king_arthur su=42.0 "
          "px=84.0 scale=0.175 show=panel side=own state=avatar",
          "PORTRAIT id=none tex=monogram su=42.0 px=42.0 scale=0.000 show=panel side=own state=avatar",
          "PORTRAIT id=king-arthur/merlin tex=/Game/x su=38.4 px=153.6 scale=1.600 show=panel side=own state=avatar"]
    errors, _ = hc.check_widget_trace(ok, set(), registry=reg)
    assert errors == []
    bad = ["PORTRAIT id=king-arthur/merlin tex=/Game/x su=42.0 px=168.0 scale=1.750 show=panel side=own state=avatar",
           "PORTRAIT id=medusa tex=monogram su=42.0 px=42.0 scale=0.000 show=panel side=opp state=avatar"]
    errors, _ = hc.check_widget_trace(bad, set(), registry=reg)
    assert len(errors) == 2 and "1.6" in errors[0] and "monogram" in errors[1]
