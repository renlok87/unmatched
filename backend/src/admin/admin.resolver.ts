import { Resolver, Query, Mutation, Args, Int } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { AdminGuard, ModeratorGuard } from './guards/admin.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { AdminService } from './admin.service';
import { AuditService } from '../audit/audit.service';
import {
  CreateHeroInput,
  UpdateHeroInput,
  CreateCardInput,
  UpdateCardInput,
  CreateBoardInput,
  UpdateBoardInput,
  UpdateUserInput,
  AdminStatsDto,
  PaginatedUsersDto,
  CardsPaginatedDto,
  GamesPaginatedDto,
  AdminGameDto,
  AuditLogsPaginatedDto,
  MatchmakingQueueDto,
  HeroesPaginatedDto,
  BoardsPaginatedDto,
  UserDto,
  AdminHeroDto,
  AdminCardDto,
  AdminBoardDto,
  CleanupGamesInput,
  CleanupGamesResultDto,
} from './dto/admin.dto';

/**
 * Admin Resolver
 * Все мутации требуют прав администратора
 * Query для чтения требуют только авторизации
 */
@Resolver()
export class AdminResolver {
  constructor(
    private readonly adminService: AdminService,
    private readonly auditService: AuditService,
  ) {}

  // ============================================
  // STATS (ADMIN ONLY)
  // ============================================

  @Query(() => AdminStatsDto, { name: 'adminStats' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async getStats(): Promise<AdminStatsDto> {
    return await this.adminService.getStats();
  }

  // ============================================
  // HEROES (ADMIN ONLY MUTATIONS)
  // ============================================

  @Query(() => AdminHeroDto, { name: 'adminHero' })
  @UseGuards(GqlAuthGuard)
  async getHero(@Args('id') id: string) {
    return await this.adminService.getHero(id);
  }

  @Mutation(() => AdminHeroDto, { name: 'createHero' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async createHero(@Args('input') input: CreateHeroInput) {
    return await this.adminService.createHero(input);
  }

  @Mutation(() => AdminHeroDto, { name: 'updateHero' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async updateHero(
    @Args('id') id: string,
    @Args('input') input: UpdateHeroInput,
  ) {
    return await this.adminService.updateHero(id, input);
  }

  @Mutation(() => Boolean, { name: 'deleteHero' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async deleteHero(@Args('id') id: string): Promise<boolean> {
    return await this.adminService.deleteHero(id);
  }

  // ============================================
  // CARDS (ADMIN ONLY MUTATIONS)
  // ============================================

  @Query(() => AdminCardDto, { name: 'adminCard' })
  @UseGuards(GqlAuthGuard)
  async getCard(@Args('id') id: string) {
    return await this.adminService.getCard(id);
  }

  @Mutation(() => AdminCardDto, { name: 'createCard' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async createCard(@Args('input') input: CreateCardInput) {
    return await this.adminService.createCard(input);
  }

  @Mutation(() => AdminCardDto, { name: 'updateCard' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async updateCard(
    @Args('id') id: string,
    @Args('input') input: UpdateCardInput,
  ) {
    return await this.adminService.updateCard(id, input);
  }

  @Mutation(() => Boolean, { name: 'deleteCard' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async deleteCard(@Args('id') id: string): Promise<boolean> {
    return await this.adminService.deleteCard(id);
  }

  // ============================================
  // BOARDS (ADMIN ONLY MUTATIONS)
  // ============================================

  @Query(() => AdminBoardDto, { name: 'adminBoard' })
  @UseGuards(GqlAuthGuard)
  async getBoard(@Args('id') id: string) {
    return await this.adminService.getBoard(id);
  }

  @Mutation(() => AdminBoardDto, { name: 'createBoard' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async createBoard(@Args('input') input: CreateBoardInput) {
    return await this.adminService.createBoard(input);
  }

  @Mutation(() => AdminBoardDto, { name: 'updateBoard' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async updateBoard(
    @Args('id') id: string,
    @Args('input') input: UpdateBoardInput,
  ) {
    return await this.adminService.updateBoard(id, input);
  }

  @Mutation(() => Boolean, { name: 'deleteBoard' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async deleteBoard(@Args('id') id: string): Promise<boolean> {
    return await this.adminService.deleteBoard(id);
  }

  // ============================================
  // USERS (AUTH REQUIRED FOR READ, ADMIN FOR MUTATIONS)
  // ============================================

  @Query(() => UserDto, { name: 'adminUser' })
  @UseGuards(GqlAuthGuard)
  async getUser(@Args('id') id: string) {
    return await this.adminService.getUser(id);
  }

  @Query(() => PaginatedUsersDto, { name: 'usersList' })
  @UseGuards(GqlAuthGuard)
  async getUsersList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getUsers(page, limit, search, sortBy, sortOrder);
  }

  // Alias для Refine (singular form)
  @Query(() => PaginatedUsersDto, { name: 'userList' })
  @UseGuards(GqlAuthGuard)
  async getUserList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getUsers(page, limit, search, sortBy, sortOrder);
  }

  @Mutation(() => UserDto, { name: 'updateUser' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async updateUser(
    @Args('id') id: string,
    @Args('input') input: UpdateUserInput,
  ) {
    return await this.adminService.updateUser(id, input);
  }

  @Mutation(() => Boolean, { name: 'banUser' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async banUser(@Args('id') id: string): Promise<boolean> {
    return await this.adminService.banUser(id);
  }

  @Mutation(() => Boolean, { name: 'unbanUser' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async unbanUser(@Args('id') id: string): Promise<boolean> {
    return await this.adminService.unbanUser(id);
  }

  // ============================================
  // CARDS LIST (NEW - AUTH REQUIRED)
  // ============================================

  @Query(() => CardsPaginatedDto, { name: 'cardsList' })
  @UseGuards(GqlAuthGuard)
  async getCardsList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('heroId', { nullable: true, type: () => String }) heroId?: string,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllCards(page, limit, heroId, search, sortBy, sortOrder);
  }

  // Alias для Refine (singular form)
  @Query(() => CardsPaginatedDto, { name: 'cardList' })
  @UseGuards(GqlAuthGuard)
  async getCardList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('heroId', { nullable: true, type: () => String }) heroId?: string,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllCards(page, limit, heroId, search, sortBy, sortOrder);
  }

  // ============================================
  // HEROES LIST (AUTH REQUIRED)
  // ============================================

  @Query(() => HeroesPaginatedDto, { name: 'heroesList' })
  @UseGuards(GqlAuthGuard)
  async getHeroesList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllHeroes(page, limit, search, sortBy, sortOrder);
  }

  // Alias для Refine (singular form)
  @Query(() => HeroesPaginatedDto, { name: 'heroList' })
  @UseGuards(GqlAuthGuard)
  async getHeroList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllHeroes(page, limit, search, sortBy, sortOrder);
  }

  // ============================================
  // BOARDS LIST (AUTH REQUIRED)
  // ============================================

  @Query(() => BoardsPaginatedDto, { name: 'boardsList' })
  @UseGuards(GqlAuthGuard)
  async getBoardsList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllBoards(page, limit, search, sortBy, sortOrder);
  }

  // Alias для Refine (singular form)
  @Query(() => BoardsPaginatedDto, { name: 'boardList' })
  @UseGuards(GqlAuthGuard)
  async getBoardList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllBoards(page, limit, search, sortBy, sortOrder);
  }

  // ============================================
  // GAMES LIST (NEW - AUTH REQUIRED)
  // ============================================

  @Query(() => GamesPaginatedDto, { name: 'gamesList' })
  @UseGuards(GqlAuthGuard)
  async getGamesList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllGames(page, limit, search, sortBy, sortOrder);
  }

  // Alias для Refine (singular form)
  @Query(() => GamesPaginatedDto, { name: 'gameList' })
  @UseGuards(GqlAuthGuard)
  async getGameList(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('search', { nullable: true, type: () => String }) search?: string,
    @Args('sortBy', { nullable: true, type: () => String }) sortBy?: string,
    @Args('sortOrder', { nullable: true, type: () => String }) sortOrder?: 'asc' | 'desc',
  ) {
    return await this.adminService.getAllGames(page, limit, search, sortBy, sortOrder);
  }

  @Query(() => AdminGameDto, { name: 'adminGame' })
  @UseGuards(GqlAuthGuard)
  async getGame(@Args('id') id: string) {
    return await this.adminService.getGameById(id);
  }

  @Mutation(() => CleanupGamesResultDto, { name: 'cleanupGames' })
  @UseGuards(GqlAuthGuard, AdminGuard)
  async cleanupGames(
    @Args('input', { nullable: true }) input?: CleanupGamesInput,
  ): Promise<CleanupGamesResultDto> {
    return await this.adminService.cleanupGames(input ?? {});
  }

  // ============================================
  // AUDIT LOGS (NEW - MODERATOR REQUIRED)
  // ============================================

  @Query(() => AuditLogsPaginatedDto, { name: 'auditLogs' })
  @UseGuards(GqlAuthGuard, ModeratorGuard)
  async getAuditLogs(
    @Args('page', { type: () => Int, nullable: true }) page?: number,
    @Args('limit', { type: () => Int, nullable: true }) limit?: number,
    @Args('userId', { nullable: true, type: () => String }) userId?: string,
  ) {
    const take = limit || 50;
    const skip = ((page || 1) - 1) * take;

    const { items, total } = await this.auditService.getAuditLogsPaginated(
      { userId },
      skip,
      take,
    );

    return {
      items: items.map((log) => {
        // У модели AuthAuditLog нет колонки metadata — собираем из реальных полей
        const metadata: Record<string, string> = {};
        if (log.userAgent) metadata.userAgent = log.userAgent;
        if (log.errorMessage) metadata.errorMessage = log.errorMessage;

        return {
          id: log.id || '',
          action: log.type,
          userId: log.userId,
          ipAddress: log.ipAddress,
          userAgent: log.userAgent,
          success: log.success,
          errorMessage: log.errorMessage,
          timestamp: log.timestamp,
          metadata: Object.keys(metadata).length > 0 ? JSON.stringify(metadata) : null,
        };
      }),
      total,
    };
  }

  // ============================================
  // MATCHMAKING QUEUE (NEW - AUTH REQUIRED)
  // ============================================

  @Query(() => MatchmakingQueueDto, { name: 'matchmakingQueue' })
  @UseGuards(GqlAuthGuard)
  async getMatchmakingQueue() {
    return await this.adminService.getMatchmakingQueue();
  }
}
