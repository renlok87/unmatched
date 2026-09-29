"""Stage bake: Cycles selected-to-active, one part at a time — only the part's own textured high-poly (HPT_<part>)
is a ray target of its low-poly (LP_<part>), so interpenetrating parts never steal each other's texels; the whole
high-poly figure stays renderable and occludes the AO rays; low-poly objects are invisible to rays.

Passes (margin 0 — padding is done by the textures stage on the composite, so a part's margin can never
overwrite a neighbour's island):
  NORMAL  tangent space, OpenGL swizzle (+X +Y +Z), shading normal of the high-poly incl. the Tripo normal map
  AO      Cycles AO (profile samples/distance), whole high-poly as occluder
  BC      emission pass-through of the Tripo BaseColor map (image read as Non-Color: raw sRGB-encoded values)
  RM      emission pass-through of the Tripo metallicRoughness map (G roughness, B metallic; Non-Color)
  HIT     white emission: texels whose cage ray hit the high-poly
Accumulated composites go to work/bake/<pass>.npy (float32 RGB, row 0 = v 0) with work/bake/<pass>_alpha.npy.
Cap texels (work/uv/cap_ids.npy: contact caps and base-top caps of the close stage) have no high-poly surface behind
them: they are baked like the rest but overwritten by the textures stage (rim transfer), so the cage-miss check counts
only the non-cap texels of a part and reports the cap texels separately."""

import json
import time
from pathlib import Path

import bpy
import numpy as np

from . import bl_util as U

RAY_FLAGS = ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission", "visible_volume_scatter",
             "visible_shadow")


def pbr_nodes(mat):
    """(basecolor image node, metallicRoughness image node, normal image node, principled) of a glTF material."""
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bc = rm = nrm = None
    for link in nt.links:
        if link.to_node == bsdf and link.to_socket.name == "Base Color" and link.from_node.type == "TEX_IMAGE":
            bc = link.from_node
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            name = n.image.name.lower()
            if name.endswith("_rm.png") or "_rm" in name:
                rm = n
            elif "normal" in name:
                nrm = n
            elif bc is None and "basecolor" in name:
                bc = n
    return bc, rm, nrm, bsdf


def emission_material(name, image=None, uv_map="UVMap", colour=(1.0, 1.0, 1.0, 1.0)):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 1.0
    em.inputs["Color"].default_value = colour
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        uvn = nt.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = uv_map
        nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], em.inputs["Color"])
    return mat


def cage_for(part_report, cfg):
    dev = part_report["deviation"]
    mm = max(dev["lo_to_hi_mm"]["p99"], dev["hi_to_lo_mm"]["p99"]) * float(cfg["factor"])
    e = min(max(mm / 1000.0, float(cfg["min_m"])), float(cfg["max_m"]))
    return e, e * float(cfg["max_ray_factor"])


def run(params, profile):
    run_dir = Path(params["run_dir"])
    retopo = json.loads((run_dir / "reports" / "retopo-report.json").read_text(encoding="utf-8"))
    bcfg = profile["bake"]
    size = int(bcfg["resolution"])
    names = sorted(profile["parts"], key=U.part_key)
    bpy.ops.wm.open_mainfile(filepath=str(run_dir / "work" / "hp.blend"))
    scene = bpy.context.scene
    for obj in [o for o in bpy.data.objects if o.name.startswith("HPG_")]:
        bpy.data.objects.remove(obj)
    with bpy.data.libraries.load(str(run_dir / "work" / "lp_uv.blend"), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("LP_")]
    lp_col = bpy.data.collections.new("LP")
    scene.collection.children.link(lp_col)
    for obj in dst.objects:
        lp_col.objects.link(obj)
        for flag in RAY_FLAGS:
            setattr(obj, flag, False)
    device = U.setup_cycles(scene, bcfg.get("device", "GPU"), samples=1, seed=int(bcfg["ao"].get("seed", 0)))
    world = bpy.data.worlds.new("h2_bake_world")
    scene.world = world
    world.light_settings.distance = float(bcfg["ao"]["distance_m"])
    # target image + one LP material for every part
    target = bpy.data.images.new("H2_BAKE_TARGET", size, size, alpha=True, float_buffer=True)
    target.colorspace_settings.name = "Non-Color"
    lp_mat = bpy.data.materials.new("H2_BAKE_LP")
    lp_mat.use_nodes = True
    tex = lp_mat.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = target
    lp_mat.node_tree.nodes.active = tex
    for obj in dst.objects:
        obj.data.materials.clear()
        obj.data.materials.append(lp_mat)
    # high-poly material variants
    variants = {}
    white = emission_material("H2_HIT_WHITE")
    for n in names:
        hp = bpy.data.objects["HPT_" + n]
        pbr = hp.data.materials[0]
        bc, rm, nrm, bsdf = pbr_nodes(pbr)
        for node in (bc, rm, nrm):
            if node is None:
                raise RuntimeError("HPT_%s: glTF material without BC/RM/N image" % n)
            node.image.colorspace_settings.name = "Non-Color" if node is not bc else node.image.colorspace_settings.name
        if not bcfg["normal"].get("include_tripo_normal_map", True):
            for link in list(pbr.node_tree.links):
                if link.to_node == bsdf and link.to_socket.name == "Normal":
                    pbr.node_tree.links.remove(link)
        bc_raw = bc.image.copy()
        bc_raw.colorspace_settings.name = "Non-Color"
        variants[n] = {"pbr": pbr, "BC": emission_material("H2_EMIT_BC_" + n, bc_raw),
                       "RM": emission_material("H2_EMIT_RM_" + n, rm.image), "HIT": white,
                       "images": {"BC": [bc.image.name, list(bc.image.size)], "RM": [rm.image.name, list(rm.image.size)],
                                  "N": [nrm.image.name, list(nrm.image.size)]}}
    passes = [("NORMAL", "NORMAL", int(bcfg["normal"]["samples"])), ("AO", "AO", int(bcfg["ao"]["samples"])),
              ("BC", "EMIT", int(bcfg["emission"]["samples"])), ("RM", "EMIT", int(bcfg["emission"]["samples"])),
              ("HIT", "EMIT", 1)]
    out_dir = run_dir / "work" / "bake"
    out_dir.mkdir(parents=True, exist_ok=True)
    part_ids = np.load(run_dir / "work" / "uv" / "part_ids.npy")
    cap_path = run_dir / "work" / "uv" / "cap_ids.npy"
    cap_mask = np.load(cap_path) > 0 if cap_path.exists() else np.zeros_like(part_ids, bool)
    zeros = np.zeros(size * size * 4, np.float32)
    stats = {n: {} for n in names}
    timing = {}
    for key, kind, samples in passes:
        scene.cycles.samples = samples
        acc = np.zeros((size, size, 3), np.float32)
        alpha_acc = np.zeros((size, size), np.uint8)
        t_pass = time.time()
        for pi, n in enumerate(names):
            hp = bpy.data.objects["HPT_" + n]
            lp = bpy.data.objects["LP_" + n]
            hp.data.materials[0] = variants[n]["pbr"] if key in ("NORMAL", "AO") else variants[n][key]
            e, dmax = cage_for(retopo["parts"][n], bcfg["cage"])
            target.pixels.foreach_set(zeros)
            bpy.ops.object.select_all(action="DESELECT")
            hp.select_set(True)
            lp.select_set(True)
            bpy.context.view_layer.objects.active = lp
            kwargs = dict(type=kind, use_selected_to_active=True, cage_extrusion=e, max_ray_distance=dmax, margin=0,
                          use_clear=False, target="IMAGE_TEXTURES", save_mode="INTERNAL")
            if kind == "NORMAL":
                kwargs.update(normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z")
            bpy.ops.object.bake(**kwargs)
            px = U.image_to_array(target)
            baked = px[..., 3] > 0.5
            mine = part_ids == pi
            take = baked & mine
            acc[take] = px[..., :3][take]
            alpha_acc[take] = 1
            s = stats[n].setdefault(key, {})
            s.update({"baked_texels": int(take.sum()), "outside_own_islands": int((baked & ~mine).sum()),
                      "cage_extrusion_m": U.r(e, 6), "max_ray_distance_m": U.r(dmax, 6)})
            if key == "HIT":
                real = mine & ~cap_mask
                hit = take & real & (px[..., 0] > 0.5)
                s["uv_texels"] = int(real.sum())
                s["cap_texels"] = int((mine & cap_mask).sum())
                s["hit_texels"] = int(hit.sum())
                s["miss_share_of_uv_texels"] = U.r(1.0 - hit.sum() / max(real.sum(), 1), 6)
            hp.data.materials[0] = variants[n]["pbr"]
        np.save(out_dir / ("%s.npy" % key), acc)
        np.save(out_dir / ("%s_alpha.npy" % key), alpha_acc)
        timing[key] = U.r(time.time() - t_pass, 2)
        print("H2_BAKE_PASS", key, timing[key], flush=True)
    miss = {n: stats[n]["HIT"]["miss_share_of_uv_texels"] for n in names}
    checks = {
        "texels_outside_own_islands_share": {
            "passed": all(stats[n][k]["outside_own_islands"] <= 1e-3 * max(stats[n][k]["baked_texels"], 1) for n in names for k in stats[n]),
            "measured": {n: max(stats[n][k]["outside_own_islands"] for k in stats[n]) for n in names},
            "expected": "<= 0.1 % of the part's baked texels",
            "note": "edge texels Cycles covered but the UV raster (pixel centres) did not; dropped from the composite, "
                    "refilled by the textures stage dilation"},
        "cage_miss_share": {"passed": all(v <= float(bcfg["hit_check"]["max_miss_share_warn"]) for v in miss.values()),
                            "measured": miss, "expected": "<= %s per part" % bcfg["hit_check"]["max_miss_share_warn"],
                            "note": "non-cap UV texels whose cage ray found no high-poly (filled by dilation from neighbours); "
                                    "cap texels (parts.<part>.HIT.cap_texels) are filled from their rim by the textures stage"},
    }
    report = {"stage": "bake", "device": device, "resolution": size, "passes": [p[0] for p in passes],
              "samples": {p[0]: p[2] for p in passes}, "ao_distance_m": bcfg["ao"]["distance_m"],
              "normal": {"space": "TANGENT", "swizzle": "POS_X POS_Y POS_Z (OpenGL)",
                         "includes_tripo_normal_map": bool(bcfg["normal"].get("include_tripo_normal_map", True))},
              "source_images": {n: variants[n]["images"] for n in names}, "parts": stats,
              "checks": checks, "passed": all(c["passed"] for c in checks.values()), "status": "измерено",
              "note": "per-part bakes, margin 0; high-poly = the textured Tripo twin (identical geometry, prepare stage)"}
    U.write_json(run_dir / "reports" / "bake-report.json", report)
    U.write_json(run_dir / "work" / "bake" / "timing.json", timing)  # not a report: wall time is not reproducible
