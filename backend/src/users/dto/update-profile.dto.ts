import { Field, InputType, ObjectType } from '@nestjs/graphql';
import { IsString, IsOptional, MaxLength, MinLength, Matches, IsUrl, IsEnum } from 'class-validator';
import { UserRole } from '@prisma/client';

@InputType()
export class UpdateProfileDto {
  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  @MinLength(3)
  @MaxLength(20)
  @Matches(/^[a-zA-Z0-9_]+$/, {
    message: 'Username must contain only letters, numbers and underscores',
  })
  username?: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  @MaxLength(500)
  @IsUrl({}, { message: 'Avatar must be a valid URL' })
  avatar?: string;
}

/**
 * Полный ответ пользователя (с email) - только для владельца аккаунта
 */
@ObjectType()
export class UserResponse {
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

/**
 * Публичный профиль пользователя (без email) - для всех пользователей
 */
@ObjectType()
export class PublicUserResponse {
  @Field()
  id: string;

  @Field()
  username: string;

  @Field(() => String, { nullable: true })
  avatar: string | null;

  @Field()
  createdAt: Date;
}

@ObjectType()
export class UserSettingsResponse {
  @Field()
  id: string;

  @Field()
  theme: string;

  @Field()
  language: string;

  @Field()
  soundEnabled: boolean;

  @Field()
  musicEnabled: boolean;

  @Field()
  profileVisible: boolean;

  @Field()
  showOnlineStatus: boolean;
}

@ObjectType()
export class UserWithSettingsResponse extends UserResponse {
  @Field(() => UserSettingsResponse, { nullable: true })
  settings?: UserSettingsResponse | null;
}

@ObjectType()
export class PublicUserWithSettingsResponse extends PublicUserResponse {
  @Field(() => UserSettingsResponse, { nullable: true })
  settings?: UserSettingsResponse | null;
}
