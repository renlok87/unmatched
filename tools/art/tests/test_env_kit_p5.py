"""ENV-MAPS P5 track A: the 7 Tripo P5 props (run 20261001-tripo-h31-p5), their looks, their UE import plan (with the
Blender back wall ASSET-ENV-M-BACKWALL-001) and their placement in the two env layouts (props only).

CPU only, no UE / Blender: the committed build report and exports, env_prop_look.py (numpy mirror of M_EnvProp),
ue_import_env_kit.py in --check mode, layout_check.py and the layout generator p5_layout_props.py.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import unittest
from argparse import Namespace
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ENV_KIT = HERE.parents[0] / "env_kit"
sys.path.insert(0, str(ENV_KIT))

import env_prop_look as LOOK  # noqa: E402
import layout_check as LC  # noqa: E402
import ue_import_env_kit as IMP  # noqa: E402

RUN = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5"
BACKWALL = REPO / "art/pipeline-candidates/ASSET-ENV-M-BACKWALL-001/20261001-backwall-v1"
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
TOPO = REPO / "backend/prisma/fixtures/boards"
P5 = {"ENV-S-BARREL": "Barrel", "ENV-S-CRATE-STACK": "CrateStack", "ENV-S-LANTERN-POST": "LanternPost",
      "ENV-S-BANNER": "Banner", "ENV-S-ROCK-OUTCROP": "RockOutcrop", "ENV-M-BALUSTRADE": "Balustrade",
      "ENV-M-HEDGE-BED": "HedgeBed"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def layout(key: str) -> dict:
    return load(LAYOUTS / f"{key}.layout.json")


def spaces(key: str) -> list:
    return LC.load_spaces(load(TOPO / f"{key}.topology.json"))


def generator():
    spec = importlib.util.spec_from_file_location("p5_layout_props", RUN / "scripts/p5_layout_props.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


LC.kit_crosscheck(LC.BUILD_REPORTS)


class BuildReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rep = load(RUN / "reports/build-report.json")
        cls.params = load(RUN / "scripts/env-kit-params.json")

    def test_seven_props_no_cherry_v2(self):  # ENV-U13: the cherry v2 is not processed
        self.assertEqual(set(self.rep["assets"]), set(P5))
        self.assertEqual(set(self.params["assets"]), set(P5))
        self.assertNotIn("ENV-M-CHERRY-V2", json.dumps(self.params["assets"]))
        self.assertTrue(self.rep["totals"]["checks_passed"])

    def test_targets_and_contract(self):
        for aid, name in P5.items():
            a = self.rep["assets"][aid]
            self.assertTrue(a["checks_passed"], aid)
            self.assertEqual(a["ue"]["mesh"], f"SM_Env_{name}")
            t = a["target"]
            d = a["readback"]["dimensions_uu_ue"]
            got = d["Z_height"] if t["dimension"] == "height" else max(d["X_depth_front_back"], d["Y_width"])
            self.assertAlmostEqual(got, t["uu"], delta=0.01 * t["uu"], msg=aid)
            self.assertLessEqual(a["readback"]["triangles"], self.params["max_triangles"])
            self.assertEqual(a["readback"]["materials"], [f"M_Env_{name}"])
            self.assertEqual(a["yaw_applied_deg"], 0.0)  # every P5 prop kept the Tripo front

    def test_task_sizes(self):  # the P5 proposal: barrel ~28, crate ~45, lantern ~95, banner ~120, rock 60-90, ...
        dims = {self.rep["assets"][aid]["ue"]["mesh"][7:]: self.rep["assets"][aid]["readback"]["dimensions_uu_ue"]
                for aid in P5}
        self.assertTrue(60 <= dims["RockOutcrop"]["Z_height"] <= 90 and 60 <= dims["RockOutcrop"]["Y_width"] <= 90)
        self.assertAlmostEqual(dims["Balustrade"]["Y_width"], 150.0, delta=1.5)
        self.assertAlmostEqual(dims["Balustrade"]["Z_height"], 45.0, delta=2.0)
        self.assertAlmostEqual(dims["HedgeBed"]["Y_width"], 150.0, delta=1.5)
        self.assertLess(dims["HedgeBed"]["Z_height"], 50.0)

    def test_no_flipped_normals(self):  # the P1 kit had inward faces on several props: P5 measured by ray escape
        for aid in P5:
            g = self.rep["assets"][aid]["geometry"]
            self.assertLess(g["ray_escape_area_fraction"]["inward"], 0.005, aid)
            self.assertEqual(g["shells_inverted_closed"], 0, aid)

    def test_export_hashes(self):
        for aid in P5:
            a = self.rep["assets"][aid]
            self.assertEqual(sha(REPO / a["fbx"]["path"]), a["fbx"]["sha256"], aid)
            for key, t in a["textures"].items():
                self.assertEqual(sha(REPO / t["path"]), t["sha256"], f"{aid} {key}")


class Looks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = LOOK.load_look(LOOK.LOOK_P5)
        cls.res = {n: LOOK.measure(n, cls.data, RUN) for n in cls.data["props"]}

    def test_every_p5_prop_and_the_back_wall_on_m_envprop(self):
        self.assertEqual(set(self.data["props"]), set(P5.values()) | {"BackWall"})
        self.assertEqual(LOOK.validate_look(self.data), [])
        self.assertTrue((REPO / self.data["props"]["BackWall"]["bc"]).is_file())

    def test_targets(self):
        for name, res in self.res.items():
            self.assertEqual(LOOK.check_targets(name, self.data, res), [], name)

    def test_emissive_only_lantern_glass_and_windows(self):
        lit = {n for n, r in self.res.items() if (r.get("emissive") or {}).get("meanLuminance", 0) > 0}
        self.assertEqual(lit, {"LanternPost", "BackWall"})
        p4 = LOOK.load_look()
        plinth = LOOK.measure("LanternPlinth", p4)["emissive"]["meanLuminance"]
        # the lantern glass: the order of the P4 LanternPlinth (x6); the back-wall windows a step below it (P5b tune:
        # at the lantern order their large area clipped to flat orange in the UE frames; P5c tune: x1.2 - the K1 top
        # band 113.8 -> 96 vs P4 91.9, the windows no longer clip: ~0.3 of the plinth glass)
        self.assertLess(abs(self.res["LanternPost"]["emissive"]["meanLuminance"] / plinth - 1.0), 0.25)
        ratio = self.res["BackWall"]["emissive"]["meanLuminance"] / plinth
        self.assertTrue(0.25 <= ratio <= 1.0, ratio)

    def test_night_friendly_rest(self):  # no prop gets brighter or more saturated
        for name, res in self.res.items():
            rest = res["rest"]
            self.assertLessEqual(rest["valRatio"], 1.005, name)
            self.assertLessEqual(rest["satRatio"], 1.005, name)

    def test_back_wall_window_matches_the_glow_mask(self):
        from PIL import Image
        bc = np.asarray(Image.open(LOOK.bc_path("BackWall", RUN, self.data)).convert("RGB"), np.float32) / 255.0
        e = Image.open(BACKWALL / "export/T_Env_BackWall_E.png").convert("L").resize(bc.shape[:2][::-1], Image.NEAREST)
        glow = np.asarray(e) > 127
        we = LOOK.apply_look(bc, LOOK.mi_params(self.data, "BackWall"))["we"]
        self.assertGreater(float((we[glow] > 0.5).mean()), 0.95)
        self.assertLess(float((we[~glow] > 0.05).mean()), 0.001)

    def test_cli_checks_every_look_file(self):
        self.assertEqual(LOOK.main(["--check"]), 0)


class Importer(unittest.TestCase):
    def test_kit_and_runs(self):
        for name in P5.values():
            self.assertIn(name, IMP.KIT)
            self.assertEqual(IMP.run_of(name), IMP.RUN_P5)
        self.assertNotIn("Cherry_V2", IMP.KIT)
        for name in IMP.BACKWALL_NAMES:
            self.assertEqual(IMP.KIT[name][0], "Marmoreal")
            paths = IMP.asset_paths(name)
            self.assertEqual(paths["mi"], "/Game/EnvKit/Marmoreal/MI_Env_BackWall")
            self.assertEqual(sorted(k for k in paths if k.startswith("tex:")), ["tex:BC", "tex:E", "tex:N", "tex:ORM"])
            self.assertEqual(paths["mesh"], f"/Game/EnvKit/Marmoreal/SM_Env_{name}")

    def test_two_sided(self):
        self.assertIn("Banner", IMP.TWO_SIDED)  # cloth
        self.assertTrue({"Cypress", "Rope", "Tree", "Cherry", "Urn"} <= IMP.TWO_SIDED)  # P1 set unchanged

    def test_backwall_report_adapted_and_verified(self):
        rep = IMP.load_build_report(IMP.RUN_BACKWALL)
        for name in IMP.BACKWALL_NAMES:
            plan = IMP.plan_prop(name, IMP.RUN_BACKWALL, rep)
            self.assertTrue(plan["ok"] and plan["verified"], name)
            self.assertEqual({v["status"] for v in plan["sources"].values()}, {"verified"})
            self.assertEqual(plan["target"]["source"], "build-report")
        self.assertEqual(IMP.plan_prop("BackWall_Centre", IMP.RUN_BACKWALL, rep)["target"]["uu"], 255.0)

    def test_check_mode_all_props(self):
        self.assertEqual(IMP.main(["--check"]), 0)

    def test_looks_merged_per_run(self):
        names = list(IMP.KIT)
        plans = {n: IMP.plan_prop(n, IMP.run_of(n), IMP.load_build_report(IMP.run_of(n))) for n in names}
        info, ok = IMP.attach_look(plans, None, Namespace(no_look=False, look=None))
        self.assertTrue(ok and info["used"])
        self.assertEqual(len(info["files"]), 2)
        p4 = set(LOOK.load_look()["props"])
        p5 = set(LOOK.load_look(LOOK.LOOK_P5)["props"])
        want = {n for n in names if IMP.material_of(n) in p4 | p5}
        self.assertEqual({n for n, p in plans.items() if p.get("look")}, want)
        self.assertEqual(plans["BackWall_Centre"]["look"], LOOK.mi_params(LOOK.load_look(LOOK.LOOK_P5), "BackWall"))
        self.assertNotIn("look", plans["Hull"])

    def test_partial_import_finds_the_shared_look(self):
        # P5b tune: --names BackWall_* alone (the back-wall run has no look file) still gets the P5 'BackWall' entry -
        # before, a partial import reported "no look file" and put MI_Env_BackWall back on M_UM_Figure
        names = ["BackWall_BayDoor", "BackWall_BayWindows", "BackWall_Centre"]
        plans = {n: IMP.plan_prop(n, IMP.run_of(n), IMP.load_build_report(IMP.run_of(n))) for n in names}
        info, ok = IMP.attach_look(plans, None, Namespace(no_look=False, look=None))
        self.assertTrue(ok and info["used"])
        self.assertEqual(info["selected"], names)
        for n in names:
            self.assertEqual(plans[n]["look"], LOOK.mi_params(LOOK.load_look(LOOK.LOOK_P5), "BackWall"))

    def test_look_entry_in_two_files_fails(self):
        import tempfile
        plans = {n: IMP.plan_prop(n, IMP.run_of(n), IMP.load_build_report(IMP.run_of(n))) for n in ("Barrel", "Hull")}
        plans["Hull"]["run"] = plans["Barrel"]["run"]
        info, ok = IMP.attach_look(plans, IMP.RUN_P5, Namespace(no_look=False, look=None))
        self.assertTrue(ok)  # the same file reached twice is one file
        self.assertEqual(len(info["files"]), 1)
        text = (RUN / "scripts/env-prop-look.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            for i, name in enumerate(("Barrel", "Hull")):
                d = Path(tmp) / f"run{i}" / "scripts"
                d.mkdir(parents=True)
                (d / "env-prop-look.json").write_text(text, encoding="utf-8")
                plans[name]["run"] = str(d.parent)  # absolute: REPO / <abs> is the absolute path
            info, ok = IMP.attach_look(plans, None, Namespace(no_look=False, look=None))
        self.assertFalse(ok)
        self.assertIn("in two look files", info["error"])


class Layouts(unittest.TestCase):
    def _check(self, key):
        lay = layout(key)
        sp = spaces(key)
        err, warn, info = LC.validate(lay, key, sp)
        self.assertTrue(info["parsed"])
        return lay, sp, [e for e in err if not e.startswith("ground:")], warn

    def _new(self, lay, names):
        return [p for p in lay["props"] if LC.mesh_name(p) in names]

    def test_marmoreal(self):
        lay, sp, err, warn = self._check("marmoreal")
        self.assertEqual(err, [])
        self.assertFalse([w for w in warn if "rocky lip" in w or "guide" in w])
        bw = load(BACKWALL / "reports/backwall-layout.json")["props"]
        got = {p["id"]: p for p in self._new(lay, IMP.BACKWALL_NAMES)}
        self.assertEqual(set(got), {p["id"] for p in bw})
        for p in bw:
            self.assertEqual(got[p["id"]]["mesh"], p["mesh"])
            self.assertEqual(got[p["id"]]["loc"], p["loc"])
        bal = self._new(lay, {"Balustrade"})
        self.assertEqual(len(bal), 12)
        self.assertEqual(sum(abs(p["loc"][0]) > 740 for p in bal), 10)  # W / E runs on the tray edges
        self.assertTrue(all(p["loc"][1] > LC.FRAME_HY for p in bal if abs(p["loc"][0]) < 740))  # near corners
        self.assertTrue(2 <= len(self._new(lay, {"HedgeBed"})) <= 3)

    def test_sarpedon(self):
        lay, sp, err, warn = self._check("sarpedon")
        self.assertEqual(err, [])
        self.assertFalse([w for w in warn if "rocky lip" in w or "guide" in w])
        deck = self._new(lay, {"Barrel", "CrateStack"})
        self.assertTrue(6 <= len(deck) <= 10)
        self.assertTrue(all(p["loc"][0] > LC.FRAME_HX for p in deck))  # east: hull / cannon deck
        self.assertTrue(2 <= len(self._new(lay, {"LanternPost"})) <= 3)
        self.assertTrue(1 <= len(self._new(lay, {"Banner"})) <= 2)
        rocks = self._new(lay, {"RockOutcrop"})
        self.assertTrue(3 <= len(rocks) <= 5)
        self.assertGreaterEqual(sum(p["loc"][0] < -LC.FRAME_HX - 100 for p in rocks), 3)  # west forest

    def test_lights_and_ground_unchanged_and_no_cherry_v2(self):
        for key in ("marmoreal", "sarpedon"):
            lay = layout(key)
            self.assertEqual(len(lay["lights"]), 5, key)  # emissive only: + 1 profile point = 6, + the key
            self.assertNotIn("Cherry_V2", json.dumps(lay["props"]))
            self.assertTrue(LC.PROPS_RANGE[0] <= len(lay["props"]) <= LC.PROPS_RANGE[1])

    def test_new_props_clear_every_circle(self):  # check 6 (all cameras) and 7 on the new props of both maps
        new = set(P5.values()) | set(IMP.BACKWALL_NAMES)
        for key in ("marmoreal", "sarpedon"):
            lay = layout(key)
            sub = dict(lay, props=[p for p in lay["props"] if LC.mesh_name(p) in new])
            sp = spaces(key)
            for pid, w in LC.occlusion(sub, sp).items():
                self.assertGreaterEqual(w["px"], LC.MARGIN_PX, f"{key} {pid}")
            for pid, s in LC.shadows(sub, sp).items():
                self.assertGreaterEqual(s["uu"], 0.0, f"{key} {pid}")

    def test_generator_is_idempotent_and_props_only(self):
        gen = generator()
        self.assertEqual(gen.main(["--check"]), 0)
        for key in ("marmoreal", "sarpedon"):
            lay = layout(key)
            out = gen.apply(key, lay)
            self.assertEqual({k: v for k, v in out.items() if k not in ("props", "notes")},
                             {k: v for k, v in lay.items() if k not in ("props", "notes")})
            self.assertEqual(out, lay)

    def test_back_wall_pivot_offset(self):
        p = {"id": "c", "mesh": "/Game/EnvKit/Marmoreal/SM_Env_BackWall_Centre", "loc": [0.0, -465.866, -3.0],
             "yawDeg": 90.0, "scale": 1.0}
        fp = LC.footprint(p)
        # yaw 90: local +X (front) -> +Y; bounds x -16 .. +9.345 -> y -481.866 .. -456.521
        self.assertAlmostEqual(float(fp[:, 1].min()), -481.866, places=2)
        self.assertAlmostEqual(float(fp[:, 1].max()), -456.521, places=2)
        self.assertAlmostEqual(float(fp[:, 0].max()), 93.0, places=2)


if __name__ == "__main__":
    unittest.main()
