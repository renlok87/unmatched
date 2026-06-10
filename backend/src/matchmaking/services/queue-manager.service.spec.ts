/**
 * Queue Manager Service Unit Tests
 *
 * ФАЗА 8F: Unit Tests
 */

import { Test, TestingModule } from '@nestjs/testing';
import { QueueManagerService } from './queue-manager.service';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';

describe('QueueManagerService', () => {
  let service: QueueManagerService;
  let redisService: jest.Mocked<RedisService>;
  let prismaService: jest.Mocked<PrismaService>;

  // Вспомогательная функция для создания mock данных hgetall
  const mockHgetallData = (userId: string, rating: number, mode: string, joinedAt: number) => ({
    userId,
    rating: String(rating),
    mode,
    heroPref: '',
    joinedAt: String(joinedAt),
  });

  const mockRedisService = {
    zadd: jest.fn(),
    zrem: jest.fn(),
    zremMany: jest.fn(),
    zrange: jest.fn(),
    zrangebyscore: jest.fn(),
    zcard: jest.fn(),
    expire: jest.fn(),
    del: jest.fn(),
    getJson: jest.fn(),
    hset: jest.fn(),
    hgetall: jest.fn(),
  };

  const mockPrismaService = {
    matchmakingQueueEntry: {
      upsert: jest.fn(),
      delete: jest.fn(),
      findMany: jest.fn(),
    },
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        QueueManagerService,
        {
          provide: RedisService,
          useValue: mockRedisService,
        },
        {
          provide: PrismaService,
          useValue: mockPrismaService,
        },
      ],
    }).compile();

    service = module.get<QueueManagerService>(QueueManagerService);
    redisService = module.get(RedisService);
    prismaService = module.get(PrismaService);

    jest.clearAllMocks();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('addToQueue', () => {
    it('should add user to queue with O(log N) complexity', async () => {
      const now = Date.now();
      mockRedisService.hset.mockResolvedValue(1);
      mockRedisService.expire.mockResolvedValue(1);
      mockRedisService.zadd.mockResolvedValue(1); // 1 = новый элемент
      mockRedisService.zrange.mockResolvedValue(['user1', '1200']); // Для getUserPosition
      mockRedisService.hgetall.mockResolvedValue(mockHgetallData('user1', 1200, 'ONE_V_ONE', now));
      mockPrismaService.matchmakingQueueEntry.upsert.mockResolvedValue({});

      const result = await service.addToQueue('user1', 1200, 'ONE_V_ONE');

      expect(result.added).toBe(true);
      expect(result.position).toBeDefined();
      expect(mockRedisService.hset).toHaveBeenCalled();
      expect(mockRedisService.zadd).toHaveBeenCalled();
      expect(mockPrismaService.matchmakingQueueEntry.upsert).toHaveBeenCalled();
    });

    it('should update existing entry instead of creating duplicate', async () => {
      const now = Date.now();
      mockRedisService.hset.mockResolvedValue(0);
      mockRedisService.expire.mockResolvedValue(1);
      mockRedisService.zadd.mockResolvedValue(0); // 0 = элемент обновлен
      mockRedisService.zrange.mockResolvedValue(['user1', '1250']);
      mockRedisService.hgetall.mockResolvedValue(mockHgetallData('user1', 1250, 'ONE_V_ONE', now));
      mockPrismaService.matchmakingQueueEntry.upsert.mockResolvedValue({});

      const result = await service.addToQueue('user1', 1250, 'ONE_V_ONE');

      expect(result.added).toBe(false); // Updated, not added
    });
  });

  describe('removeFromQueue', () => {
    it('should remove user from queue', async () => {
      mockRedisService.zrem.mockResolvedValue(1); // 1 = элемент был и удален
      mockRedisService.del.mockResolvedValue(1);
      mockPrismaService.matchmakingQueueEntry.delete.mockResolvedValue({});

      const result = await service.removeFromQueue('user1', 'ONE_V_ONE');

      expect(result).toBe(true);
      expect(mockRedisService.zrem).toHaveBeenCalledWith('mm:queue:ONE_V_ONE', 'user1');
      expect(mockRedisService.del).toHaveBeenCalledWith('mm:queue:data:user1');
    });

    it('should return false if user not in queue', async () => {
      mockRedisService.zrem.mockResolvedValue(0); // 0 = элемент не найден
      mockRedisService.del.mockResolvedValue(0);
      mockPrismaService.matchmakingQueueEntry.delete.mockResolvedValue({});

      const result = await service.removeFromQueue('nonexistent', 'ONE_V_ONE');

      expect(result).toBe(false);
      expect(mockRedisService.zrem).toHaveBeenCalledWith('mm:queue:ONE_V_ONE', 'nonexistent');
    });
  });

  describe('getQueueSize', () => {
    it('should return queue size with O(1) complexity', async () => {
      mockRedisService.zcard.mockResolvedValue(42);

      const size = await service.getQueueSize('ONE_V_ONE');

      expect(size).toBe(42);
      expect(mockRedisService.zcard).toHaveBeenCalledWith('mm:queue:ONE_V_ONE');
    });
  });

  describe('findMatch', () => {
    it('should find match with expanding window', async () => {
      const now = Date.now();
      const user1JoinedAt = now - 40000; // 40 sec wait -> +/-200 ELO
      const user2JoinedAt = now - 40000;
      const user1Data = mockHgetallData('user1', 1200, 'ONE_V_ONE', user1JoinedAt);
      const user2Data = mockHgetallData('user2', 1350, 'ONE_V_ONE', user2JoinedAt);

      // Мок для getAllEntries (вызывается внутри getEntryByUserId)
      mockRedisService.zrange.mockResolvedValue(['user1', '1200', 'user2', '1350']);
      // Используем mockReturnValue для повторных вызовов
      mockRedisService.hgetall.mockImplementation((key) => {
        if (key.includes('user1')) return Promise.resolve(user1Data);
        if (key.includes('user2')) return Promise.resolve(user2Data);
        return Promise.resolve({});
      });
      // Мок для getCandidatesInRange
      mockRedisService.zrangebyscore.mockResolvedValue(['user2', '1350']);

      const match = await service.findMatch('user1', 'ONE_V_ONE');

      expect(match).toBeDefined();
      expect(match?.userId).toBe('user2');
      expect(match?.rating).toBe(1350);
    });

    it('should return null if no match found', async () => {
      const now = Date.now();
      const user1Data = mockHgetallData('user1', 1200, 'ONE_V_ONE', now);

      // Только один пользователь в очереди
      mockRedisService.zrange.mockResolvedValue(['user1', '1200']);
      mockRedisService.hgetall.mockImplementation((key) => {
        if (key.includes('user1')) return Promise.resolve(user1Data);
        return Promise.resolve({});
      });
      // Пустой диапазон кандидатов
      mockRedisService.zrangebyscore.mockResolvedValue([]);

      const match = await service.findMatch('user1', 'ONE_V_ONE');

      expect(match).toBeNull();
    });

    it('should return null if user not in queue', async () => {
      // Пустая очередь
      mockRedisService.zrange.mockResolvedValue([]);
      mockRedisService.hgetall.mockResolvedValue({});
      mockRedisService.zrangebyscore.mockResolvedValue([]);

      const match = await service.findMatch('user1', 'ONE_V_ONE');

      expect(match).toBeNull();
    });

    it('should use expanding window for longer wait times', async () => {
      const now = Date.now();
      const user1JoinedAt = now - 90000; // 90 sec wait -> +/-400 ELO
      const user2JoinedAt = now - 90000;
      const user1Data = mockHgetallData('user1', 1200, 'ONE_V_ONE', user1JoinedAt);
      const user2Data = mockHgetallData('user2', 1600, 'ONE_V_ONE', user2JoinedAt);

      // user1=1200, user2=1600, разница=400, должно сработать
      mockRedisService.zrange.mockResolvedValue(['user1', '1200', 'user2', '1600']);
      mockRedisService.hgetall.mockImplementation((key) => {
        if (key.includes('user1')) return Promise.resolve(user1Data);
        if (key.includes('user2')) return Promise.resolve(user2Data);
        return Promise.resolve({});
      });
      mockRedisService.zrangebyscore.mockResolvedValue(['user2', '1600']);

      const match = await service.findMatch('user1', 'ONE_V_ONE');

      expect(match).toBeDefined();
      expect(match?.userId).toBe('user2');
    });
  });

  describe('getUserPosition', () => {
    it('should return user position in queue', async () => {
      const now = Date.now();
      // Очередь с 3 пользователями, user1 на 2 месте
      mockRedisService.zrange.mockResolvedValue([
        'user3',
        '1100',
        'user1',
        '1200',
        'user2',
        '1300',
      ]);
      mockRedisService.hgetall
        .mockResolvedValueOnce(mockHgetallData('user3', 1100, 'ONE_V_ONE', now))
        .mockResolvedValueOnce(mockHgetallData('user1', 1200, 'ONE_V_ONE', now))
        .mockResolvedValueOnce(mockHgetallData('user2', 1300, 'ONE_V_ONE', now));

      const position = await service.getUserPosition('user1', 'ONE_V_ONE');

      expect(position).toBe(2); // Второе место
    });

    it('should return 0 if user not in queue', async () => {
      const now = Date.now();
      mockRedisService.zrange.mockResolvedValue(['user2', '1300']);
      mockRedisService.hgetall.mockResolvedValue(mockHgetallData('user2', 1300, 'ONE_V_ONE', now));

      const position = await service.getUserPosition('user1', 'ONE_V_ONE');

      expect(position).toBe(0);
    });
  });

  describe('removeFromAllQueues', () => {
    it('should remove user from all queues', async () => {
      // Для ONE_V_ONE - пользователь есть
      mockRedisService.zrem
        .mockResolvedValueOnce(1)
        .mockResolvedValueOnce(0)
        .mockResolvedValueOnce(0)
        .mockResolvedValueOnce(0);
      mockRedisService.del.mockResolvedValue(1);
      mockPrismaService.matchmakingQueueEntry.delete.mockResolvedValue({});

      const modes = await service.removeFromAllQueues('user1');

      expect(modes).toContain('ONE_V_ONE');
    });

    it('should return empty array if user not in any queue', async () => {
      mockRedisService.zrem.mockResolvedValue(0);
      mockRedisService.del.mockResolvedValue(0);
      mockPrismaService.matchmakingQueueEntry.delete.mockResolvedValue({});

      const modes = await service.removeFromAllQueues('nonexistent');

      expect(modes).toEqual([]);
    });
  });

  describe('isInQueue', () => {
    it('should return true if user is in queue', async () => {
      const now = Date.now();
      mockRedisService.zrange.mockResolvedValue(['user1', '1200']);
      mockRedisService.hgetall.mockResolvedValue(mockHgetallData('user1', 1200, 'ONE_V_ONE', now));

      const isInQueue = await service.isInQueue('user1', 'ONE_V_ONE');

      expect(isInQueue).toBe(true);
    });

    it('should return false if user is not in queue', async () => {
      mockRedisService.zrange.mockResolvedValue([]);

      const isInQueue = await service.isInQueue('user1', 'ONE_V_ONE');

      expect(isInQueue).toBe(false);
    });
  });

  describe('clearQueue', () => {
    it('should clear the queue', async () => {
      mockRedisService.del.mockResolvedValue(1);

      await service.clearQueue('ONE_V_ONE');

      expect(mockRedisService.del).toHaveBeenCalledWith('mm:queue:ONE_V_ONE');
    });
  });

  describe('getAllQueueStats', () => {
    it('should return stats for all queues', async () => {
      mockRedisService.zcard
        .mockResolvedValueOnce(5) // ONE_V_ONE
        .mockResolvedValueOnce(3) // TWO_V_TWO
        .mockResolvedValueOnce(10) // FREE_FOR_ALL
        .mockResolvedValueOnce(2); // VS_AI

      const stats = await service.getAllQueueStats();

      expect(stats).toEqual({
        ONE_V_ONE: 5,
        TWO_V_TWO: 3,
        FREE_FOR_ALL: 10,
        VS_AI: 2,
      });
    });
  });
});
