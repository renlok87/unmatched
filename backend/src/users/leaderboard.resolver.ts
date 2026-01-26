import { Resolver, Query, Args } from '@nestjs/graphql';
import { UserStatsService } from './user-stats.service';
import { LeaderboardEntryResponse, TimeFrame } from './dto';

@Resolver('Leaderboard')
export class LeaderboardResolver {
  constructor(private userStatsService: UserStatsService) {}

  /**
   * Получить таблицу лидеров
   *
   * @param heroId - Опциональный ID героя для фильтрации по герою
   * @param timeFrame - Временной период (all, week, month)
   * @param limit - Лимит записей (по умолчанию 50, максимум 100)
   */
  @Query(() => [LeaderboardEntryResponse], { name: 'leaderboard' })
  async leaderboard(
    @Args({ name: 'heroId', type: () => String, nullable: true }) heroId?: string,
    @Args({ name: 'timeFrame', type: () => TimeFrame, nullable: true }) timeFrame?: TimeFrame,
    @Args({ name: 'limit', type: () => Number, nullable: true }) limit?: number,
  ): Promise<LeaderboardEntryResponse[]> {
    return await this.userStatsService.getLeaderboard({
      heroId,
      timeFrame,
      limit,
    });
  }

  /**
   * Получить топ игроков
   */
  @Query(() => [LeaderboardEntryResponse], { name: 'topPlayers' })
  async topPlayers(
    @Args({ name: 'limit', type: () => Number, nullable: true, defaultValue: 10 }) limit?: number,
  ): Promise<LeaderboardEntryResponse[]> {
    return await this.userStatsService.getLeaderboard({
      limit: limit || 10,
    });
  }

  /**
   * Получить топ игроков для конкретного героя
   */
  @Query(() => [LeaderboardEntryResponse], { name: 'topHeroes' })
  async topHeroes(
    @Args('heroId') heroId: string,
    @Args({ name: 'limit', type: () => Number, nullable: true, defaultValue: 10 }) limit?: number,
  ): Promise<LeaderboardEntryResponse[]> {
    return await this.userStatsService.getLeaderboard({
      heroId,
      limit: limit || 10,
    });
  }
}
