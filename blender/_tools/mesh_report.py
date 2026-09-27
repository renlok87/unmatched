"""Generate the repeatable ART-001 Blender-side geometry report."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

import bpy


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "blender" / "_shared" / "check_set"


def triangle_count(obj) -> int:
    return sum(max(0, len(poly.vertices) - 2) for poly in obj.data.polygons)


def max_influences(obj) -> int:
    maximum = 0
    for vertex in obj.data.vertices:
        active = sum(1 for assignment in vertex.groups if assignment.weight > 1e-5)
        maximum = max(maximum, active)
    return maximum


def almost(value: float, expected: float, tolerance: float = 1e-5) -> bool:
    return abs(value - expected) <= tolerance


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    failures = []
    for obj in sorted((item for item in bpy.data.objects if item.type == "MESH"), key=lambda item: item.name):
        dimensions = [float(value) for value in obj.dimensions]
        materials = [slot.material.name if slot.material else "" for slot in obj.material_slots]
        unapplied = not all(almost(value, 1.0) for value in obj.scale) or any(
            not almost(value, 0.0) for value in obj.rotation_euler
        )
        negative_scale = math.prod(float(value) for value in obj.scale) < 0.0
        influences = max_influences(obj)
        status = "PASS"
        reasons = []
        if unapplied:
            reasons.append("unapplied transform")
        if negative_scale:
            reasons.append("negative scale")
        if not obj.data.uv_layers:
            reasons.append("missing UV0")
        if influences > 4:
            reasons.append(f"{influences} vertex influences")
        if not obj.name.startswith(("SM_", "SK_", "UCX_", "UCP_", "UBX_", "USP_", "ART001_")):
            reasons.append("invalid object prefix")
        if reasons:
            status = "FAIL"
            failures.append({"object": obj.name, "reasons": reasons})
        rows.append(
            {
                "object": obj.name,
                "tris": triangle_count(obj),
                "material_slots": len(obj.material_slots),
                "materials": ";".join(materials),
                "uv_channels": len(obj.data.uv_layers),
                "max_vertex_influences": influences,
                "dimensions_m": "x".join(f"{value:.4f}" for value in dimensions),
                "negative_scale": negative_scale,
                "unapplied_transform": unapplied,
                "status": status,
                "notes": "; ".join(reasons),
            }
        )

    expected = {
        "cube_dimensions": all(almost(v, 1.0) for v in bpy.data.objects["SM_ART001_Cube"].dimensions),
        "cube_bottom_origin": all(almost(v, 0.0) for v in bpy.data.objects["SM_ART001_Cube"].location),
        "arrow_authored_minus_y": bpy.data.objects["SM_ART001_Arrow"].bound_box[0][1] <= 0.0,
        "mannequin_height_050m": almost(bpy.data.objects["SM_ART001_Mannequin"].dimensions.z, 0.5),
        "mannequin_one_material": len(bpy.data.objects["SM_ART001_Mannequin"].material_slots) == 1,
        "collision_present": "UCX_SM_ART001_Mannequin_00" in bpy.data.objects,
        "rig_17_bones": len(bpy.data.objects["SKEL_ART001_Mannequin"].data.bones) == 17,
        "root_motion_action": "AM_ART001_RootMotion" in bpy.data.actions,
    }
    for check_name, passed in expected.items():
        if not passed:
            failures.append({"check": check_name, "reasons": ["expected condition is false"]})

    csv_path = OUT / "REPORT-mesh.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {
        "blender_version": bpy.app.version_string,
        "checks": expected,
        "objects": rows,
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }
    (OUT / "mesh-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("ART001_MESH_REPORT " + json.dumps({"result": report["result"], "failures": failures}, ensure_ascii=False))
    if failures:
        raise RuntimeError(f"ART-001 mesh report failed: {failures}")


if __name__ == "__main__":
    main()
