"""VS-1 HB-03: tests of the token generator (aliases, stable order, re-run, stale header) and of G-TOKENS.

  python -m pytest tools/s08/hud_contract/test_hud_tokens_codegen.py -q
"""
import copy
import json
import random
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hud_contract as hc  # noqa: E402
import hud_tokens_codegen as cg  # noqa: E402

TOKENS = cg.load(cg.TOKENS)


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


class AliasTests(unittest.TestCase):
    def test_vr61_aliases_resolve_to_card_navy_and_text_primary(self):
        c = TOKENS["colors"]
        navy = cg.resolve_color(c, "card.navy")[0]
        self.assertEqual(cg.resolve_color(c, "tag.background"), (navy, 1.0))
        self.assertEqual(cg.resolve_color(c, "icon.token.body"), (navy, 1.0))
        self.assertEqual(cg.resolve_color(c, "tag.text")[0], cg.resolve_color(c, "text.primary")[0])
        self.assertEqual(c["tag.background"]["hex_slate"], "#161A28")  # the -S08SlateHud rollback keeps the old value

    def test_alias_keeps_its_own_alpha_not_the_targets(self):
        c = TOKENS["colors"]
        self.assertEqual(cg.resolve_color(c, "panel.edge"), (cg.resolve_color(c, "card.cream")[0], 0.45))
        self.assertEqual(cg.resolve_color(c, "panel.bg"), ("#061623", 0.92))
        self.assertEqual(cg.resolve_color(c, "state.warning"), (c["turn.flash.orange"]["hex"], 1.0))

    def test_alias_chain_and_header_bytes(self):
        t = copy.deepcopy(TOKENS)
        t["colors"]["x.chain"] = {"alias": "panel.edge", "status": "предложено", "source": "test"}
        self.assertEqual(cg.resolve_color(t["colors"], "x.chain"), ("#F9EBDB", 1.0))
        text = cg.render(t, "0" * 64)
        self.assertIn("inline constexpr FColor Color_XChain = FColor(0xF9, 0xEB, 0xDB, 0xFF);", text)
        self.assertIn("inline constexpr float Alpha_PanelEdge = 0.45f;", text)
        self.assertIn("inline constexpr FColor Color_TagBackground = FColor(0x06, 0x16, 0x23, 0xFF);", text)

    def test_bad_aliases_fail(self):
        t = copy.deepcopy(TOKENS)
        t["colors"]["a.loop"] = {"alias": "b.loop", "status": "предложено", "source": "test"}
        t["colors"]["b.loop"] = {"alias": "a.loop", "status": "предложено", "source": "test"}
        with self.assertRaises(cg.TokenError):
            cg.resolve_color(t["colors"], "a.loop")
        t = copy.deepcopy(TOKENS)
        t["colors"]["panel.edge"]["hex"] = "#000000"  # stored hex differs from the resolved alias
        self.assertTrue(any("panel.edge" in e for e in hc.validate_tokens(t)))
        t = copy.deepcopy(TOKENS)
        t["colors"]["x.missing"] = {"alias": "no.such", "status": "предложено", "source": "test"}
        self.assertTrue(any("no.such" in e for e in hc.validate_tokens(t)))

    def test_new_tokens_of_02(self):
        c, ty, r = TOKENS["colors"], TOKENS["typography"], TOKENS["radii"]
        for name in ("panel.bg", "panel.bg.inset", "panel.bg.hover", "panel.bg.pressed", "panel.edge", "panel.divider",
                     "panel.veil", "state.warning", "fx.flash", "fx.impact", "fx.rim", "fx.heal", "fx.gold", "fx.stone",
                     "fx.ash", "fx.dust", "board.reach", "board.path", "board.choice", "board.target", "board.keyline",
                     "hp.fill", "hp.back"):
            self.assertIn(name, c)
            self.assertEqual(c[name]["status"], "предложено")
            self.assertTrue(c[name]["source"].startswith("02 §"), name)
        self.assertEqual({n: ty[n]["su"] for n in ty if n.startswith("type.")},
                         {"type.display": 48, "type.banner": 36, "type.title": 28, "type.heading": 24, "type.button": 20,
                          "type.body": 16, "type.caption": 14, "type.tag": 14, "type.damage": 24})
        self.assertEqual([r[n]["px"] for n in ("radius.s", "radius.m", "radius.l")], [4, 6, 8])
        self.assertEqual(TOKENS["opacity"]["state.disabled.opacity"]["value"], 0.4)
        # existing hex stay (HB-03 dont): card.*, team.*, turn.flash.*
        self.assertEqual(c["card.navy"]["hex"], "#061623")
        self.assertEqual(c["team.p2"]["hex"], "#5A7F9F")
        self.assertEqual(c["turn.flash.yellow"]["hex"], "#F2C14E")


class GeneratorTests(unittest.TestCase):
    def test_stable_order_regardless_of_json_order(self):
        shuffled = copy.deepcopy(TOKENS)
        for group in ("colors", "typography", "spacing", "radii", "motion", "icons"):
            items = list(shuffled[group].items())
            random.Random(7).shuffle(items)
            shuffled[group] = dict(items)
        self.assertEqual(cg.render(TOKENS, "a" * 64), cg.render(shuffled, "a" * 64))

    def test_rerun_gives_the_same_file_and_the_committed_header_is_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp) / "S08HudTokens.generated.h"
            cg.generate(cg.TOKENS, h)
            first = h.read_bytes()
            cg.generate(cg.TOKENS, h)
            self.assertEqual(first, h.read_bytes())
            self.assertNotIn(b"\r\n", first)
            self.assertLessEqual(len(first), 30 * 1024)  # budget: header <= 30 KB
            committed = cg.HEADER.read_bytes().replace(b"\r\n", b"\n")
            self.assertEqual(committed, first, "S08HudTokens.generated.h is stale: run hud_tokens_codegen.py")

    def test_sha_ignores_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            lf, crlf = Path(tmp) / "lf.json", Path(tmp) / "crlf.json"
            data = cg.TOKENS.read_bytes().replace(b"\r\n", b"\n")
            lf.write_bytes(data)
            crlf.write_bytes(data.replace(b"\n", b"\r\n"))
            self.assertEqual(cg.json_sha256(lf), cg.json_sha256(crlf))

    def test_identifier_clash_fails(self):
        t = copy.deepcopy(TOKENS)
        t["colors"]["panel_bg"] = {"hex": "#000000", "status": "предложено", "source": "test"}  # Color_PanelBg twice
        with self.assertRaises(cg.TokenError):
            cg.render(t, "0" * 64)


class StaleHeaderTests(unittest.TestCase):
    def test_one_hex_changed_without_regeneration_fails_header_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            j, h = Path(tmp) / "tokens.json", Path(tmp) / "S08HudTokens.generated.h"
            shutil.copyfile(cg.TOKENS, j)
            cg.generate(j, h)
            self.assertEqual(cg.header_errors(j, h), [])
            t = cg.load(j)
            t["colors"]["hp.fill"]["hex"] = "#50BE65"
            write_json(j, t)
            errs = cg.header_errors(j, h)
            self.assertEqual(len(errs), 1)
            self.assertIn("header stale", errs[0])
            cg.generate(j, h)
            self.assertEqual(cg.header_errors(j, h), [])

    def test_missing_header_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn("header stale", cg.header_errors(cg.TOKENS, Path(tmp) / "none.h")[0])

    def test_validate_passes_on_the_repo(self):
        self.assertEqual(hc.validate_tokens(TOKENS), [])
        self.assertEqual(cg.header_errors(), [])
        self.assertEqual(hc.literal_errors(), [])

    def test_literal_scan_catches_colour_literals(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "UI"
            src.mkdir()
            (src / "UmGood.cpp").write_text("const FLinearColor C = FLinearColor::FromSRGBColor(S08HudTokens::Color_PanelBg);\n"
                                            "// FColor(1, 2, 3) in a comment is fine\n", encoding="utf-8")
            (src / "UmBad.cpp").write_text("const FColor A(22, 26, 40);\nconst FColor B = FColor(22, 26, 40);\n"
                                           "const FLinearColor L(0.2f, 0.3f, 0.4f);\nauto H = FColor::FromHex(TEXT(\"#161A28\"));\n",
                                           encoding="utf-8")
            old = hc.REPO
            try:
                hc.REPO = Path(tmp)
                errs = hc.literal_errors(src)
            finally:
                hc.REPO = old
            self.assertEqual(len(errs), 4, errs)  # declarator A(...), call B, declarator L(...), FromHex literal H
            self.assertTrue(all("UmBad.cpp" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
