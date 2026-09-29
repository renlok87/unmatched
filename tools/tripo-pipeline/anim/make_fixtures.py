"""Пересоздаёт отслеживаемые фикстуры валидатора клипов P1.6 (только headless).

ТОЛЬКО headless (`blender -b`): вызывается read_factory_settings, который в живом
Blender (MCP :9876/:9877) выгружает аддон MCP и очищает сцену. Без `-b` скрипт бросает
RuntimeError и ничего не делает; процесс Blender остаётся жив. SystemExit/sys.exit/os._exit
для guard не годятся: в живом Blender они завершают весь процесс.

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/tripo-pipeline/anim/make_fixtures.py -- [bvh|glb|tripo|all] [--out-dir=<dir>]

bvh   — round-trip BVH из AM_Medusa_LungeAttack.fbx (Z-up, как пишет Blender) для ветки BVH;
glb   — GLB из того же FBX: меш со скином на арматуре, без картинок и материалов, для ветки GLB
        (при импорте glTF появляется служебный Icosphere, арматура масштабирована 0.01);
tripo — FBX пресета Tripo «стоя_отдых», извлечённый из source/*.zip (без текстур .fbm);
rigv2 — синтетическая фикстура контракта рига v2 (волна 4, W4-D) из того же AM_Medusa_LungeAttack.fbx:
        объект арматуры SKEL_UM_Humanoid, кость weapon -> weapon.L (группы вершин и кривые следуют
        за переименованием), rest-поза и меш повёрнуты на +90° вокруг Z жёстко (EditBone.transform
        roll=True, как UM_FBX_v1 в candidate_build/core.py), экспорт FBX с осями UM_FBX_v1 и
        закреплёнными временем/UUID (make_fbx_deterministic). Не клип для игры и не производственный
        экспорт: единицы не патчатся (валидатор меряет в долях роста). Пишет в
        docs/art-pipeline/animation-library/fixtures/rig-contract-v2/ (--out-dir не влияет).
Исходники только читаются. По умолчанию bvh/glb/tripo пишут в
art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16/fixtures/; all = bvh, glb, tripo
(rigv2 — только явно).
"""
import math
import os
import sys
import zipfile

import bpy
from mathutils import Matrix

if not bpy.app.background:
    # RuntimeError, не SystemExit: SystemExit в живом Blender завершает весь процесс.
    raise RuntimeError("make_fixtures.py: только headless (blender -b)")

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RUN = os.path.join(REPO, "art/pipeline-candidates/ASSET-MEDUSA-001/tripo-rig-20260928-p16")
LUNGE_FBX = os.path.join(REPO, "blender/ASSET-MEDUSA-001/export/AM_Medusa_LungeAttack.fbx")
TRIPO_ZIP = os.path.join(RUN, "source/d562f057-ue5-forced-anim-preset-stoya-otdyh-inplace-fbx-blender.zip")
TRIPO_MEMBER = "tripo_convert_93b4445d-b871-4057-a0d7-1317f45a1548.fbx"
RIGV2_DIR = os.path.join(REPO, "docs/art-pipeline/animation-library/fixtures/rig-contract-v2")
RIGV2_NAME = "AM_RigV2_LungeAttack_weaponL.fbx"
PRESET = os.path.join(REPO, "blender/_tools/presets/UM_FBX_v1.json")
CANDIDATE_LIB = os.path.join(REPO, "tools/tripo-pipeline/blender")


def load_lunge():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=LUNGE_FBX, use_anim=True)
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    bpy.ops.object.select_all(action="DESELECT")
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    return arm


def make_bvh(out_dir):
    arm = load_lunge()
    s, e = [int(round(x)) for x in arm.animation_data.action.frame_range]
    out = os.path.join(out_dir, "AM_Medusa_LungeAttack.bvh")
    bpy.ops.export_anim.bvh(filepath=out, frame_start=s, frame_end=e)
    print("FIXTURE_OK", out, os.path.getsize(out))


def make_glb(out_dir):
    arm = load_lunge()
    for ob in bpy.context.scene.objects:
        ob.select_set(ob.type in ("ARMATURE", "MESH"))
    out = os.path.join(out_dir, "AM_Medusa_LungeAttack.glb")
    bpy.ops.export_scene.gltf(filepath=out, export_format="GLB", use_selection=True,
                              export_image_format="NONE", export_materials="NONE",
                              export_animations=True)
    print("FIXTURE_OK", out, os.path.getsize(out))


def make_tripo(out_dir):
    sub = os.path.join(out_dir, "tripo-preset-stoya-otdyh-d562")
    os.makedirs(sub, exist_ok=True)
    out = os.path.join(sub, TRIPO_MEMBER)
    with zipfile.ZipFile(TRIPO_ZIP) as z, open(out, "wb") as f:
        f.write(z.read(TRIPO_MEMBER))
    print("FIXTURE_OK", out, os.path.getsize(out))


def make_rigv2(_out_dir):
    """Синтетическая фикстура контракта v2 (см. docstring модуля)."""
    import json
    sys.path.insert(0, CANDIDATE_LIB)
    from candidate_build.core import make_fbx_deterministic  # noqa: E402 (Blender-модуль библиотеки build)
    with open(PRESET, encoding="utf-8") as f:
        preset = json.load(f)
    arm = load_lunge()
    sc = bpy.context.scene
    act = arm.animation_data.action
    s, e = [int(round(x)) for x in act.frame_range]
    sc.frame_start, sc.frame_end = s, e
    arm.name = "SKEL_UM_Humanoid"
    arm.data.name = "SKEL_UM_Humanoid"
    arm.data.bones["weapon"].name = "weapon.L"  # RNA-переименование правит группы вершин и пути кривых
    meshes = [o for o in sc.objects if o.type == "MESH"]
    if any("weapon" in m.vertex_groups for m in meshes) or not any("weapon.L" in m.vertex_groups for m in meshes):
        raise RuntimeError("vertex group weapon was not renamed to weapon.L")
    stale = [fc.data_path for fc in act.fcurves if '"weapon"' in fc.data_path] if hasattr(act, "fcurves") else []
    if stale:
        raise RuntimeError("fcurves still point at weapon: %s" % stale[:3])
    rot = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    bpy.ops.object.mode_set(mode="EDIT")
    for bone in arm.data.edit_bones:
        bone.transform(rot, scale=False, roll=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    for m in meshes:
        m.data.transform(rot)
    os.makedirs(RIGV2_DIR, exist_ok=True)
    out = os.path.join(RIGV2_DIR, RIGV2_NAME)
    bpy.ops.object.select_all(action="DESELECT")
    for ob in [arm] + meshes:
        ob.select_set(True)
    bpy.context.view_layer.objects.active = arm
    restore = make_fbx_deterministic()
    try:
        bpy.ops.export_scene.fbx(
            filepath=out, use_selection=True, object_types={"ARMATURE", "MESH"},
            apply_unit_scale=bool(preset["apply_unit_scale"]), apply_scale_options=preset["apply_scale_options"],
            axis_forward=preset["axis_forward"], axis_up=preset["axis_up"],
            add_leaf_bones=bool(preset["add_leaf_bones"]), primary_bone_axis=preset["primary_bone_axis"],
            secondary_bone_axis=preset["secondary_bone_axis"], mesh_smooth_type=preset["mesh_smooth_type"],
            bake_anim=True, bake_anim_use_all_bones=bool(preset["bake_anim_use_all_bones"]),
            bake_anim_use_nla_strips=bool(preset["bake_anim_use_nla_strips"]),
            bake_anim_use_all_actions=bool(preset["bake_anim_use_all_actions"]),
            bake_anim_force_startend_keying=bool(preset["bake_anim_force_startend_keying"]),
            use_custom_props=False, path_mode="STRIP", embed_textures=False)
    finally:
        restore()
    print("FIXTURE_OK", out, os.path.getsize(out))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    what = next((a for a in argv if not a.startswith("--")), "all")
    out_dir = next((a.split("=", 1)[1] for a in argv if a.startswith("--out-dir=")), os.path.join(RUN, "fixtures"))
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    jobs = {"bvh": make_bvh, "glb": make_glb, "tripo": make_tripo, "rigv2": make_rigv2}
    if what not in jobs and what != "all":
        raise SystemExit(f"unknown fixture: {what}")
    for name, fn in jobs.items():
        if what == name or (what == "all" and name != "rigv2"):
            fn(out_dir)


main()
