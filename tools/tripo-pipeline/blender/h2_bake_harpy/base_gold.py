"""Metal base of the H2.1 Harpy (headless Blender part; the textures come from base_textures.py, system Python).

The parametric base of candidate_build.base (read-only library) has a planar top-down UV0 that squeezes the side wall
into a ring of zero UV area and a flat preview material (dark top, flat team band): in the H2 frames it read as flat
yellow plastic. H2.1 (profile base_material, proposal):

uv_layout(base, cfg)      re-maps UV0 of the base mesh: the side wall and chamfer (faces whose normal has |z| below
                          side_normal_z_max and that are no pip) -> a strip over the full texture width (u = azimuth /
                          360 deg, tileable), v = z / height inside band_v; top and pips -> a planar disc
                          (top_centre_uv, top_radius_uv at the base radius); bottom -> one texel (never seen).
preview_material(cfg, tex) Blender approximation of M_UM_BaseMarker with textures (UE graph, um_masters.py):
                          albedo = BC x BaseColor; band = lerp(albedo, TeamColor, vertex mask R x VertexMaskWeight)
                          (BandKeepsTexture 0), lit pips = PipColor + emission PipColor x PipEmissive by
                          InstanceIndex (object props um_team_color / um_instance_index as the H2 review), Metallic =
                          ORM.B, Roughness = ORM.G, Normal = N (OpenGL copy for Blender). Label "blender".
"""

import math

import bmesh
import bpy
import numpy as np


def uv_layout(base, cfg, pip_centres, pip_radius):
    L = cfg["uv_layout"]
    me = base.data
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active or bm.loops.layers.uv.new("UVMap")
    R0 = float(cfg["radius_bottom_m"])
    h = float(cfg["height_m"])
    v0, v1 = L["band_v"]
    cu, cv = L["top_centre_uv"]
    ru = float(L["top_radius_uv"])
    nz_max = float(L.get("side_normal_z_max", 0.9))
    pc = np.asarray(pip_centres, np.float64)
    counts = {"band": 0, "top": 0, "pip": 0, "bottom": 0}
    bm.normal_update()
    for f in bm.faces:
        cen = f.calc_center_median()
        d_pip = np.sqrt(((pc - np.array((cen.x, cen.y))) ** 2).sum(1)).min() if len(pc) else 1e9
        is_pip = d_pip <= pip_radius * 1.05 and cen.z > h - 0.002
        if f.normal.z < -0.5 and not is_pip:
            for l in f.loops:
                l[uv].uv = tuple(L["bottom_uv"])
            counts["bottom"] += 1
        elif abs(f.normal.z) < nz_max and not is_pip:
            angs = [math.atan2(l.vert.co.y, l.vert.co.x) % (2 * math.pi) for l in f.loops]
            if max(angs) - min(angs) > math.pi:  # face across the seam: keep it continuous (u > 1 wraps)
                angs = [a + 2 * math.pi if a < math.pi else a for a in angs]
            for l, a in zip(f.loops, angs):
                l[uv].uv = (a / (2 * math.pi), v0 + (v1 - v0) * min(max(l.vert.co.z / h, 0.0), 1.0))
            f.smooth = True  # the 72-segment wall and chamfer: smooth, so a metal highlight shows no facets
            counts["band"] += 1
        else:
            for l in f.loops:
                l[uv].uv = (cu + l.vert.co.x / R0 * ru, cv + l.vert.co.y / R0 * ru)
            counts["pip" if is_pip else "top"] += 1
    # hard edges where the wall meets the chamfer/top/bottom (> 30 deg), so the smooth wall does not bend the top
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(30.0):
            e.smooth = False
    bm.to_mesh(me)
    me.update()
    bm.free()
    return counts


def _sock(sockets, name, typ):
    return next(s for s in sockets if s.name == name and s.type == typ)


def preview_material(cfg, tex):
    """tex: {"BC": path, "N_OpenGL": path, "ORM": path}."""
    P = cfg["preview"]
    mat = bpy.data.materials.new(cfg["material"])
    try:
        mat.use_nodes = True
    except AttributeError:
        pass
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    img = {}
    for key, cs in (("BC", "sRGB"), ("N_OpenGL", "Non-Color"), ("ORM", "Non-Color")):
        im = bpy.data.images.load(str(tex[key]))
        im.colorspace_settings.name = cs
        node = nodes.new("ShaderNodeTexImage")
        node.image = im
        node.extension = "REPEAT"
        img[key] = node
    ca = nodes.new("ShaderNodeVertexColor")
    ca.layer_name = cfg["mask_attribute"]
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

    vmw = float(P.get("VertexMaskWeight", 1.0))
    centre_on = math_node("GREATER_THAN", math_node("ABSOLUTE", math_node("SUBTRACT", idx.outputs["Fac"], 2.0)), 0.5)
    outer_on = math_node("GREATER_THAN", idx.outputs["Fac"], 1.5)
    any_on = math_node("GREATER_THAN", idx.outputs["Fac"], 0.5)
    lit = math_node("MINIMUM", math_node("MULTIPLY", math_node("MULTIPLY", math_node(
        "ADD", math_node("MULTIPLY", sep.outputs["Green"], centre_on), math_node("MULTIPLY", sep.outputs["Blue"], outer_on)),
        any_on), vmw), 1.0)
    band = math_node("MINIMUM", math_node("MULTIPLY", sep.outputs["Red"], vmw), 1.0)
    albedo = nodes.new("ShaderNodeMix")
    albedo.data_type = "RGBA"
    albedo.blend_type = "MULTIPLY"
    _sock(albedo.inputs, "Factor", "VALUE").default_value = 1.0
    links.new(img["BC"].outputs["Color"], _sock(albedo.inputs, "A", "RGBA"))
    _sock(albedo.inputs, "B", "RGBA").default_value = tuple(P.get("BaseColor", (1.0, 1.0, 1.0))) + (1.0,)
    mix_team = nodes.new("ShaderNodeMix")
    mix_team.data_type = "RGBA"
    links.new(_sock(albedo.outputs, "Result", "RGBA"), _sock(mix_team.inputs, "A", "RGBA"))
    links.new(team.outputs["Color"], _sock(mix_team.inputs, "B", "RGBA"))
    links.new(band, _sock(mix_team.inputs, "Factor", "VALUE"))
    pip_col = tuple(P.get("PipColor", (0.78, 0.74, 0.64)))
    mix_pip = nodes.new("ShaderNodeMix")
    mix_pip.data_type = "RGBA"
    links.new(_sock(mix_team.outputs, "Result", "RGBA"), _sock(mix_pip.inputs, "A", "RGBA"))
    _sock(mix_pip.inputs, "B", "RGBA").default_value = pip_col + (1.0,)
    links.new(lit, _sock(mix_pip.inputs, "Factor", "VALUE"))
    links.new(_sock(mix_pip.outputs, "Result", "RGBA"), bsdf.inputs["Base Color"])
    em = nodes.new("ShaderNodeMix")
    em.data_type = "RGBA"
    _sock(em.inputs, "A", "RGBA").default_value = (0, 0, 0, 1)
    _sock(em.inputs, "B", "RGBA").default_value = pip_col + (1.0,)
    links.new(lit, _sock(em.inputs, "Factor", "VALUE"))
    links.new(_sock(em.outputs, "Result", "RGBA"), bsdf.inputs["Emission Color"])
    bsdf.inputs["Emission Strength"].default_value = float(P.get("PipEmissive", 0.35))
    sepo = nodes.new("ShaderNodeSeparateColor")
    links.new(img["ORM"].outputs["Color"], sepo.inputs["Color"])
    links.new(sepo.outputs["Green"], bsdf.inputs["Roughness"])
    links.new(sepo.outputs["Blue"], bsdf.inputs["Metallic"])
    nm = nodes.new("ShaderNodeNormalMap")
    links.new(img["N_OpenGL"].outputs["Color"], nm.inputs["Color"])
    links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    mat.use_backface_culling = True
    return mat
