# 3d-model-pipeline — pilot run 2026-10-13 (end-to-end on a small sample)

User request (2026-10-13): «Сгенерировать модели можно все. Но сначала, чтобы полностью обкатать скилл и итерационно
его улучшить, можно это сделать на небольшой выборке».

Pilot figures (one per branch that the DB roster needs):

| Asset | Why it is in the pilot |
|---|---|
| ASSET-ACHILLES-001 | standard humanoid hero, weapon in the RIGHT hand plus a shield; whole path through Codex |
| ASSET-ANGEL-001 | humanoid hero whose front passed the acceptor pair (Sol 8.1 + Opus 8.1) |
| ASSET-ANCIENT-LESHEN-001 | licensed figure (The Witcher): front from unstability.ai Recraft; tests what 1c does when Codex image_gen refuses |

Mass stage 1b was stopped after 12 drafts (Achilles, Ancient Leshen, Angel, Annie Christmas, Beowulf, Bigfoot,
Black Panther, Black Widow, Blackbeard, Bloody Mary, Bruce Lee, Buffy); they are paid and logged
(`docs/game-design/visual/credits-ledger.json`, AN-37…AN-52/AN-122…AN-124) and wait for the pilot to finish.

## Findings → skill fixes (applied after the pilot, one commit per stage)

| # | Stage | Finding | Fix in the skill |
|---|---|---|---|
| F1 | 0 | The batch writer of stage 0 hard-coded `ANATOMY: humanoid`; five DB figures are non-humanoid (Ant Queen, Blob, Tarantula, T. Rex, Raptors) and three are winged (Jersey Devil, Mothman, Wingnut). Caught only before Tripo. | stage 0 / intake: ANATOMY must be decided per figure from the DB description before 1a; add the check «wings + separate arms = stop §5 п.5» to the 1a acceptance |
| F2 | 0 | Asset `.gitignore` (intake §3) was not created by the batch writer; 47 MB draft GLBs would have been committable. | intake checklist: `.gitignore` is a gate of stage 0, checked by `git check-ignore` on a sample GLB path |
| F3 | 1b | Tripo Studio keeps the address of the model being viewed: after «Создать» while a previous model is open, the URL still shows the old task. The task uuid of the new run is taken by clicking the newest tile in «Ассеты». | tripo3d-stages §5.2: how to read the uuid |
| F4 | 1b | `register-source` refuses when `reports/tripo-run.json` does not exist yet («evidence file missing»), but §5.2 orders the report after the source-spec. | tripo3d-stages §5.2: write the report skeleton before `register-source` |
| F5 | 1b | Spending cap ВР-04 (3000) blocked the pre-flight; the user lifted it («На триппо нет лимита»). | decisions record + ledger limit; skill text «3000» → «ledger limit (user decision)» |
| F6 | 1a acceptance | Second acceptor «Opus xhigh» reused the Sol prompt; the Workflow structured output returned `"clip": "null"`, `"verdict_reason": "null"` strings and once a free-text `known_issues.item`, which `validate_card.py` rejects. | acceptance §8.3/§8.5: the launcher strips null-strings and the Opus prompt states the item pattern |
| F7 | 1a | Codex image_gen, SYNTX (Seedream, Banana) and Gemini refuse licensed characters; unstability.ai (Recraft v4) works, Seedream inside it is filtered too. Recraft output fails Q/P against the Medusa reference. | concept-sheet §5: licensed-figure route, background flattening (`rebg.py`), user-decision record |
| F8 | 1c | 3/3 sheets accepted: Achilles Sol 9.4, Angel Sol 8.8, Ancient Leshen Sol 8.1 + Opus 8.1 (pair 8.1). Codex image_gen drew the licensed Leshen views over the Tripo orthos although single calls returned `moderation_blocked` (the 1c route through the draft render passes where 1a failed). The second-acceptor workflow again returned `"clip": "null"`/`"verdict_reason": "null"` strings (F6 repeats). A side view drawn mirrored would not be caught by `check_concept_views.py` (no facing check); on the pilot all three were correct (silhouette IoU against `ortho_<SIDE_VIEW>` 0.60–0.87, against its mirror 0.41–0.45). | concept-sheet §5.5/§12: add a facing gate (IoU of the side silhouette vs `ortho_<SIDE_VIEW>` and its mirror, prototype `C:/tmp/concept-wave/side_mirror_check.py`) to `check_concept_views.py`; licensed figures: try Codex 1c first, unstability only if Codex refuses the whole view |
| F9 | 2 | Studio route works end to end through Windows-MCP clicks in the user's Chrome: 3 heroes × (60 + 30 + 5) = 95 each, no failed generation. Facts the skill does not state: (a) after a parts generation the task opens at `/workspace/segmentation/<uuid>`, texture at `/texture-edit/<uuid>`, PBR at `/texture-pbr/<uuid>`; (b) the texture form preloads the task's own views and keeps «Удалить освещение» and 8K from the last run; (c) texture and PBR run on the same tile, the newest tile stays the newest *task*; (d) after PBR the «Создать PBR 5» button becomes active again — a second click spends again; (e) the export file name is Studio's caption («ancient warrior 3d model.glb»), not the task; (f) a new hero's generation can start while the previous hero's texture runs (Studio queues it); (g) times: generate ≈ 2 min, texture 8K ≈ 3–4 min, PBR ≈ 1 min. | tripo3d-stages §5.1/§6: URL pattern, preloaded texture form, «do not press PBR twice», rename on move, pipelining heroes |
| F10 | 2 | Tripo writes `accessor.min[1] = 2.2e-308` (DBL_MIN) for POSITION, so accessor min/max cannot give part boxes; part roles for the stage-3 profile were derived from the vertex buffer (`C:/tmp/concept-wave/post_h2.py`). Thin weapons come split: Achilles spear = 2 parts, Angel sword = 2 parts (blade+guard, grip). | tripo3d-stages §6 step 9: part roles from the vertex buffer; profile `parts` must accept a weapon made of several Tripo parts |
| F11 | 2 | §6 step 5 asks for `studio_settings_before` before *each* operation; with the form already on H2 settings from the previous hero this is one record per hero. §6 step 11 «return settings» contradicts pipelining several heroes: the form is left on H2 settings until the last hero of the batch. | tripo3d-stages §6 steps 5, 11: per batch, not per operation |
| F12 | 3 | `st_rig.py:324`, `st_lookdev.py:190` took only `tripo_part_1` as the face (Medusa's head); Achilles' part 1 is the base → `rig` FAIL (0 face polygons). `st_uv.py:586` compared the face with `tripo_part_0` as «dress» | **fixed** `0e6e1bcc`: face part = `retopo.dense_regions["face"].part`, `uv.density_reference_part` (defaults keep Medusa) |
| F13 | 3 | `profile.py:68` allows one weapon part; Tripo splits thin weapons (spear 10 + 13) | decision П3-1 (second part into `body`, 100 % weapon bone); HANDBOOK §4.2 to document |
| F14 | 3 | Single-sheet cloak shows back faces in arm raises (blobs 220/199 px), hero materials are one-sided by contract | decision П3-3: profile means first, then an opt-in cloth-shell key in h2_bake (stage-3 r2 agent) |
| F15 | 3 | seams counts a free cloak edge as a contact loop (covered by the torso 16.7 mm away) | HANDBOOK §4.3: max covering distance for loops |
| F16 | 3 | Caps skip loops < 3 cm: spear butt (1.4 cm) opens 100 % in `arm_r_raise` | HANDBOOK §4.2: a weapon end near the base needs its own cap with a lower `min_perimeter_cm` |
| F17 | 2→3 | Stage-2 part roles were wrong (part 5 = head + helmet, part 6 = crest only) | tripo3d-stages §6 step 9: roles from a per-part colour render, not from boxes |
| F18 | 0→3 | Card has no stage-3 fields (CHARACTER, FIGURE_HEIGHT_M/RANGE, UE names, FIGHTER_NAME, CLIP_PREFIX) | decision П3-5; SKILL §7.2 stage 0 must write them |
| F19 | 3 | No tool for bone positions, open-loop list for caps, inward-facing parts: the agent wrote its own scout (grid render, cross-sections, `C:/tmp/achilles-h2-scout/tools`) | HANDBOOK §4.3: a scout run as a step, ship the measuring tool |
| F20 | 3 | Medusa `team_mask.cloth_hsv` fails `team_mask_cloth_share` on a red cloak (TeamMask is deprecated) | HANDBOOK §4.2: list as a value to retune |
| F21 | 3 | Look-dev needs `work/uv/metal_mask.npy` and `baseline_BC/ORM` (`lookdev.py:330-333`) though the skill reads them as optional | HANDBOOK §4.2/4.4: metal pass required; baseline of a new hero = its H2 textures |
| F22 | 3 | Colour-only metal rules cannot split golden hair from a bronze helmet (3D half-space needed); Tripo gave the wooden shaft metallic ≈ 0.5 | HANDBOOK §2.4: bronze recipe, metal by region |
| F23 | 3 | TeamAccent 1.29 % (kilt hem + baldric) — armoured hero cannot reach 5 % without dyeing the main colour | decision П3-4 (Arthur precedent 3.56 %) |
| F24 | 3 | TeamAccent profile has no top-level `frame`; determinism: `textures-report` differs by GPU N noise, HANDBOOK says reports are identical | HANDBOOK §4.3: which files are compared, noise tolerance |
| F25 | 3 | `rig` writes `export/*.fbx` before its checks — a failed stage leaves valid-looking FBX | tool: write to staging, publish on PASS |
| F26 | 3 | Shield 100 % on `arm_lower.L` (no bone) passed all probes | decision П3-2; HANDBOOK §2.6 pattern |
| F27 | 3 | TeamAccent selectors have no «band N cm from a rim» or «lining = inner face of a closed shell»; an all-leather costume (Angel: 0.73 % area, K2 5× 0.39 % / 0.03 %) cannot pass `team_accent_visible_k2_5x_front_and_back` | decision П3-4a for the pilot; tool: lining/offset-band selectors in `lookdev_accent.py` |
| F28 | 3 | Scale reference = highest vertex of any non-base part, weapon included: Angel's raised sword put the head at 0.541 m; fixed by `figure_top_m` 0.55904 | HANDBOOK §4.2 `scale`: say it, or an opt-in key that excludes the weapon |
| F29 | 3 | Medusa pattern has `textures.team_mask.base_band.part` = `tripo_part_2` — for Angel that is a trouser leg | HANDBOOK §4.2 retune list |
| F30 | 3 | uv: charts passing the 512 px test still overlapped 7 px at 4K (`raster_overlap_px`); report does not name the islands | HANDBOOK §4.3: smaller `chart_area_cm2` for sleeves/blades; tool: name overlapping islands |
| F31 | 3 | Trousers split into two Tripo parts: the tops open in flex poses (blob 249 px); contact caps fixed it, a weight junction folded the thigh. seams-report gives no blob location | HANDBOOK §4.2 closure: caps, not junctions, for split trousers; tool: blob centroid in metres |
| F32 | 3 | `ta_report` writes `passed: false` but the driver continues to `ta_manifest` (unlike `ta_maps`) | tool: non-zero exit; SKILL: read `ld-team-report.json` |
| F33 | 3 | `--compare-with` writes the determinism report into the repro run, not the production run | HANDBOOK §4.3: rerun `--stages manifest --compare-with <repro>` on the production run |
| F34 | 3 | Blade class: Arthur's `steel_polished` rendered Angel's matte blade near-black (`metal_forged` used); `ld_measure` gains push a dark costume onto the class floor (shirt merged with coat) | HANDBOOK §4.4 / material library: class by the concept's finish; keep contrast between classes |
| F35 | 3 | Angel's coat came as a closed shell (no back faces); the loop inventory of `close` tells single sheet from shell | П3-3: check the inventory before the cloth-shell key |
| F36 | 4 | Sol acceptor sandbox (codex-cli 0.162.0-alpha.17.2): PowerShell in Constrained Language Mode outputs the OEM codepage, Cyrillic rubric arrives garbled, all exit codes 0 — the first Angel acceptance read garbage | acceptance §8.2/§8.4: read with `Get-Content <f> -Raw -Encoding OEM` or `cmd /c type <f>`; stage-0 exec probe reads a Cyrillic file; garbled = environment failure |
| F37 | 4 | codex exe moved to `bin/2e5e00daee91c61d` (alpha.17.2); the docs pin `9691020b…`/alpha.2 | SKILL §4, §8.4: glob, no pinned hash/version |
| F38 | 4 | A TeamAccent rerun in its own run dir (`-teamaccent-b`) has no slot in the acceptor prompt; the stale `passed:false` report stays in the look-dev run | §8.2: `{{TA}}` placeholder; the latest TeamAccent run decides |
| F39 | 4 | Card has `ANCHORS_EN` (not `ANCHORS`), no `ACCEPTOR_PROFILE`; `UE_NAMES.textures` patterns lack `_2K_` | §2.2/§7.2: accept `ANCHORS_EN`; G-NAMES against shipped 2K names |
| F40 | 4 | No `executor_session_id` format for a subagent executor | §1 п.2: `claude-code:<uuid>/agent:<name>` |
| F41 | 4 | G-NAMES height: `scale.figure_top_m` is the blade tip for a raised weapon (55.9 uu, +1.6 %), HANDBOOK §2.10 measures without the weapon | take the head top from `ld-fbx-report#…SK_<Key>_H2_Body.bounds_m.max` |
| F42 | 4 | Main class at tone `floor` is exempt from T: Angel's coat reads grey-brown vs the near-black concept, T still 1.5 | §5.3: a main class at `floor` → known_issues + stage-7 UE tone check (recorded this time) |
| F43 | 6 | Clip gate G-MANIFEST needs `technically_imported` (UE import), but stage 6 runs before stage 7; `validate_card` allows no `n/a` for clips — a card now would burn a clip cycle | animation-vfx-sfx §10 / SKILL §2: clip acceptance after the 7a import (pilot: prompts prepared, r1 after import) |
| F44 | 6 | §6.1 SYNTX video refs: ~4 × 6–10 tokens per hero vs 48 left in the visual cap — do not scale to the roster | make them optional; default = library patterns of a hero with the same weapon (Angel ← Arthur's sword clips); SYNTX only for unusual motion |
| F45 | 6 | `clip_review_sheet.py --check` crashed (StopIteration) for any new HEROES record: the self-test made launches for every HEROES key but SYNTH_FIGHTERS has 4 MVP heroes | **fixed** (self-test uses heroes with a synthetic fighter) |
| F46 | 6 | Д-3 `--check` also asserts a fixed AN-17 union size (31) | new-character-registration §2: card frame numbers inside the union |
| F47 | 6 | `h2anim_run.py` crashes on cp1251 stdout printing «×» before the run report | animation-vfx-sfx §6.3: run with `PYTHONIOENCODING=utf-8` |
| F48 | 6 | Arthur's hand-target offsets do not carry over; straight legs at rest → foot slide on any hips turn (fixed by a 0.4 cm hips drop) | §6.2: measure rest bones/footprint/base first, read the IK log; HANDBOOK §4.5: drop the hips 0.3–0.5 cm when they move |
| F49 | 6 | Card template has no stage-6 block; a second `decided_by:` silently overrides the first | SKILL §7.2: stage-6 fields, extend the existing `decided_by` |
| F50 | 6 | `clip_manifest.py` note says «по видео-референсу <reference>» even for a library pattern | `reference_kind` field or reworded note |
| F51 | 3 | A hero without metal: the metal pass crashes, and without it look-dev lacks `metal_mask.npy` (Leshen: zero mask written by hand) | tool: textures stage writes a zero mask |
| F52 | 3 | `team_mask_cloth_share` needs a «cloth» part even when the hero has none (Leshen: crows used) | tool: skip when `cloth_parts` is empty |
| F53 | 3 | Legless trunk: thigh weights grow downward and lift the roots (blobs 130–446 px); worked around with a junction to the base + a `root` rule for the base — legs bend only the middle of the trunk | HANDBOOK §4.2: document the trunk pattern (or a «trunk» weight kind); stage 6 must know |
| F54 | 3 | No `horn_claw` hero slot in the generic look-dev: skull, antlers, claws fall back to `legacy_bake` | HANDBOOK §4.4 / look-dev: add the slot |
| F55 | 3 | seams ray grid uses rest bounds + 0.1 m margin: raised long arms start rays inside the hand (false blobs 295/92 px); margin 0.2 used | tool: grid from posed bounds |
| F56 | 3 | uv charts checked for overlap at 512 px, gate is 0 px at 4K: slivers (11–17 px) get through (also Angel F30) | tool: check at atlas resolution |
| F57 | 3 | seams flags rays skimming flat ground at base level (rows of 9–14 px) | tool: ignore near-parallel hits |
| F58 | 3 | figure top = highest non-base vertex (antlers): skull height for `Specs()` measured by hand (budget 55 uu, bounds top 73.58 uu) | `scale.figure_top_part` key; HANDBOOK §2.10; card rule for head ornaments above the body |
| F59 | 3 | Probe height thresholds normalised by the full height incl. antlers: arm raises 0.373 vs 0.35, forearm 0.325 vs 0.30 | probes: normalise by body height |
| F60 | 3 | `compose.py` crashes on empty `preview.closeups`; TeamAccent manifest refuses a profile outside the repo | tool fixes |
| F61 | 3 | Caps on saddle-shaped shoulder openings fail hidden-at-rest (216 px); junction weights work | HANDBOOK closure table: junction weights as the alternative |
| F62 | 3 | Preview transparency bounce limit turns stacked culled layers black (false artefact in `roots_base` close-up) | tool: raise the bounce limit |
| F63 | 3 | F14 premise was wrong: Achilles' cloak is a thick shell with a hole cut on the inside (fixed by a 92 cm contact cap); the kilt is the real single sheet | HANDBOOK §4.2 closure: probe part thickness with a ray before choosing cap vs shell |
| F64 | 3 | П3-3 implemented: opt-in `rig.cloth_shell {parts, offset_mm}` (inner copy 0.3 mm, reversed winding, same UV, copied weights, bridged rim) in the rig stage; Medusa rig FBX byte-identical; 35 tests | **tool** `st_rig.add_cloth_shell`, `profile.cloth_shell`; HANDBOOK §4.2 to document |
| F65 | 3 | Swung weapon leaves the seams ray grid (rest bounds + margin): false 37 px blob; `seams.raycast.margin_m` 0.2 (also F55) | tool: posed bounds |
| F66 | 3 | `lookdev.py` `clean_labels` depends on class order and leaves orphan specks (accent leaked into a bronze core) | tool: iterate until stable |
| F67 | 3 | `lookdev_accent.py` ribbon takes one class (sandals 4.3 % could not be added); default opening 8/5000 erases thin straps | tool: several ribbons; document r 3 / 1000 |
| F68 | 3 | `ta_report` front-and-back visibility and the 90 % dress check do not fit caped, armoured heroes | decision П3-4b |
| F69 | 3 | seams counts a flipped real face lying 0.1 mm over the part's own cap as a hole | tool: pass when a same-part cap is within ε behind |
| F70 | 3 | Triangle budget: targets + caps + 2× shelled parts must stay ≤ 45k (Achilles 44 706) | HANDBOOK §4.2 retopo |
| F71 | 3 | Bronze: full tone correction gives pale brass, half gives darker bronze (0.73); leather stuck at the class floor (1.75× too bright); H2LD bronze reads coppery and glossy vs the concept's matte gold | HANDBOOK §4.4: damp metal gains (the concept's metal is paint, not PBR); UE capture decides |
| F72 | 3→4 | **Systemic:** stage 3 exits with a main class out of tone range, and T is capped at 1.0 only at stage 4 — both Leshen (bone 0.775) and Achilles (bronze 0.717) lost a full cycle (7.5 and 6.9 `rework_blender`). `ld_measure` suggestions were applied once / halved | SKILL §6 stage 3 exit: `t_cap` 2.0 from the tone table (CLI for `tools/art/acceptance/_tone.py` on the look-dev measure-report) or one more grade iteration from `gain_suggestion` |
| F73 | 4 | No profile route for a ragged Tripo base underside (Leshen: own base part, z ×1.27) | acceptance §9.3 row; option to flatten/cap the base rim or use the standard Ø0.30×0.06 base |
| F74 | 4 | WEAPON_HAND none: close-weapon repeats the upper figure, the attacking claws get no close-up | capture: frame close-weapon on `WEAPON_SOCKET_BONE` |
| F75 | 4 | codex exec picks up project skills even with `--ignore-user-config`: the acceptor read SKILL.md (outside its inputs) — Leshen and Achilles | §8.2: prompt line limiting the rubric to acceptance-and-blender.md |
| F76 | 4 | Card `ACCEPTOR_PROFILE` (opus-xhigh) vs the launcher's explicit Sol choice — no precedence stated | §8.1: explicit choice wins, recorded in NOTES |
| F77 | 4 | pose-04 (left thigh raise) is shot from the left, where the shield hides hip and kilt: the П3-3 cloth shell went unjudged | capture: second angle for pose-04 away from the shield (like pose-03b) |
| F78 | 4 | G-NAMES «figure top» undefined when a crest/headgear rises above the head (card vs launcher lesson disagreed) | rubric: defer to the card's height field, body mesh without the weapon |
| F79 | 4 | Tone-related rework items both heroes also include stage-3 artefacts the stage-3 agents did not see (Achilles: brown spear tip, skin-coloured nose guard, collar smears, elbow pinch; Leshen: faceted claws/antler tines) | stage 3 exit: executor checks the same close-ups the acceptor uses (`capture_acceptance_set.py` dry run) before handing over |
| F80 | 7 | UE import check `figure_height_as_profile` took the figure top from the whole skeletal mesh (Angel's sword tip 55.909 uu vs head 55.000) — false FAIL for any raised weapon or antlers | **fixed** `cd3ee7fe`: optional `candidate.figure_top_part` in the import profile |
| F81 | 7 | `h2anim_ue.py frames` read the removed `lightProfiles.cobble-probe` (ND-5, 2026-10-04) → KeyError; stage-6 UE frames impossible for every new hero | **fixed** `22c19667`: `--light-pinned <review report>` |
| F82 | — | The Codex desktop app runs `git diff` every few seconds on the main checkout and twice left a stale `.git/index.lock` (00:12, 01:06), blocking commits | orchestration: check lock age + live git processes before removing; consider closing the app's diff view during runs |
| F83 | 5 | A ragged base underside from the Tripo source is not fixable by `retopo`/`dense_regions` (QEM keeps the hanging bumps; 5.6 mm sag, 33 % of silhouette columns > 1 mm) | tool: opt-in base-bottom flatten in h2_bake (default off, Medusa determinism); acceptor's `tool` column should point to §9.3 «исходник Tripo: форма» |
| F84 | 5 | `dense_regions` = one box per part (`st_retopo.py:224`); faces on the box border do not count — results land 9–13 % below target | HANDBOOK §4.2: overshoot the target or allow several regions |
| F85 | 5 | Uniform tone gain has diminishing returns (AgX + clipping: 1.626/2.0/2.2 → 0.775/0.827/0.856), saturation drifts toward the family border; linear `gain_suggestion` ignores this; `tone.json` moves more than the visible EEVEE frames | HANDBOOK §4.4: iterate with the tone one-liner, not a single linear step |
| F86 | 5 | Determinism tolerances in HANDBOOK §4.3 cover bake only — nothing for render-derived look-dev/TeamAccent reports | HANDBOOK §4.3: list render-derived reports as allowed to differ |
| F87 | 5 | `work/timings.json` is overwritten when stages run one by one; Python stages have no `logs/<stage>.log` with a marker | tool: append timings; marker rule for Python stages |
| F88 | 5 | seams blob sensitive to tiny bounds shifts (antler tip +0.2 mm → unchanged trunk blob 1–2 → 8 px, at the threshold) | tool: grid anchored to rest bounds snapped, or blob threshold with hysteresis |
| F89 | 5 | Figure budget nearly spent (44 438 / 45 000) before choosing retopo values for a faceting fix | §9.3: check the budget headroom in `rig-report` first |
| F90 | 7 | `ue_hero_lookdev` default debug decode reads silk (class 11) as metal_forged (class 3): silk measured 0 px until a `debug_calibration` block; hair (legacy_bake) undetectable on the black backdrop | ue-import-package §3.2: `debug_calibration` |
| F91 | 7 | `um_masters build` fails on drift predating the run (RimColor in `M_UM_Figure`/`M_UM_BaseMarker` vs plan since FX-05 b425f06d); «repeat changes nothing» (§4.1) is false | decision needed: `--force` rebuild in a 7b window |
| F92 | 7 | MI creation in ue-import leaves `M_UM_Figure_v2` dirty (as for Medusa/Merlin/Harpy); must be discarded with `reload_packages` before closing the editor | ue-import-package §4: say so |
| F93 | 7 | Black leather / dark silk with library specular 0.5 and sheen 0.5 render 2–3× too bright in UE (Blender does not show it); Angel needed 3 LUT iterations (specular 0.2, sheen 0.06, leather roughness up) | HANDBOOK §4.4: dark-leather defaults (specular 0.2–0.3, sheen ≤ 0.1, roughness 0.55–0.6) |
| F94 | 7 | 7a evidence location (`$E` under docs/art-pipeline/evidence) conflicts with the 7a write scope; the asset's own evidence folder was used | ue-import-package §1: one place |
| F95 | 6/7 | Stage-6 validators miss the weapon rotating 60–90° inside a fixed fist (aim keys): Angel LungeAttack D=0 veto at clip acceptance | animation-vfx-sfx §6.3: weapon-to-hand rotation check + grip close-up on the Blender sheets |
| F96 | 7 | `h2anim_ue frames` shoots the grey carrier mesh without the base — acceptors notice | default `--base`; prompt template line |
| F97 | 7 | Acceptance frame copies 1920 px q88 (12.7 MB) vs HANDBOOK 1200 px q92 rule | tool/HANDBOOK: one rule |
| F98 | 7 | UE look-dev side frame is shot from the opposite side to the concept's side view (concept faces left; UE side shows the right side) — side-by-side comparison misleads | review-config: side from `SIDE_VIEW` |
| F99 | 4 r2 | §8.2 template has no slot for the previous fix list and per-item closure; executor's claimed status conflicts with §1 п.3 (executor reports not shown) — passed as one line «claim proves nothing» | §8.2: `{{PREV_FIX_LIST}}` + rule «r1 п.N: закрыт / не закрыт» in F/T rationale |
| F100 | 4 r2 | Executor said «claws closed» (dihedral p90 49→37°), the acceptor still saw facets on close-ups: numeric closure ≠ visual closure | §9: executor closes an item only on the acceptor's frame type |
| F101 | 4 | grep of events for «Failed to create unified exec process» false-positives (the rubric text contains it) | §8.4: parse `command_execution` items with `status: failed` |
| F102 | 4 | Full schema types `verdict_reason` as string and `source_defect` as boolean → a Workflow acceptor with the full schema cannot emit null → the `"null"` strings of F6 | §8.3: give the Workflow acceptor the strict *output* schema (nullable), as now done (`model-second-acceptor` workflow) |
| F103 | 6 | `clip_manifest.py` H2ANIM pins one spec per hero; a clip rework (new spec/run) must edit the registration line, or G-MANIFEST fails (validation sha ≠ registered run) | tool: spec override / history-aware lookup; animation-vfx-sfx §10: rework moves the registration |
| F104 | 5 | Jagged sole rims are in the Tripo high-poly (heel 2.4 mm, base teeth interlock) — no profile route (same class as F83) | tool: closure rim-smoothing option (z-smoothing of a loop within ~2 mm); §9.3 row «Tripo shape» |
| F105 | 5 | look-dev `bc_gate` hue ranges do not wrap 0°/360° (crest hue p50 356.9° → only 37 % in [0;15]) | tool: list of hue ranges / wrap-around |
| F106 | 5 | Metal-mask gates are AND of boxes and half-planes only, terms shared per part (nose guard needed a 90-box ladder) | tool: OR groups or per-zone terms |
| F107 | 5 | No profile means to repaint a visible band at a contact line (collar smears are Tripo texture, `bake.cage` cannot fix them; a hidden collar cap stretched the «trace» semantics) | tool: band repaint option with exclusion boxes; §9.3: such smears → not `bake.cage` |
| F108 | 5 | `ta_render` (EEVEE) varies ±0.01 between identical runs on a 220 px sample; П3-4b «threshold = measured floor» trips on noise | П3-4b: margin for noise (or deterministic render) |
| F109 | 5 | A new UV layout creates new isolated foreign-class texels; coordinate-box rules do not carry between runs | tool: auto-repaint isolated texels inside protected classes |
| F110 | 5 | Tone is measured in Cycles with LUT roughness 0.23, acceptance frames are EEVEE with ORM roughness 0.32–0.45: matched bronze reads paler on the frames | HANDBOOK §4.4 / acceptance §3: one renderer/roughness for tone and frames |
| F111 | 5 | `caps_hidden_at_rest` sum is brittle (unsunk collar cap 147 vs limit 147.07) | tool: relative threshold |

## Applied to the skill (stages 0–2, 2026-10-13)

| Finding | Where |
|---|---|
| F1, F2 | `SKILL.md` §6 stage 0 п.1 (ANATOMY per figure; `.gitignore` gate with `git check-ignore`) |
| F3, F4 | `references/tripo3d-stages.md` §5.2 п.5а (uuid via the newest tile), п.7 (report skeleton before `register-source`) |
| F5 | `references/tripo3d-stages.md` §1 (ledger limit = `limits.tripo.credits`, cap lifted by the user) |
| F6 | `references/acceptance-and-blender.md` §8.5 п.6 (null-strings, `item` pattern) |
| F7, F8 | `references/concept-sheet.md` §13.2 (licensed route, Codex first at 1c, facing check, claim queue) |
| F9 | `references/tripo3d-stages.md` §5.1 (Studio URLs, preloaded texture form, PBR button, rename, pipelining, timings); §2 + `SKILL.md` stage 0 п.4 (Windows-MCP route) |
| F10 | `references/tripo3d-stages.md` §6 step 9 (part boxes from the vertex buffer, glTF axes) |
| F11 | `references/tripo3d-stages.md` §6 steps 5, 11 (per hero / per batch) |

Not yet in tools (prototypes in `C:/tmp/concept-wave/`): facing gate in `check_concept_views.py`
(`side_mirror_check.py`), null-string cleaning (`finish_second.py`), stage-2 post steps (`post_h2.py`).
