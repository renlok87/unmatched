"""H2 stage 4 — bake the high-poly onto the game mesh (headless Cycles).

    blender -b --factory-startup --python stage_bake.py -- <profile.json> <run_dir> [--cpu]

Input <run>/work/h2-uv.blend (HP_* high-poly in the authored frame with Tripo's 8K/PBR materials, LP_* game mesh with
UV0). Per pass one float image of bake.size px, filled part by part with selected-to-active (each LP part takes only
its own HP part, so a wing never picks up the torso), margin 0 (gutters are filled later by textures.py from the UV
ownership raster, so a later part never overwrites a neighbour's texels):
  normal  NORMAL, tangent space, OpenGL (+X +Y +Z); the HP shading normal includes Tripo's normal maps
  ao      AO, world AO distance bake.ao.distance_m, every HP part + occluder parts (Tripo base) visible, LP invisible
  bc      EMIT of Tripo's BaseColor texture (linear radiance = linear base colour)
  rm      EMIT of Tripo's metallicRoughness texture (raw: G roughness, B metallic)
Cage: bake.cage_extrusion_m / bake.max_ray_distance_m. Device per pass (bake.device_per_pass): GPU (OptiX/CUDA) when
available, else CPU; fixed seed and samples. Measured 2026-09-29: OptiX gives bit-identical AO between runs but
~1e-7 noise in the texture-sampling passes (normal, EMIT), which flips 10-863 texels by one 8-bit step; those passes run
on the CPU. Saves <run>/work/bake/<pass>.npy (float32 RGBA, Blender row order) and
<run>/reports/h2-bake-report.json.
"""

import sys
import time
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

C.require_background("stage_bake.py")
args = C.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
force_cpu = "--cpu" in args
P = C.load_profile(PROFILE_PATH)
BK = P["bake"]
t0 = time.time()
src_blend = RUN / "work" / "h2-uv.blend"
bpy.ops.wm.open_mainfile(filepath=str(src_blend))
scene = bpy.context.scene
device = C.set_cycles_device(scene, prefer_gpu=not force_cpu)
scene.cycles.seed = int(BK.get("seed", 0))
scene.cycles.use_denoising = False
scene.cycles.use_adaptive_sampling = False
scene.render.use_persistent_data = False
order = sorted(P["lowpoly"]["parts"], key=lambda n: int(n.rsplit("_", 1)[1]))
lp = {p: bpy.data.objects["LP_" + p] for p in order}
hp = {p: bpy.data.objects["HP_" + p] for p in order}
occluders = [o for o in scene.objects if o.type == "MESH" and o.get("h2_role") == "occluder"]
for o in lp.values():
    for attr in ("visible_camera", "visible_diffuse", "visible_glossy", "visible_transmission",
                 "visible_volume_scatter", "visible_shadow"):
        setattr(o, attr, False)
if scene.world is None:
    scene.world = bpy.data.worlds.new("h2_bake_world")
scene.world.light_settings.distance = float(BK["ao"]["distance_m"])
size = int(BK["size"])

bake_mat = bpy.data.materials.new("M_H2_Bake")
try:
    bake_mat.use_nodes = True
except AttributeError:
    pass
tex_node = bake_mat.node_tree.nodes.new("ShaderNodeTexImage")
bake_mat.node_tree.nodes.active = tex_node
for o in lp.values():
    o.data.materials.clear()
    o.data.materials.append(bake_mat)


def hp_nodes(o):
    mat = o.material_slots[0].material
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    imgs = {}
    for n in nt.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            name = n.image.name.lower()
            key = "bc" if "basecolor" in name else "rm" if "_rm" in name else "normal" if "normal" in name else None
            if key:
                imgs[key] = n
    return mat, nt, bsdf, imgs


# recolour rules (bake.recolor): a per-vertex mask on the high-poly part (inside the box of the authored frame and,
# optionally, of skin-like texture colour) blends the BaseColor toward target x luminance(BC) / reference luminance
recolor_nodes, recolor_report = {}, {}


def sock(node, io, name, typ):
    return next(x for x in getattr(node, io) if x.name == name and x.type == typ)


for rule in BK.get("recolor", []):
    o = hp[rule["part"]]
    me = o.data
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    inside = np.zeros(len(co))
    for box in rule.get("boxes") or [rule["box"]]:  # union of the rule's boxes (authored frame)
        lo_, hi_ = np.array(box["min"]), np.array(box["max"])
        inside = np.maximum(inside, np.all((co >= lo_) & (co <= hi_), axis=1).astype(np.float64))
    _mat, _nt, _bsdf, imgs = hp_nodes(o)
    img = imgs["bc"].image
    w, h = img.size
    px = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)
    uv = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[0].data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    lv = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", lv)
    first = np.full(len(me.vertices), -1)
    first[lv[::-1]] = np.arange(len(lv))[::-1]
    u = uv[first]
    col = px[np.clip((u[:, 1] * h).astype(int), 0, h - 1), np.clip((u[:, 0] * w).astype(int), 0, w - 1), :3]
    mx_, mn_ = col.max(1), col.min(1)
    sat = np.where(mx_ > 0, (mx_ - mn_) / np.maximum(mx_, 1e-6), 0)
    cond = np.ones(len(co))
    if rule.get("skin"):
        cond = ((mx_ > rule["skin"]["v_min"]) & (sat < rule["skin"]["s_max"])).astype(np.float64)
    mask = inside * cond
    attr = me.attributes.new("h2_recolor", "FLOAT", "POINT")
    attr.data.foreach_set("value", mask.astype(np.float32))
    target = [((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92 for c in rule["target_srgb"]]
    lum_ref = float(rule.get("luminance_ref", 0.35))
    strength = float(rule.get("strength", 1.0))

    def make(nt, bc_socket, target=target, lum_ref=lum_ref, strength=strength):
        at = nt.nodes.new("ShaderNodeAttribute")
        at.attribute_type = "GEOMETRY"
        at.attribute_name = "h2_recolor"
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        nt.links.new(bc_socket, bw.inputs["Color"])
        k = nt.nodes.new("ShaderNodeMath")
        k.operation = "MULTIPLY"
        k.inputs[1].default_value = 1.0 / lum_ref
        nt.links.new(bw.outputs["Val"], k.inputs[0])
        tint = nt.nodes.new("ShaderNodeMix")
        tint.data_type = "RGBA"
        tint.blend_type = "MULTIPLY"
        sock(tint, "inputs", "Factor", "VALUE").default_value = 1.0
        sock(tint, "inputs", "A", "RGBA").default_value = tuple(target) + (1.0,)
        comb = nt.nodes.new("ShaderNodeCombineColor")
        for ch in ("Red", "Green", "Blue"):
            nt.links.new(k.outputs["Value"], comb.inputs[ch])
        nt.links.new(comb.outputs["Color"], sock(tint, "inputs", "B", "RGBA"))
        fac = nt.nodes.new("ShaderNodeMath")
        fac.operation = "MULTIPLY"
        fac.inputs[1].default_value = strength
        nt.links.new(at.outputs["Fac"], fac.inputs[0])
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        nt.links.new(fac.outputs["Value"], sock(mix, "inputs", "Factor", "VALUE"))
        nt.links.new(bc_socket, sock(mix, "inputs", "A", "RGBA"))
        nt.links.new(sock(tint, "outputs", "Result", "RGBA"), sock(mix, "inputs", "B", "RGBA"))
        return sock(mix, "outputs", "Result", "RGBA")

    recolor_nodes[rule["part"]] = make
    recolor_report[rule["part"]] = {"vertices_masked": int((mask > 0).sum()), "vertices": len(co), "rule": rule}
saved_links = {}


def set_emission(kind):
    """kind None: restore; 'bc'/'rm': texture colour -> Emission Color, strength 1."""
    for p, o in hp.items():
        _mat, nt, bsdf, imgs = hp_nodes(o)
        for link in list(nt.links):
            if link.to_node == bsdf and link.to_socket.name == "Emission Color":
                nt.links.remove(link)
        if kind is None:
            bsdf.inputs["Emission Strength"].default_value = 0.0
            continue
        bsdf.inputs["Emission Strength"].default_value = 1.0
        if kind not in imgs:  # repair materials (plugs, caps): the BSDF inputs themselves
            if kind == "bc" and bsdf.inputs["Base Color"].is_linked:  # procedural colour (repair_ops.feather_material)
                nt.links.new(bsdf.inputs["Base Color"].links[0].from_socket, bsdf.inputs["Emission Color"])
            elif kind == "bc":
                bsdf.inputs["Emission Color"].default_value = tuple(bsdf.inputs["Base Color"].default_value)
            else:
                bsdf.inputs["Emission Color"].default_value = (0.0, bsdf.inputs["Roughness"].default_value,
                                                               bsdf.inputs["Metallic"].default_value, 1.0)
            continue
        src_socket = imgs[kind].outputs["Color"]
        if kind == "bc" and p in recolor_nodes:
            src_socket = recolor_nodes[p](nt, src_socket)
        nt.links.new(src_socket, bsdf.inputs["Emission Color"])


def bake_pass(name, btype, samples, extra=None):
    img = bpy.data.images.new("h2_bake_" + name, size, size, alpha=True, float_buffer=True, is_data=True)
    img.generated_color = (0, 0, 0, 0)
    tex_node.image = img
    scene.cycles.samples = samples
    want = (BK.get("device_per_pass") or {}).get(name, "GPU")
    scene.cycles.device = "GPU" if (want == "GPU" and device["device"] == "GPU" and not force_cpu) else "CPU"
    per_part = {}
    for p in order:
        for o in scene.objects:
            o.select_set(False)
        hp[p].select_set(True)
        lp[p].select_set(True)
        bpy.context.view_layer.objects.active = lp[p]
        t = time.time()
        kw = dict(type=btype, use_selected_to_active=True, cage_extrusion=float(BK["cage_extrusion_m"]),
                  max_ray_distance=float(BK["max_ray_distance_m"]), margin=0, use_clear=False,
                  target="IMAGE_TEXTURES", save_mode="INTERNAL")
        if extra:
            kw.update(extra)
        bpy.ops.object.bake(**kw)
        per_part[p] = C.r(time.time() - t, 2)
    px = np.empty(size * size * 4, np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(size, size, 4)
    out = RUN / "work" / "bake"
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / ("%s.npy" % name), px)  # float32: float16 turned 1e-7 GPU noise into 1-ulp steps
    stats = {"seconds_per_part": per_part, "samples": samples, "type": btype, "device": scene.cycles.device,
             "texels_written": int((px[..., 3] > 0).sum()),
             "rgb_mean_written": C.rv(px[px[..., 3] > 0][:, :3].mean(0), 5) if (px[..., 3] > 0).any() else None,
             "npy": C.rel(out / ("%s.npy" % name))}
    bpy.data.images.remove(img)
    print("baked", name, stats["texels_written"], flush=True)
    return stats


report = {"schema": "unmatched.h2-bake.bake-report/1", "profile": C.rel(PROFILE_PATH),
          "profile_sha256": C.sha256(PROFILE_PATH), "blender": bpy.app.version_string, "device": device,
          "input_blend_sha256": C.sha256(src_blend), "size": size,
          "cage_extrusion_m": float(BK["cage_extrusion_m"]), "max_ray_distance_m": float(BK["max_ray_distance_m"]),
          "ao_distance_m": float(BK["ao"]["distance_m"]), "seed": scene.cycles.seed,
          "occluders": [o.name for o in occluders], "recolor": recolor_report, "passes": {}}
set_emission(None)
report["passes"]["normal"] = bake_pass("normal", "NORMAL", int(BK["samples"]["normal"]),
                                       dict(normal_space="TANGENT", normal_r="POS_X", normal_g="POS_Y",
                                            normal_b="POS_Z"))
report["passes"]["ao"] = bake_pass("ao", "AO", int(BK["samples"]["ao"]))
set_emission("bc")
report["passes"]["bc"] = bake_pass("bc", "EMIT", int(BK["samples"]["emit"]))
set_emission("rm")
report["passes"]["rm"] = bake_pass("rm", "EMIT", int(BK["samples"]["emit"]))
set_emission(None)
report["seconds"] = C.r(time.time() - t0, 1)
C.write_json(RUN / "reports" / "h2-bake-report.json", report)
print(C.STAGE_MARKER, "bake", report["seconds"], flush=True)
