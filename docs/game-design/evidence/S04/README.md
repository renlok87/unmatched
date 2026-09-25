# S04 — карта и движение: GD-014 … GD-018

База: `e133a5f` (`fix/admin-panel`, интегрированный S03); GD-016/GD-018 — поверх
`57156a7` в worktree-ветке `codex/s04-completion`. Протокол и реализация
входят в один коммит; точная ревизия: `git log -1 -- docs/game-design/evidence/S04/README.md`.

## GD-014: фиксированный контракт карты

[board-contract.json](board-contract.json) фиксирует **наблюдавшуюся в S01**
Cobble City 5×6. Источник — `evidence/S01/content-board.json`, контрольная сумма
считается по `JSON.stringify(parsed JSON)`, чтобы не зависеть от LF/CRLF checkout.
Это версия серверной сетки, не утверждение о канонической настольной карте или
принятом финальном арте. Старый контентный вариант 6×4 не подменяет snapshot.

- Все 30 клеток, две зоны blue/red и 49 неориентированных ортогональных связей
  перечислены явно. В этом capture **нет мультизонных клеток**; проверки `zones[]`
  в GD-015 используют отдельные синтетические позиции.
- Production `GameInitializationService` воспроизводит ту же `boardState`
  и шесть различных стартовых позиций для Medusa→Arthur и Arthur→Medusa.
  База и каталог заменены входными fixture-адаптерами. Реальная БД не изменяется.
- Указаны четыре world↔cell контрольные точки при 100 uu на клетку и центре
  доски (0,0,0). Обратное преобразование проверяется для всех 30 центров.
  UE-сцена, экранный hit-test и финальный размер арта здесь не проверяются.
- Стартовые позиции обновлены GD-016 под зонно-легальный алгоритм (см. ниже);
  размещение гарпий текущим алгоритмом не объявляется эталоном правил.

Проверка: `backend/src/games/services/s04-board-contract.spec.ts`.

## GD-015: серверные пути и зоны

Целевые правила: промежуточный союзник проходим, живой враг блокирует путь,
занятое назначение запрещено; побеждённый боец не блокирует. Дальняя атака
разрешена при смежности **или** пересечении зон, включая вторую зону клетки;
для старых сохранений поддерживается `zone`. Особые способности дальности
сохраняют собственную проверку.

Реализация исправляет валидацию манёвра, обычный BFS и отложенный `MOVE`,
поиск A*, исполнение явного пути и выбор пути AI. Убран фиктивный кешированный
путь `[start,end]`. Проверяются реальные границы/существование клеток, стены,
закрытые двери, целочисленные координаты и последовательность соседних шагов.

Независимый итоговый прогон: **42/42 новых проверки S04 прошли** (5 контракт
карты, 29 от исполнителя, 8 дополнительных проверок ревью). В полном backend:
**931 passed, 3 failed**, 49 suites. Все три падения — те же auth-тесты,
что до GD-015; новых падений нет. `npm run build` завершился с exit 0.
Регрессии frontend S03: **12/12**. Проверка структуры документации также прошла.

Ревью потребовало дополнительных исправлений: отсутствующие клетки, дробные
координаты, старт вне доски, отсутствие boardState, телепорт-шаги, закрытые
двери и проход через союзника при отложенном `MOVE`. GLM исправил первые шесть
по независимым тестам; последнее исправление внесено основным агентом.
Legacy `MovementService.moveFighter` по-прежнему не применяет состояние;
production манёвр использует проверенный `GameActionExecutorService`.

Доказательства и итоговые команды фиксируются в [verification.json](verification.json).
ACC-017 целиком не закрывается: будущая UE-подсветка/экранный hit-test
остаются вне этого серверного пакета. Очередь обязательных/optional-выборов
**GD-018** реализована ниже.

## GD-016: состав пары и начальная расстановка

ACC-017 серверная часть. Каталог героев не ограничен стартовой парой —
проверки generic-unique; Medusa/Arthur — только acceptance-фикстуры.

- **Конкурентный выбор героев**: `GameService.selectHero` выполняет
  проверку и запись атомарно в `$transaction` **под блокировкой строки игры**
  (`SELECT … FOR UPDATE`) с перепроверкой статуса LOBBY внутри транзакции —
  два одновременных HTTP-выбора одного героя сериализуются, ровно один
  отклоняется («Герой уже выбран другим игроком этой игры»). `startGame`
  переводит LOBBY→IN_PROGRESS, проверяет готовность/состав/дубликаты и
  пишет статус в одной транзакции под тем же локом (defense-in-depth +
  стартовавший матч не мутируется поздним reselect). Гонка на РЕАЛЬНОМ
  PostgreSQL доказана до/после — см. «Коррекции по adversarial-ревью».
- **Зонная расстановка**: `GameInitializationService.findSidekickCell` ищет
  свободную клетку, разделяющую зону с героем, кольцевым манхэттен-сканом
  (d=1.., детерминированный порядок); каждый сайдкик — отдельная клетка.
  Зоны доски — ровные ряды blue y0-2 / red y3-5 (5×6 S01 контракт).
  При вырожденной зоне — fallback на ближайшую свободную клетку с warn.
- **Первый игрок**: `metadata.firstPlayerId` = host, сериализуется в compact
  формате (`fp`), переживает save/load.
- Обе ориентации сидов (medusa-first, arthur-first) воспроизводят 6 различных
  клеток; сайдкики в зонах героев. Контракт [board-contract.json](board-contract.json)
  обновлён честно: `starts` пересчитаны по новому алгоритму, `startPolicy`
  описывает зонное правило, source sha256 сохранён.

Проверки: `backend/src/games/services/s04-start-selection.spec.ts` (6),
`backend/src/games/resolvers/s04-lobby-transport.spec.ts` (2, реальный
HTTP: полный лобби-флоу + гонка двух selectHero). Выбор стартовой зоны
игроком (расширение) остаётся вне GD-016 — автоматически легальная расстановка
соответствует backlog-формулировке «помощники в допустимой зоне и отдельных
клетках».

## GD-018: последовательная очередь обязательных и optional-выборов

ACC-008. Без generic-абстракции: существующая цепочка `pendingEffects`
расширена строгим порядком + один marker `metadata.pendingTurnEnd`
`{playerId, endEffectsApplied}` + один общий drain-point.

- **Строгий порядок**: резолвится только голова очереди
  («Resolve the first pending choice first»); чужие, out-of-order и replayed
  запросы отклоняются без мутации (sequenceNumber не растёт).
- **Второе действие и передача хода ждут цепочку**: при открытой очереди
  `advanceTurn` откладывается (`deferTurnEnd`, actionsRemaining: 0);
  attack/playDefense/playScheme/beginManeuver/endTurn/toggleDoor/setStance
  гейтятся («Resolve the pending choice first»). `endTurn` — gate, не defer.
- **Drain после каждого выбора** (`drainAfterChoice`): очередь непуста →
  следующая голова; `combatResolutionProgress` → ре-вход в combat (continuation
  сохранён, приоритет над marker); `pendingTurnEnd` → `advanceTurn`
  resume (incrementSeq=false, endEffectsApplied) — ровно одна передача хода,
  контракт «+1 sequenceNumber на мутацию» сохранён; терминальные состояния
  (immediate GAME_OVER) проходят без передачи.
- **Decline только optional**: `declinePendingEffect` отклоняет mandatory
  («Этот выбор обязателен — его нельзя отклонить»), не-голову, чужие, replay.
  `optional` флаг проставляется в card-effect-executor для «You may …» эффектов.
- **Таймаут не фабрикует решение**: combat-timeout `performAutoResolve`
  очередь не трогает (тест).
- **Круговое протухание удалено**: решения больше не подменяются экспирацией.
- **Персистентность**: `pendingTurnEnd` (`pte`), `firstPlayerId` (`fp`),
  `optional` в compact-сериализации; save/load roundtrip с резюмом передачи.
- **AI**: глобальная голова (чужая → null), mandatory без решения → null
  (не фабрикует), optional без решения → `declinePending`; при отсутствии
  улучшающего шага (враг смежен/бот заперт) mandatory-MOVE резолвится
  легальным нулевым шагом — очередь не strand'ит VS_AI-матч; полный drain
  через `AiTurnService` (resolve → decline → одна передача).
- **Нулевой шаг MOVE**: «up to N» включает 0 — резолв MOVE с target ==
  текущей клеткой принимается сервером (mandatory-MOVE без достижимых
  свободных клеток больше не зависает ни для AI, ни для человека).
- **Клиенты**: mutation `declinePendingEffect` (GraphQL DTO
  `DeclinePendingEffectDto {gameId, effectId}`); кнопка «Отказаться» в
  pending-баннере GameView для optional; `myPendingEffects` — глобальная
  голова; admin game-tester — команды `pdecline <id>` и `pending` с optional
  маркером.

Проверки: `backend/src/game-engine/services/s04-pending-queue.spec.ts` (12),
`backend/src/game-engine/services/s04-ai-queue.spec.ts` (9),
`backend/src/games/resolvers/s04-pending-transport.spec.ts` (1, реальный
HTTP/WS: сиды цепочки из двух эффектов, gated-действия, tail-first/foreign/
mandatory-decline отклонения, cache-evict + snapshot restore, replay
отклонён, оба наблюдателя видят обе мутации).

Итоговый прогон: **966 passed, 3 failed** (те же auth), **55 suites**;
frontend S03 регрессия **13/13**; `npm run build` exit 0; admin
`npm run build` exit 0. Детали — [verification.json](verification.json).

## Коррекции по adversarial-ревью (второй проход, 2026-09-25)

Независимое ревью (дословный отчёт + пофайловый ответ):
[adversarial-review-2026-09-25.md](adversarial-review-2026-09-25.md).
Все пять подтверждённых находок исправлены; каждый пункт перед фиксом
верифицирован по коду.

- **P1-1 (гонка selectHero в production БД)**: старая транзакция без
  изоляции реально пропускала дубль под READ COMMITTED — доказано
  детерминированным барьер-тестом на реальном PostgreSQL (дубль зафиксирован
  ДО фикса). Фикс: `FOR UPDATE` по строке игры + перепроверка LOBBY внутри
  транзакции в `selectHero`; атомарный LOBBY→IN_PROGRESS переход под тем же
  локом в `startGame`. Продакшн-инварианты (уникальность, LOBBY-статус,
  reselect vs start/ready) прогнаны реальным `GameService` через реальный
  Prisma — `backend/src/games/services/s04-concurrency-postgres.spec.ts` (5
  тестов, одноразовый контейнер `codex-s04-postgres` `127.0.0.1:55432`
  `s04_test`; спека сама скипается без БД). Fixture-`serializeTx`-спеки
  оставлены как юнит-уровень и больше НЕ заявляются как доказательство
  production-изоляции.
- **P1-2 (strand VS_AI при смежном бое)**: сервер принимает нулевой шаг
  MOVE («up to N» включает 0); AI без улучшающего шага отклоняет optional
  и резолвит mandatory нулевым шагом. Регрессии: decide dist=1 (optional →
  decline, mandatory → zero-step), запертый optional, полный drain
  `AiTurnService` со смежными бойцами (mandatory zero-step + optional
  decline + ровно одна передача), executor mandatory-MOVE на доске без
  достижимых свободных клеток. Mandatory-выборы не сбрасываются: decline
  по-прежнему только optional (сервер отклоняет).
- **P2-1 (PLACE в дыру сетки)**: `isCellPassable` — дыры/стены/препятствия/
  закрытые двери отклоняются для MOVE и PLACE, без мутации.
- **P2-2 (рассинхрон живости)**: occupied-чек на `isLivingFighter` —
  `isDefeated && health>0` больше не блокирует endpoint.
- **P2-3 (чужие хвосты в счётчике GameView)**: считаются только свои
  элементы очереди.

Честность покрытия: нулевой шаг доказан для MOVE «up to N» (весь текущий
MOVE-контент); AI покрывает классы CHOOSE_ONE/MOVE/PLACE на engine-уровне,
e2e VS_AI-матч по HTTP со смежной атакой не прогонялся; UE-часть ACC-017 и
карточное покрытие ACC-008 открыты (S05+). Спринт ожидает проверочного
ревью коррекций.

## Проверка Claude Code → GLM

Исследование выполнялось через `claude -p --model haiku`; локальные настройки
переопределяют этот алиас в `glm-5.3-flashx[1m]`, что подтверждено логом прокси.
Реализация GD-015 запущена с `--model claude-sonnet-4-6 --effort max`;
полное имя обходит локальное переопределение `sonnet`, а прокси маршрутизирует
его в `glm-5.3`. Это фиксация запрошенного effort, не измерение внутреннего
режима рассуждений провайдера.

Исполнителю даны конкретные acceptance cases и границы `backend/src/game-engine/**`.
Контракт карты, проверку diff, независимые тесты и интеграцию выполняет основной
агент. Процесс Claude Code запускается через CLI; наличие прокси само по себе
не делегирует задачи. Отчёт исполнителя не заменяет проверку кода и сценариев.

## Воспроизведение

Из корня checkout с установленными backend dependencies:

```powershell
node backend/node_modules/jest/bin/jest.js --config backend/package.json --runInBand
node backend/node_modules/typescript/bin/tsc --noEmit --project backend/tsconfig.json
node node_modules/vitest/vitest.mjs run src/store/remoteGameStore.s03.test.ts src/components/game/GameView.s03.test.tsx src/components/game/turnResourceChoices.test.ts
python docs/game-design/_validation/validate_package.py
```

Гонка выбора героев на реальном PostgreSQL (одноразовый контейнер, БД только
для тестов):

```powershell
docker run -d --name codex-s04-postgres -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55432:5432 postgres
node backend/node_modules/jest/bin/jest.js --config backend/package.json s04-concurrency-postgres
```

Спека сама применяет схему (`prisma db push --skip-generate` только в эту БД)
и пропускается, если БД недоступна. Admin-сборка: `npm run build` (cwd: admin)
exit 0.

Три старых падения `auth.service.spec.ts` воспроизводились до GD-015 и учитываются
отдельно. Этот пакет не меняет auth, пользовательские незакоммиченные файлы,
deployed-сервер или production-базу данных. Remote push не выполняется.

## Закрытие S04 после повторного независимого ревью

[Ревью исправлений](correction-review-2026-09-25.md): все пять замечаний закрыты; PostgreSQL 5/5, очередь/AI 21/21, transport/selection 9/9, GameView 4/4 проверены ревьюером. S04 закрыт в указанном серверном объёме. Оставшиеся неблокирующие гонки лобби — GD-029, явный UI нулевого шага — GD-035. Полные ACC-017/ACC-008 и последующие спринты этим не закрываются.
