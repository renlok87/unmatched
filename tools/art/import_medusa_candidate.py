"""Import and verify the Tripo/Blender Medusa candidate in isolated /Game/ART004/Medusa."""

import json
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "blender/ASSET-MEDUSA-001"
EXPORT = SOURCE / "export"
TEXTURES = SOURCE / "textures"
DEST = "/Game/ART004/Medusa"
ANIM_DEST = DEST + "/Animation"
EVIDENCE = SOURCE / "ue-import-result.json"
REPORT = {"destination": DEST, "checks": {}, "assets": {}}


def check(name, passed, detail):
    REPORT["checks"][name] = {"ok": bool(passed), "detail": detail}
    u.log("ART004_MEDUSA %s ok=%s %s" % (name, passed, detail))
    if not passed:
        raise RuntimeError("%s: %s" % (name, detail))


def import_texture(filename, name, kind):
    task = u.AssetImportTask()
    task.filename = str(TEXTURES / filename)
    task.destination_path = DEST + "/Textures"
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = u.load_asset(task.destination_path + "/" + name)
    check("texture_" + kind, bool(texture), str(task.filename))
    if kind == "normal":
        texture.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_NORMALMAP)
        texture.set_editor_property("srgb", False)
        texture.set_editor_property("flip_green_channel", False)
    elif kind == "orm":
        texture.set_editor_property("compression_settings", u.TextureCompressionSettings.TC_MASKS)
        texture.set_editor_property("srgb", False)
    else:
        texture.set_editor_property("srgb", True)
    u.EditorAssetLibrary.save_loaded_asset(texture)
    REPORT["assets"][kind] = texture.get_path_name()
    return texture


def material_sample(mat, texture, parameter, x, y, normal=False):
    mel = u.MaterialEditingLibrary
    sample = mel.create_material_expression(mat, u.MaterialExpressionTextureSampleParameter2D, x, y)
    sample.set_editor_property("parameter_name", parameter)
    sample.set_editor_property("texture", texture)
    if normal:
        sample.set_editor_property("sampler_type", u.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    return sample


def build_material(base, normal, orm):
    path = DEST + "/Materials/M_Medusa_Atlas"
    mat = u.load_asset(path)
    if not mat:
        mat = u.AssetToolsHelpers.get_asset_tools().create_asset(
            "M_Medusa_Atlas", DEST + "/Materials", u.Material, u.MaterialFactoryNew())
    check("material_created", bool(mat), path)
    mel = u.MaterialEditingLibrary
    mel.delete_all_material_expressions(mat)
    bc = material_sample(mat, base, "BaseColorTexture", -800, 0)
    team = mel.create_material_expression(mat, u.MaterialExpressionVectorParameter, -800, 180)
    team.set_editor_property("parameter_name", "TeamColor")
    team.set_editor_property("default_value", u.LinearColor(1, 1, 1, 1))
    multiply = mel.create_material_expression(mat, u.MaterialExpressionMultiply, -480, 60)
    mel.connect_material_expressions(bc, "RGB", multiply, "A")
    mel.connect_material_expressions(team, "", multiply, "B")
    mel.connect_material_property(multiply, "", u.MaterialProperty.MP_BASE_COLOR)
    norm = material_sample(mat, normal, "NormalTexture", -800, 380, normal=True)
    mel.connect_material_property(norm, "RGB", u.MaterialProperty.MP_NORMAL)
    packed = material_sample(mat, orm, "ORMTexture", -800, 640)
    mel.connect_material_property(packed, "R", u.MaterialProperty.MP_AMBIENT_OCCLUSION)
    mel.connect_material_property(packed, "G", u.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(packed, "B", u.MaterialProperty.MP_METALLIC)
    mat.set_editor_property("used_with_skeletal_mesh", True)
    mel.recompile_material(mat)
    u.EditorAssetLibrary.save_loaded_asset(mat)
    REPORT["assets"]["material"] = mat.get_path_name()
    return mat


def team_instance(name, parent, color):
    path = DEST + "/Materials/" + name
    inst = u.load_asset(path)
    if not inst:
        inst = u.AssetToolsHelpers.get_asset_tools().create_asset(
            name, DEST + "/Materials", u.MaterialInstanceConstant, u.MaterialInstanceConstantFactoryNew())
    u.MaterialEditingLibrary.set_material_instance_parent(inst, parent)
    u.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        inst, "TeamColor", u.LinearColor(*color))
    u.EditorAssetLibrary.save_loaded_asset(inst)
    REPORT["assets"][name] = inst.get_path_name()
    return inst


def import_skeletal(material):
    name = "SK_Medusa_Atlas"
    task = u.AssetImportTask()
    task.filename = str(EXPORT / "SK_Medusa.fbx")
    task.destination_path = DEST + "/Meshes"
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = True
    options.mesh_type_to_import = u.FBXImportType.FBXIT_SKELETAL_MESH
    options.import_animations = False
    options.import_materials = False
    options.import_textures = False
    options.skeletal_mesh_import_data.import_uniform_scale = 1.0
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset(task.destination_path + "/" + name)
    check("skeletal_import", bool(mesh), str(task.filename))
    materials = mesh.get_editor_property("materials")
    check("skeletal_material_slots", len(materials) <= 3, str(len(materials)))
    for slot in materials:
        slot.set_editor_property("material_interface", material)
    mesh.set_editor_property("materials", materials)
    u.EditorAssetLibrary.save_loaded_asset(mesh)
    skeleton = mesh.get_editor_property("skeleton")
    check("skeleton", bool(skeleton), skeleton.get_path_name() if skeleton else "missing")
    REPORT["assets"]["skeletal_mesh"] = mesh.get_path_name()
    REPORT["assets"]["skeleton"] = skeleton.get_path_name()
    return mesh, skeleton


def import_base(material):
    name = "SM_Medusa_Base"
    task = u.AssetImportTask()
    task.filename = str(EXPORT / (name + ".fbx"))
    task.destination_path = DEST + "/Meshes"
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = False
    options.mesh_type_to_import = u.FBXImportType.FBXIT_STATIC_MESH
    options.import_materials = False
    options.import_textures = False
    options.static_mesh_import_data.combine_meshes = True
    options.static_mesh_import_data.import_uniform_scale = 1.0
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset(task.destination_path + "/" + name)
    check("base_import", bool(mesh), str(task.filename))
    mesh.set_material(0, material)
    u.EditorAssetLibrary.save_loaded_asset(mesh)
    REPORT["assets"]["base"] = mesh.get_path_name()
    return mesh


def make_socket(mesh, name, bone, offset):
    sock = u.SkeletalMeshSocket(outer=mesh, name=name)
    sock.set_socket_parent(mesh, bone)
    sock.set_socket_local_transform(u.Transform(u.Vector(*offset), u.Rotator(0, 0, 0), u.Vector(1, 1, 1)))
    mesh.add_socket(sock)
    old_name = str(sock.get_editor_property("socket_name"))
    check("rename_socket_" + name, mesh.rename_socket(old_name, name), old_name + " -> " + name)
    u.EditorAssetLibrary.save_loaded_asset(mesh)


def reset_candidate_sockets(mesh):
    # This isolated asset owns only the two sockets below. UE's legacy FBX
    # reimport duplicates sockets; rebuild the exact pair on every run.
    while mesh.num_sockets():
        before = mesh.num_sockets()
        socket = mesh.get_socket_by_index(0)
        name = str(socket.get_editor_property("socket_name"))
        check("remove_socket_" + str(before), mesh.remove_socket(name) and
              mesh.num_sockets() < before, name)
    u.EditorAssetLibrary.save_loaded_asset(mesh)


def bone_names(mesh):
    out, pending = ["root"], ["root"]
    while pending:
        for child in mesh.get_bone_children(pending.pop()):
            out.append(str(child))
            pending.append(str(child))
    return sorted(out)


def import_clip(name, skeleton):
    # The legacy importer creates a throwaway mesh even for animation-only FBX.
    # Remove the exact assets from this isolated candidate before each import.
    for suffix, kind in (("_PhysicsAsset", "PhysicsAsset"), ("", "SkeletalMesh")):
        stale = ANIM_DEST + "/" + name + suffix
        if u.EditorAssetLibrary.does_asset_exist(stale):
            asset = u.load_asset(stale)
            if asset and asset.get_class().get_name() == kind:
                check("delete_legacy_" + name + suffix,
                      u.EditorAssetLibrary.delete_asset(stale), stale)
    task = u.AssetImportTask()
    task.filename = str(EXPORT / (name + ".fbx"))
    task.destination_path = ANIM_DEST
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = False
    options.import_as_skeletal = True
    options.mesh_type_to_import = u.FBXImportType.FBXIT_ANIMATION
    options.import_animations = True
    options.import_materials = False
    options.import_textures = False
    options.set_editor_property("skeleton", skeleton)
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    sequence = None
    for path in u.EditorAssetLibrary.list_assets(task.destination_path, recursive=False):
        if path.rsplit("/", 1)[-1].startswith(name):
            asset = u.load_asset(path)
            if asset and asset.get_class().get_name() == "AnimSequence":
                sequence = asset
                break
    check("clip_" + name, bool(sequence), str(task.get_editor_property("imported_object_paths")))
    check("clip_skeleton_" + name,
          sequence.get_editor_property("skeleton").get_path_name() == skeleton.get_path_name(),
          sequence.get_path_name())
    for suffix, kind in (("_PhysicsAsset", "PhysicsAsset"), ("", "SkeletalMesh")):
        stale = ANIM_DEST + "/" + name + suffix
        if u.EditorAssetLibrary.does_asset_exist(stale):
            asset = u.load_asset(stale)
            if asset and asset.get_class().get_name() == kind:
                check("remove_throwaway_" + name + suffix,
                      u.EditorAssetLibrary.delete_asset(stale), stale)
    REPORT["assets"][name] = sequence.get_path_name()
    return sequence


def main():
    base = import_texture("T_Medusa_Atlas_BC.png", "T_Medusa_BC", "base")
    normal = import_texture("T_Medusa_Atlas_N.png", "T_Medusa_N", "normal")
    orm = import_texture("T_Medusa_Atlas_ORM.png", "T_Medusa_ORM", "orm")
    material = build_material(base, normal, orm)
    team_instance("MI_Medusa_Blue", material, (.72, .85, 1.0, 1))
    team_instance("MI_Medusa_Red", material, (1.0, .76, .70, 1))
    mesh, skeleton = import_skeletal(material)
    base_mesh = import_base(material)
    bounds = mesh.get_bounds()
    base_bounds = base_mesh.get_bounding_box()
    REPORT["bounds_uu"] = {
        "skeletal_min_z": round(bounds.origin.z - bounds.box_extent.z, 3),
        "skeletal_max_z": round(bounds.origin.z + bounds.box_extent.z, 3),
        "base_min_z": round(base_bounds.min.z, 3),
        "base_max_z": round(base_bounds.max.z, 3),
        "base_x": [round(base_bounds.min.x, 3), round(base_bounds.max.x, 3)],
        "base_y": [round(base_bounds.min.y, 3), round(base_bounds.max.y, 3)],
    }
    check("height_55uu", 54 <= REPORT["bounds_uu"]["skeletal_max_z"] <= 56,
          str(REPORT["bounds_uu"]))
    check("base_6uu", 5.9 <= REPORT["bounds_uu"]["base_max_z"] <= 6.1 and
          abs(REPORT["bounds_uu"]["base_min_z"]) < .5, str(REPORT["bounds_uu"]))
    check("base_diameter_30uu",
          all(abs(abs(bound) - 15) < .15 for axis in ("base_x", "base_y")
              for bound in REPORT["bounds_uu"][axis]), str(REPORT["bounds_uu"]))
    expected = sorted(("root", "hips", "spine", "head", "arm_upper_L", "arm_lower_L", "hand_L",
                       "weapon", "arm_upper_R", "arm_lower_R", "hand_R", "leg_upper_L",
                       "leg_lower_L", "foot_L", "leg_upper_R", "leg_lower_R", "foot_R"))
    actual = bone_names(mesh)
    check("bones_17", actual == expected, str(actual))
    reset_candidate_sockets(mesh)
    make_socket(mesh, "Weapon", "weapon", (0, 0, 0))
    make_socket(mesh, "Head", "head", (0, 0, 4))
    sockets = {str(mesh.get_socket_by_index(i).get_editor_property("socket_name")):
               str(mesh.get_socket_by_index(i).get_editor_property("bone_name"))
               for i in range(mesh.num_sockets())}
    check("sockets", mesh.num_sockets() == 2 and sockets == {"Weapon": "weapon", "Head": "head"},
          str(sockets))
    REPORT["clips"] = {}
    for clip in ("Idle", "LungeAttack", "HitReact", "DeathSettle"):
        name = "AM_Medusa_" + clip
        sequence = import_clip(name, skeleton)
        length = sequence.get_play_length()
        REPORT["clips"][clip] = round(length, 4)
        check("clip_length_" + clip, .2 <= length <= 3.0, str(length))
    u.EditorAssetLibrary.save_directory(DEST)
    EVIDENCE.write_text(json.dumps(REPORT, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    u.log("ART004_MEDUSA COMPLETE " + str(EVIDENCE))


main()
