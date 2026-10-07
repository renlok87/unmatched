# CX-32 fix1 - corrective Codex run for SC-24 ... SC-30 (PAUSE and settings)

Written by Claude after the single review pass (07 §5) of run 1 (Codex thread `01a11766-6382-…`, 2026-10-07
22:25-22:48 +05:00). Verdict of run 1: fix-needed, within the cards. This is the one corrective run of each of the
seven cards (05 §1.4); there is no second one.

| field | value |
|---|---|
| id | CX-32 fix1 (cards SC-24, SC-25, SC-26, SC-27, SC-28, SC-29, SC-30) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | the seven `art/imagegen/sc24…sc30-*-codex/` packages of run 1 |
| image generations allowed | 0 |

## Task

```text
Corrective run CX-32 fix1 for the seven packages of series CX-32. Read every file as UTF-8. The task of run 1 stays
valid: docs/game-design/visual/06-tasks/prompts/SC-24-series.codex.md and the seven card files it names. Write only
inside the seven package folders art/imagegen/sc24-pause-codex/, sc25-settings-sound-codex/,
sc26-settings-language-codex/, sc27-settings-scale-codex/, sc28-settings-game-codex/, sc29-settings-hints-codex/,
sc30-settings-graphics-codex/ and their scraped-data/derived/<set>-codex/ folders. No git, no MCP, no network, no
npx / npm / pip or any other package tool (run 1 called npx openskills, which tried the network: do not), nothing
under unreal/ (read only S08UserSettings.h if you need it), no image generation.

What the review found and what to change:

1. Overlays are not keyed (all seven packages, every comparison/<card>-overlay-*.png and its -gray.png). The outlines
   on the drawing carry no names or numbers, so the legend R01 ... Rnn on the right cannot be matched to a rectangle
   except by reading coordinates (ВР-VS5-SC24-10 asks for labels at the frame or a legend keyed to the frame).
   Fix: put the legend number (R01, R02, ...) of every rectangle on the drawing as a small tag (Roboto Regular, at
   least 14 px on the overlay, text.primary on a card.navy tag box with a 1 px panel.edge-coloured keyline), at the
   rectangle's top-left corner inside it when it fits, otherwise just outside with a 1 px leader line. Tags never
   overlap each other, the legend or another rectangle's tag; measure it and record the count (must be 0) in
   verification.json next to the existing overlay label overlap. You may enlarge the overlay canvas; never shrink
   the schema.
2. Hidden scroll rows are drawn over the footer (the scroll frames: SC-24 and SC-25 at 1080p 150 % and 720p 150 %,
   and every other frame whose rows scroll). Fix: in the overlay draw only what is visible inside the RowsPanel
   viewport (clip to RowsPanel; a row cut by the viewport edge is drawn clipped); rows hidden by scrolling are not
   drawn. In the legend list them after the visible ones under a line «скрыто прокруткой» with their content-space
   y. In layout-geometry.json give every row and child "visible": true | false and, for hidden ones, the
   content-space rectangle. The mockup PNGs already hide them; do not change the mockups.
3. README typography (all seven READMEs): numbers and units are glued to words («PauseModal720 su», «padding16»,
   «x148», «Ползунок200su», «на720p150%»). Rewrite those sentences with normal spaces («PauseModal 720 su»,
   «padding 16 su», «x 148 su», «720p 150 %»); keep the content. Add a section «fix1» at the end (before
   «Воспроизведение»): what changed (keyed overlays, clipped scroll rows, typography) and that the mockups did not
   change. Keep the status «предложено».

Do not change anything else: the mockups in scraped-data/derived/ must stay byte-identical (rebuild them only if
your pipeline needs it and prove in verification.json that every mockup sha256 equals run 1; list any difference as
a failure). The sc24_pause.py copies in SC-25 ... SC-30 must stay equal to the final sc24_pause.py of SC-24; if you
change the overlay code, put it in the module that already draws the overlays and keep that chain (update
copy-provenance.json if a copied file changes, and say so in README).

After the changes: re-open and look at every regenerated overlay (colour and grey, every canvas and frame kind) and
record them in visual-review.json; update verification.json (keep the 07 §1.2 keys, outside_folder [] and every
run 1 measurement; add the tag overlap count, the hidden-row lists and the mockup-unchanged check);
rebuild manifest-sha256.json of each package (every package file except itself, every derived file, the inputs).
```
