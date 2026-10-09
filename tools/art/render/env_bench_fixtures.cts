/**
 * ENV-MAPS -Bench fixtures: Config/Bench/S08Bench<Map>.json for the original
 * maps (Marmoreal, Sarpedon), in the shape of a gameState(gameId) response.
 *
 * Template (2026-10-04, real boards only): the committed Marmoreal fixture
 * (Config/Bench/S08BenchMarmoreal.json). Its non-board content is the former
 * Cobble capture (S08BenchCobble.json, removed with the Cobble City board), so
 * the generated files stay byte for byte what they were; the "source" text
 * keeps that provenance. Only its players / ids / fighters / decks / hands /
 * metadata are read - its boardState and positions are replaced below.
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
 * hands, metadata) is copied from the template, so -ArtPreviewHeroesV2
 * maps the same four figures and the viewer (benchViewerId = seat 0) is the
 * same. benchBoardId = the fixture's deterministic Board id, which selects the
 * map-image art profile (<map>-original) and the env layout.
 *
 * Usage (from the repo root; backend/node_modules provides ts-node):
 *   node backend/node_modules/ts-node/dist/bin.js --transpile-only -P backend/tsconfig.json \
 *     tools/art/render/env_bench_fixtures.cts [--check] [--out-dir <dir>]
 *   ... env_bench_fixtures.cts --variant <Key> --hero-name "<FighterName>" --hero-slug <slug>
 *     [--sidekick-name "<FighterName>"] [--maps marmoreal,sarpedon] [--out-dir <dir>]
 * --check: build in memory and compare with the committed files (exit 1 on drift); also rebuilds every
 *   variant file S08Bench<Map>-<Key>.json found in --out-dir (default Config/Bench) from its benchVariant
 *   record and reports drift the same way.
 *
 * Variant mode (new character, .agents/skills/3d-model-pipeline/references/new-character-registration.md
 * D-2): S08Bench<Map>-<Key>.json per map = the canonical fixture of that map with seat 1 re-cast - the new hero
 * on f-1-hero (King Arthur's place: name = --hero-name, heroSlug = --hero-slug) and the new sidekick on f-1-sk0
 * (Merlin's place: name = --sidekick-name; without it Merlin stays as a stand-in figure). Both carry the new
 * heroSlug (the owner's slug, as Merlin carries king-arthur). Ids, positions, stats, decks, hands, players and
 * the board are unchanged: the server places by the sidekick COUNT only (one sidekick on seat 1 either way).
 * The client maps a figure by fighter name (S08HeroesV2::Find), so --hero-name / --sidekick-name must be the
 * FighterName of the new S08HeroesV2::Specs() rows. The root field benchVariant records the parameters (the
 * client ignores it; --check rebuilds the file from it).
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
const TEMPLATE = path.join(BENCH_DIR, 'S08BenchMarmoreal.json');
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

// ---- variant mode (D-2: the new character on seat 1) ------------------------------------------------------------

interface VariantSpec {
  key: string;
  heroName: string;
  heroSlug: string;
  sidekickName?: string;
}

const VARIANT_HERO = 'f-1-hero';
const VARIANT_SIDEKICK = 'f-1-sk0';
const VARIANT_FILE = /^S08Bench(Marmoreal|Sarpedon)-([A-Za-z][A-Za-z0-9]*)\.json$/;

class UsageError extends Error {}

function variantFile(m: { file: string }, key: string): string {
  return m.file.replace(/\.json$/, `-${key}.json`);
}

function checkVariantSpec(v: VariantSpec): void {
  if (!/^[A-Za-z][A-Za-z0-9]*$/.test(v.key)) throw new UsageError(`--variant ${v.key}: letters / digits only (the UE hero Key)`);
  if (!v.heroName || !v.heroName.trim()) throw new UsageError('--hero-name is required (the FighterName of the new Specs() row)');
  if (!/^[a-z0-9]+(-[a-z0-9]+)*$/.test(v.heroSlug || '')) throw new UsageError(`--hero-slug ${v.heroSlug}: kebab-case slug`);
  if (v.sidekickName !== undefined && !v.sidekickName.trim()) throw new UsageError('--sidekick-name is empty');
}

/** The canonical doc of one map with seat 1 re-cast (pure: the input doc is not changed). */
function applyVariant(mapKey: string, baseFile: string, base: any, v: VariantSpec): any {
  const gs = base.raw.data.gameState;
  const state = JSON.parse(gs.state);
  const hero = (state.fighters as Fighter[]).find((f) => f.id === VARIANT_HERO);
  const sk = (state.fighters as Fighter[]).find((f) => f.id === VARIANT_SIDEKICK);
  if (!hero || hero.type !== 'HERO') throw new Error(`${mapKey}: ${VARIANT_HERO} is not the seat-1 hero`);
  if (!sk || !(hero.sidekickIds || []).includes(VARIANT_SIDEKICK)) {
    throw new Error(`${mapKey}: ${VARIANT_SIDEKICK} is not ${VARIANT_HERO}'s sidekick`);
  }
  const was = `${hero.name} + ${sk.name}`;
  hero.name = v.heroName;
  hero.heroSlug = v.heroSlug;
  if (v.sidekickName !== undefined) sk.name = v.sidekickName;
  sk.heroSlug = v.heroSlug;
  const benchVariant: any = { key: v.key, base: baseFile, heroName: v.heroName, heroSlug: v.heroSlug };
  if (v.sidekickName !== undefined) benchVariant.sidekickName = v.sidekickName;
  benchVariant.recast = [VARIANT_HERO, VARIANT_SIDEKICK];
  return {
    kind: base.kind,
    httpStatus: base.httpStatus,
    source:
      `Variant ${v.key} of ${baseFile} (new-character bench scene, new-character-registration.md D-2): seat 1 ` +
      `${was} re-cast as ${hero.name} + ${sk.name} (${VARIANT_HERO} / ${VARIANT_SIDEKICK}: name, heroSlug=${v.heroSlug}); ` +
      `ids, positions, stats, decks, hands and the board are the base fixture's; generated by ` +
      `tools/art/render/env_bench_fixtures.cts --variant. Base: ${base.source}`,
    benchViewerId: base.benchViewerId,
    benchBoardId: base.benchBoardId,
    benchVariant,
    raw: { data: { gameState: { ...gs, state: JSON.stringify(state) } } },
  };
}

function argValue(argv: string[], name: string): string | undefined {
  const i = argv.indexOf(name);
  if (i < 0) return undefined;
  const v = argv[i + 1];
  if (v === undefined || v.startsWith('--')) throw new UsageError(`${name} needs a value`);
  return v;
}

const KNOWN = new Set(['--check', '--out-dir', '--variant', '--hero-name', '--hero-slug', '--sidekick-name', '--maps']);

async function main(): Promise<void> {
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    if (!argv[i].startsWith('--')) continue;
    if (!KNOWN.has(argv[i])) throw new UsageError(`unknown option ${argv[i]}`);
  }
  const check = argv.includes('--check');
  const outDir = path.resolve(argValue(argv, '--out-dir') ?? BENCH_DIR);
  const variantKey = argValue(argv, '--variant');
  if (check && variantKey !== undefined) throw new UsageError('--check and --variant are separate runs');
  // Read once before any write: the template is one of the outputs.
  const cobble = JSON.parse(fs.readFileSync(TEMPLATE, 'utf8'));
  const built = new Map<string, { doc: any; summary: string }>();
  for (const m of MAPS) built.set(m.key, await build(m.key, cobble));

  if (variantKey !== undefined) {
    const v: VariantSpec = {
      key: variantKey,
      heroName: argValue(argv, '--hero-name') ?? '',
      heroSlug: argValue(argv, '--hero-slug') ?? '',
      sidekickName: argValue(argv, '--sidekick-name'),
    };
    checkVariantSpec(v);
    const want = (argValue(argv, '--maps') ?? MAPS.map((m) => m.key).join(',')).split(',').filter(Boolean);
    for (const k of want) if (!MAPS.some((m) => m.key === k)) throw new UsageError(`--maps: unknown map ${k}`);
    fs.mkdirSync(outDir, { recursive: true });
    for (const m of MAPS.filter((x) => want.includes(x.key))) {
      const doc = applyVariant(m.key, m.file, built.get(m.key)!.doc, v);
      const file = variantFile(m, v.key);
      fs.writeFileSync(path.join(outDir, file), JSON.stringify(doc, null, 1) + '\n', 'utf8');
      console.log(
        `ENV-BENCH-FIXTURE ${m.key} variant=${v.key} wrote ${path.join(outDir, file)} ` +
          `${VARIANT_HERO}=${v.heroName} ${VARIANT_SIDEKICK}=${doc.benchVariant.sidekickName ?? '(base sidekick kept)'} ` +
          `heroSlug=${v.heroSlug} board=${doc.benchBoardId}`,
      );
    }
    return;
  }

  let drift = 0;
  for (const m of MAPS) {
    const { doc, summary } = built.get(m.key)!;
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
  if (check && fs.existsSync(outDir)) {
    // the variants: each rebuilt from its own benchVariant record over the canonical build of its map
    for (const name of fs.readdirSync(outDir).sort()) {
      const hit = VARIANT_FILE.exec(name);
      if (!hit) continue;
      const m = MAPS.find((x) => x.file === `S08Bench${hit[1]}.json`)!;
      const file = path.join(outDir, name);
      let same = false;
      let why = '';
      try {
        const have = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n');
        const rec = JSON.parse(have).benchVariant;
        if (!rec || rec.key !== hit[2] || rec.base !== m.file) {
          why = ' (no / foreign benchVariant record)';
        } else {
          const v: VariantSpec = { key: rec.key, heroName: rec.heroName, heroSlug: rec.heroSlug, sidekickName: rec.sidekickName };
          checkVariantSpec(v);
          same = have === JSON.stringify(applyVariant(m.key, m.file, built.get(m.key)!.doc, v), null, 1) + '\n';
        }
      } catch (e) {
        why = ` (${e instanceof Error ? e.message : String(e)})`;
      }
      if (!same) drift++;
      console.log(`ENV-BENCH-FIXTURE ${m.key} variant=${hit[2]} ${same ? 'ok' : 'DRIFT'} ${name}${why}`);
    }
  }
  if (drift) process.exitCode = 1;
}

main().catch((e) => {
  if (e instanceof UsageError) {
    console.error(`ENV-BENCH-FIXTURE usage: ${e.message}`);
    process.exitCode = 2;
    return;
  }
  console.error('ENV-BENCH-FIXTURE FAILED', e instanceof Error ? e.stack : String(e));
  process.exitCode = 1;
});
