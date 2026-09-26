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
import { FighterType, Zone, CardType } from '../interfaces';
import type { Hero, Card, Board as PrismaBoard } from '@prisma/client';

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
      nameEn: hero.nameEn,
      nameRu: hero.nameRu,
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

  /**
   * Прямое преобразование Prisma модели в HeroDto (для админки)
   */
  prismaHeroToHeroDto(prismaHero: Hero & { cards?: Card[] }): HeroDto {
    const cards = prismaHero.cards || [];
    const urls = this.parseHeroUrls(prismaHero);

    return {
      id: prismaHero.name, // Используем name как ID для совместимости с существующей системой
      name: prismaHero.name,
      nameEn: prismaHero.nameEn || undefined,
      nameRu: prismaHero.nameRu || undefined,
      health: prismaHero.health,
      movement: 3,
      set: prismaHero.set,
      abilities: this.parsePrismaAbility(prismaHero.ability).map((a: any, i: number) => ({
        id: `${prismaHero.name}-ability-${i}`,
        name: a.name || 'Ability',
        text: a.text || a.description || '',
        trigger: a.trigger || 'passive',
      })),
      cards: cards.map((c) => {
        const cardDef = this.prismaCardToCardDefinition(c);
        return {
          id: cardDef.id,
          title: cardDef.title,
          type: cardDef.type,
          value: cardDef.value,
          boost: cardDef.boost,
          quantity: cardDef.quantity,
          characterName: cardDef.characterName,
          imageUrl: cardDef.imageUrl,
          imageUrlRu: cardDef.imageUrlRu,
          effects: cardDef.effects.map((e: any, i: number) => ({
            id: `${c.id}-effect-${i}`,
            timing: e.timing || 'during_combat',
            text: e.text || '',
          })),
        };
      }),
      fighterType: this.parseFighterType(prismaHero.fighterType),
      sidekickCount: this.parseSidekickCount(prismaHero.properties),
      sidekickHealth: this.parseSidekickHealth(prismaHero.properties),
      urls,
      imageUrl: prismaHero.imageUrl || undefined,
      avatarUrl: prismaHero.avatarUrl || undefined,
      createdAt: prismaHero.createdAt,
      updatedAt: prismaHero.updatedAt,
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
      imageUrl: card.imageUrl,
      imageUrlRu: card.imageUrlRu,
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
      imageUrl: board.imageUrl,
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

  // ==================== Prisma Model Mapping ====================

  /**
   * Convert Prisma Hero model to HeroDefinition
   */
  prismaHeroToHeroDefinition(
    prismaHero: Hero & { cards?: Card[] },
  ): HeroDefinition {
    const cards = prismaHero.cards || [];

    return {
      id: prismaHero.name, // Use name as ID for compatibility
      name: prismaHero.name,
      nameEn: prismaHero.nameEn || undefined,
      nameRu: prismaHero.nameRu || undefined,
      health: prismaHero.health,
      movement: 3, // Default value, should be stored in DB
      set: prismaHero.set,
      abilities: this.parsePrismaAbility(prismaHero.ability),
      deckCards: cards.map((c) => this.prismaCardToCardDefinition(c)),
      fighterType: this.parseFighterType(prismaHero.fighterType),
      sidekickCount: this.parseSidekickCount(prismaHero.properties),
      sidekickHealth: this.parseSidekickHealth(prismaHero.properties),
      urls: this.parseHeroUrls(prismaHero),
    };
  }

  /**
   * Convert Prisma Card model to CardDefinition
   */
  prismaCardToCardDefinition(prismaCard: Card): CardDefinition {
    const effects = this.parsePrismaEffects(prismaCard.effects);

    return {
      id: prismaCard.id,
      title: prismaCard.name,
      type: this.parseCardType(prismaCard.cardType),
      value:
        prismaCard.attackValue ??
        prismaCard.defenseValue ??
        prismaCard.boostValue ??
        0,
      boost: prismaCard.boostValue ?? 0,
      quantity: prismaCard.count,
      characterName: prismaCard.nameEn || prismaCard.name,
      imageUrl: prismaCard.imageUrl || undefined,
      imageUrlRu: prismaCard.imageUrlRu || undefined,
      effects: effects.map((e, i) => ({
        id: `${prismaCard.id}-effect-${i}`,
        timing: e.timing || 'during_combat',
        text: e.text || prismaCard.text || '',
      })),
    };
  }

  /**
   * Convert Prisma Board model to BoardDefinition
   */
  prismaBoardToBoardDefinition(prismaBoard: PrismaBoard): BoardDefinition {
    const cells = this.parsePrismaCells(prismaBoard.cells);
    const spaces = cells.map((cell) => ({
      position: { x: cell.x, y: cell.y },
      zones: this.normalizeZones(cell.zones),
      isObstacle: cell.isObstacle || false,
    }));

    return {
      id: prismaBoard.name,
      name: prismaBoard.name,
      width: prismaBoard.width,
      height: prismaBoard.height,
      recommendedPlayers: 2,
      imageUrl: prismaBoard.imageUrl || undefined,
      spaces,
    };
  }

  // ==================== Prisma Parsing Helpers ====================

  private parsePrismaAbility(ability: any): any[] {
    if (!ability) return [];

    let abilities: any[] = [];

    if (typeof ability === 'string') {
      try {
        const parsed = JSON.parse(ability);
        abilities = Array.isArray(parsed) ? parsed : [parsed];
      } catch {
        // Если не JSON, возвращаем пустой массив или способность из текста
        return [{
          id: 'default-ability',
          name: 'Ability',
          text: ability,
          trigger: 'passive',
        }];
      }
    } else if (Array.isArray(ability)) {
      abilities = ability;
    } else {
      abilities = [ability];
    }

    // Нормализуем способности, гарантируя наличие нужных полей
    return abilities.map((a, index) => ({
      id: a?.id || a?.name?.toLowerCase().replace(/\s+/g, '-') || `ability-${index}`,
      name: a?.name || a?.title || 'Ability',
      text: a?.text || a?.description || '',
      trigger: this.normalizeAbilityTrigger(a?.trigger) || 'passive',
    }));
  }

  private normalizeAbilityTrigger(trigger: string): string {
    if (!trigger) return 'passive';
    // Конвертируем в snake_case и нижний регистр
    const normalized = trigger
      .toString()
      .toUpperCase()
      .replace(/ /g, '_');
    // Соответствие с enum values
    const triggerMap: Record<string, string> = {
      'START_OF_TURN': 'start_of_turn',
      'DURING_COMBAT': 'during_combat',
      'PASSIVE': 'passive',
      'WHEN_ATTACKED': 'when_attacked',
      'WHEN_DEFENDING': 'when_defending',
      'END_OF_TURN': 'end_of_turn',
    };
    return triggerMap[normalized] || normalized.toLowerCase();
  }

  private parseFighterType(type: string): FighterType {
    if (!type) return FighterType.HERO;
    const normalized = type.toLowerCase();
    if (normalized === 'minion' || normalized === 'sidekick') {
      return FighterType.SIDEKICK;
    }
    return FighterType.HERO;
  }

  private parseSidekickCount(properties: any): number | undefined {
    if (!properties) return undefined;
    if (typeof properties === 'string') {
      try {
        const parsed = JSON.parse(properties);
        return parsed.sidekickCount;
      } catch {
        return undefined;
      }
    }
    return properties.sidekickCount;
  }

  private parseSidekickHealth(properties: any): number | undefined {
    if (!properties) return undefined;
    if (typeof properties === 'string') {
      try {
        const parsed = JSON.parse(properties);
        return parsed.sidekickHealth;
      } catch {
        return undefined;
      }
    }
    return properties.sidekickHealth;
  }

  private parseHeroUrls(prismaHero: Hero): HeroUrls | undefined {
    if (!prismaHero.avatarUrl) return undefined;

    return {
      avatar: prismaHero.avatarUrl,
      mini: prismaHero.imageUrl || prismaHero.avatarUrl,
      cardCover: prismaHero.imageUrl || prismaHero.avatarUrl,
    };
  }

  private parsePrismaEffects(effects: any): any[] {
    if (!effects) return [];

    let parsedEffects: any[] = [];

    if (typeof effects === 'string') {
      try {
        const parsed = JSON.parse(effects);
        parsedEffects = Array.isArray(parsed) ? parsed : [parsed];
      } catch {
        return [];
      }
    } else if (Array.isArray(effects)) {
      parsedEffects = effects;
    } else {
      parsedEffects = [effects];
    }

    // Нормализуем timing к snake_case
    const normalizeTiming = (timing: string): string => {
      if (!timing) return 'during_combat';
      // Конвертируем UPPER_CASE или camelCase в snake_case
      return timing
        .replace(/([A-Z])/g, '_$1')
        .toLowerCase()
        .replace(/^_/, '')
        .replace(/_+/g, '_');
    };

    return parsedEffects.map((e) => ({
      ...e,
      timing: normalizeTiming(e.timing),
    }));
  }

  private parseCardType(type: string): CardType {
    if (!type) return CardType.VERSATILE;
    const typeMap: Record<string, CardType> = {
      'attack': CardType.ATTACK,
      'ATTACK': CardType.ATTACK,
      'defense': CardType.DEFENSE,
      'DEFENSE': CardType.DEFENSE,
      'scheme': CardType.SCHEME,
      'SCHEME': CardType.SCHEME,
      'versatile': CardType.VERSATILE,
      'VERSATILE': CardType.VERSATILE,
      'universal': CardType.VERSATILE,
      'UNIVERSAL': CardType.VERSATILE,
    };
    return typeMap[type] || CardType.VERSATILE;
  }

  private parsePrismaCells(cells: any): any[] {
    if (!cells) return [];
    if (typeof cells === 'string') {
      try {
        return JSON.parse(cells);
      } catch {
        return [];
      }
    }
    return cells;
  }

  /**
   * Алиасы zone-ключей scraped-data → базовый Zone enum.
   * Покрывает синонимы ("violet"→purple, "grey"→gray) и опечатки источника
   * ("biege"→beige). Варианты оттенков ("blue-dark", "green-light",
   * "brown-ligt") сводятся к базовому цвету по токенам в normalizeZone.
   */
  private static readonly ZONE_ALIASES: Record<string, Zone> = {
    blue: Zone.BLUE,
    green: Zone.GREEN,
    yellow: Zone.YELLOW,
    red: Zone.RED,
    purple: Zone.PURPLE,
    violet: Zone.PURPLE,
    brown: Zone.BROWN,
    gray: Zone.GRAY,
    grey: Zone.GRAY,
    orange: Zone.ORANGE,
    pink: Zone.PINK,
    white: Zone.WHITE,
    gold: Zone.GOLD,
    beige: Zone.BEIGE,
    biege: Zone.BEIGE,
  };

  /**
   * Нормализует один zone-ключ к Zone enum или null (неизвестное → дроп).
   * Без этого GraphQL-сериализация enum [Zone] падала на любом ключе вне
   * enum (например "biege") и роняла ВЕСЬ boards query.
   */
  private normalizeZone(raw: unknown): Zone | null {
    if (typeof raw !== 'string') return null;
    const s = raw.toLowerCase().trim();
    const direct = ContentMapper.ZONE_ALIASES[s];
    if (direct) return direct;
    // Варианты вида "blue-dark"/"dark-blue"/"brown-ligt": берём первый
    // распознанный цветовой токен.
    for (const token of s.split(/[-_\s]+/)) {
      const mapped = ContentMapper.ZONE_ALIASES[token];
      if (mapped) return mapped;
    }
    return null;
  }

  /**
   * Нормализует массив zone-ключей клетки: дропает неизвестные, убирает
   * дубликаты (после сведения вариантов к базовому цвету).
   */
  private normalizeZones(zones: unknown): Zone[] {
    if (!Array.isArray(zones)) return [];
    const out: Zone[] = [];
    for (const z of zones) {
      const zone = this.normalizeZone(z);
      if (zone && !out.includes(zone)) out.push(zone);
    }
    return out;
  }
}
