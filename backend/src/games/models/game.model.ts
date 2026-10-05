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

/**
 * DE-030 (W-19; 01 F-05, D-DE-05; 02 SD-29, SD-41): one catalog card of a hero's deck list - the PUBLIC
 * composition (the same list the hero pick shows), grouped by catalog id. No instance ids, no draw order,
 * no hand or discard state: the client marks "in hand" / "in discard" from data it already holds.
 */
@ObjectType()
export class DeckListCardResponse {
  /** Catalog id - the `cardId` of the instances in hands and discard piles. */
  @Field()
  cardId: string;

  @Field()
  name: string;

  @Field(() => String, { nullable: true })
  nameEn: string | null;

  @Field(() => String, { nullable: true })
  nameRu: string | null;

  @Field()
  cardType: string;

  @Field(() => Int, { nullable: true })
  attackValue: number | null;

  @Field(() => Int, { nullable: true })
  defenseValue: number | null;

  @Field(() => Int, { nullable: true })
  boostValue: number | null;

  @Field(() => String, { nullable: true })
  bannerName: string | null;

  @Field(() => String, { nullable: true })
  text: string | null;

  /** Copies of this card in the deck. */
  @Field(() => Int)
  count: number;
}

/** DE-030: one player's public deck list (gameDeckLists). */
@ObjectType()
export class DeckListResponse {
  @Field()
  playerId: string;

  /** Total copies (the deck size at setup). */
  @Field(() => Int)
  total: number;

  /** Sorted by card type, then name - never the draw order. */
  @Field(() => [DeckListCardResponse])
  cards: DeckListCardResponse[];
}
