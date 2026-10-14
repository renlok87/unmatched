# Концепт-пакет ASSET-ELEKTRA-001

Статус: **предложено** (proposed), этап 1a. Художественная приёмка не заявлена.

## Корректировка метаданных

Генераций: **0**; вызовов image_gen: **0**. Зарегистрирован готовый дизайн. Нового изображения и обработки PNG нет.
- Выбран: art/imagegen/concept-elektra-codex/concepts/elektra-design-front-g2.png (g2).
- Источник: design/elektra-front.png; копия совпадает побайтно.
- SHA256: 30dbe8062f91ccaeccdd88f633be4097ae01ab96d632c12671a9970919a1b125.
- Записей: 2; g2 — регистрация, не генерация.
- Прежняя запись сохранена; изменён только selected. Все прежние PNG и palette.json неизменны.

## Происхождение

Исторический источник — unstability.ai. Claude ранее нормализовал фон через rebg.py; описание сохранено в verification.json#design_source.post. Raw: design/elektra-front-raw.png. Сейчас постобработка не запускалась.
Точный внешний промпт u1 скопирован под ключ 1a/design-front/g2. Сейчас не выполнялся. Референсы генератору не передавались.

## Проверки и ограничения

- u1: код 1; FAIL view.border_uniform и view.side_margin.
- g2: код 0. Финальный checker на текущем дизайне без --out: код 0, 13 PASS.
- Отчёты: checks/design-front-g1 и checks/design-front-g2. Временные побайтовые копии внутри пакета удалены.
- Чек-лист: виден верх подставки; справа серый участок; клинки не читаются как саи; длинного конца пояса нет. Запрет оружия конфликтует с требованием саев.
- Аспект 4:5 вместо 3:4; на подставке каменная раскладка. Лимит генераций 0, исправлений PNG нет.
- Сбой tempfile до checker: пустая tmp-metadata-check-asb509mx осталась, ACL запрещает удаление. Все рабочие временные копии удалены.

## Архив и хеши

- Архив метаданных: art/imagegen/concept-elektra-codex/archive/metadata-before-repair-20261013T103613Z.
- Входы: source-hashes-before.json; итог: source-hashes-after.json.
- outside_folder=[]; другие пакеты не открывались. Внешний референс и карточка сейчас не перепроверялись.
- manifest-sha256.json записан последним: все файлы пакета, кроме самого manifest.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/elektra-design-front-rc1.png`, `concepts/elektra-design-front-rc2.png`. Выбран `elektra-design-front-rc1.png` → `design/elektra-front-raw.png` → фон выровнен `rebg.py` → `design/elektra-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (7.5). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-ELEKTRA-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
