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
| F8 | 1c | — (running) | |
