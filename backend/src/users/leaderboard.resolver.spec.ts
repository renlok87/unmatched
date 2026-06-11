import { Test, TestingModule } from '@nestjs/testing';
import { LeaderboardResolver } from './leaderboard.resolver';
import { LeaderboardService } from '../games/services/leaderboard.service';
import { TimeFrame } from './dto';

describe('LeaderboardResolver', () => {
  let resolver: LeaderboardResolver;
  let leaderboardService: LeaderboardService;

  const mockLeaderboardService = {
    getLeaderboard: jest.fn(),
    getTopPlayers: jest.fn(),
    getPlayerRank: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        LeaderboardResolver,
        {
          provide: LeaderboardService,
          useValue: mockLeaderboardService,
        },
      ],
    }).compile();

    resolver = module.get<LeaderboardResolver>(LeaderboardResolver);
    leaderboardService = module.get<LeaderboardService>(LeaderboardService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('leaderboard', () => {
    it('should return leaderboard entries as JSON string', async () => {
      const mockResponse = {
        entries: [
          {
            rank: 1,
            userId: 'user1',
            username: 'player1',
            avatarUrl: 'avatar1.png',
            elo: 1500,
            gamesWon: 10,
            gamesPlayed: 15,
            winRate: 66.67,
          },
        ],
        totalCount: 1,
        page: 0,
        pageSize: 50,
      };

      mockLeaderboardService.getLeaderboard.mockResolvedValue(mockResponse);

      const result = await resolver.leaderboard();
      const parsed = JSON.parse(result);

      expect(leaderboardService.getLeaderboard).toHaveBeenCalledWith({
        heroId: undefined,
        timeFrame: 'all',
        page: 0,
        pageSize: 50,
      });
      expect(parsed).toEqual(mockResponse);
    });

    it('should accept custom parameters', async () => {
      const mockResponse = { entries: [], totalCount: 0, page: 1, pageSize: 25 };
      mockLeaderboardService.getLeaderboard.mockResolvedValue(mockResponse);

      const result = await resolver.leaderboard('hero1', TimeFrame.WEEK, 1, 25);
      const parsed = JSON.parse(result);

      expect(leaderboardService.getLeaderboard).toHaveBeenCalledWith({
        heroId: 'hero1',
        timeFrame: 'week',
        page: 1,
        pageSize: 25,
      });
    });
  });

  describe('topPlayers', () => {
    it('should return top players as JSON string', async () => {
      const mockPlayers = [
        {
          rank: 1,
          userId: 'user1',
          username: 'player1',
          avatarUrl: 'avatar1.png',
          elo: 1600,
          gamesWon: 20,
          gamesPlayed: 25,
          winRate: 80,
        },
        {
          rank: 2,
          userId: 'user2',
          username: 'player2',
          avatarUrl: 'avatar2.png',
          elo: 1550,
          gamesWon: 18,
          gamesPlayed: 30,
          winRate: 60,
        },
      ];

      mockLeaderboardService.getTopPlayers.mockResolvedValue(mockPlayers);

      const result = await resolver.topPlayers(2, 'all');
      const parsed = JSON.parse(result);

      expect(leaderboardService.getTopPlayers).toHaveBeenCalledWith(2, 'all');
      expect(parsed).toEqual(mockPlayers);
    });

    it('should use default limit when not provided', async () => {
      const mockPlayers = [
        {
          rank: 1,
          userId: 'user1',
          username: 'player1',
          avatarUrl: 'avatar1.png',
          elo: 1600,
          gamesWon: 20,
          gamesPlayed: 25,
          winRate: 80,
        },
      ];

      mockLeaderboardService.getTopPlayers.mockResolvedValue(mockPlayers);

      const result = await resolver.topPlayers();
      const parsed = JSON.parse(result);

      expect(leaderboardService.getTopPlayers).toHaveBeenCalledWith(10, 'all');
      expect(parsed).toEqual(mockPlayers);
    });
  });

  describe('getPlayerRank', () => {
    it('should return player rank', async () => {
      const mockRank = {
        rank: 5,
        userId: 'user1',
        elo: 1450,
        heroId: undefined,
        timeFrame: 'all',
      };

      mockLeaderboardService.getPlayerRank.mockResolvedValue(mockRank);

      const result = await resolver.getPlayerRank('user1');

      expect(leaderboardService.getPlayerRank).toHaveBeenCalledWith('user1', undefined, 'all');
      expect(result).toEqual(mockRank);
    });

    it('should accept heroId parameter', async () => {
      const mockRank = {
        rank: 3,
        userId: 'user1',
        elo: 1500,
        heroId: 'hero1',
        timeFrame: 'all',
      };

      mockLeaderboardService.getPlayerRank.mockResolvedValue(mockRank);

      const result = await resolver.getPlayerRank('user1', 'hero1', 'all');

      expect(leaderboardService.getPlayerRank).toHaveBeenCalledWith('user1', 'hero1', 'all');
      expect(result).toEqual(mockRank);
    });

    it('should accept custom timeFrame', async () => {
      const mockRank = {
        rank: 2,
        userId: 'user1',
        elo: 1550,
        heroId: undefined,
        timeFrame: 'weekly',
      };

      mockLeaderboardService.getPlayerRank.mockResolvedValue(mockRank);

      const result = await resolver.getPlayerRank('user1', undefined, 'weekly');

      expect(leaderboardService.getPlayerRank).toHaveBeenCalledWith('user1', undefined, 'weekly');
      expect(result).toEqual(mockRank);
    });
  });
});
