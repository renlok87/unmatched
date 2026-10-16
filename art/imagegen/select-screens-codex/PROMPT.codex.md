# Codex task — SEL: hero select / board select / VS screen references (ImageGen + real data overlay)

Context: "Unmatched" — digital adaptation (Unreal Engine 5) of the Restoration Games board game: 1v1 online duels of
heroes on illustrated boards. We are redesigning the pre-game screens in the spirit of fighting games — Mortal Kombat 11 /
Mortal Kombat 1 and Injustice 2 (big full-body fighters P1 left / P2 right, compact roster strip, lock-in moment, stage
select with a big preview, a VS splash) — but in OUR art direction, the accepted in-game HUD "Стол" (table):
dark navy panels (#14161C … #1B2433) with a thin cream/bronze frame (cream #ECE3CF, bronze #8C6B3F), gold accents
(#C9A45C / #E8C06A), small greek-meander corner ornaments, polished dark green-grey marble with bronze rims for hero
plates, serif display font for titles (Philosopher-like), condensed sans for small text. Not MK neon, not sci-fi,
no blood, no lightning frames. Museum-plaque elegance + the drama of a fighting-game select screen.

Team colours (fixed, from code): P1 = gold #E8C06A, P2 = silver-blue #5A7F9F (NOT blue/red).

Read first (view the images, do not modify them):
- Design spec: `docs/game-design/select-screens/02-DESIGN.md` (layouts §3–§5, states, sizes). Follow its layouts.
- Current in-game HUD style (match its materials, frames, palette): `docs/game-design/hud-redesign/blind-s20/A.jpg`
- Current (bad) room screen we replace: `docs/game-design/hud-redesign/frames/live-s3-room.jpg`
- Marble+bronze material plates: `art/imagegen/hud-table-materials-codex/M3/hero-card-plate.png`
- Hero likeness (the in-game 3D figures were built from these): `art/imagegen/hero-quality-v1/king-arthur/king-arthur-front.png`,
  `art/imagegen/hero-quality-v1/medusa/medusa-front.png` (sidekicks: `.../merlin/merlin-front.png`, `.../harpy/harpy-front.png`)
- Real boards (K1 frames of the real maps): `docs/game-design/evidence/VISUAL/AN-23/sheet-01-marmoreal-K1-plain.png`,
  `docs/game-design/evidence/VISUAL/AN-23/sheet-03-sarpedon-K1-plain.png`

Write everything ONLY into `art/imagegen/select-screens-codex/` (subfolders `raw/`, `refs/`, `_tools/`). Do not touch
any other file. Do not commit. Write JSON/Markdown from Python with `Path.write_text(..., encoding="utf-8")`.

## What to make — 4 screens × 2 variants = 8 references, 16:9

Variant A "studio": the fighters stand in two tall dark display niches with a cone of light from above in their team
colour, marble floor reflection, very dark vignette — closest to MK11 drama.
Variant B "table": the same layout over a blurred, darkened view of the real board scene (Marmoreal K1 frame as the
background), the niches are lighter marble-and-bronze plaques — closest to our current HUD.

Screens (layouts from 02-DESIGN.md):
1. `R1-hero-hover` — step 1 "ВЫБОР ГЕРОЯ · шаг 1 из 2": left niche P1 shows King Arthur full body on his round dark
   pedestal (three-quarter view turned to screen centre), hover state; right niche P2 empty pedestal with a big "?";
   centre: hero info card; bottom centre: roster strip of 3 tiles (King Arthur hovered with a gold frame, Medusa,
   Random "?"); bottom bar with buttons.
2. `R2-hero-locked` — both locked: P1 King Arthur (gold), P2 Medusa (silver-blue) turned towards each other, a bronze
   "VS" medallion on the screen axis at chest height, tiles with P1/P2 corner badges, status chips "ВЫБРАН"/"ГОТОВ".
3. `R3-board-select` — step 2 "ВЫБОР ПОЛЯ · шаг 2 из 2": niches shrunk to the screen edges, big board preview in the
   centre (use the real Marmoreal K1 frame image as the preview content — composite it, do not redraw the board),
   board name plate, strip of 3 thumbnails (Marmoreal selected, Sarpedon, Random "?").
4. `R4-vs` — VS splash (match loading): two full-height fighters with a diagonal split to the centre, large bronze "VS"
   medallion, names and nicknames, board name at the bottom, a small loading line with a spinner.

## Method (important — real data rule)

ImageGen must NOT invent game text or numbers. Do it in two passes:
1. `image_gen`: generate the ART LAYER of each reference — composition, niches/plaques, lighting, fighters (use the
   hero front images above as likeness references; keep costumes, colours and silhouettes), medallion, empty panels
   and empty tiles. Ask for NO text, NO letters, NO numbers, NO logos in the image. Keep raw outputs in `raw/`.
2. Python/Pillow (`_tools/compose.py`): normalize to 1920×1080 and overlay the REAL text and data with real fonts
   (use `art/imagegen/anim-move-sheet-codex/_tools/fonts/Roboto-BoldCondensed.ttf` / `Roboto-Regular.ttf`; a serif from
   Windows fonts for titles if available, e.g. `C:/Windows/Fonts/georgia.ttf`), and composite the real board K1 frames
   into R3/R4 where a board is shown. Real data to print (Russian UI):
   - King Arthur: «Король Артур», «HP 18 · ход 2 · ближний бой», «+ Мерлин · HP 7 · дальний бой»,
     ability «Когда Король Артур атакует, вы можете УСИЛИТЬ эту атаку: сыграйте карту УСИЛЕНИЯ…», «Колода · 30»
   - Medusa: «Медуза», «HP 16 · ход 3 · дальний бой», «+ Гарпии ×3 · HP 1 · ближний бой»,
     ability «В начале своего хода вы можете нанести 1 урон бойцу противника в зоне Медузы.»
   - Players: «Veteran» (P1, host), «ProGamer» (P2); room code «SNYMNZ»
   - Boards: «Marmoreal · оригинальная карта», «Sarpedon · оригинальная карта»
   - Titles: «ВЫБОР ГЕРОЯ», «шаг 1 из 2», «ВЫБОР ПОЛЯ», «шаг 2 из 2», «VS», «Случайный», «Случайное»,
     buttons «Выйти», «Готов», «Начать партию», «‹ Герой», status «Выбирает…», «Выбран», «Готов»,
     «Соперник выбирает…», «Поле выбирает хост», loading «Подготовка поля…».

Output: `refs/R1-hero-hover-A.png`, `refs/R1-hero-hover-B.png`, … `refs/R4-vs-B.png` (1920×1080) and
`refs/contact-sheet.png` (all 8 at 480×270 in a 2×4 grid, A column left, B right).

Finally write `README.md` (Russian): per reference — prompt used, raw size, what was composited, which spec section it
illustrates; any `moderation_blocked` or failures; a self-check: every visible word/number is from the real data list
above (list them per image), no garbled ImageGen glyphs remain (inspect each PNG; if ImageGen drew pseudo-text, paint
it over or regenerate), fighters are recognisable as King Arthur and Medusa from the reference fronts.
