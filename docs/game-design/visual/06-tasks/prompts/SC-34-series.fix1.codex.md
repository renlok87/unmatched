# CX-34 fix1 - corrective Codex run for SC-34 ... SC-38 (GAMEOVER and ABORTED)

Written by Claude after the single review pass (07 §5) of run 1 (Codex thread `01a11792-509b-…`, 2026-10-07
23:13 - 2026-10-07 23:59 +05:00). Verdict of run 1: fix-needed, within the cards. This is the one corrective run of
each of the five cards (05 §1.4); there is no second one.

| field | value |
|---|---|
| id | CX-34 fix1 (cards SC-34, SC-35, SC-36, SC-37, SC-38) |
| date | 2026-10-08 |
| template | T-CODEX-LAYOUT |
| packages | the five `art/imagegen/sc34…sc38-*-codex/` packages of run 1 |
| image generations allowed | 0 |

## Task

```text
Corrective run CX-34 fix1 for the five packages of series CX-34. Read every file as UTF-8. The task of run 1 stays
valid: docs/game-design/visual/06-tasks/prompts/SC-34-series.codex.md and the five card files it names. Write only
inside art/imagegen/sc34-gameover-victory-codex/, sc35-gameover-defeat-codex/, sc36-gameover-board-codex/,
sc37-gameover-again-codex/, sc38-aborted-codex/ and their scraped-data/derived/<set>-codex/ folders (never change
the inputs/ subfolders). No git, no MCP, no network, no npx / npm / pip or any other package tool, nothing under
unreal/, no image generation.

What the review found and what to change:

1. Overlays are not keyed (all five packages, every comparison/<card>-overlay-*.png and its -gray.png). The legend
   lists 01 ... nn with names and x, y, w, h, but the outlines on the drawing carry no number, so a rectangle can be
   matched to its name only by reading coordinates (ВР-VS5-SC34-09: labels at the frame or a legend keyed to the
   frame). Fix: put the legend number of every rectangle on the drawing as a small tag (Roboto Regular, at least
   14 px on the overlay, text.primary on a card.navy tag box with a 1 px keyline in the panel.edge colour) at the
   rectangle's top-left corner inside it when it fits, otherwise just outside with a 1 px leader line. Tags never
   overlap each other, the legend or another tag; measure it and record the count (must be 0) in verification.json
   next to the existing label overlap. You may enlarge the overlay canvas; never shrink the schema. SC-34: add one
   overlay per canvas for the draw frame too (comparison/SC-34-overlay-draw-<res>-<scale>.png and -gray), since its
   element set differs from victory. SC-37: one overlay per canvas for again and again-busy if the geometry differs,
   otherwise say in README that they share it.
2. SC-37, class S (1080p 150 % and 720p 150 %): the three-button row does not fit the 680 su modal: the buttons sit
   about 8 su from the modal edges, under the 16 su minimum of ВР-VS5-SC34-03, and the key chips were dropped.
   Decision ВР-VS5-SC37-06 (Claude, by delegation): in VS_AI mode with three buttons, class S uses the class L modal
   width 760 su (both class S canvases are at least 1137 su wide, so 760 + 2 x 16 su margin fits); the modal height
   stays the class S 560 su and the class S vertical layout stays. Restore the key chips «V» and «Enter» when the
   row then fits the modal width minus 2 x 24 su (it measured 705.75 su of 712 in class L); keep the 16 su gaps if
   they fit, else 8 su. Re-render the eight SC-37 mockups of class S (again and again-busy, colour and grey) and
   their overlays; the class L frames must stay byte-identical. Update the acceptance line of the button row (it must
   pass now) and README (decision ВР-VS5-SC37-06, what changed).
3. README of every package: add a section «fix1» at the end (before the reproduction notes): what changed and which
   files were regenerated. Keep the status «предложено».

Do not change anything else. Every mockup in scraped-data/derived/ except the eight SC-37 class S frames (and any
comparison sheet in derived built from them) must stay byte-identical: prove it in verification.json (sha256 of
each mockup before and after) and list any other difference as a failure. If you change the overlay code in
sc34_gameover_victory.py, the copies in SC-35, SC-36 and SC-37 must stay equal to the final SC-34 script; prefer to
put the overlay change in each package's own module or a shared support module and keep copy-provenance.json true.

After the changes: re-open and look at every regenerated PNG (overlays and the SC-37 class S mockups, colour and
grey) and record them in visual-review.json; update verification.json (keep the 07 §1.2 keys, outside_folder [] and
every run 1 measurement; add the tag overlap count and the mockup-unchanged check); rebuild manifest-sha256.json of
each package (every package file except itself, every derived file, the inputs).
```
