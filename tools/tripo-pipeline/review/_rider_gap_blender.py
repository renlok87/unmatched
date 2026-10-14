"""Blender-часть rider_gap.py: замер зазора «наездника» в rest и по кадрам клипов. ТОЛЬКО headless.

    blender -b --factory-startup --python tools/tripo-pipeline/review/_rider_gap_blender.py -- <cfg.json>

cfg.json пишет обёртка: {"parts_blend", "rest_fbx", "clips": {имя: fbx}, "pairs": [{name, rider[], perch[]|null}],
"scan": [{name, parts[], bone}] (прежняя форма {часть: кость} тоже читается), "same_bone": {часть: [соседи по кости]}
(C47: в опору auto не идут), "base_parts": [...], "auto_margin_m", "window_m", "match_warn_m", "pen_eval_m",
"raw_out"}.
Выход — сырой замер raw_out (вердикты считает обёртка): сопоставление частей, опоры auto, rest (пары и скан), клипы
(пары по кадрам). Печатает RIDER_GAP_RAW_OK.

«Внутри части» для точки: нормаль ближайшей грани ЭТОЙ части смотрит от точки, точка ближе pen_eval_m к её
поверхности и обобщённое число оборотов этой части |w| ≥ 0,5 (rider_gap.winding_numbers). Чётность лучей не
годится: части h2_bake с открытыми петлями стыков (ворона плеча Leshen — 74 открытых ребра) давали ложные 3 мм.
"""
import json
import os
import sys
from collections import Counter

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rider_gap import auto_perch, fan_triangles, part_sort_key, winding_numbers  # noqa: E402  (чистые функции)

if not bpy.app.background:
    raise RuntimeError("_rider_gap_blender.py: только headless (blender -b)")

NEAR_BONES_M = 0.005  # кости опоры у детали: вершины опоры не дальше gap + 5 мм
INSIDE_W = 0.5        # |число оборотов| ≥ 0,5 — точка внутри части
INF = float("inf")


def r6(x):
    return None if x is None or x == INF else round(float(x), 6)


# ---------------------------------------------------------------------------------------------- части (lp_uv.blend)

def lp_points(path):
    """Точки частей LP_<часть> (мир блендa, м) → (N×3, имена частей)."""
    bpy.ops.wm.open_mainfile(filepath=path)
    pts, names = [], []
    for o in sorted(bpy.context.scene.objects, key=lambda o: o.name):
        if o.type != "MESH" or not o.name.startswith("LP_"):
            continue
        me = o.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        mw = np.array(o.matrix_world)
        pts.append(co @ mw[:3, :3].T + mw[:3, 3])
        names += [o.name[3:]] * len(co)
    if not pts:
        raise RuntimeError("%s: нет объектов LP_<часть>" % path)
    return np.concatenate(pts), names


FRAMES = {  # рамка частей → мировая рамка FBX
    "UM_FBX_v1 (−y, x, z)": lambda p: np.column_stack((-p[:, 1], p[:, 0], p[:, 2])),
    "identity": lambda p: p,
}


class PartMap:
    """KD-дерево точек частей в рамке FBX (из FRAMES — та, где среднее расстояние совпадения меньше: медиана не
    различает рамки, если большая часть точек симметрична относительно поворота); part_of → (части, расст.)."""

    def __init__(self, pts, names, sample):
        best = None
        sub = sample[np.linspace(0, len(sample) - 1, min(len(sample), 2000)).astype(int)]
        for label, fn in FRAMES.items():
            kd = self._kd(fn(pts))
            mean = float(np.mean([kd.find(Vector(p))[2] for p in sub]))
            if best is None or mean < best[0]:
                best = (mean, label, kd)
        self.frame, self.kd, self.names = best[1], best[2], names

    @staticmethod
    def _kd(q):
        kd = KDTree(len(q))
        for i, p in enumerate(q):
            kd.insert(Vector(p), i)
        kd.balance()
        return kd

    def part_of(self, coords):
        parts, dist = [], np.empty(len(coords))
        for i, p in enumerate(coords):
            _co, idx, d = self.kd.find(Vector(p))
            parts.append(self.names[idx])
            dist[i] = d
        return parts, dist


# ---------------------------------------------------------------------------------------------- FBX

def load_fbx(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path, use_anim=True)
    objs = list(bpy.context.scene.objects)
    meshes = sorted((o for o in objs if o.type == "MESH"), key=lambda o: o.name)
    arm = next((o for o in objs if o.type == "ARMATURE"), None)
    if not meshes:
        raise RuntimeError("%s: нет мешей" % path)
    return arm, meshes


def bind_coords(meshes):
    out = []
    for o in meshes:
        me = o.data
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        mw = np.array(o.matrix_world)
        out.append(co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
    return np.concatenate(out)


def posed_coords(meshes):
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for o in meshes:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get("co", co)
        mw = np.array(ev.matrix_world)
        out.append(co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3])
        ev.to_mesh_clear()
    return np.concatenate(out)


def polygons(meshes):
    polys, off = [], 0
    for o in meshes:
        polys += [tuple(off + v for v in p.vertices) for p in o.data.polygons]
        off += len(o.data.vertices)
    return polys


def dominant_bones(meshes):
    out = []
    for o in meshes:
        names = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            best = max(v.groups, key=lambda g: g.weight, default=None)
            out.append((names.get(best.group, ""), round(best.weight, 4)) if best is not None else ("", 0.0))
    return out


def open_edges(faces):
    ec = Counter()
    for f in faces:
        for a, b in zip(f, f[1:] + f[:1]):
            ec[(a, b) if a < b else (b, a)] += 1
    return sum(1 for c in ec.values() if c == 1)


# ---------------------------------------------------------------------------------------------- геометрия

class PartGeom:
    """Одна часть в одном состоянии: BVH (ближайшая точка с нормалью грани) и треугольники (число оборотов)."""

    def __init__(self, vecs, co, faces, tris):
        self.bvh = BVHTree.FromPolygons(vecs, faces, all_triangles=False)
        self.tris = co[np.asarray(tris, dtype=np.int64)]


def part_geoms(vecs, co, faces_by_part, tris_by_part):
    return {p: PartGeom(vecs, co, f, tris_by_part[p]) for p, f in faces_by_part.items() if f}


class Surface:
    """Набор частей. stats(ids) → наименьшее расстояние без знака (вершина, часть) и наименьшее со знаком по всем
    частям набора: минус — точка внутри части (нормаль ближайшей грани этой части смотрит от точки, точка ближе
    pen_eval к её поверхности и |число оборотов этой части| ≥ 0,5; число оборотов — пакетом по части)."""

    def __init__(self, geoms, parts, pen_eval):
        self.by_part = {p: geoms[p] for p in parts if p in geoms}
        self.empty = not self.by_part
        self.pen_eval = pen_eval

    def nearest(self, v):
        best = None
        for part, g in self.by_part.items():
            loc, _n, _i, d = g.bvh.find_nearest(v)
            if loc is not None and (best is None or d < best[1]):
                best = (part, d)
        return best

    def stats(self, vecs, co, ids):
        best_u, best_i, best_part, min_s = INF, None, None, INF
        for part, g in self.by_part.items():
            neg_i, neg_d = [], []
            for i in ids:
                v = vecs[i]
                loc, n, _fi, d = g.bvh.find_nearest(v)
                if loc is None:
                    continue
                if d < best_u:
                    best_u, best_i, best_part = d, i, part
                if (v - loc).dot(n) < 0 and d <= self.pen_eval:
                    neg_i.append(i)
                    neg_d.append(d)
                elif d < min_s:
                    min_s = d
            if neg_i:
                w = winding_numbers(co[np.asarray(neg_i)], g.tris)
                for d, wi in zip(neg_d, w):
                    min_s = min(min_s, -d if abs(wi) >= INSIDE_W else d)
        return best_u, best_i, best_part, min_s


def ids_of(idx, parts):
    got = [idx[p] for p in parts if p in idx]
    return np.concatenate(got) if got else np.array([], int)


def in_window(co, ids, lo, hi):
    if not len(ids):
        return ids
    c = co[ids]
    return ids[np.all((c >= lo) & (c <= hi), axis=1)]


def measure(vecs, co, idx, geoms, rider, perch, others, window, pen_eval):
    """Замер пары в одном состоянии: зазор и проникновение деталь ↔ опора (вершины детали → поверхность опоры и
    вершины опоры в окне детали → поверхность детали), то же против остальных частей."""
    rs, ps = Surface(geoms, rider, pen_eval), Surface(geoms, perch, pen_eval)
    rv = ids_of(idx, rider)
    if rs.empty or ps.empty or not len(rv):
        return {"gap_m": None, "pen_m": None, "note": "пустая деталь или опора"}
    lo, hi = co[rv].min(0) - window, co[rv].max(0) + window
    u1, v1, part1, s1 = ps.stats(vecs, co, rv)
    u2, _v2, _p2, s2 = rs.stats(vecs, co, in_window(co, ids_of(idx, perch), lo, hi))
    pen = max(0.0, -s1, -s2)
    gap = 0.0 if pen > 0 else min(u1, u2)
    out = {"gap_m": r6(gap), "pen_m": r6(pen), "rider_to_perch_signed_m": r6(s1), "perch_to_rider_signed_m": r6(s2),
           "closest_rider_vertex_m": [round(float(x), 5) for x in co[v1]] if v1 is not None else None,
           "closest_perch_part": part1}
    os_ = Surface(geoms, others, pen_eval)
    if not os_.empty:
        ou1, _ov, opart, os1 = os_.stats(vecs, co, rv)
        ou2, _ov2, _op2, os2 = rs.stats(vecs, co, in_window(co, ids_of(idx, others), lo, hi))
        out.update({"others_gap_m": r6(min(ou1, ou2)), "others_pen_m": r6(max(0.0, -os1, -os2)),
                    "others_nearest_part": opart})
    return out


def part_distances(vecs, idx, geoms, rider, candidates):
    """{часть: минимальное расстояние вершин детали до поверхности части} — для опоры auto."""
    rv = ids_of(idx, rider)
    out = {}
    for p in candidates:
        if p not in geoms:
            continue
        ds = [geoms[p].bvh.find_nearest(vecs[i])[3] for i in rv]
        ds = [d for d in ds if d is not None]
        out[p] = min(ds) if ds else None
    return out


def bones_near(vecs, idx, bones, geoms, rider, perch, limit):
    """Доли доминирующих костей вершин опоры не дальше limit от детали; доли костей детали и наименьший вес."""
    rs = Surface(geoms, rider, 0.0)
    hist = Counter()
    for i in ids_of(idx, perch):
        hit = rs.nearest(vecs[i])
        if hit is not None and hit[1] <= limit:
            hist[bones[i][0]] += 1
    tot = sum(hist.values()) or 1
    rid = ids_of(idx, rider)
    rh = Counter(bones[i][0] for i in rid)
    return ({b: round(n / tot, 3) for b, n in hist.most_common()},
            {"bones": {b: round(n / len(rid), 3) for b, n in rh.most_common()},
             "min_dominant_weight": round(min(bones[i][1] for i in rid), 4) if len(rid) else None})


def scan_part(vecs, co, idx, geoms, part, rest_parts, window, pen_eval, parts=None):
    """Жёсткая часть (или группа частей одной кости, C47: parts) против всей остальной фигуры: зазор поверхностей,
    ближайшая часть, утоплена ли."""
    parts = list(parts or [part])
    rs, os_ = Surface(geoms, parts, pen_eval), Surface(geoms, rest_parts, pen_eval)
    if rs.empty or os_.empty:
        out = {"part": part, "gap_m": None, "note": "пустая часть"}
        if len(parts) > 1:
            out["parts"] = parts
        return out
    rv = ids_of(idx, parts)
    lo, hi = co[rv].min(0) - window, co[rv].max(0) + window
    u1, v1, part1, _s1 = os_.stats(vecs, co, rv)
    u2 = min((h[1] for h in (rs.nearest(vecs[i]) for i in in_window(co, ids_of(idx, rest_parts), lo, hi)) if h),
             default=INF)
    gap = min(u1, u2)
    item = {"part": part, "gap_m": r6(gap), "nearest_part": part1,
            "closest_vertex_m": [round(float(x), 5) for x in co[v1]] if v1 is not None else None, "embedded": False}
    if len(parts) > 1:
        item["parts"] = parts
    if gap > 1e-4:  # не касается: утоплена ли (половина выборки вершин внутри остальных частей)?
        sample = rv[np.linspace(0, len(rv) - 1, min(len(rv), 60)).astype(int)]
        inside = 0
        for g in os_.by_part.values():
            w = winding_numbers(co[sample], g.tris)
            inside = max(inside, int((np.abs(w) >= INSIDE_W).sum()))
        item["inside_share"] = round(inside / len(sample), 3)
        item["embedded"] = inside / len(sample) >= 0.5
    return item


# ---------------------------------------------------------------------------------------------- main

def setup_state(meshes, pmap, base, warnings, label, match_warn):
    """Части вершин по bind-координатам меша; грани и треугольники по частям (только грани одной части)."""
    bind = bind_coords(meshes)
    vparts, dist = pmap.part_of(bind)
    far = int((dist > match_warn).sum())
    if far:
        warnings.append("%s: %d вершин дальше %.1f мм от точки своей части (худшая %.2f мм)"
                        % (label, far, match_warn * 1e3, float(dist.max()) * 1e3))
    faces_by_part, split = {}, 0
    for f in polygons(meshes):
        own = Counter(vparts[v] for v in f)
        p = own.most_common(1)[0][0] if len(own) > 1 else vparts[f[0]]
        split += len(own) > 1  # грань на стыке (сваренные петли close): к части большинства её вершин
        if p not in base:
            faces_by_part.setdefault(p, []).append(f)
    idx = {}
    for i, p in enumerate(vparts):
        if p not in base:
            idx.setdefault(p, []).append(i)
    return {"dist": dist, "faces_by_part": faces_by_part, "idx": {p: np.array(v, int) for p, v in idx.items()},
            "tris_by_part": {p: fan_triangles(f) for p, f in faces_by_part.items()}, "n": len(bind),
            "junction_faces": split}


def main():
    cfg = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
    warnings = []
    base = set(cfg.get("base_parts") or [])
    window, margin, match_warn, pen_eval = cfg["window_m"], cfg["auto_margin_m"], cfg["match_warn_m"], cfg["pen_eval_m"]
    pts, names = lp_points(cfg["parts_blend"])
    all_parts = sorted(set(names), key=part_sort_key)

    arm, meshes = load_fbx(cfg["rest_fbx"])
    pmap = PartMap(pts, names, bind_coords(meshes))
    st = setup_state(meshes, pmap, base, warnings, "rest", match_warn)
    base |= {p for p in all_parts if p not in st["idx"]}  # части без вершин в FBX (подставка отдельным FBX)
    fig_parts = [p for p in all_parts if p not in base]
    for pr in cfg["pairs"]:
        bad = [p for p in pr["rider"] + (pr["perch"] or []) if p not in fig_parts]
        if bad:
            raise RuntimeError("пара %s: частей %s нет в фигуре (есть %s)" % (pr["name"], bad, fig_parts))
    co = posed_coords(meshes)  # rest: арматура в позе покоя импорта
    vecs = [Vector(p) for p in co]
    geoms = part_geoms(vecs, co, st["faces_by_part"], st["tris_by_part"])
    bones = dominant_bones(meshes)

    same_bone = cfg.get("same_bone") or {}  # C47: соседи детали по кости — одно тело с ней, не опора

    def attached(parts):
        return {q for p in parts for q in same_bone.get(p, [])} - set(parts)

    scan_cfg = cfg.get("scan") or []
    if isinstance(scan_cfg, dict):  # прежняя форма {часть: кость}
        scan_cfg = [{"name": p, "parts": [p], "bone": b} for p, b in scan_cfg.items()]
    perch_of, rest_pairs = {}, {}
    for pr in cfg["pairs"]:
        rider = pr["rider"]
        sib = attached(rider)
        dist = part_distances(vecs, st["idx"], geoms, rider, [p for p in fig_parts if p not in rider and p not in sib])
        perch = pr["perch"] or auto_perch(dist, margin)
        perch_of[pr["name"]] = perch
        others = [p for p in fig_parts if p not in rider and p not in perch and p not in sib]
        m = measure(vecs, co, st["idx"], geoms, rider, perch, others, window, pen_eval)
        near, rider_bones = bones_near(vecs, st["idx"], bones, geoms, rider, perch,
                                       (m.get("gap_m") or 0.0) + NEAR_BONES_M)
        cand = sorted(((p, d) for p, d in dist.items() if d is not None), key=lambda kv: kv[1])[:6]
        m.update({"perch_candidates_m": {p: r6(d) for p, d in cand}, "perch_bones_near_rider": near,
                  "rider_bones": rider_bones, "rider_vertices": int(len(ids_of(st["idx"], rider))),
                  "perch_faces": int(sum(len(st["faces_by_part"].get(p, [])) for p in perch))})
        rest_pairs[pr["name"]] = m
    scan = []
    for unit in sorted(scan_cfg, key=lambda u: part_sort_key(u["parts"][0])):
        missing = [p for p in unit["parts"] if p not in fig_parts]
        if missing:
            warnings.append("скан: части %s нет в фигуре" % "+".join(missing))
            continue
        excl = set(unit["parts"]) | attached(unit["parts"])
        rest_parts = [p for p in fig_parts if p not in excl]
        item = scan_part(vecs, co, st["idx"], geoms, unit["name"], rest_parts, window, pen_eval, unit["parts"])
        item["bone"] = unit["bone"]
        # опора скана в клипах (F133 у детали без пары): ближайшие части в rest, как опора auto пары
        dist = part_distances(vecs, st["idx"], geoms, unit["parts"], rest_parts)
        item["perch"] = auto_perch(dist, margin)
        scan.append(item)
    involved = {p for pr in cfg["pairs"] for p in pr["rider"] + perch_of[pr["name"]]} | \
        {p for u in scan_cfg for p in u["parts"]}
    raw = {
        "blender": bpy.app.version_string,
        "mapping": {"parts_frame": pmap.frame, "vertices": st["n"], "worst_match_m": r6(st["dist"].max()),
                    "median_match_m": r6(np.median(st["dist"])), "junction_faces": st["junction_faces"],
                    "per_part": {p: int(len(v)) for p, v in sorted(st["idx"].items(), key=lambda kv: part_sort_key(kv[0]))},
                    "base_parts": sorted(base, key=part_sort_key)},
        # справка: открытые петли стыков h2_bake (части вставлены друг в друга); «внутри» решает число оборотов
        "parts_open_edges": {p: open_edges(st["faces_by_part"][p])
                             for p in sorted(involved, key=part_sort_key) if p in st["faces_by_part"]},
        "perch": perch_of,
        "rest": {"armature": arm.name if arm else None, "pairs": rest_pairs, "scan": scan},
        "clips": {},
        "warnings": warnings,
    }

    for clip, path in cfg["clips"].items():
        arm, meshes = load_fbx(path)
        cst = setup_state(meshes, pmap, base, warnings, clip, match_warn)
        if cst["n"] != st["n"]:
            warnings.append("%s: вершин %d, у rest %d — другой меш?" % (clip, cst["n"], st["n"]))
        act = arm.animation_data.action if arm is not None and arm.animation_data else None
        if act is None:
            raise RuntimeError("%s: нет действия арматуры" % path)
        f0, f1 = [int(round(x)) for x in act.frame_range]
        scene = bpy.context.scene
        rows = {pr["name"]: [] for pr in cfg["pairs"]}
        # скан в клипе: только зазор до опоры rest (без проникновения: копьё в кулаке, рог в черепе утоплены по
        # построению); утопленная в rest часть не проверяется
        scan_live = [it for it in scan if it.get("gap_m") is not None and not it.get("embedded") and it["perch"]]
        scan_rows = {it["part"]: [] for it in scan_live}
        for f in range(f0, f1 + 1):
            scene.frame_set(f)
            co_f = posed_coords(meshes)
            vecs_f = [Vector(p) for p in co_f]
            geoms_f = part_geoms(vecs_f, co_f, cst["faces_by_part"], cst["tris_by_part"])
            for pr in cfg["pairs"]:
                perch = perch_of[pr["name"]]
                sib = attached(pr["rider"])
                others = [p for p in fig_parts if p not in pr["rider"] and p not in perch and p not in sib]
                m = measure(vecs_f, co_f, cst["idx"], geoms_f, pr["rider"], perch, others, window, pen_eval)
                m["f"] = f - f0
                rows[pr["name"]].append(m)
            for it in scan_live:
                m = measure(vecs_f, co_f, cst["idx"], geoms_f, it.get("parts") or [it["part"]], it["perch"], [],
                            window, 0.0)
                scan_rows[it["part"]].append({"f": f - f0, "gap_m": m.get("gap_m")})
        raw["clips"][clip] = {"action": act.name, "frame_range": [f0, f1], "rows": rows, "scan_rows": scan_rows}
        print("CLIP", clip, f1 - f0 + 1, "frames")
        sys.stdout.flush()
    with open(cfg["raw_out"], "w", encoding="utf-8") as fh:
        json.dump(raw, fh, ensure_ascii=False)
    print("RIDER_GAP_RAW_OK")
    sys.stdout.flush()


try:
    main()
except Exception as e:  # noqa: BLE001 — код выхода 1 и причина в stdout для обёртки
    import traceback
    traceback.print_exc()
    print("RIDER_GAP_ERROR %s" % e)
    sys.stdout.flush()
    os._exit(1)
os._exit(0)
