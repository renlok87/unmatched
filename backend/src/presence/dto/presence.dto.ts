import { Field, ObjectType, registerEnumType } from '@nestjs/graphql';
import { PresenceStatus } from '../models/presence.model';

registerEnumType(PresenceStatus, {
  name: 'PresenceStatus',
  description: 'Status of user presence',
});

@ObjectType()
export class Presence {
  @Field(() => String)
  userId: string;

  @Field(() => PresenceStatus)
  status: PresenceStatus;

  @Field(() => String, { nullable: true })
  currentGameId?: string;

  @Field(() => Number)
  lastSeenAt: number;
}

@ObjectType()
export class HeartbeatResponse {
  @Field(() => Presence)
  presence: Presence;

  @Field(() => Number)
  ttl: number;
}

@ObjectType()
export class OnlineUsersResponse {
  @Field(() => [String])
  userIds: string[];

  @Field(() => Number)
  count: number;
}
