import { Field, InputType } from '@nestjs/graphql';
import { IsEnum, IsOptional, IsInt, Max, Min } from 'class-validator';
import { GameStatus, GameMode } from './create-game.dto';

@InputType()
export class GameFiltersDto {
  @Field(() => GameStatus, { nullable: true })
  @IsOptional()
  @IsEnum(GameStatus)
  status?: GameStatus;

  @Field(() => GameMode, { nullable: true })
  @IsOptional()
  @IsEnum(GameMode)
  mode?: GameMode;

  @Field({ nullable: true })
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number;

  @Field({ nullable: true })
  @IsOptional()
  @IsInt()
  @Min(0)
  offset?: number;
}
