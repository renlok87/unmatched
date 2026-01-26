import { Injectable } from '@nestjs/common';
import type {
  HeroDefinition,
  CardDefinition,
  BoardDefinition,
  HeroUrls,
} from '../interfaces';
import type {
  HeroDto,
  CardDto,
  BoardDto,
  BoardSpaceDto,
  PositionDto,
  HeroUrlsDto,
} from '../dto/content.dto';
import { FighterType, Zone } from '../interfaces';

/**
 * Content Mapper
 * Transforms Domain models to DTOs for API responses
 * Provides separation between internal data structure and API contract
 */
@Injectable()
export class ContentMapper {
  // ==================== Hero Mapping ====================

  toHeroDto(hero: HeroDefinition): HeroDto {
    return {
      id: hero.id,
      name: hero.name,
      health: hero.health,
      movement: hero.movement,
      set: hero.set,
      abilities: hero.abilities.map(a => ({
        id: a.id,
        name: a.name,
        text: a.text,
        trigger: a.trigger,
      })),
      cards: hero.deckCards.map(c => this.toCardDto(c)),
      fighterType: FighterType.HERO,
      sidekickCount: hero.sidekickCount,
      sidekickHealth: hero.sidekickHealth,
      urls: hero.urls ? this.toHeroUrlsDto(hero.urls) : undefined,
    };
  }

  toHeroDtoList(heroes: HeroDefinition[]): HeroDto[] {
    return heroes.map(h => this.toHeroDto(h));
  }

  toHeroUrlsDto(urls: HeroUrls): HeroUrlsDto {
    return {
      avatar: urls.avatar,
      mini: urls.mini,
      cardCover: urls.cardCover,
    };
  }

  // ==================== Card Mapping ====================

  toCardDto(card: CardDefinition): CardDto {
    return {
      id: card.id,
      title: card.title,
      type: card.type,
      value: card.value,
      boost: card.boost,
      quantity: card.quantity,
      characterName: card.characterName,
      effects: card.effects.map(e => ({
        id: e.id,
        timing: e.timing,
        text: e.text,
      })),
    };
  }

  toCardDtoList(cards: CardDefinition[]): CardDto[] {
    return cards.map(c => this.toCardDto(c));
  }

  // ==================== Board Mapping ====================

  toBoardDto(board: BoardDefinition): BoardDto {
    return {
      id: board.id,
      name: board.name,
      width: board.width,
      height: board.height,
      recommendedPlayers: board.recommendedPlayers,
      spaces: board.spaces.map(s => this.toBoardSpaceDto(s)),
    };
  }

  toBoardDtoList(boards: BoardDefinition[]): BoardDto[] {
    return boards.map(b => this.toBoardDto(b));
  }

  toBoardSpaceDto(space: { position: { x: number; y: number }; zones: Zone[]; isObstacle?: boolean }): BoardSpaceDto {
    return {
      position: { x: space.position.x, y: space.position.y },
      zones: space.zones,
      isObstacle: space.isObstacle,
      startingPositionsJson: undefined,
    };
  }

  // ==================== Summary Mapping ====================

  toContentSummaryDto(summary: {
    version: string;
    heroesCount: number;
    boardsCount: number;
    setsCount: number;
    sets: string[];
  }) {
    return {
      version: summary.version,
      heroesCount: summary.heroesCount,
      boardsCount: summary.boardsCount,
      setsCount: summary.setsCount,
      sets: summary.sets,
    };
  }
}
