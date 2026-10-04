"""Tests for tools/art/material_library/ue_v2_master.py: M_UM_Figure_v2.1 graph (static switch UseTeamAccent, LDV-12/13),
the v2.2 hit tint (DE-010), the v2.3 dissolve (DE-011) and the test MIs of the dye check (no editor needed).

  python -m unittest discover -s tools/art/material_library/tests -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import build_ue_inputs as bu  # noqa: E402
import ue_v2_master as vm  # noqa: E402

HAVE_SPEC = vm.UM_SPEC.is_file()


def effective_gain(use_accent: bool, gain: float, ceiling: float, team) -> float:
    """Mirror of the gain in um_v2_core.hlsl (LDV-13)."""
    if use_accent and ceiling > 0.0:
        return min(gain, ceiling / max(max(team[:3]), 1e-3))
    return gain


@unittest.skipUnless(HAVE_SPEC, "um-masters.json missing")
class Graph(unittest.TestCase):
    def setUp(self):
        self.g = vm.figure_v2_graph(vm.load_spec())

    def links_to(self, dst, inp):
        return [l for l in self.g.links if l[2] == dst and l[3] == inp]

    def test_switch_defaults_on(self):
        for nid in ("sw_dye", "sw_dyef"):
            n = self.g.nodes[nid]
            self.assertEqual(n["class"], "MaterialExpressionStaticSwitchParameter")
            self.assertEqual(n["props"]["parameter_name"], "UseTeamAccent")
            self.assertIs(n["props"]["default_value"], True)

    def test_dye_mask_routing(self):
        self.assertEqual(self.links_to("sw_dye", "True"), [["t_accent", "R", "sw_dye", "True"]])
        self.assertEqual(self.links_to("sw_dye", "False"), [["t_mask", "R", "sw_dye", "False"]])
        self.assertEqual(self.links_to("sw_dyef", "True"), [["one", "", "sw_dyef", "True"]])
        self.assertEqual(self.links_to("sw_dyef", "False"), [["zero", "", "sw_dyef", "False"]])
        self.assertEqual(self.links_to("core", "DyeMask"), [["sw_dye", "", "core", "DyeMask"]])
        self.assertEqual(self.links_to("core", "UseAccent"), [["sw_dyef", "", "core", "UseAccent"]])
        self.assertEqual(self.links_to("core", "TeamDyeCeiling"), [["p_TeamDyeCeiling", "", "core", "TeamDyeCeiling"]])

    def test_accent_texture_default_black(self):
        n = self.g.nodes["t_accent"]
        self.assertEqual(n["props"]["parameter_name"], "TeamAccentTexture")
        self.assertTrue(n["props"]["texture"].endswith("/T_UM_Mask_Black"))
        self.assertEqual(n["props"]["sampler_type"], "SAMPLERTYPE_LINEAR_GRAYSCALE")

    def test_ceiling_default_off(self):
        n = self.g.nodes["p_TeamDyeCeiling"]
        self.assertEqual(n["props"]["default_value"], 0.0)
        self.assertEqual(n["props"]["group"], "Team")

    def test_every_core_input_wired_once(self):
        for inp in vm.CORE_INPUTS:
            self.assertEqual(len(self.links_to("core", inp)), 1, inp)

    def test_hlsl_uses_the_inputs(self):
        code = vm.CORE_HLSL.read_text(encoding="utf-8")
        body = "\n".join(line for line in code.splitlines() if not line.lstrip().startswith("//"))
        for inp in vm.CORE_INPUTS:
            self.assertRegex(body, r"\b%s\b" % re.escape(inp), inp)
        self.assertNotRegex(body, r"\bTeamMask\b")          # renamed to DyeMask (the switch output)
        self.assertIn("dyeW = UseAccent > 0.5 ? DyeMask : DyeMask * L7.a;", body)
        self.assertIn("dyeW = DyeMask;", body)               # class 0: the mask alone in both modes



@unittest.skipUnless(HAVE_SPEC, "um-masters.json missing")
class HitTint(unittest.TestCase):
    """v2.2 (DE-010, 01 F-03): CPD 12 hit tint after the fade; 0 is exactly the v2.1 output."""

    def setUp(self):
        self.g = vm.figure_v2_graph(vm.load_spec())

    def links_to(self, dst, inp):
        return [l for l in self.g.links if l[2] == dst and l[3] == inp]

    def test_slot_is_free_and_neutral(self):
        v1 = vm.load_spec()["custom_primitive_data"]
        used = set()
        for k, v in v1.items():
            if isinstance(v, dict):
                used |= set(range(v["index"], v["index"] + v["size"]))
        self.assertNotIn(vm.V2_CPD["HitTint"]["index"], used)
        n = self.g.nodes["cpd_hit"]
        self.assertEqual(n["props"]["parameter_name"], "CPD_HitTint")
        self.assertTrue(n["props"]["use_custom_primitive_data"])
        self.assertEqual(n["props"]["primitive_data_index"], 12)
        self.assertEqual(n["props"]["default_value"], 0.0)

    def test_routing_after_the_fade(self):
        self.assertEqual(self.links_to("base_hit", "A"), [["base_final", "", "base_hit", "A"]])
        self.assertEqual(self.links_to("base_hit", "B"), [["p_hitcol", "RGB", "base_hit", "B"]])
        self.assertEqual(self.links_to("base_hit", "Alpha"), [["hit_a", "", "base_hit", "Alpha"]])
        # v2.3: the pins read base_hit / em_hit through the dissolve switch (off by default; class Dissolve)
        self.assertEqual(self.links_to("sw_dis_base", "False"), [["base_hit", "", "sw_dis_base", "False"]])
        self.assertEqual(self.links_to("sw_dis_em", "False"), [["em_hit", "", "sw_dis_em", "False"]])
        self.assertEqual(self.links_to("em_hit", "A"), [["em_total", "", "em_hit", "A"]])
        # every term of the hit tint is a product with CPD_HitTint: 0 adds nothing
        self.assertEqual(sorted(l[0] for l in self.links_to("hit_a", "A") + self.links_to("hit_k", "A")),
                         ["cpd_hit", "cpd_hit"])
        self.assertEqual(self.links_to("hit_c", "B"), [["hit_k", "", "hit_c", "B"]])
        self.assertEqual(self.links_to("hit_eai", "LightValueInput"), [["hit_c", "", "hit_eai", "LightValueInput"]])

    def test_knobs(self):
        p = {n["props"]["parameter_name"]: n["props"] for n in self.g.nodes.values()
             if n["class"].endswith("Parameter") and "parameter_name" in n["props"]}
        self.assertEqual(p["HitTintStrength"]["group"], "Cue")
        self.assertGreater(p["HitTintStrength"]["default_value"], 0.0)
        self.assertLessEqual(p["HitTintStrength"]["default_value"], 1.0)
        col = p["HitTintColor"]["default_value"]
        self.assertGreater(col["r"], 5 * max(col["g"], col["b"]), "red fill")

    def test_v21_graph_is_a_subgraph(self):
        """Nothing of v2.1 changed except the two attribute pins that now read the hit tint (through the v2.3 dissolve
        switch, whose False input is base_hit / em_hit: class Dissolve)."""
        new = {k for k in self.g.nodes if k.startswith(("hit_", "p_hit", "cpd_hit", "base_hit", "em_hit"))}
        self.assertEqual(new, {"cpd_hit", "p_hitcol", "p_hitstr", "p_hitemi", "hit_a", "base_hit", "hit_k", "hit_c",
                               "hit_alpha", "hit_eai", "em_hit"})
        self.assertEqual(len(self.g.nodes), 71 + len(new) + len(DISSOLVE_NODES))


# v2.3 (DE-011) nodes: CPD 13 / 14, the knobs, the Custom node, ash albedo, glow, three switches
DISSOLVE_NODES = {"cpd_dis", "cpd_dstyle", "dis", "dis_ash", "base_dis", "dis_k", "dis_c", "dis_alpha", "dis_eai",
                  "em_dis", "sw_dis_base", "sw_dis_em", "sw_dis_mask"} | {"p_" + k[0] for k in vm.DISSOLVE_KNOBS}


@unittest.skipUnless(HAVE_SPEC, "um-masters.json missing")
class Dissolve(unittest.TestCase):
    """v2.3 (DE-011, 01 F-09): the dissolve behind the static switch UseDissolve; off = exactly the v2.2 output."""

    def setUp(self):
        self.g = vm.figure_v2_graph(vm.load_spec())

    def links_to(self, dst, inp):
        return [l for l in self.g.links if l[2] == dst and l[3] == inp]

    def test_slots_are_free_and_neutral(self):
        v1 = vm.load_spec()["custom_primitive_data"]
        used = set()
        for v in v1.values():
            if isinstance(v, dict):
                used |= set(range(v["index"], v["index"] + v["size"]))
        used.add(vm.V2_CPD["HitTint"]["index"])
        for key, nid, index in (("Dissolve", "cpd_dis", 13), ("DissolveStyle", "cpd_dstyle", 14)):
            self.assertEqual(vm.V2_CPD[key]["index"], index)
            self.assertNotIn(index, used)
            n = self.g.nodes[nid]["props"]
            self.assertTrue(n["use_custom_primitive_data"])
            self.assertEqual(n["primitive_data_index"], index)
            self.assertEqual(n["default_value"], 0.0)

    def test_switch_off_is_the_v22_output(self):
        """The attribute pins read the switches; their False inputs are the v2.2 pins (base_hit, em_hit, 1)."""
        self.assertEqual(self.links_to("mma", "BaseColor"), [["sw_dis_base", "", "mma", "BaseColor"]])
        self.assertEqual(self.links_to("mma", "EmissiveColor"), [["sw_dis_em", "", "mma", "EmissiveColor"]])
        self.assertEqual(self.links_to("mma", "OpacityMask"), [["sw_dis_mask", "", "mma", "OpacityMask"]])
        self.assertEqual(self.links_to("sw_dis_base", "False"), [["base_hit", "", "sw_dis_base", "False"]])
        self.assertEqual(self.links_to("sw_dis_em", "False"), [["em_hit", "", "sw_dis_em", "False"]])
        self.assertEqual(self.links_to("sw_dis_mask", "False"), [["one", "", "sw_dis_mask", "False"]])
        for nid in ("sw_dis_base", "sw_dis_em", "sw_dis_mask"):
            props = self.g.nodes[nid]["props"]
            self.assertEqual(props["parameter_name"], vm.DISSOLVE_SWITCH)
            self.assertIs(props["default_value"], False)
        # the master stays Opaque: only the dissolve MICs override the blend mode
        self.assertEqual(vm.SETTINGS["blend_mode"], "BLEND_OPAQUE")

    def test_switch_on_routing(self):
        self.assertEqual(self.links_to("sw_dis_mask", "True"), [["dis", "", "sw_dis_mask", "True"]])
        self.assertEqual(self.links_to("base_dis", "A"), [["base_hit", "", "base_dis", "A"]])
        self.assertEqual(self.links_to("base_dis", "Alpha"), [["dis", "Edge", "base_dis", "Alpha"]])
        self.assertEqual(self.links_to("em_dis", "A"), [["em_hit", "", "em_dis", "A"]])
        wired = {l[3]: l[0] for l in self.g.links if l[2] == "dis"}
        self.assertEqual(sorted(wired), sorted(vm.DISSOLVE_INPUTS))
        self.assertEqual(wired["Progress"], "cpd_dis")
        self.assertEqual(wired["Style"], "cpd_dstyle")
        self.assertEqual(wired["Team"], "team")
        self.assertEqual(wired["P"], "vi_p")

    def test_hlsl_contract(self):
        code = vm.DISSOLVE_HLSL.read_text(encoding="utf-8")
        for name in vm.DISSOLVE_INPUTS + [o[0] for o in vm.DISSOLVE_OUTPUTS]:
            self.assertRegex(code, r"\b%s\b" % name)
        self.assertEqual(self.g.nodes["dis"]["props"]["code"], code)
        self.assertIn("return keepFade;", code)

    def test_mask_ends_mirror_the_hlsl(self):
        """Progress 0 keeps every pixel (no edge), progress 1 clips every pixel - both styles (python mirror)."""
        w = dict((k[0], k[1]) for k in vm.DISSOLVE_KNOBS)["DissolveEdgeWidth"]
        for field in np.linspace(0.0, 1.0, 101):
            for p, keep in ((0.0, True), (1.0, False)):
                t = p * (1.0 + w + 0.01) - w
                self.assertEqual(field > t, keep)
                ign = field * 0.999          # fade dither in [0, 1)
                self.assertEqual((1.0 - p) > ign, keep)

@unittest.skipUnless(HAVE_SPEC, "um-masters.json missing")
class TestInstances(unittest.TestCase):
    def setUp(self):
        self.mis = {m["asset"].rsplit("/", 1)[1]: m for m in vm.test_instances()}

    def test_legacy_mis_pin_the_v20_path(self):
        for i in range(16):
            self.assertEqual(self.mis["MI_UM_v2_Test_Class%02d_Red" % i]["switches"], {"UseTeamAccent": False})
        self.assertEqual(self.mis["MI_UM_v2_Test_LegacyMerlin_Red"]["switches"], {"UseTeamAccent": False})

    def test_accent_mis(self):
        for i in range(16):
            m = self.mis["MI_UM_v2_Test_Class%02d_Accent" % i]
            self.assertEqual(m["switches"], {"UseTeamAccent": True})
            self.assertTrue(m["textures"]["TeamAccentTexture"].endswith("/T_UM_Test_AccentHalf"))
            self.assertEqual(m["scalars"]["DebugMatIDOverride"], float(i))

    def test_template_inherits_the_default(self):
        self.assertEqual(self.mis["MI_UM_Figure_v2_Template"]["switches"], {})

    def test_gain_pairs_designed_equal(self):
        """The albedo spheres the scene compares: equal pairs have the same effective gain, E differs."""
        cols = {"red": [0.8, 0.02, 0.02], "p1": vm.MERLIN_P1, "p2": vm.MERLIN_P2}

        def eff(name):
            sw, colour, gain, ceiling, _ = vm.ALBEDO_TESTS[name]
            return effective_gain(sw is not False, gain or 0.0, ceiling or 0.0, cols[colour])

        self.assertAlmostEqual(eff("GainB"), eff("GainA"), places=6)
        self.assertAlmostEqual(eff("GainC"), eff("GainA"), places=6)
        self.assertAlmostEqual(eff("GainD"), eff("GainA"), places=6)
        self.assertNotAlmostEqual(eff("GainE"), eff("GainA"), places=2)
        self.assertAlmostEqual(eff("MerlinP1"), eff("MerlinP1Ref"), places=2)
        self.assertAlmostEqual(eff("MerlinP2"), eff("MerlinP2Ref"), places=1)

    def test_gain_rule_reproduces_the_hero_gains(self):
        """team-accent.md: gain = min(0.8 / Y50, 0.9 / (maxc(team) Y95)); Merlin P1 11.0 / P2 26.0 (ld-team-accent-ue)."""
        g, c = 0.8 / 0.0295, 0.9 / 0.0998
        self.assertAlmostEqual(effective_gain(True, g, c, vm.MERLIN_P1), 11.18, places=1)
        self.assertAlmostEqual(effective_gain(True, g, c, vm.MERLIN_P2), 26.01, places=1)
        self.assertEqual(effective_gain(False, g, c, vm.MERLIN_P1), g)   # v2.0 path: the ceiling is ignored


@unittest.skipUnless(bu.PRESETS.is_file(), "presets missing")
class AccentHalfTexture(unittest.TestCase):
    def test_half(self):
        cols = bu.class_columns(bu.load_presets())
        arr, mode, _ = bu.small_textures(cols)["T_UM_Test_AccentHalf"]
        self.assertEqual(mode, "L")
        self.assertEqual(arr.shape, (256, 256))
        self.assertTrue(np.all(arr[:128] == 255))
        self.assertTrue(np.all(arr[128:] == 0))


class HeroDyeAnalysis(unittest.TestCase):
    """ue_v2_accent.analyse_hero_view on synthetic frames: accent band dyed, the rest unchanged; the figure shadow
    (changed against the plate but not a class colour) stays out of the zones."""

    def frames(self):
        import ue_v2_accent as acc
        self.acc = acc
        calib = {str(c): [16 * c, 255 - 16 * c, (97 * c) % 256] for c in range(1, 16)}
        h = w = 48
        z = np.zeros((h, w, 3), np.int16)
        fig = (slice(4, 40), slice(4, 40))
        band = (slice(4, 16), slice(4, 40))
        dbg, plate = z.copy(), z.copy()
        dbg[fig] = calib["9"]
        dbg[42:46, 4:40] = 60        # figure shadow on the floor: changed against the plate, no class colour
        wv = z.copy()
        wv[band] = 223
        wv[42:46, 4:40] = 180        # the lit floor in the DebugView 10 frame
        alb = z.copy()
        alb[fig] = 100
        p1, p2 = alb.copy(), alb.copy()
        p1[band] = [200, 150, 50]
        p2[band] = [50, 80, 160]
        fr = {"dbg": dbg, "plate": plate, "w": wv, "alb_N": alb, "alb_N2": alb.copy(), "alb_P1": p1, "alb_P2": p2,
              "n_a": alb, "n_b": alb.copy(), "P1": p1, "P2": p2}
        return fr, calib

    def test_clean_dye_passes(self):
        fr, calib = self.frames()
        per, summ, checks = self.acc.analyse_hero_view(fr, calib)
        self.assertTrue(all(all(c.values()) for c in checks.values()), checks)
        self.assertEqual(summ["undecoded_changed_px"], 4 * 36)
        self.assertGreater(summ["weight_high_px"], 0)
        self.assertIn("wool_coarse", per)

    def test_leak_outside_the_mask_fails(self):
        fr, calib = self.frames()
        fr["alb_P1"][20:38, 4:40] = [140, 100, 60]
        _, _, checks = self.acc.analyse_hero_view(fr, calib)
        self.assertFalse(checks["P1"]["weight0_albedo_gt6_share_le_0_002"])
        self.assertTrue(checks["P2"]["weight0_albedo_gt6_share_le_0_002"])

    def test_haze_in_the_team_hue_fails(self):
        fr, calib = self.frames()
        fr["alb_P1"][16:40, 4:40] += np.array([1, 1, 0], np.int16)   # +1 level everywhere outside the band (bloom)
        _, summ, checks = self.acc.analyse_hero_view(fr, calib)
        self.assertFalse(checks["P1"]["weight0_albedo_bias_le_0_1"])
        self.assertTrue(checks["P1"]["weight0_albedo_gt6_share_le_0_002"])
        self.assertTrue(checks["P2"]["weight0_albedo_bias_le_0_1"])

    def test_dye_ignoring_the_team_fails(self):
        fr, calib = self.frames()
        fr["alb_P2"] = fr["alb_P1"].copy()
        _, _, checks = self.acc.analyse_hero_view(fr, calib)
        self.assertFalse(checks["P1"]["weight_high_P1_vs_P2_gt6_share_ge_0_95"])


if __name__ == "__main__":
    unittest.main()
