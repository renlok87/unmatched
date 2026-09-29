"""Flow "seated-parts" (profile build.flow): heroes and helpers built from a segmented Tripo GLB.

One algorithm for King Arthur, Merlin and Harpy (2026-09-28: three per-hero scripts); every difference between
them is a profile setting:
  1. import the GLB, bake part transforms, capture the imported corner normals (float corner attribute);
     [orientation.per_face_reference] per-face orientation votes against the reference high-poly GLB;
  2. drop parts (meshes.drop_parts); the figure is scaled uniformly about the source base top so the top part
     (scale.top_part) reaches scale.figure_height_m, and seated on the base top; the base is either the
     normalised Tripo base part (meshes.base.mode "normalise-part": scaled to its footprint separately) or a
     parametric base built later (mode "parametric", section base_parametric);
  3. atlas UVs and material (materials.atlas), weld inside every part, part labels (face attribute);
  4. closure: base-top footprint holes and open soles (section closure), fan caps of listed open loops
     (section open_loop_caps);
  5. weapon (meshes.weapon.mode): "split-from-part" (split off a fused fist, grip bridge on the fitted axis;
     section weapon_split), "parts" (whole GLB parts joined, shaft bridge and bottom cap; section
     weapon_assembly), "part" (one whole part) or none (meshes.weapon null);
  6. captured corner normals re-applied (the normalised base: inverse-transpose of its scale); ray-escape
     orientation per part, inside-out parts flipped (after the per-face reference fix if configured);
  7. armature (bones in the final or the source frame), weights per part group: rigid, bone heat, wing span,
     axis blend; cleanup with ramps/caps in weights.coordinates_frame; the weapon rigid on its bone;
  8. body joined; measurements (anatomy from the profile or detected, sockets incl. the UE bone-space offset,
     figure top vs skeletal top, closure diagnostics); work .blend; UM_FBX_v1 export; round trip; checks.
The operations and their order are those of the per-hero scripts, so the FBX bytes are reproduced.
"""

import math
import re
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

from . import anatomy as anatomy_mod
from .base import base_material, build_parametric_base
from .closure import cap_base_top, cap_loops_component, cap_soles
from .core import (CN_ATTR, PART_ATTR, REF_FLIP_ATTR, ROUNDTRIP_SCENE, WORK_SCENE, export_pair,
                   export_settings_report, flip_polygons, import_fbx_into, import_glb, r, rv, sha256,
                   to_authored_frame, transform_for_fbx)
from .measure import (AXIS_VECTORS, along, axis_name, boundary_edge_count, cell_rects, centroid,
                      cross_part_coincident, inconsistent_winding_edges, labelled_objects, mask_census,
                      mesh_summary, orientation_scores, part_points, polygons_by_part, roundtrip_measure,
                      see_through_rays, ue_bone_local_from_blender_uu, ue_from_blender_m, ue_predicted,
                      uv_statistics, weight_summary, world_bounds)
from .mesh_ops import (apply_corner_normals, atlas_material, bake_parts, capture_corner_normals,
                       corner_normal_agreement, dist_to_line, islands, join_objects, label_faces, material_pixels,
                       opposed_corner_fraction, part_number, read_face_labels, remap_uvs, remove_attribute,
                       weld_part)
from .orientation import read_glb_node_triangles, reference_votes, smooth_orientation
from .rig import (axis_blend_weights, cleanup_weights, group_allowed_bones, heat_weights, make_armature,
                  rigid_weights, wing_span_weights)
from .weapon import cap_loops_chain, grip_bridge_axis, grip_bridge_fitted, split_weapon, staff_axis

AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def bbox_centre(points):
    return Vector([(min(p[a] for p in points) + max(p[a] for p in points)) / 2 for a in range(3)])


def summaries_of(obj, labels):
    out = {}
    for part, ix in labels.items():
        pts = part_points(obj, ix)
        if pts:
            out[part] = {"min": [min(p[a] for p in pts) for a in range(3)],
                         "max": [max(p[a] for p in pts) for a in range(3)],
                         "centroid": [sum(p[a] for p in pts) / len(pts) for a in range(3)], "polygons": len(ix)}
    return out


def run(ctx):
    profile, params, atlas, preset = ctx.profile, ctx.params, ctx.atlas, ctx.preset
    check = ctx.checks
    m = profile["meshes"]
    wmesh = m.get("weapon") or None
    wmode = wmesh["mode"] if wmesh else None
    bmode = m["base"]["mode"]
    base_src = m["base"]["part"] if bmode == "normalise-part" else m["base"]["source_part"]
    anat_cfg = profile.get("anatomy") or {}
    axes_cfg = profile.get("axes") or {}
    ocfg = profile["orientation"]
    rcfg = ocfg.get("per_face_reference")
    closure_cfg = profile.get("closure") or {}
    size = atlas["size"]
    cells = atlas["cells"]
    rects = cell_rects(cells, size)
    rot3 = ctx.rot3
    export_axes = {"front": rot3 @ Vector((0.0, -1.0, 0.0)), "left": rot3 @ Vector((1.0, 0.0, 0.0)),
                   "right": rot3 @ Vector((-1.0, 0.0, 0.0))}
    if axes_cfg.get("blender_weapon_side"):
        export_axes["weapon_side"] = rot3 @ Vector(AXIS_VECTORS[axes_cfg["blender_weapon_side"]])
    reference = reference_hash = None
    if rcfg:
        if not params.get("reference_glb"):
            raise RuntimeError("orientation.per_face_reference needs params.reference_glb (registered source %s:%s)"
                               % (rcfg.get("source_id"), rcfg.get("role")))
        reference = Path(params["reference_glb"])
        reference_hash = sha256(reference)

    scene = ctx.new_scene(WORK_SCENE)
    import_glb(scene, ctx.source)
    parts = bake_parts(scene, ctx.namer)
    if len(parts) != profile["expected_part_count"]:
        raise RuntimeError("expected %d mesh parts, found %d" % (profile["expected_part_count"], len(parts)))
    source_polys = {n: len(o.data.polygons) for n, o in sorted(parts.items())}
    for _name, obj in sorted(parts.items()):
        capture_corner_normals(obj)  # float corner attribute, re-applied after the topology edits

    # ---- per-face reference vote (source frame) for parts with mixed winding
    orient_raw = ref_votes = None
    if rcfg:
        orient_raw = orientation_scores([(o, {n: [p.index for p in o.data.polygons]}) for n, o in sorted(parts.items())])
        ref = read_glb_node_triangles(reference, rcfg["parts"])
        ref_votes = {}
        for name in rcfg["parts"]:
            votes, info = reference_votes(parts[name], ref[name][0], ref[name][1], rcfg["max_reference_distance_m"])
            attr = parts[name].data.attributes.new(REF_FLIP_ATTR, "FLOAT", "FACE")
            attr.data.foreach_set("value", votes)
            ref_votes[name] = info
        ref.clear()

    # ---- base reference (source frame), dropped parts
    blo, bhi = world_bounds([parts[base_src]])
    cx, cy = (blo[0] + bhi[0]) / 2, (blo[1] + bhi[1]) / 2
    base_top_src, base_bottom_src = bhi[2], blo[2]
    dropped = {}
    for name, why in sorted((m.get("drop_parts") or {}).items()):
        obj = parts.pop(name)
        lo, hi = world_bounds([obj])
        dropped[name] = {"reason": why, "polygons": len(obj.data.polygons), "vertices": len(obj.data.vertices),
                         "source_size": rv([hi[i] - lo[i] for i in range(3)], 6),
                         "source_bounds": {"min": rv(lo, 5), "max": rv(hi, 5)}}
        bpy.data.objects.remove(obj)

    # ---- scale and seat: figure uniform about the source base top, base normalised to its footprint
    fx, fy, fz = m["base"]["footprint_m"]
    top_part = profile["scale"]["top_part"]
    top_src = max(v.co.z for v in parts[top_part].data.vertices)
    s = (profile["scale"]["figure_height_m"] - fz) / (top_src - base_top_src)
    xform = (s, cx, cy, fz, base_top_src)

    def to_final(axis, value):
        """A source-frame coordinate on one axis in final metres (the seat transform)."""
        if axis == "x":
            return (value - cx) * s
        if axis == "y":
            return (value - cy) * s
        return fz + (value - base_top_src) * s

    def to_final_z(value):
        return to_final("z", value)

    coords_frame = profile["weights"].get("coordinates_frame", "final")
    coord_to_final = to_final if coords_frame == "source" else (lambda _axis, value: value)
    base = parts[base_src] if bmode == "normalise-part" else None
    base_linear = None
    if base is not None:
        base_linear = [[fx / (bhi[0] - blo[0]), 0, 0], [0, fy / (bhi[1] - blo[1]), 0], [0, 0, fz / (bhi[2] - blo[2])]]
    for name, obj in parts.items():
        if obj is base:
            for v in obj.data.vertices:
                v.co = Vector(((v.co.x - cx) * base_linear[0][0], (v.co.y - cy) * base_linear[1][1],
                               (v.co.z - base_bottom_src) * base_linear[2][2]))
        else:
            for v in obj.data.vertices:
                v.co = Vector(((v.co.x - cx) * s, (v.co.y - cy) * s, fz + (v.co.z - base_top_src) * s))
        obj.data.update()
    scale_info = {"source_base_part": base_src, "source_base_top": r(base_top_src), "source_base_bottom": r(base_bottom_src),
                  "source_base_centre_xy": [r(cx), r(cy)], "top_part": top_part, "source_top_of_top_part": r(top_src),
                  "figure_scale": r(s, 8), "figure_height_m": profile["scale"]["figure_height_m"],
                  "base_mode": bmode, "base_height_m": fz, "base_diameter_m": fx,
                  "tripo_base_diameter_at_figure_scale_m": r((bhi[0] - blo[0]) * s, 6)}
    if base_linear:
        scale_info["base_scale_xyz"] = [r(base_linear[i][i], 8) for i in range(3)]

    # ---- atlas UVs + material
    files = {k: v["file"] for k, v in atlas["files"].items()}
    mat, mat_images = atlas_material(params["textures_dir"], files, profile["materials"]["atlas"])
    for name, obj in parts.items():
        remap_uvs(obj, cells[name], size)
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        obj.data.update()

    # ---- weld inside every part; label faces with their part
    weld = {n: weld_part(o, profile["weld"]["distance_m"]) for n, o in sorted(parts.items())}
    for name, obj in parts.items():
        label_faces(obj, name)
    bc_px = bc_size = n_px = None
    if wmode == "split-from-part" or closure_cfg.get("base_top"):
        bc_px, bc_size = material_pixels(mat, "BC")

    # ---- closure: base top footprint holes, open soles, fan caps of listed open loops
    caps_info = {}
    if closure_cfg.get("base_top"):
        if base is None:
            raise RuntimeError("closure.base_top needs meshes.base.mode normalise-part")
        n_px = material_pixels(mat, "N_OpenGL")[0]
        caps_info["base_top"] = cap_base_top(base, fz, base_linear, closure_cfg["base_top"], bc_px, n_px,
                                             cells[base_src], size)
    if closure_cfg.get("soles"):
        caps_info["soles"] = {p: cap_soles(parts[p], closure_cfg["soles"]) for p in closure_cfg["soles"]["parts"]}
    open_caps = {}
    for name, ccfg in sorted((profile.get("open_loop_caps") or {}).items()):
        open_caps[name] = cap_loops_component(parts[name], part_number(name), ccfg, xform)
    if open_caps:
        caps_info["open_loops"] = open_caps

    # ---- weapon
    weapon, weapon_info, weapon_labels, axis_c, axis_d = None, None, {}, None, None
    wsrc = None
    if wmode == "split-from-part":
        wcfg = profile["weapon_split"]
        wsrc = wmesh["split_from"]
        _hand, weapon, weapon_info, (axis_c, axis_d) = split_weapon(scene, parts[wsrc], wcfg, bc_px, bc_size)
        weapon.name = wmesh["object"]
        weapon.data.name = wmesh["mesh"]
        weapon_info["grip_bridge"] = grip_bridge_fitted(weapon, wcfg["grip_bridge"], axis_c, axis_d) \
            if wcfg.get("grip_bridge") else None
        weapon_info["islands_final"] = islands(weapon.data)[1]
        label_faces(weapon, wsrc)
    elif wmode == "parts":
        acfg = profile["weapon_assembly"]
        wparts = wmesh["parts"]
        staff_objs = [parts.pop(n) for n in wparts]
        weapon = join_objects(scene, staff_objs, staff_objs[0])
        weapon.name = wmesh["object"]
        weapon.data.name = wmesh["mesh"]
        labels = read_face_labels(weapon)
        gcfg = acfg["grip_bridge"]
        axis_c, axis_d, shaft_r, axis_info = staff_axis(weapon, labels, gcfg["axis_rings_source_z"], to_final_z)
        bridge = grip_bridge_axis(weapon, labels, gcfg, axis_c, axis_d, shaft_r, to_final_z)
        labels = read_face_labels(weapon)
        wcaps = cap_loops_chain(weapon, labels, acfg["caps"], to_final_z) if acfg.get("caps") else []
        labels = read_face_labels(weapon)
        weapon_info = {"parts": wparts, "axis": axis_info, "grip_bridge": bridge, "caps": wcaps,
                       "islands_final": islands(weapon.data)[1],
                       "part_polygons": {p: len(v) for p, v in sorted(labels.items())}}
    elif wmode == "part":
        wsrc = wmesh["part"]
        weapon = parts.pop(wsrc)
        weapon.name = wmesh["object"]
        weapon.data.name = wmesh["mesh"]
        weapon_info = {"part": wsrc}

    def weapon_label_map(obj):
        if wmode == "parts":
            return {"weapon:" + p: list(ix) for p, ix in sorted(read_face_labels(obj).items())}
        return {"weapon:" + wsrc: [p.index for p in obj.data.polygons]}

    # ---- corner normals back (figure: uniform scale = rotation-free, base: inverse-transpose of its scale)
    items = sorted(parts.items()) + ([("weapon", weapon)] if weapon else [])
    normals_after, normals_preserved = {}, {}
    for name, obj in items:
        normals_after[name] = apply_corner_normals(obj, base_linear if obj is base else None)
    for name, obj in items:
        mn, bad, zero = corner_normal_agreement(obj, normals_after[name])
        normals_preserved[name] = {"min_dot": r(mn, 5), "corners_below_0_999": bad,
                                   "zero_captured_corners_excluded": zero}
    for _name, obj in items:
        obj.data.attributes.remove(obj.data.attributes[CN_ATTR])

    # ---- parametric base
    base_info, bcfg = None, profile.get("base_parametric")
    if bmode == "parametric":
        base, base_info = build_parametric_base(scene, bcfg, bcfg["mask"], m["base"]["object"], m["base"]["mesh"])
        base.data.materials.append(base_material(bcfg))
        base["um_instance_index"] = float(bcfg.get("preview_instance_index", 3.0))
        base["um_team_color"] = tuple(bcfg["preview_colours_linear"][bcfg.get("preview_team", "team_gold")]) + (1.0,)

    # ---- orientation: (1) per-face reference fix, (2) whole-part ray-escape fix
    labelled = [(o, {n: [p.index for p in o.data.polygons]}) for n, o in sorted(parts.items())]
    if weapon:
        weapon_labels = weapon_label_map(weapon)
        labelled.append((weapon, weapon_labels))
    if bmode == "parametric":
        labelled.append((base, {"base": [p.index for p in base.data.polygons]}))
    orient_before_ref = None
    if rcfg:
        orient_before_ref = orientation_scores(labelled)
        for name in rcfg["parts"]:
            mesh = parts[name].data
            vals = [0.0] * len(mesh.polygons)
            mesh.attributes[REF_FLIP_ATTR].data.foreach_get("value", vals)
            ref_votes[name]["winding_after_weld_before_fix"] = inconsistent_winding_edges(mesh)
            flip, smooth = smooth_orientation(mesh, vals, rcfg["smoothing_lambda"], rcfg["smoothing_max_sweeps"])
            flip_polygons(mesh, flip)
            ref_votes[name]["smoothing"] = smooth
            ref_votes[name]["winding_after_fix"] = inconsistent_winding_edges(mesh)
            mesh.attributes.remove(mesh.attributes[REF_FLIP_ATTR])
    orient_before = orientation_scores(labelled)
    inside_out = sorted(p for p, sc in orient_before.items()
                        if sc["score"] is not None and sc["score"] < ocfg["flip_below_score"])
    check("orientation_inside_out_parts_as_profile", inside_out == sorted(ocfg["expected_inside_out_parts"]),
          inside_out, sorted(ocfg["expected_inside_out_parts"]),
          "ray-escape score < %s%s" % (ocfg["flip_below_score"],
                                       " after the per-face reference fix" if rcfg else " on the Tripo geometry"))
    for name in inside_out:
        if name.startswith("weapon:"):
            flip_polygons(weapon.data, set(weapon_labels[name]))
        elif name == "base":
            flip_polygons(base.data, {p.index for p in base.data.polygons})
        else:
            flip_polygons(parts[name].data, {p.index for p in parts[name].data.polygons})
    orient_after = orientation_scores(labelled)
    bad_after = sorted(p for p, sc in orient_after.items() if sc["score"] is None or sc["score"] < ocfg["min_score_after_fix"])
    check("orientation_all_parts_outward_after_fix", not bad_after,
          {p: sc["score"] for p, sc in sorted(orient_after.items())}, ">= %s" % ocfg["min_score_after_fix"])
    if rcfg:
        first = ref_votes[rcfg["parts"][0]]
        check("orientation_reference_vote_fixed_mixed_winding",
              all(v["winding_after_fix"]["inconsistent"] <= rcfg["max_inconsistent_after"]
                  and v["winding_after_fix"]["inconsistent"] < v["winding_after_weld_before_fix"]["inconsistent"]
                  and v["unmatched_faces"] == 0 for v in ref_votes.values()) and bool(first),
              ref_votes, "inconsistent winding edges <= %s after the fix, every face finds reference triangles"
              % rcfg["max_inconsistent_after"],
              "faces of the mixed-winding part voted against the Tripo high-poly, then smoothed (ICM) toward "
              "consistent winding")
    opposed = {n: opposed_corner_fraction(o, ix) for n, o, ix in labelled_objects(labelled)}
    check("corner_normals_agree_with_winding", all(v <= ocfg["corner_normal_opposed_max_fraction"] for v in opposed.values()),
          opposed, "<= %s area share per part" % ocfg["corner_normal_opposed_max_fraction"],
          "area share of polygons whose mean custom corner normal points against the polygon normal")
    check("corner_normals_preserved", all(v["min_dot"] > 0.999 for v in normals_preserved.values()),
          normals_preserved, "min dot > 0.999 against the captured import normals"
          + (" (base: inverse-transpose of its scale)" if base_linear else ""))

    # ---- armature and weights
    arm, bones_final = make_armature(scene, profile, xform)
    bone_names = [b[0] for b in profile["armature"]["bones"]]
    wcfg_all = profile["weights"]
    rules = {}
    for rule in wcfg_all["groups"]:
        for part in rule["parts"]:
            rules[part] = rule
    body_part_names = sorted(n for n in parts if not (bmode == "normalise-part" and n == base_src))
    missing_rules = sorted(set(body_part_names) - set(rules))
    if missing_rules:
        raise RuntimeError("no weight rule for parts %s" % missing_rules)
    wing_info = {}
    for rule in wcfg_all["groups"]:
        objs = [parts[p] for p in rule["parts"] if p in parts]
        if "rigid" in rule:
            for obj in objs:
                rigid_weights(arm, obj, rule["rigid"])
        elif "wing_span" in rule:
            for p in rule["parts"]:
                wing_info[p] = wing_span_weights(arm, parts[p], rule["wing_span"], s)
        elif "axis_blend" in rule:
            for obj in objs:
                axis_blend_weights(arm, obj, rule["axis_blend"], coord_to_final)
        else:
            heat_weights(scene, arm, objs, set(rule["heat"]))
    if weapon:
        rigid_weights(arm, weapon, wmesh["bone"])
    heat_stats = {}
    for name in body_part_names:
        rule = rules[name]
        heat_stats[name] = cleanup_weights(arm, parts[name], group_allowed_bones(rule), rule,
                                           profile["armature"]["max_influences"], wcfg_all["clean_below"],
                                           coord_to_final)
    per_part_weights = {n: weight_summary(parts[n], bone_names) for n in body_part_names}

    # ---- join body (labels re-set on every body part: cap faces added by bmesh carry the layer default)
    for name in body_part_names:
        label_faces(parts[name], name)
    body = join_objects(scene, [parts[n] for n in body_part_names], parts[m["body"]["active_part"]])
    body.name = m["body"]["object"]
    body.data.name = m["body"]["mesh"]
    if bmode == "normalise-part":
        base.name = m["base"]["object"]
        base.data.name = m["base"]["mesh"]
    for mod in [md for md in body.modifiers if md.type == "ARMATURE"][1:]:
        body.modifiers.remove(mod)
    body_parts = read_face_labels(body)
    part_of_poly = {i: p for p, ix in body_parts.items() for i in ix}
    weapon_parts = read_face_labels(weapon) if weapon else {}
    for obj in (body, weapon, base):
        if obj is not None:
            remove_attribute(obj, PART_ATTR)
    uv_parts, unassigned = polygons_by_part(body.data, rects)
    uv_matches_parts = all(sorted(uv_parts.get(p, [])) == sorted(ix) for p, ix in body_parts.items())
    unassigned_weapon, uv_weapon_matches = 0, True
    if weapon:
        uv_weapon, unassigned_weapon = polygons_by_part(weapon.data, rects)
        uv_weapon_matches = all(sorted(uv_weapon.get(p, [])) == sorted(ix) for p, ix in weapon_parts.items())

    # ---- measurements (authored frame, metres)
    skel = [body] + ([weapon] if weapon else [])
    pre = {m["body"]["object"]: mesh_summary(body)}
    if weapon:
        pre[wmesh["object"]] = mesh_summary(weapon)
    pre[m["base"]["object"]] = mesh_summary(base)
    weights = {"body": weight_summary(body, bone_names)}
    if weapon:
        weights["weapon"] = weight_summary(weapon, bone_names)
    labelled_final = [(body, body_parts)]
    if weapon:
        labelled_final.append((weapon, {"weapon:" + p: ix for p, ix in sorted(weapon_parts.items())}))
    if bmode == "normalise-part":
        labelled_final.append((base, {base_src: [p.index for p in base.data.polygons]}))
    uv_stats = uv_statistics(labelled_final, cells, size, 100.0)
    lo_sk, hi_sk = world_bounds(skel)
    lo_body, hi_body = world_bounds([body])
    lo_base, hi_base = world_bounds([base])
    lo_all, hi_all = world_bounds(skel + [base])
    anat = anatomy_mod.resolve(anat_cfg, summaries_of(body, body_parts), top_part,
                               list(arm.data.bones[wmesh["bone"]].head_local) if weapon else None)
    used = anat["used"]
    head_pts = part_points(body, body_parts[top_part])
    head_top = max(p.z for p in head_pts)
    feet = used["feet"] or {}
    if sorted(feet) != ["L", "R"] or not all(p in body_parts for p in feet.values()):
        raise RuntimeError("anatomy: feet L/R not resolved from the profile or the geometry: %s" % feet)
    feet_low = min(p.z for part in feet.values() for p in part_points(body, body_parts[part]))
    front_cfg = anat_cfg.get("front") or {}
    toes_cfg = front_cfg.get("feet") or {"method": "low_band", "band_m": 0.012, "toe_ahead_of_ankle_m": 0.02,
                                         "heel_behind_ankle_max_m": 0.03}
    ankle_bones = anat_cfg.get("ankle_bones") or {"L": "foot.L", "R": "foot.R"}
    toe_ankle, foot_tips = {}, {}
    for side, part in sorted(feet.items()):
        pts = part_points(body, body_parts[part])
        ankle = arm.data.bones[ankle_bones[side]].head_local
        if toes_cfg["method"] == "front_quartile":
            ys = sorted(p.y for p in pts)
            cut = ys[max(0, len(ys) // 4 - 1)]
            front = [p for p in pts if p.y <= cut]
            tip = sum(front, Vector()) / len(front)
            foot_tips[side] = tip
            toe_ankle[side] = {"part": part, "tips_centre_m": rv(tip, 5), "ankle_y": r(ankle.y, 5),
                               "tips_minus_ankle_y": r(tip.y - ankle.y, 5)}
        else:
            low = [p for p in pts if p.z < fz + toes_cfg["band_m"]]
            toe_y = min(p.y for p in low)
            heel_y = max(p.y for p in low)
            foot_tips[side] = min(low, key=lambda p: (p.y, p.x, p.z)).copy()
            toe_ankle[side] = {"part": part, "toe_y": r(toe_y, 5), "heel_y": r(heel_y, 5), "ankle_y": r(ankle.y, 5),
                               "toe_minus_ankle": r(toe_y - ankle.y, 5), "heel_minus_ankle": r(heel_y - ankle.y, 5)}
    body_c = centroid(body)
    weapon_c = centroid(weapon) if weapon else None

    def indicator_centroid(what, obj=None, labels=None):
        obj, labels = obj or body, labels if labels is not None else body_parts
        if what == "weapon":
            return centroid(weapon)
        if what == "body":
            return centroid(body)
        part = what.split(":", 1)[1]
        return centroid(obj, labels[part])

    radial = max(math.hypot(v.co.x, v.co.y) for o in skel for v in o.data.vertices)
    radial_body = max(math.hypot(v.co.x, v.co.y) for v in body.data.vertices)
    core_excluded = set(anat_cfg.get("capsule_exclude_parts") or [])
    core_vids = sorted({v for p, ix in body_parts.items() if p not in core_excluded for i in ix
                        for v in body.data.polygons[i].vertices})
    radial_core = max(math.hypot(body.data.vertices[v].co.x, body.data.vertices[v].co.y) for v in core_vids)
    span = hi_body[0] - lo_body[0]
    feet_radial = max(math.hypot(c.x, c.y) for part in feet.values() for c in part_points(body, body_parts[part]))
    weapon_measure = None
    if weapon:
        wb = arm.data.bones[wmesh["bone"]]
        weapon_top = max((weapon.matrix_world @ v.co for v in weapon.data.vertices), key=lambda p: p.z)
        tip_err = (wb.tail_local - weapon_top).length
        head_axis_err = dist_to_line(wb.head_local, axis_c, axis_d) if axis_c is not None else None
        hand_part = used["weapon_hand"]
        hand_pts = part_points(body, body_parts[hand_part]) if hand_part in body_parts else []
        hand_lo = [min(p[i] for p in hand_pts) for i in range(3)] if hand_pts else None
        hand_hi = [max(p[i] for p in hand_pts) for i in range(3)] if hand_pts else None
        head_in_fist = bool(hand_pts) and all(hand_lo[i] <= wb.head_local[i] <= hand_hi[i] for i in range(3))
        weapon_measure = {"tail_to_weapon_top_m": r(tip_err, 5),
                          "head_to_fitted_axis_m": r(head_axis_err, 5) if head_axis_err is not None else None,
                          "head_inside_hand_bounds": head_in_fist, "hand_part": hand_part,
                          "weapon_top_m": rv(weapon_top, 5),
                          "hand_bounds_m": {"min": rv(hand_lo, 5), "max": rv(hand_hi, 5)} if hand_pts else None}
    bone_heads = {b.name: rv(b.head_local, 5) for b in arm.data.bones}

    # ---- sockets: target in Blender, offset in Blender bone space and predicted UE bone space
    sockets = []
    for sock in profile["sockets"]:
        bone = arm.data.bones[sock["bone"]]
        tcfg = sock.get("target") or {}
        kind = tcfg.get("kind") or ("part_bbox_centre" if sock["name"] == "Head" else "bone_head")
        if kind == "bone_head":
            target = bone.head_local.copy()
        elif kind == "part_bbox_centre":
            part = tcfg.get("part") or used["head"]
            target = bbox_centre(part_points(body, body_parts[part]))
        elif kind == "foot_tip":
            target = foot_tips[tcfg["side"]].copy()
        else:
            raise RuntimeError("socket %s: unknown target kind %r" % (sock["name"], kind))
        local = bone.matrix_local.inverted() @ target
        local_uu = [c * 100 for c in local]
        ue_local = ue_bone_local_from_blender_uu(local_uu)
        explicit = sock.get("location_uu")
        entry = {"name": sock["name"], "bone": sock["bone"], "target_kind": kind, "target_blender_m": rv(target, 5),
                 "target_ue_component_uu": ue_from_blender_m(target),
                 "offset_blender_bone_local_uu": [r(c, 3) + 0.0 for c in local_uu],
                 "offset_ue_bone_local_uu_predicted": ue_local,
                 "bone_head_ue_component_uu": ue_from_blender_m(bone.head_local),
                 "location_uu_for_ue": list(explicit) if isinstance(explicit, list) else ue_local,
                 "location_source": "profile location_uu" if isinstance(explicit, list) else
                 "predicted from the Blender bone-local target (UE bone space = (x, -y, z)); verify with a live "
                 "get_socket_location against target_ue_component_uu",
                 "status": sock.get("status", "предложено")}
        if sock.get("tip_proposal"):
            tip_part = sock["tip_proposal"]["part"]
            src_obj, src_labels = (weapon, weapon_parts) if tip_part in weapon_parts else (body, body_parts)
            tip_centre = bbox_centre(part_points(src_obj, src_labels[tip_part]))
            tip_local = bone.matrix_local.inverted() @ tip_centre
            entry["tip_proposal"] = {"part": tip_part, "centre_blender_m": rv(tip_centre, 5),
                                     "offset_blender_bone_local_uu": [r(c * 100, 3) for c in tip_local],
                                     "offset_ue_bone_local_uu_predicted":
                                         ue_bone_local_from_blender_uu([c * 100 for c in tip_local]),
                                     "status": sock["tip_proposal"].get("status", "предложено")}
        sockets.append(entry)
    root = arm.data.bones[bone_names[0]]
    pivot = {"root_bone": root.name, "root_head_m": [r(c, 6) for c in root.head_local],
             "armature_object_location": [r(c, 6) for c in arm.location]}
    cross_part = cross_part_coincident(body, part_of_poly)
    closure = None
    if closure_cfg:
        weld_diag = closure_cfg["diagnostic_weld_m"]
        closure = {"base_boundary_edges": boundary_edge_count(base, weld_diag)[0],
                   "base_non_manifold_edges": boundary_edge_count(base, weld_diag)[1],
                   "body_boundary_edges_total_info": boundary_edge_count(body, weld_diag)[0]}
        if closure_cfg.get("soles"):
            closure["body_boundary_edges_below_z_max"] = boundary_edge_count(body, weld_diag,
                                                                             closure_cfg["soles"]["z_max_m"])[0]
        if closure_cfg.get("see_through"):
            closure["see_through_base_only"] = see_through_rays([base], fz, closure_cfg["see_through"])
            closure["see_through_rest_figure"] = see_through_rays([base] + skel, fz, closure_cfg["see_through"])
    base_mask = pip_clearance = None
    if bmode == "parametric":
        base_mask = mask_census(base, bcfg["mask"]["attribute"])
        clear_cfg = bcfg["pips"].get("clearance") or {"band_m": 0.015, "min_m": 0.001}
        low_xy = [(v.co.x, v.co.y) for v in body.data.vertices if v.co.z < fz + clear_cfg["band_m"]]
        pip_clearance = []
        for pip in base_info["pips"]:
            d = min(math.hypot(x - pip["centre_m"][0], y - pip["centre_m"][1]) for x, y in low_xy)
            pip_clearance.append(r(d - bcfg["pips"]["pip_radius_m"], 5))
    weapon_bone = profile["armature"].get("weapon_bone", "weapon")
    unweighted_weapon_bone = None
    if not weapon and weapon_bone in arm.data.bones:
        # read now: Bone references die at the export's edit mode
        unweighted_weapon_bone = {"present": True, "weighted": weapon_bone in weights["body"]["bones_used"],
                                  "parent": arm.data.bones[weapon_bone].parent.name
                                  if arm.data.bones[weapon_bone].parent else None,
                                  "expected_parent": next((b[1] for b in profile["armature"]["bones"]
                                                           if b[0] == weapon_bone), None)}
    tail = None
    tail_cfg = anat_cfg.get("tail")
    if tail_cfg:
        tail_y = to_final("y", tail_cfg["behind_source_y"])
        tail_vids = sorted({v for i in body_parts[tail_cfg["part"]] for v in body.data.polygons[i].vertices
                            if body.data.vertices[v].co.y > tail_y})
        forbidden = {g.index for g in body.vertex_groups if g.name.startswith(tail_cfg["forbidden_bone_prefix"])}
        tail_bad = sum(1 for v in tail_vids if any(g.group in forbidden and g.weight > 0
                                                   for g in body.data.vertices[v].groups))
        tail = {"part": tail_cfg["part"], "vertices_behind_source_y": len(tail_vids),
                "behind_source_y": tail_cfg["behind_source_y"], "with_forbidden_weight": tail_bad,
                "forbidden_bone_prefix": tail_cfg["forbidden_bone_prefix"]}
    side_values = {}
    for ind in anat_cfg.get("side_indicators") or []:
        side_values[ind["what"]] = indicator_centroid(ind["what"])
    front_parts = {p: indicator_centroid("part:" + p) for p in sorted((front_cfg.get("parts_ahead_of_body_m") or {}))}

    blend_out = Path(params["blend_out"])
    blend_out.parent.mkdir(parents=True, exist_ok=True)
    bpy.data.libraries.write(str(blend_out), {scene}, compress=False)

    # ---- export (UM_FBX_v1) on the in-memory copy; the work .blend stays authored
    transform_for_fbx(scene, arm, tuple(skel) + (base,), Matrix.Scale(ctx.data_scale, 4) @ ctx.rot)
    sk_fbx, base_fbx = Path(params["sk_fbx_out"]), Path(params["base_fbx_out"])
    ctx.note_export_names()
    export_pair(scene, arm, skel, base, preset, sk_fbx, base_fbx)

    # ---- round trip
    rt = bpy.data.scenes.new(ROUNDTRIP_SCENE)
    import_fbx_into(rt, sk_fbx)
    rtb = bpy.data.scenes.new(ROUNDTRIP_SCENE + "_base")
    import_fbx_into(rtb, base_fbx)
    raw = {re.sub(r"\.\d{3}$", "", o.name): o for sc in (rt, rtb) for o in sc.objects if o.type == "MESH"}
    wanted = [m["body"]["object"], m["base"]["object"]] + ([wmesh["object"]] if weapon else [])
    if any(name not in raw for name in wanted):
        raise RuntimeError("round trip lost meshes: %s" % sorted(raw))
    rb_export = raw[m["body"]["object"]]
    rb_parts_export, _ = polygons_by_part(rb_export.data, rects)
    raw_skel = [rb_export] + ([raw[wmesh["object"]]] if weapon else [])
    lo_x, hi_x = world_bounds(raw_skel)
    lo_xb, hi_xb = world_bounds([raw[m["base"]["object"]]])
    export_frame = {"body_centroid_m": centroid(rb_export),
                    "skeletal_bounds_cm": {"min": [r(c * 100, 3) for c in lo_x], "max": [r(c * 100, 3) for c in hi_x]},
                    "base_bounds_cm": {"min": [r(c * 100, 3) for c in lo_xb], "max": [r(c * 100, 3) for c in hi_xb]}}
    if weapon:
        export_frame["weapon_centroid_m"] = centroid(raw[wmesh["object"]])
    export_inds = anat_cfg.get("export_frame_indicators") or []
    for ind in export_inds:
        if ind["what"] != "weapon":
            export_frame.setdefault("centroids_m", {})[ind["what"]] = centroid(rb_export,
                                                                               rb_parts_export[ind["what"].split(":", 1)[1]])
    inverse = ctx.rot.inverted()
    to_authored_frame(rt, inverse)
    to_authored_frame(rtb, inverse)
    rt_sk, rt_sk_meshes = roundtrip_measure(rt, bone_names)
    rt_base, rt_base_meshes = roundtrip_measure(rtb, bone_names)
    rt_body, rt_base_obj = rt_sk_meshes[m["body"]["object"]], rt_base_meshes[m["base"]["object"]]
    rt_weapon = rt_sk_meshes[wmesh["object"]] if weapon else None
    rt_parts, rt_unassigned = polygons_by_part(rt_body.data, rects)
    rt_labelled = [(rt_body, rt_parts)]
    rt_weapon_parts, rt_unassigned_weapon = {}, 0
    if weapon:
        rt_weapon_parts, rt_unassigned_weapon = polygons_by_part(rt_weapon.data, rects)
        if wmode == "parts":
            rt_labelled.append((rt_weapon, {"weapon:" + p: ix for p, ix in sorted(rt_weapon_parts.items())}))
        else:
            rt_labelled.append((rt_weapon, {"weapon:" + wsrc: [p.index for p in rt_weapon.data.polygons]}))
    rt_labelled.append((rt_base_obj, {(base_src if bmode == "normalise-part" else "base"):
                                      [p.index for p in rt_base_obj.data.polygons]}))
    orient_rt = orientation_scores(rt_labelled)
    rt_lo_sk, rt_hi_sk = world_bounds([rt_body] + ([rt_weapon] if weapon else []))
    rt_mask = mask_census(rt_base_obj, bcfg["mask"]["attribute"]) if bmode == "parametric" else None
    if closure is not None:
        closure["roundtrip"] = {"base_boundary_edges": boundary_edge_count(rt_base_obj, closure_cfg["diagnostic_weld_m"])[0]}
        if closure_cfg.get("soles"):
            closure["roundtrip"]["body_boundary_edges_below_z_max"] = boundary_edge_count(
                rt_body, closure_cfg["diagnostic_weld_m"], closure_cfg["soles"]["z_max_m"])[0]
        if closure_cfg.get("see_through"):
            closure["roundtrip"]["see_through_base_only"] = see_through_rays(
                [rt_base_obj], fz, closure_cfg["see_through"])["missed_total"]

    # ---------------------------------------------------------------- checks
    exp = profile["expectations"]
    tris = {n: pre[n]["triangles"] for n in pre}
    if all(v is not None for v in exp["triangles"].values()):
        check("triangles_as_profile", tris == exp["triangles"], tris, exp["triangles"])
    else:
        check("triangles_as_profile", True, tris, exp["triangles"], "profile expectations not fixed yet: measured only")
    check("dropped_parts_as_profile", sorted(dropped) == sorted(m.get("drop_parts") or {}), dropped)
    check("weld_inside_parts_measured", True, weld,
          note="bmesh remove_doubles at %s m inside each part; islands_after per part" % profile["weld"]["distance_m"])
    if caps_info.get("open_loops") is not None or profile.get("open_loop_caps"):
        ol = profile.get("open_loop_caps") or {}
        check("caps_as_profile", all(len(open_caps.get(n, [])) == len(c["loops_source_centres"]) and
                                     all(cp["triangles"] == cp["loop_vertices"] and cp["max_angular_gap_deg"] < 90
                                         for cp in open_caps.get(n, []))
                                     for n, c in ol.items()),
              open_caps, {n: len(c["loops_source_centres"]) for n, c in ol.items()},
              "every listed open loop found and fan-filled all round (star-shaped ring: largest angular gap < 90 deg)")
    if wmode == "split-from-part":
        wcfg = profile["weapon_split"]
        split_ok = (weapon_info["islands_after_split"]["sword"][:1] and
                    all(n >= wcfg["min_island_polygons"] for n in weapon_info["islands_after_split"]["sword"]) and
                    all(n >= wcfg["min_island_polygons"] for n in weapon_info["islands_after_split"]["hand"]))
        check("weapon_split_clean_islands", bool(split_ok), weapon_info["islands_after_split"],
              ">= %d polygons per island" % wcfg["min_island_polygons"])
        if wcfg.get("grip_bridge"):
            br = weapon_info["grip_bridge"] or {}
            check("weapon_grip_bridge_closes_gap", br.get("added") is True and br["to_t_m"] > br["from_t_m"]
                  and br["triangles"] == 2 * wcfg["grip_bridge"]["sides"],
                  br, "an open %d-sided cylinder overlapping both weapon islands by %s m"
                  % (wcfg["grip_bridge"]["sides"], wcfg["grip_bridge"]["overlap_m"]),
                  "Tripo modelled no grip inside the fist; the split weapon was two islands with a gap hidden by the fist")
    if wmode == "parts":
        acfg = profile["weapon_assembly"]
        check("weapon_parts_as_profile", sorted(weapon_parts) == sorted(wmesh["parts"]) and
              all(len(ix) > 0 for ix in weapon_parts.values()), {p: len(ix) for p, ix in sorted(weapon_parts.items())},
              sorted(wmesh["parts"]))
        gb = weapon_info["grip_bridge"]
        check("weapon_grip_bridge_closes_gap", gb.get("added") is True and gb["to_t_m"] > gb["from_t_m"]
              and gb["triangles"] == 2 * acfg["grip_bridge"]["sides"],
              gb, "an open %d-sided cylinder on the fitted shaft axis from source z %s to %s"
              % (acfg["grip_bridge"]["sides"], acfg["grip_bridge"]["from_source_z"], acfg["grip_bridge"]["to_source_z"]),
              "Tripo modelled no shaft inside the fist; the weapon was two shaft islands with a gap hidden by the fist")
        if acfg.get("caps"):
            wcaps = weapon_info["caps"]
            check("weapon_bottom_capped", len(wcaps) == acfg["caps"]["expected_loops"] and
                  all(c["triangles"] == c["loop_vertices"] for c in wcaps),
                  wcaps, "%d closed fan(s)" % acfg["caps"]["expected_loops"])
    if weapon:
        tol_w = profile["armature"]["weapon_axis_tolerance_m"]
        axis_ok = weapon_measure["head_to_fitted_axis_m"] is None or weapon_measure["head_to_fitted_axis_m"] <= tol_w
        check("weapon_bone_on_weapon", weapon_measure["tail_to_weapon_top_m"] <= tol_w and axis_ok
              and weapon_measure["head_inside_hand_bounds"], weapon_measure, "<= %s m" % tol_w,
              "bone tail at the highest weapon vertex, head on the fitted weapon axis inside the hand part's bounds")
    check("every_polygon_in_its_atlas_cell", unassigned == 0 and rt_unassigned == 0 and uv_matches_parts
          and unassigned_weapon == 0 and rt_unassigned_weapon == 0 and uv_weapon_matches,
          {"body_build": unassigned, "body_roundtrip": rt_unassigned, "body_uv_cells_equal_part_labels": uv_matches_parts,
           "weapon_build": unassigned_weapon, "weapon_roundtrip": rt_unassigned_weapon,
           "weapon_uv_cells_equal_part_labels": uv_weapon_matches})
    uv_outside = sum(sv["loops_outside_cell_inner_rect"] for sv in uv_stats.values())
    check("uv0_single_layer_on_every_mesh", all(pre[n]["uv_layers"] == ["UVMap"] for n in pre),
          {n: pre[n]["uv_layers"] for n in pre})
    check("uv0_inside_unit_square", all(pre[n]["uv0_in_unit_square"] for n in pre),
          {n: pre[n]["uv0_in_unit_square"] for n in pre})
    check("uv0_inside_own_atlas_cell", uv_outside == 0, uv_outside,
          note="every UV corner of an atlas mesh lies in its part's inner cell rect (gutter kept)")
    check("uv0_raster_overlap_measured", True, {p: sv["overlap_ratio"] for p, sv in sorted(uv_stats.items())},
          note="informational: texels covered by >= 2 triangles / covered texels, per part at atlas resolution")
    check("weights_every_vertex_weighted", all(w["unweighted_vertices"] == 0 for w in weights.values()),
          {k: w["unweighted_vertices"] for k, w in weights.items()})
    check("weights_normalised", all(w["not_normalised_vertices"] == 0 for w in weights.values()),
          {k: w["not_normalised_vertices"] for k, w in weights.items()})
    check("weights_max_influences", max(w["max_influences"] for w in weights.values())
          <= profile["armature"]["max_influences"],
          max(w["max_influences"] for w in weights.values()), profile["armature"]["max_influences"])
    allowed_ok = {n: sorted(set(per_part_weights[n]["bones_used"]) - group_allowed_bones(rules[n]))
                  for n in body_part_names}
    check("weights_only_group_bones", not any(allowed_ok.values()), allowed_ok,
          note="per part: bones outside the group's list (must be empty)")
    fallback = {n: st.get("fallback_nearest_bone", 0) for n, st in heat_stats.items()}
    check("weights_heat_fallback_measured", True, fallback,
          note="vertices the heat solve left unweighted, given 1.0 on the nearest allowed bone (informational)")
    if weapon:
        check("weapon_bound_only_to_weapon", list(weights["weapon"]["bones_used"]) == [wmesh["bone"]],
              weights["weapon"]["bones_used"])
    if wing_info:
        wing_ok = all(set(per_part_weights[p]["bones_used"]) >= set(rules[p]["wing_span"]["chain"]) for p in wing_info)
        check("weights_wings_on_arm_chain", wing_ok, {p: per_part_weights[p]["weight_share"] for p in sorted(wing_info)},
              "each wing uses arm_upper, arm_lower and hand of its side (rig-contract harpy_wings)")
    if tail:
        check("weights_tail_follows_hips", tail["vertices_behind_source_y"] > 0 and tail["with_forbidden_weight"] == 0,
              tail, "tail vertices of %s behind source y %s carry no %s* weight"
              % (tail["part"], tail["behind_source_y"], tail["forbidden_bone_prefix"]))
    if unweighted_weapon_bone:
        check("weapon_bone_kept_unweighted", not unweighted_weapon_bone["weighted"]
              and unweighted_weapon_bone["parent"] == unweighted_weapon_bone["expected_parent"],
              unweighted_weapon_bone,
              note="no weapon mesh (meshes.weapon null): the bone set stays complete (validate_clip.py), no vertex on it")
    fh = profile["scale"]["figure_height_m"]
    height = hi_all[2] - lo_all[2]
    check("height_m", abs(head_top - fh) < 1e-5 and abs(lo_all[2]) < 1e-6,
          {"figure_top_of_top_part": r(head_top, 6), "skeletal_top": r(hi_sk[2], 6), "lowest": r(lo_all[2], 6),
           "figure_with_base_and_weapon": r(height, 6)}, fh,
          "figure height = top of scale.top_part (%s) above the base bottom; a weapon or wing may reach higher" % top_part)
    sink = anat_cfg.get("feet_sink_m") or [-0.003, 0.003]
    check("feet_on_base_top", sink[0] <= feet_low - fz <= sink[1],
          {"lowest_foot_vertex_z": r(feet_low, 5), "base_top_z": fz, "offset_m": r(feet_low - fz, 5), "feet": feet},
          "lowest foot vertex within %s m of the base top (profile anatomy.feet_sink_m)" % sink)
    if closure_cfg.get("base_top"):
        bcap = caps_info["base_top"]
        ccfg_b = closure_cfg["base_top"]
        weld_diag = closure_cfg["diagnostic_weld_m"]
        check("base_top_closed", bcap["hole_boundary_edges_before"] > 0 and bcap["boundary_edges_after"] == 0
              and closure["base_boundary_edges"] == 0 and closure["roundtrip"]["base_boundary_edges"] == 0
              and all(c["cycle_against_winding_edges"] == c["cycle_edges"] for c in bcap["caps"])
              and all(c["cap_normal_z_before_triangulate"] > 0.9999 for c in bcap["caps"]),
              {"hole_loops_before": len(bcap["holes_before"]), "hole_boundary_edges_before": bcap["hole_boundary_edges_before"],
               "caps": len(bcap["caps"]), "boundary_edges_after_caps": bcap["boundary_edges_after"],
               "boundary_edges_welded_%g_m" % weld_diag: closure["base_boundary_edges"],
               "roundtrip_boundary_edges": closure["roundtrip"]["base_boundary_edges"],
               "non_manifold_edges_info": closure["base_non_manifold_edges"]}, 0,
              "Tripo footprint holes capped; caps wound with their neighbours")
        check("base_caps_flat_with_clean_stone_uvs", all(c["cap_triangles_normal_z_min"] >= 0.9999 and
                                                         c["fold_triangles"] == 0 and
                                                         abs(c["cap_triangles_z_range_m"][0] - fz) < 1e-6 and
                                                         abs(c["cap_triangles_z_range_m"][1] - fz) < 1e-6 and
                                                         c["wall_triangles_normal_z_abs_max"] < 0.5
                                                         for c in bcap["caps"])
              and bcap["affine_max_residual_px"] <= ccfg_b["affine_max_residual_px"]
              and all(c["donor_shift_px"] is not None for c in bcap["caps"]),
              {"cap_normal_z_min": min(c["cap_triangles_normal_z_min"] for c in bcap["caps"]),
               "fold_triangles": sum(c["fold_triangles"] for c in bcap["caps"]),
               "fold_repairs": len(bcap["fold_repairs"]),
               "cap_triangles": [c["triangles"] for c in bcap["caps"]],
               "crack_end_walls": sum(c["walls"] for c in bcap["caps"]),
               "uv_scale": [c["uv_scale"] for c in bcap["caps"]],
               "affine_residual_px": bcap["affine_max_residual_px"],
               "donor_shift_px": [c["donor_shift_px"] for c in bcap["caps"]],
               "removed_flat_faces": bcap["removed_flat_faces"], "removed_area_cm2": bcap["removed_area_cm2"],
               "removed_hole_wall_faces": sum(w["faces"] for w in bcap["removed_hole_walls"])},
              note="caps flat at the base top; UVs = the top's planar map shifted onto clean stone texels "
                   "(dark hole texels and the baked fringe are no longer used within %s m of a hole)"
                   % ccfg_b["region_max_distance_from_hole_m"])
    if closure_cfg.get("soles"):
        sole = caps_info["soles"]
        check("body_soles_closed", all(v["low_boundary_edges_after"] == 0 and v["caps"] for v in sole.values())
              and closure["body_boundary_edges_below_z_max"] == 0
              and closure["roundtrip"]["body_boundary_edges_below_z_max"] == 0
              and all(c["triangles_normal_z_max"] < 0 and c["against_winding_edges"] == c["loop_edges"]
                      for v in sole.values() for c in v["caps"]),
              {p: {"caps": len(v["caps"]), "loop_edges": [c["loop_edges"] for c in v["caps"]],
                   "normal_z_max": max(c["triangles_normal_z_max"] for c in v["caps"])} for p, v in sorted(sole.items())},
              0, "boundary edges of the body below z %s m (welded %g m), build and round trip"
              % (closure_cfg["soles"]["z_max_m"], closure_cfg["diagnostic_weld_m"]))
    if closure_cfg.get("see_through"):
        st_base, st_fig = closure["see_through_base_only"], closure["see_through_rest_figure"]
        st_cfg = closure_cfg["see_through"]
        check("base_no_see_through_backface_culled", st_base["missed_total"] == 0 and st_fig["missed_total"] == 0
              and closure["roundtrip"]["see_through_base_only"] == 0,
              {"base_only": st_base["missed_total"], "rest_figure": st_fig["missed_total"],
               "roundtrip_base_only": closure["roundtrip"]["see_through_base_only"],
               "raw_base_only_edge_slips": st_base["raw_missed_total"], "raw_rest_figure_edge_slips": st_fig["raw_missed_total"],
               "rays_per_view": st_base["samples_per_view"], "views": len(st_base["missed_by_view"])}, 0,
              "orthographic rays through the base top disc (r <= %s m, step %s m) from the top and pitch %s deg "
              "every %s deg of yaw; back faces skipped as by a one-sided material; a miss counts if 2 of 4 rays "
              "jittered by %s m also miss (grid points exactly on a shared edge slip through the BVH test)" %
              (st_cfg["disc_radius_m"], st_cfg["grid_step_m"], st_cfg["pitches_deg"], st_cfg["yaw_step_deg"],
               st_cfg["jitter_m"]))
    base_dims = [r(hi_base[i] - lo_base[i], 6) for i in range(3)]
    if bmode == "parametric":
        want_z = bcfg["height_m"] + bcfg["pips"]["raise_m"]
        check("base_footprint_and_pivot", all(abs(a - b) < 1e-6 for a, b in zip(base_dims[:2], (fx, fy)))
              and abs(base_dims[2] - r(want_z, 6)) < 1e-6
              and all(abs(lo_base[i] + hi_base[i]) < 1e-6 for i in range(2)) and abs(lo_base[2]) < 1e-6,
              {"dimensions_m": base_dims, "centre_xy_m": [r((lo_base[i] + hi_base[i]) / 2, 6) for i in range(2)],
               "bottom_z_m": r(lo_base[2], 6)},
              {"dimensions_m": [fx, fy, "%s + pip raise %s" % (fz, bcfg["pips"]["raise_m"])], "centre_xy_m": [0, 0],
               "bottom_z_m": 0})
        n_pips = len(bcfg["pips"]["sector_azimuths_deg"]) * len(bcfg["pips"]["slots_per_sector"])
        clear_min = (bcfg["pips"].get("clearance") or {}).get("min_m", 0.001)
        check("base_pips_clear_of_feet", len(base_info["pips"]) == n_pips and min(pip_clearance) > clear_min,
              {"pips": len(base_info["pips"]), "feet_max_radius_m": r(feet_radial, 5),
               "per_pip_xy_clearance_m": pip_clearance, "min_m": min(pip_clearance)},
              "%d pips; every pip edge > %s m (XY) from any body vertex close to the base top" % (n_pips, clear_min))
        check("base_mask_binary_and_complete", bool(base_mask) and base_mask["binary"]
              and set(base_mask["rgb_counts"]) == {"000", "100", "010", "001"},
              base_mask, note="mask corners: 000 top/bottom, 100 team band, 010 centre pips, 001 outer pips")
    else:
        check("base_footprint_and_pivot", all(abs(a - b) < 1e-6 for a, b in zip(base_dims, (fx, fy, fz)))
              and all(abs(lo_base[i] + hi_base[i]) < 1e-6 for i in range(2)) and abs(lo_base[2]) < 1e-6,
              {"dimensions_m": base_dims, "centre_xy_m": [r((lo_base[i] + hi_base[i]) / 2, 6) for i in range(2)],
               "bottom_z_m": r(lo_base[2], 6)}, {"dimensions_m": [fx, fy, fz], "centre_xy_m": [0, 0], "bottom_z_m": 0})
    check("pivot_root_at_origin", pivot["root_head_m"] == [0.0, 0.0, 0.0] and
          pivot["armature_object_location"] == [0.0, 0.0, 0.0], pivot)
    check("armature_object_name_contract", arm.name == profile["armature"]["object"], arm.name,
          profile["armature"]["object"])
    # front (authored -Y): feet, weapon, parts ahead of the body
    front_ok, front_measured = True, {"feet": toe_ankle, "body_centroid_m": body_c}
    if toes_cfg["method"] == "front_quartile":
        front_ok = all(t["tips_minus_ankle_y"] < -toes_cfg["tip_ahead_of_ankle_m"] for t in toe_ankle.values())
    else:
        front_ok = all(t["toe_minus_ankle"] < -toes_cfg["toe_ahead_of_ankle_m"]
                       and t["heel_minus_ankle"] < toes_cfg["heel_behind_ankle_max_m"] + 1e-9 for t in toe_ankle.values())
    if front_cfg.get("weapon_centroid_y_max_m") is not None and weapon:
        front_ok = front_ok and weapon_c[1] < front_cfg["weapon_centroid_y_max_m"]
        front_measured["weapon_centroid_m"] = weapon_c
    for p, gap in sorted((front_cfg.get("parts_ahead_of_body_m") or {}).items()):
        front_ok = front_ok and front_parts[p][1] - body_c[1] < -gap
        front_measured.setdefault("part_centroids_m", {})[p] = front_parts[p]
    check("axes_front_minus_y", front_ok, front_measured, front_cfg or toes_cfg,
          "profile anatomy.front: toes/tips ahead of the ankles (-Y), listed parts and the weapon ahead of the body")
    side_ok, side_measured = True, {}
    for ind in anat_cfg.get("side_indicators") or []:
        x = side_values[ind["what"]][0]
        side_measured[ind["what"]] = side_values[ind["what"]]
        side_ok = side_ok and ind["sign"] * x > ind["min_m"]
    if anat_cfg.get("side_indicators"):
        check("axes_side_indicators", side_ok, side_measured, anat_cfg["side_indicators"],
              ".L = +X (rig-contract side_convention); sign * centroid x > min_m")
    # export frame: the same indicators after the UM_FBX_v1 rotation (relative to the body centroid)
    ef = export_frame
    ef_measured, ef_ok = {}, bool(export_inds)
    for ind in export_inds:
        c = ef["weapon_centroid_m"] if ind["what"] == "weapon" else ef["centroids_m"][ind["what"]]
        rel = [c[i] - ef["body_centroid_m"][i] for i in range(3)]
        value, _ = along(rel, export_axes[ind["axis"]])
        ef_measured["%s along %s" % (ind["what"], ind["axis"])] = value
        ef_ok = ef_ok and value > ind["min_m"]
    front_name = axis_name(export_axes["front"])
    if export_inds:
        check("export_frame_indicators_rotated", ef_ok, ef_measured,
              {"front": front_name, "left": axis_name(export_axes["left"]),
               "weapon_side": axis_name(export_axes["weapon_side"]) if "weapon_side" in export_axes else None,
               "indicators": export_inds},
              "centroids relative to the body centroid in the re-imported FBX before undoing the %s deg rotation"
              % preset["export_space_rotation_z_degrees"])
    all_tris = {n: [pre[n]["polygons"], pre[n]["triangles"]] for n in pre}
    rt_all = dict(rt_sk["meshes"], **rt_base["meshes"])
    check("triangulate_changes_no_geometry", all(e["polygons"] == e["triangles"] for e in rt_all.values())
          and all(rt_all.get(n, {}).get("triangles") == t for n, (_p, t) in all_tris.items()),
          {"pre_export_polygons_triangles": all_tris,
           "roundtrip_polygons_triangles": {n: [e["polygons"], e["triangles"]] for n, e in sorted(rt_all.items())}},
          note="preset use_triangles=%s: the export writes triangles only; meshes that were already all triangles "
               "keep their count, quads/ngons become exactly their loop triangles" % preset["use_triangles"])
    check("roundtrip_one_armature", rt_sk["armatures"] == 1 and rt_base["armatures"] == 0 and
          rt_sk["armature_objects"] == [profile["armature"]["object"]],
          {"skeletal_fbx": rt_sk["armature_objects"], "base_fbx": rt_base["armatures"]})
    rt_bones = rt_sk["bones"]
    check("roundtrip_bones", sorted(rt_bones) == sorted(bone_names) and len(rt_bones) == exp["bones"],
          len(rt_bones), exp["bones"])
    parents_ok = all(rt_bones.get(b[0], {}).get("parent") == b[1] for b in profile["armature"]["bones"])
    heads_ok = all(rt_bones.get(n) and all(abs(a - b) < 1e-4 for a, b in zip(rt_bones[n]["head_m"], bones_final[n][0]))
                   for n in bone_names)
    check("roundtrip_bone_hierarchy_and_rest_positions", parents_ok and heads_ok,
          {"parents_ok": parents_ok, "heads_within_1e-4_m": heads_ok})
    rt_tris = {n: e["triangles"] for n, e in rt_all.items()}
    check("roundtrip_triangles_preserved", rt_tris == tris, rt_tris, tris)
    rt_slots = {n: e["material_slots"] for n, e in rt_all.items()}
    sk_names = [m["body"]["object"]] + ([wmesh["object"]] if weapon else [])
    sk_unique = sorted({sl for n in sk_names for sl in rt_slots.get(n, []) if sl})
    check("roundtrip_material_slots", len(sk_unique) == exp["skeletal_material_slots"] and
          len(rt_slots.get(m["base"]["object"], [])) == exp["base_material_slots"],
          {"per_mesh": rt_slots, "skeletal_unique": sk_unique},
          {"skeletal_unique": exp["skeletal_material_slots"], "base": exp["base_material_slots"]})
    check("roundtrip_uv0", all(e["uv_layers"] == ["UVMap"] and e["uv0_in_unit_square"] for e in rt_all.values()),
          {n: e["uv_layers"] for n, e in rt_all.items()})
    if bmode == "parametric":
        check("roundtrip_base_mask", bool(rt_mask) and rt_mask["binary"] and set(rt_mask["rgb_counts"]) == set(base_mask["rgb_counts"]),
              {"build": base_mask, "roundtrip": rt_mask},
              note="the base mask survives the FBX (colors_type SRGB) with binary values and the same four classes; "
                   "corner counts differ because the export triangulates the base quads")
    rt_w = {n: e["weights"] for n, e in rt_sk["meshes"].items()}
    check("roundtrip_weights", rt_w[m["body"]["object"]]["unweighted_vertices"] == 0 and
          (not weapon or list(rt_w[wmesh["object"]]["bones_used"]) == [wmesh["bone"]]) and
          max(w["max_influences"] for w in rt_w.values()) <= profile["armature"]["max_influences"],
          {n: {k: w[k] for k in ("max_influences", "unweighted_vertices", "not_normalised_vertices")}
           for n, w in rt_w.items()})
    rt_bad = sorted(p for p, sc in orient_rt.items() if sc["score"] is None or sc["score"] < ocfg["min_score_after_fix"])
    check("roundtrip_orientation_all_parts_outward", not rt_bad,
          {p: sc["score"] for p, sc in sorted(orient_rt.items())}, ">= %s" % ocfg["min_score_after_fix"])
    ratio = [r((rt_hi_sk[i] - rt_lo_sk[i]) / (hi_sk[i] - lo_sk[i]), 6) for i in range(3)]
    check("roundtrip_scale_ratio_1", all(abs(v - 1) < 1e-4 for v in ratio), ratio,
          note="Blender re-reads the cm FBX (UnitScaleFactor 1.0) as metres")
    check("roundtrip_part_polygon_counts", {p: len(v) for p, v in sorted(rt_parts.items())} ==
          {p: len(v) for p, v in sorted(body_parts.items())} and
          (wmode != "parts" or {p: len(v) for p, v in sorted(rt_weapon_parts.items())} ==
           {p: len(v) for p, v in sorted(weapon_parts.items())}),
          {"body": {p: len(v) for p, v in sorted(rt_parts.items())},
           "weapon": {p: len(v) for p, v in sorted(rt_weapon_parts.items())}})
    lim = profile.get("proposed_limits_for_comparison_only") or {}
    tri_key = next((k for k in ("hero_triangles", "sidekick_triangles") if k in lim), None)
    capsule = lim.get("capsule_uu") or {}
    comparison = {
        "triangles": {"measured_skeletal": sum(tris[n] for n in sk_names), "with_base": sum(tris.values()),
                      "proposed_key": tri_key, "proposed": lim.get(tri_key) if tri_key else None},
        "texture_px": {"measured": size, "proposed": lim.get("texture_px")},
        "material_slots": {"measured_skeletal_unique": len(sk_unique), "base": len(rt_slots.get(m["base"]["object"], [])),
                           "proposed_max": lim.get("material_slots_max")},
        "height_uu": {"measured_figure_top": r(head_top * 100, 3), "skeletal_top": r(hi_sk[2] * 100, 3),
                      "proposed": lim.get("height_uu")},
        "base_uu": {"measured": [r(c * 100, 3) for c in base_dims], "proposed_diameter": lim.get("base_diameter_uu"),
                    "proposed_height": lim.get("base_height_uu")},
        "capsule_uu": {"max_radius_from_pivot_axis": r(radial * 100, 3), "body_max_radius": r(radial_body * 100, 3),
                       "core_max_radius": r(radial_core * 100, 3), "core_excludes": sorted(core_excluded),
                       "top": r(hi_sk[2] * 100, 3), "proposed": capsule or None,
                       "fits": bool(capsule) and bool(radial * 100 <= capsule["diameter"] / 2 + 1e-6
                                                      and hi_sk[2] * 100 <= capsule["height"]),
                       "core_fits": bool(capsule) and bool(radial_core * 100 <= capsule["diameter"] / 2 + 1e-6
                                                           and hi_sk[2] * 100 <= capsule["height"])},
        "footprint_vs_base": {"body_max_radius_uu": r(radial_body * 100, 3), "base_radius_uu": r(fx * 50, 3),
                              "note": "informational: how far the figure reaches past the base rim"},
        "note": "comparison with proposals only, not budgets (GD-058 open)"}
    if lim.get("span_max_uu") is not None:
        comparison["span_uu"] = {"measured": r(span * 100, 3), "proposed_max": lim["span_max_uu"],
                                 "fits": bool(span * 100 <= lim["span_max_uu"])}
    if lim.get("base_triangles") is not None:
        comparison["base_triangles"] = {"measured_after_triangulation": rt_tris[m["base"]["object"]],
                                        "proposed": lim["base_triangles"]}

    report = {
        "stage": "build",
        "flow": "seated-parts",
        "blender": bpy.app.version_string,
        "profile": {"id": profile["profile_id"], "status": profile["status"]},
        "source": {"file": ctx.source.name, "sha256": ctx.source_hash},
        "reference": {"file": reference.name, "sha256": reference_hash, "source_id": rcfg.get("source_id"),
                      "role": rcfg.get("role"), "use": "per-face orientation vote only"} if rcfg else None,
        "isolation_note": "live: temporary scenes, all created datablocks removed" if ctx.isolation == "live" else "process",
        "scale": scale_info,
        "source_part_polygons": source_polys,
        "dropped_parts": dropped,
        "weld": weld,
        "weapon": {"mode": wmode, "object": wmesh["object"] if wmesh else None, "info": weapon_info},
        "caps": caps_info,
        "closure": closure,
        "anatomy": anat,
        "body_parts": sorted(body_parts),
        "body_part_polygons": {p: len(v) for p, v in sorted(body_parts.items())},
        "cross_part_coincident_vertices": cross_part,
        "orientation": {"method": ocfg["method"], "raw_tripo": orient_raw, "before_reference_fix": orient_before_ref,
                        "reference_vote": ref_votes, "before_fix": orient_before, "flipped_parts": inside_out,
                        "after_fix": orient_after, "roundtrip": orient_rt, "corner_normals_opposed_area_share": opposed,
                        "corner_normals_preserved": normals_preserved},
        "materials": {"atlas": profile["materials"]["atlas"], "blender_images": mat_images,
                      "base": bcfg["material"] if bmode == "parametric" else profile["materials"]["atlas"]},
        "base": {"mode": bmode, "parametric": base_info, "mask": base_mask, "roundtrip_mask": rt_mask,
                 "feet_max_radius_m": r(feet_radial, 5)},
        "meshes_pre_export_m": pre,
        "weights": weights,
        "weights_per_part": per_part_weights,
        "weights_cleanup": heat_stats,
        "weights_coordinates_frame": coords_frame,
        "wings": wing_info,
        "tail": tail,
        "uv": uv_stats,
        "bones_final_m": bones_final,
        "bones_head_m": bone_heads,
        "sockets": sockets,
        "figure": {"top_part": top_part, "figure_height_m": fh, "figure_top_m": r(head_top),
                   "skeletal_top_m": r(hi_sk[2]), "skeletal_top_is_figure_top": abs(hi_sk[2] - head_top) < 1e-6,
                   "note": "figure height = top of scale.top_part; the skeletal mesh top (UE bounds) is the highest "
                           "vertex of body and weapon"},
        "bounds_m": {"skeletal": {"min": [r(c) for c in lo_sk], "max": [r(c) for c in hi_sk]},
                     "body": {"min": [r(c) for c in lo_body], "max": [r(c) for c in hi_body]},
                     "base": {"min": [r(c) for c in lo_base], "max": [r(c) for c in hi_base]},
                     "figure_with_base_height": r(height), "head_top": r(head_top), "span": r(span)},
        "expected_ue_bounds_uu_at_import_scale_1": {
            "skeletal_blender_axes": {"min": [r(c * 100, 3) for c in lo_sk], "max": [r(c * 100, 3) for c in hi_sk]},
            "base_blender_axes": {"min": [r(c * 100, 3) for c in lo_base], "max": [r(c * 100, 3) for c in hi_base]},
            "export_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
            "skeletal_export_frame": export_frame["skeletal_bounds_cm"],
            "base_export_frame": export_frame["base_bounds_cm"],
            "skeletal_ue_predicted": ue_predicted(export_frame["skeletal_bounds_cm"]),
            "base_ue_predicted": ue_predicted(export_frame["base_bounds_cm"]),
            "note": "*_blender_axes: authored frame (front -Y), centimetres; *_export_frame: as written into the FBX "
                    "(re-imported); *_ue_predicted: export frame mapped as UE (x, -y, z) per ART-001"},
        "axes": {"feet": toe_ankle, "body_centroid_m": body_c, "weapon_centroid_m": weapon_c,
                 "front_parts_centroids_m": front_parts, "side_indicators_centroids_m": side_values,
                 "export_frame": {k: v for k, v in export_frame.items() if not k.endswith("bounds_cm")},
                 "export_front_axis": front_name,
                 "export_weapon_side_axis": axis_name(export_axes["weapon_side"]) if "weapon_side" in export_axes else None},
        "pivot": pivot,
        "exports": {"skeletal": {"file": sk_fbx.name, "sha256": sha256(sk_fbx), "bytes": sk_fbx.stat().st_size},
                    "base": {"file": base_fbx.name, "sha256": sha256(base_fbx), "bytes": base_fbx.stat().st_size},
                    "settings": export_settings_report(preset, ctx.preset_rel, ctx.preset_path, ctx.data_scale)},
        "roundtrip": {"skeletal": rt_sk, "base": rt_base, "scale_ratio": ratio},
        "reference_comparison": None,
        "proposed_limits_comparison": comparison,
        "checks": dict(check),
        "passed": not check.failed(),
        "status": "technically_exported_not_art_accepted",
        "not_checked": [
            "art acceptance, silhouette, lighting, K1/K2/K3 (art track)",
            "deformation quality in animation; clips are not built by this stage (rig_deform_probe runs separately)",
            "budgets: numbers are measured only (proposals until GD-058)",
            "UV intra-part island padding (Tripo's own layout inside each cell)",
            "selection collision (UCP_ capsule proposal; skeletal meshes use a physics asset in UE)",
            "UE-side facing and socket world positions: ue-import stage (bounds axis map) and live frames",
        ],
    }
    if reference is not None and sha256(reference) != reference_hash:
        raise RuntimeError("reference GLB changed during build")
    return report
