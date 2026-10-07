# CX-28 fix1 - Codex corrective series task (SC-06, SC-07)

Written by Claude by hand: the one corrective run of the CX-28 series (05 §1.4, 07 §5: at most one corrective run).
It orders the two per-card fix files; each lists exactly what to fix.

| field | value |
|---|---|
| id | CX-28 fix1 |
| date | 2026-10-07 |
| decisions | ВР-VS4-SC06-08, ВР-VS4-SC07-05, ВР-VS4-SC03-09 (by delegation, Claude review of CX-28 run 1) |
| image generations allowed | 0 |

## Task

```text
Series CX-28 fix1: two corrective tasks, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-06.fix1.codex.md -> art/imagegen/sc06-login-form-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-07.fix1.codex.md -> art/imagegen/sc07-login-errors-codex/
Finish each fix (rebuild, verify, open every changed PNG, README) before the next. The base tasks SC-06/07.codex.md
and the series notes SC-06-series.codex.md still apply (credentials rule ВР-VS4-SC06-01 included: no password value,
length or token in any file). Each package writes only into its own folder and its own
scraped-data/derived/<set>-codex/ folder. No git, no MCP, nothing under unreal/, no image generation. Do not change
the SC-01 library copy (screen_mockup_base.py stays byte-identical to art/imagegen/sc01-screen-base-codex/_tools/) or
the generator snapshot (draw_icons_v3_snapshot.py).
```
