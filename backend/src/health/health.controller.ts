/**
 * Health Check Controller
 *
 * Предоставляет endpoints для проверки здоровья сервиса.
 * Используется Kubernetes для liveness/readiness probes.
 */

import { Controller, Get, Inject } from '@nestjs/common';
import {
  HealthCheck,
  HealthCheckService,
  HealthCheckResult,
  MicroserviceHealthIndicator,
} from '@nestjs/terminus';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';

@Controller('health')
export class HealthController {
  constructor(
    private health: HealthCheckService,
    private prisma: PrismaService,
    private redis: RedisService,
  ) {}

  /**
   * Базовый health check
   * GET /health
   *
   * Проверяет все критические зависимости.
   * Используется для readiness probe.
   */
@Get()
  @HealthCheck()
  async check(): Promise<HealthCheckResult & { timestamp: string; uptime: number }> {
    const result = await this.health.check([() => this.checkDatabase(), () => this.checkRedis()]);
    return {
      ...result,
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  }

  /**
   * Liveness probe
   * GET /health/live
   *
   * Простой endpoint для проверки, что процесс жив.
   * Не делает тяжёлых проверок.
   */
  @Get('live')
  liveness() {
    return { status: 'ok', timestamp: new Date().toISOString() };
  }

  /**
   * Readiness probe
   * GET /health/ready
   *
   * Проверяет, что сервис готов обрабатывать запросы.
   */
  @Get('ready')
  @HealthCheck()
  readiness() {
    return this.health.check([() => this.checkDatabase(), () => this.checkRedis()]);
  }

  /**
   * Детальная проверка
   * GET /health/detail
   *
   * Возвращает детальную информацию о состоянии всех компонентов.
   */
  @Get('detail')
  async detail() {
    const db = await this.getDatabaseDetails();
    const redis = await this.getRedisDetails();

    return {
      status: db.status === 'up' && redis.status === 'up' ? 'healthy' : 'unhealthy',
      timestamp: new Date().toISOString(),
      components: {
        database: db,
        redis: redis,
      },
    };
  }

  /**
   * Проверка базы данных
   */
  private async checkDatabase() {
    try {
      await this.prisma.$queryRaw`SELECT 1`;
      return { database: { status: 'up' } } as any;
    } catch (error) {
      return {
        database: {
          status: 'down',
          error: error instanceof Error ? error.message : 'Unknown error',
        },
      } as any;
    }
  }

  /**
   * Проверка Redis
   */
  private async checkRedis() {
    try {
      const result = await this.redis.ping();
      return { redis: { status: result === 'PONG' ? 'up' : 'degraded' } } as any;
    } catch (error) {
      return {
        redis: {
          status: 'down',
          error: error instanceof Error ? error.message : 'Unknown error',
        },
      } as any;
    }
  }

  /**
   * Детальная информация о БД
   */
  private async getDatabaseDetails() {
    try {
      const start = Date.now();
      await this.prisma.$queryRaw`SELECT 1`;
      const latency = Date.now() - start;

      return {
        status: 'up',
        latency: `${latency}ms`,
        connections: await this.getConnectionCount(),
      };
    } catch (error) {
      return {
        status: 'down',
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Детальная информация о Redis
   */
  private async getRedisDetails() {
    try {
      const start = Date.now();
      const result = await this.redis.ping();
      const latency = Date.now() - start;

      return {
        status: result === 'PONG' ? 'up' : 'degraded',
        latency: `${latency}ms`,
      };
    } catch (error) {
      return {
        status: 'down',
        error: error instanceof Error ? error.message : 'Unknown error',
      };
    }
  }

  /**
   * Получить количество подключений к БД
   */
  private async getConnectionCount(): Promise<number> {
    try {
      const result: Array<{ count: bigint }> = await this.prisma.$queryRaw`
        SELECT count(*) as count FROM pg_stat_activity WHERE state = 'active'
      `;
      return Number(result[0]?.count ?? 0);
    } catch {
      return 0;
    }
  }
}
