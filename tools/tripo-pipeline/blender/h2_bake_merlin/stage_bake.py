"""Stage `bake` (headless Blender, Cycles): high-poly -> 4K atlas, per part.

blender -b --factory-startup --python-exit-code 1 --python stage_bake.py -- <profile.json>

For every part k of every low-poly object: a temporary object with only the faces of part k (corner normals of
the whole object kept as custom normals, so the tangent frame is the exported one) is baked selected-to-active
from the high-poly part k plus the high-poly parts that share a seam with it inside the same object. All
high-poly parts stay renderable (occluders for AO); the low-poly objects are hidden or invisible to rays.
Maps (float, into one shared 4K image each, margin 0, no clear -> each part writes only its own texels):
  normal     tangent space, OpenGL (+Y), from the high-poly geometry (the Tripo normal map is unlinked unless
             bake.maps.normal.highpoly_normal_map)
  ao         Cycles AO, distance = distance_rel x figure height (source metres)
  basecolor  emission of the Tripo baseColorTexture (linear light in the float image)
  roughness  emission of metallicRoughnessTexture.G
  metallic   emission of metallicRoughnessTexture.B
Cage per part: extrusion = max(cage_extrusion_min_m, factor x measured high->low p99.9) and max ray =
max(factor x extrusion, extrusion + 1.2 x low->high max) (retopo report). Output: work/bake/<map>.npy (float16
RGBA, row 0 = bottom as Blender stores it), reports/bake-report.json (no times; timings in logs/).
"""

import json
import sys
import time
from pathlib import Path

import bmesh
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402

B.require_background("stage_bake.py")

MAPS = ("normal", "ao", "basecolor", "roughness", "metallic")


def part_object(src, pk, image_mat):
    """Copy of src with only the faces of part pk; corner normals of the full object kept as custom normals."""
    me = src.data
    corner_n = np.empty(len(me.loops) * 3, np.float32)
    me.corner_normals.foreach_get("vector", corner_n)
    corner_n = corner_n.reshape(-1, 3)
    part_of = B.int_face_attr(me, "um_part")
    ls = B.poly_array(me, "loop_start", np.int64)
    lt = B.poly_array(me, "loop_total", np.int64)
    keep = np.nonzero(part_of == pk)[0]
    tmp = src.copy()
    tmp.data = me.copy()
    tmp.name = "BAKE_%s_p%d" % (src.name, pk)
    tmp.hide_render = False
    for m in list(tmp.modifiers):
        tmp.modifiers.remove(m)
    bpy.context.scene.collection.objects.link(tmp)
    B.set_int_face_attr(tmp.data, "um_orig_face", np.arange(len(me.polygons)))
    bm = bmesh.new()
    bm.from_mesh(tmp.data)
    bm.faces.ensure_lookup_table()
    keep_set = set(keep.tolist())
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep_set], context="FACES")
    bm.to_mesh(tmp.data)
    bm.free()
    tme = tmp.data
    orig = B.int_face_attr(tme, "um_orig_face")
    tls = B.poly_array(tme, "loop_start", np.int64)
    tlt = B.poly_array(tme, "loop_total", np.int64)
    normals = np.zeros((len(tme.loops), 3), np.float32)
    for j, o in enumerate(orig):
        if tlt[j] != lt[o]:
            raise RuntimeError("corner count changed")
        normals[tls[j]:tls[j] + tlt[j]] = corner_n[ls[o]:ls[o] + lt[o]]
    tme.normals_split_custom_set(normals.tolist())
    tme.materials.clear()
    tme.materials.append(image_mat)
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(tmp, attr, False)
    return tmp


def hp_node_setup(mat):
    """Nodes of a glTF-imported high-poly material: principled, output, images by kind."""
    nt = mat.node_tree
    out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    imgs = {}
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            imgs[n.image.name.rsplit("_", 1)[1].split(".")[0]] = n
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.0
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(imgs["rm"].outputs["Color"], sep.inputs["Color"])
    for n in imgs.values():
        n.interpolation = "Linear"
    return {"nt": nt, "out": out, "bsdf": bsdf, "imgs": imgs, "emit": emit, "sep": sep,
            "normal_link": [l for l in nt.links if l.to_socket == bsdf.inputs["Normal"]]}


def hp_mode(setup, mode, use_normal_map):
    nt, out, bsdf, emit, sep, imgs = setup["nt"], setup["out"], setup["bsdf"], setup["emit"], setup["sep"], setup["imgs"]
    for l in list(out.inputs["Surface"].links):
        nt.links.remove(l)
    for l in list(emit.inputs["Color"].links):
        nt.links.remove(l)
    for l in list(bsdf.inputs["Normal"].links):
        nt.links.remove(l)
    if mode in ("normal", "ao"):
        nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
        if mode == "normal" and use_normal_map:
            nm = next(n for n in nt.nodes if n.type == "NORMAL_MAP")
            nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        return
    nt.links.new(emit.outputs[0], out.inputs["Surface"])
    if mode == "basecolor":
        nt.links.new(imgs["basecolor"].outputs["Color"], emit.inputs["Color"])
    elif mode == "roughness":
        nt.links.new(sep.outputs["Green"], emit.inputs["Color"])
    elif mode == "metallic":
        nt.links.new(sep.outputs["Blue"], emit.inputs["Color"])


def main():
    prof = C.Profile(B.script_args()[0])
    for st in ("retopo", "uv"):
        if not C.load_json(prof.reports / ("%s-report.json" % st))["passed"]:
            raise RuntimeError("%s stage did not pass" % st)
    src_rep = C.load_json(prof.reports / "source-report.json")
    retopo = C.load_json(prof.reports / "retopo-report.json")
    B.open_blend(prof.work / "h2-uv.blend")
    scene = bpy.context.scene
    bcfg = prof["bake"]
    size = int(prof["uv"]["atlas_px"])
    device = B.setup_cycles(scene, 16, bcfg["seed"], device_mode=bcfg["device"])
    scene.render.bake.use_selected_to_active = True
    scene.render.bake.margin = 0
    scene.render.bake.use_clear = False
    scene.render.bake.target = "IMAGE_TEXTURES"
    scene.render.bake.normal_space = "TANGENT"
    scene.render.bake.normal_r, scene.render.bake.normal_g, scene.render.bake.normal_b = "POS_X", "POS_Y", "POS_Z"
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    hp = {o.name[3:]: o for o in bpy.data.objects if o.name.startswith("HP_")}
    lps = {k: bpy.data.objects["LP_" + k] for k in ("body", "staff", "base")}
    for o in lps.values():
        o.hide_render = True
    zmin = min(B.verts_np(o)[:, 2].min() for o in hp.values())
    zmax = max(B.verts_np(o)[:, 2].max() for o in hp.values())
    ao_dist = float(bcfg["maps"]["ao"]["distance_rel"]) * (zmax - zmin)
    scene.world.light_settings.distance = ao_dist
    setups = {pn: hp_node_setup(o.material_slots[0].material) for pn, o in hp.items()}
    # seam neighbours inside the same object
    neighbours = {pn: set() for pn in prof["parts"]}
    for s in src_rep["seams"]:
        for other in s["shared_with"]:
            if prof["parts"][other]["object"] == prof["parts"][s["part"]]["object"]:
                neighbours[s["part"]].add(other)
    images = {}
    mats = {}
    for mp in MAPS:
        img = bpy.data.images.new("BAKE_" + mp, size, size, alpha=True, float_buffer=True)
        img.colorspace_settings.name = "Non-Color"
        img.pixels.foreach_set(np.zeros(size * size * 4, np.float32))
        images[mp] = img
        mat = bpy.data.materials.new("BAKE_MAT_" + mp)
        mat.use_nodes = True
        nt = mat.node_tree
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        nt.nodes.active = tex
        mats[mp] = mat
    cages = {}
    per_part = {}
    timings = {}
    for key in ("body", "staff", "base"):
        dev = retopo["objects"][key]["deviation_mm_source"]
        for pn in prof["objects"][key]["parts"]:
            d = dev[pn]
            e = max(float(bcfg["cage_extrusion_min_m"]), float(bcfg["cage_extrusion_factor"]) * d["high_to_low"]["p999_mm"] / 1000.0)
            ray = max(float(bcfg["max_ray_distance_factor"]) * e, e + 1.2 * d["low_to_high_any_part"]["max_mm"] / 1000.0)
            sel = sorted({pn} | neighbours[pn], key=C.part_index)
            cages[pn] = {"extrusion_m": C.r(e, 6), "max_ray_distance_m": C.r(ray, 6), "high_poly_parts": sel}
    for mp in MAPS:
        mcfg = bcfg["maps"][mp]
        scene.cycles.samples = int(mcfg["samples"])
        for pn, st in setups.items():
            hp_mode(st, mp, bool(mcfg.get("highpoly_normal_map", False)))
        t_map = time.time()
        for key in ("body", "staff", "base"):
            for pn in prof["objects"][key]["parts"]:
                low = part_object(lps[key], C.part_index(pn), mats[mp])
                B.select_only([low] + [hp[q] for q in cages[pn]["high_poly_parts"]], active=low)
                with B.ctx([low] + [hp[q] for q in cages[pn]["high_poly_parts"]], active=low):
                    bpy.ops.object.bake(type=mcfg["type"], use_selected_to_active=True,
                                        cage_extrusion=cages[pn]["extrusion_m"],
                                        max_ray_distance=cages[pn]["max_ray_distance_m"], margin=0, use_clear=False,
                                        normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z",
                                        target="IMAGE_TEXTURES")
                bpy.data.objects.remove(low)
        timings[mp] = round(time.time() - t_map, 1)
        print("baked", mp, timings[mp], flush=True)
    out_dir = prof.work / "bake"
    out_dir.mkdir(parents=True, exist_ok=True)
    stats = {}
    for mp, img in images.items():
        a = np.empty(size * size * 4, np.float32)
        img.pixels.foreach_get(a)
        a = a.reshape(size, size, 4)
        np.save(out_dir / (mp + ".npy"), a.astype(np.float16))
        cov = a[..., 3] > 0.5
        stats[mp] = {"texels_written": int(cov.sum()), "mean_rgb_written": C.rv(a[cov][:, :3].mean(0), 5) if cov.any() else None}
    (prof.run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (prof.run_dir / "logs" / "bake-timings.json").write_text(json.dumps({"seconds_per_map": timings, "device": device}, indent=1))
    report = {"stage": "bake", "profile": C.rel(prof.path), "profile_id": prof["profile_id"],
              "blender": bpy.app.version_string, "device": device["device"], "compute_device_type": device["compute_device_type"],
              "atlas_px": size, "ao_distance_m_source": C.r(ao_dist, 6), "figure_height_m_source": C.r(zmax - zmin, 5),
              "cages": cages, "maps": {mp: dict(bcfg["maps"][mp]) for mp in MAPS}, "written": stats,
              "note": "misses (texels inside UV triangles that no ray matched) are measured by the maps stage against the rasterised atlas"}
    C.write_json(prof.reports / "bake-report.json", report)
    print("H2_STAGE_OK bake device=%s" % device)


main()
