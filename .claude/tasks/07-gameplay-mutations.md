# ФАЗЫ 7A-7F: Game Module - Gameplay Mutations + Subscriptions (Разбито)

## Архитектурные примечания

**Ключевые сервисы (уже реализованы):**
- `DistributedLockService` — распределённые блокировки на Redis
- `GameStateService` — управление состоянием (DB + Redis cache)
- `GameSubscriptionService` — Redis Pub/Sub для cross-instance подписок
- `GameRulesValidator` — валидация игровых правил
- `CombatResolverService` — разрешение боёв

**Новые сервисы (создаются по фазам):**
- Фаза 7A: Guards (GameStatusGuard, GamePlayerGuard, GameTurnGuard)
- Фаза 7B: Base Game Actions (без боевой системы)
- Фаза 7C: Combat System (attack, defense, resolution)
- Фаза 7D: Advanced Actions (maneuver, toggleDoor)
- Фаза 7E: GraphQL Subscriptions
- Фаза 7F: Reconnection & Edge Cases

---

# ФАЗА 7A: Guards Layer (Фундамент)

## Зачем отдельная фаза?

Guards — это **фундамент безопасности** всех игровых мутаций. Их нужно реализовать и протестировать **до** написания любой мутации.

### Задача 7A.1 - GameStatusGuard

Проверяет, что игра находится в нужном статусе.

```typescript
@Injectable()
export class GameStatusGuard implements CanActivate {
  constructor(private prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const gameId = this.getGameId(context);

    const game = await this.prisma.game.findUnique({
      where: { id: gameId },
      select: { status: true },
    });

    if (!game) {
      throw new NotFoundException('Game not found');
    }

    const allowedStatuses = this.getAllowedStatuses(context);
    if (!allowedStatuses.includes(game.status)) {
      throw new ForbiddenException(
        `Game must be ${allowedStatuses.join(' or ')}, current: ${game.status}`,
      );
    }

    return true;
  }

  private getGameId(context: ExecutionContext): string {
    // Извлекает gameId из args через reflector
  }

  private getAllowedStatuses(context: ExecutionContext): GameStatus[] {
    // Можно настраивать через decorator:
    // @UseGuards(GameStatusGuard)
    // @AllowedStatuses(GameStatus.IN_PROGRESS, GameStatus.PAUSED)
    return [GameStatus.IN_PROGRESS];
  }
}
```

**Edge Cases:**
| Ситуация | Действие |
|----------|----------|
| Game не существует | NotFoundException |
| Game.status = LOBBY | ForbiddenException |
| Game.status = COMPLETED | ForbiddenException |
| Game.status = ABORTED | ForbiddenException |
| Game.status = PAUSED | Разрешить для некоторых мутаций (чата, настройки) |

---

### Задача 7A.2 - GamePlayerGuard

Проверяет, что пользователь участвует в игре.

```typescript
@Injectable()
export class GamePlayerGuard implements CanActivate {
  constructor(private prisma: PrismaService) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const userId = this.getUserId(context);
    const gameId = this.getGameId(context);

    const player = await this.prisma.gamePlayer.findUnique({
      where: { gameId_userId: { gameId, userId } },
    });

    if (!player) {
      throw new ForbiddenException('You are not a player in this game');
    }

    // Аttach к request для использования в резолверах
    context.switchToHttp().getRequest().gamePlayer = player;

    return true;
  }
}
```

**Edge Cases:**
| Ситуация | Действие |
|----------|----------|
| Игрок не в игре | ForbiddenException |
| Игрок был, но removed (soft delete) | ForbiddenException |
| Игрок spectator (в будущем) | Разрешить чтение, запретить мутации |

---

### Задача 7A.3 - GameTurnGuard

Проверяет, что сейчас ход игрока.

```typescript
@Injectable()
export class GameTurnGuard implements CanActivate {
  constructor(
    private gameStateService: GameStateService,
  ) {}

  async canActivate(context: ExecutionContext): Promise<boolean> {
    const userId = this.getUserId(context);
    const gameId = this.getGameId(context);

    const state = await this.gameStateService.loadState(gameId);

    if (state.currentTurnPlayerId !== userId) {
      throw new BadRequestException(
        `Not your turn. Current: ${state.currentTurnPlayerId}, You: ${userId}`,
      );
    }

    // Attach для использования
    context.switchToHttp().getRequest().gameState = state;

    return true;
  }
}
```

**Edge Cases:**
| Ситуация | Действие |
|----------|----------|
| State не существует в кеше/БД | NotFoundException |
| State.sequenceNumber mismatch | ConflictException (concurrent modification) |
| Не ход игрока | BadRequestException с сообщением чей ход |
| Игрок покинул игру во время хода | ForbiddenException |

---

### Задача 7A.4 - Phase-Specific Guards

Гарды для конкретных фаз игры.

```typescript
@Injectable()
export class ManeuverPhaseGuard implements CanActivate {
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const state = this.getGameState(context);

    if (state.phase !== GamePhase.MANEUVER) {
      throw new BadRequestException(
        `Must be in MANEUVER phase. Current: ${state.phase}`,
      );
    }

    return true;
  }
}

@Injectable()
export class ActionPhaseGuard implements CanActivate {
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const state = this.getGameState(context);

    if (state.phase !== GamePhase.ACTION) {
      throw new BadRequestException(
        `Must be in ACTION phase. Current: ${state.phase}`,
      );
    }

    return true;
  }
}

@Injectable()
export class CombatPhaseGuard implements CanActivate {
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const state = this.getGameState(context);

    if (state.phase !== GamePhase.COMBAT) {
      throw new BadRequestException(
        `Must be in COMBAT phase. Current: ${state.phase}`,
      );
    }

    return true;
  }
}

@Injectable()
export class IsDefenderGuard implements CanActivate {
  async canActivate(context: ExecutionContext): Promise<boolean> {
    const userId = this.getUserId(context);
    const state = this.getGameState(context);

    const combat = state.combat;
    if (!combat) {
      throw new BadRequestException('No combat in progress');
    }

    // Защищающийся — это тот, кого атакуют
    const defenderId = this.getDefenderId(combat);
    if (defenderId !== userId) {
      throw new ForbiddenException('Only the defender can play defense cards');
    }

    return true;
  }
}
```

---

### Задача 7A.5 - Decorator для упрощения

Создать декоратор для комбинации гардов.

```typescript
export function UseGameGuards(
  ...guards: (
    | typeof GameStatusGuard
    | typeof GamePlayerGuard
    | typeof GameTurnGuard
  )[]
) {
  return UseGuards(GqlAuthGuard, ...guards);
}

// Использование:
@Mutation(() => GameState)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, GameTurnGuard)
async maneuver(@Args() dto: ManeuverDto): Promise<GameState> {
  // ...
}
```

---

### Файлы ФАЗЫ 7A:

```
backend/src/games/
└── guards/
    ├── game-status.guard.ts
    ├── game-player.guard.ts
    ├── game-turn.guard.ts
    ├── maneuver-phase.guard.ts
    ├── action-phase.guard.ts
    ├── combat-phase.guard.ts
    ├── is-defender.guard.ts
    ├── guards.module.ts
    └── decorators.ts
```

---

### Результат ФАЗЫ 7A:

- ✅ Guards реализованы и протестированы unit тестами
- ✅ Все edge cases покрыты
- ✅ Guards готовы к использованию в мутациях
- ✅ Декоратор `@UseGameGuards` упрощает код

---

# ФАЗА 7B: Base Game Actions (Простые мутации)

## Зачем отдельная фаза?

Начинаем с **простых мутаций**, чтобы отладить базовый flow:
- Guards → Lock → Validate → Execute → Save → Publish

### Задача 7B.1 - endTurn

Самая простая мутация — переход хода к следующему игроку.

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, GameTurnGuard)
async endTurn(@Args() dto: EndTurnDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация
    this.gameRulesValidator.validateEndTurn(state, userId);

    // Применить
    const newState = await this.endTurnService.endTurn(state, userId);

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    // Вернуть отфильтрованное состояние
    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для endTurn:**
| Ситуация | Действие |
|----------|----------|
| Игрок в combat phase | ForbiddenException (нужно завершить бой) |
| Игрок уже сбросил (pass) | BadRequestException |
| Последний игрок в round | Переход к новому раунду |
| Все fighter'ы defeats | Game over |

---

### Задача 7B.2 - pass

Сброс карты из руки + дополнительное действие.

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, GameTurnGuard)
async pass(@Args() dto: PassDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация: есть ли карты в руке?
    if (state.players[userId].hand.length === 0) {
      throw new BadRequestException('No cards to pass');
    }

    // Применить
    const newState = await this.passService.pass(state, userId, dto.cardId);

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для pass:**
| Ситуация | Действие |
|----------|----------|
| Рука пуста | BadRequestException |
| cardId не в руке | BadRequestException |
| Уже был pass в этом ходу | BadRequestException |
| Pass в combat phase | ForbiddenException |

---

### Задача 7B.3 - moveFighter

Простое перемещение без использования карты.

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, GameTurnGuard, ManeuverPhaseGuard)
async moveFighter(@Args() dto: MoveFighterDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация
    this.gameRulesValidator.validateMove(state, userId, dto);

    // Применить
    const newState = await this.movementService.moveFighter(
      state,
      dto.fighterId,
      { x: dto.x, y: dto.y },
    );

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для moveFighter:**
| Ситуация | Действие |
|----------|----------|
| Fighter не принадлежит игроку | ForbiddenException |
| Целевая клетка занята | BadRequestException |
| Целевая клетка — препятствие | BadRequestException |
| Целевая клетка — закрытая дверь | BadRequestException |
| Расстояние > allowedMovement | BadRequestException |
| Fighter has "immobilized" эффект | ForbiddenException |

---

### Файлы ФАЗЫ 7B:

```
backend/src/games/
├── resolvers/
│   └── base-game.resolver.ts    # endTurn, pass, moveFighter
├── dto/
│   ├── end-turn.dto.ts
│   ├── pass.dto.ts
│   └── move-fighter.dto.ts
└── services/
    ├── end-turn.service.ts       # Логика конца хода
    ├── pass.service.ts           # Логика pass
    └── movement.service.ts       # (или в game-engine)
```

---

### Результат ФАЗЫ 7B:

- ✅ endTurn, pass, moveFighter работают
- ✅ Базовый flow отлажен (Guards → Lock → Validate → Execute → Save → Publish)
- ✅ Edge cases покрыты
- ✅ Integration тесты для всех трёх мутаций

---

# ФАЗА 7C: Combat System (Боевая система)

## Зачем отдельная фаза?

Combat — самая **сложная система** с:
- Двухфазным взаимодействием (attack → defense → resolve)
- Timeout для auto-resolve
- BullMQ для фоновой обработки
- Сложной валидацией

### Задача 7C.1 - attack

Инициация атаки с переходом в combat phase.

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, GameTurnGuard, ActionPhaseGuard)
async attack(@Args() dto: AttackDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация
    await this.gameRulesValidator.validateAttack(state, userId, dto);

    // Применить
    const newState = await this.combatResolverService.initiateAttack(
      state,
      dto.attackerId,
      dto.cardId,
      dto.targetId,
    );

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    // Запланировать auto-resolve
    await this.combatTimeoutService.scheduleAutoResolve(dto.gameId, 30);

    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для attack:**
| Ситуация | Действие |
|----------|----------|
| Attacker не принадлежит игроку | ForbiddenException |
| Target не существует или не соперника | BadRequestException |
| Карта не в руке | BadRequestException |
| Карта не ATTACK типа | BadRequestException |
| Fighters не adjacent (учитывая secret passages) | BadRequestException |
| Target имеет "untargetable" эффект | BadRequestException |
| Уже есть combat в progress | ForbiddenException |
| Игрок уже использовал все атаки за ход | BadRequestException |

---

### Задача 7C.2 - playDefense

Игрок защищается от атаки.

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, CombatPhaseGuard, IsDefenderGuard)
async playDefense(@Args() dto: PlayDefenseDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация
    await this.gameRulesValidator.validateDefense(state, userId, dto);

    // Применить
    const newState = await this.combatResolverService.applyDefense(
      state,
      dto.cardId,
    );

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    // Отменить auto-resolve timeout
    await this.combatTimeoutService.cancelAutoResolve(dto.gameId);

    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для playDefense:**
| Ситуация | Действие |
|----------|----------|
| Нет combat в progress | BadRequestException |
| UserId не defender | ForbiddenException |
| Карта не в руке | BadRequestException |
| Карта не DEFENSE типа | BadRequestException |
| Defense timeout истёк | ConflictException (auto-resolve уже выполнен) |
| Уже сыграна defense карта | BadRequestException |
| Карда имеет "cannot defend" эффект | BadRequestException |

---

### Задача 7C.3 - resolveCombat

Разрешение боя (может быть вызвано атакующим или автоматически).

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, CombatPhaseGuard)
async resolveCombat(@Args() dto: ResolveCombatDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация
    if (!state.combat) {
      throw new BadRequestException('No combat to resolve');
    }

    // Применить
    const newState = await this.combatResolverService.resolveCombat(state);

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    // Отменить auto-resolve если был
    await this.combatTimeoutService.cancelAutoResolve(dto.gameId);

    // Проверить условия победы
    if (this.checkGameOver(newState)) {
      await this.finalizeGame(newState);
    }

    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для resolveCombat:**
| Ситуация | Действие |
|----------|----------|
| Нет combat в progress | BadRequestException |
| Damage >= defender health | Fighter defeated |
| Оба fighter'а имеют одинаковый damage | Оба получают damage |
| Special abilities (Beowulf reroll) | Применить эффект |
| Defender defeat → check win condition | Игра может закончиться |
| Attacker defeat → check win condition | Игра может закончиться |

---

### Задача 7C.4 - CombatTimeoutService

Сервис для автоматического разрешения боя через BullMQ.

```typescript
@Injectable()
export class CombatTimeoutService {
  private readonly QUEUE_NAME = 'combat-timeout';

  constructor(
    @InjectQueue(this.QUEUE_NAME) private queue: Queue,
    private gameStateService: GameStateService,
    private combatResolver: CombatResolverService,
    private distributedLockService: DistributedLockService,
  ) {}

  async scheduleAutoResolve(
    gameId: string,
    delaySeconds: number = 30,
  ): Promise<void> {
    await this.queue.add(
      'auto-resolve',
      { gameId },
      {
        delay: delaySeconds * 1000,
        jobId: `combat:${gameId}`,
      },
    );
  }

  async cancelAutoResolve(gameId: string): Promise<void> {
    const job = await this.queue.getJob(`combat:${gameId}`);
    if (job) {
      await job.remove();
    }
  }

  @Process('auto-resolve')
  async processAutoResolve(job: Job<{ gameId: string }>): Promise<void> {
    const { gameId } = job.data;

    // Acquire lock
    const lock = await this.distributedLockService.acquireLock(gameId, 5000);
    if (!lock) {
      // Retry later
      throw new RetryableError('Could not acquire lock');
    }

    try {
      const state = await this.gameStateService.loadState(gameId);

      // Проверяем, что все еще в combat phase
      if (state.phase !== GamePhase.COMBAT || !state.combat) {
        return; // Уже разрешили
      }

      // Auto-resolve с defense = null
      const resolvedState = await this.combatResolver.resolveCombat(
        state,
        null, // defenseCard = null
      );

      await this.gameStateService.saveState(gameId, resolvedState);

      // Проверить условия победы
      if (this.checkGameOver(resolvedState)) {
        await this.finalizeGame(resolvedState);
      }
    } finally {
      await this.distributedLockService.releaseLock(lock);
    }
  }
}
```

**Edge Cases для CombatTimeoutService:**
| Ситуация | Действие |
|----------|----------|
| Lock не получен | RetryableError (BullMQ retry) |
| GameState не существует | Игнорировать (игра удалена) |
| Combat уже разрешен | Игнорировать |
| Game aborted | Игнорировать |
| Redis restart при запланированном job | Восстановление не требуется (игрок сам resolution) |

---

### Файлы ФАЗЫ 7C:

```
backend/src/games/
├── resolvers/
│   └── combat.resolver.ts         # attack, playDefense, resolveCombat
├── dto/
│   ├── attack.dto.ts
│   ├── defense.dto.ts
│   └── resolve-combat.dto.ts
└── services/
    └── combat-timeout.service.ts

backend/src/game-engine/
└── services/
    └── combat-resolver.service.ts  # (уже должен быть)
```

---

### Результат ФАЗЫ 7C:

- ✅ attack, playDefense, resolveCombat работают
- ✅ CombatTimeoutService с BullMQ
- ✅ Auto-resolve при timeout
- ✅ Все edge cases покрыты
- ✅ Integration тесты для combat flow

---

# ФАЗА 7D: Advanced Actions (Сложные действия)

## Зачем отдельная фаза?

Сложные действия требуют:
- Pathfinding (A* алгоритм)
- Специальные эффекты героев
- Взаимодействие с features доски (двери)

### Задача 7D.1 - maneuver

Перемещение + розыгрыш карты манёвра.

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, GameTurnGuard, ManeuverPhaseGuard)
async maneuver(@Args() dto: ManeuverDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация
    await this.gameRulesValidator.validateManeuver(state, userId, dto);

    // Рассчитать путь (A*)
    const path = await this.movementService.calculatePath(
      state,
      dto.fighterId,
      dto.path,
    );

    // Применить движение
    let newState = await this.movementService.applyMovement(
      state,
      dto.fighterId,
      path,
    );

    // Применить эффект карты
    newState = await this.valueModifierService.applyCardEffects(
      newState,
      dto.cardId,
    );

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для maneuver:**
| Ситуация | Действие |
|----------|----------|
| Fighter не принадлежит игроку | ForbiddenException |
| Карта не MANEUVER типа | BadRequestException |
| Путь превышает movement points | BadRequestException |
| Путь проходит через препятствие | BadRequestException |
| Путь проходит через закрытую дверь | BadRequestException |
| Путь не валиден (не связные клетки) | BadRequestException |
| Fighter имеет "cannot move" эффект | ForbiddenException |
| Карта имеет "additional movement" эффект | Увеличить movement points |
| Yokai pathfinding (может двигаться по диагонали) | Использовать специальную логику |

---

### Задача 7D.2 - toggleDoor

Специальное способность Бьорна — открытие/закрытие дверей.

```typescript
@Mutation(() => GameMutationResult)
@UseGameGuards(GameStatusGuard, GamePlayerGuard, GameTurnGuard)
async toggleDoor(@Args() dto: ToggleDoorDto): Promise<GameMutationResult> {
  const userId = this.getUser();

  return this.distributedLockService.withGameLock(dto.gameId, async () => {
    const state = await this.gameStateService.loadState(dto.gameId);

    // Валидация
    await this.gameRulesValidator.validateToggleDoor(state, userId, dto);

    // Применить
    const newState = await this.boardService.toggleDoor(
      state,
      { x: dto.x, y: dto.y },
    );

    // Сохранить
    await this.gameStateService.saveState(dto.gameId, newState);

    return {
      state: this.gameStateService.filterPrivateData(newState, userId),
      sequenceNumber: newState.sequenceNumber,
      timestamp: new Date(),
    };
  });
}
```

**Edge Cases для toggleDoor:**
| Ситуация | Действие |
|----------|----------|
| Координаты не door | BadRequestException |
| Игрок не играет за Бьорна | ForbiddenException |
| Способность уже использована | BadRequestException |
| Дверь заблокирована другими эффектами | ForbiddenException |
| Fighter на двери при закрытии | BadRequestException |
| Дверь part of secret passage | Особая обработка |

---

### Файлы ФАЗЫ 7D:

```
backend/src/games/
├── resolvers/
│   └── advanced-actions.resolver.ts  # maneuver, toggleDoor
├── dto/
│   ├── maneuver.dto.ts
│   └── toggle-door.dto.ts
└── services/
    └── board.service.ts              # toggleDoor

backend/src/game-engine/
└── services/
    ├── movement.service.ts           # A* pathfinding
    └── value-modifier.service.ts     # Card effects
```

---

### Результат ФАЗЫ 7D:

- ✅ maneuver, toggleDoor работают
- ✅ A* pathfinding реализован
- ✅ Door interaction работает
- ✅ Все edge cases покрыты
- ✅ Integration тесты

---

# ФАЗА 7E: GraphQL Subscriptions

## Зачем отдельная фаза?

Subscriptions — это **отдельный слой** с:
- AsyncIterator API
- Redis Pub/Sub для cross-instance
- Фильтрацией приватных данных
- Reconnection логикой

### Задача 7E.1 - GameSubscriptionsResolver

```typescript
@Resolver('Game')
export class GameSubscriptionsResolver {
  constructor(
    private gameSubscriptionService: GameSubscriptionService,
    private gameStateService: GameStateService,
  ) {}

  @Subscription(() => GameUpdatePayload, {
    filter: (payload: GameUpdateEvent, variables: { gameId: string }) => {
      return payload.gameId === variables.gameId;
    },
    resolve: (value: GameUpdateEvent, args: any, context: GqlContext) => {
      const userId = context.req?.user?.userId;
      if (!userId) {
        throw new UnauthorizedException();
      }

      // Фильтруем приватные данные
      const filteredState = this.gameStateService.filterPrivateData(
        value.gameState,
        userId,
      );

      // Пропускаем устаревшие события
      if (args.since !== undefined && value.sequenceNumber <= args.since) {
        return null;
      }

      return {
        gameState: filteredState,
        sequenceNumber: value.sequenceNumber,
        eventType: value.eventType,
        timestamp: value.timestamp,
      };
    },
  })
  gameUpdates(
    @Args('gameId') gameId: string,
    @Args('since', { nullable: true }) since?: number,
  ): AsyncIterator<GameUpdatePayload> {
    return this.gameSubscriptionService.subscribeToGame(gameId);
  }
}
```

---

### Задача 7E.2 - Reconnection Support

Добавить `since` параметр для пропущенных событий.

```typescript
@Injectable()
export class GameSubscriptionService {
  async getMissedEvents(
    gameId: string,
    sinceSequence: number,
  ): Promise<GameEvent[]> {
    // Загрузить из GameStateHistory или GameAction
    const actions = await this.prisma.gameAction.findMany({
      where: {
        gameId,
        sequenceNumber: { gt: sinceSequence },
      },
      orderBy: { sequenceNumber: 'asc' },
    });

    return actions.map(a => ({
      type: a.actionType,
      gameId: a.gameId,
      sequenceNumber: a.sequenceNumber,
      timestamp: a.timestamp,
      payload: a.payload,
    }));
  }
}
```

**Edge Cases для subscriptions:**
| Ситуация | Действие |
|----------|----------|
| Клиент disconnected | Cleanup observer |
| Redis Pub/Sub failure | Fallback to local observers |
| Race condition: subscription до mutation response | sequenceNumber check |
| since > current sequence | Вернуть текущее состояние |
| Missed events более 1000 | Вернуть только последние 1000 (ограничение) |

---

### Файлы ФАЗЫ 7E:

```
backend/src/games/
├── resolvers/
│   └── game-subscriptions.resolver.ts
└── dto/
    └── game-event.dto.ts
```

---

### Результат ФАЗЫ 7E:

- ✅ gameUpdates subscription работает
- ✅ since параметр для reconnection
- ✅ Приватные данные фильтруются
- ✅ Cross-instance через Redis Pub/Sub
- ✅ Edge cases покрыты

---

# ФАЗА 7F: Edge Cases & Error Handling

## Зачем отдельная фаза？

После реализации всех мутаций нужно **систематически** обработать edge cases.

### Задача 7F.1 - Concurrent Modification

Обработка ситуации, когда два клиента одновременно модифицируют состояние.

```typescript
// В GameStateService:
async saveState(gameId: string, state: GameState): Promise<void> {
  try {
    await this.prisma.$transaction(async (tx) => {
      const current = await tx.gameState.findUnique({
        where: { gameId },
        select: { sequenceNumber: true },
      });

      if (current && current.sequenceNumber !== state.sequenceNumber - 1) {
        throw new ConflictException(
          `Concurrent modification. Expected seq: ${current.sequenceNumber}, got: ${state.sequenceNumber}`,
        );
      }

      await tx.gameState.create({
        data: {
          gameId,
          state: state as any,
          sequenceNumber: state.sequenceNumber,
        },
      });
    });
  } catch (e) {
    if (e instanceof ConflictException) {
      throw e;
    }
    throw new InternalServerErrorException('Failed to save state');
  }
}
```

---

### Задача 7F.2 - Game Abnormal States

Обработка нештатных ситуаций.

```typescript
@Injectable()
export class GameSanityService {
  // Проверка "зависших" игр
  @Cron('*/5 * * * *') // Каждые 5 минут
  async checkStuckGames(): Promise<void> {
    const stuckGames = await this.prisma.game.findMany({
      where: {
        status: GameStatus.IN_PROGRESS,
        updatedAt: {
          lt: new Date(Date.now() - 30 * 60 * 1000), // 30 минут без активности
        },
      },
    });

    for (const game of stuckGames) {
      await this.handleStuckGame(game.id);
    }
  }

  private async handleStuckGame(gameId: string): Promise<void> {
    // Попытаться auto-resolve combat
    const state = await this.gameStateService.loadState(gameId);

    if (state.phase === GamePhase.COMBAT && state.combat) {
      await this.combatResolverService.resolveCombat(state, null);
    } else {
      // Отметить игру как problem
      await this.prisma.game.update({
        where: { id: gameId },
        data: { status: GameStatus.PAUSED },
      });
    }
  }
}
```

---

### Задача 7F.3 - Player Disconnect During Game

Обработка отключения игрока.

```typescript
@Injectable()
export class GameDisconnectService {
  async handlePlayerDisconnect(userId: string): Promise<void> {
    // Найти активные игры игрока
    const activeGames = await this.prisma.game.findMany({
      where: {
        status: GameStatus.IN_PROGRESS,
        players: {
          some: { userId },
        },
      },
    });

    for (const game of activeGames) {
      await this.handleDisconnectInGame(game.id, userId);
    }
  }

  private async handleDisconnectInGame(
    gameId: string,
    userId: string,
  ): Promise<void> {
    const state = await this.gameStateService.loadState(gameId);

    // Отметить игрока как disconnected
    state.players[userId].disconnected = true;
    state.players[userId].disconnectedAt = new Date();

    await this.gameStateService.saveState(gameId, state);

    // Опубликовать событие
    await this.gameSubscriptionService.publishPlayerDisconnected(gameId, userId);

    // Если оба игрока disconnected → pause game
    const allDisconnected = Object.values(state.players).every(
      p => p.disconnected,
    );

    if (allDisconnected) {
      await this.prisma.game.update({
        where: { id: gameId },
        data: { status: GameStatus.PAUSED },
      });
    }
  }
}
```

---

### Задача 7F.4 - Recovery After Crash

Восстановление после краха.

```typescript
@Injectable()
export class GameRecoveryService {
  async onModuleInit(): Promise<void> {
    // При старте проверить незавершённые combat timeouts
    await this.recoverCombatTimeouts();
  }

  private async recoverCombatTimeouts(): Promise<void> {
    const inCombat = await this.prisma.gameState.findMany({
      where: {
        state: {
          path: ['phase'],
          equals: GamePhase.COMBAT,
        },
      },
      take: 100,
    });

    for (const gameState of inCombat) {
      const state = gameState.state as any;
      const combatAge = Date.now() - state.combat.createdAt;

      if (combatAge > 35000) { // 30 сек + 5 сек буфер
        // Auto-resolve
        await this.combatTimeoutService.processAutoResolve({
          data: { gameId: gameState.gameId },
        } as any);
      } else if (combatAge > 0) {
        // Reschedule
        const remainingDelay = 30000 - combatAge;
        await this.combatTimeoutService.scheduleAutoResolve(
          gameState.gameId,
          Math.ceil(remainingDelay / 1000),
        );
      }
    }
  }
}
```

---

### Полный список Edge Cases

| Категория | Edge Case | Решение |
|-----------|-----------|---------|
| **Concurrent** | Два клиента одновременно действуют | Optimistic locking with sequenceNumber |
| **Concurrent** | Lock не получен | ConflictException с retry hint |
| **Combat** | Timeout истёк до defense | Auto-resolve с null defense |
| **Combat** | Defense после timeout | ConflictException |
| **Movement** | Pathfinding не находит путь | BadRequestException с подсказкой |
| **Network** | Client disconnect mid-action | Rollback или continue на сервере |
| **Network** | Subscription reconnection | since параметр |
| **Game State** | Зависшая игра (>30 мин inactivity) | Auto-pause или auto-resolve |
| **Game State** | Все игроки disconnected | Auto-pause |
| **Game State** | Один игрок disconnected на 5 мин | Auto-defeat (опционально) |
| **Crash** | Redis restart | Потеря кеша, восстановление из БД |
| **Crash** | Server restart с active combat | Recovery в onModuleInit |
| **Validation** | Invalid card ID | BadRequestException |
| **Validation** | Fighter не существует | NotFoundException |
| **Validation** | Не тот ход | BadRequestException с чей ход указан |
| **Security** | Игрок пытается действовать за другого | ForbiddenException |
| **Security** | Spectator пытается сделать мутацию | ForbiddenException |

---

### Файлы ФАЗЫ 7F:

```
backend/src/games/
├── services/
│   ├── game-sanity.service.ts
│   ├── game-disconnect.service.ts
│   └── game-recovery.service.ts
└── exceptions/
    └── game-exceptions.ts
```

---

### Результат ФАЗЫ 7F:

- ✅ Все edge cases обработаны
- ✅ Sanity checks для зависших игр
- ✅ Recovery после краша
- ✅ Disconnect handling
- ✅ Tests для всех edge cases

---

# Итоговый чеклист ФАЗ 7A-7F

```
ФАЗА 7A: Guards Layer
├── GameStatusGuard
├── GamePlayerGuard
├── GameTurnGuard
├── ManeuverPhaseGuard
├── ActionPhaseGuard
├── CombatPhaseGuard
├── IsDefenderGuard
└── @UseGameGuards decorator

ФАЗА 7B: Base Game Actions
├── endTurn mutation
├── pass mutation
├── moveFighter mutation
└── Base flow отлажен

ФАЗА 7C: Combat System
├── attack mutation
├── playDefense mutation
├── resolveCombat mutation
├── CombatTimeoutService (BullMQ)
├── Auto-resolve на timeout
└── Combat edge cases

ФАЗА 7D: Advanced Actions
├── maneuver mutation (с A* pathfinding)
├── toggleDoor mutation (Bjorn ability)
└── Special abilities handling

ФАЗА 7E: GraphQL Subscriptions
├── gameUpdates subscription
├── Redis Pub/Sub cross-instance
├── Private data filtering
├── since параметр для reconnection
└── Subscription edge cases

ФАЗЫ 7A-7E собраны и протестированы

ФАЗА 7F: Edge Cases & Error Handling
├── Concurrent modification handling
├── Game sanity checks
├── Player disconnect handling
├── Recovery after crash
└── Полный список edge cases покрыт тестами
```

---

# Преимущества разбивки на фазы

1. **Incremental Testing** — каждая фаза тестируется отдельно
2. **Parallel Development** — разные разработчики могут работать на разных фазах
3. **Easier Debugging** — проблемы изолированы
4. **Clear Milestones** — каждый этап имеет измеримый результат
5. **Risk Mitigation** — проблемы обнаруживаются рано
