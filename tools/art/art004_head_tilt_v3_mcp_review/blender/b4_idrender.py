# Live-Blender MCP step 4: part-ID Workbench renders of the saved FBX v2/v3 with
# backface culling ON (UE materials are one-sided), close-ups of the head/neck junction.
import bpy, math, json, os
import numpy as np
from mathutils import Vector
ROOT = r"C:/Users/ren/.codex/worktrees/art-foundation/unmached/"
ATLAS = json.load(open(ROOT + "blender/ASSET-MEDUSA-001/atlas-report.json"))
OUT = r"C:/tmp/a1v3/blender/renders"
os.makedirs(OUT, exist_ok=True)
scn = bpy.data.scenes["A1V3_Review"]
PAL = {10: (1, 0, 0), 14: (1, 1, 0), 1: (0, 1, 0), 3: (0, 1, 1), 7: (1, 1, 1)}
def label_mesh(me):
    uv = me.uv_layers.active.data
    cells = [(int(n.split("_")[-1]), (c["x"] + c["inset"]) / 2048, (c["x"] + c["cell"] - c["inset"]) / 2048,
              1 - (c["y_top"] + c["cell"] - c["inset"]) / 2048, 1 - (c["y_top"] + c["inset"]) / 2048)
             for n, c in ATLAS["cells"].items()]
    lab = []
    for p in me.polygons:
        v = -1
        for pid, u0, u1, v0, v1 in cells:
            if all(u0 <= uv[l].uv.x <= u1 and v0 <= uv[l].uv.y <= v1 for l in p.loop_indices):
                v = pid; break
        lab.append(v)
    return lab
def paint(me, colors):
    attr = me.color_attributes.get("A1V3_ID") or me.color_attributes.new("A1V3_ID", "BYTE_COLOR", "CORNER")
    data = []
    for p, c in zip(me.polygons, colors):
        data.extend((*c, 1.0) * p.loop_total)
    attr.data.foreach_set("color", data)
    me.color_attributes.active_color = attr
    me.color_attributes.render_color_index = me.color_attributes.find("A1V3_ID")
objs = {}
for tag in ("v2", "v3"):
    body = bpy.data.objects["SK_Medusa_Body_fbx" + tag]; bow = bpy.data.objects["SK_Medusa_Bow_fbx" + tag]
    lab = label_mesh(body.data)
    paint(body.data, [PAL.get(l, (0, 0, 0)) for l in lab])
    paint(bow.data, [(0, 0, 1)] * len(bow.data.polygons))
    objs[tag] = (body, bow, bpy.data.objects["SKEL_Medusa_fbx" + tag].location.x)
scn.render.engine = "BLENDER_WORKBENCH"
scn.render.film_transparent = True
scn.render.image_settings.file_format = "PNG"; scn.render.image_settings.color_mode = "RGBA"
scn.view_settings.view_transform = "Standard"; scn.view_settings.look = "None"
scn.display.render_aa = "OFF"; scn.render.dither_intensity = 0
sh = scn.display.shading
sh.light = "FLAT"; sh.color_type = "VERTEX"; sh.show_backface_culling = True
for f in ("show_cavity", "show_object_outline", "show_shadows", "show_specular_highlight", "show_xray"):
    setattr(sh, f, False)
cam = bpy.data.objects.get("A1V3_Cam")
if cam is None:
    cam = bpy.data.objects.new("A1V3_Cam", bpy.data.cameras.new("A1V3_Cam")); scn.collection.objects.link(cam)
scn.camera = cam
cam.data.sensor_fit = "HORIZONTAL"
def look(loc, tgt):
    cam.location = loc; cam.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
d = lambda deg: (math.cos(math.radians(deg)), math.sin(math.radians(deg)))
VIEWS = {  # (type, cam offset rel. figure, target rel. figure, ortho scale/fov, res)
    "neck-front": ("O", (0, -2, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-front34L": ("O", (-1.41, -1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-front34R": ("O", (1.41, -1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-sideL": ("O", (2, 0, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-sideR": ("O", (-2, 0, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-rear": ("O", (0, 2, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-rear34L": ("O", (-1.41, 1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-rear34R": ("O", (1.41, 1.41, .40), (-.02, 0, .40), .16, (1024, 1024)),
    "neck-front-low": ("P", (-.02, -.45, .30), (-.02, 0, .40), 35, (1600, 900)),
    "neck-top55": ("O", (0, -2 * d(55)[0], .40 + 2 * d(55)[1]), (-.02, 0, .40), .16, (1024, 1024)),
    "k2-front-d300": ("P", (0, -3 * d(55)[0], .29 + 3 * d(55)[1]), (0, 0, .29), 35, (1920, 1080)),
    "k2-rear-d300": ("P", (0, 3 * d(55)[0], .29 + 3 * d(55)[1]), (0, 0, .29), 35, (1920, 1080)),
}
res = {}
for tag, (body, bow, ox) in objs.items():
    for t2, (b2, w2, _) in objs.items():
        for o in (b2, w2):
            o.hide_render = (t2 != tag)
    for o in scn.objects:
        if o.type == "MESH" and not o.name.endswith("_fbx" + tag):
            o.hide_render = True
    for name, (kind, loc, tgt, p, (rx, ry)) in VIEWS.items():
        cam.data.type = "ORTHO" if kind == "O" else "PERSP"
        if kind == "O":
            cam.data.ortho_scale = p
        else:
            cam.data.angle = math.radians(p)
        scn.render.resolution_x, scn.render.resolution_y = rx, ry
        look((loc[0] + ox, loc[1], loc[2]), (tgt[0] + ox, tgt[1], tgt[2]))
        path = os.path.join(OUT, f"id-cull-{name}-{tag}.png")
        scn.render.filepath = path
        bpy.ops.render.render(write_still=True)
        res.setdefault(name, {})[tag] = path
print(json.dumps({"renders": len(VIEWS) * 2, "backface_culling": sh.show_backface_culling}))
