"""ASSET-TABLE-BASE-001, Blender stage: static tray candidate from a Tripo GLB (rock underside only).

Headless only (never touches live Blender sessions):
  blender -b --factory-startup --python-exit-code 1 \
      --python art/pipeline-candidates/ASSET-TABLE-BASE-001/scripts/table_base_candidate.py -- <params.json>

Reuses the helpers of tools/tripo-pipeline/blender/static_prop_candidate.py (clean-up, winding, UV analysis,
BC/N/ORM conversion, AO bake, UM_FBX_v1 export, determinism). That file is executed without its trailing
main() call and its LF sha256 is recorded; it is not modified. What differs from a barrel-like prop
(04 section 3.6; every number is PROPOSED, nothing here is an art decision):

  pivot    board centre = (0, 0), Z = 0 = play plane. The tray lies entirely below its flat top at top_z_uu.
  axes     long side along .blend Y (UM_FBX_v1 turns .blend Y into export X = UE X, the long axis of the
           ART-005 board mesh). A source whose long axis is X is turned 90 degrees about Z first.
  scale    non-uniform XY: the outline of the top band is fitted to footprint_uu_blend_xy (default 656 x 756 =
           board 556 x 656 + rim 50 on every side, in .blend axes). Z: depth_uu from the top plane to the lowest
           point, or null = source proportions (sqrt(sx * sy)).
  top      vertices above the cut (top_band_frac of the height below the highest point) are moved down onto
           the top plane, zero-length edges collapse. Faces that end up in the plane facing down (folded walls)
           are counted and fail the run; they are not hidden.
  normals  Tripo corner normals are transformed with the inverse transpose of the linear map (non-uniform
           scale) and written back; faces lying in the top plane get +Z.
  checks   footprint, top plane, centring, round trip, one slot, UV0, closed manifold, no board horizontal face
           within coplanar_min_uu of the top plane (z-fighting). Measured, not gated: flat-top rim width by ray
           casts from the board outline, board undertray enclosed by the tray.
  collision none (04 3.6: not interactive); the board keeps its own selection collision.

params.json (paths absolute or repo-relative; repo = four folders above this file unless repo_root is set):
  source_glb, out_dir, asset_name (SM_TableBase), texture_prefix (T_TableBase), material_name (M_TableBase),
  fbx_preset (blender/_tools/presets/UM_FBX_v1.json), texture_size (2048), footprint_uu_blend_xy ([656, 756]),
  top_z_uu (-3), top_band_frac (0.03), footprint_band_frac (= top_band_frac), depth_uu (null), bake_ao (true),
  ao_samples (64), ao_distance_m (0.3), board_bounds_json (measure_board_fbx.py output; optional),
  rim_proposed_uu ([40, 60]), coplanar_min_uu (0.5), require_closed_manifold (true), normal_padding_px_source (32)

Outputs in out_dir (same layout and report keys the CLI adopt stage reads for static_prop_candidate.py):
  work/<asset>.blend, work/<asset>_uv0_layout.png
  export/<asset>.fbx (UM_FBX_v1), export/<prefix>_BC.png (sRGB), _N.png (Linear, DirectX), _ORM.png (Linear)
  reports/candidate-report.json (schema unmatched.tripo-pipeline.table-base-candidate/1, status "measured")
  preview/<asset>_uv0_layout.jpg (1024 px)
Game-camera and ortho previews come from table_base_preview.py on the exported FBX; the independent read-back
from tools/tripo-pipeline/blender/check_static_prop_fbx.py.
"""

import json
import math
import sys
import types
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

HERE = Path(__file__).resolve()
REPO = HERE.parents[4]  # <repo>/art/pipeline-candidates/<asset>/scripts/<this file>
SPC = REPO / "tools" / "tripo-pipeline" / "blender" / "static_prop_candidate.py"
SCHEMA = "unmatched.tripo-pipeline.table-base-candidate/1"


def load_helpers():
    text = SPC.read_text(encoding="utf-8")
    body = text.rstrip()
    if not body.endswith("\nmain()"):
        raise SystemExit("static_prop_candidate.py no longer ends with a bare main() call: %s" % SPC)
    ns = {"__name__": "static_prop_candidate_helpers", "__file__": str(SPC)}
    exec(compile(body[:-len("main()")], str(SPC), "exec"), ns)
    return types.SimpleNamespace(**ns)


S = load_helpers()
r = S.r

DEFAULTS = {
    "asset_name": "SM_TableBase", "texture_prefix": "T_TableBase", "material_name": "M_TableBase",
    "fbx_preset": "blender/_tools/presets/UM_FBX_v1.json", "texture_size": 2048,
    "footprint_uu_blend_xy": [656.0, 756.0], "top_z_uu": -3.0, "top_band_frac": 0.03, "footprint_band_frac": None,
    "depth_uu": None, "bake_ao": True, "ao_samples": 64, "ao_distance_m": 0.3, "board_bounds_json": None,
    "rim_proposed_uu": [40.0, 60.0], "coplanar_min_uu": 0.5, "require_closed_manifold": True,
    "normal_padding_px_source": 32,
}


def load_params():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if not argv:
        raise SystemExit("params.json required after --")
    pp = Path(argv[0]).resolve()
    P = dict(DEFAULTS)
    P.update(json.loads(pp.read_text(encoding="utf-8")))
    raw = P.get("repo_root")
    root = REPO if raw is None else (Path(raw) if Path(raw).is_absolute() else pp.parent / raw)
    P["repo_root"] = root.resolve()
    for key in ("source_glb", "out_dir", "fbx_preset", "board_bounds_json"):
        if P.get(key):
            p = Path(P[key])
            P[key] = p if p.is_absolute() else P["repo_root"] / p
    missing = [k for k in ("source_glb", "fbx_preset", "board_bounds_json") if P.get(k) and not P[k].is_file()]
    if missing:
        raise SystemExit("missing input(s): %s" % ", ".join("%s=%s" % (k, P[k]) for k in missing))
    if P["footprint_band_frac"] is None:
        P["footprint_band_frac"] = P["top_band_frac"]
    return P


# ----------------------------------------------------------------------------- board reference
def export_to_blend_xy(lo, hi):
    """UM_FBX_v1 export frame (FBX read back in Blender) -> .blend frame of this script.
    Export rotates .blend data +90 deg about Z: (x_b, y_b) -> (-y_b, x_b); inverse: x_b = y_e, y_b = -x_e."""
    return [lo[1], -hi[0], lo[2]], [hi[1], -lo[0], hi[2]]


def board_reference(P):
    if not P.get("board_bounds_json"):
        return None
    b = json.loads(Path(P["board_bounds_json"]).read_text(encoding="utf-8"))
    whole = export_to_blend_xy(b["bounds_min_uu_export_frame"], b["bounds_max_uu_export_frame"])
    under = [p for p in b["parts"] if p["name"].startswith("Rock_Undertray")]
    ref = {"bounds_json": S.rel(P["board_bounds_json"], P), "fbx": b["fbx"], "fbx_sha256": b["fbx_sha256"],
           "whole_uu_blend": {"min": whole[0], "max": whole[1]},
           "size_uu_export_frame": b["size_uu_export_frame"],
           "horizontal_face_levels_uu": [{"z_uu": h["z_uu"], "facing": h["facing"], "parts": h["parts"]}
                                         for h in b["horizontal_face_levels_uu"]]}
    if under:
        u = export_to_blend_xy(under[0]["bounds_min_uu"], under[0]["bounds_max_uu"])
        ref["undertray_uu_blend"] = {"min": u[0], "max": u[1]}
    return ref


# ----------------------------------------------------------------------------- geometry steps
def corner_normals(me):
    cn = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.corner_normals.foreach_get("vector", cn)
    return cn.reshape(-1, 3).astype(np.float64)


def vertex_array(me):
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get("co", co)
    return co.reshape(-1, 3)


def fit_and_flatten(obj, P):
    """Rotate (if needed), fit, flatten the top band; returns a measurement record."""
    me = obj.data
    co = vertex_array(me)
    lo0, hi0 = co.min(0), co.max(0)
    d0 = hi0 - lo0
    turn = bool(d0[0] > d0[1])
    R3 = np.array(Matrix.Rotation(math.radians(90.0 if turn else 0.0), 3, "Z"))
    cr = co @ R3.T
    lo, hi = cr.min(0), cr.max(0)
    dims = hi - lo
    z_cut = hi[2] - float(P["top_band_frac"]) * dims[2]
    band = cr[cr[:, 2] >= hi[2] - float(P["footprint_band_frac"]) * dims[2]]
    flo, fhi = band.min(0), band.max(0)
    tx, ty = (float(v) / 100.0 for v in P["footprint_uu_blend_xy"])
    sx, sy = tx / (fhi[0] - flo[0]), ty / (fhi[1] - flo[1])
    depth_src = z_cut - lo[2]
    sz = (float(P["depth_uu"]) / 100.0) / depth_src if P.get("depth_uu") else math.sqrt(sx * sy)
    cx, cy = (flo[0] + fhi[0]) / 2, (flo[1] + fhi[1]) / 2
    top_m = float(P["top_z_uu"]) / 100.0
    L = np.diag([sx, sy, sz]) @ R3
    T = (Matrix.Translation((0.0, 0.0, top_m)) @ Matrix.Diagonal((sx, sy, sz, 1.0))
         @ Matrix.Translation((-cx, -cy, -z_cut)) @ Matrix(R3.tolist()).to_4x4())
    # corner normals: inverse transpose of the linear part, kept in a corner attribute through bmesh edits
    cn = corner_normals(me) @ np.linalg.inv(L)  # (L^-T n) for row vectors = n @ L^-1
    cn /= np.maximum(np.linalg.norm(cn, axis=1, keepdims=True), 1e-12)
    attr = me.attributes.new("um_orig_normal", "FLOAT_VECTOR", "CORNER")
    attr.data.foreach_set("vector", cn.astype(np.float32).ravel())
    me.transform(T)
    me.update()
    co = vertex_array(me)
    above = co[:, 2] > top_m + 1e-9
    disp_uu = (co[above, 2] - top_m) * 100.0
    co[above, 2] = top_m
    me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    nv, nf = len(bm.verts), len(bm.faces)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-7, edges=bm.edges[:])
    collapsed = {"vertices": nv - len(bm.verts), "faces": nf - len(bm.faces)}
    bm.to_mesh(me)
    bm.free()
    me.update()
    # normals back; faces lying in the top plane face straight up
    vec = np.empty(len(me.loops) * 3, dtype=np.float32)
    me.attributes["um_orig_normal"].data.foreach_get("vector", vec)
    vec = vec.reshape(-1, 3)
    vec /= np.maximum(np.linalg.norm(vec, axis=1, keepdims=True), 1e-12)
    co = vertex_array(me)
    on_plane_up = folded = 0
    for p in me.polygons:
        if all(abs(co[i, 2] - top_m) < 1e-7 for i in p.vertices):
            if p.normal.z > 0.99:
                on_plane_up += 1
                vec[p.loop_start:p.loop_start + p.loop_total] = (0.0, 0.0, 1.0)
            elif p.normal.z < -0.99:
                folded += 1
    me.normals_split_custom_set([tuple(v) for v in vec])
    me.attributes.remove(me.attributes["um_orig_normal"])
    me.update()
    return {
        "source_dimensions_m": [r(v) for v in d0],
        "turned_90deg_about_z": turn,
        "turn_reason": "source long axis was X; long side must be .blend Y (= UE X)" if turn else "source long axis already Y",
        "top_band_frac": P["top_band_frac"], "footprint_band_frac": P["footprint_band_frac"],
        "cut_z_prescale_m": r(z_cut), "source_top_z_prescale_m": r(hi[2]),
        "footprint_prescale_m": [r(fhi[0] - flo[0]), r(fhi[1] - flo[1])],
        "footprint_aspect_y_over_x_source": r((fhi[1] - flo[1]) / (fhi[0] - flo[0]), 4),
        "footprint_aspect_y_over_x_target": r(ty / tx, 4),
        "scale_xyz": [r(sx), r(sy), r(sz)],
        "xy_nonuniformity_pct": r(abs(sx / sy - 1.0) * 100.0, 3),
        "z_scale_rule": ("depth_uu %s" % P["depth_uu"]) if P.get("depth_uu") else "source proportions: sqrt(sx*sy)",
        "source_depth_below_cut_m": r(depth_src),
        "flatten": {"vertices_moved": int(above.sum()),
                    "displacement_uu_max": r(disp_uu.max() if disp_uu.size else 0.0, 3),
                    "displacement_uu_p50": r(np.percentile(disp_uu, 50) if disp_uu.size else 0.0, 3),
                    "collapsed_by_dissolve_degenerate": collapsed,
                    "faces_in_top_plane_facing_up": on_plane_up,
                    "faces_in_top_plane_facing_down_folded": folded},
    }


def bvh_of(obj):
    me = obj.data
    return BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [tuple(p.vertices) for p in me.polygons])


def rim_widths(bvh, top_m, half, n=25, step_uu=0.5, max_uu=150.0):
    """Flat-top rim: from sample points on the board outline, walk outward until a downward ray no longer
    lands on the top plane. Width in uu per sample (0 = the top plane does not reach the board edge)."""
    out, allw = {}, []
    down = Vector((0.0, 0.0, -1.0))
    for side, axis, sign in (("+X", 0, 1), ("-X", 0, -1), ("+Y", 1, 1), ("-Y", 1, -1)):
        other = half[1 - axis]
        widths = []
        for i in range(n):
            s = -other + 2 * other * (i + 0.5) / n
            base = [0.0, 0.0]
            base[axis] = sign * half[axis]
            base[1 - axis] = s
            t, last = 0.0, None
            while t <= max_uu:
                p = [base[0], base[1]]
                p[axis] += sign * t / 100.0
                hit = bvh.ray_cast(Vector((p[0], p[1], top_m + 0.01)), down, 0.02)
                if hit[0] is None or abs(hit[0].z - top_m) > 1e-4 or hit[1].z < 0.99:
                    break
                last = t
                t += step_uu
            widths.append(0.0 if last is None else last)
        allw += widths
        a = np.array(widths)
        out[side] = {"min": r(a.min(), 2), "p50": r(np.percentile(a, 50), 2), "max": r(a.max(), 2)}
    a = np.array(allw)
    return {"per_side_uu": out, "samples": len(allw), "min_uu": r(a.min(), 2), "p05_uu": r(np.percentile(a, 5), 2),
            "p50_uu": r(np.percentile(a, 50), 2), "max_uu": r(a.max(), 2),
            "samples_top_missing_at_board_edge": int((a == 0).sum()), "step_uu": step_uu}


def enclosed(bvh, lo_uu, hi_uu, n=12):
    """Board undertray perimeter points inside the tray: a horizontal ray outward must exit the tray first."""
    lo, hi = [v / 100.0 for v in lo_uu], [v / 100.0 for v in hi_uu]
    zs = [lo[2] + 0.005, (lo[2] + hi[2]) / 2, hi[2] - 0.005]
    inside = total = 0
    outside_pts = []
    for z in zs:
        for axis, sign in ((0, 1), (0, -1), (1, 1), (1, -1)):
            for i in range(n):
                s = lo[1 - axis] + (hi[1 - axis] - lo[1 - axis]) * (i + 0.5) / n
                p = [0.0, 0.0, z]
                p[axis] = hi[axis] if sign > 0 else lo[axis]
                p[1 - axis] = s
                d = Vector((sign if axis == 0 else 0.0, sign if axis == 1 else 0.0, 0.0))
                hit = bvh.ray_cast(Vector(p), d, 50.0)
                total += 1
                if hit[0] is not None and hit[1].dot(d) > 0:
                    inside += 1
                elif len(outside_pts) < 10:
                    outside_pts.append([r(c * 100.0, 1) for c in p])
    return {"samples": total, "inside": inside, "fraction_inside": r(inside / total, 4),
            "outside_points_uu_blend_first10": outside_pts, "heights_uu": [r(z * 100.0, 2) for z in zs]}


def top_outline(obj, top_m):
    co = vertex_array(obj.data)
    top = co[np.abs(co[:, 2] - top_m) < 1e-7]
    lo, hi = top.min(0), top.max(0)
    return lo, hi, int(len(top))


# ----------------------------------------------------------------------------- textures (as static_prop_candidate)
def build_textures(obj, glb, P, out):
    names = S.gltf_images(glb)
    size = int(P["texture_size"])
    bc_img, mr_img, n_img = (S.find_image(names[k]) for k in ("basecolor", "metallic_roughness", "normal"))
    src_size = bc_img.size[0]
    factor = src_size // size
    if src_size % size or any(i.size[0] != src_size for i in (mr_img, n_img)):
        raise RuntimeError("texture sizes not an integer multiple of target: %s" % src_size)
    bc = S.image_array(bc_img)[..., :3]
    bc_lin = S.srgb_to_lin(bc) if bc_img.colorspace_settings.name == "sRGB" else bc
    bc_out = S.lin_to_srgb(S.box_down(bc_lin, factor))
    n_raw = S.image_array(n_img)[..., :3]
    n_len = np.linalg.norm(n_raw * 2 - 1, axis=2)
    n_bg = (n_raw[..., 2] < 0.5) | (n_len < 0.7) | (n_len > 1.3)
    pad_px = int(P["normal_padding_px_source"])
    nrm, filled = S.dilate_into(n_raw * 2 - 1, n_bg, pad_px)
    nrm[~filled] = (0.0, 0.0, 1.0)
    nrm = S.box_down(nrm, factor)
    nrm /= np.maximum(np.linalg.norm(nrm, axis=2, keepdims=True), 1e-6)
    n_dx = nrm.copy()
    n_dx[..., 1] *= -1  # OpenGL (glTF) -> DirectX (UE)
    n_out = n_dx * 0.5 + 0.5
    mr = S.box_down(S.image_array(mr_img)[..., :3], factor)
    pre = P["texture_prefix"]
    bc_path, n_path, orm_path = (out / "export" / ("%s_%s.png" % (pre, s)) for s in ("BC", "N", "ORM"))
    t_bc = S.save_png(bc_out, size, bc_path, "sRGB")
    t_n = S.save_png(n_out, size, n_path, "Non-Color")
    orm = np.ones((size, size, 3), dtype=np.float32)
    orm[..., 1] = mr[..., 1]
    orm[..., 2] = mr[..., 2]
    t_orm = S.save_png(orm, size, orm_path, "Non-Color")
    obj.data.materials.clear()
    obj.data.materials.append(S.build_material(P["material_name"], t_bc, t_n, t_orm))
    ao_stats = None
    if P.get("bake_ao"):
        ao = S.bake_ao(obj, size, int(P["ao_samples"]), float(P["ao_distance_m"]))
        me = obj.data
        me.calc_loop_triangles()
        uvl = me.uv_layers[0].data
        cover = S.raster_triangles(np.array([[uvl[i].uv[:] for i in t.loops] for t in me.loop_triangles]), size) > 0
        orm[..., 0] = np.where(cover | (ao > 0), ao, 1.0)
        t_orm = S.save_png(orm, size, orm_path, "Non-Color")
        a = ao[cover]
        ao_stats = {"measured_on": "texels covered by UV islands", "min": r(a.min(), 3),
                    "p05": r(np.percentile(a, 5), 3), "p50": r(np.percentile(a, 50), 3), "mean": r(a.mean(), 3),
                    "texels_lt_0.2": int((a < 0.2).sum()), "samples": int(P["ao_samples"]),
                    "distance_m": float(P["ao_distance_m"])}
    for img in (t_bc, t_n, t_orm):
        img.reload()

    def tags(path):
        return sorted(t.decode() for t, _s, _e in S.png_chunks(path)[1] if t in S.PNG_COLOR_CHUNKS)

    note = "Linear is an import setting (UE: sRGB off); no sRGB/gAMA/cHRM/iCCP chunk in the file"
    rec = {
        "source_images": names, "source_size_px": src_size, "target_size_px": size,
        "downscale": "box %dx%d (BC in linear light)" % (factor, factor),
        "outputs": {
            "BC": {"path": bc_path.name, "colorspace": "sRGB", "png_color_chunks": tags(bc_path),
                   "sha256": S.sha256(bc_path)},
            "N": {"path": n_path.name, "colorspace": "Linear (Non-Color)",
                  "convention": "DirectX (G flipped from glTF OpenGL)", "png_color_chunks": tags(n_path),
                  "note": note, "sha256": S.sha256(n_path)},
            "ORM": {"path": orm_path.name, "colorspace": "Linear (Non-Color)",
                    "channels": {"R": "AO baked in Blender Cycles" if ao_stats else "1.0 (no AO)",
                                 "G": "roughness from glTF metallicRoughness.G",
                                 "B": "metallic from glTF metallicRoughness.B"},
                    "png_color_chunks": tags(orm_path), "note": note, "sha256": S.sha256(orm_path)},
        },
        "ao_bake": ao_stats,
        "normal_padding": {"background_fraction_source": r(n_bg.mean(), 4), "dilated_px_at_source": pad_px,
                           "flat_filled_fraction_source": r((~filled).mean(), 4)},
        "channel_stats": {"roughness_mean": r(orm[..., 1].mean(), 3), "metallic_mean": r(orm[..., 2].mean(), 3),
                          "metallic_fraction_gt_0.5": r((orm[..., 2] > 0.5).mean(), 4),
                          "normal_mean_rgb_dx": [r(v, 3) for v in n_out.reshape(-1, 3).mean(0)]},
        "teamcolor": "not applicable: the diorama base is not team-owned; M_DioramaMaster TeamColor stays neutral",
    }
    return rec, bc_out


def save_jpg(src_png, dst_jpg, px):
    img = bpy.data.images.load(str(src_png))
    img.scale(px, px)
    scene = bpy.context.scene
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 90
    scene.view_settings.view_transform = "Standard"
    img.save_render(str(dst_jpg), scene=scene)
    bpy.data.images.remove(img)


# ----------------------------------------------------------------------------- main
def json_default(o):
    if isinstance(o, np.generic):
        return o.item()
    raise TypeError("not JSON serializable: %r" % type(o))


def main():
    P = load_params()
    out = P["out_dir"]
    for sub in ("work", "export", "reports", "preview"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    preset = json.loads(P["fbx_preset"].read_text(encoding="utf-8"))
    src_sha = S.sha256(P["source_glb"])
    glb = S.glb_json(P["source_glb"])
    board = board_reference(P)
    top_m = float(P["top_z_uu"]) / 100.0
    report = {
        "schema": SCHEMA, "status": "measured", "asset": "ASSET-TABLE-BASE-001",
        "claims": {"art_accepted": False, "game_ready": False, "budgets_declared": False},
        "blender_version": bpy.app.version_string,
        "script_sha256_lf": S.text_sha256_lf(HERE),
        "helpers": {"path": S.rel(SPC, P), "sha256_lf": S.text_sha256_lf(SPC)},
        "params": {k: (S.rel(v, P) if isinstance(v, Path) else v) for k, v in P.items() if k != "repo_root"},
        "source": {"path": S.rel(P["source_glb"], P), "sha256": src_sha, "bytes": P["source_glb"].stat().st_size,
                   "gltf_generator": glb[0].get("asset", {}).get("generator")},
        "board_reference": board,
    }

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(P["source_glb"]))
    meshes = S.mesh_objects()
    lo, hi = S.world_bounds(meshes)
    report["import"] = {
        "mesh_objects": len(meshes), "triangles": sum(S.triangles(o) for o in meshes),
        "materials": sorted({m.name for o in meshes for m in o.data.materials if m}),
        "images": [{"name": i.name, "size": list(i.size), "colorspace": i.colorspace_settings.name}
                   for i in bpy.data.images if i.size[0]],
        "bounds_min_m": [r(v) for v in lo], "bounds_max_m": [r(v) for v in hi],
        "dimensions_m": [r(v) for v in (hi - lo)],
    }
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH":
            bpy.data.objects.remove(o)
    obj = meshes[0]
    if len(meshes) > 1:
        with bpy.context.temp_override(active_object=obj, selected_editable_objects=meshes):
            bpy.ops.object.join()
    obj.parent = None
    obj.data.transform(obj.matrix_world)
    obj.matrix_world = Matrix.Identity(4)
    obj.name = obj.data.name = P["asset_name"]

    geo_before, flipped = S.geometry_stats(obj)
    normals_before = S.corner_normal_stats(obj)
    removed = S.clean_mesh(obj)
    geo_mid, flipped = S.geometry_stats(obj)
    fixed, winding_note = 0, "no inconsistent faces"
    if flipped:
        backup = obj.data.copy()
        fixed = S.fix_winding(obj, flipped)
        geo_try, _ = S.geometry_stats(obj)
        if geo_try["faces_with_inconsistent_winding"] >= geo_mid["faces_with_inconsistent_winding"]:
            old = obj.data
            obj.data = backup
            bpy.data.meshes.remove(old)
            obj.data.name = P["asset_name"]
            winding_note = "%d face(s) flagged; reversing did not reduce the count, kept as delivered" % len(flipped)
            fixed = 0
        else:
            bpy.data.meshes.remove(backup)
            winding_note = "reversed %d face(s)" % fixed
    geo_clean, _ = S.geometry_stats(obj)

    fit = fit_and_flatten(obj, P)
    geo_after, flipped_after = S.geometry_stats(obj)
    closed = (geo_after["welded_boundary_edges"] == 0 and geo_after["welded_non_manifold_edges"] == 0
              and geo_after["faces_with_inconsistent_winding"] == 0)
    report["geometry"] = {"before_cleanup": geo_before, "removed": removed, "winding_faces_reversed": fixed,
                          "winding_note": winding_note, "after_cleanup": geo_clean, "after_fit_flatten": geo_after,
                          "flagged_face_centres_uu": [[r(c * 100.0, 2) for c in obj.data.polygons[i].center]
                                                      for i in flipped_after[:10]],
                          "corner_normals_before": normals_before, "corner_normals_after": S.corner_normal_stats(obj),
                          "closed_manifold_consistent_after": closed}
    report["fit"] = fit

    lo, hi = S.world_bounds([obj])
    tlo, thi, n_top = top_outline(obj, top_m)
    target = [float(v) for v in P["footprint_uu_blend_xy"]]
    report["scale_pivot"] = {
        "dimensions_m": [r(v) for v in (hi - lo)],
        "bounds_min_m": [r(v) for v in lo], "bounds_max_m": [r(v) for v in hi],
        "top_plane_z_uu": r(top_m * 100.0, 4), "top_plane_vertices": n_top,
        "top_outline_uu_blend": {"min": [r(tlo[0] * 100, 3), r(tlo[1] * 100, 3)],
                                 "max": [r(thi[0] * 100, 3), r(thi[1] * 100, 3)],
                                 "size": [r((thi[0] - tlo[0]) * 100, 3), r((thi[1] - tlo[1]) * 100, 3)]},
        "footprint_target_uu_blend_xy": target,
        "depth_below_top_uu": r((top_m - lo.z) * 100.0, 3),
        "overhang_beyond_top_outline_uu": [r((tlo[0] - lo.x) * 100, 3), r((hi.x - thi[0]) * 100, 3),
                                           r((tlo[1] - lo.y) * 100, 3), r((hi.y - thi[1]) * 100, 3)],
        "pivot": "object origin = board centre (0,0); Z=0 = play plane; tray top at top_z_uu, whole tray below",
        "collision": "none (04 3.6: not interactive; the board keeps its own UBX selection collision)",
    }

    # board relation (measured; z-fighting is a check, rim/undertray are measurements)
    bvh = bvh_of(obj)
    if board:
        bmin, bmax = board["whole_uu_blend"]["min"], board["whole_uu_blend"]["max"]
        half = [max(abs(bmin[0]), abs(bmax[0])) / 100.0, max(abs(bmin[1]), abs(bmax[1])) / 100.0]
        half_src = "board FBX bounds (whole mesh, .blend axes)"
    else:
        rim_mid = sum(P["rim_proposed_uu"]) / 2
        half = [(target[0] / 2 - rim_mid) / 100.0, (target[1] / 2 - rim_mid) / 100.0]
        half_src = "footprint minus mid of rim_proposed_uu (no board bounds json)"
    rim = rim_widths(bvh, top_m, half)
    rim["board_half_extent_uu_blend"] = [r(half[0] * 100, 3), r(half[1] * 100, 3)]
    rim["board_outline_source"] = half_src
    rim["proposed_uu"] = P["rim_proposed_uu"]
    rim["min_within_proposed"] = P["rim_proposed_uu"][0] <= rim["min_uu"] <= P["rim_proposed_uu"][1]
    rim["p50_within_proposed"] = P["rim_proposed_uu"][0] <= rim["p50_uu"] <= P["rim_proposed_uu"][1]
    relation = {"rim_flat_top": rim}
    coplanar_ok = True
    if board:
        levels = board["horizontal_face_levels_uu"]
        gaps = sorted(({"z_uu": h["z_uu"], "facing": h["facing"], "parts": h["parts"],
                        "gap_to_top_plane_uu": r(abs(h["z_uu"] - top_m * 100.0), 3)} for h in levels),
                      key=lambda g: g["gap_to_top_plane_uu"])
        coplanar_ok = gaps[0]["gap_to_top_plane_uu"] >= float(P["coplanar_min_uu"]) if gaps else True
        relation["board_horizontal_faces_nearest_top_plane"] = gaps[:4]
        relation["board_top_above_tray_top_uu"] = r(bmax[2] - top_m * 100.0, 3)
        relation["board_bottom_below_tray_top_uu"] = r(top_m * 100.0 - bmin[2], 3)
        relation["tray_depth_below_board_bottom_uu"] = r(bmin[2] - lo.z * 100.0, 3)
        if board.get("undertray_uu_blend"):
            u = board["undertray_uu_blend"]
            relation["board_undertray_enclosed"] = enclosed(bvh, u["min"], u["max"])
    report["board_relation"] = relation

    # textures, material, AO
    report["textures"], bc_out = build_textures(obj, glb, P, out)
    size = int(P["texture_size"])
    uv, tuv = S.uv_analysis(obj, size)
    report["uv0"] = uv
    uv_png = out / "work" / ("%s_uv0_layout.png" % P["asset_name"])
    S.uv_layout_png(tuv, bc_out, size, uv_png)
    save_jpg(uv_png, out / "preview" / ("%s_uv0_layout.jpg" % P["asset_name"]), 1024)
    report["material_slots"] = len(obj.data.materials)
    report["material_names"] = [m.name for m in obj.data.materials]

    blend = out / "work" / ("%s.blend" % P["asset_name"])
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=False, copy=True)

    fbx = out / "export" / ("%s.fbx" % P["asset_name"])
    kwargs = S.fbx_kwargs(preset)
    conformance = [c for c in S.um_fbx_v1_conformance(preset, kwargs, obj, bpy.context.scene)
                   if not c["setting"].startswith("Pivot:")]
    centre_uu = [r((tlo[0] + thi[0]) * 50.0, 4), r((tlo[1] + thi[1]) * 50.0, 4)]
    conformance.append({"setting": "Pivot: board centre (0,0) = centre of the top outline; top plane at top_z_uu "
                                   "and nothing above it (04 3.6)",
                        "standard": [0.0, 0.0, float(P["top_z_uu"])],
                        "used": centre_uu + [r(hi.z * 100.0, 4)],
                        "conforms": abs(centre_uu[0]) < 0.01 and abs(centre_uu[1]) < 0.01
                        and abs(hi.z - top_m) < 1e-6})
    S.export_fbx(obj, fbx, preset)
    report["export"] = {
        "fbx": fbx.name, "sha256": S.sha256(fbx), "bytes": fbx.stat().st_size, "preset": P["fbx_preset"].name,
        "settings": {k: preset[k] for k in ("axis_forward", "axis_up", "export_space_rotation_z_degrees",
                                            "temporary_data_scale", "patch_fbx_unit_scale_to", "apply_scale_options",
                                            "use_triangles", "mesh_smooth_type", "path_mode")},
        "exporter_kwargs": {k: (sorted(v) if isinstance(v, set) else v) for k, v in sorted(kwargs.items())},
        "textures_embedded": False,
        "texture_paths": "relative to the FBX (absolute checkout path is never written)",
        "um_fbx_v1_conformance": conformance,
        "um_fbx_v1_conforms": all(c["conforms"] for c in conformance),
    }

    # round trip in an empty scene (export frame: .blend (x, y) -> (-y, x); metres = uu / 100)
    expected_tris = S.triangles(obj)
    exp_top = [thi[1] - tlo[1], thi[0] - tlo[0]]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx))
    rt = S.mesh_objects()
    arm = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    rt_obj = rt[0] if rt else None
    lo2, hi2 = S.world_bounds(rt)
    pts = np.array([list(rt_obj.matrix_world @ v.co) for v in rt_obj.data.vertices]) if rt_obj else np.zeros((1, 3))
    rt_top = pts[np.abs(pts[:, 2] - hi2.z) < 1e-6]
    rt_top_size = rt_top.max(0) - rt_top.min(0)
    rt_top_centre = (rt_top.max(0) + rt_top.min(0)) / 2
    dims = report["scale_pivot"]["dimensions_m"]
    report["roundtrip"] = {
        "mesh_objects": len(rt), "object_names": [o.name for o in rt],
        "triangles": sum(S.triangles(o) for o in rt), "expected_triangles": expected_tris,
        "material_slots": len(rt_obj.data.materials) if rt_obj else None,
        "uv_layers": len(rt_obj.data.uv_layers) if rt_obj else None,
        "armatures": len(arm),
        "dimensions_uu": [r(v * 100, 3) for v in (hi2 - lo2)],
        "bounds_min_uu": [r(v * 100, 3) for v in lo2], "bounds_max_uu": [r(v * 100, 3) for v in hi2],
        "top_outline_size_uu": [r(rt_top_size[0] * 100, 3), r(rt_top_size[1] * 100, 3)],
        "top_outline_centre_uu": [r(rt_top_centre[0] * 100, 3), r(rt_top_centre[1] * 100, 3)],
        "expected_ue_dimensions_uu_at_import_scale_1": [r(dims[1] * 100, 3), r(dims[0] * 100, 3),
                                                        r(dims[2] * 100, 3)],
        "object_scale": [r(v) for v in rt_obj.scale] if rt_obj else None,
        "note": "FBX read back in Blender = UM_FBX_v1 export frame (UE shows it as x, -y, z); metres x100 = uu",
    }
    checks = {
        "single_mesh": len(rt) == 1,
        "triangles_preserved": report["roundtrip"]["triangles"] == expected_tris,
        "one_material_slot": report["roundtrip"]["material_slots"] == 1,
        "uv0_present": (report["roundtrip"]["uv_layers"] or 0) >= 1,
        "no_armature": not arm,
        "top_at_top_z": abs(hi2.z * 100 - float(P["top_z_uu"])) < 0.01,
        "top_outline_matches_footprint_1uu": (abs(rt_top_size[0] - exp_top[0]) * 100 < 1.0
                                              and abs(rt_top_size[1] - exp_top[1]) * 100 < 1.0
                                              and abs(rt_top_size[0] * 100 - target[1]) < 1.0
                                              and abs(rt_top_size[1] * 100 - target[0]) < 1.0),
        "top_outline_centred": abs(rt_top_centre[0]) * 100 < 0.01 and abs(rt_top_centre[1]) * 100 < 0.01,
        "no_folded_faces_in_top_plane": fit["flatten"]["faces_in_top_plane_facing_down_folded"] == 0,
        "no_board_horizontal_face_near_top_plane": coplanar_ok,
        "source_unchanged": S.sha256(P["source_glb"]) == src_sha,
        "um_fbx_v1_conforms": report["export"]["um_fbx_v1_conforms"],
    }
    if P.get("require_closed_manifold", True):
        checks["closed_manifold_consistent_winding"] = closed
    checks = {k: bool(v) for k, v in checks.items()}
    report["checks"] = checks
    report["checks_passed"] = all(checks.values())
    text = json.dumps(report, indent=2, ensure_ascii=False, default=json_default) + "\n"
    (out / "reports" / "candidate-report.json").write_text(text, encoding="utf-8")
    print("CANDIDATE_REPORT", json.dumps(checks))
    if not report["checks_passed"]:
        raise SystemExit(1)


main()
