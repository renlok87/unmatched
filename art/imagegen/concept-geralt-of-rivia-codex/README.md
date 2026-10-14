# Геральт из Ривии — дизайн фронтального вида, этап 1a

Статус: **предложено**.
Состояние запуска: заблокирован ошибкой image_gen; готового концепта нет.

Проверены SHA-256 обоих разрешённых входов: они совпали с заданием.
В image_gen отправлен дословный CORE с единственным референсом качества Medusa.
Одна попытка вызова из двух разрешённых завершилась HTTP 400 / moderation_blocked
на стадии output (категория other). Request ID: ea1c2665-aa85-4fd0-a36c-2329e804adfc.

Для design-front выбранной генерации нет: инструмент не вернул изображение или путь к файлу.
concepts/geralt-of-rivia-design-front-g1.png и design/geralt-of-rivia-front.png не созданы.
check_concept_views.py не запускался: входного изображения нет.
Визуальные пункты CHECKLIST остались непроверенными; код финального скрипта отсутствует.

Решение исполнителя: сохранить точный промпт и не менять CORE для обхода отказа.
Повтор не выполнен: условия шага 3 (FAIL автопроверки или CHECKLIST) не наступили.
В generation-records.json неуспешная попытка записана с null вместо отсутствующих данных файла.
В verification.json явно указаны блокер, невыполненные проверки и использование лимита.
limit_reached пуст: ни один выбранный вид не исчерпал лимит с проваленным CHECKLIST.

Все записи пакета сделаны Python в UTF-8 без BOM.
Исходный palette.json сохранён побайтно. Git, Unreal, Tripo, SYNTX и загрузки не использовались.
Команда npx openskills read не смогла прочитать навык из-за отсутствия npm-кеша;
инструкции прочитаны напрямую из локальных файлов, установка не выполнялась.
Созданные в этом запуске команды завершились; фоновых процессов запуск не оставил.

Точный промпт: prompts/concept-prompts.json и prompts.md.
Хеши входов до запуска: source-hashes-before.json.
Доказательства неизменности и ограничения: verification.json.
Состав и SHA-256 файлов пакета: manifest-sha256.json.

## Этап 1a — дизайн-front из unstability.ai

ImageGen Codex и SYNTX (Seedream, Banana) отклонили лицензионного персонажа (`moderation_blocked`). По решению пользователя 2026-10-13 фронт сгенерирован в его подписке unstability.ai: unstability.ai — UltraReal Fine-Tune v4 (Flux.1 D), Permissive, 3:4, High, CFG 3.5, 25 steps.

- Кандидаты: `concepts/geralt-of-rivia-design-front-u1.png`.
- Выбран: `geralt-of-rivia-design-front-u1.png` → `design/geralt-of-rivia-front.png`.
- Проверки 1a (`check_concept_views.py --views front --min-top-pct 4`): код 1, вердикт FAIL.
- Референс качества во входах не использовался (сервис text-to-image без референса).
- Статус: **предложено** (этап 1a); приёмка Sol — карточка в `evidence/acceptance-concept/`.
- Фон заменён на ровный нейтральный (46,46,48): сырой кадр сервиса с полом и виньеткой — `design/geralt-of-rivia-front-raw.png`; сегментация `C:/tmp/concept-wave/rebg.py` (модель фона полином 4-й степени + построчная поправка, рост от рамки), при касании края — поля с уменьшением. Перепроверка 1a: вердикт PASS.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/geralt-of-rivia-design-front-rc1.png`. Выбран `geralt-of-rivia-design-front-rc1.png` → `design/geralt-of-rivia-front-raw.png` → фон выровнен `rebg.py` → `design/geralt-of-rivia-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (6.3). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-GERALT-OF-RIVIA-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
