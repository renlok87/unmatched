"""Тесты review/rider_gap.py — зазор «наездника» (пилот 2026-10-14: F137 ворона Leshen висела 2,9 см в rest; F133 жёсткая
деталь отрывается от деформируемой руки в клипе).

1. Чистые функции (без Blender): разбор пар, пары профиля, опора auto, число оборотов, сводка клипа, вердикты.
2. Blender 5.2 headless, сквозной прогон на синтетике (как кандидат: host CLI → blender -b): тело-куб, деталь A сидит
   на нём с зазором 0,5 мм (prepare.part_offsets_m профиля → пара с опорой auto), в клипе кость детали поднимает её на
   5 мм (кадры 2–4) — FAIL только в клипе; деталь B жёсткая и висит в 10 мм над телом — FAIL скана.
   Пропуск, если Blender не установлен или TRIPO_PIPELINE_SKIP_BLENDER=1.

    python -m pytest tools/tripo-pipeline/tests/test_rider_gap.py -q -p no:cacheprovider
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

REVIEW = Path(__file__).resolve().parents[1] / "review"
sys.path.insert(0, str(REVIEW))
spec = importlib.util.spec_from_file_location("rider_gap", REVIEW / "rider_gap.py")
rg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rg)

BLENDER = os.environ.get("TRIPO_PIPELINE_BLENDER") or rg.DEFAULT_BLENDER
SKIP = os.environ.get("TRIPO_PIPELINE_SKIP_BLENDER") == "1" or not Path(BLENDER).is_file()
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

CUBE_V = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]], float)
CUBE_F = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]  # наружу


class PureTests(unittest.TestCase):
    def test_part_name_and_pair(self):
        self.assertEqual(rg.part_name("8"), "tripo_part_8")
        self.assertEqual(rg.part_name("tripo_part_12"), "tripo_part_12")
        p = rg.parse_pair("crow_R=8:6+tripo_part_12")
        self.assertEqual((p["name"], p["rider"], p["perch"], p["source"]),
                         ("crow_R", ["tripo_part_8"], ["tripo_part_6", "tripo_part_12"], "cli"))
        p = rg.parse_pair("8")
        self.assertEqual((p["name"], p["perch"]), ("tripo_part_8", None))
        self.assertIsNone(rg.parse_pair("8:auto")["perch"])
        for bad in ("=8", "crow R=8", "8:8", ":6", "8:a b"):
            with self.assertRaises(ValueError, msg=bad):
                rg.parse_pair(bad)

    def test_profile_pairs_and_merge(self):
        prof = {"prepare": {"part_offsets_m": {"tripo_part_10": [0, 0, 0.01], "tripo_part_8": [0, 0.04, 0.01]}},
                "parts": {"tripo_part_1": {"mesh": "base"}, "tripo_part_8": {"mesh": "body", "role": "ворона"}},
                "rig": {"weights": {"tripo_part_1": {"kind": "rigid", "bone": "root"},
                                    "tripo_part_8": {"kind": "rigid", "bone": "arm_lower.R"},
                                    "tripo_part_6": {"kind": "chain", "chain": ["spine"]}}}}
        pp = rg.profile_pairs(prof)
        self.assertEqual([p["rider"] for p in pp], [["tripo_part_8"], ["tripo_part_10"]])  # по номеру части
        merged = rg.merge_pairs([rg.parse_pair("crow=8:6")], pp)
        self.assertEqual([(p["name"], p["perch"]) for p in merged], [("crow", ["tripo_part_6"]), ("tripo_part_10", None)])
        self.assertEqual(rg.profile_pairs({"prepare": {"note": "x"}}), [])
        self.assertEqual(rg.rigid_parts(prof), {"tripo_part_8": "arm_lower.R"})  # подставка не в скане
        self.assertEqual(rg.base_parts(prof), ["tripo_part_1"])
        with self.assertRaises(ValueError):
            rg.merge_pairs([rg.parse_pair("a=8"), rg.parse_pair("a=9")], [])

    def test_auto_perch_margin(self):
        # Leshen r2: кисть 29,0 мм, предплечье 29,7, запястье 31, ствол 47,9 → опора — кисть, предплечье, запястье
        d = {"tripo_part_5": 0.0290, "tripo_part_6": 0.0297, "tripo_part_12": 0.031, "tripo_part_0": 0.0479,
             "tripo_part_9": None}
        self.assertEqual(rg.auto_perch(d), ["tripo_part_5", "tripo_part_6", "tripo_part_12"])
        self.assertEqual(rg.auto_perch({"a": 0.0016, "b": 0.0216}), ["a"])
        self.assertEqual(rg.auto_perch({}), [])

    def test_winding_number_closed_and_open(self):
        tris = CUBE_V[np.array(rg.fan_triangles(CUBE_F))]
        self.assertAlmostEqual(rg.winding_number((0.5, 0.5, 0.5), tris), 1.0, places=9)
        self.assertAlmostEqual(rg.winding_number((1.5, 0.5, 0.5), tris), 0.0, places=9)
        self.assertAlmostEqual(rg.winding_number((0.5, 0.5, 0.999), tris), 1.0, places=6)
        w = rg.winding_numbers([(0.5, 0.5, 0.5), (2, 2, 2)], tris, chunk_elems=5)  # куски по 1 точке
        self.assertTrue(np.allclose(w, [1.0, 0.0]))
        open_tris = CUBE_V[np.array(rg.fan_triangles(CUBE_F[1:]))]  # без дна: открытая петля стыка
        self.assertGreater(rg.winding_number((0.5, 0.5, 0.5), open_tris), 0.5)   # внутри — всё ещё внутри
        self.assertLess(rg.winding_number((0.5, 0.5, -0.2), open_tris), 0.5)     # под дырой — снаружи

    def test_compact_frames(self):
        self.assertEqual(rg.compact_frames([0, 1, 2, 5, 7, 8]), "0–2, 5, 7–8")
        self.assertEqual(rg.compact_frames([]), "")

    def _pair(self, rest, rows):
        return {"rest": rest, "clips": {"HitReact": {"rows": rows, "summary": rg.clip_summary(rows)}}}

    def test_verdict_rest_pass_clip_lift_fails(self):
        """F133: в rest сидит (1,6 мм), в клипе к. 3–4 отрывается до 4 мм → FAIL с кадрами."""
        rows = [{"f": f, "gap_m": g, "pen_m": 0.0, "others_pen_m": 0.0}
                for f, g in enumerate([0.0016, 0.0016, 0.0019, 0.003, 0.004, 0.0016])]
        s = rg.clip_summary(rows)
        self.assertEqual((s["gap_max_m"], s["gap_max_frame"]), (0.004, 4))
        self.assertAlmostEqual(s["lift_m"], 0.0024)
        v, reasons, warns = rg.pair_verdict(self._pair({"gap_m": 0.0016, "pen_m": 0.0}, rows), 0.002, 0.002)
        self.assertEqual(v, "FAIL")
        self.assertEqual(len(reasons), 1)
        self.assertIn("к. 3–4", reasons[0])
        self.assertIn("худший к. 4", reasons[0])
        self.assertEqual(warns, [])

    def test_verdict_rest_gap_and_pen_and_others_warn(self):
        v, reasons, _ = rg.pair_verdict({"rest": {"gap_m": 0.029, "pen_m": 0.0}}, 0.002, 0.002)
        self.assertEqual(v, "FAIL")
        self.assertIn("29.00", reasons[0])
        v, reasons, _ = rg.pair_verdict({"rest": {"gap_m": 0.0, "pen_m": 0.0025}}, 0.002, 0.002)
        self.assertEqual(v, "FAIL")
        self.assertIn("проникновение", reasons[0])
        rows = [{"f": 0, "gap_m": 0.0, "pen_m": 0.0015, "others_pen_m": 0.0094}]
        v, reasons, warns = rg.pair_verdict(self._pair({"gap_m": 0.0, "pen_m": 0.0015, "others_pen_m": 0.0}, rows),
                                            0.002, 0.002)
        self.assertEqual((v, reasons), ("PASS", []))
        self.assertEqual(len(warns), 1)  # когти в детали — столкновение клипа, не гейт посадки
        v, reasons, _ = rg.pair_verdict({"rest": {"gap_m": None, "pen_m": None}}, 0.002, 0.002)
        self.assertEqual(v, "FAIL")

    def test_scan_verdict(self):
        self.assertEqual(rg.scan_verdict({"part": "p", "gap_m": 0.0015}, 0.002, set()), "PASS")
        lifted = {"part": "p", "gap_m": 0.0015, "clips": {"HitReact": {"gap_max_m": 0.004}}}
        self.assertEqual(rg.scan_verdict(lifted, 0.002, set()), "FAIL")  # F133: сидит в rest, отрывается в клипе
        self.assertEqual(rg.scan_verdict(lifted, 0.002, {"p"}), "FLOAT_OK")
        self.assertEqual(rg.scan_verdict({"part": "p", "gap_m": 0.029, "embedded": False}, 0.002, set()), "FAIL")
        self.assertEqual(rg.scan_verdict({"part": "p", "gap_m": 0.029, "embedded": True}, 0.002, set()), "EMBEDDED")
        self.assertEqual(rg.scan_verdict({"part": "p", "gap_m": 0.029}, 0.002, {"p"}), "FLOAT_OK")

    def test_build_report(self):
        raw = {"perch": {"crow": ["tripo_part_6"]},
               "rest": {"pairs": {"crow": {"gap_m": 0.0016, "pen_m": 0.0}},
                        "scan": [{"part": "tripo_part_11", "gap_m": 0.0015},
                                 {"part": "tripo_part_10", "gap_m": 0.012, "embedded": False, "nearest_part": "tripo_part_0"}]},
               "clips": {"Idle": {"rows": {"crow": [{"f": 0, "gap_m": 0.0016, "pen_m": 0.0}]}}}, "warnings": []}
        pairs = [rg.parse_pair("crow=8")]
        rep = rg.build_report(raw, {}, pairs, {"tripo_part_10": "ворона плеча"}, 0.002, 0.002, set())
        self.assertEqual(rep["schema"], rg.SCHEMA)
        self.assertEqual(rep["pairs"][0]["verdict"], "PASS")
        self.assertEqual(rep["pairs"][0]["perch_source"], "auto")
        self.assertEqual(rep["pairs"][0]["clips"]["Idle"]["summary"]["gap_max_m"], 0.0016)
        self.assertEqual([s["verdict"] for s in rep["scan"]], ["PASS", "FAIL"])
        self.assertEqual(rep["verdict"], "FAIL")
        self.assertIn("ворона плеча", rep["failures"][0])


class BoneGroupAndDesignedGapTests(unittest.TestCase):
    """C47 (Beowulf 2026-10-14): скан спаривал щит с его же умбоном (одна кость arm_lower.L), постоянный задуманный
    зазор щита к предплечью (5,6 мм) мог только FAIL."""

    RIGID = {"tripo_part_2": "arm_lower.L", "tripo_part_7": "weapon.R", "tripo_part_17": "weapon.R",
             "tripo_part_18": "arm_lower.L", "tripo_part_6": "head"}

    def test_bone_groups(self):
        g = rg.bone_groups(self.RIGID)
        self.assertEqual(g["tripo_part_18"], ["tripo_part_2", "tripo_part_18"])
        self.assertEqual(g["tripo_part_7"], ["tripo_part_7", "tripo_part_17"])
        self.assertEqual(g["tripo_part_6"], ["tripo_part_6"])

    def test_scan_units_grouped_and_legacy(self):
        units = rg.scan_units(self.RIGID, [])
        self.assertEqual([(u["name"], u["bone"]) for u in units],
                         [("tripo_part_2+tripo_part_18", "arm_lower.L"), ("tripo_part_7+tripo_part_17", "weapon.R"),
                          ("tripo_part_6", "head")])
        # деталь пары (щит без умбона) снимает со скана всю группу кости: умбон не висит «сам по себе»
        units = rg.scan_units(self.RIGID, [rg.parse_pair("shield=2:10")])
        self.assertEqual([u["name"] for u in units], ["tripo_part_7+tripo_part_17", "tripo_part_6"])
        legacy = rg.scan_units(self.RIGID, [rg.parse_pair("shield=2:10")], grouped=False)
        self.assertEqual([u["parts"] for u in legacy],
                         [["tripo_part_7"], ["tripo_part_17"], ["tripo_part_18"], ["tripo_part_6"]])

    def test_parse_designed(self):
        pairs = [rg.parse_pair("shield_arm=2+18:12")]
        self.assertEqual(rg.parse_designed(["shield_arm=5.6"], pairs), {"shield_arm": 0.0056})
        self.assertEqual(rg.parse_designed([], pairs), {})
        for bad in (["shield_arm"], ["nope=5"], ["shield_arm=-1"], ["shield_arm=x"]):
            with self.assertRaises(ValueError, msg=bad):
                rg.parse_designed(bad, pairs)

    def test_designed_gap_verdict(self):
        rows = [{"f": f, "gap_m": g, "pen_m": 0.0} for f, g in enumerate([0.0056, 0.0057, 0.0061, 0.0056])]
        pair = {"rest": {"gap_m": 0.0056, "pen_m": 0.0},
                "clips": {"Idle": {"rows": rows, "summary": rg.clip_summary(rows)}}}
        self.assertEqual(rg.pair_verdict(pair, 0.002, 0.002)[0], "FAIL")  # без задуманного — зазор > 2 мм
        pair["designed_gap_m"] = 0.0056
        self.assertEqual(rg.pair_verdict(pair, 0.002, 0.002), ("PASS", [], []))
        lift = [{"f": 0, "gap_m": 0.0056, "pen_m": 0.0}, {"f": 1, "gap_m": 0.0081, "pen_m": 0.0}]
        pair["clips"] = {"HitReact": {"rows": lift, "summary": rg.clip_summary(lift)}}
        v, reasons, _ = rg.pair_verdict(pair, 0.002, 0.002)
        self.assertEqual(v, "FAIL")
        self.assertIn("вне задуманного 5.60", reasons[0])
        self.assertIn("худший к. 1", reasons[0])
        touch = dict(pair, rest={"gap_m": 0.0, "pen_m": 0.0}, clips={})
        self.assertEqual(rg.pair_verdict(touch, 0.002, 0.002)[0], "FAIL")  # прилип вместо зазора — тоже отход
        self.assertEqual(rg.state_flags({"gap_m": 0.003, "pen_m": 0.0}, 0.002, 0.002),
                         ["зазор 3.00 мм > 2.0"])  # без задуманного — прежнее правило и текст

    def test_group_scan_verdict_and_report(self):
        item = {"part": "tripo_part_2+tripo_part_18", "parts": ["tripo_part_2", "tripo_part_18"], "gap_m": 0.0056,
                "embedded": False, "nearest_part": "tripo_part_12"}
        self.assertEqual(rg.scan_verdict(item, 0.002, set()), "FAIL")
        self.assertEqual(rg.scan_verdict(item, 0.002, {"tripo_part_18"}), "FLOAT_OK")
        raw = {"perch": {"sa": ["tripo_part_12"]},
               "rest": {"pairs": {"sa": {"gap_m": 0.0056, "pen_m": 0.0}}, "scan": [item]},
               "clips": {}, "warnings": []}
        pairs = [dict(rg.parse_pair("sa=7:12"), designed_gap_m=0.0056)]
        rep = rg.build_report(raw, {}, pairs, {"tripo_part_2": "щит", "tripo_part_18": "умбон"}, 0.002, 0.002, set())
        self.assertEqual((rep["pairs"][0]["verdict"], rep["pairs"][0]["designed_gap_m"]), ("PASS", 0.0056))
        self.assertEqual(rep["scan"][0]["role"], "tripo_part_2: щит; tripo_part_18: умбон")
        self.assertIn("tripo_part_2+tripo_part_18", rep["failures"][0])
        plain = rg.build_report(dict(raw, rest={"pairs": raw["rest"]["pairs"], "scan": []}), {},
                                [rg.parse_pair("sa=7:12")], {}, 0.002, 0.002, set())
        self.assertNotIn("designed_gap_m", plain["pairs"][0])  # ключ только у пар с --designed-gap


# ---------------------------------------------------------------------------------------------- Blender

GENERATOR = r'''
import bpy, bmesh, json, os, sys
out = sys.argv[sys.argv.index("--") + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene

def box(name, lo, hi, cuts=0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    if cuts:  # вершины тела рядом с деталью (кости опоры у детали)
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        v.co = [lo[i] + (hi[i] - lo[i]) * (v.co[i] + 0.5) for i in range(3)]
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    o = bpy.data.objects.new(name, me)
    sc.collection.objects.link(o)
    return o

parts = {"tripo_part_0": ((-0.05, -0.05, 0.0), (0.05, 0.05, 0.1)),        # тело
         "tripo_part_1": ((-0.01, -0.01, 0.1005), (0.01, 0.01, 0.12)),    # деталь A: зазор 0,5 мм
         "tripo_part_2": ((-0.01, 0.035, 0.11), (0.01, 0.055, 0.13))}     # деталь B: висит 10 мм
objs = {n: box("LP_" + n, *b, cuts=9 if n == "tripo_part_0" else 0) for n, b in parts.items()}
os.makedirs(os.path.join(out, "work"), exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "work", "lp_uv.blend"))
# скелетный меш: те же коробки, тело и B на root, A — на кости rider
for n, o in objs.items():
    o.name = "SK_" + n
arm_d = bpy.data.armatures.new("Arm")
arm = bpy.data.objects.new("Arm", arm_d)
sc.collection.objects.link(arm)
bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode="EDIT")
r = arm_d.edit_bones.new("root"); r.head = (0, 0, 0); r.tail = (0, 0, 0.08)
# rider — вторая корневая кость: импорт FBX выводит хвост родителя по единственному ребёнку и соединяет кости, а
# смещение соединённой кости не действует
b = arm_d.edit_bones.new("rider"); b.head = (0, 0, 0.1); b.tail = (0, 0, 0.13)
bpy.ops.object.mode_set(mode="OBJECT")
for n, o in objs.items():
    bone = "rider" if n == "tripo_part_1" else "root"
    g = o.vertex_groups.new(name=bone)
    g.add(list(range(len(o.data.vertices))), 1.0, "REPLACE")
    o.parent = arm
    m = o.modifiers.new("Armature", "ARMATURE")
    m.object = arm
os.makedirs(os.path.join(out, "export"), exist_ok=True)
bpy.ops.export_scene.fbx(filepath=os.path.join(out, "export", "SK_Test_H2.fbx"), bake_anim=False,
                         add_leaf_bones=False)
# клип: кость rider поднимает деталь A на 5 мм по +Z мира в кадре 3 (кадры 1..5; ключ в каждом кадре). Поза — матрицей
# в пространстве арматуры: FBX меняет оси костей, смещение по локальной оси кости ушло бы вбок
from mathutils import Matrix
sc.frame_start, sc.frame_end = 1, 5
pb = arm.pose.bones["rider"]
for f, dz in ((1, 0.0), (2, 0.0), (3, 0.005), (4, 0.0), (5, 0.0)):
    sc.frame_set(f)
    pb.matrix = Matrix.Translation((0.0, 0.0, dz)) @ pb.bone.matrix_local
    bpy.context.view_layer.update()
    pb.keyframe_insert("location", frame=f)
bpy.ops.export_scene.fbx(filepath=os.path.join(out, "AM_Test_Lift.fbx"), bake_anim=True, add_leaf_bones=False,
                         bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False, bake_anim_force_startend_keying=True)
print("GEN_OK")
'''


@unittest.skipIf(SKIP, "Blender не найден или TRIPO_PIPELINE_SKIP_BLENDER=1")
class BlenderEndToEnd(unittest.TestCase):
    def test_rest_pass_clip_lift_fail_and_floating_scan(self):
        with tempfile.TemporaryDirectory(prefix="rider-gap-test-") as tmp:
            tmp = Path(tmp)
            run = tmp / "run"
            gen = tmp / "gen.py"
            gen.write_text(GENERATOR, encoding="utf-8")
            r = subprocess.run([BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(gen),
                                "--", str(run)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                               creationflags=NO_WINDOW)
            self.assertIn("GEN_OK", r.stdout, r.stdout[-2000:] + r.stderr[-2000:])
            prof = {"parts": {"tripo_part_0": {"mesh": "body", "role": "тело"},
                              "tripo_part_1": {"mesh": "body", "role": "деталь A"},
                              "tripo_part_2": {"mesh": "body", "role": "деталь B"}},
                    "prepare": {"part_offsets_m": {"tripo_part_1": [0.0, 0.0, 0.001]}},
                    "rig": {"weights": {"tripo_part_1": {"kind": "rigid", "bone": "rider"},
                                        "tripo_part_2": {"kind": "rigid", "bone": "root"}}}}
            (tmp / "profile.json").write_text(json.dumps(prof), encoding="utf-8")
            out = tmp / "rider-gap.json"
            code = rg.main(["--run", str(run), "--profile", str(tmp / "profile.json"),
                            "--clip-fbx", "Lift=%s" % (run / "AM_Test_Lift.fbx"), "--out", str(out),
                            "--blender", BLENDER])
            self.assertEqual(code, 2)
            rep = json.loads(out.read_text(encoding="utf-8"))
            self.assertLess(rep["mapping"]["worst_match_m"], 1e-5)
            (pair,) = rep["pairs"]
            self.assertEqual((pair["name"], pair["perch"], pair["source"]),
                             ("tripo_part_1", ["tripo_part_0"], "profile prepare.part_offsets_m"))
            self.assertAlmostEqual(pair["rest"]["gap_m"], 0.0005, delta=2e-5)
            self.assertEqual(pair["rest"]["pen_m"], 0.0)
            self.assertEqual(pair["rest"]["perch_bones_near_rider"], {"root": 1.0})
            rows = pair["clips"]["Lift"]["rows"]
            self.assertEqual(len(rows), 5)
            gaps = [round(r_["gap_m"], 5) for r_ in rows]
            self.assertAlmostEqual(gaps[0], 0.0005, delta=2e-5)
            self.assertAlmostEqual(max(gaps), 0.0055, delta=1e-4)
            self.assertEqual(pair["clips"]["Lift"]["summary"]["gap_max_frame"], 2)
            self.assertEqual(pair["verdict"], "FAIL")
            self.assertTrue(all(not r_.startswith("rest") for r_ in pair["reasons"]))  # в rest сидит
            scan = {s["part"]: s for s in rep["scan"]}
            self.assertEqual(list(scan), ["tripo_part_2"])  # деталь пары в скан не входит
            self.assertEqual(scan["tripo_part_2"]["verdict"], "FAIL")
            self.assertAlmostEqual(scan["tripo_part_2"]["gap_m"], 0.01, delta=1e-4)
            # --float-ok снимает висящую деталь со скана; без клипа деталь A сидит
            code = rg.main(["--run", str(run), "--profile", str(tmp / "profile.json"), "--no-profile-pairs",
                            "--pair", "A=1:0", "--float-ok", "2", "--out", str(out), "--blender", BLENDER])
            self.assertEqual(code, 0)
            rep = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(rep["scan"][0]["verdict"], "FLOAT_OK")
            self.assertEqual(rep["pairs"][0]["perch_source"], "cli")
            # без пары деталь A идёт в скан: в rest касается, в клипе отрывается — скан ловит F133 сам
            code = rg.main(["--run", str(run), "--profile", str(tmp / "profile.json"), "--no-profile-pairs",
                            "--float-ok", "2", "--clip-fbx", "Lift=%s" % (run / "AM_Test_Lift.fbx"),
                            "--out", str(out), "--blender", BLENDER])
            self.assertEqual(code, 2)
            rep = json.loads(out.read_text(encoding="utf-8"))
            scan = {s["part"]: s for s in rep["scan"]}
            a = scan["tripo_part_1"]
            self.assertEqual((a["verdict"], a["perch"]), ("FAIL", ["tripo_part_0"]))
            self.assertAlmostEqual(a["gap_m"], 0.0005, delta=2e-5)
            self.assertAlmostEqual(a["clips"]["Lift"]["gap_max_m"], 0.0055, delta=1e-4)
            self.assertEqual(a["clips"]["Lift"]["bad_frames"], "2")
            self.assertIn("отрывается", rep["failures"][0])
            self.assertEqual(scan["tripo_part_2"]["verdict"], "FLOAT_OK")
            # C47: жёсткие части одной кости — одна группа скана против остальной фигуры (не друг против друга)
            prof2 = dict(prof, rig={"weights": {"tripo_part_1": {"kind": "rigid", "bone": "rider"},
                                                "tripo_part_2": {"kind": "rigid", "bone": "rider"}}})
            (tmp / "profile2.json").write_text(json.dumps(prof2), encoding="utf-8")
            code = rg.main(["--run", str(run), "--profile", str(tmp / "profile2.json"), "--no-profile-pairs",
                            "--clip-fbx", "Lift=%s" % (run / "AM_Test_Lift.fbx"), "--out", str(out),
                            "--blender", BLENDER])
            self.assertEqual(code, 2)
            rep = json.loads(out.read_text(encoding="utf-8"))
            (grp,) = rep["scan"]
            self.assertEqual((grp["part"], grp["parts"], grp["perch"]),
                             ("tripo_part_1+tripo_part_2", ["tripo_part_1", "tripo_part_2"], ["tripo_part_0"]))
            self.assertAlmostEqual(grp["gap_m"], 0.0005, delta=2e-5)  # группа касается тела деталью A
            self.assertAlmostEqual(grp["clips"]["Lift"]["gap_max_m"], 0.0055, delta=1e-4)
            self.assertEqual(rep["inputs"]["bone_groups"], {"tripo_part_1+tripo_part_2": "rider"})
            # задуманный зазор пары: 0,5 мм против задуманных 3 мм — отход 2,5 мм > 2 → FAIL; 1 мм — PASS
            code = rg.main(["--run", str(run), "--profile", str(tmp / "profile.json"), "--no-profile-pairs",
                            "--pair", "A=1:0", "--designed-gap", "A=3", "--float-ok", "2", "--out", str(out),
                            "--blender", BLENDER])
            self.assertEqual(code, 2)
            rep = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(rep["pairs"][0]["designed_gap_m"], 0.003)
            self.assertIn("вне задуманного 3.00", rep["pairs"][0]["reasons"][0])
            self.assertIn("designed_gap_rule", rep["thresholds"])
            code = rg.main(["--run", str(run), "--profile", str(tmp / "profile.json"), "--no-profile-pairs",
                            "--pair", "A=1:0", "--designed-gap", "A=1", "--float-ok", "2", "--out", str(out),
                            "--blender", BLENDER])
            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
