import { Resolver, Query, Mutation, Args } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { GameService } from './game.service';
import { GameStateService } from './game-state.service';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import { GameResponse, GameStateResponse, EventsSinceResponse } from './models';
import { CreateGameDto, GameFiltersDto, JoinGameDto, GameMode } from './dto';

/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-argument */

@Resolver('Game')
export class GameResolver {
  constructor(
    private gameService: GameService,
    private gameStateService: GameStateService,
  ) {}

  /**
   * Получить игру по ID
   * Требует авторизации для активных игр
   */
  @Query(() => GameResponse, { nullable: true })
  @UseGuards(GqlAuthGuard)
  async game(@Args('id', { type: () => String }) id: string, @CurrentUser() user: any): Promise<GameResponse> {
    // Проверяем доступ к игре
    await this.gameService.checkGameAccess(id, user.id);
    return await this.gameService.getGame(id);
  }

  /**
   * Получить игры текущего пользователя
   */
  @Query(() => [GameResponse], { name: 'myGames' })
  @UseGuards(GqlAuthGuard)
  async getMyGames(
    @CurrentUser() user: any,
    @Args('filters', { nullable: true }) filters?: GameFiltersDto,
  ): Promise<GameResponse[]> {
    return await this.gameService.myGames(user.id, filters);
  }

  /**
   * Получить список доступных для присоединения игр
   */
  @Query(() => [GameResponse], { name: 'availableGames' })
  async getAvailableGames(
    @Args('mode', { nullable: true, type: () => String }) mode?: GameMode,
    @Args('limit', { nullable: true, type: () => Number }) limit?: number,
  ): Promise<GameResponse[]> {
    return await this.gameService.availableGames({ mode, limit });
  }

  /**
   * Получить состояние игры
   * Только участники игры могут видеть состояние
   */
  @Query(() => GameStateResponse, { nullable: true, name: 'gameState' })
  @UseGuards(GqlAuthGuard)
  async getGameState(
    @Args('gameId', { type: () => String }) gameId: string,
    @CurrentUser() user: any,
  ): Promise<GameStateResponse> {
    // Проверяем, что пользователь участвует в игре
    await this.gameService.requireParticipation(gameId, user.id);

    const state = await this.gameStateService.loadState(gameId);

    // Фильтруем приватные данные
    const filteredState = this.gameStateService.filterPrivateData(state, user.id);

    return {
      id: `${gameId}-state`,
      gameId,
      state: JSON.stringify(filteredState),
      sequenceNumber: filteredState.sequenceNumber,
      currentTurnPlayerId: filteredState.currentTurnPlayerId,
      phase: filteredState.phase,
      turnCount: filteredState.turnCount,
      updatedAt: filteredState.metadata.lastActionAt,
    };
  }

  /**
   * Создать новую игру
   * Rate limited: 10 запросов в минуту
   */
  @Mutation(() => GameResponse, { name: 'createGame' })
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 10, ttl: 60000 } })
  async createGame(
    @Args('input') input: CreateGameDto,
    @Args('idempotencyKey', { nullable: true }) idempotencyKey?: string,
    @CurrentUser() user?: any,
  ): Promise<GameResponse> {
    return await this.gameService.createGame(input, user.id, idempotencyKey);
  }

  /**
   * Присоединиться к игре
   * Rate limited: 15 запросов в минуту
   */
  @Mutation(() => GameResponse, { name: 'joinGame' })
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 15, ttl: 60000 } })
  async joinGame(
    @Args('input') input: JoinGameDto,
    @CurrentUser() user: any,
  ): Promise<GameResponse> {
    // Валидируем heroId если указан
    if (input.heroId) {
      await this.gameService.validateHeroId(input.heroId);
    }
    return await this.gameService.joinGame(input.gameId, user.id, input.heroId);
  }

  /**
   * Покинуть игру
   * - Хост: передаёт хостство opponent или удаляет игру
   * - Opponent: просто покидает игру
   * Rate limited: 10 запросов в минуту
   */
  @Mutation(() => Boolean, { name: 'leaveGame' })
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 10, ttl: 60000 } })
  async leaveGame(@Args('gameId', { type: () => String }) gameId: string, @CurrentUser() user: any): Promise<boolean> {
    await this.gameService.leaveGame(gameId, user.id);
    return true;
  }

  /**
   * Начать игру
   * Rate limited: 5 запросов в минуту
   */
  @Mutation(() => GameResponse, { name: 'startGame' })
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async startGame(@Args('gameId', { type: () => String }) gameId: string, @CurrentUser() user: any): Promise<GameResponse> {
    return await this.gameService.startGame(gameId, user.id);
  }

  /**
   * Прервать игру
   * Rate limited: 5 запросов в минуту
   */
  @Mutation(() => GameResponse, { name: 'abortGame' })
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async abortGame(@Args('gameId', { type: () => String }) gameId: string, @CurrentUser() user: any): Promise<GameResponse> {
    return await this.gameService.abortGame(gameId, user.id);
  }

  /**
   * Переключить готовность
   * Rate limited: 20 запросов в минуту
   */
  @Mutation(() => GameResponse, { name: 'toggleReady' })
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 20, ttl: 60000 } })
  async toggleReady(
    @Args('gameId', { type: () => String }) gameId: string,
    @CurrentUser() user: any,
  ): Promise<GameResponse> {
    return await this.gameService.toggleReady(gameId, user.id);
  }

  /**
   * Выбрать героя
   * Rate limited: 10 запросов в минуту
   */
  @Mutation(() => GameResponse, { name: 'selectHero' })
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 10, ttl: 60000 } })
  async selectHero(
    @Args('gameId', { type: () => String }) gameId: string,
    @Args('heroId', { type: () => String }) heroId: string,
    @CurrentUser() user: any,
  ): Promise<GameResponse> {
    return await this.gameService.selectHero(gameId, user.id, heroId);
  }

  /**
   * Получить sequence number для optimistic updates
   */
  @Query(() => Number, { name: 'gameSequence', nullable: true })
  @UseGuards(GqlAuthGuard)
  async getGameSequence(@Args('gameId', { type: () => String }) gameId: string): Promise<number> {
    return await this.gameStateService.getSequenceNumber(gameId);
  }

  /**
   * Получить события игры с указанного sequence number (для catch-up при реконнекте)
   */
  @Query(() => EventsSinceResponse, { name: 'eventsSince', nullable: true })
  @UseGuards(GqlAuthGuard)
  async getEventsSince(
    @Args('gameId', { type: () => String }) gameId: string,
    @Args('sinceSequence', { type: () => Number }) sinceSequence: number,
    @CurrentUser() user: any,
  ): Promise<EventsSinceResponse> {
    await this.gameService.checkGameAccess(gameId, user.id);

    const events = await this.gameStateService.getEventsSince(gameId, sinceSequence);

    return {
      gameId,
      events,
      lastSequence: events.length > 0 ? events[events.length - 1].sequenceNumber : sinceSequence,
      hasMore: events.length >= 100,
    };
  }
}
