"""Negative tests for validate_registry.py: acceptanceEvidence rules and parent/child status order.

Run from the repo root:  python -m unittest discover -s tools/tripo-pipeline/tests -v
Synthetic registries and acts are written only to temporary directories. The real
docs/art-pipeline/asset-registry.json is read, never modified.
"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent))
import validate_registry as vr  # noqa: E402

ACT_PATH = "docs/game-design/evidence/ART-004/acceptance-test.md"
ACT_ACCEPTED = "# ART-004 · тестовый акт\n\n**Решение: принято.** Фигурка читается на K1–K3.\n"


def ref(path, expect="exists", kind="file", root="repo", role="test", **extra):
    return {"path": path, "root": root, "kind": kind, "expect": expect, "role": role, **extra}


def asset(aid, status, parent=None, acceptance=()):
    return {
        "id": aid, "name": aid, "category": "hero", "contentKey": "medusa",
        "manifest06Row": "ASSET-MEDUSA-001", "backlog": ["ART-004"], "parent": parent, "instances": 1,
        "status": status, "stage": "ue-editor-frames",
        "ownership": {"existingFiles": "art-chat", "nextCandidates": "pipeline", "acceptance": "art-chat"},
        "sourceImages": {"selectionManifest": None, "recommended": [], "excludedCandidates": [], "note": ""},
        "source3d": [], "layers": [],
        "manifest06": {"verificationStatusIn06": "planned", "drift": "-", "proposedChange": "-"},
        "nextStep": "next", "blocker": "none", "doneCriteria": "done",
        "acceptanceEvidence": list(acceptance),
        "evidence": [ref("notes/import-report.json")],
        "plannedPaths": [],
    }


def registry(*assets):
    return {"schemaVersion": 1, "snapshotDate": "2026-09-28", "baseline": {}, "vocabularies": {},
            "assets": list(assets)}


class ValidateRegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="validate_registry_test_")
        self.root = Path(self._tmp.name)
        self.write("notes/import-report.json", "{}")
        self.write("README.md", "# not an act\n\n**Решение: принято.**\n")
        self.write(ACT_PATH, ACT_ACCEPTED)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def run_validate(self, reg):
        rep = vr.Report()
        roots = {"repo": self.root, "art-worktree": None}
        git = {"repo": vr.GitState(self.root), "art-worktree": vr.GitState(self.root / "__missing__")}
        vr.validate(reg, roots, git, rep)
        return rep

    def assertError(self, rep, fragment):
        self.assertTrue(any(fragment in e for e in rep.errors),
                        f"expected an error containing {fragment!r}; errors: {rep.errors}")

    def assertNoErrors(self, rep):
        self.assertEqual(rep.errors, [])

    # ---- positive baselines ---------------------------------------------------------
    def test_accepted_parent_and_child_with_valid_act_pass(self):
        reg = registry(asset("P", "художественно принято", acceptance=[ref(ACT_PATH)]),
                       asset("P.CHILD", "художественно принято", parent="P", acceptance=[ref(ACT_PATH)]))
        self.assertNoErrors(self.run_validate(reg))

    def test_decision_line_formats_accepted(self):
        for i, line in enumerate(["**Решение:** принято.", "Решение: художественно принято",
                                  "> **Решение**: принята", "**Решение: ПРИНЯТО**"]):
            with self.subTest(line=line):
                path = f"docs/game-design/evidence/GD-058/act-{i}.md"
                self.write(path, f"# акт\n\n{line}\n")
                reg = registry(asset("P", "художественно принято", acceptance=[ref(path)]))
                self.assertNoErrors(self.run_validate(reg))

    def test_child_at_or_below_parent_passes(self):
        reg = registry(asset("P", "технически импортировано"),
                       asset("P.SAME", "технически импортировано", parent="P"),
                       asset("P.LOWER", "предложено", parent="P"))
        self.assertNoErrors(self.run_validate(reg))

    # ---- acceptanceEvidence location --------------------------------------------------
    def test_act_outside_evidence_folder_rejected(self):
        reg = registry(asset("P", "художественно принято", acceptance=[ref("README.md")]))
        rep = self.run_validate(reg)
        self.assertError(rep, "acceptance act must be docs/game-design/evidence/(ART|GD)-NNN")
        self.assertError(rep, "requires acceptanceEvidence")

    def test_act_in_non_art_gd_folder_rejected(self):
        path = "docs/game-design/evidence/S08/review.md"
        self.write(path, ACT_ACCEPTED)
        rep = self.run_validate(registry(asset("P", "художественно принято", acceptance=[ref(path)])))
        self.assertError(rep, "acceptance act must be docs/game-design/evidence/(ART|GD)-NNN")

    def test_act_non_markdown_rejected(self):
        path = "docs/game-design/evidence/ART-004/report.json"
        self.write(path, ACT_ACCEPTED)
        rep = self.run_validate(registry(asset("P", "художественно принято", acceptance=[ref(path)])))
        self.assertError(rep, "acceptance act must be docs/game-design/evidence/(ART|GD)-NNN")

    def test_act_path_traversal_rejected(self):
        path = "docs/game-design/evidence/ART-004/../../../../README.md"
        rep = self.run_validate(registry(asset("P", "художественно принято", acceptance=[ref(path)])))
        self.assertError(rep, "acceptance act must be docs/game-design/evidence/(ART|GD)-NNN")

    def test_act_in_art_worktree_rejected(self):
        reg = registry(asset("P", "художественно принято", acceptance=[ref(ACT_PATH, root="art-worktree")]))
        rep = self.run_validate(reg)
        self.assertError(rep, "root 'repo'")
        self.assertError(rep, "requires acceptanceEvidence")

    def test_planned_act_rejected(self):
        reg = registry(asset("P", "художественно принято", acceptance=[ref(ACT_PATH, expect="planned")]))
        rep = self.run_validate(reg)
        self.assertError(rep, "expect 'exists'")
        self.assertError(rep, "requires acceptanceEvidence")

    def test_missing_act_rejected(self):
        path = "docs/game-design/evidence/ART-004/absent.md"
        rep = self.run_validate(registry(asset("P", "художественно принято", acceptance=[ref(path)])))
        self.assertError(rep, "missing repo:" + path)
        self.assertError(rep, "requires acceptanceEvidence")

    def test_accepted_without_act_rejected(self):
        rep = self.run_validate(registry(asset("P", "художественно принято")))
        self.assertError(rep, "requires acceptanceEvidence")

    # ---- decision line ------------------------------------------------------------------
    def test_act_without_decision_line_rejected(self):
        path = "docs/game-design/evidence/ART-004/no-decision.md"
        self.write(path, "# акт\n\nКадры сняты, всё выглядит хорошо. Медуза принята арт-чатом.\n")
        rep = self.run_validate(registry(asset("P", "художественно принято", acceptance=[ref(path)])))
        self.assertError(rep, "no explicit decision line")
        self.assertError(rep, "requires acceptanceEvidence")

    def test_negative_or_technical_decisions_rejected(self):
        for i, line in enumerate(["**Решение: GD-058 не принят; ART-004 не закрыт.**",
                                  "**Решение:** не принято.",
                                  "**Решение: доработать (v3.1).**",
                                  "**Решение:** [FBX v2](x.md) принят как изолированный технический кандидат.",
                                  "Решение: принятие отложено"]):
            with self.subTest(line=line):
                path = f"docs/game-design/evidence/ART-004/negative-{i}.md"
                self.write(path, f"# акт\n\n{line}\n")
                rep = self.run_validate(registry(asset("P", "художественно принято", acceptance=[ref(path)])))
                self.assertError(rep, "no explicit decision line")

    # ---- parent / child order -----------------------------------------------------------
    def test_accepted_child_under_imported_parent_rejected(self):
        reg = registry(asset("P", "технически импортировано"),
                       asset("P.CHILD", "художественно принято", parent="P", acceptance=[ref(ACT_PATH)]))
        self.assertError(self.run_validate(reg), "is above its parent P")

    def test_measured_child_under_proposed_parent_rejected(self):
        reg = registry(asset("P", "предложено"), asset("P.CHILD", "измерено", parent="P"))
        self.assertError(self.run_validate(reg), "is above its parent P")

    def test_parent_order_independent_of_record_order(self):
        reg = registry(asset("P.CHILD", "технически импортировано", parent="P"), asset("P", "предложено"))
        self.assertError(self.run_validate(reg), "is above its parent P")

    def test_self_parent_rejected(self):
        self.assertError(self.run_validate(registry(asset("P", "предложено", parent="P"))), "refers to the record itself")

    def test_layer_cannot_claim_acceptance(self):
        a = asset("P", "технически импортировано")
        a["layers"] = [{"layer": "L", "stage": "ue-editor-frames", "status": "художественно принято",
                        "owner": "art-chat", "paths": [], "note": ""}]
        self.assertError(self.run_validate(registry(a)), "layer claims artistic acceptance")

    # ---- regressions of the original T1 checks ------------------------------------------
    def test_original_negative_cases_still_fail(self):
        base = asset("P", "предложено")
        cases = {
            "duplicate asset id": registry(base, copy.deepcopy(base)),
            "backlog id 'ART-999'": registry({**base, "backlog": ["ART-999"]}),
            "sha256 mismatch": registry({**base, "evidence": [ref("notes/import-report.json", sha256="0" * 64)]}),
            "missing repo:notes/absent.md": registry({**base, "evidence": [ref("notes/absent.md")]}),
            "neither a registry id nor a 06 assetKey": registry({**base, "parent": "NOPE-404"}),
        }
        for fragment, reg in cases.items():
            with self.subTest(fragment=fragment):
                self.assertError(self.run_validate(reg), fragment)


class RealRegistryTests(unittest.TestCase):
    def test_real_registry_has_no_errors(self):
        reg = json.loads(vr.DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        art = vr.DEFAULT_ART_WORKTREE if vr.DEFAULT_ART_WORKTREE.exists() else None
        rep = vr.Report()
        git = {"repo": vr.GitState(vr.REPO_ROOT),
               "art-worktree": vr.GitState(art) if art else vr.GitState(Path("__missing__"))}
        vr.validate(reg, {"repo": vr.REPO_ROOT, "art-worktree": art}, git, rep)
        self.assertEqual(rep.errors, [])


if __name__ == "__main__":
    unittest.main()
