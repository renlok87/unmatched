import { Test, TestingModule } from '@nestjs/testing';
import { PresenceCleanupService } from './presence-cleanup.service';
import { PresenceService } from './presence.service';

describe('PresenceCleanupService', () => {
  let service: PresenceCleanupService;
  let presenceService: PresenceService;

  const mockPresenceService = {
    cleanupExpiredPresences: jest.fn(),
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        PresenceCleanupService,
        {
          provide: PresenceService,
          useValue: mockPresenceService,
        },
      ],
    }).compile();

    service = module.get<PresenceCleanupService>(PresenceCleanupService);
    presenceService = module.get<PresenceService>(PresenceService);

    jest.clearAllMocks();
  });

  describe('cleanupExpiredPresences', () => {
    it('should call presence service to cleanup', async () => {
      mockPresenceService.cleanupExpiredPresences.mockResolvedValue(5);

      await service.cleanupExpiredPresences();

      expect(mockPresenceService.cleanupExpiredPresences).toHaveBeenCalled();
    });
  });
});
