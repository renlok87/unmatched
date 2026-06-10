import { Field, InputType } from '@nestjs/graphql';
import { IsEnum, IsOptional, IsString } from 'class-validator';
import { GameMode } from '../../games/dto/create-game.dto';

@InputType()
export class JoinQueueDto {
  @Field(() => GameMode)
  @IsEnum(GameMode)
  mode: GameMode;

  @Field(() => String, { nullable: true })
  @IsOptional()
  @IsString()
  heroPref?: string;
}
