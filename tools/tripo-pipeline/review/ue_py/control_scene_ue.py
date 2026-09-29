"""UE editor Python task (LIVE editor via review/ue_live.py run_task): P1.7 control scene (stage 3, T3.1).

ARGS: {"out": ..., "op": ..., ...}; driven by review/control_scene.py (read its docstring first).

  build    {"scene": <scene spec>}  deletes the scene folder (only /Game/ArtTests/P17ControlScene), duplicates the
           Cobble review level, removes its figures/markers/camera, moves the fill light, adds the fixed-exposure
           post-process volume, creates the per-instance material instances, spawns the candidates on board cells
           (a spec actor with "place_on_surface" -- decor -- goes to the top of the surface under its bottom
           footprint, place_on_surface()), saves ONLY the scene folder and returns the measurements (actors, sockets,
           bounds, materials, textures, lights, decor support). Refuses when the scene folder holds a package that is
           not in the spec.
  camera   {"label", "location", "rotation", "fov"} spawns (once) and moves the temporary camera, pilots the viewport
  set      {"changes": [{"label", "visible"?, "yaw"?, "cast_shadow"?, "materials"?: {slot index: path}}
                        | {"label_prefix", "visible"}]}  (prefix: every StaticMeshActor with that label prefix)
  pose     {"label", "anim", "time"}  respawns the skeletal actor with a single-node animation at `time`
           (a re-posed existing actor lags one call behind, measured in T2.1)
  bones    {"label", "names": [...]}  world positions of bones/sockets of a skeletal actor
  cleanup  {"labels": [...]}          ejects the pilot and destroys the listed temporary actors (nothing is saved)

Everything spawned by `camera`/`pose`/`set` lives only in memory: the host reloads the previous level at the end and
the saved control level keeps the state written by `build`.
"""
import json
import math

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
actors_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
level_sub = u.get_editor_subsystem(u.LevelEditorSubsystem)
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary


def vec(v):
    return u.Vector(float(v[0]), float(v[1]), float(v[2]))


def v3(v, nd=4):
    return [round(v.x, nd), round(v.y, nd), round(v.z, nd)]


def by_label(label, required=True):
    hits = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == label]
    if required and len(hits) != 1:
        raise RuntimeError("actor %r: %d matches" % (label, len(hits)))
    return hits[0] if hits else None


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    asset = u.load_asset(obj(path))
    if asset is None:
        raise RuntimeError("asset not found: %s" % path)
    return asset


def texture_info(tex):
    return {"path": tex.get_path_name().split(".")[0], "srgb": bool(tex.get_editor_property("srgb")),
            "compression": str(tex.get_editor_property("compression_settings")).split(".")[-1].split(":")[0].strip("<> "),
            "flip_green": bool(tex.get_editor_property("flip_green_channel")),
            "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()]}


def material_info(mat):
    info = {"path": mat.get_path_name().split(".")[0], "class": mat.get_class().get_name()}
    base = mat
    chain = []
    while isinstance(base, u.MaterialInstance):
        parent = base.get_editor_property("parent")
        chain.append(parent.get_path_name().split(".")[0] if parent else None)
        base = parent
        if base is None:
            break
    info["parents"] = chain
    if isinstance(base, u.Material):
        info["base_material"] = {"path": base.get_path_name().split(".")[0], "two_sided": bool(base.get_editor_property("two_sided")),
                                 "blend_mode": str(base.get_editor_property("blend_mode")).split(".")[-1].split(":")[0].strip("<> ")}
        info["textures"] = sorted((texture_info(t) for t in MEL.get_used_textures(base) if isinstance(t, u.Texture2D)),
                                  key=lambda t: t["path"])
    if isinstance(mat, u.MaterialInstance):
        vectors = {}
        for name in ("TeamColor",):
            try:
                c = MEL.get_material_instance_vector_parameter_value(mat, name)
                vectors[name] = [round(c.r, 4), round(c.g, 4), round(c.b, 4), round(c.a, 4)]
            except Exception:  # noqa: BLE001
                pass
        scalars = {}
        for name in ("InstanceIndex",):
            try:
                scalars[name] = round(MEL.get_material_instance_scalar_parameter_value(mat, name), 4)
            except Exception:  # noqa: BLE001
                pass
        info["vector_parameters"], info["scalar_parameters"] = vectors, scalars
    return info


def skeletal_triangles(mesh):
    """LOD0 triangles of a skeletal mesh through GeometryScript (copy_mesh_from_skeletal_mesh into a transient
    DynamicMesh; MCP SkeletalMeshTools has no triangle count, UE Python has no clone_mesh_description)."""
    try:
        dm = u.DynamicMesh()
        _dm, outcome = u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            mesh, dm, u.GeometryScriptCopyMeshFromAssetOptions(), u.GeometryScriptMeshReadLOD())
        if "SUCCESS" not in str(outcome):
            return "not measured: %s" % outcome
        return int(u.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm))
    except Exception as exc:  # noqa: BLE001
        return "not measured: %s" % exc


def dynamic_mesh(mesh):
    """A transient GeometryScript DynamicMesh copy of a static mesh asset (LOD0, mesh space)."""
    dm = u.DynamicMesh()
    _dm, outcome = u.GeometryScript_AssetUtils.copy_mesh_from_static_mesh(
        mesh, dm, u.GeometryScriptCopyMeshFromAssetOptions(), u.GeometryScriptMeshReadLOD())
    if "SUCCESS" not in str(outcome):
        raise RuntimeError("could not read %s: %s" % (mesh.get_path_name(), outcome))
    return dm


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def inside_convex(poly, x, y):
    n = len(poly)
    for i in range(n):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % n]
        if (x1 - x0) * (y - y0) - (y1 - y0) * (x - x0) < 0:
            return False
    return True


SUPPORT_TOL_UU, SUPPORT_STEP_UU, SUPPORT_RAY_FROM_Z = 0.5, 1.0, 500.0


def place_on_surface(spec, exclude_prefixes):
    """Height of the surface a decor actor stands on (stage-3 review fix: the barrel stood at z 0 inside the 5 uu
    wooden rim). Bottom footprint = convex hull of the mesh vertices within SUPPORT_TOL_UU of its lowest point, at the
    spec location and yaw; downward rays (GeometryScript BVH, collision-independent: the Cobble board actor has no
    collision) on its hull vertices and a SUPPORT_STEP_UU grid inside it, against every visible static-mesh actor of
    the level whose bounds overlap the footprint (the scene's own P17 actors excluded). The actor goes to the highest
    hit (nothing sinks); the spread between the lowest and highest hit is reported (> 0 = partly floating)."""
    mesh = load(spec["asset"])
    dm = dynamic_mesh(mesh)
    _dm, vlist, _gaps = u.GeometryScript_MeshQueries.get_all_vertex_positions(dm, True)
    verts = u.GeometryScript_List.convert_vector_list_to_array(vlist)
    verts = verts[0] if isinstance(verts, tuple) else verts
    z0 = min(p.z for p in verts)
    hull = convex_hull([(round(p.x, 4), round(p.y, 4)) for p in verts if p.z <= z0 + SUPPORT_TOL_UU])
    yaw = math.radians(float(spec.get("yaw", 0.0)))
    c, s = math.cos(yaw), math.sin(yaw)
    lx, ly = float(spec["location"][0]), float(spec["location"][1])
    world = [(lx + x * c - y * s, ly + x * s + y * c) for x, y in hull]
    xs, ys = [p[0] for p in world], [p[1] for p in world]
    samples = list(world)
    gx = math.floor(min(xs))
    while gx <= max(xs):
        gy = math.floor(min(ys))
        while gy <= max(ys):
            if inside_convex(world, gx, gy):
                samples.append((gx, gy))
            gy += SUPPORT_STEP_UU
        gx += SUPPORT_STEP_UU
    supports = []
    for a in actors_sub.get_all_level_actors():
        if not isinstance(a, u.StaticMeshActor):
            continue
        label = a.get_actor_label()
        comp = a.static_mesh_component
        if (any(label.startswith(p) for p in exclude_prefixes) or a.get_editor_property("hidden")
                or not comp.get_editor_property("visible") or comp.static_mesh is None):
            continue
        o, e = a.get_actor_bounds(False)
        if o.x + e.x < min(xs) or o.x - e.x > max(xs) or o.y + e.y < min(ys) or o.y - e.y > max(ys):
            continue
        adm = dynamic_mesh(comp.static_mesh)
        u.GeometryScript_MeshTransforms.transform_mesh(adm, a.get_actor_transform())
        _adm, bvh = u.GeometryScript_MeshSpatial.build_bvh_for_mesh(adm)
        supports.append((label, comp.static_mesh.get_path_name().split(".")[0], adm, bvh))
    hits = []
    for x, y in samples:
        best = None
        for label, _mesh, adm, bvh in supports:
            _m, hit, _o = u.GeometryScript_MeshSpatial.find_nearest_ray_intersection_with_mesh(
                adm, bvh, u.Vector(x, y, SUPPORT_RAY_FROM_Z), u.Vector(0.0, 0.0, -1.0),
                u.GeometryScriptSpatialQueryOptions())
            if hit.get_editor_property("hit"):
                z = hit.get_editor_property("hit_position").z
                if best is None or z > best[0]:
                    best = (z, label)
        hits.append(best)
    missing = [samples[i] for i, h in enumerate(hits) if h is None]
    if missing:
        raise RuntimeError("%s: no surface under %d footprint samples, e.g. %s" % (spec["label"], len(missing), missing[:3]))
    zs = [h[0] for h in hits]
    return {"method": "downward GeometryScript BVH rays on the bottom footprint (hull of vertices within %.1f uu of the "
                      "lowest point + %.0f uu grid) against the visible static-mesh actors of the level"
                      % (SUPPORT_TOL_UU, SUPPORT_STEP_UU),
            "mesh_bottom_z_uu": round(z0, 4), "footprint_hull_mesh_uu": [[round(x, 3), round(y, 3)] for x, y in hull],
            "footprint_world_bounds_uu": {"x": [round(min(xs), 3), round(max(xs), 3)], "y": [round(min(ys), 3), round(max(ys), 3)]},
            "samples": len(samples), "support_z_max_uu": round(max(zs), 4), "support_z_min_uu": round(min(zs), 4),
            "spread_uu": round(max(zs) - min(zs), 4),
            "supports": [{"label": lb, "mesh": m} for lb, m, _a, _b in supports if lb in {h[1] for h in hits}],
            "placed_actor_z_uu": round(max(zs) - z0, 4)}


def comp_space(actor, world):
    """World point -> actor/component space (actors are spawned with scale 1 and yaw only)."""
    loc, yaw = actor.get_actor_location(), math.radians(actor.get_actor_rotation().yaw)
    dx, dy, dz = world.x - loc.x, world.y - loc.y, world.z - loc.z
    c, s = math.cos(-yaw), math.sin(-yaw)
    return [round(dx * c - dy * s, 4), round(dx * s + dy * c, 4), round(dz, 4)]


def spawn(spec):
    # NB: unreal.Rotator positional order is (roll, pitch, yaw); always pass keywords
    rot = u.Rotator(roll=0.0, pitch=0.0, yaw=float(spec.get("yaw", 0.0)))
    if spec["kind"] == "static":
        a = actors_sub.spawn_actor_from_class(u.StaticMeshActor, vec(spec["location"]), rot)
        comp = a.static_mesh_component
        comp.set_static_mesh(load(spec["asset"]))
    else:
        a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, vec(spec["location"]), rot)
        comp = a.skeletal_mesh_component
        comp.set_skinned_asset_and_update(load(spec["asset"]))
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    for idx, path in sorted((spec.get("materials") or {}).items(), key=lambda kv: int(kv[0])):
        comp.set_material(int(idx), load(path))
    a.set_actor_label(spec["label"])
    return a


def describe_actor(a):
    d = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "location": v3(a.get_actor_location(), 3),
         "yaw": round(a.get_actor_rotation().yaw, 3), "hidden": bool(a.is_hidden_ed())}
    if isinstance(a, u.StaticMeshActor):
        comp = a.static_mesh_component
        mesh = comp.static_mesh
        d["asset"] = mesh.get_path_name().split(".")[0]
        d["triangles_lod0"] = int(mesh.get_num_triangles(0))
        box = mesh.get_bounding_box()
        d["asset_bounds"] = {"min": v3(box.min), "max": v3(box.max)}
    else:
        comp = a.skeletal_mesh_component
        mesh = comp.get_skinned_asset()
        d["asset"] = mesh.get_path_name().split(".")[0]
        b = mesh.get_bounds()
        d["asset_bounds_box"] = {"origin": v3(b.origin), "extent": v3(b.box_extent)}
        d["skeleton"] = mesh.get_editor_property("skeleton").get_path_name().split(".")[0]
        d["bones"] = int(comp.get_num_bones())
        d["bone0"] = str(comp.get_bone_name(0))
        d["triangles_lod0"] = skeletal_triangles(mesh)
        d["sockets"] = {}
        for s in ("Weapon", "Head"):
            if comp.does_socket_exist(s):
                w = comp.get_socket_location(s)
                d["sockets"][s] = {"world": v3(w), "component": comp_space(a, w),
                                   "bone": str(comp.get_socket_bone_name(s))}
    origin, extent = a.get_actor_bounds(False)
    d["world_bounds"] = {"min": v3(origin - extent), "max": v3(origin + extent)}
    d["materials"] = [material_info(m) if m else None for m in comp.get_materials()]
    d["cast_shadow"] = bool(comp.get_editor_property("cast_shadow"))
    return d


def lights_info():
    out = []
    for a in actors_sub.get_all_level_actors():
        lc = None
        for cls in (u.DirectionalLight, u.PointLight, u.SpotLight, u.RectLight, u.SkyLight):
            if isinstance(a, cls):
                lc = a.light_component
        if lc is None:
            continue
        c = lc.get_editor_property("light_color")
        item = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "location": v3(a.get_actor_location(), 2),
                "rotation": [round(a.get_actor_rotation().pitch, 3), round(a.get_actor_rotation().yaw, 3),
                             round(a.get_actor_rotation().roll, 3)],
                "intensity": round(lc.get_editor_property("intensity"), 4), "color_srgb8": [c.r, c.g, c.b],
                "cast_shadows": bool(lc.get_editor_property("cast_shadows"))}
        try:
            item["attenuation_radius"] = round(lc.get_editor_property("attenuation_radius"), 2)
        except Exception:  # noqa: BLE001
            pass
        out.append(item)
    return sorted(out, key=lambda x: x["label"])


def current_level_path():
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    path = w.get_path_name().split(".")[0] if w else None
    del w
    return path


LIGHT_PROPS = ("intensity", "light_color", "cast_shadows", "mobility", "attenuation_radius", "source_radius",
               "soft_source_radius", "source_length", "use_inverse_squared_falloff", "light_falloff_exponent",
               "intensity_units", "light_source_angle", "light_source_soft_angle", "indirect_lighting_intensity",
               "volumetric_scattering_intensity", "temperature", "use_temperature", "affects_world",
               "dynamic_shadow_distance_movable_light", "cascade_distribution_exponent", "dynamic_shadow_cascades")


def plain(v):
    """A property value as plain Python data. Struct wrappers returned by get_editor_property can point into the
    owning object's memory: after the source world was replaced by new_level, the copied point-light colours came out
    as garbage (fill (11,1,104), warm (10,109,0); measured 2026-09-28 T3.1). Assets and enums are kept as they are."""
    if isinstance(v, u.Color):
        return ("Color", [int(v.r), int(v.g), int(v.b), int(v.a)])
    if isinstance(v, u.LinearColor):
        return ("LinearColor", [float(v.r), float(v.g), float(v.b), float(v.a)])
    if isinstance(v, u.Vector):
        return ("Vector", [float(v.x), float(v.y), float(v.z)])
    if isinstance(v, u.Rotator):
        return ("Rotator", [float(v.roll), float(v.pitch), float(v.yaw)])
    if isinstance(v, (bool, int, float, str)):
        return ("raw", v)
    if isinstance(v, u.EnumBase):
        return ("raw", v)
    raise RuntimeError("property value of type %s is not copied as plain data" % type(v).__name__)


def unplain(t):
    kind, v = t
    if kind == "Color":
        return u.Color(r=v[0], g=v[1], b=v[2], a=v[3])
    if kind == "LinearColor":
        return u.LinearColor(r=v[0], g=v[1], b=v[2], a=v[3])
    if kind == "Vector":
        return u.Vector(v[0], v[1], v[2])
    if kind == "Rotator":
        return u.Rotator(roll=v[0], pitch=v[1], yaw=v[2])
    return v


def plain_json(t):
    kind, v = t
    return v if kind != "raw" else (str(v) if isinstance(v, u.EnumBase) else v)


def read_source(source, remove_prefixes):
    """Actors of the source level as plain data (assets, enums, numbers; structs converted by plain()); no actor,
    component, world or struct wrapper of the source level survives the call."""
    if not level_sub.load_level(source):
        raise RuntimeError("could not load the source level %s" % source)
    copied, removed = [], []
    for a in actors_sub.get_all_level_actors():
        label = a.get_actor_label()
        if any(label.startswith(p) for p in remove_prefixes):
            removed.append(label)
            continue
        item = {"label": label, "class": a.get_class().get_name(), "location": plain(a.get_actor_location()),
                "rotation": plain(a.get_actor_rotation()), "scale": plain(a.get_actor_scale3d())}
        if isinstance(a, u.StaticMeshActor):
            c = a.static_mesh_component
            item.update(mesh=c.static_mesh, materials=list(c.get_materials()),
                        cast_shadow=bool(c.get_editor_property("cast_shadow")), mobility=c.get_editor_property("mobility"),
                        visible=bool(c.get_editor_property("visible")),
                        hidden_in_game=bool(c.get_editor_property("hidden_in_game")),
                        actor_hidden=bool(a.get_editor_property("hidden")))
        elif isinstance(a, (u.DirectionalLight, u.PointLight)):
            lc = a.light_component
            props = {}
            for name in LIGHT_PROPS:
                try:
                    value = lc.get_editor_property(name)
                except Exception:  # noqa: BLE001 - property of another light class
                    continue
                props[name] = plain(value)
            item["light_props"] = props
        else:
            removed.append(label + " (class %s not copied)" % item["class"])
            continue
        copied.append(item)
    return copied, removed


out = {"op": args["op"]}
op = args["op"]
if op == "build":
    sc = args["scene"]
    folder, level, source = sc["folder"], sc["level"], sc["source_level"]
    if not folder.startswith("/Game/ArtTests/P17ControlScene"):
        raise RuntimeError("scene folder must be /Game/ArtTests/P17ControlScene*: %s" % folder)
    current = current_level_path()
    if current == level:
        raise RuntimeError("the control level is open; the host loads another level before build")
    existing = (sorted(p.split(".")[0] for p in EAL.list_assets(folder, recursive=True, include_folder=False))
                if EAL.does_directory_exist(folder) else [])
    allowed = set(sc["owned_packages"])
    foreign = [p for p in existing if p not in allowed]
    if foreign:
        raise RuntimeError("scene folder holds packages this script does not own: %s" % foreign)
    # 1) read the source review level (a normal map load) and keep its actors as plain data. The level asset is NOT
    #    duplicated: EditorAssetLibrary.duplicate_asset of a map followed by load_level of the copy killed the editor
    #    (2026-09-28 16:18 UTC, EditorServer.cpp:2544 "World Memory Leaks": the duplicated world stays in memory as a
    #    standalone object and LoadMap refuses to replace it). No Python variable may keep an actor or a world of a
    #    level that is about to be replaced (UE Python wrappers hold strong references): read_source() returns only
    #    assets and value structs.
    copied, removed = read_source(source, sc["remove_label_prefixes"])
    out["source_actors_copied"] = len(copied)
    out["source_lights"] = sorted(({"label": it["label"], "class": it["class"],
                                    "props": {k: plain_json(v) for k, v in it["light_props"].items()}}
                                   for it in copied if "light_props" in it), key=lambda x: x["label"])
    out["removed_source_actors"] = sorted(removed)
    # 2) back to the host's level is not needed: new_level replaces the editor world with a fresh map
    if existing and not EAL.delete_directory(folder):
        raise RuntimeError("could not delete %s" % folder)
    out["previous_packages_deleted"] = existing
    u.SystemLibrary.collect_garbage()
    if not level_sub.new_level(level):
        raise RuntimeError("could not create %s" % level)
    for item in copied:
        cls = {"StaticMeshActor": u.StaticMeshActor, "DirectionalLight": u.DirectionalLight,
               "PointLight": u.PointLight}[item["class"]]
        a = actors_sub.spawn_actor_from_class(cls, unplain(item["location"]), unplain(item["rotation"]))
        a.set_actor_scale3d(unplain(item["scale"]))
        a.set_actor_label(item["label"])
        if "mesh" in item:
            c = a.static_mesh_component
            c.set_editor_property("mobility", item["mobility"])
            c.set_static_mesh(item["mesh"])
            for i, m in enumerate(item["materials"]):
                if m:
                    c.set_material(i, m)
            c.set_editor_property("cast_shadow", item["cast_shadow"])
            # the 30 "ART005 HIT" click surfaces are invisible (component visible false, actor hidden)
            c.set_editor_property("visible", item["visible"])
            c.set_editor_property("hidden_in_game", item["hidden_in_game"])
            a.set_editor_property("hidden", item["actor_hidden"])
        else:
            lc = a.light_component
            for name, value in item["light_props"].items():
                lc.set_editor_property(name, unplain(value))
    # per-instance material instances (Harpy pips etc.)
    mi_tools = u.AssetToolsHelpers.get_asset_tools()
    out["material_instances"] = {}
    for mi in sc["material_instances"]:
        path = mi["path"]
        pkg_dir, name = path.rsplit("/", 1)
        inst = mi_tools.create_asset(name, pkg_dir, u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(inst, load(mi["parent"]))
        for k, v in (mi.get("scalars") or {}).items():
            MEL.set_material_instance_scalar_parameter_value(inst, k, float(v))
        for k, v in (mi.get("vectors") or {}).items():  # linear values (FromSRGBColor done by the host)
            MEL.set_material_instance_vector_parameter_value(inst, k, u.LinearColor(*[float(c) for c in v]))
        MEL.update_material_instance(inst)
        out["material_instances"][path] = material_info(inst)
    for change in sc["light_changes"]:
        a = by_label(change["label"])
        if "location" in change:
            a.set_actor_location(vec(change["location"]), False, False)
    ex = sc["exposure"]
    ppv = actors_sub.spawn_actor_from_class(u.PostProcessVolume, u.Vector(0, 0, 0), u.Rotator(0, 0, 0))
    ppv.set_actor_label(ex["label"])
    ppv.set_editor_property("unbound", True)
    ppv.set_editor_property("priority", 1000.0)
    s = ppv.get_editor_property("settings")
    s.set_editor_property("override_auto_exposure_method", True)
    s.set_editor_property("auto_exposure_method", getattr(u.AutoExposureMethod, ex["method"]))
    s.set_editor_property("override_auto_exposure_bias", True)
    s.set_editor_property("auto_exposure_bias", float(ex["bias"]))
    s.set_editor_property("override_auto_exposure_min_brightness", True)
    s.set_editor_property("auto_exposure_min_brightness", float(ex["min_max_brightness"]))
    s.set_editor_property("override_auto_exposure_max_brightness", True)
    s.set_editor_property("auto_exposure_max_brightness", float(ex["min_max_brightness"]))
    s.set_editor_property("override_auto_exposure_apply_physical_camera_exposure", True)
    s.set_editor_property("auto_exposure_apply_physical_camera_exposure", False)
    ppv.set_editor_property("settings", s)
    s2 = ppv.get_editor_property("settings")
    out["exposure_volume"] = {"label": ex["label"], "unbound": bool(ppv.get_editor_property("unbound")),
                              "method": str(s2.get_editor_property("auto_exposure_method")),
                              "bias": s2.get_editor_property("auto_exposure_bias"),
                              "min_brightness": s2.get_editor_property("auto_exposure_min_brightness"),
                              "max_brightness": s2.get_editor_property("auto_exposure_max_brightness")}
    out["decor_support"] = {}
    for spec in sc["actors"]:
        if spec.get("place_on_surface"):
            sup = place_on_surface(spec, spec["place_on_surface"]["exclude_label_prefixes"])
            out["decor_support"][spec["label"]] = sup
            spec = dict(spec, location=[spec["location"][0], spec["location"][1], sup["placed_actor_z_uu"]])
        spawn(spec)
    if not level_sub.save_current_level():
        raise RuntimeError("could not save %s" % level)
    for path in out["material_instances"]:
        EAL.save_asset(path, only_if_is_dirty=False)
    # measurements (after save: what the saved level holds)
    out["actors"] = {spec["label"]: describe_actor(by_label(spec["label"])) for spec in sc["actors"]}
    out["lights"] = lights_info()
    # every copied light property must read back as in the source level (catches dangling struct copies)
    mismatch = []
    for src in out["source_lights"]:
        a = by_label(src["label"])
        for name, value in src["props"].items():
            got = plain_json(plain(a.light_component.get_editor_property(name)))
            if isinstance(value, float) and isinstance(got, float) and abs(value - got) <= 1e-4 * max(1.0, abs(value)):
                continue
            if got != value:
                mismatch.append({"light": src["label"], "property": name, "source": value, "built": got})
    out["lights_copied_as_source"] = not mismatch
    if mismatch:
        raise RuntimeError("light properties differ from the source level: %s" % mismatch[:5])
    out["shadow_casting_lights"] = sum(1 for x in out["lights"] if x["cast_shadows"])
    out["kept_source_actor_prefixes"] = sorted({a.get_actor_label().rsplit(" ", 1)[0] for a in actors_sub.get_all_level_actors()
                                                if a.get_actor_label().startswith("ART005")})
    out["level"] = level
    out["packages_after"] = sorted(p.split(".")[0] for p in EAL.list_assets(folder, recursive=True, include_folder=False))
elif op == "camera":
    a = by_label(args["label"], required=False)
    if a is None:
        a = actors_sub.spawn_actor_from_class(u.CameraActor, vec(args["location"]), u.Rotator(0, 0, 0))
        a.set_actor_label(args["label"])
        cam = a.camera_component
        cam.set_editor_property("field_of_view", float(args.get("fov", 35.0)))
        cam.set_editor_property("constrain_aspect_ratio", False)
    r = args["rotation"]
    a.set_actor_location_and_rotation(vec(args["location"]), u.Rotator(roll=float(r[2]), pitch=float(r[0]), yaw=float(r[1])), False, False)
    level_sub.pilot_level_actor(a)
    out["camera"] = {"label": args["label"], "fov": round(a.camera_component.get_editor_property("field_of_view"), 4),
                     "location": [round(float(x), 4) for x in args["location"]], "rotation": r}
elif op == "set":
    done = []
    for ch in args["changes"]:
        if "label_prefix" in ch:
            # every StaticMeshActor whose label starts with the prefix (lights stay): only "visible" is supported
            hits = [x for x in actors_sub.get_all_level_actors()
                    if isinstance(x, u.StaticMeshActor) and x.get_actor_label().startswith(ch["label_prefix"])]
            for x in hits:
                x.set_is_temporarily_hidden_in_editor(not ch["visible"])
            done.append("%s* (%d static-mesh actors)" % (ch["label_prefix"], len(hits)))
            continue
        a = by_label(ch["label"])
        comp = a.static_mesh_component if isinstance(a, u.StaticMeshActor) else a.skeletal_mesh_component
        if "visible" in ch:
            a.set_is_temporarily_hidden_in_editor(not ch["visible"])
        if "yaw" in ch:
            r = a.get_actor_rotation()
            a.set_actor_rotation(u.Rotator(roll=r.roll, pitch=r.pitch, yaw=float(ch["yaw"])), False)
        if "cast_shadow" in ch:
            comp.set_cast_shadow(bool(ch["cast_shadow"]))
        for idx, path in (ch.get("materials") or {}).items():
            comp.set_material(int(idx), load(path))
        done.append(ch["label"])
    out["changed"] = done
elif op == "pose":
    old = by_label(args["label"])
    loc, rot, mesh = old.get_actor_location(), old.get_actor_rotation(), old.skeletal_mesh_component.get_skinned_asset()
    mats = [m for m in old.skeletal_mesh_component.get_materials()]
    actors_sub.destroy_actor(old)
    a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, loc, rot)
    comp = a.skeletal_mesh_component
    comp.set_skinned_asset_and_update(mesh)
    for i, m in enumerate(mats):
        if m:
            comp.set_material(i, m)
    comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
    a.set_actor_label(args["label"])
    comp.set_update_animation_in_editor(True)
    comp.override_animation_data(load(args["anim"]), False, False, float(args["time"]), 0.0)
    out["pose"] = {"anim": args["anim"], "time": float(args["time"]), "actor_location": v3(a.get_actor_location())}
elif op == "bones":
    a = by_label(args["label"])
    comp = a.skeletal_mesh_component
    out["actor_location"] = v3(a.get_actor_location())
    out["position_read_back"] = round(comp.get_position(), 5)
    out["points"] = {}
    for n in args["names"]:
        w = comp.get_socket_location(n)
        out["points"][n] = {"world": v3(w), "component": comp_space(a, w)}
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
