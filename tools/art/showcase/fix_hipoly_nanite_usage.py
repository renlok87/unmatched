# 2026-10-21 playtest F7 (docs/game-design/evidence/PLAYTEST-2026-10-21-night): the showcase high-poly meshes are Nanite,
# but their materials lack the Nanite usage flag - the packaged client logs «missing usage flag Nanite» for every slot
# (48 in night 1, 32 in night 2) and the component draws the Nanite FALLBACK mesh (King Arthur 13 558 tris instead of
# 1 788 773, Medusa 15 480 instead of 1 638 982). The editor sets the flag on its own only outside -game.
#
# This script sets the flag where it belongs:
#   /Game/PipelineCandidates/KingArthur/HP2           every UMaterial (Interchange glTF, no common parent): base usage
#   /Game/PipelineCandidates/Medusa/HPLD/Materials    every MaterialInstanceConstant: the MI usage override (UE 5.8),
#                                                      so the master M_UM_Figure_v2 (every game figure) stays untouched
#
# Dry run by default (reports what lacks the flag, saves nothing). --apply sets and saves. Run headless with the
# LiveCoding client and the main checkout's editor closed:
#   UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script="<this file>" -unattended -nosplash -nullrhi
#   UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script="<this file> --apply" -unattended -nosplash -nullrhi
#
# The look of the accepted showcase changes with it (fallback -> full Nanite clusters): AGENTS.md «Hero showcase
# high-poly» asks for a blind before/after review before that becomes the default - run --apply together with it.
import sys

import unreal

APPLY = "--apply" in " ".join(sys.argv)
FOLDERS = {
    "/Game/PipelineCandidates/KingArthur/HP2": "material",
    "/Game/PipelineCandidates/Medusa/HPLD/Materials": "instance",
}


def log(msg):
    unreal.log_warning("SEL-NANITE " + msg)


def main():
    mel = unreal.MaterialEditingLibrary
    eal = unreal.EditorAssetLibrary
    usage = unreal.MaterialUsage.MATUSAGE_NANITE
    total = missing = fixed = 0
    for folder, kind in FOLDERS.items():
        if not eal.does_directory_exist(folder):
            log("missing folder %s" % folder)
            continue
        for path in eal.list_assets(folder, recursive=True, include_folder=False):
            asset = eal.load_asset(path)
            if kind == "material" and not isinstance(asset, unreal.Material):
                continue
            if kind == "instance" and not isinstance(asset, unreal.MaterialInstanceConstant):
                continue
            total += 1
            has = mel.has_material_usage(asset, usage)
            if has:
                continue
            missing += 1
            log("no Nanite usage: %s" % path)
            if not APPLY:
                continue
            if kind == "material":
                mel.set_base_material_usage(asset, usage, True)
            else:
                mel.set_material_usage_override(asset, usage, True, True)
            eal.save_loaded_asset(asset)
            if mel.has_material_usage(asset, usage):
                fixed += 1
            else:
                log("still without the flag after the set: %s" % path)
    log("%s total=%d missing=%d fixed=%d" % ("apply" if APPLY else "dry-run", total, missing, fixed))
    if APPLY:
        log("ok %d/%d" % (total - missing + fixed, total))


main()
