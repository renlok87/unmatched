"""SMOKE-TEST INPUT ONLY: a synthetic Tripo-like GLB for exercising table_base_candidate.py end to end.

This is not a candidate and not art. It exists so the Blender stage can be run and read back before the
paid Tripo step happens; every output built from it is written outside the repository (C:/tmp/...).

Headless only:
  blender -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/smoke_synthetic_tray_glb.py -- <out.glb> [tex_px=2048] [long-x]

"long-x" puts the long side on glTF X (= Blender X) to exercise the 90-degree turn of the candidate script.

Mimics what a Tripo H3.1 + Smart UV + texture 2K + PBR export looks like (one node, one mesh with NORMAL and
TEXCOORD_0, one material with baseColor / metallicRoughness / normal images, Tripo-like scale ~1 m):
- a rock slab 0.83 x 1.0 x 0.19 m, long side along glTF Z (= Blender -Y after import, like the depth seen in
  the "left" view), a slightly domed top (the top band the candidate script flattens), downward spikes
  underneath, walls with a small outward lean and noise;
- ~7 000 quads (Tripo retopology target in tripo-stage-plan.json), Smart UV islands;
- deterministic procedural textures (fixed seed).
"""
import math
import sys
import tempfile
from pathlib import Path

import bmesh
import bpy
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]
out = Path(args[0])
px = int(args[1]) if len(args) > 1 else 2048
long_x = len(args) > 2 and args[2] == "long-x"
rng = np.random.default_rng(20260928)

bpy.ops.wm.read_factory_settings(use_empty=True)
me = bpy.data.meshes.new("tripo_node_synthetic")
obj = bpy.data.objects.new("tripo_node_synthetic", me)
bpy.context.scene.collection.objects.link(obj)
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=33, use_grid_fill=True)
W, L, H = (1.0, 0.83, 0.19) if long_x else (0.83, 1.0, 0.19)
for v in bm.verts:
    x, y, z = v.co.x * W, v.co.y * L, (v.co.z + 0.5) * H  # z in [0, H]
    top = z > H - 1e-6
    bottom = z < 1e-6
    if top:
        z += 0.006 * (1 - (2 * x / W) ** 2) * (1 - (2 * y / L) ** 2)  # dome
    else:
        lean = 1.0 + 0.04 * (1 - z / H)  # wider towards the bottom
        wob = 1.0 + 0.015 * math.sin(23 * z + 9 * y) * math.cos(17 * x)
        x, y = x * lean * wob, y * lean * wob
    if bottom:
        spikes = max(0.0, math.sin(13 * x + 0.7) * math.cos(11 * y + 0.3)) ** 2
        z -= 0.14 * spikes + 0.02 * math.sin(31 * x) * math.sin(29 * y)
    v.co = (x, y, z)
bm.to_mesh(me)
bm.free()
for p in me.polygons:
    p.use_smooth = True
bpy.context.view_layer.objects.active = obj
obj.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
bpy.ops.object.mode_set(mode="OBJECT")


def noise(shape, scale):
    h, w = shape
    small = rng.random((max(2, h // scale), max(2, w // scale)))
    ys = np.linspace(0, small.shape[0] - 1, h)
    xs = np.linspace(0, small.shape[1] - 1, w)
    y0, x0 = np.floor(ys).astype(int), np.floor(xs).astype(int)
    y1, x1 = np.minimum(y0 + 1, small.shape[0] - 1), np.minimum(x0 + 1, small.shape[1] - 1)
    fy, fx = (ys - y0)[:, None], (xs - x0)[None, :]
    a = small[y0][:, x0] * (1 - fx) + small[y0][:, x1] * fx
    b = small[y1][:, x0] * (1 - fx) + small[y1][:, x1] * fx
    return a * (1 - fy) + b * fy


n = 0.55 * noise((px, px), 64) + 0.3 * noise((px, px), 16) + 0.15 * noise((px, px), 4)
bc = np.stack([0.20 + 0.16 * n, 0.22 + 0.16 * n, 0.26 + 0.17 * n], axis=2)  # cold blue-grey stone (03 C-5)
rm = np.stack([np.zeros_like(n), 0.72 + 0.2 * n, np.zeros_like(n)], axis=2)
gy, gx = np.gradient(n)
nv = np.stack([-gx * 40, -gy * 40, np.ones_like(n)], axis=2)
nv /= np.linalg.norm(nv, axis=2, keepdims=True)
nrm = nv * 0.5 + 0.5
tmp = Path(tempfile.mkdtemp(prefix="tb-smoke-"))


def image(name, arr, colorspace):
    img = bpy.data.images.new(name, px, px, alpha=False)
    img.colorspace_settings.name = colorspace
    a = np.ones((px, px, 4), dtype=np.float32)
    a[..., :3] = arr
    img.pixels.foreach_set(a.ravel())
    img.filepath_raw = str(tmp / (name + ".png"))
    img.file_format = "PNG"
    img.save()
    img.reload()
    return img


mat = bpy.data.materials.new("tripo_node_synthetic_material")
mat.use_nodes = True
nt = mat.node_tree
bsdf = nt.nodes["Principled BSDF"]
t_bc = nt.nodes.new("ShaderNodeTexImage"); t_bc.image = image("synthetic_basecolor", bc, "sRGB")
t_rm = nt.nodes.new("ShaderNodeTexImage"); t_rm.image = image("synthetic_rm", rm, "Non-Color")
t_n = nt.nodes.new("ShaderNodeTexImage"); t_n.image = image("synthetic_normal", nrm, "Non-Color")
sep = nt.nodes.new("ShaderNodeSeparateColor")
nmap = nt.nodes.new("ShaderNodeNormalMap")
nt.links.new(t_bc.outputs["Color"], bsdf.inputs["Base Color"])
nt.links.new(t_rm.outputs["Color"], sep.inputs["Color"])
nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
nt.links.new(t_n.outputs["Color"], nmap.inputs["Color"])
nt.links.new(nmap.outputs["Normal"], bsdf.inputs["Normal"])
me.materials.append(mat)
out.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.export_scene.gltf(filepath=str(out), export_format="GLB", use_selection=True, export_yup=True,
                          export_normals=True, export_texcoords=True, export_materials="EXPORT",
                          export_image_format="AUTO")
print("SYNTHETIC_GLB", out, len(me.polygons), "faces")
