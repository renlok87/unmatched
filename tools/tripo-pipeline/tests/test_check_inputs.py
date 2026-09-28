"""Tests for check_inputs.py selection coverage: a view listed in generation-inputs.json
without a normalization record (or file) must FAIL instead of silently dropping out of
manifest.json.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
Reads art/imagegen/mvp-v1 only; nothing is written there (the end-to-end test uses --check-only).
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
try:
    import check_inputs as ci  # noqa: E402  (needs numpy, Pillow, SciPy)
except ImportError as exc:  # pragma: no cover
    ci = None
    IMPORT_ERROR = exc


@unittest.skipIf(ci is None, "check_inputs dependencies (numpy/Pillow/SciPy) are not installed")
class SelectionCoverageTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="check_inputs_test_")
        self.pkg = Path(self._tmp.name)
        for rel in ("characters/h-front.png", "characters/h-right.png", "environment/b-front.png"):
            (self.pkg / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.pkg / rel).write_bytes(b"png")
        self.gen = {
            "characters": [{"assetId": "REF-HARPY",
                            "views": [{"role": "front", "path": "characters/h-front.png"}],
                            "candidateViewsExcluded": [{"role": "right", "path": "characters/h-right.png"}]}],
            "props": [{"assetId": "REF-BARREL", "referenceViews": [{"role": "front", "path": "environment/b-front.png"}]}],
        }
        self.norm = {
            "characters/h-front.png": {"assetId": "REF-HARPY", "role": "front", "normalizationRecord": "n.json"},
            "characters/h-right.png": {"assetId": "REF-HARPY", "role": "right", "normalizationRecord": "n.json"},
            "environment/b-front.png": {"assetId": "REF-BARREL", "role": "front", "normalizationRecord": "e.json"},
        }

    def tearDown(self):
        self._tmp.cleanup()

    def results(self, gen=None, norm=None):
        rows = ci.selection_coverage(gen or self.gen, self.norm if norm is None else norm, self.pkg)
        return {r["path"].rsplit("/", 1)[-1]: r for r in rows}

    def test_fully_covered_selection_passes(self):
        rows = self.results()
        self.assertEqual({k: r["result"] for k, r in rows.items()},
                         {"h-front.png": "PASS", "h-right.png": "PASS", "b-front.png": "PASS"})

    def test_missing_record_fails_for_each_selection_list(self):
        for missing in ("characters/h-front.png", "characters/h-right.png", "environment/b-front.png"):
            with self.subTest(missing=missing):
                norm = {k: v for k, v in self.norm.items() if k != missing}
                row = self.results(norm=norm)[missing.rsplit("/", 1)[-1]]
                self.assertEqual(row["result"], "FAIL")
                self.assertTrue(any("no normalization record" in p for p in row["detail"]["problems"]))

    def test_missing_file_fails(self):
        (self.pkg / "characters/h-right.png").unlink()
        row = self.results()["h-right.png"]
        self.assertEqual(row["result"], "FAIL")
        self.assertIn("file missing", row["detail"]["problems"])

    def test_record_of_other_asset_or_role_fails(self):
        norm = dict(self.norm)
        norm["characters/h-front.png"] = {"assetId": "REF-MEDUSA", "role": "back", "normalizationRecord": "n.json"}
        problems = " | ".join(self.results(norm=norm)["h-front.png"]["detail"]["problems"])
        self.assertIn("assetId 'REF-MEDUSA' != 'REF-HARPY'", problems)
        self.assertIn("role 'back' != selected role 'front'", problems)

    def test_unmapped_ref_id_fails(self):
        gen = {"characters": [], "props": [{"assetId": "REF-UNKNOWN",
                                            "referenceViews": [{"role": "front", "path": "environment/b-front.png"}]}]}
        norm = {"environment/b-front.png": {"assetId": "REF-UNKNOWN", "role": "front", "normalizationRecord": "e.json"}}
        row = self.results(gen=gen, norm=norm)["b-front.png"]
        self.assertEqual(row["result"], "FAIL")
        self.assertTrue(any("not mapped" in p for p in row["detail"]["problems"]))

    def test_real_selection_is_fully_covered(self):
        gen, norm, _ = ci.load_selection()
        rows = ci.selection_coverage(gen, norm, ci.ROOT / ci.PACKAGE)
        self.assertEqual(len(rows), len(ci.selection_views(gen)))
        self.assertTrue(rows)
        self.assertEqual([r["path"] for r in rows if r["result"] != "PASS"], [])

    def test_dropped_candidate_record_makes_exit_code_1(self):
        """normalized-v4.json holds only candidate-excluded views (Arthur v7-right, Merlin v5-left).
        Before the coverage check, dropping it left exit code 0 and the views silently vanished."""
        files = [n for n in ci.NORMALIZATION_FILES if n != "normalized-v4.json"]
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(ci, "NORMALIZATION_FILES", files), \
                mock.patch.object(sys, "argv", ["check_inputs.py", "--check-only"]), \
                contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = ci.main()
        summary = json.loads(out.getvalue().splitlines()[0])
        self.assertEqual(code, 1)
        self.assertEqual(summary["failuresOnRecommended"], 0)
        self.assertEqual(summary["failuresOnSelectionCoverage"], 2)
        self.assertIn("ref-king-arthur-v7-right.png", err.getvalue())
        self.assertIn("ref-merlin-v5-left.png", err.getvalue())


if __name__ == "__main__":
    unittest.main()
