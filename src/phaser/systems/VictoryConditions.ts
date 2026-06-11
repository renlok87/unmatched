// ============================================================
// VICTORY CONDITIONS - Система проверки условий победы/поражения
// ============================================================

import type { GameState } from '../../core/models/types';
import type { GameScene } from '../scenes/GameScene';
import type { GameStateBridge } from '../state/GameStateBridge';
import { GamePhase } from '../../core/models/types';

// Экспортируем типы
export * from './types';
import type { VictoryCheckResult } from './types';
import { VictoryResult } from './types';

// ------------------------------------------------------------
// Конфигурация системы победы
// ------------------------------------------------------------

export interface VictoryConditionsConfig {
  // Проверять уничтожение всех бойцов
  checkTotalKnockout: boolean;

  // Проверять специальные условия героев
  checkHeroAbilities: boolean;

  // Задержка перед показом экрана победы (мс)
  victoryDelay: number;

  // Callback при завершении игры
  onGameEnd: (result: VictoryCheckResult) => void;
}

// ------------------------------------------------------------
// Условия победы для конкретных героев
// ------------------------------------------------------------

interface HeroVictoryCondition {
  heroId: string;
  check: (state: GameState, playerId: string) => boolean;
  reason: string;
}

// Специальные условия победы для героев
const HERO_VICTORY_CONDITIONS: HeroVictoryCondition[] = [
  // Пример: King Arthur побеждает, если собрал Excalibur
  {
    heroId: 'king-arthur',
    check: (state, playerId) => {
      // Проверка наличия специального предмета/эффекта
      const player = state.players.find(p => p.id === playerId);
      if (!player) return false;

      // TODO: Проверка наличия Excalibur
      return false;
    },
    reason: 'Excalibur retrieved!',
  },
  // Пример: T Rex побеждает, если нанёс 50+ урона за игру
  {
    heroId: 'trex',
    check: (state, playerId) => {
      // TODO: Проверка общего нанесённого урона
      return false;
    },
    reason: 'Apex Predator: 50+ damage dealt!',
  },
  // Добавьте дополнительные условия для других героев
];

// ------------------------------------------------------------
// VictoryConditions - основная система
// ------------------------------------------------------------

export class VictoryConditions {
  private scene: GameScene;
  private bridge: GameStateBridge | null = null;
  private config: Required<VictoryConditionsConfig>;
  private localPlayerId: string;
  private isChecking: boolean = false;
  private checkTimeout: number | null = null;

  // Отслеживание побеждённых бойцов
  private defeatedFighters: Set<string> = new Set();

  constructor(
    scene: GameScene,
    localPlayerId: string,
    config: Partial<VictoryConditionsConfig> = {}
  ) {
    this.scene = scene;
    this.localPlayerId = localPlayerId;

    this.config = {
      checkTotalKnockout: config.checkTotalKnockout ?? true,
      checkHeroAbilities: config.checkHeroAbilities ?? true,
      victoryDelay: config.victoryDelay ?? 1500,
      onGameEnd: config.onGameEnd ?? (() => {}),
    };
  }

  // ------------------------------------------------------------
  // Публичные методы
  // ------------------------------------------------------------

  /**
   * Устанавливает мост состояния для получения актуальных данных
   */
  setGameStateBridge(bridge: GameStateBridge): void {
    this.bridge = bridge;
  }

  /**
   * Проверяет условия победы/поражения
   * @param state Текущее состояние игры
   * @returns Результат проверки
   */
  checkVictory(state: GameState): VictoryCheckResult {
    // Предотвращаем повторную проверку
    if (this.isChecking) {
      return { result: VictoryResult.NONE, winnerId: null, reason: '', defeatedFighters: [] };
    }

    // Игра уже завершена
    if (state.phase === GamePhase.GAME_OVER || state.winner) {
      return {
        result: this.determineResult(state.winner),
        winnerId: state.winner,
        reason: state.winner ? 'Game Over' : 'Draw',
        defeatedFighters: Array.from(this.defeatedFighters),
      };
    }

    // Проверяем общее условие - уничтожение всех бойцов
    if (this.config.checkTotalKnockout) {
      const koResult = this.checkTotalKnockoutCondition(state);
      if (koResult.result !== VictoryResult.NONE) {
        return koResult;
      }
    }

    // Проверяем специальные условия героев
    if (this.config.checkHeroAbilities) {
      const heroResult = this.checkHeroVictoryConditions(state);
      if (heroResult.result !== VictoryResult.NONE) {
        return heroResult;
      }
    }

    return {
      result: VictoryResult.NONE,
      winnerId: null,
      reason: '',
      defeatedFighters: [],
    };
  }

  /**
   * Проверяет условия победы с задержкой (для анимаций)
   */
  checkVictoryDelayed(state: GameState): void {
    if (this.checkTimeout) {
      return; // Уже есть проверка в процессе
    }

    this.checkTimeout = window.setTimeout(() => {
      const result = this.checkVictory(state);

      if (result.result !== VictoryResult.NONE) {
        this.handleGameEnd(result);
      }

      this.checkTimeout = null;
    }, this.config.victoryDelay);
  }

  /**
   * Регистрирует побеждённого бойца
   */
  registerDefeatedFighter(fighterId: string): void {
    this.defeatedFighters.add(fighterId);
    console.log(`[VictoryConditions] Боец ${fighterId} повержен`);

    // Проверяем условия победы после каждого поражения
    if (this.bridge) {
      const state = this.getCurrentState();
      if (state) {
        this.checkVictoryDelayed(state);
      }
    }
  }

  /**
   * Сбрасывает состояние (для новой игры)
   */
  reset(): void {
    this.defeatedFighters.clear();
    this.isChecking = false;

    if (this.checkTimeout) {
      clearTimeout(this.checkTimeout);
      this.checkTimeout = null;
    }
  }

  // ------------------------------------------------------------
  // Приватные методы проверки
  // ------------------------------------------------------------

  /**
   * Проверяет условие полного уничтожения бойцов
   */
  private checkTotalKnockoutCondition(state: GameState): VictoryCheckResult {
    const playersWithFighters: string[] = [];

    // Находим всех игроков, у которых остались живые бойцы
    for (const player of state.players) {
      const aliveFighters = player.fighters.filter(f => !f.isDefeated && f.health > 0);

      if (aliveFighters.length > 0) {
        playersWithFighters.push(player.id);
      }

      // Обновляем список побеждённых
      aliveFighters.forEach(f => {
        if (this.defeatedFighters.has(f.id)) {
          this.defeatedFighters.delete(f.id); // Боец восстановлен (не должно происходить)
        }
      });

      player.fighters.forEach(f => {
        if (f.isDefeated || f.health <= 0) {
          this.defeatedFighters.add(f.id);
        }
      });
    }

    // Если остался только один игрок с бойцами - он победил
    if (playersWithFighters.length === 1) {
      const winnerId = playersWithFighters[0];
      const isLocalWinner = winnerId === this.localPlayerId;

      return {
        result: isLocalWinner ? VictoryResult.VICTORY : VictoryResult.DEFEAT,
        winnerId,
        reason: 'Total Knockout! All enemy fighters defeated.',
        defeatedFighters: Array.from(this.defeatedFighters),
      };
    }

    // Если нет игроков с бойцами - ничья
    if (playersWithFighters.length === 0) {
      return {
        result: VictoryResult.DRAW,
        winnerId: null,
        reason: 'Double Knockout! All fighters defeated.',
        defeatedFighters: Array.from(this.defeatedFighters),
      };
    }

    return {
      result: VictoryResult.NONE,
      winnerId: null,
      reason: '',
      defeatedFighters: [],
    };
  }

  /**
   * Проверяет специальные условия победы героев
   */
  private checkHeroVictoryConditions(state: GameState): VictoryCheckResult {
    // Проверяем каждого игрока
    for (const player of state.players) {
      // Находим героя игрока
      const hero = player.fighters.find(f => f.type === 'hero');

      if (!hero) continue;

      // Проверяем условия для этого героя
      for (const condition of HERO_VICTORY_CONDITIONS) {
        if (hero.definitionId === condition.heroId) {
          if (condition.check(state, player.id)) {
            const isLocalPlayer = player.id === this.localPlayerId;

            return {
              result: isLocalPlayer ? VictoryResult.VICTORY : VictoryResult.DEFEAT,
              winnerId: player.id,
              reason: condition.reason,
              defeatedFighters: Array.from(this.defeatedFighters),
            };
          }
        }
      }
    }

    return {
      result: VictoryResult.NONE,
      winnerId: null,
      reason: '',
      defeatedFighters: [],
    };
  }

  // ------------------------------------------------------------
  // Обработчики событий
  // ------------------------------------------------------------

  /**
   * Обрабатывает завершение игры
   */
  private handleGameEnd(result: VictoryCheckResult): void {
    this.isChecking = true;

    console.log('[VictoryConditions] Игра завершена:', result);

    // Останавливаем ввод пользователя
    this.scene.input.enabled = false;

    // Вызываем callback
    this.config.onGameEnd(result);

    // Через некоторое время возвращаем ввод (если нужно будет показать UI)
    setTimeout(() => {
      this.isChecking = false;
    }, 2000);
  }

  // ------------------------------------------------------------
  // Утилиты
  // ------------------------------------------------------------

  /**
   * Получает текущее состояние игры из bridge
   */
  private getCurrentState(): GameState | null {
    return this.bridge?.getCurrentState() ?? null;
  }

  /**
   * Определяет результат для локального игрока
   */
  private determineResult(winnerId: string | null): VictoryResult {
    if (!winnerId) {
      return VictoryResult.DRAW;
    }

    return winnerId === this.localPlayerId ? VictoryResult.VICTORY : VictoryResult.DEFEAT;
  }

  /**
   * Проверяет, является ли игрок локальным
   */
  private isLocalPlayer(playerId: string): boolean {
    return playerId === this.localPlayerId;
  }

  /**
   * Уничтожает объект и очищает ресурсы
   */
  destroy(): void {
    this.reset();
  }
}

// ------------------------------------------------------------
// Фабричная функция для создания системы
// ------------------------------------------------------------

export function createVictoryConditions(
  scene: GameScene,
  localPlayerId: string,
  config?: Partial<VictoryConditionsConfig>
): VictoryConditions {
  return new VictoryConditions(scene, localPlayerId, config);
}
