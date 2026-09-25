import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { BullModule } from '@nestjs/bullmq';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import configuration from './config/configuration';
import { PrismaModule } from './database';
import { RedisModule } from './redis';
import { GraphqlModule } from './graphql';
import { AuthModule } from './auth';
import { UsersModule } from './users';
import { ContentModule } from './content';
import { LobbyModule } from './lobby';
import { GameEngineModule } from './game-engine';
import { CacheModule } from './cache';
import { HealthModule } from './health';
import { CommonModule } from './common/common.module';
import { GamesModule } from './games/games.module';
import { MatchmakingModule } from './matchmaking';
import { PresenceModule } from './presence';
import { AuditModule } from './audit/audit.module';
import { AdminModule } from './admin/admin.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [configuration],
      envFilePath: ['.env', '.env.local', '.env.docker'],
    }),
    // BullMQ for background jobs
    BullModule.forRootAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: (configService: ConfigService) => ({
        connection: {
          host: configService.get<string>('REDIS_HOST') || 'localhost',
          port: parseInt(configService.get<string>('REDIS_PORT') || '6379', 10),
          password: configService.get<string>('REDIS_PASSWORD'),
          connectTimeout: 5000,
          maxRetriesPerRequest: null,
          retryStrategy: () => {
            return null;
          },
        },
        defaultJobOptions: {
          removeOnComplete: true,
          removeOnFail: true,
        },
      }),
    }),
    // Rate limiting для защиты от brute force и спама.
    // Единственная регистрация в приложении: THROTTLER:MODULE_OPTIONS —
    // статический токен, второй ThrottlerModule.forRoot перезаписал бы его.
    // setHeaders: false — GraphQL-контекст не несёт express-res.
    ThrottlerModule.forRoot({
      throttlers: [{ ttl: 60000, limit: 10 }],
      setHeaders: false,
    }),
    PrismaModule,
    RedisModule,
    GraphqlModule,
    AuthModule,
    UsersModule,
    ContentModule,
    AdminModule,
    // Новая архитектура модулей
    CommonModule, // Общие сервисы и декораторы
    GamesModule, // Игровые мутации и подписки
    LobbyModule, // CRUD игр, лобби
    GameEngineModule, // Игровой движок
    MatchmakingModule, // Автоматический матчмейкинг
    PresenceModule, // Online presence
    AuditModule, // Security audit logging
    CacheModule, // Cache warming
    HealthModule, // Health checks
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
