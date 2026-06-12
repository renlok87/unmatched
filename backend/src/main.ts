import { NestFactory } from '@nestjs/core';
import { ValidationPipe, Logger, NestApplicationOptions } from '@nestjs/common';
import { AppModule } from './app.module';
import { Request, Response, NextFunction } from 'express';

/**
 * Валидация обязательных переменных окружения в production
 */
function validateEnv() {
  const isProd = process.env.NODE_ENV === 'production';

  if (isProd) {
    const requiredEnvVars = ['JWT_SECRET', 'JWT_REFRESH_SECRET', 'DATABASE_URL'];

    const missing = requiredEnvVars.filter((key) => !process.env[key]);

    if (missing.length > 0) {
      throw new Error(`Missing required environment variables: ${missing.join(', ')}`);
    }

    // Проверка длины секретов (минимум 32 символа для безопасности)
    if (process.env.JWT_SECRET && process.env.JWT_SECRET.length < 32) {
      throw new Error('JWT_SECRET must be at least 32 characters');
    }

    if (process.env.JWT_REFRESH_SECRET && process.env.JWT_REFRESH_SECRET.length < 32) {
      throw new Error('JWT_REFRESH_SECRET must be at least 32 characters');
    }

    // В production БЛОКИРУЕМ запуск с дефолтными секретами
    const hasBadSecrets =
      process.env.JWT_SECRET?.includes('change') ||
      process.env.JWT_SECRET?.includes('default') ||
      process.env.JWT_REFRESH_SECRET?.includes('change') ||
      process.env.JWT_REFRESH_SECRET?.includes('default');

    if (hasBadSecrets) {
      throw new Error(
        'CANNOT START: Using default or insecure secrets in production. ' +
          'Set secure JWT_SECRET and JWT_REFRESH_SECRET environment variables.',
      );
    }
  } else {
    // В development режиме выводим предупреждение если используются дефолтные значения
    if (!process.env.JWT_SECRET || process.env.JWT_SECRET.includes('change-in-production')) {
      console.warn('⚠️  Using default JWT_SECRET! Change this in production!');
    }
    if (
      !process.env.JWT_REFRESH_SECRET ||
      process.env.JWT_REFRESH_SECRET.includes('change-in-production')
    ) {
      console.warn('⚠️  Using default JWT_REFRESH_SECRET! Change this in production!');
    }
  }
}

async function bootstrap() {
  // Валидация ENV
  validateEnv();

  const app = await NestFactory.create(AppModule, {
    bufferLogs: true,
  });

  // Enable validation pipes globally
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      forbidNonWhitelisted: true,
      transform: true,
      transformOptions: {
        enableImplicitConversion: true,
      },
    }),
  );

  // Handle preflight OPTIONS requests for CORS
  app.use((req: Request, res: Response, next: NextFunction) => {
    if (req.method === 'OPTIONS') {
      const allowedOrigins = [
        'http://localhost:5173',
        'http://localhost:5174',
        'http://localhost:5480',
        process.env.FRONTEND_URL,
      ].filter(Boolean);

      const origin = req.headers.origin;
      if (origin && allowedOrigins.includes(origin)) {
        res.setHeader('Access-Control-Allow-Origin', origin);
      }
      res.setHeader('Access-Control-Allow-Methods', 'GET,HEAD,PUT,PATCH,POST,DELETE,OPTIONS');
      // X-Idempotency-Key шлёт фронт (roomStore setReady/selectHero)
      res.setHeader(
        'Access-Control-Allow-Headers',
        'Content-Type, Authorization, X-Requested-With, X-Idempotency-Key, apollo-require-preflight',
      );
      res.setHeader('Access-Control-Allow-Credentials', 'true');
      res.sendStatus(204);
      return;
    }
    next();
  });

  // Enable CORS - FIXED PORTS: frontend (5173-5174), admin (5480)
  const allowedOrigins = [
    'http://localhost:5173', // Main frontend (Vite default)
    'http://localhost:5174', // Main frontend (Vite alternate)
    'http://localhost:5480', // Admin panel
    process.env.FRONTEND_URL, // Custom origin from env
  ].filter(Boolean);

  app.enableCors({
    origin: (origin: string | undefined, callback: (err: Error | null, allow: boolean) => void) => {
      // Allow requests with no origin (like mobile apps, curl, etc)
      if (!origin) return callback(null, true);

      if (allowedOrigins.includes(origin)) {
        callback(null, true);
      } else {
        callback(new Error('Not allowed by CORS'), false);
      }
    },
    credentials: true,
    // Фронт шлёт X-Idempotency-Key (roomStore: setReady/selectHero) —
    // без явного списка preflight режет запрос (Failed to fetch)
    allowedHeaders: [
      'Content-Type',
      'Authorization',
      'X-Idempotency-Key',
      'apollo-require-preflight',
    ],
  });

  const port = process.env.PORT || 3000;
  await app.listen(port);

  const logger = new Logger('Bootstrap');
  logger.log(`✅ Application is running on: http://localhost:${port}`);
  logger.log(`🎮 GraphQL Playground: http://localhost:${port}/graphql`);
  logger.log(`📊 Metrics: http://localhost:${port}/metrics`);
  logger.log(`💚 Health: http://localhost:${port}/health`);
  logger.log(`🌍 Environment: ${process.env.NODE_ENV || 'development'}`);
}

bootstrap();
