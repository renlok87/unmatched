# tools/art/env_kit: Tripo GLB to UE static props (ENV kit)

This tool turns a batch of Tripo Studio GLB exports (H3.1 multiview, Quad retopology, Smart UV, 2K PBR) into
UE-ready static props under the UM_FBX_v1 contract. It runs in headless Blender on the CPU and never starts a
render. The first run was ASSET-ENV-KIT-001 / `20260930-tripo-h31`: 14 props for the Marmoreal and Sarpedon
map boards.

The tool reuses the prop pipeline and does not reimplement it. `env_kit_build.py` executes
`tools/tripo-pipeline/blender/static_prop_candidate.py` (the barrel and lantern candidates) without its
trailing `main()`. The same functions therefore produce the same bytes: glTF `baseColorFactor` in linear light,
normal-map padding and the OpenGL to DirectX green flip, colour chunks stripped from N/ORM, UM_FBX_v1 export
(+90 deg Z, data x100, `FBX_SCALE_UNITS`, `UnitScaleFactor` patched to 1.0, deterministic FBX), the UV raster
metrics and the conformance rows. The independent readback is
`tools/tripo-pipeline/blender/check_static_prop_fbx.py`, unchanged.

## Commands

Run everything from the repository root:

```sh
python tools/art/env_kit/run_env_kit.py \
    --params art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/scripts/env-kit-params.json \
    [--assets ENV-S-CANNON,ENV-M-URN] [--steps probe,orient,build,readback,report] [--blender <blender.exe>]
```

| Step | What it runs | Output |
| --- | --- | --- |
| `probe` | `env_kit_build.py --probe` per asset (import, join, apply only) | `<scratch>/probe/<ID>.npz` |
| `orient` | `orientation_check.py --sheets` (system Python: numpy, PIL, scipy) | `<run>/reports/orientation-check.json`, mask sheets in `<scratch>/orient/` |
| `build` | `env_kit_build.py` per asset | `<run>/export/SM_Env_<Name>.fbx`, `T_Env_<Name>_{BC,N,ORM}.png`, `<run>/reports/assets/SM_Env_<Name>.build.json`, `.blend` and UV layout in `<scratch>/work/` |
| `readback` | `check_static_prop_fbx.py` per FBX | `<run>/reports/fbx-readback/SM_Env_<Name>.json` |
| `report` | aggregate | `<run>/reports/build-report.json` |

Every step starts a fresh `blender -b --factory-startup`. No step connects to a running Blender GUI or MCP
session. Blender logs go to `<scratch>/logs/`. On Windows, subprocesses start without a console window. The
default Blender is `C:/Program Files/Blender Foundation/Blender 5.2/blender.exe`; override it with `--blender`
or the `BLENDER` environment variable.

## Params (`env-kit-params.json`)

- `run_dir`: the run folder, relative to the repository. The build reads `source/<ID>.glb` and checks its
  sha256 against `reports/tripo-run.json`.
- `scratch_dir`: a folder outside git for probe data, the `.blend` files, UV layouts, logs and mask sheets.
- `refs_dir`: `<ID>/{front,left,right,back}.png`, the images Tripo received.
- `texture_size` (2048), `uv_raster_size` (1024: resolution of the UV analysis only),
  `normal_padding_px_source` (32), `max_triangles` (12000), `isolated_gap_uu` (0.5).
- `bake_ao`: must be `false` while GPU measurements run. The build refuses `true` because an AO bake is a
  Cycles job. When it is `false`, ORM.R is 1.0; Tripo delivers no occlusion map.
- `orientation.apply_min_iou_gain` (0.05): the smallest silhouette gain a 90/180/270 deg turn needs before it
  replaces the Tripo front.
- `assets.<ID>`: `name` (UE `SM_Env_<name>`), `board`, and `target {dimension: height|length|diameter, uu}`.
  `length` and `diameter` both measure the largest horizontal extent. An optional `yaw_deg` overrides the
  orientation check.

## Conventions

- **Units.** FBX numbers are centimetres (1 unit = 1 uu) with `UnitScaleFactor` 1.0. Import in UE with the
  legacy FBX importer at `import_uniform_scale = 1.0`. The S05 memory note "FBX_SCALE_UNITS + import 100"
  belongs to a different export profile that has no `UnitScaleFactor` patch; see
  `docs/art-pipeline/rig/RIG-CONTRACT.md`.
- **Forward axis.** The asset front is the Tripo "front" reference view. That is glTF +Z, `.blend` -Y, and
  **UE +X**, the same as SM_Decor_Barrel, SM_Decor_Lantern and the hero figures. In the FBX readback frame,
  `.blend` -Y maps to +X, +X to +Y, +Y to -X and -X to -Y.
- **Placement.** The K1 camera has yaw -90 and looks along -Y. An actor yaw of **+90** turns the front (+X)
  towards the camera. That is the yaw the Medusa and Harpy figures use in
  `tools/tripo-pipeline/review/control_scene.py`.
- **Pivot.** Base centre: the centre of the XY bounds at min Z = 0.
- **Scale.** Uniform, from the target dimension. `scale_factor_source_to_final` in the report is the factor
  applied to the Tripo metres.
- **Textures.**
  - BC: sRGB, `TC_Default`, glTF factor 0.8 applied (same rule as the lantern).
  - N: linear, `TC_Normalmap`, **DirectX**, so `flip_green false` in UE.
  - ORM: linear, `TC_Masks`; R = AO (1.0 here), G = roughness, B = metallic.
- **Material and collision.** One material slot `M_Env_<Name>`; in UE it receives `MI_Env_<Name>`. No
  collision, because these props are decor and not interactive.
- **UE folders.** `/Game/EnvKit/<Board>/`. The proposed sub-folders are `Meshes`, `Textures` and `Materials`.

## Orientation check (no renderer)

`orientation_check.py` compares the mesh with the four reference views. It turns the mesh by 0, 90, 180 and
270 deg about +Z. For each turn it rasterises the orthographic silhouette of every view by filling the
projected triangles with PIL. It crops that silhouette and fits it into a square keeping the aspect ratio, and
does the same for the reference foreground mask (non-white pixels not connected to the image border). The score
is the IoU per view, averaged over the four views.

The view frames were derived from the cannon and portal references, where the muzzle and the steps sit at
frame-left in the "left" view:

- front: camera at -Y
- back: camera at +Y
- left: camera at +X, frame-x = +Y
- right: camera at -X

Some shapes, such as plinths, the hull and the rope coil, have front and back silhouettes that mirror each
other. For those, a colour cue decides between 0 and 180 deg. The cue compares the mean base colour of the
faces that look at each camera with the mean colour of the matching reference.

A turn other than 0 deg is applied only when it beats the Tripo front by `apply_min_iou_gain`. In the first
run all 14 props kept 0 deg. Every asymmetric prop confirmed its front with a clear margin. On the portal, the
colour cue also puts the door at the front (L1 0.086 against 0.405).

## Geometry diagnostics: measured, never repaired

The task allows fixing orientation, scale and pivot only. The build therefore skips `clean_mesh`,
`repair_cracks` and `fix_winding`, and reports the following instead:

- **Topology** (welded at 1e-6 m): open edges and their loops, non-manifold edges, degenerate and loose
  elements. Each open-edge loop gets an area A: the Newell vector over its edges, each edge directed against
  its face's winding. The two sides of a zero-width crack run in opposite directions and cancel.
  - With rim length P, the mean width 2A/P separates the two kinds of loop. A **crack** (T-junction or sliver
    left by the Tripo retopology, the same defect the lantern had) has a mean width of 0.1 uu or less. Any
    loop wider than that counts as a **hole**.
  - For every hole the report gives its area, rim length, mean width and position.
- **Shells.** Connected components. For each shell the report gives its gap to the nearest other shell;
  **isolated** means the gap is larger than `isolated_gap_uu`, and **off ground** means the shell's min Z is
  above the base. The report also gives signed volume; a closed shell with negative volume is inside-out.
- **Ray escape facing** (BVH ray casts, CPU). From each face centre, 7 rays go into a 50 deg cone around
  +normal and 7 around -normal. The face is classified as:
  - **outward**;
  - **inward**: a one-sided material culls it from outside, so a hole shows;
  - **sheet**: an open card, seen from both sides;
  - **enclosed**: inside other geometry.
  Validation: the closed plinth reads 98 % outward and 0.02 % inward.
- The bmesh `recalc_face_normals` disagreement count is also reported. It is unreliable on open or
  non-manifold meshes, so the ray escape result is the flipped-face measure.
- **Tripo custom corner normals** that point into the surface.
- **UV0**: islands, bounds in 0-1, overlaps between and inside islands, flipped UV triangles, texel density,
  gutter estimate (all from `static_prop_candidate.uv_analysis`), plus the fraction of BC gutter texels and
  their colour.

## Checks (the build fails if one is false)

- The source sha256 equals `tripo-run.json`, and the source is unchanged after the build.
- The file holds a single mesh, and the round-trip triangle count equals the triangles of the `.blend`.
- The triangle count is at most `max_triangles`.
- There is one material slot and a UV0 layer, and every UV0 triangle lies inside 0-1.
- There is no armature.
- The target dimension is met within 1 %, the base is at Z 0, and the mesh is centred in XY.
- The UM_FBX_v1 conformance rows pass, including the orientation-check row.

## Not done here (follow-ups)

- **AO bake** (Cycles, CPU), after the GPU measurement window: set `bake_ao: true` and remove the refusal in
  `build()`. The reused `bake_ao()` bakes into ORM.R.
- **Winding and hole repair** (`static_prop_candidate.repair_cracks` / `fix_winding`) changes geometry. It
  needs a decision per asset; see the findings in `build-report.json`. The UE-side alternative for foliage is
  a two-sided MI (`BasePropertyOverrides.TwoSided`).
- **UE import.** It needs the editor, which is not allowed while the GPU measurements run.
