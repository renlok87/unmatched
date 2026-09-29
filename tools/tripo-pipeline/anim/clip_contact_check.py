"""Контактные проверки клипа H2Anim (волна 5c): стопы, проникновения, подставка, шов петли. Только чтение, headless.

ТОЛЬКО headless (`blender -b`): read_factory_settings выгружает аддон MCP в живом Blender (:9876/:9877).

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup \
      --python tools/tripo-pipeline/anim/clip_contact_check.py -- <clip.fbx> --spec=<spec.json> --clip=<Idle|...> \
      [--out=<report.json>]

validate_clip.py (контракт v2) не проверяет скольжение стоп и проникновения, поэтому этот скрипт дополняет его.
Геометрия — вычисленные (скиненные) меши клипа по всем кадрам 0..N; подставка — SM_*_H2_Base.fbx спеки.
Рост H — габарит скиненных мешей в кадре 0 (как validate_clip.py). Проверки:
  foot_slide      макс. сдвиг вершин подошвы (вес foot.X ≥ 0,95) от кадра 0 в кадрах, где IK стопы этой стороны = 1
                  (ik_feet.weight[_L|_R] спеки), ≤ 0,5 % H (FAIL);
  weapon_body     BVH-пересечение треугольников меша оружия с телом; треугольники хвата (кость — кисть и
                  предплечье руки оружия) исключены. rest-контакт миниатюры (кадр 0) не считается: FAIL — пересечение
                  с областью тела (доминирующая кость), которой в rest не было, или рост в rest-области > 3× + 20 пар;
                  рост в rest-области > 25 % + 10 пар — WARN (посох в складках мантии);
  limb_body       пересечения треугольников рук (крыльев) с корпусом/головой/ногами по областям тела (доминирующая
                  кость треугольника). rest-контакт не считается: области, пересекающиеся с рукой/крылом в кадре 0
                  или ближе 0,4 % H к ней (BVH с допуском, «касание в rest» — перья Harpy H3 у бёдер, рукава у
                  мантии); зона стыка плеча (центроиды ближе 0,8 × длины arm_upper к её голове) исключена. Новая
                  область (> 10 пар) или рост > 3× + 20 пар — FAIL для всех героев (anim-v2 fix: раньше у героев без
                  крыльев было WARN, и рука в поясе Arthur/Medusa проходила); рост > 25 % + 10 пар — WARN. Метрика
                  «глубины» убрана: find_nearest с радиусом 5 % H насыщалась на радиусе (0,047–0,050 во всех клипах,
                  включая Idle) и ничего не измеряла;
  skin_stretch    разрыв скина: рёбра меша тела, удлинившиеся против кадра 0 (rest) в > 5 раз и на > 2 % H
                  (рваная оболочка наплечника/плаща Arthur LungeAttack к. 4 — 15 таких рёбер). FAIL — если такое ребро
                  ВИДНО хотя бы с одного из 24 направлений обзора (азимут через 45°, возвышение 5°/35°/65°: фигура на
                  доске поворачивается к камере любой стороной): луч из середины ребра к камере не встречает геометрию
                  фигуры (тело + оружие этого кадра, BVH). Рёбра, закрытые со всех направлений (внутренняя сторона
                  подола между ног, изнанка под плащом), — WARN skin_stretch_hidden. Рёбра > 3× и > 1 % H — WARN
                  (натяжение на сгибе); в отчёте — число рёбер по кадрам, пары доминирующих костей, высота.
                  Справочно (skin_weight_bleed, info): сколько из этих рёбер касаются вершин «утечки веса» — вершина
                  корпуса/ног (доминирующая кость не из цепи руки) с весом ≥ 0,05 на кости руки дальше 10 % H от её
                  отрезка в rest (бедро Arthur с 22 % arm_upper.R). Это дефект весов меша (исправляется в скине
                  H2/H2LD); из вердикта skin_stretch такие рёбра НЕ исключаются;
  weapon_tip      для клипов с contact.weapon_tip_frames (опора на оружие): острие (вершина меша оружия, самая
                  дальняя вдоль оси кости оружия) в этих кадрах внутри круга подставки и |z − верх| ≤ 0,2 % H (FAIL);
  weapon_below_base_top_outside  вершины оружия вне круга подставки ниже её верха (висят в воздухе у бока
                  подставки или «воткнуты» в бок) глубже 0,2 % H — WARN (кроме кадров weapon_tip);
  below_base_top  вершины фигуры (кроме подола) над кругом подставки не ниже верха подставки сверх
                  rest-заглубления + 0,2 % H (FAIL); вне круга — не ниже z = 0 (FAIL);
  hem_below_base_top  подол (доминирующая кость hips/leg_upper/leg_lower): сверх rest + 0,2 % H — WARN,
                  сверх 1,5 % H — FAIL (жёсткий скин подола без симуляции ткани, решение волны 5c);
  loop_seam       для петли: позиционный шов (кадр N против 0) и скоростной шов (N−(N−1) против 1−0),
                  средний сдвиг вершин ≤ 0,5 % H (FAIL).
Код выхода: 0 — нет FAIL, 1 — есть FAIL, 2 — ошибка запуска.
"""
import json
import os
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

if not bpy.app.background:
    raise RuntimeError("clip_contact_check.py: только headless (blender -b)")

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
import clip_curves as cc  # noqa: E402

SCHEMA = "unmatched.h2anim-contact/1"
CORE = ("hips", "spine", "head", "root")
LEGS = ("leg_upper.L", "leg_lower.L", "foot.L", "leg_upper.R", "leg_lower.R", "foot.R")
ARM = {"L": ("arm_upper.L", "arm_lower.L", "hand.L"), "R": ("arm_upper.R", "arm_lower.R", "hand.R")}
FOOT_SLIDE_MAX = 0.005
BASE_TOL = 0.002
HEM_MAX = 0.015
SEAM_MAX = 0.005
JUNCTION_R = 0.8  # H3 Harpy: перья бока под корнем крыла скинены на arm_upper до 0,65 длины кости
REST_TOUCH = 0.004  # 0,4 % роста: «касание в rest» (перья крыла Harpy H3 почти касаются бёдер)
STRETCH_FAIL = (5.0, 0.02)  # (во сколько раз длиннее rest, на какую долю роста) — разрыв оболочки
STRETCH_WARN = (3.0, 0.01)
VIEW_DIRS = [Vector((np.cos(np.radians(az)) * np.cos(np.radians(el)), np.sin(np.radians(az)) * np.cos(np.radians(el)),
                     np.sin(np.radians(el)))) for az in range(0, 360, 45) for el in (5, 35, 65)]
BLEED_R = 0.10  # вершина дальше 10 % роста от отрезка кости руки, но с весом на ней — утечка веса (дефект скина меша)
BLEED_W = 0.05
TIP_TOL = 0.002
LIMB_NEW_MAX = 10  # до 10 пар в новой области — край зоны стыка плеча (WARN)


def rel(p):
    p = Path(p).resolve()
    try:
        return p.relative_to(REPO).as_posix()
    except ValueError:
        return p.as_posix()


def r(v, nd=6):
    return round(float(v), nd)


def dominant_groups(obj):
    """Индекс полигона -> имя доминирующей кости (сумма весов вершин полигона)."""
    names = {g.index: g.name for g in obj.vertex_groups}
    vw = []
    for v in obj.data.vertices:
        vw.append({names[g.group]: g.weight for g in v.groups if g.group in names})
    out = []
    for p in obj.data.polygons:
        acc = {}
        for i in p.vertices:
            for n, w in vw[i].items():
                acc[n] = acc.get(n, 0.0) + w
        out.append(max(acc, key=acc.get) if acc else None)
    return out, vw


def evaluated(obj, dg):
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    mw = obj.matrix_world
    co = [mw @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return co


def tree(co, polys, subset, epsilon=0.0):
    if not subset:
        return None
    return BVHTree.FromPolygons(co, [polys[i] for i in subset], all_triangles=False, epsilon=epsilon)


def overlap_count(ta, tb):
    if ta is None or tb is None:
        return 0
    return len(ta.overlap(tb))


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    src = argv[0]
    opts = dict(a[2:].split("=", 1) for a in argv[1:] if a.startswith("--") and "=" in a)
    spec = json.loads(Path(opts["spec"]).read_text(encoding="utf-8"))
    clip_name = opts["clip"]
    clip = spec["clips"][clip_name]
    N = int(clip["frames"])
    role = clip["role"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=src, use_anim=True)
    sc = bpy.context.scene
    arm = next(o for o in sc.objects if o.type == "ARMATURE")
    meshes = {o.name: o for o in sc.objects if o.type == "MESH"}
    before = set(sc.objects)
    bpy.ops.import_scene.fbx(filepath=str(REPO / spec["target"]["base_fbx"]))
    base = [o for o in sc.objects if o not in before and o.type == "MESH"]
    act = arm.animation_data.action
    f0 = int(round(act.frame_range[0]))
    body = meshes[spec["meshes"]["body"]]
    weapon = meshes.get((spec["meshes"].get("weapon") or ""))
    wings = bool((spec.get("contact") or {}).get("wings", False))
    wside = (spec.get("weapon") or {}).get("side")
    dom, vw = dominant_groups(body)
    polys = [tuple(p.vertices) for p in body.data.polygons]
    edges = np.zeros(len(body.data.edges) * 2, dtype=np.int64)
    body.data.edges.foreach_get("vertices", edges)
    edges = edges.reshape(-1, 2)
    vdom = [max(w, key=w.get) if w else None for w in vw]
    rest_len = None
    grip = set(ARM[wside][1:]) if wside else set()
    body_ex_grip = [i for i, g in enumerate(dom) if g not in grip]
    core_i = [i for i, g in enumerate(dom) if g in CORE]
    legs_i = [i for i, g in enumerate(dom) if g in LEGS]
    # стык плеча: треугольники руки/крыла и корпуса ближе JUNCTION_R x длина arm_upper к голове arm_upper (rest)
    # деформируются скином по построению (плечо «сминается»), в проверку limb_body не входят
    rest_co = [body.matrix_world @ v.co for v in body.data.vertices]
    # утечка веса: вершины с весом на кости руки, лежащие в rest дальше BLEED_R роста от отрезка этой кости
    rz = [p.z for p in rest_co]
    h_rest = max(rz) - min(rz)
    bleed = {}
    for bn in ARM["L"] + ARM["R"]:
        bb = arm.data.bones.get(bn)
        if bb is None:
            continue
        a = arm.matrix_world @ bb.head_local
        ab = arm.matrix_world @ bb.tail_local - a
        for i, w in enumerate(vw):
            if w.get(bn, 0.0) >= BLEED_W:
                t = min(max((rest_co[i] - a).dot(ab) / max(ab.length_squared, 1e-12), 0.0), 1.0)
                chain = ARM["L"] if bn in ARM["L"] else ARM["R"]
                if vdom[i] not in chain and (rest_co[i] - (a + ab * t)).length > BLEED_R * h_rest:
                    bleed.setdefault(i, []).append(bn)
    bleed_mask = np.zeros(len(vw), dtype=bool)
    if bleed:
        bleed_mask[list(bleed)] = True
    bleed_regions = {}
    for i, bns in bleed.items():
        for bn in bns:
            key = "%s->%s" % (bn, vdom[i])
            bleed_regions[key] = bleed_regions.get(key, 0) + 1
    cen = [sum((rest_co[i] for i in p.vertices), Vector()) / len(p.vertices) for p in body.data.polygons]
    junction = {}
    for sd in ("L", "R"):
        bu = arm.data.bones.get(ARM[sd][0])
        if bu is None:
            junction[sd] = (Vector(), 0.0)
            continue
        hd = arm.matrix_world @ bu.head_local
        ln = (arm.matrix_world @ bu.tail_local - hd).length
        junction[sd] = (hd, JUNCTION_R * ln)
    near = {sd: {i for i, c in enumerate(cen) if (c - junction[sd][0]).length < junction[sd][1]} for sd in ("L", "R")}
    arm_i = {sd: [i for i, g in enumerate(dom) if g in ARM[sd] and i not in near[sd]] for sd in ("L", "R")}
    arm_v = {sd: sorted({v for i in arm_i[sd] for v in body.data.polygons[i].vertices}) for sd in ("L", "R")}
    trunk_i = {sd: [i for i in core_i + legs_i if i not in near[sd]] for sd in ("L", "R")}
    # подошва: вершины, скиненные на стопу почти целиком (вес foot >= 0,95); вершины смешанного веса у щиколотки
    # законно следуют за голенью и в скольжение не входят
    foot_v = {s: [i for i, w in enumerate(vw) if w.get("foot." + s, 0.0) >= 0.95] for s in ("L", "R")}
    # подол (одежда до подставки): вершины тела с доминирующей костью hips/leg_upper/leg_lower. Жёстко скиненный
    # подол при сгибе колен уходит вниз вместе с голенью/тазом (симуляции ткани нет), поэтому он проверяется
    # отдельно: WARN до HEM_MAX роста, FAIL сверх; стопы, оружие, руки, корпус — FAIL сверх rest + BASE_TOL
    hem_v = {i for i, w in enumerate(vw) if w and max(w, key=w.get) in ("hips",) + LEGS[:2] + LEGS[3:5]}
    wpolys = [tuple(p.vertices) for p in weapon.data.polygons] if weapon else []
    tip_i = None
    wbone = arm.data.bones.get((spec.get("weapon") or {}).get("bone") or "")
    if weapon and wbone is not None:
        # острие: вершина меша оружия, самая дальняя вдоль оси кости оружия от её головы (rest), как clip_author
        wh = arm.matrix_world @ wbone.head_local
        wax = (arm.matrix_world @ wbone.tail_local - wh).normalized()
        wrest = [weapon.matrix_world @ v.co for v in weapon.data.vertices]
        tip_i = max(range(len(wrest)), key=lambda i: (wrest[i] - wh).dot(wax))
    tip_frames = sorted({f for a, b in ((clip.get("contact") or {}).get("weapon_tip_frames") or [])
                         for f in range(int(a), int(b) + 1) if 0 <= f <= N})
    # подставка
    bco = [o.matrix_world @ v.co for o in base for v in o.data.vertices]
    base_top = max(p.z for p in bco)
    bx = [p.x for p in bco]
    by = [p.y for p in bco]
    bctr = Vector(((max(bx) + min(bx)) / 2, (max(by) + min(by)) / 2, 0.0))
    brad = min(max(bx) - min(bx), max(by) - min(by)) / 2 * 0.98
    ik = clip.get("ik_feet", {"weight": [[0, 1.0]]})
    # кадры, где стопа должна стоять: ik_feet.pin_frames[_L|_R] = [[a, b], ...] спеки клипа, иначе все кадры
    # с весом IK стопы >= 0,999 (падение DeathSettle и шаг лапой задаются явно)
    def pin_frames(s):
        rng = ik.get("pin_frames_" + s, ik.get("pin_frames"))
        if rng is not None:
            return sorted({f for a, b in rng for f in range(int(a), int(b) + 1) if 0 <= f <= N})
        return [f for f in range(N + 1) if ik.get("enabled", True)
                and cc.weight_curve(ik.get("weight_" + s, ik.get("weight")), f) >= 0.999]
    pinned = {s: pin_frames(s) for s in ("L", "R")}
    dg = bpy.context.evaluated_depsgraph_get()
    rows = []
    rest_touch = {}
    first = None
    prev = []
    seam_pts = {}
    height = None
    for f in range(N + 1):
        sc.frame_set(f0 + f)
        dg = bpy.context.evaluated_depsgraph_get()
        co = evaluated(body, dg)
        wco = evaluated(weapon, dg) if weapon else []
        figure = co + wco
        if f == 0:
            zs = [p.z for p in figure]
            height = max(zs) - min(zs)
            first = {"body": co, "weapon": wco}
        # стопы
        slide = {}
        for s in ("L", "R"):
            if foot_v[s]:
                slide[s] = max((co[i] - first["body"][i]).length for i in foot_v[s]) / height
        # разрыв скина: удлинение рёбер тела против rest (кадр 0)
        arr = np.array([tuple(p) for p in co])
        ln = np.linalg.norm(arr[edges[:, 0]] - arr[edges[:, 1]], axis=1)
        if rest_len is None:
            rest_len = ln
            zmin = float(arr[:, 2].min())
        ratio = ln / np.maximum(rest_len, 1e-9)
        grow = (ln - rest_len) / height
        st = {}
        for lvl, (kr, kg) in (("fail", STRETCH_FAIL), ("warn", STRETCH_WARN)):
            hit = (ratio > kr) & (grow > kg)
            is_bleed = bleed_mask[edges[:, 0]] | bleed_mask[edges[:, 1]]
            n_bleed = int((hit & is_bleed).sum())
            idx = np.nonzero(hit)[0]
            reg = {}
            for k in idx[:4000]:
                key = "|".join(sorted((str(vdom[edges[k, 0]]), str(vdom[edges[k, 1]]))))
                reg[key] = reg.get(key, 0) + 1
            vis = None
            if lvl == "fail" and len(idx):
                # видимость: луч из середины ребра к каждому из направлений обзора; ребро видно, если хотя бы один
                # луч уходит из фигуры без попадания (старт сдвинут на 0,1 % H вдоль луча от своей поверхности)
                t_all = BVHTree.FromPolygons(co + wco, polys + [tuple(len(co) + i for i in pw) for pw in wpolys],
                                             all_triangles=False)
                vis = []
                for k in idx:
                    mid = (co[edges[k, 0]] + co[edges[k, 1]]) * 0.5
                    for dv in VIEW_DIRS:
                        if t_all.ray_cast(mid + dv * (0.001 * height), dv, 2.0 * height)[0] is None:
                            vis.append(int(k))
                            break
                reg = {}
                for k in vis:
                    key = "|".join(sorted((str(vdom[edges[k, 0]]), str(vdom[edges[k, 1]]))))
                    reg[key] = reg.get(key, 0) + 1
            st[lvl] = {"edges": int(len(idx)), "bleed_edges": n_bleed,
                       "visible_edges": (len(vis) if vis is not None else 0),
                       "visible_regions": (reg if vis else {}),
                       "visible_xyz_cm": ([[r(x * 100, 2) for x in (co[edges[k, 0]] + co[edges[k, 1]]) * 0.5] for k in vis[:4]]
                                          if vis else []),
                       "regions": dict(sorted(reg.items(), key=lambda x: -x[1])[:4]),
                       "z_of_height": r((float(np.median(arr[edges[idx, 0], 2])) - zmin) / height, 3)
                       if len(idx) else None}
        st["max_ratio"] = r(float(ratio.max()), 3)
        st["max_growth_of_height"] = r(float(grow.max()), 5)
        # проникновения
        t_body_ex = tree(co, polys, body_ex_grip)
        t_w = BVHTree.FromPolygons(wco, wpolys, all_triangles=False) if weapon else None
        wb_pairs = t_w.overlap(t_body_ex) if (t_w is not None and t_body_ex is not None) else []
        wb = len(wb_pairs)
        wb_bones = {}
        for _a, j in wb_pairs:
            g = dom[body_ex_grip[j]]
            wb_bones[g] = wb_bones.get(g, 0) + 1
        t_core = tree(co, polys, core_i)
        t_legs = tree(co, polys, legs_i)
        lb = {}
        for s in ("L", "R"):
            ta = tree(co, polys, arm_i[s])
            regions = {}
            for tb, idx in ((t_core, core_i), (t_legs, legs_i)):
                if ta is None or tb is None:
                    continue
                for _a, j in ta.overlap(tb):
                    if idx[j] in near[s]:
                        continue  # корпус у стыка плеча этой стороны
                    g = dom[idx[j]]
                    regions[g] = regions.get(g, 0) + 1
            lb[s] = regions
            if f == 0:
                # «касание в rest»: области тела ближе REST_TOUCH роста к руке/крылу в rest (BVH с допуском) —
                # rest-контакт, как и прямые пересечения кадра 0
                ta_e = tree(co, polys, arm_i[s], REST_TOUCH * height)
                touch = {}
                for tb_idx in (core_i, legs_i):
                    tb_e = tree(co, polys, tb_idx, REST_TOUCH * height)
                    if ta_e is None or tb_e is None:
                        continue
                    for _a, j in ta_e.overlap(tb_e):
                        if tb_idx[j] in near[s]:
                            continue
                        g = dom[tb_idx[j]]
                        touch[g] = touch.get(g, 0) + 1
                rest_touch[s] = touch
        # подставка
        inside_pen, pen_i = 0.0, None
        hem_pen = 0.0
        outside_low = 0.0
        w_out_below = 0.0
        for p in wco:
            if (Vector((p.x, p.y, 0.0)) - bctr).length > brad:
                w_out_below = max(w_out_below, base_top - p.z)
        tip = None
        if tip_i is not None:
            tp = wco[tip_i]
            tip = {"r_of_base": r((Vector((tp.x, tp.y, 0.0)) - bctr).length / brad, 4),
                   "dz_of_height": r((tp.z - base_top) / height),
                   "xyz_cm": [r(tp.x * 100, 3), r(tp.y * 100, 3), r(tp.z * 100, 3)]}
        for i, p in enumerate(figure):
            if (Vector((p.x, p.y, 0.0)) - bctr).length <= brad:
                if i in hem_v:
                    hem_pen = max(hem_pen, base_top - p.z)
                elif base_top - p.z > inside_pen:
                    inside_pen, pen_i = base_top - p.z, i
            else:
                outside_low = max(outside_low, -p.z)
        if pen_i is None:
            pen_where = None
        elif pen_i < len(co):
            pen_where = max(vw[pen_i], key=vw[pen_i].get) if vw[pen_i] else "body"
        else:
            pen_where = "weapon"
        rows.append({"f": f, "foot_slide": {k: r(v) for k, v in slide.items()}, "weapon_body_pairs": wb,
                     "weapon_body_bones": wb_bones,
                     "limb_body_pairs": lb, "skin_stretch": st, "weapon_tip": tip,
                     "weapon_below_base_top_outside": r(w_out_below / height), "base_penetration": r(inside_pen / height), "base_penetration_bone": pen_where,
                     "hem_penetration": r(hem_pen / height),
                     "below_ground": r(outside_low / height)})
        if f in (0, 1, N - 1, N):
            seam_pts[f] = figure[::5]
    # вердикты
    checks = []
    fails = []

    def check(name, status, **kw):
        checks.append({"check": name, "status": status, **kw})
        if status == "fail":
            fails.append(name)

    for s in ("L", "R"):
        vals = [(row["f"], row["foot_slide"].get(s, 0.0)) for row in rows if row["f"] in pinned[s]]
        mx = max(vals, key=lambda x: x[1]) if vals else (None, 0.0)
        check("foot_slide_" + s, "pass" if mx[1] <= FOOT_SLIDE_MAX else "fail", max_of_height=mx[1], frame=mx[0],
              pinned_frames=len(vals), tol=FOOT_SLIDE_MAX, foot_vertices=len(foot_v[s]))
    if weapon:
        # rest-контакт миниатюры (посох Merlin касается мантии и стопы) не считается: FAIL — пересечение с областью
        # тела (доминирующая кость), которой в rest не было, или рост пересечений в rest-области > 25 % + 10 пар
        base_bones = rows[0]["weapon_body_bones"]
        bad, soft = [], []
        for row in rows:
            for g, n in row["weapon_body_bones"].items():
                b0 = base_bones.get(g, 0)
                if (b0 == 0 and n > 0) or n > b0 * 3.0 + 20:
                    bad.append({"f": row["f"], "bone": g, "pairs": n, "rest_pairs": b0})
                elif n > b0 * 1.25 + 10:
                    soft.append({"f": row["f"], "bone": g, "pairs": n, "rest_pairs": b0})
        worst = max(rows, key=lambda row: row["weapon_body_pairs"])
        check("weapon_body", "fail" if bad else ("warn" if soft else "pass"),
              soft_violations=soft[:6], soft_frames=len({b["f"] for b in soft}),
              rest_pairs=rows[0]["weapon_body_pairs"], rest_bones=base_bones, max_pairs=worst["weapon_body_pairs"],
              frame=worst["f"], body_bones=worst["weapon_body_bones"], violations=bad[:12], violating_frames=len({b["f"] for b in bad}),
              excluded_grip_bones=sorted(grip))
    else:
        check("weapon_body", "info", note="у героя нет меша оружия")
    for s in ("L", "R"):
        # как weapon_body: rest-контакт (стык плеча/крыла с корпусом, рукава у мантии) не считается; новая область
        # тела или рост > 3× + 20 пар — нарушение (FAIL для крыльев-рук, WARN для остальных), рост > 25 % + 10 — WARN
        base_r = {g: max(n, rest_touch.get(s, {}).get(g, 0)) for g, n in
                  set(rows[0]["limb_body_pairs"][s].items()) | set((rest_touch.get(s) or {}).items())}
        bad, soft = [], []
        for row in rows:
            for g, n in row["limb_body_pairs"][s].items():
                b0 = base_r.get(g, 0)
                if n > b0 * 3.0 + 20 or (b0 == 0 and n > LIMB_NEW_MAX):
                    bad.append({"f": row["f"], "bone": g, "pairs": n, "rest_pairs": b0})
                elif n > b0 * 1.25 + 10 or (b0 == 0 and n > 0):
                    soft.append({"f": row["f"], "bone": g, "pairs": n, "rest_pairs": b0})
        worst = max(rows, key=lambda row: sum(row["limb_body_pairs"][s].values()))
        # вердикт по парам областей: нарушение = пересечение области, которой в rest не было даже на расстоянии
        # REST_TOUCH, или рост > 3× + 20 пар — FAIL для всех героев (anim-v2 fix)
        status = "fail" if bad else ("warn" if soft else "pass")
        check("limb_body_" + s, status, rest_regions=base_r, max_pairs=sum(worst["limb_body_pairs"][s].values()),
              frame=worst["f"], regions=worst["limb_body_pairs"][s], new_region_frames=len({b["f"] for b in bad}),
              pair_violations=bad[:6], soft_violations=soft[:6], wings=wings, level="fail")
    sb = [row["f"] for row in rows if row["skin_stretch"]["fail"]["bleed_edges"]]
    wb_row = max(rows, key=lambda row: row["skin_stretch"]["fail"]["bleed_edges"])
    check("skin_weight_bleed", "info", frames=sb, frame=wb_row["f"],
          max_bleed_fail_edges=wb_row["skin_stretch"]["fail"]["bleed_edges"], bleed_vertices=len(bleed),
          bleed_regions=dict(sorted(bleed_regions.items(), key=lambda x: -x[1])[:8]), radius_of_height=BLEED_R,
          note="справочно: сколько FAIL-рёбер skin_stretch касаются вершин корпуса с весом на кости руки дальше 10 % H "
               "от неё (дефект весов меша, исправляется в скине H2/H2LD); из вердикта skin_stretch не исключаются")
    sf = [row["f"] for row in rows if row["skin_stretch"]["fail"]["visible_edges"]]
    sh = [row["f"] for row in rows if row["skin_stretch"]["fail"]["edges"]]
    sw = [row["f"] for row in rows if row["skin_stretch"]["warn"]["edges"]]
    ws = max(rows, key=lambda row: (row["skin_stretch"]["fail"]["visible_edges"], row["skin_stretch"]["fail"]["edges"],
                                    row["skin_stretch"]["warn"]["edges"], row["skin_stretch"]["max_growth_of_height"]))
    check("skin_stretch", "fail" if sf else ("warn" if (sh or sw) else "pass"),
          fail_frames=sf, torn_frames=sh, warn_frames=sw, frame=ws["f"],
          visible_torn_edges=ws["skin_stretch"]["fail"]["visible_edges"],
          visible_regions=ws["skin_stretch"]["fail"]["visible_regions"],
          visible_xyz_cm=ws["skin_stretch"]["fail"]["visible_xyz_cm"],
          fail_edges=ws["skin_stretch"]["fail"]["edges"], fail_regions=ws["skin_stretch"]["fail"]["regions"],
          fail_z_of_height=ws["skin_stretch"]["fail"]["z_of_height"],
          warn_edges=ws["skin_stretch"]["warn"]["edges"], warn_regions=ws["skin_stretch"]["warn"]["regions"],
          warn_z_of_height=ws["skin_stretch"]["warn"]["z_of_height"],
          max_ratio=max(row["skin_stretch"]["max_ratio"] for row in rows),
          max_growth_of_height=max(row["skin_stretch"]["max_growth_of_height"] for row in rows),
          fail_rule="ребро > %.0f× rest и > %.1f %% H, видимое хотя бы с одного из %d направлений обзора"
                    % (STRETCH_FAIL[0], STRETCH_FAIL[1] * 100, len(VIEW_DIRS)),
          hidden_note="torn_frames без fail_frames — разрывы только в закрытых со всех сторон местах (WARN)",
          warn_rule="ребро > %.0f× rest и > %.1f %% H" % (STRETCH_WARN[0], STRETCH_WARN[1] * 100))
    if tip_frames:
        bad_tip = []
        for row in rows:
            if row["f"] in tip_frames:
                t = row["weapon_tip"]
                if t is None or t["r_of_base"] > 1.0 or abs(t["dz_of_height"]) > TIP_TOL:
                    bad_tip.append({"f": row["f"], **(t or {})})
        tips = [row["weapon_tip"] for row in rows if row["f"] in tip_frames and row["weapon_tip"]]
        check("weapon_tip", "fail" if bad_tip else "pass", frames=[tip_frames[0], tip_frames[-1]],
              max_r_of_base=max((t["r_of_base"] for t in tips), default=None),
              max_abs_dz_of_height=max((abs(t["dz_of_height"]) for t in tips), default=None),
              tol_dz_of_height=TIP_TOL, violations=bad_tip[:8],
              note="острие в круге подставки (r ≤ радиуса) на уровне её верха: опора на оружие")
    else:
        check("weapon_tip", "info", note="клип без опоры на оружие (contact.weapon_tip_frames не задан)")
    if weapon:
        wo = [row for row in rows if row["f"] not in tip_frames]
        wmax = max(wo, key=lambda row: row["weapon_below_base_top_outside"])
        v = wmax["weapon_below_base_top_outside"]
        check("weapon_below_base_top_outside", "warn" if v > BASE_TOL else "pass", max_of_height=v,
              frame=wmax["f"], tol=BASE_TOL,
              note="оружие вне круга подставки ниже её верха: висит в воздухе у бока подставки")
    base_pen = rows[0]["base_penetration"]
    worst = max(rows, key=lambda row: row["base_penetration"])
    check("below_base_top", "pass" if worst["base_penetration"] <= base_pen + BASE_TOL else "fail",
          rest_penetration_of_height=base_pen, max_penetration_of_height=worst["base_penetration"],
          frame=worst["f"], worst_bone=worst["base_penetration_bone"], tol=BASE_TOL, base_top_cm=r(base_top * 100, 3), base_radius_cm=r(brad * 100, 3))
    base_hem = rows[0]["hem_penetration"]
    worst_h = max(rows, key=lambda row: row["hem_penetration"])
    hv = worst_h["hem_penetration"]
    check("hem_below_base_top", "pass" if hv <= base_hem + BASE_TOL else ("warn" if hv <= HEM_MAX else "fail"),
          rest_penetration_of_height=base_hem, max_penetration_of_height=hv, frame=worst_h["f"],
          warn_above=round(base_hem + BASE_TOL, 6), fail_above=HEM_MAX,
          note="подол (доминирующая кость hips/leg_upper/leg_lower) скинен жёстко, симуляции ткани нет")
    worst_g = max(rows, key=lambda row: row["below_ground"])
    check("below_ground", "pass" if worst_g["below_ground"] <= 1e-6 else "fail",
          max_of_height=worst_g["below_ground"], frame=worst_g["f"])
    if role == "idle":
        pos = sum((a - b).length for a, b in zip(seam_pts[N], seam_pts[0])) / len(seam_pts[0]) / height
        vel = sum(((a1 - a0) - (b1 - b0)).length for a1, a0, b1, b0 in
                  zip(seam_pts[N], seam_pts[N - 1], seam_pts[1], seam_pts[0])) / len(seam_pts[0]) / height
        check("loop_seam", "pass" if pos <= SEAM_MAX and vel <= SEAM_MAX else "fail",
              position_of_height=r(pos), velocity_of_height=r(vel), tol=SEAM_MAX)
    else:
        check("loop_seam", "info", note="не петля (%s)" % role)
    report = {"schema": SCHEMA, "clip": rel(src), "clip_name": clip_name, "hero": spec["hero"],
              "spec": rel(opts["spec"]), "base": spec["target"]["base_fbx"], "height_m": r(height, 5),
              "frames": N + 1, "role": role, "tool": "tools/tripo-pipeline/anim/clip_contact_check.py",
              "blender": bpy.app.version_string, "checks": checks, "fails": fails,
              "result": "fail" if fails else "pass", "per_frame": rows,
              "note": "техническая проверка контактов; не художественная приёмка"}
    out = opts.get("out")
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("CLIP_CONTACT", report["result"].upper(), clip_name, "fails", fails,
          {c["check"]: c.get("max_of_height", c.get("max_pairs", c.get("max_penetration_of_height", c.get("position_of_height"))))
           for c in checks})
    sys.stdout.flush()
    os._exit(1 if fails else 0)


try:
    main()
except Exception as exc:  # noqa: BLE001
    import traceback
    traceback.print_exc()
    print("CLIP_CONTACT ERROR", exc)
    sys.stdout.flush()
    os._exit(2)
