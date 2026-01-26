import { Resolver, Mutation, Args, Context } from '@nestjs/graphql';
import { UseGuards } from '@nestjs/common';
import { Throttle } from '@nestjs/throttler';
import { AuthService } from './auth.service';
import { RegisterDto, LoginDto, AuthResponseDto } from './dto';
import { GqlAuthGuard } from './guards/gql-auth.guard';
import { Public } from '../common/decorators/public.decorator';
import { CurrentUser } from '../common/decorators/current-user.decorator';

// Helper функция для получения IP адреса
function getClientIp(context: any): string | undefined {
  return context.req?.ip ||
    context.req?.headers?.['x-forwarded-for']?.split(',')[0]?.trim() ||
    context.req?.headers?.['x-real-ip'] ||
    context.req?.connection?.remoteAddress;
}

// Helper функция для получения User Agent
function getUserAgent(context: any): string | undefined {
  return context.req?.headers?.['user-agent'];
}

@Resolver()
export class AuthResolver {
  constructor(private authService: AuthService) {}

  @Mutation(() => AuthResponseDto)
  @Public()
  @Throttle({ default: { limit: 5, ttl: 60000 } })  // 5 запросов в минуту
  async register(@Args('input') input: RegisterDto) {
    return this.authService.register(input);
  }

  @Mutation(() => AuthResponseDto)
  @Public()
  @Throttle({ default: { limit: 10, ttl: 60000 } })  // 10 запросов в минуту
  async login(
    @Args('input') input: LoginDto,
    @Context() context: any,
  ) {
    const ipAddress = getClientIp(context);
    const userAgent = getUserAgent(context);
    return this.authService.login(input, ipAddress, userAgent);
  }

  @Mutation(() => Boolean)
  async logout(
    @Context() context: any,
    @CurrentUser() user: any,
  ) {
    const accessToken = context.req?.headers?.authorization?.replace('Bearer ', '');
    await this.authService.logout(user?.id, accessToken);
    return true;
  }

  @Mutation(() => AuthResponseDto)
  @Public()
  @Throttle({ default: { limit: 3, ttl: 60000 } })  // 3 запроса в минуту (строже)
  async refreshTokens(@Args('refreshToken') refreshToken: string) {
    return this.authService.refreshTokens(refreshToken);
  }

  @Mutation(() => Boolean)
  @Public()
  @Throttle({ default: { limit: 3, ttl: 60000 } })  // 3 запроса в минуту
  async requestPasswordReset(@Args('email') email: string) {
    await this.authService.requestPasswordReset(email);
    return true;
  }

  @Mutation(() => Boolean)
  @Public()
  @Throttle({ default: { limit: 3, ttl: 60000 } })  // 3 запроса в минуту
  async resetPassword(
    @Args('token') token: string,
    @Args('newPassword') newPassword: string,
  ) {
    await this.authService.resetPassword(token, newPassword);
    return true;
  }

  @Mutation(() => Boolean)
  @Public()
  @Throttle({ default: { limit: 5, ttl: 60000 } })  // 5 запросов в минуту
  async verifyEmail(@Args('token') token: string) {
    await this.authService.verifyEmail(token);
    return true;
  }
}
