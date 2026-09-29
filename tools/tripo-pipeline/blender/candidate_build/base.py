"""Parametric base (profile meshes.base.mode "parametric", profile section base_parametric): replaces a Tripo base
part that cannot be repaired cheaply (Harpy: open contact holes under the feet). A chamfered cylinder with fan
top/bottom and raised instance pips, a binary vertex-colour mask (R team band, G centre pips, B outer pips) and a
planar UV0; the preview material lights the pips by the object property um_instance_index.
Moved unchanged from build_harpy_candidate.py (2026-09-28)."""

import math
from collections import Counter

import bmesh
import bpy
from mathutils import Vector

from .core import r


def build_parametric_base(scene, cfg, mcfg, object_name, mesh_name):
    """Ø x h cylinder with a chamfer, fan top/bottom and raised pips; mask byte colours; planar UV0."""
    R0, zt, R1, h, n = cfg["radius_bottom_m"], cfg["side_top_z_m"], cfg["radius_top_m"], cfg["height_m"], cfg["segments"]
    pc = cfg["pips"]
    bm = bmesh.new()
    ang = [2 * math.pi * i / n for i in range(n)]
    bottom = [bm.verts.new((R0 * math.cos(a), R0 * math.sin(a), 0.0)) for a in ang]
    side_top = [bm.verts.new((R0 * math.cos(a), R0 * math.sin(a), zt)) for a in ang]
    top = [bm.verts.new((R1 * math.cos(a), R1 * math.sin(a), h)) for a in ang]
    cb = bm.verts.new((0.0, 0.0, 0.0))
    ct = bm.verts.new((0.0, 0.0, h))
    role = {}
    for i in range(n):
        j = (i + 1) % n
        role[bm.faces.new((bottom[j], bottom[i], cb))] = "bottom"
        role[bm.faces.new((bottom[i], bottom[j], side_top[j], side_top[i]))] = "band"
        role[bm.faces.new((side_top[i], side_top[j], top[j], top[i]))] = "band"
        role[bm.faces.new((top[i], top[j], ct))] = "top"
    pips = []
    for sector in pc["sector_azimuths_deg"]:
        base_ang = math.radians(sector)
        dphi = pc["arc_spacing_m"] / pc["ring_radius_m"]
        for slot, k in zip(pc["slots_per_sector"], (-1, 0, 1)):
            a = base_ang + k * dphi
            cx, cy = pc["ring_radius_m"] * math.cos(a), pc["ring_radius_m"] * math.sin(a)
            m = pc["pip_sides"]
            up = [bm.verts.new((cx + pc["pip_radius_m"] * math.cos(2 * math.pi * q / m),
                                cy + pc["pip_radius_m"] * math.sin(2 * math.pi * q / m), h + pc["raise_m"])) for q in range(m)]
            dn = [bm.verts.new((v.co.x, v.co.y, h - pc["skirt_m"])) for v in up]
            cen = bm.verts.new((cx, cy, h + pc["raise_m"]))
            kind = "pip_centre" if slot == "centre" else "pip_outer"
            for q in range(m):
                w = (q + 1) % m
                role[bm.faces.new((up[q], up[w], cen))] = kind
                role[bm.faces.new((dn[q], dn[w], up[w], up[q]))] = kind
            pips.append({"sector_deg": sector, "slot": slot, "centre_m": [r(cx, 5), r(cy, 5)],
                         "radius_from_axis_m": r(math.hypot(cx, cy), 5)})
    bm.normal_update()
    for f in bm.faces:  # outward check by construction: every face normal away from the axis/centre
        c = f.calc_center_median()
        kind = role[f]
        want = Vector((0, 0, -1)) if kind == "bottom" else Vector((0, 0, 1)) if kind in ("top",) else None
        if want is None:
            if kind == "band":
                want = Vector((c.x, c.y, 0)).normalized()
            else:  # pip: top faces up, skirt faces radially out of the pip
                pcen = min(pips, key=lambda q: math.hypot(q["centre_m"][0] - c.x, q["centre_m"][1] - c.y))["centre_m"]
                want = Vector((0, 0, 1)) if abs(f.normal.z) > 0.5 else Vector((c.x - pcen[0], c.y - pcen[1], 0)).normalized()
        if f.normal.dot(want) < 0:
            f.normal_flip()
    uv = bm.loops.layers.uv.new("UVMap")
    col = bm.loops.layers.color.new(mcfg["attribute"])
    colour = {"bottom": (0, 0, 0, 1), "top": (0, 0, 0, 1), "band": (1, 0, 0, 1),
              "pip_centre": (0, 1, 0, 1), "pip_outer": (0, 0, 1, 1)}
    side = {f for f in bm.faces if role[f] == "band" and abs(f.normal.z) < 0.2}
    for f in bm.faces:
        for loop in f.loops:
            co = loop.vert.co
            loop[uv].uv = (0.5 + co.x / (2 * R0) * 0.98, 0.5 + co.y / (2 * R0) * 0.98)
            loop[col] = colour[role[f]]
        f.smooth = f in side
    mesh = bpy.data.meshes.new(mesh_name)
    bm.to_mesh(mesh)
    roles = Counter(role.values())
    bm.free()
    obj = bpy.data.objects.new(object_name, mesh)
    scene.collection.objects.link(obj)
    return obj, {"faces_by_role": dict(sorted(roles.items())), "pips": pips}


def sock(sockets, name, kind):
    return next(x for x in sockets if x.name == name and x.type == kind)


def base_material(cfg):
    """Preview material of the base: dark top, team band (object prop um_team_color), pips lit by the object
    prop um_instance_index (1: G, 2: B, 3: G+B) — the UE material rule of profile base_parametric.mask."""
    cols = cfg["preview_colours_linear"]
    mat = bpy.data.materials.new(cfg["material"])
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = cfg.get("preview_roughness", 0.6)
    ca = nodes.new("ShaderNodeVertexColor")
    ca.layer_name = cfg["mask"]["attribute"]
    sep = nodes.new("ShaderNodeSeparateColor")
    links.new(ca.outputs["Color"], sep.inputs["Color"])
    idx = nodes.new("ShaderNodeAttribute")
    idx.attribute_type = "OBJECT"
    idx.attribute_name = "um_instance_index"
    team = nodes.new("ShaderNodeAttribute")
    team.attribute_type = "OBJECT"
    team.attribute_name = "um_team_color"

    def math_node(op, a, b=None):
        node = nodes.new("ShaderNodeMath")
        node.operation = op
        for k, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                node.inputs[k].default_value = v
            else:
                links.new(v, node.inputs[k])
        return node.outputs["Value"]

    centre_on = math_node("GREATER_THAN", math_node("ABSOLUTE", math_node("SUBTRACT", idx.outputs["Fac"], 2.0)), 0.5)
    outer_on = math_node("GREATER_THAN", idx.outputs["Fac"], 1.5)
    lit = math_node("MINIMUM", math_node("ADD", math_node("MULTIPLY", sep.outputs["Green"], centre_on),
                                         math_node("MULTIPLY", sep.outputs["Blue"], outer_on)), 1.0)
    mix_team = nodes.new("ShaderNodeMix")
    mix_team.data_type = "RGBA"
    sock(mix_team.inputs, "A", "RGBA").default_value = (*cols["base"], 1.0)
    links.new(team.outputs["Color"], sock(mix_team.inputs, "B", "RGBA"))
    links.new(sep.outputs["Red"], sock(mix_team.inputs, "Factor", "VALUE"))
    mix_pip = nodes.new("ShaderNodeMix")
    mix_pip.data_type = "RGBA"
    links.new(sock(mix_team.outputs, "Result", "RGBA"), sock(mix_pip.inputs, "A", "RGBA"))
    sock(mix_pip.inputs, "B", "RGBA").default_value = (*cols["pip"], 1.0)
    links.new(lit, sock(mix_pip.inputs, "Factor", "VALUE"))
    links.new(sock(mix_pip.outputs, "Result", "RGBA"), bsdf.inputs["Base Color"])
    em = nodes.new("ShaderNodeMix")
    em.data_type = "RGBA"
    sock(em.inputs, "A", "RGBA").default_value = (0, 0, 0, 1)
    sock(em.inputs, "B", "RGBA").default_value = (*cols["pip"], 1.0)
    links.new(lit, sock(em.inputs, "Factor", "VALUE"))
    links.new(sock(em.outputs, "Result", "RGBA"), bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = cfg.get("preview_emission_strength", 0.35)
    return mat
