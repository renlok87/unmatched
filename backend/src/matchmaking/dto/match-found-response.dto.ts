import { Field, ObjectType, Int } from '@nestjs/graphql';

@ObjectType()
export class MatchFoundResponse {
  @Field(() => String)
  gameId: string;

  @Field(() => String)
  opponentId: string;

  @Field(() => String)
  opponentUsername: string;

  @Field(() => Int)
  opponentRating: number;

  @Field(() => String)
  mode: string;

  @Field(() => Date)
  expiresAt: Date;
}
