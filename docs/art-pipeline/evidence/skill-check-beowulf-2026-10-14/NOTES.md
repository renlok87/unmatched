# Skill check run: Beowulf (ASSET-BEOWULF-001), 2026-10-14

User 2026-10-14 (answer to «what do we do with the roster»): «Одна фигура-проверка» — one new figure through the
refined 3d-model-pipeline skill (research and refinement a3dccf68..e80b634a), the rest of the roster after it. Tripo
window lifted the same day («Да, снять срок», 9728bca2).

Why Beowulf: paid 1b draft already in Studio (AN-45, not downloaded — RC-20), public domain, humanoid with a longsword
in the right hand (library pattern exists) and a round shield on the left arm, fur mantle, two-tier Tripo base — it
exercises the new rules (shield `weapon.extra_parts`, `rider_gap`, height team band, cloth) without the open roster
escalations.

## Findings (C-prefix: check run)

| # | Stage | Finding | Proposed fix |
|---|---|---|---|
| C1 | 0 / 1b | Claude in Chrome tools timed out (`tabs_context_mcp`) although the extension panel was open: the session was bound to another connected browser (macOS «Browser 1», `inUse`), not the user's Windows Chrome. `list_connected_browsers` → `select_browser <Windows deviceId>` fixed it; afterwards the export ran in an own tab without the user's cursor. | SKILL §6 stage 0 п.4 (Claude in Chrome probe) and `tripo3d-stages.md` §2: on a timeout first `list_connected_browsers` and select the browser with `onThisComputer: true`, only then fall back to Windows-MCP. applied: `tripo3d-stages.md` §2 (table, Claude in Chrome row); SKILL §6 stage 0 п.4 — not yet |
| C2 | 1b | The Studio form on the reopened draft task kept the last H2 settings («по частям» on, «Создать 60»): a careless click on «Создать» would have spent 60 on a wrong-mode generation. Export of an existing task needs only «Экспорт». | `tripo3d-stages.md` §5.2 п.11 (download later): open `/workspace/generate/<uuid>`, use only «Экспорт» → GLB; never «Создать» on a reopened task |
| C3 | 1c | `concept-sheet.md` §5.2 step 1: in Git Bash `ls` is aliased to `ls -F`, `EXE=$(ls -t …)` returns a path with `*` → exit 127 and a false «PROBE FAIL» | `command ls -t` in the probe |
| C4 | 1c | `codex_lane.py` on a 429 («exceeded retry limit») writes `.done "1 exit"` and keeps the claim, no retry; restart only by moving claim/.done by hand (not in §5.6). Cost here: first lane died in 6 s | detect 429 in `.err`, release the claim, retry with a pause |
| C5 | 1c | The Codex generator loads skills (AGENTS.md skill table via `npx openskills`, superpowers, imagegen) because the task header names the skill — against «Inputs are only the files listed» | B-CONCEPT-PACKAGE line «do not load skills»; drop the skill name from the `make_1c` header |
| C6 | 1c | CHECKLIST §8.1 has no tolerances: Codex rejected frame/background on < 1 % deviations (top 3.94 vs 4.0 %, background RGB 42 vs 46) with 0 WARN from the checks and spent its generations on it | judge frame/background by `check_concept_views` (PASS/WARN = ok), by eye only gross deviations |
| C7 | 1c | CORE-1C §8.2 does not name the pedestal material: front g1 came with the white draft pedestal; only Codex's own CORRECTION fixed it | line «pedestal: dark stone of the approved design» |
| C8 | 1c | `sheet_acceptance.py accept` needs a pre-created acceptance dir and an `--owned` file, neither described in §5.6 | auto-create the dir; document the `--owned` format |
| C9 | 1c | `sheet_acceptance.py` hard-codes `executor_session_id = "launcher:stage-1c-sheet-<date>"`; §11 wants the real id (F40) | `--executor-session-id` |
| C10 | 1c/4 | `.claude/workflows/second-acceptor.js` is model-shaped (frames.json, S/F/T/D); no tool prepares `acceptor-prompt-2.md` for a concept sheet (Leshen's was hand-written) — a trap at code 3 (not hit here: 8.8) | wrapper per card kind + a `prepare-second` step |
| C11 | 1c | §5.5 п.4 / §11.4 want a ledger row per Sol acceptance, but `07-prompt-templates.md` has no Codex acceptance template: `ledger.py add --template T-CODEX-ACCEPT` → ERROR (orchestrator, 12:30); generation row logged with T-CODEX-HEROVIEWS | add a T-CODEX-ACCEPT template (or name the template to use) |
| C12 | 1c | B-CONCEPT-PACKAGE contradicts itself: earlier-run files «stay as they are», but the 1c task asks to write README and verification.json; Codex chose to append | «append a 1c section, keep the 1a history» |
| C13 | 1c | Minor: long swatch names overlap on the sheet; `palette.json` lacks `asset_id` (§4.5 wants it); `make_1c` prints «view.; back»; the `limit_reached` line goes into the acceptor prompt even when empty | small tool fixes |

| C14 | 2 | `tripo3d-stages.md` §5.1 names the texture form `/texture-edit/<uuid>`; that address opens «Волшебная кисть» (Magic Brush, «Создать превью 5»). The texture generator is `/workspace/texture/<uuid>` (left toolbar «Текстура»). A click on the Magic Brush button would spend on the wrong tool | §5.1: `/workspace/texture/<uuid>`; warn that `/texture-edit/` is Magic Brush. applied: `tripo3d-stages.md` §5.1, §4 (rows «Текстура», «Правка») |
| C15 | 2 | «Удалить освещение» was OFF on the texture form (8K was remembered); §5.1 says the form remembers both from the last run. It does not: the toggle resets to OFF on every load of the form (checked again after the run), so it is not an account setting to restore. Without the check the BC would carry baked light | §5.1: always switch «Удалить освещение» on and zoom-check before «Создать текстуру». applied: `tripo3d-stages.md` §5.1 (steps 2 and the Studio notes), §4 row «Текстура», §5.3 step 3 |
| C16 | 2 | Claude in Chrome path worked end to end for stage 2 (file_upload into the four multi-view slot inputs by ref; no OS file dialog, no cursor) — faster and safer than the pilot's Windows-MCP path | `tripo3d-stages.md` §2: describe `find` → `file_upload` per slot as the main path. applied: `tripo3d-stages.md` §2 (table, Claude in Chrome row) |
Stage 1c result: Sol 8.8 pass r1 (S 2, C 1.5, Q 2, P 1.5), 33 PASS / 0 FAIL, `view.facing` 0.965 vs mirror 0.683;
6 image_gen (2 per view), ≈ 26 min incl. a 429 restart.

Stage 2 result: task ada45143 — generate 60 (20895 → 20835), texture 8K + remove lighting 30 (→ 20805), PBR 5
(→ 20800), 95 credits, three ledger rows; 20 parts, 1 993 213 tris in both GLBs; `post_h2.py` exit 0 (register-source,
previews). Previews checked by eye: one figure, one two-tier base, sword in the right hand, shield on the left arm, all
views consistent. Whole stage 2 through Claude in Chrome in ≈ 12 min without the user's cursor.

## Stage 3 findings (executor, 2026-10-14 ≈ 12:45–15:05)

| # | Stage | Finding | Proposed fix |
|---|---|---|---|
| C17 | 3 | `h2_bake/tests/test_w1d_reuse_determinism.py:65` asserted `profile_version == 1` for every committed profile — fails on the first v2 hero | fixed by the orchestrator: v1 only for `LEGACY_ASSETS` |
| C18 | 3 | HANDBOOK §4.4 `metal_f0` needs the `measure-report` of an earlier look-dev: a hero with boosted metals needs ≥ 2 look-dev runs, else `lut_metal_f0_plausible` FAIL | take the concept zones from the run's own measure pass |
| C19 | 3 | `lookdev_accent.py:686` `gold_unchanged_by_dye` fails on a view without trim pixels and always with `trim_class: none`; worked around with `trim_class: wool_coarse` | «not measured», as for cloth (cf. `dress_min_px`) |
| C20 | 3 | Skin anchor in `ld_measure` gave k 2.09 vs mean 0.92 — 9 of 11 classes out of tolerance | anchor `ld_measure` on the largest main class |
| C21 | 3 | `st_seams` loop gate measures «opening» to one covering neighbour: the hem cut-out of the mantle gave false 11–12 mm at vertices 1.3–6.8 cm from the belt | nearest neighbour per vertex |
| C22 | 3 | `st_close`: a cap seen only from its back face (`neck_top`, 1163 px, does not close the gap) passes; the acceptance capture draws the back face, UE culls it | flag such caps; backface culling in the capture |
| C23 | 3 | HANDBOOK §4.2 junction table: no cap is built for a thick shell with a saddle cut-out or a chest «ribbon» | write `rig.cloth_shell` as the fallback and its cost (≈ +7k tris) |
| C24 | 3 | `--reuse-from` needs `--stages all` (against «one stage at a time», HANDBOOK §4.3), copies foreign `work/smoke` into the new run; a `base_band.height_m` change recomputes the whole bake from uv although only the base mask changes | per-stage reuse; skip `work/smoke`; finer fingerprint for the team mask |
| C25 | 3 | H2.1 metal pass: one `target_srgb` per hero — iron, steel and gold cannot all be coloured | target per part or per term |
| C26 | 3 | Scout scripts (parts sheet in own colours, sections, loops, back-face search) were rewritten in a temp folder again | move to `tools/` (RA-12) |
| C27 | 0 | `make_tasks` writes `decided_by` as a string, SKILL.md §7.2 wants a mapping | write the mapping |
| C28 | 3/6 | `animation-vfx-sfx.md` §6.6 smoke run: the sample's `weapon_tip` / `hand_follow` targets are tied to its proportions → always FAIL on another hero | exclude them from the smoke verdict |

Stage 3 result: bake `20261014-h2-bake-t4` (profile_version 2), look-dev `20261014-h2-lookdev-t5`, TeamAccent t4; 20 parts
(mantle, tunic hem, shield + boss rigid on `arm_lower.L` (П3-2), sword `weapon` + pommel on `weapon.R` (П3-1), two-tier
base with the height team band [0.003, 0.029]); `rig.cloth_shell` on mantle/chest/neck (cap failed visibility); tris body
42 462 + sword 1 399 = 43 861, base 1 430. Handover checklist: tone code 0 / t_cap 2.0; 34 own frames looked at, 2 defects
fixed; base see-through 0.00 uu²; rider gap shield 0.00 mm / 0.12 mm in rest and 4 smoke clips; smoke clips PASS except
the sample-tied `weapon_tip` (C28); probes 14/14; TeamAccent 3.48 % (П3-4). Scouting ≈ 1.5 h of the 2 h 20 min stage.

## Stage 4 findings (launcher agent + orchestrator, 2026-10-14 ≈ 15:00–15:20)

| # | Stage | Finding | Proposed fix |
|---|---|---|---|
| C29 | 4 | Small gold accents (torc, guard, pommel, helmet rims) render as pale ivory vs gold on the sheet; neither the Sol rubric nor `tone.json` caught it (all classes ok except floor) — same as the stage-3 note (gold saturation −0.074) | tone: a check for small chromatic accent classes (share < 10 %), or a close-up crop of accents in the tone table |
| C30 | 4 | `close-hands`: for a shield arm the `hand.L` panel shows only the shield face, the left hand is not visible | capture: a shield-side angle for the hand panel when `weapon.extra_parts`/shield is present |
| C31 | 4 | With 1200 px frames (ДС-8) Sol still logged «Reconnecting 5/5» and fell back to HTTPS — RC-22 is not closed by the frame size | measure the request size; look at the number of frames (42 images) rather than their size |
| C32 | 0/4 | Card `STAGE3.executor.session` held `agent:stage3-beowulf`, the real agent name was `beowulf-stage3` | the launcher writes the actual id (RA-21) |
| C33 | 4 | The «item only S/F/T/D…; empty field = JSON null» reminder (§8.5 п.6) had to be added to both prompts by hand | move it into the §8.2 template |
| C35 | 4 | `finish_second.py` expects `{"result": [...]}` (the workflow notification shape); the journal / workflow return is a bare list → `TypeError: list indices must be integers` | accept both shapes; document the input in §8.3 |
| C34 | 4 | Orchestrator: passing the strict output schema to `second-acceptor` — the Cyrillic `description` fields came out mangled through a cp1251 print; worked around by stripping descriptions/titles | ship an ASCII args file (e.g. `_output_schema.py --workflow-args <kind>`) or have `prep` write `second-acceptor-args.json` |

Stage 4 r1: Sol 6.1 xhigh — S 2 / F 1.5 / T 1.5 / D 1.5 = 8.1, pass, `rework_fix_list` [], 8 known issues (neck flats behind
the beard, angular mantle strands, right sleeve armhole cut in `pose-05`, grey-blue strokes on the fur, thigh through the
hem in `pose-04b`); gates all PASS and recomputed by `--check-files`; validate_card code 3 → second acceptor Opus via
`second-acceptor` workflow. Capture 19 s, Sol 11 min.

Stage 4 second acceptor: Opus xhigh via `second-acceptor` — S 2 / F 1.5 / T 1.5 / D 1.5 = 8.1 pass; pair final 8.1 pass
(finish_second exit 0). Model accepted at r1 — no stage 5.

## Tripo tools experiment (separate agent, user: «Да, но сделай это в отдельном агенте…», no credit limit)

175 credits (20 800 → 20 625, 16 ledger rows AN-45). Report: `tripo-tools-experiment/README.md`, numbers and 11 frames.
Verdict: keep the skill's route (H2 «по частям» + stage 3 in Blender); update the `tripo3d-stages.md` §4 table.
- Smart Mesh P2.0 (new): good-looking mesh but a new generation, not a retopology of the accepted H2; one welded mesh
  (sword fused to the hand), no parts, texture-step UV only (4 096 islands, 43 %); overshoots the target ×1.1–1.27.
- Remesh: ceiling 10 000 quads, coarse face. Smart UV: refuses multi-part models (props only). Pack UV on export (new):
  one 8K atlas from 20 parts but 4 009 ragged islands.
- Auto-rig «Humanoid» (UE5 / Mixamo): 61–65 bones, no weapon bone; left/right now correct, but the base is weighted to
  feet/calves, on the H2 clone the sword to the fingertips and the head to the clavicles (frame 06).
- Animation presets (free) / Text-to-motion (20): 3–6× our D-11 lengths, the base travels with the feet.
- New: Smart Mesh P2.0 and P1.0 Fast; texture 4K = 20 (not 30); Multi-stage Motion 20; export options Pack UV, Export
  Skeleton, clip choice, «Animation stay in Place»; image models (GPT Image 2, Midjourney v8.2, Nano Banana).
- Traps: Smart Mesh privacy resets to «Sharing Only» on every load; skeleton export from the Model page gives a broken GLB
  (export from the Animate page works).

| # | Stage | Finding | Proposed fix |
|---|---|---|---|
| C36 | 3/4 | The experiment measured 6 099 flipped UV triangles and ~30 % UV overlap in our look-dev body while `uv-report.json` says 0. Orchestrator check: 6 099 = the `cloth_shell` inner faces (3 999 + 1 700 + 400: same UV0, reversed winding by design, П3-3) — not a defect, but any external UV measure misreads it | tag shell faces (attribute / vertex group) and exclude them in UV checks; one line in HANDBOOK §4.2 `cloth_shell` |
| C37 | 2 | `tripo3d-stages.md` §4 is out of date (Smart Mesh row, 4K price 20, Smart UV refusal text, auto-rig and animation facts, new export options, Smart Mesh privacy reset) | update §4 from `tripo-tools-experiment/README.md`. applied: `tripo3d-stages.md` §4 (intro + rows), §3 (prop rows), §5.3 (Smart Mesh route, decision 2026-10-14); `animation-vfx-sfx.md` §6.1; SKILL §3, §6 stage 6 п.2; HANDBOOK §5 |

## Stage 6 findings (executor, 2026-10-14 ≈ 15:20–15:56; orchestrator analysis)

| # | Stage | Finding | Proposed fix |
|---|---|---|---|
| C38 | 3/7 | Full repeat of look-dev t5 + TeamAccent: code 1 only on `reports/measure-report.json` (one mask pixel 2176 → 2175, hue 25.2 → 24.7) with all 26 maps / LUT / FBX identical: `determinism.py` compared it as plain JSON | **fixed (orchestrator):** `measure-report.json` → render rule; test; HANDBOOK §4.3 table |
| C39 | 3 | ДС-7 «look-dev and TeamAccent in their own repeat folders» cannot work: TeamAccent writes into the look-dev run and the comparison takes the union of files | **fixed:** HANDBOOK §4.3 — one repeat folder, `ld_manifest` + `ta_manifest` transfer |
| C40 | 6 | `weapon_tip` check and `grip_check` take the base top from its highest vertex (a 3 mm bump at 6.00 cm vs the visible 5.68 cm surface) → the sword tip must float 2.4 mm or the gate fails | base top = robust height (percentile of the top-facing faces) |
| C41 | 6 | Legs fully straight in rest (16.328 of 16.329 cm): frames where the leg IK cannot reach slide the foot up to 0.48 % H (limit 0.5 %); a pelvis drop fixed it | §6.2: check `ik_unreached_frames` and the foot-slide margin |
| C42 | 6 | Copying a pattern spec needs per-hero rest axes in aim (`from`/`from2`) and anchor / tip targets within the arm's reach — not in the §6.2 table; reach shortfall `follow_*_reach_deficit_cm` should be −0.5…−1.5 cm | §6.2 table rows |
| C43 | 3/6 | No validator catches openings uncovered by motion (top of the right sleeve from behind in LungeAttack f4 / DeathSettle f6–21; fist hole when the sword turns); only close-ups do — the §6.6 smoke run has no close-up step, so stage 3 missed them (same class as Achilles F129) | add `clip_closeups.py` on the smoke clips to the stage-3 handover checklist |
| C44 | 6 | The library sword death pattern turns the sword 154–170° in the fist — against the F95 veto rule; exposes the grip channel of any Tripo fist | library DeathSettle with a fixed grip; orchestrator asked the executor to re-author Beowulf's |
| C45 | 6 | `clip_closeups.py` has no default shots; the skill gives no standard shot list | default shot list per clip role |
| C46 | 6 | The filled sample prompt in §10 (Achilles r2) still carries the old OEM block; no template had `{{KNOWN_LIMITS}}` | refresh the sample |
| C47 | 6 | `rider_gap` auto-scan paired the shield with its own boss; the handle-to-hand pair needs a manual `--pair`; a constant non-rider gap (shield to forearm 5.6 mm) can only FAIL | exclude parts on the same bone; allow a «designed gap» per pair |

Stage 6 result: Angel r2 pattern on Arthur's sword clips, shield as `extra_parts`; h2anim_run code 0, validate 4/4, contact
4/4, foot slide ≤ 0.28 %, sword/shield through body 0, rider gap shield 0.00 / 0.12 mm in all clips; manifest and sheet
checks PASS; HIT_TYPE BLADE; prompts + known-limits ready. Bake t4 full repeat: pass. Sleeve-top cut edge left for the
clip acceptor at 7a.2 on purpose (test of the late-fix route).

## Stage 7a findings (executor, 2026-10-14 ≈ 16:10–16:55)

| # | Stage | Finding | Proposed fix |
|---|---|---|---|
| C48 | 7a | UE look-dev class decoding confuses chainmail (`steel_blued`) with fur (`wool_coarse`) — their ID colours are almost equal after the render; small gold decodes partially, its brightness jumps between runs with no material change (1.54 → 1.20 → 1.05) | wider ID palette distance; minimum pixel share per class before a verdict |
| C49 | 7a | First UE iteration starts from the library sheen 0.35 on cloth/fur — third hero in a row with the same washed-out fur (F139) | write the F139 starting values into the LUT at the Blender look-dev stage |
| C50 | 7a | `write_review_config` does not carry the base parameters into `verify`; `apply-mi` does not update the expected values after its edits — both edited by hand | carry base scalars; `apply-mi --update-verify` |
| C51 | 7a.2 | Stage 6 left no `run-acceptor.ps1` and the skill has no template for the clip acceptor launcher — written by hand | tool `ue7a/run_clip_acceptors.py` (parallel Sol + validate) |
| C52 | 7a | `env_bench_fixtures.cts` does not run on the host checkout: `backend/node_modules` is empty (lives in a container volume); ran in a temp folder inside the backend container | run inside the container by a documented command, or vendor the generator |
| C53 | 6/7a | `clip_manifest` writes the wrong provenance for BEO-* (Medusa + ARTH video instead of the Angel r2 pattern) | provenance from the spec's `pattern` / `MOTION_SOURCE` |
| C54 | 3/7a | The vertex-mask team ring (height band) has a toothed upper edge on a close side frame (2–3 teeth, a dark wedge back-left at the bottom) — fine at K2 | smooth the band edge (face split along the height plane) |
| C55 | 6 | The clip acceptor prompts again carry a wrong stage-6 executor id (repeat of C32) | launcher writes the actual id |

Stage 7a result: one import run (`technically_imported`, 27/27, idempotent), verify 14/14; vertex-mask base ring even at
K2 for P1/P2; UE look-dev r1 → `apply-mi` r2, r3 (fur sheen 0 / roughness 0.85 → 1.17× concept, beard FixGainA 0.4,
leather, metals): 7/9 classes in tolerance, linen and metal_forged at the noise band; small gold reads as gold in UE (C29
was a Blender-preview effect), helmet bands still paler (0.36 vs 0.44). Clips accepted at 7a.2 first time by Sol: Idle
8.8, LungeAttack 8.8, HitReact 9.4, DeathSettle 8.8 — the sleeve-top cut edge went to `known_issues` (D 1.5), no «stage 5
model» item → no late fix. Registrations: CUE-011/013, cook dirs, fighter names (Беовульф, Виглаф), bench variants of
both boards. 23 new `.uasset`. ≈ 45 min.

## Stage 7b findings (executor, 2026-10-14 16:55–17:45)

| # | Stage | Finding | Proposed fix |
|---|---|---|---|
| C56 | 7b | de011: `UnrealEditor-Cmd` crashed 0xC0000005 after `LogExit` (assets saved, Dissolve test PASS); the tool does not flag a non-zero editor exit | WARN on a non-zero `_editor.exit` after a clean `LogExit` |
| C57 | 7a/7b | `asset-card.yaml` had no `STAGE7A` block (the 7a executor should write it); `registration_check` does not check card blocks | 7a writes `STAGE7A`; `registration_check` checks the stage blocks |
| C58 | 7b | `render_bench` `faceRoiSkipped` refers to `SK_Merlin_H2LD`: the face-brightness ROI ignores `-BenchFocusFighter` though K2×5 is shot on the focus hero | ROI from the focus fighter |
| C59 | 7b | Stage-7b writes to `asset-registry.json` (hand-formatted) and `03-asset-registry.csv` (CRLF) have no tool — scripts in `$W` | one registry writer for the status table (registration §10) |
| C60 | 7b | `sheet.py` README template lists PNGs and needs hand edits; by ДС-8 only JPEGs go to git | template from the JPEG list |
| C61 | 3/6/7 | A black gap between the mantle collar and the back of the helmet in DeathSettle f16–21 — visible in the game at K2×1.6 (≈ 5×10 px), K1 2–3 px (reads as a shadow); likely the `neck_top` cap removed at stage 3 (C22). Not caught by any validator nor by the clip acceptors (class C43). Orchestrator decision (delegation): **known issue** for the check figure, not a late fix — recorded in README / CSV / `STAGE7B.open` | the C43 fix (close-ups of the smoke clips at stage 3) and a cap whose back face is culled (C22) |
| C62 | 7b | AN-18 is still the longest 7b step: 19 of ≈ 37 min (563 s per board) for one hero | K1 once per batch (`--k1-from`), K2 per hero |

Stage 7b result: de010/de011 `--only Beowulf` (no MVP re-saves), Specs() + tests + AudioBank BLADE; build 16 s; S08
393/393; `registration_check` 12/12; one package (1 min 33 s, stamp 69fd9bf8 + 7b); -Bench both real boards — painted
Marmoreal backdrop, Sarpedon lit3d path 1, all figures v2, Beowulf in concept colours with the team belt and ring; RENDER
fingerprints 6/6; AN-145…148 problems 0; cost K1 2.16 ms / K2×5 2.23 ms GPU (within budget); registries per the status
table; pytest 931 passed / 3 xfailed. ≈ 50 min.

## Check-run timeline (Beowulf, 2026-10-14)

| Stage | Time | Result |
|---|---|---|
| 1b download + orthos | 11:50–12:00 | paid draft exported via Claude in Chrome |
| 1c views + sheet | 12:00–12:30 | Sol 8.8 pass r1 |
| 2 Tripo H2 | 12:15–12:40 | 95 credits, 20 parts |
| 3 Blender build | 12:45–15:05 | handover checklist pass (1.5 h of scouting) |
| 4 acceptance | 15:00–15:30 | Sol 8.1 + Opus 8.1 → pass r1 (no stage 5) |
| 6 clips + determinism | 15:20–16:10 | 4 clips, full determinism pass after the C38 fix |
| 7a UE | 16:10–16:55 | one import, apply-mi r3, 4 clips pass first cycle |
| 7b game | 16:55–17:45 | packaged, both boards, AN-18 |

≈ 6 h wall clock for one figure from 1b to the game (pilot: 7–10 h per figure with r2/r3 reworks). 62 findings.
