"""Create neutral ART-003 silhouette probes, not production character meshes.

Run: blender --background --factory-startup --python blender/_tools/build_art003_blockouts.py
Source scale is metres; the pinned S04 100 uu cell is represented as one metre.
All character dimensions remain proposals until GD-058.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "blender" / "A01"
PREVIEW = OUT / "preview"
BOARD_CONTRACT = ROOT / "docs" / "game-design" / "evidence" / "S04" / "board-contract.json"
PARTS: dict[str, list[bpy.types.Object]] = {}
GAME_PARTS: list[bpy.types.Object] = []
BOARD_PARTS: list[bpy.types.Object] = []
LABEL_PARTS: list[bpy.types.Object] = []


def setup() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_cavity = True
    scene.display.shading.cavity_type = "BOTH"
    scene.display.shading.show_shadows = True
    scene.display.shading.background_type = "VIEWPORT"
    scene.display.shading.background_color = (0.70, 0.70, 0.70)
    OUT.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)


def collection(name: str) -> bpy.types.Collection:
    result = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(result)
    return result


def move_to_collection(obj: bpy.types.Object, target: bpy.types.Collection) -> bpy.types.Object:
    for old in tuple(obj.users_collection):
        old.objects.unlink(obj)
    target.objects.link(obj)
    return obj


def finish(obj: bpy.types.Object, name: str, target: bpy.types.Collection, shade: float) -> bpy.types.Object:
    obj.name = name
    obj.data.name = name
    obj.color = (shade, shade, shade, 1.0)
    move_to_collection(obj, target)
    return obj


def cube(name: str, pos, scale, target, shade=0.36):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=pos)
    obj = bpy.context.object
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return finish(obj, name, target, shade)


def cone(name: str, pos, bottom: float, top: float, depth: float, target, shade=0.36, sides=12):
    bpy.ops.mesh.primitive_cone_add(vertices=sides, radius1=bottom, radius2=top, depth=depth, location=pos)
    return finish(bpy.context.object, name, target, shade)


def cylinder(name: str, pos, radius: float, depth: float, target, shade=0.36, sides=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=sides, radius=radius, depth=depth, location=pos)
    return finish(bpy.context.object, name, target, shade)


def sphere(name: str, pos, radius: float, target, shade=0.36):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=radius, location=pos)
    return finish(bpy.context.object, name, target, shade)


def segment(name: str, a, b, radius: float, target, shade=0.36, sides=8):
    va, vb = Vector(a), Vector(b)
    mid = (va + vb) * 0.5
    direction = vb - va
    obj = cylinder(name, mid, radius, direction.length, target, shade, sides)
    obj.rotation_euler = Vector((0, 0, 1)).rotation_difference(direction).to_euler()
    return obj


def prism(name: str, points_xz, y: float, thickness: float, target, shade=0.36):
    count = len(points_xz)
    verts = [(x, y - thickness / 2, z) for x, z in points_xz]
    verts += [(x, y + thickness / 2, z) for x, z in points_xz]
    faces = [tuple(range(count - 1, -1, -1)), tuple(range(count, count * 2))]
    faces += [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    target.objects.link(obj)
    obj.color = (shade, shade, shade, 1.0)
    return obj


def base(target, radius: float, prefix: str):
    cylinder(prefix + "_Base", (0, 0, 0.025), radius, 0.05, target, 0.25, 20)


def medusa(target):
    base(target, 0.15, "Medusa")
    for sx in (-1, 1):
        segment(f"Medusa_Leg_{sx}", (sx * 0.038, 0, 0.06), (sx * 0.045, 0, 0.20), 0.024, target)
        segment(f"Medusa_Arm_{sx}", (sx * 0.075, -0.005, 0.36), (sx * 0.135, -0.035, 0.25), 0.022, target)
    cone("Medusa_Robe", (0, 0, 0.268), 0.11, 0.070, 0.19, target, 0.39)
    sphere("Medusa_Head", (0, -0.025, 0.405), 0.059, target, 0.46)
    # Five readable arcing locks stand in for the snake crown.
    for i in range(5):
        x = (i - 2) * 0.035
        segment(f"Medusa_Snake_{i}_A", (x, 0, 0.447), (x * 1.5, 0.015, 0.510), 0.016, target)
        segment(f"Medusa_Snake_{i}_B", (x * 1.5, 0.015, 0.510), (x * 1.9, -0.014, 0.535 - abs(x) * 0.3), 0.013, target)
    # Bow is offset in X so it survives K-1, front and side checks.
    # The bow changes depth along its arc, so the profile does not collapse to one line.
    bow = [(-0.20, -0.08, 0.16), (-0.26, -0.16, 0.24), (-0.28, -0.15, 0.35), (-0.23, -0.08, 0.45)]
    for i in range(len(bow) - 1):
        segment(f"Medusa_Bow_{i}", bow[i], bow[i + 1], 0.010, target, 0.19)
    segment("Medusa_BowString", bow[0], bow[-1], 0.004, target, 0.19)
    segment("Medusa_BowHand", (-0.135, -0.035, 0.25), (-0.225, -0.06, 0.28), 0.014, target, 0.40)


def harpy(target):
    base(target, 0.11, "Harpy")
    cone("Harpy_Body", (0, 0, 0.19), 0.10, 0.060, 0.21, target, 0.34)
    sphere("Harpy_Head", (0, -0.02, 0.320), 0.052, target, 0.41)
    for side in (-1, 1):
        segment(f"Harpy_Leg_{side}", (side * 0.038, 0, 0.12), (side * 0.060, -0.035, 0.055), 0.015, target)
        points = [(side * x, z) for x, z in [(0.055, 0.29), (0.15, 0.42), (0.36, 0.35), (0.30, 0.265), (0.25, 0.295), (0.20, 0.24), (0.13, 0.28)]]
        if side < 0:
            points.reverse()
        wing = prism(f"Harpy_Wing_{side}", points, 0.012, 0.025, target, 0.30)
        # Symmetric rear sweep exposes the wing plane in the side silhouette.
        wing.rotation_euler.z = math.radians(side * 24)
        for i, x in enumerate((0.18, 0.25, 0.32)):
            segment(f"Harpy_Feather_{side}_{i}", (side * x, 0.012 + x * 0.445, 0.315), (side * (x + 0.035), 0.012 + (x + 0.035) * 0.445, 0.235), 0.009, target, 0.27)
    cone("Harpy_Crest", (0, -0.006, 0.371), 0.037, 0.0, 0.095, target, 0.37)
    beak = cone("Harpy_Beak", (0, -0.078, 0.315), 0.020, 0.0, 0.065, target, 0.25, 6)
    beak.rotation_euler.x = math.radians(90)


def arthur(target):
    base(target, 0.15, "Arthur")
    for side in (-1, 1):
        segment(f"Arthur_Leg_{side}", (side * 0.055, 0, 0.06), (side * 0.062, 0, 0.225), 0.032, target, 0.29)
        segment(f"Arthur_Arm_{side}", (side * 0.110, 0, 0.383), (side * 0.145, -0.025, 0.260), 0.027, target, 0.31)
    cone("Arthur_Armor", (0, 0, 0.315), 0.105, 0.145, 0.23, target, 0.39)
    prism("Arthur_Cape", [(-0.10, 0.41), (0.10, 0.41), (0.19, 0.065), (-0.19, 0.065)], 0.11, 0.018, target, 0.24)
    sphere("Arthur_Head", (0, -0.02, 0.470), 0.063, target, 0.44)
    cylinder("Arthur_CrownBand", (0, -0.02, 0.520), 0.065, 0.018, target, 0.33)
    for x in (-0.045, 0, 0.045):
        cone(f"Arthur_CrownPoint_{x}", (x, -0.02, 0.530), 0.018, 0.0, 0.050, target, 0.30, 6)
    segment("Arthur_SwordBlade", (0.17, -0.065, 0.26), (0.17, -0.065, 0.56), 0.016, target, 0.22, 4)
    cube("Arthur_SwordGuard", (0.17, -0.065, 0.265), (0.10, 0.025, 0.02), target, 0.20)


def merlin(target):
    base(target, 0.12, "Merlin")
    cone("Merlin_Robe", (0, 0, 0.235), 0.125, 0.075, 0.37, target, 0.36)
    sphere("Merlin_Face", (0, -0.055, 0.390), 0.055, target, 0.48)
    cone("Merlin_Hood", (0, 0, 0.425), 0.078, 0.0, 0.11, target, 0.27)
    cone("Merlin_Beard", (0, -0.095, 0.335), 0.04, 0.0, 0.13, target, 0.50)
    segment("Merlin_Staff", (0.17, -0.055, 0.07), (0.17, -0.055, 0.56), 0.014, target, 0.22)
    sphere("Merlin_StaffHead", (0.17, -0.055, 0.58), 0.035, target, 0.46)
    segment("Merlin_Arm", (0.070, -0.02, 0.31), (0.17, -0.055, 0.29), 0.023, target, 0.35)


def look_at(camera: bpy.types.Object, point) -> None:
    direction = Vector(point) - camera.location
    camera.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def camera(name: str, position, target, fov_degrees: float):
    data = bpy.data.cameras.new(name)
    data.type = "PERSP"
    data.sensor_fit = "HORIZONTAL"
    data.angle = math.radians(fov_degrees)
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = position
    look_at(obj, target)
    return obj


def render(path: Path, camera_obj, width: int, height: int, background):
    scene = bpy.context.scene
    scene.camera = camera_obj
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.display.shading.background_color = background
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    if not path.is_file() or path.stat().st_size == 0:
        raise RuntimeError(f"Render missing: {path}")


def build_board_and_instances() -> dict:
    contract = json.loads(BOARD_CONTRACT.read_text(encoding="utf-8"))
    if (contract["width"], contract["height"], len(contract["cells"])) != (5, 6, 30):
        raise RuntimeError("ART-003 probe expects pinned S04 5x6/30 contract")
    board = collection("Game_5x6_Gray")
    body = cube("Board_Tray", (0, 0, -0.16), (5.20, 6.20, 0.30), board, 0.16)
    BOARD_PARTS.append(body)
    for cell in contract["cells"]:
        x = cell["x"] - 2
        y = cell["y"] - 2.5
        tile = cube(f"Cell_{cell['x']}_{cell['y']}", (x, y, 0.005), (0.97, 0.97, 0.06), board, 0.70)
        BOARD_PARTS.append(tile)

    mapping = {
        "f-0-hero": "medusa",
        "f-0-sk0": "harpy",
        "f-0-sk1": "harpy",
        "f-0-sk2": "harpy",
        "f-1-hero": "arthur",
        "f-1-sk0": "merlin",
    }
    starts = next(start for start in contract["starts"] if start["id"] == "medusa-first")
    fighters = starts["fighters"]
    if {f["id"] for f in fighters} != set(mapping):
        raise RuntimeError("Unexpected fighter set in S04 contract")
    game = collection("Game_Fighters_Gray")
    for fighter in fighters:
        kind = mapping[fighter["id"]]
        pos = fighter["position"]
        offset = Vector((pos["x"] - 2, pos["y"] - 2.5, 0.035))
        for original in PARTS[kind]:
            duplicate = original.copy()
            duplicate.data = original.data
            duplicate.name = fighter["id"] + "__" + original.name
            game.objects.link(duplicate)
            duplicate.location = original.location + offset
            GAME_PARTS.append(duplicate)
        if kind == "harpy":
            count = int(fighter["id"][-1]) + 1
            # Distinct 1/2/3 raised front tabs are instance markers, not three models.
            for i in range(count):
                x = offset.x + (i - (count - 1) / 2) * 0.047
                tab = cube(f"{fighter['id']}_Marker_{i + 1}", (x, offset.y - 0.145, 0.108), (0.033, 0.030, 0.11), game, 0.05)
                GAME_PARTS.append(tab)
    return contract


def add_probe_labels(contract: dict, game_camera: bpy.types.Object) -> None:
    """Review-only digit plates supplement the physical tally tabs at K-1."""
    target = bpy.data.collections["Game_Fighters_Gray"]
    starts = next(start for start in contract["starts"] if start["id"] == "medusa-first")
    for fighter in starts["fighters"]:
        if not fighter["id"].startswith("f-0-sk"):
            continue
        digit = str(int(fighter["id"][-1]) + 1)
        x = fighter["position"]["x"] - 2
        y = fighter["position"]["y"] - 2.5
        spot = Vector((x, y, 0.55))
        toward_camera = (game_camera.location - spot).normalized()
        plate = cube(f"{fighter['id']}_ProbePlate", spot, (0.20, 0.14, 0.01), target, 0.88)
        plate.rotation_euler = game_camera.rotation_euler
        LABEL_PARTS.append(plate)
        font = bpy.data.curves.new(f"{fighter['id']}_Digit", "FONT")
        font.body = digit
        font.size = 0.155
        font.align_x = "CENTER"
        font.align_y = "CENTER"
        label = bpy.data.objects.new(f"{fighter['id']}_Digit", font)
        target.objects.link(label)
        label.location = spot + toward_camera * 0.011
        label.rotation_euler = game_camera.rotation_euler
        label.color = (0.04, 0.04, 0.04, 1.0)
        LABEL_PARTS.append(label)
        GAME_PARTS.extend((plate, label))


def bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    return {
        "min_m": [round(min(v[i] for v in points), 4) for i in range(3)],
        "max_m": [round(max(v[i] for v in points), 4) for i in range(3)],
    }


def main() -> None:
    setup()
    for kind, builder in (("medusa", medusa), ("harpy", harpy), ("arthur", arthur), ("merlin", merlin)):
        target = collection("Studio_" + kind)
        builder(target)
        PARTS[kind] = list(target.objects)
    bpy.context.view_layer.update()
    probe_bounds = {kind: bounds(objects) for kind, objects in PARTS.items()}
    body_bounds = {
        kind: bounds([obj for obj in objects if not any(prop in obj.name for prop in ("Sword", "Staff", "Bow"))])
        for kind, objects in PARTS.items()
    }
    contract = build_board_and_instances()
    studio = {
        "front": camera("Camera_Studio_Front", (0, -1.8, 1.0), (0, 0, 0.27), 33),
        "side": camera("Camera_Studio_Side", (1.8, 0, 1.0), (0, 0, 0.27), 33),
        "back": camera("Camera_Studio_Back", (0, 1.8, 1.0), (0, 0, 0.27), 33),
    }
    k1 = camera("Camera_K1_Probe", (0, -10.324, 14.744), (0, 0, 0), 35)
    add_probe_labels(contract, k1)

    for obj in BOARD_PARTS + GAME_PARTS:
        obj.hide_render = True
    for kind, objects in PARTS.items():
        for group in PARTS.values():
            for obj in group:
                obj.hide_render = True
        for obj in objects:
            obj.hide_render = False
        for view_name, view_camera in studio.items():
            render(PREVIEW / f"{kind}-{view_name}-gray.png", view_camera, 768, 768, (0.77, 0.77, 0.77))

    for objects in PARTS.values():
        for obj in objects:
            obj.hide_render = True
    for obj in BOARD_PARTS + GAME_PARTS:
        obj.hide_render = False
    render(PREVIEW / "k1-six-figures-gray.png", k1, 1920, 1080, (0.10, 0.10, 0.10))

    # Second K1 capture removes all color/material cues, leaving silhouettes only.
    saved = {obj.name: obj.color[:] for obj in GAME_PARTS}
    for obj in GAME_PARTS:
        obj.color = (0.015, 0.015, 0.015, 1.0)
    for obj in LABEL_PARTS:
        obj.hide_render = True
    for obj in BOARD_PARTS:
        obj.hide_render = True
    render(PREVIEW / "k1-six-figures-silhouette.png", k1, 1920, 1080, (0.95, 0.95, 0.95))
    for obj in GAME_PARTS:
        obj.color = saved[obj.name]
    for obj in LABEL_PARTS:
        obj.hide_render = False
    for obj in BOARD_PARTS:
        obj.hide_render = False

    report = {
        "status": "blockout_probe_only",
        "source": str(BOARD_CONTRACT.relative_to(ROOT)).replace("\\", "/"),
        "board": {"width": contract["width"], "height": contract["height"], "cell_m": 1.0},
        "camera": {"projection": "perspective", "horizontal_fov_deg": 35, "pitch_deg_approx": -55, "distance_m": 18},
        "character_bounds": probe_bounds,
        "body_bounds_without_weapons": body_bounds,
        "fighter_instances": [f["id"] for f in next(s for s in contract["starts"] if s["id"] == "medusa-first")["fighters"]],
        "harpy_marker_counts": {"f-0-sk0": 1, "f-0-sk1": 2, "f-0-sk2": 3},
        "renders": [p.name for p in sorted(PREVIEW.glob("*.png"))],
        "approval": "none; dimensions and camera are provisional until GD-058",
    }
    (OUT / "build-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    bpy.context.scene.camera = k1
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "silhouette_blockouts.blend"))
    print("ART003_BLOCKOUTS_COMPLETE", len(report["renders"]), json.dumps(probe_bounds, sort_keys=True))


if __name__ == "__main__":
    main()
