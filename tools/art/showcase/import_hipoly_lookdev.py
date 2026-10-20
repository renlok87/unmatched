# SEL showcase (docs/game-design/select-screens/06-HIPOLY-LOOKDEV.md): import the high-poly with the game look baked by
# tools/art/showcase/hp_lookdev_bake.py into /Game/PipelineCandidates/<Key>/HPLD/:
#   SM_<Key>_HP_Showcase   one Nanite static mesh, one slot per Tripo part (MAT_tripo_part_N)
#   T_<Key>_HP_<part>_<map> BC (sRGB), ORM, MatID (nearest, no mips, exact 8-bit), EdgeMask, TeamAccent, N (OpenGL source,
#                          green flipped to the DirectX convention of the master)
#   MI_<Key>_HP_<part>_<P1|P2> children of the game MIs MI_<Key>_H2LD_<P1|P2> (same master M_UM_Figure_v2, the same LUT,
#                          team colour, dye and accent settings) with the part's maps; UseUV1Metres off (no UV1 on the
#                          high-poly). The mesh slots default to the P1 instances; the showcase swaps them by team.
# Run: UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script="<this file>" -unattended -nosplash -nullrhi
import json
import os
import re

import unreal

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HEROES = {
    "KingArthur": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20261016-hp-showcase",
    "Medusa": "art/pipeline-candidates/ASSET-MEDUSA-001/20261016-hp-showcase",
}
MAP_PARAM = {"BC": "BaseColorTexture", "N": "NormalTexture", "ORM": "ORMTexture", "MatID": "MatIDTexture",
             "EdgeMask": "EdgeMaskTexture", "TeamAccent": "TeamAccentTexture"}
mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary


def log(msg):
    unreal.log_warning("SEL-HPLD " + msg)


def pipeline():
    pipe = unreal.InterchangeGenericAssetsPipeline()
    mesh = pipe.get_editor_property("mesh_pipeline")
    mesh.set_editor_property("combine_static_meshes_behavior", unreal.InterchangeCombineStaticMeshesBehavior.ALL)
    for prop, val in (("import_static_meshes", True), ("import_skeletal_meshes", False), ("build_nanite", True),
                      ("generate_lightmap_u_vs", False)):
        try:
            mesh.set_editor_property(prop, val)
        except Exception as e:  # noqa: BLE001
            log("mesh_pipeline.%s skipped: %s" % (prop, e))
    try:
        pipe.get_editor_property("common_meshes_properties").set_editor_property(
            "force_all_mesh_as_type", unreal.InterchangeForceMeshType.IFMT_STATIC_MESH)
    except Exception as e:  # noqa: BLE001
        log("force static skipped: %s" % e)
    try:
        mp = pipe.get_editor_property("material_pipeline")
        mp.set_editor_property("import_materials", False)
    except Exception as e:  # noqa: BLE001
        log("materials skipped: %s" % e)
    return pipe


def import_file(src, dest, pipe=None):
    params = unreal.ImportAssetParameters()
    params.is_automated = True
    params.replace_existing = True
    if pipe is not None:
        params.set_editor_property("override_pipelines", [unreal.SoftObjectPath(pipe.get_path_name())])
    source = unreal.InterchangeManager.create_source_data(src)
    return unreal.InterchangeManager.get_interchange_manager_scripted().import_asset(dest, source, params)


def import_texture(path, dest, name, kind):
    task = unreal.AssetImportTask()
    task.filename = path
    task.destination_path = dest
    task.destination_name = name
    task.automated = True
    task.replace_existing = True
    task.save = False
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    tex = unreal.load_asset("%s/%s" % (dest, name))
    if tex is None:
        log("texture import failed %s" % path)
        return None
    if kind == "BC":
        tex.set_editor_property("srgb", True)
    elif kind == "N":
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("flip_green_channel", True)
    elif kind == "MatID":
        tex.set_editor_property("srgb", False)
        tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
        tex.set_editor_property("filter", unreal.TextureFilter.TF_NEAREST)
        tex.set_editor_property("mip_gen_settings", unreal.TextureMipGenSettings.TMGS_NO_MIPMAPS)
        tex.set_editor_property("never_stream", True)
    else:  # ORM, EdgeMask, TeamAccent: linear data
        tex.set_editor_property("srgb", False)
        if kind in ("EdgeMask", "TeamAccent"):
            tex.set_editor_property("compression_settings", unreal.TextureCompressionSettings.TC_GRAYSCALE)
    eal.save_loaded_asset(tex)
    return tex


def run(key, rel):
    root = os.path.join(REPO, rel)
    dest = "/Game/PipelineCandidates/%s/HPLD" % key
    if eal.does_directory_exist(dest):
        eal.delete_directory(dest)
    fbx = os.path.join(root, "export", "SM_%s_HP_Showcase.fbx" % key)
    import_file(fbx, dest, pipeline())
    meshes = [a for a in eal.list_assets(dest, recursive=False) if isinstance(unreal.load_asset(a), unreal.StaticMesh)]
    if not meshes:
        log("%s: no static mesh imported" % key)
        return
    sm = unreal.load_asset(meshes[0])
    if sm.get_name() != "SM_%s_HP_Showcase" % key:
        eal.rename_asset(meshes[0], "%s/SM_%s_HP_Showcase" % (dest, key))
        sm = unreal.load_asset("%s/SM_%s_HP_Showcase" % (dest, key))
    nanite = sm.get_editor_property("nanite_settings")
    nanite.set_editor_property("enabled", True)
    sm.set_editor_property("nanite_settings", nanite)
    tex_dir = os.path.join(root, "textures")
    report = {"mesh": sm.get_path_name(), "slots": {}}
    stage = "H3LD" if key == "Harpy" else "H2LD"
    for i, slot in enumerate(sm.get_editor_property("static_materials")):
        sname = str(slot.get_editor_property("material_slot_name"))
        m = re.search(r"tripo_part_\d+", sname)
        if not m:
            log("%s: slot %s has no part name" % (key, sname))
            continue
        part = m.group(0)
        texs = {}
        for kind in MAP_PARAM:
            fn = "T_%s_HP_%s_%s.png" % (key, part, "N_gl" if kind == "N" else kind)
            p = os.path.join(tex_dir, fn)
            if os.path.isfile(p):
                texs[kind] = import_texture(p, dest + "/Textures", "T_%s_HP_%s_%s" % (key, part, kind), kind)
        made = {}
        for team in ("P1", "P2"):
            parent = unreal.load_asset("/Game/PipelineCandidates/%s/%s/Materials/MI_%s_%s_%s" % (key, stage, key, stage, team))
            name = "MI_%s_HP_%s_%s" % (key, part, team)
            mi = unreal.AssetToolsHelpers.get_asset_tools().create_asset(name, dest + "/Materials",
                                                                         unreal.MaterialInstanceConstant,
                                                                         unreal.MaterialInstanceConstantFactoryNew())
            mel.set_material_instance_parent(mi, parent)
            for kind, tex in texs.items():
                if tex is not None:
                    mel.set_material_instance_texture_parameter_value(mi, MAP_PARAM[kind], tex)
            try:
                mel.set_material_instance_static_switch_parameter_value(mi, "UseUV1Metres", False)
            except Exception as e:  # noqa: BLE001
                log("UseUV1Metres switch: %s" % e)
            # 2026-10-21 playtest F7: the MI of a Nanite mesh carries the Nanite usage (an override: the master
            # M_UM_Figure_v2 of every game figure stays without it) - else the package draws the fallback mesh
            mel.set_material_usage_override(mi, unreal.MaterialUsage.MATUSAGE_NANITE, True, True)
            mel.update_material_instance(mi)
            eal.save_loaded_asset(mi)
            made[team] = mi
        if "P1" in made:
            sm.set_material(i, made["P1"])
        report["slots"][sname] = {"part": part, "maps": sorted(k for k, v in texs.items() if v)}
    eal.save_loaded_asset(sm)
    eal.save_directory(dest)
    log("%s: %s tris=%d slots=%d" % (key, sm.get_path_name(), sm.get_num_triangles(0), len(report["slots"])))
    with open(os.path.join(root, "reports", "ue-import.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)


for k, r in HEROES.items():
    if os.path.isfile(os.path.join(REPO, r, "export", "SM_%s_HP_Showcase.fbx" % k)):
        run(k, r)
    else:
        log("%s: no export yet" % k)
log("done")
