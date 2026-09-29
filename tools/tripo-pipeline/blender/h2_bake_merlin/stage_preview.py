"""Stage `preview` (headless Blender, EEVEE): review frames of the exported H2 candidate. All frames are Blender
renders (studio light, not the game light) and are labelled "blender" by the sheets stage.

blender -b --factory-startup --python-exit-code 1 --python stage_preview.py -- <profile.json>

The exported FBX pair (SK + SM) is imported and turned back to the authored frame (face -Y), exactly as the probe
does; material = Principled BSDF with BC (sRGB), ORM (G roughness, B metallic; AO is not applied: in UE it only
acts on indirect light) and the normal map through a tangent-space Normal Map node (H2: the DirectX N with its green
inverted in the shader, 1 - G; the previous candidate: its committed N_OpenGL). Frames (preview/):
  ortho_{front,right,back}.png    framing of the H2 concepts (crystal top / base bottom at the concept's %)
  closeup_<name>.png              4K master textures
  k2_{1p6,5x}_{front,3q}_{h2,prev}.png  game camera K2 (horizontal FOV 35, pitch -55, D 1207 / 386 uu, focus
                                  28 uu above the cell), 2K runtime textures for H2; the previous CLI candidate
                                  (2K atlas) in the same frame
  silhouette_front.png            black silhouette on white (readability)
"""

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blib as B  # noqa: E402
import common as C  # noqa: E402

B.require_background("stage_preview.py")


def import_fbx_authored(path, collection):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
    for o in new:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        collection.objects.link(o)
        if o.parent is None:
            o.matrix_world = inv @ o.matrix_world
    return new


def pbr_material(name, bc, orm, normal, directx):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs["Surface"])
    t_bc = nt.nodes.new("ShaderNodeTexImage")
    t_bc.image = bpy.data.images.load(str(bc), check_existing=True)
    nt.links.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
    t_orm = nt.nodes.new("ShaderNodeTexImage")
    t_orm.image = bpy.data.images.load(str(orm), check_existing=True)
    t_orm.image.colorspace_settings.name = "Non-Color"
    sep = nt.nodes.new("ShaderNodeSeparateColor")
    nt.links.new(t_orm.outputs["Color"], sep.inputs["Color"])
    nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    t_n = nt.nodes.new("ShaderNodeTexImage")
    t_n.image = bpy.data.images.load(str(normal), check_existing=True)
    t_n.image.colorspace_settings.name = "Non-Color"
    nmap = nt.nodes.new("ShaderNodeNormalMap")
    nmap.space = "TANGENT"
    nmap.uv_map = "UVMap"
    n_out = t_n.outputs["Color"]
    if directx:
        # DirectX (-Y) -> OpenGL (+Y) for Blender: G' = 1 - G (R and B unchanged)
        sep_n = nt.nodes.new("ShaderNodeSeparateColor")
        inv = nt.nodes.new("ShaderNodeMath")
        inv.operation = "SUBTRACT"
        inv.inputs[0].default_value = 1.0
        comb = nt.nodes.new("ShaderNodeCombineColor")
        nt.links.new(n_out, sep_n.inputs["Color"])
        nt.links.new(sep_n.outputs["Green"], inv.inputs[1])
        nt.links.new(sep_n.outputs["Red"], comb.inputs["Red"])
        nt.links.new(inv.outputs["Value"], comb.inputs["Green"])
        nt.links.new(sep_n.outputs["Blue"], comb.inputs["Blue"])
        n_out = comb.outputs["Color"]
    nt.links.new(n_out, nmap.inputs["Color"])
    nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def assign(objs, mat):
    for o in objs:
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(mat)
            if o.data.uv_layers:
                o.data.uv_layers[0].name = "UVMap"


def setup_scene(scene):
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.film_transparent = False
    # no metadata text chunks (date, time, render time, host...) in the PNGs: byte-stable frames
    for attr in dir(scene.render):
        if attr.startswith("use_stamp"):
            try:
                setattr(scene.render, attr, False)
            except (AttributeError, TypeError):
                pass
    world = bpy.data.worlds.new("preview_world")
    world.use_nodes = True if world.node_tree is None else world.use_nodes
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.018, 0.019, 0.022, 1.0)
    bg.inputs["Strength"].default_value = 1.0
    scene.world = world
    lights = []
    for name, rot, energy, color in (("key", (50, 0, -35), 3.2, (1.0, 0.96, 0.9)),
                                     ("fill", (60, 0, 140), 1.0, (0.85, 0.9, 1.0)),
                                     ("rim", (35, 0, 180), 1.6, (1.0, 1.0, 1.0))):
        ld = bpy.data.lights.new(name, "SUN")
        ld.energy = energy
        ld.color = color
        ld.angle = math.radians(8)
        lo = bpy.data.objects.new(name, ld)
        lo.rotation_euler = [math.radians(a) for a in rot]
        scene.collection.objects.link(lo)
        lights.append(lo)
    cam_data = bpy.data.cameras.new("cam")
    cam = bpy.data.objects.new("cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam, lights


def render(scene, path, res):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    return C.rel(path)


def ortho(cam, direction, centre, scale):
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = scale
    cam.data.sensor_fit = "AUTO"
    yaw = {"front": 0.0, "right": -90.0, "back": 180.0, "left": 90.0}[direction]
    cam.rotation_euler = (math.radians(90), 0.0, math.radians(yaw))
    d = cam.rotation_euler.to_matrix() @ Vector((0, 0, -1))
    cam.location = Vector(centre) - d * 3.0


def game_cam(cam, focus, distance, pitch_deg, yaw_deg, hfov_deg):
    cam.data.type = "PERSP"
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(hfov_deg)
    cam.data.clip_start = 0.05
    cam.data.clip_end = 100.0
    cam.rotation_euler = (math.radians(90 + pitch_deg), 0.0, math.radians(yaw_deg))
    d = cam.rotation_euler.to_matrix() @ Vector((0, 0, -1))
    cam.location = Vector(focus) - d * distance


def main():
    prof = C.Profile(B.script_args()[0])
    rev = prof["review"]
    B.empty_file()
    scene = bpy.context.scene
    cam, _lights = setup_scene(scene)
    h2 = bpy.data.collections.new("H2")
    prev = bpy.data.collections.new("PREV")
    scene.collection.children.link(h2)
    scene.collection.children.link(prev)
    ex = prof.export
    h2_objs = import_fbx_authored(ex / prof["exports"]["skeletal_fbx"], h2) + import_fbx_authored(ex / prof["exports"]["base_fbx"], h2)
    pc = prof["previous_candidate"]
    prev_objs = import_fbx_authored(C.repo_path(pc["sk_fbx"]), prev) + import_fbx_authored(C.repo_path(pc["base_fbx"]), prev)
    t = prof.textures
    p = prof["maps"]["prefix"]
    m4 = pbr_material("PREVIEW_H2_4K", t / (p + "_BC_4K.png"), t / (p + "_ORM_4K.png"), t / (p + "_N_4K.png"), True)
    m2 = pbr_material("PREVIEW_H2_2K", t / (p + "_BC_2K.png"), t / (p + "_ORM_2K.png"), t / (p + "_N_2K.png"), True)
    mp = pbr_material("PREVIEW_PREV_2K", C.repo_path(pc["textures"]["BC"]), C.repo_path(pc["textures"]["ORM"]),
                      C.repo_path(pc["textures"]["N_OpenGL"]), False)
    assign(h2_objs, m4)
    assign(prev_objs, mp)
    out = prof.preview
    frames = {}
    meshes = [o for o in h2_objs if o.type == "MESH"]
    pts = np.concatenate([B.verts_np(o) for o in meshes])
    zt = float(pts[:, 2].max())
    # ---------------- ortho views with the concepts' framing
    prev.hide_render = True
    framing = {"front": (0.058, 0.945, "front"), "right": (0.042, 0.935, "right"), "back": (0.042, 0.935, "back")}
    res = tuple(rev["resolution"])
    for name, (top_frac, bottom_frac, direction) in framing.items():
        span = zt - 0.0
        scale = span / (bottom_frac - top_frac)  # portrait: ortho_scale = frame height
        zc = zt + top_frac * scale - 0.5 * scale
        ortho(cam, direction, (0.0, 0.0, zc), scale)
        frames["ortho_" + name] = render(scene, out / ("ortho_%s.png" % name), res)
    # silhouette
    sil = bpy.data.materials.new("SIL")
    sil.diffuse_color = (0, 0, 0, 1)
    if sil.node_tree is None:
        sil.use_nodes = True
    em = sil.node_tree.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (0, 0, 0, 1)
    sil.node_tree.links.new(em.outputs[0], sil.node_tree.nodes["Material Output"].inputs["Surface"])
    assign(h2_objs, sil)
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    ortho(cam, "front", (0.0, 0.0, zt + 0.058 * (zt / 0.887) - 0.5 * (zt / 0.887)), zt / 0.887)
    frames["silhouette_front"] = render(scene, out / "silhouette_front.png", res)
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.018, 0.019, 0.022, 1.0)
    assign(h2_objs, m4)
    # ---------------- close-ups (4K master), ortho
    arm = next(o for o in h2_objs if o.type == "ARMATURE")

    def bone_head(name):
        return arm.matrix_world @ arm.data.bones[name].head_local

    def bone_tail(name):
        return arm.matrix_world @ arm.data.bones[name].tail_local

    head_c = (bone_head("head") * 0.35 + bone_tail("head") * 0.65)
    # FBX bone tails are rebuilt by the importer (lengths are not stored): the crystal is taken from the staff mesh
    staff = next(o for o in h2_objs if o.type == "MESH" and "Staff" in o.name)
    sv = B.verts_np(staff)
    top = sv[np.argmax(sv[:, 2])]
    crystal = Vector((float(top[0]), float(top[1]), float(top[2]) - 0.022))
    closeups = {
        "face": ("front", head_c + Vector((0, 0, -0.01)), 0.10),
        "right_fist_staff": ("front", bone_head("weapon.R"), 0.08),
        "left_fist": ("front", bone_head("hand.L") * 0.5 + bone_tail("hand.L") * 0.5, 0.07),
        "crystal": ("front", crystal, 0.07),
        "staff_mid": ("right", bone_head("weapon.R") * 0.55 + bone_tail("weapon.R") * 0.45, 0.14),
        "feet_base": ("front", Vector((0.0, 0.0, 0.06)), 0.28),
        "back_hood": ("back", head_c, 0.12),
    }
    for name, (direction, centre, scale) in closeups.items():
        ortho(cam, direction, centre, scale)
        frames["closeup_" + name] = render(scene, out / ("closeup_%s.png" % name), (1200, 1200))
    # ---------------- game camera K2 (2K runtime), H2 and the previous candidate in the same frame
    gc = rev["game_camera"]
    focus = Vector((0.0, 0.0, gc["focus_above_cell_uu"] / 100.0))
    for tag, dist in (("1p6", gc["distance_uu"][0]), ("5x", gc["distance_uu"][1])):
        for view, yaw in (("front", 0.0), ("3q", -45.0)):
            game_cam(cam, focus, dist / 100.0, gc["pitch_deg"], yaw, gc["horizontal_fov_deg"])
            assign(h2_objs, m2)
            h2.hide_render, prev.hide_render = False, True
            frames["k2_%s_%s_h2" % (tag, view)] = render(scene, out / ("k2_%s_%s_h2.png" % (tag, view)), tuple(gc["resolution"]))
            h2.hide_render, prev.hide_render = True, False
            frames["k2_%s_%s_prev" % (tag, view)] = render(scene, out / ("k2_%s_%s_prev.png" % (tag, view)), tuple(gc["resolution"]))
    h2.hide_render = False
    C.write_json(prof.reports / "preview-report.json", {
        "stage": "preview", "profile": C.rel(prof.path), "renderer": scene.render.engine, "blender": bpy.app.version_string,
        "label": "blender", "light": "three sun lights + dark world, Standard view transform: studio preview, not the game light (DX12/Lumen)",
        "ao_note": "ORM.R (AO) is not applied in the preview material",
        "normal_note": "H2: N (DirectX) with G inverted in the shader (1 - G); previous candidate: its N_OpenGL", "frames": frames,
        "k2_camera": {"horizontal_fov_deg": gc["horizontal_fov_deg"], "pitch_deg": gc["pitch_deg"], "distance_uu": gc["distance_uu"],
                      "focus_above_cell_uu": gc["focus_above_cell_uu"], "yaw_deg": {"front": 0, "3q": -45}},
        "previous_candidate": pc["run"]})
    print("H2_STAGE_OK preview")


if __name__ == "__main__":  # stage_compare.py imports the helpers above
    main()
