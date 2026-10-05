"""Verify the imported game audio inside UE (card AUC-U06):

    UnrealEditor-Cmd.exe <uproject> -run=pythonscript -script="tools/audio/ue_verify_audio.py <manifest.json>"

For every manifest entry: the SoundWave loads, its looping flag matches, the duration is > 0. Logs one AUDIO-VERIFY
line per problem and a summary through unreal.log and <manifest>-verify.json.
"""
import json
import sys

import unreal


def main(path):
    items = json.load(open(path, encoding="utf-8"))
    bad = 0
    loops = 0
    details = []
    for it in items:
        obj = f"{it['dest']}/{it['name']}"
        wave = unreal.EditorAssetLibrary.load_asset(obj)
        if not wave:
            bad += 1
            unreal.log_warning(f"AUDIO-VERIFY missing {obj}")
            details.append(f"missing {obj}")
            continue
        looping = bool(wave.get_editor_property("looping"))
        if it.get("loop"):
            loops += 1
        if looping != bool(it.get("loop")):
            bad += 1
            unreal.log_warning(f"AUDIO-VERIFY looping={int(looping)} want={int(bool(it.get('loop')))} {obj}")
            details.append(f"looping={int(looping)} {obj}")
        if wave.get_editor_property("duration") <= 0:
            bad += 1
            unreal.log_warning(f"AUDIO-VERIFY duration=0 {obj}")
            details.append(f"duration=0 {obj}")
    unreal.log(f"AUDIO-VERIFY summary total={len(items)} loops={loops} problems={bad}")
    # the commandlet log does not always keep Python output: the report also goes next to the manifest
    with open(path.replace(".json", "-verify.json"), "w", encoding="utf-8") as fh:
        json.dump({"total": len(items), "loops": loops, "problems": bad, "details": details}, fh, indent=1)


main(sys.argv[-1])
