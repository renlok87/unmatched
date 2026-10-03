import { Injectable, NotFoundException, Logger } from '@nestjs/common';
import { RedisService } from '../redis';
import type { HeroDefinition, CardDefinition } from './interfaces';
import { ContentMapper } from './mappers/content.mapper';
import { getAllHeroes, getHeroDefinition, getHeroesBySet } from './data/heroes';
import type { PaginatedHeroesDto, PaginationInfoDto } from './dto/content.dto';

/**
 * Content version for cache invalidation
 * Increment when content changes
 */
const CONTENT_VERSION = '1.0.0';

/**
 * Cache TTL in seconds (1 hour)
 */
const CACHE_TTL = 3600;

/**
 * Cache keys
 */
const CACHE_KEYS = {
  ALL_HEROES: 'content:heroes:all',
  ALL_BOARDS: 'content:boards:all',
  HERO_BY_ID: (id: string) => `content:heroes:${id}`,
  HEROES_BY_SET: (set: string) => `content:heroes:set:${set}`,
  ALL_SETS: 'content:sets:all',
  SUMMARY: 'content:summary',
} as const;

/**
 * Static hero content (data/heroes). Boards, the content summary and the content diff are served from the
 * database by ContentDbService; the static Cobble City registry was removed with the synthetic boards
 * (docs/game-design/decisions/2026-10-04-real-boards-only.md).
 */
@Injectable()
export class ContentService {
  private readonly logger = new Logger(ContentService.name);

  constructor(
    private readonly redisService: RedisService,
    private readonly mapper: ContentMapper,
  ) {}

  // ==================== Cache Helpers ====================

  private async getFromCache<T>(key: string): Promise<T | null> {
    try {
      const cached = await this.redisService.get(key);
      return cached ? (JSON.parse(cached) as T) : null;
    } catch (error) {
      this.logger.warn(`Cache get failed for key ${key}:`, error);
      return null;
    }
  }

  private async setCache<T>(key: string, value: T): Promise<void> {
    try {
      await this.redisService.setex(key, CACHE_TTL, JSON.stringify(value));
    } catch (error) {
      this.logger.warn(`Cache set failed for key ${key}:`, error);
    }
  }

  private async invalidatePattern(pattern: string): Promise<void> {
    try {
      // Note: This requires Redis SCAN implementation or simple key deletion
      await this.redisService.del(pattern);
    } catch (error) {
      this.logger.warn(`Cache invalidation failed for pattern ${pattern}:`, error);
    }
  }

  // ==================== Content Version ====================

  /**
   * Get current content version
   */
  getCurrentVersion(): string {
    return CONTENT_VERSION;
  }

  // ==================== Heroes ====================

  /**
   * Get all available heroes (with cache)
   */
  async getAllHeroes(): Promise<HeroDefinition[]> {
    const cacheKey = CACHE_KEYS.ALL_HEROES;
    const cached = await this.getFromCache<HeroDefinition[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const heroes = getAllHeroes();
    await this.setCache(cacheKey, heroes);
    return heroes;
  }

  /**
   * Get paginated heroes
   */
  async getHeroesPaginated(
    page: number = 1,
    limit: number = 10,
    set?: string,
  ): Promise<PaginatedHeroesDto> {
    const heroes = set ? getHeroesBySet(set) : await this.getAllHeroes();

    const total = heroes.length;
    const totalPages = Math.ceil(total / limit);
    const validPage = Math.max(1, Math.min(page, totalPages || 1));
    const offset = (validPage - 1) * limit;

    const items = heroes.slice(offset, offset + limit);
    const pagination: PaginationInfoDto = {
      total,
      page: validPage,
      limit,
      totalPages,
      hasNextPage: validPage < totalPages,
      hasPreviousPage: validPage > 1,
    };

    return {
      items: items.map((h) => this.mapper.toHeroDto(h)),
      pagination,
    };
  }

  /**
   * Get a hero by ID (with cache)
   * @throws NotFoundException if hero not found
   */
  async getHeroById(id: string): Promise<HeroDefinition> {
    const cacheKey = CACHE_KEYS.HERO_BY_ID(id);
    const cached = await this.getFromCache<HeroDefinition>(cacheKey);
    if (cached) {
      return cached;
    }

    try {
      const hero = getHeroDefinition(id);
      await this.setCache(cacheKey, hero);
      return hero;
    } catch (error) {
      throw new NotFoundException(`Hero not found: ${id}`);
    }
  }

  /**
   * Get heroes by expansion set (with cache)
   */
  async getHeroesBySet(set: string): Promise<HeroDefinition[]> {
    const cacheKey = CACHE_KEYS.HEROES_BY_SET(set);
    const cached = await this.getFromCache<HeroDefinition[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const heroes = getHeroesBySet(set);
    await this.setCache(cacheKey, heroes);
    return heroes;
  }

  // ==================== Cards ====================

  /**
   * Get all cards for a specific hero
   */
  async getCardsByHero(heroId: string): Promise<CardDefinition[]> {
    const hero = await this.getHeroById(heroId);
    return hero.deckCards;
  }

  /**
   * Get a specific card by ID
   * Searches through all heroes' decks
   */
  async getCardById(cardId: string): Promise<CardDefinition | null> {
    const heroes = await this.getAllHeroes();
    for (const hero of heroes) {
      const card = hero.deckCards.find((c) => c.id === cardId);
      if (card) {
        return card;
      }
    }
    return null;
  }

  // ==================== Metadata ====================

  /**
   * Get all available expansion sets (with cache)
   */
  async getAllSets(): Promise<string[]> {
    const cacheKey = CACHE_KEYS.ALL_SETS;
    const cached = await this.getFromCache<string[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const heroes = await this.getAllHeroes();
    const sets = new Set(heroes.map((h) => h.set));
    const sortedSets = Array.from(sets).sort();

    await this.setCache(cacheKey, sortedSets);
    return sortedSets;
  }

  // ==================== Cache Management ====================

  /**
   * Clear all content cache
   * Call this when content is updated
   */
  async clearCache(): Promise<void> {
    const keys = [
      CACHE_KEYS.ALL_HEROES,
      CACHE_KEYS.ALL_BOARDS,
      CACHE_KEYS.ALL_SETS,
      CACHE_KEYS.SUMMARY,
    ];

    for (const key of keys) {
      await this.redisService.del(key);
    }

    this.logger.log('Content cache cleared');
  }
}
