# HB-17 — портретные панели

Статус: **предложено**. Генераций изображений нет; `generation-records.json` — пустой массив.

Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-panels-v1-codex/.

## Что сделано

74 полных цветных холста и 74 серых: Marmoreal и Sarpedon, 1920×1080 UI 100 % и 1280×720 UI 150 %. Каждый показывает неизменённый bench-фон и три блока; в S sidekick-fallen добавлена отдельная подсказка. Состояние из имени файла относится к одному блоку; остальные нейтральны. Нет дополнительных HUD-блоков.

PANEL-LOC: начало хода (0 мс), тление 0,35 и вариант 0,55 (+3 с), ожидание, один/два заполненных слота, урон, лечение Arthur, павший герой, павший помощник, монограмма. PANEL-OPP: ход, ожидание, ИИ с точкой-пульсом, павший. OPP-HAND: 3/5/10 рубашек и устаревшая колода с ≈. Также 12 листов состояний, четыре листа кольца с аватаром, четыре с монограммой, общий контактный лист; у каждого цветного листа есть серый.

## Листы

[Контакт всех финалов](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-contact-all.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-contact-all-gray.png). Контакт содержит **нативные** кропы трёх блоков каждого финального холста; подсказка S тоже включена. Ни один кроп не уменьшен. Полные сцены лежат рядом, по маске `HB-17-<board>-<block>-<state>-<res>-<scale>.png`.

Листы состояний:
- marmoreal, loc, 1920×1080/100 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-loc-states-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-loc-states-1920x1080-100-gray.png).
- marmoreal, opp, 1920×1080/100 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opp-states-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opp-states-1920x1080-100-gray.png).
- marmoreal, opphand, 1920×1080/100 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opphand-states-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opphand-states-1920x1080-100-gray.png).
- Кольцо marmoreal/1920: [аватар](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-ring-timesheet-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-ring-timesheet-1920x1080-100-gray.png) · [монограмма](comparison/HB-17-marmoreal-ring-timesheet-1920x1080-100.png) · [серый](comparison/HB-17-marmoreal-ring-timesheet-1920x1080-100-gray.png).
- marmoreal, loc, 1280×720/150 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-loc-states-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-loc-states-1280x720-150-gray.png).
- marmoreal, opp, 1280×720/150 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opp-states-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opp-states-1280x720-150-gray.png).
- marmoreal, opphand, 1280×720/150 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opphand-states-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-opphand-states-1280x720-150-gray.png).
- Кольцо marmoreal/1280: [аватар](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-ring-timesheet-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-marmoreal-ring-timesheet-1280x720-150-gray.png) · [монограмма](comparison/HB-17-marmoreal-ring-timesheet-1280x720-150.png) · [серый](comparison/HB-17-marmoreal-ring-timesheet-1280x720-150-gray.png).
- sarpedon, loc, 1920×1080/100 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-loc-states-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-loc-states-1920x1080-100-gray.png).
- sarpedon, opp, 1920×1080/100 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opp-states-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opp-states-1920x1080-100-gray.png).
- sarpedon, opphand, 1920×1080/100 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opphand-states-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opphand-states-1920x1080-100-gray.png).
- Кольцо sarpedon/1920: [аватар](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-ring-timesheet-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-ring-timesheet-1920x1080-100-gray.png) · [монограмма](comparison/HB-17-sarpedon-ring-timesheet-1920x1080-100.png) · [серый](comparison/HB-17-sarpedon-ring-timesheet-1920x1080-100-gray.png).
- sarpedon, loc, 1280×720/150 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-loc-states-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-loc-states-1280x720-150-gray.png).
- sarpedon, opp, 1280×720/150 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opp-states-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opp-states-1280x720-150-gray.png).
- sarpedon, opphand, 1280×720/150 %: [цвет](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opphand-states-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-opphand-states-1280x720-150-gray.png).
- Кольцо sarpedon/1280: [аватар](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-ring-timesheet-1280x720-150.png) · [серый](../../../scraped-data/derived/hud-panels-v1-codex/HB-17-sarpedon-ring-timesheet-1280x720-150-gray.png) · [монограмма](comparison/HB-17-sarpedon-ring-timesheet-1280x720-150.png) · [серый](comparison/HB-17-sarpedon-ring-timesheet-1280x720-150-gray.png).
- Якоря и размеры 1920×1080/100 %: [цвет](comparison/HB-17-overlay-1920x1080-100.png) · [серый](comparison/HB-17-overlay-1920x1080-100-gray.png). Полный список внутренних прямоугольников — `facts.json/rendered_panels[].elements`.
- Якоря и размеры 1280×720/150 %: [цвет](comparison/HB-17-overlay-1280x720-150.png) · [серый](comparison/HB-17-overlay-1280x720-150-gray.png). Полный список внутренних прямоугольников — `facts.json/rendered_panels[].elements`.

## Рекомендация и небольшие решения

Рекомендую тление **0,55 для класса S**: на 720p оно яснее сохраняет контур. Для L оставить принятое 0,35. Оба варианта даны рядом; это предложение, контракт и исходные иконки не изменены. Тлеющий обод остаётся известным исключением порога 3:1; в каждом локальном активном состоянии присутствует точный статус «ВАШ ХОД» из StringTable. Градации цвета не заменяют форму, текст и заполнение трекера.

L: круг аватара 80 su в окне кольца 104 su; помощники 32 su. Harpies нумеруются 1–3 на navy-диске 14 su, подпись 1/1 под каждым. Падение первого помощника: серый портрет, принятый крест/сердце 24 su рядом, 0/1; Merlin 0/7. OPP зеркальный: аватар справа, имя, статус, группа HP и ряд помощников выровнены вправо по одной границе; трекер снаружи слева. В OPP класса L трекер поднят на 4 su относительно исходной строки, чтобы между ним и рядом помощников осталось 4 su; PANEL-LOC не менялся. Имена из backend: Medusa, King Arthur, Merlin, Harpies; монограммы M/KA.

S по 04 §1.6/2.2: панель 240×96 su, аватар 64 su в окне 80 su, трекер 24 su. В sidekick-fallen отдельная подсказка над PANEL-LOC перечисляет всех помощников: Harpies 1 0/1, Harpies 2 1/1, Harpies 3 1/1 или Merlin 0/7. Все строки точно используют hud.panel.sidekick. Выбрана подсказка без мини-портретов: павшего отмечает принятое сердце с крестом 24 su. Подложка navy 0,92, край cream 0,45, радиус 6 su, отступ 10 su, type.tag 14 su. Зазор до PANEL-LOC 8 su; обе маски и все три блока не пересекаются. Имя 24 su, HP 20 su, статус 14 su; сокращений/многоточия нет. В L сохранено принятое представление: имя/индекс отдельно от HP; их каноническая строка hud.panel.sidekick записана в facts.json.

Урон снят в 320 мс: сердце в масштабе 1, ореол glow = 1 по контракту. Лечение Arthur — 120 мс, масштаб 1,1; павшее сердце — 200 мс, крест в масштабе 1. Заполненные действия — 300 мс; пустой слот использует принятый слой ring с opacity 0,6. Ореол ограничен окном 24 su, панель не получает красную заливку. Красные тела принятых PNG не перекрашены.

Sarpedon: нейтральный King Arthur 18/18, урон 17/18, лечение 17/18 → 18/18, павший 0/18. Оба ненулевых значения есть в run I; макет не доказывает реальное событие лечения между кадрами. Marmoreal: Medusa 14/16, Arthur 17/18. Максимумы и помощники из scrape; hand/deck/discard отдельно по доске: Marmoreal 5/24/1, Sarpedon 6/23/2. В состоянии 5 на Sarpedon пять рубашек — заданное состояние макета, нейтральное значение 6 сохранено.

≈ стоит у колоды: именно `bDeckCountStale` задан в 04 §2.3; число в руке не считается измерением устаревшего deck. Для 10 карт шаг уменьшается до 25,333 su (L) и 16,444 su (S), чтобы полный последний back оставался внутри. Все рубашки 48×67 su, весь исходный рисунок вписан целиком; никакой runtime-текст не печатается поверх него.

## Действия из run I

- Marmoreal / Medusa: turnCount 3, MS-LOG строки 1504 и 1606 `combat-client-host.trace.txt`, seq 13 и 15, два манёвра без перемещения. Значки action-maneuver; это два действия одного хода, не два произвольно выбранных цвета.
- Sarpedon / King Arthur: turnCount 2, строки 335 и 883 `combat-client-joiner.trace.txt`, два вызова `S09AUTO attack (attacker=f-1-sk0…)`. Действует Merlin в команде Arthur, трекер относится к игроку; обе атаки подтверждены последующими стадиями и расходом руки. Значки action-attack.

## Дельта CX-01r

| Блок | Холст | Было → стало, su | Причина |
|---|---|---|---|
| OPP-HAND | 1280x720/150 % | [901.7777777777778, 120, 220, 87] → [901.7777777777778, 120, 220, 104] | Рубашки 48x67 su целиком + подпись 14 su с нижним отступом; высоты 87 su не хватает для отступа. Все реальные подписи уместились в одну строку; шаг 10 сокращён. Маски проверены заново. |
| PANEL-LOC-SIDEKICK-TOOLTIP | 1280x720/150 % | None → [16, 416, 180, 104] | Дельта CX-01r: отдельная подсказка только в sidekick-fallen класса S; без мини-портретов, с сердцем 24 su; слева над PANEL-LOC, зазор 8 su, пересечение с масками и тремя блоками 0 px². |
| PANEL-LOC-SIDEKICK-TOOLTIP | 1280x720/150 % | None → [16, 472, 180, 48] | Дельта CX-01r: отдельная подсказка только в sidekick-fallen класса S; без мини-портретов, с сердцем 24 su; слева над PANEL-LOC, зазор 8 su, пересечение с масками и тремя блоками 0 px². |

Прямоугольники трёх основных блоков CX-01r сохранены с прежней дельтой OPP-HAND; добавлена отдельная подсказка S только в sidekick-fallen; расширение OPP-HAND явно видно на overlay и проверено по фигурам/всем клеткам.

## Иконки и растеризация

Принятые v3 PNG используются без перекраски/перерисовки. В `_tools/draw_icons_v3_snapshot.py` лежит побайтовая копия генератора; он не запускается. Отдельный модуль `_tools/build_panels.py` только композитит исходники. Каждый способ/путь/хеш в `facts.json/icon_methods`; ниже полный список реально используемых размеров:

| Значок/слой | Размер, px | Способ |
|---|---|---|
| action-attack | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| action-attack | 32 | Готовый PNG exact-size без ресэмплинга |
| action-maneuver | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| action-maneuver | 32 | Готовый PNG exact-size без ресэмплинга |
| marker-action-slot-de_ring | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-action-slot-de_ring | 32 | Готовый PNG exact-size без ресэмплинга |
| marker-turn-ring_flash_f00 | 104 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_flash_f00 | 90 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_flash_f02 | 104 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_flash_f02 | 90 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_flash_f04 | 104 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_flash_f04 | 90 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_flash_f06 | 104 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_flash_f06 | 90 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_rim | 104 | Мастер/слой 1024 → точный размер, один Lanczos |
| marker-turn-ring_rim | 90 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-fallen | 24 | Готовый PNG exact-size без ресэмплинга |
| resource-hp-fallen | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-fallen_cross | 24 | Готовый PNG exact-size без ресэмплинга |
| resource-hp-fallen_cross | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-fallen_heart | 24 | Готовый PNG exact-size без ресэмплинга |
| resource-hp-fallen_heart | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-full-enemy | 24 | Готовый PNG exact-size без ресэмплинга |
| resource-hp-full-enemy | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-full | 24 | Готовый PNG exact-size без ресэмплинга |
| resource-hp-full | 26 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-full | 27 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-full | 30 | Мастер/слой 1024 → точный размер, один Lanczos |
| resource-hp-full_glow | 24 | Готовый PNG exact-size без ресэмплинга |
| resource-hp-full_glow | 27 | Мастер/слой 1024 → точный размер, один Lanczos |

Ring flash f00–f06 и rim — слои из motion-контракта; frame/opacity/ease вычислены из ключей без аппроксимации картинкой. Времена 0/120/300/600/1000/2000 мс, позы всех 24 комбинаций — `verification.json/ring_timesheet`. Исходные цвета flipbook сохранены, включая принятую красную фазу. Серый вариант — Rec.709, не Pillow convert(L).

Шрифты строго Roboto-BoldCondensed/Roboto-Regular из указанного каталога Engine Fonts (только чтение шрифтов, `unreal/` не открывался). Растеризация в каждом разрешении отдельно: ceil(type_su×scale). Финальный HUD не масштабируется. 720p использует один Lanczos от оригинального 1920×1080 фона; остальные пиксели фона не меняются. Цифры runtime-текст, не новые текстуры.

## Открытые данные

1. Лечение Medusa на Marmoreal пропущено: подтверждённой пары HP нет. Это требует P3; выдуманный HP не добавлен.
2. В st-hud.csv нет точной локализованной строки для PANEL-OPP «его ход». В состоянии opp поле статуса пустое; ring и видимый трекер отличают его от wait. Не использованы «ВАШ ХОД» на чужой панели или произвольный перевод THEIR TURN. Ограничение записано в uncertain_values.

## Проверки и ограничения

- Пересечение с масками фигур/пространств: **0 px²**. Маски CX-01r, полигональная регистрация и консервативные расширения сохранены; пересечение измерено в пикселях по видимому alpha.
- Минимальный raster font на 720p: **16 px** (14 su × 1,125=15,75 номинально).
- Минимальный WCAG-контраст текста по фактической подложке: **7.592:1**. Каждый текст отдельно — verification/contrast/per_panel.
- Палитра процедурного HUD: **0.0** вне токенов; сцена/аватары/рубашки/иконки/AA исключены по контракту.
- Ошибки размещения/обрезания текста: **0**. Ширины всех подписей и переносы сохранены.
- Gray-пары own-start/own, own/wait, damage/own, fallen/own, ai/wait измерены по нативному кропу: проверяется ≥ 20 luma или форма. Все PNG — RGBA, цвет/серый пары есть.
- Исходники рендера неизменны: **True**, полный hash-after для 1244 файлов снимка; writes вне разрешённых корней: `[]`. Это аудит действий данного скрипта, не сравнение чужих параллельных изменений. Git не использован.
- Метаданные происхождения: заголовок prompt объявлен provenance-only и не входит в Task. `hud.csv` — живая очередь задач, а не источник макета. Её первоначальный hash сохранён; изменение после снимка явно записано в `verification.json/provenance_changed`: [{"path": "docs/game-design/visual/06-tasks/hud.csv", "before": "6a8262d2881ecefd535d40a3b6f8a8863b67df1abb13ee20431a9ff43eb80a84", "after": "c2d129300e81f0ace128cb8565595985e1335167266238b10a5496bef62ebe12", "reason": "Live task-card provenance from header; not an input to rendering. Not written by this run."}]. Этот файл данным запуском не изменялся; baseline не перебазирован.
- Непройденные критерии: **нет**. Известные исключения — тление и компакт S; отсутствующая opp-строка и Medusa heal перечислены выше.
- Макеты офлайн: не доказывают реализацию анимации/интерфейса в клиенте. Числа HP/карты взяты из разных разрешённых кадров run I; фон — bench, а не игровая запись. Unreal и сборки не запускались.

## Хеши и воспроизведение

`source-hashes-before.json` записан до копирования генератора/создания макетов. `verification.json` содержит все hash-after и несовпадения с префиксами задания. Manifest покрывает **каждый файл обеих папок**, кроме себя, и пишется последним. После правки README/проверок его необходимо пересчитать.

Запуск из корня проекта: `python -B -X utf8 art/imagegen/hud-panels-v1-codex/_tools/build_panels.py`. Проверка: `python -B -X utf8 art/imagegen/hud-panels-v1-codex/_tools/verify_package.py`.

Различия хешей относительно карточки: нет для именованных файлов; полный снимок входов зафиксирован.

Визуальная проверка финальных PNG: Технический осмотр Codex выполнен: открыты цветные и серые листы PANEL-LOC/PANEL-OPP обеих досок и размеров, кольца Sarpedon с аватаром и монограммой, оба overlay, контактные листы и полные холсты S sidekick-fallen. Финальное визуальное ревью выполняет Claude..

## Исправления fix1

1. PANEL-OPP: HP и помощники у левого края, трекер в середине → общая правая граница колонки рядом с кольцом, трекер слева; Harpies 1–3 слева направо.
2. S sidekick-fallen: сердце на аватаре, 1:0/1 → отдельная подсказка со всеми строками hud.panel.sidekick, без мини-портретов. Дельты CX-01r приведены выше: Marmoreal [16, 416, 180, 104] su, Sarpedon [16, 472, 180, 48] su. Обе подсказки помещаются над PANEL-LOC с нулевым пересечением масок, включая нижние левые клетки Sarpedon.
3. Sarpedon: нейтральный King Arthur 17/18 → 18/18; damage 17/18, heal 18/18, fallen 0/18.
4. VS_AI: малый круг → заполненный диск 8 su цвета text.secondary, зазор 5 su, центр по строке ИИ ДУМАЕТ.
5. README и visual_review: повреждённый текст → русский UTF-8 и нормальные пробелы. Финальное визуальное ревью — Claude.

Значения до исправлений и хеши всех файлов сохранены в fix1-before.json. Source-hashes-before.json сохранён побайтово.

Расчётный контраст обода пустого трекера при opacity 0,6 относительно navy: **3.062:1**. Цвет и форма исходной принятой иконки сохранены.

## Ревью Claude (2026-10-06, CX-09, VS-2, единственный проход, по делегированию)

Итог: **принято по делегированию** как макет портретных панелей для HB-18…HB-21 (`UUmHudPlayerPanel`, `UUmHudOppHand`). Статус пакета остаётся «предложено». Дельты CX-01r (OPP-HAND в классе S 220×104 su, подсказка помощников в классе S) переносятся в 04 §1.6 и §2.2 отдельным шагом документа.

История:
- Перед прогоном исправлена карточка HB-17 в `06-tasks/hud.csv`. Фон Marmoreal заменён на кадр с нарисованным задником `-ConceptPaste` (`marmoreal-concept-flag/bench-K1`, sha256 `aeafe8f2…`, ВР-VS2-01); кадр `p7c/packaged-marmoreal` (3D P5c) запрещён. Прямоугольники взяты из принятого CX-01r (a59af59d), имена — из БД (ВР-VS2-02). Слово «уточнить» на макете запрещено. Добавлены правила P1–P10. Задание: `06-tasks/prompts/HB-17.codex.md`.
- Прогон 1: 12:55–13:10. Ревью: fix-needed, пять правок:
  - PANEL-OPP был зеркален наполовину: HP и помощники стояли у левого края, трекер висел в середине;
  - в классе S sidekick-fallen сердце павшего стояло поверх аватара и окна кольца, подпись «1:0/1» не по StringTable;
  - на Sarpedon у King Arthur было 17/18 во всех состояниях вместо 18/18 из прогона I и HB-07;
  - точка «ИИ думает» была около 4 su, её почти не видно;
  - в README и `verification.json` были «????» и слипшиеся числа.
- Корректирующий прогон fix1: 13:16–13:29, задание `06-tasks/prompts/HB-17.fix1.codex.md`. Все пять правок сделаны, остальное не менялось.

Что проверено:
- **Рамки задачи.** `git status --porcelain` основной копии до и после обоих прогонов. Codex создал только эту папку и `scraped-data/derived/hud-panels-v1-codex/` (папка в `.gitignore`). Поиск файлов новее отметки старта: вне этих папок изменены только чужие файлы параллельных сессий (`hud-hand-v1-codex`, `hud-topstrip-v1-codex`, их задания) и мои `hud.csv`, журнал трат. В `unreal/` правок нет, git-команд нет, HEAD не сдвинулся, индекс пуст. `outside_folder: []`, `source_unchanged: true`, 1243 входных файла не изменились.
- **Файлы.** `manifest-sha256.json`: 203 файла, хеши пересчитаны независимо, все совпали, лишних файлов нет. `_tools/verify_package.py` запущен ещё раз: PASS, `failures: []`. Пакет без scraped-data — 7,1 МБ, PNG больше 5 МБ нет. Генераций 0, `generation-records.json` пуст.
- **Кадры.** Открыты 64 из 74 цветных финалов: все состояния обеих досок на 1920×1080 / 100 % и все состояния Marmoreal на 1280×720 / 150 %. Состояния Sarpedon на 720p открыты выборочно, остальные — на листах состояний. Все 12 цветных листов состояний открыты после прогона 1; после fix1 повторно открыты листы PANEL-OPP обеих досок (1080p) и PANEL-LOC обеих досок (720p). Также открыты серые листы (Marmoreal loc 1080p, Sarpedon loc 720p, Sarpedon opp 1080p), листы кольца по времени (Marmoreal и Sarpedon, аватар и монограмма, цвет и серый) и оба overlay. Результат:
  - фон Marmoreal — нарисованный задник, Sarpedon — `lit3d`; на обоих шесть фигур v2. Фон вне трёх блоков не тронут (проверка пиксель-в-пиксель в верификаторе);
  - слова «уточнить» нет, обрезанных подписей и многоточий нет;
  - PANEL-OPP после fix1 зеркален: аватар справа, имя, статус, HP и ряд помощников — по одной правой границе, трекер снаружи слева;
  - аватар и окно кольца ничем не перекрыты ни в одном состоянии (1859 проверок верификатора);
  - свой ход отличим в сером: «ВАШ ХОД» против «ЖДЁТ», кольцо против его отсутствия, заполненные слоты трекера. Павший — сердце с крестом и «ВНЕ ИГРЫ»;
  - красной заливки панели нет, цвет команды на портрете не используется, `marker-turn-ring-team` не используется;
  - мазков, брызг, бликов и чужих элементов нет.
- **Замеры** (`verification.json`, формат 07 §1.2):
  - перекрытие с масками фигур и клеток — 0 px² на всех 74 холстах;
  - минимальный текст на 720p — 16 px (номинал 15,75 px при 14 su);
  - контраст текста — не ниже 7,59 : 1;
  - палитра процедурного слоя — 0 пикселей вне токенов;
  - тление обода — 1,78 : 1 при 0,35 и 2,75 : 1 при 0,55. Это известное исключение карточки, его закрывает статус «ВАШ ХОД».
- **Данные.** Каждый текст трассируется в `facts.json`: StringTable `st-hud.csv`, скрап героев, проверка БД, строки трасс прогона I. Использованы строки 1504 и 1606 хоста Marmoreal (два манёвра Medusa, turnCount 3) и строки 335 и 883 клиента King Arthur на Sarpedon (две атаки). Числа, которые задаёт само состояние (0/16, 0/18, 0/1, 0/7, 3 и 10 рубашек, «≈»), помечены «состояние макета».

Решения ревью (по делегированию, серия ВР-VS2; ВР-VS2-CX09-01…05 записаны в карточке HB-17, колонка do):

| ВР | Решение | Почему |
|---|---|---|
| ВР-VS2-CX09-01 | Владелец HUD как в ВР-VS2-03: Marmoreal — свой Medusa, соперник King Arthur; Sarpedon — свой King Arthur, соперник Medusa | Одна раскладка с принятым HB-07 |
| ВР-VS2-CX09-02 | Лечение рисуется только на Sarpedon (King Arthur 17/18 → 18/18). Макет лечения Medusa на Marmoreal не делается и записан в `uncertain_values` | В прогоне I нет пары HP лечения Medusa |
| ВР-VS2-CX09-03 | HP 0 павших, 3 и 10 рубашек и «≈» — «состояние макета», не данные партии. Колода и сброс в подписи OPP-HAND — числа прогона I своей доски | Иначе пришлось бы выдумывать числа партии |
| ВР-VS2-CX09-04 | Монограмма — правило клиента `S09TurnHud::Monogram`: «KA», «M» | `S09TurnHudTests.cpp:121-122` |
| ВР-VS2-CX09-05 | Размер значка, которого нет в `sizes/` (окно кольца 104 и 90 px, 26–30 px), — из мастера и слоёв v3 одной передискретизацией Lanczos | Форма и цвет принятых глифов не меняются |
| ВР-VS2-CX09-06 | В классе S состояние «помощник пал» показывается подсказкой портрета над PANEL-LOC: (16, 416, 180, 104) su для Marmoreal и (16, 472, 180, 48) su для Sarpedon, зазор 8 su. Строки `hud.panel.sidekick`, гарпии — «Harpies 1…3» по порядку sidekicks | 04 §2.2: в S помощники живут в подсказке портрета. Поверх аватара ничего не рисуется |
| ВР-VS2-CX09-07 | В PANEL-OPP в состоянии «его ход» строка статуса пуста. Ход соперника показывают кольцо и видимый трекер. Новую строку в этом пакете не придумываем | В `st-hud.csv` нет ключа статуса чужого хода. Ключ (предложение — `hud.panel.status.opp`) решается в HB-18 вместе с 04 §2.3 |
| ВР-VS2-CX09-08 | Тление 0,55 в классе S принимается как предложение, 0,35 в L не меняется. Окончательное значение — по живым кадрам 720p в HB-18 (ВР-43) | На листах S обод 0,35 почти теряется. Это решение по живому кадру, а не по макету |

Не входит в приёмку и остаётся открытым:
- **Подписи фигур на фоне.** На bench-кадрах есть старые подписи у фигур («Medusa 16/16» и другие). Это артефакт фона, не данные HUD (как в HB-07).
- **Состояние партии.** Значения взяты из разных моментов прогона I, синхронного снимка нет.
- **Строка статуса чужого хода.** Ключа нет (ВР-VS2-CX09-07).
- **Лечение Medusa.** Пропущено (ВР-VS2-CX09-02).
- **Лист приёмки.** `docs/game-design/evidence/VISUAL/HB-17/` (overlay без аватаров, `sheet.py`) — следующий шаг цикла, не часть пакета.
- **Манифест.** Строка README в `manifest-sha256.json` — хеш до этого раздела ревью (`34ba7ce0…`); остальные файлы пакета после fix1 не менялись. Так же сделано в HB-07.
