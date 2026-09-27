import { Test, TestingModule } from '@nestjs/testing';
import { AuthService } from './auth.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from '../database/prisma.service';
import { RedisService } from '../redis/redis.service';
import { ConflictException, UnauthorizedException } from '@nestjs/common';
import * as bcrypt from 'bcrypt';
import { RegisterDto, LoginDto } from './dto';
import { UserRole } from '@prisma/client';

jest.mock('bcrypt');
const mockedBcrypt = bcrypt as jest.Mocked<typeof bcrypt>;

describe('AuthService', () => {
  let service: AuthService;
  let prisma: PrismaService;
  let jwtService: JwtService;
  let redis: RedisService;

  beforeEach(() => {
    jest.clearAllMocks();
  });

  const mockUser = {
    id: 'user1',
    email: 'test@example.com',
    username: 'testuser',
    password: '$2b$10$hashedpassword',
    avatar: null,
    role: UserRole.USER,
    createdAt: new Date(),
    updatedAt: new Date(),
    emailVerified: null,
    emailVerifiedToken: 'token123',
    passwordResetToken: null,
    passwordResetExpires: null,
    deletedAt: null,
  };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        AuthService,
        {
          provide: PrismaService,
          useValue: {
            user: {
              findUnique: jest.fn(),
              create: jest.fn(),
              update: jest.fn(),
              findFirst: jest.fn(),
            },
            userSettings: { create: jest.fn() },
            userStats: { create: jest.fn() },
            authAuditLog: { create: jest.fn() },
            refreshToken: {
              create: jest.fn(),
              updateMany: jest.fn(),
              findFirst: jest.fn(),
              findMany: jest.fn(),
              update: jest.fn(),
            },
            $transaction: jest.fn(),
          },
        },
        {
          provide: JwtService,
          useValue: {
            signAsync: jest.fn(),
            verifyAsync: jest.fn(),
            decode: jest.fn(),
          },
        },
        {
          provide: ConfigService,
          useValue: {
            get: jest.fn((key: string) => {
              const secrets: Record<string, string> = {
                'jwt.secret': 'test-secret',
                'jwt.refreshSecret': 'test-refresh-secret',
                'jwt.expiresIn': '1h',
                'jwt.refreshExpiresIn': '24h',
              };
              return secrets[key];
            }),
          },
        },
        {
          provide: RedisService,
          useValue: {
            invalidateUserCache: jest.fn(),
            addToBlacklist: jest.fn(),
          },
        },
      ],
    }).compile();

    service = module.get<AuthService>(AuthService);
    prisma = module.get(PrismaService);
    jwtService = module.get(JwtService);
    redis = module.get(RedisService);
  });

  describe('register', () => {
    it('should successfully register a new user', async () => {
      const dto: RegisterDto = {
        email: 'new@example.com',
        username: 'newuser',
        password: 'password123',
      };

      const findUniqueSpy = jest
        .spyOn(prisma.user, 'findUnique')
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce(null);

      mockedBcrypt.hash.mockResolvedValue('$2b$10$hashed' as never);

      const createdUser = { ...mockUser, email: dto.email, username: dto.username };
      const transactionMock = jest.fn().mockImplementation(async (callback) => {
        return callback({
          user: { create: jest.fn().mockResolvedValue(createdUser) },
          userSettings: { create: jest.fn().mockResolvedValue({}) },
          userStats: { create: jest.fn().mockResolvedValue({}) },
          authAuditLog: { create: jest.fn().mockResolvedValue({}) },
        } as any);
      });
      jest.spyOn(prisma, '$transaction').mockImplementation(transactionMock);

      const signAsyncSpy = jest
        .spyOn(jwtService, 'signAsync')
        .mockResolvedValueOnce('access-token')
        .mockResolvedValueOnce('refresh-token');

      jest.spyOn(prisma.refreshToken, 'create').mockResolvedValue({} as any);

      const result = await service.register(dto);

      expect(result).toHaveProperty('accessToken', 'access-token');
      expect(result).toHaveProperty('refreshToken', 'refresh-token');
      expect(result.user.email).toBe(dto.email);
      expect(prisma.$transaction).toHaveBeenCalled();
      expect(mockedBcrypt.hash).toHaveBeenCalledWith(dto.password, 10);
      expect(signAsyncSpy).toHaveBeenCalledTimes(2);
    });

    it('should throw ConflictException if email already exists', async () => {
      const dto: RegisterDto = {
        email: 'existing@example.com',
        username: 'newuser',
        password: 'password123',
      };

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);

      await expect(service.register(dto)).rejects.toThrow(ConflictException);
      await expect(service.register(dto)).rejects.toThrow(
        'Пользователь с таким email уже существует',
      );
    });

    it('should throw ConflictException if username already exists', async () => {
      const dto: RegisterDto = {
        email: 'new@example.com',
        username: 'existinguser',
        password: 'password123',
      };

      jest
        .spyOn(prisma.user, 'findUnique')
        .mockResolvedValueOnce(null)
        .mockResolvedValueOnce(mockUser);

      await expect(service.register(dto)).rejects.toThrow(ConflictException);
    });

    it('should hash password with bcrypt', async () => {
      const dto: RegisterDto = {
        email: 'new@example.com',
        username: 'newuser',
        password: 'password123',
      };

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValueOnce(null).mockResolvedValueOnce(null);

      mockedBcrypt.hash.mockResolvedValue('$2b$10$hashed' as never);

      const transactionMock = jest.fn().mockImplementation(async (callback) => {
        return callback({
          user: { create: jest.fn().mockResolvedValue(mockUser) },
          userSettings: { create: jest.fn().mockResolvedValue({}) },
          userStats: { create: jest.fn().mockResolvedValue({}) },
          authAuditLog: { create: jest.fn().mockResolvedValue({}) },
        } as any);
      });
      jest.spyOn(prisma, '$transaction').mockImplementation(transactionMock);

      jest
        .spyOn(jwtService, 'signAsync')
        .mockResolvedValueOnce('access-token')
        .mockResolvedValueOnce('refresh-token');

      jest.spyOn(prisma.refreshToken, 'create').mockResolvedValue({} as any);

      await service.register(dto);

      expect(mockedBcrypt.hash).toHaveBeenCalledWith(dto.password, 10);
      expect(jwtService.signAsync).toHaveBeenCalledTimes(2);
    });
  });

  describe('login', () => {
    it('should successfully login with correct credentials', async () => {
      const dto: LoginDto = { email: 'test@example.com', password: 'password123' };

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);
      mockedBcrypt.compare.mockResolvedValue(true as never);

      jest
        .spyOn(jwtService, 'signAsync')
        .mockResolvedValueOnce('access-token')
        .mockResolvedValueOnce('refresh-token');

      jest.spyOn(prisma.refreshToken, 'create').mockResolvedValue({} as any);
      jest.spyOn(prisma.authAuditLog, 'create').mockResolvedValue({} as any);

      const result = await service.login(dto, '127.0.0.1', 'Mozilla');

      expect(result.accessToken).toBe('access-token');
      expect(result.refreshToken).toBe('refresh-token');
      expect(prisma.authAuditLog.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          action: 'login',
          success: true,
          ipAddress: '127.0.0.1',
        }),
      });
    });

    it('should throw UnauthorizedException with wrong password', async () => {
      const dto: LoginDto = { email: 'test@example.com', password: 'wrongpassword' };

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);
      mockedBcrypt.compare.mockResolvedValue(false as never);
      jest.spyOn(prisma.authAuditLog, 'create').mockResolvedValue({} as any);

      await expect(service.login(dto)).rejects.toThrow(UnauthorizedException);
    });

    it('should throw UnauthorizedException with non-existent user', async () => {
      const dto: LoginDto = { email: 'nonexistent@example.com', password: 'password123' };

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(null);
      mockedBcrypt.compare.mockResolvedValue(false as never);

      await expect(service.login(dto)).rejects.toThrow(UnauthorizedException);
    });

    it('should use timing attack protection', async () => {
      const dto: LoginDto = { email: 'nonexistent@example.com', password: 'password123' };

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(null);

      await expect(service.login(dto)).rejects.toThrow();

      expect(mockedBcrypt.compare).toHaveBeenCalled();
    });

    it('should log failed login attempt for existing user', async () => {
      const dto: LoginDto = { email: 'test@example.com', password: 'wrongpassword' };

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);
      mockedBcrypt.compare.mockResolvedValue(false as never);
      jest.spyOn(prisma.authAuditLog, 'create').mockResolvedValue({} as any);

      await expect(service.login(dto)).rejects.toThrow();

      expect(prisma.authAuditLog.create).toHaveBeenCalledWith({
        data: expect.objectContaining({
          userId: mockUser.id,
          action: 'login',
          success: false,
          errorMessage: 'Invalid password',
        }),
      });
    });
  });

  describe('logout', () => {
    it('should add access token to blacklist and revoke refresh tokens', async () => {
      const userId = 'user1';
      const accessToken = 'valid-token';

      const decoded = { exp: Math.floor(Date.now() / 1000) + 3600 };
      jest.spyOn(jwtService, 'decode').mockReturnValue(decoded);

      jest.spyOn(prisma.refreshToken, 'updateMany').mockResolvedValue({ count: 1 } as any);
      jest.spyOn(prisma.authAuditLog, 'create').mockResolvedValue({} as any);
      jest.spyOn(redis, 'addToBlacklist').mockResolvedValue(undefined);
      jest.spyOn(redis, 'invalidateUserCache').mockResolvedValue(undefined);

      await service.logout(userId, accessToken);

      expect(redis.addToBlacklist).toHaveBeenCalledWith(accessToken, expect.any(Number));
      expect(prisma.refreshToken.updateMany).toHaveBeenCalledWith({
        where: { userId, revokedAt: null },
        data: { revokedAt: expect.any(Date) },
      });
    });

    it('should not blacklist invalid access token', async () => {
      const userId = 'user1';
      const accessToken = 'invalid-token';

      jest.spyOn(jwtService, 'decode').mockReturnValue(null);

      jest.spyOn(prisma.refreshToken, 'updateMany').mockResolvedValue({ count: 1 } as any);
      jest.spyOn(prisma.authAuditLog, 'create').mockResolvedValue({} as any);
      jest.spyOn(redis, 'invalidateUserCache').mockResolvedValue(undefined);

      await service.logout(userId, accessToken);

      expect(redis.addToBlacklist).not.toHaveBeenCalled();
    });

    it('should invalidate user cache on logout', async () => {
      const userId = 'user1';

      jest
        .spyOn(jwtService, 'decode')
        .mockReturnValue({ exp: Math.floor(Date.now() / 1000) + 3600 });

      jest.spyOn(prisma.refreshToken, 'updateMany').mockResolvedValue({ count: 1 } as any);
      jest.spyOn(prisma.authAuditLog, 'create').mockResolvedValue({} as any);
      jest.spyOn(redis, 'addToBlacklist').mockResolvedValue(undefined);
      jest.spyOn(redis, 'invalidateUserCache').mockResolvedValue(undefined);

      await service.logout(userId);

      expect(redis.invalidateUserCache).toHaveBeenCalledWith(userId);
    });
  });

  describe('refreshTokens', () => {
    it('should rotate refresh token successfully', async () => {
      const refreshToken = 'valid-refresh-token';
      const payload = { sub: 'user1', email: 'test@example.com' };

      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(payload);
      mockedBcrypt.hash.mockResolvedValue('hashed-token' as never);
      mockedBcrypt.compare.mockResolvedValue(true as never);

      const storedToken = {
        id: 'token1',
        token: 'hashed',
        user: mockUser,
        expiresAt: new Date(Date.now() + 86400000),
        revokedAt: null,
        createdAt: new Date(),
        userId: 'user1',
        replacedBy: null,
      };

      jest.spyOn(prisma.refreshToken, 'findMany').mockResolvedValue([storedToken] as any);

      const txRefreshUpdate = jest.fn().mockResolvedValue({});
      const txRefreshCreate = jest.fn().mockResolvedValue({});
      const transactionMock = jest.fn().mockImplementation(async (callback) =>
        callback({
          refreshToken: { update: txRefreshUpdate, create: txRefreshCreate },
        } as any),
      );
      jest.spyOn(prisma, '$transaction').mockImplementation(transactionMock);

      jest.spyOn(redis, 'invalidateUserCache').mockResolvedValue(undefined);

      jest
        .spyOn(jwtService, 'signAsync')
        .mockResolvedValueOnce('new-access')
        .mockResolvedValueOnce('new-refresh');

      const result = await service.refreshTokens(refreshToken);

      expect(result.accessToken).toBe('new-access');
      expect(result.refreshToken).toBe('new-refresh');
      expect(result.user.id).toBe('user1');
      expect(mockedBcrypt.compare).toHaveBeenCalledWith(refreshToken, 'hashed');
      expect(prisma.$transaction).toHaveBeenCalledTimes(1);
      expect(txRefreshUpdate).toHaveBeenCalledWith({
        where: { id: 'token1' },
        data: { revokedAt: expect.any(Date) },
      });
      expect(txRefreshCreate).toHaveBeenCalledWith({
        data: expect.objectContaining({
          token: 'hashed-token',
          userId: 'user1',
          replacedBy: 'token1',
          expiresAt: expect.any(Date),
        }),
      });
      expect(redis.invalidateUserCache).toHaveBeenCalledWith('user1');
    });

    it('should throw UnauthorizedException for invalid token', async () => {
      jest.spyOn(jwtService, 'verifyAsync').mockRejectedValue(new Error('Invalid token'));

      await expect(service.refreshTokens('invalid')).rejects.toThrow(UnauthorizedException);
    });

    it('should throw UnauthorizedException for expired token', async () => {
      const refreshToken = 'valid-refresh-token';
      const payload = { sub: 'user1', email: 'test@example.com' };

      jest.spyOn(jwtService, 'verifyAsync').mockResolvedValue(payload);
      mockedBcrypt.hash.mockResolvedValue('hashed-token' as never);
      mockedBcrypt.compare.mockResolvedValue(true as never);

      const storedToken = {
        id: 'token1',
        token: 'hashed',
        user: mockUser,
        expiresAt: new Date(Date.now() - 1000),
        revokedAt: null,
        createdAt: new Date(),
        userId: 'user1',
        replacedBy: null,
      };

      jest.spyOn(prisma.refreshToken, 'findMany').mockResolvedValue([storedToken] as any);

      await expect(service.refreshTokens(refreshToken)).rejects.toThrow(UnauthorizedException);
      await expect(service.refreshTokens(refreshToken)).rejects.toThrow('Refresh token expired');
    });
  });

  describe('requestPasswordReset', () => {
    it('should create reset token for existing user', async () => {
      const email = 'test@example.com';

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);
      jest.spyOn(prisma.user, 'update').mockResolvedValue(mockUser);

      await service.requestPasswordReset(email);

      expect(prisma.user.update).toHaveBeenCalledWith({
        where: { id: mockUser.id },
        data: expect.objectContaining({
          passwordResetToken: expect.any(String),
          passwordResetExpires: expect.any(Date),
        }),
      });
    });

    it('should not throw error for non-existent email', async () => {
      const email = 'nonexistent@example.com';

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(null);

      await expect(service.requestPasswordReset(email)).resolves.not.toThrow();
    });
  });

  describe('resetPassword', () => {
    it('should reset password with valid token', async () => {
      const token = 'valid-reset-token';
      const newPassword = 'newPassword123';

      jest.spyOn(prisma.user, 'findFirst').mockResolvedValue(mockUser);
      mockedBcrypt.hash.mockResolvedValue('new-hashed' as never);

      const transactionMock = jest.fn().mockImplementation(async (callback) => {
        return callback({
          user: { update: jest.fn().mockResolvedValue(mockUser) },
          refreshToken: { updateMany: jest.fn().mockResolvedValue({ count: 1 }) },
          authAuditLog: { create: jest.fn().mockResolvedValue({}) },
        } as any);
      });
      jest.spyOn(prisma, '$transaction').mockImplementation(transactionMock);

      jest.spyOn(redis, 'invalidateUserCache').mockResolvedValue(undefined);

      await service.resetPassword(token, newPassword);

      expect(prisma.$transaction).toHaveBeenCalled();
      expect(redis.invalidateUserCache).toHaveBeenCalledWith(mockUser.id);
    });

    it('should throw UnauthorizedException for invalid token', async () => {
      const token = 'invalid-token';
      const newPassword = 'newPassword123';

      jest.spyOn(prisma.user, 'findFirst').mockResolvedValue(null);

      await expect(service.resetPassword(token, newPassword)).rejects.toThrow(
        UnauthorizedException,
      );
    });

    it('should throw UnauthorizedException for expired token', async () => {
      const token = 'expired-token';
      const newPassword = 'newPassword123';

      jest.spyOn(prisma.user, 'findFirst').mockResolvedValue(null);

      await expect(service.resetPassword(token, newPassword)).rejects.toThrow(
        UnauthorizedException,
      );
    });
  });

  describe('verifyEmail', () => {
    it('should verify email with valid token', async () => {
      const token = 'valid-verification-token';

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);
      jest.spyOn(prisma.user, 'update').mockResolvedValue(mockUser);
      jest.spyOn(redis, 'invalidateUserCache').mockResolvedValue(undefined);

      await service.verifyEmail(token);

      expect(prisma.user.update).toHaveBeenCalledWith({
        where: { id: mockUser.id },
        data: {
          emailVerified: expect.any(Date),
          emailVerifiedToken: null,
        },
      });
    });

    it('should throw UnauthorizedException for invalid token', async () => {
      const token = 'invalid-token';

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(null);

      await expect(service.verifyEmail(token)).rejects.toThrow(UnauthorizedException);
    });
  });

  describe('validateUser', () => {
    it('should return user without password for valid credentials', async () => {
      const email = 'test@example.com';
      const password = 'password123';

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);
      mockedBcrypt.compare.mockResolvedValue(true as never);

      const result = await service.validateUser(email, password);

      expect(result).toEqual({
        id: mockUser.id,
        email: mockUser.email,
        username: mockUser.username,
        avatar: mockUser.avatar,
        role: mockUser.role,
        createdAt: mockUser.createdAt,
        emailVerified: mockUser.emailVerified,
      });
      expect(result).not.toHaveProperty('password');
    });

    it('should return null for invalid password', async () => {
      const email = 'test@example.com';
      const password = 'wrongpassword';

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(mockUser);
      mockedBcrypt.compare.mockResolvedValue(false as never);

      const result = await service.validateUser(email, password);

      expect(result).toBeNull();
    });

    it('should return null for non-existent user', async () => {
      const email = 'nonexistent@example.com';
      const password = 'password123';

      jest.spyOn(prisma.user, 'findUnique').mockResolvedValue(null);

      const result = await service.validateUser(email, password);

      expect(result).toBeNull();
    });
  });
});
