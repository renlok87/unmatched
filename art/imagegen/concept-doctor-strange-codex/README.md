# Концепт-пакет ASSET-DOCTOR-STRANGE-001

Этап 1a. Статус: **предложено** (`proposed`). Этот запуск исправляет только метаданные; генераций изображений и вызовов image_gen: **0**. Художественная приёмка не выполнялась.

## Выбранный кандидат и происхождение

Выбран `art/imagegen/concept-doctor-strange-codex/concepts/doctor-strange-design-front-g3.png` (запись g3, попытка 3). Это новая неизменяемая побайтная копия уже существовавшего `design/doctor-strange-front.png`, SHA256 `6a14c00f2c022333e0bcca9a658373edef0451b0e48bab5e54dbdb57c64aff20`. Авторитетный дизайн не заменялся.

Исторический исходник получен из unstability.ai (UltraReal Fine-Tune v4 / Flux.1 D). Запись u1c описывает прежнюю очистку угловых логотипов Claude/PIL; её PNG совпадает с design/doctor-strange-front-raw.png. По прежней verification.json#design_source.post Claude затем исторически нормализовал фон через C:/tmp/concept-wave/rebg.py. Именно этот уже нормализованный дизайн зарегистрирован как g3.

Прежняя выбранная запись u1c указывала на ненормализованный кандидат. Исправлено соответствие выбранной записи текущему дизайну: старые записи сохранены целиком, изменены только selected. Новая запись честно отмечает историческую внешнюю обработку и регистрацию без генерации; original_path — абсолютный путь существующего дизайна, а не выдуманный выход ImageGen.

Точный внешний промпт взят из исходной записи u1c и скопирован в новый ключ 1a/design-front/g3. Промпты u1, u1c и g3 опубликованы в prompts/concept-prompts.json и prompts.md; ни один не выполнялся сейчас. В историческом text-to-image референсов не было, references=[] сохранён. Другие пакеты не открывались.

## Проверки и сохранность

- g1: код 1; FAIL: view.border_uniform, view.bottom_margin, view.side_margin; WARN: view.frame_top, view.single_component.
- g2: код 1; FAIL: view.border_uniform, view.side_margin; WARN: нет.
- g3: код 0; FAIL: нет; WARN: нет.

Финальная проверка текущего дизайна: код 0; отчёт design/checks-report.json. Последний запуск checker выполнен без --out. Отчёты кандидатов находятся в checks/design-front-g1, g2 и g3; входами служили временные побайтные копии doctor-strange-front.png внутри пакета, после проверок они удалены.

Исторические FAIL не исправлялись генерацией или обработкой. Все четыре исходных PNG, включая текущий дизайн, raw и оба прежних кандидата, сохранили SHA256 и размер. palette.json не изменялся. Исходные метаданные побайтно архивированы до обновления в `art/imagegen/concept-doctor-strange-codex/archive/metadata-only-1a-2026-10-13-r1`. Отсутствовавшие файлы промптов, source-hashes-before.json и manifest-sha256.json созданы из существующей истории.

## Ограничения

Автоматическая проверка не доказывает строгую ортографию, отсутствие текста, предметов или командных колец, позу и идентичность. Визуальные пункты не переоценивались, поскольку изображения этого запуска разрешены только для хешей/checker: passed=null явно означает не проверено. Историческая визуальная заметка Claude сохранена в verification.json. Подтверждённых визуальных FAIL в этом запуске нет; limit_reached=[] не означает художественную приёмку.

Записей design-front: 3, что ниже лимита 4; это не три генерации. Исторические неполные original_path оставлены без выдуманного уточнения. Изменения вне пакета: outside_folder=[]. Генерации, постобработка, браузер, git, Unreal, Tripo и SYNTX в этом запуске не выполнялись.

Блокер: нет; художественная оценка остаётся отдельным этапом.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/doctor-strange-design-front-rc1.png`, `concepts/doctor-strange-design-front-rc2.png`. Выбран `doctor-strange-design-front-rc2.png` → `design/doctor-strange-front-raw.png` → фон выровнен `rebg.py` → `design/doctor-strange-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (6.9). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-DOCTOR-STRANGE-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
