"""Blender-часть draft_orthos.py (headless, bpy). Не запускать в живом Blender пользователя.

    blender -b --factory-startup --python-exit-code 1 --python tools/art/concept/_blender_orthos.py -- \
        --glb <draft.glb> --render-dir <dir> --views front,left,back,right --res 1152x1536

Импортирует GLB, ставит ОДНУ ортокамеру с общим масштабом для всех видов (центр подставки по x = 50 % кадра, низ
подставки на одной высоте), нейтральный свет, прозрачный фон (ровный фон кладёт draft_orthos.py), пишет
<render-dir>/<view>.png (RGBA) и <render-dir>/framing.json.

Оси (BLENDER-MODEL-HANDBOOK §2.1): лицо фигуры −Y, Z вверх, левый бок фигуры (.L) = +X. glTF-импорт Tripo даёт
именно это (glTF +Z front → Blender −Y). Виды: front — камера в −Y; left — камера в +X (виден левый бок фигуры);
back — камера в +Y; right — камера в −X.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

# камера: (положение-направление от фигуры к камере, ось кадра «вправо» в мире)
VIEWS = {
    "front": ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0)),
    "left": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "back": ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
    "right": ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0)),
}
GROUND_PCT = 94.0       # низ подставки, % высоты кадра сверху (решение скилла; канон hero-quality-v1: 91–97 %)
MAX_FIG_PCT = 90.0      # рост фигуры не больше 90 % высоты кадра (верх ≥ 4 %)
MAX_WIDTH_PCT = 92.0    # ширина (вокруг центра подставки) не больше 92 % ширины кадра (поле ≥ 4 %)
BASE_BAND = 0.03        # нижние 3 % роста — вершины подставки (центр и ширина)


def args_after_dashes():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--glb", required=True)
    ap.add_argument("--render-dir", required=True)
    ap.add_argument("--views", default="front,left,back,right")
    ap.add_argument("--res", default="1152x1536")
    ap.add_argument("--samples", type=int, default=32)
    return ap.parse_args(argv)


def world_vertices(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    chunks = []
    for ob in objs:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        n = len(me.vertices)
        if n:
            co = np.empty(n * 3, np.float64)
            me.vertices.foreach_get("co", co)
            co = co.reshape(-1, 3)
            m = np.array(ob.matrix_world, np.float64)
            chunks.append(co @ m[:3, :3].T + m[:3, 3])
        ev.to_mesh_clear()
    return np.concatenate(chunks) if chunks else np.empty((0, 3))


def add_sun(name, energy, cam_dir, az_deg, el_deg):
    """Солнце относительно камеры: az — поворот вокруг Z от направления на камеру, el — высота."""
    d = Vector(cam_dir)
    az = math.radians(az_deg)
    rot = Vector((d.x * math.cos(az) - d.y * math.sin(az), d.x * math.sin(az) + d.y * math.cos(az), 0.0))
    el = math.radians(el_deg)
    src = Vector((rot.x * math.cos(el), rot.y * math.cos(el), math.sin(el))).normalized()  # откуда светит
    li = bpy.data.lights.new(name, "SUN")
    li.energy = energy
    li.angle = math.radians(10.0)
    ob = bpy.data.objects.new(name, li)
    ob.rotation_euler = (-src).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def main():
    a = args_after_dashes()
    views = [v.strip() for v in a.views.split(",") if v.strip()]
    for v in views:
        if v not in VIEWS:
            raise SystemExit(f"unknown view {v!r}; known: {', '.join(VIEWS)}")
    rx, ry = (int(x) for x in a.res.lower().split("x"))
    out = Path(a.render_dir)
    out.mkdir(parents=True, exist_ok=True)

    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=str(Path(a.glb).resolve()))
    meshes = [ob for ob in bpy.context.scene.objects if ob.type == "MESH"]
    if not meshes:
        raise SystemExit("GLB has no mesh objects")
    pts = world_vertices(meshes)
    if pts.shape[0] == 0:
        raise SystemExit("GLB meshes have no vertices")
    lo, hi = pts.min(0), pts.max(0)
    height = float(hi[2] - lo[2])
    base = pts[pts[:, 2] <= lo[2] + BASE_BAND * height]
    bmin, bmax = base.min(0), base.max(0)
    cx, cy = float((bmin[0] + bmax[0]) / 2), float((bmin[1] + bmax[1]) / 2)
    base_w = {"x": float(bmax[0] - bmin[0]), "y": float(bmax[1] - bmin[1])}
    # верх подставки (оценка): поднимаемся слоями 0,5 % роста, пока непустой слой шире 85 % подставки. Пустые слои
    # пропускаются: у низкополигональной подставки вершины только на ободах (между ними пусто); пустой разрыв
    # длиннее 15 % роста завершает поиск.
    base_top = float(lo[2])
    ref_w = max(base_w.values())
    step = 0.005 * height
    z = float(lo[2])
    gap = 0.0
    while z < lo[2] + 0.3 * height:
        sl = pts[(pts[:, 2] >= z) & (pts[:, 2] < z + step)]
        if sl.shape[0] == 0:
            gap += step
            if gap > 0.15 * height:
                break
            z += step
            continue
        if max(np.ptp(sl[:, 0]), np.ptp(sl[:, 1])) < 0.85 * ref_w:
            break
        gap = 0.0
        base_top = z + step
        z += step
    half_w = float(max(np.abs(pts[:, 0] - cx).max(), np.abs(pts[:, 1] - cy).max()))
    m_per_px = max(height / (MAX_FIG_PCT / 100.0 * ry), 2.0 * half_w / (MAX_WIDTH_PCT / 100.0 * rx))
    frame_h_m, frame_w_m = m_per_px * ry, m_per_px * rx
    z_center = float(lo[2]) + (GROUND_PCT / 100.0 - 0.5) * frame_h_m
    dist = float(np.linalg.norm(hi - lo)) * 2.0 + 1.0

    sc = bpy.context.scene
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.resolution_percentage = 100
    sc.render.film_transparent = True
    sc.render.image_settings.file_format = "PNG"
    sc.render.image_settings.color_mode = "RGBA"
    sc.render.image_settings.color_depth = "8"
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    engine = "BLENDER_EEVEE"
    try:
        sc.render.engine = engine
        sc.eevee.taa_render_samples = int(a.samples)
    except (TypeError, AttributeError):
        engine = "BLENDER_WORKBENCH"
        sc.render.engine = engine
    world = bpy.data.worlds.new("ortho_world")
    sc.world = world
    world.use_nodes = True
    bgn = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bgn.inputs[0].default_value = (0.5, 0.5, 0.5, 1.0)  # ровная окружающая подсветка (камерой не видна)
    bgn.inputs[1].default_value = 1.0

    cam_data = bpy.data.cameras.new("ortho_cam")
    cam_data.type = "ORTHO"
    cam_data.sensor_fit = "AUTO"
    cam_data.ortho_scale = max(frame_w_m, frame_h_m)
    cam_data.clip_start = 0.01
    cam_data.clip_end = dist * 2.0
    cam = bpy.data.objects.new("ortho_cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam

    framing_views = {}
    for v in views:
        cdir, right = VIEWS[v]
        for ob in [o for o in sc.objects if o.type == "LIGHT"]:
            bpy.data.objects.remove(ob, do_unlink=True)
        add_sun("key", 3.0, cdir, -35.0, 35.0)
        add_sun("fill", 1.2, cdir, 50.0, 10.0)
        target = Vector((cx, cy, z_center))
        cam.location = target + Vector(cdir) * dist
        cam.rotation_euler = (-Vector(cdir)).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = str(out / f"{v}.png")
        bpy.ops.render.render(write_still=True)
        axis = "x" if abs(right[0]) > 0 else "y"
        framing_views[v] = {
            "file": f"ortho_{v}.png",
            "camera_location_m": [round(c, 5) for c in cam.location],
            "camera_looks_along": [-c for c in cdir],
            "image_right_world_axis": ("+" if sum(right) > 0 else "-") + axis.upper(),
            "base_width_pct": round(base_w[axis] / frame_w_m * 100.0, 3),
        }
    def ypct(zw):
        return round((0.5 - (zw - z_center) / frame_h_m) * 100.0, 3)
    framing = {
        "engine": engine,
        "resolution": [rx, ry],
        "ortho_scale_m": round(cam_data.ortho_scale, 6),
        "metres_per_px": m_per_px,
        "axes": "Blender: front -Y, Z up, figure left (.L) = +X (BLENDER-MODEL-HANDBOOK §2.1)",
        "bounds_m": {"min": [round(float(c), 5) for c in lo], "max": [round(float(c), 5) for c in hi]},
        "height_m": round(height, 5),
        "base_center_m": [round(cx, 5), round(cy, 5)],
        "placement_pct": {
            "figure_top_y": ypct(float(hi[2])),
            "base_bottom_y": ypct(float(lo[2])),
            "base_top_y_est": ypct(base_top),
            "base_center_x": 50.0,
        },
        "light": "world grey 0.5 x1.0 + sun key 3.0 (az -35, el 35) + sun fill 1.2 (az 50, el 10), camera-relative; "
                 "view transform Standard",
        "views": framing_views,
        "vertices": int(pts.shape[0]),
        "mesh_objects": len(meshes),
    }
    (out / "framing.json").write_text(json.dumps(framing, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
