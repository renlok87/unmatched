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
