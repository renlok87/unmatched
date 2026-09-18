/**
 * Game Action Executor Service Tests
 *
 * Unit тесты для сервиса выполнения игровых действий.
 */

import { Test, TestingModule } from '@nestjs/testing';
import { GameActionExecutorService, ActionResult, ActionContext } from './game-action-executor.service';
import { GameRulesValidator, ValidationResult } from '../validators/game-rules.validator';
import { CombatResolverService, CombatResult } from '../engine/combat-resolver.service';
import { MovementService, MovementResult } from '../engine/movement.service';
import { ValueModifierService } from '../engine/value-modifier.service';
import { AdjacencyService } from '../engine/adjacency.service';
import { MetricsService } from '../../metrics/metrics.service';
import { DeckManagementService } from './deck-management.service';
import { CardEffectExecutorService } from '../effects/card-effect-executor.service';
import { HeroAbilityRegistry } from '../abilities/hero-ability-registry';
import { GamePhase } from '../../games/dto';
import { getActionsRemaining } from '../models';
import type { GameState } from '../../games/game-state.service';
import {
  ManeuverDto,
  MoveFighterDto,
  AttackDto,
  EndTurnDto,
  PassDto,
  ToggleDoorDto,
  SetStanceDto,
} from '../../games/dto/gameplay.dto';

describe('GameActionExecutorService', () => {
  let service: GameActionExecutorService;
  let rulesValidator: GameRulesValidator;
  let combatResolver: CombatResolverService;
  let movementService: MovementService;
  let valueModifier: ValueModifierService;
  let adjacencyService: AdjacencyService;

  /**
   * Создаёт тестовое состояние игры
   */
  const createMockGameState = (overrides?: Partial<GameState>): GameState => ({
    gameId: 'test-game-1',
    sequenceNumber: 1,
    phase: GamePhase.TURN_START,
    turnCount: 1,
    currentTurnPlayerId: 'player1',
    players: [
      {
        userId: 'player1',
        heroId: 'ms-marvel',
        health: 14,
        maxHealth: 14,
        fighterIds: ['fighter1'],
        isAlive: true,
      },
      {
        userId: 'player2',
        heroId: 'daredevil',
        health: 17,
        maxHealth: 17,
        fighterIds: ['fighter2'],
        isAlive: true,
      },
    ],
    fighters: [
      {
        id: 'fighter1',
        ownerId: 'player1',
        heroId: 'ms-marvel',
        name: 'Ms. Marvel',
        type: 'hero' as any,
        health: 14,
        maxHealth: 14,
        position: { x: 5, y: 5 },
        effects: [],
        hasSidekick: false,
      },
      {
        id: 'fighter2',
        ownerId: 'player2',
        heroId: 'daredevil',
        name: 'Daredevil',
        type: 'hero' as any,
        health: 17,
        maxHealth: 17,
        position: { x: 6, y: 5 },
        effects: [],
        hasSidekick: false,
      },
    ],
    decks: {},
    discardPiles: {},
    handZones: {
      player1: { cards: [], maxSize: 5 },
      player2: { cards: [], maxSize: 5 },
    },
    boardState: {
      width: 20,
      height: 20,
      cells: Array(20).fill(null).map(() =>
        Array(20).fill(null).map(() => ({ type: 'normal' as const, x: 0, y: 0 })),
      ) as any,
      doors: {} as any,
      fog: {} as any,
      tokens: {} as any,
    } as any,
    metadata: {
      lastActionAt: new Date(),
      lastActionBy: 'player1',
      version: 1,
    },
    ...overrides,
  }) as any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameActionExecutorService,
        {
          provide: GameRulesValidator,
          useValue: {
            validateManeuver: jest.fn().mockReturnValue({ valid: true }),
            validateMovement: jest.fn().mockReturnValue({ valid: true }),
            validateAttackWithParams: jest.fn().mockReturnValue({ valid: true }),
            validateDefense: jest.fn().mockReturnValue({ valid: true }),
            validateEndTurn: jest.fn().mockReturnValue({ valid: true }),
            validatePass: jest.fn().mockReturnValue({ valid: true }),
            validateToggleDoor: jest.fn().mockReturnValue({ valid: true }),
            canPlayerAct: jest.fn().mockReturnValue({ valid: true }),
            checkGameEnd: jest.fn().mockReturnValue({ ended: false }),
          },
        },
        {
          provide: CombatResolverService,
          useValue: {
            resolveCombat: jest.fn().mockResolvedValue({
              attackerDamage: 0,
              defenderDamage: 3,
              attackerEffectsApplied: [],
              defenderEffectsApplied: [],
              nextState: createMockGameState(),
            } as any),
            getHeroCombatModifiers: jest
              .fn()
              .mockReturnValue({ attackModifier: 0, defenseModifier: 0 }),
          },
        },
        {
          provide: MovementService,
          useValue: {
            executeMovement: jest.fn().mockResolvedValue({
              success: true,
              path: [{ x: 5, y: 5 }, { x: 5, y: 6 }],
              nextState: createMockGameState({
                fighters: [
                  {
                    id: 'fighter1',
                    ownerId: 'player1',
                    heroId: 'ms-marvel',
                    name: 'Ms. Marvel',
                    type: 'hero' as any,
                    health: 14,
                    maxHealth: 14,
                    position: { x: 5, y: 6 },
                    effects: [],
                    hasSidekick: false,
                  },
                ],
              }),
            } as any),
          },
        },
        {
          provide: ValueModifierService,
          useValue: {
            applyCardEffects: jest.fn().mockResolvedValue(createMockGameState()),
          },
        },
        {
          provide: AdjacencyService,
          useValue: {
            isAdjacent: jest.fn().mockResolvedValue(true),
            isInSameZone: jest.fn().mockReturnValue(false),
            manhattanDistance: jest.fn().mockReturnValue(1),
          },
        },
        {
          // Passthrough-моки: метрики просто исполняют переданный колбэк
          provide: MetricsService,
          useValue: {
            measureServiceDuration: jest.fn((_n: string, _c: string, fn: () => any) => fn()),
            measureValidation: jest.fn((_n: string, fn: () => any) => fn()),
            measureCombat: jest.fn((_a: string, _d: string, fn: () => any) => fn()),
            incrementGameAction: jest.fn(),
            incrementError: jest.fn(),
          },
        },
        {
          provide: DeckManagementService,
          useValue: {
            // По умолчанию state не меняется — тестам важна логика executor'а
            drawCards: jest.fn().mockImplementation((state: GameState) => Promise.resolve(state)),
            discardCard: jest.fn().mockImplementation((state: GameState) => Promise.resolve(state)),
            discardRandomCard: jest.fn().mockImplementation((state: GameState) => Promise.resolve(state)),
          },
        },
        {
          provide: CardEffectExecutorService,
          useValue: {
            executeOnPlayEffects: jest.fn().mockImplementation((state: GameState) =>
              Promise.resolve({ state, appliedEffects: [], manualEffects: [] }),
            ),
            // Passthrough-пайплайн боя: значения из combatInfo, без эффектов
            executeRevealEffects: jest.fn().mockImplementation((state: GameState) =>
              Promise.resolve({
                state,
                appliedEffects: [],
                manualEffects: [],
                attackerCardCancelled: false,
                defenderCardCancelled: false,
              }),
            ),
            executeCombatEffects: jest
              .fn()
              .mockImplementation((state: GameState, _a: unknown, _d: unknown, combat: any) =>
                Promise.resolve({
                  state,
                  finalAttack: combat.attackValue,
                  finalDefense: combat.defenseValue,
                  preventDamageToAttacker: false,
                  preventDamageToDefender: false,
                  appliedEffects: [],
                  manualEffects: [],
                }),
              ),
            executeAfterCombatEffects: jest.fn().mockImplementation((state: GameState) =>
              Promise.resolve({ state, appliedEffects: [], manualEffects: [] }),
            ),
          },
        },
        {
          provide: HeroAbilityRegistry,
          useValue: {
            getAny: jest.fn().mockReturnValue(undefined),
            // Extended-range gate в executeAttack — по умолчанию нет способности
            // (false), обычные melee/ranged-правила сохраняются
            canAttackAtRange: jest.fn().mockReturnValue(false),
            // TURN_START-хук в advanceTurn (TASK A) — passthrough no-op:
            // герои тестов без onTurnStart возвращают state без изменений
            triggerOnTurnStartExtended: jest
              .fn()
              .mockImplementation((_h: string, state: GameState) => Promise.resolve(state)),
            // TURN_END-хук в advanceTurn (abilities-wiring) — passthrough no-op:
            // герои тестов без onTurnEnd возвращают state без изменений
            triggerOnTurnEndExtended: jest
              .fn()
              .mockImplementation((_h: string, state: GameState) => Promise.resolve(state)),
            // AFTER-COMBAT хук в executeResolveCombat (TASK) — passthrough no-op:
            // герои тестов без onAfterCombat возвращают state без изменений
            triggerOnAfterCombat: jest
              .fn()
              .mockImplementation((_h: string, state: GameState) => Promise.resolve(state)),
            // STATEFUL combat modifiers в executeResolveCombat — нет хука → []
            getStatefulCombatModifiers: jest.fn().mockReturnValue([]),
            // AURA combat modifiers в executeResolveCombat — нет ауры → []
            getAuraCombatModifiers: jest.fn().mockReturnValue([]),
            // РЕАКТИВНЫЙ on-move хук в applyMoveReactions — passthrough no-op:
            // герои тестов без onFighterMoved возвращают state без изменений
            triggerOnFighterMoved: jest
              .fn()
              .mockImplementation((state: GameState) => Promise.resolve(state)),
            getHeroCombatModifiers: jest
              .fn()
              .mockReturnValue({ attackModifier: 0, defenseModifier: 0 }),
            // STANCE: список стоек героя для валидации executeSetStance.
            // По умолчанию у player1 (ms-marvel) нет стоек → []; тесты setStance
            // переопределяют мок под конкретного stance-героя.
            getStances: jest.fn().mockReturnValue([]),
          },
        },
      ],
    }).compile();

    service = module.get<GameActionExecutorService>(GameActionExecutorService);
    rulesValidator = module.get<GameRulesValidator>(GameRulesValidator);
    combatResolver = module.get<CombatResolverService>(CombatResolverService);
    movementService = module.get<MovementService>(MovementService);
    valueModifier = module.get<ValueModifierService>(ValueModifierService);
    adjacencyService = module.get<AdjacencyService>(AdjacencyService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('createInitialState', () => {
    it('should create initial game state', async () => {
      const params = {
        gameId: 'game-1',
        players: [
          { userId: 'player1', heroId: 'hero1', health: 10, maxHealth: 10 },
          { userId: 'player2', heroId: 'hero2', health: 10, maxHealth: 10 },
        ],
        boardId: 'board-1',
      };

      const state = await service.createInitialState(params);

      expect(state.gameId).toBe('game-1');
      expect(state.phase).toBe(GamePhase.TURN_START);
      expect(state.currentTurnPlayerId).toBe('player1');
      expect(state.players).toHaveLength(2);
      expect(state.fighters).toHaveLength(0);
      expect((state.boardState as any).width).toBe(20);
      expect((state.boardState as any).height).toBe(20);
    });

    it('should set correct initial phase', async () => {
      const params = {
        gameId: 'game-1',
        players: [{ userId: 'player1', heroId: 'hero1', health: 10, maxHealth: 10 }],
        boardId: 'board-1',
      };

      const state = await service.createInitialState(params);

      expect(state.phase).toBe(GamePhase.TURN_START);
    });
  });

  describe('executeManeuver', () => {
    it('should execute maneuver successfully', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        handZones: {
          player1: {
            cards: [{ id: 'card1', cardId: 'card1', cardType: 'ATTACK' as any, value: 2 } as any],
            maxSize: 5,
          },
          player2: { cards: [], maxSize: 5 },
        },
      });

      const dto: ManeuverDto = {
        gameId: 'test-game-1',
        fighterId: 'fighter1',
        cardId: 'card1',
        path: [{ x: 5, y: 5 }, { x: 5, y: 6 }],
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeManeuver(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState).toBeDefined();
      expect(result.metadata?.action).toBe('maneuver');
      expect(rulesValidator.validateManeuver).toHaveBeenCalledWith(
        state as any,
        'fighter1',
        'card1',
        dto.path,
        'player1',
      );
    });

    it('should return error when validation fails', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: ManeuverDto = {
        gameId: 'test-game-1',
        fighterId: 'fighter1',
        cardId: 'card1',
        path: [{ x: 5, y: 5 }, { x: 5, y: 6 }],
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(rulesValidator, 'validateManeuver').mockReturnValue({
        valid: false,
        error: 'Fighter not found',
        code: 'FIGHTER_NOT_FOUND',
      });

      const result = await service.executeManeuver(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Fighter not found');
    });

    it('отказ: конечная клетка пути занята другим бойцом (C3 — движение без movementService)', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: ManeuverDto = {
        gameId: 'test-game-1',
        fighterId: 'fighter1',
        // fighter2 стоит на (6,5) — конечная клетка занята
        path: [{ x: 6, y: 5 }],
      } as ManeuverDto;

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeManeuver(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toContain('занята');
    });
  });

  describe('executeMoveFighter', () => {
    it('should execute move fighter successfully', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: MoveFighterDto = {
        gameId: 'test-game-1',
        fighterId: 'fighter1',
        x: 5,
        y: 6,
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeMoveFighter(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState).toBeDefined();
      expect(result.metadata?.action).toBe('moveFighter');
      expect(movementService.executeMovement).toHaveBeenCalledWith(
        state as any,
        'fighter1',
        [{ x: 5, y: 6 }],
      );
    });

    it('should return error when validation fails', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: MoveFighterDto = {
        gameId: 'test-game-1',
        fighterId: 'fighter1',
        x: 5,
        y: 6,
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(rulesValidator, 'validateMovement').mockReturnValue({
        valid: false,
        error: 'Not your fighter',
        code: 'NOT_YOUR_FIGHTER',
      });

      const result = await service.executeMoveFighter(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Not your fighter');
    });
  });

  describe('executeAttack', () => {
    it('should execute attack successfully', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_ATTACK,
        handZones: {
          player1: {
            cards: [{ id: 'card1', cardId: 'card1', cardType: 'ATTACK' as any, value: 3 } as any],
            maxSize: 5,
          },
          player2: { cards: [], maxSize: 5 },
        },
      });

      const dto: AttackDto = {
        gameId: 'test-game-1',
        attackerId: 'fighter1',
        targetId: 'fighter2',
        cardId: 'card1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeAttack(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState).toBeDefined();
      expect(result.metadata?.action).toBe('attack');
      expect(result.gameState?.phase).toBe(GamePhase.COMBAT);
    });

    it('should return error when validation fails', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_ATTACK,
      });

      const dto: AttackDto = {
        gameId: 'test-game-1',
        attackerId: 'fighter1',
        targetId: 'fighter2',
        cardId: 'card1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(rulesValidator, 'validateAttackWithParams').mockReturnValue({
        valid: false,
        error: 'Card not in hand',
        code: 'CARD_NOT_IN_HAND',
      });

      const result = await service.executeAttack(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Card not in hand');
    });

    it('should check adjacency before attacking', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_ATTACK,
        handZones: {
          player1: {
            cards: [{ id: 'card1', cardId: 'card1', cardType: 'ATTACK' as any, value: 3 } as any],
            maxSize: 5,
          },
          player2: { cards: [], maxSize: 5 },
        },
      });

      const dto: AttackDto = {
        gameId: 'test-game-1',
        attackerId: 'fighter1',
        targetId: 'fighter2',
        cardId: 'card1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(adjacencyService, 'isAdjacent').mockResolvedValue(false);

      const result = await service.executeAttack(dto, context);

      expect(result.success).toBe(false);
      // Текст ошибки различает melee/ranged с введения attackType
      expect(result.error).toBe('Melee attack: target must be adjacent to attacker');
    });

    it('should ALLOW attack on a far target when hero has extended-range ability (registry.canAttackAtRange)', async () => {
      // Цель НЕ смежна и НЕ в одной зоне (обычный melee достать не может),
      // но способность героя разрешает дистанцию 3 → атака должна пройти.
      const state = createMockGameState({
        phase: GamePhase.ACTION_ATTACK,
        handZones: {
          player1: {
            cards: [{ id: 'card1', cardId: 'card1', cardType: 'ATTACK' as any, value: 3 } as any],
            maxSize: 5,
          },
          player2: { cards: [], maxSize: 5 },
        },
      });

      const dto: AttackDto = {
        gameId: 'test-game-1',
        attackerId: 'fighter1',
        targetId: 'fighter2',
        cardId: 'card1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      // Цель далеко: не смежна, не в зоне, дистанция = 3
      jest.spyOn(adjacencyService, 'isAdjacent').mockResolvedValue(false);
      jest.spyOn(adjacencyService, 'isInSameZone').mockReturnValue(false);
      jest.spyOn(adjacencyService, 'manhattanDistance').mockReturnValue(3);

      // Способность героя разрешает дистанцию <= 3
      const registry = (service as any).abilityRegistry as { canAttackAtRange: jest.Mock };
      registry.canAttackAtRange.mockReturnValue(true);

      const result = await service.executeAttack(dto, context);

      expect(result.success).toBe(true);
      expect(result.error).toBeUndefined();
      expect(result.gameState!.phase).toBe(GamePhase.COMBAT);
      // gate проверил extended-range с правильной сигнатурой (slug, attackerId,
      // targetId, range, stance). У fighter1 нет heroSlug → fallback на heroId
      // ('ms-marvel'); stance — undefined (нет metadata.heroStances). Как в проде.
      expect(registry.canAttackAtRange).toHaveBeenCalledWith(
        'ms-marvel',
        'fighter1',
        'fighter2',
        3,
        undefined,
      );
    });

    it('should REJECT a far attack when no extended-range ability (canAttackAtRange=false)', async () => {
      // Поведение по умолчанию сохранено: способности нет → далёкая melee-атака
      // отклоняется как и раньше.
      const state = createMockGameState({
        phase: GamePhase.ACTION_ATTACK,
        handZones: {
          player1: {
            cards: [{ id: 'card1', cardId: 'card1', cardType: 'ATTACK' as any, value: 3 } as any],
            maxSize: 5,
          },
          player2: { cards: [], maxSize: 5 },
        },
      });

      const dto: AttackDto = {
        gameId: 'test-game-1',
        attackerId: 'fighter1',
        targetId: 'fighter2',
        cardId: 'card1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(adjacencyService, 'isAdjacent').mockResolvedValue(false);
      jest.spyOn(adjacencyService, 'isInSameZone').mockReturnValue(false);
      const registry = (service as any).abilityRegistry as { canAttackAtRange: jest.Mock };
      registry.canAttackAtRange.mockReturnValue(false);

      const result = await service.executeAttack(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Melee attack: target must be adjacent to attacker');
    });
  });

  describe('executeEndTurn', () => {
    it('should execute end turn successfully', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: EndTurnDto = {
        gameId: 'test-game-1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeEndTurn(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState).toBeDefined();
      expect(result.metadata?.action).toBe('endTurn');
      // advanceTurn сразу ставит ACTION_MANEUVER (TURN_START исключён из потока)
      expect(result.gameState?.phase).toBe(GamePhase.ACTION_MANEUVER);
      expect(result.gameState?.currentTurnPlayerId).toBe('player2');
    });

    it('should skip dead players when finding next player', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        fighters: [
          ...createMockGameState().fighters.map(f => f.ownerId === 'player2'
            ? { ...f, health: 0, isDefeated: true } : f),
          { ...createMockGameState().fighters[0], id: 'fighter3', ownerId: 'player3',
            heroId: 'bruce-lee', health: 15, maxHealth: 15 },
        ],
        players: [
          {
            userId: 'player1',
            heroId: 'ms-marvel',
            health: 14,
            maxHealth: 14,
            fighterIds: ['fighter1'],
            isAlive: true,
          },
          {
            userId: 'player2',
            heroId: 'daredevil',
            health: 0,
            maxHealth: 17,
            fighterIds: ['fighter2'],
            isAlive: false, // Мёртв
          },
          {
            userId: 'player3',
            heroId: 'bruce-lee',
            health: 15,
            maxHealth: 15,
            fighterIds: ['fighter3'],
            isAlive: true,
          },
        ],
      });

      const dto: EndTurnDto = {
        gameId: 'test-game-1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeEndTurn(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState?.currentTurnPlayerId).toBe('player3'); // Пропускает мёртвого player2
    });

    it('should return error when validation fails', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: EndTurnDto = {
        gameId: 'test-game-1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(rulesValidator, 'validateEndTurn').mockReturnValue({
        valid: false,
        error: 'Not your turn',
        code: 'NOT_YOUR_TURN',
      });

      const result = await service.executeEndTurn(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Not your turn');
    });
  });

  describe('executePass', () => {
    it('should execute pass successfully', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: PassDto = {
        gameId: 'test-game-1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executePass(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState).toBeDefined();
      expect(result.metadata?.action).toBe('pass');
    });

    it('should return error when validation fails', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: PassDto = {
        gameId: 'test-game-1',
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(rulesValidator, 'validatePass').mockReturnValue({
        valid: false,
        error: 'Already passed',
        code: 'ALREADY_PASSED',
      });

      const result = await service.executePass(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Already passed');
    });
  });

  describe('executeToggleDoor', () => {
    it('should execute toggle door successfully', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        boardState: {
          ...createMockGameState().boardState,
          doors: { '5:5': false } as any,
        } as any,
      });

      const dto: ToggleDoorDto = {
        gameId: 'test-game-1',
        x: 5,
        y: 5,
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeToggleDoor(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState).toBeDefined();
      expect(result.metadata?.action).toBe('toggleDoor');
    });

    it('should return error when door not found', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
      });

      const dto: ToggleDoorDto = {
        gameId: 'test-game-1',
        x: 5,
        y: 5,
      };

      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      jest.spyOn(rulesValidator, 'validateToggleDoor').mockReturnValue({
        valid: false,
        error: 'No door at (5, 5)',
        code: 'DOOR_NOT_FOUND',
      });

      const result = await service.executeToggleDoor(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('No door at (5, 5)');
    });
  });

  describe('executeSetStance (STANCE)', () => {
    // Состояние со stance-героем у player1 (alice). Реестр-мок возвращает
    // её стойки через getStances.
    const aliceState = (stance?: string) =>
      createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        fighters: [
          {
            id: 'fighter1',
            ownerId: 'player1',
            heroId: 'alice',
            heroSlug: 'alice',
            name: 'Alice',
            type: 'HERO' as any,
            health: 14,
            maxHealth: 14,
            position: { x: 5, y: 5 },
            effects: [],
            hasSidekick: false,
          },
          {
            id: 'fighter2',
            ownerId: 'player2',
            heroId: 'daredevil',
            heroSlug: 'daredevil',
            name: 'Daredevil',
            type: 'HERO' as any,
            health: 17,
            maxHealth: 17,
            position: { x: 6, y: 5 },
            effects: [],
            hasSidekick: false,
          },
        ],
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 2,
          ...(stance !== undefined ? { heroStances: { player1: stance } } : {}),
        },
      });

    const stubStances = () => {
      const registry = (service as any).abilityRegistry as { getStances: jest.Mock };
      registry.getStances.mockImplementation((slug: string) =>
        slug === 'alice' ? ['big', 'small'] : [],
      );
    };

    it('ставит metadata.heroStances[userId] и бампит seq на 1', async () => {
      stubStances();
      const state = aliceState('big');
      const dto: SetStanceDto = { gameId: 'test-game-1', stanceId: 'small' };
      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeSetStance(dto, context);

      expect(result.success).toBe(true);
      expect(result.gameState!.metadata.heroStances).toEqual({ player1: 'small' });
      expect(result.gameState!.sequenceNumber).toBe(state.sequenceNumber + 1);
      expect(result.metadata?.action).toBe('setStance');
    });

    it('НЕ тратит действие (actionsRemaining без изменений)', async () => {
      stubStances();
      const state = aliceState('big');
      const dto: SetStanceDto = { gameId: 'test-game-1', stanceId: 'small' };
      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeSetStance(dto, context);
      expect(getActionsRemaining(result.gameState!)).toBe(2);
    });

    it('отклоняет неизвестную стойку', async () => {
      stubStances();
      const state = aliceState('big');
      const dto: SetStanceDto = { gameId: 'test-game-1', stanceId: 'gigantic' };
      const context: ActionContext = {
        userId: 'player1',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeSetStance(dto, context);
      expect(result.success).toBe(false);
    });

    it('отклоняет, если у игрока нет stance-героя', async () => {
      // player2 владеет daredevil — getStances('daredevil') → []
      stubStances();
      const state = aliceState('big');
      const dto: SetStanceDto = { gameId: 'test-game-1', stanceId: 'big' };
      const context: ActionContext = {
        userId: 'player2',
        gameId: 'test-game-1',
        currentState: state,
      };

      const result = await service.executeSetStance(dto, context);
      expect(result.success).toBe(false);
    });
  });

  describe('A0: executeResolveCombat бьёт атакованного бойца (targetFighterId)', () => {
    // Раньше defenderFighter искался по ownerId — урон всегда получал ПЕРВЫЙ
    // боец защитника (герой), даже если атаковали сайдкика
    const sidekick = {
      id: 'fighter2-sk0',
      ownerId: 'player2',
      heroId: 'daredevil',
      name: 'Sidekick',
      type: 'sidekick' as any,
      health: 5,
      maxHealth: 5,
      position: { x: 7, y: 5 },
      effects: [],
      hasSidekick: false,
    };

    const combatState = (targetFighterId?: string) =>
      createMockGameState({
        phase: GamePhase.COMBAT_RESOLVE,
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          actionsRemaining: 1,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId,
            attackerCardId: 'card-a',
            defenderCardId: 'card-d',
            attackValue: 4,
            defenseValue: 1,
            startedAt: new Date(),
          },
        } as any,
        // герой защитника идёт ПЕРВЫМ в fighters — провоцируем старый баг
        fighters: [...createMockGameState().fighters, sidekick] as any,
      });

    it('урон получает сайдкик из targetFighterId, герой защитника цел', async () => {
      const state = combatState('fighter2-sk0');
      const result = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as any,
        { userId: 'player1', gameId: 'test-game-1', currentState: state },
      );

      expect(result.success).toBe(true);
      const fighters = result.gameState!.fighters;
      expect(fighters.find((f) => f.id === 'fighter2-sk0')!.health).toBe(5 - 3);
      expect(fighters.find((f) => f.id === 'fighter2')!.health).toBe(17);
    });

    it('легаси без targetFighterId — fallback на первого бойца защитника', async () => {
      const state = combatState(undefined);
      const result = await service.executeResolveCombat(
        { gameId: 'test-game-1' } as any,
        { userId: 'player1', gameId: 'test-game-1', currentState: state },
      );

      expect(result.success).toBe(true);
      const fighters = result.gameState!.fighters;
      expect(fighters.find((f) => f.id === 'fighter2')!.health).toBe(17 - 3);
      expect(fighters.find((f) => f.id === 'fighter2-sk0')!.health).toBe(5);
    });
  });
});
