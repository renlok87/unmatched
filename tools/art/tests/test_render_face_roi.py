"""Tests for the face ROI rule of tools/art/render/render_bench.py (W4-A fix).

The first rule centred the ROI on the Head socket's screen X and missed the face.
These tests pin the corrected placement for the v2 candidate at K2 5x (the traced
Head line of every W4-A K2 5x frame) and the cases that must not get a face ROI.

  python -m unittest discover -s tools/art/tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "render"))

import render_bench as B  # noqa: E402

K2_HEAD = {"fighter": "f-0-hero", "socket": "Head", "mesh": "SK_Medusa_FaceNeck_v2Candidate",
           "world": "(0.0,-46.0,38.5)", "screen": "(960.0,517.7)", "top": "(960.0,489.1)",
           "bottom": "(960.0,545.6)", "headPx": "56.4", "projected": "1"}
K1_HEAD = dict(K2_HEAD, screen="(960.0,445.5)", top="(960.0,439.8)", bottom="(960.0,451.2)", headPx="11.4")


class FaceBoxes(unittest.TestCase):
    def test_k2_5x_boxes_sit_on_the_face(self):
        boxes, why = B.face_boxes(K2_HEAD)
        self.assertIsNone(why)
        self.assertEqual(boxes["faceRoi"][0], (925, 464, 958, 480))
        self.assertEqual(boxes["faceNeckRoi"][0], (924, 462, 956, 490))
        # the face is left of the socket X (the withdrawn rule centred its box on x = 960)
        for box, _ in boxes.values():
            self.assertLess((box[0] + box[2]) / 2, 945)
            self.assertLess(box[2], 960)

    def test_small_head_unknown_mesh_and_missing_head_are_skipped(self):
        self.assertIn("too small", B.face_boxes(K1_HEAD)[1])
        self.assertIn("no face ROI calibration", B.face_boxes(dict(K2_HEAD, mesh="SK_Other"))[1])
        self.assertIn("no projected Head", B.face_boxes(None)[1])
        self.assertIn("no projected Head", B.face_boxes(dict(K2_HEAD, projected="0"))[1])

    def test_boxes_scale_with_the_head(self):
        boxes, _ = B.face_boxes(dict(K2_HEAD, headPx="112.8"))  # twice the size
        x0, y0, x1, y1 = boxes["faceRoi"][0]
        self.assertAlmostEqual((x1 - x0), 2 * (958 - 925), delta=1)
        self.assertAlmostEqual((y1 - y0), 2 * (480 - 464), delta=1)


class RoiStats(unittest.TestCase):
    def test_percentiles_and_empty_box(self):
        import numpy as np
        L = np.zeros((20, 20))
        L[:, 10:] = 200.0
        st = B.roi_stats(L, (0, 0, 20, 20))
        self.assertEqual(st["pixels"], 400)
        self.assertEqual(st["mean"], 100.0)
        self.assertEqual(st["p5"], 0.0)
        self.assertEqual(st["p95"], 200.0)
        self.assertEqual(B.roi_stats(L, (5, 5, 5, 9))["pixels"], 0)


if __name__ == "__main__":
    unittest.main()
