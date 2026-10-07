# CX-31 - Codex series task: match loading mockups SC-19, SC-20

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It orders the two card tasks built by `prompt_build.py`, names the data Claude placed before the run and the decisions
Claude took for them (ВР-VS5-SC19-01…08, ВР-VS5-SC20-01…03, by delegation, 2026-10-07).

| field | value |
|---|---|
| id | CX-31 (cards SC-19, SC-20) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc19-loading-codex/`, `art/imagegen/sc20-loading-error-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| data | byte copies of Claude's stand S09 captures of 2026-10-07 07:49 UTC (CX-30) in `scraped-data/derived/<set>-codex/inputs/` (outside git) |
| image generations allowed | 0 |

## Task

```text
Series CX-31: two mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-19.codex.md -> art/imagegen/sc19-loading-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-20.codex.md -> art/imagegen/sc20-loading-error-codex/
Do each task completely (package contract, inputs, layout rules, deliverable, acceptance) before the next. The task
text is the "Task" section of each file; its header tables are provenance only. Each package writes only into its
own folder and its own scraped-data/derived/<set>-codex/ folder (never change the inputs/ subfolder Claude placed
there). No git, no MCP, no network, nothing under unreal/, no image generation. Where this file and a card text
differ, this file wins (the card texts were written before the data was placed).

Script chain: SC-19 writes the whole LOADING screen in _tools/sc19_loading.py with parameters for the stage row
(caption key, spinner or icon), the hero cards, the board line and an optional button row. SC-20 copies the FINAL
sc19_loading.py of package 1 unchanged and extends it only in _tools/sc20_loading_error.py. Both packages copy
screen_mockup_base.py (d970f881...) and art/imagegen/hud-icons-v3/_tools/draw_icons.py (as
draw_icons_v3_snapshot.py) unchanged. Record each copy's sha256 (copy-provenance.json).

Common notes (both packages):
- SC-01 library: veil, panels, buttons, chips with the accepted HB-08 skins; skins folder
  art/imagegen/hud-skins-v1-codex/vector/ (read README.md, runtime-style.json, slice-margins.json), tokens
  docs/unreal/contracts/hud/hud-style-tokens.json. Do not redraw those elements. Read for patterns (read only, record
  sha256 if you reuse code): art/imagegen/sc01-screen-base-codex/README.md, art/imagegen/sc03-boot-loading-codex/ and
  art/imagegen/sc04-boot-error-codex/ (spinner row, error row with a 48 su icon, retry button, overlays with
  BindWidget names and x/y/w/h su), art/imagegen/sc14-room-hero-codex/_tools/sc14_room_hero.py (CP-07 portrait discs,
  the ВР-75 caption panel).
- Icons: paste art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose size equals size_su x px-per-su exactly; when
  that size does not exist render it with render(name, px) of your unchanged draw_icons_v3_snapshot.py (never call
  main()); never NEAREST-upscale and never use the library's spinner() for sizes other than its source (it resizes
  with NEAREST). The spinner is drawn at step 0 in every frame: rotation is motion, not drawn (ВР-VS5-SC19-07).
  Used here: loader-spinner (48 su), resource-connection-lost (48 su, SC-20).
- Portraits (CP-07, art/imagegen/portrait-crop-v1-codex/README.md: loading show = 160 su, variant B): source PNGs
  scraped-data/derived/ue-media-v1/avatars/medusa.png and king-arthur.png (CP-01 conversions of the Hero.avatarUrl
  WebP named in the task; heroes.json avatar_files maps them), circle from
  art/imagegen/portrait-crop-v1-codex/portrait-crops.json (keys medusa, king-arthur), portrait-underlay-160 and
  portrait-edge-160 x1/x2 from that package's vector/ (select and resample like the library's skin()). No team ring,
  no team colour (02 section 2.3).
- Strings, RU column only, cite each in manifest facts (file + key):
  docs/unreal/contracts/hud/st-screens.csv: screens.loading.connect «Подключение к партии…», screens.loading.state
  «Загрузка состояния…», screens.loading.board «Подготовка поля…», screens.loading.versus «против»,
  screens.loading.error «Не удаётся подключиться», common.btn.retry «Повторить». Proposed by the card SC-20 (not in
  the table yet): common.btn.lobby «В лобби» — its text equals the existing rows screens.result.lobby and
  screens.aborted.lobby; cite those rows and list common.btn.lobby in README as a string-table delta. Buttons are
  upper case (type.button).
- Real data (Claude placed it in scraped-data/derived/<set>-codex/inputs/ of both packages; provenance.json says where
  each byte copy comes from; no password or token in any file; never copy backend/prisma/seed.ts anywhere, cite its
  lines by number): room-state.json step "started" = the startGame answer of room 6PPWSS on stand S09: status
  IN_PROGRESS, boardId c121b47f8d6eb28daccb76d05, seat 0 ProGamer (seed.ts line 34) with heroId
  cmq7d7b4000r8wi74tzd1jmxv, seat 1 Veteran (seed.ts line 44) with heroId cmq7d7b1000njwi74a536w55r; heroes.json
  adminHero(id) -> nameRu «Medusa» and «King Arthur» and the avatar file map; all-boards.json adminBoard(id) name
  «Marmoreal · original map». The run I README stays an input (same accounts, host pro@ / joiner veteran@). No
  «уточнить» on any mockup: every value is resolved.
- ВР-VS5-SC19-01 (viewer and sides): the viewer is the host ProGamer (seat 0): own hero card left «Medusa» /
  «ProGamer», opponent right «King Arthur» / «Veteran», as in the card. Hero names are Hero.nameRu as the client shows
  them (ВР-VS2-02; RU forms «Медуза», «Король Артур» wait for a content task: list them in README, do not draw them).
- ВР-VS5-SC19-02 (one screen panel): the whole loading content sits on ONE centred screen panel LoadingPanel (library
  panel kind "screen", panel.bg 1.0), so every text reads over the busy frame. Inner layout, same su on all four
  canvases (04 section 1.5 «720p — те же su»): padding 24 su; row 1 StageRow 48 su high: Spinner 48 su, 12 su gap,
  StageText (type.title, text.primary), the pair centred as one group; 24 su gap; row 2: LeftCard 240x320, versus
  column 96 su wide with VersusText «против» (type.heading, text.secondary, centred on the card centre line), RightCard
  240x320; 24 su gap; row 3 BoardText «Marmoreal · original map» (type.heading, text.primary, centred); 24 su padding.
  Panel width 24+240+96+240+24 = 624 su; height = content (about 494 su); centred on the canvas.
- ВР-VS5-SC19-03 (hero cards): LeftCard and RightCard are PanelInset skins inside the panel; content centred
  vertically and horizontally in the 240x320 card: Portrait 160 su disc, 16 su, NameText (type.heading,
  text.primary), 4 su, NickText (type.caption, text.secondary). Never decline or abbreviate a name.
- ВР-VS5-SC19-04 (StageRow width): the stage row group keeps the width of the longest of the three captions so the
  spinner does not jump between frames; the shorter captions are left-aligned after the spinner inside that group.
- ВР-VS5-SC19-05 (frames): connect = screens.loading.connect, state = screens.loading.state, board =
  screens.loading.board; everything else identical. No buttons, no hover, no focus ring, no cursor in SC-19.
- ВР-VS5-SC19-06 (background): the Marmoreal P7 K1 frame named in the task under panel.veil 0.6 (one veil, no blur),
  a placeholder until SC-02; in the game this background has no figures (ВР-75). Keep the caption «фон-заглушка: в
  игре фигур нет (ВР-75)» (type.caption, text.secondary) in a small panel that hugs its text (as SC-14), inside the
  safe area (24 su L, 16 su S), at least 8 su away from LoadingPanel; bottom-left by default; in class S it may wrap
  into two lines. LoadingPanel and the caption panel are screen layers over the veil: exempt from the figure and space
  overlap rule like modals (04 section 1.6); report them as kind "screen"; persistent match panels: none, 0 px^2.
- ВР-VS5-SC19-07 (spinner): see Icons. ВР-VS5-SC19-08 (720p and S): the same su everywhere; LoadingPanel fits all four
  canvases (height <= canvas height - 2 x margin); if something does not fit, change only gaps (>= 8 su) and report.
- ВР-VS5-SC20-01 (error frame): the SC-19 screen with the stage row replaced by ErrorIcon resource-connection-lost
  48 su in the spinner slot (same x, y, size) and StageText «Не удаётся подключиться» (screens.loading.error,
  type.title, text.primary): the change is the icon shape, not only the text. Hero cards and board line stay.
- ВР-VS5-SC20-02 (buttons): a row under BoardText inside LoadingPanel, 24 su gap above, 48 su high, centred:
  LobbyButton «В ЛОББИ» normal left, RetryButton «ПОВТОРИТЬ» primary right, 16 su apart, both the same width =
  max(168 su, widest label + 48 su). Exactly one primary. The panel grows by 72 su; it still fits every canvas.
- ВР-VS5-SC20-03 (truth of the lobby button): «В ЛОББИ» never aborts the server match (card); README notes that the
  way back is SC-11 / SC-05. No hover, no focus ring, no cursor in SC-20.

Outputs of every package (in addition to the card deliverable):
- layout-geometry.json: per canvas the rectangles in su with the BindWidget names of the card's UE column:
  LoadingPanel, StageText, Spinner (SC-20: ErrorIcon), LeftCard, RightCard (each with Portrait, NameText, NickText),
  VersusText, BoardText, LobbyButton, RetryButton (SC-20), CaptionPanel.
- comparison/<card>-overlay-<res>-<scale>.png and -gray.png: outlines and labels only on plain card.navy (no frame,
  avatar or map pixels, ВР-VS4-01); every rectangle above with its name and x, y, w, h in su (labels at the frame or a
  legend keyed to the frame); the labels never overlap each other (measure it and record 0 in verification.json).
- verification.json: the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line as {passed, measured, expected, note}) plus text contrast per panel,
  icon and edge contrast (measured on the grey finals too), smallest text px at 720p, overlap, primary-button count per
  frame, and a check that every drawn value equals the input (heroes, nicknames, board). Do not repeat the per-file
  hashes of the hud-icons-v3 files (tree digest, count, changed files, icons used). manifest-sha256.json covers every
  package file except itself, every file in scraped-data/derived/<set>-codex/ (inputs/ included) and the inputs.
- Open and look at every final PNG before you finish a package (colour and grey, all four canvases) and record it in
  visual-review.json (path, sha256, what you checked). README.md in Russian, status «предложено», with the decisions
  above and a string-table delta.

Extra inputs (add them to source-hashes-before.json and the manifest of every package that uses them):
docs/unreal/contracts/hud/st-screens.csv; docs/unreal/contracts/hud/hud-style-tokens.json;
docs/game-design/visual/06-tasks/screens.csv (rows SC-19, SC-20, column "do"); AGENTS.md (section «Board scenes and
heroes», the board id); docs/game-design/decisions/2026-10-04-real-boards-only.md; art/imagegen/hud-skins-v1-codex/
(README.md, runtime-style.json, slice-margins.json, vector/); art/imagegen/sc01-screen-base-codex/ (README.md,
_tools/, manifest-sha256.json); art/imagegen/hud-icons-v3/_tools/draw_icons.py and the sizes/ files you paste;
scraped-data/derived/ue-media-v1/avatars/medusa.png and king-arthur.png; art/imagegen/portrait-crop-v1-codex/
(README.md, portrait-crops.json, vector/portrait-edge-160*, vector/portrait-underlay-160*); backend/prisma/seed.ts
(lines only); scraped-data/derived/<set>-codex/inputs/*.json (four files); for SC-20 also
art/imagegen/sc19-loading-codex/ (README.md, _tools/, manifest-sha256.json).
```
