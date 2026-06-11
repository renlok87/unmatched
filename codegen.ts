import type { CodegenConfig } from '@graphql-codegen/cli';

const config: CodegenConfig = {
  schema: [
    {
      ['http://localhost:3000/graphql']: {
        headers: {
          // Можно добавить токен для приватных схем
          // Authorization: 'Bearer YOUR_TOKEN',
        },
      },
    },
  ],
  documents: ['src/graphql/**/*.graphql'],
  generates: {
    './src/gql/': {
      preset: 'client',
      presetConfig: {
        // Использовать gql из @apollo/client
        gqlTagName: 'gql',
        // Автоматически импортировать fragment spread mask
        fragmentMasking: { unmaskFunctionName: 'getFragment' },
      },
      plugins: [],
    },
  },
};

export default config;
