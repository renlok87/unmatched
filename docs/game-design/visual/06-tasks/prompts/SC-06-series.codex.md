# CX-28 - Codex series task: LOGIN mockups SC-06, SC-07

Written by Claude by hand (05 §2, ВР-PL05: screens of one family run as a series in one chat, one folder per card).
It only orders the two card tasks built by `prompt_build.py` and adds the inputs and decisions Claude prepared before
the run (ВР-VS4-SC06-01…07, by delegation, 2026-10-07).

| field | value |
|---|---|
| id | CX-28 (cards SC-06, SC-07) |
| date | 2026-10-07 |
| template | T-CODEX-LAYOUT |
| packages | `art/imagegen/sc06-login-form-codex/`, `art/imagegen/sc07-login-errors-codex/` |
| base library | `art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py` (SC-01, accepted in 2ddb5193) |
| image generations allowed | 0 |

## Task

```text
Series CX-28: two mockup packages, one after another, in this order. Read every file as UTF-8.
1. docs/game-design/visual/06-tasks/prompts/SC-06.codex.md -> art/imagegen/sc06-login-form-codex/
2. docs/game-design/visual/06-tasks/prompts/SC-07.codex.md -> art/imagegen/sc07-login-errors-codex/
Do each task completely (its package contract, inputs, layout rules, deliverable and acceptance) before starting the
next. The task text is the "Task" section of each file; its header tables are provenance only. Each package writes
only into its own folder and its own scraped-data/derived/<set>-codex/ folder. No git, no MCP, nothing under
unreal/, no image generation. SC-07 copies the FINAL _tools/sc06_login_form.py of package 1 unchanged into its
_tools/ (record its sha256) and extends it in a separate module.

Common notes (they apply to both packages):
- SC-01 library: copy art/imagegen/sc01-screen-base-codex/_tools/screen_mockup_base.py unchanged (sha256 d970f881...
  in that package's manifest-sha256.json). It draws the veil, panels, modal, buttons, chips, text fields and the
  spinner with the accepted HB-08 skins: pass art/imagegen/hud-skins-v1-codex/vector/ as the skins folder (read its
  README.md, runtime-style.json and slice-margins.json) and docs/unreal/contracts/hud/hud-style-tokens.json as the
  tokens. Do not redraw those elements yourself; extend the library in your module. Read
  art/imagegen/sc01-screen-base-codex/README.md and its _tools/build_package.py for the accepted patterns (its
  component sheet already shows Email / Пароль fields with labels above them and the RU/EN-style chips).
- Icons: paste the art/imagegen/hud-icons-v3/sizes/<name>-<px>.png whose pixel size equals size_su x px-per-su exactly
  (sizes 16, 18, 21, 24, 32, 36, 48, 64, 72, 96 exist). When that size does not exist (for example 24 su at 720p 150 %
  = 27 px), render it with render(name, px) of your unchanged copy of art/imagegen/hud-icons-v3/_tools/draw_icons.py
  (_tools/draw_icons_v3_snapshot.py, never call its main()); if that cannot run, resample the next larger file with
  LANCZOS and write it in verification.json. Never NEAREST-upscale an icon. Cursors are pixel-sized (02 section 4.4):
  cursor-busy-<px>.png with px = 32 x px-per-su of the canvas (24, 32, 36, 48 exist).
- Strings, RU column only. docs/unreal/contracts/hud/st-screens.csv (column "ru"): screens.login.title «Вход»,
  screens.login.email «Email», screens.login.password «Пароль», screens.login.submit «Войти», screens.login.busy
  «Вход…», screens.login.error.credentials «Неверный email или пароль», screens.login.error.server «Сервер
  недоступен», common.btn.retry «Повторить». docs/unreal/contracts/hud/why-reasons.json: why.login.fields «Заполните
  email и пароль», why.syncing «Синхронизация…». Language chips «RU» and «EN» are the locale codes named in 04
  section 1.2 («Язык RU / EN»). Cite each text in manifest facts (file, key or row).
- The sha256 prefixes written inside the task texts for 04-hud-spec.md, 02-visual-design.md and why-reasons.json are
  from the time the cards were written; these files changed since. Use the current files and record their current
  sha256 in source-hashes-before.json.
- Background: the Marmoreal P7 K1 frame named in the tasks under panel.veil 0.6 (one veil, no blur). It is a
  placeholder until SC-02; in the game the menu background has no figures (ВР-75). Keep the SC-01 overview caption
  «фон-заглушка: в игре фигур нет (ВР-75)» in a small panel inside the safe area exactly as the SC-01 finals do
  (ВР-VS3-SC01-05), placed so it never collides with the screen's own elements (the language chips are bottom right).
- LOGIN is a full screen over the veil: its card and chips are a screen layer, exempt from the figure and space
  overlap rule like modals (04 section 1.6). Report them as kind "screen" in verification.json; persistent match
  panels: none, overlap 0 px^2.
- Canvases: library Viewport.preset 1080p/720p x 100/150. The card is centred, 480x420 su on every canvas (04 section
  1.2). The chips keep 24 su from the right and bottom edges on L and 16 su on S. Write the rectangles per canvas in
  layout-geometry.json.
- Images with the K1 frame go only to scraped-data/derived/<set>-codex/; the package folder holds scripts, JSON,
  README and the overlay sheets drawn on a plain card.navy background (no frame).
- verification.json uses the 07 section 1.2 keys (source_unchanged, exports, palette, gray, sizes, outside_folder [],
  acceptance with one entry per acceptance line) plus the layout measurements of the task; do not repeat the per-file
  hashes of the 1499 hud-icons-v3 files (tree digest, count, changed files, icons used). manifest-sha256.json covers
  every package file except itself, every file in scraped-data/derived/<set>-codex/ and the inputs.
- Open and look at every final PNG before you finish a package. README.md in Russian, status «предложено».

Decisions made by Claude before the run (by delegation, 2026-10-07):
- ВР-VS4-SC06-01 (credentials): the email value is the seeded test account pro@unmatched.com from
  backend/prisma/seed.ts (dev seed, username ProGamer, the run I host); it is an account name, not a secret. The
  password is never shown: the field shows exactly 8 dots «••••••••» of fixed length (ВР-SC09). Do not copy
  backend/prisma/seed.ts anywhere (not even to scraped-data/derived/); never write any password value, its length or
  any token into a file of the package, the manifest facts, README, verification.json or the mockups. In facts cite
  only the email and username lines of seed.ts by line number and sha256 of the file.
- ВР-VS4-SC06-02 (field labels): the labels «Email» and «Пароль» stay visible in every state, above their fields as in
  the accepted SC-01 component sheet (type.body, text.primary or text.secondary with >= 4.5:1 on the card); never a
  placeholder that disappears on input. The card stays 480x420 su with 24 su inner padding, fields and button
  432x48 su; 04's "step 64" is field to field without labels, so the step becomes 64 su + the label row. Write the
  resulting step in README. If everything does not fit 420 su, keep the 04 sizes and report it in verification.json.
- ВР-VS4-SC06-03 (eye toggle): no accepted v3 glyph for "show password" exists (no IC card). Reserve the
  RevealButton slot (24 su square, right inside the password field, 12 su from its right edge; the value area ends
  before it) but draw no invented glyph and no visible "уточнить" in it; mark the slot on the overlay sheet as
  "RevealButton 24 su · глиф: нет в v3" and list the missing glyph in README (needs a new IC card).
- ВР-VS4-SC06-04 (language): two chips «RU» and «EN» at the bottom right of the screen, 32 su high (04 section 3.1
  chips), library chip(); «RU» selected (Btn_Selected skin: state.pending body, card.glyph text), «EN» normal.
- ВР-VS4-SC06-05 (SC-06 frames): empty — both fields empty (labels visible), the Email field in its focus skin (focus
  on show, 04 section 1.2), «Войти» primary in the disabled skin with its why.login.fields line under it inside the
  error zone (as the SC-01 library draws it). input — Email «pro@unmatched.com», Пароль 8 dots, fields normal,
  «Войти» primary with the keyboard focus skin (BtnPrimary_Focus); the error zone is empty. No sign-up link.
- ВР-VS4-SC07-01 (icons): badge-refuse (IC-40, accepted 2026-10-07, «X на плашке») now exists, so the X sign is
  badge-refuse at 24 su instead of the placeholder marker-x-stamp named in SC-07; the busy cursor is cursor-busy
  (IC-61, accepted; its glyph is the state-sent hourglass of 02 section 4.4). Add both to the inputs.
- ВР-VS4-SC07-02 (busy): the in-flight state of 04 section 3.1: «Войти» primary in its disabled skin showing a 32 su
  loader-spinner left of the label «ВХОД…» (screens.login.busy) inside the button; the label is its visible reason
  (why code why.syncing is the hover tooltip, recorded in geometry, not drawn as a line); fields locked = their
  values kept (email, 8 dots) with the value text in text.secondary over Input_Normal (no new skin); the busy cursor
  over the button; no keyboard focus ring; error zone empty.
- ВР-VS4-SC07-03 (error.credentials): never show which field was wrong, so neither field uses the Input_Error skin.
  Email kept, password cleared (empty field, label visible), the password field in its focus skin (the frames assume
  the player submitted with Enter, 04 section 1.2). «Войти» is disabled again (password empty) with why.login.fields.
  The error zone (432 x <= 44 su, two lines) holds: badge-refuse 24 su + «Неверный email или пароль» (type.body,
  text.primary) first, then the why.login.fields line (type.caption, text.secondary). Only the X is red.
- ВР-VS4-SC07-04 (error.server): email kept, password kept (8 dots: the credentials were not rejected). «Повторить»
  (common.btn.retry) takes the 432x48 submit slot as the one primary button, with the keyboard focus skin. The error
  zone holds resource-connection-lost 24 su + «Сервер недоступен» (type.body, text.primary); its X is the only other
  red.
- ВР-VS4-SC06-06: screen sounds are not part of a mockup (05 section 3, VS-7 note); do not draw or list sound hooks.
- ВР-VS4-SC06-07: no image with readable card scans, card backs or avatars exists in these packages; if any image
  shows one, it goes only to scraped-data/derived/<set>-codex/.

Extra inputs (add them to source-hashes-before.json and the manifest of the packages that use them):
docs/unreal/contracts/hud/st-screens.csv; docs/unreal/contracts/hud/why-reasons.json;
docs/unreal/contracts/hud/hud-style-tokens.json; docs/game-design/visual/06-tasks/screens.csv (rows SC-06, SC-07,
column "do"); art/imagegen/hud-skins-v1-codex/ (README.md, runtime-style.json, slice-margins.json, vector/);
art/imagegen/sc01-screen-base-codex/ (README.md, _tools/); art/imagegen/hud-icons-v3/_tools/draw_icons.py; for SC-07
also art/imagegen/hud-icons-v3/sizes/badge-refuse-24.png (sha256 25d35180b44c...) and
art/imagegen/hud-icons-v3/sizes/cursor-busy-32.png (sha256 09c83fff1825...) with the other sizes you paste.
```
