"""UE editor Python task (LIVE editor via review/ue_live.py run_task): the H2Anim clip-preview mesh ("carrier",
/Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>, spec ue.mesh_for_preview) on the hero's canonical skeleton (F145).

ARGS: {"out", "op": "state" | "refresh", "mesh": "/Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>",
       "skeleton": "/Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>_Skeleton",
       "fbx": <abs SK_<Hero>_H2.fbx> and "fbx_sha256": <hex> (refresh only)}

state    read only: exists, skeleton, source files of the import data, the sha stamp (package metadata tag
         UM_SourceFbxSha256, written by refresh and by canonical_skeleton.py), bounds (origin, extent, bottom/top z)
         and the LOD0 vertex count.
refresh  re-imports the carrier from `fbx` onto the EXISTING canonical skeleton (legacy FbxFactory, the options of
         canonical_skeleton.py + options.skeleton + replace_existing; the skeleton is never re-created), stamps
         fbx_sha256 into the carrier's metadata and saves ONLY the carrier. The skeleton's reference pose is read before
         and after: a change is an error (nothing is saved then). A missing carrier is imported onto the skeleton.
Why (pilot 2026-10-14, F145): canonical_skeleton.py is idempotent by the skeleton's existence, so after a model rework
the carrier kept the old geometry and every h2anim_ue.py frames / measure call posed the old mesh (Ancient Leshen r3:
the crow on the right forearm). Port of the pilot's scratch task evidence/stage7a-20261014/tasks/refresh_carrier.py.
refresh only accepts meshes under /Game/PipelineCandidates/<Hero>/Rig/ (state reads any skeletal mesh).
"""
import json

import unreal as u

TAG = "UM_SourceFbxSha256"
args = ARGS  # noqa: F821 - injected by ue_py/_run.py
op = args["op"]
mesh_pkg, skel_pkg = args["mesh"], args["skeleton"]
if op == "refresh":
    for p in (mesh_pkg, skel_pkg):
        if not p.startswith("/Game/PipelineCandidates/") or "/Rig/" not in p or ".." in p:
            raise RuntimeError("refusing a preview mesh / skeleton outside /Game/PipelineCandidates/<Hero>/Rig: %s" % p)
EAL = u.EditorAssetLibrary
ELS = u.EditorLoadingAndSavingUtils


def dirty():
    return sorted(str(p.get_name()) for p in ELS.get_dirty_content_packages()) + \
        sorted(str(p.get_name()) for p in ELS.get_dirty_map_packages())


def ref_pose(skel):
    pose = u.AnimPoseExtensions.get_reference_pose(skel)
    res = {}
    for n in u.AnimPoseExtensions.get_bone_names(pose):
        t = u.AnimPoseExtensions.get_ref_bone_pose(pose, n, u.AnimPoseSpaces.WORLD).translation
        res[str(n)] = [round(t.x, 4), round(t.y, 4), round(t.z, 4)]
    return res


def state():
    rec = {"mesh": mesh_pkg, "skeleton_expected": skel_pkg, "exists": bool(EAL.does_asset_exist(mesh_pkg)),
           "skeleton_exists": bool(EAL.does_asset_exist(skel_pkg))}
    if not rec["exists"]:
        return rec
    mesh = u.load_asset(mesh_pkg)
    skel = mesh.get_editor_property("skeleton")
    rec["skeleton"] = skel.get_path_name().split(".")[0] if skel else None
    aid = mesh.get_editor_property("asset_import_data")
    rec["source_files"] = [str(f).replace("\\", "/") for f in aid.extract_filenames()] if aid else []
    rec["sha_stamp"] = str(EAL.get_metadata_tag(mesh, TAG) or "") or None
    b = mesh.get_bounds()
    rec["bounds_origin"] = [round(b.origin.x, 3), round(b.origin.y, 3), round(b.origin.z, 3)]
    rec["bounds_extent"] = [round(b.box_extent.x, 3), round(b.box_extent.y, 3), round(b.box_extent.z, 3)]
    rec["bottom_z"] = round(b.origin.z - b.box_extent.z, 3)
    rec["top_z"] = round(b.origin.z + b.box_extent.z, 3)
    try:
        rec["vertices_lod0"] = int(u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem).get_num_verts(mesh, 0))
    except Exception as exc:  # noqa: BLE001 - optional read-back
        rec["vertices_lod0"] = "n/a: %s" % exc
    return rec


out = {"op": op, "mesh": mesh_pkg, "skeleton": skel_pkg, "dirty_before": dirty(), "before": state()}
if op == "refresh":
    if not out["before"]["skeleton_exists"]:
        raise RuntimeError("canonical skeleton %s is missing: run h2anim_ue.py skeleton first" % skel_pkg)
    if out["before"]["exists"] and out["before"].get("skeleton") != skel_pkg:
        raise RuntimeError("preview mesh %s is on %s, not on the canonical skeleton %s"
                           % (mesh_pkg, out["before"].get("skeleton"), skel_pkg))
    skel = u.load_asset(skel_pkg)
    out["ref_pose_before"] = ref_pose(skel)
    o = u.FbxImportUI()
    o.set_editor_property("automated_import_should_detect_type", False)
    o.set_editor_property("import_mesh", True)
    o.set_editor_property("import_as_skeletal", True)
    o.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_SKELETAL_MESH)
    o.set_editor_property("original_import_type", u.FBXImportType.FBXIT_SKELETAL_MESH)
    o.set_editor_property("skeleton", skel)
    o.set_editor_property("import_materials", False)
    o.set_editor_property("import_textures", False)
    o.set_editor_property("import_animations", False)
    o.set_editor_property("create_physics_asset", False)
    d = o.get_editor_property("skeletal_mesh_import_data")
    d.set_editor_property("normal_import_method", u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)
    d.set_editor_property("import_uniform_scale", 1.0)
    try:
        d.set_editor_property("import_morph_targets", False)
        d.set_editor_property("build_nanite", False)
    except Exception:  # noqa: BLE001 - optional properties
        pass
    folder, name = mesh_pkg.rsplit("/", 1)
    t = u.AssetImportTask()
    t.set_editor_property("filename", args["fbx"])
    t.set_editor_property("destination_path", folder)
    t.set_editor_property("destination_name", name)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", False)
    t.set_editor_property("factory", u.FbxFactory())
    t.set_editor_property("options", o)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    out["imported"] = [str(x) for x in t.get_editor_property("imported_object_paths")]
    mesh = u.load_asset(mesh_pkg)
    if mesh is None:
        raise RuntimeError("re-import produced no mesh %s (%s)" % (mesh_pkg, out["imported"]))
    skel_after = mesh.get_editor_property("skeleton")
    if not skel_after or skel_after.get_path_name().split(".")[0] != skel_pkg:
        raise RuntimeError("re-import moved the preview mesh to %s" % (skel_after.get_path_name() if skel_after else None))
    out["ref_pose_after"] = ref_pose(u.load_asset(skel_pkg))
    out["ref_pose_equal"] = out["ref_pose_before"] == out["ref_pose_after"]
    if not out["ref_pose_equal"]:
        raise RuntimeError("re-import changed the reference pose of %s; nothing saved" % skel_pkg)
    EAL.set_metadata_tag(mesh, TAG, args["fbx_sha256"])
    out["dirty_after_import"] = dirty()
    out["skeleton_dirty_after_import"] = skel_pkg in out["dirty_after_import"]
    out["saved"] = bool(EAL.save_asset(mesh_pkg, only_if_is_dirty=False))
    out["dirty_after_save"] = dirty()
    out["after"] = state()
elif op != "state":
    raise RuntimeError("unknown op %s" % op)
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
u.log("TRIPO_UE_PY_OK preview_mesh %s" % op)
