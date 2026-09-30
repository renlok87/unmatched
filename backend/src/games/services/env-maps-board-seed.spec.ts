/**
 * ENV-MAPS B2: prisma/seed-env-map-boards.ts - fixture validation (every rule
 * is broken once on purpose), the Board row it writes and the isolated-DB guard.
 * No database is touched here (the dry-run mode is offline as well).
 */
import { readFileSync } from 'node:fs';
import {
  assertIsolatedDatabase,
  fixtureFiles,
  fixtureSha256,
  loadTopologyFixture,
  sameJson,
  topologyBoardId,
  topologyBoardRow,
  validateTopologyFixture,
  type TopologyFixture,
} from '../../../prisma/seed-env-map-boards';

const [marmorealFile] = fixtureFiles();
const pristine = (): TopologyFixture => JSON.parse(readFileSync(marmorealFile, 'utf8'));
const cellOf = (fx: TopologyFixture, id: string) => fx.cells.find((c) => c.spaceId === id)!;

describe('seed-env-map-boards: fixtures', () => {
  it('loads both committed fixtures with their deterministic ids', () => {
    const loaded = fixtureFiles().map((f) => loadTopologyFixture(f).fixture);
    expect(loaded.map((f) => [f.map, f.boardId])).toEqual([
      ['marmoreal', topologyBoardId('marmoreal')],
      ['sarpedon', topologyBoardId('sarpedon')],
    ]);
    expect(topologyBoardId('marmoreal')).toBe('c121b47f8d6eb28daccb76d05');
  });

  it('hashes the committed LF bytes even if a checkout rewrote them to CRLF', () => {
    const lf = readFileSync(marmorealFile, 'utf8').replace(/\r\n/g, '\n');
    expect(fixtureSha256(lf.replace(/\n/g, '\r\n'))).toBe(fixtureSha256(Buffer.from(lf)));
  });

  it.each<[string, (fx: TopologyFixture) => void, RegExp]>([
    [
      'schema',
      (fx) => {
        fx.schema = 'x';
      },
      /schema/,
    ],
    [
      'foreign set',
      (fx) => {
        fx.set = 'x';
      },
      /set/,
    ],
    [
      'non-deterministic id',
      (fx) => {
        fx.boardId = 'c000000000000000000000000';
      },
      /deterministic/,
    ],
    [
      'image path',
      (fx) => {
        fx.source.image = 'https://example.invalid/m.webp';
      },
      /source.image/,
    ],
    [
      'missing lattice cell',
      (fx) => {
        fx.cells.pop();
      },
      /cells 41 != W\*H 42/,
    ],
    [
      'obstacle with zones',
      (fx) => {
        Object.assign(fx.cells.find((c) => c.isObstacle)!, { zones: ['red'] });
      },
      /obstacle .* carries zones/,
    ],
    [
      'asymmetric link',
      (fx) => {
        cellOf(fx, 'M26').links = [{ x: 5, y: 3 }];
      },
      /asymmetric link M25->M26/,
    ],
    [
      'link into a hole',
      (fx) => {
        cellOf(fx, 'M25').links!.push({ x: 3, y: 4 });
      },
      /M25 links to a non-space 3:4/,
    ],
    [
      'space without links',
      (fx) => {
        delete cellOf(fx, 'M01').links;
      },
      /space without links/,
    ],
    [
      'unknown zone',
      (fx) => {
        cellOf(fx, 'M16').zones = ['blue', 'lilac'];
      },
      /unknown zone lilac/,
    ],
    [
      'duplicate start',
      (fx) => {
        cellOf(fx, 'M01').start = 1;
      },
      /M01 start|duplicate start/,
    ],
    [
      'edge list drift',
      (fx) => {
        fx.edges.pop();
      },
      /2 x edges/,
    ],
  ])('refuses a fixture with a broken rule: %s', (_name, breakIt, message) => {
    const fx = pristine();
    expect(validateTopologyFixture(fx, 'marmoreal')).toEqual([]);
    breakIt(fx);
    const errs = validateTopologyFixture(fx, 'marmoreal');
    expect(errs.join('; ')).toMatch(message);
  });

  it('writes a Board row: lattice size, verbatim cells, no image, topology marked', () => {
    const { fixture, sha256 } = loadTopologyFixture(marmorealFile);
    const row = topologyBoardRow(fixture, sha256, marmorealFile);
    expect(row).toMatchObject({
      id: 'c121b47f8d6eb28daccb76d05',
      name: 'Marmoreal · original map',
      nameEn: 'Marmoreal',
      set: 'battle-of-legends-volume-one',
      width: 7,
      height: 6,
      imageUrl: null,
      imageUrlDark: null,
      features: {
        topology: true,
        map: 'marmoreal',
        fixture: 'backend/prisma/fixtures/boards/marmoreal.topology.json',
        fixtureSha256: sha256,
        source: { image: 'scraped-data/images/maps/marmoreal.webp', sha256: fixture.source.sha256 },
      },
    });
    expect(row.cells).toBe(fixture.cells);
    // ENV-U3: nothing but the path and hash of the map image travels
    expect(JSON.stringify(row.features)).not.toMatch(/data:image|https?:\/\//);
  });
});

describe('seed-env-map-boards: read-back check', () => {
  it('compares cells order-insensitively (jsonb reorders object keys)', () => {
    const { fixture } = loadTopologyFixture(marmorealFile);
    // jsonb key order: by length, then bytes (x, y, links, start, zones, layout, spaceId)
    const jsonb = (v: unknown): unknown =>
      Array.isArray(v)
        ? v.map(jsonb)
        : v && typeof v === 'object'
          ? Object.fromEntries(
              Object.keys(v)
                .sort((a, b) => a.length - b.length || (a < b ? -1 : 1))
                .map((k) => [k, jsonb((v as Record<string, unknown>)[k])]),
            )
          : v;
    const back = jsonb(JSON.parse(JSON.stringify(fixture.cells)));
    expect(JSON.stringify(back)).not.toBe(JSON.stringify(fixture.cells));
    expect(sameJson(back, fixture.cells)).toBe(true);
    const changed = JSON.parse(JSON.stringify(fixture.cells));
    changed[0].links.pop();
    expect(sameJson(changed, fixture.cells)).toBe(false);
  });
});

describe('seed-env-map-boards: isolated database only', () => {
  it.each([
    'postgresql://u:p@127.0.0.1:55434/unmatched',
    'postgresql://u:p@localhost:55434/unmatched',
  ])('accepts %s', (url) => {
    expect(assertIsolatedDatabase(url).port).toBe('55434');
  });

  it.each([
    'postgresql://u:p@127.0.0.1:5433/unmatched',
    'postgresql://u:p@db.example.com:55434/unmatched',
    'postgresql://u:p@127.0.0.1/unmatched',
  ])('refuses %s', (url) => {
    expect(() => assertIsolatedDatabase(url)).toThrow(/REFUSED/);
  });

  it('refuses a missing or malformed DATABASE_URL', () => {
    expect(() => assertIsolatedDatabase(undefined)).toThrow('DATABASE_URL is not set');
    expect(() => assertIsolatedDatabase('not a url')).toThrow('not a URL');
  });
});
