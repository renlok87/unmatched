# R7 — Веб-клиент: каталог поведения для портирования в UE-клиент

Дата: 2026-09-02. Ветка: `fix/admin-panel`. Автор: ридер R7 (агент).
Источники — веб-клиент React 18 + Apollo Client 3.14 + graphql-ws 6 + Phaser 3.90 + zustand 5 (`package.json:21-31`), документация `docs/FRONTEND_ARCHITECTURE.md`, `docs/frontend-tasks/*`, `docs/plans/*`, а также точечные сверки с бэкендом (`backend/src/...`) там, где поведение клиента без них непонятно. Все ссылки вида `файл:строка` относятся к корню репозитория `C:/Users/ren/WebstormProjects/unmached/unmached`.

---

## 1. Краткое резюме

1. **Единственный production-путь веб-клиента** — `/lobby → /room/:gameId → /game/:gameId`. В игре истина всегда у сервера: `remoteGameStore` грузит полное wire-состояние (`GetGame` → контентные `hero(id=имя)`/`boards`/`heroStances` → `GetGameState`), подписка `gameStateUpdated` доставляет **полные снапшоты** (не дельты), каждая gameplay-мутация возвращает `state` (полный JSON) и применяется немедленно, эхо подписки дедуплицируется по `sequenceNumber` (`src/store/remoteGameStore.ts:1-14, 295-316, 458-490`). Оптимистичных обновлений в production-пути **нет** — `useOptimisticUpdate`, `GameStateBridge`, `SubscriptionHandler`, `GameActions`, `phaser/hooks/*` помечены `@deprecated B5` и никем не импортируются.
2. **Wire-формат** (`src/lib/gameStateAdapter.ts:36-136`): query/mutation → одна JSON-строка `state`; подписка → те же данные, но `players/fighters/handZones/boardState/metadata` — пять отдельных JSON-строк **без `decks`/`discardPiles`** (мержатся из предыдущего снапшота). Фазы сервера: `SETUP|TURN_START|ACTION_MANEUVER|ACTION_ATTACK|COMBAT|COMBAT_RESOLVE|TURN_END|GAME_OVER` (`src/gql/graphql.ts:479-488`). Все данные per-user отфильтрованы бэком (чужие карты руки приходят как `name:'???'`, `isVisible:false`, без значений — `backend/src/games/game-state.service.ts:494-536`).
3. **Транспорт**: HTTP `POST /graphql` с `authorization: Bearer <accessToken>` (`src/lib/auth-link.ts:11-27`), WS graphql-ws на тот же путь с `connectionParams.authorization` (`src/lib/apolloClient.ts:16-36`; бэк принимает `authorization|Authorization|token` — `backend/src/graphql/graphql.module.ts:22-33`). Refresh по коду ошибки `UNAUTHENTICATED|AUTH_TOKEN_EXPIRED|AUTH_INVALID_TOKEN` или HTTP 401 с single-flight `refreshTokens` (`src/lib/error-link.ts:9-101`, `src/store/authStore.ts:220-281`). Retry: 3 попытки, backoff 300 мс → 10 с с jitter, мутации не ретраятся (`src/lib/retry-link.ts:8-61`). Токены в localStorage с ключами `unmached_access_token|refresh_token|token_expiry`, TTL клиентский 1 ч (`src/lib/token-storage.ts:6-9, 108`); бэк: access 1h, refresh 24h (`backend/src/auth/auth.service.ts:472, 483`).
4. **Реконнект подписки**: `useGameSync` — до 5 попыток, задержка `1000 мс × номер_попытки` (линейная, комментарий ошибочно называет её экспоненциальной), `since = lastSequenceNumber`, при `complete` — фиксированная 1000 мс (`src/hooks/useGameSync.ts:57-64, 161-169, 186-194`). Бэк фильтрует события подписки `payload.sequenceNumber > since` (`backend/src/games/resolvers/game-subscription.resolver.ts:157-166`). Детекция «дыр» seq на клиенте **не нужна**: каждый снапшот полный; при ошибке `Concurrent modification|sequence` стор делает `refetchState` (`src/store/remoteGameStore.ts:485-487`).
5. **Phaser-сцена** (`src/phaser/scenes/GameScene.ts`, 1188 строк) — единственная живая визуализация: доска 6×4 клетки по 72 px с зонами-кружками, бойцы-контейнеры (мини-арт + HP-бар + кольцо выбора), рука до 7 карт (58×84) с рантайм-подгрузкой артов по `imageUrl`, HUD-панели двух игроков, чип хода, рубашки руки соперника, инспектор выбранной карты; анимации — только tween-движение фишки (280 мс) и всплывающий урон (900 мс). Богатая библиотека анимаций/эффектов/рендереров (`animations/`, `effects/`, `renderers/`, `ui/CombatUI.ts`, `entities/`, `sprites/`, `camera/`, `input/`, `MainGameScene`) **не подключена** ни к одной сцене (проверено grep импортов, см. §2.14).
6. **Ловушки, подтверждённые кодом**: (а) `roomStore.isHost` читает `localStorage.userId`, который **никто не пишет** → кнопка «Начать игру» у хоста не появляется без ручной установки ключа (`src/store/roomStore.ts:126`); (б) `MatchmakingView` подписывается на `matchFound` с захардкоженным `userId='current-user-id'` (`src/components/matchmaking/MatchmakingView.tsx:32`); (в) deprecated `GameActions.playDefense/toggleDoor` шлют поля `combatId`/`doorId`, которых нет в `PlayDefenseDto`/`ToggleDoorDto` (`src/gql/graphql.ts:1076-1080, 1560-1564`); (г) `apolloClient.subscribe` даёт `FetchResult {data}` — событие в `result.data.gameStateUpdated`, иначе realtime молча теряется (`src/hooks/useGameSync.ts:121-132`); (д) `HERO_VISUALS` захардкожен на ms-marvel/daredevil — остальные герои рисуются с fallback-артом Ms. Marvel (`src/phaser/scenes/GameScene.ts:25-51, 1016-1024`).

---

## 2. Исчерпывающие факты по фокусу

### 2.1. Стек, точки входа, роутинг экранов

| Факт | Источник |
|---|---|
| Зависимости: `@apollo/client ^3.14.0`, `graphql-ws ^6.0.7`, `phaser ^3.90.0`, `react ^18.3.1`, `react-router-dom ^7.13.0`, `zustand ^5.0.2` | `package.json:21-31` |
| Точка входа: `initAuthStore()` (проверка токенов + `me`) **до** рендера, затем `<ApolloProvider><App/>` в `StrictMode` | `src/main.tsx:9-17` |
| `App` = `<AppRouter/>` (BrowserRouter) | `src/App.tsx:1-8`, `src/routes/index.tsx:23-66` |
| Codegen: схема по интроспекции `http://localhost:3000/graphql`, документы `src/graphql/**/*.graphql`, output `src/gql/` (client preset, `gql` tag) | `codegen.ts:3-27` |
| Vite dev-порт 5174, `publicDir: 'public'`, alias `@ → src` | `vite.config.ts:11-23` |
| URL API: `VITE_API_URL` (default `http://localhost:3000/graphql`), `VITE_WS_URL` (default `ws://localhost:3000/graphql`) | `src/env.ts:7-8` |
| `.env` содержит и `VITE_WS_URL` (верх), и `VITE_WS_URI` (низ, не читается кодом) — рассинхрон, отмеченный планом B5 | `.env` (вывод `cat .env`), `docs/plans/2026-06-12-remaining-features.md:442` |

Маршруты (`src/routes/index.tsx:27-63` + подроутеры):

| Путь | Компонент | Guard | Источник |
|---|---|---|---|
| `/` → redirect `/lobby` | — | — | `src/routes/index.tsx:29` |
| `/auth/login` | `LoginForm` | нет (`/register` закомментирован) | `src/routes/auth.routes.tsx:5-13` |
| `/lobby`, `/lobby/create` | `LobbyView` | `ProtectedRoute` → `/auth/login` | `src/routes/lobby.routes.tsx:7-25`, `src/routes/protected.route.tsx:9-23` |
| `/lobby/matchmaking` | `MatchmakingView` | `ProtectedRoute` | `src/routes/lobby.routes.tsx:15` |
| `/heroes/:gameId` | `HeroSelection` | **нет guard** | `src/routes/hero.routes.tsx:5-12` |
| `/cards/show/:cardId` | `CardShow` | нет | `src/routes/index.tsx:41` |
| `/room/:gameId` | `RoomView` | `AuthGuard` (redirect `/login?returnUrl=…` — путь `/login` не существует в роутере!) | `src/routes/room.routes.tsx:6-23`, `src/components/auth/AuthGuard.tsx:31-63` |
| `/game/:gameId` | `GameView` | `AuthGuard` | `src/routes/game.routes.tsx:6-23` |
| `/leaderboard`, `/profile[/:userId]`, `/social/friends` | `LeaderboardView`, `ProfileView`, `FriendsList` | `AuthGuard` | `src/routes/leaderboard.routes.tsx`, `profile.routes.tsx`, `social.routes.tsx` |
| `/test-game/*` | `TestGamePage` (локальный движок, песочница) | нет | `src/routes/test-game.routes.tsx:4-9` |

Несоответствия навигации: `LobbyView.handleMatchmaking` ведёт на `/matchmaking` (не `/lobby/matchmaking`) → 404 → redirect `/lobby` (`src/components/lobby/LobbyView.tsx:63-65`, `src/routes/index.tsx:62`). `AuthGuard.redirectTo` по умолчанию `/login`, `ProtectedRoute` — `/auth/login` (`src/components/auth/AuthGuard.tsx:35`, `src/routes/protected.route.tsx:19`). `LoginForm` ссылка «Зарегистрироваться» на `/register`, `VictoryScreen` — на `/matchmaking` (`src/components/auth/LoginForm.tsx:150`, `src/components/game/VictoryScreen.tsx:79`).

### 2.2. Транспорт: Apollo link chain и WS-клиент

**Цепочка** `ApolloLink.from([retryLink, authLink, errorLink, splitLink])` (`src/lib/apolloClient.ts:78-83`). Split: `subscription` → `GraphQLWsLink(wsClient)`, иначе `HttpLink({ uri: APOLLO_URI, credentials: 'include' })` (`src/lib/apolloClient.ts:38-61`).

**WS-клиент graphql-ws** (`src/lib/apolloClient.ts:16-36`):
- `url: APOLLO_WS_URI`; `connectionParams: () => ({ authorization: token ? 'Bearer '+token : '' })` — токен читается из `tokenStorage` в момент (ре)коннекта; `lazy: true`; `retryAttempts: 5`; хендлеры `connected/error/closed` только логируют.
- `reconnectWebSocket()` = `wsClient.terminate()` — экспортирована, но **нигде не вызывается** после refresh (grep по `reconnectWebSocket` даёт только определение). Следовательно, после refresh токена уже открытый WS продолжает жить со старым JWT.
- Бэк: `subscriptions: {'graphql-ws': true}`; из `connectionParams` берёт `authorization || Authorization || token`, добавляет префикс `Bearer ` если его нет, кладёт в `req.headers.authorization` для `GqlAuthGuard` (`backend/src/graphql/graphql.module.ts:19-33`). Лимит сложности запроса 1000 (`:36-46`).

**authLink** (`src/lib/auth-link.ts:11-27`): `setContext` → `headers.authorization = 'Bearer '+(authStore.accessToken || tokenStorage.getAccessToken() || '')`. При отсутствии токена шлётся **пустой** заголовок `authorization: ''`.

**retryLink** (`src/lib/retry-link.ts:8-61`): `delay {initial: 300, max: 10000, jitter: true}`, `attempts.max: 3`. `retryIf`: не ретраить если `operation.operationName === 'Mutation'` (сравнение с литералом — реальные имена операций `Login`, `Maneuver` и т. п., поэтому **фактически мутации тоже ретраятся** при сетевой ошибке); ретраить при `networkError`; ретраить GraphQL-ошибки с `extensions.code ∈ {SERVICE_UNAVAILABLE, NETWORK_ERROR, TIMEOUT, INTERNAL_SERVER_ERROR, DATABASE_ERROR}` или сообщением, содержащим `timeout|network|service unavailable`.

**errorLink** (`src/lib/error-link.ts:31-101`):
- `isAuthError`: `extensions.code ∈ {UNAUTHENTICATED, AUTH_TOKEN_EXPIRED, AUTH_INVALID_TOKEN}` или сообщение содержит `unauthenticated|token expired|invalid token` (`:9-23`).
- При auth-ошибке: нет refresh-токена → `logout()` и throw; иначе `await refreshTokens()`; неудача → `logout()`; успех → `forward(operation)` (повтор запроса — authLink подставит новый токен) (`:35-61`).
- `networkError.name === 'AbortError'` или `/\baborted?\b/i` → тихо игнорируется (dev StrictMode рвёт in-flight fetch) (`:70-75`).
- `networkError.statusCode === 401` → тот же refresh-flow (`:80-99`).
- Класс `AuthErrorLink` (`:106-130`) — альтернатива, **не используется**.

**Apollo cache / defaultOptions** (`src/lib/apolloClient.ts:93-135`): `typePolicies.Query.fields.{games, game, gameState}.merge = incoming` (перезапись), `watchQuery: {errorPolicy:'all', fetchPolicy:'cache-and-network'}`, `query/mutate: {errorPolicy:'all'}`. Из-за `errorPolicy:'all'` ошибки приходят в `errors` **рядом с data**, поэтому весь код проверяет `errors?.length` вручную.

### 2.3. Хранение токенов и auth-flow

| Факт | Источник |
|---|---|
| Ключи localStorage: `unmached_access_token`, `unmached_refresh_token`, `unmached_token_expiry` (ms epoch строкой) | `src/lib/token-storage.ts:6-9, 48-56` |
| `getTokens()` возвращает `null` и **стирает** токены, если `Date.now() >= expiresAt` (все три ключа обязательны) | `src/lib/token-storage.ts:20-43` |
| `calculateExpiry(expiresInMs = 60*60*1000)` — клиент сам ставит TTL 1 ч (сервер `expiresIn` не читается) | `src/lib/token-storage.ts:108-110`, `src/store/authStore.ts:113-117, 257-261` |
| `isTokenExpiringSoon()` — порог 5 мин; нигде не используется (grep) | `src/lib/token-storage.ts:90-96` |
| Бэк: access `jwt.expiresIn` default `1h`, refresh `jwt.refreshExpiresIn` default `24h` | `backend/src/auth/auth.service.ts:472, 483`, `backend/src/config/configuration.ts:27` |
| `login/register` → мутации `Login/Register` (`RegisterDto {email, username, password}`, `LoginDto {email, password}`) → `AuthResponseDto {accessToken, refreshToken, user{id,email,username}}` → `setTokens` + `user` (avatar:null) | `src/store/authStore.ts:89-190`, `src/gql/graphql.ts:155-160, 678-681, 1447-1451` |
| `logout` → мутация `Logout` (ошибки глотаются) → `clearTokens` + сброс state | `src/store/authStore.ts:195-213` |
| `refreshTokens` — single-flight (`_isRefreshing/_refreshPromise`), мутация `RefreshTokens($refreshToken)` → новые оба токена; провал → `clearTokens` + сброс (throw) | `src/store/authStore.ts:220-281` |
| `fetchMe` → query `Me` (`fetchPolicy: network-only`); `initAuthStore`: есть токены → `fetchMe`, нет → `setUser(null)` | `src/store/authStore.ts:304-334, 353-367` |
| Идентификатор текущего пользователя: `authStore.user?.id ?? localStorage.getItem('userId')` — но **`localStorage.userId` никто не пишет** (grep `setItem` находит только token-storage) | `src/store/remoteGameStore.ts:139-141`, `src/store/roomStore.ts:126`, `src/components/room/RoomView.tsx:148`, `src/components/room/RoomChat.tsx:38-39` |
| Валидация форм: email regex, пароль ≥6 (login) / ≥8 + буква + цифра (register), username 3–20 `[a-zA-Z0-9_-]` | `src/components/auth/LoginForm.tsx:36-55`, `src/components/auth/RegisterForm.tsx:39-80` |
| Idempotency: `createGame/joinGame/joinQueue/leaveQueue/leaveAllQueues` передают аргумент `idempotencyKey` (`${Date.now()}-${random36(9)}`); `toggleReady/startGame/selectHero` — заголовок `X-Idempotency-Key`. На бэке аргумент есть только у `createGame` (`MutationCreateGameArgs.idempotencyKey`); заголовок лишь пропущен через CORS | `src/store/lobbyStore.ts:25-45, 73-75`, `src/store/matchmakingStore.ts:6-29, 102-104`, `src/store/roomStore.ts:163, 181-188, 285, 305-312`, `src/gql/graphql.ts` (`MutationCreateGameArgs`, `MutationJoinGameArgs` — без ключа), `backend/src/main.ts:92-95, 124-129` |

### 2.4. Каталог GraphQL-операций (перенести 1:1)

Легенда «Статус»: **PROD** — используется production-путём (лобби/комната/игра); **AUX** — используется вспомогательным экраном; **DEAD** — определена, но не импортируется/используется мёртвым кодом; **INVALID** — не соответствует схеме бэка.

#### 2.4.1. Queries из `src/graphql/queries/*.graphql`

| Имя | Файл:строки | Аргументы | Выбираемые поля | Кем используется | Статус |
|---|---|---|---|---|---|
| `Me` | `queries/auth.graphql:3-18` | — | `me{id email username avatar createdAt settings{theme soundEnabled musicEnabled language profileVisible}}` | `authStore.fetchMe` (`authStore.ts:308-313`) | PROD |
| `MyStats` | `queries/auth.graphql:20-30` | — | `myStats{userId gamesPlayed gamesWon gamesLost winRate currentElo peakElo}` | не найдено использование | DEAD |
| `MySettings` | `queries/auth.graphql:32-40` | — | `mySettings{theme soundEnabled musicEnabled language profileVisible}` | не найдено | DEAD |
| `GetCards` | `queries/cards.graphql:1-21` | `page:Int!, limit:Int!` | `cardList{items{id name nameEn nameRu cardType subType attackValue defenseValue boostValue bannerName count heroId imageUrl imageUrlRu} total}` | не найдено | DEAD |
| `GetCard` | `queries/cards.graphql:23-40` | `id:String!` | `card{id title type value boost quantity characterName imageUrl imageUrlRu effects{id timing text}}` | `CardShow` использует **свой** inline `GET_CARD_QUERY` с тем же именем (`CardShow.tsx:11-28`) | AUX |
| `GetGame` | `queries/game.graphql:3-28` | `id:String!` | `game{id mode status hostId boardId winnerId createdAt updatedAt startedAt endedAt phase currentTurn players{id userId username avatar heroId isReady hasPassed seatOrder}}` | `remoteGameStore.connectToGame` (шаг 1), `HeroSelection.pollGameStatus` | PROD |
| `MyGames` | `queries/game.graphql:30-47` | `filters:GameFiltersDto` | `myGames{id mode status hostId createdAt phase currentTurn players{userId username avatar heroId isReady}}` | не найдено | DEAD |
| `AvailableGames` | `queries/game.graphql:49-61` | `mode:String, limit:Float` | `availableGames{id mode status players{userId username avatar heroId}}` | `lobbyStore` использует **inline** `AVAILABLE_GAMES_QUERY` с тем же именем и полями `id mode status hostId boardId createdAt players{userId username avatar heroId}` (`lobbyStore.ts:6-23`) | PROD (inline-версия) |
| `GetGameState` | `queries/game.graphql:63-74` | `gameId:String!` | `gameState{id gameId state sequenceNumber currentTurnPlayerId phase turnCount updatedAt}` | `remoteGameStore.connectToGame`/`refetchState` (`:191-197, 329-333`) | PROD |
| `GetGameSequence` | `queries/game.graphql:76-78` | `gameId:String!` | `gameSequence` (Float) | не найдено | DEAD |
| `EventsSince` | `queries/game.graphql:80-93` | `gameId:String!, sinceSequence:Float!` | `eventsSince{gameId events{sequenceNumber type gameId payload timestamp} lastSequence hasMore}` | не найдено (план B2 признал ненужным) | DEAD |
| `Heroes` | `queries/game.graphql:97-108` | — | `heroes{id name health movement set fighterType sidekickCount sidekickHealth}` | `testGameStore.loadHeroes` (песочница) | AUX |
| `Hero` | `queries/game.graphql:110-135` | `id:String!` | `hero{id name health movement set fighterType abilities{id name text trigger} cards{id title type value boost quantity imageUrl imageUrlRu}}` | не найдено (remoteGameStore использует inline `RemoteHeroAssets`) | DEAD |
| `Boards` | `queries/game.graphql:137-154` | — | `boards{id name width height recommendedPlayers imageUrl spaces{position{x y} zones isObstacle}}` | `CreateGameDialog` — inline `Boards` с урезанными полями (`CreateGameDialog.tsx:10-20`) | PROD (inline) |
| `Board` | `queries/game.graphql:156-173` | `id:String!` | как `Boards` | не найдено | DEAD |
| `ContentSummary` | `queries/game.graphql:175-183` | — | `contentSummary{heroesCount boardsCount setsCount version sets}` | не найдено | DEAD |
| `Sets` | `queries/game.graphql:185-187` | — | `sets` | не найдено | DEAD |
| `AllHeroes` | `queries/heroes.graphql:3-19` | — | `heroes{… urls{avatar mini cardCover}}` | `heroSelectionStore` — inline-копия (`heroSelectionStore.ts:99-117`) | AUX |
| `HeroDetails` | `queries/heroes.graphql:21-53` | `id:String!` | `hero{… urls{…} abilities{…} cards{id title type value boost quantity imageUrl imageUrlRu}}` | `HeroDetailsPanel` — inline-копия без `imageUrl` (`HeroDetailsPanel.tsx:19-51`) | AUX |
| `HeroesBySet` | `queries/heroes.graphql:55-71` | `set:String!` | `heroesBySet{… urls{…}}` | `heroSelectionStore` inline (`:80-98`) | AUX |
| `HeroStanceOptions` | `queries/heroes.graphql:75-81` | `heroSlug:String!` | `heroStances{id label isDefault}` | `remoteGameStore.connectToGame` шаг 4 (`:259-263`) | PROD |
| `LobbyAvailableGames` | `queries/lobby.graphql:1-20` | `mode:String, limit:Float` | `availableGames{id mode status host{id username avatar} opponent{id username avatar} boardId createdAt updatedAt}` | не найдено | DEAD |
| `QueueStatus` | `queries/matchmaking.graphql:1-10` | `mode:String!` | `queueStatus{inQueue mode position totalPlayers estimatedWaitTime joinedAt}` | `matchmakingStore` inline-копия (`:31-42`) | AUX |
| `PenaltyInfo` | `queries/matchmaking.graphql:12-20` | — | `penaltyInfo{canJoinQueue declineCount tempBanUntil penaltyElo reason}` | `matchmakingStore` inline-копия (`:44-54`), `fetchPenaltyInfo` нигде не вызывается | DEAD |
| `RoomInfo` | `queries/room.graphql:3-23` | `id:String!` | `game{id code status mode hostId boardId phase createdAt players{id userId username avatar heroId isReady seatOrder}}` | `roomStore.loadRoom` inline-копия (`roomStore.ts:84-106`) | PROD |
| `ValidSpawnZones` | `queries/room.graphql:25-36` | `gameId, playerId` | фактически `gameState{…}` (алиас GetGameState; `playerId` не используется) | не найдено | DEAD |

Inline-запросы вне `.graphql` (нужны UE-клиенту):

| Имя | Где | Поля | Статус |
|---|---|---|---|
| `RemoteHeroAssets($id)` | `src/store/remoteGameStore.ts:41-55` | `hero(id:$id){id name avatarUrl cards{id title imageUrl imageUrlRu}}` — **id = имя героя** (контентный резолвер ключуется именем) | PROD |
| `RemoteBoards` | `src/store/remoteGameStore.ts:57-73` | `boards{id name width height recommendedPlayers imageUrl spaces{position{x y} zones isObstacle}}` | PROD |
| `RoomHeroList` | `src/components/room/RoomView.tsx:45-51` | `heroList(limit:200){items{id name}}` — Prisma cuid для `selectHero` | PROD |
| `HeroWithAssets($id)`, `BoardsWithAssets` | `src/store/testGameStore.ts:21-77` | hero с `urls{}`+`avatarUrl`+abilities+cards; boards полные | AUX |
| `GetLeaderboard/GetFriendsLeaderboard`, `GetProfile/GetMatchHistory/GetRatingHistory/GetAchievements`, `GetFriends/GetFriendRequests`, `GetChatMessages` | `src/components/leaderboard/LeaderboardView.tsx:28,44`, `profile/ProfileView.tsx:46,54,74`, `profile/Achievements.tsx:6`, `social/FriendsList.tsx:10,26`, `chat/GameChat.tsx:27` | Запрашивают несуществующие поля/аргументы: на бэке `leaderboard(heroId,page,pageSize,timeFrame): String`, нет `profile/matchHistory/ratingHistory/achievements/friends/chatMessages` (`src/gql/graphql.ts` Query root, `QueryLeaderboardArgs`) | INVALID |

#### 2.4.2. Mutations из `src/graphql/mutations/*.graphql`

| Имя | Файл:строки | Input | Возврат | Использование | Статус |
|---|---|---|---|---|---|
| `Register($input: RegisterDto!)` | `mutations/auth.graphql:3-13` | `{email, username, password}` | `{accessToken refreshToken user{id email username}}` | `authStore.register` | PROD |
| `Login($input: LoginDto!)` | `mutations/auth.graphql:15-25` | `{email, password}` | то же | `authStore.login` | PROD |
| `RefreshTokens($refreshToken: String!)` | `mutations/auth.graphql:27-32` | — | `{accessToken refreshToken}` | `authStore.refreshTokens` | PROD |
| `Logout` | `mutations/auth.graphql:34-36` | — | `Boolean` | `authStore.logout` | PROD |
| `UpdateProfile($input: UpdateProfileDto!)` | `mutations/auth.graphql:38-44` | `{avatar?, username?}` | `{id username avatar}` | `EditProfileModal` использует свой inline с `UpdateProfileInput` (нет в схеме) | DEAD/INVALID |
| `UpdateSettings($input: SettingsDto!)` | `mutations/auth.graphql:46-54` | `{language? musicEnabled? profileVisible? showOnlineStatus? soundEnabled? theme?}` | settings | не найдено | DEAD |
| `CreateGame($input: CreateGameDto!)` | `mutations/game.graphql:3-18` | `{boardId?, mode?}` | `{id mode status hostId phase currentTurn players{…}}` | `lobbyStore` использует inline `CreateGame($input, $idempotencyKey)` → `{id mode status hostId boardId}` (`lobbyStore.ts:25-35`) | PROD (inline) |
| `JoinGame($input: JoinGameDto!)` | `mutations/game.graphql:20-32` | `{gameId, asOpponent?, heroId?}` | `{id status phase players{…}}` | `lobbyStore` inline `JoinGame($input, $idempotencyKey)` с `{gameId, asOpponent:true}` (`lobbyStore.ts:37-45, 250`); **`idempotencyKey` отсутствует в `MutationJoinGameArgs`** | PROD (inline), аргумент INVALID |
| `LeaveGame($gameId)` | `mutations/game.graphql:34-36` и дубликат `mutations/room.graphql:3-5` | — | `Boolean` | `remoteGameStore.leaveGame`, `roomStore.leaveRoom` (inline) | PROD |
| `StartGame($gameId)` | `mutations/game.graphql:38-48`, дубль `room.graphql:7-17` | — | `{id status phase players{userId heroId}}` | `roomStore.startGame` inline | PROD |
| `AbortGame($gameId)` | `mutations/game.graphql:50-55` | — | `{id status}` | не найдено | DEAD |
| `ToggleReady($gameId)` | `mutations/game.graphql:57-65`, дубль `room.graphql:19-27` | — | `{id players{userId isReady}}` | `roomStore.setReady` inline + заголовок `X-Idempotency-Key` | PROD |
| `SelectHero($gameId, $heroId)` | `mutations/game.graphql:67-75` | — | `{id players{userId heroId}}` | `RoomView` inline `RoomSelectHero` (`RoomView.tsx:83-92`), `heroSelectionStore.selectHeroOnServer` inline | PROD |
| `Maneuver($input: ManeuverDto!)` | `mutations/game.graphql:79-88` | `{gameId, fighterId?, cardId?(legacy), boostCardId?, path?[{x,y}], moves?[{fighterId, path[]}]}` | `GameMutationResult` | `remoteGameStore.maneuver` шлёт `{gameId, fighterId, boostCardId, path}` (`:378-381`); **из GameView не вызывается** (клики идут в `moveFighter`) | PROD (определён), в UI не задействован |
| `MoveFighter($input: MoveFighterDto!)` | `mutations/game.graphql:90-99` | `{gameId, fighterId, x:Int, y:Int}` | `GameMutationResult` | `remoteGameStore.moveFighter` ← `GameView SPACE_CLICKED` | PROD |
| `Attack($input: AttackDto!)` | `mutations/game.graphql:101-110` | `{gameId, attackerId, targetId, cardId, boostCardId?}` | `GameMutationResult` | `remoteGameStore.attack` ← клик по вражескому бойцу | PROD |
| `PlayDefense($input: PlayDefenseDto!)` | `mutations/game.graphql:112-121` | `{gameId, cardId, boostCardId?}` | `GameMutationResult` | `remoteGameStore.playDefense` ← клик по DEFENSE/VERSATILE в COMBAT | PROD |
| `ResolveCombat($input: ResolveCombatDto!)` | `mutations/game.graphql:123-132` | `{gameId}` | `GameMutationResult` | кнопки «Resolve»/«Без защиты» | PROD |
| `EndTurn($input: EndTurnDto!)` | `mutations/game.graphql:134-143` | `{gameId}` | `GameMutationResult` | кнопка «Конец хода» | PROD |
| `Pass($input: PassDto!)` | `mutations/game.graphql:145-154` | `{gameId}` | `GameMutationResult` | кнопка «Пас» | PROD |
| `ToggleDoor($input: ToggleDoorDto!)` | `mutations/game.graphql:156-165` | `{gameId, x:Int, y:Int}` | `GameMutationResult` | только deprecated `GameActions.toggleDoor` (шлёт `doorId` — INVALID) | DEAD |
| `PlayScheme($input: PlaySchemeDto!)` | `mutations/game.graphql:167-176` | `{gameId, cardId}` | `GameMutationResult` | `remoteGameStore.playScheme` ← клик по SCHEME в свой ход | PROD |
| `ResolvePendingEffect($input: ResolvePendingEffectDto!)` | `mutations/game.graphql:178-187` | `{gameId, effectId, fighterId?, x?, y?, optionIndex?}` | `GameMutationResult` | `resolvePendingEffect(effectId, fighterId, x, y)` (MOVE/PLACE) и `resolveChooseOption(effectId, optionIndex)` (CHOOSE_ONE) | PROD |
| `SetStance($input: SetStanceDto!)` | `mutations/game.graphql:190-199` | `{gameId, stanceId}` | `GameMutationResult` | `remoteGameStore.setStance` ← HUD стоек; «НЕ тратит действие» | PROD |
| `PlaceFighter($input: MoveFighterDto!)` | `mutations/room.graphql:29-38` | = `moveFighter` | `GameMutationResult` | не найдено (расстановка серверная) | DEAD |
| `ConfirmPlacement($gameId)` | `mutations/room.graphql:40-49` | = `pass(input:{gameId})` | `GameMutationResult` | не найдено | DEAD |
| `JoinQueue($input: JoinQueueDto!, $idempotencyKey)` | inline `matchmakingStore.ts:6-17` | `{mode: GameMode, heroPref?}` | `QueueStatusResponse` | `MatchmakingView` (`'ONE_V_ONE'`) | AUX; **`idempotencyKey` нет в `MutationJoinQueueArgs`** → INVALID аргумент |
| `LeaveQueue($mode, $idempotencyKey)`, `LeaveAllQueues($idempotencyKey)` | `matchmakingStore.ts:19-29` | — | Boolean | `MatchmakingView` | AUX; лишний аргумент INVALID |
| `acceptMatch(gameId)`, `declineMatch(gameId)`, `heartbeat(input)` | только в схеме (`src/gql/graphql.ts` Mutation root) | — | — | веб-клиент **не вызывает** (grep `heartbeat|acceptMatch` пусто) | не реализовано на клиенте |
| `SendChatMessage`, `AcceptFriendRequest`, `DeclineFriendRequest`, `RemoveFriend` | `chat/GameChat.tsx:36`, `social/FriendsList.tsx:40-57` | — | — | нет в Mutation root бэка | INVALID |

`GameMutationResult` = `{state?: String, sequenceNumber: Int, phase: GamePhase, currentTurnPlayerId?: String, turnCount: Int, timestamp: DateTime}` (`src/gql/graphql.ts:468-476`). Все gameplay-мутации выбирают ровно эти 6 полей.

Дубликаты имён операций `LeaveGame/StartGame/ToggleReady/GameStateUpdated/PlayerJoined/PlayerLeft` в `mutations/room.graphql` и `subscriptions/room.graphql` — codegen «client preset» генерирует документы по имени; наличие дублей означает, что документы совпадают побайтно (иначе codegen падает). В `src/gql/graphql.ts` по одному `…Document` на имя (`GameStateUpdatedDocument` используется `useGameSync`).

#### 2.4.3. Subscriptions

| Имя | Файл:строки | Аргументы | Поля | Использование | Статус |
|---|---|---|---|---|---|
| `GameStateUpdated($gameId: String!, $since: Float)` | `subscriptions/game.graphql:3-16` (дубль `room.graphql:3-16`) | `gameId`, `since` (схема также принимает `userId`, **игнорируется** бэком — фильтр по JWT) | `{gameId sequenceNumber phase turnCount currentTurnPlayerId players fighters handZones boardState metadata}` — последние 5 полей **строки JSON** | `useGameSync` (PROD), `useGameEvents` (DEAD), deprecated handlers | PROD |
| `AttackInitiated/DefensePlayed/CombatResolved/PlayerJoined/PlayerLeft/GameEnded($gameId)` | `subscriptions/game.graphql:18-46, 56-84` | `gameId` | `GameEvent{type gameId sequenceNumber timestamp payload}`; `payload` — JSON-строка `{phase, turnCount, currentTurnPlayerId}` для игровых событий или компактный лобби-объект `{userId, username}` / `{reason}` | только deprecated `SubscriptionHandler`/`useGameState` | DEAD на клиенте (на бэке живые) |
| `TurnChanged($gameId)` | `subscriptions/game.graphql:48-54` | — | `{playerId turnCount phase}` | deprecated | DEAD |
| `MatchFound($userId: String!)` | `subscriptions/matchmaking.graphql:1-10` | `userId` | `{gameId opponentId opponentUsername opponentRating mode expiresAt}` | `matchmakingStore.subscribeToMatchFound` — inline-копия с типом **`$userId: ID!`** (`matchmakingStore.ts:56-67`), тогда как схема ждёт `String!` (`SubscriptionMatchFoundArgs`) | AUX; тип аргумента INVALID |
| `presenceUpdated` | только схема | — | `Presence{userId status currentGameId lastSeenAt}` | не используется | — |
| `ChatUpdates($gameId)` | `chat/GameChat.tsx:45` | — | — | нет в Subscription root | INVALID |

Семантика бэка для `gameStateUpdated` (`backend/src/games/resolvers/game-subscription.resolver.ts:150-178`): фильтр `payload.gameId === gameId && payload.eventType === 'STATE_UPDATED' && (since == null || payload.sequenceNumber > since)`; ровно одно событие на мутацию; `resolve` фильтрует приватные данные по `context.req.user.id` и `JSON.stringify` пяти полей (`:45-64`). `GameEvent.payload` для игровых событий — только безопасное подмножество (`:81-98`).

#### 2.4.4. Enum-ы и справочные типы (из сгенерированной схемы)

| Тип | Значения | Источник |
|---|---|---|
| `GameMode` | `FREE_FOR_ALL, ONE_V_ONE, TWO_V_TWO, VS_AI` | `src/gql/graphql.ts:461-466` |
| `GameStatus` | `ABORTED, FINISHED, IN_PROGRESS, LOBBY, PAUSED, PENDING` | `:562-569` |
| `GamePhase` | `ACTION_ATTACK, ACTION_MANEUVER, COMBAT, COMBAT_RESOLVE, GAME_OVER, SETUP, TURN_END, TURN_START` | `:479-488` |
| `FighterType` (контент) | `HERO, SIDEKICK`; в wire-состоянии `type: 'HERO'|'MINION'|'HUGE'` | `:395-398`, `src/lib/gameStateAdapter.ts:47` |
| `CardType` (контент) | `ATTACK, DEFENSE, SCHEME, VERSATILE`; wire-карта также `MANEUVER|UNIVERSAL` (строки) | `:256-261`, `gameStateAdapter.ts:63` |
| `GameEventType` | `ATTACK_INITIATED, CARD_DISCARDED, CARD_PLAYED, COMBAT_RESOLVED, DEFENSE_PLAYED, DOOR_TOGGLED, EFFECT_APPLIED, FIGHTER_MOVED, GAME_ABORTED, GAME_CREATED, GAME_ENDED, GAME_JOINED, GAME_STARTED, MANEUVER, PASSED, PLACED, PLAYER_JOINED, PLAYER_LEFT, SPECIAL_ABILITY, TURN_CHANGED, TURN_ENDED, TURN_STARTED` | `:416-439` |
| `Zone` | `BEIGE, BLUE, BROWN, GOLD, GRAY, GREEN, ORANGE, PINK, PURPLE, RED, WHITE, YELLOW` (12); локальный `Zone` — те же в lowercase | `:1746-1759`, `src/core/models/types.ts:134-146` |
| `PresenceStatus` | `INGAME, INQUEUE, OFFLINE, ONLINE` | `:1107-1112` |
| `GameResponse` | `{id boardId boardState? code? createdAt currentTurn? endedAt? host hostId mode opponent? opponentId? phase? players[] startedAt? status updatedAt version winnerId?}` | `:512-533` |
| `GamePlayerResponse` | `{id userId username avatar? heroId? isReady hasPassed seatOrder}` | `:500-510` |
| `Hero` (контент) | `{id name nameEn? nameRu? health movement set fighterType sidekickCount? sidekickHealth? abilities[] cards[] avatarUrl? imageUrl? urls{avatar mini cardCover}?}` | `:591-610, 635-640` |
| `Card` (контент) | `{id title type value boost quantity characterName effects{id timing text} imageUrl? imageUrlRu?}` | `:215-227` |
| `Board`/`BoardSpace` | `{id name width height recommendedPlayers imageUrl? spaces{position{x y} zones[] isObstacle? startingPositionsJson?}}` | `:173-182, 198-204` |
| `HeroListItemDto` (Prisma) | `{id name nameEn nameRu set health fighterType ability? avatarUrl? imageUrl? createdAt}` | (вывод awk по `src/gql/graphql.ts`) |
| `StanceOptionDto` | `{id label isDefault}` | `:1480-1485` |
| `QueueStatusResponse` | `{inQueue mode? position? totalPlayers estimatedWaitTime joinedAt?}` | `:1437-1445` |
| `MatchFoundResponse` | `{gameId opponentId opponentUsername opponentRating mode expiresAt}` | `:697-705` |
| `PenaltyInfoDto` | `{canJoinQueue declineCount penaltyElo? reason? tempBanUntil?}` | `:1067-1074` |
| `UserWithSettingsResponse` (`me`) | `{id email username avatar? createdAt emailVerified? role settings?}` | `:1733-1743` |

### 2.5. Wire-формат GameState и `gameStateAdapter`

**Wire-типы** (`src/lib/gameStateAdapter.ts:36-136`):
- `WireGameState {gameId, sequenceNumber, phase: string, turnCount, currentTurnPlayerId, players: WirePlayer[], fighters: WireFighter[], decks?: Record<userId,{cards?, drawPile?}>, discardPiles?: Record<userId, WireCard[]>, handZones: Record<userId,{cards: WireCard[], maxSize}>, boardState {width, height, cells?: Array<Array<{type?, zone?}>>, doors?}, metadata {actionsRemaining?, combatInfo?, winnerId?, passCount?, pendingEffects?, heroStances?: Record<userId, stanceId>}}` (`:91-117`).
- `WirePlayer {userId, heroId, health, maxHealth, fighterIds[], isAlive}` (`:72-79`).
- `WireFighter {id, ownerId(userId), heroId, heroSlug?, name, type:'HERO'|'MINION'|'HUGE', health, maxHealth, position{x,y}, effects[{type, duration?}], movement?, attackType?:'melee'|'ranged', isDefeated?}` (`:41-55`).
- `WireCard {id(инстанс), cardId(дефиниция), name, nameEn?, nameRu?, cardType, attackValue?, defenseValue?, boostValue?, text?, bannerName?, isVisible?}` (`:57-70`).
- `WireCombatInfo {attackerId: fighterId!, defenderId: userId!, targetFighterId?, attackerCardId, defenderCardId?, attackValue, defenseValue}` — **смешение id бойца и id игрока** (`:81-89`).
- `WirePendingEffect {id, type:'MOVE'|'PLACE'|'CHOOSE_ONE', playerId, value?, fighterName?, targetsOpponent?, text?, options?[{index,label}], chooseCount?}` (`:124-136`).
- Приватность (бэк): для чужой руки карта → `{id, cardType, name:'???', nameEn:'Hidden', nameRu:'Скрыто', attackValue/defenseValue/boostValue/effects/text: undefined, isVisible:false}`; чужие `decks` → `topCard: undefined` (`backend/src/games/game-state.service.ts:494-536`). Сокращённые wire-ключи персиста (`f[].sl`=heroSlug, `m.ci.tf`=targetFighterId, `m.pe`=pendingEffects, `m.hs`=heroStances, `m.ar`=actionsRemaining) — внутреннее хранение; наружу отдаются полные имена (`backend/src/games/game-state.service.ts:70-111, 300-483`).

**Парсинг**: `parseWireState(json)` = `JSON.parse` (`:171-173`); `parseSubscriptionState(payload)` парсит 5 строк, `decks/discardPiles` не трогает (`:176-201`).

**Карты фаз/типов** (`:207-226`): `SETUP→setup`, `TURN_START→start_of_turn`, `ACTION_MANEUVER|ACTION_ATTACK→action_selection`, `COMBAT→combat_defense`, `COMBAT_RESOLVE→resolution`, `TURN_END→end_of_turn`, `GAME_OVER→game_over`, неизвестно → `action_selection`. `CARD_TYPE_MAP`: `ATTACK/DEFENSE/SCHEME/VERSATILE` 1:1, `MANEUVER→scheme`, `UNIVERSAL→versatile`, неизвестно → `versatile`.

**`adaptToLocal(wire, refs, localUserId)`** (`:228-360`):
- `heroNameOf(userId)` = имя HERO-бойца владельца; арты берутся из `refs.heroAssets[heroName]` (ключ — **имя героя**, не slug) (`:234-235`).
- Карта: `definition.id = cardId`, `title = hidden ? '???' : nameRu || name`, `value = attackValue ?? defenseValue ?? 0`, `boost = boostValue ?? 0`, `effects` — один псевдо-эффект с `text`, `characterName = bannerName ?? ''`, `imageUrl/imageUrlRu` — по совпадению `art.id === cardId || art.title === (nameEn ?? name)`; скрытая карта = `isVisible === false && name === '???'` (`:237-263`).
- Боец: `definitionId = heroSlug ?? heroId`, `type = HERO ? 'hero' : 'sidekick'` (MINION/HUGE → sidekick), `isDefeated = isDefeated ?? health <= 0`, `avatarUrl` только у HERO (`:265-279`).
- Игрок: `name = usernames[userId] ?? heroName ?? userId.slice(0,8)`, `hand/deck(drawPile)/discardPile`, `actionsRemaining = isCurrent ? metadata.actionsRemaining ?? 0 : 0`, `hasPassed: false` (всегда), `handLimit = handZones.maxSize ?? 7` (`:281-297`).
- **Контракт: локальный игрок всегда `players[0]`** (стабильная сортировка) (`:299-303`).
- Доска: `refs.board` (контентное определение с зонами/`imageUrl`) либо fallback из `boardState.cells` (`zone` одна строка, `isObstacle = type === 'obstacle'`), `recommendedPlayers: 2`, `name: 'Board'` (`:305-320`).
- `combatState` — только если `combatInfo` есть и найдены атакующий и цель (`targetFighterId` → иначе первый боец `defenderId`); `attackCard: null`, бусты 0 (`:325-356`).
- `phase`, `winner = metadata.winnerId ?? null`, `turnCount`, `currentTurn.cardsDrawnThisTurn: 0` (`:334-359`).

Локальный формат (`src/core/models/types.ts`): `GamePhase` (10 значений `setup…game_over`, `:167-178`), `CardType` (4, `:9-14`), `FighterType` (`hero|sidekick`, `:64-67`), `GameState {id, players[], board{definition, fighters: Map}, currentTurn, phase, combatState, winner, turnCount}` (`:182-191`), `Player {id, name, fighters[], hand[], discardPile[], deck[], actionsRemaining, hasPassed, handLimit}` (`:193-203`), `CardInstance {id, definition, ownerId, instanceIndex, boostValue?, isBoosted?, isFaceDown?}` (`:50-58`), `BoardDefinition {id, name, width, height, spaces[{position, zones[], isObstacle?}], recommendedPlayers, imageUrl?}` (`:148-156`).

### 2.6. `remoteGameStore` — единый источник истины игры

| Поведение | Детали | Источник |
|---|---|---|
| Состояние | `currentGameId, wireState, adaptedState, lastSequenceNumber, refs{usernames, heroAssets, board, stanceOptions}, localUserId, connectionStatus('disconnected'|'connecting'|'connected'|'reconnecting'|'error'), syncError, actionError, isSyncing, selectedFighterId, selectedCardId` | `src/store/remoteGameStore.ts:32-37, 80-96, 139-148` |
| `connectToGame(gameId)` — последовательность | (1) `GetGame` network-only → `usernames`, `boardId`; (2) `GetGameState` network-only → `parseWireState`; (3) параллельно для каждого уникального **имени** HERO-бойца — `RemoteHeroAssets(id=name)` (ошибка глотается); `RemoteBoards` → доска по `boardId`, иначе по совпадению `width×height` с wire, иначе `null`; (4) параллельно для каждого `heroSlug` — `HeroStanceOptions`; затем `set refs` → `applyWireState(wire)` → `connected` | `:164-278` |
| `applyWireState(wire)` — guard | `if (wire.sequenceNumber <= lastSequenceNumber && wireState) return;` затем merge `decks = wire.decks ?? prev.decks`, `discardPiles` аналогично; `adaptedState = adaptToLocal(...)`; `lastSequenceNumber = wire.sequenceNumber` | `:295-316` |
| `handleSubscriptionState(payload)` | `applyWireState(parseSubscriptionState(payload))` в try/catch | `:318-324` |
| `refetchState()` | `GetGameState` network-only, **сброс guard** (`lastSequenceNumber = 0, wireState = null`) и применение безусловно | `:326-337` |
| Хелперы | `isMyTurn = currentTurnPlayerId === localUserId`; `actionsRemaining = metadata.actionsRemaining ?? 0`; `amIDefender = combatInfo.defenderId === localUserId`; `myPendingEffects = pendingEffects.filter(p.playerId === localUserId)`; `myStanceOptions` по `heroSlug` моего HERO; `myStance = heroStances[localUserId] ?? option.isDefault ?? options[0] ?? null` (зеркалит backend `defaultStanceId()`) | `:339-376` |
| `runMutation` | `actionError = null`; `mutate`; если `result.state` → `applyWireState(parseWireState(state))`; сброс выделений; при ошибке `actionError = message`; если `/Concurrent modification|sequence/i` → `refetchState()`; rethrow | `:458-490` |
| Мутации | `maneuver(fighterId, path, boostCardId?)`, `moveFighter(fighterId, x, y)`, `attack(attackerId, targetId, cardId, boostCardId?)`, `playDefense(cardId, boostCardId?)`, `playScheme(cardId)`, `resolveCombat()`, `resolvePendingEffect(effectId, fighterId, x, y)`, `resolveChooseOption(effectId, optionIndex)`, `setStance(stanceId)`, `endTurn()`, `pass()`, `leaveGame()` (мутация + `disconnect()` в finally) | `:378-450` |
| Selector-хуки | `useCurrentGameId, useAdaptedGameState, useConnectionStatus, useIsGameSyncing, useGameSyncError, useActionError` | `:492-498` |

### 2.7. Подписка и реконнект

**`useGameSync(gameId, options)`** (`src/hooks/useGameSync.ts`) — production:
- Опции по умолчанию: `autoReconnect: true`, `reconnectDelay: 1000`, `maxReconnectAttempts: 5` (`:57-64`).
- Порядок: `connectToGame(gameId)` → затем `subscribe()`; статус в `connecting` **не** сбрасывается при подписке (иначе вечный спиннер: первое событие придёт только при чьём-то ходе) (`:102-105, 223-260`).
- Переменные подписки: `{gameId, since: lastSequenceNumber || undefined}` — «бэк сравнивает since с sequenceNumber (НЕ timestamp!)» (`:112-117`).
- `next`: `payload = result?.data?.gameStateUpdated ?? result?.gameStateUpdated` (ловушка FetchResult); при первом событии `connected` + сброс счётчика попыток; `handleSubscriptionState(payload)` (`:124-145`).
- `error`: статус `error`; если попыток < 5 → `setTimeout(subscribe, reconnectDelay * reconnectAttempts)` — **линейный** рост (1 с, 2 с, … после инкремента; первая попытка — 0 мс, т. к. счётчик увеличивается внутри таймера) (`:146-173`).
- `complete`: статус `disconnected`, реконнект через фиксированные `reconnectDelay` (1000 мс) (`:174-195`).
- `isMountedRef` защищает от событий после размонтирования; `connectionStatus` намеренно не в deps (иначе цикл `connectToGame` → ре-маунт Phaser) (`:204-218`).
- Возвращает `isConnected (connected|reconnecting), isConnecting, isReconnecting, hasError, error: syncError, connectionStatus` (`:262-269`).
- Ключевые баги, отражённые в коммитах: `09117e2` (realtime молча терял события), `83eb611` (циклы подписки) (`git log`, память проекта).

**`useGameEvents(gameId, eventTypes)`** (`:298-343`) — подписывается на `GameStateUpdated` и фильтрует по несуществующему `event.type` → никогда не срабатывает; никем не используется. DEAD.

**`SubscriptionHandler`** (`src/phaser/network/SubscriptionHandler.ts`, deprecated B5 по `network/index.ts:1-4`): 7 подписок (`gameStateUpdated` + 6 событий, `:131-148, 182-284`), guard `seq <= last → skip`, gap `seq > last+1 → warn` + TODO `eventsSince` (`:331-351`), `maxReconnectAttempts 5`, `reconnectDelay 1000`, задержка `1000 × 2^(n-1)` (**экспоненциальная**: 1 с, 2 с, 4 с, 8 с, 16 с) (`:96-100, 482-508`), `subscribe()` вызывается заново после `unsubscribe()` (счётчик сбрасывается в `unsubscribe` → фактически бесконечные попытки). Транслирует в `scene.events` события `stateUpdate/phaseChanged/turnCountChanged/gameEvent/fighterMoved/attackInitiated/defensePlayed/combatResolved/cardPlayed/turnEnded/gameEnded/doorToggled/turnChanged` (`:410-465`). Ни одна сцена эти события не слушает.

**`useGameState`** (`src/phaser/hooks/useGameSync.ts`, deprecated): `reconnectDelay 3000`, `since: lastSequenceRef.current || undefined` (`:99, 153`), начальная загрузка `GetGameState` network-only (`:301-307`), реконнект после ошибки через 3 с, 6 подписок-событий + `turnChanged` только логируют (`:221-284`).

### 2.8. Оптимистичные обновления — что есть и что реально применяется

- **Production**: оптимистики нет. «Мгновенный отклик» достигается применением `state` из ответа мутации (`remoteGameStore.runMutation`), а эхо подписки с тем же `sequenceNumber` отбрасывается guard-ом (`src/store/remoteGameStore.ts:458-462`).
- `GameView` блокирует параллельные действия локальным флагом `busy` (`src/components/game/GameView.tsx:64, 79-89`); `actionError` автоскрывается через 5 с (`:72-77`).
- Apollo `typePolicies` merge-перезапись `games/game/gameState` (`src/lib/apolloClient.ts:95-118`) — только чтобы кэш не склеивал объекты.
- `useOptimisticUpdate/useOptimisticBatch/useOptimisticDebounce(300 мс)` (`src/hooks/useOptimisticUpdate.ts:87-417`) — `predictState` через локальный `GameEngine`, rollback на ошибке, `AbortController`; помечен `@deprecated B5`, не импортируется (`:1-5`).
- `GameStateBridge` (`src/phaser/state/GameStateBridge.ts`): `enableOptimisticUpdates: true`, `maxPendingActions: 10`, `rollbackOnError: true`, история 50 состояний (`:137-141, 112`); все `computeOptimisticState/applyDiff*/applyStateToScene` — TODO-заглушки (`:444-547`). Deprecated.
- `useGameActions` (`src/phaser/hooks/useGameActions.ts`): `isPending/lastAction` хранятся в объекте из `useMemo` и мутируются — React не перерисуется (`:220-223, 573-574`). Deprecated.

### 2.9. Экраны и их состояния

#### 2.9.1. Auth
- `LoginForm`: состояния `isSubmitting`, `isAuthLoading`, ошибки полей/общая; после логина `navigate(returnUrl || '/')` (`src/components/auth/LoginForm.tsx:22-82`).
- `RegisterForm`: после регистрации `navigate('/')` (`src/components/auth/RegisterForm.tsx:82-105`).
- `AuthGuard`: `isLoading` → спиннер «Загрузка...»; не авторизован → `Navigate('/login?returnUrl=…')` (`AuthGuard.tsx:44-63`). `PublicOnlyGuard`, `withAuthGuard`, `useAuthGuard` — не используются.

#### 2.9.2. Лобби (`LobbyView`, `GameList`, `GameCard`, `CreateGameDialog`)
- Монтирование: `lobbyStore.mount()`, `startPolling(30000)`; размонтирование — `stopPolling()`, `unmount()` (`src/components/lobby/LobbyView.tsx:27-39`). `GameList` **дополнительно** сам вызывает `fetchGames` каждые 30 с (`GameList.tsx:28-32`) — двойной polling.
- Фильтры: `mode` (4 режима), `status` (LOBBY по умолчанию; IN_PROGRESS, FINISHED) — в запрос уходит только `mode` (`lobbyStore.fetchGames` использует `filter.mode`, `:108-111`); `status` не применяется ни на сервере, ни на клиенте.
- `fetchGames`: `fetchPolicy: 'cache-first'` + `AbortController` (отмена предыдущего), обработка abort с сохранением `loading` (`lobbyStore.ts:89-159`).
- Карточка игры: host = `players.find(userId === hostId)`, opponent = первый другой; «Присоединиться» если `status === 'LOBBY' && players.length < 2`; подписи статусов/режимов на русском (`GameCard.tsx:13-41`).
- `CreateGameDialog`: грузит `boards{id name width height recommendedPlayers}` network-only при открытии, режим по умолчанию `ONE_V_ONE`, `createGame({mode, boardId})` → `navigate('/room/'+id)` (`CreateGameDialog.tsx:40-83`, `LobbyView.tsx:50-52`).
- `joinGame(gameId)` → `{gameId, asOpponent: true}` → `navigate('/room/'+id)` (`LobbyView.tsx:55-61`).
- Пустое состояние «Нет доступных игр», ошибка с кнопкой «Повторить» (`GameList.tsx:46-79`).

#### 2.9.3. Матчмейкинг (`MatchmakingView`, `QueueStatus`, `MatchFound`)
- Монтирование: `mount()`, `subscribeToMatchFound('current-user-id')` — **захардкоженный userId** (`MatchmakingView.tsx:26-40`).
- `joinQueue('ONE_V_ONE')`; `leaveQueue()`; `matchFound` → `MatchFound` с `autoAcceptDelay 5000` → `navigate('/room/'+gameId)`; decline → `leaveQueue()` + `clearMatchFound()` (`:42-70, 93-99`). Мутация `acceptMatch/declineMatch` **не вызывается**.
- `QueueStatus`: локальный таймер elapsed 1 с; `fetchQueueStatus` каждые 5 с пока `inQueue`; круговой прогресс `elapsed/estimatedWaitTime`; текст «Поиск соперника...» при `position null|1` (`QueueStatus.tsx:22-66`).
- `MatchFound`: обратный отсчёт от 5 с, `hasAutoAccepted` защита от двойного accept, показывает `opponentUsername`, `opponentRating`, `expiresAt` (`MatchFound.tsx:19-70`).
- Store: `AbortController` на каждую операцию, `_lastOperationId` для отбрасывания stale-ответов, `unmount` чистит подписку (`matchmakingStore.ts:124-196, 445-531`).

#### 2.9.4. Комната (`RoomView` + `PlayerSlots`, `ReadyStatus`, `InviteLink`, `RoomChat`, `GameCountdown`)
- Монтирование: `mount()`, `RoomHeroList` (`heroList(limit:200){items{id name}}` — Prisma cuid, т. к. контентный `heroes` отдаёт `id = имя`), `loadRoom(gameId)` + polling **3000 мс** (`RoomView.tsx:41-68`).
- Автопереход: `game.status === 'IN_PROGRESS'` → `navigate('/game/'+gameId)` (не-хост по поллингу; хост — после `startGame`) (`:70-76, 118-128`).
- Выбор героя: inline `RoomSelectHero` → `loadRoom`; кнопка героя `disabled` если занят другим/идёт выбор/я уже Ready (`:78-99, 207-221`).
- Ready: `setReady(gameId)` (`toggleReady` + `X-Idempotency-Key`) → `loadRoom`; кнопка `disabled = loading || !myHeroId` (`:229-234`, `roomStore.ts:153-217`).
- Старт: только `isHost && allReady` → `GameCountdown(3 с)` → `startGame` → `navigate('/game/…')` (`:112-128, 261-263`).
- `isHost = game.hostId === localStorage.getItem('userId')` — **всегда false в чистом браузере** (см. §2.3), `allReady = players.every(isReady)` (`roomStore.ts:126-128`).
- `PlayerSlots`: 2 слота для `ONE_V_ONE`, иначе 4; показывает аватар/имя/«Герой выбран»/«Готов» (`PlayerSlots.tsx:15-61`).
- `InviteLink`: `${origin}/join/${code}` (маршрута `/join` нет), копирование/Web Share (`InviteLink.tsx:11-37`).
- `RoomChat`: локальный список сообщений без сети (`RoomChat.tsx:31-46`).
- `FighterPlacement` — UI размещения бойцов, **не используется** (расстановка серверная при `startGame`, `RoomView.tsx:190-191`).

#### 2.9.5. Выбор героя `/heroes/:gameId` (`HeroSelection`)
- Грузит `AllHeroes`/`HeroesBySet` (network-only) через `heroSelectionStore`, поиск по имени на клиенте; один `pollGameStatus` (`GetGame`) при монтировании и через 500 мс после выбора; клик → `selectHeroOnServer(gameId, hero.id)` — но `hero.id` здесь **имя** (контентный `heroes`), а `selectHero` ждёт cuid → конфликт, признанный в `RoomView.tsx:37-38`. Маршрут не в production-флоу (никто не навигирует на `/heroes/`). (`HeroSelection.tsx:30-86`, `heroSelectionStore.ts:65-186, 204-281`).

#### 2.9.6. Игра `/game/:gameId` (`GameView`)
Состояния экрана (`src/components/game/GameView.tsx`):
- `isConnecting || !adaptedState` → «Подключение к игре...» (`:214-221`); `hasError` → «Ошибка подключения» + «Перезагрузить страницу»/«Вернуться в лобби» (`:223-239`).
- Статус-бар: `Ход N`, «Ваш ход · действий: k» / «Ходит <имя>», фаза, индикатор `connectionStatus` (`🟢 online` / `🟡 <status>`), кнопки «Пас», «Конец хода» (`disabled = !myTurn || busy || gameOver`), «Покинуть» (`:261-296`).
- Баннер `actionError` (`:298-309`).
- Панель боя при `combatInfo && !gameOver`: `COMBAT` + я защитник → «Вас атакуют! Кликните карту защиты (DEFENSE/VERSATILE) или сразу Resolve.» + кнопка «Без защиты» (= `resolveCombat`); `COMBAT` + не защитник → «Ждём карту защитника…»; `COMBAT_RESOLVE` → «Карты сыграны — резолв боя.»; кнопка «Resolve» видна если `isAttacker || phase === COMBAT_RESOLVE` (`:244-247, 311-340`).
- Баннер отложенного эффекта `activePending` (первый из `myPendingEffects()`): для `CHOOSE_ONE` — кнопки `options[].label` → `resolveChooseOption`, подпись «выберите N» при `chooseCount > 1`; для `MOVE/PLACE` — подсказка «Кликните бойца противника/своего бойца (fighterName)» → после выбора «Боец выбран — кликните клетку (до N шагов | любая свободная)»; «ещё в очереди: k» (`:65-70, 342-390`).
- HUD стоек: если `myStanceOptions().length > 0 && !gameOver` — ряд кнопок, активная помечена `✓`, `disabled = busy || active` → `setStance(opt.id)` (`:254-256, 392-435`). Примечание: комментарий в памяти проекта говорит о «gate isMyTurn», в коде такого гейта **нет**.
- `PhaserGame` 1000×640 с `gameState = adaptedState`, `selectedFighterId = activePending ? pendingFighterId : selectedFighterId`, `selectedCardId = activePending ? null : selectedCardId`, `highlightedSpaces = []` (подсветки ходов нет) (`:437-450`).
- Модалки: «Покинуть игру» (→ `leaveGame()` + `/lobby`), «Игра окончена» при `phase === GAME_OVER`: `winnerId === localUserId ? '🏆 Победа!' : '💀 Поражение'` (`:205-212, 452-485`).

Диспетчер кликов `handlePhaserEvent` (`:106-203`) — правила UI (сервер валидирует всё сам):
1. `activePending.type === 'CHOOSE_ONE'` → клики по доске игнорируются.
2. `activePending` (MOVE/PLACE): `FIGHTER_CLICKED` по подходящему бойцу (`fighterFitsPending`: владелец по `targetsOpponent`, имя содержит `fighterName` с отрезанным числовым суффиксом и `ies→y`) → toggle `pendingFighterId`; `SPACE_CLICKED` при выбранном бойце → `resolvePendingEffect(id, fighterId, x, y)`; остальное игнорируется.
3. `FIGHTER_CLICKED` свой → toggle `selectFighter`; чужой → если выбрана карта `ATTACK|VERSATILE`, есть атакующий (`selectedFighterId` или мой HERO), `isMyTurn && actionsRemaining > 0` → `attack(myAttacker, fighter.id, card.id)`.
4. `SPACE_CLICKED` → нужны `selectedFighterId && isMyTurn && actionsRemaining > 0 && phase ∈ {ACTION_MANEUVER, ACTION_ATTACK}` → `moveFighter(fighterId, x, y)`.
5. `CARD_CLICKED`: `phase === COMBAT && amIDefender` → `DEFENSE|VERSATILE` → `playDefense(card.id)`; иначе требуется `isMyTurn && actionsRemaining > 0`; `SCHEME` → `playScheme`; `ATTACK|VERSATILE` → toggle `selectCard`.

Компоненты `GameHeader`, `TurnIndicator`, `ActionButtons` (hotkey Space + confirm-модалки), `OpponentHandView` (макс. 7 рубашек + «+N»), `DiscardPileView` (модалка-заглушка), `VictoryScreen` (XP: 100 + 5/ход + 2/урон + 25/побеждённый + 3/карта), `ReplayPlayer` (скорости 0.25–3×, hotkeys Space/←/→/Esc, экспорт JSON), `GameErrorBoundary` — реализованы, но в `GameView` подключён только `GameErrorBoundary` (grep импортов, §2.14). (`src/components/game/*.tsx`, `ActionButtons.tsx:40-50`, `OpponentHandView.tsx:20-22`, `VictoryScreen.tsx:259-270`, `ReplayPlayer.tsx:70-96, 345`).

Компоненты боя `src/components/combat/*` (`CombatPanel` с таймером 30 с, `DefenseCardSelector`, `TargetSelector`, `CombatResolution` — шаги 1 с/2 с, `CombatResult`, `AttackerView/DefenderView` с модификаторами `boost|ignoreDefense|doubleDamage|shield`, `DamageIndicator` 1 с) — **не подключены** к `GameView`; их `CombatState` (`attackCard`, `modifiers`, `timeRemaining`, `status`) не соответствует wire `combatInfo` (`CombatPanel.tsx:25-39, 54-68, 78`).

#### 2.9.7. Песочница `/test-game`
`TestGamePage` — локальный `GameEngine` (`src/core/engine`), `testGameStore` собирает mock-состояние из контентных `hero/boards` (колода перемешивается, рука 5, 2 действия, стартовые позиции по краям, mock-доска 6×4 `cobble-city` с `/assets/boards/hells-kitchen.webp`) (`src/store/testGameStore.ts:230-334, 699-729`). Не относится к серверной игре; в UE не переносится.

### 2.10. Phaser: обёртка, сцены, что визуализируется

**`PhaserGame` (React-обёртка)** (`src/phaser/PhaserGame.tsx`):
- Конфиг: `type: AUTO`, `width/height` по умолчанию 800×600 (GameView передаёт 1000×640), `backgroundColor '#1a1a2e'`, `scene: [BootScene, gameScene, UIScene]`, `scale: FIT + CENTER_BOTH`, `antialias`, `dom.createContainer` (`:117-135`).
- Масштабирование контейнера CSS `transform: scale(renderScale)` под ширину родителя/окна (`:150-178, 236-261`).
- Протокол React → Phaser через `game.events.emit('react-to-phaser', event)`: `UPDATE_STATE{state}`, `SELECT_FIGHTER{fighterId|null}`, `SELECT_CARD{cardId|null}`, `HIGHLIGHT_SPACES{spaces[]}`, `MOVE_FIGHTER`, `SHOW_DAMAGE`, `ATTACK`, `DEFEND`, `PLAY_CARD_ANIMATION` (последние три сцена не обрабатывает) (`src/phaser/types.ts:87-96`, `GameScene.ts:852-879`). При `PHASER_READY` обёртка досылает последние state/selection/highlights (`PhaserGame.tsx:75-102`).
- Phaser → React: `FIGHTER_CLICKED{fighterId}`, `SPACE_CLICKED{position}`, `CARD_CLICKED{cardId}`, `PHASER_READY`; `ATTACK_CLICKED`, `ANIMATION_COMPLETE` объявлены, но не эмитятся (`types.ts:79-85`).
- Каждое изменение `gameState` → `UPDATE_STATE` → сцена **полностью пересоздаёт** доску, бойцов, карты, HUD (`GameScene.ts:933-942`).

**`BootScene`** (`src/phaser/scenes/BootScene.ts`): экран «Loading...» с прогресс-баром 360×18, загружает все `GAME_IMAGE_ASSETS` (`load.image(key, path)`), затем `scene.start('GameScene')` (`:9-57`).

**`GameScene`** (`src/phaser/scenes/GameScene.ts`) — константы и геометрия:
- `SPACE_SIZE 72`, `BOARD_TOP 130`, `BOARD_PADDING 16`, `CARD_WIDTH 58`, `CARD_HEIGHT 84` (`:105-109`). Доска центрируется по ширине камеры: `x = round((cameraWidth − width·72)/2)`, `y = 130`; размер по умолчанию 6×4 (`:987-994`). Мир→клетка: `floor((worldX − x)/72)` (`:812-829`).
- Слои-контейнеры с depth: board 0, highlights 1, fighters 2, cards 3, effects 4, hud 10 (`:148-155`). Фон камеры `0x111522`, центр (400,300) (`:143-146`).
- Палитра HUD: `ink 0x040711, surface 0x08101d, line 0xf2b84b, cyan 0x00d4ff, gold 0xffc84a, red 0xff3f4f, purple 0x9c55ff, text '#fff4c7', mutedText '#9fb0ca'` (`:68-80`); «комикс-панель» с срезанными углами `cut 16`, тенью +4/+5, двойной обводкой (`:165-223`).
- `ZONE_COLORS` для 12 зон: blue `0x3286d9`, green `0x48a76a`, yellow `0xd7b84b`, red `0xb23a48`, purple `0x7b5ac8`, brown `0x92400e`, gray `0x6b7280`, orange `0xf97316`, pink `0xec4899`, white `0xe5e7eb`, gold `0xd4af37`, beige `0xd6c8a8` (`:53-66`).
- Доска (`createBoard`, `:287-347`): стол 800×600 `ink`, опциональная текстура `hud-board-vignette` (alpha 0.5), панель-рамка, арт доски (`board-<id>` из манифеста или рантайм-текстура по `board.imageUrl`, alpha 0.72), `hud-board-frame-6x4` (alpha 0.9), клетки, подпись имени доски (default «Cobble City»).
- Клетка (`createSpace`, `:349-389`): прямоугольник 68×68 с белой обводкой (кликабелен → `SPACE_CLICKED`), круг-узел радиусом `72·0.31` цвета первой зоны (alpha 0.22 + обводка 0.82), до 2 «свотчей» зон (кружки r=5) в левом верхнем углу при `showZones`, ромб-препятствие 28×28 при `isObstacle`. Fallback-зоны, если у клетки их нет: по `(x+y) mod 12` (`:1009-1014`).
- Боец (`createFighter`, `:402-442`): размер 62 (hero) / 48 (sidekick); тень-эллипс, кольцо выбора (accent героя, видно только выбранному), круг-основа `0x10131d`, изображение `hero-mini-<id>` (fallback `hero-mini-ms-marvel`), HP-бар над головой (ширина = size, цвет по `getHpColor`: >0.6 зелёный `0x4ecca3`, >0.3 жёлтый `0xd7b84b`, иначе красный `0xff4d5f`, `:1109-1113`); hit-area круг r = size/2+10; клик → `FIGHTER_CLICKED`. Побеждённые бойцы **не рисуются** (`:391-400`). Бойцы никогда не анимируются кроме `moveFighter` tween 280 мс `Sine.easeInOut` (`:944-963`), которую production не вызывает (ре-рендер целиком).
- Рука (`createCards/drawCardArea/createCard`, `:444-566`): панель 720×96 в (40,488); 7 слотов-плейсхолдеров 48×72 с шагом 68 от x=196; рубашки колоды (x=696) и сброса (x=750) с числами `deck.length`/`discardPile.length` **локального игрока (`players[0]`)**; карты `slice(0,7)` центрированы по 400, y=532, шаг 68; арт — из манифеста `card-<hero>-<cardId>` или рантайм-текстура по `definition.imageUrl` (докачка через `load.image` с ре-рендером по `filecomplete`, `:1026-1081`); без арта — обложка `hero-cover-<id>` + значение (18 px) + название (8 px); выбранная карта — scale 1.08, поднята на 10 px, золотая обводка (`:515-525, 972-981`). **Текст карты/тип на карте не отображаются.** Скрытые карты соперника в руке никогда не рендерятся (рука — только `players[0]`).
- HUD (`renderHUD`, `:568-586`): панели двух игроков (локальный y=424, соперник y=12; 292×62/76): обложка, аватар (`hero-avatar-<id>`), мини, имя (`player.name`), HP-бар 150×12, 4 «пипса» действий (ромбы, закрашено `actionsRemaining`), строка `HP h/max   Hand n   Deck n   Actions k` (`:588-663, 1104-1107`); чип хода в (308,20) 184×44: 5 цветных точек по `turnCount mod 5`, «Turn N», фаза с заменой `_` на пробел (`:665-699`); рука соперника — до 7 рубашек 40×58 с наклоном −5°+1.5°·i и подпись «Hand N» (`:701-737`); инспектор выбранной карты 224×322 в (565,132): арт 122×176 или fallback-плашка, строка `title / TYPE value/boost` (`:739-793`); при `gameState === null` — «Waiting for game state» (`:795-810`).
- Подсветки клеток (`highlightSpaces`, `:881-901`): круг cyan alpha 0.16 + обводка 4 px + скруглённый прямоугольник белой обводки; production передаёт пустой массив.
- Урон (`showDamage`, `:908-931`): текст `-N` 30 px красный, всплывает на 52 px за 900 мс `Cubic.easeOut`; вызывается только событием `SHOW_DAMAGE`, которое никто не шлёт.
- `HERO_VISUALS` только для `ms-marvel` (accent `0xd7b84b`) и `daredevil` (`0xb23a48`); `FALLBACK_HERO` использует текстуры Ms. Marvel и accent `0x4ecca3` (`:25-51`). `definitionId = heroSlug`, поэтому у других героев все мини/аватары — Ms. Marvel.
- `ReplaySystem` инициализируется с `autoRecord: true, maxEvents: 1000` и слушает `replay:*` события (`:1115-1126`), но `startRecording/loadReplay` никто не вызывает.

**`UIScene`** (`src/phaser/scenes/UIScene.ts`): `active: false`, слушает `turn-changed/phase-changed/actions-changed` от `GameScene` — сцена их не эмитит; тексты «Ход: …», «Действия: …», «Фаза: …» на русском, `showNotification` (tween 2 с), `showConfirmDialog` — TODO (`:14-158`). Фактически неактивна.

**`MainGameScene`** (`src/phaser/scenes/MainGameScene.ts`) — альтернативная сцена на `BoardRenderer`/`FighterSprite`/`InputHandler`/`CameraController` с `BoardConfig {width, height, cellSize 64, zones[], doors[]}`; экспортируется из `phaser/index.ts:7`, но не включена ни в один `Phaser.Game`. DEAD.

**Рендереры** (не подключены): `BoardRenderer` — сетка, зоны-прямоугольники, двери (контейнеры с ручкой, клик → `door:clicked`), подсветки `VALID_MOVE 0x4ecca3 / ATTACK_TARGET 0xff6b6b / SELECTED 0xffd93d / HOVER 0x6c5ce7` с tween 150 мс `Back.Out` (`src/phaser/renderers/BoardRenderer.ts:19-24, 186-252, 259-361`); `DeckRenderer` — стопка 60×84 с логотипом-«U», счётчики, `animateDraw` 300 мс `Power2.easeIn`, `animateDiscard` 300 мс `Bounce.easeOut` (`DeckRenderer.ts:35-41, 300-355`); `HandRenderer` — до 5 карт 120×170 с перекрытием 80, `CardSprite` с цветами типов `ATTACK 0xff6b6b, DEFENSE 0x4ecdc4, MANEUVER 0x95e1d3, SCHEME 0x9b59b6, UNIVERSAL 0xf39c12, BOOST 0xf1c40f`, hover ×1.1, выбор ×1.15 и подъём 20 px, розыгрыш — scale 1.5 + fade 400 мс + частицы (`HandRenderer.ts:36-43`, `sprites/CardSprite.ts:25-32, 216-345`). `CardSprite` обращается к `card.name/cardType/attackValue` — это wire-поля, а не `CardInstance` (несовместимость типов).

**Анимации** (не подключены): `FighterAnimations` — idle «дыхание» 800 мс yoyo, walk (bob 200 мс, скорость 200 px/с), attack (замах 10 px → выпад 30 px за 150 мс, hold 50 мс, возврат 105 мс), hit (отброс 15 px, 100 мс, возврат 150 мс `Elastic.Out`, tint red, поворот ±5°), block (scale 0.85/1.1, 100 мс, hold 100 мс), special: charge/teleport/heal/buff/default (`src/phaser/animations/FighterAnimations.ts:34-65, 91-522`); `CombatAnimations` — `playAttack` = подготовка (разворот 100 мс) → выполнение по типу `MELEE|HEAVY(250 мс)|CRITICAL(120 мс)|RANGED(снаряд 300 мс)|MAGIC(400 мс + flash)|EXPLOSIVE(волна 400 мс + shake 0.02/300)` → реакция (block: искра+щит-полукруг 300–400 мс; hit: отброс 10/20 px, tint, поворот 8°/15°, частицы, число урона 32/48 px 800 мс, `CRIT!` 1 с) → завершение 100 мс; `playDeath` 1 с (падение, поворот 90°, серый tint, shake 0.015/500); спец-атаки `combo/area/finisher(slow-motion 0.2)/summon` (`CombatAnimations.ts:14-21, 64-757`).

**Эффекты и UI боя** (не подключены): `ParticleSystem` — `emitDamage` (8–30 частиц, 400 мс), `emitHeal` (сердечки 1.2 с), `emitCardDraw`, `emitCardPlay` (золотой burst + кольцо + звёзды), `emitZoneActivation(color)`, `emitBurst`, `emitStatusEffect(poison|burn|shield|stun|buff)` (`src/phaser/effects/ParticleSystem.ts:55-563`); `ScreenEffects` — `shake` (по умолчанию 0.01/200 мс, шаг 16 мс), `flash` (100 мс, alpha 0.5, overlay depth 10000), `fadeOut/fadeIn` 500 мс, `setSlowMotion` (timeScale 0.1–1), `bulletTime(0.2, 500, 1000)`, `impactZoom(1.1)`, `heavyHit/criticalHit/victoryEffect/defeatEffect` (`ScreenEffects.ts:69-627`); `CombatUI` — всплывающие числа (32 px, 800 мс, heal `+`/✚, block 🛡️, crit ×1.3 `!`), `HealthBar` (12 px, цвета ≤0.3 red / ≤0.6 orange), статус-иконки, лог боя 350×250 на 8 записей с цветами по типу, `showTurnIndicator` (2 с), `showActionPrompt` (`src/phaser/ui/CombatUI.ts:78-181, 195-237, 251-349, 359-549, 588-832`).

**Ввод/камера** (не подключены): `InputHandler` — `clickThreshold 5 px`, `doubleClickDelay 300 мс`, hover-рамка `0x6c5ce7`, флаги `fighterSelectionEnabled/cellClickEnabled`, события `input:event` (`src/phaser/input/InputHandler.ts:24-28, 70-87, 113-210`); `CameraController` — WASD-панорама (10/zoom px), Q/E зум шаг 0.1 в [0.5, 2], R сброс, колесо — зум к курсору, средняя кнопка — drag, follow с lerp 0.1 и offset (0,100), `panTo` 500 мс, `playCinematicMove`, `shake/flash` (`src/phaser/camera/CameraController.ts:79-98, 114-189, 266-480`).

**Системы**: `VictoryConditions` — локальная проверка «остался один игрок с живыми бойцами» / «ничья», hero-условия TODO (king-arthur, trex), `victoryDelay 1500` (`src/phaser/systems/VictoryConditions.ts:44-68, 93-98, 212-266`) — дублирует сервер (`metadata.winnerId`), не подключена; `ReplaySystem` — запись событий (`ReplayEventType` 18 значений), снапшоты каждые 5 с, воспроизведение через `scene.time.delayedCall`, скорость 0.25–4×, обратное воспроизведение, `compressEvents` оставляет 8 ключевых типов (`src/phaser/systems/ReplaySystem.ts:26-54, 146, 563-565, 751-772`).

### 2.11. Asset manifest и реальные файлы

`src/phaser/assets/gameAssetManifest.ts`:
- `HERO_ASSET_IDS = ['ms-marvel', 'daredevil']` → ключи `hero-mini-<id>`, `hero-avatar-<id>`, `hero-cover-<id>` из `/assets/heroes/<id>/{mini,avatar,card-cover}.webp` (`:6-12`). Файлы существуют только для этих двух героев (`public/assets/heroes/*`).
- HUD (15 PNG, `/assets/ui/hud/`): `player-panel-local`, `player-panel-opponent`, `turn-phase-pill`, `selected-card-panel`, `mobile-bottom-sheet`, `hand-tray`, `hand-tray-mobile`, `deck-slot`, `discard-slot`, `hidden-card-back`, `board-vignette`, `board-frame-6x4`, `zone-legend-chip`, `status-badges`, `action-buttons` (`:14-30`); все файлы присутствуют (`ls public/assets/ui/hud`). Сцена использует только `hud-board-vignette` и `hud-board-frame-6x4` (`GameScene.ts:300-305, 325-330`).
- Эффекты (6 PNG, `/assets/ui/effects/`): `fx-selection-ring`, `fx-move-highlight`, `fx-attack-highlight`, `fx-defense-shield`, `fx-hit-spark-strip`, `fx-card-play-flash-strip` (`:32-39`); присутствуют, **не используются** сценой.
- Целевые размеры по плану генерации: панели 380×112 / 380×96, pill 220×54, inspector 260×360, bottom-sheet 390×320, hand-tray 760×130 / 390×122, deck/discard 96×132, card-back 120×180, vignette 1024×768, frame 640×430, chip 132×34, status-badges 6×64×64 (health, movement, attack, defense, boost, card-count), action-buttons 5×72×72 (move, attack, defend, boost, end-turn), selection-ring/move/attack 128×128, shield 96×96, hit-spark 8×64×64, card-flash 8×96×96 (`docs/plans/imagegen-hud-asset-plan-2026-06-11.md:191-293`). Фактические размеры файлов не проверялись.
- Доска: `board-cobble-city → /assets/boards/hells-kitchen.webp` (единственная; `getBoardArtAsset` ищет `board-<boardId>`) (`:41-43, 139-142`).
- Карты: статический словарь `'<heroId>:<cardId>'` только для ms-marvel (11) и daredevil (8) (`:45-124`); на диске `public/assets/decks/` — 19 героев (`blackbeard, chupacabra, ciri, daredevil, deadpool, donatello, eredin, krang, leonardo, loki, michelangelo, ms-marvel, muhammad-ali, pandora, philippa, raphael, shredder, yennefer-triss` + `ru/` подпапки) и `card-assets.generated.json` (`{generatedAt, heroes: {<slug>: {id, name, cards[{id, title, imageUrl, imageUrlRu}]}}}`), который сцена **не читает**; арты остальных героев приходят по `imageUrl` из контентного `hero(id=name).cards`.
- `AssetLoader.ts` (`FIGHTER_ASSETS` со spritesheet `/assets/fighters/<id>.png` 64×64, `/assets/portraits/<id>.png`, `BOARD_ASSETS cobalt-city/festering-grounds → /assets/boards/<id>.png`, `createFighterAnimations` idle 0–3/walk 4–7/attack 8–11/hit 12–13/defeat 14–17) — файлов нет, никем не вызывается (`src/phaser/assets/AssetLoader.ts:14-256`; `README.md` описывает эту же несуществующую структуру, `src/phaser/README.md:92-110`).

### 2.12. Локальные/вспомогательные store и компоненты

- `gameStore` — локальный движок (`GameEngine`), `initializeGame` с ms-marvel vs daredevil, `getValidMoves/getValidTargets` (`src/store/gameStore.ts:41-70, 192-202`); используют `BoardView`, `HandView`, `GameControls`, `PhaserBoard`, `useOptimisticUpdate` — всё вне production-пути.
- `uiStore` — модалки/лог/`isProcessing`, нигде не используется в production (`src/store/uiStore.ts`).
- `heroSelectionStore` — см. §2.9.5; `roomStore` — §2.9.4.
- Design-system: `Avatar, Badge, Button, HealthBar, Input, Modal, Toast(useToast/ToastProvider), Token, ZoneIndicator` (`src/design-system/components/`); `ToastProvider` **не смонтирован** (grep в `main.tsx/App.tsx` пусто), план B3 это требовал (`docs/plans/2026-06-12-remaining-features.md:421`).
- `LeaderboardView/ProfileView/FriendsList/GameChat` и их подкомпоненты написаны по спецификациям `docs/frontend-tasks/06-07`, против **несуществующих** операций (§2.4.1) — экраны неработоспособны с текущим бэком.

### 2.13. Известные баги и ловушки клиента (из кода, планов, памяти)

| # | Ловушка | Где | Статус |
|---|---|---|---|
| 1 | `since` в `gameStateUpdated` — это `sequenceNumber`, не timestamp; `Date.now()/1000` отсекал все события | `src/hooks/useGameSync.ts:112-116`, план `2026-06-12-remaining-features.md:29` | починено (B2) |
| 2 | `apolloClient.subscribe` возвращает `FetchResult`: событие в `result.data.gameStateUpdated` | `useGameSync.ts:121-132`, коммит `09117e2` | починено, важно повторить в UE (payload вложен в `data`) |
| 3 | `connectionStatus` в deps `subscribe` → пересоздание подписки → `connectToGame` по кругу → ре-маунт Phaser; сброс статуса в `connecting` при подписке → вечный спиннер | `useGameSync.ts:102-105, 134-137, 204-206`, коммит `83eb611` | починено |
| 4 | `remoteGameStore` старой версии типизировал `gameState` как объект, а приходит `{state: string}` | план `:30` | починено (v2) |
| 5 | GameScene показывала руку игрока, чей ход, а не локального → контракт `players[0]` | план `:31`, `GameScene.ts:1092-1098` | починено |
| 6 | `localStorage.userId` нигде не пишется → `roomStore.isHost=false`, `RoomChat` без имени; работало только с ручной установкой в Playwright | `roomStore.ts:126`, память проекта (`game-tester-and-logic-gaps.md`: «токены… + userId») | **открыто** |
| 7 | `MatchmakingView` подписывается с `userId='current-user-id'` → матч никогда не придёт | `MatchmakingView.tsx:31-33` | **открыто** |
| 8 | `acceptMatch/declineMatch` не вызываются; MatchFound «принимает» матч навигацией в комнату | `MatchmakingView.tsx:58-70` | открыто (семантика подтверждения матча на бэке не используется клиентом) |
| 9 | Лишние аргументы `idempotencyKey` у `joinGame/joinQueue/leaveQueue/leaveAllQueues` — GraphQL-валидация отвергнет запрос («Unknown argument») | `lobbyStore.ts:37-45`, `matchmakingStore.ts:6-29` vs `src/gql/graphql.ts` `Mutation*Args` | **вероятно ломает join/queue**; не проверялось вживую в этом ридинге |
| 10 | `MatchFound` inline-подписка объявляет `$userId: ID!`, схема ждёт `String!` | `matchmakingStore.ts:57` | открыто |
| 11 | Deprecated `GameActions.playDefense` шлёт `combatId`, `toggleDoor` — `doorId`; `Maneuver` требовал `cardId` | `src/phaser/network/GameActions.ts:322-328, 585-589` | мёртвый код |
| 12 | `HERO_VISUALS` захардкожен; остальные герои — арт Ms. Marvel; риск в плане назван «визуальная деградация, не блокер» | `GameScene.ts:25-51`, план `:487` | открыто |
| 13 | CORS резал `X-Idempotency-Key` — починено на бэке | `backend/src/main.ts:92-95, 124-129`, память | починено |
| 14 | `selectHero` ждёт Prisma cuid, контентный `heroes` отдаёт `id = имя` → `RoomView` использует `heroList` | `RoomView.tsx:37-38`, память | учтено в RoomView; `HeroSelection` остался сломанным |
| 15 | Zone enum был из 5 цветов, опечатка `biege` в данных роняла весь `boards` → расширен до 12 + нормализация на бэке | `GameScene.ts:53-66`, коммит `b9a645f`, память | починено |
| 16 | `errorPolicy: 'all'` → ошибки не бросаются, а лежат в `errors` рядом с `data` | `apolloClient.ts:119-130` | особенность, учитывать в клиенте |
| 17 | После refresh токена WS не переподключается (`reconnectWebSocket` не вызывается) → подписка на старом JWT | `apolloClient.ts:151-155` | открыто |
| 18 | `retryIf` сравнивает `operationName === 'Mutation'` → мутации ретраятся при сетевых ошибках (риск двойного действия; бэк защищён optimistic lock по seq) | `retry-link.ts:25-27` | открыто |
| 19 | Двойной polling лобби (LobbyView + GameList по 30 с) | `LobbyView.tsx:32`, `GameList.tsx:28-32` | открыто |
| 20 | `useOptimisticUpdate` рассчитывал `optimisticResponse` с полем `result`, которого нет в схеме | `useOptimisticUpdate.ts:188-194` | мёртвый код |
| 21 | Верстка HUD в Phaser рассчитана на 800×600, GameView запускает 1000×640 → доска центрируется, но абсолютные координаты HUD (панели, рука по x=40..760, y=488) не масштабируются под 1000×640 | `PhaserGame.tsx:50-51`, `GameView.tsx:447-448`, `GameScene.ts:461-478, 588-737` | визуальная особенность |
| 22 | Pre-commit hook сломан; коммиты `--no-verify`; codegen регенерирует `src/gql/graphql.ts` одним файлом — ловушка entanglement | память проекта, план `:479` | процесс |
| 23 | `pendingEffects` протухают при возврате хода владельцу; атака вторым действием может создать pending в той же мутации с `advanceTurn` | память проекта (C2) | семантика бэка, влияет на UI-баннер |

Из `docs/frontend-tasks/08-edge-cases.md` (спецификация, **не реализовано** в коде): rapid queue join/leave (EC-1.1), host migration (EC-3.1), auto-start 30 с (EC-3.3), pending actions recovery после reconnect (EC-4.2), periodic full sync при расхождении seq >10 каждые 10 с (EC-4.3), combat timeout actions (EC-5.1), tab visibility (EC-CROSS-2), token expiry warning за 5 мин (EC-CROSS-1) (`08-edge-cases.md:22-105, 374-417, 505-543, 597-753, 760-819, 1154-1290`). `ARCHITECTURE_REVIEW.md:685-725` предлагал `expectedSequence/rejectedSequences/CombatTimeoutAction` в схеме — на бэке этого нет (`src/gql/graphql.ts`).

### 2.14. Что НЕ переносить (устаревшее/мёртвое/невалидное)

Проверено grep-ом импортов (`grep -rl "import.*\b<Name>\b" src`): следующие модули **никем не импортируются** (кроме своих `index.ts`) или помечены `@deprecated`:

| Модуль | Причина |
|---|---|
| `src/phaser/network/{GameActions,SubscriptionHandler,index}.ts` | `@deprecated B5` (`index.ts:1-4`); DTO-несоответствия (`combatId`, `doorId`) |
| `src/phaser/state/GameStateBridge.ts` | `@deprecated B5`; все методы TODO |
| `src/phaser/components/PhaserGameWithBackend.tsx` | `@deprecated B5` |
| `src/hooks/useOptimisticUpdate.ts` | `@deprecated B5`, «никем не импортируется» |
| `src/phaser/hooks/{useGameActions,useGameSync}.ts` | параллельный черновик; импортируются только `phaser/index.ts` |
| `src/hooks/useGameSync.ts → useGameEvents` | фильтр по несуществующему `event.type` |
| `src/phaser/scenes/{MainGameScene,UIScene}.ts` | MainGameScene не в конфиге; UIScene `active:false`, события никем не эмитятся |
| `src/phaser/renderers/*`, `entities/*`, `sprites/*`, `input/*`, `camera/*`, `effects/*`, `animations/*`, `ui/CombatUI.ts`, `systems/*` | не подключены к `GameScene`; `CardSprite` несовместим с `CardInstance`; `VictoryConditions` дублирует сервер |
| `src/phaser/assets/AssetLoader.ts` | ссылается на несуществующие файлы |
| `src/store/{gameStore,testGameStore,uiStore}.ts`, `src/core/engine/*`, `src/core/data/*`, `src/pages/test-game/*` | локальный движок-песочница; истина у сервера |
| `src/components/{board,cards/HandView,controls}` | завязаны на `gameStore` |
| `src/components/phaser/PhaserBoard.tsx` | завязан на `gameStore` |
| `src/components/combat/*`, `game/{GameHeader,TurnIndicator,ActionButtons,OpponentHandView,DiscardPileView,VictoryScreen,ReplayPlayer,replayUtils}` | не подключены к `GameView`; модели не совпадают с wire |
| `src/components/room/{FighterPlacement,RoomChat}` | расстановка серверная; чат без сети |
| `src/components/heroes/*`, `src/store/heroSelectionStore.ts`, маршрут `/heroes/:gameId` | id-конфликт (имя vs cuid); вне флоу |
| `src/components/{leaderboard,profile,social,chat}/*` | операции отсутствуют в схеме бэка |
| `.graphql`-операции DEAD/INVALID из §2.4 (`MyStats, MySettings, GetCards, MyGames, GetGameSequence, EventsSince, Hero, Board, ContentSummary, Sets, LobbyAvailableGames, PenaltyInfo, ValidSpawnZones, UpdateSettings, AbortGame, ToggleDoor, PlaceFighter, ConfirmPlacement, TurnChanged, AttackInitiated/DefensePlayed/CombatResolved/PlayerJoined/PlayerLeft/GameEnded`) | не используются production-путём; часть может пригодиться позже (например `eventsSince`, `abortGame`), но текущее поведение клиента на них не опирается |
| `AuthErrorLink`, `getAuthHeader` | не используются / `@deprecated` |
| Спецификации `docs/frontend-tasks/01-07` в части GraphQL | описывают API, которого нет (`gameUpdates`, `setReady(ready)`, `placeFighter`, `chatUpdates`, `leaderboard(options)`); реальную схему брать из `src/gql/graphql.ts` |

---

## 3. Следствия для UE-клиента

1. **Модель синхронизации — снапшоты, не дельты.** Реализовать один `ApplyWireState(json)` с guard-ом `seq <= last → drop` и merge `decks/discardPiles` из предыдущего снапшота; вызывать его из трёх источников (query, ответ мутации, подписка). Никакого локального предсказания правил; UI лишь гейтит кнопки по `isMyTurn/actionsRemaining/phase/amIDefender` (§2.6, §2.9.6).
2. **Три шага загрузки игры**: `GetGame` (usernames, boardId) → `GetGameState` → параллельно контент (`hero(id=имя)` для артов, `boards` для зон/арта доски, `heroStances(heroSlug)`), только потом рендер. Контент кэшировать по имени героя и id доски; отсутствие контента не должно блокировать игру (§2.6).
3. **Парсеры**: `state` — одна JSON-строка; подписка — 5 строк JSON; писать типобезопасный парсер `WireGameState` (поля из §2.5), допуская отсутствие `decks/discardPiles`, `heroSlug`, `targetFighterId`, `pendingEffects`, `heroStances`. `combatInfo.attackerId` — id **бойца**, `defenderId` — id **игрока**, цель — `targetFighterId` с fallback на первого бойца владельца.
4. **Транспорт**: HTTP POST `/graphql` с `Authorization: Bearer`; WS `graphql-ws` (protocol `graphql-transport-ws`) с `connectionParams: {authorization: 'Bearer …'}`; переменные подписки `{gameId, since: lastSeq}`; payload события — `data.gameStateUpdated`. Реконнект: разумно взять экспоненциальный backoff 1 с × 2^n до 5 попыток (как в `SubscriptionHandler`), а не линейный из `useGameSync`; после refresh токена **обязательно** пересоздавать WS-соединение (веб этого не делает — §2.13 п.17).
5. **Auth**: хранить `accessToken/refreshToken/expiresAt`; refresh single-flight по кодам `UNAUTHENTICATED|AUTH_TOKEN_EXPIRED|AUTH_INVALID_TOKEN` или HTTP 401; access TTL 1 ч, refresh 24 ч; после провала refresh — logout и экран логина. Не повторять `errorPolicy:'all'`-ловушку: обрабатывать `errors[]` при HTTP 200.
6. **Идентификатор пользователя** — брать из `me.id` (или из ответа `login/register`), хранить в сессии; не полагаться на внешние хранилища (веб-баг с `localStorage.userId`).
7. **Retry**: ретраить только запросы/подписки при сетевых ошибках (300 мс → 10 с, jitter, 3 попытки); gameplay-мутации не ретраить автоматически (бэк защищён optimistic lock, но повтор даст «Concurrent modification» и лишний refetch). При ошибке с текстом `Concurrent modification|sequence` — `refetchState` с безусловным применением.
8. **Экраны и минимальные состояния**: Login/Register; Lobby (список `availableGames(mode)` с polling 30 с, фильтр режима, создание с выбором доски из `boards`, join `asOpponent:true`); Room (polling `game(id)` 3 с, выбор героя из `heroList` cuid, ready-гейт по `heroId`, старт только хостом при `allReady`, автопереход при `IN_PROGRESS`); Game (статус-бар, панель боя, баннер pendingEffects MOVE/PLACE/CHOOSE_ONE, HUD стоек, модалки выхода/конца игры). Матчмейкинг переносить только после исправления userId/аргументов (§2.13 п.7, 9, 10) и с учётом `acceptMatch/declineMatch`.
9. **Правила кликов** (§2.9.6) — воспроизвести как конечный автомат ввода с приоритетом: CHOOSE_ONE блокирует доску → MOVE/PLACE-режим → обычные действия (свой боец → выбор; чужой боец + ATTACK/VERSATILE → `attack`; клетка → `moveFighter` в `ACTION_*`; карта: COMBAT+защитник → `playDefense`, SCHEME → `playScheme`, ATTACK/VERSATILE → выбор). `maneuver` (с `boostCardId`/`moves[]`) и `ToggleDoor` в UI веб-клиента не задействованы — решать отдельно.
10. **Визуализация** (что реально ожидает пользователь веб-версии): доска W×H клеток с 1–2 цветовыми зонами на клетку (12 цветов, палитра §2.10), препятствия, арт доски по `board.imageUrl`; фишки бойцов (герой крупнее сайдкика) с HP-баром, кольцом выбора, побеждённые скрываются; рука локального игрока до 7 карт с артами `imageUrl/imageUrlRu` (RU-арт предпочтителен: `title = nameRu || name`) и fallback «обложка + значение»; счётчики deck/discard/hand/actions; панели двух игроков; счётчик хода/фазы; рубашки руки соперника (количество известно, содержимое — `???`). Анимации минимальны (движение 280 мс, урон 900 мс) — UE может использовать библиотеку таймингов из §2.10 как референс, но это не обязательства.
11. **Ассеты**: HUD/эффекты PNG (§2.11) можно импортировать как текстуры UMG; карты — по URL с сервера (`imageUrl` относительный `/assets/decks/...` к origin фронта 5174 либо абсолютный Supabase-URL — проверить на живом бэке); мини/аватары героев — `hero.urls{avatar,mini,cardCover}`/`avatarUrl` из контента, а не захардкоженный список.
12. **Не переносить** локальный движок, deprecated-мосты, неподключённые Phaser-подсистемы, неработоспособные экраны (§2.14). Для реплеев/чата/друзей/лидерборда серверного API нет.
13. **Idempotency**: на бэке аргумент `idempotencyKey` есть только у `createGame`; заголовок `X-Idempotency-Key` пропускается CORS, но обработка в резолверах не найдена (grep по `idempotency` — `game.resolver.ts`, `game.service.ts`, `main.ts`; детали не читались). UE-клиенту — генерировать ключ для `createGame`, для остального не полагаться.

---

## 4. Открытые вопросы / несоответствия

1. **`FRONTEND_ARCHITECTURE.md` расходится с кодом**: описывает `remoteGameStore` с `serverGameState/handleGameEvent/checkSequenceGaps` и gap-detection через «запрос пропущенных событий» (`docs/FRONTEND_ARCHITECTURE.md:161-181`), а также `useOptimisticUpdate` как рабочий поток (`:316-355`) и `useAuth.ts` (`:81`) — в коде v2-стора нет gap-detection, оптимистика deprecated, `useAuth.ts` отсутствует. `README.md` frontend-tasks утверждает «Фаза 4 — 30 %, Combat UI — 0 %» (`docs/frontend-tasks/README.md:136-171`), тогда как компоненты созданы, но не подключены.
2. **`retryIf` мутаций** — намерение «не ретраить мутации» не работает (`retry-link.ts:25-27`). Нужно решение для UE: ретраить ли gameplay-мутации.
3. **Аргументы `idempotencyKey` у `joinGame/joinQueue/leaveQueue/leaveAllQueues`** отсутствуют в `Mutation*Args` сгенерированной схемы — либо схема бэка изменилась после написания сторов, либо запросы падают. Требует живой проверки (не входило в задачу ридера).
4. **`Maneuver` в UI не используется** — движение идёт через `moveFighter` (без добора карты и boost). Правила Unmatched требуют манёвр (добор + движение всех бойцов) — UE-клиенту нужно решить, какую мутацию использовать (см. `ManeuverDto.moves[]`).
5. **HUD стоек**: память проекта говорит про gate `isMyTurn`, код `GameView.tsx:392-435` гейта не содержит. Уточнить, разрешает ли бэк `setStance` вне своего хода (мутация «не тратит действие», `mutations/game.graphql:189`).
6. **Приватность `decks`**: бэк скрывает только `topCard` чужой колоды (`game-state.service.ts:530-533`); адаптер читает `decks[userId].drawPile` для счётчика — что именно приходит для чужого `drawPile` (массив карт или пусто), не проверено.
7. **Размеры сцены**: HUD рассчитан на 800×600, production запускает 1000×640 — макет для UE нужно переработать под адаптивный layout (план imagegen описывает desktop 800×600 и mobile 390×844, `imagegen-hud-asset-plan-2026-06-11.md:151-185`).
8. **`GameEvent`-подписки** (`attackInitiated` и др.) на клиенте не используются; для UE они могут дать точные триггеры анимаций (атака/защита/резолв), но их `payload` — только `{phase, turnCount, currentTurnPlayerId}` (`game-subscription.resolver.ts:81-98`); урон/цель придётся вычислять по диффу снапшотов.
9. **`presenceUpdated`/`heartbeat`** есть в схеме, клиент не использует; нужна ли UE-клиенту presence-логика — не определено.
10. **Формат `imageUrl`** (относительный к фронту или абсолютный) — в коде обе ветки (`GameScene.ts:1030-1035` грузит как есть; `card-assets.generated.json` хранит относительные `/assets/decks/...`); проверить на живом контенте.
11. **`docs/backend-api/*` (untracked, 13 файлов, включая `06-unreal-integration-guide.md`)** существуют в рабочем дереве, но не входили в источники этого ридера; их следует сверить с данным каталогом (особенно `07-graphql-schema-reference.md`).
12. **Незакоммиченные изменения** в `src/components/lobby/*`, `matchmaking/*`, `src/store/*`, `src/phaser/*` (git status в начале сессии) — каталог описывает рабочее дерево, а не последний коммит.

---

## 5. Источники

Код клиента: `src/lib/{apolloClient,auth-link,error-link,retry-link,token-storage,gameStateAdapter}.ts`, `src/env.ts`, `.env`, `codegen.ts`, `vite.config.ts`, `package.json`; `src/store/{authStore,remoteGameStore,lobbyStore,matchmakingStore,roomStore,heroSelectionStore,gameStore,testGameStore,uiStore}.ts`; `src/hooks/{useGameSync,useOptimisticUpdate}.ts`; `src/phaser/{PhaserGame.tsx,index.ts,types.ts,README.md,COMBAT_EFFECTS_GUIDE.md}`, `src/phaser/network/*`, `src/phaser/state/*`, `src/phaser/hooks/*`, `src/phaser/scenes/*`, `src/phaser/renderers/*`, `src/phaser/ui/*`, `src/phaser/animations/*`, `src/phaser/assets/*`, `src/phaser/effects/*`, `src/phaser/entities/*`, `src/phaser/sprites/*`, `src/phaser/input/InputHandler.ts`, `src/phaser/camera/CameraController.ts`, `src/phaser/systems/*`, `src/phaser/components/PhaserGameWithBackend.tsx`; `src/graphql/**/*.graphql`, `src/graphql/README.md`; `src/gql/graphql.ts` (сгенерированная схема — DTO/enum/root types); `src/routes/*`, `src/main.tsx`, `src/App.tsx`; `src/components/{auth,lobby,matchmaking,room,game,combat,board,cards,controls,heroes,phaser}/*`, выборочно `src/components/{leaderboard,profile,social,chat}/*` (grep операций); `src/pages/test-game/*`; `src/core/models/types.ts`; `src/types/hero.ts`; `src/design-system/components/*` (список); `public/assets/**` (список файлов, `card-assets.generated.json`).

Документация: `docs/FRONTEND_ARCHITECTURE.md`; `docs/frontend-tasks/{README,01-lobby-matchmaking,02-hero-selection,03-room-setup,04-game-view,05-combat-ui,06-social,07-profile-leaderboard,08-edge-cases,ARCHITECTURE_REVIEW}.md`; `docs/plans/{2026-06-12-remaining-features,imagegen-hud-asset-plan-2026-06-11,engine-gaps-batch-2026-06-14,hero-abilities-framework-2026-06-14,vs-ai-bot-2026-06-13,2026-06-10-admin-panel-fix}.md`; `docs/unreal/00-mcp-verification.md`.

Сверки с бэкендом: `backend/src/graphql/graphql.module.ts:12-50`; `backend/src/games/resolvers/game-subscription.resolver.ts:20-64, 81-98, 150-230`; `backend/src/games/game-state.service.ts:70-134, 300-370, 413-483, 494-536`; `backend/src/games/game.resolver.ts:60-88`; `backend/src/auth/auth.service.ts:472, 483`; `backend/src/config/configuration.ts:27`; `backend/src/main.ts:92-95, 124-129`.

Прочее: `git log --oneline` по `src/phaser src/hooks src/lib src/store src/components/game` (коммиты `3feaa9b, cc77a68, b9a645f, aa97c28, 09117e2, 83eb611, e49fac2, 0641577`); память проекта `game-tester-and-logic-gaps.md` (история B2–B5, realtime-фикс, stance HUD).
