import { Resolver, Query, Args, Parent, ResolveField, Int } from '@nestjs/graphql';
import { Public } from '../common/decorators';
import { ContentDbService } from './content-db.service';
import { ContentMapper } from './mappers/content.mapper';
import type { HeroDefinition, CardDefinition, BoardDefinition } from './interfaces';
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
    private readonly contentDbService: ContentDbService,
    private readonly mapper: ContentMapper,
  ) {}

  @ResolveField(() => [CardDto], { name: 'cards' })
  async getCards(@Parent() hero: HeroDto): Promise<CardDto[]> {
    const fullHero = await this.contentDbService.getHeroBySlug(hero.id);
    return fullHero.deckCards.map((c) => this.mapper.toCardDto(c));
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
    private readonly contentDbService: ContentDbService,
    private readonly mapper: ContentMapper,
  ) {}

  /**
   * Get all available heroes
   */
  @Query(() => [HeroDto], { name: 'heroes' })
  @Public()
  async getAllHeroes(): Promise<HeroDefinition[]> {
    return this.contentDbService.getAllHeroes();
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
    return this.contentDbService.getHeroesPaginated(page || 1, limit || 10, set);
  }

  /**
   * Get a hero by ID
   */
  @Query(() => HeroDto, { name: 'hero', nullable: true })
  @Public()
  async getHero(@Args('id') id: string): Promise<HeroDefinition | null> {
    try {
      return await this.contentDbService.getHeroBySlug(id);
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
    return this.contentDbService.getCardsByHero(heroId);
  }

  /**
   * Get a single card by ID (from database)
   */
  @Query(() => CardDto, { name: 'card', nullable: true })
  @Public()
  async getCard(@Args('id') id: string): Promise<CardDto | null> {
    const cardDefinition = await this.contentDbService.getCardById(id);
    if (!cardDefinition) {
      return null;
    }
    return this.mapper.toCardDto(cardDefinition);
  }

  /**
   * Get all available boards
   */
  @Query(() => [BoardDto], { name: 'boards' })
  @Public()
  async getAllBoards(): Promise<BoardDefinition[]> {
    return this.contentDbService.getAllBoards();
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
    return this.contentDbService.getBoardsPaginated(page || 1, limit || 10);
  }

  /**
   * Get a board by ID
   */
  @Query(() => BoardDto, { name: 'board', nullable: true })
  @Public()
  async getBoard(@Args('id') id: string): Promise<BoardDefinition | null> {
    try {
      return await this.contentDbService.getBoardBySlug(id);
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
    return this.contentDbService.getCurrentVersion();
  }

  /**
   * Get all available expansion sets
   */
  @Query(() => [String], { name: 'sets' })
  @Public()
  async getAllSets(): Promise<string[]> {
    return this.contentDbService.getAllSets();
  }

  /**
   * Get heroes by expansion set
   */
  @Query(() => [HeroDto], { name: 'heroesBySet' })
  @Public()
  async getHeroesBySet(@Args('set') set: string): Promise<HeroDefinition[]> {
    return this.contentDbService.getHeroesBySet(set);
  }

  /**
   * Get content summary
   */
  @Query(() => ContentSummaryDto, { name: 'contentSummary' })
  @Public()
  async getContentSummary() {
    return this.contentDbService.getContentSummary();
  }

  /**
   * Clear content cache (admin only)
   */
  @Query(() => Boolean, { name: 'clearContentCache' })
  @Public()
  async clearCache(): Promise<boolean> {
    await this.contentDbService.clearCache();
    return true;
  }
}
