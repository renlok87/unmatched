import { Field, InputType } from '@nestjs/graphql';
import { IsString, IsUUID, IsOptional, IsBoolean } from 'class-validator';

@InputType()
export class JoinGameDto {
  @Field()
  @IsString()
  @IsUUID()
  gameId: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  @IsUUID()
  heroId?: string;

  @Field({ nullable: true })
  @IsOptional()
  @IsBoolean()
  asOpponent?: boolean;
}
