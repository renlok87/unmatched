"""Art Tuner fold (tools/art/art_tuner_fold.py): the values of S08ArtTuner.overrides.json go into a COPY of the real board
profiles by text edits - only the changed values move, the rest of the file stays byte for byte."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools/art"))
import art_tuner_fold as F  # noqa: E402

PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"


def sarpedon_index(doc: dict) -> int:
    return next(i for i, b in enumerate(doc["boards"]) if b["id"] == "sarpedon-original")


class FoldTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.prof = self.tmp / "S08ArtBoardProfiles.json"
        shutil.copyfile(PROFILES, self.prof)
        self.base_text = self.prof.read_text(encoding="utf-8")
        self.base = json.loads(self.base_text)
        self.si = sarpedon_index(self.base)
        hero = self.base["lightProfiles"]["sarpedon-night"]["heroLight"]["key"]
        light = self.base["boards"][self.si]["conceptPaste"]["lit3d"]["lights"][1]
        exp = self.base["lightProfiles"]["sarpedon-night"]["exposure"]
        self.lux_was, self.cd_was, self.ev_was = hero["lux"], light["intensityCd"], exp["ev100"]
        self.ov = self.tmp / "S08ArtTuner.overrides.json"
        self.archive = self.tmp / "saves"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write_overrides(self, entries: list[str], anchor_index: int | None = None, board: str = "sarpedon-original",
                        anchor_board: str = "sarpedon-original"):
        idx = self.si if anchor_index is None else anchor_index
        text = ("{\n \"schema\": \"unmatched.art-tuner-overrides/1\",\n \"savedAt\": \"2026-10-03T00:00:00Z\",\n"
                " \"baseProfilesSha256\": \"x\",\n \"baseRevision\": 20,\n \"boards\": [\n  {\n"
                f"   \"board\": \"{board}\",\n   \"profile\": \"sarpedon-night\",\n"
                f"   \"anchors\": {{\"/boards/{idx}/id\": \"{anchor_board}\"}},\n   \"entries\": [\n    "
                + ",\n    ".join(entries) + "\n   ]\n  }\n ]\n}\n")
        self.ov.write_text(text, encoding="utf-8")

    def standard_entries(self, si: int | None = None) -> list[str]:
        si = self.si if si is None else si
        return [
            f'{{"pointer": "/lightProfiles/sarpedon-night/heroLight/key/lux", "value": 9.5, "was": {json.dumps(self.lux_was)}}}',
            f'{{"pointer": "/boards/{si}/conceptPaste/lit3d/lights/1/intensityCd", "value": 120, "was": {json.dumps(self.cd_was)}}}',
            f'{{"pointer": "/lightProfiles/sarpedon-night/exposure/ev100", "value": 2.3, "was": {json.dumps(self.ev_was)}}}',
            '{"pointer": "/lightProfiles/sarpedon-night/exposure/minBrightness", "value": 4.92458, "was": 4.14106}',
            '{"pointer": "/lightProfiles/sarpedon-night/exposure/maxBrightness", "value": 4.92458, "was": 4.14106}',
            f'{{"pointer": "/boards/{si}/conceptPaste/lit3d/materialOverrides/Island/tintGain", "value": 1.25, "was": null}}',
            f'{{"pointer": "/boards/{si}/conceptPaste/lit3d/materialOverrides/Foliage/windAmp", "value": 12, "was": null}}',
            '{"pointer": "/lightProfiles/sarpedon-night/sky/colorLinear", "value": [0.6, 0.72, 1], "was": [0.58, 0.7, 1.0]}',
        ]

    def run_fold(self, *args: str) -> int:
        return F.main(["--overrides", str(self.ov), "--profiles", str(self.prof), "--archive-dir", str(self.archive), *args])

    def test_apply_minimal_diff(self):
        self.write_overrides(self.standard_entries())
        self.assertEqual(self.run_fold(), 0)
        new_text = self.prof.read_text(encoding="utf-8")
        new = json.loads(new_text)
        hero = new["lightProfiles"]["sarpedon-night"]
        self.assertEqual(hero["heroLight"]["key"]["lux"], 9.5)
        self.assertEqual(new["boards"][self.si]["conceptPaste"]["lit3d"]["lights"][1]["intensityCd"], 120)
        self.assertEqual(hero["exposure"]["ev100"], 2.3)
        self.assertEqual(hero["exposure"]["minBrightness"], hero["exposure"]["maxBrightness"])
        self.assertEqual(new["boards"][self.si]["conceptPaste"]["lit3d"]["materialOverrides"],
                         {"Island": {"tintGain": 1.25}, "Foliage": {"windAmp": 12}})
        self.assertEqual(hero["sky"]["colorLinear"], [0.6, 0.72, 1])
        self.assertEqual(new["revision"], self.base["revision"] + 1)
        # everything else is the same document
        expected = json.loads(self.base_text)
        expected["revision"] += 1
        e = expected["lightProfiles"]["sarpedon-night"]
        e["heroLight"]["key"]["lux"] = 9.5
        e["exposure"].update(ev100=2.3, minBrightness=4.92458, maxBrightness=4.92458)
        e["sky"]["colorLinear"] = [0.6, 0.72, 1]
        lit = expected["boards"][self.si]["conceptPaste"]["lit3d"]
        lit["lights"][1]["intensityCd"] = 120
        lit["materialOverrides"] = {"Island": {"tintGain": 1.25}, "Foliage": {"windAmp": 12}}
        self.assertEqual(new, expected)
        # only the lines that hold the values changed: the revision, the hero light, exposure, sky and the lit3d line
        old_lines = self.base_text.splitlines()
        new_lines = new_text.splitlines()
        self.assertEqual(len(old_lines), len(new_lines))
        changed = [i for i, (a, b) in enumerate(zip(old_lines, new_lines)) if a != b]
        self.assertLessEqual(len(changed), 5, changed)
        # inside a changed line only the value spans moved (same length up to the edits)
        for i in changed:
            a, b = old_lines[i], new_lines[i]
            prefix = 0
            while prefix < min(len(a), len(b)) and a[prefix] == b[prefix]:
                prefix += 1
            self.assertGreater(prefix, 0)
        # the new block in the object's style ("key": value, ", ")
        self.assertIn('"materialOverrides": {"Island": {"tintGain": 1.25}, "Foliage": {"windAmp": 12}}', new_text)
        # the folded board went to the archive, the overrides file is gone
        self.assertFalse(self.ov.exists())
        saves = list(self.archive.glob("*.overrides.json"))
        self.assertEqual(len(saves), 1)
        self.assertEqual(json.loads(saves[0].read_text(encoding="utf-8"))["boards"][0]["board"], "sarpedon-original")

    def test_tint_and_paste_tone(self):
        """The rows added after M6: a material tint ([r, g, b] in a new key of a new look) and the paste tone."""
        si = self.si
        gain_was = self.base["boards"][si]["conceptPaste"]["grade"]["gainLinear"]
        self.write_overrides([
            f'{{"pointer": "/boards/{si}/conceptPaste/lit3d/materialOverrides/Island/tint", "value": [1.1, 0.95, 0.8], "was": null}}',
            f'{{"pointer": "/boards/{si}/conceptPaste/lit3d/materialOverrides/Ship/tintGain", "value": 1.2, "was": null}}',
            f'{{"pointer": "/boards/{si}/conceptPaste/lit3d/materialOverrides/Ship/tint", "value": [0.9, 1, 1.05], "was": null}}',
            f'{{"pointer": "/boards/{si}/conceptPaste/grade/gainLinear", "value": 1.05, "was": {json.dumps(gain_was)}}}',
        ])
        self.assertEqual(self.run_fold(), 0)
        new_text = self.prof.read_text(encoding="utf-8")
        new = json.loads(new_text)
        cp = new["boards"][si]["conceptPaste"]
        self.assertEqual(cp["lit3d"]["materialOverrides"],
                         {"Island": {"tint": [1.1, 0.95, 0.8]}, "Ship": {"tintGain": 1.2, "tint": [0.9, 1, 1.05]}})
        self.assertEqual(cp["grade"]["gainLinear"], 1.05)
        expected = json.loads(self.base_text)
        expected["revision"] += 1
        expected["boards"][si]["conceptPaste"]["grade"]["gainLinear"] = 1.05
        expected["boards"][si]["conceptPaste"]["lit3d"]["materialOverrides"] = cp["lit3d"]["materialOverrides"]
        self.assertEqual(new, expected)
        self.assertEqual(len(self.base_text.splitlines()), len(new_text.splitlines()))

    def test_idempotent(self):
        self.write_overrides(self.standard_entries())
        self.assertEqual(self.run_fold("--no-archive"), 0)
        once = self.prof.read_bytes()
        self.assertEqual(self.run_fold("--no-archive"), 0)
        self.assertEqual(self.prof.read_bytes(), once, "a second fold changes nothing (no second revision bump)")
        self.assertEqual(self.run_fold("--check", "--no-archive"), 0)

    def test_dry_run_and_check(self):
        self.write_overrides(self.standard_entries())
        self.assertEqual(self.run_fold("--dry-run"), 0)
        self.assertEqual(self.prof.read_text(encoding="utf-8"), self.base_text)
        self.assertTrue(self.ov.exists())
        self.assertEqual(self.run_fold("--check"), 1)
        self.assertEqual(self.prof.read_text(encoding="utf-8"), self.base_text)

    def test_crlf_kept(self):
        crlf = self.base_text.replace("\n", "\r\n")
        self.prof.write_bytes(crlf.encode("utf-8"))
        self.write_overrides(self.standard_entries())
        self.assertEqual(self.run_fold("--no-archive"), 0)
        raw = self.prof.read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"), "no lone LF")
        self.assertEqual(raw.count(b"\r\n"), crlf.count("\r\n"))
        self.assertEqual(json.loads(raw.decode("utf-8"))["lightProfiles"]["sarpedon-night"]["heroLight"]["key"]["lux"], 9.5)

    def test_conflict_refused_then_forced(self):
        entries = self.standard_entries()
        entries[0] = '{"pointer": "/lightProfiles/sarpedon-night/heroLight/key/lux", "value": 9.5, "was": 99}'
        self.write_overrides(entries)
        self.assertEqual(self.run_fold(), 2)
        self.assertEqual(self.prof.read_text(encoding="utf-8"), self.base_text, "nothing written on a conflict")
        self.assertTrue(self.ov.exists())
        self.assertEqual(self.run_fold("--force", "--no-archive"), 0)
        self.assertEqual(json.loads(self.prof.read_text(encoding="utf-8"))["lightProfiles"]["sarpedon-night"]["heroLight"]["key"]["lux"], 9.5)

    def test_anchor_mismatch(self):
        # the anchor names a board id the profile no longer has (Cobble City, gone 2026-10-04): refused, nothing written
        self.write_overrides(self.standard_entries(), anchor_index=0, anchor_board="cobble-city")
        self.assertEqual(self.run_fold(), 2)
        self.assertEqual(self.prof.read_text(encoding="utf-8"), self.base_text)

    def test_reanchored_by_board_id(self):
        """A save made while Sarpedon was boards[4] (before the synthetic boards left the profile): the anchor and the
        /boards/4/ pointers move to Sarpedon's index now; the fold equals a save made on the new index."""
        self.assertNotEqual(self.si, 4, "the shipped profile moved Sarpedon off index 4")
        self.write_overrides(self.standard_entries(si=4), anchor_index=4)
        self.assertEqual(self.run_fold("--dry-run"), 0)
        self.assertEqual(self.prof.read_text(encoding="utf-8"), self.base_text)
        self.assertEqual(self.run_fold("--no-archive"), 0)
        moved = self.prof.read_text(encoding="utf-8")
        shutil.copyfile(PROFILES, self.prof)
        self.write_overrides(self.standard_entries())
        self.assertEqual(self.run_fold("--no-archive"), 0)
        self.assertEqual(moved, self.prof.read_text(encoding="utf-8"))
        res = F.fold_text(self.base_text, F.load_overrides(self.ov)[1])
        self.assertEqual(res.reanchored, [], "already on the new index")
        self.write_overrides(self.standard_entries(si=4), anchor_index=4)
        res = F.fold_text(self.base_text, F.load_overrides(self.ov)[1])
        self.assertEqual(res.reanchored, [f"sarpedon-original: /boards/4/ -> /boards/{self.si}/ (the board's index in the profile now)"])
        self.assertEqual(res.conflicts, [])

    def test_other_board_kept_in_the_file(self):
        self.write_overrides(self.standard_entries())
        doc = json.loads(self.ov.read_text(encoding="utf-8"))
        doc["boards"].append({"board": "marmoreal-original", "profile": "marmoreal-night", "anchors": {}, "entries": [
            {"pointer": "/lightProfiles/marmoreal-night/sky/intensity", "value": 3.5, "was": 3.0}]})
        self.ov.write_text(json.dumps(doc, indent=1), encoding="utf-8")
        self.assertEqual(self.run_fold("--board", "sarpedon-original"), 0)
        rest = json.loads(self.ov.read_text(encoding="utf-8"))
        self.assertEqual([b["board"] for b in rest["boards"]], ["marmoreal-original"])
        self.assertNotEqual(json.loads(self.prof.read_text(encoding="utf-8"))["lightProfiles"]["marmoreal-night"]["sky"]["intensity"], 3.5)

    def test_no_file_nothing_to_do(self):
        self.assertEqual(self.run_fold(), 0)
        self.assertEqual(self.prof.read_text(encoding="utf-8"), self.base_text)

    def test_scanner_spans(self):
        text = '{"a": [1, 2.50, {"b": "x\\"y"}], "c": true}'
        root = F.Scanner(text).parse()
        node, _ = F.find(root, ["a", "1"])
        self.assertEqual(text[node.start:node.end], "2.50")
        node, _ = F.find(root, ["a", "2", "b"])
        self.assertEqual(text[node.start:node.end], '"x\\"y"')
        self.assertEqual(F.array_text("[0.6,0.7]", "[0.1, 0.2]"), "[0.1,0.2]")
        self.assertEqual(F.array_text("[0.6, 0.7]", "[0.1,0.2]"), "[0.1, 0.2]")


if __name__ == "__main__":
    unittest.main()
