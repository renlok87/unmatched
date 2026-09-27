"""Audit Medusa source-part winding without altering production assets."""

import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-MEDUSA-001/tripo-source/b6253e58/medusa-segmented-retopo.glb"
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
ATLAS = ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json"
OUTPUT = ROOT / "unreal/Unmatched/Artifacts/ART004Face/source-orientation-audit.json"


def summary(obj):
    mesh = obj.data
    normals = [poly.normal.y for poly in mesh.polygons]
    return {
        "polygons": len(mesh.polygons),
        "triangles": sum(len(poly.vertices) - 2 for poly in mesh.polygons),
        "world_determinant": round(obj.matrix_world.determinant(), 6),
        "normal_y_positive_025": sum(value > .25 for value in normals),
        "normal_y_negative_025": sum(value < -.25 for value in normals),
        "custom_normal_attribute": bool(mesh.attributes.get("custom_normal")),
    }


def part_10_detail(obj):
    mesh = obj.data
    coordinates = [vertex.co for vertex in mesh.vertices]
    min_y = min(point.y for point in coordinates)
    max_y = max(point.y for point in coordinates)
    width = (max_y - min_y) / 5
    bins = [{"polygons": 0, "normal_y_positive_025": 0,
             "normal_y_negative_025": 0, "corner_dot_negative": 0,
             "corner_dot_positive": 0} for _ in range(5)]
    corner_normals = mesh.corner_normals
    polygons_by_vertex = [[] for _ in mesh.vertices]
    for poly in mesh.polygons:
        y = poly.center.y
        index = min(4, int((y - min_y) / width))
        bins[index]["polygons"] += 1
        bins[index]["normal_y_positive_025"] += poly.normal.y > .25
        bins[index]["normal_y_negative_025"] += poly.normal.y < -.25
        averaged = sum((corner_normals[loop].vector for loop in poly.loop_indices),
                       mesh.polygons[poly.index].normal * 0)
        dot = averaged.normalized().dot(poly.normal)
        bins[index]["corner_dot_negative"] += dot < -.25
        bins[index]["corner_dot_positive"] += dot > .25
        for vertex_index in poly.vertices:
            polygons_by_vertex[vertex_index].append(poly.index)
    seen = set()
    components = []
    for poly in mesh.polygons:
        if poly.index in seen:
            continue
        pending = [poly.index]
        seen.add(poly.index)
        component = []
        while pending:
            index = pending.pop()
            component.append(index)
            for vertex_index in mesh.polygons[index].vertices:
                for neighbor in polygons_by_vertex[vertex_index]:
                    if neighbor not in seen:
                        seen.add(neighbor)
                        pending.append(neighbor)
        ys = [mesh.polygons[index].center.y for index in component]
        components.append({"polygons": len(component),
                           "center_y_min": round(min(ys), 5),
                           "center_y_max": round(max(ys), 5)})
    components.sort(key=lambda item: -item["polygons"])
    return {"bounds": {axis: [round(min(point[i] for point in coordinates), 5),
                             round(max(point[i] for point in coordinates), 5)]
                       for i, axis in enumerate("xyz")},
            "y_bins": bins, "connected_components": components}


def joined_face_summary():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    obj = bpy.data.objects["SK_Medusa_Body"]
    mesh = obj.data
    cell = json.loads(ATLAS.read_text(encoding="utf-8"))["cells"]["tripo_part_10"]
    u_min = (cell["x"] + cell["inset"]) / 2048
    u_max = (cell["x"] + cell["cell"] - cell["inset"]) / 2048
    v_min = 1 - (cell["y_top"] + cell["cell"] - cell["inset"]) / 2048
    v_max = 1 - (cell["y_top"] + cell["inset"]) / 2048
    uv = mesh.uv_layers.active.data
    polys = [poly for poly in mesh.polygons
             if all(u_min <= uv[loop].uv.x <= u_max and
                    v_min <= uv[loop].uv.y <= v_max
                    for loop in poly.loop_indices)]
    assert len(polys) == 587, len(polys)
    return {
        "body": summary(obj),
        "part_10_polygons": len(polys),
        "part_10_normal_y_positive_025": sum(poly.normal.y > .25 for poly in polys),
        "part_10_normal_y_negative_025": sum(poly.normal.y < -.25 for poly in polys),
    }


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(SOURCE))
    source = {obj.name: summary(obj) for obj in bpy.data.objects if obj.type == "MESH"}
    assert len(source) == 15, len(source)
    report = {"source": str(SOURCE), "source_parts": source,
              "part_10_detail": part_10_detail(bpy.data.objects["tripo_part_10"]),
              "joined": joined_face_summary()}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("ART004_SOURCE_ORIENTATION_AUDIT_COMPLETE", str(OUTPUT),
          "part_10_polygons", source["tripo_part_10"]["polygons"],
          "joined_polygons", report["joined"]["part_10_polygons"])


main()
