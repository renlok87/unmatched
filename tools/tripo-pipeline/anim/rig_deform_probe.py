"""Проба деформаций рига: рендер покоя и тестовых поворотов костей + численный отчёт.

ТОЛЬКО headless (`blender -b`): вызывается read_factory_settings, который в живом Blender
(MCP :9876/:9877) выгружает аддон MCP и очищает сцену. Без `-b` скрипт бросает RuntimeError
и ничего не делает; процесс Blender остаётся жив. SystemExit/sys.exit/os._exit для guard не
годятся: в живом Blender они завершают весь процесс.

Headless:
  blender -b --factory-startup --python tools/tripo-pipeline/anim/rig_deform_probe.py -- \
      <rig.fbx|glb|blend> <out_dir> <label>

Что делает (исходник не изменяется, ничего не сохраняется в .blend):
1. Импорт в пустую сцену, поиск арматуры и skinned-мешей.
2. Определяет «семейство» имён костей (контракт 17 костей / UE-Mannequin-подобное
   Tripo) и строит набор тестов: поворот головы, наклон спины, подъём каждой
   руки, сгиб бедра. Поворот задаётся в пространстве арматуры вокруг мировой
   оси через голову кости (не зависит от roll).
3. Для каждого теста считает, какие вершины сдвинулись > 1 % высоты фигуры,
   их нормированный центроид (z_norm: 0 = низ подставки, 1 = верх змей;
   x_norm: +1 = левая сторона фигуры, лук), и доли по мешам.
4. Рендерит Workbench (цвет текстуры, X-ray 0.6) спереди в PNG и пишет
   2D-проекции костей в JSON; наложение костей делает overlay_bones.py.
Ожидаемые зоны (EXPECT) — грубый санитарный тест «кость двигает свою часть тела»,
а не художественная приёмка.
"""
import json
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

if not bpy.app.background:
    # RuntimeError, не SystemExit: SystemExit в живом Blender завершает весь процесс.
    raise RuntimeError("rig_deform_probe.py: только headless (blender -b)")

FAMILIES = {
    "contract17": {
        "head": "head", "spine": "spine", "arm_l": "arm_upper.L", "arm_r": "arm_upper.R",
        "fore_l": "arm_lower.L", "thigh_l": "leg_upper.L", "thigh_r": "leg_upper.R",
    },
    "ue_like": {
        "head": "head", "spine": "spine_02", "arm_l": "upperarm_l", "arm_r": "upperarm_r",
        "fore_l": "lowerarm_l", "thigh_l": "thigh_l", "thigh_r": "thigh_r",
    },
    "mixamo": {
        "head": "mixamorig:Head", "spine": "mixamorig:Spine1", "arm_l": "mixamorig:LeftArm",
        "arm_r": "mixamorig:RightArm", "fore_l": "mixamorig:LeftForeArm",
        "thigh_l": "mixamorig:LeftUpLeg", "thigh_r": "mixamorig:RightUpLeg",
    },
}
# (ключ кости, мировая ось, градусы, ожидаемая зона центроида сдвинутых вершин)
TESTS = [
    ("head_turn", "head", "Z", 35, {"z_norm_min": 0.70}),
    ("spine_bend_fwd", "spine", "X", 25, {"z_norm_min": 0.45}),
    ("arm_l_raise", "arm_l", "Y", -45, {"z_norm_min": 0.35, "x_norm_min": 0.15}),
    ("arm_r_raise", "arm_r", "Y", 45, {"z_norm_min": 0.35, "x_norm_max": -0.15}),
    ("forearm_l_bend", "fore_l", "X", -40, {"z_norm_min": 0.30, "x_norm_min": 0.20}),
    ("thigh_l_flex", "thigh_l", "X", -35, {"z_norm_max": 0.55}),
    ("thigh_r_flex", "thigh_r", "X", -35, {"z_norm_max": 0.55}),
]

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def repo_rel(path):
    """Путь относительно корня репозитория (прямые слэши); вне репозитория — абсолютный."""
    p = os.path.abspath(path)
    try:
        rel = os.path.relpath(p, REPO)
    except ValueError:  # другой диск
        return p.replace("\\", "/")
    return (p if rel.startswith("..") else rel).replace("\\", "/")


def args():
    a = sys.argv[sys.argv.index("--") + 1:]
    opts = {k: v for k, v in (x.split("=", 1) for x in a[3:] if "=" in x)}
    return a[0], a[1], a[2], opts


def load(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if ext == ".fbx":
            bpy.ops.import_scene.fbx(filepath=path)
        else:
            bpy.ops.import_scene.gltf(filepath=path)


def family(arm):
    names = set(arm.data.bones.keys())
    best, score = None, -1
    for fam, m in FAMILIES.items():
        s = sum(1 for v in m.values() if v in names)
        if s > score:
            best, score = fam, s
    return best, score


def eval_coords(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        mw = ob.matrix_world
        out[ob.name] = [mw @ v.co for v in me.vertices]
        ev.to_mesh_clear()
    return out


def rotate_bone(arm, bone, axis, deg):
    pb = arm.pose.bones[bone]
    head = pb.head.copy()  # armature space
    ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    # мировая ось -> пространство арматуры
    ax = (arm.matrix_world.to_3x3().inverted() @ ax).normalized()
    R = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-head)
    pb.matrix = R @ pb.matrix
    bpy.context.view_layer.update()


def setup_render(meshes, out_w=900):
    sc = bpy.context.scene
    pts = [ob.matrix_world @ Vector(c) for ob in meshes for c in ob.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    ctr = (mn + mx) / 2
    h = mx.z - mn.z
    cam_data = bpy.data.cameras.new("ProbeCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = h * 1.12
    cam = bpy.data.objects.new("ProbeCam", cam_data)
    sc.collection.objects.link(cam)
    cam.location = (ctr.x, mn.y - h * 3, ctr.z)
    cam.rotation_euler = (math.radians(90), 0, 0)  # смотрит вдоль +Y (вид спереди)
    sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light = "STUDIO"
    sh.color_type = "TEXTURE"
    sh.show_xray = True
    sh.xray_alpha = 0.6
    sc.render.resolution_x = out_w
    sc.render.resolution_y = out_w
    sc.render.film_transparent = False
    return mn, mx, cam


def project_bones(arm, cam):
    sc = bpy.context.scene
    W, H = sc.render.resolution_x, sc.render.resolution_y
    segs = []
    for pb in arm.pose.bones:
        a = world_to_camera_view(sc, cam, arm.matrix_world @ pb.head)
        b = world_to_camera_view(sc, cam, arm.matrix_world @ pb.tail)
        segs.append({"name": pb.name,
                     "a": [round(a.x * W, 1), round((1 - a.y) * H, 1)],
                     "b": [round(b.x * W, 1), round((1 - b.y) * H, 1)]})
    return segs


def main():
    src, out_dir, label, opts = args()
    out_dir = os.path.abspath(out_dir)  # иначе Blender пишет относительный путь от корня диска
    os.makedirs(out_dir, exist_ok=True)
    load(src)
    sc = bpy.context.scene
    arm = next(o for o in sc.objects if o.type == "ARMATURE")
    meshes = [o for o in sc.objects if o.type == "MESH"
              and any(m.type == "ARMATURE" for m in o.modifiers)]
    # Поза покоя = единичные matrix_basis (glTF-импорт может оставить позу bind).
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    # --rot-x=90: повернуть все корневые объекты сцены вокруг мировой X, если источник лёг набок.
    if "--rot-x" in opts:
        rx = Matrix.Rotation(math.radians(float(opts["--rot-x"])), 4, "X")
        for ob in [o for o in bpy.context.scene.objects if o.parent is None]:
            ob.matrix_world = rx @ ob.matrix_world
    bpy.context.view_layer.update()
    fam, score = family(arm)
    fmap = FAMILIES[fam]
    mn, mx, cam = setup_render(meshes)
    h = mx.z - mn.z
    half_w = max(mx.x - mn.x, 1e-6) / 2
    cx = (mn.x + mx.x) / 2
    rest = eval_coords(meshes)
    report = {"source": repo_rel(src), "label": label,
              "family": fam, "family_bone_hits": score, "height": round(h, 5),
              "bbox_min": [round(v, 4) for v in mn], "bbox_max": [round(v, 4) for v in mx],
              "tests": []}
    sc.render.filepath = os.path.join(out_dir, f"{label}-rest.png")
    bpy.ops.render.render(write_still=True)
    frames = {"rest": {"png": os.path.basename(sc.render.filepath), "bones": project_bones(arm, cam)}}
    for name, key, axis, deg, expect in TESTS:
        bone = fmap.get(key)
        if bone not in arm.pose.bones:
            report["tests"].append({"test": name, "bone": bone, "status": "missing_bone"})
            continue
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        rotate_bone(arm, bone, axis, deg)
        posed = eval_coords(meshes)
        moved, per_mesh = [], {}
        thr = 0.01 * h
        for obn, pts in posed.items():
            cnt = 0
            for p, r in zip(pts, rest[obn]):
                if (p - r).length > thr:
                    moved.append(r)
                    cnt += 1
            per_mesh[obn] = round(cnt / max(len(pts), 1), 4)
        if moved:
            c = sum(moved, Vector()) / len(moved)
            z_norm = (c.z - mn.z) / h
            x_norm = (c.x - cx) / half_w
        else:
            z_norm = x_norm = None
        ok = moved != []
        if ok and "z_norm_min" in expect:
            ok &= z_norm >= expect["z_norm_min"]
        if ok and "z_norm_max" in expect:
            ok &= z_norm <= expect["z_norm_max"]
        if ok and "x_norm_min" in expect:
            ok &= x_norm >= expect["x_norm_min"]
        if ok and "x_norm_max" in expect:
            ok &= x_norm <= expect["x_norm_max"]
        top = sorted(per_mesh.items(), key=lambda kv: -kv[1])[:5]
        png = f"{label}-{name}.png"
        sc.render.filepath = os.path.join(out_dir, png)
        bpy.ops.render.render(write_still=True)
        frames[name] = {"png": png, "bones": project_bones(arm, cam)}
        report["tests"].append({
            "test": name, "bone": bone, "axis": axis, "deg": deg,
            "moved_vertices": len(moved),
            "centroid_z_norm": None if z_norm is None else round(z_norm, 3),
            "centroid_x_norm": None if x_norm is None else round(x_norm, 3),
            "expect": expect, "status": "plausible" if ok else "wrong_region",
            "top_meshes_moved_share": top,
        })
    with open(os.path.join(out_dir, f"{label}-deform.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, f"{label}-bones2d.json"), "w", encoding="utf-8") as f:
        json.dump(frames, f, ensure_ascii=False)
    print("DEFORM_OK", label, fam, [(t["test"], t.get("status"), t.get("centroid_z_norm"))
                                    for t in report["tests"]])


main()
