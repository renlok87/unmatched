"""Inspect source Medusa atlas-part bounds and head rig weights without edits."""

from __future__ import annotations

import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
if Path(bpy.data.filepath).resolve() != BLEND.resolve():
    raise RuntimeError("Launch Blender with the source Medusa .blend before --python")
ATLAS = json.loads((ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json").read_text())
BODY = bpy.data.objects["SK_Medusa_Body"]
MESH = BODY.data
UV = MESH.uv_layers.active.data
RESULTS = {}

for name, cell in ATLAS["cells"].items():
    u_min = (cell["x"] + cell["inset"]) / 2048
    u_max = (cell["x"] + cell["cell"] - cell["inset"]) / 2048
    v_min = 1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / 2048
    v_max = 1 - (cell["y_top"] + cell["inset"]) / 2048
    polygons = [poly for poly in MESH.polygons if all(
        u_min <= UV[loop].uv.x <= u_max and v_min <= UV[loop].uv.y <= v_max
        for loop in poly.loop_indices)]
    if not polygons:
        continue
    indices = {index for poly in polygons for index in poly.vertices}
    coords = [MESH.vertices[index].co for index in indices]
    groups = {}
    for index in indices:
        for assignment in MESH.vertices[index].groups:
            label = BODY.vertex_groups[assignment.group].name
            groups[label] = groups.get(label, 0.0) + assignment.weight
    RESULTS[name] = {
        "polygons": len(polygons),
        "vertices": len(indices),
        "bounds_m": [[round(min(co[axis] for co in coords), 5),
                       round(max(co[axis] for co in coords), 5)] for axis in range(3)],
        "rig_weight_totals": {key: round(value, 1) for key, value in sorted(
            groups.items(), key=lambda item: -item[1])[:4]},
    }

    if name == "tripo_part_1":
        # Connected islands tell us whether the snakes can be posed independently.
        parent = {index: index for index in indices}

        def root(index):
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        for poly in polygons:
            verts = list(poly.vertices)
            for index in verts[1:]:
                parent[root(index)] = root(verts[0])
        # FBX/Tripo split most shared positions into separate vertex IDs.
        # Rejoin coincident positions before interpreting islands as snakes.
        by_position = {}
        for index in indices:
            position = tuple(round(value, 5) for value in MESH.vertices[index].co)
            if position in by_position:
                parent[root(index)] = root(by_position[position])
            else:
                by_position[position] = index
        islands = {}
        for index in indices:
            islands.setdefault(root(index), []).append(index)
        sorted_islands = sorted(islands.values(), key=len, reverse=True)
        RESULTS[name]["islands"] = [{
            "vertices": len(island),
            "bounds_m": [[round(min(MESH.vertices[index].co[axis] for index in island), 5),
                          round(max(MESH.vertices[index].co[axis] for index in island), 5)]
                         for axis in range(3)],
        } for island in sorted_islands]
        height_components = {}
        for height in (.445, .455, .465, .475, .485, .495, .505, .515, .525, .535):
            high = {index for index in indices if MESH.vertices[index].co.z >= height}
            high_parent = {index: index for index in high}

            def high_root(index):
                while high_parent[index] != index:
                    high_parent[index] = high_parent[high_parent[index]]
                    index = high_parent[index]
                return index

            for poly in polygons:
                verts = [index for index in poly.vertices if index in high]
                for index in verts[1:]:
                    high_parent[high_root(index)] = high_root(verts[0])
            by_position = {}
            for index in high:
                position = tuple(round(value, 5) for value in MESH.vertices[index].co)
                if position in by_position:
                    high_parent[high_root(index)] = high_root(by_position[position])
                else:
                    by_position[position] = index
            components = {}
            for index in high:
                components.setdefault(high_root(index), []).append(index)
            height_components[str(height)] = [{
                "vertices": len(island),
                "center_m": [round(sum(MESH.vertices[index].co[axis] for index in island)
                                   / len(island), 5) for axis in range(3)],
                "bounds_m": [[round(min(MESH.vertices[index].co[axis] for index in island), 5),
                              round(max(MESH.vertices[index].co[axis] for index in island), 5)]
                             for axis in range(3)]
            } for island in sorted(components.values(), key=len, reverse=True)
               if len(island) >= 10]
        RESULTS[name]["height_components"] = height_components

OUT = ROOT / "unreal/Unmatched/Artifacts/ART004Face/source-part-bounds.json"
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(RESULTS, indent=2) + "\n")
for name, result in RESULTS.items():
    print("ART004_PART", name, result)
print("ART004_PART_PROBE_PASS", OUT)
