import { Module, Global } from '@nestjs/common';
import { RedisModule } from '../redis/redis.module';
import { DistributedLockService } from './services/distributed-lock.service';

/**
 * CommonModule
 *
 * Глобальный модуль для общих сервисов и декораторов.
 * Используется @Global() декоратором, поэтому доступен во всех модулях без явного импорта.
 */
@Global()
@Module({
  imports: [RedisModule],
  providers: [DistributedLockService],
  exports: [DistributedLockService],
})
export class CommonModule {}
