"""Stage inspect (headless): both Tripo H2 GLBs, part matching, geometry identity, winding, preview renders.

    blender -b --factory-startup --python stage_inspect.py -- <profile.json> <run_dir>

Writes reports/inspect-sources.json and work/inspect_png/*.png (Workbench; stage sheets composes labelled sheets).
The source GLBs are only read (sha256 checked before and after).
"""

import math
import sys
import time
from pathlib import Path

import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bl  # noqa: E402
import pure as P  # noqa: E402

bl.require_background("stage_inspect.py")
args = bl.script_args()
PROFILE_PATH, RUN = Path(args[0]).resolve(), Path(args[1]).resolve()
profile = P.load_json(PROFILE_PATH)
paths = P.run_paths(RUN)
for key in ("reports", "preview"):
    paths[key].mkdir(parents=True, exist_ok=True)
OUT = paths["work"] / "inspect_png"  # raw Workbench renders; stage sheets writes the labelled sheets to preview/
OUT.mkdir(parents=True, exist_ok=True)
t0 = time.time()

src = profile["sources"]
parts_glb = P.repo_path(src["parts_glb"]["path"])
tex_glb = P.repo_path(src["tex_glb"]["path"])
hashes = {}
for key, path in (("parts_glb", parts_glb), ("tex_glb", tex_glb)):
    h = P.sha256(path)
    if h != src[key]["sha256"]:
        raise RuntimeError("%s sha256 %s != profile %s" % (path, h, src[key]["sha256"]))
    hashes[key] = {"path": P.rel(path), "sha256": h, "bytes": path.stat().st_size}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
parts, coll_parts = bl.import_glb_parts(parts_glb, "H2_PARTS")
tex, coll_tex = bl.import_glb_parts(tex_glb, "H2_TEX")
if sorted(parts) != sorted(tex):
    raise RuntimeError("part sets differ: %s vs %s" % (sorted(parts), sorted(tex)))

report = {"schema": "unmatched.h2-bake.inspect/1", "sources": hashes, "parts": {}, "blender": bpy.app.version_string}


def image_info(img, stride=16):
    w, h = img.size
    info = {"image": img.name, "px": [w, h], "colorspace": img.colorspace_settings.name}
    if w and h:
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)[::stride, ::stride]
        info["channel_mean"] = [round(float(px[..., c].mean()), 4) for c in range(4)]
        info["channel_std"] = [round(float(px[..., c].std()), 4) for c in range(4)]
    return info


arrays_parts = {}
for name in parts:
    a, b = parts[name], tex[name]
    co_a, tris_a, _ = bl.mesh_arrays(a)
    co_b, tris_b, _ = bl.mesh_arrays(b)
    arrays_parts[name] = (co_a, tris_a)
    lo, hi = co_a.min(axis=0), co_a.max(axis=0)
    # exact identity: positions quantised to 1e-7 m, triangles as sorted welded index triples
    qa = np.round(co_a / 1e-7).astype(np.int64)
    qb = np.round(co_b / 1e-7).astype(np.int64)
    ua, ia = np.unique(qa, axis=0, return_inverse=True)
    ub, ib = np.unique(qb, axis=0, return_inverse=True)
    same_positions = ua.shape == ub.shape and bool(np.array_equal(ua, ub))
    same_tris = False
    if same_positions:
        ta = np.sort(ia.reshape(-1)[tris_a], axis=1)
        tb = np.sort(ib.reshape(-1)[tris_b], axis=1)
        ta = ta[np.lexsort(ta.T[::-1])]
        tb = tb[np.lexsort(tb.T[::-1])]
        same_tris = ta.shape == tb.shape and bool(np.array_equal(ta, tb))
    entry = {
        "triangles": int(len(tris_a)), "vertices": int(len(co_a)), "vertices_textured": int(len(co_b)),
        "welded_positions": int(len(ua)), "bbox_min_m": P.rv(lo, 5), "bbox_max_m": P.rv(hi, 5),
        "size_m": P.rv(hi - lo, 5), "centre_m": P.rv((lo + hi) / 2, 5),
        "identity_with_textured": {"same_welded_positions_1e-7": same_positions, "same_triangles": same_tris},
        "topology_untextured": bl.edge_topology(a),
        "opposed_corner_normal_area_share": bl.opposed_corner_normal_share(a),
        "uv_layers_textured": [u.name for u in b.data.uv_layers],
        "materials_textured": [],
    }
    for slot in b.material_slots:
        mat = slot.material
        m = {"material": mat.name if mat else None, "images": {}}
        if mat and mat.use_nodes:
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image:
                    role = "?"
                    for link in node.outputs[0].links + node.outputs[1].links:
                        role = link.to_node.bl_idname + ":" + link.to_socket.name
                    m["images"][node.image.name] = image_info(node.image) | {"link": role}
        entry["materials_textured"].append(m)
    report["parts"][name] = entry
    print("part", name, entry["triangles"], same_positions, same_tris, round(time.time() - t0, 1), flush=True)

height = max(v[0][:, 2].max() for v in arrays_parts.values()) - min(v[0][:, 2].min() for v in arrays_parts.values())
scores = bl.ray_escape_scores(arrays_parts, sample_per_part=int(profile["inspect"]["orientation_samples_per_part"]),
                              height=height)
for name, s in scores.items():
    report["parts"][name]["orientation_ray_escape"] = s
all_co = np.concatenate([v[0] for v in arrays_parts.values()])
report["figure"] = {"bbox_min_m": P.rv(all_co.min(axis=0), 5), "bbox_max_m": P.rv(all_co.max(axis=0), 5),
                    "triangles": int(sum(len(v[1]) for v in arrays_parts.values())),
                    "frame": "Blender glTF import: Z up, figure faces -Y (glTF +Z forward), metres of Tripo normalisation"}
report["identity_all_parts"] = all(p["identity_with_textured"]["same_triangles"] for p in report["parts"].values())
flip_below = float(profile["inspect"]["flip_below_score"])
report["inside_out_parts"] = sorted(n for n, s in scores.items() if s["score"] is not None and s["score"] < flip_below)
print("orientation done", round(time.time() - t0, 1), flush=True)

# ------------------------------------------------------------------ preview renders (Workbench)
lo, hi = all_co.min(axis=0), all_co.max(axis=0)
centre = (lo + hi) / 2
size = float(max(hi[2] - lo[2], hi[0] - lo[0], hi[1] - lo[1])) * 1.08
cam = bl.new_camera(scene)
cam.data.type = "ORTHO"
cam.data.ortho_scale = size
scene.render.engine = "BLENDER_WORKBENCH"
shading = scene.display.shading
shading.light = "STUDIO"
shading.show_backface_culling = False
scene.render.film_transparent = False
scene.view_settings.view_transform = "Standard"
world = bpy.data.worlds.new("inspect_world")
scene.world = world
world.color = (0.05, 0.05, 0.055)
views = {"front": (0, -1, 0), "right": (-1, 0, 0), "back": (0, 1, 0), "left": (1, 0, 0)}
frames = {}


def render(name, res):
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.filepath = str(OUT / (name + ".png"))
    bpy.ops.render.render(write_still=True)
    frames[name] = {"png": P.rel(scene.render.filepath), "resolution": list(res)}


coll_tex.hide_render = False
coll_parts.hide_render = True
shading.color_type = "TEXTURE"
for view, d in views.items():
    bl.look_at(cam, centre, d, 3.0)
    render("tex8k_%s" % view, (900, 1000))
coll_tex.hide_render = True
coll_parts.hide_render = False
shading.color_type = "OBJECT"
rng = np.random.default_rng(7)
for name, obj in parts.items():
    obj.color = (0.62, 0.62, 0.62, 1.0)
for name, obj in parts.items():
    obj.color = (0.9, 0.08, 0.05, 1.0)
    for view in ("front", "right", "back"):
        bl.look_at(cam, centre, views[view], 3.0)
        render("part_%s_%s" % (name.rsplit("_", 1)[1], view), (270, 300))
    obj.color = (0.62, 0.62, 0.62, 1.0)
report["frames"] = frames
report["seconds"] = round(time.time() - t0, 1)
for key, path in (("parts_glb", parts_glb), ("tex_glb", tex_glb)):
    if P.sha256(path) != hashes[key]["sha256"]:
        raise RuntimeError("source changed during inspect: %s" % path)
P.write_json(paths["reports"] / "inspect-sources.json", report)
print(P.STAGE_MARKER, "inspect", round(time.time() - t0, 1))
