/**
 * Card Value Cache Service
 *
 * Оптимизированный кэш для значений карт с поддержкой батч операций.
 * Использует LRU кэширование для уменьшения количества поисков в GameState.
 */

import { Injectable, Logger } from '@nestjs/common';
import { MetricsService } from '../../metrics/metrics.service';

/**
 * Запись в кэше значений карты
 */
interface CardValueEntry {
  readonly attackValue?: number;
  readonly defenseValue?: number;
  readonly effects: readonly string[];
  readonly timestamp: number;
}

/**
 * Batch операция для получения значений карт
 */
interface BatchCardValueRequest {
  readonly cardId: string;
  readonly state: any;
}

/**
 * Batch результат
 */
interface BatchCardValueResult {
  readonly cardId: string;
  readonly attackValue?: number;
  readonly defenseValue?: number;
}

/**
 * Конфигурация кэша
 */
interface CacheConfig {
  readonly maxSize: number;
  readonly ttl: number;
}

/**
 * Статистика кэша
 */
export interface CacheStats {
  readonly size: number;
  readonly hits: number;
  readonly misses: number;
  readonly hitRate: number;
}

@Injectable()
export class CardValueCacheService {
  private readonly logger = new Logger(CardValueCacheService.name);
  private readonly cache = new Map<string, CardValueEntry>();
  private readonly lruList: string[] = [];
  private hits = 0;
  private misses = 0;

  private readonly config: CacheConfig = {
    maxSize: 500, // Максимальное количество карт в кэше
    ttl: 10000, // 10 секунд TTL
  };

  constructor(private readonly metrics: MetricsService) {
    // Запускаем периодическую очистку каждые 30 секунд
    setInterval(() => this.cleanup(), 30000);
  }

  /**
   * Получить значение атаки карты
   */
  getAttackValue(cardId: string): number | undefined {
    const entry = this.cache.get(cardId);

    if (!entry) {
      this.misses++;
      this.metrics.incrementPathCacheOperation('card_value', 'miss');
      return undefined;
    }

    // Проверяем TTL
    if (Date.now() - entry.timestamp > this.config.ttl) {
      this.cache.delete(cardId);
      this.removeFromLru(cardId);
      this.misses++;
      this.metrics.incrementPathCacheOperation('card_value', 'miss');
      return undefined;
    }

    // Обновляем LRU
    this.updateLru(cardId);
    this.hits++;
    this.metrics.incrementPathCacheOperation('card_value', 'hit');
    return entry.attackValue;
  }

  /**
   * Получить значение защиты карты
   */
  getDefenseValue(cardId: string): number | undefined {
    const entry = this.cache.get(cardId);

    if (!entry) {
      this.misses++;
      this.metrics.incrementPathCacheOperation('card_value', 'miss');
      return undefined;
    }

    if (Date.now() - entry.timestamp > this.config.ttl) {
      this.cache.delete(cardId);
      this.removeFromLru(cardId);
      this.misses++;
      this.metrics.incrementPathCacheOperation('card_value', 'miss');
      return undefined;
    }

    this.updateLru(cardId);
    this.hits++;
    this.metrics.incrementPathCacheOperation('card_value', 'hit');
    return entry.defenseValue;
  }

  /**
   * Установить значения карты
   */
  set(
    cardId: string,
    values: {
      readonly attackValue?: number;
      readonly defenseValue?: number;
      readonly effects?: readonly string[];
    },
  ): void {
    // Проверяем размер кэша
    if (this.cache.size >= this.config.maxSize && !this.cache.has(cardId)) {
      // Удаляем самый старый элемент (LRU)
      const oldest = this.lruList.shift();
      if (oldest) {
        this.cache.delete(oldest);
      }
    }

    const entry: CardValueEntry = {
      attackValue: values.attackValue,
      defenseValue: values.defenseValue,
      effects: values.effects ?? [],
      timestamp: Date.now(),
    };

    this.cache.set(cardId, entry);

    if (!this.lruList.includes(cardId)) {
      this.lruList.push(cardId);
    }

    // Обновляем метрику размера кэша
    this.metrics.setPathCacheSize('card_value', this.cache.size);
  }

  /**
   * Batch получение значений карт
   * Оптимизировано для получения значений нескольких карт за один раз
   */
  batchGet(requests: readonly BatchCardValueRequest[]): readonly BatchCardValueResult[] {
    const results: BatchCardValueResult[] = [];

    for (const request of requests) {
      const entry = this.cache.get(request.cardId);

      if (entry && Date.now() - entry.timestamp <= this.config.ttl) {
        this.hits++;
        this.updateLru(request.cardId);
        results.push({
          cardId: request.cardId,
          attackValue: entry.attackValue,
          defenseValue: entry.defenseValue,
        });
      } else {
        this.misses++;
        // Если в кэше нет, ищем в состоянии
        const card = this.findCardInState(request.state, request.cardId);
        if (card) {
          this.set(request.cardId, {
            attackValue: card.attackValue,
            defenseValue: card.defenseValue,
            effects: card.effects?.map((e: any) => e.id) ?? [],
          });
          results.push({
            cardId: request.cardId,
            attackValue: card.attackValue,
            defenseValue: card.defenseValue,
          });
        } else {
          results.push({ cardId: request.cardId });
        }
      }
    }

    return results;
  }

  /**
   * Инвалидировать кэш для конкретной карты
   */
  invalidate(cardId: string): void {
    if (this.cache.delete(cardId)) {
      this.removeFromLru(cardId);
      this.metrics.incrementPathCacheOperation('card_value', 'invalidate');
      this.metrics.setPathCacheSize('card_value', this.cache.size);
    }
  }

  /**
   * Инвалидировать весь кэш
   */
  invalidateAll(): void {
    const size = this.cache.size;
    this.cache.clear();
    this.lruList.length = 0;
    this.metrics.incrementPathCacheOperation('card_value', 'invalidate');
    this.metrics.setPathCacheSize('card_value', 0);
    this.logger.debug(`Invalidated entire card value cache (${size} entries)`);
  }

  /**
   * Получить статистику кэша
   */
  getStats(): CacheStats {
    const total = this.hits + this.misses;
    return {
      size: this.cache.size,
      hits: this.hits,
      misses: this.misses,
      hitRate: total > 0 ? this.hits / total : 0,
    };
  }

  /**
   * Сбросить статистику
   */
  resetStats(): void {
    this.hits = 0;
    this.misses = 0;
  }

  /**
   * Очистить устаревшие записи
   */
  private cleanup(): void {
    const now = Date.now();
    let cleaned = 0;

    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > this.config.ttl) {
        this.cache.delete(key);
        this.removeFromLru(key);
        cleaned++;
      }
    }

    if (cleaned > 0) {
      this.metrics.setPathCacheSize('card_value', this.cache.size);
      this.logger.debug(`Cleaned up ${cleaned} expired card value cache entries`);
    }

    // Логируем статистику периодически
    const stats = this.getStats();
    if (stats.size > 0) {
      this.logger.debug(
        `Card value cache stats: size=${stats.size}, hits=${stats.hits}, misses=${stats.misses}, hitRate=${(stats.hitRate * 100).toFixed(1)}%`,
      );
    }
  }

  /**
   * Обновить LRU список
   */
  private updateLru(cardId: string): void {
    const index = this.lruList.indexOf(cardId);
    if (index !== -1) {
      this.lruList.splice(index, 1);
    }
    this.lruList.push(cardId);
  }

  /**
   * Удалить из LRU списка
   */
  private removeFromLru(cardId: string): void {
    const index = this.lruList.indexOf(cardId);
    if (index !== -1) {
      this.lruList.splice(index, 1);
    }
  }

  /**
   * Найти карту в состоянии игры
   */
  private findCardInState(state: any, cardId: string): any {
    // Поиск в руках всех игроков
    if (state.handZones) {
      for (const handZone of Object.values(state.handZones)) {
        const card = (handZone as any).cards?.find((c: any) => c.id === cardId);
        if (card) return card;
      }
    }

    // Поиск в колодах
    if (state.decks) {
      for (const deck of Object.values(state.decks)) {
        const card = (deck as any).cards?.find((c: any) => c.id === cardId);
        if (card) return card;
      }
    }

    // Поиск в сбросах
    if (state.discardPiles) {
      for (const discardPile of Object.values(state.discardPiles)) {
        const card = (discardPile as any).find?.((c: any) => c.id === cardId);
        if (card) return card;
      }
    }

    return null;
  }
}
