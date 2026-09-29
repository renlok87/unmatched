"""Review frames of the H2 candidate (headless only). Every frame is a Blender render (label "blender"): EEVEE,
neutral preview light (sun 3.0 + sun 1.3 + grey world 0.55, Standard view transform, as the T3.3 review), single-sided
materials as in UE; not the game lighting, not an UE frame.

    blender -b --factory-startup --python review_h2.py -- <profile.json> <run_dir> <mode> [--prev-run <dir>]

mode "concept":   ortho front / left side / back framed like the H2 concepts (1470x1070, transparent film for the
                  side-by-side composition in compose_review.py), close-ups (face front and 3/4, talons and bands,
                  wing primaries, back of the neck = the Janus-repair area, the nape from behind and the crest from the
                  front at the game pitch -55 = where the hood remnant showed), each close-up also rendered from the
                  textured Tripo high-poly placed by the seat transform (bake fidelity), TeamColor previews
                  (approximation of M_UM_Figure: lerp(BC, TeamColor x luminance(BC) x TeamDyeGain, TeamMask.R),
                  TeamDye 1, gain 6, teams Gold/Silver of 03 С-11);
mode "k2":        game camera K2 (horizontal FOV 35, pitch -55, 7.5 m = K1 12 m / zoom 1.6, 1920x1080) with the
                  previous candidate (--prev-run: its export/*.fbx + textures, same parametric base) on the next cell
                  (previous at x = -0.5, H2 at x = +0.5), facing and 3/4 (azimuth -40), 4.8 m facing / back / back 3/4,
                  plus the "1 m cell = 250 px" game-scale frame; every frame name ends in prev_left_h2_right or
                  h2_left_prev_right from the projected figure centres (from behind the order flips), and the record in
                  review-frames-k2.json keeps left_to_right for compose_review.py;
mode "instances": three copies (instance index 1/2/3) on adjacent 1 m cells, K1 12 m / K2 7.5 m / 4.8 m, facing and
                  mixed yaw; writes instances-pips.json (projected pip centres, radii, ray-cast visibility) for
                  art/pipeline-candidates/ASSET-HARPY-001/scripts/analyse_instances.py.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
import review as RV  # noqa: E402

C.require_background("review_h2.py")
a = C.script_args()
PROFILE_PATH, RUN, MODE = Path(a[0]).resolve(), Path(a[1]).resolve(), a[2]
PREV = Path(a[a.index("--prev-run") + 1]).resolve() if "--prev-run" in a else None
P = C.load_profile(PROFILE_PATH)
RIG = json.loads((RUN / "reports" / "h2-rig-report.json").read_text(encoding="utf-8"))
OUT = RUN / "preview" / {"concept": "review", "k2": "k2", "instances": "instances"}[MODE]
OUT.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(RUN / "work" / "h2-candidate.blend"))
scene = bpy.context.scene
N_ = P["names"]
body = bpy.data.objects[N_["body_object"]]
base = bpy.data.objects[N_["base_object"]]
arm = next(o for o in scene.objects if o.type == "ARMATURE")
for o in (body, base):
    mw = o.matrix_world.copy()
    o.parent = None
    o.matrix_world = mw
    for m in list(o.modifiers):
        o.modifiers.remove(m)
arm.hide_render = True
for m in bpy.data.materials:
    m.use_backface_culling = True
cam = RV.setup_scene(scene, samples=64)
frames = {}
team_lin = {"Gold": (0.807, 0.527, 0.144), "Silver": (0.347, 0.539, 0.686)}
base["um_instance_index"] = 3.0
base["um_team_color"] = team_lin["Gold"] + (1.0,)


def shoot(name, d, t, **kw):
    frames[name] = RV.shoot(scene, cam, OUT / ("%s.png" % name), d, t, **kw)
    frames[name]["label"] = "blender"


def seat_matrix():
    s = RIG["seat"]
    cx, cy = s["source_base_centre_xy_m"]
    return (Matrix.Translation((0, 0, s["base_height_m"])) @ Matrix.Diagonal((s["scale"],) * 3 + (1.0,)) @
            Matrix.Translation((-cx, -cy, -s["source_base_top_z_m"])))


if MODE == "concept":
    scene.render.film_transparent = True
    span = RIG["measure"]["bounds_body_m"]["max"][0] - RIG["measure"]["bounds_body_m"]["min"][0]
    ortho = span / 0.89  # concept front: wings x 5.5 %-94.5 % of the width (prompts.md)
    zc = 0.42 - (0.5 - 0.10) * 1070 * ortho / 1470  # crest at 10 % from the top
    for tag, d in (("front", (0, -1, 0)), ("side", (1, 0, 0)), ("back", (0, 1, 0))):
        shoot("concept_frame_%s" % tag, d, (0, 0, zc), ortho=ortho, res=(1470, 1070))
    scene.render.film_transparent = False
    # high-poly (textured Tripo) placed by the seat transform, for bake-fidelity pairs
    with bpy.data.libraries.load(str(RUN / "work" / "h2-lowpoly.blend")) as (src, dst):
        dst.objects = [n for n in src.objects if n.startswith("HP_") and n != "HP_" + P["seat"]["base_reference_part"]]
    hp = []
    for o in dst.objects:
        scene.collection.objects.link(o)
        o.matrix_world = seat_matrix() @ o.matrix_world
        o.hide_render = True
        hp.append(o)
    for m in bpy.data.materials:
        m.use_backface_culling = True
    fc = Vector(RIG["measure"]["face_centroid_m"])
    close = [("face_front", (0, -1, 0.05), (fc.x, fc.y, fc.z + 0.005), 0.12),
             ("face_3q", (-0.7, -0.7, 0.12), (fc.x, fc.y + 0.01, fc.z + 0.005), 0.13),
             ("talons_front", (0, -1, 0.35), (0, -0.03, 0.085), 0.2),
             ("talons_3q_left", (0.7, -0.7, 0.3), (0.035, -0.03, 0.085), 0.14),
             ("wing_primaries_left_back", (0.2, 1, 0.3), (0.22, 0.09, 0.28), 0.3),
             ("wing_front_left", (0.15, -1, 0.1), (0.2, 0.04, 0.3), 0.3),
             ("neck_back", (0, 1, 0.25), (0, 0.06, 0.3), 0.18),
             ("nape_back_game", RV.game_dir(180), (0, 0.02, 0.29), 0.2),
             ("nape_back3q_game", RV.game_dir(140), (0, 0.02, 0.29), 0.2),
             ("crest_front_game", RV.game_dir(0), (0, -0.02, 0.31), 0.22)]
    for name, d, t, ortho in close:
        shoot("closeup_%s" % name, d, t, ortho=ortho, res=(1000, 1000))
        for o in (body, base):
            o.hide_render = True
        for o in hp:
            o.hide_render = False
        shoot("closeup_%s_highpoly" % name, d, t, ortho=ortho, res=(1000, 1000))
        for o in hp:
            o.hide_render = True
        for o in (body, base):
            o.hide_render = False
    # TeamColor preview on the figure material (TeamMask .R, W4-B dye)
    mat = body.data.materials[0]
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bc = next(n for n in nt.nodes if n.type == "TEX_IMAGE" and n.image.name.endswith("_BC.png"))
    tm = nt.nodes.new("ShaderNodeTexImage")
    tm.image = bpy.data.images.load(str(RUN / "textures" / "4k" / ("%s_TeamMask.png" % P["textures"]["prefix"])))
    tm.image.colorspace_settings.name = "Non-Color"
    rgb2bw = nt.nodes.new("ShaderNodeRGBToBW")
    nt.links.new(bc.outputs["Color"], rgb2bw.inputs["Color"])
    team = nt.nodes.new("ShaderNodeRGB")
    gain = nt.nodes.new("ShaderNodeMath")
    gain.operation = "MULTIPLY"
    gain.inputs[1].default_value = 6.0
    nt.links.new(rgb2bw.outputs["Val"], gain.inputs[0])
    dye = nt.nodes.new("ShaderNodeMix")
    dye.data_type = "RGBA"
    dye.blend_type = "MULTIPLY"
    RV_sock = lambda node, io, name, typ: next(s for s in getattr(node, io) if s.name == name and s.type == typ)
    RV_sock(dye, "inputs", "Factor", "VALUE").default_value = 1.0
    nt.links.new(team.outputs["Color"], RV_sock(dye, "inputs", "A", "RGBA"))
    comb = nt.nodes.new("ShaderNodeCombineColor")
    for k in ("Red", "Green", "Blue"):
        nt.links.new(gain.outputs["Value"], comb.inputs[k])
    nt.links.new(comb.outputs["Color"], RV_sock(dye, "inputs", "B", "RGBA"))
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    nt.links.new(tm.outputs["Color"], RV_sock(mix, "inputs", "Factor", "VALUE"))
    nt.links.new(bc.outputs["Color"], RV_sock(mix, "inputs", "A", "RGBA"))
    nt.links.new(RV_sock(dye, "outputs", "Result", "RGBA"), RV_sock(mix, "inputs", "B", "RGBA"))
    nt.links.new(RV_sock(mix, "outputs", "Result", "RGBA"), bsdf.inputs["Base Color"])
    for tname, col in team_lin.items():
        team.outputs["Color"].default_value = col + (1.0,)
        base["um_team_color"] = col + (1.0,)
        shoot("teamcolor_%s_front" % tname.lower(), (0, -1, 0.35), (0, 0, 0.21), ortho=0.8, res=(1100, 800))
        shoot("teamcolor_%s_game3q" % tname.lower(), RV.game_dir(-40), (0, 0, 0.2), fov_h=35, distance=2.0,
              res=(1600, 1000))

elif MODE == "k2":
    # previous candidate on the neighbour cell
    before = set(bpy.data.objects)
    for f in sorted((PREV / "export").glob("SK_*.fbx")):
        bpy.ops.import_scene.fbx(filepath=str(f))
    new = [o for o in bpy.data.objects if o not in before]
    inv = Matrix.Rotation(math.radians(-90.0), 4, "Z")
    for o in new:
        if o.parent is None:
            o.matrix_world = inv @ o.matrix_world
    bpy.context.view_layer.update()
    prev_body = next(o for o in new if o.type == "MESH")
    prev_arm = next((o for o in new if o.type == "ARMATURE"), None)
    mw = prev_body.matrix_world.copy()
    prev_body.parent = None
    prev_body.matrix_world = mw
    for m in list(prev_body.modifiers):
        prev_body.modifiers.remove(m)
    if prev_arm:
        prev_arm.hide_render = True
    pm = bpy.data.materials.new("M_Review_Prev_Atlas")
    try:
        pm.use_nodes = True
    except AttributeError:
        pass
    pnt = pm.node_tree
    pb = next(n for n in pnt.nodes if n.type == "BSDF_PRINCIPLED")
    imgs = {}
    for key, cs in (("BC", "sRGB"), ("N_OpenGL", "Non-Color"), ("ORM", "Non-Color")):
        im = bpy.data.images.load(str(next((PREV / "textures").glob("*_Atlas_%s.png" % key))))
        im.colorspace_settings.name = cs
        node = pnt.nodes.new("ShaderNodeTexImage")
        node.image = im
        imgs[key] = node
    pnt.links.new(imgs["BC"].outputs["Color"], pb.inputs["Base Color"])
    nmn = pnt.nodes.new("ShaderNodeNormalMap")
    pnt.links.new(imgs["N_OpenGL"].outputs["Color"], nmn.inputs["Color"])
    pnt.links.new(nmn.outputs["Normal"], pb.inputs["Normal"])
    sep = pnt.nodes.new("ShaderNodeSeparateColor")
    pnt.links.new(imgs["ORM"].outputs["Color"], sep.inputs["Color"])
    pnt.links.new(sep.outputs["Green"], pb.inputs["Roughness"])
    pnt.links.new(sep.outputs["Blue"], pb.inputs["Metallic"])
    pm.use_backface_culling = True
    prev_body.data.materials.clear()
    prev_body.data.materials.append(pm)
    prev_base = base.copy()
    scene.collection.objects.link(prev_base)
    prev_body.matrix_world = Matrix.Translation((-0.5, 0, 0)) @ prev_body.matrix_world
    prev_base.matrix_world = Matrix.Translation((-0.5, 0, 0)) @ prev_base.matrix_world
    body.matrix_world = Matrix.Translation((0.5, 0, 0)) @ body.matrix_world
    base.matrix_world = Matrix.Translation((0.5, 0, 0)) @ base.matrix_world
    RV.ground(scene, [(x, y) for x in (-0.5, 0.5) for y in (-1.0, 0.0, 1.0)] + [(x, 0.0) for x in (-1.5, 1.5)])
    bpy.context.view_layer.update()

    def centre_x(obj):
        """Screen x (0..1) of the world bounding-box centre of obj in the current camera."""
        c = sum((obj.matrix_world @ Vector(b) for b in obj.bound_box), Vector()) / 8.0
        return world_to_camera_view(scene, cam, c).x

    def shoot_pair(prefix, az, dist):
        """Game-camera frame of both figures; the file name and the record say which figure is on which side of
        the frame (from behind, azimuth 180, the H2 figure at x = +0.5 is on the LEFT)."""
        RV.aim(scene, cam, RV.game_dir(az), (0, 0, 0.12), fov_h=35, distance=dist, res=(1920, 1080))
        bpy.context.view_layer.update()
        h2_left = centre_x(body) < centre_x(prev_body)
        name = "%s_%s" % (prefix, "h2_left_prev_right" if h2_left else "prev_left_h2_right")
        shoot(name, RV.game_dir(az), (0, 0, 0.12), fov_h=35, distance=dist, res=(1920, 1080))
        frames[name].update({"azimuth_deg": az, "distance_m": dist,
                             "left_to_right": ["H2", "previous"] if h2_left else ["previous", "H2"],
                             "screen_x": {"H2": round(centre_x(body), 4), "previous": round(centre_x(prev_body), 4)}})

    shoot_pair("k2_front", 0, 7.5)
    shoot_pair("k2_3q", -40, 7.5)
    shoot_pair("k2close_front", 0, 4.8)
    shoot_pair("k2close_back", 180, 4.8)
    shoot_pair("k2close_back3q", 140, 4.8)
    game_dist = 1920 / (250 * 2 * math.tan(math.radians(17.5)))
    shoot_pair("k1_gamescale_front", 0, game_dist)
    frames["_note"] = {"previous_candidate": C.rel(PREV), "previous_base": "copy of the H2 parametric base (same spec)",
                       "k2_distance_m": 7.5, "k2close_distance_m": 4.8,
                       "k1_gamescale_distance_m": round(game_dist, 3)}

elif MODE == "instances":
    body.hide_render = base.hide_render = True
    for o in (body, base):
        o.matrix_world = Matrix.Translation((0, 0, -100)) @ o.matrix_world
    bp = P["base_parametric"]
    pc = bp["pips"]
    sectors = RIG["base"]["pips"]["pips"]
    pips_local = [{"sector_deg": q["sector_deg"], "slot": q["slot"],
                   "local": Vector((q["centre_m"][0], q["centre_m"][1], bp["height_m"] + pc["raise_m"]))} for q in sectors]
    RV.ground(scene, [(x, y) for x in (-1.0, 0.0, 1.0) for y in (-1.0, 0.0, 1.0)])
    setups = {"facing": [0.0, 0.0, 0.0], "mixed_yaw": [35.0, -120.0, 150.0]}
    cells = [(-1.0, 0.0), (0.0, 0.0), (1.0, 0.0)]
    rec = {}
    for setup, yaws in setups.items():
        copies = []
        for i, ((cx, cy), yaw) in enumerate(zip(cells, yaws)):
            for srco in (body, base):
                c = srco.copy()
                c.data = srco.data
                c.hide_render = False
                c.matrix_world = Matrix.Translation((cx, cy, 0.0)) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
                c["um_instance_index"] = float(i + 1)
                c["um_team_color"] = team_lin["Gold"] + (1.0,)
                scene.collection.objects.link(c)
                copies.append((i + 1, srco, c))
        bpy.context.view_layer.update()
        for kname, dist in (("k1", 12.0), ("k2", 7.5), ("k2close", 4.8)):
            name = "instances_%s_%s" % (setup, kname)
            shoot(name, RV.game_dir(0), (0.0, 0.0, 0.12), fov_h=35, distance=dist, res=(1920, 1080))
            frames[name]["yaws_deg"] = yaws
            dg = bpy.context.evaluated_depsgraph_get()
            recs = []
            for idx, srco, c in copies:
                if srco is not base:
                    continue
                mw = c.matrix_world
                for pip in pips_local:
                    wp = mw @ pip["local"]
                    ndc = world_to_camera_view(scene, cam, wp)
                    ndc_e = world_to_camera_view(scene, cam, mw @ (pip["local"] + Vector((pc["pip_radius_m"], 0, 0))))
                    px = (ndc.x * 1920, (1 - ndc.y) * 1080)
                    pr = math.hypot((ndc_e.x - ndc.x) * 1920, (ndc_e.y - ndc.y) * 1080)
                    direction = (wp - cam.location).normalized()
                    hit, loc, _n, _i, hobj, _m = scene.ray_cast(dg, cam.location, direction,
                                                              distance=(wp - cam.location).length + 0.01)
                    vis = bool(hit and hobj is not None and hobj.name == c.name and (loc - wp).length < pc["pip_radius_m"])
                    recs.append({"instance": idx, "yaw_deg": yaws[idx - 1], "sector_deg": pip["sector_deg"],
                                 "slot": pip["slot"], "px": [round(px[0], 2), round(px[1], 2)],
                                 "radius_px": round(pr, 2), "visible": vis,
                                 "occluder": None if vis else (hobj.name if hit and hobj else "none")})
                inner = mw @ Vector((0, 0, bp["height_m"]))
                nc = world_to_camera_view(scene, cam, inner)
                recs.append({"instance": idx, "base_centre_px": [round(nc.x * 1920, 2), round((1 - nc.y) * 1080, 2)]})
            rec[name] = recs
        for _i, _s, c in copies:
            bpy.data.objects.remove(c)
    (OUT / "instances-pips.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n", encoding="utf-8")

C.write_json(OUT / ("review-frames-%s.json" % MODE), {
    "label": "blender", "lighting": "EEVEE preview: sun 3.0 (50,0,-30), sun 1.3 (60,0,150), world grey 0.55; Standard "
    "view transform; single-sided materials; not game lighting", "frames": frames})
print(C.STAGE_MARKER, "review", MODE, len(frames), flush=True)
