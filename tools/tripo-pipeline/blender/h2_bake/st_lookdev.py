"""Look-dev Blender stages (headless): ld_fbx (UV1 in metres + UM_FBX_v1 export + read-back) and ld_preview (Cycles
frames framed like the concepts: class-ID pass, H2.1 beauty, H2LD beauty). Driver: run_h2_bake.py --mode lookdev.

ld_fbx: the figure is appended from the H2.1 run (work/sk_authored.blend: armature, weights, body/bow/base meshes in the
authored frame, saved by the rig stage before the export transform). Nothing of the geometry, weights or skeleton is
touched; only a second UV layer is added:
  UV1 = (UV0 - c_island) x s_island, s_island = sqrt(area3D / areaUV0) of the UV0 island (metres per UV unit), c_island =
  centre of the island's UV0 bounding box (UE half-float UVs: small |UV1| keeps sub-millimetre precision),
so UV1 is in metres of the object (the detail tiles use uvD = UV1 x tilesPerMeter) and every island is a uniform
scale of its UV0 island: no rotation and no mirror, so the detail normal stays in the tangent basis UE builds from UV0.
Islands: polygons connected through shared (vertex, UV0) corners. The export is the rig-stage export (candidate_build.core,
determinism pins), then read-back checks against the H2.1 FBX read back in the same process: bones and parents,
triangles, positions and UV0 of every loop identical, face +X, UV layer order [UVMap, UV1_m], UV1 density.

ld_preview: the same studio light, AgX and orthographic cameras as st_preview (concept framing), materials:
  H21   st_preview.pbr_material with the H2.1 4K textures (what M_UM_Figure v1 shows today),
  LD    Principled driven by MatID + LUT (the hero DDS written as EXR for Blender, 16 x 16, rows of build_ue_inputs.py): roughness = LUT typical,
        metallic = LUT, Specular IOR Level = specular x (1 - clothAmount) for Cloth classes (the UE Cloth lobe replaces
        GGX by clothAmount), Sheen Weight = clothAmount, Sheen Tint = fuzz colour of README §4, legacy_bake (id 0) = bake;
        no detail tiles (UE side);
  CLASS emission of MatID (Closest), Raw/Standard view, 1 sample, filter 0.01 px -> exact class per pixel."""

import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import bl_util as U


def load_ld(params):
    return json.loads(Path(params["lookdev"]).read_text(encoding="utf-8"))


def append_figure(src_blend, names):
    with bpy.data.libraries.load(str(src_blend), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in names]
    return list(dst.objects)


# ------------------------------------------------------------------ UV1
def islands(mesh):
    """Island index per polygon (UV0 connectivity through shared vertex + identical UV)."""
    nl, npoly = len(mesh.loops), len(mesh.polygons)
    lv = np.empty(nl, np.int64)
    mesh.loops.foreach_get("vertex_index", lv)
    uv = np.empty(nl * 2, np.float64)
    mesh.uv_layers[0].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    q = np.round(uv * (1 << 22)).astype(np.int64)
    keys = np.stack([lv, q[:, 0], q[:, 1]], 1)
    _u, corner = np.unique(keys, axis=0, return_inverse=True)
    corner = corner.ravel()
    ls = np.empty(npoly, np.int64)
    lt = np.empty(npoly, np.int64)
    mesh.polygons.foreach_get("loop_start", ls)
    mesh.polygons.foreach_get("loop_total", lt)
    parent = list(range(int(corner.max()) + 1))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for p in range(npoly):
        base = find(int(corner[ls[p]]))
        for k in range(1, int(lt[p])):
            b = find(int(corner[ls[p] + k]))
            if b != base:
                if b < base:
                    parent[base] = b
                    base = b
                else:
                    parent[b] = base
    root = np.array([find(int(corner[ls[p]])) for p in range(npoly)], np.int64)
    _r, isl = np.unique(root, return_inverse=True)
    return isl.ravel(), uv, ls, lt


def poly_uv_area(uv, ls, lt):
    area = np.zeros(len(ls))
    for n in np.unique(lt):
        sel = np.nonzero(lt == n)[0]
        idx = ls[sel][:, None] + np.arange(n)[None, :]
        u, v = uv[idx, 0], uv[idx, 1]
        area[sel] = 0.5 * np.abs((u * np.roll(v, -1, 1) - np.roll(u, -1, 1) * v).sum(1))
    return area


def add_uv1(obj, name):
    mesh = obj.data
    isl, uv, ls, lt = islands(mesh)
    a3 = np.empty(len(mesh.polygons))
    mesh.polygons.foreach_get("area", a3)
    auv = poly_uv_area(uv, ls, lt)
    n = int(isl.max()) + 1
    A3 = np.bincount(isl, a3, n)
    AUV = np.bincount(isl, auv, n)
    s = np.sqrt(A3 / np.maximum(AUV, 1e-18))
    order = np.argsort(ls, kind="stable")
    loop_isl = np.empty(len(uv), np.int64)
    for p in order:
        loop_isl[ls[p]:ls[p] + lt[p]] = isl[p]
    # centred per island (UV0 bounding-box centre): UE stores UVs as half floats unless Full Precision UVs is on; at
    # |UV1| <= 0.25 m the half step is <= 0.25 mm, below a detail texel (translation keeps the tangent frame)
    lo = np.full((n, 2), np.inf)
    hi = np.full((n, 2), -np.inf)
    np.minimum.at(lo, loop_isl, uv)
    np.maximum.at(hi, loop_isl, uv)
    centre = (lo + hi) * 0.5
    uv1 = (uv - centre[loop_isl]) * s[loop_isl][:, None]
    layer = mesh.uv_layers.new(name=name)
    layer.data.foreach_set("uv", uv1.astype(np.float32).ravel())
    mesh.uv_layers.active_index = 0
    mesh.uv_layers[0].active_render = True
    ratio = (AUV * s * s) / np.maximum(A3, 1e-18)
    return {"islands": n, "metres_per_uv_unit_p5_p50_p95": [U.r(x, 5) for x in np.percentile(s, [5, 50, 95])],
            "uv1_extent": [U.rv(uv1.min(0), 4), U.rv(uv1.max(0), 4)], "uv1_abs_max_m": U.r(np.abs(uv1).max(), 4),
            "half_float_step_at_abs_max_mm": U.r(2.0 ** (np.floor(np.log2(max(np.abs(uv1).max(), 1e-6))) - 10) * 1000.0, 4),
            "density_ratio_min_max": [U.r(ratio.min(), 6), U.r(ratio.max(), 6)],
            "zero_area_islands": int((AUV <= 1e-18).sum())}


def uv1_density_readback(obj, layer_name):
    """Per island: area(UV1) / area3D (read-back mesh, export frame -> data scale removed by the caller)."""
    mesh = obj.data
    isl, _uv0, ls, lt = islands(mesh)
    uv1 = np.empty(len(mesh.loops) * 2, np.float64)
    mesh.uv_layers[layer_name].data.foreach_get("uv", uv1)
    a1 = poly_uv_area(uv1.reshape(-1, 2), ls, lt)
    a3 = np.empty(len(mesh.polygons))
    mesh.polygons.foreach_get("area", a3)
    sc = obj.matrix_world.to_3x3().determinant() ** (2.0 / 3.0)
    n = int(isl.max()) + 1
    r = np.bincount(isl, a1, n) / np.maximum(np.bincount(isl, a3 * sc, n), 1e-18)
    return r


def loops_signature(obj):
    mesh = obj.data
    co = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", co)
    lv = np.empty(len(mesh.loops), np.int64)
    mesh.loops.foreach_get("vertex_index", lv)
    uv = np.empty(len(mesh.loops) * 2)
    mesh.uv_layers[0].data.foreach_get("uv", uv)
    mw = np.array(obj.matrix_world)
    p = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    return p[lv], uv.reshape(-1, 2)


def run_fbx(params, profile, ld):
    from candidate_build import core
    from candidate_build import measure

    run_dir, repo = Path(params["run_dir"]), Path(params["repo_root"])
    src_run = repo / ld["source"]["run"]
    rig, meshes = profile["rig"], profile["meshes"]
    scene = U.reset()
    names = (rig["armature_object"], meshes["body"], meshes["weapon"], meshes["base"])
    objs = append_figure(src_run / ld["source"]["files"]["sk_authored"], names)
    for o in objs:
        scene.collection.objects.link(o)
    arm = bpy.data.objects[rig["armature_object"]]
    body, weapon, base = (bpy.data.objects[meshes[k]] for k in ("body", "weapon", "base"))
    # the atlas image: the H2LD BC (the FBX stores the file name only, path_mode STRIP)
    for mat in bpy.data.materials:
        if mat.use_nodes:
            for n in mat.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image is not None:
                    n.image.filepath = str(run_dir / "textures" / ("%s_BC.png" % ld["prefix"]))
                    n.image.name = "%s_BC.png" % ld["prefix"]
    uv1 = {o.name: add_uv1(o, ld["uv1"]["layer_name"]) for o in (body, weapon, base)}
    pre = {o.name: measure.mesh_summary(o) for o in (body, weapon, base)}
    # face polygons (as the rig stage: head part, not a cap, in the face box, facing -Y)
    vpart = np.load(src_run / "work" / "rig" / "body_vertex_part.npy")
    fcap = np.load(src_run / "work" / "rig" / "body_face_cap.npy")
    face_box = next((d["box_m"] for d in profile["retopo"].get("dense_regions", []) if d["name"] == "face"), None)
    face_polys = [p.index for p in body.data.polygons
                  if vpart[p.vertices[0]] == 1 and fcap[p.index] == 0 and face_box
                  and all(face_box[0][k] <= p.center[k] <= face_box[1][k] for k in range(3)) and p.normal.y < -0.3]
    preset_path = repo / profile["exports"]["fbx_preset"]
    preset = core.load_preset(preset_path)
    rot = core.export_rotation(preset)
    data_scale = float(preset["temporary_data_scale"])
    if bpy.data.filepath:
        raise RuntimeError("bpy.data.filepath must stay empty before the FBX export (deterministic bytes)")
    core.transform_for_fbx(scene, arm, (body, weapon, base), Matrix.Scale(data_scale, 4) @ rot)
    sk_fbx = run_dir / "export" / ld["exports"]["skeletal_fbx"]
    base_fbx = run_dir / "export" / ld["exports"]["base_fbx"]
    core.export_pair(scene, arm, (body, weapon), base, preset, sk_fbx, base_fbx)
    bone_names = [b[0] for b in rig["bones"]]
    # read back: new FBX and the H2.1 FBX
    sets = {}
    for tag, sk, bs in (("ld", sk_fbx, base_fbx),
                        ("h21", src_run / ld["source"]["files"]["skeletal_fbx"], src_run / ld["source"]["files"]["base_fbx"])):
        s1 = bpy.data.scenes.new("rt_%s" % tag)
        core.import_fbx_into(s1, sk)
        s2 = bpy.data.scenes.new("rtb_%s" % tag)
        core.import_fbx_into(s2, bs)
        m1, o1 = measure.roundtrip_measure(s1, bone_names)
        m2, o2 = measure.roundtrip_measure(s2, bone_names)
        sets[tag] = {"meas": (m1, m2), "objs": dict(o1, **o2), "scene": s1}
    checks = core.Checks()
    ld_m, h_m = sets["ld"]["meas"], sets["h21"]["meas"]
    checks("bones_and_parents_as_h21", {n: v["parent"] for n, v in ld_m[0]["bones"].items()} ==
           {n: v["parent"] for n, v in h_m[0]["bones"].items()} == {b[0]: b[1] for b in rig["bones"]},
           len(ld_m[0]["bones"]), len(rig["bones"]))
    checks("bone_heads_tails_as_h21", ld_m[0]["bones"] == h_m[0]["bones"], "equal", "equal (5 decimals, export frame)")
    tri = lambda m: {n: e["triangles"] for n, e in list(m[0]["meshes"].items()) + list(m[1]["meshes"].items())}
    checks("triangles_as_h21", tri(ld_m) == tri(h_m), tri(ld_m), tri(h_m))
    geo = {}
    same = True
    for name, obj in sets["ld"]["objs"].items():
        ref = sets["h21"]["objs"].get(name)
        if ref is None or len(obj.data.loops) != len(ref.data.loops):
            same = False
            geo[name] = "missing or different loop count"
            continue
        p1, uv_a = loops_signature(obj)
        p2, uv_b = loops_signature(ref)
        dp, du = float(np.abs(p1 - p2).max()), float(np.abs(uv_a - uv_b).max())
        geo[name] = {"max_abs_position_diff": dp, "max_abs_uv0_diff": du}
        same &= dp <= 1e-6 and du <= 1e-7
    checks("positions_and_uv0_per_loop_as_h21", same, geo, "<= 1e-6 m / 1e-7 UV")
    layers = {n: [u.name for u in o.data.uv_layers] for n, o in sets["ld"]["objs"].items()}
    checks("uv_layers_order", all(v == ["UVMap", ld["uv1"]["layer_name"]] for v in layers.values()), layers,
           ["UVMap", ld["uv1"]["layer_name"]])
    dens = {}
    tol = float(ld["uv1"]["density_tolerance"])
    ok = True
    for n, o in sets["ld"]["objs"].items():
        r = uv1_density_readback(o, ld["uv1"]["layer_name"])
        # read back in the export frame: the importer returns metres (data scale undone by the unit patch)
        dens[n] = {"islands": int(len(r)), "ratio_p1_p50_p99": [U.r(x, 5) for x in np.percentile(r, [1, 50, 99])]}
        ok &= bool(np.all(np.abs(np.percentile(r, [1, 99]) - 1.0) <= tol))
    checks("uv1_metres_density_readback", ok, dens, "area(UV1) / area3D = 1 +- %s (p1..p99 of islands)" % tol)
    rt_body = sets["ld"]["objs"].get(meshes["body"])
    front_export = rot.to_3x3() @ Vector((0.0, -1.0, 0.0))
    face_rt = measure.facing(rt_body, face_polys) if rt_body else None
    checks("export_frame_face_points_along_rotated_front_ue_plus_x",
           face_rt is not None and Vector(face_rt).dot(front_export) > 0.5 and abs(front_export.x - 1.0) < 1e-6,
           {"face_normal": face_rt, "rotated_front": U.rv(front_export, 3), "face_polygons": len(face_polys)}, "dot > 0.5, front = +X")
    rep = {"stage": "ld_fbx", "uv1": dict(ld["uv1"], per_mesh=uv1), "meshes_pre_export": pre,
           "exports": {"skeletal_fbx": {"path": (Path(ld["run_rel"]) / "export" / sk_fbx.name).as_posix(), "sha256": core.sha256(sk_fbx),
                                        "bytes": sk_fbx.stat().st_size},
                       "base_fbx": {"path": (Path(ld["run_rel"]) / "export" / base_fbx.name).as_posix(), "sha256": core.sha256(base_fbx),
                                    "bytes": base_fbx.stat().st_size},
                       "settings": core.export_settings_report(preset, profile["exports"]["fbx_preset"], preset_path, data_scale)},
           "roundtrip": {"ld": {"skeletal": ld_m[0], "base": ld_m[1]}},
           "ue_import_notes": ["UV1_m — второй UV-канал (индекс 1): при импорте SM подставки выключить Generate Lightmap UVs "
                               "или DstLightmapIndex >= 2, иначе UE перезапишет UV1 картой освещения",
                               "материальный слот тот же (M_Medusa_H2_Atlas), назначается MI v2"],
           "checks": dict(checks), "failed": checks.failed(), "passed": not checks.failed(), "status": "измерено",
           "claims": {"art_accepted": False, "game_ready": False}}
    U.write_json(run_dir / "reports" / "ld-fbx-report.json", rep)
    if checks.failed():
        raise RuntimeError("ld_fbx checks failed: %s" % checks.failed())


# ------------------------------------------------------------------ preview
def lut_material(name, tex, cull):
    """Principled driven by MatID + LUT (see the module docstring)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    N, L = nt.nodes, nt.links
    bsdf = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    uv = N.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"

    def image(path, colour, closest=False):
        img = bpy.data.images.load(str(path), check_existing=True)
        img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        img.alpha_mode = "CHANNEL_PACKED"
        node = N.new("ShaderNodeTexImage")
        node.image = img
        if closest:
            node.interpolation = "Closest"
            node.extension = "EXTEND"
        return node

    def math(op, a, b=None, clamp=False):
        n = N.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                n.inputs[i].default_value = float(x)
            else:
                L.new(x, n.inputs[i])
        return n.outputs[0]

    t_bc, t_n, t_orm = image(tex["BC"], True), image(tex["N_OpenGL"], False), image(tex["ORM"], False)
    t_id = image(tex["MatID"], False, closest=True)
    for t in (t_bc, t_n, t_orm, t_id):
        L.new(uv.outputs["UV"], t.inputs["Vector"])
    sep_id = N.new("ShaderNodeSeparateColor")
    L.new(t_id.outputs["Color"], sep_id.inputs["Color"])
    cid = math("FLOOR", math("MULTIPLY", sep_id.outputs["Red"], 255.0 / 16.0))
    u = math("DIVIDE", math("ADD", cid, 0.5), 16.0)
    is_lib = math("GREATER_THAN", cid, 0.5)
    rows = {}
    for r in range(8):
        cx = N.new("ShaderNodeCombineXYZ")
        L.new(u, cx.inputs["X"])
        cx.inputs["Y"].default_value = 1.0 - (r + 0.5) / float(tex.get("LUT_ROWS", 16))
        t = image(tex["LUT"], False, closest=True)
        L.new(cx.outputs["Vector"], t.inputs["Vector"])
        sp = N.new("ShaderNodeSeparateColor")
        L.new(t.outputs["Color"], sp.inputs["Color"])
        rows[r] = (sp.outputs["Red"], sp.outputs["Green"], sp.outputs["Blue"], t.outputs["Alpha"])
    sep_orm = N.new("ShaderNodeSeparateColor")
    L.new(t_orm.outputs["Color"], sep_orm.inputs["Color"])

    def mix(a, b, f):  # a*(1-f) + b*f, scalars
        return math("ADD", math("MULTIPLY", a, math("SUBTRACT", 1.0, f)), math("MULTIPLY", b, f))

    L.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
    L.new(mix(sep_orm.outputs["Green"], rows[1][0], is_lib), bsdf.inputs["Roughness"])
    L.new(mix(sep_orm.outputs["Blue"], rows[0][3], is_lib), bsdf.inputs["Metallic"])
    cloth = math("MULTIPLY", rows[2][1], rows[3][3])  # clothAmount x (shadingModel == Cloth)
    spec = math("MULTIPLY", rows[2][0], math("SUBTRACT", 1.0, cloth))
    L.new(mix(0.5, spec, is_lib), bsdf.inputs["Specular IOR Level"])
    L.new(math("MULTIPLY", cloth, is_lib), bsdf.inputs["Sheen Weight"])
    L.new(rows[3][2], bsdf.inputs["Sheen Roughness"])
    # fuzz = sheenI * lerp(1, BC / Y, tint) * sqrt(Y)
    bw = N.new("ShaderNodeRGBToBW")
    L.new(t_bc.outputs["Color"], bw.inputs["Color"])
    y = math("MAXIMUM", bw.outputs["Val"], 1e-3)
    norm = N.new("ShaderNodeVectorMath")
    norm.operation = "DIVIDE"
    L.new(t_bc.outputs["Color"], norm.inputs[0])
    cy = N.new("ShaderNodeCombineXYZ")
    for k in ("X", "Y", "Z"):
        L.new(y, cy.inputs[k])
    L.new(cy.outputs["Vector"], norm.inputs[1])
    mx = N.new("ShaderNodeMix")
    mx.data_type = "VECTOR"
    L.new(rows[3][1], mx.inputs["Factor"])
    mx.inputs[4].default_value = (1.0, 1.0, 1.0)
    L.new(norm.outputs["Vector"], mx.inputs[5])
    sc = N.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    L.new(mx.outputs[1], sc.inputs[0])
    L.new(math("MULTIPLY", rows[3][0], math("SQRT", y)), sc.inputs["Scale"])
    L.new(sc.outputs["Vector"], bsdf.inputs["Sheen Tint"])
    nm = N.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    L.new(t_n.outputs["Color"], nm.inputs["Color"])
    L.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if cull:
        out = next(n for n in N if n.type == "OUTPUT_MATERIAL")
        geo = N.new("ShaderNodeNewGeometry")
        clear = N.new("ShaderNodeBsdfTransparent")
        m = N.new("ShaderNodeMixShader")
        L.new(geo.outputs["Backfacing"], m.inputs["Fac"])
        L.new(bsdf.outputs["BSDF"], m.inputs[1])
        L.new(clear.outputs["BSDF"], m.inputs[2])
        L.new(m.outputs["Shader"], out.inputs["Surface"])
    return mat


def class_material(name, matid, cull):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    img = bpy.data.images.load(str(matid), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.interpolation = "Closest"
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    nt.links.new(uv.outputs["UV"], t.inputs["Vector"])
    nt.links.new(t.outputs["Color"], em.inputs["Color"])
    shader = em.outputs["Emission"]
    if cull:
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        clear = nt.nodes.new("ShaderNodeBsdfTransparent")
        m = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Backfacing"], m.inputs["Fac"])
        nt.links.new(shader, m.inputs[1])
        nt.links.new(clear.outputs["BSDF"], m.inputs[2])
        shader = m.outputs["Shader"]
    nt.links.new(shader, out.inputs["Surface"])
    return mat


def run_preview(params, profile, ld):
    from . import st_preview as P

    run_dir, repo = Path(params["run_dir"]), Path(params["repo_root"])
    src_run = repo / ld["source"]["run"]
    pcfg, lcfg = profile["preview"], ld["preview"]
    raw = run_dir / "work" / "ld_preview_raw"
    raw.mkdir(parents=True, exist_ok=True)
    scene = U.reset()
    device = U.setup_cycles(scene, "GPU", samples=int(lcfg["samples"]), seed=0)
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "None"
    world = bpy.data.worlds.new("preview_world")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.045, 0.045, 0.05, 1.0)
    bg.inputs[1].default_value = 1.0
    P.area_light(scene, "key", (-1.5, -2.0, 2.0), 250, 1.5)
    P.area_light(scene, "fill", (2.0, -1.5, 1.0), 90, 2.0)
    P.area_light(scene, "rim", (0.5, 2.5, 2.2), 160, 1.5)
    names = (profile["rig"]["armature_object"], profile["meshes"]["body"], profile["meshes"]["weapon"], profile["meshes"]["base"])
    objs = append_figure(src_run / ld["source"]["files"]["sk_authored"], names)
    for o in objs:
        scene.collection.objects.link(o)
    meshes = [o for o in objs if o.type == "MESH"]
    cull = bool(pcfg.get("backface_culling", False))
    sp, lp = ld["source"]["prefix"], ld["prefix"]
    sdir, tdir = src_run / "textures", run_dir / "textures"
    mats = {"h21": P.pbr_material("LD_PREVIEW_H21", sdir / ("%s_BC.png" % sp), sdir / ("%s_N_OpenGL.png" % sp),
                                  sdir / ("%s_ORM.png" % sp), cull),
            "ld": lut_material("LD_PREVIEW_LD", {"BC": tdir / ("%s_BC.png" % lp), "N_OpenGL": tdir / ("%s_N_OpenGL.png" % lp),
                                                 "ORM": tdir / ("%s_ORM.png" % lp), "MatID": tdir / ("%s_MatID.png" % lp),
                                                 "LUT": run_dir / "work" / ("%s.exr" % ld["lut_name"]), "LUT_ROWS": 16}, cull),
            "class": class_material("LD_PREVIEW_CLASS", tdir / ("%s_MatID.png" % lp), cull)}
    lut_img = next(i for i in bpy.data.images if i.filepath.endswith(".exr"))
    lut_px = U.image_to_array(lut_img)  # Blender rows: bottom first
    ref = np.load(run_dir / "work" / ("%s.npy" % ld["lut_name"]))[::-1]  # DDS read back, row 0 = top -> Blender bottom-first
    lut_check = {"size": list(lut_img.size), "max_abs_diff_vs_json": U.r(float(np.abs(lut_px - ref).max()), 5),
                 "float_buffer": bool(lut_img.is_float)}

    def use(tag):
        for o in meshes:
            o.data.materials.clear()
            o.data.materials.append(mats[tag])

    cam_data = bpy.data.cameras.new("ld_cam")
    cam = bpy.data.objects.new("ld_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    shots = []

    def render(name, tag, res, class_pass=False):
        use(tag)
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        if class_pass:
            scene.cycles.samples = 1
            scene.cycles.use_denoising = False
            scene.cycles.filter_width = 0.01
            try:
                scene.view_settings.view_transform = "Raw"
            except TypeError:
                scene.view_settings.view_transform = "Standard"
            scene.render.film_transparent = True
            scene.render.image_settings.color_mode = "RGBA"
            scene.render.image_settings.color_depth = "8"
        else:
            scene.cycles.samples = int(lcfg["samples"])
            scene.cycles.use_denoising = True
            scene.cycles.filter_width = 1.5
            scene.view_settings.view_transform = "AgX"
            scene.render.film_transparent = False
            scene.render.image_settings.color_mode = "RGB"
        scene.render.filepath = str(raw / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        shots.append({"name": name, "set": tag, "px": list(res), "view_transform": scene.view_settings.view_transform})

    W, H = 1021, 1540
    top, bottom, base_x = 0.02, 0.968, 0.45
    height_m = float(profile["scale"]["figure_top_m"]) / (bottom - top)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = height_m
    cam_data.sensor_fit = "VERTICAL"
    zc = float(profile["scale"]["figure_top_m"]) - (0.5 - top) * height_m
    shift = (0.5 - base_x) * height_m * W / H
    views = {"front": (Vector((shift, -3.0, zc)), (0, -1, 0)), "side": (Vector((3.0, shift, zc)), (1, 0, 0)),
             "back": (Vector((-shift, 3.0, zc)), (0, 1, 0))}
    for vn, (loc, d) in views.items():
        cam.location = loc
        cam.rotation_euler = (-Vector(d)).to_track_quat("-Z", "Y").to_euler()
        render("class-%s" % vn, "class", (W, H), class_pass=True)
        for tag in ("h21", "ld"):
            render("beauty-%s-%s" % (vn, tag), tag, (W, H))
    closeups = {c["name"]: c for c in pcfg["closeups"]}
    for name in lcfg.get("closeups", []):
        c = closeups[name]
        cam_data.type = "ORTHO"
        cam_data.sensor_fit = "AUTO"
        cam_data.ortho_scale = float(c["ortho_m"])
        P.look_at(cam, c["target_m"], c["dir"], 2.0)
        for tag in ("h21", "ld"):
            render("closeup-%s-%s" % (name, tag), tag, (900, 900))
    U.write_json(run_dir / "reports" / "ld-preview-report.json",
                 {"stage": "ld_preview", "device": device, "samples": lcfg["samples"], "label": lcfg["label"],
                  "lut_exr_read_by_blender": lut_check, "shots": shots, "backface_culling": cull, "status": "измерено"})
    if lut_check["max_abs_diff_vs_json"] > 2e-3:
        raise RuntimeError("LUT EXR read by Blender differs from the JSON: %s" % lut_check)


def run(params, profile):
    ld = load_ld(params)
    ld["run_rel"] = params.get("run_rel", "")
    if params["stage"] == "ld_fbx":
        run_fbx(params, profile, ld)
    elif params["stage"] == "ld_preview":
        run_preview(params, profile, ld)
    else:
        raise ValueError(params["stage"])
