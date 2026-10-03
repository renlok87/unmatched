/**
 * Real boards only (docs/game-design/decisions/2026-10-04-real-boards-only.md):
 *  - НД-1: a game created without boardId plays on Marmoreal · original map; the pinned id is the id of the
 *    committed topology fixture; an unknown boardId is refused;
 *  - НД-2: a game whose board is missing or unusable does not start (no empty 20x20 grid any more).
 * No database is touched.
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { BadRequestException } from '@nestjs/common';
import { DEFAULT_BOARD_ID, DEFAULT_BOARD_NAME } from './default-board';
import { GameService } from './game.service';
import { GameInitializationService } from './services/game-initialization.service';
import {
  assertDefaultBoardSeeded,
  fixtureFiles,
  loadTopologyFixture,
  topologyBoardId,
  topologyBoardRow,
} from '../../prisma/seed-env-map-boards';

const seededRows = fixtureFiles().map((file) => {
  const { fixture, sha256 } = loadTopologyFixture(file);
  return topologyBoardRow(fixture, sha256, file);
});

describe('НД-1: the pinned default board', () => {
  it('is the boardId of backend/prisma/fixtures/boards/marmoreal.topology.json', () => {
    const fixture = JSON.parse(
      readFileSync(resolve(__dirname, '../../prisma/fixtures/boards/marmoreal.topology.json'), 'utf8'),
    );
    expect(DEFAULT_BOARD_ID).toBe(fixture.boardId);
    expect(DEFAULT_BOARD_ID).toBe(topologyBoardId('marmoreal'));
  });

  it('is written by seed-env-map-boards under its name', () => {
    expect(seededRows.find((r) => r.id === DEFAULT_BOARD_ID)?.name).toBe(DEFAULT_BOARD_NAME);
    expect(() => assertDefaultBoardSeeded(seededRows)).not.toThrow();
  });

  it('the seed refuses fixtures without the default board or under another name', () => {
    expect(() => assertDefaultBoardSeeded(seededRows.filter((r) => r.id !== DEFAULT_BOARD_ID))).toThrow(
      /REFUSED: the default board/,
    );
    const renamed = seededRows.map((r) => (r.id === DEFAULT_BOARD_ID ? { ...r, name: 'Marmoreal' } : r));
    expect(() => assertDefaultBoardSeeded(renamed)).toThrow(/expected "Marmoreal · original map"/);
  });
});

describe('НД-1: GameService.createGame board', () => {
  function serviceWith(boardIds: string[]) {
    const created: Array<Record<string, unknown>> = [];
    const prisma = {
      game: {
        count: jest.fn(async () => 0),
        findUnique: jest.fn(async () => null),
        create: jest.fn(async ({ data }: { data: Record<string, unknown> }) => {
          created.push(data);
          return { id: 'g1', ...data };
        }),
      },
      gamePlayer: { create: jest.fn(async () => ({})) },
      board: {
        findUnique: jest.fn(async ({ where }: { where: { id: string } }) =>
          boardIds.includes(where.id) ? { id: where.id } : null,
        ),
      },
      $transaction: jest.fn(async (run: (tx: unknown) => unknown) => run(prisma)),
    };
    const redis = { del: jest.fn(async () => 1) };
    const service = new GameService(
      prisma as never,
      redis as never,
      {} as never,
      { recordAction: jest.fn(async () => 'a1') } as never,
      { publishLobbyEvent: jest.fn() } as never,
    );
    jest.spyOn(service as never, 'generateGameCode').mockResolvedValue('ABCDEF' as never);
    jest.spyOn(service, 'getGame').mockImplementation(async (id: string) => ({ id }) as never);
    return { service, prisma, created };
  }

  it('without boardId the game is created on Marmoreal · original map', async () => {
    const { service, prisma, created } = serviceWith([DEFAULT_BOARD_ID, 'catalog']);
    await service.createGame({}, 'host');
    expect(prisma.board.findUnique).toHaveBeenCalledWith(
      expect.objectContaining({ where: { id: DEFAULT_BOARD_ID } }),
    );
    expect(created).toEqual([expect.objectContaining({ boardId: DEFAULT_BOARD_ID })]);
  });

  it('keeps an explicit existing boardId', async () => {
    const { service, created } = serviceWith([DEFAULT_BOARD_ID, 'catalog']);
    await service.createGame({ boardId: 'catalog' }, 'host');
    expect(created).toEqual([expect.objectContaining({ boardId: 'catalog' })]);
  });

  it('refuses an unknown boardId with a BadRequest and creates nothing', async () => {
    const { service, created } = serviceWith([DEFAULT_BOARD_ID]);
    const attempt = service.createGame({ boardId: 'no-such-board' }, 'host');
    await expect(attempt).rejects.toBeInstanceOf(BadRequestException);
    await expect(service.createGame({ boardId: 'no-such-board' }, 'host')).rejects.toThrow(
      'Доска no-such-board не найдена',
    );
    expect(created).toEqual([]);
  });

  it('refuses when the default board row is missing (no fallback board)', async () => {
    const { service, created } = serviceWith(['catalog']);
    await expect(service.createGame({}, 'host')).rejects.toThrow(/seed-env-map-boards/);
    expect(created).toEqual([]);
  });
});

describe('НД-2: a game without a usable board does not start', () => {
  const players = [
    { userId: 'a', heroId: 'h1', seatOrder: 0 },
    { userId: 'b', heroId: 'h2', seatOrder: 1 },
  ];

  async function start(boardId: string | null, board: unknown) {
    const saveState = jest.fn();
    const prisma = {
      game: { findUnique: jest.fn(async () => ({ boardId })) },
      board: { findUnique: jest.fn(async () => board) },
      gamePlayer: { findMany: jest.fn(async () => players) },
      hero: { findUnique: jest.fn() },
    };
    const service = new GameInitializationService(prisma as never, { saveState } as never);
    await expect(service.initializeGameState('g1')).rejects.toBeInstanceOf(BadRequestException);
    expect(saveState).not.toHaveBeenCalled();
    expect(prisma.hero.findUnique).not.toHaveBeenCalled();
    return service.initializeGameState('g1').catch((e: Error) => e.message);
  }

  it('board row missing (a retired board id)', async () => {
    await expect(start('cmuhgs4b2001mwik4f2b2xtf8', null)).resolves.toMatch(
      /cmuhgs4b2001mwik4f2b2xtf8.*не найдена/,
    );
  });

  it('game without boardId', async () => {
    await expect(start(null, null)).resolves.toMatch(/не найдена/);
  });

  it('empty cells', async () => {
    await expect(start('b1', { name: 'Empty', cells: [] })).resolves.toMatch(/cells пусты/);
  });

  it('invalid cell', async () => {
    await expect(start('b1', { name: 'Bad', cells: [{ x: -1, y: 0 }] })).resolves.toMatch(
      /невалидная клетка/,
    );
  });

  it('grid size out of range (pixel coordinates)', async () => {
    const cells = [
      { x: 0, y: 0 },
      { x: 399, y: 229 },
    ];
    await expect(start('b1', { name: 'Pixels', cells })).resolves.toMatch(/400×230 вне диапазона/);
  });
});
