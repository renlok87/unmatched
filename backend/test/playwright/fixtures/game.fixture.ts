/**
 * Game Fixture
 *
 * Фикстура для создания и управления играми в тестах.
 * Предоставляет методы для создания игр, присоединения к ним,
 * и выполнения игровых действий.
 */

import { test as base, Page } from '@playwright/test';
import { ApiService, CreateGameDto, JoinGameDto } from '../src/services/api.service';
import { GameGenerator } from '../src/generators/game.generator';
import { HEROES, URLS } from './data';
import type { Position } from '../src/services/api.service';

// ============================================================
// Types
// ============================================================

interface TestGame {
  id: string;
  name: string;
  status: string;
  players: Array<{
    userId: string;
    heroId: string;
  }>;
}

type GameFixtures = {
  /**
   * Создаёт новую игру через API
   */
  createGame: (options?: {
    name?: string;
    gameMode?: string;
    maxPlayers?: number;
  }) => Promise<string>;

  /**
   * Присоединяется к игре с выбранным героем
   */
  joinGame: (gameId: string, heroId: string) => Promise<void>;

  /**
   * Создаёт игру и ждёт второго игрока
   */
  createAndWaitForOpponent: (heroId: string) => Promise<TestGame>;

  /**
   * Выполняет полный манёвр (перемещение + карта)
   */
  executeManeuver: (
    gameId: string,
    fighterId: string,
    cardId: string,
    path: Position[],
  ) => Promise<void>;

  /**
   * Выполняет атаку
   */
  executeAttack: (
    gameId: string,
    attackerId: string,
    targetId: string,
    cardId: string,
  ) => Promise<void>;

  /**
   * Выполняет защиту
   */
  executeDefense: (gameId: string, cardId: string) => Promise<void>;

  /**
   * Разрешает бой
   */
  executeResolveCombat: (gameId: string) => Promise<void>;

  /**
   * Завершает ход
   */
  executeEndTurn: (gameId: string) => Promise<void>;

  /**
   * Создаёт mock состояние игры для тестов UI
   */
  mockGameState: (page: Page, state: 'victory' | 'defeat' | 'turn' | 'combat') => Promise<void>;

  /**
   * Быстрое создание 1v1 игры для тестов
   */
  setup1v1Game: (player1Hero: string, player2Hero: string) => Promise<{
    gameId: string;
    player1Id: string;
    player2Id: string;
  }>;
};

// ============================================================
// Game Fixtures
// ============================================================

export const gameFixtures = {
  // --------------------------------------------------------
  // createGame
  // --------------------------------------------------------
  createGame: async ({ api }, use) => {
    const createdGames: string[] = [];

    await use(async (options?: {
      name?: string;
      gameMode?: string;
      maxPlayers?: number;
    }) => {
      const input: CreateGameDto = {
        name: options?.name || `E2E Test Game ${Date.now()}`,
        gameMode: options?.gameMode || 'standard',
        maxPlayers: options?.maxPlayers || 2,
      };

      const game = await api.createGame(input);
      createdGames.push(game.id);

      return game.id;
    });

    // Cleanup (опционально - можно удалять игры после тестов)
    // for (const gameId of createdGames) {
    //   await api.leaveGame(gameId);
    // }
  },

  // --------------------------------------------------------
  // joinGame
  // --------------------------------------------------------
  joinGame: async ({ api }, use) => {
    await use(async (gameId: string, heroId: string) => {
      const input: JoinGameDto = {
        gameId,
        heroId,
      };

      await api.joinGame(input);
    });
  },

  // --------------------------------------------------------
  // createAndWaitForOpponent
  // --------------------------------------------------------
  createAndWaitForOpponent: async ({ api, createRandomUser }, use) => {
    const createdGames: TestGame[] = [];

    await use(async (heroId: string) => {
      // Создаём игру
      const gameId = await api.createGame({
        name: `E2E Test Game ${Date.now()}`,
        gameMode: 'standard',
        maxPlayers: 2,
      });

      // Присоединяемся с героем
      await api.joinGame({ gameId, heroId });

      const game: TestGame = {
        id: gameId,
        name: `E2E Test Game`,
        status: 'WAITING',
        players: [
          { userId: 'player1', heroId },
        ],
      };

      createdGames.push(game);
      return game;
    });

    // Cleanup
    // for (const game of createdGames) {
    //   await api.leaveGame(game.id);
    // }
  },

  // --------------------------------------------------------
  // executeManeuver
  // --------------------------------------------------------
  executeManeuver: async ({ api }, use) => {
    await use(async (
      gameId: string,
      fighterId: string,
      cardId: string,
      path: Position[],
    ) => {
      await api.maneuver({ gameId, fighterId, cardId, path });
    });
  },

  // --------------------------------------------------------
  // executeAttack
  // --------------------------------------------------------
  executeAttack: async ({ api }, use) => {
    await use(async (
      gameId: string,
      attackerId: string,
      targetId: string,
      cardId: string,
    ) => {
      await api.attack({ gameId, attackerId, targetId, cardId });
    });
  },

  // --------------------------------------------------------
  // executeDefense
  // --------------------------------------------------------
  executeDefense: async ({ api }, use) => {
    await use(async (gameId: string, cardId: string) => {
      await api.playDefense({ gameId, cardId });
    });
  },

  // --------------------------------------------------------
  // executeResolveCombat
  // --------------------------------------------------------
  executeResolveCombat: async ({ api }, use) => {
    await use(async (gameId: string) => {
      await api.resolveCombat({ gameId });
    });
  },

  // --------------------------------------------------------
  // executeEndTurn
  // --------------------------------------------------------
  executeEndTurn: async ({ api }, use) => {
    await use(async (gameId: string) => {
      await api.endTurn({ gameId });
    });
  },

  // --------------------------------------------------------
  // mockGameState
  // --------------------------------------------------------
  mockGameState: async ({ page }, use) => {
    await use(async (state: 'victory' | 'defeat' | 'turn' | 'combat') => {
      await page.goto(URLS.BASE);

      // Инжектим mock состояние через window object
      await page.evaluate((gameState) => {
        (window as any).testGameState = gameState;
        window.dispatchEvent(new CustomEvent('test-state-set', { detail: gameState }));
      }, state);
    });
  },

  // --------------------------------------------------------
  // setup1v1Game
  // --------------------------------------------------------
  setup1v1Game: async ({ api, createRandomUser }, use) => {
    const setupGames: Array<{
      gameId: string;
      player1Id: string;
      player2Id: string;
    }> = [];

    await use(async (player1Hero: string, player2Hero: string) => {
      // Создаём первого игрока
      const user1 = await createRandomUser();
      const api1 = new ApiService(user1.token);

      // Создаём игру
      const game = await api1.createGame({
        name: `E2E 1v1 Game ${Date.now()}`,
        gameMode: 'standard',
        maxPlayers: 2,
      });

      // Player 1 присоединяется
      await api1.joinGame({ gameId: game.id, heroId: player1Hero });

      // Создаём второго игрока
      const user2 = await createRandomUser();
      const api2 = new ApiService(user2.token);

      // Player 2 присоединяется
      await api2.joinGame({ gameId: game.id, heroId: player2Hero });

      const result = {
        gameId: game.id,
        player1Id: user1.id,
        player2Id: user2.id,
      };

      setupGames.push(result);
      return result;
    });

    // Cleanup
    // Здесь можно добавить логику для очистки созданных игр
  },
};

// Экспортируем расширенный test
export const test = base.extend<GameFixtures>(gameFixtures);
