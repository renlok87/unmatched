# ФАЗА 5: Game Module - Часть 1 (CRUD + State)

## Задача 5.1 - Game Module Setup & CRUD

Создать базовый Game Module с CRUD операциями.

### Действия:
1. Обновить Prisma schema с моделями:
   - Game
   - GamePlayer
   - GameStatus (enum)
   - GameMode (enum)
   - GamePhase (enum)
2. Создать миграцию
3. Создать GameService с методами:
   - `createGame(dto: CreateGameDto): Promise<Game>`
   - `getGame(gameId: string): Promise<Game>`
   - `listGames(filters: GameFilters): Promise<Game[]>`
   - `joinGame(gameId: string, heroId: string): Promise<Game>`
   - `leaveGame(gameId: string): Promise<void>`
   - `startGame(gameId: string): Promise<Game>`

### Prisma Schema:
```prisma
enum GameStatus {
  PENDING
  LOBBY
  IN_PROGRESS
  PAUSED
  FINISHED
  ABORTED
}

enum GameMode {
  ONE_V_ONE
  TWO_V_TWO
  FREE_FOR_ALL
  VS_AI
}

model Game {
  id          String     @id @default(cuid())
  status      GameStatus @default(PENDING)
  mode        GameMode   @default(ONE_V_ONE)

  hostId      String
  host        User       @relation("Player1Games", fields: [hostId], references: [id])

  opponentId  String?
  opponent    User?      @relation("Player2Games", fields: [opponentId], references: [id])

  boardId     String
  boardState  Json?

  createdAt   DateTime   @default(now())
  updatedAt   DateTime   @updatedAt
  startedAt   DateTime?
  endedAt     DateTime?
  winnerId    String?
  version     Int        @default(0)

  players     GamePlayer[]
  state       GameState?
  actions     GameAction[]

  @@index([status])
  @@index([hostId, status])
  @@index([mode, status])
}

model GamePlayer {
  id          String   @id @default(cuid())
  gameId      String
  game        Game     @relation(fields: [gameId], references: [id], onDelete: Cascade)

  userId      String
  user        User     @relation(fields: [userId], references: [id])

  heroId      String?
  isReady     Boolean  @default(false)
  hasPassed   Boolean  @default(false)
  seatOrder   Int      @default(0)

  @@unique([gameId, userId])
  @@index([gameId])
}
```

### Файлы:
```
backend/src/game/
├── game.module.ts
├── game.service.ts
└── dto/
    ├── create-game.dto.ts
    ├── game-filters.dto.ts
    └── join-game.dto.ts
```

---

## Задача 5.2 - GameStateService

Создать сервис для управления состоянием игры.

### Действия:
1. Создать GameStateService с методами:
   - `saveState(gameId: string, state: GameState): Promise<void>`
   - `loadState(gameId: string): Promise<GameState>`
   - `cacheState(gameId: string, state: GameState): Promise<void>`
   - `getCachedState(gameId: string): Promise<GameState | null>`
   - `serialize(state: GameState, forPlayerId: string): SerializedGameState`
   - `deserialize(data: SerializedGameState): GameState`
   - `filterPrivateData(state: GameState, playerId: string): GameState`

### Ключевые моменты:
- Сериализация Map/классов в plain JSON
- Скрытие карт соперника
- Sequence number для optimistic updates
- Сжатие больших state (опционально)

### Файлы:
```
backend/src/game/
├── game-state.service.ts
└── serializers/
    ├── game-state.serializer.ts
    └── private-data.filter.ts
```

### GameStateService Interface:
```typescript
@Injectable()
class GameStateService {
  // Persistence
  async saveState(gameId: string, state: GameState): Promise<void>
  async loadState(gameId: string): Promise<GameState>

  // Cache
  async cacheState(gameId: string, state: GameState): Promise<void>
  async getCachedState(gameId: string): Promise<GameState | null>

  // Serialization
  serialize(state: GameState, forPlayerId: string): SerializedGameState
  deserialize(data: SerializedGameState): GameState

  // Privacy - скрытие карт соперника
  filterPrivateData(state: GameState, playerId: string): GameState
}
```

---

## Задача 5.3 - Game GraphQL API - Часть 1

Создать базовые GraphQL резолверы для игр.

### Действия:
1. Создать GameResolver:
   - Queries: `game(id: ID!)`, `myGames`, `availableGames`
   - Mutations: `createGame`, `joinGame`, `leaveGame`, `startGame`
2. Создать GraphQL типы: Game, GamePlayer

### Файлы:
```
backend/src/game/
├── game.resolver.ts
└── models/
    ├── game.model.ts
    └── game-player.model.ts
```

### GraphQL Schema:
```graphql
type Game {
  id: ID!
  status: GameStatus!
  players: [GamePlayer!]!
  currentTurn: Int
  phase: GamePhase
  createdAt: DateTime!
  startedAt: DateTime
  endedAt: DateTime
  winner: User
}

type GamePlayer {
  id: ID!
  user: User!
  hero: Hero
  isReady: Boolean!
  hasPassed: Boolean!
}

enum GameStatus {
  PENDING
  LOBBY
  IN_PROGRESS
  PAUSED
  FINISHED
  ABORTED
}

extend type Query {
  game(id: ID!): Game
  myGames(status: GameStatus, limit: Int): [Game!]!
  availableGames: [Game!]!
}

extend type Mutation {
  createGame(input: CreateGameInput!): Game!
  joinGame(gameId: ID!, heroId: ID!): Game!
  leaveGame(gameId: ID!): Boolean!
  startGame(gameId: ID!): Game!
}
```

### Результат:
- Можно создавать игры
- Можно присоединяться к играм
- Можно начинать игры
