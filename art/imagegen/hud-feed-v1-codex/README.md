# HB-38 — журнал, тосты, субтитры

Статус: **предложено**. Рекомендую этот вариант: спокойный журнал слева в L, открываемый список из TOP в S, короткие сообщения в свободном коридоре с проверяемым переносом наверх. Геометрия принятых блоков сохранена; тосты и субтитры не выбирают место по визуальному впечатлению — все попытки измеряются по консервативным маскам.

64 RU-макета + 64 серых; отдельная EN-пара; 8 нативных контактных листов с восемью состояниями **бок о бок** и 8 overlay-листов с девятью панелями (восемь состояний + бой), каждый в цвете и сером. PNG со сценой находятся только в derived. Концепты не генерировались; `concepts/` пуст, `generation-records.json` хранит запрет и точный ключ `HB-38-procedural-v1`.

Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-feed-v1-codex/.

## Листы

| Холст | Overlay без сканов | Контакт: 8 состояний в нативном размере |
|---|---|---|
| marmoreal · 1920×1080 · 100% | [цвет](comparison/HB-38-marmoreal-overlay-1920x1080-100.png) · [серый](comparison/HB-38-marmoreal-overlay-1920x1080-100-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1920x1080-100-gray.png) |
| marmoreal · 1920×1080 · 150% | [цвет](comparison/HB-38-marmoreal-overlay-1920x1080-150.png) · [серый](comparison/HB-38-marmoreal-overlay-1920x1080-150-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1920x1080-150.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1920x1080-150-gray.png) |
| marmoreal · 1280×720 · 100% | [цвет](comparison/HB-38-marmoreal-overlay-1280x720-100.png) · [серый](comparison/HB-38-marmoreal-overlay-1280x720-100-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1280x720-100.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1280x720-100-gray.png) |
| marmoreal · 1280×720 · 150% | [цвет](comparison/HB-38-marmoreal-overlay-1280x720-150.png) · [серый](comparison/HB-38-marmoreal-overlay-1280x720-150-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-contact-1280x720-150-gray.png) |
| sarpedon · 1920×1080 · 100% | [цвет](comparison/HB-38-sarpedon-overlay-1920x1080-100.png) · [серый](comparison/HB-38-sarpedon-overlay-1920x1080-100-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1920x1080-100-gray.png) |
| sarpedon · 1920×1080 · 150% | [цвет](comparison/HB-38-sarpedon-overlay-1920x1080-150.png) · [серый](comparison/HB-38-sarpedon-overlay-1920x1080-150-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1920x1080-150.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1920x1080-150-gray.png) |
| sarpedon · 1280×720 · 100% | [цвет](comparison/HB-38-sarpedon-overlay-1280x720-100.png) · [серый](comparison/HB-38-sarpedon-overlay-1280x720-100-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1280x720-100.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1280x720-100-gray.png) |
| sarpedon · 1280×720 · 150% | [цвет](comparison/HB-38-sarpedon-overlay-1280x720-150.png) · [серый](comparison/HB-38-sarpedon-overlay-1280x720-150-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-sarpedon-contact-1280x720-150-gray.png) |

[EN, Marmoreal 1080p/100](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-toast-stack-en-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-toast-stack-en-1920x1080-100-gray.png). Уменьшенные листы `derived/review/` служат только осмотру, не заменяют нативные финалы.

## Данные и примеры

Владелец Marmoreal — Medusa, Sarpedon — King Arthur. HP, колоды, исходные руки и TOP используют принятую статическую проекцию HB-07, а журнал показывает последующий момент seq 23 / seq 26. Это компоновка HUD на реальных входах, не синхронный screenshot клиента. `facts.json` содержит поля, ключи, параметры, trace path/line каждого события и происхождение числа хода. Ход события выводится из последнего S09AUTO own turnCount **действовавшего игрока до первого SNAPSHOT applied данного seq**. MS-LOG запаздывает, а завершивший ход snapshot уже указывает следующего игрока; текущий HUD-TURN в момент печати лога был бы неверным. Полоса Medusa P1 #DAC576, Arthur/Merlin P2 #5786A8.

События Marmoreal: seq 5, 7, 13, 15, 22, 23; Sarpedon: seq 3, 5, 9, 13, 24, 26. `ms.log.stay` локализует no movement. Medusa названия карт — i18n.ru, King Arthur — EN, как Card.nameRu в БД. Полные строки сохранены для будущих tooltip; многоточие допустимо только внутри строки журнала. В S все шесть строк помещаются (capacity 12), поэтому scroll track/ thumb не рисуются; код поддерживает появление прокрутки при избытке до 50 строк. Открытый S-список и отказные значки намеренно могут закрывать поле; их площади в transient_overlap, а не в постоянных блоках.

Все состояния кроме log — **примеры из реальных данных**. toast-info: настоящий reconnect E со since=1 / snapshot=1 → пропущено 0. toast-stack: пример отказа устаревшей команды после reconnect, не событие run I. toast-error: пример клика в ход соперника. TOAST command echoes run I не рисуются. toast-warning — тестовая рука 8/7, а не записанная рука run I:

- **marmoreal**: medusa:gaze-of-stone, medusa:snipe, medusa:clutching-claws, medusa:dash, medusa:hiss-and-slither, medusa:regroup, medusa:second-shot, medusa:a-momentary-glance.
- **sarpedon**: king-arthur:the-holy-grail, king-arthur:noble-sacrifice, king-arthur:swift-strike, king-arthur:excalibur, king-arthur:the-aid-of-morgana, king-arthur:aid-the-chosen-one, king-arthur:command-the-storms, king-arthur:bewilderment.

toast-bottom и sub-lowered: рука опущена, видно ровно 48 su, подпись скрыта. Отказная цель выбрана из расположения фигур **на bench**, зоны — из topology:

- **marmoreal**: Medusa M13 (red, yellow) → King Arthur M31 (violet, brown); общих зон нет.
- **sarpedon**: Merlin S25 (brown, purple, yellow) → Medusa S20 (blue); общих зон нет.

sub — геометрический пример длинной ARTHUR-MATCHUP-MEDUSA-01: она звучит при старте матча. sub-lowered — пример ARTHUR-ATTACK-01 «Защищайся!»: её произносит сам Arthur при атаке, в run I атаковал Merlin. Ни одна реплика не выдаётся за сыгранную в выбранный момент журнала.

## Мелкие решения и дельта 04

Сдержанная печатная геометрия: navy-панель, закрытая тонкая кромка, плоский шрифт; без эффектов. Крест ошибки и крест закрытия различаются толщиной и назначением, предупреждение — заполненным треугольником с navy «!» из HB-29 и кромкой 2 su. Значки не экспортируются как новые ассеты. Отказ: пластина 24 su, X, тёмная внешняя keyline, 350 мс.

Проверяется фактическая маленькая плашка «Рука n/7», а пустая остальная часть HAND-CAPTION reserve свободна для SUB с отступом 8 su. Высота SUB — полный line box Roboto + 10 su, минимум 28 su. Предупреждение переносится по словам без усечения и имеет полный close cross. Самый новый тост снизу. Баннер начала хода длится 600 мс; **тост ждёт окончания баннера**, на финалах баннера нет.

ВР-VS2-HB38-18 (по делегированию, fix1): в defense-window клетки не интерактивны и LOG скрыт, поэтому COMBAT проверяет только принятые дилатированные фигуры и каждый прямоугольник HUD; HAND-CAPTION имеет зазор 8 su. spaces_px2 остаётся информационным измерением каждой попытки. В GAME клетки остаются препятствиями.

В боевом overlay группа двух тостов и длинного субтитра размещается целиком: SUB ниже тостов с gap 8 su. Цепочка: bottom-combined → top-combined → вверх по одному пикселю до STATUS.bottom + 8 su → newest-only с капсулой ниже → честный FAIL. Подробные дельты newest-only записаны в facts.deltas_04.

При неудаче всей цепочки overlay подписан FAIL; отказ и все попытки остаются в отчёте. Тёмная внешняя `mark.keyline` отказной плашки — обязательный служебный контур; её низкий контраст к собственному navy сохранён как `outer_keyline_informational`. Функциональная пара отказа — X/плашка. Приёмочная пара `panel.edge`/тело проверяется для панелей, тостов и капсулы, как §02 3.5; keyline не выдаётся за светлую panel.edge.

## Исправления fix1

1. Весь рисуемый текст и его измерение используют Roboto с посимвольным DroidSansFallback на том же baseline и кегле. До: U+2192 отсутствовал в обоих Roboto, стрелка не рисовалась; после: `→` выводится fallback. Полные строки LOG сохранены; изменённые сокращения перечислены ниже.
2. Overlay: вместо всех отклонённых прямоугольников показаны первые попытки фаз и последний отклонённый шаг каждого поиска вверх, контур state.warning 1 px без заливки. Пунктир text.secondary показывает STATUS.bottom + 8 su; легенда хранит число отклонений. Все попытки остаются в verification.
3. COMBAT: клетки исключены из препятствий согласно ВР-VS2-HB38-18; figures и все HUD-блоки остаются препятствиями, HAND-CAPTION защищён зазором 8 su. Ниже приведены результаты до → после.
4. EN check: ключевые подписи базового HUD взяты из SourceString (EN) st-hud/st-ms вместо RU; STATUS и подпись руки также переведены. Прямоугольники базового HUD совпадают с RU-парой. Имена и данные сохранены.

### Строки LOG с изменившимся отображением

| Макет / seq | До | После |
|---|---|---|
| HB-38-marmoreal-log-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-toast-info-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-toast-warning-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-toast-error-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-toast-stack-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-toast-bottom-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-sub-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-sub-lowered-1920x1080-100 / 5 | Medusa: манёвр: Medusa M13→… | Medusa: манёвр: Medusa M13… |
| HB-38-marmoreal-log-1920x1080-150 / 7 | King Arthur: манёвр: King Arthur M31→… | King Arthur: манёвр: King Arthur M31… |
| HB-38-marmoreal-log-1280x720-150 / 7 | King Arthur: манёвр: King Arthur M31→… | King Arthur: манёвр: King Arthur M31… |
| HB-38-sarpedon-log-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-log-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |
| HB-38-sarpedon-toast-info-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-toast-info-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |
| HB-38-sarpedon-toast-warning-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-toast-warning-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |
| HB-38-sarpedon-toast-error-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-toast-error-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |
| HB-38-sarpedon-toast-stack-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-toast-stack-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |
| HB-38-sarpedon-toast-bottom-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-toast-bottom-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |
| HB-38-sarpedon-sub-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-sub-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |
| HB-38-sarpedon-sub-lowered-1920x1080-100 / 3 | Medusa: манёвр: Medusa S20→… | Medusa: манёвр: Medusa S20… |
| HB-38-sarpedon-sub-lowered-1920x1080-100 / 5 | Medusa: манёвр: Medusa S35→… | Medusa: манёвр: Medusa S35… |

### Бой: до → после по доске и холсту

| Доска / холст | До: совместная группа | После: фаза | Тосты / капсула, su | figures_px2 | hud_px2 | spaces_px2 (информационно) | Тостов |
|---|---|---|---|---|---|---|---|
| marmoreal · 1920x1080-100 | upward-combined | bottom-combined | ([[810.5, 736.0, 299.0, 48], [781.0, 792.0, 358.0, 48]], [711.5, 848.0, 493, 29.0]) | 0 | 0 | 33640 | 2 |
| marmoreal · 1920x1080-150 | FAIL | top-combined | ([[488.33333333333337, 162, 303.3333333333333, 48], [457.33333333333337, 218, 365.3333333333333, 48]], [404.5, 274, 499, 29.333333333333332]) | 0 | 0 | 80201 | 2 |
| marmoreal · 1280x720-100 | FAIL | bottom-combined | ([[702.0, 638.0, 302.6666666666667, 48], [670.5, 694.0, 365.6666666666667, 48]], [602.3333333333334, 750.0, 498, 30.0]) | 0 | 0 | 18279 | 2 |
| marmoreal · 1280x720-150 | FAIL | top-combined | ([[421.0, 162, 295.77777777777777, 48], [392.0, 218, 353.77777777777777, 48]], [338.8888888888889, 274, 488, 29.555555555555557]) | 0 | 0 | 48490 | 2 |
| sarpedon · 1920x1080-100 | FAIL | top-combined | ([[810.5, 216, 299.0, 48], [781.0, 272, 358.0, 48]], [711.5, 328, 493, 29.0]) | 0 | 0 | 24997 | 2 |
| sarpedon · 1920x1080-150 | FAIL | top-combined | ([[488.33333333333337, 162, 303.3333333333333, 48], [457.33333333333337, 218, 365.3333333333333, 48]], [404.5, 274, 499, 29.333333333333332]) | 0 | 0 | 78208 | 2 |
| sarpedon · 1280x720-100 | FAIL | top-combined | ([[702.0, 216, 302.6666666666667, 48], [670.5, 272, 365.6666666666667, 48]], [602.3333333333334, 328, 498, 30.0]) | 0 | 0 | 19046 | 2 |
| sarpedon · 1280x720-150 | FAIL | upward-combined | ([[421.0, 138.0, 295.77777777777777, 48], [392.0, 194.0, 353.77777777777777, 48]], [338.8888888888889, 250.0, 488, 29.555555555555557]) | 0 | 0 | 40223 | 2 |

### EN fit

| Блок | До → после | Помещается |
|---|---|---|
| PANEL-LOC | Medusa → Medusa | да |
| PANEL-LOC | ВАШ ХОД → YOUR TURN | да |
| PANEL-LOC | 14/16 → 14/16 | да |
| PANEL-LOC | 1 → 1 | да |
| PANEL-LOC | 1/1 → 1/1 | да |
| PANEL-LOC | 2 → 2 | да |
| PANEL-LOC | 1/1 → 1/1 | да |
| PANEL-LOC | 3 → 3 | да |
| PANEL-LOC | 1/1 → 1/1 | да |
| PANEL-OPP | King Arthur → King Arthur | да |
| PANEL-OPP | ЖДЁТ → WAITING | да |
| PANEL-OPP | 17/18 → 17/18 | да |
| PANEL-OPP | Merlin → Merlin | да |
| PANEL-OPP | 7/7 → 7/7 | да |
| OPP-HAND | Рука 5 · колода 24 · сброс 1 → Hand 5 · deck 24 · discard 1 | да |
| DECKS | Колода 23 → Deck 23 | да |
| DECKS | Сброс 2 → Discard 2 | да |
| ACTIONS | МАНЁВР → MANEUVER | да |
| ACTIONS | АТАКА → ATTACK | да |
| ACTIONS | СХЕМА → SCHEME | да |
| ACTIONS | КОНЕЦ ХОДА → END TURN | да |
| TOP | Меню → Menu | да |
| TOP | Ход 3 → Turn 3 | да |
| STATUS | Choose an action: maneuver, attack or scheme → Choose an action: maneuver, attack or scheme | да |
| STATUS | M → M | да |
| STATUS | A → A | да |
| STATUS | G → G | да |
| HAND-CAPTION | Hand 5/7 → Hand 5/7 | да |

Все переведённые строки помещаются в принятые блоки, усечения нет.
Базовые строки без EN: нет; имена и числовые данные остаются из источников.


## Проверка P1–P14

| Требование | Реализация и доказательство |
|---|---|
| P1 | Два разрешённых bench-кадра, неизменные пиксели вне HUD; старые подписи фигур сохранены. |
| P2 | Четыре нативных масштаба 1 / 1,5 / 0,75 / 1,125 px/su. |
| P3 | GAME: принятые блоки HB-07, TOP/STATUS HB-13, рука HB-22, CP-13. |
| P4 | Все восемь состояний обеих досок; примеры явно перечислены ниже. |
| P5 | 6/3 строки L, все 6 в S-списке, текст через ms.log.*, полоса команды 4 su. |
| P6 | Тосты по цепочке bottom → top-band → вверх по одному пикселю → newest-only; все попытки. |
| P7 | Субтитры одной строкой, капсула, полный текст VO, геометрия из hand corridor. |
| P8 | Отдельный бой в каждом overlay, карты и кнопки HB-29; совместный поиск всей группы. |
| P9 | Никаких видимых заглушек; источники и открытые данные ниже. |
| P10 | text_fit каждого текста, log_ellipsis с полным текстом; другие подписи не сокращены. |
| P11 | Маски фигур/всех клеток с принятой дилатацией, прямоугольники HUD, отдельные transient. |
| P12 | Контраст фактического фона под панелью, точные токены; совпадение x1 HB-08 отдельно. |
| P13 | Rec.709 целочисленно, пары формы знаков и разница яркости последней строки. |
| P14 | verification.json + before hashes + полный итоговый манифест; предел 30 MB. |

## Что не прошло

Неудачных измерений нет.

Неудачные проверки сохранены в verification.acceptance и failures; статус не «принято».

## Открытые данные

Синхронные HP/рука на момент последней строки журнала не реконструируются: используется разрешённая HB-07 проекция. Положение фигур — bench, не run I. Маленькие старые клиентские имена/HP над фигурами являются **артефактом исходного фона**, их не ретушировали. Состав неизвестных карт после reconnect не утверждается; тестовые руки обозначены как примеры. Новых неподтверждённых игровых чисел не добавлено. Каждое видимое число базовых панелей сохраняет HB-07 источник.

## Строки без ключа

«Х{n}» / EN «T{n}» — §04 2.10, ВР-VS2-HB38-16, отдельного StringTable key нет. Пунктуация соединения ms.log.move — `, ` из оригинальной строки trace. Цифры гарпий и боевые значения базовых панелей — принятый HB-07, а не новые ключи HB-38.

## Входы и воспроизведение

source-hashes-before.json: 3716 файлов, включая всё дерево v3; snapshot модулей скопированы побайтно до работы. В verification.source_unchanged проверяется полная SHA256 неизменность, write audit запрещает мутации вне двух папок. Git, unreal/, сеть и subprocess не используются.

Индивидуальные хеши из карточки совпали.

Изменения входов относительно прежнего source-hashes-before.json: []. Базовый файл хешей не перезаписан. Новый вход DroidSansFallback.ttf и его SHA256 — verification.fix1_inputs.

Запуск: `python -B -X utf8 art/imagegen/hud-feed-v1-codex/_tools/build_feed.py`. Независимый аудит: `python -B -X utf8 art/imagegen/hud-feed-v1-codex/_tools/audit_feed.py`. Генератор выводит PNG сразу в реальном размере холста; текст ceil(type_su × scale), скан целиком inside CP-13, один Lanczos непосредственно из исходника. Rec.709: (2126R + 7152G + 722B + 5000) // 10000. Манифест создаётся последним после README, facts и verification.

## Ревью Claude (2026-10-06, CX-14, VS-2, единственный проход, по делегированию)

Итог: **принято по делегированию** (полномочие пользователя 2026-10-06 «Все решения принимай») как макет LOG, TOASTS
и SUB HB-38 для HB-39…HB-41 (`UUmHudLog`, `UUmToastStack`, `UUmHudSubtitle`). Статус пакета остаётся «предложено» до
листа приёмки 02 §13.2; строки «дельта 04» (newest-only в классе S, бой по ВР-VS2-HB38-18) переносятся в 04 §2.10,
§2.12, §2.13 отдельным шагом документа.

История:
- Прогон 1: 15:33–15:53 (задание `06-tasks/prompts/HB-38.codex.md`, ВР-VS2-HB38-01…17). Verifier честно записал
  `combat_zero` FAIL: в 7 из 8 боевых overlay группа «два тоста + субтитр» не помещалась без клеток.
- Ревью нашло четыре правки, задание `06-tasks/prompts/HB-38.fix1.codex.md`:
  - стрелка `→` в строках MS-LOG не рисовалась: в Roboto нет U+2192, на финалах было «M13 M25», «S20 S35»;
  - overlay-листы залиты сотнями контуров отвергнутых попыток (по одной на пиксель подъёма), маски и тосты не видны;
  - бой: клетки в окне защиты не интерактивны, а цепочка считала их препятствием — новое решение ВР-VS2-HB38-18;
  - EN-проверка смешивала языки: лента EN, базовый HUD RU («Меню», «Ход 3», «ЖДЁТ», кнопки).
- Корректирующий прогон fix1, попытка 1 (20:19–20:56) выродилась: после ошибки инструмента модель выдала 36 тыс.
  токенов бессвязного текста, файлов не меняла. По ВР-VS2-HB38-19 тот же fix1 запущен ещё раз (20:57–21:07) — это
  повтор сорвавшегося запуска, а не второй цикл ревью. Обе попытки — строки `credits-ledger.json`.

Что проверено:
- **Рамки задачи.** `git status --porcelain` до и после каждого прогона: Codex создал только эту папку и
  `scraped-data/derived/hud-feed-v1-codex/` (в `.gitignore`). Прочие новые пути основной копии — пакеты и задания
  параллельных сессий (HB-42, CP-07). `unreal/` не тронут, git-команд нет. `outside_folder: []`,
  `source_unchanged: true` — 3716 входов пересчитаны независимо, изменений 0; новый вход fix1 — `DroidSansFallback.ttf`
  (`verification.fix1_inputs`).
- **Файлы.** `manifest-sha256.json`: 200 файлов, хеши пересчитаны независимо, все совпали, лишних нет. 64 + 64 серых
  макета, EN-пара, 8 контактных и 8 overlay-листов в цвете и сером. Пакет без scraped-data — 28,7 МБ (≤ 30). Генераций
  изображений 0. В `comparison/` только контуры масок, прямоугольники и слой ленты (~1,3 тыс. цветов на лист): сканов,
  рубашек, аватаров и доски в этой папке нет. `audit_feed.py` (только чтение) — PASS, ошибок 0.
- **Кадры.** Открыты (Read) все 64 цветных финала после fix1 — обе доски, 1080p и 720p, UI 100 % и 150 %, — и
  EN-проверка; серые полные кадры выборочно и нативные серые вырезки каждого LOG, тоста, капсулы и отказной плашки на
  всех восьми холстах (собраны вне git, `C:/tmp/visual/CX-14/review-fix1/`); боевые и стопочные плитки overlay
  Marmoreal 1080p 100 %/150 % и Sarpedon 720p 150 %; стрелка при ×2–×3 nearest. Результат осмотра:
  - фон Marmoreal — нарисованный задник (`aeafe8f2…`), Sarpedon — `lit3d` (`bf36d5d6…`), без ретуши; шесть фигур v2;
  - LOG: 6 строк в L на 1080p, 3 на 720p, список S из «Журнал» с 6 строками; полоса команды 4 su, «Х{n}» слева,
    последняя строка `text.primary`, многоточие только в строках журнала; стрелка видна;
  - тосты: обычный без знака, предупреждение — кромка `state.warning` 2 su, треугольник «!» и крестик, ошибка — X
    `state.error`; в сером три вида различаются формой; стопка: старый сверху, новый снизу; при руке в покое — верхняя
    полоса, при опущенной руке — над картами; badge-refuse 24 su у «Конец хода» и над Medusa / King Arthur;
  - SUB: капсула, «King Arthur:» `type.tag` `card.cream`, реплика целиком одной строкой; при опущенной руке — над
    опущенными картами;
  - тексты дословно из `why-reasons.json`, `st-ms.csv`, `st-hud.csv` и VO-скрипта; «уточнить» нет; обрезанных подписей
    вне журнала нет; эха команд прогона I нет;
  - бой (только overlay): группа «два тоста + субтитр» на 8/8 холстах с 0 px² к фигурам и всем блокам HUD (CENTER,
    кнопки защиты, рука); площадь по клеткам — информационно в README и `verification`.
- **Метрики.** Контраст текста ≥ 7,1 : 1, кромка 3,79, знак 3,64, полоса 4,04 (≥ 3); мин. текст 10,5 px на 720p;
  `palette` 0; совпадение скинов HB-08 попиксельное; `glyph_coverage` — пропущенных глифов 0.
- **DE и права.** Только процедурная отрисовка, мазков, клякс и шрифтов DE нет. Сканы карт и аватары — только в
  `scraped-data/derived/` (внутренняя LAN-сборка, ВР-48, GAP-019). Трат SYNTX и Tripo нет; три строки Codex в журнале.

Решения ревью (по делегированию):
- ВР-VS2-HB38-18 — в окне защиты боя тост и субтитр обязаны давать 0 px² с фигурами и всеми блоками HUD; маска клеток
  не препятствие (клетки не интерактивны, LOG скрыт), её площадь пишется информационно. В обычных состояниях клетки
  остаются препятствием. Перенести в 04 §2.12 и §2.13 как дельту.
- ВР-VS2-HB38-19 — корректирующий прогон, сорвавшийся без изменений файлов (вырождение модели, сбой инструмента),
  повторяется тем же заданием один раз; второй цикл ревью не открывается.
- ВР-VS2-HB38-20 — в UE шрифт ленты (`UUmHudLog`, HB-39) должен иметь fallback с U+2192 (как Slate:
  `DroidSansFallback`); проверить стрелку в живом кадре HB-39. Плашки UMG не заменяют `→` другим символом.

Не входит в пакет: импорт в UE, флаг отката и живой кадр — HB-39…HB-41 плана 05.

Хеш `README.md` в `manifest-sha256.json` обновлён Claude после этого раздела (остальные 199 записей — от Codex, без изменений).
