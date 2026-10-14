"""W1-e (skill pilot 2026-10-13, RB-08 / RB-09 / F59 / F113 / F127): rig probes and weapon contact.

Both tools run only inside headless Blender (they import bpy and raise outside `blender -b`), so the pure helpers are
taken from the source by AST and executed without bpy, as tools/art/acceptance/_blender_capture.py reads FAMILIES and
TESTS of the probe. Live runs on the pilot and MVP rigs/clips are recorded in the W1-e report, not here.

1. rig_deform_probe.py: the 7 legacy probes (FAMILIES, TESTS) are byte-for-byte the old contract (run_h2_bake.py,
   validate_card.py and the acceptance capture count/read them); the extended list (right forearm, shins, feet, hand
   of the weapon arm, weapon.* bones) is built from data, the summary counts n/N from the lists; weapon side detection.
2. clip_contact_check.py: weapon.extra_parts parsing and part selection (bone / islands), foot_slide with 0 sole
   vertices is WARN «not measured» (F113), the per-part weapon verdict equals the old verdict without extra parts.
3. Both entry points reconfigure stdout/stderr to UTF-8 before they parse arguments (RB-11/F47).

Run from the repo root:  python -m pytest tools/tripo-pipeline/tests/test_rig_probe_contact.py -q
"""

import ast
import random
import re
import unittest
from pathlib import Path

ANIM = Path(__file__).resolve().parents[1] / "anim"
PROBE = ANIM / "rig_deform_probe.py"
CONTACT = ANIM / "clip_contact_check.py"

LEGACY_TESTS = [
    ("head_turn", "head", "Z", 35, {"z_norm_min": 0.70}),
    ("spine_bend_fwd", "spine", "X", 25, {"z_norm_min": 0.45}),
    ("arm_l_raise", "arm_l", "Y", -45, {"z_norm_min": 0.35, "x_norm_min": 0.15}),
    ("arm_r_raise", "arm_r", "Y", 45, {"z_norm_min": 0.35, "x_norm_max": -0.15}),
    ("forearm_l_bend", "fore_l", "X", -40, {"z_norm_min": 0.30, "x_norm_min": 0.20}),
    ("thigh_l_flex", "thigh_l", "X", -35, {"z_norm_max": 0.55}),
    ("thigh_r_flex", "thigh_r", "X", -35, {"z_norm_max": 0.55}),
]
LEGACY_CONTRACT17 = {"head": "head", "spine": "spine", "arm_l": "arm_upper.L", "arm_r": "arm_upper.R",
                     "fore_l": "arm_lower.L", "thigh_l": "leg_upper.L", "thigh_r": "leg_upper.R"}


def load_parts(path, names):
    """Top-level constants (literal assignments) and the named functions of a Blender script, without bpy."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    body = []
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in names:
            body.append(n)
        elif isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets):
            try:
                ast.literal_eval(n.value)
            except ValueError:
                continue
            body.append(n)
    ns = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(path), "exec"), ns)
    return ns


def main_body(path):
    src = path.read_text(encoding="utf-8")
    m = re.search(r"^def main\(.*?(?=^def |^try:|^main\(\)|^if __name__)", src, re.S | re.M)
    assert m, "%s: def main() not found" % path.name
    return m.group(0)


class RigDeformProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p = load_parts(PROBE, {"side_of", "weapon_bone_names", "weapon_sides", "ext_plan", "zone_ok",
                                   "probe_summary"})

    def test_legacy_probes_unchanged(self):
        self.assertEqual(self.p["TESTS"], LEGACY_TESTS)
        self.assertEqual(self.p["FAMILIES"]["contract17"], LEGACY_CONTRACT17)
        self.assertEqual(sorted(self.p["FAMILIES"]), ["contract17", "mixamo", "ue_like"])

    def test_extended_bones_for_every_family(self):
        keys = {k for _n, k, _a, _d, _e in self.p["EXT_TESTS"]} | {v[1] for v in self.p["HAND_TWIST"].values()}
        for fam in self.p["FAMILIES"]:
            with self.subTest(family=fam):
                self.assertTrue(keys <= set(self.p["FAMILIES_EXT"][fam]), keys - set(self.p["FAMILIES_EXT"][fam]))
        names = [t[0] for t in self.p["EXT_TESTS"]]
        for need in ("forearm_r_bend", "shin_l_bend", "shin_r_bend", "foot_l_flex", "foot_r_flex"):
            self.assertIn(need, names)
        self.assertFalse(set(names) & {t[0] for t in LEGACY_TESTS})

    def test_forearm_r_mirrors_forearm_l(self):
        fl = next(t for t in LEGACY_TESTS if t[0] == "forearm_l_bend")
        fr = next(t for t in self.p["EXT_TESTS"] if t[0] == "forearm_r_bend")
        self.assertEqual(fr[2:4], fl[2:4])
        self.assertEqual((fr[4]["z_norm_min"], fr[4]["x_norm_max"]), (fl[4]["z_norm_min"], -fl[4]["x_norm_min"]))

    def test_extended_probes_check_own_part_and_weight_bleed(self):
        """Zone-only probes passed every synthetic weight defect (rigid forearm, foot/hand bleed into the torso), so the
        extended probes also need the bone's own part to move and a small weight leak; the shin is exempt from the own
        part (a robe hem is skinned to hips/thighs: Merlin's shins own no vertex)."""
        plan = self.p["ext_plan"](self.p["FAMILIES_EXT"]["contract17"], ["R"], ["weapon.R"])
        for name, _b, _a, _d, e in plan:
            with self.subTest(probe=name):
                self.assertEqual(e.get("bleed_share_max"), 0.05)
                self.assertEqual("own_moved_min" in e, not name.startswith("shin_"))
        for _n, _k, _a, _d, e in LEGACY_TESTS:
            self.assertFalse({"own_moved_min", "bleed_share_max", "weapon_share_min"} & set(e))

    def test_weapon_sides(self):
        ws = self.p["weapon_sides"]
        par = {"weapon.R": "hand.R", "hand.R": "arm_lower.R", "weapon": "hand.L", "hand.L": "arm_lower.L"}
        self.assertEqual(ws(["weapon.R"], par), (["R"], "weapon_bone"))
        self.assertEqual(ws(["weapon.L", "weapon.R"], par), (["L", "R"], "weapon_bone"))
        self.assertEqual(ws(["weapon"], par), (["L"], "weapon_bone"))  # v1 bone without a side: side of its parent
        self.assertEqual(ws([], par), ([], "none"))
        self.assertEqual(ws([], par, mesh_side="R"), (["R"], "weapon_mesh"))
        self.assertEqual(ws(["weapon.R"], par, opt="none"), ([], "option"))
        self.assertEqual(ws([], par, opt="lr"), (["L", "R"], "option"))
        self.assertEqual(self.p["weapon_bone_names"](["hand.R", "weapon.R", "Weapon_L", "root"]),
                         ["Weapon_L", "weapon.R"])

    def test_plan_size_comes_from_lists(self):
        fext = self.p["FAMILIES_EXT"]["contract17"]
        base = len(self.p["EXT_TESTS"])
        self.assertEqual(len(self.p["ext_plan"](fext, [], [])), base)  # Harpy, Leshen: no weapon
        plan = self.p["ext_plan"](fext, ["R"], ["weapon.R"])  # Achilles, Angel, Arthur, Merlin
        self.assertEqual(len(plan), base + 2)
        self.assertEqual(plan[-2][:4], ("hand_r_twist", "hand.R", "BONE", 35))
        self.assertEqual(plan[-1][:3], ("weapon_turn_weapon.R", "weapon.R", "PERP"))
        self.assertEqual(plan[-1][4]["weapon_share_min"], 0.90)
        self.assertEqual(self.p["ext_plan"](fext, ["L"], ["weapon.L"])[-2][1], "hand.L")  # Medusa: bow in the left

    def test_zone_ok_matches_the_legacy_rule(self):
        z = self.p["zone_ok"]

        def legacy(moved, zn, xn, e):  # the inline rule of the old main()
            ok = moved != []
            if ok and "z_norm_min" in e:
                ok &= zn >= e["z_norm_min"]
            if ok and "z_norm_max" in e:
                ok &= zn <= e["z_norm_max"]
            if ok and "x_norm_min" in e:
                ok &= xn >= e["x_norm_min"]
            if ok and "x_norm_max" in e:
                ok &= xn <= e["x_norm_max"]
            return ok

        rnd = random.Random(7)
        for _ in range(500):
            e = rnd.choice(LEGACY_TESTS)[4]
            n = rnd.choice([0, 1, 50])
            zn, xn = (rnd.uniform(-0.2, 1.2), rnd.uniform(-1.2, 1.2)) if n else (None, None)
            self.assertEqual(z(n, zn, xn, e), legacy([0] * n, zn, xn, e))
            # own/bleed values never change a legacy verdict (their expectations have no such keys)
            self.assertEqual(z(n, zn, xn, e, 0.0, 0, 1.0), legacy([0] * n, zn, xn, e))
        self.assertTrue(z(10, 0.5, 0.0, {"weapon_share_min": 0.9}, 0.95))
        self.assertFalse(z(10, 0.5, 0.0, {"weapon_share_min": 0.9}, 0.5))
        self.assertFalse(z(10, 0.5, 0.0, {"weapon_share_min": 0.9}, None))
        e = {"z_norm_min": 0.3, "own_moved_min": 1, "bleed_share_max": 0.05}
        self.assertTrue(z(10, 0.5, 0.0, e, None, 3, 0.0))
        self.assertFalse(z(10, 0.5, 0.0, e, None, 0, 0.0))  # rigid forearm: only the hand and weapon moved
        self.assertFalse(z(10, 0.5, 0.0, e, None, 3, 0.2))  # 20 % of the moved vertices are a far torso leak

    def test_summary_counts_both_lists(self):
        s = self.p["probe_summary"]
        legacy = [{"test": t[0], "status": "plausible"} for t in LEGACY_TESTS]
        ext = [{"test": "forearm_r_bend", "status": "plausible"}, {"test": "foot_l_flex", "status": "skipped"},
               {"test": "shin_l_bend", "status": "unweighted"}]
        r = s(legacy, ext)
        self.assertEqual((r["summary"], r["legacy"], r["extended"], r["passed"]), ("8/9", "7/7", "1/2", False))
        self.assertEqual(r["skipped"], ["foot_l_flex"])
        r = s(legacy, ext[:2])
        self.assertEqual((r["summary"], r["passed"]), ("8/8", True))
        self.assertFalse(s([], [])["passed"])

    def test_entry_reconfigures_utf8_before_args(self):
        body = main_body(PROBE)
        fix = body.find('reconfigure(encoding="utf-8", errors="backslashreplace")')
        self.assertGreater(fix, 0)
        self.assertLess(fix, body.find("args()"))

    def test_acceptance_capture_still_reads_families_and_tests(self):
        """tools/art/acceptance/_blender_capture.py: FAMILIES and TESTS are literal top-level assignments."""
        out = {}
        for node in ast.parse(PROBE.read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id in ("FAMILIES", "TESTS"):
                    out[node.targets[0].id] = ast.literal_eval(node.value)
        self.assertEqual(out["TESTS"], LEGACY_TESTS)
        self.assertIn("contract17", out["FAMILIES"])


class ClipContactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = load_parts(CONTACT, {"extra_part_specs", "island_labels", "part_polys", "foot_slide_verdict",
                                     "weapon_verdict"})

    def test_extra_parts_spec(self):
        f = self.c["extra_part_specs"]
        self.assertEqual(f({}), [])
        self.assertEqual(f({"weapon": {"bone": "weapon.R", "side": "R"}}), [])
        self.assertEqual(f({"weapon": {"extra_parts": ["weapon.R", {"bone": "arm_lower.L", "islands": True}]}}),
                         [{"bone": "weapon.R", "islands": False, "name": "weapon.R"},
                          {"bone": "arm_lower.L", "islands": True, "name": "arm_lower.L#islands"}])
        for bad in ([1], [{"islands": True}], [""], ["weapon.R", "weapon.R"]):
            with self.subTest(bad=bad):
                self.assertRaises(ValueError, f, {"weapon": {"extra_parts": bad}})

    def test_part_selection_by_bone_and_by_island(self):
        # island A (0-2): a shield, all 100 % on arm_lower.L; island B (3-6): forearm skin, mostly hard on arm_lower.L
        # but blended towards the elbow at vertex 6
        vw = [{"arm_lower.L": 1.0}, {"arm_lower.L": 1.0}, {"arm_lower.L": 0.97},
              {"arm_lower.L": 1.0}, {"arm_lower.L": 1.0}, {"arm_lower.L": 0.96},
              {"arm_lower.L": 0.5, "arm_upper.L": 0.5}]
        polys = [(0, 1, 2), (3, 4, 5), (4, 5, 6)]
        edges = [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (5, 6), (6, 4)]
        lab = self.c["island_labels"](7, edges)
        self.assertEqual(len(set(lab)), 2)
        pp = self.c["part_polys"]
        self.assertEqual(pp(vw, polys, "arm_lower.L", False), [0, 1])  # vertex level: shield + hard forearm skin
        self.assertEqual(pp(vw, polys, "arm_lower.L", True, lab), [0])  # islands: the shield only
        self.assertEqual(pp(vw, polys, "weapon.R", False), [])

    def test_foot_slide_without_sole_vertices_is_not_a_pass(self):
        v = self.c["foot_slide_verdict"]([(0, 0.0), (5, 0.0)], 0, "L", 0.005)
        self.assertEqual((v["status"], v["measured"], v["foot_vertices"], v["max_of_height"]), ("warn", False, 0, None))
        self.assertIn("F113", v["reason"])
        self.assertEqual(self.c["foot_slide_verdict"]([(0, 0.0), (5, 0.004)], 120, "R", 0.005),
                         {"status": "pass", "max_of_height": 0.004, "frame": 5, "pinned_frames": 2, "tol": 0.005,
                          "foot_vertices": 120})
        self.assertEqual(self.c["foot_slide_verdict"]([(3, 0.006)], 120, "R", 0.005)["status"], "fail")
        self.assertEqual(self.c["foot_slide_verdict"]([], 120, "R", 0.005),
                         {"status": "pass", "max_of_height": 0.0, "frame": None, "pinned_frames": 0, "tol": 0.005,
                          "foot_vertices": 120})

    def test_weapon_verdict_without_parts_equals_the_old_rule(self):
        def legacy(rows):  # the inline rule of the old main()
            base = rows[0][1]
            bad, soft = [], []
            for f, bones in rows:
                for g, n in bones.items():
                    b0 = base.get(g, 0)
                    if (b0 == 0 and n > 0) or n > b0 * 3.0 + 20:
                        bad.append({"f": f, "bone": g, "pairs": n, "rest_pairs": b0})
                    elif n > b0 * 1.25 + 10:
                        soft.append({"f": f, "bone": g, "pairs": n, "rest_pairs": b0})
            return bad, soft

        rnd = random.Random(3)
        for _ in range(200):
            rows = [(f, {g: rnd.choice([0, 3, 12, 40, 90]) for g in rnd.sample(["spine", "hips", "head", "foot.R"], 2)})
                    for f in range(6)]
            self.assertEqual(self.c["weapon_verdict"]([(f, {"mesh": b}) for f, b in rows], False), legacy(rows))

    def test_rest_contact_of_one_part_does_not_mask_another(self):
        frames = [(0, {"Spear": {}, "weapon.R": {"spine": 30}}),
                  (1, {"Spear": {"spine": 25}, "weapon.R": {"spine": 30}})]
        bad, soft = self.c["weapon_verdict"](frames, True)
        self.assertEqual(bad, [{"f": 1, "bone": "spine", "pairs": 25, "rest_pairs": 0, "part": "Spear"}])
        self.assertEqual(soft, [])
        merged = self.c["weapon_verdict"]([(0, {"mesh": {"spine": 30}}), (1, {"mesh": {"spine": 55}})], False)
        self.assertEqual(merged[0], [])  # one bag for both parts: no FAIL (55 <= 30 * 3 + 20), only a soft WARN

    def test_entry_reconfigures_utf8_before_args(self):
        body = main_body(CONTACT)
        fix = body.find('reconfigure(encoding="utf-8", errors="backslashreplace")')
        self.assertGreater(fix, 0)
        self.assertLess(fix, body.find("sys.argv"))


if __name__ == "__main__":
    unittest.main()
