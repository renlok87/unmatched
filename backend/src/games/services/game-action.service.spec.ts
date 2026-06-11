import { Test, TestingModule } from '@nestjs/testing';
import { GameActionService } from './game-action.service';
import { PrismaService } from '../../database/prisma.service';
import { getQueueToken } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { GameActionType } from '../models/game-action.model';

describe('GameActionService', () => {
  let service: GameActionService;
  let queue: Queue;
  let prisma: PrismaService;

  const mockQueue = {
    add: jest.fn(),
    addBulk: jest.fn(),
  };

  const mockPrisma = {
    gameAction: {
      findMany: jest.fn(),
      count: jest.fn(),
      deleteMany: jest.fn(),
    },
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        GameActionService,
        {
          provide: getQueueToken('game-action'),
          useValue: mockQueue,
        },
        {
          provide: PrismaService,
          useValue: mockPrisma,
        },
      ],
    }).compile();

    service = module.get<GameActionService>(GameActionService);
    queue = module.get<Queue>(getQueueToken('game-action'));
    prisma = module.get<PrismaService>(PrismaService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('recordAction', () => {
    it('should add action to queue', async () => {
      const dto = {
        gameId: 'game1',
        sequenceNumber: 1,
        type: GameActionType.CARD_PLAYED,
        playerId: 'player1',
        metadata: { cardId: 'card1' },
      };

      mockQueue.add.mockResolvedValue('jobId');

      const actionId = await service.recordAction(dto);

      expect(mockQueue.add).toHaveBeenCalledWith(
        'record-action',
        expect.objectContaining({
          gameId: 'game1',
          sequenceNumber: 1,
          type: GameActionType.CARD_PLAYED,
          playerId: 'player1',
          metadata: { cardId: 'card1' },
        }),
        expect.objectContaining({
          attempts: 3,
        }),
      );
      expect(actionId).toBeDefined();
    });

    it('should handle queue errors', async () => {
      const dto = {
        gameId: 'game1',
        sequenceNumber: 1,
        type: GameActionType.CARD_PLAYED,
        playerId: 'player1',
        metadata: {},
      };

      mockQueue.add.mockRejectedValue(new Error('Queue error'));

      await expect(service.recordAction(dto)).rejects.toThrow('Queue error');
    });
  });

  describe('recordActionBatch', () => {
    it('should add multiple actions to queue', async () => {
      const actions = [
        {
          gameId: 'game1',
          sequenceNumber: 1,
          type: GameActionType.CARD_PLAYED,
          playerId: 'player1',
          metadata: { cardId: 'card1' },
        },
        {
          gameId: 'game1',
          sequenceNumber: 2,
          type: GameActionType.CARD_DISCARDED,
          playerId: 'player1',
          metadata: { cardId: 'card2' },
        },
      ];

      mockQueue.addBulk.mockResolvedValue([]);

      const actionIds = await service.recordActionBatch(actions);

      expect(mockQueue.addBulk).toHaveBeenCalled();
      expect(actionIds).toHaveLength(2);
    });
  });

  describe('getActionsByGame', () => {
    it('should return actions for game', async () => {
      const mockActions = [
        {
          id: 'action1',
          gameId: 'game1',
          sequenceNumber: 1,
          type: GameActionType.CARD_PLAYED,
          playerId: 'player1',
          timestamp: new Date(),
          payload: { cardId: 'card1' },
        },
      ];

      mockPrisma.gameAction.findMany.mockResolvedValue(mockActions);

      const actions = await service.getActionsByGame('game1');

      expect(mockPrisma.gameAction.findMany).toHaveBeenCalledWith({
        where: { gameId: 'game1' },
        orderBy: { sequenceNumber: 'asc' },
      });
      expect(actions).toHaveLength(1);
      expect(actions[0].id).toBe('action1');
    });

    it('should filter by sequence range', async () => {
      mockPrisma.gameAction.findMany.mockResolvedValue([]);

      await service.getActionsByGame('game1', 5, 10);

      expect(mockPrisma.gameAction.findMany).toHaveBeenCalledWith({
        where: {
          gameId: 'game1',
          sequenceNumber: { gte: 5, lte: 10 },
        },
        orderBy: { sequenceNumber: 'asc' },
      });
    });
  });

  describe('getActionsByPlayer', () => {
    it('should return actions for player', async () => {
      const mockActions = [
        {
          id: 'action1',
          gameId: 'game1',
          sequenceNumber: 1,
          type: GameActionType.CARD_PLAYED,
          playerId: 'player1',
          timestamp: new Date(),
          payload: {},
        },
      ];

      mockPrisma.gameAction.findMany.mockResolvedValue(mockActions);

      const actions = await service.getActionsByPlayer('player1');

      expect(mockPrisma.gameAction.findMany).toHaveBeenCalledWith({
        where: { playerId: 'player1' },
        orderBy: { timestamp: 'desc' },
        take: 100,
      });
    });
  });

  describe('getActionCount', () => {
    it('should return action count for game', async () => {
      mockPrisma.gameAction.count.mockResolvedValue(10);

      const count = await service.getActionCount('game1');

      expect(mockPrisma.gameAction.count).toHaveBeenCalledWith({
        where: { gameId: 'game1' },
      });
      expect(count).toBe(10);
    });
  });

  describe('cleanupOldActions', () => {
    it('should delete old actions', async () => {
      mockPrisma.gameAction.deleteMany.mockResolvedValue({ count: 5 });

      const count = await service.cleanupOldActions(30);

      expect(mockPrisma.gameAction.deleteMany).toHaveBeenCalledWith({
        where: {
          timestamp: expect.objectContaining({
            lt: expect.any(Date),
          }),
        },
      });
      expect(count).toBe(5);
    });
  });
});
