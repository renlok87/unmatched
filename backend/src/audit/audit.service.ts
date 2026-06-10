import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { v4 as uuidv4 } from 'uuid';
import { PrismaService } from '../database/prisma.service';
import {
  AuditEventType,
  AuditEvent,
  CreateAuditEventDto,
  AuditFilter,
  SuspiciousActivity,
} from '../games/models/audit.model';

@Injectable()
export class AuditService {
  private readonly logger = new Logger(AuditService.name);
  private readonly QUEUE_NAME = 'audit';
  private readonly MAX_METADATA_SIZE = 1024 * 1024; // 1MB

  constructor(
    @InjectQueue('audit') private readonly auditQueue: Queue,
    private readonly prisma: PrismaService,
  ) {}

  async logEvent(dto: CreateAuditEventDto): Promise<string> {
    const eventId = uuidv4();

    try {
      await this.auditQueue.add(
        'log-audit-event',
        {
          id: eventId,
          ...dto,
          timestamp: new Date(),
          success: dto.success ?? true,
          metadata: this.truncateMetadata(dto.metadata),
        },
        {
          attempts: 3,
          backoff: {
            type: 'exponential',
            delay: 1000,
          },
          removeOnComplete: {
            age: 7 * 24 * 3600,
          },
          removeOnFail: {
            age: 30 * 24 * 3600,
          },
        },
      );

      return eventId;
    } catch (error) {
      this.logger.error(`Failed to add audit event to queue: ${error.message}`);
      throw error;
    }
  }

  async getAuditLogs(filter: AuditFilter): Promise<AuditEvent[]> {
    const where = this.buildAuditWhere(filter);

    const logs = await this.prisma.authAuditLog.findMany({
      where,
      orderBy: { createdAt: 'desc' },
      take: 100,
    });

    return logs.map((log: any) => this.mapToAuditEvent(log));
  }

  /**
   * Получить логи с настоящей серверной пагинацией
   * total — общее число записей по фильтру (prisma.count)
   */
  async getAuditLogsPaginated(
    filter: AuditFilter,
    skip = 0,
    take = 50,
  ): Promise<{ items: AuditEvent[]; total: number }> {
    const where = this.buildAuditWhere(filter);

    const [logs, total] = await Promise.all([
      this.prisma.authAuditLog.findMany({
        where,
        orderBy: { createdAt: 'desc' },
        skip,
        take,
      }),
      this.prisma.authAuditLog.count({ where }),
    ]);

    return {
      items: logs.map((log: any) => this.mapToAuditEvent(log)),
      total,
    };
  }

  private buildAuditWhere(filter: AuditFilter): any {
    const where: any = {};

    if (filter.userId) {
      where.userId = filter.userId;
    }

    if (filter.startDate || filter.endDate) {
      where.createdAt = {};
      if (filter.startDate) {
        where.createdAt.gte = filter.startDate;
      }
      if (filter.endDate) {
        where.createdAt.lte = filter.endDate;
      }
    }

    if (filter.eventType) {
      where.action = filter.eventType;
    }

    if (filter.success !== undefined) {
      where.success = filter.success;
    }

    if (filter.ipAddress) {
      where.ipAddress = filter.ipAddress;
    }

    return where;
  }

  private mapToAuditEvent(log: any): AuditEvent {
    return {
      id: log.id,
      type: log.action as AuditEventType,
      userId: log.userId || undefined,
      ipAddress: log.ipAddress || undefined,
      userAgent: log.userAgent || undefined,
      metadata: (log.metadata as Record<string, any>) || {},
      timestamp: log.createdAt,
      success: log.success,
      errorMessage: log.errorMessage || undefined,
    };
  }

  async getUserAuditLogs(userId: string, startDate?: Date, endDate?: Date): Promise<AuditEvent[]> {
    return this.getAuditLogs({
      userId,
      startDate,
      endDate,
    });
  }

  async getSuspiciousActivity(timeWindowMinutes: number = 60): Promise<SuspiciousActivity[]> {
    const cutoffDate = new Date(Date.now() - timeWindowMinutes * 60 * 1000);

    const logs = await this.prisma.authAuditLog.findMany({
      where: {
        createdAt: {
          gte: cutoffDate,
        },
        action: {
          in: [
            AuditEventType.LOGIN_FAILED,
            AuditEventType.UNAUTHORIZED_ACCESS,
            AuditEventType.SUSPICIOUS_ACTIVITY,
            AuditEventType.RATE_LIMIT_EXCEEDED,
          ],
        },
      },
      orderBy: { createdAt: 'desc' },
    });

    const suspiciousByIp = new Map<string, SuspiciousActivity>();

    for (const log of logs) {
      const ip = log.ipAddress || 'unknown';
      const existing = suspiciousByIp.get(ip);

      if (!existing) {
        suspiciousByIp.set(ip, {
          userId: log.userId || undefined,
          ipAddress: ip,
          eventCount: 1,
          lastEventAt: log.createdAt,
          eventTypes: [log.action as AuditEventType],
        });
      } else {
        existing.eventCount++;
        existing.lastEventAt = log.createdAt;
        if (!existing.eventTypes.includes(log.action as AuditEventType)) {
          existing.eventTypes.push(log.action as AuditEventType);
        }
      }
    }

    const suspicious = Array.from(suspiciousByIp.values()).filter(
      (activity) => activity.eventCount >= 5,
    );

    return suspicious.sort((a, b) => b.eventCount - a.eventCount);
  }

  async getLoginAttempts(userId: string, timeWindowMinutes: number = 15): Promise<number> {
    const cutoffDate = new Date(Date.now() - timeWindowMinutes * 60 * 1000);

    const count = await this.prisma.authAuditLog.count({
      where: {
        userId,
        action: AuditEventType.LOGIN_FAILED,
        createdAt: {
          gte: cutoffDate,
        },
      },
    });

    return count;
  }

  async cleanupOldLogs(olderThanDays: number = 90): Promise<number> {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - olderThanDays);

    const result = await this.prisma.authAuditLog.deleteMany({
      where: {
        createdAt: {
          lt: cutoffDate,
        },
      },
    });

    this.logger.log(`Cleaned up ${result.count} old audit logs`);
    return result.count;
  }

  private truncateMetadata(metadata: Record<string, any>): Record<string, any> {
    const metadataStr = JSON.stringify(metadata);

    if (metadataStr.length > this.MAX_METADATA_SIZE) {
      this.logger.warn(`Metadata exceeds ${this.MAX_METADATA_SIZE} bytes, truncating`);
      return {
        truncated: true,
        originalSize: metadataStr.length,
        data: metadataStr.substring(0, this.MAX_METADATA_SIZE),
      };
    }

    return metadata;
  }
}
