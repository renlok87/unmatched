import { Injectable, NotFoundException, Logger } from '@nestjs/common';
import { RedisService } from '../redis';
import { PrismaService } from '../database/prisma.service';
import type { HeroDefinition, CardDefinition, BoardDefinition, ContentDiff } from './interfaces';
import { ContentMapper, boardCellsHaveTopology } from './mappers/content.mapper';
import type { PaginatedHeroesDto, PaginatedBoardsDto, PaginationInfoDto } from './dto/content.dto';

/**
 * Content version for cache invalidation
 * Increment when content changes
 */
const CONTENT_VERSION = '2.0.0';

/**
 * Cache TTL in seconds (1 hour)
 */
const CACHE_TTL = 3600;

/**
 * Cache disabled flag from environment
 */
const CACHE_DISABLED = process.env.DISABLE_CACHE === 'true';

/**
 * Cache keys
 */
const CACHE_KEYS = {
  ALL_HEROES: 'content:heroes:all',
  ALL_BOARDS: 'content:boards:all',
  HERO_BY_ID: (id: string) => `content:heroes:${id}`,
  HERO_BY_SLUG: (slug: string) => `content:heroes:slug:${slug}`,
  BOARD_BY_ID: (id: string) => `content:boards:${id}`,
  HEROES_BY_SET: (set: string) => `content:heroes:set:${set}`,
  ALL_SETS: 'content:sets:all',
  SUMMARY: 'content:summary',
} as const;

@Injectable()
export class ContentDbService {
  private readonly logger = new Logger(ContentDbService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly redisService: RedisService,
    private readonly mapper: ContentMapper,
  ) {
    if (CACHE_DISABLED) {
      this.logger.warn('⚠️  Cache DISABLED (DISABLE_CACHE=true)');
    }
  }

  // ==================== Cache Helpers ====================

  private async getFromCache<T>(key: string): Promise<T | null> {
    if (CACHE_DISABLED) {
      return null;
    }
    try {
      const cached = await this.redisService.get(key);
      return cached ? (JSON.parse(cached) as T) : null;
    } catch (error) {
      this.logger.warn(`Cache get failed for key ${key}:`, error);
      return null;
    }
  }

  private async setCache<T>(key: string, value: T): Promise<void> {
    if (CACHE_DISABLED) {
      return;
    }
    try {
      await this.redisService.setex(key, CACHE_TTL, JSON.stringify(value));
    } catch (error) {
      this.logger.warn(`Cache set failed for key ${key}:`, error);
    }
  }

  // ==================== Content Version ====================

  getCurrentVersion(): string {
    return CONTENT_VERSION;
  }

  // ==================== Heroes ====================

  /**
   * Get all available heroes from database (with cache)
   */
  async getAllHeroes(): Promise<HeroDefinition[]> {
    const cacheKey = CACHE_KEYS.ALL_HEROES;
    const cached = await this.getFromCache<HeroDefinition[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const heroes = await this.prisma.hero.findMany({
      include: { cards: true },
      orderBy: { name: 'asc' },
    });

    // Используем prismaHeroToHeroDto для получения всех полей включая imageUrl/avatarUrl
    const heroDtos = heroes.map((h) => this.mapper.prismaHeroToHeroDto(h));
    await this.setCache(cacheKey, heroDtos);
    return heroDtos as any;
  }

  /**
   * Get paginated heroes from database
   */
  async getHeroesPaginated(
    page: number = 1,
    limit: number = 10,
    set?: string,
  ): Promise<PaginatedHeroesDto> {
    const where = set ? { set } : {};

    const [heroes, total] = await Promise.all([
      this.prisma.hero.findMany({
        where,
        include: { cards: true },
        skip: (page - 1) * limit,
        take: limit,
        orderBy: { name: 'asc' },
      }),
      this.prisma.hero.count({ where }),
    ]);

    const totalPages = Math.ceil(total / limit);

    const pagination: PaginationInfoDto = {
      total,
      page,
      limit,
      totalPages,
      hasNextPage: page < totalPages,
      hasPreviousPage: page > 1,
    };

    // Прямое преобразование в HeroDto с всеми полями для админки
    const items = heroes.map((h) => this.mapper.prismaHeroToHeroDto(h));

    return {
      items,
      pagination,
    };
  }

  /**
   * Get a hero by ID from database (with cache)
   * @throws NotFoundException if hero not found
   */
  async getHeroById(id: string): Promise<HeroDefinition> {
    const cacheKey = CACHE_KEYS.HERO_BY_ID(id);
    const cached = await this.getFromCache<HeroDefinition>(cacheKey);
    if (cached) {
      return cached;
    }

    const hero = await this.prisma.hero.findUnique({
      where: { id },
      include: { cards: true },
    });

    if (!hero) {
      throw new NotFoundException(`Hero not found: ${id}`);
    }

    const heroDefinition = this.mapper.prismaHeroToHeroDefinition(hero);
    await this.setCache(cacheKey, heroDefinition);
    return heroDefinition;
  }

  /**
   * Get a hero by slug (name) from database
   */
  async getHeroBySlug(slug: string): Promise<HeroDefinition> {
    const cacheKey = CACHE_KEYS.HERO_BY_SLUG(slug);
    const cached = await this.getFromCache<HeroDefinition>(cacheKey);
    if (cached) {
      return cached;
    }

    const hero = await this.prisma.hero.findFirst({
      where: {
        // Принимаем и cuid-id, и имя: публичный query hero(id) шлёт id из БД,
        // поиск только по name возвращал null для валидных id
        OR: [{ id: slug }, { name: { equals: slug, mode: 'insensitive' } }],
      },
      include: { cards: true },
    });

    if (!hero) {
      throw new NotFoundException(`Hero not found: ${slug}`);
    }

    const heroDefinition = this.mapper.prismaHeroToHeroDefinition(hero);
    await this.setCache(cacheKey, heroDefinition);
    return heroDefinition;
  }

  /**
   * Get heroes by expansion set from database (with cache)
   */
  async getHeroesBySet(set: string): Promise<HeroDefinition[]> {
    const cacheKey = CACHE_KEYS.HEROES_BY_SET(set);
    const cached = await this.getFromCache<HeroDefinition[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const heroes = await this.prisma.hero.findMany({
      where: { set: { equals: set, mode: 'insensitive' } },
      include: { cards: true },
      orderBy: { name: 'asc' },
    });

    const heroDefinitions = heroes.map((h) => this.mapper.prismaHeroToHeroDefinition(h));
    await this.setCache(cacheKey, heroDefinitions);
    return heroDefinitions;
  }

  // ==================== Cards ====================

  /**
   * Get all cards for a specific hero from database
   */
  async getCardsByHero(heroId: string): Promise<CardDefinition[]> {
    const hero = await this.getHeroBySlug(heroId);
    return hero.deckCards;
  }

  /**
   * Get a specific card by ID from database
   */
  async getCardById(cardId: string): Promise<CardDefinition | null> {
    const card = await this.prisma.card.findUnique({
      where: { id: cardId },
    });

    if (!card) {
      return null;
    }

    return this.mapper.prismaCardToCardDefinition(card);
  }

  // ==================== Boards ====================

  /**
   * ENV-MAPS: публичный контентный каталог досок (web-лобби, web-рендер)
   * НЕ отдаёт доски с топологией оригинальной карты (Board.cells с links):
   * web-клиент рисует и валидирует ходы по сетке, а BoardDto не несёт
   * связей — такая доска была бы отрисована и сыграна неверно. Эти доски
   * играются UE-клиентом по графу из состояния игры (boardState), их
   * создают по id (seed-env-map-boards.ts); админка видит их через adminBoards.
   */
  private async findCatalogBoards() {
    const boards = await this.prisma.board.findMany({
      orderBy: { name: 'asc' },
    });
    return boards.filter((b) => !boardCellsHaveTopology(b.cells));
  }

  /**
   * Get all available boards from database (with cache)
   */
  async getAllBoards(): Promise<BoardDefinition[]> {
    const cacheKey = CACHE_KEYS.ALL_BOARDS;
    const cached = await this.getFromCache<BoardDefinition[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const boards = await this.findCatalogBoards();

    const boardDefinitions = boards.map((b) => this.mapper.prismaBoardToBoardDefinition(b));
    await this.setCache(cacheKey, boardDefinitions);
    return boardDefinitions;
  }

  /**
   * Get paginated boards from database
   */
  async getBoardsPaginated(
    page: number = 1,
    limit: number = 10,
  ): Promise<PaginatedBoardsDto> {
    // Фильтр каталога (топология) — в памяти: досок единицы-десятки
    const catalog = await this.findCatalogBoards();
    const total = catalog.length;
    const boards = catalog.slice((page - 1) * limit, (page - 1) * limit + limit);

    const totalPages = Math.ceil(total / limit);

    const pagination: PaginationInfoDto = {
      total,
      page,
      limit,
      totalPages,
      hasNextPage: page < totalPages,
      hasPreviousPage: page > 1,
    };

    return {
      items: boards.map((b) => this.mapper.prismaBoardToBoardDefinition(b)),
      pagination,
    };
  }

  /**
   * Get a board by ID from database (with cache)
   * @throws NotFoundException if board not found
   */
  async getBoardById(id: string): Promise<BoardDefinition> {
    const cacheKey = CACHE_KEYS.BOARD_BY_ID(id);
    const cached = await this.getFromCache<BoardDefinition>(cacheKey);
    if (cached) {
      return cached;
    }

    const board = await this.prisma.board.findUnique({
      where: { id },
    });

    // ENV-MAPS: доска с топологией вне публичного каталога (см. findCatalogBoards)
    if (!board || boardCellsHaveTopology(board.cells)) {
      throw new NotFoundException(`Board not found: ${id}`);
    }

    const boardDefinition = this.mapper.prismaBoardToBoardDefinition(board);
    await this.setCache(cacheKey, boardDefinition);
    return boardDefinition;
  }

  /**
   * Get a board by name/slug
   */
  async getBoardBySlug(slug: string): Promise<BoardDefinition> {
    const board = await this.prisma.board.findFirst({
      where: {
        OR: [{ name: { equals: slug, mode: 'insensitive' } }],
      },
    });

    // ENV-MAPS: доска с топологией вне публичного каталога (см. findCatalogBoards)
    if (!board || boardCellsHaveTopology(board.cells)) {
      throw new NotFoundException(`Board not found: ${slug}`);
    }

    return this.mapper.prismaBoardToBoardDefinition(board);
  }

  // ==================== Content Diff ====================

  /**
   * Get content diff for version checking
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
   * Get all available expansion sets from database (with cache)
   */
  async getAllSets(): Promise<string[]> {
    const cacheKey = CACHE_KEYS.ALL_SETS;
    const cached = await this.getFromCache<string[]>(cacheKey);
    if (cached) {
      return cached;
    }

    const sets = await this.prisma.hero.findMany({
      select: { set: true },
      distinct: ['set'],
      orderBy: { set: 'asc' },
    });

    const sortedSets = sets.map((s) => s.set);

    await this.setCache(cacheKey, sortedSets);
    return sortedSets;
  }

  /**
   * Get content summary from database (with cache)
   */
  async getContentSummary() {
    const cacheKey = CACHE_KEYS.SUMMARY;
    const cached = await this.getFromCache(cacheKey);
    if (cached) {
      return cached;
    }

    const [heroesCount, boardsCount, sets] = await Promise.all([
      this.prisma.hero.count(),
      // каталог без досок с топологией (см. findCatalogBoards)
      this.findCatalogBoards().then((boards) => boards.length),
      this.getAllSets(),
    ]);

    const summary = {
      version: CONTENT_VERSION,
      heroesCount,
      boardsCount,
      setsCount: sets.length,
      sets,
    };

    await this.setCache(cacheKey, summary);
    return summary;
  }

  // ==================== Cache Management ====================

  /**
   * Clear all content cache
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
