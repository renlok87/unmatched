# CX-33 - Codex series task: RECONNECT mockups SC-31, SC-32, SC-33

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It orders the three card tasks built by `prompt_build.py`, names the real data Claude found before the run and the
decisions Claude took for them (ВР-VS5-SC31-01…06, ВР-VS5-SC32-01…03, ВР-VS5-SC33-01…04, by delegation, 2026-10-07).
The overlay must match what the game already has: the connection badge HB-14 (`UUmConnectionBadge`,
docs/game-design/evidence/VISUAL/HB-14/README.md) and the toasts HB-40 (`UUmToast`,
docs/game-design/evidence/VISUAL/HB-40/README.md).

| field | value |
|---|---|
| id | CX-33 (cards SC-31, SC-32, SC-33) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc31-reconnect-auto-codex/`, `sc32-reconnect-manual-codex/`, `sc33-reconnect-restore-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| data | run E trace (in git): a real test-initiated WebSocket drop on Marmoreal original, 2026-10-05 |
| image generations allowed | 0 |

## Task

```text
Series CX-33: three mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-31.codex.md -> art/imagegen/sc31-reconnect-auto-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-32.codex.md -> art/imagegen/sc32-reconnect-manual-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-33.codex.md -> art/imagegen/sc33-reconnect-restore-codex/
Do each task completely (package contract, inputs, layout rules, deliverable, acceptance) before the next. The task
text is the "Task" section of each file; its header tables are provenance only. Each package writes only into its
own folder and its own scraped-data/derived/<set>-codex/ folder. No git, no MCP, no network, nothing under unreal/,
no image generation. Where this file and a card text differ, this file wins (the card texts were written before the
data below was found).

Script chain: SC-31 writes the whole RECONNECT overlay in _tools/sc31_reconnect_auto.py with parameters for the board
background (marmoreal | sarpedon), the desaturation weight, the veil opacity, the card state (auto | manual | expired
| restoring | none), an optional toast and an optional connection chip. SC-32 and SC-33 copy the FINAL
sc31_reconnect_auto.py of package 1 unchanged and extend it only in their own module. Every package copies
screen_mockup_base.py (d970f881...) and art/imagegen/hud-icons-v3/_tools/draw_icons.py (as draw_icons_v3_snapshot.py)
unchanged. Record each copy's sha256 (copy-provenance.json).

Common notes (all three packages):
- SC-01 library: veil, panels, buttons with the accepted HB-08 skins; skins folder art/imagegen/hud-skins-v1-codex/
  vector/ (read README.md, runtime-style.json, slice-margins.json; T_Skin_Toast is the toast capsule), tokens
  docs/unreal/contracts/hud/hud-style-tokens.json. Do not redraw those elements. The library's veil() uses
  panel.veil 0.6; the 0.8 veil of RECONNECT is drawn in your module with the same colour. Read for patterns (read
  only, record sha256 if you reuse code): art/imagegen/sc01-screen-base-codex/README.md, art/imagegen/
  sc04-boot-error-codex/ (error row with a 48 su icon, overlays with BindWidget names and x/y/w/h su),
  art/imagegen/hud-feed-v1-codex/ (accepted HB-38 toast mockup: README.md, facts.json, _tools/; the toast placement
  chain and the HAND-CAPTION reserve).
- Icons: paste art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose size equals size_su x px-per-su exactly; when
  that size does not exist render it with render(name, px) of your unchanged draw_icons_v3_snapshot.py (never call
  main()); never NEAREST-upscale; never use the library's spinner() (it resizes with NEAREST). Static frames: the
  ↻ cycle (1200 ms) and the spinner steps are motion, not drawn. Used here: resource-connection-reconnecting 48 su
  (SC-31), resource-connection-lost 48 su (SC-32), loader-spinner 32 su and resource-connection-online 24 su (SC-33).
- Strings, RU column only, cite each in manifest facts (file + key):
  docs/unreal/contracts/hud/st-screens.csv: screens.reconnect.title «Соединение потеряно», screens.reconnect.attempt
  «Переподключение… попытка {n} из {max}», screens.reconnect.missed «Пропущено событий: {n}»,
  screens.reconnect.running «Партия продолжается на сервере. Не закрывайте приложение.», screens.reconnect.leave
  «Выйти в лобби», screens.reconnect.retry «Переподключить», screens.reconnect.session.expired «Сессия истекла —
  войдите снова»; docs/unreal/contracts/hud/st-hud.csv: hud.toast.reconnected «Позиции обновлены (пропущено {n})».
  Proposed by the cards (not in the tables yet; list them in README as a string-table delta):
  screens.reconnect.to.login «Ко входу» (SC-32), screens.reconnect.restoring «Загрузка состояния…» (SC-33; its text
  equals the existing row screens.loading.state). Buttons are upper case (type.button).
- ВР-VS5-SC31-01 (numbers, real data): docs/game-design/evidence/DE-FOOTAGE/2026-10-04/E/live/phase2/marmoreal/
  run-20261005-135124/phase2-client-joiner.trace.txt (sha256 64a5fa51...) is a real test-initiated drop on Marmoreal
  original: line 29 «WS DROPPED (test-initiated transport loss)», line 31 «SNAPSHOT applied seq=1» (seq at the loss =
  1), line 162 «WS reconnect attempt» (the only attempt: n = 1), line 163 «SUBSCRIBED gameStateUpdated since=1»,
  line 165 «SNAPSHOT applied seq=1» (seq after recovery = 1). Missed events n = seq after recovery − seq at the loss
  = 0 (rule ВР-VS4-31 in docs/game-design/evidence/VISUAL/HB-40/README.md; the accepted HB-38 toast uses the same
  run and n = 0). {max} = 5 (04 section 1.9). So: «Переподключение… попытка 1 из 5», «Пропущено событий: 0»,
  «Позиции обновлены (пропущено 0)». The fault runs file named in the task gives only one seq per run: cite it as
  checked, not as the source. No «уточнить» on any mockup: every value is resolved.
- ВР-VS5-SC31-02 (card): ReconnectCard 520 su wide, centred on the canvas, library panel kind "modal" (panel.bg 1.0,
  panel.edge), padding 24 su, one centred column: Icon slot 48x48 su; 16 su; Title (type.title, text.primary);
  12 su; Attempt (type.body, text.primary); 8 su; Missed (type.body, text.secondary); 12 su; Running (type.body,
  text.secondary; one line if it fits 472 su, else two lines broken only between the two sentences); 24 su; button
  row 48 su; 24 su padding. A line that a state does not show is removed with its gap above it. Height = content (no
  empty band); 04's 520x340 is the reference maximum; record each frame's height. The same su on all four canvases.
- ВР-VS5-SC31-03 (scene): CUE-017 / FX-35 desaturation of the scene frame only: per pixel out = L + s x (rgb − L),
  L = Rec.709 luma of the sRGB values, s = 1 − 0.3 x w (w = 1 while disconnected), then panel.veil card.navy #061623
  at 0.8 over the whole canvas, no blur. Write in README that this approximates the engine's ColorSaturation.
  The K1 frames have no HUD; in the game the frozen HUD lies under the veil (04 section 1.9): note it, do not draw it.
- ВР-VS5-SC31-04 (auto, SC-31, Marmoreal P7 K1 frame): Icon resource-connection-reconnecting 48 su; Title; Attempt
  «Переподключение… попытка 1 из 5»; Missed «Пропущено событий: 0»; Running; one button LeaveButton «ВЫЙТИ В ЛОББИ»
  normal, centred, width max(168 su, label + 48 su). RetryButton is hidden (not drawn) until the fifth attempt. No
  primary in this frame.
- ВР-VS5-SC31-05 (input): the card and the veil swallow input; no hover, no focus ring, no cursor in any frame of the
  series. ReconnectCard and the veil are modal layers: exempt from the figure and space overlap rule (04 section 1.6),
  reported as kind "modal".
- ВР-VS5-SC31-06 (overlays): comparison/<card>-overlay-<res>-<scale>.png and -gray.png on plain card.navy, outlines
  and labels only (no frame pixels, ВР-VS4-01): every element with its BindWidget name of the card's UE column and x,
  y, w, h in su — ReconnectCard (Icon, Title, Attempt, Missed, Running, Retry, Leave; SC-32 also ToLogin), and in
  SC-33 the toast UUmToast (Body, Text) and the chip UI-HUD-CONN; labels never overlap each other (measure, record 0).
- ВР-VS5-SC32-01 (manual, SC-32, Sarpedon P10 K1 frame, same desaturation and veil): Icon resource-connection-lost
  48 su (the arrow becomes an X: a change of shape); Title; the Attempt line is not drawn (the five automatic attempts
  are over and no string says so; the icon carries the change); Missed «Пропущено событий: 0»; Running; buttons
  LeaveButton «ВЫЙТИ В ЛОББИ» normal left and RetryButton «ПЕРЕПОДКЛЮЧИТЬ» primary right, 16 su apart, the same
  width = max(168 su, widest label + 48 su), the pair centred. Exactly one primary.
- ВР-VS5-SC32-02 (expired, SC-32, Sarpedon): Icon resource-connection-lost 48 su; Title «Сессия истекла — войдите
  снова» (screens.reconnect.session.expired, type.title) in place of «Соединение потеряно»; no Attempt, Missed or
  Running line; one button ToLoginButton «КО ВХОДУ» primary, centred, width max(168 su, label + 48 su). No lobby
  button: the lobby needs a valid session; the way is LOGIN (card). Exactly one primary.
- ВР-VS5-SC32-03: the expired frame never suggests reconnecting with the old token: no Retry, no attempt text.
- ВР-VS5-SC33-01 (restoring, SC-33, Marmoreal, same desaturation and veil): the Icon slot holds loader-spinner 32 su
  centred in the 48 su slot; Title «Загрузка состояния…» (screens.reconnect.restoring, type.title); no other line,
  no buttons.
- ВР-VS5-SC33-02 (exit at 200 ms, SC-33, Marmoreal): keyframes of the card SC-33 and of FX-36 (docs/game-design/
  visual/06-tasks/vfx.csv row FX-36, ВР-FX09: the saturation returns in 300 ms inside the 800 ms CUE-018 show, which
  wins over the card's "800 ms"): at 200 ms the card is gone (opacity 0), the 0.8 veil fades with the card and is gone,
  the desaturation weight is w = 1 − 200/300 = 1/3 (s = 0.9); the connection chip has crossfaded to online (150 ms);
  the toast has just appeared. Draw exactly that.
- ВР-VS5-SC33-03 (toast, HB-40 look): kind info = T_Skin_Toast capsule (panel.bg 0.92, panel.edge), text
  «Позиции обновлены (пропущено 0)» type.body text.primary, no sign, no close button (only sticky toasts have one),
  one line, 48 su high, 16 su side padding, width hugging the text and <= 560 su (1080p L), 520 su (720p L), 440 su
  (class S); centred on the canvas. Place it with the 04 section 2.12 chain as UmHudFeed::Place does: 1) centred
  above the hand (toast bottom = HAND-CAPTION top − 8 su; HAND at rest: centre bottom −16 su, cards 150x208 L,
  120x166 S; HAND-CAPTION as in the accepted HB-38 package); 2) top band y 216 su (class S: 162 su); 3) the smallest
  upward move in whole pixels, not above STATUS bottom + 8 su (L 80 su, S 72 su); 4) FAIL. Obstacles: the Marmoreal
  space and figure masks of art/imagegen/hud-composition-v1-codex/masks.json for that canvas's pixel size
  (marmoreal-1920x1080 or marmoreal-1280x720; spaces with their conservative dilation, figure polygons), plus the
  FIELD rectangle of 04 section 1.6 (1080p px (410, 255)–(1440, 850), x 2/3 at 720p), plus the HAND and HAND-CAPTION
  reserve. Record step, y in su and overlap per canvas, and compare with the client's measured info-toast positions
  on Marmoreal in the HB-40 README (y 209 / 123 / 180 / 104 su at 1080p 100 / 1080p 150 / 720p 100 / 720p 150);
  explain any difference. Overlap of the toast with spaces, figures and FIELD must be 0 px^2 (the toast is not modal).
- ВР-VS5-SC33-04 (connection chip, HB-14 look): UI-HUD-CONN is the square of the TOP plate at its client bbox (HB-14
  traces): L canvases (68, 24, 44, 44) su, class S (56, 16, 40, 40) su; body = HB-08 Panel skin (0.92) on that square,
  icon resource-connection-online 24 su centred. Only in the exit frame; the rest of TOP is frozen HUD that the K1
  frame does not show (write it in README). Report it as kind "hud": overlap with masks 0 px^2.

Outputs of every package (in addition to the card deliverable):
- layout-geometry.json: per canvas and frame the rectangles in su with the BindWidget names above.
- verification.json: the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line as {passed, measured, expected, note}) plus text contrast per panel
  (the toast against its capsule), icon and edge contrast (measured on the grey finals too), smallest text px at
  720p, overlap (modal layers separately), primary-button count per frame, card height per frame, the desaturation
  weight and veil opacity per frame, and a check that every drawn value equals the input (attempt 1, max 5, missed
  0). Do not repeat the per-file hashes of the hud-icons-v3 files (tree digest, count, changed files, icons used).
  manifest-sha256.json covers every package file except itself, every file in scraped-data/derived/<set>-codex/ and
  the inputs.
- Open and look at every final PNG before you finish a package (colour and grey, all four canvases) and record it in
  visual-review.json (path, sha256, what you checked). README.md in Russian, status «предложено», with the decisions
  above and the string-table delta.

Extra inputs (add them to source-hashes-before.json and the manifest of every package that uses them):
docs/unreal/contracts/hud/st-screens.csv; docs/unreal/contracts/hud/st-hud.csv;
docs/unreal/contracts/hud/hud-style-tokens.json; docs/game-design/visual/06-tasks/screens.csv (rows SC-31...SC-33,
column "do"); docs/game-design/visual/06-tasks/vfx.csv (rows FX-35, FX-36); docs/game-design/evidence/VISUAL/HB-14/
README.md; docs/game-design/evidence/VISUAL/HB-40/README.md; the run E trace above; AGENTS.md (section «Board scenes
and heroes»); art/imagegen/hud-skins-v1-codex/ (README.md, runtime-style.json, slice-margins.json, vector/);
art/imagegen/sc01-screen-base-codex/ (README.md, _tools/, manifest-sha256.json); art/imagegen/hud-icons-v3/_tools/
draw_icons.py and the sizes/ files you paste; art/imagegen/hud-composition-v1-codex/masks.json (SC-33; SC-31 and
SC-32 may use it for the overlap report); art/imagegen/hud-feed-v1-codex/ (README.md, facts.json, _tools/; read
only); for SC-32 and SC-33 also art/imagegen/sc31-reconnect-auto-codex/ (README.md, _tools/, manifest-sha256.json).
```
