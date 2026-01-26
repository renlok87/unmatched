# ФАЗА 2: Auth Module

## Задача 2.1 - Auth Module Core

Создать базовый AuthModule с сервисами.

### Действия:
1. Создать AuthModule
2. Создать AuthService с методами:
   - `register(dto: RegisterDto): Promise<AuthResponse>`
   - `login(dto: LoginDto): Promise<AuthResponse>`
   - `refreshTokens(refreshToken: string): Promise<TokensPair>`
   - `logout(userId: string): Promise<void>`
   - `validateUser(email: string, password: string): Promise<User>`
3. Настроить bcrypt (10 rounds)
4. Создать DTO: RegisterDto, LoginDto, AuthResponseDto

### Файлы:
```
backend/src/auth/
├── auth.module.ts
├── auth.service.ts
└── dto/
    ├── register.dto.ts
    ├── login.dto.ts
    └── auth-response.dto.ts
```

### DTO Пример:
```typescript
export class RegisterDto {
  @IsEmail()
  email: string

  @MinLength(3)
  @MaxLength(20)
  @Matches(/^[a-zA-Z0-9_]+$/)
  username: string

  @MinLength(8)
  password: string
}

export class AuthResponseDto {
  user: User
  accessToken: string
  refreshToken: string
}
```

---

## Задача 2.2 - JWT Strategy & Guards

Создать стратегии Passport и Guards для защиты резолверов.

### Действия:
1. Создать JwtStrategy (Passport)
2. Создать RefreshTokenStrategy
3. Создать Guards:
   - `GqlAuthGuard` - для защищённых резолверов
   - `GqlPublicGuard` - для опциональной авторизации
   - `ThrottlerGuard` - для rate limiting
4. Создать декораторы:
   - `@CurrentUser()` - получить текущего пользователя
   - `@Public()` - отметить публичный резолвер

### Файлы:
```
backend/src/auth/
├── strategies/
│   ├── jwt.strategy.ts
│   └── refresh.strategy.ts
└── guards/
    └── gql-auth.guard.ts

backend/src/common/
├── decorators/
│   ├── current-user.decorator.ts
│   └── public.decorator.ts
└── guards/
    └── throttler.guard.ts
```

### JwtStrategy Пример:
```typescript
@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy) {
  constructor(private prisma: PrismaService) {
    super({
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: process.env.JWT_SECRET,
    })
  }

  async validate(payload: JwtPayload): Promise<User> {
    return this.prisma.user.findUnique({ where: { id: payload.sub } })
  }
}
```

---

## Задача 2.3 - Auth GraphQL API

Создать AuthResolver с GraphQL мутациями.

### Действия:
1. Создать AuthResolver с мутациями:
   - `register(input: RegisterInput!): AuthPayload!`
   - `login(input: LoginInput!): AuthPayload!`
   - `logout: Boolean!`
   - `refreshTokens(refreshToken: String!): AuthPayload!`
2. Создать GraphQL типы:
   - `AuthPayload`
   - `TokensPair`

### Файлы:
```
backend/src/auth/
└── auth.resolver.ts
```

### GraphQL Schema:
```graphql
type AuthPayload {
  accessToken: String!
  refreshToken: String!
  user: User!
}

type User {
  id: ID!
  email: String!
  username: String!
  avatar: String
  createdAt: DateTime!
}

extend type Mutation {
  register(input: RegisterInput!): AuthPayload!
  login(input: LoginInput!): AuthPayload!
  logout: Boolean!
  refreshTokens(refreshToken: String!): AuthPayload!
}
```

### Security:
- Access Token: 15 минут, хранится в памяти клиента
- Refresh Token: 7 дней, HttpOnly cookie + SameSite=Strict
- Rate Limiting: 5 попыток входа за 15 минут на IP

### Результат:
- Работающая регистрация, вход, refresh токенов
