import { Field, ObjectType } from '@nestjs/graphql';
import { GameStatus, GameMode, GamePhase } from '../dto';
import { GamePlayerResponse } from './game-player.model';

/* eslint-disable @typescript-eslint/no-redundant-type-constituents */

@ObjectType()
export class GameResponse {
  @Field()
  id: string;

  @Field(() => GameStatus)
  status: GameStatus;

  @Field(() => GameMode)
  mode: GameMode;

  @Field()
  hostId: string;

  @Field(() => GamePlayerResponse)
  host: GamePlayerResponse;

  @Field({ nullable: true })
  opponentId: string | null;

  @Field(() => GamePlayerResponse, { nullable: true })
  opponent: GamePlayerResponse | null;

  @Field()
  boardId: string;

  @Field({ nullable: true })
  boardState: any | null;

  @Field()
  createdAt: Date;

  @Field()
  updatedAt: Date;

  @Field({ nullable: true })
  startedAt: Date | null;

  @Field({ nullable: true })
  endedAt: Date | null;

  @Field({ nullable: true })
  winnerId: string | null;

  @Field()
  version: number;

  @Field(() => [GamePlayerResponse])
  players: GamePlayerResponse[];

  @Field(() => GamePhase, { nullable: true })
  phase: GamePhase | null;

  @Field({ nullable: true })
  currentTurn: number | null;
}

@ObjectType()
export class GameStateResponse {
  @Field()
  id: string;

  @Field()
  gameId: string;

  @Field()
  state: any;

  @Field()
  sequenceNumber: number;

  @Field({ nullable: true })
  currentTurnPlayerId: string | null;

  @Field()
  phase: string;

  @Field()
  turnCount: number;

  @Field()
  updatedAt: Date;
}
