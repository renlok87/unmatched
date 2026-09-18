# Аутентификация и пользователи

Документация API аутентификации бэкенда (NestJS + GraphQL, Apollo Server, протокол `graphql-ws`).

- **HTTP endpoint:** `http://localhost:3000/graphql` (см. `src/env.ts`, переопределяется `VITE_API_URL`)
- **WebSocket endpoint:** `ws://localhost:3000/graphql` (переопределяется `VITE_WS_URL`)
- **Playground:** `http://localhost:3000/graphql` (GraphQL Playground включён)
- Исходники: `backend/src/auth/`, `backend/src/users/`, `backend/src/graphql/graphql.module.ts`

---

## 1. Общая схема аутентификации

Используется **JWT с двумя токенами** (access + refresh). Cookie **не используются** — токены передаются только через HTTP-заголовок / connection params.

| Параметр | Access Token | Refresh Token |
|---|---|---|
| Время жизни | 1 час (`jwt.expiresIn`, по умолчанию `1h`) | 24 часа (`jwt.refreshExpiresIn`, по умолчанию `24h`) |
| Секрет | `jwt.secret` | `jwt.refreshSecret` |
| Payload | `{ sub: userId, email }` | `{ sub, email, jti }` (уникальный `jti` для каждого токена) |
| Где проверяется | Passport стратегия `jwt` (`backend/src/auth/strategies/jwt.strategy.ts`) | Метод `refreshTokens` в `AuthService` |
| Хранение на сервере | Нет (плюс blacklist в Redis при logout) | В БД, таблица `RefreshToken` (только bcrypt-хеш, ротация при каждом refresh) |

### 1.1. Как токен прикрепляется к запросам

- **HTTP (queries/mutations):** заголовок `Authorization: Bearer <accessToken>`.
  На веб-клиенте это делает `authLink` (`src/lib/auth-link.ts`) — берёт токен из `authStore` или `localStorage` (ключи `unmached_access_token`, `unmached_refresh_token`, `unmached_token_expiry` — см. `src/lib/token-storage.ts`).
- **WebSocket (subscriptions):** токен передаётся в **connection params** при установке соединения:
  ```json
  { "authorization": "Bearer <accessToken>" }
  ```
  Серверная контекст-фабрика (`backend/src/graphql/graphql.module.ts`) читает `connectionParams.authorization` (или `Authorization` / `token`; префикс `Bearer` добавляется автоматически, если его нет) и подставляет в `req.headers.authorization`, после чего работает обычный `GqlAuthGuard` + passport-jwt.

### 1.2. Жизненный цикл

1. **register / login** → сервер возвращает `accessToken` + `refreshToken` + `user`. Клиент сохраняет токены (в браузере — localStorage).
2. Все защищённые запросы идут с `Authorization: Bearer <accessToken>`.
3. При ошибке `UNAUTHENTICATED` / 401 / «token expired» клиент (`errorLink`, `src/lib/error-link.ts`) вызывает `refreshTokens(refreshToken)`; при успехе — повторяет исходный запрос и **переподключает WebSocket** (`wsClient.terminate()` — `connectionParams` функция вызывается заново). При неудаче refresh — logout.
4. **Ротация refresh token:** при каждом `refreshTokens` старый refresh токен ревокуется (`revokedAt`), новый сохраняется в БД со ссылкой `replacedBy`.
5. **logout:** access token добавляется в Redis-blacklist (TTL = остаток жизни токена), все refresh токены пользователя ревокуются.

### 1.3. Дополнительные механизмы безопасности

- `GqlAuthGuard` (`backend/src/auth/guards/gql-auth.guard.ts`) — глобальный guard; резолверы с декоратором `@Public()` доступны без токена.
- Rate limiting (`@nestjs/throttler`) на все чувствительные мутации (лимиты указаны ниже).
- Защита от timing attack при логине (сравнение с фиктивным bcrypt-хешем).
- Валидация JWT: проверка Redis-blacklist, кеш пользователя в Redis (5 мин), загрузка из БД.
- Ограничения GraphQL: complexity limit 1000, depth limit 7.
- Аудит: таблица `AuthAuditLog` (register / login / logout / password_reset).

---

## 2. Мутации аутентификации

### 2.1. `register` — регистрация

Публичная (`@Public`), throttle: 5 запросов/мин.

Аргумент `input: RegisterDto!`:

| Поле | Тип | Валидация |
|---|---|---|
| `email` | `String!` | валидный email |
| `username` | `String!` | 3–20 символов, только `[a-zA-Z0-9_]` |
| `password` | `String!` | минимум 8 символов |

Возвращает `AuthResponseDto`: `accessToken`, `refreshToken`, `user` (`id`, `email`, `username`, `avatar` (nullable), `role: UserRole`, `createdAt: DateTime`, `emailVerified: DateTime` (nullable)).

```graphql
mutation Register($input: RegisterDto!) {
  register(input: $input) {
    accessToken
    refreshToken
    user { id email username avatar role createdAt emailVerified }
  }
}
```

Переменные:
```json
{ "input": { "email": "player@mail.com", "username": "player_1", "password": "secret123" } }
```

Пример ответа:
```json
{
  "data": {
    "register": {
      "accessToken": "eyJhbGciOiJIUzI1NiIs...",
      "refreshToken": "eyJhbGciOiJIUzI1NiIs...",
      "user": {
        "id": "clx...",
        "email": "player@mail.com",
        "username": "player_1",
        "avatar": null,
        "role": "PLAYER",
        "createdAt": "2026-09-02T10:00:00.000Z",
        "emailVerified": null
      }
    }
  }
}
```

Ошибки:
- `CONFLICT` (409) — «Пользователь с таким email уже существует» / «Пользователь с таким именем уже существует».
- `BAD_USER_INPUT` — не прошла валидация полей.
- Throttler — слишком много запросов (429).

### 2.2. `login` — вход

Публичная, throttle: 10 запросов/мин. IP и User-Agent логируются в аудит.

Аргумент `input: LoginDto!`: `email: String!`, `password: String!`.

```graphql
mutation Login($input: LoginDto!) {
  login(input: $input) {
    accessToken
    refreshToken
    user { id email username }
  }
}
```

Ответ — как у `register` (`AuthResponseDto`).

Ошибки:
- `UNAUTHENTICATED` (401) — «Неверный email или пароль».

### 2.3. `refreshTokens` — обновление токенов

Публичная, throttle: 3 запроса/мин. Реализует ротацию: старый refresh токен ревокуется, выдаётся новая пара.

Аргумент: `refreshToken: String!`. Возвращает `AuthResponseDto`.

```graphql
mutation RefreshTokens($refreshToken: String!) {
  refreshTokens(refreshToken: $refreshToken) {
    accessToken
    refreshToken
    user { id email username }
  }
}
```

Ошибки:
- `UNAUTHENTICATED` (401) — «Invalid refresh token» (не найден в БД), «Refresh token has been revoked», «Refresh token expired», «Невалидный refresh token» (в т.ч. истёк JWT).

> Важно: после каждого успешного refresh предыдущий refresh токен становится недействительным — клиент обязан сохранить новый.

### 2.4. `logout` — выход

Требует авторизацию. Access token берётся из заголовка `Authorization` и добавляется в Redis-blacklist; все refresh токены пользователя ревокуются. Возвращает `Boolean`.

```graphql
mutation Logout { logout }
```

Ответ: `{ "data": { "logout": true } }`

### 2.5. `resetPassword` — сброс пароля по токену

Публичная, throttle: 3 запроса/мин. Ревокует все refresh токены пользователя.

Аргументы: `token: String!` (из email-ссылки), `newPassword: String!` (мин. 8 символов).

```graphql
mutation ResetPassword($token: String!, $newPassword: String!) {
  resetPassword(token: $token, newPassword: $newPassword)
}
```

Ошибки: `UNAUTHENTICATED` (401) — «Невалидный или истёкший токен сброса пароля».

### 2.6. `verifyEmail` — подтверждение email

Публичная, throttle: 5 запросов/мин.

Аргумент: `token: String!`. Возвращает `Boolean`.

```graphql
mutation VerifyEmail($token: String!) { verifyEmail(token: $token) }
```

Ошибки: `UNAUTHENTICATED` — «Невалидный токен верификации».

> Запрос токена сброса пароля по email (`requestPasswordReset`) реализован только в сервисе и **не экспонирован как GraphQL-мутация**.

---

## 3. Queries и мутации пользователей

Резолвер: `backend/src/users/users.resolver.ts`.

### 3.1. Queries

| Query | Аргументы | Авторизация | Возвращает |
|---|---|---|---|
| `me` | — | да | `UserWithSettingsResponse` (nullable) — полные данные + `settings` |
| `user(id: String!)` | `id` | нет (публичная) | `PublicUserResponse` (nullable): `id`, `username`, `avatar`, `createdAt`; при скрытом профиле — `username: "Hidden"` |
| `userByUsername(username: String!)` | `username` | нет | аналогично `user` |
| `myStats` | — | да | `UserStatsResponse`: `userId`, `gamesPlayed`, `gamesWon`, `gamesLost`, `winRate`, `currentElo`, `peakElo` |
| `stats(userId: String!)` | `userId` | нет | `UserStatsResponse` (nullable) |
| `mySettings` | — | да | `UserSettingsGraphql`: `id`, `theme`, `language`, `soundEnabled`, `musicEnabled`, `profileVisible`, `showOnlineStatus` |

```graphql
query Me {
  me {
    id
    email
    username
    avatar
    createdAt
    settings { theme soundEnabled musicEnabled language profileVisible }
  }
}
```

```graphql
query MyStats {
  myStats { userId gamesPlayed gamesWon gamesLost winRate currentElo peakElo }
}
```

Ошибка при отсутствии/невалидном токене: `UNAUTHENTICATED` (401) — «Неавторизованный доступ» / «Token revoked» / «Пользователь не найден».

### 3.2. Мутации

| Mutation | Аргументы | Throttle | Возвращает |
|---|---|---|---|
| `updateProfile(input: UpdateProfileDto!)` | `username?` (3–20, `[a-zA-Z0-9_]`), `avatar?`, `role?` — все optional | 5/мин | `UserResponse` |
| `updateSettings(input: SettingsDto!)` | `theme?` (`light`/`dark`/`auto`), `language?` (`ru`/`en`), `soundEnabled?`, `musicEnabled?`, `profileVisible?`, `showOnlineStatus?` | 10/мин | `UserSettingsGraphql` |
| `changePassword(input: ChangePasswordDto!)` | `currentPassword: String!`, `newPassword: String!` (мин. 8) | 3/мин | `Boolean` |
| `deleteAccount` | — | 2/час | `Boolean` |
| `uploadAvatar(fileUrl: String!)` | `fileUrl` | 5/мин | `String` (URL аватара) |
| `removeAvatar` | — | 10/мин | `Boolean` |

Все требуют авторизации.

```graphql
mutation UpdateProfile($input: UpdateProfileDto!) {
  updateProfile(input: $input) { id username avatar }
}
```

```graphql
mutation ChangePassword($input: ChangePasswordDto!) {
  changePassword(input: $input)
}
```

Ошибки: `UNAUTHENTICATED`, `CONFLICT` (занятое имя пользователя), `BAD_USER_INPUT` (валидация), `UNAUTHORIZED` (неверный `currentPassword`).

---

## 4. Подключение из не-браузерного клиента (Unreal Engine)

Cookie не используются — сервер-stateless относительно сессий, вся авторизация через `Authorization: Bearer <accessToken>`. CORS и `csrfPrevention: false` — проблем из движка нет.

### 4.1. HTTP (queries / mutations)

- **URL:** `http://<host>:3000/graphql`, метод `POST`, `Content-Type: application/json`.
- **Заголовок:** `Authorization: Bearer <accessToken>` (для публичных операций register/login не нужен).
- **Тело:** `{ "query": "...", "variables": { ... }, "operationName": "..." }`.

Полный пример (логин):

```
POST http://localhost:3000/graphql
Content-Type: application/json

{
  "query": "mutation Login($input: LoginDto!) { login(input: $input) { accessToken refreshToken user { id email username } } }",
  "variables": { "input": { "email": "player@mail.com", "password": "secret123" } },
  "operationName": "Login"
}
```

Пример авторизованного запроса (`me`):

```
POST http://localhost:3000/graphql
Content-Type: application/json
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

{
  "query": "query Me { me { id email username avatar createdAt } }",
  "operationName": "Me"
}
```

Формат ответа — стандартный JSON GraphQL: `{ "data": { ... } }` или `{ "data": {...}, "errors": [ { "message", "path", "extensions": { "code" } } ] }`.

### 4.2. WebSocket (subscriptions)

- **Протокол:** `graphql-ws` (не legacy `subscriptions-transport-ws`). Подключение к `ws://<host>:3000/graphql`, subprotocol `graphql-ws`.
- **Connection params** при `connection_init`:

```json
{
  "authorization": "Bearer <accessToken>"
}
```

Сервер также принимает `Authorization` или `token` в качестве ключа; префикс `Bearer` необязателен (добавляется автоматически).

Последовательность graphql-ws:
1. Клиент открывает WS и отправляет `{ "type": "connection_init", "payload": { "authorization": "Bearer <token>" } }`.
2. Сервер отвечает `{ "type": "connection_ack" }`.
3. Далее `{ "type": "subscribe", "id": "1", "payload": { "query": "subscription ...", "variables": {} } }`.
4. Сервер шлёт `{ "type": "next", "id": "1", "payload": { "data": ... } }`.

### 4.3. Рекомендуемый алгоритм для UE-клиента

1. `register` или `login` по HTTP → сохранить `accessToken` (1 час) и `refreshToken` (24 часа).
2. Все HTTP-запросы — с заголовком `Authorization: Bearer <accessToken>`.
3. WebSocket открывать с connection params из п. 4.2.
4. При ошибке с `extensions.code == "UNAUTHENTICATED"` или HTTP 401: вызвать `refreshTokens(refreshToken)`, заменить **оба** токена (старый refresh невалиден), повторить запрос; при неудаче — повторный логин. После refresh — переподключить WebSocket с новым токеном.
5. При выходе — вызвать `logout` с валидным access токеном.
6. Учитывать rate limits (особенно `refreshTokens` — 3/мин) и не спамить запросами.

### 4.4. Коды ошибок GraphQL

| Код | HTTP | Значение |
|---|---|---|
| `UNAUTHENTICATED` | 401 | нет/невалиден/истёк токен, токен в blacklist |
| `CONFLICT` | 409 | email/username заняты |
| `BAD_USER_INPUT` | 400 | ошибка валидации входных данных |
| `INTERNAL_SERVER_ERROR` | 500 | прочее (в production детали скрываются) |

---

## 5. Схема токенов и хранение

- Формат: стандартный JWT (HS256), access: `{ sub, email, iat, exp }`; refresh: `{ sub, email, jti, iat, exp }`.
- Браузерный клиент хранит токены в `localStorage` с префиксом `unmached_` (см. `src/lib/token-storage.ts`); для UE — сохранять в безопасном хранилище на стороне клиента.
- Refresh токены сервер хранит только в виде bcrypt-хеша; утечка БД не компрометирует токены напрямую.
