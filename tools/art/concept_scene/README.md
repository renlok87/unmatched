# tools/art/concept_scene: the lit 3D island under the Sarpedon painting (ENV-MAPS P8 / P9, path 1, track A)

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
| frame band (P9 F2) | `frame_band_build.py` | the painted heavy dark frame around frame-002: bevelled plank beams (outer top edges on the C0 rays of the painted outer edges, the near beam's tall front face over the tucked lip), iron corner brackets / mid straps / rivets; two slots (track B's `MI_EnvScene_FrameWood` / `FrameIron`), box-mapped tiling UV0; `reports/frameband-build.json` (C0 coverage of the painted frame), overlay `<work>/overlays/frameband-c0.jpg` |
| ship (P9 F1) | `ship_build.py` | procedural on the painted pixels (no Poly Haven hull): a vertical wall plane through the painted foot line of the red hull side, the rail cap on the painted rail (level ~290 uu), clinker strakes, three gun ports at the painted cannon muzzles, wales, deck 90 uu under the rail, far bulwark, hull to the keel, stern transom clear of the frame band, bow beyond the canvas, the main mast raked along the painted mast line with a yard, a furled sail and shrouds, the rail-lantern post; `reports/ship-build.json` (C0 fit, ports, lantern), overlay `<work>/overlays/ship-c0.jpg` |
| island | `island_build.py --overlay` | rim from the island matte (C0 rays), the near front-cliff rim (straight: P9 dropped the P5c waterfall tongue), the east rim on the painted dock edge; Delaunay top (flat -3 under the map and frame), cliffs to -315 with 3 ledges, the front lip tucked under the frame band's near beam (`nearLip`, P9 F3), authored UV atlas; `reports/island-build.json` |
| cascade (P9 F4) | `cascade_build.py` | the wide multi-tier waterfall on the island's front cliff in the `nearLip` outlet: 4 streams x 4 tiers (lip -> ledges 1-3 -> the sea), held off the rock, every drop bowed outward; UV0 u across the cascade, v per tier (lane K convention, `FallCard.w` 1); foam pads on the landings; tier landings = the mist / spray anchors; `reports/cascade-build.json` (C0 painted-width coverage), overlay `<work>/overlays/cascade-c0.jpg` |
| fort | `fort_build.py` | chamfered stone blocks along the painted base line, ragged top = the painted silhouette, the arch left open, rubble |
| palisade, piles | `palisade_build.py`, `piles_build.py` | logs / posts / rope bands / rope spans from C0 pixels (foot = ray hit on the island) |
| banner | `banner_build.py` | vertical cloth (the P7c `M_EnvCP_Banner` UV contract), not baked |
| export | `cs_blender.py export` (Blender) | `k_blender.MeshBuilder` -> UM_FBX_v1 FBX (deterministic), Smart UV atlas for the non-island meshes, read-back, final NPZ |
| layout | `scene_layout.py` | `EnvLayouts/sarpedon.scene.layout.json` (overlay, variant `scene`) + `scene-proxies.sarpedon.json` (geometry hulls for `layout_check` rule 12); P9: the frame band / cascade meshes, the dock props kept clear of the band and the hull side, the cannons in the ports, the rail lantern on its post arm, the banner flat on the hull, track B's `fx-plan.sarpedon.json` merged (`conceptScene.fxAnchors` / `fxPlan`) |
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
- P9 `meshesExistingMaterial`: the banner (`MI_EnvCP_Banner`), the frame band (slots `MI_EnvScene_FrameWood`,
  `MI_EnvScene_FrameIron`), the cascade (`MI_EnvScene_FallsSheet`) and its foam (`MI_EnvScene_FallsFoam`) - track B's
  material-route MIs of `ue_scene_material.py`, one per slot; the top-level `materials` block carries this build's
  values (the cascade's `FallCard`). The frame band is not baked but stays an occluder of the island bake; the
  cascade is neither baked nor an occluder (translucent).
- P9 fx: `fx-plan.sarpedon.json` (track B, schema `unmatched.concept-scene-fx/1`) is merged by `scene_layout.py` when
  present (its fires replace the P8 `NS_Env_ConceptFire` entries; a waterfall entry of a tier the cascade does not
  have is dropped and reported); anchors `brazier`, `fort-pit`, `falls-tier-1..4` are written to the overlay's
  `conceptScene.fxAnchors`. In lit3d the cascade replaces the P5c ground waterfall: the profile's `lit3d.hide` must
  list `waterfalls` (track B, overlay note `conceptScene.lit3dHide`).

## Out of git (ENV-U3 / ENV-U7)

Every image derived from the concept stays out of git: the atlases, the projected plate and the overlays. They live
in `scraped-data/derived/concept-scene/` (gitignored by `scraped-data/`) and in `<work>`. Git holds the scripts, the
params, the FBX files (each <= 15 MB), the reports and the sha256 manifest.

## P9 (2026-10-02): the six fixes, track A part (F1 ship, F2 frame band, F3 front lip, F4 cascade)

Status: *proposed / technically exported / measured on the plate at C0* (no UE run in this stage). Self-check numbers
(headless, out-of-git overlays in `<work>/overlays/` and `C:/tmp/envmaps-research/p9/scratch/`):

| Fix | What | Self-check |
|---|---|---|
| F1 ship | procedural near side on the painted pixels (`ship_build.py`), cannons in the ports, dock props re-picked, 2 barrels on the deck, banner flat on the hull, `scene-tune` Ship `BakedTint` 0.75 (the rest stays 0.45) | visible C0 silhouette IoU vs the painted ship 0.73 (P8 Poly Haven fit 0.65), rail pixel RMS 1.5 px, muzzles on their pixels (< 1 px) |
| F2 frame band | `frame_band_build.py`: dark beams + iron around frame-002, top <= 12.1 < frame-002 12.4 | 96.8 % of the painted frame band covered at C0, rule 12 clearance 21.8 px |
| F3 front lip | `island.nearLip`: the lip tucked under the beam's face, the band's planks fill limited to the beams' footprint | lip / neighbour cliff Laplacian variance on the bake preview: K1 1.23 / 1.06, C0 1.16-1.27, K1x0.65 1.17-1.96 (>= 0.7) |
| F4 cascade | `cascade_build.py`: 4 streams x 4 tiers + foam pads, mist anchors for track B's plan | painted width (C0 x 640-1000) covered 91 % in the C0 frame, 92.5 % on the extended canvas |

## P9 integrate / tune (2026-10-02, measured in UE; evidence `docs/game-design/evidence/ENV-MAPS/p9-fixes-hero-light-2026-10-02/`)

- `cascade.uvPerStream` (scene-params): every stream has its own u 0..1 and the streams overlap by 8 uu, so
  `M_EnvWaterfall`'s wobbling side fades soften each stream (the UE frames read four rectangular panels with straight
  rock gaps); `FallCard.x` = the mean stream width (82.5 uu).
- `layout.footRocks` entries may name a `mesh`: `rock-falls-*` = 8 wet Fab rocks on the cascade outline (outlet top
  corners, between streams on tiers 2 / 3, its lower sides, the sea foot).
- `scene-tune.sarpedon.json`: Ship `BakedTint` 1.3; `materials` FrameWood `BakedTint` (0.63, 0.48, 0.42) (the band read
  dL* -6.4 under the painted frame), FrameIron 1.3, FallsSheet `FallLook` (0.5, 0.96, 0.9, 1) / `FallFlow` side 30 uu.

## P10 (2026-10-03, RD-3 rework; evidence `docs/game-design/evidence/ENV-MAPS/p10-sarpedon-rework-2026-10-03/`)

- `cascade.rag` (cascade_build.py `ragged_top_dip`): the water's top under the beam is torn - Gaussian notches
  `[x, depth, half-width]` + positive value noise, so the K1 bottom edge has no straight bright line.
- `cascade.phase` (`column_phase` -> `ribbon(phase=...)`): per stream tier offsets + noise; v -> phase + (1 - phase) v,
  so the lip foam / streak bands of the four streams do not line up.
- `cascade.foamJitter`: torn foam pads (per column depth x 0.45..1, inner edge +- 4 uu).
- `layout.details.cannonScaleMul / cannonOutUU / cannonYawOffsetDeg` (scene_layout.py): the port cannons scaled /
  turned about the painted muzzle and pushed out along their axis (the carriage stays within the port frame:
  test_concept_scene_layout `test_cannons_in_the_ports`); dock crates / barrels capped at scale 2.3.
- `scene-tune.sarpedon.json` (MIs, ue_scene_material.py): Fort `BakedTint` 0.279, Ship 1.4 x [1.03, 1, 0.97], FallsSheet
  / FallsFoam opacity, foam and the emissive lift (`FallShade.w` 4 -> 2). The cannon iron: `ue_import_concept_paste.py`
  `CANNON_LOOK` (`CANNON_MI_VERSION` 3).
