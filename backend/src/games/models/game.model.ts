import { Field, ObjectType, Int } from '@nestjs/graphql';
import { GameStatus, GameMode, GamePhase } from '../dto';
import { GamePlayerResponse } from './game-player.model';

@ObjectType()
export class GameResponse {
  @Field()
  id: string;

  @Field(() => String, { nullable: true })
  code: string | null;

  @Field(() => GameStatus)
  status: GameStatus;

  @Field(() => GameMode)
  mode: GameMode;

  @Field()
  hostId: string;

  @Field(() => GamePlayerResponse)
  host: GamePlayerResponse;

  @Field(() => String, { nullable: true })
  opponentId: string | null;

  @Field(() => GamePlayerResponse, { nullable: true })
  opponent: GamePlayerResponse | null;

  @Field()
  boardId: string;

  @Field(() => String, { nullable: true })
  boardState: string | null;

  @Field()
  createdAt: Date;

  @Field()
  updatedAt: Date;

  @Field(() => Date, { nullable: true })
  startedAt: Date | null;

  @Field(() => Date, { nullable: true })
  endedAt: Date | null;

  @Field(() => String, { nullable: true })
  winnerId: string | null;

  @Field()
  version: number;

  @Field(() => [GamePlayerResponse])
  players: GamePlayerResponse[];

  @Field(() => GamePhase, { nullable: true })
  phase: GamePhase | null;

  @Field(() => Int, { nullable: true })
  currentTurn: number | null;
}

@ObjectType()
export class GameStateResponse {
  @Field()
  id: string;

  @Field()
  gameId: string;

  @Field(() => String)
  state: any;

  @Field()
  sequenceNumber: number;

  @Field(() => String, { nullable: true })
  currentTurnPlayerId: string | null;

  @Field()
  phase: string;

  @Field()
  turnCount: number;

  @Field()
  updatedAt: Date;
}
