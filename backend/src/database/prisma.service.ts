import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { PrismaClient } from '@prisma/client';

@Injectable()
export class PrismaService extends PrismaClient implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(PrismaService.name);

  constructor() {
    super({
      log: [
        { level: 'query', emit: 'event' },
        { level: 'error', emit: 'stdout' },
        { level: 'warn', emit: 'stdout' },
      ],
    });
  }

  async onModuleInit() {
    let retries = 0;
    const maxRetries = 5;

    while (retries < maxRetries) {
      try {
        await this.$connect();
        this.logger.log('Database connected successfully');
        return;
      } catch (error) {
        retries++;
        this.logger.error(
          `Failed to connect to database (attempt ${retries}/${maxRetries})`,
          error,
        );

        if (retries >= maxRetries) {
          throw error;
        }

        // Wait 5 seconds before retrying
        await new Promise((resolve) => setTimeout(resolve, 5000));
      }
    }
  }

  async onModuleDestroy() {
    await this.$disconnect();
    this.logger.log('Database disconnected');
  }

  async cleanDatabase() {
    if (process.env.NODE_ENV === 'production') {
      throw new Error('Cannot clean database in production!');
    }

    // Models in dependency order - напрямую вызываем deleteMany для каждой модели
    return Promise.all([
      this.gameAction.deleteMany(),
      this.gameState.deleteMany(),
      this.gamePlayer.deleteMany(),
      this.game.deleteMany(),
      this.leaderboardEntry.deleteMany(),
      this.matchmakingQueueEntry.deleteMany(),
      this.card.deleteMany(),
      this.hero.deleteMany(),
      this.board.deleteMany(),
      this.userStats.deleteMany(),
      this.userSettings.deleteMany(),
      this.presence.deleteMany(),
      this.user.deleteMany(),
    ]);
  }
}
