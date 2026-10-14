"""Blender-часть clip_closeups.py: крупные планы кадров клипа и пара шва цикла, Workbench «глина» (как разовые скрипты
пилота 2026-10-14 closeup_probe.py / closeups.py). ТОЛЬКО headless:

    blender -b --factory-startup --python-exit-code 1 --python _clip_closeups_blender.py -- <cfg.json>

cfg: {"clip": <AM_*.fbx>, "base": <SM_*_Base.fbx>|null, "work_dir": …, "res": 1200, "label": <Key>-<Clip>,
      "shots": [{"frame": int | "mid"|"last"|"armR"|"armL"|"gripR"|"gripL", "view",
                 "centre": {"kind": "arm_cm", "value": [x, y, z]} | {"kind": "bone", "bone"} | {"kind": "fig"},
                 "size_cm": float|null, "size_h": float|null}],
      "look": {"backface_culling": bool},
      "seam": null | {"views": [...], "camera": {<view>: {"centre_arm_cm": [...], "size_cm": float}} | null}}
Координаты — оси арматуры в см (+X — лицо, +Y — левый бок, +Z — вверх), как замеры спеки (`rest_measured`).
Правила кадра (C45): mid = N // 2, last = N, arm<S> — кадр наибольшего угла плечевой кости arm_upper.<S> к её rest,
grip<S> — кадр наибольшего поворота weapon.<S> относительно hand.<S> против rest (нет кости или поворот
< 5° — arm<S>); первый кадр
максимума. size_h — доля роста фигуры (габарит z мешей) в кадре 0. Имена кадров — clip_closeups.name_shots после
перевода правил в числа (те же имена, что раньше давала обёртка). Выход: <work_dir>/raw/<name>.png,
<work_dir>/raw/seam-fNN-<view>.png, <work_dir>/render.json; строка CLOSEUPS_OK.
"""
import json
import math
import os
import sys

import bpy
from mathutils import Vector

if not bpy.app.background:
    raise RuntimeError("_clip_closeups_blender.py: только headless (blender -b)")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clip_closeups import name_shots  # noqa: E402  (чистая функция обёртки)

# направление от объекта к камере, оси арматуры (+X — лицо); имена — как у скриптов пилота
VIEWS = {"front": (1, 0, 0), "back": (-1, 0, 0), "left": (0, 1, 0), "right": (0, -1, 0),
         "q34": (0.7071, 0.7071, 0), "q34l": (0.7071, 0.7071, 0), "q34r": (0.7071, -0.7071, 0),
         "q34b": (-0.7071, -0.7071, 0), "q34bl": (-0.7071, 0.7071, 0), "rback": (-0.5, -0.866, 0),
         "top34": (0.6, -0.4, 0.7), "top": (0.05, 0.0, 1.0), "topb": (-0.6, 0.0, 0.8)}
BODY_RGBA, BASE_RGBA = (0.78, 0.75, 0.70, 1.0), (0.22, 0.22, 0.26, 1.0)
FIG_PAD = 1.08
CAM_DIST_M = 5.0
GRIP_MIN_DEG = 5  # оружие повернулось в кулаке меньше — кадр grip<S> берётся как arm<S> (кулак при руке вперёд)


def _arm_swing_deg(B, P, side):
    """Угол плечевой кости arm_upper.<S> позы к её rest, градусы (рука вперёд, вверх или в сторону)."""
    n = "arm_upper." + side
    if n not in B:
        return None
    r = (B[n].tail_local - B[n].head_local).normalized()
    p = (P[n].tail - P[n].head).normalized()
    return math.degrees(r.angle(p, 0.0))


def _grip_deg(B, P, side):
    """Поворот weapon.<S> относительно hand.<S> против rest, градусы (как weapon_in_hand_deg grip_check)."""
    h, w = "hand." + side, "weapon." + side
    if h not in B or w not in B:
        return None
    rr = B[h].matrix_local.to_3x3().inverted() @ B[w].matrix_local.to_3x3()
    rel = P[h].matrix.to_3x3().normalized().inverted() @ P[w].matrix.to_3x3().normalized()
    q = (rr.inverted() @ rel).to_quaternion()
    return math.degrees(2.0 * math.acos(min(1.0, abs(q.w))))


def resolve_tokens(arm, sc, f0, n_last, wanted):
    """Правила кадра → {правило: {"frame", "rule", "deg"?, "fallback"?}}; первый кадр максимума."""
    out = {}
    if "mid" in wanted:
        out["mid"] = {"frame": n_last // 2, "rule": "N // 2"}
    if "last" in wanted:
        out["last"] = {"frame": n_last, "rule": "N"}
    need = sorted(t for t in wanted if t[:-1] in ("arm", "grip"))
    if not need:
        return out
    B, P = arm.data.bones, arm.pose.bones
    series = {t: [] for t in need}
    for f in range(n_last + 1):
        sc.frame_set(f0 + f)
        for t in need:
            fn = _arm_swing_deg if t.startswith("arm") else _grip_deg
            series[t].append(fn(B, P, t[-1]))
    for t in need:
        vals, fallback = series[t], None
        if t.startswith("grip") and all(v is None for v in vals):
            fallback = "нет кости weapon.%s или hand.%s: кадр arm%s" % (t[-1], t[-1], t[-1])
        elif t.startswith("grip") and max(v for v in vals if v is not None) < GRIP_MIN_DEG:
            fallback = "оружие в кулаке не поворачивается (< %d°): кадр arm%s" % (GRIP_MIN_DEG, t[-1])
        if fallback:
            vals = []
            for f in range(n_last + 1):
                sc.frame_set(f0 + f)
                vals.append(_arm_swing_deg(B, P, t[-1]))
        if all(v is None for v in vals):
            out[t] = {"frame": n_last // 2, "rule": t, "deg": None, "fallback": "нет кости: кадр N // 2"}
            continue
        vv = [v if v is not None else -1.0 for v in vals]
        f = max(range(len(vv)), key=lambda i: (round(vv[i], 6), -i))
        out[t] = {"frame": f, "deg": round(vv[f], 2),
                  "rule": ("наибольший угол arm_upper.%s к rest" if t.startswith("arm") or fallback
                           else "наибольший поворот weapon.%s в кулаке против rest") % t[-1]}
        if fallback:
            out[t]["fallback"] = fallback
    return out


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
    cull = bool((cfg.get("look") or {}).get("backface_culling", False))
    sh.show_backface_culling = cull  # как в UE: шапка, видимая только изнанкой, не закрывает дыру (C22, C61)
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
    shots = [dict(sht) for sht in cfg.get("shots") or []]
    # имя s занято масштабом арматуры (arm_cm_to_world): кадры здесь — sht
    tokens = resolve_tokens(arm, sc, f0, n_last, {sht["frame"] for sht in shots if isinstance(sht["frame"], str)})
    for sht in shots:
        if isinstance(sht["frame"], str):
            sht["frame_rule"], sht["frame"] = sht["frame"], tokens[sht["frame"]]["frame"]
    h0 = None
    if any(sht.get("size_h") for sht in shots):
        sc.frame_set(f0)
        zs = [p.z for p in fig_points()]
        h0 = max(zs) - min(zs)  # рост фигуры в кадре 0, м мира
    if shots and any("name" not in sht for sht in shots):
        name_shots(cfg.get("label") or "shot", shots)
    shots_meta = []
    for shot in shots:
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
        if shot.get("size_cm"):
            size_m = shot["size_cm"] / 100.0
        elif shot.get("size_h"):
            size_m = shot["size_h"] * h0
        else:
            size_m = size_fit if c["kind"] == "fig" else None
        if size_m is None:
            raise RuntimeError("%s: размер кадра (см) обязателен, кроме центра fig" % shot["name"])
        sc.render.resolution_x = sc.render.resolution_y = res
        place(centre_w, d, size_m)
        sc.render.filepath = os.path.join(raw, shot["name"] + ".png")
        bpy.ops.render.render(write_still=True)
        meta = shot_meta(shot["name"], fr, shot["view"], d, centre_w, size_m, src, (res, res))
        if shot.get("frame_rule"):
            meta["frame_rule"] = shot["frame_rule"]
        if shot.get("size_h"):
            meta["size_rule"] = "h%s" % shot["size_h"]
        shots_meta.append(meta)

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
    if cull:  # ключ только при отсечении: прежние отчёты без него
        info["look"]["backface_culling"] = True
    if tokens:
        info["frame_tokens"] = tokens
    if h0 is not None:
        info["figure_height_f0_m"] = round(h0, 6)
    with open(os.path.join(cfg["work_dir"], "render.json"), "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=1)
    print("CLOSEUPS_OK shots %d seam %s" % (len(shots_meta), bool(seam_meta)))
    sys.stdout.flush()


main()
os._exit(0)
