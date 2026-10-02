"""ENV-MAPS P9 track B: the hero light (docs/art-pipeline/ENV-HERO-LIGHT.md, S08HeroLight.h) - plain-Python checks of the
shipped "heroLight" profile blocks (a mirror of S08HeroLight::Parse / Place / StateMultiplier / LayersForBoard), the concept
doc numbers, and the C++ contract (channel 1 only, no shadow / GI / translucency, the -NoHeroLight flag, the budget, the
automation tests). The rendered gates H1-H6 are measured in Integrate (UE frames), not here.

  python -B -m pytest -q tools/art/tests/test_hero_light.py
"""
from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PROFILES = REPO / "unreal/Unmatched/Config/ArtBoards/S08ArtBoardProfiles.json"
S08 = REPO / "unreal/Unmatched/Source/Unmatched/S08"
DOC = REPO / "docs/art-pipeline/ENV-HERO-LIGHT.md"
LIGHT_IDS = ("cobble-probe", "forest-probe", "paddock-probe", "marmoreal-night", "sarpedon-night")
MAX_PER_FIGURE, MAX_PER_BOARD = 2, 14

BLOCK_FIELDS = {"enabled", "note", "cameraAzimuthDeg", "aimHeight", "key", "rim", "states"}
LAYER_FIELDS = {"lux", "colorSrgb", "innerConeDeg", "outerConeDeg", "heightMul", "azimuthDeg", "elevationDeg", "radiusMul", "note"}
STATE_FIELDS = {"activeMul", "breathHz", "breathAmp", "defeatedMul", "note"}
LAYER_DEFAULTS = {"innerConeDeg": 22.0, "outerConeDeg": 34.0, "heightMul": 2.5, "azimuthDeg": 35.0, "elevationDeg": 60.0,
                  "radiusMul": 1.6}


def load_profiles() -> dict:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def parse_block(block: dict) -> list[str]:
    """Mirror of S08HeroLight::Parse (the error list; empty = valid)."""
    err = []
    if set(block) - BLOCK_FIELDS:
        err.append(f"unknown {sorted(set(block) - BLOCK_FIELDS)}")
    if not isinstance(block.get("enabled"), bool):
        err.append("enabled")
    if not -360 <= block.get("cameraAzimuthDeg", 90) <= 360 or not 0 <= block.get("aimHeight", 0.55) <= 1.5:
        err.append("camera / aim")
    aim = block.get("aimHeight", 0.55)
    for name in ("key", "rim"):
        layer = block.get(name)
        if layer is None:
            if name == "key":
                err.append("no key")
            continue
        if set(layer) - LAYER_FIELDS:
            err.append(f"{name}: unknown {sorted(set(layer) - LAYER_FIELDS)}")
        v = {**LAYER_DEFAULTS, **layer}
        if not (0 < v.get("lux", 0) <= 50 and re.fullmatch(r"#[0-9A-Fa-f]{6}", str(v.get("colorSrgb", ""))) and
                0 <= v["innerConeDeg"] <= 80 and 1 <= v["outerConeDeg"] <= 80 and v["innerConeDeg"] <= v["outerConeDeg"] and
                0.3 <= v["heightMul"] <= 6 and -360 <= v["azimuthDeg"] <= 360 and 5 <= v["elevationDeg"] <= 89 and
                1.05 <= v["radiusMul"] <= 4):
            err.append(f"{name}: ranges")
        if v["heightMul"] < aim + 0.2:
            err.append(f"{name}: below the aim point")
    st = block.get("states") or {}
    if set(st) - STATE_FIELDS or not (1 <= st.get("activeMul", 1.35) <= 3 and 0 <= st.get("breathHz", 0.4) <= 3 and
                                       0 <= st.get("breathAmp", 0.08) <= 0.5 and 0 <= st.get("defeatedMul", 0) <= 1):
        err.append("states")
    return err


def place(block: dict, layer_name: str, height: float) -> dict:
    """Mirror of S08HeroLight::Place (fighter space: the cell centre on the play plane)."""
    layer = {**LAYER_DEFAULTS, **block[layer_name]}
    aim_z = block.get("aimHeight", 0.55) * height
    dz = max(1.0, (layer["heightMul"] - block.get("aimHeight", 0.55)) * height)
    horiz = dz / math.tan(math.radians(layer["elevationDeg"]))
    yaw = math.radians(block.get("cameraAzimuthDeg", 90) + layer["azimuthDeg"])
    loc = (math.cos(yaw) * horiz, math.sin(yaw) * horiz, aim_z + dz)
    d = math.hypot(horiz, dz)
    return {"loc": loc, "aim": (0.0, 0.0, aim_z), "distance": d, "cd": layer["lux"] * (d / 100.0) ** 2,
            "radius": d * layer["radiusMul"]}


def multiplier(block: dict, state: str, t: float, frozen: bool, phase: float = 0.0) -> float:
    st = block.get("states") or {}
    am, hz, amp = st.get("activeMul", 1.35), st.get("breathHz", 0.4), st.get("breathAmp", 0.08)
    if state == "idle":
        return 1.0
    if state == "defeated":
        return st.get("defeatedMul", 0.0)
    if state == "active":
        return am if frozen or hz <= 0 or amp <= 0 else am * (1 + amp * math.sin(2 * math.pi * hz * t + phase))
    return 0.0


def layers_for_board(block: dict, figures: int) -> int:
    layers = min(1 + (1 if block.get("rim") else 0), MAX_PER_FIGURE)
    if figures <= 0 or figures * layers <= MAX_PER_BOARD:
        return layers
    return 1


class ShippedBlocks(unittest.TestCase):
    def setUp(self):
        self.prof = load_profiles()
        self.lights = self.prof["lightProfiles"]

    def test_every_light_profile_lights_the_figures(self):
        # «Все сцены»: Marmoreal, Sarpedon, Cobble and the probe boards
        self.assertEqual(set(self.lights), set(LIGHT_IDS))
        for lid in LIGHT_IDS:
            block = self.lights[lid].get("heroLight")
            self.assertIsNotNone(block, lid)
            self.assertEqual(parse_block(block), [], lid)
            self.assertTrue(block["enabled"], lid)
            self.assertIn("key", block)
            self.assertIn("rim", block)
        for board in self.prof["boards"]:
            self.assertIn("heroLight", self.lights[board["light"]], board["id"])

    def test_concept_values(self):
        for lid in LIGHT_IDS:
            b = self.lights[lid]["heroLight"]
            key, rim, st = b["key"], b["rim"], b["states"]
            self.assertEqual((key["innerConeDeg"], key["outerConeDeg"]), (22, 34), lid)
            self.assertEqual(key["colorSrgb"].upper(), "#FFE4C4", lid)
            self.assertEqual(rim["colorSrgb"].upper(), "#A8C0FF", lid)
            self.assertAlmostEqual(rim["lux"] / key["lux"], 0.6, places=3, msg=lid)
            self.assertEqual((key["heightMul"], key["azimuthDeg"], key["elevationDeg"]), (2.5, 35, 60), lid)
            self.assertEqual((st["activeMul"], st["breathHz"], st["breathAmp"], st["defeatedMul"]), (1.35, 0.4, 0.08, 0.0), lid)

    def test_environment_budget_untouched(self):
        for lid in LIGHT_IDS:
            lp = self.lights[lid]
            self.assertEqual(lp["directional"]["rotation"], [-55, 30, 0], lid)
            self.assertLessEqual(len(lp["points"]), 6, lid)
            self.assertFalse(any(p.get("castShadows") for p in lp["points"]), lid)

    def test_placement_camera_side_towards_the_moon(self):
        for lid in LIGHT_IDS:
            b = self.lights[lid]["heroLight"]
            for h in (40.0, 55.0, 120.0):
                k, r = place(b, "key", h), place(b, "rim", h)
                # the camera sits at +Y (yaw -90 looks along -Y); the moon key (-55, 30, 0) comes from -X -Y
                self.assertGreater(k["loc"][1], 0.0, (lid, h))
                self.assertLess(k["loc"][0], 0.0, (lid, h))
                self.assertLess(r["loc"][1], 0.0, (lid, h))
                self.assertAlmostEqual(k["loc"][2], 2.5 * h, places=6)
                self.assertGreater(k["radius"], k["distance"])
                self.assertGreater(r["radius"], r["distance"])
                # the same illuminance at the aim point for every figure size
                self.assertAlmostEqual(k["cd"] / (k["distance"] / 100.0) ** 2, b["key"]["lux"], places=6)
            # a 55 uu figure: P9 tune (H1 measured: the start values 4 / 6 lux lit the figures +7 %) - the key is tens of
            # candelas at ~1.2 m, the attenuation radius stays a small figure-sized pool (channel 1: figures only)
            k55 = place(b, "key", 55.0)
            self.assertLess(k55["cd"], 100.0, lid)
            self.assertLess(k55["radius"], 360.0, lid)

    def test_states_and_budget(self):
        b = self.lights["sarpedon-night"]["heroLight"]
        self.assertEqual(multiplier(b, "active", 1.7, True), 1.35)
        values = [multiplier(b, "active", i * 0.025, False) for i in range(101)]
        self.assertAlmostEqual(min(values), 1.35 * 0.92, places=3)
        self.assertAlmostEqual(max(values), 1.35 * 1.08, places=3)
        self.assertGreaterEqual(min(values), 1.2)  # H4 even at the pulse low
        self.assertEqual(multiplier(b, "defeated", 0.0, False), 0.0)
        self.assertEqual(multiplier(b, "idle", 0.0, False), 1.0)
        self.assertEqual(layers_for_board(b, 7), 2)
        self.assertEqual(layers_for_board(b, 8), 1)
        for figures in range(1, 20):
            per = layers_for_board(b, figures)
            lit = min(figures, MAX_PER_BOARD // per)
            self.assertLessEqual(lit * per, MAX_PER_BOARD)
            self.assertLessEqual(per, MAX_PER_FIGURE)

    def test_parser_mirror_rejects_broken_blocks(self):
        good = self.lights["sarpedon-night"]["heroLight"]
        cases = [("notes", None, "note"), ("key.lux", 0, None), ("key.innerConeDeg", 40, None),
                 ("key.heightMul", 0.6, None), ("states.activeMul", 0.5, None), ("rim.elevationDeg", 90, None)]
        for path, value, rename in cases:
            b = json.loads(json.dumps(good))
            if rename:
                b[path] = b.pop(rename)
            else:
                outer, inner = path.split(".")
                b[outer][inner] = value
            self.assertNotEqual(parse_block(b), [], path)


class DocAndCode(unittest.TestCase):
    def test_doc_numbers_match_the_profile(self):
        doc = DOC.read_text(encoding="utf-8")
        for needle in ("22°/34°", "#FFE4C4", "#A8C0FF", "1,35", "0,4 Гц", "8 %", "-NoHeroLight", "канал 1", "14 на доску"):
            self.assertIn(needle, doc, needle)

    def test_header_constants(self):
        h = (S08 / "S08HeroLight.h").read_text(encoding="utf-8")
        self.assertRegex(h, r'OptOutFlagName = TEXT\("NoHeroLight"\)')
        self.assertRegex(h, r"constexpr int32 Channel = 1;")
        self.assertRegex(h, r"constexpr int32 MaxLightsPerFigure = 2;")
        self.assertRegex(h, r"constexpr int32 MaxLightsPerBoard = 14;")

    def test_fighter_light_settings(self):
        src = (S08 / "S08FighterActor.cpp").read_text(encoding="utf-8")
        for needle in ("SetLightingChannels(false, true, false)", "SetIndirectLightingIntensity(0.0f)",
                       "SetVolumetricScatteringIntensity(0.0f)", "SetAffectTranslucentLighting(false)",
                       "SetCastShadows(false)", "SetIntensityUnits(ELightUnits::Candelas)",
                       "SetMobility(EComponentMobility::Movable)", "SetupAttachment(RootComponent)",
                       "SetLightingChannels(true, bLit, false)"):
            self.assertIn(needle, src, needle)
        # the figure meshes only (never the rings / labels / readability parts)
        m = re.search(r"void AS08FighterActor::SetHeroLitChannels\(bool bLit\) \{(.*?)\n\}", src, re.S)
        self.assertIsNotNone(m)
        body = m.group(1)
        for part in ("ArtBody", "ArtBase", "ArtPlaceholder", "Body"):
            self.assertIn(part, body)
        for part in ("TeamRing", "Ring.Get", "Label", "TargetRing", "Base.Get()"):
            self.assertNotIn(part, body.replace("ArtBase.Get()", "").replace("ArtBody", ""), part)

    def test_board_wiring_and_tests(self):
        board = (S08 / "S08BoardActor.cpp").read_text(encoding="utf-8")
        sync = board[board.index("void AS08BoardActor::SyncFighters"):board.index("void AS08BoardActor::NotifyFighterAnimEvent")]
        self.assertIn("UpdateHeroLights();", sync)
        self.assertIn("FS08EnvFxOptions::FromCommandLine().bFreeze", board)  # the pulse is frozen in -Bench
        art = (S08 / "S08BoardArt.cpp").read_text(encoding="utf-8")
        self.assertIn("S08HeroLight::Parse(", art)
        tests = (S08 / "S08HeroLightTests.cpp").read_text(encoding="utf-8")
        for name in ("Unmatched.S08.HeroLight.Parse", "Unmatched.S08.HeroLight.Shipped", "Unmatched.S08.HeroLight.Math",
                     "Unmatched.S08.HeroLight.Actor"):
            self.assertIn(name, tests)


if __name__ == "__main__":
    unittest.main()
