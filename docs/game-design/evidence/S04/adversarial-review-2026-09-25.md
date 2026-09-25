# Независимое adversarial-ревью S04 и ответ разработчика

Ревью выполнено 2026-09-25 по дереву после GD-016/GD-018 (база `57156a7`).
Ниже — дословная копия отчёта ревьюера, затем пофайловый ответ с fixes и
доказательствами. Пять подтверждённых находок (P1-1, P1-2, P2-1, P2-2, P2-3)
исправлены; непоследовательных/ложных пунктов в отчёте не обнаружено —
каждый пункт перед фиксом верифицирован по коду (см. ответ).

## Часть 1. Отчёт ревьюера (дословно)

# Ревью S04 (e133a5f → working tree)

Прогнано локально: все 8 S04-сьютов — 48 тестов зелёные; `tsc --noEmit` exit 0. Полный backend-прогон и фронт-регрессия не перепроверялись (заявления 953/3 не опровергнуты).

## P1-1. selectHero: транзакция без реальной изоляции — гонка жива в production

- **Где:** `backend/src/games/game.service.ts:892-902`. `prisma.$transaction` (interactive) без `isolationLevel` → Postgres default **READ COMMITTED**: две конкурентные транзакции обе читают roster до коммита соперника → оба `update` проходят → у обоих игроков один герой.
- **Тесты это маскируют:** `s04-lobby-transport.spec.ts:81-87` и `s04-start-selection.spec.ts:47-54` — фикстура `$transaction: serializeTx` сериализует коллбеки promise-цепочкой; комментарий сам признаёт «stands in for production isolation». Seeded assumption ≠ production-семантика.
- **Триггер:** два одновременных HTTP selectHero одного героя в реальном Postgres.
- **Последствие:** claim README «ровно один отклоняется» ложен; оба выбора «успешны»; `startGame` (game.service.ts:682-689) отклонит старт → лобби висит с молчаливым конфликтом (никто не уведомлён).
- **Fix:** `SELECT ... FOR UPDATE` по gamePlayer-строкам внутри транзакции, либо `isolationLevel: 'Serializable'` + retry, либо partial unique index `(gameId, heroId)` + маппинг P2002.
- **Регрессия:** гонка на реальном Postgres (testcontainers), без serializeTx-фикстуры.

## P1-2. AI optional-MOVE fallback «на месте» отклоняется сервером → вечный strand VS_AI

- **Где:** `ai-decision.service.ts:139-141` — `target = step ?? {x: cur, y: cur}`. `pathToward` возвращает путь только к клетке **строго ближе** врага (строка 259-264); при `stepToward → null` AI шлёт резолв на текущую клетку.
- **Сервер отказывает:** `game-action-executor.service.ts:603-614` — `getReachableCells` **не включает старт** (`adjacency.service.ts:109`, `if (current.cost > 0)`) → «До клетки … не добраться» → шаг AI failed → `runOneStep` false → цикл стоп (`ai-turn.service.ts:81-84`).
- **Триггер:** after-combat optional MOVE при уже смежном бое — типичный случай: Arthur «Move your fighter up to 4 spaces» (`content-king-arthur.json:91`, optional), Dash, Hounds. После смежной атаки манхэттен=1 → closer-клеток нет → fallback → отказ.
- **Последствие:** очередь остаётся у AI; все действия человека гейтятся (`Resolve the pending choice first`); decline доступен только владельцу; combat-timeout очередь не трогает → **матч зависает навсегда**. Тест `s04-ai-queue.spec.ts:28-34` покрывает только dist>1.
- **Fix:** в `decidePending` optional MOVE без полезного пути → `declinePending`; и/или серверный резолв нулевого MOVE (target==start как «не двигаюсь») для «up to N» — это также закрывает mandatory-MOVE без достижимых свободных клеток (сейчас strand для любого клиента).
- **Регрессия:** decide-тест dist=1 + optional MOVE head; e2e VS_AI смежной атаки с after-MOVE картой.

## P2

1. **PLACE в дыру сетки проходит:** `game-action-executor.service.ts:583-586` — `if (cell && …)`, undefined-клетка внутри границ проскакивает bounds+occupied; для PLACE нет reachable-проверки. Латентно (Cobble City без дыр), но противоречит GD-015-принципу `isCellPassable` (дыры непроходимы). Fix: `if (!cell || !isCellPassable(cell))`.
2. **Рассинхрон живости в одном методе:** occupied-чек (строка 587-588) `f.health > 0`, blockedPositions (строка 600) `isLivingFighter(f)` — боец `isDefeated && health>0` блокирует endpoint, но не путь. Унифицировать на `isLivingFighter`.
3. **GameView «ещё в очереди: N-1»** (`GameView.tsx:500`) считает чужие хвосты как свои — `myPendingEffects` теперь возвращает всю очередь при своей голове. UX-косметика.

## Проверено, проблем не найдено

Гейты очереди во всех executor-методах (attack/scheme/defense/maneuver/endTurn/door/stance/resolveCombat); ровно одна передача хода (deferTurnEnd → drain → advanceTurn, marker снимается, combat-финал чистит `combatResolutionProgress` до advanceTurn — двойной drain не сконструирован); контракт +1 seq; circle-expiry удалён; timeout не фабрикует решения; pte/fp/optional сериализация + roundtrip; hand-limit на resume без дубля TURN_END-хуков; терминальные состояния без передачи; privacy чужих рук (isVisible=false, механизм S03 не тронут); зонно-легальная расстановка обеих ориентаций, 6 уникальных клеток; replay/foreign/out-of-order отклоняются без мутации (реальный HTTP/WS-тест).

## Не доказано / вердикт

- GD-016 «конкурентный выбор не ломает состав» — **не доказан для production БД** (P1-1); startGame-гейт не пускает дубль в матч, но лобби-флоу ломается.
- GD-018/tasks.json «AI and both clients cannot strand mandatory choices» — **опровергнуто** P1-2.
- ACC-017/ACC-008 целиком не закрываются (UE-часть, карточное покрытие — S05+), что README заявляет честно.

**Спринт закрывать нельзя** до фикса P1-1 и P1-2 (оба P0-бэклоговых claim'а). P1-2 — один fallback-фикс в `decidePending` + регрессия; P1-1 — изоляция/констрейнт + Postgres-тест.

## Часть 2. Ответ разработчика (GLM)

Каждый пункт верифицирован по коду до внесения изменений; все пять подтверждены.

### P1-1 — подтверждён, исправлен

**Fix** (`backend/src/games/game.service.ts`):
- `selectHero`: внутри `$transaction` — `SELECT id FROM "Game" WHERE id = $1 FOR UPDATE`,
  затем перепроверка статуса LOBBY и rival-чек ПОД локом, затем update.
  Выбрана блокировка строки игры (narrowest correct): сериализует и
  selectHero↔selectHero, и selectHero↔startGame, без retry-логики Serializable
  и без миграции схемы (partial unique index).
- `startGame`: LOBBY→IN_PROGRESS перевод, готовность, состав и дубль-чек
  выполняются в одной транзакции под тем же локом — стартовавший матч
  больше не мутируется поздним selectHero, второй startGame сериализуется.
- Fixture-спеки (`serializeTx`) оставлены как быстрые юнит-проверки; в
  prisma-фикстуры добавлен no-op `$queryRaw`.

**Реальная БД** — новый `backend/src/games/services/s04-concurrency-postgres.spec.ts`
(одноразовый контейнер `codex-s04-postgres`, `127.0.0.1:55432`, `s04_test`,
trust-аутентификация; схема — `npx prisma db push --skip-generate` только в
этой БД; спека сама пропускается, если БД недоступна):
1. **Before-proof (детерминированный)**: два READ COMMITTED check-then-act
   старой формы с барьером «оба прочитали ростер до апдейтов» → **дубль
   зафиксирован** — ровно та гонка, которую маскировала serializeTx-фикстура.
2. **After-proof**: тот же интерливинг с FOR UPDATE + перепроверкой → ровно
   один отклонён, ростер уникален, статус LOBBY.
3. **Продакшн-путь**: `GameService.selectHero` (реальный Prisma-клиент),
   15 раундов Promise.all одного героя → каждый раунд ровно один победитель.
4. **reselect vs startGame** (10 раундов, оба готовы): состав уникален всегда;
   успешный reselect применяется только ДО старта (тогда старт обязан пройти),
   стартовавший матч не мутируется; статус согласован с исходом startGame.
5. **reselect vs toggleReady** (5 раундов): ростер уникален, статус LOBBY.

### P1-2 — подтверждён, исправлен с двух сторон

- **Сервер** (`game-action-executor.service.ts`): резолв MOVE с target ==
  текущей клетке бойца легален («up to N» включает 0) — reachable-проверка
  пропускается только для нулевого шага. Закрывает strand mandatory-MOVE без
  достижимых свободных клеток для ЛЮБОГО клиента, не только AI.
- **AI** (`ai-decision.service.ts`): нет улучшающего шага → optional-голова
  отклоняется (`declinePending`), mandatory резолвится нулевым шагом.
  Mandatory-выборы никогда не сбрасываются молча — decline по-прежнему
  только для optional (сервер отклоняет mandatory-decline, тест есть).
- **Регрессии**: decide-тесты dist=1 (optional → decline; mandatory →
  zero-step), полностью заблокированный optional (угловая геометрия),
  полный drain `AiTurnService` со смежными бойцами (mandatory zero-step +
  optional decline, одна передача хода, seq 10→12), executor-тест
  mandatory-MOVE на доске 2×1, где НЕТ достижимых свободных клеток.

### P2-1 — подтверждён, исправлен

`if (cell && (cell.type === 'obstacle' || cell.type === 'wall'))` заменено на
`if (!isCellPassable(cell))`: дыры сетки (undefined внутри границ), стены,
препятствия и закрытые двери отклоняются для MOVE и PLACE («Клетка
непроходима»), без мутации. Регрессия: PLACE в дыру и на obstacle.

### P2-2 — подтверждён, исправлен

occupied-чек переведён на `isLivingFighter(f)` — тот же предикат, что и в
blockedPositions/пат-правилах GD-015. Регрессия: боец `isDefeated && health>0`
больше не блокирует endpoint.

### P2-3 — подтверждён, исправлен

GameView считает только элементы очереди с `playerId === localUserId`
(хвост глобальной очереди может быть чужим). Регрессия: очередь
[свой, чужой, свой] показывает «ещё в очереди: 1», не 2.

### Оговорка по полноте покрытия (без переclaim'а)

- Нулевой шаг доказан для MOVE-эффектов «up to N» (все MOVE-pending в
  текущем контенте — этого класса). Для карт с формулировкой «двигай ровно»
  семантика не определена контентом и не проверяется.
- AI-покрытие классов выбора: CHOOSE_ONE/MOVE/PLACE в `decidePending`;
  e2e VS_AI со смежной атакой и after-MOVE картой прогоняется на
  engine-уровне (полный drain), но не через реальный HTTP-матч.
- UE-часть ACC-017 и карточное покрытие ACC-008 остаются открытыми (S05+).
