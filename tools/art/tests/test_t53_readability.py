"""Tests of the W5b-R board readability fix (t53): one palette across tokens / C++ / um-masters / thresholds,
the ring geometry across Python and C++, the late SHOT section parser, the SHOT captured pixel provenance
(classify_evidence S6) and the ring shape classifier on synthetic top-down frames.

  python -m pytest tools/art/tests/test_t53_readability.py -v
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "qa010"))

import classify_evidence as CE  # noqa: E402
import t53_readability as T53  # noqa: E402
import t53_team_ring as RING  # noqa: E402
from qa010lib.projection import Camera  # noqa: E402
from qa010lib.trace import parse_trace  # noqa: E402

REPO = T53.REPO
S08 = REPO / "unreal/Unmatched/Source/Unmatched/S08"
EVID = REPO / "docs/game-design/evidence/ART-005/art3-live-3boards-r2-2026-09-29"
TS = "2026.09.29-12.00.00"


def hex_bytes(h: str) -> list[int]:
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def cpp_text(name: str) -> str:
    return (S08 / name).read_text(encoding="utf-8")


class PaletteConsistency(unittest.TestCase):
    """team.p1 / team.p2 / screen / keyline: one set of values everywhere (plan step 7)."""

    def setUp(self):
        self.tokens = json.loads(T53.TOKENS.read_text(encoding="utf-8"))["colors"]
        self.team_h = cpp_text("S08Team.h")
        self.style_h = cpp_text("S08ArtHudStyle.h")

    def cpp_hex(self, name: str) -> str:
        m = re.search(rf'{name}\s*=\s*TEXT\("(#[0-9A-Fa-f]{{6}})"\)', self.team_h)
        self.assertIsNotNone(m, name)
        return m.group(1).upper()

    def test_tokens_equal_cpp(self):
        self.assertEqual(self.tokens["team.p1"]["hex"].upper(), self.cpp_hex("P1Hex"))
        self.assertEqual(self.tokens["team.p2"]["hex"].upper(), self.cpp_hex("P2Hex"))
        self.assertEqual(self.tokens["team.p1.screen"]["hex"].upper(), self.cpp_hex("P1ScreenHex"))
        self.assertEqual(self.tokens["team.p2.screen"]["hex"].upper(), self.cpp_hex("P2ScreenHex"))
        self.assertEqual(self.tokens["mark.keyline"]["hex"].upper(), self.cpp_hex("KeylineHex"))

    def test_um_masters_active_palette(self):
        um = json.loads((REPO / "art/um-materials/um-masters.json").read_text(encoding="utf-8"))["team_palette"]
        active = um[um["active"]]
        self.assertEqual(active["Gold"].upper(), self.tokens["team.p1"]["hex"].upper())
        self.assertEqual(active["Silver"].upper(), self.tokens["team.p2"]["hex"].upper())

    def test_chip_bytes_are_the_calibrated_screen_bytes(self):
        th = json.loads((EVID / "t53-thresholds.json").read_text(encoding="utf-8"))["calibration"]["bytes"]
        for slot, tok in (("P1", "team.p1"), ("P2", "team.p2")):
            m = re.search(rf"TeamChip{slot} = FColor\((\d+), (\d+), (\d+), 255\)", self.style_h)
            self.assertIsNotNone(m, slot)
            chip = [int(x) for x in m.groups()]
            self.assertEqual(chip, hex_bytes(self.tokens[tok + ".screen"]["hex"]))
            self.assertEqual(chip, th[tok + ".fill"]["screen"])
            self.assertEqual(self.tokens[tok]["hex"].upper(), th[tok + ".fill"]["hex"].upper())

    def test_ring_tool_reads_the_tokens(self):
        th = RING.team_hex()
        self.assertEqual(th["p1"].upper(), self.tokens["team.p1"]["hex"].upper())
        self.assertEqual(th["p2"].upper(), self.tokens["team.p2"]["hex"].upper())
        self.assertEqual(th["keyline"].upper(), self.tokens["mark.keyline"]["hex"].upper())


class RingSpecConsistency(unittest.TestCase):
    def test_python_spec_equals_cpp(self):
        h = cpp_text("S08Team.h")

        def c(name):
            m = re.search(rf"\b{name} = (-?[\d.]+)f", h)
            self.assertIsNotNone(m, name)
            return float(m.group(1))
        p1, p2 = RING.RING_SPEC["p1"]["bands"], RING.RING_SPEC["p2"]["bands"]
        self.assertEqual((c("P1KeylineIn0"), c("P1Fill0"), c("P1Fill1"), c("P1KeylineOut1")),
                         (p1["keylineIn"][0], p1["fill"][0], p1["fill"][1], p1["keylineOut"][1]))
        self.assertEqual((c("P2KeylineIn0"), c("P2Fill0"), c("P2Fill1"), c("P2KeylineOut1")),
                         (p2["keylineIn"][0], p2["fill"][0], p2["fill"][1], p2["keylineOut"][1]))
        self.assertEqual(c("P2CornerGapUU"), RING.RING_SPEC["p2"]["cornerGapUU"])
        # 5c-B1 B1-3: the outer ring edge is the rim (rimOut[1]); FigureScreenRect uses it
        self.assertEqual((c("P1RimOut1"), c("P2RimOut1")), (p1["rimOut"][1], p2["rimOut"][1]))
        self.assertEqual((p1["keylineOut"][1], p2["keylineOut"][1]), (p1["rimOut"][0], p2["rimOut"][0]))
        self.assertIn("HeroRectRadiusUU = P1RimOut1", h)
        self.assertEqual((c("ZMin"), c("ZMax")), (RING.RING_SPEC["zMin"], RING.RING_SPEC["zMax"]))
        self.assertEqual(c("SidekickScale"), RING.RING_SPEC["sidekickScaleXY"])

    def test_hex_band_samples_stay_in_the_band(self):
        a0, a1 = RING.RING_SPEC["p2"]["bands"]["fill"]
        pts = T53.band_samples("P2", a0, a1, 1.0, (0.0, 0.0, 0.0), 1.2, step=0.5)
        self.assertGreater(len(pts), 500)
        for x, y, _z in pts:
            # apothem distance = max over the six side normals
            ap = max(x * math.cos(math.radians(60 * k + 30)) + y * math.sin(math.radians(60 * k + 30)) for k in range(6))
            self.assertGreaterEqual(ap, a0 - 1e-6)
            self.assertLessEqual(ap, a1 + 1e-6)
            self.assertLessEqual(abs(math.degrees(math.atan2(x, y))), 135.0 + 1e-6)


class LateShotParser(unittest.TestCase):
    """The late section is the only icon source of its block; captured attaches by file name."""

    def write(self, lines: list[str]) -> Path:
        d = Path(tempfile.mkdtemp())
        p = d / "client.trace.log"
        p.write_text("".join(f"{TS} {ln}\n" for ln in lines), encoding="utf-8")
        return p

    def base(self, name: str) -> list[str]:
        return ["SHOT ctx viewport=200x100 viewTarget=Cam cam=(0,959,1370) rot=(-55,-90,0)",
                "SHOT fighter f-0-hero pos=(1,1) world=(0,0,0) screen=(100,50) projected=1 alive=1",
                "SHOT icon fighter=f-1-hero bbox=(10,10,42,42) visible=1 geom=painted",
                "SHOT figure fighter=f-0-hero bbox=(80,20,120,60) ringR=28.00 art=1 blockout=0 team=P1 look=P1 ring=1",
                f"SHOT request file={name} frame=100",
                f"SHOT requested: FScreenshotRequest(bShowUI) -> C:\\tmp\\x\\{name}"]

    def test_late_hidden_icon_wins(self):
        name = "s09-combat-result.png"
        tr = parse_trace(self.write(self.base(name) + [
            f"SHOT late begin file={name} frame=101 requestFrame=100",
            "SHOT iconstate visible=0 frame=101",
            "SHOT widget id=board.tag impl=umg fighter=f-0-hero bbox=(1,2,30,20) geom=painted visible=1 frame=101 font=12",
            "SHOT panel id=hud.side bbox=(150,0,200,20) geom=painted visible=1 frame=101",
            f"SHOT late end file={name} frame=101",
            f"SHOT captured file={name} frame=101 px=200x100 sha256={'a' * 64} order=BGRA saved=1"]))
        blk = tr.find_shot(None, name)
        self.assertTrue(blk.late)
        self.assertEqual(blk.late_frame, 101)
        self.assertEqual(blk.request_frame, 100)
        self.assertIsNone(blk.icon)
        self.assertTrue(blk.icon_hidden_late)
        self.assertEqual(blk.captured["frame"], 101)
        self.assertEqual(blk.figures["f-0-hero"]["team"], "P1")
        self.assertEqual(blk.figures["f-0-hero"]["bbox"], (80.0, 20.0, 120.0, 60.0))
        self.assertEqual(blk.widgets[0]["id"], "board.tag")
        self.assertEqual(blk.widgets[0]["bbox"], (1.0, 2.0, 30.0, 20.0))
        self.assertEqual(blk.panels[0]["id"], "hud.side")

    def test_late_icon_line(self):
        name = "s09-combat-resolve-revealed.png"
        tr = parse_trace(self.write(self.base(name) + [
            f"SHOT late begin file={name} frame=100 requestFrame=100",
            "SHOT icon fighter=f-1-hero bbox=(50,20,82,52) visible=1 geom=painted anchor=right frame=100",
            f"SHOT late end file={name} frame=100"]))
        blk = tr.find_shot(None, name)
        self.assertIsNotNone(blk.icon)
        self.assertEqual(blk.icon.source, "shot-late")
        self.assertEqual(blk.icon.value["bbox"], (50.0, 20.0, 82.0, 52.0))
        self.assertEqual(blk.icon.value["anchor"], "right")

    def test_capture_section_supersedes_request_section(self):
        """The capture slipped to the next frame: the delegate's section (icon hidden) wins over the request's."""
        name = "s09-combat-result.png"
        tr = parse_trace(self.write(self.base(name) + [
            f"SHOT late begin file={name} frame=100 requestFrame=100",
            "SHOT icon fighter=f-1-hero bbox=(50,20,82,52) visible=1 geom=painted anchor=right frame=100",
            "SHOT panel id=hud.side bbox=(150,0,200,20) geom=painted visible=1 frame=100",
            f"SHOT late end file={name} frame=100",
            f"SHOT captured file={name} frame=101 px=200x100 sha256={'b' * 64} order=BGRA saved=1",
            f"SHOT late begin file={name} frame=101 requestFrame=100",
            "SHOT iconstate visible=0 lastFighter=none frame=101",
            "SHOT panel id=hud.side bbox=(150,0,200,30) geom=painted visible=1 frame=101",
            f"SHOT late end file={name} frame=101"]))
        blk = tr.find_shot(None, name)
        self.assertEqual(blk.late_frame, 101)
        self.assertIsNone(blk.icon)
        self.assertTrue(blk.icon_hidden_late)
        self.assertEqual(len(blk.panels), 1)
        self.assertEqual(blk.panels[0]["bbox"], (150.0, 0.0, 200.0, 30.0))


COBBLE_FIGS = {  # FigureScreenRects of the initial Cobble K1 (G3 traces, both clients)
    "f-0-hero": (915, 389, 1005, 512), "f-0-sk0": (1081, 410, 1154, 504), "f-0-sk1": (926, 288, 994, 381),
    "f-0-sk2": (766, 410, 839, 504), "f-1-hero": (914, 517, 1006, 643), "f-1-sk0": (1084, 520, 1162, 635)}


class TagBindingRevision1(unittest.TestCase):
    """t53-thresholds revision 1: tag centre nearer its owner's figure than any other; plate-owner mode rule."""

    def block(self, tags: dict, plate=None, plate_mode="hidden"):
        name = "phase2-board-joiner-1920x1080.png"
        lines = ["SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1107,1582) rot=(-55,-90,0)"]
        for fid, r in COBBLE_FIGS.items():
            lines.append(f"SHOT figure fighter={fid} bbox=({r[0]},{r[1]},{r[2]},{r[3]}) ringR=28.00 art=1 "
                         f"blockout={0 if fid == 'f-0-hero' else 1} team=P1 look=P1 ring=1")
        lines += [f"SHOT request file={name} frame=10", f"SHOT requested: FScreenshotRequest(bShowUI) -> C:\\x\\{name}",
                  f"SHOT late begin file={name} frame=10 requestFrame=10"]
        if plate:
            lines.append(f"SHOT widget id=plate impl=umg state=own fighter=f-0-hero bbox=({plate[0]},{plate[1]},{plate[2]},"
                         f"{plate[3]}) geom=painted visible=1 twin=0 source=/Game/S08/UI/ArtHud/WBP_S08ArtPlate frame=10")
        for fid, box in tags.items():
            if box is None:
                lines.append(f"SHOT widget id=board.tag impl=umg state={plate_mode} fighter={fid} bbox=(0,0,0,0) "
                             f"geom=unpainted visible=0 mode={plate_mode} frame=10")
            else:
                mode = "compact" if fid == "f-0-hero" else "full"
                lines.append(f"SHOT widget id=board.tag impl=umg state={mode} fighter={fid} bbox=({box[0]},{box[1]},"
                             f"{box[2]},{box[3]}) geom=painted visible=1 mode={mode} placement=above ring=0 frame=10")
        lines.append(f"SHOT late end file={name} frame=10")
        d = Path(tempfile.mkdtemp())
        p = d / "phase2-client-joiner.trace.log"
        p.write_text("".join(f"{TS} {ln}\n" for ln in lines), encoding="utf-8")
        return parse_trace(p).find_shot(None, name)

    def test_g3_medusa_tag_is_caught(self):
        """The verifier's case: G3 Medusa tag 98 px away next to Harpies 2, King Arthur's left tag nearer Harpies 3."""
        doc = T53.block_tag_binding(self.block({"f-0-hero": (813, 269, 915, 291), "f-0-sk1": (915, 245, 1006, 286),
                                                "f-1-hero": (807, 517, 912, 558), "f-1-sk0": (1164, 520, 1248, 561)}))
        by = {r["fighter"]: r for r in doc["tags"]}
        self.assertFalse(by["f-0-hero"]["bindingPass"])
        self.assertEqual(by["f-0-hero"]["nearestOther"], "f-0-sk1")
        self.assertEqual(by["f-0-hero"]["gapToOwner"], 98.0)
        self.assertFalse(by["f-1-hero"]["bindingPass"])
        self.assertTrue(by["f-0-sk1"]["bindingPass"])
        self.assertTrue(by["f-1-sk0"]["bindingPass"])

    def test_r3_inset_and_below_are_bound(self):
        doc = T53.block_tag_binding(self.block({"f-0-hero": (909, 389, 1011, 411), "f-1-hero": (908, 645, 1013, 686)}))
        self.assertTrue(all(r["bindingPass"] for r in doc["tags"]))
        self.assertEqual({r["fighter"]: r["gapToOwner"] for r in doc["tags"]}, {"f-0-hero": 0.0, "f-1-hero": 2.0})

    def test_plate_owner_mode(self):
        far = (1009, 638, 1181, 692)  # the Cobble host plate next to Merlin (K-2): not bound to Medusa
        doc = T53.block_tag_binding(self.block({"f-0-hero": None}, plate=far))
        r = doc["tags"][0]
        self.assertFalse(doc["plate"]["bound"])
        self.assertEqual(r["expectedPlateOwnerMode"], "compact")
        self.assertFalse(r["plateOwnerModePass"])
        doc = T53.block_tag_binding(self.block({"f-0-hero": (909, 389, 1011, 411)}, plate=far))
        self.assertTrue(doc["tags"][0]["plateOwnerModePass"])
        near = (1009, 420, 1060, 470)  # right next to Medusa (gap 4 vs 21): bound -> hidden
        doc = T53.block_tag_binding(self.block({"f-0-hero": None}, plate=near))
        self.assertTrue(doc["plate"]["bound"])
        self.assertTrue(doc["tags"][0]["plateOwnerModePass"])


    def test_unpainted_plate_uses_the_client_plate_line(self):
        """The plate appeared in the capture frame (visible=1, geom=unpainted): the mode rule follows the client's own
        PLATE line (bbox + bound=), not «no plate» (r3 Cobble s09-damage-combat host)."""
        name = "s09-damage-combat.png"
        lines = ["SHOT ctx viewport=1920x1080 viewTarget=Cam cam=(0,1107,1582) rot=(-55,-90,0)"]
        for fid, r in COBBLE_FIGS.items():
            lines.append(f"SHOT figure fighter={fid} bbox=({r[0]},{r[1]},{r[2]},{r[3]}) ringR=28.00 art=1 blockout=1")
        lines += [f"SHOT request file={name} frame=897", f"SHOT requested: FScreenshotRequest(bShowUI) -> C:\\x\\{name}",
                  "PLATE fighter=f-0-hero bbox=(1009,638,1181,692) overlapReachable=0 placement=below ring=15 gap=126 "
                  "selection=f-0-hero destinations=13 clean=0 softPx2=0 tested=18295 bound=0",
                  f"SHOT late begin file={name} frame=897 requestFrame=897",
                  "SHOT widget id=plate impl=umg state=own fighter=f-0-hero bbox=(0,0,0,0) geom=unpainted visible=1 frame=897",
                  "SHOT widget id=board.tag impl=umg state=compact fighter=f-0-hero bbox=(909,389,1011,411) geom=painted "
                  "visible=1 mode=compact placement=inset ring=0 bound=1 frame=897",
                  f"SHOT late end file={name} frame=897"]
        text = "".join(f"{TS} {ln}\n" for ln in lines)
        p = Path(tempfile.mkdtemp()) / "combat-client-host.trace.log"
        p.write_text(text, encoding="utf-8")
        doc = T53.block_tag_binding(parse_trace(p).find_shot(None, name), text)
        self.assertFalse(doc["plate"]["bound"])
        self.assertTrue(doc["plate"]["source"].startswith("PLATE line"))
        r = doc["tags"][0]
        self.assertEqual(r["expectedPlateOwnerMode"], "compact")
        self.assertTrue(r["plateOwnerModePass"])
        self.assertTrue(r["bindingPass"])


class ThresholdRevision(unittest.TestCase):
    def test_revision1_keeps_the_registered_base(self):
        """revisions[0] was appended to the 16:56 registration without touching it (base sha256)."""
        text = (EVID / "t53-thresholds.json").read_bytes().decode("utf-8")
        doc = json.loads(text)
        rev = T53.threshold_revision(doc, 1)
        self.assertIsNotNone(rev)
        base = text[:text.index('"revisions": [')] + '"revisions": []\n}\n'
        self.assertEqual(hashlib.sha256(base.encode("utf-8")).hexdigest(), rev["base"]["sha256"])
        self.assertIn("binding", rev["tags"])
        self.assertLess(rev["registeredLocal"], "2026-09-29T19:00:00+05:00")

    def test_cpp_tag_policy(self):
        """The C++ tag builder binds the tag, enables the inset and the near rings (the policy the revision names)."""
        src = cpp_text("S08ArtHud.cpp")
        body = src[src.index("FLabelPlacementInput MakeTagPlacementInput("):]
        body = body[:body.index("\n}\n") if "\n}\n" in body else body.index("\r\n}\r\n")]
        for needle in ("In.BindTarget = Owner", "In.BindOthers = Others", "In.bInset = true", "In.NearRings = 2"):
            self.assertIn(needle, body)
        flow = cpp_text("S08FlowGameMode.cpp")
        self.assertIn("S08ArtHud::MakeTagPlacementInput(", flow)
        self.assertIn("ArtHud.PlateResult.bBound ? ES08TagMode::Hidden : ES08TagMode::Compact", flow)


class ShotCapturedProvenance(unittest.TestCase):
    def make(self, sha: str | None = None, late_frame: int = 7) -> tuple[Path, list[str], dict]:
        d = Path(tempfile.mkdtemp())
        rgb = np.zeros((6, 8, 3), dtype=np.uint8)
        rgb[..., 0] = np.arange(8, dtype=np.uint8) * 30
        rgb[..., 1] = 99
        rgb[2:4, 2:5, 2] = 250
        png = d / "phase2-board-host-1920x1080.png"
        Image.fromarray(rgb).save(png)
        bgra = np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0], np.full((6, 8), 255, np.uint8)])
        true_sha = hashlib.sha256(bgra.tobytes()).hexdigest()
        lines = [f"{TS} SHOT request file={png.name} frame=6",
                 f"{TS} SHOT late begin file={png.name} frame={late_frame} requestFrame=6",
                 f"{TS} SHOT late end file={png.name} frame={late_frame}",
                 f"{TS} SHOT captured file={png.name} frame=7 px=8x6 sha256={sha or true_sha} order=BGRA saved=1"]
        return png, lines, {"width": 8, "height": 6}

    def test_bgra_sha_matches(self):
        png, lines, info = self.make()
        cap = CE.shot_captured(lines, png, info)
        self.assertTrue(cap["applies"])
        self.assertTrue(cap["ok"], cap["reasons"])

    def test_wrong_sha_rejected(self):
        png, lines, info = self.make(sha="0" * 64)
        cap = CE.shot_captured(lines, png, info)
        self.assertFalse(cap["ok"])
        self.assertTrue(any("sha256" in r for r in cap["reasons"]))

    def test_late_block_two_frames_off_rejected(self):
        png, lines, info = self.make(late_frame=9)
        self.assertFalse(CE.shot_captured(lines, png, info)["ok"])


class ShapeClassifier(unittest.TestCase):
    """Synthetic top-down frames (2 px / uu): the P1 annulus is a circle, the P2 gapped hexagon a hexagon."""

    PX_PER_UU = 2.0

    def shot_with_band(self, look: str, fs: float = 1.0, occluder: bool = False):
        w = h = 200
        # top-down camera: pitch -90, yaw 0 -> screen x = +Y world, screen y = -X world
        hfov = 60.0
        focal = (w * 0.5) / math.tan(math.radians(hfov) * 0.5)
        height = focal / self.PX_PER_UU
        cam = Camera(pos=(0.0, 0.0, height + 1.2), rot=(-90.0, 0.0, 0.0), hfov_deg=hfov, viewport=(w, h))
        mask = np.zeros((h, w), dtype=bool)
        a0, a1 = ring = RING.RING_SPEC["p1" if look == "P1" else "p2"]["bands"]["fill"]
        del ring
        quads = (RING.circle_band_quads(a0, a1, 96) if look == "P1"
                 else RING.hex_band_quads(a0, a1, RING.RING_SPEC["p2"]["cornerGapUU"]))
        # rasterise the world polygons: pixel centre -> world XY -> inside any quad
        ys, xs = np.mgrid[0:h, 0:w]
        wx = -(ys + 0.5 - h * 0.5) / self.PX_PER_UU
        wy = (xs + 0.5 - w * 0.5) / self.PX_PER_UU
        for q in quads:
            q = [(x * fs, y * fs) for x, y in q]
            inside = np.ones((h, w), dtype=bool)
            for i in range(4):
                (x0, y0), (x1, y1) = q[i], q[(i + 1) % 4]
                cross = (x1 - x0) * (wy - y0) - (y1 - y0) * (wx - x0)
                inside &= cross >= -1e-9 if self._ccw(q) else cross <= 1e-9
            mask |= inside
        if occluder:
            mask[:, 98:101] = False  # a thin vertical 'wing' across the ring
        fighter = SimpleNamespace(world=(0.0, 0.0, 0.0))
        shot = SimpleNamespace(proj=SimpleNamespace(camera=cam), w=w, h=h, fighters={"f": fighter})
        return shot, mask

    @staticmethod
    def _ccw(q) -> bool:
        a = sum(q[i][0] * q[(i + 1) % 4][1] - q[(i + 1) % 4][0] * q[i][1] for i in range(4))
        return a > 0

    def test_circle(self):
        shot, mask = self.shot_with_band("P1")
        res = T53.classify_shape(shot, "f", mask, 1.0, 1.2)
        self.assertEqual(res["shape"], "circle", res)
        self.assertEqual(res["breaks"], 0)

    def test_hexagon(self):
        shot, mask = self.shot_with_band("P2")
        res = T53.classify_shape(shot, "f", mask, 1.0, 1.2)
        self.assertEqual(res["shape"], "hexagon", res)
        self.assertGreaterEqual(res["breaks"], 2)
        self.assertGreaterEqual(res["kinks"], 2)

    def test_thin_occluder_breaks_a_circle(self):
        """Registered rule limitation (act W5b-R): a 1-3 sample occluder counts as a break -> 'unclassified'."""
        shot, mask = self.shot_with_band("P1", occluder=True)
        res = T53.classify_shape(shot, "f", mask, 1.0, 1.2)
        self.assertGreaterEqual(res["breaks"], 1)
        self.assertNotEqual(res["shape"], "circle")


if __name__ == "__main__":
    unittest.main()
