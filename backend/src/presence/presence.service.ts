import { Injectable, Logger } from '@nestjs/common';
import { RedisService } from '../redis/redis.service';
import { PresenceStatus, PresenceData } from './models/presence.model';

const PRESENCE_TTL = 300;
const ONLINE_ZSET_KEY = 'presence:online';
const PRESENCE_HASH_KEY_PREFIX = 'presence:';
const PRESENCE_CHANNEL = 'presence:updates';

@Injectable()
export class PresenceService {
  private readonly logger = new Logger(PresenceService.name);

  constructor(private readonly redisService: RedisService) {}

  async updatePresence(
    userId: string,
    status: PresenceStatus,
    currentGameId?: string,
  ): Promise<PresenceData> {
    const presenceKey = `${PRESENCE_HASH_KEY_PREFIX}${userId}`;
    const lastSeenAt = Date.now();

    const presenceData: PresenceData = {
      userId,
      status,
      currentGameId,
      lastSeenAt,
    };

    try {
      await Promise.all([
        this.redisService.setJsonex(presenceKey, PRESENCE_TTL, presenceData),
        this.redisService.zadd(ONLINE_ZSET_KEY, lastSeenAt, userId),
      ]);

      await this.publishPresenceUpdate(presenceData);

      this.logger.debug(`Updated presence for user ${userId}: ${status}`);
    } catch (error) {
      this.logger.error(`Failed to update presence for user ${userId}:`, error);
    }

    return presenceData;
  }

  async getPresence(userId: string): Promise<PresenceData | null> {
    const presenceKey = `${PRESENCE_HASH_KEY_PREFIX}${userId}`;

    try {
      const presence = await this.redisService.getJson<PresenceData>(presenceKey);
      return presence;
    } catch (error) {
      this.logger.error(`Failed to get presence for user ${userId}:`, error);
      return null;
    }
  }

  async getOnlineUserIds(): Promise<string[]> {
    try {
      const onlineUsers = await this.redisService.zrange(ONLINE_ZSET_KEY, 0, -1);
      return onlineUsers;
    } catch (error) {
      this.logger.error('Failed to get online users:', error);
      return [];
    }
  }

  async getOnlineCount(): Promise<number> {
    try {
      const count = await this.redisService.zcard(ONLINE_ZSET_KEY);
      return count;
    } catch (error) {
      this.logger.error('Failed to get online count:', error);
      return 0;
    }
  }

  async removePresence(userId: string): Promise<void> {
    const presenceKey = `${PRESENCE_HASH_KEY_PREFIX}${userId}`;

    try {
      await Promise.all([
        this.redisService.del(presenceKey),
        this.redisService.zrem(ONLINE_ZSET_KEY, userId),
      ]);

      this.logger.debug(`Removed presence for user ${userId}`);
    } catch (error) {
      this.logger.error(`Failed to remove presence for user ${userId}:`, error);
    }
  }

  async getPresencesForUserIds(userIds: string[]): Promise<Map<string, PresenceData>> {
    const presenceMap = new Map<string, PresenceData>();

    try {
      const promises = userIds.map(async (userId) => {
        const presence = await this.getPresence(userId);
        if (presence) {
          presenceMap.set(userId, presence);
        }
      });

      await Promise.all(promises);
    } catch (error) {
      this.logger.error('Failed to get presences for user IDs:', error);
    }

    return presenceMap;
  }

  async cleanupExpiredPresences(): Promise<number> {
    const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;

    try {
      const expiredUsers = await this.redisService.zrangebyscore(
        ONLINE_ZSET_KEY,
        0,
        fiveMinutesAgo,
      );

      if (expiredUsers.length > 0) {
        for (const userId of expiredUsers) {
          await this.redisService.zrem(ONLINE_ZSET_KEY, userId);
        }

        for (const userId of expiredUsers) {
          await this.removePresence(userId);
        }

        this.logger.debug(`Cleaned up ${expiredUsers.length} expired presences`);
      }

      return expiredUsers.length;
    } catch (error) {
      this.logger.error('Failed to cleanup expired presences:', error);
      return 0;
    }
  }

  private async publishPresenceUpdate(presence: PresenceData): Promise<void> {
    try {
      await this.redisService.publish(PRESENCE_CHANNEL, presence);
    } catch (error) {
      this.logger.error('Failed to publish presence update:', error);
    }
  }

  async subscribeToPresenceUpdates(callback: (presence: PresenceData) => void): Promise<void> {
    try {
      await this.redisService.subscribe(PRESENCE_CHANNEL, (message) => {
        try {
          const presence = JSON.parse(message) as PresenceData;
          callback(presence);
        } catch (error) {
          this.logger.error('Failed to parse presence update message:', error);
        }
      });

      this.logger.log('Subscribed to presence updates');
    } catch (error) {
      this.logger.error('Failed to subscribe to presence updates:', error);
    }
  }

  async unsubscribeFromPresenceUpdates(): Promise<void> {
    try {
      await this.redisService.unsubscribe(PRESENCE_CHANNEL);
      this.logger.log('Unsubscribed from presence updates');
    } catch (error) {
      this.logger.error('Failed to unsubscribe from presence updates:', error);
    }
  }

  async isUserOnline(userId: string): Promise<boolean> {
    try {
      const isMember = await this.redisService.zscore(ONLINE_ZSET_KEY, userId);
      return isMember !== null;
    } catch (error) {
      this.logger.error(`Failed to check if user ${userId} is online:`, error);
      return false;
    }
  }

  async getUserStatus(userId: string): Promise<PresenceStatus> {
    const presence = await this.getPresence(userId);
    return presence?.status ?? PresenceStatus.OFFLINE;
  }
}
