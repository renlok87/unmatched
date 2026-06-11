import { Resolver, Query, Args, Int, ObjectType, Field } from '@nestjs/graphql';
import { LeaderboardService } from '../games/services/leaderboard.service';
import { TimeFrame } from './dto';

@ObjectType()
export class LeaderboardRankResponse {
  @Field(() => Int)
  rank: number;

  @Field()
  userId: string;

  @Field(() => Int)
  elo: number;

  @Field(() => String, { nullable: true })
  heroId?: string;

  @Field()
  timeFrame: string;
}

@Resolver('Leaderboard')
export class LeaderboardResolver {
  constructor(private leaderboardService: LeaderboardService) {}

  @Query(() => String, { name: 'leaderboard' })
  async leaderboard(
    @Args({ name: 'heroId', type: () => String, nullable: true }) heroId?: string,
    @Args({ name: 'timeFrame', type: () => TimeFrame, nullable: true }) timeFrame?: TimeFrame,
    @Args({ name: 'page', type: () => Int, nullable: true }) page?: number,
    @Args({ name: 'pageSize', type: () => Int, nullable: true }) pageSize?: number,
  ): Promise<string> {
    const result = await this.leaderboardService.getLeaderboard({
      heroId,
      timeFrame: (timeFrame as 'all' | 'weekly' | 'monthly') || 'all',
      page: page || 0,
      pageSize: pageSize || 50,
    });
    return JSON.stringify(result);
  }

  @Query(() => String, { name: 'topPlayers' })
  async topPlayers(
    @Args({ name: 'limit', type: () => Int, nullable: true, defaultValue: 10 }) limit?: number,
    @Args({ name: 'timeFrame', type: () => String, nullable: true, defaultValue: 'all' })
    timeFrame?: string,
  ): Promise<string> {
    const result = await this.leaderboardService.getTopPlayers(
      limit || 10,
      (timeFrame as 'all' | 'weekly' | 'monthly') || 'all',
    );
    return JSON.stringify(result);
  }

  @Query(() => LeaderboardRankResponse, { name: 'getPlayerRank' })
  async getPlayerRank(
    @Args('userId') userId: string,
    @Args({ name: 'heroId', type: () => String, nullable: true }) heroId?: string,
    @Args({ name: 'timeFrame', type: () => String, nullable: true, defaultValue: 'all' })
    timeFrame?: string,
  ): Promise<LeaderboardRankResponse> {
    const result = await this.leaderboardService.getPlayerRank(
      userId,
      heroId,
      (timeFrame as 'all' | 'weekly' | 'monthly') || 'all',
    );
    return {
      rank: result.rank,
      userId: result.userId,
      elo: result.elo,
      heroId: result.heroId,
      timeFrame: result.timeFrame,
    };
  }
}
