import { Module } from '@nestjs/common';
import { PrometheusModule } from '@willsoto/nestjs-prometheus';
import { metricsProviders, MetricsService } from './metrics.service';

/**
 * Metrics Module
 *
 * Предоставляет Prometheus метрики для мониторинга.
 * Метрики доступны по адресу /metrics
 *
 * Экспортируемые метрики:
 * - game_actions_total: счётчик игровых действий
 * - combat_duration_seconds: гистограмма времени разрешения боя
 * - card_effects_total: счётчик выполненных эффектов карт
 * - game_service_duration_seconds: гистограмма времени операций сервисов
 * - path_cache_operations_total: операции кеша путей
 * - game_service_errors_total: счётчик ошибок сервисов
 *
 * TODO: Fix Prometheus injection for @willsoto/nestjs-prometheus v6
 */
@Module({
  imports: [
    PrometheusModule.register({
      path: '/metrics',
      defaultMetrics: {
        enabled: true,
        config: {
          labels: {
            app: 'unmatched-backend',
            environment: process.env.NODE_ENV || 'development',
          },
        },
      },
    }),
  ],
  providers: [MetricsService, ...metricsProviders],
  exports: [PrometheusModule, MetricsService],
})
export class MetricsModule {}
