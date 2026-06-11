# GraphQL на фронтенде

## Структура

```
src/
├── graphql/
│   ├── queries/           # GraphQL запросы
│   │   ├── auth.graphql
│   │   └── game.graphql
│   ├── mutations/         # GraphQL мутации
│   │   ├── auth.graphql
│   │   └── game.graphql
│   └── subscriptions/     # GraphQL подписки
│       └── game.graphql
├── gql/                  # Сгенерированные типы
│   ├── graphql.ts        # TypeScript типы
│   ├── gql.ts            # gql функция с типами
│   └── index.ts          # Экспорты
├── lib/
│   └── apolloClient.ts   # Apollo Client конфигурация
└── components/example/
    └── ApolloExample.tsx # Примеры использования
```

## Использование

### 1. Создание GraphQL операции

Создай файл в `src/graphql/queries/`, `mutations/` или `subscriptions/`:

```graphql
# src/graphql/queries/my-query.graphql
query GetMyData($id: String!) {
  game(id: $id) {
    id
    status
    players {
      username
    }
  }
}
```

### 2. Генерация типов

```bash
npm run codegen:build    # Одноразовая генерация
npm run codegen          # Watch режим (авто-генерация)
```

### 3. Использование в компонентах

```tsx
import { useGetMyDataQuery } from '@/gql';

function MyComponent() {
  const { data, loading, error } = useGetMyDataQuery({
    variables: { id: '123' },
  });

  if (loading) return <div>Loading...</div>;
  if (error) return <div>Error</div>;

  return <div>{data?.game?.players.map(p => p.username)}</div>;
}
```

## Доступные хуки

После генерации автоматически создаются хуки:

- `use<QueryName>Query` — для запросов
- `use<MutationName>Mutation` — для мутаций
- `use<SubscriptionName>Subscription` — для подписок

## Примеры

### Query

```tsx
const { data } = useMeQuery();
const user = data?.me;
```

### Mutation

```tsx
const [login] = useLoginMutation();

const handleLogin = () => {
  login({
    variables: {
      input: { email: 'test@test.com', password: '123' }
    }
  });
};
```

### Subscription

```tsx
useGameStateUpdatedSubscription({
  variables: { gameId: '123', since: 0 },
  onData: ({ data }) => {
    console.log('Game updated!', data?.gameStateUpdated);
  }
});
```
