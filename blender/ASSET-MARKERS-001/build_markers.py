"""Build an editable, neutral ART-003/005 gameplay marker kit in metres.

Dimensions and profile choices follow the provisional 04-blender-production.md
card. This scene is a design candidate; it does not decide AD-CNF-22/AD-OPEN-42
or implement UE material parameters and fighterId binding.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "blender/ASSET-MARKERS-001"
BLEND = OUT / "markers.blend"
PREVIEW = OUT / "preview/markers-kit-neutral-v1.png"
REPORT = OUT / "build-report.json"


def material(name: str, color: tuple[float, float, float]) -> bpy.types.Material:
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1.0)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.83
    bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def mesh_object(name: str, vertices, faces, collection, mat, uv: bool = True):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.validate()
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    obj.data.materials.append(mat)
    if uv:
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(island_margin=0.015)
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.data.uv_layers.active.name = "UV0"
    return obj


def outline_point(index: int, segments: int, hexagonal: bool):
    if not hexagonal:
        angle = 2 * math.pi * index / segments
        return math.cos(angle), math.sin(angle)
    per_edge = segments // 6
    side, step = divmod(index, per_edge)
    a = 2 * math.pi * side / 6
    b = 2 * math.pi * (side + 1) / 6
    t = step / per_edge
    return ((1 - t) * math.cos(a) + t * math.cos(b), (1 - t) * math.sin(a) + t * math.sin(b))


def base(name: str, radius: float, height: float, hexagonal: bool, collection, mat):
    n = 48
    # Bevel at both rims and a modest inset on top. The silhouette, rather
    # than a texture or fixed team color, conveys the team profile.
    profile = [
        (radius * 0.92, 0),
        (radius * 0.985, 0.004),
        (radius, 0.011),
        (radius, height - 0.012),
        (radius * 0.96, height - 0.004),
        (radius * 0.82, height),
    ]
    verts = []
    for r, z in profile:
        for i in range(n):
            x, y = outline_point(i, n, hexagonal)
            verts.append((r * x, r * y, z))
    bottom_center, top_center = len(verts), len(verts) + 1
    verts += [(0, 0, 0), (0, 0, height)]
    faces = []
    for p in range(len(profile) - 1):
        for i in range(n):
            j = (i + 1) % n
            faces.append((p * n + i, p * n + j, (p + 1) * n + j, (p + 1) * n + i))
    for i in range(n):
        j = (i + 1) % n
        faces.append((bottom_center, j, i))
        last = (len(profile) - 1) * n
        faces.append((top_center, last + i, last + j))
    return mesh_object(name, verts, faces, collection, mat)


def annular_arc(vertices, faces, inner: float, outer: float, z: float, start: float, span: float, steps: int, closed: bool):
    profile = [
        (inner, z), (outer, z), (outer, z + 0.004),
        (outer - 0.004, z + 0.008), (inner + 0.004, z + 0.008), (inner, z + 0.004),
    ]
    first = len(vertices)
    count = steps if closed else steps + 1
    for i in range(count):
        angle = start + span * i / steps
        for r, zz in profile:
            vertices.append((r * math.cos(angle), r * math.sin(angle), zz))
    for i in range(steps):
        j = (i + 1) % count
        for k in range(len(profile)):
            kp = (k + 1) % len(profile)
            faces.append((first + i * len(profile) + k, first + j * len(profile) + k,
                          first + j * len(profile) + kp, first + i * len(profile) + kp))
    if not closed:
        faces.append(tuple(first + k for k in range(len(profile))))
        faces.append(tuple(first + steps * len(profile) + k for k in reversed(range(len(profile)))))


def ring(name: str, inner: float, outer: float, z: float, target: bool, collection, mat):
    verts, faces = [], []
    if target:
        for quadrant in range(4):
            # Four diagonal brackets, with cardinal gaps reserved for readable
            # corners and the selected figure's base.
            annular_arc(verts, faces, inner, outer, z,
                        math.pi * (quadrant / 2 + 0.12), math.pi * 0.26, 16, False)
    else:
        annular_arc(verts, faces, inner, outer, z, 0, 2 * math.pi, 64, True)
    return mesh_object(name, verts, faces, collection, mat)


def add_box(verts, faces, x0, x1, y0, y1, z0, z1):
    n = len(verts)
    verts.extend([(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
                  (x0,y0,z1),(x1,y0,z1),(x1,y1,z1),(x0,y1,z1)])
    faces.extend(tuple(n + v for v in face) for face in [
        (3,2,1,0),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)
    ])


def status_stela(name: str, collection, mat):
    verts, faces = [], []
    add_box(verts, faces, -0.04, 0.04, -0.04, 0.04, 0, 0.014)
    add_box(verts, faces, -0.011, 0.011, -0.011, 0.011, 0.014, 0.236)
    # Vertical, icon-free diamond: gameplay supplies the status icon/meaning.
    diamond = [(0, 0.30), (0.06, 0.24), (0, 0.18), (-0.06, 0.24)]
    n = len(verts)
    verts.extend((x, -0.012, z) for x, z in diamond)
    verts.extend((x, 0.012, z) for x, z in diamond)
    faces.extend([(n+3,n+2,n+1,n), (n+4,n+5,n+6,n+7)])
    for i in range(4):
        j = (i + 1) % 4
        faces.append((n+i,n+j,n+4+j,n+4+i))
    return mesh_object(name, verts, faces, collection, mat)


def collision_target_arcs(collection, mat):
    """Four convex hit proxies follow the arcs and leave the figure centre free."""
    colliders = []
    for quadrant in range(4):
        start = math.pi * (quadrant / 2 + 0.12)
        span = math.pi * 0.26
        angles = [start + span * i / 8 for i in range(9)]
        perimeter = [(.235 * math.cos(a), .235 * math.sin(a)) for a in angles]
        perimeter += [(.205 * math.cos(angles[-1]), .205 * math.sin(angles[-1])),
                      (.205 * math.cos(angles[0]), .205 * math.sin(angles[0]))]
        count = len(perimeter)
        cross = []
        for i in range(count):
            a, b, c = perimeter[i], perimeter[(i + 1) % count], perimeter[(i + 2) % count]
            cross.append((b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]))
        if min(cross) <= 0:
            raise RuntimeError(f"Target collision hull {quadrant} is not convex")
        verts = [(x, y, z) for z in (0.015, 0.040) for x, y in perimeter]
        faces = []
        for i in range(count):
            j = (i + 1) % count
            faces.append((i, j, count + j, count + i))
        faces.extend([tuple(reversed(range(count))), tuple(range(count, 2 * count))])
        obj = mesh_object(f"UCX_SM_Marker_TargetRing_{quadrant:02d}", verts, faces, collection, mat, uv=False)
        obj.hide_render = True
        colliders.append(obj)
    return colliders


def render_preview(objects, preview_collection):
    base_mat = material("M_Preview_Table", (0.18, 0.20, 0.22))
    caption_mat = material("M_Preview_Caption", (0.80, 0.82, 0.79))
    layout = [
        ("SM_Base_Hero_P1", -0.78, 0.38, "Hero P1"),
        ("SM_Base_Hero_P2", -0.27, 0.38, "Hero P2"),
        ("SM_Base_Sidekick_P1", 0.27, 0.38, "Sidekick P1"),
        ("SM_Base_Sidekick_P2", 0.78, 0.38, "Sidekick P2"),
        ("SM_Marker_SelectionRing", -0.52, -0.34, "Selection"),
        ("SM_Marker_TargetRing", 0, -0.34, "Target"),
        ("SM_Marker_Status", 0.52, -0.34, "Status"),
    ]
    for name, x, y, label in layout:
        instance = objects[name].copy()
        instance.data = objects[name].data
        instance.name = name + "__PREVIEW"
        preview_collection.objects.link(instance)
        instance.hide_render = False
        instance.location = (x, y, 0)
        font = bpy.data.curves.new(label + "_Caption", "FONT")
        font.body = label
        font.size = 0.075
        font.align_x = "CENTER"
        font.align_y = "CENTER"
        caption = bpy.data.objects.new(label + "_Caption", font)
        preview_collection.objects.link(caption)
        caption.location = (x, y - 0.28, 0.004)
        caption.data.materials.append(caption_mat)
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, -0.018))
    floor = bpy.context.object
    floor.name = "Preview_Backdrop"
    for coll in list(floor.users_collection):
        coll.objects.unlink(floor)
    preview_collection.objects.link(floor)
    floor.data.materials.append(base_mat)
    bpy.ops.object.light_add(type="AREA", location=(-1.5, -1.0, 2.6))
    light = bpy.context.object
    light.name = "Preview_Key"
    light.data.energy = 370
    light.data.shape = "DISK"
    light.data.size = 3.0
    bpy.ops.object.camera_add(location=(0, -2.5, 2.8))
    camera = bpy.context.object
    camera.name = "Camera_MarkerKit_Preview"
    camera.rotation_euler = (Vector((0, 0, 0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.7
    scene = bpy.context.scene
    scene.camera = camera
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(PREVIEW)
    scene.world.color = (0.12, 0.12, 0.12)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    meshes = bpy.data.collections.new("ASSET_MARKERS_001_Meshes")
    collision = bpy.data.collections.new("ASSET_MARKERS_001_Collision")
    preview = bpy.data.collections.new("ASSET_MARKERS_001_PreviewOnly")
    for collection in (meshes, collision, preview):
        scene.collection.children.link(collection)
    base_mat = material("M_Marker_Base_NeutralPreview", (0.56, 0.55, 0.51))
    signal_mat = material("M_Marker_Signal_NeutralPreview", (0.76, 0.77, 0.73))
    objects = {}
    for name, radius, height, hexagonal in [
        ("SM_Base_Hero_P1", .15, .06, False),
        ("SM_Base_Hero_P2", .15, .06, True),
        ("SM_Base_Sidekick_P1", .11, .05, False),
        ("SM_Base_Sidekick_P2", .11, .05, True),
    ]:
        objects[name] = base(name, radius, height, hexagonal, meshes, base_mat)
    objects["SM_Marker_SelectionRing"] = ring("SM_Marker_SelectionRing", .178, .20, .022, False, meshes, signal_mat)
    objects["SM_Marker_TargetRing"] = ring("SM_Marker_TargetRing", .209, .23, .022, True, meshes, signal_mat)
    objects["SM_Marker_Status"] = status_stela("SM_Marker_Status", meshes, signal_mat)
    colliders = collision_target_arcs(collision, base_mat)
    for obj in objects.values():
        obj.hide_render = True
        if tuple(round(v, 6) for v in obj.location) != (0, 0, 0) or len(obj.data.materials) != 1:
            raise RuntimeError(f"Bad pivot or material slot: {obj.name}")
    render_preview(objects, preview)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.render.render(write_still=True)
    report = {"status": "candidate_only_no_ue_import", "unit_scale": scene.unit_settings.scale_length,
              "source_spec": "docs/game-design/04-blender-production.md §3.8 (provisional dimensions)",
              "meshes": {}, "collision": [obj.name for obj in colliders],
              "open": ["AD-CNF-22 / AD-OPEN-42 base ownership", "AD-CNF-19 combined-vs-separate FBX",
                       "team/status material parameters in UE", "QA-010 HUD/zones/low-settings check"]}
    for name, obj in objects.items():
        obj.data.calc_loop_triangles()
        zs = [v.co.z for v in obj.data.vertices]
        xs = [v.co.x for v in obj.data.vertices]
        ys = [v.co.y for v in obj.data.vertices]
        report["meshes"][name] = {
            "triangles": len(obj.data.loop_triangles), "material_slots": len(obj.data.materials),
            "uv_layers": [uv.name for uv in obj.data.uv_layers],
            "bounds_m": [[round(min(v), 5), round(max(v), 5)] for v in (xs, ys, zs)],
        }
        if len(obj.data.loop_triangles) > 2000 or not obj.data.uv_layers:
            raise RuntimeError(f"Marker mesh budget or UV missing: {name}")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART_MARKERS_BUILD_COMPLETE 7")


if __name__ == "__main__":
    main()
