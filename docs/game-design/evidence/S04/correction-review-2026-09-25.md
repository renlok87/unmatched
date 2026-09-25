# Вердикт S04: коррекции ЗАКРЫТЫ. Спринт можно закрывать.

Прогнано лично (реальная БД `codex-s04-postgres` 127.0.0.1:55432/s04_test): postgres-спека 5/5, queue+AI 21/21, transport/selection 9/9, фронт GameView 4/4.

## Пять находок — по коду, не по заявкам

**P1-1 закрыт.** `selectHero` — `FOR UPDATE` + перепроверка LOBBY + rival-чек + update в одной транзакции (game.service.ts:924-942); `startGame` — готовность/состав/дубль перепроверены под тем же локом, атомарный LOBBY→IN_PROGRESS (695-725). READ COMMITTED достаточно: check-then-act целиком под локом. Before-proof (дубль детерминированно воспроизведён на старой форме) → after-proof (ровно один проигравший) → продакшн `GameService` 15+10+5 раундов. Всё зелёное.

**P1-2 закрыт.** Сервер: zero-step легален только как `staysInPlace` — reachable-проверка пропущена, но bounds/passable/occupied остаются (game-action-executor.service.ts:596-621). **Телепорта нет**: target==start → позиция не меняется (628-630), applyMoveReactions без диффа, seq +1. AI: нет улучшающего шага → optional `declinePending` / mandatory zero-step (ai-decision.service.ts:143-150). Drain: реальный `AiTurnService.runOneStep`→`dispatch`→реальный executor, смежные бойцы, mandatory zero-step + optional decline + `pendingTurnEnd` + ровно одна передача, seq 10→12 (s04-ai-queue.spec.ts:128-157, зелёный).

**P2-1 закрыт.** `isCellPassable` (traversal.ts:28-31): undefined-дыра/wall/obstacle/закрытая дверь → «Клетка непроходима» для MOVE и PLACE. Тест зелёный.

**P2-2 закрыт.** occupied (590) и blockedPositions (606) — оба `isLivingFighter` (= `health>0 && !isDefeated`, идентичен AI `living()`). Тест зелёный.

**P2-3 закрыт.** `myQueueLeft` фильтрует `playerId === localUserId` (GameView.tsx:88); `myPendingEffects` гейтится на глобальную голову (remoteGameStore.ts:358-364) — чужая голова не рисуется, свой хвост не кликабелен. Тест [свой, чужой, свой] → «ещё в очереди: 1». Зелёный.

## Acceptance-чеки разработчика

**Human zero-step в Phaser — ДОСТУПЕН.** Цепочка: клик по своему бойцу → `pendingFighterId` (GameView.tsx:156-162) → клик по клетке → `resolvePendingEffect` (164-171). Геометрия: rect клетки 68px интерактивен (GameScene.ts:357-363), хит-круг героя r=41 < диагональ угла 48 (sidekick r=34) → клик в угол своей клетки эмитит `SPACE_CLICKED` с собственными координатами → сервер принимает. Работает для MOVE/PLACE, своих и `targetsOpponent` бойцов. Мешковато (нет кнопки «остаться», в отличие от панели манёвра) — UI-polish, не strand. Обязательный выбор разрешим реальным вводом.

**AI drain со смежным after-combat MOVE** — покрыт спекой через реальный dispatch/drain (выше). HTTP-e2e VS_AI-матч не гонялся — README заявляет это честно.

## Остаточные гонки (P3, не блокируют, GD-016 не ломают)

1. `setupAiOpponent` (game.service.ts:781-808): check-then-act без лока; двойной клик «Старт» в VS_AI без бота → второй create ловит `@@unique(gameId,userId)` → P2002 → 500 одному из запросов, ретрай проходит, дубль-ростера нет.
2. Stale pre-tx `player`-рид в selectHero (906-913): уход игрока между ридом и транзакцией → P2025 raw-error (не 4xx), дубля нет.
3. `toggleReady` (861-885) вне лока: может закоммитить `isReady=false` после IN_PROGRESS — косметика, после старта флаг не используется.

## Прочее

- Тестовая БД изолирована: URL hardcoded на 55432/s04_test + `S04_PG_URL` override, `db push` per-command только в неё, skip при недоступности, prod-credential не трогаются.
- Доки (README/verification.json) соответствуют коду и прогонам, оговорки честные (UE/ACC-008 → S05+, zero-step только «up to N»).
- Контрпримеров против пяти фиксов не нашёл; счётчик seq в drain (ai-turn.service.ts:74-77) не даёт зацикливания на zero-step/decline.

## Follow-up ownership

Nonblocking lobby races listed above remain tracked for GD-029 (S08): idempotent VS_AI setup, selection concurrent with leave, readiness concurrent with start. A clear stay-in-place UI action belongs to choice UI GD-035 (S09); current input path is verified in this review. These findings do not constitute completed downstream acceptance.
