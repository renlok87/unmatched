# SC-38 · Партия прервана

**Статус: предложено.**

Рекомендован `shown`: реальная партия ONE_V_ONE, Marmoreal original, ProGamer остаётся, Veteran выходит. ABORTED и GAME_ABORTED/player_left, ник Veteran и ход 1 взяты из неизменённого aborted-game.json. Имеющаяся строка БД соответствует запрошенному сценарию S09; новую партию запускать не потребовалось. Старый S10 VS_AI/ход 13 заменён данными серии и не используется.

`shown-noname` — раскладка без доступного имени; ход 1 сохранён. Имя не придумано и не заменено заглушкой. Отдельная модаль 640×360 su, центральная колонка 214 su: 48 +16 +28 +12 +16 +8 +14 +24 +48. Скрипт независим от GAMEOVER, скопированы только две обязательные библиотеки.

Исходный Marmoreal P7: painted backdrop, реальная карта и шесть v2 фигур. Под сценой нет CUE-016 grade (gains 1/1/1, saturation 1, vignette 0); veil 0.6, Modal skin opacity 1. Надписи с победой и поражением отсутствуют. Жёлтый используется только у primary «В ЛОББИ», это цвет действия, не исхода. Красный только у X resource-connection-lost. K1 содержит исходные bench name plates и стоящую павшую фигуру; это артефакты фона, не новые UI строки. В игре frozen HUD был бы под veil; K1 не содержит HUD, поэтому он не выдуман.

HB-08 Modal, BtnPrimary_Normal и KeyChip через неизменённый SC-01. KeyChip Enter — отдельный элемент 20 su высотой, ширина text+8, type.tag 14; режим подсказок «Вкл» (правило Auto/CompletedMatches=0 описано серией). Без курсора, hover и focus; финальная непрозрачность модали 1. Motion в PNG не моделируется. resource-connection-lost ровно 48 su: готовый размер при совпадении, иначе unchanged render(name, px), без resize, NEAREST и library.spinner().

Все размеры через Viewport.preset: DPI 1.0/0.75 × UI 1/1.5. Минимум 14 su =10.5 px на 720p/100. Цветные и серые PNG RGBA, серые строго Rec.709. Сравнения сохраняют исходное разрешение каждой строки. Overlays на card.navy, только линии и BindWidget+x/y/w/h, без board/hero pixels; пересечение подписей 0.

Модаль и veil отдельно отмечены modal/exempt; фактическое перекрытие HB-07 masks записано, persistent layers отсутствуют, их перекрытие 0. Контраст каждого текста против собственного фона, границ по реальным финальным пикселям и glyph/X в color/gray находится в verification.json.

## Что не прошло

Проваленные критерии: edges_and_icons_ge_3. Минимальный измеренный контраст границы 1.683:1. Принятый полупрозрачный hairline местами ниже 3:1 против кадра. Минимум контраста X в исходной иконке в сером финале 2.358:1, тоже ниже 3:1. Скин и иконка не перекрашены и не усилены: конфликт входного ассета и порога честно отмечен. Текст и одноцветная читаемость проверены отдельно.

## String-table delta

| key | RU | EN |
|---|---|---|
| screens.aborted.who.unknown | Соперник покинул партию | The opponent left the game |

Существующие строки: screens.aborted.title, .who, .turn, .lobby, столбец ru st-screens.csv. Таблица не изменена. Неиспользованные hero names из БД не переводились; content-matrix RU ждёт отдельную задачу.


## Макеты и листы

- [SC-38-shown-1080p-100.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-1080p-100.png)
- [SC-38-shown-1080p-100-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-1080p-100-gray.png)
- [SC-38-shown-noname-1080p-100.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-1080p-100.png)
- [SC-38-shown-noname-1080p-100-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-1080p-100-gray.png)
- [SC-38-overlay-1080p-100.png](comparison/SC-38-overlay-1080p-100.png)
- [SC-38-overlay-1080p-100-gray.png](comparison/SC-38-overlay-1080p-100-gray.png)
- [SC-38-comparison-1080p-100.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-1080p-100.png)
- [SC-38-comparison-1080p-100-gray.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-1080p-100-gray.png)
- [SC-38-shown-1080p-150.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-1080p-150.png)
- [SC-38-shown-1080p-150-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-1080p-150-gray.png)
- [SC-38-shown-noname-1080p-150.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-1080p-150.png)
- [SC-38-shown-noname-1080p-150-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-1080p-150-gray.png)
- [SC-38-overlay-1080p-150.png](comparison/SC-38-overlay-1080p-150.png)
- [SC-38-overlay-1080p-150-gray.png](comparison/SC-38-overlay-1080p-150-gray.png)
- [SC-38-comparison-1080p-150.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-1080p-150.png)
- [SC-38-comparison-1080p-150-gray.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-1080p-150-gray.png)
- [SC-38-shown-720p-100.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-720p-100.png)
- [SC-38-shown-720p-100-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-720p-100-gray.png)
- [SC-38-shown-noname-720p-100.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-720p-100.png)
- [SC-38-shown-noname-720p-100-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-720p-100-gray.png)
- [SC-38-overlay-720p-100.png](comparison/SC-38-overlay-720p-100.png)
- [SC-38-overlay-720p-100-gray.png](comparison/SC-38-overlay-720p-100-gray.png)
- [SC-38-comparison-720p-100.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-720p-100.png)
- [SC-38-comparison-720p-100-gray.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-720p-100-gray.png)
- [SC-38-shown-720p-150.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-720p-150.png)
- [SC-38-shown-720p-150-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-720p-150-gray.png)
- [SC-38-shown-noname-720p-150.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-720p-150.png)
- [SC-38-shown-noname-720p-150-gray.png](../../../scraped-data/derived/sc38-aborted-codex/SC-38-shown-noname-720p-150-gray.png)
- [SC-38-overlay-720p-150.png](comparison/SC-38-overlay-720p-150.png)
- [SC-38-overlay-720p-150-gray.png](comparison/SC-38-overlay-720p-150-gray.png)
- [SC-38-comparison-720p-150.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-720p-150.png)
- [SC-38-comparison-720p-150-gray.png](../../../scraped-data/derived/sc38-aborted-codex/comparison/SC-38-comparison-720p-150-gray.png)

## fix1

CX-34 fix1, 2026-10-08. Статус остаётся **предложено**. Каждый контур на схеме снабжён номером своей легенды: Roboto Regular не менее 14 px, text.primary на card.navy, keyline panel.edge 1 px. Тег в левом верхнем углу внутри, а при нехватке места — снаружи с линией 1 px. Легенда вынесена в добавленное поле справа; масштаб схемы сохранён 1:1. Измеренные пересечения тегов друг с другом и с легендой: 0; пересечения подписей: 0.

Перегенерированные PNG (каждый повторно открыт отдельно, цвет и Rec.709 серый):

- [SC-38-overlay-1080p-100.png](comparison/SC-38-overlay-1080p-100.png)
- [SC-38-overlay-1080p-100-gray.png](comparison/SC-38-overlay-1080p-100-gray.png)
- [SC-38-overlay-1080p-150.png](comparison/SC-38-overlay-1080p-150.png)
- [SC-38-overlay-1080p-150-gray.png](comparison/SC-38-overlay-1080p-150-gray.png)
- [SC-38-overlay-720p-100.png](comparison/SC-38-overlay-720p-100.png)
- [SC-38-overlay-720p-100-gray.png](comparison/SC-38-overlay-720p-100-gray.png)
- [SC-38-overlay-720p-150.png](comparison/SC-38-overlay-720p-150.png)
- [SC-38-overlay-720p-150-gray.png](comparison/SC-38-overlay-720p-150-gray.png)

SHA-256 до/после каждого mockup и всех derived-файлов: `verification.json` → `mockup_unchanged`; любая незапрошенная разница считается ошибкой. Замеры run 1 сохранены в `fix1.run1_measurements` и `fix1-before.json`. Общий sc34_gameover_victory.py и его SC-35/36/37 копии не менялись; copy-provenance остаётся true. Исходные ограничения контраста скинов/иконок сохранены; они не входят в коррекцию fix1.

Обновлены `README.md`, `verification.json`, `visual-review.json`, `manifest-sha256.json`; добавлен неизменяемый снимок исходных хешей и замеров `fix1-before.json`. Общая коррекция находится в SC-34 `_tools/fix1.py` и `_tools/fix1_overlays.py`. Геометрия макетов и скрипты run 1 сохранены.

## Воспроизведение

`python -B art/imagegen/sc34-gameover-victory-codex/_tools/fix1.py --render` — воспроизвести ровно correction fix1 для пяти пакетов (сбрасывает осмотр изменённых PNG). После прямого открытия каждого перечисленного PNG: `--finalize`. `--check` — полная проверка fix1 без записи. Нужны уже установленные Pillow/NumPy; установки пакетов, сеть, Git, MCP и unreal/ не используются.

Примечания воспроизведения run 1 (архив; для текущих исправлений используется команда выше):

## Воспроизведение и отчёты

`python -B art/imagegen/sc38-aborted-codex/_tools/sc38_aborted.py` — сборка только в две разрешённые папки, inputs/ никогда не меняется. Pillow+NumPy; no network, imagegen, MCP, Git, engine. source-hashes-before.json, copy-provenance.json, layout-geometry.json, verification.json, visual-review.json и manifest-sha256.json содержат текущие SHA-256, геометрию и результаты. Иконки записаны tree digest/count без повторения всех per-file hashes. Общая повторная проверка пяти пакетов: [series-audit.json](series-audit.json). Команда: `python -B art/imagegen/sc38-aborted-codex/_tools/audit_series.py`; сверяет каждый входной и выходной хеш, полноту manifests, неизменность копий, RGBA/размеры/Rec.709, просмотр всех 144 PNG и стабильность busy-геометрии. Записывает только отчёт и manifest SC-38.

## Ревью 2026-10-08 (Claude, единственный проход 07 §5, по делегированию)

**Вердикт: принято** — художественно, по делегированию (пользователь 2026-10-06: «Все решения принимай»). Серия
CX-34 (SC-34…SC-38 в одном чате Codex) прошла один корректирующий прогон; второго не будет (05 §1.4).

- **Прогон 1** (CX-34, 2026-10-07 23:13–23:59 +05:00, Codex `01a11792-509b-…`, `SC-34-series.codex.md`): fix-needed.
  Схемы `comparison/` не были связаны с легендой (на контурах не было номеров); в SC-37 при классе S ряд из трёх
  кнопок не помещался в модаль 680 su (около 8 su до кромки при минимуме 16 su), чипы клавиш были сняты.
- **Прогон fix1** (2026-10-08 00:01–00:19 +05:00, Codex `01a117bd-aa21-…`, `SC-34-series.fix1.codex.md`): номера на
  каждом контуре (пересечений 0; отдельные схемы draw и busy), SC-37 класса S — модаль 760×560 su (ВР-VS5-SC37-06),
  чипы «V» и «Enter» возвращены, ряд проходит. Изменились только 8 макетов SC-37 класса S и 4 листа сравнения из них
  (sha256 всех 109 файлов derived сверены Claude с прогоном 1).

Что проверено:
- Рамки: `git status --porcelain` основной копии до и после обоих прогонов — Codex создал только пять папок пакетов и
  `scraped-data/derived/sc34…sc38-*-codex/` (`inputs/` положил Claude, Codex их не менял); поиск файлов новее маркера
  запуска вне этих папок — 0; индекс пуст, HEAD `9810a253` не менялся; git, MCP, сеть и `unreal/` не использовались.
- `verification.json`: ключи 07 §1.2, `outside_folder: []`, `source_unchanged: true`; сверка Claude — все sha256
  манифестов совпали, файлов вне манифестов нет; `screen_mockup_base.py` = SC-01 (`d970f881…`),
  `draw_icons_v3_snapshot.py` = `draw_icons.py` (`353da947…`). Манифесты SC-35…SC-37 хранят хэши файлов SC-34 в том
  виде, в каком Codex их читал (до этой записи ревью).
- Данные: run I Marmoreal host (`RESULT summary … turn=11 duration=27`, Medusa 11/16, King Arthur 0/18), run I
  Sarpedon joiner (`DEFEAT … turn=5 duration=13`, Medusa 14/16, King Arthur 0/18), run F vs-ai Marmoreal
  (`… loserHero=T._Rex … turn=19 duration=33`, Medusa 14/16, T. Rex 0/27, соперник AI Bot; строка партии FINISHED,
  33,0 с); ABORTED — настоящая строка ONE_V_ONE на Marmoreal original: Veteran вышел (`GAME_ABORTED`, `player_left`),
  ход 1, зритель ProGamer (чтение эталонной БД в режиме READ ONLY 2026-10-07, новых партий не создавалось). Кадры
  результата run I и run F сверены глазами (HP и время совпали). Имена героев — из данных (Medusa, King Arthur,
  T. Rex; ВР-VS2-02). Строки — RU `st-screens.csv`; «уточнить» нет; в кадре draw числа не рисуются (настоящей ничьей
  нет), это записано.
- Не пройдено буквально и принято как известное: кромки принятых скинов HB-08 на navy ниже 3 : 1 (то же ограничение,
  что у принятых SC-03, SC-19, SC-31…SC-33 и SC-24…SC-30); значки на мелких размерах (красный крест
  `resource-hp-fallen` и X `resource-connection-lost` в сером) 2,4–2,5 : 1. Текст ≥ 8,7 : 1, кроме «ПОРАЖЕНИЕ»
  (`state.error` 48 su — 3,21 : 1; по 04 §3.7 / 02 §3.5 крупному тексту ≥ 24 su Bold достаточно 3 : 1); кегль на
  720p ≥ 10,5 px; одна главная кнопка на окно; красного вне заголовка поражения и знаков значков — 0; портрет
  проигравшего — насыщенность 0, прозрачность 0,6, без красного. Подписи фигур, стоящий павший герой и 3D-окружение
  внутри исходных кадров K1 — артефакт заданного фона.
- Кадры открыты (Read): shown и shown-noname — все 16 листами 2×2 (цвет и серый); схемы после fix1 листом.
- Вид: модаль 640×360, значок `resource-connection-lost` 48 su, «Партия прервана», «Игрок Veteran покинул партию» /
  «Соперник покинул партию», «Ход 1», «В ЛОББИ» + Enter (главная); без грейда, без слов и цветов победы или
  поражения.

Решения серии: ВР-VS5-SC34-01…09, ВР-VS5-SC35-01…02, ВР-VS5-SC36-01…03, ВР-VS5-SC37-01…06, ВР-VS5-SC38-01…04
(задания `SC-34-series.codex.md`, `SC-34-series.fix1.codex.md`). Предложенные ключи строк (дельта):
`screens.result.board.turn`, `screens.result.again.busy`, `screens.aborted.who.unknown`. UE-часть
(`UUmScreenGameOver`, `UUmScreenAborted`, `WBP_UI_SCR_GAMEOVER`, `WBP_UI_SCR_ABORTED`, постпроцесс CUE-016, строки
`screens.result.*` / `screens.aborted.*`, тесты экранов) — план VS-7.
