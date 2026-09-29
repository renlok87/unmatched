"""Common helpers of the build stage: constants, FBX preset and byte determinism, scene context, checks,
UM_FBX_v1 export and the round trip import. Moved unchanged from blender/build_candidate.py (tool 0.4.0) and
the per-hero builders of 2026-09-28 (their copies were identical)."""

import datetime
import hashlib
import json
import math
import re
import struct
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

MARKER = "TRIPO_PIPELINE_STAGE_OK build"
FIXED_TIME = datetime.datetime(2000, 1, 1, 0, 0, 0)
WORK_SCENE = "tripo_pipeline_candidate"
ROUNDTRIP_SCENE = "tripo_pipeline_candidate_roundtrip"
REFERENCE_SCENE = "tripo_pipeline_candidate_reference"
SCENES = (WORK_SCENE, ROUNDTRIP_SCENE, ROUNDTRIP_SCENE + "_base", REFERENCE_SCENE, REFERENCE_SCENE + "_base")
ID_COLLECTIONS = ("objects", "meshes", "materials", "images", "textures", "node_groups", "collections",
                  "cameras", "lights", "armatures", "actions", "worlds", "scenes", "libraries")
CN_ATTR = "um_corner_normal"
PART_ATTR = "um_part"
REF_FLIP_ATTR = "um_ref_flip"
DEGENERATE_AREA_CM2 = 1e-4  # UE's mesh build drops such slivers (measured: 2 base triangles at 1e-7..1e-6 cm2)
PRESET_KEYS = ("name", "axis_forward", "axis_up", "export_space_rotation_z_degrees", "temporary_data_scale",
               "patch_fbx_unit_scale_to", "apply_unit_scale", "apply_scale_options", "use_triangles",
               "mesh_smooth_type", "add_leaf_bones", "primary_bone_axis", "secondary_bone_axis", "path_mode")
# Deliberate, reported deviation from the preset: FBX keeps bare texture file names. The preset's "AUTO"
# would write a path relative to the staging directory (wrong after promotion, host specific); the
# candidate's textures are imported into UE separately from the atlas stage, never through the FBX.
PATH_MODE = "STRIP"
# Blender 5.2 default of export_scene.fbx(colors_type); passed explicitly (vertex-colour masks of bases).
COLORS_TYPE = "SRGB"


def r(value, nd=6):
    return round(float(value), nd)


def rv(vec, nd=6):
    return [r(c, nd) for c in vec]


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_preset(path):
    preset = json.loads(Path(path).read_text(encoding="utf-8"))
    missing = [k for k in PRESET_KEYS if k not in preset]
    if missing:
        raise RuntimeError("FBX preset %s lacks %s" % (path, missing))
    return preset


def export_rotation(preset):
    """Rotation about Z; multiples of 90 deg are snapped to an exact axis permutation (cos 90 = 6e-17
    otherwise perturbs float32 coordinates and flips the normals of sliver triangles)."""
    rot = Matrix.Rotation(math.radians(float(preset["export_space_rotation_z_degrees"])), 4, "Z")
    for i in range(4):
        for j in range(4):
            value = rot[i][j]
            if abs(value - round(value)) < 1e-9:
                rot[i][j] = float(round(value))
    return rot


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
    """Operators run in `scene`: switch the window's scene (restored afterwards)."""
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
    """Same pinning as export_fbx.py: header time, UUID hash, texture paths. Returns restore()."""
    from io_scene_fbx import export_fbx_bin, fbx_utils

    saved = {"vid": export_fbx_bin._gen_vid_path, "datetime": export_fbx_bin.datetime,
             "hash": fbx_utils.__dict__.get("hash", _MISSING)}
    original_vid_path = saved["vid"]

    def relative_vid_path(img, scene_data):
        _abs, rel = original_vid_path(img, scene_data)
        return rel, rel

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


def patch_fbx_units(path, value=1.0):
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


class Namer:
    """Canonical (headless) names when the live session already owns a name (.NNN suffix)."""

    def __init__(self, before_ids):
        self.existing = {kind: {i.name for i in ids} for kind, ids in before_ids.items()}
        self.collisions = defaultdict(set)

    def __call__(self, idb, kind):
        match = re.match(r"^(.*)\.(\d{3})$", idb.name)
        if match and match.group(1) in self.existing[kind]:
            self.collisions[kind].add(idb.name)
            return match.group(1)
        return idb.name

    def note_new(self, kind, before_ids):
        for idb in getattr(bpy.data, kind):
            if idb not in before_ids[kind]:
                self(idb, kind)

    def report(self):
        return {kind: sorted(names) for kind, names in sorted(self.collisions.items()) if names}


class Checks(dict):
    """name -> {"passed", "measured"[, "expected"][, "note"]} (the report format of every build check)."""

    def __call__(self, name, passed, measured=None, expected=None, note=None):
        item = {"passed": bool(passed), "measured": measured}
        if expected is not None:
            item["expected"] = expected
        if note:
            item["note"] = note
        self[name] = item

    def failed(self):
        return sorted(k for k, c in self.items() if not c["passed"])


def flip_polygons(mesh, selected):
    """Flip winding of `selected` polygons and negate their custom corner normals (RESTORE_NORMALS)."""
    source_vertices = {p.index: frozenset(p.vertices) for p in mesh.polygons}
    source_normals = {(p.index, mesh.loops[li].vertex_index): mesh.corner_normals[li].vector.copy()
                      for p in mesh.polygons for li in p.loop_indices}
    editable = bmesh.new()
    editable.from_mesh(mesh)
    editable.faces.index_update()
    for face in editable.faces:
        if face.index in selected:
            face.normal_flip()
    editable.to_mesh(mesh)
    editable.free()
    if not all(frozenset(p.vertices) == source_vertices[p.index] for p in mesh.polygons):
        raise RuntimeError("BMesh reordered polygons")
    normals = [None] * len(mesh.loops)
    for p in mesh.polygons:
        for li in p.loop_indices:
            n = source_normals[(p.index, mesh.loops[li].vertex_index)].copy()
            if p.index in selected:
                n.negate()
            normals[li] = n
    mesh.normals_split_custom_set(normals)
    mesh.update()


def transform_for_fbx(scene, arm, meshes, matrix):
    """UM_FBX_v1 export space on the in-memory figure: rotation about Z and metres -> centimetre numbers.

    Bones use EditBone.transform(roll=True), i.e. the whole rest pose turns rigidly with the mesh
    (batch_export.py of ART-001 moves only head/tail; for vertical bones that leaves the local X/Z
    axes unrotated). Object transforms are identity here; locations are rotated for completeness.
    """
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for bone in arm.data.edit_bones:
            bone.transform(matrix, scale=False, roll=True)
        bpy.ops.object.mode_set(mode="OBJECT")
    for obj in (arm,) + tuple(meshes):
        obj.location = matrix @ obj.location
    for mesh in meshes:
        mesh.data.transform(matrix)


def export_fbx(scene, path, objects, active, object_types, preset):
    with scene_context(scene):
        bpy.ops.object.select_all(action="DESELECT")
        for obj in objects:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = active
        bpy.ops.export_scene.fbx(
            filepath=str(path), use_selection=True, object_types=object_types,
            apply_unit_scale=bool(preset["apply_unit_scale"]), apply_scale_options=preset["apply_scale_options"],
            axis_forward=preset["axis_forward"], axis_up=preset["axis_up"],
            use_triangles=bool(preset["use_triangles"]), mesh_smooth_type=preset["mesh_smooth_type"],
            add_leaf_bones=bool(preset["add_leaf_bones"]), primary_bone_axis=preset["primary_bone_axis"],
            secondary_bone_axis=preset["secondary_bone_axis"], bake_anim=False, use_custom_props=False,
            path_mode=PATH_MODE, embed_textures=False, colors_type=COLORS_TYPE,
        )
    patch_fbx_units(path, float(preset["patch_fbx_unit_scale_to"]))


def export_pair(scene, arm, skeletal_meshes, base, preset, sk_fbx, base_fbx):
    """Skeletal FBX (armature + meshes) and base FBX, each with the determinism pins restored afterwards."""
    sk_fbx.parent.mkdir(parents=True, exist_ok=True)
    restore = make_fbx_deterministic()
    try:
        export_fbx(scene, sk_fbx, (arm,) + tuple(skeletal_meshes), arm, {"ARMATURE", "MESH"}, preset)
    finally:
        restore()
    restore = make_fbx_deterministic()
    try:
        export_fbx(scene, base_fbx, (base,), base, {"MESH"}, preset)
    finally:
        restore()


def to_authored_frame(scene, inverse):
    """Undo the export rotation on a re-imported scene so it can be compared with the authored data."""
    for obj in scene.objects:
        if obj.parent is None:
            obj.matrix_world = inverse @ obj.matrix_world
    scene.view_layers[0].update()


def to_final_point(p, frame, xform):
    """A point of the profile in the final (candidate metres) frame. frame "source": Tripo GLB metres, mapped
    by the seat transform xform = (s, cx, cy, base_height, source_base_top); frame "final": unchanged."""
    if frame == "final":
        return Vector(p)
    s, cx, cy, fz, base_top_src = xform
    return Vector(((p[0] - cx) * s, (p[1] - cy) * s, fz + (p[2] - base_top_src) * s))


def import_glb(scene, source):
    with scene_context(scene):
        bpy.ops.import_scene.gltf(filepath=str(source))


def import_fbx_into(scene, path):
    with scene_context(scene):
        bpy.ops.import_scene.fbx(filepath=str(path))


def export_settings_report(preset, preset_rel, preset_path, data_scale):
    """The "exports.settings" block of the build report (identical for both flows)."""
    return {"preset": {"name": preset["name"], "version": preset.get("version"),
                       "path": preset_rel, "sha256": sha256(preset_path)},
            "apply_unit_scale": bool(preset["apply_unit_scale"]),
            "apply_scale_options": preset["apply_scale_options"],
            "axis_forward": preset["axis_forward"], "axis_up": preset["axis_up"],
            "export_space_rotation_z_degrees": float(preset["export_space_rotation_z_degrees"]),
            "bone_rotation": "EditBone.transform(roll=True): rest pose rotated rigidly",
            "data_scale": data_scale,
            "unit_scale_factor_after_patch": float(preset["patch_fbx_unit_scale_to"]),
            "use_triangles": bool(preset["use_triangles"]),
            "add_leaf_bones": bool(preset["add_leaf_bones"]),
            "primary_bone_axis": preset["primary_bone_axis"],
            "secondary_bone_axis": preset["secondary_bone_axis"],
            "mesh_smooth_type": preset["mesh_smooth_type"], "bake_anim": False,
            "path_mode": PATH_MODE, "embed_textures": False, "colors_type": COLORS_TYPE,
            "deviations_from_preset": {
                "path_mode": "%s instead of %s: bare texture names; textures reach UE from the "
                             "atlas stage, not through the FBX" % (PATH_MODE, preset["path_mode"]),
                "bake_anim": "off: the candidate FBX carries no clips"},
            "creation_time_pinned": FIXED_TIME.isoformat()}


class BuildContext:
    """Everything a flow needs from the entry script (params, profile, atlas, preset, isolation)."""

    def __init__(self, params, profile, isolation, lib_dir):
        self.params = params
        self.profile = profile
        self.isolation = isolation
        self.lib_dir = Path(lib_dir)
        self.atlas = json.loads(Path(params["atlas_report"]).read_text(encoding="utf-8"))
        self.source = Path(params["source"])
        self.repo = Path(params["repo_root"])
        self.source_hash = sha256(self.source)
        if not params.get("fbx_preset"):
            raise RuntimeError("params.fbx_preset is required (UM_FBX_v1, 04-blender-production.md §1.1)")
        self.preset_path = Path(params["fbx_preset"])
        self.preset = load_preset(self.preset_path)
        try:
            self.preset_rel = self.preset_path.resolve().relative_to(self.repo.resolve()).as_posix()
        except ValueError:
            self.preset_rel = self.preset_path.name
        self.rot = export_rotation(self.preset)
        self.rot3 = self.rot.to_3x3()
        self.data_scale = float(self.preset["temporary_data_scale"])
        self.checks = Checks()
        self.namer = None
        self.before_ids = None
        self.removed = 0

    def begin(self):
        if self.isolation == "process":
            bpy.ops.wm.read_factory_settings(use_empty=True)
        elif self.isolation != "live":
            raise RuntimeError("unknown isolation mode %r" % self.isolation)
        for name in SCENES:
            if name in bpy.data.scenes:
                raise RuntimeError("scene %r already exists (leftover of an interrupted pipeline stage?); "
                                   "remove it by hand before re-running" % name)
        self.before_ids = id_snapshot()
        self.namer = Namer(self.before_ids)

    def new_scene(self, name):
        scene = bpy.data.scenes.new(name)
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
        return scene

    def end(self):
        """Live isolation: remove every datablock this run created (the user's session stays as it was).
        Idempotent; returns the number of datablocks removed so far."""
        if self.isolation == "live" and self.before_ids is not None:
            self.removed += remove_new_ids(self.before_ids)
            self.before_ids = None
        return self.removed

    def note_export_names(self):
        for kind in ("objects", "materials", "meshes", "armatures"):
            self.namer.note_new(kind, self.before_ids)

    def write_report(self, report):
        collisions = self.namer.report() if self.namer else {}
        if collisions:
            report["live_name_collisions"] = collisions
        out = Path(self.params["report_out"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        if sha256(self.source) != self.source_hash:
            raise RuntimeError("source GLB changed during build")
