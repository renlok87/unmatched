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

    def test_layout_trace_deck_panel_gate(self):
        # VS-3 HB-28: the deck panel never covers a block shown with it (STATUS two lines incl., VS-2 open item 3);
        # the class S transient overlap is measured only
        ids = hc.ui_ids_from_02(SPEC02)
        good = ["HUD-LAYOUT class=S canvas=1138x640 scale=1.125 field=(223,153,690,361) overlapField=0 window=1280x720 "
                "hand=268..898 handVisible=90 crossing=- deckpanel=(821.8,120,300,392) deckpanelBlocks=0 "
                "deckpanelTransient=31500"]
        self.assertEqual(hc.check_widget_trace(good, ids), ([], 0))
        bad = ["HUD-LAYOUT class=S canvas=1138x640 scale=1.125 field=(223,153,690,361) overlapField=0 "
               "deckpanel=(821.8,72,300,440) deckpanelBlocks=1490 deckpanelTransient=0"]
        errs, _ = hc.check_widget_trace(bad, ids)
        self.assertTrue(any("deckpanelBlocks=1490" in e for e in errs))


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


def test_check_trace_portrait_sidekicks_cp10_12():
    """VS-2 CP-10 / CP-12: the sidekick mini portraits - Merlin and the harpies n=1..3 in PANEL, the ROOM disc 40 su
    without a number; a harpy in PANEL without n (or n=4 of a mirror match) fails (ВР-72)."""
    reg = hc.registry_portrait_keys()
    tex = "tex=/Game/S08/UI/Portraits/T_Portrait_medusa_harpies.T_Portrait_medusa_harpies"
    ok = ["UMGALLERY panel own own PORTRAIT id=king-arthur/merlin tex=/Game/S08/UI/Portraits/T_Portrait_king_arthur_merlin."
          "T_Portrait_king_arthur_merlin su=32.0 px=32.0 scale=0.362 show=panel side=own state=avatar capped=0"]
    ok += ["PORTRAIT id=medusa/harpies %s su=32.0 px=48.0 scale=0.543 show=panel side=opp state=avatar capped=0 n=%d"
           % (tex, i) for i in (1, 2, 3)]
    ok += ["PORTRAIT id=medusa/harpies %s su=40.0 px=120.0 scale=1.359 show=room side=own state=avatar capped=0" % tex,
           "PORTRAIT id=medusa tex=/Game/x su=160.0 px=480.0 scale=1.600 show=loading side=own state=avatar capped=1"]
    errors, _ = hc.check_widget_trace(ok, set(), registry=reg)
    assert errors == []
    bad = ["PORTRAIT id=medusa/harpies %s su=32.0 px=32.0 scale=0.362 show=panel side=own state=avatar capped=0" % tex,
           "PORTRAIT id=medusa/harpies %s su=32.0 px=32.0 scale=0.362 show=panel side=opp state=avatar capped=0 n=4"
           % tex]
    errors, _ = hc.check_widget_trace(bad, set(), registry=reg)
    assert len(errors) == 2 and all("ВР-72" in e for e in errors)


def test_check_trace_card_art_cp15():
    """VS-3 CP-15 (ВР-CP10, ВР-CP04): CARD-ART lines - scale <= 1.6, no fallback face for a key the registry has (the
    -S08CardArtLegacy rollback tex=legacy excepted), the back key, the fields."""
    reg = hc.registry_card_keys()
    assert {"king-arthur:excalibur", "medusa:gaze-of-stone", "back:king-arthur", "back:medusa"} <= reg
    assert len([k for k in reg if not k.startswith("back:")]) == 27
    tex = "tex=/Game/S08/UI/Cards/king_arthur/T_Card_king_arthur_excalibur_RU.T_Card_king_arthur_excalibur_RU"
    ok = ["CARD-ART key=king-arthur:excalibur lang=ru %s show=hand su=150x208 px=142x197 scale=0.495 capped=0 "
          "state=idle chip=0" % tex,
          "UMGALLERY card p14.hover t=0 CARD-ART key=king-arthur:excalibur lang=ru %s show=inspector su=440x612 "
          "px=889x1233 scale=1.600 capped=1 state=hover+selected chip=0" % tex,
          "CARD-ART key=back:medusa lang=back tex=/Game/S08/UI/CardBacks/T_CardBack_medusa.T_CardBack_medusa "
          "show=mini-48x67 su=48x67 px=44x61 scale=0.058 capped=0 state=back+boost chip=1",
          "CARD-ART key=king-arthur:excalibur lang=fallback tex=legacy show=hand su=150x208 px=0x0 scale=0.000 "
          "capped=0 state=idle chip=0",
          "CARD-ART key=t-rex:bite lang=fallback tex=fallback show=hand su=150x208 px=0x0 scale=0.000 capped=0 "
          "state=idle chip=0"]
    errors, _ = hc.check_widget_trace(ok, set(), card_registry=reg)
    assert errors == []
    bad = ["CARD-ART key=king-arthur:excalibur lang=ru %s show=inspector su=460x640 px=905x1256 scale=1.750 capped=0 "
           "state=idle chip=0" % tex,
           "CARD-ART key=medusa:snipe lang=fallback tex=fallback show=hand su=150x208 px=0x0 scale=0.000 capped=0 "
           "state=idle chip=0",
           "CARD-ART key=medusa:snipe lang=de tex=x show=hand su=150x208 px=0x0 scale=0.000 capped=2 state=idle chip=0",
           "CARD-ART key=medusa:snipe lang=ru"]
    errors, _ = hc.check_widget_trace(bad, set(), card_registry=reg)
    assert any("1.6" in e for e in errors) and any("ВР-CP10" in e for e in errors)
    assert any("lang=de" in e for e in errors) and any("capped=2" in e for e in errors)
    assert any("без поля scale" in e for e in errors)


def test_check_trace_topstrip_hb14_16(tmp_path):
    """VS-2 HB-14...HB-16: the UI-IDs of 04 §7.1 are known to check-trace and their states come from its list."""
    spec04 = hc.SPEC04.read_text(encoding="utf-8")
    ids = hc.ui_ids_from_02(SPEC02) | hc.ui_ids_from_02(spec04)
    states = hc.ui_states_from_04(spec04)
    assert {"UI-HUD-TOP", "UI-HUD-CONN", "UI-HUD-STATUS", "UI-HUD-BANNER"} <= ids
    assert [r.pattern for r in states["UI-HUD-CONN"]] == ["online$", "syncing$", "lost$"]
    assert len(states["UI-HUD-STATUS"]) == 6 and len(states["UI-HUD-COMBAT-EDGE"]) == 5
    head = "SHOT widget id=%s impl=umg state=%s fighter=none bbox=(24,24,276,68) geom=painted visible=1 twin=0 source=x"
    ok = [head % ("UI-HUD-TOP", "idle") + " turn=3 class=L menu=glyph log=0",
          head % ("UI-HUD-CONN", "lost") + " icon=resource-connection-lost anim=appear_from_online",
          head % ("UI-HUD-STATUS", "defend") + " key=ms.status.defend lines=2 size=24 ellipsis=0 keys=- width=600",
          head % ("UI-HUD-BANNER", "shown") + " alpha=1.00",
          head % ("UI-HUD-ACTIONS", "mode=attack"),
          head % ("UI-HUD-OPP-HAND", "count=5")]
    assert hc.check_widget_trace(ok, ids, states=states) == ([], 6)
    bad = [head % ("UI-HUD-CONN", "offline"), head % ("UI-HUD-STATUS", "maneuver"),
           head % ("UI-HUD-OPP-HAND", "count=x"), head % ("UI-HUD-ACTIONS", "mode=move")]
    errors, _ = hc.check_widget_trace(bad, ids, states=states)
    assert len([e for e in errors if "04 §7.1" in e]) == 4
    # the CLI reads 04: a log with the new ids passes
    log = tmp_path / "Unmatched.log"
    log.write_text("\n".join(ok) + "\n", encoding="utf-8")
    assert hc.main(["check-trace", str(log)]) == 0
    log.write_text(head % ("UI-HUD-TOP", "busy") + "\n", encoding="utf-8")
    assert hc.main(["check-trace", str(log)]) == 1


def test_check_trace_panels_hb18_21(tmp_path):
    """VS-2 HB-18...HB-21: PANEL-LOC / PANEL-OPP / OPP-HAND lines of the client pass check-trace with the states of 04 §7.1."""
    spec04 = hc.SPEC04.read_text(encoding="utf-8")
    ids = hc.ui_ids_from_02(SPEC02) | hc.ui_ids_from_02(spec04)
    states = hc.ui_states_from_04(spec04)
    assert {"UI-HUD-PANEL-LOC", "UI-HUD-PANEL-OPP", "UI-HUD-OPP-HAND"} <= ids
    head = "SHOT widget id=%s impl=umg state=%s fighter=none bbox=(24,920,364,1056) geom=painted visible=1 twin=0 source=x"
    extra = " hero=Medusa hp=14/16 sidekicks=3 fallen=0 tracker=1/2 ring=1 avatar=1 class=L smoulder=0.35"
    ok = [head % ("UI-HUD-PANEL-LOC", s) + extra for s in ("own", "wait", "fallen")]
    ok += [head % ("UI-HUD-PANEL-OPP", s) + extra for s in ("opp", "wait", "fallen", "ai")]
    ok += [head % ("UI-HUD-OPP-HAND", "count=12") + " deck=23 discard=2 stale=1 step=20.7 width=300 fan=276.0 back=T_x"]
    assert hc.check_widget_trace(ok, ids, states=states) == ([], 8)
    bad = [head % ("UI-HUD-PANEL-LOC", "ai"), head % ("UI-HUD-PANEL-OPP", "own"), head % ("UI-HUD-OPP-HAND", "count=")]
    errors, _ = hc.check_widget_trace(bad, ids, states=states)
    assert len([e for e in errors if "04 §7.1" in e]) == 3
    log = tmp_path / "Unmatched.log"
    log.write_text("\n".join(ok) + "\n", encoding="utf-8")
    assert hc.main(["check-trace", str(log)]) == 0


def test_check_trace_combat_privacy_hb30():
    """VS-3 HB-30 / HB-33: the combat edges and the centre pass check-trace with the states of 04 §7.1; the opponent's
    card face (fighter=opp face=1) only in state=reveal."""
    spec04 = hc.SPEC04.read_text(encoding="utf-8")
    ids = hc.ui_ids_from_02(SPEC02) | hc.ui_ids_from_02(spec04)
    states = hc.ui_states_from_04(spec04)
    edge = ("SHOT widget id=UI-HUD-COMBAT-EDGE impl=umg state=%s fighter=%s bbox=(1666,360,1896,711) geom=painted visible=1 "
            "twin=0 source=x role=defense face=%s class=L card=230x319 ribbon=230x28 rows=1 timer=- timerState=off buttons=0 "
            "defend=- stamp=0 leave=0 seq=10")
    centre = ("SHOT widget id=UI-HUD-COMBAT impl=umg state=%s fighter=none bbox=(680,80,1240,232) geom=painted visible=1 "
              "twin=0 source=x class=L h=152 lines=2 shown=2 more=0 cancelled=1 current=-1 ellipsis=0 score=3:2 outcome=wins seq=10")
    ok = [edge % ("back", "opp", "0"), edge % ("chosen", "opp", "0"), edge % ("reveal", "opp", "1"),
          edge % ("back", "own", "1"), edge % ("shield", "own", "0"), edge % ("nodefense", "opp", "0")]
    ok += [centre % s for s in ("wait", "effects", "slam", "hit")]
    ok += [centre.replace("visible=1", "visible=0") % "read"]
    assert hc.check_widget_trace(ok, ids, states=states) == ([], 11)
    bad = [edge % ("chosen", "opp", "1"), edge % ("back", "opp", "1")]
    errors, _ = hc.check_widget_trace(bad, ids, states=states)
    assert len([e for e in errors if "приватность" in e]) == 2
    errors, _ = hc.check_widget_trace([edge % ("leave", "own", "0"), centre % "outcome"], ids, states=states)
    assert len([e for e in errors if "04 §7.1" in e]) == 2


def test_check_trace_vs4_blocks_hb48():
    """VS-4 HB-48 (04 §7.1): the UI-IDs of the VS-4 blocks are known with their states - PENDING, SLOT, LOG, TOAST, SUB,
    ACTIONS - and a state outside the list fails."""
    spec04 = hc.SPEC04.read_text(encoding="utf-8")
    ids = hc.ui_ids_from_02(SPEC02) | hc.ui_ids_from_02(spec04)
    states = hc.ui_states_from_04(spec04)
    want = {"UI-HUD-PENDING": ["modal", "compact", "collapsed", "toast", "opp"],
            "UI-HUD-SLOT": ["fly", "hold", "show", "fade"], "UI-HUD-LOG": ["lines=6", "hidden"],
            "UI-HUD-TOAST": ["bottom", "top"], "UI-HUD-SUB": ["shown"],
            "UI-HUD-ACTIONS": ["own", "opp", "mode=maneuver", "mode=attack", "mode=scheme"]}
    head = "SHOT widget id=%s impl=umg state=%s fighter=none bbox=(600,80,1320,140) geom=painted visible=1 twin=0 source=x"
    ok = [head % (i, s) for i, ss in want.items() for s in ss]
    assert set(want) <= ids and set(want) <= set(states)
    assert hc.check_widget_trace(ok, ids, states=states) == ([], len(ok))
    bad = [head % ("UI-HUD-PENDING", "open"), head % ("UI-HUD-SLOT", "gone"), head % ("UI-HUD-LOG", "lines=x"),
           head % ("UI-HUD-TOAST", "middle"), head % ("UI-HUD-ACTIONS", "mode=move")]
    errors, _ = hc.check_widget_trace(bad, ids, states=states)
    assert len([e for e in errors if "04 §7.1" in e]) == 5


def test_check_trace_inspector_privacy_hb49():
    """VS-4 SC-22 / HB-49: the hidden inspector line carries no value of the card (back face, no language switch, no
    copies, no grid); the own card and the deck mode may."""
    insp = ("SHOT widget id=UI-SCR-INSPECT impl=umg state=%s fighter=none bbox=(534,196,1386,884) geom=painted visible=1 "
            "twin=0 source=x modal=1 class=L alpha=1.00 mode=%s source=opphand face=%s cap=0.000 grid=%s first=0 "
            "copies=%s lang=%s primary=0")
    ok = [insp % ("hidden", "hidden", "back", "0", "0", "0"), insp % ("own", "own", "ru", "0", "0", "1"),
          insp % ("deck", "deck", "-", "11", "30", "0")]
    assert [e for e in hc.check_widget_trace(ok, {"UI-SCR-INSPECT"})[0] if "приватность" in e] == []
    bad = [insp % ("hidden", "hidden", "ru", "0", "0", "0"), insp % ("hidden", "hidden", "back", "0", "2", "1")]
    errors, _ = hc.check_widget_trace(bad, {"UI-SCR-INSPECT"})
    assert len([e for e in errors if "скрытый инспектор" in e]) == 2


SHOT_TRACE = """\
x ARTLOOK art=1 markers=0 hudImpl=%(impl)s
x SHOT captured file=s09-a.png frame=1
x SHOT widget id=UI-HUD-STATUS impl=umg state=defend fighter=none bbox=(656,24,1264,72) geom=painted visible=1 twin=0 source=x
x SHOT widget id=UI-HUD-COMBAT-EDGE impl=umg state=back fighter=opp bbox=(1666,360,1896,711) geom=painted visible=1 twin=0 source=x role=attack face=0
x SHOT widget id=UI-HUD-DECKPANEL impl=umg state=own fighter=none bbox=(0,0,0,0) geom=unpainted visible=0 twin=0 source=x
x SHOT widget id=UI-HUD-ACTIONS impl=umg state=mode=maneuver fighter=none bbox=(788,976,1132,1048) geom=painted visible=1 twin=0 source=x
x SHOT request file=s09-combat-defense-open.png frame=2
x SHOT captured file=s09-combat-defense-open.png frame=2
x SHOT widget id=UI-HUD-STATUS impl=umg state=opp fighter=none bbox=(656,24,1264,72) geom=painted visible=1 twin=0 source=x
x SHOT widget id=UI-HUD-COMBAT-EDGE impl=umg state=reveal fighter=opp bbox=(1666,360,1896,711) geom=painted visible=1 twin=0 source=x role=attack face=1
x SHOT widget id=UI-HUD-COMBAT-EDGE impl=umg state=reveal fighter=own bbox=(24,360,254,711) geom=painted visible=1 twin=0 source=x role=defense face=1
x SHOT request file=s09-combat-resolve-revealed.png frame=3
"""


def test_check_shots_hb48(tmp_path):
    """VS-4 HB-48: need / deny / '||' against the block of one shot; a swapped rule fails; a missing shot and a missing
    UMG block are named, the -S08SlateHud rollback with its hudImpl; the CLI returns 0 / 1."""
    lines = (SHOT_TRACE % {"impl": "umg"}).splitlines()
    defense = hc.parse_rule("s09-combat-defense-open.png: need UI-HUD-STATUS state=defend; "
                            "need UI-HUD-COMBAT-EDGE fighter=opp state=back|shield|chosen face=0; "
                            "deny UI-HUD-COMBAT-EDGE state=reveal; need UI-HUD-ACTIONS state=mode=maneuver")
    reveal = hc.parse_rule("s09-combat-resolve-revealed.png: need UI-HUD-COMBAT-EDGE fighter=opp state=reveal; "
                           "need UI-HUD-STATUS state=sync || UI-HUD-STATUS state=opp; deny UI-HUD-DECKPANEL")
    results, priv = hc.check_shots(lines, [defense, reveal], privacy=True)
    assert results == [("s09-combat-defense-open.png", []), ("s09-combat-resolve-revealed.png", [])] and priv == []
    # swap controls: the defense rule on the reveal shot and the reveal rule on the defense shot fail
    swapped = [("s09-combat-resolve-revealed.png", defense[1]), ("s09-combat-defense-open.png", reveal[1])]
    results, _ = hc.check_shots(lines, swapped)
    assert all(reasons for _, reasons in results)
    assert any("запрещено UI-HUD-COMBAT-EDGE state=reveal" in r for r in results[0][1])
    # an unpainted / hidden line does not satisfy a need; a missing block names the rollback
    results, _ = hc.check_shots(lines, [hc.parse_rule("s09-combat-defense-open.png: need UI-HUD-DECKPANEL")])
    assert "visible=0" in results[0][1][0]
    slate = (SHOT_TRACE % {"impl": "slate:combat"}).replace("UI-HUD-COMBAT-EDGE", "UI-HUD-XEDGE").splitlines()
    results, _ = hc.check_shots(slate, [defense])
    assert any("блок UMG не нарисован" in r and "-S08SlateHud" in r and "-S09Markers" in r for r in results[0][1])
    results, _ = hc.check_shots(lines, [hc.parse_rule("s09-nope.png: need UI-HUD-STATUS")])
    assert "нет кадра" in results[0][1][0]
    # prefix ids; privacy over the whole trace
    results, _ = hc.check_shots(lines, [hc.parse_rule("s09-combat-defense-open.png: deny UI-HUD-*")])
    assert len(results[0][1]) == 3
    leak = lines + ["x SHOT widget id=UI-HUD-COMBAT-EDGE impl=umg state=chosen fighter=opp bbox=(1,1,2,2) geom=painted "
                    "visible=1 twin=0 source=x face=1"]
    assert len(hc.check_shots(leak, [], privacy=True)[1]) == 1
    log = tmp_path / "t.log"
    log.write_text(SHOT_TRACE % {"impl": "umg"}, encoding="utf-8")
    rule = ("s09-combat-defense-open.png: need UI-HUD-STATUS state=defend; deny UI-HUD-COMBAT-EDGE state=reveal")
    assert hc.main(["check-shots", str(log), "--rule", rule, "--privacy"]) == 0
    assert hc.main(["check-shots", str(log), "--rule", rule.replace("defend", "opp")]) == 1
    assert hc.main(["check-shots", str(log), "--rule", "no colon here"]) == 2


def test_check_shots_late_block_hb48():
    """VS-4 HB-48: a block first shown in the shot frame writes its painted line in the late block of the same file
    (ВР-VS2-77) - the need is met there; the late block of ANOTHER file is not read."""
    lines = ["x SHOT captured file=s09-a.png frame=1",
             "x SHOT widget id=UI-HUD-PENDING impl=umg state=compact fighter=none bbox=(0,0,0,0) geom=unpainted visible=1 twin=0 source=x kind=MOVE",
             "x SHOT request file=s09-pending-MOVE.png frame=2",
             "x SHOT captured file=s09-pending-MOVE.png frame=2",
             "x SHOT late begin file=s09-pending-MOVE.png frame=2 requestFrame=2",
             "x SHOT widget id=UI-HUD-PENDING impl=umg state=compact fighter=none bbox=(600,80,1320,140) geom=painted visible=1 twin=0 source=x kind=MOVE",
             "x SHOT late end file=s09-pending-MOVE.png frame=2",
             "x SHOT request file=s09-b.png frame=9",
             "x SHOT late begin file=s09-b.png frame=9 requestFrame=9",
             "x SHOT late end file=s09-b.png frame=9"]
    rule = hc.parse_rule("s09-pending-MOVE.png: need UI-HUD-PENDING kind=MOVE state=compact|modal")
    assert hc.check_shots(lines, [rule]) == ([("s09-pending-MOVE.png", [])], [])
    other = hc.parse_rule("s09-b.png: need UI-HUD-PENDING kind=MOVE")
    assert hc.check_shots(lines, [other])[0][0][1]


def test_check_shots_model_state_hb48():
    """VS-4 HB-48: a matcher naming 'visible' reads the block's model drawn or not (the backend-less probe keeps
    ACTIONS collapsed); without it a hidden line never satisfies a need."""
    lines = ["x SHOT widget id=UI-HUD-ACTIONS impl=umg state=mode=maneuver fighter=none bbox=(0,0,0,0) geom=unpainted visible=0 "
             "twin=0 source=x", "x SHOT request file=s09-probe-maneuver-draft.png frame=1"]
    hidden = hc.parse_rule("s09-probe-maneuver-draft.png: need UI-HUD-ACTIONS state=mode=maneuver")
    model = hc.parse_rule("s09-probe-maneuver-draft.png: need UI-HUD-ACTIONS state=mode=maneuver visible=0|1")
    assert hc.check_shots(lines, [hidden])[0][0][1]
    assert hc.check_shots(lines, [model])[0][0][1] == []
    deny = hc.parse_rule("s09-probe-maneuver-draft.png: deny UI-HUD-ACTIONS state=mode=maneuver visible=0|1")
    assert hc.check_shots(lines, [deny])[0][0][1]
