# CX-30 - Codex series task: ROOM mockups SC-14 ... SC-18

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It orders the five card tasks built by `prompt_build.py`, names the stand captures Claude made before the run and
the decisions Claude took for them (ВР-VS4-SC14-01…12, ВР-VS4-SC15-01, ВР-VS4-SC16-01, ВР-VS4-SC17-01…02,
ВР-VS4-SC18-01, by delegation, 2026-10-07).

| field | value |
|---|---|
| id | CX-30 (cards SC-14, SC-15, SC-16, SC-17, SC-18) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc14-room-hero-codex/`, `sc15-room-board-codex/`, `sc16-room-deck-codex/`, `sc17-room-ready-codex/`, `sc18-room-countdown-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| data | stand S09 and S10 captures by Claude, 2026-10-07 07:49 UTC, in `scraped-data/derived/<set>-codex/inputs/` (outside git) |
| image generations allowed | 0 |

## Task

```text
Series CX-30: five mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-14.codex.md -> art/imagegen/sc14-room-hero-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-15.codex.md -> art/imagegen/sc15-room-board-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-16.codex.md -> art/imagegen/sc16-room-deck-codex/
4. docs/game-design/visual/06-tasks/prompts/SC-17.codex.md -> art/imagegen/sc17-room-ready-codex/
5. docs/game-design/visual/06-tasks/prompts/SC-18.codex.md -> art/imagegen/sc18-room-countdown-codex/
Do each task completely (package contract, inputs, layout rules, deliverable, acceptance) before the next. The task
text is the "Task" section of each file; its header tables are provenance only. Each package writes only into its
own folder and its own scraped-data/derived/<set>-codex/ folder (never change the inputs/ subfolder Claude placed
there). No git, no MCP, no network, nothing under unreal/, no image generation. Where this file and a card text
differ, this file wins (the card texts were written before the captures).

Script chain: SC-14 writes the whole ROOM screen (header, two slots, hero grid, board block, deck row, bottom strip,
optional modal and optional second veil with centred text) in _tools/sc14_room_hero.py, with parameters for viewer
(host / guest), room answer, card states, board, deck row, strip and overlay. SC-15, SC-16 and SC-17 copy the FINAL
sc14_room_hero.py of package 1 unchanged; SC-18 copies the FINAL sc14_room_hero.py and sc17_room_ready.py unchanged.
SC-16 also copies the accepted SC-23 scripts unchanged (art/imagegen/sc23-inspect-deck-codex/_tools/
sc23_inspect_deck.py and sc21_inspect_own.py, sha256 from that package's manifest-sha256.json). Every package copies
screen_mockup_base.py (d970f881...) and draw_icons_v3_snapshot.py unchanged. Record each copy's sha256; extend only
in the package's own module.

Common notes (all five packages):
- SC-01 library: draws veil, panels, buttons, chips, fields, the modal with the accepted HB-08 skins; skins folder
  art/imagegen/hud-skins-v1-codex/vector/ (read README.md, runtime-style.json, slice-margins.json), tokens
  docs/unreal/contracts/hud/hud-style-tokens.json. Do not redraw those elements. Read for patterns (read only, record
  sha256 if you reuse code): art/imagegen/sc01-screen-base-codex/README.md and _tools/build_package.py (base modal:
  «ОТМЕНА» normal left, one primary «ДА» right), art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py
  (disabled with visible why), art/imagegen/sc08-lobby-list-codex/_tools/sc08_lobby_list.py and
  art/imagegen/sc09-lobby-create-codex/_tools/sc09_lobby_create.py (header, PanelInset rows, hover, unavailable
  row with why text, board tiles with whole map illustrations, CP-07 portrait discs, caption panel, overlays).
- Icons: paste art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose size equals size_su x px-per-su exactly; when
  that size does not exist render it with render(name, px) of your unchanged draw_icons_v3_snapshot.py (never call
  main()); never NEAREST-upscale. Cursors are pixel-sized: cursor-<name>-<px>.png, px = 32 x px-per-su. Used here:
  ui-menu (IC-53), cursor-pointer (IC-59), cursor-default (IC-58), ui-close only if SC-23's renderer draws it.
  ui-check (IC-57) does not exist yet: see ВР-VS4-SC14-09.
- Portraits (CP-07, art/imagegen/portrait-crop-v1-codex/README.md: ROOM card 120 su B, ROOM slot 80 su B, ROOM
  sidekick 40 su B without number; class S slot 64 su B): source PNGs scraped-data/derived/ue-media-v1/avatars/
  <king-arthur|medusa>.png and .../sidekicks/<king-arthur-merlin|medusa-harpies>.png (CP-01 conversions of the
  avatarUrl / sidekicks[].avatarUrl WebP), circle from art/imagegen/portrait-crop-v1-codex/portrait-crops.json
  (keys king-arthur, medusa, king-arthur/merlin, medusa/harpies), portrait-underlay-<su> and portrait-edge-<su> x1/x2
  from that package's vector/ (select and resample like the library's skin()). No team ring, no team colour.
- Strings, RU column only, cite each in manifest facts (file + key or file + row):
  docs/unreal/contracts/hud/st-screens.csv: screens.room.title «Комната · код {code}», screens.room.code.copy
  «Копировать», screens.room.slot.host «Хост», screens.room.slot.ai «ИИ-соперник», screens.room.ready «Готов»,
  screens.room.not.ready «Не готов», screens.room.hero.pick «Выбрать», screens.room.hero.picked «Выбрано»,
  screens.room.board.title «Доска», screens.room.deck.view «Просмотр колоды», screens.room.deck.count (RU plural:
  30 -> «Колода: 30 карт»), screens.room.start «Начать партию», screens.room.leave «Выйти из комнаты»,
  screens.room.status.waiting «Ждём готовности соперника…», screens.room.status.all.ready «Все готовы»,
  screens.room.countdown «Партия начинается…», common.confirm.yes «Да», common.confirm.cancel «Отмена».
  docs/unreal/contracts/hud/why-reasons.json: why.hero.taken «Выбран соперником», why.room.not.ready «Соперник не
  готов», why.room.no.hero «Выберите героя», why.room.board.locked «Доску выбирают при создании комнаты».
  Proposed keys from the card rows (docs/game-design/visual/06-tasks/screens.csv column "do") or 04: screens.room.
  hero.stats «HP {hp} · ход {move}», screens.room.hero.melee «ближний бой», screens.room.hero.ranged «дальний бой»,
  screens.room.leave.confirm «Выйти из комнаты?», screens.lobby.create.mode «Режим», screens.lobby.create.mode.1v1
  «1×1», screens.lobby.create.mode.ai «Против ИИ». Proposed by Claude (ВР-VS4-SC14-05, -SC17-01):
  screens.room.slot.no.hero «Герой не выбран», screens.room.slot.ai.hero «Герой ИИ — при старте». Buttons are upper
  case (type.button). List every proposed key in README as a string-table delta.
- The sha256 prefixes inside the task texts are from when the cards were written; use the current files and record
  their current sha256 in source-hashes-before.json.
- Background: the Marmoreal P7 K1 frame named in the tasks under panel.veil 0.6 (one veil, no blur), a placeholder
  until SC-02; in the game the menu background has no figures (ВР-75). Keep the caption «фон-заглушка: в игре фигур
  нет (ВР-75)» in a small panel that hugs its text (as SC-08), inside the safe area, touching nothing (ВР-VS4-SC14-12).
- ROOM is a full screen over the veil: header, slots, grid, board block, deck row and strip are a screen layer,
  exempt from the figure and space overlap rule like modals (04 section 1.6). Report them as kind "screen" in
  verification.json (the header is drawn with the library kind "panel" for its 0.92 alpha and still reported as
  screen layer); persistent match panels: none, overlap 0 px^2.
- Canvases: library Viewport.preset 1080p/720p x 100/150 (1920x1080, 1706.67x960, 1280x720, 1137.78x640 su). Write
  the rectangles per canvas in layout-geometry.json with the BindWidget names of the card's UE column: Header
  (TitleText, CopyButton, ModeText, MenuButton), UUmRoomSlot[n] (Avatar, NameText, HostChip, ReadyText, HeroLine,
  SidekickLine), HeroGrid, UUmHeroCard[n] (Portrait, NameText, StatsText, AttackText, SidekickRow, AbilityText,
  PickButton), BoardBlock, UUmBoardCard[n], DeckCount, DeckButton, BottomStrip (LeaveButton, StatusText, ReadyButton,
  StartButton), UUmConfirmDialog, CountText.
- Images with the K1 frame, an avatar, a map illustration or a card scan go only to scraped-data/derived/
  <set>-codex/; the package folder holds scripts, JSON, README and overlay sheets on a plain card.navy background
  with outlines and labels only (ВР-VS4-01). No «уточнить» on any mockup: every value below is resolved.
- verification.json: the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line) plus text contrast per panel, icon and edge contrast, smallest text
  px at 720p, overlap, primary-button count per frame, and a check that every drawn value equals the captured answer
  (codes, usernames, heroes, ready flags, boardId, mode). Do not repeat the per-file hashes of the 1499 hud-icons-v3
  files (tree digest, count, changed files, icons used). manifest-sha256.json covers every package file except
  itself, every file in scraped-data/derived/<set>-codex/ (inputs/ included) and the inputs.
- Open and look at every final PNG before you finish a package (colour and grey, all four canvases). README.md in
  Russian, status «предложено».

Real data (captured by Claude before the run; the same six files in every package's inputs/; no password or token in
any file; never copy backend/prisma/seed.ts anywhere, cite its lines by number):
- room-state.json (stand S09): one real 1v1 room, code 6PPWSS, board c121b47f8d6eb28daccb76d05 (Marmoreal), host
  ProGamer (seed.ts line 34), guest Veteran (seed.ts line 44). steps: created; joined (two seats, no hero);
  host_picked (ProGamer Medusa, Veteran none) and guest_view_host_picked; guest_select_taken_hero (server refusal
  «Герой уже выбран другим игроком этой игры»); both_picked (ProGamer Medusa, Veteran King Arthur, nobody ready) and
  guest_view_both_picked; host_ready (ProGamer ready, Veteran not); start_refused_guest_not_ready (server refusal
  «Не все игроки готовы»); all_ready and host_view_all_ready; started and guest_view_started (IN_PROGRESS). The
  room was aborted after the capture.
- room-sarpedon.json (stand S09): second real 1v1 room, code PLN46F, board c7fa64a26c29a0835f2383e63 (Sarpedon),
  ProGamer Medusa / Veteran King Arthur, nobody ready (step both_picked, host_view).
- room-vsai.json (stand S10): VS_AI room, code PKKN2P, Marmoreal, ProGamer picked Medusa and is ready
  (ready_before_start). The server seats the bot only at startGame (GameService.setupAiOpponent): the room answer
  before start has no bot seat and no bot hero; the startGame answer (evidence only) shows «AI Bot» with a hero
  outside the MVP roster. Bot username «AI Bot» = backend/prisma/seed-ai.ts line 24.
- all-boards.json: adminBoard(id) names «Marmoreal · original map», «Sarpedon · original map» (the public boards
  catalog has no graph maps).
- heroes.json: adminHero(id) (the admin :5480 data): King Arthur nameRu «King Arthur», HP 18, movement 2,
  attackType melee, sidekick Merlin HP 7 movement 2 range; Medusa nameRu «Medusa», HP 16, movement 3, attackType
  range, sidekicks 3 x Harpies HP 1 movement 3 melee; ability.description (EN only); avatar file map.
- capture-log.json: every request and answer (tokens stripped).

Decisions made by Claude before the run (by delegation, 2026-10-07):
- ВР-VS4-SC14-01 (names and numbers): names are the DB values the client shows (ВР-VS2-02): heroes Hero.nameRu
  «King Arthur», «Medusa»; sidekicks sidekicks[].name «Merlin», «Harpies» (the DB has no RU sidekick name). The RU
  forms of 05-content-matrix («Король Артур», «Медуза», «Мерлин», «Гарпии») wait for a DB content task; list them in
  README, do not draw them. HP, move and attack from adminHero (= scrape): King Arthur move 2 (the S01 catalogue's
  3 is the known defect GD-019). Attack type as a word: melee -> «ближний бой», range -> «дальний бой».
- ВР-VS4-SC14-02 (ability): Hero.ability.description from adminHero (= scrape specialAbility) is EN only; no RU text
  exists in the DB or the scrape. Draw it verbatim (no translation), up to 3 lines and «…» (2 lines in class S),
  type.caption, text.secondary, preceded by a small Chip «EN» (02 section 3.4: EN is never substituted silently).
  README lists the missing RU ability text as a content gap.
- ВР-VS4-SC14-03 (header): header panel per 04 table (panel.bg 0.92, library kind "panel"): «Комната · код 6PPWSS»
  (screens.room.title, type.title, the code in card.cream), then «КОПИРОВАТЬ» (normal button, 40 su), then «Режим»
  (type.body, text.secondary) and «1×1» / «Против ИИ» (type.body, text.primary); at the right the «≡» menu button
  40x40 su (Btn_Normal, ui-menu 24 su). No language chips in ROOM.
- ВР-VS4-SC14-04 (L canvases): 04 section 1.4 rects exactly (1080p and 720p columns). Slots: two screen panels of
  the slot-column width x 200 su (1080p 560, 720p 500), stacked from y 112 with 16 su gap; nothing behind the rest
  of the column. Hero grid: no heading (no string key); 300x420 su cards from the grid's top-left, 16 su gap, a
  4-column template with only the two playable cards drawn (King Arthur, then Medusa; no placeholders). Board block
  per 04 rect (screen panel): «Доска» (type.heading) at the left, the two board cards to its right, the locked
  reason to the right of the cards. Deck row: a screen panel under the board block, 1080p (608, 864, 1288, 80),
  720p (548, 764, 1135, 68): «Колода: 30 карт» (type.body, tabular digits) then «ПРОСМОТР КОЛОДЫ» (normal 40 su).
  Bottom strip per 04 rect: «ВЫЙТИ ИЗ КОМНАТЫ» normal at the left, the status centred (type.body, text.primary), at
  the right the ready toggle and, for the host, «НАЧАТЬ ПАРТИЮ» (primary 48 su). The why text of a disabled button
  is visible in type.caption, text.secondary, directly under it inside the strip or row (left of it when it does not
  fit); when two adjacent disabled controls share one reason, show it once under the pair and record it for both.
- ВР-VS4-SC14-05 (slots): avatar 80 su (class S 64) of the seat's hero; a seat without a hero shows an empty disc
  (portrait-underlay + portrait-edge, no glyph) and the hero line «Герой не выбран» (proposed screens.room.slot.no.hero,
  text.secondary). Name line: username (type.heading, text.primary); slot 1 adds a Chip «Хост»; slot 2 has no role
  chip (VS_AI: Chip «ИИ-соперник» then «AI Bot»). Ready mark (ВР-VS4-SC14-09) + «ГОТОВ» (type.button, text.primary)
  or «Не готов» (type.body, text.secondary). Hero line «Medusa · HP 16 · ход 3»; sidekick line «+ Harpies ×3 · HP 1»
  / «+ Merlin · HP 7» (type.body, text.secondary). If the name line does not fit, the ready mark goes on its own line.
- ВР-VS4-SC14-06 (hero card, L 300x420): PanelInset body. Top to bottom: portrait 120 su centred; name
  (type.heading); «HP 18 · ход 2» (type.body, tabular digits); attack word (type.body, text.secondary); sidekick row:
  40 su mini portrait + «Merlin · HP 7 · дальний бой» / «Harpies ×3 · HP 1 · ближний бой» (type.body, at most two
  lines; Harpies = one picture without number, the count is «×3», CP-07 ROOM rule over ВР-47); the ability block
  (ВР-VS4-SC14-02); at the bottom a 40 su button across the inner width «ВЫБРАТЬ» (normal). States: hover = body
  panel.bg.hover (PanelInset radius) and «ВЫБРАТЬ» in Btn_Hover with cursor-pointer on it; picked (own) = 3 su
  state.pending edge on the card and the button slot holds a Btn_Selected chip «ВЫБРАНО» (card.glyph); taken
  (opponent's) = portrait and mini portrait at saturation x0.4, name and numbers in text.secondary, no button: its
  slot holds why.hero.taken «Выбран соперником» (type.body, text.secondary, centred), the same text as hover tooltip
  (geometry only). No pick button is ever primary. In grey the three states differ by edge + chip, missing button +
  text, hover body.
- ВР-VS4-SC14-07 (primary): host view: «НАЧАТЬ ПАРТИЮ» is the window's one primary (BtnPrimary_Disabled with its
  why until both seats are ready); the host's ready toggle is normal. Guest view: no Start button; the ready toggle
  is the guest's primary (disabled with why.room.no.hero without a hero). A toggle that is on uses Btn_Selected
  («ГОТОВ», card.glyph) and is never primary, so a ready guest has no primary. Status: screens.room.status.all.ready
  when both seats are ready, else screens.room.status.waiting.
- ВР-VS4-SC14-08 (SC-14 frames): waiting = host view of step joined (no heroes; King Arthur card hovered; toggle and
  Start disabled with why.room.no.hero shown once; «ПРОСМОТР КОЛОДЫ» disabled with why.room.no.hero); picked = host
  view of host_picked (Medusa picked; slot 2 Veteran «Герой не выбран»; toggle normal; Start disabled with
  why.room.not.ready; deck row enabled for Medusa); taken = guest view of guest_view_host_picked (Medusa card taken,
  the server refusal guest_select_taken_hero is its proof; King Arthur normal; guest toggle primary-disabled with
  why.room.no.hero; deck button disabled). No keyboard focus ring in any frame of the series.
- ВР-VS4-SC14-09 (check mark): IC-57 ui-check is not drawn yet (card «ждёт IC-33»). Use the accepted HB-08 Check_On
  (24 su, read-only, no hover) before «ГОТОВ» and Check_Off before «Не готов» in slots, and Check_On as the board
  check chip. README lists IC-57 as missing; do not draw a «✓» character.
- ВР-VS4-SC14-10 (board block, shared by all packages): two board cards 240x136 su, Marmoreal left, Sarpedon right;
  card body Chip skin; the whole map illustration scraped-data/images/maps/<marmoreal|sarpedon>.png on top (aspect
  kept, no crop, nothing printed over it) and the adminBoard name under it (type.body). The room's board: 3 su
  state.pending edge and Check_On 24 su in the card's top-right corner (never over the illustration). The other
  card: disabled, illustration at opacity 0.4 over the body, name in text.secondary; why.room.board.locked
  «Доску выбирают при создании комнаты» visible as text next to the cards and as tooltip geometry. No hover, no
  change of board in ROOM (ВР-H11). Only these two boards exist anywhere.
- ВР-VS4-SC14-11 (class S, both 150 % canvases; starting values): margins and gaps 16 su; header (16, 16, W-32, 64);
  bottom strip (16, H-96, W-32, 80) with 40 su buttons; left column 300 su from y 96: slot 1 and slot 2 (136 su
  each, avatar 64 su), then the deck row (count above its button); right area x 332..W-16: two compact hero cards
  side by side, 360x240 su each (portrait 80 su left, text right, ability 2 lines), then the board block under them
  (title row, the two 240x136 cards side by side, locked reason right of them). Measure the real text; keep every
  element visible, never shrink type or truncate a name, code or board name; if something still does not fit change
  only spacing (>= 8 su) or the compact card height, and report it in verification.json.
- ВР-VS4-SC14-12 (caption): L: bottom of the free area under slot 2 in the left column. S: under the deck row when a
  free band fits inside the safe area, otherwise inside the header between the title block and the menu button.
- ВР-VS4-SC15-01 (SC-15 frames): board-marmoreal = host view of 6PPWSS both_picked; board-sarpedon = host view of
  PLN46F both_picked (header code PLN46F). The mockup boardId equals the room capture in both frames.
- ВР-VS4-SC16-01 (SC-16 frames): deck-count = host view of 6PPWSS both_picked, deck row «Колода: 30 карт» with
  «ПРОСМОТР КОЛОДЫ» in Btn_Hover and cursor-pointer; deck-open = the same ROOM with SC-23's deck mode for Medusa (its
  frame "deck", drawn by the unchanged SC-23 renderer from its inputs scraped-data/derived/sc23-inspect-deck-codex/
  inputs/*.json, read only, recorded in source-hashes-before.json) open over it. 30 and 11 trace to
  docs/game-design/evidence/S01/catalog-medusa.json and SC-23's deck-lists.json; composition only, no deck order.
- ВР-VS4-SC17-01 (SC-17 frames): waiting = host view of host_ready (Start disabled with why.room.not.ready; its
  proof start_refused_guest_not_ready); ready = host view of host_view_all_ready (Start primary normal, status «Все
  готовы»); guest = guest view of guest_view_both_picked (guest toggle «ГОТОВ» primary normal, host «Не готов», no
  Start); ai = host view of room-vsai.json ready_before_start: mode «Против ИИ», code PKKN2P; slot 2 = Chip
  «ИИ-соперник», «AI Bot», empty disc, «ГОТОВ» (the server seats the bot ready), hero line «Герой ИИ — при старте»
  (proposed screens.room.slot.ai.hero); never draw the bot's hero; Start primary normal, status «Все готовы»;
  leave = the waiting frame plus the SC-01 base modal: title «Выйти из комнаты?» (screens.room.leave.confirm),
  «ОТМЕНА» normal left, «ДА» primary right; Start under it is disabled, so «ДА» is the only primary.
- ВР-VS4-SC17-02: no team colour on slots (02 section 2.3); screen sounds are not part of a mockup (05 section 3,
  VS-7 note): do not draw or list sound hooks in any package.
- ВР-VS4-SC18-01 (SC-18 frames): countdown-3 = the SC-17 ready frame (host view, host_view_all_ready) under a second
  panel.veil at 0.8 over the whole screen, the digit «3» centred (type.display, text.primary, tabular); starting =
  the guest view of all_ready (both ready, the guest toggle on, no primary) under the same 0.8 veil, «Партия
  начинается…» centred (type.title). The contract st-screens.csv wins over the card: screens.room.countdown is
  «Партия начинается…»; the digit is a number (README notes a proposed key for it). Triggers: step started (host)
  and guest_view_started (guest). No hover, no focus, cursor-default; frames 2 and 1 are motion, not drawn.

Extra inputs (add them to source-hashes-before.json and the manifest of every package that uses them):
docs/unreal/contracts/hud/st-screens.csv; docs/unreal/contracts/hud/why-reasons.json;
docs/unreal/contracts/hud/hud-style-tokens.json; docs/game-design/visual/06-tasks/screens.csv (rows SC-14...SC-18,
column "do"); AGENTS.md (section «Board scenes and heroes», the two board ids);
docs/game-design/decisions/2026-10-04-real-boards-only.md; art/imagegen/hud-skins-v1-codex/ (README.md,
runtime-style.json, slice-margins.json, vector/); art/imagegen/sc01-screen-base-codex/ (README.md, _tools/);
art/imagegen/hud-icons-v3/_tools/draw_icons.py and the sizes/ files you paste; scraped-data/images/maps/marmoreal.png
and sarpedon.png; scraped-data/derived/ue-media-v1/avatars/king-arthur.png, medusa.png and
scraped-data/derived/ue-media-v1/sidekicks/king-arthur-merlin.png, medusa-harpies.png; art/imagegen/
portrait-crop-v1-codex/ (README.md, portrait-crops.json, vector/portrait-edge-*, vector/portrait-underlay-*);
backend/prisma/seed.ts and backend/prisma/seed-ai.ts (lines only); scraped-data/derived/<set>-codex/inputs/*.json
(six files); for SC-16 also art/imagegen/sc23-inspect-deck-codex/ (README.md, _tools/, manifest-sha256.json) and
scraped-data/derived/sc23-inspect-deck-codex/inputs/*.json.
```
