"""Armature and skin weights.

make_armature        bones [name, parent, head, tail(, frame)] with frame "final" (candidate metres, default)
                     or "source" (Tripo GLB metres, mapped by the seat transform)
bind_rules/bind_rigid  whole-figure flow (Medusa T4): weights by part rules on the joined body
heat_weights, rigid_weights, wing_span_weights, axis_blend_weights, cleanup_weights
                     seated flow: per part group, then cleanup (allowed bones, ramps, caps, max influences)
Moved unchanged from blender/build_candidate.py (0.4.0) and the per-hero builders of 2026-09-28; the vertex
group removal of cleanup_weights reads the group indices first (the Arthur/Merlin copies read freed memory,
fixed in the Harpy copy: same result, no crash)."""

from collections import Counter

import bpy
from mathutils import Vector

from .core import r, rv, scene_context, to_final_point


def make_armature(scene, profile, xform=None):
    """Returns (armature object, {bone: [head, tail]} in final metres rounded to 1e-5)."""
    cfg = profile["armature"]
    data = bpy.data.armatures.new(cfg["object"])
    arm = bpy.data.objects.new(cfg["object"], data)
    scene.collection.objects.link(arm)
    final = {}
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for spec in cfg["bones"]:
            name, parent, head, tail = spec[:4]
            frame = spec[4] if len(spec) > 4 else "final"
            if frame != "final" and xform is None:
                raise RuntimeError("bone %s is given in frame %r but this flow has no seat transform" % (name, frame))
            bone = data.edit_bones.new(name)
            bone.head, bone.tail = to_final_point(head, frame, xform), to_final_point(tail, frame, xform)
            final[name] = [rv(bone.head, 5), rv(bone.tail, 5)]
            if parent:
                bone.parent = data.edit_bones[parent]
            bone.use_connect = False
        bpy.ops.object.mode_set(mode="OBJECT")
    for bone in arm.pose.bones:
        bone.rotation_mode = "XYZ"
    return arm, final


# ------------------------------------------------------------------ whole-figure flow (Medusa T4)

def rule_weights(rule, z):
    if "bone" in rule:
        return [(rule["bone"], 1.0)]
    if "split_z" in rule:
        return rule_weights(rule["below"] if z < rule["split_z"] else rule["above"], z)
    b = rule["blend"]
    t = max(0.0, min(1.0, (z - b["center"]) / b["span"] + 0.5))
    return [(b["low"], 1 - t), (b["high"], t)]


def bind_rules(arm, body, rules_list, body_part_names):
    """Weights of the joined body by part rules (the SRC_<part> vertex groups mark the source parts)."""
    groups = {bone.name: body.vertex_groups.new(name=bone.name) for bone in arm.data.bones}
    rules = {}
    for rule in rules_list:
        for part in rule["parts"]:
            rules[part] = rule
    missing_rules = sorted(set(body_part_names) - set(rules))
    if missing_rules:
        raise RuntimeError("no weight rule for parts %s" % missing_rules)
    counts = {}
    for part in body_part_names:
        group = body.vertex_groups["SRC_" + part]
        indices = [v.index for v in body.data.vertices if any(g.group == group.index for g in v.groups)]
        counts[part] = len(indices)
        for index in indices:
            for bone, weight in rule_weights(rules[part], body.data.vertices[index].co.z):
                if weight > 1e-5:
                    groups[bone].add([index], weight, "REPLACE")
    for group in list(body.vertex_groups):
        if group.name.startswith("SRC_"):
            body.vertex_groups.remove(group)
    body.parent = arm
    body.modifiers.new("Armature", "ARMATURE").object = arm
    return counts


def bind_rigid(arm, obj, bone):
    """Whole-figure flow: all vertices 100 % on `bone` (new group), parent and armature modifier."""
    group = obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    obj.parent = arm
    obj.modifiers.new("Armature", "ARMATURE").object = arm


# ------------------------------------------------------------------ seated flow (heroes)

def point_segment_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared)) if ab.length_squared else 0.0
    return (p - (a + ab * t)).length


def heat_weights(scene, arm, objects, allowed):
    """Blender automatic weights restricted to `allowed` bones (others temporarily non-deforming)."""
    saved = {b.name: b.use_deform for b in arm.data.bones}
    for b in arm.data.bones:
        b.use_deform = b.name in allowed
    try:
        with scene_context(scene):
            bpy.ops.object.select_all(action="DESELECT")
            for obj in objects:
                obj.select_set(True)
            arm.select_set(True)
            bpy.context.view_layer.objects.active = arm
            bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    finally:
        for b in arm.data.bones:
            b.use_deform = saved[b.name]


def bind_to_armature(arm, obj):
    obj.parent = arm
    if not any(m.type == "ARMATURE" for m in obj.modifiers):
        obj.modifiers.new("Armature", "ARMATURE").object = arm


def rigid_weights(arm, obj, bone):
    group = obj.vertex_groups.get(bone) or obj.vertex_groups.new(name=bone)
    group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
    bind_to_armature(arm, obj)


def smoothstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def wing_span_weights(arm, obj, cfg, s_scale):
    """Span rule for a wing sheet (profile weights group "wing_span"). Returns measured joint spans."""
    upper, lower, hand = cfg["chain"]
    bones = arm.data.bones
    S = bones[upper].head_local.copy()
    E = bones[lower].head_local.copy()
    W = bones[hand].head_local.copy()
    T = bones[hand].tail_local.copy()
    d = Vector((T.x - S.x, T.y - S.y, 0.0)).normalized()

    def span(p):
        return (p.x - S.x) * d.x + (p.y - S.y) * d.y

    sE, sW, sT = span(E), span(W), span(T)
    band = cfg["joint_band_m"] * s_scale
    root = cfg["root_band_m"] * s_scale
    groups = {}
    for name in (cfg["root_to"], upper, lower, hand):
        groups[name] = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
    counts = Counter()
    for v in obj.data.vertices:
        sv = span(obj.matrix_world @ v.co)
        f1 = smoothstep((sv - (sE - band)) / (2 * band))
        f2 = smoothstep((sv - (sW - band)) / (2 * band))
        w = {hand: f2, lower: max(0.0, f1 - f2), upper: 1.0 - f1}
        if cfg.get("root_mode", "span") == "distance":
            fr = smoothstep(((obj.matrix_world @ v.co) - S).length / root) if root > 0 else 1.0
        else:
            fr = smoothstep(sv / root) if root > 0 else 1.0
        w[cfg["root_to"]] = w[upper] * (1.0 - fr)
        w[upper] *= fr
        for name, value in w.items():
            if value > 0:
                groups[name].add([v.index], value, "REPLACE")
        counts[max(w, key=w.get)] += 1
    bind_to_armature(arm, obj)
    return {"direction_xy": rv(d, 4), "span_elbow_m": r(sE, 5), "span_wrist_m": r(sW, 5), "span_tip_m": r(sT, 5),
            "joint_band_m": r(band, 5), "root_band_m": r(root, 5), "root_mode": cfg.get("root_mode", "span"),
            "dominant_bone_vertices": dict(sorted(counts.items()))}


def axis_blend_weights(arm, obj, cfg, to_final):
    """Geometric two-bone blend along one axis (no heat): weight of `to` = smoothstep between the two
    coordinates (profile frame, mapped by to_final), the rest on `from`."""
    axis = cfg.get("axis", "z")
    k = {"x": 0, "y": 1, "z": 2}[axis]
    a, b = to_final(axis, cfg["zero_below"]), to_final(axis, cfg["full_above"])
    g_from = obj.vertex_groups.get(cfg["from"]) or obj.vertex_groups.new(name=cfg["from"])
    g_to = obj.vertex_groups.get(cfg["to"]) or obj.vertex_groups.new(name=cfg["to"])
    for v in obj.data.vertices:
        f = smoothstep(((obj.matrix_world @ v.co)[k] - a) / (b - a))
        if f < 1.0:
            g_from.add([v.index], 1.0 - f, "REPLACE")
        if f > 0.0:
            g_to.add([v.index], f, "REPLACE")
    bind_to_armature(arm, obj)


def group_allowed_bones(rule):
    """Bones a weight group may use: rigid bone, wing chain + root, axis-blend pair or the heat list."""
    if "rigid" in rule:
        return {rule["rigid"]}
    if "wing_span" in rule:
        return set(rule["wing_span"]["chain"]) | {rule["wing_span"]["root_to"]}
    if "axis_blend" in rule:
        return {rule["axis_blend"]["from"], rule["axis_blend"]["to"]}
    return set(rule["heat"])


def ramp_factor(ramp, value, to_final):
    """Fraction of the ramped bones' weight that is KEPT at `value` (smoothstep) on the ramp axis.
    Keys: zero_above_z/full_below_z or zero_below_z/full_above_z (axis z), or with "axis": x|y|z the keys
    zero_above/full_below or zero_below/full_above."""
    axis = ramp.get("axis", "z")
    suffix = "" if "axis" in ramp else "_z"
    if ("zero_above" + suffix) in ramp:
        a, b = to_final(axis, ramp["zero_above" + suffix]), to_final(axis, ramp["full_below" + suffix])
        f = (a - value) / (a - b)
    else:
        a, b = to_final(axis, ramp["zero_below" + suffix]), to_final(axis, ramp["full_above" + suffix])
        f = (value - a) / (b - a)
    return smoothstep(f)


def cleanup_weights(arm, obj, allowed, rule, max_influences, clean_below, to_final):
    """Weight cleanup of one part: (1) keep only the group's bones, normalise, nearest-bone fallback for
    vertices the solve left empty; (2) ramps, caps, drop < clean_below, keep the strongest max_influences,
    normalise. No edge smoothing: Tripo's retopology has long edges joining distant regions and edge averaging
    raised the probe-pose stretch (King Arthur 2026-09-28: arm_l_raise 1.46x -> 3.10x)."""
    bones = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local) for b in arm.data.bones}
    names = {g.index: g.name for g in obj.vertex_groups}
    groups = {g.name: g for g in obj.vertex_groups}
    for name in allowed:
        if name not in groups:
            groups[name] = obj.vertex_groups.new(name=name)
    caps = rule.get("caps") or {}
    excess_by_bone = rule.get("cap_excess_to_by_bone") or {}
    excess_to = rule.get("cap_excess_to")
    stats = Counter()
    mw = obj.matrix_world
    mesh = obj.data
    weights = []
    for v in mesh.vertices:
        ws = {}
        for g in v.groups:
            n = names.get(g.group)
            if n in allowed and g.weight > 0:
                ws[n] = ws.get(n, 0.0) + g.weight
            elif g.weight > 0:
                stats["foreign_weights_removed"] += 1
        total = sum(ws.values())
        if total <= 0:
            p = mw @ v.co
            best = min(sorted(allowed), key=lambda n: point_segment_distance(p, *bones[n]))
            ws = {best: 1.0}
            stats["fallback_nearest_bone"] += 1
        else:
            ws = {n: w / total for n, w in ws.items()}
        weights.append(ws)
    axis_index = {"x": 0, "y": 1, "z": 2}
    for v, ws in zip(mesh.vertices, weights):
        p = mw @ v.co
        for ramp in rule.get("height_ramps") or []:
            f = ramp_factor(ramp, p[axis_index[ramp.get("axis", "z")]], to_final)
            for bone in ramp["bones"]:
                w = ws.get(bone, 0.0)
                if w > 0 and f < 1.0:
                    ws[bone] = w * f
                    ws[ramp["to"]] = ws.get(ramp["to"], 0.0) + w * (1.0 - f)
                    stats["ramped_%s" % ramp.get("axis", "z")] += 1
        for bone, cap in sorted(caps.items()):
            if ws.get(bone, 0.0) > cap:
                extra = ws[bone] - cap
                ws[bone] = cap
                target = excess_by_bone.get(bone, excess_to)
                ws[target] = ws.get(target, 0.0) + extra
                stats["capped"] += 1
        kept = {n: w for n, w in ws.items() if w >= clean_below}
        if not kept:
            kept = {max(ws, key=ws.get): 1.0}
        if len(kept) > max_influences:
            kept = dict(sorted(kept.items(), key=lambda kv: (-kv[1], kv[0]))[:max_influences])
            stats["limited_to_max_influences"] += 1
        total = sum(kept.values())
        kept = {n: w / total for n, w in kept.items()}
        # read the group indices first: removing an entry reallocates v.groups, so VertexGroupElement references
        # taken before the removal point to freed memory (a crash of the first Harpy build, 2026-09-28)
        for gi in [g.group for g in v.groups]:
            obj.vertex_groups[gi].remove([v.index])
        for n, w in sorted(kept.items()):
            groups[n].add([v.index], w, "REPLACE")
    for g in list(obj.vertex_groups):
        if g.name not in allowed:
            obj.vertex_groups.remove(g)
    return dict(sorted(stats.items()))
