# CX-29 fix1 - Codex corrective series task (SC-08 ... SC-13)

Written by Claude by hand: the one corrective run of the CX-29 series (05 §1.4, 07 §5: at most one corrective run).
It orders the six per-card fix files; each lists exactly what to fix.

| field | value |
|---|---|
| id | CX-29 fix1 |
| date | 2026-10-07 |
| decisions | ВР-VS4-SC08-14, -15, -16, ВР-VS4-SC12-02 (by delegation, Claude review of CX-29 run 1) |
| image generations allowed | 0 |

## Task

```text
Series CX-29 fix1: six corrective tasks, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-08.fix1.codex.md -> art/imagegen/sc08-lobby-list-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-09.fix1.codex.md -> art/imagegen/sc09-lobby-create-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-10.fix1.codex.md -> art/imagegen/sc10-lobby-create-ai-codex/
4. docs/game-design/visual/06-tasks/prompts/SC-11.fix1.codex.md -> art/imagegen/sc11-lobby-code-codex/
5. docs/game-design/visual/06-tasks/prompts/SC-12.fix1.codex.md -> art/imagegen/sc12-lobby-empty-codex/
6. docs/game-design/visual/06-tasks/prompts/SC-13.fix1.codex.md -> art/imagegen/sc13-lobby-error-codex/
Finish each fix (rebuild, verify, open every changed PNG in colour and grey on all four canvases, README) before the
next. The base tasks SC-08...SC-13.codex.md and the series notes SC-08-series.codex.md still apply (data, decisions
ВР-VS4-SC08-01...13 and the card decisions, no password or token in any file). Each package writes only into its own
folder and its own scraped-data/derived/<set>-codex/ folder (never change inputs/). No git, no MCP, no network,
nothing under unreal/, no image generation. Do not change the SC-01 library copy (screen_mockup_base.py stays
byte-identical to art/imagegen/sc01-screen-base-codex/_tools/) or the generator snapshot (draw_icons_v3_snapshot.py).
The FINAL sc08_lobby_list.py of package 1 is copied unchanged into packages 2-6 (and the final sc09_lobby_create.py
into package 3).
```
