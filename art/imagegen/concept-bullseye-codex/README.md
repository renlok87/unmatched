# Концепт-пакет ASSET-BULLSEYE-001

Этап 1a, статус: **предложено** (`proposed`). Художественная приёмка не выполнялась и не заявляется.

## Исправление происхождения без генераций

Дата: 2026-10-13T10:37:33+00:00. Все вызовы генераторов в этом запуске: **0**, в том числе ImageGen: **0**. Генерации и ретраи запрещены. Браузер, git, Unreal, Tripo и SYNTX не запускались.

Авторитетный источник этой волны — уже существовавший `design/bullseye-front.png`, SHA256 `bea7253991b97489a90cf0ff78b3facd7a49f6acdc02d7c2b4dba5367d9f42e1`. Исторический `verification.json#design_source.post` документирует нормализацию фона Claude через `C:/tmp/concept-wave/rebg.py`. Этот скрипт сейчас не открывался и не выполнялся. Исторические сведения о внешней генерации unstability.ai и прежних отказах сервисов сохранены в архиве; они не относятся к вызовам этого запуска.

Выбран новый неизменяемый кандидат **g2**: `art/imagegen/concept-bullseye-codex/concepts/bullseye-design-front-g2.png`. Он зарегистрирован простым побайтным копированием текущего нормализованного дизайна. `original_path` указывает на этот существовавший дизайн, а не на вымышленный выход ImageGen. Нормализованный PNG выбран по прямому указанию пользователя, а не по новой визуальной оценке. Записей в реестре: **2** — одна историческая внешняя генерация и одна регистрация без генерации.

Исторический кандидат `concepts/bullseye-design-front-u1.png` и `design/bullseye-front-raw.png` имеют другие хеши и сохранены без изменений. Побайтная или пиксельная цепочка между u1 и raw не восстанавливалась; происхождение нормализации основано на архивном документе, а регистрация — на проверяемом SHA256 текущего дизайна. Все прежние поля записей сохранены; изменены только флаги `selected`.

## Проверки

- кандидат g1: код `1`, отчёт `art/imagegen/concept-bullseye-codex/checks/design-front-g1/checks-report.json`; FAIL: view.border_uniform, view.side_margin.
- исторический raw (не отдельная генерация): код `1`, отчёт `art/imagegen/concept-bullseye-codex/checks/historical-raw/checks-report.json`; FAIL: view.border_uniform, view.side_margin.
- кандидат g2: код `0`, отчёт `art/imagegen/concept-bullseye-codex/checks/design-front-g2/checks-report.json`; FAIL: нет.
- финальная проверка текущего дизайна: код `0`, отчёт `art/imagegen/concept-bullseye-codex/design/checks-report.json`; FAIL: нет.

Для каждого кандидата использован временный набор внутри пакета с побайтной копией под именем `bullseye-front.png`. Временные копии после проверки удалены; их совпадение с источниками записано в verification.json. Авторитетный дизайн не подменялся. Последний вызов checker проверил именно `design/bullseye-front.png` без `--out` и обновил `design/checks-report.json`. Исторические FAIL сохранены как история, без перегенераций.

## Ограничения и малые решения

- Полный визуальный чек-лист сейчас не переоценён: изображения разрешены только для хеширования и checker. Неподтверждённые пункты имеют `passed=false` с явной пометкой «не подтверждено», а не утверждением об обнаруженном дефекте; они перечислены в `limit_reached` при бюджете 0.
- Аспект существующего PNG: 1280×1600, 4:5 вместо требуемого 3:4. PNG не менялся. Автопроверка одного вида это отклонение не оценивает.
- Точный внешний промпт взят из прежней записи unstability.ai и скопирован в новый ключ `1a/design-front/g2`. Это исторический промпт, не CORE ImageGen; он не выполнялся сейчас. Image-reference исторически отсутствовал; другие пакеты не открывались.
- Raw проверен дополнительно как исторический промежуточный файл, без добавления отдельной записи генерации. Для u1 папка checker названа g1 по его неизменённому `attempt=1`.
- Изменяемые исходные метаданные сохранены побайтно в `art/imagegen/concept-bullseye-codex/archive/metadata-only-20261013T103733672540Z` до обновления. Отсутствовавшие prompts.md, prompts/concept-prompts.json, source-hashes-before.json и manifest-sha256.json созданы заново. Палитра неизменна.

Все три существовавших PNG сохранили SHA256 и размеры файлов; новый g2 совпадает с текущим дизайном. `outside_folder=[]`. Manifest записывается последним и содержит хеши и размеры каждого файла пакета, кроме самого себя.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/bullseye-design-front-rc1.png`, `concepts/bullseye-design-front-rc2.png`. Выбран `bullseye-design-front-rc2.png` → `design/bullseye-front-raw.png` → фон выровнен `rebg.py` → `design/bullseye-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (5.0). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-BULLSEYE-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
