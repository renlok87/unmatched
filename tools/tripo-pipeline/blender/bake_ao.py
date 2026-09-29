"""Atlas sub-step `ao_bake` (profile atlas.ao_bake): ambient occlusion of every atlas part, baked by Cycles into the
part's own UV at the size of the part's base colour texture, so the atlas stage can write it into ORM.R.

Run only through tripo_pipeline.py, always as a separate headless process (it produces bytes; never in the live GUI):
    blender -b --factory-startup --python-exit-code 1 --python bake_ao.py -- <params.json>
params.json: {"source": abs GLB, "out_dir": abs dir, "report_out": abs path,
              "exclude_parts": [part, ...], "occluders_excluded": [part, ...], "flip_parts": [part, ...],
              "samples": int, "distance_rel": float, "margin_px": int, "seed": int,
              "lib_dir": abs dir holding candidate_build/ (default: this script's dir),
              "per_face_reference": null | {"parts": [part, ...], "max_reference_distance_m", "smoothing_lambda",
                                            "smoothing_max_sweeps", "reference_glb": abs GLB,
                                            "weld_distance_m", "seat": {"base_part", "top_part", "figure_height_m",
                                                                        "base_height_m"}}}

The whole figure is in the scene while one part is baked, so occlusion between parts (arm over robe, feet on the
base) is part of the result. Baked parts = every mesh node of the GLB minus `exclude_parts` (= atlas.exclude_parts),
each at its base colour image size. Parts named in `occluders_excluded` (dropped by the build) are deleted before the
bake; if such a part still has an atlas cell it gets a constant unoccluded image (reported, the build does not use it).

Orientation = the build's, in the build's order (an inward face bakes as occluded: its AO rays start inside the
figure): (1) `per_face_reference` (the profile's orientation.per_face_reference, a part with MIXED winding such as
Harpy's head tripo_part_2): every face votes against the nearest triangle of the registered high-poly GLB, the votes
are smoothed (ICM) on a welded copy of the part in the build's seat frame (weld distance and figure scale as
flow_seated: the same candidate_build.orientation / mesh_ops.weld_part / core.flip_polygons code), and the faces the
build flips are flipped here (mapped back to the unwelded glTF faces through a face-index attribute); (2) parts in
`flip_parts` (the whole-part entries of orientation.expected_inside_out_parts) get their winding flipped and custom
corner normals negated (core.flip_polygons semantics). After the flips the build's ray-escape test
(candidate_build.measure.orientation_scores) runs on the bake scene and the report lists the inward / outward area
fraction of every baked part (`orientation_after_flips`); the atlas gate ao_bake_parts_face_outward fails the stage
when a baked part still has inward area (2026-09-29 review: before (1) existed, 40 % of Harpy's head area faced
inward during the bake and got AO 0.51 instead of 0.7-0.9).

The AO distance is `distance_rel` x the height of the remaining geometry. Cycles on the CPU with a fixed seed and
sample count gives the same bytes for the same inputs (checked by the second-run test of the stage). The source and
reference GLBs are only read. Texels outside the UV islands (beyond margin_px) stay 1.0. Output: <out_dir>/<part>.png
(8-bit grey, linear: 255 = unoccluded) and a JSON report.
"""

import hashlib
import json
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

MARKER = "TRIPO_PIPELINE_STAGE_OK ao_bake"
SRC_FACE_ATTR = "tripo_ao_src_face"
VOTE_ATTR = "tripo_ao_ref_vote"


def build_library(params):
    """candidate_build (the build stage's library) from params.lib_dir or the directory of this script."""
    lib = params.get("lib_dir") or str(Path(__file__).resolve().parent)
    if lib not in sys.path:
        sys.path.insert(0, lib)
    import candidate_build.core as core
    import candidate_build.measure as measure
    import candidate_build.mesh_ops as mesh_ops
    import candidate_build.orientation as orientation
    return core, measure, mesh_ops, orientation


def orientation_after_flips(meshes, measure, zs):
    """Ray-escape score of every part in the bake scene plus a test-only ground plane just under the lowest vertex.

    The build measures on its final figure, which stands on a base; the bake scene can lack one (Harpy: the Tripo base
    tripo_part_4 is dropped and the parametric base does not exist yet) and then a -normal ray of a correct upward face
    of a foot escapes downwards through an open sole (profile open_loop_caps) and the face reads inward (measured
    2026-09-29: Harpy tripo_part_7 / tripo_part_8 4.4 % / 6.6 % without the plane, the +normal ray hitting the leg
    above; with the plane 0.3 % / 0.0 %). The plane only adds occlusion: a face whose -normal ray escaped downwards
    becomes "undecided"; a face of an open single-sided shell whose +normal ray points down onto the plane while its
    -normal ray escapes upwards would read inward (not seen on the four heroes: the largest change is King Arthur's
    maximum 0.0007 -> 0.0012). It is not in the scene during the bake and changes no AO texel."""
    xs = [(o.matrix_world @ v.co).x for o in meshes.values() for v in o.data.vertices]
    ys = [(o.matrix_world @ v.co).y for o in meshes.values() for v in o.data.vertices]
    height = max(zs) - min(zs)
    z = min(zs) - 1e-3 * height
    x0, x1, y0, y1 = min(xs) - height, max(xs) + height, min(ys) - height, max(ys) + height
    mesh = bpy.data.meshes.new("tripo_ao_orientation_ground")
    mesh.from_pydata([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [], [(0, 1, 2, 3)])
    ground = bpy.data.objects.new("tripo_ao_orientation_ground", mesh)
    try:
        labelled = [(o, {n: [p.index for p in o.data.polygons]}) for n, o in sorted(meshes.items())]
        scores = measure.orientation_scores(labelled + [(ground, {})])
    finally:
        bpy.data.objects.remove(ground, do_unlink=True)
        bpy.data.meshes.remove(mesh)
    return scores, z


def world_bounds(obj):
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
    return [min(p[i] for p in pts) for i in range(3)], [max(p[i] for p in pts) for i in range(3)]


def reference_orientation_fix(meshes, cfg, lib):
    """The build's per-face orientation fix (flow_seated: orientation.per_face_reference) on the unwelded glTF parts.

    Votes are computed on a copy of the part in the source frame (as the build, before the seat transform); the copy is
    then moved into the build's seat frame (uniform figure scale about the source base top), welded with the build's
    distance and smoothed with the build's lambda and sweeps; the faces to flip are mapped back to the glTF faces by a
    face-index attribute (a weld can drop degenerate faces, so welded and glTF face indices differ)."""
    core, _measure, mesh_ops, orientation = lib
    seat = cfg["seat"]
    blo, bhi = world_bounds(meshes[seat["base_part"]])
    cx, cy, base_top = (blo[0] + bhi[0]) / 2, (blo[1] + bhi[1]) / 2, bhi[2]
    top_obj = meshes[seat["top_part"]]
    top = max((top_obj.matrix_world @ v.co).z for v in top_obj.data.vertices)
    fz = float(seat["base_height_m"])
    s = (float(seat["figure_height_m"]) - fz) / (top - base_top)
    ref = orientation.read_glb_node_triangles(cfg["reference_glb"], cfg["parts"])
    out = {"reference_glb": {"file": Path(cfg["reference_glb"]).name, "sha256": sha256(cfg["reference_glb"])},
           "figure_scale": round(s, 8), "weld_distance_m": cfg["weld_distance_m"], "parts": {}}
    for name in cfg["parts"]:
        obj = meshes[name]
        tmp = obj.data.copy()
        tmp.transform(obj.matrix_world)
        tobj = bpy.data.objects.new("tripo_ao_ref_" + name, tmp)
        try:
            votes, info = orientation.reference_votes(tobj, ref[name][0], ref[name][1], cfg["max_reference_distance_m"])
            tmp.attributes.new(VOTE_ATTR, "FLOAT", "FACE").data.foreach_set("value", votes)
            tmp.attributes.new(SRC_FACE_ATTR, "INT", "FACE").data.foreach_set("value", list(range(len(tmp.polygons))))
            for v in tmp.vertices:  # flow_seated seat transform of a figure part
                v.co = Vector(((v.co.x - cx) * s, (v.co.y - cy) * s, fz + (v.co.z - base_top) * s))
            tmp.update()
            info["weld"] = mesh_ops.weld_part(tobj, cfg["weld_distance_m"])
            n = len(tmp.polygons)
            vals, src_ix = [0.0] * n, [0] * n
            tmp.attributes[VOTE_ATTR].data.foreach_get("value", vals)
            tmp.attributes[SRC_FACE_ATTR].data.foreach_get("value", src_ix)
            flip, smooth = orientation.smooth_orientation(tmp, vals, cfg["smoothing_lambda"], cfg["smoothing_max_sweeps"])
            selected = {src_ix[i] for i in flip}
        finally:
            bpy.data.objects.remove(tobj, do_unlink=True)
            bpy.data.meshes.remove(tmp)
        core.flip_polygons(obj.data, selected)
        info.update(smoothing=smooth, flipped_faces=len(selected), glb_faces=len(obj.data.polygons))
        out["parts"][name] = info
    ref.clear()
    return out


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def flip_part(mesh):
    """Winding flip of every polygon + negated custom corner normals (same as candidate_build.core.flip_polygons)."""
    normals = [mesh.corner_normals[li].vector.copy() for li in range(len(mesh.loops))]
    by_poly = {p.index: [(mesh.loops[li].vertex_index, normals[li]) for li in p.loop_indices] for p in mesh.polygons}
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for face in bm.faces:
        face.normal_flip()
    bm.to_mesh(mesh)
    bm.free()
    out = [None] * len(mesh.loops)
    for p in mesh.polygons:
        src = {v: n for v, n in by_poly[p.index]}
        for li in p.loop_indices:
            n = src[mesh.loops[li].vertex_index].copy()
            n.negate()
            out[li] = n
    mesh.normals_split_custom_set(out)
    mesh.update()


def base_color_px(obj):
    """Width of the image feeding the Principled BSDF Base Color of the part's material (glTF import graph)."""
    def upstream_image(socket, depth=0):
        # the glTF importer puts a multiply node between the image and Base Color when baseColorFactor != 1
        for link in socket.links:
            node = link.from_node
            if node.type == "TEX_IMAGE" and node.image:
                return node.image
            if depth < 4:
                for inp in node.inputs:
                    found = upstream_image(inp, depth + 1)
                    if found is not None:
                        return found
        return None

    for slot in obj.material_slots:
        mat = slot.material
        if mat is None or mat.node_tree is None:
            continue
        for node in mat.node_tree.nodes:
            if node.type == "BSDF_PRINCIPLED":
                image = upstream_image(node.inputs["Base Color"])
                if image is not None:
                    return int(image.size[0])
    raise RuntimeError("%s: no base colour image" % obj.name)


def main():
    params = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    source = params["source"]
    before = sha256(source)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=source)
    scene = bpy.context.scene
    meshes = {o.name: o for o in scene.objects if o.type == "MESH"}
    exclude = set(params.get("exclude_parts") or [])
    parts = {n: base_color_px(o) for n, o in sorted(meshes.items()) if n not in exclude}
    lib = build_library(params)
    # (1) per-face reference fix first (the build does it before the whole-part ray-escape flips); it needs the
    # base part for the seat frame, so it runs before occluders_excluded are deleted
    ref_fix = reference_orientation_fix(meshes, params["per_face_reference"], lib) \
        if params.get("per_face_reference") else None
    removed = []
    for name in params.get("occluders_excluded") or []:
        if name in meshes:
            bpy.data.objects.remove(meshes.pop(name), do_unlink=True)
            removed.append(name)
    flipped = []
    for name in params.get("flip_parts") or []:
        if name in meshes:
            flip_part(meshes[name].data)
            flipped.append(name)
    # the build's ray-escape test on the bake scene after the flips: an inward face would bake as occluded
    zs = [(o.matrix_world @ v.co).z for o in meshes.values() for v in o.data.vertices]
    orient, ground_z = orientation_after_flips(meshes, lib[1], zs)
    height = max(zs) - min(zs)
    distance = float(params["distance_rel"]) * height
    world = bpy.data.worlds.new("tripo_ao_world")
    scene.world = world
    world.light_settings.distance = distance
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = int(params["samples"])
    scene.cycles.seed = int(params.get("seed", 0))
    scene.cycles.use_denoising = False
    scene.render.bake.margin = int(params["margin_px"])
    scene.render.bake.margin_type = "EXTEND"
    out_dir = Path(params["out_dir"])
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"stage": "ao_bake", "source": {"file": Path(source).name, "sha256": before},
              "blender": bpy.app.version_string, "engine": "CYCLES CPU", "samples": scene.cycles.samples,
              "seed": scene.cycles.seed, "distance_rel": params["distance_rel"],
              "height_m": round(height, 6), "distance_m": round(distance, 6), "margin_px": params["margin_px"],
              "occluders_excluded": removed, "flipped_before_bake": flipped,
              "per_face_reference_fix": ref_fix,
              "orientation_after_flips": {n: orient[n] for n in sorted(parts) if n in orient},
              "orientation_method": "candidate_build.measure.orientation_scores (ray-escape, the build's test) on the "
                                    "bake scene after the per-face and whole-part flips, with a test-only ground "
                                    "plane under the figure (z %.6f)" % ground_z,
              "parts": {}}
    for part, px in sorted(parts.items()):
        if part not in meshes:  # dropped by the build (occluders_excluded) but still an atlas cell
            path = out_dir / ("%s.png" % part)
            img = bpy.data.images.new("AO_" + part, width=int(px), height=int(px), alpha=False, float_buffer=False)
            img.colorspace_settings.name = "Non-Color"
            img.pixels = [1.0] * (int(px) * int(px) * 4)
            img.filepath_raw = str(path)
            img.file_format = "PNG"
            img.save()
            bpy.data.images.remove(img)
            report["parts"][part] = {"file": path.name, "px": int(px), "sha256": sha256(path), "mean": 1.0,
                                     "min": 1.0, "max": 1.0, "note": "not baked: dropped by the build (constant 1)"}
            continue
        obj = meshes[part]
        img = bpy.data.images.new("AO_" + part, width=int(px), height=int(px), alpha=False, float_buffer=False)
        img.colorspace_settings.name = "Non-Color"
        # texels no UV island covers stay unoccluded (1.0) instead of black: black would bleed into the island
        # edges at the lower mips of the atlas (the bake itself writes the islands plus margin_px, use_clear off)
        img.pixels = [1.0] * (int(px) * int(px) * 4)
        nodes_added = []
        for slot in obj.material_slots:
            mat = slot.material
            if mat is None or mat.node_tree is None:
                continue
            node = mat.node_tree.nodes.new("ShaderNodeTexImage")
            node.image = img
            mat.node_tree.nodes.active = node
            nodes_added.append((mat, node))
        if not nodes_added:
            raise RuntimeError("%s has no node material to bake into" % part)
        for o in scene.objects:
            o.select_set(False)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.bake(type="AO", use_clear=False, margin=int(params["margin_px"]), margin_type="EXTEND")
        path = out_dir / ("%s.png" % part)
        img.filepath_raw = str(path)
        img.file_format = "PNG"
        scene.render.image_settings.color_mode = "BW"
        img.save()
        for mat, node in nodes_added:
            mat.node_tree.nodes.remove(node)
        px_data = list(img.pixels)[0::4]
        n = len(px_data)
        mean = sum(px_data) / n
        report["parts"][part] = {"file": path.name, "px": int(px), "sha256": sha256(path),
                                 "mean": round(mean, 5), "min": round(min(px_data), 5), "max": round(max(px_data), 5)}
        bpy.data.images.remove(img)
    report["source_unchanged"] = sha256(source) == before
    Path(params["report_out"]).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["source_unchanged"]:
        raise RuntimeError("source GLB changed during the bake")
    print(MARKER, len(report["parts"]), "parts")


if __name__ == "__main__":
    main()
