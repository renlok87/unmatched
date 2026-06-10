/**
 * Penalty Service Unit Tests
 *
 * ФАЗА 8F: Unit Tests
 */

import { Test, TestingModule } from '@nestjs/testing';
import { PenaltyService } from './penalty.service';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';
import { PENALTY_CONFIG } from '../models';

describe('PenaltyService', () => {
  let service: PenaltyService;
  let redisService: jest.Mocked<RedisService>;
  let prismaService: jest.Mocked<PrismaService>;

  const mockRedisService = {
    getJson: jest.fn(),
    setJsonex: jest.fn(),
    del: jest.fn(),
  };

  const mockPrismaService = {
    userStats: {
      findUnique: jest.fn(),
      update: jest.fn(),
    },
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PenaltyService,
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

    service = module.get<PenaltyService>(PenaltyService);
    redisService = module.get(RedisService);
    prismaService = module.get(PrismaService);

    jest.clearAllMocks();
  });

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('recordDecline', () => {
    it('should apply ELO penalty for first decline', async () => {
      mockRedisService.getJson.mockResolvedValue(null); // No previous record
      mockRedisService.setJsonex.mockResolvedValue('OK');
      mockPrismaService.userStats.findUnique.mockResolvedValue({
        currentElo: 1200,
      });
      mockPrismaService.userStats.update.mockResolvedValue({});

      const result = await service.recordDecline('user1');

      expect(result.tempBanned).toBe(false);
      expect(result.eloPenalty).toBe(PENALTY_CONFIG.ELO_PENALTY);
      expect(mockPrismaService.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: { currentElo: 1200 - PENALTY_CONFIG.ELO_PENALTY },
      });
    });

    it('should apply temp ban after threshold declines', async () => {
      const existingRecord = {
        userId: 'user1',
        declineCount: 2,
        lastDeclineAt: new Date(Date.now() - 1000), // Within window
      };

      mockRedisService.getJson.mockResolvedValue(existingRecord);
      mockRedisService.setJsonex.mockResolvedValue('OK');

      const result = await service.recordDecline('user1');

      expect(result.tempBanned).toBe(true);
      expect(result.eloPenalty).toBe(PENALTY_CONFIG.ELO_PENALTY);
    });

    it('should not apply ELO penalty below zero', async () => {
      mockRedisService.getJson.mockResolvedValue(null);
      mockRedisService.setJsonex.mockResolvedValue('OK');
      mockPrismaService.userStats.findUnique.mockResolvedValue({
        currentElo: 10, // Less than penalty
      });
      mockPrismaService.userStats.update.mockResolvedValue({});

      await service.recordDecline('user1');

      expect(mockPrismaService.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: { currentElo: 0 }, // Should not go below 0
      });
    });
  });

  describe('getPenaltyInfo', () => {
    it('should return canJoinQueue true for new user', async () => {
      mockRedisService.getJson.mockResolvedValue(null);

      const info = await service.getPenaltyInfo('user1');

      expect(info.canJoinQueue).toBe(true);
      expect(info.declineCount).toBe(0);
    });

    it('should return canJoinQueue false for temp banned user', async () => {
      const tempBan = {
        userId: 'user1',
        bannedAt: new Date(),
        expiresAt: new Date(Date.now() + 1000000), // Future
        reason: 'Too many declines',
      };

      mockRedisService.getJson.mockResolvedValueOnce(null).mockResolvedValueOnce(tempBan);

      const info = await service.getPenaltyInfo('user1');

      expect(info.canJoinQueue).toBe(false);
      expect(info.tempBanUntil).toBeDefined();
    });
  });

  describe('canJoinQueue', () => {
    it('should return true for user without ban', async () => {
      mockRedisService.getJson.mockResolvedValue(null);

      const canJoin = await service.canJoinQueue('user1');

      expect(canJoin).toBe(true);
    });
  });

  describe('resetDeclines', () => {
    it('should clear decline count', async () => {
      mockRedisService.del.mockResolvedValue(1);

      await service.resetDeclines('user1');

      expect(mockRedisService.del).toHaveBeenCalled();
    });
  });
});
