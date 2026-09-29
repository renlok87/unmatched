"""UE editor Python task (LIVE editor via review/ue_live.py run_task): canonical hero skeleton (wave 5c, H2Anim).

ARGS: {"out": ..., "fbx": <abs SK_<Hero>_H2.fbx>, "folder": "/Game/PipelineCandidates/<Hero>/Rig",
       "mesh_name": "SK_<Hero>"}

Creates /Game/PipelineCandidates/<Hero>/Rig/SK_<Hero>_Skeleton by importing the hero's H2 skeletal FBX (UM_FBX_v1,
face +X) once as the carrier mesh SK_<Hero> (legacy FbxFactory, the same options as the CLI's UE_PY_IMPORT_FBX: no
materials, textures, animations or physics asset, ImportNormals, uniform scale 1.0, Nanite off). The legacy importer
names the new skeleton <mesh>_Skeleton, so the canonical name needs no rename (no redirector).
Idempotent: when the skeleton already exists nothing is imported or saved (a canonical skeleton is referenced by the
meshes and clips of the hero; deleting it would break them) and only its reference pose is reported.
The carrier mesh (grey default material) stays next to the skeleton as its preview mesh and as the pose carrier for
clip previews of heroes without an imported H2 mesh (Medusa, Harpy). Saves only the two new assets.
Only folders under /Game/PipelineCandidates/ ending in /Rig are accepted.
"""
import json

import unreal as u

args = ARGS  # noqa: F821 - injected by ue_py/_run.py
folder = args["folder"].rstrip("/")
if not folder.startswith("/Game/PipelineCandidates/") or not folder.endswith("/Rig") or ".." in folder:
    raise RuntimeError("refusing a canonical skeleton outside /Game/PipelineCandidates/<Hero>/Rig: %s" % folder)
mesh_name = args["mesh_name"]
mesh_pkg = "%s/%s" % (folder, mesh_name)
skel_pkg = "%s/%s_Skeleton" % (folder, mesh_name)
out = {"folder": folder, "mesh": mesh_pkg, "skeleton": skel_pkg, "fbx": args["fbx"]}
EAL = u.EditorAssetLibrary
if EAL.does_asset_exist(skel_pkg):
    out["created"] = False
    out["note"] = "skeleton already exists: nothing imported or saved"
else:
    if EAL.does_asset_exist(mesh_pkg):
        raise RuntimeError("carrier mesh %s exists without its skeleton; refusing to overwrite" % mesh_pkg)
    o = u.FbxImportUI()
    o.set_editor_property("automated_import_should_detect_type", False)
    o.set_editor_property("import_mesh", True)
    o.set_editor_property("import_as_skeletal", True)
    o.set_editor_property("mesh_type_to_import", u.FBXImportType.FBXIT_SKELETAL_MESH)
    o.set_editor_property("original_import_type", u.FBXImportType.FBXIT_SKELETAL_MESH)
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
    t = u.AssetImportTask()
    t.set_editor_property("filename", args["fbx"])
    t.set_editor_property("destination_path", folder)
    t.set_editor_property("destination_name", mesh_name)
    t.set_editor_property("replace_existing", False)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", False)
    t.set_editor_property("factory", u.FbxFactory())
    t.set_editor_property("options", o)
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([t])
    out["imported"] = [str(x) for x in t.get_editor_property("imported_object_paths")]
    mesh = u.load_asset(mesh_pkg)
    if mesh is None:
        raise RuntimeError("carrier import produced no mesh %s (%s)" % (mesh_pkg, out["imported"]))
    skel = mesh.get_editor_property("skeleton")
    out["skeleton_read_back"] = skel.get_path_name() if skel else None
    if not skel or skel.get_path_name().split(".")[0] != skel_pkg:
        raise RuntimeError("the importer created %s, expected %s" % (out["skeleton_read_back"], skel_pkg))
    aid = mesh.get_editor_property("asset_import_data")
    out["asset_import_data_class"] = aid.get_class().get_name() if aid else None
    out["saved"] = [bool(EAL.save_asset(p, only_if_is_dirty=False)) for p in (mesh_pkg, skel_pkg)]
    out["created"] = True
skel = u.load_asset(skel_pkg)
pose = u.AnimPoseExtensions.get_reference_pose(skel)
names = [str(n) for n in u.AnimPoseExtensions.get_bone_names(pose)]
comp = {}
for n in names:
    tr = u.AnimPoseExtensions.get_ref_bone_pose(pose, n, u.AnimPoseSpaces.WORLD).translation
    comp[n] = [round(tr.x, 4), round(tr.y, 4), round(tr.z, 4)]
out["bones_in_order"] = names
out["bone0"] = names[0] if names else None
out["ref_component_uu"] = comp
out["class"] = skel.get_class().get_name()
with open(args["out"], "w", encoding="utf-8", newline="\n") as handle:
    handle.write(json.dumps(out, indent=1, sort_keys=True) + "\n")
u.log("TRIPO_UE_PY_OK canonical_skeleton")
