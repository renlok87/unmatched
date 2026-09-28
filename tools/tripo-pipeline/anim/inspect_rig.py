"""Инспекция скелета и весов в FBX/GLB/.blend (только чтение исходника).

ТОЛЬКО headless (`blender -b`): для FBX/GLB вызывается read_factory_settings, который в
живом Blender (MCP :9876/:9877) выгружает аддон MCP и очищает сцену. Без `-b` скрипт бросает
RuntimeError и ничего не делает; процесс Blender остаётся жив. SystemExit/sys.exit/os._exit
для guard не годятся: в живом Blender они завершают весь процесс.

Запуск (headless, пустая сцена):
  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/tripo-pipeline/anim/inspect_rig.py -- <file> <out.json> [--glb-bone-dir]

Пишет JSON: кости (имя, родитель, head/tail/roll в мировых координатах), число
влияний на вершину по мешам, пустые/незадействованные группы, габариты мешей,
главную кость по долям веса для каждого меша/объекта, число действий (actions).
Служебные меши импортёра glTF (коллекция glTF_not_exported, Icosphere формы костей)
в меши и общий габарит не входят, их имена пишутся в helper_objects_excluded.
Файл-источник не изменяется: импорт идёт в пустую сцену, сохранения нет.
"""
import json
import os
import sys
from collections import Counter, defaultdict

import bpy
from mathutils import Vector

if not bpy.app.background:
    # RuntimeError, не SystemExit: SystemExit в живом Blender завершает весь процесс.
    raise RuntimeError("inspect_rig.py: только headless (blender -b)")

GLTF_HELPER_COLLECTION = "glTF_not_exported"
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))


def _repo_rel(path):
    """Путь относительно корня репозитория (прямые слэши); вне репозитория — абсолютный."""
    p = os.path.abspath(path)
    try:
        rel = os.path.relpath(p, REPO)
    except ValueError:  # другой диск
        return p.replace("\\", "/")
    return (p if rel.startswith("..") else rel).replace("\\", "/")


def _args():
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    if len(argv) < 2:
        raise SystemExit("usage: -- <file> <out.json>")
    return argv[0], argv[1]


def _import(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".blend":
        bpy.ops.wm.open_mainfile(filepath=path)
    elif ext == ".fbx":
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=path, automatic_bone_orientation=False)
    elif ext in (".glb", ".gltf"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=path)
    else:
        raise SystemExit(f"unsupported: {ext}")


def _r(v, n=4):
    return [round(float(x), n) for x in v]


def main():
    src, out = _args()
    _import(src)
    scene = bpy.context.scene
    report = {
        "source": _repo_rel(src),
        "source_bytes": os.path.getsize(src),
        "scene_fps": scene.render.fps / scene.render.fps_base,
        "unit_scale": scene.unit_settings.scale_length,
        "armatures": [],
        "meshes": [],
        "actions": [],
    }
    arms = [o for o in scene.objects if o.type == "ARMATURE"]
    for arm in arms:
        mw = arm.matrix_world
        bones = []
        for b in arm.data.bones:
            bones.append({
                "name": b.name,
                "parent": b.parent.name if b.parent else None,
                "head": _r(mw @ b.head_local),
                "tail": _r(mw @ b.tail_local),
                "length": round((mw @ b.tail_local - mw @ b.head_local).length, 5),
                "use_deform": b.use_deform,
                "children": [c.name for c in b.children],
            })
        roots = [b["name"] for b in bones if b["parent"] is None]
        report["armatures"].append({
            "object": arm.name,
            "parent_object": arm.parent.name if arm.parent else None,
            "location": _r(arm.location),
            "rotation_euler_deg": _r([x * 57.29578 for x in arm.rotation_euler], 2),
            "scale": _r(arm.scale),
            "bone_count": len(bones),
            "root_bones": roots,
            "bones": bones,
            "animation_action": (arm.animation_data.action.name
                                 if arm.animation_data and arm.animation_data.action else None),
        })
    report["helper_objects_excluded"] = []
    for ob in scene.objects:
        if ob.type != "MESH":
            continue
        if any(c.name == GLTF_HELPER_COLLECTION for c in ob.users_collection):
            # служебная форма костей импортёра glTF (Icosphere) — не часть модели
            report["helper_objects_excluded"].append(ob.name)
            continue
        me = ob.data
        mod_arm = [m.object.name for m in ob.modifiers if m.type == "ARMATURE" and m.object]
        gnames = {g.index: g.name for g in ob.vertex_groups}
        infl = Counter()
        weight_by_group = defaultdict(float)
        unweighted = 0
        for v in me.vertices:
            ws = [(g.group, g.weight) for g in v.groups if g.weight > 1e-4]
            infl[len(ws)] += 1
            if not ws:
                unweighted += 1
            tot = sum(w for _, w in ws) or 1.0
            for gi, w in ws:
                weight_by_group[gnames.get(gi, str(gi))] += w / tot
        top = sorted(weight_by_group.items(), key=lambda kv: -kv[1])[:8]
        nv = max(len(me.vertices), 1)
        corners = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
        mn = [min(c[i] for c in corners) for i in range(3)]
        mx = [max(c[i] for c in corners) for i in range(3)]
        tris = sum(len(p.vertices) - 2 for p in me.polygons)
        report["meshes"].append({
            "object": ob.name,
            "parent": ob.parent.name if ob.parent else None,
            "parent_type": ob.parent_type,
            "parent_bone": ob.parent_bone or None,
            "armature_modifiers": mod_arm,
            "vertices": len(me.vertices),
            "tris": tris,
            "materials": [m.name if m else None for m in me.materials],
            "uv_layers": [u.name for u in me.uv_layers],
            "vertex_groups": len(ob.vertex_groups),
            "influences_histogram": {str(k): v for k, v in sorted(infl.items())},
            "max_influences": max(infl) if infl else 0,
            "unweighted_vertices": unweighted,
            "top_groups_share": [[k, round(v / nv, 4)] for k, v in top],
            "bbox_min": _r(mn),
            "bbox_max": _r(mx),
        })
    for act in bpy.data.actions:
        fr = act.frame_range
        report["actions"].append({
            "name": act.name,
            "frame_start": round(fr[0], 3),
            "frame_end": round(fr[1], 3),
            "users": act.users,
        })
    allmin = [min(m["bbox_min"][i] for m in report["meshes"]) for i in range(3)] if report["meshes"] else None
    allmax = [max(m["bbox_max"][i] for m in report["meshes"]) for i in range(3)] if report["meshes"] else None
    report["overall_bbox"] = {"min": allmin, "max": allmax,
                              "height": round(allmax[2] - allmin[2], 5) if allmin else None}
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("INSPECT_OK", out, "armatures", len(arms), "meshes", len(report["meshes"]),
          "bones", [a["bone_count"] for a in report["armatures"]])


main()
