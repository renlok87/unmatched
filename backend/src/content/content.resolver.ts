import { Resolver, Query, Args, Parent, ResolveField, Int } from '@nestjs/graphql';
import { Public } from '../common/decorators';
import { ContentService } from './content.service';
import { ContentMapper } from './mappers/content.mapper';
import type {
  HeroDefinition,
  CardDefinition,
  BoardDefinition,
} from './interfaces';
import {
  HeroDto,
  CardDto,
  BoardDto,
  BoardSpaceDto,
  ContentSummaryDto,
  PaginatedHeroesDto,
  PaginatedBoardsDto,
} from './dto/content.dto';

// ==================== Field Resolvers ====================

@Resolver(() => HeroDto)
export class HeroResolver {
  constructor(
    private readonly contentService: ContentService,
    private readonly mapper: ContentMapper,
  ) {}

  @ResolveField(() => [CardDto], { name: 'cards' })
  async getCards(@Parent() hero: HeroDto): Promise<CardDto[]> {
    const fullHero = await this.contentService.getHeroById(hero.id);
    return fullHero.deckCards.map(c => this.mapper.toCardDto(c));
  }
}

@Resolver(() => CardDto)
export class CardResolver {}

@Resolver(() => BoardDto)
export class BoardResolver {}

@Resolver(() => BoardSpaceDto)
export class BoardSpaceResolver {}

// ==================== Main Query Resolver ====================

@Resolver()
export class ContentResolver {
  constructor(
    private readonly contentService: ContentService,
    private readonly mapper: ContentMapper,
  ) {}

  /**
   * Get all available heroes
   */
  @Query(() => [HeroDto], { name: 'heroes' })
  @Public()
  async getAllHeroes(): Promise<HeroDefinition[]> {
    return this.contentService.getAllHeroes();
  }

  /**
   * Get paginated heroes
   */
  @Query(() => PaginatedHeroesDto, { name: 'heroesPaginated' })
  @Public()
  async getHeroesPaginated(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('set', { nullable: true }) set?: string,
  ): Promise<PaginatedHeroesDto> {
    return this.contentService.getHeroesPaginated(page || 1, limit || 10, set);
  }

  /**
   * Get a hero by ID
   */
  @Query(() => HeroDto, { name: 'hero', nullable: true })
  @Public()
  async getHero(@Args('id') id: string): Promise<HeroDefinition | null> {
    try {
      return await this.contentService.getHeroById(id);
    } catch {
      return null;
    }
  }

  /**
   * Get cards for a specific hero
   */
  @Query(() => [CardDto], { name: 'cards' })
  @Public()
  async getCards(@Args('heroId') heroId: string): Promise<CardDefinition[]> {
    return this.contentService.getCardsByHero(heroId);
  }

  /**
   * Get all available boards
   */
  @Query(() => [BoardDto], { name: 'boards' })
  @Public()
  async getAllBoards(): Promise<BoardDefinition[]> {
    return this.contentService.getAllBoards();
  }

  /**
   * Get paginated boards
   */
  @Query(() => PaginatedBoardsDto, { name: 'boardsPaginated' })
  @Public()
  async getBoardsPaginated(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
  ): Promise<PaginatedBoardsDto> {
    return this.contentService.getBoardsPaginated(page || 1, limit || 10);
  }

  /**
   * Get a board by ID
   */
  @Query(() => BoardDto, { name: 'board', nullable: true })
  @Public()
  async getBoard(@Args('id') id: string): Promise<BoardDefinition | null> {
    try {
      return await this.contentService.getBoardById(id);
    } catch {
      return null;
    }
  }

  /**
   * Get content version for cache invalidation
   */
  @Query(() => String, { name: 'contentVersion' })
  @Public()
  getContentVersion(): string {
    return this.contentService.getCurrentVersion();
  }

  /**
   * Get all available expansion sets
   */
  @Query(() => [String], { name: 'sets' })
  @Public()
  async getAllSets(): Promise<string[]> {
    return this.contentService.getAllSets();
  }

  /**
   * Get heroes by expansion set
   */
  @Query(() => [HeroDto], { name: 'heroesBySet' })
  @Public()
  async getHeroesBySet(@Args('set') set: string): Promise<HeroDefinition[]> {
    return this.contentService.getHeroesBySet(set);
  }

  /**
   * Get content summary
   */
  @Query(() => ContentSummaryDto, { name: 'contentSummary' })
  @Public()
  async getContentSummary() {
    return this.contentService.getContentSummary();
  }

  /**
   * Clear content cache (admin only)
   */
  @Query(() => Boolean, { name: 'clearContentCache' })
  @Public()
  async clearCache(): Promise<boolean> {
    await this.contentService.clearCache();
    return true;
  }
}
