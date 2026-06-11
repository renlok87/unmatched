import { Field, ObjectType } from '@nestjs/graphql';

@ObjectType()
export class GamePlayerResponse {
  @Field()
  id: string;

  @Field()
  userId: string;

  @Field()
  username: string;

  @Field(() => String, { nullable: true })
  avatar: string | null;

  @Field(() => String, { nullable: true })
  heroId: string | null;

  @Field()
  isReady: boolean;

  @Field()
  hasPassed: boolean;

  @Field()
  seatOrder: number;
}
