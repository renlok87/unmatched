# Приложение: выжимка фактов бэкенда

Статус: `ФАКТ` (источник — `docs/backend-api/`, исследование 2026-09-18). Это справочная выжимка для авторов пакета; первоисточник всегда приоритетнее. Ссылки вида `NN:строка` указывают на файлы `docs/backend-api/`.

## Транспорт и авторизация

- Единый endpoint: `http://localhost:3000/graphql` (HTTP) + `ws://localhost:3000/graphql`, субпротокол `graphql-transport-ws` (пакет graphql-ws, НЕ legacy) — README:29, 06:36-42.
- JWT: HTTP — заголовок `Authorization`; WS — `connectionParams.authorization` в `connection_init` (per-subscription auth не работает) — README:30, 01:179-191, 06:89-93.
- WS-ошибки: 4403 Forbidden (токен отклонён → refresh+reconnect), 4408 init timeout, 4409 дубликат id подписки — 06:256,585-590.
- Refresh-цикл: на `UNAUTHENTICATED`/`AUTH_TOKEN_EXPIRED`/`AUTH_INVALID_TOKEN`/401 → `refreshTokens` → повтор; после refresh пересоздать WS; ротация refresh-токена (старый инвалидируется — сохранять оба); хранение в USaveGame — 02:36-40,316-321, 06:139-149. Access JWT 1 ч, refresh 24 ч (env-варианты расходятся — 01:229).
- Лимиты схемы: complexity ≤1000, depth ≤7, `forbidNonWhitelisted` — 06:66-71.

## Игровые мутации (все возвращают GameMutationResult: state: String(JSON), sequenceNumber, timestamp, phase, currentTurnPlayerId, turnCount)

Источник: 04:177-277; guard'ы/лимиты: 07:158-171.

| Мутация | Input (кратко) | Тратит действие | Событие |
|---|---|---|---|
| `maneuver` | gameId, moves:[{fighterId, path:[{x,y 0..19}]}], boostCardId | да | MANEUVER |
| `moveFighter` | gameId, fighterId, x, y | да | FIGHTER_MOVED |
| `attack` | gameId, attackerId, targetId, cardId, boostCardId? | да (карта списывается сразу) | ATTACK_INITIATED + таймер auto-resolve 30 с |
| `playDefense` | gameId, cardId, boostCardId? (только защитник, фаза COMBAT) | нет | DEFENSE_PLAYED (отменяет таймер) |
| `resolveCombat` | gameId | — | COMBAT_RESOLVED (отменяет таймер) |
| `playScheme` | gameId, cardId | да | CARD_PLAYED |
| `resolvePendingEffect` | gameId, effectId, fighterId?, x?, y?, optionIndex? | нет | CARD_PLAYED |
| `endTurn` | gameId | нет | TURN_ENDED |
| `pass` | gameId | да (passCount++) | журнал PASSED, событие CARD_PLAYED |
| `toggleDoor` | gameId, x, y (способность Bjorn) | нет | DOOR_TOGGLED |
| `setStance` | gameId, stanceId (бесплатна, не тратит действие) | нет | SPECIAL_ABILITY |

Rate limits: maneuver/moveFighter/endTurn/toggleDoor/setStance/resolvePendingEffect — 30/мин; attack/playDefense/resolveCombat/playScheme/pass — 20/мин — 04:21, 11:322-337.
Шпаргалка «мутация → событие»: 04:553-570.

## Фазы и таймеры

- Фазы: `SETUP, TURN_START, ACTION_MANEUVER, ACTION_ATTACK, COMBAT, COMBAT_RESOLVE, TURN_END, GAME_OVER` — 04:56-65. Продакшен-поток: TURN_START пропускается (ход сразу с ACTION_MANEUVER), SETUP/TURN_END — legacy — 05:34, 10:16-23. Внимание: 03:40 даёт устаревший набор фаз — брать из 04/07.
- 2 действия за ход (`ACTIONS_PER_TURN=2`, счётчик `metadata.actionsRemaining`), после 2-го действия ход завершается автоматически — 04:76, 10:26-29.
- Auto-resolve боя: **30 с** после attack (`DEFAULT_DEFENSE_TIMEOUT`), отменяется playDefense/resolveCombat; дедлайн в `metadata.combatInfo.timeoutAt` — 04:36,225,233,406,531.
- Подтверждение резолва: 10 с (`DEFAULT_RESOLVE_TIMEOUT`) — 10:133, 11:193.
- Матчмейкинг: подтверждение матча 30 с (Redis TTL 35 с); scheduler подбора каждые 5 с; ELO-окна 0-30с ±100 / 30-60 ±200 / 60-120 ±400 / 120+ без ограничений — 03:402-419, 11:234-241.
- Presence: heartbeat TTL 300 с — 03:465.
- Distributed lock на мутацию TTL 10 с; Redis-кеш GameState TTL 600 с — 11:123-129, 11:89.

## Лобби и матчмейкинг

- Три пути: приватная комната (`createGame {mode?, boardId?}+idempotencyKey` → код из 6 символов без I O 0 1 → `joinGame {gameId, heroId?, asOpponent?}`), список `availableGames`, матчмейкинг — 03:29-33.
- Жизненный цикл: PENDING → LOBBY → IN_PROGRESS → FINISHED/ABORTED; `startGame` — только хост, все isReady; VS_AI добавляет бота автоматически — 03:214-229.
- `leaveGame`: opponent освобождает слот; хост без opponent удаляет игру; выход из начавшейся игры прерывает её — 03:231-237.
- Матчмейкинг: `joinQueue {mode, heroPref}` → `matchFound` (подписка; подписаться ДО joinQueue; событие не повторяется) → `acceptMatch` (возвращает «оба приняли») → игра в LOBBY — 03:368-453. Штрафы: decline −25 ELO; 3 decline/час → бан 30 мин — 03:421-430.
- Подписки комнаты: playerJoined, playerLeft, gameStateUpdated, turnChanged, gameEnded, attackInitiated, defensePlayed, combatResolved — 03:309-317.
- Ограничение: PubSub матчмейкинга in-memory (один инстанс) — 03:455, 11:399.

## Синхронизация состояния

- `gameStateUpdated(gameId!, since: Float)`: `gameId, sequenceNumber, phase, turnCount, currentTurnPlayerId` + **пять JSON-строк**: `players, fighters, handZones, boardState, metadata` — 04:442-453. `decks/discardPiles` в подписку НЕ входят.
- sequenceNumber: +1 за мутацию; optimistic lock в saveState; защита от дублей — сравнение на клиенте.
- HTTP-ответ мутации содержит то же состояние, что и подписка → дедупликация по номеру обязательна — 04:530.
- Алгоритм клиента: `seq <= last` → отбросить; `seq > last+1` → gap → `eventsSince(gameId, lastSeq)` (пачки по 100, hasMore) и/или полный `gameState` — 04:524-529, 06:493-511.
- Полный `gameState` (query) возвращает всё одним полем `state` (включая decks/discardPiles) — 04:110-131.
- Фильтрация приватного: чужая рука = name:"???", isVisible:false, без значений/эффектов; topCard чужой колоды удалён — 04:427-433.
- VS_AI: ходы бота асинхронны после твоей мутации, приходят ТОЛЬКО через подписку — 04:533.
- Reconnect: lastSeq → `gameSequence(gameId)` → `eventsSince` пачками → свежий `gameState` → перевзятие подписки с `since` — 11:288-302. Журнал вычищается через 30 дней → тогда только полный gameState — 11:300.

## Контент

- Публичные queries: heroes, heroesPaginated, hero(id: имя|cuid), heroesBySet, cards(heroId), card, boards, board, sets, contentSummary, contentVersion, heroStances — 05:408-424.
- `HeroDto.id = hero.name` (имя как публичный ID); Hero: health, movement, set, fighterType, sidekickCount, sidekickHealth, abilities, cards, urls{avatar, mini, cardCover} — 05:395,429-447.
- `miniModelUrl` (.glb), `characterCardUrl`, `sidekicks`, `additionalMinis` — только в админских AdminHero/CreateHeroInput, в публичном Hero их НЕТ — 05:364-365, 12:88-90.
- Card: title, type (ATTACK|DEFENSE|SCHEME|VERSATILE), value, boost, quantity=count, effects, imageUrl/imageUrlRu — 05:398,449-460.
- Board: id=имя, width, height, recommendedPlayers, spaces{position{x,y}, zones:[Zone], isObstacle, startingPositionsJson}, imageUrl; 12 зон-цветов; engine Cell: zones[] мультизонность, isHighGround, isOpen — 05:399,462-472.
- `contentVersion` — константа '2.0.0', инкремент вручную; getContentDiff — примитивный — 05:387, 12:271-273.
- Redis-кеш контента TTL 1 ч; админ-мутации кэш НЕ инвалидируют — 05:387, 12:264-276.
- Ассеты: URL в БД — корневые `/assets/...`, лежат во фронтенде (`public/assets/`), бэкенд не раздаёт. Паттерны: карты EN `/assets/decks/<heroSlug>/<cardSlug>.webp`, RU `.../ru/<cardSlug>-ru.png`; герой avatar.webp/mini.webp/card-cover.webp; борд `/assets/boards/<slug>.webp` — 05:476-511.
- Порядок загрузки контента в UE: contentVersion → AllHeroes → HeroDetails → AllBoards → HeroStanceOptions → скачивание ассетов — 05:637-645.
- Дефект: `movement` публичного героя захардкожен 3 — 05:396.

## Стойки

- Хранение: `metadata.heroStances: Record<userId, stanceId>`; дефолт — стойка default:true — 05:311-319.
- `setStance` бесплатна; валидация: герой stance-aware и id в списке — 04:271-277.
- Справочник: query `heroStances(heroSlug) → [{id, label, isDefault}]`; для не-стоечных героев [] — 04:148-155.
- Stance-герои в реестре: alice (big/small), muhammad-ali (float/sting) — 08:207-220. Medusa/King Arthur — не стоечные.

## Известные ограничения сервера (для GAP-реестра)

1. Auto-resolve не применяет урон (TODO) — 11:397, 10:133.
2. playerJoined/playerLeft в игровой фазе не публикуются (только лобби-payload) — 04:512, 07:236-237.
3. `clearContentCache` помечен @Public() (недочёт безопасности) — 07:48.
4. CONTENT_VERSION — константа; кэш не инвалидируется админ-мутациями — 12:271-276.
5. Очереди combat-resolution/game-state-persist — заготовки (реальный резолв синхронный в мутациях) — 11:198-199.
6. `updateEloRatings` не вызывается автоматически при GAME_OVER — 11:75.
7. matchFound PubSub in-memory — 11:399.
8. `movement` героя = 3 захардкожен — 05:396.
9. PLACE-эффекты: зонные ограничения TODO — 10:266.
10. Turn-start-move препятствия/двери TODO — 08:237.
11. isHighGround/fog не используются логикой — 10:189,198.
12. ranged читает legacy `zone`, не мультизоны — 10:117.
13. Несостыковки самих доков: 01:208 устаревшие имена queries; 01:229 расходящиеся TTL; 03:40 устаревшие фазы; 06:485 пример AttackDto не по контракту; 06:211 несуществующее значение фазы "MAIN".
