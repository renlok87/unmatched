import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule } from '@nestjs/throttler';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import configuration from './config/configuration';
import { PrismaModule } from './database';
import { RedisModule } from './redis';
import { GraphqlModule } from './graphql';
import { AuthModule } from './auth';
import { UsersModule } from './users';
import { ContentModule } from './content';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [configuration],
      envFilePath: ['.env', '.env.local', '.env.docker'],
    }),
    // Rate limiting для защиты от brute force и спама
    ThrottlerModule.forRoot([{
      ttl: 60000,      // 60 секунд
      limit: 10,       // 10 запросов
    }]),
    PrismaModule,
    RedisModule,
    GraphqlModule,
    AuthModule,
    UsersModule,
    ContentModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
