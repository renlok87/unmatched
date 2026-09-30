"""5c-B3 target arcs (tools/art/t5cb3_target_arcs.py): geometry helpers of the redraw forecast, the colour-class
distances behind the B1-8 grey failure and the C++ constants of the fix (S08Team.h)."""
from __future__ import annotations

import hashlib
import math
import re
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ART = HERE.parent
REPO = ART.parents[1]
sys.path.insert(0, str(ART))
sys.path.insert(0, str(ART / "qa010"))

TEAM_H = REPO / "unreal/Unmatched/Source/Unmatched/S08/S08Team.h"


class Geometry(unittest.TestCase):
    def setUp(self):
        import t5cb3_target_arcs as TA
        from qa010lib.projection import Camera
        self.TA = TA
        self.cam = Camera(pos=(0.0, 1100.0, 1570.0), rot=(-55.0, -90.0, 0.0), hfov_deg=35.0, viewport=(1920, 1080))

    def test_unproject_inverts_project(self):
        import numpy as np
        pts = [(12.0, -7.5, 3.0), (-40.0, 25.0, 3.0), (0.0, 0.0, 3.0)]
        scr = [self.cam.project(p) for p in pts]
        x, y = self.TA.unproject(self.cam, np.array([s[0] for s in scr]), np.array([s[1] for s in scr]), 3.0)
        for (px, py, _), wx, wy in zip(pts, x, y):
            self.assertAlmostEqual(px, float(wx), places=6)
            self.assertAlmostEqual(py, float(wy), places=6)

    def test_ring_bands_p2_flat_and_corner_gap(self):
        import t53_readability as T53
        import numpy as np
        with T53.RING.using_bands(T53.evidence_ring_bands(T53.thresholds(self.TA.EVID))):
            flat = math.radians(30.0)  # a flat normal of the P2 hexagon (corners at 0/60/...)
            r = np.array([21.0, 22.0, 24.0, 25.8, 26.8, 28.0])
            bands = self.TA.ring_band_of("P2", r * math.cos(flat), r * math.sin(flat), 1.0)
            self.assertEqual(list(bands), ["", "keylineIn", "fill", "keylineOut", "rimOut", ""])
            # across a corner (0 deg) every band is cut by the 2-uu gap
            corner = self.TA.ring_band_of("P2", np.array([24.0 / math.cos(math.radians(30.0))]), np.array([0.0]), 1.0)
            self.assertEqual(corner[0], "")
            circ = self.TA.ring_band_of("P1", np.array([22.5, 24.0]), np.array([0.0, 0.0]), 1.0)
            self.assertEqual(list(circ), ["keylineIn", "fill"])


class ClassDistances(unittest.TestCase):
    def test_old_arcs_are_fill_in_grey_and_no_bright_colour_escapes(self):
        """The 5c-B2 arc bytes are within pixelDeltaE of the P2 fill in grey (the B1-8 failure); in grey the P2 fill
        (L* 52.8) and the P1 fill (79.2) forbid 37.8..94.2 together, so only a dark arc could leave both."""
        import t5cb3_target_arcs as TA
        calib = TA.calib_bytes()
        d = TA.class_distances([251, 137, 74], calib)
        self.assertLess(d["gray"]["team.p2.fill"], TA.PDE)
        p2 = TA.lab(TA.variant(calib["team.p2.fill"], "gray"))[0]
        p1 = TA.lab(TA.variant(calib["team.p1.fill"], "gray"))[0]
        self.assertGreater(p2 + TA.PDE, p1 - TA.PDE)   # the two forbidden bands overlap: no bright escape
        dark = TA.class_distances(TA.screen_of_tint((0.191, 0.063, 0.0203)), calib)
        self.assertGreater(dark["minOverClassesAndVariants"], TA.PDE)

    def test_thresholds_are_only_read(self):
        import t5cb3_target_arcs as TA
        p = TA.EVID / "t5cb-thresholds.json"
        before = hashlib.sha256(p.read_bytes()).hexdigest()
        TA.calib_bytes()
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), before)


class CppConstants(unittest.TestCase):
    def test_arc_scale_keeps_the_inner_keyline_visible(self):
        src = TEAM_H.read_text(encoding="utf-8")

        def num(name):
            m = re.search(r"\b%s\s*=\s*([0-9.]+)f" % name, src)
            self.assertIsNotNone(m, name)
            return float(m.group(1))
        scale, outer = num("TargetArcScale"), num("TargetArcMeshOuterUU")
        self.assertAlmostEqual(outer, 23.0)
        self.assertAlmostEqual(num("TargetArcMeshInnerUU"), 20.9)
        arc_out = outer * scale
        self.assertGreaterEqual(num("P2Fill0") - max(arc_out, num("P2KeylineIn0")), 1.0)
        self.assertGreaterEqual(num("P1Fill0") - max(arc_out, num("P1KeylineIn0")), 1.0)
        import t5cb3_target_arcs as TA
        self.assertEqual(TA.ARC_BAND_UU, (20.9, 23.0))


if __name__ == "__main__":
    unittest.main()
