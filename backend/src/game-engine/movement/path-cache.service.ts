/**
 * Pathfinding Cache Service
 *
 * Кеширует результаты поиска путей для предотвращения
 * повторных вычислений BFS/A*.
 *
 * Проблема: BFS выполняется на каждой валидации перемещения
 * Решение: Кешируем доступные позиции для каждого бойца
 */

import { Injectable, Logger, Optional } from '@nestjs/common';
import { Position } from '../models';
import { MetricsService } from '../../metrics/metrics.service';

/**
 * Запись кеша путей
 */
export interface PathCacheEntry {
  readonly from: Position;
  readonly validPositions: readonly Position[];
  readonly timestamp: number;
}

/**
 * Ключ кеша для бойца
 */
interface PathCacheKey {
  fighterId: string;
  from: Position;
  maxDistance: number;
  // Опционально: хеш состояния доски для инвалидации
  boardHash?: string;
}

@Injectable()
export class PathfindingCacheService {
  private readonly logger = new Logger(PathfindingCacheService.name);
  private readonly cache = new Map<string, PathCacheEntry>();
  private readonly TTL = 5000; // 5 секунд - состояние быстро меняется

  // Статистика для метрик
  private hits = 0;
  private misses = 0;

  constructor(@Optional() private readonly metrics?: MetricsService) {
    // Периодическая отправка статистики в Prometheus
    if (metrics) {
      setInterval(() => {
        this.reportStats();
      }, 60000); // Каждую минуту
    }
  }

  /**
   * Получить кешированные позиции
   *
   * @param fighterId ID бойца
   * @param from Начальная позиция
   * @param maxDistance Максимальное расстояние
   * @returns Кешированные позиции или null
   */
  get(fighterId: string, from: Position, maxDistance: number): readonly Position[] | null {
    const key = this.cacheKey(fighterId, from, maxDistance);
    const entry = this.cache.get(key);

    if (!entry) {
      this.misses++;
      this.metrics?.incrementPathCacheOperation('pathfinding', 'miss');
      return null;
    }

    // Проверяем TTL
    if (Date.now() - entry.timestamp > this.TTL) {
      this.cache.delete(key);
      this.misses++;
      this.metrics?.incrementPathCacheOperation('pathfinding', 'miss');
      return null;
    }

    this.hits++;
    this.metrics?.incrementPathCacheOperation('pathfinding', 'hit');
    this.logger.debug(`Cache hit for path: ${key}`);
    return entry.validPositions;
  }

  /**
   * Сохранить позиции в кеш
   *
   * @param fighterId ID бойца
   * @param from Начальная позиция
   * @param maxDistance Максимальное расстояние
   * @param validPositions Доступные позиции
   */
  set(
    fighterId: string,
    from: Position,
    maxDistance: number,
    validPositions: readonly Position[],
  ): void {
    const key = this.cacheKey(fighterId, from, maxDistance);

    this.cache.set(key, {
      from,
      validPositions,
      timestamp: Date.now(),
    });

    this.metrics?.setPathCacheSize('pathfinding', this.cache.size);
    this.logger.debug(`Cached path for ${key}`);
  }

  /**
   * Инвалидировать весь кеш для бойца
   *
   * @param fighterId ID бойца
   */
  invalidate(fighterId: string): void {
    let count = 0;
    for (const key of this.cache.keys()) {
      if (key.startsWith(`${fighterId}:`)) {
        this.cache.delete(key);
        count++;
      }
    }
    this.metrics?.incrementPathCacheOperation('pathfinding', 'invalidate');
    this.metrics?.setPathCacheSize('pathfinding', this.cache.size);
    this.logger.debug(`Invalidated ${count} cache entries for fighter ${fighterId}`);
  }

  /**
   * Инвалидировать весь кеш
   */
  invalidateAll(): void {
    const count = this.cache.size;
    this.cache.clear();
    this.metrics?.incrementPathCacheOperation('pathfinding', 'invalidate');
    this.metrics?.setPathCacheSize('pathfinding', 0);
    this.logger.debug(`Invalidated all ${count} cache entries`);
  }

  /**
   * Очистить устаревшие записи
   */
  cleanup(): number {
    const now = Date.now();
    let cleaned = 0;

    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > this.TTL) {
        this.cache.delete(key);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      this.metrics?.setPathCacheSize('pathfinding', this.cache.size);
      this.logger.debug(`Cleaned up ${cleaned} expired cache entries`);
    }

    return cleaned;
  }

  /**
   * Получить статистику кеша
   */
  getStats(): { size: number; keys: string[]; hits: number; misses: number; hitRate: number } {
    const total = this.hits + this.misses;
    return {
      size: this.cache.size,
      keys: Array.from(this.cache.keys()),
      hits: this.hits,
      misses: this.misses,
      hitRate: total > 0 ? this.hits / total : 0,
    };
  }

  /**
   * Отправить статистику в Prometheus
   */
  private reportStats(): void {
    const stats = this.getStats();
    this.metrics?.setPathCacheSize('pathfinding', stats.size);
    this.logger.debug(
      `Pathfinding cache stats: size=${stats.size}, hits=${stats.hits}, misses=${stats.misses}, hitRate=${(stats.hitRate * 100).toFixed(1)}%`,
    );
  }

  /**
   * Создать ключ кеша
   */
  private cacheKey(fighterId: string, from: Position, maxDistance: number): string {
    return `${fighterId}:${from.x}:${from.y}:${maxDistance}`;
  }
}
