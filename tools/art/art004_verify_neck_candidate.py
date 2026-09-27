"""Verify that Medusa v2 only reverses the rear-neck atlas part.

Run with Blender 5.2 in the repository root. This reads the committed .blend
and both tracked FBXs; it changes no source file.
"""

import json
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "blender/ASSET-MEDUSA-001/medusa.blend"
ATLAS = json.loads((ROOT / "blender/ASSET-MEDUSA-001/atlas-report.json").read_text())
OLD = ROOT / "blender/ASSET-MEDUSA-001/variants/face-section-v1/SK_Medusa_FaceSection_v1.fbx"
NEW = ROOT / "blender/ASSET-MEDUSA-001/variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx"


def bounds(part):
    cell = ATLAS["cells"][part]
    inset, size = cell["inset"], cell["cell"]
    return ((cell["x"] + inset) / 2048,
            (cell["x"] + size - inset) / 2048,
            1 - (cell["y_top"] + size - inset) / 2048,
            1 - (cell["y_top"] + inset) / 2048)


def in_part(uv_values, part):
    lo_u, hi_u, lo_v, hi_v = bounds(part)
    return all(lo_u - 1e-5 <= u <= hi_u + 1e-5 and
               lo_v - 1e-5 <= v <= hi_v + 1e-5 for u, v in uv_values)


def source_audit():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    mesh = bpy.data.objects["SK_Medusa_Body"].data
    uv = mesh.uv_layers.active.data
    neck = [poly for poly in mesh.polygons if in_part(
        [tuple(uv[loop].uv) for loop in poly.loop_indices], "tripo_part_14")]
    face = [poly for poly in mesh.polygons if in_part(
        [tuple(uv[loop].uv) for loop in poly.loop_indices], "tripo_part_10")]
    assert len(neck) == 480 and len(face) == 587, (len(neck), len(face))
    return {"neck_polygons": len(neck),
            "neck_normals_facing_front": sum(poly.normal.y < -.1 for poly in neck),
            "neck_normals_facing_back": sum(poly.normal.y > .1 for poly in neck),
            "face_polygons": len(face)}


def inspect_fbx(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(path), use_custom_normals=True)
    meshes = {}
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        mesh = obj.data
        records = {}
        for poly in mesh.polygons:
            key = tuple(sorted(poly.vertices))
            assert key not in records, f"Repeated triangle {key} in {obj.name}"
            records[key] = {
                "order": tuple(poly.vertices),
                "material": poly.material_index,
                "uv": {mesh.loops[loop].vertex_index:
                       tuple(round(x, 5) for x in mesh.uv_layers.active.data[loop].uv)
                       for loop in poly.loop_indices},
                "normal": {mesh.loops[loop].vertex_index:
                           tuple(round(x, 4) for x in mesh.corner_normals[loop].vector)
                           for loop in poly.loop_indices},
            }
        meshes[obj.name] = {
            "positions": [tuple(round(x, 5) for x in vertex.co) for vertex in mesh.vertices],
            "records": records,
            "slots": len(mesh.materials),
        }
    armatures = [obj for obj in bpy.data.objects if obj.type == "ARMATURE"]
    assert len(armatures) == 1 and len(armatures[0].data.bones) == 17
    return meshes


def is_cyclic(a, b):
    return any(tuple(a[(i + offset) % 3] for i in range(3)) == b
               for offset in range(3))


def verify():
    source = source_audit()
    before, after = inspect_fbx(OLD), inspect_fbx(NEW)
    assert before.keys() == after.keys() == {"SK_Medusa_Body", "SK_Medusa_Bow"}
    summary = {}
    for name in sorted(before):
        left, right = before[name], after[name]
        assert left["positions"] == right["positions"], f"Vertex positions changed: {name}"
        assert left["slots"] == right["slots"] == (2 if name.endswith("Body") else 1)
        old, new = left["records"], right["records"]
        assert old.keys() == new.keys(), f"Triangle set changed: {name}"
        neck = {key for key, record in old.items()
                if in_part(record["uv"].values(), "tripo_part_14")}
        face = {key for key, record in old.items()
                if in_part(record["uv"].values(), "tripo_part_10")}
        if name.endswith("Body"):
            assert len(neck) == 480 and len(face) == 587
        else:
            assert not neck and not face
        flips = set()
        max_normal_error = 0.0
        for key, a in old.items():
            b = new[key]
            assert a["material"] == b["material"], f"Material changed: {name} {key}"
            assert a["uv"] == b["uv"], f"UV changed: {name} {key}"
            if is_cyclic(a["order"], b["order"]):
                assert a["normal"] == b["normal"], f"Normal changed outside neck: {name} {key}"
            else:
                assert is_cyclic(tuple(reversed(a["order"])), b["order"])
                flips.add(key)
                for vertex in a["normal"]:
                    for axis in range(3):
                        error = abs(a["normal"][vertex][axis] + b["normal"][vertex][axis])
                        max_normal_error = max(max_normal_error, error)
                        assert error <= .0005, f"Normal did not invert: {name} {key}"
        assert flips == neck, f"Unexpected winding changes: {name}"
        if name.endswith("Body"):
            assert all(old[key]["material"] == 1 for key in face)
            assert all(old[key]["material"] == 0 for key in neck)
        summary[name] = {"vertices": len(left["positions"]), "triangles": len(old),
                         "flipped_neck_triangles": len(flips),
                         "max_normal_inversion_error": round(max_normal_error, 6)}
    print("ART004_NECK_CANDIDATE_OK", json.dumps({"source": source, "meshes": summary}, sort_keys=True))


verify()
