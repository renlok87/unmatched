# Приложение: карта UX веб-клиента (референс для UE)

Статус: исследование 2026-09-18 по коду фронтенда. Пометки «рабочий»/«WIP» — по коду, без запуска. Веб-клиент остаётся рабочим параллельно с UE (кросс-плей возможен, в MVP не входит).

## Страницы и маршруты (src/routes/index.tsx)

| Маршрут | Экран | Файл | Статус |
|---|---|---|---|
| /auth/login | Логин (email+пароль, валидация, ошибки полей) | src/components/auth/LoginForm.tsx | рабочий; register закомментирован в auth.routes.tsx |
| /lobby (+/create) | Список игр | src/components/lobby/LobbyView.tsx | рабочий |
| /lobby/matchmaking | Поиск игры | src/components/matchmaking/MatchmakingView.tsx | рабочий, но подписка matchFound на захардкоженном 'current-user-id' (TODO) |
| /room/:gameId | Комната (AuthGuard) | src/components/room/RoomView.tsx | рабочий |
| /heroes/:gameId | Выбор героя (запасной роут; реальный выбор встроен в RoomView) | src/components/heroes/HeroSelection.tsx | частично |
| /game/:gameId | Игровой стол на реальном API | src/components/game/GameView.tsx | рабочий |
| /test-game | Локальная демо-песочница Phaser (свой GameEngine) | src/pages/test-game/TestGamePage.tsx | рабочая песочница |
| /cards/show/:cardId, /leaderboard, /profile, /social/friends | Инспектор карты, рейтинг, профиль, друзья | src/components/... | рабочий код; в UE MVP не входят |

## Лобби и матчмейкинг

- Lobby: хедер «Создать игру»/«Найти игру»; фильтры по режиму (1v1/2v2/FFA/VsAI) и статусу (LOBBY/IN_PROGRESS/FINISHED); список — polling 30 c (двойной интервал — недочёт); состояния загрузки/ошибки с «Повторить»/пустой список; GameCard: статус-бейдж, хост/оппонент, кнопка «Присоединиться» (только LOBBY <2 игроков). CreateGameDialog: режим + доска.
- Matchmaking: «Встать в очередь» (ONE_V_ONE), прогресс-ринг (elapsed/estimated), позиция, кол-во игроков; polling 5 c; MatchFound-оверлей: VS-карточки, Принять/Отклонить, автопринятие через 5 c.

## Игровой стол (реальная игра — GameView.tsx, главный референс HUD)

Сервер — истина (remoteGameStore + подписка gameStateUpdated). Сверху вниз:
- Статус-бар: номер хода, «Ваш ход · действий: N»/«Ходит X», фаза, индикатор связи (🟢/🟡), кнопки Пас / Конец хода / Покинуть (модалка подтверждения).
- Баннер ошибки действия (автоскрытие 5 c).
- Панель боя: «Вас атакуют! Кликните карту защиты или Resolve» / «Ждём карту защитника…», кнопки Resolve и «Без защиты».
- Баннер отложенного эффекта: CHOOSE_ONE — кнопки вариантов; MOVE/PLACE — «кликните бойца, затем клетку».
- Stances: панель «🥋 Стойка» — кнопки опций, активная с «✓», клик → setStance (рендерится только для стоечных героев).
- Доска: PhaserGame 1000×640 с adaptedState (players[0] = локальный игрок).
- Клики: свой боец → выбор; клетка при выбранном бойце → moveFighter; ATTACK/VERSATILE карта → выбор → клик по врагу → attack; SCHEME → сразу playScheme; в COMBAT у защитника DEFENSE/VERSATILE → playDefense.
- Модалка «Игра окончена»: Победа/Поражение → «В лобби».
- НЮАНС: подсветка доступных клеток (highlightSpaces) в реальной игре всегда [] — не реализована (в test-game реализована). UE обязан сделать.

## Комната (RoomView)

Слоты игроков, выбор героя кнопками (занятые — disabled), ReadyStatus (toggle ready), InviteLink (код комнаты), RoomChat, GameCountdown (3 с перед стартом → startGame). FighterPlacement.tsx существует, но нигде не импортируется (расстановка теперь серверная при старте) — осиротел.

## Phaser-сцены

- BootScene — загрузка с прогресс-баром, манифест gameAssetManifest → GameScene. Рабочая.
- GameScene (1188 стр., основная): доска 6×4 (клетки-«ноды», зоны цветами, препятствия), бойцы (мини + кольцо выбора + HP-бар + тень), подсветка доступных клеток (круг + рамка), рука (мини-карты, выбор 1.08x), HUD «комикс»-стиль: панели обоих игроков (HP-бар, action-пипсы, стат-строка), чип хода/фазы, рука оппонента рубашками, инспектор карты, слоты колоды/сброса; showDamage (всплывающий «-N»), твин перемещения 280 мс, runtime-загрузка артов по URL; ReplaySystem API. Рабочая.
- UIScene — оверлей-тексты; подписана на события, которые GameScene не эмитит → мёртвый код.
- MainGameScene — альтернативная композиция (renderers/entities/input/camera/sprites/...), не подключена → WIP/осиротелая. PhaserGameWithBackend + src/phaser/hooks/* — слой интеграции с бэкендом, не подключён к реальным экранам (реальный путь: src/hooks/useGameSync.ts + remoteGameStore).

## Сторы

- authStore — user, tokens, login/logout/refresh; рабочий.
- lobbyStore — games, фильтры, polling, createGame/joinGame; рабочий.
- matchmakingStore — очередь, статус, matchFound, штрафы; рабочий (кроме TODO userId).
- remoteGameStore — главный для реальной игры: wireState (guard по sequenceNumber), adaptedState, connectionStatus (disconnected/connecting/connected/reconnecting/error), syncError/actionError; хелперы isMyTurn/actionsRemaining/amIDefender/myPendingEffects/myStance/myStanceOptions; все игровые мутации. Рабочий.
- testGameStore — локальная песочница (allHeroes/heroDetails/allBoards через GraphQL, свой GameEngine, highlightedSpaces вычисляются локально). Рабочая.

## Ошибки и переподключение

- error-link.ts: 401/UNAUTHENTICATED → refresh и повтор; нет refresh → logout. retry-link.ts: backoff 300мс→10с, 3 попытки, мутации не ретраятся.
- useGameSync: подписка с since=sequenceNumber, авто-reconnect 5 попыток с задержкой 1 c, статусы.
- GameErrorBoundary: краш-экран «Попробовать снова/Перезагрузить/В лобби».
- В GameView: экраны «Подключение к игре…» и «Ошибка подключения», индикатор онлайна, actionError с refetch при конфликте seq.

## GraphQL-операции (имена, для сверки покрытия)

Queries: Me, MyStats, MySettings, LobbyAvailableGames, QueueStatus, PenaltyInfo, RoomInfo, ValidSpawnZones, GetGame, MyGames, AvailableGames, GetGameState, GetGameSequence, EventsSince, Heroes, Hero, Boards, Board, ContentSummary, Sets, AllHeroes, HeroDetails, HeroesBySet, HeroStanceOptions, GetCards, GetCard.
Mutations: Register, Login, RefreshTokens, Logout, UpdateProfile, UpdateSettings; CreateGame, JoinGame, LeaveGame, StartGame, AbortGame, ToggleReady, SelectHero; Maneuver, MoveFighter, Attack, PlayDefense, ResolveCombat, EndTurn, Pass, ToggleDoor, PlayScheme, ResolvePendingEffect, SetStance; (room.graphql: дубли + PlaceFighter/ConfirmPlacement — WIP).
Subscriptions: GameStateUpdated, AttackInitiated, DefensePlayed, CombatResolved, TurnChanged, PlayerJoined, PlayerLeft, GameEnded, MatchFound.
