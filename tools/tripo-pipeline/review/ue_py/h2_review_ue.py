"""UE editor Python task (LIVE editor via review/ue_live.py run_task): H2 hero review scene on the Cobble light (W5c-A).

ARGS: {"out": ..., "op": ..., ...}; driven by review/h2_ue_review.py (read its docstring first).

  setup    {"level", "hide_label_prefixes", "keep_labels", "lights": {...}, "sky": {...}, "figure": {...},
            "base": {...}}  on the already loaded review level (the P1.7 Cobble control level): hides the review
           figures (temporarily hidden in the editor), applies the light profile in memory (the fill light off, the key
           CSM of the profile), spawns a Movable SkyLight from the profile cubemap and the H2 figure + base (their
           asset materials = the default team MI). Nothing is saved; the host reloads the previous level at the end.
  measure  {"label", "base_label", "bones": [...], "sockets": [...]}  ref-pose points of the figure in component
           space (bones and sockets), the facing derived from them, actor/asset bounds, materials of both actors,
           the textures the figure MI samples (size, sRGB, compression), the lights of the level
Everything else (camera, material swaps, yaw, cleanup) goes through ue_py/control_scene_ue.py (ops by actor label).
"""
import json
import math

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
actors_sub = u.get_editor_subsystem(u.EditorActorSubsystem)


def vec(v):
    return u.Vector(float(v[0]), float(v[1]), float(v[2]))


def v3(v, nd=4):
    return [round(v.x, nd), round(v.y, nd), round(v.z, nd)]


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    asset = u.load_asset(obj(path))
    if asset is None:
        raise RuntimeError("asset not found: %s" % path)
    return asset


def by_label(label, required=True):
    hits = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == label]
    if required and len(hits) != 1:
        raise RuntimeError("actor %r: %d matches" % (label, len(hits)))
    return hits[0] if hits else None


def current_level():
    w = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    path = w.get_path_name().split(".")[0] if w else None
    del w
    return path


def light_info(a):
    lc = a.light_component
    item = {"label": a.get_actor_label(), "class": a.get_class().get_name(), "location": v3(a.get_actor_location(), 2),
            "rotation_pitch_yaw_roll": [round(a.get_actor_rotation().pitch, 3), round(a.get_actor_rotation().yaw, 3),
                                        round(a.get_actor_rotation().roll, 3)],
            "intensity": round(float(lc.get_editor_property("intensity")), 4),
            "cast_shadows": bool(lc.get_editor_property("cast_shadows")),
            "mobility": str(lc.get_editor_property("mobility"))}
    for name in ("intensity_units", "attenuation_radius", "dynamic_shadow_distance_movable_light",
                 "dynamic_shadow_cascades", "source_type", "lower_hemisphere_is_black", "real_time_capture"):
        try:
            value = lc.get_editor_property(name)
        except Exception:  # noqa: BLE001 - property of another light class
            continue
        item[name] = value if isinstance(value, (bool, int, float)) else str(value)
    if isinstance(a, u.SkyLight):
        cube = lc.get_editor_property("cubemap")
        item["cubemap"] = cube.get_path_name().split(".")[0] if cube else None
    return item


def lights():
    out = []
    for a in actors_sub.get_all_level_actors():
        if isinstance(a, (u.DirectionalLight, u.PointLight, u.SpotLight, u.RectLight, u.SkyLight)):
            info = light_info(a)
            info["hidden_in_editor"] = bool(a.is_temporarily_hidden_in_editor())
            out.append(info)
    return sorted(out, key=lambda x: x["label"])


def texture_info(tex):
    return {"asset": tex.get_path_name().split(".")[0], "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()],
            "srgb": bool(tex.get_editor_property("srgb")),
            "compression": str(tex.get_editor_property("compression_settings")),
            "flip_green": bool(tex.get_editor_property("flip_green_channel"))}


def material_info(m):
    d = {"path": m.get_path_name().split(".")[0], "class": m.get_class().get_name()}
    if isinstance(m, u.MaterialInstance):
        parent = m.get_editor_property("parent")
        d["parent"] = parent.get_path_name().split(".")[0] if parent else None
        d["textures"] = {}
        for name in ("BaseColorTexture", "NormalTexture", "ORMTexture", "TeamMaskTexture"):
            tex = u.MaterialEditingLibrary.get_material_instance_texture_parameter_value(m, name)
            d["textures"][name] = texture_info(tex) if tex else None
        d["scalars"] = {n: round(u.MaterialEditingLibrary.get_material_instance_scalar_parameter_value(m, n), 5)
                        for n in ("TeamDye", "TeamDyeGain", "SideBandWeight")}
        c = u.MaterialEditingLibrary.get_material_instance_vector_parameter_value(m, "TeamColor")
        d["TeamColor"] = [round(c.r, 6), round(c.g, 6), round(c.b, 6), round(c.a, 6)]
    return d


out = {"op": args["op"]}
op = args["op"]
if op == "setup":
    level = current_level()
    if level != args["level"]:
        raise RuntimeError("review level %s is not open (current %s)" % (args["level"], level))
    hidden = []
    keep = set(args.get("keep_labels") or [])
    for a in actors_sub.get_all_level_actors():
        label = a.get_actor_label()
        if label in keep or not any(label.startswith(p) for p in args["hide_label_prefixes"]):
            continue
        if isinstance(a, (u.StaticMeshActor, u.SkeletalMeshActor)):
            a.set_is_temporarily_hidden_in_editor(True)
            hidden.append(label)
    out["hidden_review_actors"] = sorted(hidden)
    out["lights_before"] = lights()
    lc_cfg = args["lights"]
    for label in lc_cfg.get("off", []):
        a = by_label(label)
        a.light_component.set_editor_property("intensity", 0.0)
        a.set_is_temporarily_hidden_in_editor(True)
    key = by_label(lc_cfg["key"]["label"])
    kc = key.light_component
    kc.set_editor_property("intensity", float(lc_cfg["key"]["intensity_lux"]))
    kc.set_editor_property("dynamic_shadow_distance_movable_light", float(lc_cfg["key"]["shadow_distance_uu"]))
    kc.set_editor_property("dynamic_shadow_cascades", int(lc_cfg["key"]["cascades"]))
    kc.set_editor_property("contact_shadow_length", float(lc_cfg["key"].get("contact_shadow_length", 0.0)))
    r = lc_cfg["key"]["rotation_pitch_yaw_roll"]
    key.set_actor_rotation(u.Rotator(roll=float(r[2]), pitch=float(r[0]), yaw=float(r[1])), False)
    sky_cfg = args["sky"]
    sky = by_label(sky_cfg["label"], required=False)
    if sky is None:
        sky = actors_sub.spawn_actor_from_class(u.SkyLight, u.Vector(0, 0, 300), u.Rotator(0, 0, 0))
        sky.set_actor_label(sky_cfg["label"])
    sc = sky.light_component
    sc.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
    sc.set_editor_property("source_type", u.SkyLightSourceType.SLS_SPECIFIED_CUBEMAP)
    sc.set_editor_property("cubemap", load(sky_cfg["cubemap"]))
    sc.set_editor_property("intensity", float(sky_cfg["intensity"]))
    sc.set_editor_property("lower_hemisphere_is_black", bool(sky_cfg["lower_hemisphere_is_black"]))
    sc.set_editor_property("real_time_capture", False)
    sc.set_light_color(u.LinearColor(*[float(c) for c in sky_cfg["color_linear"]], 1.0))
    sc.recapture_sky()
    for spec in [x for x in (args["figure"], args.get("base")) if x]:  # base optional (H2Anim: Medusa/Harpy)
        old = by_label(spec["label"], required=False)
        if old is not None:
            actors_sub.destroy_actor(old)
        rot = u.Rotator(roll=0.0, pitch=0.0, yaw=float(spec.get("yaw", 0.0)))
        if spec["kind"] == "skeletal":
            a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, vec(spec["location"]), rot)
            comp = a.skeletal_mesh_component
            comp.set_skinned_asset_and_update(load(spec["asset"]))
        else:
            a = actors_sub.spawn_actor_from_class(u.StaticMeshActor, vec(spec["location"]), rot)
            comp = a.static_mesh_component
            comp.set_static_mesh(load(spec["asset"]))
        comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        a.set_actor_label(spec["label"])
    out["lights_after"] = lights()
    out["level"] = level
elif op == "measure":
    a = by_label(args["label"])
    comp = a.skeletal_mesh_component
    loc, yaw = a.get_actor_location(), a.get_actor_rotation().yaw
    c, s = math.cos(math.radians(-yaw)), math.sin(math.radians(-yaw))

    def comp_space(w):
        dx, dy, dz = w.x - loc.x, w.y - loc.y, w.z - loc.z
        return [round(dx * c - dy * s, 4), round(dx * s + dy * c, 4), round(dz, 4)]

    pts = {}
    for n in args["bones"] + args["sockets"]:
        pts[n] = comp_space(comp.get_socket_location(n))
    out["points_component_uu"] = pts
    out["actor"] = {"location": v3(loc, 3), "yaw": round(yaw, 3)}
    # facing (rig-report method on the UE side): side = mean(arm_upper, leg_upper) .L - .R; UE is left-handed
    # (X forward, Y right), so a figure facing +X has its left at -Y and front = side turned +90 deg about Z
    side = [0.0, 0.0]
    for left, right in (("arm_upper_L", "arm_upper_R"), ("leg_upper_L", "leg_upper_R")):
        side[0] += (pts[left][0] - pts[right][0]) / 2.0
        side[1] += (pts[left][1] - pts[right][1]) / 2.0
    front = [-side[1], side[0]]
    out["facing"] = {"left_minus_right_xy": [round(v, 4) for v in side], "front_xy": [round(v, 4) for v in front],
                     "front_yaw_deg_component": round(math.degrees(math.atan2(front[1], front[0])), 3),
                     "weapon_side_y_component": pts.get("weapon_R", [0, 0, 0])[1],
                     "method": "side = mean(arm_upper, leg_upper) _L - _R in component space; front = side turned +90 deg "
                               "about Z (UE: X forward, Y right); 0 deg = +X"}
    mesh = comp.get_skinned_asset()
    b = mesh.get_bounds()
    out["asset_bounds"] = {"origin": v3(b.origin), "extent": v3(b.box_extent),
                           "min": v3(b.origin - b.box_extent), "max": v3(b.origin + b.box_extent)}
    out["bones_in_component"] = int(comp.get_num_bones())
    out["bone0"] = str(comp.get_bone_name(0))
    out["figure_materials"] = [material_info(m) for m in comp.get_materials() if m]
    base = by_label(args["base_label"])
    out["base_materials"] = [material_info(m) for m in base.static_mesh_component.get_materials() if m]
    bb = base.static_mesh_component.static_mesh.get_bounding_box()
    out["base_asset_bounds"] = {"min": v3(bb.min), "max": v3(bb.max)}
    out["lights"] = lights()
else:
    raise RuntimeError("unknown op %s" % op)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
