"""Stage `export`: write a byte-deterministic FBX from the import .blend and re-import it.

Run only through tripo_pipeline.py, in one of two isolation modes (see
import_source.py): ``process`` (headless ``blender -b``, factory-empty scene)
or ``live`` (running Blender GUI via blender_mcp.py ``execute_code``; the
user's file is never reset or saved, the work scene is appended from the run's
.blend into temporary scenes that are removed afterwards, and the FBX exporter
patches below are reverted in ``finally``).

params.json: {"blend": abs, "fbx_out": abs, "report_out": abs, "fbx_preset": abs JSON}

FBX settings follow the verified preset UM_FBX_v1 (blender/_tools/presets/UM_FBX_v1.json,
ART-001 PASS, 04-blender-production.md §1/§1.1): the in-memory copy is rotated +90 deg
about Z (Tripo/glTF front -Y -> +X, which UE keeps as +X) and scaled to centimetre
numbers, FBX_SCALE_UNITS, -Y forward, Z up, Triangulate on, UnitScaleFactor patched
to 1.0 (UE imports at import_uniform_scale 1.0). Deliberate deviation: textures are
embedded (path_mode COPY) because this passthrough transports Tripo's own materials.
The round trip is measured in the export frame (as written) and, after undoing the
rotation, in the authored frame.
This is a technical passthrough of the Tripo geometry: no retopology, atlas,
rig or scale normalisation happens here, so the result is not a game asset.
"""

import datetime
import hashlib
import json
import math
import re
import struct
import sys
from contextlib import contextmanager
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

MARKER = "TRIPO_PIPELINE_STAGE_OK export"
FIXED_TIME = datetime.datetime(2000, 1, 1, 0, 0, 0)
WORK_SCENE = "tripo_pipeline_import"
ROUNDTRIP_SCENE = "tripo_pipeline_roundtrip"
ID_COLLECTIONS = ("objects", "meshes", "materials", "images", "textures", "node_groups", "collections",
                  "cameras", "lights", "armatures", "actions", "worlds", "scenes", "libraries")


def r(value):
    return round(float(value), 6)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_params():
    injected = globals().get("TRIPO_PIPELINE_PARAMS")
    path = injected if injected else sys.argv[sys.argv.index("--") + 1]
    return json.loads(Path(path).read_text(encoding="utf-8"))


def id_snapshot():
    return {name: set(getattr(bpy.data, name)) for name in ID_COLLECTIONS}


def remove_new_ids(before):
    doomed = []
    for name in ID_COLLECTIONS:
        doomed.extend(i for i in getattr(bpy.data, name) if i not in before[name])
    if doomed:
        bpy.data.batch_remove(doomed)
    return len(doomed)


@contextmanager
def scene_context(scene):
    """Make `scene` the context scene *and* view layer for operators.

    temp_override(view_layer=...) alone is not enough: while a window exists
    (GUI, and even `blender -b`), selection and view-layer lookups follow the
    window. The window's scene is switched for the duration and always restored;
    the live UI does not redraw in between (execute_code blocks the main thread).
    """
    wm = bpy.context.window_manager
    window = bpy.context.window or (wm.windows[0] if wm.windows else None)
    view_layer = scene.view_layers[0]
    if window is None:
        with bpy.context.temp_override(scene=scene, view_layer=view_layer):
            yield
        return
    previous_scene, previous_layer = window.scene, window.view_layer
    try:
        window.scene = scene
        with bpy.context.temp_override(window=window, scene=scene, view_layer=view_layer):
            yield
    finally:
        window.scene = previous_scene
        window.view_layer = previous_layer


def stable_hash(key):
    digest = hashlib.sha256(repr(key).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "little") & ((1 << 63) - 1)


_MISSING = object()


def make_fbx_deterministic():
    """Pin the nondeterministic inputs of Blender's FBX writer so equal scenes hash equal.

    1. export_fbx_bin writes datetime.now() into the FBX header.
    2. fbx_utils derives object UUIDs from Python's salted str hash (PYTHONHASHSEED).
    3. embedded texture records store the absolute export path (staging dir, checkout path).
    All are replaced by module-level shadows; the exporter code itself is untouched.
    Returns a callable that restores the modules (required in a live session).
    """
    from io_scene_fbx import export_fbx_bin, fbx_utils

    saved = {
        "vid": export_fbx_bin._gen_vid_path,
        "datetime": export_fbx_bin.datetime,
        "hash": fbx_utils.__dict__.get("hash", _MISSING),
    }
    original_vid_path = saved["vid"]

    def relative_vid_path(img, scene_data):
        _abs, rel = original_vid_path(img, scene_data)
        return rel, rel  # texture bytes are embedded; keep only the portable relative name

    export_fbx_bin._gen_vid_path = relative_vid_path
    fbx_utils.hash = stable_hash
    fbx_utils._keys_to_uuids.clear()
    fbx_utils._uuids_to_keys.clear()

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return FIXED_TIME

    class FixedModule:
        datetime = FixedDateTime

    export_fbx_bin.datetime = FixedModule

    def restore():
        export_fbx_bin._gen_vid_path = saved["vid"]
        export_fbx_bin.datetime = saved["datetime"]
        if saved["hash"] is _MISSING:
            fbx_utils.__dict__.pop("hash", None)
        else:
            fbx_utils.hash = saved["hash"]
        fbx_utils._keys_to_uuids.clear()
        fbx_utils._uuids_to_keys.clear()

    return restore


PRESET_KEYS = ("name", "axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
               "patch_fbx_unit_scale_to", "apply_unit_scale", "apply_scale_options", "use_triangles",
               "mesh_smooth_type", "add_leaf_bones", "path_mode")


def load_preset(path):
    preset = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in PRESET_KEYS if k not in preset]
    if missing:
        raise RuntimeError("FBX preset %s lacks %s" % (path, missing))
    return preset


def patch_fbx_units(path, value=1.0):
    """Same binary patch as batch_export.py (UM_FBX_v1): UnitScaleFactor := 1.0 (cm)."""
    buffer = bytearray(path.read_bytes())
    start = buffer.find(b"UnitScaleFactor")
    if start < 0:
        raise RuntimeError("UnitScaleFactor not found in FBX")
    token = buffer.find(b"Number", buffer.find(b"double", start))
    length = struct.unpack_from("<I", buffer, token - 4)[0]
    offset = token + length
    if buffer[offset:offset + 1] != b"S":
        raise RuntimeError("unexpected FBX property layout")
    string_length = struct.unpack_from("<I", buffer, offset + 1)[0]
    offset += 1 + 4 + string_length
    if buffer[offset:offset + 1] != b"D":
        raise RuntimeError("unexpected FBX property layout")
    struct.pack_into("<d", buffer, offset + 1, value)
    path.write_bytes(buffer)


def scene_summary(scene):
    meshes = sorted((o for o in scene.objects if o.type == "MESH"), key=lambda o: o.name)
    tris = 0
    for obj in meshes:
        obj.data.calc_loop_triangles()
        tris += len(obj.data.loop_triangles)
    points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    lo = [min(p[i] for p in points) for i in range(3)]
    hi = [max(p[i] for p in points) for i in range(3)]
    materials = sorted({s.material.name for o in meshes for s in o.material_slots if s.material})
    images = set()
    for obj in meshes:
        for slot in obj.material_slots:
            if slot.material and slot.material.node_tree:
                images.update(n.image.name for n in slot.material.node_tree.nodes
                              if n.type == "TEX_IMAGE" and n.image)
    return {
        "mesh_count": len(meshes),
        "triangles_total": tris,
        "material_count": len(materials),
        "armatures": len([o for o in scene.objects if o.type == "ARMATURE"]),
        "images": sorted(images),
        "uv_layers_min": min((len(o.data.uv_layers) for o in meshes), default=0),
        "bounds_dimensions": [r(h - l) for l, h in zip(lo, hi)],
        "bounds_min": [r(v) for v in lo],
    }


def append_work_scene(blend):
    with bpy.data.libraries.load(str(blend), link=False) as (src, dst):
        if WORK_SCENE not in src.scenes:
            raise RuntimeError("%s has no scene %r (import stage output expected)" % (blend, WORK_SCENE))
        dst.scenes = [WORK_SCENE]
    return dst.scenes[0]


def main():
    isolation = globals().get("TRIPO_PIPELINE_ISOLATION", "process")
    params = load_params()
    blend = Path(params["blend"])
    fbx = Path(params["fbx_out"])
    if not params.get("fbx_preset"):
        raise RuntimeError("params.fbx_preset is required (UM_FBX_v1, 04-blender-production.md §1.1)")
    preset_path = Path(params["fbx_preset"])
    preset = load_preset(preset_path)
    rot = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    for i in range(4):  # exact axis permutation for multiples of 90 deg (cos 90 = 6e-17 otherwise)
        for j in range(4):
            if abs(rot[i][j] - round(rot[i][j])) < 1e-9:
                rot[i][j] = float(round(rot[i][j]))
    data_scale = float(preset["temporary_data_scale"])
    fbx.parent.mkdir(parents=True, exist_ok=True)
    if isolation == "process":
        bpy.ops.wm.read_factory_settings(use_empty=True)
    elif isolation != "live":
        raise RuntimeError("unknown isolation mode %r" % isolation)
    for name in (WORK_SCENE, ROUNDTRIP_SCENE):
        if name in bpy.data.scenes:
            raise RuntimeError("scene %r already exists (leftover of an interrupted pipeline stage?); "
                               "remove it by hand before re-running" % name)
    before_ids = id_snapshot()
    existing = {kind: {i.name for i in ids} for kind, ids in before_ids.items()}
    restore = None
    removed = 0
    try:
        scene = append_work_scene(blend)
        if scene.name != WORK_SCENE:
            raise RuntimeError("work scene appended as %r; FBX would not be deterministic" % scene.name)
        view_layer = scene.view_layers[0]
        before = scene_summary(scene)
        meshes = [o for o in scene.objects if o.type == "MESH"]
        if len({o.data.name for o in meshes}) != len(meshes):
            raise RuntimeError("shared mesh data is not supported by the passthrough export")
        # UM_FBX_v1: rotate about Z, then metre values x100 so the FBX stores centimetres with
        # UnitScaleFactor 1.0 and UE imports at import_uniform_scale 1.0.
        # Only the appended in-memory copy is transformed; the import .blend is not written back.
        worlds = {obj.name: obj.matrix_world.copy() for obj in meshes}
        for obj in scene.objects:
            obj.select_set(False, view_layer=view_layer)
        for obj in meshes:
            obj.parent = None
            obj.data.transform(Matrix.Scale(data_scale, 4) @ rot @ worlds[obj.name])
            obj.matrix_world = Matrix.Identity(4)
            obj.select_set(True, view_layer=view_layer)
        collisions = {}
        for kind in ("objects", "meshes", "materials", "images"):
            names = sorted(i.name for i in getattr(bpy.data, kind) if i not in before_ids[kind]
                           and re.match(r"^(.*)\.\d{3}$", i.name)
                           and re.match(r"^(.*)\.\d{3}$", i.name).group(1) in existing[kind])
            if names:
                collisions[kind] = names
        restore = make_fbx_deterministic()
        with scene_context(scene):
            bpy.ops.export_scene.fbx(
                filepath=str(fbx), use_selection=True, object_types={"MESH"},
                apply_unit_scale=bool(preset["apply_unit_scale"]), apply_scale_options=preset["apply_scale_options"],
                axis_forward=preset["axis_forward"], axis_up=preset["axis_up"], bake_anim=False,
                add_leaf_bones=bool(preset["add_leaf_bones"]), use_triangles=bool(preset["use_triangles"]),
                mesh_smooth_type=preset["mesh_smooth_type"], path_mode="COPY", embed_textures=True,
            )
        restore()
        restore = None
        patch_fbx_units(fbx, float(preset["patch_fbx_unit_scale_to"]))

        # Round trip in an empty scene: Blender re-reads FBX centimetres as metres (x100).
        roundtrip = bpy.data.scenes.new(ROUNDTRIP_SCENE)
        with scene_context(roundtrip):
            bpy.ops.import_scene.fbx(filepath=str(fbx))
        export_frame = scene_summary(roundtrip)
        inverse = rot.inverted()
        for obj in roundtrip.objects:
            if obj.parent is None:
                obj.matrix_world = inverse @ obj.matrix_world
        roundtrip.view_layers[0].update()
        after = scene_summary(roundtrip)
    finally:
        if restore is not None:
            restore()
        if isolation == "live":
            removed = remove_new_ids(before_ids)
    ratio = [r(a / b) if b else None for a, b in zip(after["bounds_dimensions"], before["bounds_dimensions"])]
    checks = {
        "mesh_count_preserved": after["mesh_count"] == before["mesh_count"],
        "triangles_preserved": after["triangles_total"] == before["triangles_total"],
        "uv_present_on_all_meshes": after["uv_layers_min"] >= 1,
        "no_armature_expected": after["armatures"] == 0,
        # Blender re-reads the centimetre FBX (UnitScaleFactor 1.0) back into metres.
        "blender_roundtrip_ratio_is_1": all(v is not None and abs(v - 1.0) < 1e-3 for v in ratio),
        # The FBX holds the rotated figure: export-frame size = authored size turned by the preset rotation.
        "export_frame_rotated_as_preset": all(
            abs(a - b) <= 1e-3 * max(1.0, abs(b)) for a, b in zip(
                export_frame["bounds_dimensions"],
                [sum(abs(rot.to_3x3()[i][j]) * before["bounds_dimensions"][j] for j in range(3)) for i in range(3)])),
    }
    report = {
        "stage": "export",
        "blender": bpy.app.version_string,
        "fbx": {"file": fbx.name, "bytes": fbx.stat().st_size, "sha256": sha256(fbx),
                "settings": {"preset": {"name": preset["name"], "version": preset.get("version"),
                                        "file": preset_path.name, "sha256": sha256(preset_path)},
                             "apply_unit_scale": bool(preset["apply_unit_scale"]),
                             "apply_scale_options": preset["apply_scale_options"],
                             "axis_forward": preset["axis_forward"], "axis_up": preset["axis_up"],
                             "export_space_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
                             "data_scale": data_scale,
                             "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
                             "use_triangles": bool(preset["use_triangles"]),
                             "mesh_smooth_type": preset["mesh_smooth_type"],
                             "add_leaf_bones": bool(preset["add_leaf_bones"]),
                             "path_mode": "COPY", "embed_textures": True,
                             "deviations_from_preset": {
                                 "path_mode": "COPY + embed instead of %s: the passthrough carries Tripo's own "
                                              "textures inside the FBX" % preset["path_mode"]},
                             "creation_time_pinned": FIXED_TIME.isoformat(),
                             "texture_paths": "relative names only; bytes embedded"}},
        "scene_before_export": before,
        "roundtrip_export_frame": {k: export_frame[k] for k in ("bounds_dimensions", "bounds_min")},
        "roundtrip_reimport": after,
        "roundtrip_dimension_ratio": ratio,
        "expected_ue_dimensions_uu_at_import_scale_1": [r(v * 100.0) for v in export_frame["bounds_dimensions"]],
        "expected_ue_dimensions_note": "per UE axis X, Y, Z: export-frame size (UM_FBX_v1 rotation applied); "
                                       "UE flips only the sign of Y (ART-001)",
        "checks": checks,
        "passed": all(checks.values()),
        "texture_transport": {
            "images_before_export": len(before["images"]),
            "images_after_roundtrip": len(after["images"]),
            "note": ("Blender FBX writer embeds only textures wired to supported Principled inputs; "
                     "glTF metallic/roughness via Separate Color is not transported. Informational: "
                     "BC/N/ORM packing is a later candidate stage, not part of this passthrough."),
        },
        "note": "technical passthrough; not a game asset and not art-accepted",
    }
    if collisions:
        report["live_name_collisions"] = collisions
        report["note"] += "; object names collided with the live session, FBX bytes differ from headless"
    out = Path(params["report_out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not report["passed"]:
        raise RuntimeError("export round-trip checks failed: %s" % checks)
    print(MARKER, after["mesh_count"], after["triangles_total"], "isolation=%s" % isolation,
          "temp_ids_removed=%d" % removed)


main()
