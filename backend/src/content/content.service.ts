import { Injectable, NotFoundException, Logger } from '@nestjs/common';
import { RedisService } from '../redis';
import type { HeroDefinition, CardDefinition, BoardDefinition, ContentDiff } from './interfaces';
import { ContentMapper } from './mappers/content.mapper';
import { getAllHeroes, getHeroDefinition, getHeroesBySet } from './data/heroes';
import { getAllBoards, getBoardDefinition } from './data/boards';
import type { PaginatedHeroesDto, PaginatedBoardsDto, PaginationInfoDto } from './dto/content.dto';

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
  BOARD_BY_ID: (id: string) => `content:boards:${id}`,
  HEROES_BY_SET: (set: string) => `content:heroes:set:${set}`,
  ALL_SETS: 'content:sets:all',
  SUMMARY: 'content:summary',
} as const;

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

  // ==================== Boards ====================

  /**
   * Get all available boards (with cache)
   */
  async getAllBoards(): Promise<BoardDefinition[]> {
    const cacheKey = CACHE_KEYS.ALL_BOARDS;
    const cached = await this.getFromCache<BoardDefinition[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const boards = getAllBoards();
    await this.setCache(cacheKey, boards);
    return boards;
  }

  /**
   * Get paginated boards
   */
  async getBoardsPaginated(page: number = 1, limit: number = 10): Promise<PaginatedBoardsDto> {
    const boards = await this.getAllBoards();

    const total = boards.length;
    const totalPages = Math.ceil(total / limit);
    const validPage = Math.max(1, Math.min(page, totalPages || 1));
    const offset = (validPage - 1) * limit;

    const items = boards.slice(offset, offset + limit);
    const pagination: PaginationInfoDto = {
      total,
      page: validPage,
      limit,
      totalPages,
      hasNextPage: validPage < totalPages,
      hasPreviousPage: validPage > 1,
    };

    return {
      items: items.map((b) => this.mapper.toBoardDto(b)),
      pagination,
    };
  }

  /**
   * Get a board by ID (with cache)
   * @throws NotFoundException if board not found
   */
  async getBoardById(id: string): Promise<BoardDefinition> {
    const cacheKey = CACHE_KEYS.BOARD_BY_ID(id);
    const cached = await this.getFromCache<BoardDefinition[]>(cacheKey);
    if (cached) {
      return cached as unknown as BoardDefinition;
    }

    try {
      const board = getBoardDefinition(id);
      await this.setCache(cacheKey, board);
      return board;
    } catch (error) {
      throw new NotFoundException(`Board not found: ${id}`);
    }
  }

  /**
   * Get default board
   */
  async getDefaultBoard(): Promise<BoardDefinition> {
    return this.getBoardById('cobble-city');
  }

  // ==================== Content Diff ====================

  /**
   * Get content diff for version checking
   * Returns null if versions match
   */
  async getContentDiff(oldVersion: string): Promise<ContentDiff | null> {
    if (oldVersion === CONTENT_VERSION) {
      return null;
    }

    const heroes = await this.getAllHeroes();
    const boards = await this.getAllBoards();

    return {
      oldVersion,
      newVersion: CONTENT_VERSION,
      heroesChanged: true,
      boardsChanged: true,
      changedHeroIds: heroes.map((h) => h.id),
      changedBoardIds: boards.map((b) => b.id),
    };
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

  /**
   * Get content summary (with cache)
   */
  async getContentSummary() {
    const cacheKey = CACHE_KEYS.SUMMARY;
    const cached = await this.getFromCache(cacheKey);
    if (cached) {
      return cached;
    }

    const heroes = await this.getAllHeroes();
    const boards = await this.getAllBoards();
    const sets = await this.getAllSets();

    const summary = {
      version: CONTENT_VERSION,
      heroesCount: heroes.length,
      boardsCount: boards.length,
      setsCount: sets.length,
      sets,
    };

    await this.setCache(cacheKey, summary);
    return summary;
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
