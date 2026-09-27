"""Check that the saved modular corner source still matches its export report."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
VARIANT = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/corner-bracket-v1"
report = json.loads((VARIANT / "build-report.json").read_text(encoding="utf-8"))
blend = VARIANT / "corner-bracket-v1.blend"
fbx = VARIANT / "export/SM_ART005_CornerBracket_v1.fbx"
assert Path(bpy.data.filepath).resolve() == blend.resolve()
assert hashlib.sha256(blend.read_bytes()).hexdigest() == report["blend_sha256"]
assert hashlib.sha256(fbx.read_bytes()).hexdigest() == report["fbx_sha256"]

objects = [obj for obj in bpy.data.objects if obj.type == "MESH"]
assert len(objects) == report["parts"] == 1
mesh = objects[0].data
assert len(mesh.vertices) == report["vertices"] == 44
assert sum(len(face.vertices) - 2 for face in mesh.polygons) == report["triangles"] == 76
assert len(mesh.materials) == report["material_slots"] == 1
assert objects[0]["gameplay_collision"] is False
shader = mesh.materials[0].node_tree.nodes.get("Principled BSDF")
candidate = report["material_candidate"]
color = shader.inputs["Base Color"].default_value
assert all(abs(color[index] - value) < 1e-5 for index, value in enumerate(candidate["base_color_linear"]))
assert abs(shader.inputs["Metallic"].default_value - candidate["metallic"]) < 1e-5
assert abs(shader.inputs["Roughness"].default_value - candidate["roughness"]) < 1e-5
print("ART005_CORNER_BRACKET_RELOAD_PASS")
