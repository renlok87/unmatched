# CX-27 - Codex series task: BOOT mockups SC-03, SC-04, SC-05

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It only orders the three card tasks built by `prompt_build.py` and adds the inputs and decisions Claude prepared
before the run (ВР-VS4-SC03-01…08, by delegation, 2026-10-07).

| field | value |
|---|---|
| id | CX-27 (cards SC-03, SC-04, SC-05) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc03-boot-loading-codex/`, `art/imagegen/sc04-boot-error-codex/`, `art/imagegen/sc05-boot-resume-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| image generations allowed | 0 |

## Task

```text
Series CX-27: three mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-03.codex.md -> art/imagegen/sc03-boot-loading-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-04.codex.md -> art/imagegen/sc04-boot-error-codex/
3. docs/game-design/visual/06-tasks/prompts/SC-05.codex.md -> art/imagegen/sc05-boot-resume-codex/
Do each task completely (its package contract, inputs, layout rules, deliverable and acceptance) before starting the
next. The task text is the "Task" section of each file; its header tables are provenance only (do not open the
unreal/ paths listed there). Each package writes only into its own folder and its own
scraped-data/derived/<set>-codex/ folder. No git, no MCP, nothing under unreal/, no image generation. SC-04 and SC-05
copy the FINAL _tools/sc03_boot_loading.py of package 1 unchanged into their _tools/ (record its sha256) and extend it
in a separate module.

Common notes (they apply to all three packages):
- SC-01 library: copy art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py unchanged (sha256 d970f881...
  in that package's manifest-sha256.json). It draws the veil, panels, modal, buttons, chips, progress track and the
  spinner with the accepted HB-08 skins: pass art/imagegen/hud-skins-v1-codex/vector/ as the skins folder (read its
  README.md, runtime-style.json and slice-margins.json) and docs/unreal/contracts/hud/hud-style-tokens.json as the
  tokens. Do not redraw those elements yourself; extend the library in your module. Read
  art/imagegen/sc01-screen-base-codex/README.md and its _tools/build_package.py for the accepted patterns.
- Icons: paste the art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose pixel size equals size_su x px-per-su exactly
  (sizes 16, 18, 21, 24, 32, 36, 48, 64, 72, 96 exist). When that size does not exist (for example 48 su at 720p 150 %
  = 54 px), render it with render(name, px) of your unchanged copy of art/imagegen/hud-icons-v3/_tools/draw_icons.py
  (_tools/draw_icons_v3_snapshot.py, never call its main()); if that cannot run, resample the next larger file with
  LANCZOS and write it in verification.json. Never NEAREST-upscale an icon.
- Strings, RU column only. docs/unreal/contracts/hud/st-screens.csv (column "ru"): screens.boot.stage.session
  «Проверка сессии…», screens.boot.stage.heroes «Загрузка героев… {n}/{total}», screens.boot.stage.boards
  «Загрузка досок…», screens.boot.error.server «Сервер недоступен», common.btn.retry «Повторить».
  docs/unreal/contracts/hud/why-reasons.json: why.syncing «Синхронизация…». Proposed keys that exist only in the card
  rows (docs/game-design/visual/06-tasks/screens.csv, column "do"; ВР-SC15): screens.boot.title (the wordmark, value
  in 04 section 1.1 and in SC-03.do), screens.boot.build «сборка {commit}», screens.boot.resume.title «Партия идёт»,
  screens.boot.resume.line «Ваш герой: {hero} · соперник: {opponent} · {board}», screens.boot.resume.return
  «Вернуться в партию», screens.boot.resume.lobby «В лобби». Cite each text in manifest facts (file, key or row).
- The sha256 prefixes written inside the task texts for 04-hud-spec.md, 02-visual-design.md and why-reasons.json are
  from the time the cards were written; these files changed since. Use the current files and record their current
  sha256 in source-hashes-before.json.
- Background: the Marmoreal P7 K1 frame named in the tasks under panel.veil 0.6 (one veil, no blur). It is a
  placeholder until SC-02; in the game the menu background has no figures (ВР-75). Keep the SC-01 overview caption
  «фон-заглушка: в игре фигур нет (ВР-75)» in a small panel inside the safe area exactly as the SC-01 finals do
  (ВР-VS3-SC01-05), placed so it never collides with the screen's own elements (the build label is bottom right).
- BOOT is a full screen over the veil: its elements are a screen layer, exempt from the figure and space overlap rule
  like modals (04 section 1.6). Report them as kind "screen" (and the SC-05 modal as "modal") in verification.json;
  persistent match panels: none, overlap 0 px^2.
- Canvases (library Viewport.preset): 1080p 100 % uses the 04 column "1080p", 720p 100 % uses the 04 column "720p"
  (canvas 1706.67x960 su). For the two 150 % canvases (class S, 1280x720 and 1137.78x640 su) keep the centre anchor
  and the 1080p su offsets from the canvas centre (wordmark top -140, bar -40, caption -20) (ВР-VS4-SC03-03). The build
  label keeps 24 su from the right and bottom edges on L and 16 su on S (04 section 1, safe fields). Write the
  resulting rectangles per canvas in layout-geometry.json.
- Card scans, avatars and any image with the K1 frame go only to scraped-data/derived/<set>-codex/; the package
  folder holds scripts, JSON, README and the overlay sheets drawn on a plain card.navy background (no frame).
- verification.json uses the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line) plus the layout measurements of the task; do not repeat the per-file
  hashes of the 1499 hud-icons-v3 files (tree digest, count, changed files, icons used). manifest-sha256.json covers
  every package file except itself, every file in scraped-data/derived/<set>-codex/ and the inputs.
- Open and look at every final PNG before you finish a package. README.md in Russian, status «предложено».

Decisions made by Claude before the run (by delegation, 2026-10-07):
- ВР-VS4-SC03-01: the wordmark is the plain text of screens.boot.title from 04 section 1.1 (ВР-H19) in type.display
  (48 su Roboto Bold Condensed caps, text.primary). It is the only place the game title appears; no logo image, no
  other product, studio or edition names anywhere in the mockups or sheets.
- ВР-VS4-SC03-02: the stage caption sits on a capsule: panel.bg 1.0, edge panel.edge 1 su, radius 4 su, padding
  12 su left/right and 4 su top/bottom, width = text + 24 su (<= 600 su), text type.body text.secondary, centred
  under the bar with its text top at the 04 caption y. Reason (Claude's pre-measure, 1080p): text.secondary on
  panel.veil 0.6 over the Marmoreal frame in the caption box is 3.50:1 min, 4.12:1 p05, 4.83:1 median, below 4.5:1,
  and 04 section 3.7 forbids text on the scene without a capsule or panel. In verification.json record the caption
  contrast both against its capsule and (for the record) against the veiled frame. The wordmark (>= 3:1 for 48 su
  Bold) and the build label (>= 4.5:1) stay on the veil only if their per-pixel minimum against the veiled frame
  under their text boxes holds on every canvas; otherwise give them the same capsule. Measure per pixel, report min,
  p05 and median.
- ВР-VS4-SC03-04: progress by stages (ВР-SC15): ProgressTrack 480x8 su with a ProgressFill of width 480 x done / 3 su
  from the left (0/3 = empty track, 2/3 = 320 su). The SC-01 progress() draws an indeterminate segment; do not use it
  for these frames, extend in your module with the same HB-08 skins. No percentages.
- ВР-VS4-SC03-05 (SC-04): the error comes while the heroes stage waits for its answer, so the frame under the banner
  shows progress 1/3 and the caption «Загрузка героев…» without the counter (as quoted in SC-04.do): the counter
  {n}/{total} exists only after heroList answered (the SC-03 heroes frame, 2/3, 84/84). Proposed for the UE part as
  key screens.boot.stage.heroes.wait «Загрузка героев…»; write it in README and facts. The error capsule (panel.bg,
  edge panel.edge, radius 4 su, padding 12-16 su) sits under the caption capsule: icon resource-connection-lost 48 su
  (its red X is the only red), «Сервер недоступен» (type.body, text.primary), primary «Повторить» 48 su high. retrying:
  the same button in the disabled skin with its why.syncing line «Синхронизация…» (type.caption, text.secondary)
  under it, the stage caption stays visible.
- ВР-VS4-SC03-06 (SC-05): the modal comes at the end of BOOT, so it lies over the SC-03 loading-boards frame (the
  screen veil is the only veil; no second veil for the modal). Modal 640x300 su, panel.bg 1.0, radius 8 su, centred.
  Line «Ваш герой: Медуза · соперник: Король Артур · Marmoreal · original map», nominative, never declined: the
  viewer is the run I host pro@ (README "Аккаунты"); his hero is Medusa and the opponent's King Arthur from the host
  trace line "RESULT summary outcome=VICTORY winnerHero=Medusa loserHero=King_Arthur" (the host won as Medusa) and
  "ARTPREVIEW board ... boardId=c121b47f8d6eb28daccb76d05 ... map=Marmoreal"; RU names «Медуза», «Король Артур» and the
  board name «Marmoreal · original map» (the text before " (") from docs/game-design/05-content-matrix.csv rows medusa,
  king-arthur and board-marmoreal-original. If the line does not fit 608 su in one line, wrap it to two lines inside
  the modal; never shrink the type.
- ВР-VS4-SC03-07 (SC-05 resuming): «Вернуться в партию» goes to the in-flight state of 04 section 3.1: primary in its
  disabled skin, a 32 su spinner (loader-spinner) inside the button left of the label, and its why.syncing line
  «Синхронизация…» under the button. «В лобби» stays normal (it never leaves or aborts the match).
- ВР-VS4-SC03-08: screen sounds are not part of a mockup (05 section 3, VS-7 note); do not draw or list sound hooks.

Extra inputs (add them to source-hashes-before.json and the manifest of the packages that use them):
docs/unreal/contracts/hud/st-screens.csv; docs/unreal/contracts/hud/why-reasons.json;
docs/unreal/contracts/hud/hud-style-tokens.json; docs/game-design/visual/06-tasks/screens.csv (rows SC-03, SC-04,
SC-05, column "do"); art/imagegen/hud-skins-v1-codex/ (README.md, runtime-style.json, slice-margins.json, vector/);
art/imagegen/sc01-screen-base-codex/ (README.md, _tools/); art/imagegen/hud-icons-v3/_tools/draw_icons.py; for SC-05
also docs/game-design/evidence/DE-FOOTAGE/2026-10-05/I/marmoreal/combat-20261005-235827/combat-client-host.trace.txt
(sha256 08ddbf335e6a...) and docs/unreal/contracts/hud/why-reasons.json.
```
