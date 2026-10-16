# SEL (docs/game-design/select-screens/05-HIPOLY-COMPARE.md): import the Tripo H2 high-poly sources of the
# select-screen heroes, cleaned by tools/art/showcase/clean_hipoly.py (no phantoms, no Tripo base), as ONE combined Nanite
# static mesh each, with their own glTF materials, into
# /Game/PipelineCandidates/<Key>/HP/. Run headless:
#   UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script="<this file>" -unattended -nosplash -nullrhi
import os
import unreal

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
# 2026-10-16: King Arthur from the regenerated H2 4f059621 (side slot LEFT, no phantoms), his own Tripo materials; Medusa
# shows the game look (import_hipoly_lookdev.py) and is not imported here
SOURCES = {
    "KingArthur": "art/pipeline-candidates/ASSET-KING-ARTHUR-001/20261016-h2-tripo/source/king-arthur-h2-tripo-4f059621-tex8k-pbr-clean.glb",
}


def log(msg):
    unreal.log_warning("SEL-HP " + msg)


def make_pipeline():
    pipe = unreal.InterchangeGenericAssetsPipeline()
    mesh = pipe.get_editor_property("mesh_pipeline")
    combine = [n for n in dir(mesh) if "ombine" in n]
    log("combine props: %s" % combine)
    for name in combine:
        if "behavior" in name:
            enum_type = type(mesh.get_editor_property(name))
            members = [m for m in dir(enum_type) if m.isupper()]
            log("combine enum %s members %s" % (enum_type.__name__, members))
            pick = next((m for m in members if "ALL" in m or "COMBINE" in m and "NO" not in m), None)
            if pick:
                mesh.set_editor_property(name, getattr(enum_type, pick))
                log("combine -> %s" % pick)
    for prop, val in (("import_static_meshes", True), ("import_skeletal_meshes", False),
                      ("build_nanite", True), ("generate_lightmap_u_vs", False)):
        try:
            mesh.set_editor_property(prop, val)
        except Exception as e:  # property names vary between engine versions
            log("mesh_pipeline.%s skipped: %s" % (prop, e))
    try:
        common = pipe.get_editor_property("common_meshes_properties")
        common.set_editor_property("force_all_mesh_as_type", unreal.InterchangeForceMeshType.IFMT_STATIC_MESH)
    except Exception as e:
        log("force static skipped: %s" % e)
    try:
        anim = pipe.get_editor_property("animation_pipeline")
        anim.set_editor_property("import_animations", False)
    except Exception as e:
        log("anim skipped: %s" % e)
    return pipe


def import_one(key, rel):
    src = os.path.join(REPO, rel)
    dest = "/Game/PipelineCandidates/%s/HP2" % key
    if not os.path.isfile(src):
        log("missing %s (run tools/art/showcase/clean_hipoly.py first)" % src)
        return
    if unreal.EditorAssetLibrary.does_directory_exist(dest):
        unreal.EditorAssetLibrary.delete_directory(dest)  # the previous (uncleaned) import
    params = unreal.ImportAssetParameters()
    params.is_automated = True
    params.replace_existing = True
    pipe = make_pipeline()
    params.set_editor_property("override_pipelines", [unreal.SoftObjectPath(pipe.get_path_name())])
    source = unreal.InterchangeManager.create_source_data(src)
    mgr = unreal.InterchangeManager.get_interchange_manager_scripted()
    ok = mgr.import_asset(dest, source, params)
    log("import %s -> %s ok=%s" % (key, dest, ok))
    assets = unreal.EditorAssetLibrary.list_assets(dest, recursive=True)
    meshes = [a for a in assets if isinstance(unreal.load_asset(a), unreal.StaticMesh)]
    log("%s assets=%d staticMeshes=%s" % (key, len(assets), meshes))
    for a in meshes:
        sm = unreal.load_asset(a)
        try:
            nanite = sm.get_editor_property("nanite_settings")
            nanite.set_editor_property("enabled", True)
            sm.set_editor_property("nanite_settings", nanite)
        except Exception as e:
            log("nanite set failed %s" % e)
        b = sm.get_bounding_box()
        log("%s mesh=%s tris=%s bounds=%s..%s" % (key, a, sm.get_num_triangles(0), b.min, b.max))
        unreal.EditorAssetLibrary.save_asset(a)
    unreal.EditorAssetLibrary.save_directory(dest)


for k, r in SOURCES.items():
    import_one(k, r)
log("done")
