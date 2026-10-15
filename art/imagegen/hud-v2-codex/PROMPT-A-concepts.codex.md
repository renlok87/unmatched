# HUD v2 — stage A: three style directions painted over the real game

User request (2026-10-15, Russian): «мне нужно, чтобы ты с помощью кодекс ImageGen спроектировал и сгенерировал
красивый HUD. То есть красивый комплексный HUD.» Earlier: «Худ какой-то прототипный вместо нормального».
The current in-game HUD (flat dark-navy rectangles, plain text, legacy grey buttons) reads as a prototype. We need a
beautiful, cohesive, production-quality HUD for this digital board game (Unmatched-like, 1v1 skirmish on a painted map
board, 3D figures, cards). This stage designs it with image_gen; a later stage cuts an asset kit for Unreal.

## Inputs (read them, look at every image)

Real 1920x1080 frames of the live game, `scraped-data/derived/hud-v2-codex/refs/`:
- `01-maneuver-own-turn.png` — own turn, maneuver draft (status «Выберите бойца, который пойдёт»).
- `02-action-choice.png` — own turn, choose an action (M/A/G hotkeys); older build: English names there.
- `03-combat-attack.png` — combat: attack card on the left edge, the opponent's card on the right edge.
- `04-combat-defense.png` — the defense window (defend / no defense, timer).
- `05-choice-banner.png` — a card effect choice panel at the top («Сделайте выбор…»), boost pick.
- `06-result.png` — the victory screen.
- `07-room.png`, `08-lobby.png` — room (hero pick) and lobby screens.

Language of the existing assets (keep it, it is accepted art): `art/imagegen/hud-icons-v3/` (STYLE-v3.md, masters/,
sheets/) — coloured action discs (maneuver violet, attack red, scheme gold-orange, end turn grey), Roboto Bold
Condensed. Card faces: navy #061623, cream #F9EBDB, the card-type colours. The board Marmoreal: white marble, pink
cherry blossoms, warm lanterns, night garden.

## What the HUD must contain (every element in every own-turn mockup, all text in Russian, exactly as written)

1. Top-left turn plate: menu ☰, connection bars, «Ход 1».
2. Top-centre status banner — the one line «what to do now», e.g. «Выберите действие: манёвр, атака или схема» with
   key chips M A G.
3. Own player panel bottom-left: hero portrait medallion «Медуза», «ВАШ ХОД», HP «16/16» with a heart, the three
   sidekicks «Гарпия 1/2/3» with «1/1» each, two action pips (actions left this turn).
4. Opponent panel top-right: portrait «Король Артур», «ЖДЁТ», HP «18/18», sidekick «Мерлин 7/7», the opponent hand as
   5 card backs, «Рука 5 · колода 25 · сброс 0».
5. Own hand bottom-centre: 5–7 cards (the real Russian card scans from the frames — keep them recognisable), the
   resting hand peeks above the bottom edge, one card raised on hover, caption «Рука 6/7».
6. Deck and discard piles bottom-right: «Колода 24», «Сброс 0».
7. Action bar bottom-right: «МАНЁВР» (M), «АТАКА» (A), «СХЕМА» (G), «КОНЕЦ ХОДА» (E) — the v3 coloured discs.
8. Journal / log left: title «Журнал», entries like «Х1 Медуза: манёвр: без движения».
9. Fighter plates over the figures on the board: small HP plates «16/16», «1/1», the harpy digits ①②③, team colour.
10. Combat (state 03/04): attack card left with «АТАКА · Медуза», defense card right «ЗАЩИТА · Король Артур», the values,
    buttons «ЗАЩИТИТЬСЯ» / «БЕЗ ЗАЩИТЫ», timer «27 с»; a centre result «3 : 1 · Медуза побеждает».
11. Choice panel (state 05): title = card name «Второй выстрел», text «ВО ВРЕМЯ БОЯ: Можете УСИЛИТЬ эту атаку.»,
    buttons «ПОДТВЕРДИТЬ», «СВЕРНУТЬ (C)».

Hard rules:
- The board field (the circles / spaces and the figures on them) stays visible and uncovered: HUD lives on the edges,
  over the painted backdrop, as in the frames. Same 1920x1080 composition and roughly the same regions.
- Keep the game scene itself (board, figures, backdrop) as in the frame; only the HUD layer is redesigned.
- Legible at 1080p: body text ≥ 16 px, numbers big; contrast ≥ 4.5:1 on panels.
- Every text in Russian exactly as listed above (no invented words, no English, no gibberish glyphs). If image_gen
  garbles text, keep generating or render the text yourself with Pillow over the generated art (Roboto Bold Condensed
  from the UE engine fonts: `C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/` or
  `art/imagegen/anim-move-sheet-codex/_tools/fonts/`).
- No logos or trade dress of the real Unmatched / Restoration Games / Mondo; original ornament only.

## Three directions (one complete look each, clearly different)

- **A «Мраморный акрополь»** — ivory/white marble panels with thin gold-leaf filigree and Greek meander borders, deep
  navy enamel insets, warm lantern glow; matches the Marmoreal board.
- **B «Бронза и пергамент»** — premium tabletop: dark walnut and aged bronze frames, parchment inner plates, wax-seal
  medallions for portraits, embossed leather action buttons.
- **C «Цифровое издание»** — modern, clean: dark navy glass panels with subtle gradients and crisp cream edges, the bold
  coloured action discs as the hero element, minimal ornament, strong typography (closest to a digital board-game app).

## Deliverables (per direction X = A, B, C)

Concepts contain the real frames (card scans, board art) → they go OUTSIDE git:
`scraped-data/derived/hud-v2-codex/concepts/`
- `X-1-own-turn.png` — own turn, action choice (base: 01/02), all 11 elements except combat/choice.
- `X-2-combat.png` — combat attack vs defense (base: 03/04).
- `X-3-choice.png` — the choice panel (base: 05).
- `X-4-styleguide.png` — a style sheet WITHOUT any game frame: palette swatches with hex, the panel frame (empty, at
  2 sizes), the 4 action buttons in states normal / hover / pressed / disabled, the portrait medallion, the HP plate,
  the card-hand slot / hover glow, the status banner, a primary and a secondary text button, the typography sample
  («Ход 1», «16/16», «ВАШ ХОД»). This one may be committed (no scans): also copy it to
  `art/imagegen/hud-v2-codex/styleguides/X-styleguide.png`.

Use image_gen in edit mode with the reference frame as the input image for X-1..X-3 (prompt: keep the scene, repaint
only the HUD layer); 16:9 landscape output; record the real output size. If the output is not 16:9 or the scene gets
repainted, composite: paste the generated HUD regions over the original frame with soft masks (Pillow), so the board
stays the original pixels. Normalise every concept to 1920x1080.

Then `scraped-data/derived/hud-v2-codex/concepts/contact.png`: a 3x4 grid (rows A, B, C; columns 1–4) at 640x360 per
cell with labels.

## Package contract

- Write ONLY inside `art/imagegen/hud-v2-codex/` and `scraped-data/derived/hud-v2-codex/concepts/`. Nothing else on
  disk changes. No git commands at all. Claude reviews and commits.
- `art/imagegen/hud-v2-codex/README.md` (Russian): what was made, per direction 3–5 lines of design intent, honest
  self-review (what looks weak, which texts had to be overlaid with Pillow), a recommendation which direction to take.
- `art/imagegen/hud-v2-codex/prompts.md` — every image_gen prompt used, in order; `generation-records.json` — one entry
  per image_gen call (file, prompt id, input image, output size, kept/rejected and why).
- Text files UTF-8 without BOM, written from Python (`Path.write_text(..., encoding="utf-8")`), never by PowerShell
  redirection.
- Budget: up to 30 image_gen calls. Review every image yourself at full size before keeping it; regenerate garbled text.
- Final message: the list of files and the recommendation.
