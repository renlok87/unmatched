"""Живой Blender (:9877): загрузить FBX/GLB с ригом в ЧИСТУЮ сцену и показать кости спереди.

Выполняется через blender_mcp.py exec. Путь к файлу берётся из переменной
RIG_VIEW_PATH внутри текста (подставляется вызывающей стороной через exec-str)
либо из bpy.app.driver_namespace['rig_view_path'].
Сцена :9877 — рабочая песочница этой задачи; исходные файлы не сохраняются.
"""
import math

import bpy
from mathutils import Quaternion

path = bpy.app.driver_namespace.get("rig_view_path")
pose = bpy.app.driver_namespace.get("rig_view_pose", {})  # {bone: (axis, deg)}

# ВНИМАНИЕ: не вызывать read_factory_settings в живом Blender — это выгружает
# аддон MCP и роняет сервер порта (проверено 2026-09-28). Чистим данные вручную.
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.armatures, bpy.data.materials,
             bpy.data.images, bpy.data.actions):
    for item in list(coll):
        if item.users == 0:
            coll.remove(item)
if path.lower().endswith(".fbx"):
    bpy.ops.import_scene.fbx(filepath=path)
else:
    bpy.ops.import_scene.gltf(filepath=path)

arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
arm.show_in_front = True
arm.data.display_type = "STICK"
for b in arm.pose.bones:
    b.rotation_mode = "XYZ"
for name, (axis, deg) in pose.items():
    pb = arm.pose.bones.get(name)
    if pb:
        idx = "XYZ".index(axis)
        rot = list(pb.rotation_euler)
        rot[idx] = math.radians(deg)
        pb.rotation_euler = rot
bpy.context.view_layer.update()

for win in bpy.context.window_manager.windows:
    for area in win.screen.areas:
        if area.type != "VIEW_3D":
            continue
        sp = area.spaces.active
        sp.shading.type = "SOLID"
        sp.shading.color_type = "TEXTURE"
        sp.overlay.show_bones = True
        r3d = sp.region_3d
        r3d.view_perspective = "ORTHO"
        # фронт: камера смотрит вдоль +Y (Blender Front = -Y сторона)
        r3d.view_rotation = Quaternion((math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0))
        with bpy.context.temp_override(window=win, area=area,
                                       region=next(r for r in area.regions if r.type == "WINDOW")):
            bpy.ops.view3d.view_all(center=False)
print("LIVE_VIEW_OK", arm.name, len(arm.data.bones))
