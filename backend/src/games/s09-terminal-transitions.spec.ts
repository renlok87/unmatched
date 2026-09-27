import { BadRequestException, ConflictException } from '@nestjs/common';
import { GameService } from './game.service';
import { GameStateService } from './game-state.service';
import { GamePhase, GameStatus } from './dto';

describe('S09 terminal transitions', () => {
  const finished = {
    id: 'g1',
    hostId: 'host',
    opponentId: 'opponent',
    status: GameStatus.FINISHED,
    winnerId: 'host',
    endedAt: new Date('2026-01-01T00:00:00Z'),
    players: [
      { userId: 'host', seatOrder: 0 },
      { userId: 'opponent', seatOrder: 1 },
    ],
  };

  const makeGameService = (game: typeof finished) => {
    const prisma = {
      game: {
        findUnique: jest.fn().mockResolvedValue(game),
        updateMany: jest.fn(),
        update: jest.fn(),
        delete: jest.fn(),
      },
      gamePlayer: { deleteMany: jest.fn(), updateMany: jest.fn() },
      $transaction: jest.fn(),
    };
    prisma.$transaction.mockImplementation(async (fn: (tx: any) => Promise<unknown>) =>
      fn({ $queryRaw: jest.fn(), game: prisma.game, gamePlayer: prisma.gamePlayer }),
    );
    const service = new GameService(prisma as any, {} as any, {} as any, {} as any, {} as any);
    return { service, prisma };
  };

  it('rejects abort after finish without changing winner, result, or emitting an abort', async () => {
    const { service, prisma } = makeGameService(finished);
    await expect(service.abortGame('g1', 'host')).rejects.toThrow(BadRequestException);
    expect(prisma.game.updateMany).not.toHaveBeenCalled();
    expect(prisma.game.update).not.toHaveBeenCalled();
    expect(finished).toMatchObject({ status: GameStatus.FINISHED, winnerId: 'host' });
  });

  it('rejects a stale abort when finish wins the conditional write', async () => {
    const { service, prisma } = makeGameService({ ...finished, status: GameStatus.IN_PROGRESS });
    prisma.game.updateMany.mockResolvedValue({ count: 0 });
    await expect(service.abortGame('g1', 'host')).rejects.toThrow(BadRequestException);
    const calls = prisma.game.updateMany.mock.calls as unknown as Array<
      [{ where: { id: string; status: { in: GameStatus[] } } }]
    >;
    const transition = calls[0][0];
    expect(transition.where).toEqual({
      id: 'g1',
      status: {
        in: [GameStatus.PENDING, GameStatus.LOBBY, GameStatus.IN_PROGRESS, GameStatus.PAUSED],
      },
    });
  });

  it('returns a committed abort when Redis invalidation fails', async () => {
    const row = { ...finished, status: GameStatus.IN_PROGRESS };
    const game = {
      findUnique: jest.fn(async () => row),
      updateMany: jest.fn(async () => {
        row.status = GameStatus.ABORTED;
        return { count: 1 };
      }),
    };
    const prisma = { game, gameState: { findUnique: jest.fn().mockResolvedValue(null) } };
    const redis = { del: jest.fn().mockRejectedValue(new Error('Redis unavailable')) };
    const subscriptions = { publishLobbyEvent: jest.fn() };
    const service = new GameService(
      prisma as any, redis as any, {} as any,
      { recordAction: jest.fn() } as any, subscriptions as any,
    );
    const getGame = jest.spyOn(service, 'getGame').mockResolvedValue({ status: GameStatus.ABORTED } as any);

    await expect(service.abortGame('g1', 'host')).resolves.toMatchObject({ status: GameStatus.ABORTED });
    expect(row.status).toBe(GameStatus.ABORTED);
    expect(getGame).toHaveBeenCalledWith('g1', true);
    expect(subscriptions.publishLobbyEvent).toHaveBeenCalledWith('g1', 'GAME_ENDED', {
      reason: 'aborted', abortedBy: 'host',
    });
  });

  it('reads the authoritative abort response while cache reads and writes are unavailable', async () => {
    const row = {
      ...finished, status: GameStatus.ABORTED, winnerId: null,
      code: 'S09', mode: 'ONE_V_ONE', boardId: 'board', boardState: null,
      createdAt: new Date(), updatedAt: new Date(), startedAt: new Date(), version: 2,
      host: { id: 'host', username: 'Host', avatar: null },
      opponent: { id: 'opponent', username: 'Opponent', avatar: null },
      players: [
        { id: 'seat0', userId: 'host', user: { id: 'host', username: 'Host', avatar: null }, seatOrder: 0 },
        { id: 'seat1', userId: 'opponent', user: { id: 'opponent', username: 'Opponent', avatar: null }, seatOrder: 1 },
      ],
      state: { phase: GamePhase.ACTION_MANEUVER, turnCount: 1 },
    };
    const prisma = { game: { findUnique: jest.fn(async () => row) } };
    const redis = {
      getJson: jest.fn().mockRejectedValue(new Error('Redis read unavailable')),
      setJsonex: jest.fn().mockRejectedValue(new Error('Redis write unavailable')),
    };
    const service = new GameService(prisma as any, redis as any, {} as any, {} as any, {} as any);

    await expect(service.getGame('g1', true)).resolves.toMatchObject({ status: GameStatus.ABORTED });
    expect(redis.getJson).not.toHaveBeenCalled();
    expect(prisma.game.findUnique).toHaveBeenCalledTimes(1);
  });

  it('rejects late GAME_OVER after abort before writing state or cache', async () => {
    const gameState = { findUnique: jest.fn(), upsert: jest.fn() };
    const game = { updateMany: jest.fn().mockResolvedValue({ count: 0 }), update: jest.fn() };
    const prisma = {
      $transaction: jest.fn(async (fn: (tx: any) => Promise<void>) => fn({ game, gameState })),
    };
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const service = new GameStateService(prisma as any, redis as any);
    jest.spyOn(service, 'serialize').mockReturnValue({} as any);
    const state = {
      gameId: 'g1',
      phase: GamePhase.GAME_OVER,
      sequenceNumber: 2,
      metadata: { winnerId: 'host' },
      players: [{ userId: 'host' }, { userId: 'opponent' }],
    };

    await expect(service.saveState('g1', state as any)).rejects.toThrow(ConflictException);
    expect(game.updateMany).toHaveBeenCalledWith(
      expect.objectContaining({
        where: { id: 'g1', status: GameStatus.IN_PROGRESS },
      }),
    );
    expect(gameState.upsert).not.toHaveBeenCalled();
    expect(game.update).not.toHaveBeenCalled();
    expect(redis.del).not.toHaveBeenCalled();
    expect(redis.setJsonex).not.toHaveBeenCalled();
  });

  it('rejects a nonterminal save when abort wins and emits no state update', async () => {
    const gameState = { findUnique: jest.fn(), upsert: jest.fn() };
    const game = { updateMany: jest.fn().mockResolvedValue({ count: 0 }) };
    const prisma = {
      $transaction: jest.fn(async (fn: (tx: any) => Promise<void>) => fn({ game, gameState })),
    };
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const subscriptions = { publishGameUpdate: jest.fn() };
    const service = new GameStateService(prisma as any, redis as any, subscriptions as any);
    jest.spyOn(service, 'serialize').mockReturnValue({} as any);

    await expect(
      service.saveState('g1', {
        gameId: 'g1',
        phase: GamePhase.ACTION_MANEUVER,
        sequenceNumber: 2,
        metadata: {},
        players: [],
      } as any),
    ).rejects.toThrow(ConflictException);
    expect(game.updateMany).toHaveBeenCalledWith({
      where: { id: 'g1', status: GameStatus.IN_PROGRESS },
      data: { version: 2 },
    });
    expect(gameState.findUnique).not.toHaveBeenCalled();
    expect(gameState.upsert).not.toHaveBeenCalled();
    expect(redis.setJsonex).not.toHaveBeenCalled();
    expect(subscriptions.publishGameUpdate).not.toHaveBeenCalled();
  });

  it('evicts a cached game(id) response when the terminal result commits', async () => {
    const row = {
      ...finished,
      status: GameStatus.IN_PROGRESS,
      winnerId: null as string | null,
      endedAt: null as Date | null,
      version: 1,
      code: 'ABC',
      mode: 'ONE_V_ONE',
      boardId: 'board',
      boardState: null,
      createdAt: new Date(),
      updatedAt: new Date(),
      startedAt: new Date(),
      host: { id: 'host', username: 'Host', avatar: null },
      opponent: { id: 'opponent', username: 'Opponent', avatar: null },
      players: [
        {
          id: 'seat0',
          userId: 'host',
          user: { id: 'host', username: 'Host', avatar: null },
          seatOrder: 0,
        },
        {
          id: 'seat1',
          userId: 'opponent',
          user: { id: 'opponent', username: 'Opponent', avatar: null },
          seatOrder: 1,
        },
      ],
      state: { phase: GamePhase.ACTION_MANEUVER, turnCount: 1 },
    };
    const cache = new Map<string, unknown>([
      ['game:g1', { status: GameStatus.IN_PROGRESS, winnerId: null, version: 1 }],
    ]);
    const redis = {
      getJson: jest.fn(async (key: string) => cache.get(key) ?? null),
      setJsonex: jest.fn(async (key: string, _ttl: number, value: unknown) => {
        cache.set(key, value);
      }),
      del: jest.fn(async (key: string) => {
        cache.delete(key);
      }),
    };
    const gameState = {
      findUnique: jest.fn().mockResolvedValue({ sequenceNumber: 1 }),
      upsert: jest.fn(async () => {
        row.state = { phase: GamePhase.GAME_OVER, turnCount: 1 };
      }),
    };
    const game = {
      updateMany: jest.fn(
        async (args: { where: { status: GameStatus }; data: Record<string, unknown> }) => {
          if (row.status !== args.where.status) return { count: 0 };
          Object.assign(row, args.data);
          return { count: 1 };
        },
      ),
      findUnique: jest.fn(async () => row),
    };
    const prisma = {
      game,
      $transaction: jest.fn(async (fn: (tx: any) => Promise<void>) =>
        fn({
          game,
          gameState,
          userStats: { createMany: jest.fn(), update: jest.fn() },
          $queryRaw: jest.fn().mockResolvedValue([
            { userId: 'host', gamesPlayed: 0, gamesWon: 0, gamesLost: 0, currentElo: 1200, peakElo: 1200 },
            { userId: 'opponent', gamesPlayed: 0, gamesWon: 0, gamesLost: 0, currentElo: 1200, peakElo: 1200 },
          ]),
        })),
    };
    const games = new GameService(prisma as any, redis as any, {} as any, {} as any, {} as any);
    const states = new GameStateService(prisma as any, redis as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);

    expect((await games.getGame('g1')).status).toBe(GameStatus.IN_PROGRESS);
    // живой кеш-хит: ровно одна дешёвая сверка статуса/version с БД
    // (терминальный read авторитетен и при провале инвалидации), без
    // полного include-read
    expect(game.findUnique).toHaveBeenCalledTimes(1);
    expect((game.findUnique.mock.calls as unknown as Array<[Record<string, unknown>]>)[0][0]).toMatchObject({
      where: { id: 'g1' },
      select: { status: true, version: true },
    });
    await states.saveState('g1', {
      gameId: 'g1',
      phase: GamePhase.GAME_OVER,
      sequenceNumber: 2,
      currentTurnPlayerId: 'host',
      turnCount: 1,
      metadata: { winnerId: 'host' },
      players: [{ userId: 'host' }, { userId: 'opponent' }],
    } as any);
    expect(redis.del).toHaveBeenCalledWith('game:g1');
    // composition check в транзакции финиша + две проверки isCurrentSavedState
    expect(game.findUnique).toHaveBeenCalledTimes(4);
    const refreshed = await games.getGame('g1');
    expect(game.findUnique).toHaveBeenCalledTimes(5);
    expect(refreshed).toMatchObject({ status: GameStatus.FINISHED, winnerId: 'host' });
  });

  it.each(['host', 'opponent'])(
    'leave after finish keeps both seats and result for %s',
    async (userId) => {
      const { service, prisma } = makeGameService(finished);
      await expect(service.leaveGame('g1', userId)).resolves.toBeUndefined();
      expect(prisma.$transaction).toHaveBeenCalledTimes(1);
      expect(prisma.game.updateMany).not.toHaveBeenCalled();
      expect(prisma.game.delete).not.toHaveBeenCalled();
      expect(prisma.gamePlayer.deleteMany).not.toHaveBeenCalled();
      expect(finished.players.map((p) => p.userId)).toEqual(['host', 'opponent']);
    },
  );

  it('leaving an in-progress duel still aborts it', async () => {
    const { service } = makeGameService({ ...finished, status: GameStatus.IN_PROGRESS });
    const abort = jest.spyOn(service, 'abortGame').mockResolvedValue({} as any);
    await service.leaveGame('g1', 'opponent');
    expect(abort).toHaveBeenCalledWith('g1', 'opponent', 'player_left');
  });

  it('lets a player leave when finish wins after the locked in-progress read', async () => {
    const { service, prisma } = makeGameService({ ...finished, status: GameStatus.IN_PROGRESS });
    prisma.game.findUnique.mockResolvedValueOnce({ ...finished, status: GameStatus.IN_PROGRESS });
    prisma.game.findUnique.mockResolvedValueOnce(finished);
    jest.spyOn(service, 'abortGame').mockRejectedValue(new BadRequestException('Finished'));

    await expect(service.leaveGame('g1', 'host')).resolves.toBeUndefined();
    expect(prisma.gamePlayer.deleteMany).not.toHaveBeenCalled();
  });

  it.each([GameStatus.ABORTED, GameStatus.FINISHED])(
    'startGame never rolls %s back to LOBBY when initialization loses the race',
    async (terminalStatus) => {
      const players = [
        { userId: 'host', heroId: 'arthur', isReady: true },
        { userId: 'opponent', heroId: 'medusa', isReady: true },
      ];
      const row = {
        id: 'g1',
        hostId: 'host',
        opponentId: 'opponent',
        mode: 'ONE_V_ONE',
        status: GameStatus.LOBBY,
        winnerId: null as string | null,
        players,
      };
      const game = {
        findUnique: jest.fn(async () => row),
        update: jest.fn(async () => {
          row.status = GameStatus.IN_PROGRESS;
        }),
        updateMany: jest.fn(
          async (args: { where: { status: GameStatus }; data: { status: GameStatus } }) => {
            if (row.status !== args.where.status) return { count: 0 };
            row.status = args.data.status;
            return { count: 1 };
          },
        ),
      };
      const gamePlayer = { findMany: jest.fn(async () => players) };
      const prisma = {
        game,
        gamePlayer,
        $transaction: jest.fn(async (fn: (tx: any) => Promise<void>) =>
          fn({ $queryRaw: jest.fn(), game, gamePlayer }),
        ),
      };
      const redis = { del: jest.fn() };
      const initialization = {
        initializeGameState: jest.fn(async () => {
          row.status = terminalStatus;
          row.winnerId = terminalStatus === GameStatus.FINISHED ? 'host' : null;
          throw new Error('initial save rejected');
        }),
      };
      const service = new GameService(
        prisma as any,
        redis as any,
        initialization as any,
        {} as any,
        {} as any,
      );

      await expect(service.startGame('g1', 'host')).rejects.toThrow(BadRequestException);
      expect(game.updateMany).toHaveBeenCalledWith({
        where: { id: 'g1', status: GameStatus.IN_PROGRESS },
        data: { status: GameStatus.LOBBY, startedAt: null },
      });
      expect(row.status).toBe(terminalStatus);
      expect(row.winnerId).toBe(terminalStatus === GameStatus.FINISHED ? 'host' : null);
      expect(redis.del).not.toHaveBeenCalled();
    },
  );

  it('drops a saved snapshot when abort commits during cache work', async () => {
    const row = {
      id: 'g1',
      hostId: 'host',
      opponentId: 'opponent',
      status: GameStatus.IN_PROGRESS,
      version: 1,
    };
    const cache = new Map<string, unknown>();
    const events: string[] = [];
    let games!: GameService;
    const redis = {
      getJson: jest.fn(async (key: string) => cache.get(key) ?? null),
      del: jest.fn(async (key: string) => {
        cache.delete(key);
      }),
      setJsonex: jest.fn(async (key: string, _ttl: number, value: unknown) => {
        if (key === 'gamestate:g1') await games.abortGame('g1', 'host');
        cache.set(key, value);
      }),
    };
    const game = {
      findUnique: jest.fn(async () => row),
      updateMany: jest.fn(
        async (args: {
          where: { status: GameStatus | { in: GameStatus[] } };
          data: { status?: GameStatus; version?: number };
        }) => {
          const allowed =
            typeof args.where.status === 'string'
              ? row.status === args.where.status
              : args.where.status.in.includes(row.status);
          if (!allowed) return { count: 0 };
          Object.assign(row, args.data);
          return { count: 1 };
        },
      ),
    };
    const gameState = {
      findUnique: jest.fn().mockResolvedValue({ sequenceNumber: 1 }),
      upsert: jest.fn(),
    };
    const prisma = {
      game,
      gameState,
      $transaction: jest.fn(async (fn: (tx: any) => Promise<void>) =>
        fn({ game, gameState })),
    };
    games = new GameService(
      prisma as any,
      redis as any,
      {} as any,
      { recordAction: jest.fn() } as any,
      {
        publishLobbyEvent: jest.fn(async () => {
          events.push('GAME_ENDED');
        }),
      } as any,
    );
    jest.spyOn(games, 'getGame').mockResolvedValue({} as any);
    const subscriptions = {
      publishGameUpdate: jest.fn(async () => {
        events.push('STATE_UPDATED');
      }),
    };
    const states = new GameStateService(prisma as any, redis as any, subscriptions as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);

    await expect(
      states.saveState('g1', {
        gameId: 'g1',
        phase: GamePhase.ACTION_MANEUVER,
        sequenceNumber: 2,
        metadata: {},
        players: [],
      } as any),
    ).resolves.toBeUndefined();
    expect(gameState.upsert).toHaveBeenCalledTimes(1);
    expect(row.status).toBe(GameStatus.ABORTED);
    expect(cache.has('gamestate:g1')).toBe(true);
    expect(await states.getCachedState('g1')).toBeNull();
    expect(events).toEqual(['GAME_ENDED']);
    expect(subscriptions.publishGameUpdate).not.toHaveBeenCalled();
  });

  it('exposes the residual late nonterminal update after abort during publication', async () => {
    const row = {
      id: 'g1', hostId: 'host', opponentId: 'opponent',
      status: GameStatus.IN_PROGRESS, version: 1,
    };
    const events: string[] = [];
    let releasePublish!: () => void;
    let publicationStarted!: () => void;
    let abortReachedWrite!: () => void;
    const publishGate = new Promise<void>((resolve) => { releasePublish = resolve; });
    const publishing = new Promise<void>((resolve) => { publicationStarted = resolve; });
    const abortWriting = new Promise<void>((resolve) => { abortReachedWrite = resolve; });
    const game = {
      findUnique: jest.fn(async () => ({ ...row })),
      updateMany: jest.fn(async (args: { where: { status: GameStatus | { in: GameStatus[] } }; data: Record<string, unknown> }) => {
        if (typeof args.where.status !== 'string') {
          abortReachedWrite();
        }
        const allowed = typeof args.where.status === 'string'
          ? row.status === args.where.status
          : args.where.status.in.includes(row.status);
        if (!allowed) return { count: 0 };
        Object.assign(row, args.data);
        return { count: 1 };
      }),
    };
    const gameState = {
      findUnique: jest.fn(async () => ({ sequenceNumber: 1 })),
      upsert: jest.fn(),
    };
    const prisma = {
      game, gameState,
      $transaction: jest.fn(async (fn: (tx: any) => Promise<unknown>) =>
        fn({ game, gameState })),
    };
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const subscriptions = {
      publishGameUpdate: jest.fn(async () => {
        publicationStarted();
        await publishGate;
        events.push('STATE_UPDATED');
      }),
      publishLobbyEvent: jest.fn(async () => { events.push('GAME_ENDED'); }),
    };
    const games = new GameService(
      prisma as any, redis as any, {} as any,
      { recordAction: jest.fn() } as any, subscriptions as any,
    );
    jest.spyOn(games, 'getGame').mockResolvedValue({} as any);
    const states = new GameStateService(prisma as any, redis as any, subscriptions as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);

    const saving = states.saveState('g1', {
      gameId: 'g1', phase: GamePhase.ACTION_MANEUVER, sequenceNumber: 2,
      metadata: {}, players: [],
    } as any);
    await publishing;
    const aborting = games.abortGame('g1', 'host');
    await abortWriting;
    await aborting;
    expect(row.status).toBe(GameStatus.ABORTED);
    expect(events).toEqual(['GAME_ENDED']);

    releasePublish();
    await expect(saving).resolves.toBeUndefined();
    expect(row.status).toBe(GameStatus.ABORTED);
    expect(events).toEqual(['GAME_ENDED', 'STATE_UPDATED']);
  });

  it('treats a committed nonterminal save superseded by the next action as success', async () => {
    const row = { status: GameStatus.IN_PROGRESS, version: 1 };
    const persisted = { sequenceNumber: 1 };
    const cache = new Map<string, unknown>();
    const published: number[] = [];
    const game = {
      updateMany: jest.fn(async (args: { where: { status: GameStatus }; data: { version: number } }) => {
        if (row.status !== args.where.status) return { count: 0 };
        row.version = args.data.version;
        return { count: 1 };
      }),
      findUnique: jest.fn(async () => ({ ...row })),
    };
    const gameState = {
      findUnique: jest.fn(async () => ({ ...persisted })),
      upsert: jest.fn(async (args: { create: { sequenceNumber: number } }) => {
        persisted.sequenceNumber = args.create.sequenceNumber;
      }),
    };
    const prisma = {
      game, gameState,
      $transaction: jest.fn(async (fn: (tx: any) => Promise<unknown>) => fn({ game, gameState })),
    };
    let states!: GameStateService;
    let advanced = false;
    const redis = {
      getJson: jest.fn(async (key: string) => cache.get(key) ?? null),
      del: jest.fn(),
      setJsonex: jest.fn(async (key: string, _ttl: number, value: { sequenceNumber: number }) => {
        if (value.sequenceNumber === 2 && !advanced) {
          advanced = true;
          await states.saveState('g1', {
            gameId: 'g1', phase: GamePhase.ACTION_MANEUVER,
            sequenceNumber: 3, metadata: {}, players: [],
          } as any);
        }
        cache.set(key, value);
      }),
    };
    const subscriptions = {
      publishGameUpdate: jest.fn(async (_id: string, _type: string, state: { sequenceNumber: number }) => {
        published.push(state.sequenceNumber);
      }),
    };
    states = new GameStateService(prisma as any, redis as any, subscriptions as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);

    await expect(states.saveState('g1', {
      gameId: 'g1', phase: GamePhase.ACTION_MANEUVER,
      sequenceNumber: 2, metadata: {}, players: [],
    } as any)).resolves.toBeUndefined();
    expect(persisted.sequenceNumber).toBe(3);
    expect(published).toEqual([3]);
    expect(cache.get('gamestate:g1')).toMatchObject({ sequenceNumber: 2 });
    expect(await states.getCachedState('g1')).toBeNull();
  });

  it('keeps a GAME_OVER publication authoritative when abort is attempted during delivery', async () => {
    const row = {
      id: 'g1', hostId: 'host', opponentId: 'opponent',
      status: GameStatus.IN_PROGRESS, version: 1, winnerId: null as string | null,
    };
    let releasePublish!: () => void;
    let publicationStarted!: () => void;
    const publishGate = new Promise<void>((resolve) => { releasePublish = resolve; });
    const publishing = new Promise<void>((resolve) => { publicationStarted = resolve; });
    const game = {
      findUnique: jest.fn(async () => ({ ...row })),
      updateMany: jest.fn(async (args: { where: { status: GameStatus | { in: GameStatus[] } }; data: Record<string, unknown> }) => {
        const allowed = typeof args.where.status === 'string'
          ? row.status === args.where.status
          : args.where.status.in.includes(row.status);
        if (!allowed) return { count: 0 };
        Object.assign(row, args.data);
        return { count: 1 };
      }),
    };
    const gameState = { findUnique: jest.fn(async () => ({ sequenceNumber: 1 })), upsert: jest.fn() };
    const prisma = {
      game, gameState,
      $transaction: jest.fn(async (fn: (tx: any) => Promise<unknown>) =>
        fn({
          game, gameState,
          userStats: { createMany: jest.fn(), update: jest.fn() },
          $queryRaw: jest.fn().mockResolvedValue([
            { userId: 'host', gamesPlayed: 0, gamesWon: 0, gamesLost: 0, currentElo: 1200, peakElo: 1200 },
            { userId: 'opponent', gamesPlayed: 0, gamesWon: 0, gamesLost: 0, currentElo: 1200, peakElo: 1200 },
          ]),
        })),
    };
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const subscriptions = {
      publishGameUpdate: jest.fn(async (_id: string, _type: string, state: { phase: GamePhase }) => {
        expect(row.status).toBe(GameStatus.FINISHED);
        expect(state.phase).toBe(GamePhase.GAME_OVER);
        publicationStarted();
        await publishGate;
      }),
    };
    const games = new GameService(prisma as any, redis as any, {} as any, {} as any, {} as any);
    const states = new GameStateService(prisma as any, redis as any, subscriptions as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);

    const saving = states.saveState('g1', {
      gameId: 'g1', phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: { winnerId: 'host' }, players: [{ userId: 'host' }, { userId: 'opponent' }],
    } as any);
    await publishing;
    await expect(games.abortGame('g1', 'host')).rejects.toThrow(BadRequestException);
    expect(row).toMatchObject({ status: GameStatus.FINISHED, winnerId: 'host' });
    releasePublish();
    await saving;
    expect(subscriptions.publishGameUpdate).toHaveBeenCalledTimes(1);
    expect(prisma.$transaction).toHaveBeenCalledTimes(1);
  });

  it('does not roll back a committed GAME_OVER when delivery fails after reaching a client', async () => {
    const row = {
      id: 'g1', hostId: 'host', opponentId: 'opponent',
      status: GameStatus.IN_PROGRESS, version: 1, winnerId: null as string | null,
    };
    const delivered: GamePhase[] = [];
    const game = {
      findUnique: jest.fn(async () => ({ ...row })),
      updateMany: jest.fn(async (args: { where: { status: GameStatus }; data: Record<string, unknown> }) => {
        if (row.status !== args.where.status) return { count: 0 };
        Object.assign(row, args.data);
        return { count: 1 };
      }),
    };
    const gameState = { findUnique: jest.fn(async () => ({ sequenceNumber: 1 })), upsert: jest.fn() };
    const prisma = {
      game, gameState,
      $transaction: jest.fn(async (fn: (tx: any) => Promise<unknown>) => fn({
        game, gameState,
        userStats: { createMany: jest.fn(), update: jest.fn() },
        $queryRaw: jest.fn().mockResolvedValue([
          { userId: 'host', gamesPlayed: 0, gamesWon: 0, gamesLost: 0, currentElo: 1200, peakElo: 1200 },
          { userId: 'opponent', gamesPlayed: 0, gamesWon: 0, gamesLost: 0, currentElo: 1200, peakElo: 1200 },
        ]),
      })),
    };
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const subscriptions = {
      publishGameUpdate: jest.fn(async (_id: string, _type: string, state: { phase: GamePhase }) => {
        delivered.push(state.phase);
        throw new Error('Redis broadcast failed after local delivery');
      }),
    };
    const games = new GameService(prisma as any, redis as any, {} as any, {} as any, {} as any);
    const states = new GameStateService(prisma as any, redis as any, subscriptions as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);

    await expect(states.saveState('g1', {
      gameId: 'g1', phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: { winnerId: 'host' }, players: [{ userId: 'host' }, { userId: 'opponent' }],
    } as any)).resolves.toBeUndefined();
    expect(delivered).toEqual([GamePhase.GAME_OVER]);
    expect(row).toMatchObject({ status: GameStatus.FINISHED, winnerId: 'host' });
    await expect(games.abortGame('g1', 'host')).rejects.toThrow(BadRequestException);
    expect(prisma.$transaction).toHaveBeenCalledTimes(1);
  });
});
