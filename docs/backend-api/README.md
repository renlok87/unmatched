# Документация бэкенда и API (для миграции на Unreal Engine)

Полное описание работы NestJS-бэкенда и его GraphQL API, подготовленное для перевода клиента с веб-версии (React + Phaser) на Unreal Engine. Каждый контракт и каждая механика разобраны по коду.

## Обзорные документы

| Документ | Содержание |
|---|---|
| [01-architecture.md](01-architecture.md) | Архитектура бэкенда: модули NestJS, транспорт (HTTP /graphql + WS graphql-ws), Redis/PostgreSQL/BullMQ, ENV-конфигурация, модели Prisma, локальный запуск |
| [02-auth.md](02-auth.md) | Аутентификация и пользователи: JWT access/refresh (ротация, blacklist), все auth/user queries и mutations, подключение из нативного клиента |
| [03-lobby-matchmaking.md](03-lobby-matchmaking.md) | Лобби, комнаты и матчмейкинг: жизненный цикл комнаты, API, очередь матчмейкинга, presence |
| [04-game-api.md](04-game-api.md) | Игровое API: все игровые мутации, структура GameState, протокол синхронизации (sequenceNumber, eventsSince), валидация ходов |
| [05-engine-and-content.md](05-engine-and-content.md) | Игровой движок: конвейер боя, эффекты, ауры, стойки, хуки способностей; контентная подсистема и статические ассеты |
| [06-unreal-integration-guide.md](06-unreal-integration-guide.md) | Практическое руководство для UE: endpoints, формат HTTP POST и WS-сообщений, refresh-цикл, жизненный цикл сессии, маппинг GameState на UE-структуры |

## Исчерпывающие справочники (каждый контракт / каждая механика)

| Документ | Содержание |
|---|---|
| [07-graphql-schema-reference.md](07-graphql-schema-reference.md) | ПОЛНЫЙ контракт GraphQL: все 53 queries, 49 mutations, 10 subscriptions, 73 object-типа, 35 input-типов, 13 enum — каждое поле, аргумент, ограничение валидации, авторизация, ошибки |
| [08-heroes-abilities.md](08-heroes-abilities.md) | ВСЕ 29 героев реестра: система хуков (onTurnStart/onAfterCombat/onFighterDefeated/onFighterMoved/canAttackAtRange…), точная реализация каждой способности (триггер/условие/эффект/цифры), стойки, чеклист герои × хуки |
| [09-cards-and-effects.md](09-cards-and-effects.md) | ВСЕ 880 карт 70 героев: модель карты, 21 EffectType с точной семантикой, 8 таймингов, 10 целей, CountSpec, все правила BOOST (включая Blind Boost), полный реестр карт по героям |
| [10-mechanics-deep-dive.md](10-mechanics-deep-dive.md) | Каждая механика движка с числами: фазы хода и трата действий, геометрия melee/ranged, пошаговый пайплайн боя (ничья = победа защитника), мультизоны и двери, стойки, ауры, PendingEffect, колоды, VS_AI-бот |
| [11-server-internals.md](11-server-internals.md) | Серверные внутренности: персистентность GameState (компактные ключи), распределённые локи, каналы PubSub, все 7 очередей BullMQ и таймеры, матчмейкинг внутри (ZSet, ELO-окна, штрафы), реконнект-протокол, rate limits, аудит |
| [12-admin-api.md](12-admin-api.md) | Все 31 админская операция (18 queries + 13 mutations): сигнатуры, роли (ADMIN/MODERATOR), CRUD контента, кэширование ContentDbService, страницы админки |

## Быстрый старт для UE-разработчика

1. Бэкенд поднимается на `http://localhost:3000/graphql` (HTTP) и `ws://localhost:3000/graphql` (subscriptions, субпротокол `graphql-transport-ws`).
2. Аутентификация — JWT Bearer: заголовок `Authorization` для HTTP, `connectionParams.authorization` в `connection_init` для WS.
3. Источник истины по типам — документ 07 (схема собрана из декораторов, сгенерированного schema.gql в репо нет).
4. Порядок чтения: 01 → 02 → 06 → 07 (контракты) → 04 → 10 (игровой протокол и механики) → 08/09 (контент) → 03 → 11 (лобби и внутренности).
