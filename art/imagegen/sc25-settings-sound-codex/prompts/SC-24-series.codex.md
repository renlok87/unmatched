# CX-32 - Codex series task: PAUSE and settings mockups SC-24 ... SC-30

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It orders the seven card tasks built by `prompt_build.py`, names the real data Claude found before the run and the
decisions Claude took for them (ВР-VS5-SC24-01…12, ВР-VS5-SC25-01…02, ВР-VS5-SC26-01…03, ВР-VS5-SC27-01…02,
ВР-VS5-SC28-01, ВР-VS5-SC29-01…02, ВР-VS5-SC30-01, by delegation, 2026-10-07).

| field | value |
|---|---|
| id | CX-32 (cards SC-24, SC-25, SC-26, SC-27, SC-28, SC-29, SC-30) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc24-pause-codex/`, `sc25-settings-sound-codex/`, `sc26-settings-language-codex/`, `sc27-settings-scale-codex/`, `sc28-settings-game-codex/`, `sc29-settings-hints-codex/`, `sc30-settings-graphics-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| data | the client settings code (S08UserSettings.h), the string tables, why-reasons.json, game-state.model.ts, render-reference.json; no match data is drawn |
| image generations allowed | 0 |

## Task

```text
Series CX-32: seven mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-24.codex.md -> art/imagegen/sc24-pause-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-25.codex.md -> art/imagegen/sc25-settings-sound-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-26.codex.md -> art/imagegen/sc26-settings-language-codex/
4. docs/game-design/visual/06-tasks/prompts/SC-27.codex.md -> art/imagegen/sc27-settings-scale-codex/
5. docs/game-design/visual/06-tasks/prompts/SC-28.codex.md -> art/imagegen/sc28-settings-game-codex/
6. docs/game-design/visual/06-tasks/prompts/SC-29.codex.md -> art/imagegen/sc29-settings-hints-codex/
7. docs/game-design/visual/06-tasks/prompts/SC-30.codex.md -> art/imagegen/sc30-settings-graphics-codex/
Do each task completely (package contract, inputs, layout rules, deliverable, acceptance) before the next. The task
text is the "Task" section of each file; its header tables are provenance only. Each package writes only into its
own folder and its own scraped-data/derived/<set>-codex/ folder. No git, no MCP, no network, no image generation.
Under unreal/ you may only READ the two files named below (S08UserSettings.h, S08FlowGameMode.cpp is not needed);
never write, build or start anything there. Where this file and a card text differ, this file wins (the card texts
were written before the data below was checked). The sha256 prefixes written inside the card texts are from the
day the cards were written; record the real current sha256 of every input.

Script chain: SC-24 writes the whole PAUSE modal in _tools/sc24_pause.py with parameters for the background
(marmoreal | sarpedon), the open tab (sound | interface | game | graphics), the header lines, the setting rows (a
row list with kinds slider, check, chips, note, sample), the footer buttons, the confirm dialog, the language
(ru | en | pseudo) and the viewport (any Viewport(width, height, dpi, ui), not only the library presets). SC-25 ...
SC-30 copy the FINAL sc24_pause.py of package 1 unchanged and extend it only in their own module. Every package
copies screen_mockup_base.py (d970f881...) and art/imagegen/hud-icons-v3/_tools/draw_icons.py (as
draw_icons_v3_snapshot.py) unchanged. Record each copy's sha256 (copy-provenance.json).

Common notes (all seven packages):
- SC-01 library: veil, panels, buttons, chips, check boxes, key chips with the accepted HB-08 skins; skins folder
  art/imagegen/hud-skins-v1-codex/vector/ (read README.md, runtime-style.json, slice-margins.json; T_Skin_SliderTrack
  and T_Skin_SliderThumb are the slider, T_Skin_Check_On / _Off the check box, T_Skin_Btn_Selected the selected chip
  and the selected tab, T_Skin_KeyChip the key chip), tokens docs/unreal/contracts/hud/hud-style-tokens.json. Do not
  redraw those elements; add only what the library lacks (slider, scroll indicator) in your module, built from the
  same skins and tokens. Read for patterns (read only, record sha256 if you reuse code):
  art/imagegen/sc01-screen-base-codex/README.md, art/imagegen/sc19-loading-codex/ (the ВР-75 caption panel, overlays
  with BindWidget names and x/y/w/h su), art/imagegen/hud-actions-v1-codex/ (README.md, facts.json, _tools/: the
  disc button and the key chip of HB-42, needed by SC-29).
- Icons: paste art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose size equals size_su x px-per-su exactly; when
  that size does not exist render it with render(name, px) of your unchanged draw_icons_v3_snapshot.py (never call
  main()); never NEAREST-upscale; never use the library's spinner(). Used here: badge-refuse 24 su (the X sign of
  «Покинуть партию»: IC-40 is accepted, so it replaces the card's placeholder marker-x-stamp, ВР-VS5-SC24-05) and
  action-end-turn 48 su / 40 su (SC-29 sample).
- Strings: cite each drawn string in manifest facts (file + key + column). docs/unreal/contracts/hud/st-screens.csv
  (RU column «ru»; EN column «SourceString» only in SC-26): screens.pause.title «Пауза», .continue «Продолжить»,
  .leave «Покинуть партию», .leave.confirm «Партия прервётся для обоих игроков», .running «Партия продолжается»,
  .defense.left «До конца окна защиты {n} с»; settings.tab.sound / .interface / .game / .graphics; settings.sound.*
  (master «Общая громкость», mute «Без звука», music, effects, interface, voices, ambience «Окружение», subtitles,
  describe «Описывать звуки»); settings.interface.language (+ .ru «Русский», .en «English»), .scale «Масштаб
  интерфейса», .rule_hints, .key_hints (+ .auto «Авто», .on «Вкл», .off «Выкл»); settings.game.anim_speed (+ .none
  «Нет», .fast «Быстро», .normal «Обычно», .slow «Медленно»), .reduced_motion «Сокращённые анимации»;
  settings.graphics.quality (+ .high «Высокое», .medium «Среднее», .low «Низкое»); settings.value.on «вкл», .off
  «выкл», .percent «{n} %»; common.confirm.yes «Да», common.confirm.cancel «Отмена»; screens.room.leave «Выйти из
  комнаты» (named only in README: no ROOM frame is drawn). docs/unreal/contracts/hud/why-reasons.json: why.syncing
  «Синхронизация…». docs/unreal/contracts/hud/st-hud.csv: hud.action.end_turn «КОНЕЦ ХОДА», hud.key.end_turn «E»
  (SC-29). settings.game.shake «Тряска» exists in the table but is NOT drawn (ВР-SC06: no shake row; 02, rule D-10:
  the camera never shakes; S08UserSettings.h still stores bScreenShake - note it in README of SC-28 as a client
  field without a row). Buttons are upper case (type.button). Strings the cards propose that are not in the tables
  (list each in README as a string-table delta, key + RU + EN): settings.interface.scale.range «{min}–{max} %»
  (SC-27), settings.interface.key_hints.note «Авто — только в первой партии» / "Auto - first match only" (SC-29),
  settings.graphics.note «Масштаб экрана 100 % и лимит 60 кадров/с не меняются» / "Screen percentage 100 % and the
  60 fps cap stay unchanged" (SC-30). No «уточнить» on any mockup: every value below is resolved.
- Real values (cite file and line in facts): unreal/Unmatched/Source/Unmatched/S08/S08UserSettings.h (read only):
  MasterVolume 100, bMasterMuted false, MusicVolume 60, SfxVolume 80, UiVolume 80, VoVolume 80, AmbienceVolume 60,
  bAmbienceMuted false, bSubtitles true, bDescribeSounds false, AnimSpeed "normal", bReducedMotion false, bRuleHints
  true, KeyHintsMode "auto", UiScalePercent 100 with ClampUiScalePercent 75..150 in steps of 5 and the comment that
  it is raised to 100 % while the window's short side is under 1080 (HB-09, 04 §3.6); quality High = sg.* 2
  (docs/art-pipeline/render-reference.json requires screenPct 100.0; sg.* 2 lines 18-27); the 60 fps cap from
  AGENTS.md section «Unreal GPU load» (FrameRateLimit=60; do not open unreal/Unmatched/Config);
  DEFENSE_TIMEOUT_SECONDS = 30 (backend/src/game-engine/models/game-state.model.ts line 19). The language default is
  RU (04 §1.8 table, UI-ACC-010).
- ВР-VS5-SC24-01 (modal): PauseModal 720 su wide, library panel kind "modal" (panel.bg 1.0, panel.edge, radius 8),
  padding 16 su, centred on the canvas. Header: TitleText «Пауза» (type.title, text.primary); in game frames below it
  StatusText «Партия продолжается» (type.body, text.secondary); in game-defense also DefenseText «До конца окна
  защиты 30 с» (type.body, text.primary). Divider (panel.divider, 1 su) 16 su below the header. Body: TabList 160 su
  wide (four tabs 160x48 su, 8 su apart, order Звук, Интерфейс, Игра, Графика; the open tab uses the selected skin
  with card.glyph text, the others the normal button skin; tab labels in type.button case as the library draws
  buttons), 8 su gap, RowsPanel 520 su wide (16 + 160 + 8 + 520 + 16 = 720). Divider 16 su above the footer.
  Footer row 48 su: LeaveButton (normal, badge-refuse 24 su left of the label «ПОКИНУТЬ ПАРТИЮ», label text.primary)
  left, ContinueButton «ПРОДОЛЖИТЬ» (primary) right; each width max(168 su, content + 48 su). Exactly one primary in
  the modal. Height = content, never above 800 su.
- ВР-VS5-SC24-02 (rows, UUmSettingRow): rows 520 su wide, a panel.divider line between rows. Slider row 48 su: Label
  (type.body, text.primary) at x 0, Slider track 200 su long at x 148 (T_Skin_SliderTrack, fill card.cream from the
  left to the value, T_Skin_SliderThumb 16 su centred on the value), Value «{n} %» (type.body, text.primary,
  right-aligned in a 56 su box after the track, tabular digits), then optional Mute: check box 24 su + 8 su + «Без
  звука» (type.caption, text.secondary). Check row 48 su: Label, check box 24 su at x 148 + value word «вкл» / «выкл»
  (type.body, text.secondary) 8 su after it (the tick shape carries the state, the word repeats it). Chips row: the
  Label on its own line, then the chips line 8 su below (chips 32 su high, width = text + 2 x 12 su, 8 su apart,
  selected = selected skin with card.glyph text); optional Note line (type.caption, text.secondary) 8 su below. Row
  padding 8 su top and bottom. Measure every label: nothing may be clipped or touch the next element.
- ВР-VS5-SC24-03 (scroll): when the modal would be taller than canvas height - 2 x margin (24 su L, 16 su S), the
  RowsPanel becomes a scroll view: the header and the footer stay, the rows are clipped at the RowsPanel bottom and a
  ScrollBar 4 su wide sits 4 su inside the RowsPanel's right edge (track panel.bg.inset, thumb card.cream, thumb
  length = visible / total, at the top). Record visible and total row height per frame. At 720p 150 % (1138x640 su)
  the footer buttons must be fully visible.
- ВР-VS5-SC24-04 (frames of SC-24, Marmoreal P7 K1 frame under panel.veil 0.6, tab Звук open with the SC-25 rows):
  game (StatusText), game-defense (StatusText + DefenseText with n = 30), menu (opened from LOBBY: no StatusText, no
  LeaveButton, ContinueButton alone at the right; the ВР-75 caption panel «фон-заглушка: в игре фигур нет (ВР-75)»
  as in SC-19, bottom-left inside the safe area; in the game this modal lies over the LOBBY screen SC-08 - note it in
  README), confirm (the game frame, then the SC-01 draw_base_modal() on top: its own veil 0.6 over the pause modal and
  the 640x360 dialog «Покинуть партию» / «Партия прервётся для обоих игроков» / «ОТМЕНА» / «ДА» - the accepted SC-01
  dialog, not redrawn), syncing (extra fifth frame: the game frame with LeaveButton in the disabled skin and the
  reason «Синхронизация…» (why.syncing, type.caption, text.secondary) directly under it, 4 su gap; ContinueButton
  stays primary).
- ВР-VS5-SC24-05: the X of «Покинуть партию» is badge-refuse 24 su (accepted IC-40, red X on a navy plaque); the only
  red in the modal; no red text.
- ВР-VS5-SC24-06 (input): no hover, no focus ring, no cursor in any frame of the series (static keyboard-free views).
- ВР-VS5-SC24-07 (layers): the veil, PauseModal, the confirm dialog and the caption panel are modal / screen layers:
  exempt from the figure and space overlap rule (04 section 1.6), reported as kind "modal" (caption: "screen");
  persistent match panels: none, 0 px^2. Use the Marmoreal / Sarpedon space and figure masks of
  art/imagegen/hud-composition-v1-codex/masks.json for the report.
- ВР-VS5-SC24-08 (backgrounds): Marmoreal P7 K1 for SC-24, SC-25, SC-27, SC-29; Sarpedon P10 K1 for SC-26, SC-28,
  SC-30 (both real boards appear in the family). The K1 frames have no HUD; in the game the frozen HUD lies under the
  veil: write it in README, do not draw it. The bench name plates inside the K1 frames are artifacts of the given
  background, not mockup strings.
- ВР-VS5-SC24-09 (canvases): every frame on the four library canvases 1080p/720p x 100/150 % unless a card below
  says otherwise; the same su everywhere; colour and grey (Rec.709) for every final.
- ВР-VS5-SC24-10 (overlays): comparison/<card>-overlay-<res>-<scale>.png and -gray.png on plain card.navy, outlines
  and labels only (no frame pixels, ВР-VS4-01): every element with its BindWidget name and x, y, w, h in su -
  PauseModal, TitleText, StatusText, DefenseText, TabList (TabSound, TabInterface, TabGame, TabGraphics), RowsPanel,
  ScrollBar, Row_<setting key> (Label, Slider, Value, Mute, Check, Chips, Note), LeaveButton, LeaveWhy,
  ContinueButton, ConfirmDialog (Title, Body, CancelButton, YesButton), CaptionPanel, KeyHintSample (SC-29). Labels
  never overlap each other (measure, record 0); one overlay per canvas per frame kind is enough when frames share the
  geometry (say which).
- ВР-VS5-SC24-11 (no audio drawing): the sound hooks (UI-PANEL-OPEN, UI-SLIDER-TICK, ...) are not drawn anywhere.
- ВР-VS5-SC24-12 (names): BindWidget names above are proposals for UUmScreenPause / UUmSettingRow (UE part VS-7).
- ВР-VS5-SC25-01 (sound, SC-25, Marmoreal): tab Звук, rows in this order with the S08UserSettings.h defaults:
  «Общая громкость» 100 % + Mute unchecked, «Музыка» 60 %, «Эффекты» 80 %, «Интерфейс» 80 %, «Голоса» 80 %,
  «Окружение» 60 % + Mute unchecked, «Субтитры» check on «вкл», «Описывать звуки» check off «выкл». Frames: sound on
  all four canvases (at 720p 150 % and wherever needed the rows scroll, ВР-VS5-SC24-03). No other buses, no changed
  default.
- ВР-VS5-SC25-02: the slider step is 5 % (card timing) - not drawn; the value text is the integer.
- ВР-VS5-SC26-01 (language, SC-26, Sarpedon): tab Интерфейс with all four interface rows (Язык chips «Русский»
  selected / «English»; Масштаб интерфейса slider 100 %; Подсказки правил check on; Подсказки клавиш chips Авто
  selected / Вкл / Выкл). States ru, en, pseudo, each on all four canvases.
- ВР-VS5-SC26-02 (en): every interface string from the SourceString column of the same keys (no new literals, no
  translation of your own); the language chips keep their own names «Русский» / «English» in both languages; the
  value words and «{n} %» use the EN column («on», «off», «{n}%»). List every EN string with its key in README.
- ВР-VS5-SC26-03 (pseudo): pseudo(s) = "[" + s + "~" x k + "]" built from the RU string, with k the smallest count
  that makes the rendered width >= 1.3 x the RU width in the same font (measure). Hero, card and board names are
  never pseudo-localised (none are drawn here). No text clipped, wrapped into a button or covering another element on
  any canvas; if a chip line overflows 520 su it wraps to a second chips line (record it).
- ВР-VS5-SC27-01 (UI scale, SC-27, Marmoreal): five frames, each drawn on the canvas whose UI scale equals the slider
  value: scale-75 = Viewport(1920, 1080, 1.0, 0.75) (2560x1440 su, class L), scale-100 at 1080p 100 %, scale-150 at
  1080p 150 % (1280x720 su, S), scale-100 at 720p 100 % (1706.67x960 su, L), scale-150 at 720p 150 % (1137.78x640 su,
  S). File names SC-27-scale-<value>-<res>-<scale>.png. Tab Интерфейс as in SC-26 (ru). The Масштаб row shows the
  value «{n} %» and a Note «75–150 %» at 1080p, «100–150 %» at 720p (the slider minimum at 720p is 100 %: the
  track's left end means 100 there). The board frame is scaled only by the canvas (the UI scale never changes the
  board or world icons).
- ВР-VS5-SC27-02: the five combinations above replace the card's res x scale x state grid (scale-75 does not exist
  at 720p, and a slider value other than the frame's own scale would show a scale that is not applied).
- ВР-VS5-SC28-01 (game, SC-28, Sarpedon): tab Игра: «Скорость анимации» chips Нет / Быстро / Обычно (selected) /
  Медленно; «Сокращённые анимации» check off «выкл». No shake row (ВР-SC06). All four canvases.
- ВР-VS5-SC29-01 (hints, SC-29, Marmoreal): tab Интерфейс as SC-26 ru; the Подсказки клавиш row has the Note «Авто —
  только в первой партии» (type.caption) and, at the right of its chips and note, KeyHintSample: a panel.bg.inset box
  (radius 4, 8 su padding) holding the END TURN cell exactly as HB-42 / HB-43 draw it - class L: cell 86x72 su,
  action-end-turn disc 48 su at (+19, +4), label «КОНЕЦ ХОДА» type.tag caps on the baseline y + 67 su, key chip «E»
  20x20 su 2 su from the top and right edges; class S canvases: cell 48x48 su, disc 40 su at (+4, +4), no label, the
  key chip in the same corner. The sample is in the «доступна» state (not the yellow primary body: one primary per
  window, and it is a preview, not a button of the modal). If the sample does not fit beside the chips, put it under
  the note line, left-aligned (record it).
- ВР-VS5-SC29-02: the key is a chip on the button, never in a status text (04 §2.11).
- ВР-VS5-SC30-01 (graphics, SC-30, Sarpedon): tab Графика: «Качество графики» chips Высокое (selected) / Среднее /
  Низкое, Note «Масштаб экрана 100 % и лимит 60 кадров/с не меняются» (type.caption, text.secondary; may wrap to two
  lines inside 520 su). All four canvases.

Outputs of every package (in addition to the card deliverable):
- layout-geometry.json: per canvas and frame the rectangles in su with the BindWidget names above.
- verification.json: the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line as {passed, measured, expected, note}) plus text contrast per panel
  (every text against its own background, the selected chip text against teal), icon and edge contrast (measured on
  the grey finals too), smallest text px at 720p, overlap (modal layers separately), primary-button count per frame,
  modal height and scroll state per frame, clipped-text count per frame (must be 0), and a check that every drawn
  value equals the input (defaults, 30 s, ranges). Do not repeat the per-file hashes of the hud-icons-v3 files (tree
  digest, count, changed files, icons used). manifest-sha256.json covers every package file except itself, every file
  in scraped-data/derived/<set>-codex/ and the inputs.
- Open and look at every final PNG before you finish a package (colour and grey, all canvases) and record it in
  visual-review.json (path, sha256, what you checked). README.md in Russian, status «предложено», with the decisions
  above and the string-table delta.

Extra inputs (add them to source-hashes-before.json and the manifest of every package that uses them):
docs/unreal/contracts/hud/st-screens.csv; docs/unreal/contracts/hud/st-hud.csv;
docs/unreal/contracts/hud/why-reasons.json; docs/unreal/contracts/hud/hud-style-tokens.json;
docs/game-design/visual/06-tasks/screens.csv (rows SC-24...SC-30, column "do"); docs/art-pipeline/render-reference.json;
AGENTS.md (sections «Unreal GPU load», «Board scenes and heroes»); unreal/Unmatched/Source/Unmatched/S08/
S08UserSettings.h (read only); backend/src/game-engine/models/game-state.model.ts; art/imagegen/hud-skins-v1-codex/
(README.md, runtime-style.json, slice-margins.json, vector/); art/imagegen/sc01-screen-base-codex/ (README.md,
_tools/, manifest-sha256.json); art/imagegen/hud-icons-v3/_tools/draw_icons.py and the sizes/ files you paste;
art/imagegen/hud-composition-v1-codex/masks.json; art/imagegen/sc19-loading-codex/ (README.md, _tools/; read only);
art/imagegen/hud-actions-v1-codex/ (README.md, facts.json, _tools/; SC-29); for SC-25 ... SC-30 also
art/imagegen/sc24-pause-codex/ (README.md, _tools/, manifest-sha256.json).
```
