# R1 — Транспорт, аутентификация, интеграционный гайд

> Research-файл для проектирования нативного UE 5.8-клиента к GraphQL-бэкенду Unmatched.
> Дата: 2026-09-02. Основа — три документа `docs/backend-api/01-architecture.md`, `02-auth.md`, `06-unreal-integration-guide.md`, сверенные с кодом бэкенда (`backend/src`), веб-клиента (`src/`), сгенерированными типами схемы (`src/gql/graphql.ts`) и установленными библиотеками (`backend/node_modules`).
> Живой бэкенд в момент исследования не запускался (Docker Desktop недоступен, `http://localhost:3000/health` не отвечает), поэтому факты делятся на: «(док)» — из документации, «(по коду)» — выведено из исходников, «(живая проверка не проводилась)» — вывод по коду, который стоит подтвердить на работающем сервере.
> Сокращения ссылок: `01:L23` = `docs/backend-api/01-architecture.md`, строка 23; `02:` = `02-auth.md`; `06:` = `06-unreal-integration-guide.md`; `07:` = `07-graphql-schema-reference.md`. Пути к коду даны относительно корня репозитория.

---

## 1. Краткое резюме

1. **Один endpoint `/graphql` на порту 3000** для всего: HTTP `POST` — queries/mutations, WebSocket-upgrade того же пути — subscriptions (01:L21-29, 06:L36-41, `backend/src/main.ts:L134`).
2. **WS-протокол — `graphql-ws`** (npm-пакет `graphql-ws@6.0.6`), значение заголовка `Sec-WebSocket-Protocol` — строго **`graphql-transport-ws`**. Строка `graphql-ws` в этом заголовке — это имя *legacy*-протокола `subscriptions-transport-ws`, который на сервере **не включён**; такое соединение будет закрыто с кодом 4406 (`backend/node_modules/graphql-ws/dist/common-CGW11Fyb.js:L28-29`, `.../server-3ewaJSjp.js:L33-37`, `backend/node_modules/@nestjs/graphql/dist/services/gql-subscription.service.js:L28-38`).
3. **Аутентификация — JWT HS256, пара access (1 ч) + refresh (24 ч) с ротацией refresh-токена**; токен передаётся в `Authorization: Bearer <accessToken>` (HTTP) и в `payload.authorization` сообщения `connection_init` (WS) (02:L16-32, `backend/src/auth/auth.service.ts:L466-490`, `backend/src/graphql/graphql.module.ts:L22-35`).
4. **Ошибки приходят в теле ответа с HTTP 200** (исполнение резолверов) или **400** (парсинг/валидация/приведение переменных/complexity/depth). HTTP 401/409, упоминаемые в доках, в коде не найдены (по коду: `backend/node_modules/@apollo/server/dist/esm/requestPipeline.js:L193-198`, `backend/node_modules/@nestjs/apollo/dist/drivers/apollo-base.driver.js:L161-193`).
5. **Реальные коды ошибок отличаются от документации**: Nest-исключения маппятся так — 400 → `BAD_REQUEST`, 401 → `UNAUTHENTICATED`, 403 → `FORBIDDEN`, 422 → `BAD_USER_INPUT`, всё прочее (409 Conflict, 404 NotFound) → `INTERNAL_SERVER_ERROR` + `extensions.status = <HTTP-код>` + `extensions.originalError.statusCode`. Кода `CONFLICT` не существует (`apollo-base.driver.js:L17-22, L170-190`).
6. **В production (`NODE_ENV=production`) `formatError` маскирует все ошибки, кроме `BAD_USER_INPUT`/`GRAPHQL_VALIDATION_FAILED` и сообщений с подстрокой `not found`/`unauthorized`, в `{ message: "Internal server error", code: "INTERNAL_SERVER_ERROR" }` без `extensions`**. `UNAUTHENTICATED` с русским сообщением «Неавторизованный доступ» под это исключение не попадает — в production клиент по коду ошибки истёкший токен отличить не сможет (`backend/src/graphql/graphql.module.ts:L60-103`). Текущий docker-compose запускает бэкенд с `NODE_ENV=development` (`docker-compose.yml:L44`).
7. **Rate limits и `@Public()` в коде фактически не активны**: `ThrottlerModule` зарегистрирован (`10/60 с`), но `ThrottlerGuard` нигде не привязан (ни `APP_GUARD`, ни `@UseGuards`), а `GqlAuthGuard` навешивается точечно через `@UseGuards` — глобального guard'а нет (`backend/src/app.module.ts:L54-59`, grep `APP_GUARD|ThrottlerGuard` по `backend/src` — пусто; `backend/src/auth/auth.module.ts:L28-29`). Следствие: `logout`, `heartbeat`, matchmaking-мутации не защищены `GqlAuthGuard` (см. §2.15).
8. **Идемпотентность**: единственный серверный механизм — nullable-аргумент `idempotencyKey` у `createGame`. Заголовок `X-Idempotency-Key` сервер только пропускает через CORS, но нигде не читает. Аргумента `idempotencyKey` у `joinGame`, `joinQueue`, `leaveQueue`, `leaveAllQueues` в схеме нет — веб-клиент и 06-гайд его отправляют ошибочно (`backend/src/games/game.resolver.ts:L115-123`, `src/gql/graphql.ts:L867-884`, `06:L220-227`).
9. **Keep-alive WS**: сервер каждые 12 с шлёт WebSocket **ping-фрейм** (не JSON-сообщение) и разрывает сокет, если pong-фрейм не пришёл за 12 с; JSON-сообщения `{"type":"ka"}` из 06-гайда в протоколе `graphql-ws` не существует, есть `ping`/`pong` (`backend/node_modules/graphql-ws/dist/use/ws.js:L5, L44-58`). На `connection_init` даётся **3 с** (код 4408).
10. **Токен по WS проверяется при каждом `subscribe`**, а не при handshake: контекст-фабрика лишь копирует `connectionParams.authorization` в `req.headers.authorization`, `onConnect` не задан, поэтому 4403 на handshake наш сервер не выдаёт; невалидный токен проявится ошибкой на конкретную подписку (`graphql.module.ts:L22-35`, `server-3ewaJSjp.js:L66-68, L207`).
11. **`schema.gql` на диске отсутствует**: `autoSchemaFile: true` генерирует схему в памяти. Актуальный SDL — через introspection работающего сервера (так делает `codegen.ts`) либо `docs/backend-api/07-graphql-schema-reference.md` (`graphql.module.ts:L14`, `codegen.ts:L4-14`).
12. **`.env.example` содержит переменные, которые код не читает** (`JWT_ACCESS_EXPIRATION`, `JWT_REFRESH_EXPIRATION`, `THROTTLE_*`, `DEFAULT_BOARD_ID` и др.); TTL токенов задаются `JWT_EXPIRES_IN` и `REFRESH_TOKEN_EXPIRES_IN`, причём срок refresh-токена в БД захардкожен на 24 ч (`backend/src/config/configuration.ts:L27, L31`, `auth.service.ts:L94, L156, L249`).

---

## 2. Факты по темам

### 2.1. Endpoints и адреса

| Endpoint | Метод | Назначение | Формат ответа | Источник |
|---|---|---|---|---|
| `http://<host>:3000/graphql` | `POST` | GraphQL HTTP: queries и mutations | JSON `{ data, errors? }` | 01:L23, 02:L263-265, 06:L38, `main.ts:L134` |
| `http://<host>:3000/graphql` | `GET` | GraphQL Playground (HTML-страница; `playground: true`) | HTML | 01:L24, 06:L59, `graphql.module.ts:L16`, `apollo-base.driver.js:L64` |
| `ws://<host>:3000/graphql` | WS upgrade | Subscriptions по протоколу `graphql-ws` (субпротокол `graphql-transport-ws`) | JSON-сообщения | 01:L25, 06:L233, `gql-subscription.service.js:L14-18, L51-66` |
| `/health` | `GET` | Terminus-проверка Postgres + Redis, плюс `timestamp`, `uptime` | `{ status, info, error, details, timestamp, uptime }` (формат @nestjs/terminus; при ошибке компонента — HTTP 503, детали не проверялись) | 01:L17, `backend/src/health/health.controller.ts:L33-42` |
| `/health/live` | `GET` | Liveness без тяжёлых проверок | `{ status: "ok", timestamp }` | `health.controller.ts:L51-54` |
| `/health/ready` | `GET` | Readiness (Postgres + Redis) | Terminus-формат | `health.controller.ts:L62-66` |
| `/health/detail` | `GET` | Детальный статус | `{ status: "healthy"\|"unhealthy", timestamp, components: { database: { status, latency, connections }, redis: { status, latency } } }` | `health.controller.ts:L74-87` |
| `/metrics` | `GET` | Prometheus | text | 01:L27, L379 (контроллер не проверялся) |
| `/` | `GET` | Строка приветствия | text | `backend/src/app.controller.ts:L8-11` |

- Порт: `PORT`, по умолчанию `3000` (`main.ts:L134`, `configuration.ts:L6`). Глобального префикса пути нет (`main.ts` не вызывает `setGlobalPrefix`).
- Путь GraphQL `/graphql` — дефолт `@nestjs/apollo` (`apolloBaseDriver.mergeDefaultOptions`: `path: '/graphql'`); переменная `GRAPHQL_PATH` из `backend/.env` кодом не читается (grep по `backend/src` — нет вхождений).
- Веб-клиент задаёт адреса через `VITE_API_URL` / `VITE_WS_URL` с дефолтами `http://localhost:3000/graphql` / `ws://localhost:3000/graphql` (`src/env.ts:L7-8`, 02:L5-6).
- 06-гайд рекомендует UE-конфиг вида `ApiBaseUrl=http://localhost:3000`, `GraphQLPath=/graphql` и склейку для обоих каналов (06:L44-51).
- Сравнение WS-пути на сервере — `req.url.startsWith('/graphql')` (`gql-subscription.service.js:L61`), т. е. query-string в URL допустим, но не используется.

### 2.2. Версии стека (важно для совместимости протокола)

| Пакет | Версия (установлено) | Источник |
|---|---|---|
| NestJS core | 11.x | `backend/package.json:L51` |
| `@nestjs/graphql` | 13.2.3 | `backend/node_modules/@nestjs/graphql/package.json` |
| `@nestjs/apollo` | 13.2.3 | `backend/node_modules/@nestjs/apollo/package.json` |
| `@apollo/server` | 5.3.0 (Express 5 через `@as-integrations/express5`) | `backend/node_modules/@apollo/server/package.json`, `apollo-base.driver.js:L86` |
| `graphql` | 16.12.0 | `backend/node_modules/graphql/package.json` |
| `graphql-ws` | 6.0.6 | `backend/node_modules/graphql-ws/package.json` |
| `@nestjs/throttler` | 6.5.0 | `backend/node_modules/@nestjs/throttler/package.json` |
| `graphql-depth-limit` 1.1.0, `graphql-validation-complexity` 0.4.2 | — | `backend/package.json:L66, L69` |
| `passport-jwt` 4.0.1, `@nestjs/jwt` 11 | — | `backend/package.json:L53, L74` |

Из `subscriptions` включён только `'graphql-ws': true` (`graphql.module.ts:L19-21`); `subscriptions-transport-ws` не сконфигурирован, поэтому upgrade с legacy-субпротоколом уходит в graphql-ws-сервер и отклоняется (`gql-subscription.service.js:L39-60`, `server-3ewaJSjp.js:L33-37`).

### 2.3. HTTP-транспорт (queries / mutations)

**Запрос** (02:L263-291, 06:L178-198):

```http
POST /graphql HTTP/1.1
Host: localhost:3000
Content-Type: application/json
Authorization: Bearer <accessToken>        # не нужен для публичных операций

{ "query": "<GraphQL-документ>", "variables": { ... }, "operationName": "<имя>" }
```

- `operationName` обязателен, если в документе несколько операций (06:L198); в остальных случаях необязателен.
- `query` может содержать `\n` (06:L196).
- Тело парсит стандартный `express.json()` Nest-адаптера (`backend/node_modules/@nestjs/platform-express/adapters/express-adapter.js:L200-206`); явного лимита в `main.ts` нет — действует дефолт body-parser (100 kb; не проверялось на живом сервере).
- `csrfPrevention: false` — заголовок `apollo-require-preflight` не требуется (`graphql.module.ts:L17`, 02:L259).
- **CORS**: разрешены origin'ы `http://localhost:5173`, `5174`, `5480` и `FRONTEND_URL`; запросы **без заголовка `Origin`** (нативные клиенты) разрешены безусловно (`main.ts:L105-122`). `allowedHeaders`: `Content-Type, Authorization, X-Idempotency-Key, apollo-require-preflight` (`main.ts:L126-131`); для UE, не шлющего `Origin`, CORS не применяется вовсе (06:L63, 01:L303).
- Глобальный `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true, transformOptions: { enableImplicitConversion: true } })` — лишние поля во входных DTO (`RegisterDto`, `LoginDto`, `SettingsDto`, …) дают ошибку валидации; примитивы приводятся неявно (`main.ts:L66-75`, 01:L160, 06:L71).
- Apollo-контекст HTTP: `{ req: ctx.req, isSubscription: false }` (`graphql.module.ts:L34`).
- Резолвер `login` пишет в аудит IP (`req.ip`, `x-forwarded-for`, `x-real-ip`) и `user-agent` (обрезан до 500 символов) (`backend/src/auth/auth.resolver.ts:L11-23, L39-43`, `auth.service.ts:L137-146, L167-175`).

**Ответ** (02:L293, 06:L200-218):

```json
{ "data": { ... } }
{ "data": { "me": null }, "errors": [ ... ] }   // nullable корневое поле
{ "data": null,           "errors": [ ... ] }   // non-null корневое поле (например myStats!, refreshTokens!)
```

**HTTP-статусы (по коду Apollo Server 5.3.0; живая проверка не проводилась):**

| Статус | Когда | Источник |
|---|---|---|
| `200` | Успех; **а также любая ошибка, брошенная резолвером/guard'ом** (в т. ч. `UNAUTHENTICATED`) — `data` есть (`null` или объект), `errors[]` заполнен | `requestPipeline.js:L193-198` (400 ставится только при `result.data === undefined`) |
| `400` | Ошибки до исполнения: синтаксис (`GRAPHQL_PARSE_FAILED`), валидация документа (`GRAPHQL_VALIDATION_FAILED` — сюда же complexity/depth и неизвестные поля/аргументы), приведение переменных (`BAD_USER_INPUT`; `status400ForVariableCoercionErrors` по умолчанию `true`) | `ApolloServer.js:L119`, `requestPipeline.js:L40, L59, L193-198` |
| `500` | Внутренняя ошибка пайплайна без выставленного статуса | `requestPipeline.js:L343-344` |
| `401`, `409` | **В коде не найдены**: `@nestjs/apollo` не задаёт `extensions.http` для Nest-исключений | `apollo-base.driver.js:L161-193`; противоречит 02:L325-330 |

Вывод: UE-клиент **обязан анализировать тело** (`errors[]`) независимо от статуса (06:L218 говорит то же).

### 2.4. WebSocket-транспорт (`graphql-ws`)

**Handshake HTTP-уровня**

- URL `ws://<host>:3000/graphql`, заголовок `Sec-WebSocket-Protocol: graphql-transport-ws` (06:L233, L597; `common-CGW11Fyb.js:L28`).
- Сервер выбирает WS-сервер по субпротоколу: если в списке есть `graphql-ws` (legacy) и нет `graphql-transport-ws` — legacy-сервер (не сконфигурирован), иначе graphql-ws (`gql-subscription.service.js:L51-60`). Без субпротокола или с неверным — после upgrade сокет сразу закрывается кодом **4406 «Subprotocol not acceptable»** (`server-3ewaJSjp.js:L33-37`).
- HTTP-заголовок `Authorization` на handshake **не читается** — токен только в `connection_init` (01:L387, 06:L26).

**Последовательность сообщений (все — текстовые JSON-фреймы)** (02:L308-312, 06:L237-309; `common-CGW11Fyb.js:L45-52`):

| Шаг | Направление | Сообщение | Примечание |
|---|---|---|---|
| 1 | C→S | `{"type":"connection_init","payload":{"authorization":"Bearer <accessToken>"}}` | Ключ `authorization` / `Authorization` / `token`; префикс `Bearer ` добавляется сервером, если отсутствует (`graphql.module.ts:L26-29`). Должно быть отправлено **≤ 3 с** после открытия сокета (`server-3ewaJSjp.js:L12, L42-48`) |
| 2 | S→C | `{"type":"connection_ack"}` | `onConnect` не задан → ack приходит **всегда**, даже с пустым/невалидным токеном (`server-3ewaJSjp.js:L66-76`, `gql-subscription.service.js:L29-37`) |
| 3 | C→S | `{"id":"<uникальный>","type":"subscribe","payload":{"operationName":"...","query":"subscription ...","variables":{...}}}` | `id` уникален в рамках соединения; повтор → закрытие 4409 |
| 4 | S→C | `{"id":"...","type":"next","payload":{"data":{...}}}` | Данные; может содержать `errors` |
| 5 | S→C | `{"id":"...","type":"error","payload":[GraphQLFormattedError,...]}` | Ошибка операции; подписка завершена |
| 6 | S→C / C→S | `{"id":"...","type":"complete"}` | Сервер: поток завершён; клиент: отписка |
| — | C→S / S→C | `{"type":"ping"}` → `{"type":"pong"}` (payload опционален и эхом возвращается) | Сервер отвечает на клиентский `ping` (`server-3ewaJSjp.js:L84-96`); сам JSON-`ping` не инициирует |

**Keep-alive и таймауты (по коду; живая проверка не проводилась):**

| Параметр | Значение | Источник |
|---|---|---|
| Ожидание `connection_init` | 3000 мс → закрытие **4408** | `server-3ewaJSjp.js:L12, L42-48` |
| WS-ping-фреймы от сервера | каждые 12 000 мс; если pong-фрейм не получен за 12 000 мс → `socket.terminate()` (без close-фрейма) | `use/ws.js:L5, L44-58` |
| JSON `{"type":"ka"}` | **не существует** в `graphql-ws` (это legacy `subscriptions-transport-ws`); 06:L254 ошибочен | `common-CGW11Fyb.js:L45-52` |
| Остановка сервера | всем клиентам `close(1001, "Going away")` | `use/ws.js:L98-101` |

**Close-коды** (`common-CGW11Fyb.js:L30-43`, `server-3ewaJSjp.js`):

| Код | Смысл | Когда выдаёт наш сервер |
|---|---|---|
| 4400 | Bad Request | Невалидное/непарсящееся сообщение (`server:L54`) |
| 4401 | Unauthorized | `subscribe` до `connection_ack` (`server:L100-101`) |
| 4403 | Forbidden | Только если `onConnect` вернул `false` — **у нас не сконфигурирован, не выдаётся** (`server:L66-68`); 06:L256, L588 описывают несуществующее поведение |
| 4406 | Subprotocol not acceptable | Неверный/отсутствующий субпротокол (`server:L33-37`) |
| 4408 | Connection initialisation timeout | Нет `connection_init` за 3 с (`server:L42-48`) |
| 4409 | Subscriber for `<id>` already exists | Повторный `subscribe` с тем же `id` (`server:L103-106`) |
| 4429 | Too many initialisation requests | Второй `connection_init` (`server:L57-62`) |
| 4500 | Internal server error | Исключение в обработчике сообщения / сокета (`use/ws.js:L17-27, L36-42, L75-82`) |
| 4504 | Connection acknowledgement timeout | Клиентский код (клиент не дождался ack) — сервер не шлёт |
| 1000 / 1001 | Normal / Going away | Штатное закрытие / остановка сервера |

**Аутентификация по WS (по коду):**

- Контекст-фабрика вызывается graphql-ws **на каждый `subscribe`** (`server-3ewaJSjp.js:L207`), а не один раз на соединение; она формирует `{ req: { headers: { authorization } }, isSubscription: true }` (`graphql.module.ts:L25-32`). Далее `GqlAuthGuard` + passport-jwt читают `req.headers.authorization` как в HTTP (`backend/src/auth/guards/gql-auth.guard.ts:L13-16`, `backend/src/auth/strategies/jwt.strategy.ts:L16`).
- Следствия: (а) токен из `connection_init` фиксирован на всё время жизни сокета; (б) истечение access-токена **не рвёт** уже открытые подписки — guard срабатывает только при новом `subscribe`; (в) чтобы новые подписки открывались после refresh, сокет нужно пересоздать с новым токеном (06:L146). Веб-клиент экспортирует `reconnectWebSocket()` (`src/lib/apolloClient.ts:L151-155`), но **нигде не вызывает** (grep по `src/` — только определение).
- Ошибка guard'а на `subscribe` (по коду `graphql-js` + `graphql-ws`; живая проверка не проводилась): `subscribe()` возвращает `{ errors: [...] }` (не async-iterable) → сервер шлёт `{"type":"next","id":..,"payload":{"errors":[{"message":"Неавторизованный доступ","locations":[..],"path":["gameStateUpdated"]}]}}`, затем `{"type":"complete"}` (`server-3ewaJSjp.js:L223-261`). Apollo-`formatError` и маппинг кодов `@nestjs/apollo` на WS-пути **не применяются** (graphql-ws использует собственные `execute/subscribe`, `gql-subscription.service.js:L27-37`) — поэтому `extensions.code` в WS-ошибках, скорее всего, отсутствует; распознавать придётся по сообщению.
- Ошибки валидации документа подписки (неизвестное поле/аргумент, «Unable to identify operation») приходят как `{"type":"error","payload":[...]}` (`server-3ewaJSjp.js:L170-202`).
- Через graphql-ws технически можно исполнять и `query`/`mutation` (`server-3ewaJSjp.js:L210-215`), но контекст WS не содержит IP/User-Agent (`graphql.module.ts:L31`) — для аудита `login` это нежелательно; документация этот путь не описывает.

**Фильтрация подписок**: на сервере по `gameId`/`userId` (01:L193). Подписки `gameStateUpdated(gameId, since, userId?)`, `attackInitiated`, `defensePlayed`, `combatResolved`, `turnChanged`, `playerJoined`, `playerLeft`, `gameEnded` защищены `@UseGuards(GqlAuthGuard)` (`backend/src/games/resolvers/game-subscription.resolver.ts:L156-321`); `matchFound(userId)` и `presenceUpdated(userIds?)` — **без guard'а** (`backend/src/matchmaking/resolvers/matchmaking.subscription.ts:L218-237`, `backend/src/presence/presence.resolver.ts:L68-83`).

**Доставка событий**: in-memory PubSub внутри инстанса + Redis Pub/Sub `game:updates:<gameId>` между инстансами; для клиента прозрачно (01:L195-199).

### 2.5. Модель аутентификации

| Параметр | Access token | Refresh token | Источник |
|---|---|---|---|
| Алгоритм | JWT, HS256 (дефолт `@nestjs/jwt`) | JWT, HS256 | 02:L336; `auth.service.ts:L470-484` (алгоритм явно не задан) |
| Payload | `{ sub: <userId>, email, iat, exp }` | `{ sub, email, jti: <uuid>, iat, exp }` | `auth.service.ts:L467, L477-480` |
| Секрет | `jwt.secret` ← `JWT_SECRET` (dev-дефолт `dev-secret-key-change-in-production`) | `jwt.refreshSecret` ← `JWT_REFRESH_SECRET` | `configuration.ts:L24-30` |
| TTL | `jwt.expiresIn` ← `JWT_EXPIRES_IN`, дефолт `1h` | `jwt.refreshExpiresIn` ← `REFRESH_TOKEN_EXPIRES_IN`, дефолт `24h`; **плюс** запись в БД с `expiresAt = now + 24h` (захардкожено) | `configuration.ts:L27, L31`; `auth.service.ts:L94, L156, L249` |
| Где проверяется | passport-стратегия `jwt` (`ignoreExpiration: false`) + Redis-blacklist + кэш пользователя 5 мин + БД | `AuthService.refreshTokens`: `jwtService.verifyAsync` → поиск по bcrypt-хешу среди всех токенов пользователя → `revokedAt` → `expiresAt` | `jwt.strategy.ts:L15-63`; `auth.service.ts:L195-283` |
| Хранение на сервере | Нет (blacklist в Redis после logout, TTL = остаток жизни) | Таблица `RefreshToken`: `token` (bcrypt-хеш), `expiresAt`, `revokedAt`, `replacedBy` | `auth.service.ts:L288-306`; `backend/prisma/schema.prisma:L105-118` |
| Cookie | Не используются | Не используются | 02:L14, L259 |

Дополнительно:

- `JwtStrategy.validate` возвращает объект пользователя `{ id, email, username, avatar, role, createdAt, emailVerified }` (из кэша Redis `user:<id>` на 300 с или из БД); он доступен резолверам через `@CurrentUser()` = `req.user` (`jwt.strategy.ts:L33-62`, `backend/src/common/decorators/current-user.decorator.ts:L4-9`). Поле называется **`id`**, не `userId` — см. §4 п. 12.
- Порядок проверок в `validate`: blacklist → кэш → БД; при отсутствии пользователя — `UnauthorizedException('Пользователь не найден')`; при blacklist — `'Token revoked'` (`jwt.strategy.ts:L29-31, L55-57`). Ошибка passport без `err` (истёкший/битый токен) → `GqlAuthGuard.handleRequest` бросает `UnauthorizedException('Неавторизованный доступ')` (`gql-auth.guard.ts:L32-37`).
- Стратегия `jwt-refresh` (`backend/src/auth/strategies/refresh.strategy.ts`) зарегистрирована, но резолвером не используется — `refreshTokens` принимает токен аргументом (`auth.resolver.ts:L52-57`).
- **Redis-деградация**: при недоступном Redis (таймаут подключения 2 с) все обёртки возвращают `null`/`0` — blacklist не работает (разлогиненный access-токен остаётся валидным до `exp`), кэш пользователя отключён (`backend/src/redis/redis.service.ts:L74-83, L104-122, L355-373`; 01:L363).
- Пароли — bcrypt cost 10; при логине защита от timing attack (сравнение с фиктивным хешем) (`auth.service.ts:L51, L129-132`).
- Аудит: `AuthAuditLog` для `register`, `login` (успех/неуспех, IP, UA), `logout`, `password_reset` (`auth.service.ts:L78-84, L137-146, L167-175, L320-326, L396-402`; `schema.prisma:L139-153`).
- Модель `Session` (deviceId, deviceName, ipAddress, refreshToken) существует в Prisma, но в auth-коде не используется (`schema.prisma:L120-135`; grep `session` в `auth.service.ts` — нет).

### 2.6. Полный refresh-цикл

**Серверная семантика `refreshTokens(refreshToken)`** (`auth.service.ts:L195-283`):

1. `verifyAsync(refreshToken, refreshSecret)` — при любой ошибке (подпись, истёкший `exp`, мусор) → `UnauthorizedException('Невалидный refresh token')` (catch-all, L277-282).
2. Загружаются **все** записи `RefreshToken` пользователя `payload.sub` (включая отозванные), сравнение `bcrypt.compare` по очереди (L203-221). Не найден → `'Invalid refresh token'` (L224).
3. `revokedAt != null` → `'Refresh token has been revoked'` (L229); `expiresAt < now` → `'Refresh token expired'` (L233).
4. Генерируется новая пара; в транзакции старый токен помечается `revokedAt`, создаётся новый с `replacedBy = <id старого>`, `expiresAt = now + 24h` (L237-259).
5. Инвалидируется кэш пользователя; возвращается `AuthResponseDto` (access, refresh, user) (L262-276).

Все ошибки — `UnauthorizedException` → в GraphQL `extensions.code = "UNAUTHENTICATED"` (dev) (02:L148, `apollo-base.driver.js:L20`).

**Клиентский алгоритм (рекомендованный доками + уточнения по коду)** (02:L36-40, L316-321; 06:L137-148):

1. `login`/`register` → сохранить `accessToken`, `refreshToken`. Веб-клиент хранит также `expiresAt = now + 60 мин` (не из JWT) в `localStorage` под ключами `unmached_access_token`, `unmached_refresh_token`, `unmached_token_expiry` (`src/lib/token-storage.ts:L6-9, L108-110`, `src/store/authStore.ts:L113-117`).
2. Перед использованием токенов проверить локальный срок; веб-клиент считает токен «скоро истечёт» за 5 мин (`token-storage.ts:L90-96`, метод не задействован в refresh-логике).
3. При старте с сохранёнными токенами — `me`; при ошибке аутентификации — refresh (06:L323, `authStore.ts:L353-367`).
4. Признак необходимости refresh (веб-клиент, `src/lib/error-link.ts:L9-23`): `extensions.code ∈ {UNAUTHENTICATED, AUTH_TOKEN_EXPIRED, AUTH_INVALID_TOKEN}` или сообщение содержит `unauthenticated`/`token expired`/`invalid token`, либо сетевой `statusCode === 401` (L80). Коды `AUTH_TOKEN_EXPIRED`/`AUTH_INVALID_TOKEN` **сервером не выдаются** (grep по `backend/src` — нет) — это «на вырост».
5. Вызвать `refreshTokens(refreshToken)` **single-flight** (один активный refresh, остальные ждут тот же promise) — `authStore.ts:L220-281`.
6. Успех → заменить **оба** токена (старый refresh уже отозван, 02:L150), повторить исходную операцию, пересоздать WS-соединение с новым токеном (06:L146; веб-клиент это фактически не делает — §2.4).
7. Неудача или отсутствие refresh-токена → локальный logout, экран входа (`error-link.ts:L39-55`).
8. `logout` — с валидным access-токеном: он попадает в blacklist на остаток TTL, **все** refresh-токены пользователя (на всех устройствах) отзываются (`auth.service.ts:L288-330`). Клиент чистит хранилище независимо от результата мутации (`authStore.ts:L195-213`).

**Граничные случаи, важные для UE:**

- Потеря ответа на `refreshTokens` (таймаут после того, как сервер уже ротировал) → старый refresh отозван, новый не получен → единственный выход — повторный логин. Клиент должен трактовать `'Refresh token has been revoked'` как «сессия потеряна».
- Два клиента с одним refresh-токеном: первый успешный refresh отзывает токен для второго.
- `resetPassword` отзывает все refresh-токены пользователя (`auth.service.ts:L386-393`); отзывает ли `changePassword` — не проверено.
- Ограничение `refreshTokens` 3/мин объявлено декоратором, но не применяется (см. §2.11) — тем не менее клиент должен рассчитывать на его включение.
- Проактивный refresh по `exp` из JWT (base64url-декодирование payload без проверки подписи) устраняет зависимость от кодов ошибок — критично в production (§2.10).

### 2.7. Auth-мутации (полный список)

Все — в `backend/src/auth/auth.resolver.ts`; throttle-значения — объявленные декораторами (не активны, §2.11).

| Мутация | Аргументы | Auth | Throttle (объявл.) | Возвращает | Ошибки (сообщение → код dev) | Источник |
|---|---|---|---|---|---|---|
| `register(input: RegisterDto!)` | `email` (IsEmail), `username` (3–20, `^[a-zA-Z0-9_]+$`), `password` (≥ 8) | `@Public` | 5/60 с | `AuthResponseDto!` | «Пользователь с таким email уже существует» / «…именем…» → `ConflictException` → `INTERNAL_SERVER_ERROR` + `extensions.status: 409`; валидация → `BAD_REQUEST` | `auth.resolver.ts:L29-34`; `backend/src/auth/dto/register.dto.ts:L4-26`; `auth.service.ts:L38, L47`; 02:L57-108 |
| `login(input: LoginDto!)` | `email` (IsEmail), `password` (непустая строка) | `@Public` | 10/60 с | `AuthResponseDto!` | «Неверный email или пароль» → `UNAUTHENTICATED` | `auth.resolver.ts:L36-43`; `login.dto.ts:L4-15`; `auth.service.ts:L148`; 02:L112-129 |
| `logout` | — | **guard отсутствует** (док: «требует авторизацию», 02:L154; 07:L137 подтверждает отсутствие guard-класса) | — | `Boolean!` (всегда `true`) | При отсутствии токена `user?.id` = `undefined` → см. §4 п. 9 | `auth.resolver.ts:L45-50`; `auth.service.ts:L288-330` |
| `refreshTokens(refreshToken: String!)` | строка refresh-JWT | `@Public` | 3/60 с | `AuthResponseDto!` | «Invalid refresh token», «Refresh token has been revoked», «Refresh token expired», «Невалидный refresh token» → `UNAUTHENTICATED` | `auth.resolver.ts:L52-57`; `auth.service.ts:L224-233, L281`; 02:L133-150 |
| `resetPassword(token: String!, newPassword: String!)` | токен из письма; пароль (валидации длины на уровне DTO нет — аргументы скалярные) | `@Public` | 3/60 с | `Boolean!` | «Невалидный или истёкший токен сброса пароля» → `UNAUTHENTICATED` | `auth.resolver.ts:L59-65`; `auth.service.ts:L362-407`; 02:L164-174 (утверждение «мин. 8 символов» в коде резолвера не найдено) |
| `verifyEmail(token: String!)` | токен верификации | `@Public` | 5/60 с | `Boolean!` | «Невалидный токен верификации» → `UNAUTHENTICATED` | `auth.resolver.ts:L67-73`; `auth.service.ts:L412-431`; 02:L178-186 |

- `requestPasswordReset(email)` реализован в сервисе, но **не экспонирован** как мутация; отправка письма — TODO (`auth.service.ts:L335-357`, 02:L188). Значит, `resetPassword`/`verifyEmail` для UE практически бесполезны: токены получить нечем (токен верификации генерируется при регистрации, но письмо не отправляется — `auth.service.ts:L54, L64`).

**Тип `AuthResponseDto`** (`backend/src/auth/dto/auth-response.dto.ts:L19-53`; `src/gql/graphql.ts:L155-170`):

```graphql
type AuthResponseDto { accessToken: String!  refreshToken: String!  user: AuthUserResponse! }
type AuthUserResponse {
  id: String!  email: String!  username: String!
  avatar: String            # nullable
  role: UserRole!           # enum
  createdAt: DateTime!
  emailVerified: DateTime   # nullable
}
enum UserRole { USER  ADMIN  MODERATOR }     # schema.prisma:L17-21; gql/graphql.ts:L1684-1688
input RegisterDto { email: String!  username: String!  password: String! }
input LoginDto    { email: String!  password: String! }
```

Пример в 02:L96 с `"role": "PLAYER"` **неверен** — такого значения в enum нет.

### 2.8. Queries и мутации пользователей

Резолвер `backend/src/users/users.resolver.ts`.

**Queries**

| Query | Аргументы | Guard | Возвращает | Особенности | Источник |
|---|---|---|---|---|---|
| `me` | — | `GqlAuthGuard` | `UserWithSettingsResponse` (nullable) | `findById` из кэша/БД + `settings`; `NotFoundException` если пользователь исчез → `INTERNAL_SERVER_ERROR` + `status 404` | `users.resolver.ts:L31-41`; `users.service.ts:L20-31` |
| `user(id: String!)` | `id` | нет | `PublicUserResponse` (nullable) | При `profileVisible = false` и чужом запросе → `{ id, username: "Hidden", avatar: null, createdAt }`. `@CurrentUser()` без guard'а всегда `undefined` → владелец тоже увидит «Hidden» | `users.resolver.ts:L47-73` |
| `userByUsername(username: String!)` | `username` | нет | `PublicUserResponse` (nullable) | То же | `users.resolver.ts:L78-103` |
| `myStats` | — | `GqlAuthGuard` | `UserStatsResponse!` | | `users.resolver.ts:L108-112` |
| `stats(userId: String!)` | `userId` | нет | `UserStatsResponse` (nullable) | Публичная статистика | `users.resolver.ts:L117-120` |
| `mySettings` | — | `GqlAuthGuard` | `UserSettingsGraphql!` | | `users.resolver.ts:L125-129` |
| `leaderboard(...)`, `topPlayers(...)`, `getPlayerRank(...)` | см. `backend/src/users/leaderboard.resolver.ts:L27-57` | нет guard'ов | `leaderboard`/`topPlayers` возвращают **`String`** (JSON-строка), `getPlayerRank` — `LeaderboardRankResponse` | Аргументы не исследовались (вне фокуса) | `leaderboard.resolver.ts:L23-57`; 01:L207 |

**Мутации** (все с `@UseGuards(GqlAuthGuard)`)

| Mutation | Аргументы / валидация | Throttle (объявл.) | Возвращает | Ошибки | Источник |
|---|---|---|---|---|---|
| `updateProfile(input: UpdateProfileDto!)` | `username?` (3–20, `[a-zA-Z0-9_]`), `avatar?` (`IsUrl`, ≤ 500). Поля `role` в DTO **нет** (02:L232 ошибочно) | 5/60 с | `UserResponse!` | «Это имя пользователя уже занято» → Conflict (→ `INTERNAL_SERVER_ERROR` + `status 409`); валидация → `BAD_REQUEST` | `users.resolver.ts:L135-143`; `backend/src/users/dto/update-profile.dto.ts:L5-23`; `users.service.ts:L113` |
| `updateSettings(input: SettingsDto!)` | `theme?` ∈ `light\|dark\|auto`, `language?` ∈ `ru\|en`, `soundEnabled?`, `musicEnabled?`, `profileVisible?`, `showOnlineStatus?` (Boolean) | 10/60 с | `UserSettingsGraphql!` | валидация → `BAD_REQUEST` | `users.resolver.ts:L149-157`; `backend/src/users/dto/settings.dto.ts:L4-37` |
| `changePassword(input: ChangePasswordDto!)` | `currentPassword: String!`, `newPassword: String!` (≥ 8) | 3/60 с | `Boolean!` | «Неверный текущий пароль» → `UnauthorizedException` → **`UNAUTHENTICATED`** (не `UNAUTHORIZED`, как в 02:L253) — клиент не должен запускать refresh-цикл по этой ошибке | `users.resolver.ts:L163-172`; `change-password.dto.ts:L4-16`; `users.service.ts:L154` |
| `deleteAccount` | — | 2/3600 с | `Boolean!` | | `users.resolver.ts:L178-184` |
| `uploadAvatar(fileUrl: String!)` | URL (загрузка файла не реализована — только ссылка) | 5/60 с | `String!` | | `users.resolver.ts:L190-195`; `backend/src/users/profile.service.ts:L17-23` |
| `removeAvatar` | — | 10/60 с | `Boolean!` | | `users.resolver.ts:L201-207` |

**Типы** (`backend/src/users/dto/update-profile.dto.ts:L28-98`, `settings.dto.ts:L39-61`, `leaderboard-options.dto.ts:L66-112`; `src/gql/graphql.ts:L1733-1741`):

```graphql
type UserResponse {
  id: String!  email: String!  username: String!  avatar: String
  role: UserRole!  createdAt: DateTime!  emailVerified: DateTime
}
type UserWithSettingsResponse {           # = UserResponse + settings
  id: String!  email: String!  username: String!  avatar: String
  role: UserRole!  createdAt: DateTime!  emailVerified: DateTime
  settings: UserSettingsResponse           # nullable
}
type UserSettingsResponse {  id: String!  theme: String!  language: String!  soundEnabled: Boolean!
                             musicEnabled: Boolean!  profileVisible: Boolean!  showOnlineStatus: Boolean! }
type UserSettingsGraphql   { — те же 7 полей — }
type PublicUserResponse    { id: String!  username: String!  avatar: String  createdAt: DateTime! }
type UserStatsResponse {
  userId: String!  gamesPlayed: Int!  gamesWon: Int!  gamesLost: Int!  winRate: Float!
  currentElo: Int!  peakElo: Int!  lastPlayedAt: DateTime  totalPlayTime: Int!  favoriteHero: FavoriteHero
}
type FavoriteHero { id: String!  name: String!  nameEn: String!  nameRu: String! }
input UpdateProfileDto  { username: String  avatar: String }
input SettingsDto       { theme: String  language: String  soundEnabled: Boolean  musicEnabled: Boolean
                          profileVisible: Boolean  showOnlineStatus: Boolean }
input ChangePasswordDto { currentPassword: String!  newPassword: String! }
```

Поля `lastPlayedAt`, `totalPlayTime`, `favoriteHero` в 02:L203 не упомянуты, но есть в схеме.

Операции веб-клиента для паритета: `Me`, `MyStats`, `MySettings` (`src/graphql/queries/auth.graphql:L3-40`), `Register`, `Login`, `RefreshTokens` (запрашивает только `accessToken refreshToken`), `Logout`, `UpdateProfile`, `UpdateSettings` (`src/graphql/mutations/auth.graphql:L43-94`).

### 2.9. Presence / heartbeat (прикладной keep-alive)

`backend/src/presence/presence.resolver.ts`, DTO — `backend/src/presence/dto/heartbeat.dto.ts:L4-11`, `presence.dto.ts:L4-40`, enum — `backend/src/presence/models/presence.model.ts:L1-6`.

```graphql
mutation heartbeat(input: HeartbeatInput!): HeartbeatResponse!
input HeartbeatInput { status: PresenceStatus = ONLINE   currentGameId: String }
enum PresenceStatus { OFFLINE  ONLINE  INGAME  INQUEUE }      # на проводе — имена ключей enum
type HeartbeatResponse { presence: Presence!  ttl: Float! }     # ttl всегда 300
type Presence { userId: String!  status: PresenceStatus!  currentGameId: String  lastSeenAt: Float! }
query getPresence(userId: String!): Presence
query getOnlineUsers: OnlineUsersResponse!   # { userIds: [String!]!, count: Float! }
query getOnlineCount: Float!
subscription presenceUpdated(userIds: [String!]): Presence!
```

- TTL присутствия в Redis — 300 с (`backend/src/presence/presence.service.ts:L5`); значит heartbeat реже, чем раз в 5 мин, переводит игрока в offline.
- **Дефект (по коду)**: у `heartbeat` нет `@UseGuards(GqlAuthGuard)`, а резолвер читает `user.userId` — при отсутствии `req.user` будет `TypeError` → `INTERNAL_SERVER_ERROR`; при наличии guard'а поле называлось бы `id`, а не `userId` (`presence.resolver.ts:L18-24`; `jwt.strategy.ts:L42-52`). Веб-клиент `heartbeat` не вызывает (grep по `src/` — нет). Работоспособность — открытый вопрос (§4 п. 12).

### 2.10. Формат и коды ошибок

**Цепочка формирования (HTTP, по коду):** исключение резолвера → `graphql-js` оборачивает в `GraphQLError` → `@nestjs/apollo` `createTransformHttpErrorFn` добавляет `extensions.code` по HTTP-статусу Nest-исключения и `extensions.originalError = { message, error, statusCode }` (`apollo-base.driver.js:L144-193`) → пользовательский `formatError` (`graphql.module.ts:L60-103`) → Apollo сериализует.

**Маппинг Nest-исключений → `extensions.code`** (`apollo-base.driver.js:L17-22, L170-190`):

| Исключение (где возникает) | HTTP-статус исключения | `extensions.code` | Дополнительно |
|---|---|---|---|
| `BadRequestException` — `ValidationPipe` (лишние/невалидные поля DTO) | 400 | **`BAD_REQUEST`** | `extensions.originalError.message` — массив строк class-validator |
| `UnprocessableEntityException` | 422 | `BAD_USER_INPUT` | В auth/users-коде не используется |
| `UnauthorizedException` — guard, login, refresh, changePassword | 401 | **`UNAUTHENTICATED`** | `originalError: { message, error: "Unauthorized", statusCode: 401 }` |
| `ForbiddenException` — `MatchmakingGuard`, `AdminGuard` | 403 | `FORBIDDEN` | |
| `ConflictException` — register, updateProfile | 409 | **`INTERNAL_SERVER_ERROR`** | `extensions.status: 409`, `originalError.statusCode: 409` |
| `NotFoundException` — findById и др. | 404 | **`INTERNAL_SERVER_ERROR`** | `extensions.status: 404` |
| Прочие `Error` | — | `INTERNAL_SERVER_ERROR` (Apollo default) | |
| Ошибки валидации документа, complexity, depth | — | `GRAPHQL_VALIDATION_FAILED` | HTTP 400 |
| Ошибка синтаксиса | — | `GRAPHQL_PARSE_FAILED` | HTTP 400 |
| Ошибка приведения переменных | — | `BAD_USER_INPUT` | HTTP 400 |

Таблица 02:L325-330 (`CONFLICT` 409, `BAD_USER_INPUT` 400 для валидации, `UNAUTHENTICATED` 401) коду не соответствует.

**Итоговая форма элемента `errors[]`** (`graphql.module.ts:L68-102`):

- `NODE_ENV != production` (текущий docker-compose): `{ message, code, path, locations, extensions: { code, originalError?, status?, stacktrace? } }` — код продублирован на верхнем уровне и в `extensions`.
- `NODE_ENV = production`, «бизнес-ошибка» (`code ∈ {BAD_USER_INPUT, GRAPHQL_VALIDATION_FAILED}` или `message` содержит `not found` / `unauthorized` — латиница, нижний регистр): `{ message, code, path }` — **без `extensions`**.
- `NODE_ENV = production`, всё остальное (включая `UNAUTHENTICATED` с сообщением «Неавторизованный доступ», `BAD_REQUEST`, `FORBIDDEN`): `{ message: "Internal server error", code: "INTERNAL_SERVER_ERROR" }`.

Тексты сообщений — смесь русского и английского («Неавторизованный доступ», «Token revoked», «Пользователь не найден», «Invalid refresh token»); полагаться на них можно только как на вспомогательный признак (06:L583).

**Сообщения лимитов**: complexity — `Query is too complex: <n>. Maximum allowed complexity is 1000.` (`graphql.module.ts:L48-52`); depth — стандартное сообщение `graphql-depth-limit` (текст в коде не задан).

**Таблица реакций (06:L573-579, скорректирована по коду):**

| Признак | Реакция |
|---|---|
| `code == UNAUTHENTICATED` (dev) от защищённой операции; или сообщение ∈ {«Неавторизованный доступ», «Token revoked», «Пользователь не найден»}; или локальный `exp` истёк | Refresh-цикл → повтор операции |
| `UNAUTHENTICATED` от `login` («Неверный email или пароль») или `changePassword` («Неверный текущий пароль») | Ошибка ввода, **не** refresh |
| `refreshTokens` вернул любую ошибку | Logout, экран входа |
| `BAD_REQUEST` (+ `originalError.message[]`), `BAD_USER_INPUT`, `GRAPHQL_VALIDATION_FAILED` | Ошибка ввода/клиентский баг; показать/залогировать |
| `INTERNAL_SERVER_ERROR` с `extensions.status == 409` | Конфликт (email/username занят) |
| `INTERNAL_SERVER_ERROR` с `extensions.status == 404` | Не найдено |
| `FORBIDDEN` | Нет прав / бан matchmaking / уже в игре |
| Сетевая ошибка, обрыв WS | Retry с backoff; resync через `gameState` + `eventsSince` (06:L578, L511) |

### 2.11. Лимиты

| Лимит | Значение | Активен? | Источник |
|---|---|---|---|
| Complexity | 1000; при > 500 — `console.warn`; правило `graphql-validation-complexity` с `variables: {}` | Да (validation rule) | `graphql.module.ts:L39-53`; 01:L162; 06:L69 |
| Depth | 7; игнорируются `_entities`, `_service` | Да | `graphql.module.ts:L55-57`; 06:L70 |
| Throttler глобальный | `ttl 60000 мс, limit 10` | **Нет** — `ThrottlerGuard` не привязан (grep `APP_GUARD`/`ThrottlerGuard` по `backend/src` пуст); `THROTTLE_TTL`/`THROTTLE_LIMIT` из `.env` не читаются | `app.module.ts:L54-59`; 01:L138, L161, L298 |
| Throttler per-operation (объявленные) | register 5/мин, login 10/мин, refreshTokens 3/мин, resetPassword 3/мин, verifyEmail 5/мин, updateProfile 5/мин, updateSettings 10/мин, changePassword 3/мин, deleteAccount 2/час, uploadAvatar 5/мин, removeAvatar 10/мин, createGame 10/мин, joinGame 15/мин, leaveGame 10/мин, startGame 5/мин, abortGame 5/мин, toggleReady 20/мин, selectHero 10/мин, joinQueue 5/мин, игровые действия 20–30/мин | **Нет** (см. выше); проектировать клиент так, будто включены | `auth.resolver.ts`, `users.resolver.ts`, `game.resolver.ts:L115-201`, `game-actions.resolver.ts:L256-518`, `matchmaking.resolver.ts:L44-46` |
| ValidationPipe | `whitelist`, `forbidNonWhitelisted`, `transform`, `enableImplicitConversion` | Да | `main.ts:L66-75` |
| Тело HTTP | дефолт body-parser (100 kb), явно не настроен | — | `express-adapter.js:L200-206` |
| WS `connection_init` | 3 с | Да | `server-3ewaJSjp.js:L12` |
| WS keep-alive | ping-фрейм каждые 12 с, pong ≤ 12 с | Да | `use/ws.js:L5, L44-58` |
| Кэш пользователя в JWT-стратегии | 300 с — изменения профиля могут не отражаться в `req.user` до 5 мин (обновляется при refresh/logout через `invalidateUserCache`) | Да (при наличии Redis) | `jwt.strategy.ts:L60`; `auth.service.ts:L262, L329` |

### 2.12. Идемпотентность

| Механизм | Где заявлен | Что в коде | Вывод для UE |
|---|---|---|---|
| Аргумент `idempotencyKey: String` (nullable) у `createGame` | 07:L146; `src/store/lobbyStore.ts:L26-27` | Есть: `game.resolver.ts:L115-123`; сервер ищет существующую игру по ключу и `userId` (`game.service.ts:L88-92, L160-168`) | Передавать GUID; повтор с тем же ключом вернёт ту же игру |
| `idempotencyKey` у `joinGame` | `lobbyStore.ts:L38-39` (веб-клиент) | **Нет** в резолвере (`game.resolver.ts:L130-141`) и в схеме (`src/gql/graphql.ts:L867-869`) | Не передавать — будет `GRAPHQL_VALIDATION_FAILED` (Unknown argument) |
| `idempotencyKey` у `joinQueue`, `leaveQueue`, `leaveAllQueues` | 06:L224, L398-422; `src/store/matchmakingStore.ts:L7-27` | **Нет**: `matchmaking.resolver.ts:L44-50, L91-96, L116-118`; `graphql.ts:L872-884`; 07:L189-191 | Не передавать |
| HTTP-заголовок `X-Idempotency-Key` для `toggleReady`/`selectHero` | 06:L225-227, L382, L601; `src/store/heroSelectionStore.ts:L214, L235-238` (формат `${Date.now()}-${random}`) | Сервер только разрешает заголовок в CORS (`main.ts:L92-95, L124-131`); нигде не читает (grep `idempotency` по `backend/src` — только `createGame` и `main.ts`) | Безвреден, но бесполезен; серверной дедупликации нет |
| `toggleReady` | — | Семантически переключатель — повтор запроса инвертирует состояние (по имени; тело не исследовалось) | Клиенту нужна собственная защита от двойной отправки |
| `joinQueue` | 07:L189 | Под distributed-lock `mm:join:<userId>` (5 с); повторный вход в очередь — ре-вход (`matchmaking.resolver.ts:L51-58`) | Повтор безопасен на уровне сервера |

### 2.13. ENV / конфигурация

`ConfigModule` читает `.env`, `.env.local`, `.env.docker` (`app.module.ts:L27-31`; 01:L282).

**Переменные, которые код реально читает** (grep `process.env.*` и `configService.get(...)` по `backend/src`):

| Переменная | Дефолт | Использование | Источник |
|---|---|---|---|
| `NODE_ENV` | `development` | Валидация секретов в prod, `formatError`, playground | `main.ts:L10`, `graphql.module.ts:L68`, `configuration.ts:L2, L7` |
| `PORT` | `3000` | HTTP + WS | `main.ts:L134`, `configuration.ts:L6` |
| `DATABASE_URL` | — (обязательна в prod; Prisma требует всегда) | Prisma | `main.ts:L13`, `configuration.ts:L11` |
| `JWT_SECRET` | dev: `dev-secret-key-change-in-production`; prod: обязателен, ≥ 32 симв., без `change`/`default` | Подпись access | `configuration.ts:L24-26`, `main.ts:L13-42` |
| `JWT_REFRESH_SECRET` | dev: `dev-refresh-secret-change-in-production`; prod: те же требования | Подпись refresh | `configuration.ts:L28-30`, `main.ts:L13-42` |
| `JWT_EXPIRES_IN` | `1h` | TTL access-JWT | `configuration.ts:L27` |
| `REFRESH_TOKEN_EXPIRES_IN` | `24h` | TTL refresh-JWT (**срок в БД всё равно 24 ч**) | `configuration.ts:L31`; `auth.service.ts:L94, L156, L249` |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | `localhost` / `6379` / — | Redis (client/publisher/subscriber) + BullMQ | `configuration.ts:L16-18`, `redis.service.ts:L20-31`, `app.module.ts:L38-40` |
| `FRONTEND_URL` | `http://localhost:5173` | Доп. CORS-origin | `main.ts:L84, L109`, `configuration.ts:L36` |
| `DISABLE_CACHE` | `false` | Отключение Redis-кэша | 01:L299 (единичное вхождение в `backend/src`) |

**Переменные из `.env.example`/`backend/.env`, которые кодом НЕ читаются** (по grep): `JWT_ACCESS_EXPIRATION`, `JWT_REFRESH_EXPIRATION` (`.env.example:L36-37` — 01:L229 ошибочно связывает их с TTL), `THROTTLE_TTL`, `THROTTLE_LIMIT` (`.env.example:L49-50`), `DEFAULT_BOARD_ID`, `MAX_PLAYERS_PER_GAME`, `TURN_TIME_LIMIT` (`L42-44`), `LOG_LEVEL`, `LOG_FORMAT` (`L55-56`), `SENTRY_DSN`, `PROMETHEUS_ENABLED` (`L67-68`), а также `GRAPHQL_PATH`, `CORS_ORIGIN`, `BULLMQ_REDIS_*` из `backend/.env`. `validation.schema.ts` объявляет `REFRESH_TOKEN_SECRET` (не `JWT_REFRESH_SECRET`) и нигде не импортируется (`backend/src/config/validation.schema.ts:L1-25`; grep — нет импортов).

**Docker-окружение**: `docker-compose.yml:L41-45` задаёт `JWT_SECRET`/`JWT_REFRESH_SECRET` (dev-значения), `PORT=3000`, `NODE_ENV=development`, `FRONTEND_URL=http://localhost:5173`; `command: npm run start:dev` (`L57`). По памяти проекта entrypoint образа фактически запускает `node dist/src/main` (`start:prod`) при том же `NODE_ENV=development` — т. е. на текущем стенде действует dev-формат ошибок.

**Для UE-клиента** нужны только: базовый URL (`http(s)://host:port`), путь `/graphql`, схема `ws(s)`. Никаких секретов на клиенте нет.

### 2.14. Покрытие операций guard'ами (что реально требует токен)

Глобального guard'а нет; `@Public()` без глобального guard'а — маркер без эффекта (`auth.module.ts:L28-29`; `public.decorator.ts:L3-4`).

| Категория | Операции | Guard | Источник |
|---|---|---|---|
| Требуют валидный access-токен (`@UseGuards(GqlAuthGuard)`) | `me`, `myStats`, `mySettings`, `updateProfile`, `updateSettings`, `changePassword`, `deleteAccount`, `uploadAvatar`, `removeAvatar`; `game`, `myGames`, `gameState`, `gameSequence`, `eventsSince`; `createGame`, `joinGame`, `leaveGame`, `startGame`, `abortGame`, `toggleReady`, `selectHero`; все игровые действия (`maneuver` … `setStance`) + доп. guard'ы фаз; подписки `gameStateUpdated`, `attackInitiated`, `defensePlayed`, `combatResolved`, `turnChanged`, `playerJoined`, `playerLeft`, `gameEnded`; admin-операции (+ `AdminGuard`) | `GqlAuthGuard` | `users.resolver.ts`, `game.resolver.ts:L28-223`, `game-actions.resolver.ts:L256-518`, `game-subscription.resolver.ts:L170-320`, `admin.resolver.ts` |
| Публичные по коду | `register`, `login`, `refreshTokens`, `resetPassword`, `verifyEmail`; `user`, `userByUsername`, `stats`; `leaderboard`, `topPlayers`, `getPlayerRank`; `availableGames`, `heroStances`; контент `heroes`, `heroesPaginated`, `hero`, `cards`, `card`, `boards`, `boardsPaginated`, `board`, `contentVersion`, `sets`, `heroesBySet`, `contentSummary`, `clearContentCache`; `getPresence`, `getOnlineUsers`, `getOnlineCount`; подписки `matchFound`, `presenceUpdated` | нет | `auth.resolver.ts`, `users.resolver.ts:L47-120`, `leaderboard.resolver.ts`, `game.resolver.ts:L51-52, L100-101`, `content.resolver.ts:L53-182`, `presence.resolver.ts`, `matchmaking.subscription.ts:L218` |
| Ожидают `req.user`, но **без** `GqlAuthGuard` | `logout` (`user?.id`); `heartbeat` (`user.userId`); `joinQueue`, `leaveQueue`, `leaveAllQueues` (`MatchmakingGuard` проверяет `request.user.userId` через `switchToHttp()`), `acceptMatch`, `declineMatch`, `queueStatus`, `penaltyInfo` | нет / `MatchmakingGuard` | `auth.resolver.ts:L45-50`; `presence.resolver.ts:L18-24`; `matchmaking.resolver.ts:L44-50, L91-118, L135-175, L203-243`; `matchmaking.guard.ts:L13-19`; 07:L137, L189-191, L217 |

Примечание к контенту: реальные имена query — `heroes`, `hero`, `cards`, `card`, `boards`, `board`, `sets`, `contentVersion` (`content.resolver.ts:L53-155`), а не `getAllHeroes`/`getHero`/`getAllBoards`/`getAllSets`/`getContentVersion` из 01:L208, L275 (это имена методов класса).

### 2.15. Поведение веб-клиента (эталон для паритета)

| Аспект | Реализация | Источник |
|---|---|---|
| Split HTTP/WS | `subscription` → `GraphQLWsLink`, остальное → `HttpLink` (`credentials: 'include'` — для UE не нужно) | `src/lib/apolloClient.ts:L43-61` |
| WS-клиент | `graphql-ws` `createClient`: `lazy: true`, `retryAttempts: 5`, `connectionParams` — функция, читающая токен из `localStorage` при каждом (пере)подключении, `authorization: "Bearer <t>"` или `""` | `apolloClient.ts:L16-36` |
| Цепочка линков | `retryLink → authLink → errorLink → splitLink` | `apolloClient.ts:L78-83` |
| Retry HTTP | 3 попытки, задержка 300 мс → макс. 10 с с jitter; **мутации не повторяются**; повтор при `networkError` и кодах `SERVICE_UNAVAILABLE`, `NETWORK_ERROR`, `TIMEOUT`, `INTERNAL_SERVER_ERROR`, `DATABASE_ERROR` или сообщениях `timeout`/`network`/`service unavailable` | `src/lib/retry-link.ts:L12-59` |
| Инъекция токена | `authorization: Bearer <token>` из store или `localStorage`; пустая строка, если токена нет | `src/lib/auth-link.ts:L11-27` |
| Детект auth-ошибки | см. §2.6 п. 4; `AbortError` игнорируется | `src/lib/error-link.ts:L9-23, L70-75` |
| Хранение токенов | `localStorage`, ключи `unmached_access_token`, `unmached_refresh_token`, `unmached_token_expiry`; при `Date.now() >= expiry` токены стираются | `src/lib/token-storage.ts:L6-9, L33-36` |
| Расчёт expiry | `now + 60 мин` константой, JWT не декодируется | `token-storage.ts:L108-110`; `authStore.ts:L116, L169, L260` |
| Single-flight refresh | `_isRefreshing` + `_refreshPromise` | `authStore.ts:L220-281` |
| Реконнект подписок игры | 5 попыток, задержка `1000 × 2^(n−1)` мс; после переподключения — resync по `sequenceNumber`/`eventsSince` | `src/phaser/network/SubscriptionHandler.ts:L98-101, L482-507` |
| Пересоздание WS после refresh | Функция есть, не вызывается | `apolloClient.ts:L151-155` |

---

## 3. Следствия для UE-клиента

**Транспорт**

1. Реализовать два канала поверх стандартных модулей UE: `FHttpModule` (POST JSON на `/graphql`) и `IWebSocket` из модуля `WebSockets` с явным субпротоколом **`graphql-transport-ws`** (06:L170-172, §2.4). Плагины, поддерживающие только legacy `subscriptions-transport-ws`, непригодны (06:L20-28).
2. Конфиг: `ApiBaseUrl` + `GraphQLPath` (ini/Project Settings), из них строить `http(s)://…/graphql` и `ws(s)://…/graphql` (06:L44-51). TLS-схемы на сервере сейчас нет — учесть при деплое (не найдено в источниках).
3. Всегда слать `Content-Type: application/json`; `Origin` не слать (нативный клиент его и не шлёт); `apollo-require-preflight` не нужен (§2.3).
4. Отправлять в input-DTO **только** поля схемы (`forbidNonWhitelisted`), иначе `BAD_REQUEST` (§2.3, §2.10).
5. Держать запросы в пределах complexity 1000 / depth 7; при `GRAPHQL_VALIDATION_FAILED` с текстом «Query is too complex» — упрощать (§2.11).
6. Не рассчитывать на HTTP-статус: 200 при ошибках исполнения, 400 при ошибках валидации; парсить `errors[]` всегда (§2.3).

**WebSocket**

7. Отправлять `connection_init` немедленно после `OnConnected` — окно 3 с (4408). Ждать `connection_ack` до первого `subscribe` (иначе 4401).
8. Уникальные `id` подписок в рамках соединения (иначе 4409); не слать второй `connection_init` (4429).
9. Убедиться, что реализация WS в UE автоматически отвечает pong-фреймом на ping-фрейм сервера (libwebsockets это делает по умолчанию — требует проверки на целевых платформах); иначе сервер молча `terminate()` через ~24 с. Дополнительно можно слать JSON `{"type":"ping"}` и контролировать `pong` как прикладной liveness (§2.4).
10. `connection_ack` **не означает**, что токен валиден. Валидность проверяется на каждом `subscribe`; ошибка приходит как `next` с `errors` (без `extensions.code`) + `complete` либо как `error`. Обрабатывать оба варианта как «подписка не установлена» и запускать refresh, если сообщение — одно из auth-сообщений (§2.4, §2.10).
11. После refresh пересоздавать сокет (новый `connection_init`) **до** открытия новых подписок; уже открытые подписки можно не рвать, но при переподключении — переподписаться со `since = lastSequence` и сделать `gameState`/`eventsSince` resync (06:L511).
12. Обработка close-кодов: 4406 — ошибка конфигурации субпротокола (не ретраить); 4408/4401/4409/4429 — ошибка логики клиента; 4500/1001/1006 — reconnect с backoff (эталон: 5 попыток, 1 с × 2^n).

**Аутентификация**

13. Хранить `accessToken`, `refreshToken` в защищённом хранилище (06:L148 предлагает `USaveGame`; шифрование — на усмотрение проекта). Не хранить пароль.
14. Декодировать `exp` из access-JWT (base64url, без проверки подписи) и делать **проактивный** refresh за несколько минут до истечения — это единственный надёжный путь в production, где `UNAUTHENTICATED` маскируется (§2.10).
15. Реализовать single-flight refresh, очередь ожидающих операций и повтор после успеха; при любой ошибке `refreshTokens` — logout и экран входа; при «Refresh token has been revoked» — сообщить пользователю о входе с другого устройства/потере сессии (§2.6).
16. Различать `UNAUTHENTICATED` от `login`/`changePassword` (ошибка ввода) и от защищённых операций (истёкший токен) — по имени операции, а не только по коду.
17. `logout` вызывать с валидным access-токеном (иначе `user?.id` = `undefined`; см. §4 п. 9); локальные токены чистить всегда.
18. `register`: валидировать на клиенте `username` (3–20, `[A-Za-z0-9_]`), `password` (≥ 8), `email`; конфликт распознавать по `extensions.status == 409` / `originalError.statusCode == 409`, а не по коду `CONFLICT` (§2.7, §2.10).
19. Не реализовывать UI сброса пароля/подтверждения email: серверные мутации есть, но токены пользователю не доставляются (§2.7).
20. `UserRole` — `USER | ADMIN | MODERATOR`; `me` возвращает `role`, `emailVerified`, `settings` (nullable) — использовать для UI.

**Идемпотентность и лимиты**

21. `createGame` — передавать GUID в `idempotencyKey`; `joinGame`, `joinQueue`, `leaveQueue`, `leaveAllQueues` — **без** этого аргумента. `X-Idempotency-Key` можно не слать (сервер не читает); защиту от двойных кликов на `toggleReady`/`selectHero` делать на клиенте (§2.12).
22. Заложить клиентские rate-limit'ы по объявленным значениям (refreshTokens 3/мин, login 10/мин, register 5/мин, игровые действия 20–30/мин), хотя сервер их сейчас не применяет (§2.11).
23. Heartbeat присутствия — не чаще раза в ~2–4 мин при TTL 300 с, но только после подтверждения работоспособности `heartbeat` (§2.9, §4 п. 12).

**Парсинг ответов**

24. Парсер ошибок должен читать `code` из `errors[i].extensions.code` **или** `errors[i].code` (prod-формат без `extensions`), `extensions.status`, `extensions.originalError.statusCode/message[]` (§2.10).
25. Учитывать обе формы `data`: `{ "me": null }` и `null` (§2.3).
26. Скаляры: `DateTime` — ISO-строка (`createdAt`, `emailVerified`, `lastPlayedAt`); `Float`/`Number` для `ttl`, `lastSeenAt`, `getOnlineCount` (`presence.dto.ts`).

---

## 4. Открытые вопросы / несоответствия

1. **Субпротокол**: 01:L179, L29 и 02:L297 называют субпротокол `graphql-ws`; фактическое значение заголовка — `graphql-transport-ws` (06:L22, L233, L597; `common-CGW11Fyb.js:L28`). Отправка `graphql-ws` приведёт к 4406.
2. **`{"type":"ka"}`** (06:L254) — сообщение legacy-протокола; в `graphql-ws` keep-alive — WS-ping-фреймы + опциональные `ping`/`pong` (`use/ws.js:L44-58`, `common-CGW11Fyb.js:L47-48`).
3. **4403 на handshake при невалидном токене** (06:L256, L588) — `onConnect` не сконфигурирован, `connection_ack` выдаётся всегда; ошибка проявится на `subscribe` (`server-3ewaJSjp.js:L66-76`, `graphql.module.ts:L22-35`). Живая проверка формы WS-ошибки (`next`+`errors` vs `error`) не проводилась.
4. **HTTP-статусы 401/409** (02:L106, L129, L325-330; 06:L141, L575) — в коде не найдено механизма их выставления; ожидается 200 (`apollo-base.driver.js:L161-193`, `requestPipeline.js:L193-198`). Требует живой проверки.
5. **Коды ошибок** `CONFLICT`, `UNAUTHORIZED`, `BAD_USER_INPUT` для валидации DTO (02:L106-107, L253, L328-329) — фактически `INTERNAL_SERVER_ERROR`+`status 409`, `UNAUTHENTICATED`, `BAD_REQUEST` (`apolloPredefinedExceptions`, `apollo-base.driver.js:L17-22`).
6. **Production-маскирование `UNAUTHENTICATED`** (`graphql.module.ts:L71-92`): «Неавторизованный доступ» не содержит `unauthorized` → в prod клиент получит `INTERNAL_SERVER_ERROR`. Нужно решение на бэкенде (добавить `UNAUTHENTICATED`/`FORBIDDEN`/`BAD_REQUEST` в список бизнес-ошибок) либо строго проактивный refresh на клиенте.
7. **Rate limiting не применяется**: `ThrottlerGuard` не привязан (`app.module.ts:L54-59`; grep). Все цифры в 01:L161, L391, 02:L57-L236, 06 — декларативны. Если бэкенд подключит guard, для GraphQL потребуется `getRequestResponse`-override (стандартный `ThrottlerGuard` рассчитан на HTTP-контекст) — тогда поведение по WS также изменится.
8. **`@Public()` без глобального guard'а** — маркер без эффекта; документация (01:L231, 02:L44 «глобальный guard») описывает несуществующую конфигурацию.
9. **`logout` без guard'а** (`auth.resolver.ts:L45-50`; 02:L154 «требует авторизацию»; 07:L137 подтверждает): при вызове без токена `authService.logout(undefined, undefined)` выполнит `refreshToken.updateMany({ where: { userId: undefined, revokedAt: null } })` — в Prisma `undefined` в `where` означает «без фильтра», т. е. потенциально **отзыв refresh-токенов всех пользователей** и запись `AuthAuditLog` с `userId: undefined` (`auth.service.ts:L309-326`). Требует живой проверки и исправления на бэкенде.
10. **`schema.gql`** (01:L388, L218) — файл не существует (`autoSchemaFile: true`, схема в памяти; `find` по репо — нет). Источник SDL — introspection (`codegen.ts:L4-14`) или 07-документ.
11. **`.env.example` vs код**: `JWT_ACCESS_EXPIRATION=15m` / `JWT_REFRESH_EXPIRATION=7d` не читаются (01:L229 связывает их с TTL); действуют `JWT_EXPIRES_IN=1h` / `REFRESH_TOKEN_EXPIRES_IN=24h`, а срок refresh в БД захардкожен 24 ч (`configuration.ts:L27-31`, `auth.service.ts:L94, L156, L249`). `validation.schema.ts` не подключён и ссылается на `REFRESH_TOKEN_SECRET`.
12. **`userId` vs `id` в `req.user`**: `JwtStrategy` возвращает `id` (`jwt.strategy.ts:L42-52`), а `heartbeat`, `MatchmakingGuard` и matchmaking-резолверы читают `user.userId` (`presence.resolver.ts:L24`, `matchmaking.guard.ts:L17`, `matchmaking.resolver.ts:L51`, `user-payload.model.ts:L7-11`); `MatchmakingGuard` к тому же берёт запрос через `switchToHttp()` (`matchmaking.guard.ts:L14`), что в GraphQL-контексте возвращает не `req`. Работоспособность `heartbeat` и matchmaking-мутаций под вопросом (вне фокуса R1, но влияет на auth-контракт).
13. **`idempotencyKey`** у `joinGame`/`joinQueue`/`leaveQueue`/`leaveAllQueues` (06:L224, L398-422; `lobbyStore.ts:L38-39`; `matchmakingStore.ts:L7-27`, в HEAD тоже) отсутствует в схеме (`graphql.ts:L867-884`; 07:L189-191) — веб-клиент, вероятно, получает `GRAPHQL_VALIDATION_FAILED` на этих операциях. `X-Idempotency-Key` сервером не читается.
14. **Имена контентных query** в 01:L208, L275 (`getAllHeroes`, …) — это методы класса; в схеме `heroes`, `hero`, `cards`, `card`, `boards`, `board`, `sets`, `contentVersion` (`content.resolver.ts:L53-155`). Смоук-команда 01:L273-276 с `getAllHeroes` не сработает.
15. **`role` в `UpdateProfileDto`** (02:L232) — поля нет (`update-profile.dto.ts:L5-23`). **`role: "PLAYER"`** в примере 02:L96 — значения нет в enum (`schema.prisma:L17-21`).
16. **`UserStatsResponse`**: 02:L203 не перечисляет `lastPlayedAt`, `totalPlayTime`, `favoriteHero` (`leaderboard-options.dto.ts:L81-112`).
17. **`resetPassword` «мин. 8 символов»** (02:L166) — валидатор на скалярном аргументе в резолвере не найден (`auth.resolver.ts:L59-65`).
18. **Веб-клиент не пересоздаёт WS после refresh** (02:L38, 06:L146 утверждают обратное): `reconnectWebSocket()` не вызывается (`apolloClient.ts:L151-155`; grep).
19. **`leaveQueue(mode)`** — тип аргумента `String` в резолвере (`matchmaking.resolver.ts:L94`) и в `graphql.ts:L882-884`; 07:L190 указывает `GameMode!`.
20. **Redis-деградация**: blacklist и кэш пользователя молча отключаются без Redis (`redis.service.ts:L78-83, L104-122`) — logout не инвалидирует access-токен. Документация (02:L22, L40) об этом не предупреждает.
21. **Health-эндпоинты**: точный формат ответа terminus и статус 503 при падении компонента не проверялись на живом сервере.
22. **Лимит тела запроса** (100 kb по умолчанию) и поведение при превышении — не проверялись.
23. **Мутации/queries по WS**: технически исполняются graphql-ws (`server-3ewaJSjp.js:L210-215`), но нигде не документированы; в WS-контексте нет IP/UA для аудита `login`. Использовать не рекомендуется без решения бэкенда.
24. **Стенд**: по памяти проекта контейнер запускает `start:prod` при `NODE_ENV=development` (`docker-compose.yml:L44, L57`) — при переводе на `production` изменится формат ошибок (§2.10) и отключится Playground.

---

## 5. Источники

**Документация**
- `docs/backend-api/01-architecture.md` — L10-29, L112-149, L153-220, L224-231, L237-276, L280-303, L307-347, L351-379, L383-391.
- `docs/backend-api/02-auth.md` — L3-8, L12-49, L53-188, L192-253, L257-330, L334-338.
- `docs/backend-api/06-unreal-integration-guide.md` — L7-28, L32-71, L75-148, L152-172, L176-227, L231-311, L315-513, L517-548, L552-590, L594-614.
- `docs/backend-api/07-graphql-schema-reference.md` — L95-98, L137-140, L146, L178-191, L217, L601-602 (использован только для перекрёстной проверки).
- Память проекта: `C:/Users/ren/.claude/projects/C--Users-ren-WebstormProjects-unmached-unmached/memory/unmatched-launch-procedure.md` (порты, режим запуска контейнера).

**Бэкенд (код)**
- `backend/src/main.ts` — L9-55, L66-75, L78-102, L105-134.
- `backend/src/app.module.ts` — L27-31, L54-59.
- `backend/src/app.controller.ts` — L8-11.
- `backend/src/graphql/graphql.module.ts` — L14-21, L22-35, L37-58, L60-103.
- `backend/src/config/configuration.ts` — L6-36; `backend/src/config/validation.schema.ts` — L1-25.
- `backend/.env.example` — L11-68; `backend/.env` (только имена ключей); `docker-compose.yml` — L41-57; `backend/package.json` — L9-15, L43-74.
- `backend/src/auth/auth.module.ts` — L16-29; `auth.resolver.ts` — L11-73; `auth.service.ts` — L16, L31-117, L123-190, L195-283, L288-330, L335-357, L362-431, L466-490.
- `backend/src/auth/strategies/jwt.strategy.ts` — L15-63; `refresh.strategy.ts` — L8-38; `backend/src/auth/guards/gql-auth.guard.ts` — L13-37.
- `backend/src/auth/dto/auth-response.dto.ts` — L5-53; `register.dto.ts` — L4-26; `login.dto.ts` — L4-15.
- `backend/src/common/decorators/current-user.decorator.ts` — L4-9; `public.decorator.ts` — L3-4.
- `backend/src/users/users.resolver.ts` — L31-207; `users.service.ts` — L20-31, L113, L154; `profile.service.ts` — L17-23; `leaderboard.resolver.ts` — L23-57.
- `backend/src/users/dto/update-profile.dto.ts` — L5-98; `settings.dto.ts` — L4-61; `change-password.dto.ts` — L4-16; `leaderboard-options.dto.ts` — L66-112.
- `backend/src/redis/redis.service.ts` — L20-83, L104-145, L355-378.
- `backend/src/presence/presence.resolver.ts` — L18-83; `presence/dto/heartbeat.dto.ts` — L4-11; `presence/dto/presence.dto.ts` — L4-40; `presence/models/presence.model.ts` — L1-6; `presence/presence.service.ts` — L5.
- `backend/src/games/game.resolver.ts` — L28-223; `games/game.service.ts` — L88-92, L160-168; `games/resolvers/game-actions.resolver.ts` — L256-518; `games/resolvers/game-subscription.resolver.ts` — L156-321.
- `backend/src/matchmaking/resolvers/matchmaking.resolver.ts` — L44-118, L135-258; `matchmaking/resolvers/matchmaking.subscription.ts` — L214-237; `matchmaking/guards/matchmaking.guard.ts` — L13-19; `matchmaking/models/user-payload.model.ts` — L7-11.
- `backend/src/content/content.resolver.ts` — L53-182; `backend/src/admin/admin.resolver.ts` — L49-310; `backend/src/health/health.controller.ts` — L18-87.
- `backend/prisma/schema.prisma` — L17-56, L105-153.

**Библиотеки (установленные в `backend/node_modules`)**
- `graphql-ws/dist/common-CGW11Fyb.js` — L28-52; `graphql-ws/dist/server-3ewaJSjp.js` — L12-14, L25-48, L54-106, L160-261; `graphql-ws/dist/use/ws.js` — L5-108.
- `@nestjs/graphql/dist/services/gql-subscription.service.js` — L14-66; `@nestjs/graphql/dist/services/resolvers-explorer.service.js` — L111-143.
- `@nestjs/apollo/dist/drivers/apollo-base.driver.js` — L17-22, L64, L86-118, L144-193.
- `@apollo/server/dist/esm/ApolloServer.js` — L119; `@apollo/server/dist/esm/requestPipeline.js` — L40, L59, L193-198, L343-344.
- `@nestjs/platform-express/adapters/express-adapter.js` — L200-206.

**Веб-клиент (код)**
- `src/env.ts` — L7-8; `codegen.ts` — L4-14.
- `src/lib/apolloClient.ts` — L16-61, L78-83, L151-160; `src/lib/auth-link.ts` — L11-27; `src/lib/error-link.ts` — L9-101; `src/lib/retry-link.ts` — L8-61; `src/lib/token-storage.ts` — L6-9, L20-43, L90-110.
- `src/store/authStore.ts` — L89-137, L195-213, L220-281, L353-367; `src/store/lobbyStore.ts` — L26-39; `src/store/matchmakingStore.ts` — L7-27; `src/store/heroSelectionStore.ts` — L214-238.
- `src/graphql/queries/auth.graphql` — L3-40; `src/graphql/mutations/auth.graphql` — L43-94; `src/graphql/mutations/room.graphql` — L3-27.
- `src/gql/graphql.ts` — L155-170, L580-589, L826-829, L862-884, L917-930, L943-966, L1684-1688, L1733-1741.
- `src/phaser/network/SubscriptionHandler.ts` — L98-101, L482-507.
