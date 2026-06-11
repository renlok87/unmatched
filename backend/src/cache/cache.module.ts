import { Module } from '@nestjs/common';
import { ScheduleModule } from '@nestjs/schedule';
import { CacheWarmingService } from './cache-warming.service';
import { CacheTagsService } from './cache-tags.service';
import { PrismaModule } from '../database/prisma.module';
import { RedisModule } from '../redis/redis.module';

/**
 * Cache Module
 *
 * Управляет кешированием и прогревом кеша
 * - Автоматический прогрев активных игр
 * - Прогрев доступных игр для лобби
 * - Предотвращение cache stampede
 * - Tag-based инвалидация
 */
@Module({
  imports: [ScheduleModule.forRoot(), PrismaModule, RedisModule],
  providers: [CacheWarmingService, CacheTagsService],
  exports: [CacheWarmingService, CacheTagsService],
})
export class CacheModule {}
