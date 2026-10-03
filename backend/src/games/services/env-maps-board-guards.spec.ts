/**
 * ENV-MAPS review fixes: topology boards (original-map graph, cells with `links`)
 * never become the matchmaking default board, and the grid backfill never
 * overwrites them (not even with --force). No database is touched.
 */
import { readFileSync } from 'node:fs';
import { MatchmakingSchedulerService } from '../../matchmaking/services/matchmaking-scheduler.service';
import { isTopologyBoard } from '../../../prisma/backfill-board-cells';
import {
  fixtureFiles,
  topologyBoardRow,
  loadTopologyFixture,
} from '../../../prisma/seed-env-map-boards';

type BoardRow = { id: string; createdAt: Date; cells: unknown; features: unknown };

/** A web-catalog board (grid cells, no links), e.g. one of the imported real maps */
const catalog: BoardRow = {
  id: 'catalog',
  createdAt: new Date('2025-01-01T00:00:00Z'),
  cells: [{ x: 0, y: 0, zones: ['blue'] }],
  features: { mapKey: 'hells-kitchen' },
};
const topologyRows = fixtureFiles().map((file) => {
  const { fixture, sha256 } = loadTopologyFixture(file);
  const row = topologyBoardRow(fixture, sha256, file);
  return { id: row.id, cells: row.cells, features: row.features };
});
const marmoreal: BoardRow = { ...topologyRows[0], createdAt: new Date('2026-09-30T00:00:00Z') };

/**
 * Prisma double: ordered queries sort by createdAt; unordered ones return the
 * rows in "heap" order, which after a reseed (upsert -> new row version) can
 * put a topology board first.
 */
type FindArgs = { orderBy?: { createdAt?: 'asc' | 'desc' } };

function prismaWith(heapOrder: BoardRow[]) {
  const sorted = (args?: FindArgs) =>
    args?.orderBy?.createdAt === 'asc'
      ? [...heapOrder].sort((a, b) => a.createdAt.getTime() - b.createdAt.getTime())
      : heapOrder;
  return {
    board: {
      findFirst: jest.fn((args?: FindArgs) => Promise.resolve(sorted(args)[0] ?? null)),
      findMany: jest.fn((args?: FindArgs) => Promise.resolve(sorted(args))),
    },
  };
}

function defaultBoardId(prisma: ReturnType<typeof prismaWith>): Promise<string> {
  const none = {} as never;
  const svc = new MatchmakingSchedulerService(none, none, none, none, none, prisma as never, none);
  return (svc as unknown as { getDefaultBoardId(): Promise<string> }).getDefaultBoardId();
}

describe('ENV-MAPS guards: matchmaking board (web catalog only)', () => {
  it('uses the oldest catalog board, not the heap order', async () => {
    await expect(defaultBoardId(prismaWith([marmoreal, catalog]))).resolves.toBe('catalog');
  });

  it('never picks a topology board, even when it is the oldest one', async () => {
    const olderTopology = { ...marmoreal, createdAt: new Date('2024-01-01T00:00:00Z') };
    await expect(defaultBoardId(prismaWith([olderTopology, catalog]))).resolves.toBe('catalog');
  });

  it('throws when no catalog board exists (no placeholder board id)', async () => {
    await expect(defaultBoardId(prismaWith([marmoreal]))).rejects.toThrow('No catalog board');
    await expect(defaultBoardId(prismaWith([]))).rejects.toThrow('No catalog board');
  });
});

describe('ENV-MAPS guards: backfill-board-cells never overwrites a topology board', () => {
  it('recognises the rows seed-env-map-boards writes (cells with links, features.topology)', () => {
    expect(topologyRows).toHaveLength(2);
    for (const row of topologyRows) {
      expect(isTopologyBoard(row)).toBe(true);
      expect(isTopologyBoard({ cells: row.cells, features: null })).toBe(true);
      expect(isTopologyBoard({ cells: JSON.stringify(row.cells), features: null })).toBe(true);
      expect(isTopologyBoard({ cells: [], features: row.features })).toBe(true);
    }
  });

  it('leaves grid boards to the backfill', () => {
    expect(isTopologyBoard(catalog)).toBe(false);
    expect(isTopologyBoard({ cells: [], features: { mapKey: 'hells-kitchen' } })).toBe(false);
    expect(isTopologyBoard({ cells: null, features: undefined })).toBe(false);
  });

  it('checks topology before the --force overwrite in the backfill loop', () => {
    const src = readFileSync(require.resolve('../../../prisma/backfill-board-cells'), 'utf8');
    const loop = src.slice(src.indexOf('for (const board of boards)'));
    expect(loop.indexOf('isTopologyBoard(board)')).toBeGreaterThan(-1);
    expect(loop.indexOf('isTopologyBoard(board)')).toBeLessThan(loop.indexOf('!force'));
    expect(loop.indexOf('isTopologyBoard(board)')).toBeLessThan(
      loop.indexOf('prisma.board.update'),
    );
  });
});
