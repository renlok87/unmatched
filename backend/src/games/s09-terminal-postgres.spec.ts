import { BadRequestException, ConflictException } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';
import { randomUUID } from 'node:crypto';
import { GamePhase, GameStatus } from './dto';
import { GameService } from './game.service';
import { GameStateService } from './game-state.service';

const pgUrl = process.env.S09_PG_URL;
const describeWithPostgres = pgUrl ? describe : describe.skip;

describeWithPostgres('S09 terminal transitions on PostgreSQL', () => {
  let writer: PrismaClient;
  let aborter: PrismaClient;
  let hostId: string;
  let opponentId: string;
  let boardId: string;

  beforeAll(async () => {
    writer = new PrismaClient({ datasources: { db: { url: pgUrl! } } });
    aborter = new PrismaClient({ datasources: { db: { url: pgUrl! } } });
    const suffix = randomUUID();
    hostId = `s09-host-${suffix}`;
    opponentId = `s09-opponent-${suffix}`;
    await writer.user.createMany({ data: [
      { id: hostId, email: `${hostId}@test.invalid`, username: hostId, password: 'test' },
      { id: opponentId, email: `${opponentId}@test.invalid`, username: opponentId, password: 'test' },
    ] });
    const board = await writer.board.create({ data: {
      name: `s09-board-${suffix}`, nameEn: 'S09', nameRu: 'S09', set: 'test',
      width: 1, height: 1, cells: [],
    } });
    boardId = board.id;
  });

  afterAll(async () => {
    await writer?.$disconnect();
    await aborter?.$disconnect();
  });

  const makeFinishedService = () => {
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const states = new GameStateService(writer as any, redis as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);
    return states;
  };

  const seedGame = async (gameId: string, secondPlayerId: string = opponentId) => {
    await writer.game.create({ data: {
      id: gameId, hostId, opponentId: secondPlayerId, boardId, status: GameStatus.IN_PROGRESS, version: 1,
    } });
    await writer.gameState.create({ data: {
      gameId, state: {}, sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER,
    } });
  };

  const waitFor = async (
    predicate: () => Promise<boolean>,
    timeoutMs = 5000,
    intervalMs = 25,
  ) => {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      if (await predicate()) return;
      await new Promise((resolve) => setTimeout(resolve, intervalMs));
    }
    throw new Error('waitFor: condition not met before timeout');
  };

  // Принудительный overlap двух транзакций финиша. Удерживаемая из другого
  // соединения EXCLUSIVE-блокировка "UserStats" останавливает оба финиша на
  // createMany внутри их транзакций; релиз — только после подтверждения по
  // pg_locks, что оба ждут. Пока блокировка держится, оба финиша обязаны
  // быть в полёте одновременно, поэтому чисто последовательный прогон
  // (первый save закоммитился до старта второго) невозможен — сам по себе
  // Promise.all этого не доказывал.
  const forceOverlap = async (startSaves: (() => Promise<void>)[]) => {
    let releaseLock!: () => void;
    let lockAcquired!: () => void;
    const acquired = new Promise<void>((resolve) => { lockAcquired = resolve; });
    const release = new Promise<void>((resolve) => { releaseLock = resolve; });
    const holder = aborter.$transaction(
      async (lockTx) => {
        await lockTx.$executeRaw`LOCK TABLE "UserStats" IN EXCLUSIVE MODE`;
        lockAcquired();
        await release;
      },
      { timeout: 30000 },
    );
    await acquired;
    const saves = startSaves.map((start) => start());
    await waitFor(async () => {
      const waiting = await aborter.$queryRaw<{ count: number }[]>`
        SELECT count(*)::int AS count FROM pg_locks
        WHERE locktype = 'relation'
          AND relation = '"UserStats"'::regclass
          AND NOT granted`;
      return waiting[0].count >= 2;
    });
    releaseLock();
    await holder;
    await Promise.all(saves);
  };

  it('applies both seats stats exactly once on finish (idempotent retry)', async () => {
    const gameId = `s09-game-${randomUUID()}`;
    await writer.userStats.deleteMany({ where: { userId: { in: [hostId, opponentId] } } });
    await seedGame(gameId);
    const states = makeFinishedService();
    const terminal = {
      gameId, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: { winnerId: hostId }, players: [{ userId: hostId }, { userId: opponentId }],
    } as any;

    await states.saveState(gameId, terminal);

    expect(await writer.game.findUnique({ where: { id: gameId } })).toMatchObject({
      status: GameStatus.FINISHED, winnerId: hostId,
    });
    // 1200 vs 1200 (K=32): +16 / -16
    expect(await writer.userStats.findUnique({ where: { userId: hostId } })).toMatchObject({
      gamesPlayed: 1, gamesWon: 1, gamesLost: 0, currentElo: 1216, peakElo: 1216,
    });
    expect(await writer.userStats.findUnique({ where: { userId: opponentId } })).toMatchObject({
      gamesPlayed: 1, gamesWon: 0, gamesLost: 1, currentElo: 1184,
    });

    // Повторный вызов (повторная доставка/ретрай) не дублирует начисление
    await expect(states.saveState(gameId, terminal)).rejects.toThrow(ConflictException);
    expect(await writer.userStats.findUnique({ where: { userId: hostId } })).toMatchObject({
      gamesPlayed: 1, currentElo: 1216,
    });
  }, 15000);

  it('applies draw stats to both players exactly once on finish (winnerId absent)', async () => {
    const gameId = `s09-game-${randomUUID()}`;
    await writer.userStats.deleteMany({ where: { userId: { in: [hostId, opponentId] } } });
    await seedGame(gameId);
    const states = makeFinishedService();
    const draw = {
      gameId, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: {}, players: [{ userId: hostId }, { userId: opponentId }],
    } as any;

    await states.saveState(gameId, draw);

    expect(await writer.game.findUnique({ where: { id: gameId } })).toMatchObject({
      status: GameStatus.FINISHED, winnerId: null,
    });
    // Равные стартовые рейтинги: S=0.5 при E=0.5 — ELO без изменений,
    // но gamesPlayed/winRate/lastPlayedAt начислены обоим
    const host = await writer.userStats.findUnique({ where: { userId: hostId } });
    expect(host).toMatchObject({
      gamesPlayed: 1, gamesWon: 0, gamesLost: 0, winRate: 0,
      currentElo: 1200, peakElo: 1200,
    });
    expect(host!.lastPlayedAt).not.toBeNull();
    expect(await writer.userStats.findUnique({ where: { userId: opponentId } })).toMatchObject({
      gamesPlayed: 1, gamesWon: 0, gamesLost: 0, currentElo: 1200, peakElo: 1200,
    });

    // Повторная доставка ничьей не дублирует начисление
    await expect(states.saveState(gameId, draw)).rejects.toThrow(ConflictException);
    expect(await writer.userStats.findUnique({ where: { userId: hostId } })).toMatchObject({
      gamesPlayed: 1, currentElo: 1200,
    });
  }, 15000);

  it('converges ELO and raises peakElo on a draw between unequal ratings', async () => {
    const gameId = `s09-game-${randomUUID()}`;
    await writer.userStats.deleteMany({ where: { userId: { in: [hostId, opponentId] } } });
    await writer.userStats.createMany({ data: [
      { userId: hostId, currentElo: 1400, peakElo: 1400 },
      { userId: opponentId, currentElo: 1000, peakElo: 1000 },
    ] });
    await seedGame(gameId);

    await makeFinishedService().saveState(gameId, {
      gameId, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: {}, players: [{ userId: hostId }, { userId: opponentId }],
    } as any);

    // 1400 vs 1000 (K=32, S=0.5): -13.09 -> 1387 / +13.09 -> 1013
    expect(await writer.userStats.findUnique({ where: { userId: hostId } })).toMatchObject({
      gamesPlayed: 1, gamesWon: 0, gamesLost: 0, currentElo: 1387, peakElo: 1400,
    });
    expect(await writer.userStats.findUnique({ where: { userId: opponentId } })).toMatchObject({
      gamesPlayed: 1, currentElo: 1013, peakElo: 1013,
    });
  }, 15000);

  it('serializes concurrent terminal saves of one game into a single stats update', async () => {
    const gameId = `s09-game-${randomUUID()}`;
    await writer.userStats.deleteMany({ where: { userId: { in: [hostId, opponentId] } } });
    await seedGame(gameId);
    const terminal = {
      gameId, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: { winnerId: hostId }, players: [{ userId: hostId }, { userId: opponentId }],
    } as any;

    const results = await Promise.allSettled([
      makeFinishedService().saveState(gameId, terminal),
      makeFinishedService().saveState(gameId, terminal),
    ]);
    expect(results.filter((r) => r.status === 'fulfilled')).toHaveLength(1);
    const rejected = results.filter((r) => r.status === 'rejected');
    expect(rejected).toHaveLength(1);
    // Проигравший конкурент обязан увидеть условный transition — это
    // ожидаемый ConflictException, а не deadlock/timeout: оба сначала
    // конкурируют за одну строку game, второй wait завершается после
    // commit первого и пересчитывает предикат IN_PROGRESS в READ COMMITTED
    expect(rejected[0].reason).toBeInstanceOf(ConflictException);
    expect(rejected[0].reason.message).toContain('Only an in-progress game can save state');
    expect(await writer.game.findUnique({ where: { id: gameId } })).toMatchObject({
      status: GameStatus.FINISHED,
    });
    expect(await writer.userStats.findUnique({ where: { userId: hostId } })).toMatchObject({
      gamesPlayed: 1, gamesWon: 1, currentElo: 1216,
    });
  }, 15000);

  it('keeps concurrent finishes of two games sharing a player consistent (FOR UPDATE)', async () => {
    const suffix = randomUUID();
    const thirdId = `s09-third-${suffix}`;
    await writer.user.create({ data: {
      id: thirdId, email: `${thirdId}@test.invalid`, username: thirdId, password: 'test',
    } });
    const winGame = `s09-game-${randomUUID()}`;
    const loseGame = `s09-game-${randomUUID()}`;
    await writer.userStats.deleteMany({ where: { userId: { in: [hostId, opponentId, thirdId] } } });
    await seedGame(winGame);
    await seedGame(loseGame, thirdId);

    // Overlap доказан детерминированно (см. forceOverlap): обе транзакции
    // финиша одновременно висят на UserStats, а не идут последовательно
    await forceOverlap([
      () => makeFinishedService().saveState(winGame, {
        gameId: winGame, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
        metadata: { winnerId: hostId }, players: [{ userId: hostId }, { userId: opponentId }],
      } as any),
      () => makeFinishedService().saveState(loseGame, {
        gameId: loseGame, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
        metadata: { winnerId: thirdId }, players: [{ userId: hostId }, { userId: thirdId }],
      } as any),
    ]);

    // Оба апдейта применились (нет lost update): host сыграл обе игры
    const host = await writer.userStats.findUnique({ where: { userId: hostId } });
    expect(host).toMatchObject({ gamesPlayed: 2, gamesWon: 1, gamesLost: 1 });
    // Порядок сериализации не детерминирован: elo зависит от очерёдности
    expect([1199, 1201]).toContain(host!.currentElo);
    const opponent = await writer.userStats.findUnique({ where: { userId: opponentId } });
    expect(opponent).toMatchObject({ gamesPlayed: 1, gamesWon: 0, gamesLost: 1 });
    expect([1183, 1184]).toContain(opponent!.currentElo);
    const third = await writer.userStats.findUnique({ where: { userId: thirdId } });
    expect(third).toMatchObject({ gamesPlayed: 1, gamesWon: 1 });
    expect([1216, 1217]).toContain(third!.currentElo);
    expect(await writer.game.findMany({ where: { id: { in: [winGame, loseGame] } } }))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ id: winGame, status: GameStatus.FINISHED, winnerId: hostId }),
        expect.objectContaining({ id: loseGame, status: GameStatus.FINISHED, winnerId: thirdId }),
      ]));
  }, 15000);

  it('rolls back FINISHED without stats when terminal state mismatches the persisted composition', async () => {
    const suffix = randomUUID();
    const thirdId = `s09-third-${suffix}`;
    await writer.user.create({ data: {
      id: thirdId, email: `${thirdId}@test.invalid`, username: thirdId, password: 'test',
    } });
    const gameId = `s09-game-${randomUUID()}`;
    await writer.userStats.deleteMany({ where: { userId: { in: [hostId, opponentId, thirdId] } } });
    await seedGame(gameId);
    const states = makeFinishedService();

    // state подменяет соперника: persisted game = host vs opponent
    await expect(states.saveState(gameId, {
      gameId, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: { winnerId: thirdId }, players: [{ userId: hostId }, { userId: thirdId }],
    } as any)).rejects.toThrow(ConflictException);

    // Откат целиком: игра не завершена, снимок не перезаписан, stats нет
    expect(await writer.game.findUnique({ where: { id: gameId } })).toMatchObject({
      status: GameStatus.IN_PROGRESS, winnerId: null, version: 1,
    });
    expect(await writer.gameState.findUnique({ where: { gameId } })).toMatchObject({
      sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER,
    });
    expect(await writer.userStats.findUnique({ where: { userId: thirdId } })).toBeNull();
    expect(await writer.userStats.findUnique({ where: { userId: hostId } })).toBeNull();
    expect(await writer.userStats.findUnique({ where: { userId: opponentId } })).toBeNull();
  }, 15000);

  it('completes opposite-winner concurrent first finishes of one pair without deadlock', async () => {
    const hostWins = `s09-game-${randomUUID()}`;
    const oppWins = `s09-game-${randomUUID()}`;
    await writer.userStats.deleteMany({ where: { userId: { in: [hostId, opponentId] } } });
    await seedGame(hostWins);
    await seedGame(oppWins);
    const duel = [{ userId: hostId }, { userId: opponentId }];

    // Оба финиша — первые для обеих строк UserStats; вставки идут в
    // отсортированном порядке, поэтому цикла блокировок unique(userId) нет.
    // Overlap доказан детерминированно (см. forceOverlap): обе транзакции
    // одновременно висят на UserStats до релиза
    await forceOverlap([
      () => makeFinishedService().saveState(hostWins, {
        gameId: hostWins, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
        metadata: { winnerId: hostId }, players: duel,
      } as any),
      () => makeFinishedService().saveState(oppWins, {
        gameId: oppWins, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
        metadata: { winnerId: opponentId }, players: duel,
      } as any),
    ]);

    const host = await writer.userStats.findUnique({ where: { userId: hostId } });
    expect(host).toMatchObject({ gamesPlayed: 2, gamesWon: 1, gamesLost: 1 });
    const opponent = await writer.userStats.findUnique({ where: { userId: opponentId } });
    expect(opponent).toMatchObject({ gamesPlayed: 2, gamesWon: 1, gamesLost: 1 });
    // ELO-перенос с нулевой суммой: сумма пары не зависит от порядка сериализации
    expect(host!.currentElo + opponent!.currentElo).toBe(2400);
    expect(await writer.game.findMany({ where: { id: { in: [hostWins, oppWins] } } }))
      .toEqual(expect.arrayContaining([
        expect.objectContaining({ id: hostWins, status: GameStatus.FINISHED, winnerId: hostId }),
        expect.objectContaining({ id: oppWins, status: GameStatus.FINISHED, winnerId: opponentId }),
      ]));
  }, 15000);

  it('commits FINISHED before delivery and rejects abort from another connection while delivery is paused', async () => {
    const gameId = `s09-game-${randomUUID()}`;
    await writer.game.create({ data: {
      id: gameId, hostId, opponentId, boardId, status: GameStatus.IN_PROGRESS, version: 1,
    } });
    await writer.gameState.create({ data: {
      gameId, state: {}, sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER,
    } });

    let releasePublish!: () => void;
    let publicationStarted!: () => void;
    const publishGate = new Promise<void>((resolve) => { releasePublish = resolve; });
    const publishing = new Promise<void>((resolve) => { publicationStarted = resolve; });
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const subscriptions = { publishGameUpdate: jest.fn(async () => {
      publicationStarted();
      await publishGate;
      throw new Error('simulated Redis delivery failure');
    }) };
    const states = new GameStateService(writer as any, redis as any, subscriptions as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);
    const games = new GameService(
      aborter as any, redis as any, {} as any, {} as any, {} as any,
    );

    const saving = states.saveState(gameId, {
      gameId, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: { winnerId: hostId }, players: [{ userId: hostId }, { userId: opponentId }],
    } as any);
    try {
      await publishing;
      const committed = await aborter.game.findUnique({ where: { id: gameId } });
      expect(committed).toMatchObject({ status: GameStatus.FINISHED, winnerId: hostId });
      await expect(games.abortGame(gameId, hostId)).rejects.toThrow(BadRequestException);
      expect(await writer.gameState.findUnique({ where: { gameId } })).toMatchObject({
        sequenceNumber: 2, phase: GamePhase.GAME_OVER,
      });
    } finally {
      releasePublish();
      await saving;
    }
    await expect(writer.game.findUnique({ where: { id: gameId } })).resolves.toMatchObject({
      status: GameStatus.FINISHED,
    });
  }, 15000);

  it('rejects GAME_OVER before persisting state when abort commits first', async () => {
    const gameId = `s09-game-${randomUUID()}`;
    await writer.game.create({ data: {
      id: gameId, hostId, opponentId, boardId, status: GameStatus.IN_PROGRESS, version: 1,
    } });
    await writer.gameState.create({ data: {
      gameId, state: {}, sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER,
    } });
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    const subscriptions = {
      publishGameUpdate: jest.fn(), publishLobbyEvent: jest.fn(),
    };
    const games = new GameService(
      aborter as any, redis as any, {} as any,
      { recordAction: jest.fn() } as any, subscriptions as any,
    );
    jest.spyOn(games, 'getGame').mockResolvedValue({} as any);
    const states = new GameStateService(writer as any, redis as any, subscriptions as any);
    jest.spyOn(states, 'serialize').mockReturnValue({} as any);

    await games.abortGame(gameId, hostId);
    await expect(states.saveState(gameId, {
      gameId, phase: GamePhase.GAME_OVER, sequenceNumber: 2,
      metadata: { winnerId: hostId }, players: [],
    } as any)).rejects.toThrow(ConflictException);
    expect(await writer.game.findUnique({ where: { id: gameId } })).toMatchObject({
      status: GameStatus.ABORTED, winnerId: null,
    });
    expect(await writer.gameState.findUnique({ where: { gameId } })).toMatchObject({
      sequenceNumber: 1, phase: GamePhase.ACTION_MANEUVER,
    });
    expect(subscriptions.publishGameUpdate).not.toHaveBeenCalled();
  }, 15000);
});
