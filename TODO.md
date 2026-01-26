# Unmatched Digital Edition - Документация проекта

## 📋 О проекте

Цифровая версия настольной карточной игры **Unmatched** с асимметричными героями, уникальными колодами и тактическим боем.

**Технологический стек:**
- Frontend: React 18 + TypeScript
- Build Tool: Vite
- State Management: Zustand
- Стилизация: CSS Modules

---

## ✅ Что уже реализовано

### 1. Базовая структура проекта

```
unmached/
├── src/
│   ├── core/                    # Игровой движок (без UI)
│   │   ├── models/              # Типы и модели данных
│   │   ├── engine/              # Ядро игровой логики
│   │   └── data/                # Данные героев и досок
│   ├── store/                   # Zustand stores
│   ├── components/              # React компоненты
│   └── hooks/                   # Custom hooks
```

### 2. Core - Игровой движок

#### Модели (`src/core/models/`)

| Файл | Описание |
|------|----------|
| [`types.ts`](src/core/models/types.ts) | Все TypeScript интерфейсы и enum'ы |
| [`Card.ts`](src/core/models/Card.ts) | Класс Card, создание колоды, значение карты |
| [`Fighter.ts`](src/core/models/Fighter.ts) | Класс Fighter, создание героев и sidekicks |
| [`Deck.ts`](src/core/models/Deck.ts) | Тасовка, вытягивание карт, сброс |
| [`Board.ts`](src/core/models/Board.ts) | Логика доски, зоны, позиции |
| [`GameState.ts`](src/core/models/GameState.ts) | Иммутируемое состояние игры |

#### Движок (`src/core/engine/`)

| Файл | Описание |
|------|----------|
| [`GameEngine.ts`](src/core/engine/GameEngine.ts) | Главный контроллер, инициализация игры |
| [`CombatResolver.ts`](src/core/engine/CombatResolver.ts) | Разрешение боя, расчёт урона |
| [`MovementSystem.ts`](src/core/engine/MovementSystem.ts) | Перемещение по зонам, валидация |
| [`TurnManager.ts`](src/core/engine/TurnManager.ts) | Управление фазами хода |

#### Данные (`src/core/data/`)

| Файл | Описание |
|------|----------|
| [`heroes/ms-marvel.ts`](src/core/data/heroes/ms-marvel.ts) | Ms. Marvel (14 HP, 15 карт) |
| [`heroes/daredevil.ts`](src/core/data/heroes/daredevil.ts) | Daredevil (17 HP, 15 карт) |
| [`boards/cobble-city.ts`](src/core/data/boards/cobble-city.ts) | Доска Cobble City 6x4 |

### 3. State Management

| Файл | Описание |
|------|----------|
| [`gameStore.ts`](src/store/gameStore.ts) | Основное состояние игры (Zustand) |
| [`uiStore.ts`](src/store/uiStore.ts) | UI состояние, модальные окна, лог |

### 4. UI Компоненты

| Файл | Описание |
|------|----------|
| [`BoardView.tsx`](src/components/board/BoardView.tsx) | Визуализация доски с зонами |
| [`Card.tsx`](src/components/cards/Card.tsx) | Компонент карты |
| [`HandView.tsx`](src/components/cards/HandView.tsx) | Рука игрока |
| [`GameControls.tsx`](src/components/controls/GameControls.tsx) | Контролы управления игрой |

### 5. Реализованные механики игры

#### Структура хода
- ✅ 2 действия за ход (Maneuver, Scheme, Attack)
- ✅ Фазы: SETUP → START_OF_TURN → ACTION_SELECTION → COMBAT → END_OF_TURN
- ✅ Определение текущего игрока и смена хода

#### Система боя
- ✅ Инициация атаки с картой рубашкой вниз
- ✅ Возможность сыграть карту защиты
- ✅ Одновременное вскрытие карт
- ✅ Расчёт урона: max(0, атака - защита)
- ✅ Применение урона к бойцу
- ✅ Сброс карт в сброс

#### Перемещение
- ✅ Zone-based движение (по цветным зонам)
- ✅ BFS поиск валидных перемещений
- ✅ Проверка препятствий и других бойцов
- ✅ Подсветка валидных клеток на доске

#### Герои
- ✅ Ms. Marvel (14 HP, movement 2, способность Stretchy)
  - 15 карт: Embiggen, Big Wind Up, Easy Peasy, Feint, Groovy
- ✅ Daredevil (17 HP, movement 3, способность Blind Boost)
  - 15 карт: Billy Club, Radar Sense, Mania, Grappling Hook, Daredevil

---

## 🚧 Что предстоит сделать

### Приоритет 1 - Критическая функциональность

#### 1.1 Эффекты карт
**Файл:** `src/core/engine/EffectProcessor.ts`

Эффекты карт определены, но не обрабатываются. Необходимо реализовать:

| Тип эффекта | Пример |
|-------------|---------|
| `Immediately` | Feint: "Cancel all effects on opponent's card" |
| `During Combat` | Big Wind Up: "BOOST if shares no zones" |
| `After Combat` | Easy Peasy: "Draw 1 card. Deal 1 damage if 4+ cards in hand" |

```typescript
// Пример структуры для реализации
interface EffectProcessor {
  processImmediateEffects(state, combat, card): GameState;
  processDuringCombatEffects(state, combat, card): GameState;
  processAfterCombatEffects(state, combat, card): GameState;
}
```

#### 1.2 Способности героев
**Файл:** `src/core/engine/abilities/`

- [ ] **Ms. Marvel - Stretchy**: Дополнительное перемещение на 1 клетку в начале хода
- [ ] **Ms. Marvel - Stretchy**: Атака с расстояния 2 (игнорирует зоны)
- [ ] **Daredevil - Blind Boost**: Сыграть верхнюю карту колоды для boost

### Приоритет 2 - UI/UX улучшения

#### 2.1 Combat Dialog
**Файл:** `src/components/combat/CombatDialog.tsx`

- [ ] Модальное окно для выбора карты защиты
- [ ] Отображение атакующей и защищающей карт (лицевой стороной)
- [ ] Анимация подсчёта урона
- [ ] Отображение результатов боя

#### 2.2 Action Selector
**Файл:** `src/components/controls/ActionSelector.tsx`

- [ ] Интерактивный выбор действия (Maneuver/Attack/Pass)
- [ ] Подсветка доступных действий
- [ ] Отображение использованных действий

#### 2.3 Card Interactions
- [ ] Клик по карте → выбор действия (атака/защита)
- [ ] Drag & drop карт
- [ ] Hover эффект с увеличением карты
- [ ] Анимация сброса карт

### Приоритет 3 - Расширение игры

#### 3.1 Новые герои
**Папка:** `src/core/data/heroes/`

- [ ] **Invisible Woman** (17 HP, 4 sidekicks)
- [ ] **Scarlet Witch** (15 HP)
- [ ] **Dracula** (20 HP, 2 bats)
- [ ] **Jekyll & Hyde** (14 HP, трансформация)

#### 3.2 Новые доски
**Папка:** `src/core/data/boards/`

- [ ] **Cobble Fog** (для 2-4 игроков)
- [ **Atlantis** (водная тематика)
- [ ] **Asgard** (нордическая тематика)

#### 3.3 Scheme карты
- [ ] Тип карт SCHEME отдельно от ATTACK/DEFENSE
- [ ] Обработка scheme эффектов
- [ ] Отображение scheme карт в UI

### Приоритет 4 - Полноценная игровая механика

#### 4.1 Правила руками
- [ ] Рука ограничена 7 картами
- [ ] Сброс лишних карт в конце хода
- [ ] Выбор карт для сброса

#### 4.2 Истощение колоды
- [ ] Перемешивание сброса в колоду при опустошении
- [ ] Урон от истощения (1 damage за невозможность взять карту)

#### 4.3 Победа и поражение
- [ ] Проверка всех бойцов = 0 HP
- [ ] Экран победителя
- [ ] Статистика игры

#### 4.4 Sidekicks (спутники)
- [ ] Sidekicks с 1 HP
- [ ] Независимое перемещение sidekicks
- [] Sidekicks могут "блокировать" атаки

### Приоритет 5 - Улучшения интерфейса

#### 5.1 Анимации
- [ ] Анимация перемещения бойцов
- [ ] Анимация игры карт
- [ ] Анимация получения урона
- [ ] Анимация сброса карт

#### 5.2 Визуальные эффекты
- [ ] Полоска здоровья с анимацией
- [ ] Индикаторы статусов (boost, poison и т.д.)
- [ ] Лог игры (история действий)

#### 5.3 Адаптивность
- [ ] Мобильная версия
- [ ] Разные размеры досок
- [ ] Настройки качества графики

### Приоритет 6 - Расширенные возможности

#### 6.1 Мультиплеер
- [ ] Hot-seat (2 игрока на одном устройстве) — **базовая версия готова**
- [ ] Онлайн-режим через WebSocket
- [ ] Рейтинговая система

#### 6.2 AI противник
- [ ] Простой AI (случайные действия)
- [ ] Средний AI (оценка карт)
- [ ] Сложный AI (минимакс с альфа-бета отсечением)

#### 6.3 Редактор колод
- [ ] Создание кастомных героев
- [ ] Создание кастомных карт
- [ ] Импорт/экспорт колод

#### 6.4 Контент
- [ ] Больше официальных героев из Unmatched
- [ ] Fan-made герои
- [ ] Tournament mode

---

## 📚 Справочные материалы

### Официальные источники Unmatched

| Источник | Описание |
|----------|----------|
| [Unmatched Cards](https://unmatched.cards/) | База данных всех карт и героев |
| [Restoration Games](https://restorationgames.com/) | Официальный сайт издателя |
| [IELLO Games](https://iellogames.com/) | Издатель локализованных версий |
| [Reddit r/Unmatched](https://www.reddit.com/r/Unmatched/) | Сообщество, обсуждения |

### Правила и FAQ

- **Туман над мостовой (Cobble & Fog)** - правила на русском
- **Справочник уточнений** - FAQ по взаимодействию карт
- **Тир-листы** - рейтинги героев для баланса

---

## 🛠️ Разработка

### Команды

```bash
npm install       # Установка зависимостей
npm run dev        # Запуск dev сервера (http://localhost:5173)
npm run build      # Сборка продакшн версии
npm run preview    # Предпросмотр собранной версии
```

### Структура типизации

```typescript
// Карта
interface CardDefinition {
  id: string;
  title: string;
  type: CardType;        // ATTACK | DEFENSE | VERSATILE | SCHEME
  value: number;         // 0-6
  boost: number;         // 0-3
  quantity: number;      // Количество в колоде
  effects: CardEffect[];
  characterName: string;
}

// Боец
interface Fighter {
  id: string;
  definitionId: string;
  type: FighterType;     // HERO | SIDEKICK
  health: number;
  maxHealth: number;
  position: Position;
  ownerId: string;
  isDefeated: boolean;
}

// Состояние игры
interface GameState {
  id: string;
  players: Player[];
  board: BoardState;
  currentTurn: TurnState;
  phase: GamePhase;
  combatState: CombatState | null;
  winner: string | null;
  turnCount: number;
}
```

---

## 📝 TODO - Быстрый список

### Критично (для игры)
- [ ] Реализовать `EffectProcessor`
- [ ] Способность Ms. Marvel (Stretchy - движение +1)
- [ ] Combat Dialog UI
- [ ] Выбор карты защиты

### Важно (для качества)
- [ ] Остальные способности героев
- [ ] Scheme карты
- [ ] Правила руками (7 карт)
- [ ] Истощение колоды

### Желательно (для полноты)
- [ ] Новые герои (Invisible Woman, Scarlet Witch)
- [ ] Анимации
- [ ] Лог игры
- [ ] AI противник

---

*Документ обновляется по мере разработки проекта.*
