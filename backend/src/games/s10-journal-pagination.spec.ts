/** GD-039/S10: пагинация журнала eventsSince на реальном Postgres.
 *  Терминальная пара (мутация + GAME_ENDED) делит один sequenceNumber — и у
 *  человека (game-actions.resolver.executeMutation), и у бота
 *  (AiTurnService.recordJournal). Курсор клиента `gt: lastSequence`:
 *  если страница режет группу на границе, обрезанная строка того же seq
 *  теряется навсегда. Регрессия: complete-boundary batch — страница
 *  дополняется до полной группы boundary-seq; строки доставляются ровно
 *  один раз в детерминированном порядке (sequenceNumber, GAME_ENDED-last,
 *  timestamp, id — терминал строго последним в группе seq независимо от
 *  id/timestamp), приватность input (GD-025) сохраняется на каждой странице.
 *
 *  Харнесс создаёт и удаляет только собственные строки (users/board/game →
 *  каскад GameAction); сиды БД не требуются. */
import { PrismaClient, GameAction } from '@prisma/client';
import { randomUUID } from 'node:crypto';
import { GameStatus } from './dto';
import { GameStateService } from './game-state.service';

const dbUrl = process.env.S10_TEST_DB_URL;
const describePg = dbUrl ? describe : describe.skip;

const PAGE_SIZE = 100;

type SeedRow = {
  seq: number;
  type: string;
  actorId: string;
  action: string;
  input?: Record<string, string>;
  ts: Date;
  id?: string;
};

describePg('S10 GD-039: journal pagination (complete-boundary batch)', () => {
  let prisma: PrismaClient;
  let service: GameStateService;
  let humanId: string;
  let botId: string;
  const gameIds: string[] = [];
  const boardIds: string[] = [];

  beforeAll(async () => {
    prisma = new PrismaClient({ datasources: { db: { url: dbUrl! } } });
    const redis = { del: jest.fn(), setJsonex: jest.fn() };
    service = new GameStateService(prisma as any, redis as any);

    const suffix = randomUUID().slice(0, 8);
    humanId = `s10jp-human-${suffix}`;
    botId = `s10jp-bot-${suffix}`;
    await prisma.user.createMany({
      data: [
        { id: humanId, email: `${humanId}@test.invalid`, username: humanId, password: 'test' },
        { id: botId, email: `${botId}@test.invalid`, username: botId, password: 'test' },
      ],
    });
  });

  afterAll(async () => {
    try {
      // порядок: games (каскад GameAction) → boards → users; board не
      // каскадится от game — без отдельного удаления течёт на каждый прогон
      await prisma.game.deleteMany({ where: { id: { in: gameIds } } });
      await prisma.board.deleteMany({ where: { id: { in: boardIds } } });
      await prisma.user.deleteMany({ where: { id: { in: [humanId, botId] } } });
      // zero leftovers: повторный прогон стартует на чистых собственных строках
      expect(await prisma.game.count({ where: { id: { in: gameIds } } })).toBe(0);
      expect(await prisma.board.count({ where: { id: { in: boardIds } } })).toBe(0);
      expect(await prisma.gameAction.count({ where: { gameId: { in: gameIds } } })).toBe(0);
      expect(await prisma.user.count({ where: { id: { in: [humanId, botId] } } })).toBe(0);
    } finally {
      await prisma?.$disconnect();
    }
  });

  const seedGame = async (): Promise<string> => {
    const suffix = randomUUID().slice(0, 8);
    const board = await prisma.board.create({
      data: { name: `s10jp-board-${suffix}`, nameEn: 'S10JP', nameRu: 'S10JP', set: 'test', width: 1, height: 1, cells: [] },
    });
    boardIds.push(board.id);
    const gameId = `s10jp-game-${suffix}`;
    gameIds.push(gameId);
    await prisma.game.create({
      data: { id: gameId, hostId: humanId, opponentId: botId, boardId: board.id, status: GameStatus.IN_PROGRESS, version: 1 },
    });
    return gameId;
  };

  /** Запись журнала в форме GameActionProcessor (id/timestamp фиксированы на
   *  enqueue — очередь сохраняет их в upsert). */
  const seedActions = async (
    gameId: string,
    rows: SeedRow[],
  ): Promise<void> => {
    await prisma.gameAction.createMany({
      data: rows.map((r) => ({
        id: r.id ?? randomUUID(),
        gameId,
        sequenceNumber: r.seq,
        type: r.type as GameAction['type'],
        playerId: r.actorId,
        timestamp: r.ts,
        payload: { action: r.action, ...(r.input !== undefined ? { input: r.input } : {}) } as any,
      })),
    });
  };

  /** Терминальная пара на boundary: 99 филлеров (seq 1..99) + пара на seq 100.
   *  Страница take:100 без complete-boundary режет пару — терминал исчезает. */
  const seedBoundaryPairGame = async (pairActorId: string): Promise<string> => {
    const gameId = await seedGame();
    const base = Date.now();
    const rows: SeedRow[] = Array.from({ length: 99 }, (_, i) => ({
      seq: i + 1,
      type: 'CARD_PLAYED',
      actorId: pairActorId,
      action: `${pairActorId === botId ? 'ai' : 'human'}:maneuver`,
      input: { secret: `filler-${i + 1}` },
      ts: new Date(base + i),
    }));
    rows.push(
      { seq: 100, type: 'TURN_ENDED', actorId: pairActorId, action: 'ai:endTurn', input: { kind: 'endTurn' }, ts: new Date(base + 100) },
      { seq: 100, type: 'GAME_ENDED', actorId: pairActorId, action: 'ai:endTurn', ts: new Date(base + 101) },
    );
    await seedActions(gameId, rows);
    return gameId;
  };

  /** Tie-регрессия: терминальная пара с ОДИНАКОВЫМ timestamp и ОБРАТНЫМИ id
   *  (id GAME_ENDED лексикографически РАНЬШЕ id действия) — до фикса
   *  порядок решал случайный UUID, GAME_ENDED вставал перед своим действием.
   *  Полный порядок (GAME_ENDED-last) обязан быть детерминирован. */
  const seedTiePairGame = async (pairSeq: number, fillers: number): Promise<string> => {
    const gameId = await seedGame();
    const suffix = randomUUID().slice(0, 8);
    const base = Date.now();
    const tieTs = new Date(base + 1000);
    const rows: SeedRow[] = Array.from({ length: fillers }, (_, i) => ({
      seq: i + 1,
      type: 'CARD_PLAYED',
      actorId: botId,
      action: 'ai:maneuver',
      input: { secret: `tie-filler-${i + 1}` },
      ts: new Date(base + i),
    }));
    rows.push(
      { seq: pairSeq, type: 'COMBAT_RESOLVED', actorId: botId, action: 'ai:resolveCombat', input: { kind: 'resolveCombat' }, ts: tieTs, id: `zzzz-${suffix}-terminal-action` },
      { seq: pairSeq, type: 'GAME_ENDED', actorId: botId, action: 'ai:resolveCombat', ts: tieTs, id: `aaaa-${suffix}-game-ended-first` },
    );
    await seedActions(gameId, rows);
    return gameId;
  };

  it('терминальная пара бота на границе страницы: обе строки ровно один раз, в стабильном порядке', async () => {
    const gameId = await seedBoundaryPairGame(botId);

    const page1 = await service.getEventsSince(gameId, 0, humanId);
    // 99 филлеров + ПОЛНАЯ пара на boundary → 101 (до фикса: 100 — пара резалась)
    expect(page1).toHaveLength(PAGE_SIZE + 1);

    // последовательности неубывающие, полный порядок детерминирован
    const seqs = page1.map((e) => e.sequenceNumber);
    for (let i = 1; i < seqs.length; i++) expect(seqs[i]).toBeGreaterThanOrEqual(seqs[i - 1]);

    const boundary = page1.filter((e) => e.sequenceNumber === 100);
    expect(boundary.map((e) => e.type)).toEqual(['TURN_ENDED', 'GAME_ENDED']);

    // стабильность: повторная выборка идентична
    const page1again = await service.getEventsSince(gameId, 0, humanId);
    expect(page1again).toEqual(page1);

    // клиентский курсор: gt:100 → пара целиком пропущена, без дублей
    const page2 = await service.getEventsSince(gameId, 100, humanId);
    expect(page2).toHaveLength(0);
  });

  it('терминальная пара человека на границе: тот же контракт (human path)', async () => {
    const gameId = await seedBoundaryPairGame(humanId);

    const botView = await service.getEventsSince(gameId, 0, botId);
    expect(botView).toHaveLength(PAGE_SIZE + 1);
    expect(botView.filter((e) => e.sequenceNumber === 100).map((e) => e.type)).toEqual(['TURN_ENDED', 'GAME_ENDED']);
    expect(await service.getEventsSince(gameId, 100, botId)).toHaveLength(0);

    // владелец видит свой input (GD-025) на границе тоже
    const ownView = await service.getEventsSince(gameId, 0, humanId);
    const ownPair = ownView.filter((e) => e.sequenceNumber === 100);
    const ownTurn = JSON.parse(ownPair[0].payload);
    expect(ownTurn.input).toEqual({ kind: 'endTurn' });
  });

  it('tie: одинаковый timestamp + обратные id — терминал последним на boundary-разрезе', async () => {
    const gameId = await seedTiePairGame(100, 99);

    const page1 = await service.getEventsSince(gameId, 0, humanId);
    expect(page1).toHaveLength(PAGE_SIZE + 1);
    const boundary = page1.filter((e) => e.sequenceNumber === 100);
    expect(boundary.map((e) => e.type)).toEqual(['COMBAT_RESOLVED', 'GAME_ENDED']);
    // терминал — последняя строка страницы, не перед действием
    expect(page1[page1.length - 1].type).toBe('GAME_ENDED');

    // порядок стабилен между выборками (не случайный uuid-tiebreak)
    expect(await service.getEventsSince(gameId, 0, humanId)).toEqual(page1);
    expect(await service.getEventsSince(gameId, 100, humanId)).toHaveLength(0);
  });

  it('tie: тот же terminal-last контракт вне границы страницы (non-boundary)', async () => {
    const gameId = await seedTiePairGame(4, 3);

    const all = await service.getEventsSince(gameId, 0, humanId);
    expect(all).toHaveLength(5); // одна страница, complete-boundary не срабатывает
    expect(all.slice(3).map((e) => e.type)).toEqual(['COMBAT_RESOLVED', 'GAME_ENDED']);
    expect(all[all.length - 1].type).toBe('GAME_ENDED');
  });

  it('приватность сохраняется на boundary-странице: input бота не утекает человеку', async () => {
    const gameId = await seedBoundaryPairGame(botId);

    const humanView = await service.getEventsSince(gameId, 0, humanId);
    for (const e of humanView) {
      const payload = JSON.parse(e.payload);
      expect(payload.input).toBeUndefined(); // все записи бота: только action
      expect(payload.action).toMatch(/^ai:/);
    }

    const botView = await service.getEventsSince(gameId, 0, botId);
    expect(botView).toHaveLength(humanView.length);
    for (const e of botView) {
      const payload = JSON.parse(e.payload);
      if (e.type !== 'GAME_ENDED') {
        expect(payload.input).toBeDefined(); // свои записи — с input
      }
    }
  });

  it('многостраничный catch-up (>100 событий) без потерь и дублей, терминал в конце', async () => {
    const gameId = await seedGame();
    const base = Date.now();
    const rows: SeedRow[] = Array.from({ length: 149 }, (_, i) => ({
      seq: i + 1,
      type: 'CARD_PLAYED',
      actorId: botId,
      action: 'ai:maneuver',
      input: { secret: `f-${i + 1}` },
      ts: new Date(base + i),
    }));
    rows.push(
      { seq: 150, type: 'COMBAT_RESOLVED', actorId: botId, action: 'ai:resolveCombat', input: { kind: 'resolveCombat' }, ts: new Date(base + 150) },
      { seq: 150, type: 'GAME_ENDED', actorId: botId, action: 'ai:resolveCombat', ts: new Date(base + 151) },
    );
    await seedActions(gameId, rows);

    // клиентский цикл: since = lastSequence, hasMore = length >= PAGE_SIZE
    const seen: { seq: number; type: string }[] = [];
    let since = 0;
    for (let hop = 0; hop < 10; hop++) {
      const page = await service.getEventsSince(gameId, since, humanId);
      seen.push(...page.map((e) => ({ seq: e.sequenceNumber, type: e.type })));
      if (page.length < PAGE_SIZE) break;
      since = page[page.length - 1].sequenceNumber;
    }

    expect(seen).toHaveLength(151); // 149 филлеров + полная пара
    const keys = new Set(seen.map((e) => `${e.seq}:${e.type}`));
    expect(keys.size).toBe(151); // без дублей
    for (let seq = 1; seq <= 150; seq++) expect(keys.has(`${seq}:CARD_PLAYED`) || keys.has(`${seq}:COMBAT_RESOLVED`)).toBe(true);
    expect(seen[seen.length - 1].type).toBe('GAME_ENDED'); // терминал последним
  });
});
