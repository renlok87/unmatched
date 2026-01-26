import { Injectable, ConflictException, UnauthorizedException, NotFoundException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import * as bcrypt from 'bcrypt';
import * as crypto from 'crypto';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { RegisterDto, LoginDto } from './dto';

// Фиктивный хеш для Timing Attack Protection
const DUMMY_HASH = '$2b$10$XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX';

@Injectable()
export class AuthService {
  constructor(
    private prisma: PrismaService,
    private jwtService: JwtService,
    private configService: ConfigService,
    private redis: RedisService,
  ) {}

  /**
   * Регистрация нового пользователя
   * Использует транзакцию для целостности данных
   */
  async register(dto: RegisterDto) {
    // Проверяем, существует ли пользователь с таким email
    const existingUserByEmail = await this.prisma.user.findUnique({
      where: { email: dto.email },
    });

    if (existingUserByEmail) {
      throw new ConflictException('Пользователь с таким email уже существует');
    }

    // Проверяем, существует ли пользователь с таким username
    const existingUserByUsername = await this.prisma.user.findUnique({
      where: { username: dto.username },
    });

    if (existingUserByUsername) {
      throw new ConflictException('Пользователь с таким именем уже существует');
    }

    // Хешируем пароль
    const hashedPassword = await bcrypt.hash(dto.password, 10);

    // Генерируем токен верификации email
    const emailVerifiedToken = crypto.randomBytes(32).toString('hex');

    // Используем транзакцию для создания пользователя и связанных записей
    const result = await this.prisma.$transaction(async (tx) => {
      // Создаем пользователя
      const user = await tx.user.create({
        data: {
          email: dto.email,
          username: dto.username,
          password: hashedPassword,
          emailVerifiedToken,
        },
      });

      // Создаем UserSettings и UserStats
      await tx.userSettings.create({
        data: { userId: user.id },
      });

      await tx.userStats.create({
        data: { userId: user.id },
      });

      // Логируем регистрацию
      await tx.authAuditLog.create({
        data: {
          userId: user.id,
          action: 'register',
          success: true,
        },
      });

      return user;
    });

    // Генерируем токены
    const tokens = await this.generateTokens(result.id, result.email);

    // Сохраняем refresh token в БД
    const refreshTokenHash = await bcrypt.hash(tokens.refreshToken, 10);
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 часа

    await this.prisma.refreshToken.create({
      data: {
        token: refreshTokenHash,
        userId: result.id,
        expiresAt,
      },
    });

    return {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      user: {
        id: result.id,
        email: result.email,
        username: result.username,
        avatar: result.avatar,
        createdAt: result.createdAt,
        emailVerified: result.emailVerified,
      },
    };
  }

  /**
   * Вход в систему
   * С защитой от timing attack
   */
  async login(dto: LoginDto, ipAddress?: string, userAgent?: string) {
    // Находим пользователя по email
    const user = await this.prisma.user.findUnique({
      where: { email: dto.email },
    });

    // Timing Attack Protection: всегда выполняем bcrypt.compare
    const isPasswordValid = user
      ? await bcrypt.compare(dto.password, user.password)
      : await bcrypt.compare(dto.password, DUMMY_HASH);

    if (!user || !isPasswordValid) {
      // Логируем неудачную попытку входа
      if (user) {
        await this.prisma.authAuditLog.create({
          data: {
            userId: user.id,
            action: 'login',
            success: false,
            ipAddress,
            userAgent: userAgent?.substring(0, 500),
            errorMessage: 'Invalid password',
          },
        });
      }
      throw new UnauthorizedException('Неверный email или пароль');
    }

    // Генерируем токены
    const tokens = await this.generateTokens(user.id, user.email);

    // Сохраняем refresh token в БД
    const refreshTokenHash = await bcrypt.hash(tokens.refreshToken, 10);
    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 часа

    await this.prisma.refreshToken.create({
      data: {
        token: refreshTokenHash,
        userId: user.id,
        expiresAt,
      },
    });

    // Логируем успешный вход
    await this.prisma.authAuditLog.create({
      data: {
        userId: user.id,
        action: 'login',
        success: true,
        ipAddress,
        userAgent: userAgent?.substring(0, 500),
      },
    });

    return {
      accessToken: tokens.accessToken,
      refreshToken: tokens.refreshToken,
      user: {
        id: user.id,
        email: user.email,
        username: user.username,
        avatar: user.avatar,
        createdAt: user.createdAt,
        emailVerified: user.emailVerified,
      },
    };
  }

  /**
   * Обновление токенов с ротацией refresh token
   */
  async refreshTokens(refreshToken: string) {
    try {
      // 1. Проверяем валидность refresh token
      const payload = await this.jwtService.verifyAsync(refreshToken, {
        secret: this.configService.get<string>('jwt.refreshSecret') || 'default-refresh-secret',
      });

      // 2. Хешируем и ищем в БД
      const tokenHash = await bcrypt.hash(refreshToken, 10);

      const storedToken = await this.prisma.refreshToken.findFirst({
        where: {
          userId: payload.sub,
          revokedAt: null,
        },
        include: { user: true },
        orderBy: { createdAt: 'desc' },
      });

      // Проверяем хеш токена (сравниваем с константой времени для защиты от timing attack)
      let tokenMatch = false;
      if (storedToken) {
        tokenMatch = await bcrypt.compare(refreshToken, storedToken.token);
      }

      if (!storedToken || !tokenMatch || storedToken.revokedAt) {
        throw new UnauthorizedException('Invalid refresh token');
      }

      if (storedToken.expiresAt < new Date()) {
        throw new UnauthorizedException('Refresh token expired');
      }

      // 3. Ревокуем старый токен
      await this.prisma.refreshToken.update({
        where: { id: storedToken.id },
        data: { revokedAt: new Date() },
      });

      // 4. Генерируем новые токены
      const tokens = await this.generateTokens(storedToken.user.id, storedToken.user.email);

      // 5. Сохраняем новый refresh token
      const newTokenHash = await bcrypt.hash(tokens.refreshToken, 10);
      const newExpiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 часа

      await this.prisma.refreshToken.create({
        data: {
          token: newTokenHash,
          userId: storedToken.user.id,
          expiresAt: newExpiresAt,
          replacedBy: storedToken.id,
        },
      });

      // 6. Инвалидируем кеш пользователя
      await this.redis.invalidateUserCache(storedToken.user.id);

      return {
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
        user: {
          id: storedToken.user.id,
          email: storedToken.user.email,
          username: storedToken.user.username,
          avatar: storedToken.user.avatar,
          createdAt: storedToken.user.createdAt,
          emailVerified: storedToken.user.emailVerified,
        },
      };
    } catch (error) {
      if (error instanceof UnauthorizedException) {
        throw error;
      }
      throw new UnauthorizedException('Невалидный refresh token');
    }
  }

  /**
   * Выход из системы с добавлением токена в blacklist
   */
  async logout(userId: string, accessToken?: string): Promise<void> {
    // Добавляем access token в Redis blacklist
    if (accessToken) {
      try {
        // Декодируем токен без верификации для получения exp
        const decoded = this.jwtService.decode(accessToken) as any;

        if (decoded && decoded.exp) {
          // Вычисляем TTL до истечения токена
          const ttl = decoded.exp - Math.floor(Date.now() / 1000);

          if (ttl > 0) {
            await this.redis.addToBlacklist(accessToken, ttl);
          }
        }
      } catch {
        // Игнорируем ошибки декодирования токена
      }
    }

    // Ревокуем все refresh токены пользователя
    await this.prisma.refreshToken.updateMany({
      where: {
        userId,
        revokedAt: null,
      },
      data: {
        revokedAt: new Date(),
      },
    });

    // Логируем выход
    await this.prisma.authAuditLog.create({
      data: {
        userId,
        action: 'logout',
        success: true,
      },
    });

    // Инвалидируем кеш пользователя
    await this.redis.invalidateUserCache(userId);
  }

  /**
   * Запрос на сброс пароля
   */
  async requestPasswordReset(email: string): Promise<void> {
    const user = await this.prisma.user.findUnique({
      where: { email },
    });

    if (user) {
      const resetToken = crypto.randomBytes(32).toString('hex');
      const expiresAt = new Date(Date.now() + 3600000); // 1 час

      await this.prisma.user.update({
        where: { id: user.id },
        data: {
          passwordResetToken: resetToken,
          passwordResetExpires: expiresAt,
        },
      });

      // TODO: Отправить email с ссылкой для сброса пароля
      // await this.emailService.sendPasswordResetEmail(user.email, resetToken);
    }

    // Всегда возвращаем успешно (security best practice - не раскрываем существование email)
  }

  /**
   * Сброс пароля
   */
  async resetPassword(token: string, newPassword: string): Promise<void> {
    const user = await this.prisma.user.findFirst({
      where: {
        passwordResetToken: token,
        passwordResetExpires: { gte: new Date() },
      },
    });

    if (!user) {
      throw new UnauthorizedException('Невалидный или истёкший токен сброса пароля');
    }

    const hashedPassword = await bcrypt.hash(newPassword, 10);

    await this.prisma.$transaction(async (tx) => {
      await tx.user.update({
        where: { id: user.id },
        data: {
          password: hashedPassword,
          passwordResetToken: null,
          passwordResetExpires: null,
        },
      });

      // Ревокуем все токены пользователя
      await tx.refreshToken.updateMany({
        where: {
          userId: user.id,
          revokedAt: null,
        },
        data: { revokedAt: new Date() },
      });

      // Логируем сброс пароля
      await tx.authAuditLog.create({
        data: {
          userId: user.id,
          action: 'password_reset',
          success: true,
        },
      });
    });

    // Инвалидируем кеш пользователя
    await this.redis.invalidateUserCache(user.id);
  }

  /**
   * Верификация email
   */
  async verifyEmail(token: string): Promise<void> {
    const user = await this.prisma.user.findUnique({
      where: { emailVerifiedToken: token },
    });

    if (!user) {
      throw new UnauthorizedException('Невалидный токен верификации');
    }

    await this.prisma.user.update({
      where: { id: user.id },
      data: {
        emailVerified: new Date(),
        emailVerifiedToken: null,
      },
    });

    // Инвалидируем кеш пользователя
    await this.redis.invalidateUserCache(user.id);
  }

  /**
   * Валидация пользователя (для Passport стратегии)
   */
  async validateUser(email: string, password: string) {
    const user = await this.prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
      return null;
    }

    const isPasswordValid = await bcrypt.compare(password, user.password);

    if (!isPasswordValid) {
      return null;
    }

    // Возвращаем пользователя без пароля
    return {
      id: user.id,
      email: user.email,
      username: user.username,
      avatar: user.avatar,
      createdAt: user.createdAt,
      emailVerified: user.emailVerified,
    };
  }

  /**
   * Генерация access и refresh токенов
   */
  private async generateTokens(userId: string, email: string) {
    const payload = { sub: userId, email };

    // Access Token - 1 час
    const accessToken = await this.jwtService.signAsync(payload, {
      secret: this.configService.get<string>('jwt.secret') || 'default-secret-key',
      expiresIn: (this.configService.get<string>('jwt.expiresIn') || '1h') as any,
    });

    // Refresh Token - 24 часа
    const refreshToken = await this.jwtService.signAsync(payload, {
      secret: this.configService.get<string>('jwt.refreshSecret') || 'default-refresh-secret',
      expiresIn: (this.configService.get<string>('jwt.refreshExpiresIn') || '24h') as any,
    });

    return {
      accessToken,
      refreshToken,
    };
  }
}
