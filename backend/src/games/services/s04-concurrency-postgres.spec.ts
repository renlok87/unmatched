/** GD-016 (P1-1): конкурентный выбор героев на РЕАЛЬНОМ PostgreSQL.
 * Одноразовый контейнер codex-s04-postgres (127.0.0.1:55432, s04_test);
 * спека СКИПАЕТСЯ, если БД недоступна (нет контейнера — нет и теста).
 *
 * Три уровня доказательства:
 * 1. Детерминированное воспроизведение гонки старой формы: два
 *    READ COMMITTED check-then-act без блокировки (барьер заставляет оба
 *    прочитать ростер до апдейтов) → ДУБЛЬ. Так вёл себя selectHero до фикса.
 * 2. Та же интерливинг-формула с SELECT … FOR UPDATE + перепроверкой статуса
 *    → ровно один проигравший. Это форма фикса.
 * 3. Продакшн GameService.selectHero/startGame/toggleReady через реальный
 *    Prisma: раунды Promise.all — инварианты уникальности и LOBBY-статуса.
 */
import { execSync } from 'node:child_process';
import { resolve } from 'node:path';
import { PrismaClient } from '@prisma/client';
import { GameService } from '../game.service';

const PG_URL = process.env.S04_PG_URL ?? 'postgresql://postgres@127.0.0.1:55432/s04_test';

const reachable = (() => {
  const { hostname, port } = new URL(PG_URL);
  try {
    // Скрипт через stdin — экранировать кавычки под cmd/bash не нужно.
    execSync('node', {
      input:
        `const n=require('net');const s=n.connect(${port},${JSON.stringify(hostname)});` +
        `s.setTimeout(2000);s.on('connect',()=>{s.destroy();process.exit(0)});` +
        `s.on('timeout',()=>{s.destroy();process.exit(1)});s.on('error',()=>process.exit(1));`,
      timeout: 5000,
      stdio: ['pipe', 'ignore', 'ignore'],
      windowsHide: true,
    });
    return true;
  } catch {
    return false;
  }
})();

const maybeDescribe = reachable ? describe : describe.skip;
maybeDescribe('GD-016: selectHero concurrency on real PostgreSQL', () => {
  let client: PrismaClient;
  let service: GameService;
  const H1 = 's04-hero-1';
  const H2 = 's04-hero-2';
  const H3 = 's04-hero-3';

  beforeAll(async () => {
    // Схема проекта — ТОЛЬКО в одноразовой тестовой БД (per-command URL override).
    execSync('npx prisma db push --skip-generate', {
      cwd: resolve(__dirname, '../../..'),
      env: { ...process.env, DATABASE_URL: PG_URL },
      stdio: 'pipe',
      timeout: 180000,
      windowsHide: true,
    });
    client = new PrismaClient({ datasources: { db: { url: PG_URL } } });
    service = new GameService(
      client as any,
      { getJson: async () => null, setJsonex: async () => 'OK', del: async () => 1 } as any,
      { initializeGameState: async () => undefined } as any,
      { recordAction: async () => 'id' } as any,
      { publishLobbyEvent: async () => ({}) } as any,
    );
    for (const id of ['u1', 'u2']) {
      await client.user.upsert({
        where: { id },
        create: { id, email: `${id}@s04.test`, username: `s04-${id}`, password: 'x' },
        update: {},
      });
    }
    for (const id of [H1, H2, H3]) {
      await client.hero.upsert({
        where: { id },
        create: { id, name: `S04 ${id}`, nameEn: id, nameRu: id, set: 's04',
          health: 10, fighterType: 'HERO', movement: 2, ability: {}, deckCards: [] },
        update: {},
      });
    }
    const board = await client.board.upsert({
      where: { name: 's04-concurrency-board' },
      create: { name: 's04-concurrency-board', nameEn: 's04', nameRu: 's04', set: 's04',
        width: 2, height: 1, cells: [] },
      update: {},
    });
    (globalThis as any).__s04BoardId = board.id;
  }, 240000);

  afterAll(async () => {
    await client?.$disconnect();
  });

  let seq = 0;
  async function freshGame(roster: [string | null, string | null], ready = false): Promise<string> {
    const gameId = `s04-g${Date.now()}-${++seq}`;
    await client.game.create({
      data: { id: gameId, status: 'LOBBY', mode: 'ONE_V_ONE', hostId: 'u1',
        opponentId: 'u2', boardId: (globalThis as any).__s04BoardId },
    });
    await client.gamePlayer.createMany({
      data: [
        { gameId, userId: 'u1', seatOrder: 0, heroId: roster[0], isReady: ready },
        { gameId, userId: 'u2', seatOrder: 1, heroId: roster[1], isReady: ready },
      ],
    });
    return gameId;
  }

  async function rosterOf(gameId: string) {
    const roster = await client.gamePlayer.findMany({ where: { gameId } });
    return roster.sort((a, b) => a.seatOrder - b.seatOrder);
  }

  it('reproduces the unlocked READ COMMITTED check-then-act race (old selectHero shape) — duplicate slips in', async () => {
    const gameId = await freshGame([null, null]);
    // Барьер: обе транзакции читают ростер ДО любого апдейта — точный
    // интерливинг двух конкурентных selectHero одного героя без блокировки.
    let arrived = 0;
    let release!: () => void;
    const both = new Promise<void>(yes => { release = yes; });
    const barrier = async () => { if (++arrived === 2) release(); await both; };

    const oldShapeSelect = (userId: string) =>
      client.$transaction(async (tx) => {
        const roster = await tx.gamePlayer.findMany({ where: { gameId } });
        await barrier();
        const rival = roster.find((p) => p.userId !== userId && p.heroId === H1);
        if (rival) throw new Error('Герой уже выбран другим игроком этой игры');
        await tx.gamePlayer.update({
          where: { gameId_userId: { gameId, userId } },
          data: { heroId: H1 },
        });
      });

    await Promise.all([oldShapeSelect('u1'), oldShapeSelect('u2')]);
    const roster = await rosterOf(gameId);
    // Старая семантика: ОБА выбора прошли → дубль (ровно то, что маскировала serializeTx-фикстура).
    expect(roster.filter((p) => p.heroId === H1)).toHaveLength(2);
  }, 30000);

  it('the FOR UPDATE + status re-check shape rejects exactly one racer under the same interleaving', async () => {
    const gameId = await freshGame([null, null]);
    let arrived = 0;
    let release!: () => void;
    const both = new Promise<void>(yes => { release = yes; });
    const barrier = async () => { if (++arrived === 2) release(); await both; };

    const lockedSelect = (userId: string) =>
      client.$transaction(async (tx) => {
        await barrier(); // обе стартовали до захвата лока — дальше гонка ЗА лок
        await tx.$queryRaw`SELECT id FROM "Game" WHERE id = ${gameId} FOR UPDATE`;
        const locked = await tx.game.findUnique({ where: { id: gameId }, select: { status: true } });
        if (!locked || locked.status !== 'LOBBY') throw new Error('Героя можно выбрать только в лобби');
        const roster = await tx.gamePlayer.findMany({ where: { gameId } });
        const rival = roster.find((p) => p.userId !== userId && p.heroId === H1);
        if (rival) throw new Error('Герой уже выбран другим игроком этой игры');
        await tx.gamePlayer.update({
          where: { gameId_userId: { gameId, userId } },
          data: { heroId: H1 },
        });
      });

    const results = await Promise.allSettled([lockedSelect('u1'), lockedSelect('u2')]);
    expect(results.filter((r) => r.status === 'fulfilled')).toHaveLength(1);
    const roster = await rosterOf(gameId);
    expect(roster.filter((p) => p.heroId === H1)).toHaveLength(1);
    expect((await client.game.findUnique({ where: { id: gameId } }))!.status).toBe('LOBBY');
  }, 30000);

  it('production GameService: concurrent same-hero selectHero keeps exactly one winner every round', async () => {
    for (let round = 0; round < 15; round++) {
      const gameId = await freshGame([null, null]);
      const results = await Promise.allSettled([
        service.selectHero(gameId, 'u1', H1),
        service.selectHero(gameId, 'u2', H1),
      ]);
      expect(results.filter((r) => r.status === 'fulfilled')).toHaveLength(1);
      const roster = await rosterOf(gameId);
      expect(roster.filter((p) => p.heroId === H1)).toHaveLength(1);
      expect((await client.game.findUnique({ where: { id: gameId } }))!.status).toBe('LOBBY');
    }
  }, 120000);

  it('production GameService: reselect vs startGame never duplicates and never mutates a started match', async () => {
    for (let round = 0; round < 10; round++) {
      const gameId = await freshGame([H1, H2], true);
      const [start, reselect] = await Promise.allSettled([
        service.startGame(gameId, 'u1'),
        service.selectHero(gameId, 'u2', H3),
      ]);
      const game = await client.game.findUnique({
        where: { id: gameId },
        include: { players: true },
      });
      const heroes = game!.players.map((p) => p.heroId).sort();
      // Уникальность состава — ВСЕГДА, при любом порядке коммитов.
      expect(new Set(heroes).size).toBe(2);
      if (start.status === 'fulfilled') {
        expect(game!.status).toBe('IN_PROGRESS');
      } else {
        expect(game!.status).toBe('LOBBY');
      }
      // Успешный reselect применился ДО старта: тогда старт обязан был увидеть
      // финальный ростер и пройти. Поздний (после IN_PROGRESS) — отвергнут.
      if (reselect.status === 'fulfilled') {
        expect(game!.players.find((p) => p.userId === 'u2')!.heroId).toBe(H3);
        expect(start.status).toBe('fulfilled');
      }
    }
  }, 120000);

  it('production GameService: reselect vs toggleReady stays consistent', async () => {
    for (let round = 0; round < 5; round++) {
      const gameId = await freshGame([H1, H2], false);
      await Promise.allSettled([
        service.selectHero(gameId, 'u2', H3),
        service.toggleReady(gameId, 'u2'),
      ]);
      const game = await client.game.findUnique({
        where: { id: gameId },
        include: { players: true },
      });
      const heroes = game!.players.map((p) => p.heroId);
      expect(new Set(heroes).size).toBe(2);
      expect(game!.status).toBe('LOBBY');
    }
  }, 60000);
});
