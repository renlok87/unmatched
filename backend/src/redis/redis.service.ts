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
  private client: Redis;
  private publisher: Redis;
  private subscriber: Redis;

  constructor(private configService: ConfigService) {}

  async onModuleInit() {
    const host = this.configService.get<string>('redis.host');
    const port = this.configService.get<number>('redis.port');
    const password = this.configService.get<string>('redis.password');

    const redisOptions = {
      host,
      port,
      password: password || undefined,
      retryStrategy: (times: number) => {
        const delay = Math.min(times * 50, 2000);
        return delay;
      },
      maxRetriesPerRequest: 3,
    };

    this.client = new Redis(redisOptions);
    this.publisher = new Redis(redisOptions);
    this.subscriber = new Redis(redisOptions);

    // Wait for connection
    await Promise.all([
      new Promise<void>((resolve) => {
        this.client.once('connect', () => {
          this.logger.log('Redis client connected');
          resolve();
        });
      }),
      new Promise<void>((resolve) => {
        this.publisher.once('connect', () => {
          this.logger.log('Redis publisher connected');
          resolve();
        });
      }),
      new Promise<void>((resolve) => {
        this.subscriber.once('connect', () => {
          this.logger.log('Redis subscriber connected');
          resolve();
        });
      }),
    ]);
  }

  async onModuleDestroy() {
    await this.client.quit();
    await this.publisher.quit();
    await this.subscriber.quit();
    this.logger.log('Redis connections closed');
  }

  // Basic operations
  async get(key: string): Promise<string | null> {
    return this.client.get(key);
  }

  async set(key: string, value: string): Promise<'OK' | null> {
    return this.client.set(key, value);
  }

  async setex(key: string, seconds: number, value: string): Promise<'OK' | null> {
    return this.client.setex(key, seconds, value);
  }

  async del(key: string): Promise<number> {
    return this.client.del(key);
  }

  async exists(key: string): Promise<number> {
    return this.client.exists(key);
  }

  async expire(key: string, seconds: number): Promise<number> {
    return this.client.expire(key, seconds);
  }

  // JSON operations
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

  // Pub/Sub
  async publish(channel: string, message: any): Promise<number> {
    const messageStr = typeof message === 'string' ? message : JSON.stringify(message);
    return this.publisher.publish(channel, messageStr);
  }

  async subscribe(channel: string, callback: (message: string) => void): Promise<void> {
    await this.subscriber.subscribe(channel);
    this.subscriber.on('message', (ch, message) => {
      if (ch === channel) {
        callback(message);
      }
    });
  }

  async unsubscribe(channel: string): Promise<void> {
    await this.subscriber.unsubscribe(channel);
  }

  // Distributed locks
  async acquireLock(lockKey: string, ttl: number = 10000): Promise<Lock | null> {
    const lockValue = `${Date.now()}-${Math.random()}`;
    const acquired = await this.client.set(lockKey, lockValue, 'PX', ttl, 'NX');

    if (acquired === 'OK') {
      const timeout = setTimeout(async () => {
        // Auto-release after TTL (though Redis will do this automatically)
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
    await this.client.del(lock.key);
  }

  async withLock<T>(
    lockKey: string,
    fn: () => Promise<T>,
    ttl: number = 10000,
  ): Promise<T> {
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

  // Sorted Sets (for queues)
  async zadd(key: string, score: number, member: string): Promise<number> {
    return this.client.zadd(key, score, member);
  }

  async zrem(key: string, member: string): Promise<number> {
    return this.client.zrem(key, member);
  }

  async zrange(key: string, start: number, stop: number, withScores = false): Promise<string[]> {
    return this.client.zrange(key, start, stop, 'WITHSCORES');
  }

  async zrangebyscore(
    key: string,
    min: number,
    max: number,
  ): Promise<string[]> {
    return this.client.zrangebyscore(key, min, max);
  }

  async zcard(key: string): Promise<number> {
    return this.client.zcard(key);
  }

  // Sets (for presence)
  async sadd(key: string, ...members: string[]): Promise<number> {
    return this.client.sadd(key, ...members);
  }

  async srem(key: string, ...members: string[]): Promise<number> {
    return this.client.srem(key, ...members);
  }

  async smembers(key: string): Promise<string[]> {
    return this.client.smembers(key);
  }

  async sismember(key: string, member: string): Promise<number> {
    return this.client.sismember(key, member);
  }

  // Token blacklist for logout
  async addToBlacklist(token: string, ttl: number): Promise<void> {
    await this.setex(`blacklist:${token}`, ttl, '1');
  }

  async isBlacklisted(token: string): Promise<boolean> {
    return (await this.exists(`blacklist:${token}`)) === 1;
  }

  // User cache
  async getUserFromCache(userId: string): Promise<any | null> {
    return this.getJson(`user:${userId}`);
  }

  async cacheUser(userId: string, user: any, ttl: number = 300): Promise<void> {
    await this.setJsonex(`user:${userId}`, ttl, user);
  }

  async invalidateUserCache(userId: string): Promise<void> {
    await this.del(`user:${userId}`);
  }

  // Health check
  async ping(): Promise<string> {
    return this.client.ping();
  }

  async flushDb(): Promise<'OK'> {
    if (process.env.NODE_ENV === 'production') {
      throw new Error('Cannot flush database in production!');
    }
    return this.client.flushdb();
  }
}
