# Концепт-пакет ASSET-BLACK-WIDOW-001

Статус: **предложено** (proposed), этап 1a. Художественная приёмка не выполнялась.

## Корректирующий запуск: только метаданные

Генераций: **0**; вызовов image_gen: **0**. design/black-widow-front.png не изменялся. Существующий нормализованный дизайн побайтово зарегистрирован новым неизменяемым кандидатом.

- Выбран: art/imagegen/concept-black-widow-codex/concepts/black-widow-design-front-g2.png.
- SHA256: 734cba4ce1c7b1a2f4d9d56da056f48221a88eb3a7db6b97abd920803b4d54c3.
- Записей: 2: историческая генерация u1 и регистрация g2; попытка 2 не означает новую генерацию.
- Архив: art/imagegen/concept-black-widow-codex/archive/metadata-repair-20261013T101213Z/.

## Происхождение

Источник — историческая генерация unstability.ai, UltraReal Fine-Tune v4 (Flux.1 D). Claude ранее нормализовал фон через C:/tmp/concept-wave/rebg.py; это зафиксировано в прежнем verification.json#design_source.post, сохранённом в архиве. Обработка сейчас не повторялась.

Старый concepts/black-widow-design-front-u1.png, промежуточный design/black-widow-front-raw.png и текущий дизайн имеют разные хеши. Точная цепочка преобразований не восстановлена. Запись u1 сохранена, изменён только selected.

У новой записи original_path — абсолютный путь текущего дизайна. Исторический внешний промпт дословно скопирован в ключ 1a/design-front/g2 и prompts.md; сейчас не исполнялся. Другие пакеты не открывались.

## Проверки и ограничения

- u1 проверен через временную побайтовую копию внутри пакета: код 1, FAIL view.border_uniform и view.side_margin. Отчёт: checks/design-front-g1/checks-report.json.
- g2 проверен отдельно: код 0. Отчёт: checks/design-front-g2/checks-report.json.
- Текущий дизайн проверен последним без --out: код 0, 13 PASS, 0 WARN, 0 FAIL. Отчёт: design/checks-report.json.
- Временные PNG удалены; исходные изображения неизменны. Исторические FAIL сохранены.

Код скрипта не заменяет визуальный чек-лист. Замечания выбранного файла:
- Верх подставки виден: строгий уровень камеры и вид ребром не соблюдены.
- Фигура целиком; слева у подставки светлый остаток маски нарушает ровный фон.
- Пряжка: красный круг с перекрестием; однозначный знак песочных часов не подтверждён.

Размер 1280x1600 даёт 4:5 вместо 3:4; два низких диска не подтверждены. Лимит 0 запрещает исправления и генерацию. Недочёты записаны в verification.json; блокеров выполнения нет.

## Сохранность

Все три прежних PNG и palette.json сохранили байты. Прежние метаданные архивированы побайтово. outside_folder=[]. Manifest записан последним и охватывает весь пакет, кроме самого manifest.

| Прежний PNG | SHA256 до и после |
|---|---|
| art/imagegen/concept-black-widow-codex/concepts/black-widow-design-front-u1.png | febeb2e6165a4889035d056b5782f6497bbf37b4c9eabd028c13fb68e5c58c73 |
| art/imagegen/concept-black-widow-codex/design/black-widow-front-raw.png | d7a4a0bd2a42f1710f1ff6fff64cf79dee7ae342beb382729ac14952a5142467 |
| art/imagegen/concept-black-widow-codex/design/black-widow-front.png | 734cba4ce1c7b1a2f4d9d56da056f48221a88eb3a7db6b97abd920803b4d54c3 |

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/black-widow-design-front-rc1.png`, `concepts/black-widow-design-front-rc2.png`. Выбран `black-widow-design-front-rc2.png` → `design/black-widow-front-raw.png` → фон выровнен `rebg.py` → `design/black-widow-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.
