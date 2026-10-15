# HUD v2 — stage B: the asset kit of direction A «Мраморный акрополь»

Stage A of this package (read `art/imagegen/hud-v2-codex/README.md`, `prompts.md`, `generation-records.json` and look at
`scraped-data/derived/hud-v2-codex/concepts/A-*.png`, `art/imagegen/hud-v2-codex/styleguides/A-styleguide.png`) painted
three looks over the real game. Claude picked **A «Мраморный акрополь»** (ivory marble, thin gold-leaf filigree and
Greek meander, deep navy enamel insets, warm glow) — the visual decisions are delegated to Claude (user 2026-10-06:
«Делай сам… Все решения принимай»). Stage B turns A into game-ready, cut, transparent PNG assets that Unreal swaps in
for the current flat skins, plus the new ornamental pieces the concept needs.

## Contract with the game (must match exactly)

The UE HUD draws 9-slice skins by name; the current flat set is `art/imagegen/hud-skins-v1-codex/` — read its README,
`slice-margins.json` and `manifest.json` (sizes, margins, states, the colour tokens and contrast rules there still
apply to the TEXT the game draws on top: dark text on light bodies must reach 4.5:1, light text on navy too).
Text and icons are NOT in the PNGs — the game draws them (Roboto Bold Condensed; icons from `hud-icons-v3`).

### B1. Re-skin all 29 skins of v1 with the A look, same file names

`T_Skin_Panel, T_Skin_PanelInset, T_Skin_Modal, T_Skin_Btn_{Normal,Hover,Pressed,Disabled,Focus,Selected},
T_Skin_BtnPrimary_{Normal,Hover,Pressed,Disabled,Focus}, T_Skin_Toast, T_Skin_ToastWarning, T_Skin_Capsule, T_Skin_Tag,
T_Skin_Chip, T_Skin_KeyChip, T_Skin_ProgressTrack, T_Skin_ProgressFill, T_Skin_SliderTrack, T_Skin_SliderThumb,
T_Skin_Check_Off, T_Skin_Check_On, T_Skin_Input_{Normal,Focus,Error}`.
- Panels / modal / toast: navy enamel body (text on them is light, #F2EDE4) framed by a marble rim with a fine gold
  filigree line and ornamental corners; Modal gets the richest corners. Inset = darker navy, simpler rim.
- Buttons: marble-and-gold bevel; Primary = gold leaf body (dark text); states clearly different (hover brighter gold
  rim, pressed inset, disabled desaturated, selected teal enamel #0D7A89, focus = separate outer ring only).
- 9-slice rule: corners carry all ornament; the edge strips between corners must tile/stretch cleanly (uniform along
  the stretch axis), the centre is a flat or very low-detail fill. Record the new margins per file in
  `slice-margins.json` (you may enlarge the canvases and margins for the ornament; keep the content area
  proportions). Export ×1 and ×2 (`vector/x1/`, `vector/x2/` naming kept: put them in `kit/x1/`, `kit/x2/`) and a
  4 px/su master in `kit/masters/`.

### B2. New ornamental pieces (transparent PNG, ×1 and ×2, centre / insert areas transparent or flat)

- `T_Hud_PortraitFrame` — round marble-and-gold medallion ring for the hero portrait (inner circle transparent,
  diameters 80 su own panel / 64 su opponent); plus `T_Hud_PortraitFrame_Active` (warm glow for «your turn»).
- `T_Hud_SidekickRing` — small ring for sidekick mini portraits (32 su).
- `T_Hud_HpPlate` — the HP plate behind «16/16» with a heart slot (9-slice horizontally).
- `T_Hud_StatusBanner` — the top-centre status banner: a 9-slice ribbon/cartouche with meander ends.
- `T_Hud_TurnPlate` — the top-left «Ход N» plate (9-slice).
- `T_Hud_ActionRing_{Normal,Hover,Pressed,Disabled,Active}` — the ring/bezel around the v3 coloured action discs
  (64 su; the disc itself stays the v3 icon, so the ring's inner circle is transparent) and `T_Hud_KeyBadge` for the
  hotkey letter.
- `T_Hud_HandTray` — the low tray/glow under the resting hand (9-slice horizontal), `T_Hud_CardGlow_Hover` and
  `T_Hud_CardGlow_Selected` — glows around a 150×208 su card (transparent inside).
- `T_Hud_CardBackSlot` — the frame of one opponent card back (24×34 su).
- `T_Hud_PileFrame` — frame of the deck / discard chip.
- `T_Hud_CombatRibbon_Attack`, `T_Hud_CombatRibbon_Defense` — the ribbons «АТАКА · …» / «ЗАЩИТА · …» above the combat
  cards (red / blue enamel, 9-slice), `T_Hud_CombatFrame` — the frame around a 230 su combat card, `T_Hud_VersusBadge`
  for the centre «3 : 1».
- `T_Hud_FighterPlate` — the small plate over a figure on the board (HP bar slot, digit slot; 9-slice), and
  `T_Hud_FighterPlate_Enemy`.
- `T_Hud_Divider` — a horizontal meander divider (tileable).

## Method

1. image_gen paints ornament masters (corners, rims, rings, ribbons) at high resolution on a flat, uniform, clearly
   separable background (pure #00FF00 or pure black, your choice per piece) — never ask image_gen for transparency.
2. Pillow cuts them: key the background to alpha with clean anti-aliased edges (no green fringe: decontaminate),
   assemble 9-slice skins from corners + straightened edge strips + flat centre, so the stretch axis is uniform.
   Deterministic Python in `art/imagegen/hud-v2-codex/_tools/` (rerunnable from the masters).
3. Verify every PNG at 100 % and on both a navy and a light background; check that edges tile (stretch a panel to
   3 widths, 3 heights and look for seams).
4. Assembly proof: `scraped-data/derived/hud-v2-codex/kit-preview/` — rebuild the own-turn and the combat states of
   `refs/01` / `refs/03` at 1920x1080 using ONLY the kit PNGs + real text rendered with Pillow (Roboto Bold Condensed,
   Russian strings of stage A) + the v3 icons + the real card scans cropped from the frames. This is how the game will
   look; compare it side by side with `concepts/A-1-own-turn.png` / `A-2-combat.png` in `kit-preview/compare-*.png`.
5. Contact sheets: `art/imagegen/hud-v2-codex/kit/catalog.png` (every asset on navy and on light marble, labelled) —
   no scans, may be committed.

## Package contract

- Write ONLY inside `art/imagegen/hud-v2-codex/` and `scraped-data/derived/hud-v2-codex/`. No git commands at all.
  Do not touch `unreal/` or any other folder.
- Keep stage A records: README.md / prompts.md get a new «Этап B» section on top, earlier sections unchanged;
  generation-records.json appended; `kit/manifest.json` lists every kit file (size, scale, slice margins, sha256,
  role, which UE skin key / new widget it is for).
- UTF-8 without BOM, written from Python. Budget: up to 35 image_gen calls. Review every asset yourself at 100 %.
- README «Этап B» (Russian): what is in the kit, the slice margins, honest weak points, what the game code must change
  to use the new pieces (per piece: which widget / skin key).
- Final message: file list, weak points.
