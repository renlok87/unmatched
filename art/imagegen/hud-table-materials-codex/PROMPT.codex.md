# Codex task — HUD "Стол" material samples (ImageGen, material only)

Context: Unmatched (Restoration Games / Mondo) digital adaptation in UE5. HUD is being rebuilt as physical
components of the board-game box lying on the table edge: a hero card (player board), a round health dial, card
piles, action tokens. Reviews said the current mockups choose the material from flat CSS fills — we need REAL
material samples. You make ONLY material/texture plates. No text, no numbers, no letters, no icons, no game data,
no characters, no layout (rule: ImageGen is for material and style only; real data is composited later by code).

Canon of the physical Unmatched box (use as style reference, do not copy any asset): flat screen-print / riso look,
limited palette, cream card edge (~#ECE3CF / #F9EBDB), dark near-black navy body (~#14161C / #061623), tonal hero
pattern printed inside the body at 6–8 % (Medusa: greek meander), matte card stock, tiny print grain, crisp die-cut
rounded corners, NO bevel, NO metallic shine, NO glow, NO laurels.

Write everything ONLY into `art/imagegen/hud-table-materials-codex/` (create subfolders). Do not touch other files.
Do not commit. Write any JSON/Markdown with Python `Path.write_text(..., encoding="utf-8")`.

## Generate (image_gen), then normalize with Python/Pillow to the exact sizes below (keep raw outputs in `raw/`)

Three material families, same set of 4 plates each:
- **R3 "printed component canon"** — dark matte card stock body with cream die-cut edge (2–3 % of width),
  tonal meander pattern 6 % inside the body, riso grain. Must read as a printed game component lying on a table.
- **M2 "dark stock + gold thread"** — same dark matte stock, edge is a single thin flat ochre-gold printed line
  (~#C9A45C, flat ink, not metal), slightly heavier paper grain, very subtle tonal pattern.
- **M3 "marble + bronze (only for hero cards)"** — real dark green-grey polished marble slab with veins, thin
  patinated bronze rim (#8C6B3F base, restrained highlight, patina in recesses). Tasteful museum plaque, NOT
  souvenir kitsch, highlights subtle.

Plates per family (PNG, transparent outside the shape, no text):
1. `hero-card-plate.png` — 840×368, rounded rect corner radius 20 px, empty (space for art on the left 300 px may
   stay the same material). Lit from top-left, soft contact shadow baked OUTSIDE is NOT wanted (we add shadow).
2. `hp-dial.png` — 256×256 round health dial: two stacked cardboard discs with a rivet hint, an empty round window
   in the centre (diameter ~46 % of the disc) filled with plain cream paper where a number will be printed later;
   outer ring in the family material.
3. `pile-slip.png` — 240×64 small paper tag / slip (cream paper, die-cut, slight curl) to print a count on.
4. `question-strip.png` — 1200×88 long thin strip of the family material (for a one-line prompt), tileable
   horizontally in the middle 80 %.

Also make `swatch-sheet.png` (1600×1200): the 3 families side by side, each showing its 4 plates on a dark
background, family name in a corner is NOT allowed (no text) — order left→right R3, M2, M3.

Finally write `README.md` (Russian): what was generated, prompts used, raw vs normalized sizes, any
`moderation_blocked` or failures, and a self-check: no text/numbers/logos in any plate (inspect each PNG).
