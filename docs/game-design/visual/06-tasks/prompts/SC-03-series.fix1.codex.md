# CX-27 fix1 - Codex corrective series task (SC-03, SC-04, SC-05)

Written by Claude by hand: the one corrective run of the CX-27 series (05 §1.4, 07 §5: at most one corrective run).
It orders the three per-card fix files; each lists exactly what to fix.

| field | value |
|---|---|
| id | CX-27 fix1 |
| date | 2026-10-07 |
| decisions | ВР-VS4-SC03-09, ВР-VS4-SC04-01, ВР-VS4-SC04-02 (by delegation, Claude review of CX-27 run 1) |
| image generations allowed | 0 |

## Task

```text
Series CX-27 fix1: three corrective tasks, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-03.fix1.codex.md -> art/imagegen/sc03-boot-loading-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-04.fix1.codex.md -> art/imagegen/sc04-boot-error-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-05.fix1.codex.md -> art/imagegen/sc05-boot-resume-codex/
Finish each fix (rebuild, verify, open every changed PNG, README) before the next. The base tasks
SC-03/04/05.codex.md and the series notes SC-03-series.codex.md still apply. Each package writes only into its own
folder and its own scraped-data/derived/<set>-codex/ folder. No git, no MCP, nothing under unreal/, no image
generation. Do not change the SC-01 library copy (screen_mockup_base.py stays byte-identical to
art/imagegen/sc01-screen-base-codex/_tools/) or the generator snapshot (draw_icons_v3_snapshot.py).
```
