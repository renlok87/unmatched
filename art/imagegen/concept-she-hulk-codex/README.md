# ASSET-SHE-HULK-001: исправление метаданных 1a

Статус: **предложено** (proposed). Приёмка не заявлена.

Выбран concepts/she-hulk-design-front-g2.png: побайтовая копия design/she-hulk-front.png. SHA256: 3412b8761b16660cecf457b5cd04298cf48de635463ef2a38d133ce9b42af21f. Попытка 2 — регистрация; генераций и вызовов image_gen: **0**.

Источник — unstability.ai; нормализация Claude через C:/tmp/concept-wave/rebg.py историческая (verification.json#design_source.post), сейчас не выполнялась. Промпт скопирован дословно в 1a/design-front/g2, сейчас не запускался.

Старый u1 сохранён, изменён только selected. Его хеш отличается от raw: связь между ними не выдумана. Все три прежних PNG и palette.json неизменны. Архив: archive/metadata-repair-20261013T100044593241Z/.

Проверки: g1 — код 1 (фон, нижнее и боковое поля); g2 и финальная — код 0. Исторические FAIL сохранены отдельно. Временные копии удалены.

Ограничения: WARN верхнего поля 2,375% вместо 4%; 1280x1600 (4:5 вместо 3:4). Пять пунктов чек-листа не подтверждены полностью: passed=false с not_verified означает отсутствие проверки, а не доказанный дефект. Изображения использованы только для хешей и автопроверок.

Записей: 2; outside_folder=[]. Блокеров исправления нет; рисунок решает приёмщик. Манифест создан последним.

## Перегенерация Recraft v4 (после возврата Sol r1)

Кандидаты: `concepts/she-hulk-design-front-rc1.png`, `concepts/she-hulk-design-front-rc2.png`. Выбран `she-hulk-design-front-rc2.png` → `design/she-hulk-front-raw.png` → фон выровнен `rebg.py` → `design/she-hulk-front.png`. Промпт собран из карточки (DESCRIPTION_EN, ANCHORS_EN, PALETTE). Проверки 1a: код 0, вердикт PASS.

## Решение пользователя 2026-10-13

Sol r2: return_to_stage_1 (6.9). Пользователь: «Пустить их дальше с текущими фронтами» — фронт идёт на этап 1b (Tripo). Запись: `docs/game-design/decisions/2026-10-13-licensed-concepts-user-accepted.md`, `art/pipeline-candidates/ASSET-SHE-HULK-001/evidence/acceptance-concept/20261013-front-r2/user-decision.json`. Статус: **предложено**, этап 1a закрыт решением пользователя.
