import { Field, InputType, registerEnumType } from '@nestjs/graphql';
import { IsEnum, IsOptional, IsString } from 'class-validator';

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
  GAME_OVER = 'GAME_OVER', // Игра окончена, победитель определён
}

// Register enums for GraphQL
registerEnumType(GameMode, {
  name: 'GameMode',
  description: 'Game mode options',
});

registerEnumType(GameStatus, {
  name: 'GameStatus',
  description: 'Game status options',
});

registerEnumType(GamePhase, {
  name: 'GamePhase',
  description: 'Game phase options',
});

@InputType()
export class CreateGameDto {
  @Field(() => GameMode, { nullable: true })
  @IsOptional()
  @IsEnum(GameMode)
  mode?: GameMode;

  @Field({ nullable: true })
  @IsOptional()
  @IsString()
  boardId?: string;
}
