# ФАЗА 2: Hero Selection UI

## Задача 2.1 - HeroSelection

Экран выбора героя перед началом игры.

### Компоненты для создания:
```
src/components/heroes/
├── HeroSelection.tsx       # Главный компонент
├── HeroGrid.tsx            # Сетка героев
├── HeroCard.tsx            # Карточка героя
└── HeroDetailsPanel.tsx    # Панель деталей
```

---

### HeroSelection.tsx

**Функциональность:**
- Загрузка списка доступных героев при монтировании
- Отображение сетки героев
- Фильтрация по сету/фракции
- Поиск по имени
- Отображение уже выбранных героев соперников (заблокированы)
- Таймер выбора (опционально)
- Кнопка "Подтвердить выбор"

**GraphQL операции:**
```graphql
query AvailableHeroes($filters: HeroFilters) {
  availableHeroes(filters: $filters) {
    id
    name
    health
    movement
    set
    thumbnailUrl
    abilities { name description }
    fighterTypes
  }
}

query GameStatus($gameId: ID!) {
  game(id: $gameId) {
    id
    players {
      user { id username }
      hero { id name }
    }
  }
}

mutation SelectHero($gameId: ID!, $heroId: ID!) {
  selectHero(gameId: $gameId, heroId: $heroId) {
    id
    players { ... }
  }
}

subscription HeroSelectionUpdates($gameId: ID!) {
  gameUpdates(gameId: $gameId) {
    gameState {
      players {
        user { id }
        hero { id name }
      }
    }
  }
}
```

**Состояние (Zustand):**
```typescript
interface HeroSelectionStore {
  heroes: Hero[];
  selectedHero: Hero | null;
  takenHeroIds: string[];
  loading: boolean;
  filters: {
    set: string | null;
    search: string;
  };
  selectHero: (heroId: string) => Promise<void>;
  confirmSelection: () => Promise<void>;
}
```

---

### HeroGrid.tsx

**Функциональность:**
- Сетка карточек героев (responsive grid)
- Пустое состояние
- Индикатор загрузки
- Подсветка выбранного героя
- Затемнение заблокированных героев

---

### HeroCard.tsx

**Функциональность:**
- Отображение информации о герое:
  - Аватар/миниатюра
  - Имя
  - HP (здоровье)
  - Movement (перемещение)
  - Set (сет)
- Статус: доступен / выбран / заблокирован соперником
- Hover эффект с превью способностей
- Click для выбора

**Пропсы:**
```typescript
interface HeroCardProps {
  hero: Hero;
  selected: boolean;
  disabled: boolean;
  onClick: () => void;
  onHover?: () => void;
}
```

**Стили:**
- Размер: 200x280px
- Изображение героя занимает большую часть
- HP и Movement в углах
- Имя внизу
- Оверлей для заблокированных

---

### HeroDetailsPanel.tsx

**Функциональность:**
- Полное изображение героя
- Описание способностей (abilities)
- Состав колоды (количество карт по типам)
- Статистика (win rate, количество игр)
- Кнопка "Выбрать"

**GraphQL запрос для статистики:**
```graphql
query HeroStats($heroId: ID!) {
  heroStats(heroId: $heroId) {
    gamesPlayed
    wins
    winRate
    avgDamageDealt
  }
}
```

**Пропсы:**
```typescript
interface HeroDetailsPanelProps {
  hero: Hero;
  stats?: HeroStats;
  onSelect: () => void;
  onClose: () => void;
}
```

---

## Задача 2.2 - Данные героев

### Интерфейсы TypeScript:

```typescript
interface Hero {
  id: string;
  name: string;
  health: number;
  movement: number;
  set: string;
  abilities: SpecialAbility[];
  fighterTypes: FighterType[];
  thumbnailUrl: string;
  imageUrl: string;
  description?: string;
}

interface SpecialAbility {
  id: string;
  name: string;
  description: string;
  timing: EffectTiming;
}

type FighterType = 'hero' | 'sidekick';

type EffectTiming =
  | 'IMMEDIATELY'
  | 'DURING_COMBAT'
  | 'AFTER_COMBAT'
  | 'START_OF_TURN'
  | 'END_OF_TURN';

interface HeroStats {
  heroId: string;
  gamesPlayed: number;
  wins: number;
  winRate: number;
  avgDamageDealt: number;
}
```

---

## Задача 2.3 - Mock данные (для разработки)

Временные данные для тестирования UI:

```typescript
export const mockHeroes: Hero[] = [
  {
    id: 'daredevil',
    name: 'Daredevil',
    health: 17,
    movement: 3,
    set: 'Marvel',
    thumbnailUrl: '/heroes/daredevil-thumb.webp',
    imageUrl: '/heroes/daredevil-full.webp',
    fighterTypes: ['hero'],
    abilities: [
      {
        id: 'blind-boost',
        name: 'Blind Boost',
        description: 'Во время боя с 2 или меньше картами можете сбросить карту из колоды и использовать её усиление.',
        timing: 'DURING_COMBAT',
      },
    ],
  },
  {
    id: 'ms-marvel',
    name: 'Ms. Marvel',
    health: 18,
    movement: 3,
    set: 'Marvel',
    thumbnailUrl: '/heroes/ms-marvel-thumb.webp',
    imageUrl: '/heroes/ms-marvel-full.webp',
    fighterTypes: ['hero'],
    abilities: [
      {
        id: 'binary-powers',
        name: 'Binary Powers',
        description: 'При атаке или защите можете сбросить карту для увеличения значения.',
        timing: 'DURING_COMBAT',
      },
    ],
  },
  // ... больше героев
];
```

---

## Задача 2.4 - Hero Picker (быстрый выбор)

Альтернативный компонент для быстрого выбора героев.

```
src/components/heroes/
└── HeroPicker.tsx           # Быстрый выбор (compact)
```

**HeroPicker.tsx**
- Компактный список героев
- Для использования внутри CreateGameDialog
- Без детальной статистики
- Выбор одним кликом

---

## Результат ФАЗЫ 2

- ✅ Пользователь видит список доступных героев
- ✅ Пользователь может фильтровать героев
- ✅ Пользователь видит детали выбранного героя
- ✅ Пользователь видит заблокированных соперником героев
- ✅ Выбор героя отправляется на сервер
- ✅ Подтверждение выбора блокирует дальнейшие изменения

---

## Следующие шаги

→ [ФАЗА 3: Room Setup](./03-room-setup.md)
