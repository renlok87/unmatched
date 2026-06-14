import { Test, TestingModule } from '@nestjs/testing';
import { AdminService } from './admin.service';
import { PrismaService } from '../database/prisma.service';
import { QueueManagerService } from '../matchmaking/services/queue-manager.service';
import { GameStatus } from '@prisma/client';

describe('AdminService.cleanupGames', () => {
  let service: AdminService;

  const mockPrisma = {
    game: {
      deleteMany: jest.fn(),
      updateMany: jest.fn(),
    },
  };

  const mockQueueManager = {};

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AdminService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: QueueManagerService, useValue: mockQueueManager },
      ],
    }).compile();

    service = module.get<AdminService>(AdminService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  it('deletes only FINISHED/ABORTED games older than the default 7 days and returns counts', async () => {
    mockPrisma.game.deleteMany.mockResolvedValue({ count: 4 });

    const before = Date.now();
    const result = await service.cleanupGames({});
    const after = Date.now();

    expect(mockPrisma.game.deleteMany).toHaveBeenCalledTimes(1);
    const deleteArg = mockPrisma.game.deleteMany.mock.calls[0][0];

    // Только завершённые/прерванные игры — никогда PENDING/LOBBY/IN_PROGRESS/PAUSED
    expect(deleteArg.where.status).toEqual({
      in: [GameStatus.FINISHED, GameStatus.ABORTED],
    });

    // Порог = now - 7 дней (с допуском на время выполнения теста)
    const cutoff: Date = deleteArg.where.updatedAt.lt;
    expect(cutoff).toBeInstanceOf(Date);
    const expectedMin = before - 7 * 24 * 60 * 60 * 1000;
    const expectedMax = after - 7 * 24 * 60 * 60 * 1000;
    expect(cutoff.getTime()).toBeGreaterThanOrEqual(expectedMin);
    expect(cutoff.getTime()).toBeLessThanOrEqual(expectedMax);

    // По умолчанию застрявшие игры не трогаем
    expect(mockPrisma.game.updateMany).not.toHaveBeenCalled();

    expect(result).toEqual({ deleted: 4, aborted: 0 });
  });

  it('honours a custom finishedOlderThanDays threshold', async () => {
    mockPrisma.game.deleteMany.mockResolvedValue({ count: 1 });

    const before = Date.now();
    await service.cleanupGames({ finishedOlderThanDays: 30 });
    const after = Date.now();

    const cutoff: Date = mockPrisma.game.deleteMany.mock.calls[0][0].where.updatedAt.lt;
    expect(cutoff.getTime()).toBeGreaterThanOrEqual(before - 30 * 24 * 60 * 60 * 1000);
    expect(cutoff.getTime()).toBeLessThanOrEqual(after - 30 * 24 * 60 * 60 * 1000);
  });

  it('aborts stuck IN_PROGRESS/PAUSED games when abortStuckInProgress is set, never touching PENDING/LOBBY', async () => {
    mockPrisma.game.deleteMany.mockResolvedValue({ count: 0 });
    mockPrisma.game.updateMany.mockResolvedValue({ count: 2 });

    const result = await service.cleanupGames({ abortStuckInProgress: true });

    expect(mockPrisma.game.updateMany).toHaveBeenCalledTimes(1);
    const updateArg = mockPrisma.game.updateMany.mock.calls[0][0];

    // Прерываем только активные зависшие игры
    expect(updateArg.where.status).toEqual({
      in: [GameStatus.IN_PROGRESS, GameStatus.PAUSED],
    });
    expect(updateArg.data.status).toBe(GameStatus.ABORTED);
    expect(updateArg.data.endedAt).toBeInstanceOf(Date);

    // Никогда не трогаем PENDING/LOBBY
    const statuses: GameStatus[] = updateArg.where.status.in;
    expect(statuses).not.toContain(GameStatus.PENDING);
    expect(statuses).not.toContain(GameStatus.LOBBY);

    expect(result).toEqual({ deleted: 0, aborted: 2 });
  });

  it('respects a custom stuckMinutes threshold for aborting stuck games', async () => {
    mockPrisma.game.deleteMany.mockResolvedValue({ count: 0 });
    mockPrisma.game.updateMany.mockResolvedValue({ count: 0 });

    const before = Date.now();
    await service.cleanupGames({ abortStuckInProgress: true, stuckMinutes: 120 });
    const after = Date.now();

    const cutoff: Date = mockPrisma.game.updateMany.mock.calls[0][0].where.updatedAt.lt;
    expect(cutoff.getTime()).toBeGreaterThanOrEqual(before - 120 * 60 * 1000);
    expect(cutoff.getTime()).toBeLessThanOrEqual(after - 120 * 60 * 1000);
  });
});
