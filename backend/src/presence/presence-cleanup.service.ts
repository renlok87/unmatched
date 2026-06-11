import { Injectable, Logger } from '@nestjs/common';
import { Cron, CronExpression } from '@nestjs/schedule';
import { PresenceService } from './presence.service';

@Injectable()
export class PresenceCleanupService {
  private readonly logger = new Logger(PresenceCleanupService.name);

  constructor(private readonly presenceService: PresenceService) {}

  @Cron(CronExpression.EVERY_10_MINUTES)
  async cleanupExpiredPresences(): Promise<void> {
    this.logger.debug('Running presence cleanup...');
    const cleaned = await this.presenceService.cleanupExpiredPresences();

    if (cleaned > 0) {
      this.logger.log(`Cleaned up ${cleaned} expired presences`);
    }
  }
}
