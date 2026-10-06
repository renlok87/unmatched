# 07 — Шаблоны промптов для Codex, SYNTX, Tripo

Дата: 2026-10-06. Фаза 2 визуального чата ([00-VISUAL-BRIEF.md](00-VISUAL-BRIEF.md) §4.8, §5). Срез — HEAD `860ca478`.
Правила и токены — [02-visual-design.md](02-visual-design.md). Решения — [ВР-01…ВР-60](../decisions/2026-10-06-visual-delegated-decisions.md)
и ВР-61…ВР-79 в 02 §0.2.

**Статус документа — «предложено».** Решения в нём приняты по делегированию: пользователь 2026-10-06 — «Не знаю.
Делай сам, меня это не касается. Все решения принимай».

**Фаза 2 ничего не генерирует.** Шаблон заполняется только по готовой карточке `06-tasks/*.csv` (START-PROMPT:
«Генерируй только по готовой карточке задачи»). Цены SYNTX ниже получены бесплатными запросами цены
(`get-model-info`) без генерации.

Что учтено после описи (`git log 8aa356ff..HEAD`): глифы DE-012 в форме Codex вошли в набор v3 (`30ade784`), AB-5…AB-8
включены по умолчанию с флагами отката (`99ce5a1b`), звук влит (`d73d504c`). Пакет DE-012 —
[hud-icons-de012-codex/](../../../art/imagegen/hud-icons-de012-codex/README.md) — образец структуры этого документа.

## 0. Как пользоваться

### 0.1 Шаблон → строки таблиц задач

| Шаблон | Исполнитель | Таблица `06-tasks/` | Строки (по `area` и `deliverable`) |
|---|---|---|---|
| T-CODEX-2D | Codex | `icons.csv` | значки и глифы (ВР-44: бейджи, `zone-<key>`, чипы команд, `action-end-turn`, `state-heal`, `state-warning`, `card-drop`) |
| T-CODEX-LAYOUT | Codex | `hud.csv`, `screens.csv` | блок HUD в состоянии, экран (макет раскладки) |
| T-CODEX-9SLICE | Codex | `hud.csv`, `icons.csv` | панели, кнопки ×6 состояний, тост, капсула, курсоры ×4 (ВР-46) |
| T-CODEX-CARDFRAME | Codex | `cards-portraits.csv` | рамка карты ×состояния, рубашка в рамке, инспектор, круг портрета |
| T-CODEX-VFX | Codex | `vfx.csv` | флипбуки и формы для Niagara по CUE |
| T-CODEX-ENVPLATE | Codex | `env.csv` | чистая плита, outpaint, маски анимации Marmoreal (ВР-54, ВР-55) |
| T-CODEX-ANIMSHEET | Codex | `anim.csv` | схема ключевых поз и таймингов клипа или процедурной постановки |
| T-SYNTX-IMG-BANANA, -SEEDREAM, -GPT, -FLUX | SYNTX | `env.csv`, `vfx.csv` | правка плиты, когда Codex не держит размер или опору; эскизы стиля |
| T-SYNTX-VID-KLING, -SEEDANCE | SYNTX | `anim.csv`, `vfx.csv`, `env.csv` | видео-референс движения или тайминга |
| T-SYNTX-UPSCALE | SYNTX | `env.csv` | ×2 только своей сгенерированной плиты (ВР-48) |
| T-CODEX-HEROVIEWS, T-TRIPO-PART, T-BLENDER-FIG | Codex, Tripo, Blender | `anim.csv` (`hero`) | только после MVP (ВР-18) |

Если карточке нужен шаблон, которого нет, — сначала строка в этом документе, потом генерация.

### 0.2 Переменные

Синтаксис — `{{поле}}`, значение — из колонки карточки (бриф §4.8). Пустое поле не выдумывается: карточка
возвращается на доработку.

| Переменная | Колонка карточки | Правило подстановки |
|---|---|---|
| `{{id}}`, `{{area}}`, `{{title}}` | `id`, `area`, `title` | как есть; `title` в промпте генерации — по-английски |
| `{{priority}}`, `{{depends_on}}` | те же | только в шапке задания Codex |
| `{{purpose}}`, `{{do}}`, `{{dont}}` | те же | в промпт — переводом на английский, без правки смысла |
| `{{trigger}}`, `{{timing}}` | те же | CUE, событие или экран; мс и кадры только из 02 §8–§9 и cue-table |
| `{{keyframes}}`, `{{states}}` | те же | фазы `0 ms: …; 70 ms: …`; состояния UI через `;` |
| `{{readability}}` | `readability` | минимальный размер, контраст, серый тест |
| `{{palette_tokens}}` | `palette_tokens` | раскрывается в `token #HEX` по 02 §2; hex вне 02 запрещён |
| `{{type_tokens}}` | `type_tokens` | раскрывается в `type.* = N su, начертание` по 02 §3.3 |
| `{{references}}` | `references` | наши файлы с sha256; кадры DE сюда не входят (ВР-PR08) |
| `{{tool}}`, `{{prompt}}` | те же | шаблон и модель; путь к заполненному файлу промпта (ВР-PR09) |
| `{{deliverable}}`, `{{budget}}`, `{{acceptance}}` | те же | формат и имена; px, кадры, спрайты, потолок токенов; критерии → самопроверка |
| `{{ue_target}}` | `ue_target` | путь ассета и флаг отката; Codex в UE не пишет, поле только для README |
| `{{set}}` | из `deliverable` | имя пакета: папка `art/imagegen/{{set}}-codex/` |
| `{{inputs}}` | `references` + обязательный список шаблона | путь, sha256, что это |
| `{{date}}` | — | дата заполнения, ISO |

### 0.3 Общие блоки

Блоки вставляются в промпт целиком, без сокращений. Обозначение — `[[B-…]]`.

**[[B-STYLE]]** — язык 02 §1, §4, §5.1 по-английски:

```text
Style: flat printed board-game token language. Die-cut silhouette, constant-width hairline edge, flat print,
bold flat glyph. Three tones per element: body, edge, glyph; an outer dark keyline only where the element lies on the
board. No gradients, no highlights, no bevels, no embossing, no textures, no drop shadows, no glow, no lens effects,
no stone, no parchment, no metal, no bronze. No brush strokes, no ink splatter, no paint splash anywhere.
Shape is the first channel, colour is the third: every state must stay readable in grayscale.
```

**[[B-PALETTE-CORE]]** — базовые токены 02 §2 (sRGB):

```text
Palette (use only these hex values, plus the card tokens listed below):
card.navy #061623 (dark body, panels), card.cream #F9EBDB (edges, hairlines), card.glyph #FAF8F2 (white print),
mark.keyline #111317 (outer keyline on the board), text.primary #F2EDE4, text.secondary #B9B2A6 (muted),
card.type.attack #DC2F33, card.type.defense #2976AE, card.type.versatile #6B4E8F (maneuver only),
card.type.scheme #FDBE72, state.pending #0D7A89 (choice in HUD), board.choice #4CD2DC (choice on the board),
board.reach #FFC857, state.error #D9483F (only an X or "!" sign, never a fill), turn.flash.yellow #F2C14E,
turn.flash.orange #E8812C, team.p1 #E8C06A, team.p2 #5A7F9F, accent.warm #FFB45C (hit star), fx.heal #8CE69A.
```

**[[B-FORBID]]** — запреты для любого генератора:

```text
Forbidden: copying or imitating pixels, assets, splash art, logos, card text or fonts of any commercial digital
edition of a board game; brush-stroke banners and ink splatter; invented game data (card names, numbers, hero
names, HP, boards, spaces); text, letters or numbers baked into textures; red fills; any element on screen that
carries meaning only by colour.
```

**[[B-PACKAGE]]** — договор пакета Codex (§1.1), вставляется в каждое задание Codex.

### 0.4 Правила промптов (по делегированию)

- Промпт генерации — по-английски. Задание Codex — по-английски, README пакета — по-русски.
- В промптах генерации нет названий «Unmatched», «Digital Edition», художников и студий (ВР-PR07). Стиль задаётся
  словами и токенами.
- Hex — только из 02 §2. Новый цвет — сначала строка токена в 02, потом промпт.
- Числа (мс, кадры, размеры) — только из карточки и 02. Тайминги DE — только как источник уже записанных чисел F-01…F-12.
- Один промпт — одна единица реестра. Варианты A/B — разные ключи в `prompts/*.json`, не смесь в одном кадре.

## 1. Codex (приложение ChatGPT, `codex.exe exec`)

### 1.1 Договор пакета

Запуск (бриф §5.1): приложение ChatGPT (пакет OpenAI.Codex) → Ctrl+N в проекте `unmached` → короткое сообщение
«Прочитай `{{prompt}}` и выполни задачу». Запасной путь — `codex.exe exec -C <repo> "..."` из папки приложения
`C:/Program Files/WindowsApps/OpenAI.Codex_*/app/resources/`. npm-версия `codex` не работает.

Пользователь, 2026-10-05: «Codex пишет только в свою папку и не коммитит». Отсюда:

| Что | Где | В git |
|---|---|---|
| задание (заполненный шаблон) | `docs/game-design/visual/06-tasks/prompts/{{id}}.codex.md` (пишет Claude, ВР-PR09) | да, коммитит Claude |
| пакет Codex | `art/imagegen/{{set}}-codex/` | да, после ревью §5, коммитит Claude |
| картинки со сканами карт, аватарами, иллюстрацией карты, концептом окружения | `scraped-data/derived/{{set}}-codex/` (ВР-PR01, ENV-U3) | нет (папка в `.gitignore`) |
| листы «наш ассет рядом с кадром DE» | `C:/tmp/visual-review/{{set}}/` (ВР-60) | нет |

Состав папки пакета:

```text
art/imagegen/{{set}}-codex/
  README.md                 по-русски: что сделано, ссылки на листы, рекомендация, статус «предложено», открытые вопросы
  prompts/                  дословные промпты: <family>-prompts.json (ключ варианта → текст), правки — *.txt
  generation-records.json   каждая генерация: id, card_id, tool, mode, references[{path, sha256}], original_path, saved_path, date
  concepts/                 сырые результаты генерации без ретуши (только без сканов и без иллюстрации карты)
  _tools/                   копия генератора (draw_icons_v3_snapshot.py без правок) + свой модуль, build_review.py, verify_outputs.py
  vector/                   финальные экспорты по {{deliverable}}: мастер, рабочие размеры, x1/x2, слои
  comparison/               листы: цвет и серый; мастер и рабочие размеры; nearest ×4 для мелких
  verification.json         машинные проверки (§1.2)
  manifest-sha256.json      sha256 всех файлов пакета и файлов в scraped-data/derived/{{set}}-codex/
  source-hashes-before.json sha256 входов и чужих файлов, которые Codex читал, — до работы
```

**[[B-PACKAGE]]** (текст для задания):

```text
Package contract.
- Write ONLY inside art/imagegen/{{set}}-codex/. Images that contain card scans, hero avatars, card backs, the board
  illustration or the environment concept go ONLY to scraped-data/derived/{{set}}-codex/. Nothing else on disk changes.
- No git commands at all (no add, commit, stash, reset, checkout, branch). Claude reviews and commits.
- Do not open, edit or build anything under unreal/. Do not start Unreal Editor, UBT or packaging.
- Do not edit art/imagegen/hud-icons-v3/ or its _tools/draw_icons.py. Copy the generator into your _tools/ unchanged
  (draw_icons_v3_snapshot.py) and extend it in a separate module.
- Before work, record sha256 of every input and of art/imagegen/hud-icons-v3/** in source-hashes-before.json;
  after work, prove in verification.json that they are unchanged.
- Save every generation unretouched in concepts/ and log it in generation-records.json with its exact prompt key.
- Final files use exact token hex values and are drawn by script (vector or procedural), not by image generation.
- Build comparison sheets in colour and in grayscale (Rec.709 luma), at master size and at working sizes.
- README.md in Russian: what was done, links to sheets, which variant you recommend and why, what failed, status
  "предложено". Report honestly: a limit you could not meet is written in verification.json, not hidden.
- Small decisions are yours; write them in README.md. Stop only on blockers (login, captcha, payment).
```

### 1.2 Общая самопроверка пакета (`verification.json`)

- `source_unchanged`: sha256 v3 и входов совпали до и после.
- `exports`: для каждого PNG — размер, режим RGBA, поля `margin_px`, `touches_edge`.
- `palette`: доля непрозрачных пикселей финала вне ΔE76 ≤ 3 от токенов карточки (антиалиасинг кромки не в счёт) — 0.
- `gray`: у каждого финала есть серый вариант; пары состояний различаются в сером (разница luma ≥ 20 или форма).
- `sizes`: все размеры из `{{deliverable}}` есть, даунскейла мастера нет (И-9).
- `outside_folder`: список изменённых путей вне двух папок пакета — пустой.
- `acceptance`: каждая строка `{{acceptance}}` → `{passed, measured, expected, note}`.

### 1.3 T-CODEX-2D — значки и глифы

**Цель.** Форма значка в языке v3 для движка `draw_icons.py`. Финал рисует движок; Codex даёт форму числами.

**Входы:** [STYLE-v3.md](../../../art/imagegen/hud-icons-v3/STYLE-v3.md) §1–§4, §8, §11 (правило 9 в части мазка
отменено, ВР-09); `art/imagegen/hud-icons-v3/_tools/draw_icons.py` (`TOKENS`, `ROLE`, `CANDIDATES`); лист
`art/imagegen/hud-icons-v3/sheets/` текущего набора; 02 §5; `{{references}}`.

```text
Task {{id}} — {{title}}. Priority {{priority}}. Depends on {{depends_on}}.
Purpose: {{purpose}}.
[[B-PACKAGE]]
Read: art/imagegen/hud-icons-v3/STYLE-v3.md sections 1-4, 8, 11 (rule 9 brush/ink part is cancelled);
art/imagegen/hud-icons-v3/_tools/draw_icons.py; docs/game-design/visual/02-visual-design.md sections 5 and 11.4;
{{inputs}}.
1. Concepts. With image generation make 2 concepts (A, B) per glyph. Image prompt for each:
   "Original small HUD glyph concept. Square image, one centered glyph only, outer bounds within 15-85% of the
   canvas, uniform solid background #061623. [[B-STYLE]] Family: {{states}}. Meaning: {{purpose}}.
   Glyph: {{keyframes}}. Must stay clear at 24, 32 and 48 px. Colours: {{palette_tokens}}. No lettering,
   no numbers. [[B-FORBID]]"
2. Vector. In your _tools module add the glyph to a local CANDIDATES dict using the v3 grid: 32 u canvas
   (plates 64 x 32 u), keyline 1 u, edge 1.25 u, stroke W 2.25 u, every detail >= 1 u snapped to pixels; detail
   removed (not thinned) at detail <= 1; compound shapes by fill + CLEAR, no clip.
3. Export from vector: 1024 master and 16, 21, 24, 32, 48, 64, 96 px; plus layers if motion needs them ({{timing}}).
4. Sheets: concept A / concept B / vector, at 1024 and at 24, 32, 48 px (x4 nearest), colour and gray; the glyph on
   card.navy, on card.cream and on a neutral board grey #808080.
5. Write in README the exact numbers of the recommended form (radii, half-spans, stroke widths in u) so Claude can
   copy them into draw_icons.py one-to-one.
Deliverable: {{deliverable}}. Readability: {{readability}}. Do: {{do}}. Do not: {{dont}}.
Acceptance: {{acceptance}}.
```

**Выход:** `vector/{1024,16,21,24,32,48,64,96}/{{id-glyph}}.png` и `-gray.png`, слои, листы, числа формы в README.

**Самопроверка (добавка к §1.2):** силуэт относится к семейству STYLE-v3 §3.3; не больше трёх тонов; в 24 px
нет серой каши (детали ≥ 1 px); нет букв и цифр (И-7); красный только у знака X или «!»; занятые формы зоны
(звезда, щит, ромб, X, «!», сердце, шестигранник, «+») не повторены для нового смысла (02 §7.4).

**Запреты:** правка `hud-icons-v3/`; финал из ImageGen; 16 px как рабочий размер HUD (ВР-42).

### 1.4 T-CODEX-LAYOUT — макет HUD или экрана на реальных данных

**Цель.** Раскладка блока или экрана на настоящих данных партии. Пользователь 2026-10-05: «Макеты UI только на
реальных данных бэкенда и админки. ImageGen — не для макетов с игровыми данными». Метод — сборка скриптом, как
[move-selection-v2](../../../art/imagegen/move-selection-v2/README.md). Генерации изображений в этом шаблоне нет
(ВР-PR02).

**Обязательные входы** (каждый — путь и sha256 в `source-hashes-before.json`):

| Что | Источник |
|---|---|
| иллюстрация доски | `scraped-data/images/maps/marmoreal.png`, `sarpedon.png` |
| пространства, связи, зоны | `backend/prisma/fixtures/boards/{marmoreal,sarpedon}.topology.json` |
| кадр сцены (фон под HUD) | наш кадр UE с отпечатком `RENDER`, например [evidence I](../evidence/DE-FOOTAGE/2026-10-05/I/README.md); только Marmoreal или Sarpedon original, шесть фигур v2 |
| герои: имя, HP, движение, помощники | `scraped-data/api/heroes/<slug>.json`, `docs/game-design/evidence/S01/catalog-<hero>.json`, БД бэкенда через админку |
| аватары и помощники | `Hero.avatarUrl`, `sidekicks[].avatarUrl` → `scraped-data/images/heroes/avatars/`, `.../sidekicks/` |
| сканы карт и рубашки | [reused-cardart.json](../../../art/imagegen/mvp-v1/reused-cardart.json) (`en.path`, `ru.path`), `Hero.imageUrl` |
| строки RU/EN | StringTable-ключи из `04-hud-spec.md` и `why-reasons.json`; нет строки — «уточнить: <где>» |
| значки | `art/imagegen/hud-icons-v3/sizes/` (принятые) |
| токены, кегли, радиусы | 02 §2–§4 |

```text
Task {{id}} — {{title}} ({{area}}). Priority {{priority}}. Depends on {{depends_on}}.
Purpose: {{purpose}}. Trigger: {{trigger}}. States: {{states}}.
[[B-PACKAGE]]
No image generation in this task. Build the mockup with a script (Python, Pillow or pycairo) in your _tools/ from
real inputs only: {{inputs}}. Every name, number, card and avatar on the mockup must come from these files; if a value
is missing write the literal text "уточнить" in the mockup and list it in README.
Layout rules: canvas 1920x1080 and 1280x720 (device scale 1.0 and 0.75), UI scale 100% and 150%. Units su, 1 su = 1 px
at 1080p. Panels: body card.navy #061623 at opacity 0.92, hairline edge card.cream #F9EBDB at opacity 0.45, 1 su,
radii 4/6/8 su, padding 12-16 su, no shadow, no blur. Text: Roboto Bold Condensed and Roboto Regular from
C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/, sizes {{type_tokens}}, text.primary #F2EDE4,
text.secondary #B9B2A6, no text smaller than 14 su. Icons >= 24 su. Cards: hand 150x208, hover 225x312, combat
230x319, inspector <= 460x640 su, the scan whole inside our frame, nothing printed over the scan. Portrait circle 80 su,
sidekick 40 su, turn ring outside the circle. Panels never cover figures, target spaces or reachable spaces.
Colours: {{palette_tokens}}. [[B-STYLE]] [[B-FORBID]]
Output: mockups with scans or board art -> scraped-data/derived/{{set}}-codex/<id>-<state>-<res>-<scale>.png plus
-gray.png; in your package folder only the script, a manifest with sha256 of inputs and outputs, and an overlay
sheet without scans (panel rectangles, anchors, sizes in su) in comparison/.
Also measure and write to verification.json: text contrast per panel (WCAG), overlap in px^2 of panels with figure
and space masks (must be 0), smallest text in px at 720p.
Deliverable: {{deliverable}}. Readability: {{readability}}. Do: {{do}}. Do not: {{dont}}.
Acceptance: {{acceptance}}.
```

**Самопроверка:** каждый текст и число макета прослеживается до файла входа (`manifest` → `facts`); доска — одна из
двух настоящих; фигуры — v2; контраст текста ≥ 4,5 : 1, значков ≥ 3 : 1; перекрытие 0 px²; есть 720p и 150 %.

**Запреты:** ImageGen и SYNTX в любом виде; придуманные карты, герои, HP, пространства; доски Cobble, ART FIXTURE,
20×20; кадры DE как фон; картинки со сканами в `art/imagegen/`.

### 1.5 T-CODEX-9SLICE — панели, кнопки, курсоры

**Цель.** Около 40 PNG скинов и 4 курсора (ВР-46). Рисует движок v3 в новом режиме skins (02 §4.2), не ImageGen.

```text
Task {{id}} — {{title}}. States: {{states}}.
[[B-PACKAGE]]
No image generation. Extend your copy of the v3 engine with a "skins" mode and draw flat 9-slice PNGs from tokens:
{{palette_tokens}}.
Rules: radius.s 4 su (buttons, chips, capsules), radius.m 6 su (panels), radius.l 8 su (modals, card frame); hairline
1 su card.cream at opacity 0.45; corner of the slice = radius + edge + 1 px; edges snapped to pixels (1 px at x1, 2 px
at x2); centre stretches, edge never stretches; export x1 and x2.
Button states (02 section 4.3): normal, hover (body #1E2B35, edge card.cream 1.0), pressed (body #040E17),
disabled (icon opacity 0.4, text #B9B2A6), focus (white ring #FAF8F2 2 su outside with 2 su gap), selected (body
#0D7A89, text and edge #FAF8F2). Primary button: body #F2C14E, edge card.navy 1 su, text card.navy.
Cursors 32x32 px x1 and x2: arrow #FAF8F2 with 2 px keyline #111317, hotspot (1,1); pointing hand, hotspot at the
fingertip; arrow plus small X #D9483F; hourglass, max 8 frames, cycle 1500 ms. No shadow.
Write slice margins (left, top, right, bottom in px) for every file to verification.json.
Sheets: every skin stretched to 3 sizes on card.navy and on a Marmoreal and a Sarpedon backdrop crop taken from our
UE frames (those sheets go to scraped-data/derived/{{set}}-codex/), colour and gray.
Deliverable: {{deliverable}}. Acceptance: {{acceptance}}.
```

**Самопроверка:** кромка не растягивается на листе растяжки; контраст кромки к `panel.bg` ≥ 3 : 1 (4,0 по 02);
текст на главной кнопке ≥ 4,5 : 1; на бирюзе — только `card.glyph`; горячая точка курсора записана.

### 1.6 T-CODEX-CARDFRAME — рамка карты, рубашка, инспектор

**Цель.** Наша рамка вокруг оригинального скана (ВР-49). Скан не перерисовывается, не апскейлится ИИ, текст поверх
не печатается (ВР-48).

```text
Task {{id}} — {{title}}. States: {{states}}.
[[B-PACKAGE]]
No image generation on scans, avatars or card backs. Draw the frame by script; composite real scans only for review.
Inputs: art/imagegen/mvp-v1/reused-cardart.json (27 MVP cards; RU scans 287x398 for the RU build, EN scans 250x349),
Hero.imageUrl card backs (768x1051), {{inputs}}.
Frame: underlay card.navy #061623, 4 su around the scan, radius.l 8 su, hairline card.cream #F9EBDB at 0.45, outer
keyline #111317 1 su. Aspect 0.721 for every display size: hand 150x208, hover 225x312, combat 230x319, source slot
190x264, inspector <= 460x640 su (max 1.6x of the scan), opponent back 48x67.
States (02 section 6.3): idle; hover (edge card.cream 1.0, lift 24 su); selected (edge #0D7A89 3 su, lift 32 su);
playable; not playable (scan saturation -60%, opacity 0.7, applied in UE, show as a preview only); new (dot #FAF8F2
8 su top-right with keyline); discard by hand limit (edge #E8812C 2 su, down 16 su); played CUE-006 (edge flash
#FAF8F2 2 su -> idle edge in 500 ms).
State colour lives on the frame only. The card type is carried by the scan.
Output in package: frame PNGs with a transparent window, x1 and x2, 9-slice margins. Review composites with real scans
for every state and size -> scraped-data/derived/{{set}}-codex/, colour and gray.
Deliverable: {{deliverable}}. Acceptance: {{acceptance}}.
```

**Самопроверка:** окно рамки совпадает с пропорцией скана ±1 px; ни один показ, кроме инспектора, не увеличивает
RU-скан больше 1,0; инспектор ≤ 1,6×; на листах — реальные карты из `reused-cardart.json` по `heroSlug:cardSlug`.

**Запреты:** перерисовка, вырезка или апскейл скана; печать названия и значений поверх скана; картинки со сканами в git.

### 1.7 T-CODEX-VFX — флипбуки и формы для Niagara

**Цель.** Плоские формы «печатного» стиля (ВР-19, 02 §9) для своих систем Niagara (ВР-26).

Решения по делегированию (ВР-PR10): флипбук — **маска** (белая форма, прямая альфа), цвет даёт параметр материала
из токена `fx.*`; цветной вариант — только для листа. Частота листа — 30 кадров/с; кадров = `{{timing}}` × 30,
округлить, от 4 до 16; сетка 4×1, 4×2 или 4×4; ячейка 256 px (512 — только если форма > 25 % кадра K1).
Цвет в прозрачные пиксели расширен на 4 px (без тёмной каймы при mip).

```text
Task {{id}} — {{title}}. Trigger: {{trigger}}. Timing: {{timing}}. Keyframes: {{keyframes}}.
[[B-PACKAGE]]
Effect language: flat shapes with a hard edge, 2-3 tones from {{palette_tokens}}, duration <= 600 ms, no smoke, no
highlights, no glow gradients, no lens flares, no light emission, no camera shake. Shape first: star burst = hit, plus and
rising dots = heal, rim = defense, swirl of stone rings = Medusa gaze (no beam), short golden arc = Arthur sword,
three chevrons on the ground = attack direction, flat discs = dust, ash front = death.
1. Optional exploration: 2 image-generation concepts (A, B) on a flat #808080 background:
   "Original flat 2D game effect concept, {{title}}, shown as a 4-step strip from left to right: {{keyframes}}.
   Hard-edged flat shapes, 2-3 flat tones: {{palette_tokens}}. [[B-STYLE]] [[B-FORBID]]"
2. Final: draw the flipbook procedurally by script: white shape on transparent, straight alpha, frame count
   {{budget}} (4-16), grid 4x1 / 4x2 / 4x4, cell 256 px; colour bleed 4 px into transparent pixels; frame 0 = poster.
3. Sheets: every frame in colour (token tint on #061623 and on a board crop from our UE frame) and in gray; a timing
   strip with ms under each frame; a reduced-motion poster (single frame).
4. verification.json: frame count, cell size, alpha range, maximum sprite count you assume ({{budget}}; system <= 64,
   ash <= 40), tokens used.
Deliverable: {{deliverable}}. Do: {{do}}. Do not: {{dont}}. Acceptance: {{acceptance}}.
```

**Самопроверка:** красного нет, кроме знака X; удар — `#FFB45C` и белая вспышка, не красный (02 §9.3); лечение
без зелёной заливки фигуры, «+N» в капсуле; вихрь Medusa без зелёного; длительность ≤ 600 мс.

**Запреты:** реалистичный дым и огонь; паки NoAI; кадры DE и их кляксы; текстуры чужих паков как вход генерации.

### 1.8 T-CODEX-ENVPLATE — плита Marmoreal

**Цель.** Чистая плита `marmoreal-v1` для вклейки `kind=paste` (ВР-53, ВР-54): без нарисованных фонарей и серых
пешек, с достройкой краёв и ×2. Плюс маски анимации (ВР-55). UE-работа ENV-U16 — только по слову пользователя
(AGENTS.md); плита и маски слова не требуют (бриф §6).

**Входы:** `scraped-data/derived/concepts/env-v1/marmoreal-v1.png` (концепт C0, вне git);
`tools/art/concept_paste/marmoreal.paste.json` (координаты, прямоугольник поля); `scraped-data/images/maps/marmoreal.png`
(только для маски поля); кадры K1 ×0,65 и K2 нашего клиента; [ENV-CONCEPT-PASTE.md](../../art-pipeline/ENV-CONCEPT-PASTE.md).

```text
Task {{id}} — {{title}}. Priority {{priority}}.
[[B-PACKAGE]] All images of this task go to scraped-data/derived/{{set}}-codex/ (they derive from the concept).
Goal: a clean painted backdrop plate around the Marmoreal board field. The field itself is always the real board
illustration placed by the game; the plate's field area is never shown.
1. Field mask: from marmoreal.paste.json mark the board field rectangle plus 2% margin; keep it neutral #808080 in all
   edits so no generator redraws the board.
2. Clean plate (image edit, input = concept C0): "Remove only these painted elements: {{states}}. Fill the removed
   areas with the surrounding painted ground, stone and foliage, matching brush texture, light direction and colour
   of the existing painting. Keep everything else pixel-identical. Painted night scene, cold blue-grey moonlight from
   the west, warm lantern pools stay where listed in {{keyframes}}. No new objects, no figures, no text. [[B-FORBID]]"
3. Outpaint: extend every edge by at least 15% of its side so the K1 x0.65 view needs no edge clamping: "Extend the
   painting outward seamlessly: same perspective, same palette, same painterly texture, terrain continues naturally,
   darker toward the frame edges, no new landmarks, no water."
4. Detail x2: only if the edit tool keeps the painting; otherwise hand off to T-SYNTX-UPSCALE (Claude decides).
5. Masks, same size as the plate, 8-bit gray: lantern flicker regions (painted lights that stay), sakura crowns
   (UV distortion), ground fog band near the cliff, petal emission area. Names: <plate>-mask-<name>.png.
6. Sheets: C0 / clean / outpaint, full and K1 x0.65 crop and K2 crop, colour and gray; a diff map of changed pixels
   outside the listed regions (must be near zero).
Deliverable: {{deliverable}}. Budget: {{budget}}. Acceptance: {{acceptance}}.
```

**Самопроверка:** вне перечисленных областей изменённых пикселей ≤ 1 % (карта diff); воды нет; фонари и пешки,
перечисленные в `{{states}}`, убраны; поле не перерисовано; край на K1 ×0,65 не растянут.

**Запреты:** 3D-окружение P5c как основа; de-lit и рельеф (ВР-53); любые картинки плиты в `art/imagegen/`.

### 1.9 T-CODEX-ANIMSHEET — схема поз и таймингов

**Цель.** Одна страница на клип или постановку: фазы по времени, ключевые позы силуэтом, события CUE. Источник чисел —
02 §8.3, §8.4, §9.2 и `{{timing}}`. Новых клипов нет (ВР-14); поворот и наклон процедурные.

```text
Task {{id}} — {{title}}. Trigger: {{trigger}}. Timing: {{timing}}. Keyframes: {{keyframes}}.
[[B-PACKAGE]]
No image generation of characters. Pose silhouettes are traced by script from OUR renders of the v2 figures
({{inputs}}: Blender previews or UE frames of SK_KingArthur_H2LD, SK_Merlin_H2LD, SK_Medusa_H2LD, SK_Harpy_H3LD on a
neutral background). UE frames with the board in them go to scraped-data/derived/{{set}}-codex/ only.
Sheet layout 1920x1080, background #061623, text Roboto Bold Condensed / Regular:
- top: time axis in ms and, for clips, frames at 24 fps; phases as bars with labels from {{keyframes}};
- middle: 4-6 key poses as flat silhouettes (card.cream fill, #111317 keyline) with the camera direction arrow;
  facing rules: idle three-quarter to the camera (<= 45 deg off the camera axis), turn to the target 120 ms before the
  lunge, return in 150 ms, never back to the camera; step tilt 10 deg, no hop, ease 80 ms at path ends;
- bottom: CUE events on the same axis (contact notify, flash 70 ms, damage number +60 ms, HP +80 ms), the
  reduced-motion variant and the speed variants x0.5 / x1 / x1.5 / none.
Every number on the sheet must appear in {{timing}} or in docs/game-design/visual/02-visual-design.md 8.3-8.4, 9.2;
list the source of each number in README.
Deliverable: {{deliverable}}. Acceptance: {{acceptance}}.
```

**Самопроверка:** сумма фаз равна длине клипа из 02 §8.4 (±1 кадр); контакт на кадре профиля; нет поз «спиной к
камере» и «падения на колени»; нет чисел без источника.

## 2. SYNTX

### 2.1 Когда SYNTX, а не Codex (ВР-PR03)

- Codex идёт первым (подписка). SYNTX — когда Codex не может: видео-референс движения, правка плиты с опорой при
  размере > 1024, апскейл своей плиты.
- Только по готовой карточке; сначала 1–2 варианта, потом доработка лучшего (бриф §5.3), не больше 2 повторов.
- Перед первой генерацией модели — строка в журнале: ссылка на условия провайдера и дата проверки (ВР-05).
  Коммерческих прав не заявляем. П. 9.3 оферты SYNTX запрещает автоматизацию без письменного разрешения; риск принят
  пользователем 2026-10-05 («Агент должен генерировать сам все permissions у него есть»).
- Вход генерации — только наши файлы: кадры нашего клиента, наши концепты, рендеры v2. Сканы карт, аватары, рубашки,
  иллюстрация карты (поле залить `#808080`) и кадры DE в SYNTX не загружаются (ВР-48, ВР-PR08).
- Сырые ответы SYNTX (в них id аккаунта и приватные URL) — вне репозитория, в `C:/tmp/visual-syntx/{{id}}/`; в
  репозиторий — только результат и записи без id (как `tools/art/syntx_video_refs/import_runs.py`).

### 2.2 Модели и цены (замер 2026-10-06)

Источник — MCP `syntx-ai`: `list-ai-services`, `list-models`, `get-model-info` (параметры цены — через
`tools/art/syntx_video_refs/patch.cjs`). Баланс при замере цен 2026-10-06 (утро) — 210,131 токена (`get-balance`); последний известный — **173,771** (2026-10-06 05:40, последняя строка старого журнала, траты звука). Цена — токены за
одну генерацию. «—» — цену получить не удалось, перед запуском спросить снова.

| Семейство | `ai_name` / `model_type` | Параметры цены | Токены | Роль у нас |
|---|---|---|---|---|
| Nano Banana 2 | `banana` / `banana3` | `image_size` 1K / 2K / 4K | 2 / 3 / 4 | **основная** правка плиты с опорой (до 14 картинок) |
| Nano Banana 2 Lite | `banana` / `banana3_light` | 1K (2K нет) | 1,3 | дешёвые пробы правки |
| Nano Banana Pro | `banana` / `banana2` | 2K | 2 | запас к `banana3` |
| GPT Image 2 | `sora-images` / `gpt-image-2` | `quality` 1K, `details_quality` medium / high; 2K high | 2 / 8; 14 | эскизы формы, если Codex недоступен |
| Seedream 5.0 Lite | `seedream` / `seedream-5` | — | 2 | правка с сохранением нетронутых зон (альтернатива) |
| Seedream 5.0 Pro | `seedream` / `seedream-5.0-pro` | `resolution` 1K / 2K, batch 1 | 3 / 6 | плита 2K, если `banana3` не держит живопись |
| FLUX Kontext Pro / Max | `flux` / `flux-kontext-pro`, `-max` | — | 1,5 / 3 | правка по одной опоре |
| FLUX 1.1 Pro Ultra | `flux` / `flux-pro-1.1-ultra` | — | 2,5 | кадр стиля из текста |
| Kling 2.5 i2v | `kling` / `kling_image2video` | `version` 2.5, `mode` standart, 5 с, без звука | 6 | **основной** видео-референс (проверен 2026-09-28) |
| Kling 2.6 i2v | то же, `version` 2.6 | 5 с | 14 | только если 2.5 не держит фигуру |
| Kling Keyframes | `kling` / `kling_keyframes` | 2.1 standart 5 с; 2.5 только `hd` | 21; 17 | старт и конец позы заданы картинками; по карточке |
| Seedance 1.0 Pro-Fast | `seedance` / `seedance_pro-fast` | 480p / 720p, 5 с | 6 / 10 | альтернатива Kling |
| Seedance 1.5 Pro | `seedance` / `seedance-1.5-pro` | 720p, без звука, 5 с | 7,5 | альтернатива 720p |
| Hailuo 2.3 Fast | `hailuo-minimax` / `hailuo-2.3-fast` | 768p, 6 с | 9 | запас |
| Veo 3 Fast | `veo3` / `veo3fast` | 8 с | 19 | не используем: дорого, звук всегда |
| Magnific Precision v1 / v2 / Creative | `magnific` / `precision_v1`, `precision_v2`, `creative` | 2048×1152, `scale_factor` 2x | 12 | **основной** ×2 своей плиты: `precision_v2` |
| Clarity | `clarity` / `clarity` | 2048×1152, 2x | 1 (подозрительно низко) | запас; переспросить цену с реальным размером |

Не используем (замер 2026-10-06): Banana 1,5; GPT Image 1.5 — 2; Seedream 4.5 — 2; Ideogram 1,5; GPT Image 2.5
Flare / Sunburst — цена не получена; Topaz — только видео. Цены 2026-09-28
([manifest.json](../../art-pipeline/animation-refs/manifest.json)): Wan 2.6 i2v Flash 720P 10, Runway Gen-4 Turbo 14,
Veo 3.1 Lite 13. На 2026-10-06 `veo-3.1-lite` и `wan2.6-i2v-flash` в `get-model-info` не найдены, Runway не
опрашивался — до нового замера не используем.

### 2.3 Лимиты (ВР-04, ВР-PR04)

- SYNTX до 2026-10-28 — не больше 300 токенов (ВР-04), но фактический потолок — баланс: последний известный **173,771** (2026-10-06 05:40). Перед каждым запуском — свежий `get-balance`.
  Баланс общий с аудио-чатом.
- Стоп, если баланс перед запуском < 20 токенов.
- Потолок одной генерации без особой строки в `budget` карточки: картинка ≤ 8, видео ≤ 10, апскейл ≤ 12.
- Цена спрашивается перед каждым запуском (`get-model-info`); если она выше потолка — запуск отменяется.

### 2.4 Общая форма вызова

Порядок на карточку `{{id}}`: `create-chat` (чат на карточку) → `upload-files` (только `{{references}}`) →
`get-model-info` (цена; выше потолка — отмена) → `get-balance` → `generate-image` / `generate-video` с `n 1` →
`wait-for-response`, скачать в `C:/tmp/visual-syntx/{{id}}/raw/`, скопировать в путь результата → `get-balance` →
строка журнала (§4).

Сид: `generate-video` принимает `seed`, если модель его поддерживает; у картинок — только через `model_settings`.
Если модель сид не принимает — `seed: null`.

### 2.5 T-SYNTX-IMG-BANANA — правка плиты с опорой

Настройки: `ai_name banana`, `model_type banana3`, `image_size 2K` (3 токена), `n 1`, `aspect_ratio` как у входа,
вход — до 4 опор: плита, маска поля, кадры K1 и K2 нашего клиента, обрезанные до задника, поле залито `#808080`.

```text
Edit the first image only. It is a painted night backdrop around a board game table area. {{purpose}}.
Change only: {{states}}. Keep composition, perspective, palette, painterly brush texture and lighting of the original
painting. Cold blue-grey moonlight from the left, warm small lantern pools only where they already exist and are
listed: {{keyframes}}. The grey rectangle is a placeholder: leave it exactly grey and untouched.
No new objects, no characters, no text, no water. [[B-FORBID]]
```

### 2.6 T-SYNTX-IMG-SEEDREAM — правка с сохранением нетронутых зон

Настройки: `ai_name seedream`, `model_type seedream-5` (2 токена) или `seedream-5.0-pro`, `resolution 2K` (6),
`n 1`. Промпт — как §2.5, плюс строка «Preserve every area that is not mentioned, pixel for pixel». Используется,
если у `banana3` вне областей правки больше 1 % изменённых пикселей.

### 2.7 T-SYNTX-IMG-GPT и T-SYNTX-IMG-FLUX — эскизы и кадр стиля

- GPT: `sora-images` / `gpt-image-2`, `quality 1K`, `details_quality medium` (2), `n 1`. Только когда Codex недоступен.
  Промпт — пункт 1 из T-CODEX-2D или T-CODEX-VFX без изменений. Результат — эскиз; финал рисует движок v3 или скрипт.
- FLUX: `flux-kontext-pro` (1,5) — правка по одной опоре; `flux-pro-1.1-ultra` (2,5) — кадр стиля из текста, только
  для внутреннего ревью:

```text
Style frame for {{title}}: {{purpose}}. [[B-STYLE]] Palette: {{palette_tokens}}.
Composition: {{keyframes}}. Plain background #061623. [[B-FORBID]]
```

### 2.8 T-SYNTX-VID-KLING — видео-референс движения

Настройки: `ai_name kling`, `model_type kling_image2video`, `model_settings {version: "2.5", mode: "standart",
video_duration: 5, native_audio: false}` (6 токенов), `aspect_ratio 1:1` или как у входа, `n 1`. Вход — одна картинка:
наш рендер v2 фигуры на нейтральном сером фоне, фигура крупно, с подставкой. Для двух поз — `kling_keyframes` 2.1
standart (21), только если это записано в `budget` карточки. Образец — `tools/art/syntx_video_refs/gen.sh`
(цена до запуска, `SYNTX_MAX_COST`, `DRY_RUN`).

```text
Locked-off static camera, no camera movement, no zoom, no pan, no cuts. Full-body view of the painted collectible
miniature figure {{title}} come to life, standing on its round base; the entire body and base always in frame.
Motion: {{keyframes}}. Total motion fits in {{timing}}, then the figure returns to its calm standing pose.
Feet stay planted on the base unless the motion says otherwise. Plain neutral grey studio background, even soft
lighting, clean silhouette, no motion blur, no extra limbs, no extra characters, no text.
Do: {{do}}. Avoid: {{dont}}.
```

Для VFX и окружения (вход — кадр Codex с формой эффекта или кроп плиты):

```text
Locked-off static camera. Flat 2D animation of the shapes in the image: {{keyframes}}, total {{timing}}.
Shapes stay flat with hard edges and keep their colours; no smoke, no glow, no lens flare, no camera shake,
no new objects. Background stays unchanged.
```

**Результат:** `art/animation-refs/{{id}}/<id>_<model>_ref.mp4`, `prompt.txt`, `contact-sheet-2fps.png`, `analysis.json`
(как у `MED-LungeAttack`). Видео — только референс тайминга и позы: в UE не импортируется, ассетом не считается
(ВР-PR11).

### 2.9 T-SYNTX-VID-SEEDANCE — альтернатива

Настройки: `seedance_pro-fast`, `resolution 480p`, 5 с (6) или `seedance-1.5-pro`, `720p`, `generate_audio false`
(7,5). Промпт — как §2.8. Брать, если Kling 2.5 дважды ломает фигуру (лишние конечности, сдвиг подставки).

### 2.10 T-SYNTX-UPSCALE — ×2 своей плиты

Только для наших сгенерированных плит и масок (ВР-48). Сканы карт, аватары, рубашки и иллюстрацию карты не
апскейлим никогда.

Настройки: `ai_name magnific`, `model_type precision_v2`, `scale_factor 2x`, `width`/`height` — размер входа
(2048×1152 → 12 токенов; цену спросить с реальным размером). Поле карты на входе залито `#808080` (маска §1.8 п. 1).
Creative-режим не используем: он дорисовывает новое. Промпт, если модель его принимает:

```text
Upscale 2x. Preserve the painting exactly: same shapes, same brush texture, same colours. Do not add details,
objects or text. Keep the grey placeholder rectangle flat grey.
```

**Самопроверка апскейла:** SSIM уменьшенного обратно результата к входу ≥ 0,95; серый прямоугольник остался серым.

## 3. Tripo и Blender (после MVP)

Ростер после MVP вне объёма (ВР-18). Шаблоны — только заготовка под шаблон пайплайна 02 §8.6. До слова пользователя
о новом герое не используются. Лимит Tripo — ≤ 3000 кредитов до 2026-10-28 (ВР-04).

### 3.1 T-CODEX-HEROVIEWS — концепт героя (шаг 1)

Входы: данные героя из `scraped-data/api/heroes/<slug>.json` и БД (имя, оружие, помощники) — текстом; канон
`art/imagegen/hero-quality-v1/<hero>/prompts.md`. Аватар и сканы в генератор не подаются (ВР-PR08).

```text
Original concept of the collectible painted miniature {{title}} for a board game, in the canon of our
hero-quality-v1 figures: matte painted miniature on a round black base, height ratio {{budget}}.
Three orthographic views on one sheet: front, side (facing left), back; same costume and the same weapon hand in
every view. Neutral grey background, even light, no text. Team colour only on cloth accents (hem, belt, lining,
ribbon), never on skin or the whole costume. [[B-FORBID]]
```

### 3.2 T-TRIPO-PART — модель по частям (шаг 2)

Tripo Studio, DCC Bridge, «из нескольких видов в модель», по одной части (тело, голова, оружие, подставка).
Перед запуском — цена в UI, после — строка журнала (§4). Выход — GLB частей вне git
(`art/pipeline-candidates/<ASSET-ID>/`).

### 3.3 T-BLENDER-FIG — сборка, риг, клипы (шаги 3–4)

Чек-лист: риг `UM_HUMANOID_17_v2` ([RIG-CONTRACT](../../art-pipeline/rig/RIG-CONTRACT.md)); MatID UM v1, маска
TeamAccent; слоты материала ≤ 3; 4 клипа D-11 24 fps с notify `Contact`, длины ±0,05 с, RM ≈ 0; сокеты `Weapon`,
`Head`, `Root`, `Base` ([PIPELINE.md](../../art-pipeline/PIPELINE.md)); проверка `mesh_report.py`.

## 4. Журнал трат

### 4.1 Файл

Единый журнал визуала — `docs/game-design/visual/credits-ledger.json` (ВР-PR06). Его создаёт агент плана
(`05-production-plan.md`); этот документ задаёт только схему. Запись — сразу после каждой траты, до следующей.

Старые журналы он **не заменяет** и в них не пишет:
- [s3-baseline credits-ledger.json](../../art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json) — общая
  история SYNTX и Tripo до 2026-10-05, видео-референсы героев, звук (`AUC-*`); пишут
  `tools/art/syntx_video_refs/ledger_append.py` и `tools/audio/ledger.py`;
- [credits-ledger-env.json](../../art-pipeline/evidence/ENV-MAPS/credits-ledger-env.json) — Tripo трека ENV-MAPS.

Баланс SYNTX общий с аудио-чатом. Поэтому `balance_before` — всегда свежий `get-balance`, а не вычисленный: разрыв
между `balance_after` прошлой строки и `balance_before` новой — чужая трата, её не записываем.

### 4.2 Схема

```json
{
  "schema": "unmatched.visual-credits-ledger/1",
  "owner": "визуальный чат; docs/game-design/visual/07-prompt-templates.md §4",
  "limits": {
    "syntx": {"tokens": 300, "until": "2026-10-28", "source": "ВР-04", "stopBalance": 20},
    "tripo": {"credits": 3000, "until": "2026-10-28", "source": "ВР-04"},
    "codex": {"unit": "пакет", "note": "подписка, токены не считаются"}
  },
  "providerTerms": [{"service": "SYNTX", "model": "Magnific Precision v2", "url": "<страница условий>", "checked": "2026-10-06"}],
  "entries": [{
    "date": "2026-10-07T14:05:00+05:00", "service": "SYNTX", "model": "magnific/precision_v2 2x",
    "template": "T-SYNTX-UPSCALE", "task_id": "EN-03", "units": "1 upscale 2x",
    "quoted": 12, "cost": 12, "balance_before": 173.771, "balance_after": 161.771,
    "service_task_id": "<id генерации>", "seed": null,
    "prompt_file": "docs/game-design/visual/06-tasks/prompts/EN-03.syntx.txt",
    "result_path": "scraped-data/derived/env-u16-marmoreal-codex/marmoreal-extended-2x.png", "status": "ok", "note": ""
  }],
  "totals": {"syntx_spent": 12, "tripo_spent": 0, "codex_packages": 0}
}
```

Пример строки выше — иллюстрация формата, не трата.

Правила полей:
- `task_id` обязателен: трат без карточки нет. `template` — id шаблона этого документа.
- `quoted` — цена `get-model-info` до запуска; `cost` = `balance_before − balance_after`; расхождение > 0,5 — в `note`.
- Балансы — свежий `get-balance` или баланс в UI Tripo, без id аккаунта. `seed` — число или `null`.
- Пути — от корня репозитория или `C:/tmp/...`. `status` — `ok`, `failed`, `refunded`; неудача тоже пишется.

У Codex строка пишется на пакет: `units` — «пакет, N генераций image_gen», `cost` и балансы — `null`.

### 4.3 Скрипт

Агент плана делает запись по образцу `ledger_append.py`: чтение-правка-запись под файлом блокировки, временный файл и
`os.replace`, JSON с отступом 2, `ensure_ascii False`. Ручная правка журнала — только с пометкой в `note`.

## 5. Ревью результата

Один проход в конце (решение пользователя: одно ревью, арт и рамки задачи вместе). Делает Claude до коммита.

### 5.1 Рамки задачи

- `git status --porcelain`: изменены только `art/imagegen/{{set}}-codex/**` и, вне git, `scraped-data/derived/{{set}}-codex/**`.
  Чужие незакоммиченные файлы (бриф §6) не тронуты; `git log` не вырос, индекс пуст.
- `verification.json` → `source_unchanged: true`, `outside_folder: []`. В `unreal/` изменений нет, UE и сборки не запускались.

### 5.2 Файлы и размеры

- Все пути и размеры из `{{deliverable}}` есть; рабочие размеры отрисованы из вектора, не уменьшены из мастера.
- RGBA; поля не касаются края (кроме 9-slice, у него записаны отступы); `manifest-sha256.json` пересчитан и совпал.
- Пакет без `concepts/` — ориентир ≤ 30 МБ; PNG больше 5 МБ — с причиной в README.

### 5.3 Вид и токены

- Каждый финал открыт глазами (Read PNG) в мастере и рабочих размерах: значки — 24 / 32 / 48 px ×4 nearest; скины —
  ×1 и ×2; карты — показы 02 §6.2; HUD — 1080p и 720p, 100 % и 150 %. Цвет и серый для каждого размера; дейтеранопия
  — для пар 02 §11.3. Метрик мало: пользователь о значках v2 — «нарисованы криво», «топорно».
- Hex финалов — только из 02 §2 (`palette` в `verification.json` и выборочно пипеткой). Красный — только знак X или
  «!» и поражение; удар — `#FFB45C`; выбор — `#4CD2DC` / `#0D7A89`; ход — `#F2C14E`.
- Кегли ≥ 14 su, значки в HUD ≥ 24 su, контраст текста ≥ 4,5 : 1, значков и кромок ≥ 3 : 1.
- Мазка кисти, брызг туши, бликов, градиентов, камня и металла нет (ВР-01, ВР-09, ВР-19).

### 5.4 Реальные данные

- Каждое имя, число, карта, аватар и доска на макете прослеживаются до входа в `manifest` (путь и sha256).
- Доски — только Marmoreal или Sarpedon original; фигуры — шесть v2; задник Marmoreal — вклейка, Sarpedon — lit3d.
- Нет ImageGen и SYNTX на макетах с игровыми данными, сканах и аватарах.
- «Уточнить» вместо выдуманных значений — допустимо, выдумка — отказ пакета.

### 5.5 DE

- Входы генерации (`generation-records.json` → `references`) — не кадры, не ассеты и не файлы DE.
- Нет узнаваемых элементов DE: сплэш-арта, кляксы «COMBAT!», мазков, шрифтов, рамок карт. Листы «рядом с кадром DE»
  — только в `C:/tmp/`.

### 5.6 Права и траты

- У каждой генерации SYNTX и Tripo есть строка в `credits-ledger.json`; сумма за пакет не выше `budget` карточки.
- Записаны модель, ссылка на условия провайдера и дата (ВР-05). Коммерческих прав в README не заявлено.
- Сканы карт и аватары — с пометкой «только внутренняя LAN-сборка» (ВР-48, GAP-019).
- Паки NoAI не открывались; SoftTofu, если использован, — с атрибуцией в `CREDITS-fab.md`.

### 5.7 Решение и коммит

- Итог ревью — строка в README пакета («ревью Claude, дата, что принято, что нет») и статус в реестре 03:
  «предложено» → «художественно принято, по делегированию» только после листа приёмки 02 §13.2.
- Коммит — `git commit --no-verify` перечислением путей пакета, без push. Картинки из `scraped-data/` в коммит не
  попадают.
- Импорт в UE, флаг отката и кадр — отдельные шаги плана 05, не часть пакета.

## 6. Решения этого документа (по делегированию)

Все решения — по делегированию (пользователь 2026-10-06: «Все решения принимай»). Серия `ВР-PR` — локальная серия
этого документа (02 §0.3). До ревью 2026-10-06 она называлась `ВР-07.N` и путалась с ВР-07 (именные плашки).

| ВР | Решение | Почему |
|---|---|---|
| ВР-PR01 | Codex пишет во вторую папку `scraped-data/derived/{{set}}-codex/` всё, где есть сканы карт, аватары, рубашки, иллюстрация карты или концепт окружения. В своей папке — скрипты, промпты, записи, листы без них | ENV-U3 и ВР-48 держат производные скрапа вне git; договор «только своя папка» иначе невыполним для макетов и рамок |
| ВР-PR02 | T-CODEX-LAYOUT и T-CODEX-CARDFRAME — без генерации изображений: только сборка скриптом из реальных входов | Пользователь 2026-10-03 и 2026-10-05: ImageGen не для макетов с игровыми данными |
| ВР-PR03 | Codex первым, SYNTX — только видео, правка плиты > 1024 с опорой, апскейл своей плиты | Codex по подписке; баланс SYNTX ограничен (§2.3) |
| ВР-PR04 | Потолок SYNTX — баланс (последний известный 173,771 на 2026-10-06 05:40) при лимите ВР-04 300; стоп при балансе < 20; потолок одной генерации: картинка 8, видео 10, апскейл 12 | Баланс общий с аудио; лимит ВР-04 физически недостижим |
| ВР-PR05 | Модели по умолчанию: плита — Nano Banana 2 2K (3); запас — Seedream 5.0 Lite / Pro; эскизы — GPT Image 2 1K medium (2); видео — Kling 2.5 standart 5 с (6), запас — Seedance 1.0 Pro-Fast 480p (6); ×2 — Magnific Precision v2 | Самые дешёвые из подходящих по замеру 2026-10-06; Kling 2.5 уже проверен на героях 2026-09-28 |
| ВР-PR06 | Один журнал визуала `docs/game-design/visual/credits-ledger.json`; в старые журналы не пишем; баланс до и после — свежий `get-balance` | Баланс общий с аудио; двойная запись ломает суммы старого окна |
| ВР-PR07 | В промптах генерации нет названий «Unmatched», «Digital Edition», художников и студий | Название тянет генератор к арту DE (ВР-09, START-PROMPT «её арт не копировать»); промпт DE-012 содержал «Digital Edition inspired» |
| ВР-PR08 | Вход любой генерации — только наши файлы; кадры, ассеты и файлы DE, сканы карт, аватары, рубашки и иллюстрация карты в генераторы не подаются (поле на кадрах и плитах залито `#808080`) | ВР-09, ВР-48; DE — только идеи и тайминги |
| ВР-PR09 | Заполненное задание лежит в `docs/game-design/visual/06-tasks/prompts/<id>.codex.md` или `<id>.syntx.txt`; колонка `prompt` карточки — путь к нему | Образец DE-012 лежал в `C:/tmp` и потерялся бы; задание — часть истории решения |
| ВР-PR10 | Флипбук VFX — белая маска с прямой альфой, цвет — параметр материала из токена `fx.*`; 30 кадров/с, 4–16 кадров, ячейка 256 px, расширение цвета 4 px | Точные hex держит материал, а не текстура; один флипбук служит нескольким CUE |
| ВР-PR11 | Видео SYNTX — только референс тайминга и позы, в UE не импортируется; лежит в `art/animation-refs/<id>/` | D-11 без новых клипов (ВР-14); как у видео-референсов 2026-09-28 |

## 7. Открытые риски

- П. 9.3 оферты SYNTX: генерация через MCP — автоматизация; риск принят пользователем 2026-10-05, письменного
  разрешения SYNTX нет.
- Условия провайдеров (Kling, Google, ByteDance, BFL, Magnific) через агрегатор не проверены; ссылки и даты нужны в
  журнале до первой траты (ВР-05).
- Цена Clarity (1 токен за 2048×1152 ×2) выглядит ошибочной; без повторного замера не использовать.
- `banana3_light` не принимает 2K; `gpt-image-2.5-*` и Veo 3.1 Lite / Wan 2.6 / Runway цену не вернули — считать
  недоступными.
- Codex image_gen не держит hex и толщину штриха (README DE-012): финал всегда рисует скрипт; ревью проверяет это.
