/**
 * Tag-based Cache Invalidation
 *
 * Позволяет инвалидировать несколько кеш-ключей одним тегом.
 * Полезно для инвалидации всех кешей пользователя, игры и т.д.
 *
 * Пример:
 * - Кеш игры имеет теги: ['game', 'game:123', 'user:456']
 * - При изменении игры 123, инвалидировать все ключи с тегом 'game:123'
 * - При выходе пользователя 456, инвалидировать все ключи с тегом 'user:456'
 */

import { Injectable, Logger } from '@nestjs/common';
import { RedisService } from '../redis/redis.service';

const TAG_PREFIX = 'cache:tag:';
const KEY_PREFIX = 'cache:key:';
const META_PREFIX = 'cache:meta:';

@Injectable()
export class CacheTagsService {
  private readonly logger = new Logger(CacheTagsService.name);

  constructor(private redis: RedisService) {}

  /**
   * Сохранить значение с тегами
   *
   * @param key Ключ кеша
   * @param value Значение
   * @param ttl Время жизни в секундах
   * @param tags Теги для инвалидации
   */
  async setWithTag<T>(key: string, value: T, ttl: number, tags: string[]): Promise<void> {
    const fullKey = KEY_PREFIX + key;

    // Сохраняем значение
    await this.redis.setJsonex(fullKey, ttl, value);

    // Добавляем ключ в каждый тег
    for (const tag of tags) {
      await this.redis.sadd(TAG_PREFIX + tag, fullKey);
      // Тег живёт дольше ключа (+ 1 минута)
      await this.redis.expire(TAG_PREFIX + tag, ttl + 60);
    }

    // Сохраняем метаданные о тегах ключа
    await this.redis.setJsonex(META_PREFIX + fullKey, ttl + 60, { tags });

    this.logger.debug(`Cache set with tags: ${key}, tags: [${tags.join(', ')}]`);
  }

  /**
   * Инвалидировать все ключи с тегом
   *
   * @param tag Тег для инвалидации
   * @returns Количество инвалидированных ключей
   */
  async invalidateTag(tag: string): Promise<number> {
    const tagKey = TAG_PREFIX + tag;
    const keys = await this.redis.smembers(tagKey);

    if (keys.length === 0) {
      return 0;
    }

    // Удаляем все ключи
    for (const key of keys) {
      await this.redis.del(key);
      // Удаляем метаданные
      await this.redis.del(META_PREFIX + key);
    }

    // Удаляем тег
    await this.redis.del(tagKey);

    this.logger.debug(`Invalidated tag: ${tag}, keys: ${keys.length}`);

    return keys.length;
  }

  /**
   * Инвалидировать несколько тегов
   *
   * @param tags Теги для инвалидации
   * @returns Общее количество инвалидированных ключей
   */
  async invalidateTags(tags: string[]): Promise<number> {
    let total = 0;
    for (const tag of tags) {
      total += await this.invalidateTag(tag);
    }
    return total;
  }

  /**
   * Получить все ключи с тегом (без удаления)
   *
   * @param tag Тег
   * @returns Массив ключей
   */
  async getKeysByTag(tag: string): Promise<string[]> {
    const tagKey = TAG_PREFIX + tag;
    return await this.redis.smembers(tagKey);
  }

  /**
   * Проверить, существует ли ключ в теге
   *
   * @param tag Тег
   * @param key Ключ
   */
  async isKeyInTag(tag: string, key: string): Promise<boolean> {
    const fullKey = KEY_PREFIX + key;
    const tagKey = TAG_PREFIX + tag;
    const result = await this.redis.sismember(tagKey, fullKey);
    return result === 1;
  }

  /**
   * Удалить ключ из всех тегов
   *
   * @param key Ключ
   */
  async removeFromTags(key: string): Promise<void> {
    const fullKey = KEY_PREFIX + key;

    // Получаем метаданные о тегах
    const meta = await this.redis.getJson<{ tags: string[] }>(META_PREFIX + fullKey);
    if (!meta?.tags) return;

    // Удаляем ключ из каждого тега
    for (const tag of meta.tags) {
      await this.redis.srem(TAG_PREFIX + tag, fullKey);
    }

    // Удаляем метаданные
    await this.redis.del(META_PREFIX + fullKey);
  }

  /**
   * Очистить все теги (для admin/debug)
   */
  async flushAllTags(): Promise<number> {
    // Находим все ключи тегов
    // В production это должно быть ограничено
    const pattern = TAG_PREFIX + '*';
    // Это требует SCAN для production, но для MVP используем простой подход

    this.logger.warn('Flushing all cache tags');
    return 0; // TODO: Implement with SCAN
  }
}
