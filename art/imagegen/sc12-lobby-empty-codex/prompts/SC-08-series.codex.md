# CX-29 - Codex series task: LOBBY mockups SC-08 ... SC-13

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It only orders the six card tasks built by `prompt_build.py` and adds the inputs Claude captured and the decisions
Claude made before the run (ВР-VS4-SC08-01…13, ВР-VS4-SC09-01…03, ВР-VS4-SC10-01, ВР-VS4-SC11-01…05,
ВР-VS4-SC12-01, ВР-VS4-SC13-01, by delegation, 2026-10-07).

| field | value |
|---|---|
| id | CX-29 (cards SC-08, SC-09, SC-10, SC-11, SC-12, SC-13) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc08-lobby-list-codex/`, `sc09-lobby-create-codex/`, `sc10-lobby-create-ai-codex/`, `sc11-lobby-code-codex/`, `sc12-lobby-empty-codex/`, `sc13-lobby-error-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| data | stand S09 captures by Claude, 2026-10-07 06:29-06:30 UTC, in `scraped-data/derived/<set>-codex/inputs/` (outside git) |
| image generations allowed | 0 |

## Task

```text
Series CX-29: six mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-08.codex.md -> art/imagegen/sc08-lobby-list-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-09.codex.md -> art/imagegen/sc09-lobby-create-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-10.codex.md -> art/imagegen/sc10-lobby-create-ai-codex/
4. docs/game-design/visual/06-tasks/prompts/SC-11.codex.md -> art/imagegen/sc11-lobby-code-codex/
5. docs/game-design/visual/06-tasks/prompts/SC-12.codex.md -> art/imagegen/sc12-lobby-empty-codex/
6. docs/game-design/visual/06-tasks/prompts/SC-13.codex.md -> art/imagegen/sc13-lobby-error-codex/
Do each task completely (its package contract, inputs, layout rules, deliverable and acceptance) before starting the
next. The task text is the "Task" section of each file; its header tables are provenance only. Each package writes
only into its own folder and its own scraped-data/derived/<set>-codex/ folder (never change the inputs/ subfolder
Claude placed there). No git, no MCP, no network, nothing under unreal/, no image generation.
Script chain: SC-08 writes the whole LOBBY screen (header, list, Create and Join columns at rest) in
_tools/sc08_lobby_list.py with parameters for the list state and the right-column states. SC-09, SC-11, SC-12 and
SC-13 copy the FINAL sc08_lobby_list.py of package 1 unchanged into their _tools/; SC-10 copies the FINAL
sc08_lobby_list.py and sc09_lobby_create.py unchanged. Record each copy's sha256 and extend only in the package's own
module. Every package also copies screen_mockup_base.py unchanged.

Common notes (they apply to all six packages):
- SC-01 library: copy art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py unchanged (sha256 d970f881...
  in that package's manifest-sha256.json). It draws the veil, panels, buttons, chips, text fields and the spinner
  with the accepted HB-08 skins: pass art/imagegen/hud-skins-v1-codex/vector/ as the skins folder (read its README.md,
  runtime-style.json and slice-margins.json; PanelInset is the list-row skin) and
  docs/unreal/contracts/hud/hud-style-tokens.json as the tokens. Do not redraw those elements yourself; extend the
  library in your module. Read art/imagegen/sc01-screen-base-codex/README.md and its _tools/build_package.py for the
  accepted patterns. The accepted LOGIN packages show the patterns for disabled-with-reason, keyboard focus, the busy
  (in-flight) button with spinner and busy cursor, and the error zone with badge-refuse:
  art/imagegen/sc06-login-form-codex/_tools/sc06_login_form.py and
  art/imagegen/sc07-login-errors-codex/_tools/sc07_login_errors.py (read only; record sha256 if you reuse code).
- Icons: paste the art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose pixel size equals size_su x px-per-su exactly
  (sizes 16, 18, 21, 24, 32, 36, 48, 64, 72, 96 exist). When that size does not exist (for example 24 su at 720p 150 %
  = 27 px), render it with render(name, px) of your unchanged copy of art/imagegen/hud-icons-v3/_tools/draw_icons.py
  (_tools/draw_icons_v3_snapshot.py, never call its main()); if that cannot run, resample the next larger file with
  LANCZOS and write it in verification.json. Never NEAREST-upscale an icon. Cursors are pixel-sized (02 section 4.4):
  cursor-<name>-<px>.png with px = 32 x px-per-su of the canvas. Icons used here: ui-menu (IC-53), cursor-pointer
  (IC-59), cursor-busy (IC-61), loader-spinner, badge-refuse (IC-40), state-hint, resource-connection-lost.
- Strings, RU column only, cite each in manifest facts (file + key, or file + row):
  docs/unreal/contracts/hud/st-screens.csv: screens.lobby.list.title «Список игр», screens.lobby.list.empty «Сейчас
  открытых игр нет. Создайте комнату и передайте код другу», screens.lobby.list.error «Не удалось загрузить список
  игр», screens.lobby.row.join «Войти», screens.lobby.create.title «Создать игру», screens.lobby.create.mode.1v1 «1×1»,
  screens.lobby.create.mode.ai «Против ИИ», screens.lobby.create.board «Доска», screens.lobby.create.submit «Создать»,
  screens.lobby.code.title «Войти по коду», screens.lobby.code.submit «Войти», screens.lobby.recover «Вернуться в мою
  партию», common.btn.retry «Повторить». docs/unreal/contracts/hud/why-reasons.json: why.code.length «Введите 6
  символов», why.room.started «Игра уже началась», why.room.full «Комната заполнена», why.syncing «Синхронизация…».
  Proposed keys that exist only in the card rows or in 04 (docs/game-design/visual/06-tasks/screens.csv column "do",
  04 section 1.3; ВР-SC15): common.btn.refresh «Обновить» (SC-08 trigger), screens.lobby.create.mode «Режим» (04
  section 1.3 scheme "Режим:"), screens.lobby.create.busy «Создаём…» (SC-09), screens.lobby.create.ai.note «Соперник —
  ИИ: {name}» (SC-10), screens.lobby.code.error.notfound «Игра не найдена» and screens.lobby.code.error.full «Комната
  заполнена» (SC-11). Language chips «RU» and «EN» are the locale codes of 04 section 1.2. SC-13 quotes the list error
  as «Не удалось загрузить список»; the contract string in st-screens.csv wins («...список игр»).
- The sha256 prefixes written inside the task texts for 04-hud-spec.md, 02-visual-design.md and why-reasons.json are
  from the time the cards were written; these files changed since. Use the current files and record their current
  sha256 in source-hashes-before.json.
- Background: the Marmoreal P7 K1 frame named in the tasks under panel.veil 0.6 (one veil, no blur). It is a
  placeholder until SC-02; in the game the menu background has no figures (ВР-75). Keep the SC-01 overview caption
  «фон-заглушка: в игре фигур нет (ВР-75)» in a small panel that hugs its text (as the accepted SC-06 fix1), inside the
  safe area, never touching another element (placement: ВР-VS4-SC08-10).
- LOBBY is a full screen over the veil: header, list and both columns are a screen layer, exempt from the figure and
  space overlap rule like modals (04 section 1.6). Report them as kind "screen" in verification.json (the header is
  drawn with the library kind "panel" for its 0.92 alpha and still reported as screen layer); persistent match
  panels: none, overlap 0 px^2.
- Canvases: library Viewport.preset 1080p/720p x 100/150 (canvases 1920x1080, 1706.67x960, 1280x720 and
  1137.78x640 su). Write the rectangles per canvas in layout-geometry.json (BindWidget names of the card's UE column:
  Header, NicknameText, MenuButton, LangChipRu, LangChipEn, GameList, RefreshButton, UUmLobbyGameRow[n] with Code, Mode,
  Board, Seats, HeroDiscs, JoinButton; ModeChip1v1, ModeChipAi, BoardChips[n], CreateButton, CreateNote; CodeCells[n],
  JoinButton (code), CodeError, RecoverButton).
- Images with the K1 frame, an avatar or a map illustration go only to scraped-data/derived/<set>-codex/; the package
  folder holds scripts, JSON, README and the overlay sheets drawn on a plain card.navy background with outlines and
  labels only (no frame, no avatar pixels, no map pixels, no card scans) (ВР-VS4-01).
- verification.json uses the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line) plus the layout measurements of the task (text contrast per panel,
  icon and edge contrast, smallest text px at 720p, overlap, primary-button count per frame, rows vs captured answer);
  do not repeat the per-file hashes of the 1499 hud-icons-v3 files (tree digest, count, changed files, icons used).
  manifest-sha256.json covers every package file except itself, every file in scraped-data/derived/<set>-codex/
  (inputs/ included) and the inputs.
- Open and look at every final PNG before you finish a package (colour and grey, all four canvases). README.md in
  Russian, status «предложено».

Real data (captured by Claude from stand S09 before the run; files in scraped-data/derived/<set>-codex/inputs/, the
same seven files in every package):
- available-games.json: availableGames(mode: ONE_V_ONE) seen by ProGamer at the t0 poll: five LOBBY rows, answer
  order (createdAt desc): VZSJFT (Marmoreal, host Veteran, hero King Arthur), EK74C3 (Sarpedon, TestPlayer2, Medusa),
  QSMFTR (Marmoreal, NewPlayer, no hero), 4XM89G (Sarpedon, TestPlayer1, no hero), ZJ4LXZ (Marmoreal, TestPlayer1,
  Medusa). Claude created these rooms on the stand with seed test accounts for the capture (rooms_created_... in the
  file) and removed them afterwards. Field "viewer": the nickname «ProGamer» (login answer = backend/prisma/seed.ts
  line 34).
- list-join-errors.json: after t0 room 4XM89G was filled and ZJ4LXZ started; ProGamer's joinGame answered «Игра уже
  заполнена» and «Нельзя присоединиться к игре, которая уже началась или завершилась»; the next poll lists three rows.
- join-errors.json: join by code: notfound (input 3GPMCA, the stand's newest ABORTED 1v1 room, gameByCode null) and
  full (input 4XM89G: gameByCode resolved the room, NewPlayer took the seat, joinGame answered «Игра уже заполнена»);
  viewer_myGames: ProGamer had no active game.
- available-games-empty.json: availableGames(mode: ONE_V_ONE) = [] before the rooms existed (SC-12).
- all-boards.json: the public `boards` catalog (grid boards only, no graph maps) and adminBoard(id) for the two real
  maps: c121b47f8d6eb28daccb76d05 «Marmoreal · original map», c7fa64a26c29a0835f2383e63 «Sarpedon · original map».
- heroes.json: adminHero(id): cmq7d7b1000njwi74a536w55r King Arthur, cmq7d7b4000r8wi74tzd1jmxv Medusa (avatarUrl).
- capture-log.json: every request and answer of the capture (tokens stripped, no password).
No file contains a password or token; never copy backend/prisma/seed.ts anywhere, cite its lines by number.

Decisions made by Claude before the run (by delegation, 2026-10-07):
- ВР-VS4-SC08-01 (rows): the LOBBY list asks availableGames(mode: ONE_V_ONE): a VS_AI room has no human seat (04
  section 1.4) and the only extra unfiltered row of the stand is a stale VS_AI room on the synthetic Cobble City
  board. The list shows exactly the five rows of available-games.json in answer order. Code = code; mode «1×1» for
  ONE_V_ONE (screens.lobby.create.mode.1v1); board = adminBoard(boardId).name from all-boards.json; seats =
  players.length + "/2" («1/2»); a 32 su hero disc for each player with heroId (heroes.json). No host names (the card
  lists no such field). Never take a board name or id from the public catalog.
- ВР-VS4-SC08-02 (unavailable rows): availableGames never returns full or started rooms (status LOBBY, opponentId
  null). A row becomes unavailable when the client's joinGame for it answers so, until the next poll drops it: 4XM89G
  -> why.room.full «Комната заполнена», ZJ4LXZ -> why.room.started «Игра уже началась» (list-join-errors.json). The
  list frame (and the list on the left in SC-09, SC-10, SC-11) shows the five t0 rows with these two unavailable.
- ВР-VS4-SC08-03 (unavailable row look): code, mode and board in text.secondary; the seats slot empty (the last-poll
  value is stale); the hero disc stays; no Join button: its slot holds the why text (type.body, text.secondary,
  right-aligned to the button's right edge); the same text is the hover tooltip (record the why code and tooltip in
  layout-geometry.json, do not draw a tooltip). The row body stays PanelInset. In grey the row differs by the missing
  button and the visible text.
- ВР-VS4-SC08-04 (row layout): row 56 su (PanelInset skin), 8 su between rows, 16 su list padding; columns left to
  right with one fixed x per column per canvas: code (type.heading 24 su, text.primary), mode (type.body), board
  name (type.body), seats (type.body), hero disc 32 su, Join button (normal, 40 su high, min 120 su wide, right).
  Never truncate a code or a board name, never shrink type. Hover (SC-08 list frame only): the first row VZSJFT has
  body panel.bg.hover #1E2B35 (draw with the token in your module, PanelInset radius) and its Join button in the
  Btn_Hover skin, with cursor-pointer on that button. No keyboard focus ring in SC-08 frames.
- ВР-VS4-SC08-05 (list header): «Список игр» (type.heading) top left inside the list; at the top right a TEXT button
  «ОБНОВИТЬ» (normal, 40 su, common.btn.refresh): v3 has no accepted refresh glyph «⟳»; do not invent one, list the
  missing glyph in README (needs a new IC card).
- ВР-VS4-SC08-06 (loading): three skeleton rows (PanelInset 56 su, same x and gaps as the rows) with placeholder bars
  in panel.bg.hover at the code, board and button positions, drawn at the 900 ms keyframe (opacity 1.0); no text in
  them; title and «ОБНОВИТЬ» as in list; right columns at rest. Skeleton and list must differ in grey.
- ВР-VS4-SC08-07 (header): header (24, 24, 1872, 64) panel.bg 0.92 (04 table; library kind "panel"); «ProGamer»
  (type.heading, text.primary) at the left, 16 su padding; at the right the «≡» menu button 40x40 su (Btn_Normal,
  ui-menu 24 su) and then the language chips «RU» (selected, Btn_Selected skin, card.glyph text) and «EN» (Chip), 32 su
  high. The list, Create and Join columns are screen panels at panel.bg 1.0 (library kind "screen").
- ВР-VS4-SC08-08 (right columns at rest, shared by all packages): Create column = SC-09 default: title «Создать игру»
  (type.title); a mode row with the label «Режим» (type.body, text.secondary) then chips «1×1» (selected) and «Против
  ИИ» (32 su); the label «Доска» above two board tiles side by side (Marmoreal left, Sarpedon right): each tile = the
  whole map illustration scraped-data/images/maps/<marmoreal|sarpedon>.png (aspect kept, no crop, nothing printed over
  it) with 8 su inset and the board name under it (type.body); tile skin Chip, selected tile Btn_Selected with
  card.glyph name text (Marmoreal selected at rest); «СОЗДАТЬ» primary 48 su across the column's inner width. Join
  column: title «Войти по коду» (type.title); six empty code cells (ВР-VS4-SC11-04) and the code «ВОЙТИ» 48 su right of
  them, disabled with why.code.length «Введите 6 символов» visible in the error zone under the cells (as SC-06 empty).
  «Создать» is the one primary in every frame except SC-11 code-full and code-error (ВР-VS4-SC11-02).
- ВР-VS4-SC08-09 (canvases): L canvases use the 04 section 1.3 rects exactly (1080p and 720p columns). Class S (both
  150 % canvases): margins 16 su, gaps 16 su, header (16, 16, W-32, 64), columns from y 96 to H-16; right column 456 su
  wide at x = W-16-456 (Create on top, Join under it), the list fills the rest of the width. In class S the Create
  title and the mode row share one line, the board thumbnails are 96 su high, the code cells 48x48 su (as 04 class S
  cells) and the code «ВОЙТИ» goes under the cells. These are starting values: measure the real text; keep every
  element visible, never shrink type or truncate; if something still does not fit change only spacing (>= 8 su) and
  report it in verification.json.
- ВР-VS4-SC08-10 (caption): L canvases: bottom right under the Join column. S canvases: under the Join column when a
  free band fits inside the safe area, otherwise inside the header between the nickname and the menu button.
- ВР-VS4-SC08-11 (discs): the hero disc is the LOBBY show of CP-07 (art/imagegen/portrait-crop-v1-codex/README.md:
  LOBBY 32 su, variant B): source PNG scraped-data/derived/ue-media-v1/avatars/<king-arthur|medusa>.png (CP-01),
  circle from art/imagegen/portrait-crop-v1-codex/portrait-crops.json, portrait-underlay-32 and portrait-edge-32 x1/x2
  from that package's vector/ (select and resample like the library's skin()). No team ring, no name. On overlays only
  an outline circle with a label.
- ВР-VS4-SC08-12: screen sounds are not part of a mockup (05 section 3, VS-7 note); do not draw or list sound hooks.
- ВР-VS4-SC08-13: no image with readable card scans, card backs, avatars or map illustrations is in a package folder;
  such images go only to scraped-data/derived/<set>-codex/.
- ВР-VS4-SC09-01 (SC-09 frames): create-marmoreal = the rest state (1×1, Marmoreal selected, «СОЗДАТЬ» primary
  normal); create-sarpedon = Sarpedon tile selected, Marmoreal normal; busy = after create-marmoreal: «СОЗДАТЬ» in the
  BtnPrimary_Disabled skin showing a 32 su loader-spinner left of «СОЗДАЁМ…» (screens.lobby.create.busy) as SC-07 busy
  does; why.syncing is its hover tooltip (geometry only); cursor-busy over the button; chips and tiles keep their state;
  no keyboard focus ring. The list on the left is the SC-08 list state without hover.
- ВР-VS4-SC09-02: exactly two tiles; names and ids verbatim from the adminBoard answers in all-boards.json; facts cite
  them; no other board anywhere.
- ВР-VS4-SC09-03: SC-09's error state («Сервер недоступен») is outside its deliverable and is not drawn.
- ВР-VS4-SC10-01 (SC-10 frames): create-ai = chip «Против ИИ» selected (1×1 normal), Sarpedon tile selected, the note
  «Соперник — ИИ: AI Bot» (screens.lobby.create.ai.note, {name} = username 'AI Bot' of backend/prisma/seed-ai.ts line
  24; type.body, text.secondary >= 4.5:1) between the mode row and «Доска» (in class S wherever it fits inside the
  column), «СОЗДАТЬ» primary; no bot hero, no AI avatar. busy = the same with «СОЗДАТЬ» in the SC-09 busy look. The
  Join column stays at rest.
- ВР-VS4-SC11-01 (SC-11 frames, codes from the captures): code-partial = «VZSJ» (first four characters of VZSJFT) in
  cells 1-4, cell 5 in the Input_Focus skin (keyboard typing), cell 6 empty; code «ВОЙТИ» disabled with «Введите 6
  символов» visible; «Создать» primary. code-full = «VZSJFT» in all six cells, the code «ВОЙТИ» primary with the
  keyboard focus skin (BtnPrimary_Focus). code-error-notfound = «3GPMCA» kept in the cells, error zone: badge-refuse
  24 su + «Игра не найдена» (type.body, text.primary). code-error-full = «4XM89G» kept, badge-refuse 24 su + «Комната
  заполнена». In both error frames the cells stay Input_Normal (never cleared, no Input_Error: the badge carries the
  error), the code «ВОЙТИ» is primary normal, no focus ring; only the X is red. badge-refuse (IC-40, accepted) replaces
  the marker-x-stamp placeholder named in SC-11; add it to the inputs.
- ВР-VS4-SC11-02 (primary): with six characters typed the code «ВОЙТИ» is the window's one primary and «СОЗДАТЬ» is
  drawn as a normal button (Btn_Normal); with fewer characters «СОЗДАТЬ» is primary.
- ВР-VS4-SC11-03 (recover): ProGamer's myGames was empty (join-errors.json viewer_myGames), so «Вернуться в мою
  партию» is hidden in every frame; its slot (normal button 40 su inside the Join column under the error zone) appears
  only on the overlay sheet as a dashed outline «RecoverButton · если myGames вернул активную партию».
- ВР-VS4-SC11-04 (cells): 56x56 su (class S 48x48), gap 8 su, Input_Normal skin; a filled cell shows its character in
  type.title, text.primary, centred, upper case; an empty cell shows an underline 24x2 su in text.secondary centred
  12 su above its bottom (shape channel); the focused cell uses Input_Focus.
- ВР-VS4-SC11-05: the CUE-004 refusal shake and sound are motion and audio, not drawn.
- ВР-VS4-SC12-01 (SC-12): available-games-empty.json -> the list keeps its title and «ОБНОВИТЬ», no rows; a centred
  block: state-hint 32 su above «Сейчас открытых игр нет. Создайте комнату и передайте код другу» (type.body,
  text.secondary, centred, wrapped at a word boundary into at most two lines on every canvas); right columns at rest.
- ВР-VS4-SC13-01 (SC-13): the list keeps its title; «ОБНОВИТЬ» is hidden (the error offers «ПОВТОРИТЬ», one action
  once); a centred block: resource-connection-lost 48 su (its red X is the only red), «Не удалось загрузить список
  игр» (type.body, text.primary), «ПОВТОРИТЬ» normal 40 su; right columns at rest; «СОЗДАТЬ» is the only primary.

Extra inputs (add them to source-hashes-before.json and the manifest of every package that uses them):
docs/unreal/contracts/hud/st-screens.csv (sha256 0e013fe77499...); docs/unreal/contracts/hud/why-reasons.json
(42ebdea2fbf1...); docs/unreal/contracts/hud/hud-style-tokens.json (ff043c7b1080...);
docs/game-design/visual/06-tasks/screens.csv (rows SC-08...SC-13, column "do"); AGENTS.md (section «Board scenes and
heroes», the two board ids); docs/game-design/decisions/2026-10-04-real-boards-only.md;
art/imagegen/hud-skins-v1-codex/ (README.md, runtime-style.json, slice-margins.json, vector/);
art/imagegen/sc01-screen-base-codex/ (README.md, _tools/); art/imagegen/hud-icons-v3/_tools/draw_icons.py and the
sizes/ files you paste; scraped-data/images/maps/marmoreal.png (c28ce0d71558...) and sarpedon.png (4c5941fa4f71...);
scraped-data/derived/ue-media-v1/avatars/king-arthur.png (6e37a6e8b10e...) and medusa.png (631b33ee4101...);
art/imagegen/portrait-crop-v1-codex/ (README.md, portrait-crops.json 8061720ddb43..., vector/portrait-edge-32-*,
vector/portrait-underlay-32-*); backend/prisma/seed.ts (bb103d0423a3..., lines only); for SC-10
backend/prisma/seed-ai.ts (d8df11b7886a...); scraped-data/derived/<set>-codex/inputs/*.json (seven files); for SC-11
also art/imagegen/hud-icons-v3/sizes/badge-refuse-24.png (25d35180b44c...).
```
