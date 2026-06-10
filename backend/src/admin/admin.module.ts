import { Module } from '@nestjs/common';
import { AdminResolver } from './admin.resolver';
import { AdminService } from './admin.service';
import { PrismaModule } from '../database';
import { AuditModule } from '../audit/audit.module';
import { MatchmakingModule } from '../matchmaking/matchmaking.module';

/**
 * Admin Module
 * Модуль для административных функций
 */
@Module({
  imports: [PrismaModule, AuditModule, MatchmakingModule],
  providers: [AdminResolver, AdminService],
  exports: [AdminService, AdminResolver],
})
export class AdminModule {}
