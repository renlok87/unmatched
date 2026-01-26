import { Field, InputType } from '@nestjs/graphql';
import { IsEnum, IsOptional, IsString, IsUUID } from 'class-validator';

export enum GameMode {
  ONE_V_ONE = 'ONE_V_ONE',
  TWO_V_TWO = 'TWO_V_TWO',
  FREE_FOR_ALL = 'FREE_FOR_ALL',
  VS_AI = 'VS_AI',
}

export enum GameStatus {
  PENDING = 'PENDING',
  LOBBY = 'LOBBY',
  IN_PROGRESS = 'IN_PROGRESS',
  PAUSED = 'PAUSED',
  FINISHED = 'FINISHED',
  ABORTED = 'ABORTED',
}

export enum GamePhase {
  SETUP = 'SETUP',
  TURN_START = 'TURN_START',
  ACTION_MANEUVER = 'ACTION_MANEUVER',
  ACTION_ATTACK = 'ACTION_ATTACK',
  COMBAT = 'COMBAT',
  COMBAT_RESOLVE = 'COMBAT_RESOLVE',
  TURN_END = 'TURN_END',
}

@InputType()
export class CreateGameDto {
  @Field(() => GameMode, { nullable: true })
  @IsOptional()
  @IsEnum(GameMode)
  mode?: GameMode;

  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  @IsUUID()
  boardId?: string;
}
