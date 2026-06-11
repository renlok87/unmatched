import { Field, InputType } from '@nestjs/graphql';
import { PresenceStatus } from '../models/presence.model';

@InputType()
export class HeartbeatInput {
  @Field(() => PresenceStatus, { nullable: true, defaultValue: PresenceStatus.ONLINE })
  status?: PresenceStatus;

  @Field(() => String, { nullable: true })
  currentGameId?: string;
}

@InputType()
export class GetPresenceInput {
  @Field(() => String)
  userId: string;
}
