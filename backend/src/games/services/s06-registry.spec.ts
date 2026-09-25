/** GD-023/GD-021..022 closing: full-deck instance registry via the REAL
 * production start path. The frozen S01 captures (content-medusa.json,
 * content-king-arthur.json: 27 records / 60 copies) are loaded as hero.cards
 * and driven through GameService.startGame → GameInitializationService:
 * every copy becomes a DISTINCT instance (`${cardId}::${copy}`), decks are
 * 5-card hand + 25-card drawPile per player, banners survive the ingest, and
 * honest per-record support status (production resolveCardEffects) is written
 * to docs/game-design/evidence/S06/s06-card-registry.json. */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { GameService } from '../game.service';
import { GameInitializationService } from './game-initialization.service';
import { GameState } from '../game-state.service';
import { EffectType } from '../../game-engine/models';

const root = resolve(__dirname, '../../../..');
const source = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-board.json'), 'utf8'),
).adminBoard;

const medusaCapture = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-medusa.json'), 'utf8'),
);
const arthurCapture = JSON.parse(
  readFileSync(resolve(root, 'docs/game-design/evidence/S01/content-king-arthur.json'), 'utf8'),
);

/** Герои как в БД: РЕАЛЬНЫЕ 27 записей карт из замороженных S01-снимков.
 * В БД печатный текст карты живёт в Card.text (в снимке — textEn); маппим 1:1.
 * sidekicks-описания — как в s04-start-selection.spec (в снимке только число). */
const dbCards = (cards: any[]) => cards.map((c) => ({ ...c, text: c.textEn }));

const heroes: Record<string, any> = {
  medusa: {
    id: medusaCapture.id, name: medusaCapture.name, health: medusaCapture.health,
    movement: medusaCapture.movement, fighterType: 'HERO',
    properties: { attackType: 'ranged' },
    sidekicks: [{ name: 'Harpy', count: 3, health: 1 }],
    cards: dbCards(medusaCapture.cards),
  },
  arthur: {
    id: arthurCapture.id, name: arthurCapture.name, health: arthurCapture.health,
    movement: arthurCapture.movement, fighterType: 'HERO',
    sidekicks: [{ name: 'Merlin', health: 7, attackType: 'ranged' }],
    cards: dbCards(arthurCapture.cards),
  },
};

function makeDb() {
  const games = new Map<string, any>();
  const players = new Map<string, any>();
  const states = new Map<string, any>();
  const user = (id: string) => ({ id, username: `user-${id}`, avatar: null });
  const gameRow = (id: string) => {
    const game = games.get(id);
    if (!game) return null;
    const roster = [...players.values()].filter(p => p.gameId === id).sort((a, b) => a.seatOrder - b.seatOrder);
    return {
      ...game,
      host: user(game.hostId),
      opponent: game.opponentId ? user(game.opponentId) : null,
      players: roster.map(p => ({ ...p, user: user(p.userId) })),
      state: states.get(id) ?? null,
    };
  };
  let txTail = Promise.resolve();
  const serializeTx = (run: (tx: unknown) => unknown) => {
    const previous = txTail;
    let done!: () => void;
    txTail = new Promise<void>(yes => { done = yes; });
    return previous.then(() => Promise.resolve(run(prisma))).finally(() => done());
  };
  const prisma: any = {
    game: {
      findUnique: async ({ where }: any) => (where.id ? gameRow(where.id) : games.get(where.code) ?? null),
      update: async ({ where, data }: any) => {
        const game = games.get(where.id);
        games.set(where.id, { ...game, ...data });
        return games.get(where.id);
      },
    },
    gamePlayer: {
      findMany: async ({ where }: any) =>
        [...players.values()].filter(p => p.gameId === where.gameId)
          .sort((a, b) => a.seatOrder - b.seatOrder),
      create: async ({ data }: any) => { players.set(`${data.gameId}:${data.userId}`, data); return data; },
      update: async ({ where, data }: any) => {
        const key = where.id
          ? [...players.entries()].find(([, p]) => p.id === where.id)?.[0]
          : `${where.gameId_userId.gameId}:${where.gameId_userId.userId}`;
        const player = players.get(key!);
        players.set(key!, { ...player, ...data });
        return players.get(key!);
      },
      updateMany: async () => ({}),
      deleteMany: async () => ({ count: 0 }),
    },
    hero: { findUnique: async ({ where }: any) => heroes[where.id] ?? null },
    board: { findUnique: async ({ where }: any) => (where.id === source.id ? source : null) },
    gameState: {
      findUnique: async ({ where }: any) => states.get(where.gameId) ?? null,
      upsert: async ({ where, create }: any) => { states.set(where.gameId, create); return create; },
    },
    $transaction: serializeTx,
    $queryRaw: async () => [],
  };
  const redis = { getJson: async () => null, setJsonex: async () => 'OK', del: async () => 1 };
  return { prisma, redis, games, players, states };
}

function startFullGame(seat0: 'medusa' | 'arthur'): GameState {
  const db = makeDb();
  db.games.set('g1', { id: 'g1', hostId: 'u1', opponentId: 'u2', boardId: source.id,
    mode: 'ONE_V_ONE', status: 'LOBBY', code: 'AAAAAA', version: 0 });
  db.players.set('g1:u1', { id: 'p1', gameId: 'g1', userId: 'u1', seatOrder: 0, heroId: seat0, isReady: true });
  db.players.set('g1:u2', { id: 'p2', gameId: 'g1', userId: 'u2', seatOrder: 1, heroId: seat0 === 'medusa' ? 'arthur' : 'medusa', isReady: true });
  const saveState = jest.fn(async (_gameId: string, _state: GameState) => undefined);
  const service = new GameService(
    db.prisma,
    db.redis as any,
    new GameInitializationService(db.prisma, { saveState } as any),
    { recordAction: async () => 'id' } as any,
    { publishLobbyEvent: async () => ({}) } as any,
  );
  // startGame синхронно проводит init; состояние перехватываем через saveState
  return service.startGame('g1', 'u1').then(() => saveState.mock.calls[0][1] as GameState) as any;
}

const allCards = (state: GameState, userId: string) => [
  ...state.decks[userId].drawPile,
  ...state.handZones[userId].cards,
];

describe('GD-023: full-deck instance registry (production startGame, real 27 records)', () => {
  it('27 records → 60 copies per... exact 30+30: unique instance ids, 5+25 split, no overlaps', async () => {
    const state = await startFullGame('medusa');
    const u1Cards = allCards(state, 'u1');
    const u2Cards = allCards(state, 'u2');
    // каждая сторона — полная 30-карточная колода героя
    expect(u1Cards).toHaveLength(30);
    expect(u2Cards).toHaveLength(30);
    expect(state.handZones.u1.cards).toHaveLength(5);
    expect(state.decks.u1.drawPile).toHaveLength(25);
    expect(state.decks.u2.drawPile).toHaveLength(25);
    // ГЛОБАЛЬНО уникальные instance id (между игроками и копиями)
    const everyId = [...u1Cards, ...u2Cards].map((c) => c.id);
    expect(new Set(everyId).size).toBe(60);
    // формат `${cardId}::${copy}`; рука не пересекается с колодой
    for (const id of everyId) expect(id).toMatch(/^.+::\d+$/);
    const handIds = new Set(state.handZones.u1.cards.map((c) => c.id));
    for (const c of state.decks.u1.drawPile) expect(handIds.has(c.id)).toBe(false);
  });

  it('same-name copies stay distinguishable instances (Dash x2, Excalibur x1) with per-record banners', async () => {
    const state = await startFullGame('medusa');
    // Medusa-сторона: Dash count 3 → три разных instance id одной cardId
    const u1 = allCards(state, 'u1');
    const dash = u1.filter((c) => c.name === 'Dash');
    expect(dash).toHaveLength(3);
    expect(new Set(dash.map((c) => c.id)).size).toBe(3);
    expect(new Set(dash.map((c) => c.id.split('::')[0])).size).toBe(1);
    // Arthur-сторона: Excalibur count 1 — ровно один инстанс, BLANK
    const u2 = allCards(state, 'u2');
    const excalibur = u2.filter((c) => c.name === 'Excalibur');
    expect(excalibur).toHaveLength(1);
    expect(excalibur[0].effects).toHaveLength(0);
    // баннеры доехали в state: каждая карта 27 записей имеет непустой bannerName
    const bannerless = [...u1, ...u2].filter((c) => !c.bannerName);
    expect(bannerless).toHaveLength(0);
    const banners = new Set([...u1, ...u2].map((c) => c.bannerName));
    expect([...banners].sort()).toEqual(['Any', 'Arthur', 'Harpy', 'Medusa', 'Merlin']);
  });

  it('every non-Excalibur instance carries executable effects (no silent no-ops)', async () => {
    const state = await startFullGame('arthur'); // ориентация не влияет на колоды
    const every = [...allCards(state, 'u1'), ...allCards(state, 'u2')];
    const unsupported = every.filter(
      (c) => c.name !== 'Excalibur' && !c.effects.some((e) => e.type !== EffectType.UNSUPPORTED),
    );
    expect(unsupported.map((c) => c.name)).toEqual([]);
    const excalibur = every.find((c) => c.name === 'Excalibur')!;
    expect(excalibur.effects).toHaveLength(0);
  });

  it('writes the honest machine-readable registry to evidence/S06 (27 records)', async () => {
    const state = await startFullGame('medusa');
    const instances: Record<string, number> = {};
    for (const c of [...allCards(state, 'u1'), ...allCards(state, 'u2')]) {
      instances[`${c.cardId}`] = (instances[`${c.cardId}`] ?? 0) + 1;
    }
    const entries = [];
    for (const [heroName, capture, heroKey] of [
      ['Medusa', medusaCapture, 'medusa'],
      ['King Arthur', arthurCapture, 'arthur'],
    ] as const) {
      const side = heroKey === 'medusa' ? 'u1' : 'u2';
      for (const rec of capture.cards) {
        const sample = allCards(state, side).find((c) => c.cardId === rec.id)!;
        const hasSupported = sample.effects.some((e) => e.type !== EffectType.UNSUPPORTED);
        entries.push({
          hero: heroName,
          name: rec.name,
          cardType: rec.cardType,
          count: rec.count,
          bannerName: rec.bannerName,
          instanceCount: instances[rec.id] ?? 0,
          status: rec.name === 'Excalibur' ? 'BLANK' : hasSupported ? 'SUPPORTED' : 'UNSUPPORTED',
          effectTypes: sample.effects.map((e) => e.type),
        });
      }
    }
    expect(entries).toHaveLength(27);
    expect(entries.reduce((s, e) => s + e.instanceCount, 0)).toBe(60);
    expect(entries.filter((e) => e.status !== 'SUPPORTED' && e.status !== 'BLANK')).toEqual([]);
    expect(entries.filter((e) => e.status === 'BLANK').map((e) => e.name)).toEqual(['Excalibur']);

    const dir = resolve(root, 'docs/game-design/evidence/S06');
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    writeFileSync(
      resolve(dir, 's06-card-registry.json'),
      JSON.stringify({
        generatedBy: 'backend/src/games/services/s06-registry.spec.ts',
        source: 'docs/game-design/evidence/S01/content-{medusa,king-arthur}.json (frozen)',
        productionPath: 'GameService.startGame → GameInitializationService (resolveCardEffects)',
        records: entries.length,
        copies: entries.reduce((s, e) => s + e.instanceCount, 0),
        entries,
      }, null, 2),
    );
  });
});
