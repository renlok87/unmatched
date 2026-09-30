"""UE editor Python task for ASSET-TABLE-BASE-001 (LIVE editor via tools/tripo-pipeline/review/ue_live.py run_task).

ARGS: {"out": ..., "op": ..., ...}; driven by scripts/table_base_ue.py (read its docstring first).

  state     current level, dirty packages, scalability / screen-percentage cvars (read-only)
  cvars     {"set": {name: value}} sets console variables, returns the previous values
  measure   {"mesh", "textures": {key: path}, "instance"} static mesh / texture / MI read-back (read-only)
  board     StaticMeshActors whose label starts with "ART005": mesh, location, rotation, world bounds (read-only)
  spawn     {"mesh", "label", "yaw", "location"} spawns the tray as a temporary StaticMeshActor (no collision)
  cleanup   {"labels"} ejects the viewport pilot and destroys the listed temporary actors (nothing is saved)
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
op = args["op"]
out = {"op": op}
actors_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
level_sub = u.get_editor_subsystem(u.LevelEditorSubsystem)
CVARS = ["sg.ViewDistanceQuality", "sg.AntiAliasingQuality", "sg.ShadowQuality", "sg.GlobalIlluminationQuality",
         "sg.ReflectionQuality", "sg.PostProcessQuality", "sg.TextureQuality", "sg.EffectsQuality",
         "sg.FoliageQuality", "sg.ShadingQuality", "r.ScreenPercentage", "r.SecondaryScreenPercentage.GameViewport"]


def v3(v, nd=3):
    return [round(v.x, nd), round(v.y, nd), round(v.z, nd)]


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    a = u.load_asset(obj(path))
    if a is None:
        raise RuntimeError("asset not found: %s" % path)
    return a


def cvar(name):
    try:
        return round(u.SystemLibrary.get_console_variable_float_value(name), 3)
    except Exception as exc:  # noqa: BLE001
        return "error: %s" % exc


if op == "state":
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    out["current_level"] = w.get_path_name().split(".")[0] if w else None
    del w
    out["dirty_maps"] = sorted(p.get_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_map_packages())
    out["dirty_content"] = sorted(p.get_name() for p in u.EditorLoadingAndSavingUtils.get_dirty_content_packages())
    out["cvars"] = {n: cvar(n) for n in CVARS}
    out["engine_version"] = u.SystemLibrary.get_engine_version()
elif op == "cvars":
    prev = {}
    for name, value in args["set"].items():
        prev[name] = cvar(name)
        u.SystemLibrary.execute_console_command(None, "%s %s" % (name, value))
    out["previous"] = prev
    out["now"] = {n: cvar(n) for n in args["set"]}
elif op == "measure":
    sm = load(args["mesh"])
    box = sm.get_bounding_box()
    out["mesh"] = {
        "path": args["mesh"], "class": sm.get_class().get_name(),
        "bounds_min_uu": v3(box.min), "bounds_max_uu": v3(box.max), "size_uu": v3(box.max - box.min),
        "lods": int(sm.get_num_lods()), "triangles_lod0": int(sm.get_num_triangles(0)),
        "vertices_lod0": int(sm.get_num_vertices(0)),
        "uv_channels_lod0": int(u.StaticMeshEditorSubsystem.get_num_uv_channels(
            u.get_editor_subsystem(u.StaticMeshEditorSubsystem), sm, 0)) if hasattr(u, "StaticMeshEditorSubsystem") else None,
        "material_slots": [{"slot": str(m.get_editor_property("material_slot_name")),
                            "material": (m.get_editor_property("material_interface").get_path_name().split(".")[0]
                                         if m.get_editor_property("material_interface") else None)}
                           for m in sm.get_editor_property("static_materials")],
    }
    try:
        ns = sm.get_editor_property("nanite_settings")
        out["mesh"]["nanite_enabled"] = bool(ns.get_editor_property("enabled"))
    except Exception as exc:  # noqa: BLE001
        out["mesh"]["nanite_enabled"] = "error: %s" % exc
    body = sm.get_editor_property("body_setup")
    if body is not None:
        agg = body.get_editor_property("agg_geom")
        out["mesh"]["collision"] = {
            "body_setup": True,
            "simple_elements": sum(len(agg.get_editor_property(k)) for k in
                                   ("box_elems", "sphyl_elems", "sphere_elems", "convex_elems", "tapered_capsule_elems")),
            "collision_trace_flag": str(body.get_editor_property("collision_trace_flag"))}
    else:
        out["mesh"]["collision"] = {"body_setup": False, "simple_elements": 0}
    try:
        bi = sm.get_editor_property("source_models")
        bs = bi[0].get_editor_property("build_settings")
        out["mesh"]["build_settings_lod0"] = {k: str(bs.get_editor_property(k)) for k in (
            "recompute_normals", "recompute_tangents", "use_mikk_t_space", "remove_degenerates",
            "generate_lightmap_u_vs", "src_lightmap_index", "dst_lightmap_index")}
    except Exception as exc:  # noqa: BLE001
        out["mesh"]["build_settings_lod0"] = "error: %s" % exc
    tex = {}
    for key, path in sorted(args.get("textures", {}).items()):
        t = load(path)
        tex[key] = {"path": path, "size": [int(t.blueprint_get_size_x()), int(t.blueprint_get_size_y())],
                    "srgb": bool(t.get_editor_property("srgb")),
                    "compression": str(t.get_editor_property("compression_settings")),
                    "flip_green": bool(t.get_editor_property("flip_green_channel")),
                    "lod_group": str(t.get_editor_property("lod_group"))}
    out["textures"] = tex
    if args.get("instance"):
        mi = load(args["instance"])
        par = mi.get_editor_property("parent")
        out["instance"] = {"path": args["instance"], "parent": par.get_path_name().split(".")[0] if par else None,
                           "textures": {n: (u.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi, n).get_path_name().split(".")[0]
                                            if u.MaterialEditingLibrary.get_material_instance_texture_parameter_value(mi, n) else None)
                                        for n in ("BaseColorTexture", "NormalTexture", "ORMTexture", "TeamMaskTexture")},
                           "TeamColor": [round(x, 4) for x in (lambda c: (c.r, c.g, c.b, c.a))(
                               u.MaterialEditingLibrary.get_material_instance_vector_parameter_value(mi, "TeamColor"))]}
elif op == "board":
    rows = []
    for a in actors_sub.get_all_level_actors():
        if isinstance(a, u.StaticMeshActor) and a.get_actor_label().startswith("ART005"):
            m = a.static_mesh_component.static_mesh
            o, e = a.get_actor_bounds(False)
            r = a.get_actor_rotation()
            rows.append({"label": a.get_actor_label(), "mesh": m.get_path_name().split(".")[0] if m else None,
                         "location": v3(a.get_actor_location()), "rotation_pyr": [round(r.pitch, 3), round(r.yaw, 3), round(r.roll, 3)],
                         "scale": v3(a.get_actor_scale3d()), "world_min": v3(o - e), "world_max": v3(o + e),
                         "hidden": bool(a.is_hidden_ed())})
    out["actors"] = sorted(rows, key=lambda x: x["label"])
    ppv = [a.get_actor_label() for a in actors_sub.get_all_level_actors() if isinstance(a, u.PostProcessVolume)]
    out["post_process_volumes"] = ppv
elif op == "spawn":
    rot = u.Rotator(roll=0.0, pitch=0.0, yaw=float(args.get("yaw", 0.0)))
    loc = args.get("location", [0.0, 0.0, 0.0])
    a = actors_sub.spawn_actor_from_class(u.StaticMeshActor, u.Vector(*[float(x) for x in loc]), rot)
    comp = a.static_mesh_component
    comp.set_static_mesh(load(args["mesh"]))
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    a.set_actor_label(args["label"])
    o, e = a.get_actor_bounds(False)
    out["actor"] = {"label": args["label"], "location": v3(a.get_actor_location()), "yaw": round(a.get_actor_rotation().yaw, 3),
                    "world_min": v3(o - e), "world_max": v3(o + e),
                    "materials": [m.get_path_name().split(".")[0] if m else None for m in comp.get_materials()]}
elif op == "cleanup":
    level_sub.eject_pilot_level_actor()
    out["destroyed"] = []
    for label in args["labels"]:
        for a in [x for x in actors_sub.get_all_level_actors() if x.get_actor_label() == label]:
            actors_sub.destroy_actor(a)
            out["destroyed"].append(label)
else:
    raise RuntimeError("unknown op %s" % op)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
