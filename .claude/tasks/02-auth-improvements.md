# План улучшений Auth Module (ФАЗА 2.1)

> На основе архитектурного ревью от backend-architect агента

## Общая оценка: 7/10

Хороший базис для MVP, но есть критичные уязвимости безопасности, которые необходимо устранить до продакшена.

---

## 🚨 КРИТИЧНЫЕ УЛУЧШЕНИЯ (до продакшена)

### 1. Refresh Token Management

**Проблема:** Refresh токен никогда не аннулируется. Если злоумышленник украдёт refresh токен, он получит доступ на 24 часа.

**Решение:** Добавить модель `RefreshToken` в Prisma schema.

```prisma
// prisma/schema.prisma
model RefreshToken {
  id           String   @id @default(cuid())
  token        String   @unique  // hashed version
  userId       String
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)
  expiresAt    DateTime
  createdAt    DateTime @default(now())
  revokedAt    DateTime?
  replacedBy   String?  // id нового токена при ротации

  @@index([userId])
  @@index([token])
  @@index([expiresAt])
}
```

**Изменения в `auth.service.ts`:**
```typescript
async refreshTokens(refreshToken: string) {
  // 1. Проверяем валидность
  const payload = await this.jwtService.verifyAsync(refreshToken, {
    secret: this.configService.get<string>('JWT_REFRESH_SECRET'),
  });

  // 2. Хешируем и ищем в БД
  const tokenHash = await bcrypt.hash(refreshToken, 10);
  const storedToken = await this.prisma.refreshToken.findUnique({
    where: { token: tokenHash },
    include: { user: true },
  });

  if (!storedToken || storedToken.revokedAt) {
    throw new UnauthorizedException('Invalid refresh token');
  }

  if (storedToken.expiresAt < new Date()) {
    throw new UnauthorizedException('Refresh token expired');
  }

  // 3. Ревокуем старый токен
  await this.prisma.refreshToken.update({
    where: { id: storedToken.id },
    data: { revokedAt: new Date() },
  });

  // 4. Генерируем новые токены
  const tokens = await this.generateTokens(storedToken.user.id, storedToken.user.email);

  // 5. Сохраняем новый refresh token
  const newTokenHash = await bcrypt.hash(tokens.refreshToken, 10);
  await this.prisma.refreshToken.create({
    data: {
      token: newTokenHash,
      userId: storedToken.user.id,
      expiresAt: new Date(Date.now() + 24 * 60 * 60 * 1000), // 24 часа
      replacedBy: storedToken.id,
    },
  });

  return {
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
    user: {
      id: storedToken.user.id,
      email: storedToken.user.email,
      username: storedToken.user.username,
      avatar: storedToken.user.avatar,
      createdAt: storedToken.user.createdAt,
    },
  };
}
```

---

### 2. Redis Blacklist для logout

**Проблема:** Метод `logout()` пустой — access токен остаётся валидным до истечения 1 часа.

**Решение:** Использовать Redis для blacklist отозванных токенов.

**Изменения в `redis.service.ts`:**
```typescript
// Добавить методы:
async addToBlacklist(token: string, ttl: number): Promise<void> {
  await this.setex(`blacklist:${token}`, ttl, '1');
}

async isBlacklisted(token: string): Promise<boolean> {
  return (await this.exists(`blacklist:${token}`)) === 1;
}
```

**Изменения в `auth.service.ts`:**
```typescript
async logout(userId: string, accessToken: string): Promise<void> {
  // Декодируем токен без верификации для получения exp
  const decoded = this.jwtService.decode(accessToken) as any;

  if (!decoded || !decoded.exp) {
    return;
  }

  // Вычисляем TTL до истечения токена
  const ttl = decoded.exp - Math.floor(Date.now() / 1000);

  if (ttl > 0) {
    await this.redisService.addToBlacklist(accessToken, ttl);
  }
}
```

**Изменения в `jwt.strategy.ts`:**
```typescript
async validate(payload: any) {
  const request = this.getRequest();
  const token = request.headers?.authorization?.replace('Bearer ', '');

  // Проверяем blacklist
  if (token && await this.redisService.isBlacklisted(token)) {
    throw new UnauthorizedException('Token revoked');
  }

  // ... остальная логика
}
```

**Изменения в `auth.resolver.ts`:**
```typescript
@Mutation(() => Boolean)
async logout(
  @Context() context: any,
  @CurrentUser() user: any,
) {
  const accessToken = context.req.headers?.authorization?.replace('Bearer ', '');
  await this.authService.logout(user.id, accessToken);
  return true;
}
```

---

### 3. Rate Limiting

**Проблема:** Auth эндпоинты уязвимы для brute force и спама аккаунтов.

**Решение:** `@nestjs/throttler` уже в dependencies — нужно добавить.

**Изменения в `app.module.ts`:**
```typescript
import { ThrottlerModule } from '@nestjs/throttler';

@Module({
  imports: [
    // ... другие импорты
    ThrottlerModule.forRoot([{
      ttl: 60000,      // 60 секунд
      limit: 10,       // 10 запросов
    }]),
  ],
})
export class AppModule {}
```

**Изменения в `auth.resolver.ts`:**
```typescript
import { Throttle } from '@nestjs/throttler';

@Mutation(() => AuthResponseDto)
@Public()
@Throttle({ default: { limit: 5, ttl: 60000 } })  // 5 запросов в минуту
async register(@Args('input') input: RegisterDto) {
  return this.authService.register(input);
}

@Mutation(() => AuthResponseDto)
@Public()
@Throttle({ default: { limit: 10, ttl: 60000 } })  // 10 запросов в минуту
async login(@Args('input') input: LoginDto) {
  return this.authService.login(input);
}

@Mutation(() => AuthResponseDto)
@Public()
@Throttle({ default: { limit: 3, ttl: 60000 } })  // 3 запроса в минуту (строже)
async refreshTokens(@Args('refreshToken') refreshToken: string) {
  return this.authService.refreshTokens(refreshToken);
}
```

---

### 4. Timing Attack Protection

**Проблема:** Разное время ответа для существующего и несуществующего email.

**Решение:** Всегда выполнять `bcrypt.compare()`.

**Изменения в `auth.service.ts`:**
```typescript
async login(dto: LoginDto) {
  const user = await this.prisma.user.findUnique({
    where: { email: dto.email },
  });

  // Фиктивный хеш для Timing Attack Protection
  const dummyHash = '$2b$10$XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX';

  const isPasswordValid = user
    ? await bcrypt.compare(dto.password, user.password)
    : await bcrypt.compare(dto.password, dummyHash);

  if (!user || !isPasswordValid) {
    throw new UnauthorizedException('Неверный email или пароль');
  }

  // ... остальная логика
}
```

---

### 5. Transaction Safety при регистрации

**Проблема:** Создание пользователя, UserSettings и UserStats не транзакционное.

**Решение:** Обернуть в `prisma.$transaction()`.

**Изменения в `auth.service.ts`:**
```typescript
async register(dto: RegisterDto) {
  // ... валидации ...

  const hashedPassword = await bcrypt.hash(dto.password, 10);

  return this.prisma.$transaction(async (tx) => {
    const user = await tx.user.create({
      data: {
        email: dto.email,
        username: dto.username,
        password: hashedPassword,
      },
    });

    await tx.userSettings.create({
      data: { userId: user.id },
    });

    await tx.userStats.create({
      data: { userId: user.id },
    });

    const tokens = await this.generateTokens(user.id, user.email);

    return {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      user: {
        id: user.id,
        email: user.email,
        username: user.username,
        avatar: user.avatar,
        createdAt: user.createdAt,
      },
    };
  });
}
```

---

### 6. ENV Validation

**Проблема:** Небезопасные дефолтные значения секретов в configuration.

**Решение:** Валидация обязательных переменных в production.

**Изменения в `main.ts`:**
```typescript
async function bootstrap() {
  // Валидация ENV в production
  if (process.env.NODE_ENV === 'production') {
    const requiredEnvVars = [
      'JWT_SECRET',
      'JWT_REFRESH_SECRET',
      'DATABASE_URL',
    ];

    const missing = requiredEnvVars.filter(key => !process.env[key]);

    if (missing.length > 0) {
      throw new Error(
        `Missing required environment variables: ${missing.join(', ')}`
      );
    }

    // Проверка длины секретов
    if (process.env.JWT_SECRET!.length < 32) {
      throw new Error('JWT_SECRET must be at least 32 characters');
    }

    if (process.env.JWT_REFRESH_SECRET!.length < 32) {
      throw new Error('JWT_REFRESH_SECRET must be at least 32 characters');
    }
  }

  // ... остальная логика
}
```

**Изменения в `configuration.ts`:**
```typescript
jwt: {
  secret: process.env.JWT_SECRET,  // Убрать дефолт!
  expiresIn: process.env.JWT_EXPIRES_IN || '1h',
  refreshSecret: process.env.JWT_REFRESH_SECRET,  // Убрать дефолт!
  refreshExpiresIn: process.env.REFRESH_TOKEN_EXPIRES_IN || '24h',
}
```

---

## ⚠️ ВАЖНЫЕ УЛУЧШЕНИЯ (ближайшее время)

### 7. User Caching в Redis

**Проблема:** Каждый запрос с токеном делает запрос в БД (N+1).

**Решение:** Кешировать пользователя в Redis на 5 минут.

**Изменения в `jwt.strategy.ts`:**
```typescript
async validate(payload: any) {
  const cacheKey = `user:${payload.sub}`;

  // 1. Проверяем кеш
  const cached = await this.redisService.get(cacheKey);
  if (cached) {
    return JSON.parse(cached);
  }

  // 2. Загружаем из БД
  const user = await this.prisma.user.findUnique({
    where: { id: payload.sub },
    select: {
      id: true,
      email: true,
      username: true,
      avatar: true,
      createdAt: true,
    },
  });

  if (!user) {
    throw new UnauthorizedException('Пользователь не найден');
  }

  // 3. Сохраняем в кеш на 5 минут
  await this.redisService.setex(cacheKey, 300, JSON.stringify(user));

  return user;
}
```

**Инвалидация кеша при обновлении пользователя:**
```typescript
// В user.service.ts (будет создан позже)
async updateUser(userId: string, data: UpdateUserDto) {
  const user = await this.prisma.user.update({
    where: { id: userId },
    data,
  });

  // Инвалидируем кеш
  await this.redisService.del(`user:${userId}`);

  return user;
}
```

---

### 8. Session Management

**Решение:** Добавить модель `Session` для управления активными сессиями.

```prisma
// prisma/schema.prisma
model Session {
  id           String   @id @default(cuid())
  userId       String
  user         User     @relation(fields: [userId], references: [id], onDelete: Cascade)

  deviceId     String?  // fingerprint устройства
  deviceName   String?  // User Agent
  ipAddress    String?

  refreshToken String   @unique  // hashed
  expiresAt    DateTime

  lastSeenAt   DateTime @default(now())
  createdAt    DateTime @default(now())

  @@index([userId])
  @@index([expiresAt])
}
```

**GraphQL API для сессий:**
```graphql
extend type Query {
  mySessions: [Session!]!
}

extend type Mutation {
  revokeSession(sessionId: ID!): Boolean!
  revokeAllOtherSessions: Boolean!
}

type Session {
  id: ID!
  deviceId: String
  deviceName: String
  ipAddress: String
  lastSeenAt: DateTime!
  createdAt: DateTime!
  isCurrent: Boolean!
}
```

---

### 9. Email Verification

```prisma
// prisma/schema.prisma
model User {
  // ... существующие поля
  emailVerified     DateTime?
  emailVerifiedToken String?  @unique
}
```

```typescript
// auth.service.ts
async register(dto: RegisterDto) {
  const verificationToken = crypto.randomBytes(32).toString('hex');

  const user = await this.prisma.user.create({
    data: {
      // ...
      emailVerifiedToken: verificationToken,
    },
  });

  // Отправка email (отдельный модуль)
  // await this.emailService.sendVerificationEmail(user.email, verificationToken);

  return { /* ... */ };
}

@Mutation(() => Boolean)
@Public()
async verifyEmail(@Args('token') token: string) {
  await this.prisma.user.update({
    where: { emailVerifiedToken: token },
    data: {
      emailVerified: new Date(),
      emailVerifiedToken: null,
    },
  });
  return true;
}
```

---

### 10. Password Reset Flow

```prisma
// prisma/schema.prisma
model User {
  // ... существующие поля
  passwordResetToken     String?  @unique
  passwordResetExpires   DateTime?
}
```

```typescript
@Mutation(() => Boolean)
@Public()
async requestPasswordReset(@Args('email') email: string) {
  const user = await this.prisma.user.findUnique({ where: { email } });

  if (user) {
    const resetToken = crypto.randomBytes(32).toString('hex');
    await this.prisma.user.update({
      where: { id: user.id },
      data: {
        passwordResetToken: resetToken,
        passwordResetExpires: new Date(Date.now() + 3600000), // 1 час
      },
    });

    // await this.emailService.sendPasswordResetEmail(user.email, resetToken);
  }

  // Всегда возвращаем true (security best practice)
  return true;
}

@Mutation(() => Boolean)
@Public()
async resetPassword(
  @Args('token') token: string,
  @Args('newPassword') newPassword: string,
) {
  const user = await this.prisma.user.findFirst({
    where: {
      passwordResetToken: token,
      passwordResetExpires: { gte: new Date() },
    },
  });

  if (!user) {
    throw new BadRequestException('Invalid or expired reset token');
  }

  const hashedPassword = await bcrypt.hash(newPassword, 10);

  await this.prisma.user.update({
    where: { id: user.id },
    data: {
      password: hashedPassword,
      passwordResetToken: null,
      passwordResetExpires: null,
    },
  });

  return true;
}
```

---

### 11. Audit Log

```prisma
// prisma/schema.prisma
model AuthAuditLog {
  id          String   @id @default(cuid())
  userId      String?
  action      String   // login, logout, register, password_reset, etc.
  success     Boolean
  ipAddress   String?
  userAgent   String?
  errorMessage String?
  createdAt   DateTime @default(now())

  @@index([userId])
  @@index([action])
  @@index([createdAt])
}

// Добавить в User:
model User {
  // ...
  auditLogs AuthAuditLog[]
}
```

---

## 📋 ЧЕК-ЛИСТ РЕАЛИЗАЦИИ

### КРИТИЧНО (до продакшена)

- [ ] **1.1** Добавить модель `RefreshToken` в schema.prisma
- [ ] **1.2** Обновить `refreshTokens()` с хешированием и ротацией
- [ ] **1.3** Добавить методы blacklist в RedisService
- [ ] **1.4** Реализовать `logout()` с Redis blacklist
- [ ] **1.5** Обновить `JwtStrategy` с проверкой blacklist
- [ ] **1.6** Добавить `ThrottlerModule` в app.module.ts
- [ ] **1.7** Добавить `@Throttle()` декораторы на auth мутации
- [ ] **1.8** Добавить Timing Attack Protection в `login()`
- [ ] **1.9** Обернуть регистрацию в транзакцию
- [ ] **1.10** Добавить ENV validation в main.ts
- [ ] **1.11** Удалить дефолтные значения секретов из configuration.ts

### ВАЖНО (ближайшее время)

- [ ] **2.1** Добавить кеширование пользователя в `JwtStrategy`
- [ ] **2.2** Создать утилиту инвалидации кеша
- [ ] **2.3** Добавить модель `Session` в schema.prisma
- [ ] **2.4** Создать `getMySessions()` query
- [ ] **2.5** Создать `revokeSession()` mutation
- [ ] **2.6** Добавить email verification поля в User
- [ ] **2.7** Создать `verifyEmail()` mutation
- [ ] **2.8** Добавить password reset поля в User
- [ ] **2.9** Создать `requestPasswordReset()` и `resetPassword()` mutations
- [ ] **2.10** Добавить модель `AuthAuditLog`
- [ ] **2.11** Логировать auth события в audit

### ЖЕЛАТЕЛЬНО (по мере роста)

- [ ] **3.1** Device Fingerprinting
- [ ] **3.2** 2FA/MFA поддержка
- [ ] **3.3** Advanced anomaly detection

---

## 📁 СПИСОК ФАЙЛОВ ДЛЯ ИЗМЕНЕНИЙ

```
backend/src/
├── auth/
│   ├── auth.service.ts          # refreshTokens, logout, login, register
│   ├── auth.resolver.ts         # @Throttle декораторы, logout с токеном
│   ├── strategies/
│   │   └── jwt.strategy.ts      # blacklist check, кеширование
│   └── guards/
│       └── gql-auth.guard.ts    # blacklist check
├── redis/
│   └── redis.service.ts         # addToBlacklist, isBlacklisted
├── main.ts                      # ENV validation
├── config/
│   └── configuration.ts         # убрать дефолтные секреты
└── app.module.ts                # ThrottlerModule

backend/prisma/
└── schema.prisma                # RefreshToken, Session, AuthAuditLog
```

---

## 🔒 БЕЗОПАСНОСТЬ

| Критерий | До | После |
|----------|-----|-------|
| Refresh Token Management | ❌ Нет | ✅ Полный цикл |
| Logout | ❌ Заглушка | ✅ Redis blacklist |
| Rate Limiting | ❌ Нет | ✅ Throttler |
| Timing Attacks | ⚠️ Уязвим | ✅ Защищён |
| Transactions | ❌ Нет | ✅ Prisma $transaction |
| ENV Validation | ❌ Нет | ✅ Production checks |
| User Cache | ❌ Нет | ✅ Redis (5 мин TTL) |

---

## ССЫЛКИ

- [Проблемы безопасности JWT](https://datatracker.ietf.org/doc/html/rfc8725)
- [Rate Limiting Best Practices](https://cloud.google.com/architecture/rate-limiting-strategies-techniques)
- [Timing Attacks Prevention](https://codahale.com/a-lesson-in-timing-attacks/)
- [Redis Blacklist Pattern](https://redis.io/docs/manual/patterns/distributed-locks/)
