import { Test, TestingModule } from '@nestjs/testing';
import { UserStatsService } from './user-stats.service';
import { PrismaService } from '../database/prisma.service';
import { RatingService } from './rating.service';
import { NotFoundException } from '@nestjs/common';
import { TimeFrame } from './dto';

describe('UserStatsService', () => {
  let service: UserStatsService;
  let prisma: PrismaService;
  let ratingService: RatingService;

  const mockStats = {
    userId: 'user1',
    gamesPlayed: 50,
    gamesWon: 30,
    gamesLost: 20,
    winRate: 60,
    currentElo: 1400,
    peakElo: 1500,
    lastPlayedAt: new Date(),
    totalPlayTime: 30000,
    heroStats: {
      hero1: {
        gamesPlayed: 20,
        gamesWon: 12,
        gamesLost: 8,
        totalPlayTime: 12000,
        elo: 1350,
        peakElo: 1400,
        winRate: 60,
      },
      hero2: {
        gamesPlayed: 30,
        gamesWon: 18,
        gamesLost: 12,
        totalPlayTime: 18000,
        elo: 1450,
        peakElo: 1500,
        winRate: 60,
      },
    },
  };

  const mockUser = {
    id: 'user1',
    username: 'testuser',
    avatar: null,
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        UserStatsService,
        {
          provide: PrismaService,
          useValue: {
            userStats: {
              findUnique: jest.fn(),
              create: jest.fn(),
              update: jest.fn(),
              findMany: jest.fn(),
            },
            user: {
              findMany: jest.fn(),
            },
            leaderboardEntry: {
              findMany: jest.fn(),
              deleteMany: jest.fn(),
              createMany: jest.fn(),
            },
            $transaction: jest.fn(),
            $executeRawUnsafe: jest.fn(),
          },
        },
        {
          provide: RatingService,
          useValue: {
            calculateNewRatings: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<UserStatsService>(UserStatsService);
    prisma = module.get(PrismaService);
    ratingService = module.get(RatingService);
  });

  describe('getStats', () => {
    it('should return existing user stats', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);

      const stats = await service.getStats('user1');

      expect(stats.userId).toBe('user1');
      expect(stats.gamesPlayed).toBe(50);
      expect(stats.gamesWon).toBe(30);
      expect(stats.currentElo).toBe(1400);
      expect(stats.favoriteHero).toBeDefined();
      expect(prisma.userStats.findUnique).toHaveBeenCalledWith({
        where: { userId: 'user1' },
      });
    });

    it('should create new stats if not found', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(null);
      jest.spyOn(prisma.userStats, 'create').mockResolvedValue({
        userId: 'newuser',
        gamesPlayed: 0,
        gamesWon: 0,
        gamesLost: 0,
        winRate: 0,
        currentElo: 1200,
        peakElo: 1200,
        lastPlayedAt: null,
        totalPlayTime: 0,
        heroStats: null,
      } as any);

      const stats = await service.getStats('newuser');

      expect(stats.userId).toBe('newuser');
      expect(stats.gamesPlayed).toBe(0);
      expect(stats.currentElo).toBe(1200);
      expect(prisma.userStats.create).toHaveBeenCalledWith({
        data: { userId: 'newuser' },
      });
    });

    it('should identify favorite hero correctly', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);

      const stats = await service.getStats('user1');

      expect(stats.favoriteHero).toEqual({
        id: 'hero2',
        name: 'hero2',
        nameEn: 'hero2',
        nameRu: 'hero2',
      });
    });

    it('should return null favorite hero when no hero stats', async () => {
      const statsWithoutHeroes = { ...mockStats, heroStats: null };
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(statsWithoutHeroes as any);

      const stats = await service.getStats('user1');

      expect(stats.favoriteHero).toBeNull();
    });
  });

  describe('updateStatsAfterGame', () => {
    it('should update both players stats correctly', async () => {
      const winnerStats = { ...mockStats, userId: 'winner' };
      const loserStats = { ...mockStats, userId: 'loser', currentElo: 1300 };

      jest
        .spyOn(prisma.userStats, 'findUnique')
        .mockResolvedValueOnce(winnerStats as any)
        .mockResolvedValueOnce(loserStats as any);

      const newRatings = { winner: 1410, loser: 1290 };
      jest.spyOn(ratingService, 'calculateNewRatings').mockReturnValue(newRatings);

      const transactionMock = jest.fn().mockImplementation((updates) => {
        return Promise.all(updates.map((update: any) => update()));
      });
      jest.spyOn(prisma.userStats, 'update').mockResolvedValue({} as any);
      jest
        .spyOn(prisma, '$transaction')
        .mockImplementation((operations: any) => Promise.all(operations as any[]));

      await service.updateStatsAfterGame('game1', 'winner', 'loser');

      expect(ratingService.calculateNewRatings).toHaveBeenCalledWith(1400, 1300);
      expect(prisma.$transaction).toHaveBeenCalled();
      expect(prisma.userStats.update).toHaveBeenCalledTimes(2);
    });

    it('should calculate correct win rate for winner', async () => {
      const winnerStats = { ...mockStats, userId: 'winner', gamesPlayed: 50, gamesWon: 30 };
      const loserStats = { ...mockStats, userId: 'loser' };

      jest
        .spyOn(prisma.userStats, 'findUnique')
        .mockResolvedValueOnce(winnerStats as any)
        .mockResolvedValueOnce(loserStats as any);

      const newRatings = { winner: 1410, loser: 1290 };
      jest.spyOn(ratingService, 'calculateNewRatings').mockReturnValue(newRatings);

      jest.spyOn(prisma.userStats, 'update').mockResolvedValue({} as any);
      jest
        .spyOn(prisma, '$transaction')
        .mockImplementation((operations: any) => Promise.all(operations as any[]));

      await service.updateStatsAfterGame('game1', 'winner', 'loser');

      const winnerUpdate = (prisma.userStats.update as jest.Mock).mock.calls[0][0];
      expect(winnerUpdate.data.winRate).toBeCloseTo(60.78, 1);
    });

    it('should calculate correct win rate for loser', async () => {
      const winnerStats = { ...mockStats, userId: 'winner' };
      const loserStats = { ...mockStats, userId: 'loser', gamesPlayed: 50, gamesWon: 30 };

      jest
        .spyOn(prisma.userStats, 'findUnique')
        .mockResolvedValueOnce(winnerStats as any)
        .mockResolvedValueOnce(loserStats as any);

      const newRatings = { winner: 1410, loser: 1290 };
      jest.spyOn(ratingService, 'calculateNewRatings').mockReturnValue(newRatings);

      jest.spyOn(prisma.userStats, 'update').mockResolvedValue({} as any);
      jest
        .spyOn(prisma, '$transaction')
        .mockImplementation((operations: any) => Promise.all(operations as any[]));

      await service.updateStatsAfterGame('game1', 'winner', 'loser');

      const loserUpdate = (prisma.userStats.update as jest.Mock).mock.calls[1][0];
      expect(loserUpdate.data.winRate).toBeCloseTo(58.82, 1);
    });

    it('should update peakElo when new rating is higher', async () => {
      const winnerStats = { ...mockStats, userId: 'winner', currentElo: 1400, peakElo: 1450 };
      const loserStats = { ...mockStats, userId: 'loser' };

      jest
        .spyOn(prisma.userStats, 'findUnique')
        .mockResolvedValueOnce(winnerStats as any)
        .mockResolvedValueOnce(loserStats as any);

      const newRatings = { winner: 1500, loser: 1300 };
      jest.spyOn(ratingService, 'calculateNewRatings').mockReturnValue(newRatings);

      jest.spyOn(prisma.userStats, 'update').mockResolvedValue({} as any);
      jest
        .spyOn(prisma, '$transaction')
        .mockImplementation((operations: any) => Promise.all(operations as any[]));

      await service.updateStatsAfterGame('game1', 'winner', 'loser');

      const winnerUpdate = (prisma.userStats.update as jest.Mock).mock.calls[0][0];
      expect(winnerUpdate.data.peakElo).toBe(1500);
    });

    it('should throw NotFoundException when stats not found', async () => {
      jest
        .spyOn(prisma.userStats, 'findUnique')
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce(mockStats as any);

      await expect(service.updateStatsAfterGame('game1', 'winner', 'loser')).rejects.toThrow(
        NotFoundException,
      );
    });

    it('should update lastPlayedAt for both players', async () => {
      const winnerStats = { ...mockStats, userId: 'winner' };
      const loserStats = { ...mockStats, userId: 'loser' };

      jest
        .spyOn(prisma.userStats, 'findUnique')
        .mockResolvedValueOnce(winnerStats as any)
        .mockResolvedValueOnce(loserStats as any);

      const newRatings = { winner: 1410, loser: 1290 };
      jest.spyOn(ratingService, 'calculateNewRatings').mockReturnValue(newRatings);

      jest.spyOn(prisma.userStats, 'update').mockResolvedValue({} as any);
      jest
        .spyOn(prisma, '$transaction')
        .mockImplementation((operations: any) => Promise.all(operations as any[]));

      await service.updateStatsAfterGame('game1', 'winner', 'loser');

      expect(
        (prisma.userStats.update as jest.Mock).mock.calls[0][0].data.lastPlayedAt,
      ).toBeInstanceOf(Date);
      expect(
        (prisma.userStats.update as jest.Mock).mock.calls[1][0].data.lastPlayedAt,
      ).toBeInstanceOf(Date);
    });
  });

  describe('updateHeroStats', () => {
    it('should update hero stats for win', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma, '$executeRawUnsafe').mockResolvedValue(1 as any);

      await service.updateHeroStats('user1', 'hero1', true, 300);

      expect(prisma.$executeRawUnsafe).toHaveBeenCalledWith(
        expect.stringContaining('UPDATE "UserStats"'),
        'hero1',
        1,
        0,
        300,
        'user1',
      );
    });

    it('should update hero stats for loss', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma, '$executeRawUnsafe').mockResolvedValue(1 as any);

      await service.updateHeroStats('user1', 'hero1', false, 300);

      expect(prisma.$executeRawUnsafe).toHaveBeenCalledWith(
        expect.stringContaining('UPDATE "UserStats"'),
        'hero1',
        0,
        1,
        300,
        'user1',
      );
    });

    it('should throw NotFoundException when user stats not found', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(null);

      await expect(service.updateHeroStats('user1', 'hero1', true, 300)).rejects.toThrow(
        NotFoundException,
      );
    });

    it('should update total play time', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma, '$executeRawUnsafe').mockResolvedValue(1 as any);

      await service.updateHeroStats('user1', 'hero1', true, 300);

      expect(prisma.$executeRawUnsafe).toHaveBeenCalledWith(
        expect.stringContaining('"totalPlayTime" = "totalPlayTime" + $4'),
        'hero1',
        1,
        0,
        300,
        'user1',
      );
    });
  });

  describe('getLeaderboard', () => {
    it('should return leaderboard with default options', async () => {
      const mockEntries = [
        {
          userId: 'user1',
          heroId: null,
          timeFrame: TimeFrame.ALL,
          rank: 1,
          elo: 1500,
          gamesWon: 50,
          gamesPlayed: 80,
        },
        {
          userId: 'user2',
          heroId: null,
          timeFrame: TimeFrame.ALL,
          rank: 2,
          elo: 1450,
          gamesWon: 45,
          gamesPlayed: 75,
        },
      ];

      jest.spyOn(prisma.leaderboardEntry, 'findMany').mockResolvedValue(mockEntries as any);
      jest
        .spyOn(prisma.user, 'findMany')
        .mockResolvedValue([mockUser, { id: 'user2', username: 'user2', avatar: null }] as any);

      const leaderboard = await service.getLeaderboard({ limit: 50, timeFrame: TimeFrame.ALL });

      expect(leaderboard).toHaveLength(2);
      expect(leaderboard[0].rank).toBe(1);
      expect(leaderboard[0].elo).toBe(1500);
      expect(leaderboard[0].user.username).toBe('testuser');
    });

    it('should generate leaderboard when no cached entries', async () => {
      jest.spyOn(prisma.leaderboardEntry, 'findMany').mockResolvedValue([]);
      jest.spyOn(prisma.userStats, 'findMany').mockResolvedValue([mockStats] as any);
      jest.spyOn(prisma.user, 'findMany').mockResolvedValue([mockUser] as any);

      const leaderboard = await service.getLeaderboard({ limit: 50, timeFrame: TimeFrame.ALL });

      expect(leaderboard).toHaveLength(1);
      expect(leaderboard[0].rank).toBe(1);
      expect(leaderboard[0].elo).toBe(1400);
    });

    it('should filter by heroId when specified', async () => {
      const mockEntries = [
        {
          userId: 'user1',
          heroId: 'hero1',
          timeFrame: TimeFrame.ALL,
          rank: 1,
          elo: 1500,
          gamesWon: 50,
          gamesPlayed: 80,
        },
      ];

      jest.spyOn(prisma.leaderboardEntry, 'findMany').mockResolvedValue(mockEntries as any);
      jest.spyOn(prisma.user, 'findMany').mockResolvedValue([mockUser] as any);

      const leaderboard = await service.getLeaderboard({
        heroId: 'hero1',
        limit: 50,
        timeFrame: TimeFrame.ALL,
      });

      expect(prisma.leaderboardEntry.findMany).toHaveBeenCalledWith({
        where: {
          heroId: 'hero1',
          timeFrame: TimeFrame.ALL,
        },
        orderBy: {
          elo: 'desc',
        },
        take: 50,
      });
      expect(leaderboard).toHaveLength(1);
    });

    it('should handle unknown users gracefully', async () => {
      const mockEntries = [
        {
          userId: 'unknown',
          heroId: null,
          timeFrame: TimeFrame.ALL,
          rank: 1,
          elo: 1500,
          gamesWon: 50,
          gamesPlayed: 80,
        },
      ];

      jest.spyOn(prisma.leaderboardEntry, 'findMany').mockResolvedValue(mockEntries as any);
      jest.spyOn(prisma.user, 'findMany').mockResolvedValue([]);

      const leaderboard = await service.getLeaderboard({ limit: 50, timeFrame: TimeFrame.ALL });

      expect(leaderboard[0].user.username).toBe('Unknown');
      expect(leaderboard[0].user.avatar).toBeNull();
    });

    it('should respect timeFrame parameter', async () => {
      jest.spyOn(prisma.leaderboardEntry, 'findMany').mockResolvedValue([]);
      jest.spyOn(prisma.userStats, 'findMany').mockResolvedValue([mockStats] as any);
      jest.spyOn(prisma.user, 'findMany').mockResolvedValue([mockUser] as any);

      await service.getLeaderboard({ timeFrame: TimeFrame.WEEK, limit: 50 });

      expect(prisma.leaderboardEntry.findMany).toHaveBeenCalledWith({
        where: {
          heroId: null,
          timeFrame: TimeFrame.WEEK,
        },
        orderBy: {
          elo: 'desc',
        },
        take: 50,
      });
    });

    it('should filter by heroId when generating leaderboard', async () => {
      jest.spyOn(prisma.leaderboardEntry, 'findMany').mockResolvedValue([]);

      const statsWithHeroes = [
        { ...mockStats, userId: 'user1', heroStats: null },
        { ...mockStats, userId: 'user2', heroStats: { hero1: { gamesPlayed: 10 } } },
      ];
      jest.spyOn(prisma.userStats, 'findMany').mockResolvedValue(statsWithHeroes as any);
      jest
        .spyOn(prisma.user, 'findMany')
        .mockResolvedValue([mockUser, { id: 'user2', username: 'user2', avatar: null }] as any);

      const leaderboard = await service.getLeaderboard({
        heroId: 'hero1',
        limit: 50,
        timeFrame: TimeFrame.ALL,
      });

      expect(leaderboard).toHaveLength(1);
      expect(leaderboard[0].user.id).toBe('user2');
    });

    it('should limit results when specified', async () => {
      jest.spyOn(prisma.leaderboardEntry, 'findMany').mockResolvedValue([]);
      jest
        .spyOn(prisma.userStats, 'findMany')
        .mockResolvedValue([mockStats, mockStats, mockStats] as any);
      jest.spyOn(prisma.user, 'findMany').mockResolvedValue([mockUser] as any);

      const leaderboard = await service.getLeaderboard({ limit: 2, timeFrame: TimeFrame.ALL });

      expect(leaderboard.length).toBeLessThanOrEqual(2);
    });
  });

  describe('refreshLeaderboard', () => {
    it('should refresh leaderboard for all time frames', async () => {
      jest.spyOn(prisma.userStats, 'findMany').mockResolvedValue([mockStats] as any);
      jest.spyOn(prisma.leaderboardEntry, 'deleteMany').mockResolvedValue({ count: 1 });
      jest.spyOn(prisma.leaderboardEntry, 'createMany').mockResolvedValue({ count: 1 });

      await service.refreshLeaderboard();

      expect(prisma.leaderboardEntry.deleteMany).toHaveBeenCalledTimes(3);
      expect(prisma.leaderboardEntry.createMany).toHaveBeenCalledTimes(3);
    });

    it('should refresh leaderboard for specific hero', async () => {
      jest.spyOn(prisma.userStats, 'findMany').mockResolvedValue([mockStats] as any);
      jest.spyOn(prisma.leaderboardEntry, 'deleteMany').mockResolvedValue({ count: 1 });
      jest.spyOn(prisma.leaderboardEntry, 'createMany').mockResolvedValue({ count: 1 });

      await service.refreshLeaderboard('hero1');

      expect(prisma.leaderboardEntry.deleteMany).toHaveBeenCalledWith({
        where: {
          heroId: 'hero1',
          timeFrame: expect.any(String),
        },
      });
    });

    it('should limit leaderboard entries to top 100', async () => {
      jest.spyOn(prisma.userStats, 'findMany').mockResolvedValue([mockStats] as any);
      jest.spyOn(prisma.leaderboardEntry, 'deleteMany').mockResolvedValue({ count: 1 });
      jest.spyOn(prisma.leaderboardEntry, 'createMany').mockResolvedValue({ count: 1 });

      await service.refreshLeaderboard();

      expect(prisma.userStats.findMany).toHaveBeenCalledWith({
        orderBy: { currentElo: 'desc' },
        take: 100,
      });
    });

    it('should create correct leaderboard entries', async () => {
      jest.spyOn(prisma.userStats, 'findMany').mockResolvedValue([mockStats] as any);
      jest.spyOn(prisma.leaderboardEntry, 'deleteMany').mockResolvedValue({ count: 1 });
      jest.spyOn(prisma.leaderboardEntry, 'createMany').mockResolvedValue({ count: 1 });

      await service.refreshLeaderboard();

      expect(prisma.leaderboardEntry.createMany).toHaveBeenCalledWith({
        data: [
          {
            userId: 'user1',
            heroId: null,
            timeFrame: expect.any(String),
            rank: 1,
            elo: 1400,
            gamesWon: 30,
            gamesPlayed: 50,
          },
        ],
      });
    });
  });

  describe('win rate calculation', () => {
    it('should calculate win rate correctly', async () => {
      const winnerStats = { ...mockStats, userId: 'winner', gamesPlayed: 100, gamesWon: 75 };
      const loserStats = { ...mockStats, userId: 'loser' };

      jest
        .spyOn(prisma.userStats, 'findUnique')
        .mockResolvedValueOnce(winnerStats as any)
        .mockResolvedValueOnce(loserStats as any);

      const newRatings = { winner: 1410, loser: 1290 };
      jest.spyOn(ratingService, 'calculateNewRatings').mockReturnValue(newRatings);

      jest.spyOn(prisma.userStats, 'update').mockResolvedValue({} as any);
      jest
        .spyOn(prisma, '$transaction')
        .mockImplementation((operations: any) => Promise.all(operations as any[]));

      await service.updateStatsAfterGame('game1', 'winner', 'loser');

      const winnerUpdate = (prisma.userStats.update as jest.Mock).mock.calls[0][0];
      expect(winnerUpdate.data.winRate).toBeCloseTo(75.25, 1);
    });

    it('should handle zero games played', async () => {
      const newStats = { ...mockStats, gamesPlayed: 0, gamesWon: 0, winRate: 0 };
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(newStats as any);

      const stats = await service.getStats('user1');

      expect(stats.winRate).toBe(0);
    });
  });
});
