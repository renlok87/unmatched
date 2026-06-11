import { Injectable, Logger, OnModuleInit, OnModuleDestroy } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import Redis from 'ioredis';

interface Lock {
  key: string;
  timeout: NodeJS.Timeout;
}

@Injectable()
export class RedisService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(RedisService.name);
  private client: Redis | null = null;
  private publisher: Redis | null = null;
  private subscriber: Redis | null = null;
  private connected = false;

  constructor(private configService: ConfigService) {}

  async onModuleInit() {
    const host =
      this.configService.get<string>('REDIS_HOST') ||
      this.configService.get<string>('redis.host') ||
      'localhost';
    const port =
      this.configService.get<number>('REDIS_PORT') ||
      this.configService.get<number>('redis.port') ||
      6379;
    const password =
      this.configService.get<string>('REDIS_PASSWORD') ||
      this.configService.get<string>('redis.password');

    const redisOptions = {
      host,
      port,
      password: password || undefined,
      connectTimeout: 1000,
      maxRetriesPerRequest: null as any,
      retryStrategy: (): number | null => {
        return null;
      },
      lazyConnect: true,
    };

    try {
      this.client = new Redis(redisOptions);
      this.publisher = new Redis(redisOptions);
      this.subscriber = new Redis(redisOptions);

      this.client.on('error', (err) => {
        this.logger.warn(`Redis client error: ${err.message}`);
      });
      this.publisher.on('error', (err) => {
        this.logger.warn(`Redis publisher error: ${err.message}`);
      });
      this.subscriber.on('error', (err) => {
        this.logger.warn(`Redis subscriber error: ${err.message}`);
      });

      await Promise.race([
        Promise.all([
          this.client.connect().then(() => {
            this.logger.log('Redis client connected');
            this.connected = true;
          }),
          this.publisher.connect().then(() => {
            this.logger.log('Redis publisher connected');
          }),
          this.subscriber.connect().then(() => {
            this.logger.log('Redis subscriber connected');
          }),
        ]),
        new Promise<void>((_, reject) => 
          setTimeout(() => reject(new Error('Redis connection timeout')), 2000)
        ),
      ]);
    } catch (error) {
      this.logger.warn('Redis connection failed or timed out. Starting without Redis.');
      this.client = null;
      this.publisher = null;
      this.subscriber = null;
      this.connected = false;
    }
  }

  async onModuleDestroy() {
    if (this.client) await this.client.quit();
    if (this.publisher) await this.publisher.quit();
    if (this.subscriber) await this.subscriber.quit();
    this.logger.log('Redis connections closed');
  }

  private ensureConnected() {
    if (!this.client || !this.connected) {
      throw new Error('Redis is not connected');
    }
  }

  async get(key: string): Promise<string | null> {
    if (!this.client) return null;
    return this.client.get(key);
  }

  async set(key: string, value: string): Promise<'OK' | null> {
    if (!this.client) return null;
    return this.client.set(key, value);
  }

  async setex(key: string, seconds: number, value: string): Promise<'OK' | null> {
    if (!this.client) return null;
    return this.client.setex(key, seconds, value);
  }

  async del(key: string): Promise<number> {
    if (!this.client) return 0;
    return this.client.del(key);
  }

  async exists(key: string): Promise<number> {
    if (!this.client) return 0;
    return this.client.exists(key);
  }

  async expire(key: string, seconds: number): Promise<number> {
    if (!this.client) return 0;
    return this.client.expire(key, seconds);
  }

  async getJson<T = any>(key: string): Promise<T | null> {
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

  async getOrSet<T>(
    key: string,
    factory: () => Promise<T>,
    ttl: number,
    lockTtl: number = 5000,
  ): Promise<T> {
    const cached = await this.getJson<T>(key);
    if (cached !== null) {
      return cached;
    }

    const lockKey = `lock:${key}`;
    const lock = await this.acquireLock(lockKey, lockTtl);

    if (lock) {
      try {
        const doubleCheck = await this.getJson<T>(key);
        if (doubleCheck !== null) {
          return doubleCheck;
        }

        const value = await factory();
        await this.setJsonex(key, ttl, value);

        return value;
      } finally {
        await this.releaseLock(lock);
      }
    }

    await this.sleep(100);
    return this.getOrSet(key, factory, ttl, lockTtl);
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async publish(channel: string, message: any): Promise<number> {
    if (!this.publisher) return 0;
    const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
    return this.publisher.publish(channel, messageStr);
  }

  async subscribe(channel: string, callback: (message: string) => void): Promise<void> {
    if (!this.subscriber) return;
    await this.subscriber.subscribe(channel);
    this.subscriber.on('message', (ch, message) => {
      if (ch === channel) {
        callback(message);
      }
    });
  }

  async unsubscribe(channel: string): Promise<void> {
    if (!this.subscriber) return;
    await this.subscriber.unsubscribe(channel);
  }

  async acquireLock(lockKey: string, ttl: number = 10000): Promise<Lock | null> {
    if (!this.client) return null;
    const lockValue = `${Date.now()}-${Math.random()}`;
    const acquired = await this.client.set(lockKey, lockValue, 'PX', ttl, 'NX');

    if (acquired === 'OK') {
      const timeout = setTimeout(async () => {
        await this.releaseLock({ key: lockKey, timeout: null as any });
      }, ttl);

      return { key: lockKey, timeout };
    }

    return null;
  }

  async releaseLock(lock: Lock): Promise<void> {
    if (lock.timeout) {
      clearTimeout(lock.timeout);
    }
    if (this.client) {
      await this.client.del(lock.key);
    }
  }

  async withLock<T>(lockKey: string, fn: () => Promise<T>, ttl: number = 10000): Promise<T> {
    const lock = await this.acquireLock(lockKey, ttl);

    if (!lock) {
      throw new Error(`Could not acquire lock: ${lockKey}`);
    }

    try {
      return await fn();
    } finally {
      await this.releaseLock(lock);
    }
  }

  async zadd(key: string, score: string | number, member: string): Promise<number> {
    if (!this.client) return 0;
    return this.client.zadd(key, score, member);
  }

  async zrem(key: string, member: string): Promise<number> {
    if (!this.client) return 0;
    return this.client.zrem(key, member);
  }

  async zremMany(key: string, ...members: string[]): Promise<number> {
    if (!this.client || members.length === 0) return 0;
    return this.client.zrem(key, ...members);
  }

  async zrange(key: string, start: number, stop: number, withScores = false): Promise<string[]> {
    if (!this.client) return [];
    if (withScores) {
      return this.client.zrange(key, start, stop, 'WITHSCORES');
    }
    return this.client.zrange(key, start, stop);
  }

  async zrangebyscore(
    key: string,
    min: number,
    max: number,
    withScores = false,
  ): Promise<string[]> {
    if (!this.client) return [];
    if (withScores) {
      return this.client.zrangebyscore(key, min, max, 'WITHSCORES');
    }
    return this.client.zrangebyscore(key, min, max);
  }

  async zcard(key: string): Promise<number> {
    if (!this.client) return 0;
    return this.client.zcard(key);
  }

  async zscore(key: string, member: string): Promise<number | null> {
    if (!this.client) return null;
    const score = await this.client.zscore(key, member);
    return score ? parseFloat(score) : null;
  }

  async zrevrange(key: string, start: number, stop: number, withScores = false): Promise<string[]> {
    if (!this.client) return [];
    if (withScores) {
      return this.client.zrevrange(key, start, stop, 'WITHSCORES');
    }
    return this.client.zrevrange(key, start, stop);
  }

  async zrevrank(key: string, member: string): Promise<number | null> {
    if (!this.client) return null;
    return this.client.zrevrank(key, member);
  }

  async zrank(key: string, member: string): Promise<number | null> {
    if (!this.client) return null;
    return this.client.zrank(key, member);
  }

  multi() {
    if (!this.client) return null;
    return this.client.multi();
  }

  async hset(key: string, field: string | Record<string, string>, value?: string): Promise<number> {
    if (!this.client) return 0;
    if (typeof field === 'string' && value !== undefined) {
      return this.client.hset(key, field, value);
    } else if (typeof field === 'object') {
      return this.client.hset(key, field);
    }
    return 0;
  }

  async hgetall(key: string): Promise<Record<string, string>> {
    if (!this.client) return {};
    return this.client.hgetall(key);
  }

  async hget(key: string, field: string): Promise<string | null> {
    if (!this.client) return null;
    return this.client.hget(key, field);
  }

  async sadd(key: string, ...members: string[]): Promise<number> {
    if (!this.client) return 0;
    return this.client.sadd(key, ...members);
  }

  async srem(key: string, ...members: string[]): Promise<number> {
    if (!this.client) return 0;
    return this.client.srem(key, ...members);
  }

  async smembers(key: string): Promise<string[]> {
    if (!this.client) return [];
    return this.client.smembers(key);
  }

  async sismember(key: string, member: string): Promise<number> {
    if (!this.client) return 0;
    return this.client.sismember(key, member);
  }

  async addToBlacklist(token: string, ttl: number): Promise<void> {
    await this.setex(`blacklist:${token}`, ttl, '1');
  }

  async isBlacklisted(token: string): Promise<boolean> {
    return (await this.exists(`blacklist:${token}`)) === 1;
  }

  async getUserFromCache(userId: string): Promise<any | null> {
    return this.getJson(`user:${userId}`);
  }

  async cacheUser(userId: string, user: any, ttl: number = 300): Promise<void> {
    await this.setJsonex(`user:${userId}`, ttl, user);
  }

  async invalidateUserCache(userId: string): Promise<void> {
    await this.del(`user:${userId}`);
  }

  async ping(): Promise<string> {
    if (!this.client) return 'PONG';
    return this.client.ping();
  }

  async flushDb(): Promise<'OK'> {
    if (!this.client || process.env.NODE_ENV === 'production') {
      throw new Error('Cannot flush database in production!');
    }
    return this.client.flushdb();
  }
}