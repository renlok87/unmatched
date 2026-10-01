"""ENV-MAPS P5c track F: the Fab picks (AI-allowed packs only), their UE duplicate plan (ue_import_fab_picks.py --check
logic), layout_check's knowledge of the duplicates (check 11), the P5c layout generator (props only, idempotent, chained
with the P5 generator) and the P5b review follow-ups it carries (cherries, forest, vines, flowers, deck clusters,
lantern distances, looks, triangle budget).

CPU only, no UE / Blender: the committed pick file and looks, the committed P5b layouts as the generator's input (the
integrate stage writes the P5c layouts; until then the committed files stay the P5b state).
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ENV_KIT = HERE.parents[0] / "env_kit"
sys.path.insert(0, str(ENV_KIT))

import env_prop_look as LOOK  # noqa: E402
import layout_check as LC  # noqa: E402
import ue_import_fab_picks as FAB  # noqa: E402

RUN = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c"
P5_RUN = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
TOPO = REPO / "backend/prisma/fixtures/boards"
MAPS = ("marmoreal", "sarpedon")


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GEN = module(RUN / "scripts/p5c_layout_props.py", "p5c_layout_props")
GEN_P5 = module(P5_RUN / "scripts/p5_layout_props.py", "p5_layout_props")
PICKS = load(RUN / "scripts/fab-picks.json")
LC.kit_crosscheck(LC.BUILD_REPORTS)


# The P5b baseline these tests measure against. Integrate writes the P5c props (and Track V's fx / Track W's ground)
# into the working layouts, so the baseline is read from the P5b commit instead of the working tree.
P5B_COMMIT = "8938a03f"


def committed(key: str) -> dict:
    """The P5b layout (git show P5B_COMMIT); the test is skipped where git history is not available."""
    import subprocess
    rel = (LAYOUTS / f"{key}.layout.json").relative_to(REPO).as_posix()
    try:
        out = subprocess.run(["git", "-C", str(REPO), "show", f"{P5B_COMMIT}:{rel}"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:  # pragma: no cover - shallow clone / no git
        raise unittest.SkipTest(f"P5b baseline {P5B_COMMIT}:{rel} not available: {exc}")
    return json.loads(out.stdout.decode("utf-8"))


def working(key: str) -> dict:
    return load(LAYOUTS / f"{key}.layout.json")


def p5c(key: str) -> dict:
    """The P5c layout as the integrate stage writes it (P5c on top of the committed P5b layout)."""
    return GEN.apply(key, committed(key))


def spaces(key: str) -> list:
    return LC.load_spaces(load(TOPO / f"{key}.topology.json"))


def by_id(lay: dict) -> dict:
    return {p["id"]: p for p in lay["props"]}


class Picks(unittest.TestCase):
    def test_valid_and_ai_allowed_only(self):
        self.assertEqual(FAB.validate_picks(PICKS), [])
        packs = {e["pack"] for e in PICKS["meshes"].values()}
        self.assertLessEqual(packs, set(PICKS["aiAllowedPacks"]))
        text = json.dumps(PICKS)
        for root in FAB.NOAI_ROOTS:
            self.assertNotIn(f"/Game/{root}/", text)
        self.assertIn("предложено", PICKS["status"])
        self.assertNotIn("художественно принято", json.dumps(PICKS, ensure_ascii=False))

    def test_every_write_lands_under_envkit_fab(self):
        for m in PICKS["materials"].values():
            self.assertTrue(m["dest"].startswith("/Game/EnvKit/Fab/"), m["dest"])
        for e in PICKS["meshes"].values():
            self.assertTrue(e["dest"].startswith(f"/Game/EnvKit/Fab/{e['map']}/SM_EnvFab_"), e["dest"])
        with self.assertRaises(RuntimeError):
            FAB._guard("/Game/StylizedForest/Materials/M_Pink_leaves_Mat")
        FAB._guard("/Game/EnvKit/Fab/Shared/M_EnvFab_PinkLeaves")

    def test_validation_rejects(self):
        cases = [
            (lambda d: d["meshes"]["Bush"].update(source="/Game/Megaplant_Library/Yoshino/SM_Yoshino"), "NoAI"),
            (lambda d: d["meshes"]["Bush"].update(dest="/Game/StylizedForest/SM_Bush"), "is not /Game/EnvKit/Fab"),
            (lambda d: d["materials"]["MI_EnvFab_RockWet"].update(parent="/Game/Fantasy_Forest/Materials_Instance/MI_bark"),
             "descends from"),
            (lambda d: d["meshes"]["RockWet"]["slots"][0].update(night=None), "used by no slot"),
            (lambda d: d["materials"]["MI_EnvFab_SakuraLeavesNight"].update(parent="M_EnvFab_Jug"), "descends from"),
            (lambda d: d.update(aiAllowedPacks=d["aiAllowedPacks"] + ["StyleHex_Studio"]), "NoAI"),
        ]
        for mutate, needle in cases:
            d = copy.deepcopy(PICKS)
            mutate(d)
            text = " | ".join(FAB.validate_picks(d))
            self.assertIn(needle, text, needle)

    def test_night_materials(self):
        mats = PICKS["materials"]
        sak = mats["MI_EnvFab_SakuraLeavesNight"]["scalar"]
        # the sakura pink is muted for the night, wind frozen; P5c tune: NightTint pulls the warm-lit salmon back to a
        # cool pink (more blue than red / green), never above x1.35 on a channel
        self.assertTrue(0.6 <= sak["NightValue"] < 1.0 and 0.7 <= sak["NightSaturation"] < 1.0)
        self.assertEqual(sak["WPO"], 0.0)
        tint = mats["MI_EnvFab_SakuraLeavesNight"]["vector"]["NightTint"]
        self.assertTrue(tint[2] > tint[0] > tint[1] and max(tint[:3]) <= 1.35, tint)
        # the bush (lime ball in the campfire light) and the star-leaf flower clumps are darkened / cooled
        self.assertLessEqual(mats["MI_EnvFab_BushNight"]["scalar"]["NightValue"], 0.4)
        self.assertLess(mats["MI_EnvFab_FlowersNight"]["vector"]["NightTint"][1], 0.8)
        self.assertEqual(PICKS["meshes"]["FlowerLavender"]["slots"][0]["night"], "MI_EnvFab_LavenderNight")
        forest = mats["MI_EnvFab_ForestNight"]["scalar"]
        self.assertEqual((forest["Color Variation"], forest["Hue Shift"]), (0.0, 0.0))  # no hue by world position
        self.assertEqual(forest["Wind Intensity"], 0.0)
        for k in ("MI_EnvFab_Vine01Night", "MI_EnvFab_Vine02Night", "MI_EnvFab_Vine03Night"):
            self.assertTrue(mats[k]["twoSided"], k)
        self.assertLess(mats["MI_EnvFab_RockWet"]["vector"]["hue_color"][0], 0.4)
        for m in mats.values():  # every night MI mutes (never brightens) when it sets a value / brightness
            s = m.get("scalar", {})
            for k in ("NightValue", "NightSaturation"):
                if k in s:
                    self.assertLessEqual(s[k], 1.0)

    def test_hlsl_night_is_identity_at_one(self):
        c = np.array([0.31, 0.12, 0.2])
        luma = float(c @ np.array([0.2126, 0.7152, 0.0722]))

        def night(col, sat, val):
            return (luma + (col - luma) * sat) * val
        np.testing.assert_allclose(night(c, 1.0, 1.0), c)
        self.assertAlmostEqual(float(night(c, 0.0, 1.0)[0]), luma)
        self.assertIn("lerp(float3(l, l, l), C, Sat) * Val", FAB.HLSL_NIGHT)

    def test_night_tint_node(self):
        # P5c tune: a second Custom node multiplies by NightTint (default 1 = identity); tool version bumped so the
        # envfab-1 wraps / instances are revisited and the tint node is inserted after EnvFabNight
        self.assertEqual(FAB.HLSL_TINT, "return C * Tint.rgb;\n")
        self.assertEqual(FAB.TINT_PINS, ("C", "Tint"))
        self.assertNotEqual(FAB.TINT_NODE, FAB.NIGHT_NODE)
        self.assertEqual(FAB.TOOL_VERSION, "envfab-2")
        for k, m in PICKS["materials"].items():
            if m["kind"] == "instance" and "NightTint" in m.get("vector", {}):
                self.assertIn(m["parent"], PICKS["materials"], k)  # only the wraps carry NightTint
                self.assertEqual(PICKS["materials"][m["parent"]]["kind"], "wrap", k)

    @unittest.skipUnless(FAB.SCOUT_CATALOG.is_file(), "scout catalog (out of git) absent")
    def test_picks_equal_the_scout_inventory(self):
        self.assertEqual(FAB.check_catalog(PICKS, FAB.SCOUT_CATALOG), [])

    def test_cli_check(self):
        self.assertEqual(FAB.main(["--check"]), 0)

    def test_plan_orders_parents_first(self):
        p = FAB.plan(PICKS)
        self.assertEqual(len(p["meshes"]), len(PICKS["meshes"]))
        wraps = {k for k, _ in p["wraps"]}
        for k, m in p["instances"]:
            if m["parent"] in PICKS["materials"]:
                self.assertIn(m["parent"], wraps)
        only = FAB.plan(PICKS, ["RockWet"])
        self.assertEqual([k for k, _ in only["instances"]], ["MI_EnvFab_RockWet"])
        self.assertEqual(only["wraps"], [])


class FabGeometry(unittest.TestCase):
    def test_pivot_offset_footprint(self):
        # SakuraTwisted: pivot at the trunk base, bounds x -61.06 .. 1073.06 / y -311.05 .. 220.31; yaw 270 maps local
        # (x, y) -> (y, -x)
        p = {"id": "t", "mesh": PICKS["meshes"]["SakuraTwisted"]["dest"], "loc": [0.0, 0.0, -3.0], "yawDeg": 270.0,
             "scale": 0.2}
        fp = LC.footprint(p)
        self.assertAlmostEqual(float(fp[:, 0].min()), -311.05 * 0.2, places=3)
        self.assertAlmostEqual(float(fp[:, 0].max()), 220.31 * 0.2, places=3)
        self.assertAlmostEqual(float(fp[:, 1].min()), -1073.06 * 0.2, places=3)
        self.assertAlmostEqual(float(fp[:, 1].max()), 61.06 * 0.2, places=3)
        base = LC.footprint(p, base=True)  # the trunk box, not the crown
        self.assertLess(float(np.ptp(base[:, 1])), 30.0)
        self.assertEqual(LC.mesh_name(p), "Fab_SakuraTwisted")

    def test_hanging_card_box_and_mount(self):
        e = PICKS["meshes"]["VineCurtain"]
        p = {"id": "v", "mesh": e["dest"], "loc": [0.0, -446.0, 150.0], "yawDeg": 0.0, "scale": 0.8}
        b = LC.box_corners(p)
        self.assertAlmostEqual(float(b[:, 2].min()), 150.0 + e["bboxMin"][2] * 0.8, places=3)
        self.assertAlmostEqual(float(b[:, 2].max()), 150.0 + e["bboxMax"][2] * 0.8, places=3)
        self.assertTrue(LC.is_mounted(p))
        self.assertFalse(LC.is_mounted(dict(p, loc=[0.0, -446.0, -3.0])))
        flat = {"id": "s", "mesh": PICKS["meshes"]["VineSwag"]["dest"], "loc": [0.0, 0.0, 8.0], "yawDeg": 0.0,
                "scale": 0.9}
        self.assertGreaterEqual(float(np.ptp(LC.footprint(flat)[:, 1])), LC.FAB_MIN_THICK_UU - 1e-9)

    def test_tris_report(self):
        lay = {"props": [{"id": "a", "mesh": "/Game/EnvKit/Sarpedon/SM_Env_Tree"},
                         {"id": "b", "mesh": PICKS["meshes"]["OakDark"]["dest"]}]}
        r = LC.tris_report(lay)
        self.assertEqual(r["total"], LC.ENVKIT_TRIS["Tree"] + PICKS["meshes"]["OakDark"]["tris"])
        self.assertEqual(r["fab"], PICKS["meshes"]["OakDark"]["tris"])

    def test_selftest(self):
        self.assertEqual(LC.selftest(), 0)


class Layouts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lay = {k: p5c(k) for k in MAPS}
        cls.res = {}
        for k in MAPS:
            err, warn, info = LC.validate(cls.lay[k], k, spaces(k))
            cls.res[k] = (err, warn, info)

    def test_valid_no_warnings(self):
        for k in MAPS:
            err, warn, info = self.res[k]
            self.assertTrue(info["parsed"], k)
            # P5c props on the P5b ground section: only the stale splat sha may be flagged (ground_splat re-runs at
            # Integrate because the Marmoreal cherry crowns moved onto the Fab meshes)
            self.assertEqual([e for e in err if not e.startswith("ground:")], [], k)
            self.assertEqual([w for w in warn if not w.startswith("ground:")], [], k)
            # the shipped (integrated) layout: P5c props + fx + regenerated ground, no warnings at all
            err, warn, info = LC.validate(working(k), k, spaces(k))
            self.assertTrue(info["parsed"], k)
            self.assertEqual(err, [], k)
            self.assertEqual(warn, [], k)  # no rocky lip, no z, no prop-count guide, no tall-near-half warning

    def test_new_and_moved_props_clear_every_circle(self):  # checks 6 (all cameras) and 7 on the P5c props
        for k in MAPS:
            ids = {p["id"] for p in GEN.P5C_PROPS[k]()}
            sub = dict(self.lay[k], props=[p for p in self.lay[k]["props"] if p["id"] in ids])
            sp = spaces(k)
            for pid, w in LC.occlusion(sub, sp).items():
                self.assertGreaterEqual(w["px"], LC.MARGIN_PX, f"{k} {pid} {w}")
            for pid, s in LC.shadows(sub, sp).items():
                self.assertGreaterEqual(s["uu"], 0.0, f"{k} {pid}")

    def test_props_only_and_idempotent(self):
        for k in MAPS:
            cur, lay = committed(k), self.lay[k]
            self.assertEqual({a: b for a, b in lay.items() if a not in ("props", "notes")},
                             {a: b for a, b in cur.items() if a not in ("props", "notes")})
            self.assertEqual(GEN.apply(k, lay), lay)
            self.assertEqual(lay["notes"].count(GEN.NOTE_MARK), 1)
            # the P5 generator chains into P5c once P5c's paragraph is there - both idempotent on the merged result
            self.assertEqual(GEN_P5.apply(k, lay), lay)
            self.assertEqual(GEN_P5.apply(k, cur), cur)  # the committed P5b state is unchanged for the P5 generator

    def test_working_layouts_carry_the_p5c_props(self):
        # after Integrate the shipped layouts hold exactly the generator's props on top of P5b
        for k in MAPS:
            self.assertEqual(working(k)["props"], self.lay[k]["props"], k)
            self.assertEqual(GEN.apply(k, working(k))["props"], working(k)["props"], k)

    def test_kept_props_untouched(self):
        for k in MAPS:
            ids = {p["id"] for p in GEN.P5C_PROPS[k]()}
            old = [p for p in committed(k)["props"] if p["id"] not in ids]
            new = [p for p in self.lay[k]["props"] if p["id"] not in ids]
            self.assertEqual(old, new, k)

    def test_marmoreal_cherries(self):
        lay = by_id(self.lay["marmoreal"])
        cherries = {pid: p for pid, p in lay.items() if pid.startswith("cherry")}
        self.assertEqual(set(cherries), {"cherry-nw", "cherry-w", "cherry-e", "cherry-se"})  # ground_splat keys on ids
        p4 = {"cherry-nw": (-660.0, -395.0), "cherry-w": (-660.0, -170.0), "cherry-e": (660.0, -170.0),
              "cherry-se": (615.0, 255.0)}
        for pid, p in cherries.items():
            name = LC.mesh_name(p)
            self.assertIn(name, ("Fab_SakuraTwisted", "Fab_SakuraBirch"), pid)
            cx, cy = GEN.crown_centre(name[len(LC.FAB_PREFIX):], p["loc"], p["yawDeg"], p["scale"])
            self.assertLess(math.hypot(cx - p4[pid][0], cy - p4[pid][1]), 15.0, pid)  # crowns on the P4 points
        self.assertNotEqual(cherries["cherry-w"]["yawDeg"], cherries["cherry-e"]["yawDeg"])
        self.assertNotEqual(cherries["cherry-w"]["scale"], cherries["cherry-e"]["scale"])

    def test_marmoreal_vines_and_flowers(self):
        lay = self.lay["marmoreal"]
        vines = [p for p in lay["props"] if LC.mesh_name(p).startswith("Fab_Vine")]
        self.assertGreaterEqual(len(vines), 10)
        self.assertTrue(all(LC.is_mounted(p) and not p["castShadow"] for p in vines))
        wall = [p for p in vines if p["id"].startswith("vine-wall")]
        self.assertEqual(len(wall), 5)
        for p in wall:  # the garlands hang in the visible top band of the wall, above the arcade (top z 185)
            z0, z1 = LC.box_corners(p)[:, 2].min(), LC.box_corners(p)[:, 2].max()
            self.assertGreater(z0, 185.0, p["id"])
            self.assertLess(z1, GEN.CENTRE_TOP_Z, p["id"])
        flowers = [p for p in lay["props"] if LC.mesh_name(p).startswith("Fab_Flower")]
        self.assertGreaterEqual(len(flowers), 8)
        urns = {p["id"]: p for p in lay["props"] if LC.mesh_name(p) == "Urn"}
        for pid in ("flower-urn-w", "flower-urn-e"):
            f = by_id(lay)[pid]
            self.assertTrue(LC.is_mounted(f))
            self.assertTrue(any(math.hypot(f["loc"][0] - u["loc"][0], f["loc"][1] - u["loc"][1]) < 1.0
                                for u in urns.values()), pid)

    def test_sarpedon_forest_and_undergrowth(self):
        lay = by_id(self.lay["sarpedon"])
        trees = {pid: p for pid, p in lay.items() if pid.startswith("tree-")}
        self.assertEqual(len(trees), 8)
        self.assertTrue(all(LC.mesh_name(p).startswith("Fab_") for p in trees.values()))
        self.assertEqual(sum(LC.mesh_name(p) == "Fab_OakDark" for p in trees.values()), 3)
        self.assertEqual(len({p["yawDeg"] for p in trees.values()}), 8)
        self.assertTrue(all(p["loc"][0] < -LC.FRAME_HX - 100 for p in trees.values()))  # the west forest
        self.assertEqual(sum(LC.mesh_name(p) == "Fab_Bush" for p in lay.values()), 2)
        rocks = [p for p in lay.values() if LC.mesh_name(p) == "Fab_RockWet"]
        self.assertEqual(len(rocks), 2)
        vines = [p for p in lay.values() if LC.mesh_name(p).startswith("Fab_Vine")]
        self.assertGreaterEqual(len(vines), 6)
        self.assertTrue(all(LC.is_mounted(p) for p in vines))

    def test_sarpedon_vines_on_the_fronts(self):
        lay = by_id(self.lay["sarpedon"])
        for vid, host in (("vine-pal-n1", "palisade-n1"), ("vine-pal-w1", "palisade-w1"), ("vine-pal-w3", "palisade-w3"),
                          ("vine-fort", "fort-nw")):
            v, h = lay[vid], lay[host]
            n = np.array([math.cos(math.radians(h["yawDeg"])), math.sin(math.radians(h["yawDeg"]))])
            c = LC.footprint(h).mean(0)
            off = (LC.footprint(v) - c) @ n
            half = float(np.ptp(LC.footprint(h) @ n)) / 2
            self.assertGreater(float(off.min()), half, vid)  # wholly in front of the host's front face
            self.assertLess(float(off.min()), half + 2.0, vid)  # and on it (<= 2 uu gap)

    def test_lanterns_away_from_the_campfire_lights(self):
        d = GEN.lantern_distances(self.lay["sarpedon"])
        for pid in ("lantern-w", "lantern-n"):
            self.assertGreaterEqual(d[pid]["uu"], GEN.LANTERN_MIN_UU, pid)
        before = GEN.lantern_distances(committed("sarpedon"))
        self.assertLess(before["lantern-w"]["uu"], 60.0)  # the P5b state the review measured (51 / 56 uu)
        self.assertEqual(self.lay["sarpedon"]["lights"], committed("sarpedon")["lights"])  # no light moved

    def test_deck_clusters(self):
        deck = [p for p in self.lay["sarpedon"]["props"] if LC.mesh_name(p) in ("Barrel", "CrateStack")]
        self.assertEqual(len(deck), 9)
        xs = np.array([p["loc"][0] for p in deck])
        self.assertTrue((xs > LC.FRAME_HX).all())
        self.assertGreater(float(np.ptp(xs)), 100.0)  # no longer one column (P5b: x 500 .. 546)
        self.assertGreaterEqual(len({p["scale"] for p in deck}), 4)
        ys = np.sort([p["loc"][1] for p in deck])
        self.assertGreater(float(np.diff(ys).max()), 150.0)  # an empty stretch between clumps
        old = [p for p in committed("sarpedon")["props"] if LC.mesh_name(p) in ("Barrel", "CrateStack")]
        self.assertLess(float(np.ptp([p["loc"][0] for p in old])), 50.0)

    def test_triangle_budget(self):
        for k in MAPS:
            tr = LC.tris_report(self.lay[k])
            self.assertEqual(LC.tris_report(committed(k))["total"], GEN.P5B_TRIS[k], k)
            self.assertLessEqual(tr["total"], GEN.P5B_TRIS[k] * 1.08, k)  # the lighter picks: within +8 % of P5b

    def test_noai_never_in_the_main_layouts(self):
        for k in MAPS:
            text = json.dumps(self.lay[k])
            for root in FAB.NOAI_ROOTS:
                self.assertNotIn(root, text)
            self.assertEqual(FAB.check_layout_refs(PICKS, {k: self.lay[k]}), [])

    def test_generator_cli_scratch(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(GEN.main(["--out", d]), 0)
            for k in MAPS:
                out = load(Path(d) / f"{k}.layout.json")
                self.assertEqual(out["props"], self.lay[k]["props"], k)
                self.assertEqual(out, working(k), k)  # the generator leaves the integrated layout as it is
                self.assertEqual(GEN.main(["--check", "--layouts", d]), 0)


class Looks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = LOOK.load_look(LOOK.LOOK_P5)
        cls.res = {n: LOOK.measure(n, cls.data, P5_RUN) for n in ("Barrel", "CrateStack", "RockOutcrop", "BackWall",
                                                                  "LanternPost")}

    def test_deck_value_separation(self):
        barrel = self.res["Barrel"]["rest"]["after"]
        crate = self.res["CrateStack"]["rest"]["after"]
        self.assertGreater(crate["val"] / barrel["val"], 1.35)  # P5b: 1.09
        self.assertLess(crate["sat"], barrel["sat"])

    def test_dark_wet_rock(self):
        r = self.res["RockOutcrop"]
        self.assertLessEqual(r["rest"]["valRatio"], 0.62)
        self.assertLessEqual(self.data["props"]["RockOutcrop"]["surface"]["RoughnessMax"], 0.6)

    def test_back_wall_darker_calmer_glow(self):
        r = self.res["BackWall"]
        self.assertLess(r["albedoLuminance"]["after"] / r["albedoLuminance"]["before"], 0.72)
        self.assertLessEqual(self.data["props"]["BackWall"]["emissive"]["intensity"], 2.2)
        self.assertLess(r["emissive"]["meanLuminance"], 1.19)
        # P5c tune (UE K1: the wall fills the arcade openings, top band 113.8 vs P4 91.9): stone x0.52, glow x1.2
        self.assertLess(r["albedoLuminance"]["after"] / r["albedoLuminance"]["before"], 0.55)
        self.assertLessEqual(self.data["props"]["BackWall"]["emissive"]["intensity"], 1.3)

    def test_lantern_glass_lights_more(self):
        r = self.res["LanternPost"]
        self.assertGreater(r["emissiveFraction"], 0.015)  # P5b: 0.0113


if __name__ == "__main__":
    unittest.main()
