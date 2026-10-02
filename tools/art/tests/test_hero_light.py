"""ENV-MAPS P9 track B + P9b review: the hero light (docs/art-pipeline/ENV-HERO-LIGHT.md, S08HeroLight.h) - plain-Python
checks of the shipped "heroLight" profile blocks (a mirror of S08HeroLight::Parse / Place / StateMultiplier /
LayersForBoard), the P9b accent logic (review 2026-10-02 «сильно пересвечены»: the key from the moon side at 1-2 x the moon
lux, a low rim behind, reduced specular, contact shadows, the pedestal unlit, active x 1.08..1.2), the concept doc numbers,
and the C++ contract (channel 1 only, never a shadow map, no GI / translucency, the -NoHeroLight flag, the budget, the
automation tests). The rendered gates D1-D6 / H2 / H5 are measured on UE frames (tools/art/render/hero_light_metrics.py).

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

BLOCK_FIELDS = {"enabled", "note", "cameraAzimuthDeg", "aimHeight", "litPedestal", "key", "rim", "states"}
LAYER_FIELDS = {"lux", "colorSrgb", "innerConeDeg", "outerConeDeg", "heightMul", "azimuthDeg", "elevationDeg", "radiusMul",
                "specularScale", "contactShadowLength", "note"}
STATE_FIELDS = {"activeMul", "breathHz", "breathAmp", "defeatedMul", "note"}
LAYER_DEFAULTS = {"innerConeDeg": 22.0, "outerConeDeg": 34.0, "heightMul": 2.5, "azimuthDeg": 35.0, "elevationDeg": 60.0,
                  "radiusMul": 1.6, "specularScale": 1.0, "contactShadowLength": 0.0}


def load_profiles() -> dict:
    return json.loads(PROFILES.read_text(encoding="utf-8"))


def parse_block(block: dict) -> list[str]:
    """Mirror of S08HeroLight::Parse (the error list; empty = valid)."""
    err = []
    if set(block) - BLOCK_FIELDS:
        err.append(f"unknown {sorted(set(block) - BLOCK_FIELDS)}")
    if not isinstance(block.get("enabled"), bool):
        err.append("enabled")
    if "litPedestal" in block and not isinstance(block["litPedestal"], bool):
        err.append("litPedestal")
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
                1.05 <= v["radiusMul"] <= 4 and 0 <= v["specularScale"] <= 1 and 0 <= v["contactShadowLength"] <= 0.5):
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

    def test_p9b_accent_values(self):
        # review 2026-10-02 («сильно пересвечены»): the hero light is an ACCENT under the fixed night exposure, not a main
        # light - P9 had key 50 lux + rim 30 lux = ~23 x the moon key, coaxial with the camera, the pedestal lit, x 1.35
        for lid in LIGHT_IDS:
            lp = self.lights[lid]
            b = lp["heroLight"]
            key, rim, st = b["key"], b["rim"], b["states"]
            moon = lp["directional"]["intensity"]
            self.assertGreaterEqual(key["lux"], 1.0 * moon - 1e-6, lid)
            self.assertLessEqual(key["lux"], 2.0 * moon + 1e-6, lid)
            self.assertLessEqual(rim["lux"], 0.5 * key["lux"] + 1e-6, lid)
            self.assertTrue(60 <= key["azimuthDeg"] <= 90, lid)  # the moon side, 60-90 deg off the camera azimuth
            self.assertTrue(40 <= key["elevationDeg"] <= 50, lid)
            self.assertTrue(0.3 <= key["specularScale"] <= 0.5, lid)
            self.assertTrue(0.03 <= key["contactShadowLength"] <= 0.12, lid)
            self.assertTrue(12 <= rim["elevationDeg"] <= 22, lid)  # a low rim: a thin edge, not a wash over the tops
            self.assertTrue(135 <= abs(rim["azimuthDeg"]) <= 225, lid)  # behind the figure relative to the camera
            self.assertTrue(0.6 <= rim["specularScale"] <= 0.8, lid)
            self.assertLessEqual(rim["outerConeDeg"], key["outerConeDeg"], lid)  # a narrow rim cone
            self.assertIs(b.get("litPedestal", False), False, lid)  # no more cream pedestals
            # the key colour is a light tint chosen against the board's colour cast on the figures (gate D6): near-neutral
            # #FFF0E0, the cool moon white #D8E2FF on Marmoreal (its pink garden throws warm light on the figures)
            kc = [int(key["colorSrgb"][i:i + 2], 16) for i in (1, 3, 5)]
            self.assertEqual(max(kc), 255, lid)
            self.assertGreaterEqual(min(kc), 0xC8, lid)
            self.assertEqual(rim["colorSrgb"].upper(), "#A8C0FF", lid)
            self.assertTrue(1.08 <= st["activeMul"] <= 1.2, lid)
            self.assertLessEqual(st["breathAmp"], 0.05, lid)
            self.assertEqual(st["defeatedMul"], 0.0, lid)

    def test_environment_budget_untouched(self):
        for lid in LIGHT_IDS:
            lp = self.lights[lid]
            self.assertEqual(lp["directional"]["rotation"], [-55, 30, 0], lid)
            self.assertLessEqual(len(lp["points"]), 6, lid)
            self.assertFalse(any(p.get("castShadows") for p in lp["points"]), lid)

    def test_placement_moon_side_and_low_rim(self):
        for lid in LIGHT_IDS:
            b = self.lights[lid]["heroLight"]
            moon_yaw = self.lights[lid]["directional"]["rotation"][1] + 180.0  # the moon key (-55, 30, 0) comes from 210
            cam_yaw = b.get("cameraAzimuthDeg", 90)
            for h in (40.0, 55.0, 120.0):
                k, r = place(b, "key", h), place(b, "rim", h)
                # the camera sits at +Y (yaw -90 looks along -Y): the key stands on the moon (-X) side, nearer the moon's
                # azimuth than the camera's (form shading agrees with the board's moon shadows); the rim behind (-Y), low
                yaw = math.degrees(math.atan2(k["loc"][1], k["loc"][0]))

                def delta(a, c):
                    return abs((a - c + 180.0) % 360.0 - 180.0)
                self.assertLess(k["loc"][0], 0.0, (lid, h))
                self.assertLessEqual(delta(yaw, moon_yaw), delta(yaw, cam_yaw) + 1e-6, (lid, h, yaw))
                self.assertLess(r["loc"][1], 0.0, (lid, h))
                rim_elev = math.degrees(math.atan2(r["loc"][2] - r["aim"][2], math.hypot(r["loc"][0], r["loc"][1])))
                self.assertLessEqual(rim_elev, 22.0 + 1e-6, (lid, h))
                self.assertAlmostEqual(k["loc"][2], b["key"]["heightMul"] * h, places=6)
                self.assertGreater(k["radius"], k["distance"])
                self.assertGreater(r["radius"], r["distance"])
                # the same illuminance at the aim point for every figure size
                self.assertAlmostEqual(k["cd"] / (k["distance"] / 100.0) ** 2, b["key"]["lux"], places=6)
            # a 55 uu figure: P9b - the key is a few tens of candelas at ~1.5 m (P9: 77 cd), the attenuation radius stays
            # a small figure-sized pool (channel 1: figures only), the low rim stands within one figure height or so
            k55, r55 = place(b, "key", 55.0), place(b, "rim", 55.0)
            self.assertLess(k55["cd"], 40.0, lid)
            self.assertLess(k55["radius"], 360.0, lid)
            self.assertLess(r55["distance"], 110.0, lid)  # the rim stays nearer than a neighbouring figure

    def test_states_and_budget(self):
        b = self.lights["sarpedon-night"]["heroLight"]
        am, amp, hz = b["states"]["activeMul"], b["states"]["breathAmp"], b["states"]["breathHz"]
        self.assertEqual(multiplier(b, "active", 1.7, True), am)
        values = [multiplier(b, "active", i * 0.01, False) for i in range(int(100 / max(hz, 0.01)) + 1)]
        self.assertAlmostEqual(min(values), am * (1 - amp), places=3)
        self.assertAlmostEqual(max(values), am * (1 + amp), places=3)
        self.assertGreater(min(values), 1.05)  # the active figure stays above the idle ones at the pulse low
        self.assertLessEqual(max(values), 1.25)  # and is no flare at the high
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
                 ("key.heightMul", 0.6, None), ("states.activeMul", 0.5, None), ("rim.elevationDeg", 90, None),
                 ("key.specularScale", 1.5, None), ("rim.specularScale", -0.1, None), ("key.contactShadowLength", 0.6, None)]
        for path, value, rename in cases:
            b = json.loads(json.dumps(good))
            if rename:
                b[path] = b.pop(rename)
            else:
                outer, inner = path.split(".")
                b[outer][inner] = value
            self.assertNotEqual(parse_block(b), [], path)
        b = json.loads(json.dumps(good))
        b["litPedestal"] = "no"
        self.assertNotEqual(parse_block(b), [], "litPedestal")
        # the P9b fields are optional: their absence = specular 1, no contact shadow, the pedestal unlit
        b = json.loads(json.dumps(good))
        for layer in ("key", "rim"):
            b[layer].pop("specularScale", None)
            b[layer].pop("contactShadowLength", None)
        b.pop("litPedestal", None)
        self.assertEqual(parse_block(b), [])


class DocAndCode(unittest.TestCase):
    def test_doc_numbers_match_the_profile(self):
        doc = DOC.read_text(encoding="utf-8")
        for needle in ("#FFE4C4", "#A8C0FF", "0,4 Гц", "-NoHeroLight", "канал 1", "14 на доску", "Ревизия после ревью",
                       "specularScale", "contactShadowLength", "litPedestal", "D1", "D2", "D3", "D4", "D5", "D6",
                       "hero_light_metrics.py"):
            self.assertIn(needle, doc, needle)
        # the revised doc quotes the shipped Sarpedon numbers (key / rim lux, active multiplier)
        b = self.lights_for_doc()["sarpedon-night"]["heroLight"]
        for value in (b["key"]["lux"], b["rim"]["lux"], b["states"]["activeMul"]):
            self.assertIn(f"{value:g}".replace(".", ","), doc, value)

    @staticmethod
    def lights_for_doc():
        return load_profiles()["lightProfiles"]

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
                       "SetLightingChannels(true, bLit, false)",
                       # P9b: less specular, contact shadows only (never a shadow map), the pedestal only on request
                       "SetSpecularScale(Layer.SpecularScale)", "ContactShadowLength = Layer.ContactShadowLength",
                       "ShadowResolutionScale = 0.0f", "SetCastShadows(bContact)",
                       "ArtBase->SetLightingChannels(true, bPedestalLit, false)"):
            self.assertIn(needle, src, needle)
        # the figure meshes only (never the rings / labels / readability parts)
        m = re.search(r"void AS08FighterActor::SetHeroLitChannels\(bool bLit, bool bPedestal\) \{(.*?)\n\}", src, re.S)
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
        # the pulse is frozen in -Bench: UpdateHeroLights reads GetFxOptions(), the command line unless live tune overrides it
        self.assertIn("const bool bFrozen = GetFxOptions().bFreeze;", board)
        self.assertRegex(board, r"FS08EnvFxOptions AS08BoardActor::GetFxOptions\(\) const \{\s*return FxOptionsOverride\.IsSet\(\) \? "
                                r"FxOptionsOverride\.GetValue\(\) : FS08EnvFxOptions::FromCommandLine\(\);")
        art = (S08 / "S08BoardArt.cpp").read_text(encoding="utf-8")
        self.assertIn("S08HeroLight::Parse(", art)
        tests = (S08 / "S08HeroLightTests.cpp").read_text(encoding="utf-8")
        for name in ("Unmatched.S08.HeroLight.Parse", "Unmatched.S08.HeroLight.Shipped", "Unmatched.S08.HeroLight.Math",
                     "Unmatched.S08.HeroLight.Actor"):
            self.assertIn(name, tests)


if __name__ == "__main__":
    unittest.main()
