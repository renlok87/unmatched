import { Module } from '@nestjs/common';
import { UsersResolver } from './users.resolver';
import { LeaderboardResolver } from './leaderboard.resolver';
import { UsersService } from './users.service';
import { ProfileService } from './profile.service';
import { UserStatsService } from './user-stats.service';
import { RatingService } from './rating.service';
import { PrismaModule } from '../database/prisma.module';
import { RedisModule } from '../redis/redis.module';

@Module({
  imports: [
    PrismaModule,
    RedisModule,
  ],
  providers: [
    // Resolvers
    UsersResolver,
    LeaderboardResolver,

    // Services
    UsersService,
    ProfileService,
    UserStatsService,
    RatingService,
  ],
  exports: [
    UsersService,
    ProfileService,
    UserStatsService,
    RatingService,
  ],
})
export class UsersModule {}
