# Концепт-пакет ASSET-SQUIRREL-GIRL-001

## Этап 1a — дизайн-front из unstability.ai

ImageGen Codex и SYNTX (Seedream, Banana) отклонили лицензионного персонажа (`moderation_blocked`). По решению пользователя 2026-10-13 фронт сгенерирован в его подписке unstability.ai: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.

- Кандидаты: `concepts/squirrel-girl-design-front-u1.png`.
- Выбран: `squirrel-girl-design-front-u1.png` → `design/squirrel-girl-front.png`.
- Проверки 1a (`check_concept_views.py --views front --min-top-pct 4`): код 1, вердикт FAIL.
- Референс качества во входах не использовался (сервис text-to-image без референса).
- Статус: **предложено** (этап 1a); приёмка Sol — карточка в `evidence/acceptance-concept/`.
- Фон заменён на ровный нейтральный (46,46,48): сырой кадр сервиса с полом и виньеткой — `design/squirrel-girl-front-raw.png`; сегментация `C:/tmp/concept-wave/rebg.py` (модель фона полином 4-й степени + построчная поправка, рост от рамки), при касании края — поля с уменьшением. Перепроверка 1a: вердикт PASS.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/squirrel-girl-design-front-rc1.png`. Выбран `squirrel-girl-design-front-rc1.png` → `design/squirrel-girl-front-raw.png` → фон выровнен `rebg.py` → `design/squirrel-girl-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (7.5). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-SQUIRREL-GIRL-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
