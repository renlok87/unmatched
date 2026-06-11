import { Field, ObjectType, InterfaceType, registerEnumType } from '@nestjs/graphql';
import { UserRole } from '@prisma/client';

// Register UserRole enum for GraphQL
registerEnumType(UserRole, {
  name: 'UserRole',
  description: 'User role in the system',
});

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

  @Field(() => String, { nullable: true })
  avatar: string | null;

  @Field(() => UserRole)
  role: UserRole;

  @Field()
  createdAt: Date;

  @Field(() => Date, { nullable: true })
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
