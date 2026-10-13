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
