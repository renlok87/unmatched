# ASSET-BLOB-001: фронтальный дизайн 1a

Статус: **предложено**. Дата: 2026-10-13.

Созданы два кандидата design-front через встроенный image_gen, по одному изображению на вызов. Единственный графический вход — заданный референс мастерства Medusa; palette.json прочитан как данные палитры.

Выбран **g2**: art/imagegen/concept-blob-codex/design/blob-front.png. Исходный кандидат — art/imagegen/concept-blob-codex/concepts/blob-design-front-g2.png. Подставка показана строго с ребра; силуэт желе и поглощённые предметы читаются. Размер 1086 × 1448, аспект 3:4, верх маски y8,011%, низ y92,956%, центр подставки x50%.

## Проверки и неудачи

У g1 скрипт дал exit 0, но была видна узкая верхняя поверхность подставки: провал CHECKLIST-2. В g2 добавлена одна строка CORRECTION; CORE не менялся. Первое впечатление о градиенте фона не подтвердилось пиксельной сверкой; коррекция фона не запускалась.

Каждый кандидат проверен отдельно:

- art/imagegen/concept-blob-codex/checks/design-front-g1/checks-report.json
- art/imagegen/concept-blob-codex/checks/design-front-g2/checks-report.json

Финальный прогон на g2 без --out: art/imagegen/concept-blob-codex/design/checks-report.json. Все три прогона: exit 0, 13 PASS, 0 WARN, 0 FAIL. Все шесть пунктов CHECKLIST у g2 выполнены, limit_reached пуст.

Отклонения CORE: диаметр подставки около **0,81 высоты фигуры вместо 0,55**; нижняя масса желе не образует **две отдельные стопы**. Они записаны в unmet_requirements в art/imagegen/concept-blob-codex/verification.json. Использованы **2 из 2** генераций; решение о приёмке остаётся за приёмщиком.

## Решения и сохранность

view = design-front, слот скрипта = front, side_view = null. Номера кандидатов g1/g2. Размер выбрал инструмент, аргумент size не передавался. Файлы concepts/ не перезаписаны. Изображения не ретушировались, не масштабировались и не перекодировались: копии побайтово совпадают с оригиналами. Абсолютные пути сохранённых оригиналов image_gen указаны в original_path в art/imagegen/concept-blob-codex/generation-records.json; оригиналы оставлены на месте.

Точные промпты: art/imagegen/concept-blob-codex/prompts.md и art/imagegen/concept-blob-codex/prompts/concept-prompts.json. До работы в пакете был только palette.json; он сохранён. Оба входа совпали с заданными SHA-256 и после работы не изменились. Все записи в репозиторий ограничены пакетом; оригиналы инструмента находятся в его собственном каталоге. Команд Git, действий с Unreal, Tripo, SYNTX и скачиваний не было. Фоновые процессы не запускались. Манифест art/imagegen/concept-blob-codex/manifest-sha256.json записан последним. Внешняя приёмка не проводилась.
