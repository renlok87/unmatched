"""ENV-MAPS P5c track V: the environment fx - the derived Niagara specs (tools/art/env_kit/ue_import_fab_fx.py --check),
the fx layout generator (art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/p5c_layout_fx.py) and the
measured flame anchors (p5c_fx_anchor_probe.py report).

CPU only, no UE / Blender: the generator runs on copies of the committed layouts (never over them).
  python -B -m unittest tools/art/tests/test_env_fx_p5c.py
"""
from __future__ import annotations

import copy
import importlib.util
import json
import math
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ENV_KIT = HERE.parents[0] / "env_kit"
sys.path.insert(0, str(ENV_KIT))

import ue_import_fab_fx as FX  # noqa: E402

RUN = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


GEN = _load_module("p5c_layout_fx", RUN / "scripts/p5c_layout_fx.py")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class FxSpecs(unittest.TestCase):
    def test_shipped_specs_are_valid(self):
        err, _warn = FX.validate(FX.FX_SPECS, content=None)
        self.assertEqual(err, [])
        self.assertEqual({s["name"] for s in FX.FX_SPECS},
                         {"NS_Env_Campfire", "NS_Env_LanternFlame", "NS_Env_CherryPetals", "NS_Env_Fireflies"})

    def test_targets_and_rules(self):
        for s in FX.FX_SPECS:
            self.assertTrue(FX.target_path(s).startswith("/Game/EnvKit/FX/NS_Env_"))
            self.assertIn(s["pack"], FX.AI_ALLOWED_PACKS)
            self.assertEqual(s["tune"]["simTarget"], "cpu")
            self.assertTrue(s["tune"]["disableLightRenderers"] and s["tune"]["disableComponentRenderers"])
            self.assertTrue(s["system"]["determinism"])

    def test_tuned_flames_and_fireflies(self):
        # P5c tune t1: the flames read as a faint wisp in their own warm light pool -> colour x3 / x2.5, campfire k 0.4;
        # the fireflies' size is the user parameter (the constant rule matched nothing in the integrate import)
        camp = FX.spec_by_name("NS_Env_Campfire")["tune"]["constants"]
        self.assertIn({"match": "*.Color.Scale Color", "mul": 3.0}, camp)
        self.assertIn({"match": "*.InitializeParticle.Uniform Sprite Size*", "mul": 0.4}, camp)
        lantern = FX.spec_by_name("NS_Env_LanternFlame")["tune"]["constants"]
        self.assertIn({"match": "*.Color.Scale Color", "mul": 2.5}, lantern)
        ff = FX.spec_by_name("NS_Env_Fireflies")["tune"]
        self.assertEqual(ff["constants"], [])
        self.assertLess(ff["user"]["Uniform Sprite Size Min"], ff["user"]["Uniform Sprite Size Max"])

    def _bad(self, mutate) -> list[str]:
        s = copy.deepcopy(FX.FX_SPECS[0])
        mutate(s)
        err, _ = FX.validate([s], content=None)
        return err

    def test_rejections(self):
        def noai(s):
            s["source"] = "/Game/Megaplant_Library/Yoshino/NS_X"
            s["pack"] = "Megaplant_Library"
        self.assertTrue(any("NoAI" in e for e in self._bad(noai)))
        self.assertTrue(any("NoAI" in e for e in self._bad(lambda s: s.update(source="/Game/StyleHex_Studio/NS_Y",
                                                                               pack="StyleHex_Studio"))))
        self.assertTrue(any("AI-allowed" in e for e in self._bad(lambda s: s.update(source="/Game/Other/NS_Z", pack="Other"))))
        self.assertTrue(any("simTarget" in e for e in self._bad(lambda s: s["tune"].update(simTarget="gpu"))))
        self.assertTrue(any("Light" in e for e in self._bad(lambda s: s["tune"].update(disableLightRenderers=False))))
        self.assertTrue(any("determinism" in e for e in self._bad(lambda s: s["system"].update(determinism=False))))
        self.assertTrue(any("mul" in e for e in self._bad(lambda s: s["tune"]["constants"].append({"match": "*", "mul": 5}))))
        # P5c tune: a colour scale may go to x6, a size / force rule stays <= x2
        self.assertFalse(self._bad(lambda s: s["tune"]["constants"].append({"match": "*.Color.Scale Color", "mul": 5})))
        self.assertTrue(any("mul" in e
                            for e in self._bad(lambda s: s["tune"]["constants"].append({"match": "*.Color.Scale Color", "mul": 7}))))
        self.assertTrue(any("exactly one" in e
                            for e in self._bad(lambda s: s["tune"]["constants"].append({"match": "*", "mul": 1, "set": 2}))))
        self.assertTrue(any("User." in e for e in self._bad(lambda s: s["tune"]["user"].update({"User.X": 1}))))
        self.assertTrue(any("name" in e for e in self._bad(lambda s: s.update(name="Campfire"))))
        dup = [copy.deepcopy(FX.FX_SPECS[0]), copy.deepcopy(FX.FX_SPECS[0])]
        self.assertTrue(any("duplicate" in e for e in FX.validate(dup, content=None)[0]))

    def test_particle_estimates(self):
        # Stylish fire: (50 + 25 + 25) / s x 0.9 s x the spawn factor
        self.assertAlmostEqual(FX.estimate_particles("NS_Env_Campfire"), 100 * 0.9 * 0.8)
        self.assertAlmostEqual(FX.estimate_particles("NS_Env_LanternFlame"), 100 * 0.9 * 0.5)
        self.assertAlmostEqual(FX.estimate_particles("NS_Env_CherryPetals"), 6 * 5.0)
        self.assertAlmostEqual(FX.estimate_particles("NS_Env_Fireflies"), 5 * 2.75)
        self.assertAlmostEqual(FX.estimate_particles("NS_Env_Fireflies", {"User.SpawnRate": 4}), 4 * 2.75)
        for s in FX.FX_SPECS:
            self.assertLessEqual(FX.estimate_particles(s["name"]), FX.FX_PARTICLE_BUDGET)

    def test_spec_sha_tracks_the_tune(self):
        s = copy.deepcopy(FX.FX_SPECS[0])
        a = FX.spec_sha256(s)
        self.assertEqual(a, FX.spec_sha256(copy.deepcopy(s)))
        s["role"] = "documentation only"
        self.assertEqual(a, FX.spec_sha256(s), "role / licence text does not force a rebuild")
        s["tune"]["constants"][0]["mul"] = 0.31
        self.assertNotEqual(a, FX.spec_sha256(s))

    def test_check_mode_runs_without_ue(self):
        with tempfile.TemporaryDirectory() as tmp:
            rep = Path(tmp) / "r.json"
            self.assertEqual(FX.main(["--check", "--report", str(rep)]), 0)
            data = load(rep)
            self.assertEqual(data["mode"], "check")
            self.assertEqual(set(data["plan"]), {s["name"] for s in FX.FX_SPECS})


class FxAnchors(unittest.TestCase):
    def test_measured_anchors_inside_their_meshes(self):
        path = RUN / "reports/p5c-fx-anchors.json"
        self.assertTrue(path.is_file(), "run p5c_fx_anchor_probe.py (headless Blender)")
        data = load(path)
        for name, m in data["meshes"].items():
            c = m["glowCentroidUU"]
            lo, hi = m["meshBoundsUU"]["min"], m["meshBoundsUU"]["max"]
            for i in range(3):
                self.assertTrue(lo[i] <= c[i] <= hi[i], f"{name} centroid axis {i}")
            self.assertEqual(GEN.ANCHOR_DEFAULTS[name], c, "generator fallback = the measured report")
        # the flames sit in the upper part of the lanterns and on the logs of the campfire
        self.assertGreater(data["meshes"]["SM_Env_LanternPlinth"]["glowCentroidUU"][2], 40)
        self.assertGreater(data["meshes"]["SM_Env_LanternPost"]["glowCentroidUU"][2], 40)
        self.assertLess(data["meshes"]["SM_Env_Campfire"]["glowCentroidUU"][2], 16.9)


class FxLayoutGenerator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layouts = {k: load(LAYOUTS / f"{k}.layout.json") for k in ("marmoreal", "sarpedon")}
        cls.anchors = GEN.load_anchors()
        cls.fab = GEN.load_fab_bounds()

    def test_only_the_fx_section_changes_and_idempotent(self):
        for key, lay in self.layouts.items():
            src = copy.deepcopy(lay)
            new = GEN.apply(key, lay, self.anchors, self.fab)
            self.assertEqual(lay, src, "input untouched")
            self.assertEqual({k: v for k, v in new.items() if k != "fx"}, {k: v for k, v in lay.items() if k != "fx"})
            keys = [k for k in new if k != "fx"]
            self.assertEqual(keys, [k for k in lay if k != "fx"], "key order kept")
            self.assertLess(list(new).index("fx"), list(new).index("notes"), "fx before notes")
            again = GEN.apply(key, new, self.anchors, self.fab)
            self.assertEqual(json.dumps(again, indent=2), json.dumps(new, indent=2), "idempotent")

    def test_rules_hold_on_the_committed_layouts(self):
        for key, lay in self.layouts.items():
            new = GEN.apply(key, lay, self.anchors, self.fab)
            err, _warn, info = GEN.check_fx(key, new, new["fx"])
            self.assertEqual(err, [], key)
            self.assertGreater(info["particlesEstimate"], 100)
            self.assertLessEqual(info["particlesEstimate"], FX.BOARD_PARTICLE_BUDGET)
            ids = [e["id"] for e in new["fx"]]
            self.assertEqual(len(ids), len(set(ids)))
            props = {p["id"] for p in new["props"]}
            for e in new["fx"]:
                self.assertTrue(e["system"].startswith("/Game/EnvKit/FX/"))
                self.assertEqual(e["seed"], zlib.crc32(f"{key}:{e['id']}".encode()) & 0x7FFFFFFF)
                self.assertGreater(e["warmupS"], 0)
                if "anchor" in e:
                    self.assertIn(e["anchor"], props)

    def test_placement_per_map(self):
        marm = GEN.apply("marmoreal", self.layouts["marmoreal"], self.anchors, self.fab)["fx"]
        sarp = GEN.apply("sarpedon", self.layouts["sarpedon"], self.anchors, self.fab)["fx"]
        by = lambda lst, sys_: sorted(e["id"] for e in lst if e["system"].endswith(sys_))  # noqa: E731
        lit = {lt["id"] for lt in self.layouts["marmoreal"]["lights"]}
        plinths = sorted(f"flame-{p['id']}" for p in self.layouts["marmoreal"]["props"]
                         if p["mesh"].endswith("SM_Env_LanternPlinth") and p["id"] in lit)
        self.assertEqual(by(marm, "NS_Env_LanternFlame"), plinths)
        self.assertEqual(by(marm, "NS_Env_CherryPetals"),
                         sorted(f"petals-{p['id']}" for p in self.layouts["marmoreal"]["props"] if p["id"].startswith("cherry")))
        self.assertEqual(len(by(marm, "NS_Env_Fireflies")), 2)
        self.assertEqual(by(sarp, "NS_Env_Campfire"),
                         sorted(f"fire-{p['id']}" for p in self.layouts["sarpedon"]["props"]
                                if p["mesh"].endswith("SM_Env_Campfire")))
        self.assertEqual(by(sarp, "NS_Env_LanternFlame"),
                         sorted(f"flame-{p['id']}" for p in self.layouts["sarpedon"]["props"]
                                if p["mesh"].endswith("SM_Env_LanternPost")))
        self.assertEqual(len(by(sarp, "NS_Env_Fireflies")), 3)
        self.assertFalse(any("NS_Env_CherryPetals" in e["system"] for e in sarp))

    def test_anchor_transform_matches_the_cpp_convention(self):
        # S08EnvLayoutTests FxParse: prop at (-560, -400, -3) yaw 90, offset (10, 0, 6) -> (-560, -390, 3)
        x, y, z = GEN.board_xy({"loc": [-560.0, -400.0, -3.0], "yawDeg": 90.0}, [10.0, 0.0, 6.0])
        self.assertAlmostEqual(x, -560.0, places=6)
        self.assertAlmostEqual(y, -390.0, places=6)
        self.assertAlmostEqual(z, 3.0, places=6)

    def test_fab_cherry_crown_lands_on_the_crown_point(self):
        # a track F style tree: pivot shifted so the bounds centre is the crown point
        lo, hi = [-61.06, -311.05, -0.04], [1073.06, 220.31, 934.38]
        fab = {"SM_EnvFab_SakuraTwisted": (lo, hi)}
        s, yaw, crown = 0.2, 270.0, (-660.0, -170.0)
        cx, cy = (lo[0] + hi[0]) / 2 * s, (lo[1] + hi[1]) / 2 * s
        a = math.radians(yaw)
        px = crown[0] - (cx * math.cos(a) - cy * math.sin(a))
        py = crown[1] - (cx * math.sin(a) + cy * math.cos(a))
        prop = {"id": "cherry-w", "mesh": "/Game/EnvKit/Fab/Marmoreal/SM_EnvFab_SakuraTwisted",
                "loc": [px, py, -3.0], "yawDeg": yaw, "scale": s}
        off = GEN.crown_offset(prop, fab)
        x, y, z = GEN.board_xy(prop, off)
        self.assertAlmostEqual(x, crown[0], places=4)
        self.assertAlmostEqual(y, crown[1], places=4)
        self.assertAlmostEqual(z, -3.0 + (lo[2] + GEN.CROWN_Z_FRAC * (hi[2] - lo[2])) * s, places=4)

    def test_rule_violations_are_reported(self):
        lay = copy.deepcopy(self.layouts["sarpedon"])
        fx = GEN.build("sarpedon", lay, self.anchors, self.fab)
        on_map = copy.deepcopy(fx[-1])
        on_map.update(id="x-map", loc=[0.0, -330.0, 30.0])  # the 80 uu disc reaches the far map edge
        near = copy.deepcopy(fx[-1])
        near.update(id="x-near", loc=[0.0, 400.0, 30.0], user={"Sphere Radius": 10.0})
        noai = copy.deepcopy(fx[-1])
        noai.update(id="x-noai", user={"Note": "Megaplant_Library"})
        ghost = copy.deepcopy(fx[0])
        ghost.update(id="x-ghost", anchor="no-such-prop")
        pack = copy.deepcopy(fx[0])
        pack.update(id="x-pack", system="/Game/Stylish_Fire_VFX/Niagara/NS_Stylish_Fire_2")
        err, _, _ = GEN.check_fx("sarpedon", lay, fx + [on_map, near, noai, ghost, pack, copy.deepcopy(fx[0])])
        joined = " | ".join(err)
        for needle in ("x-map: spawn disc", "x-near: in the near band", "x-noai: references a NoAI",
                       "x-ghost: anchor no-such-prop", "x-pack: system", "duplicate fx id"):
            self.assertIn(needle, joined)
        heavy = [dict(copy.deepcopy(fx[0]), id=f"h{i}") for i in range(30)]
        err, _, _ = GEN.check_fx("sarpedon", lay, heavy)
        self.assertTrue(any("particles >" in e for e in err))

    def test_main_writes_scratch_and_check_passes_on_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(GEN.main(["--out", tmp]), 0)
            self.assertEqual(GEN.main(["--check", "--layouts", tmp]), 0)
            for key in ("marmoreal", "sarpedon"):
                self.assertIn("fx", load(Path(tmp) / f"{key}.layout.json"))


if __name__ == "__main__":
    unittest.main()
