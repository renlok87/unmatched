"""Контракт движения значков v3 (docs/unreal/contracts/hud/icon-motion.json): схема, копия для UE, текстуры слоёв,
детерминизм эталонных поз. Генераторы — art/imagegen/hud-icons-v3/_tools/{motion_contract,icon_motion}.py."""
import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TOOLS = REPO / "art" / "imagegen" / "hud-icons-v3" / "_tools"
sys.path.insert(0, str(TOOLS))
import icon_motion as M  # noqa: E402

CONTRACT = REPO / "docs" / "unreal" / "contracts" / "hud" / "icon-motion.json"
CONFIG = REPO / "unreal" / "Unmatched" / "Config" / "S08IconMotion.json"
GOLDEN = REPO / "docs" / "unreal" / "contracts" / "hud" / "icon-motion-golden.json"
ICONS_V3 = REPO / "art" / "imagegen" / "hud-icons-v3"
UE_SIZES = (24, 32, 48, 64)


class IconMotionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = M.load_contract(str(CONTRACT))

    def test_config_copy_is_identical(self):
        self.assertEqual(CONTRACT.read_bytes(), CONFIG.read_bytes(), "запустить motion_contract.py: копия в Config/ устарела")

    def test_all_23_icons_with_appear_and_leave(self):
        self.assertEqual(len(self.c["order"]), 23)
        self.assertEqual(set(self.c["order"]), set(self.c["icons"]))
        for icon, d in self.c["icons"].items():
            self.assertIn("appear", d["anims"], icon)
            self.assertIn("leave", d["anims"], icon)
            self.assertEqual(d["anims"]["appear"]["kind"], "enter", icon)
            self.assertEqual(d["anims"]["leave"]["kind"], "exit", icon)

    def test_tracks_are_well_formed(self):
        eases = set(self.c["eases"])
        props = set(self.c["props"])
        for icon, d in self.c["icons"].items():
            targets = {"all"} | {l["id"] for l in d["layers"]}
            for name, a in d["anims"].items():
                for branch in (a, a.get("reduced") or {"tracks": [], "duration_ms": 0}):
                    self.assertGreaterEqual(branch["duration_ms"], 0, (icon, name))
                    for tr in branch["tracks"]:
                        self.assertIn(tr["target"], targets, (icon, name))
                        self.assertIn(tr["prop"], props, (icon, name))
                        ts = [k[0] for k in tr["keys"]]
                        self.assertEqual(ts, sorted(ts), (icon, name, tr["prop"]))
                        self.assertLessEqual(ts[-1], branch["duration_ms"] + 1e-6, (icon, name, tr["prop"]))
                        for k in tr["keys"]:
                            self.assertIn(k[2], eases, (icon, name))
                # null = «значение на старте команды»: имеет смысл у событий и ухода; у появления и цикла начального
                # состояния нет — там только числа
                if a["kind"] in ("enter", "loop"):
                    for tr in a["tracks"]:
                        self.assertNotIn(None, [k[1] for k in tr["keys"]], (icon, name))

    def test_reduced_motion_is_opacity_only_and_short(self):
        """UI-ACC-005/006: в ветке reduced только opacity ≤ 100 мс (спиннер — ступени поворота, индикатор прогресса)."""
        for icon, d in self.c["icons"].items():
            for name, a in d["anims"].items():
                red = a.get("reduced")
                self.assertIsNotNone(red, (icon, name))
                if icon == "loader-spinner" and name == "cycle":
                    continue
                for tr in red["tracks"]:
                    self.assertEqual(tr["prop"], "opacity", (icon, name))
                self.assertLessEqual(red["duration_ms"], 100, (icon, name))

    def test_layer_textures_exist_for_ue_sizes(self):
        for icon, d in self.c["icons"].items():
            for l in d["layers"]:
                names = [l["src"]]
                if l["src"].endswith("#"):
                    names = [f"{l['src'][:-1]}_f{i:02d}" for i in range(l["frames"])]
                for n in names:
                    sub = "layers" if "_" in n else "sizes"
                    for s in UE_SIZES:
                        self.assertTrue((ICONS_V3 / sub / f"{n}-{s}.png").exists(), f"{sub}/{n}-{s}.png")

    def test_golden_is_current_and_deterministic(self):
        stored = json.loads(GOLDEN.read_text(encoding="utf-8"))
        fresh = json.loads(json.dumps(M.golden(self.c), separators=(",", ":")))
        self.assertEqual(stored["contract_revision"], self.c["revision"])
        self.assertEqual(stored, fresh, "запустить icon_motion.py --golden: эталонные позы устарели")

    def test_appear_ends_at_master_pose(self):
        """Последний кадр появления = мастер (поза покоя), первый кадр не пустой (opacity > 0)."""
        for icon in self.c["order"]:
            a = M.Animator(self.c, icon)
            a.play("appear", 0)
            dur = self.c["icons"][icon]["anims"]["appear"]["duration_ms"]
            pp, vis = a.pose(0)
            self.assertTrue(vis, icon)
            self.assertGreater(pp["pose"]["all"]["opacity"], 0.0, icon)
            end, _ = a.pose(dur + 1)
            for tgt, pose in end["pose"].items():
                for p in ("scale", "scale_x", "scale_y", "tx", "ty", "rotate"):
                    if icon in ("loader-spinner",) and p == "rotate":
                        continue
                    if "cycle" in self.c["icons"][icon]["anims"]:
                        continue
                    self.assertAlmostEqual(pose[p], M.REST[p] if tgt == "all" else a.rest[tgt][p], 6, (icon, tgt, p))


class IconMotionSemanticsTests(unittest.TestCase):
    """Ревью 2026-10-03: события поверх базы. Те же случаи проверяет UE-тест Unmatched.S08.IconMotion.Semantics."""

    @classmethod
    def setUpClass(cls):
        cls.c = M.load_contract(str(CONTRACT))

    def pose(self, a, t):
        pp, vis = a.pose(t)
        return pp["pose"], vis

    def test_leave_after_hold_fades(self):
        a = M.Animator(self.c, "action-attack")
        a.play("appear", 0)
        a.play("hover_in", 300)
        a.play("spend", 500)
        a.play("leave", 1000)
        p, vis = self.pose(a, 1060)
        self.assertTrue(vis)
        self.assertLess(p["all"]["opacity"], 0.4)       # от 0,4 (spend) к 0
        self.assertLess(p["all"]["scale"], 1.06)        # от 1,06 (hover) к 0,92
        self.assertFalse(self.pose(a, 1121)[1])

    def test_tap_after_hover_returns_to_hover(self):
        a = M.Animator(self.c, "action-attack")
        a.play("appear", 0)
        a.play("hover_in", 300)
        a.play("tap", 600)
        self.assertAlmostEqual(self.pose(a, 600)[0]["all"]["scale"], 1.06, 4)   # без скачка в первый кадр
        self.assertAlmostEqual(self.pose(a, 650)[0]["all"]["scale"], 0.94, 4)
        self.assertAlmostEqual(self.pose(a, 800)[0]["all"]["scale"], 1.06, 4)

    def test_future_appear_is_invisible(self):
        a = M.Animator(self.c, "state-hint")
        a.play("appear", 120)
        self.assertFalse(self.pose(a, 60)[1])
        self.assertTrue(self.pose(a, 120)[1])

    def test_equal_time_later_command_wins(self):
        a = M.Animator(self.c, "action-attack")
        a.play("appear", 0)
        a.play("release", 500)
        a.play("hover_out", 500)
        self.assertAlmostEqual(self.pose(a, 700)[0]["all"]["scale"], 1.0, 4)


if __name__ == "__main__":
    unittest.main()
