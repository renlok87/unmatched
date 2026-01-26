import { Field, InputType, ObjectType } from '@nestjs/graphql';
import { IsString, IsBoolean, IsOptional, IsIn } from 'class-validator';

@InputType()
export class SettingsDto {
  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  @IsIn(['light', 'dark', 'auto'])
  theme?: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  @IsIn(['ru', 'en'])
  language?: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsBoolean()
  soundEnabled?: boolean;

  @Field({ nullable: true })
  @IsOptional()
  @IsBoolean()
  musicEnabled?: boolean;

  @Field({ nullable: true })
  @IsOptional()
  @IsBoolean()
  profileVisible?: boolean;

  @Field({ nullable: true })
  @IsOptional()
  @IsBoolean()
  showOnlineStatus?: boolean;
}

@ObjectType()
export class UserSettingsGraphql {
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
