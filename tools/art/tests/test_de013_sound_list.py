"""DE-013 (W-25 art): the licensed sound list docs/art-pipeline/audio/de013-sound-list.json against its rules
(tools/art/de013/de013.py check) - every sound has a licence and a source, no DE sounds, purchases are the user's.

  python -B -m pytest -q tools/art/tests/test_de013_sound_list.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "art" / "de013"))
import de013 as D  # noqa: E402


class SoundListTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = D.load_json(D.LIST_PATH)
        cls.cue_table = D.load_json(D.CUE_TABLE_PATH)
        cls.credits = D.CREDITS_PATH.read_text(encoding="utf-8")

    def errors(self, data, credits=None):
        return D.check(data, self.cue_table, self.credits if credits is None else credits)

    def mutated(self):
        return copy.deepcopy(self.data)

    def sound(self, data, sid):
        return next(s for s in data["sounds"] if s["id"] == sid)

    def source(self, data, sid):
        return next(s for s in data["sources"] if s["id"] == sid)

    def assert_error(self, data, needle, credits=None):
        errs = self.errors(data, credits)
        self.assertTrue(any(needle in e for e in errs), f"no error with {needle!r} in {errs}")

    # --- the committed list -------------------------------------------------------------------------------------
    def test_committed_list_is_clean(self):
        self.assertEqual(self.errors(self.data), [])

    def test_cli_check_passes(self):
        self.assertEqual(D.main(["check"]), 0)

    def test_nothing_acquired_from_the_list(self):
        # DE-013 is a list only: nothing from it was downloaded. The game sounds were generated instead (AU-PROD,
        # docs/game-design/audio/07-production-log.md) and imported by AU-UE, so a CUE is either present with a
        # /Game/Audio sound or missing with a reason.
        self.assertTrue(all(s["acquired"] is False for s in self.data["sounds"]))
        for cue in self.cue_table["cues"]:
            sfx = cue["sfx"]
            if sfx["status"] == "present":
                self.assertTrue(str(sfx["sound"]).startswith("/Game/Audio/"), cue["id"])
            else:
                self.assertEqual(sfx["status"], "missing", cue["id"])
                self.assertTrue(sfx.get("missing_reason"), cue["id"])

    def test_every_primary_is_a_free_download(self):
        sources = {s["id"]: s for s in self.data["sources"]}
        for snd in self.data["sounds"]:
            self.assertEqual(sources[snd["primary"]["source"]]["acquisition"], "free_download", snd["id"])

    # --- rule violations are caught -----------------------------------------------------------------------------
    def test_missing_licence(self):
        data = self.mutated()
        self.source(data, "kenney-impact-sounds")["license"] = ""
        self.assert_error(data, "kenney-impact-sounds: license is empty")

    def test_missing_source_url(self):
        data = self.mutated()
        self.source(data, "kenney-music-jingles")["url"] = "kenney music jingles"
        self.assert_error(data, "url is not an http(s) URL")

    def test_digital_edition_source_is_rejected(self):
        data = self.mutated()
        data["sources"].append({**self.source(data, "kenney-rpg-audio"), "id": "de-rip",
                                "title": "Unmatched Digital Edition capture", "url": "https://store.steampowered.com/"})
        self.sound(data, "SND-HIT")["primary"]["source"] = "de-rip"
        self.assert_error(data, "Digital Edition source")

    def test_unknown_primary_source(self):
        data = self.mutated()
        self.sound(data, "SND-STEP")["primary"]["source"] = "nowhere"
        self.assert_error(data, "SND-STEP: primary source 'nowhere' is not in sources")

    def test_paid_source_must_be_bought_by_the_user(self):
        data = self.mutated()
        self.source(data, "jdsherbert-tabletop-sfx")["acquisition"] = "free_download"
        self.assert_error(data, "must be acquisition = user")

    def test_fab_source_must_be_added_by_the_user(self):
        data = self.mutated()
        self.source(data, "fab-cyrex-free-ui")["acquisition"] = "free_download"
        self.assert_error(data, "fab-cyrex-free-ui: paid or Fab source")

    def test_primary_cannot_need_a_purchase(self):
        data = self.mutated()
        self.sound(data, "SND-STEP")["primary"]["source"] = "jdsherbert-tabletop-sfx"
        self.assert_error(data, "SND-STEP: primary source must be a free download")

    def test_cc_by_needs_attribution(self):
        data = self.mutated()
        src = self.source(data, "incompetech-cc-by")
        src["attribution_required"] = False
        self.assert_error(data, "licence needs attribution")
        src["attribution_required"] = True
        src["attribution_text"] = ""
        self.assert_error(data, "attribution_required without attribution_text")

    def test_required_role_missing(self):
        data = self.mutated()
        data["sounds"] = [s for s in data["sounds"] if s["id"] != "SND-TURN-CHIME"]
        self.assert_error(data, "required role SND-TURN-CHIME")

    def test_unknown_cue_and_class_mismatch(self):
        data = self.mutated()
        self.sound(data, "SND-HIT")["cues"] = ["CUE-099", "CUE-011"]
        self.assert_error(data, "CUE-099 is not in the CUE table")
        data = self.mutated()
        self.sound(data, "SND-STING-WIN")["sound_class"] = "SFX"
        self.assert_error(data, "sound_class 'SFX' != CUE table 'Music'")

    def test_step_longer_than_an_edge(self):
        data = self.mutated()
        self.sound(data, "SND-STEP")["length_ms"] = [60, 400]
        self.assert_error(data, "a step longer than one edge")

    def test_sting_outside_two_to_three_seconds(self):
        data = self.mutated()
        self.sound(data, "SND-STING-LOSE")["length_ms"] = [1500, 3000]
        self.assert_error(data, "result sting must stay within 2000-3000")

    def test_long_ui_click(self):
        data = self.mutated()
        self.sound(data, "SND-UI-CLICK")["length_ms"] = [30, 600]
        self.assert_error(data, "a ui click longer than 250")

    def test_credits_must_mention_every_sound_and_source(self):
        self.assert_error(self.data, "CREDITS-audio.md does not mention SND-HIT", credits="nothing here")


if __name__ == "__main__":
    unittest.main()
