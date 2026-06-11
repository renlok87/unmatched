# Phaser Integration

## Обзор

Модуль `src/phaser/` содержит интеграцию игрового движка Phaser с React приложением для рендеринга игрового поля Unmatched.

## Структура

```
src/phaser/
├── PhaserGame.tsx       # React компонент-обёртка
├── types.ts             # TypeScript типы
├── index.ts             # Главный файл экспорта
├── scenes/
│   ├── BootScene.ts     # Сцена загрузки активов
│   ├── GameScene.ts     # Основная игровая сцена
│   └── UIScene.ts       # UI оверлей
└── assets/
    └── AssetLoader.ts   # Управление загрузкой активов
```

## Использование

### Базовое использование

```tsx
import { PhaserGame } from '@/phaser';

function MyComponent() {
  const handleGameEvent = (event) => {
    console.log('Событие из Phaser:', event);
  };

  return (
    <PhaserGame
      gameId="game-123"
      gameState={gameState}
      onGameEvent={handleGameEvent}
      width={800}
      height={600}
    />
  );
}
```

### Использование с GameView

Для интеграции с существующим GameView:

```tsx
import { PhaserBoard } from '@/components/phaser';

export const GameView = () => {
  return (
    <div className="game-view">
      <PhaserBoard />
      {/* Остальные компоненты UI */}
    </div>
  );
};
```

## События

### От Phaser к React

```typescript
type PhaserGameEvent =
  | { type: 'FIGHTER_CLICKED'; fighterId: string }
  | { type: 'SPACE_CLICKED'; position: Position }
  | { type: 'CARD_CLICKED'; cardId: string }
  | { type: 'ATTACK_CLICKED'; attackerId: string; targetId: string }
  | { type: 'PHASER_READY' }
  | { type: 'ANIMATION_COMPLETE'; animationId: string };
```

### От React к Phaser

```typescript
type ReactToPhaserEvent =
  | { type: 'SELECT_FIGHTER'; fighterId: string | null }
  | { type: 'SELECT_CARD'; cardId: string | null }
  | { type: 'HIGHLIGHT_SPACES'; spaces: Position[] }
  | { type: 'MOVE_FIGHTER'; fighterId: string; position: Position }
  | { type: 'ATTACK'; attackerId: string; targetId: string; cardId: string }
  | { type: 'DEFEND'; cardId: string }
  | { type: 'UPDATE_STATE'; state: GameState }
  | { type: 'SHOW_DAMAGE'; fighterId: string; amount: number }
  | { type: 'PLAY_CARD_ANIMATION'; cardId: string };
```

## Активы

Активы загружаются из `public/assets/`:

```
public/assets/
├── boards/
│   ├── cobalt-city.png
│   └── festering-grounds.png
├── fighters/
│   ├── ms-marvel.png
│   └── daredevil.png
├── cards/
│   └── ...
└── phaser/
    ├── board-placeholder.png
    ├── fighter-placeholder.png
    └── card-placeholder.png
```

## TODO Phase 0

- [x] Создать структуру директорий
- [x] Создать базовые типы TypeScript
- [x] Реализовать BootScene для загрузки активов
- [x] Реализовать GameScene с основными методами
- [x] Реализовать UIScene для координации с React
- [x] Создать AssetLoader для управления активами
- [x] Создать React компонент-обёртку PhaserGame
- [x] Интегрировать с существующим GameView
- [ ] Добавить placeholder активы в public/assets/
- [ ] Настроить анимации бойцов
- [ ] Добавить систему частиц для эффектов
- [ ] Реализовать звуковые эффекты

## Следующие шаги (Phase 1)

1. Создать placeholder изображения для активов
2. Реализовать отображение реального состояния игры
3. Добавить интерактивное перемещение бойцов
4. Реализовать систему анимаций карт
5. Добавить звуковые эффекты
