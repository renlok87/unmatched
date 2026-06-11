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
import { GamePhase } from '../../games/dto';
import type { GameState } from '../../games/game-state.service';
import {
  ManeuverDto,
  MoveFighterDto,
  AttackDto,
  EndTurnDto,
  PassDto,
  ToggleDoorDto,
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
            manhattanDistance: jest.fn().mockReturnValue(1),
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

    it('should return error when movement fails', async () => {
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

      jest.spyOn(movementService, 'executeMovement').mockResolvedValue({
        success: false,
        error: 'Path blocked',
      });

      const result = await service.executeManeuver(dto, context);

      expect(result.success).toBe(false);
      expect(result.error).toBe('Path blocked');
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
      expect(result.error).toBe('Target is not adjacent to attacker');
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
      expect(result.gameState?.phase).toBe(GamePhase.TURN_START);
      expect(result.gameState?.currentTurnPlayerId).toBe('player2');
    });

    it('should skip dead players when finding next player', async () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
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
});
