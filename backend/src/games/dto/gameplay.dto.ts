/**
 * Gameplay Mutations DTOs
 *
 * DTOs для игровых мутаций в Unmatched
 */

import { Field, InputType, ObjectType, Int, registerEnumType } from '@nestjs/graphql';
import {
  IsNotEmpty,
  IsString,
  IsInt,
  IsArray,
  ValidateNested,
  Min,
  Max,
  IsOptional,
} from 'class-validator';
import { Type } from 'class-transformer';
import { GamePhase } from './create-game.dto';

/**
 * Типы игровых событий для подписок
 */
export enum GameEventType {
  ATTACK_INITIATED = 'ATTACK_INITIATED',
  DEFENSE_PLAYED = 'DEFENSE_PLAYED',
  COMBAT_RESOLVED = 'COMBAT_RESOLVED',
  TURN_CHANGED = 'TURN_CHANGED',
  PLAYER_JOINED = 'PLAYER_JOINED',
  PLAYER_LEFT = 'PLAYER_LEFT',
  GAME_ENDED = 'GAME_ENDED',
  FIGHTER_MOVED = 'FIGHTER_MOVED',
  DOOR_TOGGLED = 'DOOR_TOGGLED',
  MANEUVER = 'MANEUVER',
  TURN_ENDED = 'TURN_ENDED',
  CARD_PLAYED = 'CARD_PLAYED',
  // Покрытие Prisma-enum GameActionType для eventsSince (журнал GameAction)
  GAME_CREATED = 'GAME_CREATED',
  GAME_JOINED = 'GAME_JOINED',
  GAME_STARTED = 'GAME_STARTED',
  GAME_ABORTED = 'GAME_ABORTED',
  TURN_STARTED = 'TURN_STARTED',
  PASSED = 'PASSED',
  CARD_DISCARDED = 'CARD_DISCARDED',
  PLACED = 'PLACED',
  EFFECT_APPLIED = 'EFFECT_APPLIED',
  SPECIAL_ABILITY = 'SPECIAL_ABILITY',
}

registerEnumType(GameEventType, {
  name: 'GameEventType',
  description: 'Типы игровых событий',
});

// ============================================
// Input DTOs
// ============================================

/**
 * Позиция на доске
 */
@InputType()
export class PositionInput {
  @Field(() => Int)
  @IsInt()
  @Min(0)
  @Max(19)
  x: number;

  @Field(() => Int)
  @IsInt()
  @Min(0)
  @Max(19)
  y: number;
}

/**
 * DTO для манёвра (перемещение + розыгрыш карты)
 */
@InputType()
export class ManeuverDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  fighterId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  cardId: string;

  @Field(() => [PositionInput])
  @IsArray()
  @ValidateNested({ each: true })
  @Type(() => PositionInput)
  path: PositionInput[];
}

/**
 * DTO для простого перемещения бойца
 */
@InputType()
export class MoveFighterDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  fighterId: string;

  @Field(() => Int)
  @IsInt()
  @Min(0)
  @Max(19)
  x: number;

  @Field(() => Int)
  @IsInt()
  @Min(0)
  @Max(19)
  y: number;
}

/**
 * DTO для атаки
 */
@InputType()
export class AttackDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  attackerId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  cardId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  targetId: string;
}

/**
 * DTO для игры защиты
 * userId извлекается из JWT (GqlAuthGuard)
 */
@InputType()
export class PlayDefenseDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  cardId: string;
}

/**
 * DTO для розыгрыша scheme-карты из руки (тратит 1 действие)
 * userId извлекается из JWT (GqlAuthGuard)
 */
@InputType()
export class PlaySchemeDto {
  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  gameId: string;

  @Field(() => String)
  @IsNotEmpty()
  @IsString()
  cardId: string;
}

/**
 * DTO для разрешения боя
 */
@InputType()
export class ResolveCombatDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;
}

/**
 * DTO для конца хода
 */
@InputType()
export class EndTurnDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;
}

/**
 * DTO для пасса (сброс карты + дополнительное действие)
 */
@InputType()
export class PassDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;
}

/**
 * DTO для переключения двери
 */
@InputType()
export class ToggleDoorDto {
  @Field(() => String)
  @IsNotEmpty()
  gameId: string;

  @Field(() => Int)
  @IsInt()
  @Min(0)
  @Max(19)
  x: number;

  @Field(() => Int)
  @IsInt()
  @Min(0)
  @Max(19)
  y: number;
}

// ============================================
// Output DTOs
// ============================================

/**
 * Типы событий для turn changed
 */
@ObjectType()
export class TurnState {
  @Field(() => String)
  playerId: string;

  @Field(() => Int)
  turnCount: number;

  @Field(() => GamePhase)
  phase: GamePhase;
}

/**
 * Игровое событие для подписок
 */
@ObjectType()
export class GameEvent {
  @Field(() => GameEventType)
  type: GameEventType;

  @Field(() => String)
  gameId: string;

  @Field(() => Int)
  sequenceNumber: number;

  @Field(() => Date)
  timestamp: Date;

  @Field(() => String, { nullable: true })
  payload: string | null;
}

/**
 * Состояние боя
 */
@ObjectType()
export class CombatState {
  @Field(() => String)
  attackerId: string;

  @Field(() => String)
  targetId: string;

  @Field(() => String, { nullable: true })
  attackCardId: string | null;

  @Field(() => String, { nullable: true })
  defenseCardId: string | null;

  @Field(() => Date)
  timeoutAt: Date;
}

/**
 * Результат мутации с метаданными для оптимизации клиента
 */
@ObjectType()
export class GameMutationResult {
  @Field(() => String, { nullable: true })
  state: string | null;

  @Field(() => Int)
  sequenceNumber: number;

  @Field(() => Date)
  timestamp: Date;

  @Field(() => GamePhase)
  phase: GamePhase;

  @Field(() => String, { nullable: true })
  currentTurnPlayerId: string | null;

  @Field(() => Int)
  turnCount: number;
}

/**
 * GameState для GraphQL (упрощённая версия)
 */
@ObjectType()
export class GameState {
  @Field(() => String)
  gameId: string;

  @Field(() => Int)
  sequenceNumber: number;

  @Field(() => GamePhase)
  phase: GamePhase;

  @Field(() => Int)
  turnCount: number;

  @Field(() => String)
  currentTurnPlayerId: string;

  @Field(() => String, { nullable: true })
  players: string | null;

  @Field(() => String, { nullable: true })
  fighters: string | null;

  @Field(() => String, { nullable: true })
  handZones: string | null;

  @Field(() => String, { nullable: true })
  boardState: string | null;

  @Field(() => String, { nullable: true })
  metadata: string | null;
}

/**
 * GameStatePlayer для GraphQL
 */
@ObjectType()
export class GameStatePlayer {
  @Field(() => String)
  userId: string;

  @Field(() => String)
  heroId: string;

  @Field(() => Int)
  health: number;

  @Field(() => Int)
  maxHealth: number;

  @Field(() => [String])
  fighterIds: string[];

  @Field()
  isAlive: boolean;
}

/**
 * Fighter для GraphQL
 */
@ObjectType()
export class Fighter {
  @Field(() => String)
  id: string;

  @Field(() => String)
  ownerId: string;

  @Field(() => String)
  heroId: string;

  @Field(() => String)
  name: string;

  @Field(() => String)
  type: string;

  @Field(() => Int)
  health: number;

  @Field(() => Int)
  maxHealth: number;

  @Field(() => String, { nullable: true })
  position: string | null;

  @Field(() => [String], { nullable: true })
  effects: string[] | null;

  @Field()
  hasSidekick: boolean;
}

/**
 * HandZone для GraphQL
 */
@ObjectType()
export class HandZone {
  @Field(() => String, { nullable: true })
  cards: string | null;

  @Field(() => Int)
  maxSize: number;
}

/**
 * EventsSinceResponse для catch-up пропущенных событий при реконнекте
 */
@ObjectType()
export class EventsSinceResponse {
  @Field(() => String)
  gameId!: string;

  @Field(() => [GameEvent])
  events!: GameEvent[];

  @Field(() => Int)
  lastSequence!: number;

  @Field()
  hasMore!: boolean;
}
