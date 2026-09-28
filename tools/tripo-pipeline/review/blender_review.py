"""Editor review frames of a pipeline candidate in the LIVE Blender (sent via blender_mcp.py exec).

Not a pipeline stage: the frames are editor screenshots for people, not measured
contracts. Driven by capture_blender_review.py, which prepends

    REVIEW_MODE = "setup" | "view" | "teardown"
    REVIEW_PARAMS = {...}

setup    appends the candidate scene from the run's work .blend and imports the
         untouched Tripo GLB next to it (scaled to the same height, shifted to -X)
         in the same temporary scene; remembers the user's window scene and 3D view
         state in bpy.app.driver_namespace.
view     sets the first 3D viewport (orthographic view, solid shading with texture
         colour, backface culling on/off, overlays off) for one named view.
teardown restores the window scene and the 3D view exactly and removes every
         datablock created by setup. The user's file is never saved.
"""

import json
import math

import bpy
from mathutils import Euler, Vector

KEY = "tripo_pipeline_review_state"
SCENE = "tripo_pipeline_candidate"
ID_COLLECTIONS = ("objects", "meshes", "materials", "images", "textures", "node_groups", "collections",
                  "cameras", "lights", "armatures", "actions", "worlds", "scenes", "libraries")


def view3d():
    screen = bpy.context.window.screen if bpy.context.window else bpy.context.screen
    for area in screen.areas:
        if area.type == "VIEW_3D":
            return area, area.spaces.active
    raise RuntimeError("no 3D viewport in the live Blender window")


def setup(params):
    ns = bpy.app.driver_namespace
    if KEY in ns:
        raise RuntimeError("review state already present; run teardown first")
    if SCENE in bpy.data.scenes:
        raise RuntimeError("scene %r already exists" % SCENE)
    before = {n: set(getattr(bpy.data, n)) for n in ID_COLLECTIONS}
    window = bpy.context.window or bpy.context.window_manager.windows[0]
    _area, space = view3d()
    r3d = space.region_3d
    state = {
        "before": before, "window_scene": window.scene, "window_view_layer": window.view_layer,
        "view": {"perspective": r3d.view_perspective, "rotation": r3d.view_rotation.copy(),
                 "location": r3d.view_location.copy(), "distance": r3d.view_distance},
        "shading": {"type": space.shading.type, "color_type": space.shading.color_type,
                    "light": space.shading.light, "culling": space.shading.show_backface_culling},
        "overlays": space.overlay.show_overlays,
    }
    ns[KEY] = state
    with bpy.data.libraries.load(params["blend"], link=False) as (src, dst):
        dst.scenes = [SCENE]
    scene = dst.scenes[0]
    window.scene = scene
    height = params["height_m"]
    with bpy.context.temp_override(window=window, scene=scene, view_layer=scene.view_layers[0]):
        existing = set(scene.objects)
        bpy.ops.import_scene.gltf(filepath=params["source_glb"])
        imported = [o for o in scene.objects if o not in existing]
    meshes = [o for o in imported if o.type == "MESH"]
    lo = min((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
    hi = max((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
    root = bpy.data.objects.new("tripo_review_source_root", None)
    scene.collection.objects.link(root)
    for obj in imported:
        if obj.parent is None:
            obj.parent = root
    s = height / (hi - lo)
    root.scale = (s, s, s)
    root.location = (params["source_offset_x_m"], 0.0, -lo * s)
    print("TRIPO_REVIEW_SETUP_OK", json.dumps({"scene": scene.name, "source_parts": len(meshes),
                                               "source_scale": round(s, 6)}))


def view(params):
    state = bpy.app.driver_namespace.get(KEY)
    if not state:
        raise RuntimeError("run setup first")
    _area, space = view3d()
    v = params["view"]
    r3d = space.region_3d
    r3d.view_perspective = "ORTHO"
    r3d.view_rotation = Euler([math.radians(a) for a in v["euler_deg"]]).to_quaternion()
    r3d.view_location = Vector(v["center_m"])
    r3d.view_distance = v["distance"]
    space.shading.type = "SOLID"
    space.shading.light = "STUDIO"
    space.shading.color_type = "TEXTURE"
    space.shading.show_backface_culling = bool(v.get("backface_culling", True))
    space.overlay.show_overlays = False
    print("TRIPO_REVIEW_VIEW_OK", v["name"])


def teardown(_params):
    ns = bpy.app.driver_namespace
    state = ns.get(KEY)
    if not state:
        print("TRIPO_REVIEW_TEARDOWN_OK nothing-to-do")
        return
    window = bpy.context.window or bpy.context.window_manager.windows[0]
    window.scene = state["window_scene"]
    window.view_layer = state["window_view_layer"]
    _area, space = view3d()
    r3d = space.region_3d
    r3d.view_perspective = state["view"]["perspective"]
    r3d.view_rotation = state["view"]["rotation"]
    r3d.view_location = state["view"]["location"]
    r3d.view_distance = state["view"]["distance"]
    space.shading.type = state["shading"]["type"]
    space.shading.color_type = state["shading"]["color_type"]
    space.shading.light = state["shading"]["light"]
    space.shading.show_backface_culling = state["shading"]["culling"]
    space.overlay.show_overlays = state["overlays"]
    doomed = []
    for name in ID_COLLECTIONS:
        doomed.extend(i for i in getattr(bpy.data, name) if i not in state["before"][name])
    bpy.data.batch_remove(doomed)
    del ns[KEY]
    print("TRIPO_REVIEW_TEARDOWN_OK removed=%d" % len(doomed))


{"setup": setup, "view": view, "teardown": teardown}[globals()["REVIEW_MODE"]](globals().get("REVIEW_PARAMS") or {})
