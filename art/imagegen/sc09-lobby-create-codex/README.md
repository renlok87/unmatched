# SC-09 — макеты лобби, fix1

Статус: **предложено**. Рекомендуется исправленный вариант на принятых скинах HB-08 и библиотеке SC-01: данные сохранены, схемы показывают состояния этой карточки; исправленный общий модуль списка скопирован без изменений.

## Состояния

- `create-marmoreal` — 1×1, выбрана Marmoreal, «СОЗДАТЬ» — основная кнопка.
- `create-sarpedon` — Выбрана Sarpedon; остальные элементы доступны.
- `busy` — Marmoreal; «СОЗДАЁМ…», спиннер 32 su и курсор ожидания; подсказка why.syncing.

## Данные

Никнейм **ProGamer** — `inputs/available-games.json`, поле `viewer.username` (источник: `backend/prisma/seed.ts`, строка 34). Две доски — ответы `adminBoard` в `inputs/all-boards.json`: `c121b47f8d6eb28daccb76d05`, **Marmoreal · original map**; `c7fa64a26c29a0835f2383e63`, **Sarpedon · original map**. Иллюстрации взяты целиком из `scraped-data/images/maps/`, без обрезки, названия под ними. Публичный каталог не используется.

Список — пять строк t0 из `inputs/available-games.json`, в порядке ответа: **VZSJFT, EK74C3, QSMFTR, 4XM89G, ZJ4LXZ**. Режим 1×1; у трёх доступных комнат 1/2 мест. После t0 ответы `joinGame` в `inputs/list-join-errors.json`: 4XM89G — «Игра уже заполнена» → why.room.full «Комната заполнена»; ZJ4LXZ — «Нельзя присоединиться к игре, которая уже началась или завершилась» → why.room.started «Игра уже началась». У них нет кнопки и значения мест, причина видна и записана как подсказка; следующий опрос удаляет эти строки.

Диски 32 su: King Arthur (`cmq7d7b1000njwi74a536w55r`) и Medusa (`cmq7d7b4000r8wi74tzd1jmxv`) из ответов `adminHero` в `inputs/heroes.json`; портреты CP-01, обрезка CP-07 B, без командного кольца.

## Решения и измерения

Применены ВР-VS4-SC08-01…16 и ВР-VS4-SC09-01…03: реальные карты и данные, скины, фиксированная сетка, состояния, подпись фона ВР-75, отступы строк, схемы и описание этой карточки. K1 под одной вуалью 0.6 — исторический фон-заглушка; это офлайн-макеты. Типографика не уменьшена; переносы и измерения текста соответствуют состояниям этой карточки. Звуки и shake не рисуются.

Минимум контраста текста **4.751:1**; наименьший текст при 720p **10.5 px**. Минимальный отступ содержимого строки **8.000 su**; код начинается в 16 su, кнопка/причина заканчивается в 8 su от рамки. Текстовых пересечений и обрезаний: 0. В каждом состоянии на каждом холсте ровно одна основная кнопка.

Минимальная измеренная граница панелей **2.1273:1**, ниже 3:1 на части растровых отсчётов. Ограничение принятых неизменяемых HB-08/SC-01 сохранено: критерий кромок и общая приёмка — **false**, остальные проверки перечислены отдельно. У основной кнопки контраст даёт внутренняя жёлтая граница; внешняя navy-кромка на navy — 1:1. Неактивные кромки записаны без подмены значений.

Значка обновления в принятом v3 нет: в состояниях с обновлением «ОБНОВИТЬ» текстовая; в ошибке SC-13 она скрыта. Для глифа нужна новая карточка IC. Условная RecoverButton скрыта по пустому myGames: на L её пунктирный резерв расположен внутри CodeColumn, на S места нет — только пояснение в легенде.

## fix1

Скопирован окончательный модуль списка SC-08 с исправленными отступами и шириной колонок; отступы проверяются там, где состояние показывает строки. Каждая схема содержит отдельную страницу состояния, локальные подписи и полную легенду x/y/w/h в su; только фон card.navy, контуры и подписи, без карты, портретов и K1. README переписан для этой карточки. Копии SC-01 и генератора иконок побайтно сохранены.

## Файлы

| Холст | Схемы всех состояний | Макеты |
|---|---|---|
| 1080p-100 | [цвет](comparison/SC-09-overlay-1080p-100.png) / [серый](comparison/SC-09-overlay-1080p-100-gray.png) | [create-marmoreal](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-1080p-100.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-1080p-100-gray.png) · [create-sarpedon](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-1080p-100.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-1080p-100-gray.png) · [busy](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-1080p-100.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-1080p-100-gray.png) |
| 1080p-150 | [цвет](comparison/SC-09-overlay-1080p-150.png) / [серый](comparison/SC-09-overlay-1080p-150-gray.png) | [create-marmoreal](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-1080p-150.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-1080p-150-gray.png) · [create-sarpedon](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-1080p-150.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-1080p-150-gray.png) · [busy](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-1080p-150.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-1080p-150-gray.png) |
| 720p-100 | [цвет](comparison/SC-09-overlay-720p-100.png) / [серый](comparison/SC-09-overlay-720p-100-gray.png) | [create-marmoreal](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-720p-100.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-720p-100-gray.png) · [create-sarpedon](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-720p-100.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-720p-100-gray.png) · [busy](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-720p-100.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-720p-100-gray.png) |
| 720p-150 | [цвет](comparison/SC-09-overlay-720p-150.png) / [серый](comparison/SC-09-overlay-720p-150-gray.png) | [create-marmoreal](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-720p-150.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-marmoreal-720p-150-gray.png) · [create-sarpedon](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-720p-150.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-create-sarpedon-720p-150-gray.png) · [busy](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-720p-150.png) / [серый](../../../scraped-data/derived/sc09-lobby-create-codex/SC-09-busy-720p-150-gray.png) |

Воспроизведение: `python -B art/imagegen/sc09-lobby-create-codex/_tools/sc09_lobby_create.py`. После осмотра каждого экспортированного PNG выполнить `python -B art/imagegen/sc09-lobby-create-codex/_tools/fix1_audit.py finish` (README, visual-review и хеши), затем `python -B art/imagegen/sc09-lobby-create-codex/_tools/verify_outputs.py`. Осмотр всех финальных PNG в цвете и сером отражён в visual-review.json. Хеши входов и выходов — manifest-sha256.json; исходное состояние до исправления — fix1-baseline.json. В verification.json блок fix1 содержит изменения и SHA-256 до/после. Для двух самоссылочных JSON применяется явно описанная нормализация; полный байтовый хеш verification.json есть в манифесте.

Git, сеть, MCP, Unreal, генерация изображений и фоновые процессы не использовались. Запись ограничена папкой пакета и соответствующей derived-папкой; inputs/ не изменялась.

## Ревью 2026-10-07 (Claude, единственный проход 07 §5, по делегированию)

**Вердикт: принято** — художественно, по делегированию (пользователь 2026-10-06: «Все решения принимай»). Серия
CX-29 (SC-08…SC-13 в одном чате Codex) прошла один корректирующий прогон; второго не будет (05 §1.4).

- **Прогон 1** (CX-29, 2026-10-07 11:38–11:58 +05:00, Codex `01a11515-c835-…`, `SC-08-series.codex.md`): данные,
  раскладка L и S, состояния и токены приняты; fix-needed — содержимое строк списка без внутреннего отступа (код на
  левой кромке строки, кнопка «ВОЙТИ» и причина на правой; ВР-VS4-SC08-14), оверлеи общие для всех карточек, имена
  оторваны от рамок, слот RecoverButton выходил за колонку (ВР-VS4-SC08-15), README-шаблоны с повторами и
  утверждением о переносах, которых нет (ВР-VS4-SC08-16), в SC-12 вся плашка state-hint с пустым полем числа
  (ВР-VS4-SC12-02), в SC-10 на 150 % заметка ИИ вплотную к чипам (ВР-VS4-SC08-09).
- **fix1** (2026-10-07 12:06–12:27 +05:00, Codex `01a1152f-4b3e-…`, `SC-08-series.fix1.codex.md`): отступ
  содержимого строк ≥ 8 su на всех холстах (код с 16 su, кнопка и причина до правой кромки − 8 su; независимая
  сверка Claude по `layout-geometry.json` — минимум 8 su), оверлеи по состояниям этой карточки с подписями у рамок и
  легендой x/y/w/h в su, README карточки переписан; `sc08_lobby_list.py` `d46e766f…` скопирован без изменений.

Что проверено:
- Рамки: `git status --porcelain` основной копии до и после обоих прогонов — Codex создал только шесть папок пакетов
  и `scraped-data/derived/sc08…sc13-…-codex/` (журналы `file_change` обоих прогонов: 0 путей вне папок); индекс пуст,
  HEAD `97f88289` не менялся; `unreal/` не тронут; git, MCP и сеть не вызывались.
- `verification.json`: ключи 07 §1.2, `outside_folder: []`, `source_unchanged: true`, блок `fix1`; сверка Claude —
  все sha256 манифеста совпали, файлов вне манифеста нет, `inputs/` побайтно равны снимку Claude;
  `screen_mockup_base.py` = SC-01 (`d970f881…`), `draw_icons_v3_snapshot.py` = `draw_icons.py` (`30da74cc…`).
- Данные (снимки стенда S09 2026-10-07 06:29–06:30 UTC, Claude, `inputs/`): ник ProGamer (ответ login = сид,
  `backend/prisma/seed.ts` строка 34); пять строк t0 `availableGames(mode: ONE_V_ONE)` VZSJFT, EK74C3, QSMFTR,
  4XM89G, ZJ4LXZ в порядке ответа; 4XM89G и ZJ4LXZ недоступны по ответам `joinGame` «Игра уже заполнена» и «Нельзя
  присоединиться к игре, которая уже началась или завершилась»; доски — `adminBoard` c121b47f8d6eb28daccb76d05
  «Marmoreal · original map», c7fa64a26c29a0835f2383e63 «Sarpedon · original map»; герои — `adminHero` King Arthur,
  Medusa. Комнаты Claude создал на стенде сид-аккаунтами для снимка и убрал после него; стенд остановлен. Пароля и
  токенов нет ни в одном файле (поиск Claude по литералу пароля сида — 0 совпадений); `seed.ts` никуда не копировался.
  «уточнить» на макетах нет.
- Кадры открыты (Read): все финальные PNG серии после fix1 — макеты этой карточки в цвете и сером на 1080p/720p при
  100 и 150 % и все её оверлеи; после прогона 1 — выборочно и триаж-листы.
- Вид: экран LOBBY по 04 §1.3 на L, класс S по ВР-VS4-SC08-09; текст ≥ 4,5 : 1 (минимум 4,751 : 1), кегль при 720p
  ≥ 10,5 px; одна главная кнопка в каждом кадре; красный только у знака X; состояния различимы в сером формой или
  текстом; скан, карта и аватары — только в `scraped-data/derived/`, в пакете — скрипты, JSON и оверлеи на
  `card.navy` без пикселей кадра, карты и аватаров (ВР-VS4-01).

Решения ревью (по делегированию):
- **ВР-VS4-SC08-17**: граница панелей к кадру K1 под вуалью местами ниже 3 : 1 (минимум 2,13 : 1) — как
  ВР-VS3-SC01-10, ВР-VS4-SC03-10 и ВР-VS4-SC06-09: свойство принятых токенов HB-08, не пакета; граница видна в цвете
  и сером. Строка `edges and icons >=3:1` в `verification.json` честно стоит `false`; приёмку не блокирует.

Карточка SC-09: create-marmoreal (по умолчанию) и create-sarpedon — выбранный тайл `Btn_Selected` с текстом
`card.glyph`, иллюстрация карты целиком, имя доски под ней; ровно две доски, имена и id — из `adminBoard`; busy —
«СОЗДАТЬ» в `BtnPrimary_Disabled` со спиннером 32 su и «СОЗДАЁМ…», курсор «занято» на кнопке, `why.syncing` —
подсказка (геометрия). Состояние «Сервер недоступен» вне поставки (ВР-VS4-SC09-03).

Остаётся (не часть макета): UE-часть (`CreateRoom(Mode, BoardId)`, `UUmBoardChip`, миниатюры — только LAN, ВР-48),
кадры набора G — план VS-7.

Примечание ревью: после этой записи sha256 `README.md` и `manifest-sha256.json` отличаются от значений «после» в
блоке `fix1` файла `verification.json` (`verify_outputs.py` сообщает именно эти два расхождения) — так и должно
быть: Claude дописал раздел ревью и пересчитал строку README в манифесте; остальные хеши не менялись.
