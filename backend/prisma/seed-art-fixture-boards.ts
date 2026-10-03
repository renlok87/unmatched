/**
 * Art-board fixtures -> ISOLATED test database only (stage 3 T3.2, variant (a)).
 *
 * «art fixture, не правила»: grid approximations of real maps (Sherwood Forest,
 * T. Rex Paddock) for the -ArtPreview art review. The fixtures are generated and
 * validated by tools/art/art_board_fixtures.py from scraped-data/api/maps.json and
 * committed as backend/prisma/fixtures/art-boards/*.art-fixture.json. This script
 * only copies them into Board rows with their deterministic ids, so a reseed gives
 * the same ids (the UE board profiles and the demo gates key on them).
 *
 * Safety:
 *   - writes ONLY to the isolated S09 test database (127.0.0.1/localhost:55434);
 *     every other DATABASE_URL (the main dev DB on 5433, anything remote) is refused
 *     before a client is created;
 *   - never touches rows it did not create (upsert by the fixture ids only);
 *   - refuses to become the default board: createGame without boardId picks the
 *     FIRST created Board row, so an empty Board table is refused;
 *   - map images are not referenced (imageUrl null): only their sha256 travels in
 *     Board.features.source.
 *
 * Usage (from backend/, credentials stay in the ignored backend/.env):
 *   node node_modules/ts-node/dist/bin.js --transpile-only prisma/seed-art-fixture-boards.ts --dry-run
 *   node node_modules/ts-node/dist/bin.js --transpile-only prisma/seed-art-fixture-boards.ts --apply [--report <json>]
 *   node node_modules/ts-node/dist/bin.js --transpile-only prisma/seed-art-fixture-boards.ts --verify [--report <json>]
 */
import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';

export const ISOLATED_DB_PORTS = ['55434'];
export const ISOLATED_DB_HOSTS = ['127.0.0.1', 'localhost'];
/**
 * Canonical dev DB (user decision 2026-10-03, docs/backend-api/db-divergence-2026-10-03.md: one identical data set
 * on every stand). Allowed only with the explicit `--allow-main-dev-db` flag; the stands are then cloned from it
 * by tools/db/sync-dev-stands.cjs.
 */
export const MAIN_DEV_DB = { port: '5433', database: 'unmatched' };

export interface DbGuardOptions {
  allowMainDevDb?: boolean;
}

/** True for the local main dev DB (localhost/127.0.0.1:5433/unmatched). */
export function isMainDevDatabase(parsed: URL): boolean {
  return (
    ISOLATED_DB_HOSTS.includes(parsed.hostname) &&
    parsed.port === MAIN_DEV_DB.port &&
    parsed.pathname.replace(/^\//, '') === MAIN_DEV_DB.database
  );
}
export const FIXTURE_DIR = path.join(__dirname, 'fixtures', 'art-boards');
export const FIXTURE_SCHEMA = 'unmatched.art-board-fixture/1';
const ID_RE = /^c[a-z0-9]{24}$/;

export interface ArtFixtureCell {
  x: number;
  y: number;
  zones?: string[];
  isObstacle?: boolean;
}

export interface ArtFixture {
  schema: string;
  artFixture: boolean;
  label: string;
  status: string;
  key: string;
  boardId: string;
  name: string;
  set: string;
  generator: { tool: string; fixtureVersion: number };
  source: Record<string, unknown> & { mapsJsonSha256: string; image?: { sha256: string } | null };
  grid: { width: number; height: number };
  summary: { cells: number; spaceCells: number; multizoneCells: number; obstacleCells: number };
  cells: ArtFixtureCell[];
}

/** Refuses every database except the isolated S09 test DB (and, with allowMainDevDb, the local main dev DB). */
export function assertIsolatedDatabase(url: string | undefined, opts: DbGuardOptions = {}): URL {
  if (!url) throw new Error('DATABASE_URL is not set');
  let parsed: URL;
  try {
    parsed = new URL(url);
  } catch {
    throw new Error('DATABASE_URL is not a URL');
  }
  if (opts.allowMainDevDb && isMainDevDatabase(parsed)) return parsed;
  if (!ISOLATED_DB_HOSTS.includes(parsed.hostname) || !ISOLATED_DB_PORTS.includes(parsed.port)) {
    throw new Error(
      `REFUSED: art fixtures go only to the isolated test DB (${ISOLATED_DB_HOSTS.join('|')}:${ISOLATED_DB_PORTS.join('|')}), ` +
        `got ${parsed.hostname}:${parsed.port || '(default)'} - the main dev DB is never written`,
    );
  }
  return parsed;
}

/** Validates a fixture file and returns it with the sha256 of its exact bytes. */
export function loadFixture(file: string): { fixture: ArtFixture; sha256: string } {
  const bytes = fs.readFileSync(file);
  const fixture = JSON.parse(bytes.toString('utf8')) as ArtFixture;
  const errs: string[] = [];
  if (fixture.schema !== FIXTURE_SCHEMA) errs.push('schema');
  if (fixture.artFixture !== true || fixture.label !== 'art fixture, не правила') errs.push('art fixture mark');
  if (!ID_RE.test(fixture.boardId || '')) errs.push('boardId is not cuid-shaped');
  const w = fixture.grid?.width;
  const h = fixture.grid?.height;
  if (!Number.isInteger(w) || !Number.isInteger(h) || w < 2 || h < 2 || w > 50 || h > 50) errs.push('grid size');
  if (!Array.isArray(fixture.cells) || fixture.cells.length !== w * h) errs.push('cells != W*H');
  let maxX = -1;
  let maxY = -1;
  for (const c of fixture.cells || []) {
    if (!Number.isInteger(c.x) || !Number.isInteger(c.y) || c.x < 0 || c.y < 0) errs.push(`bad cell ${JSON.stringify(c)}`);
    maxX = Math.max(maxX, c.x);
    maxY = Math.max(maxY, c.y);
    if (c.isObstacle && c.zones?.length) errs.push(`obstacle with zones at ${c.x},${c.y}`);
    if (!c.isObstacle && !(Array.isArray(c.zones) && c.zones.length > 0)) errs.push(`space without zones at ${c.x},${c.y}`);
  }
  // buildBoardState derives W x H from max(x)+1 / max(y)+1 - it must equal the fixture grid
  if (maxX + 1 !== w || maxY + 1 !== h) errs.push(`derived size ${maxX + 1}x${maxY + 1} != grid ${w}x${h}`);
  if (errs.length) throw new Error(`${path.basename(file)}: invalid fixture: ${errs.join('; ')}`);
  return { fixture, sha256: crypto.createHash('sha256').update(bytes).digest('hex') };
}

/** Board row data for one fixture (Board.width/height = grid cells, see backfill-board-cells.ts). */
export function boardRowFor(fixture: ArtFixture, sha256: string, fixtureFile: string) {
  return {
    id: fixture.boardId,
    name: fixture.name,
    nameEn: fixture.name,
    nameRu: fixture.name,
    set: fixture.set,
    width: fixture.grid.width,
    height: fixture.grid.height,
    cells: fixture.cells as unknown as object,
    features: {
      artFixture: true,
      label: fixture.label,
      status: fixture.status,
      key: fixture.key,
      fixture: `backend/prisma/fixtures/art-boards/${path.basename(fixtureFile)}`,
      fixtureSha256: sha256,
      generator: fixture.generator,
      source: fixture.source,
      summary: fixture.summary,
    },
    imageUrl: null as string | null,
    imageUrlDark: null as string | null,
  };
}

function argValue(args: string[], name: string): string | undefined {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const mode = args.includes('--apply') ? 'apply' : args.includes('--verify') ? 'verify' : 'dry-run';
  const reportPath = argValue(args, '--report');
  // Credentials come from the ignored backend/.env of THIS checkout (never argv).
  // eslint-disable-next-line @typescript-eslint/no-var-requires
  require('dotenv').config({ path: path.join(__dirname, '..', '.env') });
  const db = assertIsolatedDatabase(process.env.DATABASE_URL, { allowMainDevDb: args.includes('--allow-main-dev-db') });

  const files = fs
    .readdirSync(FIXTURE_DIR)
    .filter((f) => f.endsWith('.art-fixture.json'))
    .sort()
    .map((f) => path.join(FIXTURE_DIR, f));
  if (files.length === 0) throw new Error(`no fixtures in ${FIXTURE_DIR}`);
  const loaded = files.map((f) => ({ file: f, ...loadFixture(f) }));

  // eslint-disable-next-line @typescript-eslint/no-var-requires
  const { PrismaClient } = require('@prisma/client');
  const prisma = new PrismaClient();
  const report: Record<string, unknown> = {
    schema: 'unmatched.art-fixture-seed/1',
    mode,
    startedUtc: new Date().toISOString(),
    database: { host: db.hostname, port: db.port, name: db.pathname.replace(/^\//, ''), rule: 'isolated S09 test DB only' },
    label: 'art fixture, не правила',
    boards: [] as unknown[],
  };
  try {
    const first = await prisma.board.findFirst({ orderBy: { createdAt: 'asc' }, select: { id: true, name: true } });
    report.defaultBoardBefore = first;
    if (!first) throw new Error('REFUSED: Board table is empty - a fixture would become the default board of createGame');
    for (const { file, fixture, sha256 } of loaded) {
      const row = boardRowFor(fixture, sha256, file);
      const existing = await prisma.board.findUnique({ where: { id: row.id } });
      const clash = await prisma.board.findUnique({ where: { name: row.name } });
      if (clash && clash.id !== row.id) throw new Error(`REFUSED: Board name "${row.name}" belongs to another row ${clash.id}`);
      const entry: Record<string, unknown> = {
        key: fixture.key,
        id: row.id,
        name: row.name,
        grid: `${row.width}x${row.height}`,
        fixtureSha256: sha256,
        existedBefore: Boolean(existing),
      };
      if (mode === 'apply') {
        const { id, ...data } = row;
        await prisma.board.upsert({ where: { id }, create: row, update: data });
        entry.written = true;
      }
      if (mode !== 'dry-run') {
        const back = await prisma.board.findUnique({ where: { id: row.id } });
        const cellsOk = Boolean(back) && JSON.stringify(back.cells) === JSON.stringify(row.cells);
        const features = (back?.features ?? {}) as Record<string, unknown>;
        entry.verify = {
          present: Boolean(back),
          cellsIdentical: cellsOk,
          featuresArtFixture: features.artFixture === true,
          featuresFixtureSha256: features.fixtureSha256 === sha256,
          sizeIdentical: back?.width === row.width && back?.height === row.height,
          imageUrlNull: back?.imageUrl == null,
        };
        entry.verified = Object.values(entry.verify as Record<string, boolean>).every(Boolean);
      }
      (report.boards as unknown[]).push(entry);
    }
    const firstAfter = await prisma.board.findFirst({ orderBy: { createdAt: 'asc' }, select: { id: true, name: true } });
    report.defaultBoardAfter = firstAfter;
    report.defaultBoardUnchanged = firstAfter?.id === first.id;
    report.ok =
      report.defaultBoardUnchanged === true &&
      (mode === 'dry-run' || (report.boards as Array<Record<string, unknown>>).every((b) => b.verified === true));
  } finally {
    await prisma.$disconnect();
  }
  report.finishedUtc = new Date().toISOString();
  const text = JSON.stringify(report, null, 2) + '\n';
  if (reportPath) fs.writeFileSync(reportPath, text, 'utf8');
  process.stdout.write(text);
  if (!report.ok) process.exitCode = 1;
}

if (require.main === module) {
  main().catch((error) => {
    console.error('ART_FIXTURE_SEED_FAILED:', error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
