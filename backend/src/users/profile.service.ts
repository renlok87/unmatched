import { Injectable, NotFoundException } from '@nestjs/common';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { SettingsDto, UserSettingsGraphql } from './dto/settings.dto';

@Injectable()
export class ProfileService {
  constructor(
    private prisma: PrismaService,
    private redis: RedisService,
  ) {}

  /**
   * Загрузить аватар
   * Возвращает URL загруженного аватара
   */
  async uploadAvatar(userId: string, fileUrl: string): Promise<string> {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    // Обновляем avatar URL
    const updatedUser = await this.prisma.user.update({
      where: { id: userId },
      data: { avatar: fileUrl },
    });

    // Инвалидируем кеш
    await this.redis.invalidateUserCache(userId);

    return updatedUser.avatar || '';
  }

  /**
   * Удалить аватар
   */
  async removeAvatar(userId: string): Promise<void> {
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    await this.prisma.user.update({
      where: { id: userId },
      data: { avatar: null },
    });

    // Инвалидируем кеш
    await this.redis.invalidateUserCache(userId);
  }

  /**
   * Обновить настройки пользователя
   */
  async updateSettings(userId: string, dto: SettingsDto): Promise<UserSettingsGraphql> {
    // Проверяем существование пользователя
    const user = await this.prisma.user.findUnique({
      where: { id: userId },
    });

    if (!user) {
      throw new NotFoundException('Пользователь не найден');
    }

    // Обновляем или создаем настройки
    const settings = await this.prisma.userSettings.upsert({
      where: { userId },
      create: {
        userId,
        ...(dto.theme !== undefined && { theme: dto.theme }),
        ...(dto.language !== undefined && { language: dto.language }),
        ...(dto.soundEnabled !== undefined && { soundEnabled: dto.soundEnabled }),
        ...(dto.musicEnabled !== undefined && { musicEnabled: dto.musicEnabled }),
        ...(dto.profileVisible !== undefined && { profileVisible: dto.profileVisible }),
        ...(dto.showOnlineStatus !== undefined && { showOnlineStatus: dto.showOnlineStatus }),
      },
      update: {
        ...(dto.theme !== undefined && { theme: dto.theme }),
        ...(dto.language !== undefined && { language: dto.language }),
        ...(dto.soundEnabled !== undefined && { soundEnabled: dto.soundEnabled }),
        ...(dto.musicEnabled !== undefined && { musicEnabled: dto.musicEnabled }),
        ...(dto.profileVisible !== undefined && { profileVisible: dto.profileVisible }),
        ...(dto.showOnlineStatus !== undefined && { showOnlineStatus: dto.showOnlineStatus }),
      },
    });

    return {
      id: settings.id,
      theme: settings.theme,
      language: settings.language,
      soundEnabled: settings.soundEnabled,
      musicEnabled: settings.musicEnabled,
      profileVisible: settings.profileVisible,
      showOnlineStatus: settings.showOnlineStatus,
    };
  }

  /**
   * Получить настройки пользователя
   */
  async getSettings(userId: string): Promise<UserSettingsGraphql> {
    const settings = await this.prisma.userSettings.findUnique({
      where: { userId },
    });

    if (!settings) {
      // Создаем настройки по умолчанию если их нет
      const newSettings = await this.prisma.userSettings.create({
        data: { userId },
      });

      return {
        id: newSettings.id,
        theme: newSettings.theme,
        language: newSettings.language,
        soundEnabled: newSettings.soundEnabled,
        musicEnabled: newSettings.musicEnabled,
        profileVisible: newSettings.profileVisible,
        showOnlineStatus: newSettings.showOnlineStatus,
      };
    }

    return {
      id: settings.id,
      theme: settings.theme,
      language: settings.language,
      soundEnabled: settings.soundEnabled,
      musicEnabled: settings.musicEnabled,
      profileVisible: settings.profileVisible,
      showOnlineStatus: settings.showOnlineStatus,
    };
  }
}
