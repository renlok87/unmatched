# tools/art/concept_scene: the lit 3D island under the Sarpedon painting (ENV-MAPS P8, path 1, track A)

Task contract: `docs/art-pipeline/ENV-P8-3D-UNDER-PAINT-TASK.md` (§4 P8.1). Status of everything here: *proposed /
technically exported / measured* (headless Blender and Python only, no UE run yet); the art acceptance is the user's.

The P7 concept paste projected the registered concept plate UNLIT onto a relief sheet. P8 builds real geometry
instead. The albedo of every mesh comes from the DE-LIT concept plate (P8.0,
`C:/tmp/envmaps-research/p8/plates/sarpedon-extended-albedo-2x.png`), seen from the concept camera C0. The engine
lights the result. The C0 to plate mapping is the P7 one: `cp_common` C0 camera, `paste_proto.c0_to_plate` through
the `extended2x` registration homography, and the `cp_bake` Lanczos-3 sampler.

## Commands (repository root, CPU only, no locks needed)

```sh
python -B tools/art/concept_scene/run_scene.py                 # geom, export, layout, ao, bake, manifest
python -B tools/art/concept_scene/run_scene.py --steps layout  # one step
python -B tools/art/concept_scene/scene_layout.py --check      # layout + proxies fresh and valid (needs <work>)
python -B tools/art/concept_scene/bake_albedo.py --check       # sha256 of the FBX / textures vs the manifest
python -B tools/art/env_kit/layout_check.py --scene            # base layouts + the scene overlay (rule 12)
python -m pytest tools/art/tests/test_concept_scene_*.py -q
```

`<work>` = `C:/tmp/envmaps-research/p8/sceneA` (scratch: NPZ meshes, AO, overlays, logs). Blender =
`C:/Program Files/Blender Foundation/Blender 5.2/blender.exe -b --factory-startup` (headless, CPU; never a GUI or MCP
session).

## Pipeline

| Step | Script | Output |
|---|---|---|
| ship prep | `ship_build.py -- prep` (Blender) | Poly Haven CC0 `dutch_ship_large_01` hull decimated to `hullPrepTris`; spars by principal-axis thickness -> `<work>/ship_raw.npz` |
| ship fit | `ship_build.py fit` | yaw / position / scale fitted to the painted hull by C0-silhouette IoU (waterline fixed at the sea plane -300), the far hull below the deck cut, masts rebuilt at the painted mast pixels, dock line; `reports/ship-fit.json`, overlay `<work>/overlays/ship-silhouette-c0.jpg` |
| island | `island_build.py --overlay` | rim from the island matte (C0 rays), the near front-cliff rim, the waterfall tongue under `SM_Env_S_WaterfallLip`, the east rim on the painted red-wall foot; Delaunay top (flat -3 under the map and frame), cliffs to -315 with 3 ledges, authored UV atlas; `reports/island-build.json` |
| fort | `fort_build.py` | chamfered stone blocks along the painted base line, ragged top = the painted silhouette, the arch left open, rubble |
| palisade, piles | `palisade_build.py`, `piles_build.py` | logs / posts / rope bands / rope spans from C0 pixels (foot = ray hit on the island) |
| banner | `banner_build.py` | vertical cloth (the P7c `M_EnvCP_Banner` UV contract), not baked |
| export | `cs_blender.py export` (Blender) | `k_blender.MeshBuilder` -> UM_FBX_v1 FBX (deterministic), Smart UV atlas for the non-island meshes, read-back, final NPZ |
| layout | `scene_layout.py` | `EnvLayouts/sarpedon.scene.layout.json` (overlay, variant `scene`) + `scene-proxies.sarpedon.json` (geometry hulls for `layout_check` rule 12) |
| ao | `cs_blender.py ao` (Cycles CPU) | `<work>/ao/*_AO.png` |
| bake | `bake_albedo.py` | `scraped-data/derived/concept-scene/sarpedon/T_Env_S_<Name>_{BC,N,ORM}.png` + `T_Env_S_AlbedoC0.png` (gitignored), `manifest.sarpedon.json` |

## Interface for track B (`manifest.sarpedon.json`, schema `unmatched.concept-scene/1`)

- `meshes[]`: one entry per mesh with `name`, `fbx`, `ue` (`/Game/EnvMaps/Sarpedon/Scene/SM_Env_S_<Name>`), `tris`,
  `castShadow`, `lumenGI`, `pivotBoard`, `slots`, `textures` {BC, N, ORM} and `textureAssets`. BC is sRGB, N is
  DirectX with the green channel down, ORM holds linear masks (R AO, G roughness, B metal). Each mesh also lists its
  `material` (`MI_Env_S_<Name>`) and `sha256`. The banner has no textures and keeps `MI_EnvCP_Banner`.
- `projected`: `T_Env_S_AlbedoC0` (4096 x 2048, sRGB) over `rectC0Px` [-384, -216, 2688, 1512] with an identity
  homography. `u = (c0x + 384) / 2688`, `v = (c0y + 216) / 1512`.
- `looks`: `MI_EnvScene_Proj_{Foliage, Rock, RockWet, Wood}` with suggested parameters. The scene layout names them in
  the optional prop field `material`, which applies to all slots of the prop.
- Every scene mesh is authored in board space. The layout places it at `loc = pivotBoard`, yaw 0, scale 1. The
  banner is the exception: its loc, yaw and scale come from the layout.
- Sea: the cliffs and the ship's waterline reach -300 (task R3). An overlay may not change `ground`, so the base sea
  ring stays at -172 until the profile lowers it. The cliffs continue under the opaque sea.

## Out of git (ENV-U3 / ENV-U7)

Every image derived from the concept stays out of git: the atlases, the projected plate and the overlays. They live
in `scraped-data/derived/concept-scene/` (gitignored by `scraped-data/`) and in `<work>`. Git holds the scripts, the
params, the FBX files (each <= 15 MB), the reports and the sha256 manifest.
