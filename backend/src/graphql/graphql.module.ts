import { Module } from '@nestjs/common';
import { GraphQLModule } from '@nestjs/graphql';
import { ApolloDriver, ApolloDriverConfig } from '@nestjs/apollo';
import { ConfigService } from '@nestjs/config';
import { DateTimeScalar, JSONScalar } from './scalars';

@Module({
  imports: [
    GraphQLModule.forRootAsync({
      driver: ApolloDriver,
      useFactory: (configService: ConfigService): ApolloDriverConfig => ({
        autoSchemaFile: true,
        sortSchema: true,
        playground: true,
        context: ({ req, res }: { req: any; res: any }) => ({ req, res }),
        formatError: (error: any) => {
          // Log errors for debugging
          console.error('GraphQL Error:', error);

          // Return formatted error to client
          return {
            message: error.message,
            code: error.extensions?.code || 'INTERNAL_SERVER_ERROR',
            path: error.path,
            locations: error.locations,
          };
        },
      }),
      inject: [ConfigService],
    }),
  ],
  providers: [DateTimeScalar, JSONScalar],
  exports: [],
})
export class GraphqlModule {}
