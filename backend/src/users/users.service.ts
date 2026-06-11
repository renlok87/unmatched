import {
  Injectable,
  NotFoundException,
  ConflictException,
  UnauthorizedException,
} from '@nestjs/common';
import * as bcrypt from 'bcrypt';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { UpdateProfileDto, ChangePasswordDto, UserResponse } from './dto';
import { UserRole } from '@prisma/client';

@Injectable()
export class UsersService {
  constructor(
    private prisma: PrismaService,
    private redis: RedisService,
  ) {}

  async findById(id: string): Promise<UserResponse> {
    const cached = await this.redis.getUserFromCache(id);
    if (cached) {
      return cached as UserResponse;
    }

    const user = await this.prisma.user.findUnique({
      where: { id },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

const userResponse: UserResponse = {
      id: user.id,
      email: user.email,
      username: user.username,
      avatar: user.avatar,
      role: user.role,
      createdAt: user.createdAt,
      emailVerified: user.emailVerified,
    };

    await this.redis.cacheUser(id, userResponse);

    return userResponse;
  }

  /**
   * Найти пользователя по email
   */
  async findByEmail(email: string): Promise<UserResponse> {
    const user = await this.prisma.user.findUnique({
      where: { email },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

return {
      id: user.id,
      email: user.email,
      username: user.username,
      avatar: user.avatar,
      role: user.role,
      createdAt: user.createdAt,
      emailVerified: user.emailVerified,
    };
  }

  /**
   * Найти пользователя по username
   */
  async findByUsername(username: string): Promise<UserResponse> {
    const user = await this.prisma.user.findUnique({
      where: { username },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

return {
      id: user.id,
      email: user.email,
      username: user.username,
      avatar: user.avatar,
      role: user.role,
      createdAt: user.createdAt,
      emailVerified: user.emailVerified,
    };
  }

  /**
   * Обновить профиль пользователя
   */
  async updateProfile(userId: string, dto: UpdateProfileDto): Promise<UserResponse> {
    const existingUser = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!existingUser) {
      throw new NotFoundException('Пользователь не найден');
    }

    if (dto.username && dto.username !== existingUser.username) {
      const usernameTaken = await this.prisma.user.findUnique({
        where: { username: dto.username },
      });

      if (usernameTaken) {
        throw new ConflictException('Это имя пользователя уже занято');
      }
    }

    const updatedUser = await this.prisma.user.update({
      where: { id: userId },
      data: {
        ...(dto.username && { username: dto.username }),
        ...(dto.avatar !== undefined && { avatar: dto.avatar }),
      },
    });

    await this.redis.invalidateUserCache(userId);

return {
      id: updatedUser.id,
      email: updatedUser.email,
      username: updatedUser.username,
      avatar: updatedUser.avatar,
      role: updatedUser.role,
      createdAt: updatedUser.createdAt,
      emailVerified: updatedUser.emailVerified,
    };
  }

  /**
   * Сменить пароль
   */
  async changePassword(userId: string, dto: ChangePasswordDto): Promise<void> {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    // Проверяем текущий пароль
    const isPasswordValid = await bcrypt.compare(dto.currentPassword, user.password);

    if (!isPasswordValid) {
      throw new UnauthorizedException('Неверный текущий пароль');
    }

    // Хешируем новый пароль
    const hashedPassword = await bcrypt.hash(dto.newPassword, 10);

    // Обновляем пароль в транзакции с отзывом токенов
    await this.prisma.$transaction(async (tx) => {
      await tx.user.update({
        where: { id: userId },
        data: { password: hashedPassword },
      });

      // Ревокуем все refresh токены
      await tx.refreshToken.updateMany({
        where: {
          userId,
          revokedAt: null,
        },
        data: { revokedAt: new Date() },
      });
    });

    // Инвалидируем кеш
    await this.redis.invalidateUserCache(userId);
  }

  /**
   * Удалить аккаунт
   */
  async deleteAccount(userId: string): Promise<void> {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    // Каскадное удаление сработает автоматически благодаря настройкам Prisma
    await this.prisma.user.delete({
      where: { id: userId },
    });

    // Инвалидируем кеш
    await this.redis.invalidateUserCache(userId);
  }

  /**
   * Получить настройки пользователя
   */
  async getSettings(userId: string) {
    const settings = await this.prisma.userSettings.findUnique({
      where: { userId },
    });

    if (!settings) {
      // Создаем настройки если их нет
      return await this.prisma.userSettings.create({
        data: { userId },
      });
    }

    return settings;
  }
}
