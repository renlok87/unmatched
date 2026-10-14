# ASSET-LOKI-001 — концепт Loki, этап 1a

Статус: **предложено**. Выполнение остановлено из-за отказа image_gen; изображение не получено.

Запрошен один фронтальный дизайн миниатюры Loki с точным CORE из задания. Сделан один вызов встроенного image_gen с единственным изображением-референсом Medusa. Палитра прочитана как JSON и не передавалась как изображение.

Выбранная генерация для design-front: **нет**. Попытка g1 отклонена системой безопасности при выдаче изображения: HTTP 400, moderation_blocked, стадия output, категория other. Request ID: 80d9538e-6175-434e-9d99-f97cd3ca1ff2. Собственного файла инструмента и PNG-кандидата нет, поэтому original_path, saved_path, sha256 и размеры записи g1 равны null.

Использован 1 вызов из разрешённых 2; получено 0 изображений. Второй вызов не выполнен: повтор разрешён после FAIL скрипта или CHECKLIST, а здесь возник отказ инструмента до получения кандидата. Это блокер, а не исчерпание лимита CHECKLIST.

Скрипт check_concept_views.py не запускался: входного design/loki-front.png нет. CHECKLIST не оценён; финального checks-report.json нет. Пустой checklist в verification.json означает отсутствие выбранного файла, а не успешную визуальную проверку.

Хеши обоих входов совпадают с заданием и с повторной проверкой. palette.json сохранён побайтно. Точный переданный промпт записан в prompts/concept-prompts.json и prompts.md; отказ — в generation-records.json и verification.json. Все записи пакета сделаны из Python в UTF-8 без BOM.

Мелкие решения: не создавать фиктивные PNG и отчёты скрипта; не менять CORE для обхода отказа; учитывать неудавшийся вызов как одну использованную попытку. Изображения не редактировались. Команды git не выполнялись, Unreal, Tripo и SYNTX не запускались. Фоновые процессы для задачи не создавались.

## Этап 1a — дизайн-front из unstability.ai

ImageGen Codex и SYNTX (Seedream, Banana) отклонили лицензионного персонажа (`moderation_blocked`). По решению пользователя 2026-10-13 фронт сгенерирован в его подписке unstability.ai: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.

- Кандидаты: `concepts/loki-design-front-u1.png`, `concepts/loki-design-front-u2.png`.
- Выбран: `loki-design-front-u2.png` → `design/loki-front.png`.
- Проверки 1a (`check_concept_views.py --views front --min-top-pct 4`): код 1, вердикт FAIL.
- Референс качества во входах не использовался (сервис text-to-image без референса).
- Статус: **предложено** (этап 1a); приёмка Sol — карточка в `evidence/acceptance-concept/`.
- Фон заменён на ровный нейтральный (46,46,48): сырой кадр сервиса — `design/loki-front-raw.png`; сегментация `C:/tmp/concept-wave/rebg.py`. Перепроверка 1a: вердикт PASS.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/loki-design-front-rc1.png`. Выбран `loki-design-front-rc1.png` → `design/loki-front-raw.png` → фон выровнен `rebg.py` → `design/loki-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (7.5). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-LOKI-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
