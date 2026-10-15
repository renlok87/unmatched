# Patroclus H2 assembly preparation — 2026-10-15

Prep only. No final model, rig, retopology, bake, FBX, art acceptance or shared registration was produced. All files created by this scout are confined to this directory. No git, external service, GUI Blender, Unreal or other agent was used. Texture8K/PBR completion was not polled.

## Verified inputs

- Actual concept card: `../evidence/acceptance-concept/20261015-sheet-r1/card.json`, pass **9.4**, SHA256 `5161f38948ecad61c4a384225b2fb758594b30ade6386b3c7919655b8acca978`. All three accepted image hashes match the card; the sheet was personally viewed.
- Raw source: `../20261015-h2-tripo/source/patroclus-h2-tripo-e0b4d474-parts24.glb`, **44,515,584 bytes, 24 mesh parts, 1,967,447 triangles**, SHA256 `18477a384a870befeff1d3f54f4c270f57435f508f8b3f670e9b440ea0f9f557`. Hash verified before/after both source-reading runs and again at handoff. Source untouched.
- Accepted concept: figure's **own-right sword, own-left shield**, blue cape, linen corslet, bronze equipment and white plume. Selected side is **right**. Blender front −Y, own-left +X, own-right −X; these signs were visually checked on the imported figure.

## Useful outputs

- [Contact sheet, all 24 parts](contact-all24.png). Personally viewed this sheet, both larger pages ([00–11](contact-parts00-11.png), [12–23](contact-parts12-23.png)), [assembled context](assembled-context.png), all five focused detail renders, and the accepted concept sheet. Each isolate has global front34/back34 views; colors identify parts, not final materials.
- [Part-role map](part-role-map.json): all 24 parts, visual evidence, own-side, confidence and remaining checks.
- [Stage-3 proposed config data](stage3-config.proposed.json): explicit **not runnable**, with `profile_version: 2`, own part IDs, proposed scale, targets, weights, face/density/base references, right-side framing, names and pending fields. No donor bones or substitute textured source.
- [Measurements](measurements.json): bounds/height bands in the **proposed** final frame, raw-HP boundary summaries and cape ray hits. Raw topology has many fragmented small boundaries; these counts are **not** a cap selection list. Largest eight loops/part retained; original total counts preserved. Repeat real loop inventory after `prepare`/`retopo`.
- [Recipe reuse and code pins](recipe-reuse.json), [source/card hashes](source-inventory.json), [verification](verification.json), [all artifact/input hashes](hash-manifest.json).

## Actual roles

| Part | Visually identified role | Proposed treatment / uncertainty |
|---|---|---|
| 0 | Cape, shoulder drape and clasp | Cloth weights; mixed clasp material. Shell/caps unresolved. |
| 1 | Two-tier pedestal | Static base. Foot cutouts visibly exist; test closure later. |
| 2 | Round shield | Body mesh, rigid `arm_lower.L`, no new bone. Check rear hand/forearm contact. |
| 3 | Corslet, belt, diagonal strap, tabs and side scabbard/strap forms | Mixed linen/leather/bronze; open back under cape. |
| 4 | Plume / crest | `head`, proposed figure-top source. Not the face. |
| 5 | Face, ears and neck | `name: face` dense region; proposed neck blend. |
| 6 | Helmet **and hair** | `head`; cannot classify whole part as bronze. |
| 7 / 12 | Right / left greave, sandal, lower leg | Same leg-chain rules as thighs/toes; mixed materials. |
| 8 | Sword blade and guard | Sole `mesh: weapon`, rigid `weapon.R`. |
| 9 / 11 | Right / left bracer/forearm shell | Same positional arm chain across matching arm/hand pieces. |
| 10 / 14 | Left / right thigh and knee | Own leg chains; inspect skirt and knee seams. |
| 13 | Pleated lower tunic / skirt hem | Cloth weights; shell/caps unresolved. |
| 15 / 17 | Right / left upper arm and elbow region | Inspect shoulder saddles under cape. |
| 16 / 18 | Right sword fist / left shield hand | Anatomical arm-chain weights. |
| 19 / 20 | Left / right small tunic panels under belt | Confirmed in orange context renders. Exact material awaits BC. |
| 21 | Sword pommel **with adjoining hand/grip surface fragment** | Tentative body+rigid `weapon.R` split-weapon pattern; test seam with fist16. Not pure metal. |
| 22 / 23 | Left / right exposed toes | Same positional leg-chain weights as sandals12/7. |

The grip closeup shows blade/guard8, fist16 and pommel21 in contact. It does **not** prove continuous hidden handle geometry or a finished deformation-safe grip. Do not invent a handle bridge in generic h2_bake.

## Scale and geometry cautions

`asset-card.yaml` currently says `ROLE: hero` **and** `GAME_ROLE: sidekick`, with no stage-3 height. Carry the actual sidekick role forward. Proposed plume top **0.43 m**, base **Ø0.24 × 0.05 m**: 0.43/0.55 = 0.7818, inside HANDBOOK's 0.78 ± 0.06 helper/hero ratio; base follows Merlin's sidekick footprint. This is local proposal data, not an adopted card edit. A blind Achilles 0.55 m copy would lose helper scale.

With this proposal the face spans z 0.323943–0.372038 m, helmet/hair tops at 0.407004 m, attached plume tops at **0.430000 m**; sword is below the head. Base bounds are [−0.12,−0.12,0]–[0.12,0.12,0.05]. `scale.figure_top_part: tripo_part_4` makes the intended attached-headgear budget explicit.

Proposed decimation targets total **32,550 figure tris + 1,600 base**, leaving **12,450** figure tris before caps/shells against the card's 45,000 figure limit. This is only a starting allocation: final body+weapon must include caps, duplicated shell faces and rim bridges. No actual LP count was produced.

Cape-through-Y samples show two walls at x=0,z=0.12 (18.45 mm apart), x=−0.035,z=0.24 (14.57 mm), x=+0.035,z=0.24 (17.49 mm), but only one hit at x=0,z=0.20/0.29. This supports a shell with regional openings; it does not justify a blanket `cloth_shell` decision. Check LP boundary loops and posed one-sided visibility before choosing caps, junctions or an inner shell.

Raw-HP contact centres in the proposed frame are useful **starting landmarks**, not final bone heads: right elbow near [−0.06155,0.00516,0.25808], right wrist near [−0.07469,−0.00366,0.22581], blade/fist boundary near [−0.08020,−0.01345,0.20620], pommel/fist boundary near [−0.07039,0.00168,0.21424], left elbow near [0.06154,0.00417,0.25735], left/right knee contacts near z 0.1317/0.1314. Measure LP anatomical sections before authoring `rig.bones`.

## Closest recipes

- **Achilles r3**: right weapon.R, left shield on arm_lower.L, split weapon fragments in body, identical positional limb chains, and shoulder/torso/cape `rig.junctions` for forward-arm cuts. Reuse the pattern; do not copy part IDs, head coordinates, cap lists or hero scale.
- **Beowulf t4**: current generic v2 recipe, explicit `uv.density_reference_part`, base-band source, `preview.frame`, neck/collar and backside-only-cap checks; mixed materials and lower-tier ring treatment. All masks, bands and shell selections need Patroclus measurements.
- **Merlin H2**: sidekick footprint Ø0.24 × 0.05 m, right weapon chain and grip-loop measurement. Its custom driver/schema and old Smart UV path are historical, not a current generic-profile template.

## Parent's next stage

1. Finish stage-2 8K/de-lighting/PBR export on the existing task and its source-spec. Then pin actual `tex_glb` hash/bytes. No raw-parts stand-in is supplied here.
2. Adopt sidekick scale/intake fields; register `Patroclus` with `weapon.R` in the existing rig contract. Shared files were only read here; the entry was absent at scouting time. No new bone architecture is needed.
3. Use current generic `h2_bake`/Medusa schema as the structural template and this partial data as own-figure inputs. Complete missing `rig.bones`, `bake`, closure, chart settings, masks, preview/seams and material fields. The proposal envelope intentionally fails as an executable bake profile.
4. Run **one stage at a time**, read the report after each: `prepare` (parts/texture geometry identity and ray orientation), `retopo`, then inspect LP sections/loop inventory and configure `close`. Do not inherit `expected_inside_out_parts` from donors. Do not run `all` on this new profile.
5. After real bake/rig: expanded v2 probes and FBX readback, grip/shoulder/collar/cloth/base checks, lookdev + TeamAccent, tone and personally viewed acceptance closeups. Helmet6, greaves7/12, torso3 and pommel21 require mixed material masks. Preserve blue cape and white plume. Base band lower-tier z interval awaits actual measurement.
6. Later animation handoff: include pommel21 on `weapon.R` and shield2 on `arm_lower.L` with islands in the contact specification; follow HANDBOOK's smoke/grip checks before acceptance. No clips authored here.

## Exact commands

Executed from project root (one Blender child at a time, four threads, hidden console):

```powershell
python 'art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-prep/run_scout.py'
python 'art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-prep/compose_sheets.py'
python 'art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-prep/run_scout.py' scout_details.py
python 'art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-prep/prepare_handoff.py'
python -B tools/art/acceptance/validate_card.py 'art/pipeline-candidates/ASSET-PATROCLUS-001/evidence/acceptance-concept/20261015-sheet-r1/card.json' --print-verdict --check-files
python 'art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-prep/verify_and_manifest.py'
```

Final checks: canonical concept validator exited **0**, `score=9.4 verdict=pass`; prep integrity verifier passed **24 parts, 1,967,447 tris, 62 valid PNGs**, matching source and all three accepted concept hashes, and both executed Blender scripts matched their recorded SHA256. Both recorded Blender PIDs were also absent in a final `Get-Process -Id 53948,67476 -ErrorAction SilentlyContinue` check; no cleanup action was needed.

The launcher's exact executable/argv, script hash, PID, UTC start/end, exit code and child-reaped result are in `process-record.json` and `details-process-record.json`. Blender was **5.2.2 LTS**. The render scout exited 0 in 15.710 s (PID 53948); the detail scout exited 0 in 55.787 s (PID 67476). Both were waited/reaped; no user or service process was stopped. CIM inventory access was denied, so process cleanup evidence is the launcher's own child handles/exit status. `prepare_handoff.py` compacts measured JSON without changing measured scalar results.

Future commands for the parent **only after completing the real profile and inputs**, not executed here:

```powershell
$profilePath = 'art/pipeline-candidates/ASSET-PATROCLUS-001/build-profiles/patroclus-h2-bake-h2.json'
$runPath = 'art/pipeline-candidates/ASSET-PATROCLUS-001/20261015-h2-bake'
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --profile $profilePath --run-dir $runPath --stages prepare
# Read prepare-report.json and act on its actual checks before continuing.
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --profile $profilePath --run-dir $runPath --stages retopo
# Inspect own LP sections/loops; complete closure config before close.
python tools/tripo-pipeline/blender/h2_bake/run_h2_bake.py --profile $profilePath --run-dir $runPath --stages close
```

If any named future output already exists, use a new run/profile name; never overwrite another session's work. `stage3-config.proposed.json` contains the full pending checklist. No final bake was run or authorized by this scout.
