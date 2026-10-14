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
| C1 | 0 / 1b | Claude in Chrome tools timed out (`tabs_context_mcp`) although the extension panel was open: the session was bound to another connected browser (macOS «Browser 1», `inUse`), not the user's Windows Chrome. `list_connected_browsers` → `select_browser <Windows deviceId>` fixed it; afterwards the export ran in an own tab without the user's cursor. | SKILL §6 stage 0 п.4 (Claude in Chrome probe) and `tripo3d-stages.md` §2: on a timeout first `list_connected_browsers` and select the browser with `onThisComputer: true`, only then fall back to Windows-MCP |
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

| C14 | 2 | `tripo3d-stages.md` §5.1 names the texture form `/texture-edit/<uuid>`; that address opens «Волшебная кисть» (Magic Brush, «Создать превью 5»). The texture generator is `/workspace/texture/<uuid>` (left toolbar «Текстура»). A click on the Magic Brush button would spend on the wrong tool | §5.1: `/workspace/texture/<uuid>`; warn that `/texture-edit/` is Magic Brush |
| C15 | 2 | «Удалить освещение» was OFF on the texture form (8K was remembered); §5.1 says the form remembers both from the last run. It does not: the toggle resets to OFF on every load of the form (checked again after the run), so it is not an account setting to restore. Without the check the BC would carry baked light | §5.1: always switch «Удалить освещение» on and zoom-check before «Создать текстуру» |
| C16 | 2 | Claude in Chrome path worked end to end for stage 2 (file_upload into the four multi-view slot inputs by ref; no OS file dialog, no cursor) — faster and safer than the pilot's Windows-MCP path | `tripo3d-stages.md` §2: describe `find` → `file_upload` per slot as the main path |
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
