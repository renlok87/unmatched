"""Inspect the four ART-005 frame rails without changing the source blend."""

from __future__ import annotations

import json
from pathlib import Path

import bpy


rails = {}
for name in ("Frame_West", "Frame_East", "Frame_North", "Frame_South"):
    obj = bpy.data.objects[name]
    uv = obj.data.uv_layers.active
    if obj.type != "MESH" or uv is None:
        raise RuntimeError(f"Missing frame mesh or active UV layer: {name}")
    top = [face for face in obj.data.polygons if face.normal.z > 0.9]
    if len(top) != 1:
        raise RuntimeError(f"Expected one top face on {name}, got {len(top)}")
    face = top[0]
    rails[name] = {
        "dimensions_m": [round(value, 4) for value in obj.dimensions],
        "uv_layer": uv.name,
        "top_loop_xy_uv": [
            {
                "xy": [round(obj.data.vertices[obj.data.loops[index].vertex_index].co[axis], 4)
                       for axis in (0, 1)],
                "uv": [round(uv.data[index].uv[axis], 4) for axis in (0, 1)],
            }
            for index in face.loop_indices
        ],
    }
images = {}
for name in ("M_ART005_Wood_Provisional", "M_ART005_Stone_AtlasB_Provisional"):
    material = bpy.data.materials[name]
    nodes = [node for node in material.node_tree.nodes if node.type == "TEX_IMAGE"]
    if len(nodes) != 1 or nodes[0].image is None:
        raise RuntimeError(f"Missing BaseColor image in {name}")
    image_path = Path(bpy.path.abspath(nodes[0].image.filepath))
    images[name] = {"path": str(image_path), "exists": image_path.is_file()}
    if not image_path.is_file():
        raise RuntimeError(f"Missing linked image for {name}: {image_path}")
print("ART005_WOOD_UV_PROBE " + json.dumps({"rails": rails, "images": images}, sort_keys=True))
