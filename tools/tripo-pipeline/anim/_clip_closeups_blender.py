"""Blender-часть clip_closeups.py: крупные планы кадров клипа и пара шва цикла, Workbench «глина» (как разовые скрипты
пилота 2026-10-14 closeup_probe.py / closeups.py). ТОЛЬКО headless:

    blender -b --factory-startup --python-exit-code 1 --python _clip_closeups_blender.py -- <cfg.json>

cfg: {"clip": <AM_*.fbx>, "base": <SM_*_Base.fbx>|null, "work_dir": …, "res": 1200,
      "shots": [{"name", "frame", "view", "centre": {"kind": "arm_cm", "value": [x, y, z]} | {"kind": "bone", "bone"} |
                 {"kind": "fig"}, "size_cm": float|null}],
      "seam": null | {"views": [...], "camera": {<view>: {"centre_arm_cm": [...], "size_cm": float}} | null}}
Координаты — оси арматуры в см (+X — лицо, +Y — левый бок, +Z — вверх), как замеры спеки (`rest_measured`).
Выход: <work_dir>/raw/<name>.png, <work_dir>/raw/seam-fNN-<view>.png, <work_dir>/render.json; строка CLOSEUPS_OK.
"""
import json
import os
import sys

import bpy
from mathutils import Vector

if not bpy.app.background:
    raise RuntimeError("_clip_closeups_blender.py: только headless (blender -b)")

# направление от объекта к камере, оси арматуры (+X — лицо); имена — как у скриптов пилота
VIEWS = {"front": (1, 0, 0), "back": (-1, 0, 0), "left": (0, 1, 0), "right": (0, -1, 0),
         "q34": (0.7071, 0.7071, 0), "q34l": (0.7071, 0.7071, 0), "q34r": (0.7071, -0.7071, 0),
         "q34b": (-0.7071, -0.7071, 0), "q34bl": (-0.7071, 0.7071, 0), "rback": (-0.5, -0.866, 0),
         "top34": (0.6, -0.4, 0.7), "top": (0.05, 0.0, 1.0)}
BODY_RGBA, BASE_RGBA = (0.78, 0.75, 0.70, 1.0), (0.22, 0.22, 0.26, 1.0)
FIG_PAD = 1.08
CAM_DIST_M = 5.0


def main():
    cfg = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    raw = os.path.join(cfg["work_dir"], "raw")
    os.makedirs(raw, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=cfg["clip"], use_anim=True)
    sc = bpy.context.scene
    arm = next(o for o in sc.objects if o.type == "ARMATURE")
    figs = [o for o in sc.objects if o.type == "MESH"]
    base = []
    if cfg.get("base"):
        before = set(sc.objects)
        bpy.ops.import_scene.fbx(filepath=cfg["base"])
        base = [o for o in sc.objects if o not in before and o.type == "MESH"]
    act = arm.animation_data.action if arm.animation_data else None
    if act is None:
        raise RuntimeError("в %s нет анимации арматуры" % cfg["clip"])
    f0, f1 = [int(round(x)) for x in act.frame_range]
    n_last = f1 - f0

    M = arm.matrix_world.copy()
    s = M.to_scale()[0]
    R3 = M.to_3x3().normalized()

    def arm_cm_to_world(c):
        return M @ (Vector(c) / (100.0 * s))

    def world_to_arm_cm(w):
        return (M.inverted() @ w) * (100.0 * s)

    def fig_points():
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in figs:
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            mw = o.matrix_world
            pts += [mw @ v.co for v in me.vertices]
            ev.to_mesh_clear()
        return pts

    for o in figs:
        o.color = BODY_RGBA
    for o in base:
        o.color = BASE_RGBA
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type = "STUDIO", "OBJECT"
    sh.show_shadows, sh.show_cavity, sh.show_xray = True, True, False
    sh.shadow_intensity = 0.35
    sc.world = sc.world or bpy.data.worlds.new("closeups")
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    cam_data = bpy.data.cameras.new("C")
    cam_data.type = "ORTHO"
    cam_data.clip_start, cam_data.clip_end = 0.01, 2 * CAM_DIST_M + 5.0
    cam = bpy.data.objects.new("C", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam

    def view_dir(view):
        if view not in VIEWS:
            raise RuntimeError("вид %s не из %s" % (view, sorted(VIEWS)))
        return (R3 @ Vector(VIEWS[view])).normalized()

    def place(centre_w, d, size_m):
        cam.location = centre_w + d * CAM_DIST_M
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        cam_data.ortho_scale = size_m
        bpy.context.view_layer.update()

    def fit(points, d, aspect_w_over_h=1.0):
        """Центр и ortho-размер (м), в которые входят точки при взгляде по d: рамка по осям камеры, запас FIG_PAD."""
        place(Vector((0, 0, 0)), d, 1.0)
        rot = cam.matrix_world.to_3x3()
        x_ax, y_ax = rot.col[0], rot.col[1]
        xs = [p.dot(x_ax) for p in points]
        ys = [p.dot(y_ax) for p in points]
        cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
        mid = sum(points, Vector((0, 0, 0))) / len(points)
        depth = mid - x_ax * mid.dot(x_ax) - y_ax * mid.dot(y_ax)
        centre = x_ax * cx + y_ax * cy + depth
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        # ortho_scale — по большей стороне кадра; кадр шире — по ширине, выше — по высоте
        if aspect_w_over_h >= 1.0:
            size = max(w, h * aspect_w_over_h) * FIG_PAD
        else:
            size = max(h, w / aspect_w_over_h) * FIG_PAD
        return centre, size

    def shot_meta(name, frame, view, d, centre_w, size_m, source, res_xy):
        c_cm = world_to_arm_cm(centre_w)
        return {"name": name, "frame": frame, "view": view, "view_dir_arm": list(VIEWS[view]),
                # центр и размер — с полной точностью (6 знаков см): повтор --shots-from даёт тот же кадр
                # пиксель в пиксель (с 3 знаками край фигуры сдвигался на доли пикселя: до 116 пикселей разницы)
                "view_dir_world": [round(x, 6) for x in d], "centre_arm_cm": [round(x, 6) for x in c_cm],
                "centre_world_m": [round(x, 8) for x in centre_w], "size_cm": round(size_m * 100.0, 6),
                "ortho_scale_m": round(size_m, 6), "camera_location_m": [round(x, 6) for x in cam.location],
                "camera_rotation_quat": [round(x, 6) for x in cam.matrix_world.to_quaternion()],
                "centre_source": source, "res_px": list(res_xy)}

    res = int(cfg.get("res", 1200))
    shots_meta = []
    for shot in cfg.get("shots") or []:
        fr = int(shot["frame"])
        if not 0 <= fr <= n_last:
            raise RuntimeError("кадр %d вне клипа 0..%d" % (fr, n_last))
        sc.frame_set(f0 + fr)
        d = view_dir(shot["view"])
        c = shot["centre"]
        if c["kind"] == "arm_cm":
            centre_w, src = arm_cm_to_world(c["value"]), "arm_cm"
        elif c["kind"] == "bone":
            pb = arm.pose.bones.get(c["bone"])
            if pb is None:
                raise RuntimeError("нет кости %s" % c["bone"])
            centre_w, src = M @ pb.head, "@%s" % c["bone"]
        else:
            centre_w, size_fit = fit(fig_points(), d)
            src = "fig"
        size_m = shot["size_cm"] / 100.0 if shot.get("size_cm") else (size_fit if c["kind"] == "fig" else None)
        if size_m is None:
            raise RuntimeError("%s: размер кадра (см) обязателен, кроме центра fig" % shot["name"])
        sc.render.resolution_x = sc.render.resolution_y = res
        place(centre_w, d, size_m)
        sc.render.filepath = os.path.join(raw, shot["name"] + ".png")
        bpy.ops.render.render(write_still=True)
        shots_meta.append(shot_meta(shot["name"], fr, shot["view"], d, centre_w, size_m, src, (res, res)))

    seam_meta = None
    seam = cfg.get("seam")
    if seam:
        seam_meta = {"frames": [n_last, 0], "views": {}}
        fixed = seam.get("camera") or {}
        rx, ry = res // 2, res  # портретные панели: пара складывается в квадратный кадр res × res
        for view in seam["views"]:
            d = view_dir(view)
            if view in fixed:
                centre_w, size_m = arm_cm_to_world(fixed[view]["centre_arm_cm"]), fixed[view]["size_cm"] / 100.0
                src = "fixed"
            else:
                pts = []
                for fr in (0, n_last):
                    sc.frame_set(f0 + fr)
                    pts += fig_points()
                centre_w, size_m = fit(pts, d, aspect_w_over_h=rx / ry)
                src = "fig: кадры 0 и %d" % n_last
            files = {}
            for fr in (n_last, 0):
                sc.frame_set(f0 + fr)
                sc.render.resolution_x, sc.render.resolution_y = rx, ry
                place(centre_w, d, size_m)
                nm = "seam-f%02d-%s" % (fr, view)
                sc.render.filepath = os.path.join(raw, nm + ".png")
                bpy.ops.render.render(write_still=True)
                files["f%02d" % fr] = nm + ".png"
            m = shot_meta("seam-%s" % view, n_last, view, d, centre_w, size_m, src, (rx, ry))
            m["raw"] = files
            seam_meta["views"][view] = m

    info = {"blender": bpy.app.version_string, "frame_start": f0, "frame_end": f1, "last_frame": n_last,
            "fps": sc.render.fps, "armature": arm.name, "armature_scale": round(s, 6),
            "figure_meshes": sorted(o.name for o in figs), "base_meshes": sorted(o.name for o in base),
            "shots": shots_meta, "seam": seam_meta,
            "look": {"engine": "BLENDER_WORKBENCH", "light": "STUDIO", "color_type": "OBJECT", "figure_rgba": BODY_RGBA,
                     "base_rgba": BASE_RGBA, "shadows": True, "shadow_intensity": 0.35, "cavity": True,
                     "camera": "ORTHO", "fig_pad": FIG_PAD}}
    with open(os.path.join(cfg["work_dir"], "render.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    print("CLOSEUPS_OK shots %d seam %s" % (len(shots_meta), bool(seam_meta)))
    sys.stdout.flush()


main()
os._exit(0)
