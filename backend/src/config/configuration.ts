export default () => {
  const isProduction = process.env.NODE_ENV === 'production';

  return {
    // Application
    port: parseInt(process.env.PORT || '3000', 10),
    nodeEnv: process.env.NODE_ENV || 'development',

    // Database
    database: {
      url: process.env.DATABASE_URL || '',
    },

    // Redis
    redis: {
      host: process.env.REDIS_HOST || 'localhost',
      port: parseInt(process.env.REDIS_PORT || '6379', 10),
      password: process.env.REDIS_PASSWORD,
    },

    // JWT
    // В production секреты должны быть установлены через ENV (валидация в main.ts)
    jwt: {
      secret: isProduction
        ? process.env.JWT_SECRET || ''
        : process.env.JWT_SECRET || 'dev-secret-key-change-in-production',
      expiresIn: process.env.JWT_EXPIRES_IN || '1h',
      refreshSecret: isProduction
        ? process.env.JWT_REFRESH_SECRET || ''
        : process.env.JWT_REFRESH_SECRET || 'dev-refresh-secret-change-in-production',
      refreshExpiresIn: process.env.REFRESH_TOKEN_EXPIRES_IN || '24h',
    },

    // CORS
    cors: {
      origin: process.env.FRONTEND_URL || 'http://localhost:5173',
      credentials: true,
    },
  };
};
