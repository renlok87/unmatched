import { Field, Int, ObjectType, registerEnumType } from '@nestjs/graphql';
import { CardType, EffectTiming, AbilityTrigger, FighterType, Zone } from '../interfaces';

// Register enums for GraphQL
registerEnumType(CardType, {
  name: 'CardType',
  description: 'Type of a card in the game',
});

registerEnumType(EffectTiming, {
  name: 'EffectTiming',
  description: 'Timing when a card effect activates',
});

registerEnumType(AbilityTrigger, {
  name: 'AbilityTrigger',
  description: 'Trigger condition for a hero ability',
});

registerEnumType(FighterType, {
  name: 'FighterType',
  description: 'Type of a fighter in the game',
});

registerEnumType(Zone, {
  name: 'Zone',
  description: 'Color zones on the board',
});

@ObjectType('HeroUrls')
export class HeroUrlsDto {
  @Field(() => String)
  avatar!: string;

  @Field(() => String)
  mini!: string;

  @Field(() => String)
  cardCover!: string;
}

@ObjectType('HeroAbility')
export class HeroAbilityDto {
  @Field(() => String)
  id!: string;

  @Field(() => String)
  name!: string;

  @Field(() => String)
  text!: string;

  @Field(() => AbilityTrigger)
  trigger!: AbilityTrigger;
}

@ObjectType('CardEffect')
export class CardEffectDto {
  @Field(() => String)
  id!: string;

  @Field(() => EffectTiming)
  timing!: EffectTiming;

  @Field(() => String)
  text!: string;
}

@ObjectType('Card')
export class CardDto {
  @Field(() => String)
  id!: string;

  @Field(() => String)
  title!: string;

  @Field(() => CardType)
  type!: CardType;

  @Field(() => Int)
  value!: number;

  @Field(() => Int)
  boost!: number;

  @Field(() => Int)
  quantity!: number;

  @Field(() => String)
  characterName!: string;

  @Field(() => [CardEffectDto])
  effects!: CardEffectDto[];
}

@ObjectType('Hero')
export class HeroDto {
  @Field(() => String)
  id!: string;

  @Field(() => String)
  name!: string;

  @Field(() => Int)
  health!: number;

  @Field(() => Int)
  movement!: number;

  @Field(() => String)
  set!: string;

  @Field(() => [HeroAbilityDto])
  abilities!: HeroAbilityDto[];

  @Field(() => [CardDto])
  cards!: CardDto[];

  @Field(() => FighterType)
  fighterType!: FighterType;

  @Field(() => Int, { nullable: true })
  sidekickCount?: number;

  @Field(() => Int, { nullable: true })
  sidekickHealth?: number;

  @Field(() => HeroUrlsDto, { nullable: true })
  urls?: HeroUrlsDto;
}

@ObjectType('Position')
export class PositionDto {
  @Field(() => Int)
  x!: number;

  @Field(() => Int)
  y!: number;
}

@ObjectType('BoardSpace')
export class BoardSpaceDto {
  @Field(() => PositionDto)
  position!: PositionDto;

  @Field(() => [Zone])
  zones!: Zone[];

  @Field(() => Boolean, { nullable: true })
  isObstacle?: boolean;

  @Field(() => String, { nullable: true })
  startingPositionsJson?: string;
}

@ObjectType('Board')
export class BoardDto {
  @Field(() => String)
  id!: string;

  @Field(() => String)
  name!: string;

  @Field(() => Int)
  width!: number;

  @Field(() => Int)
  height!: number;

  @Field(() => Int)
  recommendedPlayers!: number;

  @Field(() => [BoardSpaceDto])
  spaces!: BoardSpaceDto[];
}

@ObjectType('PaginationInfo')
export class PaginationInfoDto {
  @Field(() => Int)
  total!: number;

  @Field(() => Int)
  page!: number;

  @Field(() => Int)
  limit!: number;

  @Field(() => Int)
  totalPages!: number;

  @Field(() => Boolean)
  hasNextPage!: boolean;

  @Field(() => Boolean)
  hasPreviousPage!: boolean;
}

@ObjectType('PaginatedHeroes')
export class PaginatedHeroesDto {
  @Field(() => [HeroDto])
  items!: HeroDto[];

  @Field(() => PaginationInfoDto)
  pagination!: PaginationInfoDto;
}

@ObjectType('PaginatedBoards')
export class PaginatedBoardsDto {
  @Field(() => [BoardDto])
  items!: BoardDto[];

  @Field(() => PaginationInfoDto)
  pagination!: PaginationInfoDto;
}

@ObjectType('ContentSummary')
export class ContentSummaryDto {
  @Field(() => String)
  version!: string;

  @Field(() => Int)
  heroesCount!: number;

  @Field(() => Int)
  boardsCount!: number;

  @Field(() => Int)
  setsCount!: number;

  @Field(() => [String])
  sets!: string[];
}
