export const validationSchema = {
  DATABASE_URL: {
    type: 'string',
    required: true,
  },
  JWT_SECRET: {
    type: 'string',
    required: true,
    defaultValue: 'change-this-in-production',
  },
  REFRESH_TOKEN_SECRET: {
    type: 'string',
    required: true,
    defaultValue: 'change-this-in-production',
  },
  PORT: {
    type: 'number',
    default: 3000,
  },
  NODE_ENV: {
    type: 'string',
    default: 'development',
  },
};
