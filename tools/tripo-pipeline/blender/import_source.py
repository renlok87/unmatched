"""Stage `import`: read a registered Tripo GLB into an isolated Blender scene.

Run only through tripo_pipeline.py, in one of two isolation modes:

* process (``--backend headless``):
    blender -b --factory-startup --python-exit-code 1 --python import_source.py -- <params.json>
  A fresh Blender process; the scene is reset to factory-empty first.
* live (``--backend mcp``): the pipeline prepends
    TRIPO_PIPELINE_PARAMS = r"<params.json>"; TRIPO_PIPELINE_ISOLATION = "live"
  to this file and sends it to the running Blender GUI via blender_mcp.py
  (addon ``execute_code``). The user's open file is never reset, saved or
  modified: the GLB is imported into a temporary scene, written to the run's
  .blend with ``bpy.data.libraries.write`` and every datablock created here is
  removed again (the active scene is not even switched).

params.json: {"source": abs path, "blend_out": abs path, "report_out": abs path}
The source GLB is opened read-only. The report is deterministic (no timestamps,
rounded floats, canonical object names) so the pipeline can dedupe identical
re-runs by hash.
"""

import hashlib
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

MARKER = "TRIPO_PIPELINE_STAGE_OK import"
WORK_SCENE = "tripo_pipeline_import"
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
    """Delete every datablock that did not exist in `before` (live-session hygiene)."""
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


class Namer:
    """Undo the .NNN suffix Blender adds when the live session already owns a name.

    Report names stay identical to a clean headless run; every suffixed name is
    remembered per datablock kind and listed in the report (the .blend and FBX
    keep the suffixed names). A source name that itself ends in .NNN while the
    session owns the base name would be misreported; this is documented.
    """

    def __init__(self, before_ids):
        self.existing = {kind: {i.name for i in ids} for kind, ids in before_ids.items()}
        self.collisions = {}

    def __call__(self, idb, kind):
        match = re.match(r"^(.*)\.(\d{3})$", idb.name)
        if match and match.group(1) in self.existing[kind]:
            self.collisions.setdefault(kind, set()).add(idb.name)
            return match.group(1)
        return idb.name

    def report(self):
        return {kind: sorted(names) for kind, names in sorted(self.collisions.items())}


def mesh_entry(obj, name, namer):
    mesh = obj.data
    mesh.calc_loop_triangles()
    bm = bmesh.new()
    bm.from_mesh(mesh)
    entry = {
        "name": name,
        "vertices": len(mesh.vertices),
        "polygons": len(mesh.polygons),
        "triangles": len(mesh.loop_triangles),
        "uv_layers": [uv.name for uv in mesh.uv_layers],
        "material_slots": [namer(s.material, "materials") if s.material else None for s in obj.material_slots],
        "boundary_edges_raw": sum(e.is_boundary for e in bm.edges),
        "non_manifold_edges_raw": sum(not e.is_manifold for e in bm.edges),
        "degenerate_faces": sum(f.calc_area() < 1e-12 for f in bm.faces),
    }
    # glTF splits vertices on UV/normal seams; a diagnostic weld separates seams from holes.
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
    entry["diagnostic_weld_1e-7"] = {
        "vertices": len(bm.verts),
        "boundary_edges": sum(e.is_boundary for e in bm.edges),
        "non_manifold_edges": sum(not e.is_manifold for e in bm.edges),
    }
    bm.free()
    return entry


def scene_images(meshes):
    images = {}
    for obj in meshes:
        for slot in obj.material_slots:
            mat = slot.material
            if mat and mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == "TEX_IMAGE" and node.image:
                        images[node.image.name] = node.image
    return [images[k] for k in sorted(images)]


def main():
    isolation = globals().get("TRIPO_PIPELINE_ISOLATION", "process")
    params = load_params()
    source = Path(params["source"])
    before_hash = sha256(source)
    if isolation == "process":
        bpy.ops.wm.read_factory_settings(use_empty=True)
    elif isolation != "live":
        raise RuntimeError("unknown isolation mode %r" % isolation)
    if WORK_SCENE in bpy.data.scenes:
        raise RuntimeError("scene %r already exists (leftover of an interrupted pipeline stage?); "
                           "remove it by hand before re-running" % WORK_SCENE)
    before_ids = id_snapshot()
    namer = Namer(before_ids)
    removed = 0
    try:
        scene = bpy.data.scenes.new(WORK_SCENE)
        with scene_context(scene):
            bpy.ops.import_scene.gltf(filepath=str(source))
        meshes = sorted((o for o in scene.objects if o.type == "MESH"), key=lambda o: namer(o, "objects"))
        for obj in meshes:
            namer(obj.data, "meshes")  # mesh data names end up in the FBX
        points = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
        lo = [min(p[i] for p in points) for i in range(3)]
        hi = [max(p[i] for p in points) for i in range(3)]
        images = sorted(scene_images(meshes), key=lambda im: namer(im, "images"))
        materials = {s.material.name for o in meshes for s in o.material_slots if s.material}
        entries = [mesh_entry(o, namer(o, "objects"), namer) for o in meshes]
        report = {
            "stage": "import",
            "blender": bpy.app.version_string,
            "source": {"file": source.name, "sha256": before_hash},
            "units": "source units (glTF metres); no scale applied",
            "mesh_count": len(meshes),
            "triangles_total": sum(e["triangles"] for e in entries),
            "material_count": len(materials),
            "image_count": len(images),
            "armatures": len([o for o in scene.objects if o.type == "ARMATURE"]),
            "actions": len([a for a in bpy.data.actions if a not in before_ids["actions"]]),
            "bounds": {"min": [r(v) for v in lo], "max": [r(v) for v in hi],
                       "dimensions": [r(h - l) for l, h in zip(lo, hi)]},
            "meshes": entries,
            "images": [{"name": namer(im, "images"), "size": list(im.size), "colorspace": im.colorspace_settings.name,
                        "packed": im.packed_file is not None} for im in images],
        }
        if namer.collisions:
            # Only possible in live mode; names in the .blend keep the suffix, the report does not.
            report["live_name_collisions"] = namer.report()
        blend_out = Path(params["blend_out"])
        blend_out.parent.mkdir(parents=True, exist_ok=True)
        # Writes the work scene and everything it references; the open file is untouched.
        bpy.data.libraries.write(str(blend_out), {scene}, compress=False)
    finally:
        if isolation == "live":
            removed = remove_new_ids(before_ids)
    if sha256(source) != before_hash:
        raise RuntimeError("source GLB changed during import")
    report_out = Path(params["report_out"])
    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(MARKER, report["mesh_count"], report["triangles_total"], "isolation=%s" % isolation,
          "temp_ids_removed=%d" % removed)


main()
