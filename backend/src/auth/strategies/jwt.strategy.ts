import { Injectable, UnauthorizedException } from '@nestjs/common';
import { PassportStrategy } from '@nestjs/passport';
import { ExtractJwt, Strategy, StrategyOptionsWithRequest } from 'passport-jwt';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../../database/prisma.service';
import { RedisService } from '../../redis/redis.service';

@Injectable()
export class JwtStrategy extends PassportStrategy(Strategy, 'jwt') {
  constructor(
    private prisma: PrismaService,
    private redis: RedisService,
    private configService: ConfigService,
  ) {
    const options: StrategyOptionsWithRequest = {
      jwtFromRequest: ExtractJwt.fromAuthHeaderAsBearerToken(),
      ignoreExpiration: false,
      secretOrKey: configService.get<string>('jwt.secret') || 'default-secret-key',
      passReqToCallback: true, // Передаём request для получения токена
    };
    super(options);
  }

  async validate(req: any, payload: any) {
    // Получаем токен из заголовка
    const token = ExtractJwt.fromAuthHeaderAsBearerToken()(req);

    // Проверяем blacklist
    if (token && (await this.redis.isBlacklisted(token))) {
      throw new UnauthorizedException('Token revoked');
    }

    const cacheKey = `user:${payload.sub}`;

    // 1. Проверяем кеш
    const cached = await this.redis.getUserFromCache(cacheKey);
    if (cached) {
      return cached;
    }

    // 2. Загружаем из БД
    const user = await this.prisma.user.findUnique({
      where: { id: payload.sub },
      select: {
        id: true,
        email: true,
        username: true,
        avatar: true,
        role: true,
        createdAt: true,
        emailVerified: true,
      },
    });

    if (!user) {
      throw new UnauthorizedException('Пользователь не найден');
    }

    // 3. Сохраняем в кеш на 5 минут
    await this.redis.cacheUser(payload.sub, user, 300);

    return user;
  }
}
