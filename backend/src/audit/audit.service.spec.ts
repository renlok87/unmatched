import { Test, TestingModule } from '@nestjs/testing';
import { AuditService } from './audit.service';
import { PrismaService } from '../database/prisma.service';
import { getQueueToken } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { AuditEventType } from '../games/models/audit.model';

describe('AuditService', () => {
  let service: AuditService;
  let queue: Queue;
  let prisma: PrismaService;

  const mockQueue = {
    add: jest.fn(),
  };

  const mockPrisma = {
    authAuditLog: {
      findMany: jest.fn(),
      count: jest.fn(),
      deleteMany: jest.fn(),
    },
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuditService,
        {
          provide: getQueueToken('audit'),
          useValue: mockQueue,
        },
        {
          provide: PrismaService,
          useValue: mockPrisma,
        },
      ],
    }).compile();

    service = module.get<AuditService>(AuditService);
    queue = module.get<Queue>(getQueueToken('audit'));
    prisma = module.get<PrismaService>(PrismaService);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('logEvent', () => {
    it('should add audit event to queue', async () => {
      const dto = {
        type: AuditEventType.USER_LOGIN,
        userId: 'user1',
        ipAddress: '127.0.0.1',
        userAgent: 'test',
        metadata: {},
        success: true,
      };

      mockQueue.add.mockResolvedValue('jobId');

      const eventId = await service.logEvent(dto);

      expect(mockQueue.add).toHaveBeenCalledWith(
        'log-audit-event',
        expect.objectContaining({
          type: AuditEventType.USER_LOGIN,
          userId: 'user1',
          success: true,
        }),
        expect.objectContaining({
          attempts: 3,
        }),
      );
      expect(eventId).toBeDefined();
    });

    it('should handle queue errors', async () => {
      const dto = {
        type: AuditEventType.USER_LOGIN,
        metadata: {},
      };

      mockQueue.add.mockRejectedValue(new Error('Queue error'));

      await expect(service.logEvent(dto)).rejects.toThrow('Queue error');
    });
  });

  describe('getAuditLogs', () => {
    it('should return audit logs', async () => {
      const mockLogs = [
        {
          id: 'log1',
          userId: 'user1',
          action: AuditEventType.USER_LOGIN,
          success: true,
          ipAddress: '127.0.0.1',
          userAgent: 'test',
          errorMessage: null,
          createdAt: new Date(),
        },
      ];

      mockPrisma.authAuditLog.findMany.mockResolvedValue(mockLogs);

      const logs = await service.getAuditLogs({ userId: 'user1' });

      expect(mockPrisma.authAuditLog.findMany).toHaveBeenCalledWith({
        where: {
          userId: 'user1',
        },
        orderBy: { createdAt: 'desc' },
        take: 100,
      });
      expect(logs).toHaveLength(1);
    });

    it('should filter by date range', async () => {
      mockPrisma.authAuditLog.findMany.mockResolvedValue([]);

      const startDate = new Date('2024-01-01');
      const endDate = new Date('2024-01-31');

      await service.getAuditLogs({
        startDate,
        endDate,
      });

      expect(mockPrisma.authAuditLog.findMany).toHaveBeenCalledWith({
        where: {
          createdAt: {
            gte: startDate,
            lte: endDate,
          },
        },
        orderBy: { createdAt: 'desc' },
        take: 100,
      });
    });
  });

  describe('getSuspiciousActivity', () => {
    it('should return suspicious activity', async () => {
      const mockLogs = Array(10).fill({
        userId: 'user1',
        action: AuditEventType.LOGIN_FAILED,
        ipAddress: '127.0.0.1',
        createdAt: new Date(),
      });

      mockPrisma.authAuditLog.findMany.mockResolvedValue(mockLogs);

      const activity = await service.getSuspiciousActivity(60);

      expect(mockPrisma.authAuditLog.findMany).toHaveBeenCalledWith({
        where: {
          createdAt: expect.any(Object),
          action: {
            in: expect.arrayContaining([
              AuditEventType.LOGIN_FAILED,
              AuditEventType.UNAUTHORIZED_ACCESS,
              AuditEventType.SUSPICIOUS_ACTIVITY,
              AuditEventType.RATE_LIMIT_EXCEEDED,
            ]),
          },
        },
        orderBy: { createdAt: 'desc' },
      });
    });
  });

  describe('getLoginAttempts', () => {
    it('should return login attempt count', async () => {
      mockPrisma.authAuditLog.count.mockResolvedValue(3);

      const count = await service.getLoginAttempts('user1', 15);

      expect(mockPrisma.authAuditLog.count).toHaveBeenCalledWith({
        where: {
          userId: 'user1',
          action: AuditEventType.LOGIN_FAILED,
          createdAt: expect.any(Object),
        },
      });
      expect(count).toBe(3);
    });
  });

  describe('cleanupOldLogs', () => {
    it('should delete old logs', async () => {
      mockPrisma.authAuditLog.deleteMany.mockResolvedValue({ count: 100 });

      const count = await service.cleanupOldLogs(90);

      expect(mockPrisma.authAuditLog.deleteMany).toHaveBeenCalledWith({
        where: {
          createdAt: expect.objectContaining({
            lt: expect.any(Date),
          }),
        },
      });
      expect(count).toBe(100);
    });
  });
});
