import { Test, TestingModule } from '@nestjs/testing';
import { StatsAggregatorService } from './stats-aggregator.service';
import { PrismaService } from '../../database/prisma.service';
import { LeaderboardService } from './leaderboard.service';
import { AuditService } from '../../audit/audit.service';

describe('StatsAggregatorService', () => {
  let service: StatsAggregatorService;
  let prisma: PrismaService;
  let leaderboard: LeaderboardService;
  let audit: AuditService;

  const mockPrisma = {
    userStats: {
      findUnique: jest.fn(),
      upsert: jest.fn(),
      update: jest.fn(),
      updateMany: jest.fn(),
    },
    $transaction: jest.fn(),
  };

  const mockLeaderboard = {
    updatePlayerStats: jest.fn(),
    getPlayerRank: jest.fn(),
    getTopPlayers: jest.fn(),
    resetWeeklyLeaderboard: jest.fn(),
  };

  const mockAudit = {
    logEvent: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        StatsAggregatorService,
        {
          provide: PrismaService,
          useValue: mockPrisma,
        },
        {
          provide: LeaderboardService,
          useValue: mockLeaderboard,
        },
        {
          provide: AuditService,
          useValue: mockAudit,
        },
      ],
    }).compile();

    service = module.get<StatsAggregatorService>(StatsAggregatorService);
    prisma = module.get<PrismaService>(PrismaService);
    leaderboard = module.get<LeaderboardService>(LeaderboardService);
    audit = module.get<AuditService>(AuditService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('updateEloRatings', () => {
    it('should update ELO ratings for winner and loser', async () => {
      const winnerStats = {
        userId: 'winner1',
        currentElo: 1200,
        peakElo: 1200,
        gamesWon: 5,
        gamesPlayed: 10,
      };

      const loserStats = {
        userId: 'loser1',
        currentElo: 1200,
        peakElo: 1200,
        gamesLost: 5,
        gamesPlayed: 10,
      };

      mockPrisma.userStats.findUnique
        .mockResolvedValueOnce(winnerStats)
        .mockResolvedValueOnce(loserStats);

      mockPrisma.$transaction.mockResolvedValue([{}, {}]);
      mockLeaderboard.updatePlayerStats.mockResolvedValue(undefined);

      await service.updateEloRatings('game1', 'winner1', 'loser1');

      expect(mockPrisma.$transaction).toHaveBeenCalled();
      expect(mockLeaderboard.updatePlayerStats).toHaveBeenCalledTimes(2);
    });

    it('should create stats if they do not exist', async () => {
      mockPrisma.userStats.findUnique.mockResolvedValueOnce(null).mockResolvedValueOnce(null);

      mockPrisma.$transaction.mockResolvedValue([{}, {}]);
      mockLeaderboard.updatePlayerStats.mockResolvedValue(undefined);

      await service.updateEloRatings('game1', 'winner1', 'loser1');

      expect(mockPrisma.$transaction).toHaveBeenCalled();
    });
  });

  describe('applyQueuePenalty', () => {
    it('should apply ELO penalty', async () => {
      const stats = {
        userId: 'user1',
        currentElo: 1200,
        peakElo: 1200,
      };

      mockPrisma.userStats.findUnique.mockResolvedValue(stats);
      mockPrisma.userStats.upsert.mockResolvedValue({});
      mockLeaderboard.updatePlayerStats.mockResolvedValue(undefined);
      mockAudit.logEvent.mockResolvedValue('eventId');

      await service.applyQueuePenalty('user1', -25);

      expect(mockPrisma.userStats.upsert).toHaveBeenCalledWith(
        expect.objectContaining({
          where: { userId: 'user1' },
          update: expect.objectContaining({
            currentElo: 1175,
          }),
        }),
      );
      expect(mockAudit.logEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          type: expect.any(String),
          userId: 'user1',
          metadata: expect.objectContaining({
            penalty: -25,
          }),
        }),
      );
    });

    it('should not allow negative ELO', async () => {
      const stats = {
        userId: 'user1',
        currentElo: 10,
        peakElo: 1200,
      };

      mockPrisma.userStats.findUnique.mockResolvedValue(stats);
      mockPrisma.userStats.upsert.mockResolvedValue({});
      mockLeaderboard.updatePlayerStats.mockResolvedValue(undefined);
      mockAudit.logEvent.mockResolvedValue('eventId');

      await service.applyQueuePenalty('user1', -100);

      expect(mockPrisma.userStats.upsert).toHaveBeenCalledWith(
        expect.objectContaining({
          update: expect.objectContaining({
            currentElo: 0,
          }),
        }),
      );
    });
  });

  describe('updateHeroStats', () => {
    it('should update hero stats', async () => {
      const stats = {
        userId: 'user1',
        heroStats: {},
      };

      mockPrisma.userStats.findUnique.mockResolvedValue(stats);
      mockPrisma.userStats.update.mockResolvedValue({});

      await service.updateHeroStats('user1', 'hero1', true, 300);

      expect(mockPrisma.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: expect.objectContaining({
          totalPlayTime: { increment: 300 },
        }),
      });
    });

    it('should skip if stats do not exist', async () => {
      mockPrisma.userStats.findUnique.mockResolvedValue(null);

      await service.updateHeroStats('user1', 'hero1', true, 300);

      expect(mockPrisma.userStats.update).not.toHaveBeenCalled();
    });
  });

  describe('getPlayerStats', () => {
    it('should return player stats with rank', async () => {
      const stats = {
        userId: 'user1',
        currentElo: 1250,
        peakElo: 1300,
        gamesPlayed: 20,
        gamesWon: 10,
        gamesLost: 10,
        winRate: 0.5,
        totalPlayTime: 6000,
        lastPlayedAt: new Date(),
        heroStats: {},
      };

      mockPrisma.userStats.findUnique.mockResolvedValue(stats);
      mockLeaderboard.getPlayerRank.mockResolvedValue({
        rank: 5,
        userId: 'user1',
        elo: 1250,
      });

      const playerStats = await service.getPlayerStats('user1');

      expect(playerStats).toMatchObject({
        userId: 'user1',
        currentElo: 1250,
        peakElo: 1300,
        rank: 5,
      });
    });

    it('should return default stats if not found', async () => {
      mockPrisma.userStats.findUnique.mockResolvedValue(null);
      mockLeaderboard.getPlayerRank.mockRejectedValue(new Error('Not found'));

      const playerStats = await service.getPlayerStats('user1');

      expect(playerStats).toMatchObject({
        userId: 'user1',
        currentElo: 1200,
        gamesPlayed: 0,
        rank: null,
      });
    });
  });

  describe('getTopPlayers', () => {
    it('should return top players with additional stats', async () => {
      const leaderboardEntries = [
        {
          rank: 1,
          userId: 'user1',
          username: 'Player1',
          elo: 1500,
          gamesWon: 50,
          gamesPlayed: 100,
          winRate: 50,
        },
      ];

      const stats = {
        peakElo: 1600,
        totalPlayTime: 12000,
      };

      mockLeaderboard.getTopPlayers.mockResolvedValue(leaderboardEntries);
      mockPrisma.userStats.findUnique.mockResolvedValue(stats);

      const topPlayers = await service.getTopPlayers(10);

      expect(topPlayers).toHaveLength(1);
      expect(topPlayers[0]).toMatchObject({
        rank: 1,
        peakElo: 1600,
        totalPlayTime: 12000,
      });
    });
  });

  describe('resetWeeklyStats', () => {
    it('should reset weekly leaderboard', async () => {
      mockLeaderboard.resetWeeklyLeaderboard.mockResolvedValue(5);

      const count = await service.resetWeeklyStats();

      expect(mockLeaderboard.resetWeeklyLeaderboard).toHaveBeenCalled();
      expect(count).toBe(0);
    });
  });

  describe('calculateNewElo', () => {
    it('should increase ELO for winner', () => {
      const service = new StatsAggregatorService(
        mockPrisma as any,
        mockLeaderboard as any,
        mockAudit as any,
      );

      const newElo = (service as any).calculateNewElo(1200, 1200, true);

      expect(newElo).toBeGreaterThan(1200);
    });

    it('should decrease ELO for loser', () => {
      const service = new StatsAggregatorService(
        mockPrisma as any,
        mockLeaderboard as any,
        mockAudit as any,
      );

      const newElo = (service as any).calculateNewElo(1200, 1200, false);

      expect(newElo).toBeLessThan(1200);
    });

    it('should give more points for beating higher ranked player', () => {
      const service = new StatsAggregatorService(
        mockPrisma as any,
        mockLeaderboard as any,
        mockAudit as any,
      );

      const newElo1 = (service as any).calculateNewElo(1200, 1400, true);
      const newElo2 = (service as any).calculateNewElo(1200, 1000, true);

      expect(newElo1).toBeGreaterThan(newElo2);
    });
  });
});
