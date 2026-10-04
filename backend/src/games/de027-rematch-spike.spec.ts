/** DE-027 (W-17, Q-203): server spike for "Play again" with the same line-up.
 *
 *  Question: can a finished game be turned into a new room with the same line-up
 *  (board, mode, the same two players with the same heroes) by the client alone,
 *  i.e. option (b) of Q-203 "createGame + join"? These tests run the real
 *  GameService lobby methods over an in-memory Prisma double; nothing in the
 *  service is mocked except storage, cache, journal, pub/sub and state init.
 *
 *  Findings pinned here (conclusion in docs/game-design/11-open-questions-and-risks.md, Q-203):
 *  - The finished room exposes everything the line-up needs: mode, boardId and
 *    each player's heroId and seatOrder (GameResponse).
 *  - VS_AI: yes, with existing mutations only. createGame(mode, boardId) +
 *    selectHero + toggleReady + startGame; the bot is re-added on start by the
 *    same max-health rule, so it gets the same hero.
 *  - Two humans: the room itself can be rebuilt, but the server never tells the
 *    second player about it. Lobby events go to the NEW game's channel only,
 *    the finished game carries no link to the new one, so the second player can
 *    enter only by code (GD-029). Automatic "createGame + join" needs a server
 *    addition (a rematch link on the finished game).
 *  - Seat order follows who creates the room: the creator is seat 0 and moves
 *    first (game-initialization: firstPlayerId = seat 0).
 */
import { GameService } from './game.service';
import { GameMode, GameStatus } from './dto';
import { DEFAULT_BOARD_ID } from './default-board';
import type { GameResponse } from './models';

const SARPEDON_BOARD_ID = 'c7fa64a26c29a0835f2383e63';
const AI_EMAIL = 'ai@unmached.local';

type UserRow = { id: string; email: string; username: string; avatar: string | null };
type HeroRow = { id: string; health: number; hasCards: boolean };
type GameRow = {
  id: string;
  code: string | null;
  status: string;
  mode: string;
  hostId: string;
  opponentId: string | null;
  boardId: string;
  boardState: unknown;
  idempotencyKey: string | null;
  createdAt: Date;
  updatedAt: Date;
  startedAt: Date | null;
  endedAt: Date | null;
  winnerId: string | null;
  version: number;
};
type PlayerRow = {
  id: string;
  gameId: string;
  userId: string;
  heroId: string | null;
  isReady: boolean;
  hasPassed: boolean;
  seatOrder: number;
};

/** In-memory Prisma double: only the calls the lobby methods make. */
class LobbyStore {
  users = new Map<string, UserRow>();
  heroes: HeroRow[] = [];
  boards = new Set<string>([DEFAULT_BOARD_ID, SARPEDON_BOARD_ID]);
  games = new Map<string, GameRow>();
  players: PlayerRow[] = [];
  private nextId = 1;

  private id(prefix: string): string {
    return `${prefix}-${this.nextId++}`;
  }

  private gameWithRelations(row: GameRow | undefined) {
    if (!row) return null;
    const user = (id: string | null) => {
      const u = id ? this.users.get(id) : undefined;
      return u ? { id: u.id, username: u.username, avatar: u.avatar } : null;
    };
    return {
      ...row,
      host: user(row.hostId),
      opponent: user(row.opponentId),
      players: this.players
        .filter((p) => p.gameId === row.id)
        .sort((a, b) => a.seatOrder - b.seatOrder)
        .map((p) => ({ ...p, user: user(p.userId) })),
      state: null,
    };
  }

  game = {
    count: async ({ where }: any) =>
      [...this.games.values()].filter(
        (g) =>
          (g.hostId === where.OR[0].hostId || g.opponentId === where.OR[1].opponentId) &&
          where.status.in.includes(g.status),
      ).length,
    findUnique: async ({ where }: any) => {
      if (where.id) return this.gameWithRelations(this.games.get(where.id));
      const byCode = [...this.games.values()].find((g) => g.code === where.code);
      return this.gameWithRelations(byCode);
    },
    findFirst: async ({ where }: any) =>
      [...this.games.values()].find(
        (g) => g.idempotencyKey === where.idempotencyKey && g.hostId === where.hostId,
      ) ?? null,
    create: async ({ data }: any) => {
      const now = new Date();
      const row: GameRow = {
        id: this.id('game'),
        code: data.code ?? null,
        status: data.status,
        mode: data.mode,
        hostId: data.hostId,
        opponentId: null,
        boardId: data.boardId,
        boardState: null,
        idempotencyKey: data.idempotencyKey ?? null,
        createdAt: now,
        updatedAt: now,
        startedAt: null,
        endedAt: null,
        winnerId: null,
        version: 1,
      };
      this.games.set(row.id, row);
      return row;
    },
    update: async ({ where, data }: any) => {
      const row = this.games.get(where.id)!;
      Object.assign(row, data, { updatedAt: new Date(), version: row.version + 1 });
      return row;
    },
    updateMany: async ({ where, data }: any) => {
      const row = this.games.get(where.id);
      if (!row || (where.status && row.status !== where.status)) return { count: 0 };
      Object.assign(row, data);
      return { count: 1 };
    },
  };

  gamePlayer = {
    create: async ({ data }: any) => {
      const row: PlayerRow = {
        id: this.id('player'),
        gameId: data.gameId,
        userId: data.userId,
        heroId: data.heroId ?? null,
        isReady: data.isReady ?? false,
        hasPassed: false,
        seatOrder: data.seatOrder ?? 0,
      };
      this.players.push(row);
      return row;
    },
    findUnique: async ({ where }: any) =>
      this.players.find(
        (p) => p.gameId === where.gameId_userId.gameId && p.userId === where.gameId_userId.userId,
      ) ?? null,
    findFirst: async ({ where }: any) =>
      this.players.find((p) => p.gameId === where.gameId && p.userId === where.userId) ?? null,
    findMany: async ({ where }: any) =>
      this.players
        .filter((p) => p.gameId === where.gameId)
        .sort((a, b) => a.seatOrder - b.seatOrder),
    update: async ({ where, data }: any) => {
      const row = this.players.find((p) => p.id === where.id)!;
      Object.assign(row, data);
      return row;
    },
  };

  user = {
    findUnique: async ({ where }: any) =>
      (where.id
        ? this.users.get(where.id)
        : [...this.users.values()].find((u) => u.email === where.email)) ?? null,
  };

  hero = {
    findUnique: async ({ where }: any) => this.heroes.find((h) => h.id === where.id) ?? null,
    findMany: async () =>
      this.heroes.filter((h) => h.hasCards).map((h) => ({ id: h.id, health: h.health })),
  };

  board = {
    findUnique: async ({ where }: any) => (this.boards.has(where.id) ? { id: where.id } : null),
  };

  $transaction = async <T>(run: (tx: LobbyStore) => Promise<T>): Promise<T> => run(this);
  $queryRaw = async () => [];

  addUser(id: string, email = `${id}@test.invalid`): void {
    this.users.set(id, { id, email, username: id, avatar: null });
  }

  /** A finished game as saveState leaves it (status FINISHED, winner set). */
  seedFinished(opts: {
    mode: GameMode;
    boardId: string;
    seats: Array<{ userId: string; heroId: string }>;
    winnerId: string;
  }): string {
    const id = this.id('finished');
    const at = new Date('2026-10-04T10:00:00Z');
    this.games.set(id, {
      id,
      code: 'OLDGAM',
      status: GameStatus.FINISHED,
      mode: opts.mode,
      hostId: opts.seats[0].userId,
      opponentId: opts.seats[1].userId,
      boardId: opts.boardId,
      boardState: null,
      idempotencyKey: null,
      createdAt: at,
      updatedAt: at,
      startedAt: at,
      endedAt: at,
      winnerId: opts.winnerId,
      version: 40,
    });
    opts.seats.forEach((s, seatOrder) =>
      this.players.push({
        id: this.id('player'),
        gameId: id,
        userId: s.userId,
        heroId: s.heroId,
        isReady: true,
        hasPassed: false,
        seatOrder,
      }),
    );
    return id;
  }
}

function buildService(store: LobbyStore) {
  const redis = {
    getJson: jest.fn().mockResolvedValue(null),
    setJsonex: jest.fn().mockResolvedValue(undefined),
    del: jest.fn().mockResolvedValue(undefined),
  };
  const init = { initializeGameState: jest.fn().mockResolvedValue(undefined) };
  const journal = { recordAction: jest.fn().mockResolvedValue('id') };
  const lobbyEvents = { publishLobbyEvent: jest.fn().mockResolvedValue(undefined) };
  const aiTurn = { maybeRunAiTurns: jest.fn().mockResolvedValue(undefined) };
  const service = new GameService(
    store as any,
    redis as any,
    init as any,
    journal as any,
    lobbyEvents as any,
    aiTurn as any,
  );
  return { service, init, lobbyEvents };
}

/** The line-up a client can read from the finished room. */
function lineUpOf(game: GameResponse) {
  return {
    mode: game.mode,
    boardId: game.boardId,
    seats: game.players.map((p) => ({ userId: p.userId, heroId: p.heroId, seatOrder: p.seatOrder })),
  };
}

const heroOf = (game: GameResponse, userId: string) =>
  game.players.find((p) => p.userId === userId)!.heroId!;

describe('DE-027 spike: "Play again" with the same line-up (Q-203)', () => {
  let store: LobbyStore;

  beforeEach(() => {
    store = new LobbyStore();
    store.addUser('arthur-player');
    store.addUser('medusa-player');
    store.addUser('ai-bot', AI_EMAIL);
    store.heroes = [
      { id: 'hero-arthur', health: 18, hasCards: true },
      { id: 'hero-medusa', health: 16, hasCards: true },
      { id: 'hero-no-deck', health: 20, hasCards: false },
    ];
  });

  it('two humans: existing mutations rebuild the room with the same board, mode, heroes and seats', async () => {
    const { service, init } = buildService(store);
    const oldId = store.seedFinished({
      mode: GameMode.ONE_V_ONE,
      boardId: SARPEDON_BOARD_ID,
      seats: [
        { userId: 'arthur-player', heroId: 'hero-arthur' },
        { userId: 'medusa-player', heroId: 'hero-medusa' },
      ],
      winnerId: 'medusa-player',
    });

    const finished = await service.getGame(oldId);
    expect(finished.status).toBe(GameStatus.FINISHED);
    const before = lineUpOf(finished);

    // Client automation of option (b): the old host recreates, the other joins.
    const created = await service.createGame(
      { mode: finished.mode, boardId: finished.boardId },
      'arthur-player',
      'de027-rematch-key',
    );
    await service.selectHero(created.id, 'arthur-player', heroOf(finished, 'arthur-player'));
    await service.toggleReady(created.id, 'arthur-player');
    await service.joinGame(created.id, 'medusa-player', heroOf(finished, 'medusa-player'));
    await service.toggleReady(created.id, 'medusa-player');
    const started = await service.startGame(created.id, 'arthur-player');

    expect(started.id).not.toBe(oldId);
    expect(started.status).toBe(GameStatus.IN_PROGRESS);
    expect(lineUpOf(started)).toEqual(before);
    expect(init.initializeGameState).toHaveBeenCalledWith(created.id);

    // The finished game is untouched: result and status stay as saved.
    const old = await service.getGame(oldId);
    expect(old.status).toBe(GameStatus.FINISHED);
    expect(old.winnerId).toBe('medusa-player');
  });

  it('two humans: the server never tells the second player about the new room', async () => {
    const { service, lobbyEvents } = buildService(store);
    const oldId = store.seedFinished({
      mode: GameMode.ONE_V_ONE,
      boardId: DEFAULT_BOARD_ID,
      seats: [
        { userId: 'arthur-player', heroId: 'hero-arthur' },
        { userId: 'medusa-player', heroId: 'hero-medusa' },
      ],
      winnerId: 'arthur-player',
    });

    const created = await service.createGame(
      { mode: GameMode.ONE_V_ONE, boardId: DEFAULT_BOARD_ID },
      'arthur-player',
    );
    await service.selectHero(created.id, 'arthur-player', 'hero-arthur');
    await service.toggleReady(created.id, 'arthur-player');

    // No lobby event reaches the finished game's channel, which is the only
    // channel the second player still knows.
    const channels = lobbyEvents.publishLobbyEvent.mock.calls.map((call: unknown[]) => call[0]);
    expect(channels).not.toContain(oldId);

    // The finished room has no link to the new one: nothing in its response
    // names the new game id or code.
    const old = JSON.stringify(await service.getGame(oldId));
    expect(old).not.toContain(created.id);
    expect(old).not.toContain(created.code);

    // The manual path that does exist: the code shown to the host (GD-029).
    const byCode = await service.getGameByCode(created.code);
    expect(byCode?.id).toBe(created.id);
    const joined = await service.joinGame(byCode!.id, 'medusa-player', 'hero-medusa');
    expect(joined.opponentId).toBe('medusa-player');
  });

  it('seat order follows the creator: if the other player recreates, seats and first move swap', async () => {
    const { service } = buildService(store);
    const oldId = store.seedFinished({
      mode: GameMode.ONE_V_ONE,
      boardId: DEFAULT_BOARD_ID,
      seats: [
        { userId: 'arthur-player', heroId: 'hero-arthur' },
        { userId: 'medusa-player', heroId: 'hero-medusa' },
      ],
      winnerId: 'arthur-player',
    });
    const finished = await service.getGame(oldId);

    const created = await service.createGame(
      { mode: finished.mode, boardId: finished.boardId },
      'medusa-player',
    );
    await service.selectHero(created.id, 'medusa-player', heroOf(finished, 'medusa-player'));
    await service.toggleReady(created.id, 'medusa-player');
    await service.joinGame(created.id, 'arthur-player', heroOf(finished, 'arthur-player'));
    await service.toggleReady(created.id, 'arthur-player');
    const started = await service.startGame(created.id, 'medusa-player');

    // Same heroes for the same players, but seat 0 (the first move) changed hands.
    expect(heroOf(started, 'arthur-player')).toBe('hero-arthur');
    expect(heroOf(started, 'medusa-player')).toBe('hero-medusa');
    expect(started.players.find((p) => p.seatOrder === 0)?.userId).toBe('medusa-player');
  });

  it('VS_AI: the human alone recreates the match; the bot comes back with the same hero', async () => {
    const { service } = buildService(store);

    // First match through the real lobby path, so the bot's hero is the one
    // startGame picks, not a seeded value.
    const first = await service.createGame({ mode: GameMode.VS_AI }, 'medusa-player');
    await service.selectHero(first.id, 'medusa-player', 'hero-medusa');
    await service.toggleReady(first.id, 'medusa-player');
    const firstStarted = await service.startGame(first.id, 'medusa-player');
    await store.game.update({
      where: { id: first.id },
      data: { status: GameStatus.FINISHED, endedAt: new Date(), winnerId: 'ai-bot' },
    });

    const finished = await service.getGame(first.id);
    expect(finished.status).toBe(GameStatus.FINISHED);
    expect(finished.boardId).toBe(DEFAULT_BOARD_ID);

    const again = await service.createGame(
      { mode: finished.mode, boardId: finished.boardId },
      'medusa-player',
    );
    await service.selectHero(again.id, 'medusa-player', heroOf(finished, 'medusa-player'));
    await service.toggleReady(again.id, 'medusa-player');
    const againStarted = await service.startGame(again.id, 'medusa-player');

    expect(againStarted.status).toBe(GameStatus.IN_PROGRESS);
    expect(lineUpOf(againStarted)).toEqual(lineUpOf(firstStarted));
    // The bot takes the strongest hero that has a deck (here Arthur, 18 health).
    expect(heroOf(againStarted, 'ai-bot')).toBe('hero-arthur');
  });

  it('a finished game does not count toward the active-games limit', async () => {
    const { service } = buildService(store);
    for (let i = 0; i < 5; i++) {
      store.seedFinished({
        mode: GameMode.ONE_V_ONE,
        boardId: DEFAULT_BOARD_ID,
        seats: [
          { userId: 'arthur-player', heroId: 'hero-arthur' },
          { userId: 'medusa-player', heroId: 'hero-medusa' },
        ],
        winnerId: 'arthur-player',
      });
    }
    await expect(
      service.createGame({ mode: GameMode.ONE_V_ONE, boardId: DEFAULT_BOARD_ID }, 'arthur-player'),
    ).resolves.toMatchObject({ status: GameStatus.LOBBY });
  });
});
