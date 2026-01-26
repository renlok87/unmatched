# ФАЗА 1: Core Infrastructure

## Задача 1.1 - NestJS Project Setup

Инициализировать NestJS проект и настроить базовую конфигурацию.

### Действия:
1. Инициализировать проект: `nest new backend` или вручную
2. Настроить `tsconfig.json` с paths для чистых импортов
3. Установить зависимости:
   - `@nestjs/config`
   - `@nestjs/throttler`
   - `@nestjs/passport`
   - `@nestjs/jwt`
   - `passport`
   - `passport-jwt`
   - `bcrypt`
   - `class-validator`
   - `class-transformer`
4. Настроить ConfigModule с validation schema
5. Создать базовые DTO: BaseDto, PaginationDto

### Файлы:
```
backend/src/
├── config/
│   ├── configuration.ts
│   └── validation.schema.ts
├── common/
│   └── dto/
│       ├── base.dto.ts
│       └── pagination.dto.ts
├── app.module.ts
└── main.ts
```

---

## Задача 1.2 - Prisma + PostgreSQL Setup

Настроить Prisma ORM с PostgreSQL.

### Действия:
1. Установить: `@prisma/client`, `prisma`
2. Создать начальный `schema.prisma` с моделями:
   - User
   - UserStats
   - UserSettings
3. Настроить PrismaModule в NestJS
4. Создать миграцию: `prisma migrate dev --name init`
5. Создать PrismaService с soft delete middleware

### Prisma Schema:
```prisma
model User {
  id        String   @id @default(cuid())
  email     String   @unique
  username  String   @unique
  password  String
  avatar    String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt

  stats     UserStats?
  settings  UserSettings?

  @@index([email])
  @@index([username])
}
```

### Файлы:
```
backend/
├── prisma/
│   └── schema.prisma
└── src/
    └── database/
        ├── prisma.service.ts
        └── prisma.module.ts
```

---

## Задача 1.3 - Redis Setup

Настроить Redis для кэширования и блокировок.

### Действия:
1. Установить: `ioredis`
2. Создать RedisModule с health check
3. Создать RedisService с методами:
   - `get`, `set`, `del`, `exists`
   - `setex` (с TTL)
   - `publish`, `subscribe` (pub/sub)
   - `acquireLock`, `releaseLock` (distributed locks)

### Файлы:
```
backend/src/redis/
├── redis.module.ts
├── redis.service.ts
└── interfaces/
    └── redis-lock.interface.ts
```

### RedisService Interface:
```typescript
class RedisService {
  get<T>(key: string): Promise<T | null>
  set(key: string, value: any): Promise<void>
  del(key: string): Promise<void>
  exists(key: string): Promise<boolean>
  setex(key: string, seconds: number, value: any): Promise<void>

  publish(channel: string, message: any): Promise<void>
  subscribe(channel: string, callback: (message: any) => void): Promise<void>

  acquireLock(key: string, ttl: number): Promise<Lock | null>
  releaseLock(lock: Lock): Promise<void>
}
```

---

## Задача 1.4 - GraphQL Apollo Server Setup

Настроить GraphQL с Apollo Server в code-first режиме.

### Действия:
1. Установить: `@nestjs/graphql`, `@apollo/server`, `graphql`
2. Настроить GraphQLModule в code-first режиме
3. Настроить Apollo Server с playground
4. Создать скаляры: DateTime, JSON
5. Настроить CORS для GraphQL playground

### Файлы:
```
backend/src/graphql/
├── graphql.module.ts
├── scalars/
│   ├── date-time.scalar.ts
│   └── json.scalar.ts
```

### Скаляр DateTime:
```typescript
export class DateTimeScalar implements CustomScalar<number, Date> {
  description = 'Date time scalar'

  parseValue(value: number): Date {
    return new Date(value)
  }

  serialize(value: Date): number {
    return value.getTime()
  }
}
```

### Результат:
- Работающий GraphQL playground на `http://localhost:3000/graphql`
- Health checks работают
