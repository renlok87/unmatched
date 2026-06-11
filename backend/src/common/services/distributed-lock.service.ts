/**
 * DistributedLockService - сервис распределённых блокировок
 *
 * Обеспечивает безопасную одновременную работу с состоянием игры
 * за счёт распределённых блокировок на базе Redis.
 *
 * TTL увеличен до 10 сек для защиты от GC pause и других задержек.
 */

import { Injectable, Logger } from '@nestjs/common';
import { RedisService } from '../../redis/redis.service';

/**
 * Распределённая блокировка
 */
export interface DistributedLock {
  key: string;
  token: string;
  acquiredAt: number;
  ttl: number;
}

/**
 * Опции приобретения блокировки
 */
export interface AcquireLockOptions {
  ttl?: number; // TTL в мс (дефолт 10000)
  retryCount?: number; // Количество попыток (дефолт 0 - без повторов)
  retryDelay?: number; // Задержка между попытками в мс (дефолт 100)
}

/**
 * Результат попытки приобретения блокировки
 */
export interface AcquireResult {
  success: boolean;
  lock?: DistributedLock;
  attempt?: number;
}

/**
 * Статистика блокировок
 */
export interface LockStats {
  totalAcquired: number;
  totalReleased: number;
  totalExpired: number;
  totalFailed: number;
  currentActive: number;
  avgHoldTime: number;
}

@Injectable()
export class DistributedLockService {
  private readonly logger = new Logger(DistributedLockService.name);

  // Префикс для ключей блокировок
  private readonly LOCK_PREFIX = 'lock:';

  // Дефолтный TTL = 10 сек (защита от GC pause)
  private readonly DEFAULT_TTL = 10000;

  // Статистика
  private stats: Map<string, LockStats> = new Map();
  private activeLocks: Map<string, DistributedLock> = new Map();

  constructor(private readonly redis: RedisService) {}

  /**
   * Приобрести блокировку игры
   *
   * @param gameId - ID игры
   * @param ttl - TTL в мс (дефолт 10000)
   * @returns Блокировка или null если не удалось получить
   */
  async acquireGameLock(
    gameId: string,
    ttl: number = this.DEFAULT_TTL,
  ): Promise<DistributedLock | null> {
    return this.acquireLock(`game:${gameId}`, ttl);
  }

  /**
   * Приобрести блокировку с опциями
   */
  async acquireLock(
    key: string,
    ttl: number = this.DEFAULT_TTL,
    options: AcquireLockOptions = {},
  ): Promise<DistributedLock | null> {
    const lockKey = this.getLockKey(key);
    const token = this.generateToken();
    const acquiredAt = Date.now();

    // Пытаемся установить блокировку с NX (только если ключа нет)
    // PX указывает TTL в миллисекундах
    const result = await (this.redis as any).client.set(lockKey, token, 'PX', ttl, 'NX');

    if (result === 'OK') {
      const lock: DistributedLock = {
        key: lockKey,
        token,
        acquiredAt,
        ttl,
      };

      this.activeLocks.set(lockKey, lock);
      this.updateStats(key, 'acquired');

      this.logger.debug(`Acquired lock: ${key} (token: ${token.slice(0, 8)}...)`);
      return lock;
    }

    // Если указаны повторы - пытаемся несколько раз
    const retryCount = options.retryCount || 0;
    if (retryCount > 0) {
      const retryDelay = options.retryDelay || 100;

      for (let i = 0; i < retryCount; i++) {
        await this.sleep(retryDelay);

        const retryResult = await (this.redis as any).client.set(lockKey, token, 'PX', ttl, 'NX');

        if (retryResult === 'OK') {
          const lock: DistributedLock = {
            key: lockKey,
            token,
            acquiredAt,
            ttl,
          };

          this.activeLocks.set(lockKey, lock);
          this.updateStats(key, 'acquired');

          this.logger.debug(`Acquired lock on attempt ${i + 1}: ${key}`);
          return lock;
        }
      }
    }

    this.updateStats(key, 'failed');
    this.logger.warn(`Failed to acquire lock: ${key}`);
    return null;
  }

  /**
   * Освободить блокировку
   *
   * @param lock - Блокировка для освобождения
   * @returns true если успешно освобождена
   */
  async releaseLock(lock: DistributedLock): Promise<void> {
    const released = await this.releaseLockSafe(lock.key, lock.token);

    if (released) {
      this.activeLocks.delete(lock.key);
      this.updateStats(lock.key, 'released');
      this.logger.debug(`Released lock: ${lock.key}`);
    } else {
      this.logger.warn(`Lock already expired or released: ${lock.key}`);
      this.updateStats(lock.key, 'expired');
    }
  }

  /**
   * Безопасное освобождение блокировки (только если токен совпадает)
   * Использует Lua скрипт для атомарности
   */
  private async releaseLockSafe(key: string, token: string): Promise<boolean> {
    const luaScript = `
      if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
      else
        return 0
      end
    `;

    const result = await (this.redis as any).client.eval(luaScript, 1, key, token);

    return result === 1;
  }

  /**
   * Выполнить функцию под блокировкой
   *
   * @param gameId - ID игры
   * @param fn - Функция для выполнения
   * @returns Результат функции
   */
  async withLock<T>(gameId: string, fn: () => Promise<T>): Promise<T> {
    return this.withLockOptions(`game:${gameId}`, fn, { ttl: this.DEFAULT_TTL });
  }

  /**
   * Выполнить функцию под блокировкой с опциями
   */
  async withLockOptions<T>(
    key: string,
    fn: () => Promise<T>,
    options: AcquireLockOptions = {},
  ): Promise<T> {
    const lock = await this.acquireLock(key, options.ttl, options);

    if (!lock) {
      throw new Error(`Could not acquire lock: ${key}`);
    }

    try {
      return await fn();
    } finally {
      await this.releaseLock(lock);
    }
  }

  /**
   * Проверить, заблокирована ли игра
   */
  async isGameLocked(gameId: string): Promise<boolean> {
    return this.isLocked(`game:${gameId}`);
  }

  /**
   * Проверить, заблокирован ли ключ
   */
  async isLocked(key: string): Promise<boolean> {
    const lockKey = this.getLockKey(key);
    const exists = await this.redis.exists(lockKey);
    return exists === 1;
  }

  /**
   * Продлить блокировку
   *
   * @param lock - Блокировка для продления
   * @param newTtl - Новый TTL в мс (опционально)
   * @returns true если успешно продлена
   */
  async extendLock(lock: DistributedLock, newTtl?: number): Promise<boolean> {
    const ttl = newTtl || lock.ttl;

    const luaScript = `
      if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("pexpire", KEYS[1], ARGV[2])
      else
        return 0
      end
    `;

    const result = await (this.redis as any).client.eval(luaScript, 1, lock.key, lock.token, ttl);

    if (result === 1) {
      lock.ttl = ttl;
      this.logger.debug(`Extended lock: ${lock.key} by ${ttl}ms`);
      return true;
    }

    return false;
  }

  /**
   * Получить информацию о блокировке
   */
  async getLockInfo(
    key: string,
  ): Promise<{ locked: boolean; ttl?: number; token?: string } | null> {
    const lockKey = this.getLockKey(key);
    const exists = await this.redis.exists(lockKey);

    if (!exists) {
      return { locked: false };
    }

    const token = await this.redis.get(lockKey);
    const ttl = await (this.redis as any).client.pttl(lockKey);

    return {
      locked: true,
      token: token || undefined,
      ttl: ttl > 0 ? ttl : undefined,
    };
  }

  /**
   * Получить статистику по блокировкам
   */
  getStats(key?: string): LockStats | Map<string, LockStats> {
    if (key) {
      return (
        this.stats.get(key) || {
          totalAcquired: 0,
          totalReleased: 0,
          totalExpired: 0,
          totalFailed: 0,
          currentActive: 0,
          avgHoldTime: 0,
        }
      );
    }

    return this.stats;
  }

  /**
   * Сбросить статистику
   */
  resetStats(key?: string): void {
    if (key) {
      this.stats.delete(key);
    } else {
      this.stats.clear();
    }
  }

  /**
   * Принудительно освободить блокировку (для администрирования)
   */
  async forceRelease(key: string): Promise<boolean> {
    const lockKey = this.getLockKey(key);
    const result = await this.redis.del(lockKey);

    if (result > 0) {
      this.activeLocks.delete(lockKey);
      this.logger.warn(`Force released lock: ${key}`);
      return true;
    }

    return false;
  }

  /**
   * Получить все активные блокировки
   */
  getActiveLocks(): DistributedLock[] {
    return Array.from(this.activeLocks.values());
  }

  /**
   * Сгенерировать уникальный токен для блокировки
   */
  private generateToken(): string {
    return `${Date.now()}-${Math.random().toString(36).slice(2)}-${process.pid || 'worker'}`;
  }

  /**
   * Получить полный ключ блокировки
   */
  private getLockKey(key: string): string {
    return `${this.LOCK_PREFIX}${key}`;
  }

  /**
   * Обновить статистику
   */
  private updateStats(key: string, action: 'acquired' | 'released' | 'expired' | 'failed'): void {
    let stats = this.stats.get(key);
    if (!stats) {
      stats = {
        totalAcquired: 0,
        totalReleased: 0,
        totalExpired: 0,
        totalFailed: 0,
        currentActive: 0,
        avgHoldTime: 0,
      };
      this.stats.set(key, stats);
    }

    switch (action) {
      case 'acquired':
        stats.totalAcquired++;
        stats.currentActive++;
        break;
      case 'released':
        stats.totalReleased++;
        stats.currentActive--;
        break;
      case 'expired':
        stats.totalExpired++;
        stats.currentActive--;
        break;
      case 'failed':
        stats.totalFailed++;
        break;
    }
  }

  /**
   * Задержка выполнения
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
