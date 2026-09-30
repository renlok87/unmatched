/**
 * ENV-MAPS -Bench fixtures: Config/Bench/S08Bench<Map>.json for the original
 * maps (Marmoreal, Sarpedon), in the exact shape of the captured Cobble bench
 * fixture (Config/Bench/S08BenchCobble.json, a gameState(gameId) response).
 *
 * The board and the starting positions are NOT hand-placed: this script runs
 * the server's own GameInitializationService.initializeGameState on the Board
 * row that prisma/seed-env-map-boards.ts builds from the committed topology
 * fixture (backend/prisma/fixtures/boards/<map>.topology.json), with a fake
 * Prisma (no DB). So the boardState cells (links / layout / start / spaceId /
 * zones / obstacles on the W x H lattice) and the positions are exactly what a
 * live room on that board would start with: seat 0 (Medusa) on start space 1,
 * her 3 Harpies by the server's graph BFS inside her zones, seat 1 (King
 * Arthur) on start space 2, Merlin by the same BFS.
 *
 * Everything else (players, user / hero ids, fighter names and stats, decks,
 * hands, metadata) is copied from the Cobble capture, so -ArtPreviewHeroesV2
 * maps the same four figures and the viewer (benchViewerId = seat 0) is the
 * same. benchBoardId = the fixture's deterministic Board id, which selects the
 * map-image art profile (<map>-original) and the env layout.
 *
 * Usage (from the repo root; backend/node_modules provides ts-node):
 *   node backend/node_modules/ts-node/dist/bin.js --transpile-only -P backend/tsconfig.json \
 *     tools/art/render/env_bench_fixtures.cts [--check]
 * --check: build in memory and compare with the committed files (exit 1 on drift).
 */
import * as fs from 'fs';
import * as path from 'path';

const REPO = path.resolve(__dirname, '..', '..', '..');
const BACKEND = path.join(REPO, 'backend');
/* eslint-disable @typescript-eslint/no-var-requires */
const { GameInitializationService } = require(
  path.join(BACKEND, 'src', 'games', 'services', 'game-initialization.service'),
);
const { fixtureFiles, loadTopologyFixture, topologyBoardRow } = require(
  path.join(BACKEND, 'prisma', 'seed-env-map-boards'),
);
/* eslint-enable @typescript-eslint/no-var-requires */

const BENCH_DIR = path.join(REPO, 'unreal', 'Unmatched', 'Config', 'Bench');
const COBBLE = path.join(BENCH_DIR, 'S08BenchCobble.json');
const MAPS: Array<{ key: string; file: string }> = [
  { key: 'marmoreal', file: 'S08BenchMarmoreal.json' },
  { key: 'sarpedon', file: 'S08BenchSarpedon.json' },
];

interface Fighter {
  id: string;
  ownerId: string;
  heroId: string;
  name: string;
  type: string;
  position: { x: number; y: number };
  sidekickIds?: string[];
  [k: string]: unknown;
}

async function serverStart(mapKey: string, cobbleState: any): Promise<any> {
  const file = fixtureFiles().find((f: string) => f.endsWith(`${mapKey}.topology.json`));
  const { fixture, sha256 } = loadTopologyFixture(file);
  // Board row exactly as the seed writes it (Json column = plain JSON copy).
  const board = JSON.parse(JSON.stringify(topologyBoardRow(fixture, sha256, file)));
  const cobbleFighters: Fighter[] = cobbleState.fighters;
  const seats = cobbleState.players.map((p: any) => p.userId as string);
  // Heroes as the placement sees them: the sidekick COUNT is what matters
  // (3 Harpies for Medusa, 1 Merlin for King Arthur, as in the Cobble capture).
  const heroes: Record<string, any> = {};
  for (const p of cobbleState.players) {
    const hero = cobbleFighters.find((f) => f.ownerId === p.userId && f.type === 'HERO')!;
    const sidekicks = cobbleFighters
      .filter((f) => f.ownerId === p.userId && f.type !== 'HERO')
      .map((f) => ({ name: f.name, health: f.maxHealth, movement: f.movement, attackType: f.attackType }));
    heroes[p.heroId] = {
      id: p.heroId,
      name: hero.name,
      health: hero.maxHealth,
      movement: hero.movement,
      properties: { attackType: hero.attackType },
      sidekicks,
    };
  }
  const prisma = {
    game: { findUnique: async () => ({ boardId: board.id }) },
    board: { findUnique: async () => board },
    gamePlayer: {
      findMany: async () =>
        cobbleState.players.map((p: any, seatOrder: number) => ({
          heroId: p.heroId,
          seatOrder,
          userId: seats[seatOrder],
        })),
    },
    hero: {
      findUnique: async ({ where }: any) => ({
        ...heroes[where.id],
        cards: [{ id: `${where.id}-bench`, name: 'Bench', cardType: 'VERSATILE', count: 30, effects: [] }],
      }),
    },
  };
  const quiet = { saveState: async () => undefined };
  const service = new GameInitializationService(prisma as any, quiet as any);
  (service as any).logger = { log: () => undefined, warn: (m: string) => console.warn('server warn:', m) };
  const state = await service.initializeGameState(`bench-${mapKey}`);
  // Wire hop (filterPrivateData -> JSON.stringify): undefined keys disappear.
  return { fixture, state: JSON.parse(JSON.stringify(state)) };
}

function spaceOf(boardState: any, pos: { x: number; y: number }): string {
  return boardState.cells[pos.y]?.[pos.x]?.spaceId ?? `(${pos.x},${pos.y})`;
}

async function build(mapKey: string, cobble: any): Promise<{ doc: any; summary: string }> {
  const cobbleState = JSON.parse(cobble.raw.data.gameState.state);
  const { fixture, state } = await serverStart(mapKey, cobbleState);
  const serverFighters: Fighter[] = state.fighters;
  const fighters = (cobbleState.fighters as Fighter[]).map((f) => {
    const placed = serverFighters.find((s) => s.id === f.id);
    if (!placed) throw new Error(`${mapKey}: server did not place ${f.id}`);
    return { ...f, position: { x: placed.position.x, y: placed.position.y } };
  });
  const out = { ...cobbleState, boardState: state.boardState, fighters };
  const summary = fighters
    .map((f) => `${f.id}=${spaceOf(state.boardState, f.position)}`)
    .join(' ');
  const gs = cobble.raw.data.gameState;
  const doc = {
    kind: cobble.kind,
    httpStatus: cobble.httpStatus,
    source:
      `ENV-MAPS bench fixture (${fixture.name}, board ${fixture.boardId}): the Cobble capture ` +
      `(S08BenchCobble.json: players, ids, fighters, decks, hands) with boardState and starting positions ` +
      `built by the server's GameInitializationService on the seed-env-map-boards Board row of ` +
      `backend/prisma/fixtures/boards/${mapKey}.topology.json (start 1 Medusa + 3 Harpies by graph BFS in her ` +
      `zones, start 2 King Arthur + Merlin); generated by tools/art/render/env_bench_fixtures.cts ` +
      `(not a live capture, not a rules fixture). Positions: ${summary}`,
    benchViewerId: cobble.benchViewerId,
    benchBoardId: fixture.boardId,
    raw: {
      data: {
        gameState: {
          ...gs,
          state: JSON.stringify(out),
        },
      },
    },
  };
  return { doc, summary };
}

async function main(): Promise<void> {
  const check = process.argv.includes('--check');
  const cobble = JSON.parse(fs.readFileSync(COBBLE, 'utf8'));
  let drift = 0;
  for (const m of MAPS) {
    const { doc, summary } = await build(m.key, cobble);
    const text = JSON.stringify(doc, null, 1) + '\n';
    const dst = path.join(BENCH_DIR, m.file);
    if (check) {
      const same = fs.existsSync(dst) && fs.readFileSync(dst, 'utf8').replace(/\r\n/g, '\n') === text;
      if (!same) drift++;
      console.log(`ENV-BENCH-FIXTURE ${m.key} ${same ? 'ok' : 'DRIFT'} ${m.file} ${summary}`);
    } else {
      fs.writeFileSync(dst, text, 'utf8');
      console.log(`ENV-BENCH-FIXTURE ${m.key} wrote ${m.file} board=${doc.benchBoardId} ${summary}`);
    }
  }
  if (drift) process.exitCode = 1;
}

main().catch((e) => {
  console.error('ENV-BENCH-FIXTURE FAILED', e instanceof Error ? e.stack : String(e));
  process.exitCode = 1;
});
