"""Stage preview: Cycles frames (label "blender"; studio light, not the game light) of
  H2  the game model (work/sk_authored.blend) with the baked 4K PBR set (BC sRGB, N OpenGL, ORM: G roughness,
      B metallic; AO is not fed to Principled — Cycles computes its own occlusion),
  HP  the Tripo high-poly with its own 8K/PBR maps (reference: what the bake had to transfer),
  PREV the current game candidate (profile preview.previous_candidate, UM_FBX_v1 FBX turned back to the authored
      frame) with its 2K atlas.
Shots: orthographic front/side/back framed exactly like the H2 concepts (1021 x 1540, base centred at x 45 %,
snakes at y 2 %, base bottom at y 96.8 % — prompts.md), close-ups (profile preview.closeups), and the game camera K2
(FOV 35 deg horizontal, pitch -55 deg, distances of the P1.7 control scene, 1920 x 1080, game scale) with a
silhouette pass (alpha) for the K2 pixel measurements. Raw PNGs go to work/preview_raw; the driver composes the
side-by-side sheets (compose.py).
preview.backface_culling (verify 2026-09-29): the H2 and previous-candidate materials pass back faces through
(Geometry.Backfacing -> Transparent BSDF), like UE one-sided materials, so an opening shows as see-through in the
frames too; the Tripo high-poly keeps its own two-sided glTF material (reference).
preview.baseline (H2.1, 2026-09-29): a second texture set of the SAME game model (the H2 textures before the material
pass, a local copy pinned by sha256 in the profile) is rendered with the same code, light and cameras as set BASE
(ortho front/side/back, close-ups, K2), so the compose stage can put concept | H2 | H2.1 side by side.
preview.pose_closeups: Cycles close-ups in a probe pose (st_seams.pose, e.g. arm_r_raise: the fist lifted off the
belt) of H2 (current textures) and BASE, plus the AO channel of each ORM shown as emission (Standard view) - the
material AO that UE applies to indirect light; Cycles itself does not read ORM.R.
preview.channel_views: ortho views of one ORM channel (e.g. Blue = metallic) of H2 and BASE, emission, Standard."""

import hashlib
import json
import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import bl_util as U

RAW = "preview_raw"


def pbr_material(name, bc, n_gl, orm, cull_backfaces=False):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"

    def tex(path, colour):
        img = bpy.data.images.load(str(path), check_existing=True)
        img.colorspace_settings.name = "sRGB" if colour else "Non-Color"
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        nt.links.new(uv.outputs["UV"], node.inputs["Vector"])
        return node

    t_bc, t_n, t_orm = tex(bc, True), tex(n_gl, False), tex(orm, False)
    nt.links.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t_orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nm = nt.nodes.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nt.links.new(t_n.outputs["Color"], nm.inputs["Color"])
    nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    if cull_backfaces:
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        clear = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
        nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
        nt.links.new(clear.outputs["BSDF"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def ao_material(name, orm, channel="Red"):
    """Emission of one ORM channel (Red = the baked AO, Blue = metallic), shown with the Standard view transform:
    1.0 = white."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    em = nt.nodes.new("ShaderNodeEmission")
    img = bpy.data.images.load(str(orm), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    uv = nt.nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(tex.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs[channel], em.inputs["Color"])
    nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
    return mat


def collection(scene, name, objs):
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    for o in objs:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
    return col


def show_only(cols, visible):
    for name, col in cols.items():
        col.hide_render = name not in visible


def look_at(cam, target, direction, distance):
    d = Vector(direction).normalized()
    cam.location = Vector(target) + d * distance
    cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()


def area_light(scene, name, loc, energy, size, target=(0, 0, 0.3)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = energy
    ld.size = size
    o = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return o


def run(params, profile):
    run_dir = Path(params["run_dir"])
    repo = Path(params["repo_root"])
    pcfg = profile["preview"]
    raw = run_dir / "work" / RAW
    raw.mkdir(parents=True, exist_ok=True)
    scene = U.reset()
    device = U.setup_cycles(scene, "GPU", samples=int(pcfg["samples"]), seed=0)
    scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "None"
    world = bpy.data.worlds.new("preview_world")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.045, 0.045, 0.05, 1.0)
    bg.inputs[1].default_value = 1.0
    area_light(scene, "key", (-1.5, -2.0, 2.0), 250, 1.5)
    area_light(scene, "fill", (2.0, -1.5, 1.0), 90, 2.0)
    area_light(scene, "rim", (0.5, 2.5, 2.2), 160, 1.5)
    cols = {}
    # ---- H2 game model
    with bpy.data.libraries.load(str(run_dir / "work" / "sk_authored.blend"), link=False) as (src, dst):
        dst.objects = [n for n in src.objects if n in (profile["rig"]["armature_object"], profile["meshes"]["body"],
                                                       profile["meshes"]["weapon"], profile["meshes"]["base"])]
    prefix = profile["textures"]["prefix"]
    tdir = run_dir / "textures"
    cull = bool(pcfg.get("backface_culling", False))
    h2_mat = pbr_material("PREVIEW_H2", tdir / ("%s_BC.png" % prefix), tdir / ("%s_N_OpenGL.png" % prefix),
                          tdir / ("%s_ORM.png" % prefix), cull)
    for o in dst.objects:
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(h2_mat)
    cols["H2"] = collection(scene, "H2", dst.objects)
    h2_meshes = [o for o in dst.objects if o.type == "MESH"]
    h2_arm = next(o for o in dst.objects if o.type == "ARMATURE")
    mats = {"H2": h2_mat}
    base = pcfg.get("baseline")
    baseline_report = None
    if base:
        bdir = run_dir / base["textures_dir"]
        files = {k: bdir / ("%s_%s.png" % (base["prefix"], k)) for k in ("BC", "N_OpenGL", "ORM")}
        got = {k: hashlib.sha256(f.read_bytes()).hexdigest() for k, f in files.items()}
        bad = [k for k in files if got[k] != base["sha256"][k]]
        if bad:
            raise RuntimeError("preview.baseline: sha256 mismatch for %s (expected the pinned H2 textures)" % bad)
        mats["BASE"] = pbr_material("PREVIEW_BASE", files["BC"], files["N_OpenGL"], files["ORM"], cull)
        baseline_report = {"textures_dir": base["textures_dir"], "sha256": got, "label": base["label"]}

    def use_material(tag):
        for o in h2_meshes:
            o.data.materials.clear()
            o.data.materials.append(mats[tag])
    # ---- Tripo high-poly (textured twin) in the same final frame
    with bpy.data.libraries.load(str(run_dir / "work" / "hp.blend"), link=False) as (src, dst2):
        dst2.objects = [n for n in src.objects if n.startswith("HPT_")]
    cols["HP"] = collection(scene, "HP", dst2.objects)
    # ---- previous candidate
    prev = pcfg["previous_candidate"]
    pr = repo / prev["run"]
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(pr / prev["skeletal_fbx"]))
    bpy.ops.import_scene.fbx(filepath=str(pr / prev["base_fbx"]))
    new = [o for o in bpy.data.objects if o not in before]
    inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
    for o in new:
        if o.parent is None:
            o.matrix_world = inv @ o.matrix_world
    prev_mat = pbr_material("PREVIEW_PREV", pr / prev["textures"]["BC"], pr / prev["textures"]["N_OpenGL"],
                            pr / prev["textures"]["ORM"], cull)
    for o in new:
        if o.type == "MESH":
            for slot in o.material_slots:
                slot.material = prev_mat
    cols["PREV"] = collection(scene, "PREV", new)
    bpy.context.view_layer.update()
    cam_data = bpy.data.cameras.new("preview_cam")
    cam = bpy.data.objects.new("preview_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    shots = []

    def render(name, set_names, res, transparent=False):
        label = sorted(set_names)
        if "BASE" in set_names:  # the baseline is the H2 collection with the baseline material
            use_material("BASE")
            set_names = {"H2"}
        elif "H2" in set_names and base:
            use_material("H2")
        show_only(cols, set_names)
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = transparent
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
        scene.render.filepath = str(raw / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        shots.append({"name": name, "sets": label, "px": list(res)})
        return raw / (name + ".png")

    # ---- orthographic views framed like the concepts
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
        for tag in ("H2", "HP", "PREV") + (("BASE",) if base else ()):
            render("ortho-%s-%s" % (vn, tag.lower()), {tag}, (W, H))
    # ---- close-ups (orthographic)
    for c in pcfg["closeups"]:
        cam_data.type = "ORTHO"
        cam_data.sensor_fit = "AUTO"
        cam_data.ortho_scale = float(c["ortho_m"])
        look_at(cam, c["target_m"], c["dir"], 2.0)
        for tag in ("H2", "HP") + (("BASE",) if base else ()):
            render("closeup-%s-%s" % (c["name"], tag.lower()), {tag}, (900, 900))
    # ---- K2 game camera (perspective, horizontal FOV)
    k2 = pcfg["k2"]
    cam_data.type = "PERSP"
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.angle = math.radians(float(k2["fov_deg_horizontal"]))
    cam_data.clip_start = 0.05
    cam_data.clip_end = 100.0
    pitch = math.radians(-float(k2["pitch_deg"]))
    k2m = {}
    for key, dist_uu in k2["distances_uu"].items():
        target = Vector((0.0, 0.0, float(k2["focus_z_m"])))
        look_at(cam, target, (0.0, -math.cos(pitch), math.sin(pitch)), float(dist_uu) / 100.0)
        for tag in ("H2", "PREV") + (("BASE",) if base else ()):
            p = render("%s-%s" % (key, tag.lower()), {tag}, tuple(k2["resolution"]), transparent=True)
            img = bpy.data.images.load(str(p))
            a = U.image_to_array(img)[..., 3]
            bpy.data.images.remove(img)
            m = a > 0.5
            ys, xs = np.nonzero(m)
            k2m["%s/%s" % (key, tag.lower())] = {"silhouette_px": int(m.sum()),
                                                  "height_px": int(ys.max() - ys.min() + 1) if len(ys) else 0,
                                                  "width_px": int(xs.max() - xs.min() + 1) if len(xs) else 0}
    scene.render.film_transparent = False
    pose_shots = []
    if pcfg.get("pose_closeups"):
        from .st_seams import pose as set_pose, reset_pose
        ao_src = {"H2": tdir / ("%s_ORM.png" % prefix)}
        if base:
            ao_src["BASE"] = run_dir / base["textures_dir"] / ("%s_ORM.png" % base["prefix"])
        for tag, path in ao_src.items():
            mats["AO_" + tag] = ao_material("PREVIEW_AO_" + tag, path)
        for c in pcfg["pose_closeups"]:
            cam_data.type = "ORTHO"
            cam_data.sensor_fit = "AUTO"
            cam_data.ortho_scale = float(c["ortho_m"])
            look_at(cam, c["target_m"], c["dir"], 2.0)
            set_pose(h2_arm, c["pose"])
            for tag in ("H2",) + (("BASE",) if base else ()):
                name = "pose-%s-%s-%s" % (c["name"], c["pose"], tag.lower())
                render(name, {tag}, (900, 900))
                pose_shots.append(name)
            view = scene.view_settings.view_transform
            scene.view_settings.view_transform = "Standard"
            for tag in ao_src:
                use_material("AO_" + tag)
                show_only(cols, {"H2"})
                scene.render.resolution_x, scene.render.resolution_y = 900, 900
                name = "pose-%s-%s-ao-%s" % (c["name"], c["pose"], tag.lower())
                scene.render.filepath = str(raw / (name + ".png"))
                bpy.ops.render.render(write_still=True)
                pose_shots.append(name)
            scene.view_settings.view_transform = view
            reset_pose(h2_arm)
        use_material("H2")
    channel_shots = []
    if pcfg.get("channel_views"):
        view = scene.view_settings.view_transform
        scene.view_settings.view_transform = "Standard"
        orm_src = {"H2": tdir / ("%s_ORM.png" % prefix)}
        if base:
            orm_src["BASE"] = run_dir / base["textures_dir"] / ("%s_ORM.png" % base["prefix"])
        for cv in pcfg["channel_views"]:
            loc, d = views[cv["view"]]
            cam_data.type = "ORTHO"
            cam_data.sensor_fit = "VERTICAL"
            cam_data.ortho_scale = height_m
            cam.location = loc
            cam.rotation_euler = (-Vector(d)).to_track_quat("-Z", "Y").to_euler()
            for tag, path in orm_src.items():
                key = "CH_%s_%s" % (cv["name"], tag)
                mats[key] = ao_material("PREVIEW_" + key, path, cv["channel"])
                use_material(key)
                show_only(cols, {"H2"})
                scene.render.resolution_x, scene.render.resolution_y = W, H
                name = "channel-%s-%s-%s" % (cv["name"], cv["view"], tag.lower())
                scene.render.filepath = str(raw / (name + ".png"))
                bpy.ops.render.render(write_still=True)
                channel_shots.append(name)
        scene.view_settings.view_transform = view
        use_material("H2")
    lo, hi = U.bounds(h2_meshes)
    report = {"stage": "preview", "device": device, "samples": pcfg["samples"], "denoise": True, "view_transform": "AgX",
              "label": pcfg["label"], "backface_culling_game_models": cull, "ortho_frame": {"px": [W, H], "ortho_height_m": U.r(height_m, 5), "centre_z_m": U.r(zc, 5),
                                                    "base_centre_x_share": base_x},
              "k2": {"fov_deg_horizontal": k2["fov_deg_horizontal"], "pitch_deg": k2["pitch_deg"],
                     "distances_uu": k2["distances_uu"], "focus_z_m": k2["focus_z_m"], "silhouettes": k2m},
              "h2_bounds_m": [U.rv(lo, 5), U.rv(hi, 5)], "shots": shots, "status": "измерено",
              "baseline": baseline_report, "pose_closeups": pose_shots, "channel_views": channel_shots,
              "note": "Blender Cycles frames (studio light, AgX) — редакторные кадры, не игровой свет и не приёмка"}
    U.write_json(run_dir / "reports" / "preview-report.json", report)
