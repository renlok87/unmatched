import { Module } from '@nestjs/common';
import { TerminusModule } from '@nestjs/terminus';
import { HealthController } from './health.controller';
import { PrismaModule } from '../database/prisma.module';
import { RedisModule } from '../redis/redis.module';

/**
 * Health Module
 *
 * Предоставляет health check endpoints для Kubernetes
 * и мониторинга состояния сервиса.
 */
@Module({
  imports: [
    TerminusModule.forRoot({
      errorLogStyle: 'pretty',
    }),
    PrismaModule,
    RedisModule,
  ],
  controllers: [HealthController],
})
export class HealthModule {}
