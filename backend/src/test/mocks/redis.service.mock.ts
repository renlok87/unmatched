/**
 * Mock Redis Service
 *
 * Используется для тестирования без реального Redis
 */

export interface IRedisService {
  get(key: string): Promise<string | null>;
  set(key: string, value: string): Promise<'OK' | null>;
  setex(key: string, seconds: number, value: string): Promise<'OK' | null>;
  del(key: string): Promise<number>;
  exists(key: string): Promise<number>;
  getJson<T>(key: string): Promise<T | null>;
  setJson(key: string, value: any): Promise<'OK' | null>;
  setJsonex(key: string, seconds: number, value: any): Promise<'OK' | null>;
  getOrSet<T>(key: string, factory: () => Promise<T>, ttl: number): Promise<T>;
}

/**
 * Mock реализация RedisService
 */
export class MockRedisService implements IRedisService {
  private store = new Map<string, { value: string; expiry?: number }>();

  async get(key: string): Promise<string | null> {
    const item = this.store.get(key);
    if (!item) return null;
    if (item.expiry && item.expiry < Date.now()) {
      this.store.delete(key);
      return null;
    }
    return item.value;
  }

  async set(key: string, value: string): Promise<'OK' | null> {
    this.store.set(key, { value });
    return 'OK';
  }

  async setex(key: string, seconds: number, value: string): Promise<'OK' | null> {
    this.store.set(key, {
      value,
      expiry: Date.now() + seconds * 1000,
    });
    return 'OK';
  }

  async del(key: string): Promise<number> {
    const existed = this.store.has(key);
    this.store.delete(key);
    return existed ? 1 : 0;
  }

  async exists(key: string): Promise<number> {
    const item = this.store.get(key);
    if (!item) return 0;
    if (item.expiry && item.expiry < Date.now()) {
      this.store.delete(key);
      return 0;
    }
    return 1;
  }

  async getJson<T>(key: string): Promise<T | null> {
    const value = await this.get(key);
    if (!value) return null;
    try {
      return JSON.parse(value) as T;
    } catch {
      return null;
    }
  }

  async setJson(key: string, value: any): Promise<'OK' | null> {
    return this.set(key, JSON.stringify(value));
  }

  async setJsonex(key: string, seconds: number, value: any): Promise<'OK' | null> {
    return this.setex(key, seconds, JSON.stringify(value));
  }

  async getOrSet<T>(key: string, factory: () => Promise<T>, ttl: number): Promise<T> {
    const cached = await this.getJson<T>(key);
    if (cached !== null) return cached;

    const value = await factory();
    await this.setJsonex(key, ttl, value);
    return value;
  }

  // Утилиты для тестов

  clear(): void {
    this.store.clear();
  }

  size(): number {
    return this.store.size;
  }

  keys(): string[] {
    return Array.from(this.store.keys());
  }
}
