"""SEL showcase: the Tripo H2 high-poly of a hero with the IN-GAME look (docs/game-design/select-screens/06-HIPOLY-LOOKDEV.md).

    blender -b --factory-startup --python tools/art/showcase/hp_lookdev_bake.py -- <arthur|medusa> [--quick]

1. Geometry (the artifacts of the raw source):
   - King Arthur: the textured GLB imported and repaired exactly as the H2 pipeline does it (h2_bake_arthur bl / repairs,
     profile king-arthur-skeletal-um-fbx-v1-h2.json): phantom parts dropped, the head (part 6) symmetrized at x = -0.0077 m
     (the second face profile), the holes the phantoms cut in the cloak (0) and the forearm (12) filled.
   - Medusa: the textured high-poly HPT_* of the H2 bake (hp.blend, the final frame of the game mesh).
   - Both: the Tripo base dropped (the showcase uses the game pedestal); every part welded at 1e-6 m, custom split normals
     cleared and shaded smooth (the hard shading lines of the glTF split normals).
2. Look: per kept part, the game look-dev maps (BaseColor, ORM, MatID, EdgeMask, TeamAccent on the game UV0) are baked
   from the game low-poly (same frame) onto the part's own Tripo UV (Cycles EMIT, selected to active); the normal map
   is the part's own Tripo normal (OpenGL -> DirectX). Two passes against bleeding (live frame 2026-10-16: a 12 mm ray
   from Arthur's face hit the sword and painted gold stripes on the cheek): a tight cage (p99 low/high deviation is
   ~0.4 mm) with a hit mask, the texels it missed from a wide cage; Arthur bakes part to part (LP_<part> only). In UE the parts take the game master M_UM_Figure_v2 through MIs
   of the game MIs (tools/art/showcase/import_hipoly_lookdev.py).
Output: art/pipeline-candidates/<ASSET>/20261016-hp-showcase/{textures,export,reports}.
"""

import json
import math
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np

REPO = Path(__file__).resolve().parents[3]
ARTHUR_MOD = REPO / "tools/tripo-pipeline/blender/h2_bake_arthur"

HEROES = {
    "arthur": {
        "key": "KingArthur",
        "asset": "art/pipeline-candidates/ASSET-KING-ARTHUR-001",
        "profile": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/build-profiles/king-arthur-skeletal-um-fbx-v1-h2.json",
        "tex_glb": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-tripo/source/king-arthur-h2-tripo-c24eeff0-tex8k-pbr.glb",
        "low_blend": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20260929-h2-bake/work/h2-lowpoly.blend",
        "low_skip": ["LP_tripo_part_4"],
        "base_part": "tripo_part_4",
        "maps": {
            "BC": ("20260929-h2-lookdev/textures/T_KingArthur_H2LD_BC_4K.png", "sRGB"),
            "ORM": ("20260929-h2-lookdev/textures/T_KingArthur_H2LD_ORM_4K.png", "Non-Color"),
            "MatID": ("20260929-h2-lookdev/textures/T_KingArthur_H2LD_MatID_2K.png", "Non-Color"),
            "EdgeMask": ("20260929-h2-lookdev/textures/T_KingArthur_H2LD_EdgeMask_4K.png", "Non-Color"),
            "TeamAccent": ("20260929-h2-lookdev/textures/T_KingArthur_H2LD_TeamAccent_4K.png", "Non-Color"),
        },
        "height_m": 0.98,
    },
    "medusa": {
        "key": "Medusa",
        "asset": "art/pipeline-candidates/ASSET-MEDUSA-001",
        "high_blend": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake/work/hp.blend",
        "high_prefix": "HPT_",
        "low_blend": "art/pipeline-candidates/ASSET-MEDUSA-001/20260929-h2-bake/work/sk_authored.blend",
        "low_names": ["SK_Medusa_H2_Body", "SK_Medusa_H2_Bow"],
        "base_part": "tripo_part_2",
        "maps": {
            "BC": ("20260929-h2-lookdev/textures/T_Medusa_H2LD_BC.png", "sRGB"),
            "ORM": ("20260929-h2-lookdev/textures/T_Medusa_H2LD_ORM.png", "Non-Color"),
            "MatID": ("20260929-h2-lookdev/textures/T_Medusa_H2LD_MatID.png", "Non-Color"),
            "EdgeMask": ("20260929-h2-lookdev/textures/T_Medusa_H2LD_Edge.png", "Non-Color"),
            "TeamAccent": ("20260929-h2-lookdev/textures/T_Medusa_H2LD_TeamAccent_4K.png", "Non-Color"),
        },
        "height_m": 0.55,
    },
}


def log(msg):
    print("HPLD " + msg, flush=True)


def args():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return a[0], "--quick" in a


def enable_gpu():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for dev_type in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = dev_type
            prefs.get_devices()
            devs = [d for d in prefs.devices if d.type == dev_type]
            if devs:
                for d in prefs.devices:
                    d.use = d.type == dev_type
                bpy.context.scene.cycles.device = "GPU"
                return dev_type
        except Exception:  # noqa: BLE001 - try the next backend
            continue
    return "CPU"


def append_objects(blend, names=None, prefix=None):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if (names and n in names) or (prefix and n.startswith(prefix))]
    out = []
    for o in dst.objects:
        if o is None:
            continue
        bpy.context.scene.collection.objects.link(o)
        out.append(o)
    return out


def high_arthur(cfg):
    sys.path.insert(0, str(ARTHUR_MOD))
    import bl  # noqa: E402
    import repairs  # noqa: E402
    profile = json.loads((REPO / cfg["profile"]).read_text(encoding="utf-8"))
    high, _ = bl.import_glb_parts(REPO / cfg["tex_glb"], "HP")
    rep = repairs.apply_geometry_repairs(high, profile)
    hf = profile["repairs"]["fill_phantom_holes"]
    pts = np.concatenate([v[:: int(profile["repairs"].get("phantom_points_stride", 1))] for v in repairs.PHANTOM_POINTS.values()])
    holes = {}
    for part in hf["parts"]:
        # the high-poly loops are ~10x longer than the measured low-poly loops (68/106/39/77 edges)
        holes[part] = repairs.fill_phantom_holes(high[part], pts, float(hf["max_dist_m"]), int(hf["max_edges"]) * 12)
    seams = {}
    for sym in profile["repairs"].get("symmetrize", []):
        seams[sym["part"]] = fix_mirror_seam(high[sym["part"]], float(sym["plane_x_m"]))
    log("arthur repairs dropped=%s symmetrized=%s holes=%s seam=%s" % (sorted(rep["dropped"]), sorted(rep["symmetrized"]),
                                                                     {k: len(v) for k, v in holes.items()}, seams))
    return high, {"dropped": sorted(rep["dropped"]), "symmetrized": list(rep["symmetrized"]),
                  "holes": {k: [h.get("edges") for h in v] for k, v in holes.items()}, "mirror_seam": seams}


def fix_mirror_seam(obj, plane_x, snap_m=3e-4, smooth_m=1.5e-3):
    """The H2 symmetrize leaves the high-poly head open along the mirror plane (2026-10-16: 341 boundary edges on the
    plane, 139 on the face - a crack down the middle of the face). Snap the near-plane vertices onto the plane, weld,
    fill the loops that still lie on the plane, dissolve degenerate faces, relax the seam band (the plane vertices only
    in Y/Z) and recompute the normals."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)

    def stats():
        b = [e for e in bm.edges if len(e.link_faces) == 1]
        on = [e for e in b if all(abs(v.co.x - plane_x) < 5e-4 for v in e.verts)]
        return {"boundary": len(b), "boundary_on_plane": len(on),
                "nonmanifold": sum(1 for e in bm.edges if len(e.link_faces) > 2)}

    before = stats()
    near = [v for v in bm.verts if abs(v.co.x - plane_x) < snap_m]
    for v in near:
        v.co.x = plane_x
    bmesh.ops.remove_doubles(bm, verts=near, dist=snap_m)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
    filled = 0
    for _ in range(3):
        b = [e for e in bm.edges if len(e.link_faces) == 1 and all(abs(v.co.x - plane_x) < 5e-4 for v in e.verts)]
        if not b:
            break
        res = bmesh.ops.holes_fill(bm, edges=b, sides=0)
        filled += len(res.get("faces", []))
        if not res.get("faces"):
            bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=b)
    band = [v for v in bm.verts if abs(v.co.x - plane_x) < smooth_m]
    on_plane = [v for v in band if abs(v.co.x - plane_x) < 1e-6]
    off_plane = [v for v in band if abs(v.co.x - plane_x) >= 1e-6]
    for _ in range(3):
        bmesh.ops.smooth_vert(bm, verts=off_plane, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bmesh.ops.smooth_vert(bm, verts=on_plane, factor=0.5, use_axis_x=False, use_axis_y=True, use_axis_z=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    after = stats()
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(obj.data)
    bm.free()
    return {"before": before, "after": after, "fill_faces": filled, "snapped": len(near), "relaxed": len(band)}


def high_medusa(cfg):
    objs = append_objects(REPO / cfg["high_blend"], prefix=cfg["high_prefix"])
    return {o.name[len(cfg["high_prefix"]):]: o for o in objs}, {}


def tidy(obj):
    """Weld at 1e-6 m (the glTF split vertices), drop custom split normals, shade smooth."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    before = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    after = len(bm.verts)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(obj.data)
    bm.free()
    me = obj.data
    if me.has_custom_normals:
        bpy.context.view_layer.objects.active = obj
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj]):
            bpy.ops.mesh.customdata_custom_splitnormals_clear()
    return before - after


def tripo_images(obj):
    """(base colour image, normal image) of the part's glTF material."""
    bc = nm = None
    mat = obj.data.materials[0] if obj.data.materials else None
    if mat and mat.use_nodes:
        for n in mat.node_tree.nodes:
            if n.type != "TEX_IMAGE" or not n.image:
                continue
            linked = [l.to_socket.name for l in n.outputs["Color"].links]
            tgt = [l.to_node.type for l in n.outputs["Color"].links]
            if "NORMAL_MAP" in tgt:
                nm = n.image
            elif "Base Color" in linked:
                bc = n.image
    return bc, nm


def bake_res(obj, quick):
    bc, _ = tripo_images(obj)
    size = max(bc.size) if bc else 1024
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    size = max(size, 2048 if tris > 80000 else 512)
    size = min(size, 4096)
    return max(256, size // 4) if quick else size


def source_material(low_objs):
    mat = bpy.data.materials.new("HPLD_SOURCE")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    tex = nt.nodes.new("ShaderNodeTexImage")
    em = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    for o in low_objs:
        o.data.materials.clear()
        o.data.materials.append(mat)
    return tex


def main():
    hero, quick = args()
    cfg = HEROES[hero]
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    device = enable_gpu()
    out = REPO / cfg["asset"] / "20261016-hp-showcase"
    for sub in ("textures", "export", "reports"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    high, repair = high_arthur(cfg) if hero == "arthur" else high_medusa(cfg)
    base = high.pop(cfg["base_part"], None)
    if base:
        bpy.data.objects.remove(base)
    if hero == "arthur":
        low = [o for o in append_objects(REPO / cfg["low_blend"], prefix="LP_") if o.name not in cfg["low_skip"]]
        for o in [o for o in bpy.data.objects if o.name in cfg["low_skip"]]:
            bpy.data.objects.remove(o)
    else:
        low = append_objects(REPO / cfg["low_blend"], names=cfg["low_names"])
        for o in low:  # the rest pose: no armature deformation, no parenting offset
            for m in list(o.modifiers):
                o.modifiers.remove(m)
            mw = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = mw
    for o in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        bpy.data.objects.remove(o)
    welded = {name: tidy(o) for name, o in high.items()}
    log("%s high parts=%d low=%s device=%s welded=%s" % (hero, len(high), [o.name for o in low], device,
                                                       sum(welded.values())))
    src_tex = source_material(low)
    maps = {}
    for m, (rel, cs) in cfg["maps"].items():
        img = bpy.data.images.load(str(REPO / cfg["asset"] / rel), check_existing=True)
        img.colorspace_settings.name = cs
        maps[m] = img
    h = cfg["height_m"]
    extrusion, ray = 0.0027 * h, 0.0055 * h       # tight pass
    wide_ext, wide_ray = 0.006 * h, 0.012 * h      # fallback for the texels the tight pass missed
    white = bpy.data.images.new("HPLD_WHITE", 4, 4, alpha=False)
    white.pixels.foreach_set([1.0] * (4 * 4 * 4))
    low_by_part = {o.name[3:]: o for o in low if o.name.startswith("LP_tripo_part_")}
    scene.render.bake.margin = 16
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.cage_extrusion = extrusion
    scene.render.bake.max_ray_distance = ray
    scene.render.bake.target = "IMAGE_TEXTURES"
    report = {"hero": hero, "device": device, "repairs": repair, "welded_vertices": welded, "parts": {},
              "cage_extrusion_m": extrusion, "max_ray_m": ray}
    tex_dir = out / "textures"
    for name, obj in high.items():
        res = bake_res(obj, quick)
        bc, nm = tripo_images(obj)
        # the bake target material: one image node per map, swapped per bake
        mat = bpy.data.materials.new("MAT_%s" % name)
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        mat.node_tree.nodes.active = node
        obj.data.materials.clear()
        obj.data.materials.append(mat)
        part = {"res": res, "triangles": sum(len(p.vertices) - 2 for p in obj.data.polygons), "maps": {}}
        sources = [low_by_part[name]] if name in low_by_part else low

        def bake_into(img, ext, ray_d, margin):
            node.image = img
            for o in bpy.data.objects:
                o.select_set(False)
            for o in sources:
                o.select_set(True)
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.bake(type="EMIT", use_selected_to_active=True, cage_extrusion=ext, max_ray_distance=ray_d,
                                margin=margin, use_clear=True)
            a = np.empty(res * res * 4, dtype=np.float32)
            img.pixels.foreach_get(a)
            return a.reshape(res, res, 4)

        # the hit mask of the tight pass (white emission, no margin): 0 = the tight ray found no low-poly surface
        src_tex.image = white
        src_tex.interpolation = "Closest"
        scene.cycles.samples = 1
        mimg = bpy.data.images.new("HPLD_MASK", res, res, alpha=False, float_buffer=False)
        mimg.colorspace_settings.name = "Non-Color"
        hit = bake_into(mimg, extrusion, ray, 0)[..., 0] > 0.5
        bpy.data.images.remove(mimg)
        part["tight_hit_ratio"] = round(float(hit.mean()), 4)
        for m, src in maps.items():
            src_tex.image = src
            src_tex.interpolation = "Closest" if m == "MatID" else "Linear"
            scene.cycles.samples = 1 if m == "MatID" else 4
            img = bpy.data.images.new("T_%s_HP_%s_%s" % (cfg["key"], name, m), res, res, alpha=False, float_buffer=False)
            img.colorspace_settings.name = "sRGB" if m == "BC" else "Non-Color"
            tb = time.time()
            wide = bake_into(img, wide_ext, wide_ray, 16)
            tight = bake_into(img, extrusion, ray, 16)
            out_px = np.where(hit[..., None], tight, wide)
            img.pixels.foreach_set(out_px.ravel())
            img.update()
            path = tex_dir / ("%s.png" % img.name)
            img.filepath_raw = str(path)
            img.file_format = "PNG"
            img.save()
            part["maps"][m] = {"file": path.name, "seconds": round(time.time() - tb, 1)}
            bpy.data.images.remove(img)
        if bc is not None and name in ("tripo_part_6", "tripo_part_1"):  # head / face: the sharper Tripo colour, to compare
            bc.filepath_raw = str(tex_dir / ("T_%s_HP_%s_BC_tripo.png" % (cfg["key"], name)))
            bc.file_format = "PNG"
            bc.save()
            part["maps"]["BC_tripo"] = {"file": Path(bc.filepath_raw).name, "size": list(bc.size)}
        if nm is not None:
            nm.filepath_raw = str(tex_dir / ("T_%s_HP_%s_N_gl.png" % (cfg["key"], name)))
            nm.file_format = "PNG"
            nm.save()
            part["maps"]["N_gl"] = {"file": Path(nm.filepath_raw).name, "size": list(nm.size)}
        report["parts"][name] = part
        log("%s %s res=%d done %.0fs" % (hero, name, res, time.time() - t0))
    # export: the kept parts with one material slot each (MAT_<part>), no low-poly
    for o in bpy.data.objects:
        o.select_set(o.name in {ob.name for ob in high.values()})
    fbx = out / "export" / ("SM_%s_HP_Showcase.fbx" % cfg["key"])
    bpy.ops.export_scene.fbx(filepath=str(fbx), use_selection=True, apply_unit_scale=True, apply_scale_options="FBX_SCALE_UNITS",
                             mesh_smooth_type="FACE", use_mesh_modifiers=False, add_leaf_bones=False, bake_anim=False,
                             path_mode="STRIP")
    report["export"] = fbx.name
    report["seconds"] = round(time.time() - t0, 1)
    (out / "reports" / "hp-lookdev-bake.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    log("%s done %.0fs -> %s" % (hero, time.time() - t0, fbx))


if __name__ == "__main__":
    main()
