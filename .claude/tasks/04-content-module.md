# ФАЗА 4: Content Module

## Задача 4.1 - Content Module Setup

Создать модуль для статического контента игры (герои, карты, доски).

### Действия:
1. Создать ContentModule
2. Перенести данные героев из фронтенда:
   - Скопировать `src/core/data/heroes/` в `backend/src/content/data/`
   - Создать TypeScript интерфейсы для HeroDefinition
3. Создать ContentService с методами:
   - `getAllHeroes(): Hero[]`
   - `getHeroById(id: string): Hero`
   - `getHeroesBySet(set: string): Hero[]`
   - `getCardsByHero(heroId: string): Card[]`
   - `getAllBoards(): Board[]`
   - `getBoardById(id: string): Board`
   - `getCurrentVersion(): string`
   - `getContentDiff(oldVersion: string): ContentDiff`

### Файлы:
```
backend/src/content/
├── content.module.ts
├── content.service.ts
├── interfaces/
│   ├── hero-definition.interface.ts
│   ├── card-definition.interface.ts
│   └── board-definition.interface.ts
└── data/
    ├── heroes/
    │   ├── index.ts
    │   ├── arthur.ts
    │   ├── dracula.ts
    │   └── ...
    └── boards/
        ├── index.ts
        └── ...
```

### HeroDefinition Interface:
```typescript
interface HeroDefinition {
  id: string
  name: { en: string; ru: string }
  set: string
  health: number
  fighterType: 'HERO' | 'MINION' | 'HUGE'
  ability: HeroAbility
  deckCards: Array<{ cardId: string; count: number }>
  properties?: {
    hasSidekick?: boolean
    sidekickCount?: number
    // ...
  }
}
```

---

## Задача 4.2 - Content GraphQL API

Создать GraphQL резолвер для контента.

### Действия:
1. Создать ContentResolver с queries:
   - `heroes: [Hero!]!`
   - `hero(id: ID!): Hero!`
   - `cards(heroId: ID!): [Card!]!`
   - `boards: [Board!]!`
   - `board(id: ID!): Board!`
   - `contentVersion: String!`

### Файлы:
```
backend/src/content/
└── content.resolver.ts
```

### GraphQL Schema:
```graphql
type Hero {
  id: ID!
  name: HeroName!
  set: String!
  health: Int!
  fighterType: FighterType!
  ability: HeroAbility!
  cards: [Card!]!
}

type Card {
  id: ID!
  name: CardName!
  type: CardType!
  attackValue: Int
  defenseValue: Int
  effects: [CardEffect!]!
}

type Board {
  id: ID!
  name: BoardName!
  set: String!
  width: Int!
  height: Int!
  cells: [BoardCell!]!
}

extend type Query {
  heroes: [Hero!]!
  hero(id: ID!): Hero!
  cards(heroId: ID!): [Card!]!
  boards: [Board!]!
  board(id: ID!): Board!
  contentVersion: String!
}
```

---

## Задача 4.3 - Shared Types Package

Создать общий пакет типов для фронтенда и бэкенда.

### Действия:
1. Создать shared package для типов
2. Вынести общие типы:
   - GameState, PlayerState, FighterState
   - Card, Hero, Board
   - GamePhase, GameStatus
   - Position, Zone

### Варианты реализации:

**Вариант А**: Monorepo с `packages/shared/`
```
packages/
└── shared/
    ├── package.json
    ├── tsconfig.json
    └── src/
        ├── game-state.ts
        ├── player-state.ts
        ├── fighter-state.ts
        ├── enums.ts
        └── index.ts
```

**Вариант Б**: Отдельный npm пакет `@unmatched/shared`

### Основные типы:
```typescript
// enums.ts
export enum GameStatus {
  PENDING = 'PENDING',
  LOBBY = 'LOBBY',
  IN_PROGRESS = 'IN_PROGRESS',
  PAUSED = 'PAUSED',
  FINISHED = 'FINISHED',
  ABORTED = 'ABORTED',
}

export enum GamePhase {
  SETUP = 'SETUP',
  TURN_START = 'TURN_START',
  ACTION_MANEUVER = 'ACTION_MANEUVER',
  ACTION_ATTACK = 'ACTION_ATTACK',
  COMBAT = 'COMBAT',
  COMBAT_RESOLVE = 'COMBAT_RESOLVE',
  TURN_END = 'TURN_END',
}

// game-state.ts
export interface GameState {
  id: string
  players: PlayerState[]
  board: BoardState
  currentTurn: TurnState
  phase: GamePhase
  combatState: CombatState | null
  sequenceNumber: number
}
```

### Результат:
- Контент доступен через GraphQL
- Типы синхронизированы между фронтендом и бэкендом
