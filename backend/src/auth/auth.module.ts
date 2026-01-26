import { Module } from '@nestjs/common';
import { JwtModule } from '@nestjs/jwt';
import { PassportModule } from '@nestjs/passport';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { AuthResolver } from './auth.resolver';
import { AuthService } from './auth.service';
import { JwtStrategy, RefreshStrategy } from './strategies';
import { GqlAuthGuard } from './guards/gql-auth.guard';
import { PrismaModule } from '../database/prisma.module';
import { RedisModule } from '../redis/redis.module';

@Module({
  imports: [
    PrismaModule,
    RedisModule,
    PassportModule.register({ defaultStrategy: 'jwt' }),
    JwtModule.registerAsync({
      imports: [ConfigModule],
      inject: [ConfigService],
      useFactory: async (configService: ConfigService) => ({
        secret: configService.get<string>('jwt.secret') || 'default-secret-key',
        signOptions: {
          expiresIn: (configService.get<string>('jwt.expiresIn') || '1h') as any,
        },
      }),
    }),
  ],
  providers: [
    AuthResolver,
    AuthService,
    JwtStrategy,
    RefreshStrategy,
    GqlAuthGuard,
  ],
  exports: [AuthService, GqlAuthGuard],
})
export class AuthModule {}
