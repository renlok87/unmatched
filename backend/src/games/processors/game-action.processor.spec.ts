import { Test, TestingModule } from '@nestjs/testing';
import { GameActionProcessor } from './game-action.processor';
import { PrismaService } from '../../database/prisma.service';
import { Job } from 'bullmq';
import { GameActionType } from '../models/game-action.model';

describe('GameActionProcessor', () => {
  let processor: GameActionProcessor;
  let prisma: PrismaService;

  const mockPrisma = {
    gameAction: {
      upsert: jest.fn(),
    },
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameActionProcessor,
        {
          provide: PrismaService,
          useValue: mockPrisma,
        },
      ],
    }).compile();

    processor = module.get<GameActionProcessor>(GameActionProcessor);
    prisma = module.get<PrismaService>(PrismaService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('process', () => {
    it('should create game action', async () => {
      const jobData = {
        id: 'action1',
        gameId: 'game1',
        sequenceNumber: 1,
        type: GameActionType.CARD_PLAYED,
        playerId: 'player1',
        timestamp: new Date(),
        metadata: { cardId: 'card1' },
      };

      const job = {
        data: jobData,
      } as Job;

      mockPrisma.gameAction.upsert.mockResolvedValue({ id: 'action1' });

      await processor.process(job);

      expect(mockPrisma.gameAction.upsert).toHaveBeenCalledWith({
        where: { id: 'action1' },
        update: {},
        create: {
          id: 'action1',
          gameId: 'game1',
          sequenceNumber: 1,
          type: GameActionType.CARD_PLAYED,
          playerId: 'player1',
          timestamp: jobData.timestamp,
          payload: { cardId: 'card1' },
        },
      });
    });

    it('should handle upsert errors', async () => {
      const jobData = {
        id: 'action1',
        gameId: 'game1',
        sequenceNumber: 1,
        type: GameActionType.CARD_PLAYED,
        playerId: 'player1',
        timestamp: new Date(),
        metadata: {},
      };

      const job = {
        data: jobData,
      } as Job;

      mockPrisma.gameAction.upsert.mockRejectedValue(new Error('Database error'));

      await expect(processor.process(job)).rejects.toThrow('Database error');
    });
  });
});
