/**
 * ENV-MAPS original-map boards -> ISOLATED test database only.
 *
 * Medusa (+3 Harpy) vs King Arthur (+Merlin) are played on the ORIGINAL maps of
 * Battle of Legends Vol. 1 - Marmoreal and Sarpedon - by the graph of spaces and
 * lines (contract unmatched.board-topology/1), not by a grid. The topology is
 * built and validated by tools/art/board_topology.py and committed as
 * backend/prisma/fixtures/boards/<map>.topology.json. This script only copies
 * those fixtures into Board rows with their deterministic ids
 * ('c' + 24 hex of sha256("unmatched-board-topology:<map>:v1")), so a reseed
 * gives the same ids.
 *
 * Board row:
 *   - id = fixture.boardId; width/height = the lattice (buildBoardState derives
 *     the grid from max(x)+1 / max(y)+1 of the cells and must get the same size);
 *   - cells = fixture.cells verbatim (spaceId / zones / layout / start / links;
 *     every lattice position without a space is an explicit {x, y, isObstacle});
 *   - name = "<Map> · original map" (Board.name is unique and a scraped
 *     "<Map>" row may already exist); nameEn/nameRu = the map name;
 *   - features = { topology: true, fixture path + sha256, source image path +
 *     sha256 + size (ENV-U3: the image itself stays out of git and out of the
 *     DB - imageUrl is null), zones palette, uuPerPx, spaceRadiusPx, summary }.
 *
 * Safety (DB guards in prisma/db-guards.ts):
 *   - writes ONLY to the isolated S09 test database (127.0.0.1/localhost:55434),
 *     or with --allow-main-dev-db to the canonical dev DB localhost:5433/unmatched;
 *     every other DATABASE_URL is refused before a client is created;
 *   - never touches rows it did not create (upsert by the fixture ids only; a
 *     name owned by another row is refused);
 *   - writes the default board: createGame without boardId plays on
 *     Marmoreal · original map (src/games/default-board.ts, decision НД-1 of
 *     docs/game-design/decisions/2026-10-04-real-boards-only.md). The pinned id
 *     must be one of the fixtures (refused otherwise), and --apply/--verify fail
 *     unless that row is present and verified afterwards.
 *
 * Modes:
 *   --dry-run (default) OFFLINE: validates both fixtures, builds the rows and
 *                        reports them; DATABASE_URL (if set) is only checked
 *                        against the isolated-DB rule - no connection is made;
 *   --apply              upsert + read-back verification;
 *   --verify             read-back verification only.
 *
 * Usage (from backend/, credentials stay in the ignored backend/.env):
 *   node node_modules/ts-node/dist/bin.js --transpile-only prisma/seed-env-map-boards.ts --dry-run
 *   node node_modules/ts-node/dist/bin.js --transpile-only prisma/seed-env-map-boards.ts --apply [--report <json>]
 *   node node_modules/ts-node/dist/bin.js --transpile-only prisma/seed-env-map-boards.ts --verify [--report <json>]
 */
import * as crypto from 'crypto';
import * as fs from 'fs';
import * as path from 'path';
import type { Prisma } from '@prisma/client';
import { DbGuardOptions, ISOLATED_DB_HOSTS, ISOLATED_DB_PORTS, isMainDevDatabase } from './db-guards';
import { DEFAULT_BOARD_ID, DEFAULT_BOARD_NAME } from '../src/games/default-board';

/**
 * Refuses every database except the isolated S09 test DB (throws). With `--allow-main-dev-db`
 * (opts.allowMainDevDb) the local main dev DB localhost:5433/unmatched is accepted as well - the canonical
 * data set the stands are cloned from (docs/backend-api/db-divergence-2026-10-03.md).
 */
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
      `REFUSED: original-map boards go only to the isolated test DB (${ISOLATED_DB_HOSTS.join('|')}:${ISOLATED_DB_PORTS.join('|')}), ` +
        `got ${parsed.hostname}:${parsed.port || '(default)'} - the main dev DB is never written`,
    );
  }
  return parsed;
}

export const TOPOLOGY_FIXTURE_DIR = path.join(__dirname, 'fixtures', 'boards');
export const TOPOLOGY_SCHEMA = 'unmatched.board-topology/1';
export const TOPOLOGY_MAPS = ['marmoreal', 'sarpedon'] as const;
export const TOPOLOGY_SET = 'battle-of-legends-volume-one';
const ID_RE = /^c[a-z0-9]{24}$/;
const SHA_RE = /^[0-9a-f]{64}$/;

export type TopologyMap = (typeof TOPOLOGY_MAPS)[number];

export interface TopologyPosition {
  x: number;
  y: number;
}

export interface TopologyCell {
  x: number;
  y: number;
  isObstacle?: boolean;
  spaceId?: string;
  zones?: string[];
  layout?: TopologyPosition;
  start?: number;
  links?: TopologyPosition[];
}

export interface TopologySpace {
  id: string;
  x: number;
  y: number;
  layout: TopologyPosition;
  zones: string[];
  start: number | null;
  links: string[];
}

export interface TopologyFixture {
  schema: string;
  map: TopologyMap;
  name: string;
  set: string;
  boardId: string;
  status?: string;
  generator?: Record<string, unknown>;
  source: {
    image: string;
    sha256: string;
    size: [number, number];
    provenance?: Record<string, unknown>;
  };
  uuPerPx: number;
  spaceRadiusPx: number;
  lattice: { width: number; height: number };
  zones: Array<{ key: string; color: string }>;
  spaces: TopologySpace[];
  edges: Array<[string, string]>;
  crossings?: unknown[];
  cells: TopologyCell[];
  summary?: Record<string, unknown>;
}

/** Deterministic Board id of a topology map (same as tools/art/board_topology.py). */
export function topologyBoardId(map: string, version = 1): string {
  return (
    'c' +
    crypto
      .createHash('sha256')
      .update(`unmatched-board-topology:${map}:v${version}`, 'utf8')
      .digest('hex')
      .slice(0, 24)
  );
}

/**
 * sha256 of the fixture bytes with CRLF normalised to LF: the fixtures are
 * committed LF (backend/prisma/fixtures/boards/.gitattributes eol=lf), so this
 * is the hash of the committed blob even on a checkout that rewrote newlines.
 */
export function fixtureSha256(bytes: Buffer | string): string {
  const text = (typeof bytes === 'string' ? bytes : bytes.toString('utf8')).replace(/\r\n/g, '\n');
  return crypto.createHash('sha256').update(text, 'utf8').digest('hex');
}

const posKey = (p: TopologyPosition) => `${p.x}:${p.y}`;

/** Full contract check of one parsed fixture; returns the list of violations. */
export function validateTopologyFixture(fx: TopologyFixture, expectedMap?: string): string[] {
  const errs: string[] = [];
  if (fx?.schema !== TOPOLOGY_SCHEMA) errs.push('schema');
  if (!TOPOLOGY_MAPS.includes(fx?.map)) errs.push(`unknown map ${String(fx?.map)}`);
  if (expectedMap && fx?.map !== expectedMap)
    errs.push(`map ${String(fx?.map)} != file ${expectedMap}`);
  if (fx?.set !== TOPOLOGY_SET) errs.push('set');
  if (typeof fx?.name !== 'string' || fx.name.length === 0) errs.push('name');
  if (!ID_RE.test(fx?.boardId || '')) errs.push('boardId is not cuid-shaped');
  else if (fx.boardId !== topologyBoardId(fx.map))
    errs.push('boardId is not the deterministic topology id');
  if (!SHA_RE.test(fx?.source?.sha256 || '')) errs.push('source.sha256');
  if (
    typeof fx?.source?.image !== 'string' ||
    !fx.source.image.startsWith('scraped-data/images/maps/')
  ) {
    errs.push('source.image must be the gitignored scraped-data path');
  }
  const w = fx?.lattice?.width;
  const h = fx?.lattice?.height;
  if (!Number.isInteger(w) || !Number.isInteger(h) || w < 2 || h < 2 || w > 50 || h > 50) {
    errs.push('lattice size');
    return errs;
  }
  const cells = Array.isArray(fx.cells) ? fx.cells : [];
  if (cells.length !== w * h) errs.push(`cells ${cells.length} != W*H ${w * h}`);
  const zoneKeys = new Set((fx.zones || []).map((z) => z.key));

  const byPos = new Map<string, TopologyCell>();
  let maxX = -1;
  let maxY = -1;
  for (const c of cells) {
    if (
      !Number.isInteger(c.x) ||
      !Number.isInteger(c.y) ||
      c.x < 0 ||
      c.y < 0 ||
      c.x >= w ||
      c.y >= h
    ) {
      errs.push(`bad cell ${JSON.stringify(c)}`);
      continue;
    }
    if (byPos.has(posKey(c))) errs.push(`duplicate cell ${posKey(c)}`);
    byPos.set(posKey(c), c);
    maxX = Math.max(maxX, c.x);
    maxY = Math.max(maxY, c.y);
    if (c.isObstacle) {
      // A hole of the lattice: exactly {x, y, isObstacle: true}
      const extra = Object.keys(c).filter((k) => !['x', 'y', 'isObstacle'].includes(k));
      if (c.isObstacle !== true || extra.length)
        errs.push(`obstacle ${posKey(c)} carries ${extra.join(',')}`);
      continue;
    }
    if (typeof c.spaceId !== 'string' || !c.spaceId)
      errs.push(`space without spaceId at ${posKey(c)}`);
    if (!Array.isArray(c.zones) || c.zones.length === 0)
      errs.push(`space without zones at ${posKey(c)}`);
    for (const z of c.zones || [])
      if (!zoneKeys.has(z)) errs.push(`unknown zone ${z} at ${posKey(c)}`);
    if (!c.layout || !Number.isFinite(c.layout.x) || !Number.isFinite(c.layout.y))
      errs.push(`layout at ${posKey(c)}`);
    if (c.start !== undefined && !(Number.isInteger(c.start) && c.start >= 1 && c.start <= 4)) {
      errs.push(`start at ${posKey(c)}`);
    }
    if (!Array.isArray(c.links)) errs.push(`space without links at ${posKey(c)}`);
  }
  // buildBoardState derives W x H from max(x)+1 / max(y)+1 - it must equal the lattice
  if (maxX + 1 !== w || maxY + 1 !== h)
    errs.push(`derived size ${maxX + 1}x${maxY + 1} != lattice ${w}x${h}`);

  // Links: targets are spaces, no self/duplicate links, symmetric
  let directed = 0;
  for (const c of byPos.values()) {
    if (c.isObstacle) continue;
    const seen = new Set<string>();
    for (const l of c.links || []) {
      directed++;
      const t = byPos.get(posKey(l));
      if (!t || t.isObstacle) errs.push(`${c.spaceId} links to a non-space ${posKey(l)}`);
      else if (!(t.links || []).some((b) => b.x === c.x && b.y === c.y)) {
        errs.push(`asymmetric link ${c.spaceId}->${t.spaceId}`);
      }
      if (l.x === c.x && l.y === c.y) errs.push(`${c.spaceId} links to itself`);
      if (seen.has(posKey(l))) errs.push(`${c.spaceId} duplicate link ${posKey(l)}`);
      seen.add(posKey(l));
    }
  }

  // spaces[] / edges[] agree with the cells (the cells are what the engine reads)
  const spaces = Array.isArray(fx.spaces) ? fx.spaces : [];
  const byId = new Map(spaces.map((s) => [s.id, s]));
  const spaceCells = [...byPos.values()].filter((c) => !c.isObstacle);
  if (spaces.length !== spaceCells.length)
    errs.push(`spaces ${spaces.length} != space cells ${spaceCells.length}`);
  for (const c of spaceCells) {
    const s = byId.get(c.spaceId);
    if (!s) {
      errs.push(`cell space ${c.spaceId} missing in spaces[]`);
      continue;
    }
    if (s.x !== c.x || s.y !== c.y) errs.push(`${s.id} position`);
    if (JSON.stringify(s.zones) !== JSON.stringify(c.zones)) errs.push(`${s.id} zones`);
    if ((s.start ?? undefined) !== c.start) errs.push(`${s.id} start`);
    // same set of linked spaces (orders may differ: spaces[] lists ids, cells[] positions)
    const linked = (s.links || [])
      .map((id) => byId.get(id))
      .map((t) => (t ? posKey(t) : '?'))
      .sort();
    if (JSON.stringify(linked) !== JSON.stringify((c.links || []).map(posKey).sort()))
      errs.push(`${s.id} links`);
  }
  const edges = Array.isArray(fx.edges) ? fx.edges : [];
  if (directed !== edges.length * 2)
    errs.push(`directed links ${directed} != 2 x edges ${edges.length}`);
  for (const [a, b] of edges) {
    const sa = byId.get(a);
    const sb = byId.get(b);
    if (!sa || !sb || !sa.links.includes(b) || !sb.links.includes(a))
      errs.push(`edge ${a}-${b} not linked`);
  }
  const starts = spaceCells.filter((c) => c.start !== undefined).map((c) => c.start);
  if (new Set(starts).size !== starts.length) errs.push('duplicate start numbers');
  return errs;
}

/** Reads, validates and hashes one fixture file (throws on any violation). */
export function loadTopologyFixture(file: string): { fixture: TopologyFixture; sha256: string } {
  const bytes = fs.readFileSync(file);
  const fixture = JSON.parse(bytes.toString('utf8')) as TopologyFixture;
  const expectedMap = path.basename(file).replace(/\.topology\.json$/, '');
  const errs = validateTopologyFixture(fixture, expectedMap);
  if (errs.length)
    throw new Error(`${path.basename(file)}: invalid topology fixture: ${errs.join('; ')}`);
  return { fixture, sha256: fixtureSha256(bytes) };
}

/** Board row data for one topology fixture. */
/** Plain JSON copy (drops undefined keys exactly as the Json column would) */
const toJsonObject = (value: object): Prisma.InputJsonObject =>
  JSON.parse(JSON.stringify(value)) as Prisma.InputJsonObject;

export function topologyBoardRow(fixture: TopologyFixture, sha256: string, fixtureFile: string) {
  return {
    id: fixture.boardId,
    name: `${fixture.name} · original map`,
    nameEn: fixture.name,
    nameRu: fixture.name,
    set: fixture.set,
    width: fixture.lattice.width,
    height: fixture.lattice.height,
    cells: fixture.cells as unknown as Prisma.InputJsonArray,
    features: toJsonObject({
      topology: true,
      schema: fixture.schema,
      map: fixture.map,
      status: fixture.status,
      fixture: `backend/prisma/fixtures/boards/${path.basename(fixtureFile)}`,
      fixtureSha256: sha256,
      generator: fixture.generator,
      // ENV-U3: only the path and hash of the map image - never the image
      source: {
        image: fixture.source.image,
        sha256: fixture.source.sha256,
        size: fixture.source.size,
      },
      zones: fixture.zones,
      uuPerPx: fixture.uuPerPx,
      spaceRadiusPx: fixture.spaceRadiusPx,
      summary: fixture.summary,
    }),
    imageUrl: null as string | null,
    imageUrlDark: null as string | null,
  };
}

/**
 * Order-insensitive JSON equality for the read-back check: Board.cells is a
 * Postgres jsonb column, which does NOT keep object key order (keys come back
 * sorted by length, then bytes), so a plain JSON.stringify comparison would
 * report a faithful copy as different.
 */
export function sameJson(a: unknown, b: unknown): boolean {
  const canonical = (v: unknown): unknown => {
    if (Array.isArray(v)) return v.map(canonical);
    if (v && typeof v === 'object') {
      return Object.fromEntries(
        Object.keys(v)
          .sort()
          .map((k) => [k, canonical((v as Record<string, unknown>)[k])]),
      );
    }
    return v;
  };
  return JSON.stringify(canonical(a)) === JSON.stringify(canonical(b));
}

function argValue(args: string[], name: string): string | undefined {
  const i = args.indexOf(name);
  return i >= 0 ? args[i + 1] : undefined;
}

export function fixtureFiles(dir = TOPOLOGY_FIXTURE_DIR): string[] {
  return TOPOLOGY_MAPS.map((m) => path.join(dir, `${m}.topology.json`));
}

/**
 * The pinned default board (src/games/default-board.ts) must be one of the rows this seed writes,
 * under the same name - otherwise createGame without boardId would point at a row no seed creates.
 */
export function assertDefaultBoardSeeded(rows: ReadonlyArray<{ id: string; name: string }>): void {
  const row = rows.find((r) => r.id === DEFAULT_BOARD_ID);
  if (!row)
    throw new Error(
      `REFUSED: the default board ${DEFAULT_BOARD_ID} (${DEFAULT_BOARD_NAME}) is not one of the topology fixtures`,
    );
  if (row.name !== DEFAULT_BOARD_NAME)
    throw new Error(
      `REFUSED: the default board ${DEFAULT_BOARD_ID} is seeded as "${row.name}", expected "${DEFAULT_BOARD_NAME}"`,
    );
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  const mode = args.includes('--apply')
    ? 'apply'
    : args.includes('--verify')
      ? 'verify'
      : 'dry-run';
  const reportPath = argValue(args, '--report');
  // Credentials come from the ignored backend/.env of THIS checkout (never argv).
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  (require('dotenv') as typeof import('dotenv')).config({
    path: path.join(__dirname, '..', '.env'),
  });

  const guard: DbGuardOptions = { allowMainDevDb: args.includes('--allow-main-dev-db') };
  const loaded = fixtureFiles().map((file) => ({ file, ...loadTopologyFixture(file) }));
  const rows = loaded.map(({ file, fixture, sha256 }) => ({
    fixture,
    sha256,
    row: topologyBoardRow(fixture, sha256, file),
  }));
  assertDefaultBoardSeeded(rows.map(({ row }) => row));

  const report: Record<string, unknown> = {
    schema: 'unmatched.env-map-seed/1',
    mode,
    startedUtc: new Date().toISOString(),
    defaultBoard: { id: DEFAULT_BOARD_ID, name: DEFAULT_BOARD_NAME },
    boards: rows.map(({ fixture, sha256, row }) => ({
      map: fixture.map,
      id: row.id,
      name: row.name,
      lattice: `${row.width}x${row.height}`,
      cells: fixture.cells.length,
      spaces: fixture.spaces.length,
      edges: fixture.edges.length,
      starts: Object.fromEntries(
        fixture.spaces
          .filter((s) => s.start != null)
          .map((s): [string, string] => [String(s.start), s.id])
          .sort(),
      ),
      fixtureSha256: sha256,
      imageSha256: fixture.source.sha256,
    })),
  };

  if (mode === 'dry-run') {
    // OFFLINE: no client, no connection. The URL rule is still reported.
    const url = process.env.DATABASE_URL;
    if (!url) {
      report.database = { configured: false, rule: 'isolated S09 test DB only', connected: false };
      report.ok = true;
    } else {
      try {
        const db = assertIsolatedDatabase(url, guard);
        report.database = {
          host: db.hostname,
          port: db.port,
          name: db.pathname.replace(/^\//, ''),
          guard: 'ok',
          connected: false,
        };
        report.ok = true;
      } catch (error) {
        report.database = {
          guard: error instanceof Error ? error.message : String(error),
          connected: false,
        };
        report.ok = false;
      }
    }
  } else {
    const db = assertIsolatedDatabase(process.env.DATABASE_URL, guard);
    report.database = {
      host: db.hostname,
      port: db.port,
      name: db.pathname.replace(/^\//, ''),
      rule: guard.allowMainDevDb ? 'isolated S09 test DB or main dev DB (--allow-main-dev-db)' : 'isolated S09 test DB only',
    };
    // Lazy: specs import this module without touching the Prisma client.
    // eslint-disable-next-line @typescript-eslint/no-require-imports
    const { PrismaClient } = require('@prisma/client') as typeof import('@prisma/client');
    const prisma = new PrismaClient();
    try {
      const entries = report.boards as Array<Record<string, unknown>>;
      for (let i = 0; i < rows.length; i++) {
        const { row, sha256 } = rows[i];
        const entry = entries[i];
        const existing = await prisma.board.findUnique({ where: { id: row.id } });
        const clash = await prisma.board.findUnique({ where: { name: row.name } });
        if (clash && clash.id !== row.id)
          throw new Error(`REFUSED: Board name "${row.name}" belongs to another row ${clash.id}`);
        entry.existedBefore = Boolean(existing);
        if (mode === 'apply') {
          const { id, ...data } = row;
          await prisma.board.upsert({ where: { id }, create: row, update: data });
          entry.written = true;
        }
        const back = await prisma.board.findUnique({ where: { id: row.id } });
        const features = (back?.features ?? {}) as Record<string, unknown>;
        entry.verify = {
          present: Boolean(back),
          cellsIdentical: Boolean(back) && sameJson(back.cells, row.cells),
          featuresTopology: features.topology === true,
          featuresFixtureSha256: features.fixtureSha256 === sha256,
          sizeIdentical: back?.width === row.width && back?.height === row.height,
          imageUrlNull: back?.imageUrl == null,
        };
        entry.verified = Object.values(entry.verify as Record<string, boolean>).every(Boolean);
      }
      // НД-1: the default board of createGame is one of these rows - it must be there and verified
      report.defaultBoardVerified =
        entries.find((b) => b.id === DEFAULT_BOARD_ID)?.verified === true;
      report.ok =
        report.defaultBoardVerified === true && entries.every((b) => b.verified === true);
    } finally {
      await prisma.$disconnect();
    }
  }
  report.finishedUtc = new Date().toISOString();
  const text = JSON.stringify(report, null, 2) + '\n';
  if (reportPath) fs.writeFileSync(reportPath, text, 'utf8');
  process.stdout.write(text);
  if (!report.ok) process.exitCode = 1;
}

if (require.main === module) {
  main().catch((error) => {
    console.error('ENV_MAP_SEED_FAILED:', error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  });
}
