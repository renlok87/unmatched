# Z-Code calibration C1 — blind comparison of hero showcase figures (X vs Y)

Context (do not act on it beyond this task): this is a calibration run of the Z-Code side model for the
3d-model-pipeline skill of the project `unmached`. Read nothing outside the folder named below.

You are an independent art director. You compare two variants, **X** and **Y**, of the 3D hero figures shown in the
hero-select niches and on the VS splash of a digital adaptation of the board game Unmatched (heroes King Arthur and
Medusa; dark "studio" niches lit in team colours; the accepted in-game HUD style is navy + marble + bronze + gold). Both
variants are rendered live in the game with the same camera, lights and frame; only the figure assets differ. You are
not told how the variants were made. Judge only what you see.

Images (open each at full size; they are also attached to this message):
- `docs/art-pipeline/evidence/skill-batch-2026-10-20/zcode-calibration/c1-arthur-medusa-blind/in/r3-X-vs.jpg`,
  `.../in/r3-Y-vs.jpg` — the VS splash (1920×1080)
- `.../in/r3-X-niches.jpg`, `.../in/r3-Y-niches.jpg` — the two niches (Arthur, Medusa) and 2× close-ups of the upper
  body (2000×730)

Score each variant 1–10 on:
1. Detail and sharpness of the sculpt and the painted surface (armour engraving, faces, snakes, folds) at the real size
   and in the 2× crops.
2. Material and colour quality (metal, cloth, skin; readable, premium, not plasticky or washed out).
3. Readability of the team colours (left = gold team, right = silver-blue team) on the figure and its base.
4. Defects (extra or duplicated geometry, holes, seams, floating parts, wrong proportions; 10 = no defects) — list each
   one you find and where it is.
5. Fit to a premium fighting-game select screen in this art direction (overall impression).

Then: **overall winner (X or Y)**, a margin (clear / slight / tie), and the 3 most important reasons. Be concrete
(region of the image, pixel coordinates if you can).

Output: write the review in Russian to
`docs/art-pipeline/evidence/skill-batch-2026-10-20/zcode-calibration/c1-arthur-medusa-blind/REVIEW-zcode.md`
— only that file. Do not create or change anything else, do not open other files or folders of the repository, do not
run git, do not commit. Start the file with one line `MODEL: <the exact model name you are running as>` and a line
`IMAGES_SEEN: <yes|no — whether you could actually see the pixels of all four images>`. Put the scores in a Markdown
table with columns `Критерий | X | Y`. Finish with one line: `WINNER: X|Y|TIE`.
