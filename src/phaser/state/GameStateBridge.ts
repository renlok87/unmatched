/**
 * @deprecated B5: параллельный черновик интеграции с бэком; единый источник
 * истины — remoteGameStore + gameStateAdapter (B2). Кандидат на удаление.
 */
// ============================================================
// GAME STATE BRIDGE - Мост между React и Phaser
// ============================================================

import type { GameScene } from '../scenes/GameScene';
import type { GameActions, ActionResult } from '../network/GameActions';
import type { GameStateUpdate, GameEvent } from '../network/SubscriptionHandler';
import type { GameState, Position } from '../../core/models/types';
import type { VictoryConditions, VictoryCheckResult } from '../systems';
import { GamePhase } from '../../core/models/types';

// ------------------------------------------------------------
// Типы для моста состояний
// ------------------------------------------------------------

/**
 * Diff для применения к состоянию
 */
export interface StateDiff {
  sequenceNumber: number;
  changes: {
    fighters?: FighterDiff[];
    cards?: CardDiff[];
    phase?: string;
    turnCount?: number;
    currentTurnPlayerId?: string;
  };
}

/**
 * Изменение бойца
 */
export interface FighterDiff {
  id: string;
  position?: Position;
  health?: number;
  isDefeated?: boolean;
}

/**
 * Изменение карты
 */
export interface CardDiff {
  id: string;
  location?: 'hand' | 'discard' | 'deck' | 'played';
  isFaceDown?: boolean;
}

/**
 * Игровое действие
 */
export type GameAction =
  | { type: 'MANEUVER'; params: { fighterId: string; cardId: string; path: Position[] } }
  | { type: 'MOVE_FIGHTER'; params: { fighterId: string; position: Position } }
  | { type: 'ATTACK'; params: { attackerId: string; targetId: string; cardId: string } }
  | { type: 'PLAY_DEFENSE'; params: { combatId: string; cardId: string } }
  | { type: 'RESOLVE_COMBAT'; params: { combatId: string } }
  | { type: 'END_TURN'; params: {} }
  | { type: 'PASS'; params: {} }
  | { type: 'TOGGLE_DOOR'; params: { doorId: string } };

/**
 * Конфигурация моста
 */
export interface BridgeConfig {
  enableOptimisticUpdates?: boolean;
  maxPendingActions?: number;
  rollbackOnError?: boolean;
}

// ------------------------------------------------------------
// GameStateBridge класс
// ------------------------------------------------------------

/**
 * GameStateBridge управляет синхронизацией состояния между
 * сервером, React store и Phaser сценой
 *
 * Функционал:
 * - Оптимистичные обновления (применение действий до ответа сервера)
 * - Rollback при ошибке
 * - Применение state diff от сервера
 * - Маршрутизация действий в GameActions
 */
export class GameStateBridge {
  private scene: GameScene;
  private actions: GameActions;
  private gameId: string;
  private config: Required<BridgeConfig>;

  // Локальное состояние
  private localState: GameState | null = null;
  private lastServerSequence = 0;

  // Очередь оптимистичных обновлений
  private pendingActions: Map<string, {
    action: GameAction;
    optimisticState: Partial<GameState>;
    timestamp: number;
  }> = new Map();

  // История для rollback
  private stateHistory: Array<{
    state: GameState;
    sequenceNumber: number;
    timestamp: number;
  }> = [];
  private readonly maxHistorySize = 50;

  // Слушатели событий
  private listeners: {
    onStateChange?: (state: GameState) => void;
    onActionPending?: (actionId: string) => void;
    onActionComplete?: (actionId: string, result: ActionResult) => void;
    onActionError?: (actionId: string, error: string) => void;
    onRollback?: (previousState: GameState) => void;
    onGameEnd?: (result: VictoryCheckResult) => void;
  } = {};

  // Система проверки условий победы
  private victoryConditions: VictoryConditions | null = null;

  constructor(
    scene: GameScene,
    actions: GameActions,
    gameId: string,
    config: BridgeConfig = {}
  ) {
    this.scene = scene;
    this.actions = actions;
    this.gameId = gameId;

    this.config = {
      enableOptimisticUpdates: config.enableOptimisticUpdates ?? true,
      maxPendingActions: config.maxPendingActions ?? 10,
      rollbackOnError: config.rollbackOnError ?? true,
    };
  }

  // ------------------------------------------------------------
  // Публичные методы
  // ------------------------------------------------------------

  /**
   * Синхронизировать полное состояние
   *
   * Вызывается при начальной загрузке или при потере синхронизации.
   */
  syncState(state: GameState): void {
    console.log('[GameStateBridge] Синхронизация состояния, seq:', state);

    // Сохраняем в историю
    this.addToHistory(state);

    // Обновляем локальное состояние
    this.localState = state;

    // Применяем к сцене
    this.applyStateToScene(state);

    // Проверяем условия победы
    this.checkVictoryConditions();

    // Уведомляем слушателей
    this.listeners.onStateChange?.(state);
  }

  /**
   * Применить diff от сервера
   *
   * Вызывается при получении обновления через WebSocket.
   */
  applyDiff(update: GameStateUpdate): void {
    console.log('[GameStateBridge] Применение diff, seq:', update.sequenceNumber);

    // Проверяем sequence number
    if (update.sequenceNumber <= this.lastServerSequence) {
      console.warn('[GameStateBridge] Пропуск устаревшего diff');
      return;
    }

    // Проверяем оптимистичные обновления
    this.checkOptimisticUpdates(update.sequenceNumber);

    // Парсим и применяем изменения
    const diff = this.parseDiff(update);

    if (this.localState) {
      this.localState = this.applyDiffToState(this.localState, diff);
    }

    this.lastServerSequence = update.sequenceNumber;

    // Применяем к сцене
    this.applyDiffToScene(diff);

    // Проверяем условия победы (особенно после боя)
    this.checkVictoryConditions();

    // Уведомляем слушателей
    if (this.localState) {
      this.listeners.onStateChange?.(this.localState);
    }
  }

  /**
   * Выполнить игровое действие
   *
   * - Создаёт оптимистичное обновление (если включено)
   * - Отправляет действие на сервер
   * - При успехе подтверждает обновление
   * - При ошибке выполняет rollback
   */
  async executeAction(action: GameAction): Promise<ActionResult> {
    const actionId = this.generateActionId();

    console.log('[GameStateBridge] Выполнение действия:', action.type, actionId);

    // Проверяем лимит pending действий
    if (this.pendingActions.size >= this.config.maxPendingActions) {
      return {
        success: false,
        error: 'Слишком много ожидающих действий',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    // Создаём оптимистичное состояние
    let optimisticState: Partial<GameState> | null = null;

    if (this.config.enableOptimisticUpdates && this.localState) {
      optimisticState = this.computeOptimisticState(this.localState, action);

      if (optimisticState) {
        // Применяем оптимистичное обновление
        this.pendingActions.set(actionId, {
          action,
          optimisticState,
          timestamp: Date.now(),
        });

        // Применяем к сцене
        this.applyOptimisticUpdate(action, optimisticState);

        // Уведомляем о pending действии
        this.listeners.onActionPending?.(actionId);
      }
    }

    // Выполняем действие на сервере
    let result: ActionResult;

    try {
      switch (action.type) {
        case 'MANEUVER':
          result = await this.actions.maneuver({
            gameId: this.gameId,
            fighterId: action.params.fighterId,
            cardId: action.params.cardId,
            path: action.params.path,
          });
          break;

        case 'MOVE_FIGHTER':
          result = await this.actions.moveFighter({
            gameId: this.gameId,
            fighterId: action.params.fighterId,
            x: action.params.position.x,
            y: action.params.position.y,
          });
          break;

        case 'ATTACK':
          result = await this.actions.attack({
            gameId: this.gameId,
            attackerId: action.params.attackerId,
            targetId: action.params.targetId,
            cardId: action.params.cardId,
          });
          break;

        case 'PLAY_DEFENSE':
          result = await this.actions.playDefense({
            gameId: this.gameId,
            combatId: action.params.combatId,
            cardId: action.params.cardId,
          });
          break;

        case 'RESOLVE_COMBAT':
          result = await this.actions.resolveCombat({
            gameId: this.gameId,
          });
          break;

        case 'END_TURN':
          result = await this.actions.endTurn({
            gameId: this.gameId,
            playerId: '', // Будет определён на сервере
          });
          break;

        case 'PASS':
          result = await this.actions.pass({
            gameId: this.gameId,
            playerId: '', // Будет определён на сервере
          });
          break;

        case 'TOGGLE_DOOR':
          result = await this.actions.toggleDoor({
            gameId: this.gameId,
            doorId: action.params.doorId,
          });
          break;

        default:
          result = {
            success: false,
            error: 'Неизвестный тип действия',
            sequenceNumber: 0,
            phase: '',
            currentTurnPlayerId: '',
            turnCount: 0,
            timestamp: new Date(),
          };
      }
    } catch (error) {
      result = {
        success: false,
        error: error instanceof Error ? error.message : 'Неизвестная ошибка',
        sequenceNumber: 0,
        phase: '',
        currentTurnPlayerId: '',
        turnCount: 0,
        timestamp: new Date(),
      };
    }

    // Обрабатываем результат
    if (result.success) {
      // Удаляем из pending
      this.pendingActions.delete(actionId);

      // Обновляем sequence number
      this.lastServerSequence = result.sequenceNumber;

      // Уведомляем об успехе
      this.listeners.onActionComplete?.(actionId, result);
    } else {
      // Ошибка - выполняем rollback
      if (this.config.rollbackOnError && optimisticState && this.localState) {
        this.performRollback(actionId);
      }

      // Удаляем из pending
      this.pendingActions.delete(actionId);

      // Уведомляем об ошибке
      this.listeners.onActionError?.(actionId, result.error ?? 'Неизвестная ошибка');
    }

    return result;
  }

  // ------------------------------------------------------------
  // Обработчики событий от сервера
  // ------------------------------------------------------------

  /**
   * Обработчик игрового события
   */
  onGameEvent(event: GameEvent): void {
    console.log('[GameStateBridge] Игровое событие:', event.type);

    switch (event.type) {
      case 'FIGHTER_MOVED':
        this.handleFighterMoved(event);
        break;
      case 'ATTACK_INITIATED':
        this.handleAttackInitiated(event);
        break;
      case 'DEFENSE_PLAYED':
        this.handleDefensePlayed(event);
        break;
      case 'COMBAT_RESOLVED':
        this.handleCombatResolved(event);
        break;
      case 'GAME_ENDED':
        this.handleGameEnded(event);
        break;
    }
  }

  // ------------------------------------------------------------
  // Слушатели
  // ------------------------------------------------------------

  /**
   * Установить слушатели
   */
  setListeners(listeners: typeof GameStateBridge.prototype.listeners): void {
    this.listeners = { ...this.listeners, ...listeners };
  }

  // ------------------------------------------------------------
  // Приватные методы
  // ------------------------------------------------------------

  /**
   * Сгенерировать ID действия
   */
  private generateActionId(): string {
    return `action_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Добавить состояние в историю
   */
  private addToHistory(state: GameState): void {
    this.stateHistory.push({
      state: { ...state },
      sequenceNumber: this.lastServerSequence,
      timestamp: Date.now(),
    });

    // Ограничиваем размер истории
    if (this.stateHistory.length > this.maxHistorySize) {
      this.stateHistory.shift();
    }
  }

  /**
   * Применить состояние к сцене
   */
  private applyStateToScene(state: GameState): void {
    // TODO: Вызвать методы сцены для обновления визуализации
    // this.scene.updateGameState(state);
  }

  /**
   * Парсить diff из обновления
   */
  private parseDiff(update: GameStateUpdate): StateDiff {
    // TODO: Распарсить JSON поля из update
    return {
      sequenceNumber: update.sequenceNumber,
      changes: {
        phase: update.phase,
        turnCount: update.turnCount,
        currentTurnPlayerId: update.currentTurnPlayerId,
      },
    };
  }

  /**
   * Применить diff к состоянию
   */
  private applyDiffToState(state: GameState, diff: StateDiff): GameState {
    const result = { ...state };

    if (diff.changes.phase) {
      result.phase = diff.changes.phase as any;
    }

    if (diff.changes.turnCount !== undefined) {
      result.turnCount = diff.changes.turnCount;
    }

    if (diff.changes.currentTurnPlayerId) {
      result.currentTurn.currentPlayerId = diff.changes.currentTurnPlayerId;
    }

    // TODO: Применить изменения бойцов и карт

    return result;
  }

  /**
   * Применить diff к сцене
   */
  private applyDiffToScene(diff: StateDiff): void {
    // TODO: Вызвать методы сцены для частичного обновления
  }

  /**
   * Вычислить оптимистичное состояние
   */
  private computeOptimisticState(
    state: GameState,
    action: GameAction
  ): Partial<GameState> | null {
    // Клонируем состояние
    const optimistic = { ...state };

    switch (action.type) {
      case 'MANEUVER':
      case 'MOVE_FIGHTER':
        // Применяем движение к локальному состоянию
        // TODO: Обновить позицию бойца
        break;

      case 'ATTACK':
        // TODO: Показать атаку визуально
        break;

      case 'PLAY_DEFENSE':
        // TODO: Показать карту защиты
        break;

      default:
        return null;
    }

    return optimistic;
  }

  /**
   * Применить оптимистичное обновление
   */
  private applyOptimisticUpdate(action: GameAction, state: Partial<GameState>): void {
    // TODO: Применить визуальные изменения до ответа сервера

    switch (action.type) {
      case 'MANEUVER':
      case 'MOVE_FIGHTER':
        // this.scene.moveFighter(action.params.fighterId, action.params.position);
        break;
    }
  }

  /**
   * Проверить оптимистичные обновления
   *
   * Удаляет подтверждённые optimistic updates.
   */
  private checkOptimisticUpdates(serverSequence: number): void {
    // TODO: Сравнить с серверным состоянием и удалить подтверждённые
  }

  /**
   * Выполнить rollback
   */
  private performRollback(actionId: string): void {
    console.log('[GameStateBridge] Rollback для действия:', actionId);

    const pending = this.pendingActions.get(actionId);
    if (!pending || !this.localState) return;

    // Восстанавливаем из истории
    const previousEntry = this.stateHistory[this.stateHistory.length - 2];
    if (previousEntry) {
      this.localState = previousEntry.state;
      this.applyStateToScene(this.localState);
      this.listeners.onRollback?.(this.localState);
    }
  }

  // ------------------------------------------------------------
  // Обработчики конкретных событий
  // ------------------------------------------------------------

  private handleFighterMoved(event: GameEvent): void {
    try {
      const payload = typeof event.payload === 'string'
        ? JSON.parse(event.payload)
        : event.payload;

      // TODO: Применить движение к сцене
      // if (payload.fighterId && payload.position) {
      //   this.scene.moveFighter(payload.fighterId, payload.position);
      // }
    } catch (e) {
      console.error('[GameStateBridge] Ошибка парсинга события движения:', e);
    }
  }

  private handleAttackInitiated(event: GameEvent): void {
    console.log('[GameStateBridge] Атака инициирована');
    // TODO: Показать UI выбора защиты
  }

  private handleDefensePlayed(event: GameEvent): void {
    console.log('[GameStateBridge] Защита сыграна');
    // TODO: Показать сыгранную карту защиты
  }

  private handleCombatResolved(event: GameEvent): void {
    try {
      const payload = typeof event.payload === 'string'
        ? JSON.parse(event.payload)
        : event.payload;

      // TODO: Показать урон
      // if (payload.damage !== undefined) {
      //   this.scene.showDamage(payload.defenderId, payload.damage);
      // }

      // Регистрируем побеждённых бойцов
      if (payload.defenderDied && payload.defenderId) {
        this.registerDefeatedFighter(payload.defenderId);
      }
      if (payload.attackerDied && payload.attackerId) {
        this.registerDefeatedFighter(payload.attackerId);
      }
    } catch (e) {
      console.error('[GameStateBridge] Ошибка парсинга события боя:', e);
    }
  }

  private handleGameEnded(event: GameEvent): void {
    console.log('[GameStateBridge] Игра завершена');
    // TODO: Показать экран окончания игры
  }

  // ------------------------------------------------------------
  // VictoryConditions Integration
  // ------------------------------------------------------------

  /**
   * Устанавливает систему проверки условий победы
   */
  setVictoryConditions(victoryConditions: VictoryConditions): void {
    this.victoryConditions = victoryConditions;

    // Настраиваем callback для завершения игры
    this.victoryConditions.setGameStateBridge(this);
  }

  /**
   * Проверяет условия победы/поражения
   * Вызывается после каждого изменения состояния
   */
  private checkVictoryConditions(): void {
    if (!this.victoryConditions || !this.localState) {
      return;
    }

    // Игра уже завершена
    if (this.localState.phase === GamePhase.GAME_OVER || this.localState.winner) {
      return;
    }

    const result = this.victoryConditions.checkVictory(this.localState);

    if (result.result !== 'none') {
      console.log('[GameStateBridge] Обнаружено условие победы:', result);

      // Уведомляем слушателей о завершении игры
      this.listeners.onGameEnd?.(result);

      // Обновляем состояние
      if (this.localState) {
        this.localState.phase = GamePhase.GAME_OVER;
        this.localState.winner = result.winnerId;
      }
    }
  }

  /**
   * Получает текущее игровое состояние
   * Используется VictoryConditions для проверок
   */
  getCurrentState(): GameState | null {
    return this.localState;
  }

  /**
   * Регистрирует побеждённого бойца
   * Вызывается из сцены при смерти бойца
   */
  registerDefeatedFighter(fighterId: string): void {
    if (this.victoryConditions) {
      this.victoryConditions.registerDefeatedFighter(fighterId);
    }
  }
}
