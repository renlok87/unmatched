# Imagegen HUD Asset Plan

Date: 2026-06-11

Project: React/Vite + Phaser tactical card-board game.

## Goal

Сделать нормальный HUD-план для web-game сцены, где существующие карты, борды, hero portraits, minis и card covers берутся из текущих ассетов/API, а imagegen генерирует только нейтральную UI-обвязку: панели, слоты, рамки, подсветки, бейджи, фоны модалок, эффекты выбора и мобильные варианты.

Главное исправление к прошлому направлению: не генерировать заново карты, борды и фигурки, если они уже есть в проекте. Их нужно использовать как primary content layer.

## Existing Assets To Use

### Hero assets

Локально уже есть production-like hero assets:

- `public/assets/heroes/ms-marvel/avatar.webp`
- `public/assets/heroes/ms-marvel/mini.webp`
- `public/assets/heroes/ms-marvel/card-cover.webp`
- `public/assets/heroes/daredevil/avatar.webp`
- `public/assets/heroes/daredevil/mini.webp`
- `public/assets/heroes/daredevil/card-cover.webp`

Figma-ready originals:

- `docs/figma/figma-ready/heroes/avatars/`
- `docs/figma/figma-ready/heroes/minis/`
- `docs/figma/figma-ready/heroes/card-covers/`

API source examples:

- `scraped-data/api/normalized/ms-marvel.json`
- `scraped-data/api/normalized/daredevil.json`

These JSON files already expose:

- `urls.avatar`
- `urls.mini`
- `urls.cardCover`
- `cards[].url`
- `cards[].filename`

### Card assets

Existing full card images live in:

- `docs/figma/figma-ready/decks/`

For the current heroes, normalized JSON includes direct deck-card image URLs:

- Ms. Marvel: 22 card image entries in `scraped-data/api/normalized/ms-marvel.json`
- Daredevil: 16 card image entries in `scraped-data/api/normalized/daredevil.json`

Important visual constraint: these card images already include card frame, art, title, values and text. HUD should not render duplicate title/value UI on top of full card thumbnails unless the gameplay intentionally uses a simplified card row.

### Board/map assets

Map data is present in:

- `scraped-data/api/maps.json`

The map records include:

- `name`
- `key`
- `width`
- `height`
- `zones`
- `image`
- zone-level `image`
- zone color keys

The current GraphQL game queries only expose board geometry fields, not full image URLs. Board/map art should be fetched from API/local cache before imagegen UI work is final.

## API And Data Prerequisites

Before final HUD implementation, expose asset URLs to the game scene:

1. Extend hero/card content shape.
   - Add `imageUrl` and optional `imageUrlRu` to card definitions.
   - Keep `title`, `type`, `value`, `boost`, `quantity` for logic.
   - Use `cards[].url` and `cards[].filename` from normalized JSON or source API.

2. Extend GraphQL/card queries.
   - `HeroDetails.cards` should include card image URL fields.
   - Generated gql types must be regenerated after schema/query update.

3. Extend board content shape.
   - Add `imageUrl` to board/map model.
   - If zone art is useful, add `zones[].imageUrl`.
   - Current `Board` query should return board art URL in addition to `spaces`.

4. Decide cache strategy.
   - Option A: Phaser loads Supabase URLs directly.
   - Option B: build/download cache into `public/assets/decks/`, `public/assets/boards/`, `public/assets/maps/`.
   - For stable dev/testing, prefer local cache with source URL stored in metadata.

5. Define runtime fallback.
   - If a full card image is missing, show generated neutral card slot plus game-rendered title/value.
   - If board image is missing, show current procedural/placeholder board but keep HUD composition identical.

## Reference Research Takeaways

Sources reviewed:

- Hearthstone mobile/store page: https://play.google.com/store/apps/details?id=com.blizzard.wtcg.hearthstone
- MTG Arena Steam page: https://store.steampowered.com/app/2141910/Magic_The_Gathering_Arena/
- MTG Arena mobile UI notes: https://magic.wizards.com/en/news/mtg-arena/mtg-arena-state-game-january-2021-01-21
- MARVEL SNAP Steam page: https://store.steampowered.com/app/1997040/
- MARVEL SNAP Apple design article: https://developer.apple.com/news/?id=sosm2p7q
- Legends of Runeterra Google Play page: https://play.google.com/store/apps/details?id=com.riotgames.legendsofruneterra
- Riot article on mobile UI safety/accessibility: https://www.riotgames.com/en/news/bringing-features-life-legends-runeterra
- GWENT Steam page: https://store.steampowered.com/app/1284410/GWENT_The_Witcher_Card_Game/

Reusable HUD patterns:

1. Center is sacred.
   - Gameplay board stays visually dominant.
   - HUD chrome hugs edges and corners.
   - Effects can cross center briefly but should not permanently cover board coordinates or fighters.

2. Player hierarchy is top/bottom.
   - Opponent info at top.
   - Local player info and hand at bottom.
   - This reads naturally on desktop and mobile.

3. Hand needs collapsed and expanded states.
   - Expanded hand for card selection.
   - Collapsed/tucked hand when moving fighters or inspecting board.
   - Mobile should prioritize board readability over always showing huge cards.

4. Card piles are compact and readable.
   - Deck/discard/exhaust piles should be small vertical slots, not full panels.
   - Counts can be Phaser text overlays, not baked into art.

5. Use real content as texture.
   - Existing card art, hero cover art and board art already provide color/noise.
   - Generated HUD should be lower-contrast, dark, glass/metal/parchment-neutral, with clear silhouettes.

6. Feedback is stronger than decoration.
   - Selection rings, playable highlights, attack target glow, defend prompt, turn pulse and damage sparks matter more than ornate borders.

7. Mobile safe area matters.
   - Avoid putting critical controls in notches/corners.
   - Use larger hit targets and fewer simultaneous panels.

## HUD Composition Target

### Desktop 800x600 Phaser scene

Layer order:

1. Background dark vignette or board table surface.
2. Existing board/map image from API.
3. Phaser grid, zones, spaces, movement/attack overlays.
4. Existing hero minis/figures from API/assets.
5. Selection rings, target indicators and combat particles.
6. HUD chrome generated by imagegen.
7. Existing card images in hand/deck detail.
8. Phaser-rendered dynamic text: health, card counts, turn, actions, selected card metadata.

Suggested layout:

- Top left: opponent hero panel, avatar/mini, HP badge, deck count, discard count.
- Top center: turn/phase pill, compact and non-decorative.
- Top right: opponent hand backs or count.
- Center: board image + grid, no permanent HUD overlay.
- Bottom left: local hero panel with avatar/mini and HP.
- Bottom center: card hand tray showing real card images.
- Bottom right: deck/discard slots and action buttons.
- Right edge: selected card inspector, hidden by default, opens on hover/tap/select.

### Mobile portrait/compact

Suggested layout:

- Top: opponent compact strip, HP, deck/discard counts, hand count.
- Middle: board fills most of viewport.
- Bottom: local hero strip and hand carousel.
- Hand has two states:
  - collapsed: 5 to 7 card backs/thumbnails peek from bottom edge;
  - expanded: card carousel overlays lower 35 to 42 percent of screen, board still visible above.
- Selected card inspector opens as a bottom sheet, not a side panel.

## Imagegen Asset Targets

Generate these assets only. Do not generate cards, boards, official-looking card frames, logos or character art.

### HUD panels

1. `public/assets/ui/hud/player-panel-local.png`
   - 380x112 transparent PNG.
   - Left portrait socket, center stat lane, right resource slots.
   - No text, no numbers, no logos.

2. `public/assets/ui/hud/player-panel-opponent.png`
   - 380x96 transparent PNG.
   - More compact than local panel.
   - Same visual language, mirrored-compatible.

3. `public/assets/ui/hud/turn-phase-pill.png`
   - 220x54 transparent PNG.
   - Empty center for Phaser text.

4. `public/assets/ui/hud/selected-card-panel.png`
   - 260x360 transparent PNG.
   - For enlarged card preview and rules text when needed.
   - Should not look like a card frame.

5. `public/assets/ui/hud/mobile-bottom-sheet.png`
   - 390x320 transparent PNG.
   - Bottom-sheet style for mobile selected card/hand expansion.

### Card area chrome

6. `public/assets/ui/hud/hand-tray.png`
   - 760x130 transparent PNG.
   - Soft top edge, card sockets only implied.
   - Existing full card images sit on top.

7. `public/assets/ui/hud/hand-tray-mobile.png`
   - 390x122 transparent PNG.
   - Compact tray with safe center and fading side edges.

8. `public/assets/ui/hud/deck-slot.png`
   - 96x132 transparent PNG.
   - Frame for deck stack/card back.

9. `public/assets/ui/hud/discard-slot.png`
   - 96x132 transparent PNG.
   - Frame for visible top discard card.

10. `public/assets/ui/hud/hidden-card-back.png`
    - 120x180 PNG.
    - Neutral back for hidden opponent hand only.
    - Must not resemble Unmatched, Hearthstone, MTG, SNAP, LoR or GWENT backs.

### Board chrome

11. `public/assets/ui/hud/board-vignette.png`
    - 1024x768 transparent PNG.
    - Subtle edge shading only.
    - Center must remain transparent/low opacity.

12. `public/assets/ui/hud/board-frame-6x4.png`
    - 640x430 transparent PNG.
    - Thin border/table rim around board area.
    - No baked spaces, no grid, no coordinates.

13. `public/assets/ui/hud/zone-legend-chip.png`
    - 132x34 transparent PNG.
    - Empty label chip for Phaser-rendered zone color/text if needed.

### Status badges

14. `public/assets/ui/hud/status-badges.png`
    - 6 frames, each 64x64, horizontal strip.
    - Frame order: health, movement, attack, defense, boost, card-count.
    - Icons can be abstract but not copied from existing games.
    - No text/numbers.

15. `public/assets/ui/hud/action-buttons.png`
    - 5 frames, each 72x72, horizontal strip.
    - Frame order: move, attack, defend, boost, end-turn.
    - Empty icon-like pictograms only.

### Selection and combat effects

16. `public/assets/ui/effects/selection-ring.png`
    - 128x128 transparent PNG.
    - Clean ring readable on bright/dark boards.

17. `public/assets/ui/effects/move-highlight.png`
    - 128x128 transparent PNG.
    - Soft blue/teal tile glow.

18. `public/assets/ui/effects/attack-highlight.png`
    - 128x128 transparent PNG.
    - Amber/red target glow.

19. `public/assets/ui/effects/defense-shield.png`
    - 96x96 transparent PNG.
    - Short-lived combat overlay.

20. `public/assets/ui/effects/hit-spark-strip.png`
    - 8 frames, each 64x64, horizontal strip.
    - Stylized comic impact, transparent background.

21. `public/assets/ui/effects/card-play-flash-strip.png`
    - 8 frames, each 96x96, horizontal strip.
    - Used when a card is selected/played.

## Global Imagegen Direction

Use this before every prompt:

```text
Create original UI assets for a tactical digital card-board game rendered in Phaser. The game already has full card images, board images, hero portraits and miniatures; generate only neutral HUD chrome, slots, badges, panels, highlights and effects that frame existing content. Style: premium digital board-game HUD, clean comic-fantasy tactics, dark neutral base, restrained brass and cool blue accents, readable at 800x600 and mobile, sharp silhouettes, transparent PNG where requested. No text, no numbers, no logos, no trademarks, no copyrighted character art, no official card backs, no official game UI frames.
```

Negative prompt for every request:

```text
no Unmatched UI copy, no Marvel or DC branding, no Hearthstone frame, no Magic Arena frame, no Marvel Snap frame, no Legends of Runeterra frame, no GWENT frame, no Restoration Games style copy, no logos, no readable text, no numbers, no card illustration, no board illustration, no character art, no watermark, no photorealistic humans, no busy ornament, no baked grid, no baked labels, no cropped transparent edges
```

## Specific Imagegen Prompts

### Local player panel

```text
Transparent PNG, 380x112. Original tactical card-board game local player HUD panel. Left circular portrait socket for an existing hero avatar, small lower socket for a miniature icon, central empty stat lane, right side has three compact empty resource/count sockets. Dark graphite glass and worn brass rim, subtle blue edge light, clean comic-board-game finish, readable at small size. No text, no numbers, no logos, no character art.
```

### Opponent player panel

```text
Transparent PNG, 380x96. Compact opponent HUD panel for a tactical digital card-board game. Empty portrait socket, health badge socket, deck and discard count sockets, restrained dark metal and brass design, slightly flatter than local player panel. No text, no numbers, no logos, no character art.
```

### Turn phase pill

```text
Transparent PNG, 220x54. Center-top turn phase pill for a tactical card-board game HUD. Empty middle reserved for dynamic Phaser text. Dark enamel, thin brass bevel, small blue and amber status lights, crisp edge readability. No text, no numbers, no logos.
```

### Hand tray desktop

```text
Transparent PNG, 760x130. Bottom hand tray for existing full card images in a tactical digital card game. Low-profile curved shelf, subtle individual card seating shadows, dark neutral base, brass side caps, cool blue selection-ready rim. Must leave cards visually dominant. No cards, no card backs, no text, no numbers, no logos.
```

### Hand tray mobile

```text
Transparent PNG, 390x122. Mobile bottom hand carousel tray for existing card thumbnails. Compact safe-area friendly shelf, soft top lip, fading left and right edges, empty center slots, dark neutral tactical board-game style. No cards, no text, no numbers, no logos.
```

### Deck slot

```text
Transparent PNG, 96x132. Deck stack slot frame for a tactical card-board HUD. Empty vertical card-sized socket with slight thickness/shadow suggesting a stack, dark graphite base, brass corner protectors, blue rim glow for selectable state. No card art, no text, no numbers, no logos.
```

### Discard slot

```text
Transparent PNG, 96x132. Discard pile slot frame for visible existing card image. Empty vertical card-sized socket, slightly worn edges, amber rim glow, subtle bottom shadow. No card art, no text, no numbers, no logos.
```

### Hidden opponent card back

```text
120x180 PNG. Original neutral hidden card back for opponent hand in a tactical card-board web game. Dark graphite and deep blue base, simple abstract crossed-path motif, thin brass border, premium board-game finish. Must not resemble any existing physical or digital card game back. No text, no logos, no faction symbols, no recognizable IP motif.
```

### Board vignette

```text
Transparent PNG, 1024x768. Very subtle board-edge vignette overlay for tactical board gameplay. Transparent center, soft dark edge shading, faint brass corner scuffs, minimal visual noise. Designed to sit over an existing board image without hiding grid, fighters, zones or cards. No text, no grid, no labels, no logos.
```

### Board frame

```text
Transparent PNG, 640x430. Thin board/table frame for a 6 by 4 tactical map area. Low-profile dark wood and graphite metal rim, small brass corner details, no internal grid, transparent interior. Must frame an existing board image without covering playable spaces. No text, no numbers, no logos.
```

### Status badge strip

```text
Transparent PNG spritesheet, 384x64, six 64x64 frames in one horizontal strip. Original tactical HUD status badges: health, movement, attack, defense, boost, card count. Abstract icon silhouettes only, no copied symbols. Dark circular medallion base, brass rim, distinct accent color per icon. No text, no numbers, no logos.
```

### Action button strip

```text
Transparent PNG spritesheet, 360x72, five 72x72 frames in one horizontal strip. Original tactical HUD action buttons: move, attack, defend, boost, end turn. Icon-like pictograms only, clean readable shapes, dark enamel button base, brass bevel, clear hover-ready rim. No text, no numbers, no logos.
```

### Selection ring

```text
Transparent PNG, 128x128. Tactical board selection ring effect for a hero miniature. Clean circular/hex hybrid ring, cyan core glow with thin white-hot edge, readable on both dark and bright board art, no filled center. No text, no logos.
```

### Move highlight

```text
Transparent PNG, 128x128. Move-space highlight tile for tactical board overlay. Soft teal-blue glow, low opacity center, sharper outer edge, readable but not blocking board art. No grid coordinates, no text, no logos.
```

### Attack highlight

```text
Transparent PNG, 128x128. Attack target highlight tile for tactical board overlay. Amber and crimson tactical glow, thin target ring, transparent center, readable over detailed board art. No text, no logos.
```

### Defense shield

```text
Transparent PNG, 96x96. Short-lived defense shield combat overlay for a tactical card-board game. Stylized translucent shield arc, blue-white rim light, comic energy flecks, transparent background. No text, no logos.
```

### Hit spark strip

```text
Transparent PNG spritesheet, 512x64, eight 64x64 frames in one horizontal strip. Comic tactical hit spark animation, amber impact core, red outer sparks, clean silhouettes, centered in each frame, no extra frames, transparent background. No text, no logos.
```

### Card play flash strip

```text
Transparent PNG spritesheet, 768x96, eight 96x96 frames in one horizontal strip. Card-play flash animation for selecting or playing a card. Blue-gold arcane/comic burst, starts compact, expands, fades cleanly, transparent background, centered in each frame. No text, no logos, no card art.
```

## Scene Integration Plan

1. Asset loader
   - Load UI chrome from `public/assets/ui/hud/`.
   - Load effects from `public/assets/ui/effects/`.
   - Load hero images from `hero.urls` or `public/assets/heroes/{heroId}/`.
   - Load card images from `card.imageUrl`.
   - Load board image from `board.imageUrl`.

2. Board render
   - Draw board image first.
   - Draw Phaser zone/grid/space overlays after board image.
   - Draw minis after overlays where appropriate.
   - Draw selection/move/attack effects above board, below HUD.

3. Player panels
   - Use generated panel PNG as background only.
   - Place existing avatar/mini in sockets.
   - Phaser text renders HP, deck count, discard count, action count.

4. Card hand
   - Use generated hand tray as background.
   - Place full existing card images as thumbnails.
   - On hover/select, enlarge the actual card image.
   - Do not recreate card title/value UI unless image is missing.

5. Hidden opponent info
   - Use generated hidden card back only for unknown opponent hand.
   - Use deck/discard slot frames for piles.
   - Counts are dynamic Phaser text.

6. Responsive behavior
   - Desktop: side inspector allowed.
   - Mobile: bottom-sheet inspector only.
   - Mobile hand starts collapsed and expands only during card selection.

## Acceptance Checklist

Visual:

- Existing full card images are visible in hand and inspector.
- Existing hero avatar, mini and card cover are visible where relevant.
- Existing board/map image is visible behind grid/zones.
- HUD chrome does not cover playable spaces or fighters.
- No duplicated card title/value text over full card images.
- No official UI/card-back/frame copy from Unmatched, Hearthstone, MTG Arena, MARVEL SNAP, Legends of Runeterra or GWENT.

Technical:

- No missing Phaser texture placeholders.
- Every visible asset URL returns 200 or resolves to local cache.
- Spritesheets have exact frame counts and dimensions.
- Transparent PNGs have clean edges and no baked background.
- `npx vite build --mode development` passes.
- Desktop screenshot at 1280x720 is readable.
- Mobile screenshot at 390x844 is readable.
- Hand collapsed/expanded states do not hide the board permanently.

Implementation gate:

- Do not run final HUD implementation until card `imageUrl` and board `imageUrl` are present in the runtime state or a local cache resolver exists.

