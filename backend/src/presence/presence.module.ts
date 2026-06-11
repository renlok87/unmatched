import { Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { PresenceService } from './presence.service';
import { PresenceCleanupService } from './presence-cleanup.service';
import { PresenceResolver } from './presence.resolver';

@Module({
  imports: [ScheduleModule.forRoot()],
  providers: [PresenceService, PresenceCleanupService, PresenceResolver],
  exports: [PresenceService],
})
export class PresenceModule {}
