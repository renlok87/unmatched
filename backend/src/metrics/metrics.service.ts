/**
 * Custom Metrics
 *
 * Кастомные метрики для приложения с поддержкой Prometheus.
 * Предоставляет Counter, Histogram, Gauge для мониторинга производительности.
 */

import { Injectable, Inject, Scope } from '@nestjs/common';
import { makeCounterProvider, makeGaugeProvider, makeHistogramProvider } from '@willsoto/nestjs-prometheus';
import { Counter, Gauge, Histogram } from 'prom-client';

/**
 * Лейблы для метрик
 */
export type ActionLabels = {
  action_type: string;
  game_mode?: string;
  status?: 'success' | 'error';
};

export type CombatLabels = {
  attacker_hero: string;
  defender_hero: string;
  result: 'win' | 'loss' | 'draw';
};

export type CardEffectLabels = {
  effect_type: string;
  timing: string;
  hero_id?: string;
};

export type DurationLabels = {
  operation: string;
  service: string;
};

export type CacheLabels = {
  cache_type: string;
  status: 'hit' | 'miss' | 'invalidate';
};

/**
 * Провайдеры метрик
 */
export const metricsProviders = [
  // Счётчик действий игры
  makeCounterProvider({
    name: 'game_actions_total',
    help: 'Total number of game actions executed',
    labelNames: ['action_type', 'game_mode', 'status'],
  }),

  // Счётчик созданных игр
  makeCounterProvider({
    name: 'games_created_total',
    help: 'Total number of games created',
  }),

  // Счётчик завершённых игр
  makeCounterProvider({
    name: 'games_completed_total',
    help: 'Total number of games completed',
    labelNames: ['winner_type'],
  }),

  // Гистограмма боёв
  makeHistogramProvider({
    name: 'combat_duration_seconds',
    help: 'Duration of combat resolution in seconds',
    labelNames: ['attacker_hero', 'defender_hero', 'result'],
    buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1],
  }),

  // Счётчик эффектов карт
  makeCounterProvider({
    name: 'card_effects_total',
    help: 'Total number of card effects executed',
    labelNames: ['effect_type', 'timing', 'hero_id', 'status'],
  }),

  // Гистограмма времени выполнения эффектов карт
  makeHistogramProvider({
    name: 'card_effect_duration_seconds',
    help: 'Duration of card effect execution in seconds',
    labelNames: ['effect_type', 'timing'],
    buckets: [0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05],
  }),

  // Гистограмма операций игровых сервисов
  makeHistogramProvider({
    name: 'game_service_duration_seconds',
    help: 'Duration of game service operations in seconds',
    labelNames: ['operation', 'service'],
    buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5],
  }),

  // Гистограмма валидации
  makeHistogramProvider({
    name: 'validation_duration_seconds',
    help: 'Duration of rule validation in seconds',
    labelNames: ['validation_type'],
    buckets: [0.0001, 0.0005, 0.001, 0.005, 0.01],
  }),

  // Счётчик операций кеша путей
  makeCounterProvider({
    name: 'path_cache_operations_total',
    help: 'Total number of path cache operations',
    labelNames: ['cache_type', 'status'],
  }),

  // Gauge размера кеша
  makeGaugeProvider({
    name: 'path_cache_size',
    help: 'Current size of path cache',
    labelNames: ['cache_type'],
  }),

  // Счётчик ошибок игровых сервисов
  makeCounterProvider({
    name: 'game_service_errors_total',
    help: 'Total number of game service errors',
    labelNames: ['service', 'operation', 'error_type'],
  }),

  // Активные игры
  makeGaugeProvider({
    name: 'games_active',
    help: 'Number of currently active games',
  }),

  // Активные пользователи
  makeGaugeProvider({
    name: 'users_online',
    help: 'Number of currently online users',
  }),
];

/**
 * Контекст для структурированного логирования
 */
export interface LogContext {
  readonly gameId?: string;
  readonly userId?: string;
  readonly action?: string;
  readonly duration?: number;
  readonly [key: string]: unknown;
}

/**
 * Metrics Service
 *
 * Сервис для записи метрик и структурированного логирования.
 * Использует инъекцию провайдеров Prometheus.
 */
@Injectable({ scope: Scope.DEFAULT })
export class MetricsService {
  // TODO: Fix Prometheus injection for @willsoto/nestjs-prometheus v6
  // All metrics are temporarily disabled - methods are no-ops
  constructor() {}

  /**
   * Инкрементировать счётчик действий игры
   * TEMPORARILY DISABLED - metrics not configured
   */
  incrementGameAction(actionType: string, gameMode?: string, status: 'success' | 'error' = 'success'): void {
    // Disabled: this.gameActionsCounter.inc(...)
  }

  /**
   * Инкрементировать счётчик созданных игр
   * TEMPORARILY DISABLED - metrics not configured
   */
  incrementGamesCreated(): void {
    // Disabled: this.gamesCreatedCounter.inc()
  }

  /**
   * Инкрементировать счётчик завершённых игр
   * TEMPORARILY DISABLED - metrics not configured
   */
  incrementGamesCompleted(winnerType: string): void {
    // Disabled: this.gamesCompletedCounter.inc(...)
  }

  /**
   * Записать время выполнения боя
   * TEMPORARILY DISABLED - metrics not configured
   */
  recordCombatDuration(
    duration: number,
    attackerHero: string,
    defenderHero: string,
    result: 'win' | 'loss' | 'draw',
  ): void {
    // Disabled: this.combatDuration.observe(...)
  }

  /**
   * Инкрементировать счётчик эффектов карт
   * TEMPORARILY DISABLED - metrics not configured
   */
  incrementCardEffect(
    effectType: string,
    timing: string,
    heroId?: string,
    status: 'success' | 'error' = 'success',
  ): void {
    // Disabled: this.cardEffectsCounter.inc(...)
  }

  /**
   * Записать время выполнения эффекта карты
   * TEMPORARILY DISABLED - metrics not configured
   */
  recordCardEffectDuration(effectType: string, timing: string, duration: number): void {
    // Disabled: this.cardEffectDuration.observe(...)
  }

  /**
   * Записать время выполнения операции сервиса
   * TEMPORARILY DISABLED - metrics not configured
   */
  recordServiceDuration(operation: string, service: string, duration: number): void {
    // Disabled: this.serviceDuration.observe(...)
  }

  /**
   * Записать время валидации
   * TEMPORARILY DISABLED - metrics not configured
   */
  recordValidationDuration(validationType: string, duration: number): void {
    // Disabled: this.validationDuration.observe(...)
  }

  /**
   * Инкрементировать счётчик операций кеша путей
   * TEMPORARILY DISABLED - metrics not configured
   */
  incrementPathCacheOperation(cacheType: string, status: 'hit' | 'miss' | 'invalidate'): void {
    // Disabled: this.pathCacheCounter.inc(...)
  }

  /**
   * Установить размер кеша путей
   * TEMPORARILY DISABLED - metrics not configured
   */
  setPathCacheSize(cacheType: string, size: number): void {
    // Disabled: this.pathCacheSize.set(...)
  }

  /**
   * Инкрементировать счётчик ошибок
   * TEMPORARILY DISABLED - metrics not configured
   */
  incrementError(service: string, operation: string, errorType: string): void {
    // Disabled: this.serviceErrorsCounter.inc(...)
  }

  /**
   * Установить количество активных игр
   * TEMPORARILY DISABLED - metrics not configured
   */
  setActiveGames(count: number): void {
    // Disabled: this.activeGamesGauge.set(count)
  }

  /**
   * Установить количество пользователей онлайн
   * TEMPORARILY DISABLED - metrics not configured
   */
  setOnlineUsers(count: number): void {
    // Disabled: this.onlineUsersGauge.set(count)
  }

  /**
   * Замерить время выполнения операции
   *
   * @param operation Имя операции
   * @param service Имя сервиса
   * @param fn Функция для выполнения
   * @returns Результат функции
   */
  async measureServiceDuration<T>(
    operation: string,
    service: string,
    fn: () => Promise<T> | T,
  ): Promise<T> {
    const start = Date.now();
    try {
      const result = await fn();
      const duration = (Date.now() - start) / 1000;
      this.recordServiceDuration(operation, service, duration);
      return result;
    } catch (error) {
      const duration = (Date.now() - start) / 1000;
      this.recordServiceDuration(operation, service, duration);
      this.incrementError(service, operation, error instanceof Error ? error.name : 'unknown');
      throw error;
    }
  }

  /**
   * Замерить время выполнения эффекта карты
   */
  async measureCardEffect<T>(
    effectType: string,
    timing: string,
    fn: () => Promise<T> | T,
  ): Promise<T> {
    const start = Date.now();
    try {
      const result = await fn();
      const duration = (Date.now() - start) / 1000;
      this.recordCardEffectDuration(effectType, timing, duration);
      this.incrementCardEffect(effectType, timing, undefined, 'success');
      return result;
    } catch (error) {
      const duration = (Date.now() - start) / 1000;
      this.recordCardEffectDuration(effectType, timing, duration);
      this.incrementCardEffect(effectType, timing, undefined, 'error');
      throw error;
    }
  }

  /**
   * Замерить время разрешения боя
   */
  async measureCombat<T extends object>(
    attackerHero: string,
    defenderHero: string,
    fn: () => Promise<{ attackerDamage: number; defenderDamage: number }>,
  ): Promise<T> {
    const start = Date.now();
    try {
      const result = await fn() as T;
      const duration = (Date.now() - start) / 1000;

      // Определяем результат боя
      let resultType: 'win' | 'loss' | 'draw' = 'draw';
      if (result && 'attackerDamage' in result && 'defenderDamage' in result) {
        const combatResult = result as { attackerDamage: number; defenderDamage: number };
        if (combatResult.defenderDamage > combatResult.attackerDamage) {
          resultType = 'win';
        } else if (combatResult.attackerDamage > combatResult.defenderDamage) {
          resultType = 'loss';
        }
      }

      this.recordCombatDuration(duration, attackerHero, defenderHero, resultType);
      return result;
    } catch (error) {
      const duration = (Date.now() - start) / 1000;
      this.recordCombatDuration(duration, attackerHero, defenderHero, 'draw');
      throw error;
    }
  }

  /**
   * Замерить время валидации
   */
  async measureValidation<T>(
    validationType: string,
    fn: () => Promise<T> | T,
  ): Promise<T> {
    const start = Date.now();
    try {
      const result = await fn();
      const duration = (Date.now() - start) / 1000;
      this.recordValidationDuration(validationType, duration);
      return result;
    } catch (error) {
      const duration = (Date.now() - start) / 1000;
      this.recordValidationDuration(validationType, duration);
      throw error;
    }
  }
}
