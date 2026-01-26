import { Module } from '@nestjs/common';
import { GameResolver } from './game.resolver';
import { GameService } from './game.service';
import { GameStateService } from './game-state.service';
import { PrismaModule } from '../database/prisma.module';
import { RedisModule } from '../redis/redis.module';

@Module({
  imports: [PrismaModule, RedisModule],
  providers: [
    // Resolvers
    GameResolver,

    // Services
    GameService,
    GameStateService,
  ],
  exports: [GameService, GameStateService],
})
export class GamesModule {}
