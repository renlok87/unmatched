"""Wave 5c-B2, B1-8 analysis tools: the thresholds as the analysis applies them (t5cb-thresholds.json over its base,
read-only) and the zone-verdict formula of the hero proxy (= ue_hero_lookdev.cmd_measure)."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE.parent
REPO = ART.parents[1]
sys.path.insert(0, str(ART))
sys.path.insert(0, str(ART / "qa010"))
sys.path.insert(0, str(ART / "material_library"))

E_R3 = REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r3-2026-09-30"
E_R2 = REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29"


class AnalysisThresholds(unittest.TestCase):
    def setUp(self):
        import t53_readability as T53
        self.T53 = T53
        self.before = hashlib.sha256((E_R3 / "t5cb-thresholds.json").read_bytes()).hexdigest()
        self.th = T53.analysis_thresholds(E_R3)

    def test_registered_file_is_not_touched(self):
        self.assertEqual(hashlib.sha256((E_R3 / "t5cb-thresholds.json").read_bytes()).hexdigest(), self.before)

    def test_5cb1_sections_win_and_base_keys_are_inherited(self):
        self.assertEqual(self.th["rings"]["rev"], 3)
        self.assertEqual(self.th["zones"]["rev"], 3)
        self.assertEqual(self.th["light"]["exposure"]["minBrightness"], 4.14106)
        # rev 2 key of the base, not overridden by the 5c-B1 file (rings_rev2 needs it)
        self.assertEqual(self.th["rings"]["keylineVsTile"]["minWcag"], 3.0)
        self.assertIn("team.rim", self.th["calibration"]["bytes"])

    def test_revisions_are_the_base_revision_1_and_own_revisions_are_kept(self):
        rev1 = self.T53.threshold_revision(self.th, 1)
        self.assertIsNotNone(rev1)
        self.assertIn("binding", rev1["tags"])
        self.assertEqual([r["revision"] for r in self.th["revisionsOwn"]], [1])

    def test_w5br_evidence_is_returned_as_registered(self):
        th = self.T53.analysis_thresholds(E_R2)
        self.assertEqual(th, json.loads((E_R2 / "t53-thresholds.json").read_text(encoding="utf-8")))


class HeroZoneFormula(unittest.TestCase):
    def test_zone_verdicts_reproduce_the_measure_of_b1(self):
        import t5cb2_hero_zones as HZ
        for name, spec in HZ.HEROES.items():
            run = REPO / spec["run"]
            cfg = json.loads((run / "review-config.json").read_text(encoding="utf-8"))
            meas = json.loads((run / "review" / "b1" / "measure-b1.json").read_text(encoding="utf-8"))
            concept = json.loads((REPO / cfg["concept_zones"]).read_text(encoding="utf-8"))["zones"]
            stats = {z: zz["reading"] for z, zz in meas["zones"].items() if "reading" in zz}
            v = HZ.zone_verdicts(stats, cfg, concept)
            ref = meas["exposure"]["reading"]
            self.assertAlmostEqual(v["k"], ref["k_concept_over_ue_geomean_key_zones"], places=3, msg=name)
            for z, d in ref["deltas"].items():
                self.assertAlmostEqual(v["deltas"][z]["Yk"], d["Y_ratio_exposure_normalised"], delta=0.002, msg=(name, z))
                self.assertEqual(v["deltas"][z]["all_within"], d["all_within"], msg=(name, z))


if __name__ == "__main__":
    unittest.main()
