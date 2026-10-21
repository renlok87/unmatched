"""model_prompt.py: шаблон §8.2 извлекается целиком, плейсхолдеры заполняются, профиль первого и второго приёмщика."""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import model_prompt as mp  # noqa: E402


class TemplateTest(unittest.TestCase):
    def test_template_is_the_whole_markdown_block(self):
        t = mp.template()
        self.assertTrue(t.startswith("# Приёмка модели {{ASSET_ID}}"))
        self.assertIn("Ответ — только JSON карточки", t)
        self.assertNotIn("```", t)

    def test_every_template_placeholder_is_known(self):
        names = set(re.findall(r"\{\{([A-Z_]+)\}\}", mp.template()))
        filled_by_tool = {"ASSET_ID", "CYCLE", "DATE", "E", "SIDE_VIEW", "SIDE_TURN", "QUALITY_REFERENCE", "BAKE", "LD",
                          "ROLE", "PALETTE", "WEAPON_HAND", "POLY_BUDGET", "PREVIOUS_CARD", "PREVIOUS_CARD_JSON",
                          "ACCEPTED_OBJECT_JSON", "FRAMES_FILES_JSON", "ACCEPTOR_PROFILE", "ACCEPTOR_SESSION_ID",
                          "EXECUTOR_SESSION_ID"}
        from_inputs = {"UE_NAMES", "BAKE_PROFILE_KEYS", "HEIGHT_RULE", "TA_REPORT", "ANCHORS", "PREV_FIX_LIST"}
        self.assertEqual(names - filled_by_tool - from_inputs, set())

    def test_palette_line(self):
        p = {"main": [{"name": "suit yellow", "hex": "#E0B830"}], "accent": {"name": "shoe black", "hex": "#1E1C1C"}}
        self.assertEqual(mp.palette(p), "main: suit yellow #E0B830; accent: shoe black #1E1C1C")


class BuildTest(unittest.TestCase):
    def _evidence(self, root: Path, prev=None) -> Path:
        asset = root / "art/pipeline-candidates/ASSET-TEST-001"
        ev = asset / "evidence/acceptance/20261021-r2"
        (ev / "frames").mkdir(parents=True)
        (asset / "asset-card.yaml").write_text(
            "ASSET_ID: ASSET-TEST-001\nROLE: hero\nWEAPON_HAND: none\nSIDE_VIEW: right\n"
            "POLY_BUDGET: {figure_tris_max: 45000, base_tris_max: 2500}\n"
            "PALETTE:\n  main:\n    - {name: red, hex: '#FF0000'}\n  accent: {name: gold, hex: '#C9A24A'}\n"
            "QUALITY_REFERENCE:\n  - art/imagegen/hero-quality-v1/reference/medusa-quality-reference.png\n",
            encoding="utf-8")
        (ev / "frames/frames.json").write_text(json.dumps({
            "accepted_object": [{"path": "a.fbx", "sha256": "0" * 64}], "files": ["turn-000.jpg", "frames.json"],
            "side_view": "right"}), encoding="utf-8")
        rel = lambda p: p.relative_to(root).as_posix()  # noqa: E731
        (ev / "acceptor-inputs.json").write_text(json.dumps({
            "sources": {"asset_card": {"path": rel(asset / "asset-card.yaml")}, "bake_run": "B", "look_dev_run": "L",
                        "previous_card": prev},
            "placeholders": {k: k.lower() for k in ("UE_NAMES", "BAKE_PROFILE_KEYS", "HEIGHT_RULE", "TA_REPORT",
                                                     "ANCHORS", "PREV_FIX_LIST")}}), encoding="utf-8")
        return ev

    def test_first_and_second_acceptor(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            old = mp.REPO
            mp.REPO = root
            try:
                ev = self._evidence(root, prev="x/card.json")
                first = mp.build(ev, "exec-1", False, None)
                second = mp.build(ev, "exec-1", True, None)
            finally:
                mp.REPO = old
        self.assertNotRegex(first, r"\{\{[A-Z_]+\}\}")
        self.assertIn('"profile": "Opus xhigh", "session_id": "workflow:acceptor-ASSET-TEST-001-r2"', first)
        self.assertIn('"profile": "Opus high", "session_id": "workflow:acceptor2-ASSET-TEST-001-r2"', second)
        self.assertIn("compare-side сделан с turn-270.jpg", first)
        self.assertIn('previous_card "x/card.json"', first)
        self.assertIn('date "2026-10-21"', first)


if __name__ == "__main__":
    unittest.main()
