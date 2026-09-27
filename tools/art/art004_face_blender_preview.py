"""Render the isolated face-winding correction in Blender's existing setup.

Reads the committed Medusa .blend, changes geometry only in memory, and writes
one diagnostic PNG. It does not save the .blend or production exports.
"""

import json
import os
from pathlib import Path

import bmesh
import bpy


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
ATLAS = ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json"
OUTPUT = ROOT / "docs/game-design/evidence/ART-004/medusa-facefix-blender-front-2026-09-28.png"
KEEP_NORMALS = os.environ.get("ART004_FACE_KEEP_NORMALS", "0") == "1"
DISABLE_NORMAL_MAP = os.environ.get("ART004_FACE_DISABLE_NORMAL_MAP", "0") == "1"
if KEEP_NORMALS:
    OUTPUT = OUTPUT.with_name("medusa-facefix-blender-front-keepnormals-2026-09-28.png")
if DISABLE_NORMAL_MAP:
    OUTPUT = OUTPUT.with_name("medusa-facefix-blender-front-nonormalmap-2026-09-28.png")


def main():
    if Path(bpy.data.filepath).resolve() != BLEND.resolve():
        raise RuntimeError("Launch Blender with medusa.blend before --python")
    body = bpy.data.objects["SK_Medusa_Body"]
    mesh = body.data
    cell = json.loads(ATLAS.read_text(encoding="utf-8"))["cells"]["tripo_part_10"]
    u_min = (cell["x"] + cell["inset"]) / 2048
    u_max = (cell["x"] + cell["cell"] - cell["inset"]) / 2048
    v_min = 1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / 2048
    v_max = 1 - (cell["y_top"] + cell["inset"]) / 2048
    uv = mesh.uv_layers.active.data
    selected = {poly.index for poly in mesh.polygons
                if all(u_min <= uv[loop].uv.x <= u_max and
                       v_min <= uv[loop].uv.y <= v_max
                       for loop in poly.loop_indices)}
    assert len(selected) == 587, len(selected)
    editable = bmesh.new()
    editable.from_mesh(mesh)
    editable.faces.index_update()
    for face in editable.faces:
        if face.index in selected:
            face.normal_flip()
    editable.to_mesh(mesh)
    editable.free()
    custom = mesh.attributes.get("custom_normal")
    if custom and not KEEP_NORMALS:
        mesh.attributes.remove(custom)
    mesh.update()
    if DISABLE_NORMAL_MAP:
        material = bpy.data.materials["M_Medusa_Atlas"]
        normal_nodes = [node for node in material.node_tree.nodes if node.type == "NORMAL_MAP"]
        assert len(normal_nodes) == 1, len(normal_nodes)
        normal_nodes[0].inputs["Strength"].default_value = 0.0
    arm = bpy.data.objects["SKEL_Medusa"]
    arm.animation_data.action = bpy.data.actions["Idle"]
    bpy.context.scene.frame_set(29)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(OUTPUT)
    bpy.ops.render.render(write_still=True)
    print("ART004_FACE_BLENDER_PREVIEW_COMPLETE", OUTPUT)


main()
