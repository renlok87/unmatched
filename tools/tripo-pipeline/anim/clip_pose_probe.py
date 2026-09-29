"""Контактный лист ключевых поз клипа в Blender (волна 5c, H2Anim): рендер кадров клипа + 2D-кости. Только headless.

ТОЛЬКО headless (`blender -b`): read_factory_settings выгружает аддон MCP в живом Blender (:9876/:9877).

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/tripo-pipeline/anim/clip_pose_probe.py -- <clip.fbx> <out_dir> <label> \
      [--frames=0,7,14] [--views=front,left,q34] [--base=<SM_*_Base.fbx>] [--res=640]

затем в системном Python тем же наложением костей, что у пробы рига:
  python tools/tripo-pipeline/anim/overlay_bones.py <out_dir> <label>

Общие скрипты rig_deform_probe.py / overlay_bones.py НЕ правятся (их использует прогон H3): функции пробы
(eval_coords, project_bones, repo_rel) берутся из исходника rig_deform_probe.py без его верхнеуровневого вызова
main() (AST), формат <label>-bones2d.json тот же, поэтому overlay_bones.py работает без изменений.
Рендер: Workbench, заливка по объектам (тело светлое, оружие оранжевое, подставка тёмная), студийный свет,
тени, ортокамеры: front (с +X, лицо героя), left (с +Y, левый бок), q34 (с +X+Y). Кадры клипа — локальные
номера 0..N (кадр 0 = rest). Ничего не сохраняется в .blend; исходники только читаются.
"""
import ast
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Vector

if not bpy.app.background:
    raise RuntimeError("clip_pose_probe.py: только headless (blender -b)")

HERE = Path(__file__).resolve().parent
PROBE_SRC = HERE / "rig_deform_probe.py"
COLORS = {"body": (0.78, 0.75, 0.70, 1.0), "weapon": (0.95, 0.55, 0.12, 1.0), "base": (0.22, 0.22, 0.26, 1.0)}
VIEWS = {"front": (1.0, 0.0), "left": (0.0, 1.0), "q34": (0.7071, 0.7071), "back": (-1.0, 0.0), "right": (0.0, -1.0)}


def probe_functions():
    """Функции rig_deform_probe.py без его вызова main(): исходник разбирается AST, верхнеуровневые
    выражения-вызовы отбрасываются, остальное исполняется в отдельном пространстве имён."""
    tree = ast.parse(PROBE_SRC.read_text(encoding="utf-8"), str(PROBE_SRC))
    tree.body = [n for n in tree.body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call))]
    ns = {"__name__": "rig_deform_probe_lib", "__file__": str(PROBE_SRC)}
    exec(compile(tree, str(PROBE_SRC), "exec"), ns)
    return ns


def args():
    a = sys.argv[sys.argv.index("--") + 1:]
    opts = dict(x[2:].split("=", 1) for x in a[3:] if x.startswith("--") and "=" in x)
    return a[0], a[1], a[2], opts


def main():
    lib = probe_functions()
    src, out_dir, label, opts = args()
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src, use_anim=True)
    sc = bpy.context.scene
    arm = next(o for o in sc.objects if o.type == "ARMATURE")
    fig = [o for o in sc.objects if o.type == "MESH"]
    base = []
    if opts.get("base"):
        before = set(sc.objects)
        bpy.ops.import_scene.fbx(filepath=opts["base"])
        base = [o for o in sc.objects if o not in before and o.type == "MESH"]
    act = arm.animation_data.action if arm.animation_data else None
    f0 = int(round(act.frame_range[0])) if act else 0
    f1 = int(round(act.frame_range[1])) if act else 0
    frames = [int(x) for x in opts["frames"].split(",")] if opts.get("frames") else [0, (f1 - f0) // 2, f1 - f0]
    views = opts.get("views", "front,left").split(",")
    weapon_names = [o.name for o in fig if not any(k in o.name for k in ("Body",))]
    for o in fig:
        o.color = COLORS["weapon"] if o.name in weapon_names else COLORS["body"]
    for o in base:
        o.color = COLORS["base"]
    res = int(opts.get("res", 640))
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "OBJECT"
    sh.show_shadows, sh.show_cavity, sh.show_xray = True, True, False
    sh.shadow_intensity = 0.35
    sc.display.shadow_focus = 0.1
    sc.render.resolution_x = sc.render.resolution_y = res
    sc.render.film_transparent = False
    sc.world = sc.world or bpy.data.worlds.new("probe")
    # габарит всех кадров (фигура + подставка), чтобы камера не менялась между кадрами
    pts = []
    for fr in range(f0, f1 + 1):
        sc.frame_set(fr)
        for co in lib["eval_coords"](fig).values():
            pts.extend(co[::7])
    for o in base:
        pts.extend(o.matrix_world @ Vector(c) for c in o.bound_box)
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    ctr = (mn + mx) / 2
    size = max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z) * 1.22
    ctr.z += size * 0.04  # overlay_bones.py закрывает верхние 34 px подписью
    cam_data = bpy.data.cameras.new("ClipProbeCam")
    cam_data.type, cam_data.ortho_scale = "ORTHO", size
    cam = bpy.data.objects.new("ClipProbeCam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    frames2d = {}
    report = {"source": lib["repo_rel"](src), "label": label, "frame_range": [f0, f1], "frames": frames,
              "views": views, "bbox_min": [round(v, 5) for v in mn], "bbox_max": [round(v, 5) for v in mx],
              "weapon_meshes": weapon_names, "base": [o.name for o in base], "renders": []}
    for fr in frames:
        sc.frame_set(f0 + fr)
        for v in views:
            dx, dy = VIEWS[v]
            d = size * 3
            cam.location = (ctr.x + dx * d, ctr.y + dy * d, ctr.z)
            direction = Vector((-dx, -dy, 0.0))
            cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
            bpy.context.view_layer.update()
            png = "%s-f%02d-%s.png" % (label, fr, v)
            sc.render.filepath = os.path.join(out_dir, png)
            bpy.ops.render.render(write_still=True)
            frames2d["f%02d %s" % (fr, v)] = {"png": png, "bones": lib["project_bones"](arm, cam)}
            report["renders"].append(png)
    with open(os.path.join(out_dir, "%s-bones2d.json" % label), "w", encoding="utf-8") as f:
        json.dump(frames2d, f, ensure_ascii=False)
    with open(os.path.join(out_dir, "%s-probe.json" % label), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print("CLIP_PROBE_OK", label, len(report["renders"]))


main()
sys.stdout.flush()
os._exit(0)
