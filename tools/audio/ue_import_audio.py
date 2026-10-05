"""Import the game's audio into UE (card AUC-U06). Runs inside the editor:

    UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script="tools/audio/ue_import_audio.py <manifest.json>"
        -unattended -nosplash -nullrhi

The manifest comes from tools/audio/ue_bank.py: {src, dest, name, loop}. Each WAV (48 kHz / 16 bit) becomes a
SoundWave at dest/name (replaced if it exists); loops get `looping`. Prints one AUDIO-IMPORT line per asset and a
summary; exit code 1 if any import failed.
"""
import json
import sys

import unreal


def main(path):
    items = json.load(open(path, encoding="utf-8"))
    tasks = []
    for it in items:
        t = unreal.AssetImportTask()
        t.set_editor_property("filename", it["src"])
        t.set_editor_property("destination_path", it["dest"])
        t.set_editor_property("destination_name", it["name"])
        t.set_editor_property("automated", True)
        t.set_editor_property("replace_existing", True)
        t.set_editor_property("save", False)
        tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    failed = 0
    for it in items:
        obj_path = f"{it['dest']}/{it['name']}"
        wave = unreal.EditorAssetLibrary.load_asset(obj_path)
        if not wave:
            failed += 1
            print(f"AUDIO-IMPORT fail {obj_path} src={it['src']}")
            continue
        if it.get("loop"):
            wave.set_editor_property("looping", True)
        unreal.EditorAssetLibrary.save_loaded_asset(wave, only_if_is_dirty=False)
        print(f"AUDIO-IMPORT ok {obj_path} loop={int(bool(it.get('loop')))}")
    print(f"AUDIO-IMPORT summary total={len(items)} failed={failed}")
    if failed:
        raise SystemExit(1)


main(sys.argv[-1])
