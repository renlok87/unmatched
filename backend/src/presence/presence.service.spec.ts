import { Test, TestingModule } from '@nestjs/testing';
import { PresenceService } from './presence.service';
import { RedisService } from '../redis/redis.service';
import { PresenceStatus } from './models/presence.model';

describe('PresenceService', () => {
  let service: PresenceService;
  let redisService: RedisService;

  const mockRedisService = {
    setJsonex: jest.fn(),
    zadd: jest.fn(),
    publish: jest.fn(),
    getJson: jest.fn(),
    zrange: jest.fn(),
    zcard: jest.fn(),
    del: jest.fn(),
    zrem: jest.fn(),
    zrangebyscore: jest.fn(),
    subscribe: jest.fn(),
    unsubscribe: jest.fn(),
    zscore: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PresenceService,
        {
          provide: RedisService,
          useValue: mockRedisService,
        },
      ],
    }).compile();

    service = module.get<PresenceService>(PresenceService);
    redisService = module.get<RedisService>(RedisService);

    jest.clearAllMocks();
  });

  describe('updatePresence', () => {
    it('should update user presence in Redis', async () => {
      const userId = 'user123';
      const status = PresenceStatus.ONLINE;
      const currentGameId = 'game456';

      mockRedisService.setJsonex.mockResolvedValue('OK');
      mockRedisService.zadd.mockResolvedValue(1);
      mockRedisService.publish.mockResolvedValue(1);

      const result = await service.updatePresence(userId, status, currentGameId);

      expect(result.userId).toBe(userId);
      expect(result.status).toBe(status);
      expect(result.currentGameId).toBe(currentGameId);
      expect(mockRedisService.setJsonex).toHaveBeenCalledWith(
        `presence:${userId}`,
        300,
        expect.any(Object),
      );
      expect(mockRedisService.zadd).toHaveBeenCalledWith(
        'presence:online',
        expect.any(Number),
        userId,
      );
      expect(mockRedisService.publish).toHaveBeenCalled();
    });

    it('should handle Redis errors gracefully', async () => {
      const userId = 'user123';
      const status = PresenceStatus.ONLINE;

      mockRedisService.setJsonex.mockRejectedValue(new Error('Redis error'));

      const result = await service.updatePresence(userId, status);

      expect(result.userId).toBe(userId);
      expect(result.status).toBe(status);
    });
  });

  describe('getPresence', () => {
    it('should retrieve user presence from Redis', async () => {
      const userId = 'user123';
      const mockPresence = {
        userId,
        status: PresenceStatus.ONLINE,
        lastSeenAt: Date.now(),
      };

      mockRedisService.getJson.mockResolvedValue(mockPresence);

      const result = await service.getPresence(userId);

      expect(result).toEqual(mockPresence);
      expect(mockRedisService.getJson).toHaveBeenCalledWith(`presence:${userId}`);
    });

    it('should return null if presence not found', async () => {
      mockRedisService.getJson.mockResolvedValue(null);

      const result = await service.getPresence('user123');

      expect(result).toBeNull();
    });
  });

  describe('getOnlineUserIds', () => {
    it('should retrieve online user IDs', async () => {
      const mockUsers = ['user1', 'user2', 'user3'];
      mockRedisService.zrange.mockResolvedValue(mockUsers);

      const result = await service.getOnlineUserIds();

      expect(result).toEqual(mockUsers);
      expect(mockRedisService.zrange).toHaveBeenCalledWith('presence:online', 0, -1);
    });

    it('should handle errors and return empty array', async () => {
      mockRedisService.zrange.mockRejectedValue(new Error('Redis error'));

      const result = await service.getOnlineUserIds();

      expect(result).toEqual([]);
    });
  });

  describe('getOnlineCount', () => {
    it('should return online user count', async () => {
      mockRedisService.zcard.mockResolvedValue(5);

      const result = await service.getOnlineCount();

      expect(result).toBe(5);
    });

    it('should handle errors and return 0', async () => {
      mockRedisService.zcard.mockRejectedValue(new Error('Redis error'));

      const result = await service.getOnlineCount();

      expect(result).toBe(0);
    });
  });

  describe('removePresence', () => {
    it('should remove user presence', async () => {
      const userId = 'user123';

      mockRedisService.del.mockResolvedValue(1);
      mockRedisService.zrem.mockResolvedValue(1);

      await service.removePresence(userId);

      expect(mockRedisService.del).toHaveBeenCalledWith(`presence:${userId}`);
      expect(mockRedisService.zrem).toHaveBeenCalledWith('presence:online', userId);
    });
  });

  describe('isUserOnline', () => {
    it('should return true if user is online', async () => {
      mockRedisService.zscore.mockResolvedValue(123456);

      const result = await service.isUserOnline('user123');

      expect(result).toBe(true);
    });

    it('should return false if user is offline', async () => {
      mockRedisService.zscore.mockResolvedValue(null);

      const result = await service.isUserOnline('user123');

      expect(result).toBe(false);
    });
  });

  describe('cleanupExpiredPresences', () => {
    it('should clean up expired presences', async () => {
      const expiredUsers = ['user1', 'user2'];
      mockRedisService.zrangebyscore.mockResolvedValue(expiredUsers);
      mockRedisService.zrem.mockResolvedValue(1);

      const result = await service.cleanupExpiredPresences();

      expect(result).toBe(2);
      expect(mockRedisService.zrangebyscore).toHaveBeenCalledWith(
        'presence:online',
        0,
        expect.any(Number),
      );
    });

    it('should handle no expired presences', async () => {
      mockRedisService.zrangebyscore.mockResolvedValue([]);

      const result = await service.cleanupExpiredPresences();

      expect(result).toBe(0);
    });
  });
});
