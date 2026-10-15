# Patroclus — bounded H2 prepare, 2026-10-15

**Prepare PASS, 5/5 checks.** This package contains a proposed generic v2 profile and an actual prepared high-poly scene. It is not a finished model or an art/rig/runtime acceptance. The only pipeline stage executed was `prepare`; no `all`, retopo, close, UV, bake, rig, lookdev, TeamAccent, animation, Unreal or paid service call was run.

## Outputs and actual measurements

- Profile: `../build-profiles/patroclus-h2-bake-h2.json`, `profile_version: 2`, `profile_id: patroclus-h2-bake/1`, validated by the current `h2_bake.profile.validate`.
- Actual report: [reports/prepare-report.json](reports/prepare-report.json); current generic runner marker: [work/stages.json](work/stages.json), containing **prepare only**.
- Actual prepared scene: `work/hp.blend` (338,164,232 bytes at handoff). Packed HP data; the diagnostic render did not save or mutate this file.
- Own separately executed HP section measurements: [measurements-own-hp.json](measurements-own-hp.json), [measurement script](measure_landmarks.py). These locate provisional bone heads/tails and the sword grip from this figure. They do not replace the required LP measurements after a separately authorized retopo.
- Exact script/input/output hashes and verification: [hash-manifest.json](hash-manifest.json), [verification.json](verification.json). The manifest includes the sibling owned profile; no shared registry/card/source file was edited.

`prepare-report.json` verifies both source hashes and lengths against the pinned source spec, identical 24-part sets, geometry correspondence for all 24 parts, and the expected empty inside-out list. The existing geometry checker compares triangle counts plus unique float32 positions rounded to seven decimal places; UV seam vertex splits are allowed. Each GLB has **1,967,447 triangles**. This is an HP count, not a runtime budget result.

Orientation uses ray escape against the whole figure, **4,000 polygon samples per part, seed 0**, unchanged threshold **−0.5**. All 24 reported scores are **1.0**; measured `inside_out: []`, expected `[]`, so **zero parts were flipped**. This sample result does not prove watertight topology or deformation-safe seams.

Final bounds are **[−0.13353, −0.12, 0] to [0.12, 0.12, 0.43] m**. Base part1 is **Ø0.24 × 0.05 m**; plume part4 defines the **0.43 m** figure-top budget. Figure scale is **0.42777741** from the actual source frame. No part offsets, base flattening, cap selection or geometry repair was applied.

The parent explicitly adopted this sidekick scale for this profile. The source `asset-card.yaml` still contains **ROLE: hero** and **GAME_ROLE: sidekick**. That conflict is disclosed in the profile and was not edited here. Standard `weapon.R` / own-right sword and own-left shield were used; the parent separately registered the shared rig-contract entry. This task did not author or edit it.

## Personally viewed current HP diagnostics

I opened all six PNGs below after rendering them from the **actual prepared `work/hp.blend`**. Workbench texture views display the original Tripo base colour with studio shading and cavity. They are diagnostic views, not the pipeline `preview` stage, PBR/lookdev evidence, rig probes, or formal acceptance renders. Three packed Tripo images were measured **8192 × 8192** (base colour, normal, roughness/metallic); the Workbench views do not evaluate the full PBR material.

| View | Observation and limit |
| --- | --- |
| [Front, source texture](diagnostic-preview/prepared-hp-front-texture.png) | Whole figure and pedestal visible without clipping; own-right sword / own-left shield, blue cape, light linen and white plume match the accepted design anchors. |
| [Own right, source texture](diagnostic-preview/prepared-hp-right-texture.png) | Correct side view; raised headgear and attached sword remain below the top budget. This is not a silhouette acceptance comparison. |
| [Back, source texture](diagnostic-preview/prepared-hp-back-texture.png) | Blue drape covers much of the torso/shoulder seams. Hidden contacts remain unproven. |
| [Front 3/4, part colours](diagnostic-preview/prepared-hp-front34-parts.png) | Actual part separation retained. Raw foot cutouts/boundaries are visible around the sandal/base contacts; inspect LP loops before closure. |
| [Own-right grip, contextual](diagnostic-preview/prepared-hp-right-grip.png) | Fist/guard visibly meet. Hidden handle continuity and the part21/fist seam remain unproven. **A jagged local opening is visible at the medial/front area of the figure's own-left knee, around thigh/knee part10**. Record this for actual LP loop inventory/closure; no repair attempted. |
| [Left shield rear, contextual](diagnostic-preview/prepared-hp-left-shield-rear.png) | Rear shield and bracer visible, but the hand/contact is partially occluded by the cape. Do not treat this shot as grip clearance proof; use a later isolated LP/contact diagnostic. |

The 17 bone rows are **proposals**, derived from unique-position HP section band bounds. Hips/spine use an explicitly proposed centreline within own torso bounds. The weapon head uses own fist bounds, and its direction uses own blade PCA. No donor coordinates, part IDs, closure lists, masks or bones were copied. These positions have not been tested by rigging or deformation probes.

The decimation targets remain the scout's starting **32,550 figure + 1,600 base triangles**. Nothing was decimated. Empty seam/junction/cap arrays mean **unconfigured pending actual LP evidence**, not “no repairs needed.” Cloth shell choice, mixed-material masks, lower-tier base band, chart packing, bake cage, K2/seam/probe/closeup configuration and actual budgets remain unresolved. Part21 contains a pommel plus adjoining grip/hand fragment; its proposed rigid `weapon.R` treatment must be tested against fist16.

## Exact executed commands and process lifecycle

From the repository root:

```powershell
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-bake/run_bounded.py measure
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-bake/create_profile.py
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-bake/run_bounded.py prepare
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-bake/run_bounded.py preview
python -B art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-bake/verify_and_manifest.py
```

`run_bounded.py prepare` calls the unchanged generic runner with `--stages prepare`; its local launch override adds **hidden console, `--threads 4`, timeout, exact PID/argv/script-hash recording and wait/reap**. It changes no pipeline stage implementation. The `preview` mode here is only the own diagnostic script, not `run_h2_bake.py --stages preview`. No generic pipeline preview/rig stage was executed.

Blender **5.2.2 LTS** children ran sequentially:

- Own measurements: PID **52532**, **4.941 s**, exit **0**, child reaped.
- Generic prepare: PID **49096**, **12.719 s**, exit **0**, child reaped.
- Prepared HP diagnostic rendering: PID **97720**, **12.320 s**, exit **0**, child reaped.

Exact records are `measure-process-record.json`, `prepare-process-record.json`, `preview-process-record.json`. A final ID-specific `Get-Process` check found none of those children. No process was killed. No user's Blender, Unreal or service process was changed.

## Next stage handoff — not executed

There is no blocker to the completed bounded prepare. The parent can review the proposed profile and this report, then authorize **retopo only** as a new step. After real LP creation, inspect own sections, all significant boundary loops and the visible knee/foot openings before authoring any closure/junction/shell settings. Remeasure anchors, inspect shield and sword contacts in isolation and pose tests, then advance one stage at a time. Do not run `all` on this prepare-only proposal.

Do not rerun `create_profile.py` over this completed profile: it intentionally refuses to overwrite. Preserve this first measured prepare and use a new profile/run when changing prepare inputs. `verify_and_manifest.py` can be rerun to check the frozen package without touching sources.
