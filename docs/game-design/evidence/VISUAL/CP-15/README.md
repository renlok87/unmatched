# CP-15 — виджет карты UUmCardWidget (общий отчёт шага U1 VS-3: CP-15…CP-20)

VS-3, шаг U1, 2026-10-07, ветка `feat/visual-vs3` (worktree `C:/tmp/wt-visual`). Карточки — `cards-portraits.csv`
CP-15…CP-20; 04 §2.6–§2.9, §1.7, §4.1–§4.3; 02 §6.1–§6.3. Здесь — общее для шести карточек виджета: код, решения,
проверки, листы. README CP-16…CP-20 ссылаются сюда и добавляют своё.

**Статус:** виджет, WBP, состояния, трасса, тесты и листы галереи готовы (коммиты `67a57467`, `b7bf24ac`). Владельцев виджета в
партии ещё нет: руку (HB-24, H7), бой у края (HB-30…HB-33, H9), слот (H10), колоду (HB-27/HB-28, H8) и инспектор
(CP-21/CP-22, H13) подключают следующие шаги VS-3 / VS-4. Поэтому приёмочные кадры наборов A, C, D, E в партии
(packaged `-Bench`, обе доски, шесть фигур v2) — после них, в шаге «Кадры». Приёмка «по делегированию» — в едином проходе
ревью VS-3.
**Откат:** `-S08CardArtLegacy` (ВР-CP08): всегда фолбэк лица 02 §6.1, рубашка — плашка card.navy с `resource-card` 24 su;
трасса `tex=legacy`, `ARTLOOK cards=legacy(-S08CardArtLegacy)`. Блоки — `-S08SlateHud=hand,combat,slot,inspect` (у
владельцев, когда они придут).

## Что сделано (CP-15)

| Пункт `do` | Где |
|---|---|
| 1. `UUmCardWidget`, BindWidget, `BuildDefaultTree`, `ApplyModel(FS09CardView, FUmCardState)`, `CollectShotLines` | `S08/UI/UmCardWidget.{h,cpp}`. Дерево: `Box` (размер показа) → `Card` (размер после кэпа, опора — низ по центру) → `Layers`: `FocusRing`, `Underlay`, `Face`, `Fallback`, `PlateIcon`, `Spinner`, `Frame`, `FlashLayer`, `NewDot`, `DropIcon`, `BoostChip` (`BoostIcon` + `BoostText`). `/Game/S08/UI/Common/WBP_UmCard` сгенерирован из того же дерева (`ue_author_um_hud.py`, `UM_HUD_WBP_OVERWRITE=0`: остальные WBP не тронуты), `git add -f`. |
| 2. Ключ `heroSlug:cardSlug`, RU при культуре ru, иначе EN | `UmCardWidget::Slug` / `CardKey` (ВР-VS3-13), `UmCardMedia::FindCard`; `FUmCardState::Lang` — принудительный язык (переключатель инспектора). Смена культуры — в кадр события (`OnCultureChanged`). |
| 3. Contain, подложка, постоянное окно | `UmCardWidget::Fit`: окно = показ − 2 × полоса (4 su, у мини 2 su); скан contain по центру; подложка `card.navy` — `FSlateRoundedBoxBrush` по внутреннему краю keyline (отступ 1 su, радиус r − 1). Рубашка: бока −5 px из 768 (1,30 %), затем contain (`UvRect`, `DrawnSrcPx`). |
| 4. Кэп ВР-CP04 | `Fit(…, PxPerSu, 1.6)`: если скан шире 1,6× источника, карта уменьшается (полоса остаётся 4 su), остаток — отступ по центру в `Box`. Наведение: `HoverScaleFor` ограничивает 1,5 тем же кэпом. |
| 5. Скрытая карта — рубашка героя владельца, лица в модели нет | `ApplyModel` с `bFaceDown` хранит только `InstanceId` (QA-005). |
| 6. Фолбэк 02 §6.1 + Warning | Название из данных `type.heading` (у показов уже 200 su — `type.button`), диск типа `action-*` 32 su (универсальная — два диска, ВР-VS3-07), «Значение N · BOOST N» (`hud.inspect.value` / `.boost`), баннер `type.caption`; нет RU — EN с меткой «EN» (ВР-VS3-06); `Warning: CARD-ART fallback key=… reason=…` один раз на виджет. |
| 7. Трасса ВР-CP10 и гейт | `CARD-ART key=… lang=ru|en|back|fallback tex=… show=… su=WxH px=WxH scale=… capped=0|1 state=a+b… chip=0|1`. `hud_contract.py check-trace`: scale > 1,6 и `lang=fallback` при ключе из реестра — ошибка (`tex=legacy` не ошибка). |
| 8. `-S08CardArtLegacy` | `IsLegacy()` = `!S08ArtLook::CardArt()` (тесты — `SetLegacyForTest`). |
| 9. Пул | `ApplyModel` того же входа ничего не делает; новый вход меняет только кисти и параметры MID. Дерево не пересоздаётся. |
| 10. ВР-CP12 | В git — только листы без сканов и README; листы со сканами — вне git, `scraped-data/derived/visual-evidence/CP-xx/`. |
| 11. UE-тесты | `Unmatched.S08.Hud.Card.Tree`, `.Fit`, `.Cap`, `.Key` (+ `.Material`, `.States`, `.Hover`, `.Boost`, `.Discard`, `.Flip`), `Unmatched.S09.HudPress.Card`. |

Остальное в виджете:
- Загрузка асинхронная (`FStreamableManager`), до готовности — рамка и `loader-spinner` 32 su. Галерея и тесты грузят
  синхронно (`SetSyncLoad`).
- Нажатие — на отпускании через `FS09HudPressArbiter`. Неиграбельная карта отвечает `Refused` со своим `why.*`. ПКМ
  вызывает инспектор владельца. Вход и выход указателя тоже уходят владельцу: подъём и порядок над соседями делает HAND.
  Курсор: `Hand`, у неиграбельной — `SlashedCircle` (HB-12).
- Тема: `UUmHudTheme::CardFrameFor(key, px/su)` берёт x2 от 2,0 px/su (ВР-VS3-16, CP-14).
- Без `M_UmCardFace` (свежий worktree) лицо рисуется текстурой с UV-областью, без обесцвечивания. Без рамок темы —
  скруглённой кромкой токена.

## Решения по делегированию (шаг U1)

| № | Решение | Почему |
|---|---|---|
| ВР-VS3-01 | Slate-столбец портретов строится и при `HUD-ROOT created=0` без `-S08SlateHud` (`UmSlatePortraits::Wanted`) | замечание ревью VS-2: иначе портретов нет вовсе (коммит `d342fe6d`) |
| ВР-VS3-03 | `card.frame.*` лежат в `DA_UmHudTheme.CardFrames` / `CardFramesX2`, а не в `Skins` | 29 токенных скинов HB-08 и тесты HB-10 не меняются; ключи — как в CP-14 |
| ВР-VS3-04 | Точка «новая» — PNG пакета CP-13 (`card-frame-new-dot`), ключ `card.frame.new`, `DrawAs Image`; текстур 16, а не 14 | точка нарисована в том же пакете точными токенами; запасной вид — круг токенов |
| ВР-VS3-06 | Метка «нет перевода» в фолбэке — код языка «EN» (`type.caption`, `text.secondary`), без новой строки ST_Hud | INT-018 п. 3 требует метку, а не фразу; код языка не переводится |
| ВР-VS3-07 | Фолбэк универсальной карты — два диска (`action-attack` + `action-defense`), схема — `action-scheme` | на печатной универсальной карте оба знака; не только цвет |
| ВР-VS3-08 | Наведение в руке — render transform 1,5 карты 150×208 (полоса и кромка тоже ×1,5); показ `Hover` 225×312 с окном 217×304 — для владельцев, которые раскладывают крупную карту | CP-17: «0 перекладок, render transform»; окно CP-13 для 225×312 остаётся верным для разложенного показа |
| ВР-VS3-09 | Чип буста и значок сброса — по центру верхнего края: 16 su над рамкой, 8 su на ней | «у верхнего края по центру» (02 §6.3); название скана закрыто не целиком |
| ВР-VS3-10 | Reduced motion: переворот — кроссфейд лица через подложку 100 мс (50 + 50); вспышка CUE-006 — держится 500 мс, потом idle | CP-18 / CP-20 «кроссфейд 100 мс»; CP-13 «статическая вспышка» |
| ВР-VS3-11 | Приватность: лицо раскрытой карты приходит только в `Flip(true, …, Face)` и назначается в кадр ребра; текстура может догружаться в первой половине переворота, но в виджет не ставится; `CARD-ART` не пишет ни значений, ни числа чипа (`chip=0|1`) | CP-18, CP-20, QA-005 |
| ВР-VS3-12 | Модель главнее анимации: `ApplyModel` с другим лицом обрывает идущий переворот; после раскрытия владелец подаёт раскрытую карту `bFaceDown=false` | переподключение и новый снапшот не оставляют виджет на полпути |
| ВР-VS3-13 | Слаг: правило CP-15 + схлопывание повторных «-» и обрезка краёв | совпадает с ключами реестра `ue_import_card_media.py` |
| ВР-VS3-14 | Листы CP-03…CP-20 — кадры галереи движка `-S08IconGallery -S08IconGalleryCards=<1…19>` (editor `-game`, один клиент, 30 FPS), не офлайн-композиты; ячейка «1,0×» материала — картинка MID в пикселях источника | как ВР-VS2-69: проверяется то, что рисует UE (mip, фильтр, 9-slice) |
| ВР-VS3-15 | Первый `-game` после создания `M_UmCardFace` компилирует шейдер: лица в этом кадре пусты. Листы сняты на прогретом DDC, в упаковке шейдер готовится в куке | наблюдение первого прогона галереи (стр. 14) |
| ВР-VS3-16 | x2-рамки `card.frame.*` — от 2,0 px/su (а не от 1,333): ниже x1 с увеличением | при 1,5 px/su x2 без mip уменьшалась 0,75 и давала яркое пятно на дуге угла idle (кадры CP-14) |

## Проверки

- Сборка UnmatchedEditor в worktree — `Result: Succeeded` (лог `C:/tmp/visual/VS3-U1/build-*.log`, ошибок нет). Игровая
  цель `Unmatched Win64 Development` — `Succeeded` (ловушка C2039 не сработала).
- UE: `Unmatched.S08 + S09 + S10` — 430 из 430 (`ue-tests-full-1.log`, до ВР-VS3-16);
  `Unmatched.S08.Hud + Unmatched.S09.HudPress + Unmatched.S08.CardMedia` — 50 из 50 после последней правки кода
  (`ue-tests-hud-4.log`). Логи — `C:/tmp/visual/VS3-U1/`.
- pytest: `tools/art/cards` + `tools/s08/hud_contract` — 97 passed (новые `test_card_decks.py`, `test_card_frames.py`,
  `test_check_trace_card_art_cp15`).
- `hud_contract.py validate` — PASS (G-TOKENS: литералов цвета в `S08/UI` нет), `hud_tokens_codegen.py --check` — FRESH.
- Найдено и исправлено тестом: у покоящейся карты масштаб был 0 (значение «To» пустого твина) — `Card.Hover` теперь
  проверяет «в покое 1».

## Листы (галерея, 1080p 100 % и другие масштабы)

Листы — кадры галереи движка (ВР-VS3-14): `-S08IconGallery -S08IconGalleryCards=<стр.>`, editor `-game`, один клиент, 30 FPS, `-RenderOffScreen`, после того как клиенты ZCode закончили. Каждый лист — цвет | серый Rec.709 | дейтеранопия. Листы со сканами и рубашками — вне git (ВР-CP12), в `scraped-data/derived/visual-evidence/<id>/`; индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-U1-index.json`; скрипты и кадры — `C:/tmp/visual/VS3-U1/` (`run-gallery.ps1`, `run-batch.ps1`, `compose.py`, `trace_check.py`, `gallery/<прогон>/`).

- `CP-15/shows-p14-1080-75.png` — sha256 `d7f0f00b875e6e6c…`
- `CP-15/shows-p14-1080-100.png` — sha256 `947eb53d8ed1a6f8…`
- `CP-15/shows-p14-1080-150.png` — sha256 `2bb52abb95747b77…`
- `CP-15/shows-p14-720-100.png` — sha256 `d7f0f00b875e6e6c…`
- `CP-15/shows-p14-720-150.png` — sha256 `4111d08d49d8a647…`
- в git (сканов нет): [`legacy-hand-1080-100.png`](legacy-hand-1080-100.png) — рука с откатом `-S08CardArtLegacy`
  (sha256 `5b7ba613856881c2…`).

Что видно (все листы открыты, Read):
- Одна карта (Excalibur) во всех показах: hand, hover, combat, slot, deckgrid, hand EN, combat EN, classS-hand,
  classS-combat, мини 48×67 и 32×45. Скан целиком, в одной и той же рамке; окно постоянное.
- Фолбэк без ключа (The Hounds of Mighty Zeus, Divine Intervention):
  - название из данных, метка «EN»;
  - два диска универсальной карты;
  - «Значение N · BOOST N», баннер.
- `legacy face` — тот же фолбэк, `legacy back` — плашка `card.navy` со значком `resource-card` 24 su. Глиф стопки мелкий
  (≈ 16×10 px в экспорте 24), как у фолбэка OPP-HAND HB-21.
- Масштабы: 1080p 75 % и 720p 100 % дают одинаковые пиксели (0,75 px/su), поэтому их листы совпадают побайтно.
- Трассы галереи (`trace_check.py` по последнему построению каждой страницы): 848 строк `CARD-ART` в 34 прогонах,
  ошибок 0.
  - Максимум scale при 1080p 100 %: рука 0,568, наведение 0,756, бой 0,888 (EN-бой 0,888, RU-бой 0,774) — ≤ 1,0.
  - Везде ≤ 1,6. `capped=1` только при 150 % и 1440p 150 % (12 строк инспектора).
  - Сводка — `C:/tmp/visual/VS3-U1/card-art-summary.json`.
