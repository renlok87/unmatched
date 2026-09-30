"""UE editor Python task (LIVE editor via review/ue_live.py run_task): wave 5c-B1, group H (heroes v2).

ARGS: {"out": ..., "op": ..., ...}; driven by tools/art/material_library/ue_h5cb1.py (read its docstring first).

  reimport  {"textures": [{"asset", "source_file", "settings"}]}  re-import each texture over itself (AssetImportTask,
            replace existing, the MIs keep their reference), set the listed properties (enum values by NAME), save
  mi_params {"instances": {mi path: {"scalars": {name: value}}}}  set scalar overrides of material instances, save
  readback  {"folder", "textures": [...], "instances": [...]}  texture settings + source file of the import data,
            overridden scalars / vectors / parent of the MIs, every package of the folder (numbered copies -> "_1")
  stage     {"figures": [{"label", "mesh", "material", "base", "base_material", "location", "yaw", "scale"}]}
            temporary SkeletalMeshActor + StaticMeshActor (base "<label> base") per figure (the S08 ApplyHeroV2
            placement: both at the cell centre, same yaw and uniform scale); nothing is saved
  pose      {"figures": [{"label", "anim", "time"}]}  respawns each skeletal actor (same transform, mesh, materials)
            with a single-node animation at `time` (an existing actor re-posed lags one call behind, T2.1)
  probe     {"figures": [label, ...]}  posed points: every bone in world space, the skinned mesh bounds of the posed
            component (GeometryScript copy of the component), the base top
  cleanup   {"prefix"}  destroys every actor whose label starts with prefix, ejects the pilot
Nothing here saves a level; `reimport` and `mi_params` save only the listed hero packages.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
op = args["op"]
actors_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
EAL = u.EditorAssetLibrary
MEL = u.MaterialEditingLibrary
out = {"op": op}

ENUMS = {
    "compression_settings": u.TextureCompressionSettings,
    "mip_gen_settings": u.TextureMipGenSettings,
    "filter": u.TextureFilter,
    "lod_group": u.TextureGroup,
}


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    asset = u.load_asset(obj(path))
    if asset is None:
        raise RuntimeError("asset not found: %s" % path)
    return asset


def v3(v, nd=3):
    return [round(v.x, nd), round(v.y, nd), round(v.z, nd)]


def enum_name(value):
    s = str(value)
    if "." in s:
        s = s.split(".")[-1]
    return s.split(":")[0].strip("<> ")


def by_label(label, required=True):
    hits = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == label]
    if required and len(hits) != 1:
        raise RuntimeError("actor %r: %d matches" % (label, len(hits)))
    return hits[0] if hits else None


def texture_info(path):
    tex = load(path)
    info = {"asset": path, "class": tex.get_class().get_name(),
            "size": [tex.blueprint_get_size_x(), tex.blueprint_get_size_y()],
            "srgb": bool(tex.get_editor_property("srgb"))}
    for k in ("compression_settings", "mip_gen_settings", "filter", "lod_group"):
        info[k] = enum_name(tex.get_editor_property(k))
    info["never_stream"] = bool(tex.get_editor_property("never_stream"))
    try:
        aid = tex.get_editor_property("asset_import_data")
        info["source_files"] = [str(x) for x in aid.extract_filenames()] if aid else []
    except Exception as exc:  # noqa: BLE001
        info["source_files"] = "n/a (%s)" % exc
    return info


def mi_info(path):
    mi = load(path)
    parent = mi.get_editor_property("parent")
    rec = {"asset": path, "parent": parent.get_path_name().split(".")[0] if parent else None, "scalars": {},
           "vectors": {}, "textures": {}}
    for p in mi.get_editor_property("scalar_parameter_values"):
        rec["scalars"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = round(
            float(p.get_editor_property("parameter_value")), 5)
    for p in mi.get_editor_property("vector_parameter_values"):
        c = p.get_editor_property("parameter_value")
        rec["vectors"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = [
            round(c.r, 5), round(c.g, 5), round(c.b, 5), round(c.a, 5)]
    for p in mi.get_editor_property("texture_parameter_values"):
        t = p.get_editor_property("parameter_value")
        rec["textures"][str(p.get_editor_property("parameter_info").get_editor_property("name"))] = (
            t.get_path_name().split(".")[0] if t else None)
    # effective values (own override or inherited)
    rec["effective"] = {n: round(MEL.get_material_instance_scalar_parameter_value(mi, n), 5)
                        for n in ("TeamDye", "TeamDyeGain", "TeamDyeCeiling")}
    return rec


if op == "reimport":
    done = []
    for t in args["textures"]:
        path = t["asset"]
        folder, name = path.rsplit("/", 1)
        before = texture_info(path)
        task = u.AssetImportTask()
        task.set_editor_property("filename", t["source_file"])
        task.set_editor_property("destination_path", folder)
        task.set_editor_property("destination_name", name)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("replace_existing_settings", False)
        task.set_editor_property("automated", True)
        task.set_editor_property("save", False)
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        tex = load(path)
        for k, v in sorted((t.get("settings") or {}).items()):
            if k in ENUMS:
                v = getattr(ENUMS[k], v)
            tex.set_editor_property(k, v)
        saved = EAL.save_asset(path, only_if_is_dirty=False)
        done.append({"asset": path, "source_file": t["source_file"], "saved": bool(saved),
                     "imported_objects": [str(x) for x in task.get_editor_property("imported_object_paths")],
                     "before": before, "after": texture_info(path)})
    out["reimported"] = done
elif op == "mi_params":
    done = {}
    for path, spec in sorted(args["instances"].items()):
        mi = load(path)
        before = mi_info(path)
        for n, v in sorted((spec.get("scalars") or {}).items()):
            MEL.set_material_instance_scalar_parameter_value(mi, n, float(v))
        MEL.update_material_instance(mi)
        saved = EAL.save_asset(path, only_if_is_dirty=False)
        done[path] = {"before": before, "after": mi_info(path), "saved": bool(saved)}
    out["instances"] = done
elif op == "readback":
    out["textures"] = {p: texture_info(p) for p in args.get("textures") or []}
    out["instances"] = {p: mi_info(p) for p in args.get("instances") or []}
    folder = args["folder"]
    pk = sorted(set(x.split(".")[0] for x in EAL.list_assets(folder, recursive=True, include_folder=False)))
    out["folder_packages"] = pk
    out["numbered_copies"] = [p for p in pk if p.rsplit("_", 1)[-1].isdigit()]
elif op == "stage":
    placed = []
    for f in args["figures"]:
        for lab in (f["label"], f["label"] + " base"):
            old = by_label(lab, required=False)
            if old is not None:
                actors_sub.destroy_actor(old)
        loc = u.Vector(*[float(x) for x in f["location"]])
        rot = u.Rotator(roll=0.0, pitch=0.0, yaw=float(f["yaw"]))
        sc = u.Vector(float(f["scale"]), float(f["scale"]), float(f["scale"]))
        b = actors_sub.spawn_actor_from_class(u.StaticMeshActor, loc, rot)
        bc = b.static_mesh_component
        bc.set_mobility(u.ComponentMobility.MOVABLE)
        bc.set_static_mesh(load(f["base"]))
        for i in range(bc.get_num_materials()):
            bc.set_material(i, load(f["base_material"]))
        bc.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        b.set_actor_scale3d(sc)
        b.set_actor_label(f["label"] + " base")
        a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, loc, rot)
        comp = a.skeletal_mesh_component
        comp.set_skinned_asset_and_update(load(f["mesh"]))
        for i in range(comp.get_num_materials()):
            comp.set_material(i, load(f["material"]))
        comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        a.set_actor_scale3d(sc)
        a.set_actor_label(f["label"])
        bb = load(f["base"]).get_bounding_box()
        placed.append({"label": f["label"], "location": v3(a.get_actor_location()),
                       "yaw": round(a.get_actor_rotation().yaw, 3), "scale": v3(a.get_actor_scale3d(), 5),
                       "materials": [m.get_path_name().split(".")[0] for m in comp.get_materials() if m],
                       "base_materials": [m.get_path_name().split(".")[0] for m in bc.get_materials() if m],
                       "base_top_z": round(loc.z + bb.max.z * float(f["scale"]), 3),
                       "base_bottom_z": round(loc.z + bb.min.z * float(f["scale"]), 3),
                       "bones": int(comp.get_num_bones())})
    out["placed"] = placed
elif op == "pose":
    posed = []
    for f in args["figures"]:
        old = by_label(f["label"])
        loc, rot, sc = old.get_actor_location(), old.get_actor_rotation(), old.get_actor_scale3d()
        mesh = old.skeletal_mesh_component.get_skinned_asset()
        mats = list(old.skeletal_mesh_component.get_materials())
        actors_sub.destroy_actor(old)
        a = actors_sub.spawn_actor_from_class(u.SkeletalMeshActor, loc, rot)
        comp = a.skeletal_mesh_component
        comp.set_skinned_asset_and_update(mesh)
        for i, m in enumerate(mats):
            if m:
                comp.set_material(i, m)
        comp.set_collision_enabled(u.CollisionEnabled.NO_COLLISION)
        a.set_actor_scale3d(sc)
        a.set_actor_label(f["label"])
        comp.set_update_animation_in_editor(True)
        anim = load(f["anim"])
        comp.override_animation_data(anim, False, False, float(f["time"]), 0.0)
        posed.append({"label": f["label"], "anim": f["anim"], "time": float(f["time"]),
                      "play_length": round(float(anim.get_play_length()), 4),
                      "same_skeleton": anim.get_editor_property("skeleton") == mesh.get_editor_property("skeleton")})
    out["posed"] = posed
elif op == "probe":
    res = {}
    for label in args["figures"]:
        a = by_label(label)
        comp = a.skeletal_mesh_component
        rec = {"position_read_back": round(comp.get_position(), 4), "bones": {}}
        for i in range(comp.get_num_bones()):
            n = comp.get_bone_name(i)
            rec["bones"][str(n)] = v3(comp.get_socket_location(n))
        try:
            dm = u.DynamicMesh()
            opts = u.GeometryScriptCopyMeshFromComponentOptions()
            _dm, xf, outcome = u.GeometryScript_SceneUtils.copy_mesh_from_component(comp, dm, opts, True)
            box = u.GeometryScript_MeshQueries.get_mesh_bounding_box(dm)
            rec["skinned_bounds_world"] = {"min": v3(box.min), "max": v3(box.max), "outcome": str(outcome)}
        except Exception as exc:  # noqa: BLE001
            rec["skinned_bounds_world"] = {"error": "%s: %s" % (type(exc).__name__, exc)}
        base = by_label(label + " base", required=False)
        if base is not None:
            bmin, bmax = base.get_actor_bounds(False)[0], base.get_actor_bounds(False)[1]
            rec["base_bounds_origin_extent"] = [v3(bmin), v3(bmax)]
        res[label] = rec
    out["probe"] = res
elif op == "cleanup":
    u.get_editor_subsystem(u.LevelEditorSubsystem).eject_pilot_level_actor()
    gone = []
    for a in list(actors_sub.get_all_level_actors()):
        lab = a.get_actor_label()
        if lab.startswith(args["prefix"]):
            actors_sub.destroy_actor(a)
            gone.append(lab)
    out["destroyed"] = gone
else:
    raise RuntimeError("unknown op %s" % op)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
