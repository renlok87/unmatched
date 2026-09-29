"""Tests of the W5-live3 readability re-measurement in tools/art/t52_art3_live.py (stage 3 T5.2 review).

Synthetic cases pin the rules (explicit icon mask vs auto-Otsu on a light tile, multizone readability,
label contrast and damage-number collisions); the repository cases re-check the published T5.2 frames.
Nothing is written outside a temp dir.

  python -m unittest discover -s tools/art/tests -p test_t52_readability.py -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "qa010"))

import t52_art3_live as t52  # noqa: E402

EV = t52.REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-2026-09-29"
TS = "2026.09.29-09.00.00"


def trace_text(png_name: str, lines: list[str]) -> str:
    body = [f"{TS} SHOT ctx viewport=200x100 viewTarget=Cam cam=(0,959,1370) rot=(-55,-90,0)"]
    body += [f"{TS} {ln}" for ln in lines]
    body.append(f"{TS} SHOT requested: FScreenshotRequest(bShowUI) -> C:\\tmp\\x\\{png_name}")
    return "\n".join(body) + "\n"


def draw_text_block(img: np.ndarray, x0: int, y0: int, x1: int, y1: int) -> None:
    """Crude 'letters': 2-px white vertical strokes every 4 px on rows y0+2..y1-2."""
    for x in range(x0 + 2, x1 - 2, 4):
        img[y0 + 2:y1 - 2, x:x + 2] = 242


class Helpers(unittest.TestCase):
    def test_iou_and_dilate(self):
        a = np.zeros((8, 8), dtype=bool)
        a[3, 3] = True
        d = t52._dilate(a, 1)
        self.assertEqual(int(d.sum()), 9)
        self.assertEqual(t52._iou(a, d), round(1 / 9, 4))
        self.assertEqual(t52._iou(np.zeros_like(a), np.zeros_like(a)), 0.0)

    def test_multizone_readability_geometry_is_not_readability(self):
        cells = [{"x": 0, "y": 0, "zones": ["gray", "orange"], "obstacle": False},
                 {"x": 1, "y": 0, "zones": ["green", "orange"], "obstacle": False},
                 {"x": 2, "y": 0, "zones": ["yellow", "green"], "obstacle": False},
                 {"x": 3, "y": 0, "zones": ["gray"], "obstacle": False},
                 {"x": 4, "y": 0, "zones": ["gray", "green"], "obstacle": True}]
        zones = {"gray": {"visible": False, "variants": {"gray": {"wcag": 1.21}}},
                 "orange": {"visible": True, "variants": {"gray": {"wcag": 1.5}}},
                 "green": {"visible": True, "variants": {"gray": {"wcag": 1.52}}},
                 "yellow": {"visible": True, "variants": {"gray": {"wcag": 1.09}}}}
        r = t52.multizone_readability(cells, zones)
        self.assertEqual(r["multizoneCells"], 3)  # the obstacle cell is not a board space
        self.assertEqual(r["unreadableZones"], ["gray"])
        self.assertEqual([c["cell"] for c in r["cellsWithUnreadableZone"]], [[0, 0]])
        self.assertEqual(r["cellsLosingAZoneInGray"], [[0, 0], [2, 0]])


class Labels(unittest.TestCase):
    def test_white_label_on_light_tile_fails_and_on_void_passes(self):
        img = np.zeros((100, 200, 3), dtype=np.uint8)
        img[:, :100] = 190  # light fixture tile
        draw_text_block(img, 10, 10, 90, 44)
        draw_text_block(img, 110, 10, 190, 44)  # over the black void
        img[60:80, 40:70] = 190
        draw_text_block(img, 40, 60, 70, 80)
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "frame.png"
            Image.fromarray(img).save(png)
            tr = Path(td) / "c.trace.log"
            tr.write_text(trace_text("frame.png", [
                "SHOT label fighter=f-0-sk0 mode=full bbox=(10,10,90,44)",
                "SHOT label fighter=f-1-hero mode=full bbox=(110,10,190,44)",
                "SHOT damage fighter=f-1-hero bbox=(40,30,70,80)"]), encoding="utf-8")
            doc = t52.label_metrics(png, tr)
        items = {(i["kind"], i["fighter"]): i for i in doc["items"]}
        light = items[("label", "f-0-sk0")]
        void = items[("label", "f-1-hero")]
        dmg = items[("damage", "f-1-hero")]
        self.assertEqual(light["name"], "Harpies 1")
        self.assertEqual(light["verdict"], "fail")
        self.assertLess(light["crWorst"], 2.0)
        self.assertEqual(void["verdict"], "AA")
        self.assertGreater(void["crWorst"], 10.0)
        self.assertEqual([h["label"] for h in dmg["collidesWithLabels"]], ["Harpies 1"])
        self.assertAlmostEqual(dmg["collidesWithLabels"][0]["shareOfDamageBbox"], 0.28, places=2)


class IconGuard(unittest.TestCase):
    def test_auto_otsu_takes_the_dark_class_on_a_light_tile(self):
        """Light blades ~ tile, dark hilts + a dark pedestal inside the bbox: Otsu picks the dark class,
        the explicit mask measures the icon (~1:1 blades), the guard marks the auto mask invalid."""
        h, w = 100, 200
        img = np.full((h, w, 3), 188, dtype=np.uint8)
        x0, y0 = 80, 30
        tm = np.zeros((32, 32), dtype=bool)
        for i in range(4, 24):
            tm[i, i:i + 3] = True           # blade 1
            tm[i, 31 - i - 3:31 - i] = True  # blade 2
        hilts = np.zeros_like(tm)
        hilts[24:30, 6:12] = True
        hilts[24:30, 20:26] = True
        tm |= hilts
        box = img[y0:y0 + 32, x0:x0 + 32]
        box[tm] = 202
        box[hilts] = 120
        box[0:4, 0:20] = 60  # pedestal of the fighter behind the target, inside the bbox
        with tempfile.TemporaryDirectory() as td:
            png = Path(td) / "k3.png"
            Image.fromarray(img).save(png)
            mask = Path(td) / "tmpl.png"
            Image.fromarray((tm * 255).astype(np.uint8), "L").save(mask)
            tr = Path(td) / "c.trace.log"
            tr.write_text(trace_text("k3.png", [f"SHOT icon fighter=f-1-hero bbox=({x0},{y0},{x0 + 32},{y0 + 32})"]),
                          encoding="utf-8")
            from qa010lib.checks import IconParams, check_icon
            params = IconParams(ring_min_px=8)  # qa010 defaults; ring 8 px as in the T5.2 icon-k3.json
            rgb = np.asarray(Image.open(png).convert("RGB"))
            masked = check_icon(rgb, (x0, y0, x0 + 32, y0 + 32), params, tm)
            auto = check_icon(rgb, (x0, y0, x0 + 32, y0 + 32), params, None)
            g = t52.icon_guard(png, tr, "k3.png", mask, masked, auto, Path(td) / "missing.png")
        self.assertEqual(auto["foreground"]["foreground"], "dark")
        self.assertGreater(min(s["contrast_ratio"] for s in auto["sizes"]), 1.5)  # the inflated number
        self.assertLess(max(s["contrast_ratio"] for s in masked["sizes"]), 1.3)
        self.assertFalse(g["autoOtsu"]["valid"])
        self.assertGreater(g["autoOtsu"]["pixelsOutsideTemplate"], 0)  # the pedestal
        self.assertGreater(g["bboxBackground"]["foreignDarkPixels"], 0)
        self.assertLess(g["partsVsTile"]["blades"]["wcagVsTile"], 1.2)
        self.assertFalse(g["iconInPixels"]["available"])
        self.assertTrue(g["verdict"].startswith("no data"))


@unittest.skipUnless((EV / "analysis" / "icon-mask-template-32.png").is_file(), "T5.2 evidence not present")
class Repository(unittest.TestCase):
    def test_sherwood_icon_rev2(self):
        k3 = EV / "k3/sherwood-forest-8x5/combat-20260929-143030"
        doc = json.loads((EV / "analysis/sherwood-forest-8x5/icon-k3.json").read_text(encoding="utf-8"))
        self.assertEqual(doc["foreground"]["method"], "mask")
        self.assertTrue(all(s["contrast_ratio"] < 1.2 and not s["pass"] for s in doc["sizes"]))
        auto = json.loads((EV / "analysis/sherwood-forest-8x5/icon-k3-auto-otsu.json").read_text(encoding="utf-8"))
        g = t52.icon_guard(k3 / "joiner/s09-combat-resolve-revealed.png", k3 / "combat-client-joiner.trace.log",
                           "s09-combat-resolve-revealed.png", EV / t52.ICON_TEMPLATE, doc, auto,
                           k3 / "joiner" / t52.ICON_NO_ICON_FRAME)
        self.assertTrue(g["iconInPixels"]["present"])
        self.assertEqual(g["autoOtsu"]["foreground"], "dark")
        self.assertFalse(g["autoOtsu"]["valid"])

    def test_sherwood_merlin_ring_missing_on_k1_joiner(self):
        run = EV / "k1/sherwood-forest-8x5/run-20260929-141815"
        doc = t52.ring_metrics(run / "phase2-board-joiner-1920x1080.png", run / "phase2-client-joiner.trace.log",
                               "joiner")
        rows = {r["fighter"]: r for r in doc["fighters"]}
        self.assertEqual(doc["ownSide"], "f-1")
        self.assertEqual(rows["f-1-sk0"]["cell"], [5, 3])
        self.assertFalse(rows["f-1-sk0"]["visible"])
        self.assertTrue(rows["f-1-hero"]["visible"])
        self.assertEqual(rows["f-1-hero"]["expected"], "blue")
        self.assertEqual(rows["f-0-hero"]["expected"], "red")


if __name__ == "__main__":
    unittest.main()
