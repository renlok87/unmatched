import { Test, TestingModule } from '@nestjs/testing';
import { RatingService, RatingResult, RatingChange } from './rating.service';
import { PrismaService } from '../database/prisma.service';

describe('RatingService', () => {
  let service: RatingService;
  let prisma: PrismaService;

  const mockStats = {
    userId: 'user1',
    currentElo: 1400,
    peakElo: 1500,
    gamesPlayed: 50,
    gamesWon: 30,
    heroStats: {
      hero1: {
        gamesPlayed: 10,
        gamesWon: 6,
        elo: 1350,
        peakElo: 1400,
      },
      hero2: {
        gamesPlayed: 5,
        gamesWon: 2,
        elo: 1250,
        peakElo: 1300,
      },
    },
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RatingService,
        {
          provide: PrismaService,
          useValue: {
            userStats: {
              findUnique: jest.fn(),
              update: jest.fn(),
            },
          },
        },
      ],
    }).compile();

    service = module.get<RatingService>(RatingService);
    prisma = module.get(PrismaService);
  });

  describe('calculateNewRatings', () => {
    it('should calculate expected score correctly', () => {
      const winnerElo = 1400;
      const loserElo = 1200;

      const result = service.calculateNewRatings(winnerElo, loserElo);

      expect(result.winner).toBeGreaterThan(winnerElo);
      expect(result.loser).toBeLessThan(loserElo);
    });

    it('should calculate new ELO after win with correct formula', () => {
      const winnerElo = 1400;
      const loserElo = 1200;
      const K = 32;

      const result = service.calculateNewRatings(winnerElo, loserElo);

      const expectedWinnerScore = 1 / (1 + Math.pow(10, (loserElo - winnerElo) / 400));
      const expectedNewWinnerElo = Math.round(winnerElo + K * (1 - expectedWinnerScore));

      expect(result.winner).toBe(expectedNewWinnerElo);
    });

    it('should calculate new ELO after loss with correct formula', () => {
      const winnerElo = 1400;
      const loserElo = 1200;
      const K = 32;

      const result = service.calculateNewRatings(winnerElo, loserElo);

      const expectedLoserScore = 1 / (1 + Math.pow(10, (winnerElo - loserElo) / 400));
      const expectedNewLoserElo = Math.round(loserElo + K * (0 - expectedLoserScore));

      expect(result.loser).toBe(expectedNewLoserElo);
    });

    it('should handle equal ratings', () => {
      const elo = 1200;

      const result = service.calculateNewRatings(elo, elo);

      const expectedWinnerScore = 1 / (1 + Math.pow(10, (elo - elo) / 400));
      const expectedWinnerElo = Math.round(elo + 32 * (1 - expectedWinnerScore));
      const expectedLoserElo = Math.round(elo + 32 * (0 - expectedWinnerScore));

      expect(result.winner).toBe(expectedWinnerElo);
      expect(result.loser).toBe(expectedLoserElo);
      expect(result.winner + result.loser).toBe(elo + elo);
    });

    it('should limit rating change to K factor for higher rated winner', () => {
      const winnerElo = 2000;
      const loserElo = 1000;

      const result = service.calculateNewRatings(winnerElo, loserElo);

      const change = result.winner - winnerElo;
      expect(change).toBeGreaterThanOrEqual(0);
      expect(change).toBeLessThanOrEqual(32);
    });

    it('should give maximum points for lower rated player winning', () => {
      const winnerElo = 1000;
      const loserElo = 2000;

      const result = service.calculateNewRatings(winnerElo, loserElo);

      const change = result.winner - winnerElo;
      expect(change).toBeGreaterThan(0);
      expect(change).toBeLessThanOrEqual(32);
    });
  });

  describe('getPlayerRating', () => {
    it('should return general player rating', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);

      const rating = await service.getPlayerRating('user1');

      expect(rating).toBe(1400);
      expect(prisma.userStats.findUnique).toHaveBeenCalledWith({
        where: { userId: 'user1' },
      });
    });

    it('should return default rating for non-existent stats', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(null);

      const rating = await service.getPlayerRating('nonexistent');

      expect(rating).toBe(1200);
    });

    it('should return hero-specific rating', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);

      const rating = await service.getPlayerRating('user1', 'hero1');

      expect(rating).toBe(1350);
    });

    it('should return default rating for hero without stats', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);

      const rating = await service.getPlayerRating('user1', 'hero3');

      expect(rating).toBe(1200);
    });

    it('should return default rating for hero when stats exist but hero missing', async () => {
      const statsWithoutHero = {
        ...mockStats,
        heroStats: {},
      };
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(statsWithoutHero as any);

      const rating = await service.getPlayerRating('user1', 'hero3');

      expect(rating).toBe(1200);
    });
  });

  describe('updatePlayerRating', () => {
    it('should update general player rating', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma.userStats, 'update').mockResolvedValue(mockStats as any);

      await service.updatePlayerRating('user1', 1450);

      expect(prisma.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: {
          currentElo: 1450,
          peakElo: 1500,
        },
      });
    });

    it('should update peakElo when new rating is higher', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma.userStats, 'update').mockResolvedValue(mockStats as any);

      await service.updatePlayerRating('user1', 1600);

      expect(prisma.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: {
          currentElo: 1600,
          peakElo: 1600,
        },
      });
    });

    it('should throw error when stats not found', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(null);

      await expect(service.updatePlayerRating('nonexistent', 1200)).rejects.toThrow(
        'Stats not found for user',
      );
    });

    it('should update hero-specific rating', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma.userStats, 'update').mockResolvedValue(mockStats as any);

      await service.updatePlayerRating('user1', 1380, 'hero1');

      expect(prisma.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: expect.objectContaining({
          heroStats: expect.objectContaining({
            hero1: expect.objectContaining({
              elo: 1380,
              peakElo: 1400,
            }),
          }),
        }),
      });
    });

    it('should create hero stats entry if hero does not exist', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma.userStats, 'update').mockResolvedValue(mockStats as any);

      await service.updatePlayerRating('user1', 1250, 'hero3');

      expect(prisma.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: expect.objectContaining({
          heroStats: expect.objectContaining({
            hero3: expect.objectContaining({
              gamesPlayed: 0,
              gamesWon: 0,
              elo: 1250,
            }),
          }),
        }),
      });
    });

    it('should update hero peakElo when new rating is higher', async () => {
      jest.spyOn(prisma.userStats, 'findUnique').mockResolvedValue(mockStats as any);
      jest.spyOn(prisma.userStats, 'update').mockResolvedValue(mockStats as any);

      await service.updatePlayerRating('user1', 1450, 'hero1');

      expect(prisma.userStats.update).toHaveBeenCalledWith({
        where: { userId: 'user1' },
        data: expect.objectContaining({
          heroStats: expect.objectContaining({
            hero1: expect.objectContaining({
              elo: 1450,
              peakElo: 1450,
            }),
          }),
        }),
      });
    });
  });

  describe('calculateRatingChange', () => {
    it('should calculate rating change for win', () => {
      const change = service.calculateRatingChange(1400, 1200, true);

      expect(change.oldRating).toBe(1400);
      expect(change.newRating).toBeGreaterThan(1400);
      expect(change.change).toBeGreaterThan(0);
    });

    it('should calculate rating change for loss', () => {
      const change = service.calculateRatingChange(1400, 1200, false);

      expect(change.oldRating).toBe(1400);
      expect(change.newRating).toBeLessThan(1400);
      expect(change.change).toBeLessThan(0);
    });

    it('should return correct change calculation', () => {
      const playerRating = 1400;
      const opponentRating = 1200;

      const winChange = service.calculateRatingChange(playerRating, opponentRating, true);
      const lossChange = service.calculateRatingChange(opponentRating, playerRating, false);

      expect(winChange.newRating - winChange.oldRating).toBe(winChange.change);
      expect(lossChange.newRating - lossChange.oldRating).toBe(lossChange.change);
    });

    it('should handle equal ratings in rating change', () => {
      const change = service.calculateRatingChange(1200, 1200, true);

      expect(change.change).toBe(16);
      expect(change.newRating).toBe(1216);
    });
  });

  describe('getKFactor', () => {
    it('should return K factor', () => {
      const kFactor = service.getKFactor();

      expect(kFactor).toBe(32);
    });
  });

  describe('ELO calculation edge cases', () => {
    it('should handle very high rating differences', () => {
      const result = service.calculateNewRatings(2500, 1000);

      expect(result.winner).toBeGreaterThanOrEqual(2500);
      expect(result.loser).toBeLessThanOrEqual(1000);
    });

    it('should handle very low ratings', () => {
      const result = service.calculateNewRatings(800, 700);

      expect(result.winner).toBeGreaterThan(800);
      expect(result.loser).toBeLessThan(700);
    });

    it('should maintain rating consistency', () => {
      const initialWinner = 1500;
      const initialLoser = 1300;

      const result = service.calculateNewRatings(initialWinner, initialLoser);

      const totalChange = result.winner - initialWinner + (result.loser - initialLoser);
      expect(totalChange).toBeCloseTo(0, 0);
    });
  });
});
