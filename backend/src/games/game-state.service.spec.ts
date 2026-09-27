import { Test, TestingModule } from '@nestjs/testing';
import { ConflictException, NotFoundException } from '@nestjs/common';
import { GameStateService, GameState, SerializedGameState } from './game-state.service';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { RatingService } from '../users/rating.service';
import { GameSubscriptionService } from './game-subscription.service';
import { GamePhase } from './dto/create-game.dto';
import { ConcurrentModificationException } from './exceptions/game.exceptions';
import { CardType, FighterType, EffectType, EffectTiming, createEmptyBoardState } from '../game-engine/models';

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
        type: FighterType.HERO,
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
        type: FighterType.HERO,
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
          cardType: CardType.ATTACK,
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
          cardType: CardType.DEFENSE,
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
            cardType: CardType.ATTACK,
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
            cardType: CardType.DEFENSE,
            defenseValue: 3,
            isVisible: true,
          },
        ],
        maxSize: 5,
      },
    },
    boardState: {
      ...createEmptyBoardState(20, 20),
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
              findUnique: jest.fn().mockResolvedValue({ status: 'IN_PROGRESS', version: 1 }),
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
        // Реальная ELO-формула: calculateNewRatings чистый, prisma не трогается
        RatingService,
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

    it('should hide deck top cards from both players', () => {
      const filtered = service.filterPrivateData(mockGameState, 'player1');

      expect(filtered.decks.player1.topCard).toBeUndefined();
      expect(filtered.decks.player2.topCard).toBeUndefined();
    });

    it('should keep own cards visible', () => {
      const filtered = service.filterPrivateData(mockGameState, 'player1');

      expect(filtered.handZones.player1.cards[0].name).toBe('Hand Card 1');
      expect(filtered.handZones.player1.cards[0].attackValue).toBe(5);
    });

    it('uses a masked allowlist for opponent hands, excluding identity, type and extra private fields', () => {
      const secret = { ...mockGameState.handZones.player2.cards[0], id: 'private-instance', cardId: 'private-definition',
        cardType: CardType.SCHEME, bannerName: 'private-banner', text: 'private-text', futurePrivateField: 'private-extra' };
      const state = { ...mockGameState, handZones: { ...mockGameState.handZones,
        player2: { ...mockGameState.handZones.player2, cards: [secret] } } };
      const filtered = service.filterPrivateData(state, 'player1');
      const hand = JSON.stringify(filtered.handZones.player2);
      for (const forbidden of ['private-instance', 'private-definition', 'SCHEME', 'private-banner', 'private-text', 'private-extra']) {
        expect(hand).not.toContain(forbidden);
      }
      expect(filtered.handZones.player2.cards).toHaveLength(1);
      expect(filtered.handZones.player2.cards[0].isVisible).toBe(false);
      expect(service.filterPrivateData(state, 'player2').handZones.player2.cards[0]).toEqual(secret);
      expect(state.handZones.player2.cards[0]).toEqual(secret);
    });
  });

  describe('S03 resumable resource choices', () => {
    const pendingStates = () => [
      { ...mockGameState, phase: GamePhase.ACTION_MANEUVER,
        metadata: { ...mockGameState.metadata, actionsRemaining: 0,
          pendingManeuver: { id: 'maneuver-42', playerId: 'player1' } } },
      { ...mockGameState, phase: GamePhase.TURN_END,
        metadata: { ...mockGameState.metadata, actionsRemaining: 0,
          pendingHandDiscard: { id: 'discard-43', playerId: 'player1', count: 2 } } },
    ];

    it.each([0, 1])('restores pending stage %s after database reload and exposes its identity', async (index) => {
      const state = pendingStates()[index];
      const upsert = jest.fn().mockResolvedValue({});
      jest.spyOn(prisma, '$transaction').mockImplementation(async (callback: any) => callback({
        gameState: { findUnique: jest.fn().mockResolvedValue(null), upsert },
        game: { updateMany: jest.fn().mockResolvedValue({ count: 1 }) },
      }));
      await service.saveState(state.gameId, state);
      const stored = JSON.parse(JSON.stringify(upsert.mock.calls[0][0].create.state));
      jest.spyOn(redis, 'getJson').mockResolvedValue(null);
      jest.spyOn(prisma.gameState, 'findUnique').mockResolvedValue({ state: stored } as any);
      const restored = await service.loadState(state.gameId);
      expect(restored.phase).toBe(state.phase);
      expect(restored.metadata.actionsRemaining).toBe(0);
      for (const field of ['pendingManeuver', 'pendingHandDiscard']) {
        expect((restored.metadata as any)[field]).toEqual((state.metadata as any)[field]);
        expect((service.filterPrivateData(restored, 'player1').metadata as any)[field])
          .toEqual((state.metadata as any)[field]);
        expect((redis.setJsonex as jest.Mock).mock.calls[0][2].metadata[field])
          .toEqual((state.metadata as any)[field]);
      }
    });

    it('does not expose either deck order or unrevealed instance IDs to either player', () => {
      const secretCard = { ...mockGameState.decks.player1.topCard!, id: 'future-instance', cardId: 'future-card' };
      const state = { ...mockGameState, decks: Object.fromEntries(['player1', 'player2'].map(id =>
        [id, { cards: [secretCard], drawPile: [secretCard, secretCard], topCard: secretCard }])) };
      const original = JSON.stringify(state);
      for (const viewer of ['player1', 'player2']) {
        const filtered = service.filterPrivateData(state, viewer);
        for (const deck of Object.values(filtered.decks)) {
          expect(deck.topCard).toBeUndefined();
          expect(deck.drawPile).toHaveLength(2);
          expect(JSON.stringify(deck)).not.toContain('future-instance');
          expect(JSON.stringify(deck)).not.toContain('future-card');
          expect(JSON.stringify(deck)).not.toContain('Card 1');
        }
        expect(filtered.handZones[viewer]).toEqual(state.handZones[viewer]);
      }
      expect(JSON.stringify(state)).toBe(original);
    });

    it('accepts legacy snapshots without pending resource choices', () => {
      const restored = service.deserialize(JSON.parse(JSON.stringify(service.serialize(mockGameState))));
      expect((restored.metadata as any).pendingManeuver).toBeUndefined();
      expect((restored.metadata as any).pendingHandDiscard).toBeUndefined();
    });
  });

  describe('GD-036 terminal state marks the Game row FINISHED', () => {
    const statsRows = () => [
      { userId: 'player1', gamesPlayed: 4, gamesWon: 2, gamesLost: 2, currentElo: 1400, peakElo: 1450 },
      { userId: 'player2', gamesPlayed: 3, gamesWon: 1, gamesLost: 2, currentElo: 1300, peakElo: 1350 },
    ];

    const saveWithMocks = async (
      state: any,
      extra: { rows?: any[]; expectConflict?: boolean } = {},
    ) => {
      const updateMany = jest.fn().mockResolvedValue({ count: 1 });
      const statsUpdate = jest.fn();
      const statsCreateMany = jest.fn();
      const queryRaw = jest.fn().mockResolvedValue(extra.rows ?? statsRows());
      jest.spyOn(prisma.game, 'findUnique').mockResolvedValue({
        status: state.phase === GamePhase.GAME_OVER ? 'FINISHED' : 'IN_PROGRESS',
        version: state.sequenceNumber,
      } as any);
      jest.spyOn(prisma, '$transaction').mockImplementation(async (callback: any) => callback({
        gameState: { findUnique: jest.fn().mockResolvedValue(null), upsert: jest.fn() },
        game: { updateMany, findUnique: jest.fn().mockResolvedValue({ hostId: 'player1', opponentId: 'player2' }) },
        userStats: { createMany: statsCreateMany, update: statsUpdate },
        $queryRaw: queryRaw,
      }));
      (redis.del as jest.Mock).mockClear();
      if (extra.expectConflict) {
        await expect(service.saveState(state.gameId, state)).rejects.toThrow(ConflictException);
      } else {
        await service.saveState(state.gameId, state);
      }
      return { updateMany, statsUpdate, statsCreateMany, queryRaw };
    };

    it('marks an in-progress game FINISHED with winnerId/endedAt', async () => {
      const state = {
        ...mockGameState,
        phase: GamePhase.GAME_OVER,
        metadata: { ...mockGameState.metadata, winnerId: 'player2' },
      };
      const { updateMany } = await saveWithMocks(state);
      expect(updateMany).toHaveBeenCalledTimes(1);
      const args = updateMany.mock.calls[0][0];
      expect(args.where).toEqual({ id: state.gameId, status: 'IN_PROGRESS' });
      expect(args.data.status).toBe('FINISHED');
      expect(args.data.winnerId).toBe('player2');
      expect(args.data.endedAt).toBeInstanceOf(Date);
      expect(args.data.version).toBe(state.sequenceNumber);
      // myGames cache invalidated for BOTH participants
      const delKeys = (redis.del as jest.Mock).mock.calls.map((c: any[]) => c[0]);
      expect(delKeys).toContain(`game:${state.gameId}`);
      expect(delKeys).toContain('games:list:player1:IN_PROGRESS');
      expect(delKeys).toContain('games:list:player2:all');
    });

    it('continues evicting the remaining cache keys when one del fails', async () => {
      const state = {
        ...mockGameState,
        phase: GamePhase.GAME_OVER,
        metadata: { ...mockGameState.metadata, winnerId: 'player1' },
      };
      // первый ключ (game:game1) падает Redis-сбоем — остальные 12 обязаны
      // быть попытаны, а не брошены: getGame перечитает терминальный статус,
      // но списки myGames чинятся только этими del
      const delSpy = jest.spyOn(redis, 'del')
        .mockRejectedValueOnce(new Error('ECONNREFUSED'))
        .mockResolvedValue(1);
      await saveWithMocks(state);

      const delKeys = delSpy.mock.calls.map((c: any[]) => c[0]);
      expect(delKeys).toHaveLength(13);
      expect(delKeys).toContain('game:game1');
      expect(delKeys).toContain('games:list:player2:FINISHED');
      expect(delKeys).toContain('games:list:player1:all');
    });

    it('only finishes a terminal state while live states update version', async () => {
      const over = {
        ...mockGameState,
        phase: GamePhase.GAME_OVER,
        metadata: { ...mockGameState.metadata, winnerId: 'player1' },
      };
      const terminal = await saveWithMocks(over);
      // Only an IN_PROGRESS row can become FINISHED; ABORTED is excluded too.
      expect(terminal.updateMany.mock.calls[0][0].where.status).toBe('IN_PROGRESS');
      expect(terminal.updateMany.mock.calls[0][0].data.status).toBe('FINISHED');

      const live = await saveWithMocks({ ...mockGameState, phase: GamePhase.ACTION_MANEUVER });
      expect(live.updateMany.mock.calls[0][0]).toEqual({
        where: { id: mockGameState.gameId, status: 'IN_PROGRESS' },
        data: { version: mockGameState.sequenceNumber },
      });
      expect(live.statsUpdate).not.toHaveBeenCalled();
    });

    describe('GD-036 finish updates both players stats exactly once (incl. ELO)', () => {
      it('applies winner/loser stats inside the finish transaction', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          metadata: { ...mockGameState.metadata, winnerId: 'player1' },
        };
        // 1400 vs 1300 (RatingService, K=32): winner +11.52 -> 1412, loser -11.52 -> 1288
        const { statsUpdate, statsCreateMany, queryRaw } = await saveWithMocks(state);

        // Missing rows are created atomically (ON CONFLICT DO NOTHING)
        expect(statsCreateMany).toHaveBeenCalledWith({
          data: [{ userId: 'player1' }, { userId: 'player2' }],
          skipDuplicates: true,
        });
        // Both rows locked FOR UPDATE in deterministic order before the read
        const rawSql = String(queryRaw.mock.calls[0][0].sql);
        expect(rawSql).toContain('FOR UPDATE');
        expect(rawSql).toContain('ORDER BY');

        expect(statsUpdate).toHaveBeenCalledTimes(2);
        const winnerUpdate = statsUpdate.mock.calls[0][0];
        expect(winnerUpdate.where).toEqual({ userId: 'player1' });
        expect(winnerUpdate.data).toMatchObject({
          gamesPlayed: 5,
          gamesWon: 3,
          winRate: 60,
          currentElo: 1412,
          peakElo: 1450,
          lastPlayedAt: expect.any(Date),
        });
        const loserUpdate = statsUpdate.mock.calls[1][0];
        expect(loserUpdate.where).toEqual({ userId: 'player2' });
        expect(loserUpdate.data).toMatchObject({
          gamesPlayed: 4,
          gamesLost: 3,
          winRate: 25,
          currentElo: 1288,
          lastPlayedAt: expect.any(Date),
        });
        // Проигравший не поднимает peakElo
        expect(loserUpdate.data.peakElo).toBeUndefined();
      });

      it('raises peakElo past the previous peak for the winner', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          metadata: { ...mockGameState.metadata, winnerId: 'player1' },
        };
        const rows = statsRows();
        rows[0] = { ...rows[0], currentElo: 1440, peakElo: 1444 };
        // 1440 vs 1300: E=0.6911 -> +9.88 -> 1450 > peak 1444
        const { statsUpdate } = await saveWithMocks(state, { rows });
        expect(statsUpdate.mock.calls[0][0].data.peakElo).toBe(1450);
      });

      it('is idempotent: a second terminal save conflicts before touching stats', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          metadata: { ...mockGameState.metadata, winnerId: 'player1' },
        };
        const gameStateUpsert = jest.fn();
        const statsUpdate = jest.fn();
        jest.spyOn(prisma, '$transaction').mockImplementation(async (callback: any) => callback({
          gameState: { findUnique: jest.fn().mockResolvedValue(null), upsert: gameStateUpsert },
          game: { updateMany: jest.fn().mockResolvedValue({ count: 0 }) },
          userStats: { createMany: jest.fn(), update: statsUpdate },
          $queryRaw: jest.fn(),
        }));
        await expect(service.saveState(state.gameId, state)).rejects.toThrow(ConflictException);
        expect(statsUpdate).not.toHaveBeenCalled();
        expect(gameStateUpsert).not.toHaveBeenCalled();
      });

      it('applies draw stats to both seats without win/loss counters', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          metadata: { ...mockGameState.metadata, winnerId: undefined },
        };
        // 1400 vs 1300, S=0.5 (K=32): -4.48 -> 1396 / +4.48 -> 1304
        const { statsUpdate, statsCreateMany, queryRaw } = await saveWithMocks(state);

        expect(statsCreateMany).toHaveBeenCalledWith({
          data: [{ userId: 'player1' }, { userId: 'player2' }],
          skipDuplicates: true,
        });
        const rawSql = String(queryRaw.mock.calls[0][0].sql);
        expect(rawSql).toContain('FOR UPDATE');

        expect(statsUpdate).toHaveBeenCalledTimes(2);
        const firstUpdate = statsUpdate.mock.calls[0][0];
        expect(firstUpdate.where).toEqual({ userId: 'player1' });
        expect(firstUpdate.data).toMatchObject({
          gamesPlayed: 5,
          winRate: 40,
          currentElo: 1396,
          peakElo: 1450,
          lastPlayedAt: expect.any(Date),
        });
        expect(firstUpdate.data).not.toHaveProperty('gamesWon');
        expect(firstUpdate.data).not.toHaveProperty('gamesLost');
        const secondUpdate = statsUpdate.mock.calls[1][0];
        expect(secondUpdate.where).toEqual({ userId: 'player2' });
        expect(secondUpdate.data).toMatchObject({
          gamesPlayed: 4,
          winRate: 25,
          currentElo: 1304,
          peakElo: 1350,
        });
        // Снимок всё равно сохранён
        expect(prisma.$transaction).toHaveBeenCalled();
      });

      it('keeps ELO unchanged and raises peakElo on a favorable draw', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          metadata: { ...mockGameState.metadata, winnerId: undefined },
        };
        const rows = statsRows();
        rows[0] = { ...rows[0], currentElo: 1300, peakElo: 1300 };
        // Равные рейтинги: S=0.5 при E=0.5 -> нулевой сдвиг
        const equalRatings = await saveWithMocks(state, {
          rows: [rows[0], { ...rows[1], currentElo: 1300, peakElo: 1250 }],
        });
        expect(equalRatings.statsUpdate.mock.calls[0][0].data.currentElo).toBe(1300);
        expect(equalRatings.statsUpdate.mock.calls[0][0].data.peakElo).toBe(1300);
        // Благоприятная ничья поднимает peakElo: 1000 vs 1300 -> +11 -> 1011
        const favorable = await saveWithMocks(state, {
          rows: [
            { ...rows[0], currentElo: 1000, peakElo: 1000 },
            { ...rows[1], currentElo: 1300, peakElo: 1300 },
          ],
        });
        expect(favorable.statsUpdate.mock.calls[0][0].data).toMatchObject({
          currentElo: 1011,
          peakElo: 1011,
        });
      });

      it('rolls back FINISHED when the winner is not a persisted participant', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          metadata: { ...mockGameState.metadata, winnerId: 'intruder' },
        };
        const { statsUpdate, statsCreateMany } = await saveWithMocks(state, { expectConflict: true });
        expect(statsUpdate).not.toHaveBeenCalled();
        expect(statsCreateMany).not.toHaveBeenCalled();
      });

      it('rolls back FINISHED for a non-duel player list', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          players: [mockGameState.players[0]],
          metadata: { ...mockGameState.metadata, winnerId: 'player1' },
        };
        const { statsUpdate, statsCreateMany } = await saveWithMocks(state, { expectConflict: true });
        expect(statsUpdate).not.toHaveBeenCalled();
        expect(statsCreateMany).not.toHaveBeenCalled();
      });

      it('rolls back FINISHED when state players disagree with the persisted Game composition', async () => {
        const state = {
          ...mockGameState,
          phase: GamePhase.GAME_OVER,
          players: [
            mockGameState.players[0],
            { ...mockGameState.players[1], userId: 'player3' },
          ],
          metadata: { ...mockGameState.metadata, winnerId: 'player1' },
        };
        const { statsUpdate, statsCreateMany, queryRaw } = await saveWithMocks(state, { expectConflict: true });
        expect(statsUpdate).not.toHaveBeenCalled();
        expect(statsCreateMany).not.toHaveBeenCalled();
        expect(queryRaw).not.toHaveBeenCalled();
      });
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

    it('bypasses an older cached snapshot after a newer game version commits', async () => {
      jest.spyOn(redis, 'getJson').mockResolvedValue(mockGameState);
      jest.spyOn(prisma.game, 'findUnique').mockResolvedValue({
        status: 'IN_PROGRESS', version: mockGameState.sequenceNumber + 1,
      } as any);

      await expect(service.getCachedState('game1')).resolves.toBeNull();
      expect(redis.del).not.toHaveBeenCalled();
    });

    // S09 regression: Redis сериализует состояние через JSON, поэтому на
    // cache-hit Date-поля приходят ISO-строками. Executor/guard'ы зовут
    // .getTime() напрямую ('timeoutAt.getTime is not a function' ронял
    // playDefense/resolveCombat в live-игре); кеш-путь обязан оживлять
    // даты так же, как DB-путь через deserialize.
    it('revives Date fields from a JSON-roundtripped cache hit', async () => {
      const startedAt = new Date('2026-01-01T00:00:00.000Z');
      const timeoutAt = new Date('2026-01-01T00:00:30.000Z');
      const roundtripped = JSON.parse(
        JSON.stringify({
          ...mockGameState,
          metadata: {
            ...mockGameState.metadata,
            lastActionAt: startedAt,
            combatInfo: {
              attackerId: 'fighter1',
              defenderId: 'player2',
              targetFighterId: 'fighter2',
              startedAt,
              timeoutAt,
            },
          },
        }),
      );
      expect(typeof roundtripped.metadata.lastActionAt).toBe('string');

      jest.spyOn(redis, 'getJson').mockResolvedValue(roundtripped);

      const cached = await service.getCachedState('game1');

      expect(cached).not.toBeNull();
      expect(cached!.metadata.lastActionAt).toBeInstanceOf(Date);
      expect(cached!.metadata.lastActionAt.getTime()).toBe(startedAt.getTime());
      expect(cached!.metadata.combatInfo!.startedAt).toBeInstanceOf(Date);
      expect(cached!.metadata.combatInfo!.startedAt.getTime()).toBe(startedAt.getTime());
      expect(cached!.metadata.combatInfo!.timeoutAt).toBeInstanceOf(Date);
      expect(cached!.metadata.combatInfo!.timeoutAt!.getTime()).toBe(timeoutAt.getTime());
    });

    it('keeps combatInfo undefined on a cache hit without combat', async () => {
      jest.spyOn(redis, 'getJson').mockResolvedValue(mockGameState);

      const cached = await service.getCachedState('game1');

      expect(cached!.metadata.combatInfo).toBeUndefined();
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
      expect(initialState.handZones.player1.maxSize).toBe(7);
      expect(initialState.handZones.player2.maxSize).toBe(7);
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
    it('accepts the initial nonterminal save once startGame has set IN_PROGRESS', async () => {
      jest.spyOn(prisma.gameState, 'findUnique').mockResolvedValue(null);
      jest.spyOn(prisma.gameState, 'upsert').mockResolvedValue({} as any);
      jest.spyOn(redis, 'setJsonex').mockResolvedValue('OK');
      jest.spyOn(gameSubscriptionService, 'publishGameUpdate').mockResolvedValue(undefined);

      const guardedUpdate = jest.fn().mockResolvedValue({ count: 1 });
      const transactionMock = jest.fn().mockImplementation(async (callback) => {
        return callback({
          gameState: {
            findUnique: jest.fn().mockResolvedValue(null),
            upsert: jest.fn().mockResolvedValue({} as any),
          },
          game: { updateMany: guardedUpdate },
        });
      });
      jest.spyOn(prisma, '$transaction').mockImplementation(transactionMock);

      await service.saveState('game1', mockGameState);

      expect(prisma.$transaction).toHaveBeenCalled();
      expect(guardedUpdate).toHaveBeenCalledWith({
        where: { id: 'game1', status: 'IN_PROGRESS' },
        data: { version: mockGameState.sequenceNumber },
      });
      expect(redis.setJsonex).toHaveBeenCalled();
      expect(gameSubscriptionService.publishGameUpdate).toHaveBeenCalledWith(
        'game1',
        'STATE_UPDATED',
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
          game: { updateMany: jest.fn().mockResolvedValue({ count: 1 }) },
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

  describe('S02 paused combat persistence', () => {
    const pausedState = (): GameState => ({
      ...mockGameState,
      phase: GamePhase.COMBAT_RESOLVE,
      metadata: {
        ...mockGameState.metadata,
        pendingEffects: [{ id: 'choice-1', type: 'MOVE', playerId: 'player2', value: 2 }],
        combatEffectContinuation: {
          stage: 'AFTER_COMBAT', attackerCardCancelled: true, defenderCardCancelled: false,
          finalAttack: 5, finalDefense: 3, preventDamageToAttacker: false, preventDamageToDefender: true,
          remaining: [{
            effect: { id: 'draw', type: EffectType.DRAW_CARD, timing: EffectTiming.AFTER_COMBAT, value: 1 },
            isAttacker: false,
            context: {
              playerId: 'player2', fighterId: 'fighter2', opposingFighterId: 'fighter1',
              card: { id: 'defense::1', cardId: 'defense', name: 'Defense', nameEn: 'Defense', nameRu: 'Защита', cardType: CardType.DEFENSE, effects: [] },
              wonCombat: true, damageDealt: 0, damageTaken: 0,
              combat: { attackerFighterId: 'fighter1', targetFighterId: 'fighter2',
                attackerPlayerId: 'player1', defenderPlayerId: 'player2', attackCardId: 'attack::1',
                defenseCardId: 'defense::1', attackValue: 5, defenseValue: 3 },
            },
          }],
        },
        combatResolutionProgress: {
          defeatedBefore: ['sidekick1'],
          reveal: { attackerCardCancelled: true, defenderCardCancelled: false, appliedEffects: [], manualEffects: [] },
          damage: { finalAttack: 5, finalDefense: 3, attackerDamage: 0, defenderDamage: 0, attackerWon: false },
          after: { appliedEffects: [], manualEffects: [], paused: true },
        },
      },
    });

    it('retains ordered contexts, cancellation, numerical outcomes and progress through stored JSON', () => {
      const state = pausedState();
      const restored = service.deserialize(JSON.parse(JSON.stringify(service.serialize(state))));
      expect(restored.phase).toBe(GamePhase.COMBAT_RESOLVE);
      expect(restored.metadata.combatEffectContinuation).toEqual(state.metadata.combatEffectContinuation);
      expect(restored.metadata.combatResolutionProgress).toEqual(state.metadata.combatResolutionProgress);
      expect(restored.metadata.pendingEffects).toEqual(state.metadata.pendingEffects);
    });

    it('does not expose internal continuation payloads in player-filtered state', () => {
      const state = pausedState();
      const filtered = service.filterPrivateData(state, 'player1');
      expect(filtered.metadata.combatEffectContinuation).toBeUndefined();
      expect(filtered.metadata.combatResolutionProgress).toBeUndefined();
      expect(filtered.metadata.pendingEffects).toEqual(state.metadata.pendingEffects);
      expect(state.metadata.combatEffectContinuation).toBeDefined();
    });

    it('persists the complete server continuation to the database and cache', async () => {
      const state = pausedState();
      const upsert = jest.fn().mockResolvedValue({});
      jest.spyOn(prisma, '$transaction').mockImplementation(async (callback: any) => callback({
        gameState: { findUnique: jest.fn().mockResolvedValue(null), upsert },
        game: { updateMany: jest.fn().mockResolvedValue({ count: 1 }) },
      }));
      await service.saveState(state.gameId, state);
      const stored = service.deserialize(JSON.parse(JSON.stringify(upsert.mock.calls[0][0].create.state)));
      expect(stored.metadata.combatEffectContinuation).toEqual(state.metadata.combatEffectContinuation);
      expect(stored.metadata.combatResolutionProgress).toEqual(state.metadata.combatResolutionProgress);
      const cached = (redis.setJsonex as jest.Mock).mock.calls[0][2];
      expect(cached.metadata.combatEffectContinuation).toEqual(state.metadata.combatEffectContinuation);
      expect(cached.metadata.combatResolutionProgress).toEqual(state.metadata.combatResolutionProgress);
    });

    it('strips the execution queue but keeps the reveal flag for per-player subscription filtering', async () => {
      const state = pausedState();
      const publish = jest.fn().mockResolvedValue(1);
      const subscriptions = new GameSubscriptionService({ publish } as unknown as RedisService);
      await subscriptions.publishGameUpdate(state.gameId, 'STATE_UPDATED', state);
      const event = JSON.parse(publish.mock.calls[0][1]);
      // Очередь исполнения не публикуется никогда
      expect(event.gameState.metadata.combatEffectContinuation).toBeUndefined();
      expect(event.gameState.metadata.pendingEffects).toEqual(state.metadata.pendingEffects);
      // S05: combatResolutionProgress ДОЛЖЕН дожить до per-player
      // filterPrivateData в резолвере подписки — это флаг «reveal уже был»
      // (пост-reveal паузы публичны, rulebook p.12-13); сама фильтрация ниже
      expect(event.gameState.metadata.combatResolutionProgress).toEqual(state.metadata.combatResolutionProgress);
      expect(state.metadata.combatEffectContinuation).toBeDefined();
      expect(state.metadata.combatResolutionProgress).toBeDefined();

      // Per-player фильтр резолвера: прогресс вырезан, обе стороны видят
      // reveal-личины (pausedState = пост-reveal пауза AFTER_COMBAT)
      for (const viewer of ['player1', 'player2'] as const) {
        const filtered = service.filterPrivateData(event.gameState, viewer);
        expect(filtered.metadata.combatResolutionProgress).toBeUndefined();
        expect(filtered.metadata.combatEffectContinuation).toBeUndefined();
        expect(filtered.metadata.pendingEffects).toEqual(state.metadata.pendingEffects);
      }
    });

    it('accepts legacy saves without continuation fields', () => {
      const restored = service.deserialize(JSON.parse(JSON.stringify(service.serialize(mockGameState))));
      expect(restored.metadata.combatEffectContinuation).toBeUndefined();
      expect(restored.metadata.combatResolutionProgress).toBeUndefined();
    });
  });

  describe('A0: round-trip combatInfo/winnerId/passCount/heroSlug', () => {
    // Раньше serialize ТЕРЯЛ combatInfo/winnerId/passCount — бой выживал
    // только в Redis-кеше (TTL), после вылета кеша resolveCombat падал
    // с 'No combat in progress'
    it('combatInfo переживает serialize → deserialize', () => {
      const startedAt = new Date('2026-06-12T10:00:00.000Z');
      const withCombat: GameState = {
        ...mockGameState,
        metadata: {
          ...mockGameState.metadata,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2-sk0',
            attackerCardId: 'card-a::1',
            defenderCardId: 'card-d::2',
            attackValue: 4,
            defenseValue: 3,
            startedAt,
          },
          passCount: 1,
          winnerId: 'player1',
          actionsRemaining: 1,
        },
      };

      const restored = service.deserialize(service.serialize(withCombat));

      expect(restored.metadata.combatInfo).toBeDefined();
      expect(restored.metadata.combatInfo!.attackerId).toBe('fighter1');
      expect(restored.metadata.combatInfo!.defenderId).toBe('player2');
      expect(restored.metadata.combatInfo!.targetFighterId).toBe('fighter2-sk0');
      expect(restored.metadata.combatInfo!.attackerCardId).toBe('card-a::1');
      expect(restored.metadata.combatInfo!.defenderCardId).toBe('card-d::2');
      expect(restored.metadata.combatInfo!.attackValue).toBe(4);
      expect(restored.metadata.combatInfo!.defenseValue).toBe(3);
      expect(restored.metadata.combatInfo!.startedAt.toISOString()).toBe(
        startedAt.toISOString(),
      );
      expect(restored.metadata.passCount).toBe(1);
      expect(restored.metadata.winnerId).toBe('player1');
    });

    it('без боя combatInfo остаётся undefined (легаси-сейвы живы)', () => {
      const restored = service.deserialize(service.serialize(mockGameState));
      expect(restored.metadata.combatInfo).toBeUndefined();
      expect(restored.metadata.winnerId).toBeUndefined();
    });

    it('GD-017: boost-слоты (bv/cbc/abc) переживают serialize → deserialize', () => {
      const withBoost: GameState = {
        ...mockGameState,
        metadata: {
          ...mockGameState.metadata,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a::1',
            attackValue: 3,
            boostValue: 3,
            cardBoostCardId: 'boost::1',
            abilityBoostCardId: 'ab::2',
            defenseValue: 0,
            startedAt: new Date(0),
          },
        },
      };
      const restored = service.deserialize(service.serialize(withBoost));
      expect(restored.metadata.combatInfo!.boostValue).toBe(3);
      expect(restored.metadata.combatInfo!.cardBoostCardId).toBe('boost::1');
      expect(restored.metadata.combatInfo!.abilityBoostCardId).toBe('ab::2');
    });

    it('GD-017/R-15: в фазе COMBAT boost-слоты видны только атакатору (face-down)', () => {
      const withBoost: GameState = {
        ...mockGameState,
        phase: GamePhase.COMBAT,
        metadata: {
          ...mockGameState.metadata,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a::1',
            attackValue: 3,
            boostValue: 3,
            cardBoostCardId: 'boost::1',
            abilityBoostCardId: 'ab::2',
            defenseValue: 0,
            startedAt: new Date(0),
          },
        },
      };

      const attackerView = service.filterPrivateData(withBoost, 'player1');
      expect(attackerView.metadata.combatInfo!.boostValue).toBe(3);
      expect(attackerView.metadata.combatInfo!.abilityBoostCardId).toBe('ab::2');

      const defenderView = service.filterPrivateData(withBoost, 'player2');
      expect(defenderView.metadata.combatInfo!.boostValue).toBeUndefined();
      expect(defenderView.metadata.combatInfo!.cardBoostCardId).toBeUndefined();
      expect(defenderView.metadata.combatInfo!.abilityBoostCardId).toBeUndefined();
      // GD-025 (S07): до reveal значение и личина атакующей карты скрыты
      // от защитника; участники боя видны обоим
      expect(defenderView.metadata.combatInfo!.attackValue).toBeUndefined();
      expect(defenderView.metadata.combatInfo!.attackerCardId).toBeUndefined();
      expect(defenderView.metadata.combatInfo!.attackerId).toBe('fighter1');
      // входное состояние не мутировано
      expect(withBoost.metadata.combatInfo!.boostValue).toBe(3);
    });

    it('GD-017: вне фазы COMBAT boost-слоты не вырезаются (бой вскрыт)', () => {
      const resolved: GameState = {
        ...mockGameState,
        phase: GamePhase.ACTION_MANEUVER,
        metadata: {
          ...mockGameState.metadata,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a::1',
            attackValue: 3,
            boostValue: 3,
            cardBoostCardId: 'boost::1',
            abilityBoostCardId: 'ab::2',
            defenseValue: 2,
            startedAt: new Date(0),
          },
        },
      };
      const view = service.filterPrivateData(resolved, 'player2');
      expect(view.metadata.combatInfo!.boostValue).toBe(3);
      expect(view.metadata.combatInfo!.abilityBoostCardId).toBe('ab::2');
    });

    it('GD-020: до reveal committed-карты боя скрыты из discardPiles для другого игрока (COMBAT)', () => {
      const inCombat: GameState = {
        ...mockGameState,
        phase: GamePhase.COMBAT,
        discardPiles: {
          player1: [
            { id: 'card-a::1', cardId: 'card-a', name: 'Attack', nameEn: 'Attack', nameRu: 'Attack', cardType: CardType.ATTACK },
            { id: 'old::0', cardId: 'old', name: 'Old Scheme', nameEn: 'Old Scheme', nameRu: 'Old Scheme', cardType: CardType.SCHEME },
          ],
          player2: [],
        },
        metadata: {
          ...mockGameState.metadata,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a::1',
            attackValue: 3,
            boostValue: 4,
            cardBoostCardId: 'boost::1',
            defenseValue: 0,
            startedAt: new Date(0),
          },
        },
      };

      // Защитник не видит личину committed attack/boost карт (плейсхолдеры),
      // но видит факт коммита (длина) и свой ДОбоевый сброс атакатора.
      const defenderView = service.filterPrivateData(inCombat, 'player2');
      const pile = defenderView.discardPiles.player1;
      expect(pile).toHaveLength(2);
      expect(pile.map((c) => c.id)).toEqual(['hidden-0', 'old::0']);
      expect(pile[0].name).toBe('???');
      expect(defenderView.metadata.combatInfo!.boostValue).toBeUndefined();

      // Атакатор видит свои committed-карты полностью
      const attackerView = service.filterPrivateData(inCombat, 'player1');
      expect(attackerView.discardPiles.player1.map((c) => c.id)).toEqual(['card-a::1', 'old::0']);
      expect(attackerView.metadata.combatInfo!.boostValue).toBe(4);

      // Входное состояние не мутировано
      expect(inCombat.discardPiles.player1[0].name).toBe('Attack');
    });

    it('GD-020: COMBAT_RESOLVE — защитная карта скрыта от атакатора до reveal', () => {
      const defended: GameState = {
        ...mockGameState,
        phase: GamePhase.COMBAT_RESOLVE,
        discardPiles: {
          player1: [{ id: 'card-a::1', cardId: 'card-a', name: 'Attack', nameEn: 'Attack', nameRu: 'Attack', cardType: CardType.ATTACK }],
          player2: [{ id: 'def::1', cardId: 'def', name: 'Defense', nameEn: 'Defense', nameRu: 'Defense', cardType: CardType.DEFENSE }],
        },
        metadata: {
          ...mockGameState.metadata,
          combatInfo: {
            attackerId: 'fighter1',
            defenderId: 'player2',
            targetFighterId: 'fighter2',
            attackerCardId: 'card-a::1',
            attackValue: 3,
            defenseValue: 2,
            defenderCardId: 'def::1',
            startedAt: new Date(0),
          },
        },
      };

      const attackerView = service.filterPrivateData(defended, 'player1');
      expect(attackerView.discardPiles.player2.map((c) => c.id)).toEqual(['hidden-0']);
      expect(attackerView.metadata.combatInfo!.boostValue).toBeUndefined();

      // Защитник видит свою карту
      const defenderView = service.filterPrivateData(defended, 'player2');
      expect(defenderView.discardPiles.player2.map((c) => c.id)).toEqual(['def::1']);
    });

    it('GD-020: после боя (combatInfo снят) сброс виден обоим полностью', () => {
      const resolved: GameState = {
        ...mockGameState,
        phase: GamePhase.ACTION_MANEUVER,
        discardPiles: {
          player1: [{ id: 'card-a::1', cardId: 'card-a', name: 'Attack', nameEn: 'Attack', nameRu: 'Attack', cardType: CardType.ATTACK }],
          player2: [],
        },
        metadata: { ...mockGameState.metadata },
      };
      const view = service.filterPrivateData(resolved, 'player2');
      expect(view.discardPiles.player1.map((c) => c.id)).toEqual(['card-a::1']);
    });

    // S05 P2-1: обе карты вскрываются ВМЕСТЕ до DURING_COMBAT-выборов
    // (rulebook BoL Vol.1, p.12-13) — reveal = запуск executeResolveCombat,
    // серверный маркер = живой combatResolutionProgress.
    describe('S05: reveal-видимость пост-reveal пауз (rulebook p.12-13)', () => {
      const attackCard = { id: 'card-a::1', cardId: 'card-a', name: 'Attack', nameEn: 'Attack', nameRu: 'Атака', cardType: CardType.ATTACK };
      const abilityBoostCard = { id: 'ab::2', cardId: 'ab', name: 'Excalibur', nameEn: 'Excalibur', nameRu: 'Экскалибур', cardType: CardType.VERSATILE };
      const defenseCard = { id: 'def::1', cardId: 'def', name: 'Defense', nameEn: 'Defense', nameRu: 'Защита', cardType: CardType.DEFENSE };
      const oldScheme = { id: 'old::0', cardId: 'old', name: 'Old Scheme', nameEn: 'Old Scheme', nameRu: 'Old Scheme', cardType: CardType.SCHEME };

      const combatBase = {
        attackerId: 'fighter1',
        defenderId: 'player2',
        targetFighterId: 'fighter2',
        attackerCardId: 'card-a::1',
        defenderCardId: 'def::1',
        attackValue: 3,
        boostValue: 3,
        abilityBoostCardId: 'ab::2',
        defenseValue: 2,
        startedAt: new Date(0),
      };

      const pausedDiscardPiles = () => ({
        player1: [attackCard, abilityBoostCard, oldScheme],
        player2: [defenseCard],
      });

      const handZonesWithBoostCandidate = () => ({
        player1: {
          cards: [
            { id: 'hand1', cardId: 'hand1', name: 'Hand Card 1', nameEn: 'Hand Card 1', nameRu: 'Карта в руке 1', cardType: CardType.ATTACK, attackValue: 5, isVisible: true },
            { id: 'boost-cand::9', cardId: 'ss', name: 'Second Shot', nameEn: 'Second Shot', nameRu: 'Second Shot', cardType: CardType.SCHEME, isVisible: true },
          ],
          maxSize: 5,
        },
        player2: { ...mockGameState.handZones.player2 },
      });

      const boostChoicePending = [
        { id: 'e5-boost-9', type: 'BOOST_CHOICE' as const, playerId: 'player1', optional: true, text: 'You may BOOST this attack' },
      ];

      it('после атаки / до защиты (COMBAT, reveal не начался): committed-карты скрыты, факт коммита виден', () => {
        const state: GameState = {
          ...mockGameState,
          phase: GamePhase.COMBAT,
          discardPiles: { player1: [attackCard, abilityBoostCard, oldScheme], player2: [] },
          metadata: { ...mockGameState.metadata,
            combatInfo: { ...combatBase, defenderCardId: undefined, defenseValue: 0 } },
        };

        const defenderView = service.filterPrivateData(state, 'player2');
        const pile = defenderView.discardPiles.player1;
        expect(pile).toHaveLength(3);
        expect(pile.map((c) => c.id)).toEqual(['hidden-0', 'hidden-1', 'old::0']);
        expect(pile[0].name).toBe('???');
        expect(defenderView.metadata.combatInfo!.boostValue).toBeUndefined();
        expect(defenderView.metadata.combatInfo!.abilityBoostCardId).toBeUndefined();

        const attackerView = service.filterPrivateData(state, 'player1');
        expect(attackerView.discardPiles.player1.map((c) => c.id)).toEqual(['card-a::1', 'ab::2', 'old::0']);
        expect(attackerView.metadata.combatInfo!.boostValue).toBe(3);
      });

      it('после защиты / до reveal (COMBAT_RESOLVE без прогресса): обе committed-личины скрыты от соперника', () => {
        const state: GameState = {
          ...mockGameState,
          phase: GamePhase.COMBAT_RESOLVE,
          discardPiles: pausedDiscardPiles(),
          metadata: { ...mockGameState.metadata, combatInfo: { ...combatBase } },
        };

        const attackerView = service.filterPrivateData(state, 'player1');
        expect(attackerView.discardPiles.player2.map((c) => c.id)).toEqual(['hidden-0']);
        expect(attackerView.discardPiles.player1.map((c) => c.id)).toEqual(['card-a::1', 'ab::2', 'old::0']);

        const defenderView = service.filterPrivateData(state, 'player2');
        expect(defenderView.discardPiles.player1.map((c) => c.id)).toEqual(['hidden-0', 'hidden-1', 'old::0']);
        expect(defenderView.discardPiles.player2.map((c) => c.id)).toEqual(['def::1']);
        expect(defenderView.metadata.combatInfo!.boostValue).toBeUndefined();
      });

      it('пауза BOOST_CHOICE после reveal: обе личины + committed Arthur-boost открыты ОБОИМ, руки не текут', () => {
        const state: GameState = {
          ...mockGameState,
          phase: GamePhase.COMBAT_RESOLVE,
          discardPiles: pausedDiscardPiles(),
          handZones: handZonesWithBoostCandidate(),
          metadata: {
            ...mockGameState.metadata,
            combatInfo: { ...combatBase },
            pendingEffects: boostChoicePending,
            combatResolutionProgress: {
              defeatedBefore: [],
              reveal: { attackerCardCancelled: false, defenderCardCancelled: false, appliedEffects: [], manualEffects: [] },
              calculation: { paused: true, finalAttack: 6, finalDefense: 2, attackerCardCancelled: false, defenderCardCancelled: false, preventDamageToAttacker: false, preventDamageToDefender: false, appliedEffects: [], manualEffects: [] },
            },
          } as GameState['metadata'],
        };

        for (const viewer of ['player1', 'player2'] as const) {
          const view = service.filterPrivateData(state, viewer);
          // Личины committed-карт боя открыты обоим (reveal уже был)
          expect(view.discardPiles.player1.map((c) => c.id)).toEqual(['card-a::1', 'ab::2', 'old::0']);
          expect(view.discardPiles.player1[1].name).toBe('Excalibur');
          expect(view.discardPiles.player2.map((c) => c.id)).toEqual(['def::1']);
          // boost-поля combatInfo открыты обоим после reveal
          expect(view.metadata.combatInfo!.boostValue).toBe(3);
          expect(view.metadata.combatInfo!.abilityBoostCardId).toBe('ab::2');
          // внутренний прогресс вырезан; выбор игрока сохранён
          expect(view.metadata.combatResolutionProgress).toBeUndefined();
          expect(view.metadata.pendingEffects).toEqual(boostChoicePending);
          // рука соперника — плейсхолдеры, личина boost-кандидата не течёт
          const other = viewer === 'player1' ? 'player2' : 'player1';
          const otherHand = view.handZones[other].cards;
          expect(otherHand.every((c) => c.name === '???')).toBe(true);
          const otherHandJson = JSON.stringify(view.handZones[other]);
          expect(otherHandJson).not.toContain('boost-cand::9');
          expect(otherHandJson).not.toContain('Second Shot');
        }
      });

      it('пауза defender DURING-выбора (reveal.paused): те же открытые личины обоим', () => {
        const state: GameState = {
          ...mockGameState,
          phase: GamePhase.COMBAT_RESOLVE,
          discardPiles: pausedDiscardPiles(),
          metadata: {
            ...mockGameState.metadata,
            combatInfo: { ...combatBase },
            pendingEffects: [{ id: 'm1-move-9', type: 'MOVE' as const, playerId: 'player2', value: 2 }],
            combatResolutionProgress: {
              defeatedBefore: [],
              reveal: { paused: true, attackerCardCancelled: false, defenderCardCancelled: false, appliedEffects: [], manualEffects: [] },
            },
          } as GameState['metadata'],
        };

        for (const viewer of ['player1', 'player2'] as const) {
          const view = service.filterPrivateData(state, viewer);
          expect(view.discardPiles.player1.map((c) => c.id)).toEqual(['card-a::1', 'ab::2', 'old::0']);
          expect(view.discardPiles.player2.map((c) => c.id)).toEqual(['def::1']);
          expect(view.metadata.combatInfo!.boostValue).toBe(3);
        }
      });

      it('после выбора boost-карты (cardBoostCardId закоммичен, резолв ещё на паузе): личина и значение видны обоим', () => {
        const state: GameState = {
          ...mockGameState,
          phase: GamePhase.COMBAT_RESOLVE,
          discardPiles: {
            player1: [attackCard, abilityBoostCard, { id: 'boost::1', cardId: 'ss', name: 'Second Shot', nameEn: 'Second Shot', nameRu: 'Second Shot', cardType: CardType.SCHEME }],
            player2: [defenseCard],
          },
          metadata: {
            ...mockGameState.metadata,
            combatInfo: { ...combatBase, boostValue: 4, cardBoostCardId: 'boost::1' },
            combatResolutionProgress: {
              defeatedBefore: [],
              reveal: { attackerCardCancelled: false, defenderCardCancelled: false, appliedEffects: [], manualEffects: [] },
              calculation: { paused: true, finalAttack: 7, finalDefense: 2, attackerCardCancelled: false, defenderCardCancelled: false, preventDamageToAttacker: false, preventDamageToDefender: false, appliedEffects: [], manualEffects: [] },
            },
          } as GameState['metadata'],
        };

        for (const viewer of ['player1', 'player2'] as const) {
          const view = service.filterPrivateData(state, viewer);
          expect(view.discardPiles.player1.map((c) => c.id)).toEqual(['card-a::1', 'ab::2', 'boost::1']);
          expect(view.metadata.combatInfo!.boostValue).toBe(4);
          expect(view.metadata.combatInfo!.cardBoostCardId).toBe('boost::1');
        }
      });

      it('paused reveal-флаг переживает serialize → deserialize, видимость не меняется', () => {
        const state: GameState = {
          ...mockGameState,
          phase: GamePhase.COMBAT_RESOLVE,
          discardPiles: pausedDiscardPiles(),
          handZones: handZonesWithBoostCandidate(),
          metadata: {
            ...mockGameState.metadata,
            combatInfo: { ...combatBase },
            pendingEffects: boostChoicePending,
            combatResolutionProgress: {
              defeatedBefore: [],
              reveal: { paused: true, attackerCardCancelled: false, defenderCardCancelled: false, appliedEffects: [], manualEffects: [] },
            },
          } as GameState['metadata'],
        };

        const restored = service.deserialize(JSON.parse(JSON.stringify(service.serialize(state))));
        expect(restored.metadata.combatResolutionProgress?.reveal?.paused).toBe(true);

        for (const viewer of ['player1', 'player2'] as const) {
          const direct = service.filterPrivateData(state, viewer);
          const afterRoundtrip = service.filterPrivateData(restored, viewer);
          expect(afterRoundtrip.discardPiles.player1.map((c) => c.id))
            .toEqual(direct.discardPiles.player1.map((c) => c.id));
          expect(afterRoundtrip.discardPiles.player2.map((c) => c.id))
            .toEqual(direct.discardPiles.player2.map((c) => c.id));
          expect(afterRoundtrip.metadata.combatInfo!.boostValue).toBe(3);
          expect(afterRoundtrip.metadata.combatResolutionProgress).toBeUndefined();
        }
      });
    });

    it('GD-020: DISCARD_CARDS pending переживает serialize → deserialize', () => {
      const withDiscardPending: GameState = {
        ...mockGameState,
        metadata: {
          ...mockGameState.metadata,
          pendingEffects: [
            {
              id: 'discard-choice-e1-12',
              type: 'DISCARD_CARDS',
              playerId: 'player1',
              value: 1,
              text: 'Your opponent discards 1 card.',
            },
          ],
        },
      } as GameState;
      const restored = service.deserialize(service.serialize(withDiscardPending));
      expect(restored.metadata.pendingEffects).toEqual([
        { id: 'discard-choice-e1-12', type: 'DISCARD_CARDS', playerId: 'player1', value: 1, text: 'Your opponent discards 1 card.' },
      ]);
    });

    it('per-turn action flags переживают serialize → deserialize', () => {
      const withFlags: GameState = {
        ...mockGameState,
        metadata: {
          ...mockGameState.metadata,
          maneuveredThisTurn: true,
          attackedThisTurn: true,
          lostCombatThisTurn: true,
        },
      };

      const restored = service.deserialize(service.serialize(withFlags));

      expect(restored.metadata.maneuveredThisTurn).toBe(true);
      expect(restored.metadata.attackedThisTurn).toBe(true);
      expect(restored.metadata.lostCombatThisTurn).toBe(true);
    });

    it('без флагов per-turn остаются undefined (легаси-сейвы живы)', () => {
      const restored = service.deserialize(service.serialize(mockGameState));
      expect(restored.metadata.maneuveredThisTurn).toBeUndefined();
      expect(restored.metadata.attackedThisTurn).toBeUndefined();
      expect(restored.metadata.lostCombatThisTurn).toBeUndefined();
    });

    it('heroSlug бойца переживает serialize → deserialize', () => {
      const withSlug: GameState = {
        ...mockGameState,
        fighters: mockGameState.fighters.map((f, i) =>
          i === 0 ? { ...f, heroSlug: 'ms-marvel' } : f,
        ),
      };

      const restored = service.deserialize(service.serialize(withSlug));

      expect(restored.fighters[0].heroSlug).toBe('ms-marvel');
      // без поля — undefined прозрачно проходит (легаси)
      expect(restored.fighters[1].heroSlug).toBeUndefined();
    });

    it('heroStances переживают serialize → deserialize (STANCE)', () => {
      const withStances: GameState = {
        ...mockGameState,
        metadata: {
          ...mockGameState.metadata,
          heroStances: { player1: 'sting', player2: 'big' },
        },
      };

      const restored = service.deserialize(service.serialize(withStances));

      expect(restored.metadata.heroStances).toEqual({
        player1: 'sting',
        player2: 'big',
      });
    });

    it('без heroStances остаётся undefined (легаси-сейвы живы)', () => {
      const restored = service.deserialize(service.serialize(mockGameState));
      expect(restored.metadata.heroStances).toBeUndefined();
    });
  });
});
