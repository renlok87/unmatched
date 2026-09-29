"""Stage `compare` (headless Blender, EEVEE): H2 and H2.1 rendered in the same scene, camera and light, both with
the 2K runtime textures (the H2 4K masters were local only). H2.1 iteration (2026-09-29).

blender -b --factory-startup --python-exit-code 1 --python stage_compare.py -- <profile.json>

Inputs: the H2.1 run (export/, textures/*_2K.png) and the H2 baseline that run.py restores from git into
work/h2-baseline/ (profile h21.baseline: git_rev + path + sha256 per file; checked again here). Lights
(profile h21.compare.lights):
  studio      the preview stage light (three suns + near-black world), as the H2 frames;
  studio_env  the same suns + a soft grey gradient environment (strength h21.compare.env_strength) that lights and is
              reflected but is not seen by the camera (film transparent; compare_sheets.py composites the preview
              background): metal and a glossy gem need something to reflect. Blender EEVEE, not the game light.
Frames (work/compare/, git-ignored; the committed sheets are made by compare_sheets.py):
  ortho_{front,right,back}_<light>_{h2,h21}.png      framing of the preview stage (concept %), 1200 x 1333
  k2_{1p6,5x}_{front,3q}_<light>_{h2,h21}.png         game camera K2 (as the preview stage), 1920 x 1080
  mat_{crystal,buckle,stole,staff}_<light>_{h2,h21}.png  material close-ups, 800 x 800
Report: reports/compare-report.json (inputs with sha256, lights, cameras, frame sha256).
"""

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402
import stage_preview as SP  # noqa: E402  (helpers only: its main() runs as a script)

B.require_background("stage_compare.py")

LIGHTS = ("studio", "studio_env")


def env_world(strength):
    """Soft grey gradient: dark ground, grey horizon, light zenith (world direction z)."""
    world = bpy.data.worlds.new("compare_env")
    world.use_nodes = True if world.node_tree is None else world.use_nodes
    nt = world.node_tree
    bg = nt.nodes.get("Background")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1.0
    mr.inputs["From Max"].default_value = 1.0
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    rp = nt.nodes.new("ShaderNodeValToRGB")
    cr = rp.color_ramp
    cr.elements[0].position = 0.35
    cr.elements[0].color = (0.02, 0.02, 0.022, 1.0)
    cr.elements[1].position = 1.0
    cr.elements[1].color = (0.75, 0.78, 0.82, 1.0)
    mid = cr.elements.new(0.52)
    mid.color = (0.22, 0.22, 0.23, 1.0)
    nt.links.new(mr.outputs["Result"], rp.inputs["Fac"])
    nt.links.new(rp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = float(strength)
    return world


def source_to_final(prof):
    """The rig stage's figure transform (source frame -> final metres): uniform scale about the source base-top centre."""
    src = C.load_json(prof.reports / "source-report.json")
    bmin = np.array(src["parts"]["tripo_part_1"]["bounds_m"]["min"])
    bmax = np.array(src["parts"]["tripo_part_1"]["bounds_m"]["max"])
    cx, cy, base_top = (bmin[0] + bmax[0]) / 2, (bmin[1] + bmax[1]) / 2, bmax[2]
    top_src = src["parts"][prof["scale"]["top_part"]]["bounds_m"]["max"][2]
    fz = prof["scale"]["base_footprint_m"][2]
    s = (prof["scale"]["figure_height_m"] - fz) / (top_src - base_top)
    return lambda p: Vector(((p[0] - cx) * s, (p[1] - cy) * s, fz + (p[2] - base_top) * s))


def main():
    prof = C.Profile(B.script_args()[0])
    h21 = prof["h21"]
    base = h21["baseline"]
    bdir = prof.work / "h2-baseline"
    inputs = {}
    for key, f in sorted(base["files"].items()):
        path = bdir / Path(f["path"]).name
        got = C.sha256(path)
        if got != f["sha256"]:
            raise RuntimeError("baseline %s: sha256 %s != %s (run.py restores it from git)" % (key, got, f["sha256"]))
        inputs["h2_" + key] = {"path": base["files"][key]["path"], "git_rev": base["git_rev"], "sha256": got}
    B.empty_file()
    scene = bpy.context.scene
    cam, _lights = SP.setup_scene(scene)
    studio_world = scene.world
    world_env = env_world(h21["compare"]["env_strength"])
    cols = {k: bpy.data.collections.new(k.upper()) for k in ("h2", "h21")}
    for c in cols.values():
        scene.collection.children.link(c)
    objs = {"h2": SP.import_fbx_authored(bdir / Path(base["files"]["sk_fbx"]["path"]).name, cols["h2"])
            + SP.import_fbx_authored(bdir / Path(base["files"]["base_fbx"]["path"]).name, cols["h2"]),
            "h21": SP.import_fbx_authored(prof.export / prof["exports"]["skeletal_fbx"], cols["h21"])
            + SP.import_fbx_authored(prof.export / prof["exports"]["base_fbx"], cols["h21"])}
    t = prof.textures
    p = prof["maps"]["prefix"]
    for name in ("BC", "ORM", "N"):
        inputs["h21_%s_2K" % name] = {"path": C.rel(t / ("%s_%s_2K.png" % (p, name))), "sha256": C.sha256(t / ("%s_%s_2K.png" % (p, name)))}
    for name in ("sk_fbx", "base_fbx"):
        f = prof.export / prof["exports"]["skeletal_fbx" if name == "sk_fbx" else "base_fbx"]
        inputs["h21_" + name] = {"path": C.rel(f), "sha256": C.sha256(f)}
    mats = {"h2": SP.pbr_material("CMP_H2_2K", bdir / Path(base["files"]["BC_2K"]["path"]).name,
                                  bdir / Path(base["files"]["ORM_2K"]["path"]).name, bdir / Path(base["files"]["N_2K"]["path"]).name, True),
            "h21": SP.pbr_material("CMP_H21_2K", t / (p + "_BC_2K.png"), t / (p + "_ORM_2K.png"), t / (p + "_N_2K.png"), True)}
    for k in objs:
        SP.assign(objs[k], mats[k])
    out = prof.work / "compare"
    out.mkdir(parents=True, exist_ok=True)
    frames = {}

    def shoot(name, res, light, which):
        cols["h2"].hide_render = which != "h2"
        cols["h21"].hide_render = which != "h21"
        env = light == "studio_env"
        scene.world = world_env if env else studio_world
        scene.render.film_transparent = env
        scene.render.resolution_x, scene.render.resolution_y = res
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA" if env else "RGB"
        path = out / ("%s_%s_%s.png" % (name, light, which))
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        C.strip_png_metadata(path)
        frames[path.name] = C.sha256(path)

    meshes = [o for o in objs["h21"] if o.type == "MESH"]
    zt = float(np.concatenate([B.verts_np(o) for o in meshes])[:, 2].max())
    rev = prof["review"]
    framing = {"front": (0.058, 0.945), "right": (0.042, 0.935), "back": (0.042, 0.935)}
    fin = source_to_final(prof)
    arm = next(o for o in objs["h21"] if o.type == "ARMATURE")

    def bone_head(name):
        return arm.matrix_world @ arm.data.bones[name].head_local

    def bone_tail(name):
        return arm.matrix_world @ arm.data.bones[name].tail_local

    staff = next(o for o in objs["h21"] if o.type == "MESH" and "Staff" in o.name)
    sv = B.verts_np(staff)
    top = sv[np.argmax(sv[:, 2])]
    closeups = {
        "crystal": ("front", Vector((float(top[0]), float(top[1]), float(top[2]) - 0.022)), 0.07),
        "buckle": ("front", fin((-0.0085, -0.065, 0.5635)), 0.05),
        "stole": ("front", fin((-0.073, -0.075, 0.47)), 0.07),
        "staff": ("right", bone_head("weapon.R") * 0.55 + bone_tail("weapon.R") * 0.45, 0.12),
    }
    gc = rev["game_camera"]
    focus = Vector((0.0, 0.0, gc["focus_above_cell_uu"] / 100.0))
    cameras = {}
    for light in LIGHTS:
        for view, (top_frac, bottom_frac) in framing.items():
            scale = zt / (bottom_frac - top_frac)
            SP.ortho(cam, view, (0.0, 0.0, zt + top_frac * scale - 0.5 * scale), scale)
            cameras["ortho_" + view] = {"ortho_scale_m": C.r(scale, 5), "direction": view}
            for which in ("h2", "h21"):
                shoot("ortho_" + view, tuple(h21["compare"]["ortho_resolution"]), light, which)
        for tag, dist in (("1p6", gc["distance_uu"][0]), ("5x", gc["distance_uu"][1])):
            for view, yaw in (("front", 0.0), ("3q", -45.0)):
                SP.game_cam(cam, focus, dist / 100.0, gc["pitch_deg"], yaw, gc["horizontal_fov_deg"])
                cameras["k2_%s_%s" % (tag, view)] = {"distance_uu": dist, "yaw_deg": yaw, "pitch_deg": gc["pitch_deg"]}
                for which in ("h2", "h21"):
                    shoot("k2_%s_%s" % (tag, view), tuple(gc["resolution"]), light, which)
        for name, (direction, centre, scale) in closeups.items():
            SP.ortho(cam, direction, centre, scale)
            cameras["mat_" + name] = {"direction": direction, "centre_m": C.rv(centre, 5), "ortho_scale_m": scale}
            for which in ("h2", "h21"):
                shoot("mat_" + name, (800, 800), light, which)
    C.write_json(prof.reports / "compare-report.json", {
        "stage": "compare", "profile": C.rel(prof.path), "profile_id": prof["profile_id"], "renderer": scene.render.engine,
        "blender": bpy.app.version_string, "label": "blender", "inputs": inputs, "lights": h21["compare"]["lights"],
        "env_strength": h21["compare"]["env_strength"], "texture_set": h21["compare"]["texture_set"], "cameras": cameras,
        "frames_dir": C.rel(out), "frames_sha256": frames,
        "note": "same scene, camera and light for H2 and H2.1; ORM.R (AO) not applied (as the preview stage); "
                "the N (DirectX) green is inverted in the shader"})
    print("H2_STAGE_OK compare frames=%d" % len(frames))


main()
