import { Field, ObjectType, Int } from '@nestjs/graphql';

@ObjectType()
export class PenaltyInfoDto {
  @Field(() => Boolean)
  canJoinQueue: boolean;

  @Field(() => Int)
  declineCount: number;

  @Field(() => Date, { nullable: true })
  tempBanUntil?: Date;

  @Field(() => Int, { nullable: true })
  penaltyElo?: number;

  @Field(() => String, { nullable: true })
  reason?: string;
}
