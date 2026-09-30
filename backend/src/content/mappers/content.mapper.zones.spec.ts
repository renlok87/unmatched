/**
 * ENV-MAPS B2: zone normalisation of the content API.
 *
 * Decision (2026-09-30): the ContentMapper alias violet -> purple is removed;
 * violet is a zone of its own (Zone.VIOLET). Before the change every map of
 * scraped-data/api/maps.json that uses violet was checked (table below, the
 * zone keys of all 29 maps; the file itself is gitignored - set
 * UNMATCHED_MAPS_JSON=<path to maps.json> to re-check the table against it):
 *   - 16 maps use violet; on 3 of them (azuchi-castle, globe-theatre, marmoreal)
 *     purple is a DIFFERENT zone of the same map and the alias merged the two;
 *   - on the other 13 only the label changes (PURPLE -> VIOLET), the partition
 *     of the map into zones is unchanged; no map gets a new merge.
 * Also: the public content catalog hides boards with an original-map topology.
 */
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import type { Board } from '@prisma/client';
import { ContentMapper, boardCellsHaveTopology } from './content.mapper';
import { ContentDbService } from '../content-db.service';
import { Zone } from '../interfaces';

/** Zone keys per map, verbatim from scraped-data/api/maps.json (sha256 476eb21b...cd6e) */
const MAP_ZONE_KEYS: Record<string, string[]> = {
  'azuchi-castle': ['green', 'yellow', 'beige', 'brown', 'orange', 'violet', 'red', 'purple'],
  'baskerville-manor': ['blue', 'brown', 'yellow', 'dark-blue', 'green', 'violet', 'gray'],
  'fayrlund-forest': [
    'blue',
    'brown-dark',
    'brown-light',
    'brown-medium',
    'gray',
    'green-dark',
    'green-light',
    'orange',
  ],
  'globe-theatre': [
    'blue',
    'brown',
    'brown-light',
    'green',
    'green-dark',
    'green-light',
    'orange',
    'violet',
    'red',
    'purple',
  ],
  'hanging-gardens': [
    'blue',
    'brown',
    'gray',
    'green',
    'green-light',
    'roze',
    'yellow',
    'yellow-light',
  ],
  helicarrier: ['blue', 'brown', 'brown-light', 'green', 'orange', 'violet', 'yellow'],
  'hells-kitchen': ['blue', 'blue-light', 'brown', 'gray', 'green', 'violet', 'yellow'],
  heorot: ['blue', 'blue-dark', 'gray', 'gray-light', 'orange', 'red', 'yellow'],
  'kaer-morhen': [
    'blue-dark',
    'blue-light',
    'blue-medium',
    'brown-dark',
    'brown-light',
    'gray',
    'green',
    'violet',
  ],
  'king-solomons-mine': ['blue', 'brown', 'gray', 'green', 'red', 'yellow', 'gold'],
  marmoreal: ['gray', 'green', 'blue', 'violet', 'purple', 'red', 'brown', 'yellow'],
  'mcminnville-or': [
    'blue',
    'brown',
    'gray',
    'gray-dark',
    'green',
    'green-light',
    'orange',
    'pink',
    'violet',
    'yellow',
  ],
  naglfar: ['blue', 'brown', 'green', 'pink', 'violet', 'white', 'yellow'],
  'navy-pier': ['blue', 'green', 'green-light', 'orange', 'purple', 'yellow'],
  'point-pleasant': ['blue', 'blue-light', 'brown', 'burgundy', 'gray', 'green', 'pink'],
  'raptor-paddock': ['beige', 'blue', 'brown', 'gray', 'green', 'yellow'],
  'sanctum-sanctorum': ['blue', 'brown', 'green', 'orange', 'red', 'violet', 'yellow'],
  'santas-workshop': ['green-light', 'green-dark', 'blue', 'yellow', 'beige', 'red'],
  sarpedon: ['green', 'yellow', 'brown', 'red', 'purple', 'blue'],
  'sherwood-forest': ['gray', 'light-gray', 'green', 'brown', 'light-green', 'orange', 'yellow'],
  soho: ['blue', 'brown', 'dark-blue', 'gray', 'green', 'orange', 'yellow'],
  'streets-of-novigrad': [
    'blue',
    'brown',
    'gray',
    'green-dark',
    'green-light',
    'orange',
    'pink',
    'yellow',
  ],
  'sunnydale-high': ['gray', 'green', 'red', 'pink', 'violet', 'yellow'],
  't-rex-paddock': ['blue', 'gray', 'green', 'blue-green', 'purple', 'yellow'],
  'the-bronze': ['green', 'green-dark', 'red', 'pink', 'violet', 'violet-dark'],
  'the-raft': ['blue', 'blue-dark', 'blue-light', 'brown', 'yellow', 'gray', 'green', 'violet'],
  venice: ['orange', 'green', 'yellow', 'gray', 'red', 'violet', 'blue', 'blue-dark'],
  yukon: ['brown-ligt', 'brown', 'gray', 'orange', 'red', 'violet', 'yellow'],
  'yukon-1900': ['brown-ligt', 'brown', 'gray', 'orange', 'red', 'violet', 'yellow'],
};

const mapper = new ContentMapper();
const board = (cells: unknown, extra: Partial<Board> = {}): Board =>
  ({
    id: 'b',
    name: 'B',
    nameEn: 'B',
    nameRu: 'B',
    set: 's',
    width: 5,
    height: 5,
    cells,
    features: null,
    imageUrl: null,
    imageUrlDark: null,
    createdAt: new Date(0),
    updatedAt: new Date(0),
    ...extra,
  }) as unknown as Board;

/** Content API zone of one raw key (null = dropped as unknown) */
const zoneOf = (raw: string): Zone | null =>
  mapper.prismaBoardToBoardDefinition(board([{ x: 0, y: 0, zones: [raw] }])).spaces[0].zones[0] ??
  null;
/** Behaviour BEFORE the change: the only difference was violet -> PURPLE */
const legacyZoneOf = (raw: string): Zone | null =>
  zoneOf(raw) === Zone.VIOLET ? Zone.PURPLE : zoneOf(raw);

describe('ContentMapper zones: violet is its own zone', () => {
  it('maps violet (and its shades) to VIOLET and keeps purple PURPLE', () => {
    expect(zoneOf('violet')).toBe(Zone.VIOLET);
    expect(zoneOf('violet-dark')).toBe(Zone.VIOLET);
    expect(zoneOf('purple')).toBe(Zone.PURPLE);
    expect(zoneOf('grey')).toBe(Zone.GRAY);
    expect(zoneOf('biege')).toBe(Zone.BEIGE);
    const cell = mapper.prismaBoardToBoardDefinition(
      board([{ x: 0, y: 0, zones: ['violet', 'purple'] }]),
    );
    expect(cell.spaces[0].zones).toEqual([Zone.VIOLET, Zone.PURPLE]);
  });

  it('every map of maps.json: no new merges; violet != purple where a map has both', () => {
    const violetMaps: string[] = [];
    const split: string[] = [];
    for (const [map, keys] of Object.entries(MAP_ZONE_KEYS)) {
      if (keys.some((k) => k.split('-').includes('violet'))) violetMaps.push(map);
      for (const a of keys) {
        // unknown keys are dropped exactly as before
        expect([map, a, zoneOf(a) === null]).toEqual([map, a, legacyZoneOf(a) === null]);
        for (const b of keys) {
          if (a >= b || zoneOf(a) === null) continue;
          // new equality implies old equality: the new partition is never coarser
          if (zoneOf(a) === zoneOf(b))
            expect([map, a, b, legacyZoneOf(a)]).toEqual([map, a, b, legacyZoneOf(b)]);
          if (zoneOf(a) !== zoneOf(b) && legacyZoneOf(a) === legacyZoneOf(b))
            split.push(`${map}:${a}|${b}`);
        }
      }
    }
    expect(violetMaps).toHaveLength(16);
    expect(split.sort()).toEqual([
      'azuchi-castle:purple|violet',
      'globe-theatre:purple|violet',
      'marmoreal:purple|violet',
    ]);
  });

  const live =
    process.env.UNMATCHED_MAPS_JSON ?? resolve(__dirname, '../../../../scraped-data/api/maps.json');
  (existsSync(live) ? it : it.skip)('the table equals the zone keys of the live maps.json', () => {
    // SvelteKit devalue payload, parsed like prisma/backfill-board-cells.ts
    const data = JSON.parse(readFileSync(live, 'utf8')).nodes[2].data as any[];
    const at = (i: unknown) => (typeof i === 'number' && i >= 0 ? data[i] : null);
    const table: Record<string, string[]> = {};
    for (const index of data[1]) {
      const m = data[index];
      table[at(m.key)] = (at(m.zones) as number[]).map((zi) => at(at(zi).key));
    }
    expect(table).toEqual(MAP_ZONE_KEYS);
  });
});

describe('ENV-MAPS: public content catalog hides original-map topology boards', () => {
  const grid = board([{ x: 0, y: 0, zones: ['red'] }], { id: 'grid', name: 'Cobble City' });
  const topo = board(
    [
      { x: 0, y: 0, zones: ['violet'], links: [{ x: 1, y: 0 }] },
      { x: 1, y: 0, zones: ['violet'], links: [{ x: 0, y: 0 }] },
    ],
    { id: 'topo', name: 'Marmoreal · original map' },
  );

  it('boardCellsHaveTopology: any cell with a links array, tolerant to string JSON', () => {
    expect(boardCellsHaveTopology(topo.cells)).toBe(true);
    expect(boardCellsHaveTopology(JSON.stringify(topo.cells))).toBe(true);
    expect(boardCellsHaveTopology(JSON.stringify(JSON.stringify(topo.cells)))).toBe(true);
    expect(boardCellsHaveTopology([{ x: 0, y: 0, links: [] }])).toBe(true);
    expect(boardCellsHaveTopology(grid.cells)).toBe(false);
    expect(boardCellsHaveTopology([])).toBe(false);
    expect(boardCellsHaveTopology(null)).toBe(false);
    expect(boardCellsHaveTopology('not json')).toBe(false);
  });

  function service(rows: Board[]) {
    const prisma = {
      board: {
        findMany: async () => rows,
        findUnique: async ({ where }: any) => rows.find((b) => b.id === where.id) ?? null,
        findFirst: async ({ where }: any) =>
          rows.find((b) => b.name.toLowerCase() === where.OR[0].name.equals.toLowerCase()) ?? null,
        count: async () => rows.length,
      },
      hero: { count: async () => 0, findMany: async () => [] },
    };
    const redis = { get: async () => null, setex: async () => 'OK' };
    return new ContentDbService(prisma as any, redis as any, mapper);
  }

  it('boards / boardsPaginated / board(id) / summary do not offer them', async () => {
    const content = service([grid, topo]);
    expect((await content.getAllBoards()).map((b) => b.name)).toEqual(['Cobble City']);
    const page = await content.getBoardsPaginated(1, 10);
    expect(page.items.map((b) => b.name)).toEqual(['Cobble City']);
    expect(page.pagination.total).toBe(1);
    await expect(content.getBoardById('topo')).rejects.toThrow('Board not found');
    await expect(content.getBoardBySlug('Marmoreal · original map')).rejects.toThrow(
      'Board not found',
    );
    expect((await content.getBoardById('grid')).name).toBe('Cobble City');
    expect(((await content.getContentSummary()) as any).boardsCount).toBe(1);
  });
});
