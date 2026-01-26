# ФАЗА 3: Users Module

## Задача 3.1 - Users Module

Создать модуль для управления пользователями.

### Действия:
1. Создать UsersModule
2. Создать UsersService с методами:
   - `findById(id: string): Promise<User>`
   - `findByEmail(email: string): Promise<User>`
   - `updateProfile(userId: string, dto: UpdateProfileDto): Promise<User>`
   - `changePassword(userId: string, dto: ChangePasswordDto): Promise<void>`
   - `deleteAccount(userId: string): Promise<void>`
3. Создать ProfileService:
   - `uploadAvatar(userId: string, file: File): Promise<string>`
   - `updateSettings(userId: string, dto: SettingsDto): Promise<UserSettings>`

### Файлы:
```
backend/src/users/
├── users.module.ts
├── users.service.ts
├── profile.service.ts
└── dto/
    ├── update-profile.dto.ts
    ├── change-password.dto.ts
    └── settings.dto.ts
```

---

## Задача 3.2 - User Stats Module

Создать модуль для статистики и ELO рейтинга.

### Действия:
1. Создать UserStatsService:
   - `getStats(userId: string): Promise<UserStats>`
   - `updateStatsAfterGame(gameId: string, userId: string): Promise<void>`
   - `getLeaderboard(options: LeaderboardOptions): Promise<LeaderboardEntry[]>`
2. Создать RatingService:
   - `calculateNewRatings(winnerElo: number, loserElo: number): {winner: number, loser: number}`
   - `getPlayerRating(userId: string, heroId?: string): Promise<number>`

### ELO Formula:
```typescript
// Expected score
Ea = 1 / (1 + 10^((Rb - Ra) / 400))

// New rating
Ra' = Ra + K * (Sa - Ea)

// K = 32 для стандартных игр
```

### Файлы:
```
backend/src/users/
├── user-stats.service.ts
├── rating.service.ts
└── dto/
    └── leaderboard-options.dto.ts
```

---

## Задача 3.3 - Users GraphQL API

Создать GraphQL резолверы для пользователей.

### Действия:
1. Создать UsersResolver:
   - Queries: `me`, `user(id: ID!)`, `myStats`
   - Mutations: `updateProfile`, `changePassword`, `deleteAccount`
2. Создать LeaderboardResolver:
   - Query: `leaderboard(hero, timeFrame, limit)`

### Файлы:
```
backend/src/users/
├── users.resolver.ts
└── leaderboard.resolver.ts
```

### GraphQL Schema:
```graphql
type User {
  id: ID!
  email: String!
  username: String!
  avatar: String
  createdAt: DateTime!
  settings: UserSettings
}

type UserStats {
  userId: ID!
  gamesPlayed: Int!
  gamesWon: Int!
  gamesLost: Int!
  winRate: Float!
  currentElo: Int!
  peakElo: Int!
  favoriteHero: Hero
}

type LeaderboardEntry {
  rank: Int!
  user: User!
  elo: Int!
  gamesWon: Int!
  gamesPlayed: Int!
}

extend type Query {
  me: User
  user(id: ID!): User
  myStats: UserStats
  leaderboard(hero: String, timeFrame: TimeFrame, limit: Int): [LeaderboardEntry!]!
}

extend type Mutation {
  updateProfile(input: UpdateProfileInput!): User!
  changePassword(input: ChangePasswordInput!): Boolean!
  deleteAccount: Boolean!
}
```

### Результат:
- Полностью рабочий users module
