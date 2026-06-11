import { Test, TestingModule } from '@nestjs/testing';
import { PresenceResolver } from './presence.resolver';
import { PresenceService } from './presence.service';
import { PresenceStatus } from './models/presence.model';

describe('PresenceResolver', () => {
  let resolver: PresenceResolver;
  let presenceService: PresenceService;

  const mockPresenceService = {
    updatePresence: jest.fn(),
    getPresence: jest.fn(),
    getOnlineUserIds: jest.fn(),
    getOnlineCount: jest.fn(),
    subscribeToPresenceUpdates: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PresenceResolver,
        {
          provide: PresenceService,
          useValue: mockPresenceService,
        },
      ],
    }).compile();

    resolver = module.get<PresenceResolver>(PresenceResolver);
    presenceService = module.get<PresenceService>(PresenceService);

    jest.clearAllMocks();
  });

  describe('heartbeat', () => {
    it('should update user presence and return response', async () => {
      const mockUser = {
        userId: 'user123',
        email: 'test@example.com',
        username: 'testuser',
      };
      const input = {
        status: PresenceStatus.ONLINE,
        currentGameId: 'game456',
      };

      const mockPresence = {
        userId: mockUser.userId,
        status: PresenceStatus.ONLINE,
        currentGameId: 'game456',
        lastSeenAt: Date.now(),
      };

      mockPresenceService.updatePresence.mockResolvedValue(mockPresence);

      const result = await resolver.heartbeat(mockUser, input);

      expect(result).toEqual({
        presence: {
          userId: mockPresence.userId,
          status: mockPresence.status,
          currentGameId: mockPresence.currentGameId,
          lastSeenAt: mockPresence.lastSeenAt,
        },
        ttl: 300,
      });

      expect(mockPresenceService.updatePresence).toHaveBeenCalledWith(
        mockUser.userId,
        input.status,
        input.currentGameId,
      );
    });

    it('should use default status if not provided', async () => {
      const mockUser = {
        userId: 'user123',
        email: 'test@example.com',
        username: 'testuser',
      };
      const input = { currentGameId: 'game456' };

      const mockPresence = {
        userId: mockUser.userId,
        status: PresenceStatus.ONLINE,
        currentGameId: 'game456',
        lastSeenAt: Date.now(),
      };

      mockPresenceService.updatePresence.mockResolvedValue(mockPresence);

      await resolver.heartbeat(mockUser, input);

      expect(mockPresenceService.updatePresence).toHaveBeenCalledWith(
        mockUser.userId,
        PresenceStatus.ONLINE,
        'game456',
      );
    });
  });

  describe('getPresence', () => {
    it('should return presence data', async () => {
      const userId = 'user123';
      const mockPresence = {
        userId,
        status: PresenceStatus.ONLINE,
        lastSeenAt: Date.now(),
        currentGameId: undefined,
      };

      mockPresenceService.getPresence.mockResolvedValue(mockPresence);

      const result = await resolver.getPresence(userId);

      expect(result).toEqual({
        userId: mockPresence.userId,
        status: mockPresence.status,
        currentGameId: mockPresence.currentGameId,
        lastSeenAt: mockPresence.lastSeenAt,
      });

      expect(mockPresenceService.getPresence).toHaveBeenCalledWith(userId);
    });

    it('should return null if presence not found', async () => {
      mockPresenceService.getPresence.mockResolvedValue(null);

      const result = await resolver.getPresence('user123');

      expect(result).toBeNull();
    });
  });

  describe('getOnlineUsers', () => {
    it('should return online users', async () => {
      const mockUsers = ['user1', 'user2', 'user3'];
      mockPresenceService.getOnlineUserIds.mockResolvedValue(mockUsers);

      const result = await resolver.getOnlineUsers();

      expect(result).toEqual({
        userIds: mockUsers,
        count: 3,
      });

      expect(mockPresenceService.getOnlineUserIds).toHaveBeenCalled();
    });
  });

  describe('getOnlineCount', () => {
    it('should return online count', async () => {
      mockPresenceService.getOnlineCount.mockResolvedValue(5);

      const result = await resolver.getOnlineCount();

      expect(result).toBe(5);

      expect(mockPresenceService.getOnlineCount).toHaveBeenCalled();
    });
  });
});
