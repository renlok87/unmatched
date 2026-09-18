# S01 UE smoke — GD-004

Verified 2026-09-18. This is a real isolated UE project, not the legacy snippets in `docs/unreal`.

## Reproduce

From the repository root in PowerShell:

```powershell
./tools/s01/ue_build.ps1
./tools/s01/ue_smoke.ps1
# Optional manual interactive demo, remains open:
./tools/s01/ue_launch.ps1
```

Defaults are the installed UE 5.8 and Blender 5.2 directories; `ue_build.ps1` accepts `-Engine` and `-Blender` overrides. Requires Visual Studio C++ Build Tools and Windows SDK. Source fixtures must exist at `docs/game-design/evidence/S01/content-board.json` and `duel-start-p1.json`.

The script builds the editor module, exports a fresh Blender cube, imports assets and generates the level, builds the game, then cooks/stages/archives it. It compiles targets separately with `-NoHotReloadFromIDE -NoLiveCoding` and packages without rebuilding the editor, so the user's existing editor/Blender sessions can remain open. It never closes those sessions. No backend calls occur.

Launch the local packaged artifact interactively through `Artifacts/S01/Windows/Unmatched.exe`. `ue_smoke.ps1` instead launches its game binary hidden with `-RenderOffscreen -S01Smoke`: capture after eight seconds, completion marker and graceful exit after twelve seconds. `-S01Smoke` is opt-in; normal runs remain open.

Generated Content, Binaries, Intermediate, Saved and Artifacts are intentionally ignored. Recreate them using the scripts. Only one game module exists: dependencies Core, CoreUObject, Engine and InputCore. PythonScriptPlugin and EditorScriptingUtilities support generation in the editor commandlet; installed engine defaults also remain enabled. This is not a minimized redistributable or a Shipping build.

API URL is in `Config/DefaultGame.ini`, quoted because Unreal's INI parser treats an unquoted `//` as a comment. Runtime verifies the complete string in the smoke marker. Network transport, login, HTTP and WS are out of scope.

The scene uses the captured 5×6/30-cell board and six static placeholders. Coordinates follow INT-019; zones are retained in actor labels, not presented as final board art. Camera is fixed perspective, horizontal FOV 35°, pitch −55°, yaw −90°, distance 1800 uu to fit the tall fixture in 16:9. Zoom is deferred. No rig, animation, axis-arrow check, material-quality/normal sign-off or performance acceptance is claimed.

See `docs/game-design/evidence/S01/ue/README.md` for measured results and limitations.
