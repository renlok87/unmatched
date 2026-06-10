/**
 * Match Confirmation Service Unit Tests
 *
 * ФАЗА 8F: Unit Tests
 */

import { Test, TestingModule } from '@nestjs/testing';
import { MatchConfirmationService } from './match-confirmation.service';
import { RedisService } from '../../redis/redis.service';
import { PrismaService } from '../../database/prisma.service';
import { ConfirmationStatus } from '../models';
import { GameStatus } from '@prisma/client';
import { BullModule } from '@nestjs/bullmq';
import { Queue } from 'bullmq';

describe('MatchConfirmationService', () => {
  let service: MatchConfirmationService;
  let redisService: jest.Mocked<RedisService>;
  let prismaService: jest.Mocked<PrismaService>;
  let confirmationQueue: jest.Mocked<Queue>;

  const mockRedisService = {
    setJsonex: jest.fn(),
    getJson: jest.fn(),
    del: jest.fn(),
  };

  const mockPrismaService = {
    game: {
      update: jest.fn(),
    },
  };

  const mockConfirmationQueue = {
    add: jest.fn(),
    getJob: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      imports: [
        BullModule.registerQueue({
          name: 'match-confirmation',
        }),
      ],
      providers: [
        MatchConfirmationService,
        {
          provide: RedisService,
          useValue: mockRedisService,
        },
        {
          provide: PrismaService,
          useValue: mockPrismaService,
        },
      ],
    })
      .overrideProvider(getQueueToken('match-confirmation'))
      .useValue(mockConfirmationQueue)
      .compile();

    service = module.get<MatchConfirmationService>(MatchConfirmationService);
    redisService = module.get(RedisService);
    prismaService = module.get(PrismaService);
    confirmationQueue = module.get(getQueueToken('match-confirmation'));

    jest.clearAllMocks();
  });

  // Helper function для получения токена очереди
  function getQueueToken(name: string): string {
    return `BullQueue_${name}`;
  }

  it('should be defined', () => {
    expect(service).toBeDefined();
  });

  describe('createConfirmation', () => {
    it('should create confirmation with TTL', async () => {
      mockRedisService.setJsonex.mockResolvedValue('OK');
      mockConfirmationQueue.add.mockResolvedValue({} as any);

      await service.createConfirmation('game1', 'player1', 'player2');

      expect(mockRedisService.setJsonex).toHaveBeenCalled();
      expect(mockConfirmationQueue.add).toHaveBeenCalled();
    });
  });

  describe('acceptMatch', () => {
    it('should accept match for player', async () => {
      const confirmation = {
        gameId: 'game1',
        player1Id: 'player1',
        player2Id: 'player2',
        player1Status: ConfirmationStatus.PENDING,
        player2Status: ConfirmationStatus.PENDING,
        expiresAt: new Date(Date.now() + 30000),
        createdAt: new Date(),
      };

      mockRedisService.getJson.mockResolvedValue(confirmation);
      mockRedisService.setJsonex.mockResolvedValue('OK');
      mockPrismaService.game.update.mockResolvedValue({});

      const result = await service.acceptMatch('game1', 'player1');

      expect(result.success).toBe(true);
      expect(result.bothAccepted).toBe(false); // Only player1 accepted
    });

    it('should start game when both players accept', async () => {
      const confirmation = {
        gameId: 'game1',
        player1Id: 'player1',
        player2Id: 'player2',
        player1Status: ConfirmationStatus.ACCEPTED,
        player2Status: ConfirmationStatus.PENDING,
        expiresAt: new Date(Date.now() + 30000),
        createdAt: new Date(),
      };

      mockRedisService.getJson.mockResolvedValue(confirmation);
      mockRedisService.setJsonex.mockResolvedValue('OK');
      mockRedisService.del.mockResolvedValue(1);
      mockPrismaService.game.update.mockResolvedValue({});

      const result = await service.acceptMatch('game1', 'player2');

      expect(result.bothAccepted).toBe(true);
      expect(mockPrismaService.game.update).toHaveBeenCalledWith({
        where: { id: 'game1' },
        data: {
          status: GameStatus.LOBBY,
          startedAt: expect.any(Date),
        },
      });
    });

    it('should return error if confirmation expired', async () => {
      mockRedisService.getJson.mockResolvedValue(null);

      const result = await service.acceptMatch('game1', 'player1');

      expect(result.success).toBe(false);
      expect(result.status).toBe(ConfirmationStatus.TIMEOUT);
    });
  });

  describe('declineMatch', () => {
    it('should decline match and cancel game', async () => {
      const confirmation = {
        gameId: 'game1',
        player1Id: 'player1',
        player2Id: 'player2',
        player1Status: ConfirmationStatus.PENDING,
        player2Status: ConfirmationStatus.PENDING,
        expiresAt: new Date(Date.now() + 30000),
        createdAt: new Date(),
      };

      mockRedisService.getJson.mockResolvedValue(confirmation);
      mockRedisService.del.mockResolvedValue(1);
      mockPrismaService.game.update.mockResolvedValue({});

      const result = await service.declineMatch('game1', 'player1');

      expect(result.success).toBe(true);
      expect(result.status).toBe(ConfirmationStatus.DECLINED);
      expect(mockPrismaService.game.update).toHaveBeenCalledWith({
        where: { id: 'game1' },
        data: { status: GameStatus.ABORTED },
      });
    });
  });
});
