"""Проба деформаций рига: рендер покоя и тестовых поворотов костей + численный отчёт.

ТОЛЬКО headless (`blender -b`): вызывается read_factory_settings, который в живом Blender
(MCP :9876/:9877) выгружает аддон MCP и очищает сцену. Без `-b` скрипт бросает RuntimeError
и ничего не делает; процесс Blender остаётся жив. SystemExit/sys.exit/os._exit для guard не
годятся: в живом Blender они завершают весь процесс.

Headless:
  blender -b --factory-startup --python tools/tripo-pipeline/anim/rig_deform_probe.py -- \
      <rig.fbx|glb|blend> <out_dir> <label> [--rot-x=90] [--weapon-side=L|R|LR|none] [--body-mesh=<имя>]
      [--skip=<проба>,<проба>]

Что делает (исходник не изменяется, ничего не сохраняется в .blend):
1. Импорт в пустую сцену, поиск арматуры и skinned-мешей.
2. Определяет «семейство» имён костей (контракт 17 костей / UE-Mannequin-подобное
   Tripo) и строит набор тестов: поворот головы, наклон спины, подъём каждой
   руки, сгиб бедра. Поворот задаётся в пространстве арматуры вокруг мировой
   оси через голову кости (не зависит от roll).
3. Для каждого теста считает, какие вершины сдвинулись > 1 % роста тела,
   их нормированный центроид (z_norm: 0 = низ тела, 1 = верх тела; x_norm: +1 = левая
   сторона фигуры, лук), и доли по мешам.
4. Рендерит Workbench (цвет текстуры, X-ray 0.6) спереди в PNG и пишет
   2D-проекции костей в JSON; наложение костей делает overlay_bones.py.
5. Расширенные пробы (RB-08, волна 1 доработки скилла): сгиб правого предплечья, сгиб обеих голеней,
   подъём носка каждой стопы, скрутка кисти руки оружия вокруг оси кости и поворот каждой кости weapon.*
   поперёк её оси (сдвигаться должно только оружие: доля вершин оружия среди сдвинутых ≥ 0,9). Кроме зоны
   центроида — своя часть кости сдвинулась (own_moved ≥ 1; не у голени) и утечка веса ≤ 5 % сдвинутых (bleed:
   вершина чужой части тела дальше 10 % роста от костей пробы). Для прежних 7 проб own/bleed — только справочно.
Рамка нормировки (F59): z_norm, x_norm и порог сдвига 1 % — по вершинам тела без оружия (skinned-меши, кроме
тела, и вершины тела с весом ≥ 0,95 на костях weapon.*, П3-1); рамка всей фигуры с оружием — frame.*_all, по ней
же камера рендера. Тело — меши с «Body» в имени (иначе самый большой skinned-меш) или --body-mesh.
Рука оружия: --weapon-side, иначе сторона костей weapon.* (суффикс .L/.R или сторона родителя), иначе сторона
доминирующей кости меша оружия.
Отчёт <label>-deform.json: tests — прежние 7 проб (имена, кости, оси, углы и пороги без изменений; их читают
run_h2_bake.py, validate_card.py и захват приёмки), extended_tests — новые пробы, probes — счёт n/N по обоим
спискам (N — из списков, без зашитых 7). --skip=<проба> выводит расширенную пробу из N (статус skipped) — для
фигуры без голеней и стоп (ствол Leshen, F53) по решению профиля; прежние 7 не пропускаются. Кость расширенной
пробы, у которой ни у неё, ни у потомков нет весов, — статус unweighted (не plausible).
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
# RB-08: кости расширенных проб по семействам (FAMILIES и TESTS выше не меняются — их читают другие инструменты)
FAMILIES_EXT = {
    "contract17": {
        "fore_r": "arm_lower.R", "shin_l": "leg_lower.L", "shin_r": "leg_lower.R", "foot_l": "foot.L",
        "foot_r": "foot.R", "hand_l": "hand.L", "hand_r": "hand.R",
    },
    "ue_like": {
        "fore_r": "lowerarm_r", "shin_l": "calf_l", "shin_r": "calf_r", "foot_l": "foot_l", "foot_r": "foot_r",
        "hand_l": "hand_l", "hand_r": "hand_r",
    },
    "mixamo": {
        "fore_r": "mixamorig:RightForeArm", "shin_l": "mixamorig:LeftLeg", "shin_r": "mixamorig:RightLeg",
        "foot_l": "mixamorig:LeftFoot", "foot_r": "mixamorig:RightFoot", "hand_l": "mixamorig:LeftHand",
        "hand_r": "mixamorig:RightHand",
    },
}
# Ось "BONE" — собственная ось кости (скрутка), "PERP" — мировая ось поперёк кости (X для почти вертикальной).
# X −40° сгибает предплечье вперёд (как forearm_l_bend), X +40° отводит голень назад (сгиб колена),
# X −30° поднимает носок стопы.
# Кроме зоны центроида расширенные пробы проверяют: own_moved_min — сдвинулась хоть одна вершина, у которой эта кость
# доминирующая (кость двигает свою часть, а не только дочерние: предплечье без весов, F122-класс); bleed_share_max —
# доля сдвинутых вершин чужой части тела (доминирующая кость не из цепи пробы и не её родитель) дальше 10 % роста от
# костей пробы (утечка веса: бедро Arthur на arm_upper.R). У голени own не требуется: под мантией (Merlin) голень
# своих вершин не имеет, подол скинен на таз/бёдра.
EXT_TESTS = [
    ("forearm_r_bend", "fore_r", "X", -40, {"z_norm_min": 0.30, "x_norm_max": -0.20, "own_moved_min": 1,
                                            "bleed_share_max": 0.05}),
    ("shin_l_bend", "shin_l", "X", 40, {"z_norm_max": 0.35, "x_norm_min": 0.0, "bleed_share_max": 0.05}),
    ("shin_r_bend", "shin_r", "X", 40, {"z_norm_max": 0.35, "x_norm_max": 0.0, "bleed_share_max": 0.05}),
    ("foot_l_flex", "foot_l", "X", -30, {"z_norm_max": 0.20, "x_norm_min": 0.0, "own_moved_min": 1,
                                         "bleed_share_max": 0.05}),
    ("foot_r_flex", "foot_r", "X", -30, {"z_norm_max": 0.20, "x_norm_max": 0.0, "own_moved_min": 1,
                                         "bleed_share_max": 0.05}),
]
HAND_TWIST = {  # скрутка кисти руки оружия вокруг оси кости
    "L": ("hand_l_twist", "hand_l", "BONE", 35, {"z_norm_min": 0.15, "x_norm_min": 0.10, "own_moved_min": 1,
                                                 "bleed_share_max": 0.05}),
    "R": ("hand_r_twist", "hand_r", "BONE", 35, {"z_norm_min": 0.15, "x_norm_max": -0.10, "own_moved_min": 1,
                                                 "bleed_share_max": 0.05}),
}
# кость weapon.*: двигает оружие, а не тело (доля вершин оружия среди сдвинутых)
WEAPON_TURN = ("PERP", 30, {"weapon_share_min": 0.90, "own_moved_min": 1, "bleed_share_max": 0.05})
WEAPON_HARD_W = 0.95  # вершина тела с таким весом на кости weapon.* — часть оружия (П3-1)
BLEED_R = 0.10  # сдвинутая вершина чужой части тела дальше 10 % роста от костей пробы — утечка веса (как clip_contact_check)

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


def side_of(name):
    """Сторона кости по имени: L, R или None (.L/_l/Left — левая сторона фигуры)."""
    n = name.lower()
    if n.endswith((".l", "_l")) or "left" in n:
        return "L"
    if n.endswith((".r", "_r")) or "right" in n:
        return "R"
    return None


def weapon_bone_names(names):
    return sorted(n for n in names if n.lower().startswith("weapon"))


def weapon_sides(wbones, parents, opt=None, mesh_side=None):
    """Стороны рук оружия и источник: --weapon-side (L, R, LR, none) > кости weapon.* (суффикс или сторона
    ближайшего предка) > доминирующая кость меша оружия > нет."""
    if opt is not None:
        o = opt.strip().upper()
        return ([] if o in ("", "NONE") else sorted(set(o) & {"L", "R"})), "option"
    sides = set()
    for b in wbones:
        s, p = side_of(b), parents.get(b)
        while s is None and p is not None:
            s, p = side_of(p), parents.get(p)
        if s:
            sides.add(s)
    if sides:
        return sorted(sides), "weapon_bone"
    if mesh_side:
        return [mesh_side], "weapon_mesh"
    return [], "none"


def ext_plan(fext, sides, wbones):
    """Расширенные пробы: (имя, кость|None, ось, градусы, ожидание) — число проб берётся из этого списка."""
    plan = [(n, fext.get(k), ax, d, e) for n, k, ax, d, e in EXT_TESTS]
    for s in sides:
        n, k, ax, d, e = HAND_TWIST[s]
        plan.append((n, fext.get(k), ax, d, e))
    for b in wbones:
        plan.append(("weapon_turn_" + b, b) + WEAPON_TURN)
    return plan


def zone_ok(moved_n, z_norm, x_norm, expect, weapon_share=None, own_n=None, bleed_share=None):
    """Санитарный тест зоны: что-то сдвинулось, центроид в ожидаемой зоне; для расширенных проб ещё доля оружия,
    своя часть кости и утечка веса (ключи ожидания weapon_share_min, own_moved_min, bleed_share_max)."""
    ok = moved_n > 0
    if ok and "z_norm_min" in expect:
        ok &= z_norm >= expect["z_norm_min"]
    if ok and "z_norm_max" in expect:
        ok &= z_norm <= expect["z_norm_max"]
    if ok and "x_norm_min" in expect:
        ok &= x_norm >= expect["x_norm_min"]
    if ok and "x_norm_max" in expect:
        ok &= x_norm <= expect["x_norm_max"]
    if ok and "weapon_share_min" in expect:
        ok &= weapon_share is not None and weapon_share >= expect["weapon_share_min"]
    if ok and "own_moved_min" in expect:
        ok &= own_n is not None and own_n >= expect["own_moved_min"]
    if ok and "bleed_share_max" in expect:
        ok &= bleed_share is not None and bleed_share <= expect["bleed_share_max"]
    return bool(ok)


def probe_summary(tests, extended):
    """Счёт проб n/N по обоим спискам; skipped выводится из N."""
    def count(ts):
        live = [t for t in ts if t.get("status") != "skipped"]
        return sum(1 for t in live if t.get("status") == "plausible"), len(live)
    lp, ln = count(tests)
    ep, en = count(extended)
    return {"plausible": lp + ep, "total": ln + en, "summary": "%d/%d" % (lp + ep, ln + en),
            "legacy": "%d/%d" % (lp, ln), "extended": "%d/%d" % (ep, en),
            "skipped": [t["test"] for t in list(tests) + list(extended) if t.get("status") == "skipped"],
            "passed": lp + ep == ln + en and ln + en > 0}


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
    if axis == "BONE":  # собственная ось кости (скрутка), уже в пространстве арматуры
        ax = (pb.tail - pb.head).normalized()
    elif axis == "PERP":  # мировая ось поперёк кости
        d = (arm.matrix_world.to_3x3() @ (pb.tail - pb.head)).normalized()
        w = Vector((1, 0, 0)) if abs(d.z) > 0.9 else d.cross(Vector((0, 0, 1))).normalized()
        ax = (arm.matrix_world.to_3x3().inverted() @ w).normalized()
    else:
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


def weapon_masks(meshes, wbones, body_opt=None):
    """Вершины оружия по мешам: все вершины skinned-мешей, кроме тела, и вершины тела с весом >= WEAPON_HARD_W на
    костях weapon.*. Тело — --body-mesh, иначе меши с «Body» в имени, иначе самый большой меш."""
    if body_opt:
        body = {o.name for o in meshes if o.name == body_opt}
    else:
        body = {o.name for o in meshes if "body" in o.name.lower()}
    if not body and meshes:
        body = {max(meshes, key=lambda o: len(o.data.vertices)).name}
    masks = {}
    for ob in meshes:
        if ob.name not in body:
            masks[ob.name] = [True] * len(ob.data.vertices)
            continue
        gi = {g.index for g in ob.vertex_groups if g.name in wbones}
        masks[ob.name] = [any(g.group in gi and g.weight >= WEAPON_HARD_W for g in v.groups) for v in ob.data.vertices]
    return sorted(body), masks


def dominant_bones(meshes):
    """Доминирующая кость (наибольший вес) каждой вершины skinned-меша; None — вершина без весов."""
    out = {}
    for ob in meshes:
        names = {g.index: g.name for g in ob.vertex_groups}
        dom = []
        for v in ob.data.vertices:
            ws = [(names[g.group], g.weight) for g in v.groups if g.group in names and g.weight > 0.0]
            dom.append(max(ws, key=lambda x: x[1])[0] if ws else None)
        out[ob.name] = dom
    return out


def seg_dist(p, a, b):
    ab = b - a
    t = min(max((p - a).dot(ab) / max(ab.length_squared, 1e-12), 0.0), 1.0)
    return (p - (a + ab * t)).length


def weighted_bones(meshes):
    out = set()
    for ob in meshes:
        names = {g.index: g.name for g in ob.vertex_groups}
        for v in ob.data.vertices:
            for g in v.groups:
                if g.weight > 0.0 and g.group in names:
                    out.add(names[g.group])
    return out


def mesh_dominant_side(meshes, body):
    """Сторона руки, на которой висит меш оружия (доминирующая кость его вершин), если костей weapon.* нет."""
    acc = {}
    for ob in meshes:
        if ob.name in body:
            continue
        names = {g.index: g.name for g in ob.vertex_groups}
        for v in ob.data.vertices:
            ws = [(names[g.group], g.weight) for g in v.groups if g.group in names]
            if ws:
                n = max(ws, key=lambda x: x[1])[0]
                acc[n] = acc.get(n, 0) + 1
    if not acc:
        return None
    return side_of(max(acc, key=acc.get))


def main():
    for stream in (sys.stdout, sys.stderr):  # RB-11/F47: кириллица и «×» при cp1251-канале (Bash агентов)
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
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
    names = list(arm.data.bones.keys())
    wbones = weapon_bone_names(names)
    body, wmask = weapon_masks(meshes, set(wbones), opts.get("--body-mesh"))
    parents = {b.name: (b.parent.name if b.parent else None) for b in arm.data.bones}
    sides, side_src = weapon_sides(wbones, parents, opts.get("--weapon-side"),
                                   None if wbones else mesh_dominant_side(meshes, set(body)))
    skip = {s.strip() for s in opts.get("--skip", "").split(",") if s.strip()}
    weighted = weighted_bones(meshes)
    vdom = dominant_bones(meshes)
    mn_all, mx_all, cam = setup_render(meshes)
    rest = eval_coords(meshes)
    # F59: рамка нормировки — тело без оружия (вершины rest), рамка всей фигуры — только для камеры и справки
    body_pts = [p for obn, pts in rest.items() for p, w in zip(pts, wmask[obn]) if not w]
    if not body_pts:
        body_pts = [p for pts in rest.values() for p in pts]
    mn = Vector([min(p[i] for p in body_pts) for i in range(3)])
    mx = Vector([max(p[i] for p in body_pts) for i in range(3)])
    h = mx.z - mn.z
    half_w = max(mx.x - mn.x, 1e-6) / 2
    cx = (mn.x + mx.x) / 2
    n_weapon_v = sum(sum(m) for m in wmask.values())
    report = {"source": repo_rel(src), "label": label,
              "family": fam, "family_bone_hits": score, "height": round(h, 5),
              "bbox_min": [round(v, 4) for v in mn], "bbox_max": [round(v, 4) for v in mx],
              "frame": {"kind": "body_without_weapon", "body_meshes": body,
                        "weapon_meshes": sorted(k for k in wmask if k not in body),
                        "weapon_bones": wbones, "weapon_vertices": n_weapon_v,
                        "height_all": round(mx_all.z - mn_all.z, 5),
                        "bbox_all_min": [round(v, 4) for v in mn_all], "bbox_all_max": [round(v, 4) for v in mx_all],
                        "note": "z_norm/x_norm и порог сдвига 1 % — по телу без оружия (F59); камера — по всей фигуре"},
              "weapon_sides": sides, "weapon_side_source": side_src,
              "tests": [], "extended_tests": []}
    sc.render.filepath = os.path.join(out_dir, f"{label}-rest.png")
    bpy.ops.render.render(write_still=True)
    frames = {"rest": {"png": os.path.basename(sc.render.filepath), "bones": project_bones(arm, cam)}}
    fext = FAMILIES_EXT.get(fam, {})
    plan = [("tests", n, fmap.get(k), ax, d, e) for n, k, ax, d, e in TESTS] + \
           [("extended_tests", n, b, ax, d, e) for n, b, ax, d, e in ext_plan(fext, sides, wbones)]
    for where, name, bone, axis, deg, expect in plan:
        if name in skip and where == "extended_tests":  # прежние 7 проб — контракт, не пропускаются
            report[where].append({"test": name, "bone": bone, "status": "skipped", "reason": "--skip"})
            continue
        if bone not in arm.pose.bones:
            report[where].append({"test": name, "bone": bone, "status": "missing_bone"})
            continue
        for pb in arm.pose.bones:
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        rotate_bone(arm, bone, axis, deg)
        posed = eval_coords(meshes)
        moved, per_mesh = [], {}
        n_wmoved = 0
        thr = 0.01 * h
        bb = arm.data.bones[bone]
        chain = {bone} | {c.name for c in bb.children_recursive}
        near = chain | ({bb.parent.name} if bb.parent else set())  # родитель — стык сустава, не утечка
        segs = [(arm.matrix_world @ arm.data.bones[b].head_local, arm.matrix_world @ arm.data.bones[b].tail_local)
                for b in chain]
        foreign, own, bleed = 0, 0, {}
        for obn, pts in posed.items():
            cnt = 0
            for i, (p, r, w) in enumerate(zip(pts, rest[obn], wmask[obn])):
                if (p - r).length > thr:
                    moved.append(r)
                    cnt += 1
                    n_wmoved += w
                    g = vdom[obn][i]
                    own += g == bone
                    if not w and g not in near:
                        foreign += 1
                        if min(seg_dist(r, a, b) for a, b in segs) > BLEED_R * h:
                            bleed[g] = bleed.get(g, 0) + 1
            per_mesh[obn] = round(cnt / max(len(pts), 1), 4)
        if moved:
            c = sum(moved, Vector()) / len(moved)
            z_norm = (c.z - mn.z) / h
            x_norm = (c.x - cx) / half_w
            z_all = (c.z - mn_all.z) / max(mx_all.z - mn_all.z, 1e-9)
        else:
            z_norm = x_norm = z_all = None
        wshare = (n_wmoved / len(moved)) if moved else None
        nb = sum(bleed.values())
        bshare = (nb / len(moved)) if moved else None
        ok = zone_ok(len(moved), z_norm, x_norm, expect, wshare, own, bshare)
        status = "plausible" if ok else "wrong_region"
        if not moved and where == "extended_tests" and                 not ({bone} | {c.name for c in arm.data.bones[bone].children_recursive}) & weighted:
            status = "unweighted"  # у кости и её потомков нет весов: проба не двигает ничего
        top = sorted(per_mesh.items(), key=lambda kv: -kv[1])[:5]
        png = f"{label}-{name}.png"
        sc.render.filepath = os.path.join(out_dir, png)
        bpy.ops.render.render(write_still=True)
        frames[name] = {"png": png, "bones": project_bones(arm, cam)}
        row = {
            "test": name, "bone": bone, "axis": axis, "deg": deg,
            "moved_vertices": len(moved),
            "centroid_z_norm": None if z_norm is None else round(z_norm, 3),
            "centroid_x_norm": None if x_norm is None else round(x_norm, 3),
            "expect": expect, "status": status,
            "top_meshes_moved_share": top,
            "centroid_z_norm_all": None if z_all is None else round(z_all, 3),
        }
        row.update({"own_moved": own, "foreign_moved": foreign, "bleed_vertices": nb,
                    "bleed_share": None if bshare is None else round(bshare, 4),
                    "bleed_bones": dict(sorted(bleed.items(), key=lambda kv: -kv[1])[:4])})
        if where == "extended_tests":
            row["weapon_moved_share"] = None if wshare is None else round(wshare, 4)
        report[where].append(row)
    report["probes"] = probe_summary(report["tests"], report["extended_tests"])
    with open(os.path.join(out_dir, f"{label}-deform.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, f"{label}-bones2d.json"), "w", encoding="utf-8") as f:
        json.dump(frames, f, ensure_ascii=False)
    print("DEFORM_OK", label, fam, report["probes"]["summary"],
          [(t["test"], t.get("status"), t.get("centroid_z_norm"))
           for t in report["tests"] + report["extended_tests"]])


main()
