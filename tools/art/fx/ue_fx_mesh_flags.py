"""VS-6 FX-37 (ВР-VS6-48): the static meshes of the cue effects (/Game/S08/FX/Meshes) are plain, non-Nanite meshes.

SM_FX_VortexRings came in through Interchange with bBuildNanite true; the Nanite mesh behind the vortex put a Nanite
shadow pass (~0.25 ms GPU, render_bench ProfileGPU "Nanite Shadows") into every frame of a packaged client - the pooled
vortex components are registered from the prewarm on. An FX print is translucent: Nanite gives it nothing.

  UnrealEditor-Cmd <uproject> -run=pythonscript -script="tools/art/fx/ue_fx_mesh_flags.py" -unattended -nullrhi
  (add " --check" inside the -script quotes to only report)

Prints one FX_MESH_FLAGS {json} line; ok = every mesh has Nanite off.
"""
from __future__ import annotations

import json
import sys

import unreal as u  # type: ignore

ROOT = "/Game/S08/FX/Meshes"


def nanite_off(mesh, check: bool) -> dict:
    ns = mesh.get_editor_property("nanite_settings")
    was = bool(ns.get_editor_property("enabled"))
    changed = False
    if was and not check:
        ns.set_editor_property("enabled", False)
        sub = u.get_editor_subsystem(u.StaticMeshEditorSubsystem)
        if hasattr(sub, "set_nanite_settings"):
            sub.set_nanite_settings(mesh, ns, True)  # applies the change (rebuilds the render data)
        else:
            mesh.set_editor_property("nanite_settings", ns)
        changed = u.EditorAssetLibrary.save_loaded_asset(mesh, False)
    now = bool(mesh.get_editor_property("nanite_settings").get_editor_property("enabled"))
    return {"asset": mesh.get_path_name(), "naniteBefore": was, "nanite": now, "saved": changed}


def main(argv) -> int:
    check = "--check" in argv
    rows = []
    for path in u.EditorAssetLibrary.list_assets(ROOT, recursive=True, include_folder=False):
        a = u.load_asset(path)
        if isinstance(a, u.StaticMesh):
            rows.append(nanite_off(a, check))
    ok = bool(rows) and all(not r["nanite"] for r in rows)
    print("FX_MESH_FLAGS " + json.dumps({"ok": ok, "check": check, "meshes": rows}))
    return 0 if ok else 1


if __name__ == "__main__":
    main(sys.argv[1:])
