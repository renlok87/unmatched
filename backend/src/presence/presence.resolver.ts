import { Resolver, Mutation, Query, Args, Subscription } from '@nestjs/graphql';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { PresenceService } from './presence.service';
import { HeartbeatResponse, OnlineUsersResponse, Presence } from './dto/presence.dto';
import { HeartbeatInput } from './dto/heartbeat.dto';
import { PresenceData, PresenceStatus } from './models/presence.model';

interface UserPayload {
  userId: string;
  email: string;
  username: string;
}

@Resolver()
export class PresenceResolver {
  constructor(private readonly presenceService: PresenceService) {}

  @Mutation(() => HeartbeatResponse)
  async heartbeat(
    @CurrentUser() user: UserPayload,
    @Args('input') input: HeartbeatInput,
  ): Promise<HeartbeatResponse> {
    const status = input.status ?? PresenceStatus.ONLINE;
    const presence = await this.presenceService.updatePresence(user.userId, status, input.currentGameId);

    return {
      presence: {
        userId: presence.userId,
        status: presence.status,
        currentGameId: presence.currentGameId,
        lastSeenAt: presence.lastSeenAt,
      },
      ttl: 300,
    };
  }

  @Query(() => Presence, { nullable: true })
  async getPresence(@Args('userId', { type: () => String }) userId: string): Promise<Presence | null> {
    const presence = await this.presenceService.getPresence(userId);

    if (!presence) {
      return null;
    }

    return {
      userId: presence.userId,
      status: presence.status,
      currentGameId: presence.currentGameId,
      lastSeenAt: presence.lastSeenAt,
    };
  }

  @Query(() => OnlineUsersResponse)
  async getOnlineUsers(): Promise<OnlineUsersResponse> {
    const userIds = await this.presenceService.getOnlineUserIds();

    return {
      userIds,
      count: userIds.length,
    };
  }

  @Query(() => Number)
  async getOnlineCount(): Promise<number> {
    return this.presenceService.getOnlineCount();
  }

  @Subscription(() => Presence, {
    filter: (payload: any, variables: any) => {
      if (!variables.userIds || variables.userIds.length === 0) {
        return true;
      }
      return variables.userIds.includes(payload.presenceUpdated.userId);
    },
  })
  presenceUpdated(
    @Args('userIds', { nullable: true, type: () => [String] })
    userIds?: string[],
  ): AsyncIterator<Presence> {
    return this.presenceService.subscribeToPresenceUpdates((presence) => ({
      presenceUpdated: presence,
    })) as any;
  }
}
