import { Resolver, Query, Mutation, Args } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { UsersService } from './users.service';
import { ProfileService } from './profile.service';
import { UserStatsService } from './user-stats.service';
import { GqlAuthGuard } from '../auth/guards/gql-auth.guard';
import { CurrentUser } from '../common/decorators/current-user.decorator';
import {
  UpdateProfileDto,
  ChangePasswordDto,
  UserResponse,
  UserWithSettingsResponse,
  PublicUserResponse,
  UserSettingsGraphql,
  UserStatsResponse,
  SettingsDto,
} from './dto';

@Resolver('User')
export class UsersResolver {
  constructor(
    private usersService: UsersService,
    private profileService: ProfileService,
    private userStatsService: UserStatsService,
  ) {}

  /**
   * Получить текущего пользователя (полные данные включая email)
   */
  @Query(() => UserWithSettingsResponse, { nullable: true })
  @UseGuards(GqlAuthGuard)
  async me(@CurrentUser() user: any): Promise<UserWithSettingsResponse> {
    const userResponse = await this.usersService.findById(user.id);
    const settings = await this.profileService.getSettings(user.id);

    return {
      ...userResponse,
      settings,
    };
  }

  /**
   * Получить публичный профиль пользователя по ID
   * Email возвращается только владельцу аккаунта
   */
@Query(() => PublicUserResponse, { nullable: true })
  async user(
    @Args('id', { type: () => String }) id: string,
    @CurrentUser() currentUser?: any,
  ): Promise<PublicUserResponse> {
    const user = await this.usersService.findById(id);

    // Проверяем настройки приватности
    const settings = await this.profileService.getSettings(id);

    if (!settings.profileVisible && currentUser?.id !== id) {
      // Профиль скрыт - возвращаем минимальную информацию
      return {
        id: user.id,
        username: 'Hidden',
        avatar: null,
        createdAt: user.createdAt,
      };
    }

    return {
      id: user.id,
      username: user.username,
      avatar: user.avatar,
      createdAt: user.createdAt,
    };
  }

  /**
   * Получить публичный профиль пользователя по username
   */
@Query(() => PublicUserResponse, { nullable: true, name: 'userByUsername' })
  async userByUsername(
    @Args('username', { type: () => String }) username: string,
    @CurrentUser() currentUser?: any,
  ): Promise<PublicUserResponse> {
    const user = await this.usersService.findByUsername(username);

    // Проверяем настройки приватности
    const settings = await this.profileService.getSettings(user.id);

    if (!settings.profileVisible && currentUser?.id !== user.id) {
      return {
        id: user.id,
        username: 'Hidden',
        avatar: null,
        createdAt: user.createdAt,
      };
    }

    return {
      id: user.id,
      username: user.username,
      avatar: user.avatar,
      createdAt: user.createdAt,
    };
  }

  /**
   * Получить статистику текущего пользователя
   */
  @Query(() => UserStatsResponse)
  @UseGuards(GqlAuthGuard)
  async myStats(@CurrentUser() user: any): Promise<UserStatsResponse> {
    return await this.userStatsService.getStats(user.id);
  }

  /**
   * Получить публичную статистику пользователя
   */
@Query(() => UserStatsResponse, { nullable: true })
  async stats(@Args('userId', { type: () => String }) userId: string): Promise<UserStatsResponse> {
    return await this.userStatsService.getStats(userId);
  }

  /**
   * Получить настройки текущего пользователя
   */
  @Query(() => UserSettingsGraphql)
  @UseGuards(GqlAuthGuard)
  async mySettings(@CurrentUser() user: any): Promise<UserSettingsGraphql> {
    return await this.profileService.getSettings(user.id);
  }

  /**
   * Обновить профиль
   * Rate limited: 5 запросов в минуту
   */
  @Mutation(() => UserResponse)
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async updateProfile(
    @Args('input') input: UpdateProfileDto,
    @CurrentUser() user: any,
  ): Promise<UserResponse> {
    return await this.usersService.updateProfile(user.id, input);
  }

  /**
   * Обновить настройки
   * Rate limited: 10 запросов в минуту
   */
  @Mutation(() => UserSettingsGraphql)
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 10, ttl: 60000 } })
  async updateSettings(
    @Args('input') input: SettingsDto,
    @CurrentUser() user: any,
  ): Promise<UserSettingsGraphql> {
    return await this.profileService.updateSettings(user.id, input);
  }

  /**
   * Сменить пароль
   * Rate limited: 3 запроса в минуту (чувствительная операция)
   */
  @Mutation(() => Boolean)
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 3, ttl: 60000 } })
  async changePassword(
    @Args('input') input: ChangePasswordDto,
    @CurrentUser() user: any,
  ): Promise<boolean> {
    await this.usersService.changePassword(user.id, input);
    return true;
  }

  /**
   * Удалить аккаунт
   * Rate limited: 2 запроса в час (критическая операция)
   */
  @Mutation(() => Boolean)
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 2, ttl: 3600000 } })
  async deleteAccount(@CurrentUser() user: any): Promise<boolean> {
    await this.usersService.deleteAccount(user.id);
    return true;
  }

  /**
   * Загрузить аватар
   * Rate limited: 5 запросов в минуту
   */
@Mutation(() => String)
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 5, ttl: 60000 } })
  async uploadAvatar(@Args('fileUrl', { type: () => String }) fileUrl: string, @CurrentUser() user: any): Promise<string> {
    return await this.profileService.uploadAvatar(user.id, fileUrl);
  }

  /**
   * Удалить аватар
   * Rate limited: 10 запросов в минуту
   */
  @Mutation(() => Boolean)
  @UseGuards(GqlAuthGuard)
  @Throttle({ default: { limit: 10, ttl: 60000 } })
  async removeAvatar(@CurrentUser() user: any): Promise<boolean> {
    await this.profileService.removeAvatar(user.id);
    return true;
  }
}
