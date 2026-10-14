"""Хват оружия, кисти, локти, колени и пересечения оружия/щита с телом H2Anim-клипа по кадрам (headless Blender).

Собственная проверка исполнителя этапа 6 (доработка клипов), не гейт: числа для обоснования правки ключей и для
приёмщика. Объединяет пилотные копии C:/tmp/{angel-anim-r2,achilles-anim-s6,achilles-r3}/grip_check.py (Angel —
меч в правой, Achilles — копьё в правой + щит на левом предплечье); сторона, оружие, щит и подставка — флаги.

    blender -b --factory-startup --python tools/tripo-pipeline/anim/grip_check.py -- <clip.fbx> <out.json>
        [--side R|L] [--base <SM_<Key>_..._Base.fbx>] [--shield-bone arm_lower.L] [--shield-min-dist-cm 2.5]
        [--body-suffix _Body] [--weapon-suffix _Spear [_Sword ...]] [--rest-only] [--verbose]
    python tools/tripo-pipeline/anim/grip_check.py --help        # без Blender: только справка

На кадр (координаты — пространство арматуры, см):
  weapon_in_hand_deg      поворот weapon.<S> относительно hand.<S> против rest (0 = оружие жёстко в кулаке)
  wrist_R_deg / wrist_L_deg, wrist_<S>_twist_swing   кисть против предплечья относительно rest
  elbow_R_deg / elbow_L_deg   угол плечо–локоть–запястье (180 = прямая рука); elbow_<S>_offhinge_deg — уход
                          плоскости сгиба руки с оружием от шарнира rest; elbow_<S>_twist_deg
  knee_L_deg / knee_R_deg (180 = прямая), thigh_flex_L_deg / thigh_flex_R_deg (бедро против rest)
  weapon_dir, hand_head   ось кости оружия и голова кисти <S>
  butt_cm / tip_cm        концы оружия (вершины веса weapon.<S> тела + меши оружия, по оси кости в rest);
                          butt_below_top_cm — насколько пятка ниже верха подставки (> 0 = утоплена; только с --base и
                          если пятка над кругом подставки)
  weapon_body_pairs       BVH-пересечения оружия (меши оружия + грани тела с доминантой weapon.<S>) с гранями тела
                          ядра, ног, головы и другой руки (грани хвата hand.<S>/arm_lower.<S> исключены); weapon_regions
  shield_vs_forearm_cm    (с --shield-bone) сдвиг вершин щита (вес кости щита ≥ 0,999 и дальше --shield-min-dist-cm от
                          кости) в системе кости против rest (0 = щит жёсткий); shield_body_pairs / shield_regions —
                          пересечения щита с ядром, ногами, головой, другой рукой и оружием; shield_min_z_cm
Итог `summary` — максимумы и диапазоны; JSON: {tool, fbx, base, options, summary, rest, frames}; строка
`GRIP_CHECK {summary}` в stdout. Выход 0 — замер записан (вердиктов нет), 2 — ошибка аргументов/входа.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

TOOL = "tools/tripo-pipeline/anim/grip_check.py"
CORE = ("hips", "spine", "head", "leg_upper.L", "leg_lower.L", "foot.L", "leg_upper.R", "leg_lower.R", "foot.R")


# ---------------------------------------------------------------------------------- чистая математика (без Blender)
def quat_angle_deg(q) -> float:
    """Угол поворота кватерниона (w, x, y, z), градусы, 0..180."""
    w = abs(q[0])
    return math.degrees(2.0 * math.acos(min(1.0, w)))


def twist_swing_deg(q) -> tuple[float, float]:
    """(twist, swing) кватерниона (w, x, y, z) относительно оси Y кости, градусы."""
    w, _x, y, _z = q
    if w < 0:
        w, y = -w, -y
    tw = math.degrees(2.0 * math.atan2(abs(y), w))
    sw = math.degrees(2.0 * math.acos(min(1.0, math.sqrt(w * w + y * y))))
    return round(tw, 1), round(sw, 1)


def joint_angle_deg(s, e, w) -> float:
    """Угол в суставе e между s и w (3-векторы), градусы; 180 = прямая."""
    u = [a - b for a, b in zip(s, e)]
    v = [a - b for a, b in zip(w, e)]
    nu, nv = math.sqrt(sum(c * c for c in u)), math.sqrt(sum(c * c for c in v))
    if nu < 1e-9 or nv < 1e-9:
        return 180.0
    d = sum(a * b for a, b in zip(u, v)) / (nu * nv)
    return math.degrees(math.acos(max(-1.0, min(1.0, d))))


def _vals(rows, key):
    return [r[key] for r in rows if r.get(key) is not None]


def _max(rows, key):
    v = _vals(rows, key)
    return max(v) if v else None


def _range(rows, key):
    v = _vals(rows, key)
    return [min(v), max(v)] if v else None


def summarize(rows: list, side: str = "R", base: dict | None = None) -> dict:
    """Итог по кадрам: максимумы, диапазоны, значения rest (кадр 0) для пересечений."""
    if not rows:
        return {"frames": 0}
    other = "L" if side == "R" else "R"
    knees = [min(r["knee_L_deg"], r["knee_R_deg"]) for r in rows if r.get("knee_L_deg") is not None]
    thighs = [max(r["thigh_flex_L_deg"], r["thigh_flex_R_deg"]) for r in rows if r.get("thigh_flex_L_deg") is not None]
    out = {
        "frames": len(rows),
        "weapon_in_hand_max_deg": _max(rows, "weapon_in_hand_deg"),
        f"wrist_{side}_max_deg": _max(rows, f"wrist_{side}_deg"),
        f"wrist_{other}_max_deg": _max(rows, f"wrist_{other}_deg"),
        "elbow_R_range": _range(rows, "elbow_R_deg"),
        "elbow_L_range": _range(rows, "elbow_L_deg"),
        f"elbow_{side}_offhinge_max_deg": _max(rows, f"elbow_{side}_offhinge_deg"),
        "knee_min_deg": min(knees) if knees else None,
        "thigh_flex_max_deg": max(thighs) if thighs else None,
        "butt_sink_max_cm": _max(rows, "butt_below_top_cm"),
        "weapon_body_pairs_rest": rows[0].get("weapon_body_pairs"),
        "weapon_body_pairs_max": _max(rows, "weapon_body_pairs"),
        "shield_vs_forearm_max_cm": _max(rows, "shield_vs_forearm_cm"),
        "shield_body_pairs_rest": rows[0].get("shield_body_pairs"),
        "shield_body_pairs_max": _max(rows, "shield_body_pairs"),
    }
    if base:
        out.update({"base_top_cm": base.get("top_cm"), "base_radius_cm": base.get("radius_cm")})
    return out


def parse_args(argv: list[str]):
    """Аргументы после «--» (запуск из Blender) или вся строка после имени скрипта (python … --help)."""
    rest = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
    ap = argparse.ArgumentParser(prog="grip_check.py", description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    ap.add_argument("clip", help="FBX клипа (AM_<Key>_<Clip>.fbx из <run>/export)")
    ap.add_argument("out", help="куда писать JSON замера")
    ap.add_argument("--side", choices=("R", "L"), default="R", help="рука с оружием: weapon.<S>, hand.<S> (R)")
    ap.add_argument("--base", default=None, help="FBX подставки (SM_<Key>_..._Base.fbx): верх и круг для пятки оружия")
    ap.add_argument("--shield-bone", default=None, help="кость щита, если щит — часть тела (Achilles: arm_lower.L)")
    ap.add_argument("--shield-min-dist-cm", type=float, default=2.5,
                    help="вершины щита — дальше этого от отрезка кости (2,5 см: не трогать само предплечье)")
    ap.add_argument("--body-suffix", default="_Body", help="суффикс меша тела (_Body)")
    ap.add_argument("--weapon-suffix", nargs="*", default=None,
                    help="суффиксы мешей оружия (_Spear _Sword …); по умолчанию — все меши, кроме тела")
    ap.add_argument("--rest-only", action="store_true", help="только таблица костей rest, без кадров")
    ap.add_argument("--verbose", action="store_true", help="строка на кадр в stdout")
    a = ap.parse_args(rest)
    if a.shield_bone and not a.shield_bone.endswith((".L", ".R")):
        ap.error("--shield-bone: кость стороны .L/.R (arm_lower.L)")
    return a


# ----------------------------------------------------------------------------------------------------- Blender
def _q(m):
    q = m.to_quaternion()
    return (q.w, q.x, q.y, q.z)


def measure(a) -> dict:  # pragma: no cover - выполняется только внутри Blender
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    S = a.side
    O = "L" if S == "R" else "R"
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=a.clip, use_anim=True)
    sc = bpy.context.scene
    arm = next(o for o in sc.objects if o.type == "ARMATURE")
    meshes = {o.name: o for o in sc.objects if o.type == "MESH"}
    body = next((o for n, o in meshes.items() if n.endswith(a.body_suffix)), None)
    if body is None and meshes:
        body = max(meshes.values(), key=lambda o: len(o.data.vertices))
    weapons = [o for n, o in meshes.items() if o is not body
               and (a.weapon_suffix is None or any(n.endswith(s) for s in a.weapon_suffix))]
    base = None
    if a.base:
        before = set(sc.objects)
        bpy.ops.import_scene.fbx(filepath=a.base)
        base_objs = [o for o in sc.objects if o not in before and o.type == "MESH"]
    inv = arm.matrix_world.inverted()
    if a.base and base_objs:
        bco = [inv @ o.matrix_world @ v.co for o in base_objs for v in o.data.vertices]
        bx, by = [p.x for p in bco], [p.y for p in bco]
        base = {"top_cm": round(max(p.z for p in bco), 3),
                "center": Vector(((max(bx) + min(bx)) / 2, (max(by) + min(by)) / 2, 0.0)),
                "radius_cm": round(min(max(bx) - min(bx), max(by) - min(by)) / 2, 2)}
    B, P = arm.data.bones, arm.pose.bones
    rest = {n: {"head": [round(x, 3) for x in B[n].head_local], "tail": [round(x, 3) for x in B[n].tail_local],
                "parent": B[n].parent.name if B[n].parent else None} for n in B.keys()}
    res = {"tool": TOOL, "fbx": a.clip, "base": a.base, "options": {k: v for k, v in vars(a).items()
                                                                    if k not in ("clip", "out")},
           "summary": {}, "rest": rest, "frames": []}
    act = arm.animation_data.action if arm.animation_data else None
    if a.rest_only or act is None:
        res["summary"] = {"frames": 0, "rest_only": True}
        return res

    hand, low, up = "hand." + S, "arm_lower." + S, "arm_upper." + S
    wname = "weapon." + S if ("weapon." + S) in B else None
    names = {g.index: g.name for g in body.vertex_groups}
    vw = [{names[g.group]: g.weight for g in v.groups if g.group in names} for v in body.data.vertices]
    vdom = [max(w, key=w.get) if w else None for w in vw]
    polys = [tuple(p.vertices) for p in body.data.polygons]

    def pdom(p):
        acc = {}
        for i in p:
            for n, w in vw[i].items():
                acc[n] = acc.get(n, 0.0) + w
        return max(acc, key=acc.get) if acc else None

    fdom = [pdom(p) for p in polys]
    rest_co = [inv @ body.matrix_world @ v.co for v in body.data.vertices]

    # щит: вершины, жёстко на кости щита и дальше порога от её отрезка
    shield_v, shield_f, sh_bone = [], [], a.shield_bone
    if sh_bone and sh_bone in B:
        h0 = B[sh_bone].head_local
        ax = B[sh_bone].tail_local - h0

        def dseg(p):
            s = min(max((p - h0).dot(ax) / ax.length_squared, 0.0), 1.0)
            return (p - (h0 + ax * s)).length

        shield_v = [i for i, w in enumerate(vw) if w.get(sh_bone, 0) >= 0.999 and dseg(rest_co[i]) > a.shield_min_dist_cm]
        ss = set(shield_v)
        shield_f = [k for k, p in enumerate(polys) if all(i in ss for i in p)]
    sh_side = sh_bone[-1] if sh_bone else O
    sh_other = "L" if sh_side == "R" else "R"
    weapon_f = [k for k, d in enumerate(fdom) if wname and d == wname]
    weapon_ob_f = [k for k, d in enumerate(fdom) if d in CORE or d in ("arm_upper." + O, "arm_lower." + O, "hand." + O, up)]
    shield_ob_f = [k for k, d in enumerate(fdom) if d in CORE or d in ("arm_upper." + sh_other, "arm_lower." + sh_other,
                                                                       "hand." + sh_other) or (wname and d == wname)]
    wpolys, wrest, off = [], [], 0
    for o in weapons:
        wpolys += [tuple(off + i for i in p.vertices) for p in o.data.polygons]
        wrest += [inv @ o.matrix_world @ v.co for v in o.data.vertices]
        off += len(o.data.vertices)
    tip_ref = butt_ref = None
    if wname:
        wb = B[wname]
        wax = (wb.tail_local - wb.head_local).normalized()
        pts = [("b", i, rest_co[i]) for i, d in enumerate(vdom) if d == wname] + [("w", i, p) for i, p in enumerate(wrest)]
        if pts:
            key = lambda t: (t[2] - wb.head_local).dot(wax)  # noqa: E731
            butt_ref, tip_ref = min(pts, key=key)[:2], max(pts, key=key)[:2]

    def coords(obj):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh()
        co = [inv @ obj.matrix_world @ v.co for v in me.vertices]
        ev.to_mesh_clear()
        return co

    def bvh(co, faces):
        return BVHTree.FromPolygons(co, faces, all_triangles=False) if faces else None

    def rel_rest(x, y):
        return B[x].matrix_local.to_3x3().inverted() @ B[y].matrix_local.to_3x3()

    def rel_pose(x, y):
        return P[x].matrix.to_3x3().normalized().inverted() @ P[y].matrix.to_3x3().normalized()

    pairs = [(low, hand), ("arm_lower." + O, "hand." + O), (up, low)] + ([(hand, wname)] if wname else [])
    rr = {k: rel_rest(*k) for k in pairs}
    u0 = (B[low].head_local - B[up].head_local).normalized()
    f0_ = (B[hand].head_local - B[low].head_local).normalized()
    hinge_rest = u0.cross(f0_).normalized()
    sh_rest = B[sh_bone].matrix_local if shield_v else None
    f0, f1 = [int(round(x)) for x in act.frame_range]
    for f in range(f0, f1 + 1):
        sc.frame_set(f)
        co = coords(body)
        wco = [p for o in weapons for p in coords(o)]
        allco = co + wco
        row = {"f": f - f0}
        if wname:
            row["weapon_in_hand_deg"] = round(quat_angle_deg(_q(rr[(hand, wname)].inverted() @ rel_pose(hand, wname))), 3)
            wd = (P[wname].tail - P[wname].head).normalized()
            row["weapon_dir"] = [round(x, 3) for x in wd]
        else:
            row["weapon_in_hand_deg"] = None
        hs = rr[(low, hand)].inverted() @ rel_pose(low, hand)
        row["wrist_%s_deg" % S] = round(quat_angle_deg(_q(hs)), 2)
        row["wrist_%s_twist_swing" % S] = twist_swing_deg(_q(hs))
        row["wrist_%s_deg" % O] = round(quat_angle_deg(_q(rr[("arm_lower." + O, "hand." + O)].inverted()
                                                         @ rel_pose("arm_lower." + O, "hand." + O))), 3)
        et = rr[(up, low)].inverted() @ rel_pose(up, low)
        row["elbow_%s_twist_deg" % S] = twist_swing_deg(_q(et))[0]
        s_, e_, w_ = P[up].head, P[low].head, P[hand].head
        wup = P[up].matrix.to_3x3().normalized() @ B[up].matrix_local.to_3x3().normalized().inverted()
        nn = (e_ - s_).normalized().cross((w_ - e_).normalized())
        row["elbow_%s_offhinge_deg" % S] = round(math.degrees(nn.normalized().angle(wup @ hinge_rest)), 1) \
            if nn.length > 1e-6 else 0.0
        row["hand_head"] = [round(x, 3) for x in w_]
        for sd in ("R", "L"):
            row["elbow_%s_deg" % sd] = round(joint_angle_deg(P["arm_upper." + sd].head, P["arm_lower." + sd].head,
                                                             P["hand." + sd].head), 1)
            row["knee_%s_deg" % sd] = round(joint_angle_deg(P["leg_upper." + sd].head, P["leg_lower." + sd].head,
                                                            P["foot." + sd].head), 1)
            row["thigh_flex_%s_deg" % sd] = round(math.degrees((P["leg_upper." + sd].tail - P["leg_upper." + sd].head)
                                                               .angle(B["leg_upper." + sd].tail_local
                                                                      - B["leg_upper." + sd].head_local)), 1)
        # концы оружия и пятка в подставке
        if butt_ref:
            pick = lambda ref: co[ref[1]] if ref[0] == "b" else wco[ref[1]]  # noqa: E731
            butt, tip = pick(butt_ref), pick(tip_ref)
            row["butt_cm"] = [round(x, 2) for x in butt]
            row["tip_cm"] = [round(x, 2) for x in tip]
            if base:
                r = (Vector((butt.x, butt.y, 0)) - base["center"]).length
                row["butt_r_cm"] = round(r, 2)
                row["butt_below_top_cm"] = round(base["top_cm"] - butt.z, 3) if r < base["radius_cm"] else None
        # пересечения оружия с телом
        if wname:
            t_w = bvh(allco, [polys[k] for k in weapon_f] + [tuple(len(co) + i for i in p) for p in wpolys])
            t_ob = bvh(co, [polys[k] for k in weapon_ob_f])
            ov = t_w.overlap(t_ob) if (t_w and t_ob) else []
            reg = {}
            for _i, j in ov:
                reg[fdom[weapon_ob_f[j]]] = reg.get(fdom[weapon_ob_f[j]], 0) + 1
            row["weapon_body_pairs"], row["weapon_regions"] = len(ov), reg
        if shield_v:
            m = P[sh_bone].matrix @ sh_rest.inverted()
            row["shield_vs_forearm_cm"] = round(max((co[i] - m @ rest_co[i]).length for i in shield_v), 4)
            t_sh = bvh(co, [polys[k] for k in shield_f])
            ob_faces = shield_ob_f + ["W"] * len(wpolys)
            t_sh_ob = bvh(allco, [polys[k] for k in shield_ob_f] + [tuple(len(co) + i for i in p) for p in wpolys])
            ov = t_sh.overlap(t_sh_ob) if (t_sh and t_sh_ob) else []
            reg = {}
            for _i, j in ov:
                d = fdom[ob_faces[j]] if ob_faces[j] != "W" else "weapon_mesh"
                reg[d] = reg.get(d, 0) + 1
            row["shield_body_pairs"], row["shield_regions"] = len(ov), reg
            row["shield_min_z_cm"] = round(min(co[i].z for i in shield_v), 2)
        res["frames"].append(row)
    res["summary"] = summarize(res["frames"], S, base)
    return res


def _utf8_streams() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv=None) -> int:  # pragma: no cover - точка входа Blender
    _utf8_streams()
    argv = sys.argv if argv is None else argv
    try:
        a = parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        import bpy  # noqa: F401
    except ImportError:
        print("ERROR: grip_check.py запускается в Blender: blender -b --factory-startup --python "
              f"{TOOL} -- <clip.fbx> <out.json> …", file=sys.stderr)
        return 2
    if not os.path.isfile(a.clip) or (a.base and not os.path.isfile(a.base)):
        print(f"ERROR: нет файла {a.clip if not os.path.isfile(a.clip) else a.base}", file=sys.stderr)
        return 2
    res = measure(a)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False)
    print("GRIP_CHECK", json.dumps(res["summary"], ensure_ascii=False))
    if a.verbose:
        for r in res["frames"]:
            print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    if "bpy" in sys.modules:
        os._exit(code)  # Blender: без ожидания atexit-хуков (как пилотные копии)
    sys.exit(code)
