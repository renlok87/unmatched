import { Test, TestingModule } from '@nestjs/testing';
import { NotFoundException } from '@nestjs/common';
import { GameStateService, GameState, SerializedGameState } from './game-state.service';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { GameSubscriptionService } from './game-subscription.service';
import { GamePhase } from './dto/create-game.dto';
import { ConcurrentModificationException } from './exceptions/game.exceptions';

describe('GameStateService', () => {
  let service: GameStateService;
  let prisma: PrismaService;
  let redis: RedisService;
  let gameSubscriptionService: GameSubscriptionService;

  const mockGameState: GameState = {
    gameId: 'game1',
    sequenceNumber: 1,
    phase: GamePhase.SETUP,
    turnCount: 0,
    currentTurnPlayerId: 'player1',
    players: [
      {
        userId: 'player1',
        heroId: 'hero1',
        health: 100,
        maxHealth: 100,
        fighterIds: ['fighter1'],
        isAlive: true,
      },
      {
        userId: 'player2',
        heroId: 'hero2',
        health: 100,
        maxHealth: 100,
        fighterIds: ['fighter2'],
        isAlive: true,
      },
    ],
    fighters: [
      {
        id: 'fighter1',
        ownerId: 'player1',
        heroId: 'hero1',
        name: 'Fighter 1',
        type: 'HERO',
        health: 100,
        maxHealth: 100,
        position: { x: 0, y: 0 },
        effects: [],
        hasSidekick: false,
      },
      {
        id: 'fighter2',
        ownerId: 'player2',
        heroId: 'hero2',
        name: 'Fighter 2',
        type: 'HERO',
        health: 100,
        maxHealth: 100,
        position: { x: 10, y: 10 },
        effects: [],
        hasSidekick: false,
      },
    ],
    decks: {
      player1: {
        cards: [],
        drawPile: [],
        topCard: {
          id: 'card1',
          cardId: 'card1',
          name: 'Card 1',
          nameEn: 'Card 1',
          nameRu: 'Карта 1',
          cardType: 'ATTACK',
        },
      },
      player2: {
        cards: [],
        drawPile: [],
        topCard: {
          id: 'card2',
          cardId: 'card2',
          name: 'Card 2',
          nameEn: 'Card 2',
          nameRu: 'Карта 2',
          cardType: 'DEFENSE',
        },
      },
    },
    discardPiles: {},
    handZones: {
      player1: {
        cards: [
          {
            id: 'hand1',
            cardId: 'hand1',
            name: 'Hand Card 1',
            nameEn: 'Hand Card 1',
            nameRu: 'Карта в руке 1',
            cardType: 'ATTACK',
            attackValue: 5,
            isVisible: true,
          },
        ],
        maxSize: 5,
      },
      player2: {
        cards: [
          {
            id: 'hand2',
            cardId: 'hand2',
            name: 'Hand Card 2',
            nameEn: 'Hand Card 2',
            nameRu: 'Карта в руке 2',
            cardType: 'DEFENSE',
            defenseValue: 3,
            isVisible: true,
          },
        ],
        maxSize: 5,
      },
    },
    boardState: {
      doors: {},
      fog: {},
      tokens: {},
    },
    metadata: {
      lastActionAt: new Date(),
      lastActionBy: 'player1',
      version: 1,
    },
  };

  const mockGamePlayers = [
    {
      userId: 'player1',
      gameId: 'game1',
      heroId: 'hero1',
      user: { id: 'player1', email: 'player1@test.com', username: 'player1' },
    },
    {
      userId: 'player2',
      gameId: 'game1',
      heroId: 'hero2',
      user: { id: 'player2', email: 'player2@test.com', username: 'player2' },
    },
  ];

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameStateService,
        {
          provide: PrismaService,
          useValue: {
            gameState: {
              findUnique: jest.fn(),
              upsert: jest.fn(),
            },
            game: {
              update: jest.fn(),
            },
            gamePlayer: {
              findMany: jest.fn(),
            },
            $transaction: jest.fn(),
          },
        },
        {
          provide: RedisService,
          useValue: {
            setJsonex: jest.fn(),
            getJson: jest.fn(),
            del: jest.fn(),
            withLock: jest.fn(),
          },
        },
        {
          provide: GameSubscriptionService,
          useValue: {
            publishGameUpdate: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<GameStateService>(GameStateService);
    prisma = module.get(PrismaService);
    redis = module.get(RedisService);
    gameSubscriptionService = module.get(GameSubscriptionService);
  });

  describe('serialize', () => {
    it('should serialize game state correctly', () => {
      const serialized = service.serialize(mockGameState);

      expect(serialized.v).toBe(1);
      expect(serialized.g).toBe('game1');
      expect(serialized.s).toBe(1);
      expect(serialized.p).toBe(GamePhase.SETUP);
      expect(serialized.t).toBe(0);
      expect(serialized.c).toBe('player1');
      expect(serialized.pl).toHaveLength(2);
      expect(serialized.f).toHaveLength(2);
      expect(serialized.d).toHaveProperty('player1');
      expect(serialized.d).toHaveProperty('player2');
      expect(serialized.h).toHaveProperty('player1');
      expect(serialized.h).toHaveProperty('player2');
      expect(serialized.b).toHaveProperty('dr');
      expect(serialized.b).toHaveProperty('fg');
      expect(serialized.b).toHaveProperty('tk');
    });

    it('should serialize players correctly', () => {
      const serialized = service.serialize(mockGameState);

      expect(serialized.pl[0].uid).toBe('player1');
      expect(serialized.pl[0].hid).toBe('hero1');
      expect(serialized.pl[0].hp).toBe(100);
      expect(serialized.pl[0].mhp).toBe(100);
      expect(serialized.pl[0].fid).toEqual(['fighter1']);
      expect(serialized.pl[0].alv).toBe(true);
    });

    it('should serialize fighters correctly', () => {
      const serialized = service.serialize(mockGameState);

      expect(serialized.f[0].id).toBe('fighter1');
      expect(serialized.f[0].oid).toBe('player1');
      expect(serialized.f[0].hid).toBe('hero1');
      expect(serialized.f[0].n).toBe('Fighter 1');
      expect(serialized.f[0].ty).toBe('HERO');
      expect(serialized.f[0].hp).toBe(100);
      expect(serialized.f[0].mhp).toBe(100);
      expect(serialized.f[0].pos).toEqual({ x: 0, y: 0 });
      expect(serialized.f[0].e).toEqual([]);
      expect(serialized.f[0].hs).toBe(false);
    });

    it('should serialize decks correctly', () => {
      const serialized = service.serialize(mockGameState);

      expect(serialized.d.player1.c).toBe(0);
      expect(serialized.d.player1.tc).toBeDefined();
      expect(serialized.d.player1.tc?.id).toBe('card1');
    });

    it('should serialize hand zones correctly', () => {
      const serialized = service.serialize(mockGameState);

      expect(serialized.h.player1.c).toHaveLength(1);
      expect(serialized.h.player1.c[0].id).toBe('hand1');
      expect(serialized.h.player1.c[0].v).toBe(true);
      expect(serialized.h.player1.ms).toBe(5);
    });

    it('should serialize board state correctly', () => {
      const serialized = service.serialize(mockGameState);

      expect(serialized.b.dr).toEqual({});
      expect(serialized.b.fg).toEqual({});
      expect(serialized.b.tk).toEqual({});
    });

    it('should serialize metadata correctly', () => {
      const serialized = service.serialize(mockGameState);

      expect(serialized.m.la).toBe(mockGameState.metadata.lastActionAt.toISOString());
      expect(serialized.m.lb).toBe('player1');
      expect(serialized.m.v).toBe(1);
    });
  });

  describe('deserialize', () => {
    it('should deserialize serialized state correctly', () => {
      const serialized = service.serialize(mockGameState);
      const deserialized = service.deserialize(serialized);

      expect(deserialized.gameId).toBe('game1');
      expect(deserialized.sequenceNumber).toBe(1);
      expect(deserialized.phase).toBe(GamePhase.SETUP);
      expect(deserialized.turnCount).toBe(0);
      expect(deserialized.currentTurnPlayerId).toBe('player1');
      expect(deserialized.players).toHaveLength(2);
      expect(deserialized.fighters).toHaveLength(2);
      expect(deserialized.decks).toHaveProperty('player1');
      expect(deserialized.handZones).toHaveProperty('player1');
    });

    it('should handle non-serialized data', () => {
      const deserialized = service.deserialize(mockGameState);

      expect(deserialized.gameId).toBe('game1');
    });

    it('should deserialize players correctly', () => {
      const serialized = service.serialize(mockGameState);
      const deserialized = service.deserialize(serialized);

      expect(deserialized.players[0].userId).toBe('player1');
      expect(deserialized.players[0].heroId).toBe('hero1');
      expect(deserialized.players[0].health).toBe(100);
      expect(deserialized.players[0].maxHealth).toBe(100);
      expect(deserialized.players[0].fighterIds).toEqual(['fighter1']);
      expect(deserialized.players[0].isAlive).toBe(true);
    });

    it('should deserialize fighters correctly', () => {
      const serialized = service.serialize(mockGameState);
      const deserialized = service.deserialize(serialized);

      expect(deserialized.fighters[0].id).toBe('fighter1');
      expect(deserialized.fighters[0].ownerId).toBe('player1');
      expect(deserialized.fighters[0].heroId).toBe('hero1');
      expect(deserialized.fighters[0].name).toBe('Fighter 1');
      expect(deserialized.fighters[0].type).toBe('HERO');
      expect(deserialized.fighters[0].health).toBe(100);
      expect(deserialized.fighters[0].position).toEqual({ x: 0, y: 0 });
    });
  });

  describe('filterPrivateData', () => {
    it('should hide other players cards', () => {
      const filtered = service.filterPrivateData(mockGameState, 'player1');

      expect(filtered.handZones.player1.cards[0].name).toBe('Hand Card 1');
      expect(filtered.handZones.player2.cards[0].name).toBe('???');
      expect(filtered.handZones.player2.cards[0].nameEn).toBe('Hidden');
      expect(filtered.handZones.player2.cards[0].nameRu).toBe('Скрыто');
      expect(filtered.handZones.player2.cards[0].isVisible).toBe(false);
    });

    it('should hide other players deck top cards', () => {
      const filtered = service.filterPrivateData(mockGameState, 'player1');

      expect(filtered.decks.player1.topCard).toBeDefined();
      expect(filtered.decks.player2.topCard).toBeUndefined();
    });

    it('should keep own cards visible', () => {
      const filtered = service.filterPrivateData(mockGameState, 'player1');

      expect(filtered.handZones.player1.cards[0].name).toBe('Hand Card 1');
      expect(filtered.handZones.player1.cards[0].attackValue).toBe(5);
    });
  });

  describe('validateState', () => {
    it('should validate correct state', () => {
      const result = service.validateState(mockGameState);

      expect(result.valid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should detect missing gameId', () => {
      const invalidState = { ...mockGameState, gameId: '' };
      const result = service.validateState(invalidState);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing gameId');
    });

    it('should detect invalid sequenceNumber', () => {
      const invalidState = { ...mockGameState, sequenceNumber: -1 };
      const result = service.validateState(invalidState);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Invalid sequenceNumber');
    });

    it('should detect missing currentTurnPlayerId', () => {
      const invalidState = { ...mockGameState, currentTurnPlayerId: '' };
      const result = service.validateState(invalidState);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Missing currentTurnPlayerId');
    });

    it('should detect no players', () => {
      const invalidState = { ...mockGameState, players: [] };
      const result = service.validateState(invalidState);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('No players in state');
    });

    it('should detect current player not in list', () => {
      const invalidState = { ...mockGameState, currentTurnPlayerId: 'nonexistent' };
      const result = service.validateState(invalidState);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Current player not found in players list');
    });

    it('should detect fighter without id', () => {
      const invalidFighters = [{ ...mockGameState.fighters[0], id: '' }];
      const invalidState = { ...mockGameState, fighters: invalidFighters };
      const result = service.validateState(invalidState);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Fighter missing id');
    });

    it('should detect fighter with negative health', () => {
      const invalidFighters = [{ ...mockGameState.fighters[0], health: -10 }];
      const invalidState = { ...mockGameState, fighters: invalidFighters };
      const result = service.validateState(invalidState);

      expect(result.valid).toBe(false);
      expect(result.errors).toContain('Fighter fighter1 has negative health');
    });
  });

  describe('cache management', () => {
    it('should cache state', async () => {
      jest.spyOn(redis, 'setJsonex').mockResolvedValue('OK');

      await service.cacheState('game1', mockGameState);

      expect(redis.setJsonex).toHaveBeenCalledWith('gamestate:game1', 600, mockGameState);
    });

    it('should get cached state', async () => {
      jest.spyOn(redis, 'getJson').mockResolvedValue(mockGameState);

      const cached = await service.getCachedState('game1');

      expect(redis.getJson).toHaveBeenCalledWith('gamestate:game1');
      expect(cached).toEqual(mockGameState);
    });

    it('should return null when cache miss', async () => {
      jest.spyOn(redis, 'getJson').mockResolvedValue(null);

      const cached = await service.getCachedState('game1');

      expect(cached).toBeNull();
    });

    it('should invalidate cache', async () => {
      jest.spyOn(redis, 'del').mockResolvedValue(1);

      await service.invalidateStateCache('game1');

      expect(redis.del).toHaveBeenCalledWith('gamestate:game1');
    });
  });

  describe('createInitialState', () => {
    it('should create initial state', async () => {
      jest.spyOn(prisma.gamePlayer, 'findMany').mockResolvedValue(mockGamePlayers as any);

      const initialState = await service.createInitialState('game1', ['player1', 'player2']);

      expect(initialState.gameId).toBe('game1');
      expect(initialState.sequenceNumber).toBe(1);
      expect(initialState.phase).toBe(GamePhase.SETUP);
      expect(initialState.turnCount).toBe(0);
      expect(initialState.currentTurnPlayerId).toBe('player1');
      expect(initialState.players).toHaveLength(2);
      expect(initialState.fighters).toHaveLength(0);
      expect(initialState.decks).toHaveProperty('player1');
      expect(initialState.decks).toHaveProperty('player2');
      expect(initialState.handZones).toHaveProperty('player1');
      expect(initialState.handZones).toHaveProperty('player2');
      expect(initialState.handZones.player1.maxSize).toBe(5);
      expect(initialState.handZones.player2.maxSize).toBe(5);
    });

    it('should handle empty players list', async () => {
      jest.spyOn(prisma.gamePlayer, 'findMany').mockResolvedValue([]);

      const initialState = await service.createInitialState('game1', []);

      expect(initialState.players).toHaveLength(0);
      expect(initialState.currentTurnPlayerId).toBe('');
    });
  });

  describe('getStateDiff', () => {
    it('should detect phase change', () => {
      const newState = { ...mockGameState, phase: GamePhase.ACTION_MANEUVER };

      const diff = service.getStateDiff(mockGameState, newState);

      expect(diff.newSequence).toBe(mockGameState.sequenceNumber);
      expect(diff.changes.phase).toBe(GamePhase.ACTION_MANEUVER);
    });

    it('should detect turnCount change', () => {
      const newState = { ...mockGameState, turnCount: 5 };

      const diff = service.getStateDiff(mockGameState, newState);

      expect(diff.changes.turnCount).toBe(5);
    });

    it('should detect currentTurnPlayerId change', () => {
      const newState = { ...mockGameState, currentTurnPlayerId: 'player2' };

      const diff = service.getStateDiff(mockGameState, newState);

      expect(diff.changes.currentTurnPlayerId).toBe('player2');
    });

    it('should not include unchanged fields', () => {
      const newState = { ...mockGameState };

      const diff = service.getStateDiff(mockGameState, newState);

      expect(diff.changes.phase).toBeUndefined();
      expect(diff.changes.turnCount).toBeUndefined();
      expect(diff.changes.currentTurnPlayerId).toBeUndefined();
    });
  });

  describe('loadState', () => {
    it('should load state from cache', async () => {
      jest.spyOn(redis, 'getJson').mockResolvedValue(mockGameState);

      const state = await service.loadState('game1');

      expect(state).toEqual(mockGameState);
      expect(prisma.gameState.findUnique).not.toHaveBeenCalled();
    });

    it('should load state from database when cache miss', async () => {
      jest.spyOn(redis, 'getJson').mockResolvedValue(null);
      jest.spyOn(prisma.gameState, 'findUnique').mockResolvedValue({
        gameId: 'game1',
        state: service.serialize(mockGameState),
        sequenceNumber: 1,
        currentTurnPlayerId: 'player1',
        phase: GamePhase.SETUP,
        turnCount: 0,
      } as any);
      jest.spyOn(redis, 'setJsonex').mockResolvedValue('OK');

      const state = await service.loadState('game1');

      expect(state.gameId).toBe('game1');
      expect(prisma.gameState.findUnique).toHaveBeenCalledWith({
        where: { gameId: 'game1' },
      });
      expect(redis.setJsonex).toHaveBeenCalled();
    });

    it('should throw NotFoundException when state not found', async () => {
      jest.spyOn(redis, 'getJson').mockResolvedValue(null);
      jest.spyOn(prisma.gameState, 'findUnique').mockResolvedValue(null);

      await expect(service.loadState('nonexistent')).rejects.toThrow(NotFoundException);
    });
  });

  describe('saveState', () => {
    it('should save state with optimistic locking', async () => {
      jest.spyOn(prisma.gameState, 'findUnique').mockResolvedValue(null);
      jest.spyOn(prisma.gameState, 'upsert').mockResolvedValue({} as any);
      jest.spyOn(prisma.game, 'update').mockResolvedValue({} as any);
      jest.spyOn(redis, 'setJsonex').mockResolvedValue('OK');
      jest.spyOn(gameSubscriptionService, 'publishGameUpdate').mockResolvedValue(undefined);

      const transactionMock = jest.fn().mockImplementation(async (callback) => {
        return callback({
          gameState: {
            findUnique: jest.fn().mockResolvedValue(null),
            upsert: jest.fn().mockResolvedValue({} as any),
          },
          game: { update: jest.fn().mockResolvedValue({} as any) },
        });
      });
      jest.spyOn(prisma, '$transaction').mockImplementation(transactionMock);

      await service.saveState('game1', mockGameState);

      expect(prisma.$transaction).toHaveBeenCalled();
      expect(redis.setJsonex).toHaveBeenCalled();
      expect(gameSubscriptionService.publishGameUpdate).toHaveBeenCalledWith(
        'game1',
        mockGameState,
      );
    });

    it('should throw ConcurrentModificationException on version conflict', async () => {
      const existingState = {
        gameId: 'game1',
        sequenceNumber: 5,
      };

      const transactionMock = jest.fn().mockImplementation(async (callback) => {
        return callback({
          gameState: {
            findUnique: jest.fn().mockResolvedValue(existingState as any),
            upsert: jest.fn().mockResolvedValue({} as any),
          },
          game: { update: jest.fn().mockResolvedValue({} as any) },
        });
      });
      jest.spyOn(prisma, '$transaction').mockImplementation(transactionMock);

      await expect(service.saveState('game1', mockGameState)).rejects.toThrow(
        ConcurrentModificationException,
      );
    });
  });

  describe('getSequenceNumber', () => {
    it('should return sequence number', async () => {
      jest.spyOn(prisma.gameState, 'findUnique').mockResolvedValue({
        sequenceNumber: 5,
      } as any);

      const seqNum = await service.getSequenceNumber('game1');

      expect(seqNum).toBe(5);
    });

    it('should return 0 when game state not found', async () => {
      jest.spyOn(prisma.gameState, 'findUnique').mockResolvedValue(null);

      const seqNum = await service.getSequenceNumber('nonexistent');

      expect(seqNum).toBe(0);
    });
  });
});
