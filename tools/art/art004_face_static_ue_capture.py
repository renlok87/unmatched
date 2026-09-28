"""Compare a frozen Blender Medusa pose with the UE skeletal import in ART005H.

This probe imports into ignored /Game/ArtTests and moves the existing skeletal
actor only in memory. It never saves or modifies the ART005H level.
"""

import json
import math
import os
import traceback
from pathlib import Path

import unreal as u


ROOT = Path(__file__).resolve().parents[2]
SKELETAL = os.environ.get("ART004_FACE_SKELETAL", "0") == "1"
USE_PRODUCTION = os.environ.get("ART004_FACE_USE_PRODUCTION", "0") == "1"
if USE_PRODUCTION and not SKELETAL:
    raise ValueError("ART004_FACE_USE_PRODUCTION requires skeletal probe")
FRONT_ONLY = os.environ.get("ART004_FACE_FRONT_ONLY", "0") == "1"
FACE_SLOT = os.environ.get("ART004_FACE_SLOT", "0") == "1"
RESTORE_NORMALS = os.environ.get("ART004_FACE_RESTORE_NORMALS", "0") == "1"
NECK_BACK = os.environ.get("ART004_FACE_NECK_BACK", "0") == "1"
CROWN_PROBE = os.environ.get("ART004_FACE_CROWN_PROBE", "0") == "1"
HEAD_TILT_PROBE = os.environ.get("ART004_FACE_HEAD_TILT_PROBE", "0") == "1"
NORMAL_IMPORT = os.environ.get("ART004_FACE_NORMAL_IMPORT", "import")
if NORMAL_IMPORT not in {"import", "compute"} or (NORMAL_IMPORT != "import" and not RESTORE_NORMALS):
    raise ValueError("ART004_FACE_NORMAL_IMPORT must be import or compute on restored-normal skeletal probe")
if FACE_SLOT and (FRONT_ONLY or USE_PRODUCTION or not SKELETAL):
    raise ValueError("Face-slot probe needs a separate skeletal test import")
if RESTORE_NORMALS and (FRONT_ONLY or USE_PRODUCTION or not SKELETAL):
    raise ValueError("Restored normals need a separate full-flip skeletal test import")
if NECK_BACK and not (FACE_SLOT and RESTORE_NORMALS and SKELETAL):
    raise ValueError("Rear-neck correction requires restored normals and the face slot")
if CROWN_PROBE and not NECK_BACK:
    raise ValueError("Crown probe requires the corrected v2 face-and-neck path")
if HEAD_TILT_PROBE and (not NECK_BACK or CROWN_PROBE):
    raise ValueError("Head tilt probe requires v2 face and neck without crown spread")
FLIP_HEAD = os.environ.get("ART004_FACE_FLIP_HEAD", "0") == "1"
CLEAR_NORMALS = FLIP_HEAD and os.environ.get("ART004_FACE_CLEAR_NORMALS", "0") == "1"
TWO_SIDED = os.environ.get("ART004_FACE_TWO_SIDED", "0") == "1"
if FACE_SLOT and RESTORE_NORMALS and TWO_SIDED:
    raise ValueError("Corrected face-slot geometry should use a one-sided probe")
if SKELETAL:
    name = ("SK_Medusa_FaceFixNormalsSlotNeck" if NECK_BACK else
            "SK_Medusa_FaceFixNormalsSlot" if FACE_SLOT and RESTORE_NORMALS else
            "SK_Medusa_FaceSlot" if FACE_SLOT else
            "SK_Medusa_FaceFixNormals" if RESTORE_NORMALS else
            "SK_Medusa_FaceFrontOnly" if FRONT_ONLY else "SK_Medusa_FaceFix")
else:
    name = ("SM_Medusa_FlippedHeadRecalc" if CLEAR_NORMALS else
            "SM_Medusa_FlippedHead" if FLIP_HEAD else "SM_Medusa_FrozenIdle")
FBX = ROOT / "unreal/Unmatched/Artifacts/ART004Face" / (name + ".fbx")
if NECK_BACK:
    FBX = ROOT / "blender/ASSET-MEDUSA-001/variants/face-section-neck-v2/SK_Medusa_FaceSectionNeck_v2.fbx"
elif FACE_SLOT and RESTORE_NORMALS:
    FBX = ROOT / "blender/ASSET-MEDUSA-001/variants/face-section-v1/SK_Medusa_FaceSection_v1.fbx"
if CROWN_PROBE:
    name = "SK_Medusa_CrownSpreadProbe"
    FBX = ROOT / "unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_CrownSpreadProbe.fbx"
if HEAD_TILT_PROBE:
    name = "SK_Medusa_HeadTiltProbe"
    FBX = ROOT / "unreal/Unmatched/Artifacts/ART004Face/SK_Medusa_HeadTiltProbe.fbx"
UNLIT = os.environ.get("ART004_FACE_UNLIT", "0") == "1"
UNLIT_SINGLE = UNLIT and os.environ.get("ART004_FACE_UNLIT_SINGLE", "0") == "1"
UNLIT_ALL = os.environ.get("ART004_FACE_UNLIT_ALL", "0") == "1"
if UNLIT_ALL and not (FACE_SLOT and RESTORE_NORMALS and UNLIT_SINGLE):
    raise ValueError("One-sided unlit-all probe requires corrected two-slot skeletal mesh")
NO_NORMAL = os.environ.get("ART004_FACE_NO_NORMAL", "0") == "1"
FACE_LIFT = float(os.environ.get("ART004_FACE_LIFT", "0"))
if not 0 <= FACE_LIFT <= 1:
    raise ValueError("ART004_FACE_LIFT is a diagnostic factor from 0 to 1")
FACE_AMBIENT = float(os.environ.get("ART004_FACE_AMBIENT", "0"))
if not 0 <= FACE_AMBIENT <= .2 or (FACE_AMBIENT and FACE_LIFT):
    raise ValueError("ART004_FACE_AMBIENT is 0..0.2 and excludes FACE_LIFT")
FACE_FLAT_NORMAL = os.environ.get("ART004_FACE_FLAT_NORMAL", "0") == "1"
NO_SHADOW = os.environ.get("ART004_FACE_NO_SHADOW", "0") == "1"
FRONT_FILL = os.environ.get("ART004_FACE_FRONT_FILL", "0") == "1"
LOCAL_FILL = FRONT_FILL and os.environ.get("ART004_FACE_LOCAL_FILL", "0") == "1"
LOCAL_FILL_INTENSITY = float(os.environ.get("ART004_FACE_LOCAL_INTENSITY", "40"))
if LOCAL_FILL and not 0 < LOCAL_FILL_INTENSITY <= 100:
    raise ValueError("Local fill intensity is a diagnostic value in (0, 100]")
VIEW = os.environ.get("ART004_FACE_VIEW", "front")
if VIEW not in {"front", "rear", "k1", "d10-k1", "d10-k2"}:
    raise ValueError("ART004_FACE_VIEW must be front, rear, k1, d10-k1, or d10-k2")
ADD_BASE = os.environ.get("ART004_FACE_ADD_BASE", "0") == "1"
if ADD_BASE and not (SKELETAL and NECK_BACK):
    raise ValueError("The isolated base composition requires the v2 skeletal candidate")
D10_DISTANCE = float(os.environ.get("ART004_FACE_D10_DISTANCE", "550"))
if not 200 <= D10_DISTANCE <= 1000:
    raise ValueError("ART004_FACE_D10_DISTANCE must be 200..1000 uu")
LIGHT_PROFILE = os.environ.get("ART004_FACE_LIGHT_PROFILE", "cobble")
LEVELS = {
    "cobble": "/Game/ArtTests/ART005H/L_ART005H_CornerReview",
    "forest-probe": "/Game/ArtTests/ART005I/L_ART005I_ForestReferenceLight",
    "paddock-probe": "/Game/ArtTests/ART005I/L_ART005I_PaddockReferenceLight",
}
if LIGHT_PROFILE not in LEVELS:
    raise ValueError("ART004_FACE_LIGHT_PROFILE must be cobble, forest-probe, or paddock-probe")
REPOSITION_AMBIENT = os.environ.get("ART004_FACE_REPOSITION_AMBIENT", "0") == "1"
AMBIENT_Y = float(os.environ.get("ART004_FACE_AMBIENT_Y", "300"))
AMBIENT_Z = float(os.environ.get("ART004_FACE_AMBIENT_Z", "350"))
AMBIENT_SCALE = float(os.environ.get("ART004_FACE_AMBIENT_SCALE", "1"))
if REPOSITION_AMBIENT and not (-500 <= AMBIENT_Y <= 500 and 100 <= AMBIENT_Z <= 800
                               and .1 <= AMBIENT_SCALE <= 2):
    raise ValueError("Diagnostic ambient position or scale is out of range")
MATERIAL_MODE = ("unlit-all" if UNLIT_ALL else "unlit-single" if UNLIT_SINGLE else "unlit") if UNLIT else (
    "no-normal" if NO_NORMAL else ("twosided" if TWO_SIDED else "static"))
if SKELETAL:
    mesh_mode = ("skeletal-production-" if USE_PRODUCTION else
                 "skeletal-restorednormals-faceslot-neck-" if NECK_BACK else
                 "skeletal-restorednormals-faceslot-" if FACE_SLOT and RESTORE_NORMALS else
                 "skeletal-faceslot-" if FACE_SLOT else
                 "skeletal-restorednormals-" if RESTORE_NORMALS else
                 "skeletal-frontonly-" if FRONT_ONLY else "skeletal-")
else:
    mesh_mode = "flippedhead-recalc-" if CLEAR_NORMALS else "flippedhead-" if FLIP_HEAD else ""
MODE = mesh_mode + MATERIAL_MODE + (
            "-noshadow" if NO_SHADOW else "") + (
            f"-localfill{round(LOCAL_FILL_INTENSITY):03d}" if LOCAL_FILL else
            "-frontfill" if FRONT_FILL else "") + (
            f"-lift{round(FACE_LIFT * 1000):03d}" if FACE_LIFT else "") + (
            f"-ambient{round(FACE_AMBIENT * 1000):03d}" if FACE_AMBIENT else "") + (
            "-flatnormal" if FACE_FLAT_NORMAL else "") + (
            f"-frontambient-y{round(AMBIENT_Y)}-z{round(AMBIENT_Z)}-s{round(AMBIENT_SCALE * 100)}"
            if REPOSITION_AMBIENT else "") + (
            "-" + VIEW if VIEW != "front" else "") + (
            "-base" if ADD_BASE else "") + (
            f"-d{round(D10_DISTANCE)}" if VIEW == "d10-k2" else "") + (
            "-computenormals" if NORMAL_IMPORT == "compute" else "") + (
            "-" + LIGHT_PROFILE if LIGHT_PROFILE != "cobble" else "")
if CROWN_PROBE:
    MODE += "-crownprobe"
if HEAD_TILT_PROBE:
    MODE += "-headtiltprobe"
OUTPUT = ROOT / f"docs/game-design/evidence/ART-004/medusa-frozen-{MODE}-ue-editor-2026-09-28.png"
REPORT = ROOT / f"unreal/Unmatched/Artifacts/ART004Face/ue-{MODE}-report.json"
if CROWN_PROBE or HEAD_TILT_PROBE:
    OUTPUT = ROOT / f"unreal/Unmatched/Artifacts/ART004Face/medusa-{MODE}.png"
LEVEL = LEVELS[LIGHT_PROFILE]
DEST = "/Game/ArtTests/ART004Face/Meshes"
NAME = name
if NORMAL_IMPORT == "compute":
    NAME += "_ComputeNormals"
MATERIAL = "/Game/ART004/Medusa/Materials/MI_Medusa_Blue"


def basecolor_texture():
    texture = u.load_asset("/Game/ART004/Medusa/Textures/T_Medusa_BC")
    if texture:
        return texture
    path = "/Game/ArtTests/ART004Face/Textures"
    name = "T_Medusa_BC_Probe"
    texture = u.load_asset(path + "/" + name)
    if not texture:
        task = u.AssetImportTask()
        task.filename = str(ROOT / "blender/ASSET-MEDUSA-001/textures/T_Medusa_Atlas_BC.png")
        task.destination_path = path
        task.destination_name = name
        task.automated = True
        task.replace_existing = True
        task.save = True
        u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        texture = u.load_asset(path + "/" + name)
    if not texture:
        raise RuntimeError("Cannot import diagnostic Medusa BaseColor")
    texture.set_editor_property("srgb", True)
    u.EditorAssetLibrary.save_loaded_asset(texture)
    return texture


def comparison_material():
    if NO_NORMAL:
        path = "/Game/ArtTests/ART004Face/Materials"
        material = u.load_asset(path + "/M_Medusa_NoNormalProbe")
        if not material:
            material = u.AssetToolsHelpers.get_asset_tools().create_asset(
                "M_Medusa_NoNormalProbe", path, u.Material, u.MaterialFactoryNew())
        texture = basecolor_texture()
        if not material or not texture:
            raise RuntimeError("Missing no-normal material or imported BaseColor texture")
        material.set_editor_property("two_sided", False)
        mel = u.MaterialEditingLibrary
        mel.delete_all_material_expressions(material)
        sample = mel.create_material_expression(material, u.MaterialExpressionTextureSample, -300, 0)
        sample.set_editor_property("texture", texture)
        mel.connect_material_property(sample, "RGB", u.MaterialProperty.MP_BASE_COLOR)
        rough = mel.create_material_expression(material, u.MaterialExpressionConstant, -300, 180)
        rough.set_editor_property("r", .8)
        mel.connect_material_property(rough, "", u.MaterialProperty.MP_ROUGHNESS)
        mel.recompile_material(material)
        u.EditorAssetLibrary.save_loaded_asset(material)
        return material
    if UNLIT:
        path = "/Game/ArtTests/ART004Face/Materials"
        name = "M_Medusa_UnlitSingleProbe" if UNLIT_SINGLE else "M_Medusa_UnlitProbe"
        material = u.load_asset(path + "/" + name)
        if not material:
            material = u.AssetToolsHelpers.get_asset_tools().create_asset(
                name, path, u.Material, u.MaterialFactoryNew())
        texture = basecolor_texture()
        if not material or not texture:
            raise RuntimeError("Missing unlit material or imported BaseColor texture")
        material.set_editor_property("two_sided", not UNLIT_SINGLE)
        material.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
        mel = u.MaterialEditingLibrary
        mel.delete_all_material_expressions(material)
        sample = mel.create_material_expression(material, u.MaterialExpressionTextureSample, -300, 0)
        sample.set_editor_property("texture", texture)
        mel.connect_material_property(sample, "RGB", u.MaterialProperty.MP_EMISSIVE_COLOR)
        mel.recompile_material(material)
        u.EditorAssetLibrary.save_loaded_asset(material)
        return material
    if not TWO_SIDED and not FACE_AMBIENT and not FACE_LIFT and not FACE_FLAT_NORMAL:
        material = u.load_asset(MATERIAL)
        if not material:
            raise RuntimeError("Missing imported Medusa material: " + MATERIAL)
        return material
    source = "/Game/ART004/Medusa/Materials/M_Medusa_Atlas"
    path = "/Game/ArtTests/ART004Face/Materials"
    suffix = (f"Lift{round(FACE_LIFT * 1000):03d}" if FACE_LIFT else "") + (
        f"Ambient{round(FACE_AMBIENT * 1000):03d}" if FACE_AMBIENT else "") + (
        "FlatNormal" if FACE_FLAT_NORMAL else "")
    parent_path = path + "/M_Medusa_" + ("TwoSided" if TWO_SIDED else "SingleSided") + suffix + "Probe"
    parent = u.load_asset(parent_path)
    created = not parent
    if not parent:
        parent = u.EditorAssetLibrary.duplicate_asset(source, parent_path)
    if not parent:
        raise RuntimeError("Cannot duplicate Medusa parent material")
    parent.set_editor_property("two_sided", TWO_SIDED)
    if FACE_FLAT_NORMAL and created:
        flat = u.MaterialEditingLibrary.create_material_expression(
            parent, u.MaterialExpressionConstant3Vector, -450, 760)
        flat.set_editor_property("constant", u.LinearColor(0, 0, 1, 1))
        u.MaterialEditingLibrary.connect_material_property(
            flat, "", u.MaterialProperty.MP_NORMAL)
    if FACE_LIFT and created:
        mel = u.MaterialEditingLibrary
        texture = basecolor_texture()
        if not texture:
            raise RuntimeError("Missing Medusa BaseColor for face lift")
        sample = mel.create_material_expression(parent, u.MaterialExpressionTextureSample, -450, 900)
        sample.set_editor_property("texture", texture)
        factor = mel.create_material_expression(parent, u.MaterialExpressionConstant, -450, 1100)
        factor.set_editor_property("r", FACE_LIFT)
        multiply = mel.create_material_expression(parent, u.MaterialExpressionMultiply, -150, 1000)
        mel.connect_material_expressions(sample, "RGB", multiply, "A")
        mel.connect_material_expressions(factor, "", multiply, "B")
        mel.connect_material_property(multiply, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    if FACE_AMBIENT and created:
        ambient = u.MaterialEditingLibrary.create_material_expression(
            parent, u.MaterialExpressionConstant3Vector, -450, 1000)
        ambient.set_editor_property("constant", u.LinearColor(
            FACE_AMBIENT, FACE_AMBIENT, FACE_AMBIENT, 1))
        u.MaterialEditingLibrary.connect_material_property(
            ambient, "", u.MaterialProperty.MP_EMISSIVE_COLOR)
    u.MaterialEditingLibrary.recompile_material(parent)
    u.EditorAssetLibrary.save_loaded_asset(parent)
    instance_name = "MI_Medusa_" + ("TwoSided" if TWO_SIDED else "SingleSided") + suffix + "BlueProbe"
    instance_path = path + "/" + instance_name
    instance = u.load_asset(instance_path)
    if not instance:
        instance = u.AssetToolsHelpers.get_asset_tools().create_asset(
            instance_name, path, u.MaterialInstanceConstant,
            u.MaterialInstanceConstantFactoryNew())
    if not instance:
        raise RuntimeError("Cannot create two-sided test instance")
    u.MaterialEditingLibrary.set_material_instance_parent(instance, parent)
    u.MaterialEditingLibrary.set_material_instance_vector_parameter_value(
        instance, "TeamColor", u.LinearColor(.72, .85, 1.0, 1.0))
    u.EditorAssetLibrary.save_loaded_asset(instance)
    return instance


def import_mesh():
    if USE_PRODUCTION:
        mesh = u.load_asset("/Game/ART004/Medusa/Meshes/SK_Medusa_Atlas")
        if not mesh:
            raise RuntimeError("Missing production Medusa skeletal mesh")
        material = comparison_material()
        slots = len(mesh.get_editor_property("materials"))
        return mesh, slots, [material] * slots
    if not FBX.is_file():
        raise RuntimeError("Run art004_face_static_export.py in Blender first")
    task = u.AssetImportTask()
    task.filename = str(FBX)
    task.destination_path = DEST
    task.destination_name = NAME
    task.automated = True
    task.replace_existing = True
    task.save = True
    options = u.FbxImportUI()
    options.import_mesh = True
    options.import_as_skeletal = SKELETAL
    options.mesh_type_to_import = (u.FBXImportType.FBXIT_SKELETAL_MESH if SKELETAL
                                   else u.FBXImportType.FBXIT_STATIC_MESH)
    options.import_materials = False
    options.import_textures = False
    if SKELETAL:
        options.import_animations = False
        options.skeletal_mesh_import_data.import_uniform_scale = 1.0
        if RESTORE_NORMALS:
            options.skeletal_mesh_import_data.normal_import_method = (
                u.FBXNormalImportMethod.FBXNIM_COMPUTE_NORMALS if NORMAL_IMPORT == "compute"
                else u.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS_AND_TANGENTS)
    else:
        options.static_mesh_import_data.combine_meshes = True
        options.static_mesh_import_data.import_uniform_scale = 1.0
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset(DEST + "/" + NAME)
    if not mesh:
        raise RuntimeError("Diagnostic import failed: " + str(FBX))
    material = comparison_material()
    if SKELETAL:
        materials = mesh.get_editor_property("materials")
        slots = len(materials)
        if FACE_SLOT:
            if slots != 2 or TWO_SIDED == RESTORE_NORMALS:
                raise RuntimeError("Face-slot test requires two slots and matching winding/culling")
            if UNLIT_ALL:
                assigned = [material] * slots
            else:
                normal = u.load_asset(MATERIAL)
                if not normal:
                    raise RuntimeError("Missing original one-sided Medusa material")
                assigned = [normal, material]
        else:
            assigned = [material] * slots
        for slot, assigned_material in zip(materials, assigned):
            slot.set_editor_property("material_interface", assigned_material)
        mesh.set_editor_property("materials", materials)
    else:
        slots = len(mesh.get_editor_property("static_materials"))
        assigned = [material] * slots
        for index in range(slots):
            mesh.set_material(index, material)
    u.EditorAssetLibrary.save_loaded_asset(mesh)
    return mesh, slots, assigned


def import_isolated_base():
    source = ROOT / "blender/ASSET-MEDUSA-001/export/SM_Medusa_Base.fbx"
    if not source.is_file():
        raise RuntimeError("Missing original separate Medusa base FBX")
    task = u.AssetImportTask()
    task.filename = str(source)
    task.destination_path = DEST
    task.destination_name = "SM_Medusa_Base_FaceProbe"
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
    options.static_mesh_import_data.auto_generate_collision = False
    task.options = options
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    mesh = u.load_asset(DEST + "/SM_Medusa_Base_FaceProbe")
    if not mesh:
        raise RuntimeError("Isolated Medusa base import failed")
    bounds = mesh.get_bounding_box()
    size = (bounds.max.x - bounds.min.x, bounds.max.y - bounds.min.y,
            bounds.max.z - bounds.min.z)
    if any(abs(value - expected) > .5 for value, expected in zip(size, (30, 30, 6))):
        raise RuntimeError(f"Unexpected separate Medusa base dimensions: {size}")
    material = u.load_asset(MATERIAL)
    if not material:
        raise RuntimeError("Missing original Medusa material for base")
    mesh.set_material(0, material)
    u.EditorAssetLibrary.save_loaded_asset(mesh)
    return mesh, size


class CaptureJob:
    def __init__(self):
        self.frame = 0
        self.handle = None

    def finish(self):
        if self.handle is not None:
            u.unregister_slate_post_tick_callback(self.handle)
            self.handle = None
        u.EditorPythonScripting.set_keep_python_script_alive(False)

    def tick(self, _delta_seconds):
        try:
            self.frame += 1
            if self.frame == 90:
                self.capture.capture_scene()
            elif self.frame == 96:
                u.RenderingLibrary.export_render_target(self.world, self.target,
                                                        str(OUTPUT.parent), OUTPUT.name)
                if not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
                    raise RuntimeError("Static comparison PNG missing")
                REPORT.parent.mkdir(parents=True, exist_ok=True)
                REPORT.write_text(json.dumps({
                    "level": LEVEL, "light_profile": LIGHT_PROFILE,
                    "mesh": self.mesh.get_path_name(),
                    "materials": [material.get_path_name() for material in self.materials],
                    "material_slots": self.slots,
                    "two_sided": TWO_SIDED or (UNLIT and not UNLIT_SINGLE),
                    "unlit": UNLIT, "unlit_all": UNLIT_ALL, "no_normal": NO_NORMAL,
                    "skeletal": SKELETAL,
                    "use_production": USE_PRODUCTION,
                    "front_only": FRONT_ONLY,
                    "face_slot": FACE_SLOT,
                    "neck_back": NECK_BACK,
                    "crown_probe": CROWN_PROBE,
                    "head_tilt_probe": HEAD_TILT_PROBE,
                    "restore_normals": RESTORE_NORMALS,
                    "normal_import": NORMAL_IMPORT,
                    "flipped_head": FLIP_HEAD,
                    "clear_custom_normals": CLEAR_NORMALS,
                    "no_shadow": NO_SHADOW,
                    "front_fill": FRONT_FILL,
                    "local_fill": LOCAL_FILL,
                    "local_fill_intensity": LOCAL_FILL_INTENSITY if LOCAL_FILL else None,
                    "face_lift": FACE_LIFT,
                    "face_ambient": FACE_AMBIENT,
                    "face_flat_normal": FACE_FLAT_NORMAL,
                    "reposition_ambient": REPOSITION_AMBIENT,
                    "ambient_probe": [AMBIENT_Y, AMBIENT_Z, AMBIENT_SCALE]
                    if REPOSITION_AMBIENT else None,
                    "output": str(OUTPUT), "scene_saved": False,
                    "camera_location": list(self.camera_location),
                    "camera_target": list(self.camera_target), "fov": 35,
                    "add_base": ADD_BASE,
                    "base_mesh": self.base_mesh.get_path_name() if ADD_BASE else None,
                    "base_dimensions_uu": list(self.base_dimensions) if ADD_BASE else None,
                    "d10_distance_uu": D10_DISTANCE if VIEW == "d10-k2" else None,
                }, indent=2) + "\n", encoding="utf-8")
                u.log("ART004_FACE_STATIC_UE_CAPTURE_COMPLETE " + str(OUTPUT))
                self.finish()
        except Exception:
            u.log_error("ART004_FACE_STATIC_UE_CAPTURE_FAILED\n" + traceback.format_exc())
            self.finish()

    def start(self):
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        self.mesh, self.slots, self.materials = import_mesh()
        if not u.get_editor_subsystem(u.LevelEditorSubsystem).load_level(LEVEL):
            raise RuntimeError("Missing review level " + LEVEL)
        self.world = u.EditorLevelLibrary.get_editor_world()
        u.SystemLibrary.execute_console_command(self.world, "t.MaxFPS 30")
        u.SystemLibrary.execute_console_command(self.world, "r.DefaultFeature.AutoExposure 0")
        u.SystemLibrary.execute_console_command(self.world, "r.EyeAdaptationQuality 0")
        actors = u.get_editor_subsystem(u.EditorActorSubsystem).get_all_level_actors()
        if REPOSITION_AMBIENT:
            ambient = [actor for actor in actors if actor.get_actor_label() ==
                       "ART005 neutral readability fill - review only"]
            if len(ambient) != 1:
                raise RuntimeError("Expected one neutral ambient fill actor")
            ambient[0].set_actor_location(u.Vector(0, AMBIENT_Y, AMBIENT_Z), False, False)
            current = ambient[0].light_component.get_editor_property("intensity")
            ambient[0].light_component.set_editor_property("intensity", current * AMBIENT_SCALE)
        figures = [actor for actor in actors
                   if actor.get_actor_label() == "ART004 Medusa - animation review"]
        if len(figures) != 1:
            raise RuntimeError("Expected one Medusa, found " + str(len(figures)))
        location = figures[0].get_actor_location()
        figures[0].set_actor_location(u.Vector(10000, 10000, 0), False, False)
        if ADD_BASE:
            self.base_mesh, self.base_dimensions = import_isolated_base()
            base_actor = u.EditorLevelLibrary.spawn_actor_from_class(
                u.StaticMeshActor, location, u.Rotator(0, 0, 0))
            base_actor.set_actor_label("ART004 temporary separate base - v2 composition")
            base_actor.static_mesh_component.set_static_mesh(self.base_mesh)
            base_actor.static_mesh_component.set_collision_profile_name("NoCollision")
        if SKELETAL:
            probe_actor = u.EditorLevelLibrary.spawn_actor_from_class(
                u.SkeletalMeshActor, location, u.Rotator(0, 0, 0))
            probe_actor.set_actor_label("ART004 temporary skeletal face probe")
            probe_actor.skeletal_mesh_component.set_editor_property("skeletal_mesh", self.mesh)
            for index in range(self.slots):
                probe_actor.skeletal_mesh_component.set_material(index, self.materials[index])
            if NO_SHADOW:
                probe_actor.skeletal_mesh_component.set_editor_property("cast_shadow", False)
        else:
            probe_actor = u.EditorLevelLibrary.spawn_actor_from_class(
                u.StaticMeshActor, location, u.Rotator(0, 0, 0))
            probe_actor.set_actor_label("ART004 temporary frozen-body probe")
            probe_actor.static_mesh_component.set_static_mesh(self.mesh)
            if NO_SHADOW:
                probe_actor.static_mesh_component.set_editor_property("cast_shadow", False)
        if FRONT_FILL:
            fill = u.EditorLevelLibrary.spawn_actor_from_class(
                u.PointLight, u.Vector(-30, 0, 85) if LOCAL_FILL else
                u.Vector(-70, 105, 145))
            fill.set_actor_label("ART004 temporary face fill - diagnostic")
            fill.light_component.set_editor_property(
                "intensity", LOCAL_FILL_INTENSITY if LOCAL_FILL else 600.0)
            fill.light_component.set_editor_property("attenuation_radius", 140.0 if LOCAL_FILL else 330.0)
            fill.light_component.set_editor_property("cast_shadows", False)
            fill.light_component.set_editor_property("mobility", u.ComponentMobility.MOVABLE)
        self.camera_location = {
            "front": (-70, 105, 105), "rear": (70, -205, 105),
            "k1": (0, -1032.4, 1474.4),
        }.get(VIEW)
        self.camera_target = (0, 0, 0) if VIEW == "k1" else (0, -50, 29)
        if VIEW == "d10-k1":
            half_h = math.tan(math.radians(35 / 2))
            half_v = half_h / (16 / 9)
            need_v = (300 * math.sin(math.radians(55)) + 60) / half_v
            need_h = (250 + 60) / half_h
            distance = max(need_v, need_h) * 1.12
            self.camera_location = (0, distance * math.cos(math.radians(55)),
                                    distance * math.sin(math.radians(55)))
            self.camera_target = (0, 0, 0)
        elif VIEW == "d10-k2":
            self.camera_location = (location.x,
                                    location.y + D10_DISTANCE * math.cos(math.radians(55)),
                                    29 + D10_DISTANCE * math.sin(math.radians(55)))
            self.camera_target = (location.x, location.y, 29)
        origin = u.Vector(*self.camera_location)
        target = u.Vector(*self.camera_target)
        camera = u.EditorLevelLibrary.spawn_actor_from_class(
            u.SceneCapture2D, origin, u.MathLibrary.find_look_at_rotation(origin, target))
        camera.set_actor_label("ART004 temporary static capture")
        self.target = u.TextureRenderTarget2D()
        self.target.set_editor_property("render_target_format", u.TextureRenderTargetFormat.RTF_RGBA8)
        self.target.set_editor_property("size_x", 1920)
        self.target.set_editor_property("size_y", 1080)
        self.capture = camera.capture_component2d
        self.capture.set_editor_property("texture_target", self.target)
        self.capture.set_editor_property("capture_source", u.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        self.capture.set_editor_property("fov_angle", 35.0)
        self.capture.set_editor_property("capture_every_frame", False)
        self.capture.set_editor_property("capture_on_movement", False)
        u.EditorPythonScripting.set_keep_python_script_alive(True)
        self.handle = u.register_slate_post_tick_callback(self.tick)
        u.log("ART004_FACE_STATIC_UE_CAPTURE_WAITING")


JOB = CaptureJob()
JOB.start()
