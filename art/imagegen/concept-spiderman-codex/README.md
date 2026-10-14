# ASSET-SPIDERMAN-001 — концепт 1a

Статус: **предложено**. Выполнение заблокировано сервисом генерации; изображение для приёмки не получено.

Записаны исходные SHA-256 референса качества и палитры, выполнен один вызов встроенного `image_gen.imagegen` с CORE дословно и только референсом Medusa. Сервис вернул HTTP 400, `moderation_blocked`, этап проверки `output`, категория `other`. ID запроса: `4b6e86c2-12dc-4129-97e5-29c538b9684f`.

Для вида `design-front` выбранной генерации нет: g1 не вернула PNG. Использован 1 из 2 разрешённых вызовов; успешных изображений — 0. Второй вызов не выполнялся: без кандидата нет основания для CORRECTION по FAIL скрипта или CHECKLIST, а недоступность генерации является блокером задания.

`check_concept_views.py` не запускался: файла кандидата нет. Финальный код скрипта отсутствует; визуальный CHECKLIST не оценён. Каталоги `concepts/`, `design/` и `checks/` не заполнялись фиктивными результатами.

Небольшое решение: неуспешный вызов сохранён в `generation-records.json` с `selected=false`, ошибкой и `null` в полях отсутствующего изображения. Точный отправленный CORE сохранён в обоих журналах промптов. CORE не исправлялся.

Оба входа и существовавший `palette.json` сохранены без изменений. Все записи этого запуска сделаны внутри пакета. Ограничения и блокер перечислены в `verification.json`; пакет не является принятым фронтальным дизайном.

## Этап 1a — дизайн-front из unstability.ai

ImageGen Codex и SYNTX (Seedream, Banana) отклонили лицензионного персонажа (`moderation_blocked`). По решению пользователя 2026-10-13 фронт сгенерирован в его подписке unstability.ai: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.

- Кандидаты: `concepts/spiderman-design-front-u1.png`.
- Выбран: `spiderman-design-front-u1.png` → `design/spiderman-front.png`.
- Проверки 1a (`check_concept_views.py --views front --min-top-pct 4`): код 1, вердикт FAIL.
- Референс качества во входах не использовался (сервис text-to-image без референса).
- Статус: **предложено** (этап 1a); приёмка Sol — карточка в `evidence/acceptance-concept/`.
- Фон заменён на ровный нейтральный (46,46,48): сырой кадр сервиса с полом и виньеткой — `design/spiderman-front-raw.png`; сегментация `C:/tmp/concept-wave/rebg.py` (модель фона полином 4-й степени + построчная поправка, рост от рамки), при касании края — поля с уменьшением. Перепроверка 1a: вердикт PASS.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/spiderman-design-front-rc1.png`. Выбран `spiderman-design-front-rc1.png` → `design/spiderman-front-raw.png` → фон выровнен `rebg.py` → `design/spiderman-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (7.5). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-SPIDERMAN-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
