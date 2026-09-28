"""Real-Blender harness for the live (MCP) isolation mode of the stage scripts.

Runs inside `blender -b --factory-startup --python blender_live_harness.py -- <job.json>`.
It reproduces what the blender-mcp addon does for `execute_code`
(exec(code, {"bpy": bpy}) under redirect_stdout, in a session that already
holds the user's data) and records whether the stage scripts left that session
exactly as they found it.

job.json:
  {"mode": "make-glb", "glb": path}                       -> writes a small test GLB
  {"mode": "live", "result": path, "collide": bool,
   "stages": [{"stage": "import"|"export", "script": path, "params": path}, ...]}
"""

import io
import json
import sys
import traceback
from contextlib import redirect_stdout
from pathlib import Path

import bpy
from mathutils import Matrix

ID_COLLECTIONS = ("objects", "meshes", "materials", "images", "textures", "node_groups", "collections",
                  "cameras", "lights", "armatures", "actions", "worlds", "scenes", "libraries")


def make_glb(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mat = bpy.data.materials.new("MatA")
    mat.use_nodes = True
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=(0, 0, 0.2))
    cube = bpy.context.active_object
    # non-square footprint (0.4 x 0.2 m): the UM_FBX_v1 rotation must visibly swap X and Y sizes
    cube.data.transform(Matrix.Diagonal((1.0, 0.5, 1.0, 1.0)))
    cube.name = "part_body"
    cube.data.name = "part_body_mesh"
    cube.data.materials.append(mat)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.1, location=(0, 0, 0.5), segments=12, ring_count=6)
    head = bpy.context.active_object
    head.name = "part_head"
    head.data.name = "part_head_mesh"
    head.data.materials.append(bpy.data.materials.new("MatB"))
    bpy.ops.export_scene.gltf(filepath=str(path), export_format="GLB")


def all_id_collections():
    """Every ID collection of bpy.data (wider than the stage scripts' cleanup list on purpose)."""
    names = []
    for name in dir(bpy.data):
        value = getattr(bpy.data, name, None)
        if isinstance(value, bpy.types.bpy_prop_collection):
            if all(isinstance(i, bpy.types.ID) for i in value):
                names.append(name)
    return sorted(names)


def state():
    snap = {name: sorted(i.name for i in getattr(bpy.data, name)) for name in all_id_collections()}
    assert set(ID_COLLECTIONS) <= set(snap), "harness must see at least what the stage scripts clean"
    from io_scene_fbx import export_fbx_bin, fbx_utils
    snap["_active_scene"] = bpy.context.window.scene.name if bpy.context.window else bpy.context.scene.name
    snap["_user_cube_location"] = list(bpy.data.objects["UserCube"].location)
    snap["_is_dirty"] = bpy.data.is_dirty
    snap["_fbx_patches"] = {
        "vid_path": export_fbx_bin._gen_vid_path.__name__,
        "datetime_is_module": type(export_fbx_bin.datetime).__name__,
        "fbx_utils_has_hash": "hash" in fbx_utils.__dict__,
    }
    return snap


def live(job):
    bpy.ops.wm.read_factory_settings(use_empty=False)  # default startup: Cube, Camera, Light, "Scene"
    bpy.data.objects["Cube"].name = "UserCube"
    bpy.data.scenes.new("UserSecondScene")
    if job.get("collide"):
        mesh = bpy.data.meshes.new("part_body")
        obj = bpy.data.objects.new("part_body", mesh)  # same name as a GLB node
        bpy.context.scene.collection.objects.link(obj)
        bpy.data.materials.new("MatA")  # same name as a GLB material
    before = state()
    runs = []
    for item in job["stages"]:
        code = ('TRIPO_PIPELINE_PARAMS = %r\nTRIPO_PIPELINE_ISOLATION = "live"\n' % item["params"]
                + Path(item["script"]).read_text(encoding="utf-8"))
        namespace = {"bpy": bpy}  # exactly what blender_mcp_addon.execute_code passes
        buf = io.StringIO()
        error = None
        try:
            with redirect_stdout(buf):
                exec(code, namespace)
        except Exception:  # noqa: BLE001 - the addon reports any exception
            error = traceback.format_exc()
        runs.append({"stage": item["stage"], "stdout": buf.getvalue(), "error": error})
    after = state()
    Path(job["result"]).write_text(json.dumps({"before": before, "after": after, "runs": runs}, indent=1),
                                   encoding="utf-8")


def main():
    job = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))
    if job["mode"] == "make-glb":
        make_glb(job["glb"])
    else:
        live(job)
    print("HARNESS_OK")


main()
