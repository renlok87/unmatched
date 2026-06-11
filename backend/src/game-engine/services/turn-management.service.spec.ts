/**
 * Turn Management Service Tests
 *
 * Unit тесты для сервиса управления ходами
 */

import { Test, TestingModule } from '@nestjs/testing';
import { TurnManagementService } from './turn-management.service';
import { ContentService } from '../../content/content.service';
import { HeroAbilityRegistry } from '../abilities/hero-ability-registry';
import { GamePhase, FighterType } from '../models';
import type { GameState, Fighter } from '../models';

describe('TurnManagementService', () => {
  let service: TurnManagementService;
  let contentService: ContentService;
  let abilityRegistry: HeroAbilityRegistry;

  /**
   * Создаёт тестовое состояние игры
   */
  const createMockGameState = (overrides?: Partial<GameState>): GameState => ({
    gameId: 'test-game-1',
    sequenceNumber: 1,
    phase: GamePhase.SETUP,
    turnCount: 0,
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
        type: FighterType.HERO,
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
        type: FighterType.HERO,
        health: 17,
        maxHealth: 17,
        position: { x: 15, y: 15 },
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
      cells: [],
      doors: {},
      fog: {},
      tokens: {},
    },
    metadata: {
      lastActionAt: new Date(),
      lastActionBy: 'player1',
      version: 1,
    },
    ...overrides,
  });

  const mockHeroDefinition = {
    id: 'ms-marvel',
    name: 'Ms. Marvel',
    health: 14,
    movement: 2,
    set: 'teen-spirit',
    abilities: [
      {
        id: 'stretchy',
        name: 'Stretchy',
        text: 'At the start of your turn, you may move Ms. Marvel 1 space.',
        trigger: 'start_of_turn' as const,
      },
    ],
    deckCards: [],
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        TurnManagementService,
        {
          provide: ContentService,
          useValue: {
            getHeroById: jest.fn().mockResolvedValue(mockHeroDefinition),
          },
        },
        {
          provide: HeroAbilityRegistry,
          useValue: {
            triggerOnTurnStart: jest.fn().mockReturnValue([]),
            triggerOnTurnEnd: jest.fn().mockReturnValue([]),
            triggerOnMove: jest.fn().mockReturnValue([]),
            triggerOnDefeat: jest.fn().mockReturnValue([]),
          },
        },
      ],
    }).compile();

    service = module.get<TurnManagementService>(TurnManagementService);
    contentService = module.get<ContentService>(ContentService);
    abilityRegistry = module.get<HeroAbilityRegistry>(HeroAbilityRegistry);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('startTurn', () => {
    it('should start turn for valid player', async () => {
      const state = createMockGameState();

      const result = await service.startTurn(state, 'player1');

      expect(result.state.phase).toBe(GamePhase.TURN_START);
      expect(result.state.currentTurnPlayerId).toBe('player1');
      expect(result.state.sequenceNumber).toBe(2);
    });

    it('should reset action counters on turn start', async () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 2, // Предыдущий ход использовал 2 действия
          turn_passed: true,
          turn_additional: 1,
        },
      } as any);

      const result = await service.startTurn(state, 'player2');

      const metadata = result.state.metadata as Record<string, any>;
      expect(metadata.turn_actions).toBe(0);
      expect(metadata.turn_passed).toBe(false);
      expect(metadata.turn_additional).toBe(0);
    });

    it('should trigger hero abilities on turn start', async () => {
      const state = createMockGameState();
      const mockEvents = [
        {
          type: 'MOVE',
          description: 'Ms. Marvel moves 1 space',
          sourceId: 'fighter1',
        },
      ];

      jest.spyOn(abilityRegistry, 'triggerOnTurnStart').mockReturnValue(mockEvents);

      const result = await service.startTurn(state, 'player1');

      expect(abilityRegistry.triggerOnTurnStart).toHaveBeenCalledWith(
        'ms-marvel',
        expect.objectContaining({ id: 'fighter1' }),
      );
      // Сервис добавляет событие CARD_DRAWN для героев со способностью start_of_turn
      expect(result.events).toContainEqual(mockEvents[0]);
      expect(result.events.length).toBeGreaterThan(0);
    });

    it('should throw error for non-existent player', async () => {
      const state = createMockGameState();

      await expect(service.startTurn(state, 'nonexistent')).rejects.toThrow(
        'Player nonexistent not found in game state',
      );
    });

    it('should throw error for dead player', async () => {
      const state = createMockGameState({
        players: [
          {
            userId: 'player1',
            heroId: 'ms-marvel',
            health: 0,
            maxHealth: 14,
            fighterIds: ['fighter1'],
            isAlive: false, // Мёртв
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
      });

      await expect(service.startTurn(state, 'player1')).rejects.toThrow(
        'Player player1 is not alive',
      );
    });

    it('should update lastAction metadata', async () => {
      const state = createMockGameState();
      const beforeTime = new Date();

      const result = await service.startTurn(state, 'player1');

      expect(result.state.metadata.lastActionBy).toBe('player1');
      expect(result.state.metadata.lastActionAt.getTime()).toBeGreaterThanOrEqual(
        beforeTime.getTime(),
      );
    });
  });

  describe('endTurn', () => {
    it('should end turn and transition to next player', async () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player1',
        phase: GamePhase.ACTION_MANEUVER,
      });

      const result = await service.endTurn(state, 'player1');

      expect(result.state.currentTurnPlayerId).toBe('player2');
      expect(result.state.phase).toBe(GamePhase.TURN_END);
      expect(result.gameOver).toBe(false);
    });

    it('should detect game over when all enemies defeated', async () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player1',
        fighters: [
          {
            id: 'fighter1',
            ownerId: 'player1',
            heroId: 'ms-marvel',
            name: 'Ms. Marvel',
            type: FighterType.HERO,
            health: 14,
            maxHealth: 14,
            position: { x: 5, y: 5 },
            effects: [],
            hasSidekick: false,
          },
          // Боец player2 повержен (health = 0)
          {
            id: 'fighter2',
            ownerId: 'player2',
            heroId: 'daredevil',
            name: 'Daredevil',
            type: FighterType.HERO,
            health: 0, // Повержен
            maxHealth: 17,
            position: { x: 15, y: 15 },
            effects: [],
            hasSidekick: false,
          },
        ],
      });

      const result = await service.endTurn(state, 'player1');

      expect(result.gameOver).toBe(true);
      expect(result.winnerId).toBe('player1');
    });

    it('should trigger hero abilities on turn end', async () => {
      const state = createMockGameState();
      const mockEvents = [
        {
          type: 'HEAL',
          description: 'Daredevil heals 1',
          sourceId: 'fighter2',
        },
      ];

      jest.spyOn(abilityRegistry, 'triggerOnTurnEnd').mockReturnValue(mockEvents);

      const result = await service.endTurn(state, 'player1');

      expect(abilityRegistry.triggerOnTurnEnd).toHaveBeenCalled();
      expect(result.events).toEqual(mockEvents);
    });

    it('should handle player death without allies', async () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player1',
        fighters: [
          {
            id: 'fighter1',
            ownerId: 'player1',
            heroId: 'ms-marvel',
            name: 'Ms. Marvel',
            type: FighterType.HERO,
            health: 0, // Повержен
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
            type: FighterType.HERO,
            health: 17,
            maxHealth: 17,
            position: { x: 15, y: 15 },
            effects: [],
            hasSidekick: false,
          },
        ],
      });

      const result = await service.endTurn(state, 'player1');

      expect(result.gameOver).toBe(true);
      expect(result.winnerId).toBe('player2');
    });

    it('should throw error for non-existent player', async () => {
      const state = createMockGameState();

      await expect(service.endTurn(state, 'nonexistent')).rejects.toThrow(
        'Player nonexistent not found in game state',
      );
    });

    it('should clear expired modifiers at end of turn', async () => {
      const state = createMockGameState({
        fighters: [
          {
            id: 'fighter1',
            ownerId: 'player1',
            heroId: 'ms-marvel',
            name: 'Ms. Marvel',
            type: FighterType.HERO,
            health: 14,
            maxHealth: 14,
            position: { x: 5, y: 5 },
            effects: [
              {
                type: 'BUFF',
                value: 2,
                duration: 'turn', // Истекает в конце хода
                expiresAt: Date.now() - 1000, // Уже истёк
                source: 'test',
              },
            ],
            hasSidekick: false,
          },
          {
            id: 'fighter2',
            ownerId: 'player2',
            heroId: 'daredevil',
            name: 'Daredevil',
            type: FighterType.HERO,
            health: 17,
            maxHealth: 17,
            position: { x: 15, y: 15 },
            effects: [],
            hasSidekick: false,
          },
        ],
      });

      const result = await service.endTurn(state, 'player1');

      // Эффект должен быть очищен
      const fighter1 = result.state.fighters.find((f) => f.id === 'fighter1');
      expect(fighter1?.effects).toHaveLength(0);
    });
  });

  describe('canTakeAction', () => {
    it('should return true when player can take action', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 0,
        },
      } as any);

      const result = service.canTakeAction(state, 'player1');

      expect(result).toBe(true);
    });

    it('should return false when max actions reached', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 2, // Максимум
        },
      } as any);

      const result = service.canTakeAction(state, 'player1');

      expect(result).toBe(false);
    });

    it('should return false when player has passed', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 1,
          turn_passed: true, // Пасовал
        },
      } as any);

      const result = service.canTakeAction(state, 'player1');

      expect(result).toBe(false);
    });

    it('should return false when not player turn', () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player2', // Не ход player1
      });

      const result = service.canTakeAction(state, 'player1');

      expect(result).toBe(false);
    });

    it('should respect additional actions', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 2, // Базовый лимит
          turn_additional: 1, // +1 дополнительное
        },
      } as any);

      const result = service.canTakeAction(state, 'player1');

      expect(result).toBe(true); // Может взять 3-е действие
    });
  });

  describe('spendAction', () => {
    it('should increment actions taken', async () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 0,
        },
      } as any);

      const result = await service.spendAction(state, 'player1');

      const metadata = result.metadata as Record<string, any>;
      expect(metadata.turn_actions).toBe(1);
    });

    it('should throw error when cannot take action', async () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 2, // Максимум
        },
      } as any);

      await expect(service.spendAction(state, 'player1')).rejects.toThrow(
        'Player player1 cannot take action',
      );
    });

    it('should increment sequence number', async () => {
      const state = createMockGameState({
        sequenceNumber: 5,
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 0,
        },
      } as any);

      const result = await service.spendAction(state, 'player1');

      expect(result.sequenceNumber).toBe(6);
    });
  });

  describe('pass', () => {
    it('should set hasPassed flag', async () => {
      const state = createMockGameState();

      const result = await service.pass(state, 'player1');

      const metadata = result.state.metadata as Record<string, any>;
      expect(metadata.turn_passed).toBe(true);
    });

    it('should throw error when not player turn', async () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player2',
      });

      await expect(service.pass(state, 'player1')).rejects.toThrow(
        'Not player1\'s turn',
      );
    });

    it('should throw error when already passed', async () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_passed: true,
        },
      } as any);

      await expect(service.pass(state, 'player1')).rejects.toThrow(
        'Player player1 has already passed',
      );
    });

    it('should increment sequence number', async () => {
      const state = createMockGameState({
        sequenceNumber: 5,
      });

      const result = await service.pass(state, 'player1');

      expect(result.state.sequenceNumber).toBe(6);
    });
  });

  describe('getCurrentPlayer', () => {
    it('should return current player ID', () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player2',
      });

      const result = service.getCurrentPlayer(state);

      expect(result).toBe('player2');
    });

    it('should return null when no current player', () => {
      const state = createMockGameState({
        currentTurnPlayerId: '',
      });

      const result = service.getCurrentPlayer(state);

      expect(result).toBeNull();
    });
  });

  describe('getNextPlayer', () => {
    it('should return next player in order', () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player1',
      });

      const result = service.getNextPlayer(state);

      expect(result).toBe('player2');
    });

    it('should wrap around to first player', () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player2',
      });

      const result = service.getNextPlayer(state);

      expect(result).toBe('player1');
    });

    it('should skip dead players', () => {
      const state = createMockGameState({
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

      const result = service.getNextPlayer(state);

      expect(result).toBe('player3'); // Пропускает мёртвого player2
    });

    it('should use explicit currentPlayerId when provided', () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'player1',
      });

      const result = service.getNextPlayer(state, 'player2');

      expect(result).toBe('player1');
    });

    it('should return first alive player when current not found', () => {
      const state = createMockGameState({
        currentTurnPlayerId: 'nonexistent',
      });

      const result = service.getNextPlayer(state);

      expect(result).toBe('player1'); // Первый живой
    });
  });

  describe('getPlayerTurnMetadata', () => {
    it('should return player turn metadata', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 1,
          turn_passed: false,
          turn_additional: 0,
        },
      } as any);

      const result = service.getPlayerTurnMetadata(state, 'player1');

      expect(result.actionsTaken).toBe(1);
      expect(result.hasPassed).toBe(false);
      expect(result.additionalActions).toBe(0);
    });

    it('should return default values when metadata missing', () => {
      const state = createMockGameState();

      const result = service.getPlayerTurnMetadata(state, 'player1');

      expect(result.actionsTaken).toBe(0);
      expect(result.hasPassed).toBe(false);
      expect(result.additionalActions).toBe(0);
    });
  });

  describe('getRemainingActions', () => {
    it('should calculate remaining actions correctly', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 1,
        },
      } as any);

      const result = service.getRemainingActions(state, 'player1');

      expect(result).toBe(1); // 2 - 1 = 1
    });

    it('should include additional actions', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 2,
          turn_additional: 2,
        },
      } as any);

      const result = service.getRemainingActions(state, 'player1');

      expect(result).toBe(2); // (2 + 2) - 2 = 2
    });

    it('should return 0 when no actions remaining', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          turn_actions: 3,
          turn_additional: 1,
        },
      } as any);

      const result = service.getRemainingActions(state, 'player1');

      expect(result).toBe(0); // (2 + 1) - 3 = 0
    });
  });

  describe('phase transitions', () => {
    it('should transition to maneuver phase', () => {
      const state = createMockGameState({
        phase: GamePhase.TURN_START,
        sequenceNumber: 1,
      });

      const result = service.transitionToManeuver(state);

      expect(result.phase).toBe(GamePhase.ACTION_MANEUVER);
      expect(result.sequenceNumber).toBe(2);
    });

    it('should transition to attack phase', () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_MANEUVER,
        sequenceNumber: 1,
      });

      const result = service.transitionToAttack(state);

      expect(result.phase).toBe(GamePhase.ACTION_ATTACK);
      expect(result.sequenceNumber).toBe(2);
    });

    it('should transition to combat phase', () => {
      const state = createMockGameState({
        phase: GamePhase.ACTION_ATTACK,
        sequenceNumber: 1,
      });

      const result = service.transitionToCombat(state);

      expect(result.phase).toBe(GamePhase.COMBAT);
      expect(result.sequenceNumber).toBe(2);
    });

    it('should transition to combat resolve phase', () => {
      const state = createMockGameState({
        phase: GamePhase.COMBAT,
        sequenceNumber: 1,
      });

      const result = service.transitionToCombatResolve(state);

      expect(result.phase).toBe(GamePhase.COMBAT_RESOLVE);
      expect(result.sequenceNumber).toBe(2);
    });
  });

  describe('game state helpers', () => {
    it('should check if game is over', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          gameOver: true,
        },
      } as any);

      expect(service.isGameOver(state)).toBe(true);
    });

    it('should return false when game is not over', () => {
      const state = createMockGameState();

      expect(service.isGameOver(state)).toBe(false);
    });

    it('should get winner', () => {
      const state = createMockGameState({
        metadata: {
          lastActionAt: new Date(),
          lastActionBy: 'player1',
          version: 1,
          gameOver: true,
          winnerId: 'player2',
        },
      } as any);

      expect(service.getWinner(state)).toBe('player2');
    });

    it('should return undefined when no winner', () => {
      const state = createMockGameState();

      expect(service.getWinner(state)).toBeUndefined();
    });
  });
});
