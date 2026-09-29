"""Stage bake (headless, Cycles): high-poly (textured Tripo GLB, same repairs) -> low-poly atlas maps.

    blender -b --factory-startup --python stage_bake.py -- <profile.json> <run_dir> [--only=PASS,..] [--parts=a,b]

Selected-to-active per low part from its own high part(s) (a ray never lands on a neighbouring part), cage =
extrusion along the low normals (profile bake.cage_extrusion_m / max_ray_distance_m, per-part overrides), into one
image per pass (use_clear off: every part writes only its own islands + margin). Passes:
  NORMAL  tangent space, Blender/OpenGL convention (+X +Y +Z); the high material keeps its Tripo normal map, so the
          baked normal = high-poly geometry + Tripo detail normal (checked by the A/B probe below)
  AO      Cycles ambient occlusion at the high-poly hit point, occluders = all kept high parts (+ base); the low
          objects are invisible to rays
  BC      emission rewire of the Tripo BaseColor texture (EMIT), float linear
  MR      emission rewire of the Tripo metallicRoughness texture (R unused = 1, G roughness, B metallic), float
  HIT     emission 1.0: texels whose ray hit the high part (miss = 0) for the cage check
Output: work/bake/<PASS>.npy (float16 H x W x C, row 0 = top), reports/bake-report.json.
"""

import sys
import time
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl  # noqa: E402
import pure as P  # noqa: E402
import repairs  # noqa: E402

bl.require_background("stage_bake.py")
args = bl.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
opts = dict(a[2:].split("=", 1) for a in args[2:] if a.startswith("--") and "=" in a)
profile = P.load_json(PROFILE_PATH)
paths = P.run_paths(RUN)
bake_dir = paths["work"] / "bake"
bake_dir.mkdir(parents=True, exist_ok=True)
cfg = profile["bake"]
t0 = time.time()

bpy.ops.wm.open_mainfile(filepath=str(paths["work"] / "h2-lowpoly.blend"))
scene = bpy.context.scene
low = {o.name: o for o in scene.objects if o.type == "MESH" and o.name.startswith("LP_")}
src = P.repo_path(profile["sources"]["tex_glb"]["path"])
if P.sha256(src) != profile["sources"]["tex_glb"]["sha256"]:
    raise RuntimeError("textured GLB sha256 mismatch")
high, coll_high = bl.import_glb_parts(src, "H2_HIGH_TEX")
repair_log = repairs.apply_geometry_repairs(high, profile)

# ------------------------------------------------------------------ Cycles, device
scene.render.engine = "CYCLES"
device = "CPU"
if opts.get("device", cfg.get("device", "GPU")) == "GPU":
    prefs = bpy.context.preferences.addons["cycles"].preferences
    for backend in ("OPTIX", "CUDA"):
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
        except TypeError:
            continue
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for d in prefs.devices:
                d.use = d.type == backend
            device = "GPU:%s:%s" % (backend, gpus[0].name)
            scene.cycles.device = "GPU"
            break
scene.cycles.seed = 0
scene.cycles.use_denoising = False
scene.cycles.use_adaptive_sampling = False
scene.render.bake.margin = int(cfg["margin_px"])
scene.render.bake.margin_type = cfg.get("margin_type", "ADJACENT_FACES")
scene.render.bake.use_clear = False
scene.render.bake.target = "IMAGE_TEXTURES"
world = bpy.data.worlds.new("h2_bake_world")
scene.world = world
world.light_settings.distance = float(cfg["ao_distance_m"])
for o in low.values():
    o.visible_camera = True
    o.visible_diffuse = o.visible_glossy = o.visible_transmission = False
    o.visible_volume_scatter = o.visible_shadow = False

size = int(profile["uv"]["atlas_px"])

# ------------------------------------------------------------------ target material on every low part
target_mat = bpy.data.materials.new("H2_BAKE_TARGET")
target_mat.use_nodes = True
tnode = target_mat.node_tree.nodes.new("ShaderNodeTexImage")
tnode.name = "h2_target"
target_mat.node_tree.nodes.active = tnode
for o in low.values():
    o.data.materials.clear()
    o.data.materials.append(target_mat)


def new_image(name, colour, channels_note):
    img = bpy.data.images.new(name, size, size, alpha=False, float_buffer=True)
    img.colorspace_settings.name = "Non-Color" if channels_note != "linear-colour" else "Linear Rec.709"
    fill = np.empty((size * size, 4), dtype=np.float32)
    fill[:] = colour
    img.pixels.foreach_set(fill.ravel())
    return img


# ------------------------------------------------------------------ high material rewiring
def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeBsdfPrincipled")


def output(mat):
    return next(n for n in mat.node_tree.nodes if n.bl_idname == "ShaderNodeOutputMaterial" and n.is_active_output)


def source_socket(mat, kind):
    nt = mat.node_tree
    bsdf = principled(mat)
    if kind == "BC":
        link = bsdf.inputs["Base Color"].links
        return link[0].from_socket if link else None
    if kind == "MR":
        rough = bsdf.inputs["Roughness"].links
        if rough and rough[0].from_node.bl_idname == "ShaderNodeSeparateColor":
            sep = rough[0].from_node
            link = sep.inputs[0].links
            return link[0].from_socket if link else None
        return None
    raise KeyError(kind)


state = {}
for name, obj in high.items():
    for slot in obj.material_slots:
        mat = slot.material
        if mat.name in state:
            continue
        nt = mat.node_tree
        em = nt.nodes.new("ShaderNodeEmission")
        em.name = "h2_emit"
        em.inputs["Strength"].default_value = 1.0
        state[mat.name] = {"mat": mat, "emit": em, "bsdf_out": principled(mat).outputs[0], "out": output(mat),
                           "BC": source_socket(mat, "BC"), "MR": source_socket(mat, "MR")}


def wire(kind):
    for st in state.values():
        nt = st["mat"].node_tree
        for l in list(st["out"].inputs["Surface"].links):
            nt.links.remove(l)
        em = st["emit"]
        for l in list(em.inputs["Color"].links):
            nt.links.remove(l)
        if kind == "SHADER":
            nt.links.new(st["bsdf_out"], st["out"].inputs["Surface"])
            continue
        if kind == "HIT":
            em.inputs["Color"].default_value = (1, 1, 1, 1)
        else:
            sock = st[kind]
            if sock is None:
                raise RuntimeError("material %s has no %s texture" % (st["mat"].name, kind))
            nt.links.new(sock, em.inputs["Color"])
        nt.links.new(em.outputs[0], st["out"].inputs["Surface"])


# ------------------------------------------------------------------ bake groups
groups = []
for lname in sorted(low, key=lambda n: bl.part_key(n)):
    part = lname[3:]
    if part in high:
        sources = [part]
    else:
        sources = cfg["extra_sources"][lname]
    ov = cfg.get("overrides", {}).get(part, {})
    groups.append({"low": lname, "high": sources,
                   "cage_extrusion_m": float(ov.get("cage_extrusion_m", cfg["cage_extrusion_m"])),
                   "max_ray_distance_m": float(ov.get("max_ray_distance_m", cfg["max_ray_distance_m"]))})
if "parts" in opts:
    wanted = set(opts["parts"].split(","))
    groups = [g for g in groups if g["low"] in wanted or g["low"][3:] in wanted]

PASSES = {
    "NORMAL": {"type": "NORMAL", "wire": "SHADER", "samples": int(cfg["samples"]["NORMAL"]), "fill": (0.5, 0.5, 1.0, 1.0), "space": "non-colour"},
    "AO": {"type": "AO", "wire": "SHADER", "samples": int(cfg["samples"]["AO"]), "fill": (1.0, 1.0, 1.0, 1.0), "space": "non-colour"},
    "BC": {"type": "EMIT", "wire": "BC", "samples": int(cfg["samples"]["EMIT"]), "fill": (0.0, 0.0, 0.0, 1.0), "space": "linear-colour"},
    "MR": {"type": "EMIT", "wire": "MR", "samples": int(cfg["samples"]["EMIT"]), "fill": (0.0, 0.0, 0.0, 1.0), "space": "non-colour"},
    "HIT": {"type": "EMIT", "wire": "HIT", "samples": 1, "fill": (0.0, 0.0, 0.0, 1.0), "space": "non-colour"},
}
only = opts.get("only", "NORMAL,AO,BC,MR,HIT,POS").split(",")
report = {"schema": "unmatched.h2-bake.bake/1", "device": device, "blender": bpy.app.version_string,
          "atlas_px": size, "margin_px": scene.render.bake.margin, "margin_type": scene.render.bake.margin_type,
          "ao_distance_m_tripo_frame": world.light_settings.distance, "groups": groups, "passes": {},
          "repairs": repair_log}


def bake_pass(pname):
    spec = PASSES[pname]
    img = new_image("H2_" + pname, spec["fill"], spec["space"])
    tnode.image = img
    wire(spec["wire"])
    scene.cycles.samples = spec["samples"]
    tp = time.time()
    for g in groups:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        for h in g["high"]:
            high[h].select_set(True)
        lo = low[g["low"]]
        lo.select_set(True)
        bpy.context.view_layer.objects.active = lo
        kw = dict(type=spec["type"], use_selected_to_active=True, cage_extrusion=g["cage_extrusion_m"],
                  max_ray_distance=g["max_ray_distance_m"], margin=scene.render.bake.margin,
                  margin_type=scene.render.bake.margin_type, use_clear=False, target="IMAGE_TEXTURES")
        if spec["type"] == "NORMAL":
            kw.update(normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z")
        bpy.ops.object.bake(**kw)
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(size, size, 4)[::-1]  # Blender rows start at the bottom
    keep = {"NORMAL": 3, "AO": 1, "BC": 3, "MR": 3, "HIT": 1}[pname]
    arr = px[..., :keep].astype(np.float16)
    np.save(bake_dir / ("%s.npy" % pname), arr)
    report["passes"][pname] = {"type": spec["type"], "samples": spec["samples"], "seconds": round(time.time() - tp, 1),
                               "file": P.rel(bake_dir / ("%s.npy" % pname)), "dtype": "float16", "rows": "top first",
                               "channel_mean": [P.r(arr[..., c].astype(np.float32).mean(), 4) for c in range(keep)]}
    bpy.data.images.remove(img)
    print("baked", pname, report["passes"][pname]["seconds"], round(time.time() - t0, 1), flush=True)


def bake_pos():
    """Tripo-frame position of every covered texel: EMIT bake of each low object onto itself (no rays, so the
    filled holes and the ray misses get a position too). Used by stage textures for the phantom repaint."""
    img = new_image("H2_POS", (0.0, 0.0, 0.0, 1.0), "non-colour")
    tnode.image = img
    nt = target_mat.node_tree
    out = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeOutputMaterial")
    saved = [(l.from_socket, l.to_socket) for l in out.inputs["Surface"].links]
    for l in list(out.inputs["Surface"].links):
        nt.links.remove(l)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    em = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(geo.outputs["Position"], em.inputs["Color"])
    nt.links.new(em.outputs[0], out.inputs["Surface"])
    scene.cycles.samples = 1
    tp = time.time()
    for g in groups:
        for o in bpy.context.view_layer.objects:
            o.select_set(False)
        lo = low[g["low"]]
        lo.select_set(True)
        bpy.context.view_layer.objects.active = lo
        bpy.ops.object.bake(type="EMIT", use_selected_to_active=False, margin=scene.render.bake.margin,
                            margin_type=scene.render.bake.margin_type, use_clear=False, target="IMAGE_TEXTURES")
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    np.save(bake_dir / "POS.npy", px.reshape(size, size, 4)[::-1][..., :3].astype(np.float32))
    for l in list(out.inputs["Surface"].links):
        nt.links.remove(l)
    for a, b in saved:
        nt.links.new(a, b)
    nt.nodes.remove(geo)
    nt.nodes.remove(em)
    report["passes"]["POS"] = {"type": "EMIT (low onto itself, Geometry.Position)", "samples": 1,
                               "seconds": round(time.time() - tp, 1), "file": P.rel(bake_dir / "POS.npy"),
                               "dtype": "float32", "rows": "top first", "frame": "Tripo (low parts before seat)"}
    bpy.data.images.remove(img)
    print("baked POS", report["passes"]["POS"]["seconds"], flush=True)


for pname in only:
    if pname == "POS":
        bake_pos()
    else:
        bake_pass(pname)

# A/B probe: is the Tripo detail normal map part of the baked normal? (one small part, map unlinked)
probe = cfg.get("normal_map_probe_part")
if probe and "NORMAL" in only and "parts" not in opts:
    g = next(g for g in groups if g["low"] == "LP_" + probe)
    saved_groups = list(groups)
    groups[:] = [g]
    unlinked = []
    for slot in high[probe].material_slots:
        nt = slot.material.node_tree
        bsdf = principled(slot.material)
        for l in list(bsdf.inputs["Normal"].links):
            unlinked.append((l.from_socket, bsdf.inputs["Normal"], nt))
            nt.links.remove(l)
    img = new_image("H2_NORMAL_PROBE", (0.5, 0.5, 1.0, 1.0), "non-colour")
    tnode.image = img
    wire("SHADER")
    scene.cycles.samples = int(cfg["samples"]["NORMAL"])
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    high[probe].select_set(True)
    low[g["low"]].select_set(True)
    bpy.context.view_layer.objects.active = low[g["low"]]
    bpy.ops.object.bake(type="NORMAL", use_selected_to_active=True, cage_extrusion=g["cage_extrusion_m"],
                        max_ray_distance=g["max_ray_distance_m"], margin=scene.render.bake.margin,
                        margin_type=scene.render.bake.margin_type, use_clear=False, target="IMAGE_TEXTURES",
                        normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y", normal_b="POS_Z")
    px = np.empty(size * size * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    without = px.reshape(size, size, 4)[::-1][..., :3]
    full = np.load(bake_dir / "NORMAL.npy").astype(np.float32)
    part_id = np.load(paths["work"] / "uv-part-id.npy")
    names = list(np.load(paths["work"] / "uv-triangles.npz")["names"])
    m = part_id == names.index(probe) + 1
    diff = np.abs(full[m] - without[m]).max(axis=1)
    report["normal_map_probe"] = {"part": probe, "texels": int(m.sum()),
                                  "mean_abs_diff": P.r(diff.mean(), 4), "p95_abs_diff": P.r(np.percentile(diff, 95), 4),
                                  "share_diff_above_0.02": P.r((diff > 0.02).mean(), 4),
                                  "note": "difference of the baked tangent normal with the Tripo normal map linked vs unlinked on the high material: > 0 means the detail normal map is carried into the bake"}
    for fs, ts, nt in unlinked:
        nt.links.new(fs, ts)
    groups[:] = saved_groups
    bpy.data.images.remove(img)

report["seconds"] = round(time.time() - t0, 1)
out = paths["reports"] / "bake-report.json"
if "only" in opts or "parts" in opts:
    out = paths["reports"] / "bake-report-partial.json"
P.write_json(out, report)
print(P.STAGE_MARKER, "bake", device, report["seconds"])
