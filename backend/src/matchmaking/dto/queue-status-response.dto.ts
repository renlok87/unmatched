import { Field, ObjectType, Int } from '@nestjs/graphql';

@ObjectType()
export class QueueStatusResponse {
  @Field(() => Boolean)
  inQueue: boolean;

  @Field(() => String, { nullable: true })
  mode?: string;

  @Field(() => Int, { nullable: true })
  position?: number;

  @Field(() => Int)
  totalPlayers: number;

  @Field(() => Int)
  estimatedWaitTime: number; // секунды

  @Field(() => Date, { nullable: true })
  joinedAt?: Date;
}
