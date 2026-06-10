import { Injectable, Logger } from '@nestjs/common';
import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Job } from 'bullmq';
import { PrismaService } from '../database/prisma.service';

interface AuditEventJobData {
  id: string;
  type: string;
  userId?: string;
  ipAddress?: string;
  userAgent?: string;
  metadata: Record<string, any>;
  timestamp: Date;
  success: boolean;
  errorMessage?: string;
}

@Injectable()
@Processor('audit')
export class AuditProcessor extends WorkerHost {
  private readonly logger = new Logger(AuditProcessor.name);

  constructor(private readonly prisma: PrismaService) {
    super();
  }

  async process(job: Job<AuditEventJobData>): Promise<void> {
    const { id, type, userId, ipAddress, userAgent, metadata, timestamp, success, errorMessage } =
      job.data;

    try {
      await this.prisma.authAuditLog.create({
        data: {
          id,
          userId,
          action: type,
          success,
          ipAddress,
          userAgent,
          errorMessage,
          createdAt: timestamp,
        },
      });

      this.logger.debug(`Logged audit event ${id}: ${type}`);
    } catch (error) {
      this.logger.error(`Failed to log audit event ${id}: ${error.message}`, error.stack);
      throw error;
    }
  }
}
