# GD-004: verified Windows Development smoke

Recorded 2026-09-18. **GD-004 acceptance demonstrated:** minimal real UE project, configured API address, Blender static mesh import, packaged launch outside Editor, exact versions and build journal. ART-001 and final visual gate remain open.

## Evidence

- `build-manifest.json`: versions, configuration, local artifact path, executable hash/bytes, archive size, runtime markers.
- `editor-build.txt`, `game-build.txt`: successful compilation. UE 5.8.2 CL 56702186; MSVC 14.44.35228; Windows SDK 10.0.22621.0.
- `blender-output.txt`: Blender 5.2.2 LTS d13f752e3b9c, factory-startup background export; no modification of the user's Blender session.
- `import-output.txt`: final idempotent import/scene commandlet, **0 errors, 0 warnings**.
- `import-result.json`: imported mesh AABB (−50.000004,−50.000004,0) to (50.000004,50.000004,100); dimensions 100×100×100 uu within 0.1 tolerance; bottom-centred pivot; one non-null material slot `/Game/S01/M_S01_Clay` at import scale 1.
- `package-output.txt`: complete successful cook/stage/archive. `restage-output.txt`: earlier successful camera-only restage; the final full cook in `package-output.txt` additionally disables the probe cube shadow so all fixture tiles stay visible.
- `runtime-output.txt`: packaged game uses DirectX 11 / RTX 4090; loaded `Smoke`, read full `http://localhost:3000/graphql`, emitted READY and COMPLETE; exit code **0**.
- `packaged-smoke.png`: 1280×720 screenshot taken by that packaged runtime, inspected visually: full 5×6 fixture board, six placeholder figures, separate cube visible. Dark primitive materials and hard shadows are smoke presentation only.

Log copies replace worktree/user-profile paths and local host metadata. Full local logs remain ignored under `unreal/Unmatched/`.

## Reproducible sources

- `unreal/Unmatched/Unmatched.uproject`, `Source/`, `Config/`: one small runtime game module plus commandlet authoring plugins.
- `tools/s01/ue_build.ps1`, `ue_smoke.ps1`: rebuild and offscreen packaged gate.
- `tools/s01/ue_blender_probe.py`: one-metre cube, metric unit scale 1, bottom-origin mesh, FBX export −Y-forward/Z-up and face smoothing.
- `tools/s01/ue_import_scene.py`: legacy FBX static import with explicit scale 1; asserted bounds/pivot/material; idempotent scene generation from captured fixtures; geometry-only SHA256 excludes shuffled hands and timestamps (board dimensions/cells and fighter id/name/position/type). The legacy FBX path is selected explicitly because it is the pipeline under test, not inferred from newer Interchange defaults.
- `blender/_shared/s01-import/s01-cube.blend`, `SM_S01_Cube.fbx`: editable trial source/export. Not a character asset or production art.

Local runnable bootstrap: `unreal/Unmatched/Artifacts/S01/Windows/Unmatched.exe`. Actual game binary: `unreal/Unmatched/Artifacts/S01/Windows/Unmatched/Binaries/Win64/Unmatched.exe`. Whole archive including debug data and runtime captures is approximately 935 MB, deliberately ignored. Exact bytes/hash are in the manifest. Build products and generated `.uasset`/`.umap` files are not committed; generation scripts are the source of truth.

## Findings / boundaries

1. Initial engine target V6 was incompatible with UE 5.8 shared editor build settings; targets now use V7 and Unreal5_8 include order.
2. UAT's combined build encountered the user's existing Live Coding session. Separate explicit target builds with no Live Coding followed by cook/stage succeeded; no existing process was closed.
3. Default Blender smoothing export initially warned in UE. Explicit `mesh_smooth_type='FACE'` and modern save subsystem remove the warning. This does not prove final normals or tangents on future assets.
4. Unquoted API URL loaded as `http:`. Quoted config passes the final packaged marker; this is configuration validation only, not an HTTP request.
5. Draft 1200-uu camera clipped this fixture at 16:9. Fixed 1800-uu distance fits it; FOV/pitch/yaw remain the art proposal. Camera zoom, selection and final scale gate are deferred.
6. Fixture board is the current API's 5×6 grid, not a rules-approved Cobble City model. Placeholder locations come from the captured duel start; no rules or gameplay interactions are implemented.
7. Cube symmetry does **not** validate forward-axis conversion. Arrow, skeleton/bone axes, animation clip, rig, UV/normal/material-quality validation and the remainder of ART-001 are still required before mass art production.
8. RTX 4090 smoke evidence is not proof of the target medium-PC performance budget. No FPS acceptance or art acceptance is claimed. Installed engine default plugins remain enabled; only the authored gameplay module and direct dependencies are minimal.
