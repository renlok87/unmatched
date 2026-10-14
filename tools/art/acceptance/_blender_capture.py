"""Blender-часть capture_acceptance_set.py: рендер кадров приёмки модели (этап 4, DECISIONS Р-6.1).

ТОЛЬКО headless: read_factory_settings в живом Blender (MCP) выгрузил бы аддон и очистил сцену.

  blender -b --factory-startup --python tools/art/acceptance/_blender_capture.py -- <cfg.json>

Запускается обёрткой capture_acceptance_set.py; cfg.json пишет обёртка:
  {"fbx", "base_fbx"|null, "textures": {"bc","n","orm"}, "work_dir", "size", "probe_source",
   "attack_bone"|null, "attack_source"|null}
Выход (всё в work_dir; JPEG и uv-layout.png собирает обёртка): raw/{turn-000..turn-315, close-head, close-weapon,
close-torso, close-head-back, close-torso-back, close-legs, close-legs-back, close-base, close-hands-R, close-hands-L
(две панели 1:2, склеивает обёртка), close-attack-side, close-attack-back (две панели 1:2, только при attack_bone),
wire-front, wire-34, wire-back, pose-01..04, pose-03b, pose-04b, pose-05}.png (RGBA, прозрачный фон),
uv-data.npz (UV0 треугольников), capture.json (pose_checks: 3D-зазоры оружие–голова и оружие–тело в каждой позе,
ракурс pose-04b по видимости, attack).

Кадры пилота 2026-10-14 (добавочные, прежние не меняются):
- pose-04b (F77): поза pose-04 со второго ракурса — азимут (шаг 30°, не ближе 60° к az pose-04), где из вершин таза и
  поднятого бедра (доминирующие группы thigh_l и её родителя) видно больше всего (луч от вершины к камере ни во что не
  упирается): у Achilles щит закрывал бедро и юбку с az 70, оболочка юбки П3-3 осталась без оценки.
- pose-05 (F129): рука оружия (без оружия — атакующая, иначе правая) вперёд — плечо X −70°, предплечье X −20° (как
  выпад/бросок; оси и знаки — rig_deform_probe) — со спины 3/4 этой стороны (R: az 225, L: az 135), рамка — верх
  фигуры от тазобедренного сустава (оружие в рамку не входит): кромка проймы плаща Achilles за правой подмышкой
  раскрывалась только в клипах этапа 6.
- close-attack (F74): при attack_bone (WEAPON_HAND none: сокет-кость атаки, когти/кисть/лапа) — две панели 600×1200 по
  группе этой кости: бок (R: az 270, L: az 90) и спина 3/4 (R: az 215, L: az 145); рамка — вся группа с запасом 15 %,
  не меньше 12 % роста. Фронт 3/4 атакующей кисти даёт close-hands; close-weapon без кости оружия показывает верх фигуры.

Правила v2 (профиль H2 с profile_version ≥ 2; cfg "rules": 2, решает обёртка; проверочный прогон Beowulf 2026-10-14):
- backface_culling (C22): материалы превью и каркаса отсекают задние грани, как односторонние материалы UE — крышка,
  видимая только изнанкой, на кадре становится дырой (как в игре), а не закрашенной заплаткой;
- hand_view "visibility" (C30): панель close-hands снимается с ракурса по умолчанию (R az −35, L az 35), если с него
  видно не меньше HAND_MIN_VISIBLE (20 %) вершин кисти; иначе — с азимута (шаг 30°) наибольшей видимости (щит на предплечье);
- uv_shell (C36): в uv-data не идут внутренняя копия оболочки `rig.cloth_shell` (тот же UV0, обратный обход:
  _framing.shell_copy_mask) и её мосты (нулевая площадь UV) — они не острова и не перевёрнутые треугольники развёртки.
У профилей v1 (Medusa, пилот) и без правил все три выключены: кадры прежние.

Сцена: FBX UM_FBX_v1 (лицо +X) поворачивается на -90 deg вокруг Z обратно в авторский кадр (лицо -Y, сторона .L = +X),
как st_preview.py h2_bake. Материал превью: BC (sRGB) -> Base Color; N (Non-Color, DirectX) -> зелёный канал
инвертируется (1 - G) -> Normal Map (Blender ждёт OpenGL); ORM (Non-Color): G -> Roughness, B -> Metallic,
R (AO) в Principled не подаётся (как в Material Preview / st_preview: рендер считает затенение сам).
Камера ортографическая; свет (key/fill/rim) вращается вместе с камерой — все ракурсы освещены одинаково.
"""
import ast
import json
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _framing import (CLOSE_MIN, HAND_MIN_VISIBLE, best_panel_azimuth,  # noqa: E402  (только numpy;
                      best_separating_azimuth, best_visible_azimuth, clamp_close_scale,  # тестируется без Blender)
                      panel_fit_scale, shell_copy_mask, view_fit_scale, zero_uv_area_mask)

if not bpy.app.background:
    raise RuntimeError("_blender_capture.py: только headless (blender -b)")

TURN_ANGLES = list(range(0, 360, 45))
# Позы pose-01..04: сочетания тестов rig_deform_probe.py (те же кости, мировые оси, углы; авторский кадр).
POSES = [
    ("pose-01", ["arm_l_raise", "forearm_l_bend"], 0, 0),
    ("pose-02", ["arm_r_raise"], 0, 0),
    ("pose-03", ["spine_bend_fwd", "head_turn"], 60, 10),
    ("pose-04", ["thigh_l_flex"], 70, 5),
]
# Ноги и низ одежды для close-legs / close-legs-back (кости UM_HUMANOID_17_v2, docs/art-pipeline/rig/rig-contract.json)
LEG_GROUPS = ["hips", "leg_upper.L", "leg_upper.R", "leg_lower.L", "leg_lower.R", "foot.L", "foot.R"]
CONTACT_M = 0.003  # 3D-зазор оружия меньше 3 мм на модели ~0,6 м — касание или проникновение (решение скилла)
# pose-05 (F129): рука вперёд — повороты вокруг мировой оси X через голову кости, как тесты rig_deform_probe
# (X − сгибает вперёд: forearm_l_bend −40, thigh_l_flex −35); ракурс — спина 3/4 стороны руки
ARM_FORWARD = (("arm", "X", -70), ("fore", "X", -20))
POSE05_AZ, POSE05_EL = {"R": 225, "L": 135}, 10
# pose-04b (F77): кандидаты азимута и отступ от ракурса pose-04
POSE04B_CANDIDATES, POSE04B_MIN_SEP, POSE04B_SAMPLE = range(0, 360, 30), 60, 400
# close-attack (F74): бок и спина 3/4 атакующей конечности
ATTACK_AZ = {"R": (("side", 270), ("back", 215)), "L": (("side", 90), ("back", 145))}
# close-hands по видимости (правила v2, C30): кандидаты азимута панели кисти
HAND_CANDIDATES = range(0, 360, 30)


def probe_definitions(path):
    """FAMILIES и TESTS из rig_deform_probe.py без импорта (модуль при импорте сразу запускает main()); третьим —
    FAMILIES_EXT (кости расширенных проб: fore_r, hand_*), {} если их нет."""
    tree = ast.parse(open(path, encoding="utf-8").read())
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ("FAMILIES", "TESTS", "FAMILIES_EXT"):
                out[node.targets[0].id] = ast.literal_eval(node.value)
    return out["FAMILIES"], out["TESTS"], out.get("FAMILIES_EXT", {})


def visible_share(bvh, pts, az, el, eps):
    """Доля точек pts (вершины поверхности), из которых луч к камере (az, el) ни во что не упирается."""
    d = direction(az, el)
    seen = 0
    for p in pts:
        loc, _n, _i, _dist = bvh.ray_cast(Vector(p.tolist()) + d * eps, d)
        seen += loc is None
    return seen / max(len(pts), 1)


def figure_bvh(meshes, coords_by_mesh):
    """BVH всех мешей в текущей позе (окклюзия для видимости)."""
    from mathutils.bvhtree import BVHTree

    verts, polys, off = [], [], 0
    for o in meshes:
        co = coords_by_mesh[o.name]
        verts += [Vector(p.tolist()) for p in co]
        polys += [tuple(off + v for v in p.vertices) for p in o.data.polygons]
        off += len(co)
    return BVHTree.FromPolygons(verts, polys, all_triangles=False)


def rotate_bone(arm, bone, axis, deg):
    """Как rig_deform_probe.rotate_bone: поворот вокруг мировой оси через голову кости (не зависит от roll)."""
    pb = arm.pose.bones[bone]
    head = pb.head.copy()
    ax = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}[axis]
    ax = (arm.matrix_world.to_3x3().inverted() @ ax).normalized()
    pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, ax) @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def set_engine(scene):
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    if scene.render.engine == "CYCLES":
        scene.cycles.samples = 64
        scene.cycles.use_denoising = True
    else:
        scene.eevee.taa_render_samples = 64
    return scene.render.engine


def tex_node(nt, path, colour, uv):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    node = nt.nodes.new("ShaderNodeTexImage")
    node.image = img
    nt.links.new(uv.outputs["UV"], node.inputs["Vector"])
    return node


def cull_back_faces(mat, engine):
    """Отсечение задних граней (C22): флаг материала EEVEE; в Cycles — Backfacing → Transparent перед выходом."""
    mat.use_backface_culling = True
    if engine != "CYCLES":
        return
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    src = out.inputs["Surface"].links[0].from_socket
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    nt.links.new(src, mix.inputs[1])
    nt.links.new(clear.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])


def preview_material(tex):
    mat = bpy.data.materials.new("ACCEPT_PREVIEW")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    t_bc = tex_node(nt, tex["bc"], True, uv)
    nt.links.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
    t_orm = tex_node(nt, tex["orm"], False, uv)
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t_orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    # N DirectX -> OpenGL для Blender: G = 1 - G
    t_n = tex_node(nt, tex["n"], False, uv)
    sn = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t_n.outputs["Color"], sn.inputs["Color"])
    inv = nt.nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    nt.links.new(sn.outputs["Green"], inv.inputs[1])
    cn = nt.nodes.new("ShaderNodeCombineColor")
    nt.links.new(sn.outputs["Red"], cn.inputs["Red"])
    nt.links.new(inv.outputs["Value"], cn.inputs["Green"])
    nt.links.new(sn.outputs["Blue"], cn.inputs["Blue"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nt.links.new(cn.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def wire_material():
    """Глина + сетка треугольников (Wireframe node, толщина в пикселях)."""
    mat = bpy.data.materials.new("ACCEPT_WIRE")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Base Color"].default_value = (0.55, 0.55, 0.55, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.7
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    wf = nt.nodes.new("ShaderNodeWireframe")
    wf.use_pixel_size = True
    wf.inputs["Size"].default_value = 1.0
    line = nt.nodes.new("ShaderNodeEmission")
    line.inputs["Color"].default_value = (0.01, 0.03, 0.06, 1.0)
    line.inputs["Strength"].default_value = 1.0
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs["Fac"], mix.inputs["Fac"])
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    nt.links.new(line.outputs["Emission"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def assign(meshes, mat):
    for o in meshes:
        if not o.material_slots:
            o.data.materials.append(mat)
        for slot in o.material_slots:
            slot.link = "OBJECT"  # не трогает материалы меша; слот объекта перекрывает
            slot.material = mat


def world(scene):
    """Освещение от мира 0,05 (тёмный нейтральный); фон кадра прозрачный — обёртка кладёт кадр на серый фон."""
    w = bpy.data.worlds.new("ACCEPT_WORLD")
    scene.world = w
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (0.05, 0.05, 0.055, 1.0)
    bg.inputs["Strength"].default_value = 1.0


def light_rig(scene, centre, h):
    """key/fill/rim как st_preview.py (позиции для фигуры 0,55 м), масштаб по росту; вращается с камерой."""
    rig = bpy.data.objects.new("ACCEPT_LIGHT_RIG", None)
    scene.collection.objects.link(rig)
    rig.location = centre
    s = max(h, 1e-3) / 0.55
    for name, loc, energy, size in (("key", (-1.5, -2.0, 2.0), 250, 1.5), ("fill", (2.0, -1.5, 1.0), 90, 2.0),
                                    ("rim", (0.5, 2.5, 2.2), 160, 1.5)):
        ld = bpy.data.lights.new("ACCEPT_" + name, "AREA")
        ld.energy = energy * s * s
        ld.size = size * s
        o = bpy.data.objects.new("ACCEPT_" + name, ld)
        scene.collection.objects.link(o)
        o.parent = rig
        o.location = Vector(loc) * s
        o.rotation_euler = (-Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return rig


def direction(az_deg, el_deg):
    """Направление от цели к камере. az 0 = спереди (камера на -Y), 90 = левый бок фигуры (+X, сторона .L),
    180 = сзади, 270 = правый бок; против часовой стрелки при взгляде сверху."""
    a, e = math.radians(az_deg), math.radians(el_deg)
    return Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


def evaluated_coords(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    out = {}
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3, dtype=np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        mw = np.array(o.matrix_world)
        out[o.name] = co @ mw[:3, :3].T + mw[:3, 3]
        ev.to_mesh_clear()
    return out


def group_coords(meshes, coords, group, min_w=0.5):
    pts = []
    for o in meshes:
        vg = o.vertex_groups.get(group)
        if vg is None:
            continue
        idx = vg.index
        sel = [v.index for v in o.data.vertices if any(g.group == idx and g.weight >= min_w for g in v.groups)]
        if sel:
            pts.append(coords[o.name][sel])
    return np.concatenate(pts) if pts else None


def dominant_groups(meshes):
    """{имя меша: массив имён группы с наибольшим весом на вершину ('' — без групп)}; веса в позах не меняются."""
    out = {}
    for o in meshes:
        names = {g.index: g.name for g in o.vertex_groups}
        dom = []
        for v in o.data.vertices:
            best = max(v.groups, key=lambda g: g.weight, default=None)
            dom.append(names.get(best.group, "") if best is not None else "")
        out[o.name] = np.array(dom, dtype=object)
    return out


def kd_min_distance(a, b):
    """Точное минимальное расстояние между вершинами наборов a и b (KD-дерево по b, все вершины, без поднабора)."""
    from mathutils.kdtree import KDTree

    tree = KDTree(len(b))
    for i, p in enumerate(b):
        tree.insert(Vector(p.tolist()), i)
    tree.balance()
    return min(tree.find(Vector(p.tolist()))[2] for p in a)


def body_coords(meshes, coords, dom, exclude):
    """Вершины тела фигуры: меши без подставки, вершины, чья главная группа не из exclude."""
    pts = [coords[o.name][~np.isin(dom[o.name], list(exclude))] for o in meshes]
    pts = [p for p in pts if len(p)]
    return np.concatenate(pts) if pts else None


def main():
    cfg = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    work_dir = cfg["work_dir"]
    size = int(cfg["size"])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    warnings = []
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=cfg["fbx"])
    before_base = set(bpy.data.objects)
    if cfg.get("base_fbx"):
        bpy.ops.import_scene.fbx(filepath=cfg["base_fbx"])
    base_objs = {o.name for o in bpy.data.objects if o not in before_base}
    imported = [o for o in bpy.data.objects if o not in before]
    # UM_FBX_v1: лицо +X -> авторский кадр (лицо -Y), как st_preview.py
    inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
    for o in imported:
        if o.parent is None:
            o.matrix_world = inv @ o.matrix_world
    bpy.context.view_layer.update()
    meshes = [o for o in imported if o.type == "MESH"]
    arms = [o for o in imported if o.type == "ARMATURE"]
    arm = arms[0] if arms else None
    if len(arms) > 1:
        warnings.append("арматур %d, позы — по первой (%s)" % (len(arms), arm.name))
    if arm is not None:
        reset_pose(arm)
    engine = set_engine(scene)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "None"
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True  # RGBA PNG; JPEG q92 на сером фоне делает обёртка (и маску для проверок)
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    raw_dir = os.path.join(work_dir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    world(scene)

    rest = evaluated_coords(meshes)
    allc = np.concatenate(list(rest.values()))
    mn, mx = allc.min(axis=0), allc.max(axis=0)
    h = float(mx[2] - mn[2])
    radius = float(np.sqrt(allc[:, 0] ** 2 + allc[:, 1] ** 2).max())  # вокруг оси pivot (0, 0)
    turn_scale = max(h, 2.0 * radius) * 1.10
    centre = Vector((0.0, 0.0, float(mn[2] + mx[2]) / 2.0))

    cam_data = bpy.data.cameras.new("ACCEPT_CAM")
    cam_data.type = "ORTHO"
    cam_data.clip_start = 0.01 * h
    cam_data.clip_end = 40.0 * h
    cam = bpy.data.objects.new("ACCEPT_CAM", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    rig = light_rig(scene, centre, h)
    mats = {"preview": preview_material(cfg["textures"]), "wire": wire_material()}
    cull = bool(cfg.get("backface_culling"))  # правила v2 (C22)
    if cull:
        for m in mats.values():
            cull_back_faces(m, engine)
    hand_view = cfg.get("hand_view") or "fixed"  # правила v2: "visibility" (C30)
    hand_views = {}
    frames = []

    def shot(name, target, az, el, ortho, material, note="", res=(None, None)):
        """Кадр орто-камерой. res — (x, y) в пикселях; по умолчанию квадрат size. ortho_scale Blender относит к
        большей стороне кадра (sensor_fit AUTO): у панели 600x1200 ortho — высота, ширина = ortho / 2."""
        assign(meshes, mats[material])
        d = direction(az, el)
        cam.location = Vector(target) + d * (10.0 * h)
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        cam_data.ortho_scale = ortho
        rig.location = Vector(target)
        rig.rotation_euler = (0.0, 0.0, math.radians(az))
        scene.render.resolution_x = res[0] or size
        scene.render.resolution_y = res[1] or size
        bpy.context.view_layer.update()
        scene.render.filepath = os.path.join(raw_dir, name + ".png")
        bpy.ops.render.render(write_still=True)
        scene.render.resolution_x = scene.render.resolution_y = size
        frames.append({"name": name + (".png" if res[0] else ".jpg"), "material": material, "azimuth_deg": az,
                       "elevation_deg": el, "ortho_scale_m": round(ortho, 4),
                       "target_m": [round(float(v), 4) for v in target], "note": note,
                       **({"resolution_px": [res[0], res[1]]} if res[0] else {})})

    for a in TURN_ANGLES:
        shot("turn-%03d" % a, centre, a, 0, turn_scale, "preview")

    # close-head: вершины группы head (вес >= 0,5); нет — верх 22 % роста
    hp = group_coords(meshes, rest, "head")
    if hp is not None and len(hp) >= 10:
        hmn, hmx = hp.min(axis=0), hp.max(axis=0)
        tgt = Vector(((hmn + hmx) / 2).tolist())
        ortho = float((hmx - hmn).max()) * 1.35
        src = "vertex group head (%d вершин, вес >= 0,5)" % len(hp)
    else:
        tgt = Vector((0.0, 0.0, float(mx[2]) - 0.11 * h))
        ortho = 0.30 * h
        src = "нет группы head: верх 22 % роста"
        warnings.append("close-head: " + src)
    shot("close-head", tgt, 25, 10, ortho, "preview", src)
    head_frame = (tgt, ortho, src)

    # Кисти: группы hand.L / hand.R (вес >= 0,5); масштаб — от размера кисти (решение скилла: 3 габарита кисти,
    # не меньше 12 % и не больше 25 % роста — увеличение x4...x8 против turn-*)
    wbone = None
    if arm is not None:
        wbone = next((b for b in ("weapon.L", "weapon.R") if b in arm.data.bones), None)
    hands = {}
    for side in ("L", "R"):
        pts = group_coords(meshes, rest, "hand." + side)
        if pts is not None and len(pts) >= 10:
            hands[side] = pts

    # close-weapon: крупный план ХВАТА — точка хвата = голова кости оружия (HANDBOOK §2.6), рядом кисть этой стороны;
    # не всё оружие (длинный лук или посох в рамке «всё оружие» — почти полный рост)
    az_w = 35 if (wbone or "").endswith(".L") else -35
    if wbone:
        b = arm.data.bones[wbone]
        grip = np.array(arm.matrix_world @ b.head_local)
        hand = hands.get(wbone[-1])
        if hand is not None:
            hmn_, hmx_ = hand.min(axis=0), hand.max(axis=0)
            ext = float((hmx_ - hmn_).max())
            tgt = Vector(((grip + (hmn_ + hmx_) / 2) / 2).tolist())
            ortho = clamp_close_scale(3.0 * ext, h)
            src = "хват: голова кости %s + кисть hand.%s (%d вершин), 3 габарита кисти" % (wbone, wbone[-1], len(hand))
        else:
            tgt = Vector(grip.tolist())
            ortho = clamp_close_scale(0.0, h)
            src = "хват: голова кости %s, нет группы hand.%s — 12 %% роста" % (wbone, wbone[-1])
            warnings.append("close-weapon: " + src)
    else:
        tgt = Vector((0.0, 0.0, float(mn[2]) + 0.72 * h))
        ortho = 0.55 * h
        src = "нет кости weapon.L/R: верхняя часть фигуры"
        warnings.append("close-weapon: " + src)
    shot("close-weapon", tgt, az_w, 10, ortho, "preview", src)

    # close-hands: две портретные панели 600x1200 (слева hand.R, справа hand.L — как у фигуры, стоящей лицом к нам);
    # только при арматуре (у пропа кистей нет)
    if arm is not None:
        hand_bvh = figure_bvh(meshes, rest) if hand_view == "visibility" else None
        for side, az_h in (("R", -35), ("L", 35)):
            pts = hands.get(side)
            if pts is not None:
                hmn_, hmx_ = pts.min(axis=0), pts.max(axis=0)
                ext = float((hmx_ - hmn_).max())
                tgt = Vector(((hmn_ + hmx_) / 2).tolist())
                ortho = clamp_close_scale(3.0 * ext, h)
                src = "vertex group hand.%s (%d вершин, вес >= 0,5), 3 габарита кисти" % (side, len(pts))
                if hand_bvh is not None:  # C30: щит или другая деталь на предплечье закрывает кисть с ракурса по умолчанию
                    sample = pts[np.linspace(0, len(pts) - 1, min(len(pts), POSE04B_SAMPLE)).astype(int)]
                    vis = {a: visible_share(hand_bvh, sample, a, 10, 1e-4 * h)
                           for a in [az_h] + [a for a in HAND_CANDIDATES if a % 360 != az_h % 360]}
                    az_new, share, moved = best_panel_azimuth(vis, az_h, HAND_MIN_VISIBLE)
                    hand_views[side] = {"default_azimuth_deg": az_h, "default_visible_share": round(vis[az_h], 4),
                                        "azimuth_deg": az_new, "visible_share": round(share, 4), "moved": moved,
                                        "visibility": {str(a): round(v, 4) for a, v in vis.items()},
                                        "min_share": HAND_MIN_VISIBLE}
                    if moved:
                        src += "; ракурс az %d по видимости кисти (%.0f %% против %.0f %% с az %d: деталь на предплечье)" % (
                            az_new, share * 100, vis[az_h] * 100, az_h)
                        warnings.append("close-hands: hand.%s снята с az %d (с az %d видно %.0f %% кисти)"
                                        % (side, az_new, az_h, vis[az_h] * 100))
                    az_h = az_new
            else:
                bone = arm.data.bones.get("hand." + side)
                tgt = (arm.matrix_world @ bone.head_local) if bone else Vector((0.0, 0.0, float(mn[2]) + 0.55 * h))
                ortho = clamp_close_scale(0.0, h)
                src = "нет группы hand.%s: %s, 12 %% роста" % (side, "голова кости" if bone else "середина фигуры")
                warnings.append("close-hands: " + src)
            shot("close-hands-" + side, tgt, az_h, 10, ortho, "preview", src, res=(size // 2, size))

    # close-attack (F74): атакующая конечность без оружия (attack_bone — сокет-кость заявки) — бок и спина 3/4,
    # две портретные панели; рамка — вся группа кости (когти целиком) с запасом 15 %, не меньше 12 % роста
    attack = None
    ab = cfg.get("attack_bone")
    if arm is not None and ab:
        if ab not in arm.data.bones:
            warnings.append("close-attack: нет кости %s в арматуре — кадр не снят" % ab)
        else:
            side = ab[-1] if ab[-2:] in (".L", ".R") else "R"
            pts = group_coords(meshes, rest, ab)
            if pts is not None and len(pts) >= 10:
                tgt = Vector(((pts.min(axis=0) + pts.max(axis=0)) / 2).tolist())
                src = "vertex group %s (%d вершин, вес >= 0,5)" % (ab, len(pts))
            else:
                pts = None
                tgt = arm.matrix_world @ arm.data.bones[ab].head_local
                src = "нет группы %s: голова кости, 12 %% роста" % ab
                warnings.append("close-attack: " + src)
            for tag, az_a in ATTACK_AZ[side]:
                ortho = (max(panel_fit_scale(pts, tgt, az_a, 10), CLOSE_MIN * h) if pts is not None
                         else clamp_close_scale(0.0, h))
                shot("close-attack-" + tag, tgt, az_a, 10, ortho, "preview",
                     "%s, %s (az %d)" % (src, {"side": "бок", "back": "спина 3/4"}[tag], az_a), res=(size // 2, size))
            attack = {"bone": ab, "source": cfg.get("attack_source"), "side": side,
                      "panels": [{"panel": t, "azimuth_deg": a} for t, a in ATTACK_AZ[side]], "framing": src}

    # close-torso: группа spine (вес >= 0,5), рамка не больше 45 % роста
    if arm is not None:
        sp = group_coords(meshes, rest, "spine")
        if sp is not None and len(sp) >= 10:
            smn, smx = sp.min(axis=0), sp.max(axis=0)
            tgt = Vector(((smn + smx) / 2).tolist())
            ortho = min(max(float((smx - smn).max()) * 1.15, 0.20 * h), 0.45 * h)
            src = "vertex group spine (%d вершин, вес >= 0,5)" % len(sp)
        else:
            tgt = Vector((0.0, 0.0, float(mn[2]) + 0.62 * h))
            ortho = 0.35 * h
            src = "нет группы spine: 62 % роста, рамка 35 % роста"
            warnings.append("close-torso: " + src)
        shot("close-torso", tgt, 20, 5, ortho, "preview", src)

        # Крупные планы со спины (калибровка 2026-10-09, раунд 3): затылок, волосы/змеи сзади, спина, задняя сторона
        # плеч, колчан, спина плаща. Без них дефект сзади был либо невидим, либо сразу «полный рост» (балл 1,0).
        htgt, hortho, hsrc = head_frame
        shot("close-head-back", htgt, 205, 10, hortho, "preview", hsrc + ", со спины (az 205)")
        shot("close-torso-back", tgt, 200, 5, ortho, "preview", src + ", со спины (az 200)")

        # Ноги и низ одежды (группы hips, leg_*, foot.*): спереди 3/4 и сзади 3/4, рамка 25–60 % роста
        lp = [group_coords(meshes, rest, g) for g in LEG_GROUPS]
        lp = [p for p in lp if p is not None and len(p)]
        if lp and sum(len(p) for p in lp) >= 10:
            lpts = np.concatenate(lp)
            lmn, lmx = lpts.min(axis=0), lpts.max(axis=0)
            ltgt = Vector(((lmn + lmx) / 2).tolist())
            lortho = min(max(float((lmx - lmn).max()) * 1.10, 0.25 * h), 0.60 * h)
            lsrc = "vertex groups %s (%d вершин, вес >= 0,5)" % ("+".join(LEG_GROUPS), len(lpts))
        else:
            ltgt = Vector((0.0, 0.0, float(mn[2]) + 0.27 * h))
            lortho = 0.55 * h
            lsrc = "нет групп ног: нижние 55 % роста"
            warnings.append("close-legs: " + lsrc)
        shot("close-legs", ltgt, 340, 5, lortho, "preview", lsrc + ", спереди-справа (az 340)")
        shot("close-legs-back", ltgt, 160, 5, lortho, "preview", lsrc + ", со спины (az 160)")

    # close-base: подставка (объекты из --base) сверху-сбоку; без подставки — нижние 22 % модели
    base_meshes = [o for o in meshes if o.name in base_objs]
    if base_meshes:
        bp = np.concatenate([rest[o.name] for o in base_meshes])
        bmn, bmx = bp.min(axis=0), bp.max(axis=0)
        tgt = Vector(((bmn + bmx) / 2).tolist())
        ortho = view_fit_scale(bp, tgt, 30, 25, margin=1.12)
        src = "подставка: %s" % ", ".join(sorted(o.name for o in base_meshes))
    else:
        low = allc[allc[:, 2] <= float(mn[2]) + 0.22 * h]
        tgt = Vector(((low.min(axis=0) + low.max(axis=0)) / 2).tolist())
        ortho = view_fit_scale(low, tgt, 30, 25, margin=1.12)
        src = "нет подставки: нижние 22 % модели"
        warnings.append("close-base: " + src)
    shot("close-base", tgt, 30, 25, ortho, "preview", src)

    # Каркас: масштаб turn-кадров, но не меньше проекции модели на этот ракурс (широкий проп на el 15° иначе обрезан)
    # wire-back (az 180): след формы для спины, затылка и плаща сзади (калибровка 2026-10-09, раунд 4)
    for wname, waz, wel in (("wire-front", 0, 0), ("wire-34", 45, 15), ("wire-back", 180, 0)):
        wscale = max(turn_scale, view_fit_scale(allc, centre, waz, wel))
        shot(wname, centre, waz, wel, wscale, "wire")

    poses_out = []
    pose_checks = {}
    if arm is not None:
        families, tests, families_ext = probe_definitions(cfg["probe_source"])
        names = set(arm.data.bones.keys())
        fam = max(families, key=lambda f: sum(1 for v in families[f].values() if v in names))
        fmap = dict(families_ext.get(fam, {}), **families[fam])
        tmap = {t[0]: t for t in tests}
        fig_meshes = [o for o in meshes if o.name not in base_objs]
        dom = dominant_groups(fig_meshes)

        def weapon_check(posed_by):
            """3D-зазоры жёсткого оружия в КАЖДОЙ позе (калибровка 2026-10-09, раунд 3): с головой (вместе с волосами,
            змеями, короной — группа head) и с телом (вершины фигуры без подставки, чья главная группа не оружие, не
            кисть и не предплечье руки с оружием — их оружие касается по построению хвата). На орто-кадре не понять,
            перед головой клинок или сквозь неё; число решает. → (chk, вершины head, вершины оружия)."""
            hd = group_coords(meshes, posed_by, "head")
            wp = group_coords(meshes, posed_by, wbone) if wbone else None
            chk = {"weapon_bone": wbone}
            if wp is not None and len(wp):
                side = wbone[-1]
                body = body_coords(fig_meshes, posed_by, dom,
                                   {wbone, "hand." + side, "arm_lower." + side, "head"})
                if hd is not None and len(hd):
                    dh = kd_min_distance(wp, hd)
                    chk.update({"weapon_head_min_distance_m": round(dh, 5), "weapon_head_contact": dh < CONTACT_M})
                if body is not None and len(body):
                    db = kd_min_distance(wp, body)
                    chk.update({"weapon_body_min_distance_m": round(db, 5), "weapon_body_contact": db < CONTACT_M})
                chk["contact_threshold_m"] = CONTACT_M
            else:
                chk["note"] = "нет кости или группы оружия: зазоры не считаются"
            return chk, hd, wp

        def pose_shot(pname, az, el, note, posed):
            pmn, pmx = posed.min(axis=0), posed.max(axis=0)
            pr = float(np.sqrt(posed[:, 0] ** 2 + posed[:, 1] ** 2).max())
            ptgt = Vector((0.0, 0.0, float(pmn[2] + pmx[2]) / 2.0))
            ortho = max(max(float(pmx[2] - pmn[2]), 2.0 * pr, h) * 1.10, view_fit_scale(posed, ptgt, az, el))
            shot(pname, ptgt, az, el, ortho, "preview", note)

        for pname, combo, az, el in POSES:
            reset_pose(arm)
            applied = []
            for tname in combo:
                _n, key, axis, deg, _exp = tmap[tname]
                bone = fmap.get(key)
                if bone not in arm.pose.bones:
                    warnings.append("%s: нет кости %s (%s)" % (pname, bone, tname))
                    continue
                rotate_bone(arm, bone, axis, deg)
                applied.append({"test": tname, "bone": bone, "axis": axis, "deg": deg})
            posed_by = evaluated_coords(meshes)
            posed = np.concatenate(list(posed_by.values()))
            pose_shot(pname, az, el, "+".join(combo), posed)
            poses_out.append({"name": pname + ".jpg", "family": fam, "rotations": applied})
            chk, hd, wp = weapon_check(posed_by)
            pose_checks[pname] = chk
            if pname == "pose-03":
                # Второй ракурс той же позы: длинное жёсткое оружие в сочетании проб (корпус + голова) может встать
                # перед лицом. pose-03b снимается с азимута, где проекции оружия и головы дальше всего друг от друга.
                az_b = (az + 180) % 360
                if hd is not None and wp is not None and len(hd) and len(wp):
                    az_b, gap2d = best_separating_azimuth(wp, hd, el=10)
                    chk["pose-03b_projected_gap_m"] = round(gap2d, 5)
                else:
                    chk["note_03b"] = "нет группы оружия или головы: pose-03b — противоположный ракурс"
                chk["pose-03b_azimuth_deg"] = az_b
                pose_shot("pose-03b", az_b, 10, "+".join(combo) + ", второй ракурс", posed)
                poses_out.append({"name": "pose-03b.jpg", "family": fam, "rotations": applied,
                                  "note": "та же поза, что pose-03, другой ракурс"})
            if pname == "pose-04":
                # pose-04b (F77): второй ракурс — где таз и поднятое бедро видны лучше всего (у Achilles с az 70 их
                # закрывал щит): доля вершин цели, из которых луч к камере ни во что не упирается
                thigh = arm.data.bones.get(applied[0]["bone"]) if applied else None
                groups = ({thigh.name} | ({thigh.parent.name} if thigh.parent else set())) if thigh else set()
                tp = [posed_by[o.name][np.isin(dom[o.name], list(groups))] for o in fig_meshes]
                tp = np.concatenate([x for x in tp if len(x)]) if any(len(x) for x in tp) else np.zeros((0, 3))
                if len(tp):
                    tp = tp[np.linspace(0, len(tp) - 1, min(len(tp), POSE04B_SAMPLE)).astype(int)]
                    bvh = figure_bvh(meshes, posed_by)
                    vis = {a: visible_share(bvh, tp, a, el, 1e-4 * h) for a in POSE04B_CANDIDATES}
                    az_b, share = best_visible_azimuth(vis, az, POSE04B_MIN_SEP)
                    chk.update({"pose-04b_azimuth_deg": az_b, "pose-04b_visible_share": round(share, 4),
                                "pose-04b_visibility": {str(a): round(v, 4) for a, v in vis.items()},
                                "pose-04b_target_groups": sorted(groups), "pose-04b_target_vertices": int(len(tp))})
                else:
                    az_b = (360 - az) % 360
                    chk["note_04b"] = "нет вершин групп %s: pose-04b — зеркальный ракурс" % sorted(groups)
                    chk["pose-04b_azimuth_deg"] = az_b
                pose_shot("pose-04b", az_b, el, "+".join(combo) + ", второй ракурс (видимость таза и бедра)", posed)
                poses_out.append({"name": "pose-04b.jpg", "family": fam, "rotations": applied,
                                  "note": "та же поза, что pose-04, ракурс с наибольшей видимостью таза и бедра"})

        # pose-05 (F129): рука оружия (без оружия — атакующая, иначе правая) вперёд, со спины 3/4 этой стороны; рамка —
        # верх фигуры от тазобедренного сустава, оружие в рамку не входит (кадр обрезан намеренно)
        side5 = (wbone[-1] if wbone else None) or ((attack or {}).get("side")) or "R"
        reset_pose(arm)
        applied = []
        for key, axis, deg in ARM_FORWARD:
            bone = fmap.get("%s_%s" % (key, side5.lower()))
            if bone not in arm.pose.bones:
                warnings.append("pose-05: нет кости %s_%s (%s)" % (key, side5.lower(), bone))
                continue
            rotate_bone(arm, bone, axis, deg)
            applied.append({"bone": bone, "axis": axis, "deg": deg})
        posed_by = evaluated_coords(meshes)
        hip = arm.data.bones.get(fmap.get("thigh_" + side5.lower()) or "")
        hip_z = float((arm.matrix_world @ hip.head_local).z) if hip else float(mn[2]) + 0.45 * h
        up = [posed_by[o.name][(posed_by[o.name][:, 2] >= hip_z) & ~np.isin(dom[o.name], [wbone] if wbone else [])]
              for o in fig_meshes]
        up = np.concatenate([x for x in up if len(x)]) if any(len(x) for x in up) else \
            np.concatenate(list(posed_by.values()))
        az5 = POSE05_AZ[side5]
        tgt5 = Vector(((up.min(axis=0) + up.max(axis=0)) / 2).tolist())
        shot("pose-05", tgt5, az5, POSE05_EL, view_fit_scale(up, tgt5, az5, POSE05_EL), "preview",
             "рука %s вперёд (плечо X %d, предплечье X %d), спина 3/4 az %d; рамка — верх фигуры от z %.3f м, без оружия"
             % (side5, ARM_FORWARD[0][2], ARM_FORWARD[1][2], az5, hip_z))
        chk5, _hd, _wp = weapon_check(posed_by)
        chk5.update({"arm_side": side5, "frame_from_z_m": round(hip_z, 4)})
        pose_checks["pose-05"] = chk5
        poses_out.append({"name": "pose-05.jpg", "family": fam, "rotations": applied,
                          "note": "рука %s вперёд, вид со спины 3/4: кромки проймы и плаща за подмышкой (F129)" % side5})
        reset_pose(arm)

    # UV0 для uv-layout.png (рисует обёртка): треугольники в UV, острова, границы островов
    uvdata = {}
    island_counts = {}
    uv_shell = {}
    for o in meshes:
        me = o.data
        if not me.uv_layers:
            warnings.append("%s: нет UV" % o.name)
            continue
        uvl = me.uv_layers.get("UVMap") or me.uv_layers[0]
        me.calc_loop_triangles()
        nl = len(me.loops)
        uv = np.empty(nl * 2, dtype=np.float64)
        uvl.data.foreach_get("uv", uv)
        uv = uv.reshape(-1, 2)
        lv = np.empty(nl, dtype=np.int64)
        me.loops.foreach_get("vertex_index", lv)
        tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
        me.loop_triangles.foreach_get("loops", tri)
        tri = tri.reshape(-1, 3)
        tri_poly = np.empty(len(me.loop_triangles), dtype=np.int64)
        me.loop_triangles.foreach_get("polygon_index", tri_poly)
        keep_poly = None  # правила v2 (C36): полигоны оболочки П3-3 не входят в острова, треугольники и границы
        if cfg.get("uv_shell"):
            t_uv, t_co = uv[tri], rest[o.name][lv[tri]]  # мировые метры (локальные FBX — в сантиметрах)
            copy_m = shell_copy_mask(t_uv, t_co)
            bridge_m = zero_uv_area_mask(t_uv) & bool(copy_m.any())  # мосты — только у сетки с оболочкой
            drop = copy_m | bridge_m
            e1, e2 = t_uv[:, 1] - t_uv[:, 0], t_uv[:, 2] - t_uv[:, 0]
            flipped = (e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) < 0
            uv_shell[o.name] = {"shell_copy_triangles": int(copy_m.sum()), "rim_bridge_triangles": int(bridge_m.sum()),
                                "uv_flipped_triangles_without_shell": int((flipped & ~drop).sum()),
                                "uv_flipped_triangles_all": int(flipped.sum())}
            if drop.any():
                keep_poly = np.ones(len(me.polygons), bool)
                keep_poly[np.unique(tri_poly[drop])] = False
                tri, tri_poly = tri[~drop], tri_poly[~drop]
        # острова: полигоны, связанные ребром с совпадающими UV на обоих концах
        ps = np.empty(len(me.polygons), dtype=np.int64)
        pt = np.empty(len(me.polygons), dtype=np.int64)
        me.polygons.foreach_get("loop_start", ps)
        me.polygons.foreach_get("loop_total", pt)
        loop_poly = np.repeat(np.arange(len(me.polygons)), pt)
        nxt = np.arange(nl) + 1
        last = ps + pt - 1
        nxt[last] = ps
        va, vb = lv, lv[nxt]
        ua, ub = uv, uv[nxt]
        swap = va > vb
        k0, k1 = np.where(swap, vb, va), np.where(swap, va, vb)
        q = np.round(np.where(swap[:, None], np.hstack([ub, ua]), np.hstack([ua, ub])) * 1e6).astype(np.int64)
        key = np.stack([k0, k1], axis=1)
        loops_in = np.arange(nl) if keep_poly is None else np.nonzero(keep_poly[loop_poly])[0]
        order = loops_in[np.lexsort((q[loops_in, 3], q[loops_in, 2], q[loops_in, 1], q[loops_in, 0], key[loops_in, 1],
                                     key[loops_in, 0]))]
        parent = list(range(len(me.polygons)))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        prev = None
        for li in order:
            sig = (key[li, 0], key[li, 1], q[li, 0], q[li, 1], q[li, 2], q[li, 3])
            if prev is not None and sig == prev[0]:
                a, b = find(int(loop_poly[li])), find(int(loop_poly[prev[1]]))
                if a != b:
                    parent[a] = b
            prev = (sig, li)
        roots = np.array([find(i) for i in range(len(me.polygons))])
        if keep_poly is None:
            _u, island = np.unique(roots, return_inverse=True)
            island_counts[o.name] = int(island.max() + 1) if len(island) else 0
        else:
            _u, isl_kept = np.unique(roots[keep_poly], return_inverse=True)
            island = np.full(len(me.polygons), -1, np.int64)
            island[keep_poly] = isl_kept.ravel()
            island_counts[o.name] = int(isl_kept.max() + 1) if len(isl_kept) else 0
        # граница острова: ребро (вершины + UV) встречается в одном полигоне
        sigs = np.hstack([key, q])
        _s, inv_idx, cnt = np.unique(sigs[loops_in], axis=0, return_inverse=True, return_counts=True)
        boundary = np.zeros(nl, bool)
        boundary[loops_in] = cnt[inv_idx.ravel()] == 1
        uvdata[o.name + "__uv"] = uv.astype(np.float32)
        uvdata[o.name + "__tri"] = tri.astype(np.int32)
        uvdata[o.name + "__tri_island"] = island[tri_poly].astype(np.int32)
        uvdata[o.name + "__bedge"] = np.stack([np.arange(nl)[boundary], nxt[boundary]], axis=1).astype(np.int32)
    np.savez_compressed(os.path.join(work_dir, "uv-data.npz"), **uvdata)

    info = {
        "blender": bpy.app.version_string, "engine": engine, "view_transform": "AgX",
        "imported_objects": sorted(o.name for o in imported),
        "meshes": {o.name: {"triangles": sum(len(p.vertices) - 2 for p in o.data.polygons),
                            "uv_islands": island_counts.get(o.name)} for o in meshes},
        "armature": None if arm is None else {"name": arm.name, "bones": len(arm.data.bones),
                                              "weapon_bone": wbone},
        "bounds_m": {"min": [round(float(v), 4) for v in mn], "max": [round(float(v), 4) for v in mx],
                     "height": round(h, 4), "radius_from_pivot": round(radius, 4)},
        "frames": frames, "poses": poses_out, "pose_checks": pose_checks, "warnings": warnings,
        "attack": attack,
    }
    if cfg.get("rules") is not None:  # правила v2 (C22, C30, C36); без них capture.json прежний
        info["rules"] = {"version": cfg["rules"], "backface_culling": cull, "hand_view": hand_view,
                         "hands": hand_views or None, "uv_shell": uv_shell or None}
    with open(os.path.join(work_dir, "capture.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    print("CAPTURE_OK", len(frames))


main()
