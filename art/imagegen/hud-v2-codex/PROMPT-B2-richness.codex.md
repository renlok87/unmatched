# HUD v2 — stage B2: bring the kit up to the richness of concept A

## HARD CONTRACT — the body colour under the game's text (found in the live game, overrides stage B choices)

The game draws its own text on the skins with fixed colours: LIGHT text (#F2EDE4 / #B9B2A6) on every skin below except
BtnPrimary_* (dark #061623 text). Stage B made several bodies light ivory marble — in the live game the status line
«Выберите бойца…», the deck / discard chips «Колода 24» / «Сброс 0» and the disabled action buttons became unreadable
(white text on ivory). So the BODY (the stretched centre where text sits) of each skin must keep the v1 body colour and
opacity from `art/imagegen/hud-skins-v1-codex/manifest.json`:
Panel, Modal, Btn_Normal, Btn_Disabled, Btn_Focus, Toast, ToastWarning, Capsule, Tag, Chip, Check_Off, Input_* = navy
#061623 (α 0.92; Modal 1.0); PanelInset, KeyChip, ProgressTrack, SliderTrack = #15232E α 0.92; Btn_Hover #1E2B35;
Btn_Pressed #040E17; Btn_Selected, ProgressFill, Check_On = teal #0D7A89; BtnPrimary_* = gold #F2C14E / #F3C55B /
#D5AA45 / #4E5457 (disabled); SliderThumb #FAF8F2. Marble and gold live ONLY in the rim and the corners, never under
the text. The same for the new pieces: StatusBanner, TurnPlate, HpPlate, PileFrame, ActionPlate, HandTray,
FighterPlate bodies are navy (light text on them). Measure and record in verification.json: body colour of every skin
at its centre ±10 % and contrast with its game text colour ≥ 4.5:1.

Read this package's README (stages A and B), `kit/manifest.json`, `slice-margins.json`, `_tools/`, and compare
`scraped-data/derived/hud-v2-codex/kit-preview/compare-own-turn.png` and `compare-combat.png` at full size.

Claude's review of stage B (the reason for this pass): the kit assembly (right) is much poorer than concept A (left).
The concept reads as **ivory marble frames with gold filigree**; the kit reads as thin flat lines on navy:
1. Panel / Modal / Toast / TurnPlate / StatusBanner / PileFrame: the rim is a 1–2 px line. Concept A has a visible
   marble rim (≈6–8 su wide at ×1, veined ivory) with a thin gold inner line and larger gold filigree corners
   (≈20–28 su). Bring that rim and those corners into the 9-slice (bigger margins are fine; record them).
2. StatusBanner: concept A has cartouche ends with meander and a raised gold edge; the kit has plain brackets.
3. Portrait medallion: concept A has a thick marble ring with a gold bevel and laurel sprays at the bottom; the kit's
   ring is thin and the laurels are tiny. Same for the opponent 64 su version.
4. Action buttons: concept A shows the v3 discs inside a gold-and-marble bezel with a navy enamel back plate and the
   label plate under it; the kit ring is a thin line. Make ActionRing_* a real bezel (≈8 su) and add
   `T_Hud_ActionPlate` (the small navy plate with gold edge behind label + disc, 9-slice).
5. KeyChip / KeyBadge: plain squares. Make them small gold coins / enamel tiles with a bevel, readable dark letter.
6. Buttons (Btn_*, BtnPrimary_*): flat rectangles. Give them a marble bevel (light top edge, darker bottom), gold edge
   on hover, gold-leaf texture on Primary; keep the centre flat enough for text (contrast rules unchanged).
7. Fighter plates: fine as they are (small, must stay light) — only check legibility.
8. Keep everything that already passed (transparency, ×1/×2/4 px/su, seams, contrast ≥ 4.5:1 for text on bodies).

Use image_gen for new ornament masters (marble rim strips, corners, laurels, bezels) — up to 25 calls — and the
existing `_tools` pipeline to cut and assemble. Re-run the kit-preview own-turn / combat assemblies and the compare
sheets; add `kit-preview/compare-b-vs-b2-own-turn.png` (stage B vs B2). The ×1 versions must still look clean at
1080p: prefer fewer, bolder ornaments over fine noise.

Package contract as in stage B: write only in `art/imagegen/hud-v2-codex/` and `scraped-data/derived/hud-v2-codex/`,
same file names (overwrite kit/x1, kit/x2, kit/masters; keep a copy of the stage B kit as `kit-b1/`), manifest and
slice-margins updated, README section «Этап B2» on top, generation-records appended, UTF-8 from Python, no git.
Final message: what changed, weak points.
