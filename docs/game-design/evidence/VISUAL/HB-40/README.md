# HB-40 — тосты: `UUmToastStack` и `UUmToast`, отказ у элемента (шаг H5)

VS-4, шаг V2 (H5 + H11), 2026-10-07, ветка `feat/visual-vs4` (worktree `C:/tmp/wt-visual`), код — `6cdec6e1`.
Карточка — `hud.csv` HB-40; 04 §2.12 (с дельтами VS-2 и VS-4), §4.3, §7.1, ВР-H06; 02 §4.5 (ВР-66); принятый макет
HB-38 (`art/imagegen/hud-feed-v1-codex/`, ВР-VS2-HB38-06…12, -18); значки IC-40 `badge-refuse`, IC-47 `state-warning`,
IC-54 `ui-close` (сделаны, влиты `236658c8`). Тот же коммит — [HB-39](../HB-39/README.md), [HB-41](../HB-41/README.md),
[HB-36](../HB-36/README.md).

**Статус:** стопка, тост, WBP, подключение всех источников, тесты и лист галереи готовы, по делегированию. Живой кадр H5
«тост сверху и снизу» из партии и check-trace живой трассы — шаг «Кадры». **Откат:** `-S08SlateHud=toast` — строка Slate
`ToastHudLine` на старом месте и подсказка лимита руки в панели руки; стопка не строится.

## Что сделано (`do`)

| Пункт | Где и как |
|---|---|
| 1. Классы | `S08/UI/UmToastStack.h/.cpp` (`/Game/S08/UI/Hud/WBP_UI_HUD_TOAST`: `Canvas`, `Badge`; пул из 3 `UUmToast`) и `S08/UI/UmToast.h/.cpp` (`/Game/S08/UI/Common/WBP_UmToast`: BindWidget `Body`, `Icon`, `Text`, `CloseButton` — `WBP_UmButton`). API `Push(FUmToastSpec{Kind, Text, HoldSec, bSticky, Key})`, `Dismiss(Key)`, `SetExternal` (тост-триггер HB-36), `ShowBadge`. Общие правила — `S08/UI/UmHudFeed.h/.cpp`, сторона режима игры — `UmHudFeedBlocks.h/.cpp`. |
| 2. Размещение | `UmHudFeed::Place` — цепочка 04 §2.12: над рукой → верхняя полоса (y 216, S 162) → наименьший сдвиг вверх целыми пикселями, не выше низа STATUS + 8 → только новый тост → FAIL. Тосты и капсула SUB — одна группа (ВР-VS4-23). Препятствия — ВР-VS4-29. Трасса `TOAST place=bottom|top step=bottom|top|upward|newest|fail overlap=<px²> n= kinds= dropped= y= h= sub= external= attempts=` при каждом новом размещении. |
| 3. Ввод | ни стопка, ни тост фокус не берут; мышь ловит только крестик удерживаемого тоста (`UUmButton` через арбитр нажатий, подсказка `ms.hint.close`); `CursorOverHud` не отдаёт этот клик доске. |
| 4. Отказ у элемента | `badge-refuse` (IC-40) 24 su на 350 мс (`refuse.ms`, анимация `appear`, без тряски): у кнопки Slate — в её правом верхнем углу, у элемента UMG — у указателя, у клетки — над её центром (хуки в `HandleHudPressOutcome` и в четырёх местах `ShowIllegalCell`); текст причины — тостом из `ShowReason`. |
| 5. Эхо команд | эхо и остальные EN-строки кода ввода без ключа — только `-S09Markers` (строка Slate) и откат (ВР-VS4-26). |
| 6. Строки | `ST_Why` (вид «ошибка»), `ms.hint.hand.limit` («предупреждение», удерживается), `ms.hint.close` (подсказка крестика), `hud.toast.reconnected` («обычный»); `hud.toast.rate` — без источника (ВР-VS4-36). |
| 7. `SHOT widget` | `id=UI-HUD-TOAST impl=umg state=bottom|top … n= kinds=info,error,pending step= overlap= dropped= sticky=0|1 external=0|1 badge=0|1 class=L|S` — без текста. |
| 8. Slate | `ToastHudLine` — только `-S08SlateHud=toast`; в виде по умолчанию — ничего (ключевые тосты рисует UMG), под `-S09Markers` — строки без ключа. Подсказка лимита руки в панели руки — только на откате. |
| 9. Тесты | `Unmatched.S08.Hud.Toast.Place` (цепочка на холстах с FIELD Marmoreal: снизу, верхняя полоса и подъём с 0 px², группа с капсулой, опущенная рука, бой без клеток, только новый в S, FAIL; вид трёх тостов; строки `TOAST` и `SHOT`), `.Sticky` (правило лимита держится 30 с, ловит клик только по себе, новый тост прячет его, но не убирает, `Dismiss` — уход за 120 мс), `.Queue` (не больше 2, новый снизу, тот же тост продлевает срок, ожидание баннера, сроки 4 с / 2–4 с, значок 350 мс, бюджет). |

## Источники тостов в клиенте

| Источник | Хук | Вид |
|---|---|---|
| отказ по нажатию, клетке, правилу (`ShowReason`, CUE-004: `why.*`, `ms.*`) | `UmHudToastReason` в `ShowReason` | по ключу (ВР-VS2-HB38-06) |
| пропущенный эффект без целей (`why.effect.no.targets`, обоим игрокам) | тот же `ShowReason` в `FeedPendingPresentation` | ошибка |
| отказ клетки выбора на поле (`PendingCellReason`) | `UmHudToastReason` рядом с `ShowIllegalCell` | ошибка + значок над клеткой |
| правило лимита руки (DE-024, `FS09HandLimitHint`) | `UmHudSyncHandLimit` в `ApplyHandLimitHintVisibility` | предупреждение, до крестика, конца хода или GAME_OVER |
| восстановление связи | `TickUmFeed` (поток снова готов после потери) | обычный «Позиции обновлены (пропущено {n})» |
| повторный необязательный выбор (HB-36) | `SetExternal` из `TickUmFeed` | форма `UUmHudPending` в месте стопки |

## Решения по делегированию (шаг V2)

| № | Решение | Почему |
|---|---|---|
| ВР-VS4-23 | Тосты и SUB всегда одна группа (капсула под тостами 8 su, по центру коридора руки; тосты по центру холста); верхняя полоса S — y 162 (HB-38 P6), а не 144 прежнего кода H2 | 04 §2.13 «под стопкой тостов»; макет HB-38 |
| ВР-VS4-25 | Шаг 5: виден новый тост на позиции с наименьшим пересечением, `step=fail overlap=<px²>` | отказ без текста запрещён (DE-014) |
| ВР-VS4-26 | В вид по умолчанию попадают только тосты с ключом StringTable; свободные EN-строки кода ввода (`attack draft: …`, `pending cell rejected: …`, `discard pick 2/3`) — только `-S09Markers` и откат; отказ клетки выбора — тостом своего `why.*` | HUD-RULES П5 (без литералов), ВР-35 (отладка — под маркерами) |
| ВР-VS4-28 | Тот же тост (ключ и текст) продлевает срок, второго не будет; удерживаемое правило не уходит ради нового тоста — ждёт скрытым, пока нет места | повтор отказа — не новое сообщение; правило закрывает только его владелец |
| ВР-VS4-29 | Препятствия в клиенте: прямоугольник каждой клетки (центр ± радиус через камеру K1), фигуры с тегами и плашкой, все нарисованные блоки (и ещё рисующие панели Slate: кнопки командной панели до HB-43, строки панели руки, боковая), карты руки как нарисованы, HAND-CAPTION + 8 su со всех сторон; пока на экране бой — без клеток | 04 §2.12, ВР-VS2-HB38-18; маски HB-38 есть только для двух кадров bench |
| ВР-VS4-30 | Место `badge-refuse`: кнопка Slate — правый верхний угол, элемент UMG — указатель + (16, −16) su, клетка — центр (текущая камера) | у UMG-элементов нет общего реестра прямоугольников по id нажатия |
| ВР-VS4-31 | «Позиции обновлены (пропущено {n})»: n = seq после восстановления − seq в момент потери потока; только если поток уже был готов | клиент не получает числа пропущенных событий; трасса E: since = 1, снимок 1 → 0 |
| ВР-VS4-36 | `hud.toast.rate` пока без источника: ограничение частоты (429) клиент показывает как `why.syncing` (02 §1.1, `S08Contracts`) | менять разбор ошибок сервера — отдельное решение |
| ВР-VS4-37 | Тост появляется со времени `Push`, а если ждал баннер — с конца баннера | скачок часов (лист галереи) и живой клиент дают один вид |
| ВР-VS4-38 | Лист `-S08IconGalleryFeed` (инструмент ревью): клетки — один консервативный прямоугольник FIELD, фигуры — рамки масок HB-07 + 4 px, бой — вид защитника без центра (как overlay HB-38) | в галерее нет доски и камеры партии |

## Лист

Галерея `-S08IconGallery -S08IconGalleryFeed=<board>` (editor `-game` из worktree, один клиент, `t.MaxFPS 30`,
`-RenderOffScreen`; клиенты ZCode в это время свои, не трогались), кадры на + 600 мс каждой секунды:
0 log, 1 toast-info, 2 toast-warning, 3 toast-error (значок у «Конец хода»), 4 toast-stack, 5 toast-bottom (рука опущена,
значок над King Arthur / Medusa — цель отказа HB-38), 6 sub, 7 sub-lowered, 8 combat. Данные — матрица HB-38: журнал
прогона I, строки таблиц, реплики VO-скрипта, рука прогона I (Medusa 5/7) и King Arthur (3 карты).

Размещение по трассам (`TOAST place=…`, все 0 px²):

| Холст | info / error | warning | stack | bottom | sub | sub-lowered | бой |
|---|---|---|---|---|---|---|---|
| Marmoreal 1080p 100 % | upward y 209 | upward y 197 | upward y 153, 2 | bottom y 976 | top y 216 | bottom y 999 | bottom y 751 |
| Marmoreal 1080p 150 % (S) | upward y 123 | upward y 111 | newest, 1 | bottom y 616 | upward y 142 | bottom y 639 | top y 162 |
| Marmoreal 720p 100 % | upward y 180 | upward y 168 | upward y 124, 2 | bottom y 856 | upward y 199 | bottom y 879 | bottom y 655 |
| Marmoreal 720p 150 % (S) | upward y 104 | upward y 92 | newest, 1 | bottom y 536 | upward y 123 | bottom y 559 | top y 162 |
| Sarpedon 1080p 100 % | upward y 210 | upward y 198 | upward y 154, 2 | bottom y 976 | top y 216 | bottom y 999 | top y 216 |
| Sarpedon 1080p 150 % (S) | upward y 124 | upward y 112 | newest, 1 | bottom y 616 | upward y 143 | bottom y 639 | top y 162 |
| Sarpedon 720p 100 % | upward y 181 | upward y 169 | newest, 1 | bottom y 856 | upward y 200 | bottom y 879 | top y 216 |
| Sarpedon 720p 150 % (S) | upward y 104 | upward y 93 | newest, 1 | bottom y 536 | upward y 124 | bottom y 559 | upward y 139 |

y — в su. «newest, 1» — шаг 4: старый тост ушёл раньше, как в макете при UI 150 %; на Sarpedon 720p 100 % так же, потому
что лист берёт FIELD целиком (ВР-VS4-38), а клиент — каждую клетку.

- В git (без доски и сканов: `-S08IconGalleryHandPlain -S08CardArtLegacy`, запасные лица карт): `plain-1080-100-contact-*.png`,
  `plain-720-150-contact-*.png` (9 состояний, цвет и серый Rec.709), `plain-crops-*.png` (журнал, предупреждение, стопка,
  нижний тост в родных пикселях) — sha256 в [`sheets-sha.json`](sheets-sha.json).
- Вне git (кадр доски, сканы в руке — ВР-VS4-01): `scraped-data/derived/visual-evidence/HB-40/` — контакты 9 состояний на
  8 холстах, вырезки тостов всех 8 холстов и значка отказа, цвет и серый — [`visual-evidence-index.json`](visual-evidence-index.json).

Что видно (Read: контакты Marmoreal 720p 150 % и Sarpedon 1080p 100 %, вырезки тостов 8 холстов, plain-листы цвет и
серый): обычный тост без знака, предупреждение — оранжевая кромка 2 su, треугольник «!», две строки без обрезки и крестик
×, ошибка — красный X на тёмной плашке; в сером три вида различаются формой (знак, толщина кромки); стопка — старый сверху,
новый снизу; при руке в покое тосты в верхней полосе над клетками, при опущенной руке — над картами; значок отказа у «Конец
хода» и над фигурой цели. Тексты — дословно из таблиц RU.

## Проверки

- Сборка UnmatchedEditor — `Succeeded` (`C:/tmp/visual/vs4-v2/build-12.log`), игровая цель — `Succeeded` (`build-game-2.log`).
- UE: новые тесты 9 из 9, `Unmatched.S08.Hud.*` 89 из 89, `Unmatched.S08 + S09 + S10` 491 из 491. Бюджет: тик стопки
  p95 0,0003 мс (≤ 0,02).
- `check-trace` — PASS на 8 трассах галереи: `UI-HUD-TOAST state=bottom` и `state=top` на обеих досках, `overlap=0`.
- `hud_contract.py validate` — PASS, `hud_strings_build.py check` — PASS, pytest `tools/s08` — 133 passed.
- WBP `WBP_UI_HUD_TOAST`, `WBP_UmToast` — created, up-to-date (`C:/tmp/visual/vs4-v2/um-hud-wbp-report.json`).

## Что не сделано в этом шаге

- Живой кадр H5 «тост сверху и снизу» из партии (1080p и 720p 150 %), check-trace живой трассы на обеих досках, клик по
  крестику правила в живой партии — шаг «Кадры».
- `hud.toast.rate` — ВР-VS4-36.
