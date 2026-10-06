# CP-14 — рамка карты в теме и материал лица M_UmCardFace

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `cards-portraits.csv` CP-14; 02 §4.2, §6.1, §6.3;
04 §4.1, §4.4; HUD-RULES П3, П9. Пакет рамки — CP-13 `art/imagegen/card-frame-v1-codex` (принят по делегированию,
ВР-VS2-CP-01…09). Виджет — [CP-15](../CP-15/README.md).

**Статус:** технически импортировано; лист готов. Коммиты `f24ca3c1` (импорт, материал) и `b7bf24ac` (ВР-VS3-16). Строки реестра 03 `T_UmCardFrame_*` переводятся в
«художественно принято, по делегированию» после единого прохода ревью VS-3 (ВР-VS2-CP-09) — в основной копии после
интеграции (ВР-PL09).
**Откат:** `-S08CardArtLegacy`. Без темы и материала виджет рисует скруглённые кромки токенов и лицо без обесцвечивания.

## Что сделано

| Пункт `do` | Где |
|---|---|
| 1. `M_UmCardFace` (UI, Translucent): Face, UVRect, Desaturation (Rec.709), Opacity; без света | `tools/art/cards/ue_card_face_material.py` (по образцу `M_UmPortraitDisc`): один Custom-узел, **одна** выборка текстуры её же сэмплером (mip, трилинейный), `lerp(rgb, dot(rgb, (0.2126, 0.7152, 0.0722)), Desaturation)`, `alpha × Opacity`. `--check` сверяет имена параметров с `UmCardWidget.h`. Отчёт `art/cards-v1/card-face-material-report.json`. Ассет `git add -f`. |
| 2. `--frames` → `/Game/S08/UI/Skins/CardFrame/T_UmCardFrame_<state>_{x1,x2}` | `ue_import_card_media.py --frames` (и в конце `--all`): `TC_EDITOR_ICON`, без mip, `TEXTUREGROUP_UI`, sRGB, bilinear, без стриминга. Состояния: idle, hover, selected, warning, flash, focus, mini_idle и new_dot — 16 текстур (ВР-VS3-04). Все ≤ 16 КБ (бюджет 64 КБ). `git add -f`. Отчёт `art/cards-v1/card-frame-import-report.json`. |
| 3. Поля 9-slice из `verification.json` CP-13 → кисти темы; x2 при DPI × UIScale ≥ 1,333 (уточнено ВР-VS3-16: от 2,0) | `DA_UmHudTheme.CardFrames` / `CardFramesX2` (ВР-VS3-03), ключи `card.frame.idle`, `.hover`, `.selected`, `.warning`, `.flash`, `.focus`, `.mini`, `.new`; `UUmHudTheme::ImportCardFrame`, `CardFrameFor(key, px/su)` (x2 от 2,0 px/su, ВР-VS3-16). ImageSize — пиксели ×1 в su (460×640, focus 468×648, мини 48×67). Углы ×1: 11 / 13 / 12 / 12 / 13 / 7 px (≤ 13). `hud_theme_import.py` после сброса темы снова вызывает `bind_frames`. |
| 4. Рамки — наш арт: `git add -f` | 16 `.uasset` в коммите `f24ca3c1`. |
| 5. G-TOKENS: hex кромок = токены (ΔE76 ≤ 3) | pytest `test_card_frames.py::test_frame_pngs_use_only_token_colours`: все непрозрачные пиксели 16 PNG — в пределах ΔE76 ≤ 3 от шести токенов; окно рамки прозрачно. `hud_contract.py validate` — PASS. |
| 6. UE-тест `Unmatched.S08.Hud.Card.Material` | Параметры есть; домен UI, translucent; Custom-код с весами Rec.709 и одной выборкой; у карты UVRect = (0, 0, 287/512, 398/512) — паддинг не виден; «нельзя сыграть» → Desaturation 0,6, Opacity 0,7; 7 рамок ×1/×2 с полями пакета; точка — `Image`; 29 токенных скинов не тронуты. |

## Решения шага

- **ВР-VS3-03:** рамки — в отдельных картах темы (см. CP-15).
- **ВР-VS3-04:** точка «новая» — 15-я и 16-я текстуры (см. CP-15).
- **ВР-VS3-05.** Число инструкций пиксельного шейдера коммандлет не отдаёт: `get_statistics` возвращает 0 и под
  `-nullrhi`, и с RHI, как и у `M_UmPortraitDisc` в VS-2. Бюджет «≤ 25 инструкций, 1 выборка» поэтому проверен по
  построению. В материале:
  - одна выборка текстуры (pytest и UE-тест считают `Texture2DSample`);
  - один `dot`, два `lerp`, одно умножение;
  - нет света и бликов.
  Замер на GPU войдёт в бюджет HUD шага «Кадры» (`render_bench.py`).

## Листы

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-14/face-material-sheet.png` — sha256 `ed849d378c4239e3…`
- `CP-14/frames-p12-1080-100.png` — sha256 `40bffabc1ba52e47…`
- `CP-14/frames-p12-720-100.png` — sha256 `5e75327e2091f43f…`
- `CP-14/frames-p12-1080-150.png` — sha256 `78f3e81cd9a770b2…`
- `CP-14/frames-p13-1080-100.png` — sha256 `19f07df20e25c783…`
- `CP-14/frames-p13-1080-150.png` — sha256 `f3e52b576f05988a…`
- `CP-14/frames-p13-1440-150.png` — sha256 `8088f1f0bf632b26…`

Что видно (Read; углы рамок увеличены ×6 nearest — `C:/tmp/visual/VS3-U1/zoom-frame-corners-*.png`,
`cmp-150-x2-vs-x1*.png`):
- Материал. Скан 1 : 1, 0,52× (рука) и 0,11× (фишка 32×45) — без муара и ступенек: mip и трилинейный фильтр.
  «Нельзя сыграть» (Desaturation 0,6, Opacity 0,7) в цвете и в сером заметно бледнее нормы, подложка видна сквозь скан.
- Рамки при 150×208 и 230×319:
  - кромка не растягивается, угол целый;
  - idle (1 su, cream 0,45), hover (cream 1,0), selected (teal 3 su), warning (оранжевый 2 su), flash (белый 2 su),
    focus (кольцо снаружи с зазором);
  - в сером selected толще idle, warning и flash различаются яркостью (ВР-VS2-CP-05);
  - мини — только mini-idle.
- Инспектор RU 460×640 / EN 408×566 при 1080p 100 % — без кэпа: scale 1,575 / 1,599. При 1080p 150 % и 1440p 150 %
  карта уменьшена до 1,6× (`capped=1`, 238×331 / 208×289 su при 2 px/su).
- **ВР-VS3-16** (по делегированию; уточняет CP-14 п. 3 «x2 от 1,333»). На первом прогоне при 1080p 150 % (1,5 px/su)
  x2-текстура рисовалась с уменьшением 0,75 без mip. Полупрозрачная дуга угла idle легла неровно: в верхнем левом
  углу появилось яркое пятно. x1 с увеличением 1,5× ровный. Поэтому x2 берётся от 2,0 px/su: 1440p 150 % и 4K, где
  x2 рисуется 1 : 1 или крупнее.
  - Кадры до и после: `C:/tmp/visual/VS3-U1/cmp-150-x2-vs-x1.png`; листы `frames-p12-1080-150` сняты уже после правки.
  - Проверено: тест `Card.Material`, `UUmHudTheme::CardFrameX2MinPxPerSu = 2.0`.
