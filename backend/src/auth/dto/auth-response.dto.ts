import { Field, ObjectType, InterfaceType } from '@nestjs/graphql';

@InterfaceType()
export abstract class TokensPair {
  @Field()
  accessToken: string;

  @Field()
  refreshToken: string;
}

@ObjectType()
export class AuthUserResponse {
  @Field()
  id: string;

  @Field()
  email: string;

  @Field()
  username: string;

  @Field({ nullable: true })
  avatar: string | null;

  @Field()
  createdAt: Date;

  @Field({ nullable: true })
  emailVerified: Date | null;
}

@ObjectType()
export class AuthResponseDto implements TokensPair {
  @Field(() => String)
  accessToken: string;

  @Field(() => String)
  refreshToken: string;

  @Field(() => AuthUserResponse)
  user: AuthUserResponse;
}
