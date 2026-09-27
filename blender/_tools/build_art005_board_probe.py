"""Build a provisional Cobble City surface probe from the pinned S04 runtime grid.

The decorative mesh contains no zone, hit-test or fighter data. Blender units
are metres; one 100 uu game cell is one metre. This is ART-005 evidence, not a
production board or a decision about the final palette/camera.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "docs/game-design/evidence/S04/board-contract.json"
MATERIALS = ROOT / "art/imagegen/mvp-v1/materials/export"
OUT = ROOT / "blender/ASSET-BOARD-COBBLE-001"
PREVIEW = OUT / "preview"
BLEND = OUT / "cobble-city-probe.blend"
REPORT = OUT / "build-report.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def collection(name: str):
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def material(name: str, file_name: str, roughness: float):
    result = bpy.data.materials.new(name)
    result.use_nodes = True
    nodes = result.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(MATERIALS / file_name), check_existing=True)
    tex.interpolation = "Linear"
    result.node_tree.links.new(tex.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = roughness
    return result


def flat_material(name: str, color, roughness: float = 0.85):
    result = bpy.data.materials.new(name)
    result.diffuse_color = (*color, 1.0)
    result.use_nodes = True
    shader = result.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    return result


def add_box(name: str, center, dimensions, mat, target, uv_mode="box"):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for old in tuple(obj.users_collection):
        old.objects.unlink(obj)
    target.objects.link(obj)
    obj.data.materials.append(mat)
    uv = obj.data.uv_layers.active or obj.data.uv_layers.new(name="UV0")
    for face in obj.data.polygons:
        normal = face.normal
        dominant = max(range(3), key=lambda axis: abs(normal[axis]))
        axes = ((1, 2), (0, 2), (0, 1))[dominant]
        for loop_index in face.loop_indices:
            point = obj.data.vertices[obj.data.loops[loop_index].vertex_index].co
            # A single source image spans each rail, avoiding the old-wood
            # image's unaccepted repeating seam in this probe.
            u = point[axes[0]] / dimensions[axes[0]] + 0.5
            v = point[axes[1]] / dimensions[axes[1]] + 0.5
            uv.data[loop_index].uv = (u, v)
    obj["art_layer"] = "decor"
    return obj


def tile_mesh(x: int, y: int, mat, target):
    """A shallow, non-colliding stone tile; top displacement stays below Z=0."""
    name = f"StoneTile_{x}_{y}"
    subdivisions = 4
    edge = 0.985  # ~1.5 uu seam between 100 uu cell centres
    verts = []
    for j in range(subdivisions + 1):
        for i in range(subdivisions + 1):
            lx = (i / subdivisions - 0.5) * edge
            ly = (j / subdivisions - 0.5) * edge
            wave = abs(math.sin((x * 9 + i * 3) * 1.17) * math.cos((y * 7 + j * 5) * 1.31))
            z = -0.012 * wave  # up to 1.2 uu, below gameplay plane
            verts.append((lx, ly, z))
    faces = []
    for j in range(subdivisions):
        for i in range(subdivisions):
            a = j * (subdivisions + 1) + i
            faces.append((a, a + 1, a + subdivisions + 2, a + subdivisions + 1))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    obj.location = (x - 2, y - 2.5, 0)
    mesh.materials.append(mat)
    uv = mesh.uv_layers.new(name="UV0")
    # Quadrant offsets break the most obvious repeated-image pattern while
    # tile seams remain physically separate. Texture suitability is still open.
    offset_u = (x * 3 + y * 5) % 4 / 4
    offset_v = (x * 7 + y * 2) % 4 / 4
    for face in mesh.polygons:
        for loop_index in face.loop_indices:
            point = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            uv.data[loop_index].uv = (offset_u + (point.x / edge + 0.5) / 4,
                                       offset_v + (point.y / edge + 0.5) / 4)
    obj["art_layer"] = "board_surface"
    obj["cell_key"] = f"{x}:{y}"
    obj["gameplay_collision"] = False
    return obj


def camera(name: str, position, target, fov: float):
    data = bpy.data.cameras.new(name)
    data.type = "PERSP"
    data.sensor_fit = "HORIZONTAL"
    data.angle = math.radians(fov)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def light(name: str, kind: str, location, color, energy: float, *, shadows=True, size=3.0):
    data = bpy.data.lights.new(name, kind)
    data.energy = energy
    data.color = color
    data.use_shadow = shadows
    if kind == "AREA":
        data.shape = "DISK"
        data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = (Vector((0, 0, 0)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    return obj


def main():
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    cells = contract["cells"]
    assert (contract["width"], contract["height"], len(cells), contract["cellSizeUu"]) == (5, 6, 30, 100)
    assert all(len(cell["zones"]) == 1 for cell in cells)
    assert {zone: sum(zone in c["zones"] for c in cells) for zone in ("blue", "red")} == {"blue": 15, "red": 15}
    assert not contract["multiZoneCells"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.world = bpy.data.worlds.new("ART005_Studio_World")
    scene.world.color = (0.07, 0.08, 0.11)
    scene.view_settings.view_transform = "AgX"
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    stone = material("M_ART005_Stone_Provisional", "T_cobblestone_D_1024.png", 0.82)
    wood = material("M_ART005_Wood_Provisional", "T_old_wood_D_1024.png", 0.80)
    rock = flat_material("M_ART005_Undertray_Provisional", (0.14, 0.16, 0.18))
    surface = collection("L2_Decorative_Stone_NoCollision")
    frame = collection("L2_Wood_Frame_NoCollision")
    foundation = collection("L3_Undertray_NoCollision")
    for cell in cells:
        tile_mesh(cell["x"], cell["y"], stone, surface)
    add_box("Rock_Undertray", (0, 0, -0.19), (5.56, 6.56, 0.24), rock, foundation)
    add_box("Frame_West", (-2.615, 0, -0.03), (0.23, 6.46, 0.16), wood, frame)
    add_box("Frame_East", (2.615, 0, -0.03), (0.23, 6.46, 0.16), wood, frame)
    add_box("Frame_North", (0, 3.115, -0.03), (5.00, 0.23, 0.16), wood, frame)
    add_box("Frame_South", (0, -3.115, -0.03), (5.00, 0.23, 0.16), wood, frame)
    # A physically separate exact grid is for gameplay. Here it is retained
    # as metadata only; the UE proof creates hit surfaces from cells[] directly.
    camera_obj = camera("Camera_K1_Proposed_NotApproved", (0, -10.324, 14.744), (0, 0, 0), 35)
    scene.camera = camera_obj
    light("Cool_Key_Probe", "AREA", (-4, -2, 8), (0.65, 0.76, 1.0), 1400, size=5.0)
    light("Warm_Lantern_Probe", "POINT", (2.5, -3.0, 2), (1.0, 0.58, 0.26), 120, shadows=False)
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.filepath = str(PREVIEW / "board-surface-k1-blender.png")
    bpy.ops.render.render(write_still=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(BLEND))
    report = {
        "status": "provisional_art005_surface_probe",
        "source_contract": str(CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "source_contract_sha256": sha(CONTRACT),
        "grid": {"width": 5, "height": 6, "cells": 30, "cell_uu": 100},
        "zones": {"blue": 15, "red": 15, "encoded_in_art_mesh": False},
        "mesh_parts": {"surface_tiles": len(surface.objects), "frame": len(frame.objects), "foundation": len(foundation.objects)},
        "surface_relief_max_uu": 1.2,
        "wood_texture_note": "T_old_wood_D_1024 has unaccepted repeating seams; probe maps one image per rail",
        "source_textures": [
            {"path": str((MATERIALS / name).relative_to(ROOT)).replace("\\", "/"), "sha256": sha(MATERIALS / name)}
            for name in ("T_cobblestone_D_1024.png", "T_old_wood_D_1024.png")
        ],
        "approval": "none; boardState-driven zone visuals, final material and GD-058 remain open",
    }
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("ART005_BOARD_BUILD_COMPLETE 30")


if __name__ == "__main__":
    main()
