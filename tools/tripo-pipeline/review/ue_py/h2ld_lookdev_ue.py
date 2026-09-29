"""UE editor Python task (LIVE editor via review/ue_live.py run_task): look-dev helpers of LD-<hero>-ue.

ARGS: {"out": ..., "op": ..., ...}; driven by review/h2ld_ue_lookdev.py.

  swap_mesh  {"label", "mesh"}  the skeletal mesh asset of a temporary review figure (in memory: H2 <-> H2LD share the
             skeleton contract, UV0 and geometry, so the same actor, cell and yaw show both)
  mid        {"label", "slot", "parent", "scalars", "vectors"}  a transient MaterialInstanceDynamic on the actor's
             component (never an asset; e.g. H2 v1 without dye for the concept comparison)
  verify     {"textures": [...], "skeletal": [...]}  asset-registry tags of textures (source/pixel format, size,
             filter) and UV sets / triangles of skeletal meshes (GeometryScript copy)
  reimport   {"asset", "source_file", "settings"}  re-import one texture over itself (AssetImportTask, replace
             existing: MIs keep their reference), then set its properties; used by the look-dev loop for the hero LUT
             before the final clean CLI run
Nothing here saves a package except `reimport` (the asset is owned by the look-dev run).
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
op = args["op"]
actors_sub = u.get_editor_subsystem(u.EditorActorSubsystem)
out = {"op": op}


def obj(path):
    return path if "." in path.rsplit("/", 1)[-1] else "%s.%s" % (path, path.rsplit("/", 1)[-1])


def load(path):
    asset = u.load_asset(obj(path))
    if asset is None:
        raise RuntimeError("asset not found: %s" % path)
    return asset


def by_label(label):
    hits = [a for a in actors_sub.get_all_level_actors() if a.get_actor_label() == label]
    if len(hits) != 1:
        raise RuntimeError("actor %r: %d matches" % (label, len(hits)))
    return hits[0]


def comp_of(a):
    return a.static_mesh_component if isinstance(a, u.StaticMeshActor) else a.skeletal_mesh_component


if op == "swap_mesh":
    a = by_label(args["label"])
    comp = a.skeletal_mesh_component
    comp.set_skinned_asset_and_update(load(args["mesh"]))
    out["mesh"] = comp.get_skinned_asset().get_path_name()
elif op == "mid":
    a = by_label(args["label"])
    comp = comp_of(a)
    mid = comp.create_dynamic_material_instance(int(args.get("slot", 0)), load(args["parent"]))
    for k, v in sorted((args.get("scalars") or {}).items()):
        mid.set_scalar_parameter_value(k, float(v))
    for k, v in sorted((args.get("vectors") or {}).items()):
        mid.set_vector_parameter_value(k, u.LinearColor(*[float(x) for x in v]))
    out["mid"] = {"parent": args["parent"], "scalars": args.get("scalars"), "vectors": args.get("vectors"),
                  "class": mid.get_class().get_name()}
elif op == "verify":
    ar = u.AssetRegistryHelpers.get_asset_registry()
    out["textures"] = {}
    for p in args.get("textures") or []:
        ad = ar.get_asset_by_object_path(obj(p))
        tags = {}
        for k in ("Format", "SourceFormat", "Dimensions", "CompressionSettings", "Filter", "SRGB", "MipGenSettings",
                  "NeverStream", "LODGroup"):
            try:
                v = ad.get_tag_value(k)
                tags[k] = None if v is None else str(v)
            except Exception as exc:  # noqa: BLE001
                tags[k] = "n/a (%s)" % type(exc).__name__
        out["textures"][p] = tags
    out["skeletal"] = {}
    for p in args.get("skeletal") or []:
        dm = u.DynamicMesh()
        _dm, outcome = u.GeometryScript_AssetUtils.copy_mesh_from_skeletal_mesh(
            load(p), dm, u.GeometryScriptCopyMeshFromAssetOptions(), u.GeometryScriptMeshReadLOD())
        rec = {"outcome": str(outcome)}
        if "SUCCESS" in str(outcome):
            rec["uv_sets"] = int(u.GeometryScript_MeshQueries.get_num_uv_sets(dm))
            rec["triangles"] = int(u.GeometryScript_MeshQueries.get_num_triangle_i_ds(dm))
        out["skeletal"][p] = rec
elif op == "reimport":
    path = args["asset"]
    folder, name = path.rsplit("/", 1)
    task = u.AssetImportTask()
    task.set_editor_property("filename", args["source_file"])
    task.set_editor_property("destination_path", folder)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("replace_existing_settings", False)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", False)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = load(path)
    for k, v in sorted((args.get("settings") or {}).items()):
        cur = tex.get_editor_property(k)
        if isinstance(v, str) and hasattr(cur, "name"):
            v = getattr(type(cur), v)
        tex.set_editor_property(k, v)
    u.EditorAssetLibrary.save_asset(path, only_if_is_dirty=False)
    out["reimported"] = {"asset": path, "imported_objects": [str(x) for x in task.get_editor_property("imported_object_paths")],
                         "settings": args.get("settings")}
else:
    raise RuntimeError("unknown op %s" % op)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
