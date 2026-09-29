"""Stages `ld_render_before` / `ld_render_after` (headless Blender, EEVEE): measurement frames of the look-dev.

blender -b --factory-startup --python-exit-code 1 --python lookdev_render.py -- <lookdev profile.json> before|after

The look-dev FBX pair is imported and turned back to the authored frame (face -Y), as the H2.1 preview/compare
stages. Cameras: ortho front / right / back with the framing of the H2.1 compare stage (concept %). Light: the H2.1
preview "studio" (three suns + near-black world, view transform Standard) - Blender, not the game light.
  before  lit frames with the H2.1 2K runtime textures (BC, ORM, N) + a zone-ID pass of the same camera (emission
          of work/lookdev/T_Zone_4K.png, Closest filter, 1 sample, filter size 0, view transform Raw)
          -> work/lookdev/render/<view>_lit_before.png, <view>_zone.png
  after   lit frames with the look-dev textures (<prefix>_BC/ORM/N_2K) -> <view>_lit_after.png;
          review frames: MatID classes (emission, Closest) front, UV1 checker (2 cm squares on UV1_m) front and a staff
          close-up -> preview/ld_render_*.png; LUT read-back: the EXR written by ld_tone loaded by Blender's own EXR
          decoder and compared with the float16 values of the LUT JSON -> reports/ld-render-after-report.json
The PBR here is Principled BSDF (no Cloth, no detail tiles, no LUT): it shows the BC / ORM change only; the v2
shader is a UE decision of the next wave.
"""

import sys
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402
import stage_preview as SP  # noqa: E402  (helpers only)

B.require_background("lookdev_render.py")

VIEWS = ("front", "right", "back")


def emission_material(name, image_path, colourise=None):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(image_path), check_existing=True)
    tex.image.colorspace_settings.name = "Non-Color"
    tex.interpolation = "Closest"
    src = tex.outputs["Color"]
    if colourise is not None:
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.interpolation = "CONSTANT"
        els = ramp.color_ramp.elements
        els[0].position = 0.0
        els[0].color = (0, 0, 0, 1)
        els[1].position = 1.0
        els[1].color = (1, 1, 1, 1)
        for idx, col in sorted(colourise.items()):
            e = els.new((idx * 16 + 4) / 255.0)
            e.color = tuple(col) + (1.0,)
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(src, sep.inputs["Color"])
        nt.links.new(sep.outputs["Red"], ramp.inputs["Fac"])
        src = ramp.outputs["Color"]
    nt.links.new(src, em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    return mat


def checker_material(name, uv_name, square_m):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = uv_name
    chk = nt.nodes.new("ShaderNodeTexChecker")
    chk.inputs["Scale"].default_value = 1.0 / square_m  # one square = 1 / Scale UV units = square_m metres on UV1_m
    chk.inputs["Color1"].default_value = (0.8, 0.8, 0.8, 1)
    chk.inputs["Color2"].default_value = (0.08, 0.08, 0.1, 1)
    nt.links.new(uvn.outputs["UV"], chk.inputs["Vector"])
    nt.links.new(chk.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.7
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    return mat


def main():
    args = B.script_args()
    prof = C.Profile(args[0])
    mode = args[1]
    ld = prof["lookdev"]
    src = C.Profile(C.repo_path(ld["source_profile"]))
    B.empty_file()
    scene = bpy.context.scene
    cam, _lights = SP.setup_scene(scene)
    col = bpy.data.collections.new("LD")
    scene.collection.children.link(col)
    objs = (SP.import_fbx_authored(prof.export / ld["exports"]["skeletal_fbx"], col)
            + SP.import_fbx_authored(prof.export / ld["exports"]["base_fbx"], col))
    meshes = [o for o in objs if o.type == "MESH"]
    out = prof.work / "lookdev" / "render"
    out.mkdir(parents=True, exist_ok=True)
    rcfg = ld["render"]
    res = tuple(rcfg["ortho_resolution"])
    zt = float(np.concatenate([B.verts_np(o) for o in meshes])[:, 2].max())
    frames = {}
    inputs = {}

    def set_views(raw):
        scene.view_settings.view_transform = "Raw" if raw else "Standard"
        scene.view_settings.look = "None"

    def shoot(path, resolution, rgba=False):
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA" if rgba else "RGB"
        scene.render.image_settings.color_depth = "8"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        C.strip_png_metadata(path)
        frames[C.rel(path)] = C.sha256(path)

    def frame_view(view):
        top_frac, bottom_frac = rcfg["framing"][view]
        scale = zt / (bottom_frac - top_frac)
        SP.ortho(cam, view, (0.0, 0.0, zt + top_frac * scale - 0.5 * scale), scale)

    def lit(tag, prefix, tdir):
        bc, orm, n = (tdir / ("%s_%s_2K.png" % (prefix, k)) for k in ("BC", "ORM", "N"))
        for k, p in (("BC", bc), ("ORM", orm), ("N", n)):
            inputs["%s_%s" % (tag, k)] = {"path": C.rel(p), "sha256": C.sha256(p)}
        SP.assign(meshes, SP.pbr_material("LD_" + tag, bc, orm, n, True))
        set_views(False)
        scene.render.film_transparent = False
        for view in VIEWS:
            frame_view(view)
            shoot(out / ("%s_lit_%s.png" % (view, tag)), res)

    report = {"stage": "ld_render_" + mode, "profile": C.rel(prof.path), "profile_id": prof["profile_id"],
              "renderer": scene.render.engine, "blender": bpy.app.version_string, "light": "H2.1 preview studio (3 suns, near-black world)",
              "views": list(VIEWS), "framing": rcfg["framing"], "resolution": list(res)}
    checks = {}
    if mode == "before":
        lit("before", src["maps"]["prefix"], src.textures)
        zone_tex = prof.work / "lookdev" / "T_Zone_4K.png"
        inputs["zone"] = {"path": C.rel(zone_tex), "sha256": C.sha256(zone_tex)}
        SP.assign(meshes, emission_material("LD_zone", zone_tex))
        set_views(True)
        scene.render.film_transparent = True
        filt = scene.render.filter_size
        scene.render.filter_size = 0.0
        samples = scene.eevee.taa_render_samples
        scene.eevee.taa_render_samples = 1
        for view in VIEWS:
            frame_view(view)
            shoot(out / ("%s_zone.png" % view), res, rgba=True)
        scene.render.filter_size = filt
        scene.eevee.taa_render_samples = samples
    else:
        lit("after", ld["prefix"], prof.textures)
        # MatID classes, front
        import lookdev_lut as LL  # noqa: E402  (numpy only)
        mpx = int(ld["matid_px"])
        matid = prof.textures / ("%s_MatID_%dK.png" % (ld["prefix"], mpx // 1024))
        SP.assign(meshes, emission_material("LD_matid", matid, {k: v for k, v in LL.CLASS_COLOURS.items()}))
        set_views(False)
        scene.render.film_transparent = False
        frame_view("front")
        shoot(prof.preview / "ld_render_matid_front.png", res)
        # UV1 checker: front + staff close-up (right)
        SP.assign(meshes, checker_material("LD_uv1", ld["uv1"]["layer_name"], 0.01))
        # SP.assign renames uv_layers[0] only; the checker reads the second layer by name
        for view in ("front",):
            frame_view(view)
            shoot(prof.preview / "ld_render_uv1_checker_front.png", res)
        arm = next(o for o in objs if o.type == "ARMATURE")
        hb = arm.matrix_world @ arm.data.bones["weapon.R"].head_local
        tb = arm.matrix_world @ arm.data.bones["weapon.R"].tail_local
        SP.ortho(cam, "front", hb * 0.35 + tb * 0.65, 0.12)  # upper shaft + claw, in front of nothing
        shoot(prof.preview / "ld_render_uv1_checker_staff.png", (800, 800))
        # LUT read-back through Blender's EXR decoder
        lut_exr = prof.textures / ("%s_MatLUT.exr" % ld["prefix"])
        lut_json = C.load_json(prof.reports / "ld-lut.json")
        img = bpy.data.images.load(str(lut_exr))
        img.colorspace_settings.name = "Non-Color"
        w, h = img.size
        px = np.array(img.pixels[:], np.float32).reshape(h, w, 4)[::-1]  # Blender rows bottom-up -> row 0 = top
        ref = np.array(lut_json["half_values_rows_top_to_bottom"], np.float32)
        d = float(np.abs(px - ref).max())
        C.check(checks, "lut_exr_blender_readback", (w, h) == (16, 8) and d == 0.0,
                {"size": [w, h], "max_abs_diff": d, "file_format": img.file_format}, {"size": [16, 8], "max_abs_diff": 0.0})
        inputs["lut_exr"] = {"path": C.rel(lut_exr), "sha256": C.sha256(lut_exr)}
    report.update({"inputs": inputs, "frames_sha256": frames, "checks": checks, "passed": all(c["passed"] for c in checks.values())})
    C.write_json(prof.reports / ("ld-render-%s-report.json" % mode), report)
    print("H2_STAGE_OK ld_render_%s passed=%s" % (mode, report["passed"]))
    if not report["passed"]:
        raise RuntimeError("ld_render checks failed: %s" % sorted(k for k, c in checks.items() if not c["passed"]))


main()
