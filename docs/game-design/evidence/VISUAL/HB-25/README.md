# HB-25 — рука: сброс по лимиту и выбор BOOST (манёвр, способность King Arthur)

VS-3, шаг U2, 2026-10-07, ветка `feat/visual-vs3`. Карточка — `hud.csv` HB-25; 04 §2.6 (буст, сброс), §2.8; 02 §6.3;
SD-42, SD-43, SD-56; IC-34 П-2; макет HB-22 (состояния drop, boost-maneuver, boost-attack; ВР-VS2-HB22-07, -11).
Блок — `UUmHudHand` из [HB-24](../HB-24/README.md) (общий код, тесты, листы); виджет карты — CP-18, CP-19 (U1).

**Статус:** режимы Discard и Boost, трасса, тесты и листы галереи готовы (тот же коммит кода, что HB-24). Кадры набора D
(сброс на Marmoreal 1080p 100 % / 720p 150 %, буст King Arthur на Sarpedon) в партии — шаг «Кадры».
**Откат:** `-S08SlateHud=hand` (текстовые фишки с `[DROP]` / `[BOOST]`).

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. Режимы по `FS09DiscardPick` и BOOST_CHOICE | `UmHudHand::Gather`: Discard — сброс по лимиту (`DiscardDraft`) и `DISCARD_CARDS` своей головы; Boost — черновик манёвра, подсказка способности King Arthur (`IsAttackAbilityPromptOpen`, SD-56) и BOOST_CHOICE своей головы (Second Shot, Noble Sacrifice). |
| 2. Discard | все карты — `SetDiscardCandidate` (кромка `card.frame.warning` 2 su); отмеченные — `SetMarkedForDiscard` (−16 su за 150 мс, глиф card-drop IC-36); клик идёт прежним путём (`ToggleDiscardCard` / `TogglePendingCard`), второй клик снимает отметку; отмены у лимита нет (как было). «Подтвердить» — см. ВР-VS3-32. |
| 3. Boost | кандидаты — карты с напечатанным BOOST > 0, прочие — `why.boost.no.value` (вид CP-16 и подсказка); выбранная — `SetFaceDown` + `SetBoostChip(boostValue)` (CP-18) и полёт в слот буста за 150 мс; карта атаки в подсказке King Arthur остаётся выбранной; клик по карте в слоте возвращает её в руку. |
| 4. Строки | `hud.card.boost` «+{n}» — чип (runtime-текст, И-7); `hud.slot.boost` «BOOST» — лента под картой в SLOT; `hud.card.drop` — ВР-VS3-28 (HB-24). |
| 5. `SHOT widget` | `state=discard` (с `mode=discard marked=<n>`); буст — `mode=boost placed=1`. |
| 6. Тесты | `Unmatched.S08.Hud.Hand.Discard`, `.Boost` (`S08/UI/UmHudHandTests.cpp`). |
| 7. Чип ≥ 21 px | `UmCardWidget::ChipSuFor`: 32 su при DPI × UI < 1 (720p 100 %: 24 px), иначе 24 su; цифра растёт с чипом (12 → 16 su). |

## Решения по делегированию (шаг U2)

| № | Решение | Почему |
|---|---|---|
| ВР-VS3-29 | Кандидат буста — BOOST > 0 (карточка); в колодах MVP карт «+0» нет, так что это совпадает с допуском модели (`bHasBoostValue`) | без расхождения клика и подсветки на реальных данных |
| ВР-VS3-30 | Слот буста: манёвр и BOOST_CHOICE вне боя — SLOT (24, 84, 190, 264), S (16, 64, 120, 166), под ним лента BOOST (`marker-status` 24 su + «BOOST», 28 su, зазор 4 su — HB-22), её рисует рука до H10; атака King Arthur и BOOST_CHOICE в бою — размер карты COMBAT-L, сдвиг 40 su (S 32) вправо: (64, 360, 230, 319), S (48, 240, 150, 208), чип справа на 4 su над верхом (ВР-VS2-HB22-11) | одно правило на всех холстах; z под картой атаки — у H9 |
| ВР-VS3-31 | Чип «+N» — 32 su при DPI × UI < 1, иначе 24; 8 su чипа на рамке | IC-34 П-2: «лучше 32 su», при 18 px число не рисуется |
| ВР-VS3-32 | «Подтвердить» сброса и «Сбросьте {n}: выбрано {h}/{n}» остаются в Slate-панели команд до компакта PENDING (HB-36, VS-4); неверное число отвечает её проверка (`ConfirmDiscard`) | рука только отмечает карты (HB-25 `do` 2 ссылается на HB-36) |

## Проверки

- `Unmatched.S08.Hud.Hand.Discard`: 9 карт при лимите 7 — все кандидаты, 2 отмечены (−16 su, card-drop), повторный клик
  снимает, `SHOT state=discard marked=2`, «Рука 9/7»; `DISCARD_CARDS` эффекта — тот же вид.
- `Unmatched.S08.Hud.Hand.Boost`: Dash (+1) уходит рубашкой в SLOT (24, 84) показом 190×264, чип «+1», лента BOOST,
  «Рука 5/7», ряд сомкнулся; снятие — назад лицом; King Arthur: Swift Strike выбрана, Noble Sacrifice — рубашкой в
  (64, 360) 230×319, «+3» справа над краем, «Рука 2/7»; класс S — (48, 240) 150×208; при 0,75 px/su чип 32 su; BOOST_CHOICE
  в бою — у COMBAT-L; карта без BOOST — `why.boost.no.value`.
- `Unmatched.S09.HudPress.UmgHand`: неиграбельная карта с `why.boost.no.value` — 24 отказа из 24 с причиной.
- Вся сборка и общий прогон — в [README HB-24](../HB-24/README.md) (437 из 437).

## Листы

Те же прогоны галереи, что у HB-24 (`scraped-data/derived/visual-evidence/HB-24/`, строки drop, boost-maneuver,
boost-attack; sha256 — там же и в `VS3-U2-index.json`); в git — `../HB-24/plain-legacy-*.png`.

Что видно (Read):
- drop (тестовая рука 9/7): все 9 карт с оранжевой кромкой, две последние опущены на 16 su с глифом над картой; в сером
  отличаются от выбранной формой; 720p 150 % — веер 63,7 su, обе отмеченные различимы.
- boost-maneuver: рубашка Medusa в SLOT, чип «+1», лента «BOOST»; «Рука 4/7» (Marmoreal) / «5/7» (Sarpedon).
- boost-attack: рубашка King Arthur у COMBAT-L, «+3» справа над краем, Swift Strike поднята в руке, «Рука 2/7».

## Что не сделано в этом шаге

- Кадры набора D в партии и трасса `state=discard` живого клиента — шаг «Кадры».
- Карта атаки King Arthur в COMBAT-L (поверх рубашки буста) — блок боя H9 (HB-30…HB-33).
- Компакт «Сбросьте {n}: выбрано {h}/{n}» и «Добавить BOOST?» — HB-36 (VS-4).

## Кадры выхода VS-3 (2026-10-07, упаковка `c9dac400`)

Живая партия двух клиентов `run-combat-demo -PlayerView -S08ExitShots` без `-S09Markers`, по 30 FPS у клиента, на приёмочной упаковке шага (`BuildStamp` `c9dac400`, `sourceHash` `0eaad2a3…`). Доски — Marmoreal original (с `-ConceptPaste` до EN-13, пометка) и Sarpedon original (lit3d), шесть фигур v2 (`v2=6`), слоя отладки нет (`ARTLOOK markers=0`). Сводка шага, гейты и открытые пункты — [VS-3](../VS-3/README.md).

Листы `tools/art/visual/sheet.py` (цвет / серый Rec.709 / дейтеранопия): `sheet-NN-*.png` — вне git, `scraped-data/derived/visual-evidence/HB-25/exit-vs3/` в worktree `C:/tmp/wt-visual` (индекс с sha256 — `scraped-data/derived/visual-evidence/VS3-exit-index.json`): на них сканы, рубашки и аватары нашего клиента (ВР-48, ВР-CP12, 02 §12; ревью VS-3, ВР-VS3-R01). В этой папке — `sheet-manifest.json` с sha256 каждого листа; в git из кадров выхода — только контактные листы [VS-3/contact](../VS-3/contact/).

Открыто: сброс по лимиту 9/7 на обеих досках (1080p 100 / 150 %, 720p 150 %) — вся рука кандидаты, «Рука 9/7», STATUS «Рука больше предела: сбросьте 2»; отмеченная карта (опущена, значок card-drop) — в кадре DISCARD_CARDS Marmoreal 720p 150 % (выбор после «Hiss and Slither»); буст King Arthur способностью (прогон `boost`): карта рубашкой у COMBAT-L с «+2».

**Вердикт: художественно принято, по делегированию (2026-10-07).** Сброс по лимиту с отмеченными картами в одном кадре автоклиент не даёт (подтверждает сразу) — отметка показана на сбросе DISCARD_CARDS того же режима руки.

**Ревью VS-3 (2026-10-07, единый проход):** принято, по делегированию, с замечанием: у рубашки буста King Arthur (boost, 720p 150 %) чип «+2» привязан к коробке 150×208, а рубашка вписана уже — чип висит на ~20–25 px в стороне от угла карты; привязать к нарисованному прямоугольнику ([VS-3](../VS-3/README.md) п. 12, ВР-VS3-R03).
