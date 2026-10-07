# CX-34 - Codex series task: GAMEOVER and ABORTED mockups SC-34 ... SC-38

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It orders the five card tasks built by `prompt_build.py`, names the real data Claude found and placed before the run
and the decisions Claude took for them (ВР-VS5-SC34-01…09, ВР-VS5-SC35-01…02, ВР-VS5-SC36-01…03,
ВР-VS5-SC37-01…05, ВР-VS5-SC38-01…04, by delegation, 2026-10-07).

| field | value |
|---|---|
| id | CX-34 (cards SC-34, SC-35, SC-36, SC-37, SC-38) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc34-gameover-victory-codex/`, `sc35-gameover-defeat-codex/`, `sc36-gameover-board-codex/`, `sc37-gameover-again-codex/`, `sc38-aborted-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| data | run I traces (in git, 1v1 Marmoreal and Sarpedon original), run F vs-ai trace (in git, VS_AI Marmoreal original), two game rows read read-only from the reference DB, placed by Claude in `scraped-data/derived/<set>-codex/inputs/` (outside git) |
| image generations allowed | 0 |

## Task

```text
Series CX-34: five mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-34.codex.md -> art/imagegen/sc34-gameover-victory-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-35.codex.md -> art/imagegen/sc35-gameover-defeat-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-36.codex.md -> art/imagegen/sc36-gameover-board-codex/
4. docs/game-design/visual/06-tasks/prompts/SC-37.codex.md -> art/imagegen/sc37-gameover-again-codex/
5. docs/game-design/visual/06-tasks/prompts/SC-38.codex.md -> art/imagegen/sc38-aborted-codex/
Do each task completely (package contract, inputs, layout rules, deliverable, acceptance) before the next. The task
text is the "Task" section of each file; its header tables are provenance only. Each package writes only into its
own folder and its own scraped-data/derived/<set>-codex/ folder (never change the inputs/ subfolder Claude placed
there). No git, no MCP, no network, no image generation. Under unreal/ you may only READ
unreal/Unmatched/Source/Unmatched/S08/S08FlowGameModeResult.cpp (named in the cards); never write, build or start
anything there. Where this file and a card text differ, this file wins (the card texts were written before the data
below was checked). The sha256 prefixes inside the card texts are from the day the cards were written; record the
real current sha256 of every input.

Script chain: SC-34 writes the whole GAMEOVER screen in _tools/sc34_gameover_victory.py with parameters for the
background (marmoreal | sarpedon), the scene grade (victory | defeat | none), the veil (on | off), the outcome word
(key, colour, type role), the headline, the reason, the turn line, the left and right sides (hero name, portrait
source, role, HP, winner | defeated), the button list (label key, key chip, normal | primary | busy) and the board
strip (SC-36). SC-35, SC-36 and SC-37 copy the FINAL sc34_gameover_victory.py of package 1 unchanged and extend it
only in their own module. SC-38 is a separate modal: it copies only the libraries. Every package copies
screen_mockup_base.py (d970f881...) and art/imagegen/hud-icons-v3/_tools/draw_icons.py (as
draw_icons_v3_snapshot.py) unchanged. Record each copy's sha256 (copy-provenance.json).

Common notes (all five packages):
- SC-01 library: veil, panels, buttons, key chips with the accepted HB-08 skins; skins folder
  art/imagegen/hud-skins-v1-codex/vector/ (read README.md, runtime-style.json, slice-margins.json; T_Skin_KeyChip is
  the key chip, T_Skin_Btn_Disabled the disabled body), tokens docs/unreal/contracts/hud/hud-style-tokens.json
  (type.display 48, type.banner 36, type.title 28, type.heading 24, type.button 20, type.body 16, type.caption 14,
  type.tag 14). Do not redraw those elements. Read for patterns (read only, record sha256 if you reuse code):
  art/imagegen/sc01-screen-base-codex/README.md, art/imagegen/sc19-loading-codex/ (portrait discs of CP-07, the
  «против» column, overlays with BindWidget names and x/y/w/h su), art/imagegen/sc31-reconnect-auto-codex/ (a scene
  colour operation under a veil, the 48 su icon slot), art/imagegen/hud-actions-v1-codex/ (the key chip geometry).
- Icons: paste art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose size equals size_su x px-per-su exactly; when
  that size does not exist render it with render(name, px) of your unchanged draw_icons_v3_snapshot.py (never call
  main()); never NEAREST-upscale; never use the library's spinner(). Used here: resource-hp-fallen 24 su,
  resource-connection-lost 48 su (SC-38), loader-spinner 24 su (SC-37 busy; static step 0, rotation is motion).
- Portraits (CP-07, art/imagegen/portrait-crop-v1-codex/README.md: GAMEOVER = 120 su): source PNGs
  scraped-data/derived/ue-media-v1/avatars/medusa.png and king-arthur.png (CP-01 conversions of the Hero.avatarUrl
  WebP), circle from art/imagegen/portrait-crop-v1-codex/portrait-crops.json (keys medusa, king-arthur),
  portrait-underlay-120 and portrait-edge-120 x1/x2 from that package's vector/ (select and resample like the
  library's skin()). No team ring, no team colour (02 section 2.3). Every mockup with a portrait or the board frame
  stays in scraped-data/derived/; overlays never contain avatar or frame pixels (ВР-VS4-01).
- Strings, RU column «ru» of docs/unreal/contracts/hud/st-screens.csv, cite each in manifest facts (file + key):
  screens.result.victory «ПОБЕДА», .defeat «ПОРАЖЕНИЕ», .draw «ВЗАИМНОЕ УНИЧТОЖЕНИЕ», .unknown «ИСХОД НЕДОСТУПЕН»
  (named only), .wins «{hero} побеждает», .reason.hp «{hero}: HP достигли 0», .turn.time «Ход {n} · {time}», .you
  «Вы», .opponent «Соперник», .winner «Победитель», .defeated «Повержен», .view.board «Посмотреть доску»,
  .view.results «К итогам», .lobby «В лобби», .again «Сыграть ещё»; screens.loading.versus «против»;
  screens.aborted.title «Партия прервана», .who «Игрок {player} покинул партию», .turn «Ход {n}», .lobby «В лобби».
  The HP part of a caption is «HP {hp}/{max}» (04 section 1.10 caption row; hud.panel.hp «{hp}/{max}» of
  docs/unreal/contracts/hud/st-hud.csv). Proposed by the cards, not in the table yet (list them in README as a
  string-table delta, key + RU + EN): screens.result.board.turn «Ход {n} · {outcome}» / "Turn {n} · {outcome}"
  (SC-36), screens.result.again.busy «Создаём партию…» / "Creating a game…" (SC-37), screens.aborted.who.unknown
  «Соперник покинул партию» / "The opponent left the game" (SC-38). Buttons are upper case (type.button). No
  «уточнить» on any mockup: every value is resolved or, where no real value exists, the element is left out and the
  omission is listed in README (ВР-VS5-SC34-07).
- ВР-VS5-SC34-01 (hero names from data, ВР-VS2-02): hero names are Hero.name / Hero.nameRu as the client shows them:
  «Medusa», «King Arthur», «T. Rex» (all three nameRu equal the EN name in the reference DB; the RU forms «Медуза»,
  «Король Артур» of docs/game-design/05-content-matrix.csv wait for a content task: list them in README, do not draw
  them). The headline is screens.result.wins in upper case, as 04 section 6.2 budgets it («КОРОЛЬ АРТУР ПОБЕЖДАЕТ»):
  «MEDUSA ПОБЕЖДАЕТ» - by the winning hero, not by the fighter who dealt the last blow (SD-45). The reason keeps the
  table's case: «King Arthur: HP достигли 0». The time is m:ss of the trace duration in seconds (27 -> «0:27»).
- ВР-VS5-SC34-02 (data of SC-34, viewer = host ProGamer, Medusa): docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/
  marmoreal/combat-20261005-235827/combat-client-host.trace.txt line 4190 «RESULT summary outcome=VICTORY
  winnerHero=Medusa loserHero=King_Arthur reason=hp0 turn=11 duration=27 left=viewer»; line 2015 «HUD-HEART side=own
  hero=f-0-hero hp=11/16» and line 3491 (plate Medusa hp=11/16); lines 4154 / 4180 (King Arthur hp=0/18, fallen
  cross). The host result frame named in the card confirms 11/16 and 0/18 (read it; it stays an input, never copied
  into the package). So: «ПОБЕДА», «MEDUSA ПОБЕЖДАЕТ», «King Arthur: HP достигли 0», «Ход 11 · 0:27»; left Medusa
  «Вы · HP 11/16 · Победитель»; right King Arthur «Соперник · HP 0/18 · Повержен».
- ВР-VS5-SC34-03 (modal, 04 section 1.10): ResultModal 760x580 su (class S 680x560), centred, library panel kind
  "modal" (panel.bg 1.0, panel.edge, radius 8), everything centred on the modal's vertical axis. Class L, tops in su
  from the modal top: OutcomeText y 32 (type.display; victory turn.flash.yellow, defeat state.error, draw
  text.primary); HeadlineText y 96 (type.title, card.cream); ReasonText y 140 (type.body, text.primary); TurnText y
  168 (type.caption, text.secondary, tabular digits); portrait band y 210...410: LeftPortrait and RightPortrait 120 su
  discs, centres 180 su left and right of the axis, VersusText «против» (type.heading, text.secondary) on the axis at
  the disc centre line; under each disc 12 su gap, NameText (type.heading, text.primary), 4 su, CaptionText
  (type.caption): «<role> · HP <hp>/<max> · » in text.secondary followed by «Победитель» in turn.flash.yellow, or
  «Повержен» in text.secondary followed by 6 su and resource-hp-fallen 24 su; ButtonRow top y 500 (48 su). Class S:
  same order, ButtonRow top y 480 and the portrait band 20 su shorter (disc centres 160 su from the axis). Measure:
  every text inside the modal with >= 16 su side padding, nothing overlapping.
- ВР-VS5-SC34-04 (loser portrait, 02 section 6.4): the loser's whole disc (avatar, underlay, edge) at saturation 0
  and opacity 0.6 over the modal body; no red anywhere on it.
- ВР-VS5-SC34-05 (buttons and key chips): ButtonRow centred, 16 su gaps, left to right: ViewBoardButton
  «ПОСМОТРЕТЬ ДОСКУ» (normal), [SC-37 only: AgainButton «СЫГРАТЬ ЕЩЁ» (normal)], LobbyButton «В ЛОББИ» (primary).
  Keys are chips, never text (ВР-H09, 04 section 2.11): a KeyChip (T_Skin_KeyChip, type.tag, text.primary; 20x20 su,
  wider for «Enter»: text + 2 x 4 su) inside the button, 8 su right of the label, vertically centred: «V» on
  ViewBoardButton, «Enter» on LobbyButton. Button width = max(168 su, label + chip + 48 su). Exactly one primary. In
  Auto mode the client shows the chips only while no match was completed (CompletedMatches = 0, HB-43): the mockups
  show the chips (mode «Вкл»); write that in README.
- ВР-VS5-SC34-06 (scene grade, CUE-016 / FX-34, docs/unreal/contracts/cue-dispatcher/cue-table.json postprocess):
  approximate the engine grade on the K1 frame before the veil: victory = white balance from 6500 K to 5900 K
  (per-channel gains of a standard blackbody Kelvin-to-sRGB approximation, ratio target / base, renormalised so the
  Rec.709 luma of mid grey is unchanged) + vignette; defeat = 6500 K -> 7300 K, then saturation x 0.8 (out = L + 0.8
  x (rgb - L), Rec.709 luma) + vignette. Vignette add 0.25: multiply by 1 - 0.25 x r^2, r = distance from the canvas
  centre / half-diagonal. Then panel.veil 0.6 (no blur). Write in README that this approximates S08CuePostProcess
  and that the grade holds until the player leaves the match (it stays in SC-36). Record the gains per frame.
- ВР-VS5-SC34-07 (draw frame of SC-34): no real drawn match exists, so its numbers are not drawn (never invented,
  never «уточнить»): OutcomeText «ВЗАИМНОЕ УНИЧТОЖЕНИЕ» in type.banner (04 section 6.2: one step down, it must fit
  the modal width minus 2 x 24 su; measure), text.primary; no HeadlineText (no winner), no ReasonText, no TurnText;
  both portraits of the run I pair (left Medusa «Вы», right King Arthur «Соперник») both in the loser look
  (ВР-VS5-SC34-04) with captions «Вы · Повержен» and «Соперник · Повержен» + fallen heart, no HP; buttons as in
  victory. Neutral scene: no grade (CUE-016 has no draw profile), veil 0.6. README: «кадр-раскладка состояния draw:
  настоящей ничьей нет; числа и строки причины не рисуются».
- ВР-VS5-SC34-08 (input and motion): no hover, no focus ring, no cursor; the modal is drawn at its final state
  (opacity 1, 400 ms entry is motion). The veil and ResultModal are modal layers: exempt from the figure and space
  overlap rule (04 section 1.6), kind "modal"; use the masks of art/imagegen/hud-composition-v1-codex/masks.json for
  the report. The K1 frames have no HUD; in the game the frozen HUD lies under the veil: note it, do not draw it. The
  bench name plates inside the K1 frames are artifacts of the given background, not mockup strings; the K1 frame also
  still shows the fallen hero standing - note it as a background artifact.
- ВР-VS5-SC34-09 (overlays): comparison/<card>-overlay-<res>-<scale>.png and -gray.png on plain card.navy, outlines
  and labels only (no frame or avatar pixels, ВР-VS4-01): every element with its BindWidget name (proposals for
  UUmScreenGameOver / UUmScreenAborted, UE part VS-7) and x, y, w, h in su - ResultModal, OutcomeText, HeadlineText,
  ReasonText, TurnText, LeftPortrait, RightPortrait, VersusText, LeftName, RightName, LeftCaption, RightCaption,
  ButtonRow, ViewBoardButton, AgainButton, LobbyButton, KeyChip_V, KeyChip_Enter, BoardStrip, StripText,
  ResultsButton, AbortedModal, Icon, TitleText, WhoText, TurnText. Labels never overlap each other (measure, record
  0).
- ВР-VS5-SC35-01 (data of SC-35, viewer = joiner Veteran, King Arthur): docs/game-design/evidence/DE-FOOTAGE/
  2026-10-05/I/sarpedon/combat-20261005-235948/combat-client-joiner.trace.txt line 2456 «RESULT summary
  outcome=DEFEAT winnerHero=Medusa loserHero=King_Arthur reason=hp0 turn=5 duration=13 left=opponent»; line 982
  «HUD-HEART side=opp hero=f-0-hero hp=14/16»; lines 2420 / 2446 (own King Arthur hp=0/18, fallen cross); the joiner
  result frame confirms. So: «ПОРАЖЕНИЕ» (state.error), «MEDUSA ПОБЕЖДАЕТ»,
  «King Arthur: HP достигли 0», «Ход 5 · 0:13»; left (winner) Medusa «Соперник · HP 14/16 · Победитель», right King
  Arthur «Вы · HP 0/18 · Повержен» in the loser look. Sarpedon P10 K1 frame, defeat grade, veil 0.6.
- ВР-VS5-SC35-02: red only on «ПОРАЖЕНИЕ» (type.display 48 su >= 24 su); measure red pixels elsewhere = 0 (the red
  of the fallen heart's cross, if the icon has one, is an icon sign, report it separately).
- ВР-VS5-SC36-01 (board view, SC-36, Marmoreal, data of SC-34): the K1 frame with the victory grade (it holds), no
  veil, no modal. BoardStrip 520x56 su at the bottom centre, bottom edge at the safe margin (24 su L, 16 su S),
  library panel kind with panel.bg 0.92 (in-match panel), panel.edge, radius 6, padding 8 su: StripText «ХОД 11 ·
  ПОБЕДА» (screens.result.board.turn with screens.result.victory, type.button, text.primary) left; ResultsButton
  «К ИТОГАМ» (normal, 40 su high, KeyChip «V») and LobbyButton «В ЛОББИ» (primary, 40 su high, KeyChip «Enter») right,
  8 su apart. If the three do not fit 520 su, drop the KeyChips first (record it), never shrink the type.
- ВР-VS5-SC36-02: measure the BoardStrip against the Marmoreal FIELD rectangle of 04 section 1.6 (1080p px (410,
  255)-(1440, 850), x 2/3 at 720p) and against the space and figure masks: 0 px^2 on every canvas (the strip is not
  modal). The fallen hero's crossed heart on the HUD portrait is not drawn (the K1 frame has no HUD; note it).
- ВР-VS5-SC36-03: returning to the results has no entry animation (motion, not drawn).
- ВР-VS5-SC37-01 (VS_AI data, placed by Claude): scraped-data/derived/sc37-gameover-again-codex/inputs/
  vsai-result.json (+ provenance.json): run F vs-ai, 2026-10-05, Marmoreal original, packaged client; trace
  docs/game-design/evidence/DE-FOOTAGE/2026-10-04/F/live/vs-ai/vsai-20261005-165024/vsai-client.trace.txt line 5183
  «RESULT summary outcome=VICTORY winnerHero=Medusa loserHero=T._Rex reason=hp0 turn=19 duration=33 left=viewer»;
  Medusa HP 14/16 (lines 2070, 4313), T. Rex HP 0/27 (line 5156); game row FINISHED, mode VS_AI, opponent «AI Bot»
  (backend/prisma/seed-ai.ts line 24), endedAt - startedAt = 33.0 s. The run F result frame
  docs/game-design/evidence/DE-FOOTAGE/2026-10-04/F/live/vs-ai/vsai-20261005-165024/human/s09-result-screen.jpg
  confirms «Turn 19 · 0:33», «HP 14 / 16», «HP 0 / 27» (read it; an input, never copied). Never reuse run I numbers.
  So: «ПОБЕДА», «MEDUSA ПОБЕЖДАЕТ», «T. Rex: HP достигли 0», «Ход 19 · 0:33»; left Medusa «Вы · HP 14/16 ·
  Победитель»; right T. Rex «AI Bot · HP 0/27 · Повержен» (in VS_AI the opponent's role word is the bot's nickname
  from data, as the card names it). Marmoreal P7 K1 frame, victory grade, veil 0.6.
- ВР-VS5-SC37-02 (T. Rex portrait): CP-07 has no T. Rex crop. Convert scraped-data/images/heroes/avatars/
  9z9iaYFxdQpstwDftty0r.webp (768x768, the Hero.avatarUrl file of T. Rex) with Pillow, unretouched, to
  scraped-data/derived/sc37-gameover-again-codex/avatars/t-rex.png and crop it with the proposal cx 0.58, cy 0.33,
  d 0.64 (Claude's reading of the avatar: the eye at about (0.43, 0.19) must lie in the central 60 % of the disc; if
  your measurement shows it does not, move cx / cy by at most 0.05 and record the final values). List the crop in
  README as a CP-07 delta. The bot is the loser: loser look.
- ВР-VS5-SC37-03 (buttons): ViewBoardButton «ПОСМОТРЕТЬ ДОСКУ» + V, AgainButton «СЫГРАТЬ ЕЩЁ» (normal, no chip: no
  key is assigned), LobbyButton «В ЛОББИ» + Enter (primary). All three in one row of the modal in both classes; if the
  row is wider than the modal minus 2 x 24 su, reduce the gaps to 8 su, then drop the chips (record it); never
  shrink the type, never wrap a label.
- ВР-VS5-SC37-04 (again-busy): the same frame with AgainButton busy: normal body (no hover), loader-spinner 24 su +
  8 su + «СОЗДАЁМ ПАРТИЮ…» (screens.result.again.busy); the button keeps the width of the wider of its two labels in
  both frames, so nothing moves. The other buttons are unchanged. again.error (a toast) is not drawn: no real error
  exists; name it in README.
- ВР-VS5-SC37-05: no ROOM step, no 1v1 button (the again button exists only in VS_AI: the SC-34 frame has none).
- ВР-VS5-SC38-01 (ABORTED data, placed by Claude): scraped-data/derived/sc38-aborted-codex/inputs/aborted-game.json
  (+ provenance.json): a real ONE_V_ONE match on Marmoreal original (board c121b47f8d6eb28daccb76d05), host ProGamer
  (Medusa, seat 0), opponent Veteran (King Arthur, seat 1), status ABORTED, GAME_ABORTED by Veteran with reason
  player_left (leaveGame of an IN_PROGRESS match calls abortGame(..., 'player_left'),
  backend/src/games/game.service.ts), turnCount 1. The viewer is ProGamer. The card asked for a fresh stand S09
  capture; this existing row is the same scenario and needed no new match (README). Nicknames are confirmed by
  backend/prisma/seed.ts (lines only, never copy the file).
- ВР-VS5-SC38-02 (modal, 04 section 1.11): AbortedModal 640x360 su, centred, library panel kind "modal", one centred
  column, vertically centred in the modal: Icon resource-connection-lost 48 su; 16 su; TitleText «Партия прервана»
  (type.title, text.primary); 12 su; WhoText (type.body, text.primary); 8 su; TurnText «Ход 1» (type.caption,
  text.secondary); 24 su; LobbyButton «В ЛОББИ» (primary, centred, width max(168 su, label + 48 su), KeyChip «Enter»
  as in ВР-VS5-SC34-05). Marmoreal P7 K1 frame, veil 0.6, no grade (no CUE-016), no victory or defeat words or
  colours; the X of the icon is the only red.
- ВР-VS5-SC38-03 (frames): shown = WhoText «Игрок Veteran покинул партию» (screens.aborted.who with the nickname
  from aborted-game.json); shown-noname = «Соперник покинул партию» (screens.aborted.who.unknown, proposed).
- ВР-VS5-SC38-04: no 20x20 grid frame, no Cobble frame; only the Marmoreal P7 K1 frame.

Canvases: every frame on the four library canvases 1080p/720p x 100/150 %, colour and grey (Rec.709), the same su
everywhere. Frames: SC-34 victory, draw; SC-35 defeat; SC-36 board; SC-37 again, again-busy; SC-38 shown,
shown-noname.

Outputs of every package (in addition to the card deliverable):
- layout-geometry.json: per canvas and frame the rectangles in su with the BindWidget names above.
- verification.json: the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line as {passed, measured, expected, note}) plus text contrast per panel
  (every text against its own background; «Победитель» yellow and the outcome word against panel.bg), icon and edge
  contrast (measured on the grey finals too), smallest text px at 720p, overlap (modal layers separately, the SC-36
  strip as a persistent layer), primary-button count per frame, red-pixel report (state.error-like pixels outside icon
  signs: SC-34 victory 0, SC-35 only the title, SC-38 0; the red cross of resource-hp-fallen and the red X of
  resource-connection-lost are icon signs, report their pixel counts separately), the grade gains and vignette per frame, and a check that every drawn value equals the
  input (heroes, HP, turn, time, nicknames). Do not repeat the per-file hashes of the hud-icons-v3 files (tree digest,
  count, changed files, icons used). manifest-sha256.json covers every package file except itself, every file in
  scraped-data/derived/<set>-codex/ (inputs/ included) and the inputs.
- Open and look at every final PNG before you finish a package (colour and grey, all four canvases) and record it in
  visual-review.json (path, sha256, what you checked). README.md in Russian, status «предложено», with the decisions
  above and the string-table delta.

Extra inputs (add them to source-hashes-before.json and the manifest of every package that uses them):
docs/unreal/contracts/hud/st-screens.csv; docs/unreal/contracts/hud/st-hud.csv;
docs/unreal/contracts/hud/hud-style-tokens.json; docs/unreal/contracts/cue-dispatcher/cue-table.json;
docs/game-design/visual/06-tasks/screens.csv (rows SC-34...SC-38, column "do"); AGENTS.md (section «Board scenes and
heroes»); docs/game-design/decisions/2026-10-04-real-boards-only.md; art/imagegen/hud-skins-v1-codex/ (README.md,
runtime-style.json, slice-margins.json, vector/); art/imagegen/sc01-screen-base-codex/ (README.md, _tools/,
manifest-sha256.json); art/imagegen/hud-icons-v3/_tools/draw_icons.py and the sizes/ files you paste;
art/imagegen/hud-composition-v1-codex/masks.json; art/imagegen/portrait-crop-v1-codex/ (README.md,
portrait-crops.json, vector/portrait-edge-120*, vector/portrait-underlay-120*); scraped-data/derived/ue-media-v1/
avatars/medusa.png and king-arthur.png; the run I and run F traces and result frames named above; for SC-37
scraped-data/images/heroes/avatars/9z9iaYFxdQpstwDftty0r.webp and inputs/*.json; for SC-38 inputs/*.json,
backend/src/games/game.service.ts and backend/prisma/seed.ts (lines only); for SC-35 ... SC-37 also
art/imagegen/sc34-gameover-victory-codex/ (README.md, _tools/, manifest-sha256.json).
```
