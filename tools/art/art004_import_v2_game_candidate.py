"""Import a saved Medusa visual candidate with a persisted UE skeleton.

This does not import or approve animation clips. The assets have explicit
Candidate names so the existing production Medusa is left untouched.
Run in UnrealEditor-Cmd after ART004_MATERIAL_ONLY has built the PBR assets
in /Game/ArtPreview/Medusa. This namespace does not overwrite production.
"""

import hashlib
import json
import os
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-MEDUSA-001"
VARIANT = os.environ.get("ART004_GAME_VARIANT", "face-neck-v2")
if VARIANT not in {"face-neck-v2", "head-tilt-v3"}:
    raise ValueError("ART004_GAME_VARIANT must be face-neck-v2 or head-tilt-v3")
FBX = SOURCE / ("variants/head-tilt-v3/SK_Medusa_HeadTilt_v3.fbx" if VARIANT == "head-tilt-v3"
                else "variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx")
BASE_FBX = SOURCE / "export/SM_Medusa_Base.fbx"
DEST = "/Game/ArtPreview/Medusa"
MESH_DIR = DEST + "/Meshes"
MESH_NAME = ("SK_Medusa_HeadTilt_v3Candidate" if VARIANT == "head-tilt-v3"
             else "SK_Medusa_FaceNeck_v2Candidate")
BASE_NAME = "SM_Medusa_Base_v2Candidate"
BLUE_PATH = DEST + "/Materials/MI_Medusa_Blue"
RED_PATH = DEST + "/Materials/MI_Medusa_Red"
REPORT = ROOT / ("docs/game-design/evidence/ART-004/head-tilt-v3-game-import-report.json"
                 if VARIANT == "head-tilt-v3"
                 else "docs/game-design/evidence/ART-004/v2-game-import-report.json")
EXPECTED_FBX_SHA256 = ("b9cea0fe05071b07732b8d72ecc75b074c366bc665679c378cd4e397e1f822a2"
                       if VARIANT == "head-tilt-v3"
                       else "bd125c6bbeb2559b28f6fc4908a1790e0d05fd572b128bd9188c2daeea046592")


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def import_asset(source, name, skeletal):
    task = u.AssetImportTask()
    task.filename = str(source)
    task.destination_path = MESH_DIR
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = skeletal
    options.mesh_type_to_import = (u.FBXImportType.FBXIT_SKELETAL_MESH if skeletal
                                   else u.FBXImportType.FBXIT_STATIC_MESH)
    options.import_materials = False
    options.import_textures = False
    if skeletal:
        options.import_animations = False
        options.skeletal_mesh_import_data.import_uniform_scale = 1.0
        options.skeletal_mesh_import_data.normal_import_method = (
            u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    else:
        options.static_mesh_import_data.combine_meshes = True
        options.static_mesh_import_data.auto_generate_collision = False
        options.static_mesh_import_data.import_uniform_scale = 1.0
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    asset = u.load_asset(MESH_DIR + "/" + name)
    require(asset is not None, "FBX import failed: " + name)
    return asset


def bone_names(mesh):
    names = ["root"]
    pending = ["root"]
    while pending:
        for child in mesh.get_bone_children(pending.pop()):
            value = str(child)
            names.append(value)
            pending.append(value)
    return sorted(names)


def replace_sockets(mesh):
    while mesh.num_sockets():
        socket = mesh.get_socket_by_index(0)
        require(mesh.remove_socket(str(socket.get_editor_property("socket_name"))),
                "Could not remove stale candidate socket")
    for name, bone, offset in (("Weapon", "weapon", (0, 0, 0)),
                               ("Head", "head", (0, 0, 4))):
        socket = u.SkeletalMeshSocket(outer=mesh, name=name)
        socket.set_socket_parent(mesh, bone)
        socket.set_socket_local_transform(u.Transform(
            u.Vector(*offset), u.Rotator(0, 0, 0), u.Vector(1, 1, 1)))
        mesh.add_socket(socket)
        old = str(socket.get_editor_property("socket_name"))
        require(mesh.rename_socket(old, name), "Could not name socket " + name)
    require(mesh.num_sockets() == 2, "Candidate has incorrect socket count")


def main():
    require(FBX.is_file() and BASE_FBX.is_file(), "Saved candidate or base FBX missing")
    require(hashlib.sha256(FBX.read_bytes()).hexdigest() == EXPECTED_FBX_SHA256,
            "Saved v2 FBX changed; review before importing")
    blue = u.load_asset(BLUE_PATH)
    red = u.load_asset(RED_PATH)
    require(blue is not None and red is not None, "Run ART004_MATERIAL_ONLY first")

    mesh = import_asset(FBX, MESH_NAME, True)
    imported_slots = mesh.get_editor_property("materials")
    require(len(imported_slots) == 2, "v2 candidate should have exactly two body slots")
    # UE 5.8 Python returns SkeletalMaterial struct values; mutating each
    # returned struct in-place does not persist the material interface.
    slots = [u.SkeletalMaterial(material_interface=blue,
                                material_slot_name=slot.get_editor_property("material_slot_name"))
             for slot in imported_slots]
    mesh.set_editor_property("materials", slots)
    require(all(slot.get_editor_property("material_interface") == blue
                for slot in mesh.get_editor_property("materials")),
            "Candidate PBR material assignment did not stick")
    expected = sorted(("root", "hips", "spine", "head", "arm_upper_L", "arm_lower_L",
                       "hand_L", "weapon", "arm_upper_R", "arm_lower_R", "hand_R",
                       "leg_upper_L", "leg_lower_L", "foot_L", "leg_upper_R",
                       "leg_lower_R", "foot_R"))
    actual = bone_names(mesh)
    require(actual == expected, "Unexpected candidate bones: " + str(actual))
    replace_sockets(mesh)
    skeleton = mesh.get_editor_property("skeleton")
    require(skeleton is not None, "UE did not create a candidate Skeleton")
    require(u.EditorAssetLibrary.save_loaded_asset(skeleton), "Could not persist Skeleton")
    require(u.EditorAssetLibrary.save_loaded_asset(mesh), "Could not persist SkeletalMesh")
    skeleton_path = skeleton.get_path_name()
    require(u.EditorAssetLibrary.does_asset_exist(skeleton_path),
            "Saved Skeleton package is missing")

    # v3 keeps the already-saved v2 pedestal byte-for-byte. Reimporting it
    # would dirty an unrelated tracked UE package for no visual change.
    base = (u.load_asset(MESH_DIR + "/" + BASE_NAME) if VARIANT == "head-tilt-v3"
            else import_asset(BASE_FBX, BASE_NAME, False))
    require(base is not None, "Candidate base is missing")
    bounds = base.get_bounding_box()
    dimensions = [bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y,
                  bounds.max.z - bounds.min.z]
    require(all(abs(value - expected) < .5 for value, expected in
                zip(dimensions, (30, 30, 6))), "Base size changed: " + str(dimensions))
    if VARIANT == "face-neck-v2":
        base.set_material(0, blue)
        require(u.EditorAssetLibrary.save_loaded_asset(base), "Could not persist base")

    # A new process must be able to load the skeleton by its package path.
    require(u.load_asset(skeleton_path) is not None, "Skeleton cannot be reloaded")
    result = {
        "status": "isolated_game_candidate_not_art_acceptance",
        "variant": VARIANT,
        "source_fbx_sha256": EXPECTED_FBX_SHA256,
        "base_fbx_sha256": hashlib.sha256(BASE_FBX.read_bytes()).hexdigest(),
        "skeletal_mesh": mesh.get_path_name(),
        "skeleton": skeleton_path,
        "base": base.get_path_name(),
        "materials": [blue.get_path_name(), red.get_path_name()],
        "body_material_slots": len(slots),
        "bones": actual,
        "sockets": [str(mesh.get_socket_by_index(i).get_editor_property("socket_name"))
                    for i in range(mesh.num_sockets())],
        "base_dimensions_uu": [round(v, 4) for v in dimensions],
        "animations_imported": False,
        "approval": "Only technical import. Visual K1-K3, gameplay, animation and packaged QA remain open.",
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("ART004_GAME_CANDIDATE_IMPORT_OK " + str(REPORT))


main()
