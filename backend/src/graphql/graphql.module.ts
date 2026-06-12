import { Module } from '@nestjs/common';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { ConfigService } from '@nestjs/config';
import { DateTimeScalar, JSONScalar } from './scalars';
import { createComplexityLimitRule } from 'graphql-validation-complexity';
import depthLimit from 'graphql-depth-limit';

@Module({
  imports: [
    GraphQLModule.forRootAsync({
      driver: ApolloDriver,
      useFactory: (configService: ConfigService): ApolloDriverConfig => ({
        autoSchemaFile: true,
        sortSchema: true,
        playground: true,
        csrfPrevention: false, // Отключаем CSRF для локальной разработки
        // WebSocket Subscriptions для real-time игры
        subscriptions: {
          'graphql-ws': true,
        },
        context: (ctx: any) => {
          // graphql-ws вызывает context-фабрику с { connectionParams, extra, ... },
          // а не с legacy { connection } из subscriptions-transport-ws
          if (ctx?.connectionParams || ctx?.extra?.request) {
            const p = ctx.connectionParams || {};
            const raw = p.authorization || p.Authorization || p.token;
            const authorization =
              raw && !String(raw).startsWith('Bearer') ? `Bearer ${raw}` : raw;
            // Форма req.headers.authorization — её ждут GqlAuthGuard + passport-jwt
            return { req: { headers: { authorization } }, isSubscription: true };
          }
          // Обычный HTTP-запрос
          return { req: ctx.req, isSubscription: false };
        },
        // Validation rules для безопасности
        validationRules: [
          // Ограничение сложности запроса (защита от DOS)
          createComplexityLimitRule({
            maximumComplexity: 1000,
            variables: {},
            // Колбэк для логирования сложных запросов
            onComplete: (complexity: number) => {
              if (complexity > 500) {
                console.warn(`High complexity query: ${complexity}`);
              }
            },
            createError: (complexity: number) => {
              return new Error(
                `Query is too complex: ${complexity}. Maximum allowed complexity is 1000.`,
              );
            },
          }),
          // Ограничение глубины запроса (защита от глубокой вложенности)
          depthLimit(7, {
            ignore: ['_entities', '_service'], // Для Apollo Federation
          }),
        ],
        // Санитайзация ошибок в production
        formatError: (error: any) => {
          // Логируем все ошибки
          console.error('GraphQL Error:', {
            message: error.message,
            path: error.path,
            extensions: error.extensions,
          });

          const isProd = process.env.NODE_ENV === 'production';

          // В production не раскрываем внутренние детали ошибок
          if (isProd) {
            // Проверяем, это системная ошибка или бизнес-логика
            const isBusinessError =
              error.extensions?.code === 'BAD_USER_INPUT' ||
              error.extensions?.code === 'GRAPHQL_VALIDATION_FAILED' ||
              error.message.includes('not found') ||
              error.message.includes('unauthorized');

            if (isBusinessError) {
              // Бизнес ошибки можно показывать
              return {
                message: error.message,
                code: error.extensions?.code || 'USER_ERROR',
                path: error.path,
              };
            }

            // Системные ошибки скрываем
            return {
              message: 'Internal server error',
              code: 'INTERNAL_SERVER_ERROR',
            };
          }

          // В development возвращаем полную информацию
          return {
            message: error.message,
            code: error.extensions?.code || 'INTERNAL_SERVER_ERROR',
            path: error.path,
            locations: error.locations,
            extensions: error.extensions,
          };
        },
        // Plugin для логирования запросов
        plugins: [
          {
            requestDidStart: () =>
              ({
                didEncounterErrors: (ctx: any) => {
                  if (ctx.errors) {
                    ctx.errors.forEach((error: any) => {
                      // Санитайзируем чувствительные данные в логах
                      const sanitizedMessage = sanitizeErrorMessage(error.message);
                      console.error('GraphQL execution error:', sanitizedMessage);
                    });
                  }
                },
              }) as any,
          },
        ],
      }),
      inject: [ConfigService],
    }),
  ],
  providers: [DateTimeScalar, JSONScalar],
  exports: [],
})
export class GraphqlModule {}

/**
 * Санитайзация сообщений об ошибках
 * Удаляет пароли и другие чувствительные данные
 */
function sanitizeErrorMessage(message: string): string {
  if (!message) return message;

  // Удаляем пароли из сообщения
  return message.replace(/password['":\s]*['"]?[^'"\s,}]+/gi, 'password:***');
}
