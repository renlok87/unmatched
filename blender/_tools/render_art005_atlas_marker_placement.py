"""Compare a non-occluding Harpy number placement in the ART-005 atlas probe.

The labels are review-only parts from ART-003, not production HUD meshes. This
script opens a separate six-blockout scene and leaves its source untouched.
"""

from __future__ import annotations

import json
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
VARIANT = ROOT / "blender/ASSET-BOARD-COBBLE-001/variants/B-atlas-v1"
SOURCE = VARIANT / "cobble-city-atlas-B-six-blockouts.blend"
OUT = VARIANT / "marker-placement-v2"
SCENE = OUT / "cobble-city-atlas-B-six-blockouts-markers-v2.blend"
PREVIEW = OUT / "board-six-figures-k1-markers-v2.png"
REPORT = OUT / "marker-placement-report.json"


def screen_rect(obj: bpy.types.Object, scene: bpy.types.Scene) -> tuple[float, float, float, float]:
    camera = scene.camera
    assert camera is not None
    points = [world_to_camera_view(scene, camera, obj.matrix_world @ Vector(c)) for c in obj.bound_box]
    width, height = scene.render.resolution_x, scene.render.resolution_y
    return (
        min(p.x for p in points) * width,
        min(1 - p.y for p in points) * height,
        max(p.x for p in points) * width,
        max(1 - p.y for p in points) * height,
    )


def overlap_area(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    if (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage) != (1280, 720, 100):
        raise RuntimeError("Expected the original 1280x720 comparison camera")
    if scene.camera is None:
        raise RuntimeError("Missing K1 probe camera")

    results = []
    for index in range(3):
        fighter_id = f"f-0-sk{index}"
        plate = bpy.data.objects.get(f"{fighter_id}_ProbePlate")
        digit = bpy.data.objects.get(f"{fighter_id}_Digit")
        if plate is None or digit is None or digit.type != "FONT":
            raise RuntimeError(f"Missing review-only marker pair for {fighter_id}")
        old_center = tuple(round(v, 4) for v in plate.location)
        # The plate stays within the same 1 m tile: +X moves it beside the
        # base, -Y moves it towards the K1 camera, and low Z clears the wings.
        target = Vector((old_center[0] + 0.32, old_center[1] - 0.33, 0.08))
        delta = target - plate.location
        plate.location += delta
        digit.location += delta
        results.append({"fighter_id": fighter_id, "digit": index + 1, "old_center_m": old_center, "new_center_m": tuple(round(v, 4) for v in plate.location)})

    bpy.context.view_layer.update()
    for result in results:
        fighter_id = result["fighter_id"]
        plate = bpy.data.objects[f"{fighter_id}_ProbePlate"]
        marker_rect = screen_rect(plate, scene)
        silhouette_objects = [o for o in bpy.data.objects if o.name.startswith(fighter_id + "__") and o.type == "MESH"]
        if not silhouette_objects:
            raise RuntimeError(f"No figure parts for {fighter_id}")
        silhouette_rect = (
            min(screen_rect(o, scene)[0] for o in silhouette_objects),
            min(screen_rect(o, scene)[1] for o in silhouette_objects),
            max(screen_rect(o, scene)[2] for o in silhouette_objects),
            max(screen_rect(o, scene)[3] for o in silhouette_objects),
        )
        result["marker_rect_px"] = [round(v, 1) for v in marker_rect]
        result["figure_rect_px"] = [round(v, 1) for v in silhouette_rect]
        result["projected_bbox_overlap_px2"] = round(overlap_area(marker_rect, silhouette_rect), 1)
        result["front_gap_px"] = round(marker_rect[1] - silhouette_rect[3], 1)
        if result["front_gap_px"] < 5:
            raise RuntimeError(f"Marker too close to {fighter_id} silhouette: {result['front_gap_px']} px")

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 16
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 4
    scene.render.filepath = str(PREVIEW)
    scene.render.image_settings.file_format = "PNG"
    bpy.ops.wm.save_as_mainfile(filepath=str(SCENE))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(SCENE))
    bpy.ops.render.render(write_still=True)

    report = {
        "scope": "Review-only placement of three Harpy number plates; not a UE/HUD test",
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "output_scene": str(SCENE.relative_to(ROOT)).replace("\\", "/"),
        "preview": str(PREVIEW.relative_to(ROOT)).replace("\\", "/"),
        "render": "Cycles CPU, 4 threads, 16 samples, 1280x720",
        "fighters": results,
        "limits": "Bounding boxes are conservative screen-space proxies; visual review is required. No zones, selection, HUD, UE import, or gameplay identity binding.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART005_MARKER_PLACEMENT_V2_COMPLETE")


if __name__ == "__main__":
    main()
