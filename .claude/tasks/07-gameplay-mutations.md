# ФАЗА 7: Game Module - Часть 3 (Gameplay Mutations + Subscriptions)

## Задача 7.1 - Gameplay Mutations

Создать мутации для игровых действий.

### Действия:
1. Добавить мутации в GameResolver:
   - `maneuver(gameId, fighterId, cardId, path)` - перемещение + розыгрыш
   - `moveFighter(gameId, fighterId, x, y)` - простое перемещение
   - `attack(gameId, attackerId, cardId, targetId)` - объявление атаки
   - `playDefense(gameId, cardId)` - розыгрыш защиты (в ответ на атаку)
   - `resolveCombat(gameId)` - разрешение боя после защиты
   - `endTurn(gameId)` - конец хода
   - `pass(gameId)` - сброс карты + доп. действие
   - `toggleDoor(gameId, x, y)` - открыть/закрыть дверь

2. Обернуть каждую мутацию в distributed lock
3. Добавить валидацию перед выполнением

### Flow для attack мутации:
```
1. GqlAuthGuard проверяет токен
2. DistributedLockService.acquireGameLock()
3. GameRulesValidator.validateAttack()
   - Проверка: очередь атакующего?
   - Проверка: смежность (с учётом потайных ходов/дверей)
   - Проверка: карта может быть атакой
4. GameEngineService.attack()
   - Создаём состояние "ожидание защиты"
5. GameStateService.saveState() (DB + Redis)
6. PubSub.publish('attackInitiated', { gameId, attackerId })
7. DistributedLockService.releaseLock()
8. Return состояние (защищающийся видит, что может сыграть защиту)
```

### Flow для playDefense мутации:
```
1. GqlAuthGuard проверяет токен
2. DistributedLockService.acquireGameLock()
3. GameRulesValidator.validateDefense()
   - Проверка: игрок защищающийся?
   - Проверка: карта может быть защитой?
4. GameEngineService.playDefense()
   - Добавляем карту защиты в состояние боя
5. GameStateService.saveState()
6. PubSub.publish('defensePlayed', { gameId, defenseCard })
7. DistributedLockService.releaseLock()
```

### Flow для resolveCombat мутации:
```
1. GqlAuthGuard проверяет токен
2. DistributedLockService.acquireGameLock()
3. CombatResolver.resolveCombat()
   - Полный цикл разрешения боя (см. ФАЗУ 6.2)
4. Проверка условий победы/поражения
5. GameStateService.saveState()
6. PubSub.publish('combatResolved', { gameId, result })
7. DistributedLockService.releaseLock()
```

### Файлы:
```
backend/src/game/
└── game.resolver.ts (update)
```

### GraphQL Schema:
```graphql
extend type Mutation {
  # Игровые действия (все требуют блокировок)
  maneuver(
    gameId: ID!
    fighterId: ID!
    cardId: ID!
    path: [PositionInput!]!
  ): GameState!

  moveFighter(
    gameId: ID!
    fighterId: ID!
    x: Int!
    y: Int!
  ): GameState!

  attack(
    gameId: ID!
    attackerId: ID!
    cardId: ID!
    targetId: ID!
  ): GameState!

  playDefense(gameId: ID!, cardId: ID!): GameState!

  resolveCombat(gameId: ID!): GameState!

  endTurn(gameId: ID!): GameState!

  pass(gameId: ID!): GameState!

  # Действия с полями
  toggleDoor(gameId: ID!, x: Int!, y: Int!): GameState!
}
```

---

## Задача 7.2 - GraphQL Subscriptions

Создать подписки для real-time обновлений.

### Действия:
1. Настроить Redis Pub/Sub для subscriptions
2. Создать subscriptions:
   - `gameStateUpdated(gameId: ID!)` - полное обновление состояния
   - `attackInitiated(gameId: ID!)` - атака объявлена
   - `defensePlayed(gameId: ID!)` - защита сыграна
   - `combatResolved(gameId: ID!)` - бой разрешён
   - `playerJoined(gameId: ID!)`
   - `playerLeft(gameId: ID!)`
   - `turnChanged(gameId: ID!)` - смена хода

3. Добавить sequenceNumber для реконнекта
4. Добавить фильтрацию приватных данных (карты соперника)

### Файлы:
```
backend/src/game/
├── subscriptions/
│   └── game.subscriptions.ts
└── dto/
    └── game-event.dto.ts

backend/src/common/services/
└── pubsub.service.ts
```

### PubSubService:
```typescript
@Injectable()
class PubSubService {
  private pubSub: PubSub

  constructor(private redisService: RedisService) {
    // Redis Pub/Sub для масштабируемости
  }

  publish(channel: string, message: any): void
  async subscribe(channel: string, callback: (message: any) => void): Promise<void>
}
```

### Game Subscriptions:
```typescript
@Resolver('Game')
export class GameSubscriptions {
  @Subscription(() => GameState, {
    filter: (payload, variables) => {
      return payload.gameStateUpdated.gameId === variables.gameId
    },
  })
  gameStateUpdated(@Args('gameId') gameId: string): GameState {
    return
  }

  @Subscription(() => GameEvent, {
    filter: (payload, variables) => {
      return payload.attackInitiated.gameId === variables.gameId
    },
  })
  attackInitiated(@Args('gameId') gameId: string): GameEvent {
    return
  }

  // ... другие подписки
}
```

### GraphQL Schema:
```graphql
type GameEvent {
  type: GameEventType!
  sequenceNumber: Int!
  timestamp: DateTime!
  payload: JSON!
}

enum GameEventType {
  ATTACK_INITIATED
  DEFENSE_PLAYED
  COMBAT_RESOLVED
  TURN_CHANGED
  PLAYER_JOINED
  PLAYER_LEFT
  GAME_ENDED
}

extend type Subscription {
  gameStateUpdated(gameId: ID!): GameState!
  attackInitiated(gameId: ID!): GameEvent!
  defensePlayed(gameId: ID!): GameEvent!
  combatResolved(gameId: ID!): GameEvent!
  playerJoined(gameId: ID!): GamePlayer!
  playerLeft(gameId: ID!): ID!
  turnChanged(gameId: ID!): TurnState!
}
```

### Reconnection Flow:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Client Disconnect                                │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. Client сохраняет: lastSequenceNumber, currentPhase                 │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. Exponential backoff: 1s → 2s → 4s → 8s → max 30s                   │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. На успешном реконнекте:                                              │
│     GET /games/{id}?since={sequenceNumber}                              │
│     → Возвращает missed events + currentState                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Результат:
- Полноценный онлайн геймплей
- Механика защиты работает
- Подписки обновляются в реальном времени
- Reconnection работает корректно
