"""ART-004 A1 follow-up: headless re-checks requested by the verifier (vc, 2026-09-28).

Blender 5.2, from the repository root (never saves a .blend or FBX):

  blender --background --factory-startup --python tools/art/art004_head_tilt_v3_followup.py -- [OUT_DIR]

OUT_DIR defaults to C:/tmp/a1v3/followup (scratch). Writes followup-measurements.json
and hitreact-*-{v2,v3}.png there; build_json.py / composites.py in
art004_head_tilt_v3_mcp_review pick them up.

1. Head socket vs the rotated head. The live-Blender step b9_socket.py was fixed
   after the run (the executed copy used +15 deg) and its numbers were typed into
   build_json.py by hand; this recomputes them from the source + tilt and checks
   the tilt direction against the saved v3 FBX.
2. Per-frame intersection counts of the draft clips (the measure script stores
   only max/mean). Diagnostic only: the clips are not accepted animations.
3. The HitReact worst frame rendered for v2 and v3 with one identical camera,
   only body and bow visible (replaces the live viewport shot with two cameras).
"""

import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import art004_head_tilt_v3_measure as m  # noqa: E402  (guarded main)

ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = Path(ARGS[0]) if ARGS else Path("C:/tmp/a1v3/followup")
# Head socket = bone `head` + (0,0,4) -> UE component (0, 4, 38.5) cm. FBX/source
# data use the mirrored Y (front of the figure is -Y), so the same point is (0,-4,38.5).
SOCKET_UU = np.array([0.0, -4.0, 38.5])
PIVOT_UU = np.array(m.PIVOT_M) * m.UU


def r(value, digits=3):
    return round(float(value), digits)


def socket_check(fbx_body, co_m, moved_v, labels, polys):
    co = {"v2": co_m * m.UU, "v3": m.tilt(co_m, moved_v) * m.UU}
    face = [i for i, lab in enumerate(labels) if lab == "tripo_part_10"]
    feat = [i for i in face if co["v2"][polys[i]].mean(axis=0)[2] >= 42.0]
    fv = sorted({v for i in feat for v in polys[i]})
    out = {"method": "source medusa.blend + tilt(-15 deg about X, pivot z=38.5 uu), equal to the saved "
                     "FBX within 1e-5 uu (blender-measurements.json reproduction_check); facial features = "
                     "face part polygons with v2 centre z >= 42 uu",
           "face_polys": len(face), "feature_polys": len(feat)}
    sock = Vector(SOCKET_UU)
    for tag, c in co.items():
        cen = c[fv].mean(axis=0)
        bvh = BVHTree.FromPolygons(c.tolist(), polys)
        _loc, _nrm, _idx, dist = bvh.find_nearest(sock)
        hits, origin = 0, sock.copy()
        while True:  # ray to the front (-Y): 0 hits = socket is outside, in front of the throat
            hit = bvh.ray_cast(origin, Vector((0, -1, 0)))
            if hit[0] is None:
                break
            hits += 1
            origin = hit[0] + Vector((0, -1e-3, 0))
        out[tag] = {"feature_centroid_fbx_uu": [r(x) for x in cen],
                    "socket_to_feature_centroid_uu": r(np.linalg.norm(cen - SOCKET_UU)),
                    "socket_nearest_surface_uu": r(dist), "ray_forward_hits": hits}
    rot = np.array(m.rotation())
    rel = SOCKET_UU - PIVOT_UU
    moved = rot @ rel + PIVOT_UU
    out["v3_socket_if_rotated_with_head_fbx_uu"] = [r(x) for x in moved]
    out["v3_socket_if_rotated_with_head_ue_component_uu"] = [r(moved[0]), r(-moved[1]), r(moved[2])]
    out["v3_socket_offset_vs_rotated_uu"] = r(np.linalg.norm(moved - SOCKET_UU))
    # Direction check on the saved FBX: v3 face == v2 face rotated by -15 deg (not +15).
    face_v = sorted({v for i in face for v in polys[i]})
    v2f, v3f = fbx_body["v2"][face_v], fbx_body["v3"][face_v]
    for sign in (-1, 1):
        rs = np.array(m.Matrix.Rotation(math.radians(sign * abs(m.TILT_DEG)), 3, "X"))
        pred = (v2f - PIVOT_UU) @ rs.T + PIVOT_UU
        out[f"saved_v3_face_vs_v2_rotated_{'minus' if sign < 0 else 'plus'}15_max_uu"] = r(np.abs(v3f - pred).max(), 5)
    return out


def clip_frames(co_m, moved_v, labels, polys, moved_polys, seam_moved, seam_static):
    """Same counting as measure.posed_analysis, but every frame is kept."""
    body = bpy.data.objects["SK_Medusa_Body"]
    arm = bpy.data.objects["SKEL_Medusa"]
    arm.data.pose_position = "POSE"
    head_parts = set(m.MOVED_PARTS) | {"tripo_part_3"}
    other = [i for i, lab in enumerate(labels) if lab not in head_parts]
    scene = bpy.context.scene
    original = co_m.reshape(-1).copy()
    variants = {"v2": original, "v3": m.tilt(co_m, moved_v).reshape(-1)}
    result = {}
    for action in sorted(bpy.data.actions, key=lambda a: a.name):
        start, end = (int(x) for x in action.frame_range)
        arm.animation_data.action = action
        per = {"frame_range": [start, end]}
        for tag, flat in variants.items():
            body.data.vertices.foreach_set("co", flat)
            body.data.update()
            counts, crown_quiver = [], []
            for frame in range(start, end + 1):
                scene.frame_set(frame)
                graph = bpy.context.evaluated_depsgraph_get()
                ev = body.evaluated_get(graph)
                em = ev.to_mesh()
                co = np.empty(len(em.vertices) * 3)
                em.vertices.foreach_get("co", co)
                ev.to_mesh_clear()
                count, pairs = m.overlaps(co.reshape(-1, 3) * m.UU, polys, moved_polys, other, labels,
                                          seam_moved, seam_static)
                counts.append(int(count))
                crown_quiver.append(int(pairs.get("crown|quiver", 0)))
            per[tag] = {"per_frame": counts, "crown_quiver_per_frame": crown_quiver,
                        "max": max(counts), "mean": r(sum(counts) / len(counts), 1),
                        "worst_frame": start + int(np.argmax(counts))}
        result[action.name] = per
    body.data.vertices.foreach_set("co", original)
    body.data.update()
    return result, variants


def render_worst(variants, labels, action_name, frame):
    body = bpy.data.objects["SK_Medusa_Body"]
    bow = bpy.data.objects["SK_Medusa_Bow"]
    arm = bpy.data.objects["SKEL_Medusa"]
    arm.data.pose_position = "POSE"
    arm.animation_data.action = bpy.data.actions[action_name]
    scene = bpy.context.scene
    scene.frame_set(frame)
    for obj in bpy.data.objects:
        if obj.type in {"MESH", "LIGHT", "CAMERA", "CURVE", "EMPTY"}:
            obj.hide_render = obj not in (body, bow)
    # Aim at the v3 crown x quiver contact: centroid of crown polygons that intersect
    # the quiver at this frame (world metres). The same camera is used for v2.
    body.data.vertices.foreach_set("co", variants["v3"])
    body.data.update()
    scene.frame_set(frame)
    graph = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(graph)
    em = ev.to_mesh()
    co = np.empty(len(em.vertices) * 3)
    em.vertices.foreach_get("co", co)
    ev.to_mesh_clear()
    co = co.reshape(-1, 3)
    polys = [list(p.vertices) for p in body.data.polygons]
    crown = [i for i, lab in enumerate(labels) if lab == "tripo_part_1"]
    quiver = [i for i, lab in enumerate(labels) if lab == "tripo_part_7"]
    ta = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in crown])
    tb = BVHTree.FromPolygons(co.tolist(), [polys[i] for i in quiver])
    hit_v = sorted({v for a, _b in ta.overlap(tb) for v in polys[crown[a]]})
    target = body.matrix_world @ Vector(co[hit_v].mean(axis=0))
    # Rear 3/4 from the +X side, above (chosen from a sweep of six directions): the
    # quiver tips stand clear of the crown in v2 and disappear into the snakes in v3.
    direction = Vector((.75, .55, .35)).normalized()
    eye = target + direction * .36
    cam = bpy.data.objects.new("A1F_Camera", bpy.data.cameras.new("A1F_Camera"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "PERSP"
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(35)
    m.look_at(cam, eye, target)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.resolution_x = scene.render.resolution_y = 1024
    scene.render.dither_intensity = 0
    sh = scene.display.shading
    for flag in ("show_cavity", "show_object_outline", "show_shadows", "show_specular_highlight", "show_xray"):
        if hasattr(sh, flag):
            setattr(sh, flag, False)
    sh.show_backface_culling = True
    OUT.mkdir(parents=True, exist_ok=True)
    files = {}
    # textured pass
    sh.light, sh.color_type = "STUDIO", "TEXTURE"
    scene.display.render_aa = "8"
    mat = body.data.materials[0]
    mat.node_tree.nodes.active = mat.node_tree.nodes["Image Texture"]
    for tag, flat in variants.items():
        body.data.vertices.foreach_set("co", flat)
        body.data.update()
        scene.frame_set(frame)
        path = OUT / f"hitreact-f{frame}-rear34-tex-{tag}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files[f"tex-{tag}"] = path.name
    # flat part-ID pass (same palette as the measure script)
    names = {"tripo_part_1": "crown", "tripo_part_10": "face", "tripo_part_14": "neck_back",
             "tripo_part_3": "shoulder_collar", "tripo_part_7": "quiver"}
    m.paint(body, lambda i: m.PALETTE[names.get(labels[i], "body")])
    m.paint(bow, lambda i: m.PALETTE["bow"])
    sh.light, sh.color_type = "FLAT", "VERTEX"
    scene.display.render_aa = "OFF"
    for tag, flat in variants.items():
        body.data.vertices.foreach_set("co", flat)
        body.data.update()
        scene.frame_set(frame)
        path = OUT / f"hitreact-f{frame}-rear34-id-{tag}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        files[f"id-{tag}"] = path.name
    body.data.vertices.foreach_set("co", variants["v2"])
    body.data.update()
    return {"action": action_name, "frame": frame, "camera": {
        "type": "persp", "horizontal_fov_deg": 35, "resolution_px": [1024, 1024],
        "target_m": [r(x, 4) for x in target], "eye_m": [r(x, 4) for x in eye],
        "rule": "same camera for v2 and v3; target = centroid of v3 crown polygons intersecting the quiver "
                "at this frame; only body and bow rendered; backface culling on",
        "v3_crown_vertices_in_contact": len(hit_v)}, "files": files}


def main():
    hashes = {"medusa.blend": m.sha(m.BLEND), "v2": m.sha(m.V2), "v3": m.sha(m.V3)}
    assert hashes == m.EXPECTED_SHA, hashes
    fbx_body = {}
    for tag, path in (("v2", m.V2), ("v3", m.V3)):
        meshes, _bones = m.read_fbx(path)
        fbx_body[tag] = meshes["SK_Medusa_Body"]["co"]
    (_src, co_m, moved_v, labels, polys, _part_polys, moved_polys,
     seam_moved, seam_static) = m.source_analysis()
    socket = socket_check(fbx_body, co_m, moved_v, labels, polys)
    clips, variants = clip_frames(co_m, moved_v, labels, polys, moved_polys, seam_moved, seam_static)
    # Consistency with the stored headless measurements (max/mean per clip).
    stored = json.loads((m.OUT / "blender-measurements.json").read_text(encoding="utf-8"))["draft_clip_interpenetration"]
    consistent = all(stored[a][t]["moved_vs_non_head_intersections_max"] == clips[a][t]["max"] and
                     stored[a][t]["moved_vs_non_head_intersections_mean"] == clips[a][t]["mean"]
                     for a in stored for t in ("v2", "v3"))
    worst = clips["HitReact"]["v3"]["worst_frame"]
    render = render_worst(variants, labels, "HitReact", worst)
    report = {"status": "measured_diagnostic_not_art_acceptance", "date": "2026-09-28",
              "runner": "Blender " + bpy.app.version_string + " --background --factory-startup (no live Blender, no UE)",
              "inputs_sha256": hashes, "head_socket": socket,
              "draft_clip_per_frame": clips,
              "draft_clip_matches_blender_measurements_max_mean": consistent,
              "hitreact_render": render}
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "followup-measurements.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("ART004_HEAD_TILT_V3_FOLLOWUP_OK", path, "sha256",
          hashlib.sha256(path.read_bytes()).hexdigest())


main()
