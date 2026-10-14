"""UE task (ue_live run_task): refresh the H2Anim pose carrier /Game/PipelineCandidates/<Hero>/Rig/SK_<Hero> from a new
SK_<Hero>_H2.fbx (same rig, changed geometry) on the EXISTING canonical skeleton; the skeleton itself is not re-created.

Why: h2anim_ue.py skeleton is idempotent by the skeleton's existence (canonical_skeleton.py), so after a model rework the
carrier keeps the old geometry and every h2anim_ue frames/measure call poses the old mesh (Ancient Leshen r3: the
right-forearm crow moved 4.25 cm back / 1.5 cm up). Same import options as canonical_skeleton.py (legacy FbxFactory,
no materials / textures / animations / physics asset, ImportNormals, uniform scale 1.0, Nanite off) + options.skeleton =
the canonical skeleton + replace_existing. Saves only the carrier; reports the skeleton's reference pose before and
after (must be equal) and the dirty packages.

ARGS: {"out", "fbx": <abs SK_<Hero>_H2.fbx>, "mesh": "/Game/.../Rig/SK_<Hero>", "skeleton": "/Game/.../Rig/SK_<Hero>_Skeleton"}
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
mesh_pkg, skel_pkg = args["mesh"], args["skeleton"]
if not mesh_pkg.startswith("/Game/PipelineCandidates/") or "/Rig/" not in mesh_pkg:
    raise RuntimeError("refusing a carrier outside /Game/PipelineCandidates/<Hero>/Rig: %s" % mesh_pkg)
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


def mesh_info(mesh):
    aid = mesh.get_editor_property("asset_import_data")
    files = list(aid.extract_filenames()) if aid else []
    b = mesh.get_bounds()
    info = {"source_files": [str(f) for f in files],
            "bounds_origin": [round(b.origin.x, 3), round(b.origin.y, 3), round(b.origin.z, 3)],
            "bounds_extent": [round(b.box_extent.x, 3), round(b.box_extent.y, 3), round(b.box_extent.z, 3)],
            "skeleton": mesh.get_editor_property("skeleton").get_path_name()}
    try:
        info["source_file_hash"] = [str(x.file_hash) for x in aid.get_editor_property("source_data").get_editor_property("source_files")]
    except Exception as exc:  # noqa: BLE001 - optional read-back
        info["source_file_hash"] = "n/a: %s" % exc
    try:
        info["vertices_lod0"] = int(u.SkeletalMeshEditorSubsystem().get_num_verts(mesh, 0)) \
            if hasattr(u, "SkeletalMeshEditorSubsystem") else None
    except Exception as exc:  # noqa: BLE001
        info["vertices_lod0"] = "n/a: %s" % exc
    return info


out = {"mesh": mesh_pkg, "skeleton": skel_pkg, "fbx": args["fbx"], "dirty_before": dirty()}
if not EAL.does_asset_exist(skel_pkg) or not EAL.does_asset_exist(mesh_pkg):
    raise RuntimeError("carrier or skeleton missing: %s %s" % (mesh_pkg, skel_pkg))
skel = u.load_asset(skel_pkg)
mesh = u.load_asset(mesh_pkg)
out["before"] = mesh_info(mesh)
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
skel_after = mesh.get_editor_property("skeleton")
if not skel_after or skel_after.get_path_name().split(".")[0] != skel_pkg:
    raise RuntimeError("carrier re-import changed the skeleton: %s" % (skel_after.get_path_name() if skel_after else None))
out["after"] = mesh_info(mesh)
out["ref_pose_after"] = ref_pose(u.load_asset(skel_pkg))
out["ref_pose_equal"] = out["ref_pose_before"] == out["ref_pose_after"]
out["dirty_after_import"] = dirty()
out["saved"] = bool(EAL.save_asset(mesh_pkg, only_if_is_dirty=False))
out["dirty_after_save"] = dirty()
with open(args["out"], "w", encoding="utf-8", newline="\n") as h:
    json.dump(out, h, indent=1)
